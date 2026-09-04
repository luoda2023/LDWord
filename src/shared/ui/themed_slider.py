from __future__ import annotations

from src.qt_api import QAbstractSlider, QBrush, QColor, QPainter, QPen, QRectF, QSize, Qt

from src.shared.ui.selection_control_metrics import build_slider_metrics
from src.shared.ui.selection_control_painter import draw_focus_ring
from src.shared.ui.theme import bind_theme, get_theme


class ThemedSlider(QAbstractSlider):
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(parent)
        self.setOrientation(orientation)
        self.setRange(0, 100)
        self.setSingleStep(1)
        self.setPageStep(10)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self._hovered = False
        self._pressed = False
        bind_theme(self, self.update)

    def sizeHint(self) -> QSize:
        metrics = build_slider_metrics(get_theme())
        height = int(metrics.handle_diameter + metrics.hit_extra_radius * 2)
        return QSize(160, max(32, height))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _track_rect(self) -> QRectF:
        metrics = build_slider_metrics(get_theme())
        y = (self.height() - metrics.track_height) / 2.0
        margin = metrics.handle_diameter / 2.0 + self._endpoint_inset(metrics)
        return QRectF(margin, y, max(1.0, self.width() - margin * 2.0), metrics.track_height)

    @staticmethod
    def _endpoint_inset(metrics) -> float:
        return max(2.0, metrics.handle_ring_width + 1.0, metrics.focus_ring_width)

    def _handle_rect_for_value(self, value: int) -> QRectF:
        metrics = build_slider_metrics(get_theme())
        track = self._track_rect()
        span = max(1, self.maximum() - self.minimum())
        ratio = (value - self.minimum()) / span
        center_x = track.left() + track.width() * ratio
        top = (self.height() - metrics.handle_diameter) / 2.0
        half = metrics.handle_diameter / 2.0
        return QRectF(center_x - half, top, metrics.handle_diameter, metrics.handle_diameter)

    def _value_from_pos(self, x: float) -> int:
        track = self._track_rect()
        if track.width() <= 0:
            return self.minimum()
        ratio = min(1.0, max(0.0, (x - track.left()) / track.width()))
        return int(round(self.minimum() + ratio * (self.maximum() - self.minimum())))

    def _focus_ring_color(self) -> QColor:
        color = QColor(get_theme().slider_focus_ring_color)
        color.setAlpha(96)
        return color

    def _focus_ring_rect_for_handle(self, handle: QRectF) -> QRectF:
        metrics = build_slider_metrics(get_theme())
        pen_half = metrics.focus_ring_width / 2.0
        base_expansion = metrics.focus_ring_width + 0.5
        expansion = min(
            base_expansion,
            handle.left(),
            max(0.0, self.width() - handle.right()),
            handle.top(),
            max(0.0, self.height() - handle.bottom()),
        )
        expansion = max(0.0, expansion)
        delta = pen_half - expansion
        return handle.adjusted(delta, delta, -delta, -delta)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        self._pressed = True
        self.setSliderDown(True)
        self.setValue(self._value_from_pos(event.position().x()))
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self.isSliderDown():
            self.setValue(self._value_from_pos(event.position().x()))
            self.sliderMoved.emit(self.value())
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.isSliderDown() and event.button() == Qt.LeftButton:
            self._pressed = False
            self.setSliderDown(False)
            self.update()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Right:
            self.setValue(min(self.maximum(), self.value() + self.singleStep()))
            return
        if event.key() == Qt.Key_Left:
            self.setValue(max(self.minimum(), self.value() - self.singleStep()))
            return
        super().keyPressEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        theme = get_theme()
        metrics = build_slider_metrics(theme)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        track = self._track_rect()
        handle = self._handle_rect_for_value(self.value())
        active = QRectF(
            track.left(),
            track.top(),
            max(0.0, handle.center().x() - track.left()),
            track.height(),
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(theme.slider_inactive_track_color)))
        painter.drawRoundedRect(track, track.height() / 2.0, track.height() / 2.0)
        painter.setBrush(QBrush(QColor(theme.slider_active_track_color)))
        painter.drawRoundedRect(active, track.height() / 2.0, track.height() / 2.0)

        if self.hasFocus():
            draw_focus_ring(
                painter,
                self._focus_ring_rect_for_handle(handle),
                color=self._focus_ring_color(),
                width=metrics.focus_ring_width,
            )

        border = theme.slider_handle_border_color
        if self._hovered:
            border = theme.slider_handle_hover_border_color
        if self._pressed:
            border = theme.slider_handle_pressed_border_color

        painter.setPen(QPen(QColor(border), metrics.handle_ring_width))
        painter.setBrush(
            QBrush(
                QColor(
                    theme.slider_handle_color
                    if self.isEnabled()
                    else theme.slider_handle_disabled_color
                )
            )
        )
        painter.drawEllipse(handle)
