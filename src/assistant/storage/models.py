"""Serializable assistant session aggregate and list projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from src.assistant.contracts.jobs import validate_document_job_transition
from src.assistant.contracts.messages import AssistantMessage
from src.assistant.contracts.serialization import plain_data

ASSISTANT_SESSION_SCHEMA_VERSION = "form-assistant-session-v1"
ASSISTANT_SESSION_SUMMARY_SCHEMA_VERSION = "form-assistant-session-summary-v1"
ASSISTANT_SESSION_ICON_NAMES = frozenset(
    {
        "message-circle",
        "file-text",
        "chart-no-axes-gantt",
        "alert-triangle",
        "circle-check",
    }
)


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
    activity_at: str = ""
    has_draft: bool = False
    preview: str = ""
    turn_count: int = 0
    unread: bool = False
    icon_name: str = "message-circle"
    sidebar_order: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ASSISTANT_SESSION_SUMMARY_SCHEMA_VERSION,
            "session_id": self.session_id,
            "title": self.title,
            "updated_at": self.updated_at,
            "pinned": self.pinned,
            "turn_status": self.turn_status,
            "document_job_status": self.document_job_status,
            "corrupt": self.corrupt,
            "recovery_path": self.recovery_path,
            "activity_at": self.activity_at,
            "has_draft": self.has_draft,
            "preview": self.preview,
            "turn_count": self.turn_count,
            "unread": self.unread,
            "icon_name": self.icon_name,
            "sidebar_order": self.sidebar_order,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AssistantSessionSummary:
        if (
            str(value.get("schema_version") or "")
            != ASSISTANT_SESSION_SUMMARY_SCHEMA_VERSION
        ):
            raise ValueError("Unsupported assistant session summary schema")
        session_id = str(value.get("session_id") or "").strip()
        updated_at = str(value.get("updated_at") or "").strip()
        if not session_id or not updated_at:
            raise ValueError("Assistant session summary identity is required")
        return cls(
            session_id=session_id,
            title=str(value.get("title") or "新对话"),
            updated_at=updated_at,
            pinned=bool(value.get("pinned", False)),
            turn_status=str(value.get("turn_status") or ""),
            document_job_status=str(value.get("document_job_status") or ""),
            corrupt=bool(value.get("corrupt", False)),
            recovery_path=str(value.get("recovery_path") or ""),
            activity_at=str(value.get("activity_at") or updated_at),
            has_draft=bool(value.get("has_draft", False)),
            preview=str(value.get("preview") or ""),
            turn_count=max(0, _optional_int(value.get("turn_count")) or 0),
            unread=bool(value.get("unread", False)),
            icon_name=str(value.get("icon_name") or "message-circle"),
            sidebar_order=_optional_int(value.get("sidebar_order")),
        )


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
    activity_at: str = ""
    unread: bool = False
    icon_name: str = "message-circle"
    sidebar_order: int | None = None

    def __post_init__(self) -> None:
        if not self.session_id or not self.created_at or not self.updated_at:
            raise ValueError("Assistant session identity and timestamps are required")
        if not self.activity_at:
            object.__setattr__(self, "activity_at", self.updated_at)
        if self.icon_name not in ASSISTANT_SESSION_ICON_NAMES:
            object.__setattr__(self, "icon_name", "message-circle")
        if self.sidebar_order is not None and self.sidebar_order < 0:
            object.__setattr__(self, "sidebar_order", None)
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
            "activity_at": self.activity_at,
            "unread": self.unread,
            "icon_name": self.icon_name,
            "sidebar_order": self.sidebar_order,
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
    def from_dict(cls, value: Mapping[str, Any]) -> AssistantSession:
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
            activity_at=str(
                value.get("activity_at")
                or value.get("updated_at")
                or value.get("created_at")
                or ""
            ),
            unread=bool(value.get("unread", False)),
            icon_name=str(value.get("icon_name") or "message-circle"),
            sidebar_order=_optional_int(value.get("sidebar_order")),
        )

    def summary(self) -> AssistantSessionSummary:
        preview = ""
        for message in reversed(self.messages):
            candidate = " ".join(message.visible_text().split())
            if candidate:
                preview = (
                    f"{candidate[:77]}…"
                    if len(candidate) > 78
                    else candidate
                )
                break
        return AssistantSessionSummary(
            session_id=self.session_id,
            title=self.title,
            updated_at=self.updated_at,
            pinned=self.pinned,
            turn_status=self.turn_status,
            document_job_status=str(self.document_job.get("status") or ""),
            activity_at=self.activity_at,
            has_draft=bool(self.draft_text.strip()),
            preview=preview,
            turn_count=sum(
                1 for message in self.messages if message.role == "user"
            ),
            unread=self.unread,
            icon_name=self.icon_name,
            sidebar_order=self.sidebar_order,
        )


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


__all__ = [
    "ASSISTANT_SESSION_ICON_NAMES",
    "ASSISTANT_SESSION_SCHEMA_VERSION",
    "ASSISTANT_SESSION_SUMMARY_SCHEMA_VERSION",
    "AssistantSession",
    "AssistantSessionSummary",
]
