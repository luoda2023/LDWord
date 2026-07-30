from __future__ import annotations

from dataclasses import fields
import logging
from pathlib import Path

import pytest
from shiboken6 import isValid

from src.config.entity import EntityArchive, EntityProfile
from src.config import material_package_library
from src.config.material_package_library import MaterialPackageLibraryEntry
from src.qt_api import QApplication, QEvent
from src.shared.ui.toast import Toast
from src.ui.bridge import PanelBridge
from src.ui.panels.assets_panel import AssetsPanel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _panel(monkeypatch, tmp_path: Path) -> tuple[AssetsPanel, Path]:
    _app()
    root = tmp_path / "material_packages"
    monkeypatch.setattr(material_package_library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    panel = AssetsPanel(PanelBridge())
    assert panel.set_archive(
        EntityArchive(
            archive_id="package-1",
            archive_name="Package 1",
            profiles=[
                EntityProfile(
                    profile_id="profile-1",
                    profile_name="Profile 1",
                )
            ],
        )
    )
    panel._material_persistence.replace_identity(None, "")
    panel._capture_material_persistence_snapshot()
    return panel, root


def _existing_user_target(
    panel: AssetsPanel,
    root: Path,
    payload: bytes = b"old bytes",
) -> tuple[MaterialPackageLibraryEntry, Path]:
    target = root / "custom" / "user" / "package-1" / "package.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)
    entry = MaterialPackageLibraryEntry(
        package_id="package-1",
        name="Package 1",
        path=target,
        mode_id="custom",
        source_type="user",
    )
    panel._material_persistence.replace_identity(entry, str(target))
    panel._capture_material_persistence_snapshot()
    panel._profile_name_edit.setText("Unsaved profile")
    return entry, target


def _fail_first_publication_snapshot(monkeypatch, published: list[bool]) -> list[int]:
    real_capture = material_package_library.capture_material_package_entry_snapshot
    failures = [0]

    def capture(entry):
        if published[0] and failures[0] == 0:
            failures[0] += 1
            raise OSError("first post-write snapshot failed")
        return real_capture(entry)

    monkeypatch.setattr(
        "src.ui.panels.assets.persistence_presenter."
        "capture_material_package_entry_snapshot",
        capture,
    )
    return failures


def _fail_first_creator_snapshot(monkeypatch) -> list[int]:
    real_capture = material_package_library.capture_material_package_entry_snapshot
    failures = [0]

    def capture(entry):
        if failures[0] == 0:
            failures[0] += 1
            raise OSError("first creator snapshot failed")
        return real_capture(entry)

    monkeypatch.setattr(
        material_package_library,
        "capture_material_package_entry_snapshot",
        capture,
    )
    return failures


def _interleave_second_writer_after_creator_receipt(monkeypatch) -> dict[str, object]:
    real_create = (
        material_package_library.create_material_package_in_library_with_receipt
    )
    observed: dict[str, object] = {}

    def create_then_publish_b(*args, **kwargs):
        receipt = real_create(*args, **kwargs)
        material_package_library.save_material_package_entry(
            EntityArchive(
                archive_name="Writer B",
                profiles=[EntityProfile(profile_name="Writer B profile")],
            ),
            receipt.entry,
        )
        observed["receipt_a"] = receipt
        observed["entry"] = receipt.entry
        observed["bytes_b"] = receipt.entry.path.read_bytes()
        return receipt

    monkeypatch.setattr(
        material_package_library,
        "create_material_package_in_library_with_receipt",
        create_then_publish_b,
    )
    return observed


@pytest.mark.parametrize("failing_stage", ["capture", "refresh"])
def test_direct_existing_save_recovers_disk_identity_and_baseline_after_adoption_failure(
    monkeypatch,
    tmp_path,
    failing_stage: str,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    entry, target = _existing_user_target(panel, root)
    baseline = panel._persisted_archive_snapshot

    def publish(_archive, current_entry):
        assert current_entry == entry
        target.write_bytes(b"published bytes")
        return current_entry

    monkeypatch.setattr(
        "src.ui.panels.assets.persistence_presenter.save_material_package_entry",
        publish,
    )
    if failing_stage == "capture":
        monkeypatch.setattr(
            panel,
            "_capture_material_persistence_snapshot",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("capture failed")
            ),
        )
    else:
        monkeypatch.setattr(
            panel,
            "_refresh_archive_selector_from_library",
            lambda: (_ for _ in ()).throw(RuntimeError("refresh failed")),
        )

    try:
        assert panel._material_persistence.save_current_package() is False
        assert target.read_bytes() == b"old bytes"
        assert panel._current_archive_entry == entry
        assert panel._current_archive_path == str(target)
        assert panel._persisted_archive_snapshot == baseline
    finally:
        panel.close()


def test_direct_new_save_deletes_only_unchanged_orphan_when_activation_rejects(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    baseline = panel._persisted_archive_snapshot
    panel._profile_name_edit.setText("Unsaved new package")
    monkeypatch.setattr(panel, "_activate_archive_entry", lambda _entry: False)

    try:
        assert panel._material_persistence.save_current_package() is False
        assert not tuple(root.rglob("package.json"))
        assert panel._current_archive_entry is None
        assert panel._current_archive_path == ""
        assert panel._persisted_archive_snapshot == baseline
    finally:
        panel.close()


def test_direct_new_save_recovers_editor_and_disk_after_post_activation_failure(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    baseline = panel._persisted_archive_snapshot
    panel._profile_name_edit.setText("Unsaved new package")
    expected_editor = panel.current_archive()
    monkeypatch.setattr(
        panel,
        "_refresh_archive_selector_from_library",
        lambda: (_ for _ in ()).throw(RuntimeError("refresh failed")),
    )

    try:
        assert panel._material_persistence.save_current_package() is False
        assert not tuple(root.rglob("package.json"))
        assert panel._current_archive_entry is None
        assert panel._persisted_archive_snapshot == baseline
        assert panel.current_archive() == expected_editor
    finally:
        panel.close()


def test_direct_existing_save_retries_first_publication_snapshot_failure(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    entry, target = _existing_user_target(panel, root)
    published = [False]
    failures = _fail_first_publication_snapshot(monkeypatch, published)

    def publish(_archive, current_entry):
        assert current_entry == entry
        target.write_bytes(b"published bytes")
        published[0] = True
        return current_entry

    monkeypatch.setattr(
        "src.ui.panels.assets.persistence_presenter.save_material_package_entry",
        publish,
    )
    monkeypatch.setattr(
        panel,
        "_capture_material_persistence_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("post-write adoption failed")
        ),
    )

    try:
        assert panel._material_persistence.save_current_package() is False
        assert failures == [1]
        assert target.read_bytes() == b"old bytes"
        assert panel._material_persistence.publication_recovery_state is None
    finally:
        panel.close()


def test_direct_new_save_retries_first_snapshot_and_cleans_confirmed_orphan(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    failures = _fail_first_creator_snapshot(monkeypatch)
    panel._profile_name_edit.setText("Unsaved new package")
    monkeypatch.setattr(panel, "_activate_archive_entry", lambda _entry: False)

    try:
        assert panel._material_persistence.save_current_package() is False
        assert failures == [1]
        assert not tuple(root.rglob("package.json"))
        assert panel._material_persistence.publication_recovery_state is None
    finally:
        panel.close()


def test_prepared_existing_save_retries_first_publication_snapshot_failure(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    entry, target = _existing_user_target(panel, root)
    assert panel.prepare_pending_material_changes("save") is True
    published = [False]
    failures = _fail_first_publication_snapshot(monkeypatch, published)

    def publish(_archive, current_entry):
        assert current_entry == entry
        target.write_bytes(b"published bytes")
        published[0] = True
        return current_entry

    monkeypatch.setattr(
        "src.ui.panels.assets.persistence_presenter.save_material_package_entry",
        publish,
    )
    monkeypatch.setattr(
        panel,
        "_capture_material_persistence_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("post-write adoption failed")
        ),
    )

    try:
        assert panel.commit_prepared_material_changes() is False
        assert failures == [1]
        assert target.read_bytes() == b"old bytes"
        assert panel._prepared_material_changes is None
    finally:
        panel.close()


def test_prepared_new_save_retries_first_snapshot_and_removes_known_publication(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    panel._profile_name_edit.setText("Unsaved new package")
    assert panel.prepare_pending_material_changes("save") is True
    failures = _fail_first_creator_snapshot(monkeypatch)
    monkeypatch.setattr(panel, "_activate_archive_entry", lambda _entry: False)

    try:
        assert panel.commit_prepared_material_changes() is False
        assert failures == [1]
        assert not tuple(root.rglob("package.json"))
        assert panel._prepared_material_changes is None
    finally:
        panel.close()


def test_direct_new_persistent_creator_snapshot_failure_cleans_owned_target(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    panel._profile_name_edit.setText("Unsaved new package")
    monkeypatch.setattr(
        material_package_library,
        "capture_material_package_entry_snapshot",
        lambda _entry: (_ for _ in ()).throw(OSError("snapshot unavailable")),
    )

    try:
        assert panel._material_persistence.save_current_package() is False
        assert not tuple(root.rglob("package.json"))
        assert panel._current_archive_entry is None
        assert panel._material_persistence.publication_recovery_state is None
    finally:
        panel.close()


def test_prepared_new_persistent_creator_snapshot_failure_cleans_before_return(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    panel._profile_name_edit.setText("Unsaved new package")
    assert panel.prepare_pending_material_changes("save") is True
    monkeypatch.setattr(
        material_package_library,
        "capture_material_package_entry_snapshot",
        lambda _entry: (_ for _ in ()).throw(OSError("snapshot unavailable")),
    )

    try:
        assert panel.commit_prepared_material_changes() is False
        assert not tuple(root.rglob("package.json"))
        assert panel._prepared_material_changes is None
    finally:
        panel.close()


def test_direct_new_creator_receipt_never_claims_interleaved_writer_b(
    monkeypatch,
    tmp_path,
) -> None:
    panel, _root = _panel(monkeypatch, tmp_path)
    panel._profile_name_edit.setText("Writer A")
    observed = _interleave_second_writer_after_creator_receipt(monkeypatch)
    monkeypatch.setattr(panel, "_activate_archive_entry", lambda _entry: False)

    try:
        assert panel._material_persistence.save_current_package() is False
        entry = observed["entry"]
        assert entry.path.read_bytes() == observed["bytes_b"]
        evidence = panel._material_persistence.publication_recovery_state
        assert evidence is not None
        assert evidence["receipt"] == observed["receipt_a"]
        assert evidence["recovery_required"] is True
    finally:
        panel.close()


def test_prepared_new_creator_receipt_never_claims_interleaved_writer_b(
    monkeypatch,
    tmp_path,
) -> None:
    panel, _root = _panel(monkeypatch, tmp_path)
    panel._profile_name_edit.setText("Writer A")
    assert panel.prepare_pending_material_changes("save") is True
    observed = _interleave_second_writer_after_creator_receipt(monkeypatch)
    monkeypatch.setattr(panel, "_activate_archive_entry", lambda _entry: False)

    try:
        assert panel.commit_prepared_material_changes() is False
        entry = observed["entry"]
        assert entry.path.read_bytes() == observed["bytes_b"]
        evidence = panel._prepared_material_changes
        assert evidence is not None
        assert evidence["published_snapshot"] == observed["receipt_a"].snapshot
        assert evidence["revision_conflict"] is True
        assert evidence["recovery_required"] is True
    finally:
        panel.close()


def test_prepare_revision_conflict_never_calls_writer_or_overwrites_external_bytes(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    _entry, target = _existing_user_target(panel, root)
    assert panel.prepare_pending_material_changes("save") is True
    target.write_bytes(b"external bytes")
    calls: list[str] = []
    monkeypatch.setattr(
        panel,
        "save_pending_material_changes",
        lambda: calls.append("writer") or True,
    )

    try:
        assert panel.commit_prepared_material_changes() is False
        assert calls == []
        assert target.read_bytes() == b"external bytes"
    finally:
        panel.close()


def test_rollback_revision_conflict_never_overwrites_external_update(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    entry, target = _existing_user_target(panel, root)
    assert panel.prepare_pending_material_changes("save") is True

    def publish_then_external_update() -> bool:
        target.write_bytes(b"owned publication")
        panel._material_change_transaction.record_publication(entry)
        target.write_bytes(b"external update after publication")
        return False

    monkeypatch.setattr(
        panel,
        "save_pending_material_changes",
        publish_then_external_update,
    )

    try:
        assert panel.commit_prepared_material_changes() is False
        assert target.read_bytes() == b"external update after publication"
        state = panel._prepared_material_changes
        assert state is not None
        assert state["recovery_required"] is True
        assert state["revision_conflict"] is True
    finally:
        panel.close()


def test_new_package_rollback_never_deletes_externally_replaced_publication(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    panel._profile_name_edit.setText("Unsaved new package")
    assert panel.prepare_pending_material_changes("save") is True
    target = root / "custom" / "user" / "known" / "package.json"
    entry = MaterialPackageLibraryEntry(
        package_id="known",
        name="Known",
        path=target,
        mode_id="custom",
        source_type="user",
    )

    def publish_then_external_update() -> bool:
        target.parent.mkdir(parents=True)
        target.write_bytes(b"owned publication")
        panel._material_change_transaction.record_publication(entry)
        target.write_bytes(b"external replacement")
        return False

    monkeypatch.setattr(
        panel,
        "save_pending_material_changes",
        publish_then_external_update,
    )

    try:
        assert panel.commit_prepared_material_changes() is False
        assert target.read_bytes() == b"external replacement"
        assert target.parent.exists()
    finally:
        panel.close()


def test_unconfirmed_prepared_publication_never_claims_external_bytes(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    _entry, target = _existing_user_target(panel, root)
    assert panel.prepare_pending_material_changes("save") is True

    def external_update_then_report_false() -> bool:
        target.write_bytes(b"external bytes without publication evidence")
        return False

    monkeypatch.setattr(
        panel,
        "save_pending_material_changes",
        external_update_then_report_false,
    )

    try:
        assert panel.commit_prepared_material_changes() is False
        assert target.read_bytes() == b"external bytes without publication evidence"
        state = panel._prepared_material_changes
        assert state is not None
        assert state["recovery_required"] is True
        assert state["revision_conflict"] is True
        assert state["publication_confirmed"] is False
    finally:
        panel.close()


def test_created_package_adoption_rejection_removes_only_confirmed_revision(
    monkeypatch,
    tmp_path,
) -> None:
    panel, _root = _panel(monkeypatch, tmp_path)
    receipt = material_package_library.create_material_package_in_library_with_receipt(
        EntityArchive(
            archive_name="Created package",
            profiles=[EntityProfile(profile_name="Profile")],
        ),
        mode_id="custom",
        requested_id="created-package",
    )
    entry = receipt.entry
    sibling = entry.path.parent / "external.txt"
    sibling.write_bytes(b"preserve sibling")
    baseline = panel._persisted_archive_snapshot
    monkeypatch.setattr(panel, "_activate_archive_entry", lambda _entry: False)

    try:
        assert panel._material_persistence.adopt_created_package(receipt) is False
        assert not entry.path.exists()
        assert sibling.read_bytes() == b"preserve sibling"
        assert panel._current_archive_entry is None
        assert panel._persisted_archive_snapshot == baseline
    finally:
        panel.close()


def test_restore_rejection_never_emits_success_and_keeps_actions_dirty(
    monkeypatch,
    tmp_path,
) -> None:
    panel, _root = _panel(monkeypatch, tmp_path)
    panel._profile_name_edit.setText("Unsaved profile")
    panel._run_scheduled_summary_refresh()
    successes: list[str] = []
    monkeypatch.setattr(panel, "set_archive", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(Toast, "show_success", successes.append)

    try:
        assert panel._restore_material_section("fields") is False
        assert successes == []
        assert panel._material_persistence_actions["fields"].restore_button.isEnabled()
    finally:
        panel.close()


def test_refresh_failure_logs_and_disables_every_persistence_action(
    monkeypatch,
    tmp_path,
    caplog,
) -> None:
    panel, _root = _panel(monkeypatch, tmp_path)
    panel._profile_name_edit.setText("Unsaved profile")
    panel._run_scheduled_summary_refresh()
    assert panel._material_persistence_actions["fields"].save_button.isEnabled()
    monkeypatch.setattr(
        panel,
        "current_archive",
        lambda: (_ for _ in ()).throw(RuntimeError("projection failed")),
    )

    try:
        with caplog.at_level(logging.ERROR):
            panel._material_persistence.refresh_actions()
        assert "failed to refresh material persistence actions" in caplog.text
        assert all(
            not actions.save_button.isEnabled()
            and not actions.restore_button.isEnabled()
            for actions in panel._material_persistence_actions.values()
        )
    finally:
        panel.close()


def test_direct_save_recovers_then_reraises_programming_errors(
    monkeypatch,
    tmp_path,
) -> None:
    panel, root = _panel(monkeypatch, tmp_path)
    _entry, target = _existing_user_target(panel, root)
    monkeypatch.setattr(
        "src.ui.panels.assets.persistence_presenter.save_material_package_entry",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            NameError("undefined implementation symbol")
        ),
    )

    try:
        with pytest.raises(NameError, match="undefined implementation symbol"):
            panel._material_persistence.save_current_package()
        assert target.read_bytes() == b"old bytes"
    finally:
        panel.close()


def test_archive_refresh_timer_is_owned_stopped_on_close_and_ports_are_weak(
    monkeypatch,
    tmp_path,
) -> None:
    panel, _root = _panel(monkeypatch, tmp_path)
    for coordinator in (
        panel._material_persistence,
        panel._material_change_transaction,
    ):
        port = coordinator._port
        for field in fields(port):
            callback = getattr(port, field.name)
            closure = getattr(callback, "__closure__", None) or ()
            assert all(cell.cell_contents is not panel for cell in closure)
    with pytest.raises(AttributeError):
        panel._current_archive_entry = None
    with pytest.raises(TypeError):
        panel._material_persistence_actions["unexpected"] = object()

    panel._on_material_package_library_path_changed()
    assert panel._material_package_library_refresh_timer.isActive()
    panel.close()
    assert not panel._material_package_library_refresh_timer.isActive()


def test_pending_archive_refresh_is_cancelled_when_panel_is_deleted(
    monkeypatch,
    tmp_path,
) -> None:
    panel, _root = _panel(monkeypatch, tmp_path)
    panel._on_material_package_library_path_changed()
    timer = panel._material_package_library_refresh_timer
    assert timer.isActive()

    panel.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    assert not isValid(timer)
