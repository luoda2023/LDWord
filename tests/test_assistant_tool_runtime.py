from __future__ import annotations

import pytest

from src.assistant.contracts.permissions import PermissionDecision, ToolRiskLevel
from src.assistant.runtime.continuation_store import ContinuationStore
from src.assistant.runtime.tool_runtime import (
    TOOL_RUNTIME_WAITING_PERMISSION,
    ToolPermissionRuntime,
)
from src.assistant.tools.gateway import FormToolGateway
from src.assistant.tools.registry import ToolCall, ToolDefinition, ToolRegistry


def test_permission_pause_is_durable_and_resume_is_one_shot(tmp_path):
    calls = []
    gateway = FormToolGateway(
        ToolRegistry(
            (
                ToolDefinition(
                    "inspect_doc",
                    "读取文档正文",
                    ToolRiskLevel.LOCAL_CONTENT_READ,
                    lambda args: calls.append(dict(args)) or {"ok": True},
                ),
            )
        )
    )
    runtime = ToolPermissionRuntime(gateway, ContinuationStore(tmp_path))
    call = ToolCall(
        call_id="call-1",
        session_id="session-1",
        turn_id="turn-1",
        tool_name="inspect_doc",
        arguments={"path": r"C:\Users\Alice\secret.docx"},
    )

    waiting = runtime.request(call)

    assert waiting.status == TOOL_RUNTIME_WAITING_PERMISSION
    assert waiting.continuation is not None
    assert waiting.permission_request["arguments_preview"]["path"] == "secret.docx"
    assert calls == []

    result = runtime.resume(
        waiting.continuation.continuation_id,
        PermissionDecision(request_id="call-1", allowed=True),
    )

    assert result.status == "success"
    assert calls == [{"path": r"C:\Users\Alice\secret.docx"}]
    with pytest.raises(FileNotFoundError):
        runtime.resume(
            waiting.continuation.continuation_id,
            PermissionDecision(request_id="call-1", allowed=True),
        )


def test_mismatched_decision_keeps_continuation_pending(tmp_path):
    runtime = ToolPermissionRuntime(
        FormToolGateway(
            ToolRegistry(
                (
                    ToolDefinition(
                        "inspect_doc",
                        "读取文档正文",
                        ToolRiskLevel.LOCAL_CONTENT_READ,
                        lambda _args: {"ok": True},
                    ),
                )
            )
        ),
        ContinuationStore(tmp_path),
    )
    waiting = runtime.request(
        ToolCall("call-1", "session-1", "turn-1", "inspect_doc")
    )
    assert waiting.continuation is not None

    with pytest.raises(ValueError, match="does not match"):
        runtime.resume(
            waiting.continuation.continuation_id,
            PermissionDecision(request_id="other-call", allowed=True),
        )

    assert len(runtime.continuations.list_pending()) == 1
