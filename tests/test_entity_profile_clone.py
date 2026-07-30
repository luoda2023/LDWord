from __future__ import annotations

import pytest

from src.config.entity import AssetBinding, EntityProfile, clone_entity_profile


def test_clone_entity_profile_preserves_every_declared_field_and_is_deep() -> None:
    source = EntityProfile(
        profile_id="source",
        profile_name="Source",
        fields={"company_name": "Example"},
        declared_field_keys=["company_name", "empty_field"],
        field_functions={"today": {"kind": "current_date"}},
        timeline_plans={"plan": {"items": [{"name": "A"}]}},
        asset_bindings={
            "qualification": AssetBinding(
                role="qualification",
                cardinality="multiple",
                source_kind="directory",
                items=[{"path": "one.png"}],
            )
        },
        asset_items=[{"item_id": "one", "metadata": {"page": 1}}],
    )

    cloned = clone_entity_profile(
        source,
        profile_id="copy",
        profile_name="Copy",
    )

    assert cloned.profile_id == "copy"
    assert cloned.profile_name == "Copy"
    assert cloned.fields == source.fields
    assert cloned.declared_field_keys == source.declared_field_keys
    assert cloned.asset_bindings == source.asset_bindings
    assert cloned.asset_items == source.asset_items

    cloned.fields["company_name"] = "Changed"
    cloned.declared_field_keys.append("copy_only")
    cloned.asset_bindings["qualification"].items[0]["path"] = "two.png"
    cloned.asset_items[0]["metadata"]["page"] = 2

    assert source.fields["company_name"] == "Example"
    assert source.declared_field_keys == ["company_name", "empty_field"]
    assert source.asset_bindings["qualification"].items[0]["path"] == "one.png"
    assert source.asset_items[0]["metadata"]["page"] == 1


def test_clone_entity_profile_rejects_unknown_override() -> None:
    with pytest.raises(TypeError, match="Unknown EntityProfile fields: future_field"):
        clone_entity_profile(EntityProfile(), future_field="value")
