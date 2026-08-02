from __future__ import annotations

import copy
from pathlib import Path

import pytest
from PySide6.QtTest import QTest

from src.config import library as config_library
from src.qt_api import QWidget
from src.ui.bridge import PanelBridge
from src.ui.main_window import MainWindow, WORK_MODE_DIRTY_SAVE
from src.ui.panels import scene_panel as scene_panel_module
from src.ui.panels import scene_session_coordinator as scene_session_module
from src.ui.panels.scene_panel import ScenePanel


BUILTIN_SCENES = (
    ("custom", "custom"),
    ("exam", "exam"),
    ("exam", "exam_quiz"),
    ("exam", "exam_term"),
    ("thesis", "thesis"),
    ("bidding", "bidding"),
    ("official", "official"),
    ("technical", "technical"),
    ("report", "report"),
)


@pytest.fixture
def isolated_scene_config_library(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "config_library"
    monkeypatch.setattr(config_library, "TEMPLATE_LIBRARY_DIR", root / "templates")
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", root / "plans")
    config_library.ensure_scene_library()
    return root


def _open_scene_panel(mode_id: str, scene_id: str) -> tuple[PanelBridge, ScenePanel]:
    bridge = PanelBridge()
    bridge.set_current_work_mode(mode_id, emit_signal=False)
    entry = config_library.get_scene_entry(scene_id, mode_id=mode_id)
    assert entry is not None
    assert entry.source_type == "builtin"
    scene = config_library.load_scene_from_library(scene_id, mode_id=mode_id)
    bridge.set_current_scene(
        scene,
        config_id=scene_id,
        path=str(entry.path),
        source="library",
        source_type=entry.source_type,
        emit_signal=False,
    )
    panel = ScenePanel(bridge)
    bridge.commit_pending_work_mode_transition()
    return bridge, panel


def _open_owned_user_scene_panel(
    *,
    scene_id: str,
    name: str,
) -> tuple[PanelBridge, ScenePanel, Path]:
    scene = config_library.load_scene_from_library("exam", mode_id="exam")
    scene.name = name
    entry = config_library.save_scene_to_library(
        scene,
        scene_id=scene_id,
        mode_id="exam",
        expected_absent=True,
    )
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    bridge.set_current_scene(
        config_library.load_scene_from_library(scene_id, mode_id="exam"),
        config_id=scene_id,
        path=str(entry.path),
        source="library",
        source_type="user",
        emit_signal=False,
    )
    panel = ScenePanel(bridge)
    bridge.commit_pending_work_mode_transition()
    return bridge, panel, entry.path


def _mark_scene_dirty(bridge: PanelBridge, *, description: str) -> None:
    scene = bridge.current_scene()
    scene.description = description
    bridge.set_current_scene(
        scene,
        config_id=bridge.current_scene_id(),
        path=bridge.current_scene_path(),
        source=bridge.current_scene_source(),
        source_type=bridge.current_scene_source_type(),
        emit_signal=False,
    )
    bridge.set_scene_dirty(True)


def _dispose_panel(bridge: PanelBridge, panel: ScenePanel, qapp) -> None:
    panel.cancel_prepared_scene_changes()
    bridge.clear_scene_dirty()
    panel.close()
    qapp.processEvents()


def _close_clean(window: MainWindow, qapp) -> None:
    window.bridge.clear_scene_dirty()
    assets = window._loaded_panel_for_id("assets")
    if assets is not None and assets.has_pending_material_changes():
        assets._capture_material_persistence_snapshot()
    window.close()
    qapp.processEvents()


def test_owned_user_scene_autosaves_after_an_edit_burst(
    qapp,
    isolated_scene_config_library,
):
    scene_id = "autosave_owned_plan"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="自动保存方案",
    )
    try:
        _mark_scene_dirty(bridge, description="autosaved-in-place")

        assert panel._scene_autosave_state == "pending"
        assert panel._scene_autosave_timer.isActive()

        panel._scene_autosave_timer.start(0)
        qapp.processEvents()

        persisted = config_library.load_scene_from_library(
            scene_id,
            mode_id="exam",
        )
        assert persisted.description == "autosaved-in-place"
        assert path.exists()
        assert bridge.is_scene_dirty() is False
        assert panel._scene_autosave_state == "saved"
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_builtin_scene_first_autosave_creates_owned_copy_without_prompt(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel = _open_scene_panel("custom", "custom")
    builtin_path = Path(bridge.current_scene_path())
    builtin_bytes = builtin_path.read_bytes()
    monkeypatch.setattr(
        panel,
        "_prompt_scene_save_as_name",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("autosave must not prompt for a copy name")
        ),
    )
    try:
        _mark_scene_dirty(bridge, description="autosaved-user-copy")

        assert panel.flush_pending_scene_autosave() is True

        copied_id = bridge.current_scene_id()
        assert copied_id and copied_id != "custom"
        assert bridge.current_scene_source_type() == "user"
        assert builtin_path.read_bytes() == builtin_bytes
        persisted = config_library.load_scene_from_library(
            copied_id,
            mode_id="custom",
        )
        assert persisted.description == "autosaved-user-copy"
        assert bridge.is_scene_dirty() is False
        assert panel._scene_autosave_state == "saved"
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_autosave_failure_keeps_dirty_draft_and_reports_failed_state(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "autosave_failure_plan"
    bridge, panel, _path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="自动保存失败方案",
    )
    try:
        _mark_scene_dirty(bridge, description="must-remain-in-memory")
        monkeypatch.setattr(
            panel,
            "prepare_pending_scene_changes",
            lambda *_args, **_kwargs: False,
        )

        assert panel.flush_pending_scene_autosave() is False

        persisted = config_library.load_scene_from_library(
            scene_id,
            mode_id="exam",
        )
        assert persisted.description != "must-remain-in-memory"
        assert bridge.current_scene().description == "must-remain-in-memory"
        assert bridge.is_scene_dirty() is True
        assert panel._scene_autosave_state == "failed"
    finally:
        _dispose_panel(bridge, panel, qapp)


@pytest.mark.parametrize(("mode_id", "scene_id"), BUILTIN_SCENES)
def test_every_builtin_manual_save_forks_to_an_owned_user_scene(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
    mode_id: str,
    scene_id: str,
):
    bridge, panel = _open_scene_panel(mode_id, scene_id)
    builtin_path = Path(bridge.current_scene_path())
    builtin_bytes = builtin_path.read_bytes()
    fork_name = f"user_copy_{scene_id}"
    sentinel = f"forked:{mode_id}:{scene_id}"
    try:
        _mark_scene_dirty(bridge, description=sentinel)
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": fork_name,
        )

        qapp.processEvents()
        assert not hasattr(panel._overview, "_save_scene_btn")
        assert panel.save_current_scene() is True
        qapp.processEvents()

        fork_path = config_library.scene_user_dir(mode_id) / f"{fork_name}.json"
        persisted = config_library.load_scene_from_library(
            fork_name,
            mode_id=mode_id,
        )
        assert fork_path.is_file()
        assert persisted.scene_id == fork_name
        assert persisted.name == fork_name
        assert persisted.description == sentinel
        assert builtin_path.read_bytes() == builtin_bytes
        assert bridge.current_scene_id() == fork_name
        assert bridge.current_scene_path() == str(fork_path)
        assert bridge.current_scene_source() == "library"
        assert bridge.current_scene_source_type() == "user"
        assert bridge.current_scene() == persisted
        assert bridge.is_scene_dirty() is False
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_builtin_save_as_cancel_keeps_the_exact_dirty_draft_and_writes_nothing(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel = _open_scene_panel("exam", "exam")
    builtin_path = Path(bridge.current_scene_path())
    builtin_bytes = builtin_path.read_bytes()
    sentinel = "cancelled-save-as-draft"
    try:
        _mark_scene_dirty(bridge, description=sentinel)
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": None,
        )

        assert panel.save_current_scene() is False

        assert list(config_library.scene_user_dir("exam").glob("*.json")) == []
        assert builtin_path.read_bytes() == builtin_bytes
        assert bridge.current_scene_id() == "exam"
        assert bridge.current_scene_source_type() == "builtin"
        assert bridge.current_scene().description == sentinel
        assert bridge.is_scene_dirty() is True
        assert panel._scene_session.prepared_changes is None
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_standard_save_shortcut_uses_the_same_builtin_fork_transaction(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel = _open_scene_panel("exam", "exam")
    try:
        _mark_scene_dirty(bridge, description="shortcut-saved-draft")
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": "shortcut_copy",
        )

        panel._save_scene_shortcut.activated.emit()
        qapp.processEvents()

        persisted = config_library.load_scene_from_library(
            "shortcut_copy",
            mode_id="exam",
        )
        assert persisted.description == "shortcut-saved-draft"
        assert bridge.current_scene_id() == "shortcut_copy"
        assert bridge.current_scene_source_type() == "user"
        assert bridge.is_scene_dirty() is False
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_user_scene_manual_save_updates_in_place_without_save_as(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    base = config_library.load_scene_from_library("exam", mode_id="exam")
    base.name = "owned_user"
    entry = config_library.save_scene_to_library(
        base,
        scene_id="owned_user",
        mode_id="exam",
        expected_absent=True,
    )
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    bridge.set_current_scene(
        config_library.load_scene_from_library("owned_user", mode_id="exam"),
        config_id="owned_user",
        path=str(entry.path),
        source="library",
        source_type="user",
        emit_signal=False,
    )
    panel = ScenePanel(bridge)
    bridge.commit_pending_work_mode_transition()
    before_files = tuple(config_library.scene_user_dir("exam").glob("*.json"))
    try:
        _mark_scene_dirty(bridge, description="in-place-update")
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("an authoritative user scene must save in place")
            ),
        )

        assert panel.save_current_scene() is True

        after_files = tuple(config_library.scene_user_dir("exam").glob("*.json"))
        persisted = config_library.load_scene_from_library(
            "owned_user",
            mode_id="exam",
        )
        assert after_files == before_files
        assert persisted.description == "in-place-update"
        assert bridge.current_scene_id() == "owned_user"
        assert bridge.current_scene_path() == str(entry.path)
        assert bridge.current_scene_source_type() == "user"
        assert bridge.is_scene_dirty() is False
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_manual_save_publishes_one_coherent_scene_for_workbench_consumers(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel = _open_scene_panel("exam", "exam")
    observations: list[tuple[str, str, str, bool, bool]] = []
    try:
        _mark_scene_dirty(bridge, description="coherent-publication")
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": "coherent_copy",
        )
        bridge.scene_changed.connect(
            lambda scene: observations.append(
                (
                    scene.scene_id,
                    bridge.current_scene_id(),
                    bridge.current_scene_source_type(),
                    bridge.is_scene_dirty(),
                    bridge.current_scene() == scene,
                )
            )
        )

        assert panel.save_current_scene() is True

        assert observations == [
            ("coherent_copy", "coherent_copy", "user", False, True)
        ]
        assert panel._current_scene == bridge.current_scene()
        assert panel._overview._combo.currentData() == "coherent_copy"
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_manual_save_updates_the_real_workbench_scene_context(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        workbench = window._ensure_panel_loaded_for_id("workbench")
        assert window._request_work_mode_change("exam") is True
        panel = window._ensure_panel_loaded_for_id("scene")
        _mark_scene_dirty(window.bridge, description="real-workbench-publication")
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": "workbench_copy",
        )

        assert panel.save_current_scene() is True
        qapp.processEvents()

        persisted = config_library.load_scene_from_library(
            "workbench_copy",
            mode_id="exam",
        )
        assert window.bridge.current_scene_id() == "workbench_copy"
        assert window.bridge.current_scene_source_type() == "user"
        assert window.bridge.current_scene() == persisted
        assert workbench._current_scene == persisted
        assert workbench._quick_execution_detail.current_scene() == persisted
        assert workbench._quick_execution_detail.current_scene_id() == "workbench_copy"
    finally:
        _close_clean(window, qapp)


def test_selector_save_forks_builtin_before_switching_to_the_requested_scene(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel = _open_scene_panel("exam", "exam")
    builtin_path = Path(bridge.current_scene_path())
    builtin_bytes = builtin_path.read_bytes()
    try:
        _mark_scene_dirty(bridge, description="selector-saved-draft")
        monkeypatch.setattr(panel, "_prompt_pending_scene_action", lambda _reason: "save")
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": "selector_copy",
        )
        combo = panel._overview._combo
        target_index = combo.findData("exam_quiz")
        assert target_index >= 0

        combo.setCurrentIndex(target_index)
        qapp.processEvents()

        saved = config_library.load_scene_from_library(
            "selector_copy",
            mode_id="exam",
        )
        assert saved.description == "selector-saved-draft"
        assert builtin_path.read_bytes() == builtin_bytes
        assert bridge.current_scene_id() == "exam_quiz"
        assert bridge.current_scene_source_type() == "builtin"
        assert bridge.is_scene_dirty() is False
        assert combo.currentData() == "exam_quiz"
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_work_mode_save_forks_builtin_in_the_old_mode_before_switching(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        assert window._request_work_mode_change("exam") is True
        panel = window._ensure_panel_loaded_for_id("scene")
        builtin_path = Path(window.bridge.current_scene_path())
        builtin_bytes = builtin_path.read_bytes()
        _mark_scene_dirty(window.bridge, description="mode-switch-saved-draft")
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda _mode: WORK_MODE_DIRTY_SAVE,
        )
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": "mode_switch_copy",
        )

        assert window._request_work_mode_change("thesis") is True
        qapp.processEvents()

        saved = config_library.load_scene_from_library(
            "mode_switch_copy",
            mode_id="exam",
        )
        assert saved.description == "mode-switch-saved-draft"
        assert builtin_path.read_bytes() == builtin_bytes
        assert window.bridge.current_work_mode_id() == "thesis"
        assert window.bridge.current_scene_id() == "thesis"
        assert window.bridge.current_scene_source_type() == "builtin"
        assert window.bridge.is_scene_dirty() is False
    finally:
        _close_clean(window, qapp)


def test_work_mode_scene_finalize_failure_rolls_back_and_cancels_switch(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        panel = window._ensure_panel_loaded_for_id("scene")
        original_mode_id = window.bridge.current_work_mode_id()
        original_scene_id = window.bridge.current_scene_id()
        original_source_type = window.bridge.current_scene_source_type()
        _mark_scene_dirty(
            window.bridge,
            description="finalize-failure-draft",
        )
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda _mode: WORK_MODE_DIRTY_SAVE,
        )
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": "finalize_failure_copy",
        )
        monkeypatch.setattr(
            window.bridge,
            "finalize_scene_publication",
            lambda _transaction: (_ for _ in ()).throw(
                RuntimeError("injected mode-save finalize failure")
            ),
        )

        assert window._request_work_mode_change("exam") is False

        target = (
            config_library.scene_user_dir(original_mode_id)
            / "finalize_failure_copy.json"
        )
        assert target.exists() is False
        assert window.bridge.current_work_mode_id() == original_mode_id
        assert window.bridge.current_scene_id() == original_scene_id
        assert window.bridge.current_scene_source_type() == original_source_type
        assert window.bridge.current_scene().description == "finalize-failure-draft"
        assert window.bridge.is_scene_dirty() is True
        assert window.bridge._active_scene_publication is None
        assert panel._scene_session.prepared_changes is None
    finally:
        _close_clean(window, qapp)


def test_close_save_forks_builtin_and_allows_close(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    assert window._request_work_mode_change("exam") is True
    panel = window._ensure_panel_loaded_for_id("scene")
    builtin_path = Path(window.bridge.current_scene_path())
    builtin_bytes = builtin_path.read_bytes()
    _mark_scene_dirty(window.bridge, description="close-saved-draft")
    monkeypatch.setattr(panel, "_prompt_pending_scene_action", lambda _reason: "save")
    monkeypatch.setattr(
        panel,
        "_prompt_scene_save_as_name",
        lambda _reason="": "close_copy",
    )

    assert window.close() is True
    qapp.processEvents()

    saved = config_library.load_scene_from_library("close_copy", mode_id="exam")
    assert saved.description == "close-saved-draft"
    assert builtin_path.read_bytes() == builtin_bytes
    assert window._close_accepted is True


def test_close_save_as_cancel_rejects_close_and_preserves_builtin_draft(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        assert window._request_work_mode_change("exam") is True
        panel = window._ensure_panel_loaded_for_id("scene")
        builtin_path = Path(window.bridge.current_scene_path())
        builtin_bytes = builtin_path.read_bytes()
        _mark_scene_dirty(window.bridge, description="cancelled-close-draft")
        monkeypatch.setattr(panel, "_prompt_pending_scene_action", lambda _reason: "save")
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": None,
        )

        assert window.close() is False
        qapp.processEvents()

        assert list(config_library.scene_user_dir("exam").glob("*.json")) == []
        assert builtin_path.read_bytes() == builtin_bytes
        assert window.bridge.current_scene_id() == "exam"
        assert window.bridge.current_scene().description == "cancelled-close-draft"
        assert window.bridge.current_scene_source_type() == "builtin"
        assert window.bridge.is_scene_dirty() is True
        assert window._close_accepted is False
    finally:
        _close_clean(window, qapp)


def test_wrong_save_receipt_target_is_rejected_and_removed(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel = _open_scene_panel("exam", "exam")
    builtin_path = Path(bridge.current_scene_path())
    builtin_bytes = builtin_path.read_bytes()
    planned_id = "prepared_receipt_target"
    wrong_id = "wrong_receipt_target"
    try:
        _mark_scene_dirty(bridge, description="wrong-receipt-draft")
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": planned_id,
        )

        def save_to_wrong_target(scene, scene_id=None, *, mode_id=None, **_kwargs):
            assert scene_id == planned_id
            return config_library.save_scene_to_library(
                scene,
                scene_id=wrong_id,
                mode_id=mode_id,
                expected_absent=True,
            )

        assert panel.prepare_pending_scene_changes(
            "save",
            save_callable=save_to_wrong_target,
            mode_id="exam",
        ) is True
        assert panel.commit_prepared_scene_changes() is False

        user_dir = config_library.scene_user_dir("exam")
        assert (user_dir / f"{planned_id}.json").exists() is False
        assert (user_dir / f"{wrong_id}.json").exists() is False
        assert builtin_path.read_bytes() == builtin_bytes
        assert bridge.current_scene_id() == "exam"
        assert bridge.current_scene_source_type() == "builtin"
        assert bridge.current_scene().description == "wrong-receipt-draft"
        assert bridge.is_scene_dirty() is True
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_projection_failure_removes_new_fork_and_restores_builtin_dirty_draft(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel = _open_scene_panel("exam", "exam")
    builtin_path = Path(bridge.current_scene_path())
    builtin_bytes = builtin_path.read_bytes()
    fork_id = "projection_failure_copy"
    try:
        _mark_scene_dirty(bridge, description="projection-failure-draft")
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": fork_id,
        )
        assert panel.prepare_pending_scene_changes("save", mode_id="exam") is True

        original_apply = panel._apply_scene
        injected = {"raised": False}

        def fail_first_saved_projection(*args, **kwargs):
            if not injected["raised"]:
                injected["raised"] = True
                raise RuntimeError("injected saved-scene projection failure")
            return original_apply(*args, **kwargs)

        monkeypatch.setattr(panel, "_apply_scene", fail_first_saved_projection)
        monkeypatch.setattr(
            "src.ui.panels.scene_panel.Toast.show_error",
            lambda *_args, **_kwargs: None,
        )

        assert panel.commit_prepared_scene_changes() is False

        assert (config_library.scene_user_dir("exam") / f"{fork_id}.json").exists() is False
        assert builtin_path.read_bytes() == builtin_bytes
        assert bridge.current_scene_id() == "exam"
        assert bridge.current_scene_source_type() == "builtin"
        assert bridge.current_scene().description == "projection-failure-draft"
        assert bridge.is_scene_dirty() is True
        assert panel._current_scene is bridge.current_scene()
    finally:
        _dispose_panel(bridge, panel, qapp)


@pytest.mark.parametrize("failure_stage", ("activation", "finalize"))
def test_duplicate_failure_removes_fork_and_restores_original_session(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
    failure_stage: str,
):
    bridge, panel = _open_scene_panel("exam", "exam")
    original_snapshot = bridge.capture_state_snapshot()
    original_selector_id = panel._overview._combo.currentData()
    builtin_path = Path(bridge.current_scene_path())
    builtin_bytes = builtin_path.read_bytes()
    fork_id = f"duplicate_{failure_stage}_failure"
    try:
        if failure_stage == "activation":
            original_apply = panel._apply_scene
            injected = {"raised": False}

            def fail_first_fork_projection(*args, **kwargs):
                if not injected["raised"]:
                    injected["raised"] = True
                    raise RuntimeError("injected duplicate activation failure")
                return original_apply(*args, **kwargs)

            monkeypatch.setattr(panel, "_apply_scene", fail_first_fork_projection)
        else:
            monkeypatch.setattr(
                bridge,
                "finalize_scene_publication",
                lambda _transaction: (_ for _ in ()).throw(
                    RuntimeError("injected duplicate finalize failure")
                ),
            )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda *_args, **_kwargs: None,
        )
        assert panel._create_scene_copy(fork_id, action_label="duplicate") is False

        target = config_library.scene_user_dir("exam") / f"{fork_id}.json"
        assert target.exists() is False
        assert builtin_path.read_bytes() == builtin_bytes
        assert bridge.capture_state_snapshot() == original_snapshot
        assert bridge.current_scene_id() == "exam"
        assert bridge.current_scene_source_type() == "builtin"
        assert bridge.is_scene_dirty() is False
        assert panel._current_scene == bridge.current_scene()
        assert panel._overview._combo.currentData() == original_selector_id == "exam"
        assert panel._scene_session.prepared_changes is None
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_rename_write_failure_restores_file_identity_scene_and_selector(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id="rename_failure_source",
        name="Original user plan",
    )
    original_bytes = path.read_bytes()
    original_scene = copy.deepcopy(bridge.current_scene())
    original_identity = (
        bridge.current_scene_id(),
        bridge.current_scene_path(),
        bridge.current_scene_source(),
        bridge.current_scene_source_type(),
    )
    original_selector_id = panel._overview._combo.currentData()
    try:
        monkeypatch.setattr(
            scene_panel_module,
            "input_text",
            lambda *_args, **_kwargs: "Renamed user plan",
        )

        def write_then_return(scene, scene_id=None, *, mode_id=None, **kwargs):
            entry = config_library.save_scene_to_library(
                scene,
                scene_id=scene_id,
                mode_id=mode_id,
                **kwargs,
            )
            assert path.read_bytes() != original_bytes
            return entry

        monkeypatch.setattr(
            scene_session_module,
            "save_scene_to_library",
            write_then_return,
        )
        monkeypatch.setattr(
            panel._scene_session,
            "_load_canonical_committed_scene",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("injected rename canonical reload failure after write")
            ),
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda *_args, **_kwargs: None,
        )

        panel._on_rename_scene_requested()

        assert path.read_bytes() == original_bytes
        assert bridge.current_scene() == original_scene
        assert panel._current_scene == original_scene
        assert (
            bridge.current_scene_id(),
            bridge.current_scene_path(),
            bridge.current_scene_source(),
            bridge.current_scene_source_type(),
        ) == original_identity
        assert bridge.is_scene_dirty() is False
        assert panel._overview._combo.currentData() == original_selector_id
        assert panel._overview._combo.findData("rename_failure_source") >= 0
        persisted = config_library.load_scene_from_library(
            "rename_failure_source",
            mode_id="exam",
        )
        assert persisted == original_scene
        assert persisted.name == "Original user plan"
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_watcher_missing_current_file_preserves_dirty_user_draft_and_selection(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id="watcher_dirty_source",
        name="Watcher dirty source",
    )
    original_identity = (
        bridge.current_scene_id(),
        bridge.current_scene_path(),
        bridge.current_scene_source(),
        bridge.current_scene_source_type(),
    )
    try:
        _mark_scene_dirty(bridge, description="watcher-must-preserve-this-draft")
        panel._scene_library_watcher.blockSignals(True)
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_warning",
            lambda *_args, **_kwargs: None,
        )
        path.unlink()
        assert path.exists() is False

        panel._refresh_scene_library_from_disk()

        assert path.exists() is False
        assert (
            bridge.current_scene_id(),
            bridge.current_scene_path(),
            bridge.current_scene_source(),
            bridge.current_scene_source_type(),
        ) == original_identity
        assert bridge.current_scene().description == "watcher-must-preserve-this-draft"
        assert panel._current_scene.description == "watcher-must-preserve-this-draft"
        assert bridge.is_scene_dirty() is True
        assert panel._overview._combo.currentData() == "watcher_dirty_source"
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_watcher_notification_during_move_aside_runs_after_successful_publish(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "watcher_move_aside_publish"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Watcher move-aside publish",
    )
    real_rename = config_library.os.rename
    observed_missing_window = False
    default_switches = 0

    def rename_then_queue_refresh(source, destination, *args, **kwargs):
        nonlocal observed_missing_window
        result = real_rename(source, destination, *args, **kwargs)
        if (
            Path(source) == path
            and Path(destination).name == "displaced.json"
        ):
            observed_missing_window = path.exists() is False
            panel._on_scene_library_path_changed(str(path))
            assert panel._scene_library_refresh_pending is True
        return result

    def record_default_switch(*_args, **_kwargs):
        nonlocal default_switches
        default_switches += 1
        return False

    try:
        panel._scene_library_watcher.blockSignals(True)
        monkeypatch.setattr(config_library.os, "rename", rename_then_queue_refresh)
        monkeypatch.setattr(
            panel,
            "_switch_to_default_scene_after_missing_file",
            record_default_switch,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_success",
            lambda *_args, **_kwargs: None,
        )
        _mark_scene_dirty(bridge, description="published-after-move-aside")

        assert panel.save_current_scene() is True
        assert observed_missing_window is True
        assert path.exists() is True

        QTest.qWait(80)
        qapp.processEvents()

        assert default_switches == 0
        assert bridge.current_scene_id() == scene_id
        assert bridge.current_scene().description == "published-after-move-aside"
        assert bridge.is_scene_dirty() is False
        assert panel._scene_session.authoritative_user_conflict() is False
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_watcher_notification_during_failed_move_aside_preserves_dirty_draft(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "watcher_move_aside_rollback"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Watcher move-aside rollback",
    )
    original_payload = path.read_bytes()
    real_rename = config_library.os.rename
    real_read_bytes = Path.read_bytes
    observed_missing_window = False
    failed_read = False
    default_switches = 0

    def rename_then_queue_refresh(source, destination, *args, **kwargs):
        nonlocal observed_missing_window
        result = real_rename(source, destination, *args, **kwargs)
        if (
            Path(source) == path
            and Path(destination).name == "displaced.json"
        ):
            observed_missing_window = path.exists() is False
            panel._on_scene_library_path_changed(str(path))
        return result

    def fail_displaced_once(candidate, *args, **kwargs):
        nonlocal failed_read
        if not failed_read and Path(candidate).name == "displaced.json":
            failed_read = True
            raise PermissionError("injected unreadable move-aside occupant")
        return real_read_bytes(candidate, *args, **kwargs)

    def record_default_switch(*_args, **_kwargs):
        nonlocal default_switches
        default_switches += 1
        return False

    try:
        panel._scene_library_watcher.blockSignals(True)
        monkeypatch.setattr(config_library.os, "rename", rename_then_queue_refresh)
        monkeypatch.setattr(Path, "read_bytes", fail_displaced_once)
        monkeypatch.setattr(
            panel,
            "_switch_to_default_scene_after_missing_file",
            record_default_switch,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda *_args, **_kwargs: None,
        )
        _mark_scene_dirty(bridge, description="draft-survives-move-aside-rollback")

        assert panel.save_current_scene() is False
        assert observed_missing_window is True
        assert failed_read is True
        assert path.read_bytes() == original_payload

        QTest.qWait(80)
        qapp.processEvents()

        assert default_switches == 0
        assert bridge.current_scene_id() == scene_id
        assert bridge.current_scene().description == (
            "draft-survives-move-aside-rollback"
        )
        assert bridge.is_scene_dirty() is True
        assert panel._scene_session.recovery_required() is False
        assert config_library.scene_recovery_artifacts(path) == ()
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_watcher_clean_external_update_reloads_and_adopts_the_new_revision(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "watcher_clean_reload"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Watcher clean reload",
    )
    original_revision = panel._scene_session.authoritative_user_revision()
    try:
        panel._scene_library_watcher.blockSignals(True)
        externally_updated = copy.deepcopy(bridge.current_scene())
        externally_updated.description = "external-clean-revision"
        external_path = path.with_name(f".{scene_id}.external.json")
        config_library.save_scene(externally_updated, external_path)
        config_library.os.replace(external_path, path)
        assert config_library.scene_file_revision(path) != original_revision

        panel._refresh_scene_library_from_disk()

        persisted = config_library.load_scene_from_library(scene_id, mode_id="exam")
        assert persisted.description == "external-clean-revision"
        assert bridge.current_scene() == persisted
        assert panel._current_scene == persisted
        assert bridge.current_scene_id() == scene_id
        assert bridge.current_scene_path() == str(path)
        assert bridge.current_scene_source_type() == "user"
        assert bridge.is_scene_dirty() is False
        assert panel._scene_session.authoritative_user_conflict() is False
        assert panel._scene_session.authoritative_user_revision() == (
            config_library.scene_file_revision(path)
        )
        assert panel._overview._combo.currentData() == scene_id
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_watcher_dirty_external_update_preserves_draft_and_save_forks(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "watcher_dirty_external"
    fork_id = "watcher_dirty_external_fork"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Watcher dirty external",
    )
    try:
        panel._scene_library_watcher.blockSignals(True)
        externally_updated = copy.deepcopy(bridge.current_scene())
        externally_updated.description = "external-version-must-survive"
        _mark_scene_dirty(bridge, description="local-dirty-draft-must-survive")
        external_path = path.with_name(f".{scene_id}.external.json")
        config_library.save_scene(externally_updated, external_path)
        config_library.os.replace(external_path, path)
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_warning",
            lambda *_args, **_kwargs: None,
        )

        panel._refresh_scene_library_from_disk()

        assert bridge.current_scene().description == "local-dirty-draft-must-survive"
        assert panel._current_scene.description == "local-dirty-draft-must-survive"
        assert bridge.is_scene_dirty() is True
        assert panel._scene_session.authoritative_user_conflict() is True
        assert panel._overview._combo.currentData() == scene_id

        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": fork_id,
        )
        assert panel.save_current_scene() is True

        original = config_library.load_scene_from_library(scene_id, mode_id="exam")
        fork = config_library.load_scene_from_library(fork_id, mode_id="exam")
        assert original.description == "external-version-must-survive"
        assert fork.description == "local-dirty-draft-must-survive"
        assert path == config_library.get_scene_entry(scene_id, mode_id="exam").path
        assert bridge.current_scene_id() == fork_id
        assert bridge.current_scene_source_type() == "user"
        assert bridge.current_scene() == fork
        assert bridge.is_scene_dirty() is False
        assert panel._scene_session.authoritative_user_conflict() is False
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_save_preflight_detects_unwatched_external_update_and_forks(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "save_preflight_external"
    fork_id = "save_preflight_external_fork"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Save preflight external",
    )
    try:
        panel._scene_library_watcher.blockSignals(True)
        external = copy.deepcopy(bridge.current_scene())
        external.description = "unwatched-external-version"
        _mark_scene_dirty(bridge, description="unwatched-local-draft")
        external_path = path.with_name(f".{scene_id}.external.json")
        config_library.save_scene(external, external_path)
        config_library.os.replace(external_path, path)
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": fork_id,
        )

        assert panel.save_current_scene() is True

        assert config_library.load_scene_from_library(
            scene_id,
            mode_id="exam",
        ).description == "unwatched-external-version"
        assert config_library.load_scene_from_library(
            fork_id,
            mode_id="exam",
        ).description == "unwatched-local-draft"
        assert bridge.current_scene_id() == fork_id
        assert bridge.current_scene_source_type() == "user"
        assert bridge.is_scene_dirty() is False
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_watcher_missing_clean_scene_default_load_exception_never_escapes(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "watcher_missing_clean_failure"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Watcher missing clean failure",
    )
    original_scene = copy.deepcopy(bridge.current_scene())
    original_identity = (
        bridge.current_scene_id(),
        bridge.current_scene_path(),
        bridge.current_scene_source(),
        bridge.current_scene_source_type(),
    )
    errors: list[str] = []
    try:
        panel._scene_library_watcher.blockSignals(True)
        path.unlink()
        monkeypatch.setattr(
            scene_panel_module,
            "default_scene_entry",
            lambda **_kwargs: (_ for _ in ()).throw(
                RuntimeError("injected watcher default lookup failure")
            ),
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda message, *_args, **_kwargs: errors.append(str(message)),
        )

        panel._refresh_scene_library_from_disk()

        assert path.exists() is False
        assert bridge.current_scene() == original_scene
        assert panel._current_scene == original_scene
        assert (
            bridge.current_scene_id(),
            bridge.current_scene_path(),
            bridge.current_scene_source(),
            bridge.current_scene_source_type(),
        ) == original_identity
        assert bridge.is_scene_dirty() is False
        assert panel._scene_session.authoritative_user_conflict() is True
        assert any("加载默认方案失败" in message for message in errors)
    finally:
        _dispose_panel(bridge, panel, qapp)


@pytest.mark.parametrize("failure_stage", ("load", "activation"))
def test_delete_failure_after_unlink_restores_file_and_selector(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
    failure_stage: str,
):
    scene_id = f"delete_{failure_stage}_source"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name=f"Delete {failure_stage} source",
    )
    original_bytes = path.read_bytes()
    original_scene = copy.deepcopy(bridge.current_scene())
    original_identity = (
        bridge.current_scene_id(),
        bridge.current_scene_path(),
        bridge.current_scene_source(),
        bridge.current_scene_source_type(),
    )
    try:
        panel._scene_library_watcher.blockSignals(True)
        monkeypatch.setattr(
            scene_panel_module,
            "confirm",
            lambda *_args, **_kwargs: True,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda *_args, **_kwargs: None,
        )
        if failure_stage == "load":

            def fail_default_load(*_args, **_kwargs):
                assert path.exists() is False
                raise RuntimeError("injected post-delete default load failure")

            monkeypatch.setattr(
                scene_panel_module,
                "load_scene_from_library",
                fail_default_load,
            )
        else:

            def fail_default_activation(*_args, **_kwargs):
                assert path.exists() is False
                return False

            monkeypatch.setattr(panel, "_activate_scene", fail_default_activation)

        panel._on_delete_scene_requested()

        assert path.read_bytes() == original_bytes
        assert bridge.current_scene() == original_scene
        assert panel._current_scene == original_scene
        assert (
            bridge.current_scene_id(),
            bridge.current_scene_path(),
            bridge.current_scene_source(),
            bridge.current_scene_source_type(),
        ) == original_identity
        assert bridge.is_scene_dirty() is False
        assert panel._overview._combo.currentData() == scene_id
        assert panel._overview._combo.findData(scene_id) >= 0
        assert config_library.load_scene_from_library(scene_id, mode_id="exam") == (
            original_scene
        )
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_delete_activation_failure_keeps_receipt_until_rollback_cleanup_retries(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "delete_activation_cleanup_retry"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Delete activation cleanup retry",
    )
    original_bytes = path.read_bytes()
    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_once(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls == 1:
            raise OSError("injected delete rollback evidence cleanup failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    try:
        panel._scene_library_watcher.blockSignals(True)
        monkeypatch.setattr(
            scene_panel_module,
            "confirm",
            lambda *_args, **_kwargs: True,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_warning",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(panel, "_activate_scene", lambda *_args, **_kwargs: False)
        monkeypatch.setattr(
            config_library,
            "_discard_scene_recovery_directory",
            fail_once,
        )

        panel._on_delete_scene_requested()

        pending_receipt = panel._pending_scene_delete_receipt
        assert isinstance(
            pending_receipt,
            config_library.SceneFileMutationReceipt,
        )
        assert panel._pending_scene_delete_resolution == "rollback"
        assert panel._scene_session.recovery_required() is True
        assert path.read_bytes() == original_bytes
        assert config_library.scene_recovery_artifacts(path)

        assert panel.prepare_pending_scene_changes("discard", mode_id="exam") is True

        assert panel._pending_scene_delete_receipt is None
        assert panel._pending_scene_delete_resolution == ""
        assert panel._scene_session.recovery_required() is False
        assert path.read_bytes() == original_bytes
        assert config_library.scene_recovery_artifacts(path) == ()
        panel.cancel_prepared_scene_changes()
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_pending_delete_finalize_cleanup_blocks_prepare_and_close_until_retry(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "delete_finalize_cleanup_gate"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Delete finalize cleanup gate",
    )
    real_discard = config_library._discard_scene_recovery_directory
    cleanup_blocked = True

    def block_cleanup(recovery_dir, *, ignore_errors=False):
        if cleanup_blocked:
            raise OSError("injected retained delete finalize cleanup failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    try:
        panel._scene_library_watcher.blockSignals(True)
        monkeypatch.setattr(
            scene_panel_module,
            "confirm",
            lambda *_args, **_kwargs: True,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            config_library,
            "_discard_scene_recovery_directory",
            block_cleanup,
        )

        panel._on_delete_scene_requested()

        pending_receipt = panel._pending_scene_delete_receipt
        assert isinstance(
            pending_receipt,
            config_library.SceneFileMutationReceipt,
        )
        assert panel._pending_scene_delete_resolution == "finalize"
        assert panel._scene_session.recovery_required() is True
        assert path.exists() is False
        assert config_library.scene_recovery_artifacts(path)

        assert panel.prepare_pending_scene_changes("discard", mode_id="exam") is False
        assert panel.prepare_close_pending_changes() is False
        assert panel._pending_scene_delete_receipt is pending_receipt
        assert panel._scene_session.prepared_changes is None
        assert panel._scene_session.recovery_required() is True
        assert config_library.scene_recovery_artifacts(path)

        cleanup_blocked = False
        assert panel.prepare_close_pending_changes() is True

        assert panel._pending_scene_delete_receipt is None
        assert panel._pending_scene_delete_resolution == ""
        assert panel._scene_session.recovery_required() is False
        assert path.exists() is False
        assert config_library.scene_recovery_artifacts(path) == ()
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_delete_refuses_externally_changed_file_before_unlink(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "delete_revision_conflict"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Delete revision conflict",
    )
    external = copy.deepcopy(bridge.current_scene())
    external.description = "external-version-must-not-be-deleted"
    errors: list[str] = []
    try:
        panel._scene_library_watcher.blockSignals(True)
        external_path = isolated_scene_config_library / "external-winner.json"
        config_library.save_scene(external, external_path)
        config_library.os.replace(external_path, path)
        external_bytes = path.read_bytes()
        monkeypatch.setattr(
            scene_panel_module,
            "confirm",
            lambda *_args, **_kwargs: True,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda message, *_args, **_kwargs: errors.append(str(message)),
        )

        panel._on_delete_scene_requested()

        assert path.read_bytes() == external_bytes
        assert config_library.load_scene_from_library(
            scene_id,
            mode_id="exam",
        ).description == "external-version-must-not-be-deleted"
        assert bridge.current_scene_id() == scene_id
        assert panel._scene_session.authoritative_user_conflict() is True
        assert any("删除方案失败" in message for message in errors)
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_delete_rollback_never_overwrites_external_recreation(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "delete_external_recreation"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Delete external recreation",
    )
    original_scene = copy.deepcopy(bridge.current_scene())
    original_bytes = path.read_bytes()
    external = copy.deepcopy(original_scene)
    external.description = "externally-recreated-version"
    warnings: list[str] = []
    recreated = {"done": False}
    try:
        panel._scene_library_watcher.blockSignals(True)
        monkeypatch.setattr(
            scene_panel_module,
            "confirm",
            lambda *_args, **_kwargs: True,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_warning",
            lambda message, *_args, **_kwargs: warnings.append(str(message)),
        )

        def recreate_then_fail(*_args, **_kwargs):
            assert path.exists() is False
            if not recreated["done"]:
                recreated["done"] = True
                external_path = (
                    isolated_scene_config_library / "external-recreation.json"
                )
                config_library.save_scene(external, external_path)
                config_library.os.replace(external_path, path)
            raise RuntimeError("injected failure after external recreation")

        monkeypatch.setattr(
            scene_panel_module,
            "load_scene_from_library",
            recreate_then_fail,
        )

        panel._on_delete_scene_requested()

        assert recreated["done"] is True
        assert path.read_bytes() != original_bytes
        persisted = config_library.load_scene(path)
        assert persisted.description == "externally-recreated-version"
        assert bridge.current_scene() == original_scene
        assert bridge.current_scene_id() == scene_id
        assert bridge.is_scene_dirty() is False
        assert panel._scene_session.authoritative_user_conflict() is True
        assert any("未覆盖" in message for message in warnings)
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_commit_rollback_failure_evidence_survives_cancel_and_can_retry(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "recoverable_commit_rollback"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Recoverable commit rollback",
    )
    original_bytes = path.read_bytes()
    original_revision = panel._scene_session.authoritative_user_revision()
    try:
        panel._scene_library_watcher.blockSignals(True)
        _mark_scene_dirty(bridge, description="published-before-rollback-failure")
        assert panel.prepare_pending_scene_changes("save", mode_id="exam") is True

        original_apply = panel._apply_scene
        projection = {"failed": False}

        def fail_first_saved_projection(*args, **kwargs):
            if not projection["failed"]:
                projection["failed"] = True
                raise RuntimeError("injected saved projection failure")
            return original_apply(*args, **kwargs)

        monkeypatch.setattr(panel, "_apply_scene", fail_first_saved_projection)
        original_restore = panel._scene_session._restore_prepared_file
        restore_attempts = {"count": 0}

        def fail_first_two_restores(prepared):
            restore_attempts["count"] += 1
            if restore_attempts["count"] <= 2:
                raise OSError("injected rollback persistence failure")
            return original_restore(prepared)

        monkeypatch.setattr(
            panel._scene_session,
            "_restore_prepared_file",
            fail_first_two_restores,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda *_args, **_kwargs: None,
        )

        assert panel.commit_prepared_scene_changes() is False
        prepared = panel._scene_session.prepared_changes
        assert prepared is not None
        assert prepared.committed is False
        assert prepared.publication_attempted is True
        assert prepared.recovery_required is True
        assert panel._scene_session.authoritative_user_conflict() is True
        assert panel._scene_session.authoritative_user_revision() == original_revision
        assert path.read_bytes() != original_bytes

        panel.cancel_prepared_scene_changes()

        assert restore_attempts["count"] == 2
        assert panel._scene_session.prepared_changes is prepared
        assert prepared.recovery_required is True
        assert panel._scene_session.authoritative_user_conflict() is True
        assert panel._scene_session.authoritative_user_revision() == original_revision
        assert path.read_bytes() != original_bytes

        assert panel.rollback_prepared_scene_changes() is True
        assert restore_attempts["count"] == 3
        assert panel._scene_session.prepared_changes is None
        assert path.read_bytes() == original_bytes
        assert panel._scene_session.authoritative_user_conflict() is False
        assert bridge.current_scene().description == (
            "published-before-rollback-failure"
        )
        assert bridge.is_scene_dirty() is True
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_missing_post_write_snapshot_never_rolls_back_external_replacement(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    scene_id = "missing_post_write_snapshot"
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id=scene_id,
        name="Missing post-write snapshot",
    )
    original = copy.deepcopy(bridge.current_scene())
    external = copy.deepcopy(original)
    external.description = "replacement-after-unverified-write"
    original_revision = panel._scene_session.authoritative_user_revision()
    try:
        panel._scene_library_watcher.blockSignals(True)
        _mark_scene_dirty(bridge, description="transaction-write")
        assert panel.prepare_pending_scene_changes("save", mode_id="exam") is True

        record_called = {"value": False}

        def replace_before_post_write_snapshot(prepared, entry):
            record_called["value"] = True
            prepared.committed_path = Path(entry.path)
            prepared.committed_before = prepared.target_snapshot
            prepared.committed_after = None
            prepared.committed_receipt_revision = ""
            prepared.committed_directory_after = None
            external_path = path.with_name(f".{scene_id}.external.json")
            config_library.save_scene(external, external_path)
            config_library.os.replace(external_path, path)
            raise OSError("injected post-write snapshot failure")

        monkeypatch.setattr(
            panel._scene_session,
            "_record_commit_candidate",
            replace_before_post_write_snapshot,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_error",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            scene_panel_module.Toast,
            "show_warning",
            lambda *_args, **_kwargs: None,
        )

        result = panel._scene_session.commit_prepared_changes()
        assert result.success is False
        assert record_called["value"] is True, repr(result.error)
        prepared = panel._scene_session.prepared_changes
        assert prepared is not None
        assert prepared.committed_after is None
        assert prepared.recovery_required is True
        assert panel._scene_session.authoritative_user_conflict() is True
        assert panel._scene_session.authoritative_user_revision() == original_revision
        assert config_library.load_scene_from_library(
            scene_id,
            mode_id="exam",
        ).description == "replacement-after-unverified-write"
        with pytest.raises(scene_session_module.SceneSaveRevisionChanged):
            panel._scene_session.capture_verified_authoritative_user_file(path)

        panel._refresh_scene_library_from_disk()

        assert panel._scene_session.prepared_changes is prepared
        assert panel._scene_session.authoritative_user_conflict() is True
        retry = panel._scene_session.prepare_pending_changes("save", mode_id="exam")
        assert retry.success is False
        assert panel._scene_session.prepared_changes is prepared
        assert prepared.recovery_required is True

        panel.cancel_prepared_scene_changes()

        assert panel._scene_session.prepared_changes is prepared
        assert prepared.recovery_required is True
        assert panel._scene_session.authoritative_user_conflict() is True
        assert panel._scene_session.authoritative_user_revision() == original_revision
        assert config_library.load_scene_from_library(
            scene_id,
            mode_id="exam",
        ).description == "replacement-after-unverified-write"
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_close_rejects_scene_finalize_false_and_keeps_save_rollbackable(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id="close_finalize_false",
        name="Close finalize false",
    )
    original_payload = path.read_bytes()
    try:
        panel._scene_library_watcher.blockSignals(True)
        _mark_scene_dirty(bridge, description="close-finalize-false-draft")
        monkeypatch.setattr(
            panel,
            "_prompt_pending_scene_action",
            lambda _reason: "save",
        )
        assert panel.prepare_close_pending_changes() is True
        monkeypatch.setattr(
            panel,
            "finalize_prepared_scene_changes",
            lambda **_kwargs: False,
        )

        accepted = MainWindow._commit_prepared_panel_closes([panel])

        assert accepted is False
        if panel._scene_session.prepared_changes is not None:
            assert panel.rollback_close_pending_changes() is True
        assert panel._scene_session.prepared_changes is None
        assert panel._scene_session.recovery_required() is False
        assert path.read_bytes() == original_payload
        assert bridge.current_scene().description == "close-finalize-false-draft"
        assert bridge.is_scene_dirty() is True
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_close_rejects_scene_finalize_exception_and_keeps_save_rollbackable(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id="close_finalize_exception",
        name="Close finalize exception",
    )
    original_payload = path.read_bytes()

    def fail_finalize(**_kwargs):
        raise OSError("injected close Scene finalize failure")

    try:
        panel._scene_library_watcher.blockSignals(True)
        _mark_scene_dirty(bridge, description="close-finalize-exception-draft")
        monkeypatch.setattr(
            panel,
            "_prompt_pending_scene_action",
            lambda _reason: "save",
        )
        assert panel.prepare_close_pending_changes() is True
        monkeypatch.setattr(
            panel,
            "finalize_prepared_scene_changes",
            fail_finalize,
        )

        accepted = MainWindow._commit_prepared_panel_closes([panel])

        assert accepted is False
        if panel._scene_session.prepared_changes is not None:
            assert panel.rollback_close_pending_changes() is True
        assert panel._scene_session.prepared_changes is None
        assert panel._scene_session.recovery_required() is False
        assert path.read_bytes() == original_payload
        assert bridge.current_scene().description == (
            "close-finalize-exception-draft"
        )
        assert bridge.is_scene_dirty() is True
    finally:
        _dispose_panel(bridge, panel, qapp)


def test_close_accepts_successful_scene_finalize_and_releases_transaction(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    bridge, panel, path = _open_owned_user_scene_panel(
        scene_id="close_finalize_success",
        name="Close finalize success",
    )
    original_payload = path.read_bytes()
    try:
        panel._scene_library_watcher.blockSignals(True)
        _mark_scene_dirty(bridge, description="close-finalize-success-draft")
        monkeypatch.setattr(
            panel,
            "_prompt_pending_scene_action",
            lambda _reason: "save",
        )
        assert panel.prepare_close_pending_changes() is True

        accepted = MainWindow._commit_prepared_panel_closes([panel])

        assert accepted is True
        assert panel._scene_session.prepared_changes is None
        assert panel._scene_session.recovery_required() is False
        assert path.read_bytes() != original_payload
        assert config_library.load_scene(path).description == (
            "close-finalize-success-draft"
        )
        assert bridge.is_scene_dirty() is False
    finally:
        _dispose_panel(bridge, panel, qapp)


class _FailingCloseParticipant(QWidget):
    def prepare_close_pending_changes(self) -> bool:
        return True

    def commit_close_pending_changes(self) -> bool:
        return False

    def cancel_prepared_close(self) -> None:
        pass


def test_later_close_participant_failure_rolls_back_new_scene_fork(
    qapp,
    isolated_scene_config_library,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    failure = _FailingCloseParticipant()
    try:
        assert window._request_work_mode_change("exam") is True
        panel = window._ensure_panel_loaded_for_id("scene")
        builtin_path = Path(window.bridge.current_scene_path())
        builtin_bytes = builtin_path.read_bytes()
        _mark_scene_dirty(window.bridge, description="participant-failure-draft")
        monkeypatch.setattr(panel, "_prompt_pending_scene_action", lambda _reason: "save")
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": "participant_failure_copy",
        )
        # Template occupies index 2.  This irreversible participant commits
        # after reversible Scene and forces the Scene fork to roll back.
        window.register_panel(2, failure)

        assert window.close() is False
        qapp.processEvents()

        target = (
            config_library.scene_user_dir("exam")
            / "participant_failure_copy.json"
        )
        assert target.exists() is False
        assert builtin_path.read_bytes() == builtin_bytes
        assert window.bridge.current_scene_id() == "exam"
        assert window.bridge.current_scene_source_type() == "builtin"
        assert window.bridge.current_scene().description == "participant-failure-draft"
        assert window.bridge.is_scene_dirty() is True
        assert window._close_accepted is False
    finally:
        window.register_panel(2, QWidget())
        _close_clean(window, qapp)


def test_scene_runtime_library_is_json_only(
    isolated_scene_config_library,
):
    user_dir = config_library.scene_user_dir("exam")
    user_dir.mkdir(parents=True, exist_ok=True)
    legacy_yaml = user_dir / "legacy_yaml.yaml"
    legacy_yml = user_dir / "legacy_yml.yml"
    legacy_yaml.write_text("scene_id: legacy_yaml\n", encoding="utf-8")
    legacy_yml.write_text("scene_id: legacy_yml\n", encoding="utf-8")

    assert config_library.get_scene_entry("legacy_yaml", mode_id="exam") is None
    assert config_library.get_scene_entry("legacy_yml", mode_id="exam") is None
    assert {
        entry.config_id for entry in config_library.list_scene_entries(mode_id="exam")
    }.isdisjoint({"legacy_yaml", "legacy_yml"})

    scene = copy.deepcopy(
        config_library.load_scene_from_library("exam", mode_id="exam")
    )
    scene.name = "legacy_yaml"
    entry = config_library.save_scene_to_library(
        scene,
        scene_id="legacy_yaml",
        mode_id="exam",
        expected_absent=True,
    )

    assert entry.path == user_dir / "legacy_yaml.json"
    assert entry.path.is_file()
    assert config_library.get_scene_entry("legacy_yaml", mode_id="exam") == entry
