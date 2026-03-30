from __future__ import annotations

from src.qt_api import QAbstractButton, QPainter, QRectF, QSize, Qt

from src.shared.ui.selection_control_metrics import build_radio_metrics
from src.shared.ui.selection_control_painter import draw_focus_ring, draw_radio_indicator
from src.shared.ui.theme import bind_theme, get_theme


class ThemedRadioButton(QAbstractButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False
        bind_theme(self, self.update)

    def sizeHint(self) -> QSize:
        metrics = build_radio_metrics(get_theme())
        fm = self.fontMetrics()
        width = int(
            metrics.hit_padding_x * 2
            + metrics.indicator_diameter
            + metrics.label_gap
            + max(0, fm.horizontalAdvance(self.text()))
        )
        height = int(max(metrics.indicator_diameter, fm.height()) + metrics.hit_padding_y * 2)
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _indicator_rect(self) -> QRectF:
        metrics = build_radio_metrics(get_theme())
        top = (self.height() - metrics.indicator_diameter) / 2.0
        return QRectF(
            float(metrics.hit_padding_x),
            top,
            metrics.indicator_diameter,
            metrics.indicator_diameter,
        )

    def paintEvent(self, event) -> None:
        theme = get_theme()
        metrics = build_radio_metrics(theme)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        indicator = self._indicator_rect()
        if self.hasFocus():
            draw_focus_ring(
                painter,
                indicator.adjusted(-3, -3, 3, 3),
                color=theme.radio_focus_ring_color,
                width=metrics.focus_ring_width,
            )

        ring_color = theme.radio_color_ring_disabled if not self.isEnabled() else theme.radio_color_ring
        if self.isEnabled() and self._hovered:
            ring_color = theme.radio_color_ring_hover
        if self.isChecked():
            ring_color = (
                theme.radio_color_ring_checked if self.isEnabled() else theme.radio_color_ring_disabled
            )

        bg_color = theme.radio_color_bg if self.isEnabled() else theme.radio_color_bg_disabled
        dot_color = None
        if self.isChecked():
            dot_color = theme.radio_color_dot if self.isEnabled() else theme.radio_color_dot_disabled

        draw_radio_indicator(
            painter,
            indicator,
            ring_color=ring_color,
            bg_color=bg_color,
            ring_width=metrics.ring_width,
            dot_color=dot_color,
            dot_diameter=metrics.dot_diameter,
        )

        text_left = int(indicator.right() + metrics.label_gap)
        text_rect = self.rect().adjusted(text_left, 0, 0, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)
