# -*- coding: utf-8 -*-
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.theme import get_theme
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench import WorkbenchPanel as PackageWorkbenchPanel
from src.ui.panels.workbench.command_bar import TaskCommandBar
from src.ui.panels.workbench_panel import WorkbenchPanel
from src.ui.panels.workbench.state import CurrentTaskState
from src.ui.panels.workbench.styles import build_workbench_stylesheet


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_panel_import_path_stays_stable_after_package_split():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel.__class__.__name__ == "WorkbenchPanel"
        assert panel.objectName() == "WorkbenchPanel"
        assert PackageWorkbenchPanel is WorkbenchPanel
    finally:
        panel.close()


def test_workbench_panel_uses_v2_master_detail_shell():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert hasattr(panel, "_nav_rail")
        assert hasattr(panel, "_detail_scroll")
        assert panel._nav_rail.selected_card_id() == "quick_execute"
        assert panel._current_detail is panel._quick_execution_detail
    finally:
        panel.close()


def test_workbench_panel_starts_with_fixed_cards_only():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert list(panel._navigation_cards) == ["quick_execute", "config_management"]
    finally:
        panel.close()


def test_navigation_selection_switches_detail_pane():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel._nav_rail.select_card("config_management")
        assert panel._current_detail is panel._config_management_detail
    finally:
        panel.close()


def test_enabling_feature_adds_dynamic_navigation_card():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel._quick_execution_detail.set_feature_enabled("content_fill", True)

        assert "content_fill" in panel._navigation_cards
        panel._nav_rail.select_card("content_fill")
        assert panel._current_detail is panel._content_fill_detail
    finally:
        panel.close()


def test_disabling_feature_removes_dynamic_navigation_card():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel._quick_execution_detail.set_feature_enabled("content_fill", True)
        assert "content_fill" in panel._navigation_cards

        panel._quick_execution_detail.set_feature_enabled("content_fill", False)

        assert "content_fill" not in panel._navigation_cards
    finally:
        panel.close()


def test_summary_refresh_does_not_recreate_existing_dynamic_navigation_cards():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel._quick_execution_detail.set_feature_enabled("content_fill", True)
        original_card = panel._navigation_cards["content_fill"]

        panel._quick_execution_detail.set_document_path("C:/docs/thesis.docx")

        assert panel._navigation_cards["content_fill"] is original_card
    finally:
        panel.close()


def test_task_command_bar_renders_document_strategy_and_ready_status():
    _app()
    bar = TaskCommandBar()
    assert bar.objectName() == "wb_command_bar"
    assert not bar._run_button.isEnabled()
    assert bar._status_value.text() == "待执行"
    state = CurrentTaskState(
        document_label="thesis.docx",
        strategy_label="论文标准",
        ready=True,
        status_text="待执行",
    )

    bar.set_state(state)

    assert bar._doc_value.text() == "thesis.docx"
    assert bar._strategy_value.text() == "论文标准"
    assert bar._status_value.text() == "待执行"
    assert bar._run_button.isEnabled()


def test_task_command_bar_uses_compact_strip_spacing():
    _app()
    bar = TaskCommandBar()
    try:
        margins = bar.layout().contentsMargins()

        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (16, 10, 16, 10)
        assert bar.layout().spacing() == 12
    finally:
        bar.close()


def test_workbench_stylesheet_includes_v3_shell_selectors():
    theme = get_theme()
    stylesheet = build_workbench_stylesheet(theme)

    assert "#wb_navigation_rail" in stylesheet
    assert "#wb_detail_stack" in stylesheet
    assert "#wb_quick_execute_pane" in stylesheet
    assert "#wb_config_management_pane" in stylesheet
    assert "#wb_config_management_title" in stylesheet
    assert "#wb_config_management_description" in stylesheet
    assert "#wb_command_center_subtitle" in stylesheet
