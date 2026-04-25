"""Indent helpers that keep paragraph_format and OOXML in sync."""

from __future__ import annotations

from lxml import etree
from docx.shared import Pt

from src.config.style_semantics import (
    config_indent_value_to_pt,
    normalize_indent_size_pt,
    normalize_indent_unit,
    normalize_indent_value,
    resolve_style_special_indent,
)
from src.shared.engine.ooxml_ops import qn


def _ensure_ppr(container_element):
    ppr = container_element.find(qn("w:pPr"))
    if ppr is None:
        ppr = etree.SubElement(container_element, qn("w:pPr"))
    return ppr


def _ensure_ind(container_element):
    ppr = _ensure_ppr(container_element)
    ind = ppr.find(qn("w:ind"))
    if ind is None:
        ind = etree.SubElement(ppr, qn("w:ind"))
    return ind


def resolve_style_config_indents(style_config, *, size_pt=None) -> dict[str, float | str]:
    """Resolve unit-aware indent config into effective pt/XML write values."""
    effective_size_pt = normalize_indent_size_pt(
        size_pt if size_pt is not None else getattr(style_config, "size_pt", 12.0)
    )

    left_value = normalize_indent_value(getattr(style_config, "left_indent_chars", 0.0))
    left_unit = normalize_indent_unit(getattr(style_config, "left_indent_unit", "chars"))
    left_pt = config_indent_value_to_pt(left_value, effective_size_pt, left_unit)

    right_value = normalize_indent_value(getattr(style_config, "right_indent_chars", 0.0))
    right_unit = normalize_indent_unit(getattr(style_config, "right_indent_unit", "chars"))
    right_pt = config_indent_value_to_pt(right_value, effective_size_pt, right_unit)

    special = resolve_style_special_indent(style_config)
    special_mode = str(special["mode"])
    special_value = normalize_indent_value(special["value"])
    special_unit = normalize_indent_unit(str(special["unit"]))
    special_pt = config_indent_value_to_pt(special_value, effective_size_pt, special_unit)

    first_value = special_value if special_mode == "first_line" and special_value > 0 else 0.0
    first_unit = special_unit if special_mode == "first_line" and special_value > 0 else "chars"
    first_pt = config_indent_value_to_pt(first_value, effective_size_pt, first_unit)

    hanging_value = special_value if special_mode == "hanging" and special_value > 0 else 0.0
    hanging_unit = special_unit if special_mode == "hanging" and special_value > 0 else "chars"
    hanging_pt = config_indent_value_to_pt(hanging_value, effective_size_pt, hanging_unit)

    effective_left_value = left_value
    effective_left_unit = left_unit
    effective_left_pt = left_pt

    # Word's hanging indent is modeled as left indent + negative first-line indent.
    # Promote left indent when needed so the first line stays at the page margin.
    if hanging_pt > 0 and effective_left_pt < hanging_pt:
        effective_left_value = hanging_value
        effective_left_unit = hanging_unit
        effective_left_pt = hanging_pt

    return {
        "size_pt": effective_size_pt,
        "left_value": left_value,
        "left_unit": left_unit,
        "left_pt": left_pt,
        "right_value": right_value,
        "right_unit": right_unit,
        "right_pt": right_pt,
        "special_mode": special_mode,
        "special_value": special_value,
        "special_unit": special_unit,
        "special_pt": special_pt,
        "first_value": first_value,
        "first_unit": first_unit,
        "first_pt": first_pt,
        "hanging_value": hanging_value,
        "hanging_unit": hanging_unit,
        "hanging_pt": hanging_pt,
        "effective_left_value": effective_left_value,
        "effective_left_unit": effective_left_unit,
        "effective_left_pt": effective_left_pt,
    }


def _sync_single_indent(ind, *, twips_attr: str, chars_attr: str, value, unit: str, size_pt) -> None:
    normalized_value = normalize_indent_value(value)
    normalized_unit = normalize_indent_unit(unit)
    twips_key = qn(f"w:{twips_attr}")
    chars_key = qn(f"w:{chars_attr}")

    if normalized_value <= 0:
        ind.set(twips_key, "0")
        ind.set(chars_key, "0")
        return

    if normalized_unit == "chars":
        ind.set(chars_key, str(int(round(normalized_value * 100))))
        ind.attrib.pop(twips_key, None)
        return

    pt_value = config_indent_value_to_pt(normalized_value, size_pt, normalized_unit)
    ind.set(twips_key, str(int(round(pt_value * 20))))
    ind.attrib.pop(chars_key, None)


def sync_indent_ooxml(
    container_element,
    *,
    left_value=0.0,
    left_unit: str = "chars",
    first_line_value=0.0,
    first_line_unit: str = "chars",
    hanging_value=0.0,
    hanging_unit: str = "chars",
    right_value=0.0,
    right_unit: str = "chars",
    size_pt=12.0,
    force_zero: bool = False,
) -> None:
    """Synchronize indentation OOXML with explicit unit semantics."""
    ind = _ensure_ind(container_element)

    if force_zero:
        left_value = first_line_value = hanging_value = right_value = 0.0
        left_unit = first_line_unit = hanging_unit = right_unit = "pt"

    normalized_size_pt = normalize_indent_size_pt(size_pt)
    normalized_left_value = normalize_indent_value(left_value)
    normalized_left_unit = normalize_indent_unit(left_unit)
    normalized_first_value = normalize_indent_value(first_line_value)
    normalized_first_unit = normalize_indent_unit(first_line_unit)
    normalized_hanging_value = normalize_indent_value(hanging_value)
    normalized_hanging_unit = normalize_indent_unit(hanging_unit)
    normalized_right_value = normalize_indent_value(right_value)
    normalized_right_unit = normalize_indent_unit(right_unit)

    effective_left_value = normalized_left_value
    effective_left_unit = normalized_left_unit
    if normalized_hanging_value > 0:
        left_pt = config_indent_value_to_pt(normalized_left_value, normalized_size_pt, normalized_left_unit)
        hanging_pt = config_indent_value_to_pt(
            normalized_hanging_value,
            normalized_size_pt,
            normalized_hanging_unit,
        )
        if left_pt < hanging_pt:
            effective_left_value = normalized_hanging_value
            effective_left_unit = normalized_hanging_unit

    _sync_single_indent(
        ind,
        twips_attr="left",
        chars_attr="leftChars",
        value=effective_left_value,
        unit=effective_left_unit,
        size_pt=normalized_size_pt,
    )

    if normalized_hanging_value > 0:
        _sync_single_indent(
            ind,
            twips_attr="hanging",
            chars_attr="hangingChars",
            value=normalized_hanging_value,
            unit=normalized_hanging_unit,
            size_pt=normalized_size_pt,
        )
        ind.attrib.pop(qn("w:firstLine"), None)
        ind.attrib.pop(qn("w:firstLineChars"), None)
    else:
        _sync_single_indent(
            ind,
            twips_attr="firstLine",
            chars_attr="firstLineChars",
            value=normalized_first_value,
            unit=normalized_first_unit,
            size_pt=normalized_size_pt,
        )
        ind.attrib.pop(qn("w:hanging"), None)
        ind.attrib.pop(qn("w:hangingChars"), None)

    _sync_single_indent(
        ind,
        twips_attr="right",
        chars_attr="rightChars",
        value=normalized_right_value,
        unit=normalized_right_unit,
        size_pt=normalized_size_pt,
    )


def apply_style_config_indents(
    paragraph_format,
    container_element,
    style_config,
    *,
    size_pt=None,
) -> tuple[float, float, float, float]:
    """Apply indents to python-docx and OOXML together."""
    resolved = resolve_style_config_indents(style_config, size_pt=size_pt)

    left_pt = float(resolved["effective_left_pt"])
    first_pt = float(resolved["first_pt"])
    hanging_pt = float(resolved["hanging_pt"])
    right_pt = float(resolved["right_pt"])

    paragraph_format.left_indent = Pt(left_pt if left_pt > 0 else 0)
    paragraph_format.right_indent = Pt(right_pt if right_pt > 0 else 0)
    if hanging_pt > 0:
        paragraph_format.first_line_indent = Pt(-hanging_pt)
    else:
        paragraph_format.first_line_indent = Pt(first_pt if first_pt > 0 else 0)

    sync_indent_ooxml(
        container_element,
        left_value=resolved["effective_left_value"],
        left_unit=str(resolved["effective_left_unit"]),
        first_line_value=resolved["first_value"],
        first_line_unit=str(resolved["first_unit"]),
        hanging_value=resolved["hanging_value"],
        hanging_unit=str(resolved["hanging_unit"]),
        right_value=resolved["right_value"],
        right_unit=str(resolved["right_unit"]),
        size_pt=resolved["size_pt"],
        force_zero=left_pt <= 0 and first_pt <= 0 and hanging_pt <= 0 and right_pt <= 0,
    )
    return left_pt, first_pt, hanging_pt, right_pt
