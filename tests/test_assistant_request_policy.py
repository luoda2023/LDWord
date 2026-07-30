from __future__ import annotations

from src.assistant.application.request_policy import (
    POLICY_DOCUMENT_ACTION,
    POLICY_GENERAL_CHAT,
    POLICY_NEEDS_ROUTE_CLARIFICATION,
    POLICY_RESPONSE_CLOSED,
    evaluate_request_policy,
)


def _decision(query: str, *, has_attachment: bool = False):
    return evaluate_request_policy(
        query,
        workspace_mode_id="custom",
        has_attachment=has_attachment,
    )


def test_ambiguous_document_request_is_clarified_before_provider() -> None:
    decision = _decision("处理这份双语文档", has_attachment=True)

    assert decision.kind == POLICY_NEEDS_ROUTE_CLARIFICATION
    assert {
        choice.route_id for choice in decision.choices
    } >= {"quick_bilingual_formatting", "bilingual_review_documents"}


def test_gated_and_planned_routes_close_locally() -> None:
    for query in (
        "检查翻译和术语一致性",
        "审查合同法律风险",
        "起草一份专利权利要求",
        "分析医疗注册材料",
        "根据成本表做客户报价",
        "PDF论文转Word",
    ):
        decision = _decision(query, has_attachment=True)
        assert decision.kind in {
            POLICY_NEEDS_ROUTE_CLARIFICATION,
            POLICY_RESPONSE_CLOSED,
        }, (query, decision)


def test_executable_document_action_creates_local_plan_policy() -> None:
    decision = _decision("统一这份 Word 文档格式", has_attachment=True)

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.capability_status == "executable"


def test_general_chat_remains_a_provider_conversation() -> None:
    decision = _decision("你好，请解释一下标题样式的作用")

    assert decision.kind == POLICY_GENERAL_CHAT


def test_clarification_route_override_is_deterministic() -> None:
    decision = evaluate_request_policy(
        "处理这份双语文档",
        workspace_mode_id="custom",
        has_attachment=True,
        route_id_override="quick_bilingual_formatting",
    )

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.route_id == "quick_bilingual_formatting"
