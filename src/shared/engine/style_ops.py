"""Helpers for updating Word style definitions."""

from __future__ import annotations

from docx.shared import Pt

from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.ooxml_ops import find_or_create, qn


def apply_style_text_format(
    style,
    *,
    font_cn: str | None = None,
    font_en: str | None = None,
    size_pt: float | None = None,
) -> bool:
    """Apply text-level formatting to a Word style definition."""
    if not any((font_cn, font_en, size_pt is not None)):
        return False

    changed = False
    r_pr = find_or_create(style._element, "w:rPr")
    r_fonts = find_or_create(r_pr, "w:rFonts")

    if font_en:
        resolved_en = resolve_font(font_en, lang="en")
        current_name = style.font.name
        if current_name != resolved_en:
            changed = True
        style.font.name = resolved_en
        changed |= _set_attr(r_fonts, "w:ascii", resolved_en)
        changed |= _set_attr(r_fonts, "w:hAnsi", resolved_en)
        changed |= _set_attr(r_fonts, "w:cs", resolved_en)

    if font_cn:
        resolved_cn = resolve_font(font_cn, lang="cn")
        changed |= _set_attr(r_fonts, "w:eastAsia", resolved_cn)

    if size_pt is not None:
        current_pt = style.font.size.pt if style.font.size else None
        if current_pt is None or abs(current_pt - size_pt) > 0.01:
            changed = True
        style.font.size = Pt(size_pt)
        half_points = str(int(round(size_pt * 2)))
        changed |= _set_attr(find_or_create(r_pr, "w:sz"), "w:val", half_points)
        changed |= _set_attr(find_or_create(r_pr, "w:szCs"), "w:val", half_points)

    return changed


def _set_attr(element, attr: str, value: str) -> bool:
    previous = element.get(qn(attr))
    if previous == value:
        return False
    element.set(qn(attr), value)
    return True
