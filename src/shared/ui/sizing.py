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

from typing import Literal

from src.qt_api import QWidget, Qt

SizeClass = Literal["sm", "md", "lg"]

_VALID_CLASSES = {"sm", "md", "lg"}


def resolved_control_height(theme, size: SizeClass = "md") -> int:
    """Return the rendered pixel height for a themed interactive control."""
    if size not in _VALID_CLASSES:
        raise ValueError(
            f"Invalid size class: {size!r}. Expected one of {_VALID_CLASSES}"
        )
    token = {
        "sm": theme.control_height_sm,
        "md": theme.control_height_md,
        "lg": theme.control_height_lg,
    }[size]
    return int(token) + 2


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


def normalize_form_control_heights(
    root: QWidget,
    height: int,
    *,
    marker: str = "/* normalized-form-control-height */",
) -> None:
    """Force mixed form controls under ``root`` to render at one height.

    ``StyledComboBox`` and ``StyledSpinBox`` both participate in the themed
    size-class system, but Qt's spin-box size hint can still become taller
    than combo boxes when both are placed in the same form. ``SpacingInput``
    adds one more wrapper around the spin box, so its outer widget must also
    be constrained. This helper keeps that contract centralized instead of
    scattering object-specific QSS patches through panels.
    """
    if height <= 0:
        return

    from src.shared.ui.spacing_input import SpacingInput
    from src.shared.ui.styled_combo_box import StyledComboBox
    from src.shared.ui.styled_spin_box import StyledSpinBox

    def _widgets() -> list[QWidget]:
        return [root, *root.findChildren(QWidget)]

    def _ensure_object_name(widget: QWidget) -> str:
        name = widget.objectName()
        if not name:
            name = f"normalized_control_{id(widget)}"
            widget.setObjectName(name)
        return name

    def _strip_previous_override(style_sheet: str) -> str:
        if marker not in style_sheet:
            return style_sheet.rstrip()
        return style_sheet.split(marker, 1)[0].rstrip()

    def _apply_qss_height(widget: QWidget) -> None:
        object_name = _ensure_object_name(widget)
        base_style = _strip_previous_override(widget.styleSheet())
        override = f"""
{marker}
#{object_name} {{
    min-height: {height}px;
    max-height: {height}px;
    padding-top: 0px;
    padding-bottom: 0px;
}}
#{object_name}[sizeClass="sm"],
#{object_name}[sizeClass="md"],
#{object_name}[sizeClass="lg"] {{
    min-height: {height}px;
    max-height: {height}px;
    padding-top: 0px;
    padding-bottom: 0px;
}}
""".strip()
        widget.setStyleSheet(f"{base_style}\n{override}".strip())
        widget.updateGeometry()

    for widget in _widgets():
        if isinstance(widget, (StyledComboBox, StyledSpinBox)):
            _apply_qss_height(widget)
        elif isinstance(widget, SpacingInput):
            widget.setMinimumHeight(height)
            widget.setMaximumHeight(height)
            widget.updateGeometry()
