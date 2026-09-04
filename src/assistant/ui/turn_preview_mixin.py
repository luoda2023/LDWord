"""Streaming preview and attachment context behavior for assistant turns."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from src.assistant.adapters.workspace_state_adapter import (
    WorkspaceSnapshot,
    snapshot_workspace,
)
from src.assistant.contracts.permissions import DisclosureGrant
from src.assistant.domain.docx_format_evidence import attachment_disclosure_fields
from src.assistant.runtime.events import (
    EVENT_CONTEXT_READY,
    EVENT_MODEL_STARTED,
    EVENT_TEXT_DELTA,
    EVENT_TURN_CANCELLED,
    EVENT_TURN_FAILED,
    EVENT_TURN_FINISHED,
    EVENT_TURN_STARTED,
    EVENT_TURN_WAITING,
)
from src.assistant.runtime.turn_runner import attachment_fingerprints
from src.assistant.storage.models import AssistantSession
from src.assistant.ui.workers import AssistantTurnWorker
from src.qt_api import QTimer

_ASSISTANT_ATTACHMENT_MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".wps": "application/vnd.ms-works",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


class AssistantTurnPreviewMixin:
    def _start_turn_preview(self, *, session_id: str, turn_id: str) -> None:
        normalized_session_id = str(session_id or "")
        self._turn_previews[normalized_session_id] = {
            "turn_id": str(turn_id or ""),
            "text": "",
            "status": "正在准备请求",
            "pending_delta": [],
        }
        self._activate_turn_preview(normalized_session_id)

    def _context_refs_for_submission(self) -> tuple[dict[str, object], ...]:
        """Freeze explicitly selected local material into this turn and message."""

        if self._active_session is not None and self._active_session.context_refs:
            valid_refs: list[dict[str, object]] = []
            for reference in self._active_session.context_refs:
                path_text = str(reference.get("path") or "").strip()
                if path_text and Path(path_text).expanduser().is_file():
                    valid_refs.append(dict(reference))
            return tuple(valid_refs)
        composer = (
            self._composer
            if self._conversation_stack.currentWidget() is self._active_page
            else self._empty_input
        )
        return self._context_refs_for_paths(composer.document_paths())

    def _missing_context_refs_for_submission(
        self,
        context_refs: tuple[dict[str, object], ...] | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Return explicitly selected attachment refs that no longer exist."""

        candidates: list[dict[str, object]] = []
        if context_refs is not None:
            candidates.extend(dict(reference) for reference in context_refs)
        elif self._active_session is not None and self._active_session.context_refs:
            candidates.extend(
                dict(reference)
                for reference in self._active_session.context_refs
                if isinstance(reference, Mapping)
            )
        else:
            composer = (
                self._composer
                if self._conversation_stack.currentWidget()
                is self._active_page
                else self._empty_input
            )
            candidates.extend(
                {
                    "path": path_text,
                    "name": Path(path_text).name,
                }
                for path_text in composer.document_paths()
                if str(path_text or "").strip()
            )
        return tuple(
            reference
            for reference in candidates
            if (
                str(reference.get("path") or "").strip()
                and not Path(
                    str(reference.get("path") or "")
                ).expanduser().is_file()
            )
        )

    @staticmethod
    def _context_refs_for_path(path_text: str) -> tuple[dict[str, object], ...]:
        return AssistantTurnPreviewMixin._context_refs_for_paths((path_text,))

    @staticmethod
    def _context_refs_for_paths(
        path_texts: tuple[str, ...],
    ) -> tuple[dict[str, object], ...]:
        refs: list[dict[str, object]] = []
        identities: set[str] = set()
        for path_text in tuple(path_texts or ()):
            reference = AssistantTurnPreviewMixin._context_ref_for_path(path_text)
            if reference is None:
                continue
            identity = str(reference["path"]).casefold()
            if identity in identities:
                continue
            identities.add(identity)
            refs.append(reference)
        return tuple(refs)

    @staticmethod
    def _context_ref_for_path(path_text: str) -> dict[str, object] | None:
        normalized = str(path_text or "").strip()
        if not normalized:
            return None
        path = Path(normalized).expanduser()
        media_type = _ASSISTANT_ATTACHMENT_MEDIA_TYPES.get(path.suffix.casefold())
        if not path.is_file() or media_type is None:
            return None
        return {
            "type": "file",
            "source_type": "attachment",
            "title": path.name,
            "path": str(path.resolve()),
            "media_type": media_type,
        }

    @staticmethod
    def _disclosure_grant_for_turn(
        session: AssistantSession,
        context_refs: tuple[dict[str, object], ...],
    ) -> DisclosureGrant | None:
        if not context_refs:
            return None
        ref_ids = tuple(str(item.get("path") or "") for item in context_refs)
        return DisclosureGrant(
            grant_id=uuid4().hex,
            session_id=session.session_id,
            provider_id=session.provider_profile_id,
            model_id=session.model_id,
            allowed_refs=ref_ids,
            allowed_fields=attachment_disclosure_fields(context_refs),
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(
                datetime.now(timezone.utc) + timedelta(minutes=10)
            ).isoformat(),
            scope="once",
            content_fingerprints=attachment_fingerprints(context_refs),
        )

    def _workspace_snapshot_for_session(
        self,
        session: AssistantSession,
    ) -> WorkspaceSnapshot:
        live = snapshot_workspace(self.bridge)
        path_text = ""
        for reference in session.context_refs:
            path_text = str(reference.get("path") or "").strip()
            if path_text:
                break
        if not path_text:
            return replace(
                live,
                input_path="",
                input_name="",
                input_exists=False,
            )
        path = Path(path_text).expanduser()
        return replace(
            live,
            input_path=str(path.resolve()) if path.exists() else str(path),
            input_name=path.name,
            input_exists=path.is_file(),
        )

    def _activate_turn_preview(self, session_id: str) -> None:
        normalized = str(session_id or "")
        state = self._turn_previews.get(normalized)
        if state is None:
            self._turn_preview_session_id = ""
            self._turn_preview_turn_id = ""
            self._turn_preview_text = ""
            self._turn_preview_status = ""
        else:
            self._materialize_turn_preview_state(state)
            self._turn_preview_session_id = normalized
            self._turn_preview_turn_id = str(state["turn_id"])
            self._turn_preview_text = str(state["text"])
            self._turn_preview_status = str(state["status"])
        self._turn_preview_widget = None

    @staticmethod
    def _materialize_turn_preview_state(state: dict[str, object]) -> str:
        pending = state.get("pending_delta")
        if not isinstance(pending, list) or not pending:
            return ""
        delta = "".join(str(part) for part in pending)
        pending.clear()
        state["text"] = f"{state.get('text', '')}{delta}"
        return delta

    def _clear_turn_preview(self, session_id: str = "") -> None:
        normalized = str(session_id or self._turn_preview_session_id or "")
        if normalized:
            self._turn_previews.pop(normalized, None)
        if normalized == self._turn_preview_session_id:
            self._turn_preview_flush_timer.stop()
        current_session_id = (
            self._active_session.session_id
            if self._active_session is not None
            else ""
        )
        if not normalized or normalized == current_session_id:
            self._activate_turn_preview(current_session_id)

    def _on_turn_event(self, worker: AssistantTurnWorker | object, event=None) -> None:
        if event is None:
            event = worker
            worker = self._turn_worker
        session_id = (
            worker.request.session_id
            if isinstance(worker, AssistantTurnWorker)
            else self._turn_preview_session_id
        )
        state = self._turn_previews.get(session_id)
        if (
            state is None
            or str(getattr(event, "turn_id", "") or "")
            != str(state["turn_id"])
        ):
            return
        event_type = str(getattr(event, "type", "") or "")
        template_authoring = bool(
            isinstance(worker, AssistantTurnWorker)
            and worker.request.template_authoring_mode_id
        )
        status_by_type = {
            EVENT_TURN_STARTED: "正在理解你的要求",
            EVENT_CONTEXT_READY: "已整理当前文档上下文",
            EVENT_MODEL_STARTED: "模型正在生成",
            EVENT_TEXT_DELTA: "正在生成回复",
            EVENT_TURN_FINISHED: "回复生成完成",
            EVENT_TURN_FAILED: "模型响应未完成",
            EVENT_TURN_CANCELLED: "正在停止",
            EVENT_TURN_WAITING: "需要你的确认或补充",
        }
        if event_type == EVENT_TEXT_DELTA:
            delta = str(getattr(event, "text_delta", "") or "")
            if delta and not template_authoring:
                pending = state.setdefault("pending_delta", [])
                if isinstance(pending, list):
                    pending.append(delta)
        state["status"] = status_by_type.get(
            event_type,
            str(state["status"]) or "正在处理",
        )
        if template_authoring and event_type in {
            EVENT_MODEL_STARTED,
            EVENT_TEXT_DELTA,
        }:
            state["status"] = "正在生成并校验模板配置"
        if (
            self._active_session is None
            or self._active_session.session_id != session_id
        ):
            return
        if not self._turn_preview_flush_timer.isActive():
            self._turn_preview_flush_timer.start()

    def _flush_active_turn_preview(self) -> None:
        session = self._active_session
        if session is None:
            return
        session_id = session.session_id
        state = self._turn_previews.get(session_id)
        if state is None:
            return
        delta = self._materialize_turn_preview_state(state)
        self._turn_preview_session_id = session_id
        self._turn_preview_turn_id = str(state["turn_id"])
        self._turn_preview_text = str(state["text"])
        self._turn_preview_status = str(state["status"])
        if self._turn_preview_widget is None:
            self._render_active_session()
            return
        follow_output = self._is_near_latest()
        self._turn_preview_widget.append_live_delta(
            delta=delta,
            status_text=self._turn_preview_status,
        )
        if follow_output:
            self._schedule_stream_scroll_to_bottom()

    def _schedule_stream_scroll_to_bottom(self) -> None:
        if self._scroll_update_pending:
            return
        self._scroll_update_pending = True
        QTimer.singleShot(0, self._flush_stream_scroll_to_bottom)

    def _flush_stream_scroll_to_bottom(self) -> None:
        self._scroll_update_pending = False
        self._begin_follow_latest_layout_settle()

    def _finish_turn_ui(self, worker: AssistantTurnWorker) -> None:
        session_id = worker.request.session_id
        if self._turn_workers.get(session_id) is worker:
            self._turn_workers.pop(session_id, None)
        worker.deleteLater()
        self._sync_turn_worker_alias()
        self._clear_turn_preview(session_id)
        self._sync_composer_busy_state()
        if (
            (self._content_worker is None or not self._content_worker.is_running)
            and (self._preflight_worker is None or not self._preflight_worker.is_running)
            and (self._execution_worker is None or not self._execution_worker.is_running)
        ):
            self._stop_button.setVisible(False)

    def cancel_active_turn(self) -> None:
        if self._turn_worker is not None:
            self._turn_worker.cancel()
        current_session_id = (
            self._active_session.session_id
            if self._active_session is not None
            else ""
        )
        if self._content_worker is not None and self._worker_session_id(self._content_worker) == current_session_id:
            self._content_worker.cancel()
        if self._preflight_worker is not None and self._worker_session_id(self._preflight_worker) == current_session_id:
            self._preflight_worker.cancel()
        if self._execution_worker is not None and self._worker_session_id(self._execution_worker) == current_session_id:
            self._execution_worker.cancel()

__all__ = ["AssistantTurnPreviewMixin"]
