import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_external_handoff_contract_audit import (  # noqa: E402
    SCENE_EXTERNAL_HANDOFF_REQUIRED_FAILURE_POLICY_IDS,
    SCENE_EXTERNAL_HANDOFF_STATUS_IDS,
    audit_scene_external_handoff_contract_report,
    build_scene_external_handoff_contract_audit_report,
)


def test_scene_external_handoff_contract_audit_locks_n2_379_contracts():
    report = build_scene_external_handoff_contract_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.contract_id: row for row in report.rows}

    assert report.status == "passed"
    assert audit_scene_external_handoff_contract_report(report) == ()
    assert report.contract_count == 6
    assert report.ready_contract_count == 6
    assert report.pack_contract_count == 2
    assert report.family_contract_count == 4
    assert report.plugin_gate_count == 2
    assert report.target_plugin_count == 6
    assert report.risk_domain_count == 9
    assert report.report_count == 19
    assert report.ui_surface_count == 14
    assert report.fixture_count == 8
    assert report.status_state_count == 8
    assert report.failure_policy_count == 4
    assert report.issue_count == 0
    assert report.missing_source_evidence_count == 0
    assert tuple(payload["required_status_ids"]) == SCENE_EXTERNAL_HANDOFF_STATUS_IDS
    assert tuple(payload["required_failure_policy_ids"]) == (
        SCENE_EXTERNAL_HANDOFF_REQUIRED_FAILURE_POLICY_IDS
    )
    assert {evidence.status for evidence in report.source_evidence} == {"ready"}

    for row in report.rows:
        assert row.status == "ready"
        assert row.readiness_level == "blue_boundary"
        assert row.issue_ids == ()
        assert "manual_decision" in row.payload_field_ids
        assert "handoff_status" in row.payload_field_ids
        assert "external_receipt_id" in row.payload_field_ids
        assert set(SCENE_EXTERNAL_HANDOFF_STATUS_IDS).issubset(row.status_ids)
        assert set(SCENE_EXTERNAL_HANDOFF_REQUIRED_FAILURE_POLICY_IDS).issubset(
            row.failure_policy_ids
        )
        assert row.boundary_capability_ids
        assert row.fixture_ids
        assert row.required_report_ids
        assert row.excluded_core_claims

    professional = rows["professional_disclosure_plugin_ecosystem_handoff"]
    assert professional.subject_type == "pack"
    assert professional.subject_id == "professional_disclosure"
    assert professional.gap_id == "real plugin ecosystem"
    assert professional.gate_id == "professional_disclosure_review_gate"
    assert professional.target_plugin_id == "professional_disclosure_review_plugin"
    assert "professional_boundary_matrix" in professional.required_report_ids
    assert "professional_review_owner_assignment" in professional.ui_surface_ids
    assert "translation quality guarantee" in professional.excluded_core_claims

    import_contract = rows["import_ocr_pdf_latex_plugin_handoff"]
    assert import_contract.subject_type == "pack"
    assert import_contract.subject_id == "import_ai_boundary"
    assert import_contract.gap_id == "real OCR/PDF/LaTeX plugin integration"
    assert import_contract.gate_id == "import_ai_conversion_gate"
    assert import_contract.target_plugin_id == "import_ai_assistant_plugin"
    assert "confidence_artifact_manifest" in import_contract.required_report_ids
    assert "ocr_pdf_latex_plugin_boundary" in import_contract.required_report_ids
    assert "lossless PDF to Word" in import_contract.excluded_core_claims

    finance = rows["finance_quote_plugin_handoff"]
    assert finance.subject_type == "family"
    assert finance.subject_id == "finance_quote_documents"
    assert finance.gap_id == "finance plugin handoff"
    assert "finance_spreadsheet_mapping_report" in finance.required_report_ids
    assert "quote_source_workbook_id" in finance.payload_field_ids

    patent = rows["ip_patent_plugin_handoff"]
    assert patent.subject_id == "ip_patent_documents"
    assert patent.gap_id == "IP plugin handoff"
    assert "claim_quality_boundary_ui" in patent.required_report_ids
    assert "patentability judgment" in patent.excluded_core_claims

    translation = rows["translation_quality_plugin_handoff"]
    assert translation.subject_id == "bilingual_translation_documents"
    assert translation.gap_id == "translation-quality plugin handoff"
    assert "termbase_ui" in translation.required_report_ids
    assert "unresolved_term_report_id" in translation.payload_field_ids

    regulated = rows["regulated_assurance_review_handoff"]
    assert regulated.subject_id == "regulated_disclosure_documents"
    assert regulated.gap_id == "external assurance review handoff"
    assert "assurance_boundary_ui" in regulated.required_report_ids
    assert "regulated filing completeness conclusion" in regulated.excluded_core_claims


def test_scene_external_handoff_contract_filters_by_subject_and_gate():
    subject_report = build_scene_external_handoff_contract_audit_report(
        subject_id="finance_quote_documents",
        project_root=ROOT,
    )
    gate_report = build_scene_external_handoff_contract_audit_report(
        gate_id="import_ai_conversion_gate",
        project_root=ROOT,
    )

    assert subject_report.status == "passed"
    assert subject_report.contract_count == 1
    assert subject_report.rows[0].contract_id == "finance_quote_plugin_handoff"
    assert gate_report.status == "passed"
    assert gate_report.contract_count == 1
    assert gate_report.rows[0].contract_id == "import_ocr_pdf_latex_plugin_handoff"


def test_scene_external_handoff_contract_export_script_writes_json(tmp_path):
    output_path = tmp_path / "external_handoff_contract.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_external_handoff_contract_audit.py",
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
    assert payload["counts"]["contract_count"] == 1
    assert payload["rows"][0]["contract_id"] == "finance_quote_plugin_handoff"


def test_scene_external_handoff_contract_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_external_handoff_contract_audit.py",
            "--format",
            "markdown",
            "--gate",
            "professional_disclosure_review_gate",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene External Handoff Contract Audit" in result.stdout
    assert "| Contract | Status | Subject | Gap | Gate | Target Plugin |" in result.stdout
    assert "finance_quote_plugin_handoff" in result.stdout
    assert "external_receipt_id" in result.stdout


def test_release_gate_includes_scene_external_handoff_contract_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_external_handoff_contract_audit"]["status"] == (
        "passed"
    )
    assert payload["counts"]["scene_external_handoff_contract_count"] == 6
    assert payload["counts"]["scene_external_handoff_contract_ready_count"] == 6
    assert payload["counts"]["scene_external_handoff_contract_pack_count"] == 2
    assert payload["counts"]["scene_external_handoff_contract_family_count"] == 4
    assert payload["counts"]["scene_external_handoff_contract_plugin_gate_count"] == 2
    assert payload["counts"]["scene_external_handoff_contract_target_plugin_count"] == 6
    assert payload["counts"]["scene_external_handoff_contract_status_state_count"] == 8
    assert payload["counts"]["scene_external_handoff_contract_failure_policy_count"] == 4
    assert payload["counts"]["scene_external_handoff_contract_issue_count"] == 0
    assert (
        payload["counts"][
            "scene_external_handoff_contract_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_external_handoff_contract_audit"]["status"] == "passed"
