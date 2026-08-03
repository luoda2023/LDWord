"""Completion and durable-result projection for assistant turns."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from urllib.parse import urlsplit

from src.assistant.application.template_authoring import (
    AssistantTemplateAuthoringCompletion,
    complete_template_authoring,
)
from src.assistant.contracts.jobs import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_PROVIDER_RUNNING,
    JOB_RESPONSE_READY,
    JOB_RESPONSE_WAITING,
)
from src.assistant.contracts.messages import ROLE_ASSISTANT, AssistantMessage
from src.assistant.contracts.runtime import (
    TURN_CANCELLED,
    TURN_COMPLETED,
    TURN_FAILED,
    TURN_WAITING_DATA_PERMISSION,
    TURN_WAITING_TOOL_PERMISSION,
    TURN_WAITING_USER_QUESTION,
    AssistantRuntimeResult,
)
from src.assistant.ui.provider_presentation import provider_error_text
from src.assistant.ui.runtime_result_presentation import format_evidence_payload
from src.assistant.ui.workers import AssistantTurnWorker


class AssistantTurnCompletionMixin:
    def _on_turn_finished(self, worker: AssistantTurnWorker, result) -> None:
        if self._turn_workers.get(worker.request.session_id) is not worker:
            return
        origin_session_id = worker.request.session_id
        if (
            self._active_session is not None
            and self._active_session.session_id == origin_session_id
        ):
            self._flush_active_turn_preview()
        self._clear_turn_preview(origin_session_id)
        try:
            origin = self._coordinator.load_session(origin_session_id)
        except (OSError, ValueError, TypeError):
            self._finish_turn_ui(worker)
            return
        template_authoring = None
        if (
            worker.request.template_authoring_mode_id
            and result.status == TURN_COMPLETED
        ):
            try:
                template_authoring = complete_template_authoring(
                    mode_id=worker.request.template_authoring_mode_id,
                    provider_text=result.visible_text,
                    strategy=worker.request.template_authoring_strategy,
                )
            except Exception as exc:
                template_authoring = exc
            result = replace(result, visible_text="")
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
            if str(origin.document_job.get("status") or "") == JOB_PROVIDER_RUNNING:
                origin = self._coordinator.update_state(
                    origin,
                    document_job={
                        **dict(origin.document_job),
                        "status": JOB_RESPONSE_WAITING,
                    },
                )
        elif worker.request.conversation_cursor and result.status == TURN_COMPLETED:
            origin = self._coordinator.update_state(
                origin,
                pending_continuation={},
            )
        for message in self._runtime_result_messages(
            result,
            pending_continuation=origin.pending_continuation,
        ):
            origin = self._coordinator.append_message(origin, message)
        if template_authoring is not None:
            for message in self._template_authoring_messages(template_authoring):
                origin = self._coordinator.append_message(origin, message)
        raw_runtime_results = origin.document_job.get("runtime_results", ())
        runtime_results = (
            [dict(item) for item in raw_runtime_results if isinstance(item, Mapping)]
            if isinstance(raw_runtime_results, (list, tuple))
            else []
        )
        runtime_results.append(result.to_dict())
        next_document_job = {
            **dict(origin.document_job),
            "runtime_results": runtime_results[-50:],
        }
        if template_authoring is not None:
            next_document_job["template_authoring"] = (
                self._template_authoring_job_payload(template_authoring)
            )
        origin = self._coordinator.update_state(
            origin,
            document_job=next_document_job,
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
                            continuation.get("model_id") or worker.request.model_id
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
            if str(origin.document_job.get("status") or "") == JOB_PROVIDER_RUNNING:
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
                    title=("本次请求已取消" if cancelled else "模型响应未完成"),
                    body=(
                        ""
                        if cancelled
                        else (
                            f"原因：{provider_error_text(error_message)}"
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
        origin = self._project_completion_read_state(origin)
        if (
            self._active_session is not None
            and self._active_session.session_id == origin_session_id
        ):
            self._active_session = origin
            self._render_active_session()
        self._refresh_session_list()
        self._finish_turn_ui(worker)
        if (
            result.status == TURN_COMPLETED
            and self._active_session is not None
            and self._active_session.session_id == origin_session_id
        ):
            self._composer.focus_input()

    def _template_authoring_messages(
        self,
        completion: AssistantTemplateAuthoringCompletion | Exception,
    ) -> tuple[AssistantMessage, ...]:
        """Project the host-validated template write, never the raw model JSON."""

        if isinstance(completion, Exception):
            return (
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="recovery",
                    title="模板未写入",
                    body=f"原因：{completion}",
                    payload={"actions": []},
                ),
            )

        batch = completion.batch
        if not batch.successes:
            reasons = [issue.message for issue in batch.rejections]
            reasons.extend(issue.message for issue in batch.warnings)
            if not reasons and batch.pending_count:
                reasons.append("模板来源归档仍在等待，尚未形成可核验的成功记录")
            retry_issue = next(
                (
                    issue
                    for issue in batch.rejections
                    if issue.source_path.suffix.casefold() == ".json"
                    and issue.source_path.is_file()
                ),
                None,
            )
            payload: dict[str, object] = {"actions": []}
            if retry_issue is not None:
                payload.update(
                    {
                        "template_authoring_mode_id": completion.mode_id,
                        "failed_result_path": str(retry_issue.source_path),
                        "actions": [
                            {
                                "id": "revalidate_template_authoring_failure",
                                "label": "重新校验已保留结果",
                                "variant": "secondary",
                            }
                        ],
                    }
                )
            return (
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="recovery",
                    title="模板未通过本地校验",
                    body=(
                        "原因：" + "\n".join(reasons)
                        if reasons
                        else ""
                    ),
                    payload=payload,
                ),
            )

        success = batch.successes[0]
        entry = success.entry
        strategy_label = {
            "requirements": "文本规范生成",
            "format_clone": "Word 格式克隆",
        }.get(completion.strategy, "历史结果重新校验")
        notices = [issue.message for issue in batch.warnings]
        observation_labels = {
            "master": "母版边界",
            "scene": "方案边界",
            "material": "资料边界",
            "unsupported": "未支持项",
        }
        for field_name, label in observation_labels.items():
            values = getattr(success.observations, field_name)
            notices.extend(f"{label}：{value}" for value in values)
        reference = {
            "path": str(entry.path),
            "title": entry.path.name,
            "description": "已写入当前模式的用户模板库",
            "kind": "template_config",
            "owner": "form",
        }
        self.bridge.template_library_events.import_completed.emit(
            completion.mode_id,
            batch,
        )
        return (
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="artifact",
                title="新模板已创建并写入模板库",
                body="",
                payload={
                    "facts": [
                        {"label": "模板名称", "value": entry.name},
                        {"label": "工作模式", "value": completion.mode_id},
                        {"label": "提取方式", "value": strategy_label},
                        {"label": "模板标识", "value": entry.config_id},
                    ],
                    "notices": notices[:8],
                    "reference": reference,
                    "actions": [
                        {
                            "id": "open_template_artifact",
                            "label": "打开模板文件",
                            "variant": "secondary",
                        }
                    ],
                },
            ),
        )

    @staticmethod
    def _template_authoring_job_payload(
        completion: AssistantTemplateAuthoringCompletion | Exception,
    ) -> dict[str, object]:
        if isinstance(completion, Exception):
            return {
                "status": "failed",
                "error": str(completion),
            }
        batch = completion.batch
        if batch.successes:
            entry = batch.successes[0].entry
            return {
                "status": "completed",
                "mode_id": completion.mode_id,
                "strategy": completion.strategy,
                "template_id": entry.config_id,
                "template_name": entry.name,
                "template_path": str(entry.path),
                "warning_count": len(batch.warnings),
            }
        return {
            "status": "failed",
            "mode_id": completion.mode_id,
            "strategy": completion.strategy,
            "issues": [
                issue.message
                for issue in (*batch.rejections, *batch.warnings)
            ],
        }

    def _runtime_result_messages(
        self,
        result: AssistantRuntimeResult,
        *,
        pending_continuation: Mapping[str, object] | None = None,
    ) -> tuple[AssistantMessage, ...]:
        """Project Flow result side channels into durable, actionable messages."""

        messages: list[AssistantMessage] = []
        continuation = dict(pending_continuation or result.continuation_ref)
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
            raw_summaries = context_audit.get("attachment_format_evidence_summaries")
            summaries = (
                tuple(dict(item) for item in raw_summaries if isinstance(item, Mapping))
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
                tuple(dict(item) for item in raw_coverage if isinstance(item, Mapping))
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
                tuple(dict(item) for item in raw_errors if isinstance(item, Mapping))
                if isinstance(raw_errors, (list, tuple))
                else ()
            )
            if incomplete or material_errors:
                facts: list[dict[str, str]] = []
                for item in incomplete:
                    kind = str(item.get("kind") or "")
                    label = "附件正文" if kind == "document_text" else "格式证据"
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
                                "读取失败：" + str(item.get("reason") or "unknown")
                            ),
                        }
                    )
                messages.append(
                    AssistantMessage.interaction(
                        role=ROLE_ASSISTANT,
                        interaction_type="boundary",
                        title="本轮材料覆盖范围有限",
                        body="",
                        payload={
                            "facts": [
                                *facts,
                                {
                                    "label": "结论范围",
                                    "value": "仅覆盖已读取内容",
                                },
                            ],
                            "actions": [],
                        },
                    )
                )
        history_audit = result.provider_audit.get("history")
        if isinstance(history_audit, Mapping) and history_audit.get("truncated"):
            messages.append(
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="boundary",
                    title="本轮仅携带最近对话",
                    body="",
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
                            {
                                "label": "需要完整上下文",
                                "value": "新建任务并粘贴必要摘要",
                            },
                        ],
                        "actions": [],
                    },
                )
            )
        for request in result.confirmation_requests:
            kind = str(
                request.get("kind") or request.get("type") or "question"
            ).casefold()
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
                or ""
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
                    title=str(
                        request.get("title")
                        or ("需要权限确认" if is_permission else "需要补充信息")
                    ),
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
                action.get("path") or action.get("url") or action.get("href") or ""
            ).strip()
            messages.append(
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="info",
                    title=str(action.get("title") or action.get("label") or "建议操作"),
                    body=str(
                        action.get("description")
                        or action.get("body")
                        or ""
                    ),
                    payload={
                        "actions": (
                            [{"id": "runtime_open_reference", "label": "打开"}]
                            if target and _provider_reference_is_openable(action)
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
                    title=str(
                        artifact.get("title") or artifact.get("name") or "生成的产物"
                    ),
                    body=str(
                        artifact.get("description")
                        or artifact.get("summary")
                        or ""
                    ),
                    reference=dict(artifact),
                    actions=(
                        ({"id": "runtime_open_reference", "label": "打开产物"},)
                        if target and _provider_reference_is_openable(artifact)
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


def _provider_reference_is_openable(reference: Mapping[str, object]) -> bool:
    """Provider side channels may open remote links, never local shell targets."""

    if any(
        str(reference.get(key) or "").strip()
        for key in ("path", "file_path", "local_path")
    ):
        return False
    target = str(
        reference.get("url") or reference.get("href") or reference.get("uri") or ""
    ).strip()
    return bool(
        target and urlsplit(target).scheme.casefold() in {"http", "https", "mailto"}
    )
