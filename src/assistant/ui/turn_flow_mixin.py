"""Alavette Design-aligned AI document assistant panel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.assistant.adapters.workspace_state_adapter import snapshot_workspace
from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.application.attachment_policy import bind_policy_attachment_roles
from src.assistant.application.request_policy import (
    POLICY_DOCUMENT_ACTION,
    POLICY_NEEDS_ROUTE_CLARIFICATION,
    POLICY_RESPONSE_CLOSED,
    RequestPolicyDecision,
    evaluate_request_policy,
)
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.jobs import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_PROVIDER_RUNNING,
    JOB_RESPONSE_WAITING,
)
from src.assistant.contracts.material_snapshot import MaterialContextSnapshot
from src.assistant.contracts.permissions import DisclosureGrant
from src.assistant.contracts.messages import (
    ROLE_ASSISTANT,
    ROLE_USER,
    AssistantMessage,
)
from src.assistant.contracts.runtime import (
    AssistantTurnRequest,
    MAX_ASSISTANT_USER_MESSAGE_CHARACTERS,
    TURN_COMPLETED,
    TURN_WAITING_DATA_PERMISSION,
    TURN_WAITING_USER_QUESTION,
)
from src.assistant.domain.docx_format_evidence import (
    attachment_disclosure_fields,
    bind_attachment_semantic_roles,
)
from src.assistant.runtime.events import (
    EVENT_CONTEXT_READY,
    EVENT_MODEL_STARTED,
    EVENT_TEXT_DELTA,
    EVENT_TURN_CANCELLED,
    EVENT_TURN_FAILED,
    EVENT_TURN_FINISHED,
    EVENT_TURN_STARTED,
    EVENT_TURN_WAITING,
)
from src.assistant.runtime.providers.router import ProviderResolutionError
from src.assistant.runtime.turn_runner import attachment_fingerprints
from src.assistant.storage.models import AssistantSession
from src.assistant.ui.creative_home import AssistantHeroComposer
from src.assistant.ui.turn_completion_mixin import AssistantTurnCompletionMixin
from src.assistant.ui.workers import (
    AssistantTurnWorker,
)
from src.qt_api import (
    QTimer,
)
from src.config.material_context import MaterialExecutionContext


class AssistantTurnFlowMixin(AssistantTurnCompletionMixin):
    def _send_message(
        self,
        text: str,
        *,
        source: AssistantHeroComposer | None = None,
    ) -> bool:
        normalized = str(text or "").strip()
        if not normalized:
            return False
        if len(normalized) > MAX_ASSISTANT_USER_MESSAGE_CHARACTERS:
            reason = (
                f"单次需求最多 {MAX_ASSISTANT_USER_MESSAGE_CHARACTERS} 字符，"
                f"当前为 {len(normalized)} 字符；请精简或拆分后再发送，"
                "当前草稿已保留。"
            )
            self._composer.set_submission_gate(reason)
            self._empty_input.set_submission_gate(reason)
            return False
        current_session_id = (
            self._active_session.session_id
            if self._active_session is not None
            else ""
        )
        if current_session_id and current_session_id in self._turn_workers:
            if source is not None:
                source.set_submission_gate("当前对话正在生成回复，请等待完成或停止后再发送")
            self._sync_composer_busy_state()
            return False
        owner_session_id = self._running_operation_session_id()
        if owner_session_id:
            owner_label = self._operation_owner_label(owner_session_id)
            reason = f"{owner_label}正在处理，请等待完成或切回该对话停止任务"
            if source is not None:
                source.set_submission_gate(reason)
            self._sync_composer_busy_state()
            return False
        if self._active_session is None:
            profile_id, model_id = self._provider_selection.selected_identity()
            self._active_session = self._coordinator.create_session(
                provider_profile_id=profile_id,
                model_id=model_id,
            )
        else:
            self._active_session = self._provider_selection.synchronize_session(
                self._active_session
            )
        missing_refs = self._missing_context_refs_for_submission()
        if missing_refs:
            names = "、".join(
                str(item.get("title") or item.get("name") or Path(
                    str(item.get("path") or "")
                ).name or "DOCX 附件")
                for item in missing_refs
            )
            reason = (
                f"附件已失效：{names}。请重新选择存在的 DOCX 文档后再发送；"
                "当前草稿已保留。"
            )
            self._composer.set_submission_gate(reason)
            self._empty_input.set_submission_gate(reason)
            return False
        context_refs = bind_attachment_semantic_roles(
            self._context_refs_for_submission(),
            normalized,
        )
        pending_continuation = dict(self._active_session.pending_continuation)
        continuation_cursor = str(
            pending_continuation.get("continuation_id")
            or pending_continuation.get("cursor")
            or (
                pending_continuation.get("turn_id")
                if not str(pending_continuation.get("kind") or "").startswith("local_")
                else ""
            )
            or ""
        ).strip()
        retrying_continuation = bool(
            continuation_cursor
            and pending_continuation.get("last_attempt_failed")
            and str(
                pending_continuation.get("submitted_response") or ""
            ).strip()
            == normalized
        )
        if continuation_cursor:
            original_profile_id = str(
                pending_continuation.get("provider_profile_id") or ""
            ).strip()
            original_model_id = str(
                pending_continuation.get("model_id") or ""
            ).strip()
            if original_profile_id and original_model_id:
                self._active_session = self._coordinator.update_state(
                    self._active_session,
                    provider_profile_id=original_profile_id,
                    model_id=original_model_id,
                )
            pending_continuation.update(
                {
                    "submitted_response": normalized,
                    "provider_profile_id": (
                        original_profile_id
                        or self._active_session.provider_profile_id
                    ),
                    "model_id": (
                        original_model_id or self._active_session.model_id
                    ),
                    "last_attempt_failed": False,
                }
            )
        self._active_session = self._coordinator.update_state(
            self._active_session,
            context_refs=context_refs,
            pending_continuation=(
                pending_continuation if continuation_cursor else None
            ),
        )
        workspace = self._workspace_snapshot_for_session(self._active_session)
        material_context = self.bridge.current_material_context()
        material_snapshot = (
            material_context.clone()
            if isinstance(material_context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        if not continuation_cursor:
            policy = evaluate_request_policy(
                normalized,
                workspace_mode_id=workspace.mode_id,
                has_attachment=bool(context_refs),
            )
            context_refs = bind_policy_attachment_roles(context_refs, policy)
            self._active_session = self._coordinator.update_state(
                self._active_session,
                context_refs=context_refs,
            )
            if policy.kind in {
                POLICY_DOCUMENT_ACTION,
                POLICY_NEEDS_ROUTE_CLARIFICATION,
                POLICY_RESPONSE_CLOSED,
            }:
                self._handle_local_request_policy(
                    policy,
                    workspace=workspace,
                    material_snapshot=material_snapshot,
                    context_refs=context_refs,
                )
                return True
        disclosure_fields = attachment_disclosure_fields(context_refs)
        if context_refs and disclosure_fields:
            self._queue_provider_disclosure(
                query=normalized,
                context_refs=context_refs,
                workspace=workspace,
                material_snapshot=material_snapshot,
                continuation_cursor=continuation_cursor,
            )
            return True
        return self._start_provider_turn(
            query=normalized,
            context_refs=context_refs,
            workspace=workspace,
            material_snapshot=material_snapshot,
            continuation_cursor=continuation_cursor,
            append_user=not retrying_continuation,
            disclosure_grant=None,
        )

    def _queue_provider_disclosure(
        self,
        *,
        query: str,
        context_refs: tuple[dict[str, object], ...],
        workspace: WorkspaceSnapshot,
        material_snapshot: MaterialExecutionContext,
        continuation_cursor: str,
    ) -> None:
        session = self._active_session
        if session is None:
            return
        turn_id = uuid4().hex
        disclosure_id = uuid4().hex
        fields = attachment_disclosure_fields(context_refs)
        durable_material = MaterialContextSnapshot.capture(material_snapshot)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.text(
                role=ROLE_USER,
                text=query,
                source_refs=context_refs,
            ),
            turn_status=TURN_WAITING_DATA_PERMISSION,
        )
        continuation = {
            "kind": "local_provider_disclosure",
            "disclosure_id": disclosure_id,
            "turn_id": turn_id,
            "query": query,
            "context_refs": [dict(item) for item in context_refs],
            "workspace": workspace.to_dict(include_local_path=True),
            "continuation_cursor": continuation_cursor,
            "fields": list(fields),
            "material_snapshot": durable_material.to_dict(),
        }
        job = {
            **dict(session.document_job),
            "status": "needs_data_disclosure",
            "request_turn_id": turn_id,
            "disclosure_id": disclosure_id,
        }
        session = self._coordinator.update_state(
            session,
            pending_continuation=continuation,
            document_job=job,
            turn_status=TURN_WAITING_DATA_PERMISSION,
        )
        field_labels = {
            "document_text": "附件正文",
            "document_format_evidence": "格式结构证据",
        }
        file_names = "、".join(
            str(item.get("title") or item.get("name") or "DOCX 文档")
            for item in context_refs
        )
        target_attachment_required = any(
            bool(item.get("target_attachment_required"))
            for item in context_refs
        )
        scope_facts = (
            [
                {
                    "label": "本轮范围",
                    "value": (
                        "只分析标准样稿；目标文档尚未提供，"
                        "不会执行套用或生成"
                    ),
                }
            ]
            if target_attachment_required
            else []
        )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="disclosure",
                title="确认本次发送的材料范围",
                body=(
                    "确认后，仅把下面列出的内容发送给当前模型；本地路径和未列出的"
                    "生产资料不会发送。"
                    + (
                        "\n目标文档尚未提供，本轮只分析标准样稿并列出格式要求；"
                        "不会把样稿当作生产输入。"
                        if target_attachment_required
                        else ""
                    )
                ),
                payload={
                    "disclosure_id": disclosure_id,
                    "facts": [
                        {"label": "材料", "value": file_names or "DOCX 文档"},
                        {
                            "label": "发送内容",
                            "value": "、".join(
                                field_labels.get(field, field)
                                for field in fields
                            ),
                        },
                        *scope_facts,
                        *self._provider_disclosure_facts(session),
                    ],
                    "actions": [
                        {
                            "id": "approve_provider_disclosure",
                            "label": "同意并继续",
                            "variant": "primary",
                        },
                        {
                            "id": "deny_provider_disclosure",
                            "label": "不发送",
                            "variant": "secondary",
                        },
                    ],
                },
            ),
            turn_status=TURN_WAITING_DATA_PERMISSION,
        )
        self._active_session = session
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)

    def _resolve_provider_disclosure(
        self,
        payload: Mapping[str, object],
        *,
        approved: bool,
    ) -> None:
        session = self._active_session
        if session is None:
            return
        continuation = dict(session.pending_continuation)
        if continuation.get("kind") != "local_provider_disclosure":
            return
        expected_id = str(continuation.get("disclosure_id") or "")
        submitted_id = str(payload.get("disclosure_id") or "")
        if not expected_id or submitted_id != expected_id:
            return
        turn_id = str(continuation.get("turn_id") or "")
        if not approved:
            self._turn_material_snapshots.pop(turn_id, None)
            job = {
                **dict(session.document_job),
                "status": "response_closed",
                "disclosure_decision": "denied",
            }
            session = self._coordinator.update_state(
                session,
                pending_continuation={},
                document_job=job,
                turn_status=TURN_COMPLETED,
            )
            session = self._coordinator.append_message(
                session,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="boundary",
                    title="已停止发送材料",
                    body="未向模型发送附件内容，也未执行任何文档生产操作。",
                    payload={"actions": []},
                ),
                turn_status=TURN_COMPLETED,
            )
            self._active_session = session
            self._render_active_session()
            self._refresh_session_list(select_session_id=session.session_id)
            return
        workspace_payload = continuation.get("workspace")
        if not isinstance(workspace_payload, Mapping):
            return
        try:
            workspace = WorkspaceSnapshot.from_dict(workspace_payload)
        except (TypeError, ValueError):
            return
        context_refs = tuple(
            dict(item)
            for item in continuation.get("context_refs", ())
            if isinstance(item, Mapping)
        )
        raw_material = continuation.get("material_snapshot")
        try:
            material_snapshot = (
                MaterialContextSnapshot.from_dict(raw_material).restore()
                if isinstance(raw_material, Mapping)
                else MaterialExecutionContext()
            )
        except (TypeError, ValueError):
            return
        session = self._coordinator.update_state(
            session,
            pending_continuation={},
            document_job={
                **dict(session.document_job),
                "status": "provider_running",
                "disclosure_decision": "approved",
            },
            turn_status="provider_running",
        )
        self._active_session = session
        grant = self._disclosure_grant_for_turn(session, context_refs)
        self._start_provider_turn(
            query=str(continuation.get("query") or ""),
            context_refs=context_refs,
            workspace=workspace,
            material_snapshot=material_snapshot,
            continuation_cursor=str(
                continuation.get("continuation_cursor") or ""
            ),
            append_user=False,
            disclosure_grant=grant,
        )

    def _start_provider_turn(
        self,
        *,
        query: str,
        context_refs: tuple[dict[str, object], ...],
        workspace: WorkspaceSnapshot,
        material_snapshot: MaterialExecutionContext,
        continuation_cursor: str,
        append_user: bool,
        disclosure_grant: DisclosureGrant | None,
    ) -> bool:
        session = self._active_session
        if session is None:
            return False
        current_job_status = str(session.document_job.get("status") or "")
        if (
            current_job_status == JOB_RESPONSE_WAITING
            or (
                continuation_cursor
                and current_job_status in {JOB_FAILED, JOB_CANCELLED}
            )
        ):
            session = self._coordinator.update_state(
                session,
                document_job={
                    **dict(session.document_job),
                    "status": JOB_PROVIDER_RUNNING,
                },
            )
            self._active_session = session
        if append_user:
            session = self._coordinator.append_message(
                session,
                AssistantMessage.text(
                    role=ROLE_USER,
                    text=query,
                    source_refs=context_refs,
                ),
                turn_status="provider_running",
            )
            self._active_session = session
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)
        self._composer.set_busy(True)
        try:
            runner = self._runner_for_session(session)
        except ProviderResolutionError as exc:
            body = self._provider_selection.failure_message(
                session.provider_profile_id,
                exc,
            )
            recovery = AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="recovery",
                title="模型暂不可用",
                body=body,
                payload={
                    "actions": [
                        {"id": "open_ai_settings", "label": "打开 AI 模型设置"},
                        {"id": "retry_provider_request", "label": "重新发送"},
                    ],
                    "retry_text": query,
                },
            )
            pending = dict(session.pending_continuation)
            if continuation_cursor:
                pending["last_attempt_failed"] = True
            next_job = dict(session.document_job)
            if str(next_job.get("status") or "") == JOB_PROVIDER_RUNNING:
                next_job["status"] = JOB_FAILED
            session = self._coordinator.update_state(
                session,
                pending_continuation=pending,
                document_job=next_job,
            )
            self._active_session = self._coordinator.append_message(
                session,
                recovery,
                turn_status="blocked",
            )
            self._composer.set_busy(False)
            self._render_active_session()
            self._sync_composer_busy_state()
            return True
        turn_id = uuid4().hex
        request = AssistantTurnRequest(
            turn_id=turn_id,
            session_id=session.session_id,
            user_message=query,
            provider_profile_id=session.provider_profile_id,
            model_id=session.model_id,
            history=session.messages,
            local_context_refs=context_refs,
            disclosure_grant_id=(
                disclosure_grant.grant_id
                if disclosure_grant is not None
                else ""
            ),
            disclosure_grant=(
                disclosure_grant.to_dict()
                if disclosure_grant is not None
                else {}
            ),
            history_disclosure_grant=dict(
                session.provider_history_grant
            ),
            conversation_cursor=continuation_cursor,
        )
        worker = AssistantTurnWorker(runner, request, parent=self)
        worker.workspace_snapshot = workspace
        worker.material_context_snapshot = material_snapshot.clone()
        self._turn_material_snapshots[turn_id] = worker.material_context_snapshot
        self._turn_workers[session.session_id] = worker
        self._turn_worker = worker
        self._active_cancellation = worker.cancellation
        self._start_turn_preview(
            session_id=session.session_id,
            turn_id=turn_id,
        )
        self._render_active_session()
        worker.event_received.connect(
            lambda event, current=worker: self._on_turn_event(current, event)
        )
        worker.finished.connect(
            lambda result, current=worker: self._on_turn_finished(current, result)
        )
        worker.start()
        self._sync_composer_busy_state()
        return True

    def _handle_local_request_policy(
        self,
        policy: RequestPolicyDecision,
        *,
        workspace: WorkspaceSnapshot,
        material_snapshot: MaterialExecutionContext,
        context_refs: tuple[dict[str, object], ...],
    ) -> None:
        """Complete a deterministic Form decision without invoking a provider."""

        session = self._active_session
        if session is None:
            return
        turn_id = uuid4().hex
        session = self._coordinator.append_message(
            session,
            AssistantMessage.text(
                role=ROLE_USER,
                text=policy.query,
                source_refs=context_refs,
            ),
            turn_status="local_processing",
        )
        durable_material = MaterialContextSnapshot.capture(material_snapshot)
        if policy.kind == POLICY_NEEDS_ROUTE_CLARIFICATION:
            choice_rows = [choice.to_dict() for choice in policy.choices]
            continuation = {
                "kind": "local_route_clarification",
                "clarification_id": uuid4().hex,
                "turn_id": turn_id,
                "root_query": policy.query,
                "workspace": workspace.to_dict(include_local_path=True),
                "context_refs": [dict(item) for item in context_refs],
                "route_choices": choice_rows,
                "material_snapshot": durable_material.to_dict(),
            }
            job = {
                **dict(session.document_job),
                "status": "needs_route_clarification",
                "request_turn_id": turn_id,
                "route_status": policy.route_status,
            }
            session = self._coordinator.update_state(
                session,
                pending_continuation=continuation,
                document_job=job,
                turn_status=TURN_WAITING_USER_QUESTION,
            )
            session = self._coordinator.append_message(
                session,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="question",
                    title="确认文档任务",
                    body=policy.clarification_prompt,
                    payload={
                        "confirmation_request": {
                            "kind": "local_route_clarification",
                            "options": choice_rows,
                            "selection_mode": "single",
                            "allow_other": False,
                            "allow_skip": False,
                        },
                        "clarification_id": continuation["clarification_id"],
                    },
                ),
                turn_status=TURN_WAITING_USER_QUESTION,
            )
        elif policy.kind == POLICY_RESPONSE_CLOSED:
            session = self._append_local_boundary(
                session,
                policy,
                turn_id=turn_id,
            )
        else:
            session = self._create_local_form_plan(
                session,
                query=policy.query,
                turn_id=turn_id,
                workspace=workspace,
                material_snapshot=material_snapshot,
                route_id_override=policy.route_id,
            )
        self._active_session = session
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)

    def _append_local_boundary(
        self,
        session: AssistantSession,
        policy: RequestPolicyDecision,
        *,
        turn_id: str,
    ) -> AssistantSession:
        capability_status = policy.capability_status
        if capability_status == "gated":
            title = "该任务需要专业能力确认"
            body = (
                f"已识别为“{policy.route_label}”。当前核心文档助手不会自动执行该专业任务，"
                "也不会把已添加文档的正文发送给模型。"
            )
        else:
            title = "该文档生产链尚未开放"
            body = (
                f"已识别为“{policy.route_label}”。当前可以保留需求，但不会降级为通用"
                "文档任务，也不会生成不可验证的产物。"
            )
        job = {
            **dict(session.document_job),
            "status": "response_closed",
            "request_turn_id": turn_id,
            "route_id": policy.route_id,
            "route_label": policy.route_label,
            "capability_status": capability_status,
            "blocking_reason": policy.capability.blocking_reason,
        }
        session = self._coordinator.update_state(
            session,
            active_plan={},
            pending_continuation={},
            document_job=job,
            turn_status=TURN_COMPLETED,
        )
        return self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="boundary",
                title=title,
                body=body,
                payload={
                    "facts": [
                        {"label": "任务", "value": policy.route_label},
                        {
                            "label": "状态",
                            "value": (
                                "需要专业确认"
                                if capability_status == "gated"
                                else "尚未开放"
                            ),
                        },
                    ],
                    "actions": [],
                },
            ),
            turn_status=TURN_COMPLETED,
        )

    def _create_local_form_plan(
        self,
        session: AssistantSession,
        *,
        query: str,
        turn_id: str,
        workspace: WorkspaceSnapshot,
        material_snapshot: MaterialExecutionContext,
        route_id_override: str = "",
    ) -> AssistantSession:
        previous_plan = None
        if session.active_plan:
            try:
                previous_plan = DocumentPlan.from_dict(session.active_plan)
            except (TypeError, ValueError):
                previous_plan = None
        plan = self._document_jobs.draft_plan(
            query=query,
            workspace=workspace,
            turn_id=turn_id,
            previous_plan=previous_plan,
            route_id_override=route_id_override,
        )
        durable_material = MaterialContextSnapshot.capture(material_snapshot)
        plan = replace(
            plan,
            material_snapshot_ref=durable_material.reference(),
        )
        self._turn_material_snapshots.pop(turn_id, None)
        self._plan_material_snapshots[plan.plan_id] = material_snapshot.clone()
        job = {
            **dict(session.document_job),
            "job_id": uuid4().hex,
            "status": "plan_ready",
            "plan_id": plan.plan_id,
            "plan_revision": plan.revision,
            "plan_source": "form_local_policy",
            "request_turn_id": turn_id,
            "route_id": plan.capability_ref.route_id,
            "material_snapshot": durable_material.to_dict(),
        }
        session = self._coordinator.update_state(
            session,
            active_plan=plan.to_dict(),
            pending_continuation={},
            document_job=job,
            turn_status=TURN_COMPLETED,
        )
        return self._coordinator.append_message(
            session,
            self._plan_message(plan),
            turn_status=TURN_COMPLETED,
        )

    def _resolve_local_route_clarification(
        self,
        payload: Mapping[str, object],
    ) -> None:
        session = self._active_session
        if session is None:
            return
        continuation = dict(session.pending_continuation)
        if continuation.get("kind") != "local_route_clarification":
            return
        expected_id = str(continuation.get("clarification_id") or "")
        submitted_id = str(payload.get("clarification_id") or "")
        if not expected_id or submitted_id != expected_id:
            return
        selected_ids = tuple(
            str(item or "").strip()
            for item in payload.get("selected_choice_ids", ())
            if str(item or "").strip()
        )
        allowed = {
            str(item.get("id") or ""): str(item.get("label") or "")
            for item in continuation.get("route_choices", ())
            if isinstance(item, Mapping)
        }
        selected_id = selected_ids[0] if selected_ids else ""
        if selected_id not in allowed:
            return
        workspace_payload = continuation.get("workspace")
        if not isinstance(workspace_payload, Mapping):
            return
        try:
            workspace = WorkspaceSnapshot.from_dict(workspace_payload)
        except (TypeError, ValueError):
            return
        query = str(continuation.get("root_query") or "").strip()
        turn_id = str(continuation.get("turn_id") or uuid4().hex)
        context_refs = tuple(
            dict(item)
            for item in continuation.get("context_refs", ())
            if isinstance(item, Mapping)
        )
        raw_material = continuation.get("material_snapshot")
        try:
            material_snapshot = (
                MaterialContextSnapshot.from_dict(raw_material).restore()
                if isinstance(raw_material, Mapping)
                else MaterialExecutionContext()
            )
        except (TypeError, ValueError):
            return
        session = self._coordinator.append_message(
            session,
            AssistantMessage.text(
                role=ROLE_USER,
                text=allowed[selected_id],
                source_refs=context_refs,
            ),
            turn_status="local_processing",
        )
        policy = evaluate_request_policy(
            query,
            workspace_mode_id=workspace.mode_id,
            has_attachment=bool(context_refs),
            route_id_override=selected_id,
        )
        if policy.kind == POLICY_RESPONSE_CLOSED:
            session = self._append_local_boundary(
                session,
                policy,
                turn_id=turn_id,
            )
        else:
            session = self._create_local_form_plan(
                session,
                query=query,
                turn_id=turn_id,
                workspace=workspace,
                material_snapshot=material_snapshot,
                route_id_override=selected_id,
            )
        self._active_session = session
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)

    def _start_turn_preview(self, *, session_id: str, turn_id: str) -> None:
        normalized_session_id = str(session_id or "")
        self._turn_previews[normalized_session_id] = {
            "turn_id": str(turn_id or ""),
            "text": "",
            "status": "正在准备请求",
        }
        self._activate_turn_preview(normalized_session_id)

    def _context_refs_for_submission(self) -> tuple[dict[str, object], ...]:
        """Freeze explicitly selected local material into this turn and message."""

        if self._active_session is not None and self._active_session.context_refs:
            valid_refs: list[dict[str, object]] = []
            for reference in self._active_session.context_refs:
                path_text = str(reference.get("path") or "").strip()
                if path_text and Path(path_text).expanduser().is_file():
                    valid_refs.append(dict(reference))
            return tuple(valid_refs)
        composer = (
            self._composer
            if self._conversation_stack.currentWidget() is self._active_page
            else self._empty_input
        )
        return self._context_refs_for_path(composer.document_path())

    def _missing_context_refs_for_submission(
        self,
    ) -> tuple[dict[str, object], ...]:
        """Return explicitly selected attachment refs that no longer exist."""

        candidates: list[dict[str, object]] = []
        if self._active_session is not None and self._active_session.context_refs:
            candidates.extend(
                dict(reference)
                for reference in self._active_session.context_refs
                if isinstance(reference, Mapping)
            )
        else:
            composer = (
                self._composer
                if self._conversation_stack.currentWidget()
                is self._active_page
                else self._empty_input
            )
            path_text = str(composer.document_path() or "").strip()
            if path_text:
                candidates.append(
                    {
                        "path": path_text,
                        "name": Path(path_text).name,
                    }
                )
        return tuple(
            reference
            for reference in candidates
            if (
                str(reference.get("path") or "").strip()
                and not Path(
                    str(reference.get("path") or "")
                ).expanduser().is_file()
            )
        )

    @staticmethod
    def _context_refs_for_path(path_text: str) -> tuple[dict[str, object], ...]:
        normalized = str(path_text or "").strip()
        if not normalized:
            return ()
        path = Path(normalized).expanduser()
        if not path.is_file() or path.suffix.casefold() != ".docx":
            return ()
        return (
            {
                "type": "file",
                "source_type": "attachment",
                "title": path.name,
                "path": str(path.resolve()),
                "media_type": (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    if path.suffix.casefold() == ".docx"
                    else "application/octet-stream"
                ),
            },
        )

    @staticmethod
    def _disclosure_grant_for_turn(
        session: AssistantSession,
        context_refs: tuple[dict[str, object], ...],
    ) -> DisclosureGrant | None:
        if not context_refs:
            return None
        ref_ids = tuple(str(item.get("path") or "") for item in context_refs)
        return DisclosureGrant(
            grant_id=uuid4().hex,
            session_id=session.session_id,
            provider_id=session.provider_profile_id,
            model_id=session.model_id,
            allowed_refs=ref_ids,
            allowed_fields=attachment_disclosure_fields(context_refs),
            created_at=datetime.now(timezone.utc).isoformat(),
            scope="once",
            content_fingerprints=attachment_fingerprints(context_refs),
        )

    def _workspace_snapshot_for_session(
        self,
        session: AssistantSession,
    ) -> WorkspaceSnapshot:
        live = snapshot_workspace(self.bridge)
        path_text = ""
        for reference in session.context_refs:
            path_text = str(reference.get("path") or "").strip()
            if path_text:
                break
        if not path_text:
            return replace(
                live,
                input_path="",
                input_name="",
                input_exists=False,
            )
        path = Path(path_text).expanduser()
        return replace(
            live,
            input_path=str(path.resolve()) if path.exists() else str(path),
            input_name=path.name,
            input_exists=path.is_file(),
        )

    def _activate_turn_preview(self, session_id: str) -> None:
        normalized = str(session_id or "")
        state = self._turn_previews.get(normalized)
        if state is None:
            self._turn_preview_session_id = ""
            self._turn_preview_turn_id = ""
            self._turn_preview_text = ""
            self._turn_preview_status = ""
        else:
            self._turn_preview_session_id = normalized
            self._turn_preview_turn_id = state["turn_id"]
            self._turn_preview_text = state["text"]
            self._turn_preview_status = state["status"]
        self._turn_preview_widget = None

    def _clear_turn_preview(self, session_id: str = "") -> None:
        normalized = str(session_id or self._turn_preview_session_id or "")
        if normalized:
            self._turn_previews.pop(normalized, None)
        current_session_id = (
            self._active_session.session_id
            if self._active_session is not None
            else ""
        )
        if not normalized or normalized == current_session_id:
            self._activate_turn_preview(current_session_id)

    def _on_turn_event(self, worker: AssistantTurnWorker | object, event=None) -> None:
        if event is None:
            event = worker
            worker = self._turn_worker
        session_id = (
            worker.request.session_id
            if isinstance(worker, AssistantTurnWorker)
            else self._turn_preview_session_id
        )
        state = self._turn_previews.get(session_id)
        if state is None or str(getattr(event, "turn_id", "") or "") != state["turn_id"]:
            return
        event_type = str(getattr(event, "type", "") or "")
        status_by_type = {
            EVENT_TURN_STARTED: "正在理解你的要求",
            EVENT_CONTEXT_READY: "已整理当前文档上下文",
            EVENT_MODEL_STARTED: "模型正在生成",
            EVENT_TEXT_DELTA: "正在生成回复",
            EVENT_TURN_FINISHED: "回复生成完成",
            EVENT_TURN_FAILED: "模型响应未完成",
            EVENT_TURN_CANCELLED: "正在停止",
            EVENT_TURN_WAITING: "需要你的确认或补充",
        }
        if event_type == EVENT_TEXT_DELTA:
            state["text"] += str(getattr(event, "text_delta", "") or "")
        state["status"] = status_by_type.get(
            event_type,
            state["status"] or "正在处理",
        )
        if (
            self._active_session is None
            or self._active_session.session_id != session_id
        ):
            return
        self._turn_preview_session_id = session_id
        self._turn_preview_turn_id = state["turn_id"]
        self._turn_preview_text = state["text"]
        self._turn_preview_status = state["status"]
        if self._turn_preview_widget is None:
            self._render_active_session()
            return
        follow_output = self._is_near_latest()
        self._turn_preview_widget.set_live_state(
            text=self._turn_preview_text,
            status_text=self._turn_preview_status,
        )
        if follow_output:
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _finish_turn_ui(self, worker: AssistantTurnWorker) -> None:
        session_id = worker.request.session_id
        if self._turn_workers.get(session_id) is worker:
            self._turn_workers.pop(session_id, None)
        worker.deleteLater()
        self._sync_turn_worker_alias()
        self._clear_turn_preview(session_id)
        self._sync_composer_busy_state()
        if (
            (self._content_worker is None or not self._content_worker.is_running)
            and (self._preflight_worker is None or not self._preflight_worker.is_running)
            and (self._execution_worker is None or not self._execution_worker.is_running)
        ):
            self._stop_button.setVisible(False)

    def cancel_active_turn(self) -> None:
        if self._turn_worker is not None:
            self._turn_worker.cancel()
        current_session_id = (
            self._active_session.session_id
            if self._active_session is not None
            else ""
        )
        if self._content_worker is not None and self._worker_session_id(self._content_worker) == current_session_id:
            self._content_worker.cancel()
        if self._preflight_worker is not None and self._worker_session_id(self._preflight_worker) == current_session_id:
            self._preflight_worker.cancel()
        if self._execution_worker is not None and self._worker_session_id(self._execution_worker) == current_session_id:
            self._execution_worker.cancel()

    def _sync_composer_busy_state(self) -> None:
        self._sync_turn_worker_alias()
        owner_session_id = self._running_operation_session_id()
        current_session_id = (
            self._active_session.session_id
            if self._active_session is not None
            else ""
        )
        owns_local_operation = bool(owner_session_id and owner_session_id == current_session_id)
        owns_turn = self._turn_worker is not None
        gate = ""
        if owner_session_id and not owns_local_operation:
            gate = (
                f"{self._operation_owner_label(owner_session_id)}正在处理，"
                "请等待完成或切回该对话停止任务"
            )
        self._composer.set_submission_gate(gate)
        self._empty_input.set_submission_gate(gate)
        self._composer.set_busy(owns_local_operation or owns_turn)
        self._empty_input.set_busy(False)

    def _sync_turn_worker_alias(self) -> None:
        session_id = (
            self._active_session.session_id
            if self._active_session is not None
            else ""
        )
        self._turn_worker = self._turn_workers.get(session_id)
        self._active_cancellation = (
            self._turn_worker.cancellation if self._turn_worker is not None else None
        )

    @staticmethod
    def _worker_session_id(worker: object) -> str:
        request = getattr(worker, "request", None)
        return str(
            getattr(request, "session_id", "")
            or getattr(worker, "session_id", "")
            or ""
        ).strip()

    def _running_operation_session_id(self) -> str:
        workers = (
            self._content_worker,
            self._preflight_worker,
            self._execution_worker,
        )
        for worker in workers:
            if worker is None or not worker.is_running:
                continue
            request = getattr(worker, "request", None)
            session_id = str(getattr(request, "session_id", "") or "").strip()
            if not session_id:
                session_id = str(getattr(worker, "session_id", "") or "").strip()
            if session_id:
                return session_id
        return ""

    def _operation_owner_label(self, session_id: str) -> str:
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            return "另一对话"
        title = str(session.title or "").strip()
        return f"“{title}”" if title else "另一对话"

    def shutdown_active_execution(self, timeout_ms: int | None = None) -> bool:
        timeout = 5000 if timeout_ms is None else max(0, int(timeout_ms))
        turn_stopped = all(
            worker.shutdown(timeout)
            for worker in tuple(self._turn_workers.values())
        )
        content_stopped = (
            self._content_worker is None
            or self._content_worker.shutdown(timeout)
        )
        preflight_stopped = (
            self._preflight_worker is None
            or self._preflight_worker.shutdown(timeout)
        )
        execution_stopped = (
            self._execution_worker is None
            or self._execution_worker.shutdown(timeout)
        )
        return bool(
            turn_stopped
            and content_stopped
            and preflight_stopped
            and execution_stopped
        )
