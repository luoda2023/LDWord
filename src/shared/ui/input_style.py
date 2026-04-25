"""
Shared text-input styling helpers.
"""

from __future__ import annotations

from src.shared.ui.theme import AppTheme


def build_text_input_stylesheet(
    theme: AppTheme,
    selector: str = "QLineEdit",
    *,
    font_family: str | None = None,
    background: str | None = None,
    focus_border_color: str | None = None,
    padding_x: int | None = None,
    padding_y: int | None = None,
) -> str:
    resolved_font_family = font_family or theme.font_family
    resolved_background = background or theme.bg_input
    resolved_focus_border = focus_border_color or theme.border_focus
    resolved_padding_x = theme.input_padding_x if padding_x is None else padding_x
    resolved_padding_y = theme.input_padding_y if padding_y is None else padding_y

    return f"""
        {selector} {{
            background: {resolved_background};
            color: {theme.text_primary};
            border: 1px solid {theme.border};
            border-radius: {theme.input_radius}px;
            min-height: {theme.control_height_md}px;
            padding: {resolved_padding_y}px {resolved_padding_x}px;
            font-size: {theme.font_size_md}px;
            font-family: {resolved_font_family};
            selection-background-color: {theme.primary};
            selection-color: {theme.text_on_primary};
        }}
        {selector}:focus {{
            border-color: {resolved_focus_border};
        }}
        {selector}:disabled {{
            background: {theme.bg_hover};
            color: {theme.text_disabled};
        }}
        {selector}::placeholder {{
            color: {theme.text_hint};
        }}

        /* ── Size-class tiers (via sizeClass dynamic property) ── */
        {selector}[sizeClass="sm"] {{
            min-height: {theme.control_height_sm}px;
            max-height: {theme.control_height_sm}px;
        }}
        {selector}[sizeClass="md"] {{
            min-height: {theme.control_height_md}px;
            max-height: {theme.control_height_md}px;
        }}
        {selector}[sizeClass="lg"] {{
            min-height: {theme.control_height_lg}px;
            max-height: {theme.control_height_lg}px;
        }}

        QComboBox[sizeClass="sm"] {{
            min-height: {theme.control_height_sm}px;
            max-height: {theme.control_height_sm}px;
        }}
        QComboBox[sizeClass="md"] {{
            min-height: {theme.control_height_md}px;
            max-height: {theme.control_height_md}px;
        }}

        QSpinBox[sizeClass="sm"] {{
            min-height: {theme.control_height_sm}px;
            max-height: {theme.control_height_sm}px;
        }}
        QSpinBox[sizeClass="md"] {{
            min-height: {theme.control_height_md}px;
            max-height: {theme.control_height_md}px;
        }}

        QDoubleSpinBox[sizeClass="sm"] {{
            min-height: {theme.control_height_sm}px;
            max-height: {theme.control_height_sm}px;
        }}
        QDoubleSpinBox[sizeClass="md"] {{
            min-height: {theme.control_height_md}px;
            max-height: {theme.control_height_md}px;
        }}
    """
