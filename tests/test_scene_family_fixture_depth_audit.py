import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_family_fixture_depth_audit import (  # noqa: E402
    N2_164_REQUIRED_PRIORITIES,
    audit_scene_family_fixture_depth_report,
    build_scene_family_fixture_depth_audit_report,
)


def test_scene_family_fixture_depth_audit_locks_p1_family_fixture_chain():
    report = build_scene_family_fixture_depth_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.family_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.family_count == 15
    assert report.p1_family_count == 11
    assert report.p1_ready_count == 11
    assert report.independent_family_fixture_count == 15
    assert report.manual_boundary_fixture_family_count == 6
    assert report.independent_fixture_count == 36
    assert report.manual_boundary_fixture_count == 9
    assert report.issue_count == 0
    assert report.missing_source_evidence_count == 0
    assert audit_scene_family_fixture_depth_report(report) == ()
    assert tuple(payload["required_priorities"]) == N2_164_REQUIRED_PRIORITIES
    assert {evidence.status for evidence in report.source_evidence} == {"ready"}

    for row in report.rows:
        assert row.status == "ready"
        assert row.issue_ids == ()
        assert row.request_cell_sample_ids
        assert row.docx_surfaces
        assert row.expected_behaviors
        if row.required_priority:
            assert row.priority in {"P1", "P1_CANDIDATE"}
            assert row.independent_fixture_ids
            assert row.direct_request_cell_count > 0
            assert row.fixture_strategy in {
                "independent_family_fixture",
                "independent_and_manual_boundary_fixture",
            }

    thesis = rows["thesis_cn"]
    assert thesis.independent_fixture_ids == (
        "chinese_academic_hidden_formula",
        "chinese_academic_rule_source_degraded",
        "chinese_academic_school_rule_section_confirmation",
    )
    assert thesis.fixture_strategy == "independent_family_fixture"
    assert "school_rule_source_selection" in thesis.report_expectations
    assert "section_classifier_confirmation" in thesis.report_expectations

    journal = rows["journal_en"]
    assert journal.fixture_strategy == "independent_and_manual_boundary_fixture"
    assert journal.independent_fixture_ids == (
        "english_journal_revision_comments",
        "english_journal_bibtex_csl_degraded",
        "english_journal_publisher_rule_manual_boundary",
    )
    assert journal.manual_boundary_fixture_ids == (
        "english_journal_revision_comments",
        "english_journal_publisher_rule_manual_boundary",
    )
    assert "journal_publisher_rule_review_gate" in journal.plugin_gate_ids
    assert "reviewed_journal_profile_update" in journal.report_expectations
    assert "submission_artifact_manifest" in journal.report_expectations
    assert "journal_submission_package" in journal.report_expectations

    exam = rows["exam_teaching"]
    assert exam.fixture_strategy == "independent_and_manual_boundary_fixture"
    assert exam.independent_fixture_ids == (
        "exam_education_controls_textboxes",
        "exam_education_structured_multiversion",
    )
    assert exam.manual_boundary_fixture_ids == ("exam_education_controls_textboxes",)
    assert "exam_ai_complex_diagram_gate" in exam.plugin_gate_ids

    contract = rows["contract_delivery"]
    assert contract.fixture_strategy == "independent_family_fixture"
    assert contract.independent_fixture_ids == (
        "contract_delivery_revisions",
        "contract_delivery_signature_fields_degraded",
    )
    assert contract.request_cell_sample_ids == (
        "contract_signing_consistency",
        "contract_review_revisions",
        "contract_signature_package_fields",
        "ambiguous_contract_legal_review",
    )
    assert "professional_disclosure_review_gate" in contract.plugin_gate_ids

    project = rows["project_application"]
    assert project.independent_fixture_ids == (
        "application_reports_hidden_comments",
        "application_reports_project_attachment_degraded",
        "application_reports_project_budget_manual_boundary",
    )
    assert "skip_report" in project.expected_behaviors
    assert "manual_confirmation" in project.expected_behaviors
    assert "budget_attachment_report" in project.report_expectations
    assert "rule_source_governance" in project.report_expectations
    assert "submission_system_boundary_report" in project.report_expectations

    product = rows["product_sales_documents"]
    assert product.independent_fixture_ids == (
        "application_reports_product_sales_assets",
        "application_reports_product_asset_degraded",
        "application_reports_product_version_manual_boundary",
    )
    assert "skip_report" in product.expected_behaviors
    assert "manual_confirmation" in product.expected_behaviors
    assert "customer_internal_version_report" in product.report_expectations
    assert "asset_consistency_report" in product.report_expectations
    assert "quote_body_disambiguation" in product.report_expectations

    hr = rows["hr_batch_documents"]
    assert hr.independent_fixture_ids == (
        "batch_forms_hr_batch_offer",
        "batch_forms_hr_missing_fields_manual_boundary",
    )
    assert "manual_confirmation" in hr.expected_behaviors
    assert "batch_failure_isolation" in hr.report_expectations
    assert "profile_specific_preview" in hr.report_expectations

    form_batch = rows["form_batch_documents"]
    assert form_batch.independent_fixture_ids == (
        "batch_forms_fixed_layout",
        "batch_forms_fixed_layout_placeholder_manual_boundary",
    )
    assert "manual_confirmation" in form_batch.expected_behaviors
    assert "placeholder_residue_report" in form_batch.report_expectations
    assert "fixed_layout_profile_browser" in form_batch.report_expectations
    assert "answer_sheet_reuse_path" in form_batch.report_expectations

    meeting = rows["meeting_policy_documents"]
    assert meeting.independent_fixture_ids == (
        "official_policy_fields_comments",
        "official_policy_formal_archive_manual_boundary",
        "official_policy_metadata_archive_report",
    )
    assert "manual_confirmation" in meeting.expected_behaviors
    assert "official_metadata_report" in meeting.report_expectations
    assert "formal_internal_archive_manifest" in meeting.report_expectations
    assert "watermark_status_report" in meeting.report_expectations

    long_doc = rows["long_document_publishing"]
    assert long_doc.independent_fixture_ids == (
        "technical_long_docs_skip_objects",
        "technical_long_docs_chapter_inventory_manual_boundary",
        "technical_long_docs_index_appendix_merge_boundary",
    )
    assert "manual_confirmation" in long_doc.expected_behaviors
    assert "chapter_inventory" in long_doc.report_expectations
    assert "index_appendix_inventory" in long_doc.report_expectations
    assert "multi_file_merge_boundary_report" in long_doc.report_expectations
    assert "cross_reference_status_report" in long_doc.report_expectations

    qualification = rows["qualification_archive_packages"]
    assert qualification.independent_fixture_ids == (
        "bidding_materials_attachments",
        "bidding_materials_missing_attachment_degraded",
        "bidding_materials_original_copy_manual_boundary",
        "bidding_materials_consortium_seal_residue_degraded",
    )
    assert "skip_report" in qualification.expected_behaviors
    assert "manual_confirmation" in qualification.expected_behaviors
    assert "missing_items_report" in qualification.report_expectations
    assert "expiry_metadata_report" in qualification.report_expectations
    assert "consortium_archive_manifest" in qualification.report_expectations
    assert "seal_position_residue_report" in qualification.report_expectations
    assert "qualification_authenticity_boundary_report" in (
        qualification.report_expectations
    )

    finance = rows["finance_quote_documents"]
    assert finance.priority == "P2"
    assert finance.fixture_strategy == "independent_and_manual_boundary_fixture"
    assert finance.independent_fixture_ids == (
        "professional_disclosure_source_quality_degraded",
        "professional_disclosure_finance_table_mapping_boundary",
    )
    assert finance.manual_boundary_fixture_ids == (
        "professional_disclosure_manual_boundary",
        "professional_disclosure_source_quality_degraded",
        "professional_disclosure_finance_table_mapping_boundary",
    )
    assert "professional_source_quality_report" in finance.report_expectations
    assert "finance_spreadsheet_mapping_report" in finance.report_expectations
    assert "finance_plugin_handoff" in finance.report_expectations
    assert "professional_boundary_matrix" in finance.report_expectations
    assert "professional_disclosure_review_gate" in finance.plugin_gate_ids

    patent = rows["ip_patent_documents"]
    assert patent.priority == "P2"
    assert patent.fixture_strategy == "independent_and_manual_boundary_fixture"
    assert patent.independent_fixture_ids == (
        "professional_disclosure_patent_claim_quality_boundary",
    )
    assert patent.manual_boundary_fixture_ids == (
        "professional_disclosure_manual_boundary",
        "professional_disclosure_patent_claim_quality_boundary",
    )
    assert "claim_quality_boundary_ui" in patent.report_expectations
    assert "ip_plugin_handoff" in patent.report_expectations
    assert "professional_boundary_matrix" in patent.report_expectations
    assert "professional_disclosure_review_gate" in patent.plugin_gate_ids

    bilingual = rows["bilingual_translation_documents"]
    assert bilingual.priority == "P2"
    assert bilingual.fixture_strategy == "independent_and_manual_boundary_fixture"
    assert bilingual.independent_fixture_ids == (
        "professional_disclosure_bilingual_termbase_boundary",
    )
    assert bilingual.manual_boundary_fixture_ids == (
        "professional_disclosure_manual_boundary",
        "professional_disclosure_bilingual_termbase_boundary",
    )
    assert "termbase_ui" in bilingual.report_expectations
    assert "translation_quality_plugin_handoff" in bilingual.report_expectations
    assert "professional_boundary_matrix" in bilingual.report_expectations
    assert "professional_disclosure_review_gate" in bilingual.plugin_gate_ids

    disclosure = rows["regulated_disclosure_documents"]
    assert disclosure.priority == "P2"
    assert disclosure.fixture_strategy == "independent_and_manual_boundary_fixture"
    assert disclosure.independent_fixture_ids == (
        "professional_disclosure_manual_boundary",
        "professional_disclosure_regulated_assurance_boundary",
    )
    assert disclosure.manual_boundary_fixture_ids == (
        "professional_disclosure_manual_boundary",
        "professional_disclosure_regulated_assurance_boundary",
    )
    assert "regulated_rule_source_governance" in disclosure.report_expectations
    assert "assurance_boundary_ui" in disclosure.report_expectations
    assert "disclosure_archive_manifest" in disclosure.report_expectations
    assert "professional_boundary_matrix" in disclosure.report_expectations
    assert "professional_disclosure_review_gate" in disclosure.plugin_gate_ids


def test_scene_family_fixture_depth_export_script_writes_json(tmp_path):
    output_path = tmp_path / "family_fixture_depth.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_family_fixture_depth_audit.py",
            "--format",
            "json",
            "--priority",
            "P1",
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
    assert payload["counts"]["family_count"] == 8
    assert payload["counts"]["p1_family_count"] == 8
    assert payload["counts"]["p1_ready_count"] == 8
    assert all(row["priority"] == "P1" for row in payload["rows"])
    assert all(row["independent_fixture_ids"] for row in payload["rows"])


def test_scene_family_fixture_depth_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_family_fixture_depth_audit.py",
            "--format",
            "markdown",
            "--family",
            "finance_quote_documents",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Family Fixture Depth Audit" in result.stdout
    assert "| Family | Status | Priority | Strategy |" in result.stdout
    assert "finance_quote_documents" in result.stdout
    assert "manual_boundary_fixture" in result.stdout
    assert "professional_disclosure_manual_boundary" in result.stdout


def test_release_gate_includes_scene_family_fixture_depth_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_family_fixture_depth_audit"]["status"] == "passed"
    assert payload["counts"]["scene_family_fixture_depth_family_count"] == 15
    assert payload["counts"]["scene_family_fixture_depth_p1_family_count"] == 11
    assert payload["counts"]["scene_family_fixture_depth_p1_ready_count"] == 11
    assert (
        payload["counts"]["scene_family_fixture_depth_independent_family_count"]
        == 15
    )
    assert (
        payload["counts"]["scene_family_fixture_depth_manual_boundary_family_count"]
        == 6
    )
    assert payload["counts"]["scene_family_fixture_depth_issue_count"] == 0
    assert (
        payload["counts"][
            "scene_family_fixture_depth_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_family_fixture_depth_audit"]["status"] == "passed"
