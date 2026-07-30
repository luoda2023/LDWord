"""equation_table_format - formula-table formatting module."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.document_scope_runtime import document_scope_allows_paragraph
from src.modules.table.table_format import _is_equation_table, top_level_table_anchor_positions
from src.config.style_semantics import normalize_spacing_unit, spacing_value_to_pt
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.line_spacing_ops import apply_line_spacing, sync_spacing_ooxml
from src.shared.engine.ooxml_ops import find_or_create, qn
from src.shared.engine.sequence_numbering import (
    build_heading_chapter_ranges,
    parse_chapter_numbering_format,
    resolve_chapter_number,
)

if TYPE_CHECKING:
    from docx import Document
    from docx.table import _Cell, Table
    from docx.text.paragraph import Paragraph
    from docx.text.run import Run
    from lxml.etree import _Element
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


_PARAGRAPH_ALIGNMENTS: dict[str, WD_ALIGN_PARAGRAPH] = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
}

_TABLE_ALIGNMENTS = frozenset({"left", "center", "right"})
_WRAPPER_PAIRS = {
    "(": ")",
    "（": "）",
    "[": "]",
    "【": "】",
}
_EQUATION_NUMBER_RE = re.compile(
    r"^\s*(?P<open>[\(\[（【])?\s*(?P<head>\d+)"
    r"(?:\s*(?P<sep>[.\-:—–_/])\s*(?P<tail>\d+))?\s*(?P<close>[\)\]）】])?\s*$"
)


@dataclass(frozen=True)
class EquationTablePlan:
    table_alignment: str
    formula_alignment: str
    number_alignment: str
    formula_font_name: str | None
    formula_font_size_pt: float | None
    formula_line_spacing: float
    formula_space_before_pt: float
    formula_space_before_unit: str
    formula_space_after_pt: float
    formula_space_after_unit: str
    number_font_name: str | None
    number_font_size_pt: float | None
    unify_spacing: bool
    include_chapter_number: bool
    numbering_separator: str
    numbering_format: str


@dataclass
class EquationNumberingState:
    global_sequence: int = 0
    chapter_sequences: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class NumberCellFormatResult:
    normalized: bool = False
    skipped: bool = False


@dataclass
class EquationTableStats:
    normalized_number_count: int = 0
    skipped_number_count: int = 0


@dataclass(frozen=True)
class NumberParagraphMatch:
    paragraph_index: int
    open_wrapper: str
    close_wrapper: str


class EquationTableFormatModule(BaseModule):
    """Format equation tables and consume template-owned formula config."""

    meta = ModuleMeta(
        name="equation_table_format",
        description="公式表格格式",
        category="special",
        requires_config=("formula_table", "formula_style", "equation_numbering"),
        soft_after=("table_format",),
        soft_consumes=("heading_map", "doc_tree"),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        plan = _resolve_equation_table_plan(config)
        heading_map = getattr(context, "heading_map", None) or {}
        doc_tree = getattr(context, "doc_tree", None)
        chapter_ranges = build_heading_chapter_ranges(
            heading_map,
            len(doc.paragraphs),
            doc_tree=doc_tree,
        )
        table_positions = top_level_table_anchor_positions(doc)
        numbering_state = EquationNumberingState()

        count = 0
        normalized_number_count = 0
        skipped_number_count = 0

        for table_index, table in enumerate(doc.tables):
            if not _is_equation_table(table):
                continue

            table_para_index = table_positions[table_index] if table_index < len(table_positions) else -1
            if not document_scope_allows_paragraph(context, table_para_index):
                continue
            stats = _format_equation_table(
                table,
                plan,
                table_para_index=table_para_index,
                chapter_ranges=chapter_ranges,
                numbering_state=numbering_state,
            )
            normalized_number_count += stats.normalized_number_count
            skipped_number_count += stats.skipped_number_count
            count += 1

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 个公式表格",
                section="global",
                change_type="format",
                before="(mixed)",
                after=(
                    f"table={plan.table_alignment}, "
                    f"formula={plan.formula_alignment}, "
                    f"number={plan.number_alignment}, "
                    f"numbering={plan.numbering_format}"
                ),
            )
        if normalized_number_count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{normalized_number_count} 个公式编号",
                section="global",
                change_type="format",
                before="existing numbering text",
                after=f"normalized to {plan.numbering_format}",
            )
        if skipped_number_count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{skipped_number_count} 个公式编号",
                section="global",
                change_type="skip",
                before="chapter-aware numbering normalization",
                after="skipped due to missing chapter context",
            )


def _resolve_equation_table_plan(config: ResolvedConfig) -> EquationTablePlan:
    formula_cfg = config.formula_table
    style_cfg = config.formula_style
    numbering_cfg = config.equation_numbering

    block_alignment = _normalize_alignment_keyword(formula_cfg.block_alignment, default="center")
    table_alignment = _resolve_block_alignment(
        formula_cfg.table_alignment,
        block_alignment,
        default="center",
    )
    formula_alignment = _resolve_block_alignment(
        formula_cfg.formula_cell_alignment,
        block_alignment,
        default="center",
    )
    number_alignment = _normalize_alignment_keyword(formula_cfg.number_alignment, default="right")

    formula_font_name = _clean_font_name(formula_cfg.formula_font_name)
    formula_font_size_pt = _clean_optional_positive_float(formula_cfg.formula_font_size_pt)
    formula_line_spacing = _clean_positive_float(formula_cfg.formula_line_spacing, default=1.0)
    formula_space_before_pt = _clean_nonnegative_float(
        formula_cfg.formula_space_before_pt,
        default=0.0,
    )
    formula_space_before_unit = normalize_spacing_unit(
        getattr(formula_cfg, "formula_space_before_unit", "pt")
    )
    formula_space_after_pt = _clean_nonnegative_float(
        formula_cfg.formula_space_after_pt,
        default=0.0,
    )
    formula_space_after_unit = normalize_spacing_unit(
        getattr(formula_cfg, "formula_space_after_unit", "pt")
    )

    number_font_name = (
        formula_font_name
        if bool(style_cfg.unify_font)
        else _clean_font_name(formula_cfg.number_font_name)
    )
    number_font_size_pt = (
        formula_font_size_pt
        if bool(style_cfg.unify_size)
        else _clean_optional_positive_float(formula_cfg.number_font_size_pt)
    )

    numbering_format = str(getattr(numbering_cfg, "numbering_format", "") or "chapter.seq")
    include_chapter_number, numbering_separator = parse_chapter_numbering_format(numbering_format)

    return EquationTablePlan(
        table_alignment=table_alignment,
        formula_alignment=formula_alignment,
        number_alignment=number_alignment,
        formula_font_name=formula_font_name,
        formula_font_size_pt=formula_font_size_pt,
        formula_line_spacing=formula_line_spacing,
        formula_space_before_pt=formula_space_before_pt,
        formula_space_before_unit=formula_space_before_unit,
        formula_space_after_pt=formula_space_after_pt,
        formula_space_after_unit=formula_space_after_unit,
        number_font_name=number_font_name,
        number_font_size_pt=number_font_size_pt,
        unify_spacing=bool(style_cfg.unify_spacing),
        include_chapter_number=include_chapter_number,
        numbering_separator=numbering_separator,
        numbering_format=numbering_format,
    )


def _format_equation_table(
    table: Table,
    plan: EquationTablePlan,
    *,
    table_para_index: int,
    chapter_ranges: list[tuple[int, int, int]],
    numbering_state: EquationNumberingState,
) -> EquationTableStats:
    _clear_table_borders(table)
    _set_table_alignment(table._element, plan.table_alignment)

    chapter_num = resolve_chapter_number(table_para_index, chapter_ranges)
    stats = EquationTableStats()

    for row in table.rows:
        cells = row.cells
        if len(cells) >= 2:
            for cell in cells[:-1]:
                _format_formula_cell(cell, plan)
            number_result = _format_number_cell(
                cells[-1],
                plan,
                chapter_num=chapter_num,
                numbering_state=numbering_state,
            )
            stats.normalized_number_count += int(number_result.normalized)
            stats.skipped_number_count += int(number_result.skipped)
            continue

        for cell in cells:
            _format_formula_cell(cell, plan)

    return stats


def _clear_table_borders(table: Table) -> None:
    tbl_el = table._element
    tbl_pr = find_or_create(tbl_el, "w:tblPr")
    tbl_borders = find_or_create(tbl_pr, "w:tblBorders")

    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = find_or_create(tbl_borders, f"w:{side}")
        border.set(qn("w:val"), "none")
        border.set(qn("w:sz"), "0")


def _set_table_alignment(tbl_el: _Element, alignment: str) -> None:
    tbl_pr = find_or_create(tbl_el, "w:tblPr")
    jc = find_or_create(tbl_pr, "w:jc")
    jc.set(qn("w:val"), alignment)


def _format_formula_cell(cell: _Cell, plan: EquationTablePlan) -> None:
    for para in cell.paragraphs:
        _apply_paragraph_alignment(para, plan.formula_alignment)
        _apply_paragraph_spacing(
            para,
            line_spacing=plan.formula_line_spacing,
            space_before_pt=plan.formula_space_before_pt,
            space_before_unit=plan.formula_space_before_unit,
            space_after_pt=plan.formula_space_after_pt,
            space_after_unit=plan.formula_space_after_unit,
        )
        _apply_word_run_typography(
            para.runs,
            font_name=plan.formula_font_name,
            size_pt=plan.formula_font_size_pt,
        )
        _apply_math_run_typography(
            para._element,
            font_name=plan.formula_font_name,
            size_pt=plan.formula_font_size_pt,
        )


def _format_number_cell(
    cell: _Cell,
    plan: EquationTablePlan,
    *,
    chapter_num: int,
    numbering_state: EquationNumberingState,
) -> NumberCellFormatResult:
    match = _find_number_paragraph(cell)
    if match is not None:
        if plan.include_chapter_number and chapter_num <= 0:
            result = NumberCellFormatResult(skipped=True)
        else:
            normalized_text = _next_equation_number_text(
                plan,
                chapter_num=chapter_num,
                numbering_state=numbering_state,
                match=match,
            )
            _replace_paragraph_text(cell.paragraphs[match.paragraph_index], normalized_text)
            result = NumberCellFormatResult(normalized=True)
    else:
        result = NumberCellFormatResult()

    for para in cell.paragraphs:
        _apply_paragraph_alignment(para, plan.number_alignment)
        if plan.unify_spacing:
            _apply_paragraph_spacing(
                para,
                line_spacing=plan.formula_line_spacing,
                space_before_pt=plan.formula_space_before_pt,
                space_before_unit=plan.formula_space_before_unit,
                space_after_pt=plan.formula_space_after_pt,
                space_after_unit=plan.formula_space_after_unit,
            )
        _apply_word_run_typography(
            para.runs,
            font_name=plan.number_font_name,
            size_pt=plan.number_font_size_pt,
        )
    return result


def _find_number_paragraph(cell: _Cell) -> NumberParagraphMatch | None:
    for paragraph_index, para in enumerate(cell.paragraphs):
        match = _EQUATION_NUMBER_RE.match((para.text or "").strip())
        if match is None:
            continue
        open_wrapper = match.group("open") or ""
        close_wrapper = match.group("close") or ""
        if open_wrapper and _WRAPPER_PAIRS.get(open_wrapper) != close_wrapper:
            open_wrapper = ""
            close_wrapper = ""
        return NumberParagraphMatch(
            paragraph_index=paragraph_index,
            open_wrapper=open_wrapper,
            close_wrapper=close_wrapper,
        )
    return None


def _next_equation_number_text(
    plan: EquationTablePlan,
    *,
    chapter_num: int,
    numbering_state: EquationNumberingState,
    match: NumberParagraphMatch,
) -> str:
    if plan.include_chapter_number and chapter_num > 0:
        next_seq = numbering_state.chapter_sequences.get(chapter_num, 0) + 1
        numbering_state.chapter_sequences[chapter_num] = next_seq
        core = f"{chapter_num}{plan.numbering_separator}{next_seq}" if plan.numbering_separator else f"{chapter_num}{next_seq}"
    else:
        numbering_state.global_sequence += 1
        core = str(numbering_state.global_sequence)

    return f"{match.open_wrapper}{core}{match.close_wrapper}"


def _replace_paragraph_text(para: Paragraph, new_text: str) -> None:
    for child in list(para._element):
        if child.tag != qn("w:pPr"):
            para._element.remove(child)
    para.add_run(new_text)


def _apply_paragraph_alignment(para: Paragraph, alignment: str) -> None:
    para.paragraph_format.alignment = _PARAGRAPH_ALIGNMENTS.get(
        alignment,
        WD_ALIGN_PARAGRAPH.CENTER,
    )


def _apply_paragraph_spacing(
    para: Paragraph,
    *,
    line_spacing: float,
    space_before_pt: float,
    space_before_unit: str = "pt",
    space_after_pt: float,
    space_after_unit: str = "pt",
) -> None:
    pf = para.paragraph_format
    apply_line_spacing(pf, "multiple", line_spacing)
    before_abs_pt = spacing_value_to_pt(space_before_pt, space_before_unit)
    after_abs_pt = spacing_value_to_pt(space_after_pt, space_after_unit)
    if before_abs_pt is not None:
        from docx.shared import Pt
        pf.space_before = Pt(before_abs_pt)
    if after_abs_pt is not None:
        from docx.shared import Pt
        pf.space_after = Pt(after_abs_pt)
    sync_spacing_ooxml(
        para._element,
        space_before_pt=space_before_pt,
        space_before_unit=space_before_unit,
        space_after_pt=space_after_pt,
        space_after_unit=space_after_unit,
        line_spacing_type="multiple",
        line_spacing_value=line_spacing,
    )


def _apply_word_run_typography(
    runs: list[Run],
    *,
    font_name: str | None,
    size_pt: float | None,
) -> None:
    if not runs or (font_name is None and size_pt is None):
        return

    resolved_font = resolve_font(font_name, lang="en") if font_name else None
    half_points = _size_to_half_points(size_pt)

    for run in runs:
        r_pr = _find_or_insert_word_run_pr(run._element)
        if resolved_font:
            r_fonts = find_or_create(r_pr, "w:rFonts")
            r_fonts.set(qn("w:ascii"), resolved_font)
            r_fonts.set(qn("w:hAnsi"), resolved_font)
            r_fonts.set(qn("w:cs"), resolved_font)
        if half_points is not None:
            find_or_create(r_pr, "w:sz").set(qn("w:val"), half_points)
            find_or_create(r_pr, "w:szCs").set(qn("w:val"), half_points)


def _apply_math_run_typography(
    container: _Element,
    *,
    font_name: str | None,
    size_pt: float | None,
) -> None:
    if font_name is None and size_pt is None:
        return

    resolved_font = resolve_font(font_name, lang="en") if font_name else None
    half_points = _size_to_half_points(size_pt)

    for math_run in container.findall(f".//{qn('m:r')}"):
        r_pr = _find_or_insert_math_word_run_pr(math_run)
        if resolved_font:
            r_fonts = find_or_create(r_pr, "w:rFonts")
            r_fonts.set(qn("w:ascii"), resolved_font)
            r_fonts.set(qn("w:hAnsi"), resolved_font)
            r_fonts.set(qn("w:cs"), resolved_font)
        if half_points is not None:
            find_or_create(r_pr, "w:sz").set(qn("w:val"), half_points)
            find_or_create(r_pr, "w:szCs").set(qn("w:val"), half_points)


def _find_or_insert_word_run_pr(run_el: _Element) -> _Element:
    r_pr = run_el.find(qn("w:rPr"))
    if r_pr is not None:
        return r_pr
    r_pr = OxmlElement("w:rPr")
    run_el.insert(0, r_pr)
    return r_pr


def _find_or_insert_math_word_run_pr(math_run_el: _Element) -> _Element:
    r_pr = math_run_el.find(qn("w:rPr"))
    if r_pr is not None:
        return r_pr

    r_pr = OxmlElement("w:rPr")
    children = list(math_run_el)
    insert_at = 0
    for index, child in enumerate(children):
        if child.tag == qn("m:rPr"):
            insert_at = index + 1
            break
    math_run_el.insert(insert_at, r_pr)
    return r_pr


def _resolve_block_alignment(primary: str | None, block_alignment: str, *, default: str) -> str:
    primary_alignment = _normalize_alignment_keyword(primary, default=default)
    if primary_alignment == default and block_alignment != default:
        return block_alignment
    return primary_alignment


def _normalize_alignment_keyword(value: str | None, *, default: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _TABLE_ALIGNMENTS:
        return normalized
    return default


def _clean_font_name(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _clean_optional_positive_float(value) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _clean_positive_float(value, *, default: float) -> float:
    parsed = _clean_optional_positive_float(value)
    return parsed if parsed is not None else default


def _clean_nonnegative_float(value, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _size_to_half_points(size_pt: float | None) -> str | None:
    if size_pt is None:
        return None
    return str(int(round(size_pt * 2)))
