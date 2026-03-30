import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.quick_fill_card import QuickFillCard
from src.ui.panels.workbench_panel import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_quick_fill_card_exposes_summary_and_actions():
    _app()
    bridge = PanelBridge()
    card = QuickFillCard(bridge)

    assert card._source_summary.text()
    assert card._entity_summary.text()
    assert card._quick_setup_btn.text()
    assert card._advanced_mapping_btn.text()
    assert card._bridge is bridge


def test_workbench_includes_quick_fill_as_default_homepage_card():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert hasattr(panel, "_quick_fill_card")
        assert panel._capability_grid.card_at(0, 1) is panel._quick_fill_card
    finally:
        panel.close()
