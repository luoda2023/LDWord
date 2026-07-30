import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.quick_fill_card import QuickFillCard
from src.ui.panels.workbench import WorkbenchPanel


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


def test_quick_fill_card_uses_shared_summary_and_action_hooks():
    _app()
    card = QuickFillCard(PanelBridge())

    assert card._source_summary.text() == "填充源：未连接"
    assert card._entity_summary.text() == "实体：未选择"
    assert card._source_summary.objectName() == "wb_quick_card_summary"
    assert card._entity_summary.objectName() == "wb_quick_card_summary"
    assert card._quick_setup_btn.objectName() == "wb_quick_card_action"
    assert card._advanced_mapping_btn.objectName() == "wb_quick_card_action_secondary"


def test_workbench_exposes_content_fill_via_dynamic_navigation_card():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel._quick_execution_detail.set_feature_enabled("content_fill", True)

        assert "content_fill" in panel._navigation_cards
        panel._nav_rail.select_card("content_fill")
        assert panel._current_detail is panel._content_fill_detail
    finally:
        panel.close()
