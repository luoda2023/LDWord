"""Spacing input widget."""

from __future__ import annotations

from src.qt_api import QDoubleSpinBox, QHBoxLayout, QWidget, Signal

from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme


class SpacingInput(QWidget):
    """Numeric spacing input with configurable unit presentation."""

    value_changed = Signal(float, str)

    def __init__(
        self,
        *,
        unit: str = 'cm',
        min_val: float = 0,
        max_val: float = 20,
        step: float = 0.1,
        decimals: int = 2,
        units: tuple[str, ...] | None = None,
        show_unit: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._units = tuple(units or ("cm", "pt", "mm", "?"))
        self._show_unit = bool(show_unit)
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
        self._unit.addItems(list(self._units))
        if unit in self._units:
            self._unit.setCurrentText(unit)
        elif self._units:
            self._unit.setCurrentIndex(0)
        self._unit.currentTextChanged.connect(self._emit)
        self._layout.addWidget(self._unit)
        self._unit.setVisible(self._show_unit)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setSpacing(t.spacing_xs)
        apply_size_class(self._spin, "md")
        apply_size_class(self._unit, "md")
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

    @property
    def spin_box(self) -> QDoubleSpinBox:
        return self._spin

    @property
    def unit_combo(self) -> StyledComboBox:
        return self._unit
