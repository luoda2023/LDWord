from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
)
from src.config.official_material_form import (
    build_official_material_form_projection,
    official_material_field_label,
)


def test_notice_projection_prioritizes_required_fields_and_hides_optional_groups():
    projection = build_official_material_form_projection("notice")

    assert projection.required_field_keys == (
        "title",
        "body",
        "organization",
        "document_no",
        "issue_date",
    )
    assert projection.visible_field_keys == projection.required_field_keys
    assert "attachment_note" in projection.field_keys
    assert "copy_scope" in projection.field_keys
    assert "attachment_note" not in projection.visible_field_keys
    assert "copy_scope" not in projection.visible_field_keys


def test_projection_expands_optional_and_advanced_groups_without_scanning_docx():
    projection = build_official_material_form_projection(
        "notice",
        expanded_groups={"optional", "advanced"},
    )

    assert "attachment_note" in projection.visible_field_keys
    assert "issuer" in projection.visible_field_keys
    assert "copy_scope" in projection.visible_field_keys
    assert "printing_org" in projection.visible_field_keys
    assert "printing_date" in projection.visible_field_keys


def test_existing_optional_value_stays_visible_when_group_is_collapsed():
    projection = build_official_material_form_projection(
        "notice",
        {"attachment_note": "附件：检查表"},
    )

    assert "attachment_note" in projection.visible_field_keys


def test_profile_policies_distinguish_minutes_and_public_announcement_fields():
    minutes = build_official_material_form_projection("minutes")
    announcement = build_official_material_form_projection("announcement")

    assert "meeting_date" in minutes.visible_field_keys
    assert "participants" in minutes.visible_field_keys
    assert "recipient" not in minutes.field_keys
    assert "attachment_note" not in minutes.field_keys
    assert "recipient" not in announcement.field_keys
    assert "meeting_date" not in announcement.field_keys
    assert minutes.required_field_keys == (
        "title",
        "body",
        "organization",
        "document_no",
        "issue_date",
    )


def test_contract_and_form_projection_share_requirement_policy():
    request = get_official_document_assembly_contract("request")
    projection = build_official_material_form_projection("request")

    assert request is not None
    request_requirements = {
        binding.field_key: binding.resolved_requirement
        for binding in request.field_bindings
    }
    assert request_requirements["recipient"] == "optional"
    assert set(projection.required_field_keys) == {
        binding.field_key
        for binding in request.field_bindings
        if binding.required and binding.applicable
    }
    assert official_material_field_label("issuer") == "落款机关"


def test_contract_distinguishes_registered_fields_from_currently_applicable_fields():
    minutes = get_official_document_assembly_contract("minutes")

    assert minutes is not None
    assert "recipient" in minutes.material_field_keys
    assert "attachment_note" in minutes.material_field_keys
    assert "recipient" not in minutes.applicable_material_field_keys
    assert "attachment_note" not in minutes.applicable_material_field_keys


def test_unknown_profile_projects_no_fields_instead_of_guessing_notice_fields():
    projection = build_official_material_form_projection("missing")

    assert projection.profile_id == "missing"
    assert projection.fields == ()
