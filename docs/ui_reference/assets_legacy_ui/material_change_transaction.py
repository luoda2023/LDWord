"""Prepared save/discard transaction boundary for material packages."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import nullcontext
import copy
from dataclasses import dataclass
import logging
from types import MappingProxyType
from typing import Protocol, cast

from src.config.entity import EntityArchive
from src.config.material_package_library import (
    MaterialPackageFileSnapshot,
    MaterialPackageLibraryEntry,
    capture_material_package_entry_snapshot,
    material_package_entry_matches_snapshot,
    material_package_entry_target_lock,
    restore_material_package_entry_snapshot,
)
from src.shared.ui.toast import Toast


_LOGGER = logging.getLogger(__name__)

MATERIAL_PENDING_SAVE = "save"
MATERIAL_PENDING_DISCARD = "discard"


def _is_programming_error(exc: BaseException) -> bool:
    return isinstance(exc, (AssertionError, AttributeError, NameError, TypeError))


class MaterialPersistenceBoundary(Protocol):
    """State and operations the transaction is allowed to coordinate."""

    @property
    def current_entry(self) -> MaterialPackageLibraryEntry | None: ...

    @property
    def current_path(self) -> str: ...

    @property
    def persisted_snapshot(self) -> EntityArchive | None: ...

    def has_unsaved_changes(self) -> bool: ...

    def replace_identity(
        self,
        entry: MaterialPackageLibraryEntry | None,
        path: str,
    ) -> None: ...

    def replace_persisted_snapshot(self, snapshot: EntityArchive | None) -> None: ...

    def refresh_actions(self) -> None: ...


@dataclass(frozen=True, slots=True)
class MaterialChangeTransactionPort:
    """Explicit editor operations required by the transaction boundary."""

    persistence: Callable[[], MaterialPersistenceBoundary]
    persist_current_profile_editor: Callable[[], bool]
    current_archive: Callable[[], EntityArchive]
    current_profile_index: Callable[[], int]
    set_archive: Callable[[EntityArchive, int], bool]
    save_pending_changes: Callable[[], bool]
    capture_persistence_snapshot: Callable[[], None]
    refresh_archive_selector: Callable[[], None]


class MaterialChangeTransactionCoordinator:
    """Prepare, commit, and CAS-recover one material package decision."""

    def __init__(self, port: MaterialChangeTransactionPort) -> None:
        self._port = port
        self._prepared_state: dict[str, object] | None = None
        self._prepared_view: Mapping[str, object] | None = None

    @property
    def prepared_state(self) -> Mapping[str, object] | None:
        """Read-only compatibility view of retained recovery evidence."""

        return self._prepared_view

    def _replace_prepared_state(self, state: dict[str, object] | None) -> None:
        self._prepared_state = state
        self._prepared_view = MappingProxyType(state) if state is not None else None

    def prepared_save_active(self) -> bool:
        state = self._prepared_state
        return bool(
            state is not None
            and state.get("action") == MATERIAL_PENDING_SAVE
            and not bool(state.get("committed"))
        )

    def begin_publication(self) -> bool:
        """CAS-check the prepared target before allowing the writer to run."""

        state = self._prepared_state
        if not self.prepared_save_active() or state is None:
            return True
        if bool(state.get("publication_attempted")):
            return True
        entry = cast(MaterialPackageLibraryEntry | None, state.get("entry"))
        expected = cast(
            MaterialPackageFileSnapshot | None,
            state.get("target_snapshot"),
        )
        if entry is not None and expected is not None:
            try:
                unchanged = material_package_entry_matches_snapshot(entry, expected)
            except Exception as exc:
                _LOGGER.exception("material publication precondition failed")
                state["revision_conflict"] = True
                Toast.show_error(f"无法确认资料包保存版本: {exc}")
                if _is_programming_error(exc):
                    raise
                return False
            if not unchanged:
                state["revision_conflict"] = True
                Toast.show_warning("资料包已被其他进程修改，本次保存已取消")
                return False
        state["publication_attempted"] = True
        return True

    def record_publication_identity(
        self,
        entry: MaterialPackageLibraryEntry,
    ) -> None:
        if not self.prepared_save_active():
            return
        state = self._prepared_state
        assert state is not None
        state["published_entry"] = copy.deepcopy(entry)

    def record_publication(
        self,
        entry: MaterialPackageLibraryEntry,
        snapshot: MaterialPackageFileSnapshot | None = None,
    ) -> None:
        if not self.prepared_save_active():
            return
        # Persist the returned identity before observing its revision. If the
        # observation fails, rollback retains this evidence but never guesses
        # that whatever bytes are currently there belong to this writer.
        self.record_publication_identity(entry)
        state = self._prepared_state
        assert state is not None
        published_snapshot = (
            snapshot
            if snapshot is not None
            else capture_material_package_entry_snapshot(entry)
        )
        state["publication_confirmed"] = True
        state["published_snapshot"] = published_snapshot

    def record_adoption(self) -> None:
        if not self.prepared_save_active():
            return
        state = self._prepared_state
        assert state is not None
        state["adopted"] = True

    def prepare(self, action: str) -> bool:
        """Snapshot a material decision and validate it without writing."""

        if not self.cancel():
            return False
        persistence = self._port.persistence()
        if not persistence.has_unsaved_changes():
            return True
        normalized_action = str(action or "").strip()
        if normalized_action not in {MATERIAL_PENDING_SAVE, MATERIAL_PENDING_DISCARD}:
            return False
        if not self._port.persist_current_profile_editor():
            Toast.show_warning("资料字段存在冲突，暂时无法保存或切换")
            return False
        archive = copy.deepcopy(self._port.current_archive())
        baseline = copy.deepcopy(persistence.persisted_snapshot)
        entry = copy.deepcopy(persistence.current_entry)
        if (
            normalized_action == MATERIAL_PENDING_SAVE
            and entry is not None
            and str(entry.source_type or "") != "user"
        ):
            Toast.show_warning("内置资料包不能直接保存，请先创建副本")
            return False

        target_snapshot: MaterialPackageFileSnapshot | None = None
        if normalized_action == MATERIAL_PENDING_SAVE and entry is not None:
            try:
                target_snapshot = capture_material_package_entry_snapshot(entry)
            except Exception as exc:
                _LOGGER.exception("failed to capture material save precondition")
                Toast.show_error(f"无法准备资料包保存: {exc}")
                if _is_programming_error(exc):
                    raise
                return False
        self._replace_prepared_state(
            {
                "action": normalized_action,
                "archive": archive,
                "baseline": baseline,
                "entry": entry,
                "current_path": persistence.current_path,
                "profile_index": self._port.current_profile_index(),
                "target_snapshot": target_snapshot,
                "publication_attempted": False,
                "publication_confirmed": False,
                "published_entry": None,
                "published_snapshot": None,
                "adopted": False,
                "committed": False,
                "recovery_required": False,
                "revision_conflict": False,
            }
        )
        return True

    def _restore_storage(self, state: dict[str, object]) -> bool:
        if not (
            state.get("action") == MATERIAL_PENDING_SAVE
            and bool(state.get("publication_attempted"))
        ):
            return True
        original_entry = cast(
            MaterialPackageLibraryEntry | None,
            state.get("entry"),
        )
        published_entry = cast(
            MaterialPackageLibraryEntry | None,
            state.get("published_entry"),
        )
        published_snapshot = cast(
            MaterialPackageFileSnapshot | None,
            state.get("published_snapshot"),
        )
        original_snapshot = cast(
            MaterialPackageFileSnapshot | None,
            state.get("target_snapshot"),
        )
        if published_snapshot is None:
            if published_entry is None and original_entry is None:
                # A failed creator without a returned identity owns its exact
                # mkdir cleanup. Never infer ownership by scanning siblings.
                return True
            if published_entry is None and original_entry is not None:
                try:
                    unchanged = bool(
                        original_snapshot is not None
                        and material_package_entry_matches_snapshot(
                            original_entry,
                            original_snapshot,
                        )
                    )
                except Exception:
                    _LOGGER.exception(
                        "failed to verify unconfirmed material publication"
                    )
                    unchanged = False
                if unchanged:
                    return True
            state["revision_conflict"] = True
            Toast.show_error(
                "资料包回滚已停止：发布版本未经确认，目标可能已被外部修改"
            )
            _LOGGER.error(
                "material rollback skipped for unconfirmed publication: %s",
                getattr(published_entry or original_entry, "path", ""),
            )
            return False
        if published_entry is None:
            state["revision_conflict"] = True
            _LOGGER.error("material rollback has revision evidence without identity")
            return False
        if original_entry is None:
            original_snapshot = MaterialPackageFileSnapshot(
                path=published_snapshot.path,
                payload=None,
                revision="missing",
            )
        if original_snapshot is None:
            return True
        restored = restore_material_package_entry_snapshot(
            published_entry,
            expected_current=published_snapshot,
            restore=original_snapshot,
        )
        if not restored:
            state["revision_conflict"] = True
            Toast.show_error("资料包回滚被拒绝：目标已被其他进程修改")
            _LOGGER.error(
                "material rollback CAS conflict: %s",
                published_entry.path,
            )
        return restored

    def _commit_discard(self, state: dict[str, object]) -> bool:
        baseline = state.get("baseline")
        if baseline is None:
            state["committed"] = True
            return True
        try:
            restored = self._port.set_archive(
                copy.deepcopy(cast(EntityArchive, baseline)),
                int(state.get("profile_index") or 0),
            )
        except Exception as exc:
            _LOGGER.exception("failed to apply prepared material discard")
            state["recovery_required"] = True
            Toast.show_error(f"恢复资料包修改失败：{exc}")
            if _is_programming_error(exc):
                raise
            return False
        if not restored:
            state["recovery_required"] = True
            return False
        try:
            self._port.capture_persistence_snapshot()
        except Exception as exc:
            _LOGGER.exception("failed to capture discarded material baseline")
            state["recovery_required"] = True
            Toast.show_error(f"记录资料包恢复状态失败：{exc}")
            if _is_programming_error(exc):
                raise
            return False
        state["committed"] = True
        return True

    def commit(self) -> bool:
        """Apply a prepared decision while retaining CAS rollback evidence."""

        state = self._prepared_state
        if state is None:
            return not self._port.persistence().has_unsaved_changes()
        if bool(state.get("committed")):
            return True
        action = str(state.get("action") or "")
        if action == MATERIAL_PENDING_DISCARD:
            return self._commit_discard(state)
        if action != MATERIAL_PENDING_SAVE:
            return False
        entry = cast(MaterialPackageLibraryEntry | None, state.get("entry"))
        target_guard = (
            material_package_entry_target_lock(entry)
            if entry is not None
            else nullcontext()
        )
        try:
            # The prepared revision check and writer run under one same-process
            # target lock. The persistence service re-enters this RLock while
            # writing and recording the publication receipt.
            with target_guard:
                if not self.begin_publication():
                    saved = False
                else:
                    saved = self._port.save_pending_changes()
        except Exception as exc:
            _LOGGER.exception("prepared material publication failed")
            Toast.show_error(f"保存资料包失败：{exc}")
            self.rollback()
            if _is_programming_error(exc):
                raise
            return False
        if not saved:
            self.rollback()
            return False
        if not bool(state.get("publication_confirmed")):
            _LOGGER.error(
                "prepared material save returned success without publication evidence"
            )
            Toast.show_error("资料包保存未返回可验证的发布版本")
            self.rollback()
            return False
        state["adopted"] = True
        state["committed"] = True
        return True

    def rollback(self) -> bool:
        state = self._prepared_state
        if state is None:
            return True
        persistence = self._port.persistence()
        previous_entry = copy.deepcopy(persistence.current_entry)
        previous_path = persistence.current_path
        previous_baseline = copy.deepcopy(persistence.persisted_snapshot)
        archive_restored = False
        try:
            if not self._restore_storage(state):
                state["recovery_required"] = True
                return False
            persistence.replace_identity(
                copy.deepcopy(
                    cast(MaterialPackageLibraryEntry | None, state.get("entry"))
                ),
                str(state.get("current_path") or ""),
            )
            archive_restored = self._port.set_archive(
                copy.deepcopy(cast(EntityArchive, state["archive"])),
                int(state.get("profile_index") or 0),
            )
            if not archive_restored:
                persistence.replace_identity(previous_entry, previous_path)
                persistence.replace_persisted_snapshot(previous_baseline)
                state["recovery_required"] = True
                return False
            persistence.replace_persisted_snapshot(
                copy.deepcopy(
                    cast(EntityArchive | None, state.get("baseline"))
                )
            )
            self._port.refresh_archive_selector()
            persistence.refresh_actions()
        except Exception as exc:
            _LOGGER.exception("prepared material rollback failed")
            if not archive_restored:
                persistence.replace_identity(previous_entry, previous_path)
                persistence.replace_persisted_snapshot(previous_baseline)
            state["recovery_required"] = True
            Toast.show_error(f"回滚资料包保存失败: {exc}")
            if _is_programming_error(exc):
                raise
            return False

        self._replace_prepared_state(None)
        return True

    def finalize(self) -> None:
        self._replace_prepared_state(None)

    def cancel(self) -> bool:
        state = self._prepared_state
        if state is None:
            self._replace_prepared_state(None)
            return True
        if bool(state.get("recovery_required")):
            return self.rollback()
        if bool(state.get("committed")) or bool(state.get("publication_attempted")):
            return False
        self._replace_prepared_state(None)
        return True


__all__ = [
    "MATERIAL_PENDING_DISCARD",
    "MATERIAL_PENDING_SAVE",
    "MaterialChangeTransactionCoordinator",
    "MaterialChangeTransactionPort",
]
