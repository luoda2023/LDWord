from __future__ import annotations

from src.qt_api import (
    QHBoxLayout, QLabel, QPainter, QPen, QColor, QWidget, QVBoxLayout, Signal, Qt
)
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.icons.catalog import get_icon


class StepperItem(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._status = "queued"
        self._progress = 0
        self.setFixedHeight(get_theme().control_height_md)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(12)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(24, 24)
        self._icon_label.setAlignment(Qt.AlignCenter)

        # Title
        self._title_label = QLabel(title, self)

        # Details
        self._detail_label = QLabel("", self)

        # Using stretch to push details to right
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
        self._title_font_size = t.font_size_sm
        self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px;")
        self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px;")
        self._refresh_ui()

    def _refresh_ui(self):
        t = get_theme()
        if self._status == "queued":
            self._icon_label.setPixmap(get_icon("info", size=16, color=t.text_hint).pixmap(24, 24))
            self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px; color: {t.text_secondary};")
            self._detail_label.setText("排队中")
            self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_hint};")
        elif self._status == "running":
            # Just an indicator, the spinner is hard natively, we'll use a filled circle from primary
            self._icon_label.setPixmap(get_icon("play", size=18, color=t.primary).pixmap(24, 24))
            self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px; font-weight: bold; color: {t.text_primary};")
            self._detail_label.setText(f"执行中 {self._progress}%")
            self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px; font-weight: bold; color: {t.primary};")
        elif self._status == "completed":
            self._icon_label.setPixmap(get_icon("circle-check", size=20, color=t.success).pixmap(24, 24))
            self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px; color: {t.text_primary};")
            self._detail_label.setText("已完成")
            self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.success};")
        elif self._status == "failed" or self._status == "error":
            self._icon_label.setPixmap(get_icon("circle-x", size=20, color=t.error).pixmap(24, 24))
            self._title_label.setStyleSheet(f"font-size: {t.font_size_md}px; color: {t.error};")
            self._detail_label.setText("失败")
            self._detail_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.error};")
        else:
            self._icon_label.setPixmap(get_icon("alert-triangle", size=20, color=t.warning).pixmap(24, 24))
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

        self.update() # Trigger paint for lines

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
        # Access protected member directly for simplicity
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

        # Center of the 24x24 icon which has 8px left margin in the QHBoxLayout
        # margin = 8, width = 24 => center is at 8 + 12 = 20
        x = 20

        for i in range(len(self._item_keys) - 1):
            key_curr = self._item_keys[i]
            key_next = self._item_keys[i + 1]
            item_curr = self._items[key_curr]
            item_next = self._items[key_next]

            y_start = item_curr.get_node_center_y() + 12
            y_end = item_next.get_node_center_y() - 12

            # Determine line color
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
