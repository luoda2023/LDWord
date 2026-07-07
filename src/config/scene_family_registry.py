"""Planning-level scene family registry.

This registry records high-frequency scene families that are close to the
current product surface but are not ready to become top-level built-in scenes.
It is intentionally separate from Workbench ``SCENE_METAS`` and scene
factories, so planned coverage does not masquerade as executable support.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlannedSceneFamily:
    """A planning contract for one high-frequency scene family."""

    family_id: str
    name: str
    priority: str
    intended_landing: str
    default_profile_id: str
    input_formats: tuple[str, ...]
    material_schema_ids: tuple[str, ...]
    compliance_profiles: tuple[str, ...]
    count_profiles: tuple[str, ...]
    delivery_presets: tuple[str, ...]
    capability_domains: tuple[str, ...]
    workflow_archetypes: tuple[str, ...]
    maturity_level: str
    first_closed_slice: str
    ooxml_touchpoints: tuple[str, ...]
    required_closures: tuple[str, ...]
    boundaries: tuple[str, ...]
    expose_in_navigation: bool = False


PLANNED_SCENE_FAMILIES: tuple[PlannedSceneFamily, ...] = (
    PlannedSceneFamily(
        family_id="thesis_cn",
        name="Chinese academic thesis and coursework",
        priority="P1",
        intended_landing="existing_thesis_scene_profile",
        default_profile_id="thesis_cn",
        input_formats=("docx", "markdown", "json"),
        material_schema_ids=("thesis_school_rule_context_v1",),
        compliance_profiles=("thesis_cn", "school_thesis"),
        count_profiles=("thesis_cn", "school_thesis"),
        delivery_presets=(
            "final",
            "review",
            "compliance_report",
        ),
        capability_domains=(
            "template_baseline",
            "scope_structure",
            "compliance_counting",
            "references_citations",
            "formula_symbols",
            "delivery_package",
        ),
        workflow_archetypes=(
            "structured_input",
            "template_normalization",
            "scope_localization",
            "compliance_counting",
            "references_citations",
            "formula_symbols",
            "submission_package",
        ),
        maturity_level="L2",
        first_closed_slice=(
            "existing thesis scene uses thesis_cn compliance profile and school_thesis count profile"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "run",
            "numbering",
            "table",
            "drawing",
            "field",
            "header_footer",
            "footnote",
            "endnote",
        ),
        required_closures=(
            "Chinese academic profile split from journal_en and exam_teaching",
            "school thesis count profile and scope report evidence",
            "citation and reference confidence reporting",
            "formula conversion confidence reporting",
            "review and compliance report delivery presets",
        ),
        boundaries=(
            "does not absorb English journal submission",
            "does not generate exam student or teacher versions",
            "does not claim one school count profile is authoritative for every institution",
        ),
    ),
    PlannedSceneFamily(
        family_id="journal_en",
        name="English journal submission",
        priority="P1",
        intended_landing="independent_scene_family",
        default_profile_id="journal_en_default",
        input_formats=("docx", "markdown", "bibtex", "csl_json"),
        material_schema_ids=("journal_submission_materials_v1",),
        compliance_profiles=("journal_submission", "journal_revision"),
        count_profiles=("journal_words", "journal_display_items"),
        delivery_presets=(
            "submission_manuscript",
            "review_copy",
            "cover_letter",
            "declaration_package",
            "compliance_report",
        ),
        capability_domains=(
            "input_sources",
            "references_citations",
            "formula_symbols",
            "compliance_counting",
            "object_safety",
            "delivery_package",
        ),
        workflow_archetypes=(
            "compliance_counting",
            "references_citations",
            "submission_package",
            "review_compare",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "section word count + display item count + submission package manifest"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "table",
            "drawing",
            "field",
            "comment",
            "revision",
            "relationship",
        ),
        required_closures=(
            "journal profile registry",
            "reviewed journal rule source governance",
            "BibTeX/CSL parsing and citation checks",
            "section-aware word/display-item counting",
            "submission package delivery preset",
            "high-risk object preflight explanation",
        ),
        boundaries=(
            "does not promise publisher-final layout",
            "does not fetch journal rules without a reviewed profile update flow",
            "does not promise lossless full LaTeX project conversion",
        ),
    ),
    PlannedSceneFamily(
        family_id="exam_teaching",
        name="Exam and teaching materials",
        priority="P1",
        intended_landing="independent_scene_family_or_education_profile",
        default_profile_id="exam_teaching_default",
        input_formats=("docx", "markdown", "json", "xlsx"),
        material_schema_ids=("exam_items_v1", "teaching_assets_v1"),
        compliance_profiles=("exam_paper", "teaching_handout"),
        count_profiles=("exam_items", "teaching_sections"),
        delivery_presets=(
            "student_version",
            "teacher_version",
            "answer_key",
            "analysis_version",
            "answer_sheet",
        ),
        capability_domains=(
            "structured_input",
            "formula_symbols",
            "images_assets",
            "multi_version_delivery",
            "batch_generation",
        ),
        workflow_archetypes=(
            "structured_input",
            "content_visibility",
            "multi_version_delivery",
            "batch_generation",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "structured question source + student/teacher/answer visibility rendering"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "run",
            "table",
            "drawing",
            "numbering",
            "section",
            "relationship",
        ),
        required_closures=(
            "question schema validation",
            "single structured source for all paper versions",
            "answer/analysis visibility rules",
            "discipline-specific formula and image handling",
            "answer sheet delivery preset",
        ),
        boundaries=(
            "does not validate AI-generated content quality",
            "does not generate complex geometry diagrams in core",
            "does not create student and teacher versions from separate sources",
        ),
    ),
    PlannedSceneFamily(
        family_id="project_application",
        name="Project application and review materials",
        priority="P1",
        intended_landing="profile_shared_with_academic_and_bidding_capabilities",
        default_profile_id="project_application_default",
        input_formats=("docx", "markdown", "xlsx", "json"),
        material_schema_ids=("project_application_materials_v1",),
        compliance_profiles=("project_application", "project_review_pack"),
        count_profiles=("application_word_limits", "attachment_inventory"),
        delivery_presets=(
            "application_package",
            "attachment_inventory_report",
        ),
        capability_domains=(
            "material_package",
            "compliance_checklist",
            "counting_limits",
            "attachment_inventory",
            "delivery_package",
            "object_safety",
        ),
        workflow_archetypes=(
            "material_fill",
            "attachment_inventory",
            "compliance_counting",
            "submission_package",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "attachment inventory + word limit profile + application package manifest"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "table",
            "drawing",
            "field",
            "header_footer",
            "section",
            "relationship",
        ),
        required_closures=(
            "project/team/budget material schema",
            "attachment completeness checks",
            "word limit and section scope profiles",
            "application and attachment package delivery presets",
            "review report for missing or risky materials",
        ),
        boundaries=(
            "does not replace external submission systems",
            "does not predict review scores",
            "does not verify the truthfulness of attachment contents",
        ),
    ),
    PlannedSceneFamily(
        family_id="contract_delivery",
        name="Contract and agreement delivery",
        priority="P1",
        intended_landing="profile_shared_with_official_and_business_capabilities",
        default_profile_id="contract_delivery_default",
        input_formats=("docx", "json"),
        material_schema_ids=("contract_parties_v1", "signature_assets_v1"),
        compliance_profiles=("contract_format", "contract_review_copy"),
        count_profiles=("contract_fields",),
        delivery_presets=(
            "review_copy",
            "signing_copy",
            "field_consistency_report",
        ),
        capability_domains=(
            "material_package",
            "field_consistency",
            "object_safety",
            "review_compare",
            "delivery_package",
        ),
        workflow_archetypes=(
            "field_consistency",
            "object_safety",
            "review_compare",
            "signing_package",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "party/amount/date consistency + tracked-change protection + review/signing presets"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "run",
            "field",
            "comment",
            "revision",
            "header_footer",
            "relationship",
        ),
        required_closures=(
            "party/amount/date/signature material schema",
            "tracked changes and comments preservation policy",
            "field consistency checks for repeated contract values",
            "review and signing delivery presets",
            "legal-advice boundary explanation in reports",
        ),
        boundaries=(
            "does not provide legal advice",
            "does not judge whether contract clauses are valid",
            "does not verify the truthfulness of party or signature data",
        ),
    ),
    PlannedSceneFamily(
        family_id="hr_batch_documents",
        name="HR and personnel batch documents",
        priority="P1",
        intended_landing="material_batch_profile",
        default_profile_id="hr_batch_documents_default",
        input_formats=("docx", "xlsx", "json"),
        material_schema_ids=("personnel_records_v1",),
        compliance_profiles=("personnel_batch", "hr_document_fields"),
        count_profiles=("batch_item_inventory",),
        delivery_presets=(
            "per_person_docx",
            "batch_summary_report",
            "failed_items_report",
        ),
        capability_domains=(
            "structured_input",
            "material_package",
            "batch_generation",
            "delivery_package",
            "compliance_checklist",
        ),
        workflow_archetypes=(
            "structured_input",
            "material_fill",
            "batch_generation",
            "failure_isolation",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "one-record-one-output xlsx/json batch + failure isolation + summary report"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "table",
            "drawing",
            "content_control",
            "header_footer",
        ),
        required_closures=(
            "personnel field schema",
            "one-record-one-output batch mapping",
            "per-item failure isolation",
            "batch artifact summary by profile and preset",
            "resume/certificate/offer/invitation template profiles",
        ),
        boundaries=(
            "does not verify personnel qualification or background truthfulness",
            "does not need a top-level navigation entry",
            "does not merge failed records into successful outputs",
        ),
    ),
    PlannedSceneFamily(
        family_id="meeting_policy_documents",
        name="Meeting minutes and policy collections",
        priority="P1",
        intended_landing="official_sub_profile",
        default_profile_id="meeting_policy_documents_default",
        input_formats=("docx", "markdown", "json"),
        material_schema_ids=("administrative_meeting_fields_v1",),
        compliance_profiles=("meeting_minutes", "policy_collection"),
        count_profiles=("administrative_sections",),
        delivery_presets=(
            "formal_minutes",
            "internal_review",
            "policy_collection",
            "archive_manifest",
        ),
        capability_domains=(
            "material_package",
            "scope_structure",
            "preserve_numbering",
            "delivery_package",
            "object_safety",
        ),
        workflow_archetypes=(
            "official_fields",
            "preserve_numbering",
            "collection_archive",
            "formal_internal_delivery",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "official sub-profile + formal/internal delivery + archive metadata"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "numbering",
            "field",
            "header_footer",
            "section",
        ),
        required_closures=(
            "meeting participants and agenda material schema",
            "preserve-numbering official document profile",
            "policy collection section and appendix model",
            "formal/internal review delivery presets",
            "archive-oriented metadata report",
            "policy archive profile defaults",
        ),
        boundaries=(
            "does not create many small top-level administrative scenes",
            "does not own official page layout details",
            "does not validate administrative decision substance",
        ),
    ),
    PlannedSceneFamily(
        family_id="product_sales_documents",
        name="Product, whitepaper, and pre-sales documents",
        priority="P1",
        intended_landing="profile_shared_with_report_technical_bidding",
        default_profile_id="product_sales_documents_default",
        input_formats=("docx", "markdown", "json", "xlsx"),
        material_schema_ids=("product_assets_v1", "case_study_assets_v1"),
        compliance_profiles=("product_document", "pre_sales_package"),
        count_profiles=("product_asset_inventory",),
        delivery_presets=(
            "customer_copy",
            "internal_review",
            "asset_report",
            "pre_sales_package",
        ),
        capability_domains=(
            "material_package",
            "images_assets",
            "table_chart",
            "review_compare",
            "delivery_package",
        ),
        workflow_archetypes=(
            "material_fill",
            "image_table_assets",
            "customer_internal_delivery",
            "review_compare",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "product asset schema + customer/internal delivery presets"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "table",
            "drawing",
            "section",
            "relationship",
        ),
        required_closures=(
            "product specification and asset schema",
            "image/table consistency checks",
            "customer/internal delivery presets",
            "quote-number professional boundary",
            "upgrade path to bidding or technical profiles",
        ),
        boundaries=(
            "does not promise marketing copy quality",
            "does not treat content generation as a core scene capability",
            "does not judge quotation or financial correctness",
        ),
    ),
    PlannedSceneFamily(
        family_id="long_document_publishing",
        name="Book manuscript and long document publishing",
        priority="P1_CANDIDATE",
        intended_landing="long_document_profile",
        default_profile_id="long_document_publishing_default",
        input_formats=("docx", "markdown"),
        material_schema_ids=("long_document_metadata_v1",),
        compliance_profiles=("long_document_structure", "proof_copy"),
        count_profiles=("chapter_inventory",),
        delivery_presets=(
            "review_copy",
            "proof_copy",
            "final_docx",
            "archive_package",
        ),
        capability_domains=(
            "scope_structure",
            "references_citations",
            "review_compare",
            "delivery_archive",
            "object_safety",
        ),
        workflow_archetypes=(
            "chapter_inventory",
            "cross_reference_protection",
            "review_compare",
            "archive_package",
        ),
        maturity_level="L1",
        first_closed_slice="chapter inventory + object-risk report",
        ooxml_touchpoints=(
            "paragraph",
            "numbering",
            "table",
            "drawing",
            "field",
            "header_footer",
            "section",
            "relationship",
        ),
        required_closures=(
            "chapter model and multi-file import boundary",
            "table of contents and cross-reference strategy",
            "index and appendix handling decision",
            "review/proof/final/archive delivery presets",
            "publisher-system boundary explanation",
        ),
        boundaries=(
            "does not replace publisher layout systems",
            "does not promise lossless multi-document merge yet",
            "does not expose as a top-level scene before long-document closure",
        ),
    ),
    PlannedSceneFamily(
        family_id="form_batch_documents",
        name="Form filling and fixed-layout batch documents",
        priority="P1_CANDIDATE",
        intended_landing="batch_form_profile_shared_with_hr_official_project",
        default_profile_id="form_batch_documents_default",
        input_formats=("docx", "xlsx", "json"),
        material_schema_ids=("form_batch_fields_v1",),
        compliance_profiles=("form_batch_fields", "placeholder_residue_check"),
        count_profiles=("batch_item_inventory",),
        delivery_presets=(
            "per_record_docx",
            "batch_summary_report",
            "residue_check_report",
        ),
        capability_domains=(
            "structured_input",
            "material_package",
            "placeholder_fill",
            "batch_generation",
            "delivery_package",
        ),
        workflow_archetypes=(
            "structured_input",
            "placeholder_fill",
            "batch_generation",
            "residue_check",
        ),
        maturity_level="L1",
        first_closed_slice="fixed-layout field fill + placeholder residue report",
        ooxml_touchpoints=(
            "paragraph",
            "table",
            "row_height",
            "textbox",
            "shape",
            "content_control",
            "field",
            "header_footer",
        ),
        required_closures=(
            "fixed-layout field schema and mapping model",
            "one-record-one-output batch delivery",
            "placeholder residue and empty-field checks",
            "profile reuse path for HR, official, and project forms",
            "batch failure isolation and summary report",
        ),
        boundaries=(
            "does not replace professional form systems",
            "does not need an immediate top-level navigation entry",
            "does not judge whether submitted form data is truthful",
        ),
    ),
    PlannedSceneFamily(
        family_id="qualification_archive_packages",
        name="Qualification certificate and attachment packages",
        priority="P1_CANDIDATE",
        intended_landing="shared_material_inventory_for_bidding_and_projects",
        default_profile_id="qualification_archive_packages_default",
        input_formats=("docx", "xlsx", "json"),
        material_schema_ids=("qualification_archive_assets_v1",),
        compliance_profiles=("qualification_inventory", "attachment_completeness"),
        count_profiles=("attachment_inventory",),
        delivery_presets=(
            "attachment_package",
            "missing_items_report",
            "archive_manifest",
        ),
        capability_domains=(
            "material_package",
            "attachment_inventory",
            "images_assets",
            "compliance_checklist",
            "delivery_archive",
        ),
        workflow_archetypes=(
            "attachment_inventory",
            "image_pdf_assets",
            "missing_items_report",
            "archive_package",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "certificate/license attachment inventory + missing-items manifest"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "table",
            "drawing",
            "relationship",
            "package_part",
        ),
        required_closures=(
            "certificate/license attachment schema",
            "image/PDF role inventory",
            "missing attachment and expired-metadata report",
            "reuse path from bidding and project application profiles",
            "archive manifest delivery preset",
        ),
        boundaries=(
            "does not verify certificate authenticity",
            "does not judge qualification validity",
            "does not need a standalone top-level scene",
        ),
    ),
    PlannedSceneFamily(
        family_id="finance_quote_documents",
        name="Finance, quotation, and audit-format documents",
        priority="P2",
        intended_landing="professional_profile_or_plugin",
        default_profile_id="finance_quote_documents_default",
        input_formats=("docx", "xlsx", "json"),
        material_schema_ids=("finance_quote_fields_v1",),
        compliance_profiles=("quote_document_format", "finance_attachment_pack"),
        count_profiles=("finance_attachment_inventory",),
        delivery_presets=(
            "customer_quote",
            "internal_review",
            "attachment_report",
        ),
        capability_domains=(
            "structured_input",
            "table_chart",
            "material_package",
            "compliance_checklist",
            "delivery_package",
        ),
        workflow_archetypes=(
            "structured_input",
            "spreadsheet_table_mapping",
            "attachment_inventory",
            "professional_boundary",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "spreadsheet-to-document table mapping + attachment consistency report"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "table",
            "drawing",
            "field",
            "embedded_workbook",
            "relationship",
        ),
        required_closures=(
            "quote and budget field schema",
            "spreadsheet-to-document table mapping",
            "attachment completeness report",
            "professional judgment boundary in UI and reports",
            "optional finance plugin handoff",
        ),
        boundaries=(
            "does not perform financial audit judgment",
            "does not verify quotation correctness",
            "does not replace accounting or procurement systems",
        ),
    ),
    PlannedSceneFamily(
        family_id="ip_patent_documents",
        name="Patent and intellectual-property documents",
        priority="P2",
        intended_landing="professional_plugin",
        default_profile_id="ip_patent_documents_default",
        input_formats=("docx", "markdown", "json"),
        material_schema_ids=("patent_document_fields_v1",),
        compliance_profiles=("patent_structure", "ip_review_package"),
        count_profiles=("patent_section_inventory",),
        delivery_presets=(
            "disclosure_form",
            "specification_draft",
            "review_copy",
        ),
        capability_domains=(
            "scope_structure",
            "figure_captioning",
            "terminology_fields",
            "review_compare",
            "professional_plugin",
        ),
        workflow_archetypes=(
            "section_inventory",
            "figure_captioning",
            "terminology_fields",
            "review_compare",
        ),
        maturity_level="L1",
        first_closed_slice="section/figure-number inventory + review copy",
        ooxml_touchpoints=(
            "paragraph",
            "numbering",
            "table",
            "drawing",
            "caption",
            "field",
        ),
        required_closures=(
            "patent section and figure-number profile",
            "technical term and claim placeholder schema",
            "review delivery preset",
            "professional IP plugin boundary",
            "legal-quality disclaimer in reports",
        ),
        boundaries=(
            "does not promise patent legal quality",
            "does not judge claim validity or infringement risk",
            "does not replace professional patent drafting review",
        ),
    ),
    PlannedSceneFamily(
        family_id="bilingual_translation_documents",
        name="Bilingual and translation-review documents",
        priority="P2",
        intended_landing="profile_or_translation_plugin_boundary",
        default_profile_id="bilingual_translation_documents_default",
        input_formats=("docx", "markdown", "json", "xlsx"),
        material_schema_ids=("bilingual_terms_v1",),
        compliance_profiles=("bilingual_layout", "translation_review_pack"),
        count_profiles=("bilingual_parallel_text",),
        delivery_presets=(
            "bilingual_review_copy",
            "parallel_comparison",
            "term_consistency_report",
        ),
        capability_domains=(
            "scope_structure",
            "terminology_fields",
            "table_chart",
            "review_compare",
            "plugin_boundary",
        ),
        workflow_archetypes=(
            "bilingual_layout",
            "terminology_consistency",
            "parallel_review",
            "professional_boundary",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "parallel paragraph/table layout + terminology consistency report"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "run",
            "table",
            "field",
            "comment",
            "revision",
            "textbox",
        ),
        required_closures=(
            "bilingual termbase and language-pair material schema",
            "parallel paragraph/table alignment profile",
            "term consistency and unresolved-source report",
            "review-copy delivery preset",
            "translation-quality plugin boundary in UI and reports",
        ),
        boundaries=(
            "does not guarantee translation quality",
            "does not replace professional translation review",
            "does not silently rewrite bilingual legal or technical meaning",
        ),
    ),
    PlannedSceneFamily(
        family_id="regulated_disclosure_documents",
        name="Annual, ESG, and regulated disclosure documents",
        priority="P2",
        intended_landing="profile_combination_with_long_document_finance_and_report",
        default_profile_id="regulated_disclosure_documents_default",
        input_formats=("docx", "markdown", "xlsx", "json"),
        material_schema_ids=("regulated_disclosure_materials_v1",),
        compliance_profiles=("regulated_disclosure_structure", "disclosure_review_pack"),
        count_profiles=("disclosure_section_inventory", "attachment_inventory"),
        delivery_presets=(
            "board_review_copy",
            "public_release_copy",
            "disclosure_archive_package",
            "archive_manifest",
        ),
        capability_domains=(
            "scope_structure",
            "table_chart",
            "attachment_inventory",
            "review_compare",
            "delivery_archive",
        ),
        workflow_archetypes=(
            "long_report_structure",
            "table_attachment_inventory",
            "review_compare",
            "archive_package",
        ),
        maturity_level="L1",
        first_closed_slice=(
            "section/table/attachment inventory + board/public/archive presets"
        ),
        ooxml_touchpoints=(
            "paragraph",
            "numbering",
            "table",
            "drawing",
            "field",
            "comment",
            "revision",
            "hidden_text",
            "relationship",
        ),
        required_closures=(
            "disclosure period, organization, and report-type material schema",
            "section/table/attachment inventory profile",
            "board-review and public-release delivery presets",
            "archive manifest and evidence report",
            "audit/legal disclosure boundary in UI and reports",
        ),
        boundaries=(
            "does not perform audit or assurance judgment",
            "does not decide regulated disclosure completeness",
            "does not replace legal, finance, or exchange filing review",
        ),
    ),
)

PLANNED_SCENE_FAMILY_MAP: dict[str, PlannedSceneFamily] = {
    family.family_id: family for family in PLANNED_SCENE_FAMILIES
}


def list_planned_scene_families(
    *, priority: str | None = None
) -> tuple[PlannedSceneFamily, ...]:
    """Return planned scene families, optionally filtered by priority."""

    if priority is None:
        return PLANNED_SCENE_FAMILIES
    normalized = str(priority or "").strip().upper()
    return tuple(
        family
        for family in PLANNED_SCENE_FAMILIES
        if family.priority.upper() == normalized
    )


def get_planned_scene_family(family_id: str) -> PlannedSceneFamily:
    """Look up one planned scene family by id."""

    normalized = str(family_id or "").strip()
    try:
        return PLANNED_SCENE_FAMILY_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown planned scene family: {family_id}") from exc


def build_planned_scene_family_summary(family: PlannedSceneFamily) -> str:
    """Build a compact audit summary for planning and tests."""

    domains = "/".join(family.capability_domains[:3])
    workflows = "/".join(family.workflow_archetypes[:3])
    deliveries = "/".join(family.delivery_presets[:3])
    return (
        f"{family.family_id} [{family.priority}] -> {family.intended_landing}; "
        f"profile={family.default_profile_id}; maturity={family.maturity_level}; "
        f"domains={domains}; workflows={workflows}; "
        f"delivery={deliveries}; navigation={family.expose_in_navigation}"
    )


__all__ = [
    "PLANNED_SCENE_FAMILIES",
    "PLANNED_SCENE_FAMILY_MAP",
    "PlannedSceneFamily",
    "build_planned_scene_family_summary",
    "get_planned_scene_family",
    "list_planned_scene_families",
]
