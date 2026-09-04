"""Shared semantics for table visual style presets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TableStyleOption:
    key: str
    label: str


@dataclass(frozen=True, slots=True)
class ColorTablePalette:
    key: str
    label: str
    accent: str
    accent_light: str
    accent_soft: str
    header_text: str = "FFFFFF"


@dataclass(frozen=True, slots=True)
class ColorTableVariant:
    key: str
    label: str
    header_fill: bool
    show_vertical: bool
    show_horizontal: bool
    zebra: bool = False
    header_rule_only: bool = False


TABLE_STYLE_OPTIONS: tuple[TableStyleOption, ...] = (
    TableStyleOption("three_line", "三线表"),
    TableStyleOption("full_grid", "全框线表"),
    TableStyleOption("color_table", "颜色表"),
    TableStyleOption("none", "无框线表"),
    TableStyleOption("keep", "保留原样"),
)


COLOR_TABLE_PALETTES: tuple[ColorTablePalette, ...] = (
    ColorTablePalette("black", "黑色", "000000", "BFBFBF", "F2F2F2"),
    ColorTablePalette("blue", "蓝色", "4472C4", "B4C6E7", "EAF1FB"),
    ColorTablePalette("orange", "橙色", "ED7D31", "F4B183", "FCE4D6"),
    ColorTablePalette("gray", "灰色", "A5A5A5", "D9D9D9", "F2F2F2", header_text="1F2933"),
    ColorTablePalette("yellow", "黄色", "FFC000", "FFD966", "FFF2CC", header_text="1F2933"),
    ColorTablePalette("cyan", "青色", "5B9BD5", "BDD7EE", "EAF4FC"),
    ColorTablePalette("green", "绿色", "70AD47", "C6E0B4", "E2F0D9"),
)


COLOR_TABLE_VARIANTS: tuple[ColorTableVariant, ...] = (
    ColorTableVariant("header_grid", "表头网格", True, True, True),
    ColorTableVariant("header_grid_zebra", "表头网格+隔行", True, True, True, zebra=True),
    ColorTableVariant("line_table", "横线表", False, False, True),
    ColorTableVariant("line_table_zebra", "横线表+隔行", False, False, True, zebra=True),
    ColorTableVariant("light_grid", "浅网格", False, True, True),
    ColorTableVariant("light_grid_zebra", "浅网格+隔行", False, True, True, zebra=True),
    ColorTableVariant("header_lines", "表头横线", True, False, True),
    ColorTableVariant("header_rule", "彩色三线表", True, False, False, header_rule_only=True),
)


def table_style_label(style_key: str | None) -> str:
    lookup = {option.key: option.label for option in TABLE_STYLE_OPTIONS}
    return lookup.get(str(style_key or ""), str(style_key or "三线表"))


def color_palette(key: str | None) -> ColorTablePalette:
    lookup = {palette.key: palette for palette in COLOR_TABLE_PALETTES}
    return lookup.get(str(key or ""), lookup["blue"])


def color_variant(key: str | None) -> ColorTableVariant:
    lookup = {variant.key: variant for variant in COLOR_TABLE_VARIANTS}
    lookup["header_columns"] = lookup["header_rule"]
    return lookup.get(str(key or ""), lookup["header_grid"])


__all__ = [
    "COLOR_TABLE_PALETTES",
    "COLOR_TABLE_VARIANTS",
    "TABLE_STYLE_OPTIONS",
    "ColorTablePalette",
    "ColorTableVariant",
    "TableStyleOption",
    "color_palette",
    "color_variant",
    "table_style_label",
]
