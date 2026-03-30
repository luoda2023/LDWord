"""
size_combo — 字号选择器

初号~小六 + 自定义 pt 值。
"""

from __future__ import annotations

from src.qt_api import Signal

from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import get_theme

_CN_SIZES = [
    ("初号", 42), ("小初", 36), ("一号", 26), ("小一", 24),
    ("二号", 22), ("小二", 18), ("三号", 16), ("小三", 15),
    ("四号", 14), ("小四", 12), ("五号", 10.5), ("小五", 9),
    ("六号", 7.5), ("小六", 6.5),
]


class SizeCombo(StyledComboBox):
    """字号选择器。

    Signals:
        size_changed(float): 字号 pt 值变化
    """

    size_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setFixedHeight(get_theme().control_height_md)
        self.setMinimumWidth(100)

        for name, pt in _CN_SIZES:
            self.addItem(f"{name} ({pt}pt)", pt)

        self.currentIndexChanged.connect(self._on_change)

    def _on_change(self, _index: int) -> None:
        pt = self.current_pt()
        if pt:
            self.size_changed.emit(pt)

    def current_pt(self) -> float | None:
        data = self.currentData()
        if data is not None:
            return float(data)
        # 尝试从文本解析
        text = self.currentText().strip()
        try:
            return float(text.replace("pt", ""))
        except ValueError:
            return None

    def set_pt(self, pt: float) -> None:
        for i in range(self.count()):
            if self.itemData(i) == pt:
                self.setCurrentIndex(i)
                return
        self.setEditText(f"{pt}pt")
