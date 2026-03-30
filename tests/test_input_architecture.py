import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.placeholder_edit import PlaceholderEdit
from src.shared.ui.theme import LIGHT
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def test_shared_input_stylesheet_supports_font_family_override():
    qss = build_text_input_stylesheet(LIGHT, font_family="Consolas, monospace")

    assert "font-family: Consolas, monospace;" in qss
    assert f"border-radius: {LIGHT.input_radius}px;" in qss


def test_placeholder_edit_uses_shared_text_input_stylesheet():
    source = inspect.getsource(PlaceholderEdit._apply_theme)

    assert "build_text_input_stylesheet" in source
    assert "QLineEdit {" not in source


def test_heading_numbering_panel_uses_shared_text_input_and_selection_helpers():
    source = inspect.getsource(HeadingNumberingPanel._apply_theme)
    stylesheet_source = (ROOT / "src/ui/panels/heading_numbering_styles.py").read_text(encoding="utf-8")

    assert "build_heading_numbering_panel_stylesheet" in source
    assert "build_text_input_stylesheet" in stylesheet_source
    assert "build_checkbox_stylesheet" in stylesheet_source
    assert "build_selection_control_stylesheet" not in stylesheet_source
    assert "QLineEdit {" not in source
