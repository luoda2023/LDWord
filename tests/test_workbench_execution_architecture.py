import ast
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from src.ui.panels.workbench.execution_controller import WorkbenchExecutionController
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def test_workbench_panel_uses_execution_controller_for_worker_feedback_flow():
    panel_source = inspect.getsource(WorkbenchPanel)
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")

    assert "from .execution_controller import WorkbenchExecutionController" in module_source
    assert "self._execution = WorkbenchExecutionController(" in panel_source
    assert (
        "self._quick_execution_detail.cancel_requested.connect(self._cancel_execution)"
        in panel_source
    )
    assert "self._execution.cancel_execution(" in panel_source
    assert "self._execution.prepare_worker(" in panel_source
    assert "self._execution.apply_execution_result(" in panel_source
    assert "def _clear_execution_worker" in panel_source


def test_execution_controller_owns_worker_signal_and_quick_feedback_logic():
    controller_source = inspect.getsource(WorkbenchExecutionController)

    assert "def prepare_worker" in controller_source
    assert "def cancel_execution" in controller_source
    assert "def apply_execution_result" in controller_source
    assert "def _wire_worker" in controller_source
    assert "execution_history" not in controller_source
    assert "def _on_execution_finished" in controller_source
    assert "terminal_payload=result" in controller_source
    assert "dict(result" not in controller_source
    assert "batch_issue_items=" not in controller_source
    assert "question_figure_repair_queue=" not in controller_source


def test_execution_controller_preserves_cancelled_result_payload():
    adapter_payloads: list[dict[str, object]] = []
    detail_results: list[dict[str, object]] = []

    class _Adapter:
        def build_result_state(self, *, terminal_payload):
            adapter_payloads.append(terminal_payload)
            return terminal_payload

    class _Detail:
        def set_execution_result(self, result):
            detail_results.append(result)

    controller = WorkbenchExecutionController(
        _Adapter(),
        _Detail(),
        refresh_quick_execute_card=lambda: None,
        clear_execution_worker=lambda: None,
        has_ready_document=lambda: True,
    )
    payload = {
        "status": "cancelled",
        "output_path": "published.docx",
        "output_paths": {"final": "published.docx"},
        "report_paths": ["batch.json"],
        "batch_isolation": {"completed_count": 1},
        "material_package_receipt": {"status": "incomplete"},
        "material_package_receipts": {
            "profile-a": {"status": "complete"},
        },
        "exam_markdown_import": {"summary": {"question_count": 2}},
        "future_extension": {"kept": True},
    }

    controller._on_execution_cancelled(payload)

    assert adapter_payloads == [payload]
    assert detail_results == [payload]
    assert adapter_payloads[0]["material_package_receipts"] == {
        "profile-a": {"status": "complete"}
    }
    assert adapter_payloads[0]["exam_markdown_import"] == {
        "summary": {"question_count": 2}
    }
    assert adapter_payloads[0]["future_extension"] == {"kept": True}


def test_execution_result_state_preserves_material_package_receipts():
    receipt = {"status": "incomplete", "detail": {"reason": "missing"}}
    state = WorkbenchExecutionAdapter().build_result_state(
        terminal_payload={
            "status": "success",
            "output_path": "",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
            "material_package_receipt": receipt,
            "material_package_receipts": {
                "profile-a": {"status": "complete"},
            },
        }
    )
    receipt["detail"]["reason"] = "mutated"

    assert state.material_package_receipt == {
        "status": "incomplete",
        "detail": {"reason": "missing"},
    }
    assert state.material_package_receipts == {
        "profile-a": {"status": "complete"}
    }
    assert state.terminal_payload["material_package_receipt"] == (
        state.material_package_receipt
    )


def test_execution_result_and_recent_state_preserve_complete_terminal_payload():
    adapter = WorkbenchExecutionAdapter()
    terminal_payload = {
        "status": "partial_success",
        "output_path": "output.docx",
        "report_paths": [],
        "failed_count": 0,
        "artifact_failure_count": 1,
        "error_text": "disk full",
        "exam_markdown_import": {"summary": {"question_count": 2}},
        "artifact_failures": [
            {
                "kind": "report_json",
                "path": "report.json",
                "error_type": "OSError",
                "error": "disk full",
            }
        ],
        "execution_session": {
            "input_ref": {"frozen_revision": "sha256:" + "a" * 64}
        },
        "future_extension": {"kept": True},
    }
    state = adapter.build_result_state(terminal_payload=terminal_payload)
    terminal_payload["future_extension"]["kept"] = False
    terminal_payload["execution_session"]["input_ref"]["frozen_revision"] = (
        "sha256:" + "b" * 64
    )

    assert state.terminal_payload["future_extension"] == {"kept": True}
    assert state.execution_session["input_ref"]["frozen_revision"] == (
        "sha256:" + "a" * 64
    )
    state.execution_session["input_ref"]["frozen_revision"] = (
        "sha256:" + "c" * 64
    )
    assert state.terminal_payload["execution_session"]["input_ref"][
        "frozen_revision"
    ] == ("sha256:" + "a" * 64)

    recent = adapter.build_recent_run_state(state)
    assert recent.terminal_payload == state.terminal_payload
    assert recent.execution_session["input_ref"]["frozen_revision"] == (
        "sha256:" + "a" * 64
    )
    state.terminal_payload["execution_session"]["input_ref"][
        "frozen_revision"
    ] = ("sha256:" + "d" * 64)
    recent.execution_session["input_ref"]["frozen_revision"] = (
        "sha256:" + "e" * 64
    )
    assert recent.terminal_payload["execution_session"]["input_ref"][
        "frozen_revision"
    ] == ("sha256:" + "a" * 64)


def test_execution_result_state_rejects_execution_session_shape_divergence():
    adapter = WorkbenchExecutionAdapter()

    with pytest.raises(
        TypeError,
        match="execution_session.*must be a mapping",
    ):
        adapter.build_result_state(
            terminal_payload={
                "status": "success",
                "execution_session": ["wrong-shape"],
            },
        )


def test_execution_result_state_requires_one_mapping_terminal_payload():
    signature = inspect.signature(WorkbenchExecutionAdapter.build_result_state)

    assert tuple(signature.parameters) == ("self", "terminal_payload")
    assert (
        signature.parameters["terminal_payload"].kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    adapter = WorkbenchExecutionAdapter()
    with pytest.raises(TypeError, match="Terminal payload must be a mapping"):
        adapter.build_result_state(terminal_payload=["wrong-shape"])


def test_execution_controller_does_not_coerce_non_mapping_terminal_payload():
    class _Detail:
        def set_execution_result(self, _result):
            raise AssertionError("invalid terminal payload must not reach the detail")

    controller = WorkbenchExecutionController(
        WorkbenchExecutionAdapter(),
        _Detail(),
        refresh_quick_execute_card=lambda: None,
        clear_execution_worker=lambda: None,
        has_ready_document=lambda: True,
    )

    with pytest.raises(TypeError, match="Terminal payload must be a mapping"):
        controller.apply_execution_result([("status", "success")])


def test_execution_runtime_is_a_qt_free_frozen_snapshot_boundary():
    runtime_path = ROOT / "src/services/production_runtime/execution_runtime.py"
    runtime_source = runtime_path.read_text(encoding="utf-8")
    runtime_tree = ast.parse(runtime_source)

    imported_modules = {
        node.module
        for node in ast.walk(runtime_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(runtime_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "ExecutionMaterialSnapshot" in runtime_source
    assert "material_snapshot: ExecutionMaterialSnapshot | None" in runtime_source
    assert "MaterialExecutionContext" not in runtime_source
    assert "material_context" not in runtime_source
    assert "src.application.materials" in imported_modules
    assert not any(module.startswith("src.ui") for module in imported_modules)
    assert not any(module.startswith("src.qt_api") for module in imported_modules)
    assert "PySide6" not in runtime_source


def test_execution_runtime_delegates_to_canonical_pipeline_and_source_services():
    runtime_source = (
        ROOT / "src/services/production_runtime/execution_runtime.py"
    ).read_text(encoding="utf-8")

    assert "Pipeline(" in runtime_source
    assert "load_exam_markdown_source(" in runtime_source
    assert "build_exam_delivery_runtime(" in runtime_source
    assert "load_official_draft_source(" in runtime_source
    assert "resolve_config(" in runtime_source
    for retired_module in (
        "material_preflight",
        "exam_question_assets",
        "delivery_runtime",
        "batch_reporting",
        "question_figure_repair_runtime",
    ):
        assert f"production_runtime.{retired_module}" not in runtime_source
        assert f"from .{retired_module} import" not in runtime_source
    assert "finalize_result_artifacts(" in runtime_source
    assert "material_artifact_payload(" in runtime_source


def test_execution_runtime_surface_stays_bounded():
    runtime_path = ROOT / "src/services/production_runtime/execution_runtime.py"
    runtime_source = runtime_path.read_text(encoding="utf-8")
    runtime_tree = ast.parse(runtime_source)
    runtime_classes = {
        node.name for node in runtime_tree.body if isinstance(node, ast.ClassDef)
    }
    runtime_functions = {
        node.name for node in runtime_tree.body if isinstance(node, ast.FunctionDef)
    }

    assert len(runtime_source.splitlines()) <= 425
    assert runtime_classes == {"WorkbenchProductionRunner"}
    assert runtime_functions == {"_failed", "_cancelled"}
