"""
Standard form row widget.
"""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QSizePolicy, QWidget, Qt

from src.shared.ui.theme import bind_theme, get_theme


class FormRow(QWidget):
    """Label + control + optional suffix row."""

    def __init__(
        self,
        label: str,
        widget: QWidget,
        *,
        suffix_widget: QWidget | None = None,
        label_width: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._label_width = label_width

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(8)

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._layout.addWidget(self._label)

        self._widget = widget
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._layout.addWidget(widget, 1)

        self._suffix = suffix_widget
        if suffix_widget:
            self._layout.addWidget(suffix_widget)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._label.setFixedWidth(self._label_width or t.form_row_label_width)
        self.setFixedHeight(t.form_row_height + 8)
        self._label.setStyleSheet(f'font-size: {t.font_size_md}px; color: {t.text_primary};')

    @property
    def widget(self) -> QWidget:
        return self._widget

    @property
    def label_text(self) -> str:
        return self._label.text()

    def set_label(self, text: str) -> None:
        self._label.setText(text)
