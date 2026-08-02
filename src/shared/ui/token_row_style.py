"""Shared row chrome for material-token inventories."""

from __future__ import annotations


from src.qt_api import Qt


def apply_token_row_style(row, *, object_name: str, is_last: bool) -> None:
    """Declare row state without compiling a stylesheet for every row.

    The owning page installs :func:`build_token_row_stylesheet` once.  Dynamic
    properties keep the row's last-item state local while avoiding hundreds of
    identical ``setStyleSheet`` calls during page construction.
    """

    if row.objectName() != object_name:
        row.setObjectName(object_name)
    row.setProperty("tokenRow", True)
    next_is_last = bool(is_last)
    changed = row.property("tokenRowLast") != next_is_last
    row.setProperty("tokenRowLast", next_is_last)
    if changed and row.testAttribute(Qt.WA_WState_Polished):
        style = row.style()
        style.unpolish(row)
        style.polish(row)


def build_token_row_stylesheet(theme) -> str:
    """Return the single inherited QSS rule used by all token inventory rows."""

    return f"""
        QWidget[tokenRow="true"] {{
            border: none;
            border-bottom: 1px solid {theme.divider};
            background: transparent;
        }}
        QWidget[tokenRow="true"][tokenRowLast="true"] {{
            border-bottom-color: transparent;
        }}
        QWidget[tokenRow="true"]:hover {{
            background: {theme.bg_hover};
        }}
    """


__all__ = ["apply_token_row_style", "build_token_row_stylesheet"]
