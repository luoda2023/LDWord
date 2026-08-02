"""
migration — 配置迁移 / 归一化层

职责：
1. 把旧版 / 混合版配置统一迁移为当前 canonical schema
2. 让 loader / resolver 在进入运行时之前完成 normalize
3. 运行时模块只读取规范字段，不再内嵌兼容分支
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from src.config.formula_policy import (
    THESIS_FORMULA_MODULE_NAMES,
    ThesisFormulaRules,
    is_thesis_formula_mode,
)
from src.config.heading_normalize import normalize_heading_numbering_payload
from src.config.special_title_rules import parse_special_title_selector
from src.config.style_semantics import (
    normalize_font_size_display_text,
    normalize_spacing_unit,
)
from src.modules.default_switches import default_module_switches
from src.shared.engine.font_resolver import canonicalize_font_name
from src.shared.engine.units import cn_size_to_pt

# ── 模块名 / 开关归一化 ─────────────────────────────

MODULE_SWITCH_ALIASES: dict[str, str] = {
    "equation_table_fmt": "equation_table_format",
    "formula_to_table": "equation_table_format",
    "formula_style": "equation_table_format",
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
    """Read the cycle-free canonical module-default catalog."""

    switches = default_module_switches()
    if not switches:
        raise RuntimeError("module registry contains no default switch metadata")
    return switches


# 延迟计算的缓存
_default_switches_cache: dict[str, bool] | None = None


def get_default_module_switches() -> dict[str, bool]:
    """获取默认模块开关（缓存结果，避免重复计算）。"""
    global _default_switches_cache
    if _default_switches_cache is None:
        _default_switches_cache = _build_default_module_switches()
    return dict(_default_switches_cache)


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
    2. 未实现 / 未注册的 key 明确拒绝
    3. 缺失的已注册模块补默认值
    """
    normalized = dict(defaults if defaults is not None else get_default_module_switches())
    canonical_items: list[tuple[str, bool]] = []
    unknown_names: list[str] = []
    legacy_formula_switches: list[bool] = []
    has_canonical_equation_switch = False

    for raw_name, enabled in (module_switches or {}).items():
        raw_name_text = str(raw_name)
        canonical_name = normalize_module_name(raw_name_text)
        if canonical_name not in normalized:
            unknown_names.append(raw_name_text)
            continue
        if raw_name_text in {"formula_to_table", "formula_style"}:
            legacy_formula_switches.append(bool(enabled))
            continue
        if raw_name_text in {"equation_table_format", "equation_table_fmt"}:
            has_canonical_equation_switch = True
        canonical_items.append((canonical_name, bool(enabled)))

    if unknown_names:
        names = ", ".join(sorted(dict.fromkeys(unknown_names)))
        raise ValueError(f"unknown module switch key(s): {names}")

    for canonical_name, enabled in canonical_items:
        normalized[canonical_name] = enabled
    if legacy_formula_switches and not has_canonical_equation_switch:
        # The V1 surface consolidates two V0.2 switches.  Enabling either old
        # structural/style pass must keep the consolidated rule enabled;
        # dictionary insertion order must not decide the result.
        normalized["equation_table_format"] = any(legacy_formula_switches)

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


def upgrade_legacy_user_template_layout_policies(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply bounded compatibility upgrades to a user template.

    This compatibility projection is intentionally narrow.  The strict
    canonical loader still rejects every other missing or unknown field, and
    callers must not persist the projected payload unless the user saves it.
    """

    upgraded = copy.deepcopy(dict(payload))
    # Formula behavior no longer belongs to templates.  Compatible loading may
    # discard these historical baseline copies because execution now reads the
    # migrated thesis-plan rule aggregate exclusively.
    for legacy_formula_root in (
        "formula_convert",
        "formula_to_table",
        "formula_table",
        "formula_style",
        "equation_table_format",
        "equation_numbering",
        "chem_typography",
    ):
        upgraded.pop(legacy_formula_root, None)
    page_setup = upgraded.get("page_setup")
    if isinstance(page_setup, Mapping):
        page_setup = dict(page_setup)
        page_setup.setdefault("paper_size_mode", "force_template")
        page_setup.setdefault("orientation_mode", "preserve_source")
        page_setup.setdefault("margin_mode", "force_template")
        page_setup.setdefault("paper_size_by_section", {})
        page_setup.setdefault("orientation_by_section", {})
        page_setup.setdefault("margin_by_section", {})
        upgraded["page_setup"] = page_setup

    section = upgraded.get("section")
    if isinstance(section, Mapping):
        section = dict(section)
        legacy_break_type = section.get("section_break_type")
        section.setdefault(
            "boundary_mode",
            "normalize_all" if legacy_break_type else "preserve_source",
        )
        section.setdefault("empty_break_policy", "preserve")
        section.setdefault("caption_table_break_policy", "preserve")
        header_footer = upgraded.get("header_footer")
        behavior = (
            header_footer.get("behavior")
            if isinstance(header_footer, Mapping)
            else None
        )
        link_to_previous = (
            str(behavior.get("link_to_previous", "") or "")
            if isinstance(behavior, Mapping)
            else ""
        )
        section.setdefault(
            "header_footer_link_mode",
            "semantic_rebuild"
            if link_to_previous == "never"
            else "preserve_source",
        )
        upgraded["section"] = section

    header_footer = upgraded.get("header_footer")
    if isinstance(header_footer, Mapping):
        header_footer = dict(header_footer)
        page_number_plan = header_footer.get("page_number_plan")
        if isinstance(page_number_plan, Mapping):
            page_number_plan = dict(page_number_plan)
            inherited_variant = {
                "visibility": "inherit",
                "template": "",
                "alignment": "inherit",
            }
            page_number_plan.setdefault("first", copy.deepcopy(inherited_variant))
            page_number_plan.setdefault("even", copy.deepcopy(inherited_variant))
            header_footer["page_number_plan"] = page_number_plan
        upgraded["header_footer"] = header_footer
    return upgraded


_THESIS_FORMULA_RULE_ROOTS = (
    "formula_convert",
    "formula_to_table",
    "formula_table",
    "formula_style",
    "equation_numbering",
    "chem_typography",
)


def upgrade_scene_formula_policy_ownership(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Move flat/template formula state into the thesis-plan rule aggregate.

    This is a deliberately narrow canonical-schema upgrade.  It accepts the
    immediately previous V1 representation and the corresponding V0.2 formula
    blocks, but it does not repair unrelated missing or unknown fields.
    """

    upgraded = copy.deepcopy(dict(payload))
    mode_id = str(upgraded.get("mode_id", "") or "").strip()
    if not mode_id:
        category = str(upgraded.get("category", "") or "").strip().casefold()
        if category == "thesis":
            mode_id = "thesis"
            upgraded["mode_id"] = mode_id

    rule_payload = asdict(ThesisFormulaRules())
    existing_rules = upgraded.get("thesis_formula_rules")
    canonical_rules = (
        copy.deepcopy(dict(existing_rules))
        if isinstance(existing_rules, Mapping)
        else None
    )
    formula_master_explicit = bool(
        isinstance(existing_rules, Mapping)
        and "formula_enabled" in existing_rules
    )
    if isinstance(existing_rules, Mapping):
        _merge_mapping_tree(rule_payload, existing_rules)

    explicit_enabled: set[str] = set()
    if isinstance(existing_rules, Mapping):
        for root in (
            "formula_convert",
            "formula_to_table",
            "formula_style",
            "equation_numbering",
            "chem_typography",
        ):
            value = existing_rules.get(root)
            if isinstance(value, Mapping) and "enabled" in value:
                explicit_enabled.add(root)

    for root in _THESIS_FORMULA_RULE_ROOTS:
        value = upgraded.pop(root, None)
        if isinstance(value, Mapping):
            block = copy.deepcopy(dict(value))
            if "enabled" in block:
                explicit_enabled.add(root)
            if root == "formula_table":
                block = _normalize_formula_table_payload(block)
            _merge_mapping_tree(rule_payload[root], block)

    equation_table = upgraded.pop("equation_table_format", None)
    if isinstance(equation_table, Mapping):
        if equation_table.get("enabled") is not None:
            explicit_enabled.add("equation_numbering")
            rule_payload["equation_numbering"]["enabled"] = bool(
                equation_table.get("enabled")
            )
        numbering_format = equation_table.get("numbering_format")
        if numbering_format not in (None, ""):
            rule_payload["equation_numbering"]["numbering_format"] = copy.deepcopy(
                numbering_format
            )
    for override_key in ("overrides", "template_overrides"):
        raw_overrides = upgraded.get(override_key)
        if not isinstance(raw_overrides, Mapping):
            continue
        nested = unflatten_dict(raw_overrides)
        for root in _THESIS_FORMULA_RULE_ROOTS:
            value = nested.get(root)
            if not isinstance(value, Mapping):
                continue
            block = copy.deepcopy(dict(value))
            if root == "formula_table":
                block = _normalize_formula_table_payload(block)
            _merge_mapping_tree(rule_payload[root], block)
        equation_override = nested.get("equation_table_format")
        if isinstance(equation_override, Mapping):
            if equation_override.get("enabled") is not None:
                rule_payload["equation_numbering"]["enabled"] = bool(
                    equation_override.get("enabled")
                )
            numbering_format = equation_override.get("numbering_format")
            if numbering_format not in (None, ""):
                rule_payload["equation_numbering"]["numbering_format"] = (
                    copy.deepcopy(numbering_format)
                )
        cleaned = {
            str(key): copy.deepcopy(value)
            for key, value in raw_overrides.items()
            if str(key).split(".", 1)[0]
            not in {*_THESIS_FORMULA_RULE_ROOTS, "equation_table_format"}
        }
        upgraded[override_key] = cleaned

    raw_switches = upgraded.get("module_switches")
    raw_switches = dict(raw_switches) if isinstance(raw_switches, Mapping) else {}
    capability_switches = _extract_switches_from_capabilities(
        upgraded.get("capabilities")
    )
    pipeline_switches = _extract_switches_from_pipeline(upgraded.get("pipeline"))
    switch_sources = {**pipeline_switches, **capability_switches, **raw_switches}

    if isinstance(upgraded.get("pipeline"), list):
        pipeline_names = {
            str(name) for name in upgraded.get("pipeline", [])
        }
        for root, accepted_names in (
            ("formula_convert", {"formula_convert"}),
            ("formula_to_table", {"formula_to_table"}),
            ("formula_style", {"formula_style"}),
            (
                "equation_numbering",
                {"equation_table_format", "equation_table_fmt"},
            ),
            (
                "chem_typography",
                {"chem_typography", "chem_typography_restore"},
            ),
        ):
            if root not in explicit_enabled and pipeline_names.isdisjoint(
                accepted_names
            ):
                rule_payload[root]["enabled"] = False

    if "formula_convert" not in explicit_enabled and "formula_convert" in switch_sources:
        rule_payload["formula_convert"]["enabled"] = bool(
            switch_sources["formula_convert"]
        )
    if "chem_typography" not in explicit_enabled:
        chem_switch = switch_sources.get(
            "chem_typography",
            switch_sources.get("chem_typography_restore"),
        )
        if chem_switch is not None:
            rule_payload["chem_typography"]["enabled"] = bool(chem_switch)
    for root, switch_name in (
        ("formula_to_table", "formula_to_table"),
        ("formula_style", "formula_style"),
        ("equation_numbering", "equation_table_format"),
    ):
        if root not in explicit_enabled and switch_name in switch_sources:
            rule_payload[root]["enabled"] = bool(switch_sources[switch_name])

    # The immediately previous V1 schema had one composite switch.  Use it as
    # a fallback for legacy sub-passes that did not persist their own state.
    if "equation_table_format" in switch_sources:
        combined_enabled = bool(switch_sources["equation_table_format"])
        for root in ("formula_to_table", "formula_style", "equation_numbering"):
            if root not in explicit_enabled and root not in switch_sources:
                rule_payload[root]["enabled"] = combined_enabled

    if not formula_master_explicit:
        # Older payloads had no master gate. Infer it from their effective
        # child workflow so migration neither activates nor suppresses work.
        rule_payload["formula_enabled"] = any(
            bool(rule_payload[root].get("enabled", False))
            for root in (
                "formula_convert",
                "formula_to_table",
                "formula_style",
                "equation_numbering",
            )
        )

    # A mixed transitional payload may contain both the canonical nested owner
    # and stale V0/V1 root blocks. Legacy blocks only fill gaps; explicitly
    # persisted canonical values must win the final merge.
    if canonical_rules is not None:
        _merge_mapping_tree(rule_payload, canonical_rules)

    cleaned_switches = {
        str(key): copy.deepcopy(value)
        for key, value in raw_switches.items()
        if normalize_module_name(str(key)) not in THESIS_FORMULA_MODULE_NAMES
    }
    upgraded["module_switches"] = cleaned_switches

    if is_thesis_formula_mode(mode_id):
        upgraded["thesis_formula_rules"] = rule_payload
    else:
        upgraded["thesis_formula_rules"] = None
    return upgraded


def _merge_mapping_tree(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        current = target.get(str(key))
        if isinstance(current, dict) and isinstance(value, Mapping):
            _merge_mapping_tree(current, value)
        else:
            target[str(key)] = copy.deepcopy(value)


def _add_header_footer_compat_aliases(flat: dict[str, Any]) -> None:
    prefix = "header_footer."
    if not any(key.startswith(prefix) for key in flat):
        return

    if "header_footer.header.mode" in flat:
        flat.setdefault("header_footer.header_mode", flat["header_footer.header.mode"])
    if "header_footer.header.enabled" in flat:
        flat.setdefault("header_footer.header_enabled", flat["header_footer.header.enabled"])
    if "header_footer.header.fixed_text" in flat:
        flat.setdefault("header_footer.header_text", flat["header_footer.header.fixed_text"])
    if "header_footer.header.alignment" in flat:
        flat.setdefault("header_footer.header_alignment", flat["header_footer.header.alignment"])
    if "header_footer.header.styleref_level" in flat:
        flat.setdefault(
            "header_footer.styleref_level",
            flat["header_footer.header.styleref_level"],
        )
    if "header_footer.header.border" in flat:
        flat.setdefault("header_footer.header_border", flat["header_footer.header.border"])
    if "header_footer.header.typography.font_cn" in flat:
        flat.setdefault("header_footer.font_cn", flat["header_footer.header.typography.font_cn"])
    if "header_footer.header.typography.font_en" in flat:
        flat.setdefault("header_footer.font_en", flat["header_footer.header.typography.font_en"])
    if "header_footer.header.typography.size_pt" in flat:
        flat.setdefault("header_footer.size_pt", flat["header_footer.header.typography.size_pt"])
    if "header_footer.header.typography.bold" in flat:
        flat.setdefault("header_footer.bold", flat["header_footer.header.typography.bold"])
    if "header_footer.header.typography.italic" in flat:
        flat.setdefault("header_footer.italic", flat["header_footer.header.typography.italic"])

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

    if "header_footer.page_number_plan.enabled" in flat:
        flat.setdefault(
            "header_footer.page_number_enabled",
            flat["header_footer.page_number_plan.enabled"],
        )
    elif "header_footer.footer.content_mode" in flat:
        footer_mode = str(
            flat.get("header_footer.footer.content_mode", "page_number") or "page_number"
        )
        flat.setdefault(
            "header_footer.page_number_enabled",
            footer_mode in {"page_number", "page_number_with_text"},
        )
    if "header_footer.page_number_plan.template" in flat:
        flat.setdefault(
            "header_footer.page_number_template",
            flat["header_footer.page_number_plan.template"],
        )
    if "header_footer.page_number_plan.alignment" in flat:
        flat.setdefault(
            "header_footer.page_number_alignment",
            flat["header_footer.page_number_plan.alignment"],
        )
    if "header_footer.footer.enabled" in flat:
        flat.setdefault("header_footer.footer_enabled", flat["header_footer.footer.enabled"])
    if "header_footer.footer.fixed_text" in flat:
        flat.setdefault("header_footer.footer_text", flat["header_footer.footer.fixed_text"])
    if "header_footer.footer.alignment" in flat:
        flat.setdefault("header_footer.footer_alignment", flat["header_footer.footer.alignment"])

    if (
        "header_footer.header.hidden_selectors" in flat
        or "header_footer.footer.hidden_selectors" in flat
    ):
        header_hidden = set(flat.get("header_footer.header.hidden_selectors") or [])
        footer_hidden = set(flat.get("header_footer.footer.hidden_selectors") or [])
        flat.setdefault(
            "header_footer.hide_cover_header_footer",
            "cover" in header_hidden and "cover" in footer_hidden,
        )
    elif (
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
    "page_number_template",
    "page_number_alignment",
    "footer_text",
    "footer_alignment",
    "header_border",
    "hide_cover_header_footer",
    "suppress_header_footer_selectors",
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
        _normalize_toc_style_keys(styles)
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


def _normalize_toc_style_keys(styles: dict[str, dict[str, Any]]) -> None:
    """Keep legacy TOC style payloads loadable without generating new role styles."""
    return


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
        legacy_value_key = f"formula_space_{slot}_value"
        unit_key = f"formula_space_{slot}_unit"
        if value_key not in payload and legacy_value_key in payload:
            payload[value_key] = payload.get(legacy_value_key)
        payload.pop(legacy_value_key, None)
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


_PAGE_SCOPE_LEAVES: tuple[str, ...] = (
    "cover",
    "abstract_cn",
    "abstract_en",
    "toc",
    "body",
    "references",
    "errata",
    "appendix",
    "acknowledgment",
    "resume",
)

_PAGE_SCOPE_GROUPS: dict[str, tuple[str, ...]] = {
    "pre_numbering": ("cover",),
    "front_matter": ("abstract_cn", "abstract_en", "toc"),
    "abstracts": ("abstract_cn", "abstract_en"),
    "back_matter": (
        "references",
        "errata",
        "appendix",
        "acknowledgment",
        "resume",
    ),
    "all_numbered_content": (
        "abstract_cn",
        "abstract_en",
        "toc",
        "body",
        "references",
        "errata",
        "appendix",
        "acknowledgment",
        "resume",
    ),
}

_REMOVED_IMPLICIT_PAGE_SCOPE_SELECTORS = frozenset(
    {"statement", "authorization", "front_note"}
)


def normalize_page_scope_selectors(selectors: Any) -> list[str]:
    """Expand supported groups and retain only explicit, executable scopes."""

    if not isinstance(selectors, (list, tuple)):
        return []
    expanded: list[str] = []
    for raw_selector in selectors:
        selector = str(raw_selector or "").strip()
        if not selector or selector in _REMOVED_IMPLICIT_PAGE_SCOPE_SELECTORS:
            continue
        for candidate in _PAGE_SCOPE_GROUPS.get(selector, (selector,)):
            if candidate in _REMOVED_IMPLICIT_PAGE_SCOPE_SELECTORS:
                continue
            if (
                candidate not in _PAGE_SCOPE_LEAVES
                and parse_special_title_selector(candidate) is None
            ):
                continue
            if candidate not in expanded:
                expanded.append(candidate)
    return expanded


def _normalize_header_footer_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _copy_mapping(payload)

    update_header = normalized.pop("update_header", None)
    update_page_number = normalized.pop("update_page_number", None)
    update_header_line = normalized.pop("update_header_line", None)

    legacy_typography = (
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
    behavior = (
        _copy_mapping(normalized.get("behavior"))
        if isinstance(normalized.get("behavior"), Mapping)
        else {}
    )
    variants = (
        _copy_mapping(normalized.get("variants"))
        if isinstance(normalized.get("variants"), Mapping)
        else {}
    )

    legacy_variant_footer_modes: dict[str, str] = {}
    legacy_variant_footer_templates: dict[str, str] = {}
    for variant_name in ("default", "first", "even"):
        variant = (
            _copy_mapping(variants.get(variant_name))
            if isinstance(variants.get(variant_name), Mapping)
            else {}
        )
        variant_footer = (
            _copy_mapping(variant.get("footer"))
            if isinstance(variant.get("footer"), Mapping)
            else {}
        )
        legacy_mode = str(variant_footer.get("mode", "inherit") or "inherit").strip().lower()
        legacy_variant_footer_modes[variant_name] = legacy_mode
        legacy_variant_footer_templates[variant_name] = str(
            variant_footer.get("template", "") or ""
        )
        if legacy_mode == "page_number":
            variant_footer["mode"] = "none"
            variant_footer["fixed_text"] = ""
            variant_footer["template"] = ""
        elif legacy_mode == "page_number_with_text":
            variant_footer["mode"] = "fixed"
            variant_footer["template"] = ""
        elif legacy_mode == "template" and "{page}" in legacy_variant_footer_templates[variant_name]:
            variant_footer["mode"] = (
                "fixed" if str(variant_footer.get("fixed_text", "") or "") else "none"
            )
            variant_footer["template"] = ""
        variant["footer"] = variant_footer
        variants[variant_name] = variant

    header_typography = (
        _copy_mapping(header.get("typography"))
        if isinstance(header.get("typography"), Mapping)
        else {}
    )
    footer_typography = (
        _copy_mapping(footer.get("typography"))
        if isinstance(footer.get("typography"), Mapping)
        else {}
    )
    for key in ("font_cn", "font_en", "size_pt", "bold", "italic"):
        if key in legacy_typography and key not in header_typography:
            header_typography[key] = legacy_typography[key]
        if key in normalized and key not in header_typography:
            header_typography[key] = normalized[key]
    if "bold" in header_typography:
        header_typography["bold"] = bool(header_typography["bold"])
    if "italic" in header_typography:
        header_typography["italic"] = bool(header_typography["italic"])
    if "bold" in footer_typography:
        footer_typography["bold"] = bool(footer_typography["bold"])
    if "italic" in footer_typography:
        footer_typography["italic"] = bool(footer_typography["italic"])

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
    if "alignment" not in header:
        header["alignment"] = str(normalized.get("header_alignment", "center") or "center")
    header["alignment"] = str(header.get("alignment", "center") or "center").strip().lower()
    if header["alignment"] not in {"left", "center", "right"}:
        header["alignment"] = "center"
    if "styleref_level" not in header:
        header["styleref_level"] = int(normalized.get("styleref_level", 1) or 1)
    if "border" not in header:
        if "header_border" in normalized:
            header["border"] = bool(normalized["header_border"])
        elif update_header_line is not None:
            header["border"] = bool(update_header_line)
        else:
            header["border"] = True
    if not isinstance(header.get("border_style"), Mapping):
        header["border_style"] = {}
    if "enabled" not in header["border_style"]:
        header["border_style"]["enabled"] = bool(header.get("border", True))

    hide_cover = normalized.get("hide_cover_header_footer")
    if "enabled" not in header:
        header["enabled"] = bool(normalized.get("header_enabled", True))
    header["typography"] = header_typography
    if "content_mode" not in footer:
        page_number_enabled = normalized.get("page_number_enabled")
        if page_number_enabled is None and update_page_number is not None:
            page_number_enabled = bool(update_page_number)
        footer_text = str(normalized.get("footer_text", "") or footer.get("fixed_text", "") or "")
        if page_number_enabled is False:
            legacy_footer_content_mode = "fixed" if footer_text else "none"
        elif footer_text:
            legacy_footer_content_mode = "page_number_with_text"
        else:
            legacy_footer_content_mode = "page_number"
    else:
        legacy_footer_content_mode = str(
            footer.get("content_mode", "page_number") or "page_number"
        )
    footer["content_mode"] = (
        "fixed"
        if legacy_footer_content_mode in {"fixed", "page_number_with_text"}
        else "none"
    )
    if "fixed_text" not in footer:
        footer["fixed_text"] = str(normalized.get("footer_text", "") or "")
    if "alignment" not in footer:
        footer["alignment"] = str(normalized.get("footer_alignment", "center") or "center")
    footer["alignment"] = str(footer.get("alignment", "center") or "center").strip().lower()
    if footer["alignment"] not in {"left", "center", "right"}:
        footer["alignment"] = "center"
    if "enabled" not in footer:
        footer["enabled"] = bool(normalized.get("footer_enabled", True))
    footer["typography"] = footer_typography

    suppress_selectors_raw = normalized.get("suppress_header_footer_selectors")
    legacy_common_hidden = normalize_page_scope_selectors(suppress_selectors_raw)
    legacy_header_hide_cover = bool(
        header.pop("hide_on_cover", True if hide_cover is None else bool(hide_cover))
    )
    legacy_footer_hide_cover = bool(
        footer.pop("hide_on_cover", True if hide_cover is None else bool(hide_cover))
    )
    if not legacy_common_hidden and legacy_header_hide_cover and legacy_footer_hide_cover:
        legacy_common_hidden = list(_PAGE_SCOPE_GROUPS["pre_numbering"])

    header_hidden_explicit = isinstance(header.get("hidden_selectors"), list)
    footer_hidden_explicit = isinstance(footer.get("hidden_selectors"), list)
    header_hidden = normalize_page_scope_selectors(header.get("hidden_selectors"))
    footer_hidden = normalize_page_scope_selectors(footer.get("hidden_selectors"))
    if not header_hidden_explicit:
        header_hidden = list(legacy_common_hidden)
        if not header_hidden and legacy_header_hide_cover:
            header_hidden = ["cover"]
    if not footer_hidden_explicit:
        footer_hidden = list(legacy_common_hidden)
        if not footer_hidden and legacy_footer_hide_cover:
            footer_hidden = ["cover"]
    header["hidden_selectors"] = header_hidden
    footer["hidden_selectors"] = footer_hidden

    phases_raw = page_number_plan.get("phases")
    phases: list[dict[str, Any]] = []
    if isinstance(phases_raw, list):
        for item in phases_raw:
            if not isinstance(item, Mapping):
                continue
            phases.append(
                {
                    "phase_id": str(item.get("phase_id", "") or ""),
                    "selectors": normalize_page_scope_selectors(item.get("selectors", [])),
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
                "selectors": ["abstract_cn", "abstract_en", "toc"],
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
                "selectors": [
                    "body",
                    "references",
                    "errata",
                    "appendix",
                    "acknowledgment",
                    "resume",
                ],
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

    covered_roles = {
        selector
        for phase in phases
        for selector in phase.get("selectors", [])
    }
    hidden_legacy_roles = [
        role for role in legacy_common_hidden if role not in covered_roles
    ]
    if hidden_legacy_roles:
        phases.insert(
            0,
            {
                "phase_id": "pre_numbering",
                "selectors": hidden_legacy_roles,
                "visible": False,
                "number_format": "decimal",
                "start_mode": "restart",
                "start_value": 1,
            },
        )

    legacy_page_number_enabled = normalized.get("page_number_enabled")
    if legacy_page_number_enabled is None and update_page_number is not None:
        legacy_page_number_enabled = bool(update_page_number)
    if legacy_page_number_enabled is None:
        legacy_page_number_enabled = bool(footer.get("enabled", True)) and (
            legacy_footer_content_mode in {"page_number", "page_number_with_text"}
        )

    legacy_template = footer.pop("page_number_template", None)
    page_number_plan["enabled"] = bool(
        page_number_plan.get("enabled", legacy_page_number_enabled)
    )
    page_number_plan["template"] = str(
        page_number_plan.get(
            "template",
            legacy_template
            if legacy_template is not None
            else normalized.get("page_number_template", "{page}"),
        )
        or "{page}"
    )
    page_number_plan["alignment"] = str(
        page_number_plan.get(
            "alignment",
            normalized.get("page_number_alignment", footer.get("alignment", "center")),
        )
        or "center"
    ).strip().lower()
    if page_number_plan["alignment"] not in {"left", "center", "right"}:
        page_number_plan["alignment"] = "center"
    page_number_plan["phases"] = phases
    page_number_plan["on_missing_doc_tree"] = str(
        page_number_plan.get("on_missing_doc_tree", "warn_and_fallback")
        or "warn_and_fallback"
    )
    page_number_plan["validation_mode"] = str(
        page_number_plan.get("validation_mode", "strict") or "strict"
    )

    for variant_name in ("first", "even"):
        raw_variant = (
            _copy_mapping(page_number_plan.get(variant_name))
            if isinstance(page_number_plan.get(variant_name), Mapping)
            else {}
        )
        legacy_mode = legacy_variant_footer_modes.get(variant_name, "inherit")
        default_visibility = (
            "show"
            if legacy_mode in {"page_number", "page_number_with_text", "template"}
            else "inherit"
        )
        visibility = str(
            raw_variant.get("visibility", default_visibility) or default_visibility
        ).strip().lower()
        if visibility not in {"inherit", "show", "hide"}:
            visibility = "inherit"
        alignment = str(raw_variant.get("alignment", "inherit") or "inherit").strip().lower()
        if alignment not in {"inherit", "left", "center", "right"}:
            alignment = "inherit"
        template = str(raw_variant.get("template", "") or "")
        if not template and legacy_mode in {"page_number", "page_number_with_text", "template"}:
            template = legacy_variant_footer_templates.get(variant_name, "")
        page_number_plan[variant_name] = {
            "visibility": visibility,
            "template": template,
            "alignment": alignment,
        }

    return {
        "header": header,
        "footer": footer,
        "behavior": behavior,
        "variants": variants,
        "page_number_plan": page_number_plan,
    }


def normalize_header_footer_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Public compatibility boundary for standalone header/footer presets."""

    return _normalize_header_footer_payload(payload or {})


# ── Scene normalize ─────────────────────────────────

_SCENE_META_KEYS = (
    "name",
    "description",
    "category",
    "category_label",
    "scene_id",
    "mode_id",
    "display_order",
    "template_id",
    "compatible_template_ids",
    "master_id",
)

_LEGACY_SCENE_OPTION_BLOCKS: tuple[tuple[str, str | None, str | None], ...] = (
    ("md_cleanup", "md_cleanup", "md_cleanup"),
    ("whitespace_normalize", "whitespace", "whitespace_normalize"),
    ("whitespace", "whitespace", "whitespace_normalize"),
    ("citation_link", "citation_link", "citation_link"),
    ("formula_convert", "formula_convert", "formula_convert"),
    ("formula_to_table", None, "equation_table_format"),
    ("formula_style", "formula_style", "equation_table_format"),
    ("chem_typography", "chem_typography", "chem_typography"),
    ("equation_table_format", None, "equation_table_format"),
)

_SCENE_DIRECT_FEATURE_ROOTS = ("reference_style",)

_SCENE_LIFTED_TEMPLATE_KEYS = {
    "page_setup",
    "styles",
    "heading_numbering",
    "heading_numbering_v2",
    "heading_model",
    "heading",
    "section",
    "watermark",
    "reference_style",
}
_SCENE_LIFTED_TEMPLATE_ROOTS = {
    "page_setup",
    "styles",
    "heading_numbering",
    "heading_model",
    "section",
    "watermark",
    "reference_style",
}


def normalize_scene_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """将场景 / 混合 legacy payload 归一为当前 SceneWorkspace 结构。"""
    raw = upgrade_scene_formula_policy_ownership(_copy_mapping(payload))
    normalized: dict[str, Any] = {}

    for key in _SCENE_META_KEYS:
        if key in raw:
            normalized[key] = copy.deepcopy(raw[key])

    if isinstance(raw.get("thesis_formula_rules"), Mapping):
        normalized["thesis_formula_rules"] = _copy_mapping(
            raw.get("thesis_formula_rules")
        )
    else:
        normalized["thesis_formula_rules"] = None

    # 0.2 scenes predate ``mode_id``. Its built-in thesis presets identified
    # themselves through ``category=thesis``; retain that execution identity
    # so the explicitly enabled block-formula containerization is not lost.
    if not str(normalized.get("mode_id", "") or "").strip():
        legacy_category = str(raw.get("category", "") or "").strip().casefold()
        if legacy_category == "thesis":
            normalized["mode_id"] = "thesis"

    if isinstance(raw.get("document_scope"), Mapping):
        normalized["document_scope"] = {
            key: copy.deepcopy(value)
            for key, value in raw["document_scope"].items()
            if key in {"mode", "selected_roles"}
        }
    if isinstance(raw.get("exam_paper"), Mapping):
        normalized["exam_paper"] = {
            key: copy.deepcopy(value)
            for key, value in raw["exam_paper"].items()
            if key
            in {
                "question_structure_mode",
                "answer_policy",
                "custom_blank_styles",
                "runtime_fields",
            }
        }
    input_source_profile = raw.get("input_source_profile")
    if not isinstance(input_source_profile, Mapping):
        input_source_profile = raw.get("input_sources")
    if isinstance(input_source_profile, Mapping):
        normalized["input_source_profile"] = _copy_mapping(input_source_profile)

    compliance_profile = raw.get("compliance_profile")
    if not isinstance(compliance_profile, Mapping):
        compliance_profile = raw.get("compliance")
    if isinstance(compliance_profile, Mapping):
        normalized["compliance_profile"] = _copy_mapping(compliance_profile)
    if isinstance(raw.get("object_preservation"), Mapping):
        compliance_payload = _copy_mapping(normalized.get("compliance_profile"))
        compliance_payload.setdefault(
            "object_preflight",
            _copy_mapping(raw.get("object_preservation")),
        )
        normalized["compliance_profile"] = compliance_payload

    delivery_presets = raw.get("delivery_presets")
    delivery_payload = raw.get("delivery")
    if isinstance(delivery_payload, Mapping):
        if "default_preset_id" in delivery_payload:
            normalized["default_delivery_preset_id"] = str(
                delivery_payload.get("default_preset_id") or ""
            )
        if not isinstance(delivery_presets, list):
            delivery_presets = delivery_payload.get("presets")
    if "default_delivery_preset_id" in raw:
        normalized["default_delivery_preset_id"] = str(
            raw.get("default_delivery_preset_id") or ""
        )
    if isinstance(delivery_presets, list):
        normalized["delivery_presets"] = [
            _copy_mapping(item)
            for item in delivery_presets
            if isinstance(item, Mapping)
        ]

    pipeline_switches = _extract_switches_from_pipeline(raw.get("pipeline"))
    capability_switches = _extract_switches_from_capabilities(raw.get("capabilities"))
    direct_switches = raw.get("module_switches") if isinstance(raw.get("module_switches"), Mapping) else {}

    if isinstance(raw.get("pipeline"), list):
        switch_defaults: dict[str, bool] = {
            name: False for name in get_default_module_switches()
        }
    else:
        switch_defaults = dict(get_default_module_switches())

    # Keep user-provided switches separate from defaults until canonical
    # normalization. Otherwise a default canonical ``False`` looks explicit
    # and suppresses legacy formula aliases that were actually enabled.
    switches: dict[str, Any] = {}
    switches.update(pipeline_switches)
    switches.update(capability_switches)
    switches.update(copy.deepcopy(dict(direct_switches)))

    legacy_equation_switches: list[bool] = []
    has_canonical_equation_switch = "equation_table_format" in {
        *pipeline_switches,
        *capability_switches,
        *direct_switches,
    }

    for legacy_key, target_attr, module_name in _LEGACY_SCENE_OPTION_BLOCKS:
        block = raw.get(legacy_key)
        if not isinstance(block, Mapping):
            continue
        block_data = copy.deepcopy(dict(block))
        enabled = block_data.pop("enabled", None)
        if target_attr is not None:
            normalized[target_attr] = block_data
        if legacy_key == "equation_table_format":
            numbering_format = block_data.get("numbering_format")
            if numbering_format not in (None, ""):
                normalized.setdefault("equation_numbering", {}).setdefault(
                    "numbering_format",
                    copy.deepcopy(numbering_format),
                )
            if enabled is not None:
                has_canonical_equation_switch = True
        if (
            legacy_key in {"formula_to_table", "formula_style"}
            and enabled is not None
        ):
            legacy_equation_switches.append(bool(enabled))
            continue
        if module_name is not None and enabled is not None:
            switches[module_name] = bool(enabled)

    if legacy_equation_switches and not has_canonical_equation_switch:
        switches["equation_table_format"] = any(legacy_equation_switches)

    normalized["module_switches"] = normalize_module_switches(
        switches,
        defaults=switch_defaults,
    )
    for module_name in THESIS_FORMULA_MODULE_NAMES:
        normalized["module_switches"].pop(module_name, None)

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
    remaining_overrides = {
        key: value
        for key, value in remaining_overrides.items()
        if key != "output" and not str(key).startswith("output.")
    }

    if "reference_style" in direct_feature_payloads:
        normalized["reference_style"] = _normalize_reference_style_payload(
            direct_feature_payloads["reference_style"]
        )

    if remaining_overrides:
        normalized["template_overrides"] = remaining_overrides

    compatible_template_ids = normalized.get("compatible_template_ids")
    if isinstance(compatible_template_ids, list):
        normalized["compatible_template_ids"] = list(
            dict.fromkeys(
                str(item).strip()
                for item in compatible_template_ids
                if str(item or "").strip()
            )
        )

    return normalized


def _extract_switches_from_capabilities(
    capabilities: Any,
) -> dict[str, bool]:
    if not isinstance(capabilities, Mapping):
        return {}
    return {
        str(name): bool(enabled)
        for name, enabled in capabilities.items()
    }


def _extract_switches_from_pipeline(pipeline: Any) -> dict[str, bool]:
    if not isinstance(pipeline, list):
        return {}
    return {str(name): True for name in pipeline}


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
        and str(key).split(".", 1)[0] in _SCENE_LIFTED_TEMPLATE_ROOTS
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
