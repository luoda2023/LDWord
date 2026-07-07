import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_boundary_capability_matrix import (  # noqa: E402
    SCENE_BOUNDARY_CAPABILITY_REQUIRED_DECISION_IDS,
    SCENE_BOUNDARY_CAPABILITY_REQUIRED_GUARDRAIL_IDS,
    audit_scene_boundary_capability_report,
    build_scene_boundary_capability_audit_report,
    list_scene_boundary_capabilities,
)
from src.ui.panels.scene_summary_projection import (  # noqa: E402
    build_boundary_capability_evidence_summary_items,
)
from src.config.scene import SceneWorkspace  # noqa: E402


def test_boundary_capability_matrix_locks_professional_and_import_boundaries():
    report = build_scene_boundary_capability_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.capability_id: row for row in report.rows}

    assert report.status == "passed"
    assert audit_scene_boundary_capability_report(report) == ()
    assert report.capability_count == 6
    assert report.ready_capability_count == 6
    assert report.professional_capability_count == 5
    assert report.import_ai_capability_count == 1
    assert report.fixture_count == 9
    assert report.report_expectation_count == 19
    assert report.ui_surface_count == 7
    assert report.risk_domain_count == 9
    assert report.decision_requirement_count == 4
    assert report.external_receipt_count == 8
    assert report.release_guardrail_count == 4
    assert report.issue_count == 0
    assert report.missing_source_evidence_count == 0
    assert payload["counts"]["ready_capability_count"] == 6
    assert payload["counts"]["risk_domain_count"] == 9
    assert payload["counts"]["decision_requirement_count"] == 4
    assert payload["counts"]["external_receipt_count"] == 8
    assert payload["counts"]["release_guardrail_count"] == 4
    assert {evidence.status for evidence in report.source_evidence} == {"ready"}
    assert all(row.risk_domain_ids for row in report.rows)
    assert all(row.external_receipt_ids for row in report.rows)
    assert all(
        set(SCENE_BOUNDARY_CAPABILITY_REQUIRED_DECISION_IDS).issubset(
            row.decision_requirement_ids
        )
        for row in report.rows
    )
    assert all(
        set(SCENE_BOUNDARY_CAPABILITY_REQUIRED_GUARDRAIL_IDS).issubset(
            row.release_guardrail_ids
        )
        for row in report.rows
    )

    professional = rows["professional_disclosure_boundary_matrix"]
    assert professional.status == "ready"
    assert professional.subject_type == "pack"
    assert professional.subject_id == "professional_disclosure"
    assert professional.plugin_gate_id == "professional_disclosure_review_gate"
    assert "professional_boundary_matrix" in professional.report_expectation_ids
    assert "professional_disclosure_regulated_assurance_boundary" in (
        professional.fixture_ids
    )
    assert "professional_medical_regulatory" in (
        professional.high_frequency_sample_ids
    )
    assert "medical_regulatory" in professional.risk_domain_ids
    assert "external_review_result_ingestion" in professional.external_receipt_ids

    import_ai = rows["import_ai_boundary_confidence_matrix"]
    assert import_ai.plugin_gate_id == "import_ai_conversion_gate"
    assert "confidence_artifact_manifest" in import_ai.report_expectation_ids
    assert "ocr_pdf_latex_plugin_boundary" in import_ai.report_expectation_ids
    assert "import_ai_boundary_latex_handoff_confidence" in import_ai.fixture_ids
    assert import_ai.handoff_target_ids == ("chinese_academic", "thesis_cn")
    assert "ocr_confidence" in import_ai.risk_domain_ids
    assert "loss_review_artifact_roundtrip" in import_ai.external_receipt_ids

    finance = rows["finance_quote_boundary_depth"]
    assert finance.family_id == "finance_quote_documents"
    assert finance.material_schema_ids == ("finance_quote_fields_v1",)
    assert "finance_spreadsheet_mapping_report" in finance.report_expectation_ids
    assert "finance_spreadsheet_mapping_report" in finance.ui_surface_ids
    assert finance.risk_domain_ids == ("financial_assurance",)
    assert finance.external_receipt_ids == ("quote_source_reconciliation_receipt",)

    patent = rows["ip_patent_boundary_depth"]
    assert patent.family_id == "ip_patent_documents"
    assert "claim_quality_boundary_ui" in patent.report_expectation_ids
    assert "ip_plugin_handoff" in patent.report_expectation_ids
    assert "ip_patent_quality" in patent.risk_domain_ids
    assert patent.external_receipt_ids == ("claim_quality_review_receipt",)

    bilingual = rows["bilingual_translation_boundary_depth"]
    assert bilingual.family_id == "bilingual_translation_documents"
    assert "termbase_ui" in bilingual.report_expectation_ids
    assert "translation_quality_plugin_handoff" in bilingual.report_expectation_ids
    assert bilingual.risk_domain_ids == ("translation_quality",)
    assert bilingual.external_receipt_ids == ("termbase_review_receipt",)

    disclosure = rows["regulated_disclosure_boundary_depth"]
    assert disclosure.family_id == "regulated_disclosure_documents"
    assert "regulated_rule_source_governance" in disclosure.report_expectation_ids
    assert "assurance_boundary_ui" in disclosure.report_expectation_ids
    assert disclosure.risk_domain_ids == ("audit_assurance",)
    assert disclosure.external_receipt_ids == ("assurance_receipt_archive",)


def test_boundary_capability_matrix_filters_and_scene_summary_projection():
    professional_specs = list_scene_boundary_capabilities(boundary_group="professional")
    import_specs = list_scene_boundary_capabilities(boundary_group="import_ai")

    assert len(professional_specs) == 5
    assert len(import_specs) == 1

    scene = SceneWorkspace(scene_id="professional_disclosure", category="professional_disclosure")
    items = {
        item.key: item
        for item in build_boundary_capability_evidence_summary_items(scene)
    }

    assert items["boundary_capability_evidence"].value == "5 项能力"
    tooltip = items["boundary_capability_evidence"].tooltip
    assert "professional_boundary_matrix" in tooltip
    assert "finance_spreadsheet_mapping_report" in tooltip
    assert "professional_disclosure_review_gate" in tooltip
    assert "financial_assurance" in tooltip
    assert "quote_source_reconciliation_receipt" in tooltip


def test_release_gate_includes_boundary_capability_matrix(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_boundary_capability_matrix"]["status"] == (
        "passed"
    )
    assert payload["counts"]["scene_boundary_capability_count"] == 6
    assert payload["counts"]["scene_boundary_capability_ready_count"] == 6
    assert payload["counts"]["scene_boundary_capability_professional_count"] == 5
    assert payload["counts"]["scene_boundary_capability_import_ai_count"] == 1
    assert payload["counts"]["scene_boundary_capability_fixture_count"] == 9
    assert payload["counts"]["scene_boundary_capability_report_expectation_count"] == 19
    assert payload["counts"]["scene_boundary_capability_ui_surface_count"] == 7
    assert payload["counts"]["scene_boundary_capability_risk_domain_count"] == 9
    assert (
        payload["counts"]["scene_boundary_capability_decision_requirement_count"]
        == 4
    )
    assert payload["counts"]["scene_boundary_capability_external_receipt_count"] == 8
    assert payload["counts"]["scene_boundary_capability_release_guardrail_count"] == 4
    assert payload["counts"]["scene_boundary_capability_issue_count"] == 0
    assert (
        payload["counts"]["scene_boundary_capability_missing_source_evidence_count"]
        == 0
    )
