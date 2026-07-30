"""Execution-time material context for entity fields and assets."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from src.config.attachment_materials import AttachmentBinding
from src.config.content_artifacts import ContentMaterialBinding
from src.config.content_materials import ContentInsertionRule
from src.config.entity import EntityProfile
from src.config.image_materials import ImageMaterialRule
from src.config.materials import (
    AssetInsertionRule,
    AssetItem,
    build_image_insertions,
    missing_required_asset_roles,
    normalize_asset_role,
)
from src.config.asset_resolution import asset_item_from_payload
from src.config.resolved import ImageInsertionItem
from src.shared.engine.material_field_function import (
    normalize_field_functions,
    resolve_field_functions,
)
from src.shared.engine.material_timeline import (
    TimelineIssue,
    normalize_timeline_plans,
    resolve_timeline_plans,
    timeline_owned_field_keys,
    timeline_output_field_keys,
)


@dataclass(frozen=True, slots=True)
class MaterialFieldResolution:
    """One execution snapshot plus structured calculation diagnostics."""

    values: dict[str, str]
    function_errors: dict[str, str] = field(default_factory=dict)
    timeline_issues: tuple[TimelineIssue, ...] = ()


@dataclass(slots=True)
class MaterialExecutionContext:
    """Runtime payload produced by material/quick-fill UI for one execution."""

    mode_id: str = ""
    scene_id: str = ""
    package_id: str = ""
    material_schema_ids: tuple[str, ...] = ()
    compatible_profile_ids: tuple[str, ...] = ()
    compatible_master_families: tuple[str, ...] = ()
    archive_id: str = ""
    archive_name: str = ""
    profile_id: str = ""
    profile_name: str = ""
    entity_data: dict[str, str] = field(default_factory=dict)
    frozen_field_values: dict[str, str] = field(default_factory=dict)
    field_values_frozen: bool = False
    field_scopes: dict[str, str] = field(default_factory=dict)
    field_functions: dict[str, dict[str, str]] = field(default_factory=dict)
    timeline_plans: dict[str, dict[str, object]] = field(default_factory=dict)
    field_aliases: dict[str, str] = field(default_factory=dict)
    entity_assets_dir: str = ""
    images: list[ImageInsertionItem] = field(default_factory=list)
    asset_items: list[AssetItem] = field(default_factory=list)
    asset_diagnostics: list[dict[str, object]] = field(default_factory=list)
    image_rules: list[AssetInsertionRule] = field(default_factory=list)
    image_material_rules: dict[str, ImageMaterialRule] = field(default_factory=dict)
    image_watermark_text: str = ""
    content_bindings: dict[str, ContentMaterialBinding] = field(default_factory=dict)
    content_rules: list[ContentInsertionRule] = field(default_factory=list)
    attachment_bindings: dict[str, AttachmentBinding] = field(default_factory=dict)
    exact_material_placeholders: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.field_values_frozen, bool):
            raise TypeError("field_values_frozen must be a boolean")
        if self.frozen_field_values and not self.field_values_frozen:
            raise ValueError(
                "frozen_field_values require field_values_frozen=True"
            )
        if not isinstance(self.image_watermark_text, str):
            raise TypeError("image_watermark_text must be a string")
        self.images = _normalize_image_items(self.images)
        self.asset_items = _normalize_asset_items(self.asset_items)
        self.image_rules = _normalize_asset_insertion_rules(self.image_rules)
        self.image_material_rules = _normalize_image_material_rules(
            self.image_material_rules
        )
        self.content_bindings = _normalize_content_bindings(self.content_bindings)
        self.content_rules = _normalize_content_rules(self.content_rules)
        self.attachment_bindings = _normalize_attachment_bindings(
            self.attachment_bindings
        )
        _validate_image_material_ownership(self)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None) -> "MaterialExecutionContext":
        if payload is None:
            return cls()

        entity_data = payload.get("entity_data", {})
        if not isinstance(entity_data, Mapping):
            entity_data = {}

        return cls(
            mode_id=str(payload.get("mode_id", "") or ""),
            scene_id=str(payload.get("scene_id", "") or ""),
            package_id=str(payload.get("package_id", "") or ""),
            material_schema_ids=_normalize_text_sequence(
                payload.get("material_schema_ids", ())
            ),
            compatible_profile_ids=_normalize_text_sequence(
                payload.get("compatible_profile_ids", ())
            ),
            compatible_master_families=_normalize_text_sequence(
                payload.get("compatible_master_families", ())
            ),
            archive_id=str(payload.get("archive_id", "") or ""),
            archive_name=str(payload.get("archive_name", "") or ""),
            profile_id=str(payload.get("profile_id", "") or ""),
            profile_name=str(payload.get("profile_name", "") or ""),
            entity_data={
                str(key): str(value)
                for key, value in entity_data.items()
                if str(key or "").strip()
            },
            frozen_field_values=_normalize_text_value_mapping(
                payload.get("frozen_field_values", {})
            ),
            field_values_frozen=bool(payload.get("field_values_frozen", False)),
            field_scopes=_normalize_text_mapping(payload.get("field_scopes", {})),
            field_functions=normalize_field_functions(
                payload.get("field_functions", {})
            ),
            timeline_plans=normalize_timeline_plans(payload.get("timeline_plans", {})),
            field_aliases=_normalize_text_mapping(payload.get("field_aliases", {})),
            exact_material_placeholders=bool(
                payload.get("exact_material_placeholders", False)
            ),
            entity_assets_dir=str(payload.get("entity_assets_dir", "") or ""),
            images=_normalize_image_items(payload.get("images", [])),
            asset_items=_normalize_asset_items(payload.get("asset_items", [])),
            asset_diagnostics=_normalize_mapping_sequence(
                payload.get("asset_diagnostics", [])
            ),
            image_rules=_normalize_asset_insertion_rules(payload.get("image_rules", [])),
            image_material_rules=_normalize_image_material_rules(
                payload.get("image_material_rules", {})
            ),
            image_watermark_text=str(payload.get("image_watermark_text", "") or ""),
            content_bindings=_normalize_content_bindings(
                payload.get("content_bindings", {})
            ),
            content_rules=_normalize_content_rules(payload.get("content_rules", [])),
            attachment_bindings=_normalize_attachment_bindings(
                payload.get("attachment_bindings", {})
            ),
        )

    def clone(self) -> "MaterialExecutionContext":
        return MaterialExecutionContext(
            mode_id=self.mode_id,
            scene_id=self.scene_id,
            package_id=self.package_id,
            material_schema_ids=tuple(self.material_schema_ids),
            compatible_profile_ids=tuple(self.compatible_profile_ids),
            compatible_master_families=tuple(self.compatible_master_families),
            archive_id=self.archive_id,
            archive_name=self.archive_name,
            profile_id=self.profile_id,
            profile_name=self.profile_name,
            entity_data=dict(self.entity_data),
            frozen_field_values=dict(self.frozen_field_values),
            field_values_frozen=self.field_values_frozen,
            field_scopes=dict(self.field_scopes),
            field_functions=copy.deepcopy(self.field_functions),
            timeline_plans=copy.deepcopy(self.timeline_plans),
            field_aliases=dict(self.field_aliases),
            exact_material_placeholders=self.exact_material_placeholders,
            entity_assets_dir=self.entity_assets_dir,
            images=copy.deepcopy(self.images),
            asset_items=copy.deepcopy(self.asset_items),
            asset_diagnostics=copy.deepcopy(self.asset_diagnostics),
            image_rules=copy.deepcopy(self.image_rules),
            image_material_rules=copy.deepcopy(self.image_material_rules),
            image_watermark_text=self.image_watermark_text,
            content_bindings=copy.deepcopy(self.content_bindings),
            content_rules=copy.deepcopy(self.content_rules),
            attachment_bindings=copy.deepcopy(self.attachment_bindings),
        )

    def to_payload(self) -> dict[str, object]:
        """Return the complete JSON-compatible execution payload."""

        return _material_payload_value(asdict(self))

    def is_empty(self) -> bool:
        return not (
            self.mode_id
            or self.scene_id
            or self.package_id
            or self.material_schema_ids
            or self.compatible_profile_ids
            or self.compatible_master_families
            or self.archive_id
            or self.archive_name
            or self.profile_id
            or self.profile_name
            or self.entity_data
            or self.frozen_field_values
            or self.field_values_frozen
            or self.field_scopes
            or self.field_functions
            or self.timeline_plans
            or self.field_aliases
            or self.entity_assets_dir
            or self.images
            or self.asset_items
            or self.asset_diagnostics
            or self.image_rules
            or self.image_material_rules
            or self.image_watermark_text
            or self.content_bindings
            or self.content_rules
            or self.attachment_bindings
        )

    def resolved_mode_id(self) -> str:
        """Return the explicit or safely inferable work-mode scope."""

        explicit = str(self.mode_id or "").strip()
        if explicit:
            return explicit
        profile_id = str(self.profile_id or "").strip()
        if profile_id.startswith("official:"):
            return "official"
        return ""

    def is_compatible_with(self, *, mode_id: str, scene_id: str = "") -> bool:
        """Whether this context may be injected into the requested resource scope."""

        target_mode = str(mode_id or "").strip()
        context_mode = self.resolved_mode_id()
        if context_mode and target_mode and context_mode != target_mode:
            return False
        target_scene = str(scene_id or "").strip()
        context_scene = str(self.scene_id or "").strip()
        if context_scene and target_scene and context_scene != target_scene:
            return False
        return True

    def to_resolve_kwargs(self) -> dict[str, object]:
        # A request owns exactly one image-execution domain.  Revalidate here
        # as a defensive guard against adapters mutating the typed context.
        _validate_image_material_ownership(self)
        images = [
            *copy.deepcopy(self.images),
            *build_image_insertions(self.asset_items, self.image_rules),
        ]
        return {
            "entity_data": self.resolved_entity_data(),
            "field_scopes": dict(self.field_scopes),
            "field_aliases": dict(self.field_aliases),
            "timeline_field_keys": timeline_owned_field_keys(
                self.timeline_plans,
                include_inactive=True,
            ),
            "exact_material_placeholders": self.exact_material_placeholders,
            "entity_assets_dir": self.entity_assets_dir,
            "images": images,
        }

    def resolved_entity_data(self, *, now=None) -> dict[str, str]:
        """Return one safely calculated field snapshot for execution."""

        return self.resolve_material_fields(now=now).values

    def with_frozen_field_resolution(
        self,
        resolution: MaterialFieldResolution,
    ) -> "MaterialExecutionContext":
        """Return a clone whose downstream reads reuse one resolved value set.

        The original field-function and timeline definitions remain available
        for manifests and diagnostics, but ``resolve_material_fields`` will no
        longer consult clocks or external providers for this execution.
        """

        if not isinstance(resolution, MaterialFieldResolution):
            raise TypeError("resolution must be a MaterialFieldResolution")
        frozen = self.clone()
        frozen.frozen_field_values = {
            str(key): str(value)
            for key, value in resolution.values.items()
            if str(key or "").strip()
        }
        frozen.field_values_frozen = True
        return frozen

    def resolve_material_fields(self, *, now=None) -> MaterialFieldResolution:
        """Resolve realtime functions first, then atomically apply timeline plans."""

        if self.field_values_frozen:
            return MaterialFieldResolution(values=dict(self.frozen_field_values))

        function_resolution = resolve_field_functions(
            self.entity_data,
            self.field_functions,
            now=now,
        )
        timeline_resolution = resolve_timeline_plans(
            function_resolution.values,
            self.timeline_plans,
        )
        ownership_conflicts = sorted(
            set(self.field_functions)
            & set(timeline_output_field_keys(self.timeline_plans))
        )
        timeline_issues = [*timeline_resolution.issues]
        timeline_issues.extend(
            TimelineIssue(
                severity="error",
                code="field_function_conflict",
                plan_id="",
                field=field_key,
                message=f"字段“{field_key}”不能同时使用字段函数和时间计划",
            )
            for field_key in ownership_conflicts
        )
        return MaterialFieldResolution(
            values=dict(timeline_resolution.values),
            function_errors=dict(function_resolution.errors),
            timeline_issues=tuple(timeline_issues),
        )

    def missing_required_asset_roles(self) -> list[str]:
        return missing_required_asset_roles(self.asset_items, self.image_rules)


def _normalize_image_items(items: object) -> list[ImageInsertionItem]:
    normalized: list[ImageInsertionItem] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return normalized

    for item in items:
        if isinstance(item, ImageInsertionItem):
            copied = copy.deepcopy(item)
            copied.role = normalize_asset_role(copied.role)
            normalized.append(copied)
            continue
        if not isinstance(item, Mapping):
            continue

        try:
            width_cm = float(item.get("width_cm", 14.0))
        except (TypeError, ValueError):
            width_cm = 14.0

        normalized.append(
            ImageInsertionItem(
                path=str(item.get("path", "") or ""),
                position=item.get("position", "end"),
                width_cm=width_cm,
                role=normalize_asset_role(item.get("role", "")),
                item_id=str(item.get("item_id", "") or ""),
                group_id=str(item.get("group_id", "") or ""),
                sequence=_optional_int(item.get("sequence")),
                normalized_name=str(item.get("normalized_name", "") or ""),
            )
        )
    return normalized


def _normalize_text_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if str(key or "").strip() and str(item or "").strip()
    }


def _normalize_text_value_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if str(key or "").strip()
    }


def _normalize_text_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(
        dict.fromkeys(
            str(item or "").strip()
            for item in value
            if str(item or "").strip()
        )
    )


def _normalize_mapping_sequence(value: object) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [
        {str(key): copy.deepcopy(item) for key, item in entry.items()}
        for entry in value
        if isinstance(entry, Mapping)
    ]


def _normalize_asset_items(items: object) -> list[AssetItem]:
    normalized: list[AssetItem] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return normalized

    for item in items:
        if isinstance(item, AssetItem):
            copied = copy.deepcopy(item)
            copied.role = normalize_asset_role(copied.role)
            normalized.append(copied)
            continue
        if not isinstance(item, Mapping):
            continue
        normalized.append(asset_item_from_payload(item))
    return normalized


def _normalize_asset_insertion_rules(items: object) -> list[AssetInsertionRule]:
    normalized: list[AssetInsertionRule] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return normalized

    for item in items:
        if isinstance(item, AssetInsertionRule):
            copied = copy.deepcopy(item)
            copied.asset_role = normalize_asset_role(copied.asset_role)
            normalized.append(copied)
            continue
        if not isinstance(item, Mapping):
            continue
        try:
            width_cm = float(item.get("width_cm", 6.0))
        except (TypeError, ValueError):
            width_cm = 6.0
        cardinality = (
            "multiple"
            if str(item.get("cardinality", "single") or "single").strip().lower()
            == "multiple"
            else "single"
        )
        max_default = None if cardinality == "multiple" else 1
        raw_max_items = item.get("max_items", max_default)
        normalized.append(
            AssetInsertionRule(
                rule_id=str(item.get("rule_id", "") or ""),
                asset_role=str(item.get("asset_role", "") or ""),
                target=str(item.get("target", "end") or "end"),
                width_cm=width_cm,
                required=bool(item.get("required", True)),
                cardinality=cardinality,
                min_items=max(0, _optional_int(item.get("min_items")) or 0),
                max_items=_optional_int(raw_max_items),
                occurrence_policy=str(item.get("occurrence_policy", "first") or "first"),
            )
        )
    return normalized


def _normalize_image_material_rules(
    value: object,
) -> dict[str, ImageMaterialRule]:
    """Reuse the EntityProfile v3 contract; do not create execution plans here."""

    normalized_input = dict(value) if isinstance(value, Mapping) else value
    profile = EntityProfile(image_material_rules=normalized_input)
    return copy.deepcopy(profile.image_material_rules)


def _validate_image_material_ownership(context: MaterialExecutionContext) -> None:
    if not context.image_material_rules:
        return
    if context.image_rules or context.images:
        legacy_domains = []
        if context.image_rules:
            legacy_domains.append("image_rules")
        if context.images:
            legacy_domains.append("images")
        raise ValueError(
            "material_image_domain_conflict:" + ",".join(legacy_domains)
        )


def _normalize_content_bindings(
    value: object,
) -> dict[str, ContentMaterialBinding]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, ContentMaterialBinding] = {}
    for raw_key, raw_binding in value.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        if isinstance(raw_binding, ContentMaterialBinding):
            binding = copy.deepcopy(raw_binding)
        elif isinstance(raw_binding, Mapping):
            try:
                binding = ContentMaterialBinding.from_dict(raw_binding)
            except (TypeError, ValueError):
                continue
        else:
            continue
        if binding.content_id != key:
            continue
        normalized[key] = binding
    return normalized


def _normalize_content_rules(value: object) -> list[ContentInsertionRule]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    normalized: list[ContentInsertionRule] = []
    seen: set[str] = set()
    for raw_rule in value:
        if isinstance(raw_rule, ContentInsertionRule):
            rule = copy.deepcopy(raw_rule)
        elif isinstance(raw_rule, Mapping):
            try:
                rule = ContentInsertionRule.from_dict(raw_rule)
            except (TypeError, ValueError):
                continue
        else:
            continue
        if rule.rule_id in seen:
            continue
        seen.add(rule.rule_id)
        normalized.append(rule)
    return normalized


def _normalize_attachment_bindings(
    value: object,
) -> dict[str, AttachmentBinding]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, AttachmentBinding] = {}
    for raw_key, raw_binding in value.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        if isinstance(raw_binding, AttachmentBinding):
            binding = copy.deepcopy(raw_binding)
        elif isinstance(raw_binding, Mapping):
            try:
                binding = AttachmentBinding.from_dict(raw_binding)
            except (TypeError, ValueError):
                continue
        else:
            continue
        if binding.role != key:
            continue
        normalized[key] = binding
    return normalized


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _material_payload_value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _material_payload_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_material_payload_value(item) for item in value]
    return value


__all__ = ["MaterialExecutionContext", "MaterialFieldResolution"]
