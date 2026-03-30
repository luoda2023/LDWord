"""
Placeholder editor with shared input styling.
"""

from __future__ import annotations

from src.qt_api import QLineEdit, Signal

from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.theme import bind_theme, get_theme


DEFAULT_PLACEHOLDER_TEMPLATE = "{{占位符}}"


class PlaceholderEdit(QLineEdit):
    """Line edit specialized for placeholder templates."""

    placeholder_changed = Signal(str)

    def __init__(self, *, placeholder: str = DEFAULT_PLACEHOLDER_TEMPLATE, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(get_theme().control_height_md)
        self.textChanged.connect(self.placeholder_changed.emit)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(
            build_text_input_stylesheet(
                t,
                font_family="Consolas, monospace",
            )
        )

    def value(self) -> str:
        return self.text()

    def set_value(self, text: str):
        self.setText(text)
