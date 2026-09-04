"""Immutable request/receipt contracts for Office image layout.

This module is deliberately pure: it defines validation and serialization
contracts, but performs no DOCX, process, COM, or filesystem orchestration.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Mapping, Sequence

from src.config.image_materials import ImagePlacementMode, ResolvedImageInsertionPlan
from src.shared.engine.prepared_image import PreparedImage

LAYOUT_SCHEMA_VERSION = 4
DEFAULT_SAFETY_MARGIN_PT = 8.0
DEFAULT_READABILITY_MIN_DIMENSION_PT = 72.0
DEFAULT_STABILIZATION_ROUNDS = 3
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

class OfficeImageProvider(str, Enum):
    WORD = "word"
    WPS = "wps"

class LayoutStatus(str, Enum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"
    CHILD_FAILED = "child_failed"

class LayoutFailureCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SOURCE_DOCX_MISSING = "source_docx_missing"
    SOURCE_DOCX_IDENTITY_MISMATCH = "source_docx_identity_mismatch"
    SOURCE_IMAGE_IDENTITY_MISMATCH = "source_image_identity_mismatch"
    PREPARED_IMAGE_IDENTITY_MISMATCH = "prepared_image_identity_mismatch"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    DUPLICATE_JOB_ID = "duplicate_job_id"
    DUPLICATE_STRICT_ANCHOR = "duplicate_strict_anchor"
    INVALID_FLOW_SEQUENCE = "invalid_flow_sequence"
    BOOKMARK_MISSING = "bookmark_missing"
    BOOKMARK_NOT_UNIQUE = "bookmark_not_unique"
    GUARD_REQUIRED = "guard_required"
    GUARD_ORDER_INVALID = "guard_order_invalid"
    GUARD_PAGE_MISMATCH = "guard_page_mismatch"
    UNSUPPORTED_SURFACE = "unsupported_surface"
    RANGE_START_MISMATCH = "range_start_mismatch"
    INVALID_GEOMETRY = "invalid_geometry"
    NO_REMAINING_SPACE = "no_remaining_space"
    BELOW_WORD_MINIMUM = "below_word_minimum"
    ABOVE_WORD_MAXIMUM = "above_word_maximum"
    PROCESS_OWNERSHIP_UNPROVEN = "process_ownership_unproven"
    OFFICE_TIMEOUT = "office_timeout"
    OFFICE_ERROR = "office_error"
    SHAPE_OWNERSHIP_INVALID = "shape_ownership_invalid"
    FINAL_COLOCATION_FAILED = "final_colocation_failed"
    FINAL_BOUNDARY_FAILED = "final_boundary_failed"
    PROPORTION_CHANGED = "proportion_changed"
    GUARD_MUTATED = "guard_mutated"
    PAGE_BREAK_MUTATED = "page_break_mutated"
    STABILIZATION_FAILED = "stabilization_failed"
    SHADOW_CREATE_FAILED = "shadow_create_failed"
    SHADOW_SAVE_FAILED = "shadow_save_failed"
    INPUT_MUTATED = "input_mutated"
    PATH_TOO_LONG = "path_too_long"
    OFFICE_INPUT_STAGE_FAILED = "office_input_stage_failed"
    IMAGE_INVENTORY_INVALID = "image_inventory_invalid"
    PREEXISTING_IMAGE_MUTATED = "preexisting_image_mutated"
    UNOWNED_IMAGE_ADDED = "unowned_image_added"
    JOB_IMAGE_HIDDEN = "job_image_hidden"
    SENTINEL_REVEALED = "sentinel_revealed"
    CHILD_PROTOCOL_ERROR = "child_protocol_error"

class LayoutWarningCode(str, Enum):
    READABILITY_RISK = "readability_risk"
    FIXED_FLOW_NO_COLOCATION_CLAIM = "fixed_flow_no_colocation_claim"
    OWNED_PROCESS_FORCED_CLEANUP = "owned_process_forced_cleanup"

@dataclass(frozen=True, slots=True)
class OfficeProviderSpec:
    provider: OfficeImageProvider
    adapter_name: str
    prog_id: str
    process_names: tuple[str, ...]

PROVIDER_SPECS: dict[OfficeImageProvider, OfficeProviderSpec] = {
    OfficeImageProvider.WORD: OfficeProviderSpec(
        OfficeImageProvider.WORD,
        "word_adapter_v1",
        "Word.Application",
        ("WINWORD",),
    ),
    OfficeImageProvider.WPS: OfficeProviderSpec(
        OfficeImageProvider.WPS,
        "wps_adapter_v1",
        "KWPS.Application",
        ("wps",),
    ),
}


@dataclass(frozen=True, slots=True)
class OfficeImageLayoutJob:
    plan: ResolvedImageInsertionPlan
    prepared_image: PreparedImage
    expected_anchor_start: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ResolvedImageInsertionPlan):
            raise TypeError("plan must be a ResolvedImageInsertionPlan")
        if not isinstance(self.prepared_image, PreparedImage):
            raise TypeError("prepared_image must be a PreparedImage")
        if self.expected_anchor_start is not None and (
            isinstance(self.expected_anchor_start, bool)
            or not isinstance(self.expected_anchor_start, int)
            or self.expected_anchor_start < 0
        ):
            raise ValueError("expected_anchor_start must be a non-negative integer")

    @property
    def job_id(self) -> str:
        return self.plan.job_id

    def to_dict(self) -> dict[str, object]:
        return {
            "plan": self.plan.to_dict(),
            "prepared_image": _prepared_to_dict(self.prepared_image),
            "expected_anchor_start": self.expected_anchor_start,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> OfficeImageLayoutJob:
        plan = payload.get("plan")
        prepared = payload.get("prepared_image")
        if not isinstance(plan, Mapping) or not isinstance(prepared, Mapping):
            raise TypeError("job plan/prepared_image must be mappings")
        expected = payload.get("expected_anchor_start")
        return cls(
            plan=ResolvedImageInsertionPlan.from_dict(plan),
            prepared_image=_prepared_from_dict(prepared),
            expected_anchor_start=None if expected is None else int(expected),
        )

@dataclass(frozen=True, slots=True)
class OfficeImageLayoutRequest:
    transaction_id: str
    source_docx_path: str
    source_docx_sha256: str
    source_docx_size: int
    provider: OfficeImageProvider
    jobs: tuple[OfficeImageLayoutJob, ...]
    timeout_seconds: float = 90.0
    max_stabilization_rounds: int = DEFAULT_STABILIZATION_ROUNDS
    safety_margin_pt: float = DEFAULT_SAFETY_MARGIN_PT
    readability_min_dimension_pt: float = DEFAULT_READABILITY_MIN_DIMENSION_PT
    correction_shrink_factor: float = 0.9

    def __post_init__(self) -> None:
        if not self.transaction_id.strip():
            raise ValueError("transaction_id must not be empty")
        if not self.source_docx_path:
            raise ValueError("source_docx_path must not be empty")
        _require_sha256(self.source_docx_sha256, "source_docx_sha256")
        if (
            isinstance(self.source_docx_size, bool)
            or not isinstance(self.source_docx_size, int)
            or self.source_docx_size < 0
        ):
            raise ValueError("source_docx_size must be a non-negative integer")
        provider = (
            self.provider
            if isinstance(self.provider, OfficeImageProvider)
            else OfficeImageProvider(str(self.provider))
        )
        object.__setattr__(self, "provider", provider)
        jobs = tuple(self.jobs or ())
        if not jobs or any(not isinstance(item, OfficeImageLayoutJob) for item in jobs):
            raise ValueError("jobs must contain at least one OfficeImageLayoutJob")
        object.__setattr__(self, "jobs", jobs)
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
            or not math.isfinite(self.timeout_seconds)
        ):
            raise ValueError("timeout_seconds must be positive")
        if isinstance(self.max_stabilization_rounds, bool) or self.max_stabilization_rounds not in {2, 3}:
            raise ValueError("max_stabilization_rounds must be 2 or 3")
        if self.safety_margin_pt < 0 or not math.isfinite(self.safety_margin_pt):
            raise ValueError("safety_margin_pt must be finite and non-negative")
        if self.readability_min_dimension_pt <= 0:
            raise ValueError("readability_min_dimension_pt must be positive")
        if not 0 < self.correction_shrink_factor < 1:
            raise ValueError("correction_shrink_factor must be between 0 and 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "transaction_id": self.transaction_id,
            "source_docx_path": self.source_docx_path,
            "source_docx_sha256": self.source_docx_sha256,
            "source_docx_size": self.source_docx_size,
            "provider": self.provider.value,
            "jobs": [item.to_dict() for item in self.jobs],
            "timeout_seconds": self.timeout_seconds,
            "max_stabilization_rounds": self.max_stabilization_rounds,
            "safety_margin_pt": self.safety_margin_pt,
            "readability_min_dimension_pt": self.readability_min_dimension_pt,
            "correction_shrink_factor": self.correction_shrink_factor,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> OfficeImageLayoutRequest:
        jobs = payload.get("jobs", ())
        if not isinstance(jobs, Sequence) or isinstance(jobs, (str, bytes)):
            raise TypeError("jobs must be a sequence")
        if any(not isinstance(item, Mapping) for item in jobs):
            raise TypeError("each job must be a mapping")
        return cls(
            transaction_id=str(payload.get("transaction_id", "") or ""),
            source_docx_path=str(payload.get("source_docx_path", "") or ""),
            source_docx_sha256=str(payload.get("source_docx_sha256", "") or ""),
            source_docx_size=int(payload.get("source_docx_size", 0) or 0),
            provider=OfficeImageProvider(str(payload.get("provider", "") or "")),
            jobs=tuple(
                OfficeImageLayoutJob.from_dict(item)
                for item in jobs
                if isinstance(item, Mapping)
            ),
            timeout_seconds=float(payload.get("timeout_seconds", 90.0) or 90.0),
            max_stabilization_rounds=int(
                payload.get("max_stabilization_rounds", DEFAULT_STABILIZATION_ROUNDS)
                or DEFAULT_STABILIZATION_ROUNDS
            ),
            safety_margin_pt=float(
                DEFAULT_SAFETY_MARGIN_PT
                if payload.get("safety_margin_pt") is None
                else payload.get("safety_margin_pt")
            ),
            readability_min_dimension_pt=float(
                payload.get(
                    "readability_min_dimension_pt",
                    DEFAULT_READABILITY_MIN_DIMENSION_PT,
                )
                or DEFAULT_READABILITY_MIN_DIMENSION_PT
            ),
            correction_shrink_factor=float(
                payload.get("correction_shrink_factor", 0.9) or 0.9
            ),
        )

@dataclass(frozen=True, slots=True)
class LayoutFailure:
    code: LayoutFailureCode
    message: str
    job_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message, "job_id": self.job_id}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> LayoutFailure:
        return cls(
            LayoutFailureCode(str(payload.get("code", ""))),
            str(payload.get("message", "") or ""),
            str(payload.get("job_id", "") or ""),
        )

@dataclass(frozen=True, slots=True)
class LayoutWarning:
    code: LayoutWarningCode
    message: str
    job_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message, "job_id": self.job_id}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> LayoutWarning:
        return cls(
            LayoutWarningCode(str(payload.get("code", ""))),
            str(payload.get("message", "") or ""),
            str(payload.get("job_id", "") or ""),
        )

@dataclass(frozen=True, slots=True)
class OfficeImageJobReceipt:
    job_id: str
    mode: ImagePlacementMode
    sequence: int | None
    shape_id: str
    source_image_sha256: str
    prepared_image_sha256: str
    measurement_guard_page: int | None
    measurement_anchor_page: int
    measurement_anchor_start: int
    anchor_y_pt: float
    section_index: int
    column_index: int
    column_count: int
    container_width_pt: float
    flow_bottom_pt: float
    paragraph_reserve_pt: float
    safety_margin_pt: float
    available_height_pt: float | None
    width_cap_pt: float
    initial_target_width_pt: float
    initial_target_height_pt: float
    initial_scale_ratio: float
    readability_warning: bool
    co_location_claimed: bool
    final_guard_page: int | None = None
    final_anchor_page: int | None = None
    final_image_page: int | None = None
    final_image_y_pt: float | None = None
    final_width_pt: float | None = None
    final_height_pt: float | None = None
    proportion_error: float | None = None
    boundary_ok: bool = False
    guard_xml_sha256_before: str = ""
    guard_xml_sha256_after: str = ""
    guard_keep_sha256_before: str = ""
    guard_keep_sha256_after: str = ""
    correction_count: int = 0
    initial_actual_width_pt: float | None = None
    initial_actual_height_pt: float | None = None
    initial_proportion_error: float | None = None
    dimension_candidate_count: int = 1
    selected_width_offset_pt: float = 0.0

    def __post_init__(self) -> None:
        mode = self.mode if isinstance(self.mode, ImagePlacementMode) else ImagePlacementMode(str(self.mode))
        object.__setattr__(self, "mode", mode)
        _require_sha256(self.source_image_sha256, "source_image_sha256")
        _require_sha256(self.prepared_image_sha256, "prepared_image_sha256")
        for name in (
            "guard_xml_sha256_before",
            "guard_xml_sha256_after",
            "guard_keep_sha256_before",
            "guard_keep_sha256_after",
        ):
            value = getattr(self, name)
            if value:
                _require_sha256(value, name)
        if not self.job_id or not self.shape_id:
            raise ValueError("job_id and shape_id must not be empty")
        if self.co_location_claimed and self.measurement_guard_page is None:
            raise ValueError("co-location receipts require a measurement guard page")
        if self.correction_count < 0:
            raise ValueError("correction_count cannot be negative")
        for name in (
            "initial_actual_width_pt",
            "initial_actual_height_pt",
            "initial_proportion_error",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0
            ):
                raise ValueError(f"{name} must be finite and non-negative")
        if (
            isinstance(self.dimension_candidate_count, bool)
            or not isinstance(self.dimension_candidate_count, int)
            or self.dimension_candidate_count < 1
        ):
            raise ValueError("dimension_candidate_count must be a positive integer")
        if not math.isfinite(float(self.selected_width_offset_pt)):
            raise ValueError("selected_width_offset_pt must be finite")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            result[name] = value.value if isinstance(value, Enum) else value
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> OfficeImageJobReceipt:
        values = dict(payload)
        values["mode"] = ImagePlacementMode(str(values["mode"]))
        return cls(**values)  # type: ignore[arg-type]

@dataclass(frozen=True, slots=True)
class StabilizationRoundReceipt:
    round_index: int
    page_count: int
    field_update_count: int
    job_pages: tuple[tuple[str, int | None, int | None, int | None], ...]
    violation_job_ids: tuple[str, ...]
    corrected_job_ids: tuple[str, ...]
    revalidate_from_job_id: str
    state_sha256: str
    stable: bool

    def __post_init__(self) -> None:
        if self.round_index < 1 or self.page_count < 1 or self.field_update_count < 0:
            raise ValueError("stabilization round counters are invalid")
        _require_sha256(self.state_sha256, "state_sha256")
        object.__setattr__(self, "job_pages", tuple(self.job_pages or ()))
        object.__setattr__(self, "violation_job_ids", tuple(self.violation_job_ids or ()))
        object.__setattr__(self, "corrected_job_ids", tuple(self.corrected_job_ids or ()))

    def to_dict(self) -> dict[str, object]:
        return {
            "round_index": self.round_index,
            "page_count": self.page_count,
            "field_update_count": self.field_update_count,
            "job_pages": [list(item) for item in self.job_pages],
            "violation_job_ids": list(self.violation_job_ids),
            "corrected_job_ids": list(self.corrected_job_ids),
            "revalidate_from_job_id": self.revalidate_from_job_id,
            "state_sha256": self.state_sha256,
            "stable": self.stable,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> StabilizationRoundReceipt:
        return cls(
            round_index=int(payload.get("round_index", 0) or 0),
            page_count=int(payload.get("page_count", 0) or 0),
            field_update_count=int(payload.get("field_update_count", 0) or 0),
            job_pages=tuple(
                (str(item[0]), _opt_int(item[1]), _opt_int(item[2]), _opt_int(item[3]))
                for item in payload.get("job_pages", ())  # type: ignore[union-attr]
            ),
            violation_job_ids=tuple(str(x) for x in payload.get("violation_job_ids", ())),
            corrected_job_ids=tuple(str(x) for x in payload.get("corrected_job_ids", ())),
            revalidate_from_job_id=str(payload.get("revalidate_from_job_id", "") or ""),
            state_sha256=str(payload.get("state_sha256", "") or ""),
            stable=bool(payload.get("stable", False)),
        )

@dataclass(frozen=True, slots=True)
class OOXMLImageIdentity:
    """Package-local identity for one DrawingML/VML image reference.

    The identity deliberately excludes ZIP timestamps, compression details, XML
    paths, and other package metadata that Word/WPS may legitimately rewrite.
    It contains only the image-bearing part, shape identity, relationship, and
    the bytes of the relationship target.  ``docPr/@id`` and relationship ids
    remain explicit evidence, but are provider-assigned local keys: real Word
    and WPS may renumber them on save.  Preservation therefore compares the
    semantic key below while still exposing both complete inventories.  Repeated
    identical references remain repeated rows and are compared as a multiset.
    """

    part_name: str
    drawing_kind: str
    doc_pr_id: str
    doc_pr_name: str
    alternative_text: str
    title: str
    run_visibility: str
    layout_extent_cx_emu: int
    layout_extent_cy_emu: int
    drawing_semantic_sha256: str
    relationship_reference: str
    relationship_id: str
    relationship_type: str
    relationship_target: str
    target_mode: str
    media_part_name: str
    media_sha256: str

    def __post_init__(self) -> None:
        if not self.part_name or self.drawing_kind not in {"inline", "anchor", "vml"}:
            raise ValueError("image identity requires a part and supported drawing kind")
        if not self.run_visibility:
            raise ValueError("image identity run_visibility must not be empty")
        for name in ("layout_extent_cx_emu", "layout_extent_cy_emu"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        _require_sha256(self.drawing_semantic_sha256, "drawing_semantic_sha256")
        if self.relationship_reference not in {"embed", "link", "id", "href"}:
            raise ValueError("invalid image relationship reference kind")
        if not self.relationship_id or not self.relationship_target:
            raise ValueError("image identity relationship id/target must not be empty")
        if self.target_mode not in {"internal", "external"}:
            raise ValueError("image identity target_mode must be internal or external")
        if self.target_mode == "internal":
            if not self.media_part_name:
                raise ValueError("internal image identity requires media_part_name")
            _require_sha256(self.media_sha256, "media_sha256")
        elif self.media_sha256:
            _require_sha256(self.media_sha256, "media_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> OOXMLImageIdentity:
        values = {
            name: str(payload.get(name, "") or "")
            for name in cls.__dataclass_fields__
            if name not in {"layout_extent_cx_emu", "layout_extent_cy_emu"}
        }
        values["layout_extent_cx_emu"] = int(
            payload.get("layout_extent_cx_emu", 0) or 0
        )
        values["layout_extent_cy_emu"] = int(
            payload.get("layout_extent_cy_emu", 0) or 0
        )
        return cls(**values)  # type: ignore[arg-type]

    @property
    def sort_key(self) -> tuple[str, ...]:
        return tuple(str(getattr(self, name)) for name in self.__dataclass_fields__)

    @property
    def preservation_key(self) -> tuple[str, ...]:
        return tuple(
            str(getattr(self, name))
            for name in self.__dataclass_fields__
            if name
            not in {
                "doc_pr_id",
                "relationship_id",
                "layout_extent_cx_emu",
                "layout_extent_cy_emu",
            }
        )

@dataclass(frozen=True, slots=True)
class OfficeImageLayoutReceipt:
    schema_version: int
    transaction_id: str
    provider: OfficeImageProvider
    adapter_name: str
    prog_id: str
    status: LayoutStatus
    application_pid: int | None
    source_docx_path: str
    source_docx_sha256_before: str
    source_docx_sha256_after: str
    shadow_path: str
    shadow_sha256: str
    shadow_retained: bool
    source_images_unchanged: bool
    prepared_images_unchanged: bool
    document_open_count: int
    document_save_count: int
    repaginate_count: int
    pdf_export_count: int
    field_update_rounds: int
    page_break_count_before: int
    page_break_count_after: int
    jobs: tuple[OfficeImageJobReceipt, ...]
    stabilization_rounds: tuple[StabilizationRoundReceipt, ...]
    warnings: tuple[LayoutWarning, ...]
    failures: tuple[LayoutFailure, ...]
    elapsed_ms: float = 0.0
    source_image_inventory_sha256: str = ""
    shadow_image_inventory_sha256: str = ""
    preexisting_image_semantic_sha256_before: str = ""
    preexisting_image_semantic_sha256_after: str = ""
    preexisting_images_unchanged: bool = False
    inserted_images_job_owned: bool = False
    inserted_images_visible: bool = False
    sentinel_texts_hidden: bool = False
    source_image_inventory: tuple[OOXMLImageIdentity, ...] = ()
    shadow_image_inventory: tuple[OOXMLImageIdentity, ...] = ()
    inserted_image_inventory: tuple[OOXMLImageIdentity, ...] = ()

    def __post_init__(self) -> None:
        provider = self.provider if isinstance(self.provider, OfficeImageProvider) else OfficeImageProvider(str(self.provider))
        status = self.status if isinstance(self.status, LayoutStatus) else LayoutStatus(str(self.status))
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "status", status)
        _require_sha256(self.source_docx_sha256_before, "source_docx_sha256_before")
        for name in ("source_docx_sha256_after", "shadow_sha256"):
            value = getattr(self, name)
            if value:
                _require_sha256(value, name)
        for name in (
            "source_image_inventory_sha256",
            "shadow_image_inventory_sha256",
            "preexisting_image_semantic_sha256_before",
            "preexisting_image_semantic_sha256_after",
        ):
            value = getattr(self, name)
            if value:
                _require_sha256(value, name)
        for name in (
            "document_open_count",
            "document_save_count",
            "repaginate_count",
            "pdf_export_count",
            "field_update_rounds",
            "page_break_count_before",
            "page_break_count_after",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.elapsed_ms < 0 or not math.isfinite(self.elapsed_ms):
            raise ValueError("elapsed_ms must be finite and non-negative")
        for name, expected in (
            ("jobs", OfficeImageJobReceipt),
            ("stabilization_rounds", StabilizationRoundReceipt),
            ("warnings", LayoutWarning),
            ("failures", LayoutFailure),
        ):
            values = tuple(getattr(self, name) or ())
            if any(not isinstance(item, expected) for item in values):
                raise TypeError(f"{name} contains an invalid receipt item")
            object.__setattr__(self, name, values)
        for name in (
            "source_image_inventory",
            "shadow_image_inventory",
            "inserted_image_inventory",
        ):
            values = tuple(getattr(self, name) or ())
            if any(not isinstance(item, OOXMLImageIdentity) for item in values):
                raise TypeError(f"{name} contains an invalid image identity")
            object.__setattr__(self, name, values)

    @property
    def succeeded(self) -> bool:
        return self.status is LayoutStatus.SUCCESS and not self.failures

    def to_identity_dict(self) -> dict[str, object]:
        payload = self.to_dict(include_identity=False)
        payload.pop("elapsed_ms", None)
        return payload

    @property
    def identity_sha256(self) -> str:
        encoded = json.dumps(
            self.to_identity_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def to_dict(self, *, include_identity: bool = True) -> dict[str, object]:
        payload = {
            "schema_version": self.schema_version,
            "transaction_id": self.transaction_id,
            "provider": self.provider.value,
            "adapter_name": self.adapter_name,
            "prog_id": self.prog_id,
            "status": self.status.value,
            "application_pid": self.application_pid,
            "source_docx_path": self.source_docx_path,
            "source_docx_sha256_before": self.source_docx_sha256_before,
            "source_docx_sha256_after": self.source_docx_sha256_after,
            "shadow_path": self.shadow_path,
            "shadow_sha256": self.shadow_sha256,
            "shadow_retained": self.shadow_retained,
            "source_images_unchanged": self.source_images_unchanged,
            "prepared_images_unchanged": self.prepared_images_unchanged,
            "document_open_count": self.document_open_count,
            "document_save_count": self.document_save_count,
            "repaginate_count": self.repaginate_count,
            "pdf_export_count": self.pdf_export_count,
            "field_update_rounds": self.field_update_rounds,
            "page_break_count_before": self.page_break_count_before,
            "page_break_count_after": self.page_break_count_after,
            "jobs": [item.to_dict() for item in self.jobs],
            "stabilization_rounds": [item.to_dict() for item in self.stabilization_rounds],
            "warnings": [item.to_dict() for item in self.warnings],
            "failures": [item.to_dict() for item in self.failures],
            "elapsed_ms": self.elapsed_ms,
            "source_image_inventory_sha256": self.source_image_inventory_sha256,
            "shadow_image_inventory_sha256": self.shadow_image_inventory_sha256,
            "preexisting_image_semantic_sha256_before": (
                self.preexisting_image_semantic_sha256_before
            ),
            "preexisting_image_semantic_sha256_after": (
                self.preexisting_image_semantic_sha256_after
            ),
            "preexisting_images_unchanged": self.preexisting_images_unchanged,
            "inserted_images_job_owned": self.inserted_images_job_owned,
            "inserted_images_visible": self.inserted_images_visible,
            "sentinel_texts_hidden": self.sentinel_texts_hidden,
            "source_image_inventory": [
                item.to_dict() for item in self.source_image_inventory
            ],
            "shadow_image_inventory": [
                item.to_dict() for item in self.shadow_image_inventory
            ],
            "inserted_image_inventory": [
                item.to_dict() for item in self.inserted_image_inventory
            ],
        }
        if include_identity:
            payload["identity_sha256"] = self.identity_sha256
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> OfficeImageLayoutReceipt:
        return cls(
            schema_version=int(payload.get("schema_version", LAYOUT_SCHEMA_VERSION)),
            transaction_id=str(payload.get("transaction_id", "") or ""),
            provider=OfficeImageProvider(str(payload.get("provider", ""))),
            adapter_name=str(payload.get("adapter_name", "") or ""),
            prog_id=str(payload.get("prog_id", "") or ""),
            status=LayoutStatus(str(payload.get("status", ""))),
            application_pid=_opt_int(payload.get("application_pid")),
            source_docx_path=str(payload.get("source_docx_path", "") or ""),
            source_docx_sha256_before=str(payload.get("source_docx_sha256_before", "") or ""),
            source_docx_sha256_after=str(payload.get("source_docx_sha256_after", "") or ""),
            shadow_path=str(payload.get("shadow_path", "") or ""),
            shadow_sha256=str(payload.get("shadow_sha256", "") or ""),
            shadow_retained=bool(payload.get("shadow_retained", False)),
            source_images_unchanged=bool(payload.get("source_images_unchanged", False)),
            prepared_images_unchanged=bool(payload.get("prepared_images_unchanged", False)),
            document_open_count=int(payload.get("document_open_count", 0) or 0),
            document_save_count=int(payload.get("document_save_count", 0) or 0),
            repaginate_count=int(payload.get("repaginate_count", 0) or 0),
            pdf_export_count=int(payload.get("pdf_export_count", 0) or 0),
            field_update_rounds=int(payload.get("field_update_rounds", 0) or 0),
            page_break_count_before=int(payload.get("page_break_count_before", 0) or 0),
            page_break_count_after=int(payload.get("page_break_count_after", 0) or 0),
            jobs=tuple(
                OfficeImageJobReceipt.from_dict(item)
                for item in payload.get("jobs", ())
                if isinstance(item, Mapping)
            ),
            stabilization_rounds=tuple(
                StabilizationRoundReceipt.from_dict(item)
                for item in payload.get("stabilization_rounds", ())
                if isinstance(item, Mapping)
            ),
            warnings=tuple(
                LayoutWarning.from_dict(item)
                for item in payload.get("warnings", ())
                if isinstance(item, Mapping)
            ),
            failures=tuple(
                LayoutFailure.from_dict(item)
                for item in payload.get("failures", ())
                if isinstance(item, Mapping)
            ),
            elapsed_ms=float(payload.get("elapsed_ms", 0.0) or 0.0),
            source_image_inventory_sha256=str(
                payload.get("source_image_inventory_sha256", "") or ""
            ),
            shadow_image_inventory_sha256=str(
                payload.get("shadow_image_inventory_sha256", "") or ""
            ),
            preexisting_image_semantic_sha256_before=str(
                payload.get("preexisting_image_semantic_sha256_before", "") or ""
            ),
            preexisting_image_semantic_sha256_after=str(
                payload.get("preexisting_image_semantic_sha256_after", "") or ""
            ),
            preexisting_images_unchanged=bool(
                payload.get("preexisting_images_unchanged", False)
            ),
            inserted_images_job_owned=bool(
                payload.get("inserted_images_job_owned", False)
            ),
            inserted_images_visible=bool(
                payload.get("inserted_images_visible", False)
            ),
            sentinel_texts_hidden=bool(
                payload.get("sentinel_texts_hidden", False)
            ),
            source_image_inventory=tuple(
                OOXMLImageIdentity.from_dict(item)
                for item in payload.get("source_image_inventory", ())
                if isinstance(item, Mapping)
            ),
            shadow_image_inventory=tuple(
                OOXMLImageIdentity.from_dict(item)
                for item in payload.get("shadow_image_inventory", ())
                if isinstance(item, Mapping)
            ),
            inserted_image_inventory=tuple(
                OOXMLImageIdentity.from_dict(item)
                for item in payload.get("inserted_image_inventory", ())
                if isinstance(item, Mapping)
            ),
        )

def build_layout_receipt(
    request: OfficeImageLayoutRequest,
    spec: OfficeProviderSpec,
    status: LayoutStatus,
    *,
    application_pid: int | None = None,
    open_count: int = 0,
    save_count: int = 0,
    repaginate_count: int = 0,
    field_rounds: int = 0,
    page_breaks_before: int = 0,
    page_breaks_after: int = 0,
    jobs: tuple[OfficeImageJobReceipt, ...] = (),
    rounds: tuple[StabilizationRoundReceipt, ...] = (),
    warnings: tuple[LayoutWarning, ...] = (),
    failures: tuple[LayoutFailure, ...] = (),
    elapsed_ms: float = 0.0,
    source_image_inventory: tuple[OOXMLImageIdentity, ...] = (),
    source_image_inventory_sha256: str = "",
    preexisting_image_semantic_sha256_before: str = "",
) -> OfficeImageLayoutReceipt:
    return OfficeImageLayoutReceipt(
        schema_version=LAYOUT_SCHEMA_VERSION,
        transaction_id=request.transaction_id,
        provider=request.provider,
        adapter_name=spec.adapter_name,
        prog_id=spec.prog_id,
        status=status,
        application_pid=application_pid,
        source_docx_path=request.source_docx_path,
        source_docx_sha256_before=request.source_docx_sha256,
        source_docx_sha256_after="",
        shadow_path="",
        shadow_sha256="",
        shadow_retained=False,
        source_images_unchanged=False,
        prepared_images_unchanged=False,
        document_open_count=open_count,
        document_save_count=save_count,
        repaginate_count=repaginate_count,
        pdf_export_count=0,
        field_update_rounds=field_rounds,
        page_break_count_before=page_breaks_before,
        page_break_count_after=page_breaks_after,
        jobs=jobs,
        stabilization_rounds=rounds,
        warnings=warnings,
        failures=failures,
        elapsed_ms=elapsed_ms,
        source_image_inventory_sha256=source_image_inventory_sha256,
        preexisting_image_semantic_sha256_before=(
            preexisting_image_semantic_sha256_before
        ),
        source_image_inventory=source_image_inventory,
    )

def _prepared_to_dict(prepared: PreparedImage) -> dict[str, object]:
    return {name: getattr(prepared, name) for name in prepared.__dataclass_fields__}

def _prepared_from_dict(payload: Mapping[str, object]) -> PreparedImage:
    return PreparedImage(
        cache_key=str(payload.get("cache_key", "") or ""),
        output_path=str(payload.get("output_path", "") or ""),
        output_sha256=str(payload.get("output_sha256", "") or ""),
        media_type=str(payload.get("media_type", "") or ""),
        width_px=int(payload.get("width_px", 0) or 0),
        height_px=int(payload.get("height_px", 0) or 0),
        source_sha256=str(payload.get("source_sha256", "") or ""),
        watermark_text_sha256=str(payload.get("watermark_text_sha256", "") or ""),
        transform_contract=str(payload.get("transform_contract", "image-transform-v1") or ""),
        cache_hit=bool(payload.get("cache_hit", False)),
    )

def _require_sha256(value: str, name: str) -> None:
    if not _SHA256_RE.fullmatch(str(value or "")):
        raise ValueError(f"{name} must be a lowercase SHA-256")

def job_owned_shape_id(job_id: str) -> str:
    return "ldword-layout-image-" + sha256(job_id.encode("utf-8")).hexdigest()[:20]

def _opt_int(value: object) -> int | None:
    return None if value is None else int(value)

__all__ = [
    "DEFAULT_READABILITY_MIN_DIMENSION_PT",
    "DEFAULT_SAFETY_MARGIN_PT",
    "DEFAULT_STABILIZATION_ROUNDS",
    "LAYOUT_SCHEMA_VERSION",
    "LayoutFailure",
    "LayoutFailureCode",
    "LayoutStatus",
    "LayoutWarning",
    "LayoutWarningCode",
    "OOXMLImageIdentity",
    "OfficeImageJobReceipt",
    "OfficeImageLayoutJob",
    "OfficeImageLayoutReceipt",
    "OfficeImageLayoutRequest",
    "OfficeImageProvider",
    "OfficeProviderSpec",
    "PROVIDER_SPECS",
    "StabilizationRoundReceipt",
    "build_layout_receipt",
    "job_owned_shape_id",
]
