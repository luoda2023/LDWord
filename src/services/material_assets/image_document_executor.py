"""Execute the shared material-image chain against one owned DOCX copy."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from hashlib import sha256
import os
from pathlib import Path
import re
from types import MappingProxyType
from typing import Protocol

from docx import Document

from src.config.image_materials import (
    FrozenImageMaterialRule,
    ImageSourceBinding,
    ResolvedImageInsertionPlan,
)
from src.services.material_assets.image_execution_verifier import (
    ImageExecutionVerificationError,
    verify_image_plan_result,
    verify_image_transform_result,
    verify_office_layout_receipt,
)
from src.services.material_assets.image_plan_builder import (
    ImageInsertionPlanBuilder,
    ImagePlanBuildError,
    ImagePlanBuildResult,
)
from src.services.material_assets.image_transform_batch import (
    ImageTransformBatch,
    ImageTransformBatchError,
    ImageTransformBatchResult,
    MAX_IMAGE_TRANSFORM_WORKERS,
)
from src.shared.engine.office_image_layout_contracts import (
    OfficeImageLayoutReceipt,
    OfficeImageLayoutRequest,
    OfficeImageProvider,
)
from src.shared.engine.office_image_layout_coordinator import (
    build_office_image_layout_request,
    run_office_image_layout,
)
from src.shared.io.layout_shadow import is_controlled_layout_shadow


class _TransformBatchFactory(Protocol):
    def __call__(self, plans, **kwargs) -> object: ...


class ImageDocumentExecutionError(RuntimeError):
    """The owned DOCX did not complete the shared image chain."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        self.code = str(code)
        self.path = str(path)
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ImageDocumentExecutionRequest:
    owned_docx_path: str
    snapshot_id: str
    consumer_id: str
    frozen_rules: tuple[FrozenImageMaterialRule, ...]
    source_bindings: tuple[ImageSourceBinding, ...]
    cache_dir: str
    transaction_id: str
    office_provider: OfficeImageProvider = OfficeImageProvider.WORD
    watermark_font_path: str = ""
    max_transform_workers: int = 1
    layout_options: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "owned_docx_path",
            "snapshot_id",
            "consumer_id",
            "cache_dir",
            "transaction_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not re.fullmatch(r"[0-9a-f]{64}", self.snapshot_id):
            raise ValueError("snapshot_id must be a lowercase SHA-256")
        rules = tuple(self.frozen_rules or ())
        sources = tuple(self.source_bindings or ())
        if any(not isinstance(item, FrozenImageMaterialRule) for item in rules):
            raise TypeError("frozen_rules contains an invalid rule")
        if any(not isinstance(item, ImageSourceBinding) for item in sources):
            raise TypeError("source_bindings contains an invalid source")
        object.__setattr__(self, "frozen_rules", rules)
        object.__setattr__(self, "source_bindings", sources)
        try:
            provider = (
                self.office_provider
                if isinstance(self.office_provider, OfficeImageProvider)
                else OfficeImageProvider(str(self.office_provider))
            )
        except ValueError as exc:
            raise ValueError("unsupported Office image provider") from exc
        object.__setattr__(self, "office_provider", provider)
        if (
            isinstance(self.max_transform_workers, bool)
            or not isinstance(self.max_transform_workers, int)
            or self.max_transform_workers < 1
            or self.max_transform_workers > MAX_IMAGE_TRANSFORM_WORKERS
        ):
            raise ValueError(
                "max_transform_workers must be between 1 and "
                f"{MAX_IMAGE_TRANSFORM_WORKERS}"
            )
        if not isinstance(self.layout_options, Mapping):
            raise TypeError("layout_options must be a mapping")
        options = dict(self.layout_options)
        reserved = {"provider", "transaction_id"} & set(options)
        if reserved:
            raise ValueError(
                "layout_options contains reserved keys: " + ", ".join(sorted(reserved))
            )
        object.__setattr__(self, "layout_options", MappingProxyType(options))


@dataclass(frozen=True, slots=True)
class ImageDocumentExecutionResult:
    plans: tuple[ResolvedImageInsertionPlan, ...]
    plan_result: ImagePlanBuildResult
    transform_result: ImageTransformBatchResult
    layout_request: OfficeImageLayoutRequest | None
    layout_receipt: OfficeImageLayoutReceipt | None
    output_path: str
    output_sha256: str


@dataclass(frozen=True, slots=True)
class ImageDocumentExecutionDependencies:
    document_loader: Callable[[str], object] = Document
    image_plan_builder: ImageInsertionPlanBuilder = field(
        default_factory=ImageInsertionPlanBuilder
    )
    transform_batch_factory: _TransformBatchFactory = ImageTransformBatch
    layout_request_builder: Callable[..., OfficeImageLayoutRequest] = (
        build_office_image_layout_request
    )
    layout_runner: Callable[[OfficeImageLayoutRequest], OfficeImageLayoutReceipt] = (
        run_office_image_layout
    )
    atomic_replace: Callable[[str | Path, str | Path], object] = os.replace

    def __post_init__(self) -> None:
        for name in (
            "document_loader",
            "transform_batch_factory",
            "layout_request_builder",
            "layout_runner",
            "atomic_replace",
        ):
            if not callable(getattr(self, name)):
                raise TypeError(f"{name} must be callable")
        if not hasattr(self.image_plan_builder, "build"):
            raise TypeError("image_plan_builder must provide build()")


class ImageDocumentExecutor:
    """Plan, transform, lay out, and promote one transaction-owned DOCX."""

    def __init__(
        self,
        dependencies: ImageDocumentExecutionDependencies | None = None,
    ) -> None:
        self._deps = dependencies or ImageDocumentExecutionDependencies()

    def execute(
        self,
        request: ImageDocumentExecutionRequest,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ImageDocumentExecutionResult:
        if not isinstance(request, ImageDocumentExecutionRequest):
            raise TypeError("request must be an ImageDocumentExecutionRequest")
        owned = Path(request.owned_docx_path).expanduser().resolve(strict=False)
        if owned.is_symlink() or not owned.is_file():
            raise _error("image_owned_docx_invalid", "owned DOCX is not a regular file", owned)
        _check_cancel(cancel_check)
        try:
            document = self._deps.document_loader(str(owned))
            plan_result = self._deps.image_plan_builder.build(
                document,
                snapshot_id=request.snapshot_id,
                frozen_rules=request.frozen_rules,
                source_bindings=request.source_bindings,
                consumer_id=request.consumer_id,
            )
            verify_image_plan_result(plan_result, request.snapshot_id)
            document.save(str(owned))
        except ImagePlanBuildError as exc:
            details = "; ".join(
                f"{item.code}: {item.message}" for item in exc.diagnostics
            )
            raise _error("image_plan_failed", details or str(exc), owned) from exc
        except ImageExecutionVerificationError as exc:
            raise _error(exc.code, str(exc), owned) from exc
        except ImageDocumentExecutionError:
            raise
        except Exception as exc:
            raise _error(
                "image_plan_failed",
                str(exc) or type(exc).__name__,
                owned,
            ) from exc

        _check_cancel(cancel_check)
        try:
            batch = self._deps.transform_batch_factory(
                plan_result.plans,
                cache_dir=Path(request.cache_dir).expanduser().resolve(),
                font_path_resolver=(
                    (lambda _plan: request.watermark_font_path)
                    if request.watermark_font_path.strip()
                    else None
                ),
                max_workers=request.max_transform_workers,
            )
            transform_result = batch.run(cancel_check=cancel_check)
            verify_image_transform_result(transform_result, plan_result.plans)
        except ImageTransformBatchError as exc:
            raise _error(
                "image_transform_failed",
                f"{exc.code}: {exc}",
                Path(exc.path) if exc.path else owned,
            ) from exc
        except ImageExecutionVerificationError as exc:
            raise _error(exc.code, str(exc), owned) from exc
        except ImageDocumentExecutionError:
            raise
        except Exception as exc:
            raise _error(
                "image_transform_failed",
                str(exc) or type(exc).__name__,
                owned,
            ) from exc

        if not plan_result.plans:
            digest = _stable_file_sha256(owned)
            return ImageDocumentExecutionResult(
                plans=(),
                plan_result=plan_result,
                transform_result=transform_result,
                layout_request=None,
                layout_receipt=None,
                output_path=str(owned),
                output_sha256=digest,
            )

        _check_cancel(cancel_check)
        try:
            layout_request = self._deps.layout_request_builder(
                owned,
                plan_result.plans,
                transform_result.prepared_by_job,
                provider=request.office_provider,
                transaction_id=request.transaction_id,
                **dict(request.layout_options),
            )
            layout_receipt = self._deps.layout_runner(layout_request)
            verify_office_layout_receipt(
                layout_receipt,
                layout_request,
                plan_result.plans,
            )
            shadow = Path(layout_receipt.shadow_path).expanduser().resolve(strict=False)
            if not is_controlled_layout_shadow(owned, shadow):
                raise _error(
                    "image_layout_foreign_shadow",
                    "layout shadow is not owned by this DOCX",
                    shadow,
                )
            if _stable_file_sha256(shadow) != layout_receipt.shadow_sha256:
                raise _error(
                    "office_layout_receipt_invalid",
                    "layout shadow hash differs from its verified receipt",
                    shadow,
                )
            self._deps.atomic_replace(shadow, owned)
            final_sha256 = _stable_file_sha256(owned)
            if final_sha256 != layout_receipt.shadow_sha256:
                raise _error(
                    "image_layout_promotion_failed",
                    "promoted DOCX differs from the verified layout shadow",
                    owned,
                )
        except ImageExecutionVerificationError as exc:
            raise _error(exc.code, str(exc), owned) from exc
        except ImageDocumentExecutionError:
            raise
        except Exception as exc:
            raise _error(
                "image_layout_failed",
                str(exc) or type(exc).__name__,
                owned,
            ) from exc

        return ImageDocumentExecutionResult(
            plans=plan_result.plans,
            plan_result=plan_result,
            transform_result=transform_result,
            layout_request=layout_request,
            layout_receipt=layout_receipt,
            output_path=str(owned),
            output_sha256=final_sha256,
        )


def _check_cancel(cancel_check: Callable[[], bool] | None) -> None:
    if cancel_check is not None and cancel_check():
        raise ImageDocumentExecutionError(
            "image_execution_cancelled",
            "image execution was cancelled",
        )


def _stable_file_sha256(path: str | Path) -> str:
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ValueError(f"symbolic links are not accepted: {candidate}")
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise ValueError(f"not a regular file: {candidate}")
    before = candidate.stat()
    digest = sha256()
    with candidate.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = candidate.stat()
    if (
        before.st_size,
        before.st_mtime_ns,
        getattr(before, "st_ino", 0),
    ) != (
        after.st_size,
        after.st_mtime_ns,
        getattr(after, "st_ino", 0),
    ):
        raise ValueError(f"file changed while hashing: {candidate}")
    return digest.hexdigest()


def _error(code: str, message: str, path: Path) -> ImageDocumentExecutionError:
    return ImageDocumentExecutionError(code, message, path=str(path))


__all__ = [
    "ImageDocumentExecutionDependencies",
    "ImageDocumentExecutionError",
    "ImageDocumentExecutionRequest",
    "ImageDocumentExecutionResult",
    "ImageDocumentExecutor",
]
