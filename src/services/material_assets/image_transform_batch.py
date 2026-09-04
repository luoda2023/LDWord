"""Transactional, job-scoped orchestration for material image transforms."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from shutil import rmtree
from time import perf_counter
from typing import Callable, Mapping, Sequence
from uuid import uuid4
import warnings

from PIL import Image, ImageFont, UnidentifiedImageError

from src.config.image_materials import ResolvedImageInsertionPlan
from src.services.material_assets.image_transformer import (
    ImageTransformLimits,
    build_image_transform_cache_key,
    load_cached_material_image,
    prepare_material_image,
    resolve_watermark_font,
)
from src.shared.engine.prepared_image import PreparedImage


MAX_IMAGE_TRANSFORM_WORKERS = 4
_STAGING_MARKER = ".image-transform-batch-staging-"
_SUPPORTED_SOURCE_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "BMP", "TIFF"})
_SOURCE_FORMAT_CONTRACTS = {
    "JPEG": ("image/jpeg", frozenset({".jpg", ".jpeg"})),
    "PNG": ("image/png", frozenset({".png"})),
    "WEBP": ("image/webp", frozenset({".webp"})),
    "BMP": ("image/bmp", frozenset({".bmp"})),
    "TIFF": ("image/tiff", frozenset({".tif", ".tiff"})),
}

SourcePathResolver = Callable[[ResolvedImageInsertionPlan], str | Path]
FontPathResolver = Callable[[ResolvedImageInsertionPlan], str | Path | None]
CancelCheck = Callable[[], bool]


class ImageTransformBatchError(RuntimeError):
    """One structured all-or-nothing batch failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        job_id: str,
        path: str = "",
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.job_id = str(job_id)
        self.path = str(path)


@dataclass(frozen=True, slots=True)
class ImageTransformBatchBudget:
    """Whole-batch limits plus the transformer's per-image limits."""

    max_total_source_bytes: int = 512 * 1024 * 1024
    max_total_decoded_bytes: int = 1024 * 1024 * 1024
    per_image_limits: ImageTransformLimits = field(default_factory=ImageTransformLimits)

    def __post_init__(self) -> None:
        for name in ("max_total_source_bytes", "max_total_decoded_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.per_image_limits, ImageTransformLimits):
            raise TypeError("per_image_limits must be an ImageTransformLimits")


@dataclass(frozen=True, slots=True)
class ImageTransformJobReceipt:
    job_id: str
    cache_key: str
    cache_hit: bool
    output_sha256: str
    source_sha256: str
    watermark_text_sha256: str
    duration_ms: float

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id is required")
        for name in ("cache_key", "output_sha256", "source_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if self.watermark_text_sha256 and not re.fullmatch(
            r"[0-9a-f]{64}", self.watermark_text_sha256
        ):
            raise ValueError("watermark_text_sha256 must be empty or a SHA-256")
        if self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "cache_key": self.cache_key,
            "cache_hit": self.cache_hit,
            "output_sha256": self.output_sha256,
            "source_sha256": self.source_sha256,
            "watermark_text_sha256": self.watermark_text_sha256,
            "duration_ms": round(self.duration_ms, 3),
        }

    def to_identity_dict(self) -> dict[str, object]:
        """Stable output identity; cache mechanics and timing are evidence only."""

        return {
            "job_id": self.job_id,
            "cache_key": self.cache_key,
            "output_sha256": self.output_sha256,
            "source_sha256": self.source_sha256,
            "watermark_text_sha256": self.watermark_text_sha256,
        }


@dataclass(frozen=True, slots=True)
class ImageTransformBatchReceipt:
    identity_sha256: str
    jobs: tuple[ImageTransformJobReceipt, ...]
    unique_cache_key_count: int
    transformed_group_count: int
    cache_hit_group_count: int

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.identity_sha256):
            raise ValueError("identity_sha256 must be a lowercase SHA-256")
        if len({job.job_id for job in self.jobs}) != len(self.jobs):
            raise ValueError("receipt job ids must be unique")

    def to_identity_dict(self) -> dict[str, object]:
        return {"jobs": [job.to_identity_dict() for job in self.jobs]}

    def to_dict(self) -> dict[str, object]:
        return {
            "identity_sha256": self.identity_sha256,
            "job_count": len(self.jobs),
            "unique_cache_key_count": self.unique_cache_key_count,
            "transformed_group_count": self.transformed_group_count,
            "cache_hit_group_count": self.cache_hit_group_count,
            "jobs": [job.to_dict() for job in self.jobs],
        }

    def to_json(self, *, include_timing: bool = True) -> str:
        payload = self.to_dict() if include_timing else {
            "identity_sha256": self.identity_sha256,
            **self.to_identity_dict(),
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class ImageTransformJobResult:
    job_id: str
    prepared_image: PreparedImage


@dataclass(frozen=True, slots=True)
class ImageTransformBatchResult:
    jobs: tuple[ImageTransformJobResult, ...]
    receipt: ImageTransformBatchReceipt

    def prepared_for(self, job_id: str) -> PreparedImage:
        for item in self.jobs:
            if item.job_id == job_id:
                return item.prepared_image
        raise KeyError(job_id)

    @property
    def prepared_by_job(self) -> Mapping[str, PreparedImage]:
        return {item.job_id: item.prepared_image for item in self.jobs}


@dataclass(frozen=True, slots=True)
class _PreflightJob:
    plan: ResolvedImageInsertionPlan
    source_path: Path
    font_path: Path | None
    cache_key: str
    decoded_bytes: int


@dataclass(frozen=True, slots=True)
class _TransformGroup:
    cache_key: str
    jobs: tuple[_PreflightJob, ...]


@dataclass(frozen=True, slots=True)
class _GroupOutcome:
    group: _TransformGroup
    prepared: PreparedImage
    duration_ms: float
    transformed: bool


class ImageTransformBatch:
    """Preflight and atomically prepare one resolved image-plan batch."""

    def __init__(
        self,
        plans: Sequence[ResolvedImageInsertionPlan],
        *,
        cache_dir: str | Path,
        source_path_resolver: SourcePathResolver | None = None,
        font_path_resolver: FontPathResolver | None = None,
        budget: ImageTransformBatchBudget | None = None,
        max_workers: int = 1,
        jpeg_quality: int = 95,
    ) -> None:
        self._plans = tuple(plans or ())
        if any(not isinstance(plan, ResolvedImageInsertionPlan) for plan in self._plans):
            raise TypeError("plans must contain only ResolvedImageInsertionPlan values")
        self._cache_dir = Path(cache_dir).resolve()
        self._source_path_resolver = source_path_resolver or (
            lambda plan: plan.image_ref.source_path
        )
        self._font_path_resolver = font_path_resolver
        self._budget = budget or ImageTransformBatchBudget()
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")
        if not 1 <= max_workers <= MAX_IMAGE_TRANSFORM_WORKERS:
            raise ValueError(
                f"max_workers must be between 1 and {MAX_IMAGE_TRANSFORM_WORKERS}"
            )
        self._max_workers = max_workers
        if isinstance(jpeg_quality, bool) or not isinstance(jpeg_quality, int):
            raise TypeError("jpeg_quality must be an integer")
        if not 1 <= jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")
        self._jpeg_quality = jpeg_quality

    def run(self, *, cancel_check: CancelCheck | None = None) -> ImageTransformBatchResult:
        """Return a complete result or raise without exposing partial receipts."""

        preflight_jobs = self._preflight()
        groups = _group_jobs(preflight_jobs)
        if not groups:
            receipt = _build_batch_receipt((), (), transformed_keys=frozenset())
            return ImageTransformBatchResult((), receipt)
        self._check_cancel(cancel_check, groups[0].jobs[0].plan.job_id)

        cached_outcomes: dict[str, _GroupOutcome] = {}
        missing_groups: list[_TransformGroup] = []
        for group in groups:
            first = group.jobs[0]
            cached = _find_cached_prepared(
                self._cache_dir,
                group.cache_key,
                first.plan,
                jpeg_quality=self._jpeg_quality,
            )
            if cached is None:
                missing_groups.append(group)
            else:
                cached_outcomes[group.cache_key] = _GroupOutcome(
                    group=group,
                    prepared=cached,
                    duration_ms=0.0,
                    transformed=False,
                )

        staging: Path | None = None
        staging_committed = False
        transformed_outcomes: dict[str, _GroupOutcome] = {}
        try:
            if missing_groups:
                staging = self._create_staging_dir()
                transformed_outcomes = self._transform_groups(
                    tuple(missing_groups),
                    staging=staging,
                    cancel_check=cancel_check,
                )
                final_dir = self._commit_staging(staging)
                staging_committed = True
                transformed_outcomes = {
                    key: replace(
                        outcome,
                        prepared=replace(
                            outcome.prepared,
                            output_path=str(
                                final_dir
                                / Path(outcome.prepared.output_path).relative_to(staging)
                            ),
                        ),
                    )
                    for key, outcome in transformed_outcomes.items()
                }
            all_outcomes = {**cached_outcomes, **transformed_outcomes}
            job_results = tuple(
                ImageTransformJobResult(
                    job_id=job.plan.job_id,
                    prepared_image=all_outcomes[job.cache_key].prepared,
                )
                for job in preflight_jobs
            )
            receipt = _build_batch_receipt(
                preflight_jobs,
                tuple(all_outcomes[key] for key in sorted(all_outcomes)),
                transformed_keys=frozenset(transformed_outcomes),
            )
            return ImageTransformBatchResult(job_results, receipt)
        except ImageTransformBatchError:
            raise
        except Exception as exc:
            representative = missing_groups[0].jobs[0] if missing_groups else preflight_jobs[0]
            raise ImageTransformBatchError(
                "batch_commit_failed",
                str(exc),
                job_id=representative.plan.job_id,
                path=str(staging or self._cache_dir),
            ) from exc
        finally:
            if staging is not None and not staging_committed:
                _cleanup_owned_staging(staging, self._cache_dir.parent)

    def _preflight(self) -> tuple[_PreflightJob, ...]:
        if self._cache_dir.exists() and not self._cache_dir.is_dir():
            raise ImageTransformBatchError(
                "cache_path_not_directory",
                "cache_dir exists but is not a directory",
                job_id=self._plans[0].job_id if self._plans else "batch",
                path=str(self._cache_dir),
            )
        seen_job_ids: set[str] = set()
        refs_by_resolved_path: dict[str, tuple[object, ...]] = {}
        refs_by_cache_key: dict[str, tuple[object, ...]] = {}
        geometry_by_source: dict[tuple[str, tuple[object, ...]], tuple[int, int]] = {}
        source_bytes_by_sha: dict[str, int] = {}
        jobs: list[_PreflightJob] = []
        for plan in self._plans:
            if plan.job_id in seen_job_ids:
                raise ImageTransformBatchError(
                    "duplicate_job_id",
                    f"duplicate image transform job id: {plan.job_id}",
                    job_id=plan.job_id,
                )
            seen_job_ids.add(plan.job_id)
            source = self._resolve_source(plan)
            source_identity = _source_ref_identity(plan)
            path_key = os.path.normcase(str(source.resolve()))
            previous_path_ref = refs_by_resolved_path.get(path_key)
            if previous_path_ref is not None and previous_path_ref != source_identity:
                raise ImageTransformBatchError(
                    "source_ref_conflict",
                    "one resolved source path has conflicting frozen references",
                    job_id=plan.job_id,
                    path=str(source),
                )
            refs_by_resolved_path[path_key] = source_identity
            geometry_key = (path_key, source_identity)
            geometry = geometry_by_source.get(geometry_key)
            if geometry is None:
                geometry = self._validate_source(plan, source)
                geometry_by_source[geometry_key] = geometry
            width, height = geometry
            decoded_bytes = width * height * 4
            self._validate_watermark(plan)
            cache_key = self._build_cache_key(plan)
            previous_group_ref = refs_by_cache_key.get(cache_key)
            if previous_group_ref is not None and previous_group_ref != source_identity:
                raise ImageTransformBatchError(
                    "cache_key_source_ref_conflict",
                    "jobs sharing a transform key must share one frozen source reference",
                    job_id=plan.job_id,
                    path=str(source),
                )
            refs_by_cache_key[cache_key] = source_identity
            font_path = self._resolve_font(plan)
            source_bytes_by_sha.setdefault(
                plan.image_ref.content_sha256, plan.image_ref.byte_size
            )
            jobs.append(
                _PreflightJob(
                    plan=plan,
                    source_path=source,
                    font_path=font_path,
                    cache_key=cache_key,
                    decoded_bytes=decoded_bytes,
                )
            )

        total_source_bytes = sum(source_bytes_by_sha.values())
        if total_source_bytes > self._budget.max_total_source_bytes:
            job = jobs[-1] if jobs else None
            raise ImageTransformBatchError(
                "batch_source_budget_exceeded",
                f"batch source bytes {total_source_bytes} exceed "
                f"{self._budget.max_total_source_bytes}",
                job_id=job.plan.job_id if job else "batch",
                path=str(job.source_path) if job else "",
            )
        decoded_by_key: dict[str, int] = {}
        job_by_key: dict[str, _PreflightJob] = {}
        for job in jobs:
            decoded_by_key.setdefault(job.cache_key, job.decoded_bytes)
            job_by_key.setdefault(job.cache_key, job)
        total_decoded_bytes = sum(decoded_by_key.values())
        if total_decoded_bytes > self._budget.max_total_decoded_bytes:
            trigger = job_by_key[sorted(job_by_key)[-1]] if job_by_key else None
            raise ImageTransformBatchError(
                "batch_decoded_budget_exceeded",
                f"estimated decoded bytes {total_decoded_bytes} exceed "
                f"{self._budget.max_total_decoded_bytes}",
                job_id=trigger.plan.job_id if trigger else "batch",
                path=str(trigger.source_path) if trigger else "",
            )
        return tuple(jobs)

    def _resolve_source(self, plan: ResolvedImageInsertionPlan) -> Path:
        try:
            raw = self._source_path_resolver(plan)
        except Exception as exc:
            raise ImageTransformBatchError(
                "source_path_resolution_failed",
                str(exc),
                job_id=plan.job_id,
                path=plan.image_ref.source_path,
            ) from exc
        path = Path(str(raw or ""))
        if not path.is_file():
            raise ImageTransformBatchError(
                "source_missing",
                "image source does not exist",
                job_id=plan.job_id,
                path=str(path),
            )
        return path.resolve()

    def _validate_source(
        self, plan: ResolvedImageInsertionPlan, source: Path
    ) -> tuple[int, int]:
        stat = source.stat()
        limits = self._budget.per_image_limits
        if stat.st_size > limits.max_source_bytes:
            self._fail(plan, "source_size_limit_exceeded", source)
        if stat.st_size != plan.image_ref.byte_size:
            self._fail(plan, "source_size_mismatch", source)
        if _sha256_file(source) != plan.image_ref.content_sha256:
            self._fail(plan, "source_hash_mismatch", source)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(source) as image:
                    image_format = str(image.format or "").upper()
                    width, height = image.size
                    if image_format not in _SUPPORTED_SOURCE_FORMATS:
                        self._fail(plan, "unsupported_image_format", source)
                    image.verify()
        except ImageTransformBatchError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ImageTransformBatchError(
                "decompression_bomb",
                "image dimensions exceed Pillow's safety threshold",
                job_id=plan.job_id,
                path=str(source),
            ) from exc
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            raise ImageTransformBatchError(
                "unreadable_image",
                "image bytes cannot be decoded during batch preflight",
                job_id=plan.job_id,
                path=str(source),
            ) from exc
        pixels = int(width) * int(height)
        if pixels <= 0:
            self._fail(plan, "invalid_dimensions", source)
        if pixels > limits.max_pixels:
            self._fail(plan, "pixel_limit_exceeded", source)
        decoded_bytes = pixels * 4
        if decoded_bytes > limits.max_decoded_bytes:
            self._fail(plan, "decoded_memory_limit_exceeded", source)
        if decoded_bytes * 4 > limits.max_working_bytes:
            self._fail(plan, "working_memory_limit_exceeded", source)
        media_type, extensions = _SOURCE_FORMAT_CONTRACTS[image_format]
        if plan.image_ref.media_type.casefold() != media_type:
            self._fail(plan, "source_media_type_mismatch", source)
        if Path(plan.image_ref.original_name).suffix.casefold() not in extensions:
            self._fail(plan, "source_extension_mismatch", source)
        if source.suffix.casefold() not in extensions:
            self._fail(plan, "source_path_extension_mismatch", source)
        return width, height

    @staticmethod
    def _validate_watermark(plan: ResolvedImageInsertionPlan) -> None:
        watermark = plan.watermark
        if watermark.transform_contract != "image-transform-v1":
            raise ImageTransformBatchError(
                "transform_contract_mismatch",
                "resolved watermark uses a different transform contract",
                job_id=plan.job_id,
                path=plan.image_ref.source_path,
            )
        if watermark.style_version != "diagonal_tiled_v1":
            raise ImageTransformBatchError(
                "unsupported_watermark_style",
                "resolved watermark style is unsupported",
                job_id=plan.job_id,
                path=plan.image_ref.source_path,
            )
        if watermark.enabled and sha256(
            watermark.resolved_text.encode("utf-8")
        ).hexdigest() != watermark.resolved_text_sha256:
            raise ImageTransformBatchError(
                "watermark_text_hash_mismatch",
                "resolved watermark text differs from its frozen hash",
                job_id=plan.job_id,
                path=plan.image_ref.source_path,
            )
        if watermark.enabled and (
            len(watermark.resolved_text) > 512
            or len(watermark.resolved_text.encode("utf-8")) > 4096
        ):
            raise ImageTransformBatchError(
                "watermark_text_too_long",
                "resolved watermark text exceeds the supported first-version limit",
                job_id=plan.job_id,
                path=plan.image_ref.source_path,
            )

    def _build_cache_key(self, plan: ResolvedImageInsertionPlan) -> str:
        try:
            return build_image_transform_cache_key(
                plan.image_ref,
                plan.watermark,
                jpeg_quality=self._jpeg_quality,
            )
        except Exception as exc:
            code = getattr(exc, "code", "cache_key_invalid")
            raise ImageTransformBatchError(
                code,
                str(exc),
                job_id=plan.job_id,
                path=plan.image_ref.source_path,
            ) from exc

    def _resolve_font(self, plan: ResolvedImageInsertionPlan) -> Path | None:
        watermark = plan.watermark
        if not watermark.enabled:
            return None
        try:
            raw = (
                self._font_path_resolver(plan)
                if self._font_path_resolver is not None
                else resolve_watermark_font(watermark.resolved_text).path
            )
        except Exception as exc:
            raise ImageTransformBatchError(
                getattr(exc, "code", "watermark_font_resolution_failed"),
                str(exc),
                job_id=plan.job_id,
                path=getattr(exc, "path", ""),
            ) from exc
        font = Path(str(raw or ""))
        if not font.is_file() or font.suffix.casefold() not in {".ttf", ".otf", ".ttc"}:
            raise ImageTransformBatchError(
                "watermark_font_missing",
                "resolved watermark font is unavailable",
                job_id=plan.job_id,
                path=str(font),
            )
        if _sha256_file(font) != watermark.resolved_font_sha256:
            raise ImageTransformBatchError(
                "watermark_font_hash_mismatch",
                "resolved font bytes differ from the frozen watermark hash",
                job_id=plan.job_id,
                path=str(font),
            )
        try:
            ImageFont.truetype(str(font), 16)
        except OSError as exc:
            raise ImageTransformBatchError(
                "unreadable_watermark_font",
                "resolved watermark font cannot be loaded",
                job_id=plan.job_id,
                path=str(font),
            ) from exc
        return font.resolve()

    def _transform_groups(
        self,
        groups: tuple[_TransformGroup, ...],
        *,
        staging: Path,
        cancel_check: CancelCheck | None,
    ) -> dict[str, _GroupOutcome]:
        outcomes: dict[str, _GroupOutcome] = {}
        for start in range(0, len(groups), self._max_workers):
            chunk = groups[start : start + self._max_workers]
            self._check_cancel(cancel_check, chunk[0].jobs[0].plan.job_id)
            if len(chunk) == 1:
                outcome = self._transform_group(chunk[0], staging)
                outcomes[outcome.group.cache_key] = outcome
                continue
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                futures = {
                    group.cache_key: executor.submit(self._transform_group, group, staging)
                    for group in chunk
                }
                for group in chunk:
                    try:
                        outcome = futures[group.cache_key].result()
                    except ImageTransformBatchError:
                        raise
                    outcomes[outcome.group.cache_key] = outcome
        return outcomes

    def _transform_group(self, group: _TransformGroup, staging: Path) -> _GroupOutcome:
        job = group.jobs[0]
        started = perf_counter()
        try:
            prepared = prepare_material_image(
                job.source_path,
                job.plan.image_ref,
                job.plan.watermark,
                cache_dir=staging,
                font_path=job.font_path,
                limits=self._budget.per_image_limits,
                jpeg_quality=self._jpeg_quality,
            )
        except Exception as exc:
            raise ImageTransformBatchError(
                getattr(exc, "code", "image_transform_failed"),
                str(exc),
                job_id=job.plan.job_id,
                path=str(getattr(exc, "path", "") or job.source_path),
            ) from exc
        if prepared.cache_key != group.cache_key:
            raise ImageTransformBatchError(
                "transform_cache_key_mismatch",
                "transformer returned an unexpected cache key",
                job_id=job.plan.job_id,
                path=prepared.output_path,
            )
        return _GroupOutcome(
            group=group,
            prepared=prepared,
            duration_ms=(perf_counter() - started) * 1000.0,
            transformed=True,
        )

    def _create_staging_dir(self) -> Path:
        parent = self._cache_dir.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            staging = parent / f"{_STAGING_MARKER}{uuid4().hex}"
            staging.mkdir()
            return staging
        except OSError as exc:
            raise ImageTransformBatchError(
                "batch_staging_create_failed",
                str(exc),
                job_id=self._plans[0].job_id if self._plans else "batch",
                path=str(parent),
            ) from exc

    def _commit_staging(self, staging: Path) -> Path:
        batch_root = self._cache_dir / "batches"
        final_dir = batch_root / f"batch-{uuid4().hex}"
        try:
            batch_root.mkdir(parents=True, exist_ok=True)
            os.replace(staging, final_dir)
        except OSError as exc:
            raise ImageTransformBatchError(
                "batch_commit_failed",
                str(exc),
                job_id=self._plans[0].job_id if self._plans else "batch",
                path=str(final_dir),
            ) from exc
        return final_dir

    def _check_cancel(self, check: CancelCheck | None, job_id: str) -> None:
        if check is None:
            return
        try:
            cancelled = bool(check())
        except Exception as exc:
            raise ImageTransformBatchError(
                "cancel_check_failed", str(exc), job_id=job_id
            ) from exc
        if cancelled:
            raise ImageTransformBatchError(
                "batch_cancelled", "image transform batch was cancelled", job_id=job_id
            )

    @staticmethod
    def _fail(plan: ResolvedImageInsertionPlan, code: str, path: Path) -> None:
        raise ImageTransformBatchError(
            code,
            code.replace("_", " "),
            job_id=plan.job_id,
            path=str(path),
        )


def _group_jobs(jobs: Sequence[_PreflightJob]) -> tuple[_TransformGroup, ...]:
    grouped: dict[str, list[_PreflightJob]] = {}
    for job in jobs:
        grouped.setdefault(job.cache_key, []).append(job)
    return tuple(
        _TransformGroup(cache_key, tuple(grouped[cache_key]))
        for cache_key in sorted(grouped)
    )


def _source_ref_identity(plan: ResolvedImageInsertionPlan) -> tuple[object, ...]:
    ref = plan.image_ref
    return (
        ref.source_path,
        ref.original_name,
        ref.media_type.casefold(),
        ref.content_sha256,
        ref.byte_size,
    )


def _find_cached_prepared(
    cache_dir: Path,
    cache_key: str,
    plan: ResolvedImageInsertionPlan,
    *,
    jpeg_quality: int,
) -> PreparedImage | None:
    directories = [cache_dir]
    batch_root = cache_dir / "batches"
    if batch_root.is_dir():
        directories.extend(
            sorted(
                (path for path in batch_root.glob("batch-*") if path.is_dir()),
                key=lambda item: item.as_posix(),
            )
        )
    for directory in directories:
        prepared = load_cached_material_image(
            directory,
            plan.image_ref,
            plan.watermark,
            jpeg_quality=jpeg_quality,
        )
        if prepared is not None and prepared.cache_key == cache_key:
            return prepared
    return None


def _build_batch_receipt(
    jobs: Sequence[_PreflightJob],
    outcomes: Sequence[_GroupOutcome],
    *,
    transformed_keys: frozenset[str],
) -> ImageTransformBatchReceipt:
    by_key = {outcome.group.cache_key: outcome for outcome in outcomes}
    job_receipts = tuple(
        ImageTransformJobReceipt(
            job_id=job.plan.job_id,
            cache_key=job.cache_key,
            cache_hit=by_key[job.cache_key].prepared.cache_hit,
            output_sha256=by_key[job.cache_key].prepared.output_sha256,
            source_sha256=by_key[job.cache_key].prepared.source_sha256,
            watermark_text_sha256=by_key[
                job.cache_key
            ].prepared.watermark_text_sha256,
            duration_ms=by_key[job.cache_key].duration_ms,
        )
        for job in jobs
    )
    identity_payload = {"jobs": [job.to_identity_dict() for job in job_receipts]}
    identity_json = json.dumps(
        identity_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ImageTransformBatchReceipt(
        identity_sha256=sha256(identity_json).hexdigest(),
        jobs=job_receipts,
        unique_cache_key_count=len(by_key),
        transformed_group_count=len(transformed_keys),
        cache_hit_group_count=sum(
            1 for outcome in outcomes if outcome.prepared.cache_hit
        ),
    )


def _cleanup_owned_staging(path: Path, expected_parent: Path) -> None:
    try:
        resolved = path.resolve()
        parent = expected_parent.resolve()
    except OSError:
        return
    if resolved.parent != parent or not resolved.name.startswith(_STAGING_MARKER):
        return
    if resolved.is_dir():
        rmtree(resolved, ignore_errors=True)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "MAX_IMAGE_TRANSFORM_WORKERS",
    "ImageTransformBatch",
    "ImageTransformBatchBudget",
    "ImageTransformBatchError",
    "ImageTransformBatchReceipt",
    "ImageTransformBatchResult",
    "ImageTransformJobReceipt",
    "ImageTransformJobResult",
]
