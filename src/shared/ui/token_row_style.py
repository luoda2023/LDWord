"""Shared row chrome for material-token inventories."""

from __future__ import annotations

from src.shared.ui.theme import get_theme


def apply_token_row_style(row, *, object_name: str, is_last: bool) -> None:
    theme = get_theme()
    divider = "transparent" if is_last else theme.divider
    row.setStyleSheet(
        f"""
        #{object_name} {{
            border: none;
            border-bottom: 1px solid {divider};
            background: transparent;
        }}
        #{object_name}:hover {{
            background: {theme.bg_hover};
        }}
        """
    )


__all__ = ["apply_token_row_style"]
