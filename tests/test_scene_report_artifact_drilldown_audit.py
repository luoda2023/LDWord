import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_report_artifact_drilldown_audit import (  # noqa: E402
    N2_180_REPORT_ARTIFACT_DRILLDOWN_SPECS,
    audit_scene_report_artifact_drilldown_report,
    build_scene_report_artifact_drilldown_audit_report,
)


def test_scene_report_artifact_drilldown_audit_locks_n2_180_channels():
    report = build_scene_report_artifact_drilldown_audit_report(project_root=ROOT)
    payload = report.to_payload()
    counts = payload["counts"]
    rows = {row.drilldown_channel_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.drilldown_channel_count == 10
    assert report.ready_drilldown_channel_count == 10
    assert report.artifact_kind_count == 13
    assert report.runtime_surface_count == 24
    assert report.ui_surface_count == 18
    assert report.report_surface_count == 21
    assert report.repair_target_type_count == 3
    assert report.test_evidence_count == 16
    assert report.covered_pack_count == 12
    assert report.covered_family_count == 15
    assert report.issue_count == 0
    assert report.source_evidence_count == 32
    assert report.missing_source_evidence_count == 0
    assert audit_scene_report_artifact_drilldown_report(report) == ()
    assert tuple(row.drilldown_channel_id for row in report.rows) == tuple(
        spec.drilldown_channel_id for spec in N2_180_REPORT_ARTIFACT_DRILLDOWN_SPECS
    )
    assert all(item["status"] == "ready" for item in payload["source_evidence"])

    state_model = rows["artifact_state_model"]
    assert "output" in state_model.artifact_kind_ids
    assert "scene_sample_manifest" in state_model.artifact_kind_ids
    assert "ArtifactItemState" in state_model.runtime_surface_ids
    assert "RecentRunPanel.artifact_items" in state_model.ui_surface_ids

    runtime_maps = rows["runtime_delivery_artifact_maps"]
    assert "material_package" in runtime_maps.artifact_kind_ids
    assert "_write_material_package_artifacts" in runtime_maps.runtime_surface_ids
    assert "material_package_paths" in runtime_maps.report_surface_ids

    grouping = rows["artifact_grouping_and_report_inference"]
    assert "_infer_report_group" in grouping.runtime_surface_ids
    assert "group_id" in grouping.report_surface_ids

    recent_run = rows["recent_run_artifact_browser"]
    assert "material_package_report" in recent_run.artifact_kind_ids
    assert "QDesktopServices.openUrl" in recent_run.ui_surface_ids
    assert "test_recent_run_panel_labels_material_package_report_anchor" in (
        recent_run.test_ids
    )
    assert "test_recent_run_panel_renders_delivery_artifact_labels" in (
        recent_run.test_ids
    )

    transaction_task = rows["question_figure_transaction_task_report_drilldown"]
    assert "question_figure_batch_apply_transaction_report" in (
        transaction_task.artifact_kind_ids
    )
    assert "question_figure_batch_apply_transaction_task_summary" in (
        transaction_task.artifact_kind_ids
    )
    assert "question_figure_transaction_task_issue_items" in (
        transaction_task.runtime_surface_ids
    )
    assert "WorkbenchPanel._open_issue_repair_target" in (
        transaction_task.ui_surface_ids
    )
    assert "RecentRunPanel._open_artifact_file" in transaction_task.ui_surface_ids
    assert "question_figure_batch_apply_transaction_task_summary" in (
        transaction_task.repair_target_types
    )
    assert "test_recent_run_panel_labels_question_figure_transaction_task_anchors" in (
        transaction_task.test_ids
    )

    quick_log = rows["quick_execution_artifact_log"]
    assert "QuickExecutionDetail execution log" in quick_log.ui_surface_ids
    assert "artifact_items" in quick_log.report_surface_ids

    report_writer = rows["report_writer_artifact_evidence"]
    assert "journal_submission_package" in report_writer.report_surface_ids
    assert "_extract_scene_sample_fixture_manifest" in report_writer.runtime_surface_ids

    sample_manifest = rows["sample_manifest_child_drilldown"]
    assert sample_manifest.coverage_selector == "sample_fixture_artifact"
    assert "sample_fixture" in sample_manifest.repair_target_types
    assert "request_cell_report" in sample_manifest.artifact_kind_ids

    output_repair = rows["output_target_warning_repair"]
    assert "planned_output" in output_repair.artifact_kind_ids
    assert "output_target" in output_repair.repair_target_types
    assert "output_target_preflight" in output_repair.report_surface_ids

    matrix_browse = rows["matrix_browse_report_artifact_drilldown"]
    assert "SceneMatrixDashboard.report_artifact_drilldown" in (
        matrix_browse.runtime_surface_ids
    )
    assert "Dashboard card" in matrix_browse.ui_surface_ids
    assert "release_gate.counts" in matrix_browse.report_surface_ids

    assert counts["drilldown_channel_count"] == report.drilldown_channel_count
    assert counts["missing_source_evidence_count"] == 0


def test_scene_report_artifact_drilldown_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_report_artifact_drilldown.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_report_artifact_drilldown_audit.py",
            "--format",
            "json",
            "--channel",
            "recent_run_artifact_browser",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.stdout == ""
    assert payload["status"] == "passed"
    assert payload["counts"]["drilldown_channel_count"] == 1
    assert payload["rows"][0]["drilldown_channel_id"] == (
        "recent_run_artifact_browser"
    )
    assert "RecentRunPanel._build_artifact_row" in payload["rows"][0]["ui_surface_ids"]


def test_scene_report_artifact_drilldown_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_report_artifact_drilldown_audit.py",
            "--format",
            "markdown",
            "--channel",
            "output_target_warning_repair",
        ],
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
    )

    assert "# Report/Artifact Drilldown Productization Audit" in result.stdout
    assert "| Channel | Status | Coverage | Packs | Families | Artifacts |" in (
        result.stdout
    )
    assert "output_target_warning_repair" in result.stdout
    assert "output_target_preflight" in result.stdout
    assert "## Source Evidence" in result.stdout


def test_release_gate_includes_scene_report_artifact_drilldown_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_report_artifact_drilldown_audit"]["status"] == (
        "passed"
    )
    assert payload["counts"]["scene_report_artifact_drilldown_channel_count"] == 10
    assert payload["counts"]["scene_report_artifact_drilldown_ready_channel_count"] == 10
    assert payload["counts"]["scene_report_artifact_drilldown_artifact_kind_count"] == 13
    assert payload["counts"]["scene_report_artifact_drilldown_runtime_surface_count"] == 24
    assert payload["counts"]["scene_report_artifact_drilldown_ui_surface_count"] == 18
    assert payload["counts"]["scene_report_artifact_drilldown_report_surface_count"] == 21
    assert (
        payload["counts"][
            "scene_report_artifact_drilldown_repair_target_type_count"
        ]
        == 3
    )
    assert payload["counts"]["scene_report_artifact_drilldown_test_evidence_count"] == 16
    assert payload["counts"]["scene_report_artifact_drilldown_covered_pack_count"] == 12
    assert (
        payload["counts"]["scene_report_artifact_drilldown_covered_family_count"]
        == 15
    )
    assert payload["counts"]["scene_report_artifact_drilldown_issue_count"] == 0
    assert (
        payload["counts"][
            "scene_report_artifact_drilldown_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_report_artifact_drilldown_audit"]["status"] == "passed"
