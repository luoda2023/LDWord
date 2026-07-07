import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_high_frequency_completeness_audit import (  # noqa: E402
    REQUEST_CELL_REPORT_ARTIFACT_NAME,
    audit_high_frequency_completeness_report,
    build_high_frequency_completeness_audit_report,
)
from src.config.scene_request_cell_fixture_registry import (  # noqa: E402
    build_scene_request_cell_fixture_summary,
)
from src.config.scene_sample_fixture_registry import (  # noqa: E402
    list_scene_sample_fixtures,
)


def test_high_frequency_completeness_audit_aggregates_v27_evidence():
    report = build_high_frequency_completeness_audit_report()
    payload = report.to_payload()
    rows = {row.pack_id: row for row in report.rows}
    request_summary = build_scene_request_cell_fixture_summary()

    assert report.status == "passed"
    assert report.warning_count == 0
    assert audit_high_frequency_completeness_report(report) == ()
    assert report.pack_count == 12
    assert report.ready_pack_count == 12
    assert payload["ready_pack_count"] == 12
    assert payload["counts"]["request_cell_count"] == request_summary.cell_count
    assert payload["counts"]["report_anchor_count"] == request_summary.cell_count
    assert payload["counts"]["unassigned_request_cell_count"] == 3
    assert payload["counts"]["request_cell_pack_link_count"] == 57
    assert payload["counts"]["report_anchor_pack_link_count"] == 57
    assert payload["counts"]["sample_fixture_count"] == len(list_scene_sample_fixtures())
    assert payload["counts"]["plugin_boundary_pack_count"] == 4
    assert payload["low_matched_request_pack_ids"] == []

    for row in report.rows:
        assert row.capability_axis_ids
        assert row.workflow_archetype_ids
        assert row.word_risk_surface_ids
        assert row.completeness_gate_ids
        assert row.request_cell_count > 0
        assert row.sample_fixture_count > 0
        assert row.request_cell_report_artifact_name == (
            REQUEST_CELL_REPORT_ARTIFACT_NAME
        )
        assert row.request_cell_report_anchor_count == row.request_cell_count
        assert not row.issue_ids
        assert row.status in {"ready", "needs_depth"}

    assert rows["batch_forms"].sample_fixture_count == 4
    assert "fixed_row_height" in rows["batch_forms"].word_risk_surface_ids
    assert "fixed_row_height" in rows["batch_forms"].docx_surfaces
    assert "fixed_layout_row_height" in rows["batch_forms"].report_expectations
    assert "manual_confirmation" in rows["batch_forms"].expected_behaviors
    assert "batch_failure_isolation" in rows["batch_forms"].report_expectations

    thesis = rows["chinese_academic"]
    assert thesis.sample_fixture_count == 3
    assert thesis.sample_fixture_ids == (
        "chinese_academic_hidden_formula",
        "chinese_academic_rule_source_degraded",
        "chinese_academic_school_rule_section_confirmation",
    )
    assert "manual_confirmation" in thesis.expected_behaviors
    assert "school_rule_source_selection" in thesis.report_expectations
    assert "section_classifier_confirmation" in thesis.report_expectations

    journal = rows["english_journal"]
    assert journal.sample_fixture_count == 3
    assert journal.sample_fixture_ids == (
        "english_journal_revision_comments",
        "english_journal_bibtex_csl_degraded",
        "english_journal_publisher_rule_manual_boundary",
    )
    assert journal.sample_manual_gate_ids == ("journal_publisher_rule_review_gate",)

    contract = rows["contract_delivery"]
    assert contract.request_cell_count == 4
    assert contract.matched_request_cell_count == 3
    assert contract.ambiguous_request_cell_count == 1
    assert contract.request_cell_manual_gate_ids == (
        "professional_disclosure_review_gate",
    )
    assert contract.sample_fixture_ids == (
        "contract_delivery_revisions",
        "contract_delivery_signature_fields_degraded",
    )
    assert contract.request_cell_report_anchor_sample_ids == (
        "contract_signing_consistency",
        "contract_review_revisions",
        "contract_signature_package_fields",
        "ambiguous_contract_legal_review",
    )

    official = rows["official_policy"]
    assert official.sample_fixture_count == 3
    assert official.sample_fixture_ids == (
        "official_policy_fields_comments",
        "official_policy_formal_archive_manual_boundary",
        "official_policy_metadata_archive_report",
    )
    assert "manual_confirmation" in official.expected_behaviors
    assert "official_metadata_report" in official.report_expectations
    assert "formal_internal_archive_manifest" in official.report_expectations
    assert "official_delivery_status_report" in official.report_expectations
    assert "watermark_status_report" in official.report_expectations

    technical = rows["technical_long_docs"]
    assert technical.sample_fixture_count == 3
    assert technical.sample_fixture_ids == (
        "technical_long_docs_skip_objects",
        "technical_long_docs_chapter_inventory_manual_boundary",
        "technical_long_docs_index_appendix_merge_boundary",
    )
    assert "manual_confirmation" in technical.expected_behaviors
    assert "chapter_inventory" in technical.report_expectations
    assert "index_appendix_inventory" in technical.report_expectations
    assert "multi_file_merge_boundary_report" in technical.report_expectations
    assert "cross_reference_status_report" in technical.report_expectations

    bidding = rows["bidding_materials"]
    assert bidding.sample_fixture_count == 4
    assert bidding.sample_fixture_ids == (
        "bidding_materials_attachments",
        "bidding_materials_missing_attachment_degraded",
        "bidding_materials_original_copy_manual_boundary",
        "bidding_materials_consortium_seal_residue_degraded",
    )
    assert "skip_report" in bidding.expected_behaviors
    assert "manual_confirmation" in bidding.expected_behaviors
    assert "missing_items_report" in bidding.report_expectations
    assert "expiry_metadata_report" in bidding.report_expectations
    assert "consortium_archive_manifest" in bidding.report_expectations
    assert "seal_position_residue_report" in bidding.report_expectations
    assert "qualification_authenticity_boundary_report" in (
        bidding.report_expectations
    )

    application = rows["application_reports"]
    assert application.sample_fixture_count == 6
    assert application.sample_fixture_ids == (
        "application_reports_hidden_comments",
        "application_reports_project_attachment_degraded",
        "application_reports_project_budget_manual_boundary",
        "application_reports_product_sales_assets",
        "application_reports_product_asset_degraded",
        "application_reports_product_version_manual_boundary",
    )
    assert "skip_report" in application.expected_behaviors
    assert "manual_confirmation" in application.expected_behaviors
    assert "budget_attachment_report" in application.report_expectations
    assert "customer_internal_version_report" in application.report_expectations

    professional = rows["professional_disclosure"]
    assert professional.sample_fixture_count == 6
    assert professional.sample_fixture_ids == (
        "professional_disclosure_manual_boundary",
        "professional_disclosure_source_quality_degraded",
        "professional_disclosure_finance_table_mapping_boundary",
        "professional_disclosure_patent_claim_quality_boundary",
        "professional_disclosure_bilingual_termbase_boundary",
        "professional_disclosure_regulated_assurance_boundary",
    )
    assert "skip_report" in professional.expected_behaviors
    assert "professional_source_quality_report" in professional.report_expectations
    assert "professional_boundary_matrix" in professional.report_expectations

    import_boundary = rows["import_ai_boundary"]
    assert import_boundary.sample_fixture_count == 3
    assert import_boundary.sample_fixture_ids == (
        "import_ai_boundary_blocking_macro",
        "import_ai_boundary_conversion_confidence_degraded",
        "import_ai_boundary_latex_handoff_confidence",
    )
    assert "skip_report" in import_boundary.expected_behaviors
    assert "conversion_confidence_report" in import_boundary.report_expectations
    assert "confidence_artifact_manifest" in import_boundary.report_expectations


def test_high_frequency_completeness_audit_filters_one_pack():
    report = build_high_frequency_completeness_audit_report(
        pack_id="professional_disclosure"
    )
    row = report.rows[0]

    assert report.pack_count == 1
    assert row.pack_id == "professional_disclosure"
    assert row.plugin_boundary is True
    assert row.manual_boundary_request_cell_count == 6
    assert row.sample_fixture_count == 6
    assert row.sample_manual_gate_ids == ("professional_disclosure_review_gate",)
    assert "plugin_manual_gate" in row.workflow_archetype_ids
    assert report.to_payload()["counts"]["report_anchor_count"] == 9


def test_scene_high_frequency_completeness_export_script_writes_json(tmp_path):
    output_path = tmp_path / "batch_forms_completeness.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_high_frequency_completeness.py",
            "--format",
            "json",
            "--pack",
            "batch_forms",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.stdout == ""
    assert payload["pack_count"] == 1
    assert payload["status"] == "passed"
    assert payload["rows"][0]["pack_id"] == "batch_forms"
    assert payload["rows"][0]["sample_fixture_count"] == 4
    assert payload["rows"][0]["request_cell_report_artifact_name"] == (
        REQUEST_CELL_REPORT_ARTIFACT_NAME
    )


def test_scene_high_frequency_completeness_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_high_frequency_completeness.py",
            "--format",
            "markdown",
            "--pack",
            "contract_delivery",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene High-Frequency Completeness Audit" in result.stdout
    assert "| Pack | Status | Cells | Matched | Fixtures | Report |" in (
        result.stdout
    )
    assert "contract_delivery" in result.stdout
    assert "request_cell_report.md (4)" in result.stdout
    assert "low_matched_request_cell_depth" not in result.stdout
