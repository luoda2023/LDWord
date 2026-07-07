import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_family_subscene_audit import (  # noqa: E402
    audit_scene_family_subscene_report,
    build_scene_family_subscene_audit_report,
)


def test_scene_family_subscene_audit_locks_n2_158_family_chain():
    report = build_scene_family_subscene_audit_report()
    rows = {row.family_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.family_count == 15
    assert report.issue_count == 0
    assert report.warning_count == 0
    assert report.request_cell_count == 35
    assert report.direct_family_fixture_count == 15
    assert report.manual_boundary_family_count == 6
    assert audit_scene_family_subscene_report(report) == ()

    for row in report.rows:
        assert row.pack_ids
        assert row.request_cell_count >= 1
        assert row.matched_request_cell_count >= 1
        assert row.delivery_preset_ids
        assert row.workflow_archetype_ids
        assert row.ooxml_touchpoints
        assert row.required_closure_count > 0
        assert row.boundary_count > 0
        assert row.has_application_defaults or row.plugin_boundary_only

    hr = rows["hr_batch_documents"]
    assert hr.priority == "P1"
    assert hr.request_cell_count == 2
    assert hr.direct_request_cell_count == 2
    assert "batch_hr_offer" in hr.request_cell_sample_ids
    assert "batch_employee_certificate" in hr.request_cell_sample_ids
    assert hr.sample_fixture_ids == (
        "batch_forms_hr_batch_offer",
        "batch_forms_hr_missing_fields_manual_boundary",
    )
    assert hr.application_default_delivery_preset_id == "per_person_docx"

    exam = rows["exam_teaching"]
    assert exam.direct_request_cell_count == 2
    assert exam.manual_boundary_request_cell_count == 1
    assert "exam_ai_complex_diagram_gate" in exam.plugin_gate_ids
    assert exam.sample_fixture_ids == (
        "exam_education_controls_textboxes",
        "exam_education_structured_multiversion",
    )

    thesis = rows["thesis_cn"]
    assert thesis.sample_fixture_ids == (
        "chinese_academic_hidden_formula",
        "chinese_academic_rule_source_degraded",
        "chinese_academic_school_rule_section_confirmation",
    )

    journal = rows["journal_en"]
    assert journal.direct_request_cell_count == 2
    assert journal.manual_boundary_request_cell_count == 1
    assert journal.sample_fixture_ids == (
        "english_journal_revision_comments",
        "english_journal_bibtex_csl_degraded",
        "english_journal_publisher_rule_manual_boundary",
    )
    assert journal.plugin_gate_ids == ("journal_publisher_rule_review_gate",)

    contract = rows["contract_delivery"]
    assert contract.request_cell_count == 4
    assert contract.direct_request_cell_count == 3
    assert contract.ambiguous_request_cell_count == 1
    assert contract.request_cell_sample_ids == (
        "contract_signing_consistency",
        "contract_review_revisions",
        "contract_signature_package_fields",
        "ambiguous_contract_legal_review",
    )
    assert contract.sample_fixture_ids == (
        "contract_delivery_revisions",
        "contract_delivery_signature_fields_degraded",
    )
    assert "professional_disclosure_review_gate" in contract.plugin_gate_ids

    project = rows["project_application"]
    assert project.sample_fixture_ids == (
        "application_reports_hidden_comments",
        "application_reports_project_attachment_degraded",
        "application_reports_project_budget_manual_boundary",
    )
    assert project.direct_request_cell_count == 2

    product = rows["product_sales_documents"]
    assert product.sample_fixture_ids == (
        "application_reports_product_sales_assets",
        "application_reports_product_asset_degraded",
        "application_reports_product_version_manual_boundary",
    )
    assert product.direct_request_cell_count == 2

    finance = rows["finance_quote_documents"]
    assert finance.has_application_defaults is True
    assert finance.application_default_delivery_preset_id == "customer_quote"
    assert finance.sample_fixture_ids == (
        "professional_disclosure_source_quality_degraded",
        "professional_disclosure_finance_table_mapping_boundary",
    )
    assert finance.manual_boundary_fixture_ids == (
        "professional_disclosure_manual_boundary",
        "professional_disclosure_source_quality_degraded",
        "professional_disclosure_finance_table_mapping_boundary",
    )
    assert "professional_disclosure_review_gate" in finance.plugin_gate_ids

    patent = rows["ip_patent_documents"]
    assert patent.plugin_boundary_only is True
    assert patent.has_application_defaults is False
    assert patent.manual_boundary_request_cell_count == 1
    assert patent.sample_fixture_ids == (
        "professional_disclosure_patent_claim_quality_boundary",
    )
    assert "professional_disclosure_review_gate" in patent.plugin_gate_ids

    bilingual = rows["bilingual_translation_documents"]
    assert bilingual.sample_fixture_ids == (
        "professional_disclosure_bilingual_termbase_boundary",
    )
    assert bilingual.application_default_delivery_preset_id == "bilingual_review_copy"

    regulated = rows["regulated_disclosure_documents"]
    assert regulated.sample_fixture_ids == (
        "professional_disclosure_manual_boundary",
        "professional_disclosure_regulated_assurance_boundary",
    )
    assert regulated.application_default_delivery_preset_id == "board_review_copy"

    form_batch = rows["form_batch_documents"]
    assert form_batch.sample_fixture_ids == (
        "batch_forms_fixed_layout",
        "batch_forms_fixed_layout_placeholder_manual_boundary",
    )
    assert "residue_check_report" in form_batch.delivery_preset_ids

    meeting = rows["meeting_policy_documents"]
    assert meeting.sample_fixture_ids == (
        "official_policy_fields_comments",
        "official_policy_formal_archive_manual_boundary",
        "official_policy_metadata_archive_report",
    )
    assert meeting.direct_request_cell_count == 3
    assert meeting.application_default_delivery_preset_id == "formal_minutes"

    long_doc = rows["long_document_publishing"]
    assert long_doc.sample_fixture_ids == (
        "technical_long_docs_skip_objects",
        "technical_long_docs_chapter_inventory_manual_boundary",
        "technical_long_docs_index_appendix_merge_boundary",
    )
    assert long_doc.direct_request_cell_count == 3
    assert long_doc.application_default_delivery_preset_id == "final_docx"

    qualification = rows["qualification_archive_packages"]
    assert qualification.sample_fixture_ids == (
        "bidding_materials_attachments",
        "bidding_materials_missing_attachment_degraded",
        "bidding_materials_original_copy_manual_boundary",
        "bidding_materials_consortium_seal_residue_degraded",
    )
    assert qualification.direct_request_cell_count == 4
    assert qualification.application_default_delivery_preset_id == (
        "attachment_package"
    )


def test_scene_family_subscene_export_script_writes_json(tmp_path):
    output_path = tmp_path / "family_subscene.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_family_subscene_audit.py",
            "--format",
            "json",
            "--family",
            "hr_batch_documents",
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
    assert payload["family_count"] == 1
    assert payload["rows"][0]["family_id"] == "hr_batch_documents"
    assert payload["rows"][0]["request_cell_count"] == 2


def test_scene_family_subscene_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_family_subscene_audit.py",
            "--format",
            "markdown",
            "--family",
            "ip_patent_documents",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Family Subscene Audit" in result.stdout
    assert "| Family | Status | Priority | Packs |" in result.stdout
    assert "ip_patent_documents" in result.stdout
    assert "professional_disclosure_review_gate" in result.stdout
    assert "professional_disclosure_manual_boundary" in result.stdout


def test_release_gate_includes_scene_family_subscene_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_family_subscene_audit"]["status"] == "passed"
    assert payload["counts"]["scene_family_subscene_family_count"] == 15
    assert payload["counts"]["scene_family_subscene_issue_count"] == 0
    assert payload["counts"]["scene_family_subscene_warning_count"] == 0
    assert payload["counts"]["scene_family_subscene_request_cell_count"] == 35
    assert payload["scene_family_subscene_audit"]["status"] == "passed"
