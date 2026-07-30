from __future__ import annotations

import copy

from src.config.entity import EntityArchive, EntityProfile
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.assets_panel import AssetsPanel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _panel_with_persisted_profile() -> AssetsPanel:
    _app()
    panel = AssetsPanel(PanelBridge())
    assert panel.set_archive(
        EntityArchive(
            archive_id="package-1",
            archive_name="Package 1",
            profiles=[
                EntityProfile(
                    profile_id="profile-1",
                    profile_name="Profile 1",
                    fields={"existing": "before"},
                )
            ],
        )
    )
    panel._capture_material_persistence_snapshot()
    return panel


def test_set_archive_harvest_failure_does_not_partially_write_profile(
    monkeypatch,
) -> None:
    panel = _panel_with_persisted_profile()
    before_profiles = copy.deepcopy(panel._profiles)
    before_selection = panel.bridge.current_material_batch_selection()
    panel._profile_id_edit.setText("profile-after")
    panel._profile_name_edit.setText("Profile After")

    def fail_after_earlier_fields_would_have_been_written():
        raise RuntimeError("asset binding harvest failed")

    try:
        monkeypatch.setattr(
            panel,
            "_copy_asset_bindings",
            fail_after_earlier_fields_would_have_been_written,
        )

        assert panel.set_archive(
            EntityArchive(
                archive_id="replacement",
                profiles=[EntityProfile(profile_id="replacement-profile")],
            )
        ) is False

        assert panel._profiles == before_profiles
        assert panel.bridge.current_material_batch_selection() == before_selection
    finally:
        panel.close()


def test_prepared_discard_rejection_is_reported_and_keeps_rollback_evidence(
    monkeypatch,
) -> None:
    panel = _panel_with_persisted_profile()
    panel._profile_name_edit.setText("Unsaved Profile")
    assert panel.prepare_pending_material_changes("discard") is True
    prepared = panel._prepared_material_changes
    calls: list[str] = []

    try:
        monkeypatch.setattr(
            panel,
            "set_archive",
            lambda *_args, **_kwargs: calls.append("set_archive") or False,
        )
        monkeypatch.setattr(
            panel,
            "_capture_material_persistence_snapshot",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("rejected discard captured a success snapshot")
            ),
        )

        assert panel.commit_prepared_material_changes() is False

        assert calls == ["set_archive"]
        assert panel._prepared_material_changes is prepared
        assert prepared["committed"] is False
        assert panel.cancel_prepared_material_changes() is False
        assert panel._prepared_material_changes is prepared
        assert panel.prepare_pending_material_changes("discard") is False
        assert panel._prepared_material_changes is prepared
    finally:
        panel.close()


def test_prepared_rollback_rejection_is_reported_and_keeps_rollback_evidence(
    monkeypatch,
) -> None:
    panel = _panel_with_persisted_profile()
    panel._profile_name_edit.setText("Unsaved Profile")
    assert panel.prepare_pending_material_changes("discard") is True
    prepared = panel._prepared_material_changes
    before_entry = copy.deepcopy(panel._current_archive_entry)
    before_path = panel._current_archive_path
    calls: list[str] = []

    try:
        monkeypatch.setattr(
            panel,
            "set_archive",
            lambda *_args, **_kwargs: calls.append("set_archive") or False,
        )

        assert panel.rollback_prepared_material_changes() is False

        assert calls == ["set_archive"]
        assert panel._prepared_material_changes is prepared
        assert panel._current_archive_entry == before_entry
        assert panel._current_archive_path == before_path
        assert panel.cancel_prepared_material_changes() is False
        assert panel._prepared_material_changes is prepared
    finally:
        panel.close()


def test_cancel_retries_transient_discard_failure_before_clearing_evidence(
    monkeypatch,
) -> None:
    panel = _panel_with_persisted_profile()
    panel._profile_name_edit.setText("Unsaved Profile")
    assert panel.prepare_pending_material_changes("discard") is True
    prepared = panel._prepared_material_changes
    expected_archive = copy.deepcopy(prepared["archive"])
    original_set_archive = panel.set_archive
    attempts = 0

    def reject_once_then_restore(*args, **kwargs) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return False
        return original_set_archive(*args, **kwargs)

    try:
        monkeypatch.setattr(panel, "set_archive", reject_once_then_restore)

        assert panel.commit_prepared_material_changes() is False
        assert panel._prepared_material_changes is prepared
        assert panel.cancel_prepared_material_changes() is True

        assert attempts == 2
        assert panel._prepared_material_changes is None
        assert panel.current_archive() == expected_archive
    finally:
        panel.close()
