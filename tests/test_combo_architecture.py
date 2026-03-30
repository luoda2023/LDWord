import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.font_combo import FontCombo
from src.shared.ui.numbering_preset import NumberingPreset
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import LIGHT
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def test_styled_combo_box_uses_combo_tokens():
    qss = StyledComboBox.build_combo_stylesheet("combo_id", LIGHT)

    assert "#combo_id" in qss
    assert f"padding-right: {LIGHT.combo_arrow_zone_width}px;" in qss
    assert f"width: {LIGHT.combo_arrow_zone_width}px;" in qss
    assert f"border-radius: {LIGHT.input_radius}px;" in qss


def test_styled_combo_box_arrow_metrics_are_tokenized():
    assert LIGHT.combo_arrow_zone_width > LIGHT.combo_arrow_size
    assert LIGHT.combo_popup_offset_y >= 0


def test_combo_widgets_inherit_shared_base():
    assert issubclass(FontCombo, StyledComboBox)
    assert issubclass(SizeCombo, StyledComboBox)
    assert issubclass(NumberingPreset, StyledComboBox)


def test_spacing_input_uses_shared_unit_combo():
    source = inspect.getsource(SpacingInput.__init__)

    assert "StyledComboBox()" in source
    assert "QComboBox()" not in source


def test_heading_numbering_panel_uses_shared_combo_constructors():
    source = inspect.getsource(HeadingNumberingPanel)

    assert "StyledComboBox()" in source
    assert "QComboBox()" not in source
