"""Freeze validated image inputs into deterministic DOCX insertion plans.

The builder is the only bridge between persisted image-material intent and
the later pixel-transform/layout phases.  It intentionally does *not* insert
drawings or page breaks.  Its commit changes only material-token paragraphs
into hidden bookmark sentinels, plus optional bookmark boundaries around the
already-existing paragraph that must stay with a strict same-page image.

All filesystem, token-surface, and OOXML validation completes before the
first target-document mutation.  A failed preflight therefore leaves the
target document byte-for-byte unchanged at the XML level.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Mapping, Sequence
import warnings

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image, UnidentifiedImageError

from src.config.content_artifacts import ContentArtifactResource
from src.config.content_materials import ContentResourceKey, FileAssetRef
from src.config.image_materials import (
    FrozenImageMaterialRule,
    ImageAnchorOrigin,
    ImageAnchorRef,
    ImageCardinality,
    ImageCoLocationGuard,
    ImageOccurrencePolicy,
    ImagePlacementMode,
    ImagePlacementPolicy,
    ImageSourceBinding,
    ImageSourceItem,
    ResolvedImageInsertionPlan,
    ResolvedImageWatermark,
)
from src.services.material_content.docx_renderer import ContentImageJobDraft
from src.shared.engine.docx_material_tokens import (
    extract_docx_material_token_blocks,
    is_strict_material_token_paragraph,
    paragraph_text_fragments,
)
from src.shared.engine.material_token_router import (
    MaterialTokenKind,
    TokenDeclaration,
    TokenDiagnosticSeverity,
    TokenOccurrencePolicy,
    route_material_tokens,
)

if TYPE_CHECKING:
    from docx.document import Document as DocumentType


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_IMAGE_FORMATS: dict[str, tuple[str, frozenset[str]]] = {
    "PNG": ("image/png", frozenset({".png"})),
    "JPEG": ("image/jpeg", frozenset({".jpg", ".jpeg"})),
    "WEBP": ("image/webp", frozenset({".webp"})),
    "BMP": ("image/bmp", frozenset({".bmp"})),
    "TIFF": ("image/tiff", frozenset({".tif", ".tiff"})),
}
_OFFICE_OR_DOCUMENT_EXTENSIONS = frozenset(
    {
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".pdf",
        ".rtf",
    }
)


class ImagePlanSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ImagePlanDiagnostic:
    severity: ImagePlanSeverity
    code: str
    message: str
    rule_id: str = ""
    source_role: str = ""
    anchor_token: str = ""
    item_id: str = ""
    surface: str = ""


class ImagePlanBuildError(ValueError):
    """Aggregate preflight failure; the target DOCX has not been changed."""

    def __init__(self, diagnostics: Sequence[ImagePlanDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        detail = "\n".join(
            f"- [{item.code}] {item.message}" for item in self.diagnostics
        )
        super().__init__(f"Image insertion planning blocked:\n{detail}")


def _default_content_image_placement() -> ImagePlacementPolicy:
    return ImagePlacementPolicy(
        mode=ImagePlacementMode.FIXED_BOX_FLOW,
        fixed_width_cm=16.0,
    )


@dataclass(frozen=True, slots=True)
class ContentResourceImageSource:
    """Resolve one compiled content-image resource to bytes and image policy."""

    resource: ContentArtifactResource
    source_path: str
    placement: ImagePlacementPolicy = field(
        default_factory=_default_content_image_placement
    )
    watermark: ResolvedImageWatermark = field(
        default_factory=ResolvedImageWatermark.disabled
    )
    source_role: str = "content_resource"
    guard_marker_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.resource, ContentArtifactResource):
            raise TypeError("resource must be a ContentArtifactResource")
        _require_text(self.source_path, "source_path")
        if not isinstance(self.placement, ImagePlacementPolicy):
            raise TypeError("placement must be an ImagePlacementPolicy")
        if not isinstance(self.watermark, ResolvedImageWatermark):
            raise TypeError("watermark must be a ResolvedImageWatermark")
        _require_text(self.source_role, "source_role")
        if self.placement.mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE:
            if (
                self.placement.co_location_guard
                is not ImageCoLocationGuard.PRECEDING_NONEMPTY_PARAGRAPH
                or not self.guard_marker_id.strip()
            ):
                raise ValueError(
                    "strict content-resource placement requires an explicit guard marker"
                )
        elif self.placement.mode not in {
            ImagePlacementMode.FIXED_BOX,
            ImagePlacementMode.FIXED_BOX_FLOW,
        }:
            raise ValueError("unsupported content-resource image placement")
        elif (
            self.guard_marker_id
            or self.placement.co_location_guard is not ImageCoLocationGuard.NONE
        ):
            raise ValueError(
                "fixed content-resource placement must not claim a same-page guard"
            )

    @classmethod
    def from_materialized_resource(
        cls,
        materialized,
        *,
        placement: ImagePlacementPolicy | None = None,
        watermark: ResolvedImageWatermark | None = None,
        source_role: str = "content_resource",
        guard_marker_id: str = "",
    ) -> "ContentResourceImageSource":
        """Build an image source from the verified content cache receipt."""

        from src.services.material_content.resource_materializer import (
            MaterializedContentResource,
        )

        if not isinstance(materialized, MaterializedContentResource):
            raise TypeError(
                "materialized must be a MaterializedContentResource"
            )
        return cls(
            resource=materialized.resource,
            source_path=materialized.source_path,
            placement=placement or _default_content_image_placement(),
            watermark=watermark or ResolvedImageWatermark.disabled(),
            source_role=source_role,
            guard_marker_id=guard_marker_id,
        )


@dataclass(frozen=True, slots=True)
class ImagePlanReceiptEntry:
    job_id: str
    occurrence_id: str
    stable_marker_id: str
    guard_marker_id: str
    origin: ImageAnchorOrigin
    source_role: str
    item_id: str
    sequence: int
    body_element_index: int
    document_order: int
    reserved_docpr_id: int
    source_sha256: str
    watermark_text_sha256: str
    watermark_font_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "occurrence_id": self.occurrence_id,
            "stable_marker_id": self.stable_marker_id,
            "guard_marker_id": self.guard_marker_id,
            "origin": self.origin.value,
            "source_role": self.source_role,
            "item_id": self.item_id,
            "sequence": self.sequence,
            "body_element_index": self.body_element_index,
            "document_order": self.document_order,
            "reserved_docpr_id": self.reserved_docpr_id,
            "source_sha256": self.source_sha256,
            "watermark_text_sha256": self.watermark_text_sha256,
            "watermark_font_sha256": self.watermark_font_sha256,
        }


@dataclass(frozen=True, slots=True)
class ImagePlanReceipt:
    """Evidence for the anchor-planning step, not a delivery identity.

    This receipt intentionally has no variant id, staged-DOCX hash, or
    ``DeliveryVariantPlan.plan_id``.  Only ``DeliveryVariantPlan`` is the
    canonical identity of a variant after the marker mutations are saved and
    the staged DOCX is hashed.
    """

    snapshot_id: str
    receipt_id: str
    entries: tuple[ImagePlanReceiptEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "receipt_id": self.receipt_id,
            "entries": [item.to_dict() for item in self.entries],
        }


@dataclass(frozen=True, slots=True)
class ImagePlanBuildResult:
    """Resolved jobs plus step evidence awaiting DeliveryVariantPlan wrapping."""

    plans: tuple[ResolvedImageInsertionPlan, ...]
    receipt: ImagePlanReceipt


@dataclass(frozen=True, slots=True)
class ImagePlanPreflight:
    diagnostics: tuple[ImagePlanDiagnostic, ...]
    planned_job_count: int

    @property
    def ready(self) -> bool:
        return not any(
            item.severity is ImagePlanSeverity.ERROR for item in self.diagnostics
        )


@dataclass(frozen=True, slots=True)
class _MarkerReservation:
    name: str
    bookmark_id: int


@dataclass(frozen=True, slots=True)
class _AnchorMutation:
    paragraph: object
    primary_marker: _MarkerReservation
    additional_markers: tuple[_MarkerReservation, ...]
    guard_paragraph: object | None
    guard_marker: _MarkerReservation | None


@dataclass(frozen=True, slots=True)
class _DraftPlan:
    plan: ResolvedImageInsertionPlan
    item_id: str
    body_element_index: int
    order_sequence: int
    preferred_docpr_id: int | None = None


@dataclass(frozen=True, slots=True)
class _PreparedBuild:
    plans: tuple[ResolvedImageInsertionPlan, ...]
    receipt: ImagePlanReceipt
    mutations: tuple[_AnchorMutation, ...]
    diagnostics: tuple[ImagePlanDiagnostic, ...]


class ImageInsertionPlanBuilder:
    """Perform a read-only preflight followed by one guarded commit pass."""

    def preflight(
        self,
        document: "DocumentType",
        *,
        snapshot_id: str,
        frozen_rules: Sequence[FrozenImageMaterialRule],
        source_bindings: Sequence[ImageSourceBinding],
        content_image_drafts: Sequence[ContentImageJobDraft] = (),
        content_resource_sources: (
            Mapping[ContentResourceKey, ContentResourceImageSource] | None
        ) = None,
        consumer_id: str = "main:source-docx",
    ) -> ImagePlanPreflight:
        prepared = _prepare_build(
            document,
            snapshot_id=snapshot_id,
            frozen_rules=frozen_rules,
            source_bindings=source_bindings,
            content_image_drafts=content_image_drafts,
            content_resource_sources=content_resource_sources or {},
            consumer_id=consumer_id,
        )
        return ImagePlanPreflight(
            diagnostics=prepared.diagnostics,
            planned_job_count=len(prepared.plans),
        )

    def build(
        self,
        document: "DocumentType",
        *,
        snapshot_id: str,
        frozen_rules: Sequence[FrozenImageMaterialRule],
        source_bindings: Sequence[ImageSourceBinding],
        content_image_drafts: Sequence[ContentImageJobDraft] = (),
        content_resource_sources: (
            Mapping[ContentResourceKey, ContentResourceImageSource] | None
        ) = None,
        consumer_id: str = "main:source-docx",
    ) -> ImagePlanBuildResult:
        prepared = _prepare_build(
            document,
            snapshot_id=snapshot_id,
            frozen_rules=frozen_rules,
            source_bindings=source_bindings,
            content_image_drafts=content_image_drafts,
            content_resource_sources=content_resource_sources or {},
            consumer_id=consumer_id,
        )
        errors = [
            item
            for item in prepared.diagnostics
            if item.severity is ImagePlanSeverity.ERROR
        ]
        if errors:
            raise ImagePlanBuildError(errors)
        _commit_mutations(document, prepared.mutations)
        return ImagePlanBuildResult(prepared.plans, prepared.receipt)


def build_image_insertion_plans(
    document: "DocumentType",
    *,
    snapshot_id: str,
    frozen_rules: Sequence[FrozenImageMaterialRule],
    source_bindings: Sequence[ImageSourceBinding],
    content_image_drafts: Sequence[ContentImageJobDraft] = (),
    content_resource_sources: (
        Mapping[ContentResourceKey, ContentResourceImageSource] | None
    ) = None,
    consumer_id: str = "main:source-docx",
) -> ImagePlanBuildResult:
    return ImageInsertionPlanBuilder().build(
        document,
        snapshot_id=snapshot_id,
        frozen_rules=frozen_rules,
        source_bindings=source_bindings,
        content_image_drafts=content_image_drafts,
        content_resource_sources=content_resource_sources,
        consumer_id=consumer_id,
    )


@dataclass(frozen=True, slots=True)
class _UserAnchorSpec:
    rule: FrozenImageMaterialRule
    occurrence_id: str
    paragraph: object
    body_element_index: int
    sources: tuple[ImageSourceBinding, ...]
    guard_paragraph: object | None


@dataclass(slots=True)
class _BuildInputs:
    snapshot_id: object
    consumer_id: str
    rules: tuple[FrozenImageMaterialRule, ...]
    sources: tuple[ImageSourceBinding, ...]
    content_drafts: tuple[ContentImageJobDraft, ...]
    content_resource_sources: Mapping[
        ContentResourceKey,
        ContentResourceImageSource,
    ]
    diagnostics: list[ImagePlanDiagnostic]


def _prepare_build(
    document,
    *,
    snapshot_id,
    frozen_rules,
    source_bindings,
    content_image_drafts,
    content_resource_sources,
    consumer_id,
) -> _PreparedBuild:
    inputs = _validate_build_inputs(
        document,
        snapshot_id=snapshot_id,
        frozen_rules=frozen_rules,
        source_bindings=source_bindings,
        content_image_drafts=content_image_drafts,
        content_resource_sources=content_resource_sources,
        consumer_id=consumer_id,
    )
    sources_by_role, valid_source_ids = _validated_source_state(
        inputs.rules,
        inputs.sources,
        inputs.diagnostics,
    )
    routed, direct_body_blocks = _route_image_token_anchors(
        document,
        inputs.rules,
        consumer_id=inputs.consumer_id,
        diagnostics=inputs.diagnostics,
    )
    user_specs = _collect_user_anchor_specs(
        document,
        inputs.rules,
        sources_by_role=sources_by_role,
        valid_source_ids=valid_source_ids,
        routed=routed,
        direct_body_blocks=direct_body_blocks,
        diagnostics=inputs.diagnostics,
    )
    plan_drafts, mutations, max_docpr_id = _prepare_material_token_plans(
        document,
        snapshot_id=inputs.snapshot_id,
        consumer_id=inputs.consumer_id,
        user_specs=user_specs,
    )
    plan_drafts.extend(
        _prepare_content_resource_plans(
            document,
            snapshot_id=inputs.snapshot_id,
            drafts=inputs.content_drafts,
            sources=inputs.content_resource_sources,
            diagnostics=inputs.diagnostics,
        )
    )
    return _finalize_prepared_build(
        snapshot_id=inputs.snapshot_id,
        plan_drafts=plan_drafts,
        mutations=mutations,
        diagnostics=inputs.diagnostics,
        max_docpr_id=max_docpr_id,
    )


def _validate_build_inputs(
    document,
    *,
    snapshot_id,
    frozen_rules,
    source_bindings,
    content_image_drafts,
    content_resource_sources,
    consumer_id,
) -> _BuildInputs:
    if not isinstance(content_resource_sources, Mapping):
        raise TypeError("content_resource_sources must be a mapping")
    if not hasattr(document, "element") or not hasattr(document.element, "body"):
        raise TypeError("document must be a python-docx Document")
    if not isinstance(consumer_id, str) or not consumer_id.strip():
        raise ValueError("consumer_id must not be empty")
    consumer_id = consumer_id.strip()

    rules = tuple(frozen_rules or ())
    sources = tuple(source_bindings or ())
    content_drafts = tuple(content_image_drafts or ())
    diagnostics: list[ImagePlanDiagnostic] = []
    if not isinstance(snapshot_id, str) or not _SHA256_PATTERN.fullmatch(snapshot_id):
        diagnostics.append(
            _diagnostic(
                "invalid_snapshot_id",
                "snapshot_id must be a lowercase 64-character SHA-256",
            )
        )
    for value in rules:
        if not isinstance(value, FrozenImageMaterialRule):
            raise TypeError(
                "frozen_rules must contain only FrozenImageMaterialRule values"
            )
    for value in sources:
        if not isinstance(value, ImageSourceBinding):
            raise TypeError(
                "source_bindings must contain only ImageSourceBinding values"
            )
    for value in content_drafts:
        if not isinstance(value, ContentImageJobDraft):
            raise TypeError(
                "content_image_drafts must contain only ContentImageJobDraft values"
            )
    for key, value in content_resource_sources.items():
        if not isinstance(key, ContentResourceKey):
            raise TypeError(
                "content resource mapping keys must be ContentResourceKey values"
            )
        if not isinstance(value, ContentResourceImageSource):
            raise TypeError(
                "content resource mapping values must be ContentResourceImageSource"
            )

    return _BuildInputs(
        snapshot_id=snapshot_id,
        consumer_id=consumer_id,
        rules=rules,
        sources=sources,
        content_drafts=content_drafts,
        content_resource_sources=content_resource_sources,
        diagnostics=diagnostics,
    )


def _validated_source_state(
    rules: tuple[FrozenImageMaterialRule, ...],
    sources: tuple[ImageSourceBinding, ...],
    diagnostics: list[ImagePlanDiagnostic],
) -> tuple[dict[str, tuple[ImageSourceBinding, ...]], set[int]]:

    _validate_unique_rule_state(rules, diagnostics)
    _validate_unique_source_state(sources, diagnostics)
    known_roles = {rule.source_role for rule in rules}
    for item in sources:
        if item.role not in known_roles:
            diagnostics.append(
                _diagnostic(
                    "unknown_source_role",
                    f"image item {item.item_id!r} uses undeclared role {item.role!r}",
                    source_role=item.role,
                    item_id=item.item_id,
                )
            )

    valid_source_ids: set[int] = set()
    for item in sources:
        problem = _validate_image_file(item.file_ref, item.file_ref.original_name)
        if problem is None:
            valid_source_ids.add(id(item))
        else:
            code, message = problem
            diagnostics.append(
                _diagnostic(
                    code,
                    message,
                    source_role=item.role,
                    item_id=item.item_id,
                )
            )

    sources_by_role: dict[str, tuple[ImageSourceBinding, ...]] = {}
    for rule in rules:
        selected = tuple(
            sorted(
                (item for item in sources if item.role == rule.source_role),
                key=lambda item: (item.sequence, item.item_id),
            )
        )
        sources_by_role[rule.source_role] = selected
        if rule.required and not selected:
            diagnostics.append(
                _rule_diagnostic(
                    rule,
                    "required_image_source_missing",
                    f"required role {rule.source_role!r} has no selected image",
                )
            )
        if rule.cardinality is ImageCardinality.SINGLE and len(selected) > 1:
            diagnostics.append(
                _rule_diagnostic(
                    rule,
                    "single_image_cardinality_exceeded",
                    f"role {rule.source_role!r} has {len(selected)} images but permits one",
                )
            )
        sequences = [item.sequence for item in selected]
        if len(sequences) != len(set(sequences)):
            diagnostics.append(
                _rule_diagnostic(
                    rule,
                    "duplicate_source_sequence",
                    f"role {rule.source_role!r} has duplicate sequence values",
                )
            )

    return sources_by_role, valid_source_ids


def _route_image_token_anchors(
    document,
    rules: tuple[FrozenImageMaterialRule, ...],
    *,
    consumer_id: str,
    diagnostics: list[ImagePlanDiagnostic],
):

    token_blocks = extract_docx_material_token_blocks(document)
    blocks = token_blocks.blocks
    direct_body_blocks = token_blocks.direct_body_blocks
    declarations = tuple(
        TokenDeclaration(
            token=rule.anchor_token,
            kind=MaterialTokenKind.IMAGE,
            declaration_id=rule.rule_id,
            required=rule.required,
            occurrence_policy=(
                TokenOccurrencePolicy.EXACTLY_ONE
                if rule.occurrence_policy is ImageOccurrencePolicy.EXACTLY_ONE
                else TokenOccurrencePolicy.ALL
            ),
        )
        for rule in rules
    )
    routed = route_material_tokens(
        blocks,
        image_tokens=declarations,
        consumer_id=consumer_id,
    )
    for item in routed.diagnostics:
        if item.severity is TokenDiagnosticSeverity.ERROR:
            diagnostics.append(
                _diagnostic(
                    f"token_{item.code.value}",
                    item.message,
                    anchor_token=item.token,
                    surface=(
                        next(
                            (
                                block.surface
                                for block in blocks
                                if block.block_id == item.block_id
                            ),
                            "",
                        )
                        if item.block_id
                        else ""
                    ),
                )
            )

    return routed, direct_body_blocks


def _collect_user_anchor_specs(
    document,
    rules: tuple[FrozenImageMaterialRule, ...],
    *,
    sources_by_role: Mapping[str, tuple[ImageSourceBinding, ...]],
    valid_source_ids: set[int],
    routed,
    direct_body_blocks: Mapping[str, tuple[object, int]],
    diagnostics: list[ImagePlanDiagnostic],
) -> list[_UserAnchorSpec]:

    user_specs: list[_UserAnchorSpec] = []
    for rule in rules:
        selected = sources_by_role.get(rule.source_role, ())
        route = routed.route_for(rule.anchor_token)
        occurrences = route.occurrences if route is not None else ()
        if selected and not occurrences:
            diagnostics.append(
                _rule_diagnostic(
                    rule,
                    "selected_image_has_no_anchor",
                    f"selected role {rule.source_role!r} has no target token",
                )
            )
        if not selected:
            continue
        usable_sources = tuple(
            item for item in selected if id(item) in valid_source_ids
        )
        if len(usable_sources) != len(selected):
            continue
        for occurrence in occurrences:
            direct = direct_body_blocks.get(occurrence.block_id)
            if direct is None:
                diagnostics.append(
                    _rule_diagnostic(
                        rule,
                        "image_anchor_unsupported_surface",
                        f"image token is on unsupported surface {occurrence.surface!r}",
                        surface=occurrence.surface,
                    )
                )
                continue
            paragraph, body_index = direct
            if not is_strict_material_token_paragraph(
                paragraph,
                rule.anchor_token,
            ):
                diagnostics.append(
                    _rule_diagnostic(
                        rule,
                        "image_anchor_not_isolated",
                        "image token must be the only visible content in a direct body paragraph",
                        surface="body",
                    )
                )
                continue
            if _paragraph_has_section_boundary(paragraph):
                diagnostics.append(
                    _rule_diagnostic(
                        rule,
                        "image_anchor_section_boundary",
                        "image token paragraph must not carry sectPr",
                        surface="body",
                    )
                )
                continue
            guard = None
            if (
                rule.placement.co_location_guard
                is ImageCoLocationGuard.PRECEDING_NONEMPTY_PARAGRAPH
            ):
                guard = _nearest_preceding_nonempty_direct_paragraph(
                    document.element.body, body_index
                )
                if guard is None:
                    diagnostics.append(
                        _rule_diagnostic(
                            rule,
                            "same_page_guard_missing",
                            "strict same-page placement has no preceding non-empty body paragraph",
                        )
                    )
                    continue
                guard_problem = _guard_paragraph_problem(guard)
                if guard_problem is not None:
                    diagnostics.append(
                        _rule_diagnostic(
                            rule,
                            guard_problem[0],
                            guard_problem[1],
                        )
                    )
                    continue
            user_specs.append(
                _UserAnchorSpec(
                    rule=rule,
                    occurrence_id=occurrence.occurrence_id,
                    paragraph=paragraph,
                    body_element_index=body_index,
                    sources=usable_sources,
                    guard_paragraph=guard,
                )
            )

    return user_specs


def _prepare_material_token_plans(
    document,
    *,
    snapshot_id,
    consumer_id: str,
    user_specs: Sequence[_UserAnchorSpec],
) -> tuple[list[_DraftPlan], list[_AnchorMutation], int]:

    existing_names, max_bookmark_id, max_docpr_id = _existing_marker_state(document)
    reserved_names = set(existing_names)
    next_bookmark_id = max_bookmark_id + 1
    plan_drafts: list[_DraftPlan] = []
    mutations: list[_AnchorMutation] = []

    for spec in sorted(
        user_specs,
        key=lambda item: (
            item.body_element_index,
            item.rule.anchor_token,
            item.occurrence_id,
        ),
    ):
        marker_reservations, guard_reservation, next_bookmark_id = (
            _reserve_material_markers(
                spec,
                snapshot_id=snapshot_id,
                consumer_id=consumer_id,
                reserved_names=reserved_names,
                next_bookmark_id=next_bookmark_id,
            )
        )

        if marker_reservations:
            mutations.append(
                _AnchorMutation(
                    paragraph=spec.paragraph,
                    primary_marker=marker_reservations[0],
                    additional_markers=tuple(marker_reservations[1:]),
                    guard_paragraph=spec.guard_paragraph,
                    guard_marker=guard_reservation,
                )
            )
        plan_drafts.extend(
            _material_drafts_for_spec(
                spec,
                marker_reservations=marker_reservations,
                guard_reservation=guard_reservation,
                snapshot_id=snapshot_id,
                consumer_id=consumer_id,
            )
        )

    return plan_drafts, mutations, max_docpr_id


def _reserve_material_markers(
    spec: _UserAnchorSpec,
    *,
    snapshot_id,
    consumer_id: str,
    reserved_names: set[str],
    next_bookmark_id: int,
) -> tuple[list[_MarkerReservation], _MarkerReservation | None, int]:
    marker_reservations: list[_MarkerReservation] = []
    for source in spec.sources:
        salt = _stable_json(
            {
                "snapshot_id": snapshot_id,
                "consumer_id": consumer_id,
                "origin": ImageAnchorOrigin.MATERIAL_TOKEN.value,
                "rule_id": spec.rule.rule_id,
                "occurrence_id": spec.occurrence_id,
                "item_id": source.item_id,
                "sequence": source.sequence,
                "source_sha256": source.file_ref.content_sha256,
            }
        )
        marker_name = _unique_marker_name("LDWordImage", salt, reserved_names)
        reserved_names.add(marker_name)
        marker_reservations.append(
            _MarkerReservation(marker_name, next_bookmark_id)
        )
        next_bookmark_id += 1

    guard_reservation = None
    if spec.guard_paragraph is not None:
        guard_salt = _stable_json(
            {
                "snapshot_id": snapshot_id,
                "consumer_id": consumer_id,
                "origin": "image_guard",
                "rule_id": spec.rule.rule_id,
                "occurrence_id": spec.occurrence_id,
            }
        )
        guard_name = _unique_marker_name("LDWordGuard", guard_salt, reserved_names)
        reserved_names.add(guard_name)
        guard_reservation = _MarkerReservation(guard_name, next_bookmark_id)
        next_bookmark_id += 1
    return marker_reservations, guard_reservation, next_bookmark_id


def _material_drafts_for_spec(
    spec: _UserAnchorSpec,
    *,
    marker_reservations: Sequence[_MarkerReservation],
    guard_reservation: _MarkerReservation | None,
    snapshot_id,
    consumer_id: str,
) -> list[_DraftPlan]:
    drafts: list[_DraftPlan] = []
    for source, marker in zip(spec.sources, marker_reservations):
        job_identity = _stable_json(
            {
                "snapshot_id": snapshot_id,
                "consumer_id": consumer_id,
                "rule_id": spec.rule.rule_id,
                "occurrence_id": spec.occurrence_id,
                "item_id": source.item_id,
                "sequence": source.sequence,
                "marker": marker.name,
            }
        )
        drafts.append(
            _DraftPlan(
                plan=ResolvedImageInsertionPlan(
                    job_id="material-image-"
                    + sha256(job_identity.encode("utf-8")).hexdigest()[:24],
                    image_ref=source.file_ref,
                    anchor=ImageAnchorRef(
                        origin=ImageAnchorOrigin.MATERIAL_TOKEN,
                        stable_marker_id=marker.name,
                        source_token=spec.rule.anchor_token,
                        guard_marker_id=(
                            guard_reservation.name if guard_reservation else ""
                        ),
                    ),
                    occurrence_id=spec.occurrence_id,
                    watermark=spec.rule.watermark,
                    placement=spec.rule.placement,
                    source_role=spec.rule.source_role,
                    sequence=source.sequence,
                ),
                item_id=source.item_id,
                body_element_index=spec.body_element_index,
                order_sequence=source.sequence,
            )
        )
    return drafts


def _finalize_prepared_build(
    *,
    snapshot_id,
    plan_drafts: Sequence[_DraftPlan],
    mutations: Sequence[_AnchorMutation],
    diagnostics: Sequence[ImagePlanDiagnostic],
    max_docpr_id: int,
) -> _PreparedBuild:

    ordered = tuple(
        sorted(
            plan_drafts,
            key=lambda item: (
                item.body_element_index,
                item.order_sequence,
                item.plan.anchor.origin.value,
                item.plan.job_id,
            ),
        )
    )
    plans = tuple(item.plan for item in ordered)
    reserved_docpr_ids = _assign_docpr_ids(ordered, max_docpr_id)
    receipt_entries = tuple(
        ImagePlanReceiptEntry(
            job_id=item.plan.job_id,
            occurrence_id=item.plan.occurrence_id,
            stable_marker_id=item.plan.anchor.stable_marker_id,
            guard_marker_id=item.plan.anchor.guard_marker_id,
            origin=item.plan.anchor.origin,
            source_role=item.plan.source_role,
            item_id=item.item_id,
            sequence=item.plan.sequence if item.plan.sequence is not None else 0,
            body_element_index=item.body_element_index,
            document_order=index,
            reserved_docpr_id=reserved_docpr_ids[index - 1],
            source_sha256=item.plan.image_ref.content_sha256,
            watermark_text_sha256=item.plan.watermark.resolved_text_sha256,
            watermark_font_sha256=item.plan.watermark.resolved_font_sha256,
        )
        for index, item in enumerate(ordered, start=1)
    )
    receipt_payload = {
        "snapshot_id": snapshot_id,
        "entries": [item.to_dict() for item in receipt_entries],
    }
    receipt_id = "image-plan-" + sha256(
        _stable_json(receipt_payload).encode("utf-8")
    ).hexdigest()
    return _PreparedBuild(
        plans=plans,
        receipt=ImagePlanReceipt(snapshot_id, receipt_id, receipt_entries),
        mutations=tuple(mutations),
        diagnostics=tuple(diagnostics),
    )


def _prepare_content_resource_plans(
    document,
    *,
    snapshot_id,
    drafts,
    sources,
    diagnostics,
) -> list[_DraftPlan]:
    result: list[_DraftPlan] = []
    seen_job_ids: set[str] = set()
    seen_markers: set[str] = set()
    resolved_sources: dict[ContentResourceKey, FileAssetRef | None] = {}
    for draft in drafts:
        if not _validate_content_draft_identity(
            draft,
            seen_job_ids=seen_job_ids,
            seen_markers=seen_markers,
            diagnostics=diagnostics,
        ):
            continue
        resolved_source = _resolve_content_image_source(
            draft,
            sources=sources,
            resolved_sources=resolved_sources,
            diagnostics=diagnostics,
        )
        if resolved_source is None:
            continue
        source, image_ref = resolved_source
        marker_state = _resolve_content_marker_state(
            document,
            draft,
            source=source,
            diagnostics=diagnostics,
        )
        if marker_state is None:
            continue
        body_index, guard_marker = marker_state
        result.append(
            _content_resource_draft(
                draft,
                source=source,
                image_ref=image_ref,
                body_index=body_index,
                guard_marker=guard_marker,
            )
        )
    return result


def _validate_content_draft_identity(
    draft: ContentImageJobDraft,
    *,
    seen_job_ids: set[str],
    seen_markers: set[str],
    diagnostics: list[ImagePlanDiagnostic],
) -> bool:
    if (
        not draft.job_id
        or not draft.resource_id
        or not draft.stable_marker_id
        or not draft.occurrence_id
    ):
        diagnostics.append(
            _diagnostic(
                "invalid_content_image_draft",
                "content image draft is missing job, resource, occurrence, or marker identity",
                item_id=draft.resource_id,
            )
        )
        return False
    if (
        isinstance(draft.reserved_docpr_id, bool)
        or not isinstance(draft.reserved_docpr_id, int)
        or draft.reserved_docpr_id <= 0
    ):
        diagnostics.append(
            _diagnostic(
                "invalid_content_docpr_reservation",
                "content image docPr reservation must be a positive integer",
                item_id=draft.resource_id,
            )
        )
        return False
    if draft.job_id in seen_job_ids:
        diagnostics.append(
            _diagnostic(
                "duplicate_content_job_id",
                f"duplicate content image job id {draft.job_id!r}",
                item_id=draft.resource_id,
            )
        )
    seen_job_ids.add(draft.job_id)
    if draft.stable_marker_id in seen_markers:
        diagnostics.append(
            _diagnostic(
                "duplicate_content_marker_id",
                f"duplicate content image marker {draft.stable_marker_id!r}",
                item_id=draft.resource_id,
            )
        )
    seen_markers.add(draft.stable_marker_id)
    if (
        isinstance(draft.sequence, bool)
        or not isinstance(draft.sequence, int)
        or draft.sequence < 0
    ):
        diagnostics.append(
            _diagnostic(
                "invalid_content_image_sequence",
                "content image sequence must be a non-negative integer",
                item_id=draft.resource_id,
            )
        )
        return False
    return True


def _resolve_content_image_source(
    draft: ContentImageJobDraft,
    *,
    sources: Mapping[ContentResourceKey, ContentResourceImageSource],
    resolved_sources: dict[ContentResourceKey, FileAssetRef | None],
    diagnostics: list[ImagePlanDiagnostic],
) -> tuple[ContentResourceImageSource, FileAssetRef] | None:
    resource_key = draft.resource_key
    source = sources.get(resource_key)
    if source is None:
        diagnostics.append(
            _diagnostic(
                "content_resource_source_missing",
                "content image resource "
                f"({draft.content_id!r}, {draft.resource_id!r}) "
                "has no source mapping",
                item_id=draft.resource_id,
            )
        )
        return None
    if resource_key not in resolved_sources:
        image_ref = FileAssetRef(
            source_path=source.source_path,
            original_name=Path(source.resource.resource_id).name,
            media_type=source.resource.media_type,
            content_sha256=source.resource.file.sha256,
            byte_size=source.resource.file.byte_size,
        )
        problem = _validate_image_file(image_ref, source.resource.resource_id)
        if problem is not None:
            diagnostics.append(
                _diagnostic(
                    problem[0],
                    problem[1],
                    source_role=source.source_role,
                    item_id=draft.resource_id,
                )
            )
            resolved_sources[resource_key] = None
        else:
            resolved_sources[resource_key] = image_ref
    resolved = resolved_sources[resource_key]
    return (source, resolved) if resolved is not None else None


def _resolve_content_marker_state(
    document,
    draft: ContentImageJobDraft,
    *,
    source: ContentResourceImageSource,
    diagnostics: list[ImagePlanDiagnostic],
) -> tuple[int, str] | None:
    marker_matches = _bookmark_starts_named(document, draft.stable_marker_id)
    if len(marker_matches) != 1:
        diagnostics.append(
            _diagnostic(
                "content_marker_not_unique",
                f"content marker {draft.stable_marker_id!r} occurs {len(marker_matches)} times",
                item_id=draft.resource_id,
            )
        )
        return None
    marker_paragraph = _direct_body_paragraph(marker_matches[0], document)
    if marker_paragraph is None:
        diagnostics.append(
            _diagnostic(
                "content_marker_unsupported_surface",
                "content image marker must be in a direct body paragraph",
                item_id=draft.resource_id,
            )
        )
        return None
    if not _is_hidden_marker_sentinel(
        marker_paragraph,
        draft.stable_marker_id,
        marker_matches[0],
    ):
        diagnostics.append(
            _diagnostic(
                "content_marker_not_sentinel",
                "content image marker paragraph is not the frozen hidden sentinel",
                item_id=draft.resource_id,
            )
        )
        return None
    body_index = list(document.element.body).index(marker_paragraph)
    guard_marker = ""
    if source.placement.mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE:
        guard_marker = source.guard_marker_id
        if not _content_guard_is_valid(
            document,
            guard_marker,
            body_index=body_index,
            item_id=draft.resource_id,
            diagnostics=diagnostics,
        ):
            return None
    return body_index, guard_marker


def _content_guard_is_valid(
    document,
    guard_marker: str,
    *,
    body_index: int,
    item_id: str,
    diagnostics: list[ImagePlanDiagnostic],
) -> bool:
    guard_matches = _bookmark_starts_named(document, guard_marker)
    if len(guard_matches) != 1:
        diagnostics.append(
            _diagnostic(
                "content_guard_not_unique",
                f"content guard {guard_marker!r} occurs {len(guard_matches)} times",
                item_id=item_id,
            )
        )
        return False
    guard_paragraph = _direct_body_paragraph(guard_matches[0], document)
    if guard_paragraph is None:
        diagnostics.append(
            _diagnostic(
                "content_guard_unsupported_surface",
                "content guard must be in a direct body paragraph",
                item_id=item_id,
            )
        )
        return False
    guard_index = list(document.element.body).index(guard_paragraph)
    if guard_index >= body_index:
        diagnostics.append(
            _diagnostic(
                "content_guard_not_preceding",
                "content guard must precede its image sentinel",
                item_id=item_id,
            )
        )
        return False
    guard_problem = _guard_paragraph_problem(guard_paragraph)
    if guard_problem is not None:
        diagnostics.append(
            _diagnostic(guard_problem[0], guard_problem[1], item_id=item_id)
        )
        return False
    return True


def _content_resource_draft(
    draft: ContentImageJobDraft,
    *,
    source: ContentResourceImageSource,
    image_ref: FileAssetRef,
    body_index: int,
    guard_marker: str,
) -> _DraftPlan:
    return _DraftPlan(
        plan=ResolvedImageInsertionPlan(
            job_id=draft.job_id,
            image_ref=image_ref,
            anchor=ImageAnchorRef(
                origin=ImageAnchorOrigin.CONTENT_RESOURCE,
                stable_marker_id=draft.stable_marker_id,
                source_token="",
                guard_marker_id=guard_marker,
            ),
            occurrence_id=draft.occurrence_id,
            watermark=source.watermark,
            placement=source.placement,
            source_role=source.source_role,
            sequence=draft.sequence,
        ),
        item_id=draft.resource_id,
        body_element_index=body_index,
        order_sequence=draft.sequence,
        preferred_docpr_id=draft.reserved_docpr_id,
    )


def _assign_docpr_ids(
    ordered: Sequence[_DraftPlan], max_existing_docpr_id: int
) -> tuple[int, ...]:
    """Preserve safe M3 reservations and deterministically remap conflicts."""

    preferred = [
        item.preferred_docpr_id
        for item in ordered
        if item.preferred_docpr_id is not None
    ]
    next_id = max([max_existing_docpr_id, *preferred], default=0) + 1
    used: set[int] = set()
    assigned: list[int] = []
    for item in ordered:
        candidate = item.preferred_docpr_id
        if (
            candidate is None
            or candidate <= max_existing_docpr_id
            or candidate in used
        ):
            while next_id in used:
                next_id += 1
            candidate = next_id
            next_id += 1
        used.add(candidate)
        assigned.append(candidate)
    return tuple(assigned)


def _validate_unique_rule_state(rules, diagnostics) -> None:
    for field_name, code in (
        ("rule_id", "duplicate_rule_id"),
        ("anchor_token", "duplicate_rule_anchor_token"),
        ("source_role", "duplicate_rule_source_role"),
    ):
        grouped: dict[str, list[FrozenImageMaterialRule]] = {}
        for rule in rules:
            grouped.setdefault(getattr(rule, field_name), []).append(rule)
        for value, duplicates in grouped.items():
            if len(duplicates) > 1:
                diagnostics.append(
                    _diagnostic(
                        code,
                        f"{field_name} {value!r} is declared {len(duplicates)} times",
                        rule_id=duplicates[0].rule_id,
                        source_role=duplicates[0].source_role,
                        anchor_token=duplicates[0].anchor_token,
                    )
                )


def _validate_unique_source_state(sources, diagnostics) -> None:
    grouped: dict[str, list[ImageSourceBinding]] = {}
    for item in sources:
        grouped.setdefault(item.item_id, []).append(item)
    for item_id, duplicates in grouped.items():
        if len(duplicates) > 1:
            diagnostics.append(
                _diagnostic(
                    "duplicate_source_item_id",
                    f"source item id {item_id!r} is not unique",
                    item_id=item_id,
                )
            )


def _validate_image_file(
    image_ref: FileAssetRef, declared_name: str
) -> tuple[str, str] | None:
    source = Path(image_ref.source_path)
    if not source.is_file():
        return "image_source_missing", f"image source does not exist: {source}"
    source_suffix = source.suffix.casefold()
    declared_suffix = Path(declared_name).suffix.casefold()
    if source_suffix in _OFFICE_OR_DOCUMENT_EXTENSIONS or (
        declared_suffix in _OFFICE_OR_DOCUMENT_EXTENSIONS
    ):
        return (
            "non_image_file_pollution",
            f"document/spreadsheet file is not permitted in image sources: {source.name}",
        )
    stat_before = source.stat()
    if stat_before.st_size != image_ref.byte_size:
        return (
            "image_source_size_mismatch",
            f"image source size changed for {source.name}",
        )
    digest_before = _sha256_file(source)
    if digest_before != image_ref.content_sha256:
        return (
            "image_source_hash_mismatch",
            f"image source hash changed for {source.name}",
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as probe:
                detected_format = str(probe.format or "").upper()
                dimensions = probe.size
                probe.verify()
            with Image.open(source) as opened:
                opened.load()
                if opened.size != dimensions or min(opened.size) <= 0:
                    return (
                        "invalid_image_dimensions",
                        f"image dimensions are invalid for {source.name}",
                    )
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return (
            "image_decompression_bomb",
            f"image dimensions exceed Pillow safety limits: {source.name}",
        )
    except (OSError, ValueError, UnidentifiedImageError):
        return (
            "unreadable_image_bytes",
            f"file bytes are not a supported raster image: {source.name}",
        )
    format_contract = _SUPPORTED_IMAGE_FORMATS.get(detected_format)
    if format_contract is None:
        return (
            "unsupported_image_format",
            f"unsupported raster format {detected_format or '<unknown>'}: {source.name}",
        )
    expected_media_type, valid_extensions = format_contract
    if image_ref.media_type.casefold() != expected_media_type:
        return (
            "image_mime_mismatch",
            f"declared MIME {image_ref.media_type!r} does not match {expected_media_type}",
        )
    if declared_suffix not in valid_extensions:
        return (
            "image_extension_mismatch",
            f"declared image extension {declared_suffix or '<none>'!r} does not match {detected_format}",
        )
    if source_suffix not in valid_extensions:
        return (
            "image_source_extension_mismatch",
            f"source extension {source_suffix or '<none>'!r} does not match {detected_format}",
        )
    stat_after = source.stat()
    digest_after = _sha256_file(source)
    if (
        stat_after.st_size != stat_before.st_size
        or stat_after.st_mtime_ns != stat_before.st_mtime_ns
        or digest_after != digest_before
    ):
        return (
            "image_source_mutated_during_preflight",
            f"image source changed during validation: {source.name}",
        )
    return None


def _paragraph_text(paragraph) -> str:
    return "".join(paragraph_text_fragments(paragraph))


def _paragraph_has_section_boundary(paragraph) -> bool:
    ppr = paragraph.find(qn("w:pPr"))
    return ppr is not None and ppr.find(qn("w:sectPr")) is not None


def _nearest_preceding_nonempty_direct_paragraph(body, body_index):
    for element in reversed(list(body)[:body_index]):
        if element.tag == qn("w:p") and _paragraph_text(element).strip():
            return element
    return None


def _guard_paragraph_problem(paragraph) -> tuple[str, str] | None:
    if not _paragraph_text(paragraph).strip():
        return (
            "same_page_guard_empty",
            "same-page guard paragraph must contain visible text",
        )
    if _paragraph_has_section_boundary(paragraph):
        return (
            "same_page_guard_section_boundary",
            "same-page guard paragraph must not carry sectPr",
        )
    if any(True for _ in paragraph.iter(qn("w:drawing"))):
        return (
            "same_page_guard_contains_drawing",
            "same-page guard paragraph must be text-only",
        )
    if "{{" in _paragraph_text(paragraph) or "}}" in _paragraph_text(paragraph):
        return (
            "same_page_guard_contains_token",
            "same-page guard paragraph must not be another material token",
        )
    ppr = paragraph.find(qn("w:pPr"))
    if ppr is not None and ppr.find(qn("w:pageBreakBefore")) is not None:
        return (
            "same_page_guard_explicit_page_break",
            "same-page guard paragraph must not force a page break",
        )
    for page_break in paragraph.iter(qn("w:br")):
        if page_break.get(qn("w:type"), "") == "page":
            return (
                "same_page_guard_explicit_page_break",
                "same-page guard paragraph must not contain a page break",
            )
    if any(True for _ in paragraph.iter(qn("w:lastRenderedPageBreak"))):
        return (
            "same_page_guard_rendered_page_boundary",
            "same-page guard paragraph crosses a rendered page boundary",
        )
    return None


def _existing_marker_state(document):
    names: set[str] = set()
    max_bookmark_id = 0
    max_docpr_id = 0
    for part in document.part.package.parts:
        root = getattr(part, "_element", None)
        if root is None:
            continue
        for bookmark in root.iter(qn("w:bookmarkStart")):
            name = bookmark.get(qn("w:name"))
            if name:
                names.add(name)
            max_bookmark_id = max(
                max_bookmark_id, _safe_int(bookmark.get(qn("w:id")))
            )
        for docpr in root.iter(qn("wp:docPr")):
            max_docpr_id = max(max_docpr_id, _safe_int(docpr.get("id")))
    return names, max_bookmark_id, max_docpr_id


def _bookmark_starts_named(document, marker_name: str) -> tuple[object, ...]:
    matches: list[object] = []
    for part in document.part.package.parts:
        root = getattr(part, "_element", None)
        if root is None:
            continue
        matches.extend(
            item
            for item in root.iter(qn("w:bookmarkStart"))
            if item.get(qn("w:name")) == marker_name
        )
    return tuple(matches)


def _direct_body_paragraph(element, document):
    current = element
    while current is not None and current.tag != qn("w:p"):
        current = current.getparent()
    if current is None or current.getparent() is not document.element.body:
        return None
    return current


def _is_hidden_marker_sentinel(paragraph, marker_name, bookmark_start) -> bool:
    bookmark_id = bookmark_start.get(qn("w:id"))
    direct_starts = [item for item in paragraph if item.tag == qn("w:bookmarkStart")]
    direct_ends = [item for item in paragraph if item.tag == qn("w:bookmarkEnd")]
    if direct_starts != [bookmark_start] or len(direct_ends) != 1:
        return False
    if direct_ends[0].get(qn("w:id")) != bookmark_id:
        return False
    if _paragraph_text(paragraph) != marker_name:
        return False
    direct_runs = [item for item in paragraph if item.tag == qn("w:r")]
    if len(direct_runs) != 1:
        return False
    for child in paragraph:
        if child.tag not in {
            qn("w:pPr"),
            qn("w:bookmarkStart"),
            qn("w:r"),
            qn("w:bookmarkEnd"),
        }:
            return False
    hidden_runs: list[bool] = []
    for run in direct_runs:
        if any(
            child.tag not in {qn("w:rPr"), qn("w:t")} for child in run
        ):
            return False
        rpr = run.find(qn("w:rPr"))
        hidden_runs.append(
            rpr is not None
            and rpr.find(qn("w:vanish")) is not None
            and rpr.find(qn("w:noProof")) is not None
        )
    return hidden_runs == [True]


def _unique_marker_name(prefix: str, salt: str, existing: set[str]) -> str:
    attempt = 0
    while True:
        digest = sha256(f"{salt}:{attempt}".encode("utf-8")).hexdigest()
        marker = f"{prefix}_{digest[:24]}"
        if marker not in existing:
            return marker
        attempt += 1


def _commit_mutations(document, mutations: Sequence[_AnchorMutation]) -> None:
    if not mutations:
        return
    root = document.element
    backup_body = deepcopy(root.body)
    try:
        for mutation in mutations:
            if mutation.guard_paragraph is not None:
                if mutation.guard_marker is None:
                    raise RuntimeError("guard paragraph has no reserved marker")
                _wrap_paragraph_with_bookmark(
                    mutation.guard_paragraph, mutation.guard_marker
                )
            _replace_paragraph_with_sentinel(
                mutation.paragraph, mutation.primary_marker
            )
            parent = mutation.paragraph.getparent()
            insert_at = parent.index(mutation.paragraph) + 1
            for marker in mutation.additional_markers:
                parent.insert(insert_at, _sentinel_paragraph(marker))
                insert_at += 1
    except Exception:
        root.replace(root.body, backup_body)
        raise


def _replace_paragraph_with_sentinel(paragraph, marker: _MarkerReservation) -> None:
    for child in tuple(paragraph):
        if child.tag != qn("w:pPr"):
            paragraph.remove(child)
    for child in _sentinel_children(marker):
        paragraph.append(child)


def _sentinel_paragraph(marker: _MarkerReservation):
    paragraph = OxmlElement("w:p")
    for child in _sentinel_children(marker):
        paragraph.append(child)
    return paragraph


def _sentinel_children(marker: _MarkerReservation) -> tuple[object, ...]:
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(marker.bookmark_id))
    start.set(qn("w:name"), marker.name)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rpr.append(OxmlElement("w:vanish"))
    rpr.append(OxmlElement("w:noProof"))
    run.append(rpr)
    text = OxmlElement("w:t")
    text.text = marker.name
    run.append(text)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(marker.bookmark_id))
    return start, run, end


def _wrap_paragraph_with_bookmark(
    paragraph, marker: _MarkerReservation
) -> None:
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(marker.bookmark_id))
    start.set(qn("w:name"), marker.name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(marker.bookmark_id))
    insert_at = 1 if len(paragraph) and paragraph[0].tag == qn("w:pPr") else 0
    paragraph.insert(insert_at, start)
    paragraph.append(end)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_json(payload: object) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _diagnostic(
    code,
    message,
    *,
    rule_id="",
    source_role="",
    anchor_token="",
    item_id="",
    surface="",
):
    return ImagePlanDiagnostic(
        severity=ImagePlanSeverity.ERROR,
        code=str(code),
        message=str(message),
        rule_id=str(rule_id),
        source_role=str(source_role),
        anchor_token=str(anchor_token),
        item_id=str(item_id),
        surface=str(surface),
    )


def _rule_diagnostic(rule, code, message, *, surface=""):
    return _diagnostic(
        code,
        message,
        rule_id=rule.rule_id,
        source_role=rule.source_role,
        anchor_token=rule.anchor_token,
        surface=surface,
    )


__all__ = [
    "ContentResourceImageSource",
    "ImageInsertionPlanBuilder",
    "ImagePlanBuildError",
    "ImagePlanBuildResult",
    "ImagePlanDiagnostic",
    "ImagePlanPreflight",
    "ImagePlanReceipt",
    "ImagePlanReceiptEntry",
    "ImagePlanSeverity",
    "ImageSourceItem",
    "build_image_insertion_plans",
]
