"""
table_format — 表格格式模块

统一表格样式：列宽自适应、行高、字体、边框、三线表、行距。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lxml import etree
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn, find, find_or_create
from src.shared.engine.paragraph_iter import iter_table_cells
from src.shared.engine.table_builder import (
    set_table_borders, set_repeat_header_row, set_row_height,
)
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.run_ops import set_run_east_asian_font

if TYPE_CHECKING:
    from docx import Document
    from docx.table import Table
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


# ── 常量 ─────────────────────────────────────────────
_A4_WIDTH_TWIPS = 11906       # 21cm ≈ 11906 twips
_MIN_COL_WIDTH = 850          # 每列最小 ~1.5cm
_CELL_PADDING = 216           # 单元格左右内边距合计
_CJK_CHAR_W = 210             # 中文字符宽 (10.5pt 字号)
_ASCII_CHAR_W = 115           # 英文字符宽
_M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


class TableFormatModule(BaseModule):
    """表格格式模块。

    职责：
    - 列宽自适应（权重分析 → 最小宽度 → 分配 → 写回）
    - 表格字体统一（中英文分别设置）
    - 边框样式（三线表 / 全框线 / 无边框）
    - 表头行重复
    - 单元格对齐与行距
    """

    meta = ModuleMeta(
        name="table_format",
        description="表格格式",
        category="table",
        requires_config=("table",),
        enabled_by_default=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        tbl_cfg = config.table

        avail_w = _available_width(config)
        count = 0

        for idx, table in enumerate(doc.tables):
            if _is_equation_table(table):
                continue

            tbl_el = table._element

            # Step 1: 边框
            border_mode = tbl_cfg.border_mode
            if border_mode == "three_line":
                _apply_three_line_borders(tbl_el, tbl_cfg)
            else:
                set_table_borders(table, mode=border_mode)

            # Step 2: 表头行重复
            if tbl_cfg.repeat_header:
                set_repeat_header_row(table, row=0)

            # Step 3: 列宽自适应
            layout = tbl_cfg.layout_mode
            if layout in ("smart", "full"):
                _auto_fit_columns(tbl_el, avail_w, layout)

            # Step 4: 单元格字体 + 行距
            _format_table_cells(table, tbl_cfg)

            # Step 5: 行高
            row_height = tbl_cfg.row_height_pt
            if row_height:
                for r_idx in range(len(table.rows)):
                    set_row_height(table, r_idx, row_height)

            count += 1

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 个表格",
                section="global",
                change_type="format",
                before="(mixed)",
                after=f"border={tbl_cfg.border_mode}, layout={tbl_cfg.layout_mode}",
            )


# ── 列宽自适应 ─────────────────────────────────────

def _available_width(config) -> int:
    """Return available table width in twips."""
    ps = config.page_setup
    margin = ps.margin
    left_cm = margin.left_cm
    right_cm = margin.right_cm
    gutter_cm = ps.gutter_cm

    return _A4_WIDTH_TWIPS - _cm_to_twips(left_cm) - _cm_to_twips(right_cm) - _cm_to_twips(gutter_cm)


def _cm_to_twips(cm: float) -> int:
    return int(cm * 567)


def _auto_fit_columns(tbl_el, avail_w: int, layout: str) -> None:
    """列宽自适应：权重分析 → 最小宽度 → 分配 → 写回。"""
    num_cols = _count_cols(tbl_el)
    if num_cols == 0:
        return

    # Step 1: 权重分析
    weights = _analyze_col_weights(tbl_el, num_cols)

    # Step 2: 首行最小宽度
    min_widths = _first_row_min_widths(tbl_el, num_cols)

    # Step 3: 分配宽度
    widths = _distribute_widths(weights, avail_w, min_widths)

    # Step 4: 写回
    _set_grid_cols(tbl_el, widths)
    _set_table_width(tbl_el, sum(widths))
    _set_table_alignment(tbl_el, "center")


def _count_cols(tbl_el) -> int:
    """推断列数（取首行 gridSpan 之和）。"""
    for tr in tbl_el.findall(qn("w:tr")):
        n = 0
        for tc in tr.findall(qn("w:tc")):
            span = 1
            tcPr = tc.find(qn("w:tcPr"))
            if tcPr is not None:
                gs = tcPr.find(qn("w:gridSpan"))
                if gs is not None:
                    span = int(gs.get(qn("w:val"), "1"))
            n += span
        if n > 0:
            return n
    return 0


def _analyze_col_weights(tbl_el, num_cols: int) -> list[float]:
    """分析每列最大内容权重（中文 × 2, 英文 × 1）。"""
    weights = [0.0] * num_cols

    for tr in tbl_el.findall(qn("w:tr")):
        grid_idx = 0
        trPr = tr.find(qn("w:trPr"))
        if trPr is not None:
            gb = trPr.find(qn("w:gridBefore"))
            if gb is not None:
                grid_idx = int(gb.get(qn("w:val"), "0"))

        for tc in tr.findall(qn("w:tc")):
            span = 1
            tcPr = tc.find(qn("w:tcPr"))
            if tcPr is not None:
                gs = tcPr.find(qn("w:gridSpan"))
                if gs is not None:
                    span = int(gs.get(qn("w:val"), "1"))

            # 计算文本权重
            text = _get_cell_text(tc)
            tw = sum(2.0 if ord(ch) > 0x7F else 1.0 for ch in text)

            # 均分到所跨列
            per_col = tw / span if span > 0 else 0
            for k in range(span):
                ci = grid_idx + k
                if ci < num_cols:
                    weights[ci] = max(weights[ci], per_col)

            grid_idx += span

    return weights


def _first_row_min_widths(tbl_el, num_cols: int) -> list[int]:
    """计算首行各列最小宽度（保证表头不换行）。"""
    mins = [_MIN_COL_WIDTH] * num_cols
    rows = tbl_el.findall(qn("w:tr"))
    if not rows:
        return mins

    tr = rows[0]
    grid_idx = 0

    for tc in tr.findall(qn("w:tc")):
        span = 1
        tcPr = tc.find(qn("w:tcPr"))
        if tcPr is not None:
            gs = tcPr.find(qn("w:gridSpan"))
            if gs is not None:
                span = int(gs.get(qn("w:val"), "1"))

        text = _get_cell_text(tc).strip()
        if text:
            need = _text_width_twips(text)
            per_col = need // span if span > 0 else need
            for k in range(span):
                ci = grid_idx + k
                if ci < num_cols:
                    mins[ci] = max(mins[ci], per_col)

        grid_idx += span

    return mins


def _distribute_widths(
    weights: list[float],
    total: int,
    min_widths: list[int],
) -> list[int]:
    """按权重分配列宽，保证最小宽度且总宽精确。"""
    n = len(weights)
    if n == 0:
        return []

    total_weight = sum(weights) or 1.0

    # Step 1: 初始按比例分配
    raw = [max(int(w / total_weight * total), min_widths[i]) for i, w in enumerate(weights)]

    # Step 2: 如果总和超出，按比例缩减
    raw_sum = sum(raw)
    if raw_sum > total:
        scale = total / raw_sum
        raw = [max(int(w * scale), _MIN_COL_WIDTH) for w in raw]

    # Step 3: 误差修正 — 将剩余空间分配给最大权重列
    diff = total - sum(raw)
    if diff != 0 and raw:
        max_idx = weights.index(max(weights))
        raw[max_idx] += diff

    return raw


# ── 三线表边框 ─────────────────────────────────────

def _apply_three_line_borders(tbl_el, tbl_cfg) -> None:
    """应用严格三线表：上/下外边线同宽，表头下分隔线更细，无竖线/内部横线。"""
    outer_w = tbl_cfg.three_line_header_width_pt
    inner_w = tbl_cfg.three_line_bottom_width_pt

    # 表格级：top + bottom 粗线
    tblPr = find_or_create(tbl_el, "w:tblPr")
    tblBorders = find_or_create(tblPr, "w:tblBorders")

    for tag in ("w:top", "w:bottom"):
        border = find_or_create(tblBorders, tag)
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), str(int(outer_w * 8)))  # pt → eighth pt
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), "auto")

    # 清除左右竖线
    for tag in ("w:left", "w:right", "w:insideH", "w:insideV"):
        border = find_or_create(tblBorders, tag)
        border.set(qn("w:val"), "none")
        border.set(qn("w:sz"), "0")

    # 首行底部加粗线
    rows = tbl_el.findall(qn("w:tr"))
    if rows:
        for tc in rows[0].findall(qn("w:tc")):
            tcPr = find_or_create(tc, "w:tcPr")
            tcBorders = find_or_create(tcPr, "w:tcBorders")
            bottom = find_or_create(tcBorders, "w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), str(int(inner_w * 8)))
            bottom.set(qn("w:space"), "0")
            bottom.set(qn("w:color"), "auto")


# ── 网格列写入 ─────────────────────────────────────

def _set_grid_cols(tbl_el, widths: list[int]) -> None:
    """设置 tblGrid 各列宽度。"""
    grid = tbl_el.find(qn("w:tblGrid"))
    if grid is None:
        # 插入到 tblPr 之后
        tblPr = tbl_el.find(qn("w:tblPr"))
        idx = list(tbl_el).index(tblPr) + 1 if tblPr is not None else 0
        grid = etree.Element(qn("w:tblGrid"))
        tbl_el.insert(idx, grid)
    else:
        for old in grid.findall(qn("w:gridCol")):
            grid.remove(old)

    for w in widths:
        col = etree.SubElement(grid, qn("w:gridCol"))
        col.set(qn("w:w"), str(w))


def _set_table_width(tbl_el, total_w: int) -> None:
    """设置 tblPr/tblW 为精确宽度 (dxa)。"""
    tblPr = find_or_create(tbl_el, "w:tblPr")
    tblW = find_or_create(tblPr, "w:tblW")
    tblW.set(qn("w:w"), str(total_w))
    tblW.set(qn("w:type"), "dxa")


def _set_table_alignment(tbl_el, align: str) -> None:
    """设置表格水平对齐 (left/center/right)。"""
    tblPr = find_or_create(tbl_el, "w:tblPr")
    jc = find_or_create(tblPr, "w:jc")
    jc.set(qn("w:val"), align)


# ── 单元格格式 ─────────────────────────────────────

def _format_table_cells(table: Table, tbl_cfg) -> None:
    """统一表格单元格字体、对齐和行距。"""
    font_cn = tbl_cfg.font_cn
    font_en = tbl_cfg.font_en
    size_pt = tbl_cfg.size_pt
    alignment = tbl_cfg.cell_alignment
    line_spacing = tbl_cfg.line_spacing_mode

    for row_idx, col_idx, cell in iter_table_cells(table):
        for para in cell.paragraphs:
            pf = para.paragraph_format

            # 对齐
            if alignment == "center":
                pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif alignment == "left":
                pf.alignment = WD_ALIGN_PARAGRAPH.LEFT

            # 行距
            if line_spacing == "single":
                pf.line_spacing = 1.0
            elif line_spacing == "one_half":
                pf.line_spacing = 1.5

            # 段前段后清零（表格内紧凑排列）
            pf.space_before = Pt(0)
            pf.space_after = Pt(0)

            # 字体+字号
            for run in para.runs:
                if font_en:
                    run.font.name = resolve_font(font_en, lang="en")
                if font_cn:
                    set_run_east_asian_font(run, font_cn)
                if size_pt:
                    run.font.size = Pt(size_pt)


# ── 工具函数 ─────────────────────────────────────────

def _get_cell_text(tc) -> str:
    """提取单元格纯文本。"""
    parts = []
    for t in tc.iter(qn("w:t")):
        if t.text:
            parts.append(t.text)
    return "".join(parts)


def _text_width_twips(text: str) -> int:
    """估算文本单行宽度 (twips)。"""
    w = sum(_CJK_CHAR_W if ord(ch) > 0x7F else _ASCII_CHAR_W for ch in text)
    return w + _CELL_PADDING


def _is_equation_table(table: Table) -> bool:
    """判断是否为公式表格（≤5行 + 含 OMML 数学对象）。"""
    tbl_el = table._element
    rows = tbl_el.findall(qn("w:tr"))
    if len(rows) > 5:
        return False

    if tbl_el.find(f"{{{_M_NS}}}oMathPara") is not None:
        return True
    if tbl_el.find(f"{{{_M_NS}}}oMath") is not None:
        return True

    # 文本层公式检测：行内仅含数学符号
    for tr in rows:
        for tc in tr.findall(qn("w:tc")):
            text = _get_cell_text(tc).strip()
            if text and re.search(r"[=≈≠≤≥∑∫∏√→←↔⇌±∂]", text):
                # 含数学符号且行少 → 可能是公式表
                if len(rows) <= 3:
                    return True

    return False

