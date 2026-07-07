import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_user_journey_fixture_audit import (  # noqa: E402
    SCENE_USER_JOURNEY_PATH_TYPES,
    audit_scene_user_journey_fixture_report,
    build_scene_user_journey_fixture_audit_report,
)


def test_scene_user_journey_fixture_audit_baseline_counts():
    report = build_scene_user_journey_fixture_audit_report(project_root=ROOT)
    issues, warnings = audit_scene_user_journey_fixture_report(report)
    counts = report.to_payload()["counts"]

    assert report.status == "passed"
    assert issues == ()
    assert warnings == report.warnings
    assert report.pack_count == 12
    assert report.ready_pack_count == 12
    assert report.warning_pack_count == 0
    assert report.family_count == 15
    assert report.ready_family_count == 15
    assert report.warning_family_count == 0
    assert report.p1_family_count == 11
    assert report.p1_ready_family_count == 11
    assert report.path_count == 100
    assert counts["success_path_count"] == 31
    assert counts["degraded_path_count"] == 29
    assert counts["failure_path_count"] == 4
    assert counts["manual_boundary_path_count"] == 25
    assert counts["ambiguous_decision_path_count"] == 7
    assert counts["handoff_path_count"] == 1
    assert counts["negative_control_path_count"] == 3
    assert report.issue_count == 0
    assert report.warning_count == 0
    assert report.missing_source_evidence_count == 0
    assert tuple(report.to_payload()["path_types"]) == SCENE_USER_JOURNEY_PATH_TYPES


def test_scene_user_journey_paths_keep_high_frequency_boundaries_explicit():
    report = build_scene_user_journey_fixture_audit_report(project_root=ROOT)
    paths = {row.path_id: row for row in report.path_rows}
    packs = {row.pack_id: row for row in report.pack_rows}

    handoff = paths["handoff:import_pdf_thesis"]
    assert handoff.status == "ready"
    assert handoff.pack_ids == ("import_ai_boundary", "chinese_academic")
    assert handoff.family_ids == ("thesis_cn",)
    assert handoff.fixture_ids == ("import_ai_boundary_blocking_macro",)
    assert "import_ai_conversion_gate" in handoff.manual_gate_ids
    assert "block_report" in handoff.expected_behaviors

    degraded = paths["degraded:technical_product_manual"]
    assert degraded.pack_ids == ("technical_long_docs",)
    assert "skip_report" in degraded.expected_behaviors

    technical_manual = paths["manual_boundary:technical_product_manual"]
    assert technical_manual.pack_ids == ("technical_long_docs",)
    assert technical_manual.family_ids == ("long_document_publishing",)
    assert "technical_long_docs_index_appendix_merge_boundary" in (
        technical_manual.fixture_ids
    )
    assert "manual_confirmation" in technical_manual.expected_behaviors
    assert "index_appendix_inventory" in technical_manual.report_expectations
    assert "multi_file_merge_boundary_report" in technical_manual.report_expectations

    quick_degraded = paths["degraded:quick_template_cleanup"]
    assert quick_degraded.pack_ids == ("quick_formatting",)
    assert quick_degraded.fixture_ids == (
        "quick_formatting_fields_comments",
        "quick_formatting_preserve_fields_degraded",
    )
    assert "preserve_layout" in quick_degraded.expected_behaviors

    quick_business_cleanup = paths["degraded:quick_word_cleanup"]
    assert quick_business_cleanup.pack_ids == ("quick_formatting",)
    assert quick_business_cleanup.fixture_ids == (
        "quick_formatting_fields_comments",
        "quick_formatting_business_template_cleanup",
    )
    assert "template_field_repair" in quick_business_cleanup.report_expectations

    resume_cleanup = paths["degraded:personal_resume_formatting"]
    assert resume_cleanup.pack_ids == ("quick_formatting",)
    assert resume_cleanup.fixture_ids == (
        "quick_formatting_fields_comments",
        "quick_formatting_business_template_cleanup",
    )
    assert "preserve_layout" in resume_cleanup.expected_behaviors

    preserve_layout = paths["degraded:batch_hr_offer"]
    assert preserve_layout.pack_ids == ("batch_forms",)
    assert "preserve_layout" in preserve_layout.expected_behaviors

    hr_manual = paths["manual_boundary:batch_employee_certificate"]
    assert hr_manual.pack_ids == ("batch_forms",)
    assert hr_manual.family_ids == ("hr_batch_documents",)
    assert "manual_confirmation" in hr_manual.expected_behaviors
    assert "batch_failure_isolation" in hr_manual.report_expectations
    assert hr_manual.manual_gate_ids == ()

    form_manual = paths["manual_boundary:batch_certificate_printing"]
    assert form_manual.pack_ids == ("batch_forms",)
    assert form_manual.family_ids == ("form_batch_documents",)
    assert "manual_confirmation" in form_manual.expected_behaviors
    assert "placeholder_residue_report" in form_manual.report_expectations
    assert form_manual.manual_gate_ids == ()

    exam_degraded = paths["degraded:exam_multi_version"]
    assert exam_degraded.pack_ids == ("exam_education",)
    assert exam_degraded.fixture_ids == ("exam_education_controls_textboxes",)
    assert "skip_report" in exam_degraded.expected_behaviors
    assert "exam_ai_complex_diagram_gate" in exam_degraded.manual_gate_ids

    exam_success = paths["success:exam_answer_sheet"]
    assert exam_success.fixture_ids == ("exam_education_structured_multiversion",)
    assert exam_success.manual_gate_ids == ()

    thesis_degraded = paths["degraded:chinese_thesis_count"]
    assert thesis_degraded.pack_ids == ("chinese_academic",)
    assert thesis_degraded.family_ids == ("thesis_cn",)
    assert thesis_degraded.fixture_ids == (
        "chinese_academic_hidden_formula",
        "chinese_academic_rule_source_degraded",
        "chinese_academic_school_rule_section_confirmation",
    )
    assert "rule_source_governance" in thesis_degraded.report_expectations
    assert "skip_report" in thesis_degraded.expected_behaviors
    assert "section_classifier_confirmation" in (
        thesis_degraded.report_expectations
    )

    thesis_manual = paths["manual_boundary:chinese_thesis_count"]
    assert thesis_manual.pack_ids == ("chinese_academic",)
    assert thesis_manual.family_ids == ("thesis_cn",)
    assert "chinese_academic_school_rule_section_confirmation" in (
        thesis_manual.fixture_ids
    )
    assert "manual_confirmation" in thesis_manual.expected_behaviors
    assert "school_rule_source_selection" in thesis_manual.report_expectations
    assert "section_classifier_confirmation" in thesis_manual.report_expectations

    journal_degraded = paths["degraded:english_journal_submission_package"]
    assert journal_degraded.pack_ids == ("english_journal",)
    assert journal_degraded.family_ids == ("journal_en",)
    assert journal_degraded.fixture_ids == (
        "english_journal_revision_comments",
        "english_journal_bibtex_csl_degraded",
    )
    assert "citation_source_report" in journal_degraded.report_expectations
    assert "skip_report" in journal_degraded.expected_behaviors

    journal_manual = paths["manual_boundary:english_journal_response_letter"]
    assert journal_manual.fixture_ids == (
        "english_journal_revision_comments",
        "english_journal_publisher_rule_manual_boundary",
    )
    assert journal_manual.manual_gate_ids == ("journal_publisher_rule_review_gate",)
    assert "manual_confirmation" in journal_manual.expected_behaviors

    negative = paths["negative_control:negative_ppt_poster_design"]
    assert negative.status == "ready"
    assert negative.fixture_ids == ()
    assert negative.journey_type == "negative_control"

    ambiguous = paths["ambiguous_decision:ambiguous_quote_plan"]
    assert ambiguous.status == "ready"
    assert "ambiguous_fixture_set" in ambiguous.coverage_levels
    assert "professional_disclosure_review_gate" in ambiguous.manual_gate_ids

    import_pack = packs["import_ai_boundary"]
    assert import_pack.path_type_ids == (
        "degraded",
        "failure",
        "manual_boundary",
        "handoff",
    )
    assert import_pack.warning_ids == ()

    quick_pack = packs["quick_formatting"]
    assert quick_pack.path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert quick_pack.warning_ids == ()

    exam_pack = packs["exam_education"]
    assert exam_pack.path_type_ids == ("success", "degraded", "manual_boundary")
    assert exam_pack.warning_ids == ()

    thesis_pack = packs["chinese_academic"]
    assert thesis_pack.path_type_ids == (
        "success",
        "degraded",
        "failure",
        "manual_boundary",
        "handoff",
    )
    assert thesis_pack.warning_ids == ()

    journal_pack = packs["english_journal"]
    assert journal_pack.path_type_ids == ("success", "degraded", "manual_boundary")
    assert journal_pack.warning_ids == ()

    contract_degraded = paths["degraded:contract_signing_consistency"]
    assert contract_degraded.pack_ids == ("contract_delivery",)
    assert contract_degraded.fixture_ids == (
        "contract_delivery_revisions",
        "contract_delivery_signature_fields_degraded",
    )
    assert "contract_field_consistency_report" in (
        contract_degraded.report_expectations
    )
    assert "skip_report" in contract_degraded.expected_behaviors

    contract_manual = paths["manual_boundary:ambiguous_contract_legal_review"]
    assert contract_manual.pack_ids == (
        "contract_delivery",
        "professional_disclosure",
    )
    assert contract_manual.family_ids == ("contract_delivery",)
    assert contract_manual.manual_gate_ids == (
        "professional_disclosure_review_gate",
    )
    assert "manual_confirmation" in contract_manual.expected_behaviors

    contract_pack = packs["contract_delivery"]
    assert contract_pack.path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert contract_pack.warning_ids == ()

    batch_pack = packs["batch_forms"]
    assert batch_pack.path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert batch_pack.warning_ids == ()

    official_degraded = paths["degraded:official_notice_formal_archive"]
    assert official_degraded.pack_ids == ("official_policy",)
    assert official_degraded.family_ids == ("meeting_policy_documents",)
    assert official_degraded.fixture_ids == (
        "official_policy_fields_comments",
        "official_policy_formal_archive_manual_boundary",
    )
    assert official_degraded.manual_gate_ids == ()
    assert "preserve_layout" in official_degraded.expected_behaviors
    assert "watermark_status_report" in official_degraded.report_expectations

    official_manual = paths["manual_boundary:official_notice_formal_archive"]
    assert official_manual.pack_ids == ("official_policy",)
    assert official_manual.family_ids == ("meeting_policy_documents",)
    assert official_manual.fixture_ids == (
        "official_policy_fields_comments",
        "official_policy_formal_archive_manual_boundary",
    )
    assert official_manual.manual_gate_ids == ()
    assert "manual_confirmation" in official_manual.expected_behaviors
    assert "official_delivery_status_report" in official_manual.report_expectations

    official_pack = packs["official_policy"]
    assert official_pack.path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert official_pack.warning_ids == ()

    long_doc_manual = paths["manual_boundary:technical_sop_chapter_inventory"]
    assert long_doc_manual.pack_ids == ("technical_long_docs",)
    assert long_doc_manual.family_ids == ("long_document_publishing",)
    assert long_doc_manual.fixture_ids == (
        "technical_long_docs_skip_objects",
        "technical_long_docs_chapter_inventory_manual_boundary",
    )
    assert long_doc_manual.manual_gate_ids == ()
    assert "manual_confirmation" in long_doc_manual.expected_behaviors
    assert "chapter_inventory" in long_doc_manual.report_expectations
    assert "cross_reference_status_report" in long_doc_manual.report_expectations

    technical_pack = packs["technical_long_docs"]
    assert technical_pack.path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert technical_pack.warning_ids == ()

    bidding_degraded = paths["degraded:bidding_license_archive"]
    assert bidding_degraded.pack_ids == ("bidding_materials",)
    assert bidding_degraded.family_ids == ("qualification_archive_packages",)
    assert bidding_degraded.fixture_ids == (
        "bidding_materials_attachments",
        "bidding_materials_missing_attachment_degraded",
    )
    assert "skip_report" in bidding_degraded.expected_behaviors
    assert "missing_items_report" in bidding_degraded.report_expectations

    bidding_consortium = paths["degraded:bidding_consortium_seal_archive"]
    assert bidding_consortium.pack_ids == ("bidding_materials",)
    assert bidding_consortium.family_ids == ("qualification_archive_packages",)
    assert bidding_consortium.fixture_ids == (
        "bidding_materials_attachments",
        "bidding_materials_consortium_seal_residue_degraded",
    )
    assert "expiry_metadata_report" in bidding_consortium.report_expectations
    assert "consortium_archive_manifest" in bidding_consortium.report_expectations
    assert "seal_position_residue_report" in bidding_consortium.report_expectations

    bidding_consortium_manual = paths[
        "manual_boundary:bidding_consortium_seal_archive"
    ]
    assert "manual_confirmation" in bidding_consortium_manual.expected_behaviors
    assert "qualification-validity judgment" in (
        " ".join(bidding_consortium_manual.boundary_notes)
    )

    bidding_manual = paths["manual_boundary:bidding_original_copy"]
    assert bidding_manual.pack_ids == ("bidding_materials",)
    assert bidding_manual.family_ids == ("qualification_archive_packages",)
    assert bidding_manual.fixture_ids == (
        "bidding_materials_attachments",
        "bidding_materials_original_copy_manual_boundary",
    )
    assert bidding_manual.manual_gate_ids == ()
    assert "manual_confirmation" in bidding_manual.expected_behaviors
    assert "qualification_authenticity_boundary_report" in (
        bidding_manual.report_expectations
    )

    bidding_pack = packs["bidding_materials"]
    assert bidding_pack.path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert bidding_pack.warning_ids == ()

    project_degraded = paths["degraded:application_project_limits"]
    assert project_degraded.family_ids == ("project_application",)
    assert "application_reports_project_attachment_degraded" in (
        project_degraded.fixture_ids
    )
    assert "missing_items_report" in project_degraded.report_expectations

    project_manual = paths["manual_boundary:application_review_budget"]
    assert project_manual.family_ids == ("project_application",)
    assert "application_reports_project_budget_manual_boundary" in (
        project_manual.fixture_ids
    )
    assert "budget_attachment_report" in project_manual.report_expectations

    product_degraded = paths["degraded:application_customer_product_manual"]
    assert product_degraded.family_ids == ("product_sales_documents",)
    assert "application_reports_product_asset_degraded" in (
        product_degraded.fixture_ids
    )
    assert "product_asset_inventory" in product_degraded.report_expectations

    product_manual = paths["manual_boundary:application_presales_plan"]
    assert product_manual.family_ids == ("product_sales_documents",)
    assert "application_reports_product_version_manual_boundary" in (
        product_manual.fixture_ids
    )
    assert "customer_internal_version_report" in product_manual.report_expectations

    professional_degraded = paths["degraded:professional_finance_quote"]
    assert professional_degraded.pack_ids == ("professional_disclosure",)
    assert "professional_disclosure_source_quality_degraded" in (
        professional_degraded.fixture_ids
    )
    assert "professional_source_quality_report" in (
        professional_degraded.report_expectations
    )

    import_degraded = paths["degraded:import_ocr_pdf"]
    assert import_degraded.pack_ids == ("import_ai_boundary",)
    assert "import_ai_boundary_conversion_confidence_degraded" in (
        import_degraded.fixture_ids
    )
    assert "conversion_confidence_report" in import_degraded.report_expectations


def test_scene_user_journey_export_script_writes_json_and_markdown(tmp_path):
    output_path = tmp_path / "scene_user_journey_fixture.json"

    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_user_journey_fixture_audit.py",
            "--format",
            "json",
            "--journey-type",
            "handoff",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert json_result.stdout == ""
    assert payload["status"] == "passed"
    assert payload["counts"]["path_count"] == 1
    assert payload["path_rows"][0]["path_id"] == "handoff:import_pdf_thesis"

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_user_journey_fixture_audit.py",
            "--format",
            "markdown",
            "--pack",
            "technical_long_docs",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene User Journey Fixture Audit" in markdown_result.stdout
    assert "| Path | Type | Status | Packs | Families | Cells | Fixtures | Sources |" in (
        markdown_result.stdout
    )
    assert "technical_long_docs" in markdown_result.stdout
    assert "degraded:technical_product_manual" in markdown_result.stdout


def test_release_gate_includes_scene_user_journey_fixture_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_user_journey_fixture_audit"]["status"] == (
        "passed"
    )
    assert payload["counts"]["scene_user_journey_pack_count"] == 12
    assert payload["counts"]["scene_user_journey_ready_pack_count"] == 12
    assert payload["counts"]["scene_user_journey_warning_pack_count"] == 0
    assert payload["counts"]["scene_user_journey_path_count"] == 100
    assert payload["counts"]["scene_user_journey_handoff_path_count"] == 1
    assert payload["counts"]["scene_user_journey_issue_count"] == 0
    assert payload["counts"]["scene_user_journey_warning_count"] == 0
    assert (
        payload["counts"]["scene_user_journey_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_user_journey_fixture_audit"]["status"] == "passed"
