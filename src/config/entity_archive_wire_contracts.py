"""Declarative JSON contracts for the current generic material package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EntityProfileWirePayload:
    profile_id: str
    profile_name: str
    fields: dict[str, str]
    assets_dir: str
    field_scopes: dict[str, str]
    field_functions: dict[str, dict[str, str]]
    timeline_plans: dict[str, dict[str, Any]]
    declared_field_keys: list[str]
    field_sources: dict[str, str]
    field_aliases: dict[str, str]
    asset_paths: dict[str, str]
    asset_bindings: dict[str, dict[str, Any]]
    asset_metadata: dict[str, dict[str, str]]
    asset_token_specs: list[dict[str, Any]]
    asset_items: list[dict[str, Any]]
    asset_item_history: list[dict[str, Any]]
    image_material_rules: dict[str, dict[str, Any]]
    content_bindings: dict[str, dict[str, Any]]
    content_rules: list[dict[str, Any]]
    attachment_role_specs: list[dict[str, Any]]
    attachment_bindings: dict[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class EntityArchiveWirePayload:
    kind: str
    version: int
    mode_id: str
    package_id: str
    material_schema_ids: list[str]
    archive_id: str
    archive_name: str
    profiles: list[EntityProfileWirePayload]


@dataclass(frozen=True, slots=True)
class AssetBindingWire:
    role: str
    cardinality: str
    source_kind: str
    source_path: str
    recursive: bool
    order_policy: str
    naming_template: str
    min_items: int
    max_items: int | None
    items: list[dict[str, Any]]
    snapshot_revision: str


@dataclass(frozen=True, slots=True)
class AssetTokenSpecWire:
    token_id: str
    token: str
    label: str
    cardinality: str
    source_kind: str
    order: int
    required: bool
    recursive: bool
    min_items: int
    max_items: int | None
    order_policy: str
    naming_template: str


@dataclass(frozen=True, slots=True)
class ImageWatermarkWire:
    enabled: bool
    text_source: str
    text_template: str
    style_version: str


@dataclass(frozen=True, slots=True)
class ImagePlacementWire:
    mode: str
    contain: bool
    allow_crop: bool
    allow_move_preceding_text: bool
    allow_page_break: bool
    fixed_width_cm: float | None
    max_width_cm: float | None
    co_location_guard: str


@dataclass(frozen=True, slots=True)
class ImageMaterialRuleWire:
    rule_id: str
    source_role: str
    anchor_token: str
    required: bool
    occurrence_policy: str
    cardinality: str
    placement: ImagePlacementWire
    watermark: ImageWatermarkWire


@dataclass(frozen=True, slots=True)
class ContentArtifactRefWire:
    artifact_id: str
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class ContentMaterialBindingWire:
    content_id: str
    label: str
    artifact_ref: ContentArtifactRefWire


@dataclass(frozen=True, slots=True)
class ContentInsertionRuleWire:
    rule_id: str
    content_id: str
    anchor_token: str
    required: bool
    occurrence_policy: str
    heading_policy: str
    heading_level_offset: int
    page_break_policy: str


@dataclass(frozen=True, slots=True)
class FileAssetRefWire:
    source_path: str
    original_name: str
    media_type: str
    content_sha256: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class AttachmentRoleSpecWire:
    role: str
    label: str
    accepted_types: list[str]
    required: bool
    cardinality: str
    source_kind: str
    recursive: bool
    processing_mode: str
    min_items: int
    max_items: int | None
    origin: str


@dataclass(frozen=True, slots=True)
class AttachmentItemWire:
    item_id: str
    file_ref: FileAssetRefWire
    label: str
    sequence: int
    relative_path: str


@dataclass(frozen=True, slots=True)
class AttachmentBindingWire:
    role: str
    label: str
    source_kind: str
    source_path: str
    recursive: bool
    processing_mode: str
    cardinality: str
    items: list[AttachmentItemWire]
    required: bool
    min_items: int
    max_items: int | None
    accepted_media_types: list[str]
    accepted_extensions: list[str]
    binding_revision: str


ASSET_ITEM_REQUIRED_FIELDS = frozenset({"item_id", "role", "path"})
ASSET_ITEM_FIELD_TYPES: dict[str, object] = {
    "item_id": str,
    "label": str,
    "role": str,
    "path": str,
    "mime_type": str,
    "tags": list[str],
    "width_cm": float,
    "metadata": dict[str, str],
    "group_id": str,
    "sequence": int,
    "source_path": str,
    "original_relative_path": str,
    "normalized_name": str,
    "content_hash": str,
}

HISTORY_ALLOWED_FIELDS = frozenset(
    {
        "schema_version",
        "action",
        "changed_at",
        "role",
        "item_id",
        "target_label",
        "question_index",
        "changed_fields",
        "source_before",
        "source_after",
        "asset_id_before",
        "asset_id_after",
        "alt_text_before",
        "alt_text_after",
        "rollback_from_changed_at",
        "change_summary",
    }
)

TIMELINE_PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "label",
        "enabled",
        "deleted",
        "number_state",
        "token_copied",
        "retired_outputs",
        "segment_no",
        "start_value",
        "end_value",
        "output_format",
        "format_mode",
        "input_scope",
        "start_field",
        "end_field",
        "rounding",
        "calendar",
        "constraints",
        "nodes",
        "overrides",
        "preset",
    }
)
