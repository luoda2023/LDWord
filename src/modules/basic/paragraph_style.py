"""Paragraph style module."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from src.config.heading_style_semantics import (
    resolve_heading_style,
    resolve_non_numbered_heading_style,
)
from src.config.section_semantics import (
    canonicalize_section_type,
    style_key_for_section,
)
from src.config.style_semantics import (
    resolve_style_size_pt,
)
from src.modules.base import BaseModule, ModuleMeta
from src.modules.structure.heading_numbering import _should_skip_numbering
from src.modules.table.caption import caption_kind_from_text
from src.shared.engine.document_scope_runtime import document_scope_allows_paragraph
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.heading_numbering_ooxml import disable_style_numbering
from src.shared.engine.indent_ops import (
    apply_style_config_indents,
)
from src.shared.engine.line_spacing_ops import (
    apply_line_spacing,
    apply_paragraph_spacing,
    sync_spacing_ooxml,
)
from src.shared.engine.ooxml_ops import find_or_create_before, qn
from src.shared.engine.run_ops import set_run_east_asian_font
from src.shared.engine.style_ops import apply_style_text_format

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph

    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


ALIGNMENT_MAP: dict[str, int] = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    "distribute": WD_ALIGN_PARAGRAPH.DISTRIBUTE,
}


class ParagraphStyleModule(BaseModule):
    meta = ModuleMeta(
        name="paragraph_style",
        description="段落样式",
        category="basic",
        requires_config=("styles",),
        soft_after=("heading_recognition",),
        soft_consumes=("doc_tree",),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        styles_cfg = config.styles
        max_levels = config.heading_model.max_heading_levels
        non_numbered = set(config.heading_model.non_numbered_title_texts or [])
        non_numbered_pfx = list(config.heading_model.non_numbered_prefixes or [])
        whole_document = (
            str(getattr(context.document_scope, "mode", "all") or "all") == "all"
        )
        style_definition_count = (
            _sync_heading_style_definitions(doc, config)
            if whole_document
            else 0
        )
        body_style_definition_count = (
            _sync_body_style_definition(doc, config) if whole_document else 0
        )
        non_numbered_word_style = None
        count = 0

        for para_index, para in enumerate(doc.paragraphs):
            if not document_scope_allows_paragraph(context, para_index):
                continue
            text = (para.text or "").strip()
            if not text:
                continue

            special_title_selector = None
            if context.doc_tree is not None:
                special_title_getter = getattr(
                    context.doc_tree,
                    "get_special_title_match",
                    None,
                )
                if callable(special_title_getter):
                    special_title_selector = special_title_getter(para_index)
            style_key = _resolve_style_key(para, context, para_index)
            if style_key == "toc" and special_title_selector is None:
                continue
            if style_key.startswith("heading") and style_key != "heading":
                level_num = int(style_key.replace("heading", "") or "0")
                if level_num > max_levels:
                    style_key = "body"

            style_config = styles_cfg.get(style_key)
            is_non_numbered_heading = False
            if special_title_selector is not None:
                style_config = resolve_non_numbered_heading_style(
                    config,
                    include_body_fallback=True,
                )
                is_non_numbered_heading = True
            elif style_key.startswith("heading") and style_key != "heading":
                if _should_skip_numbering(para, non_numbered, non_numbered_pfx):
                    style_config = resolve_non_numbered_heading_style(config, include_body_fallback=True)
                    is_non_numbered_heading = True
                else:
                    style_config = resolve_heading_style(styles_cfg, level_num, include_body_fallback=True)
            elif style_key == "heading":
                style_config = styles_cfg.get("heading") or styles_cfg.get("body") or styles_cfg.get("normal")
            if not style_config:
                if style_key == "body":
                    style_config = styles_cfg.get("normal")
                elif style_key == "normal":
                    style_config = styles_cfg.get("body")
                else:
                    style_config = styles_cfg.get("normal") or styles_cfg.get("body")
            if not style_config:
                continue

            if is_non_numbered_heading:
                if non_numbered_word_style is None:
                    non_numbered_word_style = _ensure_non_numbered_heading_style_definition(
                        doc,
                        config,
                        style_config,
                    )
                if non_numbered_word_style is not None:
                    para.style = non_numbered_word_style
            elif style_key.startswith("heading") and style_key != "heading":
                word_style_name = str(
                    (config.heading_model.level_to_word_style or {}).get(style_key)
                    or f"Heading {level_num}"
                )
                try:
                    para.style = doc.styles[word_style_name]
                except KeyError:
                    pass

            if _apply_style_to_paragraph(para, style_config):
                count += 1
            if _body_heading_starts_on_new_page(
                style_key,
                is_non_numbered_heading=is_non_numbered_heading,
                para_index=para_index,
                config=config,
                context=context,
            ):
                para.paragraph_format.page_break_before = True
            _keep_section_properties_last(para)

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 个段落",
                section="global",
                change_type="format",
                before="(mixed)",
                after="已统一样式",
            )
        if style_definition_count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{style_definition_count} 个 Word 标题样式定义",
                section="global",
                change_type="format",
                before="字号未同步",
                after="已同步到样式定义",
            )
        if body_style_definition_count:
            tracker.record(
                rule_name=self.meta.name,
                target="Word Normal 样式定义",
                section="global",
                change_type="format",
                before="正文样式未绑定",
                after="已绑定模板 body 样式",
            )


def _resolve_style_key(
    para: Paragraph,
    context: PipelineContext,
    para_index: int | None = None,
) -> str:
    resolved_index = _get_para_index(para) if para_index is None else para_index
    heading_map = getattr(context, "heading_map", None) or {}
    recognized_level = heading_map.get(resolved_index)
    if isinstance(recognized_level, int) and 1 <= recognized_level <= 8:
        return f"heading{recognized_level}"

    style = para.style
    style_name = style.name if style else ""
    style_lower = style_name.lower()

    if style_lower.startswith("heading") or "标题" in style_name:
        match = re.search(r"(\d+)", style_name)
        if match:
            return f"heading{match.group(1)}"
        return "heading"

    if "caption" in style_lower or "题注" in style_name:
        caption_kind = caption_kind_from_text(para.text)
        if caption_kind is not None:
            return f"{caption_kind}_caption"
        return "caption"
    if style_lower.startswith("toc") or "目录" in style_name:
        return "toc"
    if "header" in style_lower or "页眉" in style_name:
        return "header"
    if "footer" in style_lower or "页脚" in style_name:
        return "footer"

    doc_tree = context.doc_tree
    if doc_tree is not None:
        section_type = doc_tree.get_section_for_paragraph(resolved_index)
        mapped_style_key = style_key_for_section(section_type)
        if mapped_style_key:
            return mapped_style_key

    return "body"


def _get_para_index(para: Paragraph) -> int:
    body = para._element.getparent()
    if body is None:
        return -1
    for index, child in enumerate(body):
        if child is para._element:
            return index
    return -1


def _apply_style_to_paragraph(para: Paragraph, style_config) -> bool:
    size_pt = _resolve_size_pt(style_config)
    changed = False
    changed |= _apply_font(para, style_config, size_pt)
    changed |= _apply_alignment(para, style_config)
    changed |= _apply_spacing(para, style_config)
    changed |= _apply_indent(para, style_config, size_pt)
    _keep_section_properties_last(para)
    return changed


def _keep_section_properties_last(para: Paragraph) -> bool:
    paragraph_properties = para._element.find(qn("w:pPr"))
    if paragraph_properties is None:
        return False
    section_properties = paragraph_properties.find(qn("w:sectPr"))
    if section_properties is None:
        return False
    children_before = list(paragraph_properties)
    find_or_create_before(
        paragraph_properties,
        "w:sectPr",
        ("w:pPrChange",),
    )
    return children_before != list(paragraph_properties)


def _sync_heading_style_definitions(doc: Document, config: ResolvedConfig) -> int:
    styles_cfg = config.styles
    style_name_map = config.heading_model.level_to_word_style or {}
    count = 0

    for level in range(1, 9):
        style_key = f"heading{level}"
        style_config = resolve_heading_style(styles_cfg, level, include_body_fallback=True)
        if style_config is None:
            continue

        size_pt = _resolve_size_pt(style_config)
        if size_pt is None:
            continue

        word_style_name = str(style_name_map.get(style_key) or f"Heading {level}")
        try:
            style = doc.styles[word_style_name]
        except KeyError:
            continue

        changed = apply_style_text_format(
            style,
            font_cn=style_config.font_cn,
            font_en=style_config.font_en,
            size_pt=size_pt,
            bold=style_config.bold,
            italic=style_config.italic,
        )
        changed |= _apply_paragraph_format_to_style(style, style_config, size_pt)
        if changed:
            count += 1

    return count


def _sync_body_style_definition(doc: Document, config: ResolvedConfig) -> int:
    style_config = config.styles.get("body") or config.styles.get("normal")
    if style_config is None:
        return 0
    try:
        style = doc.styles["Normal"]
    except KeyError:
        return 0

    size_pt = _resolve_size_pt(style_config)
    changed = apply_style_text_format(
        style,
        font_cn=style_config.font_cn,
        font_en=style_config.font_en,
        size_pt=size_pt,
        bold=style_config.bold,
        italic=style_config.italic,
    )
    changed |= _apply_paragraph_format_to_style(style, style_config, size_pt)
    return 1 if changed else 0


def _apply_paragraph_format_to_style(style, style_config, size_pt: float | None) -> bool:
    paragraph_format = style.paragraph_format
    alignment = str(getattr(style_config, "alignment", "") or "")
    if alignment in ALIGNMENT_MAP:
        paragraph_format.alignment = ALIGNMENT_MAP[alignment]

    apply_paragraph_spacing(paragraph_format, style_config, style.element)
    if getattr(style_config, "line_spacing_pt", None) is not None:
        apply_line_spacing(
            paragraph_format,
            style_config.line_spacing_type,
            style_config.line_spacing_pt,
        )
        sync_spacing_ooxml(
            style.element,
            space_before_pt=style_config.space_before_pt,
            space_before_unit=getattr(style_config, "space_before_unit", "pt"),
            space_after_pt=style_config.space_after_pt,
            space_after_unit=getattr(style_config, "space_after_unit", "pt"),
            line_spacing_type=style_config.line_spacing_type,
            line_spacing_value=style_config.line_spacing_pt,
        )
    apply_style_config_indents(
        paragraph_format,
        style.element,
        style_config,
        size_pt=size_pt,
    )
    return True


def _ensure_non_numbered_heading_style_definition(
    doc: Document,
    config: ResolvedConfig,
    style_config,
):
    style_name = str(
        getattr(config.heading_model, "non_numbered_heading_style_name", "") or ""
    ).strip()
    if not style_name:
        return None

    try:
        style = doc.styles[style_name]
    except KeyError:
        style = doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
        heading_one_name = str(
            (config.heading_model.level_to_word_style or {}).get("heading1")
            or "Heading 1"
        ).strip()
        try:
            style.base_style = doc.styles[heading_one_name]
        except KeyError:
            pass

    disable_style_numbering(style)

    size_pt = _resolve_size_pt(style_config)
    if size_pt is not None:
        apply_style_text_format(
            style,
            font_cn=style_config.font_cn,
            font_en=style_config.font_en,
            size_pt=size_pt,
            bold=style_config.bold,
            italic=style_config.italic,
        )
    return style


def _body_heading_starts_on_new_page(
    style_key: str,
    *,
    is_non_numbered_heading: bool,
    para_index: int,
    config: ResolvedConfig,
    context: PipelineContext,
) -> bool:
    if style_key != "heading1" or is_non_numbered_heading:
        return False
    section_cfg = getattr(config, "section", None)
    if str(getattr(section_cfg, "section_break_type", "") or "") != "nextPage":
        return False

    doc_tree = context.doc_tree
    if doc_tree is None:
        return True
    section_getter = getattr(doc_tree, "get_section_for_paragraph", None)
    if not callable(section_getter):
        return True
    return canonicalize_section_type(section_getter(para_index)) == "body"


def _resolve_size_pt(style_config) -> float | None:
    return resolve_style_size_pt(style_config)


def _apply_font(para: Paragraph, style_config, size_pt: float | None) -> bool:
    font_cn = style_config.font_cn
    font_en = style_config.font_en
    bold = style_config.bold
    italic = style_config.italic

    if not (font_cn or font_en or size_pt is not None or bold is not None or italic is not None):
        return False

    for run in para.runs:
        if font_en:
            run.font.name = resolve_font(font_en, lang="en")
        if font_cn:
            set_run_east_asian_font(run, font_cn)
        if size_pt is not None:
            run.font.size = Pt(size_pt)
        if bold is not None:
            run.font.bold = bold
        if italic is not None:
            run.font.italic = italic
    return True


def _apply_alignment(para: Paragraph, style_config) -> bool:
    alignment = style_config.alignment
    if alignment and alignment in ALIGNMENT_MAP:
        para.paragraph_format.alignment = ALIGNMENT_MAP[alignment]
        return True
    return False


def _apply_spacing(para: Paragraph, style_config) -> bool:
    changed = False
    pf = para.paragraph_format

    apply_paragraph_spacing(pf, style_config, para._element)
    changed = True

    if style_config.line_spacing_pt is not None:
        apply_line_spacing(pf, style_config.line_spacing_type, style_config.line_spacing_pt)
        changed = True
    if changed:
        sync_spacing_ooxml(
            para._element,
            space_before_pt=style_config.space_before_pt,
            space_before_unit=getattr(style_config, "space_before_unit", "pt"),
            space_after_pt=style_config.space_after_pt,
            space_after_unit=getattr(style_config, "space_after_unit", "pt"),
            line_spacing_type=style_config.line_spacing_type,
            line_spacing_value=style_config.line_spacing_pt,
        )

    return changed


def _apply_indent(para: Paragraph, style_config, size_pt: float | None) -> bool:
    apply_style_config_indents(
        para.paragraph_format,
        para._element,
        style_config,
        size_pt=size_pt,
    )
    return True
