"""Resolve typed follow-ups against the currently active document job.

The provider may help interpret or revise content, but it does not own Form's
production state machine.  This module recognizes only high-confidence,
state-dependent continuations and projects them to the same bounded action IDs
used by interaction-card buttons.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from src.assistant.application.request_semantics import (
    is_semantic_revision_request,
)
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.execution import PreflightReceipt
from src.assistant.contracts.jobs import (
    JOB_CANCELLED,
    JOB_CONTENT_DRAFT_READY,
    JOB_CONTENT_GENERATION_READY,
    JOB_EXECUTION_RUNNING,
    JOB_FAILED,
    JOB_NEEDS_EXECUTION_APPROVAL,
    JOB_PARTIAL_SUCCESS,
    JOB_PLAN_READY,
    JOB_PREFLIGHT_FAILED,
    JOB_PREFLIGHT_RUNNING,
    JOB_SUCCESS,
)

ACTION_APPROVE_EXECUTE = "approve_execute"
ACTION_CONFIRM_OUTLINE_AND_GENERATE = "confirm_outline_then_generate"
ACTION_GENERATE_CONTENT_DRAFT = "generate_content_draft"
ACTION_OPEN_ARTIFACT = "open_artifact"
ACTION_OPEN_OUTPUT_FOLDER = "open_output_folder"
ACTION_OPEN_CONTENT_DRAFT = "open_content_draft"
ACTION_PREFLIGHT = "preflight"
ACTION_RETRY_PREFLIGHT = "retry_preflight"
ACTION_REVISE_CONTENT_DRAFT = "revise_content_draft"
ACTION_RESTORE_PREVIOUS_DRAFT = "restore_previous_draft"

DOCUMENT_ACTION_IDS = frozenset(
    {
        ACTION_APPROVE_EXECUTE,
        ACTION_CONFIRM_OUTLINE_AND_GENERATE,
        ACTION_GENERATE_CONTENT_DRAFT,
        ACTION_OPEN_ARTIFACT,
        ACTION_OPEN_OUTPUT_FOLDER,
        ACTION_OPEN_CONTENT_DRAFT,
        ACTION_PREFLIGHT,
        ACTION_RETRY_PREFLIGHT,
        ACTION_REVISE_CONTENT_DRAFT,
        ACTION_RESTORE_PREVIOUS_DRAFT,
    }
)

_ACTION_STATUSES = {
    ACTION_APPROVE_EXECUTE: frozenset({JOB_NEEDS_EXECUTION_APPROVAL}),
    # Directory confirmation surfaces only while the plan is ready and no
    # generation has run yet. Reuse the generate set so the confirm card can
    # still be shown after a cancelled/failed attempt (regenerate path).
    ACTION_CONFIRM_OUTLINE_AND_GENERATE: frozenset(
        {
            JOB_PLAN_READY,
            JOB_CONTENT_GENERATION_READY,
            JOB_CONTENT_DRAFT_READY,
            JOB_FAILED,
            JOB_CANCELLED,
        }
    ),
    ACTION_GENERATE_CONTENT_DRAFT: frozenset(
        {
            JOB_PLAN_READY,
            JOB_CONTENT_GENERATION_READY,
            JOB_CONTENT_DRAFT_READY,
            JOB_FAILED,
            JOB_CANCELLED,
        }
    ),
    ACTION_OPEN_ARTIFACT: frozenset({JOB_SUCCESS, JOB_PARTIAL_SUCCESS}),
    ACTION_OPEN_OUTPUT_FOLDER: frozenset({JOB_SUCCESS, JOB_PARTIAL_SUCCESS}),
    ACTION_OPEN_CONTENT_DRAFT: frozenset(
        {
            JOB_CONTENT_DRAFT_READY,
            JOB_PREFLIGHT_RUNNING,
            JOB_PREFLIGHT_FAILED,
            JOB_NEEDS_EXECUTION_APPROVAL,
            JOB_EXECUTION_RUNNING,
            JOB_SUCCESS,
            JOB_PARTIAL_SUCCESS,
            JOB_FAILED,
            JOB_CANCELLED,
        }
    ),
    ACTION_PREFLIGHT: frozenset({JOB_PLAN_READY, JOB_CONTENT_DRAFT_READY}),
    ACTION_RETRY_PREFLIGHT: frozenset(
        {
            JOB_PREFLIGHT_FAILED,
            JOB_NEEDS_EXECUTION_APPROVAL,
            JOB_PARTIAL_SUCCESS,
            JOB_FAILED,
            JOB_CANCELLED,
        }
    ),
    ACTION_REVISE_CONTENT_DRAFT: frozenset(
        {
            JOB_CONTENT_DRAFT_READY,
            JOB_PREFLIGHT_FAILED,
            JOB_NEEDS_EXECUTION_APPROVAL,
        }
    ),
    ACTION_RESTORE_PREVIOUS_DRAFT: frozenset({JOB_FAILED, JOB_CANCELLED}),
}

_OPEN_HINTS = ("打开", "查看", "预览", "看看")
_DRAFT_HINTS = ("草稿", "题稿", "内容稿")
_OUTPUT_HINTS = ("文档", "word", "docx", "文件", "产物", "结果")
_DELIVERY_REQUEST_HINTS = (
    "给我",
    "最终",
    "生成",
    "输出",
    "导出",
    "交付",
    "制作",
    "做成",
    "转成",
    "完成",
    "下载",
)
_REGENERATE_HINTS = (
    "重新生成草稿",
    "重新生成内容",
    "重新生成题稿",
    "重新生成试卷",
    "重新出题",
    "重写草稿",
    "重做草稿",
    "再生成一份",
    "换一版",
    "重新起草",
)
_CONTINUE_HINTS = (
    "继续",
    "下一步",
    "按这个来",
    "就这样",
    "可以",
    "拼装",
    "装配",
    "输出",
    "交付",
    "生成word",
    "生成文档",
    "制作word",
    "做成word",
    "转成word",
    "导出word",
    "完成文档",
    "最后给我word",
    "给我word",
)
_RETRY_HINTS = ("重试", "重新检查", "再检查", "再试", "重新来", "重来")
_RESTORE_PREVIOUS_DRAFT_HINTS = (
    "恢复上一版",
    "恢复上一个版本",
    "回到上一版",
    "还原上一版",
    "撤销这次修改",
    "撤销本次修改",
)
_APPROVAL_HINTS = (
    "确认并生成",
    "确认生成",
    "确认执行",
    "继续执行",
    "开始执行",
    "同意生成",
    "可以执行",
    "就按这个生成",
    "生成word",
    "生成文档",
)
_EXACT_APPROVALS = frozenset({"确认", "执行", "开始生成"})
_GENERATION_START_HINTS = (
    "继续",
    "开始",
    "下一步",
    "按这个来",
    "就这样",
    "可以",
    "命题",
    "出题",
    "生成草稿",
    "生成内容",
    "生成题稿",
    "开始出题",
)


@dataclass(frozen=True, slots=True)
class ActiveDocumentContinuation:
    """One host-owned action inferred from a typed follow-up."""

    action_id: str
    reason: str

    def __post_init__(self) -> None:
        if self.action_id not in DOCUMENT_ACTION_IDS:
            raise ValueError(f"Unsupported active document action: {self.action_id!r}")


def resolve_active_document_continuation(
    query: str,
    *,
    job_status: str,
    has_active_plan: bool,
    pending_kind: str = "",
    generation_pending: bool = False,
) -> ActiveDocumentContinuation | None:
    """Return a deterministic local action, or ``None`` for provider handling.

    Content-editing language resolves to a host-owned revision action.  It must
    never be mistaken for permission to produce the current draft unchanged.
    """

    compact = _compact(query)
    status = str(job_status or "").strip()
    if not compact or not has_active_plan or str(pending_kind or "").strip():
        return None

    if status == JOB_NEEDS_EXECUTION_APPROVAL:
        if _contains_any(compact, _RETRY_HINTS):
            return ActiveDocumentContinuation(
                ACTION_RETRY_PREFLIGHT,
                "explicit_preflight_refresh",
            )
        if is_semantic_revision_request(query):
            return ActiveDocumentContinuation(
                ACTION_REVISE_CONTENT_DRAFT,
                "revise_current_generated_draft",
            )
        if (
            compact in _EXACT_APPROVALS
            or _contains_any(
                compact,
                _APPROVAL_HINTS,
            )
            or _is_final_output_request(compact)
        ):
            return ActiveDocumentContinuation(
                ACTION_APPROVE_EXECUTE,
                "explicit_execution_confirmation",
            )
        return None

    if status == JOB_PREFLIGHT_FAILED:
        if is_semantic_revision_request(query):
            return ActiveDocumentContinuation(
                ACTION_REVISE_CONTENT_DRAFT,
                "revise_current_generated_draft",
            )
        if _contains_any(compact, _RETRY_HINTS):
            return ActiveDocumentContinuation(
                ACTION_RETRY_PREFLIGHT,
                "explicit_preflight_retry",
            )

    if status in {JOB_SUCCESS, JOB_PARTIAL_SUCCESS} and (
        (
            _contains_any(compact, _OPEN_HINTS)
            and (_contains_any(compact, _OUTPUT_HINTS) or compact in _OPEN_HINTS)
        )
        or _is_final_output_request(compact)
    ):
        return ActiveDocumentContinuation(
            ACTION_OPEN_ARTIFACT,
            "open_current_output",
        )

    if status == JOB_CONTENT_DRAFT_READY:
        if _contains_any(compact, _OPEN_HINTS) and _contains_any(
            compact,
            _DRAFT_HINTS,
        ):
            return ActiveDocumentContinuation(
                ACTION_OPEN_CONTENT_DRAFT,
                "open_current_draft",
            )
        if _contains_any(compact, _REGENERATE_HINTS):
            return ActiveDocumentContinuation(
                ACTION_GENERATE_CONTENT_DRAFT,
                "regenerate_current_draft",
            )
        if is_semantic_revision_request(query):
            return ActiveDocumentContinuation(
                ACTION_REVISE_CONTENT_DRAFT,
                "revise_current_generated_draft",
            )
        if _contains_any(compact, _CONTINUE_HINTS) or _is_final_output_request(compact):
            return ActiveDocumentContinuation(
                ACTION_PREFLIGHT,
                "continue_current_draft_to_preflight",
            )

    if status in {JOB_PLAN_READY, JOB_CONTENT_GENERATION_READY}:
        if generation_pending and (
            _contains_any(compact, _GENERATION_START_HINTS)
            or _is_final_output_request(compact)
        ):
            return ActiveDocumentContinuation(
                ACTION_GENERATE_CONTENT_DRAFT,
                "start_planned_content_generation",
            )
        if not generation_pending and (
            _contains_any(compact, _CONTINUE_HINTS) or _is_final_output_request(compact)
        ):
            return ActiveDocumentContinuation(
                ACTION_PREFLIGHT,
                "continue_current_input_to_preflight",
            )

    if status in {JOB_FAILED, JOB_CANCELLED}:
        if _contains_any(compact, _RESTORE_PREVIOUS_DRAFT_HINTS):
            return ActiveDocumentContinuation(
                ACTION_RESTORE_PREVIOUS_DRAFT,
                "restore_previous_generated_draft",
            )
        if _contains_any(compact, _RETRY_HINTS):
            return ActiveDocumentContinuation(
                ACTION_RETRY_PREFLIGHT,
                "retry_current_document_job",
            )
    return None


def is_active_document_revision_request(
    query: str,
    *,
    job_status: str,
) -> bool:
    """Whether a follow-up edits the draft and must bypass new-plan routing."""

    return bool(
        str(job_status or "").strip()
        in {
            JOB_CONTENT_DRAFT_READY,
            JOB_PREFLIGHT_FAILED,
            JOB_NEEDS_EXECUTION_APPROVAL,
        }
        and is_semantic_revision_request(query)
    )


def validate_active_document_action(
    action_id: str,
    *,
    job: Mapping[str, object],
    plan: DocumentPlan,
) -> str:
    """Fail closed when a card or typed action points at stale job evidence."""

    normalized_action = str(action_id or "").strip()
    if normalized_action not in DOCUMENT_ACTION_IDS:
        return "assistant_document_action_unsupported"
    status = str(job.get("status") or "").strip()
    if status not in _ACTION_STATUSES[normalized_action]:
        return "assistant_document_action_state_changed"

    try:
        job_plan_revision = int(job.get("plan_revision") or 0)
    except (TypeError, ValueError):
        job_plan_revision = 0
    if normalized_action in {
        ACTION_PREFLIGHT,
        ACTION_RETRY_PREFLIGHT,
        ACTION_GENERATE_CONTENT_DRAFT,
        ACTION_CONFIRM_OUTLINE_AND_GENERATE,
        ACTION_APPROVE_EXECUTE,
        ACTION_REVISE_CONTENT_DRAFT,
        ACTION_RESTORE_PREVIOUS_DRAFT,
    } and (
        str(job.get("plan_id") or "") != plan.plan_id
        or job_plan_revision != plan.revision
    ):
        return "assistant_document_action_plan_stale"

    if normalized_action in {
        ACTION_GENERATE_CONTENT_DRAFT,
        ACTION_CONFIRM_OUTLINE_AND_GENERATE,
    } and (not plan.generation_required or plan.blocking_issues):
        return "assistant_content_generation_not_available"
    if normalized_action == ACTION_REVISE_CONTENT_DRAFT:
        source = plan.production_input_artifact
        if (
            not plan.generation_required
            or source is None
            or source.source_kind != "assistant_generated"
        ):
            return "assistant_content_revision_not_available"
    if normalized_action == ACTION_RESTORE_PREVIOUS_DRAFT:
        raw_previous_plan = job.get("previous_plan_snapshot")
        if not isinstance(raw_previous_plan, Mapping):
            return "assistant_previous_draft_not_available"
        try:
            previous_plan = DocumentPlan.from_dict(raw_previous_plan)
        except (TypeError, ValueError):
            return "assistant_previous_draft_invalid"
        previous_source = previous_plan.production_input_artifact
        if (
            previous_plan.plan_id != plan.plan_id
            or previous_plan.revision >= plan.revision
            or previous_source is None
            or previous_source.source_kind != "assistant_generated"
            or not Path(previous_source.path).expanduser().is_file()
        ):
            return "assistant_previous_draft_invalid"

    if normalized_action == ACTION_APPROVE_EXECUTE:
        raw_preflight = job.get("preflight")
        if not isinstance(raw_preflight, Mapping):
            return "assistant_preflight_missing"
        try:
            preflight = PreflightReceipt.from_dict(raw_preflight)
        except (TypeError, ValueError):
            return "assistant_preflight_invalid"
        if (
            not preflight.ready
            or preflight.plan_id != plan.plan_id
            or preflight.plan_revision != plan.revision
            or preflight.plan_fingerprint != plan.fingerprint
        ):
            return "assistant_preflight_stale"
    return ""


def _compact(value: str) -> str:
    normalized = str(value or "").casefold()
    return re.sub(r"[\s，。！？、；：,.!?;:（）()【】\[\]“”\"']+", "", normalized)


def _contains_any(value: str, candidates: tuple[str, ...]) -> bool:
    return any(candidate in value for candidate in candidates)


def _is_final_output_request(compact: str) -> bool:
    return _contains_any(compact, _OUTPUT_HINTS) and _contains_any(
        compact, _DELIVERY_REQUEST_HINTS
    )


__all__ = [
    "ACTION_APPROVE_EXECUTE",
    "ACTION_CONFIRM_OUTLINE_AND_GENERATE",
    "ACTION_GENERATE_CONTENT_DRAFT",
    "ACTION_OPEN_ARTIFACT",
    "ACTION_OPEN_CONTENT_DRAFT",
    "ACTION_OPEN_OUTPUT_FOLDER",
    "ACTION_PREFLIGHT",
    "ACTION_RETRY_PREFLIGHT",
    "ACTION_REVISE_CONTENT_DRAFT",
    "ACTION_RESTORE_PREVIOUS_DRAFT",
    "DOCUMENT_ACTION_IDS",
    "ActiveDocumentContinuation",
    "is_active_document_revision_request",
    "resolve_active_document_continuation",
    "validate_active_document_action",
]
