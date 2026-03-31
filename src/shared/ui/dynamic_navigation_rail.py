"""Shared dynamic navigation rail primitive."""

from __future__ import annotations

from src.qt_api import QVBoxLayout, QWidget, Signal

from src.shared.ui.navigation_card import NavigationCard
from src.shared.ui.theme import bind_theme, get_theme


class DynamicNavigationRail(QWidget):
    """Vertical navigation container with dynamic entries."""

    card_selected = Signal(str)

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

    def add_card(self, card_id: str, card: NavigationCard) -> None:
        if card_id in self._cards:
            raise ValueError(f"duplicate card_id: {card_id}")
        if card.key != card_id:
            raise ValueError("card.key must match card_id")
        card.setParent(self)
        card.clicked.connect(lambda: self.select_card(card_id))
        self._cards[card_id] = card
        self._layout.insertWidget(self._layout.count() - 1, card)
        if self._selected_key is None:
            self.select_card(card_id)

    def remove_card(self, card_id: str) -> None:
        card = self._cards.pop(card_id, None)
        if card is None:
            return
        card.setParent(None)
        card.deleteLater()
        if self._selected_key == card_id:
            self._selected_key = None
            if self._cards:
                first_key = next(iter(self._cards))
                self.select_card(first_key)

    def select_card(self, card_id: str) -> None:
        if card_id not in self._cards:
            return
        self._selected_key = card_id
        for card_key, card in self._cards.items():
            card.set_selected(card_key == card_id)
        self.card_selected.emit(card_id)

    def selected_card_id(self) -> str | None:
        return self._selected_key

    @property
    def selected_card(self) -> NavigationCard | None:
        if self._selected_key is None:
            return None
        return self._cards.get(self._selected_key)

    @property
    def item_count(self) -> int:
        return len(self._cards)

    # Backward-compatible aliases.
    def add_item(self, key: str, title: str) -> NavigationCard:
        card = NavigationCard(key, title, parent=self)
        self.add_card(key, card)
        return card

    def remove_item(self, key: str) -> None:
        self.remove_card(key)

    def select_item(self, key: str) -> None:
        self.select_card(key)

    @property
    def selected_key(self) -> str | None:
        return self.selected_card_id()
