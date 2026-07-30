"""Qt font measurement and geometry only for template preview projections."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from src.qt_api import QFont, QFontMetricsF, QRectF, Qt

from .model import (
    PreviewBlockKind,
    PreviewTextStyle,
    TemplatePreviewBlock,
    TemplatePreviewProjection,
)


_OUTER_PADDING = 18.0
_PAGE_GAP = 22.0
_DEFAULT_MAX_SINGLE_PAGE_WIDTH = 640.0
_MAX_PAIRED_PAGE_WIDTH = 500.0
_MIN_PAGE_WIDTH = 260.0
_NORMAL_BLOCK_GAP = 6.0
_COMPACT_BLOCK_GAP = 4.0


@dataclass(frozen=True, slots=True)
class PreviewBlockLayout:
    block: TemplatePreviewBlock
    rect: QRectF
    text: str
    font: QFont
    detail_font: QFont
    first_indent_px: float = 0.0
    hanging_indent_px: float = 0.0
    line_height_px: float = 0.0
    pt_scale: float = 1.0


@dataclass(frozen=True, slots=True)
class PreviewPageLayout:
    page_rect: QRectF
    content_rect: QRectF
    header_layout: PreviewBlockLayout | None
    footer_layout: PreviewBlockLayout | None
    block_layouts: tuple[PreviewBlockLayout, ...]
    scale_x: float
    scale_y: float


@dataclass(frozen=True, slots=True)
class TemplatePreviewLayout:
    pages: tuple[PreviewPageLayout, ...]
    total_height: float
    compact: bool
    columns: int
    page_width: float


def build_template_preview_layout(
    projection: TemplatePreviewProjection,
    width: float,
    *,
    max_single_page_width: float = _DEFAULT_MAX_SINGLE_PAGE_WIDTH,
) -> TemplatePreviewLayout:
    """Measure every projected block; never omit an overflowing block."""

    available_width = max(
        _MIN_PAGE_WIDTH,
        float(width) - _OUTER_PADDING * 2.0,
    )
    resolved_max_page_width = max(
        _MIN_PAGE_WIDTH,
        float(max_single_page_width),
    )
    initial_page_width = min(resolved_max_page_width, available_width)
    local_pages, compact = _layout_local_pages(
        projection,
        initial_page_width,
    )

    page_width = initial_page_width
    if len(local_pages) > 1 and available_width >= _MIN_PAGE_WIDTH * 2 + _PAGE_GAP:
        page_width = min(
            _MAX_PAIRED_PAGE_WIDTH,
            (available_width - _PAGE_GAP) / 2.0,
        )
        local_pages, compact = _layout_local_pages(projection, page_width)

    columns = (
        2
        if len(local_pages) > 1
        and page_width * 2.0 + _PAGE_GAP <= available_width + 0.5
        else 1
    )
    page_height = _page_height(projection, page_width)
    pages: list[PreviewPageLayout] = []
    for index, local_page in enumerate(local_pages):
        row = index // columns
        column = index % columns
        items_in_row = min(columns, len(local_pages) - row * columns)
        row_width = items_in_row * page_width + (items_in_row - 1) * _PAGE_GAP
        row_left = max(_OUTER_PADDING, (float(width) - row_width) / 2.0)
        x = row_left + column * (page_width + _PAGE_GAP)
        y = _OUTER_PADDING + row * (page_height + _PAGE_GAP)
        pages.append(_translate_page(local_page, x, y))

    rows = max(1, ceil(max(1, len(local_pages)) / columns))
    total_height = (
        _OUTER_PADDING * 2.0
        + rows * page_height
        + max(0, rows - 1) * _PAGE_GAP
    )
    return TemplatePreviewLayout(
        pages=tuple(pages),
        total_height=total_height,
        compact=compact,
        columns=columns,
        page_width=page_width,
    )


def _layout_local_pages(
    projection: TemplatePreviewProjection,
    page_width: float,
) -> tuple[tuple[PreviewPageLayout, ...], bool]:
    page_height = _page_height(projection, page_width)
    page_rect = QRectF(0.0, 0.0, page_width, page_height)
    content_rect = _content_rect(projection, page_rect)
    pt_scale = _page_pt_scale(
        page_width,
        projection.page_geometry.width_cm,
    )
    flow_blocks = tuple(
        block
        for block in projection.blocks
        if block.kind
        not in {
            PreviewBlockKind.PAGE_GUIDES,
            PreviewBlockKind.HEADER,
            PreviewBlockKind.FOOTER,
            PreviewBlockKind.WATERMARK,
        }
    )
    headers = tuple(
        block
        for block in projection.blocks
        if block.kind is PreviewBlockKind.HEADER
    )
    footers = tuple(
        block
        for block in projection.blocks
        if block.kind is PreviewBlockKind.FOOTER
    )

    normal_heights = tuple(
        _block_height(block, content_rect.width(), pt_scale, compact=False)
        for block in flow_blocks
    )
    normal_total = sum(normal_heights) + max(
        0,
        len(flow_blocks) - 1,
    ) * _NORMAL_BLOCK_GAP
    compact = normal_total > content_rect.height()
    gap = _COMPACT_BLOCK_GAP if compact else _NORMAL_BLOCK_GAP
    heights = (
        tuple(
            _block_height(block, content_rect.width(), pt_scale, compact=True)
            for block in flow_blocks
        )
        if compact
        else normal_heights
    )

    page_groups: list[list[tuple[TemplatePreviewBlock, float]]] = [[]]
    used_height = 0.0
    for block, height in zip(flow_blocks, heights):
        next_height = height if not page_groups[-1] else gap + height
        if (
            page_groups[-1]
            and used_height + next_height > content_rect.height()
        ):
            page_groups.append([])
            used_height = 0.0
            next_height = height
        page_groups[-1].append((block, min(height, content_rect.height())))
        used_height += next_height

    if not flow_blocks:
        page_groups = [[]]

    variant_names = {
        block.page_variant for block in (*headers, *footers)
    }
    required_pages = (
        3
        if {"first", "even"}.issubset(variant_names)
        else 2
        if variant_names.intersection({"first", "even"})
        else 1
    )
    while len(page_groups) < required_pages:
        page_groups.append([])

    scale_x = page_width / projection.page_geometry.width_cm
    scale_y = page_height / projection.page_geometry.height_cm

    pages: list[PreviewPageLayout] = []
    for page_index, group in enumerate(page_groups):
        variant_name = _page_variant_for_index(page_index, variant_names)
        header_layout = _header_footer_layout(
            _variant_block(headers, variant_name),
            projection,
            page_rect,
            content_rect,
            pt_scale,
            is_header=True,
        )
        footer_layout = _header_footer_layout(
            _variant_block(footers, variant_name),
            projection,
            page_rect,
            content_rect,
            pt_scale,
            is_header=False,
        )
        y = content_rect.top()
        layouts: list[PreviewBlockLayout] = []
        for block, height in group:
            if layouts:
                y += gap
            rect = _indented_block_rect(
                block,
                QRectF(content_rect.left(), y, content_rect.width(), height),
                pt_scale,
            )
            layouts.append(
                PreviewBlockLayout(
                    block=block,
                    rect=rect,
                    text=block.text_for_density(compact=compact),
                    font=_font_for_style(block.style, pt_scale),
                    detail_font=_font_for_style(
                        block.detail_style or block.style,
                        pt_scale,
                    ),
                    first_indent_px=(
                        float(getattr(block.style, "first_indent_pt", 0.0) or 0.0)
                        - float(getattr(block.style, "hanging_indent_pt", 0.0) or 0.0)
                    ) * pt_scale,
                    # ``rect.left`` is already the effective Word left indent.
                    # Later lines stay there; a hanging indent moves only the
                    # first line back to the left.
                    hanging_indent_px=0.0,
                    line_height_px=_line_height_px(
                        block.style,
                        _font_for_style(block.style, pt_scale),
                        pt_scale,
                    ),
                    pt_scale=pt_scale,
                )
            )
            y += height
        pages.append(
            PreviewPageLayout(
                page_rect=QRectF(page_rect),
                content_rect=QRectF(content_rect),
                header_layout=header_layout,
                footer_layout=footer_layout,
                block_layouts=tuple(layouts),
                scale_x=scale_x,
                scale_y=scale_y,
            )
        )
    return tuple(pages), compact


def _page_variant_for_index(page_index: int, variants: set[str]) -> str:
    page_number = page_index + 1
    if page_number == 1 and "first" in variants:
        return "first"
    if page_number % 2 == 0 and "even" in variants:
        return "even"
    return "default"


def _variant_block(
    blocks: tuple[TemplatePreviewBlock, ...],
    variant_name: str,
) -> TemplatePreviewBlock | None:
    return next(
        (block for block in blocks if block.page_variant == variant_name),
        next((block for block in blocks if block.page_variant == "default"), None),
    )


def _page_height(projection: TemplatePreviewProjection, page_width: float) -> float:
    geometry = projection.page_geometry
    return page_width * geometry.height_cm / geometry.width_cm


def _content_rect(
    projection: TemplatePreviewProjection,
    page_rect: QRectF,
) -> QRectF:
    geometry = projection.page_geometry
    scale_x = page_rect.width() / geometry.width_cm
    scale_y = page_rect.height() / geometry.height_cm
    left = min(
        page_rect.width() * 0.43,
        (geometry.margin_left_cm + geometry.gutter_cm) * scale_x,
    )
    right = min(
        page_rect.width() * 0.43,
        geometry.margin_right_cm * scale_x,
    )
    top = min(
        page_rect.height() * 0.40,
        geometry.margin_top_cm * scale_y,
    )
    bottom = min(
        page_rect.height() * 0.40,
        geometry.margin_bottom_cm * scale_y,
    )
    rect = page_rect.adjusted(left, top, -right, -bottom)
    if rect.width() < 80.0 or rect.height() < 120.0:
        return page_rect.adjusted(
            page_rect.width() * 0.14,
            page_rect.height() * 0.11,
            -page_rect.width() * 0.14,
            -page_rect.height() * 0.11,
        )
    return rect


def _block_height(
    block: TemplatePreviewBlock,
    width: float,
    pt_scale: float,
    *,
    compact: bool,
) -> float:
    font = _font_for_style(block.style, pt_scale)
    detail_font = _font_for_style(block.detail_style or block.style, pt_scale)
    metrics = QFontMetricsF(font)
    detail_metrics = QFontMetricsF(detail_font)
    scale = pt_scale
    before = max(0.0, float(getattr(block.style, "space_before_pt", 0.0))) * scale
    after = max(0.0, float(getattr(block.style, "space_after_pt", 0.0))) * scale

    if block.kind is PreviewBlockKind.TABLE:
        row_height = max(metrics.height() * 1.45, 21.0 * scale)
        return max(36.0, row_height * max(1, len(block.rows)))
    if block.kind is PreviewBlockKind.TOC:
        title_height = metrics.height() * 1.25
        if block.row_styles:
            rows_height = sum(
                max(
                    _font_for_style(row_style, pt_scale).pixelSize() * 1.35,
                    QFontMetricsF(_font_for_style(row_style, pt_scale)).height() * 1.25,
                )
                + max(0.0, row_style.space_before_pt) * scale
                + max(0.0, row_style.space_after_pt) * scale
                for row_style in block.row_styles
            )
        else:
            rows_height = detail_metrics.height() * 1.25 * len(block.rows)
        return before + title_height + 4.0 * scale + rows_height + after
    if block.kind is PreviewBlockKind.FORMULA:
        return before + max(metrics.height(), detail_metrics.height()) * 1.35 + after
    if block.kind is PreviewBlockKind.EMPTY_STATE:
        return max(84.0 * scale, metrics.height() * 3.0)
    if block.kind is PreviewBlockKind.SECTION_MARKER:
        return max(20.0 * scale, metrics.height() * 1.25)

    text = block.text_for_density(compact=compact)
    style = block.style
    text_width = max(
        20.0,
        width
        - 4.0
        - max(0.0, float(getattr(style, "left_indent_pt", 0.0) or 0.0)) * scale
        - max(0.0, float(getattr(style, "right_indent_pt", 0.0) or 0.0)) * scale,
    )
    bounds = metrics.boundingRect(
        QRectF(0.0, 0.0, text_width, 10000.0),
        Qt.TextWordWrap,
        text,
    )
    measured = max(metrics.height(), bounds.height())
    if style is not None:
        if style.line_spacing_type == "exact":
            target_line = max(
                1.0,
                style.line_spacing_value * scale,
            )
            measured *= target_line / max(metrics.height(), 1.0)
        else:
            measured *= max(1.0, style.line_spacing_value)
    return before + measured + after


def _indented_block_rect(
    block: TemplatePreviewBlock,
    rect: QRectF,
    pt_scale: float,
) -> QRectF:
    style = block.style
    if style is None:
        return rect
    scale = pt_scale
    left = max(0.0, style.left_indent_pt) * scale
    right = max(0.0, style.right_indent_pt) * scale
    if left + right >= rect.width() * 0.7:
        return rect
    return rect.adjusted(left, 0.0, -right, 0.0)


def _header_footer_layout(
    block: TemplatePreviewBlock | None,
    projection: TemplatePreviewProjection,
    page_rect: QRectF,
    content_rect: QRectF,
    pt_scale: float,
    *,
    is_header: bool,
) -> PreviewBlockLayout | None:
    if block is None or (not block.text and not block.draw_rule):
        return None
    geometry = projection.page_geometry
    scale_y = page_rect.height() / geometry.height_cm
    font = _font_for_style(block.style, pt_scale)
    rule_spacing = (
        max(0.0, block.rule_spacing_pt) * pt_scale
        if is_header and block.draw_rule
        else 0.0
    )
    height = max(QFontMetricsF(font).height() * 1.4 + rule_spacing, 18.0)
    if is_header:
        center_y = page_rect.top() + geometry.header_distance_cm * scale_y
    else:
        center_y = page_rect.bottom() - geometry.footer_distance_cm * scale_y
    rect = QRectF(
        content_rect.left(),
        center_y - height / 2.0,
        content_rect.width(),
        height,
    )
    return PreviewBlockLayout(
        block=block,
        rect=rect,
        text=block.text,
        font=font,
            detail_font=font,
            pt_scale=pt_scale,
    )


def _font_for_style(
    style: PreviewTextStyle | None,
    pt_scale: float,
) -> QFont:
    value = style or PreviewTextStyle()
    font = QFont()
    families = [name for name in (value.font_en, value.font_cn) if name]
    try:
        font.setFamilies(families or ["宋体"])
    except AttributeError:
        font.setFamily((families or ["宋体"])[-1])
    font.setPixelSize(max(4, int(round(value.size_pt * pt_scale))))
    font.setBold(value.bold)
    font.setItalic(value.italic)
    return font


def _page_pt_scale(page_width: float, paper_width_cm: float) -> float:
    # Geometry and typography share one physical scale for every paper size;
    # QFont point sizes would otherwise add screen DPI a second time.
    paper_width_pt = max(0.01, float(paper_width_cm)) * 72.0 / 2.54
    return max(0.01, float(page_width) / paper_width_pt)


def _line_height_px(
    style: PreviewTextStyle | None,
    font: QFont,
    pt_scale: float,
) -> float:
    metrics = QFontMetricsF(font)
    if style is None:
        return metrics.height()
    if style.line_spacing_type == "exact":
        return max(1.0, style.line_spacing_value * pt_scale)
    return max(metrics.height(), metrics.height() * max(0.1, style.line_spacing_value))


def _translate_page(
    page: PreviewPageLayout,
    x: float,
    y: float,
) -> PreviewPageLayout:
    def translated(rect: QRectF) -> QRectF:
        result = QRectF(rect)
        result.translate(x, y)
        return result

    def translate_block(
        layout: PreviewBlockLayout | None,
    ) -> PreviewBlockLayout | None:
        if layout is None:
            return None
        return PreviewBlockLayout(
            block=layout.block,
            rect=translated(layout.rect),
            text=layout.text,
            font=layout.font,
            detail_font=layout.detail_font,
            first_indent_px=layout.first_indent_px,
            hanging_indent_px=layout.hanging_indent_px,
            line_height_px=layout.line_height_px,
            pt_scale=layout.pt_scale,
        )

    return PreviewPageLayout(
        page_rect=translated(page.page_rect),
        content_rect=translated(page.content_rect),
        header_layout=translate_block(page.header_layout),
        footer_layout=translate_block(page.footer_layout),
        block_layouts=tuple(
            translate_block(layout) for layout in page.block_layouts
        ),
        scale_x=page.scale_x,
        scale_y=page.scale_y,
    )


__all__ = [
    "PreviewBlockLayout",
    "PreviewPageLayout",
    "TemplatePreviewLayout",
    "build_template_preview_layout",
]
