import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_boundary_guarded_completion_audit import (  # noqa: E402
    SCENE_BOUNDARY_GUARDED_COMPLETION_REQUIRED_EVIDENCE_IDS,
    audit_scene_boundary_guarded_completion_report,
    build_scene_boundary_guarded_completion_audit_report,
)


def test_scene_boundary_guarded_completion_audit_locks_n2_380_subjects():
    report = build_scene_boundary_guarded_completion_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {f"{row.subject_type}:{row.subject_id}": row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_boundary_guarded_completion_report(report) == ()
    assert report.subject_count == 6
    assert report.ready_subject_count == 6
    assert report.pack_subject_count == 2
    assert report.family_subject_count == 4
    assert report.retained_gap_count == 6
    assert report.external_contract_count == 6
    assert report.boundary_capability_count == 6
    assert report.plugin_gate_count == 2
    assert report.target_plugin_count == 6
    assert report.risk_domain_count == 11
    assert report.excluded_core_claim_count == 14
    assert report.issue_count == 0
    assert report.missing_source_evidence_count == 0
    assert tuple(payload["required_evidence_ids"]) == (
        SCENE_BOUNDARY_GUARDED_COMPLETION_REQUIRED_EVIDENCE_IDS
    )
    assert {evidence.status for evidence in report.source_evidence} == {"ready"}
    assert source_status["export_script"] == "ready"

    for row in report.rows:
        assert row.status == "boundary_guarded_complete"
        assert row.readiness_level == "blue_boundary"
        assert row.maturity_status == "boundary_guarded"
        assert row.remaining_gap_ids
        assert row.boundary_capability_ids
        assert row.plugin_gate_ids
        assert row.external_handoff_contract_ids
        assert row.target_plugin_ids
        assert row.report_ids
        assert row.fixture_ids
        assert row.excluded_core_claims
        assert row.issue_ids == ()
        assert row.evidence_ids == (
            SCENE_BOUNDARY_GUARDED_COMPLETION_REQUIRED_EVIDENCE_IDS
        )

    professional = rows["pack:professional_disclosure"]
    assert professional.remaining_gap_ids == ("real plugin ecosystem",)
    assert professional.boundary_capability_ids == (
        "professional_disclosure_boundary_matrix",
    )
    assert professional.external_handoff_contract_ids == (
        "professional_disclosure_plugin_ecosystem_handoff",
    )
    assert "translation quality guarantee" in professional.excluded_core_claims

    import_boundary = rows["pack:import_ai_boundary"]
    assert import_boundary.remaining_gap_ids == (
        "real OCR/PDF/LaTeX plugin integration",
    )
    assert import_boundary.boundary_capability_ids == (
        "import_ai_boundary_confidence_matrix",
    )
    assert import_boundary.external_handoff_contract_ids == (
        "import_ocr_pdf_latex_plugin_handoff",
    )
    assert "lossless PDF to Word" in import_boundary.excluded_core_claims

    finance = rows["family:finance_quote_documents"]
    assert finance.remaining_gap_ids == ("finance plugin handoff",)
    assert finance.boundary_capability_ids == ("finance_quote_boundary_depth",)
    assert finance.external_handoff_contract_ids == (
        "finance_quote_plugin_handoff",
    )
    assert "quotation correctness" in finance.excluded_core_claims

    patent = rows["family:ip_patent_documents"]
    assert patent.external_handoff_contract_ids == ("ip_patent_plugin_handoff",)
    assert "patentability judgment" in patent.excluded_core_claims

    translation = rows["family:bilingual_translation_documents"]
    assert translation.external_handoff_contract_ids == (
        "translation_quality_plugin_handoff",
    )
    assert "silent meaning rewrite" in translation.excluded_core_claims

    regulated = rows["family:regulated_disclosure_documents"]
    assert regulated.external_handoff_contract_ids == (
        "regulated_assurance_review_handoff",
    )
    assert "regulated filing completeness conclusion" in (
        regulated.excluded_core_claims
    )


def test_scene_boundary_guarded_completion_filters_by_subject():
    report = build_scene_boundary_guarded_completion_audit_report(
        subject_id="finance_quote_documents",
        project_root=ROOT,
    )

    assert report.status == "passed"
    assert report.subject_count == 1
    assert report.rows[0].subject_id == "finance_quote_documents"
    assert report.rows[0].status == "boundary_guarded_complete"
    assert report.rows[0].external_handoff_contract_ids == (
        "finance_quote_plugin_handoff",
    )


def test_scene_boundary_guarded_completion_export_script_writes_json(tmp_path):
    output_path = tmp_path / "boundary_guarded_completion.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_guarded_completion_audit.py",
            "--format",
            "json",
            "--subject",
            "finance_quote_documents",
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
    assert payload["counts"]["subject_count"] == 1
    assert payload["rows"][0]["subject_id"] == "finance_quote_documents"
    assert payload["rows"][0]["status"] == "boundary_guarded_complete"
    assert payload["rows"][0]["external_handoff_contract_ids"] == [
        "finance_quote_plugin_handoff"
    ]
    assert "quotation correctness" in payload["rows"][0]["excluded_core_claims"]


def test_scene_boundary_guarded_completion_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_boundary_guarded_completion_audit.py",
            "--format",
            "markdown",
            "--subject",
            "professional_disclosure",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Boundary Guarded Completion Audit" in result.stdout
    assert "| Subject | Status | Readiness | Maturity |" in result.stdout
    assert "pack:professional_disclosure" in result.stdout
    assert "boundary_guarded_complete" in result.stdout
    assert "professional_disclosure_plugin_ecosystem_handoff" in result.stdout


def test_release_gate_includes_scene_boundary_guarded_completion_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_boundary_guarded_completion_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_boundary_guarded_completion_subject_count"] == 6
    assert payload["counts"]["scene_boundary_guarded_completion_ready_count"] == 6
    assert payload["counts"]["scene_boundary_guarded_completion_pack_count"] == 2
    assert payload["counts"]["scene_boundary_guarded_completion_family_count"] == 4
    assert payload["counts"]["scene_boundary_guarded_completion_retained_gap_count"] == 6
    assert (
        payload["counts"][
            "scene_boundary_guarded_completion_external_contract_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_guarded_completion_boundary_capability_count"
        ]
        == 6
    )
    assert payload["counts"]["scene_boundary_guarded_completion_plugin_gate_count"] == 2
    assert payload["counts"]["scene_boundary_guarded_completion_target_plugin_count"] == 6
    assert payload["counts"]["scene_boundary_guarded_completion_risk_domain_count"] == 11
    assert (
        payload["counts"][
            "scene_boundary_guarded_completion_excluded_core_claim_count"
        ]
        == 14
    )
    assert payload["counts"]["scene_boundary_guarded_completion_issue_count"] == 0
    assert (
        payload["counts"][
            "scene_boundary_guarded_completion_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_boundary_guarded_completion_audit"]["status"] == "passed"
