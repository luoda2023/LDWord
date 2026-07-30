import hashlib
import json
from pathlib import Path

from PIL import Image
import pytest

from content_artifact_test_utils import compile_content_binding
from src.config.attachment_materials import (
    AttachmentBinding,
    AttachmentItem,
    AttachmentSourceKind,
)
from src.config.content_materials import ContentInsertionRule, FileAssetRef
from src.config.entity import (
    ENTITY_PACKAGE_VERSION,
    AssetBinding,
    EntityArchive,
    EntityProfile,
    clone_entity_profile,
    load_entity_archive,
    save_entity_archive,
    save_entity_archive_bundle,
)
from src.config.image_materials import (
    ImageCardinality,
    ImageMaterialRule,
    ImagePlacementMode,
    ImagePlacementPolicy,
    ImageWatermarkPolicy,
)
from src.services.material_content.artifact_repository import ContentArtifactRepository


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_ref(path: Path, media_type: str) -> FileAssetRef:
    return FileAssetRef(
        str(path), path.name, media_type, _sha(path), path.stat().st_size
    )


def _image_rule(*, watermark_text: str = "Bidder {{company_name}}") -> ImageMaterialRule:
    return ImageMaterialRule(
        rule_id="qualification-images",
        source_role="qualification",
        anchor_token="{{@img:qualification1}}",
        cardinality=ImageCardinality.MULTIPLE,
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW, fixed_width_cm=15.0
        ),
        watermark=ImageWatermarkPolicy(True, watermark_text),
    )


def _archive(tmp_path: Path):
    source_root = tmp_path / "sources"
    source_root.mkdir()
    image = source_root / "images" / "route.png"
    image.parent.mkdir()
    Image.new("RGB", (16, 10), "navy").save(image)
    markdown = source_root / "route.md"
    markdown.write_text("# 技术路线\n\n![路线](images/route.png)\n", encoding="utf-8")
    report = source_root / "inspection.pdf"
    report.write_bytes(b"%PDF-1.7 report")
    repository = ContentArtifactRepository(tmp_path / "repository")
    binding = compile_content_binding(markdown, repository)
    attachments = AttachmentBinding(
        role="attachment_list",
        source_kind=AttachmentSourceKind.FILE_SET,
        cardinality="multiple",
        items=(AttachmentItem("inspection", _file_ref(report, "application/pdf")),),
        min_items=1,
        max_items=None,
        accepted_media_types=("application/pdf",),
        accepted_extensions=(".pdf",),
    )
    profile = EntityProfile(
        profile_id="bidder",
        profile_name="投标人",
        content_bindings={binding.content_id: binding},
        content_rules=(
            ContentInsertionRule(
                "technical-route-rule", binding.content_id, "{{@file:technical_route}}"
            ),
        ),
        attachment_bindings={attachments.role: attachments},
        image_material_rules={"qualification-images": _image_rule()},
    )
    return EntityArchive(archive_id="bid-materials", profiles=[profile]), repository, {
        "markdown": markdown, "image": image, "report": report
    }


def test_v5_json_round_trip_preserves_typed_contracts_and_clone(tmp_path: Path) -> None:
    archive, _, _ = _archive(tmp_path)
    target = tmp_path / "package.json"
    save_entity_archive(archive, target)
    loaded = load_entity_archive(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    profile = loaded.profiles[0]
    assert payload["version"] == ENTITY_PACKAGE_VERSION == 5
    assert profile.content_bindings["technical_route"].artifact_ref.artifact_id
    assert profile.content_rules[0].anchor_token == "{{@file:technical_route}}"
    assert profile.image_material_rules["qualification-images"] == _image_rule()
    cloned = clone_entity_profile(profile, profile_name="副本")
    assert cloned.content_bindings == profile.content_bindings
    assert cloned.content_bindings is not profile.content_bindings


def test_save_canonicalizes_relative_package_paths_before_strict_load(
    tmp_path: Path,
) -> None:
    target = tmp_path / "package.json"
    save_entity_archive(
        EntityArchive(
            package_id="relative-paths",
            profiles=[EntityProfile(assets_dir=r"assets\nested")],
        ),
        target,
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["profiles"][0]["assets_dir"] == "assets/nested"
    assert load_entity_archive(target).profiles[0].assets_dir == str(
        (tmp_path / "assets" / "nested").resolve()
    )


def test_bundle_vendors_artifacts_and_survives_move_without_sources(tmp_path: Path) -> None:
    archive, repository, sources = _archive(tmp_path)
    original_report = sources["report"].read_bytes()
    package_dir = tmp_path / "portable"
    package_path = save_entity_archive_bundle(
        archive, package_dir, content_artifact_repository=repository
    )
    payload = json.loads(package_path.read_text(encoding="utf-8"))
    binding_payload = payload["profiles"][0]["content_bindings"]["technical_route"]
    artifact_id = binding_payload["artifact_ref"]["artifact_id"]
    assert (package_dir / "content_artifacts" / "sha256" / artifact_id).is_dir()
    assert "source" not in binding_payload

    sources["markdown"].unlink()
    sources["image"].unlink()
    moved = tmp_path / "moved-portable"
    package_dir.rename(moved)
    installed = ContentArtifactRepository(tmp_path / "installed")
    loaded = load_entity_archive(
        moved / "package.json", content_artifact_repository=installed
    )
    binding = loaded.profiles[0].content_bindings["technical_route"]
    assert installed.validate(binding.artifact_ref).manifest.artifact_id == artifact_id
    attachment = loaded.profiles[0].attachment_bindings["attachment_list"].items[0]
    assert Path(attachment.file_ref.source_path).read_bytes() == original_report


def test_image_rule_inventory_is_stable_and_affects_package_hash(tmp_path: Path) -> None:
    profile = EntityProfile(image_material_rules={"qualification-images": _image_rule()})
    archive = EntityArchive(package_id="stable", profiles=[profile])
    target = tmp_path / "package.json"
    save_entity_archive(archive, target)
    first = _sha(target)
    archive.profiles[0] = EntityProfile(
        image_material_rules={
            "qualification-images": _image_rule(watermark_text="changed")
        }
    )
    save_entity_archive(archive, target)
    assert _sha(target) != first


@pytest.mark.parametrize("version", [0, 1, 2, 3, 4, 6])
def test_non_v5_package_contracts_are_rejected(tmp_path: Path, version: int) -> None:
    path = tmp_path / f"v{version}.json"
    path.write_text(
        json.dumps({"kind": "alavette.material_package", "version": version, "profiles": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="material_package_version_unsupported"):
        load_entity_archive(path)


def _strict_v5_payload(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    target = tmp_path / "strict-package.json"
    save_entity_archive(
        EntityArchive(
            archive_id="strict-archive",
            package_id="strict-package",
            profiles=[
                EntityProfile(
                    profile_id="main",
                    fields={"company_name": "Acme"},
                    asset_bindings={"logo": AssetBinding(role="logo")},
                )
            ],
        ),
        target,
    )
    return target, json.loads(target.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda payload: payload.pop("package_id"),
            "material_package_v5_structure_invalid:.*package_id",
        ),
        (
            lambda payload: payload.__setitem__("legacy_source", "old"),
            "material_package_v5_structure_invalid:.*legacy_source",
        ),
        (
            lambda payload: payload["profiles"][0].pop("field_scopes"),
            "material_package_v5_structure_invalid:.*profiles\\[0\\].*field_scopes",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__(
                "required_fields", []
            ),
            "material_package_v5_structure_invalid:.*profiles\\[0\\].*required_fields",
        ),
    ],
)
def test_v5_rejects_missing_and_unknown_archive_or_profile_fields(
    tmp_path: Path,
    mutate,
    error: str,
) -> None:
    target, payload = _strict_v5_payload(tmp_path)
    mutate(payload)
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        load_entity_archive(target)


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda payload: payload.__setitem__("profiles", {}),
            "material_package_v5_structure_invalid:.*profiles",
        ),
        (
            lambda payload: payload.__setitem__("mode_id", 1),
            "material_package_v5_structure_invalid:.*mode_id",
        ),
        (
            lambda payload: payload["profiles"][0].__setitem__("fields", []),
            "material_package_v5_structure_invalid:.*profiles\\[0\\].fields",
        ),
        (
            lambda payload: payload["profiles"][0]["fields"].__setitem__(
                "company_name", 7
            ),
            "material_package_v5_structure_invalid:"
            ".*profiles\\[0\\].fields.company_name",
        ),
    ],
)
def test_v5_rejects_wrong_json_container_and_scalar_types(
    tmp_path: Path,
    mutate,
    error: str,
) -> None:
    target, payload = _strict_v5_payload(tmp_path)
    mutate(payload)
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        load_entity_archive(target)


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda payload: payload["profiles"][0]["asset_bindings"][
                "logo"
            ].pop("role"),
            "material_package_nested_fields_missing:"
            "profile_0.asset_bindings.logo:role",
        ),
        (
            lambda payload: payload["profiles"][0]["asset_bindings"][
                "logo"
            ].__setitem__("legacy_identity", "logo"),
            "material_package_nested_fields_unknown:"
            "profile_0.asset_bindings.logo:legacy_identity",
        ),
    ],
)
def test_v5_rejects_repaired_nested_binding_identity(
    tmp_path: Path,
    mutate,
    error: str,
) -> None:
    target, payload = _strict_v5_payload(tmp_path)
    mutate(payload)
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        load_entity_archive(target)


def test_v5_requires_exact_kind_and_nonempty_persisted_package_id(
    tmp_path: Path,
) -> None:
    target, payload = _strict_v5_payload(tmp_path)
    payload["kind"] = ""
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="material_package_kind_invalid"):
        load_entity_archive(target)

    _, payload = _strict_v5_payload(tmp_path)
    payload["package_id"] = ""
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="material_package_package_id_invalid"):
        load_entity_archive(target)


def test_version_error_precedes_current_schema_validation(tmp_path: Path) -> None:
    target = tmp_path / "old.json"
    target.write_text(
        json.dumps({"version": 1, "unknown": "legacy"}),
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError,
        match="material_package_version_unsupported:1",
    ):
        load_entity_archive(target)


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ([], "material_package_root_type_invalid:object_required"),
        ({"version": "5"}, "material_package_version_invalid"),
    ],
)
def test_v5_rejects_invalid_root_or_version_json_type(
    tmp_path: Path,
    payload: object,
    error: str,
) -> None:
    target = tmp_path / "invalid-root.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        load_entity_archive(target)


def test_bundle_failure_leaves_existing_directory_untouched(tmp_path: Path) -> None:
    archive, repository, _ = _archive(tmp_path)
    package_dir = tmp_path / "portable"
    package_dir.mkdir()
    sentinel = package_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    binding = archive.profiles[0].content_bindings["technical_route"]
    resolved = repository.validate(binding.artifact_ref)
    (resolved.directory / "manifest.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(Exception):
        save_entity_archive_bundle(
            archive, package_dir, content_artifact_repository=repository
        )
    assert sentinel.read_text(encoding="utf-8") == "keep"
