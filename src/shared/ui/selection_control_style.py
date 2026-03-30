"""
Shared checkbox stylesheet builder.

Checkbox remains on the shared QSS path.
Radio / Slider geometry has moved onto project-owned self-drawn controls.
"""

from __future__ import annotations

from urllib.parse import quote

from src.shared.ui.theme import AppTheme


def _checkbox_checkmark_image(color: str) -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
        f"stroke='{color}' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'>"
        "<polyline points='20 6 9 17 4 12'/></svg>"
    )
    return f'url("data:image/svg+xml;utf8,{quote(svg)}")'


def build_checkbox_stylesheet(theme: AppTheme, selector: str = "QCheckBox") -> str:
    return f"""
        {selector} {{
            font-size: {theme.font_size_md}px;
            color: {theme.selection_label_color};
            spacing: {theme.checkbox_label_gap}px;
        }}
        {selector}:checked {{
            color: {theme.selection_label_checked_color};
        }}
        {selector}:disabled {{
            color: {theme.selection_label_disabled_color};
        }}
        {selector}::indicator {{
            width: {theme.checkbox_size}px;
            height: {theme.checkbox_size}px;
            border: {theme.checkbox_border_width}px solid {theme.checkbox_border_color};
            border-radius: {theme.checkbox_radius}px;
            background: {theme.checkbox_bg};
        }}
        {selector}::indicator:hover {{
            border-color: {theme.checkbox_hover_border_color};
        }}
        {selector}::indicator:checked {{
            background: {theme.checkbox_checked_bg};
            border-color: {theme.checkbox_checked_border_color};
            image: {_checkbox_checkmark_image(theme.checkbox_checkmark_color)};
        }}
        {selector}::indicator:checked:hover {{
            border-color: {theme.checkbox_focus_border_color};
        }}
        {selector}::indicator:disabled {{
            background: {theme.checkbox_disabled_bg};
            border-color: {theme.checkbox_disabled_border_color};
            image: none;
        }}
        {selector}::indicator:disabled:checked {{
            background: {theme.checkbox_disabled_bg};
            border-color: {theme.checkbox_disabled_border_color};
            image: {_checkbox_checkmark_image(theme.checkbox_disabled_checkmark_color)};
        }}
    """
