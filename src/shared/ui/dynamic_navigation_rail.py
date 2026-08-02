"""Shared dynamic navigation rail primitive."""

from __future__ import annotations

from src.qt_api import QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget, Qt, Signal

from src.shared.ui.navigation_card import NavigationCard
from src.shared.ui.theme import bind_theme, get_theme


class DynamicNavigationRail(QWidget):
    """Vertical navigation container with dynamic entries.

    Supports optional section headers to visually separate fixed cards
    from dynamic (feature) cards.
    """

    card_selected = Signal(str)

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)

        self._scroll = QScrollArea(self)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._scroll.setMinimumHeight(0)
        self._scroll.setAttribute(Qt.WA_StyledBackground, True)
        viewport = self._scroll.viewport()
        if viewport is not None:
            viewport.setAttribute(Qt.WA_StyledBackground, True)
            viewport.setAutoFillBackground(False)

        self._content = QWidget(self._scroll)
        self._content.setAttribute(Qt.WA_StyledBackground, True)

        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.addStretch()
        self._scroll.setWidget(self._content)
        self._outer_layout.addWidget(self._scroll)

        self.setMinimumHeight(0)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self._cards: dict[str, NavigationCard] = {}
        self._section_labels: list[QLabel] = []
        self._selected_key: str | None = None
        self._background_color: str | None = None
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        background = self._background_color or t.bg_nav_rail
        self._layout.setSpacing(t.spacing_xs)
        self._content.setStyleSheet(f"background: {background};")
        if self._scroll.viewport() is not None:
            self._scroll.viewport().setStyleSheet(f"background: {background};")
        self._scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background: {background};
                border: none;
            }}
            QScrollBar:vertical {{
                background: {t.scrollbar_track};
                width: 8px;
                border: none;
                margin: 2px 0px 2px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {t.scrollbar_thumb};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t.scrollbar_thumb_hover};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
                background: transparent;
                border: none;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            """
        )
        alive_labels: list[QLabel] = []
        for label in self._section_labels:
            try:
                label.setStyleSheet(
                    f"font-size: {t.font_size_xs}px; "
                    f"color: {t.text_hint}; "
                    f"font-weight: {t.font_weight_emphasis}; "
                    f"padding: {t.spacing_sm}px 4px 2px 4px; "
                    f"letter-spacing: 1px;"
                )
            except RuntimeError:
                continue
            alive_labels.append(label)
        self._section_labels = alive_labels

    def set_background_color(self, color: str | None) -> None:
        """Keep the outer rail, scroll viewport, and content canvas in sync."""
        normalized = str(color or "").strip() or None
        if self._background_color == normalized:
            return
        self._background_color = normalized
        self._apply_theme()

    # ------------------------------------------------------------------
    # Section headers
    # ------------------------------------------------------------------

    def add_section_header(self, text: str) -> QLabel:
        """Insert an uppercase section header above the stretch."""
        label = QLabel(text.upper(), self._content)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._section_labels.append(label)
        self._layout.insertWidget(self._layout.count() - 1, label)
        self._apply_theme()
        return label

    def remove_section_header(self, label: QLabel | None) -> None:
        """Remove a previously-added section header safely."""
        if label is None:
            return
        if label in self._section_labels:
            self._section_labels.remove(label)
        try:
            label.hide()
            label.setParent(None)
            label.deleteLater()
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Card management
    # ------------------------------------------------------------------

    def add_card(self, card_id: str, card: NavigationCard) -> None:
        if card_id in self._cards:
            raise ValueError(f"duplicate card_id: {card_id}")
        if card.key != card_id:
            raise ValueError("card.key must match card_id")
        card.setParent(self._content)
        card.clicked.connect(lambda: self.select_card(card_id))
        self._cards[card_id] = card
        self._layout.insertWidget(self._layout.count() - 1, card)
        if self._selected_key is None:
            self.select_card(card_id)

    def remove_card(self, card_id: str) -> None:
        card = self._cards.pop(card_id, None)
        if card is None:
            return
        card.hide()
        card.setParent(None)
        card.deleteLater()
        if self._selected_key == card_id:
            self._selected_key = None
            if self._cards:
                first_key = next(iter(self._cards))
                self.select_card(first_key)

    def place_cards_after(
        self,
        anchor: QWidget,
        card_ids: list[str] | tuple[str, ...],
    ) -> None:
        """Reorder existing cards after ``anchor`` without recreating them."""

        anchor_index = self._layout.indexOf(anchor)
        if anchor_index < 0:
            raise ValueError("anchor must belong to the navigation rail layout")
        target_index = anchor_index + 1
        for card_id in card_ids:
            card = self._cards.get(card_id)
            if card is None:
                continue
            current_index = self._layout.indexOf(card)
            if current_index != target_index:
                self._layout.removeWidget(card)
                self._layout.insertWidget(target_index, card)
            target_index += 1

    def select_card(self, card_id: str) -> None:
        if card_id not in self._cards:
            return
        self._selected_key = card_id
        for card_key, card in self._cards.items():
            card.set_selected(card_key == card_id)
        selected = self._cards.get(card_id)
        if selected is not None and selected.isVisible():
            self._scroll.ensureWidgetVisible(selected, 0, get_theme().spacing_sm)
        self._content.update()
        viewport = self._scroll.viewport()
        if viewport is not None:
            viewport.update()
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

    # ------------------------------------------------------------------
    # Backward-compatible aliases
    # ------------------------------------------------------------------

    def add_item(
        self,
        key: str,
        title: str,
        *,
        icon_name: str = "",
    ) -> NavigationCard:
        """Create and register a NavigationCard in one call."""
        card = NavigationCard(key, title, icon_name=icon_name, parent=self)
        self.add_card(key, card)
        return card

    def remove_item(self, key: str) -> None:
        self.remove_card(key)

    def select_item(self, key: str) -> None:
        self.select_card(key)

    @property
    def selected_key(self) -> str | None:
        return self.selected_card_id()

    @property
    def scroll_area(self) -> QScrollArea:
        return self._scroll
