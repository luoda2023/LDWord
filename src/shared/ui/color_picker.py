"""
Color picker with tokenized swatch styling.
"""

from __future__ import annotations

from src.qt_api import QColor, QColorDialog, QHBoxLayout, QPushButton, QWidget, Signal, Qt

from src.shared.ui.theme import bind_theme, get_theme


COLOR_DIALOG_TITLE = "选择颜色"


class ColorPicker(QWidget):
    """Color picker with a themed swatch button."""

    color_changed = Signal(str)

    def __init__(self, *, initial: str = "#000000", parent=None):
        super().__init__(parent)
        self._color = initial

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().spacing_xs)

        self._swatch = QPushButton()
        self._swatch.setCursor(Qt.PointingHandCursor)
        self._swatch.clicked.connect(self._pick)
        layout.addWidget(self._swatch)
        layout.addStretch()

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @staticmethod
    def build_swatch_stylesheet(color: str, theme) -> str:
        return (
            f"background: {color}; border: 1px solid {theme.border}; "
            f"border-radius: {theme.radius_sm}px;"
        )

    def _apply_theme(self) -> None:
        t = get_theme()
        self.layout().setSpacing(t.spacing_xs)
        self._swatch.setFixedSize(t.color_picker_swatch_size, t.color_picker_swatch_size)
        self._swatch.setStyleSheet(self.build_swatch_stylesheet(self._color, t))
        self.setFixedHeight(t.color_picker_height)

    def _pick(self):
        color = QColorDialog.getColor(QColor(self._color), self, COLOR_DIALOG_TITLE)
        if color.isValid():
            self._color = color.name()
            self._apply_theme()
            self.color_changed.emit(self._color)

    def color(self) -> str:
        return self._color

    def set_color(self, hex_color: str):
        self._color = hex_color
        self._apply_theme()
