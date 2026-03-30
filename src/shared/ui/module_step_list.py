"""
Module step list.
"""

from __future__ import annotations

from src.qt_api import QCheckBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget, Signal, Qt

from src.shared.ui.theme import bind_theme, get_theme
from src.ui.icons.catalog import get_icon


class ModuleStepItem(QWidget):
    """Single module step row."""

    toggled = Signal(str, bool)

    def __init__(self, name: str, description: str, *, checked: bool = True, parent=None):
        super().__init__(parent)
        self._name = name
        self._status_icon_name = 'square'
        self._status_color_hex = None

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 4)
        self._layout.setSpacing(get_theme().spacing_sm)

        self._cb = QCheckBox()
        self._cb.setChecked(checked)
        self._cb.stateChanged.connect(lambda state: self.toggled.emit(name, state == Qt.Checked))
        self._layout.addWidget(self._cb)

        self._label = QLabel(f'<b>{description}</b>')
        self._layout.addWidget(self._label, 1)

        self._status = QLabel()
        self._layout.addWidget(self._status)

        self.set_status('square', get_theme().text_hint)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setSpacing(t.spacing_sm)
        self._status.setFixedSize(t.module_step_status_size, t.module_step_status_size)
        self._label.setStyleSheet(f'font-size: {t.font_size_md}px; color: {t.text_primary};')
        self.setFixedHeight(t.module_step_item_height)
        self._refresh_status_icon()

    def _refresh_status_icon(self) -> None:
        t = get_theme()
        size = t.module_step_status_size
        color = self._status_color_hex or t.text_primary
        self._status.setPixmap(get_icon(self._status_icon_name, size, color).pixmap(size, size))

    def set_status(self, icon_name: str, color_hex: str = None) -> None:
        self._status_icon_name = icon_name
        self._status_color_hex = color_hex
        self._refresh_status_icon()

    @property
    def module_name(self) -> str:
        return self._name


class ModuleStepList(QScrollArea):
    """Scrollable container of module step items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._layout.addStretch()
        self.setWidget(self._container)
        self._items: dict[str, ModuleStepItem] = {}
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setSpacing(t.spacing_xs // 2)

    def add_module(self, name: str, description: str, *, checked: bool = True):
        item = ModuleStepItem(name, description, checked=checked)
        self._layout.insertWidget(self._layout.count() - 1, item)
        self._items[name] = item

    def set_status(self, name: str, icon_name: str, color_hex: str = None) -> None:
        if name in self._items:
            self._items[name].set_status(icon_name, color_hex)
