from __future__ import annotations

from src.qt_api import QLabel
from src.shared.ui.card import Card

from .state import StrategySummaryState


class StrategyCard(Card):
    _SOURCE_TYPE_LABELS = {
        "default": "默认",
        "template": "模板",
        "scene": "场景",
    }

    def __init__(self, parent=None):
        super().__init__("执行策略", parent=parent)
        self._name_value = QLabel()
        self._template_value = QLabel()
        self._scene_value = QLabel()
        self._modules_value = QLabel()
        self._source_value = QLabel()
        self._strict_mode_value = QLabel()
        for widget in (
            self._name_value,
            self._template_value,
            self._scene_value,
            self._modules_value,
            self._source_value,
            self._strict_mode_value,
        ):
            self.add_widget(widget)
        self.set_state(StrategySummaryState())

    def set_state(self, state: StrategySummaryState) -> None:
        self._name_value.setText(f"策略: {state.name}")
        self._template_value.setText(f"模板: {state.template_label}")
        self._scene_value.setText(f"场景: {state.scene_label}")
        self._modules_value.setText(f"模块数: {state.enabled_module_count}")
        source_text = self._SOURCE_TYPE_LABELS.get(state.source_type, "自定义")
        self._source_value.setText(f"来源: {source_text}")
        if state.source_type != "scene":
            strict_text = "未适用"
        else:
            strict_text = "是" if state.strict_mode else "否"
        self._strict_mode_value.setText(f"严格模式: {strict_text}")
