from src.ui.panels import assets
from src.ui.panels.assets import specs


def test_assets_specs_are_package_level_exports():
    assert assets.COMMON_FIELD_DEFS is specs.COMMON_FIELD_DEFS
    assert assets.COMMON_ASSET_SLOTS is specs.COMMON_ASSET_SLOTS
    assert assets.ASSETS_SECTION_SPECS is specs.ASSETS_SECTION_SPECS


def test_assets_specs_keep_default_material_roles():
    field_keys = [key for key, _label, _placeholder in specs.COMMON_FIELD_DEFS]
    slot_roles = [role for role, _label, _target in specs.COMMON_ASSET_SLOTS]

    assert specs.REQUIRED_FIELD_KEYS == ("company_name",)
    assert "company_name" in field_keys
    assert {"seal", "legal_signature", "qualification"} <= set(slot_roles)
    assert ".png" in specs.SUPPORTED_IMAGE_SUFFIXES
