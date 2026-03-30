"""
Shared dialog style builders.
"""

from __future__ import annotations

from src.shared.ui.theme import AppTheme


def build_dialog_icon_container_stylesheet(theme: AppTheme, background: str) -> str:
    return f"background: {background}; border-radius: {theme.radius_lg}px;"


def build_dialog_message_stylesheet(theme: AppTheme) -> str:
    return (
        f"color: {theme.text_secondary}; "
        f"font-size: {theme.font_size_md}px; "
        f"font-weight: 400; "
        f"font-family: {theme.font_family};"
        f"line-height: 1.5;"
    )


def build_dialog_detail_stylesheet(
    theme: AppTheme,
    *,
    text_color: str,
    border_color: str | None = None,
    padding: int | None = None,
    radius: int | None = None,
) -> str:
    return (
        "QTextEdit { "
        f"background: {theme.bg_input}; "
        f"color: {text_color}; "
        f"border: 1px solid {border_color or theme.border_light}; "
        f"border-radius: {(radius if radius is not None else theme.radius_md)}px; "
        f"padding: {(padding if padding is not None else theme.spacing_md)}px; "
        "font-family: 'Consolas', 'Microsoft YaHei'; "
        f"font-size: {theme.font_size_sm}px;"
        "}"
    )


def build_dialog_path_label_stylesheet(theme: AppTheme) -> str:
    return f"color: {theme.text_hint}; font-size: {theme.font_size_sm}px; font-family: {theme.font_family};"
