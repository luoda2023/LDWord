"""Projection helpers for template overview summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.config.style_semantics import line_spacing_display_label, resolve_style_special_indent
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
    return f"{size_pt:g}pt"


def _line_spacing_label(kind: str, value: float) -> str:
    label = line_spacing_display_label(kind)
    if label == "固定值":
        return f"固定{value:g}pt"
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
        f"{_paper_label(page.paper_size)} · 边距 {margin.top_cm:g}/{margin.bottom_cm:g}/{margin.left_cm:g}/{margin.right_cm:g}cm",
        f"页眉{page.header_distance_cm:g}cm/页脚{page.footer_distance_cm:g}cm",
    ]
    if page.gutter_cm:
        parts.append(f"装订线{page.gutter_cm:g}cm")
    if cfg.section.section_break_type:
        parts.append(str(cfg.section.section_break_type))
    return " · ".join(parts)


def _style_group_summary(cfg: TemplateConfig) -> str:
    body = cfg.styles.get("body") or cfg.styles.get("normal")
    if body is None:
        return "默认正文样式"
    return (
        f"{body.font_cn}/{body.font_en} · {_size_label(body.size_display, body.size_pt)}"
        f" · {_indent_label(body)} · 行距{_line_spacing_label(body.line_spacing_type, body.line_spacing_pt)}"
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
    return f"{flow} · 最多{cfg.heading_model.max_heading_levels}级"


def _table_group_summary(cfg: TemplateConfig) -> str:
    table = cfg.table
    border_map = {
        "three_line": "三线表",
        "full_grid": "全框线",
        "keep": "保留原样",
    }
    layout_map = {
        "smart": f"智能布局({table.smart_levels}级)",
        "compact": "紧凑布局",
        "full": "撑满布局",
    }
    border = border_map.get(table.border_mode, table.border_mode or "默认边框")
    layout = layout_map.get(table.layout_mode, table.layout_mode or "默认布局")
    return f"{border} · {layout} · 图表{_numbering_label(cfg.caption.numbering_format)}"


def _elements_group_summary(cfg: TemplateConfig) -> str:
    header_footer = cfg.header_footer
    mode_map = {
        "styleref": f"STYLEREF {header_footer.styleref_level}级",
        "fixed": f"固定页眉 {header_footer.header_text or '(空)'}",
        "none": "无页眉",
    }
    toc = "目录关闭"
    if cfg.toc.enabled:
        toc = f"目录 {cfg.toc.max_level}级"
    page_no = "有页码" if header_footer.page_number_enabled else "无页码"
    return f"{mode_map.get(header_footer.header_mode, header_footer.header_mode)} · {page_no} · {toc}"


def _formula_group_summary(cfg: TemplateConfig) -> str:
    formula = cfg.formula_table
    style = cfg.formula_style
    enabled_parts = []
    if style.unify_font:
        enabled_parts.append("统一字体")
    if style.unify_size:
        enabled_parts.append("统一字号")
    if style.unify_spacing:
        enabled_parts.append("统一间距")
    style_text = "/".join(enabled_parts) if enabled_parts else "保留原样"
    size_text = formula.formula_font_size_display or f"{formula.formula_font_size_pt:g}"
    return (
        f"{formula.formula_font_name} {size_text}pt · {_numbering_label(cfg.equation_numbering.numbering_format)}"
        f" · {style_text}"
    )


def _reference_group_summary(cfg: TemplateConfig) -> str:
    ref = cfg.reference_style
    fonts = "跟随正文"
    if ref.font_cn or ref.font_en:
        fonts = f"{ref.font_cn or '-'} / {ref.font_en or '-'}"
    size_text = f"{ref.size_pt:g}pt" if ref.size_pt else "跟随正文"
    return f"{fonts} · {size_text} · 悬挂{ref.hanging_indent_cm:g}cm"


def _other_group_summary(cfg: TemplateConfig) -> str:
    watermark = "水印关闭"
    if cfg.watermark.enabled:
        watermark = f"水印 {cfg.watermark.text or '已启用'}"
    outputs = sum(1 for enabled in cfg.output.__dict__.values() if enabled)
    return f"{watermark} · 输出{outputs}项"


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
        label="表格题注",
        icon_name="table-2",
        field_names=("table", "caption"),
        summary_builder=_table_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="elements",
        detail_card_id="tpl_elements",
        label="页眉目录",
        icon_name="panel-top",
        field_names=("header_footer", "toc"),
        summary_builder=_elements_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="formula",
        detail_card_id="tpl_formula",
        label="公式",
        icon_name="sigma",
        field_names=("formula_table", "formula_style", "equation_numbering"),
        summary_builder=_formula_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="reference",
        detail_card_id="tpl_reference",
        label="参考文献",
        icon_name="book-open",
        field_names=("reference_style",),
        summary_builder=_reference_group_summary,
    ),
    TemplatePreviewGroupSpec(
        group_id="other",
        detail_card_id="tpl_other",
        label="其他",
        icon_name="settings",
        field_names=("watermark", "output"),
        summary_builder=_other_group_summary,
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
