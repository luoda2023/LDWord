"""Unified summary projection for template detail panes."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.style_semantics import (
    format_spacing_value,
    line_spacing_display_label,
    normalize_line_spacing_type,
    resolve_line_spacing_value,
    resolve_style_paragraph_spacing,
    resolve_style_special_indent,
)
from src.config.style_variant_semantics import get_effective_style, is_variant_overridden
from src.config.table_style_presets import color_palette, color_variant, table_style_label
from src.config.template import StyleConfig, TemplateConfig
from src.shared.engine.toc_style_ops import resolve_toc_style_config
from src.shared.ui.summary_grid import SummaryGridItem
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter


@dataclass(frozen=True, slots=True)
class TemplateSummaryTileSpec:
    key: str
    label: str
    value: str
    detail: str = ""
    icon_name: str = ""
    detail_emphasis: bool = True
    preferred_span: int | None = None
    min_span: int = 2
    tooltip: str = ""


@dataclass(frozen=True, slots=True)
class TemplateDetailSummarySpec:
    detail_card_id: str
    title: str
    icon_name: str
    nav_label: str
    nav_summary: str
    field_names: tuple[str, ...]
    tiles: tuple[TemplateSummaryTileSpec, ...]


DETAIL_ORDER: tuple[str, ...] = (
    "tpl_page",
    "tpl_style",
    "tpl_heading",
    "tpl_table",
    "tpl_header_footer",
    "tpl_toc",
    "tpl_caption",
)


ALIGNMENT_LABELS = {
    "left": "左对齐",
    "center": "居中",
    "right": "右对齐",
    "justify": "两端对齐",
    "": "不调整",
    None: "不调整",
}

TABLE_LAYOUT_LABELS = {
    "smart": "智能布局",
    "compact": "紧凑布局",
    "full": "撑满布局",
    "keep": "保留原样",
}

TABLE_LINE_SPACING_LABELS = {
    "single": "单倍",
    "one_half": "1.5 倍",
    "double": "双倍",
}

TABLE_ALIGNMENT_LABELS = {
    None: "不调整",
    "": "不调整",
    "left": "左对齐",
    "center": "居中",
    "right": "右对齐",
}

TOC_MODE_LABELS = {
    "word_native": "Word 自动目录",
    "plain": "普通目录",
}

TOC_INSERT_LABELS = {
    "auto": "自动位置",
    "after_cover": "封面后",
    "0": "文档起始",
}


def _paper_label(size: str) -> str:
    return str(size or "A4").upper()


def _orientation_label(orientation: str) -> str:
    return "横向" if str(orientation or "portrait") == "landscape" else "纵向"


def _section_break_label(value: str | None) -> str:
    return {
        "nextPage": "下一页分节",
        "continuous": "连续分节",
        "": "不设置",
        None: "不设置",
    }.get(value, str(value))


def _cm_text(value: float) -> str:
    return f"{float(value):g} cm"


def _size_text(style: StyleConfig) -> str:
    if style.size_display:
        return style.size_display
    if style.size_pt:
        return f"{style.size_pt:g}磅"
    return "默认字号"


def _size_label(size_display: str, size_pt: float | None) -> str:
    if size_display:
        return size_display
    if size_pt is None:
        return "默认字号"
    return f"{size_pt:g}磅"


def _plain_size_text(size_pt: float | None) -> str:
    if size_pt in (None, ""):
        return "默认字号"
    return f"{float(size_pt):g} 磅"


def _emphasis_text(style) -> str:
    parts: list[str] = []
    if bool(getattr(style, "bold", False)):
        parts.append("加粗")
    if bool(getattr(style, "italic", False)):
        parts.append("斜体")
    return " / ".join(parts) if parts else "常规"


def _emphasis_text_cn(style) -> str:
    parts: list[str] = []
    if bool(getattr(style, "bold", False)):
        parts.append("加粗")
    if bool(getattr(style, "italic", False)):
        parts.append("斜体")
    return "、".join(parts) if parts else "常规"


def _typography_detail_text(typography) -> str:
    return (
        f"{getattr(typography, 'font_cn', None) or '-'} / "
        f"{getattr(typography, 'font_en', None) or '-'} / "
        f"{_plain_size_text(getattr(typography, 'size_pt', None))} / "
        f"{_emphasis_text_cn(typography)}"
    )


def _indent_value_text(value: float, unit: str) -> str:
    unit_label = {"chars": "字", "pt": "磅", "cm": "cm"}.get(str(unit), str(unit))
    return f"{float(value):g}{unit_label}"


def _special_indent_text(style: StyleConfig) -> str:
    special = resolve_style_special_indent(style)
    if special["mode"] == "first_line" and float(special["value"]) > 0:
        return f"首行 {_indent_value_text(float(special['value']), str(special['unit']))}"
    if special["mode"] == "hanging" and float(special["value"]) > 0:
        return f"悬挂 {_indent_value_text(float(special['value']), str(special['unit']))}"
    return "无特殊缩进"


def _line_spacing_text(style: StyleConfig) -> str:
    line_kind = normalize_line_spacing_type(style.line_spacing_type)
    value = resolve_line_spacing_value(line_kind, style.line_spacing_pt)
    label = line_spacing_display_label(line_kind)
    if line_kind == "exact":
        return f"{label} {value:g} 磅"
    if line_kind == "multiple":
        return f"{label} {value:g} 倍"
    return label


def _line_spacing_label(kind: str, value: float) -> str:
    label = line_spacing_display_label(kind)
    if label == "固定值":
        return f"固定{value:g}磅"
    if kind in {"single", "one_half", "double"}:
        return label
    return f"{value:g}倍"


def _style_summary_detail(style: StyleConfig) -> str:
    alignment = ALIGNMENT_LABELS.get(style.alignment, str(style.alignment or "未设置对齐"))
    return (
        f"{style.font_cn or '-'} / {style.font_en or '-'} / {_size_text(style)} / "
        f"{_emphasis_text(style)} / {alignment}"
    )


def _body_style(cfg: TemplateConfig) -> StyleConfig:
    return cfg.styles.get("body") or cfg.styles.get("normal") or StyleConfig()


def _caption_style(cfg: TemplateConfig) -> StyleConfig:
    return cfg.styles.get("caption") or cfg.styles.get("body") or cfg.styles.get("normal") or StyleConfig()


def _toc_role_style(cfg: TemplateConfig, role_key: str) -> StyleConfig:
    return resolve_toc_style_config(cfg.styles, role_key) or StyleConfig()


def _page_number_phase_scope_label(selectors: list[str]) -> str:
    selector_map = {
        "all_numbered_content": "全文",
        "front_matter": "前置部分",
        "body": "正文部分",
        "back_matter": "后置部分",
        "appendix": "附录",
        "references": "参考文献",
        "toc": "目录",
    }
    labels = [
        selector_map.get(str(selector or ""), str(selector or ""))
        for selector in selectors
        if str(selector or "").strip()
    ]
    if not labels:
        return "未设置范围"
    if labels == ["全文"]:
        return "全文"
    return "+".join(labels)


def _default_page_number_phases(header) -> list:
    phases = list(getattr(header.page_number_plan, "phases", []) or [])
    if phases:
        return phases
    return [
        type(
            "_DefaultPhase",
            (),
            {
                "selectors": ["all_numbered_content"],
                "visible": True,
                "number_format": "decimal",
                "start_mode": "restart",
                "start_value": 1,
            },
        )()
    ]


def _suppress_header_footer_summary(header) -> str:
    selector_map = {
        "pre_numbering": "封面及声明页",
        "cover": "封面",
        "statement": "声明页",
        "authorization": "授权书",
        "front_note": "说明页",
        "front_matter": "前置部分",
        "toc": "目录",
        "body": "正文部分",
        "back_matter": "后置部分",
        "references": "参考文献",
        "appendix": "附录",
        "abstracts": "摘要",
        "acknowledgment": "致谢",
        "errata": "勘误",
        "resume": "简历",
    }
    selectors = [
        str(selector or "").strip()
        for selector in (getattr(header, "suppress_header_footer_selectors", []) or [])
        if str(selector or "").strip()
    ]
    if not selectors and getattr(header, "hide_cover_header_footer", False):
        selectors = ["pre_numbering"]
    labels = [selector_map.get(selector, selector) for selector in selectors]
    return f"排除：{'+'.join(labels)}" if labels else ""


def _footer_content_summary(header) -> str:
    if not bool(getattr(getattr(header, "footer", None), "enabled", True)):
        return "页脚关闭"
    mode = str(getattr(header.footer, "content_mode", "page_number") or "page_number")
    footer_text = str(getattr(header, "footer_text", "") or "").strip()
    if mode in {"none", "page_number"}:
        return "底部文字：不显示"
    if mode in {"fixed", "page_number_with_text"}:
        return f"底部文字：{footer_text or '未填写'}"
    return "底部文字：不显示"


def _page_number_position_label(header) -> str:
    return {
        "left": "页脚左侧",
        "center": "页脚居中",
        "right": "页脚右侧",
    }.get(str(getattr(header, "footer_alignment", "center") or "center"), "页脚居中")


def _header_position_label(header) -> str:
    return {
        "left": "页眉左侧",
        "center": "页眉居中",
        "right": "页眉右侧",
    }.get(str(getattr(header, "header_alignment", "center") or "center"), "页眉居中")


def _page_number_template_label(header) -> str:
    template = str(getattr(header, "page_number_template", "{page}") or "{page}").strip() or "{page}"
    return {
        "{page}": "1",
        "第 {page} 页": "第 1 页",
        "第 {page} 页 / 共 {pages} 页": "第 1 页 / 共 10 页",
    }.get(template, "自定义格式")


def _page_number_summary_value(header) -> str:
    if not bool(getattr(header, "page_number_enabled", True)):
        return "不显示页码"
    return f"显示页码 / {_page_number_position_label(header)}"


def _page_number_summary_detail(header) -> str:
    if not bool(getattr(header, "page_number_enabled", True)):
        return "页码暂不输出"
    parts = [_page_number_template_label(header), _phase_result_summary(header).replace("页码：", "", 1)]
    suppress_summary = _suppress_header_footer_summary(header)
    if suppress_summary:
        parts.append(suppress_summary)
    return "；".join(part for part in parts if part)


def _phase_result_summary(header) -> str:
    if not bool(getattr(header, "page_number_enabled", True)):
        return "页码：不显示"
    phases = _default_page_number_phases(header)
    results: list[str] = []
    for phase in phases[:2]:
        scope = _page_number_phase_scope_label(list(getattr(phase, "selectors", []) or []))
        if not bool(getattr(phase, "visible", True)):
            results.append(f"{scope}不显示页码")
            continue
        fmt = {
            "decimal": "阿拉伯数字",
            "upperRoman": "大写罗马",
            "lowerRoman": "小写罗马",
        }.get(str(getattr(phase, "number_format", "decimal") or "decimal"), "阿拉伯数字")
        if str(getattr(phase, "start_mode", "restart") or "restart") == "continue":
            results.append(f"{scope}{fmt}续号")
        else:
            start_value = max(1, int(getattr(phase, "start_value", 1) or 1))
            results.append(f"{scope}{fmt}从 {start_value} 起")
    if len(phases) > 2:
        results.append(f"另 {len(phases) - 2} 项")
    return "页码：" + " / ".join(results)


def _header_summary_value(header_footer) -> str:
    if not bool(getattr(getattr(header_footer, "header", None), "enabled", True)):
        return "页眉关闭"
    mode = str(header_footer.header_mode or "styleref")
    if mode == "none":
        return "不显示顶部"
    if mode == "fixed":
        return "固定文字"
    return f"跟随 {header_footer.styleref_level} 级标题"


def _header_summary_detail(header_footer) -> str:
    if not bool(getattr(getattr(header_footer, "header", None), "enabled", True)):
        return "不输出页眉"
    mode = str(header_footer.header_mode or "styleref")
    typography_detail = _typography_detail_text(getattr(header_footer.header, "typography", None))
    position = _header_position_label(header_footer)
    if mode == "none":
        return "不输出顶部横线"
    if mode == "fixed":
        text = str(header_footer.header_text or "").strip() or "未填写固定文字"
        return f"{text} / {position} / {'顶部横线开启' if header_footer.header_border else '顶部横线关闭'} / {typography_detail}"
    return f"{position} / {typography_detail}"


def _footer_summary_value(header_footer) -> str:
    if not bool(getattr(getattr(header_footer, "footer", None), "enabled", True)):
        return "页脚关闭"
    mode = str(getattr(header_footer.footer, "content_mode", "page_number") or "page_number")
    if mode in {"fixed", "page_number_with_text"}:
        return "固定文字"
    return "不显示底部文字"


def _page_number_phase_result_brief(phase) -> str:
    scope = _page_number_phase_scope_label(list(getattr(phase, "selectors", []) or []))
    if not bool(getattr(phase, "visible", True)):
        return f"{scope}不显示页码"
    fmt = {
        "decimal": "阿拉伯数字",
        "upperRoman": "大写罗马",
        "lowerRoman": "小写罗马",
    }.get(str(getattr(phase, "number_format", "decimal") or "decimal"), "阿拉伯数字")
    if str(getattr(phase, "start_mode", "restart") or "restart") == "continue":
        return f"{scope}{fmt}续号"
    start_value = max(1, int(getattr(phase, "start_value", 1) or 1))
    return f"{scope}{fmt}从 {start_value} 起"


def _footer_summary_detail(header_footer) -> str:
    if not bool(getattr(getattr(header_footer, "footer", None), "enabled", True)):
        return "不输出页脚"
    mode = str(getattr(header_footer.footer, "content_mode", "page_number") or "page_number")
    footer_text = str(getattr(header_footer, "footer_text", "") or "").strip()
    typography_detail = _typography_detail_text(getattr(header_footer.footer, "typography", None))
    if mode in {"fixed", "page_number_with_text"}:
        return f"{footer_text or '未填写固定文字'} / {typography_detail}"
    return f"页面底部不输出固定文字 / {typography_detail}"


def _toc_summary_value(toc) -> str:
    if not toc.enabled:
        return "目录关闭"
    mode_label = TOC_MODE_LABELS.get(toc.mode, toc.mode or "Word 自动目录")
    return f"{mode_label} / {int(toc.max_level or 3)} 级"


def _toc_summary_detail(toc) -> str:
    if not toc.enabled:
        return "不插入或更新目录"
    insert_label = TOC_INSERT_LABELS.get(str(toc.insert_position or "auto"), str(toc.insert_position or "auto"))
    return f"插入位置 {insert_label}"


def _toc_style_tile(cfg: TemplateConfig) -> TemplateSummaryTileSpec:
    if not cfg.toc.enabled:
        value = "目录关闭"
        detail = "样式暂不输出"
    else:
        title_style = _toc_role_style(cfg, "toc_title")
        entry_style = _toc_role_style(cfg, "toc_level1")
        value = f"标题 {_size_text(title_style)} / 条目 {_size_text(entry_style)}"
        detail = _style_summary_detail(entry_style)
    return TemplateSummaryTileSpec(
        key="toc_style",
        label="目录样式",
        value=value,
        detail=detail,
        icon_name="type-outline",
        preferred_span=6,
    )


def _table_width_summary_text(table) -> tuple[str, str]:
    border_mode = str(getattr(table, "border_mode", "") or "three_line")
    spacing_label = TABLE_LINE_SPACING_LABELS.get(table.line_spacing_mode, table.line_spacing_mode or "单倍")
    if border_mode == "three_line":
        return (
            f"外线 {table.three_line_header_width_pt:g} / 表头 {table.three_line_bottom_width_pt:g} 磅",
            f"表格行距 {spacing_label}",
        )
    if border_mode == "full_grid":
        return (
            f"网格 {table.border_width_pt:g} 磅",
            f"表格行距 {spacing_label}，表头下线不单独调整",
        )
    if border_mode == "color_table":
        variant = color_variant(getattr(table, "color_table_variant", "header_grid"))
        if variant.header_rule_only:
            return (
                f"外线 {table.three_line_header_width_pt:g} / 表头 {table.three_line_bottom_width_pt:g} 磅",
                f"表格行距 {spacing_label}，彩色三线表",
            )
        line_label = "网格线宽" if variant.show_vertical and variant.show_horizontal else "横线线宽"
        return (
            f"{line_label.replace('线宽', '')} {table.border_width_pt:g} 磅",
            f"表格行距 {spacing_label}，颜色表格按子样式应用线条",
        )
    if border_mode == "none":
        return "无边框", f"表格行距 {spacing_label}，线宽参数不生效"
    return "边框保留原样", f"表格行距 {spacing_label}，线宽参数不生效"


def _table_behavior_summary_text(table) -> str:
    first_row_text = "首行加粗" if bool(getattr(table, "first_row_bold", False)) else "不首行加粗"
    repeat_header_text = "跨页重复表头" if table.repeat_header else "不跨页重复表头"
    table_alignment_label = TABLE_ALIGNMENT_LABELS.get(
        getattr(table, "table_alignment", "center") or "",
        "不调整",
    )
    return f"{first_row_text} / {repeat_header_text} / 表格{table_alignment_label}"


def _table_behavior_visible_flags(table) -> list[str]:
    flags: list[str] = []
    if bool(getattr(table, "first_row_bold", False)):
        flags.append("首行加粗")
    if bool(getattr(table, "repeat_header", False)):
        flags.append("重复表头")
    return flags


def _table_alignment_tile_text(table) -> str:
    table_alignment_label = TABLE_ALIGNMENT_LABELS.get(
        getattr(table, "table_alignment", "center") or "",
        "不调整",
    )
    return f"表格{table_alignment_label}"


def _table_type_tile_detail(table, cell_alignment_label: str) -> str:
    size_text = f"{table.size_pt:g} 磅" if table.size_pt else "默认字号"
    parts = [size_text, _table_alignment_tile_text(table)]
    emphasis = _table_emphasis_summary_text(table)
    if emphasis != "常规":
        parts.append(emphasis)
    if cell_alignment_label != "不调整":
        parts.append(f"单元格{cell_alignment_label}")
    parts.extend(_table_behavior_visible_flags(table))
    return " / ".join(parts)


def _table_emphasis_summary_text(table) -> str:
    parts: list[str] = []
    if bool(getattr(table, "bold", False)):
        parts.append("加粗")
    if bool(getattr(table, "italic", False)):
        parts.append("斜体")
    return "、".join(parts) if parts else "常规"


def _heading_preset_label(adapter: HeadingNumberingAdapter) -> str:
    preset_key = adapter.detect_active_preset()
    if not preset_key:
        return "自定义"
    from src.config.heading_presets import PRESET_CATALOG

    return PRESET_CATALOG.get(preset_key, {}).get("label", preset_key)


def _ellipsis_join(parts: list[str], *, max_items: int = 2) -> str:
    visible = [part for part in parts[:max_items] if part]
    if not visible:
        return ""
    if len(parts) > len(visible):
        visible.append("...")
    return "/".join(visible)


def _heading_preview_values(adapter: HeadingNumberingAdapter) -> tuple[str, str, str]:
    enabled_levels: list[int] = []
    previews: list[str] = []
    for level in range(1, adapter.max_levels + 1):
        binding = adapter.get_binding(level)
        if not binding.enabled:
            continue
        enabled_levels.append(level)
        preview = adapter.preview_number(level).strip()
        previews.append(preview or f"{level}级未编号")
    if not previews:
        return "未启用编号", "所有级别当前不输出编号", ""
    return f"共{len(enabled_levels)}级标题", _ellipsis_join(previews), "/".join(previews)


def _heading_special_rule_text(adapter: HeadingNumberingAdapter) -> tuple[str, str, str]:
    texts = [item for item in adapter.get_non_numbered_texts() if str(item).strip()]
    prefixes = [item for item in adapter.get_non_numbered_prefixes() if str(item).strip()]
    samples = texts + [f"{item}*" for item in prefixes]
    total = len(texts) + len(prefixes)
    if not samples:
        return "未设置跳过规则", "所有识别标题都会按级别编号", ""
    detail = "、".join(samples[:2])
    if total > 2:
        detail = f"{detail}、..."
    tooltip = "、".join(texts + [f"{item}*" for item in prefixes])
    return f"共{total}项非编号标题", detail, tooltip


def _page_margin_detail(page) -> str:
    detail = f"左右 {page.margin.left_cm:g}/{page.margin.right_cm:g} cm"
    if float(page.gutter_cm or 0) > 0:
        detail = f"{detail} / 装订 {page.gutter_cm:g} cm"
    return detail


def _page_margin_tooltip(page) -> str:
    return (
        f"上 {page.margin.top_cm:g} cm / 下 {page.margin.bottom_cm:g} cm\n"
        f"左 {page.margin.left_cm:g} cm / 右 {page.margin.right_cm:g} cm\n"
        f"装订线 {page.gutter_cm:g} cm"
    )


def _page_tiles(cfg: TemplateConfig) -> tuple[TemplateSummaryTileSpec, ...]:
    page = cfg.page_setup
    return (
        TemplateSummaryTileSpec(
            key="paper_layout",
            label="纸张与版面",
            value=f"{_paper_label(page.paper_size)} / {_orientation_label(page.orientation)}",
            detail=f"分节 {_section_break_label(cfg.section.section_break_type)}",
            icon_name="layout",
            preferred_span=4,
        ),
        TemplateSummaryTileSpec(
            key="margin_gutter",
            label="页边距",
            value=f"上下 {page.margin.top_cm:g}/{page.margin.bottom_cm:g} cm",
            detail=_page_margin_detail(page),
            icon_name="scan",
            preferred_span=4,
            tooltip=_page_margin_tooltip(page),
        ),
        TemplateSummaryTileSpec(
            key="header_footer",
            label="页眉页脚",
            value=f"页眉/页脚 {page.header_distance_cm:g}/{page.footer_distance_cm:g} cm",
            detail="距离页面边缘",
            icon_name="panel-top",
            preferred_span=4,
        ),
    )


def _style_tiles(cfg: TemplateConfig) -> tuple[TemplateSummaryTileSpec, ...]:
    style = _body_style(cfg)
    return (
        TemplateSummaryTileSpec(
            key="text",
            label="文字样式",
            value=f"{style.font_cn or '-'} / {style.font_en or '-'}",
            detail=f"字号 {_size_text(style)}  字形 {_emphasis_text(style)}",
            icon_name="type-outline",
            preferred_span=4,
        ),
        TemplateSummaryTileSpec(
            key="paragraph",
            label="对齐与缩进",
            value=f"{ALIGNMENT_LABELS.get(style.alignment, str(style.alignment or '未设置对齐'))}  {_special_indent_text(style)}",
            detail=(
                f"左缩进 {_indent_value_text(style.left_indent_chars, style.left_indent_unit)}  "
                f"右缩进 {_indent_value_text(style.right_indent_chars, style.right_indent_unit)}"
            ),
            icon_name="sliders-horizontal",
            preferred_span=4,
        ),
        TemplateSummaryTileSpec(
            key="spacing",
            label="行距与段距",
            value=_line_spacing_text(style),
            detail=(
                f"段前 {format_spacing_value(style.space_before_pt, getattr(style, 'space_before_unit', 'pt'))}  "
                f"段后 {format_spacing_value(style.space_after_pt, getattr(style, 'space_after_unit', 'pt'))}"
            ),
            icon_name="sliders-horizontal",
            preferred_span=4,
        ),
    )


def _heading_tiles(cfg: TemplateConfig) -> tuple[TemplateSummaryTileSpec, ...]:
    adapter = HeadingNumberingAdapter()
    adapter.set_template(cfg)
    preset_label = _heading_preset_label(adapter)
    enabled_count = sum(
        1 for level in range(1, adapter.max_levels + 1) if adapter.get_binding(level).enabled
    )
    preview_value, preview_detail, preview_tooltip = _heading_preview_values(adapter)
    special_value, special_detail, special_tooltip = _heading_special_rule_text(adapter)
    return (
        TemplateSummaryTileSpec(
            key="scheme",
            label="编号方案",
            value=preset_label,
            detail=f"最大 {adapter.max_levels} 级 / 启用 {enabled_count} 级",
            icon_name="settings",
            preferred_span=4,
        ),
        TemplateSummaryTileSpec(
            key="level_preview",
            label="级别预览",
            value=preview_value,
            detail=preview_detail,
            icon_name="sliders-horizontal",
            preferred_span=4,
            tooltip=preview_tooltip,
        ),
        TemplateSummaryTileSpec(
            key="special_rules",
            label="特殊规则",
            value=special_value,
            detail=special_detail,
            icon_name="list-ordered",
            preferred_span=4,
            tooltip=special_tooltip,
        ),
    )


def _table_tiles(cfg: TemplateConfig) -> tuple[TemplateSummaryTileSpec, ...]:
    table = cfg.table
    border_label = table_style_label(table.border_mode)
    color_detail = ""
    if str(table.border_mode or "") == "color_table":
        color_detail = (
            f"颜色表 {color_palette(getattr(table, 'color_table_accent', 'blue')).label}"
            f" / {color_variant(getattr(table, 'color_table_variant', 'header_grid')).label}"
        )
    layout_label = TABLE_LAYOUT_LABELS.get(table.layout_mode, table.layout_mode or "智能布局")
    spacing_label = TABLE_LINE_SPACING_LABELS.get(table.line_spacing_mode, table.line_spacing_mode or "单倍")
    smart_detail = (
        f"智能层级 {table.smart_levels} 级"
        if str(table.layout_mode or "smart") == "smart"
        else layout_label
    )
    detail_parts = [smart_detail]
    if color_detail:
        detail_parts.append(color_detail)
    width_value, width_detail = _table_width_summary_text(table)
    alignment_label = ALIGNMENT_LABELS.get(table.cell_alignment, table.cell_alignment or "不调整")
    size_text = f"{table.size_pt:g}磅" if table.size_pt else "默认字号"
    return (
        TemplateSummaryTileSpec(
            key="border",
            label="边框与布局",
            value=f"{border_label} / {layout_label}",
            detail="",
            icon_name="table-2",
            preferred_span=4,
            tooltip="  ".join(detail_parts),
        ),
        TemplateSummaryTileSpec(
            key="width",
            label="线宽与行距",
            value=width_value,
            detail=width_detail if width_detail else f"表格行距 {spacing_label}",
            icon_name="ruler",
            preferred_span=4,
        ),
        TemplateSummaryTileSpec(
            key="type",
            label="字体与对齐",
            value=f"{table.font_cn or '-'} / {table.font_en or '-'}",
            detail=_table_type_tile_detail(table, alignment_label),
            icon_name="type-outline",
            preferred_span=4,
            tooltip=(
                f"{table.font_cn or '-'} / {table.font_en or '-'} / {size_text}\n"
                f"字形 {_table_emphasis_summary_text(table)} / 单元格 {alignment_label}\n"
                f"{_table_behavior_summary_text(table)}"
            ),
        ),
    )


def _header_footer_tiles(cfg: TemplateConfig) -> tuple[TemplateSummaryTileSpec, ...]:
    header_footer = cfg.header_footer
    return (
        TemplateSummaryTileSpec(
            key="header",
            label="顶部",
            value=_header_summary_value(header_footer),
            detail=_header_summary_detail(header_footer),
            icon_name="panel-top",
            preferred_span=4,
        ),
        TemplateSummaryTileSpec(
            key="footer_text",
            label="底部文字",
            value=_footer_summary_value(header_footer),
            detail=_footer_summary_detail(header_footer),
            icon_name="panel-bottom",
            preferred_span=4,
        ),
        TemplateSummaryTileSpec(
            key="page_number",
            label="页码",
            value=_page_number_summary_value(header_footer),
            detail=_page_number_summary_detail(header_footer),
            icon_name="list-ordered",
            preferred_span=4,
        ),
    )


def _toc_tiles(cfg: TemplateConfig) -> tuple[TemplateSummaryTileSpec, ...]:
    return (
        TemplateSummaryTileSpec(
            key="toc",
            label="目录结构",
            value=_toc_summary_value(cfg.toc),
            detail=_toc_summary_detail(cfg.toc),
            icon_name="chart-no-axes-gantt",
            preferred_span=6,
        ),
        _toc_style_tile(cfg),
    )


def _reference_tiles(cfg: TemplateConfig) -> tuple[TemplateSummaryTileSpec, ...]:
    style = get_effective_style(cfg, "references_body")
    ref = cfg.reference_style
    mode = "独立设置" if is_variant_overridden(cfg, "references_body") else "跟随正文"
    return (
        TemplateSummaryTileSpec(
            key="paragraph_style",
            label="条目样式",
            value=mode,
            detail=_style_summary_detail(style),
            icon_name="type-outline",
            preferred_span=6,
        ),
        TemplateSummaryTileSpec(
            key="citation_rules",
            label="条目规则",
            value=f"悬挂缩进 {ref.hanging_indent_cm:g}cm",
            detail=f"条目段后 {format_spacing_value(ref.space_after_pt, getattr(ref, 'space_after_unit', 'pt'))}",
            icon_name="book-open",
            preferred_span=6,
        ),
    )


def _caption_tiles(cfg: TemplateConfig) -> tuple[TemplateSummaryTileSpec, ...]:
    caption = cfg.caption
    style = _caption_style(cfg)
    numbering_mode = {
        "chapter": "按章节编号",
        "global": "全文连续",
    }.get(caption.numbering_mode, caption.numbering_mode or "按章节编号")
    numbering_format = {
        "chapter.seq": "1.1",
        "chapter-seq": "1-1",
        "chapter:seq": "1:1",
        "seq": "1",
    }.get(caption.numbering_format, caption.numbering_format or "1.1")
    return (
        TemplateSummaryTileSpec(
            key="caption_text",
            label="题注文本",
            value=f"{caption.figure_prefix or '图'} / {caption.table_prefix or '表'}",
            detail=f"编号后间隔 {caption.separator or '无'}  缺失标题 {caption.placeholder or '未设置'}",
            icon_name="waves-arrow-down",
            preferred_span=4,
        ),
        TemplateSummaryTileSpec(
            key="numbering_rules",
            label="编号规则",
            value=numbering_mode,
            detail=(
                f"{numbering_format}  "
                f"{'缺失时自动补齐' if caption.auto_insert else '缺失时不补齐'}  "
                f"{'Word 可更新编号' if caption.format_inserted else '固定文本编号'}"
            ),
            icon_name="list-ordered",
            preferred_span=4,
        ),
        TemplateSummaryTileSpec(
            key="caption_style",
            label="题注样式",
            value=f"{style.font_cn or '-'} / {style.font_en or '-'} / {_size_text(style)}",
            detail=(
                f"字形 {_emphasis_text(style)}  "
                f"{ALIGNMENT_LABELS.get(style.alignment, str(style.alignment or '未设置对齐'))}  "
                f"段前 {format_spacing_value(style.space_before_pt, getattr(style, 'space_before_unit', 'pt'))}  "
                f"段后 {format_spacing_value(style.space_after_pt, getattr(style, 'space_after_unit', 'pt'))}"
            ),
            icon_name="type-outline",
            preferred_span=4,
        ),
    )


def _page_nav_summary(cfg: TemplateConfig) -> str:
    page = cfg.page_setup
    margin = page.margin
    parts = [
        f"{_paper_label(page.paper_size)}  边距 {margin.top_cm:g}/{margin.bottom_cm:g}/{margin.left_cm:g}/{margin.right_cm:g}cm",
        f"页眉{page.header_distance_cm:g}cm / 页脚{page.footer_distance_cm:g}cm",
    ]
    if page.gutter_cm:
        parts.append(f"装订线{page.gutter_cm:g}cm")
    if cfg.section.section_break_type:
        parts.append(str(cfg.section.section_break_type))
    return "，".join(parts)


def _style_nav_summary(cfg: TemplateConfig) -> str:
    body = _body_style(cfg)
    return (
        f"{body.font_cn}/{body.font_en}  {_size_label(body.size_display, body.size_pt)}"
        f"，{_special_indent_text(body).replace(' ', '')}，行距{_line_spacing_label(body.line_spacing_type, body.line_spacing_pt)}"
    )


def _heading_nav_summary(cfg: TemplateConfig) -> str:
    adapter = HeadingNumberingAdapter()
    adapter.set_template(cfg)
    preset = _heading_preset_label(adapter)
    preview, _detail, _tooltip = _heading_preview_values(adapter)
    return f"{preset}，{preview}，最多{adapter.max_levels}级"


def _table_nav_summary(cfg: TemplateConfig) -> str:
    table = cfg.table
    style = table_style_label(table.border_mode)
    if str(table.border_mode or "") == "color_table":
        style = (
            f"{style}"
            f"({color_palette(getattr(table, 'color_table_accent', 'blue')).label}"
            f"/{color_variant(getattr(table, 'color_table_variant', 'header_grid')).label})"
        )
    parts = [
        style,
        TABLE_LAYOUT_LABELS.get(table.layout_mode, table.layout_mode or "智能布局"),
        f"表格{TABLE_ALIGNMENT_LABELS.get(getattr(table, 'table_alignment', 'center'), '居中')}",
        f"字形{_table_emphasis_summary_text(table)}",
        "首行加粗" if bool(getattr(table, "first_row_bold", False)) else "不首行加粗",
        "跨页重复表头" if table.repeat_header else "不跨页重复表头",
    ]
    return " / ".join(parts)


def _header_footer_nav_summary(cfg: TemplateConfig) -> str:
    header = cfg.header_footer
    if not bool(getattr(getattr(header, "header", None), "enabled", True)):
        header_text = "页眉关闭"
    elif header.header_mode == "none":
        header_text = "顶部不显示"
    elif header.header_mode == "fixed":
        header_text = f"顶部：{str(header.header_text or '').strip() or '固定文字'}"
    elif header.header_mode == "styleref":
        header_text = f"顶部跟随 {header.styleref_level} 级标题"
    else:
        header_text = str(header.header_mode or "顶部跟随章节标题")
    parts = [header_text]
    if bool(getattr(getattr(header, "header", None), "enabled", True)) and header.header_mode != "none":
        parts.append(_header_position_label(header))
    header_outputs = bool(getattr(getattr(header, "header", None), "enabled", True)) and header.header_mode != "none"
    parts.append("顶部横线" if header.header_border and header_outputs else "无顶部横线")
    parts.append(_footer_content_summary(header))
    parts.append(_phase_result_summary(header))
    suppress_summary = _suppress_header_footer_summary(header)
    if suppress_summary:
        parts.append(suppress_summary)
    return " / ".join(parts)


def _toc_nav_summary(cfg: TemplateConfig) -> str:
    parts = ["目录开启" if cfg.toc.enabled else "目录关闭"]
    if cfg.toc.enabled:
        parts.append(TOC_MODE_LABELS.get(cfg.toc.mode, cfg.toc.mode or "Word 自动目录"))
        parts.append(f"{cfg.toc.max_level}级")
        parts.append(TOC_INSERT_LABELS.get(str(cfg.toc.insert_position or "auto"), str(cfg.toc.insert_position or "auto")))
    return " / ".join(parts)


def _reference_nav_summary(cfg: TemplateConfig) -> str:
    ref = cfg.reference_style
    mode = "独立设置" if is_variant_overridden(cfg, "references_body") else "跟随正文"
    return (
        f"{mode} / 悬挂缩进 {ref.hanging_indent_cm:g}cm / "
        f"段后 {format_spacing_value(ref.space_after_pt, getattr(ref, 'space_after_unit', 'pt'))}"
    )


def _caption_nav_summary(cfg: TemplateConfig) -> str:
    caption = cfg.caption
    mode = {
        "chapter": "按章节编号",
        "global": "全文连续",
    }.get(caption.numbering_mode, caption.numbering_mode or "按章节编号")
    return " / ".join(
        [
            f"{caption.figure_prefix}/{caption.table_prefix}",
            mode,
            "缺失时自动补齐" if caption.auto_insert else "缺失时不补齐",
            "Word 可更新编号" if caption.format_inserted else "固定文本编号",
        ]
    )


def _spec_data(cfg: TemplateConfig) -> dict[str, TemplateDetailSummarySpec]:
    return {
        "tpl_page": TemplateDetailSummarySpec(
            detail_card_id="tpl_page",
            title="页面设置",
            icon_name="ruler",
            nav_label="页面",
            nav_summary=_page_nav_summary(cfg),
            field_names=("page_setup", "section"),
            tiles=_page_tiles(cfg),
        ),
        "tpl_style": TemplateDetailSummarySpec(
            detail_card_id="tpl_style",
            title="正文排版",
            icon_name="type-outline",
            nav_label="排版",
            nav_summary=_style_nav_summary(cfg),
            field_names=("styles",),
            tiles=_style_tiles(cfg),
        ),
        "tpl_heading": TemplateDetailSummarySpec(
            detail_card_id="tpl_heading",
            title="标题编号",
            icon_name="list-ordered",
            nav_label="标题",
            nav_summary=_heading_nav_summary(cfg),
            field_names=("heading_numbering", "heading_model"),
            tiles=_heading_tiles(cfg),
        ),
        "tpl_table": TemplateDetailSummarySpec(
            detail_card_id="tpl_table",
            title="表格",
            icon_name="table-2",
            nav_label="表格",
            nav_summary=_table_nav_summary(cfg),
            field_names=("table",),
            tiles=_table_tiles(cfg),
        ),
        "tpl_header_footer": TemplateDetailSummarySpec(
            detail_card_id="tpl_header_footer",
            title="页眉与页脚",
            icon_name="panel-top",
            nav_label="页眉与页脚",
            nav_summary=_header_footer_nav_summary(cfg),
            field_names=("header_footer",),
            tiles=_header_footer_tiles(cfg),
        ),
        "tpl_toc": TemplateDetailSummarySpec(
            detail_card_id="tpl_toc",
            title="目录",
            icon_name="chart-no-axes-gantt",
            nav_label="目录",
            nav_summary=_toc_nav_summary(cfg),
            field_names=("toc", "styles"),
            tiles=_toc_tiles(cfg),
        ),
        "tpl_reference": TemplateDetailSummarySpec(
            detail_card_id="tpl_reference",
            title="参考文献",
            icon_name="book-open",
            nav_label="参考文献",
            nav_summary=_reference_nav_summary(cfg),
            field_names=("reference_style", "styles"),
            tiles=_reference_tiles(cfg),
        ),
        "tpl_caption": TemplateDetailSummarySpec(
            detail_card_id="tpl_caption",
            title="题注",
            icon_name="waves-arrow-down",
            nav_label="题注",
            nav_summary=_caption_nav_summary(cfg),
            field_names=("caption", "styles"),
            tiles=_caption_tiles(cfg),
        ),
    }


def build_template_detail_summary(cfg: TemplateConfig, detail_card_id: str) -> TemplateDetailSummarySpec:
    specs = _spec_data(cfg)
    if detail_card_id not in specs:
        raise KeyError(f"Unknown template detail card id: {detail_card_id}")
    return specs[detail_card_id]


def all_template_detail_summaries(cfg: TemplateConfig) -> list[TemplateDetailSummarySpec]:
    specs = _spec_data(cfg)
    return [specs[detail_id] for detail_id in DETAIL_ORDER]


def summary_grid_items(
    spec_or_tiles: TemplateDetailSummarySpec | tuple[TemplateSummaryTileSpec, ...],
    *,
    span_override: int | None = None,
) -> list[SummaryGridItem]:
    tiles = spec_or_tiles.tiles if isinstance(spec_or_tiles, TemplateDetailSummarySpec) else spec_or_tiles
    return [
        SummaryGridItem(
            key=tile.key,
            label=tile.label,
            value=tile.value,
            detail=tile.detail,
            detail_emphasis=tile.detail_emphasis,
            column_span=max(tile.min_span, int(span_override or tile.preferred_span or 1)),
            icon_name=tile.icon_name or None,
            tooltip=tile.tooltip,
        )
        for tile in tiles
    ]


def build_template_detail_summary_items(
    cfg: TemplateConfig,
    detail_card_id: str,
    *,
    span_override: int | None = None,
) -> list[SummaryGridItem]:
    return summary_grid_items(
        build_template_detail_summary(cfg, detail_card_id),
        span_override=span_override,
    )


__all__ = [
    "TemplateSummaryTileSpec",
    "TemplateDetailSummarySpec",
    "DETAIL_ORDER",
    "all_template_detail_summaries",
    "build_template_detail_summary",
    "build_template_detail_summary_items",
    "summary_grid_items",
]
