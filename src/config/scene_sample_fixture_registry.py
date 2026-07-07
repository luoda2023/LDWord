"""Minimal DOCX sample fixture registry for high-frequency scene packs.

The registry is metadata-only: tests use these specs to generate real temporary
DOCX packages and verify that required Word/OOXML surfaces are detectable,
preserved, blocked, skipped, or routed to manual/plugin confirmation.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.config.plugin_manual_gate import plugin_manual_gate_for_pack
from src.config.scene_coverage_manifest import SCENE_COVERAGE_PACK_MAP


SUPPORTED_SAMPLE_SURFACES: tuple[str, ...] = (
    "paragraph_run",
    "table_grid",
    "fixed_row_height",
    "drawing_media_rels",
    "headers_footers",
    "package_relationships",
    "fields",
    "comments",
    "tracked_changes",
    "hidden_text",
    "textboxes",
    "content_controls",
    "ole_objects",
    "embedded_workbooks",
    "embedded_packages",
    "visio_drawings",
    "macros",
)
REQUIRED_SAMPLE_SURFACES: tuple[str, ...] = (
    "content_controls",
    "textboxes",
    "fields",
    "tracked_changes",
    "comments",
    "ole_objects",
    "macros",
    "hidden_text",
    "fixed_row_height",
)
SUPPORTED_SAMPLE_BEHAVIORS: tuple[str, ...] = (
    "detect",
    "skip_report",
    "block_report",
    "preserve_layout",
    "manual_confirmation",
)
REQUIRED_SAMPLE_PACK_IDS: tuple[str, ...] = tuple(SCENE_COVERAGE_PACK_MAP)


@dataclass(frozen=True, slots=True)
class SceneSampleFixtureSpec:
    """One minimum DOCX sample expected for a coverage pack."""

    fixture_id: str
    pack_id: str
    label: str
    family_id: str = ""
    docx_surfaces: tuple[str, ...] = ()
    expected_preflight_findings: tuple[str, ...] = ()
    expected_behaviors: tuple[str, ...] = ("detect",)
    report_expectations: tuple[str, ...] = ()
    manual_gate_id: str = ""
    boundary_notes: tuple[str, ...] = ()
    request_sample_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "pack_id": self.pack_id,
            "label": self.label,
            "family_id": self.family_id,
            "docx_surfaces": list(self.docx_surfaces),
            "expected_preflight_findings": list(self.expected_preflight_findings),
            "expected_behaviors": list(self.expected_behaviors),
            "report_expectations": list(self.report_expectations),
            "manual_gate_id": self.manual_gate_id,
            "boundary_notes": list(self.boundary_notes),
            "request_sample_ids": list(self.request_sample_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneSampleFixtureAuditIssue:
    fixture_id: str
    kind: str
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class SceneSampleCoverageSummary:
    """Aggregated DOCX sample coverage for one or more scene packs."""

    pack_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    docx_surfaces: tuple[str, ...]
    expected_behaviors: tuple[str, ...]
    manual_gate_ids: tuple[str, ...]
    boundary_notes: tuple[str, ...]
    missing_pack_ids: tuple[str, ...]
    audit_issues: tuple[SceneSampleFixtureAuditIssue, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not (self.missing_pack_ids or self.audit_issues)


SCENE_SAMPLE_FIXTURES: tuple[SceneSampleFixtureSpec, ...] = (
    SceneSampleFixtureSpec(
        fixture_id="quick_formatting_fields_comments",
        pack_id="quick_formatting",
        label="Quick formatting fields and comments sample",
        docx_surfaces=("paragraph_run", "fields", "comments"),
        expected_preflight_findings=("fields", "comments"),
        report_expectations=("object_preflight",),
        boundary_notes=("General formatting must preserve field/comment awareness.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="quick_formatting_preserve_fields_degraded",
        pack_id="quick_formatting",
        label="Quick formatting preserve field/comment degraded sample",
        docx_surfaces=("paragraph_run", "fields", "comments"),
        expected_preflight_findings=("fields", "comments"),
        expected_behaviors=("detect", "preserve_layout"),
        report_expectations=("object_preflight", "coverage_boundaries"),
        boundary_notes=(
            "Quick cleanup should preserve field/comment layout and warn instead of "
            "rewriting risky Word objects.",
        ),
        request_sample_ids=("quick_template_cleanup",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="quick_formatting_business_template_cleanup",
        pack_id="quick_formatting",
        label="Quick formatting real business template cleanup sample",
        docx_surfaces=("paragraph_run", "table_grid", "fields", "comments"),
        expected_preflight_findings=("fields", "comments"),
        expected_behaviors=("detect", "preserve_layout"),
        report_expectations=(
            "template_field_repair",
            "object_preflight",
            "formatting_report",
        ),
        boundary_notes=(
            "Business templates can be cleaned through template field repair "
            "without making professional or content-quality promises.",
        ),
        request_sample_ids=("quick_word_cleanup", "personal_resume_formatting"),
    ),
    SceneSampleFixtureSpec(
        fixture_id="chinese_academic_hidden_formula",
        pack_id="chinese_academic",
        label="Chinese academic hidden text and field sample",
        family_id="thesis_cn",
        docx_surfaces=("paragraph_run", "fields", "hidden_text"),
        expected_preflight_findings=("fields", "hidden_text"),
        report_expectations=("count_report", "object_preflight"),
        boundary_notes=("School-specific rules still require reviewed rule source data.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="chinese_academic_rule_source_degraded",
        pack_id="chinese_academic",
        label="Chinese academic rule-source degraded count sample",
        family_id="thesis_cn",
        docx_surfaces=("paragraph_run", "fields", "comments", "hidden_text"),
        expected_preflight_findings=("fields", "comments", "hidden_text"),
        expected_behaviors=("detect", "skip_report"),
        report_expectations=(
            "count_report",
            "coverage_boundaries",
            "object_preflight",
            "rule_source_governance",
        ),
        boundary_notes=(
            "Unreviewed school rules or low-confidence formula/citation handling "
            "should downgrade to a boundary report.",
        ),
        request_sample_ids=("chinese_thesis_count",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="chinese_academic_school_rule_section_confirmation",
        pack_id="chinese_academic",
        label="Chinese academic school rule and section confirmation sample",
        family_id="thesis_cn",
        docx_surfaces=("paragraph_run", "fields", "comments", "hidden_text"),
        expected_preflight_findings=("fields", "comments", "hidden_text"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "count_report",
            "rule_source_governance",
            "school_rule_source_selection",
            "section_classifier_confirmation",
            "object_preflight",
        ),
        boundary_notes=(
            "School-rule source selection and section classifier decisions must "
            "be confirmed before strict school compliance is claimed.",
        ),
        request_sample_ids=("chinese_thesis_count",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="english_journal_revision_comments",
        pack_id="english_journal",
        label="English journal revision/comment sample",
        family_id="journal_en",
        docx_surfaces=("paragraph_run", "fields", "comments", "tracked_changes"),
        expected_preflight_findings=("fields", "comments", "tracked_changes"),
        report_expectations=(
            "journal_rule_source_governance",
            "reviewed_journal_profile_update",
            "submission_artifact_manifest",
            "object_preflight",
        ),
        boundary_notes=("Generic journal rules do not equal target-publisher rules.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="english_journal_bibtex_csl_degraded",
        pack_id="english_journal",
        label="English journal BibTeX/CSL degraded sample",
        family_id="journal_en",
        docx_surfaces=("paragraph_run", "fields", "comments", "tracked_changes"),
        expected_preflight_findings=("fields", "comments", "tracked_changes"),
        expected_behaviors=("detect", "skip_report"),
        report_expectations=(
            "coverage_boundaries",
            "journal_rule_source_governance",
            "citation_source_report",
            "journal_submission_package",
            "reviewed_journal_profile_update",
            "submission_artifact_manifest",
            "object_preflight",
        ),
        boundary_notes=(
            "Incomplete BibTeX/CSL or unresolved citation keys should downgrade "
            "to a citation-source boundary report.",
        ),
        request_sample_ids=("english_journal_submission_package",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="english_journal_publisher_rule_manual_boundary",
        pack_id="english_journal",
        label="English journal publisher-rule manual boundary sample",
        family_id="journal_en",
        docx_surfaces=("paragraph_run", "fields", "comments", "tracked_changes"),
        expected_preflight_findings=("fields", "comments", "tracked_changes"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "journal_rule_source_governance",
            "reviewed_journal_profile_update",
            "submission_artifact_manifest",
            "plugin_manual_gate",
            "object_preflight",
        ),
        manual_gate_id="journal_publisher_rule_review_gate",
        boundary_notes=(
            "Publisher-final layout and unreviewed target-journal rules require "
            "manual/plugin confirmation.",
        ),
        request_sample_ids=("english_journal_response_letter",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="exam_education_controls_textboxes",
        pack_id="exam_education",
        label="Exam content-control and textbox sample",
        family_id="exam_teaching",
        docx_surfaces=("paragraph_run", "content_controls", "textboxes", "fields"),
        expected_preflight_findings=("content_controls", "textboxes", "fields"),
        expected_behaviors=("detect", "skip_report", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "object_preflight",
            "object_preflight.module_skips",
            "plugin_manual_gate",
        ),
        manual_gate_id="exam_ai_complex_diagram_gate",
        boundary_notes=("AI quality and complex diagrams stay behind manual/plugin review.",),
        request_sample_ids=("exam_multi_version",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="exam_education_structured_multiversion",
        pack_id="exam_education",
        label="Exam structured source multi-version sample",
        family_id="exam_teaching",
        docx_surfaces=("paragraph_run", "table_grid", "content_controls", "fields"),
        expected_preflight_findings=("content_controls", "fields"),
        report_expectations=(
            "structured_intermediate",
            "content_visibility",
            "delivery_preset",
            "object_preflight",
        ),
        boundary_notes=(
            "Student, teacher, answer, and analysis outputs share one structured source.",
        ),
        request_sample_ids=("exam_answer_sheet", "exam_answer_analysis"),
    ),
    SceneSampleFixtureSpec(
        fixture_id="bidding_materials_attachments",
        pack_id="bidding_materials",
        label="Bidding attachment and embedded package sample",
        family_id="qualification_archive_packages",
        docx_surfaces=("paragraph_run", "fields", "embedded_packages", "ole_objects"),
        expected_preflight_findings=("fields", "embedded_packages", "ole_objects"),
        report_expectations=("material_package", "object_preflight"),
        boundary_notes=("Bid strategy and certificate truthfulness remain outside core.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="bidding_materials_missing_attachment_degraded",
        pack_id="bidding_materials",
        label="Bidding missing certificate/license attachment degraded sample",
        family_id="qualification_archive_packages",
        docx_surfaces=("paragraph_run", "fields", "comments", "embedded_packages"),
        expected_preflight_findings=("fields", "comments", "embedded_packages"),
        expected_behaviors=("detect", "skip_report"),
        report_expectations=(
            "material_package",
            "attachment_inventory",
            "missing_items_report",
            "archive_manifest",
            "object_preflight",
        ),
        boundary_notes=(
            "Missing certificate, license, or required archive assets should "
            "downgrade to an attachment inventory and missing-items report.",
        ),
        request_sample_ids=("bidding_license_archive",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="bidding_materials_original_copy_manual_boundary",
        pack_id="bidding_materials",
        label="Bidding original/copy archive authenticity manual-boundary sample",
        family_id="qualification_archive_packages",
        docx_surfaces=(
            "paragraph_run",
            "fields",
            "comments",
            "embedded_packages",
            "ole_objects",
        ),
        expected_preflight_findings=(
            "fields",
            "comments",
            "embedded_packages",
            "ole_objects",
        ),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "material_package",
            "attachment_inventory",
            "archive_manifest",
            "qualification_authenticity_boundary_report",
            "object_preflight",
        ),
        boundary_notes=(
            "Certificate authenticity, qualification validity, seal/original-copy "
            "state, and expired metadata require manual confirmation before "
            "archive delivery.",
        ),
        request_sample_ids=("bidding_original_copy",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="bidding_materials_consortium_seal_residue_degraded",
        pack_id="bidding_materials",
        label="Bidding consortium archive and seal-position residue degraded sample",
        family_id="qualification_archive_packages",
        docx_surfaces=(
            "paragraph_run",
            "table_grid",
            "fields",
            "comments",
            "drawing_media_rels",
            "headers_footers",
            "package_relationships",
        ),
        expected_preflight_findings=("fields", "comments"),
        expected_behaviors=("detect", "skip_report", "manual_confirmation"),
        report_expectations=(
            "material_package",
            "attachment_inventory",
            "archive_manifest",
            "expiry_metadata_report",
            "consortium_archive_manifest",
            "seal_position_residue_report",
            "object_preflight",
        ),
        boundary_notes=(
            "Consortium lead/member fields and certificate expiry metadata "
            "are inventory evidence, not a qualification-validity judgment.",
            "Seal placeholder or position residue should downgrade to a "
            "residue report before archive delivery.",
        ),
        request_sample_ids=("bidding_consortium_seal_archive",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="official_policy_fields_comments",
        pack_id="official_policy",
        label="Official policy fields and comments sample",
        family_id="meeting_policy_documents",
        docx_surfaces=("paragraph_run", "fields", "comments"),
        expected_preflight_findings=("fields", "comments"),
        report_expectations=("object_preflight", "policy_archive"),
    ),
    SceneSampleFixtureSpec(
        fixture_id="official_policy_formal_archive_manual_boundary",
        pack_id="official_policy",
        label="Official formal/internal archive manual-boundary sample",
        family_id="meeting_policy_documents",
        docx_surfaces=("paragraph_run", "fields", "comments", "hidden_text"),
        expected_preflight_findings=("fields", "comments", "hidden_text"),
        expected_behaviors=("detect", "preserve_layout", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "policy_archive",
            "official_delivery_status_report",
            "watermark_status_report",
            "object_preflight",
        ),
        boundary_notes=(
            "Official formal/internal copies, watermark state, and preserved "
            "numbering require manual confirmation before archive delivery.",
        ),
        request_sample_ids=("official_notice_formal_archive",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="official_policy_metadata_archive_report",
        pack_id="official_policy",
        label="Official metadata and archive-report sample",
        family_id="meeting_policy_documents",
        docx_surfaces=(
            "paragraph_run",
            "fields",
            "comments",
            "headers_footers",
            "package_relationships",
        ),
        expected_preflight_findings=("fields", "comments"),
        expected_behaviors=("detect",),
        report_expectations=(
            "policy_archive",
            "official_metadata_report",
            "formal_internal_archive_manifest",
            "official_delivery_status_report",
            "watermark_status_report",
            "object_preflight",
        ),
        boundary_notes=(
            "Official metadata, delivery status, and archive manifests are "
            "evidence for formatting and packaging, not administrative "
            "decision-substance validation.",
            "Formal/internal/archive status requires human confirmation before "
            "official release or archive-office handoff.",
        ),
        request_sample_ids=("official_policy_collection",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="technical_long_docs_skip_objects",
        pack_id="technical_long_docs",
        label="Technical long document high-risk object sample",
        family_id="long_document_publishing",
        docx_surfaces=(
            "paragraph_run",
            "ole_objects",
            "embedded_workbooks",
            "visio_drawings",
        ),
        expected_preflight_findings=(
            "ole_objects",
            "embedded_workbooks",
            "visio_drawings",
        ),
        expected_behaviors=("detect", "skip_report"),
        report_expectations=("object_preflight.module_skips",),
        boundary_notes=("Risky technical embedded objects should cause module downgrade.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="technical_long_docs_chapter_inventory_manual_boundary",
        pack_id="technical_long_docs",
        label="Technical long document chapter inventory manual-boundary sample",
        family_id="long_document_publishing",
        docx_surfaces=("paragraph_run", "fields", "comments", "embedded_packages"),
        expected_preflight_findings=("fields", "comments", "embedded_packages"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "count_report",
            "chapter_inventory",
            "cross_reference_status_report",
            "archive_package",
            "object_preflight",
        ),
        boundary_notes=(
            "Chapter inventory, cross-reference state, and archive completeness "
            "require manual confirmation before long-document delivery.",
        ),
        request_sample_ids=("technical_sop_chapter_inventory",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="technical_long_docs_index_appendix_merge_boundary",
        pack_id="technical_long_docs",
        label="Technical long document index/appendix merge-boundary sample",
        family_id="long_document_publishing",
        docx_surfaces=(
            "paragraph_run",
            "fields",
            "comments",
            "headers_footers",
            "embedded_packages",
            "package_relationships",
        ),
        expected_preflight_findings=("fields", "comments", "embedded_packages"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "chapter_inventory",
            "index_appendix_inventory",
            "multi_file_merge_boundary_report",
            "cross_reference_status_report",
            "archive_package",
            "object_preflight",
        ),
        boundary_notes=(
            "Index, appendix, and cross-file package evidence is an inventory "
            "and boundary signal, not a promise of lossless multi-document merge.",
            "Multi-file merge, rebuilt index entries, and appendix scope require "
            "manual confirmation before publishing delivery.",
        ),
        request_sample_ids=("technical_product_manual",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="application_reports_hidden_comments",
        pack_id="application_reports",
        label="Application report hidden text/comment sample",
        family_id="project_application",
        docx_surfaces=("paragraph_run", "fields", "comments", "hidden_text"),
        expected_preflight_findings=("fields", "comments", "hidden_text"),
        report_expectations=("count_report", "material_package", "object_preflight"),
    ),
    SceneSampleFixtureSpec(
        fixture_id="application_reports_project_attachment_degraded",
        pack_id="application_reports",
        label="Project application attachment and rule-source degraded sample",
        family_id="project_application",
        docx_surfaces=(
            "paragraph_run",
            "fields",
            "comments",
            "hidden_text",
            "embedded_packages",
        ),
        expected_preflight_findings=(
            "fields",
            "comments",
            "hidden_text",
            "embedded_packages",
        ),
        expected_behaviors=("detect", "skip_report"),
        report_expectations=(
            "count_report",
            "attachment_inventory",
            "missing_items_report",
            "material_package",
            "rule_source_governance",
            "submission_system_boundary_report",
            "object_preflight",
        ),
        boundary_notes=(
            "Missing application attachments or unreviewed project rules should "
            "downgrade to an inventory and rule-source boundary report.",
        ),
        request_sample_ids=("application_project_limits",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="application_reports_project_budget_manual_boundary",
        pack_id="application_reports",
        label="Project application budget attachment manual-boundary sample",
        family_id="project_application",
        docx_surfaces=("paragraph_run", "table_grid", "fields", "comments", "embedded_packages"),
        expected_preflight_findings=("fields", "comments", "embedded_packages"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "budget_attachment_report",
            "attachment_inventory",
            "rule_source_governance",
            "submission_system_boundary_report",
            "material_package",
            "object_preflight",
        ),
        boundary_notes=(
            "Budget tables, evidence attachments, and application-system "
            "submission state require manual confirmation before delivery.",
        ),
        request_sample_ids=("application_review_budget",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="application_reports_product_sales_assets",
        pack_id="application_reports",
        label="Product/sales asset consistency sample",
        family_id="product_sales_documents",
        docx_surfaces=("paragraph_run", "fields", "comments", "embedded_packages"),
        expected_preflight_findings=("fields", "comments", "embedded_packages"),
        report_expectations=(
            "asset_consistency_report",
            "quote_body_disambiguation",
            "material_package",
            "object_preflight",
        ),
        boundary_notes=("Product/sales samples do not imply technical manual authority.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="application_reports_product_asset_degraded",
        pack_id="application_reports",
        label="Product/sales asset degraded sample",
        family_id="product_sales_documents",
        docx_surfaces=("paragraph_run", "fields", "comments", "embedded_packages"),
        expected_preflight_findings=("fields", "comments", "embedded_packages"),
        expected_behaviors=("detect", "skip_report"),
        report_expectations=(
            "asset_report",
            "asset_consistency_report",
            "quote_body_disambiguation",
            "product_asset_inventory",
            "material_package",
            "coverage_boundaries",
            "object_preflight",
        ),
        boundary_notes=(
            "Missing product images, case-study evidence, or technical asset "
            "sources should downgrade to an asset boundary report.",
        ),
        request_sample_ids=("application_customer_product_manual",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="application_reports_product_version_manual_boundary",
        pack_id="application_reports",
        label="Product/sales customer-internal version manual-boundary sample",
        family_id="product_sales_documents",
        docx_surfaces=("paragraph_run", "fields", "comments", "hidden_text", "embedded_packages"),
        expected_preflight_findings=("fields", "comments", "hidden_text", "embedded_packages"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "customer_internal_version_report",
            "asset_consistency_report",
            "quote_body_disambiguation",
            "product_asset_inventory",
            "material_package",
            "object_preflight",
        ),
        boundary_notes=(
            "Customer/internal copy split, claim truthfulness, and sales-version "
            "approval require manual confirmation.",
        ),
        request_sample_ids=("application_presales_plan",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="contract_delivery_revisions",
        pack_id="contract_delivery",
        label="Contract revisions and hidden text sample",
        family_id="contract_delivery",
        docx_surfaces=("paragraph_run", "fields", "comments", "tracked_changes", "hidden_text"),
        expected_preflight_findings=("fields", "comments", "tracked_changes", "hidden_text"),
        report_expectations=("coverage_boundaries", "object_preflight"),
        boundary_notes=("Contract samples do not imply legal review.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="contract_delivery_signature_fields_degraded",
        pack_id="contract_delivery",
        label="Contract signing field and signature-asset degraded sample",
        family_id="contract_delivery",
        docx_surfaces=(
            "paragraph_run",
            "fields",
            "comments",
            "tracked_changes",
            "hidden_text",
            "embedded_packages",
        ),
        expected_preflight_findings=(
            "fields",
            "comments",
            "tracked_changes",
            "hidden_text",
            "embedded_packages",
        ),
        expected_behaviors=("detect", "skip_report", "preserve_layout"),
        report_expectations=(
            "coverage_boundaries",
            "contract_field_consistency_report",
            "signature_asset_report",
            "material_package",
            "object_preflight",
        ),
        boundary_notes=(
            "Missing or inconsistent contract party, amount, date, or signature "
            "assets should downgrade to a field/signature boundary report.",
        ),
        request_sample_ids=(
            "contract_signing_consistency",
            "contract_signature_package_fields",
        ),
    ),
    SceneSampleFixtureSpec(
        fixture_id="batch_forms_fixed_layout",
        pack_id="batch_forms",
        label="Batch form fixed row-height/control sample",
        family_id="form_batch_documents",
        docx_surfaces=(
            "paragraph_run",
            "table_grid",
            "fixed_row_height",
            "content_controls",
            "textboxes",
        ),
        expected_preflight_findings=("content_controls", "textboxes"),
        expected_behaviors=("detect", "preserve_layout"),
        report_expectations=(
            "fixed_layout_row_height",
            "fixed_layout_profile_browser",
            "profile_specific_preview",
            "answer_sheet_reuse_path",
            "object_preflight",
        ),
        boundary_notes=("Fixed-layout row height is not generic table styling.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="batch_forms_hr_batch_offer",
        pack_id="batch_forms",
        label="HR batch offer letter sample",
        family_id="hr_batch_documents",
        docx_surfaces=("paragraph_run", "fields", "content_controls", "comments"),
        expected_preflight_findings=("fields", "content_controls", "comments"),
        expected_behaviors=("detect", "preserve_layout"),
        report_expectations=(
            "batch_report",
            "profile_specific_preview",
            "object_preflight",
        ),
        boundary_notes=("HR batch samples do not verify personnel truthfulness.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="batch_forms_hr_missing_fields_manual_boundary",
        pack_id="batch_forms",
        label="HR batch missing-field item isolation manual-boundary sample",
        family_id="hr_batch_documents",
        docx_surfaces=("paragraph_run", "fields", "content_controls", "comments"),
        expected_preflight_findings=("fields", "content_controls", "comments"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "batch_failure_isolation",
            "missing_required_fields_report",
            "profile_specific_preview",
            "material_package",
            "object_preflight",
        ),
        boundary_notes=(
            "Per-person HR outputs with missing employee fields or signature "
            "assets require item-level isolation and manual repair.",
        ),
        request_sample_ids=("batch_employee_certificate",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="batch_forms_fixed_layout_placeholder_manual_boundary",
        pack_id="batch_forms",
        label="Fixed-layout placeholder residue manual-boundary sample",
        family_id="form_batch_documents",
        docx_surfaces=(
            "paragraph_run",
            "table_grid",
            "fixed_row_height",
            "content_controls",
            "textboxes",
        ),
        expected_preflight_findings=("content_controls", "textboxes"),
        expected_behaviors=("detect", "manual_confirmation", "preserve_layout"),
        report_expectations=(
            "coverage_boundaries",
            "fixed_layout_row_height",
            "fixed_layout_profile_browser",
            "profile_specific_preview",
            "answer_sheet_reuse_path",
            "placeholder_residue_report",
            "batch_failure_isolation",
            "object_preflight",
        ),
        boundary_notes=(
            "Fixed-layout forms with unresolved placeholders or uncertain target "
            "positions require manual confirmation before batch output.",
        ),
        request_sample_ids=("batch_certificate_printing",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="professional_disclosure_manual_boundary",
        pack_id="professional_disclosure",
        label="Professional disclosure hidden text/manual boundary sample",
        family_id="regulated_disclosure_documents",
        docx_surfaces=("paragraph_run", "fields", "comments", "hidden_text", "ole_objects"),
        expected_preflight_findings=("fields", "comments", "hidden_text", "ole_objects"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=("coverage_boundaries", "plugin_manual_gate", "object_preflight"),
        manual_gate_id="professional_disclosure_review_gate",
        boundary_notes=("Disclosure samples do not perform audit or assurance judgment.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="professional_disclosure_source_quality_degraded",
        pack_id="professional_disclosure",
        label="Professional disclosure source-quality degraded sample",
        family_id="finance_quote_documents",
        docx_surfaces=("paragraph_run", "fields", "comments", "embedded_workbooks"),
        expected_preflight_findings=("fields", "comments", "embedded_workbooks"),
        expected_behaviors=("detect", "skip_report"),
        report_expectations=(
            "coverage_boundaries",
            "professional_source_quality_report",
            "attachment_inventory",
            "object_preflight",
        ),
        manual_gate_id="professional_disclosure_review_gate",
        boundary_notes=(
            "Incomplete spreadsheets, attachment evidence, or professional-source "
            "uncertainty should downgrade before manual/plugin review.",
        ),
        request_sample_ids=("professional_finance_quote",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="professional_disclosure_finance_table_mapping_boundary",
        pack_id="professional_disclosure",
        label="Finance quote spreadsheet table-mapping boundary sample",
        family_id="finance_quote_documents",
        docx_surfaces=("paragraph_run", "table_grid", "fields", "comments", "embedded_workbooks"),
        expected_preflight_findings=("fields", "comments", "embedded_workbooks"),
        expected_behaviors=("detect", "skip_report", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "finance_spreadsheet_mapping_report",
            "finance_plugin_handoff",
            "attachment_inventory",
            "professional_boundary_matrix",
            "object_preflight",
        ),
        manual_gate_id="professional_disclosure_review_gate",
        boundary_notes=(
            "Spreadsheet table mapping is captured as evidence before any finance "
            "assurance or procurement judgment.",
        ),
        request_sample_ids=("professional_finance_quote",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="professional_disclosure_patent_claim_quality_boundary",
        pack_id="professional_disclosure",
        label="Patent claim-quality manual boundary sample",
        family_id="ip_patent_documents",
        docx_surfaces=("paragraph_run", "fields", "comments", "drawing_media_rels"),
        expected_preflight_findings=("fields", "comments"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "patent_claim_boundary_report",
            "claim_quality_boundary_ui",
            "ip_plugin_handoff",
            "professional_boundary_matrix",
            "object_preflight",
        ),
        manual_gate_id="professional_disclosure_review_gate",
        boundary_notes=(
            "Claim numbering, figures, and placeholders can be inventoried, but "
            "patentability and claim quality remain professional review.",
        ),
        request_sample_ids=("professional_patent_claims",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="professional_disclosure_bilingual_termbase_boundary",
        pack_id="professional_disclosure",
        label="Bilingual termbase and translation-quality boundary sample",
        family_id="bilingual_translation_documents",
        docx_surfaces=("paragraph_run", "table_grid", "comments", "tracked_changes", "textboxes"),
        expected_preflight_findings=("comments", "tracked_changes", "textboxes"),
        expected_behaviors=("detect", "manual_confirmation", "preserve_layout"),
        report_expectations=(
            "coverage_boundaries",
            "bilingual_termbase_report",
            "termbase_ui",
            "translation_quality_plugin_handoff",
            "professional_boundary_matrix",
            "object_preflight",
        ),
        manual_gate_id="professional_disclosure_review_gate",
        boundary_notes=(
            "Termbase and parallel layout evidence do not guarantee translation "
            "quality or silently rewrite bilingual meaning.",
        ),
        request_sample_ids=("professional_bilingual_terms",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="professional_disclosure_regulated_assurance_boundary",
        pack_id="professional_disclosure",
        label="Regulated disclosure rule-source and assurance boundary sample",
        family_id="regulated_disclosure_documents",
        docx_surfaces=("paragraph_run", "table_grid", "fields", "comments", "hidden_text", "embedded_workbooks"),
        expected_preflight_findings=("fields", "comments", "hidden_text", "embedded_workbooks"),
        expected_behaviors=("detect", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "regulated_rule_source_governance",
            "assurance_boundary_ui",
            "disclosure_archive_manifest",
            "professional_boundary_matrix",
            "object_preflight",
        ),
        manual_gate_id="professional_disclosure_review_gate",
        boundary_notes=(
            "Disclosure inventories and rule-source notes do not perform audit, "
            "assurance, or regulated filing completeness decisions.",
        ),
        request_sample_ids=("professional_esg_archive",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="import_ai_boundary_blocking_macro",
        pack_id="import_ai_boundary",
        label="Import/AI macro blocking sample",
        docx_surfaces=("paragraph_run", "macros", "ole_objects", "textboxes"),
        expected_preflight_findings=("macros", "ole_objects", "textboxes"),
        expected_behaviors=("detect", "block_report", "manual_confirmation"),
        report_expectations=("coverage_boundaries", "object_preflight.blocking"),
        manual_gate_id="import_ai_conversion_gate",
        boundary_notes=("Import samples require confidence/manual confirmation before core execution.",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="import_ai_boundary_conversion_confidence_degraded",
        pack_id="import_ai_boundary",
        label="Import/AI conversion confidence degraded sample",
        docx_surfaces=("paragraph_run", "fields", "comments", "hidden_text"),
        expected_preflight_findings=("fields", "comments", "hidden_text"),
        expected_behaviors=("detect", "skip_report"),
        report_expectations=(
            "coverage_boundaries",
            "conversion_confidence_report",
            "import_handoff",
            "object_preflight",
        ),
        manual_gate_id="import_ai_conversion_gate",
        boundary_notes=(
            "Low-confidence OCR/PDF/AI conversion should downgrade to a confidence "
            "report before handoff to a target Word scene.",
        ),
        request_sample_ids=("import_ocr_pdf",),
    ),
    SceneSampleFixtureSpec(
        fixture_id="import_ai_boundary_latex_handoff_confidence",
        pack_id="import_ai_boundary",
        label="Import/AI LaTeX and diagram confidence-handoff sample",
        docx_surfaces=("paragraph_run", "fields", "comments", "textboxes", "embedded_packages"),
        expected_preflight_findings=("fields", "comments", "textboxes", "embedded_packages"),
        expected_behaviors=("detect", "skip_report", "manual_confirmation"),
        report_expectations=(
            "coverage_boundaries",
            "conversion_confidence_report",
            "confidence_artifact_manifest",
            "ocr_pdf_latex_plugin_boundary",
            "import_handoff",
            "object_preflight",
        ),
        manual_gate_id="import_ai_conversion_gate",
        boundary_notes=(
            "LaTeX projects, complex diagrams, and AI-imported content require "
            "confidence artifacts and explicit handoff before target-scene execution.",
        ),
        request_sample_ids=("import_latex_project", "import_ai_diagrams"),
    ),
)

SCENE_SAMPLE_FIXTURE_MAP: dict[str, SceneSampleFixtureSpec] = {
    spec.fixture_id: spec for spec in SCENE_SAMPLE_FIXTURES
}


def list_scene_sample_fixtures() -> tuple[SceneSampleFixtureSpec, ...]:
    return SCENE_SAMPLE_FIXTURES


def get_scene_sample_fixture(fixture_id: str) -> SceneSampleFixtureSpec:
    normalized = str(fixture_id or "").strip()
    try:
        return SCENE_SAMPLE_FIXTURE_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown scene sample fixture: {fixture_id}") from exc


def scene_sample_fixtures_for_pack(pack_id: str) -> tuple[SceneSampleFixtureSpec, ...]:
    normalized = str(pack_id or "").strip()
    return tuple(spec for spec in SCENE_SAMPLE_FIXTURES if spec.pack_id == normalized)


def sample_surface_coverage() -> dict[str, tuple[str, ...]]:
    return {
        surface: tuple(
            spec.fixture_id for spec in SCENE_SAMPLE_FIXTURES if surface in spec.docx_surfaces
        )
        for surface in SUPPORTED_SAMPLE_SURFACES
    }


def build_scene_sample_coverage_summary(
    pack_ids: Sequence[str],
) -> SceneSampleCoverageSummary:
    normalized_pack_ids = _unique_values(pack_ids)
    fixtures: list[SceneSampleFixtureSpec] = []
    missing_pack_ids: list[str] = []
    for pack_id in normalized_pack_ids:
        pack_fixtures = scene_sample_fixtures_for_pack(pack_id)
        if not pack_fixtures:
            missing_pack_ids.append(pack_id)
        fixtures.extend(pack_fixtures)
    return SceneSampleCoverageSummary(
        pack_ids=normalized_pack_ids,
        fixture_ids=tuple(spec.fixture_id for spec in fixtures),
        docx_surfaces=_ordered_supported_values(
            (surface for spec in fixtures for surface in spec.docx_surfaces),
            SUPPORTED_SAMPLE_SURFACES,
        ),
        expected_behaviors=_ordered_supported_values(
            (behavior for spec in fixtures for behavior in spec.expected_behaviors),
            SUPPORTED_SAMPLE_BEHAVIORS,
        ),
        manual_gate_ids=_unique_values(spec.manual_gate_id for spec in fixtures),
        boundary_notes=_unique_values(
            note for spec in fixtures for note in spec.boundary_notes
        ),
        missing_pack_ids=tuple(missing_pack_ids),
        audit_issues=audit_scene_sample_fixtures(),
    )


def audit_scene_sample_fixtures() -> tuple[SceneSampleFixtureAuditIssue, ...]:
    issues: list[SceneSampleFixtureAuditIssue] = []
    seen: set[str] = set()
    covered_packs = {spec.pack_id for spec in SCENE_SAMPLE_FIXTURES}
    coverage = sample_surface_coverage()

    for spec in SCENE_SAMPLE_FIXTURES:
        if not spec.fixture_id:
            issues.append(
                SceneSampleFixtureAuditIssue(
                    fixture_id="",
                    kind="missing_fixture_id",
                    message="Scene sample fixture requires fixture_id.",
                )
            )
            continue
        if spec.fixture_id in seen:
            issues.append(
                SceneSampleFixtureAuditIssue(
                    fixture_id=spec.fixture_id,
                    kind="duplicate_fixture_id",
                    message=f"Duplicate sample fixture id: {spec.fixture_id}",
                )
            )
        seen.add(spec.fixture_id)
        if spec.pack_id not in SCENE_COVERAGE_PACK_MAP:
            issues.append(
                SceneSampleFixtureAuditIssue(
                    fixture_id=spec.fixture_id,
                    kind="unknown_pack",
                    message=f"Unknown coverage pack: {spec.pack_id}",
                )
            )
        if not spec.docx_surfaces:
            issues.append(
                SceneSampleFixtureAuditIssue(
                    fixture_id=spec.fixture_id,
                    kind="missing_surfaces",
                    message="Sample fixture must declare at least one DOCX surface.",
                )
            )
        for surface in spec.docx_surfaces:
            if surface not in SUPPORTED_SAMPLE_SURFACES:
                issues.append(
                    SceneSampleFixtureAuditIssue(
                        fixture_id=spec.fixture_id,
                        kind="unknown_surface",
                        message=f"Unknown DOCX sample surface: {surface}",
                    )
                )
        for finding in spec.expected_preflight_findings:
            if finding not in SUPPORTED_SAMPLE_SURFACES:
                issues.append(
                    SceneSampleFixtureAuditIssue(
                        fixture_id=spec.fixture_id,
                        kind="unknown_expected_finding",
                        message=f"Unknown expected preflight finding: {finding}",
                    )
                )
        for behavior in spec.expected_behaviors:
            if behavior not in SUPPORTED_SAMPLE_BEHAVIORS:
                issues.append(
                    SceneSampleFixtureAuditIssue(
                        fixture_id=spec.fixture_id,
                        kind="unknown_behavior",
                        message=f"Unknown expected sample behavior: {behavior}",
                    )
                )
        if "manual_confirmation" in spec.expected_behaviors and (
            spec.manual_gate_id or plugin_manual_gate_for_pack(spec.pack_id) is not None
        ):
            gate = plugin_manual_gate_for_pack(spec.pack_id)
            if gate is None or gate.gate_id != spec.manual_gate_id:
                issues.append(
                    SceneSampleFixtureAuditIssue(
                        fixture_id=spec.fixture_id,
                        kind="manual_gate_mismatch",
                        message=(
                            f"Expected manual gate '{spec.manual_gate_id}' is not "
                            f"registered for pack '{spec.pack_id}'."
                        ),
                    )
                )
    for pack_id in REQUIRED_SAMPLE_PACK_IDS:
        if pack_id not in covered_packs:
            issues.append(
                SceneSampleFixtureAuditIssue(
                    fixture_id=pack_id,
                    kind="missing_required_pack_fixture",
                    message=f"Required pack '{pack_id}' has no DOCX sample fixture.",
                )
            )
    for surface in REQUIRED_SAMPLE_SURFACES:
        if not coverage.get(surface):
            issues.append(
                SceneSampleFixtureAuditIssue(
                    fixture_id=surface,
                    kind="missing_required_surface",
                    message=f"Required OOXML sample surface '{surface}' is not covered.",
                )
            )
    return tuple(issues)


def build_scene_sample_fixture_summary(spec: SceneSampleFixtureSpec) -> str:
    surfaces = ",".join(spec.docx_surfaces)
    findings = ",".join(spec.expected_preflight_findings) or "-"
    behaviors = ",".join(spec.expected_behaviors) or "-"
    return (
        f"{spec.fixture_id}: pack={spec.pack_id}; family={spec.family_id or '-'}; "
        f"surfaces={surfaces}; findings={findings}; behaviors={behaviors}; "
        f"gate={spec.manual_gate_id or '-'}"
    )


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def _ordered_supported_values(
    values: Iterable[object],
    supported_order: Sequence[str],
) -> tuple[str, ...]:
    value_set = set(_unique_values(values))
    ordered = [value for value in supported_order if value in value_set]
    extras = sorted(value_set - set(supported_order))
    return tuple([*ordered, *extras])


__all__ = [
    "REQUIRED_SAMPLE_PACK_IDS",
    "REQUIRED_SAMPLE_SURFACES",
    "SCENE_SAMPLE_FIXTURE_MAP",
    "SCENE_SAMPLE_FIXTURES",
    "SUPPORTED_SAMPLE_BEHAVIORS",
    "SUPPORTED_SAMPLE_SURFACES",
    "SceneSampleCoverageSummary",
    "SceneSampleFixtureAuditIssue",
    "SceneSampleFixtureSpec",
    "audit_scene_sample_fixtures",
    "build_scene_sample_coverage_summary",
    "build_scene_sample_fixture_summary",
    "get_scene_sample_fixture",
    "list_scene_sample_fixtures",
    "sample_surface_coverage",
    "scene_sample_fixtures_for_pack",
]
