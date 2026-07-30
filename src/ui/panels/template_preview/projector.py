"""Project effective template styles into an immutable preview document.

The projection is strictly downstream of template/resolved configuration.
``ModuleSelectionPlan`` is optional and acts only as a visibility mask for the
explicit current-plan view; it never supplies fonts, dimensions, or defaults.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from src.config.heading_style_semantics import (
    resolve_heading_style,
    resolve_non_numbered_heading_style,
)
from src.config.resolved import ResolvedConfig
from src.config.style_semantics import (
    normalize_line_spacing_type,
    resolve_line_spacing_value,
    resolve_spacing_render_pt,
)
from src.config.table_style_presets import color_palette, color_variant
from src.config.template import StyleConfig
from src.pipeline.module_selection import ModuleDisposition, ModuleSelectionPlan
from src.shared.engine.heading_numbering_format import format_heading_level_number
from src.shared.engine.sequence_numbering import parse_chapter_numbering_format
from src.shared.ui.style_preview_utils import (
    resolve_preview_indents_pt,
    resolve_preview_size_pt,
)
from src.ui.panels.template_feature_specs import TEMPLATE_FEATURE_SPECS

from .model import (
    PreviewBlockKind,
    PreviewPageGeometry,
    PreviewPrunedModule,
    PreviewTableStyle,
    PreviewTextStyle,
    TemplatePreviewBlock,
    TemplatePreviewMode,
    TemplatePreviewProjection,
)
from .sample import DEFAULT_TEMPLATE_PREVIEW_SAMPLE, TemplatePreviewSample


_PAPER_DIMENSIONS_CM: dict[str, tuple[float, float]] = {
    "A4": (21.0, 29.7),
    "A3": (29.7, 42.0),
    "B5": (17.6, 25.0),
    "LETTER": (21.59, 27.94),
    "LEGAL": (21.59, 35.56),
    "16K": (18.4, 26.0),
}


def build_template_preview_projection(
    config: ResolvedConfig,
    selection: ModuleSelectionPlan | None = None,
    *,
    mode: TemplatePreviewMode = TemplatePreviewMode.TEMPLATE_BASELINE,
    sample: TemplatePreviewSample = DEFAULT_TEMPLATE_PREVIEW_SAMPLE,
) -> TemplatePreviewProjection:
    """Build preview content from style facts plus an optional visibility mask."""

    preview_mode = TemplatePreviewMode(mode)
    # The baseline is a template-style view.  A caller may already have a
    # plan selection at hand, but it must not mask template facts unless the
    # user explicitly switched to the current-plan view.
    visibility_selection = (
        selection
        if preview_mode is TemplatePreviewMode.CURRENT_PLAN
        else None
    )
    page_enabled = _enabled(visibility_selection, "page_setup")
    paragraph_enabled = _enabled(visibility_selection, "paragraph_style")
    numbering_enabled = _enabled(visibility_selection, "heading_numbering")
    table_enabled = _enabled(visibility_selection, "table_format")
    header_footer_enabled = _enabled(visibility_selection, "header_footer")
    caption_enabled = _enabled(visibility_selection, "caption")

    geometry = _page_geometry(config, guides_enabled=page_enabled)
    heading_rows = _heading_samples(
        config,
        numbering_enabled=numbering_enabled,
        sample=sample,
    )
    blocks: list[TemplatePreviewBlock] = []
    if page_enabled:
        blocks.append(
            TemplatePreviewBlock(
                kind=PreviewBlockKind.PAGE_GUIDES,
            )
        )

    headers, footers = _header_footer_blocks(
        config,
        enabled=header_footer_enabled,
        heading_rows=heading_rows,
    )
    blocks.extend(headers)
    blocks.extend(footers)

    _append_paragraph_blocks(
        blocks,
        config,
        heading_rows=heading_rows,
        paragraph_enabled=paragraph_enabled,
        numbering_enabled=numbering_enabled,
        sample=sample,
    )

    if table_enabled:
        if caption_enabled:
            _append_table_caption_block(blocks, config, sample=sample)
        blocks.append(
            TemplatePreviewBlock(
                kind=PreviewBlockKind.TABLE,
                rows=sample.table_rows,
                style=_table_text_style(config),
                table_style=_table_style(config),
            )
        )

    visible_content = tuple(
        block
        for block in blocks
        if block.kind not in {PreviewBlockKind.PAGE_GUIDES, PreviewBlockKind.WATERMARK}
        and not (
            block.kind in {PreviewBlockKind.HEADER, PreviewBlockKind.FOOTER}
            and not block.text
            and not block.draw_rule
        )
    )
    if not visible_content and not page_enabled:
        blocks = [
            TemplatePreviewBlock(
                kind=PreviewBlockKind.EMPTY_STATE,
                text="当前方案未启用可预览的格式处理",
                style=PreviewTextStyle(size_pt=10.5, alignment="center"),
                alignment="center",
            )
        ]

    hidden, pruned = _plan_status_details(selection, preview_mode)
    status = _status_text(
        preview_mode,
        hidden_labels=hidden,
        auto_pruned=pruned,
        is_empty=bool(blocks and blocks[0].kind is PreviewBlockKind.EMPTY_STATE),
    )
    return TemplatePreviewProjection(
        mode=preview_mode,
        page_geometry=geometry,
        show_page_guides=page_enabled,
        show_header_distance_guide=page_enabled and any(block.text for block in headers),
        show_footer_distance_guide=page_enabled and any(block.text for block in footers),
        blocks=tuple(blocks),
        hidden_feature_labels=hidden,
        auto_pruned=pruned,
        status_text=status,
        accessible_description=_accessible_description(preview_mode, status, blocks),
    )


def _enabled(selection: ModuleSelectionPlan | None, module_name: str) -> bool:
    return True if selection is None else selection.is_effectively_enabled(module_name)


def _page_geometry(config: ResolvedConfig, *, guides_enabled: bool) -> PreviewPageGeometry:
    page = config.page_setup
    label = str(page.paper_size or "A4").strip().upper() or "A4"
    width, height = _PAPER_DIMENSIONS_CM.get(label, _PAPER_DIMENSIONS_CM["A4"])
    if str(page.orientation or "portrait") == "landscape":
        width, height = height, width
    return PreviewPageGeometry(
        paper_label=label,
        width_cm=width,
        height_cm=height,
        margin_top_cm=max(0.0, float(page.margin.top_cm)),
        margin_bottom_cm=max(0.0, float(page.margin.bottom_cm)),
        margin_left_cm=max(0.0, float(page.margin.left_cm)),
        margin_right_cm=max(0.0, float(page.margin.right_cm)),
        gutter_cm=max(0.0, float(page.gutter_cm)),
        header_distance_cm=max(0.0, float(page.header_distance_cm)),
        footer_distance_cm=max(0.0, float(page.footer_distance_cm)),
        neutral=not guides_enabled,
    )


def _heading_samples(
    config: ResolvedConfig,
    *,
    numbering_enabled: bool,
    sample: TemplatePreviewSample,
) -> tuple[tuple[int, str], ...]:
    max_levels = max(1, min(int(config.heading_model.max_heading_levels or 1), 8))
    bindings = config.heading_numbering.level_bindings
    rows: list[tuple[int, str]] = []
    for level, title in enumerate(sample.heading_titles[:max_levels], start=1):
        binding = bindings.get(f"heading{level}")
        number = ""
        if numbering_enabled and binding is not None and binding.enabled:
            counters = [0] * 10
            for current in range(1, level + 1):
                current_binding = bindings.get(f"heading{current}")
                counters[current] = max(1, int(getattr(current_binding, "start_at", 1) or 1))
            number = format_heading_level_number(level, counters, binding, bindings)
        rows.append((level, f"{number}{title}"))
    return tuple(rows)


def _append_paragraph_blocks(
    blocks: list[TemplatePreviewBlock],
    config: ResolvedConfig,
    *,
    heading_rows: tuple[tuple[int, str], ...],
    paragraph_enabled: bool,
    numbering_enabled: bool,
    sample: TemplatePreviewSample,
) -> None:
    body_style = _style_projection(
        config.styles.get("body") or config.styles.get("normal") or StyleConfig()
    )
    for index, (level, text) in enumerate(heading_rows):
        if not paragraph_enabled and not numbering_enabled:
            break
        style = (
            _style_projection(
                resolve_heading_style(config, level, include_body_fallback=True)
                or StyleConfig()
            )
            if paragraph_enabled
            else None
        )
        blocks.append(
            TemplatePreviewBlock(
                kind=PreviewBlockKind.HEADING,
                text=text,
                style=style,
                level=level,
            )
        )
        if paragraph_enabled and index < 2:
            blocks.append(
                TemplatePreviewBlock(
                    kind=PreviewBlockKind.BODY,
                    text=sample.body_text if index == 0 else sample.secondary_body_text,
                    compact_text=(
                        sample.compact_body_text
                        if index == 0
                        else sample.compact_secondary_body_text
                    ),
                    style=body_style,
                )
            )
    if paragraph_enabled:
        blocks.extend(
            (
                TemplatePreviewBlock(
                    kind=PreviewBlockKind.HEADING,
                    text=sample.non_numbered_title,
                    style=_style_projection(
                        resolve_non_numbered_heading_style(
                            config, include_body_fallback=True
                        )
                        or StyleConfig()
                    ),
                ),
                TemplatePreviewBlock(
                    kind=PreviewBlockKind.BODY,
                    text=sample.non_numbered_body,
                    compact_text="非编号标题样式示例。",
                    style=body_style,
                ),
            )
        )


def _style_projection(style: StyleConfig) -> PreviewTextStyle:
    size = resolve_preview_size_pt(style, default=11.0)
    indents = resolve_preview_indents_pt(style, size_pt=size)
    line_kind = normalize_line_spacing_type(style.line_spacing_type)
    line_value = resolve_line_spacing_value(line_kind, style.line_spacing_pt)
    line_height = line_value if line_kind == "exact" else size * max(0.1, line_value)
    return PreviewTextStyle(
        font_cn=str(style.font_cn or "宋体"),
        font_en=str(style.font_en or "Times New Roman"),
        size_pt=max(1.0, size),
        bold=bool(style.bold),
        italic=bool(style.italic),
        alignment=str(style.alignment or "left"),
        first_indent_pt=indents["first_pt"],
        hanging_indent_pt=indents["hanging_pt"],
        left_indent_pt=indents["left_pt"],
        right_indent_pt=indents["right_pt"],
        line_spacing_type=line_kind,
        line_spacing_value=max(0.1, line_value),
        space_before_pt=resolve_spacing_render_pt(
            style.space_before_pt,
            getattr(style, "space_before_unit", "pt"),
            line_height_pt=line_height,
        ),
        space_after_pt=resolve_spacing_render_pt(
            style.space_after_pt,
            getattr(style, "space_after_unit", "pt"),
            line_height_pt=line_height,
        ),
    )


def _table_text_style(config: ResolvedConfig) -> PreviewTextStyle:
    table = config.table
    body = config.styles.get("body") or config.styles.get("normal") or StyleConfig()
    return PreviewTextStyle(
        font_cn=str(table.font_cn or body.font_cn or "宋体"),
        font_en=str(table.font_en or body.font_en or "Times New Roman"),
        size_pt=max(1.0, float(table.size_pt or body.size_pt or 10.5)),
        bold=bool(table.bold),
        italic=bool(table.italic),
        alignment=str(table.cell_alignment or "left"),
        line_spacing_type="multiple",
        line_spacing_value={"one_half": 1.5, "double": 2.0}.get(
            str(table.line_spacing_mode or "single"), 1.0
        ),
    )


def _table_style(config: ResolvedConfig) -> PreviewTableStyle:
    table = config.table
    palette = color_palette(table.color_table_accent)
    variant = color_variant(table.color_table_variant)
    return PreviewTableStyle(
        border_mode=str(table.border_mode or "three_line"),
        layout_mode=str(table.layout_mode or "smart"),
        accent_color=palette.accent,
        light_color=palette.accent_light,
        soft_color=palette.accent_soft,
        header_text_color=palette.header_text,
        header_fill=variant.header_fill,
        show_vertical=variant.show_vertical,
        show_horizontal=variant.show_horizontal,
        zebra=variant.zebra,
        header_rule_only=variant.header_rule_only,
        table_alignment=str(table.table_alignment or ""),
        cell_alignment=str(table.cell_alignment or ""),
        first_row_bold=bool(table.first_row_bold),
        repeat_header=bool(table.repeat_header),
        border_width_pt=max(0.1, float(table.border_width_pt or 0.5)),
        outer_width_pt=max(0.1, float(table.three_line_header_width_pt or 1.0)),
        header_rule_width_pt=max(0.1, float(table.three_line_bottom_width_pt or 0.5)),
    )


def _append_table_caption_block(
    blocks: list[TemplatePreviewBlock],
    config: ResolvedConfig,
    *,
    sample: TemplatePreviewSample,
) -> None:
    """Place the table title immediately before its table sample."""

    _figure_number, table_number = _caption_number_samples(config)
    separator = str(config.caption.separator or "\u3000")
    style = _caption_style(config, "table")
    blocks.append(
        TemplatePreviewBlock(
            kind=PreviewBlockKind.TABLE_CAPTION,
            text=(
                f"{config.caption.table_prefix}{table_number}"
                f"{separator}{sample.table_caption_title}"
            ),
            compact_text=f"{config.caption.table_prefix}{table_number}",
            style=style,
            alignment=style.alignment,
        )
    )


def _caption_style(config: ResolvedConfig, kind: str) -> PreviewTextStyle:
    key = "figure_caption" if kind == "figure" else "table_caption"
    specific = config.styles.get(key)
    shared = config.styles.get("caption")
    style = specific or shared or config.styles.get("body") or StyleConfig()
    projected = _style_projection(style)
    if specific is None and shared is None:
        return replace(
            projected,
            alignment="center",
            first_indent_pt=0.0,
            hanging_indent_pt=0.0,
            left_indent_pt=0.0,
            right_indent_pt=0.0,
        )
    return projected


def _caption_number_samples(config: ResolvedConfig) -> tuple[str, str]:
    include_chapter, separator = parse_chapter_numbering_format(
        config.caption.numbering_format
    )
    if str(config.caption.numbering_mode or "").lower() == "chapter" and include_chapter:
        value = f"1{separator}1"
        return value, value
    return "1", "1"


def _header_footer_blocks(
    config: ResolvedConfig,
    *,
    enabled: bool,
    heading_rows: tuple[tuple[int, str], ...],
) -> tuple[tuple[TemplatePreviewBlock, ...], tuple[TemplatePreviewBlock, ...]]:
    if not enabled:
        return (), ()
    hf = config.header_footer
    variants = ["default"]
    if bool(getattr(hf.behavior, "different_first_page", False)):
        variants.append("first")
    if bool(getattr(hf.behavior, "different_odd_even_pages", False)):
        variants.append("even")

    headers: list[TemplatePreviewBlock] = []
    footers: list[TemplatePreviewBlock] = []
    for variant_name in variants:
        header_content = _resolved_header_footer_content(hf, variant_name, "header")
        footer_content = _resolved_header_footer_content(hf, variant_name, "footer")
        header_mode = str(header_content["mode"])
        footer_mode = str(footer_content["mode"])
        header_text = _header_content_sample(
            hf,
            header_content,
            heading_rows=heading_rows,
        )
        footer_text = _footer_content_sample(hf, footer_content)
        unknown_header = header_mode == "preserve" or bool(
            getattr(hf.behavior, "preserve_existing_content", False)
        )
        unknown_footer = footer_mode == "preserve" or bool(
            getattr(hf.behavior, "preserve_existing_content", False)
        )
        border = hf.header.border_style
        if hf.header.enabled:
            headers.append(TemplatePreviewBlock(
                kind=PreviewBlockKind.HEADER,
                text=header_text if hf.header.enabled else "",
                style=_typography_style(hf.header.typography, fallback_size=9.0),
                alignment=str(header_content["alignment"]),
                draw_rule=bool(
                    hf.header.enabled
                    and header_mode not in {"none", "preserve"}
                    and hf.header.border
                    and border.enabled
                ),
                rule_color=str(border.color or "000000").lstrip("#").replace("auto", "000000"),
                rule_width_pt=max(0.1, float(border.width_pt or 0.5)),
                rule_spacing_pt=max(0.0, float(border.spacing_pt or 0.0)),
                rule_style=str(border.line_style or "single"),
                text_color="#667085" if unknown_header else "",
                page_variant=variant_name,
            ))
        if hf.footer.enabled:
            footers.append(TemplatePreviewBlock(
                kind=PreviewBlockKind.FOOTER,
                text=footer_text if hf.footer.enabled else "",
                style=_typography_style(hf.footer.typography, fallback_size=9.0),
                alignment=str(footer_content["alignment"]),
                text_color="#667085" if unknown_footer else "",
                page_variant=variant_name,
            ))
    return tuple(headers), tuple(footers)


def _resolved_header_footer_content(hf, variant_name: str, part_name: str) -> dict[str, object]:
    part = hf.header if part_name == "header" else hf.footer
    if part_name == "header":
        base = {
            "mode": str(part.mode or "styleref"),
            "fixed_text": str(part.fixed_text or ""),
            "template": "",
            "alignment": str(part.alignment or "center"),
            "styleref_level": int(part.styleref_level or 1),
            "styleref_include_number": True,
        }
    else:
        base = {
            "mode": str(part.content_mode or "page_number"),
            "fixed_text": str(part.fixed_text or ""),
            "template": str(part.page_number_template or "{page}"),
            "alignment": str(part.alignment or "center"),
            "styleref_level": 1,
            "styleref_include_number": True,
        }
    variants = getattr(hf, "variants", None)
    candidates = []
    variant = getattr(variants, variant_name, None)
    if variant is not None:
        candidates.append(getattr(variant, part_name, None))
    if variant_name != "default":
        default_variant = getattr(variants, "default", None)
        if default_variant is not None:
            candidates.append(getattr(default_variant, part_name, None))
    for content in candidates:
        mode = str(getattr(content, "mode", "inherit") or "inherit").strip().lower()
        if mode == "inherit":
            continue
        return {
            "mode": mode,
            "fixed_text": str(getattr(content, "fixed_text", "") or ""),
            "template": str(getattr(content, "template", "") or ""),
            "alignment": str(getattr(content, "alignment", "center") or "center"),
            "styleref_level": int(getattr(content, "styleref_level", 1) or 1),
            "styleref_include_number": bool(
                getattr(content, "styleref_include_number", True)
            ),
        }
    return base


def _header_content_sample(
    hf,
    content: dict[str, object],
    *,
    heading_rows: tuple[tuple[int, str], ...],
) -> str:
    if not hf.header.enabled:
        return ""
    if bool(getattr(hf.behavior, "preserve_existing_content", False)):
        return "保留原页眉（内容取决于原文）"
    mode = str(content["mode"])
    if mode == "none":
        return ""
    if mode == "preserve":
        return "保留原页眉（内容取决于原文）"
    if mode == "fixed":
        return str(content["fixed_text"])
    level = max(1, min(int(content["styleref_level"]), len(heading_rows) or 1))
    numbered = heading_rows[level - 1][1] if heading_rows else "标题"
    title = (
        numbered
        if bool(content["styleref_include_number"])
        else _strip_sample_number(numbered)
    )
    if mode == "template":
        return _content_template_sample(
            str(content["template"]),
            fixed_text=str(content["fixed_text"]),
            page_number=_page_number_sample(hf),
            styleref=title,
        )
    return title


def _footer_content_sample(hf, content: dict[str, object]) -> str:
    if not hf.footer.enabled:
        return ""
    if bool(getattr(hf.behavior, "preserve_existing_content", False)):
        return "保留原页脚（内容取决于原文）"
    mode = str(content["mode"])
    if mode == "none":
        return ""
    if mode == "preserve":
        return "保留原页脚（内容取决于原文）"
    fixed_text = str(content["fixed_text"])
    if mode == "fixed":
        return fixed_text
    page_number = _page_number_sample(hf)
    template = str(content["template"] or "{page}")
    if mode == "page_number_with_text" and fixed_text and "{text}" not in template:
        template = f"{template} {{text}}"
    if mode in {"page_number", "page_number_with_text", "template"}:
        return _content_template_sample(
            template,
            fixed_text=fixed_text,
            page_number=page_number,
            styleref="标题",
        )
    return ""


def _content_template_sample(
    template: str,
    *,
    fixed_text: str,
    page_number: str,
    styleref: str,
) -> str:
    source = str(template or "")
    return (
        source.replace("{page}", page_number)
        .replace("{pages}", "10")
        .replace("{section_pages}", "10")
        .replace("{text}", fixed_text)
        .replace("{styleref_number}", styleref)
        .replace("{styleref}", _strip_sample_number(styleref))
    ).strip()


def _strip_sample_number(text: str) -> str:
    value = str(text or "")
    for marker in ("　", " "):
        if marker in value:
            return value.split(marker, 1)[-1]
    return value


def _typography_style(typography, *, fallback_size: float) -> PreviewTextStyle:
    return PreviewTextStyle(
        font_cn=str(getattr(typography, "font_cn", None) or "宋体"),
        font_en=str(getattr(typography, "font_en", None) or "Times New Roman"),
        size_pt=max(1.0, float(getattr(typography, "size_pt", None) or fallback_size)),
        bold=bool(getattr(typography, "bold", False)),
        italic=bool(getattr(typography, "italic", False)),
        alignment="center",
    )


def _page_number_sample(header_footer) -> str:
    phases = tuple(
        phase
        for phase in header_footer.page_number_plan.phases
        if bool(getattr(phase, "visible", True))
    )
    phase = phases[0] if phases else None
    start = max(1, int(getattr(phase, "start_value", 1) or 1))
    fmt = str(getattr(phase, "number_format", "decimal") or "decimal")
    if fmt == "upperRoman":
        value = _roman(start)
    elif fmt == "lowerRoman":
        value = _roman(start).lower()
    else:
        value = str(start)
    return value


def _roman(value: int) -> str:
    number = max(1, min(3999, int(value)))
    pairs = (
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    )
    result: list[str] = []
    for amount, glyph in pairs:
        while number >= amount:
            result.append(glyph)
            number -= amount
    return "".join(result)


def _plan_status_details(
    selection: ModuleSelectionPlan | None,
    mode: TemplatePreviewMode,
) -> tuple[tuple[str, ...], tuple[PreviewPrunedModule, ...]]:
    if selection is None or mode is TemplatePreviewMode.TEMPLATE_BASELINE:
        return (), ()
    hidden: list[str] = []
    pruned: list[PreviewPrunedModule] = []
    for feature in TEMPLATE_FEATURE_SPECS:
        for control in feature.module_controls:
            decision = selection.decision_for(control.module_name)
            if decision.disposition is ModuleDisposition.DISABLED_BY_PLAN:
                hidden.append(control.status_label)
            elif decision.disposition is ModuleDisposition.AUTO_PRUNED:
                pruned.append(
                    PreviewPrunedModule(
                        module_name=decision.module_name,
                        label=control.status_label,
                        unmet_dependencies=decision.unmet_dependencies,
                    )
                )
    return tuple(hidden), tuple(pruned)


def _status_text(
    mode: TemplatePreviewMode,
    *,
    hidden_labels: tuple[str, ...],
    auto_pruned: tuple[PreviewPrunedModule, ...],
    is_empty: bool,
) -> str:
    if mode is TemplatePreviewMode.TEMPLATE_BASELINE:
        return "展示当前模板配置的样式基线"
    if is_empty:
        return "当前方案未启用可预览的格式处理"
    parts: list[str] = []
    if hidden_labels:
        parts.append("本次跳过：" + "、".join(hidden_labels))
    if auto_pruned:
        parts.append("依赖未满足：" + "、".join(item.label for item in auto_pruned))
    return "；".join(parts) if parts else "展示当前方案的应用效果"


def _accessible_description(
    mode: TemplatePreviewMode,
    status: str,
    blocks: Iterable[TemplatePreviewBlock],
) -> str:
    labels = {
        PreviewBlockKind.PAGE_GUIDES: "页面设置",
        PreviewBlockKind.SECTION_MARKER: "分节",
        PreviewBlockKind.HEADING: "标题",
        PreviewBlockKind.BODY: "正文",
        PreviewBlockKind.TABLE: "表格",
        PreviewBlockKind.HEADER: "页眉",
        PreviewBlockKind.FOOTER: "页脚",
        PreviewBlockKind.TOC: "目录",
        PreviewBlockKind.FIGURE_CAPTION: "图题",
        PreviewBlockKind.TABLE_CAPTION: "表题",
        PreviewBlockKind.FORMULA: "公式",
        PreviewBlockKind.REFERENCE: "参考文献",
        PreviewBlockKind.WATERMARK: "水印",
        PreviewBlockKind.EMPTY_STATE: "空状态",
    }
    visible = tuple(dict.fromkeys(labels[block.kind] for block in blocks))
    mode_label = "模板基线" if mode is TemplatePreviewMode.TEMPLATE_BASELINE else "当前方案"
    suffix = "；可见内容：" + "、".join(visible) if visible else ""
    return f"{mode_label}；{status}{suffix}；点击预览内容可进入对应编辑项"


__all__ = ["build_template_preview_projection"]
