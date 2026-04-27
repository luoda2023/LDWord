"""Compact binary option chip used inside form rows."""

from __future__ import annotations

from typing import Literal

from src.qt_api import QHBoxLayout, QLabel, QSizePolicy, QWidget, Qt

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch


OptionToggleChipVariant = Literal["contained", "inline"]


class OptionToggleChip(QWidget):
    """Label + ``ToggleSwitch`` primitive for compact form-row booleans.

    Use this when a boolean option is one field inside a form row, for example
    text style flags such as bold or italic. Do not use it for module-level
    feature controls; larger feature rows with a config action should keep
    using ``FeatureToggleRow``.
    """

    _VALID_VARIANTS = {"contained", "inline"}

    def __init__(
        self,
        label: str,
        toggle: ToggleSwitch | None = None,
        *,
        variant: OptionToggleChipVariant = "contained",
        fill: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        if variant not in self._VALID_VARIANTS:
            raise ValueError(f"Unsupported option chip variant: {variant!r}")

        self._variant: OptionToggleChipVariant = variant
        self._fill = bool(fill)
        self._label = QLabel(label, self)
        self._toggle = toggle or ToggleSwitch(self)

        self.setObjectName("option_toggle_chip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        horizontal_policy = QSizePolicy.Expanding if self._fill else QSizePolicy.Fixed
        self.setSizePolicy(horizontal_policy, QSizePolicy.Fixed)

        self._layout = QHBoxLayout(self)
        self._layout.addWidget(self._label)
        if self._variant == "contained":
            if self._fill:
                self._layout.addStretch(1)
            self._layout.addWidget(self._toggle)
        else:
            self._layout.addWidget(self._toggle)
            if self._fill:
                self._layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def toggle(self) -> ToggleSwitch:
        return self._toggle

    def label_widget(self) -> QLabel:
        return self._label

    def _apply_theme(self) -> None:
        theme = get_theme()
        if self._variant == "contained":
            self._layout.setContentsMargins(12, 8, 12, 8)
            self._layout.setSpacing(10)
            self.setStyleSheet(
                f"""
                QWidget#option_toggle_chip {{
                    background: {theme.bg_hover};
                    border: 1px solid {theme.border_light};
                    border-radius: {theme.radius_sm}px;
                }}
                """
            )
        else:
            self._layout.setContentsMargins(0, 0, 0, 0)
            self._layout.setSpacing(8)
            self.setStyleSheet("QWidget#option_toggle_chip { background: transparent; border: none; }")

        self._label.setStyleSheet(
            f"font-size: {theme.font_size_md}px; color: {theme.text_primary};"
        )


__all__ = ["OptionToggleChip", "OptionToggleChipVariant"]
