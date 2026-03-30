"""
reference_format — 参考文献格式模块

统一参考文献条目的格式（悬挂缩进、字号、字体、编号清理）。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn, find_or_create
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.run_ops import set_run_east_asian_font

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


_RE_REF_ENTRY = re.compile(r"^\s*\[?\d+[.\]）)]\s*")


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
        enabled_by_default=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        ref_cfg = config.reference_style
        ref_start = _find_reference_start(doc)
        if ref_start is None:
            return

        count = 0
        for i in range(ref_start, len(doc.paragraphs)):
            para = doc.paragraphs[i]
            text = (para.text or "").strip()
            if not text:
                continue

            if _is_reference_entry(text):
                _format_reference_entry(para, ref_cfg)
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


def _find_reference_start(doc: Document) -> int | None:
    """查找参考文献区域的起始位置。"""
    ref_titles = {"参考文献", "references", "bibliography", "文献"}

    for i, para in enumerate(doc.paragraphs):
        text = (para.text or "").strip().lower()
        for title in ref_titles:
            if title in text and len(text) < 30:
                return i + 1

    return None


def _is_reference_entry(text: str) -> bool:
    """判断文本是否为参考文献条目。"""
    # [1] / 1. / 1) 开头
    if _RE_REF_ENTRY.match(text):
        return True
    # 较长文本但不像标题
    if len(text) > 30 and not text.startswith("第"):
        return True
    return False


def _format_reference_entry(para: Paragraph, ref_cfg) -> None:
    """格式化单条参考文献。"""
    pf = para.paragraph_format

    # 对齐
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 缩进：悬挂缩进
    hanging = ref_cfg.hanging_indent_cm
    pf.left_indent = Cm(hanging)
    pf.first_line_indent = Cm(-hanging)

    # 间距
    space_pt = ref_cfg.space_after_pt
    if space_pt is not None:
        pf.space_after = Pt(space_pt)
        pf.space_before = Pt(0)

    # 字体
    font_cn = ref_cfg.font_cn
    font_en = ref_cfg.font_en
    size_pt = ref_cfg.size_pt

    for run in para.runs:
        if font_en:
            run.font.name = resolve_font(font_en, lang="en")
        if font_cn:
            set_run_east_asian_font(run, font_cn)
        if size_pt:
            run.font.size = Pt(size_pt)

    # 清除列表编号
    pPr = para._element.find(qn("w:pPr"))
    if pPr is not None:
        numPr = pPr.find(qn("w:numPr"))
        if numPr is not None:
            pPr.remove(numPr)
