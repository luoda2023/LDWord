"""
numbering_preset — 编号预设下拉

标题编号/题注前缀预设选择 + 预览。
"""
from __future__ import annotations
from src.qt_api import Signal

from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import get_theme

_PRESETS = {
    "arabic_dot": "1. / 1.1 / 1.1.1",
    "cn_chapter": "第一章 / 第一节 / 1.1.1",
    "cn_paren": "（一）/（二）/（三）",
    "roman": "Ⅰ / Ⅱ / Ⅲ",
    "alpha": "A / B / C",
    "none": "无编号",
}


class NumberingPreset(StyledComboBox):
    """编号预设下拉。"""
    preset_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(get_theme().control_height_md)
        self.setMinimumWidth(180)
        for key, preview in _PRESETS.items():
            self.addItem(f"{preview}", key)
        self.currentIndexChanged.connect(
            lambda _: self.preset_changed.emit(self.current_preset())
        )

    def current_preset(self) -> str:
        return self.currentData() or "arabic_dot"

    def set_preset(self, key: str):
        for i in range(self.count()):
            if self.itemData(i) == key:
                self.setCurrentIndex(i)
                return
