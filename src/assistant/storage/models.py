"""Serializable assistant session aggregate and list projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from src.assistant.contracts.jobs import validate_document_job_transition
from src.assistant.contracts.messages import AssistantMessage
from src.assistant.contracts.serialization import plain_data


ASSISTANT_SESSION_SCHEMA_VERSION = "form-assistant-session-v1"


@dataclass(frozen=True, slots=True)
class AssistantSessionSummary:
    session_id: str
    title: str
    updated_at: str
    pinned: bool = False
    turn_status: str = ""
    document_job_status: str = ""
    corrupt: bool = False
    recovery_path: str = ""


@dataclass(frozen=True, slots=True)
class AssistantSession:
    session_id: str
    title: str
    created_at: str
    updated_at: str
    messages: tuple[AssistantMessage, ...] = ()
    draft_text: str = ""
    pinned: bool = False
    provider_profile_id: str = "mock-default"
    model_id: str = "form-assistant-mock"
    active_plan: Mapping[str, Any] = field(default_factory=dict)
    pending_continuation: Mapping[str, Any] = field(default_factory=dict)
    document_job: Mapping[str, Any] = field(default_factory=dict)
    provider_history_grant: Mapping[str, Any] = field(default_factory=dict)
    context_refs: tuple[dict[str, Any], ...] = ()
    turn_status: str = ""

    def __post_init__(self) -> None:
        if not self.session_id or not self.created_at or not self.updated_at:
            raise ValueError("Assistant session identity and timestamps are required")
        if not all(isinstance(item, AssistantMessage) for item in self.messages):
            raise TypeError("Assistant session messages must be AssistantMessage values")
        for name in (
            "active_plan",
            "pending_continuation",
            "document_job",
            "provider_history_grant",
        ):
            object.__setattr__(self, name, dict(plain_data(getattr(self, name))))
        validate_document_job_transition(
            "",
            str(self.document_job.get("status") or ""),
        )
        normalized_refs = plain_data(self.context_refs)
        object.__setattr__(self, "context_refs", tuple(dict(item) for item in normalized_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ASSISTANT_SESSION_SCHEMA_VERSION,
            "contract_kind": "assistant_session",
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [message.to_dict() for message in self.messages],
            "draft_text": self.draft_text,
            "pinned": self.pinned,
            "provider_profile_id": self.provider_profile_id,
            "model_id": self.model_id,
            "active_plan": dict(self.active_plan),
            "pending_continuation": dict(self.pending_continuation),
            "document_job": dict(self.document_job),
            "provider_history_grant": dict(self.provider_history_grant),
            "context_refs": [dict(item) for item in self.context_refs],
            "turn_status": self.turn_status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AssistantSession":
        schema = str(value.get("schema_version") or "")
        if schema != ASSISTANT_SESSION_SCHEMA_VERSION:
            raise ValueError(f"Unsupported assistant session schema: {schema!r}")
        if str(value.get("contract_kind") or "") != "assistant_session":
            raise ValueError("Not an assistant_session payload")
        raw_messages = value.get("messages")
        if not isinstance(raw_messages, (list, tuple)):
            raise TypeError("Assistant session messages must be a list")
        raw_refs = value.get("context_refs", ())
        if not isinstance(raw_refs, (list, tuple)):
            raise TypeError("Assistant session context_refs must be a list")
        return cls(
            session_id=str(value.get("session_id") or ""),
            title=str(value.get("title") or "新对话"),
            created_at=str(value.get("created_at") or ""),
            updated_at=str(value.get("updated_at") or ""),
            messages=tuple(
                AssistantMessage.from_dict(item)
                for item in raw_messages
                if isinstance(item, Mapping)
            ),
            draft_text=str(value.get("draft_text") or ""),
            pinned=bool(value.get("pinned", False)),
            provider_profile_id=str(value.get("provider_profile_id") or "mock-default"),
            model_id=str(value.get("model_id") or "form-assistant-mock"),
            active_plan=value.get("active_plan") if isinstance(value.get("active_plan"), Mapping) else {},
            pending_continuation=value.get("pending_continuation") if isinstance(value.get("pending_continuation"), Mapping) else {},
            document_job=value.get("document_job") if isinstance(value.get("document_job"), Mapping) else {},
            provider_history_grant=(
                value.get("provider_history_grant")
                if isinstance(value.get("provider_history_grant"), Mapping)
                else {}
            ),
            context_refs=tuple(dict(item) for item in raw_refs if isinstance(item, Mapping)),
            turn_status=str(value.get("turn_status") or ""),
        )

    def summary(self) -> AssistantSessionSummary:
        return AssistantSessionSummary(
            session_id=self.session_id,
            title=self.title,
            updated_at=self.updated_at,
            pinned=self.pinned,
            turn_status=self.turn_status,
            document_job_status=str(self.document_job.get("status") or ""),
        )


__all__ = [
    "ASSISTANT_SESSION_SCHEMA_VERSION",
    "AssistantSession",
    "AssistantSessionSummary",
]
