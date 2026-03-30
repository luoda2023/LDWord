import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.heading_quick_card import HeadingQuickCard
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.workbench_panel import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_heading_quick_card_exposes_summary_and_advanced_button():
    _app()
    card = HeadingQuickCard(PanelBridge())

    assert hasattr(card, "_summary_label")
    assert hasattr(card, "_advanced_btn")


def test_heading_quick_card_uses_concise_summary_and_shared_action_hooks():
    _app()
    card = HeadingQuickCard(PanelBridge())

    assert card._summary_label.text() == "标题方案：未读取"
    assert card._summary_label.objectName() == "wb_quick_card_summary"
    assert card._advanced_btn.objectName() == "wb_quick_card_action"


def test_heading_quick_card_click_emits_advanced_requested():
    _app()
    card = HeadingQuickCard(PanelBridge())
    advanced_calls = []
    card.advanced_requested.connect(lambda: advanced_calls.append(True))

    card._advanced_btn.click()

    assert advanced_calls == [True]


def test_heading_quick_card_can_update_summary_text():
    _app()
    card = HeadingQuickCard(PanelBridge())

    card.set_summary_text("summary: thesis-template")

    assert card._summary_label.text() == "summary: thesis-template"


def test_workbench_uses_heading_quick_card_instead_of_inline_full_editor():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert hasattr(panel, "_heading_quick_card")
        assert panel.findChild(HeadingNumberingPanel) is None
    finally:
        panel.close()
