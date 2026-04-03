"""Editable size combo for Chinese named sizes and pt values."""

from __future__ import annotations

from src.qt_api import Signal

from src.config.style_semantics import (
    WORD_NAMED_FONT_SIZES,
    font_size_display_text,
    parse_font_size_input,
)
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox


class SizeCombo(StyledComboBox):
    """Editable size combo that understands named sizes like `小四`."""

    size_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        apply_size_class(self, "md")
        self.setMinimumWidth(100)
        self.setToolTip("支持中文字号和磅值，例如小四、五号、12、10.5、12磅。")

        for name, pt in WORD_NAMED_FONT_SIZES:
            self.addItem(f"{name} ({pt}pt)", pt)

        self.currentIndexChanged.connect(self._on_change)
        self.currentTextChanged.connect(self._on_text_change)

        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("如小四或12磅")
            line_edit.setToolTip("可输入中文字号名，或直接输入 pt/磅值。")

    def _on_change(self, _index: int) -> None:
        pt = self.current_pt()
        if pt is not None:
            self.size_changed.emit(pt)

    def _on_text_change(self, _text: str) -> None:
        pt = self.current_pt()
        if pt is not None:
            self.size_changed.emit(pt)

    def current_pt(self) -> float | None:
        try:
            return parse_font_size_input(self.currentText().strip())
        except (TypeError, ValueError):
            data = self.currentData()
            if data is not None:
                return float(data)
            return None

    def set_pt(self, pt: float) -> None:
        for index in range(self.count()):
            if self.itemData(index) == pt:
                self.setCurrentIndex(index)
                return
        self.setEditText(font_size_display_text(pt))
