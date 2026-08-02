from __future__ import annotations

import pytest

from src.assistant.application.plan_builder import requests_form_document_action
from src.assistant.application.request_policy import (
    POLICY_DOCUMENT_ADVISORY,
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


def test_template_authoring_owns_the_request_before_document_production() -> None:
    query = "帮我按照要求制作论文的模板"

    decision = _decision(query, has_attachment=True)

    assert decision.kind == POLICY_DOCUMENT_ADVISORY
    assert decision.route_id == "chinese_academic_thesis"
    assert decision.operation == "author"
    assert requests_form_document_action(query) is False


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


def test_exam_creation_with_zh_make_verb_stays_in_local_plan_flow() -> None:
    decision = evaluate_request_policy(
        "我需要制作一份初中六年级语文期中考试试卷",
        workspace_mode_id="exam",
    )

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.operation == "author"
    assert decision.route_id == "exam_teaching_versions"
    assert decision.capability_status == "executable"


@pytest.mark.parametrize(
    "query",
    (
        "我需要写一个公文",
        "我想写一个公文",
        "帮我拟一个公文",
        "我要发一个公文",
        "我有写一篇公文",
        "请下发一份通知",
        "我有个公文要写",
        "帮我写篇公文",
        "拟个通知",
        "做个公文",
    ),
)
def test_generic_official_authoring_phrases_enter_local_official_flow(
    query,
) -> None:
    decision = _decision(query)

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.operation == "author"
    assert decision.route_id == "official_policy_documents"
    assert decision.capability.mode_id == "official"
    assert decision.capability.generation.required is True


@pytest.mark.parametrize(
    "query",
    (
        "帮我命题一份七年级数学试卷",
        "帮我出一份七年级数学试卷",
        "请出一套七年级数学试卷",
        "设计一份七年级数学试卷",
        "准备一份七年级数学试卷",
        "我想要一份七年级数学试卷",
        "给我一份七年级数学试卷",
        "编制一份项目报告",
    ),
)
def test_common_authoring_phrases_share_one_document_action_policy(query) -> None:
    decision = _decision(query)

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.operation == "author"


@pytest.mark.parametrize(
    "query",
    (
        "不要生成试卷，只解释命题原则",
        "不要写公文，只告诉我有哪些公文类型",
        "不用写通知，解释一下通知格式",
    ),
)
def test_negated_generation_request_does_not_create_a_document_plan(query) -> None:
    decision = _decision(query)

    assert decision.kind != POLICY_DOCUMENT_ACTION


def test_sending_an_existing_report_to_the_assistant_is_not_authoring() -> None:
    decision = _decision("我发一个报告给你分析", has_attachment=True)

    assert decision.kind == POLICY_DOCUMENT_ADVISORY
    assert decision.operation == "review"


@pytest.mark.parametrize(
    "query, expected_kind, expected_route",
    (
        ("给我整一份通知", POLICY_DOCUMENT_ACTION, "official_policy_documents"),
        ("弄一套数学卷", POLICY_DOCUMENT_ACTION, "exam_teaching_versions"),
        ("给我来个周报", POLICY_DOCUMENT_ACTION, ""),
        ("帮我重新做一版期中卷", POLICY_DOCUMENT_ACTION, "exam_teaching_versions"),
        ("重新排一下版", POLICY_DOCUMENT_ACTION, ""),
    ),
)
def test_remaining_colloquial_document_actions_do_not_fall_into_chat(
    query,
    expected_kind,
    expected_route,
) -> None:
    decision = _decision(query, has_attachment=True)

    assert decision.kind == expected_kind
    assert decision.route_id == expected_route


@pytest.mark.parametrize(
    "query",
    (
        "别给我写公文，写个工作总结",
        "公文不要，帮我写一份工作总结",
        "不考虑公文，帮我写一份工作总结",
    ),
)
def test_negated_official_object_cannot_steal_the_later_authoring_target(
    query,
) -> None:
    decision = _decision(query)

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.route_id == ""
    assert decision.capability.mode_id == "custom"


def test_hypothetical_authoring_question_stays_advisory() -> None:
    decision = _decision("假设我要写通知，需要准备什么")

    assert decision.kind != POLICY_DOCUMENT_ACTION
    assert decision.operation != "author"


@pytest.mark.parametrize(
    "query",
    ("分析这篇论文", "不要润色论文，只分析结构", "检查这份试卷", "检查这份 Word 文档"),
)
def test_attachment_review_is_consistently_read_only(query) -> None:
    decision = _decision(query, has_attachment=True)

    assert decision.kind == POLICY_DOCUMENT_ADVISORY
    assert decision.operation == "review"


@pytest.mark.parametrize(
    "query, expected_generation",
    (
        ("把论文语言润色一下", True),
        ("帮我把报告改专业一点", True),
        ("把页边距改为 2 厘米", False),
        ("把这个 Word 美化一下", False),
    ),
)
def test_semantic_revision_and_formatting_use_distinct_execution_contracts(
    query,
    expected_generation,
) -> None:
    decision = _decision(query, has_attachment=True)

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.capability.generation.required is expected_generation


@pytest.mark.parametrize(
    "query",
    (
        "我不想写公文",
        "有没有必要写公文",
        "不要帮我写公文，只说明格式",
        "是否需要写一份通知",
    ),
)
def test_negation_and_advisory_scope_never_starts_authoring(query) -> None:
    decision = _decision(query)

    assert decision.kind != POLICY_DOCUMENT_ACTION
    assert decision.operation != "author"


def test_negated_first_clause_does_not_suppress_later_authoring_target() -> None:
    decision = _decision("不要写公文，帮我写一份工作总结")

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.operation == "author"
    assert decision.route_id == ""
    assert decision.capability.mode_id == "custom"


@pytest.mark.parametrize(
    "query, route_id",
    (
        ("我要发个通知", "official_policy_documents"),
        ("写封函", "official_policy_documents"),
        ("来一份请示", "official_policy_documents"),
        ("给孩子出套数学卷", "exam_teaching_versions"),
        ("帮我做张六年级语文卷子", "exam_teaching_versions"),
        ("组一套期中卷", "exam_teaching_versions"),
        ("帮我写一篇论文", "chinese_academic_thesis"),
    ),
)
def test_colloquial_document_creation_enters_the_domain_plan(
    query,
    route_id,
) -> None:
    decision = _decision(query)

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.operation == "author"
    assert decision.route_id == route_id


@pytest.mark.parametrize(
    "query",
    (
        "给我写份文档",
        "帮我写一份工作总结",
        "生成一份周报",
        "做个汇报材料",
    ),
)
def test_generic_document_objects_enter_local_authoring(query) -> None:
    decision = _decision(query)

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.operation == "author"


@pytest.mark.parametrize(
    "query, expected_route",
    (
        ("帮我修改这份公文", "official_policy_documents"),
        ("润色一下这份通知", "official_policy_documents"),
        ("改一下这个 Word 文档", ""),
        ("按这个模板套一下", ""),
        ("把页边距改为 2 厘米", ""),
    ),
)
def test_existing_document_mutations_enter_local_plan(
    query,
    expected_route,
) -> None:
    decision = _decision(query, has_attachment=True)

    assert decision.kind == POLICY_DOCUMENT_ACTION
    assert decision.operation == "transform"
    assert decision.route_id == expected_route


def test_existing_document_transfer_for_review_is_not_reclassified_as_authoring() -> None:
    decision = _decision("我发个通知给你看看", has_attachment=True)

    assert decision.kind == POLICY_GENERAL_CHAT
    assert decision.operation == "transform"


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
