"""
migration — 配置迁移 / 归一化层

职责：
1. 把旧版 / 混合版配置统一迁移为当前 canonical schema
2. 让 loader / resolver 在进入运行时之前完成 normalize
3. 运行时模块只读取规范字段，不再内嵌兼容分支
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from src.config.heading_normalize import normalize_heading_numbering_payload
from src.shared.engine.units import cn_size_to_pt


# ── 模块名 / 开关归一化 ─────────────────────────────

MODULE_SWITCH_ALIASES: dict[str, str] = {
    "citation_link": "reference_format",
    "equation_table_fmt": "equation_table_format",
}

LEGACY_MODULE_NAME_ALIASES: dict[str, str] = {
    "style_manager": "paragraph_style",
    "heading_detect": "heading_recognition",
    "toc_format": "toc",
    "toc_rebuild": "toc",
    "caption_format": "caption",
    "section_detection": "section_format",
    "citation_link_restore": "reference_format",
    "chem_typography_restore": "chem_typography",
}

def _build_default_module_switches() -> dict[str, bool]:
    """Derive default switches from ModuleMeta.enabled_by_default (single source of truth)."""
    try:
        from src.modules.registry import ALL_MODULES
        return {cls.meta.name: cls.meta.enabled_by_default for cls in ALL_MODULES}
    except ImportError:
        # 回退: 仅在极早期加载 / 测试隔离场景触发
        return {}


# 延迟计算的缓存
_default_switches_cache: dict[str, bool] | None = None


def get_default_module_switches() -> dict[str, bool]:
    """获取默认模块开关（缓存结果，避免重复计算）。"""
    global _default_switches_cache
    if _default_switches_cache is None:
        _default_switches_cache = _build_default_module_switches()
    return _default_switches_cache


def normalize_module_name(module_name: str) -> str:
    """将历史模块名 / 旧 pipeline 名归一到当前注册名。"""
    return LEGACY_MODULE_NAME_ALIASES.get(
        MODULE_SWITCH_ALIASES.get(module_name, module_name),
        MODULE_SWITCH_ALIASES.get(module_name, module_name),
    )


def normalize_module_switches(
    module_switches: Mapping[str, Any] | None,
    *,
    defaults: Mapping[str, bool] | None = None,
) -> dict[str, bool]:
    """归一化模块开关字典。

    规则：
    1. 历史别名转换为当前注册名
    2. 未实现 / 未注册的遗留 key 直接丢弃
    3. 缺失的已注册模块补默认值
    """
    normalized = dict(defaults if defaults is not None else get_default_module_switches())

    for raw_name, enabled in (module_switches or {}).items():
        canonical_name = normalize_module_name(str(raw_name))
        if canonical_name in normalized:
            normalized[canonical_name] = bool(enabled)

    return normalized


# ── 通用工具 ────────────────────────────────────────

def flatten_dict(prefix: str, obj: Mapping[str, Any]) -> dict[str, Any]:
    """将嵌套 dict 扁平化为 dotted-key。"""
    result: dict[str, Any] = {}
    for key, val in obj.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(val, Mapping):
            result.update(flatten_dict(full_key, val))
        else:
            result[full_key] = val
    return result


def unflatten_dict(obj: Mapping[str, Any] | None) -> dict[str, Any]:
    """将 dotted-key dict 还原为嵌套 dict。"""
    nested: dict[str, Any] = {}
    for key, val in (obj or {}).items():
        parts = str(key).split(".")
        cursor = nested
        for part in parts[:-1]:
            child = cursor.get(part)
            if not isinstance(child, dict):
                child = {}
                cursor[part] = child
            cursor = child
        cursor[parts[-1]] = val
    return nested


def _copy_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    return copy.deepcopy(dict(payload))


# ── Template normalize ──────────────────────────────

_TEMPLATE_META_KEYS = ("name", "description")
_CANONICAL_TEMPLATE_SECTION_KEYS = (
    "page_setup",
    "styles",
    "heading_numbering",
    "heading_model",
    "toc",
    "caption",
    "table",
    "section",
    "header_footer",
    "watermark",
    "reference_style",
    "formula_table",
    "formula_style",
    "equation_numbering",
    "output",
)

_LEGACY_FLAT_TABLE_KEYS = {
    "normal_table_layout_mode": "layout_mode",
    "normal_table_smart_levels": "smart_levels",
    "normal_table_border_mode": "border_mode",
    "table_border_width_pt": "border_width_pt",
    "three_line_header_width_pt": "three_line_header_width_pt",
    "three_line_bottom_width_pt": "three_line_bottom_width_pt",
    "normal_table_line_spacing_mode": "line_spacing_mode",
    "normal_table_repeat_header": "repeat_header",
}

_HEADER_FOOTER_TOP_LEVEL_KEYS = (
    "header_mode",
    "header_text",
    "styleref_level",
    "font_cn",
    "font_en",
    "size_pt",
    "update_header",
    "update_page_number",
    "update_header_line",
    "page_number_enabled",
    "header_border",
)


def normalize_template_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """将模板 / 混合 legacy payload 归一为当前 TemplateConfig 结构。"""
    raw = _copy_mapping(payload)
    normalized: dict[str, Any] = {}

    for key in _TEMPLATE_META_KEYS:
        if key in raw:
            normalized[key] = copy.deepcopy(raw[key])

    # 直接可复用的 canonical 区块
    for key in _CANONICAL_TEMPLATE_SECTION_KEYS:
        if key == "styles":
            continue
        if key == "heading_numbering":
            continue
        if key in raw and isinstance(raw[key], Mapping):
            normalized[key] = copy.deepcopy(raw[key])

    # heading_numbering：在 migration 层统一吸收 current / v2 / legacy 输入
    heading_numbering = normalize_heading_numbering_payload(raw)
    if heading_numbering:
        normalized["heading_numbering"] = heading_numbering

    # styles
    styles_raw = raw.get("styles")
    if isinstance(styles_raw, Mapping):
        styles = {
            str(name): _normalize_style_payload(style)
            for name, style in styles_raw.items()
            if isinstance(style, Mapping)
        }
        _ensure_runtime_style_aliases(styles)
        normalized["styles"] = styles

    # table: 接住 legacy 扁平字段
    table_payload = {}
    if isinstance(raw.get("table"), Mapping):
        table_payload.update(copy.deepcopy(dict(raw["table"])))
    for legacy_key, canonical_key in _LEGACY_FLAT_TABLE_KEYS.items():
        if legacy_key in raw:
            table_payload[canonical_key] = copy.deepcopy(raw[legacy_key])
    if table_payload:
        normalized["table"] = table_payload

    # header_footer: 接住 legacy 顶层/嵌套旧字段
    header_footer_payload = {}
    if isinstance(raw.get("header_footer"), Mapping):
        header_footer_payload.update(copy.deepcopy(dict(raw["header_footer"])))
    for key in _HEADER_FOOTER_TOP_LEVEL_KEYS:
        if key in raw and key not in header_footer_payload:
            header_footer_payload[key] = copy.deepcopy(raw[key])
    if header_footer_payload:
        normalized["header_footer"] = _normalize_header_footer_payload(header_footer_payload)

    return normalized


def normalize_template_overrides(
    overrides: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """将 legacy dotted-key overrides 归一为 canonical dotted-key。"""
    nested = unflatten_dict(overrides)
    normalized = normalize_template_payload(nested)
    flat = flatten_dict("", normalized)
    return {
        key: val
        for key, val in flat.items()
        if key not in _TEMPLATE_META_KEYS
    }


def _normalize_style_payload(style: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _copy_mapping(style)

    if "size_name" in normalized and "size_display" not in normalized:
        normalized["size_display"] = normalized["size_name"]
    normalized.pop("size_name", None)

    size_display = normalized.get("size_display")
    if (normalized.get("size_pt") in (None, "")) and isinstance(size_display, str):
        size_pt = cn_size_to_pt(size_display)
        if size_pt is not None:
            normalized["size_pt"] = size_pt

    _normalize_style_line_spacing(normalized)
    _normalize_style_indent(normalized)

    normalized.pop("line_spacing_rule", None)
    normalized.pop("line_spacing", None)
    normalized.pop("left_indent_cm", None)
    normalized.pop("special_indent_mode", None)
    normalized.pop("special_indent_value", None)
    normalized.pop("special_indent_unit", None)

    return normalized


def _normalize_style_line_spacing(style: dict[str, Any]) -> None:
    legacy_rule = style.get("line_spacing_rule")
    current_type = style.get("line_spacing_type")
    current_value = style.get("line_spacing_pt")
    legacy_value = style.get("line_spacing")

    if current_type in {"single", "one_half", "double"}:
        style["line_spacing_type"] = "multiple"
        style["line_spacing_pt"] = {
            "single": 1.0,
            "one_half": 1.5,
            "double": 2.0,
        }[current_type]
        return

    effective_rule = current_type or legacy_rule
    if effective_rule == "fixed":
        effective_rule = "exact"

    if effective_rule in {"single", "one_half", "double"}:
        style["line_spacing_type"] = "multiple"
        style["line_spacing_pt"] = {
            "single": 1.0,
            "one_half": 1.5,
            "double": 2.0,
        }[effective_rule]
        return

    if effective_rule:
        style["line_spacing_type"] = effective_rule

    if legacy_value is not None and current_value in (None, ""):
        style["line_spacing_pt"] = legacy_value


def _normalize_style_indent(style: dict[str, Any]) -> None:
    left_indent_cm = style.get("left_indent_cm")
    if left_indent_cm is not None and "left_indent_chars" not in style:
        style["left_indent_chars"] = left_indent_cm
        style["left_indent_unit"] = "cm"

    mode = style.get("special_indent_mode")
    value = style.get("special_indent_value")
    unit = style.get("special_indent_unit", "chars")
    if value in (None, ""):
        return

    if mode == "first_line" and "first_line_indent_chars" not in style:
        style["first_line_indent_chars"] = value
        style["first_line_indent_unit"] = unit
    elif mode == "left" and "left_indent_chars" not in style:
        style["left_indent_chars"] = value
        style["left_indent_unit"] = unit
    elif mode == "right" and "right_indent_chars" not in style:
        style["right_indent_chars"] = value
        style["right_indent_unit"] = unit
    elif mode == "hanging" and "hanging_indent_chars" not in style:
        style["hanging_indent_chars"] = value
        style["hanging_indent_unit"] = unit


def _ensure_runtime_style_aliases(styles: dict[str, dict[str, Any]]) -> None:
    """补出当前运行时真正依赖的样式别名。"""
    alias_groups = {
        "heading": ("heading", "heading1", "heading2", "heading3"),
        "caption": ("caption", "figure_caption", "table_caption"),
        "toc": ("toc", "toc_level1", "toc_chapter", "toc_title"),
        "references_body": ("references_body",),
        "abstract_body": ("abstract_body", "abstract_body_en"),
        "appendix_body": ("appendix_body",),
    }

    for target, candidates in alias_groups.items():
        if target in styles:
            continue
        for candidate in candidates:
            if candidate in styles:
                styles[target] = copy.deepcopy(styles[candidate])
                break


def _normalize_header_footer_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _copy_mapping(payload)

    update_header = normalized.pop("update_header", None)
    update_page_number = normalized.pop("update_page_number", None)
    update_header_line = normalized.pop("update_header_line", None)

    if "page_number_enabled" not in normalized and update_page_number is not None:
        normalized["page_number_enabled"] = bool(update_page_number)
    normalized.setdefault("page_number_enabled", True)

    if "header_border" not in normalized and update_header_line is not None:
        normalized["header_border"] = bool(update_header_line)
    normalized.setdefault("header_border", True)

    if "header_mode" not in normalized:
        header_text = str(normalized.get("header_text", "") or "").strip()
        if header_text:
            normalized["header_mode"] = "fixed"
        elif update_header is False:
            normalized["header_mode"] = "none"
        else:
            normalized["header_mode"] = "styleref"

    return normalized


# ── Scene normalize ─────────────────────────────────

_SCENE_META_KEYS = (
    "name",
    "description",
    "category",
    "category_label",
    "template_id",
)

_LEGACY_SCENE_OPTION_BLOCKS: tuple[tuple[str, str | None, str | None], ...] = (
    ("md_cleanup", "md_cleanup", "md_cleanup"),
    ("whitespace_normalize", "whitespace", None),
    ("whitespace", "whitespace", None),
    ("citation_link", "citation_link", "reference_format"),
    ("formula_convert", "formula_convert", None),
    ("chem_typography", "chem_typography", "chem_typography"),
    ("equation_table_format", None, "equation_table_format"),
)

_SCENE_LIFTED_TEMPLATE_KEYS = {
    "page_setup",
    "styles",
    "heading_numbering",
    "heading_numbering_v2",
    "heading_model",
    "heading",
    "toc",
    "caption",
    "table",
    "section",
    "header_footer",
    "watermark",
    "reference_style",
    "formula_table",
    "formula_style",
    "equation_numbering",
    "output",
    "normal_table_layout_mode",
    "normal_table_smart_levels",
    "normal_table_border_mode",
    "table_border_width_pt",
    "three_line_header_width_pt",
    "three_line_bottom_width_pt",
    "normal_table_line_spacing_mode",
    "normal_table_repeat_header",
    "update_header",
    "update_page_number",
    "update_header_line",
}


def normalize_scene_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """将场景 / 混合 legacy payload 归一为当前 SceneWorkspace 结构。"""
    raw = _copy_mapping(payload)
    normalized: dict[str, Any] = {}

    for key in _SCENE_META_KEYS:
        if key in raw:
            normalized[key] = copy.deepcopy(raw[key])

    if isinstance(raw.get("format_scope"), Mapping):
        normalized["format_scope"] = copy.deepcopy(dict(raw["format_scope"]))
    if isinstance(raw.get("available_sections"), list):
        normalized["available_sections"] = copy.deepcopy(list(raw["available_sections"]))

    pipeline_switches = _extract_switches_from_pipeline(raw.get("pipeline"))
    capability_switches = _extract_switches_from_capabilities(raw.get("capabilities"))
    direct_switches = raw.get("module_switches") if isinstance(raw.get("module_switches"), Mapping) else {}

    if isinstance(raw.get("pipeline"), list):
        switch_defaults: dict[str, bool] = {
            name: False for name in get_default_module_switches()
        }
    else:
        switch_defaults = dict(get_default_module_switches())

    switches: dict[str, Any] = dict(switch_defaults)
    switches.update(pipeline_switches)
    switches.update(capability_switches)
    switches.update(copy.deepcopy(dict(direct_switches)))

    for legacy_key, target_attr, module_name in _LEGACY_SCENE_OPTION_BLOCKS:
        block = raw.get(legacy_key)
        if not isinstance(block, Mapping):
            continue
        block_data = copy.deepcopy(dict(block))
        enabled = block_data.pop("enabled", None)
        if target_attr is not None:
            normalized[target_attr] = block_data
        if module_name is not None and enabled is not None:
            switches[module_name] = bool(enabled)

    normalized["module_switches"] = normalize_module_switches(
        switches,
        defaults=switch_defaults,
    )

    if "strict_mode" in raw:
        normalized["strict_mode"] = bool(raw["strict_mode"])
    elif "pipeline_strict_mode" in raw:
        normalized["strict_mode"] = bool(raw["pipeline_strict_mode"])

    lifted_overrides = _extract_template_overrides_from_payload(raw)
    explicit_overrides = normalize_template_overrides(raw.get("overrides"))
    explicit_overrides.update(
        normalize_template_overrides(raw.get("template_overrides"))
    )
    merged_overrides = {**lifted_overrides, **explicit_overrides}
    if merged_overrides:
        normalized["template_overrides"] = merged_overrides

    return normalized


def _extract_switches_from_capabilities(
    capabilities: Any,
) -> dict[str, bool]:
    if not isinstance(capabilities, Mapping):
        return {}
    return {
        normalize_module_name(str(name)): bool(enabled)
        for name, enabled in capabilities.items()
        if normalize_module_name(str(name)) in get_default_module_switches()
    }


def _extract_switches_from_pipeline(pipeline: Any) -> dict[str, bool]:
    if not isinstance(pipeline, list):
        return {}

    normalized: dict[str, bool] = {}
    for name in pipeline:
        canonical = normalize_module_name(str(name))
        if canonical in get_default_module_switches():
            normalized[canonical] = True
    return normalized


def _extract_template_overrides_from_payload(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    if not any(key in raw for key in _SCENE_LIFTED_TEMPLATE_KEYS):
        return {}

    template_payload = normalize_template_payload(raw)
    flat = flatten_dict("", template_payload)
    return {
        key: val
        for key, val in flat.items()
        if key not in _TEMPLATE_META_KEYS
    }

