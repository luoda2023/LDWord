from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image
import pytest

from src.config.content_materials import FileAssetRef
from src.config.image_materials import (
    ImageAnchorRef,
    ImagePlacementPolicy,
    ImageWatermarkPolicy,
    ResolvedImageInsertionPlan,
    ResolvedImageWatermark,
)
import src.services.material_assets.image_transform_batch as batch_module
from src.services.material_assets.image_transform_batch import (
    MAX_IMAGE_TRANSFORM_WORKERS,
    ImageTransformBatch,
    ImageTransformBatchBudget,
    ImageTransformBatchError,
)
from src.services.material_assets.image_transformer import (
    ImageTransformError,
    prepare_material_image,
    resolve_image_watermark,
)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _image(path: Path, color: str = "red", size: tuple[int, int] = (32, 24)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=color).save(path, format="PNG")
    return path


def _ref(path: Path, *, source_path: str | None = None, original_name: str = "") -> FileAssetRef:
    return FileAssetRef(
        source_path=source_path or str(path),
        original_name=original_name or path.name,
        media_type="image/png",
        content_sha256=_sha(path),
        byte_size=path.stat().st_size,
    )


def _plan(
    job_id: str,
    path: Path,
    *,
    image_ref: FileAssetRef | None = None,
    watermark: ResolvedImageWatermark | None = None,
    source_role: str = "qualification",
) -> ResolvedImageInsertionPlan:
    return ResolvedImageInsertionPlan(
        job_id=job_id,
        image_ref=image_ref or _ref(path),
        anchor=ImageAnchorRef(
            "material_token",
            f"anchor-{job_id}",
            f"{{{{IMAGE_{job_id}}}}}",
        ),
        occurrence_id=f"occurrence-{job_id}",
        watermark=watermark or ResolvedImageWatermark.disabled(),
        placement=ImagePlacementPolicy(mode="fixed_box", fixed_width_cm=6.0),
        source_role=source_role,
        sequence=0,
    )


@pytest.fixture(scope="module")
def font_path() -> Path:
    candidates = (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    pytest.skip("No usable TrueType/OpenType font is available")


def test_same_cache_key_transforms_once_and_shares_one_prepared_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _image(tmp_path / "qualification.png")
    original = source.read_bytes()
    shared_ref = _ref(source)
    plans = (
        _plan("variant-a", source, image_ref=shared_ref),
        _plan("variant-b", source, image_ref=shared_ref),
    )
    calls = 0

    def counting_transform(*args, **kwargs):
        nonlocal calls
        calls += 1
        return prepare_material_image(*args, **kwargs)

    monkeypatch.setattr(batch_module, "prepare_material_image", counting_transform)
    result = ImageTransformBatch(plans, cache_dir=tmp_path / "cache").run()

    assert calls == 1
    assert result.prepared_for("variant-a") is result.prepared_for("variant-b")
    assert result.receipt.unique_cache_key_count == 1
    assert result.receipt.transformed_group_count == 1
    assert source.read_bytes() == original
    assert "batches" in Path(result.prepared_for("variant-a").output_path).parts


def test_different_profile_watermark_facts_never_share_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, font_path: Path
) -> None:
    source = _image(tmp_path / "shared.png", "white")
    first_watermark = resolve_image_watermark(
        ImageWatermarkPolicy(enabled=True, text_template="profile-A"),
        {},
        font_path=font_path,
    )
    second_watermark = resolve_image_watermark(
        ImageWatermarkPolicy(enabled=True, text_template="profile-B"),
        {},
        font_path=font_path,
    )
    calls = 0

    def counting_transform(*args, **kwargs):
        nonlocal calls
        calls += 1
        return prepare_material_image(*args, **kwargs)

    monkeypatch.setattr(batch_module, "prepare_material_image", counting_transform)
    result = ImageTransformBatch(
        (
            _plan("profile-a", source, watermark=first_watermark, source_role="profile-a"),
            _plan("profile-b", source, watermark=second_watermark, source_role="profile-b"),
        ),
        cache_dir=tmp_path / "cache",
        font_path_resolver=lambda _plan: font_path,
    ).run()

    assert calls == 2
    assert result.receipt.unique_cache_key_count == 2
    assert result.prepared_for("profile-a").cache_key != result.prepared_for(
        "profile-b"
    ).cache_key
    assert (
        result.prepared_for("profile-a").watermark_text_sha256
        != result.prepared_for("profile-b").watermark_text_sha256
    )


def test_all_jobs_preflight_before_any_transform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _image(tmp_path / "source.png")
    plan = _plan("duplicate", source)
    calls = 0

    def forbidden_transform(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("transform must not start during failed preflight")

    monkeypatch.setattr(batch_module, "prepare_material_image", forbidden_transform)
    with pytest.raises(ImageTransformBatchError) as raised:
        ImageTransformBatch((plan, plan), cache_dir=tmp_path / "cache").run()

    assert raised.value.code == "duplicate_job_id"
    assert raised.value.job_id == "duplicate"
    assert calls == 0
    assert not (tmp_path / "cache").exists()


def test_source_path_resolver_and_source_ref_conflict_are_preflighted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _image(tmp_path / "source.png")
    relative_ref = _ref(source, source_path="package/images/source.png")
    valid = _plan("resolved", source, image_ref=relative_ref)
    result = ImageTransformBatch(
        (valid,),
        cache_dir=tmp_path / "cache",
        source_path_resolver=lambda _plan: source,
    ).run()
    assert result.prepared_for("resolved").source_sha256 == relative_ref.content_sha256

    conflicting_ref = _ref(source, original_name="different-name.png")
    calls = 0

    def forbidden_transform(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError

    monkeypatch.setattr(batch_module, "prepare_material_image", forbidden_transform)
    with pytest.raises(ImageTransformBatchError) as raised:
        ImageTransformBatch(
            (
                _plan("one", source),
                _plan("two", source, image_ref=conflicting_ref),
            ),
            cache_dir=tmp_path / "conflict-cache",
        ).run()
    assert raised.value.code in {"source_ref_conflict", "cache_key_source_ref_conflict"}
    assert calls == 0


@pytest.mark.parametrize(
    ("budget", "code"),
    [
        (ImageTransformBatchBudget(max_total_source_bytes=1), "batch_source_budget_exceeded"),
        (ImageTransformBatchBudget(max_total_decoded_bytes=100), "batch_decoded_budget_exceeded"),
    ],
)
def test_whole_batch_resource_budgets_block_before_transform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    budget: ImageTransformBatchBudget,
    code: str,
) -> None:
    source = _image(tmp_path / f"{code}.png", size=(20, 20))
    calls = 0

    def forbidden_transform(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError

    monkeypatch.setattr(batch_module, "prepare_material_image", forbidden_transform)
    with pytest.raises(ImageTransformBatchError) as raised:
        ImageTransformBatch(
            (_plan("budget", source),),
            cache_dir=tmp_path / "cache",
            budget=budget,
        ).run()
    assert raised.value.code == code
    assert raised.value.job_id == "budget"
    assert raised.value.path == str(source.resolve())
    assert calls == 0


def test_font_hash_and_loadability_are_preflighted_before_transform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _image(tmp_path / "source.png")
    fake_font = tmp_path / "fake.ttf"
    fake_font.write_bytes(b"not-a-font")
    watermark = ResolvedImageWatermark(
        True,
        "profile",
        sha256(b"profile").hexdigest(),
        "fake-font",
        _sha(fake_font),
        "diagonal_tiled_v1",
        "image-transform-v1",
    )
    calls = 0

    def forbidden_transform(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError

    monkeypatch.setattr(batch_module, "prepare_material_image", forbidden_transform)
    with pytest.raises(ImageTransformBatchError) as raised:
        ImageTransformBatch(
            (_plan("font", source, watermark=watermark),),
            cache_dir=tmp_path / "cache",
            font_path_resolver=lambda _plan: fake_font,
        ).run()
    assert raised.value.code == "unreadable_watermark_font"
    assert raised.value.job_id == "font"
    assert raised.value.path == str(fake_font)
    assert calls == 0


def test_cancellation_between_groups_discards_batch_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _image(tmp_path / "first.png", "red")
    second = _image(tmp_path / "second.png", "blue")
    calls = 0

    def counting_transform(*args, **kwargs):
        nonlocal calls
        prepared = prepare_material_image(*args, **kwargs)
        calls += 1
        return prepared

    monkeypatch.setattr(batch_module, "prepare_material_image", counting_transform)
    cache = tmp_path / "cache"
    with pytest.raises(ImageTransformBatchError) as raised:
        ImageTransformBatch(
            (_plan("first", first), _plan("second", second)),
            cache_dir=cache,
        ).run(cancel_check=lambda: calls >= 1)

    assert raised.value.code == "batch_cancelled"
    assert calls == 1
    assert not list(tmp_path.glob(".image-transform-batch-staging-*"))
    assert not list(cache.glob("batches/batch-*"))


def test_group_failure_exposes_no_success_receipt_and_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _image(tmp_path / "first.png", "red")
    second = _image(tmp_path / "second.png", "blue")
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ImageTransformError(
                "forced_group_failure",
                "forced failure",
                path=str(args[0]),
            )
        return prepare_material_image(*args, **kwargs)

    monkeypatch.setattr(batch_module, "prepare_material_image", fail_second)
    cache = tmp_path / "cache"
    with pytest.raises(ImageTransformBatchError) as raised:
        ImageTransformBatch(
            (_plan("first", first), _plan("second", second)), cache_dir=cache
        ).run()

    assert raised.value.code == "forced_group_failure"
    assert raised.value.job_id in {"first", "second"}
    assert raised.value.path
    assert calls == 2
    assert not hasattr(raised.value, "receipt")
    assert not list(tmp_path.glob(".image-transform-batch-staging-*"))
    assert not list(cache.glob("batches/batch-*"))


def test_receipt_identity_is_deterministic_across_miss_and_hit(tmp_path: Path) -> None:
    source = _image(tmp_path / "source.png", "green")
    source_before = source.read_bytes()
    plan = _plan("stable", source)
    cache = tmp_path / "cache"

    first = ImageTransformBatch((plan,), cache_dir=cache).run()
    second = ImageTransformBatch((plan,), cache_dir=cache).run()

    assert first.receipt.jobs[0].cache_hit is False
    assert second.receipt.jobs[0].cache_hit is True
    assert first.receipt.identity_sha256 == second.receipt.identity_sha256
    assert first.receipt.to_identity_dict() == second.receipt.to_identity_dict()
    assert first.receipt.to_json(include_timing=False) == second.receipt.to_json(
        include_timing=False
    )
    assert first.receipt.jobs[0].to_dict()["duration_ms"] >= 0
    assert source.read_bytes() == source_before


def test_batch_cache_manifest_rejects_valid_but_polluted_cached_pixels(
    tmp_path: Path,
) -> None:
    source = _image(tmp_path / "source.png", "white", (80, 60))
    plan = _plan("stable", source)
    cache = tmp_path / "cache"
    first = ImageTransformBatch((plan,), cache_dir=cache).run()
    cached_path = Path(first.prepared_for("stable").output_path)
    Image.new("RGB", (80, 60), "black").save(cached_path, format="PNG")

    rebuilt = ImageTransformBatch((plan,), cache_dir=cache).run()

    assert rebuilt.receipt.jobs[0].cache_hit is False
    assert rebuilt.prepared_for("stable").output_sha256 == (
        first.prepared_for("stable").output_sha256
    )


def test_image_domain_rejects_non_image_filename_even_when_bytes_are_png(
    tmp_path: Path,
) -> None:
    polluted = _image(tmp_path / "polluted.docx")

    with pytest.raises(ImageTransformBatchError) as raised:
        ImageTransformBatch(
            (_plan("polluted", polluted),), cache_dir=tmp_path / "cache"
        ).run()

    assert raised.value.code in {
        "source_extension_mismatch",
        "source_path_extension_mismatch",
    }
    assert not (tmp_path / "cache").exists()


def test_worker_limit_is_explicit_and_finite(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_workers"):
        ImageTransformBatch(
            (),
            cache_dir=tmp_path / "cache",
            max_workers=MAX_IMAGE_TRANSFORM_WORKERS + 1,
        )
