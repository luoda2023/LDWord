"""Shared formula-typography primitives without module orchestration dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement

from src.config.style_semantics import spacing_value_to_pt
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.line_spacing_ops import apply_line_spacing, sync_spacing_ooxml
from src.shared.engine.ooxml_ops import find_or_create, qn

if TYPE_CHECKING:
    from docx.text.paragraph import Paragraph
    from docx.text.run import Run
    from lxml.etree import _Element


_PARAGRAPH_ALIGNMENTS: dict[str, WD_ALIGN_PARAGRAPH] = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
}


def apply_paragraph_alignment(para: Paragraph, alignment: str) -> None:
    para.paragraph_format.alignment = _PARAGRAPH_ALIGNMENTS.get(
        alignment,
        WD_ALIGN_PARAGRAPH.CENTER,
    )


def apply_paragraph_spacing(
    para: Paragraph,
    *,
    line_spacing: float,
    space_before_pt: float,
    space_before_unit: str = "pt",
    space_after_pt: float,
    space_after_unit: str = "pt",
) -> None:
    paragraph_format = para.paragraph_format
    apply_line_spacing(paragraph_format, "multiple", line_spacing)
    before_abs_pt = spacing_value_to_pt(space_before_pt, space_before_unit)
    after_abs_pt = spacing_value_to_pt(space_after_pt, space_after_unit)
    if before_abs_pt is not None:
        from docx.shared import Pt

        paragraph_format.space_before = Pt(before_abs_pt)
    if after_abs_pt is not None:
        from docx.shared import Pt

        paragraph_format.space_after = Pt(after_abs_pt)
    sync_spacing_ooxml(
        para._element,
        space_before_pt=space_before_pt,
        space_before_unit=space_before_unit,
        space_after_pt=space_after_pt,
        space_after_unit=space_after_unit,
        line_spacing_type="multiple",
        line_spacing_value=line_spacing,
    )


def apply_word_run_typography(
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
        _apply_run_typography(
            _find_or_insert_word_run_pr(run._element), resolved_font, half_points
        )


def apply_math_run_typography(
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
        _apply_run_typography(
            _find_or_insert_math_word_run_pr(math_run), resolved_font, half_points
        )


def _apply_run_typography(
    run_properties: _Element,
    resolved_font: str | None,
    half_points: str | None,
) -> None:
    if resolved_font:
        fonts = find_or_create(run_properties, "w:rFonts")
        fonts.set(qn("w:ascii"), resolved_font)
        fonts.set(qn("w:hAnsi"), resolved_font)
        fonts.set(qn("w:cs"), resolved_font)
    if half_points is not None:
        find_or_create(run_properties, "w:sz").set(qn("w:val"), half_points)
        find_or_create(run_properties, "w:szCs").set(qn("w:val"), half_points)


def _find_or_insert_word_run_pr(run_element: _Element) -> _Element:
    run_properties = run_element.find(qn("w:rPr"))
    if run_properties is None:
        run_properties = OxmlElement("w:rPr")
        run_element.insert(0, run_properties)
    return run_properties


def _find_or_insert_math_word_run_pr(math_run: _Element) -> _Element:
    run_properties = math_run.find(qn("w:rPr"))
    if run_properties is not None:
        return run_properties
    run_properties = OxmlElement("w:rPr")
    insert_at = 0
    for index, child in enumerate(list(math_run)):
        if child.tag == qn("m:rPr"):
            insert_at = index + 1
            break
    math_run.insert(insert_at, run_properties)
    return run_properties


def _size_to_half_points(size_pt: float | None) -> str | None:
    if size_pt is None:
        return None
    return str(int(round(size_pt * 2)))


__all__ = [
    "apply_math_run_typography",
    "apply_paragraph_alignment",
    "apply_paragraph_spacing",
    "apply_word_run_typography",
]
