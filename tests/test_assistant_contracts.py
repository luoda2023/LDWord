from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.assistant.contracts.document_plan import DocumentPlan, OutputPolicy
from src.assistant.contracts.jobs import (
    JOB_EXECUTION_RUNNING,
    JOB_NEEDS_EXECUTION_APPROVAL,
    JOB_PLAN_READY,
    JOB_PREFLIGHT_RUNNING,
    JOB_SUCCESS,
    validate_document_job_transition,
)
from src.assistant.contracts.messages import AssistantMessage, MessageBlock, ROLE_USER
from src.assistant.contracts.permissions import DisclosureGrant, ToolRiskLevel
from src.assistant.contracts.runtime import (
    AssistantRuntimeResult,
    AssistantTurnRequest,
    TURN_COMPLETED,
)


def test_message_round_trip_is_versioned_and_detached():
    message = AssistantMessage.text(
        message_id="message-1",
        role=ROLE_USER,
        text="统一这份文档格式",
    )

    restored = AssistantMessage.from_dict(message.to_dict())

    assert restored == message
    assert restored.visible_text() == "统一这份文档格式"
    assert restored.to_dict()["schema_version"] == "form-assistant-message-v1"


def test_message_contract_rejects_live_values_and_is_immutable():
    with pytest.raises(TypeError, match="Unsupported assistant payload"):
        MessageBlock(type="interaction", data={"widget": object()})

    message = AssistantMessage.text(message_id="message-1", role=ROLE_USER, text="hello")
    with pytest.raises(FrozenInstanceError):
        message.role = "assistant"  # type: ignore[misc]


def test_runtime_result_can_never_claim_product_fact_writes():
    result = AssistantRuntimeResult(
        status=TURN_COMPLETED,
        visible_text="计划完成",
        writes_product_facts=True,
    )

    assert result.writes_product_facts is False
    assert result.to_dict()["writes_product_facts"] is False
    assert AssistantRuntimeResult.from_dict(result.to_dict()) == result


def test_turn_request_requires_stable_identity_and_model():
    with pytest.raises(ValueError, match="model_id"):
        AssistantTurnRequest(
            turn_id="turn-1",
            session_id="session-1",
            user_message="处理文档",
            provider_profile_id="mock",
            model_id="",
        )


def test_document_plan_fingerprint_changes_with_revision():
    first = DocumentPlan(
        plan_id="plan-1",
        revision=1,
        intent="统一排版",
        created_by_turn_id="turn-1",
        output_policy=OutputPolicy(output_root="out"),
    )
    second = DocumentPlan.from_dict({**first.to_dict(), "revision": 2})

    assert first.fingerprint != second.fingerprint
    assert DocumentPlan.from_dict(first.to_dict()) == first


def test_disclosure_grant_is_bound_to_provider_model_fields_and_fingerprint():
    grant = DisclosureGrant(
        grant_id="grant-1",
        session_id="session-1",
        provider_id="provider-a",
        model_id="model-a",
        allowed_refs=("document-1",),
        allowed_fields=("paragraphs",),
        content_fingerprints={"document-1": "hash-a"},
        scope="once",
    )

    assert grant.permits(
        session_id="session-1",
        provider_id="provider-a",
        model_id="model-a",
        refs=("document-1",),
        fields=("paragraphs",),
        fingerprints={"document-1": "hash-a"},
    )
    assert not grant.permits(
        session_id="session-1",
        provider_id="provider-a",
        model_id="model-b",
        refs=("document-1",),
        fields=("paragraphs",),
        fingerprints={"document-1": "hash-a"},
    )
    assert ToolRiskLevel.DOCUMENT_PRODUCTION > ToolRiskLevel.PROVIDER_DISCLOSURE


def test_document_job_state_machine_accepts_the_approval_path_and_rejects_skips():
    assert validate_document_job_transition("", JOB_PLAN_READY) == (
        JOB_PLAN_READY
    )
    assert validate_document_job_transition(
        JOB_PLAN_READY,
        JOB_PREFLIGHT_RUNNING,
    ) == JOB_PREFLIGHT_RUNNING
    assert validate_document_job_transition(
        JOB_PREFLIGHT_RUNNING,
        JOB_NEEDS_EXECUTION_APPROVAL,
    ) == JOB_NEEDS_EXECUTION_APPROVAL
    assert validate_document_job_transition(
        JOB_NEEDS_EXECUTION_APPROVAL,
        JOB_EXECUTION_RUNNING,
    ) == JOB_EXECUTION_RUNNING
    assert validate_document_job_transition(
        JOB_EXECUTION_RUNNING,
        JOB_SUCCESS,
    ) == JOB_SUCCESS

    with pytest.raises(ValueError, match="Unsupported document job transition"):
        validate_document_job_transition(
            JOB_PLAN_READY,
            JOB_EXECUTION_RUNNING,
        )
