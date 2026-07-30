import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, Qt
from src.qt_api import QWidget
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.sizing import (
    apply_size_class,
)
from src.shared.ui.input_metrics import INPUT_EDITOR_TEXT_MARGIN_LEFT
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.theme import get_theme
from src.shared.ui.surface_card import SurfaceCard
from src.ui.panels.workbench.heading_quick_card import HeadingQuickCard
from src.ui.panels.workbench.quick_fill_card import QuickFillCard
from src.ui.panels.workbench.strategy_card import StrategyCard


def _app():
    return QApplication.instance() or QApplication([])


def test_apply_size_class_sets_dynamic_property_for_qss_sizing():
    _app()
    widget = QWidget()

    apply_size_class(widget, "md")

    assert widget.property("sizeClass") == "md"


def test_styled_spin_box_normalizes_editor_text_inset():
    app = _app()
    spin = StyledSpinBox()

    try:
        spin.resize(240, 32)
        spin.show()
        app.processEvents()
        editor = spin.lineEdit()
        theme = get_theme()

        assert editor is not None
        assert editor.alignment() & Qt.AlignLeft
        assert editor.alignment() & Qt.AlignVCenter
        assert not editor.hasFrame()
        assert editor.textMargins().left() == INPUT_EDITOR_TEXT_MARGIN_LEFT
        assert editor.geometry().x() == theme.input_padding_x
        assert editor.geometry().height() == spin.height()
        assert editor.geometry().x() + editor.geometry().width() == spin.width() - theme.spin_button_width
    finally:
        spin.close()
        spin.deleteLater()


def test_surface_card_module_builds_on_shared_rounded_surface():
    assert issubclass(SurfaceCard, RoundedSurfaceFrame)


def test_workbench_cards_use_direct_surface_card_foundation():
    assert issubclass(HeadingQuickCard, SurfaceCard)
    assert issubclass(QuickFillCard, SurfaceCard)
    assert issubclass(StrategyCard, SurfaceCard)
