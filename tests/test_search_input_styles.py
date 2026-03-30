import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.search_input import SearchInput
from src.shared.ui.theme import LIGHT


def test_search_input_uses_theme_tokens_in_stylesheet():
    qss = SearchInput.build_container_stylesheet("search_input", LIGHT, focused=False)

    assert "#search_input" in qss
    assert f"border-radius: {LIGHT.input_radius}px;" in qss
    assert f"border: 1px solid {LIGHT.border};" in qss
    assert f"background: {LIGHT.bg_input};" in qss


def test_search_input_input_and_clear_stylesheets_are_tokenized():
    input_qss = SearchInput.build_input_stylesheet(LIGHT)
    clear_qss = SearchInput.build_clear_button_stylesheet(LIGHT)

    assert f"font-size: {LIGHT.font_size_md}px;" in input_qss
    assert f"padding: {LIGHT.input_padding_y}px 0;" in input_qss
    assert f"border-radius: {LIGHT.input_radius}px;" in clear_qss


def test_search_input_has_single_clear_button_stylesheet_assignment():
    source = inspect.getsource(SearchInput._apply_theme)

    assert source.count("self._clear_btn.setStyleSheet") == 1
    assert "WA_StyledBackground" in inspect.getsource(SearchInput.__init__)
