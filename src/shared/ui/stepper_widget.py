from __future__ import annotations

from src.qt_api import (
    QBrush,
    QColor,
    QConicalGradient,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPen,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
    Qt,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.icons.catalog import get_icon

_PULSE_INTERVAL_MS = 40
_PULSE_STEP = 6  # degrees per tick


class _RunningDot(QWidget):
    """Small pulsing arc indicator for the 'running' stepper state."""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self._color = QColor(color)
        self._angle = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(_PULSE_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._angle = (self._angle + _PULSE_STEP) % 360
        self.update()

    def paintEvent(self, event) -> None:
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r = min(cx, cy) - 3.0

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Track
        track = QColor(self._color)
        track.setAlpha(40)
        painter.setPen(QPen(track, 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        # Spinning arc
        grad = QConicalGradient(cx, cy, self._angle)
        grad.setColorAt(0.0, QColor(self._color.red(), self._color.green(),
                                    self._color.blue(), 0))
        grad.setColorAt(0.5, QColor(self._color.red(), self._color.green(),
                                    self._color.blue(), 200))
        grad.setColorAt(1.0, QColor(self._color.red(), self._color.green(),
                                    self._color.blue(), 255))
        painter.setPen(QPen(QBrush(grad), 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(int(cx - r), int(cy - r), int(r * 2), int(r * 2),
                        int(self._angle * 16), int(270 * 16))

    def stop(self) -> None:
        self._timer.stop()


class StepperItem(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._status = "queued"
        self._progress = 0
        self._running_dot: _RunningDot | None = None
        self.setFixedHeight(get_theme().control_height_md)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(12)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(24, 24)
        self._icon_label.setAlignment(Qt.AlignCenter)

        self._title_label = QLabel(title, self)
        self._detail_label = QLabel("", self)

        layout.addWidget(self._icon_label)
        layout.addWidget(self._title_label)
        layout.addStretch(1)
        layout.addWidget(self._detail_label)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_status(self, status: str, progress: int):
        self._status = status
        self._progress = progress
        self._refresh_ui()

    def _apply_theme(self):
        t = get_theme()
        self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px;")
        self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px;")
        self._refresh_ui()

    def _clear_running_dot(self) -> None:
        if self._running_dot is not None:
            self._running_dot.stop()
            layout = self.layout()
            if layout is not None:
                layout.removeWidget(self._running_dot)
            self._running_dot.deleteLater()
            self._running_dot = None

    def _show_running_dot(self) -> None:
        self._clear_running_dot()
        t = get_theme()
        dot = _RunningDot(t.primary, self)
        self.layout().replaceWidget(self._icon_label, dot)
        self._icon_label.hide()
        dot.show()
        self._running_dot = dot

    def _show_icon(self, name: str, size: int, color: str) -> None:
        self._clear_running_dot()
        self._icon_label.setPixmap(get_icon(name, size=size, color=color).pixmap(24, 24))
        self._icon_label.show()

    def _refresh_ui(self):
        t = get_theme()
        if self._status == "queued":
            self._show_icon("info", 16, t.text_hint)
            self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px; color: {t.text_secondary};")
            self._detail_label.setText("排队中")
            self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_hint};")
        elif self._status == "running":
            self._show_running_dot()
            self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px; font-weight: bold; color: {t.text_primary};")
            self._detail_label.setText(f"执行中 {self._progress}%")
            self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px; font-weight: bold; color: {t.primary};")
        elif self._status == "completed":
            self._show_icon("circle-check", 20, t.success)
            self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px; color: {t.text_primary};")
            self._detail_label.setText("已完成")
            self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.success};")
        elif self._status in ("failed", "error"):
            self._show_icon("circle-x", 20, t.error)
            self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px; color: {t.error};")
            self._detail_label.setText("失败")
            self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.error};")
        else:
            self._show_icon("alert-triangle", 20, t.warning)
            self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px; color: {t.warning};")
            self._detail_label.setText(self._status)
            self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.warning};")

    def get_node_center_y(self) -> int:
        return self.y() + self.height() // 2

    def status(self) -> str:
        return self._status


class StepperWidget(QWidget):
    """Replaces ModuleStatusList with a visual stepper layout."""

    module_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 8, 0, 8)
        self._layout.setSpacing(0)
        self._items: dict[str, StepperItem] = {}
        self._item_keys: list[str] = []
        self._current_module_id = ""

    def add_module(self, module_id: str, title: str) -> None:
        if module_id in self._items:
            item = self._items[module_id]
            item.set_status("queued", 0)
            self._current_module_id = module_id
            return

        item = StepperItem(title, self)
        self._layout.addWidget(item)
        self._items[module_id] = item
        self._item_keys.append(module_id)

        if not self._current_module_id:
            self._current_module_id = module_id

        self.update()

    def update_status(self, module_id: str, status: str, progress: int = 0) -> None:
        if module_id not in self._items:
            return
        item = self._items[module_id]
        item.set_status(status, progress)
        self._current_module_id = module_id
        self.update()

    def current_module_text(self) -> str:
        if not self._current_module_id or self._current_module_id not in self._items:
            return ""
        return self._items[self._current_module_id]._title_label.text()

    def clear(self) -> None:
        for module_id in self._item_keys:
            widget = self._items[module_id]
            self._layout.removeWidget(widget)
            widget.deleteLater()
        self._items.clear()
        self._item_keys.clear()
        self._current_module_id = ""
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if len(self._item_keys) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        t = get_theme()

        x = 20

        for i in range(len(self._item_keys) - 1):
            key_curr = self._item_keys[i]
            key_next = self._item_keys[i + 1]
            item_curr = self._items[key_curr]
            item_next = self._items[key_next]

            y_start = item_curr.get_node_center_y() + 12
            y_end = item_next.get_node_center_y() - 12

            status_curr = item_curr.status()
            if status_curr == "completed":
                color = QColor(t.success)
            elif status_curr in ["running", "failed"]:
                color = QColor(t.text_hint)
                color.setAlphaF(0.4)
            else:
                color = QColor(t.border_light)

            pen = QPen(color, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawLine(x, y_start, x, y_end)
