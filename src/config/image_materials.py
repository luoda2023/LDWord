"""Immutable image-material policy and resolved-plan contracts.

No image decoding, UI, or Office automation belongs here. Configuration-time
watermark text is intentionally separated from the frozen resolved watermark
consumed by execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Mapping, TypeVar

from src.config.content_materials import FileAssetRef
from src.config.materials import normalize_asset_role
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    parse_material_token,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class _StringEnum(str, Enum):
    pass


class ImagePlacementMode(_StringEnum):
    NATURAL_SIZE = "natural_size"
    FIT_CONTAINER_FLOW = "fit_container_flow"
    FIXED_BOX = "fixed_box"
    FIXED_BOX_FLOW = "fixed_box_flow"
    FIT_REMAINING_ANCHOR_PAGE = "fit_remaining_anchor_page"


class ImageCoLocationGuard(_StringEnum):
    NONE = "none"
    PRECEDING_NONEMPTY_PARAGRAPH = "preceding_nonempty_paragraph"


class ImageAnchorOrigin(_StringEnum):
    MATERIAL_TOKEN = "material_token"
    CONTENT_RESOURCE = "content_resource"


class ImageOccurrencePolicy(_StringEnum):
    EXACTLY_ONE = "exactly_one"
    ALL = "all"


class ImageCardinality(_StringEnum):
    SINGLE = "single"
    MULTIPLE = "multiple"


class ImageWatermarkTextSource(_StringEnum):
    """Where enabled watermark text is supplied."""

    FIXED_FIELD = "fixed_field"
    WORKBENCH_FREE_FIELD = "workbench_free_field"


@dataclass(frozen=True, slots=True)
class ImageWatermarkPolicy:
    """Persisted configuration; ``text_template`` is not execution text."""

    enabled: bool = False
    text_template: str = ""
    style_version: str = "diagonal_tiled_v1"
    text_source: ImageWatermarkTextSource = ImageWatermarkTextSource.FIXED_FIELD

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a boolean")
        _coerce_enum_field(self, "text_source", ImageWatermarkTextSource)
        if not isinstance(self.text_template, str):
            raise TypeError("text_template must be a string")
        if (
            self.text_source is ImageWatermarkTextSource.WORKBENCH_FREE_FIELD
            and self.text_template.strip()
        ):
            raise ValueError(
                "workbench_free_field watermarks must not persist execution text"
            )
        _require_text(self.style_version, "style_version")
        if self.style_version != "diagonal_tiled_v1":
            raise ValueError("only diagonal_tiled_v1 image watermarks are supported")

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "text_source": self.text_source.value,
            "text_template": self.text_template,
            "style_version": self.style_version,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ImageWatermarkPolicy":
        return cls(
            enabled=payload.get("enabled", False),
            text_source=payload.get("text_source", "fixed_field") or "fixed_field",
            text_template=payload.get("text_template", ""),
            style_version=(
                payload.get("style_version", "diagonal_tiled_v1")
                or "diagonal_tiled_v1"
            ),
        )


@dataclass(frozen=True, slots=True)
class ResolvedImageWatermark:
    """Freeze-stage output; execution must never reinterpret field tokens."""

    enabled: bool
    resolved_text: str
    resolved_text_sha256: str
    resolved_font_identity: str
    resolved_font_sha256: str
    style_version: str
    transform_contract: str

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a boolean")
        _require_text(self.style_version, "style_version")
        _require_text(self.transform_contract, "transform_contract")
        if self.enabled:
            _require_text(self.resolved_text, "resolved_text")
            _require_text(self.resolved_font_identity, "resolved_font_identity")
            _validate_sha256(self.resolved_text_sha256, "resolved_text_sha256")
            _validate_sha256(self.resolved_font_sha256, "resolved_font_sha256")
        elif any(
            (
                self.resolved_text,
                self.resolved_text_sha256,
                self.resolved_font_identity,
                self.resolved_font_sha256,
            )
        ):
            raise ValueError("disabled resolved watermarks must not retain resolved text/font data")

    @classmethod
    def disabled(
        cls,
        *,
        style_version: str = "diagonal_tiled_v1",
        transform_contract: str = "image-transform-v1",
    ) -> "ResolvedImageWatermark":
        return cls(False, "", "", "", "", style_version, transform_contract)

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "resolved_text": self.resolved_text,
            "resolved_text_sha256": self.resolved_text_sha256,
            "resolved_font_identity": self.resolved_font_identity,
            "resolved_font_sha256": self.resolved_font_sha256,
            "style_version": self.style_version,
            "transform_contract": self.transform_contract,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ResolvedImageWatermark":
        return cls(
            enabled=bool(payload.get("enabled", False)),
            resolved_text=str(payload.get("resolved_text", "") or ""),
            resolved_text_sha256=str(payload.get("resolved_text_sha256", "") or ""),
            resolved_font_identity=str(payload.get("resolved_font_identity", "") or ""),
            resolved_font_sha256=str(payload.get("resolved_font_sha256", "") or ""),
            style_version=str(payload.get("style_version", "") or ""),
            transform_contract=str(payload.get("transform_contract", "") or ""),
        )


@dataclass(frozen=True, slots=True)
class ImagePlacementPolicy:
    mode: ImagePlacementMode
    contain: bool = True
    allow_crop: bool = False
    allow_move_preceding_text: bool = False
    allow_page_break: bool = False
    fixed_width_cm: float | None = None
    max_width_cm: float | None = None
    co_location_guard: ImageCoLocationGuard = ImageCoLocationGuard.NONE

    def __post_init__(self) -> None:
        _coerce_enum_field(self, "mode", ImagePlacementMode)
        _coerce_enum_field(self, "co_location_guard", ImageCoLocationGuard)
        for name in ("contain", "allow_crop", "allow_move_preceding_text", "allow_page_break"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a boolean")
        _validate_optional_positive(self.fixed_width_cm, "fixed_width_cm")
        _validate_optional_positive(self.max_width_cm, "max_width_cm")
        if self.mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE:
            if not self.contain:
                raise ValueError("fit_remaining_anchor_page requires contain=True")
            if self.allow_crop or self.allow_move_preceding_text or self.allow_page_break:
                raise ValueError(
                    "fit_remaining_anchor_page forbids crop, preceding-text moves, and page breaks"
                )
            if self.fixed_width_cm is not None:
                raise ValueError("fit_remaining_anchor_page does not use fixed_width_cm")
        elif self.mode in {
            ImagePlacementMode.NATURAL_SIZE,
            ImagePlacementMode.FIT_CONTAINER_FLOW,
        }:
            if not self.contain:
                raise ValueError(f"{self.mode.value} requires contain=True")
            if self.allow_crop or self.allow_move_preceding_text or self.allow_page_break:
                raise ValueError(
                    f"{self.mode.value} forbids crop, preceding-text moves, and page breaks"
                )
            if self.fixed_width_cm is not None:
                raise ValueError(f"{self.mode.value} does not use fixed_width_cm")
        elif self.fixed_width_cm is None:
            raise ValueError("fixed_box modes require fixed_width_cm")

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "contain": self.contain,
            "allow_crop": self.allow_crop,
            "allow_move_preceding_text": self.allow_move_preceding_text,
            "allow_page_break": self.allow_page_break,
            "fixed_width_cm": self.fixed_width_cm,
            "max_width_cm": self.max_width_cm,
            "co_location_guard": self.co_location_guard.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ImagePlacementPolicy":
        return cls(
            mode=payload.get("mode", ""),
            contain=payload.get("contain", True),
            allow_crop=payload.get("allow_crop", False),
            allow_move_preceding_text=payload.get(
                "allow_move_preceding_text", False
            ),
            allow_page_break=payload.get("allow_page_break", False),
            fixed_width_cm=_optional_float(payload.get("fixed_width_cm")),
            max_width_cm=_optional_float(payload.get("max_width_cm")),
            co_location_guard=str(payload.get("co_location_guard", "none") or "none"),
        )


@dataclass(frozen=True, slots=True)
class ImageMaterialRule:
    """Persisted binding from one image role to one canonical DOCX token.

    Layout facts which depend on the target document are deliberately absent:
    this contract records only durable user intent.  In particular, strict
    same-page placement is legal only for a single image and declares the
    exact guard that the plan builder must freeze in the target document.
    """

    rule_id: str
    source_role: str
    anchor_token: str
    placement: ImagePlacementPolicy
    required: bool = True
    occurrence_policy: ImageOccurrencePolicy = ImageOccurrencePolicy.EXACTLY_ONE
    cardinality: ImageCardinality = ImageCardinality.SINGLE
    watermark: ImageWatermarkPolicy = field(default_factory=ImageWatermarkPolicy)

    def __post_init__(self) -> None:
        _require_text(self.rule_id, "rule_id")
        object.__setattr__(self, "source_role", normalize_asset_role(self.source_role))
        _validate_source_role(self.source_role)
        if not _is_canonical_image_token(self.anchor_token):
            raise ValueError(
                "anchor_token must be an exact canonical {{...}} image token"
            )
        if not isinstance(self.required, bool):
            raise TypeError("required must be a boolean")
        _coerce_enum_field(self, "occurrence_policy", ImageOccurrencePolicy)
        _coerce_enum_field(self, "cardinality", ImageCardinality)
        if not isinstance(self.placement, ImagePlacementPolicy):
            raise TypeError("placement must be an ImagePlacementPolicy")
        if not isinstance(self.watermark, ImageWatermarkPolicy):
            raise TypeError("watermark must be an ImageWatermarkPolicy")

        if (
            self.cardinality is ImageCardinality.MULTIPLE
            and self.placement.mode
            not in {
                ImagePlacementMode.NATURAL_SIZE,
                ImagePlacementMode.FIT_CONTAINER_FLOW,
                ImagePlacementMode.FIXED_BOX_FLOW,
            }
        ):
            raise ValueError("multiple images require a flow placement")
        if self.placement.mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE:
            if self.cardinality is not ImageCardinality.SINGLE:
                raise ValueError(
                    "fit_remaining_anchor_page permits exactly one image per anchor"
                )
            if (
                self.placement.co_location_guard
                is not ImageCoLocationGuard.PRECEDING_NONEMPTY_PARAGRAPH
            ):
                raise ValueError(
                    "fit_remaining_anchor_page requires a preceding paragraph guard"
                )
        elif self.placement.co_location_guard is not ImageCoLocationGuard.NONE:
            raise ValueError("flow placement must not claim a same-page paragraph guard")

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "source_role": self.source_role,
            "anchor_token": self.anchor_token,
            "required": self.required,
            "occurrence_policy": self.occurrence_policy.value,
            "cardinality": self.cardinality.value,
            "placement": self.placement.to_dict(),
            "watermark": self.watermark.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ImageMaterialRule":
        placement = payload.get("placement")
        watermark = payload.get("watermark", {})
        if not isinstance(placement, Mapping):
            raise TypeError("placement must be a mapping")
        if not isinstance(watermark, Mapping):
            raise TypeError("watermark must be a mapping")
        return cls(
            rule_id=payload.get("rule_id", ""),
            source_role=payload.get("source_role", ""),
            anchor_token=payload.get("anchor_token", ""),
            required=payload.get("required", True),
            occurrence_policy=(
                payload.get("occurrence_policy", "exactly_one") or "exactly_one"
            ),
            cardinality=payload.get("cardinality", "single") or "single",
            placement=ImagePlacementPolicy.from_dict(placement),
            watermark=ImageWatermarkPolicy.from_dict(watermark),
        )


@dataclass(frozen=True, slots=True)
class FrozenImageMaterialRule:
    """Freeze-stage image policy with no template or runtime lookup left.

    This is deliberately a distinct type instead of an ``ImageMaterialRule``
    carrying a differently shaped watermark.  A planner can therefore accept
    only values that have crossed the image-policy Freeze boundary.
    """

    rule_id: str
    source_role: str
    anchor_token: str
    placement: ImagePlacementPolicy
    watermark: ResolvedImageWatermark
    required: bool = True
    occurrence_policy: ImageOccurrencePolicy = ImageOccurrencePolicy.EXACTLY_ONE
    cardinality: ImageCardinality = ImageCardinality.SINGLE

    def __post_init__(self) -> None:
        _require_text(self.rule_id, "rule_id")
        _validate_source_role(self.source_role)
        if not _is_canonical_image_token(self.anchor_token):
            raise ValueError(
                "anchor_token must be an exact canonical {{...}} image token"
            )
        if not isinstance(self.required, bool):
            raise TypeError("required must be a boolean")
        _coerce_enum_field(self, "occurrence_policy", ImageOccurrencePolicy)
        _coerce_enum_field(self, "cardinality", ImageCardinality)
        if not isinstance(self.placement, ImagePlacementPolicy):
            raise TypeError("placement must be an ImagePlacementPolicy")
        if not isinstance(self.watermark, ResolvedImageWatermark):
            raise TypeError("watermark must be a ResolvedImageWatermark")
        _validate_rule_layout(self.cardinality, self.placement)

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "source_role": self.source_role,
            "anchor_token": self.anchor_token,
            "required": self.required,
            "occurrence_policy": self.occurrence_policy.value,
            "cardinality": self.cardinality.value,
            "placement": self.placement.to_dict(),
            "watermark": self.watermark.to_dict(),
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, object]
    ) -> "FrozenImageMaterialRule":
        placement = payload.get("placement")
        watermark = payload.get("watermark")
        if not isinstance(placement, Mapping):
            raise TypeError("placement must be a mapping")
        if not isinstance(watermark, Mapping):
            raise TypeError("watermark must be a mapping")
        return cls(
            rule_id=str(payload.get("rule_id", "") or ""),
            source_role=str(payload.get("source_role", "") or ""),
            anchor_token=str(payload.get("anchor_token", "") or ""),
            required=payload.get("required", True),
            occurrence_policy=(
                payload.get("occurrence_policy", "exactly_one") or "exactly_one"
            ),
            cardinality=payload.get("cardinality", "single") or "single",
            placement=ImagePlacementPolicy.from_dict(placement),
            watermark=ResolvedImageWatermark.from_dict(watermark),
        )


@dataclass(frozen=True, slots=True)
class ImageSourceItem:
    """Pre-Freeze selected image supplied by intake/UI code."""

    role: str
    item_id: str
    sequence: int
    image_ref: FileAssetRef

    def __post_init__(self) -> None:
        _validate_source_role(self.role)
        _require_text(self.item_id, "item_id")
        _validate_sequence(self.sequence)
        if not isinstance(self.image_ref, FileAssetRef):
            raise TypeError("image_ref must be a FileAssetRef")
        _require_image_ref(self.image_ref, "image_ref")


@dataclass(frozen=True, slots=True)
class ImageSourceBinding:
    """Frozen binding between an image role and content-addressed bytes."""

    role: str
    item_id: str
    sequence: int
    file_ref: FileAssetRef

    def __post_init__(self) -> None:
        _validate_source_role(self.role)
        _require_text(self.item_id, "item_id")
        _validate_sequence(self.sequence)
        if not isinstance(self.file_ref, FileAssetRef):
            raise TypeError("file_ref must be a FileAssetRef")
        _require_image_ref(self.file_ref, "file_ref")

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "item_id": self.item_id,
            "sequence": self.sequence,
            "file_ref": self.file_ref.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ImageSourceBinding":
        file_ref = payload.get("file_ref")
        if not isinstance(file_ref, Mapping):
            raise TypeError("file_ref must be a mapping")
        return cls(
            role=str(payload.get("role", "") or ""),
            item_id=str(payload.get("item_id", "") or ""),
            sequence=_required_int(payload.get("sequence"), "sequence"),
            file_ref=FileAssetRef.from_dict(file_ref),
        )


@dataclass(frozen=True, slots=True)
class ImageAnchorRef:
    origin: ImageAnchorOrigin
    stable_marker_id: str
    source_token: str = ""
    guard_marker_id: str = ""

    def __post_init__(self) -> None:
        _coerce_enum_field(self, "origin", ImageAnchorOrigin)
        _require_text(self.stable_marker_id, "stable_marker_id")
        if self.origin is ImageAnchorOrigin.MATERIAL_TOKEN:
            if not _is_token(self.source_token):
                raise ValueError("material-token anchors require a canonical {{...}} source_token")
        elif self.source_token:
            raise ValueError("content-resource anchors must not retain a source_token")

    def to_dict(self) -> dict[str, object]:
        return {
            "origin": self.origin.value,
            "stable_marker_id": self.stable_marker_id,
            "source_token": self.source_token,
            "guard_marker_id": self.guard_marker_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ImageAnchorRef":
        return cls(
            origin=str(payload.get("origin", "") or ""),
            stable_marker_id=str(payload.get("stable_marker_id", "") or ""),
            source_token=str(payload.get("source_token", "") or ""),
            guard_marker_id=str(payload.get("guard_marker_id", "") or ""),
        )


@dataclass(frozen=True, slots=True)
class ResolvedImageInsertionPlan:
    """Complete, deterministic image job consumed by transform/layout phases."""

    job_id: str
    image_ref: FileAssetRef
    anchor: ImageAnchorRef
    occurrence_id: str
    watermark: ResolvedImageWatermark
    placement: ImagePlacementPolicy
    source_role: str
    sequence: int | None

    def __post_init__(self) -> None:
        _require_text(self.job_id, "job_id")
        if not isinstance(self.image_ref, FileAssetRef):
            raise TypeError("image_ref must be a FileAssetRef")
        if not self.image_ref.media_type.casefold().startswith("image/"):
            raise ValueError("image_ref must identify an image media type")
        if not isinstance(self.anchor, ImageAnchorRef):
            raise TypeError("anchor must be an ImageAnchorRef")
        if not isinstance(self.watermark, ResolvedImageWatermark):
            raise TypeError("watermark must be a ResolvedImageWatermark")
        if not isinstance(self.placement, ImagePlacementPolicy):
            raise TypeError("placement must be an ImagePlacementPolicy")
        _require_text(self.occurrence_id, "occurrence_id")
        _require_text(self.source_role, "source_role")
        if self.sequence is not None and (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValueError("sequence must be a non-negative integer when provided")
        if (
            self.placement.co_location_guard
            is ImageCoLocationGuard.PRECEDING_NONEMPTY_PARAGRAPH
            and not self.anchor.guard_marker_id
        ):
            raise ValueError("co-location guard policy requires anchor.guard_marker_id")

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "image_ref": self.image_ref.to_dict(),
            "anchor": self.anchor.to_dict(),
            "occurrence_id": self.occurrence_id,
            "watermark": self.watermark.to_dict(),
            "placement": self.placement.to_dict(),
            "source_role": self.source_role,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ResolvedImageInsertionPlan":
        nested = {}
        for name in ("image_ref", "anchor", "watermark", "placement"):
            value = payload.get(name, {})
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be a mapping")
            nested[name] = value
        sequence = payload.get("sequence")
        return cls(
            job_id=str(payload.get("job_id", "") or ""),
            image_ref=FileAssetRef.from_dict(nested["image_ref"]),
            anchor=ImageAnchorRef.from_dict(nested["anchor"]),
            occurrence_id=str(payload.get("occurrence_id", "") or ""),
            watermark=ResolvedImageWatermark.from_dict(nested["watermark"]),
            placement=ImagePlacementPolicy.from_dict(nested["placement"]),
            source_role=str(payload.get("source_role", "") or ""),
            sequence=None if sequence is None else int(sequence),
        )


DELIVERY_VARIANT_PLAN_CONTRACT_VERSION = "delivery-variant-plan-v1"


@dataclass(frozen=True, slots=True)
class DeliveryVariantPlan:
    """Content-addressed execution plan for one already-staged DOCX variant.

    ``snapshot_id`` points one way to the intake Freeze.  The intake snapshot
    never contains this plan, which removes the former snapshot/plan identity
    cycle.  The staged DOCX identity is part of the plan because its anchors
    and layout surface are the facts against which the jobs were planned.
    """

    snapshot_id: str
    variant_id: str
    variant_version: str
    staged_docx_sha256: str
    staged_docx_byte_size: int
    resolved_image_plans: tuple[ResolvedImageInsertionPlan, ...] = ()
    plan_id: str = ""
    contract_version: str = DELIVERY_VARIANT_PLAN_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != DELIVERY_VARIANT_PLAN_CONTRACT_VERSION:
            raise ValueError(
                f"unsupported delivery variant plan contract: {self.contract_version!r}"
            )
        _validate_sha256(self.snapshot_id, "snapshot_id")
        _require_text(self.variant_id, "variant_id")
        _require_text(self.variant_version, "variant_version")
        _validate_sha256(self.staged_docx_sha256, "staged_docx_sha256")
        if (
            isinstance(self.staged_docx_byte_size, bool)
            or not isinstance(self.staged_docx_byte_size, int)
            or self.staged_docx_byte_size <= 0
        ):
            raise ValueError("staged_docx_byte_size must be a positive integer")
        plans = tuple(self.resolved_image_plans or ())
        if any(not isinstance(item, ResolvedImageInsertionPlan) for item in plans):
            raise TypeError(
                "resolved_image_plans must contain ResolvedImageInsertionPlan values"
            )
        _require_unique(
            (item.job_id for item in plans),
            "resolved image plan job_id",
        )
        object.__setattr__(self, "resolved_image_plans", plans)
        supplied_id = str(self.plan_id or "").strip()
        computed_id = sha256(self.canonical_json().encode("utf-8")).hexdigest()
        if supplied_id and supplied_id != computed_id:
            raise ValueError("plan_id does not match canonical delivery plan payload")
        object.__setattr__(self, "plan_id", computed_id)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "snapshot_id": self.snapshot_id,
            "variant_id": self.variant_id,
            "variant_version": self.variant_version,
            "staged_docx_sha256": self.staged_docx_sha256,
            "staged_docx_byte_size": self.staged_docx_byte_size,
            "resolved_image_plans": [
                item.to_dict() for item in self.resolved_image_plans
            ],
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
        return {"plan_id": self.plan_id, **self.canonical_payload()}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DeliveryVariantPlan":
        raw_plans = payload.get("resolved_image_plans", ())
        if (
            not isinstance(raw_plans, (list, tuple))
            or isinstance(raw_plans, (str, bytes, bytearray))
        ):
            raise TypeError("resolved_image_plans must be a sequence")
        plans: list[ResolvedImageInsertionPlan] = []
        for item in raw_plans:
            if not isinstance(item, Mapping):
                raise TypeError("resolved image plan entries must be mappings")
            plans.append(ResolvedImageInsertionPlan.from_dict(item))
        return cls(
            plan_id=str(payload.get("plan_id", "") or ""),
            contract_version=str(payload.get("contract_version", "") or ""),
            snapshot_id=str(payload.get("snapshot_id", "") or ""),
            variant_id=str(payload.get("variant_id", "") or ""),
            variant_version=str(payload.get("variant_version", "") or ""),
            staged_docx_sha256=str(
                payload.get("staged_docx_sha256", "") or ""
            ),
            staged_docx_byte_size=_required_int(
                payload.get("staged_docx_byte_size"),
                "staged_docx_byte_size",
            ),
            resolved_image_plans=tuple(plans),
        )


def _is_token(value: str) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("{{")
        and value.endswith("}}")
        and bool(value[2:-2])
        and value[2:-2].strip() == value[2:-2]
        and "{" not in value[2:-2]
        and "}" not in value[2:-2]
    )


def _is_canonical_image_token(value: str) -> bool:
    if not _is_token(value) or value != value.strip():
        return False
    try:
        return parse_material_token(value).kind is MaterialTokenKind.IMAGE
    except (TypeError, ValueError):
        return False


def _validate_source_role(value: str) -> None:
    _require_text(value, "source_role")
    if value != value.strip() or any(char in value for char in "\\/\r\n{}"):
        raise ValueError(
            "source_role must be trimmed and must not contain paths, braces, or newlines"
        )


def _validate_rule_layout(
    cardinality: ImageCardinality,
    placement: ImagePlacementPolicy,
) -> None:
    if (
        cardinality is ImageCardinality.MULTIPLE
        and placement.mode
        not in {
            ImagePlacementMode.NATURAL_SIZE,
            ImagePlacementMode.FIT_CONTAINER_FLOW,
            ImagePlacementMode.FIXED_BOX_FLOW,
        }
    ):
        raise ValueError("multiple images require a flow placement")
    if placement.mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE:
        if cardinality is not ImageCardinality.SINGLE:
            raise ValueError(
                "fit_remaining_anchor_page permits exactly one image per anchor"
            )
        if (
            placement.co_location_guard
            is not ImageCoLocationGuard.PRECEDING_NONEMPTY_PARAGRAPH
        ):
            raise ValueError(
                "fit_remaining_anchor_page requires a preceding paragraph guard"
            )
    elif placement.co_location_guard is not ImageCoLocationGuard.NONE:
        raise ValueError("flow placement must not claim a same-page paragraph guard")


def _validate_sequence(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("sequence must be a non-negative integer")


def _require_image_ref(value: FileAssetRef, field_name: str) -> None:
    if not value.media_type.casefold().startswith("image/"):
        raise ValueError(f"{field_name} must identify an image media type")


def _required_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be an integer") from exc


def _require_unique(values, label: str) -> None:
    items = tuple(values)
    if len(items) != len(set(items)):
        raise ValueError(f"{label} values must be unique")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _validate_sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase 64-character SHA-256")


def _validate_optional_positive(value: float | None, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{field_name} must be positive when provided")


EnumType = TypeVar("EnumType", bound=Enum)


def _coerce_enum_field(instance: object, name: str, enum_type: type[EnumType]) -> None:
    raw_value = getattr(instance, name)
    try:
        value = raw_value if isinstance(raw_value, enum_type) else enum_type(str(raw_value))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{name} must be one of: {allowed}") from exc
    object.__setattr__(instance, name, value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("boolean is not a valid dimension")
    return float(value)


__all__ = [
    "DELIVERY_VARIANT_PLAN_CONTRACT_VERSION",
    "DeliveryVariantPlan",
    "FileAssetRef",
    "FrozenImageMaterialRule",
    "ImageAnchorOrigin",
    "ImageAnchorRef",
    "ImageCardinality",
    "ImageCoLocationGuard",
    "ImageMaterialRule",
    "ImageOccurrencePolicy",
    "ImagePlacementMode",
    "ImagePlacementPolicy",
    "ImageSourceBinding",
    "ImageSourceItem",
    "ImageWatermarkPolicy",
    "ImageWatermarkTextSource",
    "ResolvedImageInsertionPlan",
    "ResolvedImageWatermark",
]
