import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, Qt
from src.shared.ui.input_metrics import INPUT_EDITOR_TEXT_MARGIN_LEFT
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.numbering_preset import NumberingPreset
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
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
        assert editor.textMargins().left() == INPUT_EDITOR_TEXT_MARGIN_LEFT
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


def test_styled_combo_box_exposes_one_text_rect_for_static_and_editable_modes():
    app = _app()
    combo = StyledComboBox()

    try:
        combo.addItem("Word 自动目录")
        combo.resize(240, 32)
        combo.show()
        app.processEvents()

        static_rect = combo._input_text_rect()
        assert static_rect.x() == LIGHT.input_padding_x
        assert static_rect.height() == combo.height()
        assert static_rect.x() + static_rect.width() == combo.width() - LIGHT.combo_arrow_zone_width

        combo.setEditable(True)
        app.processEvents()
        editor = combo.lineEdit()

        assert editor is not None
        assert editor.geometry() == combo._input_text_rect()
    finally:
        combo.close()
        combo.deleteLater()


def test_styled_combo_box_keeps_single_text_renderer_per_mode():
    source = inspect.getsource(StyledComboBox)
    paint_source = inspect.getsource(StyledComboBox.paintEvent)

    assert "if not self.isEditable():" in paint_source
    assert "_paint_current_text" in paint_source
    assert "_editor_draws_own_text" not in source
    assert "color: transparent" not in source


def test_styled_combo_box_editor_stylesheet_keeps_native_text_visible():
    qss = StyledComboBox.build_editor_stylesheet(LIGHT)

    assert f"color: {LIGHT.text_primary};" in qss
    assert f"color: {LIGHT.text_hint};" in qss
    assert "QLineEdit::placeholder" in qss
    assert "color: transparent;" not in qss


def test_combo_and_spin_share_embedded_editor_geometry_helper():
    combo_sync = inspect.getsource(StyledComboBox._sync_editor_geometry)
    spin_sync = inspect.getsource(StyledSpinBox._sync_editor_geometry)

    assert "sync_input_line_edit_geometry" in combo_sync
    assert "sync_input_line_edit_geometry" in spin_sync
    assert "line_edit.setGeometry" not in combo_sync
    assert "line_edit.setGeometry" not in spin_sync


def test_spacing_input_uses_shared_unit_combo():
    source = inspect.getsource(SpacingInput.__init__)

    assert "StyledComboBox()" in source
    assert "QComboBox()" not in source


def test_heading_numbering_panel_uses_shared_combo_constructors():
    source = inspect.getsource(HeadingNumberingPanel)

    assert "StyledComboBox(self)" in source or "StyledComboBox(" in source
    assert "QComboBox()" not in source
