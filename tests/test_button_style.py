import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import LIGHT


def test_button_stylesheet_uses_theme_tokens():
    qss = build_button_stylesheet(LIGHT)

    assert 'QPushButton[variant="primary"]' in qss
    assert f'border-radius: {LIGHT.button_radius}px;' in qss
    assert f'min-height: {LIGHT.button_height_md}px;' in qss
    assert f'padding: {LIGHT.button_padding_y}px {LIGHT.button_padding_x}px;' in qss
    assert f'font-weight: {LIGHT.button_font_weight};' in qss


def test_theme_exposes_combo_and_input_tokens():
    assert LIGHT.input_radius > 0
    assert LIGHT.input_icon_size > 0
    assert LIGHT.combo_arrow_zone_width > 0
    assert LIGHT.combo_popup_radius > 0
    assert LIGHT.spin_button_width > 0


def test_theme_uses_compact_medium_button_tokens():
    assert LIGHT.button_height_md == 32
    assert LIGHT.button_padding_x == 14
    assert LIGHT.button_padding_y == 4


def test_apply_button_variant_sets_dynamic_property_and_refreshes_style():
    class _FakeStyle:
        def __init__(self):
            self.unpolished = False
            self.polished = False

        def unpolish(self, _button):
            self.unpolished = True

        def polish(self, _button):
            self.polished = True

    class _FakeButton:
        def __init__(self):
            self._properties = {}
            self._attributes = {}
            self._style = _FakeStyle()
            self.updated = False

        def setProperty(self, key, value):
            self._properties[key] = value

        def property(self, key):
            return self._properties.get(key)

        def setAttribute(self, key, value):
            self._attributes[key] = value

        def style(self):
            return self._style

        def update(self):
            self.updated = True

    button = _FakeButton()

    apply_button_variant(button, "danger")

    assert button.property("variant") == "danger"
    assert button.updated is True
    assert button._style.unpolished is True
    assert button._style.polished is True
