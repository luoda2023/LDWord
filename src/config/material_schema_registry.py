"""Planning-level material schema registry.

This registry gives scene families a shared vocabulary for the canonical
material fields and resource roles they need.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MaterialFieldSpec:
    """One field required or recommended by a material schema."""

    key: str
    label: str
    required: bool = True
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MaterialAssetRoleSpec:
    """One explicitly typed content, image, or attachment role.

    ``accepted_types`` describes file formats only; it must never be used to
    infer whether the file enters the inline-image pipeline or the delivery
    attachment pipeline.  ``material_domain`` owns that routing decision.
    """

    role: str
    label: str
    required: bool = True
    accepted_types: tuple[str, ...] = ("image",)
    archive_dir: str = ""
    cardinality: str = "single"
    source_kind: str = "file"
    recursive: bool = False
    min_items: int = 0
    max_items: int | None = 1
    order_policy: str = "natural_path"
    naming_template: str = "{role}_{sequence:03d}"
    material_domain: str = "image"

    def __post_init__(self) -> None:
        domain = str(self.material_domain or "").strip().casefold()
        if domain not in {"content", "image", "attachment"}:
            raise ValueError(
                "material_domain must be content, image, or attachment"
            )
        accepted_types = tuple(
            str(item or "").strip().casefold()
            for item in tuple(self.accepted_types or ())
            if str(item or "").strip()
        )
        if not accepted_types:
            raise ValueError("accepted_types must not be empty")
        if domain == "image" and accepted_types != ("image",):
            raise ValueError(
                "image material roles may only declare accepted_types=('image',)"
            )
        object.__setattr__(self, "material_domain", domain)
        object.__setattr__(self, "accepted_types", accepted_types)

    @property
    def is_attachment(self) -> bool:
        return self.material_domain == "attachment"


@dataclass(frozen=True, slots=True)
class MaterialSchema:
    """Planning contract for one reusable material package shape."""

    schema_id: str
    label: str
    family: str
    description: str
    fields: tuple[MaterialFieldSpec, ...] = ()
    asset_roles: tuple[MaterialAssetRoleSpec, ...] = ()
    batch_mode: str = "single"
    boundaries: tuple[str, ...] = ()
    version: str = "v1"
    aliases: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()

    @property
    def required_field_keys(self) -> tuple[str, ...]:
        return tuple(field.key for field in self.fields if field.required)

    @property
    def required_asset_roles(self) -> tuple[str, ...]:
        return tuple(role.role for role in self.asset_roles if role.required)


@dataclass(frozen=True, slots=True)
class MaterialRequirements:
    """Resolved field and asset-role requirements for one schema use."""

    schema_id: str = ""
    schema_label: str = ""
    schema_ids: tuple[str, ...] = ()
    schema_labels: tuple[str, ...] = ()
    required_field_keys: tuple[str, ...] = ()
    required_asset_roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MaterialRequirementCheck:
    """Missing-field / missing-asset report for one material payload."""

    requirements: MaterialRequirements
    missing_field_keys: tuple[str, ...] = ()
    missing_asset_roles: tuple[str, ...] = ()

    @property
    def is_satisfied(self) -> bool:
        return not self.missing_field_keys and not self.missing_asset_roles


@dataclass(frozen=True, slots=True)
class MaterialSchemaRecommendation:
    """Auditable suggestion for repairing an unknown material schema id."""

    schema_id: str
    score: int
    reasons: tuple[str, ...] = ()


MATERIAL_SCHEMAS: tuple[MaterialSchema, ...] = (
    MaterialSchema(
        schema_id="generic_document_v1",
        label="Generic document materials",
        family="custom",
        description="User-defined fields and optional resources for general documents.",
        # General-document fields are package-owned declarations.  Keeping a
        # fixed English starter inventory here made every new custom package
        # expose six unrelated rows and prevented the field editor from
        # behaving like the other freely authored material domains.
        fields=(),
        asset_roles=(
            MaterialAssetRoleSpec("logo", "Logo", required=False),
            MaterialAssetRoleSpec(
                "attachment",
                "Attachment",
                required=False,
                accepted_types=("docx", "pdf", "xlsx", "zip"),
                cardinality="multiple",
                max_items=None,
                material_domain="attachment",
            ),
        ),
        boundaries=(
            "does not infer document placement from resource roles",
            "does not require optional fields or resources for no-material runs",
        ),
    ),
    MaterialSchema(
        schema_id="bid_materials_v1",
        label="Bidding materials",
        family="bidding",
        description="Company, project, seal, and logo materials for bid documents.",
        fields=(
            MaterialFieldSpec("company_name", "Company name"),
            MaterialFieldSpec("project_name", "Project name"),
            MaterialFieldSpec("legal_person", "Legal representative"),
            MaterialFieldSpec("bid_date", "Bid date", required=False),
            MaterialFieldSpec("address", "Company address", required=False),
            MaterialFieldSpec("consortium_lead", "Consortium lead", required=False),
            MaterialFieldSpec("consortium_members", "Consortium members", required=False),
            MaterialFieldSpec("consortium_roles", "Consortium member roles", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("logo", "Company logo"),
            MaterialAssetRoleSpec("seal", "Company seal"),
            MaterialAssetRoleSpec(
                "qualification",
                "Qualification certificate",
                required=False,
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                max_items=None,
            ),
        ),
        batch_mode="multi_profile",
        boundaries=(
            "does not verify certificate authenticity",
            "does not judge bid strategy or legal validity",
            "does not judge consortium member qualification validity",
        ),
    ),
    MaterialSchema(
        schema_id="official_document_v1",
        label="Official document fields",
        family="official",
        description="Administrative fields for official documents and notices.",
        fields=(
            MaterialFieldSpec("title", "Document title"),
            MaterialFieldSpec("body", "Document body"),
            MaterialFieldSpec("organization", "Organization"),
            MaterialFieldSpec("document_no", "Document number"),
            MaterialFieldSpec("issue_date", "Issue date"),
            MaterialFieldSpec("issuer", "Issuer", required=False),
            MaterialFieldSpec("recipient", "Recipient", required=False),
            MaterialFieldSpec("attachment_note", "Attachment note", required=False),
            MaterialFieldSpec("document_type", "Document type", required=False),
            MaterialFieldSpec("security_level", "Security level", required=False),
            MaterialFieldSpec("urgency", "Urgency", required=False),
            MaterialFieldSpec("signer", "Signer", required=False),
            MaterialFieldSpec("copy_scope", "Copy scope", required=False),
            MaterialFieldSpec("printing_org", "Printing organization", required=False),
            MaterialFieldSpec("printing_date", "Printing date", required=False),
            MaterialFieldSpec("archive_status", "Archive status", required=False),
            MaterialFieldSpec("archive_no", "Archive number", required=False),
            MaterialFieldSpec("retention_period", "Retention period", required=False),
            MaterialFieldSpec("meeting_title", "Meeting title", required=False),
            MaterialFieldSpec("meeting_date", "Meeting date", required=False),
            MaterialFieldSpec("participants", "Participants", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("seal", "Official seal", required=False),
        ),
        boundaries=(
            "does not own official page layout details",
            "does not validate administrative decision substance",
            "does not certify official release validity or replace archive-office approval",
        ),
    ),
    MaterialSchema(
        schema_id="technical_document_v1",
        label="Technical document materials",
        family="technical",
        description="Version fields and diagram roles for technical documents.",
        fields=(
            MaterialFieldSpec("document_title", "Document title", required=False),
            MaterialFieldSpec("version", "Version", required=False),
            MaterialFieldSpec("owner", "Owner", required=False),
            MaterialFieldSpec("index_scope", "Index scope", required=False),
            MaterialFieldSpec("appendix_scope", "Appendix scope", required=False),
            MaterialFieldSpec("source_file_manifest", "Source file manifest", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec(
                "diagram",
                "Technical diagram",
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                min_items=1,
                max_items=None,
            ),
            MaterialAssetRoleSpec(
                "figure",
                "Figure",
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                min_items=1,
                max_items=None,
            ),
        ),
        boundaries=(
            "does not verify technical correctness",
            "does not rewrite fragile embedded technical objects",
            "does not promise lossless multi-file merge or index rebuild without review",
        ),
    ),
    MaterialSchema(
        schema_id="engineering_document_v1",
        label="Engineering document materials",
        family="engineering",
        description=(
            "Stage fields and reference roles for engineering documents: "
            "project, scale, stage, cost and source files."
        ),
        fields=(
            MaterialFieldSpec("project_name", "Project name"),
            MaterialFieldSpec("project_location", "Project location", required=False),
            MaterialFieldSpec("project_scale", "Project scale", required=False),
            MaterialFieldSpec("engineering_stage", "Engineering stage"),
            MaterialFieldSpec("doc_kind", "Document kind"),
            MaterialFieldSpec("design_org", "Design organization", required=False),
            MaterialFieldSpec("owner_org", "Owner organization", required=False),
            MaterialFieldSpec("invest_estimate", "Investment estimate", required=False),
            MaterialFieldSpec("currency", "Currency", required=False),
            MaterialFieldSpec("cost_standard", "Cost standard", required=False),
            MaterialFieldSpec("info_price_month", "Information price month", required=False),
            MaterialFieldSpec("version", "Version", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec(
                "reference_doc",
                "Reference document",
                required=False,
                cardinality="multiple",
                accepted_types=("docx", "pdf", "xlsx", "zip"),
                material_domain="attachment",
                max_items=None,
            ),
            MaterialAssetRoleSpec("diagram", "Engineering diagram", required=False, cardinality="multiple", max_items=None),
            MaterialAssetRoleSpec("logo", "Organization logo", required=False),
        ),
        batch_mode="single",
        boundaries=(
            "does not verify engineering cost correctness",
            "does not certify budget or tender legality",
            "does not replace licensed engineer review or statutory approval",
        ),
    ),
    MaterialSchema(
        schema_id="journal_materials_v1",
        label="Journal materials legacy profile",
        family="journal_en",
        description="Legacy journal material schema id used by scene import tests.",
        fields=(
            MaterialFieldSpec("author", "Author"),
            MaterialFieldSpec("affiliation", "Affiliation"),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("graphical_abstract", "Graphical abstract"),
        ),
        boundaries=(
            "does not promise publisher-final layout",
        ),
    ),
    MaterialSchema(
        schema_id="thesis_school_rule_context_v1",
        label="Thesis school rule context",
        family="thesis_cn",
        description=(
            "Reviewed school-rule source selection and section-classifier "
            "confirmation context for Chinese thesis checks."
        ),
        fields=(
            MaterialFieldSpec("school_rule_source_id", "School rule source id"),
            MaterialFieldSpec(
                "section_classifier_decisions",
                "Section classifier decisions",
            ),
            MaterialFieldSpec("school_name", "School name", required=False),
            MaterialFieldSpec("rule_source_version", "Rule source version", required=False),
            MaterialFieldSpec("reviewed_by", "Rule reviewer", required=False),
            MaterialFieldSpec("reviewed_on", "Rule reviewed date", required=False),
            MaterialFieldSpec("confirmed_by", "Classifier confirmer", required=False),
            MaterialFieldSpec("confirmed_at", "Classifier confirmation time", required=False),
        ),
        batch_mode="review_context",
        boundaries=(
            "does not make local defaults authoritative for every school",
            "does not execute strict school compliance without reviewed rule data",
            "does not auto-classify ambiguous thesis sections without confirmation",
        ),
        aliases=("school_thesis_rules_v1", "thesis_section_classifier_v1"),
    ),
    MaterialSchema(
        schema_id="journal_submission_materials_v1",
        label="Journal submission materials",
        family="journal_en",
        description="Submission metadata, declarations, and display items.",
        fields=(
            MaterialFieldSpec("article_title", "Article title"),
            MaterialFieldSpec("author", "Author"),
            MaterialFieldSpec("affiliation", "Affiliation"),
            MaterialFieldSpec("corresponding_author", "Corresponding author"),
            MaterialFieldSpec("journal_name", "Journal name", required=False),
            MaterialFieldSpec(
                "target_journal_profile_id",
                "Target journal profile id",
                required=False,
            ),
            MaterialFieldSpec(
                "reviewed_rule_source_id",
                "Reviewed rule source id",
                required=False,
            ),
            MaterialFieldSpec(
                "submission_package_manifest",
                "Submission package manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "citation_source_manifest",
                "Citation source manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "publisher_boundary_note",
                "Publisher boundary note",
                required=False,
            ),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("graphical_abstract", "Graphical abstract", required=False),
            MaterialAssetRoleSpec("cover_image", "Cover image", required=False),
        ),
        boundaries=(
            "does not fetch journal rules without reviewed profile updates",
            "does not promise publisher-final layout",
        ),
    ),
    MaterialSchema(
        schema_id="exam_items_v1",
        label="Exam item data",
        family="exam_teaching",
        description="Structured paper and question metadata for exam rendering.",
        fields=(
            MaterialFieldSpec("paper_title", "Paper title"),
            MaterialFieldSpec("subject", "Subject"),
            MaterialFieldSpec("grade", "Grade"),
            MaterialFieldSpec("duration", "Duration"),
            MaterialFieldSpec("total_score", "Total score"),
        ),
        asset_roles=(
            MaterialAssetRoleSpec(
                "question_figure",
                "Question figure",
                required=False,
                cardinality="multiple",
                source_kind="files",
                max_items=None,
                order_policy="metadata",
            ),
        ),
        batch_mode="structured_source",
        boundaries=(
            "does not validate AI-generated content quality",
            "does not generate complex geometry diagrams in core",
        ),
    ),
    MaterialSchema(
        schema_id="teaching_assets_v1",
        label="Teaching assets",
        family="exam_teaching",
        description="Course and handout assets shared by teaching materials.",
        fields=(
            MaterialFieldSpec("course_name", "Course name"),
            MaterialFieldSpec("teacher_name", "Teacher name", required=False),
            MaterialFieldSpec("class_name", "Class name", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("handout_cover", "Handout cover", required=False),
            MaterialAssetRoleSpec(
                "teaching_diagram",
                "Teaching diagram",
                required=False,
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                max_items=None,
            ),
        ),
        boundaries=(
            "does not make AI content generation a core scene capability",
        ),
    ),
    MaterialSchema(
        schema_id="project_application_materials_v1",
        label="Project application materials",
        family="project_application",
        description="Project, team, budget, and attachment metadata.",
        fields=(
            MaterialFieldSpec("project_name", "Project name"),
            MaterialFieldSpec("applicant_unit", "Applicant unit"),
            MaterialFieldSpec("principal_investigator", "Principal investigator"),
            MaterialFieldSpec("budget_total", "Budget total", required=False),
            MaterialFieldSpec("submission_system_id", "Submission system id", required=False),
            MaterialFieldSpec(
                "submission_rule_source_id",
                "Submission rule source id",
                required=False,
            ),
            MaterialFieldSpec(
                "submission_system_status",
                "Submission system status",
                required=False,
            ),
            MaterialFieldSpec(
                "external_submission_boundary_note",
                "External submission boundary note",
                required=False,
            ),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("seal", "Applicant seal", required=False),
            MaterialAssetRoleSpec(
                "application_form",
                "Application form",
                accepted_types=("pdf", "image", "docx"),
                material_domain="attachment",
            ),
            MaterialAssetRoleSpec(
                "budget_sheet",
                "Budget sheet",
                accepted_types=("pdf", "image", "xlsx"),
                material_domain="attachment",
            ),
            MaterialAssetRoleSpec(
                "team_resume",
                "Team resume",
                required=False,
                accepted_types=("pdf", "image", "docx"),
                material_domain="attachment",
            ),
            MaterialAssetRoleSpec(
                "supporting_proof",
                "Supporting proof",
                required=False,
                accepted_types=("pdf", "image"),
                material_domain="attachment",
            ),
            MaterialAssetRoleSpec(
                "attachment",
                "Attachment",
                required=False,
                accepted_types=("image", "pdf"),
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                max_items=None,
                material_domain="attachment",
            ),
        ),
        batch_mode="attachment_package",
        boundaries=(
            "does not replace external submission systems",
            "does not verify attachment truthfulness",
        ),
    ),
    MaterialSchema(
        schema_id="contract_parties_v1",
        label="Contract party fields",
        family="contract_delivery",
        description="Repeated party, amount, and date fields for contracts.",
        fields=(
            MaterialFieldSpec("party_a", "Party A"),
            MaterialFieldSpec("party_b", "Party B"),
            MaterialFieldSpec("contract_amount", "Contract amount"),
            MaterialFieldSpec("signing_date", "Signing date"),
            MaterialFieldSpec("contract_no", "Contract number", required=False),
        ),
        boundaries=(
            "does not provide legal advice",
            "does not judge clause validity",
        ),
    ),
    MaterialSchema(
        schema_id="signature_assets_v1",
        label="Signature and seal assets",
        family="contract_delivery",
        description="Seal and signature images for signing packages.",
        asset_roles=(
            MaterialAssetRoleSpec("seal", "Seal"),
            MaterialAssetRoleSpec("legal_signature", "Legal representative signature", required=False),
            MaterialAssetRoleSpec("agent_signature", "Agent signature", required=False),
        ),
        boundaries=(
            "does not verify signature authenticity",
        ),
        aliases=("signature_assets_v2", "signing_assets_v1"),
        supersedes=("signature_assets_legacy_v1",),
    ),
    MaterialSchema(
        schema_id="personnel_records_v1",
        label="Personnel records",
        family="hr_batch_documents",
        description="One-record-one-output fields for HR batch documents.",
        fields=(
            MaterialFieldSpec("employee_name", "Employee name"),
            MaterialFieldSpec("employee_id", "Employee id"),
            MaterialFieldSpec("department", "Department", required=False),
            MaterialFieldSpec("position", "Position", required=False),
            MaterialFieldSpec("effective_date", "Effective date", required=False),
            MaterialFieldSpec(
                "fixed_layout_profile_id",
                "Fixed-layout profile id",
                required=False,
            ),
            MaterialFieldSpec(
                "profile_preview_manifest",
                "Profile-specific preview manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "source_row_manifest",
                "Source row manifest",
                required=False,
            ),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("portrait", "Portrait", required=False),
            MaterialAssetRoleSpec("signature", "Signature", required=False),
        ),
        batch_mode="multi_profile",
        boundaries=(
            "does not verify personnel qualification or background truthfulness",
            "does not merge failed records into successful outputs",
        ),
    ),
    MaterialSchema(
        schema_id="administrative_meeting_fields_v1",
        label="Meeting and policy fields",
        family="meeting_policy_documents",
        description="Meeting, agenda, participant, and archive fields.",
        fields=(
            MaterialFieldSpec("organization", "Organization"),
            MaterialFieldSpec("meeting_title", "Meeting title"),
            MaterialFieldSpec("meeting_date", "Meeting date"),
            MaterialFieldSpec("participants", "Participants", required=False),
            MaterialFieldSpec("document_no", "Document number", required=False),
            MaterialFieldSpec("issuer", "Issuer", required=False),
            MaterialFieldSpec("document_type", "Document type", required=False),
            MaterialFieldSpec("security_level", "Security level", required=False),
            MaterialFieldSpec("copy_scope", "Copy scope", required=False),
            MaterialFieldSpec("archive_status", "Archive status", required=False),
            MaterialFieldSpec("archive_no", "Archive number", required=False),
            MaterialFieldSpec("retention_period", "Retention period", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("seal", "Official seal", required=False),
        ),
        boundaries=(
            "does not validate administrative decision substance",
            "does not certify official release validity or replace archive-office approval",
        ),
    ),
    MaterialSchema(
        schema_id="product_assets_v1",
        label="Product assets",
        family="product_sales_documents",
        description="Product specifications and images for manuals and pre-sales docs.",
        fields=(
            MaterialFieldSpec("product_name", "Product name"),
            MaterialFieldSpec("product_version", "Product version", required=False),
            MaterialFieldSpec("product_model", "Product model", required=False),
            MaterialFieldSpec("asset_source_manifest", "Asset source manifest", required=False),
            MaterialFieldSpec(
                "asset_consistency_policy",
                "Asset consistency policy",
                required=False,
            ),
            MaterialFieldSpec(
                "customer_internal_version_policy",
                "Customer/internal version policy",
                required=False,
            ),
            MaterialFieldSpec("quote_boundary_signal", "Quote boundary signal", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec(
                "product_image",
                "Product image",
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                min_items=1,
                max_items=None,
            ),
            MaterialAssetRoleSpec(
                "diagram",
                "Product diagram",
                required=False,
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                max_items=None,
            ),
        ),
        boundaries=(
            "does not promise marketing copy quality",
        ),
    ),
    MaterialSchema(
        schema_id="case_study_assets_v1",
        label="Case study assets",
        family="product_sales_documents",
        description="Customer case metadata and supporting images.",
        fields=(
            MaterialFieldSpec("customer_name", "Customer name"),
            MaterialFieldSpec("case_title", "Case title"),
            MaterialFieldSpec("case_evidence_source", "Case evidence source", required=False),
            MaterialFieldSpec("case_approval_status", "Case approval status", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec(
                "case_image",
                "Case image",
                required=False,
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                max_items=None,
            ),
        ),
        boundaries=(
            "does not verify customer claim truthfulness",
        ),
    ),
    MaterialSchema(
        schema_id="long_document_metadata_v1",
        label="Long document metadata",
        family="long_document_publishing",
        description="Book, manual, or chapter collection metadata.",
        fields=(
            MaterialFieldSpec("title", "Title"),
            MaterialFieldSpec("author", "Author", required=False),
            MaterialFieldSpec("editor", "Editor", required=False),
            MaterialFieldSpec("version", "Version", required=False),
            MaterialFieldSpec("index_scope", "Index scope", required=False),
            MaterialFieldSpec("appendix_scope", "Appendix scope", required=False),
            MaterialFieldSpec("source_file_manifest", "Source file manifest", required=False),
            MaterialFieldSpec("merge_boundary_notes", "Merge boundary notes", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("cover", "Cover image", required=False),
        ),
        batch_mode="chapter_collection",
        boundaries=(
            "does not replace publisher layout systems",
            "does not promise lossless multi-document merge yet",
        ),
    ),
    MaterialSchema(
        schema_id="form_batch_fields_v1",
        label="Form batch fields",
        family="form_batch_documents",
        description="Fixed-layout form fields for one-record-one-output batch filling.",
        fields=(
            MaterialFieldSpec("form_title", "Form title"),
            MaterialFieldSpec("record_id", "Record id"),
            MaterialFieldSpec("applicant_name", "Applicant name"),
            MaterialFieldSpec("organization", "Organization", required=False),
            MaterialFieldSpec("issue_date", "Issue date", required=False),
            MaterialFieldSpec(
                "fixed_layout_profile_id",
                "Fixed-layout profile id",
                required=False,
            ),
            MaterialFieldSpec(
                "answer_sheet_reuse_profile_id",
                "Answer-sheet reuse profile id",
                required=False,
            ),
            MaterialFieldSpec(
                "placeholder_residue_policy",
                "Placeholder residue policy",
                required=False,
            ),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("seal", "Seal", required=False),
            MaterialAssetRoleSpec("signature", "Signature", required=False),
        ),
        batch_mode="multi_profile",
        boundaries=(
            "does not replace professional form systems",
            "does not judge submitted data truthfulness",
        ),
    ),
    MaterialSchema(
        schema_id="qualification_archive_assets_v1",
        label="Qualification archive assets",
        family="qualification_archive_packages",
        description="Certificate, license, and attachment inventory for bid or project packages.",
        fields=(
            MaterialFieldSpec("organization", "Organization"),
            MaterialFieldSpec("package_name", "Package name"),
            MaterialFieldSpec("project_name", "Project name", required=False),
            MaterialFieldSpec("certificate_no", "Certificate number", required=False),
            MaterialFieldSpec("license_no", "Business license number", required=False),
            MaterialFieldSpec("valid_from", "Valid from", required=False),
            MaterialFieldSpec("valid_until", "Valid until", required=False),
            MaterialFieldSpec("consortium_member_name", "Consortium member name", required=False),
            MaterialFieldSpec("consortium_member_role", "Consortium member role", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec(
                "certificate",
                "Qualification certificate",
                accepted_types=("image", "pdf"),
                archive_dir="01_certificates",
                material_domain="attachment",
            ),
            MaterialAssetRoleSpec(
                "business_license",
                "Business license",
                accepted_types=("image", "pdf"),
                archive_dir="02_business_license",
                material_domain="attachment",
            ),
            MaterialAssetRoleSpec(
                "attachment",
                "Supporting attachment",
                required=False,
                accepted_types=("image", "pdf"),
                archive_dir="99_supporting_attachments",
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                max_items=None,
                material_domain="attachment",
            ),
        ),
        batch_mode="attachment_package",
        boundaries=(
            "does not verify certificate authenticity",
            "does not judge qualification validity",
            "does not decide whether expired metadata is acceptable for submission",
            "does not judge consortium member qualification validity",
        ),
        aliases=("qualification_certificate_v2", "qualification_assets_v1"),
        supersedes=("qualification_archive_legacy_v1",),
    ),
    MaterialSchema(
        schema_id="finance_quote_fields_v1",
        label="Finance and quote fields",
        family="finance_quote_documents",
        description="Quotation, budget, and attachment metadata.",
        fields=(
            MaterialFieldSpec("customer_name", "Customer name"),
            MaterialFieldSpec("quote_no", "Quote number"),
            MaterialFieldSpec("amount", "Amount"),
            MaterialFieldSpec("currency", "Currency", required=False),
            MaterialFieldSpec("issue_date", "Issue date", required=False),
            MaterialFieldSpec(
                "quote_source_workbook_id",
                "Quote source workbook id",
                required=False,
            ),
            MaterialFieldSpec(
                "spreadsheet_table_mapping_manifest",
                "Spreadsheet table mapping manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "attachment_inventory_manifest",
                "Attachment inventory manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "finance_plugin_handoff_status",
                "Finance plugin handoff status",
                required=False,
            ),
            MaterialFieldSpec(
                "financial_boundary_note",
                "Financial boundary note",
                required=False,
            ),
        ),
        asset_roles=(
            MaterialAssetRoleSpec("seal", "Seal", required=False),
            MaterialAssetRoleSpec(
                "source_workbook",
                "Source workbook",
                required=False,
                accepted_types=("xlsx",),
                material_domain="attachment",
            ),
            MaterialAssetRoleSpec(
                "attachment",
                "Attachment",
                required=False,
                accepted_types=("image", "pdf"),
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                max_items=None,
                material_domain="attachment",
            ),
        ),
        batch_mode="attachment_package",
        boundaries=(
            "does not perform financial audit judgment",
            "does not verify quotation correctness",
            "spreadsheet table mapping is evidence, not finance assurance",
            "finance plugin handoff remains explicit before professional judgment",
        ),
    ),
    MaterialSchema(
        schema_id="patent_document_fields_v1",
        label="Patent document fields",
        family="ip_patent_documents",
        description="Patent disclosure, specification, and figure metadata.",
        fields=(
            MaterialFieldSpec("invention_title", "Invention title"),
            MaterialFieldSpec("applicant", "Applicant"),
            MaterialFieldSpec("inventor", "Inventor", required=False),
            MaterialFieldSpec("technical_field", "Technical field", required=False),
            MaterialFieldSpec(
                "claim_outline_manifest",
                "Claim outline manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "figure_number_inventory",
                "Figure number inventory",
                required=False,
            ),
            MaterialFieldSpec(
                "claim_quality_boundary_note",
                "Claim quality boundary note",
                required=False,
            ),
            MaterialFieldSpec(
                "ip_plugin_handoff_status",
                "IP plugin handoff status",
                required=False,
            ),
            MaterialFieldSpec("review_owner", "Review owner", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec(
                "figure",
                "Patent figure",
                required=False,
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                max_items=None,
            ),
        ),
        boundaries=(
            "does not promise patent legal quality",
            "does not judge claim validity or infringement risk",
            "claim-quality boundary UI must not imply patentability review",
            "IP plugin handoff remains explicit before professional judgment",
        ),
    ),
    MaterialSchema(
        schema_id="bilingual_terms_v1",
        label="Bilingual terminology and review fields",
        family="bilingual_translation_documents",
        description="Language pair, terminology, and reviewer fields for bilingual review packages.",
        fields=(
            MaterialFieldSpec("source_language", "Source language"),
            MaterialFieldSpec("target_language", "Target language"),
            MaterialFieldSpec("document_title", "Document title"),
            MaterialFieldSpec("reviewer", "Reviewer", required=False),
            MaterialFieldSpec("termbase_name", "Termbase name", required=False),
            MaterialFieldSpec(
                "termbase_manifest",
                "Termbase manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "parallel_alignment_manifest",
                "Parallel alignment manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "unresolved_term_report_id",
                "Unresolved term report id",
                required=False,
            ),
            MaterialFieldSpec(
                "translation_quality_plugin_status",
                "Translation quality plugin status",
                required=False,
            ),
            MaterialFieldSpec(
                "translation_quality_boundary_note",
                "Translation quality boundary note",
                required=False,
            ),
        ),
        asset_roles=(
            MaterialAssetRoleSpec(
                "term_table",
                "Terminology table",
                required=False,
                accepted_types=("image", "pdf", "xlsx"),
                material_domain="attachment",
            ),
        ),
        boundaries=(
            "does not guarantee translation quality",
            "does not replace professional translation review",
            "termbase UI records evidence and unresolved terms only",
            "translation-quality plugin handoff remains explicit",
        ),
    ),
    MaterialSchema(
        schema_id="regulated_disclosure_materials_v1",
        label="Regulated disclosure materials",
        family="regulated_disclosure_documents",
        description="Organization, period, report type, and attachment metadata for annual, ESG, and disclosure packages.",
        fields=(
            MaterialFieldSpec("organization", "Organization"),
            MaterialFieldSpec("report_period", "Report period"),
            MaterialFieldSpec("report_type", "Report type"),
            MaterialFieldSpec("board_meeting_date", "Board meeting date", required=False),
            MaterialFieldSpec("public_release_date", "Public release date", required=False),
            MaterialFieldSpec(
                "regulated_rule_source_id",
                "Regulated rule source id",
                required=False,
            ),
            MaterialFieldSpec(
                "section_inventory_manifest",
                "Section inventory manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "table_attachment_inventory_manifest",
                "Table and attachment inventory manifest",
                required=False,
            ),
            MaterialFieldSpec(
                "assurance_boundary_note",
                "Assurance boundary note",
                required=False,
            ),
            MaterialFieldSpec(
                "external_filing_boundary_note",
                "External filing boundary note",
                required=False,
            ),
            MaterialFieldSpec("review_owner", "Review owner", required=False),
        ),
        asset_roles=(
            MaterialAssetRoleSpec(
                "table_source",
                "Table source",
                required=False,
                accepted_types=("xlsx", "pdf", "image"),
                material_domain="attachment",
            ),
            MaterialAssetRoleSpec(
                "disclosure_attachment",
                "Disclosure attachment",
                required=False,
                accepted_types=("pdf", "image"),
                cardinality="multiple",
                source_kind="directory",
                recursive=True,
                max_items=None,
                material_domain="attachment",
            ),
        ),
        batch_mode="attachment_package",
        boundaries=(
            "does not perform audit or assurance judgment",
            "does not decide regulated disclosure completeness",
            "regulated rule-source governance is evidence, not filing advice",
            "assurance boundary UI must route professional review explicitly",
        ),
    ),
)

MATERIAL_SCHEMA_MAP: dict[str, MaterialSchema] = {
    schema.schema_id: schema for schema in MATERIAL_SCHEMAS
}


def list_material_schemas(*, family: str | None = None) -> tuple[MaterialSchema, ...]:
    """Return material schemas, optionally filtered by family id."""

    if family is None:
        return MATERIAL_SCHEMAS
    normalized = str(family or "").strip()
    return tuple(schema for schema in MATERIAL_SCHEMAS if schema.family == normalized)


def get_material_schema(schema_id: str) -> MaterialSchema:
    """Look up a material schema by id."""

    normalized = str(schema_id or "").strip()
    try:
        return MATERIAL_SCHEMA_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown material schema: {schema_id}") from exc


def missing_material_schema_ids(schema_ids: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Return schema ids that are referenced but not registered."""

    return tuple(
        schema_id
        for schema_id in schema_ids
        if str(schema_id or "").strip() not in MATERIAL_SCHEMA_MAP
    )


def resolve_material_schema_ids(
    schema_id: str = "",
    schema_ids: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Return unique schema ids, preserving the legacy primary id first."""

    return _unique_values([schema_id, *(schema_ids or ())])


_SCHEMA_RECOMMENDATION_STOP_TOKENS = {
    "schema",
    "schemas",
    "material",
    "materials",
    "missing",
    "primary",
    "extra",
    "unknown",
}


def recommend_material_schema_replacement(
    missing_schema_ids: Sequence[str],
    *,
    family_hints: Sequence[str] | None = None,
    existing_schema_ids: Sequence[str] | None = None,
) -> MaterialSchemaRecommendation | None:
    """Suggest a registered schema to replace unknown schema ids.

    The score favors explicit family hints, families already present in valid
    schema ids, and token similarity to the unknown ids. This is intentionally
    deterministic so UI repairs and tests can audit the recommendation.
    """

    missing_ids = _unique_values(list(missing_schema_ids or []))
    if not missing_ids:
        return None
    hinted_families = {
        str(value or "").strip()
        for value in list(family_hints or [])
        if str(value or "").strip()
    }
    for schema_id in list(existing_schema_ids or []):
        schema = MATERIAL_SCHEMA_MAP.get(str(schema_id or "").strip())
        if schema is not None and schema.family:
            hinted_families.add(schema.family)
    missing_tokens = _schema_recommendation_tokens(*missing_ids)
    best: MaterialSchemaRecommendation | None = None
    best_rank: tuple[int, int] = (0, 0)
    for index, schema in enumerate(MATERIAL_SCHEMAS):
        score = 0
        reasons: list[str] = []
        alias_hits = tuple(
            missing_id for missing_id in missing_ids if missing_id in schema.aliases
        )
        if alias_hits:
            score += 500 * len(alias_hits)
            reasons.append("alias:" + ",".join(alias_hits))
        supersedes_hits = tuple(
            missing_id for missing_id in missing_ids if missing_id in schema.supersedes
        )
        if supersedes_hits:
            score += 450 * len(supersedes_hits)
            reasons.append("supersedes:" + ",".join(supersedes_hits))
        if schema.family in hinted_families:
            score += 100
            reasons.append(f"family:{schema.family}")
        candidate_tokens = _schema_recommendation_tokens(
            schema.schema_id,
            schema.label,
            schema.description,
            schema.family,
            *schema.aliases,
            *schema.supersedes,
        )
        token_overlap = tuple(sorted(missing_tokens & candidate_tokens))
        if token_overlap:
            score += 20 * len(token_overlap)
            reasons.append("tokens:" + ",".join(token_overlap))
        if any(
            schema.schema_id.startswith(missing_id.rsplit("_", 1)[0])
            for missing_id in missing_ids
            if "_" in missing_id
        ):
            score += 10
            reasons.append("prefix")
        rank = (score, -index)
        if score > 0 and rank > best_rank:
            best_rank = rank
            best = MaterialSchemaRecommendation(
                schema_id=schema.schema_id,
                score=score,
                reasons=tuple(reasons),
            )
    return best


def build_material_requirements(
    schema_id: str = "",
    *,
    schema_ids: Sequence[str] | None = None,
    extra_required_fields: Sequence[str] | None = None,
    extra_required_asset_roles: Sequence[str] | None = None,
) -> MaterialRequirements:
    """Resolve schema-driven requirements plus scene/profile overrides."""

    resolved_schema_ids = resolve_material_schema_ids(schema_id, schema_ids)
    schemas = [
        MATERIAL_SCHEMA_MAP[schema_id]
        for schema_id in resolved_schema_ids
        if schema_id in MATERIAL_SCHEMA_MAP
    ]
    primary_id = resolved_schema_ids[0] if resolved_schema_ids else ""
    primary_schema = MATERIAL_SCHEMA_MAP.get(primary_id)
    return MaterialRequirements(
        schema_id=primary_id,
        schema_label=primary_schema.label if primary_schema is not None else primary_id,
        schema_ids=resolved_schema_ids,
        schema_labels=tuple(schema.label for schema in schemas),
        required_field_keys=_unique_values(
            [
                *(key for schema in schemas for key in schema.required_field_keys),
                *(extra_required_fields or ()),
            ]
        ),
        required_asset_roles=_unique_values(
            [
                *(role for schema in schemas for role in schema.required_asset_roles),
                *(extra_required_asset_roles or ()),
            ]
        ),
    )


def evaluate_material_requirements(
    *,
    schema_id: str = "",
    schema_ids: Sequence[str] | None = None,
    entity_data: Mapping[str, object] | None = None,
    asset_roles: Sequence[str] | None = None,
    extra_required_fields: Sequence[str] | None = None,
    extra_required_asset_roles: Sequence[str] | None = None,
) -> MaterialRequirementCheck:
    """Evaluate missing required fields and asset roles for a material payload."""

    requirements = build_material_requirements(
        schema_id,
        schema_ids=schema_ids,
        extra_required_fields=extra_required_fields,
        extra_required_asset_roles=extra_required_asset_roles,
    )
    data = entity_data if isinstance(entity_data, Mapping) else {}
    present_fields = {
        str(key).strip()
        for key, value in data.items()
        if str(key or "").strip() and str(value or "").strip()
    }
    present_fields.update(_nested_exam_material_fields(requirements.schema_ids, data))
    present_assets = {
        _normalize_key(role)
        for role in (asset_roles or ())
        if _normalize_key(role)
    }
    return MaterialRequirementCheck(
        requirements=requirements,
        missing_field_keys=tuple(
            key for key in requirements.required_field_keys if key not in present_fields
        ),
        missing_asset_roles=tuple(
            role for role in requirements.required_asset_roles if role not in present_assets
        ),
    )


def build_material_schema_summary(schema: MaterialSchema) -> str:
    """Build a compact audit summary for docs and tests."""

    required_fields = len(schema.required_field_keys)
    required_assets = len(schema.required_asset_roles)
    return (
        f"{schema.schema_id} [{schema.family}] -> fields={required_fields}; "
        f"assets={required_assets}; batch={schema.batch_mode}"
    )


def _unique_values(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = _normalize_key(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _normalize_key(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _nested_exam_material_fields(
    schema_ids: Sequence[str],
    entity_data: Mapping[str, object],
) -> set[str]:
    """Treat structured exam payload metadata as satisfying exam material fields."""

    if "exam_items_v1" not in set(schema_ids):
        return set()
    payload = _coerce_exam_payload(entity_data.get("exam_items"))
    if payload is None:
        for key in ("paper_json", "questions", "sections"):
            payload = _coerce_exam_payload(entity_data.get(key))
            if payload is not None:
                break
    if payload is None:
        return set()
    candidates: dict[str, object] = {}
    if isinstance(payload, Mapping):
        candidates.update(payload)
        paper = payload.get("paper")
        if isinstance(paper, Mapping):
            candidates.update(paper)
        metadata = payload.get("metadata")
        if isinstance(metadata, Mapping):
            candidates.update(metadata)
    return {
        key
        for key in ("paper_title", "subject", "grade", "duration", "total_score")
        if str(candidates.get(key) or "").strip()
    }


def _coerce_exam_payload(value: object) -> object | None:
    if isinstance(value, (Mapping, list, tuple)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
            except (ValueError, SyntaxError, TypeError):
                continue
            if isinstance(parsed, (Mapping, list, tuple)):
                return parsed
    return None


def _schema_recommendation_tokens(*values) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower()):
            if (
                not token
                or token in _SCHEMA_RECOMMENDATION_STOP_TOKENS
                or re.fullmatch(r"v\d+", token)
            ):
                continue
            tokens.add(token)
    return tokens


__all__ = [
    "MATERIAL_SCHEMA_MAP",
    "MATERIAL_SCHEMAS",
    "MaterialAssetRoleSpec",
    "MaterialFieldSpec",
    "MaterialRequirementCheck",
    "MaterialRequirements",
    "MaterialSchema",
    "MaterialSchemaRecommendation",
    "build_material_schema_summary",
    "build_material_requirements",
    "evaluate_material_requirements",
    "get_material_schema",
    "list_material_schemas",
    "missing_material_schema_ids",
    "recommend_material_schema_replacement",
    "resolve_material_schema_ids",
]
