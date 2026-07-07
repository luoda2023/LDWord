import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_object_preflight_action_audit import (  # noqa: E402
    audit_scene_object_preflight_action_report,
    build_scene_object_preflight_action_audit_report,
)


def test_scene_object_preflight_action_audit_baseline_counts():
    report = build_scene_object_preflight_action_audit_report(project_root=ROOT)
    issues, warnings = audit_scene_object_preflight_action_report(report)

    assert report.status == "passed"
    assert issues == ()
    assert warnings == report.warnings
    assert report.target_count == 11
    assert report.ready_target_count == 11
    assert report.warning_target_count == 0
    assert report.high_risk_target_count == 5
    assert report.fixture_backed_target_count == 11
    assert report.blockable_target_count == 3
    assert report.skippable_target_count == 11
    assert report.manual_confirmation_target_count == 10
    assert report.family_count == 15
    assert report.ready_family_count == 14
    assert report.boundary_family_count == 1
    assert report.strict_family_count == 2
    assert report.family_with_fixture_count == 15
    assert report.issue_count == 0
    assert report.warning_count == 0
    assert report.missing_source_evidence_count == 0


def test_scene_object_preflight_targets_expose_actions_and_boundaries():
    report = build_scene_object_preflight_action_audit_report(project_root=ROOT)
    rows = {row.target_id: row for row in report.target_rows}

    macros = rows["macros"]
    assert macros.status == "ready"
    assert "block_report" in macros.action_behavior_ids
    assert "manual_confirmation" in macros.action_behavior_ids
    assert "import_ai_boundary_blocking_macro" in macros.fixture_ids
    assert len(macros.block_policy_family_ids) == 15

    fields = rows["fields"]
    assert fields.status == "ready"
    assert "preserve_layout" in fields.action_behavior_ids
    assert "toc" in fields.skip_module_ids
    assert fields.repair_route_id == "object_preflight"
    assert len(fields.fixture_ids) == 37
    assert "bidding_materials_consortium_seal_residue_degraded" in fields.fixture_ids
    assert "quick_formatting_preserve_fields_degraded" in fields.fixture_ids
    assert "quick_formatting_business_template_cleanup" in fields.fixture_ids
    assert "chinese_academic_rule_source_degraded" in fields.fixture_ids
    assert (
        "chinese_academic_school_rule_section_confirmation" in fields.fixture_ids
    )
    assert "english_journal_bibtex_csl_degraded" in fields.fixture_ids
    assert "english_journal_publisher_rule_manual_boundary" in fields.fixture_ids
    assert "exam_education_structured_multiversion" in fields.fixture_ids
    assert "contract_delivery_signature_fields_degraded" in fields.fixture_ids
    assert "batch_forms_hr_missing_fields_manual_boundary" in fields.fixture_ids
    assert "official_policy_formal_archive_manual_boundary" in fields.fixture_ids
    assert "official_policy_metadata_archive_report" in fields.fixture_ids
    assert (
        "technical_long_docs_chapter_inventory_manual_boundary"
        in fields.fixture_ids
    )
    assert "technical_long_docs_index_appendix_merge_boundary" in fields.fixture_ids
    assert "bidding_materials_missing_attachment_degraded" in fields.fixture_ids
    assert "bidding_materials_original_copy_manual_boundary" in fields.fixture_ids
    assert "application_reports_project_attachment_degraded" in fields.fixture_ids
    assert "application_reports_project_budget_manual_boundary" in fields.fixture_ids
    assert "application_reports_product_asset_degraded" in fields.fixture_ids
    assert "application_reports_product_version_manual_boundary" in fields.fixture_ids
    assert "professional_disclosure_source_quality_degraded" in fields.fixture_ids
    assert (
        "professional_disclosure_finance_table_mapping_boundary"
        in fields.fixture_ids
    )
    assert (
        "professional_disclosure_patent_claim_quality_boundary"
        in fields.fixture_ids
    )
    assert (
        "professional_disclosure_regulated_assurance_boundary"
        in fields.fixture_ids
    )
    assert "import_ai_boundary_conversion_confidence_degraded" in fields.fixture_ids
    assert "import_ai_boundary_latex_handoff_confidence" in fields.fixture_ids

    comments = rows["comments"]
    assert len(comments.fixture_ids) == 34
    assert "bidding_materials_consortium_seal_residue_degraded" in comments.fixture_ids
    assert "quick_formatting_business_template_cleanup" in comments.fixture_ids
    assert "chinese_academic_rule_source_degraded" in comments.fixture_ids
    assert (
        "chinese_academic_school_rule_section_confirmation" in comments.fixture_ids
    )
    assert "english_journal_bibtex_csl_degraded" in comments.fixture_ids
    assert "english_journal_publisher_rule_manual_boundary" in comments.fixture_ids
    assert "contract_delivery_signature_fields_degraded" in comments.fixture_ids
    assert "batch_forms_hr_missing_fields_manual_boundary" in comments.fixture_ids
    assert "official_policy_formal_archive_manual_boundary" in comments.fixture_ids
    assert "official_policy_metadata_archive_report" in comments.fixture_ids
    assert (
        "technical_long_docs_chapter_inventory_manual_boundary"
        in comments.fixture_ids
    )
    assert "technical_long_docs_index_appendix_merge_boundary" in comments.fixture_ids
    assert "bidding_materials_missing_attachment_degraded" in comments.fixture_ids
    assert "bidding_materials_original_copy_manual_boundary" in comments.fixture_ids
    assert "application_reports_project_attachment_degraded" in comments.fixture_ids
    assert "application_reports_project_budget_manual_boundary" in comments.fixture_ids
    assert "application_reports_product_asset_degraded" in comments.fixture_ids
    assert "application_reports_product_version_manual_boundary" in comments.fixture_ids
    assert "professional_disclosure_source_quality_degraded" in comments.fixture_ids
    assert (
        "professional_disclosure_finance_table_mapping_boundary"
        in comments.fixture_ids
    )
    assert (
        "professional_disclosure_patent_claim_quality_boundary"
        in comments.fixture_ids
    )
    assert (
        "professional_disclosure_bilingual_termbase_boundary"
        in comments.fixture_ids
    )
    assert (
        "professional_disclosure_regulated_assurance_boundary"
        in comments.fixture_ids
    )
    assert "import_ai_boundary_conversion_confidence_degraded" in comments.fixture_ids
    assert "import_ai_boundary_latex_handoff_confidence" in comments.fixture_ids

    content_controls = rows["content_controls"]
    assert len(content_controls.fixture_ids) == 6
    assert "batch_forms_hr_missing_fields_manual_boundary" in (
        content_controls.fixture_ids
    )
    assert "batch_forms_fixed_layout_placeholder_manual_boundary" in (
        content_controls.fixture_ids
    )

    textboxes = rows["textboxes"]
    assert len(textboxes.fixture_ids) == 6
    assert "batch_forms_fixed_layout_placeholder_manual_boundary" in (
        textboxes.fixture_ids
    )
    assert "professional_disclosure_bilingual_termbase_boundary" in (
        textboxes.fixture_ids
    )
    assert "import_ai_boundary_latex_handoff_confidence" in textboxes.fixture_ids

    hidden_text = rows["hidden_text"]
    assert len(hidden_text.fixture_ids) == 12
    assert "chinese_academic_rule_source_degraded" in hidden_text.fixture_ids
    assert (
        "chinese_academic_school_rule_section_confirmation"
        in hidden_text.fixture_ids
    )
    assert "contract_delivery_signature_fields_degraded" in hidden_text.fixture_ids
    assert "official_policy_formal_archive_manual_boundary" in hidden_text.fixture_ids
    assert "application_reports_project_attachment_degraded" in hidden_text.fixture_ids
    assert "application_reports_product_version_manual_boundary" in hidden_text.fixture_ids
    assert "import_ai_boundary_conversion_confidence_degraded" in hidden_text.fixture_ids
    assert (
        "professional_disclosure_regulated_assurance_boundary"
        in hidden_text.fixture_ids
    )

    tracked_changes = rows["tracked_changes"]
    assert len(tracked_changes.fixture_ids) == 6
    assert "english_journal_bibtex_csl_degraded" in tracked_changes.fixture_ids
    assert (
        "english_journal_publisher_rule_manual_boundary"
        in tracked_changes.fixture_ids
    )
    assert (
        "contract_delivery_signature_fields_degraded"
        in tracked_changes.fixture_ids
    )
    assert "professional_disclosure_bilingual_termbase_boundary" in (
        tracked_changes.fixture_ids
    )

    embedded_packages = rows["embedded_packages"]
    assert len(embedded_packages.fixture_ids) == 12
    assert "bidding_materials_attachments" in embedded_packages.fixture_ids
    assert "bidding_materials_missing_attachment_degraded" in (
        embedded_packages.fixture_ids
    )
    assert "bidding_materials_original_copy_manual_boundary" in (
        embedded_packages.fixture_ids
    )
    assert (
        "technical_long_docs_chapter_inventory_manual_boundary"
        in embedded_packages.fixture_ids
    )
    assert "technical_long_docs_index_appendix_merge_boundary" in (
        embedded_packages.fixture_ids
    )
    assert "application_reports_project_attachment_degraded" in (
        embedded_packages.fixture_ids
    )
    assert "application_reports_project_budget_manual_boundary" in (
        embedded_packages.fixture_ids
    )
    assert "application_reports_product_asset_degraded" in (
        embedded_packages.fixture_ids
    )
    assert "application_reports_product_version_manual_boundary" in (
        embedded_packages.fixture_ids
    )
    assert "import_ai_boundary_latex_handoff_confidence" in (
        embedded_packages.fixture_ids
    )

    visio = rows["visio_drawings"]
    assert visio.status == "ready"
    assert visio.warning_ids == ()
    assert visio.fixture_ids == ("technical_long_docs_skip_objects",)
    assert "skip_report" in visio.action_behavior_ids


def test_scene_object_preflight_family_rows_link_planning_to_runtime_policy():
    report = build_scene_object_preflight_action_audit_report(project_root=ROOT)
    rows = {row.family_id: row for row in report.family_rows}

    contract = rows["contract_delivery"]
    assert contract.status == "ready"
    assert contract.preservation_mode == "strict"
    assert "tracked_changes" in contract.recommended_scan_targets
    assert "tracked_changes" in contract.actual_scan_targets
    assert contract.fixture_ids == (
        "contract_delivery_revisions",
        "contract_delivery_signature_fields_degraded",
    )

    long_docs = rows["long_document_publishing"]
    assert long_docs.status == "ready"
    assert long_docs.preservation_mode == "strict"
    assert set(long_docs.block_on) == {"ole_objects", "embedded_workbooks", "macros"}

    finance = rows["finance_quote_documents"]
    assert finance.status == "ready"
    assert finance.warning_ids == ()
    assert finance.fixture_ids == (
        "professional_disclosure_source_quality_degraded",
        "professional_disclosure_finance_table_mapping_boundary",
    )

    patent = rows["ip_patent_documents"]
    assert patent.status == "boundary"
    assert patent.plugin_boundary_only is True


def test_scene_object_preflight_action_export_script_writes_json_and_markdown(tmp_path):
    output_path = tmp_path / "scene_object_preflight_action.json"

    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_object_preflight_action_audit.py",
            "--format",
            "json",
            "--target",
            "fields",
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
    assert payload["counts"]["target_count"] == 1
    assert payload["target_rows"][0]["target_id"] == "fields"

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_object_preflight_action_audit.py",
            "--format",
            "markdown",
            "--family",
            "contract_delivery",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene ObjectPreflight Action Audit" in markdown_result.stdout
    assert "| Family | Status | Mode | Recommended targets | Actual targets | Fixtures |" in markdown_result.stdout
    assert "contract_delivery" in markdown_result.stdout
    assert "tracked_changes" in markdown_result.stdout
