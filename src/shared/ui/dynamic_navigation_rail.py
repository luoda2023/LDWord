"""Shared dynamic navigation rail primitive."""

from __future__ import annotations

from src.qt_api import QVBoxLayout, QWidget, Signal

from src.shared.ui.navigation_card import NavigationCard
from src.shared.ui.theme import bind_theme, get_theme


class DynamicNavigationRail(QWidget):
    """Vertical navigation container with dynamic entries."""

    selection_changed = Signal(str)

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addStretch()
        self._cards: dict[str, NavigationCard] = {}
        self._selected_key: str | None = None
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setSpacing(t.spacing_sm)

    def add_item(self, key: str, title: str) -> NavigationCard:
        card = NavigationCard(key, title, parent=self)
        card.clicked.connect(lambda: self.select_item(key))
        self._cards[key] = card
        self._layout.insertWidget(self._layout.count() - 1, card)
        if self._selected_key is None:
            self.select_item(key)
        return card

    def remove_item(self, key: str) -> None:
        card = self._cards.pop(key, None)
        if card is None:
            return
        card.setParent(None)
        card.deleteLater()
        if self._selected_key == key:
            self._selected_key = None
            if self._cards:
                first_key = next(iter(self._cards))
                self.select_item(first_key)

    def select_item(self, key: str) -> None:
        if key not in self._cards:
            return
        self._selected_key = key
        for card_key, card in self._cards.items():
            card.set_selected(card_key == key)
        self.selection_changed.emit(key)

    @property
    def selected_key(self) -> str | None:
        return self._selected_key

    @property
    def selected_card(self) -> NavigationCard | None:
        if self._selected_key is None:
            return None
        return self._cards.get(self._selected_key)

    @property
    def item_count(self) -> int:
        return len(self._cards)
