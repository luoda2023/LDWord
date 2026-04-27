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
from src.config.style_semantics import normalize_font_size_display_text, normalize_spacing_unit
from src.shared.engine.font_resolver import canonicalize_font_name
from src.shared.engine.units import cn_size_to_pt


# ── 模块名 / 开关归一化 ─────────────────────────────

MODULE_SWITCH_ALIASES: dict[str, str] = {
    "equation_table_fmt": "equation_table_format",
    "whitespace": "whitespace_normalize",
}

LEGACY_MODULE_NAME_ALIASES: dict[str, str] = {
    "style_manager": "paragraph_style",
    "heading_detect": "heading_recognition",
    "toc_format": "toc",
    "toc_rebuild": "toc",
    "caption_format": "caption",
    "section_detection": "section_format",
    "citation_link_restore": "citation_link",
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


def add_template_compat_aliases(flat: Mapping[str, Any]) -> dict[str, Any]:
    """Add legacy flat aliases for fields that now live in nested schema."""
    result = dict(flat)
    _add_header_footer_compat_aliases(result)
    return result


def _add_header_footer_compat_aliases(flat: dict[str, Any]) -> None:
    prefix = "header_footer."
    if not any(key.startswith(prefix) for key in flat):
        return

    if "header_footer.header.mode" in flat:
        flat.setdefault("header_footer.header_mode", flat["header_footer.header.mode"])
    if "header_footer.header.fixed_text" in flat:
        flat.setdefault("header_footer.header_text", flat["header_footer.header.fixed_text"])
    if "header_footer.header.styleref_level" in flat:
        flat.setdefault(
            "header_footer.styleref_level",
            flat["header_footer.header.styleref_level"],
        )
    if "header_footer.header.border" in flat:
        flat.setdefault("header_footer.header_border", flat["header_footer.header.border"])

    if "header_footer.typography.font_cn" in flat:
        flat.setdefault("header_footer.font_cn", flat["header_footer.typography.font_cn"])
    if "header_footer.typography.font_en" in flat:
        flat.setdefault("header_footer.font_en", flat["header_footer.typography.font_en"])
    if "header_footer.typography.size_pt" in flat:
        flat.setdefault("header_footer.size_pt", flat["header_footer.typography.size_pt"])
    if "header_footer.typography.bold" in flat:
        flat.setdefault("header_footer.bold", flat["header_footer.typography.bold"])
    if "header_footer.typography.italic" in flat:
        flat.setdefault("header_footer.italic", flat["header_footer.typography.italic"])

    if "header_footer.footer.content_mode" in flat:
        footer_mode = str(
            flat.get("header_footer.footer.content_mode", "page_number") or "page_number"
        )
        flat.setdefault("header_footer.page_number_enabled", footer_mode == "page_number")

    if (
        "header_footer.header.hide_on_cover" in flat
        or "header_footer.footer.hide_on_cover" in flat
    ):
        hide_header = bool(flat.get("header_footer.header.hide_on_cover", True))
        hide_footer = bool(flat.get("header_footer.footer.hide_on_cover", True))
        flat.setdefault("header_footer.hide_cover_header_footer", hide_header and hide_footer)

    if "header_footer.page_number_plan.phases" in flat:
        front_phase = _resolve_page_number_phase_alias(
            flat.get("header_footer.page_number_plan.phases"),
            phase_id="front",
            fallback_selectors=("front_matter",),
            default_format="upperRoman",
            default_start_mode="restart",
            default_start_value=1,
        )
        body_phase = _resolve_page_number_phase_alias(
            flat.get("header_footer.page_number_plan.phases"),
            phase_id="body",
            fallback_selectors=("body", "back_matter"),
            default_format="decimal",
            default_start_mode="restart",
            default_start_value=1,
        )

        flat.setdefault(
            "header_footer.front_matter_page_number_format",
            front_phase["number_format"],
        )
        flat.setdefault(
            "header_footer.front_matter_page_number_start",
            front_phase["start_value"],
        )
        flat.setdefault(
            "header_footer.body_page_number_format",
            body_phase["number_format"],
        )
        flat.setdefault(
            "header_footer.body_page_number_start",
            body_phase["start_value"],
        )
        flat.setdefault(
            "header_footer.restart_body_page_number",
            body_phase["start_mode"] != "continue",
        )


def _resolve_page_number_phase_alias(
    phases: Any,
    *,
    phase_id: str,
    fallback_selectors: tuple[str, ...],
    default_format: str,
    default_start_mode: str,
    default_start_value: int,
) -> dict[str, Any]:
    phase = None
    if isinstance(phases, list):
        for item in phases:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("phase_id", "") or "") == phase_id:
                phase = item
                break
        if phase is None:
            expected = {str(selector) for selector in fallback_selectors}
            for item in phases:
                if not isinstance(item, Mapping):
                    continue
                selectors = item.get("selectors")
                if not isinstance(selectors, list):
                    continue
                if expected.issubset({str(selector) for selector in selectors}):
                    phase = item
                    break

    if not isinstance(phase, Mapping):
        phase = {}

    return {
        "number_format": str(phase.get("number_format", default_format) or default_format),
        "start_mode": str(phase.get("start_mode", default_start_mode) or default_start_mode),
        "start_value": max(
            1,
            int(phase.get("start_value", default_start_value) or default_start_value),
        ),
    }


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
    "color_table_accent": "color_table_accent",
    "color_table_variant": "color_table_variant",
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
    "bold",
    "italic",
    "update_header",
    "update_page_number",
    "update_header_line",
    "page_number_enabled",
    "header_border",
    "hide_cover_header_footer",
    "front_matter_page_number_format",
    "front_matter_page_number_start",
    "body_page_number_format",
    "body_page_number_start",
    "restart_body_page_number",
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
            value = copy.deepcopy(dict(raw[key]))
            if key == "reference_style":
                value = _normalize_reference_style_payload(value)
            elif key == "formula_table":
                value = _normalize_formula_table_payload(value)
            normalized[key] = value

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
    flat = add_template_compat_aliases(flatten_dict("", normalized))
    return {
        key: val
        for key, val in flat.items()
        if key not in _TEMPLATE_META_KEYS
    }


def _normalize_style_payload(style: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _copy_mapping(style)

    if "font_cn" in normalized:
        normalized["font_cn"] = canonicalize_font_name(str(normalized.get("font_cn") or "").strip())
    if "font_en" in normalized:
        normalized["font_en"] = canonicalize_font_name(str(normalized.get("font_en") or "").strip())

    if "size_name" in normalized and "size_display" not in normalized:
        normalized["size_display"] = normalized["size_name"]
    normalized.pop("size_name", None)

    size_display = normalized.get("size_display")
    if isinstance(size_display, str):
        repaired_size = _repair_utf8_gbk_mojibake(size_display)
        normalized["size_display"] = normalize_font_size_display_text(repaired_size)
        size_display = normalized["size_display"]
    if (normalized.get("size_pt") in (None, "")) and isinstance(size_display, str):
        size_pt = cn_size_to_pt(size_display)
        if size_pt is not None:
            normalized["size_pt"] = size_pt

    _normalize_style_line_spacing(normalized)
    _normalize_style_indent(normalized)
    _normalize_style_spacing(normalized)

    normalized.pop("line_spacing_rule", None)
    normalized.pop("line_spacing", None)
    normalized.pop("left_indent_cm", None)

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


def _repair_utf8_gbk_mojibake(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    try:
        repaired = raw.encode("gbk").decode("utf-8")
    except UnicodeError:
        return raw
    return repaired if repaired else raw


def _normalize_style_indent(style: dict[str, Any]) -> None:
    left_indent_cm = style.get("left_indent_cm")
    if left_indent_cm is not None and "left_indent_chars" not in style:
        style["left_indent_chars"] = left_indent_cm
        style["left_indent_unit"] = "cm"

    mode = style.get("special_indent_mode")
    value = style.get("special_indent_value")
    unit = style.get("special_indent_unit", "chars")
    if value not in (None, ""):
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

    hanging_value = style.get("hanging_indent_chars")
    hanging_unit = style.get("hanging_indent_unit", "chars")
    first_value = style.get("first_line_indent_chars")
    first_unit = style.get("first_line_indent_unit", "chars")

    if hanging_value not in (None, "", 0, 0.0, "0", "0.0"):
        style["special_indent_mode"] = "hanging"
        style["special_indent_value"] = hanging_value
        style["special_indent_unit"] = hanging_unit
        return

    if first_value not in (None, "", 0, 0.0, "0", "0.0"):
        style["special_indent_mode"] = "first_line"
        style["special_indent_value"] = first_value
        style["special_indent_unit"] = first_unit
        return

    normalized_mode = str(mode or "none")
    if normalized_mode not in {"first_line", "hanging"}:
        normalized_mode = "none"
    style["special_indent_mode"] = normalized_mode
    style["special_indent_value"] = 0 if normalized_mode == "none" or value in (None, "") else value
    style["special_indent_unit"] = unit


def _normalize_style_spacing(style: dict[str, Any]) -> None:
    for slot in ("before", "after"):
        value_key = f"space_{slot}_pt"
        unit_key = f"space_{slot}_unit"
        if unit_key in style:
            style[unit_key] = normalize_spacing_unit(style.get(unit_key))
        elif value_key in style:
            style[unit_key] = "pt"


def _normalize_reference_style_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "space_after_unit" in payload:
        payload["space_after_unit"] = normalize_spacing_unit(payload.get("space_after_unit"))
    elif "space_after_pt" in payload:
        payload["space_after_unit"] = "pt"
    return payload


def _normalize_formula_table_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for slot in ("before", "after"):
        value_key = f"formula_space_{slot}_pt"
        unit_key = f"formula_space_{slot}_unit"
        if unit_key in payload:
            payload[unit_key] = normalize_spacing_unit(payload.get(unit_key))
        elif value_key in payload:
            payload[unit_key] = "pt"
    return payload


def _ensure_runtime_style_aliases(styles: dict[str, dict[str, Any]]) -> None:
    """补出当前运行时真正依赖的样式别名。"""
    alias_groups = {
        "heading": ("heading", "heading1", "heading2", "heading3"),
        "caption": ("caption", "figure_caption", "table_caption"),
        "toc": ("toc", "toc_level1", "toc_chapter", "toc_title"),
        "references_body": ("references_body",),
        "abstract_body": ("abstract_body", "abstract_body_en"),
        "appendix_body": ("appendix_body",),
        "acknowledgment_body": ("acknowledgment_body", "acknowledgements_body"),
        "resume_body": ("resume_body", "bio_body"),
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

    typography = (
        _copy_mapping(normalized.get("typography"))
        if isinstance(normalized.get("typography"), Mapping)
        else {}
    )
    header = (
        _copy_mapping(normalized.get("header"))
        if isinstance(normalized.get("header"), Mapping)
        else {}
    )
    footer = (
        _copy_mapping(normalized.get("footer"))
        if isinstance(normalized.get("footer"), Mapping)
        else {}
    )
    page_number_plan = (
        _copy_mapping(normalized.get("page_number_plan"))
        if isinstance(normalized.get("page_number_plan"), Mapping)
        else {}
    )

    if "font_cn" in normalized and "font_cn" not in typography:
        typography["font_cn"] = normalized["font_cn"]
    if "font_en" in normalized and "font_en" not in typography:
        typography["font_en"] = normalized["font_en"]
    if "size_pt" in normalized and "size_pt" not in typography:
        typography["size_pt"] = normalized["size_pt"]
    if "bold" in normalized and "bold" not in typography:
        typography["bold"] = bool(normalized["bold"])
    if "italic" in normalized and "italic" not in typography:
        typography["italic"] = bool(normalized["italic"])

    if "mode" not in header:
        header_text = str(normalized.get("header_text", "") or "").strip()
        if header_text:
            header["mode"] = "fixed"
        elif update_header is False:
            header["mode"] = "none"
        else:
            header["mode"] = str(normalized.get("header_mode", "") or "styleref")
    else:
        header["mode"] = str(header.get("mode", "styleref") or "styleref")

    if "fixed_text" not in header:
        header["fixed_text"] = str(normalized.get("header_text", "") or "")
    if "styleref_level" not in header:
        header["styleref_level"] = int(normalized.get("styleref_level", 1) or 1)
    if "border" not in header:
        if "header_border" in normalized:
            header["border"] = bool(normalized["header_border"])
        elif update_header_line is not None:
            header["border"] = bool(update_header_line)
        else:
            header["border"] = True

    hide_cover = normalized.get("hide_cover_header_footer")
    if "hide_on_cover" not in header:
        header["hide_on_cover"] = True if hide_cover is None else bool(hide_cover)
    if "content_mode" not in footer:
        page_number_enabled = normalized.get("page_number_enabled")
        if page_number_enabled is None and update_page_number is not None:
            page_number_enabled = bool(update_page_number)
        footer["content_mode"] = "page_number" if page_number_enabled is not False else "none"
    if "hide_on_cover" not in footer:
        footer["hide_on_cover"] = True if hide_cover is None else bool(hide_cover)

    suppress_selectors_raw = normalized.get("suppress_header_footer_selectors")
    suppress_selectors: list[str] = []
    if isinstance(suppress_selectors_raw, list):
        suppress_selectors = [
            str(selector).strip()
            for selector in suppress_selectors_raw
            if str(selector or "").strip()
        ]
    elif bool(header.get("hide_on_cover", True)) and bool(footer.get("hide_on_cover", True)):
        suppress_selectors = ["pre_numbering"]

    phases_raw = page_number_plan.get("phases")
    phases: list[dict[str, Any]] = []
    if isinstance(phases_raw, list):
        for item in phases_raw:
            if not isinstance(item, Mapping):
                continue
            phases.append(
                {
                    "phase_id": str(item.get("phase_id", "") or ""),
                    "selectors": [
                        str(selector)
                        for selector in item.get("selectors", [])
                        if str(selector or "").strip()
                    ],
                    "visible": bool(item.get("visible", True)),
                    "number_format": str(item.get("number_format", "decimal") or "decimal"),
                    "start_mode": str(item.get("start_mode", "continue") or "continue"),
                    "start_value": max(1, int(item.get("start_value", 1) or 1)),
                }
            )

    if not phases:
        phases = [
            {
                "phase_id": "front",
                "selectors": ["front_matter"],
                "visible": True,
                "number_format": str(
                    normalized.get("front_matter_page_number_format", "upperRoman")
                    or "upperRoman"
                ),
                "start_mode": "restart",
                "start_value": max(
                    1,
                    int(normalized.get("front_matter_page_number_start", 1) or 1),
                ),
            },
            {
                "phase_id": "body",
                "selectors": ["body", "back_matter"],
                "visible": True,
                "number_format": str(
                    normalized.get("body_page_number_format", "decimal") or "decimal"
                ),
                "start_mode": (
                    "restart"
                    if bool(normalized.get("restart_body_page_number", True))
                    else "continue"
                ),
                "start_value": max(
                    1,
                    int(normalized.get("body_page_number_start", 1) or 1),
                ),
            },
        ]

    page_number_plan["phases"] = phases
    page_number_plan["on_missing_doc_tree"] = str(
        page_number_plan.get("on_missing_doc_tree", "warn_and_fallback")
        or "warn_and_fallback"
    )
    page_number_plan["validation_mode"] = str(
        page_number_plan.get("validation_mode", "strict") or "strict"
    )

    return {
        "typography": typography,
        "header": header,
        "footer": footer,
        "page_number_plan": page_number_plan,
        "suppress_header_footer_selectors": suppress_selectors,
    }


# ── Scene normalize ─────────────────────────────────

_SCENE_META_KEYS = (
    "name",
    "description",
    "category",
    "category_label",
    "scene_id",
    "template_id",
    "default_template_id",
    "compatible_template_ids",
)

_LEGACY_SCENE_OPTION_BLOCKS: tuple[tuple[str, str | None, str | None], ...] = (
    ("md_cleanup", "md_cleanup", "md_cleanup"),
    ("whitespace_normalize", "whitespace", "whitespace_normalize"),
    ("whitespace", "whitespace", "whitespace_normalize"),
    ("citation_link", "citation_link", "citation_link"),
    ("formula_convert", "formula_convert", None),
    ("chem_typography", "chem_typography", "chem_typography"),
    ("equation_table_format", None, "equation_table_format"),
)

_SCENE_DIRECT_FEATURE_ROOTS = ("header_footer", "toc")

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
    "color_table_accent",
    "color_table_variant",
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
    direct_feature_payloads, remaining_overrides = _lift_scene_direct_feature_overrides(
        merged_overrides
    )

    if "header_footer" in direct_feature_payloads:
        normalized["header_footer"] = _normalize_header_footer_payload(
            direct_feature_payloads["header_footer"]
        )
    if "toc" in direct_feature_payloads:
        normalized["toc"] = direct_feature_payloads["toc"]

    if remaining_overrides:
        normalized["template_overrides"] = remaining_overrides

    compatible_template_ids = normalized.get("compatible_template_ids")
    if isinstance(compatible_template_ids, list):
        normalized["compatible_template_ids"] = [
            str(item).strip()
            for item in compatible_template_ids
            if str(item or "").strip()
        ]

    default_template_id = str(normalized.get("default_template_id", "") or "").strip()
    template_id = str(normalized.get("template_id", "") or "").strip()
    if not default_template_id and template_id:
        normalized["default_template_id"] = template_id
    if not template_id and default_template_id:
        normalized["template_id"] = default_template_id
    if not normalized.get("compatible_template_ids"):
        seed = str(
            normalized.get("template_id")
            or normalized.get("default_template_id")
            or ""
        ).strip()
        if seed:
            normalized["compatible_template_ids"] = [seed]

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
    flat = add_template_compat_aliases(flatten_dict("", template_payload))
    return {
        key: val
        for key, val in flat.items()
        if key not in _TEMPLATE_META_KEYS
    }


def _lift_scene_direct_feature_overrides(
    overrides: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    feature_flat: dict[str, dict[str, Any]] = {
        root: {} for root in _SCENE_DIRECT_FEATURE_ROOTS
    }
    remaining: dict[str, Any] = {}

    for key, value in overrides.items():
        matched_root = next(
            (
                root
                for root in _SCENE_DIRECT_FEATURE_ROOTS
                if key == root or str(key).startswith(f"{root}.")
            ),
            None,
        )
        if matched_root is None:
            remaining[key] = value
            continue
        feature_flat[matched_root][key] = copy.deepcopy(value)

    feature_payloads: dict[str, dict[str, Any]] = {}
    for root, flat_payload in feature_flat.items():
        if not flat_payload:
            continue
        nested_payload = unflatten_dict(flat_payload)
        root_payload = nested_payload.get(root)
        if isinstance(root_payload, Mapping):
            feature_payloads[root] = copy.deepcopy(dict(root_payload))

    return feature_payloads, remaining

