import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_boundary_maturity_release_envelope_audit import (  # noqa: E402
    audit_scene_boundary_maturity_release_envelope_report,
    build_scene_boundary_maturity_release_envelope_audit_report,
)


def test_boundary_maturity_release_envelopes_keep_retained_gaps_traceable():
    report = build_scene_boundary_maturity_release_envelope_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.envelope_id: row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_boundary_maturity_release_envelope_report(report) == ()
    assert payload["counts"]["envelope_count"] == 6
    assert payload["counts"]["ready_envelope_count"] == 6
    assert payload["counts"]["l5_blocker_enveloped_count"] == 6
    assert payload["counts"]["maturity_boundary_count"] == 6
    assert payload["counts"]["external_handoff_count"] == 6
    assert payload["counts"]["guarded_completion_count"] == 6
    assert payload["counts"]["readiness_reconciliation_count"] == 6
    assert payload["counts"]["terminal_trace_count"] == 6
    assert payload["counts"]["release_dossier_count"] == 6
    assert payload["counts"]["subject_continuity_count"] == 6
    assert payload["counts"]["retained_gap_count"] == 6
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert source_status["export_script"] == "ready"
    assert source_status["n2_393e_plan"] == "ready"

    assert rows[
        "pack:professional_disclosure:real plugin ecosystem"
    ].external_handoff_contract_id == "professional_disclosure_plugin_ecosystem_handoff"
    assert rows[
        "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration"
    ].guarded_completion_status == "boundary_guarded_complete"
    assert rows[
        "family:ip_patent_documents:IP plugin handoff"
    ].subject_continuity_status == "continuity_ready"
    assert rows[
        "family:regulated_disclosure_documents:external assurance review handoff"
    ].release_dossier_status == "release_dossier_ready"


def test_boundary_maturity_release_envelope_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_maturity_release_envelope_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["envelope_count"] == 6
    assert payload["counts"]["ready_envelope_count"] == 6
    assert payload["counts"]["l5_blocker_enveloped_count"] == 6
    rows = {row["envelope_id"]: row for row in payload["rows"]}
    ip_envelope = rows["family:ip_patent_documents:IP plugin handoff"]
    assert ip_envelope["external_handoff_contract_id"] == (
        "ip_patent_plugin_handoff"
    )
    assert ip_envelope["subject_continuity_status"] == "continuity_ready"
    assert "boundary_subject_release_continuity" in ip_envelope["evidence_ids"]
    regulated_envelope = rows[
        "family:regulated_disclosure_documents:external assurance review handoff"
    ]
    assert regulated_envelope["release_dossier_status"] == "release_dossier_ready"
    assert "terminal_release_trace" in regulated_envelope["evidence_ids"]

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_maturity_release_envelope_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Boundary Maturity Release Envelope Audit" in (
        markdown_result.stdout
    )
    assert "Envelopes ready: 6/6" in markdown_result.stdout
    assert "professional_disclosure" in markdown_result.stdout
    assert "regulated_disclosure_documents" in markdown_result.stdout


def test_release_gate_includes_boundary_maturity_release_envelopes(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_boundary_maturity_release_envelope_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_boundary_maturity_release_envelope_count"] == 6
    assert (
        payload["counts"]["scene_boundary_maturity_release_envelope_ready_count"]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_maturity_release_envelope_l5_blocker_enveloped_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_maturity_release_envelope_external_handoff_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_maturity_release_envelope_guarded_completion_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_maturity_release_envelope_subject_continuity_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_maturity_release_envelope_retained_gap_count"
        ]
        == 6
    )
    assert payload["counts"]["retained_gap_enveloped_count"] == 6
    assert (
        payload["counts"]["retained_gap_enveloped_count"]
        == payload["counts"]["scene_product_maturity_upgrade_gap_count"]
    )
    assert (
        payload["counts"]["scene_boundary_maturity_release_envelope_issue_count"]
        == 0
    )
