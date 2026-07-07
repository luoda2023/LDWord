import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_boundary_subject_release_continuity_audit import (  # noqa: E402
    audit_scene_boundary_subject_release_continuity_report,
    build_scene_boundary_subject_release_continuity_audit_report,
)


EXPECTED_SUBJECTS = {
    "pack:professional_disclosure",
    "pack:import_ai_boundary",
    "family:finance_quote_documents",
    "family:ip_patent_documents",
    "family:bilingual_translation_documents",
    "family:regulated_disclosure_documents",
}


def test_boundary_subject_release_continuity_keeps_subjects_identical_across_layers():
    report = build_scene_boundary_subject_release_continuity_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.subject_key: row for row in report.rows}

    assert report.status == "passed"
    assert audit_scene_boundary_subject_release_continuity_report(report) == ()
    assert {row.subject_key for row in report.rows} == EXPECTED_SUBJECTS
    assert payload["counts"]["subject_count"] == 6
    assert payload["counts"]["ready_subject_count"] == 6
    assert payload["counts"]["maturity_subject_count"] == 6
    assert payload["counts"]["guarded_completion_subject_count"] == 6
    assert payload["counts"]["readiness_reconciliation_subject_count"] == 6
    assert payload["counts"]["terminal_release_subject_count"] == 6
    assert payload["counts"]["subject_dossier_count"] == 6
    assert payload["counts"]["readiness_row_count"] == 14
    assert payload["counts"]["terminal_trace_count"] == 26
    assert payload["counts"]["dossier_trace_count"] == 26
    assert payload["counts"]["mismatch_count"] == 0
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }
    assert source_status["export_script"] == "ready"

    for row in report.rows:
        assert row.status == "continuity_ready"
        assert row.in_maturity
        assert row.in_guarded_completion
        assert row.in_readiness_reconciliation
        assert row.in_terminal_release_exception
        assert row.in_subject_dossier
        assert row.issue_ids == ()
    assert rows["family:ip_patent_documents"].readiness_row_ids
    assert rows["pack:import_ai_boundary"].terminal_trace_ids


def test_boundary_subject_release_continuity_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_subject_release_continuity_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["subject_count"] == 6
    assert payload["counts"]["ready_subject_count"] == 6
    rows = {row["subject_key"]: row for row in payload["rows"]}
    ip_row = rows["family:ip_patent_documents"]
    assert ip_row["status"] == "continuity_ready"
    assert ip_row["in_readiness_reconciliation"] is True
    assert ip_row["in_terminal_release_exception"] is True
    assert (
        "scene_product_maturity_upgrade_audit:maturity_l5_blocked:family:ip_patent_documents"
        in ip_row["readiness_row_ids"]
    )
    assert "boundary_guarded_maturity:family:ip_patent_documents" in (
        ip_row["terminal_trace_ids"]
    )
    import_ai_row = rows["pack:import_ai_boundary"]
    assert len(import_ai_row["terminal_trace_ids"]) == 8
    assert len(import_ai_row["dossier_trace_ids"]) == 8
    assert "boundary_subject_release_dossier" in import_ai_row["evidence_ids"]

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_subject_release_continuity_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Boundary Subject Release Continuity Audit" in (
        markdown_result.stdout
    )
    assert "Subjects ready: 6/6" in markdown_result.stdout
    assert "family:ip_patent_documents" in markdown_result.stdout
    assert "pack:import_ai_boundary" in markdown_result.stdout


def test_release_gate_includes_boundary_subject_release_continuity(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_boundary_subject_release_continuity_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_boundary_subject_release_continuity_subject_count"] == 6
    assert payload["counts"]["scene_boundary_subject_release_continuity_ready_count"] == 6
    assert (
        payload["counts"][
            "scene_boundary_subject_release_continuity_maturity_subject_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_subject_release_continuity_guarded_completion_subject_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_subject_release_continuity_terminal_release_subject_count"
        ]
        == 6
    )
    assert (
        payload["counts"]["scene_boundary_subject_release_continuity_mismatch_count"]
        == 0
    )
