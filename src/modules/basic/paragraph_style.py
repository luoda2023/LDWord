"""Paragraph style module."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from src.config.style_semantics import (
    config_indent_value_to_pt,
    normalize_line_spacing_type,
    parse_font_size_input,
    resolve_line_spacing_value,
    resolve_style_special_indent,
)
from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.font_resolver import resolve_font
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
            if not style_config and style_key.startswith("heading") and style_key != "heading":
                style_config = styles_cfg.get("heading")
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
        if section_type == "references":
            return "references_body"
        if section_type in ("abstract_cn", "abstract_en"):
            return "abstract_body"
        if section_type == "appendix":
            return "appendix_body"

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
        style_config = styles_cfg.get(style_key) or styles_cfg.get("heading")
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
    size_pt = style_config.size_pt
    if size_pt is None:
        size_text = style_config.size_display
        if size_text:
            try:
                size_pt = parse_font_size_input(size_text)
            except (TypeError, ValueError):
                size_pt = None
    return size_pt


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

    if style_config.space_before_pt is not None:
        pf.space_before = Pt(style_config.space_before_pt)
        changed = True
    if style_config.space_after_pt is not None:
        pf.space_after = Pt(style_config.space_after_pt)
        changed = True

    if style_config.line_spacing_pt is not None:
        line_kind = normalize_line_spacing_type(style_config.line_spacing_type)
        line_value = resolve_line_spacing_value(line_kind, style_config.line_spacing_pt)
        if line_kind == "exact":
            pf.line_spacing = Pt(line_value)
        else:
            pf.line_spacing = line_value
        changed = True

    return changed


def _apply_indent(para: Paragraph, style_config, size_pt: float | None) -> bool:
    pf = para.paragraph_format
    effective_pt = size_pt or 12.0

    left_pt = config_indent_value_to_pt(
        getattr(style_config, "left_indent_chars", 0.0),
        effective_pt,
        getattr(style_config, "left_indent_unit", "chars"),
    )
    right_pt = config_indent_value_to_pt(
        getattr(style_config, "right_indent_chars", 0.0),
        effective_pt,
        getattr(style_config, "right_indent_unit", "chars"),
    )
    pf.left_indent = Pt(left_pt)
    pf.right_indent = Pt(right_pt)

    special = resolve_style_special_indent(style_config)
    special_mode = str(special["mode"])
    special_pt = config_indent_value_to_pt(
        special["value"],
        effective_pt,
        str(special["unit"]),
    )

    if special_mode == "hanging" and special_pt > 0:
        pf.left_indent = Pt(max(left_pt, special_pt))
        pf.first_line_indent = Pt(-special_pt)
    elif special_mode == "first_line" and special_pt > 0:
        pf.first_line_indent = Pt(special_pt)
    else:
        pf.first_line_indent = Pt(0)

    return True
