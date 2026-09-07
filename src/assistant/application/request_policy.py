"""Pre-provider policy for document requests.

The provider is conversational infrastructure, not the owner of Form capability
decisions.  This module classifies a request before any attachment content is
read or any provider is invoked.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.assistant.application.capability_registry import (
    ResolvedAssistantCapability,
    classify_task_operation,
    resolve_assistant_capability,
)
from src.assistant.application.plan_builder import requests_form_document_action
from src.assistant.application.request_semantics import (
    is_semantic_revision_request,
)
from src.assistant.contracts.task_plan import CAPABILITY_EXECUTABLE
from src.assistant.domain.docx_format_evidence import (
    is_format_requirements_request,
    is_template_authoring_request,
)
from src.config.scene_natural_request_router import (
    NaturalRequestRoute,
    NaturalRequestRouteResult,
    get_natural_request_route,
    route_natural_scene_request,
)

POLICY_GENERAL_CHAT = "general_chat"
POLICY_DOCUMENT_ADVISORY = "document_advisory"
POLICY_DOCUMENT_ACTION = "document_action"
POLICY_NEEDS_ROUTE_CLARIFICATION = "needs_route_clarification"
POLICY_RESPONSE_CLOSED = "response_closed"

_ROUTE_DISPLAY_LABELS = {
    "quick_formatting_general": "通用快速排版",
    "quick_bilingual_formatting": "双语排版",
    "personal_career_formatting": "个人职业文档",
    "chinese_academic_thesis": "中文论文或课程论文",
    "english_journal_submission": "英文期刊投稿",
    "exam_teaching_versions": "试卷与教学版本",
    "bidding_document_authoring": "标书正文生成与排版",
    "bidding_qualification_archive": "投标资质归档",
    "official_policy_documents": "公文、会议或政策文档",
    "technical_long_document": "技术长文档",
    "project_application_package": "项目申报与评审包",
    "product_sales_document": "产品、白皮书或售前文档",
    "contract_delivery_package": "合同审阅与签署交付",
    "hr_batch_documents": "人事批量文档",
    "fixed_form_batch_documents": "固定表单或证书批量",
    "finance_quote_documents": "报价、预算或财务附件",
    "regulated_disclosure_documents": "受监管披露归档",
    "ip_patent_manual_boundary": "专利或知识产权文档",
    "legal_document_manual_boundary": "法律意见或法律文书",
    "medical_regulatory_manual_boundary": "医疗或药品注册材料",
    "bilingual_review_documents": "翻译与术语一致性审阅",
    "import_pdf_thesis_boundary": "PDF 论文导入",
    "import_ai_conversion_boundary": "OCR、PDF 或 LaTeX 转换",
}


@dataclass(frozen=True, slots=True)
class RequestPolicyChoice:
    route_id: str
    label: str
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.route_id,
            "label": self.label,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class RequestPolicyDecision:
    kind: str
    query: str
    operation: str
    route: NaturalRequestRoute | None
    route_status: str
    capability: ResolvedAssistantCapability
    clarification_prompt: str = ""
    choices: tuple[RequestPolicyChoice, ...] = ()

    @property
    def route_id(self) -> str:
        return self.route.route_id if self.route is not None else ""

    @property
    def route_label(self) -> str:
        return route_display_label(self.route)

    @property
    def capability_status(self) -> str:
        return self.capability.ref.status


def route_display_label(route: NaturalRequestRoute | None) -> str:
    if route is None:
        return "通用文档"
    return _ROUTE_DISPLAY_LABELS.get(route.route_id, str(route.label or "文档任务"))


def route_display_label_by_id(route_id: str) -> str:
    return _ROUTE_DISPLAY_LABELS.get(str(route_id or "").strip(), "通用文档")


def evaluate_request_policy(
    query: str,
    *,
    workspace_mode_id: str,
    has_attachment: bool = False,
    route_id_override: str = "",
) -> RequestPolicyDecision:
    """Return the deterministic decision that must run before the provider."""

    normalized_query = str(query or "").strip()
    routed = route_natural_scene_request(normalized_query)
    override = str(route_id_override or "").strip()
    deterministic_route = _deterministic_ambiguity_route(routed)
    selected_route = (
        get_natural_request_route(override)
        if override
        else (routed.selected_route or deterministic_route)
    )
    operation = classify_task_operation(normalized_query)
    capability = resolve_assistant_capability(
        route=selected_route,
        workspace_mode_id=workspace_mode_id,
        operation=operation,
        query=normalized_query,
    )

    if is_template_authoring_request(normalized_query):
        # Template authoring is a provider-backed configuration workflow, not
        # document production.  It must win before route clarification and the
        # generic document-action branch so its source DOCX can never become a
        # content-generation or Word-production input.
        return RequestPolicyDecision(
            kind=POLICY_DOCUMENT_ADVISORY,
            query=normalized_query,
            operation=operation,
            route=selected_route,
            route_status=(
                "matched"
                if override or deterministic_route is not None
                else routed.status
            ),
            capability=capability,
        )

    if not override and routed.status == "ambiguous" and deterministic_route is None:
        # 一句话直出目录：不再让用户在相似场景之间挑选。AI 自动采用得分
        # 最高的场景继续起草（matches 已按分数降序），生成章节目录后用户
        # 仍可在目录卡里修改要求，选错场景的代价被降到最低。
        top_match = routed.matches[0] if routed.matches else None
        if top_match is not None and selected_route is None:
            selected_route = top_match.route
            capability = resolve_assistant_capability(
                route=selected_route,
                workspace_mode_id=workspace_mode_id,
                operation=operation,
                query=normalized_query,
            )

    route_status = (
        "matched"
        if override
        or deterministic_route is not None
        or (routed.status == "ambiguous" and selected_route is not None)
        else routed.status
    )
    if is_format_requirements_request(normalized_query):
        return RequestPolicyDecision(
            kind=POLICY_DOCUMENT_ADVISORY,
            query=normalized_query,
            operation=operation,
            route=selected_route,
            route_status=route_status,
            capability=capability,
        )

    if selected_route is not None and capability.ref.status != CAPABILITY_EXECUTABLE:
        return RequestPolicyDecision(
            kind=POLICY_RESPONSE_CLOSED,
            query=normalized_query,
            operation=operation,
            route=selected_route,
            route_status=route_status,
            capability=capability,
        )

    if override and selected_route is not None:
        return RequestPolicyDecision(
            kind=POLICY_DOCUMENT_ACTION,
            query=normalized_query,
            operation=operation,
            route=selected_route,
            route_status=route_status,
            capability=capability,
        )

    if (
        has_attachment
        and operation == "review"
        and not is_semantic_revision_request(normalized_query)
    ):
        return RequestPolicyDecision(
            kind=POLICY_DOCUMENT_ADVISORY,
            query=normalized_query,
            operation=operation,
            route=selected_route,
            route_status=route_status,
            capability=capability,
        )
    if requests_form_document_action(normalized_query):
        return RequestPolicyDecision(
            kind=POLICY_DOCUMENT_ACTION,
            query=normalized_query,
            operation=operation,
            route=selected_route,
            route_status=route_status,
            capability=capability,
        )

    return RequestPolicyDecision(
        kind=POLICY_GENERAL_CHAT,
        query=normalized_query,
        operation=operation,
        route=selected_route,
        route_status=route_status,
        capability=capability,
    )


def _deterministic_ambiguity_route(
    result: NaturalRequestRouteResult,
) -> NaturalRequestRoute | None:
    """Collapse context-only quick-format noise to the generic quick route."""

    if result.status != "ambiguous" or not result.matches:
        return None
    top_score = result.matches[0].score
    competing = tuple(
        match for match in result.matches if top_score - match.score <= 14
    )
    if not competing or any(match.matched_aliases for match in competing):
        return None
    quick_general = next(
        (
            match.route
            for match in competing
            if match.route.route_id == "quick_formatting_general"
        ),
        None,
    )
    if quick_general is None:
        return None
    if any(match.route.pack_id != "quick_formatting" for match in competing):
        return None
    return quick_general


def _choice_description(route: NaturalRequestRoute) -> str:
    if route.route_type in {
        "professional_boundary",
        "plugin_manual_boundary",
        "import_boundary",
    }:
        return "当前只说明能力边界，不会自动生产文档"
    if route.route_id in {
        "english_journal_submission",
        "project_application_package",
        "product_sales_document",
        "contract_delivery_package",
        "hr_batch_documents",
        "fixed_form_batch_documents",
    }:
        return "当前已识别，但尚未开放自动生产"
    return "使用现有 Form 方案建立本地计划"


__all__ = [
    "POLICY_DOCUMENT_ACTION",
    "POLICY_DOCUMENT_ADVISORY",
    "POLICY_GENERAL_CHAT",
    "POLICY_NEEDS_ROUTE_CLARIFICATION",
    "POLICY_RESPONSE_CLOSED",
    "RequestPolicyChoice",
    "RequestPolicyDecision",
    "evaluate_request_policy",
    "route_display_label",
    "route_display_label_by_id",
]
