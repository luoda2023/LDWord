import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_terminal_release_exception_audit import (  # noqa: E402
    audit_scene_terminal_release_exception_report,
    build_scene_terminal_release_exception_audit_report,
)


def test_terminal_release_exception_ledger_governs_release_residual_states():
    report = build_scene_terminal_release_exception_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.exception_id: row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_terminal_release_exception_report(report) == ()
    assert payload["counts"]["exception_count"] == 5
    assert payload["counts"]["governed_exception_count"] == 5
    assert payload["counts"]["ungoverned_exception_count"] == 0
    assert payload["counts"]["managed_warning_count"] == 10
    assert payload["counts"]["warning_projection_count"] == 3
    assert payload["counts"]["readiness_reconciliation_count"] == 15
    assert payload["counts"]["boundary_guarded_maturity_count"] == 6
    assert payload["counts"]["static_closed_boundary_count"] == 2
    assert payload["counts"]["exception_trace_count"] == 36
    assert payload["counts"]["unique_source_trace_count"] == 31
    assert payload["counts"]["linked_boundary_subject_count"] == 6
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert source_status["export_script"] == "ready"
    assert source_status["n2_393c_plan"] == "ready"
    assert source_status["n2_393d_plan"] == "ready"

    assert rows["managed_residual_warnings"].observed_count == 10
    assert rows["managed_residual_warnings"].governed_count == 10
    assert rows["managed_residual_warnings"].trace_count == 10
    assert "family:ip_patent_documents" in (
        rows["managed_residual_warnings"].linked_boundary_subject_ids
    )
    assert rows["dashboard_warning_projection"].observed_count == 3
    assert rows["dashboard_warning_projection"].trace_count == 3
    assert all(
        trace.surface_source_id == "scene_matrix_dashboard"
        for trace in rows["dashboard_warning_projection"].trace_rows
    )
    assert rows["boundary_readiness_reconciliation"].governed_count == 15
    assert rows["boundary_readiness_reconciliation"].trace_count == 15
    assert rows["boundary_guarded_maturity"].governed_count == 6
    assert rows["boundary_guarded_maturity"].trace_count == 6
    assert "pack:import_ai_boundary" in (
        rows["boundary_guarded_maturity"].linked_boundary_subject_ids
    )
    assert rows["static_closed_boundary"].governed_count == 2
    assert rows["static_closed_boundary"].trace_count == 2
    assert {
        trace.source_row_id for trace in rows["static_closed_boundary"].trace_rows
    } == {
        "scene_product_readiness:static_closed_not_green:pack:professional_disclosure",
        "scene_product_readiness:static_closed_not_green:pack:import_ai_boundary",
    }


def test_terminal_release_exception_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_terminal_release_exception_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["exception_count"] == 5
    assert payload["counts"]["governed_exception_count"] == 5
    assert payload["counts"]["exception_trace_count"] == 36
    rows = {row["exception_id"]: row for row in payload["rows"]}
    maturity = rows["boundary_guarded_maturity"]
    assert maturity["status"] == "governed"
    assert maturity["trace_count"] == 6
    assert "family:regulated_disclosure_documents" in (
        maturity["linked_boundary_subject_ids"]
    )
    assert "boundary_guarded_completion" in maturity["evidence_ids"]
    static_closed = rows["static_closed_boundary"]
    assert static_closed["trace_count"] == 2
    assert (
        "static_closed_boundary:scene_product_readiness:static_closed_not_green:pack:import_ai_boundary"
        in static_closed["trace_ids"]
    )
    managed = rows["managed_residual_warnings"]
    assert managed["trace_count"] == 10
    assert "family:ip_patent_documents" in managed["linked_boundary_subject_ids"]

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_terminal_release_exception_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Terminal Release Exception Audit" in markdown_result.stdout
    assert "Governed exceptions: 5/5" in markdown_result.stdout
    assert "Exception traces: 36" in markdown_result.stdout
    assert "managed_residual_warnings" in markdown_result.stdout
    assert "scene_terminal_release_exception_audit" in markdown_result.stdout


def test_release_gate_includes_terminal_release_exception_ledger(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert (
        payload["checks"]["scene_terminal_release_exception_audit"]["status"]
        == "passed"
    )
    assert payload["counts"]["scene_terminal_release_exception_count"] == 5
    assert payload["counts"]["scene_terminal_release_exception_governed_count"] == 5
    assert payload["counts"]["scene_terminal_release_exception_ungoverned_count"] == 0
    assert (
        payload["counts"]["scene_terminal_release_exception_managed_warning_count"]
        == 10
    )
    assert (
        payload["counts"][
            "scene_terminal_release_exception_readiness_reconciliation_count"
        ]
        == 15
    )
    assert (
        payload["counts"][
            "scene_terminal_release_exception_boundary_guarded_maturity_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_terminal_release_exception_static_closed_boundary_count"
        ]
        == 2
    )
    assert payload["counts"]["static_closed_not_green_governed_count"] == 2
    assert (
        payload["counts"]["static_closed_not_green_governed_count"]
        == payload["counts"]["static_closed_but_not_green_count"]
    )
    assert payload["counts"]["dashboard_warning_projection_governed_count"] == 3
    assert (
        payload["counts"]["dashboard_warning_projection_governed_count"]
        == payload["counts"]["scene_matrix_dashboard_warning_count"]
    )
    assert payload["counts"]["scene_terminal_release_exception_trace_count"] == 36
    assert (
        payload["counts"][
            "scene_terminal_release_exception_unique_source_trace_count"
        ]
        == 31
    )
    assert (
        payload["counts"][
            "scene_terminal_release_exception_linked_boundary_subject_count"
        ]
        == 6
    )
