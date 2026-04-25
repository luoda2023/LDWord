"""Line-spacing helpers that keep paragraph_format and OOXML in sync."""

from __future__ import annotations

from lxml import etree
from docx.enum.text import WD_LINE_SPACING
from docx.shared import Pt

from src.config.style_semantics import (
    normalize_line_spacing_type,
    normalize_spacing_unit,
    resolve_line_spacing_value,
    resolve_style_paragraph_spacing,
    spacing_value_to_line_hundredths,
    spacing_value_to_twips,
)
from src.shared.engine.ooxml_ops import qn


def _ensure_ppr(container_element):
    ppr = container_element.find(qn("w:pPr"))
    if ppr is None:
        ppr = etree.SubElement(container_element, qn("w:pPr"))
    return ppr


def _ensure_spacing(container_element):
    ppr = _ensure_ppr(container_element)
    spacing = ppr.find(qn("w:spacing"))
    if spacing is None:
        spacing = etree.SubElement(ppr, qn("w:spacing"))
    return ppr, spacing


def normalize_line_spacing(line_spacing_type: str, line_spacing_value) -> tuple[str, float]:
    """Normalize config spacing to exact/multiple semantics."""
    kind = normalize_line_spacing_type(line_spacing_type)
    value = resolve_line_spacing_value(kind, line_spacing_value)
    if kind == "exact":
        return ("exact", value)
    return ("multiple", value)


def apply_line_spacing(paragraph_format, line_spacing_type: str, line_spacing_value) -> None:
    kind, value = normalize_line_spacing(line_spacing_type, line_spacing_value)
    if kind == "exact":
        paragraph_format.line_spacing = Pt(value)
        paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        return
    paragraph_format.line_spacing = value
    paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE


def _clear_spacing_attrs(spacing, *attr_names: str) -> None:
    for attr_name in attr_names:
        spacing.attrib.pop(qn(f"w:{attr_name}"), None)


def _apply_paragraph_spacing_slot(paragraph_format, spacing, slot: str, value, unit: str) -> None:
    normalized_unit = normalize_spacing_unit(unit)

    if paragraph_format is not None:
        if slot == "before":
            paragraph_format.space_before = Pt(0) if normalized_unit == "auto" else None
        else:
            paragraph_format.space_after = Pt(0) if normalized_unit == "auto" else None

    _clear_spacing_attrs(
        spacing,
        "before" if slot == "before" else "after",
        "beforeLines" if slot == "before" else "afterLines",
        "beforeAutospacing" if slot == "before" else "afterAutospacing",
    )

    twips = spacing_value_to_twips(value, normalized_unit)
    if twips is not None:
        spacing.set(qn(f"w:{slot}"), str(twips))
        if paragraph_format is not None:
            if slot == "before":
                paragraph_format.space_before = Pt(twips / 20)
            else:
                paragraph_format.space_after = Pt(twips / 20)
        return

    line_hundredths = spacing_value_to_line_hundredths(value, normalized_unit)
    if line_hundredths is not None:
        spacing.set(qn(f"w:{slot}Lines"), str(line_hundredths))
        return

    if normalized_unit == "auto":
        spacing.set(qn(f"w:{slot}Autospacing"), "1")


def apply_paragraph_spacing(paragraph_format, style_config, container_element) -> None:
    ppr, spacing = _ensure_spacing(container_element)
    before = resolve_style_paragraph_spacing(style_config, "before")
    after = resolve_style_paragraph_spacing(style_config, "after")
    _apply_paragraph_spacing_slot(
        paragraph_format,
        spacing,
        "before",
        before["value"],
        str(before["unit"]),
    )
    _apply_paragraph_spacing_slot(
        paragraph_format,
        spacing,
        "after",
        after["value"],
        str(after["unit"]),
    )

    contextual_spacing = ppr.find(qn("w:contextualSpacing"))
    if contextual_spacing is not None:
        ppr.remove(contextual_spacing)


def sync_spacing_ooxml(
    container_element,
    *,
    space_before_pt=0.0,
    space_before_unit: str = "pt",
    space_after_pt=0.0,
    space_after_unit: str = "pt",
    line_spacing_type: str = "exact",
    line_spacing_value=20.0,
) -> None:
    """Synchronize before/after spacing and line rule into OOXML."""
    ppr, spacing = _ensure_spacing(container_element)
    _apply_paragraph_spacing_slot(None, spacing, "before", space_before_pt, space_before_unit)
    _apply_paragraph_spacing_slot(None, spacing, "after", space_after_pt, space_after_unit)

    kind, value = normalize_line_spacing(line_spacing_type, line_spacing_value)
    if kind == "exact":
        spacing.set(qn("w:line"), str(int(round(value * 20))))
        spacing.set(qn("w:lineRule"), "exact")
    else:
        spacing.set(qn("w:line"), str(int(round(value * 240))))
        spacing.set(qn("w:lineRule"), "auto")

    contextual_spacing = ppr.find(qn("w:contextualSpacing"))
    if contextual_spacing is not None:
        ppr.remove(contextual_spacing)
