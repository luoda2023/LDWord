"""Paragraph style module."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from src.config.heading_style_semantics import resolve_heading_style, resolve_non_numbered_heading_style
from src.modules.structure.heading_numbering import _should_skip_numbering
from src.config.section_semantics import style_key_for_section
from src.config.style_semantics import (
    resolve_style_size_pt,
)
from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.indent_ops import apply_style_config_indents
from src.shared.engine.line_spacing_ops import apply_line_spacing, apply_paragraph_spacing, sync_spacing_ooxml
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
        enabled_by_default=True,
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
        style_definition_count = _sync_heading_style_definitions(doc, config)
        count = 0

        for para in doc.paragraphs:
            text = (para.text or "").strip()
            if not text:
                continue

            style_key = _resolve_style_key(para, context)
            if style_key.startswith("heading") and style_key != "heading":
                level_num = int(style_key.replace("heading", "") or "0")
                if level_num > max_levels:
                    style_key = "normal"

            style_config = styles_cfg.get(style_key)
            if style_key.startswith("heading") and style_key != "heading":
                if _should_skip_numbering(para, non_numbered, non_numbered_pfx):
                    style_config = resolve_non_numbered_heading_style(config, include_body_fallback=True)
                else:
                    style_config = resolve_heading_style(styles_cfg, level_num, include_body_fallback=True)
            elif style_key == "heading":
                style_config = styles_cfg.get("heading") or styles_cfg.get("body") or styles_cfg.get("normal")
            if not style_config:
                style_config = styles_cfg.get("normal")
            if not style_config:
                continue

            if _apply_style_to_paragraph(para, style_config):
                count += 1

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


def _resolve_style_key(para: Paragraph, context: PipelineContext) -> str:
    style = para.style
    style_name = style.name if style else ""
    style_lower = style_name.lower()

    if style_lower.startswith("heading") or "标题" in style_name:
        match = re.search(r"(\d+)", style_name)
        if match:
            return f"heading{match.group(1)}"
        return "heading"

    if "caption" in style_lower or "题注" in style_name:
        return "caption"
    if style_lower.startswith("toc") or "目录" in style_name:
        return "toc"
    if "header" in style_lower or "页眉" in style_name:
        return "header"
    if "footer" in style_lower or "页脚" in style_name:
        return "footer"

    doc_tree = context.doc_tree
    if doc_tree is not None:
        section_type = doc_tree.get_section_for_paragraph(_get_para_index(para))
        mapped_style_key = style_key_for_section(section_type)
        if mapped_style_key:
            return mapped_style_key

    return "normal"


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
    return changed


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

        if apply_style_text_format(
            style,
            font_cn=style_config.font_cn,
            font_en=style_config.font_en,
            size_pt=size_pt,
        ):
            count += 1

    return count


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
