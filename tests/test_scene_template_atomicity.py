from __future__ import annotations

import copy

import pytest

from src.config import library as config_library
from src.config.library import get_scene_descriptor, load_scene_from_library
from src.config.loader import load_template, save_template
from src.config.template import TemplateConfig
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_panel import ScenePanel
from src.ui.panels.template_panel import TemplatePanel


def test_template_close_discard_projection_failure_restores_entire_draft_boundary(
    qapp,
    monkeypatch,
):
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    try:
        committed = panel._edit_session.committed_copy()
        draft = copy.deepcopy(panel._current_template)
        draft.name = "TEMPLATE_DRAFT_SENTINEL"
        panel._on_template_edited(draft)
        qapp.processEvents()

        assert panel.pending_template_draft_count() == 1
        assert bridge.is_template_dirty() is True
        assert bridge.current_template().name == committed.name

        monkeypatch.setattr(
            panel,
            "_prompt_close_template_draft_action",
            lambda _count: "discard",
        )
        original_refresh = panel._refresh_overview_projection
        injected = {"raised": False}

        def fail_after_discard(*, reason: str) -> None:
            if reason == "all_template_drafts_discarded" and not injected["raised"]:
                injected["raised"] = True
                raise RuntimeError("injected template projection failure")
            original_refresh(reason=reason)

        monkeypatch.setattr(panel, "_refresh_overview_projection", fail_after_discard)

        assert panel.prepare_close_pending_changes() is True
        assert panel.commit_close_pending_changes() is False

        assert panel.pending_template_draft_count() == 1
        assert panel._draft_context.session is panel._edit_session
        assert panel._current_template is panel._edit_session.draft
        assert panel._current_template.name == "TEMPLATE_DRAFT_SENTINEL"
        assert panel._edit_session.committed_copy() == committed
        assert bridge.current_template().name == committed.name
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        qapp.processEvents()


def test_template_close_save_revision_failure_preserves_external_writer(
    qapp,
    tmp_path,
    monkeypatch,
):
    target = save_template(
        TemplateConfig(name="committed"),
        tmp_path / "template.json",
    )
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    try:
        panel._activate_template(
            load_template(target),
            template_id="revision-guard",
            path=str(target),
            source="file",
            source_type="external",
        )
        draft = copy.deepcopy(panel._current_template)
        draft.name = "local draft"
        panel._on_template_edited(draft)
        monkeypatch.setattr(
            panel,
            "_prompt_close_template_draft_action",
            lambda _count: "save",
        )
        monkeypatch.setattr(
            panel,
            "_confirm_shared_template_write_for_context",
            lambda _context, **_kwargs: True,
        )

        assert panel.prepare_close_pending_changes() is True
        save_template(TemplateConfig(name="external writer"), target)

        assert panel.commit_close_pending_changes() is False
        assert load_template(target).name == "external writer"
        assert panel._current_template.name == "local draft"
        assert panel._edit_session.is_dirty() is True
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        qapp.processEvents()


def test_template_close_save_can_rollback_file_and_draft_store(
    qapp,
    tmp_path,
    monkeypatch,
):
    target = save_template(
        TemplateConfig(name="committed"),
        tmp_path / "template.json",
    )
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    try:
        panel._activate_template(
            load_template(target),
            template_id="reversible-save",
            path=str(target),
            source="file",
            source_type="external",
        )
        draft = copy.deepcopy(panel._current_template)
        draft.name = "saved draft"
        panel._on_template_edited(draft)
        monkeypatch.setattr(
            panel,
            "_prompt_close_template_draft_action",
            lambda _count: "save",
        )
        monkeypatch.setattr(
            panel,
            "_confirm_shared_template_write_for_context",
            lambda _context, **_kwargs: True,
        )

        assert panel.prepare_close_pending_changes() is True
        assert panel.commit_close_pending_changes() is True
        assert load_template(target).name == "saved draft"
        assert panel._edit_session.is_dirty() is False
        assert bridge.is_template_dirty() is False

        assert panel.rollback_close_pending_changes() is True
        assert load_template(target).name == "committed"
        assert panel._current_template.name == "saved draft"
        assert panel._edit_session.committed_copy().name == "committed"
        assert panel._edit_session.is_dirty() is True
        assert bridge.current_template().name == "committed"
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        qapp.processEvents()


def test_scene_selector_target_load_failure_restores_old_selection_and_dirty(
    qapp,
    monkeypatch,
):
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    panel = ScenePanel(bridge)
    bridge.commit_pending_work_mode_transition()
    try:
        old_scene = bridge.current_scene()
        old_scene.name = "SCENE_LOAD_SENTINEL"
        bridge.set_current_scene(
            old_scene,
            config_id=bridge.current_scene_id(),
            path=bridge.current_scene_path(),
            source=bridge.current_scene_source(),
            source_type=bridge.current_scene_source_type(),
            emit_signal=False,
        )
        bridge.set_scene_dirty(True)
        old_scene_id = bridge.current_scene_id()
        monkeypatch.setattr(
            panel,
            "_prompt_pending_scene_action",
            lambda _reason: "discard",
        )
        original_load = load_scene_from_library

        def fail_target_load(scene_id: str, *, mode_id: str):
            if scene_id == "exam_quiz":
                raise RuntimeError("injected target load failure")
            return original_load(scene_id, mode_id=mode_id)

        monkeypatch.setattr(
            "src.ui.panels.scene_panel.load_scene_from_library",
            fail_target_load,
        )

        target_index = panel._overview._combo.findData("exam_quiz")
        assert target_index >= 0
        panel._overview._combo.setCurrentIndex(target_index)
        qapp.processEvents()

        assert bridge.current_scene_id() == old_scene_id
        assert bridge.current_scene().name == "SCENE_LOAD_SENTINEL"
        assert bridge.is_scene_dirty() is True
        assert panel._overview._combo.currentData() == old_scene_id
    finally:
        bridge.clear_scene_dirty()
        panel.close()
        qapp.processEvents()


@pytest.mark.parametrize("failure_stage", ("binding", "detail", "bridge"))
def test_scene_activation_failure_restores_model_overview_selector_and_dirty(
    qapp,
    monkeypatch,
    failure_stage,
):
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    panel = ScenePanel(bridge)
    bridge.commit_pending_work_mode_transition()
    try:
        panel._ensure_detail_loaded("scn_content")
        old_scene = bridge.current_scene()
        old_scene.name = "SCENE_DRAFT_SENTINEL"
        bridge.set_current_scene(
            old_scene,
            config_id=bridge.current_scene_id(),
            path=bridge.current_scene_path(),
            source=bridge.current_scene_source(),
            source_type=bridge.current_scene_source_type(),
            emit_signal=False,
        )
        bridge.set_scene_dirty(True)
        old_scene_id = bridge.current_scene_id()
        old_template_id = bridge.current_template_id()
        old_path = bridge.current_scene_path()

        target = load_scene_from_library("exam_quiz", mode_id="exam")
        descriptor = get_scene_descriptor("exam_quiz", mode_id="exam")
        if failure_stage == "binding":

            def fail_template_binding(_scene):
                raise RuntimeError("injected scene template binding failure")

            monkeypatch.setattr(
                panel._scene_session,
                "resolve_template_binding",
                fail_template_binding,
            )
        elif failure_stage == "detail":
            original_sync = panel._sync_loaded_scene_details
            injected = {"raised": False}

            def fail_after_detail_projection(scene, template) -> None:
                original_sync(scene, template)
                if scene.scene_id == "exam_quiz" and not injected["raised"]:
                    injected["raised"] = True
                    raise RuntimeError("injected scene detail projection failure")

            monkeypatch.setattr(
                panel,
                "_sync_loaded_scene_details",
                fail_after_detail_projection,
            )
        else:
            original_publish = bridge.set_current_scene

            def fail_after_bridge_publication(scene, **kwargs) -> None:
                original_publish(scene, **kwargs)
                if str(kwargs.get("config_id") or "") == "exam_quiz":
                    raise RuntimeError("injected bridge scene publication failure")

            monkeypatch.setattr(
                bridge,
                "set_current_scene",
                fail_after_bridge_publication,
            )

        assert (
            panel._activate_scene(
                target,
                scene_id="exam_quiz",
                path=str(descriptor.path),
                source="library",
                source_type=descriptor.source_type,
                dirty=False,
            )
            is False
        )

        assert bridge.current_scene_id() == old_scene_id
        assert bridge.current_scene_path() == old_path
        assert bridge.current_scene().name == "SCENE_DRAFT_SENTINEL"
        assert bridge.current_template_id() == old_template_id
        assert bridge.is_scene_dirty() is True
        assert panel._current_scene is bridge.current_scene()
        assert panel._current_scene.name == "SCENE_DRAFT_SENTINEL"
        assert panel._content._scene.name == "SCENE_DRAFT_SENTINEL"
        assert panel._overview._combo.currentData() == old_scene_id
    finally:
        bridge.clear_scene_dirty()
        panel.close()
        qapp.processEvents()


def test_scene_save_projection_failure_restores_file_bridge_and_dirty_draft(
    qapp,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "plans")
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    panel = ScenePanel(bridge)
    bridge.commit_pending_work_mode_transition()
    try:
        scene_id = "projection-user-scene"
        baseline_scene = copy.deepcopy(load_scene_from_library("exam", mode_id="exam"))
        baseline_scene.scene_id = scene_id
        baseline_scene.name = "PROJECTION_USER_BASELINE"
        baseline_entry = config_library.save_scene_to_library(
            baseline_scene,
            scene_id=scene_id,
            mode_id="exam",
        )
        assert (
            panel._activate_scene(
                load_scene_from_library(scene_id, mode_id="exam"),
                scene_id=scene_id,
                path=str(baseline_entry.path),
                source="library",
                source_type="user",
                dirty=False,
            )
            is True
        )
        target = baseline_entry.path
        original_bytes = target.read_bytes()

        scene = bridge.current_scene()
        scene.name = "SCENE_SAVE_ROLLBACK_SENTINEL"
        bridge.set_current_scene(
            scene,
            config_id=scene_id,
            path=str(target),
            source="library",
            source_type="user",
            emit_signal=False,
        )
        bridge.set_scene_dirty(True)

        def write_then_return(scene_to_save, scene_id=None, *, mode_id=None):
            assert scene_to_save.name == "SCENE_SAVE_ROLLBACK_SENTINEL"
            assert mode_id == "exam"
            entry = config_library.save_scene_to_library(
                scene_to_save,
                scene_id=scene_id,
                mode_id=mode_id,
            )
            assert entry.path == target
            assert target.read_bytes() != original_bytes
            return entry

        assert (
            panel.prepare_pending_scene_changes(
                "save",
                save_callable=write_then_return,
                mode_id="exam",
            )
            is True
        )

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
        assert injected["raised"] is True
        assert target.read_bytes() == original_bytes
        assert bridge.current_scene_id() == scene_id
        assert bridge.current_scene().name == "SCENE_SAVE_ROLLBACK_SENTINEL"
        assert bridge.is_scene_dirty() is True
        assert panel._current_scene is bridge.current_scene()
        assert panel._overview._combo.currentData() == scene_id
    finally:
        bridge.clear_scene_dirty()
        panel.close()
        qapp.processEvents()


def test_scene_save_revision_conflict_preserves_external_writer(
    qapp,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "plans")
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    panel = ScenePanel(bridge)
    bridge.commit_pending_work_mode_transition()
    try:
        scene_id = "revision-user-scene"
        baseline_scene = copy.deepcopy(load_scene_from_library("exam", mode_id="exam"))
        baseline_scene.scene_id = scene_id
        baseline_scene.name = "REVISION_USER_BASELINE"
        baseline_entry = config_library.save_scene_to_library(
            baseline_scene,
            scene_id=scene_id,
            mode_id="exam",
        )
        assert (
            panel._activate_scene(
                load_scene_from_library(scene_id, mode_id="exam"),
                scene_id=scene_id,
                path=str(baseline_entry.path),
                source="library",
                source_type="user",
                dirty=False,
            )
            is True
        )
        bridge.set_scene_dirty(True)
        target = baseline_entry.path
        called = {"save": False}

        def unexpected_save(*_args, **_kwargs):
            called["save"] = True
            raise AssertionError("revision conflict must stop before publication")

        assert (
            panel.prepare_pending_scene_changes(
                "save",
                save_callable=unexpected_save,
                mode_id="exam",
            )
            is True
        )
        target.write_bytes(b"EXTERNAL_WRITER_REVISION")

        assert panel.commit_prepared_scene_changes() is False
        assert called["save"] is False
        assert target.read_bytes() == b"EXTERNAL_WRITER_REVISION"
        assert bridge.is_scene_dirty() is True
    finally:
        panel.cancel_prepared_scene_changes()
        bridge.clear_scene_dirty()
        panel.close()
        qapp.processEvents()


def test_scene_save_prepare_rejects_unsafe_active_identity_before_path_access(
    qapp,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "plans")
    bridge = PanelBridge()
    panel = ScenePanel(bridge)
    try:
        scene = bridge.current_scene()
        bridge.set_current_scene(
            scene,
            config_id="../outside",
            path=bridge.current_scene_path(),
            source=bridge.current_scene_source(),
            source_type=bridge.current_scene_source_type(),
            emit_signal=False,
        )
        bridge.set_scene_dirty(True)
        monkeypatch.setattr(
            "src.ui.panels.scene_panel.Toast.show_error",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": "safe fork target",
        )

        assert panel.prepare_pending_scene_changes("save") is False
        assert panel._scene_session.prepared_changes is None
        assert (tmp_path / "outside.json").exists() is False
    finally:
        panel.cancel_prepared_scene_changes()
        bridge.clear_scene_dirty()
        panel.close()
        qapp.processEvents()


def test_scene_save_rejects_and_rolls_back_unprepared_returned_target(
    qapp,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", tmp_path / "plans")
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    panel = ScenePanel(bridge)
    bridge.commit_pending_work_mode_transition()
    try:
        original_scene_id = bridge.current_scene_id()
        scene = bridge.current_scene()
        returned_scene_id = "exam-returned-target"
        baseline_scene = copy.deepcopy(scene)
        baseline_scene.name = "RETURNED_TARGET_BASELINE"
        baseline_entry = config_library.save_scene_to_library(
            baseline_scene,
            scene_id=returned_scene_id,
            mode_id="exam",
        )
        returned_target = baseline_entry.path
        baseline_bytes = returned_target.read_bytes()

        scene.name = "CANONICAL_ADOPTION_SENTINEL"
        bridge.set_current_scene(
            scene,
            config_id=original_scene_id,
            path=bridge.current_scene_path(),
            source=bridge.current_scene_source(),
            source_type=bridge.current_scene_source_type(),
            emit_signal=False,
        )
        bridge.set_scene_dirty(True)
        expected_scene_id = "canonical expected target"
        expected_target = config_library.scene_user_target_path(
            expected_scene_id,
            mode_id="exam",
        )
        monkeypatch.setattr(
            panel,
            "_prompt_scene_save_as_name",
            lambda _reason="": expected_scene_id,
        )

        def save_to_returned_target(scene_to_save, **_kwargs):
            return config_library.save_scene_to_library(
                scene_to_save,
                scene_id=returned_scene_id,
                mode_id="exam",
            )

        assert (
            panel.prepare_pending_scene_changes(
                "save",
                save_callable=save_to_returned_target,
                mode_id="exam",
            )
            is True
        )
        assert panel.commit_prepared_scene_changes() is False

        assert returned_target.read_bytes() == baseline_bytes
        assert expected_target.exists() is False
        assert bridge.current_scene_id() == original_scene_id
        assert bridge.current_scene().name == "CANONICAL_ADOPTION_SENTINEL"
        assert bridge.is_scene_dirty() is True
    finally:
        panel.cancel_prepared_scene_changes()
        bridge.clear_scene_dirty()
        panel.close()
        qapp.processEvents()
