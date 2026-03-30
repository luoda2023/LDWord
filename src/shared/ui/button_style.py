"""
Shared QPushButton variant styling.
"""

from __future__ import annotations

from src.qt_api import QPushButton, Qt

from src.shared.ui.theme import AppTheme


_BUTTON_VARIANTS = {"primary", "secondary", "danger", "ghost-danger", "ghost-primary"}


def build_button_stylesheet(
    theme: AppTheme,
    selector: str = "QPushButton",
    *,
    min_height: int | None = None,
    padding_x: int | None = None,
    padding_y: int | None = None,
    radius: int | None = None,
    font_size: int | None = None,
) -> str:
    resolved_min_height = theme.button_height_md if min_height is None else min_height
    resolved_padding_x = theme.button_padding_x if padding_x is None else padding_x
    resolved_padding_y = theme.button_padding_y if padding_y is None else padding_y
    resolved_radius = theme.button_radius if radius is None else radius
    resolved_font_size = theme.font_size_md if font_size is None else font_size

    return f"""
        {selector}[variant] {{
            outline: none;
            min-height: {resolved_min_height}px;
            padding: {resolved_padding_y}px {resolved_padding_x}px;
            border-radius: {resolved_radius}px;
            font-size: {resolved_font_size}px;
            font-weight: {theme.button_font_weight};
        }}

        {selector}[variant="primary"] {{
            background: {theme.primary};
            color: {theme.text_on_primary};
            border: none;
        }}
        {selector}[variant="primary"]:hover {{
            background: {theme.primary_hover};
        }}
        {selector}[variant="primary"]:pressed {{
            background: {theme.primary_pressed};
        }}

        {selector}[variant="secondary"] {{
            background: {theme.bg_card};
            color: {theme.text_primary};
            border: 1px solid {theme.border};
        }}
        {selector}[variant="secondary"]:hover {{
            background: {theme.bg_hover};
        }}
        {selector}[variant="secondary"]:pressed {{
            background: {theme.bg_selected};
            border-color: {theme.border_focus};
        }}

        {selector}[variant="danger"] {{
            background: {theme.error};
            color: {theme.text_on_primary};
            border: none;
        }}
        {selector}[variant="danger"]:hover {{
            background: {theme.error_hover};
        }}
        {selector}[variant="danger"]:pressed {{
            background: {theme.error_pressed};
        }}

        {selector}[variant="ghost-danger"] {{
            background: transparent;
            color: {theme.error};
            border: none;
        }}
        {selector}[variant="ghost-danger"]:hover {{
            background: {theme.error_bg};
        }}
        {selector}[variant="ghost-danger"]:pressed {{
            background: {theme.error_bg};
            color: {theme.error_pressed};
        }}

        {selector}[variant="ghost-primary"] {{
            background: transparent;
            color: {theme.primary};
            border: none;
        }}
        {selector}[variant="ghost-primary"]:hover {{
            background: {theme.primary_light};
        }}
        {selector}[variant="ghost-primary"]:pressed {{
            background: {theme.primary_light};
            color: {theme.primary_pressed};
        }}

        {selector}:disabled {{
            background: {theme.bg_input};
            color: {theme.text_disabled};
            border: none;
        }}
    """


def apply_button_variant(button: QPushButton, variant: str) -> QPushButton:
    if variant not in _BUTTON_VARIANTS:
        raise ValueError(f"Unsupported button variant: {variant}")
    button.setProperty("variant", variant)
    button.setAttribute(Qt.WA_StyledBackground, True)
    button.style().unpolish(button)
    button.style().polish(button)
    button.update()
    return button
