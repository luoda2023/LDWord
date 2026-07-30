from __future__ import annotations

from src.config import library as config_library
from src.qt_api import QWidget
from src.ui.main_window import MainWindow


def _close_clean(window: MainWindow, qapp) -> None:
    window.bridge.clear_scene_dirty()
    assets = window._loaded_panel_for_id("assets")
    if assets is not None and assets.has_pending_material_changes():
        assets._capture_material_persistence_snapshot()
    window.close()
    qapp.processEvents()


def test_scene_selector_cancel_preserves_dirty_scene_and_discard_switches(
    qapp,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        assert window._request_work_mode_change("exam") is True
        panel = window._ensure_panel_loaded_for_id("scene")
        scene = window.bridge.current_scene()
        scene.name = "UNSAVED_SENTINEL"
        window.bridge.set_current_scene(
            scene,
            config_id="exam",
            path=window.bridge.current_scene_path(),
            source=window.bridge.current_scene_source(),
            source_type=window.bridge.current_scene_source_type(),
            emit_signal=False,
        )
        window.bridge.set_scene_dirty(True)

        combo = panel._overview._combo
        target_index = combo.findData("exam_quiz")
        assert target_index >= 0
        monkeypatch.setattr(
            panel,
            "_prompt_pending_scene_action",
            lambda _reason: "cancel",
        )

        combo.setCurrentIndex(target_index)
        qapp.processEvents()

        assert combo.currentData() == "exam"
        assert window.bridge.current_scene_id() == "exam"
        assert window.bridge.current_scene().name == "UNSAVED_SENTINEL"
        assert window.bridge.is_scene_dirty() is True

        monkeypatch.setattr(
            panel,
            "_prompt_pending_scene_action",
            lambda _reason: "discard",
        )
        combo.setCurrentIndex(target_index)
        qapp.processEvents()

        assert window.bridge.current_scene_id() == "exam_quiz"
        assert window.bridge.current_scene().name != "UNSAVED_SENTINEL"
        assert window.bridge.is_scene_dirty() is False
    finally:
        _close_clean(window, qapp)


def test_scene_selector_save_commits_old_scene_before_switch(
    qapp,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "plans")
    window = MainWindow(enable_background_services=False)
    try:
        assert window._request_work_mode_change("exam") is True
        panel = window._ensure_panel_loaded_for_id("scene")
        scene = window.bridge.current_scene()
        scene.name = "SAVED_SENTINEL"
        window.bridge.set_current_scene(
            scene,
            config_id="exam",
            path=window.bridge.current_scene_path(),
            source=window.bridge.current_scene_source(),
            source_type=window.bridge.current_scene_source_type(),
            emit_signal=False,
        )
        window.bridge.set_scene_dirty(True)
        monkeypatch.setattr(
            panel,
            "_prompt_pending_scene_action",
            lambda _reason: "save",
        )
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": "exam_saved_copy",
        )
        combo = panel._overview._combo
        target_index = combo.findData("exam_quiz")
        assert target_index >= 0

        combo.setCurrentIndex(target_index)
        qapp.processEvents()

        saved = config_library.load_scene_from_library(
            "exam_saved_copy",
            mode_id="exam",
        )
        assert saved.name == "exam_saved_copy"
        assert window.bridge.current_scene_id() == "exam_quiz"
        assert window.bridge.is_scene_dirty() is False
    finally:
        _close_clean(window, qapp)


def test_scene_close_cancel_preserves_edit_and_discard_is_reversible(
    qapp,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        panel = window._ensure_panel_loaded_for_id("scene")
        scene = window.bridge.current_scene()
        scene.name = "CLOSE_SENTINEL"
        window.bridge.set_current_scene(
            scene,
            config_id=window.bridge.current_scene_id(),
            path=window.bridge.current_scene_path(),
            source=window.bridge.current_scene_source(),
            source_type=window.bridge.current_scene_source_type(),
            emit_signal=False,
        )
        window.bridge.set_scene_dirty(True)

        monkeypatch.setattr(
            panel,
            "_prompt_pending_scene_action",
            lambda _reason: "cancel",
        )
        assert panel.prepare_close_pending_changes() is False
        assert window.bridge.current_scene().name == "CLOSE_SENTINEL"
        assert window.bridge.is_scene_dirty() is True

        monkeypatch.setattr(
            panel,
            "_prompt_pending_scene_action",
            lambda _reason: "discard",
        )
        assert panel.prepare_close_pending_changes() is True
        assert panel.commit_close_pending_changes() is True
        assert window.bridge.is_scene_dirty() is False

        assert panel.rollback_close_pending_changes() is True
        assert window.bridge.current_scene().name == "CLOSE_SENTINEL"
        assert window.bridge.is_scene_dirty() is True
    finally:
        _close_clean(window, qapp)


class _ReversibleCloseParticipant:
    def __init__(self, events: list[str]):
        self.events = events

    def commit_close_pending_changes(self) -> bool:
        self.events.append("reversible.commit")
        return True

    def rollback_close_pending_changes(self) -> bool:
        self.events.append("reversible.rollback")
        return True

    def finalize_close_pending_changes(self) -> None:
        self.events.append("reversible.finalize")

    def cancel_prepared_close(self) -> None:
        self.events.append("reversible.cancel")


class _FailingIrreversibleCloseParticipant:
    def __init__(self, events: list[str]):
        self.events = events

    def commit_close_pending_changes(self) -> bool:
        self.events.append("irreversible.commit")
        return False

    def cancel_prepared_close(self) -> None:
        self.events.append("irreversible.cancel")


def test_close_commit_failure_rolls_back_reversible_participants_first():
    events: list[str] = []
    reversible = _ReversibleCloseParticipant(events)
    irreversible = _FailingIrreversibleCloseParticipant(events)

    assert (
        MainWindow._commit_prepared_panel_closes([irreversible, reversible]) is False
    )
    assert events == [
        "reversible.commit",
        "irreversible.commit",
        "irreversible.cancel",
        "reversible.rollback",
    ]


class _PreparedCloseFailure(QWidget):
    def prepare_close_pending_changes(self) -> bool:
        return True

    def commit_close_pending_changes(self) -> bool:
        return False

    def cancel_prepared_close(self) -> None:
        pass


def test_window_close_failure_restores_real_scene_and_material_edits(
    qapp,
    monkeypatch,
):
    window = MainWindow(
        enable_background_services=False,
        include_optional_panels=True,
    )
    failure = _PreparedCloseFailure()
    try:
        scene_panel = window._ensure_panel_loaded_for_id("scene")
        assets_panel = window._ensure_panel_loaded_for_id("assets")
        archive = assets_panel.current_archive()
        archive.profiles[0].fields["company_name"] = "TRANSACTION_SENTINEL"
        assets_panel.set_archive(archive)
        window.bridge.set_scene_dirty(True)
        monkeypatch.setattr(
            scene_panel,
            "_prompt_pending_scene_action",
            lambda _reason: "discard",
        )
        monkeypatch.setattr(
            assets_panel,
            "_prompt_pending_material_action",
            lambda _reason: "discard",
        )
        # Template occupies index 2.  Its failed irreversible commit must run
        # after Scene/Assets and force both reversible editors to roll back.
        window.register_panel(2, failure)

        assert window.close() is False
        qapp.processEvents()

        assert window.bridge.is_scene_dirty() is True
        assert assets_panel.has_pending_material_changes() is True
        assert (
            assets_panel.current_archive().profiles[0].fields["company_name"]
            == "TRANSACTION_SENTINEL"
        )
    finally:
        window.register_panel(2, QWidget())
        _close_clean(window, qapp)
