"""Projection helpers for template overview summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.config.style_semantics import format_spacing_value, line_spacing_display_label, resolve_style_special_indent
from src.config.table_style_presets import color_palette, color_variant, table_style_label
from src.config.template import TemplateConfig


@dataclass(frozen=True, slots=True)
class TemplatePreviewGroup:
    group_id: str
    detail_card_id: str
    label: str
    icon_name: str
    summary: str
    field_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TemplatePreviewGroupSpec:
    group_id: str
    detail_card_id: str
    label: str
    icon_name: str
    field_names: tuple[str, ...]
    summary_builder: Callable[[TemplateConfig], str]


def _paper_label(size: str) -> str:
    return size.upper() if size else "A4"


def _size_label(size_display: str, size_pt: float | None) -> str:
    if size_display:
        return size_display
    if size_pt is None:
        return "默认字号"
    return f"{size_pt:g}磅"


def _line_spacing_label(kind: str, value: float) -> str:
    label = line_spacing_display_label(kind)
    if label == "固定值":
        return f"固定{value:g}磅"
    if kind in {"single", "one_half", "double"}:
        return label
    return f"{value:g}倍"


def _indent_label(body) -> str:
    special = resolve_style_special_indent(body)
    unit = {"chars": "字", "pt": "磅", "cm": "cm"}.get(str(special["unit"]), str(special["unit"]))
    if special["mode"] == "first_line" and float(special["value"]) > 0:
        return f"首行{float(special['value']):g}{unit}"
    if special["mode"] == "hanging" and float(special["value"]) > 0:
        return f"悬挂{float(special['value']):g}{unit}"
    if getattr(body, "left_indent_chars", 0):
        left_unit = {"chars": "字", "pt": "磅", "cm": "cm"}.get(
            getattr(body, "left_indent_unit", "chars"),
            getattr(body, "left_indent_unit", "chars"),
        )
        return f"左缩进{body.left_indent_chars:g}{left_unit}"
    return "无特殊缩进"


def _numbering_label(numbering_format: str) -> str:
    numbering_map = {
        "chapter.seq": "章节序号",
        "global": "全局序号",
    }
    return numbering_map.get(numbering_format, numbering_format or "默认编号")


def _page_group_summary(cfg: TemplateConfig) -> str:
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


def _style_group_summary(cfg: TemplateConfig) -> str:
    body = cfg.styles.get("body") or cfg.styles.get("normal")
    if body is None:
        return "默认正文样式"
    return (
        f"{body.font_cn}/{body.font_en}  {_size_label(body.size_display, body.size_pt)}"
        f"，{_indent_label(body)}，行距{_line_spacing_label(body.line_spacing_type, body.line_spacing_pt)}"
    )


def _heading_numbering_flow(cfg: TemplateConfig) -> str:
    bindings = cfg.heading_numbering.level_bindings
    if not bindings:
        return "默认编号样式"

    parts = []
    for level_key in sorted(bindings.keys())[:4]:
        binding = bindings[level_key]
        if not binding.enabled:
            continue
        if binding.display_template:
            parts.append(
                binding.display_template
                .replace("{cn}", "X")
                .replace("{nn}", "X")
                .replace("{current}", "X")
            )
        else:
            parts.append(binding.display_core_style[:3] or level_key[:3])
    return " -> ".join(parts) if parts else "默认编号样式"


def _heading_group_summary(cfg: TemplateConfig) -> str:
    flow = _heading_numbering_flow(cfg)
    return f"{flow}，最多{cfg.heading_model.max_heading_levels}级"


def _table_group_summary(cfg: TemplateConfig) -> str:
    table = cfg.table
    layout_map = {
        "smart": "智能布局",
        "compact": "紧凑布局",
        "full": "撑满布局",
        "keep": "布局保留原样",
    }
    table_alignment_map = {
        None: "表格不调整",
        "": "表格不调整",
        "left": "表格左对齐",
        "center": "表格居中",
        "right": "表格右对齐",
    }
    style = table_style_label(table.border_mode)
    if str(table.border_mode or "") == "color_table":
        style = (
            f"{style}"
            f"({color_palette(getattr(table, 'color_table_accent', 'blue')).label}"
            f"/{color_variant(getattr(table, 'color_table_variant', 'header_grid')).label})"
        )
    parts = [
        style,
        layout_map.get(table.layout_mode, table.layout_mode or "智能布局"),
        table_alignment_map.get(getattr(table, "table_alignment", "center"), "表格居中"),
    ]
    emphasis_parts: list[str] = []
    if bool(getattr(table, "bold", False)):
        emphasis_parts.append("加粗")
    if bool(getattr(table, "italic", False)):
        emphasis_parts.append("斜体")
    parts.append(f"字形{'、'.join(emphasis_parts) if emphasis_parts else '常规'}")
    parts.append("首行加粗" if bool(getattr(table, "first_row_bold", False)) else "不首行加粗")
    parts.append("跨页重复表头" if table.repeat_header else "不跨页重复表头")
    return " / ".join(parts)


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
    }
    selectors = [
        str(selector or "").strip()
        for selector in (getattr(header, "suppress_header_footer_selectors", []) or [])
        if str(selector or "").strip()
    ]
    if not selectors and getattr(header, "hide_cover_header_footer", False):
        selectors = ["pre_numbering"]
    labels = [selector_map.get(selector, selector) for selector in selectors]
    return f"分区排除：{'+'.join(labels)}" if labels else ""


def _footer_content_summary(header) -> str:
    mode = str(getattr(header.footer, "content_mode", "page_number") or "page_number")
    footer_text = str(getattr(header, "footer_text", "") or "").strip()
    alignment = {
        "left": "左对齐",
        "center": "居中",
        "right": "右对齐",
    }.get(str(getattr(header, "footer_alignment", "center") or "center"), "居中")
    if mode == "none":
        return "无页脚"
    if mode == "fixed":
        return f"页脚固定文字：{footer_text or '未填写'} / {alignment}"
    if mode == "page_number_with_text":
        return f"页码+页脚文字：{footer_text or '未填写'} / {alignment}"
    return f"仅页码 / {alignment}"


def _phase_result_summary(header) -> str:
    if not bool(getattr(header, "page_number_enabled", True)):
        return "页码：不显示"
    phases = list(getattr(header.page_number_plan, "phases", []) or [])
    if not phases:
        return "页码：全文阿拉伯，从 1 起"
    results: list[str] = []
    for phase in phases[:2]:
        scope = _page_number_phase_scope_label(list(getattr(phase, "selectors", []) or []))
        if not bool(getattr(phase, "visible", True)):
            results.append(f"{scope}不显示页码")
            continue
        fmt = {
            "decimal": "阿拉伯",
            "upperRoman": "大写罗马",
            "lowerRoman": "小写罗马",
        }.get(str(getattr(phase, "number_format", "decimal") or "decimal"), "阿拉伯")
        if str(getattr(phase, "start_mode", "restart") or "restart") == "continue":
            results.append(f"{scope}{fmt}续号")
        else:
            start_value = max(1, int(getattr(phase, "start_value", 1) or 1))
            results.append(f"{scope}{fmt}从 {start_value}")
    if len(phases) > 2:
        results.append(f"另 {len(phases) - 2} 项")
    return "页码：" + " / ".join(results)


def _header_footer_group_summary(cfg: TemplateConfig) -> str:
    header = cfg.header_footer
    header_map = {
        "styleref": "跟随章节标题",
        "fixed": "固定页眉",
        "none": "无页眉",
    }
    parts = [header_map.get(header.header_mode, header.header_mode or "跟随章节标题")]
    parts.append("页眉线" if header.header_border else "无页眉线")
    parts.append(_footer_content_summary(header))
    parts.append(_phase_result_summary(header))
    suppress_summary = _suppress_header_footer_summary(header)
    if suppress_summary:
        parts.append(suppress_summary)
    return " / ".join(parts)


def _toc_group_summary(cfg: TemplateConfig) -> str:
    toc = cfg.toc
    mode_map = {
        "word_native": "Word 自动目录",
        "plain": "普通目录",
    }
    insert_map = {
        "auto": "自动位置",
        "after_cover": "封面后",
        "0": "文档起始",
    }
    parts = ["目录开启" if toc.enabled else "目录关闭"]
    if toc.enabled:
        parts.append(mode_map.get(toc.mode, toc.mode or "Word 自动目录"))
        parts.append(f"{toc.max_level}级")
        parts.append(insert_map.get(str(toc.insert_position or "auto"), str(toc.insert_position or "auto")))
    return " / ".join(parts)


def _reference_group_summary(cfg: TemplateConfig) -> str:
    ref = cfg.reference_style
    return f"悬挂缩进 {ref.hanging_indent_cm:g}cm / 段后 {format_spacing_value(ref.space_after_pt, 'pt')}"


def _caption_group_summary(cfg: TemplateConfig) -> str:
    caption = cfg.caption
    mode_map = {
        "chapter": "章节编号",
        "global": "全局编号",
    }
    parts = [
        f"{caption.figure_prefix}/{caption.table_prefix}",
        mode_map.get(caption.numbering_mode, caption.numbering_mode or "章节编号"),
    ]
    parts.append("自动补题注" if caption.auto_insert else "手动题注")
    parts.append("域编号" if caption.format_inserted else "纯文本编号")
    return " / ".join(parts)


TEMPLATE_PREVIEW_SPECS: tuple[TemplatePreviewGroupSpec, ...] = (
    TemplatePreviewGroupSpec(
        group_id="page",
        detail_card_id="tpl_page",
        label="页面",
        icon_name="ruler",
        field_names=("page_setup", "section"),
        summary_builder=_page_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="style",
        detail_card_id="tpl_style",
        label="排版",
        icon_name="type-outline",
        field_names=("styles",),
        summary_builder=_style_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="heading",
        detail_card_id="tpl_heading",
        label="标题",
        icon_name="list-ordered",
        field_names=("heading_numbering", "heading_model"),
        summary_builder=_heading_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="table",
        detail_card_id="tpl_table",
        label="表格",
        icon_name="table-2",
        field_names=("table",),
        summary_builder=_table_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="header_footer",
        detail_card_id="tpl_header_footer",
        label="页眉与页脚",
        icon_name="panel-top",
        field_names=("header_footer",),
        summary_builder=_header_footer_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="toc",
        detail_card_id="tpl_toc",
        label="目录",
        icon_name="scroll-text",
        field_names=("toc",),
        summary_builder=_toc_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="reference",
        detail_card_id="tpl_reference",
        label="参考文献",
        icon_name="book-open",
        field_names=("reference_style", "styles"),
        summary_builder=_reference_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="caption",
        detail_card_id="tpl_caption",
        label="题注",
        icon_name="image-plus",
        field_names=("caption", "styles"),
        summary_builder=_caption_group_summary,
    ),
)


def build_template_preview_groups(cfg: TemplateConfig) -> list[TemplatePreviewGroup]:
    return [
        TemplatePreviewGroup(
            group_id=spec.group_id,
            detail_card_id=spec.detail_card_id,
            label=spec.label,
            icon_name=spec.icon_name,
            summary=spec.summary_builder(cfg),
            field_names=spec.field_names,
        )
        for spec in TEMPLATE_PREVIEW_SPECS
    ]


def build_template_summary_lines(cfg: TemplateConfig) -> list[tuple[str, str, str]]:
    return [
        (group.icon_name, group.label, group.summary)
        for group in build_template_preview_groups(cfg)
    ]


__all__ = [
    "TemplatePreviewGroup",
    "TemplatePreviewGroupSpec",
    "TEMPLATE_PREVIEW_SPECS",
    "build_template_preview_groups",
    "build_template_summary_lines",
]
