"""Shared typography form controls."""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QWidget

from src.shared.ui.option_toggle_chip import OptionToggleChip, OptionToggleChipVariant
from src.shared.ui.toggle_switch import ToggleSwitch


def build_emphasis_widget(
    parent,
    bold_toggle: ToggleSwitch,
    italic_toggle: ToggleSwitch,
    *,
    variant: OptionToggleChipVariant = "contained",
    fill: bool = True,
    spacing: int = 8,
) -> QWidget:
    """Build the standard bold/italic field used by typography forms."""

    widget = QWidget(parent)
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)

    stretch = 1 if fill else 0
    layout.addWidget(
        OptionToggleChip("加粗", bold_toggle, variant=variant, fill=fill, parent=widget),
        stretch,
    )
    layout.addWidget(
        OptionToggleChip("斜体", italic_toggle, variant=variant, fill=fill, parent=widget),
        stretch,
    )
    if not fill:
        layout.addStretch(1)
    return widget


__all__ = ["build_emphasis_widget"]
