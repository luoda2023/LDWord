import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_retained_gap_exit_criteria_audit import (  # noqa: E402
    audit_scene_retained_gap_exit_criteria_report,
    build_scene_retained_gap_exit_criteria_audit_report,
)


def test_retained_gap_exit_criteria_keep_boundary_gaps_release_limited():
    report = build_scene_retained_gap_exit_criteria_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.criteria_id: row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_retained_gap_exit_criteria_report(report) == ()
    assert payload["counts"]["criteria_count"] == 6
    assert payload["counts"]["release_allowed_count"] == 6
    assert payload["counts"]["envelope_link_count"] == 6
    assert payload["counts"]["handoff_link_count"] == 6
    assert payload["counts"]["guarded_completion_link_count"] == 6
    assert payload["counts"]["boundary_capability_link_count"] == 6
    assert payload["counts"]["exit_signal_count"] == 14
    assert payload["counts"]["external_receipt_target_count"] == 8
    assert payload["counts"]["external_receipt_alignment_count"] == 6
    assert payload["counts"]["prohibited_core_claim_count"] == 14
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert source_status["export_script"] == "ready"
    assert source_status["n2_393j_plan"] == "ready"

    professional = rows["pack:professional_disclosure:real plugin ecosystem"]
    assert professional.status == "release_allowed_with_exit_criteria"
    assert professional.boundary_capability_ids == (
        "professional_disclosure_boundary_matrix",
    )
    assert "reviewed_plugin_receipt_contract" in professional.external_receipt_ids
    assert "external_review_result_ingestion" in professional.exit_signal_ids
    assert set(professional.external_receipt_ids).issubset(
        set(professional.exit_signal_ids)
    )
    assert "audit opinion" in professional.prohibited_core_claim_ids

    import_ai = rows[
        "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration"
    ]
    assert "lossless PDF to Word" in import_ai.prohibited_core_claim_ids
    assert "fallback_report_required" in import_ai.release_condition_ids
    assert "loss_review_artifact_roundtrip" in import_ai.external_receipt_ids
    assert set(import_ai.external_receipt_ids).issubset(set(import_ai.exit_signal_ids))


def test_retained_gap_exit_criteria_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_retained_gap_exit_criteria_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["criteria_count"] == 6
    assert payload["counts"]["release_allowed_count"] == 6
    assert payload["counts"]["external_receipt_alignment_count"] == 6
    rows = {row["criteria_id"]: row for row in payload["rows"]}
    ip_criteria = rows["family:ip_patent_documents:IP plugin handoff"]
    assert ip_criteria["status"] == "release_allowed_with_exit_criteria"
    assert ip_criteria["boundary_capability_ids"] == ["ip_patent_boundary_depth"]
    assert ip_criteria["external_receipt_ids"] == ["claim_quality_review_receipt"]
    assert "claim_quality_review_receipt" in ip_criteria["exit_signal_ids"]
    assert "patentability judgment" in ip_criteria["prohibited_core_claim_ids"]
    regulated_criteria = rows[
        "family:regulated_disclosure_documents:external assurance review handoff"
    ]
    assert "assurance_receipt_archive" in regulated_criteria["exit_signal_ids"]
    assert (
        "regulated filing completeness conclusion"
        in regulated_criteria["prohibited_core_claim_ids"]
    )

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_retained_gap_exit_criteria_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Retained Gap Exit Criteria Audit" in markdown_result.stdout
    assert "Release allowed: 6/6" in markdown_result.stdout
    assert "Receipt alignment: 6/6" in markdown_result.stdout
    assert "claim_quality_review_receipt" in markdown_result.stdout
    assert "professional_disclosure" in markdown_result.stdout
    assert "regulated_disclosure_documents" in markdown_result.stdout


def test_release_gate_includes_retained_gap_exit_criteria(tmp_path, capsys):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_retained_gap_exit_criteria_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_retained_gap_exit_criteria_count"] == 6
    assert (
        payload["counts"][
            "scene_retained_gap_exit_criteria_release_allowed_count"
        ]
        == 6
    )
    assert (
        payload["counts"]["scene_retained_gap_exit_criteria_envelope_link_count"]
        == 6
    )
    assert (
        payload["counts"]["scene_retained_gap_exit_criteria_handoff_link_count"]
        == 6
    )
    assert (
        payload["counts"][
            "scene_retained_gap_exit_criteria_guarded_completion_link_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_retained_gap_exit_criteria_boundary_capability_link_count"
        ]
        == 6
    )
    assert payload["counts"]["scene_retained_gap_external_receipt_target_count"] == 8
    assert (
        payload["counts"]["scene_retained_gap_external_receipt_alignment_count"]
        == 6
    )
    assert payload["counts"]["scene_retained_gap_exit_criteria_issue_count"] == 0

    from scripts.verify_scene_matrix_release_gate import main

    assert main(["--output-dir", str(tmp_path / "gate-output")]) == 0
    output = capsys.readouterr().out
    assert "retained_gap_exit_criteria=6/6 release-allowed" in output
    assert "retained_gap_receipts=6/6 aligned" in output
