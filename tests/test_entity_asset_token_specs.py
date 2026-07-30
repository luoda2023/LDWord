from __future__ import annotations

from src.config.attachment_materials import AttachmentRoleSpec
from src.config.entity import (
    AssetTokenSpec,
    EntityArchive,
    EntityProfile,
    load_entity_archive,
    save_entity_archive,
)


def test_asset_token_specs_round_trip_as_explicit_profile_inventory(tmp_path):
    path = tmp_path / "package.json"
    archive = EntityArchive(
        profiles=[
            EntityProfile(
                asset_token_specs=[
                    AssetTokenSpec(
                        token_id="logo",
                        token="{{@img:LOGO1}}",
                        label="Logo",
                    ),
                    AssetTokenSpec(
                        token_id="qualification",
                        token="{{@img:资质证书1}}",
                        label="资质证书",
                        cardinality="multiple",
                        source_kind="directory",
                        recursive=True,
                        min_items=1,
                        max_items=None,
                    ),
                ]
            )
        ]
    )

    save_entity_archive(archive, path)
    restored = load_entity_archive(path)

    single, group = restored.profiles[0].asset_token_specs
    assert single.token == "{{@img:LOGO1}}"
    assert single.cardinality == "single"
    assert single.max_items == 1
    assert group.token == "{{@img:资质证书1}}"
    assert group.cardinality == "multiple"
    assert group.source_kind == "directory"
    assert group.recursive is True
    assert group.min_items == 1
    assert group.max_items is None


def test_unbound_attachment_role_specs_round_trip_without_fake_bindings(tmp_path):
    path = tmp_path / "package.json"
    archive = EntityArchive(
        profiles=[
            EntityProfile(
                attachment_role_specs=[
                    AttachmentRoleSpec(
                        role="附件1",
                        label="附件1",
                        accepted_types=("pdf", "docx"),
                        origin="profile",
                    ),
                    AttachmentRoleSpec(
                        role="附件文件夹1",
                        label="附件文件夹1",
                        accepted_types=("pdf", "docx"),
                        cardinality="multiple",
                        source_kind="directory_package",
                        recursive=True,
                        max_items=None,
                        origin="profile",
                    ),
                ],
            )
        ]
    )

    save_entity_archive(archive, path)
    restored = load_entity_archive(path).profiles[0]

    assert [spec.anchor_token for spec in restored.attachment_role_specs] == [
        "{{@attach:附件1}}",
        "{{@attach:附件文件夹1}}",
    ]
    assert restored.attachment_role_specs[1].source_kind == "directory_package"
    assert restored.attachment_bindings == {}
