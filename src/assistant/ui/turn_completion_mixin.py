"""Completion and durable-result projection for assistant turns."""

from __future__ import annotations

from collections.abc import Mapping

from src.assistant.contracts.jobs import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_PROVIDER_RUNNING,
    JOB_RESPONSE_READY,
    JOB_RESPONSE_WAITING,
)
from src.assistant.contracts.messages import ROLE_ASSISTANT, AssistantMessage
from src.assistant.contracts.runtime import (
    AssistantRuntimeResult,
    TURN_CANCELLED,
    TURN_COMPLETED,
    TURN_FAILED,
    TURN_WAITING_DATA_PERMISSION,
    TURN_WAITING_TOOL_PERMISSION,
    TURN_WAITING_USER_QUESTION,
)
from src.assistant.ui.provider_presentation import provider_error_text
from src.assistant.ui.runtime_result_presentation import format_evidence_payload
from src.assistant.ui.workers import AssistantTurnWorker


class AssistantTurnCompletionMixin:
    def _on_turn_finished(self, worker: AssistantTurnWorker, result) -> None:
        if self._turn_workers.get(worker.request.session_id) is not worker:
            return
        origin_session_id = worker.request.session_id
        self._clear_turn_preview(origin_session_id)
        try:
            origin = self._coordinator.load_session(origin_session_id)
        except (OSError, ValueError, TypeError):
            self._finish_turn_ui(worker)
            return
        if result.visible_text:
            assistant_message = AssistantMessage.text(
                role=ROLE_ASSISTANT,
                text=result.visible_text,
                source_refs=result.source_refs,
            )
            origin = self._coordinator.append_message(
                origin,
                assistant_message,
                turn_status=result.status,
            )
        waiting_statuses = {
            TURN_WAITING_USER_QUESTION,
            TURN_WAITING_DATA_PERMISSION,
            TURN_WAITING_TOOL_PERMISSION,
        }
        if result.continuation_ref or result.status in waiting_statuses:
            continuation = dict(result.continuation_ref)
            continuation.setdefault("turn_id", worker.request.turn_id)
            continuation.setdefault("status", result.status)
            continuation.setdefault(
                "provider_profile_id",
                worker.request.provider_profile_id,
            )
            continuation.setdefault("model_id", worker.request.model_id)
            origin = self._coordinator.update_state(
                origin,
                pending_continuation=continuation,
                turn_status=result.status,
            )
            if (
                str(origin.document_job.get("status") or "")
                == JOB_PROVIDER_RUNNING
            ):
                origin = self._coordinator.update_state(
                    origin,
                    document_job={
                        **dict(origin.document_job),
                        "status": JOB_RESPONSE_WAITING,
                    },
                )
        elif (
            worker.request.conversation_cursor
            and result.status == TURN_COMPLETED
        ):
            origin = self._coordinator.update_state(
                origin,
                pending_continuation={},
            )
        for message in self._runtime_result_messages(result):
            origin = self._coordinator.append_message(origin, message)
        raw_runtime_results = origin.document_job.get("runtime_results", ())
        runtime_results = (
            [dict(item) for item in raw_runtime_results if isinstance(item, Mapping)]
            if isinstance(raw_runtime_results, (list, tuple))
            else []
        )
        runtime_results.append(result.to_dict())
        origin = self._coordinator.update_state(
            origin,
            document_job={
                **dict(origin.document_job),
                "runtime_results": runtime_results[-50:],
            },
        )
        if result.status == TURN_COMPLETED:
            next_job = dict(origin.document_job)
            next_job.pop("pending_document_request", None)
            next_job.pop("plan_candidate", None)
            if str(next_job.get("status") or "") == JOB_PROVIDER_RUNNING:
                next_job["status"] = JOB_RESPONSE_READY
            self._turn_material_snapshots.pop(worker.request.turn_id, None)
            origin = self._coordinator.update_state(
                origin,
                document_job=next_job,
                turn_status=result.status,
            )
        elif result.status in {TURN_FAILED, TURN_CANCELLED}:
            self._turn_material_snapshots.pop(worker.request.turn_id, None)
            if worker.request.conversation_cursor:
                continuation = dict(origin.pending_continuation)
                continuation.update(
                    {
                        "continuation_id": (
                            continuation.get("continuation_id")
                            or worker.request.conversation_cursor
                        ),
                        "provider_profile_id": (
                            continuation.get("provider_profile_id")
                            or worker.request.provider_profile_id
                        ),
                        "model_id": (
                            continuation.get("model_id")
                            or worker.request.model_id
                        ),
                        "submitted_response": (
                            continuation.get("submitted_response")
                            or worker.request.user_message
                        ),
                        "last_attempt_failed": True,
                    }
                )
                origin = self._coordinator.update_state(
                    origin,
                    pending_continuation=continuation,
                )
            if (
                str(origin.document_job.get("status") or "")
                == JOB_PROVIDER_RUNNING
            ):
                origin = self._coordinator.update_state(
                    origin,
                    document_job={
                        **dict(origin.document_job),
                        "status": (
                            JOB_CANCELLED
                            if result.status == TURN_CANCELLED
                            else JOB_FAILED
                        ),
                    },
                )
            error_message = str(result.error.get("message") or "")
            cancelled = result.status == TURN_CANCELLED
            recovery_actions = (
                []
                if cancelled
                else [
                    {"id": "open_ai_settings", "label": "检查 AI 模型设置"},
                    {"id": "retry_provider_request", "label": "重新发送"},
                ]
            )
            origin = self._coordinator.append_message(
                origin,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="recovery",
                    title=(
                        "本次请求已取消"
                        if cancelled
                        else "模型响应未完成"
                    ),
                    body=(
                        "未执行任何文档生产操作。"
                        + (
                            f"\n原因：{provider_error_text(error_message)}"
                            if error_message
                            else ""
                        )
                    ),
                    payload={
                        "actions": recovery_actions,
                        "retry_text": worker.request.user_message,
                    },
                ),
                turn_status=result.status,
            )
        if self._active_session is not None and self._active_session.session_id == origin_session_id:
            self._active_session = origin
            self._render_active_session()
        self._refresh_session_list(select_session_id=origin_session_id)
        self._finish_turn_ui(worker)
        if result.status == TURN_COMPLETED and self._active_session is not None and self._active_session.session_id == origin_session_id:
            self._composer.focus_input()

    def _runtime_result_messages(
        self,
        result: AssistantRuntimeResult,
    ) -> tuple[AssistantMessage, ...]:
        """Project Flow result side channels into durable, actionable messages."""

        messages: list[AssistantMessage] = []
        continuation = dict(result.continuation_ref)
        if result.source_refs and not result.visible_text:
            messages.append(
                AssistantMessage.text(
                    role=ROLE_ASSISTANT,
                    text="已返回可核验来源。",
                    source_refs=result.source_refs,
                )
            )
        context_audit = result.provider_audit.get("context")
        if isinstance(context_audit, Mapping):
            raw_summaries = context_audit.get(
                "attachment_format_evidence_summaries"
            )
            summaries = (
                tuple(
                    dict(item)
                    for item in raw_summaries
                    if isinstance(item, Mapping)
                )
                if isinstance(raw_summaries, (list, tuple))
                else ()
            )
            for summary in summaries:
                direct_count = int(
                    summary.get("direct_paragraph_format_count") or 0
                ) + int(summary.get("direct_run_format_count") or 0)
                notices_list = []
                if str(summary.get("coverage_mode") or "") != "full":
                    notices_list.append(
                        "本轮发送的是格式证据摘要，不代表已覆盖全部样式明细。"
                    )
                if direct_count:
                    notices_list.append(
                        f"检测到 {direct_count} 处样式外直接格式，"
                        "AI回答必须将其视为待核验例外，不能自动提升为全局规范。"
                    )
                messages.append(
                    AssistantMessage.interaction(
                        role=ROLE_ASSISTANT,
                        interaction_type="format_evidence",
                        title="标准样稿格式证据已读取",
                        body="",
                        payload=format_evidence_payload(
                            summary,
                            notices=tuple(notices_list),
                        ),
                    )
                )
            raw_coverage = context_audit.get("attachment_coverage")
            coverage = (
                tuple(
                    dict(item)
                    for item in raw_coverage
                    if isinstance(item, Mapping)
                )
                if isinstance(raw_coverage, (list, tuple))
                else ()
            )
            incomplete = tuple(
                item
                for item in coverage
                if str(item.get("mode") or "") not in {"", "full"}
            )
            raw_errors = context_audit.get("attachment_errors")
            material_errors = (
                tuple(
                    dict(item)
                    for item in raw_errors
                    if isinstance(item, Mapping)
                )
                if isinstance(raw_errors, (list, tuple))
                else ()
            )
            if incomplete or material_errors:
                facts: list[dict[str, str]] = []
                for item in incomplete:
                    kind = str(item.get("kind") or "")
                    label = (
                        "附件正文"
                        if kind == "document_text"
                        else "格式证据"
                    )
                    facts.append(
                        {
                            "label": str(item.get("name") or label),
                            "value": (
                                f"{label}：{item.get('mode')}，"
                                f"已发送 {int(item.get('sent_characters') or 0)} / "
                                f"{int(item.get('total_characters') or 0)} 字符"
                            ),
                        }
                    )
                for item in material_errors:
                    facts.append(
                        {
                            "label": str(item.get("name") or "附件"),
                            "value": (
                                "读取失败："
                                + str(item.get("reason") or "unknown")
                            ),
                        }
                    )
                messages.append(
                    AssistantMessage.interaction(
                        role=ROLE_ASSISTANT,
                        interaction_type="boundary",
                        title="本轮材料覆盖范围有限",
                        body=(
                            "下列材料未被完整读取。本轮回答只能作为已覆盖范围内的"
                            "分析，不能视为全文或全部格式规则的最终结论。"
                        ),
                        payload={
                            "facts": facts,
                            "actions": [],
                        },
                    )
                )
        history_audit = result.provider_audit.get("history")
        if (
            isinstance(history_audit, Mapping)
            and history_audit.get("truncated")
        ):
            messages.append(
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="boundary",
                    title="本轮仅携带最近对话",
                    body=(
                        "较早历史因上下文预算未发送给模型；本轮回答不能被视为"
                        "覆盖全部历史。需要完整上下文时，请新建任务并粘贴必要摘要。"
                    ),
                    payload={
                        "facts": [
                            {
                                "label": "已发送",
                                "value": (
                                    f"{int(history_audit.get('sent_message_count') or 0)} "
                                    "条 / "
                                    f"{int(history_audit.get('sent_character_count') or 0)} "
                                    "字符"
                                ),
                            },
                            {
                                "label": "未发送",
                                "value": (
                                    f"{int(history_audit.get('omitted_message_count') or 0)} "
                                    "条 / "
                                    f"{int(history_audit.get('omitted_character_count') or 0)} "
                                    "字符"
                                ),
                            },
                        ],
                        "actions": [],
                    },
                )
            )
        for request in result.confirmation_requests:
            kind = str(request.get("kind") or request.get("type") or "question").casefold()
            is_permission = "permission" in kind or "approval" in kind
            actions = (
                []
                if is_permission
                else [{"id": "focus_continuation_response", "label": "填写回复"}]
            )
            body = str(
                request.get("body")
                or request.get("message")
                or request.get("prompt")
                or "请确认后继续。"
            )
            if is_permission:
                body += (
                    "\n\n当前文本模型连接没有可验证的 Tool Call 恢复通道，"
                    "因此本应用没有执行该操作。请改用不需要此权限的方案，"
                    "或在支持工具调用的 Provider 接入后重试。"
                )
            messages.append(
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="permission" if is_permission else "question",
                    title=str(request.get("title") or ("需要权限确认" if is_permission else "需要补充信息")),
                    body=body,
                    payload={
                        "actions": actions,
                        "confirmation_request": dict(request),
                        "continuation_ref": continuation,
                    },
                )
            )
        for action in result.proposed_actions:
            target = str(
                action.get("path")
                or action.get("url")
                or action.get("href")
                or ""
            ).strip()
            messages.append(
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="info",
                    title=str(action.get("title") or action.get("label") or "建议操作"),
                    body=str(action.get("description") or action.get("body") or "这是模型提出的后续建议。"),
                    payload={
                        "actions": (
                            [{"id": "runtime_open_reference", "label": "打开"}]
                            if target
                            else []
                        ),
                        "reference": dict(action),
                    },
                )
            )
        for artifact in result.artifacts:
            target = str(
                artifact.get("path")
                or artifact.get("url")
                or artifact.get("href")
                or ""
            ).strip()
            messages.append(
                AssistantMessage.artifact(
                    role=ROLE_ASSISTANT,
                    title=str(artifact.get("title") or artifact.get("name") or "生成的产物"),
                    body=str(artifact.get("description") or artifact.get("summary") or "产物已记录到当前对话。"),
                    reference=dict(artifact),
                    actions=(
                        ({"id": "runtime_open_reference", "label": "打开产物"},)
                        if target
                        else ()
                    ),
                )
            )
        if result.process_steps or result.public_reasoning_summary:
            summary_parts = [f"• {step}" for step in result.process_steps]
            if result.public_reasoning_summary:
                summary_parts.append(
                    f"\n公开推理摘要：{result.public_reasoning_summary}"
                )
            messages.append(
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="info",
                    title="处理摘要",
                    body="\n".join(summary_parts),
                    payload={
                        "actions": [],
                        "tool_audit": dict(result.tool_audit),
                        "citation_audit": dict(result.citation_audit),
                        "public_reasoning_summary": result.public_reasoning_summary,
                        "transcript_ref": dict(result.transcript_ref),
                    },
                )
            )
        return tuple(messages)
