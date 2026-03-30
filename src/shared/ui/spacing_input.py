"""
Spacing input widget.
"""

from __future__ import annotations

from src.qt_api import QDoubleSpinBox, QHBoxLayout, QWidget, Signal

from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme


class SpacingInput(QWidget):
    """Numeric spacing input with selectable units."""

    value_changed = Signal(float, str)

    def __init__(
        self,
        *,
        unit: str = 'cm',
        min_val: float = 0,
        max_val: float = 20,
        step: float = 0.1,
        decimals: int = 2,
        parent=None,
    ):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(get_theme().spacing_xs)

        self._spin = QDoubleSpinBox()
        self._spin.setRange(min_val, max_val)
        self._spin.setSingleStep(step)
        self._spin.setDecimals(decimals)
        self._spin.valueChanged.connect(self._emit)
        self._layout.addWidget(self._spin, 1)

        self._unit = StyledComboBox()
        self._unit.addItems(['cm', 'pt', 'mm', '?'])
        self._unit.setCurrentText(unit)
        self._unit.currentTextChanged.connect(self._emit)
        self._layout.addWidget(self._unit)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setSpacing(t.spacing_xs)
        self._spin.setFixedHeight(t.control_height_md)
        self._unit.setFixedHeight(t.control_height_md)
        self._unit.setFixedWidth(t.spacing_input_unit_width)
        self.setFixedHeight(t.control_height_md)

    def _emit(self, *_):
        self.value_changed.emit(self._spin.value(), self._unit.currentText())

    def value(self) -> float:
        return self._spin.value()

    def unit(self) -> str:
        return self._unit.currentText()

    def set_value(self, val: float, unit: str = ''):
        self._spin.setValue(val)
        if unit:
            self._unit.setCurrentText(unit)
