import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_boundary_subject_release_dossier_audit import (  # noqa: E402
    audit_scene_boundary_subject_release_dossier_report,
    build_scene_boundary_subject_release_dossier_audit_report,
)


def test_boundary_subject_release_dossiers_group_terminal_traces_by_subject():
    report = build_scene_boundary_subject_release_dossier_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.subject_key: row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_boundary_subject_release_dossier_report(report) == ()
    assert payload["counts"]["subject_count"] == 6
    assert payload["counts"]["ready_subject_count"] == 6
    assert payload["counts"]["pack_subject_count"] == 2
    assert payload["counts"]["family_subject_count"] == 4
    assert payload["counts"]["subject_trace_count"] == 26
    assert payload["counts"]["unique_source_trace_count"] == 24
    assert payload["counts"]["readiness_reconciliation_row_count"] == 14
    assert payload["counts"]["terminal_exception_count"] == 4
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert source_status["export_script"] == "ready"

    assert rows["family:ip_patent_documents"].subject_trace_count == 7
    assert rows["family:ip_patent_documents"].status == "release_dossier_ready"
    assert "boundary_guarded_maturity" in (
        rows["family:ip_patent_documents"].terminal_exception_ids
    )
    assert any(
        row_id.endswith("family:ip_patent_documents")
        for row_id in rows[
            "family:ip_patent_documents"
        ].readiness_reconciliation_row_ids
    )

    assert rows["pack:import_ai_boundary"].subject_trace_count == 8
    assert "static_closed_boundary" in (
        rows["pack:import_ai_boundary"].terminal_exception_ids
    )
    assert rows["pack:professional_disclosure"].subject_trace_count == 5


def test_boundary_subject_release_dossier_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_subject_release_dossier_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["ready_subject_count"] == 6
    assert payload["counts"]["subject_trace_count"] == 26
    rows = {row["subject_key"]: row for row in payload["rows"]}
    import_ai = rows["pack:import_ai_boundary"]
    assert import_ai["subject_trace_count"] == 8
    assert "import_ocr_pdf_latex_plugin_handoff" in (
        import_ai["external_handoff_contract_ids"]
    )
    assert "lossless PDF to Word" in import_ai["excluded_core_claims"]
    assert (
        "static_closed_boundary:scene_product_readiness:static_closed_not_green:pack:import_ai_boundary"
        in import_ai["release_exception_trace_ids"]
    )
    ip_row = rows["family:ip_patent_documents"]
    assert ip_row["subject_trace_count"] == 7
    assert "ip_patent_plugin_handoff" in ip_row["external_handoff_contract_ids"]
    assert "claim quality judgment" in ip_row["excluded_core_claims"]
    assert (
        "boundary_guarded_maturity:family:ip_patent_documents"
        in ip_row["release_exception_trace_ids"]
    )

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_subject_release_dossier_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Boundary Subject Release Dossier Audit" in markdown_result.stdout
    assert "Ready subjects: 6/6" in markdown_result.stdout
    assert "pack:import_ai_boundary" in markdown_result.stdout
    assert "Scene Boundary Subject Release Dossier Audit" in markdown_result.stdout


def test_release_gate_includes_boundary_subject_release_dossiers(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_boundary_subject_release_dossier_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_boundary_subject_release_dossier_subject_count"] == 6
    assert payload["counts"]["scene_boundary_subject_release_dossier_ready_count"] == 6
    assert (
        payload["counts"]["scene_boundary_subject_release_dossier_subject_trace_count"]
        == 26
    )
    assert (
        payload["counts"][
            "scene_boundary_subject_release_dossier_unique_source_trace_count"
        ]
        == 24
    )
    assert (
        payload["counts"][
            "scene_boundary_subject_release_dossier_readiness_reconciliation_row_count"
        ]
        == 14
    )
    assert (
        payload["counts"]["scene_boundary_subject_release_dossier_terminal_exception_count"]
        == 4
    )
