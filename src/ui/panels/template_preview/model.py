"""Immutable, Qt-free data contracts for template preview projection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TemplatePreviewMode(str, Enum):
    TEMPLATE_BASELINE = "template_baseline"
    CURRENT_PLAN = "current_plan"


class PreviewBlockKind(str, Enum):
    PAGE_GUIDES = "page_guides"
    SECTION_MARKER = "section_marker"
    HEADING = "heading"
    BODY = "body"
    TABLE = "table"
    HEADER = "header"
    FOOTER = "footer"
    TOC = "toc"
    FIGURE_CAPTION = "figure_caption"
    TABLE_CAPTION = "table_caption"
    FORMULA = "formula"
    REFERENCE = "reference"
    WATERMARK = "watermark"
    EMPTY_STATE = "empty_state"


@dataclass(frozen=True, slots=True)
class PreviewTextStyle:
    font_cn: str = "宋体"
    font_en: str = "Times New Roman"
    size_pt: float = 11.0
    bold: bool = False
    italic: bool = False
    alignment: str = "left"
    first_indent_pt: float = 0.0
    hanging_indent_pt: float = 0.0
    left_indent_pt: float = 0.0
    right_indent_pt: float = 0.0
    line_spacing_type: str = "multiple"
    line_spacing_value: float = 1.0
    space_before_pt: float = 0.0
    space_after_pt: float = 0.0


@dataclass(frozen=True, slots=True)
class PreviewPageGeometry:
    paper_label: str
    width_cm: float
    height_cm: float
    margin_top_cm: float
    margin_bottom_cm: float
    margin_left_cm: float
    margin_right_cm: float
    gutter_cm: float
    header_distance_cm: float
    footer_distance_cm: float
    neutral: bool = False


@dataclass(frozen=True, slots=True)
class PreviewTableStyle:
    border_mode: str = "three_line"
    layout_mode: str = "smart"
    accent_color: str = "000000"
    light_color: str = "BFBFBF"
    soft_color: str = "F2F2F2"
    header_text_color: str = "FFFFFF"
    header_fill: bool = False
    show_vertical: bool = False
    show_horizontal: bool = False
    zebra: bool = False
    header_rule_only: bool = False
    table_alignment: str = "center"
    cell_alignment: str = ""
    first_row_bold: bool = False
    repeat_header: bool = False
    border_width_pt: float = 0.5
    outer_width_pt: float = 1.0
    header_rule_width_pt: float = 0.5


@dataclass(frozen=True, slots=True)
class TemplatePreviewBlock:
    kind: PreviewBlockKind
    text: str = ""
    compact_text: str = ""
    style: PreviewTextStyle | None = None
    detail_style: PreviewTextStyle | None = None
    level: int = 0
    rows: tuple[tuple[str, ...], ...] = ()
    row_styles: tuple[PreviewTextStyle, ...] = ()
    table_style: PreviewTableStyle | None = None
    alignment: str = "left"
    draw_rule: bool = False
    rule_color: str = "000000"
    rule_width_pt: float = 0.5
    rule_spacing_pt: float = 0.0
    rule_style: str = "single"
    text_color: str = ""
    rotation: float = 0.0
    page_variant: str = "default"

    def text_for_density(self, *, compact: bool) -> str:
        if compact and self.compact_text:
            return self.compact_text
        return self.text


@dataclass(frozen=True, slots=True)
class PreviewPrunedModule:
    module_name: str
    label: str
    unmet_dependencies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TemplatePreviewProjection:
    mode: TemplatePreviewMode
    page_geometry: PreviewPageGeometry
    show_page_guides: bool
    show_header_distance_guide: bool
    show_footer_distance_guide: bool
    blocks: tuple[TemplatePreviewBlock, ...]
    hidden_feature_labels: tuple[str, ...]
    auto_pruned: tuple[PreviewPrunedModule, ...]
    status_text: str
    accessible_description: str

    @property
    def is_empty(self) -> bool:
        return any(
            block.kind is PreviewBlockKind.EMPTY_STATE
            for block in self.blocks
        )

    @property
    def visible_block_kinds(self) -> tuple[PreviewBlockKind, ...]:
        return tuple(dict.fromkeys(block.kind for block in self.blocks))


__all__ = [
    "PreviewBlockKind",
    "PreviewPageGeometry",
    "PreviewPrunedModule",
    "PreviewTableStyle",
    "PreviewTextStyle",
    "TemplatePreviewBlock",
    "TemplatePreviewMode",
    "TemplatePreviewProjection",
]
