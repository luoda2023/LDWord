"""Reconcile durable assistant job state with execution journals at startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.assistant.application.execution_lease import ExecutionLeaseManager
from src.assistant.application.output_references import project_output_references
from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.contracts.messages import AssistantMessage, ROLE_ASSISTANT
from src.assistant.storage.execution_journal import ExecutionJournalStore


@dataclass(frozen=True, slots=True)
class RecoverySummary:
    recovered_terminal_jobs: int = 0
    interrupted_jobs: int = 0
    interrupted_turns: int = 0


class AssistantSessionRecovery:
    def __init__(
        self,
        coordinator: AssistantSessionCoordinator,
        journals: ExecutionJournalStore,
        leases: ExecutionLeaseManager,
    ) -> None:
        self.coordinator = coordinator
        self.journals = journals
        self.leases = leases

    def reconcile(self) -> RecoverySummary:
        recovered_terminal = 0
        interrupted_jobs = 0
        interrupted_turns = 0
        for summary in self.coordinator.list_sessions():
            try:
                session = self.coordinator.load_session(summary.session_id)
            except (OSError, ValueError, TypeError):
                continue
            job = dict(session.document_job)
            job_status = str(job.get("status") or "")
            execution_id = str(job.get("execution_id") or "")
            if job_status == "execution_running":
                journal = None
                if execution_id:
                    try:
                        journal = self.journals.load(execution_id)
                    except (OSError, ValueError, TypeError):
                        journal = None
                current = self.leases.current
                still_running = bool(
                    current is not None
                    and current.execution_id == execution_id
                    and current.session_id == session.session_id
                )
                if journal is not None and journal.status != "running":
                    result = dict(journal.result)
                    status = journal.status
                    primary_output_path = str(result.get("output_path") or "")
                    output_references = project_output_references(result)
                    if not primary_output_path and output_references:
                        primary_output_path = output_references[0]["path"]
                    actions = []
                    if (
                        status in {"success", "partial_success"}
                        and primary_output_path
                    ):
                        actions.append(
                            {"id": "runtime_open_reference", "label": "打开文档"}
                        )
                    job.update(
                        {
                            "status": status,
                            "result": result,
                            "primary_output_path": primary_output_path,
                            "recovered_from_journal": True,
                        }
                    )
                    session = self.coordinator.update_state(session, document_job=job)
                    session = self.coordinator.append_message(
                        session,
                        AssistantMessage.interaction(
                            role=ROLE_ASSISTANT,
                            interaction_type=(
                                "artifact"
                                if status in {"success", "partial_success"}
                                else "recovery"
                            ),
                            title="已恢复上次文档任务结果",
                            body=(
                                ""
                                if status in {"success", "partial_success"}
                                else f"应用已从本地执行记录恢复任务终态：{status}。"
                            ),
                            payload={
                                "execution_id": execution_id,
                                "actions": actions,
                                "reference": {
                                    "type": "file",
                                    "title": (
                                        Path(primary_output_path).name
                                        if primary_output_path
                                        else ""
                                    ),
                                    "path": primary_output_path,
                                },
                                "references": list(output_references),
                            },
                        ),
                    )
                    recovered_terminal += 1
                elif not still_running:
                    job.update(
                        {
                            "status": "failed",
                            "error_text": "assistant_execution_interrupted",
                            "recovery_required": True,
                        }
                    )
                    session = self.coordinator.update_state(session, document_job=job)
                    session = self.coordinator.append_message(
                        session,
                        AssistantMessage.interaction(
                            role=ROLE_ASSISTANT,
                            interaction_type="recovery",
                            title="上次文档任务已中断",
                            body=(
                                "未发现完整的成功回执，因此不会把任务误报为成功，也不会自动覆盖输出。"
                                "请重新执行本地检查后再确认生成。"
                            ),
                            payload={
                                "execution_id": execution_id,
                                "actions": [
                                    {"id": "retry_preflight", "label": "重新检查"}
                                ],
                            },
                        ),
                    )
                    interrupted_jobs += 1
            elif job_status == "preflight_running":
                job.update(
                    {
                        "status": "preflight_failed",
                        "error_text": "assistant_preflight_interrupted",
                        "recovery_required": True,
                    }
                )
                session = self.coordinator.update_state(session, document_job=job)
                session = self.coordinator.append_message(
                    session,
                    AssistantMessage.interaction(
                        role=ROLE_ASSISTANT,
                        interaction_type="recovery",
                        title="上次执行前检查已中断",
                        body="没有执行文档生产。请重新检查当前题稿、方案、模板和输出目录。",
                        payload={
                            "actions": [
                                {"id": "retry_preflight", "label": "重新检查"}
                            ]
                        },
                    ),
                )
                interrupted_jobs += 1
            elif job_status == "content_generation_running":
                job.update(
                    {
                        "status": "failed",
                        "error_text": "assistant_content_generation_interrupted",
                        "recovery_required": True,
                    }
                )
                session = self.coordinator.update_state(session, document_job=job)
                session = self.coordinator.append_message(
                    session,
                    AssistantMessage.interaction(
                        role=ROLE_ASSISTANT,
                        interaction_type="recovery",
                        title="上次内容起草已中断",
                        body="未完成的模型输出不会作为文档输入；可以从原计划重新生成草稿。",
                        payload={
                            "actions": [
                                {
                                    "id": "generate_content_draft",
                                    "label": "重新生成内容草稿",
                                }
                            ]
                        },
                    ),
                )
                interrupted_jobs += 1
            elif job_status == "content_generation_ready":
                job.update(
                    {
                        "status": "plan_ready",
                        "error_text": "assistant_content_generation_not_started",
                        "recovery_required": True,
                    }
                )
                session = self.coordinator.update_state(
                    session,
                    document_job=job,
                    turn_status="completed",
                )
                session = self.coordinator.append_message(
                    session,
                    AssistantMessage.interaction(
                        role=ROLE_ASSISTANT,
                        interaction_type="recovery",
                        title="内容生成尚未开始",
                        body="上次已完成材料授权，但内容生成尚未真正启动；原计划仍保留。",
                        payload={
                            "actions": [
                                {
                                    "id": "generate_content_draft",
                                    "label": "继续生成内容草稿",
                                }
                            ]
                        },
                    ),
                )
                interrupted_jobs += 1
            elif (
                job_status == "needs_official_field_completion"
                and session.pending_continuation.get("kind")
                != "official_field_completion"
            ):
                job.update(
                    {
                        "status": "failed",
                        "error_text": "assistant_official_field_completion_interrupted",
                        "recovery_required": True,
                    }
                )
                session = self.coordinator.update_state(
                    session,
                    document_job=job,
                    turn_status="failed",
                )
                session = self.coordinator.append_message(
                    session,
                    AssistantMessage.interaction(
                        role=ROLE_ASSISTANT,
                        interaction_type="recovery",
                        title="公文字段补充已中断",
                        body="缺失字段的确认记录不完整，没有把未确认草稿送入正式生产。",
                        payload={
                            "actions": [
                                {
                                    "id": "generate_content_draft",
                                    "label": "重新生成内容草稿",
                                }
                            ]
                        },
                    ),
                )
                interrupted_jobs += 1
            if session.turn_status == "provider_running":
                interrupted_job = dict(session.document_job)
                if str(interrupted_job.get("status") or "") == "provider_running":
                    interrupted_job.update(
                        {
                            "status": "failed",
                            "error_text": "assistant_provider_turn_interrupted",
                            "recovery_required": True,
                        }
                    )
                retry_text = next(
                    (
                        message.visible_text()
                        for message in reversed(session.messages)
                        if message.role == "user" and message.visible_text()
                    ),
                    "",
                )
                session = self.coordinator.update_state(
                    session,
                    turn_status="failed",
                    document_job=interrupted_job,
                )
                session = self.coordinator.append_message(
                    session,
                    AssistantMessage.interaction(
                        role=ROLE_ASSISTANT,
                        interaction_type="recovery",
                        title="上次 AI 回复已中断",
                        body="未完成的流式回复不会继续拼接；可以重新发送上一条请求。",
                        payload={
                            "actions": (
                                [
                                    {
                                        "id": "retry_provider_request",
                                        "label": "重新发送",
                                    }
                                ]
                                if retry_text
                                else []
                            ),
                            "retry_text": retry_text,
                        },
                    ),
                )
                interrupted_turns += 1
        return RecoverySummary(
            recovered_terminal_jobs=recovered_terminal,
            interrupted_jobs=interrupted_jobs,
            interrupted_turns=interrupted_turns,
        )


__all__ = ["AssistantSessionRecovery", "RecoverySummary"]
