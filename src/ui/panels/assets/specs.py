"""Static specs for the assets panel."""

from __future__ import annotations

from dataclasses import dataclass


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

REQUIRED_FIELD_KEYS: tuple[str, ...] = ("company_name",)

COMMON_ASSET_SLOTS: tuple[tuple[str, str, str], ...] = (
    ("logo", "Logo", "{{logo}}"),
    ("seal", "公章", "{{seal}}"),
    ("legal_signature", "法人签名", "{{legal_signature}}"),
    ("agent_signature", "授权代表签名", "{{agent_signature}}"),
    ("qualification", "资质证书", "{{qualification}}"),
    ("qrcode", "二维码", "{{qrcode}}"),
    ("cover", "封面图", "{{cover}}"),
)

SUPPORTED_IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
)

BATCH_OUTPUT_CUSTOM_TEMPLATE = "__custom_output_template__"

BATCH_OUTPUT_NAMING_OPTIONS: tuple[tuple[str, str], ...] = (
    ("按公司名称", "{entity_name}"),
    ("编号 + 公司名称", "{profile_id}-{entity_name}"),
    ("按这一份名称", "{profile_name}"),
    ("资料包 + 公司名称", "{archive_name}-{entity_name}"),
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
class AttachmentRoleSpec:
    role: str
    label: str
    accepted_types: tuple[str, ...] = ("image", "pdf")
    required: bool = False


ASSETS_SECTION_SPECS: tuple[AssetsSectionSpec, ...] = (
    AssetsSectionSpec("generate", "资料包概览", "package"),
    AssetsSectionSpec("io", "导入导出", "download"),
    AssetsSectionSpec("fields", "填资料", "type"),
    AssetsSectionSpec("images", "选图片", "image"),
    AssetsSectionSpec("preview", "看预览", "eye"),
    AssetsSectionSpec("batch", "多份生成", "layers"),
    AssetsSectionSpec("advanced", "高级", "settings"),
)


__all__ = [
    "ASSETS_SECTION_SPECS",
    "BATCH_OUTPUT_CUSTOM_TEMPLATE",
    "BATCH_OUTPUT_NAMING_OPTIONS",
    "COMMON_ASSET_SLOTS",
    "COMMON_FIELD_DEFS",
    "FIELD_SOURCE_IMPORTED_MAPPING",
    "REQUIRED_FIELD_KEYS",
    "SUPPORTED_IMAGE_SUFFIXES",
    "AssetSlotSpec",
    "AssetsSectionSpec",
    "AttachmentRoleSpec",
]
