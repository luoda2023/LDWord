from __future__ import annotations

from PySide6.QtWidgets import QGridLayout
from src.qt_api import QWidget


class CapabilityGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)

    def add_card(self, widget: QWidget, row: int, column: int) -> None:
        self._layout.addWidget(widget, row, column)

    def card_at(self, row: int, column: int) -> QWidget | None:
        item = self._layout.itemAtPosition(row, column)
        return item.widget() if item else None
