"""Typed material entity models and their canonical normalization rules."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Any

from src.config.attachment_materials import (
    AttachmentBinding,
    AttachmentRoleSpec,
)
from src.config.content_artifacts import ContentMaterialBinding
from src.config.content_materials import ContentInsertionRule
from src.config.image_materials import ImageMaterialRule
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    parse_material_token,
)


ENTITY_PACKAGE_VERSION = 5


@dataclass
class AssetBinding:
    """Persisted image-material binding to one file or image directory.

    Non-image attachments and future document content blocks must keep their
    own typed execution contracts instead of entering this image binding.
    """

    role: str = ""
    cardinality: str = "single"
    source_kind: str = "file"
    source_path: str = ""
    recursive: bool = False
    order_policy: str = "natural_path"
    naming_template: str = "{role}_{sequence:03d}"
    min_items: int = 0
    max_items: int | None = 1
    items: list[dict[str, Any]] = field(default_factory=list)
    snapshot_revision: str = ""

@dataclass
class AssetTokenSpec:
    """User-owned image Token definition persisted with one material profile."""

    token_id: str = ""
    token: str = ""
    label: str = ""
    cardinality: str = "single"
    source_kind: str = "file"
    order: int = 0
    required: bool = False
    recursive: bool = False
    min_items: int = 0
    max_items: int | None = 1
    order_policy: str = "natural_path"
    naming_template: str = "{role}_{sequence:03d}"

@dataclass
class EntityProfile:
    """单个实体配置集（如：某公司某角色的一套数据）。"""

    profile_id: str = ""
    profile_name: str = ""          # e.g. "投标人主体"
    fields: dict[str, str] = field(default_factory=dict)
    # 示例 fields:
    # {
    #     "company_name": "中建三局第一建设工程有限公司",
    #     "legal_person": "张三",
    #     "address": "武汉市洪山区xxx路xxx号",
    #     "phone": "027-12345678",
    #     "project_name": "xxx工程",
    #     "bid_date": "2026年3月24日",
    # }

    assets_dir: str = ""            # 关联素材文件夹路径
    field_scopes: dict[str, str] = field(default_factory=dict)  # fixed / floating
    field_functions: dict[str, dict[str, str]] = field(default_factory=dict)
    timeline_plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    declared_field_keys: list[str] = field(default_factory=list)
    field_sources: dict[str, str] = field(default_factory=dict)  # 字段来源，如 imported_mapping
    field_aliases: dict[str, str] = field(default_factory=dict)  # 占位符别名 -> 常用字段
    asset_paths: dict[str, str] = field(default_factory=dict)  # 常用图片材料位，如 logo / seal
    asset_bindings: dict[str, AssetBinding] = field(default_factory=dict)
    asset_metadata: dict[str, dict[str, str]] = field(default_factory=dict)  # 素材角色 -> 元数据
    asset_token_specs: list[AssetTokenSpec] = field(default_factory=list)
    asset_items: list[dict[str, Any]] = field(default_factory=list)  # 可重复素材条目，如逐题题图
    asset_item_history: list[dict[str, Any]] = field(default_factory=list)  # 素材条目治理/版本审计
    image_material_rules: dict[str, ImageMaterialRule] = field(default_factory=dict)
    content_bindings: dict[str, ContentMaterialBinding] = field(default_factory=dict)
    content_rules: list[ContentInsertionRule] = field(default_factory=list)
    attachment_role_specs: list[AttachmentRoleSpec] = field(default_factory=list)
    attachment_bindings: dict[str, AttachmentBinding] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.declared_field_keys = list(
            dict.fromkeys(
                str(key or "").strip()
                for key in (*self.declared_field_keys, *self.fields.keys())
                if str(key or "").strip()
            )
        )
        self.asset_bindings = _normalized_asset_bindings(self.asset_bindings)
        self.asset_token_specs = _normalized_asset_token_specs(self.asset_token_specs)
        self.image_material_rules = _normalized_image_material_rules(
            self.image_material_rules
        )
        self.content_bindings = _normalized_content_bindings(self.content_bindings)
        self.content_rules = _normalized_content_rules(self.content_rules)
        self.attachment_role_specs = _normalized_attachment_role_specs(
            self.attachment_role_specs
        )
        self.attachment_bindings = _normalized_attachment_bindings(
            self.attachment_bindings
        )

def clone_entity_profile(
    profile: EntityProfile,
    **changes: object,
) -> EntityProfile:
    """Deep-copy one profile while preserving every declared profile field.

    UI and batch adapters previously rebuilt ``EntityProfile`` by hand.  That
    makes every newly added material domain vulnerable to being silently
    dropped by an older copy path.  This helper is the single copy primitive;
    callers may override only declared fields.
    """

    payload = {
        item.name: copy.deepcopy(getattr(profile, item.name))
        for item in dataclass_fields(EntityProfile)
    }
    unknown = sorted(set(changes) - set(payload))
    if unknown:
        raise TypeError(f"Unknown EntityProfile fields: {', '.join(unknown)}")
    payload.update(copy.deepcopy(changes))
    return EntityProfile(**payload)

@dataclass
class EntityArchive:
    """实体档案（一个公司/组织的所有配置集）。"""

    archive_id: str = ""
    archive_name: str = ""          # e.g. "中建三局总部"
    profiles: list[EntityProfile] = field(default_factory=list)
    kind: str = "alavette.material_package"
    version: int = ENTITY_PACKAGE_VERSION
    mode_id: str = ""
    package_id: str = ""
    material_schema_ids: list[str] = field(default_factory=list)
    source_path: str = field(default="", repr=False, compare=False)

    def get_profile(self, profile_id: str) -> EntityProfile | None:
        for p in self.profiles:
            if p.profile_id == profile_id:
                return p
        return None

    def get_default_profile(self) -> EntityProfile | None:
        return self.profiles[0] if self.profiles else None

    def list_profile_names(self) -> list[str]:
        return [p.profile_name for p in self.profiles]

def _normalized_asset_bindings(value: object) -> dict[str, AssetBinding]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, AssetBinding] = {}
    for raw_role, raw_binding in value.items():
        binding = normalize_asset_binding(str(raw_role or ""), raw_binding)
        if binding.role:
            result[binding.role] = binding
    return result

def _normalized_image_material_rules(
    value: object,
) -> dict[str, ImageMaterialRule]:
    """Normalize the independent v3 image-rule inventory by ``rule_id``."""

    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise TypeError("image_material_rules must be a mapping keyed by rule_id")
    result: dict[str, ImageMaterialRule] = {}
    seen_source_roles: set[str] = set()
    seen_anchor_tokens: set[str] = set()
    for raw_rule_id, raw_rule in value.items():
        if isinstance(raw_rule, ImageMaterialRule):
            rule = copy.deepcopy(raw_rule)
        elif isinstance(raw_rule, dict):
            _validate_image_material_rule_payload_shape(raw_rule)
            rule = ImageMaterialRule.from_dict(raw_rule)
        else:
            raise TypeError(
                "image material rule values must be mappings or ImageMaterialRule"
            )
        rule_id = str(raw_rule_id or "").strip()
        if rule_id != rule.rule_id:
            raise ValueError(
                f"material_package_image_rule_id_mismatch:{rule_id}:{rule.rule_id}"
            )
        if rule.rule_id in result:
            raise ValueError(
                f"material_package_image_rule_duplicate:{rule.rule_id}"
            )
        if rule.source_role in seen_source_roles:
            raise ValueError(
                "material_package_image_rule_source_role_duplicate:"
                f"{rule.source_role}"
            )
        if rule.anchor_token in seen_anchor_tokens:
            raise ValueError(
                "material_package_image_rule_anchor_duplicate:"
                f"{rule.anchor_token}"
            )
        result[rule.rule_id] = rule
        seen_source_roles.add(rule.source_role)
        seen_anchor_tokens.add(rule.anchor_token)
    return dict(sorted(result.items()))

def _validate_image_material_rule_payload_shape(payload: dict[str, object]) -> None:
    allowed = {
        "rule_id",
        "source_role",
        "anchor_token",
        "required",
        "occurrence_policy",
        "cardinality",
        "placement",
        "watermark",
    }
    placement_allowed = {
        "mode",
        "contain",
        "allow_crop",
        "allow_move_preceding_text",
        "allow_page_break",
        "fixed_width_cm",
        "max_width_cm",
        "co_location_guard",
    }
    watermark_allowed = {
        "enabled",
        "text_source",
        "text_template",
        "style_version",
    }
    for path, value, expected in (
        ("rule", payload, allowed),
        ("placement", payload.get("placement"), placement_allowed),
        ("watermark", payload.get("watermark", {}), watermark_allowed),
    ):
        if not isinstance(value, dict):
            # The typed constructor emits the more specific missing/type error.
            continue
        unknown = sorted(set(value) - expected)
        if unknown:
            raise ValueError(
                "material_package_image_rule_structure_unsupported:"
                f"{path}:{','.join(unknown)}"
            )

def _normalized_content_bindings(
    value: object,
) -> dict[str, ContentMaterialBinding]:
    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise TypeError("content_bindings must be a mapping")
    result: dict[str, ContentMaterialBinding] = {}
    for raw_content_id, raw_binding in value.items():
        if isinstance(raw_binding, ContentMaterialBinding):
            binding = copy.deepcopy(raw_binding)
        elif isinstance(raw_binding, dict):
            binding = ContentMaterialBinding.from_dict(raw_binding)
        else:
            raise TypeError(
                "content binding values must be mappings or ContentMaterialBinding"
            )
        content_id = str(raw_content_id or binding.content_id).strip()
        if content_id != binding.content_id:
            raise ValueError(
                f"material_package_content_id_mismatch:{content_id}:{binding.content_id}"
            )
        if binding.content_id in result:
            raise ValueError(f"material_package_content_id_duplicate:{binding.content_id}")
        result[binding.content_id] = binding
    return result

def _normalized_content_rules(value: object) -> list[ContentInsertionRule]:
    if value in (None, []):
        return []
    if not isinstance(value, (list, tuple)):
        raise TypeError("content_rules must be a sequence")
    result: list[ContentInsertionRule] = []
    seen_rule_ids: set[str] = set()
    for raw_rule in value:
        if isinstance(raw_rule, ContentInsertionRule):
            rule = copy.deepcopy(raw_rule)
        elif isinstance(raw_rule, dict):
            rule = ContentInsertionRule.from_dict(raw_rule)
        else:
            raise TypeError("content rules must be mappings or ContentInsertionRule values")
        if rule.rule_id in seen_rule_ids:
            raise ValueError(f"material_package_content_rule_duplicate:{rule.rule_id}")
        seen_rule_ids.add(rule.rule_id)
        result.append(rule)
    return result

def _normalized_attachment_role_specs(
    value: object,
) -> list[AttachmentRoleSpec]:
    if value in (None, []):
        return []
    if not isinstance(value, (list, tuple)):
        raise TypeError("attachment_role_specs must be a sequence")
    result: list[AttachmentRoleSpec] = []
    seen: set[str] = set()
    for raw in value:
        if isinstance(raw, AttachmentRoleSpec):
            spec = copy.deepcopy(raw)
        elif isinstance(raw, dict):
            spec = AttachmentRoleSpec.from_dict(raw)
        else:
            raise TypeError(
                "attachment role specs must be mappings or AttachmentRoleSpec values"
            )
        if spec.role in seen:
            raise ValueError(f"material_package_attachment_role_duplicate:{spec.role}")
        seen.add(spec.role)
        result.append(spec)
    return result

def _normalized_attachment_bindings(
    value: object,
) -> dict[str, AttachmentBinding]:
    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise TypeError("attachment_bindings must be a mapping")
    result: dict[str, AttachmentBinding] = {}
    for raw_role, raw_binding in value.items():
        if isinstance(raw_binding, AttachmentBinding):
            binding = copy.deepcopy(raw_binding)
        elif isinstance(raw_binding, dict):
            binding = AttachmentBinding.from_dict(raw_binding)
        else:
            raise TypeError(
                "attachment binding values must be mappings or AttachmentBinding"
            )
        role = str(raw_role or binding.role).strip()
        if role != binding.role:
            raise ValueError(
                f"material_package_attachment_role_mismatch:{role}:{binding.role}"
            )
        if binding.role in result:
            raise ValueError(f"material_package_attachment_role_duplicate:{binding.role}")
        result[binding.role] = binding
    return result

def _normalized_asset_token_specs(value: object) -> list[AssetTokenSpec]:
    if not isinstance(value, (list, tuple)):
        return []
    normalized: list[AssetTokenSpec] = []
    seen: set[str] = set()
    seen_tokens: set[str] = set()
    for index, raw in enumerate(value):
        if isinstance(raw, AssetTokenSpec):
            spec = copy.deepcopy(raw)
        elif isinstance(raw, dict):
            try:
                order = int(raw.get("order", (index + 1) * 10) or 0)
            except (TypeError, ValueError):
                order = (index + 1) * 10
            spec = AssetTokenSpec(
                token_id=str(raw.get("token_id", "") or "").strip(),
                token=str(raw.get("token", "") or "").strip(),
                label=str(raw.get("label", "") or "").strip(),
                cardinality=str(raw.get("cardinality", "single") or "single").strip(),
                source_kind=str(raw.get("source_kind", "file") or "file").strip(),
                order=order,
                required=bool(raw.get("required", False)),
                recursive=bool(raw.get("recursive", False)),
                min_items=_safe_nonnegative_int(raw.get("min_items", 0), default=0),
                max_items=_safe_optional_nonnegative_int(
                    raw.get("max_items", 1),
                    default=1,
                ),
                order_policy=str(
                    raw.get("order_policy", "natural_path") or "natural_path"
                ).strip(),
                naming_template=str(
                    raw.get("naming_template", "{role}_{sequence:03d}")
                    or "{role}_{sequence:03d}"
                ).strip(),
            )
        else:
            continue
        raw_token = str(spec.token or "").strip()
        try:
            token_ref = parse_material_token(raw_token)
        except (TypeError, ValueError):
            continue
        if (
            not spec.token_id
            or token_ref.kind is not MaterialTokenKind.IMAGE
            or spec.token_id in seen
        ):
            continue
        spec.token = token_ref.token
        if spec.token in seen_tokens:
            continue
        seen.add(spec.token_id)
        seen_tokens.add(spec.token)
        spec.label = str(spec.label or "").strip() or token_ref.identifier
        spec.cardinality = "multiple" if spec.cardinality == "multiple" else "single"
        spec.source_kind = "directory" if spec.cardinality == "multiple" else "file"
        try:
            normalized_order = int(spec.order)
        except (TypeError, ValueError):
            normalized_order = 0
        spec.order = normalized_order if normalized_order > 0 else (index + 1) * 10
        if spec.cardinality == "multiple":
            spec.max_items = _safe_optional_nonnegative_int(spec.max_items, default=None)
        else:
            spec.recursive = False
            spec.min_items = 0
            spec.max_items = 1
        normalized.append(spec)
    normalized.sort(key=lambda item: (int(item.order), item.token_id))
    return normalized

def normalize_asset_binding(role: str, value: object) -> AssetBinding:
    """Materialize and canonicalize one role-keyed image binding."""

    normalized_role = str(role or "").strip().lower().replace(" ", "_")
    if isinstance(value, AssetBinding):
        binding = copy.deepcopy(value)
        binding.role = str(binding.role or normalized_role).strip().lower().replace(" ", "_")
        return _normalize_asset_binding(binding)
    payload = dict(value) if isinstance(value, dict) else {}
    binding = AssetBinding(
        role=str(payload.get("role", "") or normalized_role),
        cardinality=str(payload.get("cardinality", "single") or "single"),
        source_kind=str(payload.get("source_kind", "file") or "file"),
        source_path=str(payload.get("source_path", "") or ""),
        recursive=bool(payload.get("recursive", False)),
        order_policy=str(payload.get("order_policy", "natural_path") or "natural_path"),
        naming_template=str(
            payload.get("naming_template", "{role}_{sequence:03d}")
            or "{role}_{sequence:03d}"
        ),
        min_items=_safe_nonnegative_int(payload.get("min_items", 0), default=0),
        max_items=_safe_optional_nonnegative_int(payload.get("max_items", 1), default=1),
        items=[dict(item) for item in list(payload.get("items", []) or []) if isinstance(item, dict)],
        snapshot_revision=str(payload.get("snapshot_revision", "") or ""),
    )
    return _normalize_asset_binding(binding)

def _normalize_asset_binding(binding: AssetBinding) -> AssetBinding:
    binding.role = str(binding.role or "").strip().lower().replace(" ", "_")
    binding.cardinality = (
        "multiple"
        if str(binding.cardinality or "").strip().lower() == "multiple"
        else "single"
    )
    source_kind = str(binding.source_kind or "").strip().lower()
    binding.source_kind = source_kind if source_kind in {"file", "directory", "files"} else (
        "directory" if binding.cardinality == "multiple" else "file"
    )
    if binding.cardinality == "single":
        binding.recursive = False
        binding.max_items = 1
    elif binding.max_items == 1:
        binding.max_items = None
    binding.min_items = max(0, int(binding.min_items or 0))
    if binding.max_items is not None:
        binding.max_items = max(0, int(binding.max_items))
    binding.order_policy = str(binding.order_policy or "natural_path").strip() or "natural_path"
    binding.naming_template = (
        str(binding.naming_template or "{role}_{sequence:03d}").strip()
        or "{role}_{sequence:03d}"
    )
    return binding

def _safe_nonnegative_int(value: object, *, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default

def _safe_optional_nonnegative_int(
    value: object,
    *,
    default: int | None,
) -> int | None:
    if value is None or value == "":
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default

__all__ = [
    "ENTITY_PACKAGE_VERSION",
    "AssetBinding",
    "AssetTokenSpec",
    "EntityArchive",
    "EntityProfile",
    "clone_entity_profile",
    "normalize_asset_binding",
]
