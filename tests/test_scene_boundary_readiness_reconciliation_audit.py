import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_boundary_readiness_reconciliation_audit import (  # noqa: E402
    audit_scene_boundary_readiness_reconciliation_report,
    build_scene_boundary_readiness_reconciliation_audit_report,
)


def test_boundary_readiness_reconciliation_explains_non_full_counters():
    report = build_scene_boundary_readiness_reconciliation_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.row_id: row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_boundary_readiness_reconciliation_report(report) == ()
    assert payload["counts"]["row_count"] == 15
    assert payload["counts"]["reconciled_count"] == 15
    assert payload["counts"]["unreconciled_count"] == 0
    assert payload["counts"]["readiness_delta_count"] == 5
    assert payload["counts"]["not_applicable_count"] == 2
    assert payload["counts"]["static_closed_boundary_count"] == 2
    assert payload["counts"]["maturity_boundary_guarded_count"] == 6
    assert payload["counts"]["boundary_subject_count"] == 6
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert source_status["export_script"] == "ready"

    assert rows[
        "scene_input_source_audit:family_readiness_delta:family:ip_patent_documents"
    ].observed_status == "boundary"
    assert rows[
        "scene_count_profile_audit:pack_not_applicable_delta:pack:quick_formatting"
    ].reconciliation_mode == "not_applicable_count_surface"
    assert rows[
        "scene_count_profile_audit:pack_not_applicable_delta:pack:import_ai_boundary"
    ].linked_boundary_subject_ids == ("pack:import_ai_boundary",)
    assert rows[
        "scene_product_readiness:static_closed_not_green:pack:professional_disclosure"
    ].observed_status == "closed->blue_boundary"
    assert rows[
        "scene_product_maturity_upgrade_audit:maturity_l5_blocked:family:ip_patent_documents"
    ].status == "reconciled"


def test_boundary_readiness_reconciliation_filters_by_source():
    report = build_scene_boundary_readiness_reconciliation_audit_report(
        source_id="scene_product_maturity_upgrade_audit",
        project_root=ROOT,
    )

    assert report.status == "passed"
    assert report.row_count == 6
    assert report.reconciled_count == 6
    assert {row.source_id for row in report.rows} == {
        "scene_product_maturity_upgrade_audit"
    }


def test_boundary_readiness_reconciliation_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_readiness_reconciliation_audit.py",
            "--format",
            "json",
            "--source",
            "scene_count_profile_audit",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["row_count"] == 3
    assert payload["counts"]["reconciled_count"] == 3
    assert all(
        row["source_id"] == "scene_count_profile_audit"
        for row in payload["rows"]
    )
    rows = {row["row_id"]: row for row in payload["rows"]}
    quick = rows[
        "scene_count_profile_audit:pack_not_applicable_delta:pack:quick_formatting"
    ]
    assert quick["status"] == "reconciled"
    assert quick["observed_status"] == "not_applicable"
    assert quick["reconciliation_mode"] == "not_applicable_count_surface"
    import_ai = rows[
        "scene_count_profile_audit:pack_not_applicable_delta:pack:import_ai_boundary"
    ]
    assert import_ai["reconciliation_mode"] == (
        "boundary_not_applicable_count_surface"
    )
    assert import_ai["linked_boundary_subject_ids"] == ["pack:import_ai_boundary"]

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_readiness_reconciliation_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Boundary Readiness Reconciliation Audit" in markdown_result.stdout
    assert "Reconciled rows: 15/15" in markdown_result.stdout
    assert "not_applicable_count_surface" in markdown_result.stdout
    assert "scene_boundary_readiness_reconciliation_audit" in markdown_result.stdout


def test_release_gate_includes_boundary_readiness_reconciliation(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert (
        payload["checks"]["scene_boundary_readiness_reconciliation_audit"]["status"]
        == "passed"
    )
    assert payload["counts"]["scene_boundary_readiness_reconciliation_count"] == 15
    assert (
        payload["counts"][
            "scene_boundary_readiness_reconciliation_reconciled_count"
        ]
        == 15
    )
    assert (
        payload["counts"][
            "scene_boundary_readiness_reconciliation_unreconciled_count"
        ]
        == 0
    )
    assert (
        payload["counts"][
            "scene_boundary_readiness_reconciliation_not_applicable_count"
        ]
        == 2
    )
    assert (
        payload["counts"][
            "scene_boundary_readiness_reconciliation_static_closed_boundary_count"
        ]
        == 2
    )
    assert (
        payload["counts"][
            "scene_boundary_readiness_reconciliation_maturity_boundary_guarded_count"
        ]
        == 6
    )
