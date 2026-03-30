"""
table_builder — 表格构建工具

创建/修改 Word 表格：行列操作、边框设置、单元格合并。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from src.shared.engine.ooxml_ops import qn, find_or_create
from src.shared.engine.units import pt_to_emu

if TYPE_CHECKING:
    from docx import Document
    from docx.table import Table


def create_table(
    doc: Document,
    rows: int,
    cols: int,
    *,
    style: str | None = None,
) -> Table:
    """在文档末尾创建表格。"""
    table = doc.add_table(rows=rows, cols=cols)
    if style:
        table.style = style
    return table


def set_cell_text(table: Table, row: int, col: int, text: str) -> None:
    """设置单元格文本。"""
    table.rows[row].cells[col].text = text


def set_column_width(table: Table, col: int, width_cm: float) -> None:
    """设置列宽 (cm)。"""
    from src.shared.engine.units import cm_to_emu
    width = cm_to_emu(width_cm)
    for row in table.rows:
        cell = row.cells[col]
        tc = cell._element
        tcPr = find_or_create(tc, "w:tcPr")
        tcW = find_or_create(tcPr, "w:tcW")
        tcW.set(qn("w:w"), str(width))
        tcW.set(qn("w:type"), "dxa")


def set_row_height(table: Table, row: int, height_pt: float) -> None:
    """设置行高 (pt)。"""
    from src.shared.engine.units import pt_to_twip
    tr = table.rows[row]._element
    trPr = find_or_create(tr, "w:trPr")
    trHeight = find_or_create(trPr, "w:trHeight")
    trHeight.set(qn("w:val"), str(pt_to_twip(height_pt)))
    trHeight.set(qn("w:hRule"), "atLeast")


def merge_cells(
    table: Table,
    start_row: int, start_col: int,
    end_row: int, end_col: int,
) -> None:
    """合并单元格区域。"""
    cell_a = table.cell(start_row, start_col)
    cell_b = table.cell(end_row, end_col)
    cell_a.merge(cell_b)


# ── 边框 ─────────────────────────────────────────

def set_table_borders(
    table: Table,
    mode: str = "full_grid",
    *,
    width_pt: float = 0.5,
    header_width_pt: float = 1.0,
    bottom_width_pt: float = 0.5,
) -> None:
    """设置表格边框样式。

    mode:
    - "full_grid": 全框线
    - "three_line": 三线表
    - "none": 无边框
    """
    if mode == "full_grid":
        _apply_full_grid(table, width_pt)
    elif mode == "three_line":
        _apply_three_line(table, header_width_pt, bottom_width_pt)
    elif mode == "none":
        _apply_no_border(table)


def _apply_full_grid(table: Table, width_pt: float) -> None:
    """全框线。"""
    tbl = table._element
    tblPr = find_or_create(tbl, "w:tblPr")
    borders = find_or_create(tblPr, "w:tblBorders")

    width_eighth = int(width_pt * 8)
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = find_or_create(borders, f"w:{side}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), str(width_eighth))
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), "000000")


def _apply_three_line(table: Table, outer_pt: float, inner_pt: float) -> None:
    """严格三线表：上/下外边线同宽，表头下分隔线更细，无竖线/内部横线。"""
    tbl = table._element
    tblPr = find_or_create(tbl, "w:tblPr")
    borders = find_or_create(tblPr, "w:tblBorders")

    outer_eighth = max(1, int(outer_pt * 8))
    inner_eighth = max(1, int(inner_pt * 8))

    for side in ("left", "right", "insideH", "insideV"):
        border = find_or_create(borders, f"w:{side}")
        border.set(qn("w:val"), "none")
        border.set(qn("w:sz"), "0")

    for side in ("top", "bottom"):
        border = find_or_create(borders, f"w:{side}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), str(outer_eighth))
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), "000000")

    if not table.rows:
        return

    for cell in table.rows[0].cells:
        tc_pr = find_or_create(cell._element, "w:tcPr")
        tc_borders = find_or_create(tc_pr, "w:tcBorders")
        border = find_or_create(tc_borders, "w:bottom")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), str(inner_eighth))
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), "000000")


def _apply_no_border(table: Table) -> None:
    """无边框。"""
    tbl = table._element
    tblPr = find_or_create(tbl, "w:tblPr")
    borders = find_or_create(tblPr, "w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = find_or_create(borders, f"w:{side}")
        border.set(qn("w:val"), "none")
        border.set(qn("w:sz"), "0")


def set_repeat_header_row(table: Table, row: int = 0) -> None:
    """设置重复标题行（跨页时重复表头）。"""
    tr = table.rows[row]._element
    trPr = find_or_create(tr, "w:trPr")
    find_or_create(trPr, "w:tblHeader")
