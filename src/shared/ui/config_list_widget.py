from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, Signal

from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.search_input import SearchInput
from src.shared.ui.theme import bind_theme, get_theme


class _ConfigItemCard(Card):
    def __init__(self, config_id: str, name: str, description: str, updated_at: str, parent=None):
        super().__init__(parent=parent)
        self.config_id = config_id
        self.name = str(name or "")
        self.description = str(description or "")
        self.updated_at = str(updated_at or "")

        self._name_label = QLabel(self.name, self)
        self._desc_label = QLabel(self.description, self)
        self._desc_label.setWordWrap(True)
        self._time_label = QLabel(self.updated_at, self)
        self._time_label.setObjectName("config_list_time")

        self._load_button = QPushButton("\u52a0\u8f7d", self)
        self._delete_button = QPushButton("\u5220\u9664", self)
        apply_button_variant(self._load_button, "secondary")
        apply_button_variant(self._delete_button, "ghost-danger")

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.addWidget(self._load_button)
        action_row.addWidget(self._delete_button)
        action_row.addStretch(1)

        self.add_widget(self._name_label)
        if self.description:
            self.add_widget(self._desc_label)
        self.add_widget(self._time_label)
        self.add_layout(action_row)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def matches(self, query: str) -> bool:
        needle = str(query or "").strip().lower()
        if not needle:
            return True
        haystack = " ".join([self.name, self.description, self.updated_at]).lower()
        return needle in haystack

    def _apply_theme(self) -> None:
        super()._apply_theme()
        if not hasattr(self, "_name_label"):
            return
        t = get_theme()
        self._name_label.setStyleSheet(
            f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_bold}; color: {t.text_primary};"
        )
        self._desc_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._time_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )


class ConfigListWidget(QWidget):
    config_loaded = Signal(str)
    config_deleted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, _ConfigItemCard] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._search = SearchInput("\u641c\u7d22\u914d\u7f6e...", self)
        layout.addWidget(self._search)

        self._list_container = QWidget(self)
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(10)
        layout.addWidget(self._list_container)
        layout.addStretch(1)

        self._search.search_changed.connect(self._apply_filter)
        self._search.search_submitted.connect(self._apply_filter)

    def add_config(self, config_id: str, name: str, description: str, updated_at: str) -> None:
        card = self._cards.get(config_id)
        if card is not None:
            self.remove_config(config_id)

        card = _ConfigItemCard(config_id, name, description, updated_at, parent=self._list_container)
        card._load_button.clicked.connect(lambda: self.config_loaded.emit(config_id))
        card._delete_button.clicked.connect(lambda: self.config_deleted.emit(config_id))
        self._cards[config_id] = card
        self._list_layout.addWidget(card)
        self._apply_filter(self._search.text)

    def remove_config(self, config_id: str) -> None:
        card = self._cards.pop(config_id, None)
        if card is None:
            return
        self._list_layout.removeWidget(card)
        card.deleteLater()

    def clear_configs(self) -> None:
        for config_id in list(self._cards):
            self.remove_config(config_id)

    def config_count(self) -> int:
        return len(self._cards)

    def config_name(self, config_id: str) -> str:
        card = self._cards.get(config_id)
        if card is None:
            return ""
        return card.name

    def _apply_filter(self, query: str) -> None:
        for card in self._cards.values():
            card.setVisible(card.matches(query))
