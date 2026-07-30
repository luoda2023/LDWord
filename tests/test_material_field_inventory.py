from src.config.entity import EntityProfile
from src.config.material_field_inventory import (
    discard_material_field,
    normalize_material_field_inventory,
    project_material_field_inventory,
    rename_material_field,
)


def test_blank_package_has_no_implicit_mode_or_scenario_fields():
    profile = EntityProfile()

    inventory = project_material_field_inventory(profile)

    assert inventory.fixed_keys == ()
    assert inventory.floating_keys == ()
    assert profile.field_scopes == {}


def test_explicit_package_inventory_preserves_exact_identifiers_and_order():
    profile = EntityProfile(
        field_scopes={
            "Field_01": "fixed",
            "发文机关1": "floating",
            "字段=自定义": "fixed",
        }
    )

    inventory = project_material_field_inventory(profile)

    assert inventory.fixed_keys == ("Field_01", "字段=自定义")
    assert inventory.floating_keys == ("发文机关1",)


def test_legacy_package_values_migrate_to_fixed_without_starter_injection():
    profile = EntityProfile(
        fields={"公司": "A 公司"},
        declared_field_keys=["项目名称", "公司"],
    )

    inventory = normalize_material_field_inventory(profile)

    assert inventory.fixed_keys == ("项目名称", "公司")
    assert inventory.floating_keys == ()
    assert profile.field_scopes == {
        "项目名称": "fixed",
        "公司": "fixed",
    }


def test_removed_legacy_tombstone_is_compacted_without_resurrecting_field():
    profile = EntityProfile(
        fields={"保留": "值", "已删": "旧值"},
        declared_field_keys=["保留", "已删"],
        field_scopes={"保留": "fixed", "已删": "removed"},
        field_functions={"已删": {"function": "realtime_date"}},
        field_aliases={"旧别名": "已删"},
    )

    inventory = normalize_material_field_inventory(profile)

    assert inventory.fixed_keys == ("保留",)
    assert inventory.floating_keys == ()
    assert profile.field_scopes == {"保留": "fixed"}
    assert profile.fields == {"保留": "值"}
    assert profile.declared_field_keys == ["保留"]
    assert profile.field_functions == {}
    assert profile.field_aliases == {}


def test_discard_material_field_cleans_every_inventory_reference():
    profile = EntityProfile(
        fields={"保留": "值", "已删": "旧值"},
        declared_field_keys=["保留", "已删"],
        field_scopes={"保留": "fixed", "已删": "floating"},
        field_functions={"已删": {"function": "realtime_date"}},
        field_sources={"已删": "imported_mapping", "保留": "manual"},
        field_aliases={"旧别名": "已删", "保留别名": "保留"},
    )

    assert discard_material_field(profile, "已删") is True
    inventory = normalize_material_field_inventory(profile)

    assert inventory.active_keys == ("保留",)
    assert profile.fields == {"保留": "值"}
    assert profile.declared_field_keys == ["保留"]
    assert profile.field_functions == {}
    assert profile.field_sources == {"保留": "manual"}
    assert profile.field_aliases == {"保留别名": "保留"}


def test_rename_material_field_preserves_order_and_retargets_projections():
    profile = EntityProfile(
        fields={"第一项": "A", "旧字段": "B", "第三项": "C"},
        declared_field_keys=["第一项", "旧字段", "第三项"],
        field_scopes={"第一项": "fixed", "旧字段": "floating", "第三项": "fixed"},
        field_functions={"旧字段": {"function": "realtime_date"}},
        field_sources={"旧字段": "imported_mapping"},
        field_aliases={"旧别名": "旧字段"},
    )

    assert rename_material_field(profile, "旧字段", "新字段") is True

    assert list(profile.field_scopes) == ["第一项", "新字段", "第三项"]
    assert list(profile.fields) == ["第一项", "新字段", "第三项"]
    assert profile.fields["新字段"] == "B"
    assert profile.declared_field_keys == ["第一项", "新字段", "第三项"]
    assert profile.field_functions == {"新字段": {"function": "realtime_date"}}
    assert profile.field_sources == {"新字段": "imported_mapping"}
    assert profile.field_aliases == {"旧别名": "新字段"}
