"""Spacing input widget."""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QSizePolicy, QWidget, Signal

from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
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
        units: tuple[str, ...] | tuple[tuple[str, str], ...] | None = None,
        show_unit: bool = True,
        unit_inline: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        raw_units = tuple(units or ("cm", "pt", "mm", "?"))
        self._unit_items = tuple(
            (str(item[0]), str(item[1]))
            if isinstance(item, tuple) and len(item) == 2
            else (str(item), str(item))
            for item in raw_units
        )
        self._units = tuple(value for value, _label in self._unit_items)
        self._show_unit = bool(show_unit)
        self._unit_inline = bool(unit_inline)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(get_theme().spacing_xs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._spin = StyledSpinBox()
        self._spin.setRange(min_val, max_val)
        self._spin.setSingleStep(step)
        self._spin.setDecimals(decimals)
        self._spin.valueChanged.connect(self._emit)
        self._layout.addWidget(self._spin, 1)

        self._unit = StyledComboBox()
        if self._unit_inline:
            self._unit.set_inline(True)
            self._unit.setSizeAdjustPolicy(StyledComboBox.AdjustToContents)
        for value, label in self._unit_items:
            self._unit.addItem(label, value)
        if unit in self._units:
            self._set_unit(unit)
        elif self._units:
            self._unit.setCurrentIndex(0)
        self._unit.currentIndexChanged.connect(self._emit)
        self._layout.addWidget(self._unit)
        self._unit.setVisible(self._show_unit)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setSpacing(t.spacing_xs)
        apply_size_class(self._spin, "md")
        apply_size_class(self._unit, "md")
        if self._unit_inline:
            self._unit.setMinimumWidth(0)
            self._unit.setMaximumWidth(16777215)
        else:
            self._unit.setFixedWidth(t.spacing_input_unit_width)
        content_heights = [self._spin.sizeHint().height(), self._spin.minimumSizeHint().height()]
        if self._show_unit:
            content_heights.extend([self._unit.sizeHint().height(), self._unit.minimumSizeHint().height()])
        self.setMinimumHeight(max([t.control_height_md, *content_heights]))
        self.updateGeometry()

    def _emit(self, *_):
        self.value_changed.emit(self._spin.value(), self.unit())

    def value(self) -> float:
        return self._spin.value()

    def unit(self) -> str:
        return str(self._unit.currentData() or self._unit.currentText())

    def set_value(self, val: float, unit: str = ''):
        self._spin.setValue(val)
        if unit:
            self._set_unit(unit)

    def _set_unit(self, unit: str) -> None:
        for index in range(self._unit.count()):
            if self._unit.itemData(index) == unit:
                self._unit.setCurrentIndex(index)
                return
        self._unit.setCurrentText(unit)

    @property
    def spin_box(self) -> StyledSpinBox:
        return self._spin

    @property
    def unit_combo(self) -> StyledComboBox:
        return self._unit
