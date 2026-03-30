"""
figure_table_center — 图表居中模块

将包含图片的段落和表格对象居中对齐。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn, find_or_create

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class FigureTableCenterModule(BaseModule):
    """图表居中模块。

    职责：
    - 将包含图片的段落居中
    - 将表格居中
    - 保留已有的图片行距安全设置
    """

    meta = ModuleMeta(
        name="figure_table_center",
        description="图表居中",
        category="table",
        requires_config=(),
        soft_after=("caption",),
        enabled_by_default=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        fig_count = 0
        tbl_count = 0

        # 1. 图片段落居中
        for i, para in enumerate(doc.paragraphs):
            if _para_has_image(para):
                _center_paragraph(para)
                fig_count += 1

        # 2. 表格居中
        for table in doc.tables:
            _center_table(table)
            tbl_count += 1

        if fig_count or tbl_count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{fig_count} 图片, {tbl_count} 表格",
                section="global",
                change_type="format",
                before="(mixed)",
                after="居中对齐",
            )


# ── 判断与操作 ───────────────────────────────────

def _para_has_image(para: Paragraph) -> bool:
    """判断段落是否包含图片。"""
    drawing_ns = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    pict_ns = "urn:schemas-microsoft-com:vml"

    for elem in para._element.iter():
        if elem.tag.endswith("}drawing") or elem.tag.endswith("}pict"):
            return True
        if elem.tag == f"{{{drawing_ns}}}inline":
            return True
        if elem.tag == f"{{{drawing_ns}}}anchor":
            return True
    return False


def _center_paragraph(para: Paragraph) -> None:
    """居中段落 + 清除缩进。"""
    pf = para.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.left_indent = None
    pf.first_line_indent = None


def _center_table(table: Table) -> None:
    """居中表格。"""
    tbl = table._element
    tblPr = find_or_create(tbl, "w:tblPr")
    jc = find_or_create(tblPr, "w:jc")
    jc.set(qn("w:val"), "center")
