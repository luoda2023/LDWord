import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui import (
    build_checkbox_stylesheet,
)
from src.shared.ui.theme import LIGHT


def test_theme_exposes_selection_control_tokens():
    assert LIGHT.checkbox_size == 18
    assert LIGHT.checkbox_radius == 5
    assert LIGHT.checkbox_border_width == 1
    assert LIGHT.checkbox_border_color == LIGHT.border
    assert LIGHT.checkbox_hover_border_color == LIGHT.border_focus
    assert LIGHT.checkbox_checked_bg == LIGHT.primary
    assert LIGHT.radio_size == 18
    assert LIGHT.radio_ring_width == 1
    assert LIGHT.radio_dot_size == 7
    assert LIGHT.radio_checked_ring_color == LIGHT.primary
    assert LIGHT.selection_label_color == LIGHT.text_secondary
    assert LIGHT.selection_label_checked_color == LIGHT.text_primary
    assert LIGHT.selection_label_disabled_color == LIGHT.text_disabled


def test_checkbox_stylesheet_uses_theme_tokens_and_stays_checkbox_only():
    checkbox_qss = build_checkbox_stylesheet(LIGHT, selector="#demo QCheckBox")

    assert "#demo QCheckBox" in checkbox_qss
    assert f"width: {LIGHT.checkbox_size}px;" in checkbox_qss
    assert f"height: {LIGHT.checkbox_size}px;" in checkbox_qss
    assert f"border-radius: {LIGHT.checkbox_radius}px;" in checkbox_qss
    assert f"spacing: {LIGHT.checkbox_label_gap}px;" in checkbox_qss
    assert LIGHT.checkbox_checked_bg in checkbox_qss
    assert "QRadioButton" not in checkbox_qss
