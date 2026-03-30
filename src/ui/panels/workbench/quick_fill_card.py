from __future__ import annotations

from src.qt_api import QLabel, QPushButton
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card


class QuickFillCard(Card):
    def __init__(self, bridge, parent=None):
        super().__init__("快捷填充", parent=parent)
        self._bridge = bridge
        self._source_summary = QLabel("填充源：未连接")
        self._entity_summary = QLabel("实体：未选择")
        self._source_summary.setObjectName("wb_quick_card_summary")
        self._entity_summary.setObjectName("wb_quick_card_summary")
        self._quick_setup_btn = QPushButton("快速设置")
        self._quick_setup_btn.setObjectName("wb_quick_card_action")
        self._advanced_mapping_btn = QPushButton("高级映射")
        self._advanced_mapping_btn.setObjectName("wb_quick_card_action_secondary")
        apply_button_variant(self._quick_setup_btn, "secondary")
        apply_button_variant(self._advanced_mapping_btn, "ghost-primary")
        self.add_widget(self._source_summary)
        self.add_widget(self._entity_summary)
        self.add_widget(self._quick_setup_btn)
        self.add_widget(self._advanced_mapping_btn)
