"""Typed boundary between provider/tool runtime and Form application."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from src.assistant.contracts.messages import AssistantMessage
from src.assistant.contracts.serialization import mapping_tuple, plain_data, text_tuple


ASSISTANT_RUNTIME_RESULT_SCHEMA_VERSION = "form-assistant-runtime-result-v1"
ASSISTANT_TURN_REQUEST_SCHEMA_VERSION = "form-assistant-turn-request-v1"
MAX_ASSISTANT_USER_MESSAGE_CHARACTERS = 32_000
MAX_ASSISTANT_HISTORY_CHARACTERS = 80_000

TURN_STARTED = "started"
TURN_CONTEXT_READY = "context_ready"
TURN_PROVIDER_RUNNING = "provider_running"
TURN_WAITING_USER_QUESTION = "waiting_user_question"
TURN_WAITING_DATA_PERMISSION = "waiting_data_permission"
TURN_WAITING_TOOL_PERMISSION = "waiting_tool_permission"
TURN_BLOCKED = "blocked"
TURN_FAILED = "failed"
TURN_CANCELLED = "cancelled"
TURN_COMPLETED = "completed"

TURN_STATUSES = frozenset(
    {
        TURN_STARTED,
        TURN_CONTEXT_READY,
        TURN_PROVIDER_RUNNING,
        TURN_WAITING_USER_QUESTION,
        TURN_WAITING_DATA_PERMISSION,
        TURN_WAITING_TOOL_PERMISSION,
        TURN_BLOCKED,
        TURN_FAILED,
        TURN_CANCELLED,
        TURN_COMPLETED,
    }
)


@dataclass(frozen=True, slots=True)
class AssistantTurnRequest:
    turn_id: str
    session_id: str
    user_message: str
    provider_profile_id: str
    model_id: str
    history: tuple[AssistantMessage, ...] = ()
    local_context_refs: tuple[dict[str, Any], ...] = ()
    disclosure_grant_id: str = ""
    disclosure_grant: Mapping[str, Any] = field(default_factory=dict)
    history_disclosure_grant: Mapping[str, Any] = field(default_factory=dict)
    conversation_cursor: str = ""
    template_authoring_mode_id: str = ""
    template_authoring_strategy: str = ""

    def __post_init__(self) -> None:
        for name in ("turn_id", "session_id", "provider_profile_id", "model_id"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"Assistant turn {name} is required")
        if not str(self.user_message or "").strip():
            raise ValueError("Assistant turn user_message is required")
        if not all(isinstance(item, AssistantMessage) for item in self.history):
            raise TypeError("Assistant turn history must contain AssistantMessage values")
        object.__setattr__(self, "user_message", str(self.user_message).strip())
        object.__setattr__(self, "history", tuple(self.history))
        object.__setattr__(self, "local_context_refs", mapping_tuple(self.local_context_refs))
        object.__setattr__(
            self,
            "disclosure_grant",
            dict(plain_data(self.disclosure_grant)),
        )
        object.__setattr__(
            self,
            "history_disclosure_grant",
            dict(plain_data(self.history_disclosure_grant)),
        )
        object.__setattr__(
            self,
            "template_authoring_mode_id",
            str(self.template_authoring_mode_id or "").strip(),
        )
        strategy = str(self.template_authoring_strategy or "").strip()
        if strategy not in {"", "requirements", "format_clone"}:
            raise ValueError(
                f"Unsupported template authoring strategy: {strategy!r}"
            )
        object.__setattr__(self, "template_authoring_strategy", strategy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ASSISTANT_TURN_REQUEST_SCHEMA_VERSION,
            "contract_kind": "assistant_turn_request",
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "user_message": self.user_message,
            "provider_profile_id": self.provider_profile_id,
            "model_id": self.model_id,
            "history": [item.to_dict() for item in self.history],
            "local_context_refs": [dict(item) for item in self.local_context_refs],
            "disclosure_grant_id": self.disclosure_grant_id,
            "disclosure_grant": dict(self.disclosure_grant),
            "history_disclosure_grant": dict(
                self.history_disclosure_grant
            ),
            "conversation_cursor": self.conversation_cursor,
            "template_authoring_mode_id": self.template_authoring_mode_id,
            "template_authoring_strategy": self.template_authoring_strategy,
        }


@dataclass(frozen=True, slots=True)
class AssistantRuntimeResult:
    """A neutral result that can never write Form product facts by itself."""

    status: str
    visible_text: str
    source_refs: tuple[dict[str, Any], ...] = ()
    proposed_actions: tuple[dict[str, Any], ...] = ()
    confirmation_requests: tuple[dict[str, Any], ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()
    process_steps: tuple[str, ...] = ()
    tool_audit: Mapping[str, Any] = field(default_factory=dict)
    provider_audit: Mapping[str, Any] = field(default_factory=dict)
    citation_audit: Mapping[str, Any] = field(default_factory=dict)
    public_reasoning_summary: str = ""
    transcript_ref: Mapping[str, Any] = field(default_factory=dict)
    continuation_ref: Mapping[str, Any] = field(default_factory=dict)
    error: Mapping[str, Any] = field(default_factory=dict)
    writes_product_facts: bool = False

    def __post_init__(self) -> None:
        status = str(self.status or "").strip()
        if status not in TURN_STATUSES:
            raise ValueError(f"Unsupported assistant runtime status: {status!r}")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "visible_text", str(self.visible_text or ""))
        object.__setattr__(self, "source_refs", mapping_tuple(self.source_refs))
        object.__setattr__(self, "proposed_actions", mapping_tuple(self.proposed_actions))
        object.__setattr__(self, "confirmation_requests", mapping_tuple(self.confirmation_requests))
        object.__setattr__(self, "artifacts", mapping_tuple(self.artifacts))
        object.__setattr__(self, "process_steps", text_tuple(self.process_steps))
        for name in (
            "tool_audit",
            "provider_audit",
            "citation_audit",
            "transcript_ref",
            "continuation_ref",
            "error",
        ):
            object.__setattr__(self, name, dict(plain_data(getattr(self, name))))
        object.__setattr__(self, "writes_product_facts", False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ASSISTANT_RUNTIME_RESULT_SCHEMA_VERSION,
            "contract_kind": "assistant_runtime_result",
            "status": self.status,
            "visible_text": self.visible_text,
            "source_refs": [dict(item) for item in self.source_refs],
            "proposed_actions": [dict(item) for item in self.proposed_actions],
            "confirmation_requests": [dict(item) for item in self.confirmation_requests],
            "artifacts": [dict(item) for item in self.artifacts],
            "process_steps": list(self.process_steps),
            "tool_audit": dict(self.tool_audit),
            "provider_audit": dict(self.provider_audit),
            "citation_audit": dict(self.citation_audit),
            "public_reasoning_summary": self.public_reasoning_summary,
            "transcript_ref": dict(self.transcript_ref),
            "continuation_ref": dict(self.continuation_ref),
            "error": dict(self.error),
            "writes_product_facts": False,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AssistantRuntimeResult":
        if str(value.get("contract_kind") or "") != "assistant_runtime_result":
            raise ValueError("Not an assistant_runtime_result payload")
        return cls(
            status=str(value.get("status") or ""),
            visible_text=str(value.get("visible_text") or ""),
            source_refs=mapping_tuple(value.get("source_refs")),
            proposed_actions=mapping_tuple(value.get("proposed_actions")),
            confirmation_requests=mapping_tuple(value.get("confirmation_requests")),
            artifacts=mapping_tuple(value.get("artifacts")),
            process_steps=text_tuple(value.get("process_steps")),
            tool_audit=value.get("tool_audit") if isinstance(value.get("tool_audit"), Mapping) else {},
            provider_audit=value.get("provider_audit") if isinstance(value.get("provider_audit"), Mapping) else {},
            citation_audit=value.get("citation_audit") if isinstance(value.get("citation_audit"), Mapping) else {},
            public_reasoning_summary=str(value.get("public_reasoning_summary") or ""),
            transcript_ref=value.get("transcript_ref") if isinstance(value.get("transcript_ref"), Mapping) else {},
            continuation_ref=value.get("continuation_ref") if isinstance(value.get("continuation_ref"), Mapping) else {},
            error=value.get("error") if isinstance(value.get("error"), Mapping) else {},
            writes_product_facts=False,
        )


__all__ = [name for name in globals() if name.startswith("TURN_")] + [
    "ASSISTANT_RUNTIME_RESULT_SCHEMA_VERSION",
    "ASSISTANT_TURN_REQUEST_SCHEMA_VERSION",
    "MAX_ASSISTANT_HISTORY_CHARACTERS",
    "MAX_ASSISTANT_USER_MESSAGE_CHARACTERS",
    "AssistantRuntimeResult",
    "AssistantTurnRequest",
]
