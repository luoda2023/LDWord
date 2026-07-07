import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_business_capability_matrix_audit import (  # noqa: E402
    audit_scene_business_capability_matrix_report,
    build_scene_business_capability_matrix_audit_report,
)


def test_business_capability_matrix_locks_n2_181_baseline():
    report = build_scene_business_capability_matrix_audit_report(project_root=ROOT)
    issues, warnings = audit_scene_business_capability_matrix_report(report)
    payload = report.to_payload()
    rows = {row.capability_id: row for row in report.rows}

    assert report.status == "passed"
    assert issues == ()
    assert warnings == report.warnings
    assert report.capability_count == 18
    assert report.ready_capability_count == 18
    assert report.high_priority_capability_count == 11
    assert report.high_priority_ready_count == 11
    assert report.boundary_capability_count == 7
    assert report.manual_gate_capability_count == 10
    assert report.unique_request_cell_count == 46
    assert report.unique_fixture_count == 42
    assert report.missing_journey_group_count == 0
    assert report.adopted_external_record_count == 2
    assert report.issue_count == 0
    assert report.warning_count == 0
    assert report.missing_source_evidence_count == 0
    assert payload["counts"]["capability_count"] == 18
    assert payload["counts"]["adopted_external_record_count"] == 2
    assert tuple(payload["journey_groups"]) == (
        "success",
        "degraded",
        "failure",
        "manual_boundary",
        "failure_or_manual_boundary",
        "handoff",
    )

    assert rows["quick_word_formatting"].status == "ready"
    assert rows["quick_word_formatting"].missing_journey_groups == ()
    assert "quick_formatting_preserve_fields_degraded" in (
        rows["quick_word_formatting"].fixture_ids
    )
    assert "quick_formatting_business_template_cleanup" in (
        rows["quick_word_formatting"].fixture_ids
    )
    assert rows["project_application"].status == "ready"
    assert "application_reports_project_attachment_degraded" in (
        rows["project_application"].fixture_ids
    )
    assert "application_reports_project_budget_manual_boundary" in (
        rows["project_application"].fixture_ids
    )
    assert "missing_items_report" in rows["project_application"].report_expectations
    assert "budget_attachment_report" in (
        rows["project_application"].report_expectations
    )
    assert "submission_system_boundary_report" in (
        rows["project_application"].report_expectations
    )
    assert rows["product_sales_documents"].status == "ready"
    assert "application_reports_product_asset_degraded" in (
        rows["product_sales_documents"].fixture_ids
    )
    assert "application_reports_product_version_manual_boundary" in (
        rows["product_sales_documents"].fixture_ids
    )
    assert "customer_internal_version_report" in (
        rows["product_sales_documents"].report_expectations
    )
    assert "asset_consistency_report" in (
        rows["product_sales_documents"].report_expectations
    )
    assert "quote_body_disambiguation" in (
        rows["product_sales_documents"].report_expectations
    )
    assert rows["exam_teaching"].boundary_policy == "core_with_manual_gate"
    assert rows["exam_teaching"].adopted_external_record_ids == (
        "exam_generator_tech_stack_record",
    )
    assert rows["exam_teaching"].status == "ready"
    assert rows["exam_teaching"].journey_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
    )
    assert rows["exam_teaching"].missing_journey_groups == ()
    assert rows["exam_teaching"].fixture_ids == (
        "exam_education_controls_textboxes",
        "exam_education_structured_multiversion",
    )
    assert rows["thesis_cn"].status == "ready"
    assert rows["thesis_cn"].journey_type_ids == (
        "success",
        "degraded",
        "failure",
        "manual_boundary",
        "handoff",
    )
    assert rows["thesis_cn"].missing_journey_groups == ()
    assert rows["thesis_cn"].fixture_ids == (
        "chinese_academic_hidden_formula",
        "chinese_academic_rule_source_degraded",
        "chinese_academic_school_rule_section_confirmation",
    )
    assert "school_rule_source_selection" in rows["thesis_cn"].report_expectations
    assert "section_classifier_confirmation" in rows["thesis_cn"].report_expectations
    assert rows["journal_en"].adopted_external_record_ids == (
        "count_engine_tech_record",
    )
    assert rows["journal_en"].status == "ready"
    assert rows["journal_en"].journey_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
    )
    assert rows["journal_en"].missing_journey_groups == ()
    assert rows["journal_en"].fixture_ids == (
        "english_journal_revision_comments",
        "english_journal_bibtex_csl_degraded",
        "english_journal_publisher_rule_manual_boundary",
    )
    assert rows["journal_en"].manual_gate_ids == (
        "journal_publisher_rule_review_gate",
    )
    assert "reviewed_journal_profile_update" in rows["journal_en"].report_expectations
    assert "submission_artifact_manifest" in rows["journal_en"].report_expectations
    assert "journal_submission_package" in rows["journal_en"].report_expectations
    assert rows["contract_delivery"].status == "ready"
    assert rows["contract_delivery"].journey_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert rows["contract_delivery"].missing_journey_groups == ()
    assert rows["contract_delivery"].fixture_ids == (
        "contract_delivery_revisions",
        "contract_delivery_signature_fields_degraded",
        "professional_disclosure_manual_boundary",
    )
    assert rows["contract_delivery"].manual_gate_ids == (
        "professional_disclosure_review_gate",
    )
    assert rows["hr_batch_documents"].status == "ready"
    assert rows["hr_batch_documents"].journey_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert rows["hr_batch_documents"].missing_journey_groups == ()
    assert "batch_forms_hr_missing_fields_manual_boundary" in (
        rows["hr_batch_documents"].fixture_ids
    )
    assert rows["form_batch_documents"].status == "ready"
    assert rows["form_batch_documents"].journey_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert rows["form_batch_documents"].missing_journey_groups == ()
    assert "batch_forms_fixed_layout_placeholder_manual_boundary" in (
        rows["form_batch_documents"].fixture_ids
    )
    assert rows["meeting_policy_documents"].status == "ready"
    assert rows["meeting_policy_documents"].journey_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert rows["meeting_policy_documents"].missing_journey_groups == ()
    assert "official_policy_formal_archive_manual_boundary" in (
        rows["meeting_policy_documents"].fixture_ids
    )
    assert "official_policy_metadata_archive_report" in (
        rows["meeting_policy_documents"].fixture_ids
    )
    assert "official_metadata_report" in (
        rows["meeting_policy_documents"].report_expectations
    )
    assert "formal_internal_archive_manifest" in (
        rows["meeting_policy_documents"].report_expectations
    )
    assert "watermark_status_report" in (
        rows["meeting_policy_documents"].report_expectations
    )
    assert rows["long_document_publishing"].status == "ready"
    assert rows["long_document_publishing"].journey_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert rows["long_document_publishing"].missing_journey_groups == ()
    assert "technical_long_docs_chapter_inventory_manual_boundary" in (
        rows["long_document_publishing"].fixture_ids
    )
    assert "technical_long_docs_index_appendix_merge_boundary" in (
        rows["long_document_publishing"].fixture_ids
    )
    assert "chapter_inventory" in (
        rows["long_document_publishing"].report_expectations
    )
    assert "index_appendix_inventory" in (
        rows["long_document_publishing"].report_expectations
    )
    assert "multi_file_merge_boundary_report" in (
        rows["long_document_publishing"].report_expectations
    )
    assert "cross_reference_status_report" in (
        rows["long_document_publishing"].report_expectations
    )
    assert rows["qualification_archive_packages"].status == "ready"
    assert rows["qualification_archive_packages"].journey_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert rows["qualification_archive_packages"].missing_journey_groups == ()
    assert "bidding_materials_missing_attachment_degraded" in (
        rows["qualification_archive_packages"].fixture_ids
    )
    assert "bidding_materials_original_copy_manual_boundary" in (
        rows["qualification_archive_packages"].fixture_ids
    )
    assert "bidding_materials_consortium_seal_residue_degraded" in (
        rows["qualification_archive_packages"].fixture_ids
    )
    assert "missing_items_report" in (
        rows["qualification_archive_packages"].report_expectations
    )
    assert "expiry_metadata_report" in (
        rows["qualification_archive_packages"].report_expectations
    )
    assert "consortium_archive_manifest" in (
        rows["qualification_archive_packages"].report_expectations
    )
    assert "seal_position_residue_report" in (
        rows["qualification_archive_packages"].report_expectations
    )
    assert "qualification_authenticity_boundary_report" in (
        rows["qualification_archive_packages"].report_expectations
    )
    assert rows["import_ai_assistance_boundary"].journey_type_ids == (
        "degraded",
        "failure",
        "manual_boundary",
        "handoff",
    )
    assert rows["import_ai_assistance_boundary"].status == "ready"
    assert "import_ai_boundary_conversion_confidence_degraded" in (
        rows["import_ai_assistance_boundary"].fixture_ids
    )
    assert "import_ai_boundary_latex_handoff_confidence" in (
        rows["import_ai_assistance_boundary"].fixture_ids
    )
    assert "conversion_confidence_report" in (
        rows["import_ai_assistance_boundary"].report_expectations
    )
    assert "confidence_artifact_manifest" in (
        rows["import_ai_assistance_boundary"].report_expectations
    )
    assert "ocr_pdf_latex_plugin_boundary" in (
        rows["import_ai_assistance_boundary"].report_expectations
    )
    assert rows["professional_disclosure_boundary"].status == "ready"
    assert rows["professional_disclosure_boundary"].boundary_policy == (
        "professional_manual_gate"
    )
    assert rows["professional_disclosure_boundary"].request_cell_ids == (
        "ambiguous_contract_legal_review",
        "professional_finance_quote",
        "professional_esg_archive",
        "professional_patent_claims",
        "professional_bilingual_terms",
        "professional_legal_opinion",
        "professional_medical_regulatory",
        "ambiguous_quote_plan",
        "ambiguous_bilingual_document",
    )
    assert "professional_boundary_matrix" in (
        rows["professional_disclosure_boundary"].report_expectations
    )
    assert rows["finance_quote_documents"].boundary_policy == (
        "professional_manual_gate"
    )
    assert rows["finance_quote_documents"].request_cell_ids == (
        "professional_finance_quote",
    )
    assert "professional_disclosure_source_quality_degraded" in (
        rows["finance_quote_documents"].fixture_ids
    )
    assert "professional_disclosure_finance_table_mapping_boundary" in (
        rows["finance_quote_documents"].fixture_ids
    )
    assert "professional_source_quality_report" in (
        rows["finance_quote_documents"].report_expectations
    )
    assert "finance_spreadsheet_mapping_report" in (
        rows["finance_quote_documents"].report_expectations
    )
    assert "finance_plugin_handoff" in (
        rows["finance_quote_documents"].report_expectations
    )
    assert "professional_disclosure_review_gate" in (
        rows["finance_quote_documents"].manual_gate_ids
    )
    assert rows["ip_patent_documents"].request_cell_ids == (
        "professional_patent_claims",
    )
    assert "claim_quality_boundary_ui" in (
        rows["ip_patent_documents"].report_expectations
    )
    assert "ip_plugin_handoff" in rows["ip_patent_documents"].report_expectations
    assert rows["bilingual_translation_documents"].request_cell_ids == (
        "professional_bilingual_terms",
    )
    assert "termbase_ui" in (
        rows["bilingual_translation_documents"].report_expectations
    )
    assert "translation_quality_plugin_handoff" in (
        rows["bilingual_translation_documents"].report_expectations
    )
    assert rows["regulated_disclosure_documents"].request_cell_ids == (
        "professional_esg_archive",
    )
    assert "regulated_rule_source_governance" in (
        rows["regulated_disclosure_documents"].report_expectations
    )
    assert "assurance_boundary_ui" in (
        rows["regulated_disclosure_documents"].report_expectations
    )
    assert all(
        "scene_control_runtime_consistency_audit" in row.control_alignment_ids
        for row in report.rows
    )
    assert Counter(warning.kind for warning in report.warnings) == {}
    assert all(evidence.status == "ready" for evidence in report.source_evidence)


def test_business_capability_matrix_filters_and_exports(tmp_path):
    education = build_scene_business_capability_matrix_audit_report(
        group_id="education_exam",
        project_root=ROOT,
    )
    p2 = build_scene_business_capability_matrix_audit_report(
        priority="P2",
        project_root=ROOT,
    )

    assert [row.capability_id for row in education.rows] == ["exam_teaching"]
    assert education.warning_count == 0
    assert p2.capability_count == 4
    assert p2.ready_capability_count == 4

    output_path = tmp_path / "business_capability_matrix.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_business_capability_matrix_audit.py",
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["counts"]["capability_count"] == 18
    assert payload["counts"]["missing_journey_group_count"] == 0
    assert payload["rows"][0]["capability_id"] == "quick_word_formatting"

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_business_capability_matrix_audit.py",
            "--format",
            "markdown",
            "--group",
            "education_exam",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "Business Capability Matrix Audit" in markdown_result.stdout
    assert "exam_generator_tech_stack_record" in markdown_result.stdout
    assert "| exam_teaching | ready |" in markdown_result.stdout


def test_release_gate_includes_business_capability_matrix(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path / "gate")

    assert payload["checks"]["scene_business_capability_matrix_audit"]["status"] == (
        "passed"
    )
    assert payload["counts"]["scene_business_capability_matrix_count"] == 18
    assert payload["counts"]["scene_business_capability_matrix_ready_count"] == 18
    assert (
        payload["counts"]["scene_business_capability_matrix_high_priority_count"]
        == 11
    )
    assert (
        payload["counts"]["scene_business_capability_matrix_high_priority_ready_count"]
        == 11
    )
    assert payload["counts"]["scene_business_capability_matrix_boundary_count"] == 7
    assert payload["counts"]["scene_business_capability_matrix_manual_gate_count"] == 10
    assert (
        payload["counts"]["scene_business_capability_matrix_missing_journey_group_count"]
        == 0
    )
    assert (
        payload["counts"]["scene_business_capability_matrix_adopted_external_record_count"]
        == 2
    )
    assert payload["counts"]["scene_business_capability_matrix_issue_count"] == 0
    assert payload["counts"]["scene_business_capability_matrix_warning_count"] == 0
    assert (
        payload["counts"]["scene_business_capability_matrix_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_business_capability_matrix_audit"]["status"] == "passed"
