"""Shared inputs for paragraph-style editing."""

from __future__ import annotations

from src.config.style_semantics import (
    config_indent_value_to_pt,
    normalize_indent_size_pt,
    normalize_indent_unit,
    normalize_special_indent_mode,
    resolve_pt_indent_value,
)
from src.qt_api import QDoubleSpinBox, QHBoxLayout, QSizePolicy, QWidget, Signal
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


class IndentInput(QWidget):
    """Unit-aware indent editor that preserves a canonical pt value."""

    value_changed = Signal(float, str)

    def __init__(self, parent=None, *, reference_size_pt: float = 12.0):
        super().__init__(parent)
        self._reference_size_pt = normalize_indent_size_pt(reference_size_pt)
        self._canonical_pt_value = 0.0
        self._is_syncing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._spin = QDoubleSpinBox(self)
        self._spin.valueChanged.connect(self._on_spin_changed)
        self._spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self._spin, 1)

        self._unit_combo = StyledComboBox(self)
        self._unit_combo.setSizeAdjustPolicy(StyledComboBox.AdjustToContents)
        for value, label in _INDENT_UNITS:
            self._unit_combo.addItem(label, value)
        self._unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        layout.addWidget(self._unit_combo)

        apply_size_class(self._spin, "md")
        apply_size_class(self._unit_combo, "md")
        self._sync_spin_for_unit("chars")

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
        self._reference_size_pt = normalize_indent_size_pt(size_pt)
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

    def _emit(self) -> None:
        self.value_changed.emit(self.mode(), self.value(), self.unit())

    def _on_any_changed(self, _index: int) -> None:
        if self._is_syncing:
            return
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
