"""Shared inputs for paragraph-style editing."""

from __future__ import annotations

from src.config.style_semantics import (
    config_indent_value_to_pt,
    normalize_indent_size_pt,
    normalize_indent_unit,
    normalize_special_indent_mode,
    resolve_pt_indent_value,
)
from src.qt_api import QHBoxLayout, QSizePolicy, QWidget, Signal
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox

_INDENT_UNITS: tuple[tuple[str, str], ...] = (
    ("chars", "字"),
    ("pt", "磅"),
    ("cm", "cm"),
)

_SPECIAL_MODES: tuple[tuple[str, str], ...] = (
    ("none", "无"),
    ("first_line", "首行"),
    ("hanging", "悬挂"),
)

_UNIT_HINTS = {
    "chars": "按当前字号换算，常用于“首行2字”。",
    "pt": "直接按磅值设置缩进。",
    "cm": "按厘米设置缩进，适合精确版芯控制。",
}


class IndentInput(QWidget):
    """Unit-aware indent editor that preserves a canonical pt value.

    Invariant: ``set_reference_size()`` preserves the **display value**
    when the current unit is ``"chars"`` (recalculates the internal pt
    canonical), and preserves the **canonical pt** when the unit is
    ``"pt"`` or ``"cm"``.  This matches Word's behaviour where a
    "首行缩进 2字" stays as "2字" after a font-size change.
    """

    value_changed = Signal(float, str)

    def __init__(self, parent=None, *, reference_size_pt: float = 12.0):
        super().__init__(parent)
        self._reference_size_pt = normalize_indent_size_pt(reference_size_pt)
        self._canonical_pt_value = 0.0
        self._is_syncing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._spin = StyledSpinBox(self)
        self._spin.valueChanged.connect(self._on_spin_changed)
        self._spin.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._spin.setMinimumWidth(0)
        layout.addWidget(self._spin, 1)

        self._unit_combo = StyledComboBox(self)
        self._unit_combo.setSizeAdjustPolicy(StyledComboBox.AdjustToContents)
        self._unit_combo.set_inline(True)
        for value, label in _INDENT_UNITS:
            self._unit_combo.addItem(label, value)
        self._unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        layout.addWidget(self._unit_combo)

        apply_size_class(self._spin, "md")
        apply_size_class(self._unit_combo, "md")
        self._sync_spin_for_unit("chars")
        self._refresh_tooltips()

    def _sync_spin_for_unit(self, unit: str) -> None:
        normalized = normalize_indent_unit(unit)
        if normalized == "chars":
            self._spin.setRange(0.0, 20.0)
            self._spin.setSingleStep(0.5)
            self._spin.setDecimals(1)
        elif normalized == "pt":
            self._spin.setRange(0.0, 240.0)
            self._spin.setSingleStep(1.0)
            self._spin.setDecimals(1)
        else:
            self._spin.setRange(0.0, 20.0)
            self._spin.setSingleStep(0.1)
            self._spin.setDecimals(2)

    def _current_unit(self) -> str:
        return str(self._unit_combo.currentData() or "chars")

    def _display_value_for_canonical(self, unit: str) -> float:
        return resolve_pt_indent_value(self._canonical_pt_value, unit, self._reference_size_pt)

    def _refresh_display(self) -> None:
        unit = self._current_unit()
        self._sync_spin_for_unit(unit)
        blocked = self._spin.blockSignals(True)
        self._spin.setValue(self._display_value_for_canonical(unit))
        self._spin.blockSignals(blocked)
        self._refresh_tooltips()

    def _refresh_tooltips(self) -> None:
        unit = self._current_unit()
        unit_label = dict(_INDENT_UNITS).get(unit, unit)
        hint = _UNIT_HINTS.get(unit, "")
        text = f"当前单位: {unit_label}。{hint} 参考字号 {self._reference_size_pt:g}磅。"
        self.setToolTip(text)
        self._spin.setToolTip(text)
        self._unit_combo.setToolTip("切换缩进单位: 字 / 磅 / cm。")

    def _emit(self) -> None:
        self.value_changed.emit(self.value(), self.unit())

    def _on_spin_changed(self, value: float) -> None:
        if self._is_syncing:
            return
        self._canonical_pt_value = config_indent_value_to_pt(
            value,
            self._reference_size_pt,
            self._current_unit(),
        )
        self._emit()

    def _on_unit_changed(self, _index: int) -> None:
        if self._is_syncing:
            return
        self._refresh_display()
        self._emit()

    def set_reference_size(self, size_pt: float) -> None:
        new_ref = normalize_indent_size_pt(size_pt)
        if new_ref == self._reference_size_pt:
            return

        # When the unit is "chars", the user-visible character count must
        # stay unchanged (matching Word's behaviour).  We recalculate the
        # canonical pt value from the *current display value* × the *new*
        # reference size so that ``value()`` returns the same number the
        # user already sees.
        #
        # For "pt" and "cm" the canonical pt is an absolute physical
        # measurement and must NOT change when the font size changes.
        unit = self._current_unit()
        if unit == "chars":
            current_display = float(self._spin.value())
            self._reference_size_pt = new_ref
            self._canonical_pt_value = config_indent_value_to_pt(
                current_display, self._reference_size_pt, "chars",
            )
        else:
            self._reference_size_pt = new_ref

        self._is_syncing = True
        try:
            self._refresh_display()
        finally:
            self._is_syncing = False

    def set_value(self, value: float, unit: str = "chars") -> None:
        normalized_unit = normalize_indent_unit(unit)
        self._canonical_pt_value = config_indent_value_to_pt(
            value,
            self._reference_size_pt,
            normalized_unit,
        )
        self._is_syncing = True
        try:
            combo_blocked = self._unit_combo.blockSignals(True)
            for index in range(self._unit_combo.count()):
                if self._unit_combo.itemData(index) == normalized_unit:
                    self._unit_combo.setCurrentIndex(index)
                    break
            self._unit_combo.blockSignals(combo_blocked)
            self._refresh_display()
        finally:
            self._is_syncing = False

    def value(self) -> float:
        return float(self._spin.value())

    def unit(self) -> str:
        return self._current_unit()


class SpecialIndentInput(QWidget):
    """Mode + value editor for first-line or hanging indent."""

    value_changed = Signal(str, float, str)

    def __init__(self, parent=None, *, reference_size_pt: float = 12.0):
        super().__init__(parent)
        self._is_syncing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._mode_combo = StyledComboBox(self)
        self._mode_combo.setSizeAdjustPolicy(self._mode_combo.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self._mode_combo.setMinimumWidth(76)
        for value, label in _SPECIAL_MODES:
            self._mode_combo.addItem(label, value)
        self._mode_combo.currentIndexChanged.connect(self._on_any_changed)
        layout.addWidget(self._mode_combo)

        self._indent_input = IndentInput(self, reference_size_pt=reference_size_pt)
        self._indent_input.value_changed.connect(self._on_indent_changed)
        layout.addWidget(self._indent_input, 1)

        self._sync_enabled_state()

    def _mode(self) -> str:
        return normalize_special_indent_mode(self._mode_combo.currentData() or "none")

    def _sync_enabled_state(self) -> None:
        enabled = self._mode() != "none"
        self._indent_input.setEnabled(enabled)
        mode = self._mode()
        if mode == "none":
            text = "不启用特殊缩进。"
        elif mode == "first_line":
            text = "首行缩进: 仅第一行向内缩进。"
        else:
            text = "悬挂缩进: 首行顶格，后续各行向内缩进。"
        self.setToolTip(text)
        self._mode_combo.setToolTip("切换特殊缩进模式: 无 / 首行 / 悬挂。")

    def _emit(self) -> None:
        self.value_changed.emit(self.mode(), self.value(), self.unit())

    def _on_any_changed(self, _index: int) -> None:
        if self._is_syncing:
            return
        if self._mode() != "none" and self._indent_input.value() <= 0:
            self._indent_input.set_value(2.0, self._indent_input.unit())
        self._sync_enabled_state()
        self._emit()

    def _on_indent_changed(self, _value: float, _unit: str) -> None:
        if self._is_syncing:
            return
        self._emit()

    def set_reference_size(self, size_pt: float) -> None:
        self._indent_input.set_reference_size(size_pt)

    def set_value(self, mode: str, value: float, unit: str = "chars") -> None:
        normalized_mode = normalize_special_indent_mode(mode)
        self._is_syncing = True
        try:
            combo_blocked = self._mode_combo.blockSignals(True)
            for index in range(self._mode_combo.count()):
                if self._mode_combo.itemData(index) == normalized_mode:
                    self._mode_combo.setCurrentIndex(index)
                    break
            self._mode_combo.blockSignals(combo_blocked)
            self._indent_input.set_value(value, unit)
            self._sync_enabled_state()
        finally:
            self._is_syncing = False
        self._emit()

    def mode(self) -> str:
        return self._mode()

    def value(self) -> float:
        if self.mode() == "none":
            return 0.0
        return self._indent_input.value()

    def unit(self) -> str:
        return self._indent_input.unit()
