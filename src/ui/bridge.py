"""
bridge - panel-to-panel event bus.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from src.application.materials import MaterialPreviewSnapshot
from src.config.execution_target import ExecutionTarget, resolve_execution_target
from src.config.official_document_profiles import get_official_document_profile
from src.config.work_mode import WorkModeSpec, default_work_mode, get_work_mode
from src.domain.materials import (
    MaterialIssue,
    MaterialPackageRef,
    MaterialRunSelection,
)
from src.qt_api import QObject, Signal

if TYPE_CHECKING:
    from src.ui.workspace_preferences import WorkspacePreferenceStore


class TemplateLibraryEvents(QObject):
    """Events that belong to template-library projection changes."""

    import_completed = Signal(str, object)  # mode_id, TemplateImportBatch


@dataclass(frozen=True)
class NavigationIntent:
    """Cross-panel navigation target with optional in-panel context."""

    panel_id: str = ""
    panel_index: int = -1
    card_id: str = ""
    field_id: str = ""
    issue_id: str = ""
    return_panel_id: str = ""
    return_card_id: str = ""
    payload: dict[str, object] = field(default_factory=dict)


@dataclass
class _BridgeStateSnapshot:
    """Complete bridge state needed to roll back one failed publication."""

    work_mode: WorkModeSpec
    scene: object
    scene_id: str
    scene_path: str
    scene_source: str
    scene_source_type: str
    template: object
    template_id: str
    template_path: str
    template_source: str
    template_source_type: str
    template_mode_id: str
    protected_template_commits: dict[tuple[str, str], object]
    official_document_type_id: str
    official_document_type_source: str
    scene_dirty: bool
    template_dirty: bool
    suppress_next_scene_dirty_recheck: bool
    material_package_ref: MaterialPackageRef | None
    material_run_selection: MaterialRunSelection | None
    material_preview_snapshot: MaterialPreviewSnapshot | None
    material_issues: tuple[MaterialIssue, ...]
    suspended_material_states: list[dict[str, object]]
    execution_target: ExecutionTarget


def _clone_suspended_material_states(
    states: list[dict[str, object]] | tuple[dict[str, object], ...],
) -> list[dict[str, object]]:
    """Copy evidence containers without copying immutable MaterialPackage V1 values.

    ``MaterialRunSelection`` and ``MaterialPreviewSnapshot`` deliberately expose
    read-only mapping proxies.  They are frozen value objects and must be shared
    by reference; ``copy.deepcopy`` cannot (and should not) reconstruct them.
    """

    return [dict(item) for item in states]


@dataclass(slots=True, eq=False)
class ScenePublicationTransaction:
    """One reversible scene publication owned by a single :class:`PanelBridge`.

    The token deliberately keeps its snapshots private.  Callers may inspect
    ``status`` but must use ``PanelBridge`` to adopt, finalize, or roll back the
    provisional state.  That keeps scene identity, material scope, and the
    derived execution target inside one publication boundary.
    """

    _owner: object = field(repr=False)
    _baseline: _BridgeStateSnapshot = field(repr=False)
    _status: str = field(default="active", init=False)
    _adopted: bool = field(default=False, init=False, repr=False)
    _published_state: _BridgeStateSnapshot | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _provisional_state: _BridgeStateSnapshot | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _owned_fields: frozenset[str] = field(
        default_factory=frozenset,
        init=False,
        repr=False,
    )

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_active(self) -> bool:
        return self._status == "active"

    @property
    def is_published(self) -> bool:
        return self._status == "finalized"

    @property
    def is_rolled_back(self) -> bool:
        return self._status == "rolled_back"


# Only state that provisional Scene adoption can actually mutate belongs to the
# publication.  In particular, protected template commits are maintained by
# TemplatePanel listeners and must survive a later outer-transaction rollback.
_SCENE_PUBLICATION_OWNABLE_FIELDS = frozenset(
    {
        "scene",
        "scene_id",
        "scene_path",
        "scene_source",
        "scene_source_type",
        "template",
        "template_id",
        "template_path",
        "template_source",
        "template_source_type",
        "template_mode_id",
        "scene_dirty",
        "template_dirty",
        "suppress_next_scene_dirty_recheck",
        "material_package_ref",
        "material_run_selection",
        "material_preview_snapshot",
        "material_issues",
        "suspended_material_states",
        "execution_target",
    }
)


def navigation_intent_value(intent, key: str, default=None):
    """Read a field from a NavigationIntent-like object or dict."""
    if isinstance(intent, dict):
        return intent.get(key, default)
    return getattr(intent, key, default)


def _template_resource_identity(
    mode_id: str,
    config_id: str,
    path: str,
) -> tuple[str, str]:
    mode = str(mode_id or "").strip() or "custom"
    raw_path = str(path or "").strip()
    if raw_path:
        try:
            normalized_path = str(Path(raw_path).resolve(strict=False))
        except (OSError, RuntimeError):
            normalized_path = str(Path(raw_path).absolute())
        if os.name == "nt":
            normalized_path = normalized_path.casefold()
        return mode, f"path:{normalized_path}"
    return mode, f"id:{str(config_id or '').strip() or 'default'}"


class PanelBridge(QObject):
    """Shared event bus for cross-panel communication."""

    # Scene / template events
    scene_changed = Signal(object)                  # SceneWorkspace
    template_changed = Signal(object)               # TemplateConfig
    work_mode_changed = Signal(object)              # WorkModeSpec
    scene_dirty_changed = Signal(bool)
    template_dirty_changed = Signal(bool)
    material_package_ref_changed = Signal(object)   # MaterialPackageRef | None
    material_run_selection_changed = Signal(object)  # MaterialRunSelection | None
    material_preview_snapshot_changed = Signal(object)  # MaterialPreviewSnapshot | None
    material_issues_changed = Signal(object)        # tuple[MaterialIssue, ...]
    material_scope_suspended = Signal(object)       # incompatibility evidence
    execution_target_changed = Signal(object)       # ExecutionTarget
    official_document_type_changed = Signal(str)    # task-level document type id
    material_repair_target_requested = Signal(str, str)  # (target_type, target_key)
    material_profile_repair_target_requested = Signal(str, str, str, str)  # (profile_id, profile_name, target_type, target_key)
    material_profile_repair_candidate_requested = Signal(str, str, object)  # (profile_id, profile_name, candidate)
    assistant_provider_profiles_changed = Signal()
    preferences_page_requested = Signal(str)

    # Module configuration events
    config_value_changed = Signal(str, str, object) # (module, key, value)

    # Document events
    document_loaded = Signal(str)                   # file_path
    format_requested = Signal()
    format_completed = Signal(dict)                 # report_data

    # Navigation events
    navigate_to_panel = Signal(int)                 # panel_index
    navigate_to_intent = Signal(object)             # NavigationIntent | dict

    def __init__(
        self,
        parent=None,
        *,
        workspace_preference_store: "WorkspacePreferenceStore | None" = None,
    ):
        super().__init__(parent)
        self._workspace_preference_store = workspace_preference_store
        self.template_library_events = TemplateLibraryEvents(self)
        self._current_work_mode = default_work_mode()
        self._current_scene = None
        self._current_scene_id = ""
        self._current_scene_path = ""
        self._current_scene_source = ""
        self._current_scene_source_type = ""
        self._scene_change_reason = ""
        self._current_template = None
        self._current_template_id = ""
        self._current_template_path = ""
        self._current_template_source = ""
        self._current_template_source_type = ""
        self._current_template_mode_id = ""
        self._protected_template_commits: dict[tuple[str, str], object] = {}
        self._current_document_path = ""
        self._preferred_preferences_page = "about"
        self._current_official_document_type_id = "notice"
        self._current_official_document_type_source = "default"
        self._execution_target = resolve_execution_target(
            mode_id=self._current_work_mode.mode_id,
            scene=None,
            document_path="",
        )
        self._scene_dirty = False
        self._template_dirty = False
        self._suppress_next_scene_dirty_recheck = False
        self._material_package_ref: MaterialPackageRef | None = None
        self._material_run_selection: MaterialRunSelection | None = None
        self._material_preview_snapshot: MaterialPreviewSnapshot | None = None
        self._material_issues: tuple[MaterialIssue, ...] = ()
        self._suspended_material_states: list[dict[str, object]] = []
        self._material_repair_target: tuple[str, str] = ("", "")
        self._material_profile_repair_target: tuple[str, str, str, str] = ("", "", "", "")
        self._material_profile_repair_candidate: tuple[str, str, dict[str, object]] = ("", "", {})
        self._pending_work_mode_transition: _BridgeStateSnapshot | None = None
        self._scene_publication_owner = object()
        self._active_scene_publication: ScenePublicationTransaction | None = None

    def workspace_preference_store(self) -> "WorkspacePreferenceStore | None":
        return self._workspace_preference_store

    def preferred_preferences_page(self) -> str:
        return self._preferred_preferences_page

    def navigate_to_preferences(self, page_id: str = "about") -> None:
        normalized = str(page_id or "about").strip() or "about"
        self._preferred_preferences_page = normalized
        from src.ui.panel_specs import panel_index

        index = panel_index("preferences")
        self.navigate_to_panel.emit(index)
        self.preferences_page_requested.emit(normalized)

    def current_work_mode(self) -> WorkModeSpec:
        return self._current_work_mode

    def current_work_mode_id(self) -> str:
        return self._current_work_mode.mode_id

    def set_current_work_mode(
        self,
        mode: WorkModeSpec | str | None,
        *,
        emit_signal: bool = True,
    ) -> None:
        previous_mode_id = self._current_work_mode.mode_id
        next_mode = self._coerce_work_mode(mode)
        if next_mode.mode_id == previous_mode_id:
            return
        self._pending_work_mode_transition = self.capture_state_snapshot()
        self._current_work_mode = next_mode
        self._suspend_incompatible_material_state(
            mode_id=self._current_work_mode.mode_id,
            scene_id="",
            reason="work_mode_changed",
            previous_mode_id=previous_mode_id,
            previous_scene_id=self._current_scene_id,
            emit_signal=emit_signal,
        )
        self._refresh_execution_target(emit_signal=emit_signal)
        if emit_signal:
            self.work_mode_changed.emit(self._current_work_mode)

    def capture_state_snapshot(self) -> _BridgeStateSnapshot:
        """Freeze every bridge domain affected by scene or mode publication."""

        return _BridgeStateSnapshot(
            work_mode=self._current_work_mode,
            scene=copy.deepcopy(self._current_scene),
            scene_id=self._current_scene_id,
            scene_path=self._current_scene_path,
            scene_source=self._current_scene_source,
            scene_source_type=self._current_scene_source_type,
            template=copy.deepcopy(self._current_template),
            template_id=self._current_template_id,
            template_path=self._current_template_path,
            template_source=self._current_template_source,
            template_source_type=self._current_template_source_type,
            template_mode_id=self._current_template_mode_id,
            protected_template_commits=copy.deepcopy(self._protected_template_commits),
            official_document_type_id=self._current_official_document_type_id,
            official_document_type_source=self._current_official_document_type_source,
            scene_dirty=self._scene_dirty,
            template_dirty=self._template_dirty,
            suppress_next_scene_dirty_recheck=self._suppress_next_scene_dirty_recheck,
            material_package_ref=self._material_package_ref,
            material_run_selection=self._material_run_selection,
            material_preview_snapshot=self._material_preview_snapshot,
            material_issues=self._material_issues,
            suspended_material_states=_clone_suspended_material_states(
                self._suspended_material_states
            ),
            execution_target=copy.deepcopy(self._execution_target),
        )

    def restore_state_snapshot(
        self,
        snapshot: _BridgeStateSnapshot,
        *,
        emit_signal: bool = True,
    ) -> None:
        """Restore a snapshot before notifying listeners of the old state.

        Scene publication can suspend material scope and replace the derived
        execution target.  Restoring only the scene/template fields would
        therefore leave a split-brain bridge after a downstream UI failure.
        """

        previous_mode = self._current_work_mode
        previous_official_type = self._current_official_document_type_id
        self._current_work_mode = snapshot.work_mode
        self._current_scene = copy.deepcopy(snapshot.scene)
        self._current_scene_id = snapshot.scene_id
        self._current_scene_path = snapshot.scene_path
        self._current_scene_source = snapshot.scene_source
        self._current_scene_source_type = snapshot.scene_source_type
        self._current_template = copy.deepcopy(snapshot.template)
        self._current_template_id = snapshot.template_id
        self._current_template_path = snapshot.template_path
        self._current_template_source = snapshot.template_source
        self._current_template_source_type = snapshot.template_source_type
        self._current_template_mode_id = snapshot.template_mode_id
        self._protected_template_commits = copy.deepcopy(
            snapshot.protected_template_commits
        )
        self._current_official_document_type_id = snapshot.official_document_type_id
        self._current_official_document_type_source = (
            snapshot.official_document_type_source
        )
        self._scene_dirty = snapshot.scene_dirty
        self._template_dirty = snapshot.template_dirty
        self._suppress_next_scene_dirty_recheck = (
            snapshot.suppress_next_scene_dirty_recheck
        )
        self._material_package_ref = snapshot.material_package_ref
        self._material_run_selection = snapshot.material_run_selection
        self._material_preview_snapshot = snapshot.material_preview_snapshot
        self._material_issues = snapshot.material_issues
        self._suspended_material_states = _clone_suspended_material_states(
            snapshot.suspended_material_states
        )
        self._execution_target = copy.deepcopy(snapshot.execution_target)

        if not emit_signal:
            return
        if previous_mode != self._current_work_mode:
            self.work_mode_changed.emit(self._current_work_mode)
        if previous_official_type != self._current_official_document_type_id:
            self.official_document_type_changed.emit(
                self._current_official_document_type_id
            )
        self.scene_changed.emit(self._current_scene)
        self.template_changed.emit(self._current_template)
        self.scene_dirty_changed.emit(self._scene_dirty)
        self.template_dirty_changed.emit(self._template_dirty)
        self.material_package_ref_changed.emit(self._material_package_ref)
        self.material_run_selection_changed.emit(self._material_run_selection)
        self.material_preview_snapshot_changed.emit(self._material_preview_snapshot)
        self.material_issues_changed.emit(self._material_issues)
        self.execution_target_changed.emit(self._execution_target)

    def commit_pending_work_mode_transition(self) -> None:
        """Forget rollback state after the mode defaults were activated."""

        self._pending_work_mode_transition = None

    def rollback_pending_work_mode_transition(self, *, emit_signal: bool = True) -> bool:
        """Restore every bridge domain touched by a failed mode activation.

        All internal fields are restored before the first signal is emitted, so
        listeners never observe a second mixed old/new scope during rollback.
        """

        snapshot = self._pending_work_mode_transition
        if snapshot is None:
            return False
        self._pending_work_mode_transition = None

        self.restore_state_snapshot(snapshot, emit_signal=emit_signal)
        return True

    def _coerce_work_mode(self, mode: WorkModeSpec | str | None) -> WorkModeSpec:
        if isinstance(mode, WorkModeSpec):
            return get_work_mode(mode.mode_id) or mode
        resolved = get_work_mode(str(mode or ""))
        return resolved or default_work_mode()

    def current_scene(self):
        return self._current_scene

    def current_scene_id(self) -> str:
        return self._current_scene_id

    def current_scene_path(self) -> str:
        return self._current_scene_path

    def current_scene_source(self) -> str:
        return self._current_scene_source

    def current_scene_source_type(self) -> str:
        """Return the resource origin, independent from its loading channel."""
        return self._current_scene_source_type

    def begin_scene_publication(self) -> ScenePublicationTransaction:
        """Open a reversible scene publication without changing visible state.

        Only one scene publication may be active on a bridge.  The returned
        token freezes every domain that ``set_current_scene`` may affect so a
        failed multi-participant transaction can restore the old coherent
        state without sending signals for a state that was never published.
        """

        if self._active_scene_publication is not None:
            raise RuntimeError("a scene publication is already active")
        transaction = ScenePublicationTransaction(
            self._scene_publication_owner,
            self.capture_state_snapshot(),
        )
        self._active_scene_publication = transaction
        return transaction

    def adopt_scene_provisionally(
        self,
        transaction: ScenePublicationTransaction,
        scene,
        *,
        config_id: str = "",
        path: str = "",
        source: str = "",
        source_type: str | None = None,
        scene_dirty: bool | None = None,
    ) -> bool:
        """Adopt a scene silently inside an active publication.

        Material compatibility and execution-target derivation still run
        immediately, but their signals are deferred until
        :meth:`finalize_scene_publication`.  Passing ``scene_dirty`` folds the
        dirty-state transition into the same publication instead of leaking a
        provisional ``scene_dirty_changed`` event.
        """

        self._require_active_scene_publication(transaction)
        if transaction._adopted:
            raise RuntimeError("the scene publication already adopted a scene")
        before = self.capture_state_snapshot()
        try:
            self.set_current_scene(
                scene,
                config_id=config_id,
                path=path,
                source=source,
                source_type=source_type,
                emit_signal=False,
            )
            if scene_dirty is not None:
                self.set_scene_dirty(bool(scene_dirty), emit_signal=False)
        except Exception:
            self.restore_state_snapshot(transaction._baseline, emit_signal=False)
            transaction._status = "rolled_back"
            self._active_scene_publication = None
            raise
        transaction._adopted = True
        self._refresh_scene_publication_ownership(transaction)
        return not self._scene_publication_states_equal(
            before,
            self.capture_state_snapshot(),
        )

    def adopt_template_provisionally(
        self,
        transaction: ScenePublicationTransaction,
        template,
        *,
        config_id: str = "",
        path: str = "",
        source: str = "",
        source_type: str | None = None,
        template_dirty: bool | None = None,
        allow_dirty_same_identity_replace: bool = False,
    ) -> bool:
        """Adopt a bound template inside the same silent Scene publication.

        A saved Scene and its bound template form one observable context.  The
        template therefore cannot publish independently while the Scene token
        is still provisional.  Identity, value, and dirty-state changes are
        released together by :meth:`finalize_scene_publication`.
        """

        self._require_active_scene_publication(transaction)
        if not transaction._adopted:
            raise RuntimeError(
                "the scene publication must adopt its scene before its template"
            )
        before = self.capture_state_snapshot()
        try:
            self.set_current_template(
                template,
                config_id=config_id,
                path=path,
                source=source,
                source_type=source_type,
                emit_signal=False,
                allow_dirty_same_identity_replace=allow_dirty_same_identity_replace,
            )
            if template_dirty is not None:
                self.set_template_dirty(
                    bool(template_dirty),
                    emit_signal=False,
                )
        except Exception:
            self.restore_state_snapshot(transaction._baseline, emit_signal=False)
            transaction._status = "rolled_back"
            self._active_scene_publication = None
            raise
        self._refresh_scene_publication_ownership(transaction)
        return not self._scene_publication_states_equal(
            before,
            self.capture_state_snapshot(),
        )

    def finalize_scene_publication(
        self,
        transaction: ScenePublicationTransaction,
    ) -> bool:
        """Publish one coherent diff after all transaction participants commit.

        Internal state is already final before the first signal is sent.
        Repeated finalization is an idempotent no-op and therefore cannot emit
        duplicate events.
        """

        self._require_owned_scene_publication(transaction)
        if transaction._status == "finalized":
            return False
        self._require_active_scene_publication(transaction)
        if not transaction._adopted:
            raise RuntimeError("the scene publication has no provisional scene")
        published = self.capture_state_snapshot()
        provisional = transaction._provisional_state
        if provisional is None:
            raise RuntimeError("the scene publication is missing its provisional state")
        if not self._scene_publication_owned_states_equal(
            published,
            provisional,
            transaction._owned_fields,
        ):
            raise RuntimeError(
                "cannot finalize a stale scene publication after newer bridge changes"
            )
        publication_diff = self._merge_scene_publication_state(
            transaction._baseline,
            published,
            transaction._owned_fields,
        )
        suspension_evidence = self._new_material_suspension_evidence(
            transaction._baseline.suspended_material_states,
            publication_diff.suspended_material_states,
        )
        transaction._published_state = published
        transaction._status = "finalized"
        self._active_scene_publication = None
        return self._publish_scene_publication_diff(
            transaction._baseline,
            publication_diff,
            suspension_evidence=suspension_evidence,
        )

    def rollback_scene_publication(
        self,
        transaction: ScenePublicationTransaction,
    ) -> bool:
        """Restore the transaction baseline with publication-aware signaling.

        A provisional transaction has never been visible and is restored
        silently.  A finalized transaction has been visible, so rollback emits
        only the reverse scene/template/material/batch/target/dirty diff.
        Rollback is refused if newer bridge state has replaced the published
        state.
        """

        self._require_owned_scene_publication(transaction)
        if transaction._status == "rolled_back":
            return False
        if transaction._status == "active":
            if self._active_scene_publication is not transaction:
                raise RuntimeError("the scene publication is no longer active")
            current = self.capture_state_snapshot()
            provisional = transaction._provisional_state
            if provisional is not None and not self._scene_publication_owned_states_equal(
                current,
                provisional,
                transaction._owned_fields,
            ):
                raise RuntimeError(
                    "cannot roll back a stale provisional scene publication after "
                    "newer bridge changes"
                )
            restored = self._merge_scene_publication_state(
                current,
                transaction._baseline,
                transaction._owned_fields,
            )
            changed = not self._scene_publication_states_equal(current, restored)
            self.restore_state_snapshot(restored, emit_signal=False)
            transaction._status = "rolled_back"
            self._active_scene_publication = None
            return changed
        if transaction._status != "finalized":
            raise RuntimeError(
                f"unsupported scene publication state: {transaction._status}"
            )
        if self._active_scene_publication is not None:
            raise RuntimeError(
                "cannot roll back a published scene while another publication is active"
            )
        published = transaction._published_state
        if published is None:
            raise RuntimeError("the scene publication is missing its published snapshot")
        current = self.capture_state_snapshot()
        if not self._scene_publication_owned_states_equal(
            current,
            published,
            transaction._owned_fields,
        ):
            raise RuntimeError(
                "cannot roll back a stale scene publication after newer bridge changes"
            )
        rollback_state = self._merge_scene_publication_state(
            current,
            transaction._baseline,
            transaction._owned_fields,
        )
        self.restore_state_snapshot(rollback_state, emit_signal=False)
        restored = self.capture_state_snapshot()
        transaction._status = "rolled_back"
        return self._publish_scene_publication_diff(
            current,
            restored,
            suspension_evidence=(),
        )

    def _require_owned_scene_publication(
        self,
        transaction: ScenePublicationTransaction,
    ) -> None:
        if not isinstance(transaction, ScenePublicationTransaction):
            raise TypeError("transaction must be a ScenePublicationTransaction")
        if transaction._owner is not self._scene_publication_owner:
            raise ValueError("the scene publication belongs to another bridge")

    def _require_active_scene_publication(
        self,
        transaction: ScenePublicationTransaction,
    ) -> None:
        self._require_owned_scene_publication(transaction)
        if transaction._status != "active":
            raise RuntimeError("the scene publication is not active")
        if self._active_scene_publication is not transaction:
            raise RuntimeError("the scene publication is no longer active")

    def _refresh_scene_publication_ownership(
        self,
        transaction: ScenePublicationTransaction,
    ) -> None:
        provisional = self.capture_state_snapshot()
        transaction._provisional_state = provisional
        transaction._owned_fields = frozenset(
            field_name
            for field_name in _SCENE_PUBLICATION_OWNABLE_FIELDS
            if getattr(transaction._baseline, field_name)
            != getattr(provisional, field_name)
        )

    @staticmethod
    def _scene_publication_owned_states_equal(
        left: _BridgeStateSnapshot,
        right: _BridgeStateSnapshot,
        owned_fields: frozenset[str],
    ) -> bool:
        return all(
            getattr(left, field_name) == getattr(right, field_name)
            for field_name in owned_fields
        )

    @staticmethod
    def _merge_scene_publication_state(
        preserved: _BridgeStateSnapshot,
        owned_source: _BridgeStateSnapshot,
        owned_fields: frozenset[str],
    ) -> _BridgeStateSnapshot:
        """Replace transaction-owned fields while preserving external state."""

        # Snapshots already own deep copies of mutable scene/template state.
        # A shallow dataclass copy also preserves the identity of frozen V1
        # material values, whose mapping proxies intentionally reject deepcopy.
        merged = copy.copy(preserved)
        for field_name in owned_fields:
            value = getattr(owned_source, field_name)
            if field_name in {
                "material_package_ref",
                "material_run_selection",
                "material_preview_snapshot",
                "material_issues",
            }:
                cloned = value
            elif field_name == "suspended_material_states":
                cloned = _clone_suspended_material_states(value)
            else:
                cloned = copy.deepcopy(value)
            setattr(merged, field_name, cloned)
        return merged

    @staticmethod
    def _scene_publication_states_equal(
        left: _BridgeStateSnapshot,
        right: _BridgeStateSnapshot,
    ) -> bool:
        """Compare the complete rollback domain, including source identity."""

        return left == right

    @staticmethod
    def _scene_identity_or_value_changed(
        before: _BridgeStateSnapshot,
        after: _BridgeStateSnapshot,
    ) -> bool:
        return (
            before.scene != after.scene
            or before.scene_id != after.scene_id
            or before.scene_path != after.scene_path
            or before.scene_source != after.scene_source
            or before.scene_source_type != after.scene_source_type
        )

    @staticmethod
    def _template_identity_or_value_changed(
        before: _BridgeStateSnapshot,
        after: _BridgeStateSnapshot,
    ) -> bool:
        return (
            before.template != after.template
            or before.template_id != after.template_id
            or before.template_path != after.template_path
            or before.template_source != after.template_source
            or before.template_source_type != after.template_source_type
            or before.template_mode_id != after.template_mode_id
        )

    @staticmethod
    def _new_material_suspension_evidence(
        before: list[dict[str, object]],
        after: list[dict[str, object]],
    ) -> tuple[dict[str, object], ...]:
        """Return provably appended evidence, accounting for the 20-item cap."""

        if before == after:
            return ()
        if not before:
            additions = after
        elif len(after) >= len(before) and after[: len(before)] == before:
            additions = after[len(before) :]
        else:
            additions = []
            max_overlap = min(len(before), len(after))
            for overlap in range(max_overlap, 0, -1):
                if before[-overlap:] == after[:overlap]:
                    additions = after[overlap:]
                    break
        return tuple(dict(item) for item in additions)

    def _publish_scene_publication_diff(
        self,
        before: _BridgeStateSnapshot,
        after: _BridgeStateSnapshot,
        *,
        suspension_evidence: tuple[dict[str, object], ...],
    ) -> bool:
        """Emit a minimal diff for state that is already internally coherent."""

        emitted = False
        if before.material_package_ref != after.material_package_ref:
            self.material_package_ref_changed.emit(after.material_package_ref)
            emitted = True
        if before.material_run_selection != after.material_run_selection:
            self.material_run_selection_changed.emit(after.material_run_selection)
            emitted = True
        if before.material_preview_snapshot != after.material_preview_snapshot:
            self.material_preview_snapshot_changed.emit(
                after.material_preview_snapshot
            )
            emitted = True
        if before.material_issues != after.material_issues:
            self.material_issues_changed.emit(after.material_issues)
            emitted = True
        for evidence in suspension_evidence:
            self.material_scope_suspended.emit(
                {
                    key: copy.deepcopy(value)
                    for key, value in evidence.items()
                    if key not in {"package_ref", "selection", "preview", "issues"}
                }
            )
            emitted = True
        if before.execution_target != after.execution_target:
            self.execution_target_changed.emit(after.execution_target)
            emitted = True
        if self._scene_identity_or_value_changed(before, after):
            self.scene_changed.emit(after.scene)
            emitted = True
        if self._template_identity_or_value_changed(before, after):
            self.template_changed.emit(after.template)
            emitted = True
        if before.scene_dirty != after.scene_dirty:
            self.scene_dirty_changed.emit(after.scene_dirty)
            emitted = True
        if before.template_dirty != after.template_dirty:
            self.template_dirty_changed.emit(after.template_dirty)
            emitted = True
        return emitted

    def set_current_scene(
        self,
        scene,
        *,
        config_id: str = "",
        path: str = "",
        source: str = "",
        source_type: str | None = None,
        emit_signal: bool = True,
    ) -> None:
        next_id = str(config_id or "").strip()
        next_path = str(path or "").strip()
        next_source = str(source or "").strip()
        previous_identity = (
            self._current_scene_id,
            self._current_scene_path,
            self._current_scene_source,
        )
        next_identity = (next_id, next_path, next_source)
        next_source_type = (
            self._current_scene_source_type
            if source_type is None and next_identity == previous_identity
            else str(source_type or "").strip()
        )
        self._current_scene = scene
        self._current_scene_id = next_id
        self._current_scene_path = next_path
        self._current_scene_source = next_source
        self._current_scene_source_type = next_source_type
        self._suspend_incompatible_material_state(
            mode_id=self._current_work_mode.mode_id,
            scene_id=next_id,
            reason="scene_changed",
            previous_mode_id=self._current_work_mode.mode_id,
            previous_scene_id=previous_identity[0],
            emit_signal=emit_signal,
        )
        self._refresh_execution_target(emit_signal=emit_signal)
        if emit_signal:
            self.scene_changed.emit(scene)

    def update_current_scene_module_switches(
        self,
        changes: Mapping[str, bool],
    ) -> bool:
        """Copy-on-write the authoritative scene switches and emit once.

        Returns ``False`` for an absent scene or a semantic no-op.  The method
        deliberately preserves requested switches even when runtime dependency
        selection later auto-prunes a module.
        """
        scene = self._current_scene
        if scene is None:
            return False
        current = dict(getattr(scene, "module_switches", {}) or {})
        normalized = {
            str(module_name).strip(): bool(enabled)
            for module_name, enabled in changes.items()
            if str(module_name).strip()
        }
        changed = {
            module_name: enabled
            for module_name, enabled in normalized.items()
            if current.get(module_name) != enabled
        }
        if not changed:
            return False
        updated = copy.deepcopy(scene)
        updated_switches = dict(getattr(updated, "module_switches", {}) or {})
        updated_switches.update(changed)
        updated.module_switches = updated_switches
        self._current_scene = updated
        previous_reason = self._scene_change_reason
        self._scene_change_reason = "module_switches"
        try:
            self.mark_scene_dirty(recheck=False)
            self.scene_changed.emit(updated)
        finally:
            self._scene_change_reason = previous_reason
        return True

    def scene_change_reason(self) -> str:
        """Return the semantic reason during a synchronous scene notification."""

        return str(self._scene_change_reason or "")

    def is_scene_dirty(self) -> bool:
        return self._scene_dirty

    def set_scene_dirty(self, dirty: bool, *, emit_signal: bool = True) -> None:
        dirty = bool(dirty)
        if self._scene_dirty == dirty:
            return
        self._scene_dirty = dirty
        if not dirty:
            self._suppress_next_scene_dirty_recheck = False
        if emit_signal:
            self.scene_dirty_changed.emit(dirty)

    def mark_scene_dirty(
        self,
        *,
        recheck: bool = True,
        emit_signal: bool = True,
    ) -> None:
        if not recheck and not self._scene_dirty:
            self._suppress_next_scene_dirty_recheck = True
        self.set_scene_dirty(True, emit_signal=emit_signal)

    def clear_scene_dirty(self, *, emit_signal: bool = True) -> None:
        self.set_scene_dirty(False, emit_signal=emit_signal)

    def consume_scene_dirty_recheck_suppressed(self) -> bool:
        suppressed = bool(self._suppress_next_scene_dirty_recheck)
        self._suppress_next_scene_dirty_recheck = False
        return suppressed

    def current_template(self):
        return self._current_template

    def current_template_id(self) -> str:
        return self._current_template_id

    def current_template_path(self) -> str:
        return self._current_template_path

    def current_template_source(self) -> str:
        return self._current_template_source

    def current_template_source_type(self) -> str:
        """Return the resource origin, independent from its loading channel."""
        return self._current_template_source_type

    def current_template_mode_id(self) -> str:
        return self._current_template_mode_id

    def replace_protected_template_commits(
        self,
        records: list[tuple[str, str, str, object]],
    ) -> None:
        """Protect committed baselines for every retained dirty draft."""

        self._protected_template_commits = {
            _template_resource_identity(mode_id, config_id, path): copy.deepcopy(template)
            for mode_id, config_id, path, template in records
        }

    def current_document_path(self) -> str:
        return self._current_document_path

    def current_official_document_type_id(self) -> str:
        return self._current_official_document_type_id

    def current_official_document_type_source(self) -> str:
        return self._current_official_document_type_source

    def set_current_official_document_type_id(
        self,
        document_type_id: str,
        *,
        source: str = "user",
        emit_signal: bool = True,
    ) -> bool:
        """Set the authoritative task document type independently of the plan."""

        normalized = str(document_type_id or "").strip()
        if get_official_document_profile(normalized) is None:
            return False
        normalized_source = str(source or "user").strip() or "user"
        if normalized == self._current_official_document_type_id:
            self._current_official_document_type_source = normalized_source
            return False
        self._current_official_document_type_id = normalized
        self._current_official_document_type_source = normalized_source
        self._refresh_execution_target(emit_signal=emit_signal)
        if emit_signal:
            self.official_document_type_changed.emit(normalized)
        return True

    def current_execution_target(self) -> ExecutionTarget:
        return self._execution_target

    def set_current_document_path(self, path: str, *, emit_signal: bool = True) -> None:
        self._current_document_path = str(path or "").strip()
        self._refresh_execution_target(emit_signal=emit_signal)
        if emit_signal:
            self.document_loaded.emit(self._current_document_path)

    def _refresh_execution_target(self, *, emit_signal: bool) -> None:
        target = resolve_execution_target(
            mode_id=self._current_work_mode.mode_id,
            scene=self._current_scene,
            document_path=self._current_document_path,
            official_document_type_id=self._current_official_document_type_id,
        )
        changed = target != self._execution_target
        self._execution_target = target
        if emit_signal and changed:
            self.execution_target_changed.emit(target)

    def set_current_template(
        self,
        template,
        *,
        config_id: str = "",
        path: str = "",
        source: str = "",
        source_type: str | None = None,
        emit_signal: bool = True,
        allow_dirty_same_identity_replace: bool = False,
    ) -> bool:
        """Publish the committed template used by execution surfaces.

        A template editor may retain a dirty in-memory draft while the bridge
        continues to expose the last committed snapshot.  Ordinary navigation
        and quick-binding refreshes must not replace that committed snapshot
        for the same resource.  The authoring owner opts in only when it
        deliberately republishes its committed baseline (for example after a
        save or when returning to a cached draft).
        """
        next_id = str(config_id or "").strip()
        next_path = str(path or "").strip()
        next_source = str(source or "").strip()
        next_mode_id = str(self._current_work_mode.mode_id or "").strip()
        next_resource_identity = _template_resource_identity(
            next_mode_id,
            next_id,
            next_path,
        )
        previous_identity = (
            self._current_template_mode_id,
            self._current_template_id,
            self._current_template_path,
        )
        next_identity = (next_mode_id, next_id, next_path)
        protected_commit = self._protected_template_commits.get(next_resource_identity)
        if protected_commit is not None and not allow_dirty_same_identity_replace:
            if self._current_template is not None and next_identity == previous_identity:
                return False
            template = copy.deepcopy(protected_commit)
        elif (
            self._template_dirty
            and self._current_template is not None
            and next_identity == previous_identity
            and not allow_dirty_same_identity_replace
        ):
            return False
        next_source_type = (
            self._current_template_source_type
            if source_type is None
            and next_identity == previous_identity
            and next_source == self._current_template_source
            else str(source_type or "").strip()
        )
        published_template = copy.deepcopy(template)
        self._current_template = published_template
        self._current_template_mode_id = next_mode_id
        self._current_template_id = next_id
        self._current_template_path = next_path
        self._current_template_source = next_source
        self._current_template_source_type = next_source_type
        if emit_signal:
            self.template_changed.emit(published_template)
        return True

    def is_template_dirty(self) -> bool:
        return self._template_dirty

    def set_template_dirty(self, dirty: bool, *, emit_signal: bool = True) -> None:
        dirty = bool(dirty)
        if self._template_dirty == dirty:
            return
        self._template_dirty = dirty
        if emit_signal:
            self.template_dirty_changed.emit(dirty)

    def mark_template_dirty(self, *, emit_signal: bool = True) -> None:
        self.set_template_dirty(True, emit_signal=emit_signal)

    def clear_template_dirty(self, *, emit_signal: bool = True) -> None:
        self.set_template_dirty(False, emit_signal=emit_signal)

    def current_material_package_ref(self) -> MaterialPackageRef | None:
        return self._material_package_ref

    def set_current_material_package_ref(
        self,
        package_ref: MaterialPackageRef | None,
        *,
        emit_signal: bool = True,
    ) -> bool:
        if package_ref is not None and not isinstance(
            package_ref,
            MaterialPackageRef,
        ):
            raise TypeError("material_package_ref_type_invalid")
        if package_ref == self._material_package_ref:
            return False
        self._material_package_ref = package_ref
        if emit_signal:
            self.material_package_ref_changed.emit(package_ref)
        return True

    def current_material_run_selection(self) -> MaterialRunSelection | None:
        return self._material_run_selection

    def set_current_material_run_selection(
        self,
        selection: MaterialRunSelection | None,
        *,
        emit_signal: bool = True,
    ) -> bool:
        if selection is not None and not isinstance(
            selection,
            MaterialRunSelection,
        ):
            raise TypeError("material_run_selection_type_invalid")
        if selection == self._material_run_selection:
            return False
        self._material_run_selection = selection
        if selection is not None:
            self._material_package_ref = selection.package_ref
        if emit_signal:
            if selection is not None:
                self.material_package_ref_changed.emit(selection.package_ref)
            self.material_run_selection_changed.emit(selection)
        return True

    def current_material_preview_snapshot(
        self,
    ) -> MaterialPreviewSnapshot | None:
        return self._material_preview_snapshot

    def set_current_material_preview_snapshot(
        self,
        snapshot: MaterialPreviewSnapshot | None,
        *,
        emit_signal: bool = True,
    ) -> bool:
        if snapshot is not None and not isinstance(
            snapshot,
            MaterialPreviewSnapshot,
        ):
            raise TypeError("material_preview_snapshot_type_invalid")
        if snapshot == self._material_preview_snapshot:
            return False
        self._material_preview_snapshot = snapshot
        if emit_signal:
            self.material_preview_snapshot_changed.emit(snapshot)
        return True

    def current_material_issues(self) -> tuple[MaterialIssue, ...]:
        return self._material_issues

    def set_current_material_issues(
        self,
        issues: tuple[MaterialIssue, ...] | list[MaterialIssue],
        *,
        emit_signal: bool = True,
    ) -> bool:
        normalized = tuple(issues)
        if any(not isinstance(item, MaterialIssue) for item in normalized):
            raise TypeError("material_issues_type_invalid")
        if normalized == self._material_issues:
            return False
        self._material_issues = normalized
        if emit_signal:
            self.material_issues_changed.emit(normalized)
        return True

    def suspended_material_states(self) -> tuple[dict[str, object], ...]:
        """Return evidence for package state detached by a scope change."""

        return tuple(
            _clone_suspended_material_states(self._suspended_material_states)
        )

    def _suspend_incompatible_material_state(
        self,
        *,
        mode_id: str,
        scene_id: str,
        reason: str,
        previous_mode_id: str,
        previous_scene_id: str,
        emit_signal: bool,
    ) -> bool:
        if (
            self._material_package_ref is None
            and self._material_run_selection is None
            and self._material_preview_snapshot is None
            and not self._material_issues
        ):
            return False

        evidence = {
            "reason": str(reason or "scope_changed"),
            "previous_mode_id": str(previous_mode_id or ""),
            "previous_scene_id": str(previous_scene_id or ""),
            "next_mode_id": str(mode_id or ""),
            "next_scene_id": str(scene_id or ""),
            "package_ref": self._material_package_ref,
            "selection": self._material_run_selection,
            "preview": self._material_preview_snapshot,
            "issues": self._material_issues,
        }
        self._suspended_material_states.append(evidence)
        if len(self._suspended_material_states) > 20:
            self._suspended_material_states = self._suspended_material_states[-20:]
        self._material_package_ref = None
        self._material_run_selection = None
        self._material_preview_snapshot = None
        self._material_issues = ()
        if emit_signal:
            self.material_package_ref_changed.emit(None)
            self.material_run_selection_changed.emit(None)
            self.material_preview_snapshot_changed.emit(None)
            self.material_issues_changed.emit(())
            self.material_scope_suspended.emit(
                {
                    key: value
                    for key, value in evidence.items()
                    if key not in {"package_ref", "selection", "preview", "issues"}
                }
            )
        return True

    def current_material_repair_target(self) -> tuple[str, str]:
        return self._material_repair_target

    def consume_material_repair_target(self) -> tuple[str, str]:
        target = self._material_repair_target
        self._material_repair_target = ("", "")
        return target

    def current_material_profile_repair_target(self) -> tuple[str, str, str, str]:
        return self._material_profile_repair_target

    def consume_material_profile_repair_target(self) -> tuple[str, str, str, str]:
        target = self._material_profile_repair_target
        self._material_profile_repair_target = ("", "", "", "")
        return target

    def current_material_profile_repair_candidate(self) -> tuple[str, str, dict[str, object]]:
        return (
            self._material_profile_repair_candidate[0],
            self._material_profile_repair_candidate[1],
            dict(self._material_profile_repair_candidate[2]),
        )

    def consume_material_profile_repair_candidate(self) -> tuple[str, str, dict[str, object]]:
        profile_id, profile_name, candidate = self._material_profile_repair_candidate
        self._material_profile_repair_candidate = ("", "", {})
        return (profile_id, profile_name, dict(candidate))

    def request_material_repair_target(
        self,
        target_type: str,
        target_key: str,
        *,
        emit_signal: bool = True,
    ) -> None:
        normalized_type = str(target_type or "").strip()
        normalized_key = str(target_key or "").strip()
        self._material_repair_target = (normalized_type, normalized_key)
        if emit_signal:
            self.material_repair_target_requested.emit(normalized_type, normalized_key)

    def request_material_profile_repair_target(
        self,
        profile_id: str,
        profile_name: str,
        target_type: str,
        target_key: str,
        *,
        emit_signal: bool = True,
    ) -> None:
        normalized_profile_id = str(profile_id or "").strip()
        normalized_profile_name = str(profile_name or "").strip()
        normalized_type = str(target_type or "").strip()
        normalized_key = str(target_key or "").strip()
        self._material_profile_repair_target = (
            normalized_profile_id,
            normalized_profile_name,
            normalized_type,
            normalized_key,
        )
        if emit_signal:
            self.material_profile_repair_target_requested.emit(
                normalized_profile_id,
                normalized_profile_name,
                normalized_type,
                normalized_key,
            )

    def request_material_profile_repair_candidate(
        self,
        profile_id: str,
        profile_name: str,
        candidate: dict[str, object],
        *,
        emit_signal: bool = True,
    ) -> None:
        normalized_profile_id = str(profile_id or "").strip()
        normalized_profile_name = str(profile_name or "").strip()
        normalized_candidate = dict(candidate) if isinstance(candidate, dict) else {}
        self._material_profile_repair_candidate = (
            normalized_profile_id,
            normalized_profile_name,
            normalized_candidate,
        )
        if emit_signal:
            self.material_profile_repair_candidate_requested.emit(
                normalized_profile_id,
                normalized_profile_name,
                dict(normalized_candidate),
            )
