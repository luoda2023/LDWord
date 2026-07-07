import pytest

from src.config.fixed_layout import (
    audit_fixed_layout_row_height_policies,
    build_fixed_layout_row_height_policy_summary,
    fixed_layout_row_height_policy_for_family,
)
from src.config.scene_family_registry import (
    build_planned_scene_family_summary,
    get_planned_scene_family,
    list_planned_scene_families,
)
from src.ui.panels.workbench.scene_presets import (
    SCENE_FACTORIES,
    SCENE_META_MAP,
    create_scene,
)
from src.shared.engine.count_engine import list_count_profiles
from src.shared.engine.object_preflight import object_preflight_targets_for_touchpoints


def test_p1_scene_families_are_registered_as_planning_contracts():
    families = {family.family_id: family for family in list_planned_scene_families(priority="P1")}

    assert set(families) >= {
        "thesis_cn",
        "journal_en",
        "exam_teaching",
        "project_application",
        "contract_delivery",
        "hr_batch_documents",
        "meeting_policy_documents",
        "product_sales_documents",
    }
    for family in families.values():
        assert family.priority == "P1"
        assert family.default_profile_id
        assert family.capability_domains
        assert family.workflow_archetypes
        assert family.maturity_level.startswith("L")
        assert family.first_closed_slice
        assert family.ooxml_touchpoints
        assert family.required_closures
        assert family.boundaries
        assert family.expose_in_navigation is False


def test_extended_scene_family_priorities_are_queryable():
    p1_ids = {family.family_id for family in list_planned_scene_families(priority="P1")}
    p1_candidate_ids = {
        family.family_id
        for family in list_planned_scene_families(priority="P1_CANDIDATE")
    }
    p2_ids = {family.family_id for family in list_planned_scene_families(priority="P2")}

    assert "long_document_publishing" in p1_candidate_ids
    assert {
        "form_batch_documents",
        "qualification_archive_packages",
    } <= p1_candidate_ids
    assert {
        "finance_quote_documents",
        "ip_patent_documents",
        "bilingual_translation_documents",
        "regulated_disclosure_documents",
    } <= p2_ids
    assert p1_ids.isdisjoint(p1_candidate_ids)
    assert p1_ids.isdisjoint(p2_ids)
    assert p1_candidate_ids.isdisjoint(p2_ids)


def test_planned_scene_family_count_profiles_are_registered():
    registered_profile_ids = {profile.profile_id for profile in list_count_profiles()}

    missing = {
        family.family_id: tuple(
            profile_id
            for profile_id in family.count_profiles
            if profile_id not in registered_profile_ids
        )
        for family in list_planned_scene_families()
    }
    missing = {
        family_id: profile_ids
        for family_id, profile_ids in missing.items()
        if profile_ids
    }

    assert missing == {}


def test_planned_scene_families_capture_distinct_high_frequency_boundaries():
    thesis_cn = get_planned_scene_family("thesis_cn")
    journal = get_planned_scene_family("journal_en")
    exam = get_planned_scene_family("exam_teaching")
    project = get_planned_scene_family("project_application")
    contract = get_planned_scene_family("contract_delivery")
    hr = get_planned_scene_family("hr_batch_documents")
    meeting = get_planned_scene_family("meeting_policy_documents")
    product = get_planned_scene_family("product_sales_documents")
    long_doc = get_planned_scene_family("long_document_publishing")
    form_batch = get_planned_scene_family("form_batch_documents")
    qualifications = get_planned_scene_family("qualification_archive_packages")
    finance = get_planned_scene_family("finance_quote_documents")
    patent = get_planned_scene_family("ip_patent_documents")
    bilingual = get_planned_scene_family("bilingual_translation_documents")
    disclosure = get_planned_scene_family("regulated_disclosure_documents")

    assert thesis_cn.intended_landing == "existing_thesis_scene_profile"
    assert thesis_cn.default_profile_id == "thesis_cn"
    assert "school_thesis" in thesis_cn.count_profiles
    assert "references_citations" in thesis_cn.workflow_archetypes
    assert "formula_symbols" in thesis_cn.workflow_archetypes
    assert "field" in thesis_cn.ooxml_touchpoints
    assert any("English journal" in item for item in thesis_cn.boundaries)

    assert journal.intended_landing == "independent_scene_family"
    assert "journal_words" in journal.count_profiles
    assert "submission_manuscript" in journal.delivery_presets
    assert "submission_package" in journal.workflow_archetypes
    assert "field" in journal.ooxml_touchpoints
    assert any("reviewed journal rule" in item for item in journal.required_closures)
    assert any("publisher-final layout" in item for item in journal.boundaries)

    assert "json" in exam.input_formats
    assert "student_version" in exam.delivery_presets
    assert "teacher_version" in exam.delivery_presets
    assert "content_visibility" in exam.workflow_archetypes
    assert "structured question source" in exam.first_closed_slice
    assert any("single structured source" in item for item in exam.required_closures)

    assert project.material_schema_ids == ("project_application_materials_v1",)
    assert "attachment_inventory" in project.count_profiles
    assert project.delivery_presets == (
        "application_package",
        "attachment_inventory_report",
    )
    assert "submission_package" in project.workflow_archetypes
    assert any("submission systems" in item for item in project.boundaries)

    assert "review_copy" in contract.delivery_presets
    assert "signing_copy" in contract.delivery_presets
    assert "compare_docx" not in contract.delivery_presets
    assert "contract_parties_v1" in contract.material_schema_ids
    assert "field_consistency" in contract.workflow_archetypes
    assert "revision" in contract.ooxml_touchpoints
    assert any("legal advice" in item for item in contract.boundaries)

    assert "xlsx" in hr.input_formats
    assert "batch_generation" in hr.capability_domains
    assert "failure_isolation" in hr.workflow_archetypes
    assert any("failure isolation" in item for item in hr.required_closures)

    assert meeting.intended_landing == "official_sub_profile"
    assert "preserve_numbering" in meeting.capability_domains
    assert "formal_internal_delivery" in meeting.workflow_archetypes
    assert "archive_manifest" in meeting.delivery_presets
    assert any("policy archive profile defaults" in item for item in meeting.required_closures)
    assert any("top-level administrative scenes" in item for item in meeting.boundaries)

    assert "product_assets_v1" in product.material_schema_ids
    assert "customer_copy" in product.delivery_presets
    assert "pre_sales_package" in product.delivery_presets
    assert "customer_internal_delivery" in product.workflow_archetypes
    assert any("marketing copy quality" in item for item in product.boundaries)

    assert long_doc.priority == "P1_CANDIDATE"
    assert "archive_package" in long_doc.delivery_presets
    assert "chapter_inventory" in long_doc.workflow_archetypes
    assert "field" in long_doc.ooxml_touchpoints
    assert any("publisher layout systems" in item for item in long_doc.boundaries)

    assert form_batch.priority == "P1_CANDIDATE"
    assert "form_batch_fields_v1" in form_batch.material_schema_ids
    assert "placeholder_fill" in form_batch.capability_domains
    assert "row_height" in form_batch.ooxml_touchpoints
    assert "content_control" in form_batch.ooxml_touchpoints
    assert any("professional form systems" in item for item in form_batch.boundaries)

    assert qualifications.priority == "P1_CANDIDATE"
    assert "qualification_archive_assets_v1" in qualifications.material_schema_ids
    assert "attachment_inventory" in qualifications.capability_domains
    assert "archive_package" in qualifications.workflow_archetypes
    assert "relationship" in qualifications.ooxml_touchpoints
    assert any("certificate authenticity" in item for item in qualifications.boundaries)

    assert finance.priority == "P2"
    assert "xlsx" in finance.input_formats
    assert "professional_boundary" in finance.workflow_archetypes
    assert "embedded_workbook" in finance.ooxml_touchpoints
    assert any("financial audit judgment" in item for item in finance.boundaries)

    assert patent.priority == "P2"
    assert "professional_plugin" in patent.intended_landing
    assert "section/figure-number inventory" in patent.first_closed_slice
    assert any("patent legal quality" in item for item in patent.boundaries)

    assert bilingual.priority == "P2"
    assert "bilingual_terms_v1" in bilingual.material_schema_ids
    assert "bilingual_parallel_text" in bilingual.count_profiles
    assert "terminology_consistency" in bilingual.workflow_archetypes
    assert "revision" in bilingual.ooxml_touchpoints
    assert any("translation quality" in item for item in bilingual.boundaries)

    assert disclosure.priority == "P2"
    assert "regulated_disclosure_materials_v1" in disclosure.material_schema_ids
    assert "disclosure_section_inventory" in disclosure.count_profiles
    assert "archive_manifest" in disclosure.delivery_presets
    assert "archive_package" in disclosure.workflow_archetypes
    assert "hidden_text" in disclosure.ooxml_touchpoints
    assert "relationship" in disclosure.ooxml_touchpoints
    assert any("audit or assurance judgment" in item for item in disclosure.boundaries)


def test_planned_scene_families_do_not_become_executable_builtin_scenes_yet():
    planned_ids = {family.family_id for family in list_planned_scene_families()}

    assert planned_ids.isdisjoint(SCENE_META_MAP)
    assert planned_ids.isdisjoint(SCENE_FACTORIES)

    for family_id in planned_ids:
        with pytest.raises(ValueError):
            create_scene(family_id)


def test_planned_scene_family_ooxml_touchpoints_have_preflight_mapping():
    mapped_families = {
        family.family_id: object_preflight_targets_for_touchpoints(
            family.ooxml_touchpoints
        )
        for family in list_planned_scene_families()
    }

    assert "tracked_changes" in mapped_families["contract_delivery"]
    assert "content_controls" in mapped_families["form_batch_documents"]
    assert "embedded_workbooks" in mapped_families["finance_quote_documents"]
    assert "fields" in mapped_families["journal_en"]
    assert "comments" in mapped_families["bilingual_translation_documents"]
    assert "tracked_changes" in mapped_families["regulated_disclosure_documents"]


def test_form_batch_family_has_fixed_layout_row_height_policy():
    policy = fixed_layout_row_height_policy_for_family("form_batch_documents")
    result = audit_fixed_layout_row_height_policies()
    summary = build_fixed_layout_row_height_policy_summary(policy)

    assert result.is_clean
    assert policy is not None
    assert policy.owner_layer == "scene"
    assert policy.mode == "preserve_existing"
    assert policy.row_height_pt is None
    assert policy.parameter_path == "form_batch_documents.table.row_height_pt"
    assert policy.ooxml_touchpoint == "w:trHeight"
    assert "content_controls" in policy.applies_to
    assert "textboxes" in policy.applies_to
    assert "w:trHeight" in summary
    assert fixed_layout_row_height_policy_for_family("thesis") is None
    assert fixed_layout_row_height_policy_for_family("thesis_cn") is None


def test_planned_scene_family_summary_is_audit_friendly():
    summary = build_planned_scene_family_summary(
        get_planned_scene_family("journal_en")
    )

    assert "journal_en [P1]" in summary
    assert "navigation=False" in summary
    assert "profile=journal_en_default" in summary
    assert "maturity=L1" in summary
    assert "workflows=compliance_counting/references_citations/submission_package" in summary
