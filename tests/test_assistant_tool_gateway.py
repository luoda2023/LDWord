from __future__ import annotations

from src.assistant.contracts.permissions import (
    DisclosureGrant,
    PermissionDecision,
    ToolRiskLevel,
)
from src.assistant.tools.gateway import FormToolGateway
from src.assistant.tools.registry import ToolCall, ToolDefinition, ToolRegistry


def _call(name: str, *, arguments=None, call_id="call-1", idempotency_key="") -> ToolCall:
    return ToolCall(
        call_id=call_id,
        session_id="session-1",
        turn_id="turn-1",
        tool_name=name,
        arguments=arguments or {},
        idempotency_key=idempotency_key,
    )


def test_metadata_tool_runs_without_prompting():
    registry = ToolRegistry(
        (
            ToolDefinition(
                "list_modes",
                "列出工作模式",
                ToolRiskLevel.LOCAL_METADATA_READ,
                lambda _args: {"items": ["custom"]},
            ),
        )
    )

    result = FormToolGateway(registry).invoke(_call("list_modes"))

    assert result.status == "success"
    assert result.output == {"items": ["custom"]}


def test_content_read_fails_closed_until_matching_permission_is_granted():
    registry = ToolRegistry(
        (
            ToolDefinition(
                "inspect_doc",
                "读取文档正文",
                ToolRiskLevel.LOCAL_CONTENT_READ,
                lambda _args: {"text": "secret body"},
            ),
        )
    )
    gateway = FormToolGateway(registry)
    call = _call("inspect_doc", arguments={"path": r"C:\Users\Alice\secret.docx"})

    waiting = gateway.invoke(call)

    assert waiting.status == "needs_permission"
    assert waiting.permission_request["arguments_preview"]["path"] == "secret.docx"
    assert "C:\\Users" not in str(waiting.to_dict())

    denied = gateway.invoke(
        call,
        decision=PermissionDecision(request_id=call.call_id, allowed=False),
    )
    assert denied.status == "blocked"

    allowed = gateway.invoke(
        call,
        decision=PermissionDecision(request_id=call.call_id, allowed=True),
    )
    assert allowed.status == "success"


def test_permission_preview_redacts_nested_plan_paths():
    registry = ToolRegistry(
        (
            ToolDefinition(
                "produce",
                "生成文档",
                ToolRiskLevel.DOCUMENT_PRODUCTION,
                lambda _args: {"ok": True},
            ),
        )
    )
    result = FormToolGateway(registry).invoke(
        _call(
            "produce",
            arguments={
                "plan": {
                    "input_document_ref": {
                        "path": r"C:\\Users\\Alice\\secret.docx"
                    },
                    "output_policy": {"output_root": r"C:\\Secret\\Output"},
                }
            },
        )
    )

    preview = result.permission_request["arguments_preview"]
    assert preview["plan"]["input_document_ref"]["path"] == "secret.docx"
    assert preview["plan"]["output_policy"]["output_root"] == "Output"
    assert "C:\\" not in str(preview)


def test_provider_disclosure_is_bound_to_exact_provider_model_and_fingerprint():
    registry = ToolRegistry(
        (
            ToolDefinition(
                "disclose",
                "向模型发送选定正文",
                ToolRiskLevel.PROVIDER_DISCLOSURE,
                lambda _args: {"sent": True},
            ),
        )
    )
    gateway = FormToolGateway(registry)
    call = _call(
        "disclose",
        arguments={
            "provider_id": "cloud-main",
            "model_id": "model-a",
            "refs": ["doc-1"],
            "fields": ["paragraphs"],
            "fingerprints": {"doc-1": "hash-a"},
        },
    )
    wrong = DisclosureGrant(
        grant_id="grant-1",
        session_id="session-1",
        provider_id="cloud-main",
        model_id="model-b",
        allowed_refs=("doc-1",),
        allowed_fields=("paragraphs",),
        content_fingerprints={"doc-1": "hash-a"},
    )
    right = DisclosureGrant(
        grant_id="grant-2",
        session_id="session-1",
        provider_id="cloud-main",
        model_id="model-a",
        allowed_refs=("doc-1",),
        allowed_fields=("paragraphs",),
        content_fingerprints={"doc-1": "hash-a"},
    )

    assert gateway.invoke(call, disclosure_grant=wrong).status == "needs_permission"
    assert gateway.invoke(call, disclosure_grant=right).status == "success"


def test_external_publish_is_always_blocked():
    registry = ToolRegistry(
        (
            ToolDefinition(
                "publish",
                "发布到外部",
                ToolRiskLevel.EXTERNAL_PUBLISH,
                lambda _args: {"published": True},
            ),
        )
    )
    result = FormToolGateway(registry).invoke(
        _call("publish"),
        decision=PermissionDecision(request_id="call-1", allowed=True),
    )
    assert result.status == "blocked"


def test_confirmed_write_is_idempotent():
    calls = []
    registry = ToolRegistry(
        (
            ToolDefinition(
                "produce",
                "生成文档",
                ToolRiskLevel.DOCUMENT_PRODUCTION,
                lambda _args: calls.append("run") or {"status": "success"},
            ),
        )
    )
    gateway = FormToolGateway(registry)
    first_call = _call("produce", idempotency_key="job-1")
    second_call = _call("produce", call_id="call-2", idempotency_key="job-1")

    first = gateway.invoke(
        first_call,
        decision=PermissionDecision(request_id="call-1", allowed=True),
    )
    second = gateway.invoke(
        second_call,
        decision=PermissionDecision(request_id="call-2", allowed=True),
    )

    assert first.status == "success"
    assert second.output == first.output
    assert calls == ["run"]
