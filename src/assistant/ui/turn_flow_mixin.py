"""LDWord AI document assistant panel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from src.application.materials import (
    ExecutionMaterialSnapshot,
    bind_repository_material_run,
)
from src.assistant.adapters.workspace_state_adapter import (
    WorkspaceSnapshot,
)
from src.assistant.application.active_document_continuation import (
    is_active_document_revision_request,
    resolve_active_document_continuation,
)
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
    JOB_NEEDS_EXECUTION_APPROVAL,
    JOB_PREFLIGHT_FAILED,
    JOB_PROVIDER_RUNNING,
    JOB_RESPONSE_WAITING,
)
from src.assistant.contracts.material_snapshot import MaterialExecutionEnvelope
from src.assistant.contracts.messages import (
    ROLE_ASSISTANT,
    ROLE_USER,
    AssistantMessage,
)
from src.assistant.contracts.permissions import DisclosureGrant
from src.assistant.contracts.runtime import (
    MAX_ASSISTANT_USER_MESSAGE_CHARACTERS,
    TURN_COMPLETED,
    TURN_WAITING_DATA_PERMISSION,
    TURN_WAITING_USER_QUESTION,
    AssistantTurnRequest,
)
from src.assistant.domain.docx_format_evidence import (
    TEMPLATE_AUTHORING_FORMAT_CLONE,
    TEMPLATE_AUTHORING_REQUIREMENTS,
    attachment_disclosure_fields,
    bind_attachment_semantic_roles,
    is_template_authoring_request,
    resolve_template_authoring_strategy,
)
from src.assistant.domain.exam_authoring_contract import (
    exam_request_clarification,
)
from src.assistant.runtime.providers.router import ProviderResolutionError
from src.assistant.storage.models import AssistantSession
from src.assistant.ui.creative_home import AssistantHeroComposer
from src.assistant.ui.exam_clarification_mixin import AssistantExamClarificationMixin
from src.assistant.ui.official_clarification_mixin import (
    AssistantOfficialClarificationMixin,
    official_request_needs_intake,
)
from src.assistant.ui.turn_completion_mixin import AssistantTurnCompletionMixin
from src.assistant.ui.turn_preview_mixin import AssistantTurnPreviewMixin
from src.assistant.ui.workers import (
    AssistantTurnWorker,
)
from src.config.material_package_library import material_package_repository
from src.config.work_mode import get_work_mode

_ASSISTANT_ATTACHMENT_MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".wps": "application/vnd.ms-works",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


class AssistantTurnFlowMixin(
    AssistantOfficialClarificationMixin,
    AssistantExamClarificationMixin,
    AssistantTurnCompletionMixin,
    AssistantTurnPreviewMixin,
):
    _DOCUMENT_RECOVERY_COMMANDS = frozenset(
        {
            "转为文档任务",
            "按刚才的需求生成文档",
            "把刚才的内容做成word",
            "把刚才的内容做成docx",
            "根据刚才的需求创建文档",
            "将刚才的需求转成文档",
        }
    )

    def _current_execution_material_snapshot(
        self,
    ) -> ExecutionMaterialSnapshot | None:
        selection = self.bridge.current_material_run_selection()
        if selection is None:
            return None
        mode_id = self.bridge.current_work_mode_id()
        result = bind_repository_material_run(
            material_package_repository(),
            selection,
            work_mode_id=mode_id,
            recipe_id="document_batch",
            scene_id=self.bridge.current_scene_id(),
            document_type=(
                self.bridge.current_official_document_type_id()
                if mode_id == "official"
                else ""
            ),
        )
        if not result.ok:
            self.bridge.set_current_material_issues(result.issues)
            return None
        return result.snapshot

    def _send_message(
        self,
        text: str,
        *,
        source: AssistantHeroComposer | None = None,
        context_refs_override: tuple[dict[str, object], ...] | None = None,
    ) -> bool:
        accepted = self._submit_message(
            text,
            source=source,
            context_refs_override=context_refs_override,
        )
        if accepted:
            self._consume_submitted_context_refs()
        return accepted

    def _submit_message(
        self,
        text: str,
        *,
        source: AssistantHeroComposer | None = None,
        context_refs_override: tuple[dict[str, object], ...] | None = None,
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
        if context_refs_override is None:
            submission_refs = self._context_refs_for_submission()
            missing_refs = self._missing_context_refs_for_submission()
        else:
            submission_refs = tuple(
                dict(item)
                for item in context_refs_override
                if isinstance(item, Mapping)
            )
            missing_refs = self._missing_context_refs_for_submission(
                submission_refs
            )
        if missing_refs:
            names = "、".join(
                str(item.get("title") or item.get("name") or Path(
                    str(item.get("path") or "")
                    ).name or "文档材料")
                for item in missing_refs
            )
            reason = (
                f"附件已失效：{names}。请重新选择存在的文档材料后再发送；"
                "当前草稿已保留。"
            )
            self._composer.set_submission_gate(reason)
            self._empty_input.set_submission_gate(reason)
            return False
        context_refs = bind_attachment_semantic_roles(
            submission_refs,
            normalized,
        )
        template_authoring_requested = is_template_authoring_request(normalized)
        template_authoring_strategy = resolve_template_authoring_strategy(
            normalized
        )
        template_source_is_valid = bool(
            len(context_refs) == 1
            and Path(
                str(
                    context_refs[0].get("path")
                    or context_refs[0].get("file_path")
                    or context_refs[0].get("local_path")
                    or ""
                )
            ).suffix.casefold()
            == ".docx"
        )
        if template_authoring_requested and not template_source_is_valid:
            self._close_template_authoring_without_single_source(
                query=normalized,
                context_refs=context_refs,
            )
            return True
        if template_authoring_requested and not template_authoring_strategy:
            self._close_template_authoring_without_strategy(
                query=normalized,
                context_refs=context_refs,
            )
            return True
        if self._recover_previous_request_as_document(
            normalized,
            context_refs=context_refs,
        ):
            return True
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
            consume_draft=retrying_continuation,
        )
        active_plan = None
        if self._active_session.active_plan:
            try:
                active_plan = DocumentPlan.from_dict(
                    self._active_session.active_plan
                )
            except (TypeError, ValueError):
                active_plan = None
        job_status = str(
            self._active_session.document_job.get("status") or ""
        )
        pending_kind = str(
            self._active_session.pending_continuation.get("kind") or ""
        )
        active_continuation = resolve_active_document_continuation(
            normalized,
            job_status=job_status,
            has_active_plan=active_plan is not None,
            pending_kind=pending_kind,
            generation_pending=bool(
                active_plan is not None
                and active_plan.generation_required
                and active_plan.production_input_artifact is None
            ),
        )
        if active_continuation is not None:
            return self._dispatch_document_action(
                active_continuation.action_id,
                user_text=normalized,
                source_refs=context_refs,
            )
        preserve_active_draft = bool(
            active_plan is not None
            and is_active_document_revision_request(
                normalized,
                job_status=job_status,
            )
        )
        if (
            preserve_active_draft
            and job_status == JOB_NEEDS_EXECUTION_APPROVAL
        ):
            invalidated_job = dict(self._active_session.document_job)
            invalidated_job.pop("preflight", None)
            invalidated_job.update(
                {
                    "status": JOB_PREFLIGHT_FAILED,
                    "preflight_invalidated_reason": (
                        "assistant_draft_revision_requested"
                    ),
                }
            )
            self._active_session = self._coordinator.update_state(
                self._active_session,
                document_job=invalidated_job,
            )
        workspace = self._workspace_snapshot_for_session(self._active_session)
        material_snapshot = self._current_execution_material_snapshot()
        policy = evaluate_request_policy(
            normalized,
            workspace_mode_id=workspace.mode_id,
            has_attachment=bool(context_refs),
        )
        template_authoring_mode_id = ""
        if template_authoring_requested:
            routed_mode_id = str(policy.capability.mode_id or "").strip()
            template_authoring_mode_id = routed_mode_id or workspace.mode_id
        local_policy_kinds = {
            POLICY_DOCUMENT_ACTION,
            POLICY_NEEDS_ROUTE_CLARIFICATION,
            POLICY_RESPONSE_CLOSED,
        }
        if (
            continuation_cursor
            and not preserve_active_draft
            and policy.kind in local_policy_kinds
        ):
            # A provider question owns only its answer, not every later turn in
            # the conversation.  A fresh deterministic document request
            # supersedes that cursor and is routed through Form again.
            interrupted_job = dict(self._active_session.document_job)
            interrupted_job_update = None
            if str(interrupted_job.get("status") or "") == JOB_RESPONSE_WAITING:
                interrupted_job.update(
                    {
                        "status": JOB_CANCELLED,
                        "superseded_continuation_id": continuation_cursor,
                        "superseded_reason": "new_local_document_request",
                    }
                )
                interrupted_job_update = interrupted_job
            self._active_session = self._coordinator.update_state(
                self._active_session,
                pending_continuation={},
                document_job=interrupted_job_update,
                turn_status=TURN_COMPLETED,
            )
            continuation_cursor = ""
        if not continuation_cursor and not preserve_active_draft:
            context_refs = bind_policy_attachment_roles(context_refs, policy)
            self._active_session = self._coordinator.update_state(
                self._active_session,
                context_refs=context_refs,
            )
            if policy.kind in local_policy_kinds:
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
                template_authoring_mode_id=template_authoring_mode_id,
                template_authoring_strategy=template_authoring_strategy,
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
            template_authoring_mode_id=template_authoring_mode_id,
            template_authoring_strategy=template_authoring_strategy,
        )

    def _consume_submitted_context_refs(self) -> None:
        """Clear only pending composer materials after a turn accepts them."""

        session = self._active_session
        if session is not None and session.context_refs:
            try:
                self._active_session = self._coordinator.update_state(
                    session,
                    context_refs=(),
                    touch_activity=False,
                )
            except (OSError, RuntimeError, TypeError, ValueError):
                # The message/request already owns an immutable copy. Never
                # leave the in-memory composer pointing at a consumed file.
                self._active_session = replace(session, context_refs=())
        self._empty_input.set_document_paths(())
        self._composer.set_document_paths(())

    def _recover_previous_request_as_document(
        self,
        command: str,
        *,
        context_refs: tuple[dict[str, object], ...],
    ) -> bool:
        """Give a misrouted provider conversation an explicit local escape hatch."""

        session = self._active_session
        compact = "".join(str(command or "").casefold().split())
        if (
            session is None
            or session.active_plan
            or compact not in self._DOCUMENT_RECOVERY_COMMANDS
        ):
            return False
        previous_query = next(
            (
                message.visible_text().strip()
                for message in reversed(session.messages)
                if message.role == ROLE_USER and message.visible_text().strip()
            ),
            "",
        )
        if not previous_query:
            return False
        workspace = self._workspace_snapshot_for_session(session)
        policy = evaluate_request_policy(
            previous_query,
            workspace_mode_id=workspace.mode_id,
            has_attachment=bool(context_refs),
        )
        if policy.kind not in {
            POLICY_DOCUMENT_ACTION,
            POLICY_NEEDS_ROUTE_CLARIFICATION,
            POLICY_RESPONSE_CLOSED,
        }:
            previous_query = "生成一份文档，具体要求如下：" + previous_query
            policy = evaluate_request_policy(
                previous_query,
                workspace_mode_id=workspace.mode_id,
                has_attachment=bool(context_refs),
            )
        if policy.kind not in {
            POLICY_DOCUMENT_ACTION,
            POLICY_NEEDS_ROUTE_CLARIFICATION,
            POLICY_RESPONSE_CLOSED,
        }:
            return False
        bound_refs = bind_policy_attachment_roles(context_refs, policy)
        self._active_session = self._coordinator.update_state(
            session,
            context_refs=bound_refs,
            pending_continuation={},
        )
        self._handle_local_request_policy(
            policy,
            workspace=workspace,
            material_snapshot=self._current_execution_material_snapshot(),
            context_refs=bound_refs,
        )
        return True

    def _close_template_authoring_without_single_source(
        self,
        *,
        query: str,
        context_refs: tuple[dict[str, object], ...],
    ) -> None:
        """Fail closed before provider disclosure when the source is ambiguous."""

        session = self._active_session
        if session is None:
            return
        session = self._coordinator.append_message(
            session,
            AssistantMessage.text(
                role=ROLE_USER,
                text=query,
                source_refs=context_refs,
            ),
            turn_status=TURN_COMPLETED,
            consume_draft=True,
        )
        single_non_docx = bool(
            len(context_refs) == 1
            and Path(
                str(
                    context_refs[0].get("path")
                    or context_refs[0].get("file_path")
                    or context_refs[0].get("local_path")
                    or ""
                )
            ).suffix.casefold()
            != ".docx"
        )
        body = (
            "请先上传一份 DOCX 规范文档或标准样稿，并明确选择“按照文本要求"
            "生成模板”或“克隆 Word 格式生成模板”。两种功能不会混合读取。"
            if not context_refs
            else (
                "模板创作的来源必须是 DOCX，Markdown 或其他附件不能提供完整的"
                "Word 样式、分节和页面结构证据。请改为上传一份 DOCX 后重试。"
                if single_non_docx
                else (
                    "一次模板创作只能绑定一份来源 DOCX，以免不同规范相互覆盖。"
                    "请只保留要作为模板依据的那一份后重试。"
                )
            )
        )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="boundary",
                title="请选择一份模板来源 DOCX",
                body=body,
                payload={"actions": []},
            ),
            turn_status=TURN_COMPLETED,
        )
        self._active_session = self._coordinator.update_state(
            session,
            context_refs=context_refs,
            pending_continuation={},
            document_job={
                **dict(session.document_job),
                "status": "response_closed",
                "reason": "template_authoring_requires_single_docx",
            },
            turn_status=TURN_COMPLETED,
        )
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)

    def _close_template_authoring_without_strategy(
        self,
        *,
        query: str,
        context_refs: tuple[dict[str, object], ...],
    ) -> None:
        """Require an explicit evidence source; never silently blend both."""

        session = self._active_session
        if session is None:
            return
        session = self._coordinator.append_message(
            session,
            AssistantMessage.text(
                role=ROLE_USER,
                text=query,
                source_refs=context_refs,
            ),
            turn_status=TURN_COMPLETED,
            consume_draft=True,
        )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="boundary",
                title="请选择一种模板提取方式",
                body=(
                    "两种功能相互独立，不能在同一次模板创作中混用：\n"
                    "1. 按照文本要求生成模板：只读取附件正文中的明确规范条款；\n"
                    "2. 克隆 Word 格式生成模板：只读取 DOCX 格式结构证据。\n"
                    "请在请求中明确写出其中一种方式后重新发送。"
                ),
                payload={"actions": []},
            ),
            turn_status=TURN_COMPLETED,
        )
        self._active_session = self._coordinator.update_state(
            session,
            context_refs=context_refs,
            pending_continuation={},
            document_job={
                **dict(session.document_job),
                "status": "response_closed",
                "reason": "template_authoring_strategy_required",
            },
            turn_status=TURN_COMPLETED,
        )
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)

    def _queue_provider_disclosure(
        self,
        *,
        query: str,
        context_refs: tuple[dict[str, object], ...],
        workspace: WorkspaceSnapshot,
        material_snapshot: ExecutionMaterialSnapshot | None,
        continuation_cursor: str,
        template_authoring_mode_id: str = "",
        template_authoring_strategy: str = "",
    ) -> None:
        session = self._active_session
        if session is None:
            return
        turn_id = uuid4().hex
        disclosure_id = uuid4().hex
        fields = attachment_disclosure_fields(context_refs)
        template_authoring_requested = is_template_authoring_request(query)
        durable_material = MaterialExecutionEnvelope.capture(material_snapshot)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.text(
                role=ROLE_USER,
                text=query,
                source_refs=context_refs,
            ),
            turn_status=TURN_WAITING_DATA_PERMISSION,
            consume_draft=True,
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
            "template_authoring_mode_id": template_authoring_mode_id,
            "template_authoring_strategy": template_authoring_strategy,
        }
        job = {
            **dict(session.document_job),
            "status": "needs_data_disclosure",
            "request_turn_id": turn_id,
            "disclosure_id": disclosure_id,
            "operation": (
                "template_authoring"
                if template_authoring_requested
                else "provider_response"
            ),
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
        if template_authoring_requested:
            target_mode = get_work_mode(template_authoring_mode_id)
            target_mode_label = (
                str(getattr(target_mode, "label", "") or "").strip()
                or template_authoring_mode_id
                or workspace.mode_label
            )
            scope_facts.append(
                {
                    "label": "写入目标",
                    "value": f"{target_mode_label}用户模板库（新增模板）",
                }
            )
            strategy_label = {
                TEMPLATE_AUTHORING_REQUIREMENTS: "文本规范生成（只读正文要求）",
                TEMPLATE_AUTHORING_FORMAT_CLONE: "Word 格式克隆（只读格式结构）",
            }.get(template_authoring_strategy, "未选择")
            scope_facts.append(
                {
                    "label": "提取方式",
                    "value": strategy_label,
                }
            )
            scope_facts.append(
                {
                    "label": "写入条件",
                    "value": "通过本地合同、字段边界和无损读回校验",
                }
            )
            if template_authoring_mode_id != workspace.mode_id:
                scope_facts.append(
                    {
                        "label": "模式识别",
                        "value": (
                            f"当前界面为{workspace.mode_label}，"
                            f"本次请求识别为{target_mode_label}"
                        ),
                    }
                )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="disclosure",
                title="确认本次发送的材料范围",
                body="",
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
                    body="",
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
                MaterialExecutionEnvelope.from_dict(raw_material).restore()
                if isinstance(raw_material, Mapping)
                else None
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
            template_authoring_mode_id=str(
                continuation.get("template_authoring_mode_id") or ""
            ),
            template_authoring_strategy=str(
                continuation.get("template_authoring_strategy") or ""
            ),
        )

    def _start_provider_turn(
        self,
        *,
        query: str,
        context_refs: tuple[dict[str, object], ...],
        workspace: WorkspaceSnapshot,
        material_snapshot: ExecutionMaterialSnapshot | None,
        continuation_cursor: str,
        append_user: bool,
        disclosure_grant: DisclosureGrant | None,
        template_authoring_mode_id: str = "",
        template_authoring_strategy: str = "",
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
                consume_draft=True,
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
            template_authoring_mode_id=(
                template_authoring_mode_id or workspace.mode_id
                if is_template_authoring_request(query)
                else ""
            ),
            template_authoring_strategy=(
                template_authoring_strategy
                if is_template_authoring_request(query)
                else ""
            ),
        )
        worker = AssistantTurnWorker(runner, request, parent=self)
        worker.workspace_snapshot = workspace
        worker.material_snapshot = material_snapshot
        self._turn_material_snapshots[turn_id] = worker.material_snapshot
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
        material_snapshot: ExecutionMaterialSnapshot | None,
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
            consume_draft=True,
        )
        durable_material = MaterialExecutionEnvelope.capture(material_snapshot)
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
            official_clarification_required = bool(
                policy.operation == "author"
                and policy.capability.mode_id == "official"
                and official_request_needs_intake(
                    policy.query,
                    document_type_id=(
                        workspace.document_type_id
                        if workspace.mode_id == "official"
                        else ""
                    ),
                )
            )
            exam_clarification = (
                exam_request_clarification(policy.query)
                if policy.operation == "author"
                and policy.capability.mode_id == "exam"
                else None
            )
            if official_clarification_required:
                session = self._queue_local_official_clarification(
                    session,
                    query=policy.query,
                    turn_id=turn_id,
                    workspace=workspace,
                    material_snapshot=material_snapshot,
                    context_refs=context_refs,
                    route_id_override=policy.route_id,
                )
            elif exam_clarification is not None:
                session = self._queue_local_exam_clarification(
                    session,
                    query=policy.query,
                    turn_id=turn_id,
                    workspace=workspace,
                    material_snapshot=material_snapshot,
                    context_refs=context_refs,
                    route_id_override=policy.route_id,
                    clarification=exam_clarification,
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
            outcome = "未发送材料，也未生成产物"
        else:
            title = "该文档生产链尚未开放"
            outcome = "保留需求，不降级生成"
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
                body="",
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
                        {"label": "处理结果", "value": outcome},
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
        material_snapshot: ExecutionMaterialSnapshot | None,
        route_id_override: str = "",
        scene_ref_updates: Mapping[str, object] | None = None,
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
        if scene_ref_updates:
            plan = replace(
                plan,
                scene_ref={
                    **dict(plan.scene_ref),
                    **dict(scene_ref_updates),
                },
            )
        durable_material = MaterialExecutionEnvelope.capture(material_snapshot)
        plan = replace(
            plan,
            material_snapshot_ref=durable_material.reference(),
        )
        self._turn_material_snapshots.pop(turn_id, None)
        self._plan_material_snapshots[plan.plan_id] = material_snapshot
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
                MaterialExecutionEnvelope.from_dict(raw_material).restore()
                if isinstance(raw_material, Mapping)
                else None
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
