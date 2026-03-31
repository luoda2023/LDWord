"""Shared navigation card primitive."""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QVBoxLayout, Qt, Signal

from src.shared.ui.badge import Badge
from src.shared.ui.card import Card
from src.shared.ui.theme import bind_theme, get_theme


class NavigationCard(Card):
    """Selectable card used by navigation rail."""

    clicked = Signal()

    def __init__(self, key: str, title: str, *, badge: Badge | None = None, parent=None):
        super().__init__(parent=parent)
        self._key = key
        self._selected = False
        self._title = QLabel(title)
        self._subtitle = QLabel("")
        self._badge = badge or Badge("")

        row = QHBoxLayout()
        labels = QVBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.addWidget(self._title)
        labels.addWidget(self._subtitle)
        row.addLayout(labels, 1)
        row.addWidget(self._badge, 0, Qt.AlignRight)
        self.add_layout(row)
        self._apply_navigation_theme()
        bind_theme(self, self._apply_navigation_theme)

    def _apply_navigation_theme(self) -> None:
        t = get_theme()
        border = t.primary if self._selected else t.border
        bg = t.bg_selected if self._selected else t.bg_card
        self.setStyleSheet(
            f"""
            NavigationCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: {t.radius_md}px;
            }}
            """
        )
        self._title.setStyleSheet(f"color: {t.text_primary};")
        self._subtitle.setStyleSheet(f"color: {t.text_secondary};")

    def mousePressEvent(self, event):  # noqa: N802
        self.clicked.emit()
        return super().mousePressEvent(event)

    @property
    def key(self) -> str:
        return self._key

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._apply_navigation_theme()

    def is_selected(self) -> bool:
        return self._selected

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)

    def set_badge(self, text: str, variant: str = "neutral") -> None:
        self._badge.set_text(text)
        self._badge.set_variant(variant)
