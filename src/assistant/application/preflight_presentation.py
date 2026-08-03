"""Pure, centralized presentation and recovery policy for preflight evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.assistant.adapters.production_adapter import AUTHORING_ONLY_MATERIAL_WARNING
from src.assistant.application.plan_presentation import present_document_plan
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.execution import PreflightReceipt
from src.services.official_draft_source import official_field_label


@dataclass(frozen=True, slots=True)
class PreflightFindingPresentation:
    code: str
    severity: str
    owner: str
    message: str
    repair_action: str = ""


@dataclass(frozen=True, slots=True)
class PreflightCardPresentation:
    interaction_type: str
    title: str
    body: str
    facts: tuple[tuple[str, str], ...]
    notices: tuple[str, ...]
    actions: tuple[dict[str, str], ...]


_EXACT_ISSUE_MESSAGES = {
    "material_snapshot_digest_mismatch": "资料在检查过程中发生了变化，请重新检查。",
    "execution_material_mode_mismatch": "当前资料类型不能直接用于该文档模式，请调整资料或任务类型。",
    "assistant_capability_not_executable": "当前任务还不能进入本地文档生产。",
    "input_document_missing": "用于生产的内容草稿不存在，请重新生成草稿。",
    "input_document_unsupported": "当前内容草稿格式不受该生产链支持。",
    "input_artifact_digest_mismatch": "内容草稿在生成后发生了变化，请重新生成或恢复草稿。",
    "work_mode_missing": "尚未确定文档工作模式。",
    "scene_unavailable": "当前文档方案不可用，请重新选择方案。",
    "template_unavailable": "当前模板不可用，请重新选择模板。",
    "approved_master_missing": "当前文档母版不可用，请重新选择母版。",
    "output_root_is_not_directory": "输出位置不是有效文件夹，请重新选择。",
    "output_root_overwrites_input_document": "输出位置与输入文件冲突，请更换输出位置。",
    "execution_path_resolution_failed": "无法确认输入和输出路径，请重新选择输出位置。",
    "official_draft_document_type_mismatch": "内容草稿的公文文种与当前计划不一致。",
    "official_material_snapshot_required": "当前公文缺少可用于生产的结构化资料。",
    "official_document_type_missing": "尚未确定公文文种。",
}

_EXAM_REVIEW_WARNING_MESSAGES = {
    "missing_paper_title": "题稿缺少明确标题，将使用可用的文件名或默认标题。",
    "missing_subject": "题稿缺少学科信息，请在交付前复核。",
    "missing_grade": "题稿缺少年级信息，请在交付前复核。",
    "missing_duration": "题稿缺少考试时长，请在交付前复核。",
    "missing_total_score": "题稿缺少满分信息，请在交付前复核。",
    "answer_coverage_incomplete": "部分题目缺少答案，答案卷会以“待补充”标记。",
    "score_coverage_incomplete": "部分题目缺少分值，仍会生成候选版。",
    "declared_total_score_missing": "题稿未声明总分，仍会生成候选版。",
    "total_score_mismatch": "题目分值合计与声明总分不一致，请复核。",
    "section_question_number_reference_mismatch": "大题标题中的题号范围与题目不一致，输出会统一编号。",
    "question_number_sequence_invalid": "原题号不连续，输出会统一重新编号。",
    "section_question_count_mismatch": "大题声明的题量与实际题量不一致，请复核。",
    "section_score_mismatch": "大题声明分值与小题合计不一致，请复核。",
    "section_per_question_score_mismatch": "大题标注的每题分值与实际分值不一致，请复核。",
    "choice_options_incomplete": "部分选择题选项不完整，仍会生成候选版。",
    "duplicate_question_stem": "题稿中存在重复题目，请复核。",
    "requested_analysis_coverage_incomplete": "部分题目缺少要求的解析，请复核。",
    "inline_format_degraded": "局部 Markdown 样式已退化为纯文本，正文内容仍会保留。",
    "unexpected_foreign_text_in_chinese_exam": "语文题稿中疑似混入异常外语片段，已保留交付但请重点复核。",
    "knowledge_point_coverage_too_low": "知识点覆盖偏少，请复核。",
    "blueprint_section_count_too_low": "大题数量少于推荐规格，请复核。",
    "blueprint_section_structure_mismatch": "大题结构与推荐规格不完全一致，请复核。",
    "difficulty_metadata_incomplete": "部分题目缺少难度标记，请复核。",
    "difficulty_metadata_invalid": "部分题目的难度标记无法识别，请复核。",
    "difficulty_distribution_mismatch": "难度分布与推荐规格不完全一致，请复核。",
}


def present_preflight_issue(value: str) -> PreflightFindingPresentation:
    issue = str(value or "").strip()
    if issue in _EXACT_ISSUE_MESSAGES:
        return PreflightFindingPresentation(
            code=issue,
            severity="blocking",
            owner=_owner_for_issue(issue),
            message=_EXACT_ISSUE_MESSAGES[issue],
            repair_action=_repair_action_for_issue(issue),
        )
    if issue.startswith(("official_draft_field_missing:", "official_material_field_missing:")):
        field = issue.rsplit(":", 1)[-1]
        source_label = (
            "内容草稿"
            if issue.startswith("official_draft_field_missing:")
            else "公文资料"
        )
        return PreflightFindingPresentation(
            code=issue,
            severity="blocking",
            owner="official_plan_editor",
            message=(
                f"{source_label}缺少{official_field_label(field)}，"
                "请补充后重新检查。"
            ),
            repair_action="edit_official_plan_requirements",
        )
    if issue.startswith("official_draft_source_invalid:"):
        message, action, owner = (
            "当前公文内容草稿无法读取，请重新生成草稿。",
            "generate_content_draft",
            "content_draft",
        )
    elif issue.startswith("master_ref_incompatible:"):
        message, action, owner = (
            "当前母版与所选公文文种不匹配。系统内置默认母版可在重新检查时自动纠正。",
            "retry_preflight",
            "official_plan_binding",
        )
    elif issue.startswith("master_ref_unresolved:"):
        message, action, owner = (
            "当前母版不存在或已经失效，请重新选择母版。",
            "edit_official_plan_requirements",
            "official_plan_editor",
        )
    elif issue.startswith("official_document_type_unknown:"):
        message, action, owner = (
            "当前公文文种无法识别，请重新选择文种。",
            "edit_official_plan_requirements",
            "official_plan_editor",
        )
    elif issue.startswith("exam_source_error:") or issue.startswith("exam_source_invalid:"):
        message, action, owner = (
            "当前试卷题稿无法通过本地结构校验，请重新生成或修改题稿。",
            "generate_content_draft",
            "content_draft",
        )
    elif issue.startswith("execution_target_unresolved:"):
        message, action, owner = (
            "无法解析当前文档的生产目标，请重新检查计划绑定。",
            "retry_preflight",
            "plan_binding",
        )
    elif issue.startswith(("assistant_scene_projection_failed:", "assistant_scene_family_projection_failed:")):
        message, action, owner = (
            "当前文档方案无法应用，请重新检查计划配置。",
            "retry_preflight",
            "plan_binding",
        )
    elif issue.startswith("assistant_scene_family_not_applicable:"):
        message, action, owner = (
            "当前场景族不适用于这份文档，请重新检查计划配置。",
            "retry_preflight",
            "plan_binding",
        )
    elif issue.startswith("assistant_delivery_preset_unavailable:"):
        message, action, owner = (
            "当前交付方式不适用于这份文档，请重新选择交付方式。",
            "edit_official_plan_requirements",
            "official_plan_editor",
        )
    elif issue.startswith(("execution_material_finalize_failed:", "execution_material_finalize_blocked:")):
        message, action, owner = (
            "资料与输出配置无法完成冻结，请重新检查。",
            "retry_preflight",
            "local_preflight",
        )
    elif issue.startswith("plan_blocked:"):
        message, action, owner = (
            "当前计划仍有未解决项目，请补充要求后重新检查。",
            "edit_plan",
            "plan_editor",
        )
    else:
        message, action, owner = (
            "本地检查发现一项尚未识别的问题；未执行文档生产。请重新检查。",
            "retry_preflight",
            "local_preflight",
        )
    return PreflightFindingPresentation(
        code=issue,
        severity="blocking",
        owner=owner,
        message=message,
        repair_action=action,
    )


def present_preflight_warning(value: str) -> str:
    warning = str(value or "").strip()
    if warning.startswith("official_draft_warning:"):
        return warning.split(":", 1)[1].strip()
    if warning == AUTHORING_ONLY_MATERIAL_WARNING:
        return "参考资料仅用于内容起草；正式生成将使用当前结构化草稿。"
    if warning == "output_replacement_requested":
        return "本次任务申请覆盖已有输出，执行前请确认。"
    if warning.startswith("exam_source_warning:"):
        finding = warning.split(":", 1)[1]
        code = finding.split(":", 1)[0]
        return _EXAM_REVIEW_WARNING_MESSAGES.get(
            code,
            f"题稿存在可复核项（{code}），仍可生成候选版。",
        )
    return warning


def present_preflight_card(
    plan: DocumentPlan,
    receipt: PreflightReceipt,
) -> PreflightCardPresentation:
    notices = tuple(present_preflight_warning(item) for item in receipt.warnings)
    if receipt.ready:
        review_candidate = any(
            str(item or "").startswith("exam_source_warning:")
            for item in receipt.warnings
        )
        plan_presentation = present_document_plan(plan)
        allowed = {
            "任务", "操作", "输入", "方案", "模板", "资料",
            "交付", "输出", "输出位置", "数据范围",
        }
        facts = tuple(
            (label, value)
            for label, value in plan_presentation.facts
            if label in allowed
        ) + ((
            "原文件",
            "允许覆盖（执行前再次确认）"
            if plan.output_policy.overwrite
            else "保留，不覆盖",
        ),)
        return PreflightCardPresentation(
            interaction_type="approval",
            title=(
                "可生成候选版，建议复核"
                if review_candidate
                else "执行前检查已通过"
            ),
            body="",
            facts=facts,
            notices=notices,
            actions=(
                {
                    "id": "approve_execute",
                    "label": (
                        "确认并生成候选 Word"
                        if review_candidate
                        else "确认并生成 Word"
                    ),
                },
            ),
        )

    findings = tuple(present_preflight_issue(item) for item in receipt.issues)
    return PreflightCardPresentation(
        interaction_type="preflight",
        title="执行前检查未通过",
        body="\n".join(f"• {item.message}" for item in findings),
        facts=(("输出目录", str(receipt.output_root)),),
        notices=notices,
        actions=_recovery_actions(plan, findings),
    )


def active_preflight_card_presentation(
    *,
    active_plan: Mapping[str, object] | None,
    document_job: Mapping[str, object] | None,
) -> PreflightCardPresentation | None:
    """Rehydrate the active card from evidence instead of stale UI strings."""

    job = dict(document_job or {})
    raw_receipt = job.get("preflight")
    if not isinstance(active_plan, Mapping) or not isinstance(raw_receipt, Mapping):
        return None
    try:
        plan = DocumentPlan.from_dict(active_plan)
        receipt = PreflightReceipt.from_dict(raw_receipt)
    except (TypeError, ValueError):
        return None
    if receipt.plan_id != plan.plan_id or receipt.plan_revision != plan.revision:
        return None
    return present_preflight_card(plan, receipt)


def _recovery_actions(
    plan: DocumentPlan,
    findings: tuple[PreflightFindingPresentation, ...],
) -> tuple[dict[str, str], ...]:
    issues = tuple(item.code for item in findings)
    requested = {item.repair_action for item in findings}
    auto_master = any(item.startswith("master_ref_incompatible:") for item in issues)
    actions: list[dict[str, str]] = [{
        "id": "retry_preflight",
        "label": "使用匹配母版重新检查" if auto_master else "重新检查",
    }]
    if "generate_content_draft" in requested or (
        plan.generation_required and "input_document_missing" in issues
    ):
        actions.append({"id": "generate_content_draft", "label": "重新生成草稿"})
    if "edit_official_plan_requirements" in requested or (
        plan.production_contract.terminal_assembler == "official"
        and "edit_plan" in requested
    ):
        actions.append(
            {"id": "edit_official_plan_requirements", "label": "修改公文信息"}
        )
    elif plan.production_contract.terminal_assembler == "exam" and "edit_plan" in requested:
        actions.append(
            {"id": "edit_exam_plan_requirements", "label": "修改试卷要求"}
        )
    elif "open_workbench" in requested:
        actions.append({"id": "open_workbench", "label": "返回工作台处理"})
    return tuple(actions)


def _owner_for_issue(issue: str) -> str:
    if issue.startswith("output_") or issue == "execution_path_resolution_failed":
        return "plan_editor"
    if issue in {"scene_unavailable", "template_unavailable", "approved_master_missing"}:
        return "workbench"
    if issue.startswith("input_"):
        return "content_draft"
    return "local_preflight"


def _repair_action_for_issue(issue: str) -> str:
    if issue in {"input_document_missing", "input_document_unsupported"}:
        return "generate_content_draft"
    if issue == "scene_unavailable":
        return "open_workbench"
    if issue in {"template_unavailable", "approved_master_missing"}:
        return "edit_plan"
    if issue.startswith("output_") or issue == "execution_path_resolution_failed":
        return "edit_plan"
    if issue.startswith("official_"):
        return "edit_official_plan_requirements"
    return "retry_preflight"


__all__ = [
    "PreflightCardPresentation",
    "PreflightFindingPresentation",
    "active_preflight_card_presentation",
    "present_preflight_card",
    "present_preflight_issue",
    "present_preflight_warning",
]
