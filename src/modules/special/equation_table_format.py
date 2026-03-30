"""
equation_table_format — 公式表格格式模块

识别并格式化公式表格（居中公式 + 右对齐编号）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn, find_or_create

if TYPE_CHECKING:
    from docx import Document
    from docx.table import Table
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class EquationTableFormatModule(BaseModule):
    """公式表格格式模块。

    职责：
    - 识别公式表格（无边框 + 含数学对象）
    - 公式单元格居中
    - 编号单元格右对齐
    - 清除公式表格边框
    """

    meta = ModuleMeta(
        name="equation_table_format",
        description="公式表格格式",
        category="special",
        requires_config=(),
        soft_after=("table_format",),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        count = 0

        for table in doc.tables:
            if not _is_equation_table(table):
                continue

            _format_equation_table(table)
            count += 1

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 个公式表格",
                section="global",
                change_type="format",
                before="(mixed)",
                after="公式居中+编号右对齐",
            )


def _is_equation_table(table: Table) -> bool:
    """检测公式表格。"""
    tbl_el = table._element
    rows = tbl_el.findall(qn("w:tr"))

    # 公式表格通常 1-5 行
    if len(rows) > 10:
        return False

    # 检查是否含 OMML
    m_ns = "http://schemas.openxmlformats.org/officeDocument/2006/math"
    has_math = (
        tbl_el.find(f".//{{{m_ns}}}oMath") is not None
        or tbl_el.find(f".//{{{m_ns}}}oMathPara") is not None
    )

    return has_math


def _format_equation_table(table: Table) -> None:
    """格式化公式表格。"""
    # 清除边框
    tbl_el = table._element
    tblPr = find_or_create(tbl_el, "w:tblPr")
    tblBorders = find_or_create(tblPr, "w:tblBorders")

    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = find_or_create(tblBorders, f"w:{side}")
        border.set(qn("w:val"), "none")
        border.set(qn("w:sz"), "0")

    # 居中表格
    jc = find_or_create(tblPr, "w:jc")
    jc.set(qn("w:val"), "center")

    # 单元格对齐
    for row in table.rows:
        cells = row.cells
        if len(cells) >= 2:
            # 最后一个单元格（编号）右对齐
            for para in cells[-1].paragraphs:
                para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            # 其他单元格（公式）居中
            for cell in cells[:-1]:
                for para in cell.paragraphs:
                    para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            for cell in cells:
                for para in cell.paragraphs:
                    para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
