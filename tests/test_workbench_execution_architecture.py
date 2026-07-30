import ast
import inspect
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.workbench.execution_controller import WorkbenchExecutionController
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter


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


def test_workbench_material_preflight_logic_lives_in_dedicated_module():
    runtime_path = ROOT / "src/services/production_runtime/execution_runtime.py"
    preflight_path = ROOT / "src/services/production_runtime/material_preflight.py"
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
    runtime_path = ROOT / "src/services/production_runtime/execution_runtime.py"
    exam_assets_path = ROOT / "src/services/production_runtime/exam_question_assets.py"
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
    runtime_path = ROOT / "src/services/production_runtime/execution_runtime.py"
    artifacts_path = ROOT / "src/services/production_runtime/material_artifacts.py"
    delivery_path = ROOT / "src/services/material_delivery/package_builder.py"
    runtime_source = runtime_path.read_text(encoding="utf-8")
    artifacts_source = artifacts_path.read_text(encoding="utf-8")
    delivery_source = delivery_path.read_text(encoding="utf-8")
    delivery_runtime_source = (
        ROOT / "src/services/production_runtime/delivery_runtime.py"
    ).read_text(encoding="utf-8")
    delivery_reporting_source = (
        ROOT / "src/services/production_runtime/delivery_reporting.py"
    ).read_text(encoding="utf-8")

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
    delivery_tree = ast.parse(delivery_source)
    delivery_functions = {
        node.name for node in delivery_tree.body if isinstance(node, ast.FunctionDef)
    }
    delivery_classes = {
        node.name for node in delivery_tree.body if isinstance(node, ast.ClassDef)
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
        "write_material_manifest",
        "write_material_package_artifacts",
        "_material_manifest_payload",
    }

    assert moved_runtime_functions.isdisjoint(runtime_functions)
    assert expected_artifact_functions <= artifact_functions
    assert "_render_material_archive_report" not in artifact_functions
    assert "_write_package_zip" not in artifact_functions
    assert {"_render_archive_report", "_write_zip", "_publish_pair"} <= (
        delivery_functions
    )
    assert "MaterialDeliveryPackageBuilder" in delivery_classes
    assert "from .material_artifacts import" in delivery_runtime_source
    assert "from .material_artifacts import" in delivery_reporting_source
    assert "from src.services.material_delivery import" in artifacts_source
    assert "PySide6" not in artifacts_source
    assert "shutil" not in artifacts_source
    assert "zipfile" not in artifacts_source


def test_delivery_execution_and_reporting_have_real_non_runtime_owners():
    runtime_source = (
        ROOT / "src/services/production_runtime/execution_runtime.py"
    ).read_text(encoding="utf-8")
    delivery_runtime_source = (
        ROOT / "src/services/production_runtime/delivery_runtime.py"
    ).read_text(encoding="utf-8")
    delivery_reporting_source = (
        ROOT / "src/services/production_runtime/delivery_reporting.py"
    ).read_text(encoding="utf-8")

    runtime_tree = ast.parse(runtime_source)
    delivery_runtime_tree = ast.parse(delivery_runtime_source)
    delivery_reporting_tree = ast.parse(delivery_reporting_source)
    runtime_functions = {
        node.name for node in runtime_tree.body if isinstance(node, ast.FunctionDef)
    }
    runtime_methods = {
        method.name
        for node in runtime_tree.body
        if isinstance(node, ast.ClassDef)
        for method in node.body
        if isinstance(method, ast.FunctionDef)
    }
    delivery_runtime_functions = {
        node.name
        for node in delivery_runtime_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    delivery_reporting_functions = {
        node.name
        for node in delivery_reporting_tree.body
        if isinstance(node, ast.FunctionDef)
    }

    removed_runtime_functions = {
        "_delivery_target_groups",
        "_load_delivery_template",
        "_prepare_delivery_target_groups",
        "_aggregate_delivery_status",
        "_finalize_result_artifacts",
        "_write_enabled_result_reports",
        "_write_delivery_reports",
        "_write_structured_intermediates",
        "_delivery_preset_payload",
        "_pipeline_context_payload",
    }
    assert removed_runtime_functions.isdisjoint(runtime_functions)
    assert "_run_delivery_target_groups" not in runtime_methods
    assert {
        "delivery_target_groups",
        "load_delivery_template",
        "mode_id_for_scene",
        "run_delivery_target_groups",
        "aggregate_delivery_status",
    } <= delivery_runtime_functions
    assert {
        "finalize_result_artifacts",
        "write_enabled_result_reports",
        "write_delivery_reports",
        "write_structured_intermediates",
        "delivery_preset_payload",
        "pipeline_context_payload",
    } <= delivery_reporting_functions
    assert "from .delivery_runtime import" in runtime_source
    assert "from .delivery_reporting import" in runtime_source
    assert "execution_runtime" not in delivery_runtime_source
    assert "execution_runtime" not in delivery_reporting_source
    assert "WorkbenchProductionRunner" not in delivery_runtime_source
    assert "WorkbenchProductionRunner" not in delivery_reporting_source
    assert "PySide6" not in delivery_runtime_source
    assert "PySide6" not in delivery_reporting_source


def test_workbench_question_figure_repair_runtime_lives_in_dedicated_module():
    runtime_path = ROOT / "src/services/production_runtime/execution_runtime.py"
    batch_reporting_path = (
        ROOT / "src/services/production_runtime/batch_reporting.py"
    )
    repair_runtime_path = (
        ROOT / "src/services/production_runtime/question_figure_repair_runtime.py"
    )
    runtime_source = runtime_path.read_text(encoding="utf-8")
    batch_reporting_source = batch_reporting_path.read_text(encoding="utf-8")
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

    production_projection_roots = {
        "build_batch_question_figure_comparison_matrix",
        "build_batch_question_figure_repair_queue",
    }
    speculative_execution_functions = {
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
    }

    assert production_projection_roots.isdisjoint(runtime_functions)
    assert production_projection_roots <= repair_runtime_functions
    assert speculative_execution_functions.isdisjoint(repair_runtime_functions)
    assert "from .question_figure_repair_runtime import" in batch_reporting_source
    assert "from .question_figure_repair_runtime import" not in runtime_source
    assert "PySide6" not in repair_runtime_source
    assert "WorkbenchProductionRunner" not in repair_runtime_source


def test_execution_runtime_leaf_contracts_have_real_non_runtime_owners():
    runtime_source = (
        ROOT / "src/services/production_runtime/execution_runtime.py"
    ).read_text(encoding="utf-8")
    thread_source = (
        ROOT / "src/ui/panels/workbench/execution_thread_handle.py"
    ).read_text(encoding="utf-8")
    official_payload_source = (
        ROOT / "src/reporting/official_batch_payload.py"
    ).read_text(encoding="utf-8")
    execution_payload_source = (
        ROOT / "src/reporting/execution_payload.py"
    ).read_text(encoding="utf-8")
    batch_reporting_source = (
        ROOT / "src/services/production_runtime/batch_reporting.py"
    ).read_text(encoding="utf-8")

    runtime_tree = ast.parse(runtime_source)
    runtime_functions = {
        node.name for node in runtime_tree.body if isinstance(node, ast.FunctionDef)
    }
    runtime_classes = {
        node.name for node in runtime_tree.body if isinstance(node, ast.ClassDef)
    }
    thread_classes = {
        node.name
        for node in ast.parse(thread_source).body
        if isinstance(node, ast.ClassDef)
    }
    official_payload_functions = {
        node.name
        for node in ast.parse(official_payload_source).body
        if isinstance(node, ast.FunctionDef)
    }
    execution_payload_functions = {
        node.name
        for node in ast.parse(execution_payload_source).body
        if isinstance(node, ast.FunctionDef)
    }
    batch_reporting_functions = {
        node.name
        for node in ast.parse(batch_reporting_source).body
        if isinstance(node, ast.FunctionDef)
    }

    moved_official_payload_functions = {
        "_official_document_batch_item_payload",
        "_official_document_batch_preflight_failure_payload",
        "_official_document_batch_exception_payload",
        "_official_document_batch_diagnostics",
        "_official_document_batch_error_text",
    }
    expected_official_payload_functions = {
        "official_document_batch_item_payload",
        "official_document_batch_preflight_failure_payload",
        "official_document_batch_exception_payload",
        "official_document_batch_diagnostics",
        "official_document_batch_error_text",
    }
    moved_execution_payload_functions = {
        "_diagnostics_payload",
        "_content_visibility_scan_payload",
        "_content_visibility_preview_payload",
        "_content_visibility_receipts_payload",
        "_output_target_preflight_payload",
        "_object_preflight_payload",
        "_material_field_consistency_payload",
        "_journal_submission_package_payload",
        "_official_document_assembly_payload",
        "_official_numbering_preservation_payload",
        "_technical_chapter_inventory_payload",
        "_application_section_word_limits_payload",
        "_material_field_issue_payload",
        "_plain_data",
    }
    expected_execution_payload_functions = {
        name.removeprefix("_") for name in moved_execution_payload_functions
    }
    moved_batch_reporting_functions = {
        "_attach_batch_reports",
        "_write_batch_reports",
        "_publish_batch_report_files",
        "_render_batch_markdown_report",
        "_batch_payload",
        "_batch_profile_ids",
        "_batch_profile_ids_from_payload",
        "_batch_isolation_payload",
        "_batch_profile_key",
        "_batch_profile_summary",
        "_batch_issue_items_for_result",
        "_batch_issue_id",
    }
    expected_batch_reporting_functions = {
        "attach_batch_reports",
        "_write_batch_reports",
        "_publish_batch_report_files",
        "_render_batch_markdown_report",
        "build_batch_payload",
        "batch_profile_ids",
        "_batch_profile_ids_from_payload",
        "_batch_isolation_payload",
        "_batch_profile_key",
        "_batch_profile_summary",
        "build_batch_issue_items_for_result",
        "_batch_issue_id",
    }

    assert "ThreadedExecutionHandle" not in runtime_classes
    assert "ThreadedExecutionHandle" in thread_classes
    assert "PySide6" not in runtime_source
    assert moved_official_payload_functions.isdisjoint(runtime_functions)
    assert expected_official_payload_functions <= official_payload_functions
    assert moved_execution_payload_functions.isdisjoint(runtime_functions)
    assert expected_execution_payload_functions <= execution_payload_functions
    assert moved_batch_reporting_functions.isdisjoint(runtime_functions)
    assert expected_batch_reporting_functions <= batch_reporting_functions
    assert "_lazy_optional_function" in runtime_functions
    assert '"src.reporting.official_batch_payload"' in runtime_source
    assert (
        '"src.services.production_runtime.batch_reporting"'
        in runtime_source
    )
    assert "from src.reporting.official_batch_payload import" not in runtime_source
    assert "from src.reporting.execution_payload import" in runtime_source
    assert "from .batch_reporting import" not in runtime_source
    assert "src.ui" not in official_payload_source
    assert "src.ui" not in execution_payload_source
    assert "src.ui" not in batch_reporting_source
    assert "PySide6" not in batch_reporting_source
    assert "execution_runtime" not in batch_reporting_source
