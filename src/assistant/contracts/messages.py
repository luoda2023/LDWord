"""Neutral assistant message contract.

Ported and adapted from Alavette Flow's MIT-licensed assistant kernel message
contract.  Flow product-decision ownership has intentionally been removed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.assistant.contracts.serialization import mapping_tuple, plain_data


ASSISTANT_MESSAGE_SCHEMA_VERSION = "form-assistant-message-v1"

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"
ROLE_TOOL = "tool"
MESSAGE_ROLES = frozenset({ROLE_USER, ROLE_ASSISTANT, ROLE_SYSTEM, ROLE_TOOL})

BLOCK_TEXT = "text"
BLOCK_INTERACTION = "interaction"
BLOCK_ARTIFACT = "artifact"


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class MessageBlock:
    type: str
    text: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.type or "").strip():
            raise ValueError("Message block type is required")
        object.__setattr__(self, "type", str(self.type).strip())
        object.__setattr__(self, "text", str(self.text or ""))
        object.__setattr__(self, "data", dict(plain_data(self.data)))

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text, "data": dict(self.data)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MessageBlock":
        return cls(
            type=str(value.get("type") or ""),
            text=str(value.get("text") or ""),
            data=value.get("data") if isinstance(value.get("data"), Mapping) else {},
        )


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    message_id: str
    role: str
    blocks: tuple[MessageBlock, ...]
    created_at: str = ""
    visibility: str = "visible"
    source_refs: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not str(self.message_id or "").strip():
            raise ValueError("Assistant message_id is required")
        role = str(self.role or "").strip()
        if role not in MESSAGE_ROLES:
            raise ValueError(f"Unsupported assistant message role: {role!r}")
        blocks = tuple(self.blocks)
        if not blocks:
            raise ValueError("Assistant message requires at least one block")
        if not all(isinstance(item, MessageBlock) for item in blocks):
            raise TypeError("Assistant message blocks must be MessageBlock values")
        object.__setattr__(self, "message_id", str(self.message_id).strip())
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "blocks", blocks)
        object.__setattr__(self, "created_at", str(self.created_at or utc_now_text()))
        object.__setattr__(self, "visibility", str(self.visibility or "visible"))
        object.__setattr__(self, "source_refs", mapping_tuple(self.source_refs))

    @classmethod
    def text(
        cls,
        *,
        role: str,
        text: str,
        message_id: str = "",
        source_refs: tuple[dict[str, Any], ...] = (),
        created_at: str = "",
    ) -> "AssistantMessage":
        return cls(
            message_id=message_id or uuid4().hex,
            role=role,
            blocks=(MessageBlock(type=BLOCK_TEXT, text=text),),
            source_refs=source_refs,
            created_at=created_at,
        )

    @classmethod
    def interaction(
        cls,
        *,
        role: str,
        interaction_type: str,
        title: str,
        body: str,
        payload: Mapping[str, Any] | None = None,
        message_id: str = "",
    ) -> "AssistantMessage":
        data = dict(payload or {})
        data.update({"interaction_type": interaction_type, "title": title})
        return cls(
            message_id=message_id or uuid4().hex,
            role=role,
            blocks=(MessageBlock(type=BLOCK_INTERACTION, text=body, data=data),),
        )

    @classmethod
    def artifact(
        cls,
        *,
        role: str,
        title: str,
        body: str,
        reference: Mapping[str, Any],
        actions: tuple[Mapping[str, Any], ...] = (),
        message_id: str = "",
    ) -> "AssistantMessage":
        return cls(
            message_id=message_id or uuid4().hex,
            role=role,
            blocks=(
                MessageBlock(
                    type=BLOCK_ARTIFACT,
                    text=body,
                    data={
                        "interaction_type": "artifact",
                        "title": title,
                        "reference": dict(reference),
                        "actions": [dict(item) for item in actions],
                    },
                ),
            ),
        )

    def visible_text(self) -> str:
        return "".join(block.text for block in self.blocks if block.type == BLOCK_TEXT)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ASSISTANT_MESSAGE_SCHEMA_VERSION,
            "contract_kind": "assistant_message",
            "message_id": self.message_id,
            "role": self.role,
            "blocks": [block.to_dict() for block in self.blocks],
            "created_at": self.created_at,
            "visibility": self.visibility,
            "source_refs": [dict(item) for item in self.source_refs],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AssistantMessage":
        if str(value.get("contract_kind") or "assistant_message") != "assistant_message":
            raise ValueError("Not an assistant_message payload")
        raw_blocks = value.get("blocks")
        if not isinstance(raw_blocks, (list, tuple)):
            raise TypeError("Assistant message blocks must be a list")
        return cls(
            message_id=str(value.get("message_id") or ""),
            role=str(value.get("role") or ""),
            blocks=tuple(
                MessageBlock.from_dict(item)
                for item in raw_blocks
                if isinstance(item, Mapping)
            ),
            created_at=str(value.get("created_at") or ""),
            visibility=str(value.get("visibility") or "visible"),
            source_refs=mapping_tuple(value.get("source_refs")),
        )


__all__ = [
    "ASSISTANT_MESSAGE_SCHEMA_VERSION",
    "BLOCK_ARTIFACT",
    "BLOCK_INTERACTION",
    "BLOCK_TEXT",
    "MESSAGE_ROLES",
    "ROLE_ASSISTANT",
    "ROLE_SYSTEM",
    "ROLE_TOOL",
    "ROLE_USER",
    "AssistantMessage",
    "MessageBlock",
    "utc_now_text",
]
