"""Pure Markdown normalization helpers for the compiled-artifact pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Mapping
import warnings

from PIL import Image, UnidentifiedImageError

from src.config.content_materials import DocumentFragment
from src.services.material_content.import_contract import (
    ContentImportDisposition,
    ContentImportFinding,
)
from src.services.material_content.markdown_importer import (
    MarkdownImportError,
    discover_markdown_resource_paths,
    parse_markdown_content_with_events,
)


DEFAULT_MAX_MARKDOWN_IMAGE_PIXELS = 40_000_000

_RASTER_FORMATS: dict[str, tuple[str, frozenset[str], str]] = {
    "PNG": ("image/png", frozenset({"png"}), "png"),
    "JPEG": ("image/jpeg", frozenset({"jpg", "jpeg"}), "jpg"),
    "WEBP": ("image/webp", frozenset({"webp"}), "webp"),
    "TIFF": ("image/tiff", frozenset({"tif", "tiff"}), "tiff"),
    "BMP": ("image/bmp", frozenset({"bmp"}), "bmp"),
}


@dataclass(frozen=True, slots=True)
class MarkdownRasterInfo:
    media_type: str
    canonical_suffix: str
    width_px: int
    height_px: int


@dataclass(frozen=True, slots=True)
class MarkdownNormalization:
    fragment: DocumentFragment
    findings: tuple[ContentImportFinding, ...] = ()


def decode_markdown_source(payload: bytes) -> str:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MarkdownImportError(
            _diagnostic(
                "source_encoding_invalid",
                "Markdown source must be valid UTF-8",
                token=str(exc.start),
            )
        ) from exc


def markdown_resource_paths(markdown_text: str) -> tuple[str, ...]:
    return discover_markdown_resource_paths(markdown_text)


def inspect_markdown_raster(
    payload: bytes,
    *,
    relative_path: str,
    max_pixels: int = DEFAULT_MAX_MARKDOWN_IMAGE_PIXELS,
) -> MarkdownRasterInfo:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if isinstance(max_pixels, bool) or int(max_pixels) < 1:
        raise ValueError("max_pixels must be a positive integer")
    suffix = PurePosixPath(relative_path).suffix.casefold().lstrip(".")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as image:
                image_format = str(image.format or "").upper()
                width, height = image.size
                if width < 1 or height < 1 or width * height > int(max_pixels):
                    raise MarkdownImportError(
                        _diagnostic(
                            "resource_pixel_limit_exceeded",
                            "Markdown image exceeds the pixel limit",
                            path=relative_path,
                        )
                    )
                image.verify()
    except MarkdownImportError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning) as exc:
        raise MarkdownImportError(
            _diagnostic(
                "resource_not_raster",
                "Markdown image is not a valid supported raster image",
                path=relative_path,
            )
        ) from exc
    contract = _RASTER_FORMATS.get(image_format)
    if contract is None:
        raise MarkdownImportError(
            _diagnostic(
                "resource_raster_format_unsupported",
                "Markdown image format is not supported",
                path=relative_path,
                token=image_format,
            )
        )
    media_type, allowed_suffixes, canonical_suffix = contract
    if suffix not in allowed_suffixes:
        raise MarkdownImportError(
            _diagnostic(
                "resource_extension_mismatch",
                "Markdown image extension does not match its byte format",
                path=relative_path,
                token=suffix,
            )
        )
    return MarkdownRasterInfo(
        media_type=media_type,
        canonical_suffix=canonical_suffix,
        width_px=width,
        height_px=height,
    )


def normalize_markdown_content(
    markdown_text: str,
    *,
    source_identity: str,
    resource_id_by_path: Mapping[str, str],
) -> MarkdownNormalization:
    fragment, events = parse_markdown_content_with_events(
        markdown_text,
        resource_id_by_path=resource_id_by_path,
        source_path=source_identity,
    )
    return MarkdownNormalization(
        fragment=fragment,
        findings=tuple(_normalization_finding(code, count) for code, count in events),
    )


_WARNING_EVENTS = frozenset({"markdown_relative_link_normalized"})
_IGNORED_EVENTS = frozenset(
    {"markdown_image_title_ignored", "markdown_link_title_ignored"}
)
_EVENT_MESSAGES = {
    "markdown_blockquote_normalized": "引用已转换为目标文档中的引用段落。",
    "markdown_code_block_normalized": "代码块已按可见文本和换行导入。",
    "markdown_inline_code_normalized": "行内代码已按普通可见文本导入。",
    "markdown_task_list_normalized": "任务列表已转换为稳定的勾选符号。",
    "markdown_horizontal_rule_normalized": "分隔线已转换为目标文档分隔段落。",
    "markdown_relative_link_normalized": "相对文档链接已保留显示文字，链接目标未带入。",
    "markdown_image_title_ignored": "图片标题元数据未带入，图片和替代文字已保留。",
    "markdown_link_title_ignored": "链接标题元数据未带入，链接正文已保留。",
}


def _normalization_finding(code: str, count: int) -> ContentImportFinding:
    disposition = ContentImportDisposition.NORMALIZED
    if code in _WARNING_EVENTS:
        disposition = ContentImportDisposition.WARNING
    elif code in _IGNORED_EVENTS:
        disposition = ContentImportDisposition.IGNORED
    return ContentImportFinding(
        code=code,
        disposition=disposition,
        scope="markdown",
        object_id=code,
        cause_id=code,
        count=count,
        message_key=f"content.{code}",
        user_message=_EVENT_MESSAGES[code],
    )


def _diagnostic(code: str, message: str, *, path: str = "", token: str = ""):
    from src.services.material_content.markdown_importer import MarkdownImportDiagnostic

    return MarkdownImportDiagnostic(code, message, path=path, token=token)


__all__ = [
    "DEFAULT_MAX_MARKDOWN_IMAGE_PIXELS",
    "MarkdownNormalization",
    "MarkdownRasterInfo",
    "decode_markdown_source",
    "inspect_markdown_raster",
    "markdown_resource_paths",
    "normalize_markdown_content",
]
