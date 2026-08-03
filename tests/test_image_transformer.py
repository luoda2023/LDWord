from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from src.config.content_materials import FileAssetRef
from src.config.image_materials import (
    ImageWatermarkPolicy,
    ImageWatermarkTextSource,
)
from src.services.material_assets import image_transformer as image_transformer_module
from src.services.material_assets.image_transformer import (
    ImageTransformError,
    ImageTransformLimits,
    build_image_transform_cache_key,
    prepare_material_image,
    resolve_image_watermark,
)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _ref(path: Path, media_type: str) -> FileAssetRef:
    return FileAssetRef(
        source_path=str(path),
        original_name=path.name,
        media_type=media_type,
        content_sha256=_sha(path),
        byte_size=path.stat().st_size,
    )


@pytest.fixture(scope="module")
def font_path() -> Path:
    candidates = (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    pytest.skip("No usable TrueType/OpenType font is available")


def test_resolve_watermark_freezes_fields_font_and_hashes(font_path: Path):
    resolved = resolve_image_watermark(
        ImageWatermarkPolicy(
            enabled=True,
            text_template="投标人：{{@text:company_name}}  项目：{{@text:project_name}}",
        ),
        {"company_name": "示例公司", "project_name": "安全评估"},
        font_path=font_path,
        font_identity="fixture-font",
    )

    assert resolved.enabled is True
    assert resolved.resolved_text == "投标人：示例公司  项目：安全评估"
    assert resolved.resolved_text_sha256 == sha256(
        resolved.resolved_text.encode("utf-8")
    ).hexdigest()
    assert resolved.resolved_font_sha256 == _sha(font_path)
    assert resolved.resolved_font_identity == "fixture-font"
    assert "{{" not in resolved.resolved_text


def test_resolve_watermark_honors_requested_font_family(
    font_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    requested: list[str] = []

    def candidates(font_family: str) -> tuple[Path, ...]:
        requested.append(font_family)
        return (font_path,)

    monkeypatch.setattr(
        image_transformer_module,
        "_font_family_candidates",
        candidates,
    )

    resolved = resolve_image_watermark(
        ImageWatermarkPolicy(enabled=True, text_template="内部资料"),
        {},
        font_family="宋体",
    )

    assert requested == ["宋体"]
    assert resolved.resolved_font_sha256 == _sha(font_path)


@pytest.mark.parametrize(
    ("template", "values", "code"),
    [
        ("{{@text:missing}}", {}, "unresolved_watermark_field"),
        ("{{@file:route}}", {}, "non_field_watermark_token"),
        ("{{ bad }}", {"bad": "x"}, "invalid_watermark_token"),
        ("{{@text:name}}", {"name": "{{@text:other}}"}, "invalid_or_recursive_watermark_template"),
        ("{{@text:name", {"name": "x"}, "invalid_or_recursive_watermark_template"),
    ],
)
def test_resolve_watermark_blocks_invalid_or_unresolved_templates(
    font_path: Path, template: str, values: dict[str, object], code: str
):
    with pytest.raises(ImageTransformError) as caught:
        resolve_image_watermark(
            ImageWatermarkPolicy(enabled=True, text_template=template),
            values,
            font_path=font_path,
        )
    assert caught.value.code == code


def test_disabled_watermark_needs_no_font_and_uses_execution_contract():
    resolved = resolve_image_watermark(
        ImageWatermarkPolicy(enabled=False, text_template="{{@text:missing}}"), {}
    )
    assert resolved.enabled is False
    assert resolved.transform_contract == "image-transform-v1"


def test_workbench_free_watermark_uses_runtime_text_only(font_path: Path):
    policy = ImageWatermarkPolicy(
        enabled=True,
        text_source=ImageWatermarkTextSource.WORKBENCH_FREE_FIELD,
    )

    resolved = resolve_image_watermark(
        policy,
        {"ignored": "field value"},
        runtime_text=" 本次投标专用123456 ",
        font_path=font_path,
    )

    assert resolved.resolved_text == "本次投标专用123456"
    with pytest.raises(ImageTransformError) as caught:
        resolve_image_watermark(policy, {}, font_path=font_path)
    assert caught.value.code == "runtime_watermark_text_missing"


def test_watermark_resolution_blocks_unbounded_text(font_path: Path):
    with pytest.raises(ImageTransformError) as raised:
        resolve_image_watermark(
            ImageWatermarkPolicy(enabled=True, text_template="水" * 513),
            {},
            font_path=font_path,
        )
    assert raised.value.code == "watermark_text_too_long"


def test_prepare_png_burns_tiled_watermark_without_mutating_source_and_hits_cache(
    tmp_path: Path, font_path: Path
):
    source = tmp_path / "qualification.png"
    Image.new("RGB", (720, 960), "white").save(source)
    original_bytes = source.read_bytes()
    ref = _ref(source, "image/png")
    watermark = resolve_image_watermark(
        ImageWatermarkPolicy(enabled=True, text_template="示例水印1234567891011"),
        {},
        font_path=font_path,
    )

    first = prepare_material_image(
        source,
        ref,
        watermark,
        cache_dir=tmp_path / "cache",
        font_path=font_path,
    )
    second = prepare_material_image(
        source,
        ref,
        watermark,
        cache_dir=tmp_path / "cache",
        font_path=font_path,
    )

    assert source.read_bytes() == original_bytes
    assert first.media_type == "image/png"
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.output_sha256 == first.output_sha256
    with Image.open(first.output_path) as prepared:
        white = Image.new("RGB", prepared.size, "white")
        assert ImageChops.difference(prepared.convert("RGB"), white).getbbox() is not None


def test_exif_transpose_cmyk_and_alpha_normalization(tmp_path: Path):
    oriented = tmp_path / "oriented.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("CMYK", (40, 80), (0, 128, 128, 0)).save(
        oriented, format="JPEG", exif=exif
    )
    disabled = resolve_image_watermark(ImageWatermarkPolicy(enabled=False), {})
    receipt = prepare_material_image(
        oriented,
        _ref(oriented, "image/jpeg"),
        disabled,
        cache_dir=tmp_path / "jpeg-cache",
    )
    assert (receipt.width_px, receipt.height_px) == (80, 40)
    assert receipt.media_type == "image/jpeg"
    with Image.open(receipt.output_path) as output:
        assert output.mode == "RGB"

    alpha = tmp_path / "alpha.png"
    image = Image.new("RGBA", (30, 20), (10, 20, 30, 0))
    image.putpixel((10, 10), (10, 20, 30, 255))
    image.save(alpha)
    alpha_receipt = prepare_material_image(
        alpha,
        _ref(alpha, "image/png"),
        disabled,
        cache_dir=tmp_path / "alpha-cache",
    )
    assert alpha_receipt.media_type == "image/png"
    with Image.open(alpha_receipt.output_path) as output:
        assert output.mode == "RGBA"
        assert output.getchannel("A").getextrema() == (0, 255)


def test_transform_is_deterministic_and_cache_key_separates_profiles(
    tmp_path: Path, font_path: Path
):
    source = tmp_path / "source.png"
    Image.new("RGB", (420, 300), (230, 235, 240)).save(source)
    ref = _ref(source, "image/png")
    one = resolve_image_watermark(
        ImageWatermarkPolicy(enabled=True, text_template="公司甲"),
        {},
        font_path=font_path,
    )
    two = resolve_image_watermark(
        ImageWatermarkPolicy(enabled=True, text_template="公司乙"),
        {},
        font_path=font_path,
    )
    assert build_image_transform_cache_key(ref, one) != build_image_transform_cache_key(
        ref, two
    )

    first = prepare_material_image(
        source, ref, one, cache_dir=tmp_path / "a", font_path=font_path
    )
    second = prepare_material_image(
        source, ref, one, cache_dir=tmp_path / "b", font_path=font_path
    )
    assert first.output_sha256 == second.output_sha256


def test_cache_manifest_detects_valid_image_pollution_and_rebuilds(
    tmp_path: Path,
):
    source = tmp_path / "source.png"
    Image.new("RGB", (80, 60), "white").save(source)
    ref = _ref(source, "image/png")
    disabled = resolve_image_watermark(ImageWatermarkPolicy(enabled=False), {})
    first = prepare_material_image(
        source, ref, disabled, cache_dir=tmp_path / "cache"
    )
    Image.new("RGB", (80, 60), "black").save(first.output_path)

    rebuilt = prepare_material_image(
        source, ref, disabled, cache_dir=tmp_path / "cache"
    )

    assert rebuilt.cache_hit is False
    assert rebuilt.output_sha256 == first.output_sha256


def test_source_hash_and_resource_limits_block_before_output(tmp_path: Path):
    source = tmp_path / "large.png"
    Image.new("RGB", (100, 100), "white").save(source)
    ref = _ref(source, "image/png")
    disabled = resolve_image_watermark(ImageWatermarkPolicy(enabled=False), {})

    with pytest.raises(ImageTransformError) as limited:
        prepare_material_image(
            source,
            ref,
            disabled,
            cache_dir=tmp_path / "limited",
            limits=ImageTransformLimits(max_pixels=9_999),
        )
    assert limited.value.code == "pixel_limit_exceeded"
    assert not list((tmp_path / "limited").glob("prepared-*"))

    with pytest.raises(ImageTransformError) as working_limited:
        prepare_material_image(
            source,
            ref,
            disabled,
            cache_dir=tmp_path / "working-limited",
            limits=ImageTransformLimits(max_working_bytes=100 * 100 * 4 * 4 - 1),
        )
    assert working_limited.value.code == "working_memory_limit_exceeded"

    source.write_bytes(source.read_bytes() + b"pollution")
    with pytest.raises(ImageTransformError) as changed:
        prepare_material_image(
            source, ref, disabled, cache_dir=tmp_path / "changed"
        )
    assert changed.value.code == "source_size_mismatch"
