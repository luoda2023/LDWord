from __future__ import annotations

from src.qt_api import QLabel, QPushButton, Signal
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import get_theme
from src.shared.ui.surface_card import SurfaceCard


class HeadingQuickCard(SurfaceCard):
    advanced_requested = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__("标题编号", parent=parent)
        self._bridge = bridge
        self._summary_label = QLabel("标题方案：未读取")
        self._summary_label.setObjectName("wb_quick_card_summary")
        self._advanced_btn = QPushButton("高级配置")
        self._advanced_btn.setObjectName("wb_quick_card_action")
        apply_button_variant(self._advanced_btn, "secondary")
        apply_size_class(self._advanced_btn, "md")
        self._advanced_btn.setStyleSheet(build_button_stylesheet(get_theme()))
        self._advanced_btn.clicked.connect(self.advanced_requested.emit)
        self.add_widget(self._summary_label)
        self.add_widget(self._advanced_btn)

    def set_summary_text(self, text: str) -> None:
        self._summary_label.setText(text)
