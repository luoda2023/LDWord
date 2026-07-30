"""Durable, one-shot permission pause/resume around the Form Tool Gateway."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from src.assistant.contracts.permissions import PermissionDecision
from src.assistant.runtime.continuation_store import ContinuationRecord, ContinuationStore
from src.assistant.tools.gateway import FormToolGateway
from src.assistant.tools.registry import ToolCall, ToolResult


TOOL_RUNTIME_WAITING_PERMISSION = "waiting_permission"


@dataclass(frozen=True, slots=True)
class ToolRuntimeOutcome:
    status: str
    tool_result: ToolResult | None = None
    continuation: ContinuationRecord | None = None
    permission_request: Mapping[str, Any] = field(default_factory=dict)


class ToolPermissionRuntime:
    def __init__(self, gateway: FormToolGateway, continuations: ContinuationStore) -> None:
        self.gateway = gateway
        self.continuations = continuations

    def request(self, call: ToolCall) -> ToolRuntimeOutcome:
        result = self.gateway.invoke(call)
        if result.status != "needs_permission":
            return ToolRuntimeOutcome(status=result.status, tool_result=result)
        record = ContinuationRecord(
            continuation_id=uuid4().hex,
            session_id=call.session_id,
            turn_id=call.turn_id,
            kind="tool_permission",
            payload={
                "call": call.to_dict(),
                "permission_request": dict(result.permission_request),
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.continuations.save(record)
        return ToolRuntimeOutcome(
            status=TOOL_RUNTIME_WAITING_PERMISSION,
            tool_result=result,
            continuation=record,
            permission_request=result.permission_request,
        )

    def resume(
        self,
        continuation_id: str,
        decision: PermissionDecision,
    ) -> ToolRuntimeOutcome:
        record = self.continuations.load(continuation_id)
        raw_call = record.payload.get("call")
        if not isinstance(raw_call, Mapping):
            raise ValueError("Tool continuation has no valid call")
        call = ToolCall.from_dict(raw_call)
        if decision.request_id != call.call_id:
            raise ValueError("Permission decision does not match the paused tool call")
        consumed = self.continuations.consume(continuation_id)
        if consumed != record:
            raise RuntimeError("Tool continuation changed while resuming")
        result = self.gateway.invoke(call, decision=decision)
        return ToolRuntimeOutcome(status=result.status, tool_result=result)


__all__ = [
    "TOOL_RUNTIME_WAITING_PERMISSION",
    "ToolPermissionRuntime",
    "ToolRuntimeOutcome",
]
