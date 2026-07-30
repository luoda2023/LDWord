from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

import pytest

from src.config.loader import load_template, save_template
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.config.template_save_transaction import (
    TemplateSaveItem,
    save_template_batch,
)
from src.qt_api import QApplication, QWidget
from src.ui.bridge import PanelBridge
from src.ui.main_window import MainWindow
from src.ui.panels.scene_panel import ScenePanel
from src.ui.panels.template_caption_detail import CaptionDetail
from src.ui.panels.template_elements_detail import ElementsDetail
from src.ui.panels.template_formula_detail import FormulaDetail
from src.ui.panels.template_other_detail import OtherDetail
from src.ui.panels.template_panel import (
    TEMPLATE_EDIT_CANCEL,
    TEMPLATE_EDIT_DISCARD,
    TEMPLATE_EDIT_SAVE,
    TemplatePanel,
)
from src.ui.panels.template_reference_detail import ReferenceDetail
from src.ui.panels.template_style_detail import StyleDetail
from src.ui.panels.template_table_detail import TableCaptionDetail
from src.ui.panels.workbench import WorkbenchPanel
from src.ui.template_edit_session import (
    TemplateDraftCollisionError,
    TemplateDraftStore,
    TemplateEditSession,
)
from src.ui.template_draft_save_coordinator import (
    OVERWRITE_EXISTING_TARGET,
    TemplateDraftSaveCoordinator,
    TemplateSavePreparationCancelled,
    TemplateSaveRevisionChanged,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _complete_close_protocol(panel) -> bool:
    if not panel.prepare_close_pending_changes():
        return False
    if not panel.commit_close_pending_changes():
        rollback = getattr(panel, "rollback_close_pending_changes", None)
        if callable(rollback):
            rollback()
        return False
    panel.finalize_close_pending_changes()
    return True


def test_template_edit_session_separates_draft_commit_and_discard(tmp_path):
    template = TemplateConfig()
    source = save_template(template, tmp_path / "template.json")
    session = TemplateEditSession(template, source_path=source)

    session.draft.page_setup.margin.top_cm += 1.0

    assert session.is_dirty() is True
    assert session.committed_copy().page_setup.margin.top_cm != session.draft.page_setup.margin.top_cm

    restored = session.discard()

    assert session.is_dirty() is False
    assert restored == template


def test_template_edit_session_copies_a_replacement_draft_from_external_owner():
    session = TemplateEditSession(TemplateConfig(name="committed"))
    external = TemplateConfig(name="external draft")

    adopted = session.replace_draft(external)
    external.name = "mutated elsewhere"

    assert adopted is session.draft
    assert session.draft.name == "external draft"
    assert session.is_dirty() is True


def test_unsaved_template_draft_does_not_reach_bridge_or_workbench(tmp_path):
    app = _app()
    source_template = TemplateConfig()
    source = save_template(source_template, tmp_path / "user-template.json")
    bridge = PanelBridge()
    bridge.set_current_template(
        source_template,
        config_id=source.stem,
        path=str(source),
        source="file",
        source_type="external",
        emit_signal=False,
    )
    workbench = WorkbenchPanel(bridge)
    panel = TemplatePanel(bridge)
    try:
        committed_margin = bridge.current_template().page_setup.margin.top_cm
        panel._current_template.page_setup.margin.top_cm = committed_margin + 1.25
        panel._on_template_edited(panel._current_template)
        app.processEvents()

        assert bridge.is_template_dirty() is True
        assert bridge.current_template().page_setup.margin.top_cm == committed_margin
        assert workbench._current_template.page_setup.margin.top_cm == committed_margin

        assert panel._save_current_template() is True
        app.processEvents()

        expected = committed_margin + 1.25
        assert bridge.is_template_dirty() is False
        assert bridge.current_template().page_setup.margin.top_cm == expected
        assert workbench._current_template.page_setup.margin.top_cm == expected
        assert load_template(source).page_setup.margin.top_cm == expected
    finally:
        panel.close()
        workbench.close()
        app.processEvents()


def test_template_draft_dirty_state_does_not_block_workbench_binding():
    app = _app()
    bridge = PanelBridge()
    workbench = WorkbenchPanel(bridge)
    try:
        target_scene = deepcopy(workbench._current_scene)
        target_template_id = workbench._quick_execution_detail.current_template_id()
        bridge.set_current_scene(
            SceneWorkspace(
                scene_id="sentinel",
                name="sentinel",
                template_id=target_template_id,
                compatible_template_ids=[target_template_id],
            ),
            config_id="sentinel",
            emit_signal=False,
        )
        bridge.mark_template_dirty()

        workbench._on_quick_binding_changed(target_scene, target_template_id)
        app.processEvents()

        assert bridge.current_scene_id() == target_scene.scene_id
        assert bridge.current_template_id() == target_template_id
        assert bridge.is_template_dirty() is True
    finally:
        workbench.close()
        app.processEvents()


def test_template_draft_dirty_state_does_not_block_scene_template_binding():
    app = _app()
    bridge = PanelBridge()
    panel = ScenePanel(bridge)
    try:
        target_template_id = str(panel._current_scene.template_id or "").strip()
        assert target_template_id
        bridge.set_current_template(
            TemplateConfig(name="sentinel"),
            config_id="sentinel",
            emit_signal=False,
        )
        bridge.mark_template_dirty()

        panel._sync_bound_template_from_scene()
        app.processEvents()

        assert bridge.current_template_id() == target_template_id
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_scene_template_binding_does_not_reuse_same_id_from_another_work_mode():
    app = _app()
    bridge = PanelBridge()
    panel = ScenePanel(bridge)
    try:
        target_template_id = str(panel._current_scene.template_id or "").strip()
        assert target_template_id == "default"
        bridge.set_current_template(
            TemplateConfig(name="custom-mode sentinel"),
            config_id=target_template_id,
            emit_signal=False,
        )
        assert bridge.current_template_mode_id() == "custom"

        bridge.set_current_work_mode("exam", emit_signal=False)
        panel._sync_bound_template_from_scene()
        app.processEvents()

        assert bridge.current_template_id() == target_template_id
        assert bridge.current_template_mode_id() == "exam"
        assert bridge.current_template().name != "custom-mode sentinel"
    finally:
        panel.close()
        app.processEvents()


def test_external_source_change_blocks_save_and_preserves_draft(tmp_path, monkeypatch):
    _app()
    source_template = TemplateConfig()
    source = save_template(source_template, tmp_path / "external-template.json")
    bridge = PanelBridge()
    bridge.set_current_template(
        source_template,
        config_id=source.stem,
        path=str(source),
        source="file",
        source_type="external",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        draft_margin = source_template.page_setup.margin.top_cm + 1.0
        panel._current_template.page_setup.margin.top_cm = draft_margin
        panel._on_template_edited(panel._current_template)

        external = deepcopy(source_template)
        external.page_setup.margin.top_cm += 3.0
        save_template(external, source)
        monkeypatch.setattr(
            "src.ui.panels.template_panel.confirm",
            lambda *_args, **_kwargs: False,
        )

        assert panel._save_current_template() is False
        assert bridge.is_template_dirty() is True
        assert panel._current_template.page_setup.margin.top_cm == draft_margin
        assert load_template(source).page_setup.margin.top_cm == external.page_setup.margin.top_cm
        assert bridge.current_template().page_setup.margin.top_cm == source_template.page_setup.margin.top_cm
    finally:
        panel.close()


def test_new_external_target_requires_overwrite_confirmation(tmp_path):
    target = tmp_path / "created-after-activation.json"
    store = TemplateDraftStore()
    context = store.activate(
        TemplateConfig(name="committed"),
        mode_id="custom",
        template_id="logical-id",
        path=target,
    )
    context.session.draft.name = "draft"
    save_template(TemplateConfig(name="external"), target)
    confirmations: list[tuple[str, Path]] = []
    coordinator = TemplateDraftSaveCoordinator(
        store,
        confirm_overwrite=lambda reason, path: (
            confirmations.append((reason, path)) or False
        ),
    )

    with pytest.raises(TemplateSavePreparationCancelled):
        coordinator.prepare((context,))

    assert confirmations == [(OVERWRITE_EXISTING_TARGET, target)]
    assert context.session.is_dirty() is True
    assert load_template(target).name == "external"


def test_prepared_save_rejects_target_changed_before_commit(tmp_path):
    target = save_template(TemplateConfig(name="committed"), tmp_path / "target.json")
    store = TemplateDraftStore()
    context = store.activate(
        load_template(target),
        mode_id="custom",
        template_id="logical-id",
        path=target,
    )
    context.session.draft.name = "draft"
    coordinator = TemplateDraftSaveCoordinator(
        store,
        confirm_overwrite=lambda _reason, _path: True,
    )
    plans = coordinator.prepare((context,))
    save_template(TemplateConfig(name="external"), target)

    with pytest.raises(TemplateSaveRevisionChanged):
        coordinator.commit(plans)

    assert context.session.is_dirty() is True
    assert load_template(target).name == "external"


def test_save_preparation_rejects_an_existing_non_file_target(tmp_path):
    target = tmp_path / "directory.json"
    target.mkdir()
    store = TemplateDraftStore()
    context = store.activate(
        TemplateConfig(name="committed"),
        mode_id="custom",
        template_id="logical-id",
        path=target,
    )
    context.session.draft.name = "draft"
    coordinator = TemplateDraftSaveCoordinator(
        store,
        confirm_overwrite=lambda *_args: pytest.fail(
            "an unreadable target must fail before overwrite confirmation"
        ),
    )

    with pytest.raises(OSError, match="可读取的常规文件"):
        coordinator.prepare((context,))

    assert context.session.is_dirty() is True


def test_detail_navigation_keeps_draft_without_prompt_or_publish():
    app = _app()
    panel = TemplatePanel(PanelBridge())
    try:
        panel._ensure_detail_loaded("tpl_page")
        panel._finish_detail_transition("tpl_page")
        original = panel._edit_session.committed_copy().page_setup.margin.top_cm
        panel._current_template.page_setup.margin.top_cm = original + 2.0
        panel._on_template_edited(panel._current_template)

        assert not hasattr(panel, "_prompt_pending_template_action")
        panel._show_detail("tpl_overview")
        app.processEvents()

        assert panel._current_detail_card_id == "tpl_overview"
        assert panel._current_template.page_setup.margin.top_cm == original + 2.0
        assert panel._edit_session.is_dirty() is True
        assert panel.bridge.is_template_dirty() is True
        assert panel.bridge.current_template().page_setup.margin.top_cm == original
    finally:
        panel.close()
        app.processEvents()


def test_template_draft_store_restores_independent_draft_after_switching():
    first = TemplateConfig(name="first")
    second = TemplateConfig(name="second")
    store = TemplateDraftStore()

    first_context = store.activate(
        first,
        mode_id="custom",
        template_id="first",
        path="first.json",
    )
    original_margin = first_context.session.draft.page_setup.margin.top_cm
    first_context.session.draft.page_setup.margin.top_cm = original_margin + 1.5

    second_context = store.activate(
        second,
        mode_id="custom",
        template_id="second",
        path="second.json",
    )
    restored_first = store.activate(
        deepcopy(first),
        mode_id="custom",
        template_id="first",
        path="first.json",
    )

    assert second_context.session.is_dirty() is False
    assert restored_first is first_context
    assert restored_first.session.draft.page_setup.margin.top_cm == original_margin + 1.5
    assert restored_first.session.committed_copy().page_setup.margin.top_cm == original_margin
    assert store.dirty_contexts() == (first_context,)


def test_template_draft_store_uses_mode_and_path_as_resource_identity(tmp_path):
    source = tmp_path / "shared.json"
    store = TemplateDraftStore()
    original = store.activate(
        TemplateConfig(name="original"),
        mode_id="custom",
        template_id="old-logical-id",
        path=source,
    )
    original.session.draft.name = "preserved draft"

    aliased = store.activate(
        TemplateConfig(name="incoming committed"),
        mode_id="custom",
        template_id="new-logical-id",
        path=source,
    )

    assert aliased is original
    assert len(store) == 1
    assert aliased.template_id == "new-logical-id"
    assert aliased.session.draft.name == "preserved draft"


def test_template_draft_store_rejects_rekey_over_another_dirty_context(tmp_path):
    store = TemplateDraftStore()
    pathless = store.activate(
        TemplateConfig(name="pathless"),
        mode_id="custom",
        template_id="logical-id",
        path="",
    )
    existing = store.activate(
        TemplateConfig(name="existing"),
        mode_id="custom",
        template_id="existing-id",
        path=tmp_path / "target.json",
    )
    existing.session.draft.name = "existing dirty draft"

    with pytest.raises(TemplateDraftCollisionError):
        store.ensure_rekey_available(
            pathless,
            mode_id="custom",
            template_id="logical-id",
            path=tmp_path / "target.json",
        )
    with pytest.raises(TemplateDraftCollisionError):
        store.rekey(
            pathless,
            mode_id="custom",
            template_id="logical-id",
            path=tmp_path / "target.json",
            source="library",
            source_type="user",
        )

    assert len(store) == 2
    assert existing in store.dirty_contexts()


def test_switching_templates_caches_draft_without_writing_source_json(tmp_path):
    _app()
    first = TemplateConfig(name="first")
    second = TemplateConfig(name="second")
    first_path = save_template(first, tmp_path / "first.json")
    second_path = save_template(second, tmp_path / "second.json")
    bridge = PanelBridge()
    bridge.set_current_template(
        first,
        config_id="first",
        path=str(first_path),
        source="file",
        source_type="external",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        panel._current_template.name = "first draft"
        panel._on_template_edited(panel._current_template)
        panel._activate_template(
            second,
            template_id="second",
            path=str(second_path),
            source="file",
            source_type="external",
        )

        assert load_template(first_path).name == "first"
        assert bridge.current_template().name == "second"

        panel._activate_template(
            load_template(first_path),
            template_id="first",
            path=str(first_path),
            source="file",
            source_type="external",
        )

        assert panel._current_template.name == "first draft"
        assert bridge.current_template().name == "first"
        assert panel._edit_session.is_dirty() is True
    finally:
        panel._discard_all_pending_template_edits()
        panel.close()


def test_builtin_template_save_creates_user_copy_without_mutating_source(
    tmp_path,
    monkeypatch,
):
    import src.config.library as library

    _app()
    template_dir = tmp_path / "templates"
    scene_dir = tmp_path / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    source_template = TemplateConfig(name="builtin source")
    source = save_template(source_template, tmp_path / "builtin" / "default.json")
    source_bytes = source.read_bytes()
    bridge = PanelBridge()
    bridge.set_current_template(
        source_template,
        config_id="default",
        path=str(source),
        source="library",
        source_type="builtin",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        prompt: dict[str, object] = {}

        def name_user_copy(*_args, **kwargs):
            prompt.update(kwargs)
            return "saved user copy"

        panel._template_text_request = name_user_copy
        panel._current_template.page_setup.margin.top_cm += 1.0
        panel._on_template_edited(panel._current_template)
        style_detail = panel._ensure_detail_loaded("tpl_style")

        assert panel._can_save_in_place() is False
        assert style_detail._save_btn.text() == "保存"
        assert panel._save_current_template() is True
        saved = Path(panel._current_template_path)
        assert prompt["ok_text"] == "保存副本"
        assert source.read_bytes() == source_bytes
        assert load_template(source).name == "builtin source"
        assert saved != source
        assert saved.parent == template_dir / "custom" / "user"
        assert load_template(saved).name == "saved user copy"
        assert panel._current_template_source_type == "user"
        assert panel.pending_template_draft_count() == 0
        assert bridge.current_template().name == "saved user copy"
        assert bridge.current_template_path() == str(saved)
    finally:
        panel.close()


def test_in_place_save_preserves_logical_template_id_when_filename_differs(
    tmp_path,
    monkeypatch,
):
    _app()
    template = TemplateConfig(name="saved")
    source = save_template(template, tmp_path / "physical-file.json")
    bridge = PanelBridge()
    bridge.set_current_template(
        template,
        config_id="logical-template-id",
        path=str(source),
        source="file",
        source_type="external",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        monkeypatch.setattr(
            "src.ui.panels.template_panel.confirm",
            lambda *_args, **_kwargs: True,
        )
        panel._current_template.name = "updated"
        panel._on_template_edited(panel._current_template)

        assert panel._save_current_template() is True
        assert panel._current_template_id == "logical-template-id"
        assert bridge.current_template_id() == "logical-template-id"
        assert bridge.current_template_path() == str(source)
        assert load_template(source).name == "updated"
    finally:
        panel.close()


def test_template_batch_save_rolls_back_all_targets_on_commit_failure(
    tmp_path,
    monkeypatch,
):
    import src.config.template_save_transaction as transaction

    first_path = save_template(TemplateConfig(name="first saved"), tmp_path / "first.json")
    second_path = save_template(TemplateConfig(name="second saved"), tmp_path / "second.json")
    real_replace = os.replace

    def fail_second_stage_commit(source, target):
        source_path = Path(source)
        target_path = Path(target)
        if target_path == second_path and ".stage" in source_path.name:
            raise OSError("simulated second-target commit failure")
        return real_replace(source, target)

    monkeypatch.setattr(transaction.os, "replace", fail_second_stage_commit)

    with pytest.raises(OSError, match="second-target"):
        save_template_batch(
            (
                TemplateSaveItem(TemplateConfig(name="first draft"), first_path),
                TemplateSaveItem(TemplateConfig(name="second draft"), second_path),
            )
        )

    assert load_template(first_path).name == "first saved"
    assert load_template(second_path).name == "second saved"
    assert not tuple(tmp_path.glob(".*.stage.json"))
    assert not tuple(tmp_path.glob(".*.backup.json"))


def test_template_batch_save_cleans_partial_stage_after_serialization_failure(
    tmp_path,
    monkeypatch,
):
    import src.config.template_save_transaction as transaction

    target = save_template(TemplateConfig(name="committed"), tmp_path / "target.json")

    def fail_after_partial_stage(_template, path):
        Path(path).write_text("{", encoding="utf-8")
        raise OSError("simulated serialization failure")

    monkeypatch.setattr(transaction, "save_template", fail_after_partial_stage)

    with pytest.raises(OSError, match="serialization failure"):
        save_template_batch((TemplateSaveItem(TemplateConfig(name="draft"), target),))

    assert load_template(target).name == "committed"
    assert not tuple(tmp_path.glob(".*.stage.json"))
    assert not tuple(tmp_path.glob(".*.backup.json"))


def test_close_is_the_resolution_point_for_all_cached_template_drafts(
    tmp_path,
    monkeypatch,
):
    _app()
    first = TemplateConfig(name="first")
    second = TemplateConfig(name="second")
    first_path = save_template(first, tmp_path / "first.json")
    second_path = save_template(second, tmp_path / "second.json")
    bridge = PanelBridge()
    bridge.set_current_template(
        first,
        config_id="first",
        path=str(first_path),
        source="file",
        source_type="external",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        panel._current_template.name = "first draft"
        panel._on_template_edited(panel._current_template)
        panel._activate_template(
            second,
            template_id="second",
            path=str(second_path),
            source="file",
            source_type="external",
        )
        panel._current_template.name = "second draft"
        panel._on_template_edited(panel._current_template)

        assert panel.request_leave_pending_changes("switch panel") is True
        assert panel.pending_template_draft_count() == 2

        monkeypatch.setattr(
            panel,
            "_prompt_close_template_draft_action",
            lambda _count: TEMPLATE_EDIT_SAVE,
        )
        assert _complete_close_protocol(panel) is True
        assert panel.pending_template_draft_count() == 0
        assert load_template(first_path).name == "first draft"
        assert load_template(second_path).name == "second draft"
    finally:
        panel.close()


def test_close_save_all_failure_keeps_every_context_dirty_and_files_unchanged(
    tmp_path,
    monkeypatch,
):
    _app()
    first = TemplateConfig(name="first")
    second = TemplateConfig(name="second")
    first_path = save_template(first, tmp_path / "first.json")
    second_path = save_template(second, tmp_path / "second.json")
    bridge = PanelBridge()
    bridge.set_current_template(
        first,
        config_id="first",
        path=str(first_path),
        source="file",
        source_type="external",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        panel._current_template.name = "first draft"
        panel._on_template_edited(panel._current_template)
        panel._activate_template(
            second,
            template_id="second",
            path=str(second_path),
            source="file",
            source_type="external",
        )
        panel._current_template.name = "second draft"
        panel._on_template_edited(panel._current_template)
        monkeypatch.setattr(
            panel,
            "_prompt_close_template_draft_action",
            lambda _count: TEMPLATE_EDIT_SAVE,
        )

        def fail_batch(_items):
            raise OSError("simulated batch failure")

        monkeypatch.setattr(panel._draft_save_coordinator, "_save_batch", fail_batch)

        assert _complete_close_protocol(panel) is False
        assert panel.pending_template_draft_count() == 2
        assert load_template(first_path).name == "first"
        assert load_template(second_path).name == "second"
    finally:
        panel._discard_all_pending_template_edits()
        panel.close()


def test_close_cancel_keeps_draft_and_discard_does_not_write_json(
    tmp_path,
    monkeypatch,
):
    _app()
    saved = TemplateConfig(name="saved")
    source = save_template(saved, tmp_path / "saved.json")
    bridge = PanelBridge()
    bridge.set_current_template(
        saved,
        config_id="saved",
        path=str(source),
        source="file",
        source_type="external",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        panel._current_template.name = "draft"
        panel._on_template_edited(panel._current_template)
        action = {"value": TEMPLATE_EDIT_CANCEL}
        monkeypatch.setattr(
            panel,
            "_prompt_close_template_draft_action",
            lambda _count: action["value"],
        )

        assert _complete_close_protocol(panel) is False
        assert panel.pending_template_draft_count() == 1
        assert panel._current_template.name == "draft"
        assert load_template(source).name == "saved"

        action["value"] = TEMPLATE_EDIT_DISCARD
        assert _complete_close_protocol(panel) is True
        assert panel.pending_template_draft_count() == 0
        assert panel._current_template.name == "saved"
        assert load_template(source).name == "saved"
    finally:
        panel.close()


def test_opening_template_details_is_model_read_only():
    _app()
    details = (
        StyleDetail(),
        TableCaptionDetail(),
        ElementsDetail(scope="header_footer"),
        ElementsDetail(scope="toc"),
        CaptionDetail(),
        ReferenceDetail(),
        FormulaDetail(),
        OtherDetail(),
    )
    try:
        for detail in details:
            template = TemplateConfig()
            before = deepcopy(template)
            detail.set_template(template)
            assert template == before, type(detail).__name__
    finally:
        for detail in details:
            detail.close()


def test_template_panel_preloading_details_does_not_create_a_draft_change():
    app = _app()
    panel = TemplatePanel(PanelBridge())
    try:
        panel.preload_details_for_startup()
        app.processEvents()

        assert panel._edit_session.is_dirty() is False
        assert panel.bridge.is_template_dirty() is False
        assert panel._current_template == panel._edit_session.committed_copy()
    finally:
        panel.close()


class _LeaveGuardPanel(QWidget):
    def __init__(self, allow_leave: bool):
        super().__init__()
        self.allow_leave = allow_leave
        self.reasons: list[str] = []

    def request_leave_pending_changes(self, reason: str) -> bool:
        self.reasons.append(reason)
        return self.allow_leave


class _CanonicalCloseGuardPanel(QWidget):
    def __init__(self, allow_close: bool):
        super().__init__()
        self.allow_close = allow_close
        self.prepare_requests = 0
        self.leave_requests = 0

    def request_leave_pending_changes(self, _reason: str = "") -> bool:
        self.leave_requests += 1
        return True

    def prepare_close_pending_changes(self) -> bool:
        self.prepare_requests += 1
        return self.allow_close

    def commit_close_pending_changes(self) -> bool:
        return True


class _TwoPhaseClosePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.prepare_requests = 0
        self.commit_requests = 0
        self.cancel_requests = 0

    def prepare_close_pending_changes(self) -> bool:
        self.prepare_requests += 1
        return True

    def commit_close_pending_changes(self) -> bool:
        self.commit_requests += 1
        return True

    def cancel_prepared_close(self) -> None:
        self.cancel_requests += 1


class _ShutdownRejectPanel(QWidget):
    def shutdown_active_execution(self, timeout_ms=1000) -> bool:
        del timeout_ms
        return False


def test_navigation_leave_guard_is_not_a_second_close_protocol():
    _app()
    window = MainWindow(enable_background_services=False)
    guard = _LeaveGuardPanel(allow_leave=False)
    window.register_panel(0, guard)
    try:
        window.panel_stack.setCurrentIndex(0)
        result = window._show_panel(1, allow_async=False)

        assert result is guard
        assert window.panel_stack.currentIndex() == 0
        assert guard.reasons[-1] == "切换到方案配置"
        assert window.close() is True
    finally:
        guard.allow_leave = True
        window.close()


def test_main_window_prefers_global_close_resolution_over_navigation_guard():
    _app()
    window = MainWindow(enable_background_services=False)
    guard = _CanonicalCloseGuardPanel(allow_close=False)
    window.register_panel(0, guard)
    try:
        assert window.close() is False
        assert guard.prepare_requests == 1
        assert guard.leave_requests == 0

        guard.allow_close = True
        assert window.close() is True
        assert guard.prepare_requests == 2
        assert guard.leave_requests == 0
    finally:
        guard.allow_close = True
        window.close()


def test_close_flow_has_one_two_phase_protocol_without_legacy_fallback():
    paths = (
        Path("src/ui/main_window.py"),
        Path("src/ui/panels/template_panel.py"),
        Path("src/ui/panels/scene_panel.py"),
        Path("src/ui/panels/assets/archive_presenter.py"),
    )

    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "request_close_pending_changes" not in source, path


def test_main_window_does_not_commit_prepared_close_when_shutdown_fails():
    _app()
    window = MainWindow(enable_background_services=False)
    prepared = _TwoPhaseClosePanel()
    reject_shutdown = _ShutdownRejectPanel()
    window.register_panel(0, prepared)
    window.register_panel(1, reject_shutdown)
    try:
        assert window.close() is False
        assert prepared.prepare_requests == 1
        assert prepared.commit_requests == 0
        assert prepared.cancel_requests == 1
    finally:
        window.register_panel(1, QWidget())
        window.close()
