import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, Qt
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.numbering_preset import NumberingPreset
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import LIGHT
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def _app():
    return QApplication.instance() or QApplication([])


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


def test_styled_combo_box_normalizes_editable_editor_text_inset():
    app = _app()
    combo = StyledComboBox()

    try:
        combo.resize(240, 32)
        combo.setEditable(True)
        combo.show()
        app.processEvents()
        editor = combo.lineEdit()

        assert editor is not None
        assert editor.alignment() & Qt.AlignLeft
        assert editor.alignment() & Qt.AlignVCenter
        assert not editor.hasFrame()
        assert editor.textMargins().left() == 0
        assert editor.textMargins().right() == 0
        assert editor.minimumHeight() == 0
        assert editor.maximumHeight() == combo.height()
        assert editor.geometry().x() == LIGHT.input_padding_x
        assert editor.geometry().height() == combo.height()
        assert editor.geometry().x() + editor.geometry().width() == combo.width() - LIGHT.combo_arrow_zone_width
        assert "padding: 0;" in editor.styleSheet()
    finally:
        combo.close()
        combo.deleteLater()


def test_spacing_input_uses_shared_unit_combo():
    source = inspect.getsource(SpacingInput.__init__)

    assert "StyledComboBox()" in source
    assert "QComboBox()" not in source


def test_heading_numbering_panel_uses_shared_combo_constructors():
    source = inspect.getsource(HeadingNumberingPanel)

    assert "StyledComboBox(self)" in source or "StyledComboBox(" in source
    assert "QComboBox()" not in source
