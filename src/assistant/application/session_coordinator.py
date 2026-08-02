"""Single durable source of truth for assistant sessions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.assistant.contracts.jobs import validate_document_job_transition
from src.assistant.contracts.messages import AssistantMessage, utc_now_text
from src.assistant.storage.models import (
    ASSISTANT_SESSION_ICON_NAMES,
    AssistantSession,
    AssistantSessionSummary,
)
from src.assistant.storage.session_store import AssistantSessionStore


class AssistantSessionCoordinator:
    def __init__(self, store: AssistantSessionStore | None = None) -> None:
        self.store = store or AssistantSessionStore()

    def list_sessions(self) -> tuple[AssistantSessionSummary, ...]:
        return self.store.list_summaries()

    def create_session(
        self,
        *,
        title: str = "新对话",
        provider_profile_id: str = "mock-default",
        model_id: str = "form-assistant-mock",
    ) -> AssistantSession:
        now = utc_now_text()
        session = AssistantSession(
            session_id=uuid4().hex,
            title=str(title or "新对话").strip() or "新对话",
            created_at=now,
            updated_at=now,
            provider_profile_id=provider_profile_id,
            model_id=model_id,
        )
        self.store.save(session)
        return session

    def load_session(self, session_id: str) -> AssistantSession:
        return self.store.load(session_id)

    def append_message(
        self,
        session: AssistantSession,
        message: AssistantMessage,
        *,
        turn_status: str | None = None,
        consume_draft: bool = False,
    ) -> AssistantSession:
        title = session.title
        if title == "新对话" and message.role == "user":
            title = self.title_from_text(message.visible_text())
        now = utc_now_text()
        updated = replace(
            session,
            title=title,
            updated_at=now,
            activity_at=now,
            messages=(*session.messages, message),
            turn_status=session.turn_status if turn_status is None else turn_status,
            draft_text="" if consume_draft else session.draft_text,
        )
        self.store.save(updated)
        return updated

    def stage_draft(self, session: AssistantSession, draft_text: str) -> AssistantSession:
        """Update the in-memory draft without forcing synchronous disk I/O."""

        now = utc_now_text()
        return replace(
            session,
            draft_text=str(draft_text or ""),
            updated_at=now,
            activity_at=now,
        )

    def persist(self, session: AssistantSession) -> AssistantSession:
        """Persist a draft snapshot without forcing a recoverable cache write."""

        self.store.save(session, update_summary_cache=False)
        return session

    def update_draft(self, session: AssistantSession, draft_text: str) -> AssistantSession:
        """Compatibility helper for callers that require an immediate draft save."""

        return self.persist(self.stage_draft(session, draft_text))

    def rename(self, session: AssistantSession, title: str) -> AssistantSession:
        normalized = str(title or "").strip()
        if not normalized:
            raise ValueError("Session title cannot be empty")
        updated = replace(session, title=normalized[:80], updated_at=utc_now_text())
        self.store.save(updated)
        return updated

    def set_pinned(self, session: AssistantSession, pinned: bool) -> AssistantSession:
        target_pinned = bool(pinned)
        summaries = tuple(
            summary for summary in self.list_sessions() if not summary.corrupt
        )
        if not any(summary.session_id == session.session_id for summary in summaries):
            raise ValueError("Assistant session is not present in the sidebar")
        pinned_ids = [
            summary.session_id
            for summary in summaries
            if summary.pinned and summary.session_id != session.session_id
        ]
        recent_ids = [
            summary.session_id
            for summary in summaries
            if not summary.pinned and summary.session_id != session.session_id
        ]
        target_ids = pinned_ids if target_pinned else recent_ids
        target_ids.insert(0, session.session_id)
        layout = _sidebar_layout(pinned_ids, recent_ids)
        self.store.save_sidebar_layout(layout)
        return replace(
            session,
            pinned=target_pinned,
            sidebar_order=layout[session.session_id][1],
        )

    def set_icon(
        self,
        session: AssistantSession,
        icon_name: str,
    ) -> AssistantSession:
        normalized = str(icon_name or "").strip()
        if normalized not in ASSISTANT_SESSION_ICON_NAMES:
            raise ValueError(f"Unsupported assistant session icon: {normalized!r}")
        updated = replace(
            session,
            icon_name=normalized,
            updated_at=utc_now_text(),
        )
        self.store.save(updated)
        return updated

    def set_unread(
        self,
        session: AssistantSession,
        unread: bool,
    ) -> AssistantSession:
        updated = replace(
            session,
            unread=bool(unread),
            updated_at=utc_now_text(),
        )
        self.store.save(updated)
        return updated

    def reorder_sessions(
        self,
        ordered_ids: Iterable[str],
        *,
        pinned: bool,
    ) -> tuple[AssistantSession, ...]:
        normalized = tuple(str(value or "").strip() for value in ordered_ids)
        if not normalized or any(not value for value in normalized):
            return ()
        if len(set(normalized)) != len(normalized):
            raise ValueError("Assistant session order contains duplicate IDs")
        summaries = tuple(
            summary for summary in self.list_sessions() if not summary.corrupt
        )
        expected = {
            summary.session_id
            for summary in summaries
            if summary.pinned == bool(pinned)
        }
        if set(normalized) != expected:
            raise ValueError("Assistant session order must cover one full section")
        pinned_ids = [
            summary.session_id
            for summary in summaries
            if summary.pinned
        ]
        recent_ids = [
            summary.session_id
            for summary in summaries
            if not summary.pinned
        ]
        if bool(pinned):
            pinned_ids = list(normalized)
        else:
            recent_ids = list(normalized)
        self.store.save_sidebar_layout(
            _sidebar_layout(pinned_ids, recent_ids)
        )
        return tuple(self.load_session(session_id) for session_id in normalized)

    def move_session_to_section(
        self,
        session_id: str,
        *,
        pinned: bool,
        target_index: int,
    ) -> tuple[AssistantSession, ...]:
        normalized_id = str(session_id or "").strip()
        summaries = tuple(
            summary for summary in self.list_sessions() if not summary.corrupt
        )
        if not normalized_id or not any(
            summary.session_id == normalized_id for summary in summaries
        ):
            raise ValueError("Assistant session is not present in the sidebar")
        pinned_ids = [
            summary.session_id
            for summary in summaries
            if summary.pinned and summary.session_id != normalized_id
        ]
        recent_ids = [
            summary.session_id
            for summary in summaries
            if not summary.pinned and summary.session_id != normalized_id
        ]
        target_ids = pinned_ids if bool(pinned) else recent_ids
        insertion = max(0, min(int(target_index), len(target_ids)))
        target_ids.insert(insertion, normalized_id)
        layout = _sidebar_layout(pinned_ids, recent_ids)
        self.store.save_sidebar_layout(layout)
        ordered_ids = (*pinned_ids, *recent_ids)
        return tuple(self.load_session(value) for value in ordered_ids)

    def update_state(
        self,
        session: AssistantSession,
        *,
        active_plan: Mapping[str, Any] | None = None,
        pending_continuation: Mapping[str, Any] | None = None,
        document_job: Mapping[str, Any] | None = None,
        provider_history_grant: Mapping[str, Any] | None = None,
        context_refs: tuple[dict[str, Any], ...] | None = None,
        turn_status: str | None = None,
        provider_profile_id: str | None = None,
        model_id: str | None = None,
        consume_draft: bool = False,
        touch_activity: bool = True,
    ) -> AssistantSession:
        next_document_job = (
            session.document_job
            if document_job is None
            else dict(document_job)
        )
        if document_job is not None:
            validate_document_job_transition(
                str(session.document_job.get("status") or ""),
                str(next_document_job.get("status") or ""),
            )
        now = utc_now_text()
        updated = replace(
            session,
            updated_at=now,
            activity_at=now if touch_activity else session.activity_at,
            active_plan=(session.active_plan if active_plan is None else active_plan),
            pending_continuation=(
                session.pending_continuation
                if pending_continuation is None
                else pending_continuation
            ),
            document_job=next_document_job,
            provider_history_grant=(
                session.provider_history_grant
                if provider_history_grant is None
                else provider_history_grant
            ),
            context_refs=(session.context_refs if context_refs is None else context_refs),
            turn_status=(session.turn_status if turn_status is None else turn_status),
            provider_profile_id=(
                session.provider_profile_id
                if provider_profile_id is None
                else provider_profile_id
            ),
            model_id=session.model_id if model_id is None else model_id,
            draft_text="" if consume_draft else session.draft_text,
        )
        self.store.save(updated)
        return updated

    def delete_session(self, session_id: str) -> bool:
        return self.store.delete(session_id)

    def quarantine_corrupt_session(self, recovery_path: str) -> Path:
        return self.store.quarantine_corrupt(recovery_path)

    @staticmethod
    def title_from_text(text: str) -> str:
        normalized = " ".join(str(text or "").split())
        return (normalized[:32] + "…") if len(normalized) > 32 else (normalized or "新对话")


def _sidebar_layout(
    pinned_ids: Iterable[str],
    recent_ids: Iterable[str],
) -> dict[str, tuple[bool, int]]:
    return {
        **{
            session_id: (True, index)
            for index, session_id in enumerate(pinned_ids)
        },
        **{
            session_id: (False, index)
            for index, session_id in enumerate(recent_ids)
        },
    }


__all__ = ["AssistantSessionCoordinator"]
