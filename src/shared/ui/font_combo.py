"""
font_combo — 字体选择器

系统字体枚举 + 中英分组 + 预览。
"""

from __future__ import annotations

from src.qt_api import Signal

from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import get_theme
# 预定义中英文常用字体
_CN_FONTS = ["宋体", "黑体", "仿宋", "楷体", "微软雅黑", "华文中宋", "华文楷体"]
_EN_FONTS = ["Times New Roman", "Arial", "Calibri", "Courier New", "Cambria"]


class FontCombo(StyledComboBox):
    """字体选择器。

    Signals:
        font_changed(str): 字体选择变化
    """

    font_changed = Signal(str)

    def __init__(self, *, lang: str = "cn", parent=None):
        super().__init__(parent)
        self._lang = lang
        self.setMinimumWidth(160)
        self.setFixedHeight(get_theme().control_height_md)
        self._populate()
        self.currentTextChanged.connect(self.font_changed.emit)

    def _populate(self) -> None:
        fonts = _CN_FONTS if self._lang == "cn" else _EN_FONTS
        self.addItems(fonts)

    def selected_font(self) -> str:
        return self.currentText()

    def set_font_name(self, name: str) -> None:
        idx = self.findText(name)
        if idx >= 0:
            self.setCurrentIndex(idx)
