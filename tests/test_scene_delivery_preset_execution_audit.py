import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_delivery_preset_execution_audit import (  # noqa: E402
    N2_176_DELIVERY_PRESET_EXECUTION_SPECS,
    audit_scene_delivery_preset_execution_report,
    build_scene_delivery_preset_execution_audit_report,
)


def test_scene_delivery_preset_execution_audit_locks_n2_176_channels():
    report = build_scene_delivery_preset_execution_audit_report(project_root=ROOT)
    payload = report.to_payload()
    counts = payload["counts"]
    rows = {row.execution_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.execution_channel_count == 10
    assert report.ready_execution_channel_count == 10
    assert report.required_output_signal_count == 27
    assert report.payload_key_count == 16
    assert report.runtime_surface_count == 19
    assert report.report_surface_count == 12
    assert report.ui_surface_count == 10
    assert report.test_evidence_count == 14
    assert report.covered_pack_count == 10
    assert report.covered_family_count == 14
    assert report.issue_count == 0
    assert report.source_evidence_count == 23
    assert report.missing_source_evidence_count == 0
    assert audit_scene_delivery_preset_execution_report(report) == ()
    assert tuple(row.execution_id for row in report.rows) == tuple(
        spec.execution_id for spec in N2_176_DELIVERY_PRESET_EXECUTION_SPECS
    )
    assert all(item["status"] == "ready" for item in payload["source_evidence"])

    final_docx = rows["final_docx_delivery_outputs"]
    assert final_docx.pack_ids
    assert "final_docx" in final_docx.required_output_signal_ids
    assert "output_paths" in final_docx.payload_keys
    assert "Pipeline._save_delivery_outputs" in final_docx.runtime_surface_ids

    visibility = rows["content_visibility_variant_outputs"]
    assert visibility.pack_ids == ("exam_education",)
    assert visibility.family_ids == ("exam_teaching",)
    assert "content_visibility_preview" in visibility.payload_keys

    compare = rows["compare_docx_artifacts"]
    assert "compare_docx" in compare.required_output_signal_ids
    assert "compare_paths" in compare.payload_keys

    reports = rows["delivery_reports"]
    assert {"report_json", "report_markdown", "report_paths"}.issubset(
        reports.required_output_signal_ids
    )
    assert "delivery_changes_markdown" in reports.report_surface_ids

    intermediate = rows["structured_intermediate_outputs"]
    assert "structured_intermediate_json" in intermediate.required_output_signal_ids
    assert "intermediate_paths" in intermediate.payload_keys

    material_package = rows["material_manifest_package_outputs"]
    assert "material_package_zip" in material_package.required_output_signal_ids
    assert "material_package_paths" in material_package.payload_keys

    failed_package = rows["failed_run_material_package_outputs"]
    assert "failed_run_material_package" in failed_package.required_output_signal_ids
    assert "failed_count" in failed_package.payload_keys
    assert (
        "test_workbench_runner_writes_material_package_for_failed_delivery_run"
        in failed_package.test_ids
    )

    batch = rows["batch_failure_isolation_artifacts"]
    assert batch.pack_ids == ("batch_forms",)
    assert batch.family_ids == ("hr_batch_documents", "form_batch_documents")
    assert "batch_failure_isolation" in batch.required_output_signal_ids
    assert "batch_issue_items" in batch.payload_keys

    ui_surface = rows["artifact_surface_state_and_logs"]
    assert "quick_execution_log" in ui_surface.required_output_signal_ids
    assert "QuickExecutionDetail.set_execution_result" in ui_surface.ui_surface_ids

    assert counts["execution_channel_count"] == report.execution_channel_count
    assert counts["missing_source_evidence_count"] == 0


def test_scene_delivery_preset_execution_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_delivery_preset_execution.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_delivery_preset_execution_audit.py",
            "--format",
            "json",
            "--execution",
            "failed_run_material_package_outputs",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.stdout == ""
    assert payload["status"] == "passed"
    assert payload["counts"]["execution_channel_count"] == 1
    assert payload["rows"][0]["execution_id"] == (
        "failed_run_material_package_outputs"
    )
    assert "failed_run_material_package" in (
        payload["rows"][0]["required_output_signal_ids"]
    )


def test_scene_delivery_preset_execution_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_delivery_preset_execution_audit.py",
            "--format",
            "markdown",
            "--execution",
            "artifact_surface_state_and_logs",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# DeliveryPreset Execution Completeness Audit" in result.stdout
    assert "| Execution | Status | Coverage | Packs | Families | Signals |" in (
        result.stdout
    )
    assert "artifact_surface_state_and_logs" in result.stdout
    assert "quick_execution_log" in result.stdout
    assert "## Source Evidence" in result.stdout


def test_release_gate_includes_scene_delivery_preset_execution_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert (
        payload["checks"]["scene_delivery_preset_execution_audit"]["status"]
        == "passed"
    )
    assert payload["counts"]["scene_delivery_execution_channel_count"] == 10
    assert payload["counts"]["scene_delivery_execution_ready_channel_count"] == 10
    assert payload["counts"]["scene_delivery_execution_required_output_signal_count"] == 27
    assert payload["counts"]["scene_delivery_execution_payload_key_count"] == 16
    assert payload["counts"]["scene_delivery_execution_runtime_surface_count"] == 19
    assert payload["counts"]["scene_delivery_execution_report_surface_count"] == 12
    assert payload["counts"]["scene_delivery_execution_ui_surface_count"] == 10
    assert payload["counts"]["scene_delivery_execution_test_evidence_count"] == 14
    assert payload["counts"]["scene_delivery_execution_issue_count"] == 0
    assert (
        payload["counts"]["scene_delivery_execution_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_delivery_preset_execution_audit"]["status"] == "passed"
