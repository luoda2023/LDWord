"""
Card container widget.
"""

from __future__ import annotations

from src.qt_api import QColor, QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget
from src.shared.ui.theme import bind_theme, get_theme


class Card(QFrame):
    """Card container with optional title and separator."""

    def __init__(self, title: str = '', *, parent=None):
        super().__init__(parent)

        self._layout = QVBoxLayout(self)
        self._shadow = QGraphicsDropShadowEffect(self)
        self.setGraphicsEffect(self._shadow)

        self._title_label = None
        self._sep = None
        if title:
            self._title_label = QLabel(title)
            self._layout.addWidget(self._title_label)
            self._sep = QFrame()
            self._sep.setFrameShape(QFrame.HLine)
            self._layout.addWidget(self._sep)

        self._content_layout = QVBoxLayout()
        self._layout.addLayout(self._content_layout)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setContentsMargins(t.card_padding_x, t.card_padding_top, t.card_padding_x, t.card_padding_bottom)
        self._layout.setSpacing(t.card_spacing)
        self._content_layout.setSpacing(t.card_content_spacing)

        self.setStyleSheet(
            f"""
            Card {{
                background: {t.bg_card};
                border-radius: {t.radius_md}px;
                border: 1px solid {t.border};
            }}
            """
        )
        self._shadow.setBlurRadius(t.shadow_blur_md)
        self._shadow.setColor(QColor(0, 0, 0, 15))
        self._shadow.setOffset(0, t.shadow_offset_y)

        if self._title_label:
            self._title_label.setStyleSheet(
                f'font-size: {t.font_size_xl}px; font-weight: bold; color: {t.text_primary};'
            )
        if self._sep:
            self._sep.setStyleSheet(f'background: {t.border_light}; max-height: 1px;')

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._content_layout.addLayout(layout)
