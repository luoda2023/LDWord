"""Composed persistence service for the material package editor."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import nullcontext
import copy
from dataclasses import dataclass
import logging
from types import MappingProxyType
from typing import Protocol

from src.config.entity import EntityArchive
from src.config.material_package_library import (
    MaterialPackageFileSnapshot,
    MaterialPackageLibraryEntry,
    MaterialPackagePublicationReceipt,
    capture_material_package_entry_snapshot,
    material_package_entry_target_lock,
    material_package_entry_matches_snapshot,
    restore_material_package_entry_snapshot,
    save_material_package_entry,
)
from src.shared.ui.card import Card
from src.shared.ui.persistence_actions import PersistenceActions
from src.shared.ui.toast import Toast


_LOGGER = logging.getLogger(__name__)

_SECTION_PROFILE_FIELDS: dict[str, tuple[str, ...]] = {
    "fields": (
        "profile_id",
        "profile_name",
        "fields",
        "field_scopes",
        "field_functions",
        "field_sources",
        "declared_field_keys",
        "field_aliases",
    ),
    "content": ("content_bindings", "content_rules"),
    "timeline": ("timeline_plans",),
    "images": (
        "assets_dir",
        "asset_paths",
        "asset_bindings",
        "asset_metadata",
        "asset_token_specs",
        "asset_items",
        "asset_item_history",
        "image_material_rules",
    ),
    "attachments": ("attachment_role_specs", "attachment_bindings"),
}


def _is_programming_error(exc: BaseException) -> bool:
    return isinstance(exc, (AssertionError, AttributeError, NameError, TypeError))


class _MaterialAdoptionRejected(RuntimeError):
    pass


class MaterialPublicationBoundary(Protocol):
    """Publication facts the persistence service may report to a transaction."""

    def prepared_save_active(self) -> bool: ...

    def begin_publication(self) -> bool: ...

    def record_publication_identity(
        self,
        entry: MaterialPackageLibraryEntry,
    ) -> None: ...

    def record_publication(
        self,
        entry: MaterialPackageLibraryEntry,
        snapshot: MaterialPackageFileSnapshot,
    ) -> None: ...

    def record_adoption(self) -> None: ...


@dataclass(frozen=True, slots=True)
class MaterialPersistencePort:
    """Explicit editor operations needed by material persistence."""

    current_archive: Callable[[], EntityArchive]
    persist_current_profile_editor: Callable[[], bool]
    set_archive: Callable[[EntityArchive, int], bool]
    activate_archive_entry: Callable[[MaterialPackageLibraryEntry], bool]
    capture_persistence_snapshot: Callable[[EntityArchive | None], None]
    refresh_archive_selector: Callable[[], None]
    current_mode_id: Callable[[], str]
    current_profile_index: Callable[[], int]
    field_conflicts: Callable[[], bool]
    publication_transaction: Callable[[], MaterialPublicationBoundary]


@dataclass(frozen=True, slots=True)
class _OwnedPersistenceState:
    entry: MaterialPackageLibraryEntry | None
    path: str
    baseline: EntityArchive | None


class MaterialPersistenceCoordinator:
    """Own package identity, baseline, card actions, and save publication."""

    def __init__(self, port: MaterialPersistencePort) -> None:
        self._port = port
        self._current_entry: MaterialPackageLibraryEntry | None = None
        self._current_path = ""
        self._persisted_snapshot: EntityArchive | None = None
        self._actions: dict[str, PersistenceActions] = {}
        self._actions_view: Mapping[str, PersistenceActions] = MappingProxyType(
            self._actions
        )
        self._publication_recovery_state: dict[str, object] | None = None

    @property
    def current_entry(self) -> MaterialPackageLibraryEntry | None:
        return self._current_entry

    @property
    def current_path(self) -> str:
        return self._current_path

    @property
    def persisted_snapshot(self) -> EntityArchive | None:
        return copy.deepcopy(self._persisted_snapshot)

    @property
    def actions(self) -> Mapping[str, PersistenceActions]:
        return self._actions_view

    @property
    def publication_recovery_state(self) -> Mapping[str, object] | None:
        state = self._publication_recovery_state
        if state is None:
            return None
        return MappingProxyType(copy.deepcopy(state))

    def replace_identity(
        self,
        entry: MaterialPackageLibraryEntry | None,
        path: str,
    ) -> None:
        self._current_entry = entry
        self._current_path = str(path or "")

    def replace_persisted_snapshot(self, snapshot: EntityArchive | None) -> None:
        self._persisted_snapshot = copy.deepcopy(snapshot)

    def _owned_state(self) -> _OwnedPersistenceState:
        return _OwnedPersistenceState(
            entry=copy.deepcopy(self._current_entry),
            path=self._current_path,
            baseline=copy.deepcopy(self._persisted_snapshot),
        )

    def _restore_owned_state(self, state: _OwnedPersistenceState) -> None:
        self.replace_identity(copy.deepcopy(state.entry), state.path)
        self.replace_persisted_snapshot(state.baseline)

    def setup_actions(self, card_by_section: Mapping[str, Card]) -> None:
        self._actions.clear()
        for section_id, card in card_by_section.items():
            actions = PersistenceActions(
                object_name_prefix=f"assets_{section_id}",
                compact=True,
                parent=card,
            )
            actions.restore_requested.connect(
                lambda section_id=section_id: self.restore_section(section_id)
            )
            actions.save_requested.connect(self.save_current_package)
            card.add_header_action(actions)
            self._actions[section_id] = actions

    def capture_snapshot(self, archive: EntityArchive | None = None) -> None:
        # ``set_archive`` hydrates legacy packages and projects implicit image
        # defaults into the working editor. Capture that normalized working
        # representation, not the pre-hydration payload passed by the caller.
        del archive
        target = self._port.current_archive()
        self._persisted_snapshot = copy.deepcopy(target)
        self._publication_recovery_state = None
        self.refresh_actions()

    def _disable_actions(self) -> None:
        for actions in self._actions.values():
            actions.set_states(restore_enabled=False, save_enabled=False)

    def fail_closed_actions(self) -> None:
        """Disable restore/save controls after an unprojectable editor failure."""

        self._disable_actions()

    def refresh_actions(self) -> None:
        if not self._actions:
            return
        baseline = self._persisted_snapshot
        if baseline is None:
            self._disable_actions()
            return
        try:
            current = self._port.current_archive()
            conflicts = self._port.field_conflicts()
            writable = bool(
                self._current_entry is None
                or self._current_entry.source_type == "user"
            )
            for section_id, actions in self._actions.items():
                dirty = self.material_section_projection(
                    current, section_id
                ) != self.material_section_projection(baseline, section_id)
                actions.set_states(
                    restore_enabled=dirty,
                    save_enabled=dirty and writable and not conflicts,
                )
        except Exception:
            _LOGGER.exception("failed to refresh material persistence actions")
            self._disable_actions()

    @staticmethod
    def material_section_projection(
        archive: EntityArchive,
        section_id: str,
    ) -> tuple[object, ...]:
        field_names = _SECTION_PROFILE_FIELDS[section_id]
        return tuple(
            tuple(copy.deepcopy(getattr(profile, field_name)) for field_name in field_names)
            for profile in archive.profiles
        )

    @classmethod
    def material_edit_projection(
        cls,
        archive: EntityArchive,
    ) -> tuple[object, ...]:
        """Project only package state that the material editor lets users edit."""

        return (
            archive.archive_name,
            tuple(
                cls.material_section_projection(archive, section_id)
                for section_id in _SECTION_PROFILE_FIELDS
            ),
        )

    def has_unsaved_changes(self) -> bool:
        baseline = self._persisted_snapshot
        if baseline is None:
            return False
        try:
            current = self._port.current_archive()
            return self.material_edit_projection(
                current
            ) != self.material_edit_projection(baseline)
        except Exception:
            _LOGGER.exception("failed to project current material changes")
            return True

    def restore_section(self, section_id: str) -> bool:
        baseline = self._persisted_snapshot
        if baseline is None or section_id not in _SECTION_PROFILE_FIELDS:
            return False
        try:
            current_index = self._port.current_profile_index()
            current = self._port.current_archive()
            field_names = _SECTION_PROFILE_FIELDS[section_id]
            baseline_profiles_by_id = {
                str(profile.profile_id or ""): profile
                for profile in baseline.profiles
                if str(profile.profile_id or "")
            }
            for index, profile in enumerate(current.profiles):
                saved = baseline_profiles_by_id.get(str(profile.profile_id or ""))
                if saved is None and index < len(baseline.profiles):
                    saved = baseline.profiles[index]
                if saved is None:
                    continue
                for field_name in field_names:
                    setattr(
                        profile,
                        field_name,
                        copy.deepcopy(getattr(saved, field_name)),
                    )
            restored = self._port.set_archive(current, current_index)
        except Exception as exc:
            _LOGGER.exception("failed to restore material section %s", section_id)
            self.refresh_actions()
            Toast.show_error(f"恢复资料失败: {exc}")
            if _is_programming_error(exc):
                raise
            return False
        if not restored:
            self.refresh_actions()
            Toast.show_error("恢复资料失败：编辑器拒绝了恢复内容")
            return False
        self.refresh_actions()
        Toast.show_success(f"已恢复{self._material_section_label(section_id)}到上次保存状态")
        return True

    @staticmethod
    def _capture_publication_snapshot(
        entry: MaterialPackageLibraryEntry,
    ) -> MaterialPackageFileSnapshot:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                return capture_material_package_entry_snapshot(entry)
            except Exception as exc:
                last_error = exc
                if _is_programming_error(exc) or attempt == 1:
                    raise
                _LOGGER.warning(
                    "material publication revision observation failed; retrying",
                    exc_info=True,
                )
        assert last_error is not None
        raise last_error

    def _retain_direct_publication_recovery(
        self,
        *,
        previous_state: _OwnedPersistenceState,
        original_snapshot: MaterialPackageFileSnapshot | None,
        receipt: MaterialPackagePublicationReceipt | None,
        affected_entry: MaterialPackageLibraryEntry | None,
        attempted_archive: EntityArchive,
        reason: str,
    ) -> None:
        recovery_entry = receipt.entry if receipt is not None else affected_entry
        if receipt is not None:
            self.replace_identity(receipt.entry, str(receipt.entry.path))
        else:
            self.replace_identity(previous_state.entry, previous_state.path)
        self.replace_persisted_snapshot(previous_state.baseline)
        self._publication_recovery_state = {
            "receipt": copy.deepcopy(receipt),
            "affected_entry": copy.deepcopy(recovery_entry),
            "original_snapshot": original_snapshot,
            "attempted_archive": copy.deepcopy(attempted_archive),
            "previous_entry": copy.deepcopy(previous_state.entry),
            "previous_path": previous_state.path,
            "previous_baseline": copy.deepcopy(previous_state.baseline),
            "ownership_confirmed": receipt is not None,
            "recovery_required": True,
            "reason": str(reason),
        }
        self._disable_actions()

    def _recover_direct_publication(
        self,
        *,
        previous_state: _OwnedPersistenceState,
        original_snapshot: MaterialPackageFileSnapshot | None,
        receipt: MaterialPackagePublicationReceipt | None,
        affected_entry: MaterialPackageLibraryEntry | None,
        attempted_archive: EntityArchive,
        reason: str,
    ) -> bool:
        restored = True
        published_entry = receipt.entry if receipt is not None else affected_entry
        published_snapshot = receipt.snapshot if receipt is not None else None
        if receipt is not None and published_snapshot is not None:
            restore_snapshot = original_snapshot
            if restore_snapshot is None:
                restore_snapshot = MaterialPackageFileSnapshot(
                    path=published_snapshot.path,
                    payload=None,
                    revision="missing",
                )
            try:
                restored = restore_material_package_entry_snapshot(
                    published_entry,
                    expected_current=published_snapshot,
                    restore=restore_snapshot,
                )
            except Exception:
                _LOGGER.exception("direct material publication rollback failed")
                restored = False
        elif receipt is not None:
            restored = False
            _LOGGER.error(
                "direct material rollback skipped without a publication revision: %s",
                receipt.entry.path,
            )
        elif published_entry is not None and original_snapshot is not None:
            try:
                restored = material_package_entry_matches_snapshot(
                    published_entry,
                    original_snapshot,
                )
            except Exception:
                _LOGGER.exception(
                    "failed to verify unconfirmed direct material publication"
                )
                restored = False
            if not restored:
                _LOGGER.error(
                    "direct material rollback skipped because publication ownership "
                    "is unconfirmed: %s",
                    published_entry.path,
                )
        if restored:
            self._restore_owned_state(previous_state)
            self._publication_recovery_state = None
        else:
            self._retain_direct_publication_recovery(
                previous_state=previous_state,
                original_snapshot=original_snapshot,
                receipt=receipt,
                affected_entry=published_entry,
                attempted_archive=attempted_archive,
                reason=reason,
            )
        if not restored:
            _LOGGER.error("direct material rollback rejected by revision CAS")
            self._disable_actions()
            Toast.show_error("资料包保存回滚被拒绝：目标已被其他进程修改")
        return restored

    def adopt_created_package(
        self,
        receipt: MaterialPackagePublicationReceipt,
    ) -> bool:
        """Activate a newly created package or CAS-remove its exact orphan."""

        if receipt.snapshot is None:
            raise ValueError("created_material_package_receipt_revision_missing")
        entry = receipt.entry
        previous_state = self._owned_state()
        attempted_archive = self._port.current_archive()
        try:
            adopted = self._port.activate_archive_entry(entry)
        except Exception as exc:
            _LOGGER.exception("failed to adopt newly created material package")
            self._recover_direct_publication(
                previous_state=previous_state,
                original_snapshot=None,
                receipt=receipt,
                affected_entry=entry,
                attempted_archive=attempted_archive,
                reason=str(exc),
            )
            if _is_programming_error(exc):
                raise
            return False
        if adopted:
            self._publication_recovery_state = None
            return True
        self._recover_direct_publication(
            previous_state=previous_state,
            original_snapshot=None,
            receipt=receipt,
            affected_entry=entry,
            attempted_archive=attempted_archive,
            reason="material package activation was rejected",
        )
        return False

    def save_current_package(self) -> bool:
        transaction = self._port.publication_transaction()
        track_publication = transaction.prepared_save_active()
        entry = self._current_entry
        if entry is not None and entry.source_type != "user":
            Toast.show_warning("内置资料包不能直接保存，请先创建副本")
            return False
        if not self._port.persist_current_profile_editor():
            Toast.show_warning("资料字段存在冲突，暂时无法保存")
            return False
        archive = self._port.current_archive()
        previous_state = self._owned_state()
        original_snapshot: MaterialPackageFileSnapshot | None = None
        receipt: MaterialPackagePublicationReceipt | None = None
        target_guard = (
            material_package_entry_target_lock(entry)
            if entry is not None
            else nullcontext()
        )
        try:
            with target_guard:
                if not track_publication and entry is not None:
                    original_snapshot = capture_material_package_entry_snapshot(entry)
                if not transaction.begin_publication():
                    return False
                if entry is None:
                    from src.config.material_package_library import (
                        create_material_package_in_library_with_receipt,
                    )

                    receipt = create_material_package_in_library_with_receipt(
                        archive,
                        mode_id=self._port.current_mode_id(),
                        requested_id=archive.archive_name,
                    )
                    published_entry = receipt.entry
                else:
                    published_entry = save_material_package_entry(archive, entry)
                    # Existing-package writers return identity first; revision
                    # observation follows while the original target lock is
                    # still held. New-package creators already returned their
                    # first-lock receipt and must never be recaptured here.
                    receipt = MaterialPackagePublicationReceipt(
                        entry=copy.deepcopy(published_entry)
                    )
                if track_publication:
                    transaction.record_publication_identity(published_entry)
                if entry is not None:
                    with material_package_entry_target_lock(published_entry):
                        receipt = receipt.with_snapshot(
                            self._capture_publication_snapshot(published_entry)
                        )
                if track_publication:
                    assert receipt.snapshot is not None
                    transaction.record_publication(
                        published_entry,
                        receipt.snapshot,
                    )

            if entry is None:
                if not self._port.activate_archive_entry(receipt.entry):
                    raise _MaterialAdoptionRejected(
                        "material package activation was rejected"
                    )
            else:
                self.replace_identity(receipt.entry, str(receipt.entry.path))
                archive.source_path = str(receipt.entry.path)
                self._port.capture_persistence_snapshot(archive)
                self._port.refresh_archive_selector()
            if track_publication:
                transaction.record_adoption()
        except _MaterialAdoptionRejected as exc:
            _LOGGER.error("direct material adoption rejected: %s", exc)
            if not track_publication:
                self._recover_direct_publication(
                    previous_state=previous_state,
                    original_snapshot=original_snapshot,
                    receipt=receipt,
                    affected_entry=entry,
                    attempted_archive=archive,
                    reason=str(exc),
                )
            return False
        except Exception as exc:
            _LOGGER.exception("material save or adoption failed")
            if not track_publication:
                self._recover_direct_publication(
                    previous_state=previous_state,
                    original_snapshot=original_snapshot,
                    receipt=receipt,
                    affected_entry=entry,
                    attempted_archive=archive,
                    reason=str(exc),
                )
            Toast.show_error(f"保存资料包失败: {exc}")
            if _is_programming_error(exc):
                raise
            return False

        self._publication_recovery_state = None
        assert receipt is not None
        Toast.show_success(f"已保存资料包: {receipt.entry.name}")
        return True

    def save_pending_changes(self) -> bool:
        if not self.has_unsaved_changes():
            return True
        return self.save_current_package()

    @staticmethod
    def _material_section_label(section_id: str) -> str:
        return {
            "fields": "字段资料",
            "content": "文件资料",
            "timeline": "时间计划",
            "images": "图片资料",
            "attachments": "附件资料",
        }.get(section_id, "资料")


__all__ = [
    "MaterialPersistenceCoordinator",
    "MaterialPersistencePort",
]
