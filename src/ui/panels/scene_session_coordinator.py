"""Atomic scene activation and edit-session transactions for ``ScenePanel``.

The coordinator owns the mutable scene context, bridge publication order, and
rollback evidence.  The panel supplies only view-projection callbacks; it does
not keep a second copy of the transaction state.
"""

from __future__ import annotations

import copy
import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.config import library as config_library
from src.config.library import (
    get_scene_entry,
    get_template_entry,
    load_scene_from_library,
    load_template_from_library,
    save_scene_to_library,
)
from src.config.scene_identity import allocate_scene_id
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig


SCENE_PENDING_SAVE = "save"
SCENE_PENDING_DISCARD = "discard"
SCENE_PENDING_CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class SceneTemplateBinding:
    template: TemplateConfig | None
    template_id: str = ""
    path: str = ""
    source: str = ""
    source_type: str = ""
    publish: bool = False


@dataclass(frozen=True, slots=True)
class SceneProjectionCallbacks:
    apply_scene: Callable[[SceneWorkspace, TemplateConfig | None], None]
    refresh_scene_selector: Callable[[], None]
    selected_card_id: Callable[[], str]
    restore_selected_card: Callable[[str], None]
    refresh_navigation_cards: Callable[[], None]


@dataclass(slots=True)
class SceneSessionState:
    scene: SceneWorkspace | None = None
    persisted_scene: SceneWorkspace | None = None
    scene_path: str = ""
    scene_source: str = ""
    scene_source_type: str = ""
    template: TemplateConfig | None = None
    activating_scene_id: str = ""
    restoring_activation: bool = False
    ignore_own_scene_changed: bool = False
    authoritative_user_revision: str = ""
    authoritative_user_conflict: bool = False
    external_recovery_required: bool = False


@dataclass(frozen=True, slots=True)
class SceneActivationSnapshot:
    bridge_state: object
    persisted_scene: SceneWorkspace | None
    scene_id: str
    scene_path: str
    scene_source: str
    scene_source_type: str
    authoritative_user_revision: str
    authoritative_user_conflict: bool
    selected_card_id: str


@dataclass(frozen=True, slots=True)
class SceneTransactionResult:
    success: bool
    error: Exception | None = None
    rollback_error: Exception | None = None


class SceneSaveRevisionChanged(RuntimeError):
    """A user-plan target changed after preparation or after publication."""


class SceneSaveTargetRequired(ValueError):
    """A non-user Scene needs an explicit user-owned target before saving."""


@dataclass(frozen=True, slots=True)
class SceneSaveTarget:
    """Frozen ownership transition for one Scene save transaction."""

    source_scene_id: str
    source_path: str
    source_type: str
    mode_id: str
    operation: str
    target_scene_id: str
    target_name: str
    target_path: Path

    @property
    def expected_absent(self) -> bool:
        return self.operation == "fork_to_user"


@dataclass(frozen=True, slots=True)
class SceneFileSnapshot:
    path: Path
    payload: bytes | None

    @property
    def revision(self) -> str:
        if self.payload is None:
            return "missing"
        return f"sha256:{hashlib.sha256(self.payload).hexdigest()}"


@dataclass(slots=True)
class PreparedSceneChanges:
    action: str
    scene: SceneWorkspace
    scene_id: str
    mode_id: str
    target_path: Path
    target_snapshot: SceneFileSnapshot
    directory_snapshots: dict[str, SceneFileSnapshot]
    save_callable: Callable[..., object]
    activation_snapshot: SceneActivationSnapshot
    save_target: SceneSaveTarget | None = None
    publication_transaction: object | None = None
    publication_attempted: bool = False
    publication_finalized: bool = False
    recovery_required: bool = False
    committed: bool = False
    committed_path: Path | None = None
    committed_before: SceneFileSnapshot | None = None
    committed_after: SceneFileSnapshot | None = None
    committed_receipt_revision: str = ""
    committed_directory_after: dict[str, SceneFileSnapshot] | None = None
    recovery_path: Path | None = None
    unowned_directory_effects: bool = False
    file_rollback_completed: bool = False
    file_mutation_receipt: object | None = None
    external_revision_conflict: bool = False


class SceneSessionCoordinator:
    """Own one scene panel's context and reversible bridge transactions."""

    def __init__(self, bridge, projection: SceneProjectionCallbacks):
        self._bridge = bridge
        self._projection = projection
        self._state = SceneSessionState(
            scene=bridge.current_scene(),
            persisted_scene=(
                copy.deepcopy(bridge.current_scene())
                if bridge.current_scene() is not None
                and not bool(bridge.is_scene_dirty())
                else None
            ),
            scene_path=str(bridge.current_scene_path() or ""),
            scene_source=str(bridge.current_scene_source() or ""),
            scene_source_type=str(bridge.current_scene_source_type() or ""),
            template=bridge.current_template(),
        )
        self._prepared_changes: PreparedSceneChanges | None = None
        self._record_authoritative_user_revision()

    @property
    def state(self) -> SceneSessionState:
        return self._state

    @property
    def prepared_changes(self) -> PreparedSceneChanges | None:
        return self._prepared_changes

    def current_work_mode_id(self) -> str:
        getter = getattr(self._bridge, "current_work_mode_id", None)
        return str(getter() or "").strip() if callable(getter) else "custom"

    def current_scene_id(self) -> str:
        activating_id = str(self._state.activating_scene_id or "").strip()
        if activating_id:
            return activating_id
        return str(
            self._bridge.current_scene_id()
            or getattr(self._state.scene, "scene_id", "")
            or ""
        ).strip()

    def capture_persisted_scene(
        self,
        scene: SceneWorkspace | None = None,
    ) -> None:
        """Freeze the canonical scene used for whole-draft dirty comparison."""

        target = self._state.scene if scene is None else scene
        self._state.persisted_scene = copy.deepcopy(target)

    def is_dirty_against_persisted(
        self,
        scene: SceneWorkspace | None = None,
    ) -> bool:
        """Return whether the active draft differs from its persisted baseline."""

        target = self._state.scene if scene is None else scene
        if target is None:
            return False
        baseline = self._state.persisted_scene
        if baseline is None:
            return True
        return target != baseline

    def authoritative_user_conflict(self) -> bool:
        return bool(
            self._state.authoritative_user_conflict or self.recovery_required()
        )

    def recovery_required(self) -> bool:
        prepared = self._prepared_changes
        return bool(
            self._state.external_recovery_required
            or (prepared is not None and prepared.recovery_required)
        )

    def set_external_recovery_required(self, required: bool) -> None:
        self._state.external_recovery_required = bool(required)
        if required:
            self._state.authoritative_user_conflict = True

    def authoritative_user_revision(self) -> str:
        return str(self._state.authoritative_user_revision or "").strip()

    def refresh_authoritative_user_conflict(self) -> bool:
        """Compare the active user Scene with the exact bytes originally adopted."""

        recovery_conflict = self.recovery_required()
        if not self._has_authoritative_user_context():
            self._state.authoritative_user_revision = ""
            self._state.authoritative_user_conflict = recovery_conflict
            return recovery_conflict
        try:
            current = self._capture_scene_file(Path(self._state.scene_path))
        except (OSError, ValueError):
            self._state.authoritative_user_conflict = True
            return True
        expected = self.authoritative_user_revision()
        conflict = (
            recovery_conflict
            or not expected
            or current.payload is None
            or current.revision != expected
        )
        self._state.authoritative_user_conflict = conflict
        return conflict

    def capture_verified_authoritative_user_file(
        self,
        path: str | Path,
    ) -> SceneFileSnapshot:
        """Return current bytes only when they still match the adopted revision."""

        if self.recovery_required():
            self._state.authoritative_user_conflict = True
            raise SceneSaveRevisionChanged(
                "a Scene recovery transaction is unresolved; file mutation refused"
            )
        target = Path(path)
        expected_path = str(self._state.scene_path or "").strip()
        if (
            not self._has_authoritative_user_context()
            or not expected_path
            or self._path_key(target) != self._path_key(Path(expected_path))
            or not config_library.is_scene_user_library_path(target)
        ):
            self._state.authoritative_user_conflict = True
            raise SceneSaveRevisionChanged(
                f"active Scene is not the authoritative user target: {target}"
            )
        current = self._capture_scene_file(target)
        expected = self.authoritative_user_revision()
        if (
            not expected
            or current.payload is None
            or current.revision != expected
        ):
            self._state.authoritative_user_conflict = True
            raise SceneSaveRevisionChanged(
                f"active user Scene changed before the operation: {target}"
            )
        self._state.authoritative_user_conflict = False
        return current

    def capture_user_reload_candidate(
        self,
        path: str | Path,
    ) -> SceneFileSnapshot:
        """Capture a changed active user file without adopting it as authoritative."""

        if self.recovery_required():
            self._state.authoritative_user_conflict = True
            raise SceneSaveRevisionChanged(
                "a Scene recovery transaction is unresolved; reload refused"
            )
        target = Path(path)
        expected_path = str(self._state.scene_path or "").strip()
        if (
            not self._has_authoritative_user_context()
            or not expected_path
            or self._path_key(target) != self._path_key(Path(expected_path))
            or not config_library.is_scene_user_library_path(target)
        ):
            self._state.authoritative_user_conflict = True
            raise SceneSaveRevisionChanged(
                f"active Scene is not an owned user reload target: {target}"
            )
        current = self._capture_scene_file(target)
        if current.payload is None:
            self._state.authoritative_user_conflict = True
            raise SceneSaveRevisionChanged(
                f"active user Scene disappeared before reload: {target}"
            )
        return current

    def replace_local_context(
        self,
        scene: SceneWorkspace | None,
        *,
        path: str,
        source: str,
        source_type: str,
        template: TemplateConfig | None = None,
        authoritative_revision: str = "",
    ) -> None:
        self._state.scene = scene
        self._state.scene_path = str(path or "").strip()
        self._state.scene_source = str(source or "").strip()
        self._state.scene_source_type = str(source_type or "").strip()
        self._state.template = template
        frozen_revision = str(authoritative_revision or "").strip()
        if frozen_revision and self._has_authoritative_user_context():
            self._state.authoritative_user_revision = frozen_revision
            self._state.authoritative_user_conflict = False
        else:
            self._record_authoritative_user_revision()

    def accept_bridge_scene(self, scene: SceneWorkspace) -> None:
        self.replace_local_context(
            scene,
            path=str(self._bridge.current_scene_path() or ""),
            source=str(self._bridge.current_scene_source() or ""),
            source_type=str(self._bridge.current_scene_source_type() or ""),
            template=self._state.template,
        )

    def accept_bridge_runtime_scene_update(self, scene: SceneWorkspace) -> None:
        """Adopt an in-memory value change without re-reading library state."""

        self._state.scene = scene

    def _has_authoritative_user_context(self) -> bool:
        return (
            str(self._state.scene_source_type or "").strip() == "user"
            and bool(str(self._state.scene_path or "").strip())
        )

    def _record_authoritative_user_revision(self) -> None:
        self._state.authoritative_user_revision = ""
        self._state.authoritative_user_conflict = False
        if not self._has_authoritative_user_context():
            return
        try:
            snapshot = self._capture_scene_file(Path(self._state.scene_path))
        except (OSError, ValueError):
            self._state.authoritative_user_conflict = True
            return
        self._state.authoritative_user_revision = snapshot.revision
        self._state.authoritative_user_conflict = snapshot.payload is None

    def _refresh_recovery_conflict(
        self,
        snapshot: SceneActivationSnapshot,
    ) -> None:
        """Refresh disk conflict without blessing failed publication bytes.

        A publication rollback may intentionally retain unrelated Bridge listener
        commits.  When its Scene identity still matches the activation baseline,
        however, that baseline revision remains the authority until file rollback
        succeeds.  Reusing it prevents failed/new disk bytes from being adopted as
        a clean baseline merely while synchronizing the local projection.
        """

        current_id = str(self._bridge.current_scene_id() or "").strip()
        current_path = str(self._bridge.current_scene_path() or "").strip()
        current_source_type = str(
            self._bridge.current_scene_source_type() or ""
        ).strip()
        snapshot_path = str(snapshot.scene_path or "").strip()
        same_path = (
            (not current_path and not snapshot_path)
            or (
                bool(current_path)
                and bool(snapshot_path)
                and self._path_key(Path(current_path))
                == self._path_key(Path(snapshot_path))
            )
        )
        if (
            current_id == snapshot.scene_id
            and current_source_type == snapshot.scene_source_type
            and same_path
        ):
            self._state.authoritative_user_revision = (
                snapshot.authoritative_user_revision
            )
            self._state.authoritative_user_conflict = (
                snapshot.authoritative_user_conflict
            )
        self.refresh_authoritative_user_conflict()

    def accept_bridge_template(self, template: TemplateConfig | None) -> None:
        self._state.template = template

    def resolve_template_binding(
        self,
        scene: SceneWorkspace,
    ) -> SceneTemplateBinding:
        template_id = str(
            getattr(scene, "template_id", "")
            or ""
        ).strip()
        if not template_id:
            return SceneTemplateBinding(template=None)
        if (
            self._bridge.current_template() is not None
            and self._bridge.current_template_id() == template_id
            and self._bridge.current_template_mode_id() == self.current_work_mode_id()
        ):
            return SceneTemplateBinding(template=self._bridge.current_template())
        entry = get_template_entry(
            template_id,
            mode_id=self.current_work_mode_id(),
        )
        template = load_template_from_library(
            template_id,
            mode_id=self.current_work_mode_id(),
        )
        return SceneTemplateBinding(
            template=template,
            template_id=template_id,
            path=str(entry.path) if entry is not None else "",
            source="library" if entry is not None else "builtin",
            source_type=entry.source_type if entry is not None else "builtin",
            publish=True,
        )

    def publish_bound_template(
        self,
        scene: SceneWorkspace,
        *,
        publication_transaction: object | None = None,
    ) -> SceneTemplateBinding:
        binding = self.resolve_template_binding(scene)
        self._state.template = binding.template
        if binding.publish:
            adopt_provisionally = getattr(
                self._bridge,
                "adopt_template_provisionally",
                None,
            )
            if publication_transaction is not None:
                if not callable(adopt_provisionally):
                    raise RuntimeError(
                        "Bridge cannot adopt the bound template provisionally"
                    )
                adopt_provisionally(
                    publication_transaction,
                    binding.template,
                    config_id=binding.template_id,
                    path=binding.path,
                    source=binding.source,
                    source_type=binding.source_type,
                )
            else:
                self._bridge.set_current_template(
                    binding.template,
                    config_id=binding.template_id,
                    path=binding.path,
                    source=binding.source,
                    source_type=binding.source_type,
                )
        return binding

    def scene_source_type_for_context(
        self,
        *,
        scene_id: str,
        path: str,
        source: str,
    ) -> str:
        channel = str(source or "").strip()
        if channel in {"builtin", "runtime"}:
            return channel
        normalized_path = str(path or "").strip()
        if normalized_path:
            return config_library.scene_source_type_for_path(normalized_path)
        if channel == "file":
            return "external"
        if channel == "library":
            entry = get_scene_entry(
                scene_id,
                mode_id=self.current_work_mode_id(),
            )
            if entry is not None:
                return str(entry.source_type or "").strip()
        return ""

    def activate(
        self,
        scene: SceneWorkspace,
        *,
        scene_id: str,
        path: str = "",
        source: str = "library",
        source_type: str | None = None,
        dirty: bool = False,
        expected_user_revision: str = "",
    ) -> SceneTransactionResult:
        snapshot = self._capture_activation_snapshot()
        next_path = str(path or "").strip()
        next_source = str(source or "").strip()
        next_source_type = (
            self.scene_source_type_for_context(
                scene_id=scene_id,
                path=next_path,
                source=next_source,
            )
            if source_type is None
            else str(source_type or "").strip()
        )
        expected_reload_revision = str(expected_user_revision or "").strip()
        self._state.activating_scene_id = str(scene_id or "").strip()
        try:
            binding = self.resolve_template_binding(scene)
            if expected_reload_revision:
                if next_source_type != "user" or not next_path:
                    raise SceneSaveRevisionChanged(
                        "a verified user reload requires an owned user target"
                    )
                reload_snapshot = self.capture_user_reload_candidate(next_path)
                if reload_snapshot.revision != expected_reload_revision:
                    raise SceneSaveRevisionChanged(
                        "active user Scene changed again before reload activation"
                    )
            self.replace_local_context(
                scene,
                path=next_path,
                source=next_source,
                source_type=next_source_type,
                template=binding.template,
            )
            if expected_reload_revision and (
                self.authoritative_user_revision() != expected_reload_revision
                or self.authoritative_user_conflict()
            ):
                raise SceneSaveRevisionChanged(
                    "active user Scene changed while adopting the external reload"
                )
            self._projection.refresh_scene_selector()
            self._projection.apply_scene(scene, binding.template)

            self._state.ignore_own_scene_changed = True
            self._bridge.set_current_scene(
                scene,
                config_id=scene_id,
                path=next_path,
                source=next_source,
                source_type=next_source_type,
                emit_signal=True,
            )
            self._state.ignore_own_scene_changed = False
            if binding.publish:
                self._bridge.set_current_template(
                    binding.template,
                    config_id=binding.template_id,
                    path=binding.path,
                    source=binding.source,
                    source_type=binding.source_type,
                )
            self._bridge.set_scene_dirty(bool(dirty))
            self._projection.refresh_navigation_cards()
            if expected_reload_revision and self.refresh_authoritative_user_conflict():
                raise SceneSaveRevisionChanged(
                    "active user Scene changed before reload activation completed"
                )
            if not dirty:
                self.capture_persisted_scene(scene)
        except Exception as exc:
            self._state.ignore_own_scene_changed = False
            try:
                self._restore_activation_snapshot(snapshot)
            except Exception as rollback_exc:
                return SceneTransactionResult(
                    success=False,
                    error=exc,
                    rollback_error=rollback_exc,
                )
            return SceneTransactionResult(success=False, error=exc)
        finally:
            self._state.ignore_own_scene_changed = False
            self._state.activating_scene_id = ""
        return SceneTransactionResult(success=True)

    def requires_fork_save(self, *, mode_id: str = "") -> bool:
        """Return whether the active Scene lacks an authoritative user owner."""

        scene = self._bridge.current_scene() or self._state.scene
        if scene is None:
            return True
        owning_mode_id = str(mode_id or "").strip() or self.current_work_mode_id()
        return not self._active_scene_is_owned_user(scene, mode_id=owning_mode_id)

    def build_save_target(
        self,
        *,
        mode_id: str = "",
        fork_name: str | None = None,
        force_fork: bool = False,
        scene: SceneWorkspace | None = None,
    ) -> SceneSaveTarget:
        """Resolve and freeze update-vs-fork before any publication occurs."""

        active_scene = scene or self._bridge.current_scene() or self._state.scene
        if active_scene is None:
            raise ValueError("cannot save an empty Scene session")
        owning_mode_id = str(mode_id or "").strip() or self.current_work_mode_id()
        source_scene_id = str(
            self._bridge.current_scene_id()
            or getattr(self._state.scene, "scene_id", "")
            or ""
        ).strip()
        payload_scene_id = str(
            getattr(self._bridge.current_scene() or self._state.scene, "scene_id", "")
            or ""
        ).strip()
        if not source_scene_id or payload_scene_id != source_scene_id:
            raise ValueError(
                "scene save source identity mismatch: "
                f"bridge={source_scene_id or '<empty>'}; "
                f"payload={payload_scene_id or '<empty>'}"
            )
        payload_mode_id = str(
            getattr(self._bridge.current_scene() or self._state.scene, "mode_id", "")
            or ""
        ).strip()
        if payload_mode_id and payload_mode_id != owning_mode_id:
            raise ValueError(
                "scene save source mode mismatch: "
                f"active={owning_mode_id}; payload={payload_mode_id}"
            )
        source_path = str(
            self._bridge.current_scene_path() or self._state.scene_path or ""
        ).strip()
        source_type = str(
            self._bridge.current_scene_source_type()
            or self._state.scene_source_type
            or ""
        ).strip()
        owned_user = self._active_scene_is_owned_user(
            self._bridge.current_scene() or self._state.scene,
            mode_id=owning_mode_id,
        )
        if owned_user and not force_fork:
            target_scene_id = source_scene_id
            target_name = str(getattr(active_scene, "name", "") or "").strip()
            operation = "update_user"
            if not source_path:
                raise ValueError("owned user Scene has no authoritative path")
            target_path = config_library.validate_scene_library_write_path(
                source_path
            )
            authoritative_entry = get_scene_entry(
                target_scene_id,
                mode_id=owning_mode_id,
            )
            if (
                authoritative_entry is None
                or str(authoritative_entry.source_type or "").strip() != "user"
                or self._path_key(Path(authoritative_entry.path))
                != self._path_key(target_path)
            ):
                raise ValueError(
                    "owned user Scene path is not the authoritative library entry"
                )
        else:
            target_name = str(fork_name or "").strip()
            if not target_name:
                raise SceneSaveTargetRequired(
                    "non-user Scene must be saved under a new user-owned identity"
                )
            target_scene_id = allocate_scene_id(
                name=target_name,
                mode_id=owning_mode_id,
            )
            operation = "fork_to_user"
            target_path = config_library.scene_user_target_path(
                target_scene_id,
                mode_id=owning_mode_id,
            )
        return SceneSaveTarget(
            source_scene_id=source_scene_id,
            source_path=source_path,
            source_type=source_type,
            mode_id=owning_mode_id,
            operation=operation,
            target_scene_id=target_scene_id,
            target_name=target_name,
            target_path=target_path,
        )

    def _active_scene_is_owned_user(
        self,
        scene: SceneWorkspace | None,
        *,
        mode_id: str,
    ) -> bool:
        if scene is None:
            return False
        if self.refresh_authoritative_user_conflict():
            return False
        scene_id = str(self._bridge.current_scene_id() or "").strip()
        payload_scene_id = str(getattr(scene, "scene_id", "") or "").strip()
        source_type = str(
            self._bridge.current_scene_source_type()
            or self._state.scene_source_type
            or ""
        ).strip()
        current_path = str(
            self._bridge.current_scene_path() or self._state.scene_path or ""
        ).strip()
        if (
            not scene_id
            or payload_scene_id != scene_id
            or source_type != "user"
            or not current_path
        ):
            return False
        entry = get_scene_entry(scene_id, mode_id=mode_id)
        if (
            entry is None
            or not bool(getattr(entry, "is_available", True))
            or str(entry.source_type or "").strip() != "user"
        ):
            return False
        return (
            self._path_key(entry.path) == self._path_key(Path(current_path))
            and config_library.is_scene_user_library_path(entry.path)
        )

    def prepare_pending_changes(
        self,
        action: str,
        *,
        save_callable=None,
        mode_id: str = "",
        fork_name: str | None = None,
        force_fork: bool = False,
        force_save: bool = False,
        scene_override: SceneWorkspace | None = None,
    ) -> SceneTransactionResult:
        if self._state.external_recovery_required:
            return SceneTransactionResult(
                success=False,
                error=RuntimeError(
                    "an external Scene recovery must be resolved before preparing changes"
                ),
            )
        self.cancel_prepared_changes()
        if self._prepared_changes is not None:
            return SceneTransactionResult(
                success=False,
                error=RuntimeError(
                    "a committed Scene transaction must be finalized or rolled back "
                    "before preparing another transaction"
                ),
            )
        if not self._bridge.is_scene_dirty() and not force_save:
            return SceneTransactionResult(success=True)
        normalized_action = str(action or "").strip()
        if normalized_action not in {SCENE_PENDING_SAVE, SCENE_PENDING_DISCARD}:
            return SceneTransactionResult(success=False)
        scene = self._bridge.current_scene() or self._state.scene
        if scene is None:
            return SceneTransactionResult(success=False)
        owning_mode_id = str(mode_id or "").strip() or self.current_work_mode_id()
        scene_id = str(self._bridge.current_scene_id() or "").strip()
        target_path = Path()
        directory_snapshots: dict[str, SceneFileSnapshot] = {}
        target_snapshot = SceneFileSnapshot(path=target_path, payload=None)
        save_target: SceneSaveTarget | None = None
        prepared_scene = copy.deepcopy(scene_override or scene)
        if normalized_action == SCENE_PENDING_SAVE:
            try:
                save_target = self.build_save_target(
                    mode_id=owning_mode_id,
                    fork_name=fork_name,
                    force_fork=force_fork,
                    scene=prepared_scene,
                )
                scene_id = save_target.target_scene_id
                target_path = save_target.target_path
                prepared_scene.scene_id = save_target.target_scene_id
                prepared_scene.name = save_target.target_name
                prepared_scene.mode_id = owning_mode_id
                directory_snapshots = self._capture_scene_directory(target_path.parent)
                target_snapshot = directory_snapshots.get(
                    self._path_key(target_path),
                    SceneFileSnapshot(path=target_path, payload=None),
                )
                if save_target.operation == "update_user":
                    expected_revision = self.authoritative_user_revision()
                    if (
                        self._state.authoritative_user_conflict
                        or not expected_revision
                        or target_snapshot.revision != expected_revision
                    ):
                        self._state.authoritative_user_conflict = True
                        raise SceneSaveRevisionChanged(
                            "active user Scene changed while preparing the save"
                        )
            except (OSError, ValueError, SceneSaveRevisionChanged) as exc:
                return SceneTransactionResult(success=False, error=exc)
        self._prepared_changes = PreparedSceneChanges(
            action=normalized_action,
            scene=prepared_scene,
            scene_id=scene_id,
            mode_id=owning_mode_id,
            target_path=target_path,
            target_snapshot=target_snapshot,
            directory_snapshots=directory_snapshots,
            save_callable=save_callable or save_scene_to_library,
            activation_snapshot=self._capture_activation_snapshot(),
            save_target=save_target,
        )
        return SceneTransactionResult(success=True)

    def commit_prepared_changes(self) -> SceneTransactionResult:
        prepared = self._prepared_changes
        if prepared is None:
            return SceneTransactionResult(success=not self._bridge.is_scene_dirty())
        if prepared.recovery_required:
            return SceneTransactionResult(
                success=False,
                error=RuntimeError(
                    "an unresolved Scene recovery must be rolled back before commit"
                ),
            )
        if prepared.committed:
            return SceneTransactionResult(success=True)
        if prepared.publication_attempted:
            return SceneTransactionResult(
                success=False,
                error=RuntimeError(
                    "a failed Scene publication must be cancelled and prepared again"
                ),
            )
        if prepared.action == SCENE_PENDING_DISCARD:
            self._bridge.clear_scene_dirty()
            prepared.committed = True
            return SceneTransactionResult(success=True)
        if prepared.action != SCENE_PENDING_SAVE:
            return SceneTransactionResult(success=False)
        save_target = prepared.save_target
        if save_target is None:
            return SceneTransactionResult(
                success=False,
                error=ValueError("prepared Scene save is missing its frozen target"),
            )
        try:
            self._assert_prepared_revision(prepared)
        except (OSError, ValueError, SceneSaveRevisionChanged) as exc:
            return SceneTransactionResult(success=False, error=exc)
        prepared.publication_attempted = True
        try:
            scene = copy.deepcopy(prepared.scene)
            save_kwargs = {
                "scene_id": save_target.target_scene_id,
                "mode_id": save_target.mode_id,
            }
            if save_target.expected_absent:
                save_kwargs["expected_absent"] = True
            else:
                save_kwargs["expected_revision"] = prepared.target_snapshot.revision
            entry = prepared.save_callable(scene, **save_kwargs)
            self._record_commit_candidate(prepared, entry)
            self._assert_commit_directory_effects(prepared)
            committed_path, committed_scene_id = self._validate_commit_receipt(
                prepared,
                entry,
            )
            if prepared.committed_after.payload is None:
                raise OSError(f"scene save receipt target is missing: {committed_path}")
            canonical_scene = self._load_canonical_committed_scene(
                prepared,
                scene_id=committed_scene_id,
                committed_path=committed_path,
                expected_revision=prepared.committed_receipt_revision,
            )
            begin_publication = getattr(
                self._bridge,
                "begin_scene_publication",
                None,
            )
            if callable(begin_publication):
                prepared.publication_transaction = begin_publication()
            self._adopt_committed_scene(
                canonical_scene,
                scene_id=committed_scene_id,
                path=str(committed_path),
                source_type="user",
                publication_transaction=prepared.publication_transaction,
                authoritative_revision=prepared.committed_receipt_revision,
            )
            if (
                config_library.scene_file_revision(committed_path)
                != prepared.committed_receipt_revision
            ):
                self._state.authoritative_user_conflict = True
                raise SceneSaveRevisionChanged(
                    "committed Scene changed while it was being adopted"
                )
        except Exception as exc:
            recovery_path = getattr(exc, "recovery_path", None)
            if recovery_path is not None:
                prepared.recovery_path = Path(recovery_path)
            mutation_receipt = getattr(exc, "mutation_receipt", None)
            if isinstance(
                mutation_receipt,
                config_library.SceneFileMutationReceipt,
            ):
                prepared.file_mutation_receipt = mutation_receipt
            prepared.recovery_required = bool(
                getattr(exc, "recovery_required", False)
                or prepared.recovery_path is not None
            )
            if prepared.committed_directory_after is None:
                try:
                    prepared.committed_directory_after = self._capture_scene_directory(
                        prepared.target_path.parent
                    )
                except Exception:
                    prepared.recovery_required = True
            if self._has_unowned_commit_directory_effects(prepared):
                prepared.unowned_directory_effects = True
                prepared.recovery_required = True
            try:
                rollback_error = self._rollback_failed_commit(prepared)
            except Exception as rollback_exc:
                rollback_error = rollback_exc
            prepared.recovery_required = bool(
                prepared.recovery_required
                or rollback_error is not None
                or self._prepared_recovery_artifacts(prepared)
            )
            return SceneTransactionResult(
                success=False,
                error=exc,
                rollback_error=rollback_error,
            )
        prepared.committed = True
        prepared.recovery_required = bool(
            self._prepared_recovery_artifacts(prepared)
        )
        return SceneTransactionResult(success=True)

    def rollback_prepared_changes(self) -> SceneTransactionResult:
        prepared = self._prepared_changes
        if prepared is None:
            return SceneTransactionResult(success=True)
        errors: list[Exception] = []
        if (
            prepared.action == SCENE_PENDING_SAVE
            and (
                prepared.committed
                or prepared.publication_attempted
                or prepared.recovery_required
            )
        ):
            try:
                self._restore_prepared_file(prepared)
            except Exception as exc:
                errors.append(exc)
        publication_rollback_attempted = False
        if prepared.publication_transaction is not None:
            rollback_publication = getattr(
                self._bridge,
                "rollback_scene_publication",
                None,
            )
            if callable(rollback_publication):
                publication_rollback_attempted = True
                try:
                    rollback_publication(prepared.publication_transaction)
                except Exception as exc:
                    errors.append(exc)
        try:
            self._restore_activation_snapshot(
                prepared.activation_snapshot,
                emit_bridge=not publication_rollback_attempted,
                restore_bridge=not publication_rollback_attempted,
            )
        except Exception as exc:
            errors.append(exc)
        recovery_artifacts = self._prepared_recovery_artifacts(prepared)
        unresolved_artifact = bool(recovery_artifacts)
        unowned_effects = self._refresh_unowned_commit_directory_effects(prepared)
        if errors or unresolved_artifact or unowned_effects:
            prepared.recovery_required = True
            if not errors:
                reason = (
                    f"Scene recovery evidence remains: {recovery_artifacts[0]}"
                    if unresolved_artifact
                    else "Scene saver changed an unowned library path"
                )
                errors.append(RuntimeError(reason))
            try:
                self._refresh_recovery_conflict(prepared.activation_snapshot)
            except Exception as exc:
                errors.append(exc)
            return SceneTransactionResult(
                success=False,
                error=errors[0],
                rollback_error=errors[1] if len(errors) > 1 else None,
            )
        prepared.recovery_required = False
        self._prepared_changes = None
        self.refresh_authoritative_user_conflict()
        return SceneTransactionResult(success=True)

    def finalize_prepared_changes(
        self,
        *,
        retain_rollback: bool = False,
    ) -> SceneTransactionResult:
        prepared = self._prepared_changes
        if prepared is None:
            return SceneTransactionResult(success=True)
        recovery_artifacts = self._prepared_recovery_artifacts(prepared)
        if (
            prepared.committed
            and prepared.committed_path is not None
            and prepared.committed_receipt_revision
            and recovery_artifacts
        ):
            try:
                config_library.finalize_committed_scene_recovery(
                    prepared.committed_path,
                    expected_revision=prepared.committed_receipt_revision,
                )
            except Exception as exc:
                prepared.recovery_required = True
                return SceneTransactionResult(success=False, error=exc)
            if self._prepared_recovery_artifacts(prepared):
                prepared.recovery_required = True
                return SceneTransactionResult(
                    success=False,
                    error=RuntimeError(
                        "committed Scene cleanup evidence remains after finalize"
                    ),
                )
            prepared.recovery_path = None
            if not prepared.unowned_directory_effects:
                prepared.recovery_required = False
        elif (
            prepared.committed
            and prepared.recovery_required
            and not recovery_artifacts
            and not prepared.unowned_directory_effects
        ):
            # A synthetic unreadable-namespace latch is cleared only after a
            # fresh full artifact scan succeeds and proves the namespace empty.
            prepared.recovery_path = None
            prepared.recovery_required = False
        if prepared.recovery_required:
            return SceneTransactionResult(
                success=False,
                error=RuntimeError(
                    "cannot finalize while Scene recovery evidence is unresolved"
                ),
            )
        if (
            prepared.committed
            and prepared.action == SCENE_PENDING_SAVE
            and prepared.publication_transaction is not None
            and not prepared.publication_finalized
        ):
            finalize_publication = getattr(
                self._bridge,
                "finalize_scene_publication",
                None,
            )
            if not callable(finalize_publication):
                return SceneTransactionResult(
                    success=False,
                    error=RuntimeError("Bridge cannot finalize Scene publication"),
                )
            self._state.ignore_own_scene_changed = True
            try:
                finalize_publication(prepared.publication_transaction)
                if (
                    str(
                        getattr(
                            prepared.publication_transaction,
                            "status",
                            "",
                        )
                        or ""
                    ).strip()
                    != "finalized"
                ):
                    return SceneTransactionResult(
                        success=False,
                        error=RuntimeError(
                            "Bridge did not finalize the Scene publication"
                        ),
                    )
            except Exception as exc:
                return SceneTransactionResult(success=False, error=exc)
            finally:
                self._state.ignore_own_scene_changed = False
            prepared.publication_finalized = True
        if not retain_rollback:
            self._prepared_changes = None
        return SceneTransactionResult(success=True)

    def release_finalized_changes(self) -> SceneTransactionResult:
        """Discard recovery evidence only after the outer transaction finalizes."""

        prepared = self._prepared_changes
        if prepared is None:
            return SceneTransactionResult(success=True)
        if prepared.recovery_required:
            return SceneTransactionResult(
                success=False,
                error=RuntimeError(
                    "cannot release while Scene recovery evidence is unresolved"
                ),
            )
        if self._prepared_recovery_artifacts(prepared):
            prepared.recovery_required = True
            return SceneTransactionResult(
                success=False,
                error=RuntimeError(
                    "cannot release while Scene cleanup artifacts remain"
                ),
            )
        if not prepared.committed:
            return SceneTransactionResult(
                success=False,
                error=RuntimeError("cannot release an uncommitted Scene transaction"),
            )
        if (
            prepared.action == SCENE_PENDING_SAVE
            and prepared.publication_transaction is not None
            and not prepared.publication_finalized
        ):
            return SceneTransactionResult(
                success=False,
                error=RuntimeError("cannot release an unpublished Scene transaction"),
            )
        self._prepared_changes = None
        return SceneTransactionResult(success=True)

    def cancel_prepared_changes(self) -> None:
        prepared = self._prepared_changes
        if prepared is None:
            return
        if prepared.recovery_required:
            self.rollback_prepared_changes()
            return
        if not prepared.committed:
            self._prepared_changes = None

    @staticmethod
    def _path_key(path: Path) -> str:
        return os.path.normcase(os.path.abspath(path))

    @classmethod
    def _capture_scene_file(cls, path: Path) -> SceneFileSnapshot:
        target = config_library.validate_scene_library_write_path(path)
        try:
            payload = target.read_bytes()
        except FileNotFoundError:
            if os.path.lexists(target):
                raise OSError(f"scene target is not a regular file: {target}")
            payload = None
        except (IsADirectoryError, PermissionError) as exc:
            raise OSError(f"scene target is not a readable file: {target}") from exc
        validated = config_library.validate_scene_library_write_path(target)
        if cls._path_key(validated) != cls._path_key(target):
            raise ValueError(f"scene target identity changed while reading: {target}")
        return SceneFileSnapshot(path=validated, payload=payload)

    @classmethod
    def _capture_scene_directory(
        cls,
        directory: Path,
    ) -> dict[str, SceneFileSnapshot]:
        probe = config_library.validate_scene_library_write_path(
            directory / "scene-revision-probe.json"
        )
        if cls._path_key(probe.parent) != cls._path_key(directory):
            raise ValueError(f"scene library directory identity changed: {directory}")
        snapshots: dict[str, SceneFileSnapshot] = {}
        for candidate in directory.iterdir():
            if candidate.suffix.lower() != ".json":
                continue
            snapshot = cls._capture_scene_file(candidate)
            if snapshot.payload is not None:
                snapshots[cls._path_key(snapshot.path)] = snapshot
        config_library.validate_scene_library_write_path(probe)
        return snapshots

    @classmethod
    def _assert_prepared_revision(cls, prepared: PreparedSceneChanges) -> None:
        current = cls._capture_scene_directory(prepared.target_path.parent)
        expected_revisions = {
            key: snapshot.revision
            for key, snapshot in prepared.directory_snapshots.items()
        }
        current_revisions = {
            key: snapshot.revision for key, snapshot in current.items()
        }
        if current_revisions != expected_revisions:
            raise SceneSaveRevisionChanged(
                f"scene library changed after save preparation: {prepared.target_path.parent}"
            )

    @classmethod
    def _record_commit_candidate(cls, prepared: PreparedSceneChanges, entry) -> None:
        """Capture a same-directory returned target before strict receipt checks.

        A faulty saver may publish a different ID and then return that receipt.
        It is still safe to roll that file back when it is inside the exact
        prepared user directory; paths outside that boundary are never touched.
        """

        prepared.committed_receipt_revision = str(
            getattr(entry, "revision", "") or ""
        ).strip()
        receipt_recovery_path = getattr(entry, "recovery_path", None)
        if receipt_recovery_path is not None:
            prepared.recovery_path = Path(receipt_recovery_path)
        prepared.committed_directory_after = cls._capture_scene_directory(
            prepared.target_path.parent
        )
        raw_path = str(getattr(entry, "path", "") or "").strip()
        if not raw_path:
            return
        try:
            candidate = config_library.validate_scene_library_write_path(raw_path)
        except (OSError, ValueError):
            return
        if (
            candidate.suffix.lower() != ".json"
            or cls._path_key(candidate.parent)
            != cls._path_key(prepared.target_path.parent)
        ):
            return
        prepared.committed_path = candidate
        prepared.committed_before = prepared.directory_snapshots.get(
            cls._path_key(candidate),
            SceneFileSnapshot(path=candidate, payload=None),
        )
        prepared.committed_after = cls._capture_scene_file(candidate)
        if (
            prepared.committed_receipt_revision
            and prepared.committed_after.revision
            != prepared.committed_receipt_revision
        ):
            raise SceneSaveRevisionChanged(
                "scene save receipt revision no longer owns its returned target"
            )

    @classmethod
    def _assert_commit_directory_effects(cls, prepared: PreparedSceneChanges) -> None:
        """Reject a saver that mutated any JSON path beyond its frozen target."""

        after = prepared.committed_directory_after
        if after is None:
            raise SceneSaveRevisionChanged(
                "scene save has no verified post-write directory snapshot"
            )
        changed = cls._changed_snapshot_keys(prepared.directory_snapshots, after)
        allowed = {cls._path_key(prepared.target_path)}
        unexpected = changed - allowed
        if unexpected:
            details = ",".join(sorted(unexpected))
            raise ValueError(
                f"scene saver mutated paths outside its prepared target: {details}"
            )

    @classmethod
    def _has_unowned_commit_directory_effects(
        cls,
        prepared: PreparedSceneChanges,
    ) -> bool:
        """Treat directory deltas as diagnostics, never as ownership proof."""

        after = prepared.committed_directory_after
        if after is None:
            return False
        changed = cls._changed_snapshot_keys(prepared.directory_snapshots, after)
        owned: set[str] = set()
        if prepared.committed_receipt_revision and prepared.committed_path is not None:
            owned.add(cls._path_key(prepared.committed_path))
        if isinstance(
            prepared.file_mutation_receipt,
            config_library.SceneFileMutationReceipt,
        ):
            owned.add(cls._path_key(prepared.file_mutation_receipt.target))
        return bool(changed - owned)

    @classmethod
    def _refresh_unowned_commit_directory_effects(
        cls,
        prepared: PreparedSceneChanges,
    ) -> bool:
        if not prepared.unowned_directory_effects:
            return False
        try:
            current = cls._capture_scene_directory(prepared.target_path.parent)
        except Exception:
            return True
        changed = cls._changed_snapshot_keys(prepared.directory_snapshots, current)
        if prepared.external_revision_conflict:
            # An exact mutation receipt proved that this pathname was the one
            # captured and restored.  Its different revision belongs to the
            # external winner and is handled as an authoritative conflict; it
            # must not disguise that winner as an adjacent saver side effect.
            changed.discard(cls._path_key(prepared.target_path))
            if prepared.committed_path is not None:
                changed.discard(cls._path_key(prepared.committed_path))
        prepared.unowned_directory_effects = bool(changed)
        return prepared.unowned_directory_effects

    @classmethod
    def _prepared_recovery_artifacts(
        cls,
        prepared: PreparedSceneChanges,
    ) -> tuple[Path, ...]:
        if prepared.action != SCENE_PENDING_SAVE:
            return ()
        targets = {cls._path_key(prepared.target_path): prepared.target_path}
        if prepared.committed_path is not None:
            targets[cls._path_key(prepared.committed_path)] = prepared.committed_path
        artifacts: dict[str, Path] = {}
        for target in targets.values():
            try:
                for artifact in config_library.scene_recovery_artifacts(target):
                    artifacts[cls._path_key(artifact)] = artifact
            except Exception:
                # An unreadable recovery namespace is itself unresolved.
                fallback = target.parent / ".scene-recovery-unreadable"
                artifacts[cls._path_key(fallback)] = fallback
        return tuple(artifacts.values())

    @staticmethod
    def _changed_snapshot_keys(
        before: dict[str, SceneFileSnapshot],
        after: dict[str, SceneFileSnapshot],
    ) -> set[str]:
        keys = set(before) | set(after)
        return {
            key
            for key in keys
            if (
                before.get(key).revision if key in before else "missing"
            )
            != (
                after.get(key).revision if key in after else "missing"
            )
        }

    @classmethod
    def _validate_commit_receipt(
        cls,
        prepared: PreparedSceneChanges,
        entry,
    ) -> tuple[Path, str]:
        save_target = prepared.save_target
        if save_target is None:
            raise ValueError("scene save receipt has no prepared target")
        raw_path = str(getattr(entry, "path", "") or "").strip()
        if not raw_path:
            raise ValueError("scene save receipt is missing its committed path")
        committed_path = config_library.validate_scene_library_write_path(raw_path)
        if committed_path.suffix.lower() != ".json":
            raise ValueError(
                f"scene save receipt must identify a JSON target: {committed_path}"
            )
        if cls._path_key(committed_path) != cls._path_key(save_target.target_path):
            raise ValueError(
                "scene save receipt changed the prepared target path: "
                f"{committed_path}"
            )
        committed_scene_id = str(getattr(entry, "config_id", "") or "").strip()
        if (
            not committed_scene_id
            or committed_scene_id != committed_path.stem
            or committed_scene_id != save_target.target_scene_id
        ):
            raise ValueError(
                "scene save receipt identity does not match its prepared target"
            )
        receipt_mode_id = str(getattr(entry, "mode_id", "") or "").strip()
        if receipt_mode_id != save_target.mode_id:
            raise ValueError("scene save receipt changed the prepared work mode")
        if str(getattr(entry, "source_type", "") or "").strip() != "user":
            raise ValueError("scene save receipt is not an owned user resource")
        receipt_revision = str(getattr(entry, "revision", "") or "").strip()
        committed_after = prepared.committed_after
        if (
            not receipt_revision
            or committed_after is None
            or committed_after.payload is None
            or receipt_revision != committed_after.revision
        ):
            raise ValueError(
                "scene save receipt does not prove ownership of the published bytes"
            )
        return committed_path, committed_scene_id

    @classmethod
    def _load_canonical_committed_scene(
        cls,
        prepared: PreparedSceneChanges,
        *,
        scene_id: str,
        committed_path: Path,
        expected_revision: str,
    ) -> SceneWorkspace:
        if config_library.scene_file_revision(committed_path) != expected_revision:
            raise SceneSaveRevisionChanged(
                "committed Scene changed before canonical reload"
            )
        entry = get_scene_entry(scene_id, mode_id=prepared.mode_id)
        if entry is None or cls._path_key(entry.path) != cls._path_key(committed_path):
            raise ValueError(
                "scene save receipt does not resolve to the authoritative library entry"
            )
        scene = load_scene_from_library(scene_id, mode_id=prepared.mode_id)
        if config_library.scene_file_revision(committed_path) != expected_revision:
            raise SceneSaveRevisionChanged(
                "committed Scene changed during canonical reload"
            )
        return scene

    def _adopt_committed_scene(
        self,
        scene: SceneWorkspace,
        *,
        scene_id: str,
        path: str,
        source_type: str,
        publication_transaction: object | None = None,
        authoritative_revision: str = "",
    ) -> None:
        self.replace_local_context(
            scene,
            path=path,
            source="library",
            source_type=str(source_type or "user").strip() or "user",
            authoritative_revision=authoritative_revision,
        )
        self._state.ignore_own_scene_changed = True
        try:
            adopt_provisionally = getattr(
                self._bridge,
                "adopt_scene_provisionally",
                None,
            )
            if publication_transaction is not None and callable(adopt_provisionally):
                adopt_provisionally(
                    publication_transaction,
                    scene,
                    config_id=scene_id,
                    path=self._state.scene_path,
                    source=self._state.scene_source,
                    source_type=self._state.scene_source_type,
                    scene_dirty=False,
                )
            else:
                self._bridge.set_current_scene(
                    scene,
                    config_id=scene_id,
                    path=self._state.scene_path,
                    source=self._state.scene_source,
                    source_type=self._state.scene_source_type,
                    emit_signal=False,
                )
                set_dirty = getattr(self._bridge, "set_scene_dirty")
                try:
                    set_dirty(False, emit_signal=False)
                except TypeError:
                    set_dirty(False)
            self._projection.refresh_scene_selector()
            binding = self.publish_bound_template(
                scene,
                publication_transaction=publication_transaction,
            )
            self._projection.apply_scene(scene, binding.template)
            self._projection.refresh_navigation_cards()
            self.capture_persisted_scene(scene)
        finally:
            self._state.ignore_own_scene_changed = False

    def _capture_activation_snapshot(self) -> SceneActivationSnapshot:
        return SceneActivationSnapshot(
            bridge_state=self._bridge.capture_state_snapshot(),
            persisted_scene=copy.deepcopy(self._state.persisted_scene),
            scene_id=str(self._bridge.current_scene_id() or "").strip(),
            scene_path=self._state.scene_path,
            scene_source=self._state.scene_source,
            scene_source_type=self._state.scene_source_type,
            authoritative_user_revision=self.authoritative_user_revision(),
            authoritative_user_conflict=self.authoritative_user_conflict(),
            selected_card_id=str(self._projection.selected_card_id() or "").strip(),
        )

    def _restore_activation_snapshot(
        self,
        snapshot: SceneActivationSnapshot,
        *,
        emit_bridge: bool = True,
        restore_bridge: bool = True,
    ) -> None:
        self._state.restoring_activation = True
        self._state.ignore_own_scene_changed = True
        try:
            if restore_bridge:
                self._bridge.restore_state_snapshot(
                    snapshot.bridge_state,
                    emit_signal=False,
                )
            self.replace_local_context(
                self._bridge.current_scene(),
                path=(
                    snapshot.scene_path
                    if restore_bridge
                    else str(self._bridge.current_scene_path() or "")
                ),
                source=(
                    snapshot.scene_source
                    if restore_bridge
                    else str(self._bridge.current_scene_source() or "")
                ),
                source_type=(
                    snapshot.scene_source_type
                    if restore_bridge
                    else str(self._bridge.current_scene_source_type() or "")
                ),
                template=self._bridge.current_template(),
            )
            self._state.persisted_scene = copy.deepcopy(snapshot.persisted_scene)
            if restore_bridge:
                self._state.authoritative_user_revision = (
                    snapshot.authoritative_user_revision
                )
                self._state.authoritative_user_conflict = (
                    snapshot.authoritative_user_conflict
                )
            self._state.activating_scene_id = (
                snapshot.scene_id
                if restore_bridge
                else str(self._bridge.current_scene_id() or "").strip()
            )
            self._projection.refresh_scene_selector()
            if self._state.scene is not None:
                self._projection.apply_scene(
                    self._state.scene,
                    self._state.template,
                )
            self._projection.restore_selected_card(snapshot.selected_card_id)
            if emit_bridge:
                self._bridge.restore_state_snapshot(
                    snapshot.bridge_state,
                    emit_signal=True,
                )
        finally:
            self._state.activating_scene_id = ""
            self._state.ignore_own_scene_changed = False
            self._state.restoring_activation = False

    def _rollback_failed_commit(
        self,
        prepared: PreparedSceneChanges,
    ) -> Exception | None:
        rollback_errors: list[Exception] = []
        if prepared.publication_attempted:
            try:
                self._restore_prepared_file(prepared)
            except Exception as exc:
                rollback_errors.append(exc)
        publication_rollback_attempted = False
        if prepared.publication_transaction is not None:
            rollback_publication = getattr(
                self._bridge,
                "rollback_scene_publication",
                None,
            )
            if callable(rollback_publication):
                publication_rollback_attempted = True
                try:
                    rollback_publication(prepared.publication_transaction)
                except Exception as exc:
                    rollback_errors.append(exc)
        try:
            self._restore_activation_snapshot(
                prepared.activation_snapshot,
                emit_bridge=not publication_rollback_attempted,
                restore_bridge=not publication_rollback_attempted,
            )
        except Exception as exc:
            rollback_errors.append(exc)
        if rollback_errors or prepared.external_revision_conflict:
            try:
                self._refresh_recovery_conflict(prepared.activation_snapshot)
            except Exception as exc:
                rollback_errors.append(exc)
        return rollback_errors[0] if rollback_errors else None

    @classmethod
    def _restore_prepared_file(cls, prepared: PreparedSceneChanges) -> None:
        # A directory delta can reveal an invalid saver, but it cannot prove
        # who owns an adjacent file.  Only the receipt target/revision may be
        # mutated during rollback; every other delta remains diagnostic
        # recovery evidence.
        if isinstance(
            prepared.file_mutation_receipt,
            config_library.SceneFileMutationReceipt,
        ):
            receipt = prepared.file_mutation_receipt
            if prepared.file_rollback_completed:
                config_library.finalize_scene_file_cleanup(receipt)
            else:
                matched_expected = config_library.rollback_scene_file_mutation(
                    receipt
                )
                prepared.external_revision_conflict = not matched_expected
                prepared.file_rollback_completed = True
            prepared.file_mutation_receipt = None
            prepared.recovery_path = None
            return
        if prepared.file_rollback_completed:
            artifacts = cls._prepared_recovery_artifacts(prepared)
            if artifacts:
                target = prepared.committed_path or prepared.target_path
                before = prepared.committed_before
                if before is None:
                    before = prepared.directory_snapshots.get(cls._path_key(target))
                if before is None:
                    before = prepared.target_snapshot
                if before.revision == "missing":
                    raise SceneSaveRevisionChanged(
                        "deleted Scene cleanup has no exact mutation receipt"
                    )
                config_library.finalize_committed_scene_recovery(
                    target,
                    expected_revision=before.revision,
                )
                if cls._prepared_recovery_artifacts(prepared):
                    raise SceneSaveRevisionChanged(
                        "Scene rollback cleanup evidence remains unresolved"
                    )
            return
        cls._restore_single_prepared_target(prepared)
        prepared.file_rollback_completed = True

    @classmethod
    def _restore_single_prepared_target(cls, prepared: PreparedSceneChanges) -> None:
        """Fallback when directory capture failed, using only receipt ownership."""

        target = prepared.committed_path or prepared.target_path
        before = prepared.committed_before
        if before is None:
            before = prepared.directory_snapshots.get(cls._path_key(target))
        if before is None:
            before = (
                prepared.target_snapshot
                if cls._path_key(target) == cls._path_key(prepared.target_path)
                else SceneFileSnapshot(path=target, payload=None)
            )
        if (
            prepared.committed_receipt_revision
            and cls._prepared_recovery_artifacts(prepared)
        ):
            config_library.finalize_committed_scene_recovery(
                target,
                expected_revision=prepared.committed_receipt_revision,
            )
            prepared.recovery_path = None
        current = cls._capture_scene_file(target)
        if current.revision == before.revision:
            return
        after_revision = prepared.committed_receipt_revision
        if not after_revision:
            raise SceneSaveRevisionChanged(
                "scene publication has no verified post-write revision; "
                f"rollback refused: {target}"
            )
        if current.revision != after_revision:
            raise SceneSaveRevisionChanged(
                f"scene target changed after publication; rollback refused: {target}"
            )
        mutation_result = config_library.replace_scene_file_if_revision(
            target,
            expected_revision=after_revision,
            replacement_payload=before.payload,
        )
        # The receipt revision is a one-shot capability.  Once the conditional
        # mutation succeeds it must never be reused, even if a later live
        # verification observes another external write.
        prepared.file_rollback_completed = True
        if isinstance(
            mutation_result,
            config_library.SceneFileMutationReceipt,
        ):
            prepared.file_mutation_receipt = mutation_result
            prepared.recovery_path = mutation_result.recovery_dir
            config_library.finalize_scene_file_cleanup(mutation_result)
            prepared.file_mutation_receipt = None
            prepared.recovery_path = None
        if cls._prepared_recovery_artifacts(prepared):
            raise SceneSaveRevisionChanged(
                "Scene rollback cleanup evidence remains unresolved"
            )
        restored = cls._capture_scene_file(target)
        if restored.revision != before.revision:
            raise OSError(f"scene rollback verification failed: {target}")
