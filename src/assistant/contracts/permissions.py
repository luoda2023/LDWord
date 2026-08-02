"""Data disclosure and tool permission contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any

from src.assistant.contracts.serialization import plain_data


class ToolRiskLevel(IntEnum):
    LOCAL_METADATA_READ = 0
    LOCAL_CONTENT_READ = 1
    PROVIDER_DISCLOSURE = 2
    SESSION_DRAFT_WRITE = 3
    DURABLE_WORKSPACE_WRITE = 4
    DOCUMENT_PRODUCTION = 5
    EXTERNAL_PUBLISH = 6


@dataclass(frozen=True, slots=True)
class ToolPermissionRequest:
    request_id: str
    session_id: str
    turn_id: str
    tool_name: str
    risk_level: ToolRiskLevel
    summary: str
    arguments_preview: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_level", ToolRiskLevel(self.risk_level))
        object.__setattr__(
            self, "arguments_preview", dict(plain_data(self.arguments_preview))
        )
        if not all(
            str(getattr(self, name) or "").strip()
            for name in ("request_id", "session_id", "turn_id", "tool_name")
        ):
            raise ValueError("Permission request identity fields are required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": "tool_permission_request",
            "request_id": self.request_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "tool_name": self.tool_name,
            "risk_level": int(self.risk_level),
            "summary": self.summary,
            "arguments_preview": dict(self.arguments_preview),
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    request_id: str
    allowed: bool
    scope: str = "once"
    decided_at: str = ""

    def __post_init__(self) -> None:
        if self.scope not in {"once", "session"}:
            raise ValueError("Permission scope must be 'once' or 'session'")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": "permission_decision",
            "request_id": self.request_id,
            "allowed": self.allowed,
            "scope": self.scope,
            "decided_at": self.decided_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PermissionDecision:
        return cls(
            request_id=str(value.get("request_id") or ""),
            allowed=bool(value.get("allowed", False)),
            scope=str(value.get("scope") or "once"),
            decided_at=str(value.get("decided_at") or ""),
        )


@dataclass(frozen=True, slots=True)
class DisclosureGrant:
    grant_id: str
    session_id: str
    provider_id: str
    model_id: str
    allowed_refs: tuple[str, ...]
    allowed_fields: tuple[str, ...]
    text_character_count: int = 0
    image_count: int = 0
    created_at: str = ""
    expires_at: str = ""
    scope: str = "once"
    content_fingerprints: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scope not in {"once", "session"}:
            raise ValueError("Disclosure scope must be 'once' or 'session'")
        if self.text_character_count < 0 or self.image_count < 0:
            raise ValueError("Disclosure counts cannot be negative")
        object.__setattr__(
            self, "allowed_refs", tuple(str(item) for item in self.allowed_refs)
        )
        object.__setattr__(
            self, "allowed_fields", tuple(str(item) for item in self.allowed_fields)
        )
        normalized = plain_data(self.content_fingerprints)
        object.__setattr__(self, "content_fingerprints", dict(normalized))

    def permits(
        self,
        *,
        session_id: str,
        provider_id: str,
        model_id: str,
        refs: tuple[str, ...],
        fields: tuple[str, ...],
        fingerprints: Mapping[str, str] | None = None,
        now: datetime | None = None,
    ) -> bool:
        if self.expires_at:
            try:
                expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                current = now or datetime.now(timezone.utc)
                if current.tzinfo is None:
                    current = current.replace(tzinfo=timezone.utc)
                if current >= expires:
                    return False
            except ValueError:
                return False
        if (session_id, provider_id, model_id) != (
            self.session_id,
            self.provider_id,
            self.model_id,
        ):
            return False
        if not set(refs).issubset(self.allowed_refs):
            return False
        if not set(fields).issubset(self.allowed_fields):
            return False
        if fingerprints is not None:
            for key, value in fingerprints.items():
                if self.content_fingerprints.get(key) != value:
                    return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": "disclosure_grant",
            "grant_id": self.grant_id,
            "session_id": self.session_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "allowed_refs": list(self.allowed_refs),
            "allowed_fields": list(self.allowed_fields),
            "text_character_count": self.text_character_count,
            "image_count": self.image_count,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "content_fingerprints": dict(self.content_fingerprints),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> DisclosureGrant:
        if str(value.get("contract_kind") or "") != "disclosure_grant":
            raise ValueError("Not a disclosure_grant payload")
        raw_refs = value.get("allowed_refs", ())
        raw_fields = value.get("allowed_fields", ())
        if not isinstance(raw_refs, (list, tuple)) or not isinstance(
            raw_fields,
            (list, tuple),
        ):
            raise TypeError("Disclosure grant refs and fields must be lists")
        fingerprints = value.get("content_fingerprints")
        return cls(
            grant_id=str(value.get("grant_id") or ""),
            session_id=str(value.get("session_id") or ""),
            provider_id=str(value.get("provider_id") or ""),
            model_id=str(value.get("model_id") or ""),
            allowed_refs=tuple(str(item) for item in raw_refs),
            allowed_fields=tuple(str(item) for item in raw_fields),
            text_character_count=int(value.get("text_character_count") or 0),
            image_count=int(value.get("image_count") or 0),
            created_at=str(value.get("created_at") or ""),
            expires_at=str(value.get("expires_at") or ""),
            scope=str(value.get("scope") or "once"),
            content_fingerprints=(
                dict(fingerprints) if isinstance(fingerprints, Mapping) else {}
            ),
        )


__all__ = [
    "DisclosureGrant",
    "PermissionDecision",
    "ToolPermissionRequest",
    "ToolRiskLevel",
]
