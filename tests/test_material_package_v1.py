from __future__ import annotations

import json

import pytest

from src.domain.materials import (
    MaterialContract,
    MaterialFieldContract,
    MaterialGroup,
    MaterialPackage,
    MaterialRecord,
    MaterialResourceBinding,
    MaterialResourceRoleContract,
    MaterialResolver,
    MaterialScope,
    clone_material_package,
    generate_group_id,
    generate_package_id,
    generate_record_id,
)
from src.infrastructure.materials.codec import (
    canonical_material_package_bytes,
    load_material_package,
    material_package_revision,
)
from src.infrastructure.materials.repository import MaterialPackageRepository


def _package(*, package_id: str | None = None) -> MaterialPackage:
    group_id = generate_group_id()
    return MaterialPackage(
        package_id=package_id or generate_package_id(),
        display_name="资料包",
        work_mode_id="official",
        material_contract_id="official_document_material_v1",
        shared_scope=MaterialScope(fields={"organization": "甲单位"}),
        groups=(
            MaterialGroup(
                group_id=group_id,
                display_name="第一批",
                scope=MaterialScope(fields={"x": "B"}),
            ),
        ),
        records=(
            MaterialRecord(
                record_id=generate_record_id(),
                display_name="通知一",
                group_id=group_id,
                lifecycle="active",
                scope=MaterialScope(fields={"x": "A", "title": "通知"}),
            ),
        ),
    )


def test_ids_are_opaque_and_rename_does_not_change_identity() -> None:
    package = _package()
    renamed = clone_material_package(package, display_name="新名称")
    assert renamed.package_id == package.package_id
    assert renamed.records[0].record_id == package.records[0].record_id


def test_equal_lower_scope_value_is_not_removed() -> None:
    package = _package()
    record = package.records[0]
    assert package.shared_scope.fields["organization"] == "甲单位"
    assert package.groups[0].scope.fields["x"] == "B"
    assert record.scope.fields["x"] == "A"


def test_resolver_preserves_explicit_owner_and_contract_boundary() -> None:
    package = _package()
    contract = MaterialContract(
        contract_id=package.material_contract_id,
        work_mode_id=package.work_mode_id,
        label="公文资料",
        fields=(
            MaterialFieldContract(
                key="organization",
                label="单位",
                allowed_scopes=("shared",),
            ),
            MaterialFieldContract(
                key="x",
                label="覆盖值",
                allowed_scopes=("group", "record"),
            ),
            MaterialFieldContract(
                key="title",
                label="标题",
                required=True,
                allowed_scopes=("record",),
            ),
        ),
    )

    resolution = MaterialResolver(package, contract).resolve_record(
        package.records[0].record_id
    )

    assert resolution.ok
    assert resolution.record is not None
    assert resolution.record.field_values["x"] == "A"
    assert resolution.record.field_owners["x"] == "record"


def test_resolver_rejects_unknown_fields_and_bad_resource_scope() -> None:
    package = _package()
    contract = MaterialContract(
        contract_id=package.material_contract_id,
        work_mode_id=package.work_mode_id,
        label="公文资料",
        fields=(
            MaterialFieldContract(
                key="organization",
                label="单位",
                allowed_scopes=("shared",),
            ),
            MaterialFieldContract(
                key="title",
                label="标题",
                required=True,
                allowed_scopes=("record",),
            ),
        ),
        resource_roles=(
            MaterialResourceRoleContract(
                role="logo",
                label="标志",
                domain="image",
                allowed_scopes=("shared",),
            ),
        ),
    )

    resolution = MaterialResolver(package, contract).resolve_record(
        package.records[0].record_id
    )

    assert not resolution.ok
    assert "material.field.unknown" in {item.code for item in resolution.issues}


def test_codec_is_schema_v1_only_and_round_trips_exactly(tmp_path) -> None:
    package = _package()
    target = tmp_path / "package.json"
    target.write_bytes(canonical_material_package_bytes(package))

    loaded = load_material_package(target)

    assert loaded == package
    assert material_package_revision(loaded).startswith("sha256:")
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["schema_version"] = 5
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(
        ValueError,
        match="material_package_schema_version_unsupported",
    ):
        load_material_package(target)


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda payload: payload["records"][0].update(
                {"display_name": " 通知一"}
            ),
            "material_record.display_name_invalid",
        ),
        (
            lambda payload: payload["records"][0]["scope"]["derivations"].update(
                {"bad": []}
            ),
            "material_package_field_type_invalid",
        ),
        (
            lambda payload: payload["records"][0].update({"unknown": True}),
            "material_package_fields_unknown",
        ),
    ],
)
def test_codec_rejects_instead_of_normalizing(tmp_path, mutate, error) -> None:
    target = tmp_path / "package.json"
    payload = json.loads(canonical_material_package_bytes(_package()))
    mutate(payload)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises((TypeError, ValueError), match=error):
        load_material_package(target)


def test_repository_uses_revision_cas_and_no_shadowing(tmp_path) -> None:
    repository = MaterialPackageRepository(tmp_path)
    package = _package()
    created = repository.create_user(package)
    renamed = clone_material_package(package, display_name="新名称")

    saved = repository.save_user(
        renamed,
        expected_revision=created.ref.revision,
    )

    assert saved.package.display_name == "新名称"
    with pytest.raises(RuntimeError, match="material_package_revision_conflict"):
        repository.save_user(
            package,
            expected_revision=created.ref.revision,
        )
    with pytest.raises(FileExistsError):
        repository.create_user(package)


def test_repository_vendors_and_verifies_resource_objects(tmp_path) -> None:
    repository = MaterialPackageRepository(tmp_path / "library")
    package = _package()
    created = repository.create_user(package)
    source = tmp_path / "logo.png"
    source.write_bytes(b"not-a-real-png-but-a-stable-object")
    object_ref = repository.import_object(
        work_mode_id=package.work_mode_id,
        package_id=package.package_id,
        source_path=source,
        media_type="image/png",
    )
    record = package.records[0]
    updated_record = MaterialRecord(
        record_id=record.record_id,
        display_name=record.display_name,
        group_id=record.group_id,
        lifecycle=record.lifecycle,
        scope=MaterialScope(
            fields=record.scope.fields,
            resources={
                "logo": MaterialResourceBinding(
                    role="logo",
                    items=(object_ref,),
                )
            },
        ),
    )
    updated = clone_material_package(package, records=(updated_record,))

    saved = repository.save_user(
        updated,
        expected_revision=created.ref.revision,
    )

    assert repository.object_path(saved, object_ref).read_bytes() == source.read_bytes()
