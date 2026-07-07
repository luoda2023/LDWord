import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_plugin_boundary_confirmation_audit import (  # noqa: E402
    N2_160_REQUIRED_RISK_DOMAIN_IDS,
    audit_scene_plugin_boundary_confirmation_report,
    build_scene_plugin_boundary_confirmation_audit_report,
)


def test_scene_plugin_boundary_confirmation_audit_locks_gate_matrix():
    report = build_scene_plugin_boundary_confirmation_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.gate_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.gate_count == 4
    assert report.issue_count == 0
    assert report.risk_domain_count == 14
    assert report.route_count == 10
    assert report.request_sample_count == 13
    assert report.manual_fixture_count == 11
    assert report.missing_source_evidence_count == 0
    assert audit_scene_plugin_boundary_confirmation_report(report) == ()
    assert tuple(payload["required_risk_domain_ids"]) == (
        N2_160_REQUIRED_RISK_DOMAIN_IDS
    )
    assert {evidence.status for evidence in report.source_evidence} == {"ready"}

    for row in report.rows:
        assert row.status == "ready"
        assert row.issue_ids == ()
        assert row.coverage_pack_plugin_boundary is True
        assert row.manual_confirmation_required is True
        assert row.boundary_report_required is True
        assert row.blocks_core_execution_until_confirmed is True
        assert "manual_decision" in row.report_fields
        assert row.route_ids
        assert row.request_sample_ids
        assert row.request_cell_sample_ids
        assert row.manual_fixture_ids

    journal = rows["journal_publisher_rule_review_gate"]
    assert journal.pack_id == "english_journal"
    assert journal.risk_domain_ids == (
        "publisher_final_layout",
        "unreviewed_journal_rules",
        "citation_source_integrity",
    )
    assert journal.confidence_report_required is False
    assert journal.professional_review_required is False
    assert journal.route_ids == ("english_journal_submission",)
    assert journal.request_sample_ids == ("english_journal_response_letter",)
    assert journal.manual_fixture_ids == (
        "english_journal_publisher_rule_manual_boundary",
    )
    assert journal.report_fields == (
        "target_journal",
        "rule_review_status",
        "citation_source_status",
        "manual_decision",
    )

    exam = rows["exam_ai_complex_diagram_gate"]
    assert exam.pack_id == "exam_education"
    assert exam.risk_domain_ids == (
        "ai_content_quality",
        "complex_diagram_generation",
    )
    assert exam.confidence_report_required is True
    assert exam.professional_review_required is False
    assert exam.route_ids == ("exam_teaching_versions",)
    assert exam.request_sample_ids == ("exam_multi_version",)
    assert exam.manual_fixture_ids == ("exam_education_controls_textboxes",)

    professional = rows["professional_disclosure_review_gate"]
    assert professional.pack_id == "professional_disclosure"
    assert set(professional.risk_domain_ids) == {
        "audit_assurance",
        "legal_opinion",
        "financial_assurance",
        "ip_patent_quality",
        "medical_regulatory",
        "translation_quality",
    }
    assert professional.professional_review_required is True
    assert professional.confidence_report_required is False
    assert set(professional.route_ids) == {
        "finance_quote_documents",
        "regulated_disclosure_documents",
        "ip_patent_manual_boundary",
        "legal_document_manual_boundary",
        "medical_regulatory_manual_boundary",
        "bilingual_review_documents",
    }
    assert set(professional.request_sample_ids) >= {
        "ambiguous_contract_legal_review",
        "professional_finance_quote",
        "professional_esg_archive",
        "professional_patent_claims",
        "professional_bilingual_terms",
        "professional_legal_opinion",
        "professional_medical_regulatory",
    }
    assert professional.manual_fixture_ids == (
        "professional_disclosure_manual_boundary",
        "professional_disclosure_source_quality_degraded",
        "professional_disclosure_finance_table_mapping_boundary",
        "professional_disclosure_patent_claim_quality_boundary",
        "professional_disclosure_bilingual_termbase_boundary",
        "professional_disclosure_regulated_assurance_boundary",
    )

    import_gate = rows["import_ai_conversion_gate"]
    assert import_gate.pack_id == "import_ai_boundary"
    assert set(import_gate.risk_domain_ids) == {
        "ocr_confidence",
        "pdf_conversion",
        "full_latex_conversion",
        "ai_content_quality",
        "complex_diagram_generation",
    }
    assert import_gate.confidence_report_required is True
    assert import_gate.professional_review_required is False
    assert import_gate.route_ids == (
        "import_pdf_thesis_boundary",
        "import_ai_conversion_boundary",
    )
    assert set(import_gate.request_sample_ids) == {
        "import_pdf_thesis",
        "import_ocr_pdf",
        "import_latex_project",
        "import_ai_diagrams",
    }
    assert import_gate.manual_fixture_ids == (
        "import_ai_boundary_blocking_macro",
        "import_ai_boundary_conversion_confidence_degraded",
        "import_ai_boundary_latex_handoff_confidence",
    )
    assert import_gate.report_fields == (
        "source_type",
        "confidence_level",
        "low_confidence_regions",
        "manual_decision",
        "handoff_pack_id",
        "handoff_family_id",
        "handoff_status",
        "fallback_strategy",
    )


def test_scene_plugin_boundary_confirmation_audit_filters_by_risk_domain():
    report = build_scene_plugin_boundary_confirmation_audit_report(
        risk_domain_id="medical_regulatory",
        project_root=ROOT,
    )

    assert report.status == "passed"
    assert report.gate_count == 1
    assert report.rows[0].gate_id == "professional_disclosure_review_gate"
    assert "medical_regulatory_manual_boundary" in report.rows[0].route_ids
    assert "professional_medical_regulatory" in report.rows[0].request_sample_ids


def test_scene_plugin_boundary_confirmation_export_script_writes_json(tmp_path):
    output_path = tmp_path / "plugin_boundary.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_plugin_boundary_confirmation_audit.py",
            "--format",
            "json",
            "--gate",
            "import_ai_conversion_gate",
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
    assert payload["gate_count"] == 1
    assert payload["rows"][0]["gate_id"] == "import_ai_conversion_gate"
    assert payload["rows"][0]["risk_domain_ids"] == [
        "ocr_confidence",
        "pdf_conversion",
        "full_latex_conversion",
        "ai_content_quality",
        "complex_diagram_generation",
    ]


def test_scene_plugin_boundary_confirmation_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_plugin_boundary_confirmation_audit.py",
            "--format",
            "markdown",
            "--risk-domain",
            "translation_quality",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Plugin Boundary Confirmation Audit" in result.stdout
    assert "| Gate | Status | Pack | Risk Domains |" in result.stdout
    assert "professional_disclosure_review_gate" in result.stdout
    assert "translation_quality" in result.stdout
    assert "bilingual_review_documents" in result.stdout


def test_release_gate_includes_scene_plugin_boundary_confirmation_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert (
        payload["checks"]["scene_plugin_boundary_confirmation_audit"]["status"]
        == "passed"
    )
    assert payload["counts"]["scene_plugin_boundary_gate_count"] == 4
    assert payload["counts"]["scene_plugin_boundary_risk_domain_count"] == 14
    assert payload["counts"]["scene_plugin_boundary_route_count"] == 10
    assert payload["counts"]["scene_plugin_boundary_request_sample_count"] == 13
    assert payload["counts"]["scene_plugin_boundary_manual_fixture_count"] == 11
    assert payload["counts"]["scene_plugin_boundary_issue_count"] == 0
    assert (
        payload["counts"][
            "scene_plugin_boundary_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_plugin_boundary_confirmation_audit"]["status"] == "passed"
