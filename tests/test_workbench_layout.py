# -*- coding: utf-8 -*-
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.theme import get_theme
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench import WorkbenchPanel
from src.ui.panels.workbench.command_bar import TaskCommandBar
from src.ui.panels.workbench.state import CurrentTaskState
from src.ui.panels.workbench.styles import build_workbench_stylesheet


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_panel_uses_the_package_entry_point():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel.__class__.__name__ == "WorkbenchPanel"
        assert panel.objectName() == "WorkbenchPanel"
        assert WorkbenchPanel is type(panel)
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


def test_workbench_panel_starts_with_all_fixed_workbench_functions():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert list(panel._navigation_cards) == [
            "quick_execute",
            "batch_generate",
            "material_suite_generate",
        ]
        assert not hasattr(panel, "_config_management_detail")
    finally:
        panel.close()


def test_workbench_keeps_one_panel_implementation() -> None:
    package_dir = ROOT / "src" / "ui" / "panels" / "workbench"
    package_source = (package_dir / "__init__.py").read_text(encoding="utf-8")

    assert not (package_dir / "panel.py").exists()
    assert not (package_dir / "detail_controller.py").exists()
    assert not (package_dir / "scene_presets.py").exists()
    assert not (package_dir.parent / "workbench_panel.py").exists()
    assert "LegacyWorkbenchPanel" not in package_source
    assert "WorkbenchPanelV2" not in package_source


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


def test_dynamic_navigation_feature_diff_preserves_selection_identity_and_order():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel._quick_execution_detail.set_feature_enabled("formula", True)
        formula_card = panel._navigation_cards["formula"]
        header = panel._navigation.dynamic_section_header
        panel._nav_rail.select_card("formula")
        selection_events: list[str] = []
        panel._nav_rail.card_selected.connect(selection_events.append)

        # table_chart is ordered before formula, but enabling it must move only
        # layout items and leave the selected formula card alive.
        panel._quick_execution_detail.set_feature_enabled("table_chart", True)

        assert panel._navigation_cards["formula"] is formula_card
        assert panel._navigation.dynamic_section_header is header
        assert panel._nav_rail.selected_card_id() == "formula"
        assert selection_events == []
        header_index = panel._nav_rail._layout.indexOf(header)
        assert panel._nav_rail._layout.itemAt(header_index + 1).widget() is panel._navigation_cards["table_chart"]
        assert panel._nav_rail._layout.itemAt(header_index + 2).widget() is formula_card

        table_card = panel._navigation_cards["table_chart"]
        panel._quick_execution_detail.set_feature_enabled("table_chart", False)

        assert "table_chart" not in panel._navigation_cards
        assert panel._navigation_cards["formula"] is formula_card
        assert panel._navigation.dynamic_section_header is header
        assert panel._nav_rail.selected_card_id() == "formula"
        assert selection_events == []
        assert table_card is not formula_card
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
        assert bar.layout().spacing() == 8
    finally:
        bar.close()


def test_workbench_stylesheet_includes_v3_shell_selectors():
    theme = get_theme()
    stylesheet = build_workbench_stylesheet(theme)

    assert "#wb_navigation_rail" in stylesheet
    assert "#wb_detail_stack" in stylesheet
    assert "#wb_quick_execute_pane" in stylesheet
    assert "#wb_config_management_pane" not in stylesheet
    assert "#wb_config_management_title" not in stylesheet
    assert "#wb_config_management_description" not in stylesheet
    assert "#wb_command_center_subtitle" in stylesheet
