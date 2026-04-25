import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.execution_session_controller import WorkbenchExecutionSessionController
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_panel_uses_execution_session_controller_for_worker_lifecycle():
    panel_source = inspect.getsource(WorkbenchPanel)
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")

    assert "from .execution_session_controller import WorkbenchExecutionSessionController" in module_source
    assert "self._execution_session = WorkbenchExecutionSessionController(" in panel_source
    assert "return self._execution_session.active_worker" in panel_source
    assert "self._execution_session.shutdown_active_execution(" in panel_source
    assert "build = self._execution_session.build_worker(" in panel_source
    assert "session_overrides=self._quick_execution_detail.runtime_template_overrides()," in panel_source
    assert "self._execution_session.start_worker(worker)" in panel_source


def test_execution_session_controller_owns_handle_build_start_and_shutdown_logic():
    module_source = (ROOT / "src/ui/panels/workbench/execution_session_controller.py").read_text(encoding="utf-8")
    controller_source = inspect.getsource(WorkbenchExecutionSessionController)

    assert "class ExecutionBuildResult" in module_source
    assert "def build_worker" in controller_source
    assert "ThreadedExecutionHandle(" in module_source
    assert "session_overrides=session_overrides" in module_source
    assert "def start_worker" in controller_source
    assert "def shutdown_active_execution" in controller_source
    assert "def clear_active_worker" in controller_source


def test_execution_worker_alias_tracks_session_controller_state():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        handle = object()

        panel._execution_worker = handle

        assert panel._execution_worker is handle
        assert panel._execution_session.active_worker is handle

        panel._clear_execution_worker()

        assert panel._execution_worker is None
        assert panel._execution_session.active_worker is None
    finally:
        panel.close()


def test_start_execution_passes_runtime_overrides_into_session_build_worker():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        expected_overrides = {"header_footer.suppress_header_footer_selectors": ["cover", "toc"]}

        class _BuildResult:
            def __init__(self, worker):
                self.worker = worker
                self.cancelled = False
                self.already_running = False

        class _FakeSession:
            def __init__(self):
                self.active_worker = None
                self.build_kwargs = None
                self.start_calls = []

            def set_active_worker(self, worker):
                self.active_worker = worker

            def build_worker(self, **kwargs):
                self.build_kwargs = dict(kwargs)
                return _BuildResult(worker=object())

            def start_worker(self, worker):
                self.start_calls.append(worker)

            def shutdown_active_execution(self, timeout_ms=1000):
                return True

        class _FakeExecution:
            def __init__(self):
                self.prepared = []

            def prepare_worker(self, worker):
                self.prepared.append(worker)

        fake_session = _FakeSession()
        fake_execution = _FakeExecution()

        panel._execution_session = fake_session
        panel._execution = fake_execution
        panel._quick_execution_detail.runtime_template_overrides = lambda: dict(expected_overrides)

        panel._start_execution()

        assert fake_session.build_kwargs is not None
        assert fake_session.build_kwargs["session_overrides"] == expected_overrides
        assert fake_session.start_calls
        assert fake_execution.prepared
        assert fake_session.active_worker is fake_execution.prepared[0]
    finally:
        panel.close()
