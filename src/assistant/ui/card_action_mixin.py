"""Card-action dispatch for the AI assistant panel."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from src.assistant.application.active_document_continuation import (
    ACTION_APPROVE_EXECUTE,
    ACTION_CONFIRM_OUTLINE_AND_GENERATE,
    ACTION_GENERATE_CONTENT_DRAFT,
    ACTION_OPEN_ARTIFACT,
    ACTION_OPEN_CONTENT_DRAFT,
    ACTION_OPEN_OUTPUT_FOLDER,
    ACTION_PREFLIGHT,
    ACTION_RESTORE_PREVIOUS_DRAFT,
    ACTION_RETRY_PREFLIGHT,
    ACTION_REVISE_CONTENT_DRAFT,
    DOCUMENT_ACTION_IDS,
    validate_active_document_action,
)
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.messages import (
    ROLE_ASSISTANT,
    ROLE_USER,
    AssistantMessage,
)
from src.assistant.contracts.runtime import TURN_COMPLETED
from src.assistant.ui.conversation_presentation import (
    interaction_action_scope_is_current,
    interaction_matches_pending_continuation,
)
from src.config.library import is_template_user_library_path
from src.qt_api import QDesktopServices, QUrl
from src.shared.ui.dialogs import info as show_info


class AssistantCardActionMixin:
    def _handle_card_action(self, action_id: str, payload: object) -> None:
        if action_id in {
            "approve_provider_disclosure",
            "deny_provider_disclosure",
        }:
            if isinstance(payload, Mapping):
                self._resolve_provider_disclosure(
                    payload,
                    approved=action_id == "approve_provider_disclosure",
                )
            return
        if action_id in {
            "approve_content_disclosure",
            "deny_content_disclosure",
        }:
            if isinstance(payload, Mapping):
                self._resolve_content_disclosure(
                    payload,
                    approved=action_id == "approve_content_disclosure",
                )
            return
        if action_id == "submit_question_answer":
            if (
                isinstance(payload, Mapping)
                and self._active_session is not None
                and self._active_session.pending_continuation.get("kind")
                == "local_official_clarification"
            ):
                self._resolve_local_official_clarification(payload)
                return
            if (
                isinstance(payload, Mapping)
                and self._active_session is not None
                and self._active_session.pending_continuation.get("kind")
                == "official_field_completion"
            ):
                self._resolve_official_field_completion(payload)
                return
            if (
                isinstance(payload, Mapping)
                and self._active_session is not None
                and self._active_session.pending_continuation.get("kind")
                == "local_exam_clarification"
            ):
                self._resolve_local_exam_clarification(payload)
                return
            if (
                isinstance(payload, Mapping)
                and self._active_session is not None
                and self._active_session.pending_continuation.get("kind")
                == "local_route_clarification"
            ):
                self._resolve_local_route_clarification(payload)
                return
            response = (
                str(payload.get("response") or "").strip()
                if isinstance(payload, Mapping)
                else ""
            )
            if (
                response
                and isinstance(payload, Mapping)
                and self._card_action_scope_is_current(payload)
                and self._active_session is not None
                and interaction_matches_pending_continuation(
                    payload,
                    self._active_session.pending_continuation,
                )
            ):
                self._send_message(response)
            return
        if action_id == "runtime_open_reference":
            reference = (
                payload.get("reference") if isinstance(payload, Mapping) else None
            )
            self._open_runtime_reference(reference)
            return
        if action_id == "open_template_artifact":
            reference = (
                payload.get("reference") if isinstance(payload, Mapping) else None
            )
            if isinstance(reference, Mapping):
                path = Path(str(reference.get("path") or "")).expanduser()
                if (
                    str(reference.get("owner") or "") == "form"
                    and str(reference.get("kind") or "") == "template_config"
                    and path.is_file()
                    and is_template_user_library_path(path)
                ):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
                    return
            show_info(
                "模板不可用",
                "找不到由应用写入的用户模板文件。",
                parent=self,
            )
            return
        if action_id == "revalidate_template_authoring_failure":
            if not isinstance(payload, Mapping) or self._active_session is None:
                return
            from src.assistant.application.template_authoring import (
                AssistantTemplateAuthoringCompletion,
            )
            from src.config.template_authoring_workspace import (
                revalidate_template_authoring_failure,
            )

            mode_id = str(payload.get("template_authoring_mode_id") or "").strip()
            failed_path = str(payload.get("failed_result_path") or "").strip()
            if not mode_id or not failed_path:
                return
            batch = revalidate_template_authoring_failure(mode_id, failed_path)
            completion = AssistantTemplateAuthoringCompletion(
                mode_id=mode_id,
                result_text="",
                batch=batch,
            )
            for message in self._template_authoring_messages(completion):
                self._active_session.messages.append(message)
            self._render_active_session()
            self._refresh_session_list()
            return
        if action_id == "focus_continuation_response":
            composer = (
                self._composer
                if self._conversation_stack.currentWidget() is self._active_page
                else self._empty_input
            )
            composer.focus_input()
            return
        if action_id in {"resume_runtime_allow", "resume_runtime_deny"}:
            show_info(
                "未执行权限操作",
                "这张旧卡片没有可验证的 Tool Call 恢复通道，应用未执行任何操作。"
                "请重新描述一个不需要该权限的方案。",
                parent=self,
            )
            return
        if action_id == "open_ai_settings":
            self._open_provider_settings()
            return
        if action_id == "retry_provider_request":
            if not isinstance(
                payload, Mapping
            ) or not self._card_action_scope_is_current(payload):
                return
            retry_text = (
                str(payload.get("retry_text") or "").strip()
                if isinstance(payload, Mapping)
                else ""
            )
            if retry_text:
                self._send_message(
                    retry_text,
                    context_refs_override=self._source_refs_for_retry(
                        retry_text
                    ),
                )
            return
        if action_id == "open_workbench":
            from src.ui.panel_specs import panel_index

            self.bridge.navigate_to_panel.emit(panel_index("workbench"))
            return
        if action_id == "edit_exam_plan_requirements":
            if isinstance(payload, Mapping) and self._card_action_scope_is_current(
                payload
            ):
                self._open_exam_plan_editor(payload)
            return
        if action_id == "edit_official_plan_requirements":
            if isinstance(payload, Mapping) and self._card_action_scope_is_current(
                payload
            ):
                self._open_official_plan_editor(payload)
            return
        if action_id in DOCUMENT_ACTION_IDS:
            if isinstance(payload, Mapping) and self._card_action_scope_is_current(
                payload
            ):
                self._dispatch_document_action(action_id, payload=payload)
            return

    def _source_refs_for_retry(
        self,
        retry_text: str,
    ) -> tuple[dict[str, object], ...]:
        """Recover the exact attachments owned by the failed user turn."""

        session = self._active_session
        target = str(retry_text or "").strip()
        if session is None or not target:
            return ()
        for message in reversed(session.messages):
            if (
                message.role == ROLE_USER
                and message.visible_text().strip() == target
            ):
                return tuple(dict(item) for item in message.source_refs)
        return ()

    def _card_action_scope_is_current(
        self,
        payload: Mapping[str, object],
    ) -> bool:
        session = self._active_session
        if session is None:
            return False
        scope = payload.get("action_scope")
        return interaction_action_scope_is_current(
            scope if isinstance(scope, Mapping) else None,
            pending_continuation=session.pending_continuation,
            active_plan=session.active_plan,
            document_job=session.document_job,
            turn_status=session.turn_status,
        )

    def _dispatch_document_action(
        self,
        action_id: str,
        *,
        user_text: str = "",
        source_refs: tuple[dict[str, object], ...] = (),
        payload: Mapping[str, object] | None = None,
    ) -> bool:
        """Run a bounded host action from either a card or typed follow-up."""

        session = self._active_session
        if session is None or not session.active_plan:
            return False
        local_operation_running = bool(
            (self._turn_worker is not None and self._turn_worker.is_running)
            or (self._content_worker is not None and self._content_worker.is_running)
            or (
                self._preflight_worker is not None and self._preflight_worker.is_running
            )
            or (
                self._execution_worker is not None and self._execution_worker.is_running
            )
        )
        if local_operation_running and action_id in {
            ACTION_CONFIRM_OUTLINE_AND_GENERATE,
            ACTION_GENERATE_CONTENT_DRAFT,
            ACTION_REVISE_CONTENT_DRAFT,
            ACTION_PREFLIGHT,
            ACTION_RETRY_PREFLIGHT,
            ACTION_APPROVE_EXECUTE,
        }:
            return False

        normalized_user_text = str(user_text or "").strip()
        if normalized_user_text:
            session = self._coordinator.append_message(
                session,
                AssistantMessage.text(
                    role=ROLE_USER,
                    text=normalized_user_text,
                    source_refs=source_refs,
                ),
                turn_status=TURN_COMPLETED,
                consume_draft=True,
            )
            self._active_session = session
            # Typed document actions append a user message too; always land
            # at the newest turn rather than preserving an older scroll offset.
            self._force_follow_latest = True
            self._render_active_session()
            self._refresh_session_list(select_session_id=session.session_id)

        try:
            plan = DocumentPlan.from_dict(session.active_plan)
        except (ValueError, TypeError):
            self._append_document_action_rejection(
                session,
                "assistant_document_action_plan_invalid",
            )
            return True
        rejection = validate_active_document_action(
            action_id,
            job=session.document_job,
            plan=plan,
        )
        if rejection:
            self._append_document_action_rejection(session, rejection)
            return True

        if action_id == ACTION_PREFLIGHT:
            self._run_preflight(session, plan)
        elif action_id == ACTION_GENERATE_CONTENT_DRAFT:
            self._start_content_generation(session, plan)
        elif action_id == ACTION_CONFIRM_OUTLINE_AND_GENERATE:
            # 章节目录确认卡上内嵌的编辑结果（改标题/增删章/排序）优先于
            # AI 初次生成的目录：确认时把编辑后的标题写进任务状态，
            # 后续逐章写作严格按这份目录执行。
            if payload is not None:
                edited_titles = tuple(
                    str(item).strip()
                    for item in (payload.get("editable_outline") or ())
                    if str(item).strip()
                )
                if edited_titles:
                    session = self._coordinator.update_state(
                        session,
                        document_job={
                            **dict(session.document_job),
                            "outline_edited_titles": list(edited_titles),
                        },
                    )
                    self._active_session = session
            self._start_content_generation(
                session,
                plan,
                outline_confirmed=True,
            )
        elif action_id == ACTION_REVISE_CONTENT_DRAFT:
            self._revise_content_draft(
                session,
                plan,
                normalized_user_text,
            )
        elif action_id == ACTION_RESTORE_PREVIOUS_DRAFT:
            self._restore_previous_content_draft(session, plan)
        elif action_id == ACTION_APPROVE_EXECUTE:
            self._start_execution(session, plan)
        elif action_id == ACTION_RETRY_PREFLIGHT:
            self._run_preflight(session, plan)
        elif action_id == ACTION_OPEN_CONTENT_DRAFT:
            path = str(
                session.document_job.get("generated_content_preview_path")
                or session.document_job.get("generated_content_document_path")
                or ""
            )
            if not path or not Path(path).expanduser().is_file():
                self._append_document_action_rejection(
                    session,
                    "assistant_content_draft_missing",
                )
                return True
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        elif action_id == ACTION_OPEN_ARTIFACT:
            path = str(session.document_job.get("primary_output_path") or "")
            if not path or not Path(path).expanduser().is_file():
                self._append_document_action_rejection(
                    session,
                    "assistant_output_artifact_missing",
                )
                return True
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        elif action_id == ACTION_OPEN_OUTPUT_FOLDER:
            path = str(session.document_job.get("primary_output_path") or "")
            target = Path(path).expanduser().parent if path else None
            if target is None or not target.is_dir():
                self._append_document_action_rejection(
                    session,
                    "assistant_output_folder_missing",
                )
                return True
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        return True

    def _append_document_action_rejection(
        self,
        session,
        reason: str,
    ) -> None:
        descriptions = {
            "assistant_document_action_state_changed": (
                "当前任务状态已经变化，没有执行旧卡片或旧指令中的操作。"
            ),
            "assistant_document_action_plan_stale": (
                "当前草稿与任务方案的版本不一致，为避免误用旧草稿，没有继续生产。"
            ),
            "assistant_preflight_missing": "当前没有可确认的执行前检查结果。",
            "assistant_preflight_invalid": "执行前检查记录不可验证，必须重新检查。",
            "assistant_preflight_stale": (
                "草稿或方案在检查后发生了变化，旧确认已失效，必须重新检查。"
            ),
            "assistant_content_generation_not_available": (
                "当前方案不允许重新生成内容，请先处理方案中的待补充项。"
            ),
            "assistant_content_draft_missing": (
                "当前内容草稿文件已不可用，没有继续执行。"
            ),
            "assistant_output_artifact_missing": "当前交付文件已不可用。",
            "assistant_document_action_plan_invalid": (
                "当前任务方案无法验证，没有执行任何文档操作。"
            ),
            "assistant_exam_plan_edit_invalid": (
                "修改后的试卷要求不完整，未替换当前计划。请检查年级、学科、题量和交付内容。"
            ),
            "assistant_exam_plan_revision_failed": (
                "未能创建新的试卷计划版本，当前计划和已有文件均未改变。"
            ),
            "assistant_exam_master_unavailable": (
                "所选卷面模板已不存在或文件不可用，未替换当前计划。请重新选择卷面模板。"
            ),
            "assistant_exam_master_template_incompatible": (
                "所选卷面模板与当前试卷方案不兼容，未替换当前计划。请改选可用卷面模板。"
            ),
            "assistant_material_snapshot_unavailable": (
                "当前任务绑定的资料快照不可验证，未替换计划或继续生成。"
            ),
        }
        retryable = reason in {
            "assistant_preflight_missing",
            "assistant_preflight_invalid",
            "assistant_preflight_stale",
        }
        updated = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="recovery",
                title="当前操作未执行",
                body=descriptions.get(
                    reason,
                    "当前文档任务无法安全继续，没有创建或覆盖任何文件。",
                ),
                payload={
                    "reason": reason,
                    "actions": (
                        [
                            {
                                "id": ACTION_RETRY_PREFLIGHT,
                                "label": "重新检查",
                            }
                        ]
                        if retryable
                        else []
                    ),
                },
            ),
            turn_status=TURN_COMPLETED,
        )
        self._active_session = updated
        self._render_active_session()
        self._refresh_session_list(select_session_id=updated.session_id)
