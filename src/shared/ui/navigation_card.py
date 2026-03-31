"""Shared navigation card primitive."""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, Qt, Signal

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
        self._badge = badge

        row = QHBoxLayout()
        row.addWidget(self._title, 1)
        if self._badge is not None:
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
