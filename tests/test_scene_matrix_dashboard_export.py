import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_matrix_dashboard import build_scene_matrix_dashboard  # noqa: E402


def test_scene_matrix_dashboard_filters_for_drilldown():
    family_report = build_scene_matrix_dashboard(family_id="hr_batch_documents")
    manual_report = build_scene_matrix_dashboard(
        boundary_signal="manual_boundary_request_cell"
    )
    boundary_report = build_scene_matrix_dashboard(readiness_level="blue_boundary")

    assert [row.pack_id for row in family_report.rows] == ["batch_forms"]
    assert [row.pack_id for row in manual_report.rows] == [
        "english_journal",
        "exam_education",
        "professional_disclosure",
        "import_ai_boundary",
    ]
    assert [row.pack_id for row in boundary_report.rows] == [
        "professional_disclosure",
        "import_ai_boundary",
    ]
    assert family_report.to_payload()["family_filter"] == "hr_batch_documents"
    assert manual_report.to_payload()["boundary_filter"] == (
        "manual_boundary_request_cell"
    )


def test_scene_matrix_dashboard_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_matrix_dashboard.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_dashboard.py",
            "--format",
            "json",
            "--family",
            "hr_batch_documents",
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
    assert payload["visible_count"] == 1
    assert payload["rows"][0]["pack_id"] == "batch_forms"
    assert payload["rows"][0]["family_ids"] == [
        "hr_batch_documents",
        "form_batch_documents",
    ]


def test_scene_matrix_dashboard_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_dashboard.py",
            "--format",
            "markdown",
            "--pack",
            "professional_disclosure",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Matrix Dashboard" in result.stdout
    assert "| Pack | Status | Readiness | Cells | Families | Boundaries |" in (
        result.stdout
    )
    assert "professional_disclosure" in result.stdout
    assert "manual_boundary_request_cell" in result.stdout
    assert "high_frequency_task_lexicon_audit" in result.stdout
    assert "scene_ambiguous_boundary_audit" in result.stdout
    assert "scene_ambiguity_clarification_ui_audit" in result.stdout
    assert "scene_import_handoff_audit" in result.stdout
    assert "scene_object_preflight_action_audit" in result.stdout
    assert "scene_user_journey_fixture_audit" in result.stdout
    assert "scene_business_capability_matrix_audit" in result.stdout
    assert "scene_control_runtime_consistency_audit" in result.stdout
    assert "scene_family_fixture_depth_audit" in result.stdout
    assert "scene_material_schema_audit" in result.stdout
    assert "scene_material_repair_flow_audit" in result.stdout
    assert "scene_fixed_layout_profile_audit" in result.stdout
    assert "scene_report_artifact_drilldown_audit" in result.stdout
    assert "scene_delivery_preset_audit" in result.stdout
    assert "scene_delivery_preset_execution_audit" in result.stdout
    assert "scene_formula_output_watermark_audit" in result.stdout
    assert "scene_input_source_audit" in result.stdout
    assert "scene_count_profile_audit" in result.stdout
    assert "scene_product_maturity_upgrade_audit" in result.stdout
    assert "scene_word_risk_closure_audit" in result.stdout
    assert "scene_plugin_boundary_confirmation_audit" in result.stdout
    assert "scene_residual_warning_governance_audit" in result.stdout
    assert "scene_boundary_readiness_reconciliation_audit" in result.stdout
    assert "scene_terminal_release_exception_audit" in result.stdout
    assert "scene_boundary_subject_release_dossier_audit" in result.stdout
    assert "scene_non_subject_release_trace_attribution_audit" in result.stdout
    assert "scene_release_trace_partition_guard_audit" in result.stdout
    assert "scene_release_projection_surface_parity_audit" in result.stdout
    assert "scene_boundary_subject_release_continuity_audit" in result.stdout
    assert "scene_release_closure_ledger_audit" in result.stdout
    assert "scene_boundary_maturity_release_envelope_audit" in result.stdout
    assert "scene_retained_gap_exit_criteria_audit" in result.stdout
    assert "scene_release_residual_ratio_ledger_audit" in result.stdout
    assert "scene_release_residual_explanation_audit" in result.stdout
