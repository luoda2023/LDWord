"""
Shared text-input styling helpers.
"""

from __future__ import annotations

from src.shared.ui.input_metrics import build_framed_input_stylesheet
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
    min_height: int | None = None,
) -> str:
    return build_framed_input_stylesheet(
        theme,
        selector,
        font_family=font_family,
        background=background,
        focus_border_color=focus_border_color,
        padding_x=padding_x,
        padding_y=padding_y,
        min_height=min_height,
    )
