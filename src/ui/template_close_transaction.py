"""Two-phase close transaction for template drafts.

The transaction owns prepared-close state, file backups, and rollback order.
The host panel keeps user prompts and UI projection hooks so this coordinator
does not become a second template editor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from src.shared.ui import Toast
from src.ui.template_draft_save_coordinator import PreparedTemplateSave
from src.ui.template_edit_session import (
    TemplateDraftContext,
    TemplateDraftStore,
    TemplateDraftStoreState,
)


TEMPLATE_EDIT_SAVE = "save"
TEMPLATE_EDIT_DISCARD = "discard"
TEMPLATE_EDIT_CANCEL = "cancel"


class TemplateSaveCancelled(Exception):
    """Internal control flow for a user-cancelled template save."""


@dataclass(frozen=True, slots=True)
class _TemplateFileBackup:
    target: Path
    existed: bool
    payload: bytes


@dataclass(frozen=True, slots=True)
class _TemplateCloseSnapshot:
    """Recoverable state retained until the whole-window close is final."""

    draft_store: TemplateDraftStoreState
    active_context: TemplateDraftContext
    current_template_id: str
    current_template_path: str
    current_template_source: str
    current_template_source_type: str
    bridge_state: object
    files: tuple[_TemplateFileBackup, ...]


class TemplateCloseHost(Protocol):
    """Panel surface required by :class:`TemplateCloseTransaction`."""

    bridge: Any
    _draft_store: TemplateDraftStore
    _draft_context: TemplateDraftContext
    _edit_session: Any
    _current_template_id: str
    _current_template_path: str
    _current_template_source: str
    _current_template_source_type: str
    _current_template: Any

    def _prompt_close_template_draft_action(self, count: int) -> str: ...

    def _prepare_draft_context_saves(
        self,
        contexts: tuple[TemplateDraftContext, ...],
        *,
        confirm_shared: bool,
        path: str | Path | None = None,
    ) -> tuple[PreparedTemplateSave, ...]: ...

    def _execute_prepared_template_saves(
        self,
        plans: tuple[PreparedTemplateSave, ...],
    ) -> tuple[TemplateDraftContext, ...]: ...

    def _finalize_saved_template_contexts(
        self,
        contexts: tuple[TemplateDraftContext, ...],
    ) -> None: ...

    def _discard_all_pending_template_edits(self) -> None: ...

    def _set_detail_templates(self, template: Any) -> None: ...

    def _set_detail_save_enabled(self, enabled: bool) -> None: ...

    def _refresh_template_selector_options(self) -> None: ...

    def _sync_template_file_status(self) -> None: ...

    def _refresh_overview_projection(self, *, reason: str) -> None: ...


class TemplateCloseTransaction:
    """Prepare, commit, roll back, and finalize one template close decision."""

    def __init__(self, host: TemplateCloseHost) -> None:
        self._host = host
        self._action = ""
        self._plans: tuple[PreparedTemplateSave, ...] = ()
        self._snapshot: _TemplateCloseSnapshot | None = None
        self._committed = False
        self._files_published = False
        self._restoring_snapshot = False

    @property
    def is_restoring_snapshot(self) -> bool:
        return self._restoring_snapshot

    def prepare(self) -> bool:
        """Collect the close decision and validate it without writing files."""

        self.cancel()
        dirty_contexts = tuple(self._host._draft_store.dirty_contexts())
        if not dirty_contexts:
            return True
        action = self._host._prompt_close_template_draft_action(
            len(dirty_contexts)
        )
        if action == TEMPLATE_EDIT_SAVE:
            try:
                self._plans = self._host._prepare_draft_context_saves(
                    dirty_contexts,
                    confirm_shared=True,
                )
            except TemplateSaveCancelled:
                return False
            except Exception as exc:
                Toast.show_error(f"无法准备模板草稿保存: {exc}")
                return False
            self._action = TEMPLATE_EDIT_SAVE
            try:
                self._snapshot = self._capture_snapshot(self._plans)
            except OSError as exc:
                Toast.show_error(f"无法准备模板关闭事务: {exc}")
                self.cancel()
                return False
            return True
        if action == TEMPLATE_EDIT_DISCARD:
            self._action = TEMPLATE_EDIT_DISCARD
            try:
                self._snapshot = self._capture_snapshot()
            except OSError as exc:
                Toast.show_error(f"无法准备模板关闭事务: {exc}")
                self.cancel()
                return False
            return True
        return False

    def commit(self) -> bool:
        """Apply the already accepted close decision."""

        if self._committed:
            return True
        if not self._action:
            return not self._host._draft_store.dirty_contexts()
        snapshot = self._snapshot
        if snapshot is None:
            return False
        try:
            if self._action == TEMPLATE_EDIT_SAVE:
                if not self._commit_prepared_saves(self._plans):
                    self._restore_snapshot(
                        snapshot,
                        # Preparation/revision failures publish no files. In
                        # particular, do not overwrite a target changed after
                        # the close decision was accepted.
                        restore_files=False,
                    )
                    self.cancel()
                    return False
            elif self._action == TEMPLATE_EDIT_DISCARD:
                self._host._discard_all_pending_template_edits()
            else:
                return False
        except Exception as exc:
            rollback_succeeded = False
            try:
                self._restore_snapshot(
                    snapshot,
                    restore_files=self._files_published,
                )
            except Exception as rollback_exc:
                Toast.show_error(
                    f"模板关闭事务失败，且回滚失败: {rollback_exc}"
                )
            else:
                rollback_succeeded = True
                Toast.show_error(f"模板关闭事务失败，已恢复草稿: {exc}")
            if rollback_succeeded:
                self._clear()
            return False
        self._committed = True
        return True

    def rollback(self) -> bool:
        snapshot = self._snapshot
        if snapshot is None:
            return True
        try:
            self._restore_snapshot(
                snapshot,
                restore_files=(
                    self._files_published
                    and self._action == TEMPLATE_EDIT_SAVE
                ),
            )
        except Exception as exc:
            Toast.show_error(f"恢复模板草稿失败: {exc}")
            return False
        self._clear()
        return True

    def finalize(self) -> None:
        self._clear()

    def cancel(self) -> None:
        if not self._committed:
            self._clear()

    def _commit_prepared_saves(
        self,
        plans: tuple[PreparedTemplateSave, ...],
    ) -> bool:
        try:
            contexts = self._host._execute_prepared_template_saves(plans)
        except TemplateSaveCancelled:
            Toast.show_warning(
                "模板文件在确认后再次发生变化，未写入任何草稿"
            )
            return False
        except Exception as exc:
            Toast.show_error(
                f"保存模板草稿失败，已回滚本批次写入: {exc}"
            )
            return False
        self._files_published = True
        self._host._finalize_saved_template_contexts(contexts)
        Toast.show_success(f"已保存 {len(contexts)} 个模板草稿")
        return True

    def _capture_snapshot(
        self,
        plans: tuple[PreparedTemplateSave, ...] = (),
    ) -> _TemplateCloseSnapshot:
        backups: list[_TemplateFileBackup] = []
        for plan in plans:
            target = Path(plan.target)
            existed = target.is_file()
            payload = target.read_bytes() if existed else b""
            backups.append(
                _TemplateFileBackup(
                    target=target,
                    existed=existed,
                    payload=payload,
                )
            )
        host = self._host
        return _TemplateCloseSnapshot(
            draft_store=host._draft_store.capture_state(),
            active_context=host._draft_context,
            current_template_id=host._current_template_id,
            current_template_path=host._current_template_path,
            current_template_source=host._current_template_source,
            current_template_source_type=host._current_template_source_type,
            bridge_state=host.bridge.capture_state_snapshot(),
            files=tuple(backups),
        )

    @staticmethod
    def _restore_files(
        backups: tuple[_TemplateFileBackup, ...],
    ) -> None:
        for backup in backups:
            target = backup.target
            if not backup.existed:
                if target.exists():
                    target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            stage = target.with_name(
                f".{target.name}.rollback-{uuid4().hex}.tmp"
            )
            try:
                stage.write_bytes(backup.payload)
                os.replace(stage, target)
            finally:
                if stage.exists():
                    stage.unlink()

    def _restore_snapshot(
        self,
        snapshot: _TemplateCloseSnapshot,
        *,
        restore_files: bool,
    ) -> None:
        if restore_files:
            self._restore_files(snapshot.files)

        host = self._host
        host._draft_store.restore_state(snapshot.draft_store)
        host._draft_context = snapshot.active_context
        host._edit_session = snapshot.active_context.session
        host._current_template_id = snapshot.current_template_id
        host._current_template_path = snapshot.current_template_path
        host._current_template_source = snapshot.current_template_source
        host._current_template_source_type = (
            snapshot.current_template_source_type
        )
        host._current_template = host._edit_session.draft

        self._restoring_snapshot = True
        try:
            # Restore authoritative state before any projection can observe it.
            host.bridge.restore_state_snapshot(
                snapshot.bridge_state,
                emit_signal=False,
            )
            host._set_detail_templates(host._current_template)
            host._set_detail_save_enabled(host._edit_session.is_dirty())
            host._refresh_template_selector_options()
            host._sync_template_file_status()
            host._refresh_overview_projection(
                reason="template_close_rolled_back"
            )
            # Notify other panels only after this panel is internally coherent.
            host.bridge.restore_state_snapshot(
                snapshot.bridge_state,
                emit_signal=True,
            )
        finally:
            self._restoring_snapshot = False

    def _clear(self) -> None:
        self._action = ""
        self._plans = ()
        self._snapshot = None
        self._committed = False
        self._files_published = False


__all__ = [
    "TEMPLATE_EDIT_CANCEL",
    "TEMPLATE_EDIT_DISCARD",
    "TEMPLATE_EDIT_SAVE",
    "TemplateCloseTransaction",
    "TemplateSaveCancelled",
]
