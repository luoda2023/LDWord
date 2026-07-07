import ast
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
    assert "对象预检明细" in controller_source
    assert "batch_issue_items=list(payload.get(\"batch_issue_items\") or [])" in controller_source
    assert "payload.get(\"question_figure_repair_queue\")" in controller_source


def test_workbench_material_preflight_logic_lives_in_dedicated_module():
    runtime_path = ROOT / "src/ui/panels/workbench/execution_runtime.py"
    preflight_path = ROOT / "src/ui/panels/workbench/material_preflight.py"
    runtime_source = runtime_path.read_text(encoding="utf-8")
    preflight_source = preflight_path.read_text(encoding="utf-8")

    runtime_functions = {
        node.name
        for node in ast.parse(runtime_source).body
        if isinstance(node, ast.FunctionDef)
    }
    preflight_functions = {
        node.name
        for node in ast.parse(preflight_source).body
        if isinstance(node, ast.FunctionDef)
    }

    moved_runtime_functions = {
        "_material_requirement_diagnostics",
        "_question_figure_file_diagnostics",
        "_question_figure_manual_comparison_issue_diagnostic",
        "_question_figure_filename_mismatch",
        "_question_figure_item_repair_target_key",
        "_missing_asset_rule_diagnostics",
        "_material_context_asset_roles",
        "_material_failure_policy",
        "_material_preflight_error_text",
    }
    expected_preflight_functions = {
        "material_requirement_diagnostics",
        "question_figure_file_diagnostics",
        "missing_asset_rule_diagnostics",
        "material_context_asset_roles",
        "material_failure_policy",
        "material_preflight_error_text",
    }

    assert moved_runtime_functions.isdisjoint(runtime_functions)
    assert expected_preflight_functions <= preflight_functions
    assert "from .material_preflight import" in runtime_source
    assert "PySide6" not in preflight_source


def test_workbench_exam_question_asset_runtime_lives_in_dedicated_module():
    runtime_path = ROOT / "src/ui/panels/workbench/execution_runtime.py"
    exam_assets_path = ROOT / "src/ui/panels/workbench/exam_question_assets.py"
    runtime_source = runtime_path.read_text(encoding="utf-8")
    exam_assets_source = exam_assets_path.read_text(encoding="utf-8")

    runtime_functions = {
        node.name
        for node in ast.parse(runtime_source).body
        if isinstance(node, ast.FunctionDef)
    }
    exam_asset_functions = {
        node.name
        for node in ast.parse(exam_assets_source).body
        if isinstance(node, ast.FunctionDef)
    }

    moved_runtime_functions = {
        "_material_context_with_exam_question_assets",
        "_coerce_exam_material_payload",
        "_inject_question_figure_assets",
        "_append_question_figure_payload",
        "_question_figure_payload_from_asset",
        "_iter_exam_question_payloads",
        "_question_has_figure_path",
    }
    expected_exam_asset_functions = {
        "material_context_with_exam_question_assets",
        "inject_question_figure_assets",
    }

    assert moved_runtime_functions.isdisjoint(runtime_functions)
    assert expected_exam_asset_functions <= exam_asset_functions
    assert "from .exam_question_assets import" in runtime_source
    assert "PySide6" not in exam_assets_source


def test_workbench_material_artifacts_live_in_dedicated_module():
    runtime_path = ROOT / "src/ui/panels/workbench/execution_runtime.py"
    artifacts_path = ROOT / "src/ui/panels/workbench/material_artifacts.py"
    runtime_source = runtime_path.read_text(encoding="utf-8")
    artifacts_source = artifacts_path.read_text(encoding="utf-8")

    runtime_functions = {
        node.name
        for node in ast.parse(runtime_source).body
        if isinstance(node, ast.FunctionDef)
    }
    artifact_functions = {
        node.name
        for node in ast.parse(artifacts_source).body
        if isinstance(node, ast.FunctionDef)
    }

    moved_runtime_functions = {
        "_write_material_manifest",
        "_write_material_package_artifacts",
        "_material_manifest_payload",
        "_material_manifest_asset_item_payload",
        "_render_material_archive_report",
        "_write_package_zip",
    }
    expected_artifact_functions = {
        "_write_material_manifest",
        "_write_material_package_artifacts",
        "_material_manifest_payload",
        "_render_material_archive_report",
    }

    assert moved_runtime_functions.isdisjoint(runtime_functions)
    assert expected_artifact_functions <= artifact_functions
    assert "from .material_artifacts import" in runtime_source
    assert "PySide6" not in artifacts_source


def test_workbench_question_figure_repair_runtime_lives_in_dedicated_module():
    runtime_path = ROOT / "src/ui/panels/workbench/execution_runtime.py"
    repair_runtime_path = (
        ROOT / "src/ui/panels/workbench/question_figure_repair_runtime.py"
    )
    runtime_source = runtime_path.read_text(encoding="utf-8")
    repair_runtime_source = repair_runtime_path.read_text(encoding="utf-8")

    runtime_functions = {
        node.name
        for node in ast.parse(runtime_source).body
        if isinstance(node, ast.FunctionDef)
    }
    repair_runtime_functions = {
        node.name
        for node in ast.parse(repair_runtime_source).body
        if isinstance(node, ast.FunctionDef)
    }

    moved_runtime_functions = {
        "_batch_question_figure_comparison_matrix",
        "_batch_question_figure_repair_queue",
        "_apply_question_figure_repair_queue_conflict_guard",
        "_question_figure_repair_batch_confirmation_plan",
        "_freeze_question_figure_repair_batch_confirmation_plan",
        "_dry_run_question_figure_repair_batch_apply_guard",
        "_plan_question_figure_repair_batch_apply_execution",
        "_apply_question_figure_repair_batch_execution_to_docx",
        "_question_figure_batch_apply_audit_record",
        "_append_question_figure_batch_apply_audit_record",
        "_read_question_figure_batch_apply_audit_payload",
        "_question_figure_batch_apply_transaction_manifest_from_audit",
        "_write_question_figure_batch_apply_transaction_manifest",
        "_rollback_question_figure_repair_batch_apply_from_audit",
        "_question_figure_batch_apply_rollback_audit_record",
        "_resolve_question_figure_repair_queue_conflict",
        "_refresh_question_figure_repair_queue_status",
        "_question_figure_repair_apply_plan",
    }
    expected_repair_runtime_functions = {
        "_batch_question_figure_comparison_matrix",
        "_batch_question_figure_repair_queue",
        "_freeze_question_figure_repair_batch_confirmation_plan",
        "_dry_run_question_figure_repair_batch_apply_guard",
        "_plan_question_figure_repair_batch_apply_execution",
        "_apply_question_figure_repair_batch_execution_to_docx",
        "_rollback_question_figure_repair_batch_apply_from_audit",
        "_resolve_question_figure_repair_queue_conflict",
    }

    assert moved_runtime_functions.isdisjoint(runtime_functions)
    assert expected_repair_runtime_functions <= repair_runtime_functions
    assert "from .question_figure_repair_runtime import" in runtime_source
    assert "PySide6" not in repair_runtime_source
    assert "WorkbenchProductionRunner" not in repair_runtime_source
