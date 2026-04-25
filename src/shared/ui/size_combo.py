"""Editable size combo for Chinese named sizes and pt values."""

from __future__ import annotations

from src.qt_api import QAbstractItemView, Qt, Signal

from src.config.style_semantics import (
    NUMERIC_FONT_SIZE_OPTIONS,
    WORD_NAMED_FONT_SIZES,
    font_size_display_text,
    normalize_font_size_token,
    parse_font_size_input,
)
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox


class SizeCombo(StyledComboBox):
    """Editable size combo that understands named sizes like `小四`."""

    _SECTION_ROLE = Qt.UserRole + 1
    _CUSTOM_ITEM_ROLE = Qt.UserRole + 2
    _SECTION_NAMED = "named"
    _SECTION_NUMERIC = "numeric"

    size_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(self.InsertPolicy.NoInsert)
        self.setSizeAdjustPolicy(self.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(4)
        self.setMaxVisibleItems(16)
        apply_size_class(self, "md")
        self.setMinimumWidth(100)
        self.setToolTip("支持中文字号和磅值，例如小四、五号、12、10.5、12磅。")

        for name, pt in WORD_NAMED_FONT_SIZES:
            self.add_size_item(
                f"{name} ({font_size_display_text(pt)}磅)",
                pt,
                section=self._SECTION_NAMED,
            )
        self.insertSeparator(self.count())
        for pt in NUMERIC_FONT_SIZE_OPTIONS:
            self.add_size_item(font_size_display_text(pt), pt, section=self._SECTION_NUMERIC)

        self.currentIndexChanged.connect(self._on_change)
        self.currentTextChanged.connect(self._on_text_change)

        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("如小四或12磅")
            line_edit.setToolTip("可输入中文字号名，或直接输入磅值。")

    def add_size_item(self, text: str, pt: float, *, section: str) -> None:
        self.addItem(text, pt)
        self.setItemData(self.count() - 1, section, self._SECTION_ROLE)

    def _on_change(self, _index: int) -> None:
        pt = self.current_pt()
        if pt is not None:
            self.size_changed.emit(pt)

    def _on_text_change(self, _text: str) -> None:
        pt = self.current_pt()
        if pt is not None:
            self.size_changed.emit(pt)

    def showPopup(self):
        index = self._find_popup_target_index()
        super().showPopup()
        if index >= 0:
            model_index = self.model().index(index, 0)
            self.view().setCurrentIndex(model_index)
            self.view().scrollTo(model_index, QAbstractItemView.PositionAtCenter)

    def _find_popup_target_index(self) -> int:
        self._clear_custom_font_size_item()
        text = self.currentText().strip()
        if not text:
            return self.currentIndex()

        target_section = (
            self._SECTION_NAMED
            if self._looks_like_named_size_input(text)
            else self._SECTION_NUMERIC
        )

        exact_index = self._find_exact_index(text, target_section)
        if exact_index >= 0:
            return exact_index

        try:
            target_value = parse_font_size_input(text)
        except ValueError:
            return self.currentIndex()

        value_index = self._find_value_index(target_value, target_section)
        if value_index >= 0:
            return value_index

        if target_section == self._SECTION_NUMERIC:
            return self._insert_custom_numeric_value(target_value)

        return self.currentIndex()

    def _looks_like_named_size_input(self, text: str) -> bool:
        token = normalize_font_size_token(text)
        if not token:
            return False
        return not token[:1].isdigit() and token[:1] not in {"+", "-", "."}

    def _find_exact_index(self, text: str, section: str) -> int:
        normalized_text = text.strip()
        for index in self._font_size_indices(section):
            if self.itemText(index).strip() == normalized_text:
                return index
        return -1

    def _font_size_indices(self, section: str) -> list[int]:
        indices: list[int] = []
        for index in range(self.count()):
            if self.itemData(index, self._SECTION_ROLE) == section:
                indices.append(index)
        return indices

    def _find_value_index(self, target_value: float, section: str) -> int:
        for index in self._font_size_indices(section):
            item_value = self.itemData(index)
            if item_value is None:
                continue
            if abs(float(item_value) - float(target_value)) < 0.01:
                return index
        return -1

    def _clear_custom_font_size_item(self) -> None:
        for index in range(self.count() - 1, -1, -1):
            if self.itemData(index, self._CUSTOM_ITEM_ROLE):
                self.removeItem(index)

    def _insert_custom_numeric_value(self, value: float) -> int:
        numeric_indices = self._font_size_indices(self._SECTION_NUMERIC)
        if not numeric_indices:
            self.add_size_item(font_size_display_text(value), value, section=self._SECTION_NUMERIC)
            index = self.count() - 1
            self.setItemData(index, True, self._CUSTOM_ITEM_ROLE)
            return index

        insert_index = numeric_indices[-1] + 1
        for index in numeric_indices:
            item_value = self.itemData(index)
            if item_value is None:
                continue
            if float(value) < float(item_value):
                insert_index = index
                break

        self.insertItem(insert_index, font_size_display_text(value), value)
        self.setItemData(insert_index, self._SECTION_NUMERIC, self._SECTION_ROLE)
        self.setItemData(insert_index, True, self._CUSTOM_ITEM_ROLE)
        return insert_index

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
