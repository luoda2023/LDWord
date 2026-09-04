"""
Unified control sizing — replaces all business-layer setFixedHeight() calls.

Why this module exists
─────────────────────
Qt's ``setFixedHeight()`` operates at the C++/layout level, creating a hard
viewport clip.  QSS ``min-height`` + ``padding`` + ``border`` operate inside
the Qt style-sheet box model.  When both are set on the same widget the
rendered content overflows the clip and the bottom border / padding is cut off.

This module resolves the conflict once and for all by delegating **all**
height declarations for themed interactive controls to the QSS layer via
Qt Dynamic Properties.  The QSS selectors ``[sizeClass="sm|md|lg"]`` are
picked up by rules emitted from ``button_style.py`` and ``input_style.py``.

Usage::

    from src.shared.ui.sizing import apply_size_class

    apply_size_class(my_button, "md")    # standard height
    apply_size_class(my_input,  "sm")    # compact height
    apply_size_class(my_combo,  "lg")    # large height
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.qt_api import QWidget

SizeClass = Literal["sm", "md", "lg"]

_VALID_CLASSES = {"sm", "md", "lg"}


@dataclass(frozen=True)
class ControlSizeMetrics:
    """Resolved geometry for one interactive-control size tier."""

    size: SizeClass
    outer_height: int
    vertical_padding: int
    border_width: int

    @property
    def content_height(self) -> int:
        """QSS min/max-height after accounting for padding and borders."""
        return max(
            0,
            self.outer_height
            - (self.vertical_padding * 2)
            - (self.border_width * 2),
        )


def control_size_metrics(
    theme,
    size: SizeClass = "md",
    *,
    vertical_padding: int = 0,
    border_width: int = 1,
) -> ControlSizeMetrics:
    """Return one unambiguous final-outer-height control metric."""
    if size not in _VALID_CLASSES:
        raise ValueError(
            f"Invalid size class: {size!r}. Expected one of {_VALID_CLASSES}"
        )
    outer_height = {
        "sm": theme.control_height_sm,
        "md": theme.control_height_md,
        "lg": theme.control_height_lg,
    }[size]
    return ControlSizeMetrics(
        size=size,
        outer_height=max(1, int(outer_height)),
        vertical_padding=max(0, int(vertical_padding)),
        border_width=max(0, int(border_width)),
    )


def resolved_control_height(theme, size: SizeClass = "md") -> int:
    """Return the final outer pixel height for a themed control."""
    return control_size_metrics(theme, size).outer_height


def apply_size_class(widget: QWidget, size: SizeClass) -> None:
    """Declare a widget's size tier — the QSS layer handles the rest.

    This sets the ``sizeClass`` dynamic property so that QSS rules like
    ``QPushButton[sizeClass="md"] { min-height: …; max-height: …; }``
    take effect.  No ``setFixedHeight()`` is ever called.

    Parameters
    ----------
    widget:
        Any QWidget that participates in the themed size system.
    size:
        One of ``"sm"`` (compact), ``"md"`` (default), ``"lg"`` (large).
    """
    if size not in _VALID_CLASSES:
        raise ValueError(
            f"Invalid size class: {size!r}. Expected one of {_VALID_CLASSES}"
        )
    widget.setProperty("sizeClass", size)
    # Dynamic property changes require unpolish/polish to re-evaluate selectors
    style = widget.style()
    if style:
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
    widget.updateGeometry()


def widget_size_class(widget: QWidget, default: SizeClass = "md") -> SizeClass:
    """Return a validated size class from a widget dynamic property."""
    value = str(widget.property("sizeClass") or default)
    return value if value in _VALID_CLASSES else default
