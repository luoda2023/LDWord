"""QPainter renderer for immutable template projections.

The page never edits configuration.  The embedded renderer is one clickable
preview surface; its owner decides how to open the read-only whole-window view.
"""

from __future__ import annotations

from math import ceil

from src.qt_api import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPen,
    QRectF,
    QSize,
    Signal,
    Qt,
    QWidget,
)
from src.shared.ui.theme import bind_theme, get_theme

from .layout import (
    PreviewBlockLayout,
    PreviewPageLayout,
    TemplatePreviewLayout,
    build_template_preview_layout,
)
from .model import (
    PreviewBlockKind,
    PreviewTableStyle,
    TemplatePreviewProjection,
)


_PAGE_COLOR = "#FFFFFF"
_PAGE_BORDER = "#CBD5E1"
_GUIDE_COLOR = "#6B7F9D"
_TEXT_COLOR = "#172033"
_MUTED_TEXT_COLOR = "#667085"
_INLINE_MAX_PAGE_WIDTH = 640.0
_DIALOG_MAX_PAGE_WIDTH = 900.0
_ACCENT_COLORS = {
    "blue": "#3978D6",
    "green": "#2D8B66",
    "red": "#C84C4C",
    "orange": "#C8782D",
    "purple": "#7656B5",
    "gray": "#667085",
}


class TemplateStylePreview(QWidget):
    """Read-only page that opens one whole-window preview when activated."""

    preview_requested = Signal()

    def __init__(self, parent=None, *, presentation: str = "inline") -> None:
        super().__init__(parent)
        if presentation not in {"inline", "dialog"}:
            raise ValueError("presentation must be 'inline' or 'dialog'")
        self._presentation = presentation
        self._max_page_width = (
            _DIALOG_MAX_PAGE_WIDTH
            if presentation == "dialog"
            else _INLINE_MAX_PAGE_WIDTH
        )
        self._projection: TemplatePreviewProjection | None = None
        self._layout_snapshot: TemplatePreviewLayout | None = None
        self._layout_width = -1
        self.setObjectName("template_style_preview")
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("")
        self.setAccessibleName("模板样式预览，点击打开整体预览")
        self.setMinimumWidth(280)
        bind_theme(self, self.apply_theme)

    @property
    def projection(self) -> TemplatePreviewProjection | None:
        return self._projection

    @property
    def presentation(self) -> str:
        return self._presentation

    @property
    def layout_snapshot(self) -> TemplatePreviewLayout | None:
        return self._layout_snapshot

    def set_projection(
        self,
        projection: TemplatePreviewProjection | None,
    ) -> None:
        if projection == self._projection:
            return
        self._projection = projection
        self._layout_snapshot = None
        self._layout_width = -1
        self.setAccessibleDescription(
            projection.accessible_description if projection is not None else ""
        )
        self.setProperty(
            "template_preview_mode",
            projection.mode.value if projection is not None else "",
        )
        self.setProperty(
            "template_preview_status",
            projection.status_text if projection is not None else "",
        )
        self._rebuild_layout()
        self.updateGeometry()
        self.update()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        if self._projection is None:
            return 360
        layout = build_template_preview_layout(
            self._projection,
            max(280, int(width)),
            max_single_page_width=self._max_page_width,
        )
        return max(360, int(ceil(layout.total_height)))

    def sizeHint(self) -> QSize:
        preferred = 936 if self._presentation == "dialog" else 720
        width = max(preferred, self.width())
        return QSize(width, self.heightForWidth(width))

    def apply_theme(self) -> None:
        self._layout_snapshot = None
        self._layout_width = -1
        self._rebuild_layout()
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild_layout()

    def paintEvent(self, event) -> None:
        del event
        if self._projection is None:
            return
        if self._layout_snapshot is None:
            self._rebuild_layout()
        layout = self._layout_snapshot
        if layout is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        for index, page in enumerate(layout.pages, start=1):
            self._draw_page(painter, page, index=index, total=len(layout.pages))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            point = event.position() if hasattr(event, "position") else event.pos()
            if self._page_contains(point):
                self.preview_requested.emit()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space}:
            self.preview_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _page_contains(self, point) -> bool:
        layout = self._layout_snapshot
        if layout is None:
            return False
        return any(page.page_rect.contains(point) for page in layout.pages)

    def _rebuild_layout(self) -> None:
        if self._projection is None:
            self._layout_snapshot = None
            return
        width = max(280, self.width() or self.sizeHint().width())
        if self._layout_snapshot is not None and self._layout_width == width:
            return
        self._layout_width = width
        self._layout_snapshot = build_template_preview_layout(
            self._projection,
            width,
            max_single_page_width=self._max_page_width,
        )
        desired = max(360, int(ceil(self._layout_snapshot.total_height)))
        if self.minimumHeight() != desired:
            self.setMinimumHeight(desired)
            self.updateGeometry()

    def _draw_page(
        self,
        painter: QPainter,
        page: PreviewPageLayout,
        *,
        index: int,
        total: int,
    ) -> None:
        shadow = page.page_rect.translated(0.0, 5.0)
        shadow_color = QColor(15, 23, 42, 25)
        painter.setPen(Qt.NoPen)
        painter.setBrush(shadow_color)
        painter.drawRoundedRect(shadow, 8.0, 8.0)

        painter.setPen(QPen(QColor(_PAGE_BORDER), 1.0))
        painter.setBrush(QColor(_PAGE_COLOR))
        painter.drawRoundedRect(page.page_rect, 7.0, 7.0)

        projection = self._projection
        if projection is None:
            return
        watermark = next(
            (
                block
                for block in projection.blocks
                if block.kind is PreviewBlockKind.WATERMARK
            ),
            None,
        )
        if watermark is not None:
            self._draw_watermark(painter, page, watermark)
        if projection.show_page_guides:
            self._draw_page_guides(painter, page)
        if total > 1:
            self._draw_page_index(painter, page, index, total)
        if page.header_layout is not None:
            self._draw_header_footer(painter, page.header_layout, is_header=True)
        if page.footer_layout is not None:
            self._draw_header_footer(painter, page.footer_layout, is_header=False)
        for block in page.block_layouts:
            self._draw_block(painter, block)

    def _draw_page_guides(
        self,
        painter: QPainter,
        page: PreviewPageLayout,
    ) -> None:
        projection = self._projection
        if projection is None:
            return
        theme = get_theme()
        page_rect = page.page_rect
        content = page.content_rect
        band = QColor(theme.primary)
        band.setAlpha(12)
        painter.setPen(Qt.NoPen)
        painter.fillRect(
            QRectF(
                page_rect.left(),
                page_rect.top(),
                page_rect.width(),
                max(0.0, content.top() - page_rect.top()),
            ),
            band,
        )
        painter.fillRect(
            QRectF(
                page_rect.left(),
                content.bottom(),
                page_rect.width(),
                max(0.0, page_rect.bottom() - content.bottom()),
            ),
            band,
        )
        side_band = QColor(theme.primary)
        side_band.setAlpha(9)
        painter.fillRect(
            QRectF(
                page_rect.left(),
                content.top(),
                max(0.0, content.left() - page_rect.left()),
                content.height(),
            ),
            side_band,
        )
        painter.fillRect(
            QRectF(
                content.right(),
                content.top(),
                max(0.0, page_rect.right() - content.right()),
                content.height(),
            ),
            side_band,
        )

        pen = QPen(QColor(_GUIDE_COLOR), 1.0)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        mark = max(7.0, page.page_rect.width() * 0.025)
        for x, x_dir in ((content.left(), 1), (content.right(), -1)):
            for y, y_dir in ((content.top(), 1), (content.bottom(), -1)):
                painter.drawLine(x, y, x + x_dir * mark, y)
                painter.drawLine(x, y, x, y + y_dir * mark)

        geometry = projection.page_geometry
        self._draw_badge(
            painter,
            page,
            geometry.paper_label,
        )
        self._draw_margin_dimensions(painter, page)
        if projection.show_header_distance_guide and page.header_layout is not None:
            self._draw_vertical_dimension(
                painter,
                page.page_rect.top() + 5.0,
                page.header_layout.rect.center().y(),
                page.content_rect.right() - 20.0,
                f"{geometry.header_distance_cm:g}cm",
                page,
            )
        if projection.show_footer_distance_guide and page.footer_layout is not None:
            self._draw_vertical_dimension(
                painter,
                page.footer_layout.rect.center().y(),
                page.page_rect.bottom() - 5.0,
                page.content_rect.right() - 20.0,
                f"{geometry.footer_distance_cm:g}cm",
                page,
            )

    def _draw_badge(
        self,
        painter: QPainter,
        page: PreviewPageLayout,
        text: str,
    ) -> None:
        if not text:
            return
        theme = get_theme()
        compact = page.page_rect.width() < 520.0
        font = QFont(self.font())
        font.setPointSizeF(
            max(7.0, theme.font_size_sm * (0.68 if compact else 0.8))
        )
        font.setBold(True)
        metrics = QFontMetricsF(font)
        width = max(
            40.0 if compact else 54.0,
            metrics.horizontalAdvance(text) + (16.0 if compact else 24.0),
        )
        height = max(
            20.0 if compact else 24.0,
            metrics.height() + (5.0 if compact else 8.0),
        )
        rect = QRectF(
            page.page_rect.left() + (8.0 if compact else 14.0),
            page.page_rect.top() + (8.0 if compact else 12.0),
            width,
            height,
        )
        painter.setPen(QPen(QColor(theme.primary), 1.0))
        fill = QColor(theme.primary)
        fill.setAlpha(12)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, height / 2.0, height / 2.0)
        painter.setFont(font)
        painter.setPen(QColor(theme.primary))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _draw_margin_dimensions(
        self,
        painter: QPainter,
        page: PreviewPageLayout,
    ) -> None:
        projection = self._projection
        if projection is None or page.page_rect.width() < 360:
            return
        geometry = projection.page_geometry
        page_rect = page.page_rect
        content = page.content_rect
        inset = 5.0
        side_y = content.top() + min(
            max(24.0, content.height() * 0.06),
            max(24.0, content.height() - 24.0),
        )
        left_value = geometry.margin_left_cm + geometry.gutter_cm
        left_label = (
            f"{geometry.margin_left_cm:g}+{geometry.gutter_cm:g}cm"
            if geometry.gutter_cm > 0
            else f"{left_value:g}cm"
        )
        self._draw_horizontal_dimension(
            painter,
            page_rect.left() + inset,
            content.left() - inset,
            side_y,
            left_label,
            page,
        )
        self._draw_horizontal_dimension(
            painter,
            content.right() + inset,
            page_rect.right() - inset,
            side_y,
            f"{geometry.margin_right_cm:g}cm",
            page,
        )
        top_bottom_x = page_rect.left() + page_rect.width() * 0.18
        self._draw_vertical_dimension(
            painter,
            page_rect.top() + inset,
            content.top() - inset,
            top_bottom_x,
            f"{geometry.margin_top_cm:g}cm",
            page,
        )
        self._draw_vertical_dimension(
            painter,
            content.bottom() + inset,
            page_rect.bottom() - inset,
            top_bottom_x,
            f"{geometry.margin_bottom_cm:g}cm",
            page,
        )

    def _dimension_style(self, page: PreviewPageLayout):
        scale = max(0.72, min(1.2, page.page_rect.width() / 620.0))
        font = QFont(self.font())
        font.setPointSizeF(max(7.5, 8.5 * scale))
        metrics = QFontMetricsF(font)
        pen = QPen(QColor(_GUIDE_COLOR), max(0.8, scale))
        background = QColor(_PAGE_COLOR)
        background.setAlpha(225)
        arrow_size = max(2, round(3 * scale))
        return font, metrics, pen, background, arrow_size

    def _draw_horizontal_dimension(
        self,
        painter: QPainter,
        x1: float,
        x2: float,
        y: float,
        label: str,
        page: PreviewPageLayout,
    ) -> None:
        if x2 <= x1:
            return
        font, metrics, pen, background, arrow = self._dimension_style(page)
        text_width = metrics.horizontalAdvance(label)
        text_height = metrics.height()
        middle = (x1 + x2) / 2.0
        gap = text_width / 2.0 + 4.0
        painter.setPen(pen)
        if x2 - x1 > text_width + arrow * 6:
            painter.drawLine(int(x1), int(y), int(middle - gap), int(y))
            painter.drawLine(int(middle + gap), int(y), int(x2), int(y))
            self._draw_horizontal_arrow(painter, pen, x1, y, arrow, points_left=True)
            self._draw_horizontal_arrow(painter, pen, x2, y, arrow, points_left=False)
        else:
            painter.drawLine(int(x1), int(y), int(x2), int(y))
            painter.drawLine(int(x1), int(y - arrow), int(x1), int(y + arrow))
            painter.drawLine(int(x2), int(y - arrow), int(x2), int(y + arrow))
        label_rect = QRectF(
            middle - text_width / 2.0 - 3.0,
            y - text_height / 2.0,
            text_width + 6.0,
            text_height,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(label_rect, 3.0, 3.0)
        painter.setFont(font)
        painter.setPen(QColor(_GUIDE_COLOR))
        painter.drawText(label_rect, Qt.AlignCenter, label)

    def _draw_vertical_dimension(
        self,
        painter: QPainter,
        y1: float,
        y2: float,
        x: float,
        label: str,
        page: PreviewPageLayout,
    ) -> None:
        if y2 <= y1:
            return
        font, metrics, pen, background, arrow = self._dimension_style(page)
        text_width = metrics.horizontalAdvance(label)
        text_height = metrics.height()
        middle = (y1 + y2) / 2.0
        gap = text_height / 2.0 + 3.0
        painter.setPen(pen)
        if y2 - y1 > text_height + arrow * 6:
            painter.drawLine(int(x), int(y1), int(x), int(middle - gap))
            painter.drawLine(int(x), int(middle + gap), int(x), int(y2))
            self._draw_vertical_arrow(painter, pen, x, y1, arrow, points_up=True)
            self._draw_vertical_arrow(painter, pen, x, y2, arrow, points_up=False)
        else:
            painter.drawLine(int(x), int(y1), int(x), int(y2))
            painter.drawLine(int(x - arrow), int(y1), int(x + arrow), int(y1))
            painter.drawLine(int(x - arrow), int(y2), int(x + arrow), int(y2))
        label_rect = QRectF(
            x - text_width / 2.0 - 3.0,
            middle - text_height / 2.0,
            text_width + 6.0,
            text_height,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(label_rect, 3.0, 3.0)
        painter.setFont(font)
        painter.setPen(QColor(_GUIDE_COLOR))
        painter.drawText(label_rect, Qt.AlignCenter, label)

    @staticmethod
    def _draw_horizontal_arrow(
        painter: QPainter,
        pen: QPen,
        x: float,
        y: float,
        size: int,
        *,
        points_left: bool,
    ) -> None:
        delta = size if points_left else -size
        painter.setPen(pen)
        painter.drawLine(int(x), int(y), int(x + delta), int(y - size))
        painter.drawLine(int(x), int(y), int(x + delta), int(y + size))

    @staticmethod
    def _draw_vertical_arrow(
        painter: QPainter,
        pen: QPen,
        x: float,
        y: float,
        size: int,
        *,
        points_up: bool,
    ) -> None:
        delta = size if points_up else -size
        painter.setPen(pen)
        painter.drawLine(int(x), int(y), int(x - size), int(y + delta))
        painter.drawLine(int(x), int(y), int(x + size), int(y + delta))

    def _draw_page_index(
        self,
        painter: QPainter,
        page: PreviewPageLayout,
        index: int,
        total: int,
    ) -> None:
        font = QFont(self.font())
        font.setPointSizeF(7.5)
        painter.setFont(font)
        painter.setPen(QColor(_MUTED_TEXT_COLOR))
        painter.drawText(
            page.page_rect.adjusted(0.0, 8.0, -10.0, 0.0),
            Qt.AlignTop | Qt.AlignRight,
            f"{index} / {total}",
        )

    def _draw_header_footer(
        self,
        painter: QPainter,
        layout: PreviewBlockLayout,
        *,
        is_header: bool,
    ) -> None:
        painter.setFont(layout.font)
        painter.setPen(QColor(layout.block.text_color or _MUTED_TEXT_COLOR))
        text_rect = QRectF(layout.rect)
        if is_header and layout.block.draw_rule:
            text_rect.adjust(
                0.0,
                0.0,
                0.0,
                -max(0.0, layout.block.rule_spacing_pt) * layout.pt_scale,
            )
        painter.drawText(
            text_rect,
            _alignment_flags(layout.block.alignment) | Qt.AlignVCenter,
            layout.text,
        )
        if is_header and layout.block.draw_rule:
            color = QColor(f"#{layout.block.rule_color.lstrip('#')}")
            pen = QPen(
                color if color.isValid() else QColor(_MUTED_TEXT_COLOR),
                max(0.5, layout.block.rule_width_pt * layout.pt_scale),
            )
            if layout.block.rule_style in {"dashed", "dash"}:
                pen.setStyle(Qt.DashLine)
            elif layout.block.rule_style in {"dotted", "dot"}:
                pen.setStyle(Qt.DotLine)
            painter.setPen(pen)
            if layout.block.rule_style == "double":
                separation = max(2.0, pen.widthF() * 2.0)
                for y in (layout.rect.bottom(), layout.rect.bottom() - separation):
                    painter.drawLine(
                        layout.rect.left(), y, layout.rect.right(), y
                    )
            else:
                painter.drawLine(
                    layout.rect.left(),
                    layout.rect.bottom(),
                    layout.rect.right(),
                    layout.rect.bottom(),
                )

    def _draw_watermark(
        self,
        painter: QPainter,
        page: PreviewPageLayout,
        block,
    ) -> None:
        painter.save()
        font = QFont("宋体")
        font.setPixelSize(
            max(10, int(round(float(block.style.size_pt or 48.0) * page.scale_x / 72.0 * 2.54)))
        )
        font.setBold(bool(block.style.bold))
        painter.setFont(font)
        color = QColor(block.text_color or "#C0C0C0")
        if not color.isValid():
            color = QColor("#C0C0C0")
        painter.setPen(color)
        painter.translate(page.page_rect.center())
        painter.rotate(float(block.rotation or 0.0))
        rect = QRectF(
            -page.page_rect.width() * 0.42,
            -40.0,
            page.page_rect.width() * 0.84,
            80.0,
        )
        painter.drawText(rect, Qt.AlignCenter, block.text)
        painter.restore()

    def _draw_block(
        self,
        painter: QPainter,
        layout: PreviewBlockLayout,
    ) -> None:
        kind = layout.block.kind
        if kind is PreviewBlockKind.TABLE:
            self._draw_table(painter, layout)
            return
        if kind is PreviewBlockKind.TOC:
            self._draw_toc(painter, layout)
            return
        if kind is PreviewBlockKind.FORMULA:
            self._draw_formula(painter, layout)
            return
        if kind is PreviewBlockKind.SECTION_MARKER:
            self._draw_section_marker(painter, layout)
            return

        painter.setFont(layout.font)
        unknown_style = kind is PreviewBlockKind.HEADING and layout.block.style is None
        painter.setPen(
            QColor(_MUTED_TEXT_COLOR)
            if kind is PreviewBlockKind.EMPTY_STATE or unknown_style
            else QColor(_TEXT_COLOR)
        )
        text = (
            f"{layout.text}（保留原文样式）"
            if unknown_style
            else layout.text
        )
        flags = _alignment_flags(
            layout.block.alignment
            or getattr(layout.block.style, "alignment", "left")
        )
        if kind is PreviewBlockKind.EMPTY_STATE:
            flags |= Qt.AlignVCenter
        else:
            flags |= Qt.AlignTop | Qt.TextWordWrap
        if kind in {
            PreviewBlockKind.BODY,
            PreviewBlockKind.HEADING,
            PreviewBlockKind.REFERENCE,
        } and layout.block.style is not None:
            self._draw_wrapped_text(painter, layout, text)
        else:
            painter.drawText(layout.rect, flags, text)

    def _draw_formula(
        self,
        painter: QPainter,
        layout: PreviewBlockLayout,
    ) -> None:
        formula_text, number_text = (
            layout.block.rows[0]
            if layout.block.rows
            else (layout.text, "")
        )
        table_rect = _aligned_table_rect(
            layout.rect,
            layout.block.alignment,
            "smart",
        )
        number_width = min(
            table_rect.width() * 0.24,
            max(34.0, QFontMetricsF(layout.detail_font).horizontalAdvance(number_text) + 12.0),
        )
        formula_rect = table_rect.adjusted(0.0, 0.0, -number_width, 0.0)
        number_rect = QRectF(
            table_rect.right() - number_width,
            table_rect.top(),
            number_width,
            table_rect.height(),
        )
        painter.setFont(layout.font)
        painter.setPen(QColor(_TEXT_COLOR))
        painter.drawText(
            formula_rect,
            _alignment_flags(getattr(layout.block.style, "alignment", "center"))
            | Qt.AlignVCenter,
            formula_text,
        )
        if number_text:
            painter.setFont(layout.detail_font)
            painter.drawText(
                number_rect,
                _alignment_flags(
                    getattr(layout.block.detail_style, "alignment", "right")
                )
                | Qt.AlignVCenter,
                number_text,
            )

    def _draw_wrapped_text(
        self,
        painter: QPainter,
        layout: PreviewBlockLayout,
        text: str,
    ) -> None:
        metrics = QFontMetricsF(layout.font)
        first_left = layout.rect.left() + layout.first_indent_px
        later_left = layout.rect.left() + layout.hanging_indent_px
        first_width = max(8.0, layout.rect.right() - first_left)
        later_width = max(8.0, layout.rect.right() - later_left)
        lines = _wrap_text(metrics, text, first_width, later_width)
        line_height = max(1.0, layout.line_height_px or metrics.height())
        y = layout.rect.top() + metrics.ascent()
        for index, line in enumerate(lines):
            if y - metrics.ascent() > layout.rect.bottom():
                break
            left = first_left if index == 0 else later_left
            width = first_width if index == 0 else later_width
            line_rect = QRectF(left, y - metrics.ascent(), width, line_height)
            alignment = str(layout.block.style.alignment or "left")
            if alignment == "right":
                x = line_rect.right() - metrics.horizontalAdvance(line)
            elif alignment == "center":
                x = line_rect.left() + max(
                    0.0,
                    (line_rect.width() - metrics.horizontalAdvance(line)) / 2.0,
                )
            elif alignment == "justify" and index < len(lines) - 1 and len(line) > 1:
                extra = max(
                    0.0,
                    (line_rect.width() - metrics.horizontalAdvance(line))
                    / (len(line) - 1),
                )
                x = line_rect.left()
                for character in line:
                    painter.drawText(float(x), float(y), character)
                    x += metrics.horizontalAdvance(character) + extra
                y += line_height
                continue
            else:
                x = line_rect.left()
            painter.drawText(float(x), float(y), line)
            y += line_height

    def _draw_section_marker(
        self,
        painter: QPainter,
        layout: PreviewBlockLayout,
    ) -> None:
        center = layout.rect.center().y()
        pen = QPen(QColor(_PAGE_BORDER), 0.8)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(layout.rect.left(), center, layout.rect.right(), center)
        painter.setFont(layout.font)
        metrics = QFontMetricsF(layout.font)
        width = min(
            layout.rect.width() * 0.78,
            metrics.horizontalAdvance(layout.text) + 18.0,
        )
        label_rect = QRectF(
            layout.rect.center().x() - width / 2.0,
            layout.rect.top(),
            width,
            layout.rect.height(),
        )
        painter.fillRect(label_rect, QColor(_PAGE_COLOR))
        painter.setPen(QColor(_MUTED_TEXT_COLOR))
        painter.drawText(label_rect, Qt.AlignCenter, layout.text)

    def _draw_table(
        self,
        painter: QPainter,
        layout: PreviewBlockLayout,
    ) -> None:
        rows = layout.block.rows
        if not rows:
            return
        style = layout.block.table_style or PreviewTableStyle()
        rect = _aligned_table_rect(
            layout.rect,
            style.table_alignment,
            style.layout_mode,
        )
        row_height = rect.height() / len(rows)
        columns = max(1, max(len(row) for row in rows))
        column_width = rect.width() / columns
        accent = _hex_color(style.accent_color, "#4472C4")
        light = _hex_color(style.light_color, "#B4C6E7")
        soft = _hex_color(style.soft_color, "#EAF1FB")
        painter.fillRect(rect, QColor(_PAGE_COLOR))

        if style.border_mode == "color_table":
            if style.zebra:
                for row_index in range(1, len(rows), 2):
                    painter.fillRect(
                        QRectF(
                            rect.left(),
                            rect.top() + row_index * row_height,
                            rect.width(),
                            row_height,
                        ),
                        soft,
                    )
            if style.header_fill:
                painter.fillRect(
                    QRectF(rect.left(), rect.top(), rect.width(), row_height),
                    accent,
                )

        border_width = max(0.45, style.border_width_pt * layout.pt_scale)
        outer_width = max(0.55, style.outer_width_pt * layout.pt_scale)
        header_width = max(0.45, style.header_rule_width_pt * layout.pt_scale)
        if style.border_mode == "three_line":
            painter.setPen(QPen(QColor("#000000"), outer_width))
            painter.drawLine(rect.topLeft(), rect.topRight())
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            painter.setPen(QPen(QColor("#000000"), header_width))
            painter.drawLine(
                rect.left(), rect.top() + row_height,
                rect.right(), rect.top() + row_height,
            )
        elif style.border_mode == "full_grid":
            painter.setPen(QPen(QColor("#000000"), border_width))
            _draw_grid(painter, rect, len(rows), columns, row_height, column_width)
        elif style.border_mode == "color_table":
            if style.header_rule_only:
                painter.setPen(QPen(accent, outer_width))
                painter.drawLine(rect.topLeft(), rect.topRight())
                painter.drawLine(rect.bottomLeft(), rect.bottomRight())
                painter.setPen(QPen(accent, header_width))
                painter.drawLine(
                    rect.left(), rect.top() + row_height,
                    rect.right(), rect.top() + row_height,
                )
            else:
                if style.show_horizontal:
                    painter.setPen(QPen(accent, border_width))
                    painter.drawLine(rect.topLeft(), rect.topRight())
                    painter.drawLine(rect.bottomLeft(), rect.bottomRight())
                    painter.setPen(QPen(light, max(0.4, border_width * 0.8)))
                    for row_index in range(1, len(rows)):
                        y = rect.top() + row_index * row_height
                        painter.drawLine(rect.left(), y, rect.right(), y)
                if style.show_vertical:
                    painter.setPen(QPen(accent, border_width))
                    painter.drawLine(rect.topLeft(), rect.bottomLeft())
                    painter.drawLine(rect.topRight(), rect.bottomRight())
                    painter.setPen(QPen(light, max(0.4, border_width * 0.8)))
                    for column_index in range(1, columns):
                        x = rect.left() + column_index * column_width
                        painter.drawLine(x, rect.top(), x, rect.bottom())
        elif style.border_mode == "keep":
            keep_pen = QPen(QColor(_MUTED_TEXT_COLOR), max(0.4, border_width))
            keep_pen.setStyle(Qt.DashLine)
            painter.setPen(keep_pen)
            painter.drawRect(rect)

        for row_index, row in enumerate(rows):
            font = QFont(layout.font)
            font.setBold(
                bool(layout.font.bold())
                or (
                    row_index == 0
                    and (style.first_row_bold or (style.border_mode == "color_table" and style.header_fill))
                )
            )
            painter.setFont(font)
            painter.setPen(
                _hex_color(style.header_text_color, "#FFFFFF")
                if row_index == 0 and style.border_mode == "color_table" and style.header_fill
                else QColor(_TEXT_COLOR)
            )
            for column_index, value in enumerate(row):
                cell = QRectF(
                    rect.left() + column_index * column_width + 5.0,
                    rect.top() + row_index * row_height,
                    max(1.0, column_width - 10.0),
                    row_height,
                )
                painter.drawText(
                    cell,
                    _alignment_flags(style.cell_alignment) | Qt.AlignVCenter,
                    value,
                )

    def _draw_toc(
        self,
        painter: QPainter,
        layout: PreviewBlockLayout,
    ) -> None:
        title_metrics = QFontMetricsF(layout.font)
        title_height = title_metrics.height() * 1.25
        title_rect = QRectF(
            layout.rect.left(),
            layout.rect.top(),
            layout.rect.width(),
            title_height,
        )
        painter.setFont(layout.font)
        painter.setPen(QColor(_TEXT_COLOR))
        painter.drawText(title_rect, Qt.AlignHCenter | Qt.AlignVCenter, layout.text)

        y = title_rect.bottom() + 4.0
        for row_index, (title, page_number, *rest) in enumerate(layout.block.rows):
            row_style = (
                layout.block.row_styles[row_index]
                if row_index < len(layout.block.row_styles)
                else layout.block.detail_style
            )
            row_font = (
                _preview_font(row_style, layout.pt_scale)
                if row_style is not None
                else layout.detail_font
            )
            painter.setFont(row_font)
            metrics = QFontMetricsF(row_font)
            before = max(0.0, float(getattr(row_style, "space_before_pt", 0.0))) * layout.pt_scale
            after = max(0.0, float(getattr(row_style, "space_after_pt", 0.0))) * layout.pt_scale
            y += before
            row_height = metrics.height() * 1.25
            row = QRectF(layout.rect.left(), y, layout.rect.width(), row_height)
            try:
                level = max(1, int(rest[0])) if rest else 1
            except (TypeError, ValueError):
                level = 1
            left_indent = max(0.0, float(getattr(row_style, "left_indent_pt", 0.0)))
            first_indent = max(0.0, float(getattr(row_style, "first_indent_pt", 0.0)))
            hanging_indent = max(0.0, float(getattr(row_style, "hanging_indent_pt", 0.0)))
            has_configured_indent = any(
                value > 0.0 for value in (left_indent, first_indent, hanging_indent)
            )
            configured_indent = max(
                0.0,
                left_indent + first_indent - hanging_indent,
            ) * layout.pt_scale
            fallback_indent = (level - 1) * metrics.horizontalAdvance("　")
            indent = min(
                row.width() * 0.24,
                configured_indent if has_configured_indent else fallback_indent,
            )
            row = row.adjusted(indent, 0.0, 0.0, 0.0)
            page_width = metrics.horizontalAdvance(page_number) + 4.0
            title_width = min(
                row.width() * 0.72,
                metrics.horizontalAdvance(title) + 4.0,
            )
            painter.drawText(
                QRectF(row.left(), row.top(), title_width, row.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                title,
            )
            painter.drawText(
                QRectF(row.right() - page_width, row.top(), page_width, row.height()),
                Qt.AlignRight | Qt.AlignVCenter,
                page_number,
            )
            dot_pen = QPen(QColor(_PAGE_BORDER), 0.8)
            dot_pen.setStyle(Qt.DotLine)
            painter.setPen(dot_pen)
            painter.drawLine(
                row.left() + title_width + 4.0,
                row.center().y(),
                row.right() - page_width - 4.0,
                row.center().y(),
            )
            painter.setPen(QColor(_TEXT_COLOR))
            y += row_height + after


def _alignment_flags(value: str | None):
    normalized = str(value or "left").strip().lower()
    if normalized == "center":
        return Qt.AlignHCenter
    if normalized == "right":
        return Qt.AlignRight
    if normalized == "justify":
        return Qt.AlignJustify
    return Qt.AlignLeft


def _aligned_table_rect(
    rect: QRectF,
    alignment: str,
    layout_mode: str,
) -> QRectF:
    width = rect.width()
    if layout_mode == "compact":
        width *= 0.68
    elif layout_mode == "smart" and width > 280.0:
        width *= 0.82
    if alignment == "left":
        x = rect.left()
    elif alignment == "right":
        x = rect.right() - width
    else:
        x = rect.center().x() - width / 2.0
    return QRectF(x, rect.top(), width, rect.height())


def _hex_color(value: str, fallback: str) -> QColor:
    raw = str(value or "").strip()
    color = QColor(raw if raw.startswith("#") else f"#{raw}")
    return color if color.isValid() else QColor(fallback)


def _preview_font(style, pt_scale: float) -> QFont:
    font = QFont()
    families = [
        name
        for name in (
            getattr(style, "font_en", ""),
            getattr(style, "font_cn", ""),
        )
        if name
    ]
    try:
        font.setFamilies(families or ["宋体"])
    except AttributeError:
        font.setFamily((families or ["宋体"])[-1])
    font.setPixelSize(
        max(4, int(round(float(getattr(style, "size_pt", 11.0) or 11.0) * pt_scale)))
    )
    font.setBold(bool(getattr(style, "bold", False)))
    font.setItalic(bool(getattr(style, "italic", False)))
    return font


def _draw_grid(
    painter: QPainter,
    rect: QRectF,
    rows: int,
    columns: int,
    row_height: float,
    column_width: float,
) -> None:
    painter.drawRect(rect)
    for row_index in range(1, rows):
        y = rect.top() + row_index * row_height
        painter.drawLine(rect.left(), y, rect.right(), y)
    for column_index in range(1, columns):
        x = rect.left() + column_index * column_width
        painter.drawLine(x, rect.top(), x, rect.bottom())


def _wrap_text(
    metrics: QFontMetricsF,
    text: str,
    first_width: float,
    later_width: float,
) -> list[str]:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return [""]
    lines: list[str] = []
    current = ""
    current_width = 0.0
    limit = max(8.0, first_width)
    for character in cleaned:
        width = metrics.horizontalAdvance(character)
        if current and current_width + width > limit:
            lines.append(current.rstrip())
            current = "" if character.isspace() else character
            current_width = 0.0 if character.isspace() else width
            limit = max(8.0, later_width)
        else:
            current += character
            current_width += width
    if current:
        lines.append(current.rstrip())
    return lines or [cleaned]


__all__ = ["TemplateStylePreview"]
