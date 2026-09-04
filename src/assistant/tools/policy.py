"""Fail-closed tool permission policy."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePath
from typing import Any

from src.assistant.contracts.permissions import (
    DisclosureGrant,
    PermissionDecision,
    ToolPermissionRequest,
    ToolRiskLevel,
)
from src.assistant.tools.registry import ToolCall, ToolDefinition


AUTO_ALLOWED_RISKS = frozenset(
    {ToolRiskLevel.LOCAL_METADATA_READ, ToolRiskLevel.SESSION_DRAFT_WRITE}
)


class ToolPolicy:
    def permission_request(
        self,
        definition: ToolDefinition,
        call: ToolCall,
    ) -> ToolPermissionRequest | None:
        if definition.risk_level in AUTO_ALLOWED_RISKS:
            return None
        if definition.risk_level == ToolRiskLevel.EXTERNAL_PUBLISH:
            return None
        return ToolPermissionRequest(
            request_id=call.call_id,
            session_id=call.session_id,
            turn_id=call.turn_id,
            tool_name=call.tool_name,
            risk_level=definition.risk_level,
            summary=definition.description,
            arguments_preview=redact_tool_arguments(call.arguments),
            idempotency_key=call.idempotency_key,
        )

    def allows(
        self,
        definition: ToolDefinition,
        call: ToolCall,
        *,
        decision: PermissionDecision | None,
        disclosure_grant: DisclosureGrant | None,
    ) -> bool:
        risk = definition.risk_level
        if risk in AUTO_ALLOWED_RISKS:
            return True
        if risk == ToolRiskLevel.EXTERNAL_PUBLISH:
            return False
        if risk == ToolRiskLevel.PROVIDER_DISCLOSURE:
            if disclosure_grant is None:
                return False
            raw_refs = call.arguments.get("refs", ())
            raw_fields = call.arguments.get("fields", ())
            raw_fingerprints = call.arguments.get("fingerprints", {})
            refs = tuple(str(item) for item in raw_refs) if isinstance(raw_refs, (list, tuple)) else ()
            fields = tuple(str(item) for item in raw_fields) if isinstance(raw_fields, (list, tuple)) else ()
            fingerprints = (
                {str(key): str(value) for key, value in raw_fingerprints.items()}
                if isinstance(raw_fingerprints, Mapping)
                else {}
            )
            return disclosure_grant.permits(
                session_id=call.session_id,
                provider_id=str(call.arguments.get("provider_id") or ""),
                model_id=str(call.arguments.get("model_id") or ""),
                refs=refs,
                fields=fields,
                fingerprints=fingerprints,
            )
        return bool(
            decision is not None
            and decision.request_id == call.call_id
            and decision.allowed
        )


def redact_tool_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _redact_preview_value(str(key), value)
        for key, value in arguments.items()
    }


def _redact_preview_value(key: str, value: Any) -> Any:
    normalized_key = key.casefold()
    if any(token in normalized_key for token in ("path", "root", "file")):
        return _path_name(value)
    if "secret" in normalized_key or "api_key" in normalized_key or normalized_key == "key":
        return "<已隐藏>"
    if isinstance(value, Mapping):
        return {
            str(child_key): _redact_preview_value(str(child_key), child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_preview_value(key, item) for item in value]
    return value


def _path_name(value: object) -> object:
    if isinstance(value, str):
        return PurePath(value).name or "<本地路径>"
    if isinstance(value, (list, tuple)):
        return [_path_name(item) for item in value]
    return "<本地路径>"


__all__ = ["AUTO_ALLOWED_RISKS", "ToolPolicy", "redact_tool_arguments"]
