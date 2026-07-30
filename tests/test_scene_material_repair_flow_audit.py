import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_material_repair_flow_audit import (  # noqa: E402
    N2_177_MATERIAL_REPAIR_FLOW_SPECS,
    audit_scene_material_repair_flow_report,
    build_scene_material_repair_flow_audit_report,
)


def test_scene_material_repair_flow_audit_locks_n2_177_channels():
    report = build_scene_material_repair_flow_audit_report(project_root=ROOT)
    payload = report.to_payload()
    counts = payload["counts"]
    rows = {row.flow_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.flow_count == 11
    assert report.ready_flow_count == 11
    assert report.capability_count == 33
    assert report.material_signal_count == 36
    assert report.repair_target_type_count == 8
    assert report.runtime_surface_count == 21
    assert report.ui_surface_count == 16
    assert report.test_evidence_count == 25
    assert report.covered_pack_count == 10
    assert report.covered_family_count == 15
    assert report.issue_count == 0
    assert report.source_evidence_count == 33
    assert report.missing_source_evidence_count == 0
    assert audit_scene_material_repair_flow_report(report) == ()
    assert tuple(row.flow_id for row in report.rows) == tuple(
        spec.flow_id for spec in N2_177_MATERIAL_REPAIR_FLOW_SPECS
    )
    assert all(item["status"] == "ready" for item in payload["source_evidence"])

    schema_projection = rows["schema_requirements_to_assets_panel"]
    assert schema_projection.pack_ids
    assert "material_schema_projection" in schema_projection.capability_ids
    assert "required_material_fields" in schema_projection.material_signal_ids
    assert "SceneSpecPresenterMixin._attachment_roles_from_scene" in (
        schema_projection.runtime_surface_ids
    )

    preview = rows["assets_panel_preview_missing_detection"]
    assert "package_field_inventory" in preview.material_signal_ids
    assert "preview" in preview.repair_target_types

    workbench_groups = rows["workbench_material_readiness_groups"]
    assert "schema" in workbench_groups.repair_target_types
    assert "recommend_material_schema_replacement" in (
        workbench_groups.runtime_surface_ids
    )

    gate = rows["execution_gate_policy_semantics"]
    assert "can_run" in gate.material_signal_ids
    assert "blocking_reasons" in gate.material_signal_ids
    assert "material_readiness_gate_decision" in gate.runtime_surface_ids
    assert {"field", "asset", "schema"}.issubset(gate.repair_target_types)

    result_detail = rows["execution_result_detail_access"]
    assert "profile_schema" in result_detail.repair_target_types
    assert "execution_log" in result_detail.material_signal_ids

    bridge = rows["panel_bridge_material_routing"]
    assert "schema_scene_content_route" in bridge.capability_ids
    assert "Scene content detail" in bridge.ui_surface_ids

    focus = rows["assets_panel_target_focus"]
    assert "profile_field" in focus.repair_target_types
    assert "AssetsPanel.focus_material_profile_repair_target" in (
        focus.runtime_surface_ids
    )

    schema_replacement = rows["schema_replacement_recommendation_flow"]
    assert "schema_alias_recommendation" in schema_replacement.capability_ids
    assert "content_fill" in schema_replacement.repair_target_types

    batch = rows["batch_profile_material_repair_targets"]
    assert batch.coverage_selector == "batch_material"
    assert "hr_batch_documents" in batch.family_ids
    assert "profile_field" in batch.repair_target_types
    assert "QuickExecutionDetail.set_execution_result" in (
        batch.runtime_surface_ids
    )

    manifest = rows["material_manifest_feedback"]
    assert "material_manifest_paths" in manifest.material_signal_ids
    assert "_material_manifest_payload" in manifest.runtime_surface_ids

    assert counts["flow_count"] == report.flow_count
    assert counts["missing_source_evidence_count"] == 0


def test_scene_material_repair_flow_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_material_repair_flow.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_material_repair_flow_audit.py",
            "--format",
            "json",
            "--flow",
            "schema_replacement_recommendation_flow",
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
    assert payload["counts"]["flow_count"] == 1
    assert payload["rows"][0]["flow_id"] == "schema_replacement_recommendation_flow"
    assert "recommendation_schema_id" in (
        payload["rows"][0]["material_signal_ids"]
    )


def test_scene_material_repair_flow_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_material_repair_flow_audit.py",
            "--format",
            "markdown",
            "--flow",
            "execution_result_detail_access",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# MaterialSchema Input and Repair Flow Audit" in result.stdout
    assert "| Flow | Status | Coverage | Packs | Families | Signals |" in result.stdout
    assert "execution_result_detail_access" in result.stdout
    assert "execution_log" in result.stdout
    assert "## Source Evidence" in result.stdout


def test_release_gate_includes_scene_material_repair_flow_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["checks"]["scene_material_repair_flow_audit"]["status"] == "passed"
    assert payload["counts"]["scene_material_repair_flow_count"] == 11
    assert payload["counts"]["scene_material_repair_flow_ready_count"] == 11
    assert payload["counts"]["scene_material_repair_flow_capability_count"] == 33
    assert payload["counts"]["scene_material_repair_flow_signal_count"] == 36
    assert payload["counts"]["scene_material_repair_flow_target_type_count"] == 8
    assert payload["counts"]["scene_material_repair_flow_runtime_surface_count"] == 21
    assert payload["counts"]["scene_material_repair_flow_ui_surface_count"] == 16
    assert payload["counts"]["scene_material_repair_flow_test_evidence_count"] == 25
    assert payload["counts"]["scene_material_repair_flow_issue_count"] == 0
    assert (
        payload["counts"]["scene_material_repair_flow_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_material_repair_flow_audit"]["status"] == "passed"
