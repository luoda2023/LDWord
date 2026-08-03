"""reference_format — 参考文献格式模块."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from src.config.style_semantics import apply_style_special_indent
from src.config.template import StyleConfig
from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.document_scope_runtime import document_scope_allows_role
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.indent_ops import apply_style_config_indents
from src.shared.engine.line_spacing_ops import apply_line_spacing, apply_paragraph_spacing, sync_spacing_ooxml
from src.shared.engine.ooxml_ops import qn
from src.shared.engine.run_ops import set_run_east_asian_font

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


_RE_REF_ENTRY = re.compile(r"^\s*\[?\d+[.\]）)]\s*")

ALIGNMENT_MAP: dict[str, int] = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    "distribute": WD_ALIGN_PARAGRAPH.DISTRIBUTE,
}


class ReferenceFormatModule(BaseModule):
    """参考文献格式模块。

    职责：
    - 识别参考文献区域
    - 统一条目格式（字体、字号、行距）
    - 设置悬挂缩进
    - 清除列表编号标记
    """

    meta = ModuleMeta(
        name="reference_format",
        description="参考文献格式",
        category="special",
        requires_config=("reference_style",),
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
        if not document_scope_allows_role(context, "references"):
            return
        ref_range = _resolve_reference_range(doc, context)
        if ref_range is None:
            return
        ref_start, ref_end = ref_range

        entry_style = _resolve_reference_entry_style(config)
        count = 0
        for i in range(ref_start, ref_end):
            para = doc.paragraphs[i]
            text = (para.text or "").strip()
            if not text:
                continue

            if _is_reference_entry(text):
                _format_reference_entry(para, entry_style)
                count += 1

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 条参考文献",
                section="references",
                change_type="format",
                before="(mixed)",
                after="已统一格式+悬挂缩进",
            )


def _resolve_reference_entry_style(config: ResolvedConfig) -> StyleConfig:
    """Combine the effective reference style with scene-owned paragraph rules."""
    base_style = deepcopy(
        config.styles.get("references_body")
        or config.styles.get("body")
        or config.styles.get("normal")
        or StyleConfig()
    )
    ref_cfg = config.reference_style

    base_style.space_before_pt = 0.0
    base_style.space_before_unit = "pt"
    if ref_cfg.space_after_pt is not None:
        base_style.space_after_pt = ref_cfg.space_after_pt
        base_style.space_after_unit = getattr(ref_cfg, "space_after_unit", "pt")

    apply_style_special_indent(base_style, "hanging", ref_cfg.hanging_indent_cm, "cm")
    return base_style


def _resolve_reference_range(
    doc: Document,
    context: PipelineContext,
) -> tuple[int, int] | None:
    total = len(doc.paragraphs)
    if total <= 0:
        return None

    doc_tree = getattr(context, "doc_tree", None)
    if doc_tree is not None:
        ref_section = getattr(doc_tree, "get_section", lambda *_: None)("references")
        if ref_section is not None:
            start = max(0, min(int(getattr(ref_section, "start_index", 0)), total))
            end = max(start, min(int(getattr(ref_section, "end_index", total)), total))
            if end > start:
                return (start, end)

    return None


def _is_reference_entry(text: str) -> bool:
    """判断文本是否为参考文献条目。"""
    if _RE_REF_ENTRY.match(text):
        return True
    if len(text) > 30 and not text.startswith("第"):
        return True
    return False


def _format_reference_entry(para: Paragraph, style_config: StyleConfig) -> None:
    """格式化单条参考文献。"""
    pf = para.paragraph_format
    pf.alignment = ALIGNMENT_MAP.get(
        str(getattr(style_config, "alignment", "") or "").strip().lower(),
        WD_ALIGN_PARAGRAPH.JUSTIFY,
    )

    apply_paragraph_spacing(pf, style_config, para._element)
    apply_line_spacing(pf, style_config.line_spacing_type, style_config.line_spacing_pt)
    sync_spacing_ooxml(
        para._element,
        space_before_pt=style_config.space_before_pt,
        space_before_unit=getattr(style_config, "space_before_unit", "pt"),
        space_after_pt=style_config.space_after_pt,
        space_after_unit=getattr(style_config, "space_after_unit", "pt"),
        line_spacing_type=style_config.line_spacing_type,
        line_spacing_value=style_config.line_spacing_pt,
    )
    apply_style_config_indents(
        pf,
        para._element,
        style_config,
        size_pt=style_config.size_pt,
    )

    font_cn = style_config.font_cn
    font_en = style_config.font_en
    size_pt = style_config.size_pt
    bold = style_config.bold
    italic = style_config.italic

    for run in para.runs:
        if font_en:
            run.font.name = resolve_font(font_en, lang="en")
        if font_cn:
            set_run_east_asian_font(run, font_cn)
        if size_pt:
            run.font.size = Pt(size_pt)
        run.font.bold = bool(bold)
        run.font.italic = bool(italic)

    # Only strip numPr that is list-indentation spillover (numId=0),
    # preserve intentional reference numbering (numId > 0, e.g. [1] [2] ...).
    p_pr = para._element.find(qn("w:pPr"))
    if p_pr is not None:
        num_pr = p_pr.find(qn("w:numPr"))
        if num_pr is not None and not _has_intentional_numbering(num_pr):
            p_pr.remove(num_pr)


def _has_intentional_numbering(num_pr) -> bool:
    """numId > 0 means intentional document numbering."""
    num_id = num_pr.find(qn("w:numId"))
    if num_id is None:
        return False
    try:
        return int(num_id.get(qn("w:val"), "0")) > 0
    except (ValueError, TypeError):
        return False
