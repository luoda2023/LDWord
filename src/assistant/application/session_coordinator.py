"""Single durable source of truth for assistant sessions."""

from __future__ import annotations

from dataclasses import replace
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from src.assistant.contracts.jobs import validate_document_job_transition
from src.assistant.contracts.messages import AssistantMessage, utc_now_text
from src.assistant.storage.models import AssistantSession, AssistantSessionSummary
from src.assistant.storage.session_store import AssistantSessionStore


class AssistantSessionCoordinator:
    def __init__(self, store: AssistantSessionStore | None = None) -> None:
        self.store = store or AssistantSessionStore()

    def list_sessions(self) -> tuple[AssistantSessionSummary, ...]:
        summaries = self.store.list_summaries()
        return tuple(
            sorted(
                summaries,
                key=lambda item: (item.pinned, item.updated_at),
                reverse=True,
            )
        )

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
    ) -> AssistantSession:
        title = session.title
        if title == "新对话" and message.role == "user":
            title = self.title_from_text(message.visible_text())
        updated = replace(
            session,
            title=title,
            updated_at=utc_now_text(),
            messages=(*session.messages, message),
            turn_status=session.turn_status if turn_status is None else turn_status,
        )
        self.store.save(updated)
        return updated

    def update_draft(self, session: AssistantSession, draft_text: str) -> AssistantSession:
        updated = replace(session, draft_text=str(draft_text or ""), updated_at=utc_now_text())
        self.store.save(updated)
        return updated

    def rename(self, session: AssistantSession, title: str) -> AssistantSession:
        normalized = str(title or "").strip()
        if not normalized:
            raise ValueError("Session title cannot be empty")
        updated = replace(session, title=normalized[:80], updated_at=utc_now_text())
        self.store.save(updated)
        return updated

    def set_pinned(self, session: AssistantSession, pinned: bool) -> AssistantSession:
        updated = replace(session, pinned=bool(pinned), updated_at=utc_now_text())
        self.store.save(updated)
        return updated

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
        updated = replace(
            session,
            updated_at=utc_now_text(),
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
        )
        self.store.save(updated)
        return updated

    def delete_session(self, session_id: str) -> bool:
        return self.store.delete(session_id)

    @staticmethod
    def title_from_text(text: str) -> str:
        normalized = " ".join(str(text or "").split())
        return (normalized[:32] + "…") if len(normalized) > 32 else (normalized or "新对话")


__all__ = ["AssistantSessionCoordinator"]
