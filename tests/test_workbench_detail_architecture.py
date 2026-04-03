import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QScrollArea, QVBoxLayout, QWidget
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.detail_controller import WorkbenchDetailController
from src.ui.panels.workbench.feature_detail_panes import (
    CitationDetailPane,
    CleanupDetailPane,
    ContentDataDetailPane,
    FormulaDetailPane,
    PageElementsDetailPane,
    TableChartDetailPane,
)
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_panel_uses_detail_controller_for_detail_switching():
    panel_source = inspect.getsource(WorkbenchPanel)
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")

    assert "from .detail_controller import WorkbenchDetailController" in module_source
    assert "self._details = WorkbenchDetailController(" in panel_source
    assert "self._details.register_details(detail_map)" in panel_source
    assert "self._details.show_detail(card_id)" in panel_source


def test_detail_controller_owns_registration_and_visible_pane_switching():
    controller_source = inspect.getsource(WorkbenchDetailController)

    assert "def register_details" in controller_source
    assert "def show_detail" in controller_source
    assert "self._detail_layout.removeWidget" in controller_source
    assert "self._detail_scroll.verticalScrollBar().setValue(0)" in controller_source


def test_workbench_panel_keeps_current_detail_alias_in_sync():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._current_detail is panel._details.current_detail

        panel._nav_rail.select_card("config_management")

        assert panel._current_detail is panel._config_management_detail
        assert panel._current_detail is panel._details.current_detail
    finally:
        panel.close()


def test_detail_controller_reparents_and_hides_registered_details():
    app = _app()

    host = QWidget()
    scroll = QScrollArea(host)
    container = QWidget(scroll)
    layout = QVBoxLayout(container)
    scroll.setWidget(container)

    detail_a = QWidget(host)
    detail_b = QWidget(host)

    controller = WorkbenchDetailController(container, layout, scroll)
    controller.register_details({"a": detail_a, "b": detail_b})

    try:
        assert controller.current_detail is None
        assert detail_a.parent() is container
        assert detail_b.parent() is container
        assert detail_a.isHidden() is True
        assert detail_b.isHidden() is True

        controller.show_detail("a")
        app.processEvents()

        assert controller.current_detail is detail_a
        assert detail_a.parent() is container
        assert detail_b.parent() is container
        assert detail_a.isHidden() is False
        assert detail_b.isHidden() is True
    finally:
        host.close()


def test_workbench_panel_hides_unselected_details_inside_detail_container():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._current_detail is panel._quick_execution_detail

        for card_id, detail in panel._detail_map.items():
            assert detail.parent() is panel._detail_container
            if card_id == "quick_execute":
                assert detail.isHidden() is False
            else:
                assert detail.isHidden() is True
    finally:
        panel.close()


def test_workbench_panel_uses_semantic_capability_detail_panes():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert isinstance(panel._table_chart_detail, TableChartDetailPane)
        assert isinstance(panel._page_elements_detail, PageElementsDetailPane)
        assert isinstance(panel._formula_detail, FormulaDetailPane)
        assert isinstance(panel._citation_detail, CitationDetailPane)
        assert isinstance(panel._cleanup_detail, CleanupDetailPane)
        assert isinstance(panel._content_fill_detail, ContentDataDetailPane)
        assert panel._heading_numbering_detail is panel._table_chart_detail
        assert panel._quick_fill_detail is panel._content_fill_detail
    finally:
        panel.close()
