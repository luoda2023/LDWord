import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.qt_api import QVBoxLayout
from src.qt_api import QWidget
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.sizing import (
    apply_size_class,
    normalize_form_control_heights,
    resolved_control_height,
)
from src.shared.ui.spacing_input import SpacingInput
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


def test_normalize_form_control_heights_unifies_mixed_inputs():
    app = _app()
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = StyledComboBox(host)
    combo.addItems(["A", "B"])
    spin = StyledSpinBox(host)
    spacing = SpacingInput(unit="", units=(), show_unit=False, parent=host)
    layout.addWidget(combo)
    layout.addWidget(spin)
    layout.addWidget(spacing)

    height = resolved_control_height(get_theme(), "md")
    normalize_form_control_heights(host, height)

    host.resize(360, 180)
    host.show()
    app.processEvents()

    try:
        assert combo.height() == height
        assert spin.height() == height
        assert spacing.height() == height
        assert spacing.spin_box.height() == height
    finally:
        host.close()
        app.processEvents()


def test_surface_card_module_builds_on_shared_rounded_surface():
    assert issubclass(SurfaceCard, RoundedSurfaceFrame)


def test_workbench_cards_use_direct_surface_card_foundation():
    assert issubclass(HeadingQuickCard, SurfaceCard)
    assert issubclass(QuickFillCard, SurfaceCard)
    assert issubclass(StrategyCard, SurfaceCard)
