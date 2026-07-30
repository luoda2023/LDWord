from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
import hashlib
import json
from pathlib import Path

import pytest

from src.config import entity_bundle as entity_bundle_module
from src.config import material_package_library as library
from src.config.attachment_materials import AttachmentBinding, AttachmentItem
from src.config.content_materials import FileAssetRef
from src.config.entity import (
    AssetBinding,
    AssetTokenSpec,
    EntityArchive,
    EntityProfile,
    load_entity_archive,
    save_entity_archive,
    save_entity_archive_bundle,
)
from src.config.asset_resolution import asset_item_payload
from src.config.entity_archive_validation import first_payload_difference
from src.config.entity_archive_wire_contracts import (
    ASSET_ITEM_FIELD_TYPES,
    TIMELINE_PLAN_FIELDS,
    AssetBindingWire,
    AssetTokenSpecWire,
    EntityProfileWirePayload,
)
from src.config.image_materials import (
    ImageMaterialRule,
    ImagePlacementMode,
    ImagePlacementPolicy,
)
from src.config.materials import AssetItem
from src.config.strict_payload_validation import (
    StrictPayloadValidationError,
    validate_complete_dataclass_payload,
)
from src.shared.engine.material_timeline import (
    default_timeline_plan,
    default_timeline_segment,
    normalize_timeline_plans,
)


def _strict_payload(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    target = tmp_path / "package.json"
    save_entity_archive(
        EntityArchive(
            package_id="strict",
            profiles=[
                EntityProfile(
                    profile_id="main",
                    asset_bindings={"logo": AssetBinding(role="logo")},
                )
            ],
        ),
        target,
    )
    return target, json.loads(target.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_first_payload_difference_is_unconditionally_type_sensitive() -> None:
    assert first_payload_difference({"value": 1}, {"value": 1.0}) == (
        "<profile>.value"
    )
    assert first_payload_difference({"value": True}, {"value": 1}) == (
        "<profile>.value"
    )


def test_entity_domain_wire_and_serializer_keys_remain_in_parity(
    tmp_path: Path,
) -> None:
    item = AssetItem(
        item_id="logo-1",
        label="Logo",
        role="logo",
        path="assets/logo.png",
        mime_type="image/png",
        tags=["brand"],
        width_cm=2.0,
        metadata={"owner": "brand"},
        group_id="logos",
        sequence=1,
        source_path="assets",
        original_relative_path="logo.png",
        normalized_name="logo.png",
        content_hash="sha256:content",
    )
    timeline = normalize_timeline_plans({"main": default_timeline_plan()})
    archive = EntityArchive(
        package_id="parity",
        profiles=[
            EntityProfile(
                profile_id="main",
                asset_bindings={"logo": AssetBinding(role="logo")},
                asset_token_specs=[
                    AssetTokenSpec(
                        token_id="logo",
                        token="{{@img:LOGO1}}",
                        label="Logo",
                    )
                ],
                asset_items=[asset_item_payload(item)],
                timeline_plans=timeline,
            )
        ],
    )
    target = tmp_path / "parity.json"
    save_entity_archive(archive, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    profile_payload = payload["profiles"][0]

    profile_fields = {field.name for field in dataclass_fields(EntityProfile)}
    profile_wire_fields = {
        field.name for field in dataclass_fields(EntityProfileWirePayload)
    }
    binding_fields = {field.name for field in dataclass_fields(AssetBinding)}
    binding_wire_fields = {
        field.name for field in dataclass_fields(AssetBindingWire)
    }
    token_fields = {field.name for field in dataclass_fields(AssetTokenSpec)}
    token_wire_fields = {
        field.name for field in dataclass_fields(AssetTokenSpecWire)
    }
    item_fields = {field.name for field in dataclass_fields(AssetItem)}

    assert set(profile_payload) == profile_fields == profile_wire_fields
    assert (
        set(profile_payload["asset_bindings"]["logo"])
        == binding_fields
        == binding_wire_fields
    )
    assert (
        set(profile_payload["asset_token_specs"][0])
        == token_fields
        == token_wire_fields
    )
    assert (
        set(profile_payload["asset_items"][0])
        == item_fields
        == set(ASSET_ITEM_FIELD_TYPES)
    )
    assert set(profile_payload["timeline_plans"]["main"]) == set(
        TIMELINE_PLAN_FIELDS
    )
    assert load_entity_archive(target).profiles[0].profile_id == "main"


@pytest.mark.parametrize(
    ("field", "value", "expected_type"),
    [
        ("recursive", 0, "bool"),
        ("min_items", False, "int"),
        ("max_items", 1.0, "union"),
    ],
)
def test_nested_binding_wire_rejects_equal_but_different_numeric_types(
    tmp_path: Path,
    field: str,
    value: object,
    expected_type: str,
) -> None:
    target, payload = _strict_payload(tmp_path)
    payload["profiles"][0]["asset_bindings"]["logo"][field] = value
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match=rf"material_package_field_type_invalid:.*{field}:{expected_type}",
    ):
        load_entity_archive(target)


def test_nested_float_wire_rejects_integer_for_float_field(tmp_path: Path) -> None:
    rule = ImageMaterialRule(
        rule_id="logo-rule",
        source_role="logo",
        anchor_token="{{@img:logo}}",
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX,
            fixed_width_cm=1.0,
        ),
    )
    target = tmp_path / "image-package.json"
    save_entity_archive(
        EntityArchive(
            package_id="images",
            profiles=[
                EntityProfile(
                    profile_id="main",
                    image_material_rules={rule.rule_id: rule},
                )
            ],
        ),
        target,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["profiles"][0]["image_material_rules"][rule.rule_id]["placement"][
        "fixed_width_cm"
    ] = 1
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="fixed_width_cm:union"):
        load_entity_archive(target)


def test_timeline_requires_the_complete_current_canonical_schema(
    tmp_path: Path,
) -> None:
    rejected = tmp_path / "partial.json"
    with pytest.raises(ValueError, match="material_package_timeline_not_canonical"):
        save_entity_archive(
            EntityArchive(
                package_id="partial-timeline",
                profiles=[
                    EntityProfile(
                        profile_id="main",
                        timeline_plans={"main": {"enabled": True}},
                    )
                ],
            ),
            rejected,
        )
    assert not rejected.exists()

    canonical = normalize_timeline_plans({"main": default_timeline_plan()})
    accepted = tmp_path / "canonical.json"
    save_entity_archive(
        EntityArchive(
            package_id="canonical-timeline",
            profiles=[
                EntityProfile(profile_id="main", timeline_plans=canonical)
            ],
        ),
        accepted,
    )
    assert load_entity_archive(accepted).profiles[0].timeline_plans == canonical

    payload = json.loads(accepted.read_text(encoding="utf-8"))
    payload["profiles"][0]["timeline_plans"]["main"]["schema_version"] = 2
    accepted.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="timeline_version_unsupported"):
        load_entity_archive(accepted)


@pytest.mark.parametrize(
    ("preset", "error"),
    [
        ({"id": "timeline_segment"}, "timeline_preset_fields_missing:version"),
        (
            {"id": "timeline_segment", "version": 2, "unknown": True},
            "timeline_preset_fields_unknown:unknown",
        ),
        ({"id": [], "version": 2}, "timeline_preset_field_type_invalid:id:str"),
        (
            {"id": "timeline_segment", "version": {}},
            "timeline_preset_field_type_invalid:version:int",
        ),
        (
            {"id": "timeline_segment", "version": True},
            "timeline_preset_field_type_invalid:version:int",
        ),
        (
            {"id": "generic_equal", "version": 2},
            "timeline_preset_unsupported:generic_equal:2",
        ),
    ],
)
def test_timeline_preset_requires_an_exact_generator_owned_contract(
    tmp_path: Path,
    preset: dict[str, object],
    error: str,
) -> None:
    plan = default_timeline_segment(1)
    plan["preset"] = preset
    target = tmp_path / "invalid-preset.json"

    with pytest.raises(ValueError, match=error):
        save_entity_archive(
            EntityArchive(
                package_id="invalid-preset",
                profiles=[
                    EntityProfile(
                        profile_id="main",
                        timeline_plans={"segment_1": plan},
                    )
                ],
            ),
            target,
        )
    assert not target.exists()


@pytest.mark.parametrize("binding_item", [False, True])
def test_asset_items_have_one_explicit_wire_contract(
    tmp_path: Path,
    binding_item: bool,
) -> None:
    item = {
        "item_id": "logo-1",
        "role": "logo",
        "path": "assets/logo.png",
        "sha256": "legacy-field-is-not-current-wire",
    }
    profile = (
        EntityProfile(
            profile_id="main",
            asset_bindings={
                "logo": AssetBinding(role="logo", items=[item])
            },
        )
        if binding_item
        else EntityProfile(profile_id="main", asset_items=[item])
    )
    target = tmp_path / f"asset-item-{binding_item}.json"

    with pytest.raises(ValueError, match="nested_fields_unknown:.*sha256"):
        save_entity_archive(
            EntityArchive(package_id="asset-items", profiles=[profile]),
            target,
        )
    assert not target.exists()


def test_asset_item_history_rejects_unmodeled_semantic_fields(
    tmp_path: Path,
) -> None:
    target = tmp_path / "history.json"
    profile = EntityProfile(
        profile_id="main",
        asset_item_history=[
            {
                "action": "question_figure_library_metadata_update",
                "changed_at": "2026-07-14T00:00:00Z",
                "profile_id": "pretends-to-be-a-cross-profile-link",
            }
        ],
    )

    with pytest.raises(ValueError, match="nested_fields_unknown:.*profile_id"):
        save_entity_archive(
            EntityArchive(package_id="history", profiles=[profile]),
            target,
        )
    assert not target.exists()


def test_asset_item_required_id_role_and_path_must_be_nonempty(
    tmp_path: Path,
) -> None:
    for field in ("item_id", "role", "path"):
        item = {"item_id": "logo", "role": "logo", "path": "logo.png"}
        item[field] = ""
        with pytest.raises(
            ValueError,
            match=rf"asset_item_identity_invalid:.*{field}",
        ):
            save_entity_archive(
                EntityArchive(
                    package_id=f"empty-{field}",
                    profiles=[
                        EntityProfile(profile_id="main", asset_items=[item])
                    ],
                ),
                tmp_path / f"empty-{field}.json",
            )


@pytest.mark.parametrize(
    "profiles,error",
    [
        ([EntityProfile(profile_id="")], "profile_id_invalid"),
        (
            [EntityProfile(profile_id="main"), EntityProfile(profile_id="MAIN")],
            "profile_id_duplicate",
        ),
        (
            [EntityProfile(profile_id="a*b"), EntityProfile(profile_id="a?b")],
            "profile_segment_collision",
        ),
    ],
)
def test_bundle_rejects_ambiguous_profile_identities_before_staging(
    tmp_path: Path,
    profiles: list[EntityProfile],
    error: str,
) -> None:
    target = tmp_path / "bundle"
    with pytest.raises(ValueError, match=error):
        save_entity_archive_bundle(EntityArchive(profiles=profiles), target)
    assert not target.exists()
    assert not list(tmp_path.glob(".bundle.staging-*"))


def test_bundle_rejects_safe_role_and_casefolded_target_collisions(
    tmp_path: Path,
) -> None:
    source = tmp_path / "logo.png"
    source.write_bytes(b"logo")
    archive = EntityArchive(
        profiles=[
            EntityProfile(
                profile_id="main",
                asset_paths={"a*b": str(source), "a?b": str(source)},
            )
        ]
    )
    with pytest.raises(ValueError, match="safe_segment_collision"):
        save_entity_archive_bundle(archive, tmp_path / "bundle")

    registry = entity_bundle_module._BundleTargetRegistry()
    registry.claim(tmp_path / "A.png", owner="first")
    with pytest.raises(ValueError, match="entity_bundle_target_collision"):
        registry.claim(tmp_path / "a.PNG", owner="second")


def test_bundle_fallback_package_id_uses_final_destination_name(
    tmp_path: Path,
) -> None:
    target = save_entity_archive_bundle(
        EntityArchive(),
        tmp_path / "final-package",
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["package_id"] == "final-package"
    assert ".staging-" not in payload["package_id"]


def test_bundle_asset_item_source_paths_are_portable_and_do_not_leak_staging(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "1.png").write_bytes(b"one")
    (source / "2.png").write_bytes(b"two")
    archive = EntityArchive(
        profiles=[
            EntityProfile(
                profile_id="main",
                asset_bindings={
                    "gallery": AssetBinding(
                        role="gallery",
                        cardinality="multiple",
                        source_kind="directory",
                        source_path=str(source),
                        max_items=None,
                    )
                },
            )
        ]
    )
    target = save_entity_archive_bundle(archive, tmp_path / "portable")
    text = target.read_text(encoding="utf-8")
    payload = json.loads(text)
    items = payload["profiles"][0]["asset_bindings"]["gallery"]["items"]
    assert all(not Path(item["source_path"]).is_absolute() for item in items)
    assert ".staging-" not in text

    moved = tmp_path / "moved"
    target.parent.rename(moved)
    loaded = load_entity_archive(moved / "package.json")
    for item in loaded.profiles[0].asset_bindings["gallery"].items:
        assert Path(item["source_path"]) == moved / "assets" / "main" / "groups" / "gallery"
        assert Path(item["source_path"]).is_dir()


def test_bundle_rechecks_every_file_asset_ref_after_manifest_save(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "report.pdf"
    source.write_bytes(b"original-report")
    file_ref = FileAssetRef(
        source_path=str(source),
        original_name=source.name,
        media_type="application/pdf",
        content_sha256=_sha256(source),
        byte_size=source.stat().st_size,
    )
    binding = AttachmentBinding(
        role="evidence",
        items=(AttachmentItem("report", file_ref),),
    )
    archive = EntityArchive(
        profiles=[
            EntityProfile(
                profile_id="main",
                attachment_bindings={binding.role: binding},
            )
        ]
    )
    original_save = entity_bundle_module.save_entity_archive

    def save_then_tamper(staged_archive: EntityArchive, path: Path) -> None:
        original_save(staged_archive, path)
        staged_ref = (
            staged_archive.profiles[0]
            .attachment_bindings["evidence"]
            .items[0]
            .file_ref
        )
        Path(staged_ref.source_path).write_bytes(b"tampered-report")

    monkeypatch.setattr(
        entity_bundle_module,
        "save_entity_archive",
        save_then_tamper,
    )
    with pytest.raises(ValueError, match="material_package_file_hash_mismatch"):
        save_entity_archive_bundle(archive, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()


@pytest.mark.parametrize(
    ("archive", "error"),
    [
        (
            EntityArchive(kind="wrong.kind", package_id="valid"),
            "material_package_kind_invalid",
        ),
        (
            EntityArchive(package_id="../escape"),
            "material_package_package_id_invalid",
        ),
        (
            EntityArchive(package_id="types", mode_id=1),
            "material_package_v5_structure_invalid",
        ),
        (
            EntityArchive(package_id="version-bool", version=True),
            "material_package_version_invalid",
        ),
        (
            EntityArchive(package_id="version-one", version=1),
            "material_package_version_unsupported:1",
        ),
        (
            EntityArchive(package_id="version-six", version=6),
            "material_package_version_unsupported:6",
        ),
        (
            EntityArchive(
                package_id="path-types",
                profiles=[
                    EntityProfile(profile_id="main", assets_dir=Path("assets"))
                ],
            ),
            "material_package_path_type_invalid",
        ),
        (
            EntityArchive(
                package_id="paths",
                profiles=[EntityProfile(profile_id="main", assets_dir="../escape")],
            ),
            "material_package_path_escape",
        ),
        (
            EntityArchive(
                package_id="item-source-path",
                profiles=[
                    EntityProfile(
                        profile_id="main",
                        asset_items=[
                            {
                                "item_id": "logo",
                                "role": "logo",
                                "path": "logo.png",
                                "source_path": "../escape",
                            }
                        ],
                    )
                ],
            ),
            "material_package_path_escape",
        ),
        (
            EntityArchive(
                package_id="numbers",
                profiles=[
                    EntityProfile(
                        profile_id="main",
                        asset_items=[
                            {
                                "item_id": "logo",
                                "role": "logo",
                                "path": "logo.png",
                                "width_cm": float("nan"),
                            }
                        ],
                    )
                ],
            ),
            "material_package_nonfinite_number",
        ),
    ],
)
def test_save_rejects_unloadable_payloads_before_replacing_the_target(
    tmp_path: Path,
    archive: EntityArchive,
    error: str,
) -> None:
    target = tmp_path / "package.json"
    target.write_text("preserved", encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        save_entity_archive(archive, target)
    assert target.read_text(encoding="utf-8") == "preserved"


def test_json_loader_rejects_nonstandard_numeric_constants(tmp_path: Path) -> None:
    target, _ = _strict_payload(tmp_path)
    text = target.read_text(encoding="utf-8")
    target.write_text(
        text.replace('"archive_name": ""', '"archive_name": NaN'),
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError,
        match="material_package_json_constant_invalid:NaN",
    ):
        load_entity_archive(target)


def test_shared_strict_float_contract_rejects_nonfinite_numbers() -> None:
    @dataclass
    class FloatPayload:
        value: float

    with pytest.raises(StrictPayloadValidationError, match="finite number"):
        validate_complete_dataclass_payload(
            FloatPayload,
            {"value": float("inf")},
        )
    validate_complete_dataclass_payload(
        FloatPayload,
        {"value": 10**10_000},
    )


@pytest.mark.parametrize(
    ("field", "drift_value", "error"),
    [
        ("package_id", "payload-claims-another-folder", "path_identity_mismatch"),
        ("mode_id", "bidding", "mode_scope_mismatch"),
    ],
)
def test_library_marks_folder_and_mode_drift_unavailable_and_rechecks_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    drift_value: str,
    error: str,
) -> None:
    root = tmp_path / "material-packages"
    monkeypatch.setattr(library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    original = library.create_material_package_in_library(
        EntityArchive(archive_name="Current package"),
        mode_id="official",
        requested_id="folder-id",
    )
    payload = json.loads(original.path.read_text(encoding="utf-8"))
    payload[field] = drift_value
    original.path.write_text(json.dumps(payload), encoding="utf-8")

    (current,) = library.list_material_package_entries(mode_id="official")
    assert current.package_id == "folder-id"
    assert not current.is_available
    assert error in current.load_error
    with pytest.raises(ValueError, match=error):
        library.load_material_package_entry(original)


def test_library_rejects_a_path_claimed_from_the_wrong_source_bucket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "material-packages"
    monkeypatch.setattr(library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    entry = library.create_material_package_in_library(
        EntityArchive(archive_name="User package"),
        mode_id="official",
        requested_id="user-package",
    )
    drifted = library._entry_from_path(
        entry.path,
        mode_id="official",
        source_type="builtin",
    )
    assert drifted is not None
    assert not drifted.is_available
    assert "path_outside_scope" in drifted.load_error
