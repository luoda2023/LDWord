"""Static specs for the assets panel."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.attachment_materials import AttachmentRoleSpec
from src.config.materials import IMAGE_EXTENSIONS
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    material_token,
)


COMMON_FIELD_DEFS: tuple[tuple[str, str, str], ...] = (
    ("company_name", "公司名称", "例如：测试公司"),
    ("credit_code", "统一社会信用代码", "例如：9142..."),
    ("legal_person", "法定代表人", "例如：张三"),
    ("address", "地址", "例如：武汉市..."),
    ("contact_name", "联系人", "例如：李四"),
    ("phone", "电话", "例如：13800000000"),
    ("project_name", "项目名称", "例如：XX 项目"),
    ("bid_number", "招标编号", "例如：ZB-2026-001"),
    ("bid_date", "投标日期", "例如：2026年6月2日"),
    ("compile_date", "编制日期", "例如：2026年6月2日"),
)

REQUIRED_FIELD_KEYS: tuple[str, ...] = ()

COMMON_ASSET_SLOTS: tuple[tuple[str, str, str], ...] = (
    ("logo", "Logo", "{{LOGO1}}"),
    ("seal", "公章", "{{公章1}}"),
    ("legal_signature", "法人签名", "{{法人签名1}}"),
    ("agent_signature", "授权代表签名", "{{授权代表签名1}}"),
    ("qualification", "资质证书", "{{qualification}}"),
    ("qrcode", "二维码", "{{二维码1}}"),
    ("cover", "封面图", "{{封面图1}}"),
)

COMMON_ASSET_SLOTS = tuple(
    (
        role,
        label,
        material_token(MaterialTokenNamespace.IMAGE, target[2:-2]),
    )
    for role, label, target in COMMON_ASSET_SLOTS
)

SUPPORTED_IMAGE_SUFFIXES: frozenset[str] = frozenset(IMAGE_EXTENSIONS)

BATCH_OUTPUT_CUSTOM_TEMPLATE = "__custom_output_template__"

BATCH_OUTPUT_NAMING_OPTIONS: tuple[tuple[str, str], ...] = (
    ("按这一份名称", "{profile_name}"),
    ("编号 + 这一份名称", "{profile_id}-{profile_name}"),
    ("资料包 + 这一份名称", "{archive_name}-{profile_name}"),
    ("按 entity_name 字段（兼容）", "{entity_name}"),
    ("自定义", BATCH_OUTPUT_CUSTOM_TEMPLATE),
)

FIELD_SOURCE_IMPORTED_MAPPING = "imported_mapping"

@dataclass(frozen=True)
class AssetsSectionSpec:
    section_id: str
    title: str
    icon_name: str


@dataclass(frozen=True)
class AssetSlotSpec:
    role: str
    label: str
    target: str
    required: bool = False


@dataclass(frozen=True)
class AssetGroupSpec:
    role: str
    label: str
    target: str
    required: bool = False
    recursive: bool = True
    min_items: int = 0
    max_items: int | None = None
    order_policy: str = "natural_path"
    naming_template: str = "{role}_{sequence:03d}"
    source_kind: str = "directory"


ASSETS_SECTION_SPECS: tuple[AssetsSectionSpec, ...] = (
    AssetsSectionSpec("generate", "资料包概览", "package"),
    AssetsSectionSpec("fields", "字段资料", "type"),
    AssetsSectionSpec("content", "文件资料", "file-text"),
    AssetsSectionSpec("timeline", "时间计划", "chart-no-axes-gantt"),
    AssetsSectionSpec("images", "图片资料", "image"),
    AssetsSectionSpec("attachments", "附件资料", "gallery-vertical-end"),
)

# Preview projection and multi-profile selection remain implementation
# services. They keep backing widgets but are not user-facing secondary pages.
ASSETS_SUPPORT_SECTION_SPECS: tuple[AssetsSectionSpec, ...] = (
    AssetsSectionSpec("preview", "生成检查", "eye"),
    AssetsSectionSpec("batch", "多份资料", "layers"),
)
ASSETS_RUNTIME_SECTION_SPECS: tuple[AssetsSectionSpec, ...] = (
    *ASSETS_SECTION_SPECS,
    *ASSETS_SUPPORT_SECTION_SPECS,
)


__all__ = [
    "ASSETS_SECTION_SPECS",
    "ASSETS_RUNTIME_SECTION_SPECS",
    "ASSETS_SUPPORT_SECTION_SPECS",
    "BATCH_OUTPUT_CUSTOM_TEMPLATE",
    "BATCH_OUTPUT_NAMING_OPTIONS",
    "COMMON_ASSET_SLOTS",
    "COMMON_FIELD_DEFS",
    "FIELD_SOURCE_IMPORTED_MAPPING",
    "REQUIRED_FIELD_KEYS",
    "SUPPORTED_IMAGE_SUFFIXES",
    "AssetSlotSpec",
    "AssetGroupSpec",
    "AssetsSectionSpec",
    "AttachmentRoleSpec",
]
