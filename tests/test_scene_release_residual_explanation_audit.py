import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    _print_human,
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_release_residual_explanation_audit import (  # noqa: E402
    SCENE_RELEASE_RESIDUAL_EXPLANATION_SPECS,
    audit_scene_release_residual_explanation_report,
    build_scene_release_residual_explanation_audit_report,
)


def test_release_residual_explanation_covers_all_visible_residuals():
    report = build_scene_release_residual_explanation_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.residual_id: row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_release_residual_explanation_report(report) == ()
    assert payload["counts"]["row_count"] == len(
        SCENE_RELEASE_RESIDUAL_EXPLANATION_SPECS
    )
    assert payload["counts"]["row_count"] == 14
    assert payload["counts"]["covered_count"] == 14
    assert payload["counts"]["mismatch_count"] == 0
    assert payload["counts"]["missing_summary_marker_count"] == 0
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert source_status["scene_matrix_dashboard"] == "ready"
    assert source_status["summary_projection"] == "ready"
    assert source_status["n2_393i_plan"] == "ready"

    assert rows["managed_warnings"].residual_count == 10
    assert rows["managed_warnings"].governed_count == 10
    assert rows["input_warnings"].residual_count == 5
    assert rows["input_warnings"].governed_count == 5
    assert rows["count_profile_warnings"].residual_count == 2
    assert rows["count_profile_warnings"].governed_count == 2
    assert rows["plugin_manual_warnings"].residual_count == 5
    assert rows["plugin_manual_warnings"].governed_count == 5
    assert rows["reference_profile_warnings"].residual_count == 2
    assert rows["reference_profile_warnings"].governed_count == 2
    assert rows["visio_fixture"].residual_count == 1
    assert rows["visio_fixture"].governed_count == 1
    assert rows["dashboard_warning_projection"].residual_count == 3
    assert rows["dashboard_warning_projection"].governed_count == 3
    assert rows["static_closed_not_green"].residual_count == 2
    assert rows["static_closed_not_green"].governed_count == 2
    assert rows["maturity_l5_enveloped"].residual_count == 6
    assert rows["maturity_l5_enveloped"].governed_count == 6
    assert rows["maturity_l5_alignment"].residual_count == 6
    assert rows["maturity_l5_alignment"].governed_count == 6
    assert rows["retained_gaps"].residual_count == 6
    assert rows["retained_gaps"].governed_count == 6
    assert rows["gap_domains"].residual_count == 3
    assert rows["gap_domains"].governed_count == 3
    assert rows["count_delivery_alignment"].residual_count == 4
    assert rows["count_delivery_alignment"].governed_count == 4
    assert rows["boundary_scope_alignment"].residual_count == 6
    assert rows["boundary_scope_alignment"].governed_count == 6
    assert all(row.summary_marker_present for row in rows.values())


def test_release_residual_explanation_has_no_dashboard_builder_back_edge():
    source = (
        ROOT / "src/config/scene_release_residual_explanation_audit.py"
    ).read_text(encoding="utf-8")

    assert "from src.config.scene_matrix_dashboard import" not in source
    assert "build_scene_matrix_dashboard()" not in source

    mismatched = build_scene_release_residual_explanation_audit_report(
        project_root=ROOT,
        dashboard_warning_count=2,
    )
    warning_projection = next(
        row
        for row in mismatched.rows
        if row.residual_id == "dashboard_warning_projection"
    )
    assert mismatched.status == "failed"
    assert warning_projection.status == "uncovered"
    assert "count_mismatch" in warning_projection.issue_ids


def test_release_gate_includes_release_residual_explanations(tmp_path, capsys):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_release_residual_explanation_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_release_residual_explanation_count"] == 14
    assert (
        payload["counts"]["scene_release_residual_explanation_covered_count"]
        == 14
    )
    assert payload["counts"]["scene_release_residual_explanation_mismatch_count"] == 0
    assert (
        payload["counts"][
            "scene_release_residual_explanation_missing_summary_marker_count"
        ]
        == 0
    )
    assert payload["counts"]["scene_release_residual_explanation_issue_count"] == 0
    assert (
        payload["scene_release_residual_explanation_audit"]["counts"][
            "covered_count"
        ]
        == 14
    )

    _print_human(payload)
    output = capsys.readouterr().out
    assert "boundary_scope_alignment=6/6" in output
    assert "residual_explanations=14/14 covered" in output


def test_release_residual_explanation_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_residual_explanation_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["row_count"] == 14
    assert payload["counts"]["covered_count"] == 14

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_residual_explanation_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Release Residual Explanation Audit" in markdown_result.stdout
    assert "Residual explanations covered: 14/14" in markdown_result.stdout
    assert "managed_warnings" in markdown_result.stdout
    assert "retained_gaps" in markdown_result.stdout
    assert "boundary_scope_alignment" in markdown_result.stdout
