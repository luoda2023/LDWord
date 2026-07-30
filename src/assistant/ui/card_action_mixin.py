"""Card-action dispatch for the AI assistant panel."""

from __future__ import annotations

from collections.abc import Mapping

from src.assistant.contracts.document_plan import DocumentPlan
from src.qt_api import QDesktopServices, QMessageBox, QUrl


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
                == "local_route_clarification"
            ):
                self._resolve_local_route_clarification(payload)
                return
            response = (
                str(payload.get("response") or "").strip()
                if isinstance(payload, Mapping)
                else ""
            )
            if response:
                self._send_message(response)
            return
        if action_id == "runtime_open_reference":
            reference = payload.get("reference") if isinstance(payload, Mapping) else None
            self._open_message_reference(reference)
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
            QMessageBox.information(
                self,
                "未执行权限操作",
                "这张旧卡片没有可验证的 Tool Call 恢复通道，应用未执行任何操作。"
                "请重新描述一个不需要该权限的方案。",
            )
            return
        if action_id == "open_ai_settings":
            self._open_provider_settings()
            return
        if action_id == "retry_provider_request":
            retry_text = (
                str(payload.get("retry_text") or "").strip()
                if isinstance(payload, Mapping)
                else ""
            )
            if retry_text:
                self._send_message(retry_text)
            return
        if action_id == "open_workbench":
            from src.ui.panel_specs import panel_index

            self.bridge.navigate_to_panel.emit(panel_index("workbench"))
            return
        session = self._active_session
        if session is None or not session.active_plan:
            return
        try:
            plan = DocumentPlan.from_dict(session.active_plan)
        except (ValueError, TypeError):
            return
        local_operation_running = bool(
            (self._turn_worker is not None and self._turn_worker.is_running)
            or
            (self._content_worker is not None and self._content_worker.is_running)
            or (self._preflight_worker is not None and self._preflight_worker.is_running)
            or (self._execution_worker is not None and self._execution_worker.is_running)
        )
        if local_operation_running and action_id in {
            "generate_content_draft",
            "preflight",
            "retry_preflight",
            "approve_execute",
        }:
            return
        if action_id == "preflight":
            self._run_preflight(session, plan)
        elif action_id == "generate_content_draft":
            self._start_content_generation(session, plan)
        elif action_id == "approve_execute":
            self._start_execution(session, plan)
        elif action_id == "retry_preflight":
            self._run_preflight(session, plan)
        elif action_id == "open_content_draft":
            path = str(
                session.document_job.get("generated_content_preview_path")
                or session.document_job.get("generated_content_document_path")
                or ""
            )
            if path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        elif action_id == "open_artifact":
            path = str(session.document_job.get("primary_output_path") or "")
            if path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
