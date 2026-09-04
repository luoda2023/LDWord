"""The only runtime entry point for registered Form assistant tools."""

from __future__ import annotations

from src.assistant.contracts.permissions import DisclosureGrant, PermissionDecision, ToolRiskLevel
from src.assistant.tools.policy import ToolPolicy
from src.assistant.tools.registry import ToolCall, ToolRegistry, ToolResult


class FormToolGateway:
    def __init__(self, registry: ToolRegistry, *, policy: ToolPolicy | None = None) -> None:
        self.registry = registry
        self.policy = policy or ToolPolicy()
        self._idempotent_results: dict[str, ToolResult] = {}

    def invoke(
        self,
        call: ToolCall,
        *,
        decision: PermissionDecision | None = None,
        disclosure_grant: DisclosureGrant | None = None,
    ) -> ToolResult:
        try:
            definition = self.registry.get(call.tool_name)
        except KeyError as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="failed",
                error={"category": "unknown_tool", "message": str(exc)},
            )
        if definition.risk_level == ToolRiskLevel.EXTERNAL_PUBLISH:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="blocked",
                error={"category": "unsupported", "message": "外部发布在当前版本中不可用"},
                audit={"risk_level": int(definition.risk_level)},
            )
        permission_request = self.policy.permission_request(definition, call)
        if not self.policy.allows(
            definition,
            call,
            decision=decision,
            disclosure_grant=disclosure_grant,
        ):
            declined = decision is not None and decision.request_id == call.call_id and not decision.allowed
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="blocked" if declined else "needs_permission",
                permission_request=(permission_request.to_dict() if permission_request is not None else {}),
                error=(
                    {"category": "permission_denied", "message": "用户拒绝了此操作"}
                    if declined
                    else {}
                ),
                audit={"risk_level": int(definition.risk_level)},
            )
        cache_key = str(call.idempotency_key or "").strip()
        if cache_key and definition.risk_level >= ToolRiskLevel.DURABLE_WORKSPACE_WRITE:
            cached = self._idempotent_results.get(cache_key)
            if cached is not None:
                return cached
        try:
            output = definition.handler(call.arguments)
            result = ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="success",
                output=output,
                audit={
                    "risk_level": int(definition.risk_level),
                    "idempotency_key": cache_key,
                    "writes_product_facts": False,
                },
            )
        except Exception as exc:
            result = ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="failed",
                error={
                    "category": "tool_execution",
                    "type": type(exc).__name__,
                    "message": str(exc) or type(exc).__name__,
                },
                audit={"risk_level": int(definition.risk_level)},
            )
        if cache_key and definition.risk_level >= ToolRiskLevel.DURABLE_WORKSPACE_WRITE:
            self._idempotent_results[cache_key] = result
        return result


__all__ = ["FormToolGateway"]
