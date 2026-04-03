import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.workbench.execution_controller import WorkbenchExecutionController
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def test_workbench_panel_uses_execution_controller_for_worker_feedback_flow():
    panel_source = inspect.getsource(WorkbenchPanel)
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")

    assert "from .execution_controller import WorkbenchExecutionController" in module_source
    assert "self._execution = WorkbenchExecutionController(" in panel_source
    assert "self._execution.cancel_execution(" in panel_source
    assert "self._execution.prepare_worker(" in panel_source
    assert "self._execution.apply_execution_result(" in panel_source
    assert "def _clear_execution_worker" in panel_source


def test_execution_controller_owns_worker_signal_and_history_sync_logic():
    controller_source = inspect.getsource(WorkbenchExecutionController)

    assert "def prepare_worker" in controller_source
    assert "def cancel_execution" in controller_source
    assert "def apply_execution_result" in controller_source
    assert "def _wire_worker" in controller_source
    assert "def _sync_execution_history_progress" in controller_source
    assert "def _sync_execution_history_result" in controller_source
    assert "def _on_execution_finished" in controller_source
