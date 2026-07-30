"""Deterministic preparation and burn-in watermarking for material images.

This service is deliberately separate from the document-header watermark
module.  It consumes a frozen :class:`ResolvedImageWatermark`, never resolves
runtime fields while transforming pixels, and never overwrites the source.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
import threading
import warnings
from typing import Mapping

from PIL import (
    Image,
    ImageCms,
    ImageDraw,
    ImageFont,
    ImageOps,
    UnidentifiedImageError,
    __version__ as PILLOW_VERSION,
    features as pillow_features,
)

from src.config.content_materials import FileAssetRef
from src.config.image_materials import (
    ImageWatermarkPolicy,
    ImageWatermarkTextSource,
    ResolvedImageWatermark,
)
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    parse_material_token,
)
from src.shared.engine.material_token_router import MATERIAL_TOKEN_PATTERN
from src.shared.engine.prepared_image import (
    IMAGE_TRANSFORM_CONTRACT,
    PreparedImage as _PreparedImage,
)


IMAGE_TRANSFORM_ENGINE_VERSION = "material-image-transform-v1"
IMAGE_ORIENTATION_COLOR_CONTRACT = "exif-transpose-srgb-v1"
IMAGE_CODEC_CONTRACT = "source-jpeg-else-png-v1"
DIAGONAL_TILED_STYLE_VERSION = "diagonal_tiled_v1"
_WATERMARK_TRANSFORM_CONTRACT = IMAGE_TRANSFORM_CONTRACT
_SUPPORTED_SOURCE_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "BMP", "TIFF"})
_CACHE_LOCK = threading.RLock()
_CACHE_KEY_LOCKS: dict[str, threading.RLock] = {}


class ImageTransformError(RuntimeError):
    """A stable, reportable image preparation failure."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        super().__init__(message)
        self.code = str(code)
        self.path = str(path)


@dataclass(frozen=True, slots=True)
class ImageTransformLimits:
    """Hard resource limits for the first full-decode implementation."""

    max_pixels: int = 50_000_000
    max_decoded_bytes: int = 256 * 1024 * 1024
    max_working_bytes: int = 512 * 1024 * 1024
    max_source_bytes: int = 128 * 1024 * 1024

    def __post_init__(self) -> None:
        for name in (
            "max_pixels",
            "max_decoded_bytes",
            "max_working_bytes",
            "max_source_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class WatermarkFontResolution:
    path: str
    identity: str
    content_sha256: str

    def __post_init__(self) -> None:
        if not self.path or not self.identity:
            raise ValueError("resolved watermark font path and identity are required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_sha256):
            raise ValueError("resolved watermark font hash must be a SHA-256")


def resolve_image_watermark(
    policy: ImageWatermarkPolicy,
    field_values: Mapping[str, object],
    *,
    runtime_text: str = "",
    font_path: str | Path | None = None,
    font_identity: str = "",
) -> ResolvedImageWatermark:
    """Resolve a configuration template exactly once at the Freeze boundary."""

    if not isinstance(policy, ImageWatermarkPolicy):
        raise TypeError("policy must be an ImageWatermarkPolicy")
    if not isinstance(field_values, Mapping):
        raise TypeError("field_values must be a mapping")
    if not isinstance(runtime_text, str):
        raise TypeError("runtime_text must be a string")
    if policy.style_version != DIAGONAL_TILED_STYLE_VERSION:
        raise ImageTransformError(
            "unsupported_watermark_style",
            f"Unsupported image watermark style: {policy.style_version}",
        )
    if not policy.enabled:
        return ResolvedImageWatermark.disabled(
            style_version=policy.style_version,
            transform_contract=_WATERMARK_TRANSFORM_CONTRACT,
        )

    if policy.text_source is ImageWatermarkTextSource.WORKBENCH_FREE_FIELD:
        resolved_text = runtime_text.strip()
        if not resolved_text:
            raise ImageTransformError(
                "runtime_watermark_text_missing",
                "Image watermark text must be supplied by Workbench for this run.",
            )
    else:
        template = policy.text_template
        if not template.strip():
            raise ImageTransformError(
                "empty_watermark_template",
                "Image watermark is enabled but its fixed text template is empty.",
            )

        replacements: list[tuple[int, int, str]] = []
        for match in MATERIAL_TOKEN_PATTERN.finditer(template):
            raw_key = match.group(1)
            key = raw_key.strip()
            if raw_key != key or not key:
                raise ImageTransformError(
                    "invalid_watermark_token",
                    f"Invalid watermark token {match.group(0)!r}.",
                )
            try:
                token_ref = parse_material_token(match.group(0))
            except (TypeError, ValueError) as exc:
                raise ImageTransformError(
                    "invalid_watermark_token",
                    f"Invalid watermark token {match.group(0)!r}.",
                ) from exc
            if token_ref.kind is not MaterialTokenKind.FIELD:
                raise ImageTransformError(
                    "non_field_watermark_token",
                    f"Only field tokens are allowed in image watermarks: {match.group(0)}",
                )
            lookup_key = (
                token_ref.identifier
                if token_ref.identifier in field_values
                else token_ref.key
            )
            if lookup_key not in field_values:
                raise ImageTransformError(
                    "unresolved_watermark_field",
                    f"Watermark field {match.group(0)} has no frozen value.",
                )
            value = field_values[lookup_key]
            if value is None or isinstance(
                value, (Mapping, list, tuple, set, bytes, bytearray)
            ):
                raise ImageTransformError(
                    "invalid_watermark_field_value",
                    f"Watermark field {match.group(0)} is not a scalar value.",
                )
            replacements.append((match.start(), match.end(), str(value)))

        resolved_text = template
        for start, end, value in reversed(replacements):
            resolved_text = resolved_text[:start] + value + resolved_text[end:]
    if "{{" in resolved_text or "}}" in resolved_text:
        raise ImageTransformError(
            "invalid_or_recursive_watermark_template",
            "Watermark text contains an invalid or recursively produced token.",
        )
    resolved_text = resolved_text.strip()
    if not resolved_text:
        raise ImageTransformError(
            "empty_resolved_watermark", "Resolved image watermark text is empty."
        )
    if len(resolved_text) > 512 or len(resolved_text.encode("utf-8")) > 4096:
        raise ImageTransformError(
            "watermark_text_too_long",
            "Resolved image watermark text exceeds the supported first-version limit.",
        )

    font_resolution = resolve_watermark_font(
        resolved_text,
        candidate_paths=() if font_path is None else (font_path,),
    )
    resolved_font_path = Path(font_resolution.path)
    font_bytes = resolved_font_path.read_bytes()
    resolved_font_hash = sha256(font_bytes).hexdigest()
    try:
        ImageFont.truetype(str(resolved_font_path), 16)
    except OSError as exc:
        raise ImageTransformError(
            "unreadable_watermark_font",
            f"Watermark font cannot be loaded: {resolved_font_path}",
            path=str(resolved_font_path),
        ) from exc

    identity = str(font_identity or "").strip()
    if not identity:
        identity = font_resolution.identity
    return ResolvedImageWatermark(
        enabled=True,
        resolved_text=resolved_text,
        resolved_text_sha256=sha256(resolved_text.encode("utf-8")).hexdigest(),
        resolved_font_identity=identity,
        resolved_font_sha256=resolved_font_hash,
        style_version=policy.style_version,
        transform_contract=_WATERMARK_TRANSFORM_CONTRACT,
    )


def resolve_watermark_font(
    text: str,
    *,
    candidate_paths: tuple[str | Path, ...] = (),
) -> WatermarkFontResolution:
    """Resolve a readable font file with glyph coverage for CJK watermark text."""

    if not isinstance(text, str) or not text.strip():
        raise ImageTransformError(
            "empty_watermark_text", "Watermark text is required to resolve a font."
        )
    candidates = [Path(item) for item in candidate_paths]
    candidates.extend(_default_watermark_font_candidates())
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(str(candidate)))
        if key in seen:
            continue
        seen.add(key)
        if not candidate.is_file() or candidate.suffix.casefold() not in {
            ".ttf",
            ".otf",
            ".ttc",
        }:
            continue
        try:
            font = ImageFont.truetype(str(candidate), 32)
        except OSError:
            continue
        if not _font_supports_text(font, text):
            continue
        content_hash = _sha256_file(candidate)
        return WatermarkFontResolution(
            path=str(candidate),
            identity=f"{candidate.name}:{content_hash[:16]}",
            content_sha256=content_hash,
        )
    raise ImageTransformError(
        "watermark_font_unavailable",
        "No installed TrueType/OpenType font can render the resolved watermark text.",
    )


def build_image_transform_cache_key(
    image_ref: FileAssetRef,
    watermark: ResolvedImageWatermark,
    *,
    jpeg_quality: int = 95,
) -> str:
    """Hash all facts that can change prepared pixels or their encoding."""

    _validate_jpeg_quality(jpeg_quality)
    if not isinstance(image_ref, FileAssetRef):
        raise TypeError("image_ref must be a FileAssetRef")
    if not isinstance(watermark, ResolvedImageWatermark):
        raise TypeError("watermark must be a ResolvedImageWatermark")
    if watermark.enabled:
        actual_text_hash = sha256(watermark.resolved_text.encode("utf-8")).hexdigest()
        if actual_text_hash != watermark.resolved_text_sha256:
            raise ImageTransformError(
                "watermark_text_hash_mismatch",
                "Resolved watermark text no longer matches its frozen hash.",
            )
        if len(watermark.resolved_text) > 512 or len(
            watermark.resolved_text.encode("utf-8")
        ) > 4096:
            raise ImageTransformError(
                "watermark_text_too_long",
                "Resolved image watermark text exceeds the supported first-version limit.",
            )
    payload = {
        "source_sha256": image_ref.content_sha256,
        "watermark_enabled": watermark.enabled,
        "resolved_text_sha256": watermark.resolved_text_sha256,
        "resolved_font_identity": watermark.resolved_font_identity,
        "resolved_font_sha256": watermark.resolved_font_sha256,
        "style_version": watermark.style_version,
        "declared_transform_contract": watermark.transform_contract,
        "engine_version": IMAGE_TRANSFORM_ENGINE_VERSION,
        "pillow_version": PILLOW_VERSION,
        "freetype_version": pillow_features.version("freetype2") or "",
        "jpeg_library_version": pillow_features.version("jpg") or "",
        "orientation_color_contract": IMAGE_ORIENTATION_COLOR_CONTRACT,
        "codec_contract": IMAGE_CODEC_CONTRACT,
        "jpeg_quality": jpeg_quality,
        "jpeg_subsampling": 0,
        "png_compress_level": 6,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def prepare_material_image(
    source_path: str | Path,
    image_ref: FileAssetRef,
    watermark: ResolvedImageWatermark,
    *,
    cache_dir: str | Path,
    font_path: str | Path | None = None,
    limits: ImageTransformLimits | None = None,
    jpeg_quality: int = 95,
) -> _PreparedImage:
    """Normalize, optionally watermark, and atomically cache one image."""

    if not isinstance(image_ref, FileAssetRef):
        raise TypeError("image_ref must be a FileAssetRef")
    if not image_ref.media_type.casefold().startswith("image/"):
        raise ImageTransformError("not_an_image", "The supplied file reference is not an image.")
    if not isinstance(watermark, ResolvedImageWatermark):
        raise TypeError("watermark must be a ResolvedImageWatermark")
    if watermark.transform_contract != _WATERMARK_TRANSFORM_CONTRACT:
        raise ImageTransformError(
            "transform_contract_mismatch",
            "Resolved watermark was frozen for a different transform contract.",
        )
    if watermark.style_version != DIAGONAL_TILED_STYLE_VERSION:
        raise ImageTransformError(
            "unsupported_watermark_style",
            f"Unsupported image watermark style: {watermark.style_version}",
        )
    if watermark.enabled:
        if sha256(watermark.resolved_text.encode("utf-8")).hexdigest() != (
            watermark.resolved_text_sha256
        ):
            raise ImageTransformError(
                "watermark_text_hash_mismatch",
                "Resolved watermark text no longer matches its frozen hash.",
            )
        if len(watermark.resolved_text) > 512 or len(
            watermark.resolved_text.encode("utf-8")
        ) > 4096:
            raise ImageTransformError(
                "watermark_text_too_long",
                "Resolved image watermark text exceeds the supported first-version limit.",
            )
    _validate_jpeg_quality(jpeg_quality)
    effective_limits = limits or ImageTransformLimits()
    source = Path(source_path)
    if not source.is_file():
        raise ImageTransformError("source_missing", f"Image source does not exist: {source}", path=str(source))
    stat = source.stat()
    if stat.st_size > effective_limits.max_source_bytes:
        raise ImageTransformError(
            "source_size_limit_exceeded",
            f"Image source exceeds {effective_limits.max_source_bytes} bytes.",
            path=str(source),
        )
    if stat.st_size != image_ref.byte_size:
        raise ImageTransformError("source_size_mismatch", "Image source size no longer matches its frozen reference.", path=str(source))
    source_hash = _sha256_file(source)
    if source_hash != image_ref.content_sha256:
        raise ImageTransformError("source_hash_mismatch", "Image source hash no longer matches its frozen reference.", path=str(source))

    resolved_font_path: Path | None = None
    if watermark.enabled:
        if font_path is None:
            resolved_font_path = Path(resolve_watermark_font(watermark.resolved_text).path)
        else:
            resolved_font_path = _validated_font_path(font_path)
        if _sha256_file(resolved_font_path) != watermark.resolved_font_sha256:
            raise ImageTransformError(
                "watermark_font_hash_mismatch",
                "Watermark font bytes no longer match the frozen font hash.",
                path=str(resolved_font_path),
            )

    cache_key = build_image_transform_cache_key(
        image_ref, watermark, jpeg_quality=jpeg_quality
    )
    target_dir = Path(cache_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with _cache_lock_for_key(cache_key):
        cached = _find_valid_cached_image(target_dir, cache_key, image_ref, watermark)
        if cached is not None:
            return cached

        image, source_format = _load_normalized_image(source, effective_limits)
        if watermark.enabled:
            assert resolved_font_path is not None
            image = _burn_diagonal_tiled_watermark(
                image, watermark.resolved_text, resolved_font_path
            )
        output_format, extension, media_type = _select_output_codec(
            image, source_format
        )
        output_path = target_dir / f"prepared-{cache_key}.{extension}"
        temp_path = target_dir / f".prepared-{cache_key}.{os.getpid()}.tmp.{extension}"
        try:
            _save_deterministic_image(
                image,
                temp_path,
                output_format=output_format,
                jpeg_quality=jpeg_quality,
            )
            os.replace(temp_path, output_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
        if _sha256_file(source) != source_hash:
            raise ImageTransformError(
                "source_mutated", "The image source changed during preparation.", path=str(source)
            )
        output_hash = _sha256_file(output_path)
        prepared = _PreparedImage(
            cache_key=cache_key,
            output_path=str(output_path),
            output_sha256=output_hash,
            media_type=media_type,
            width_px=image.width,
            height_px=image.height,
            source_sha256=source_hash,
            watermark_text_sha256=watermark.resolved_text_sha256,
            cache_hit=False,
        )
        _atomic_write_json(
            target_dir / f"prepared-{cache_key}.json",
            {
                "cache_key": cache_key,
                "output_file": output_path.name,
                "output_sha256": output_hash,
                "media_type": media_type,
                "width_px": image.width,
                "height_px": image.height,
                "source_sha256": source_hash,
                "watermark_text_sha256": watermark.resolved_text_sha256,
                "transform_contract": _WATERMARK_TRANSFORM_CONTRACT,
            },
        )
        return prepared


def load_cached_material_image(
    cache_dir: str | Path,
    image_ref: FileAssetRef,
    watermark: ResolvedImageWatermark,
    *,
    jpeg_quality: int = 95,
) -> _PreparedImage | None:
    """Load one cache entry only when its manifest and bytes still agree."""

    cache_key = build_image_transform_cache_key(
        image_ref, watermark, jpeg_quality=jpeg_quality
    )
    directory = Path(cache_dir)
    if not directory.is_dir():
        return None
    with _cache_lock_for_key(cache_key):
        return _find_valid_cached_image(directory, cache_key, image_ref, watermark)


def _validated_font_path(font_path: str | Path | None) -> Path:
    if font_path is None:
        raise ImageTransformError(
            "watermark_font_required", "An explicit resolved font file is required."
        )
    path = Path(font_path)
    if not path.is_file() or path.suffix.casefold() not in {".ttf", ".otf", ".ttc"}:
        raise ImageTransformError(
            "watermark_font_missing", f"Watermark font file is unavailable: {path}", path=str(path)
        )
    return path


def _default_watermark_font_candidates() -> tuple[Path, ...]:
    if sys.platform == "win32":
        font_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        local_dir = (
            Path.home()
            / "AppData"
            / "Local"
            / "Microsoft"
            / "Windows"
            / "Fonts"
        )
        names = (
            "msyh.ttc",
            "msyh.ttf",
            "simsun.ttc",
            "simhei.ttf",
            "Deng.ttf",
            "arial.ttf",
        )
        return tuple(directory / name for directory in (font_dir, local_dir) for name in names)
    if sys.platform == "darwin":
        return (
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        )
    return (
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )


def _font_supports_text(font: ImageFont.FreeTypeFont, text: str) -> bool:
    required = tuple(
        dict.fromkeys(
            char
            for char in text
            if not char.isspace() and _requires_explicit_glyph_check(char)
        )
    )
    if not required:
        return True
    missing_signatures: set[tuple[tuple[int, int], bytes]] = set()
    for sentinel in ("\ufffd", "\uffff", "\U0010ffff"):
        try:
            mask = font.getmask(sentinel)
            missing_signatures.add((mask.size, bytes(mask)))
        except (OSError, ValueError):
            continue
    for char in required:
        try:
            mask = font.getmask(char)
        except (OSError, ValueError):
            return False
        signature = (mask.size, bytes(mask))
        if not mask.getbbox() or signature in missing_signatures:
            return False
    return True


def _requires_explicit_glyph_check(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    )


def _load_normalized_image(
    source: Path, limits: ImageTransformLimits
) -> tuple[Image.Image, str]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as probe:
                source_format = str(probe.format or "").upper()
                if source_format not in _SUPPORTED_SOURCE_FORMATS:
                    raise ImageTransformError(
                        "unsupported_image_format",
                        f"Unsupported image format: {source_format or '<unknown>'}",
                        path=str(source),
                    )
                width, height = probe.size
                _enforce_decoded_limits(width, height, limits, source)
                probe.verify()
            with Image.open(source) as opened:
                opened.load()
                oriented = ImageOps.exif_transpose(opened)
                image = _normalize_color_and_alpha(oriented)
    except ImageTransformError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageTransformError(
            "decompression_bomb", "Image dimensions exceed Pillow's safety threshold.", path=str(source)
        ) from exc
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise ImageTransformError(
            "unreadable_image", f"Image bytes cannot be decoded: {source}", path=str(source)
        ) from exc
    _enforce_decoded_limits(image.width, image.height, limits, source)
    return image, source_format


def _normalize_color_and_alpha(image: Image.Image) -> Image.Image:
    icc_profile = image.info.get("icc_profile")
    has_alpha = image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )
    if icc_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(BytesIO(icc_profile))
            target_profile = ImageCms.createProfile("sRGB")
            source_image = image.convert("RGBA") if has_alpha else image
            image = ImageCms.profileToProfile(
                source_image,
                source_profile,
                target_profile,
                outputMode="RGBA" if has_alpha else "RGB",
            )
        except (OSError, ValueError, ImageCms.PyCMSError) as exc:
            raise ImageTransformError(
                "invalid_icc_profile", "Embedded image color profile is invalid."
            ) from exc
    if has_alpha:
        return image.convert("RGBA")
    return image.convert("RGB")


def _enforce_decoded_limits(
    width: int, height: int, limits: ImageTransformLimits, source: Path
) -> None:
    pixels = int(width) * int(height)
    if pixels <= 0:
        raise ImageTransformError("invalid_dimensions", "Image dimensions must be positive.", path=str(source))
    if pixels > limits.max_pixels:
        raise ImageTransformError(
            "pixel_limit_exceeded",
            f"Image has {pixels} pixels; limit is {limits.max_pixels}.",
            path=str(source),
        )
    estimated_bytes = pixels * 4
    if estimated_bytes > limits.max_decoded_bytes:
        raise ImageTransformError(
            "decoded_memory_limit_exceeded",
            f"Decoded image needs about {estimated_bytes} bytes; limit is {limits.max_decoded_bytes}.",
            path=str(source),
        )
    working_bytes = estimated_bytes * 4
    if working_bytes > limits.max_working_bytes:
        raise ImageTransformError(
            "working_memory_limit_exceeded",
            f"Image transform needs about {working_bytes} bytes; limit is {limits.max_working_bytes}.",
            path=str(source),
        )


def _burn_diagonal_tiled_watermark(
    image: Image.Image, text: str, font_path: Path
) -> Image.Image:
    base = image.convert("RGBA")
    short_edge = min(base.size)
    font_size = max(12, min(96, int(round(short_edge * 0.045))))
    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except OSError as exc:
        raise ImageTransformError(
            "unreadable_watermark_font", f"Watermark font cannot be loaded: {font_path}", path=str(font_path)
        ) from exc

    measure = Image.new("L", (1, 1), 0)
    bbox = ImageDraw.Draw(measure).textbbox((0, 0), text, font=font)
    text_width = max(1, bbox[2] - bbox[0])
    text_height = max(1, bbox[3] - bbox[1])
    padding_x = font_size
    padding_y = max(6, font_size // 2)
    tile = Image.new(
        "RGBA",
        (text_width + 2 * padding_x, text_height + 2 * padding_y),
        (0, 0, 0, 0),
    )
    ImageDraw.Draw(tile).text(
        (padding_x - bbox[0], padding_y - bbox[1]),
        text,
        font=font,
        fill=(145, 145, 145, 78),
    )
    rotated = tile.rotate(
        -35,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    step_x = rotated.width + max(font_size * 2, short_edge // 12)
    step_y = rotated.height + max(font_size, short_edge // 18)
    row = 0
    y = -rotated.height
    while y < base.height + rotated.height:
        offset = -(step_x // 2) if row % 2 else -rotated.width
        x = offset
        while x < base.width + rotated.width:
            overlay.alpha_composite(rotated, (x, y))
            x += step_x
        row += 1
        y += step_y
    return Image.alpha_composite(base, overlay)


def _select_output_codec(
    image: Image.Image, source_format: str
) -> tuple[str, str, str]:
    alpha = image.getchannel("A") if image.mode == "RGBA" else None
    has_transparency = alpha is not None and alpha.getextrema()[0] < 255
    if source_format == "JPEG" and not has_transparency:
        return "JPEG", "jpg", "image/jpeg"
    return "PNG", "png", "image/png"


def _save_deterministic_image(
    image: Image.Image,
    path: Path,
    *,
    output_format: str,
    jpeg_quality: int,
) -> None:
    if output_format == "JPEG":
        image.convert("RGB").save(
            path,
            format="JPEG",
            quality=jpeg_quality,
            subsampling=0,
            optimize=False,
            progressive=False,
            exif=b"",
            icc_profile=None,
        )
        return
    image.save(path, format="PNG", compress_level=6, optimize=False)


def _find_valid_cached_image(
    cache_dir: Path,
    cache_key: str,
    image_ref: FileAssetRef,
    watermark: ResolvedImageWatermark,
) -> _PreparedImage | None:
    manifest_path = cache_dir / f"prepared-{cache_key}.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict):
        return None
    if (
        manifest.get("cache_key") != cache_key
        or manifest.get("source_sha256") != image_ref.content_sha256
        or manifest.get("watermark_text_sha256") != watermark.resolved_text_sha256
        or manifest.get("transform_contract") != _WATERMARK_TRANSFORM_CONTRACT
    ):
        return None
    for extension, media_type in (("png", "image/png"), ("jpg", "image/jpeg")):
        path = cache_dir / f"prepared-{cache_key}.{extension}"
        if manifest.get("output_file") != path.name or manifest.get("media_type") != media_type:
            continue
        if not path.is_file():
            continue
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
        except (OSError, ValueError, UnidentifiedImageError):
            continue
        output_hash = _sha256_file(path)
        if output_hash != manifest.get("output_sha256"):
            continue
        if width != manifest.get("width_px") or height != manifest.get("height_px"):
            continue
        return _PreparedImage(
            cache_key=cache_key,
            output_path=str(path),
            output_sha256=output_hash,
            media_type=media_type,
            width_px=width,
            height_px=height,
            source_sha256=image_ref.content_sha256,
            watermark_text_sha256=watermark.resolved_text_sha256,
            cache_hit=True,
        )
    return None


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        temp_path.write_text(encoded, encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _cache_lock_for_key(cache_key: str) -> threading.RLock:
    with _CACHE_LOCK:
        lock = _CACHE_KEY_LOCKS.get(cache_key)
        if lock is None:
            lock = threading.RLock()
            _CACHE_KEY_LOCKS[cache_key] = lock
        return lock


def _validate_jpeg_quality(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise ValueError("jpeg_quality must be an integer between 1 and 100")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "DIAGONAL_TILED_STYLE_VERSION",
    "IMAGE_CODEC_CONTRACT",
    "IMAGE_ORIENTATION_COLOR_CONTRACT",
    "IMAGE_TRANSFORM_ENGINE_VERSION",
    "ImageTransformError",
    "ImageTransformLimits",
    "WatermarkFontResolution",
    "build_image_transform_cache_key",
    "load_cached_material_image",
    "prepare_material_image",
    "resolve_image_watermark",
    "resolve_watermark_font",
]
