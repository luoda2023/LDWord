from __future__ import annotations

import pytest

from src.config import library as config_library
from src.config.execution_target import ExecutionTarget
from src.config.material_batch import MaterialBatchSelection
from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.ui import bridge as bridge_module
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_session_coordinator import (
    SceneProjectionCallbacks,
    SceneSessionCoordinator,
)


def _scene_target_resolver(
    *,
    mode_id: str,
    scene=None,
    document_path: str = "",
    official_document_type_id: str = "",
) -> ExecutionTarget:
    del official_document_type_id
    scene_id = str(getattr(scene, "scene_id", "") or "none")
    return ExecutionTarget(
        mode_id=mode_id,
        document_path=document_path,
        issues=(f"scene:{scene_id}",),
    )


def _scoped_bridge(monkeypatch) -> tuple[PanelBridge, SceneWorkspace, SceneWorkspace]:
    monkeypatch.setattr(
        bridge_module,
        "resolve_execution_target",
        _scene_target_resolver,
    )
    bridge = PanelBridge()
    builtin = SceneWorkspace(
        scene_id="builtin_scene",
        mode_id="custom",
        name="Builtin",
    )
    user_copy = SceneWorkspace(
        scene_id="user_copy",
        mode_id="custom",
        name="User copy",
    )
    bridge.set_current_scene(
        builtin,
        config_id="builtin_scene",
        path="builtin/builtin_scene.json",
        source="library",
        source_type="builtin",
        emit_signal=False,
    )
    bridge.set_current_material_context(
        MaterialExecutionContext(
            mode_id="custom",
            scene_id="builtin_scene",
            package_id="material-package",
        ),
        emit_signal=False,
    )
    bridge.set_current_material_batch_selection(
        MaterialBatchSelection(
            mode_id="custom",
            scene_id="builtin_scene",
            package_id="batch-package",
        ),
        emit_signal=False,
    )
    bridge.set_scene_dirty(True, emit_signal=False)
    return bridge, builtin, user_copy


def _connect_coherence_observers(bridge: PanelBridge):
    events: list[tuple[str, object, tuple[object, ...]]] = []
    slots = []

    def connect(signal, name: str) -> None:
        def observe(payload) -> None:
            context = bridge.current_material_context()
            batch = bridge.current_material_batch_selection()
            events.append(
                (
                    name,
                    payload,
                    (
                        bridge.current_scene_id(),
                        context.package_id,
                        batch.package_id,
                        bridge.current_execution_target().issues,
                        bridge.is_scene_dirty(),
                    ),
                )
            )

        slots.append(observe)
        signal.connect(observe)

    connect(bridge.material_context_changed, "material")
    connect(bridge.material_batch_selection_changed, "batch")
    connect(bridge.material_scope_suspended, "suspended")
    connect(bridge.execution_target_changed, "target")
    connect(bridge.scene_changed, "scene")
    connect(bridge.scene_dirty_changed, "dirty")
    return events, slots


def _adopt_user_copy(bridge: PanelBridge, user_copy: SceneWorkspace):
    transaction = bridge.begin_scene_publication()
    changed = bridge.adopt_scene_provisionally(
        transaction,
        user_copy,
        config_id="user_copy",
        path="user/user_copy.json",
        source="library",
        source_type="user",
        scene_dirty=False,
    )
    assert changed is True
    return transaction


def test_provisional_adoption_is_silent_and_finalize_publishes_one_coherent_diff(
    monkeypatch,
):
    bridge, _builtin, user_copy = _scoped_bridge(monkeypatch)
    events, _slots = _connect_coherence_observers(bridge)

    transaction = _adopt_user_copy(bridge, user_copy)

    assert transaction.status == "active"
    assert events == []
    assert bridge.current_scene_id() == "user_copy"
    assert bridge.current_material_context().is_empty()
    assert bridge.current_material_batch_selection().package_id == ""
    assert bridge.current_execution_target().issues == ("scene:user_copy",)
    assert bridge.is_scene_dirty() is False
    assert len(bridge.suspended_material_states()) == 1

    assert bridge.finalize_scene_publication(transaction) is True

    assert transaction.status == "finalized"
    assert [name for name, _payload, _state in events] == [
        "material",
        "batch",
        "suspended",
        "target",
        "scene",
        "dirty",
    ]
    assert all(
        state == ("user_copy", "", "", ("scene:user_copy",), False)
        for _name, _payload, state in events
    )
    suspended = next(payload for name, payload, _state in events if name == "suspended")
    assert suspended == {
        "reason": "scene_changed",
        "previous_mode_id": "custom",
        "previous_scene_id": "builtin_scene",
        "next_mode_id": "custom",
        "next_scene_id": "user_copy",
    }

    assert bridge.finalize_scene_publication(transaction) is False
    assert len(events) == 6


def test_rollback_before_finalize_restores_the_baseline_without_any_signal(
    monkeypatch,
):
    bridge, _builtin, user_copy = _scoped_bridge(monkeypatch)
    events, _slots = _connect_coherence_observers(bridge)
    transaction = _adopt_user_copy(bridge, user_copy)

    assert bridge.rollback_scene_publication(transaction) is True

    assert transaction.status == "rolled_back"
    assert events == []
    assert bridge.current_scene_id() == "builtin_scene"
    assert bridge.current_scene_source_type() == "builtin"
    assert bridge.current_material_context().package_id == "material-package"
    assert (
        bridge.current_material_batch_selection().package_id
        == "batch-package"
    )
    assert bridge.current_execution_target().issues == ("scene:builtin_scene",)
    assert bridge.is_scene_dirty() is True
    assert bridge.suspended_material_states() == ()
    assert bridge.rollback_scene_publication(transaction) is False
    assert events == []


def test_rollback_after_finalize_publishes_only_the_reverse_coherent_diff(
    monkeypatch,
):
    bridge, _builtin, user_copy = _scoped_bridge(monkeypatch)
    events, _slots = _connect_coherence_observers(bridge)
    transaction = _adopt_user_copy(bridge, user_copy)
    assert bridge.finalize_scene_publication(transaction) is True
    events.clear()

    assert bridge.rollback_scene_publication(transaction) is True

    assert transaction.status == "rolled_back"
    assert [name for name, _payload, _state in events] == [
        "material",
        "batch",
        "target",
        "scene",
        "dirty",
    ]
    assert all(
        state
        == (
            "builtin_scene",
            "material-package",
            "batch-package",
            ("scene:builtin_scene",),
            True,
        )
        for _name, _payload, state in events
    )
    assert bridge.suspended_material_states() == ()


def test_semantic_noop_finalization_emits_nothing(monkeypatch):
    monkeypatch.setattr(
        bridge_module,
        "resolve_execution_target",
        _scene_target_resolver,
    )
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="same", mode_id="custom")
    bridge.set_current_scene(
        scene,
        config_id="same",
        path="user/same.json",
        source="library",
        source_type="user",
        emit_signal=False,
    )
    events, _slots = _connect_coherence_observers(bridge)
    transaction = bridge.begin_scene_publication()

    assert (
        bridge.adopt_scene_provisionally(
            transaction,
            scene,
            config_id="same",
            path="user/same.json",
            source="library",
            source_type="user",
        )
        is False
    )
    assert bridge.finalize_scene_publication(transaction) is False
    assert events == []


def test_tokens_are_bridge_owned_nested_publications_are_rejected(monkeypatch):
    bridge, _builtin, _user_copy = _scoped_bridge(monkeypatch)
    other = PanelBridge()
    transaction = bridge.begin_scene_publication()

    with pytest.raises(RuntimeError, match="already active"):
        bridge.begin_scene_publication()
    with pytest.raises(ValueError, match="another bridge"):
        other.rollback_scene_publication(transaction)

    assert bridge.rollback_scene_publication(transaction) is False


def test_published_rollback_refuses_to_clobber_newer_bridge_state(monkeypatch):
    bridge, _builtin, user_copy = _scoped_bridge(monkeypatch)
    transaction = _adopt_user_copy(bridge, user_copy)
    assert bridge.finalize_scene_publication(transaction) is True
    bridge.set_current_material_context(
        MaterialExecutionContext(
            mode_id="custom",
            scene_id="user_copy",
            package_id="newer-package",
        ),
        emit_signal=False,
    )

    with pytest.raises(RuntimeError, match="stale scene publication"):
        bridge.rollback_scene_publication(transaction)

    assert bridge.current_scene_id() == "user_copy"
    assert bridge.current_material_context().package_id == "newer-package"


def test_finalize_retains_exact_new_suspension_evidence_when_history_is_capped(
    monkeypatch,
):
    bridge, _builtin, user_copy = _scoped_bridge(monkeypatch)
    for index in range(20):
        previous_id = bridge.current_scene_id()
        next_id = f"history_{index}"
        bridge.set_current_material_context(
            MaterialExecutionContext(
                mode_id="custom",
                scene_id=previous_id,
                package_id=f"package-{index}",
            ),
            emit_signal=False,
        )
        bridge.set_current_scene(
            SceneWorkspace(scene_id=next_id, mode_id="custom"),
            config_id=next_id,
            source="library",
            source_type="user",
            emit_signal=False,
        )
    assert len(bridge.suspended_material_states()) == 20
    previous_id = bridge.current_scene_id()
    bridge.set_current_material_context(
        MaterialExecutionContext(
            mode_id="custom",
            scene_id=previous_id,
            package_id="latest-context",
        ),
        emit_signal=False,
    )
    bridge.set_current_material_batch_selection(
        MaterialBatchSelection(
            mode_id="custom",
            scene_id=previous_id,
            package_id="latest-batch",
        ),
        emit_signal=False,
    )
    events, _slots = _connect_coherence_observers(bridge)

    transaction = _adopt_user_copy(bridge, user_copy)
    assert bridge.finalize_scene_publication(transaction) is True

    suspension_events = [
        payload for name, payload, _state in events if name == "suspended"
    ]
    assert suspension_events == [
        {
            "reason": "scene_changed",
            "previous_mode_id": "custom",
            "previous_scene_id": previous_id,
            "next_mode_id": "custom",
            "next_scene_id": "user_copy",
        }
    ]
    assert len(bridge.suspended_material_states()) == 20


def test_bound_template_and_dirty_state_share_scene_publication_and_reverse_diff(
    monkeypatch,
):
    bridge, _builtin, user_copy = _scoped_bridge(monkeypatch)
    old_template = TemplateConfig(name="Old template")
    new_template = TemplateConfig(name="New template")
    bridge.set_current_template(
        old_template,
        config_id="old_template",
        path="templates/old_template.json",
        source="library",
        source_type="user",
        emit_signal=False,
    )
    bridge.set_template_dirty(True, emit_signal=False)
    events: list[tuple[str, object]] = []
    bridge.template_changed.connect(
        lambda template: events.append(("template", template.name))
    )
    bridge.template_dirty_changed.connect(
        lambda dirty: events.append(("dirty", dirty))
    )

    transaction = _adopt_user_copy(bridge, user_copy)
    assert bridge.adopt_template_provisionally(
        transaction,
        new_template,
        config_id="new_template",
        path="templates/new_template.json",
        source="library",
        source_type="user",
        template_dirty=False,
    ) is True

    assert events == []
    assert bridge.current_template_id() == "new_template"
    assert bridge.current_template().name == "New template"
    assert bridge.is_template_dirty() is False

    assert bridge.finalize_scene_publication(transaction) is True
    assert events == [("template", "New template"), ("dirty", False)]

    assert bridge.rollback_scene_publication(transaction) is True
    assert events == [
        ("template", "New template"),
        ("dirty", False),
        ("template", "Old template"),
        ("dirty", True),
    ]
    assert bridge.current_template_id() == "old_template"
    assert bridge.current_template().name == "Old template"
    assert bridge.is_template_dirty() is True


def test_provisional_template_rollback_is_silent(monkeypatch):
    bridge, _builtin, user_copy = _scoped_bridge(monkeypatch)
    bridge.set_current_template(
        TemplateConfig(name="Old template"),
        config_id="old_template",
        source="runtime",
        source_type="runtime",
        emit_signal=False,
    )
    seen_templates: list[TemplateConfig] = []
    bridge.template_changed.connect(seen_templates.append)
    transaction = _adopt_user_copy(bridge, user_copy)
    bridge.adopt_template_provisionally(
        transaction,
        TemplateConfig(name="Provisional template"),
        config_id="provisional_template",
        source="library",
        source_type="user",
    )

    assert bridge.rollback_scene_publication(transaction) is True

    assert seen_templates == []
    assert bridge.current_template_id() == "old_template"
    assert bridge.current_template().name == "Old template"


def test_listener_derived_template_state_survives_outer_publication_rollback(
    monkeypatch,
):
    bridge, _builtin, user_copy = _scoped_bridge(monkeypatch)
    old_template = TemplateConfig(name="Old template")
    new_template = TemplateConfig(name="New template")
    retained_draft = TemplateConfig(name="Listener-owned draft")
    bridge.set_current_template(
        old_template,
        config_id="old_template",
        path="templates/old_template.json",
        source="library",
        source_type="user",
        emit_signal=False,
    )

    transaction = _adopt_user_copy(bridge, user_copy)
    bridge.adopt_template_provisionally(
        transaction,
        new_template,
        config_id="new_template",
        path="templates/new_template.json",
        source="library",
        source_type="user",
    )

    def retain_listener_draft(_template) -> None:
        bridge.replace_protected_template_commits(
            [
                (
                    "custom",
                    "listener_draft",
                    "templates/listener_draft.json",
                    retained_draft,
                )
            ]
        )
        bridge.mark_template_dirty()

    bridge.template_changed.connect(retain_listener_draft)

    assert bridge.finalize_scene_publication(transaction) is True
    assert bridge.is_template_dirty() is True

    # A later outer participant failed.  Reverse only the Scene-owned fields;
    # the synchronous TemplatePanel-style listener state is not stale and must
    # not be replaced by the transaction's earlier full-bridge snapshot.
    assert bridge.rollback_scene_publication(transaction) is True

    restored = bridge.capture_state_snapshot()
    assert bridge.current_scene_id() == "builtin_scene"
    assert bridge.current_template_id() == "old_template"
    assert bridge.is_template_dirty() is True
    assert tuple(restored.protected_template_commits.values()) == (retained_draft,)


def _scene_coordinator_with_owned_user_scene(
    tmp_path,
    monkeypatch,
    *,
    current_template_matches: bool,
):
    root = tmp_path / "config_library"
    monkeypatch.setattr(
        config_library,
        "TEMPLATE_LIBRARY_DIR",
        root / "templates",
    )
    monkeypatch.setattr(
        config_library,
        "SCENE_LIBRARY_DIR",
        root / "plans",
    )
    config_library.ensure_config_library()
    scene = config_library.load_scene_from_library("exam", mode_id="exam")
    scene.scene_id = "owned_scene"
    scene.name = "Owned scene"
    entry = config_library.save_scene_to_library(
        scene,
        scene_id="owned_scene",
        mode_id="exam",
        expected_absent=True,
    )
    scene = config_library.load_scene_from_library("owned_scene", mode_id="exam")
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    bridge.set_current_scene(
        scene,
        config_id="owned_scene",
        path=str(entry.path),
        source="library",
        source_type="user",
        emit_signal=False,
    )
    if current_template_matches:
        template_entry = config_library.get_template_entry(
            scene.template_id,
            mode_id="exam",
        )
        template = config_library.load_template_from_library(
            scene.template_id,
            mode_id="exam",
        )
        bridge.set_current_template(
            template,
            config_id=scene.template_id,
            path=str(template_entry.path),
            source="library",
            source_type=template_entry.source_type,
            emit_signal=False,
        )
    else:
        bridge.set_current_template(
            TemplateConfig(name="Old template"),
            config_id="old_template",
            source="runtime",
            source_type="runtime",
            emit_signal=False,
        )
    bridge.commit_pending_work_mode_transition()
    coordinator = SceneSessionCoordinator(
        bridge,
        SceneProjectionCallbacks(
            apply_scene=lambda *_args: None,
            refresh_scene_selector=lambda: None,
            selected_card_id=lambda: "",
            restore_selected_card=lambda _card_id: None,
            refresh_navigation_cards=lambda: None,
        ),
    )
    return bridge, coordinator


def test_coordinator_defers_bound_template_signal_until_finalize(
    tmp_path,
    monkeypatch,
):
    bridge, coordinator = _scene_coordinator_with_owned_user_scene(
        tmp_path,
        monkeypatch,
        current_template_matches=False,
    )
    seen_template_ids: list[str] = []
    bridge.template_changed.connect(
        lambda _template: seen_template_ids.append(bridge.current_template_id())
    )

    assert coordinator.prepare_pending_changes("save", force_save=True).success
    assert coordinator.commit_prepared_changes().success

    assert seen_template_ids == []
    assert bridge.current_template_id() == "default"
    assert coordinator.finalize_prepared_changes().success
    assert seen_template_ids == ["default"]


def test_coordinator_provisional_template_rollback_has_no_leaked_signal(
    tmp_path,
    monkeypatch,
):
    bridge, coordinator = _scene_coordinator_with_owned_user_scene(
        tmp_path,
        monkeypatch,
        current_template_matches=False,
    )
    seen_template_ids: list[str] = []
    bridge.template_changed.connect(
        lambda _template: seen_template_ids.append(bridge.current_template_id())
    )

    assert coordinator.prepare_pending_changes("save", force_save=True).success
    assert coordinator.commit_prepared_changes().success
    assert bridge.current_template_id() == "default"
    assert coordinator.rollback_prepared_changes().success

    assert seen_template_ids == []
    assert bridge.current_template_id() == "old_template"


def test_coordinator_retained_rollback_preserves_template_listener_state(
    tmp_path,
    monkeypatch,
):
    bridge, coordinator = _scene_coordinator_with_owned_user_scene(
        tmp_path,
        monkeypatch,
        current_template_matches=False,
    )
    retained_draft = TemplateConfig(name="Retained listener draft")

    def retain_listener_draft(_template) -> None:
        bridge.replace_protected_template_commits(
            [
                (
                    "exam",
                    "retained_listener_draft",
                    "templates/retained_listener_draft.json",
                    retained_draft,
                )
            ]
        )
        bridge.mark_template_dirty()

    bridge.template_changed.connect(retain_listener_draft)

    assert coordinator.prepare_pending_changes("save", force_save=True).success
    assert coordinator.commit_prepared_changes().success
    assert coordinator.finalize_prepared_changes(retain_rollback=True).success
    assert bridge.current_template_id() == "default"
    assert bridge.is_template_dirty() is True

    # Simulate a later outer participant failing after Scene publication.
    result = coordinator.rollback_prepared_changes()

    assert result.success is True
    assert coordinator.prepared_changes is None
    assert bridge.current_template_id() == "old_template"
    assert bridge.is_template_dirty() is True
    snapshot = bridge.capture_state_snapshot()
    assert tuple(snapshot.protected_template_commits.values()) == (retained_draft,)


def test_coordinator_stale_publication_rollback_never_clobbers_newer_template(
    tmp_path,
    monkeypatch,
):
    bridge, coordinator = _scene_coordinator_with_owned_user_scene(
        tmp_path,
        monkeypatch,
        current_template_matches=False,
    )
    assert coordinator.prepare_pending_changes("save", force_save=True).success
    assert coordinator.commit_prepared_changes().success
    assert coordinator.finalize_prepared_changes(retain_rollback=True).success

    newer_template = TemplateConfig(name="Newer unrelated template")
    bridge.set_current_template(
        newer_template,
        config_id="newer_template",
        source="runtime",
        source_type="runtime",
        emit_signal=False,
    )

    result = coordinator.rollback_prepared_changes()

    assert result.success is False
    assert "stale scene publication" in str(result.error)
    assert bridge.current_template_id() == "newer_template"
    assert bridge.current_template().name == "Newer unrelated template"
    assert coordinator.prepared_changes is not None
    assert coordinator.prepared_changes.recovery_required is True


def test_coordinator_accepts_successful_no_diff_finalization(
    tmp_path,
    monkeypatch,
):
    bridge, coordinator = _scene_coordinator_with_owned_user_scene(
        tmp_path,
        monkeypatch,
        current_template_matches=True,
    )
    scene_events: list[SceneWorkspace] = []
    template_events: list[TemplateConfig] = []
    bridge.scene_changed.connect(scene_events.append)
    bridge.template_changed.connect(template_events.append)

    assert bridge.is_scene_dirty() is False
    assert coordinator.prepare_pending_changes("save", force_save=True).success
    assert coordinator.commit_prepared_changes().success
    transaction = coordinator.prepared_changes.publication_transaction

    result = coordinator.finalize_prepared_changes()

    assert result.success is True
    assert result.error is None
    assert transaction.status == "finalized"
    assert coordinator.prepared_changes is None
    assert bridge._active_scene_publication is None
    assert scene_events == []
    assert template_events == []


def test_coordinator_refuses_to_overwrite_committed_unfinalized_transaction(
    tmp_path,
    monkeypatch,
):
    bridge, coordinator = _scene_coordinator_with_owned_user_scene(
        tmp_path,
        monkeypatch,
        current_template_matches=True,
    )
    assert coordinator.prepare_pending_changes("save", force_save=True).success
    assert coordinator.commit_prepared_changes().success
    first_prepared = coordinator.prepared_changes
    first_transaction = first_prepared.publication_transaction

    second = coordinator.prepare_pending_changes("save", force_save=True)

    assert second.success is False
    assert "must be finalized or rolled back" in str(second.error)
    assert coordinator.prepared_changes is first_prepared
    assert first_transaction.status == "active"
    assert bridge._active_scene_publication is first_transaction
    assert coordinator.rollback_prepared_changes().success
    assert coordinator.prepared_changes is None
    assert bridge._active_scene_publication is None
