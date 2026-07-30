import logging
import sys
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.main_window import MainWindow
from src.ui.panel_registry import OPTIONAL_PANEL_SPECS, PANEL_SPECS, create_panel
from src.ui.panels.workbench import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_main_window_registers_real_workbench_panel():
    _app()
    window = MainWindow()
    try:
        expected_index = next(i for i, spec in enumerate(PANEL_SPECS) if spec.id == "workbench")
        workbench_panel = window.panel_stack.widget(expected_index)
        assert isinstance(workbench_panel, WorkbenchPanel)
        assert workbench_panel._batch_generation_detail is not None
        assert "batch_generate" in workbench_panel._navigation_cards
    finally:
        window.close()


def test_main_window_keeps_theme_in_core_navigation_and_assets_optional():
    _app()
    window = MainWindow()
    try:
        panel_ids = tuple(spec.id for spec in PANEL_SPECS)
        optional_ids = tuple(spec.id for spec in OPTIONAL_PANEL_SPECS)
        assert "assets" not in panel_ids
        assert optional_ids == ("assets",)
        assert panel_ids[-2:] == ("theme", "preferences")
        assert window.panel_stack.count() == len(PANEL_SPECS)

        theme_index = panel_ids.index("theme")
        theme_panel = window._show_panel(theme_index, allow_async=False)
        assert theme_panel.__class__.__name__ == "ThemePanel"
    finally:
        window.close()


def test_workbench_panel_exposes_navigation_components():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._nav_rail.selected_card_id() == "quick_execute"
        assert panel._current_detail is panel._quick_execution_detail
        assert "batch_generate" in panel._navigation_cards
        panel._nav_rail.select_card("batch_generate")
        assert panel._current_detail is panel._batch_generation_detail
    finally:
        panel.close()


def test_optional_main_window_adds_assets_without_changing_core_workbench():
    _app()
    window = MainWindow(include_optional_panels=True)
    try:
        workbench_panel = window.panel_stack.widget(0)
        assert isinstance(workbench_panel, WorkbenchPanel)
        assert workbench_panel._batch_generation_detail is not None
        assert "batch_generate" in workbench_panel._navigation_cards
        assert [spec.id for spec in window._panel_specs].count("theme") == 1
        assert "assets" in {spec.id for spec in window._panel_specs}
    finally:
        window.close()


def test_legacy_optional_feature_flag_cannot_hide_batch_generation():
    _app()
    panel = create_panel(
        "workbench",
        PanelBridge(),
        include_optional_features=False,
    )
    try:
        assert isinstance(panel, WorkbenchPanel)
        assert panel._batch_generation_detail is not None
        assert "batch_generate" in panel._navigation_cards
    finally:
        panel.close()


def test_workbench_removes_ai_shortcut_from_quick_execution():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        ids = [spec.id for spec in PANEL_SPECS]
        assert "assistant" in ids
        assert "assistant_home" not in panel._detail_map
        assert not hasattr(panel, "_assistant_panel")
        assert not hasattr(panel._quick_execution_detail, "_assistant_btn")
        assert not hasattr(panel._quick_execution_detail, "assistant_requested")
    finally:
        panel.close()


def test_workbench_panel_uses_bridge_reference_without_task_2_behavior():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        assert panel.bridge is bridge
        assert panel.objectName() == "WorkbenchPanel"
    finally:
        panel.close()


def test_workbench_execution_adapter_import_is_not_blocked_by_panels_package_reexports():
    script = (
        "import sys; "
        f"sys.path.insert(0, r'{ROOT}'); "
        "from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter; "
        "print(WorkbenchExecutionAdapter.__name__)"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "WorkbenchExecutionAdapter"


def test_main_window_close_ignored_when_panel_shutdown_fails():
    app = _app()
    window = MainWindow()
    failing_panel = None
    try:
        from src.qt_api import QWidget

        class _FailingPanel(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.calls = []

            def shutdown_active_execution(self, timeout_ms: int | None = None) -> bool:
                self.calls.append(timeout_ms)
                return False

        failing_panel = _FailingPanel()
        window.register_panel(0, failing_panel)

        window.show()
        app.processEvents()
        assert window.isVisible()

        assert window.close() is False
        app.processEvents()
        assert window.isVisible()
    finally:
        # Ensure the test can clean up the window even if the close was blocked.
        if failing_panel is not None:
            failing_panel.shutdown_active_execution = lambda timeout_ms=None: True
        window.close()


def test_main_window_close_requests_workbench_shutdown_before_closing():
    app = _app()
    window = MainWindow()
    workbench_panel = None
    try:
        expected_index = next(i for i, spec in enumerate(PANEL_SPECS) if spec.id == "workbench")
        workbench_panel = window.panel_stack.widget(expected_index)
        assert isinstance(workbench_panel, WorkbenchPanel)

        class _FakeThread:
            def isRunning(self) -> bool:
                return False

        class _FakeExecutionHandle:
            def __init__(self):
                self._thread = _FakeThread()
                self.cancel_requests = 0
                self.shutdown_calls = []

            def request_cancel(self) -> None:
                self.cancel_requests += 1

            def shutdown(self, timeout_ms: int | None = 1000) -> None:
                self.shutdown_calls.append(timeout_ms)

        handle = _FakeExecutionHandle()
        workbench_panel._execution_worker = handle

        window.show()
        app.processEvents()

        assert window.close() is True
        assert handle.cancel_requests == 1
        assert handle.shutdown_calls
    finally:
        if workbench_panel is not None:
            workbench_panel._execution_worker = None
        window.close()


def test_main_window_close_logs_shutdown_exception_before_blocking_close(caplog):
    app = _app()
    window = MainWindow()
    failing_panel = None
    try:
        from src.qt_api import QWidget

        class _ExplodingPanel(QWidget):
            def shutdown_active_execution(self, timeout_ms: int | None = None) -> bool:
                raise RuntimeError("shutdown boom")

        failing_panel = _ExplodingPanel()
        window.register_panel(0, failing_panel)

        window.show()
        app.processEvents()

        with caplog.at_level(logging.WARNING):
            assert window.close() is False
            app.processEvents()

        assert any("panel shutdown at index 0" in record.getMessage() for record in caplog.records)
    finally:
        if failing_panel is not None:
            failing_panel.shutdown_active_execution = lambda timeout_ms=None: True
        window.close()


def test_main_window_close_logs_panel_stack_count_failure_and_still_closes(caplog):
    app = _app()
    window = MainWindow()
    original_stack = window.panel_stack
    try:
        class _BrokenStack:
            def count(self):
                raise RuntimeError("count boom")

        window.panel_stack = _BrokenStack()
        window.show()
        app.processEvents()

        with caplog.at_level(logging.WARNING):
            assert window.close() is True
            app.processEvents()

        assert any("panel stack count" in record.getMessage() for record in caplog.records)
    finally:
        window.panel_stack = original_stack
        window.close()
