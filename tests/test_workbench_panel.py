import sys
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.main_window import MainWindow
from src.ui.panel_registry import PANEL_SPECS
from src.ui.panels.workbench_panel import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_main_window_registers_real_workbench_panel():
    _app()
    window = MainWindow()
    try:
        expected_index = next(i for i, spec in enumerate(PANEL_SPECS) if spec.id == "workbench")
        workbench_panel = window.panel_stack.widget(expected_index)
        assert isinstance(workbench_panel, WorkbenchPanel)
    finally:
        window.close()


def test_workbench_panel_exposes_navigation_components():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._navigation_rail.selected_card_id() == "quick_execute"
        assert panel._detail_stack.currentWidget() is panel._quick_execute_pane
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
