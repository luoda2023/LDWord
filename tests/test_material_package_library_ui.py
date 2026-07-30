from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import material_package_library as library
from src.config.entity import AssetBinding, EntityArchive, EntityProfile
from src.config.image_materials import ImagePlacementMode
from src.config.scene import SceneWorkspace
from src.ui.bridge import PanelBridge
from src.ui.panels.assets_panel import AssetsPanel


def test_failed_package_creation_removes_only_its_owned_directory(
    monkeypatch,
    tmp_path,
):
    root = tmp_path / "config_library" / "material_packages"
    monkeypatch.setattr(library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    user_dir = root / "official" / "user"
    concurrent_target = user_dir / "concurrent-package" / "package.json"

    def fail_after_partial_write(_archive, target):
        target.write_bytes(b"partial package")
        concurrent_target.parent.mkdir(parents=True)
        concurrent_target.write_bytes(b"concurrent package")
        raise RuntimeError("injected save failure")

    monkeypatch.setattr(library, "save_entity_archive", fail_after_partial_write)

    with pytest.raises(RuntimeError, match="injected save failure"):
        library.create_material_package_in_library(
            EntityArchive(archive_name="Owned package"),
            mode_id="official",
            requested_id="owned-package",
        )

    assert not (user_dir / "owned-package").exists()
    assert concurrent_target.read_bytes() == b"concurrent package"


def test_generic_material_package_library_keeps_external_assets_as_paths(
    monkeypatch,
    tmp_path,
):
    root = tmp_path / "config_library" / "material_packages"
    monkeypatch.setattr(library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    external_image = tmp_path / "external" / "logo.png"
    external_image.parent.mkdir()
    external_image.write_bytes(b"not-copied")
    archive = EntityArchive(
        archive_name="学校公文资料",
        profiles=[
            EntityProfile(
                profile_id="default",
                profile_name="默认资料",
                asset_paths={"logo": str(external_image)},
                asset_bindings={
                    "logo": AssetBinding(
                        role="logo",
                        source_path=str(external_image),
                    )
                },
            )
        ],
    )

    entry = library.create_material_package_in_library(
        archive,
        mode_id="official",
        requested_id="school_notice",
    )

    assert entry.path == root / "official" / "user" / "school_notice" / "package.json"
    payload = json.loads(entry.path.read_text(encoding="utf-8"))
    assert payload["profiles"][0]["asset_paths"]["logo"] == str(external_image)
    assert not (entry.path.parent / "assets").exists()
    assert library.list_material_package_entries(mode_id="official") == (entry,)

    loaded = library.load_material_package_entry(entry)
    assert loaded.profiles[0].asset_paths["logo"] == str(external_image)
    loaded.archive_name = "已原子保存的学校公文资料"
    saved = library.save_material_package_entry(loaded, entry)
    assert saved.path == entry.path
    assert library.load_material_package_entry(saved).archive_name == (
        "已原子保存的学校公文资料"
    )

    duplicate = library.duplicate_material_package_entry(
        loaded,
        mode_id="official",
        name="学校公文资料副本",
    )
    assert duplicate.path != entry.path
    assert external_image.exists()

    library.delete_material_package_entry(entry)
    assert not entry.path.parent.exists()
    assert external_image.exists()


def test_generic_material_package_library_ignores_flat_files_and_reuses_the_id(
    monkeypatch,
    tmp_path,
):
    root = tmp_path / "config_library" / "material_packages"
    monkeypatch.setattr(library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    user_dir = root / "official" / "user"
    user_dir.mkdir(parents=True)
    flat_path = user_dir / "school_notice.material.json"
    library.save_entity_archive(
        EntityArchive(
            archive_id="school_notice",
            package_id="school_notice",
            archive_name="Flat package outside the library contract",
        ),
        flat_path,
    )

    entry = library.create_material_package_in_library(
        EntityArchive(archive_name="Canonical package"),
        mode_id="official",
        requested_id="school_notice",
    )

    assert entry.package_id == "school_notice"
    assert entry.path == user_dir / "school_notice" / "package.json"
    assert library.list_material_package_entries(mode_id="official") == (entry,)
    assert flat_path.exists()


@pytest.mark.parametrize("link_kind", ("file", "directory"))
def test_save_and_delete_reject_linked_package_paths_without_touching_sibling(
    monkeypatch,
    tmp_path,
    link_kind,
):
    root = tmp_path / "config_library" / "material_packages"
    monkeypatch.setattr(library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    sibling = library.create_material_package_in_library(
        EntityArchive(archive_name="Protected sibling"),
        mode_id="official",
        requested_id="protected",
    )
    protected_bytes = sibling.path.read_bytes()
    user_dir = library.material_package_user_dir("official")
    linked_dir = user_dir / "linked"
    linked_path = linked_dir / "package.json"
    try:
        if link_kind == "directory":
            linked_dir.symlink_to(sibling.path.parent, target_is_directory=True)
        else:
            linked_dir.mkdir()
            linked_path.symlink_to(sibling.path)
    except OSError as exc:
        pytest.skip(f"{link_kind} symlinks unavailable: {exc}")
    linked_entry = library.MaterialPackageLibraryEntry(
        package_id="linked",
        name="Linked package",
        path=linked_path,
        mode_id="official",
        source_type="user",
    )

    with pytest.raises(ValueError, match="material_package_path_link_or_reparse"):
        library.save_material_package_entry(
            EntityArchive(archive_name="Must not overwrite sibling"),
            linked_entry,
        )
    with pytest.raises(ValueError, match="material_package_path_link_or_reparse"):
        library.delete_material_package_entry(linked_entry)

    assert sibling.path.read_bytes() == protected_bytes
    assert sibling.path.parent.is_dir()


@pytest.mark.parametrize("link_method", ("is_symlink", "is_junction"))
def test_save_and_delete_fail_closed_on_detected_link_or_junction(
    monkeypatch,
    tmp_path,
    link_method,
):
    root = tmp_path / "config_library" / "material_packages"
    monkeypatch.setattr(library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    sibling = library.create_material_package_in_library(
        EntityArchive(archive_name="Protected sibling"),
        mode_id="official",
        requested_id="protected",
    )
    protected_bytes = sibling.path.read_bytes()
    original = getattr(Path, link_method, None)

    def detected(path):
        if path == sibling.path:
            return True
        return bool(original(path)) if callable(original) else False

    monkeypatch.setattr(Path, link_method, detected, raising=False)

    with pytest.raises(ValueError, match="material_package_path_link_or_reparse"):
        library.save_material_package_entry(
            EntityArchive(archive_name="Must not overwrite sibling"),
            sibling,
        )
    with pytest.raises(ValueError, match="material_package_path_link_or_reparse"):
        library.delete_material_package_entry(sibling)

    assert sibling.path.read_bytes() == protected_bytes
    assert sibling.path.parent.is_dir()


def test_assets_cards_share_restore_save_and_persist_the_current_package(
    qapp,
    monkeypatch,
    tmp_path,
):
    root = tmp_path / "config_library" / "material_packages"
    monkeypatch.setattr(library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    bridge = PanelBridge()
    bridge.set_current_scene(SceneWorkspace(), config_id="custom", emit_signal=False)
    panel = AssetsPanel(bridge)

    assert set(panel._material_persistence_actions) == {
        "fields",
        "content",
        "timeline",
        "images",
        "attachments",
    }
    fields_actions = panel._material_persistence_actions["fields"]
    assert fields_actions.restore_button.text() == "恢复"
    assert fields_actions.save_button.text() == "保存"
    assert not fields_actions.restore_button.isEnabled()
    assert not fields_actions.save_button.isEnabled()
    content_actions = panel._material_persistence_actions["content"]
    assert panel._content_card._header_actions_layout.indexOf(
        panel._add_content_material_btn
    ) < (
        panel._content_card._header_actions_layout.indexOf(content_actions)
    )
    original_name = panel._profile_name_edit.text()
    panel._profile_name_edit.setText("已修改资料")
    panel._run_scheduled_summary_refresh()
    assert fields_actions.restore_button.isEnabled()
    assert fields_actions.save_button.isEnabled()

    fields_actions.restore_button.click()
    assert panel._profile_name_edit.text() == original_name
    assert not fields_actions.restore_button.isEnabled()

    panel._profile_name_edit.setText("需要保存的资料")
    panel._run_scheduled_summary_refresh()
    fields_actions.save_button.click()

    entry = panel._current_archive_entry
    assert entry is not None
    assert entry.path.exists()
    saved = library.load_material_package_entry(entry)
    assert saved.profiles[0].profile_name == "需要保存的资料"
    assert not fields_actions.save_button.isEnabled()


def test_implicit_image_rule_defaults_do_not_make_loaded_or_restored_package_dirty(
    qapp,
):
    panel = AssetsPanel(PanelBridge())
    try:
        legacy = EntityArchive(profiles=[EntityProfile(image_material_rules={})])
        panel.set_archive(legacy)
        panel._capture_material_persistence_snapshot(legacy)

        actions = panel._material_persistence_actions["images"]
        assert panel._selected_profile().image_material_rules
        assert panel._image_rule_adaptive_check.isChecked()
        assert not actions.restore_button.isEnabled()
        assert not actions.save_button.isEnabled()

        panel._image_rule_adaptive_check.setChecked(False)
        qapp.processEvents()
        assert actions.restore_button.isEnabled()
        assert actions.save_button.isEnabled()

        actions.restore_button.click()
        qapp.processEvents()
        assert panel._image_rule_adaptive_check.isChecked()
        assert (
            panel._image_material_rules["image:logo"].placement.mode
            is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE
        )
        assert not actions.restore_button.isEnabled()
        assert not actions.save_button.isEnabled()
    finally:
        panel.close()
