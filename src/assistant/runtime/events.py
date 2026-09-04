"""Public streaming events adapted from Alavette Flow (MIT)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from src.assistant.contracts.serialization import plain_data


ASSISTANT_EVENT_SCHEMA_VERSION = "form-assistant-event-v1"

EVENT_TURN_STARTED = "turn_started"
EVENT_CONTEXT_READY = "context_ready"
EVENT_MODEL_STARTED = "model_started"
EVENT_TEXT_DELTA = "text_delta"
EVENT_TURN_FINISHED = "turn_finished"
EVENT_TURN_FAILED = "turn_failed"
EVENT_TURN_CANCELLED = "turn_cancelled"
EVENT_TURN_WAITING = "turn_waiting"


@dataclass(frozen=True, slots=True)
class AssistantEvent:
    type: str
    turn_id: str
    message_id: str = ""
    text_delta: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.type or not self.turn_id:
            raise ValueError("Assistant event type and turn_id are required")
        object.__setattr__(self, "payload", dict(plain_data(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ASSISTANT_EVENT_SCHEMA_VERSION,
            "contract_kind": "assistant_event",
            "type": self.type,
            "turn_id": self.turn_id,
            "message_id": self.message_id,
            "text_delta": self.text_delta,
            "payload": dict(self.payload),
        }


__all__ = [name for name in globals() if name.startswith("EVENT_")] + [
    "ASSISTANT_EVENT_SCHEMA_VERSION",
    "AssistantEvent",
]
