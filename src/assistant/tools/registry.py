"""Neutral tool definitions and invocation results."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from src.assistant.contracts.permissions import ToolRiskLevel
from src.assistant.contracts.serialization import plain_data


ToolHandler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    risk_level: ToolRiskLevel
    handler: ToolHandler
    parameters_schema: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not callable(self.handler):
            raise ValueError("Tool name and handler are required")
        object.__setattr__(self, "risk_level", ToolRiskLevel(self.risk_level))
        object.__setattr__(self, "parameters_schema", dict(plain_data(self.parameters_schema)))

    def public_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": int(self.risk_level),
            "parameters": dict(self.parameters_schema),
        }


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    session_id: str
    turn_id: str
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not all(str(getattr(self, name) or "").strip() for name in ("call_id", "session_id", "turn_id", "tool_name")):
            raise ValueError("Tool call identity is required")
        object.__setattr__(self, "arguments", dict(plain_data(self.arguments)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": "assistant_tool_call",
            "call_id": self.call_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ToolCall":
        return cls(
            call_id=str(value.get("call_id") or ""),
            session_id=str(value.get("session_id") or ""),
            turn_id=str(value.get("turn_id") or ""),
            tool_name=str(value.get("tool_name") or ""),
            arguments=(
                value.get("arguments")
                if isinstance(value.get("arguments"), Mapping)
                else {}
            ),
            idempotency_key=str(value.get("idempotency_key") or ""),
        )


@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: str
    tool_name: str
    status: str
    output: Mapping[str, Any] = field(default_factory=dict)
    error: Mapping[str, Any] = field(default_factory=dict)
    permission_request: Mapping[str, Any] = field(default_factory=dict)
    audit: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in {"success", "failed", "needs_permission", "blocked", "cancelled"}:
            raise ValueError(f"Unsupported tool result status: {self.status!r}")
        for name in ("output", "error", "permission_request", "audit"):
            object.__setattr__(self, name, dict(plain_data(getattr(self, name))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": "assistant_tool_result",
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "status": self.status,
            "output": dict(self.output),
            "error": dict(self.error),
            "permission_request": dict(self.permission_request),
            "audit": dict(self.audit),
        }


class ToolRegistry:
    def __init__(self, definitions: tuple[ToolDefinition, ...] = ()) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"Duplicate assistant tool: {definition.name}")
        self._definitions[definition.name] = definition

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._definitions[str(name)]
        except KeyError as exc:
            raise KeyError(f"Unknown assistant tool: {name}") from exc

    def public_catalog(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            self._definitions[name].public_schema()
            for name in sorted(self._definitions)
        )


__all__ = ["ToolCall", "ToolDefinition", "ToolHandler", "ToolRegistry", "ToolResult"]
