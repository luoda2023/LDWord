"""Shared typography semantics for template style editing and execution."""

from __future__ import annotations

import re
from typing import Any

WORD_NAMED_FONT_SIZES: tuple[tuple[str, float], ...] = (
    ("初号", 42.0),
    ("小初", 36.0),
    ("一号", 26.0),
    ("小一", 24.0),
    ("二号", 22.0),
    ("小二", 18.0),
    ("三号", 16.0),
    ("小三", 15.0),
    ("四号", 14.0),
    ("小四", 12.0),
    ("五号", 10.5),
    ("小五", 9.0),
    ("六号", 7.5),
    ("小六", 6.5),
    ("七号", 5.5),
    ("八号", 5.0),
)

NUMERIC_FONT_SIZE_OPTIONS: tuple[float, ...] = (
    5.0,
    5.5,
    6.5,
    7.5,
    8.0,
    9.0,
    10.0,
    10.5,
    11.0,
    12.0,
    14.0,
    16.0,
    18.0,
    20.0,
    22.0,
    26.0,
    28.0,
    36.0,
    48.0,
    56.0,
    72.0,
)

WORD_NAMED_FONT_SIZE_TO_PT = {name: pt for name, pt in WORD_NAMED_FONT_SIZES}
PT_TO_NAMED_SIZE = {pt: name for name, pt in WORD_NAMED_FONT_SIZES}

FULLWIDTH_ASCII_TRANSLATION = str.maketrans(
    {
        "０": "0",
        "１": "1",
        "２": "2",
        "３": "3",
        "４": "4",
        "５": "5",
        "６": "6",
        "７": "7",
        "８": "8",
        "９": "9",
        "．": ".",
        "。": ".",
        "－": "-",
        "＋": "+",
        "（": "(",
        "）": ")",
    }
)

LINE_SPACING_OPTIONS: tuple[tuple[str, str], ...] = (
    ("exact", "固定值"),
    ("single", "单倍"),
    ("one_half", "1.5 倍"),
    ("double", "双倍"),
    ("multiple", "多倍"),
)

LINE_SPACING_VALUE_TO_LABEL = {
    value: label for value, label in LINE_SPACING_OPTIONS
}

LINE_SPACING_ALIASES = {
    "exact": "exact",
    "fixed": "exact",
    "固定值": "exact",
    "single": "single",
    "单倍": "single",
    "one_half": "one_half",
    "1.5倍": "one_half",
    "1.5 倍": "one_half",
    "double": "double",
    "双倍": "double",
    "multiple": "multiple",
    "多倍": "multiple",
}

FIXED_LINE_SPACING_VALUES = {
    "single": 1.0,
    "one_half": 1.5,
    "double": 2.0,
}

DEFAULT_LINE_SPACING_VALUES = {
    "exact": 20.0,
    "single": 1.0,
    "one_half": 1.5,
    "double": 2.0,
    "multiple": 1.0,
}

SPECIAL_INDENT_NONE = "none"
SPECIAL_INDENT_FIRST_LINE = "first_line"
SPECIAL_INDENT_HANGING = "hanging"
CM_TO_PT = 72.0 / 2.54


def normalize_font_size_token(text: str) -> str:
    raw = str(text or "").strip().translate(FULLWIDTH_ASCII_TRANSLATION)
    return "".join(raw.split())


def format_font_size_pt(value: float) -> str:
    pt = float(value)
    if pt.is_integer():
        return str(int(pt))
    return f"{pt:.2f}".rstrip("0").rstrip(".")


def display_font_size_with_name(pt_value: float) -> str:
    name = PT_TO_NAMED_SIZE.get(round(float(pt_value), 2))
    if name:
        return name
    return format_font_size_pt(pt_value)


def font_size_display_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        pt = float(value)
    except (TypeError, ValueError):
        return normalize_font_size_display_text(value)
    return format_font_size_pt(pt)


def normalize_font_size_display_text(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return re.sub(
        r"(?i)(?P<number>[+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*(?:pt|pts)\b",
        lambda match: f"{match.group('number')}磅",
        raw,
    )


def parse_font_size_input(text: str) -> float:
    token = normalize_font_size_token(text)
    if not token:
        raise ValueError("empty font size")

    if token in WORD_NAMED_FONT_SIZE_TO_PT:
        return WORD_NAMED_FONT_SIZE_TO_PT[token]

    name_prefix = token.split("(", 1)[0]
    if name_prefix in WORD_NAMED_FONT_SIZE_TO_PT:
        return WORD_NAMED_FONT_SIZE_TO_PT[name_prefix]

    numeric_token = token.lower()
    for suffix in ("pt", "pts", "磅"):
        if numeric_token.endswith(suffix):
            numeric_token = numeric_token[: -len(suffix)]
            break

    return float(numeric_token)


def normalize_line_spacing_type(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "exact"
    return LINE_SPACING_ALIASES.get(raw.lower(), LINE_SPACING_ALIASES.get(raw, "exact"))


def line_spacing_display_label(value: str) -> str:
    return LINE_SPACING_VALUE_TO_LABEL.get(normalize_line_spacing_type(value), "固定值")


def line_spacing_unit_label(value: str) -> str:
    kind = normalize_line_spacing_type(value)
    return "磅" if kind == "exact" else "倍"


def line_spacing_is_editable(value: str) -> bool:
    kind = normalize_line_spacing_type(value)
    return kind in {"exact", "multiple"}


def resolve_line_spacing_value(kind: str, raw_value: Any) -> float:
    normalized_kind = normalize_line_spacing_type(kind)
    if normalized_kind in FIXED_LINE_SPACING_VALUES:
        return FIXED_LINE_SPACING_VALUES[normalized_kind]

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        value = DEFAULT_LINE_SPACING_VALUES[normalized_kind]

    if value <= 0:
        value = DEFAULT_LINE_SPACING_VALUES[normalized_kind]
    return value


def normalize_indent_unit(unit: Any) -> str:
    raw = str(unit or "").strip().lower()
    if raw in {"pt", "point", "points", "磅"}:
        return "pt"
    if raw in {"cm", "centimeter", "centimeters"}:
        return "cm"
    return "chars"


def normalize_special_indent_mode(mode: Any) -> str:
    raw = str(mode or "").strip().lower()
    if raw in {"first", "firstline", "first_line", "first-line", "首行"}:
        return SPECIAL_INDENT_FIRST_LINE
    if raw in {"hanging", "hang", "悬挂"}:
        return SPECIAL_INDENT_HANGING
    return SPECIAL_INDENT_NONE


def normalize_indent_value(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return max(0.0, numeric)


def normalize_indent_size_pt(size_pt: Any) -> float:
    try:
        if isinstance(size_pt, str):
            numeric = parse_font_size_input(size_pt)
        else:
            numeric = float(size_pt)
    except (TypeError, ValueError):
        numeric = 12.0
    return numeric if numeric > 0 else 12.0


def config_indent_value_to_pt(value: Any, size_pt: Any, unit: str = "chars") -> float:
    normalized_value = normalize_indent_value(value)
    normalized_unit = normalize_indent_unit(unit)
    if normalized_unit == "pt":
        return normalized_value
    if normalized_unit == "cm":
        return normalized_value * CM_TO_PT
    return normalized_value * normalize_indent_size_pt(size_pt)


def resolve_pt_indent_value(value_pt: Any, unit: str, size_pt: Any) -> float:
    try:
        pt_value = float(value_pt)
    except (TypeError, ValueError):
        pt_value = 0.0
    normalized_unit = normalize_indent_unit(unit)
    if normalized_unit == "cm":
        return pt_value / CM_TO_PT if CM_TO_PT > 0 else 0.0
    if normalized_unit == "pt":
        return pt_value
    normalized_size = normalize_indent_size_pt(size_pt)
    return pt_value / normalized_size if normalized_size > 0 else pt_value


def resolve_style_special_indent(style_config: Any) -> dict[str, float | str]:
    raw_mode = normalize_special_indent_mode(getattr(style_config, "special_indent_mode", "none"))
    raw_value = normalize_indent_value(getattr(style_config, "special_indent_value", 0.0))
    raw_unit = normalize_indent_unit(getattr(style_config, "special_indent_unit", "chars"))

    legacy_first_value = normalize_indent_value(getattr(style_config, "first_line_indent_chars", 0.0))
    legacy_first_unit = normalize_indent_unit(getattr(style_config, "first_line_indent_unit", "chars"))
    legacy_hanging_value = normalize_indent_value(getattr(style_config, "hanging_indent_chars", 0.0))
    legacy_hanging_unit = normalize_indent_unit(getattr(style_config, "hanging_indent_unit", "chars"))

    if legacy_hanging_value > 0:
        return {
            "mode": SPECIAL_INDENT_HANGING,
            "value": legacy_hanging_value,
            "unit": legacy_hanging_unit,
        }
    if legacy_first_value > 0:
        return {
            "mode": SPECIAL_INDENT_FIRST_LINE,
            "value": legacy_first_value,
            "unit": legacy_first_unit,
        }
    if raw_mode != SPECIAL_INDENT_NONE and raw_value > 0:
        return {"mode": raw_mode, "value": raw_value, "unit": raw_unit}
    return {"mode": SPECIAL_INDENT_NONE, "value": 0.0, "unit": raw_unit}


def apply_style_special_indent(style_config: Any, mode: str, value: Any, unit: str) -> None:
    normalized_mode = normalize_special_indent_mode(mode)
    normalized_value = normalize_indent_value(value)
    normalized_unit = normalize_indent_unit(unit)

    if hasattr(style_config, "special_indent_mode"):
        setattr(style_config, "special_indent_mode", normalized_mode)
    if hasattr(style_config, "special_indent_value"):
        setattr(style_config, "special_indent_value", normalized_value)
    if hasattr(style_config, "special_indent_unit"):
        setattr(style_config, "special_indent_unit", normalized_unit)

    if normalized_mode == SPECIAL_INDENT_FIRST_LINE and normalized_value > 0:
        setattr(style_config, "first_line_indent_chars", normalized_value)
        setattr(style_config, "first_line_indent_unit", normalized_unit)
        setattr(style_config, "hanging_indent_chars", 0.0)
        setattr(style_config, "hanging_indent_unit", "chars")
        return

    if normalized_mode == SPECIAL_INDENT_HANGING and normalized_value > 0:
        setattr(style_config, "first_line_indent_chars", 0.0)
        setattr(style_config, "first_line_indent_unit", "chars")
        setattr(style_config, "hanging_indent_chars", normalized_value)
        setattr(style_config, "hanging_indent_unit", normalized_unit)
        return

    setattr(style_config, "first_line_indent_chars", 0.0)
    setattr(style_config, "first_line_indent_unit", "chars")
    setattr(style_config, "hanging_indent_chars", 0.0)
    setattr(style_config, "hanging_indent_unit", "chars")
