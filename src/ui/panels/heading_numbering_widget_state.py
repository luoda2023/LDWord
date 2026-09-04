"""Small widget-state helpers shared by heading-numbering surfaces."""

from __future__ import annotations


def set_disabled_visual(widget, muted: bool) -> None:
    widget.setProperty("muted", muted)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_state_property(widget, name: str, value) -> None:
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def select_combo_value(combo, value) -> None:
    for index in range(combo.count()):
        if combo.itemData(index) == value:
            combo.setCurrentIndex(index)
            return
