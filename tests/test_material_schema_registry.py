from src.config.material_schema_registry import (
    build_material_requirements,
    build_material_schema_summary,
    evaluate_material_requirements,
    get_material_schema,
    list_material_schemas,
    missing_material_schema_ids,
    recommend_material_schema_replacement,
    resolve_material_schema_ids,
)
from src.config.scene_family_registry import list_planned_scene_families
from src.ui.panels.workbench.scene_presets import SCENE_FACTORIES


def test_planned_scene_family_material_schema_ids_are_registered():
    referenced_ids = {
        schema_id
        for family in list_planned_scene_families()
        for schema_id in family.material_schema_ids
    }

    assert referenced_ids
    assert missing_material_schema_ids(sorted(referenced_ids)) == ()


def test_builtin_scene_material_schema_ids_are_registered():
    referenced_ids = {
        schema_id
        for factory in SCENE_FACTORIES.values()
        for scene in [factory()]
        for schema_id in [
            scene.input_source_profile.material_schema_id,
            *scene.input_source_profile.material_schema_ids,
        ]
        if schema_id
    }

    assert {
        "bid_materials_v1",
        "official_document_v1",
        "technical_document_v1",
        "thesis_school_rule_context_v1",
    } <= referenced_ids
    assert missing_material_schema_ids(sorted(referenced_ids)) == ()


def test_thesis_school_rule_context_schema_captures_rule_source_and_section_confirmation():
    schema = get_material_schema("thesis_school_rule_context_v1")

    assert schema.family == "thesis_cn"
    assert schema.batch_mode == "review_context"
    assert {
        "school_rule_source_id",
        "section_classifier_decisions",
    } <= set(schema.required_field_keys)
    assert {
        "school_name",
        "rule_source_version",
        "reviewed_by",
        "reviewed_on",
        "confirmed_by",
        "confirmed_at",
    } <= {field.key for field in schema.fields}
    assert "school_thesis_rules_v1" in schema.aliases
    assert any("local defaults" in item for item in schema.boundaries)
    assert any("strict school compliance" in item for item in schema.boundaries)


def test_journal_submission_schema_captures_reviewed_profile_and_artifact_manifest():
    schema = get_material_schema("journal_submission_materials_v1")

    assert schema.family == "journal_en"
    assert {
        "article_title",
        "author",
        "affiliation",
        "corresponding_author",
    } <= set(schema.required_field_keys)
    field_keys = {field.key for field in schema.fields}
    assert {
        "target_journal_profile_id",
        "reviewed_rule_source_id",
        "submission_package_manifest",
        "citation_source_manifest",
        "publisher_boundary_note",
    } <= field_keys
    assert any("reviewed profile updates" in item for item in schema.boundaries)
    assert any("publisher-final layout" in item for item in schema.boundaries)


def test_technical_long_document_schemas_capture_index_appendix_and_merge_boundaries():
    technical = get_material_schema("technical_document_v1")
    long_doc = get_material_schema("long_document_metadata_v1")

    technical_fields = {field.key for field in technical.fields}
    assert {
        "index_scope",
        "appendix_scope",
        "source_file_manifest",
    } <= technical_fields
    assert any("multi-file merge" in item for item in technical.boundaries)

    long_doc_fields = {field.key for field in long_doc.fields}
    assert {
        "index_scope",
        "appendix_scope",
        "source_file_manifest",
        "merge_boundary_notes",
    } <= long_doc_fields
    assert long_doc.batch_mode == "chapter_collection"
    assert any("multi-document merge" in item for item in long_doc.boundaries)


def test_contract_and_hr_material_schemas_capture_core_requirements():
    contract = get_material_schema("contract_parties_v1")
    signatures = get_material_schema("signature_assets_v1")
    personnel = get_material_schema("personnel_records_v1")

    assert contract.family == "contract_delivery"
    assert {
        "party_a",
        "party_b",
        "contract_amount",
        "signing_date",
    } <= set(contract.required_field_keys)
    assert any("legal advice" in item for item in contract.boundaries)

    assert signatures.required_asset_roles == ("seal",)
    assert "legal_signature" not in signatures.required_asset_roles
    assert signatures.version == "v1"
    assert "signature_assets_v2" in signatures.aliases
    assert "signature_assets_legacy_v1" in signatures.supersedes

    assert personnel.family == "hr_batch_documents"
    assert personnel.batch_mode == "multi_profile"
    assert {"employee_name", "employee_id"} <= set(personnel.required_field_keys)
    personnel_field_keys = {field.key for field in personnel.fields}
    assert {
        "fixed_layout_profile_id",
        "profile_preview_manifest",
        "source_row_manifest",
    } <= personnel_field_keys
    assert any("failed records" in item for item in personnel.boundaries)


def test_form_and_qualification_material_schemas_capture_high_frequency_candidates():
    bidding = get_material_schema("bid_materials_v1")
    form_batch = get_material_schema("form_batch_fields_v1")
    qualifications = get_material_schema("qualification_archive_assets_v1")

    assert bidding.family == "bidding"
    bidding_field_keys = {field.key for field in bidding.fields}
    assert {
        "company_name",
        "project_name",
        "legal_person",
        "consortium_lead",
        "consortium_members",
        "consortium_roles",
    } <= bidding_field_keys
    assert any("consortium member qualification" in item for item in bidding.boundaries)

    assert form_batch.family == "form_batch_documents"
    assert form_batch.batch_mode == "multi_profile"
    assert {
        "form_title",
        "record_id",
        "applicant_name",
    } <= set(form_batch.required_field_keys)
    form_batch_field_keys = {field.key for field in form_batch.fields}
    assert {
        "fixed_layout_profile_id",
        "answer_sheet_reuse_profile_id",
        "fixed_row_height_policy_id",
        "placeholder_residue_policy",
    } <= form_batch_field_keys
    assert any("professional form systems" in item for item in form_batch.boundaries)

    assert qualifications.family == "qualification_archive_packages"
    assert qualifications.batch_mode == "attachment_package"
    assert {"organization", "package_name"} <= set(qualifications.required_field_keys)
    qualification_field_keys = {field.key for field in qualifications.fields}
    assert {
        "certificate_no",
        "license_no",
        "valid_from",
        "valid_until",
        "consortium_member_name",
        "consortium_member_role",
    } <= qualification_field_keys
    assert "qualification_certificate_v2" in qualifications.aliases
    assert "qualification_archive_legacy_v1" in qualifications.supersedes
    assert {"certificate", "business_license"} <= set(
        qualifications.required_asset_roles
    )
    qualification_roles = {role.role: role for role in qualifications.asset_roles}
    assert qualification_roles["certificate"].archive_dir == "01_certificates"
    assert qualification_roles["business_license"].archive_dir == "02_business_license"
    assert (
        qualification_roles["attachment"].archive_dir
        == "99_supporting_attachments"
    )
    assert any("certificate authenticity" in item for item in qualifications.boundaries)
    assert any("expired metadata" in item for item in qualifications.boundaries)


def test_project_application_material_schema_captures_attachment_inventory_profile():
    project = get_material_schema("project_application_materials_v1")

    assert project.family == "project_application"
    assert project.batch_mode == "attachment_package"
    assert {
        "project_name",
        "applicant_unit",
        "principal_investigator",
    } <= set(project.required_field_keys)
    project_field_keys = {field.key for field in project.fields}
    assert {
        "submission_system_id",
        "submission_rule_source_id",
        "submission_system_status",
        "external_submission_boundary_note",
    } <= project_field_keys
    assert {
        "application_form",
        "budget_sheet",
    } <= set(project.required_asset_roles)
    roles = {role.role: role for role in project.asset_roles}
    assert roles["application_form"].accepted_types == ("pdf", "image", "docx")
    assert roles["budget_sheet"].accepted_types == ("pdf", "image", "xlsx")
    assert roles["team_resume"].required is False
    assert roles["supporting_proof"].required is False
    assert any("submission systems" in item for item in project.boundaries)


def test_product_sales_material_schemas_capture_asset_consistency_profile():
    product = get_material_schema("product_assets_v1")
    case_study = get_material_schema("case_study_assets_v1")

    assert product.family == "product_sales_documents"
    assert {"product_name"} <= set(product.required_field_keys)
    product_field_keys = {field.key for field in product.fields}
    assert {
        "asset_source_manifest",
        "asset_consistency_policy",
        "customer_internal_version_policy",
        "quote_boundary_signal",
    } <= product_field_keys
    assert product.required_asset_roles == ("product_image",)
    assert any("marketing copy quality" in item for item in product.boundaries)

    assert case_study.family == "product_sales_documents"
    case_field_keys = {field.key for field in case_study.fields}
    assert {
        "customer_name",
        "case_title",
        "case_evidence_source",
        "case_approval_status",
    } <= case_field_keys
    assert "case_image" not in case_study.required_asset_roles
    assert any("customer claim truthfulness" in item for item in case_study.boundaries)


def test_official_policy_material_schema_captures_archive_metadata_fields():
    official = get_material_schema("official_document_v1")
    meeting = get_material_schema("administrative_meeting_fields_v1")

    assert official.family == "official"
    official_field_keys = {field.key for field in official.fields}
    assert {
        "document_type",
        "security_level",
        "urgency",
        "signer",
        "copy_scope",
        "archive_status",
        "archive_no",
        "retention_period",
    } <= official_field_keys
    assert any("archive-office approval" in item for item in official.boundaries)

    assert meeting.family == "meeting_policy_documents"
    assert {"organization", "meeting_title", "meeting_date"} <= set(
        meeting.required_field_keys
    )
    field_keys = {field.key for field in meeting.fields}
    assert {
        "document_no",
        "issuer",
        "document_type",
        "security_level",
        "copy_scope",
        "archive_status",
        "archive_no",
        "retention_period",
    } <= field_keys
    assert any("administrative decision substance" in item for item in meeting.boundaries)
    assert any("archive-office approval" in item for item in meeting.boundaries)


def test_bilingual_and_disclosure_material_schemas_capture_boundary_profiles():
    finance = get_material_schema("finance_quote_fields_v1")
    patent = get_material_schema("patent_document_fields_v1")
    bilingual = get_material_schema("bilingual_terms_v1")
    disclosure = get_material_schema("regulated_disclosure_materials_v1")

    assert finance.family == "finance_quote_documents"
    assert finance.batch_mode == "attachment_package"
    assert {"customer_name", "quote_no", "amount"} <= set(
        finance.required_field_keys
    )
    finance_fields = {field.key for field in finance.fields}
    assert {
        "quote_source_workbook_id",
        "spreadsheet_table_mapping_manifest",
        "attachment_inventory_manifest",
        "finance_plugin_handoff_status",
        "financial_boundary_note",
    } <= finance_fields
    finance_roles = {role.role: role for role in finance.asset_roles}
    assert finance_roles["source_workbook"].accepted_types == ("xlsx",)
    assert any("spreadsheet table mapping" in item for item in finance.boundaries)
    assert any("financial audit judgment" in item for item in finance.boundaries)

    assert patent.family == "ip_patent_documents"
    patent_fields = {field.key for field in patent.fields}
    assert {
        "claim_outline_manifest",
        "figure_number_inventory",
        "claim_quality_boundary_note",
        "ip_plugin_handoff_status",
        "review_owner",
    } <= patent_fields
    assert any("claim-quality boundary UI" in item for item in patent.boundaries)

    assert bilingual.family == "bilingual_translation_documents"
    assert {
        "source_language",
        "target_language",
        "document_title",
    } <= set(bilingual.required_field_keys)
    bilingual_fields = {field.key for field in bilingual.fields}
    assert {
        "termbase_manifest",
        "parallel_alignment_manifest",
        "unresolved_term_report_id",
        "translation_quality_plugin_status",
        "translation_quality_boundary_note",
    } <= bilingual_fields
    assert any("termbase UI" in item for item in bilingual.boundaries)
    assert any("translation quality" in item for item in bilingual.boundaries)

    assert disclosure.family == "regulated_disclosure_documents"
    assert disclosure.batch_mode == "attachment_package"
    assert {
        "organization",
        "report_period",
        "report_type",
    } <= set(disclosure.required_field_keys)
    disclosure_fields = {field.key for field in disclosure.fields}
    assert {
        "regulated_rule_source_id",
        "section_inventory_manifest",
        "table_attachment_inventory_manifest",
        "assurance_boundary_note",
        "external_filing_boundary_note",
        "review_owner",
    } <= disclosure_fields
    assert any("regulated rule-source governance" in item for item in disclosure.boundaries)
    assert any("assurance boundary UI" in item for item in disclosure.boundaries)
    assert any("audit or assurance judgment" in item for item in disclosure.boundaries)


def test_material_schema_family_filter_and_summary_are_audit_friendly():
    contract_schemas = list_material_schemas(family="contract_delivery")
    summary = build_material_schema_summary(get_material_schema("personnel_records_v1"))

    assert {schema.schema_id for schema in contract_schemas} == {
        "contract_parties_v1",
        "signature_assets_v1",
    }
    assert "personnel_records_v1 [hr_batch_documents]" in summary
    assert "fields=2" in summary
    assert "batch=multi_profile" in summary


def test_material_schema_recommendation_uses_family_and_token_signals():
    recommendation = recommend_material_schema_replacement(
        ["signature_assets_v2"],
        family_hints=["contract_delivery"],
        existing_schema_ids=["contract_parties_v1"],
    )
    fallback = recommend_material_schema_replacement(
        ["qualification_certificate_v2"],
        family_hints=[],
        existing_schema_ids=[],
    )
    legacy = recommend_material_schema_replacement(
        ["signature_assets_legacy_v1"],
        family_hints=[],
        existing_schema_ids=[],
    )

    assert recommendation is not None
    assert recommendation.schema_id == "signature_assets_v1"
    assert recommendation.score > 0
    assert "alias:signature_assets_v2" in recommendation.reasons
    assert "family:contract_delivery" in recommendation.reasons
    assert any(reason.startswith("tokens:") for reason in recommendation.reasons)

    assert fallback is not None
    assert fallback.schema_id == "qualification_archive_assets_v1"
    assert "alias:qualification_certificate_v2" in fallback.reasons
    assert any(reason.startswith("tokens:") for reason in fallback.reasons)

    assert legacy is not None
    assert legacy.schema_id == "signature_assets_v1"
    assert "supersedes:signature_assets_legacy_v1" in legacy.reasons


def test_material_requirement_evaluation_merges_schema_and_scene_overrides():
    check = evaluate_material_requirements(
        schema_id="contract_parties_v1",
        entity_data={
            "party_a": "甲方公司",
            "party_b": "乙方公司",
            "contract_amount": "100000",
        },
        asset_roles=["seal"],
        extra_required_fields=["project_name"],
        extra_required_asset_roles=["legal_signature"],
    )

    assert check.requirements.schema_label == "Contract party fields"
    assert check.requirements.required_field_keys == (
        "party_a",
        "party_b",
        "contract_amount",
        "signing_date",
        "project_name",
    )
    assert check.missing_field_keys == ("signing_date", "project_name")
    assert check.missing_asset_roles == ("legal_signature",)
    assert check.is_satisfied is False


def test_material_requirements_merge_multiple_schema_ids():
    schema_ids = resolve_material_schema_ids(
        "contract_parties_v1",
        ["contract_parties_v1", "signature_assets_v1"],
    )
    requirements = build_material_requirements(
        "contract_parties_v1",
        schema_ids=schema_ids,
    )
    check = evaluate_material_requirements(
        schema_id="contract_parties_v1",
        schema_ids=schema_ids,
        entity_data={
            "party_a": "甲方公司",
            "party_b": "乙方公司",
            "contract_amount": "100000",
            "signing_date": "2026-06-16",
        },
        asset_roles=[],
    )

    assert schema_ids == ("contract_parties_v1", "signature_assets_v1")
    assert requirements.schema_ids == ("contract_parties_v1", "signature_assets_v1")
    assert requirements.schema_labels == (
        "Contract party fields",
        "Signature and seal assets",
    )
    assert requirements.required_field_keys == (
        "party_a",
        "party_b",
        "contract_amount",
        "signing_date",
    )
    assert requirements.required_asset_roles == ("seal",)
    assert check.missing_field_keys == ()
    assert check.missing_asset_roles == ("seal",)


def test_exam_material_requirement_evaluation_accepts_nested_question_source_metadata():
    check = evaluate_material_requirements(
        schema_id="exam_items_v1",
        entity_data={
            "exam_items": {
                "paper": {
                    "paper_title": "Midterm",
                    "subject": "Math",
                    "grade": "Grade 9",
                    "duration": "120",
                    "total_score": 100,
                },
                "sections": [
                    {
                        "section_id": "choice",
                        "questions": [
                            {
                                "id": "Q1",
                                "stem": "1+1=?",
                                "answer": "2",
                                "score": 2,
                            }
                        ],
                    }
                ],
            }
        },
        asset_roles=[],
    )

    assert check.missing_field_keys == ()
    assert check.missing_asset_roles == ()
    assert check.is_satisfied is True


def test_exam_material_requirement_evaluation_accepts_json_encoded_question_source_metadata():
    check = evaluate_material_requirements(
        schema_id="exam_items_v1",
        entity_data={
            "exam_items": (
                '{"paper_title":"Unit Test","subject":"Physics","grade":"Grade 8",'
                '"duration":"90","total_score":100,"questions":[]}'
            )
        },
        asset_roles=[],
    )

    assert check.missing_field_keys == ()


def test_material_requirement_evaluation_accepts_complete_personnel_payload():
    check = evaluate_material_requirements(
        schema_id="personnel_records_v1",
        entity_data={
            "employee_name": "张三",
            "employee_id": "E001",
        },
        asset_roles=[],
    )

    assert check.requirements.schema_label == "Personnel records"
    assert check.missing_field_keys == ()
    assert check.missing_asset_roles == ()
    assert check.is_satisfied is True
