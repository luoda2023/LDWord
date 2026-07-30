"""Strong public contracts for the material assembly transaction.

The UI and the formatting pipeline are deliberately absent from this module.
Callers provide one immutable request and one pipeline callback; the assembly
service owns all intermediate paths and returns content-addressed evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Protocol

from src.config.content_materials import ContentResourceKey
from src.config.entity import EntityProfile
from src.config.image_materials import (
    DeliveryVariantPlan,
    ImageMaterialRule,
    ImageSourceItem,
)
from src.config.material_snapshot import MaterialSnapshot
from src.services.material_assets.image_plan_builder import (
    ContentResourceImageSource,
    ImagePlanReceipt,
)
from src.services.material_assets.image_transform_batch import (
    ImageTransformBatchReceipt,
)
from src.services.material_content.composer import ComposeReceipt
from src.shared.engine.office_image_layout_contracts import (
    OfficeImageLayoutReceipt,
    OfficeImageProvider,
)
from src.shared.engine.material_dependency_index import MaterialDependencyIndex
from src.shared.io.file_evidence import FileEvidence


MATERIAL_ASSEMBLY_CONTRACT_VERSION = "material-assembly-v2"
INTAKE_VARIANT_ID = "intake"
INTAKE_VARIANT_VERSION = "intake-v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_LAYOUT_OPTION_KEYS = frozenset(
    {
        "timeout_seconds",
        "max_stabilization_rounds",
        "safety_margin_pt",
        "readability_min_dimension_pt",
        "correction_shrink_factor",
    }
)


class AssemblyStage(str, Enum):
    PREFLIGHT = "preflight"
    INTAKE_FREEZE = "intake_freeze"
    DEPENDENCY_INDEX = "dependency_index"
    CONTENT_COMPOSE = "content_compose"
    PIPELINE = "pipeline"
    IMAGE_PLAN = "image_plan"
    DELIVERY_PLAN = "delivery_plan"
    IMAGE_TRANSFORM = "image_transform"
    OFFICE_LAYOUT = "office_layout"
    VERIFY = "verify"
    PUBLISH = "publish"
    ROLLBACK = "rollback"
    CANCEL = "cancel"


class AssemblyFailureCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SOURCE_MISSING = "source_missing"
    SOURCE_DRIFT = "source_drift"
    INTAKE_FREEZE_FAILED = "intake_freeze_failed"
    INTAKE_FREEZE_INVALID = "intake_freeze_invalid"
    DEPENDENCY_INDEX_FAILED = "dependency_index_failed"
    DEPENDENCY_INDEX_INVALID = "dependency_index_invalid"
    CONTENT_COMPOSE_FAILED = "content_compose_failed"
    CONTENT_RECEIPT_INVALID = "content_receipt_invalid"
    CONTENT_RESOURCE_HANDOFF_INVALID = "content_resource_handoff_invalid"
    PIPELINE_CALLBACK_FAILED = "pipeline_callback_failed"
    PIPELINE_CONTRACT_VIOLATION = "pipeline_contract_violation"
    PIPELINE_OUTPUT_INVALID = "pipeline_output_invalid"
    IMAGE_PLAN_FAILED = "image_plan_failed"
    IMAGE_PLAN_RECEIPT_INVALID = "image_plan_receipt_invalid"
    DELIVERY_PLAN_INVALID = "delivery_plan_invalid"
    IMAGE_TRANSFORM_FAILED = "image_transform_failed"
    IMAGE_TRANSFORM_RECEIPT_INVALID = "image_transform_receipt_invalid"
    OFFICE_LAYOUT_FAILED = "office_layout_failed"
    OFFICE_LAYOUT_RECEIPT_INVALID = "office_layout_receipt_invalid"
    FOREIGN_SHADOW = "foreign_shadow"
    FINAL_DRIFT = "final_drift"
    FINAL_VERIFY_FAILED = "final_verify_failed"
    ATOMIC_PUBLISH_FAILED = "atomic_publish_failed"
    ROLLBACK_FAILED = "rollback_failed"
    CANCELLED = "cancelled"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True, slots=True)
class AssemblyDiagnostic:
    code: AssemblyFailureCode
    stage: AssemblyStage
    message: str
    variant_id: str = ""
    path: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.code, AssemblyFailureCode):
            object.__setattr__(self, "code", AssemblyFailureCode(str(self.code)))
        if not isinstance(self.stage, AssemblyStage):
            object.__setattr__(self, "stage", AssemblyStage(str(self.stage)))
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("diagnostic message must not be empty")
        if not isinstance(self.variant_id, str) or not isinstance(self.path, str):
            raise TypeError("diagnostic variant_id/path must be strings")

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code.value,
            "stage": self.stage.value,
            "message": self.message,
            "variant_id": self.variant_id,
            "path": self.path,
        }


class MaterialAssemblyError(RuntimeError):
    """Structured failure; no successful receipt coexists with this value."""

    def __init__(self, diagnostics: Sequence[AssemblyDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics or ())
        if not self.diagnostics:
            raise ValueError("MaterialAssemblyError requires diagnostics")
        if any(not isinstance(item, AssemblyDiagnostic) for item in self.diagnostics):
            raise TypeError("diagnostics must contain AssemblyDiagnostic values")
        detail = "; ".join(
            f"{item.stage.value}:{item.code.value}: {item.message}"
            for item in self.diagnostics
        )
        super().__init__(f"material assembly failed: {detail}")

    @property
    def primary(self) -> AssemblyDiagnostic:
        return self.diagnostics[0]

    def to_dict(self) -> dict[str, object]:
        return {
            "error": "material_assembly_failed",
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


class MaterialAssemblyCancelled(MaterialAssemblyError):
    """Cancellation is a rollback-producing structured outcome."""

    def __init__(self, stage: AssemblyStage, *, variant_id: str = "") -> None:
        super().__init__(
            (
                AssemblyDiagnostic(
                    AssemblyFailureCode.CANCELLED,
                    AssemblyStage.CANCEL,
                    f"material assembly was cancelled during {stage.value}",
                    variant_id=variant_id,
                ),
            )
        )


@dataclass(frozen=True, slots=True)
class MaterialVariantRequest:
    variant_id: str
    variant_version: str
    final_output_path: str
    rule_versions: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.variant_id, "variant_id")
        _require_text(self.variant_version, "variant_version")
        _require_text(self.final_output_path, "final_output_path")
        object.__setattr__(
            self,
            "rule_versions",
            _freeze_text_mapping(self.rule_versions, "rule_versions"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "variant_id": self.variant_id,
            "variant_version": self.variant_version,
            "final_output_path": self.final_output_path,
            "rule_versions": dict(self.rule_versions),
        }


@dataclass(frozen=True, slots=True)
class MaterialAssemblyRequest:
    source_docx_path: str
    profile: EntityProfile
    frozen_field_values: Mapping[str, object]
    material_schema_id: str
    material_schema_version: str
    variants: tuple[MaterialVariantRequest, ...]
    office_provider: OfficeImageProvider
    rule_versions: Mapping[str, str] = field(default_factory=dict)
    image_rules: tuple[ImageMaterialRule, ...] = ()
    image_source_items: tuple[ImageSourceItem, ...] = ()
    content_resource_sources: Mapping[
        ContentResourceKey, ContentResourceImageSource
    ] = field(default_factory=dict)
    watermark_font_path: str = ""
    watermark_font_identity: str = ""
    runtime_image_watermark_text: str = ""
    image_cache_dir: str = ""
    work_root: str = ""
    source_root: str = ""
    layout_options: Mapping[str, object] = field(default_factory=dict)
    max_image_transform_workers: int = 1

    def __post_init__(self) -> None:
        _require_text(self.source_docx_path, "source_docx_path")
        if not isinstance(self.profile, EntityProfile):
            raise TypeError("profile must be an EntityProfile")
        if not isinstance(self.frozen_field_values, Mapping):
            raise TypeError("frozen_field_values must be a mapping")
        _require_text(self.material_schema_id, "material_schema_id")
        _require_text(self.material_schema_version, "material_schema_version")
        variants = tuple(self.variants or ())
        if not variants or any(
            not isinstance(item, MaterialVariantRequest) for item in variants
        ):
            raise ValueError("variants must contain at least one MaterialVariantRequest")
        if len({item.variant_id for item in variants}) != len(variants):
            raise ValueError("variant_id values must be unique")
        object.__setattr__(self, "variants", variants)
        provider = (
            self.office_provider
            if isinstance(self.office_provider, OfficeImageProvider)
            else OfficeImageProvider(str(self.office_provider))
        )
        object.__setattr__(self, "office_provider", provider)
        object.__setattr__(
            self,
            "rule_versions",
            _freeze_text_mapping(self.rule_versions, "rule_versions"),
        )
        rules = tuple(self.image_rules or ())
        if any(not isinstance(item, ImageMaterialRule) for item in rules):
            raise TypeError("image_rules must contain ImageMaterialRule values")
        if len({item.rule_id for item in rules}) != len(rules):
            raise ValueError("image rule ids must be unique")
        object.__setattr__(self, "image_rules", rules)
        source_items = tuple(self.image_source_items or ())
        if any(not isinstance(item, ImageSourceItem) for item in source_items):
            raise TypeError("image_source_items must contain ImageSourceItem values")
        object.__setattr__(self, "image_source_items", source_items)

        resource_sources = dict(self.content_resource_sources or {})
        if any(not isinstance(key, ContentResourceKey) for key in resource_sources):
            raise TypeError("content_resource_sources keys must be ContentResourceKey")
        if any(
            not isinstance(value, ContentResourceImageSource)
            for value in resource_sources.values()
        ):
            raise TypeError(
                "content_resource_sources values must be ContentResourceImageSource"
            )
        object.__setattr__(
            self,
            "content_resource_sources",
            MappingProxyType(dict(sorted(resource_sources.items()))),
        )
        for name in (
            "watermark_font_path",
            "watermark_font_identity",
            "runtime_image_watermark_text",
            "image_cache_dir",
            "work_root",
            "source_root",
        ):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} must be a string")
        if (
            isinstance(self.max_image_transform_workers, bool)
            or not isinstance(self.max_image_transform_workers, int)
            or not 1 <= self.max_image_transform_workers <= 4
        ):
            raise ValueError("max_image_transform_workers must be between 1 and 4")
        options = dict(self.layout_options or {})
        unexpected = sorted(set(options) - _LAYOUT_OPTION_KEYS)
        if unexpected:
            raise ValueError(
                "unsupported layout options: " + ", ".join(unexpected)
            )
        object.__setattr__(
            self,
            "layout_options",
            MappingProxyType(_freeze_plain_mapping(options, "layout_options")),
        )


@dataclass(frozen=True, slots=True)
class PipelineVariantTarget:
    variant_id: str
    variant_version: str
    final_output_path: str
    owned_stage_output_path: str

    def __post_init__(self) -> None:
        _require_text(self.variant_id, "variant_id")
        _require_text(self.variant_version, "variant_version")
        for name in ("final_output_path", "owned_stage_output_path"):
            _require_text(getattr(self, name), name)
        final = Path(self.final_output_path).resolve()
        stage = Path(self.owned_stage_output_path).resolve()
        if final == stage:
            raise ValueError("owned stage output cannot be the final output")
        if final.parent != stage.parent:
            raise ValueError("owned stage output must share the final directory")

    def to_dict(self) -> dict[str, str]:
        return {
            "variant_id": self.variant_id,
            "variant_version": self.variant_version,
            "final_output_path": self.final_output_path,
            "owned_stage_output_path": self.owned_stage_output_path,
        }


@dataclass(frozen=True, slots=True)
class MaterialPipelineRequest:
    execution_id: str
    logical_source_path: str
    prepared_input: FileEvidence
    intake_snapshot_id: str
    targets: tuple[PipelineVariantTarget, ...]

    def __post_init__(self) -> None:
        _require_text(self.execution_id, "execution_id")
        _require_text(self.logical_source_path, "logical_source_path")
        if not isinstance(self.prepared_input, FileEvidence):
            raise TypeError("prepared_input must be FileEvidence")
        _require_sha256(self.intake_snapshot_id, "intake_snapshot_id")
        targets = tuple(self.targets or ())
        if not targets or any(
            not isinstance(item, PipelineVariantTarget) for item in targets
        ):
            raise ValueError("targets must contain at least one PipelineVariantTarget")
        if len({item.variant_id for item in targets}) != len(targets):
            raise ValueError("pipeline target variant ids must be unique")
        object.__setattr__(self, "targets", targets)

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id,
            "logical_source_path": self.logical_source_path,
            "prepared_input": self.prepared_input.to_dict(),
            "intake_snapshot_id": self.intake_snapshot_id,
            "targets": [item.to_dict() for item in self.targets],
        }


CancelCheck = Callable[[], bool]


class MaterialPipelineCallback(Protocol):
    def __call__(
        self,
        request: MaterialPipelineRequest,
        *,
        cancel_check: CancelCheck | None = None,
    ) -> "MaterialPipelineOutcome": ...


class VisibilityEvidenceKind(str, Enum):
    RECEIPT = "receipt"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class PipelineVisibilityEvidence:
    """Variant-owned proof for filtering deferred content image jobs."""

    variant_id: str
    kind: VisibilityEvidenceKind
    visibility_receipt_id: str = ""
    removed_content_image_markers: tuple[str, ...] = ()
    not_applicable_reason: str = ""

    def __post_init__(self) -> None:
        _require_text(self.variant_id, "variant_id")
        kind = (
            self.kind
            if isinstance(self.kind, VisibilityEvidenceKind)
            else VisibilityEvidenceKind(str(self.kind))
        )
        object.__setattr__(self, "kind", kind)
        markers = tuple(str(item or "").strip() for item in self.removed_content_image_markers)
        if any(not item for item in markers) or len(set(markers)) != len(markers):
            raise ValueError(
                "removed_content_image_markers must be unique non-empty strings"
            )
        object.__setattr__(self, "removed_content_image_markers", markers)
        if kind is VisibilityEvidenceKind.RECEIPT:
            _require_sha256(self.visibility_receipt_id, "visibility_receipt_id")
            if self.not_applicable_reason:
                raise ValueError("receipt evidence cannot retain not_applicable_reason")
        else:
            if self.visibility_receipt_id or markers:
                raise ValueError(
                    "not-applicable visibility evidence cannot remove content markers"
                )
            _require_text(self.not_applicable_reason, "not_applicable_reason")

    def to_dict(self) -> dict[str, object]:
        return {
            "variant_id": self.variant_id,
            "kind": self.kind.value,
            "visibility_receipt_id": self.visibility_receipt_id,
            "removed_content_image_markers": list(
                self.removed_content_image_markers
            ),
            "not_applicable_reason": self.not_applicable_reason,
        }


@dataclass(frozen=True, slots=True)
class MaterialPipelineOutcome:
    visibility_evidence: tuple[PipelineVisibilityEvidence, ...]

    def __post_init__(self) -> None:
        items = tuple(self.visibility_evidence or ())
        if not items or any(
            not isinstance(item, PipelineVisibilityEvidence) for item in items
        ):
            raise ValueError(
                "visibility_evidence must contain PipelineVisibilityEvidence values"
            )
        if len({item.variant_id for item in items}) != len(items):
            raise ValueError("visibility evidence variant ids must be unique")
        object.__setattr__(self, "visibility_evidence", items)

    def to_dict(self) -> dict[str, object]:
        return {
            "visibility_evidence": [item.to_dict() for item in self.visibility_evidence]
        }


@dataclass(frozen=True, slots=True)
class PipelineRunReceipt:
    prepared_input_before: FileEvidence
    prepared_input_after: FileEvidence
    outputs: tuple[FileEvidence, ...]
    variant_ids: tuple[str, ...]
    visibility_evidence: tuple[PipelineVisibilityEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.prepared_input_before, FileEvidence) or not isinstance(
            self.prepared_input_after, FileEvidence
        ):
            raise TypeError("pipeline prepared input evidence is invalid")
        outputs = tuple(self.outputs or ())
        if any(not isinstance(item, FileEvidence) for item in outputs):
            raise TypeError("pipeline outputs must contain FileEvidence values")
        variant_ids = tuple(self.variant_ids or ())
        if len(outputs) != len(variant_ids) or len(set(variant_ids)) != len(variant_ids):
            raise ValueError("pipeline output evidence must map one-to-one to variants")
        visibility = tuple(self.visibility_evidence or ())
        if any(not isinstance(item, PipelineVisibilityEvidence) for item in visibility):
            raise TypeError("visibility_evidence contains an invalid value")
        if {item.variant_id for item in visibility} != set(variant_ids):
            raise ValueError("visibility evidence must cover every pipeline variant")
        object.__setattr__(self, "outputs", outputs)
        object.__setattr__(self, "variant_ids", variant_ids)
        object.__setattr__(self, "visibility_evidence", visibility)

    def to_dict(self) -> dict[str, object]:
        return {
            "prepared_input_before": self.prepared_input_before.to_dict(),
            "prepared_input_after": self.prepared_input_after.to_dict(),
            "outputs": [
                {"variant_id": variant_id, **evidence.to_dict()}
                for variant_id, evidence in zip(
                    self.variant_ids, self.outputs, strict=True
                )
            ],
            "visibility_evidence": [
                item.to_dict() for item in self.visibility_evidence
            ],
        }


@dataclass(frozen=True, slots=True)
class VariantAssemblyReceipt:
    variant: MaterialVariantRequest
    delivery_plan: DeliveryVariantPlan
    pipeline_output: FileEvidence
    visibility_evidence: PipelineVisibilityEvidence
    not_applicable_content_image_job_ids: tuple[str, ...]
    not_applicable_content_image_markers: tuple[str, ...]
    image_plan_receipt: ImagePlanReceipt
    image_transform_receipt: ImageTransformBatchReceipt
    office_layout_receipt: OfficeImageLayoutReceipt | None
    publish_candidate: FileEvidence
    final_output: FileEvidence

    def __post_init__(self) -> None:
        if not isinstance(self.variant, MaterialVariantRequest):
            raise TypeError("variant must be a MaterialVariantRequest")
        if not isinstance(self.delivery_plan, DeliveryVariantPlan):
            raise TypeError("delivery_plan must be DeliveryVariantPlan")
        if not isinstance(self.pipeline_output, FileEvidence):
            raise TypeError("pipeline_output must be FileEvidence")
        if not isinstance(self.visibility_evidence, PipelineVisibilityEvidence):
            raise TypeError("visibility_evidence must be PipelineVisibilityEvidence")
        job_ids = tuple(self.not_applicable_content_image_job_ids or ())
        markers = tuple(self.not_applicable_content_image_markers or ())
        if any(not isinstance(item, str) or not item for item in (*job_ids, *markers)):
            raise ValueError("not-applicable content image evidence cannot be empty")
        if len(set(job_ids)) != len(job_ids) or len(set(markers)) != len(markers):
            raise ValueError("not-applicable content image evidence must be unique")
        if len(job_ids) != len(markers):
            raise ValueError("not-applicable content jobs and markers must pair one-to-one")
        if markers != self.visibility_evidence.removed_content_image_markers:
            raise ValueError(
                "not-applicable markers must equal the visibility ownership evidence"
            )
        object.__setattr__(self, "not_applicable_content_image_job_ids", job_ids)
        object.__setattr__(self, "not_applicable_content_image_markers", markers)
        if not isinstance(self.image_plan_receipt, ImagePlanReceipt):
            raise TypeError("image_plan_receipt must be ImagePlanReceipt")
        if not isinstance(self.image_transform_receipt, ImageTransformBatchReceipt):
            raise TypeError("image_transform_receipt is invalid")
        if self.office_layout_receipt is not None and not isinstance(
            self.office_layout_receipt, OfficeImageLayoutReceipt
        ):
            raise TypeError("office_layout_receipt is invalid")
        if not isinstance(self.publish_candidate, FileEvidence) or not isinstance(
            self.final_output, FileEvidence
        ):
            raise TypeError("candidate/final evidence is invalid")
        if (
            self.publish_candidate.sha256 != self.final_output.sha256
            or self.publish_candidate.byte_size != self.final_output.byte_size
        ):
            raise ValueError("published final does not match the verified candidate")

    def to_dict(self) -> dict[str, object]:
        return {
            "variant": self.variant.to_dict(),
            "delivery_plan": self.delivery_plan.to_dict(),
            "pipeline_output": self.pipeline_output.to_dict(),
            "visibility_evidence": self.visibility_evidence.to_dict(),
            "not_applicable_content_image_jobs": [
                {"job_id": job_id, "stable_marker_id": marker}
                for job_id, marker in zip(
                    self.not_applicable_content_image_job_ids,
                    self.not_applicable_content_image_markers,
                    strict=True,
                )
            ],
            "image_plan_receipt": self.image_plan_receipt.to_dict(),
            "image_transform_receipt": self.image_transform_receipt.to_dict(),
            "office_layout_receipt": (
                None
                if self.office_layout_receipt is None
                else self.office_layout_receipt.to_dict()
            ),
            "publish_candidate": self.publish_candidate.to_dict(),
            "final_output": self.final_output.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class MaterialAssemblyReceipt:
    receipt_id: str
    contract_version: str
    execution_id: str
    source: FileEvidence
    intake_snapshot: MaterialSnapshot
    dependency_index: MaterialDependencyIndex
    content_compose_receipt: ComposeReceipt
    pipeline_receipt: PipelineRunReceipt
    variants: tuple[VariantAssemblyReceipt, ...]

    def __post_init__(self) -> None:
        if self.contract_version != MATERIAL_ASSEMBLY_CONTRACT_VERSION:
            raise ValueError("unsupported material assembly receipt contract")
        _require_text(self.execution_id, "execution_id")
        if not isinstance(self.source, FileEvidence):
            raise TypeError("source must be FileEvidence")
        if not isinstance(self.intake_snapshot, MaterialSnapshot):
            raise TypeError("intake_snapshot must be MaterialSnapshot")
        if not isinstance(self.dependency_index, MaterialDependencyIndex):
            raise TypeError("dependency_index must be MaterialDependencyIndex")
        if not isinstance(self.content_compose_receipt, ComposeReceipt):
            raise TypeError("content_compose_receipt must be ComposeReceipt")
        if not isinstance(self.pipeline_receipt, PipelineRunReceipt):
            raise TypeError("pipeline_receipt must be PipelineRunReceipt")
        variants = tuple(self.variants or ())
        if not variants or any(
            not isinstance(item, VariantAssemblyReceipt) for item in variants
        ):
            raise ValueError("variants must contain VariantAssemblyReceipt values")
        object.__setattr__(self, "variants", variants)
        supplied = str(self.receipt_id or "").strip()
        computed = sha256(self.canonical_json().encode("utf-8")).hexdigest()
        if supplied and supplied != computed:
            raise ValueError("receipt_id does not match canonical payload")
        object.__setattr__(self, "receipt_id", computed)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "execution_id": self.execution_id,
            "source": self.source.to_dict(),
            "intake_snapshot": self.intake_snapshot.to_dict(),
            "dependency_index": self.dependency_index.to_dict(),
            "content_compose_receipt": self.content_compose_receipt.to_dict(),
            "pipeline_receipt": self.pipeline_receipt.to_dict(),
            "variants": [item.to_dict() for item in self.variants],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def to_dict(self) -> dict[str, object]:
        return {"receipt_id": self.receipt_id, **self.canonical_payload()}


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_sha256(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256")


def _freeze_text_mapping(value: object, field_name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ValueError(f"{field_name} keys must be non-empty strings")
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValueError(f"{field_name} values must be non-empty strings")
        normalized[raw_key] = raw_value
    return MappingProxyType(dict(sorted(normalized.items())))


def _freeze_plain_mapping(value: Mapping[str, object], path: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in sorted(value):
        if not isinstance(key, str):
            raise TypeError(f"{path} keys must be strings")
        item = value[key]
        if item is None or isinstance(item, (str, bool, int, float)):
            result[key] = item
        else:
            raise TypeError(f"{path}.{key} must be a scalar value")
    return result


__all__ = [
    "AssemblyDiagnostic",
    "AssemblyFailureCode",
    "AssemblyStage",
    "CancelCheck",
    "FileEvidence",
    "INTAKE_VARIANT_ID",
    "INTAKE_VARIANT_VERSION",
    "MATERIAL_ASSEMBLY_CONTRACT_VERSION",
    "MaterialAssemblyCancelled",
    "MaterialAssemblyError",
    "MaterialAssemblyReceipt",
    "MaterialAssemblyRequest",
    "MaterialPipelineCallback",
    "MaterialPipelineOutcome",
    "MaterialPipelineRequest",
    "MaterialVariantRequest",
    "PipelineRunReceipt",
    "PipelineVariantTarget",
    "PipelineVisibilityEvidence",
    "VariantAssemblyReceipt",
    "VisibilityEvidenceKind",
]
