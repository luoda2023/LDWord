from src.ui.panels import assets
from src.ui.panels.assets import image_helpers, roles, specs


def test_assets_specs_are_package_level_exports():
    assert assets.COMMON_FIELD_DEFS is specs.COMMON_FIELD_DEFS
    assert assets.COMMON_ASSET_SLOTS is specs.COMMON_ASSET_SLOTS
    assert assets.ASSETS_SECTION_SPECS is specs.ASSETS_SECTION_SPECS


def test_assets_primary_material_sections_use_resource_nouns():
    titles = {spec.section_id: spec.title for spec in specs.ASSETS_SECTION_SPECS}
    icons = {spec.section_id: spec.icon_name for spec in specs.ASSETS_SECTION_SPECS}

    assert titles["fields"] == "字段资料"
    assert titles["images"] == "图片资料"
    assert icons["attachments"] == "gallery-vertical-end"


def test_assets_specs_keep_default_material_roles():
    field_keys = [key for key, _label, _placeholder in specs.COMMON_FIELD_DEFS]
    slot_roles = [role for role, _label, _target in specs.COMMON_ASSET_SLOTS]

    assert specs.REQUIRED_FIELD_KEYS == ()
    assert "company_name" in field_keys
    assert {"seal", "legal_signature", "qualification"} <= set(slot_roles)
    assert ".png" in specs.SUPPORTED_IMAGE_SUFFIXES
    assert ".gif" not in specs.SUPPORTED_IMAGE_SUFFIXES


def test_material_file_dialog_filters_preserve_image_and_attachment_boundaries():
    image_filter = image_helpers._image_file_dialog_filter()
    attachment_filter = roles._attachment_path_policy(
        specs.AttachmentRoleSpec(
            role="evidence",
            label="附件",
            accepted_types=("docx", "pdf", "xlsx"),
        )
    ).dialog_filter

    assert "*.png" in image_filter
    assert "*.gif" not in image_filter
    assert "所有文件" not in image_filter
    assert "*.docx" in attachment_filter
    assert "*.pdf" in attachment_filter
    assert "*.xlsx" in attachment_filter
    assert "所有文件" not in attachment_filter
