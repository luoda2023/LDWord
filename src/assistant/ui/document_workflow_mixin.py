"""AI document-generation, preflight, execution, and provider workflow mixin."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from src.assistant.adapters.content_generation_adapter import (
    AssistantContentGenerationAdapter,
    GeneratedOfficialDraft,
    complete_generated_official_draft_field,
    generated_draft_source_ref,
    is_generated_draft,
)
from src.assistant.application.content_generation_service import (
    AssistantContentGenerationService,
    ContentGenerationRequest,
)
from src.assistant.application.document_job_controller import DocumentJobController
from src.assistant.application.exam_plan_editing import (
    ExamPlanEditValues,
    compose_exam_plan_intent,
    normalized_output_root,
    resolve_exam_master_binding,
)
from src.assistant.application.generated_draft_binding import bind_generated_draft
from src.assistant.application.official_plan_editing import (
    OfficialPlanEditValues,
    compose_official_plan_intent,
    official_plan_field_values,
    official_plan_missing_user_fields,
    resolve_official_format_binding,
)
from src.assistant.application.plan_presentation import (
    generated_draft_display_name,
    present_document_plan,
)
from src.assistant.application.preflight_presentation import present_preflight_card
from src.assistant.application.output_location import remember_output_root
from src.assistant.application.official_plan_binding import (
    OFFICIAL_DELIVERY_PROFILE_KEY,
    bind_official_plan,
)
from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.application.session_recovery import AssistantSessionRecovery
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.execution import PreflightReceipt
from src.assistant.contracts.material_snapshot import MaterialExecutionEnvelope
from src.assistant.contracts.messages import (
    BLOCK_ARTIFACT,
    BLOCK_INTERACTION,
    BLOCK_TEXT,
    ROLE_ASSISTANT,
    ROLE_USER,
    AssistantMessage,
)
from src.assistant.contracts.permissions import DisclosureGrant
from src.assistant.contracts.runtime import (
    TURN_COMPLETED,
    TURN_WAITING_DATA_PERMISSION,
    TURN_WAITING_USER_QUESTION,
)
from src.services.official_draft_source import official_field_label
from src.assistant.runtime.cancellation import AssistantCancellationToken
from src.assistant.runtime.providers.profiles import default_mock_profile
from src.assistant.runtime.providers.router import (
    ProviderResolutionError,
    ProviderRouter,
)
from src.assistant.runtime.turn_runner import (
    AssistantTurnRunner,
    attachment_fingerprints,
    history_fingerprint,
)
from src.assistant.storage.execution_journal import ExecutionJournalStore
from src.assistant.storage.models import AssistantSession
from src.assistant.ui.card_action_mixin import AssistantCardActionMixin
from src.assistant.ui.conversation_presentation import (
    interaction_is_active,
    project_output_references,
)
from src.assistant.ui.conversation_view import (
    AssistantConversationMessage,
    AssistantConversationSurface,
)
from src.assistant.ui.creative_home import AssistantCreativeHome, AssistantHeroComposer
from src.assistant.ui.design_tokens import TOKENS
from src.assistant.ui.exam_plan_editor import ExamPlanEditor
from src.assistant.ui.official_plan_editor import OfficialPlanEditor
from src.assistant.ui.interaction_card import AssistantInteractionCard
from src.assistant.ui.panel_theme_mixin import AssistantPanelThemeMixin
from src.assistant.ui.provider_presentation import (
    provider_connection_badge,
)
from src.assistant.ui.provider_selection import ProviderSelectionCoordinator
from src.assistant.ui.session_sidebar import (
    SESSION_ICON_OPTIONS,
    AssistantSessionSidebar,
    session_row_presentation,
)
from src.assistant.ui.turn_flow_mixin import AssistantTurnFlowMixin
from src.assistant.ui.workers import (
    AssistantTurnWorker,
    ContentGenerationWorker,
    DocumentExecutionWorker,
    PreflightWorker,
)
from src.application.materials import ExecutionMaterialSnapshot
from src.config.library import load_scene_from_library
from src.qt_api import (
    QComboBox,
    QDesktopServices,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSize,
    QSizePolicy,
    QStackedWidget,
    Qt,
    QTimer,
    QToolButton,
    QUrl,
    QVBoxLayout,
    QWidget,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.context_menu import ContextMenu
from src.shared.ui.drawer import Drawer
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.theme import bind_theme
from src.ui.adapters.config_selector_models import (
    master_selector_options,
    template_selector_options,
)
from src.ui.base_panel import BasePanel


_CONTENT_VALIDATION_ERROR_LABELS = {
    "duplicate_answer_number": "答案编号重复",
    "duplicate_question_stem": "存在内容完全相同的重复题目",
    "requested_grade_mismatch": "年级与需求不一致",
    "requested_subject_mismatch": "学科与需求不一致",
    "requested_exam_period_mismatch": "考试类型与需求不一致",
    "answer_coverage_incomplete": "答案未覆盖全部题目",
    "blueprint_question_count_mismatch": "题量与试卷规格不一致",
    "requested_question_count_mismatch": "题量与用户要求不一致",
    "question_number_sequence_invalid": "题号不连续",
    "choice_options_incomplete": "选择题选项不完整",
}

def _content_generation_failure_presentation(error: str) -> tuple[str, str]:
    raw = str(error or "content_generation_failed")
    reason, separator, diagnostic_path = raw.partition("|diagnostic=")
    validation_prefixes = (
        "exam_content_compile_blocked:",
        "exam_question_phase_blocked:",
        "exam_section_phase_blocked:",
        "exam_answer_phase_blocked:",
    )
    if reason.startswith("official_content_fields_missing:"):
        return (
            "公文草稿未通过内容校验",
            (
                "模型返回的公文缺少标题或正文，本次结果没有进入正式生产。"
                "请重新生成；发文机关等用户信息仍保留在当前计划中。"
            ),
        )
    if reason.startswith(validation_prefixes):
        code_text = reason.split(":", 1)[1] if ":" in reason else reason
        codes = [item.strip() for item in code_text.split(",") if item.strip()]
        labels = [_CONTENT_VALIDATION_ERROR_LABELS.get(code, code) for code in codes]
        body = (
            "模型已经返回内容，但题稿没有通过本地校验，因此没有创建或覆盖正式输出文件。"
        )
        if labels:
            body += "\n待修复：" + "；".join(labels)
        if separator and diagnostic_path.strip():
            body += "\n失败原稿已保留：" + diagnostic_path.strip()
        return "题稿未通过校验", body
    if "provider" in reason.casefold() or "model" in reason.casefold():
        return (
            "模型服务未完成内容生成",
            (
                "本次模型调用没有取得可用结果，请检查模型连接后重试。"
                f"\n原因：{reason}"
            ),
        )
    return (
        "内容草稿未生成",
        (
            "没有创建或覆盖正式输出文件。可以重试本次生成。"
            f"\n原因：{reason}"
        ),
    )


class AssistantDocumentWorkflowMixin:
    """Own the assistant document workflow outside the panel shell."""

    def _plan_message(self, plan: DocumentPlan) -> AssistantMessage:
        presentation = present_document_plan(plan)
        return AssistantMessage.interaction(
            role=ROLE_ASSISTANT,
            interaction_type="plan",
            title=presentation.title,
            body=presentation.body,
            payload={
                "plan_id": plan.plan_id,
                "revision": plan.revision,
                "actions": list(presentation.actions),
                "facts": [
                    {"label": label, "value": value}
                    for label, value in presentation.facts
                ],
                "notices": list(presentation.notices),
            },
        )

    def _open_exam_plan_editor(self, payload: Mapping[str, object]) -> None:
        session = self._active_session
        if session is None or not session.active_plan:
            return
        try:
            plan = DocumentPlan.from_dict(session.active_plan)
        except (TypeError, ValueError):
            return
        try:
            payload_revision = int(payload.get("revision") or 0)
        except (TypeError, ValueError):
            payload_revision = -1
        if (
            plan.production_contract.terminal_assembler != "exam"
            or str(payload.get("plan_id") or "") != plan.plan_id
            or payload_revision != plan.revision
        ):
            self._append_document_action_rejection(
                session,
                "assistant_document_action_plan_stale",
            )
            return
        if any(
            worker is not None and worker.is_running
            for worker in (
                self._content_worker,
                self._preflight_worker,
                self._execution_worker,
            )
        ):
            self._append_document_action_rejection(
                session,
                "assistant_document_action_state_changed",
            )
            return
        try:
            values = ExamPlanEditValues.from_plan(plan)
        except (TypeError, ValueError):
            return
        master_options = ()
        try:
            scene = load_scene_from_library(
                str(plan.scene_ref.get("id") or ""),
                mode_id=plan.work_mode_id,
            )
            master_options = master_selector_options(
                "exam",
                exam_config=getattr(scene, "exam_paper", None),
                include_source_prefix=False,
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            pass
        drawer = getattr(self, "_exam_plan_editor_drawer", None)
        if drawer is None:
            drawer = Drawer(
                title="修改试卷要求",
                width=min(480, max(360, self.width() - 64)),
                side="right",
                parent=self,
            )
            self._exam_plan_editor_drawer = drawer
        editor = ExamPlanEditor(values, master_options=master_options)
        editor.cancel_requested.connect(drawer.close)

        def save_revision(
            revised,
            plan_id=plan.plan_id,
            revision=plan.revision,
        ) -> None:
            self._apply_exam_plan_edit(
                revised,
                expected_plan_id=plan_id,
                expected_revision=revision,
            )

        editor.save_requested.connect(save_revision)
        previous_editor = drawer.take_body()
        if previous_editor is not None:
            previous_editor.deleteLater()
        drawer.set_body(editor)
        drawer.set_title("修改试卷要求")
        drawer.open()

    def _apply_exam_plan_edit(
        self,
        values: ExamPlanEditValues,
        *,
        expected_plan_id: str,
        expected_revision: int,
    ) -> None:
        session = self._active_session
        if session is None or not isinstance(values, ExamPlanEditValues):
            return
        try:
            current_plan = DocumentPlan.from_dict(session.active_plan)
        except (TypeError, ValueError):
            return
        if (
            current_plan.plan_id != expected_plan_id
            or current_plan.revision != expected_revision
            or current_plan.production_contract.terminal_assembler != "exam"
        ):
            self._append_document_action_rejection(
                session,
                "assistant_document_action_plan_stale",
            )
            return
        if any(
            worker is not None and worker.is_running
            for worker in (
                self._content_worker,
                self._preflight_worker,
                self._execution_worker,
            )
        ):
            self._append_document_action_rejection(
                session,
                "assistant_document_action_state_changed",
            )
            return
        try:
            self._material_snapshot_for_plan(session, current_plan)
        except (TypeError, ValueError):
            self._append_document_action_rejection(
                session,
                "assistant_material_snapshot_unavailable",
            )
            return
        try:
            revised_intent = compose_exam_plan_intent(values)
            turn_id = uuid4().hex
            workspace = self._workspace_snapshot_for_session(session)
            revised_plan = self._document_jobs.draft_plan(
                query=revised_intent,
                workspace=workspace,
                turn_id=turn_id,
                previous_plan=current_plan,
                route_id_override=current_plan.capability_ref.route_id,
            )
            revised_output_root = normalized_output_root(
                values.output_root,
                current_plan.output_policy.output_root,
            )
        except (TypeError, ValueError):
            self._append_document_action_rejection(
                session,
                "assistant_exam_plan_edit_invalid",
            )
            return
        except (OSError, RuntimeError):
            self._append_document_action_rejection(
                session,
                "assistant_exam_plan_revision_failed",
            )
            return
        try:
            master_binding = resolve_exam_master_binding(
                revised_plan,
                values.master_id,
            )
        except ValueError as exc:
            reason = {
                "exam_master_unavailable": "assistant_exam_master_unavailable",
                "exam_master_template_incompatible": (
                    "assistant_exam_master_template_incompatible"
                ),
            }.get(str(exc), "assistant_exam_plan_revision_failed")
            self._append_document_action_rejection(session, reason)
            return
        retained_sources = tuple(
            source
            for source in current_plan.source_artifacts
            if source.source_kind != "assistant_generated"
        )
        revised_plan = replace(
            revised_plan,
            input_document_ref=dict(current_plan.input_document_ref),
            scene_ref={
                **dict(revised_plan.scene_ref),
                "master_id": master_binding.master.master_id,
                "master_label": str(
                    master_binding.master.label or master_binding.master.master_id
                ),
            },
            template_ref={
                **dict(revised_plan.template_ref),
                "id": master_binding.template_id,
            },
            theme_ref=dict(current_plan.theme_ref),
            material_refs=current_plan.material_refs,
            material_snapshot_ref=dict(current_plan.material_snapshot_ref),
            source_artifacts=retained_sources,
            output_policy=replace(
                revised_plan.output_policy,
                output_root=revised_output_root,
            ),
        )
        try:
            remember_output_root(revised_output_root)
        except (OSError, ValueError):
            # The plan remains valid even if remembering a convenience default
            # fails; execution still uses the explicit path stored in the plan.
            pass
        old_job = dict(session.document_job)
        job = {
            "job_id": uuid4().hex,
            "status": "plan_ready",
            "plan_id": revised_plan.plan_id,
            "plan_revision": revised_plan.revision,
            "plan_source": "user_exam_plan_edit",
            "request_turn_id": turn_id,
            "route_id": revised_plan.capability_ref.route_id,
            "material_snapshot": old_job.get("material_snapshot", {}),
            "invalidated_plan_revision": current_plan.revision,
            "invalidated_reason": "assistant_exam_plan_edited",
        }
        session = self._coordinator.append_message(
            session,
            AssistantMessage.text(
                role=ROLE_USER,
                text="已修改试卷要求：" + revised_intent,
            ),
            turn_status=TURN_COMPLETED,
        )
        session = self._coordinator.update_state(
            session,
            active_plan=revised_plan.to_dict(),
            pending_continuation={},
            document_job=job,
            turn_status=TURN_COMPLETED,
        )
        session = self._coordinator.append_message(
            session,
            self._plan_message(revised_plan),
            turn_status=TURN_COMPLETED,
        )
        self._active_session = session
        drawer = getattr(self, "_exam_plan_editor_drawer", None)
        if drawer is not None:
            drawer.close()
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)

    def _open_official_plan_editor(
        self,
        payload: Mapping[str, object],
    ) -> None:
        session = self._active_session
        if session is None or not session.active_plan:
            return
        try:
            plan = DocumentPlan.from_dict(session.active_plan)
            payload_revision = int(payload.get("revision") or 0)
        except (TypeError, ValueError):
            return
        if (
            plan.production_contract.terminal_assembler != "official"
            or not plan.generation_required
            or str(payload.get("plan_id") or "") != plan.plan_id
            or payload_revision != plan.revision
        ):
            self._append_document_action_rejection(
                session,
                "assistant_document_action_plan_stale",
            )
            return
        if any(
            worker is not None and worker.is_running
            for worker in (
                self._content_worker,
                self._preflight_worker,
                self._execution_worker,
            )
        ):
            self._append_document_action_rejection(
                session,
                "assistant_document_action_state_changed",
            )
            return
        values = OfficialPlanEditValues.from_plan(plan)
        drawer = getattr(self, "_official_plan_editor_drawer", None)
        if drawer is None:
            drawer = Drawer(
                title="填写公文信息",
                width=min(520, max(380, self.width() - 64)),
                side="right",
                parent=self,
            )
            self._official_plan_editor_drawer = drawer
        try:
            masters = master_selector_options("official")
            templates = template_selector_options("official")
        except (OSError, RuntimeError, TypeError, ValueError):
            masters = ()
            templates = ()
        editor = OfficialPlanEditor(
            values,
            master_options=masters,
            template_options=templates,
        )
        editor.cancel_requested.connect(drawer.close)

        def save_revision(
            revised,
            plan_id=plan.plan_id,
            revision=plan.revision,
        ) -> None:
            self._apply_official_plan_edit(
                revised,
                expected_plan_id=plan_id,
                expected_revision=revision,
            )

        editor.save_requested.connect(save_revision)
        previous_editor = drawer.take_body()
        if previous_editor is not None:
            previous_editor.deleteLater()
        drawer.set_body(editor)
        drawer.set_title("填写公文信息")
        drawer.open()

    def _apply_official_plan_edit(
        self,
        values: OfficialPlanEditValues,
        *,
        expected_plan_id: str,
        expected_revision: int,
    ) -> None:
        session = self._active_session
        if session is None or not isinstance(values, OfficialPlanEditValues):
            return
        try:
            current_plan = DocumentPlan.from_dict(session.active_plan)
        except (TypeError, ValueError):
            return
        if (
            current_plan.plan_id != expected_plan_id
            or current_plan.revision != expected_revision
            or current_plan.production_contract.terminal_assembler != "official"
            or not current_plan.generation_required
        ):
            self._append_document_action_rejection(
                session,
                "assistant_document_action_plan_stale",
            )
            return
        if any(
            worker is not None and worker.is_running
            for worker in (
                self._content_worker,
                self._preflight_worker,
                self._execution_worker,
            )
        ):
            self._append_document_action_rejection(
                session,
                "assistant_document_action_state_changed",
            )
            return
        try:
            revised_intent = compose_official_plan_intent(values)
            format_binding = resolve_official_format_binding(values)
            turn_id = uuid4().hex
            revised_plan = self._document_jobs.draft_plan(
                query=revised_intent,
                workspace=self._workspace_snapshot_for_session(session),
                turn_id=turn_id,
                previous_plan=current_plan,
                route_id_override=current_plan.capability_ref.route_id,
            )
            revised_output_root = normalized_output_root(
                values.output_root,
                current_plan.output_policy.output_root,
            )
        except (TypeError, ValueError):
            self._append_document_action_rejection(
                session,
                "assistant_official_plan_edit_invalid",
            )
            return
        except (OSError, RuntimeError):
            self._append_document_action_rejection(
                session,
                "assistant_official_plan_revision_failed",
            )
            return
        retained_sources = tuple(
            source
            for source in current_plan.source_artifacts
            if source.source_kind != "assistant_generated"
        )
        revised_plan = replace(
            revised_plan,
            input_document_ref=dict(current_plan.input_document_ref),
            scene_ref={
                **dict(revised_plan.scene_ref),
                "official_field_values": values.authoritative_fields(),
                "official_content_requirements": (
                    values.content_requirements.strip()
                ),
                OFFICIAL_DELIVERY_PROFILE_KEY: (
                    format_binding.delivery_profile
                ),
            },
            template_ref={
                **dict(revised_plan.template_ref),
                "id": format_binding.template_id,
            },
            theme_ref=dict(current_plan.theme_ref),
            material_refs=current_plan.material_refs,
            material_snapshot_ref=dict(current_plan.material_snapshot_ref),
            source_artifacts=retained_sources,
            production_contract=replace(
                revised_plan.production_contract,
                document_type_id=values.document_type_id,
                master_id=format_binding.master.master_id,
            ),
            output_policy=replace(
                revised_plan.output_policy,
                output_root=revised_output_root,
            ),
        )
        revised_plan = bind_official_plan(revised_plan)
        try:
            remember_output_root(revised_output_root)
        except (OSError, ValueError):
            pass
        old_job = dict(session.document_job)
        job = {
            "job_id": uuid4().hex,
            "status": "plan_ready",
            "plan_id": revised_plan.plan_id,
            "plan_revision": revised_plan.revision,
            "plan_source": "user_official_plan_edit",
            "request_turn_id": turn_id,
            "route_id": revised_plan.capability_ref.route_id,
            "material_snapshot": old_job.get("material_snapshot", {}),
            "invalidated_plan_revision": current_plan.revision,
            "invalidated_reason": "assistant_official_plan_edited",
        }
        session = self._coordinator.append_message(
            session,
            AssistantMessage.text(
                role=ROLE_USER,
                text="已填写公文信息：" + revised_intent,
            ),
            turn_status=TURN_COMPLETED,
        )
        session = self._coordinator.update_state(
            session,
            active_plan=revised_plan.to_dict(),
            pending_continuation={},
            document_job=job,
            turn_status=TURN_COMPLETED,
        )
        session = self._coordinator.append_message(
            session,
            self._plan_message(revised_plan),
            turn_status=TURN_COMPLETED,
        )
        self._active_session = session
        drawer = getattr(self, "_official_plan_editor_drawer", None)
        if drawer is not None:
            drawer.close()
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)

    def _open_provider_settings(self) -> None:
        navigate = getattr(self.bridge, "navigate_to_preferences", None)
        if callable(navigate):
            navigate("ai")

    def _provider_disclosure_facts(
        self,
        session: AssistantSession,
    ) -> list[dict[str, str]]:
        profile_label = session.provider_profile_id or "当前所选服务"
        profile_model_id = ""
        try:
            profile = self._provider_router.profiles.get(
                session.provider_profile_id
            )
        except (KeyError, OSError, TypeError, ValueError):
            pass
        else:
            profile_label = profile.label
            profile_model_id = profile.model_id
        return [
            {"label": "服务", "value": profile_label},
            {
                "label": "模型",
                "value": (
                    session.model_id
                    or profile_model_id
                    or "当前所选模型"
                ),
            },
        ]

    def _queue_content_generation_disclosure(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
        context_documents: tuple[dict[str, object], ...],
    ) -> None:
        disclosure_id = uuid4().hex
        continuation = {
            "kind": "local_content_disclosure",
            "disclosure_id": disclosure_id,
            "plan_id": plan.plan_id,
            "plan_revision": plan.revision,
            "context_refs": [dict(item) for item in context_documents],
        }
        job = {
            **dict(session.document_job),
            "status": "needs_data_disclosure",
            "disclosure_id": disclosure_id,
            "disclosure_purpose": "content_generation",
        }
        session = self._coordinator.update_state(
            session,
            pending_continuation=continuation,
            document_job=job,
            turn_status=TURN_WAITING_DATA_PERMISSION,
        )
        names = "、".join(
            str(item.get("name") or item.get("title") or "DOCX 材料")
            for item in context_documents
        )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="disclosure",
                title="确认用于内容生成的材料",
                body="",
                payload={
                    "disclosure_id": disclosure_id,
                    "facts": [
                        {"label": "材料", "value": names or "DOCX 材料"},
                        {"label": "发送内容", "value": "附件正文"},
                        {"label": "用途", "value": "生成并校验文档内容"},
                        *self._provider_disclosure_facts(session),
                    ],
                    "actions": [
                        {
                            "id": "approve_content_disclosure",
                            "label": "同意并生成",
                            "variant": "primary",
                        },
                        {
                            "id": "deny_content_disclosure",
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

    def _resolve_content_disclosure(
        self,
        payload: Mapping[str, object],
        *,
        approved: bool,
    ) -> None:
        session = self._active_session
        if session is None:
            return
        continuation = dict(session.pending_continuation)
        if continuation.get("kind") != "local_content_disclosure":
            return
        expected_id = str(continuation.get("disclosure_id") or "")
        submitted_id = str(payload.get("disclosure_id") or "")
        if not expected_id or submitted_id != expected_id:
            return
        try:
            plan = DocumentPlan.from_dict(session.active_plan)
        except (TypeError, ValueError):
            return
        if (
            plan.plan_id != str(continuation.get("plan_id") or "")
            or plan.revision != int(continuation.get("plan_revision") or 0)
        ):
            return
        job = {
            **dict(session.document_job),
            "status": "plan_ready" if not approved else "content_generation_ready",
            "disclosure_decision": "approved" if approved else "denied",
        }
        session = self._coordinator.update_state(
            session,
            pending_continuation={},
            document_job=job,
            turn_status=TURN_COMPLETED if not approved else "local_processing",
        )
        self._active_session = session
        if not approved:
            session = self._coordinator.append_message(
                session,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="boundary",
                    title="已取消材料发送",
                    body="",
                    payload={"actions": []},
                ),
                turn_status=TURN_COMPLETED,
            )
            self._active_session = session
            self._render_active_session()
            self._refresh_session_list(select_session_id=session.session_id)
            return
        self._start_content_generation(
            session,
            plan,
            approved_disclosure=True,
        )

    def _start_content_generation(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
        *,
        approved_disclosure: bool = False,
        revision_context_text: str = "",
        revision_context_ref: str = "",
        include_plan_materials: bool = True,
    ) -> None:
        if self._content_worker is not None and self._content_worker.is_running:
            return
        if not plan.generation_required or plan.blocking_issues:
            return
        if official_plan_missing_user_fields(plan):
            self._open_official_plan_editor(
                {"plan_id": plan.plan_id, "revision": plan.revision}
            )
            return
        if (
            not str(revision_context_text or "").strip()
            and str(plan.scene_ref.get("generation_mode") or "")
            == "revision_pending"
        ):
            retry_source = Path(
                str(session.document_job.get("revision_source_path") or "")
            ).expanduser()
            if retry_source.suffix.casefold() not in {".md", ".markdown", ".json"}:
                self._append_content_generation_failure(
                    session.session_id,
                    "assistant_content_revision_source_unavailable",
                )
                return
            try:
                retry_text = retry_source.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                self._append_content_generation_failure(
                    session.session_id,
                    "assistant_content_revision_source_unreadable",
                )
                return
            if not retry_text.strip() or len(retry_text) > 100_000:
                self._append_content_generation_failure(
                    session.session_id,
                    "assistant_content_revision_source_invalid",
                )
                return
            revision_context_text = retry_text
            revision_context_ref = str(retry_source.resolve())
            include_plan_materials = False
        context_documents = (
            tuple(dict(item) for item in plan.material_refs)
            if include_plan_materials
            else ()
        )
        if context_documents and not approved_disclosure:
            self._queue_content_generation_disclosure(
                session,
                plan,
                context_documents,
            )
            return
        try:
            gateway = (
                self._fixed_turn_runner.gateway
                if self._fixed_turn_runner is not None
                else self._provider_router.resolve(session.provider_profile_id)
            )
        except ProviderResolutionError as exc:
            self._append_content_generation_failure(session.session_id, str(exc))
            return
        context_ref_ids = tuple(
            str(item.get("path") or item.get("artifact_id") or item.get("name") or "")
            for item in context_documents
            if str(item.get("path") or item.get("artifact_id") or item.get("name") or "")
        )
        context_fingerprints = attachment_fingerprints(context_documents)
        normalized_revision_ref = str(revision_context_ref or "").strip()
        normalized_revision_text = str(revision_context_text or "").strip()
        if normalized_revision_ref:
            context_ref_ids = (*context_ref_ids, normalized_revision_ref)
            context_fingerprints.update(
                attachment_fingerprints(
                    ({"path": normalized_revision_ref},)
                )
            )
        try:
            generation_material = self._material_snapshot_for_plan(
                session,
                plan,
            )
        except (TypeError, ValueError):
            generation_material = None
        authoritative_fields = {
            **self._material_field_values(generation_material),
            **official_plan_field_values(plan),
        }
        context_fields = (
            *(("document_text",) if context_documents else ()),
            *(("generated_draft_text",) if normalized_revision_text else ()),
        )
        disclosure_grant = (
            DisclosureGrant(
                grant_id=uuid4().hex,
                session_id=session.session_id,
                provider_id=session.provider_profile_id,
                model_id=session.model_id,
                allowed_refs=context_ref_ids,
                allowed_fields=context_fields,
                created_at=datetime.now(timezone.utc).isoformat(),
                expires_at=(
                    datetime.now(timezone.utc) + timedelta(minutes=10)
                ).isoformat(),
                scope="once",
                content_fingerprints=context_fingerprints,
            )
            if context_documents or normalized_revision_text
            else None
        )
        generation_id = uuid4().hex
        request = ContentGenerationRequest(
            session_id=session.session_id,
            turn_id=plan.created_by_turn_id,
            prompt=plan.intent,
            provider_id=session.provider_profile_id,
            model_id=session.model_id,
            generation_id=generation_id,
            plan_id=plan.plan_id,
            plan_revision=plan.revision,
            plan_fingerprint=plan.fingerprint,
            context_text=normalized_revision_text,
            context_documents=context_documents,
            context_refs=context_ref_ids,
            context_fields=context_fields,
            context_fingerprints=tuple(context_fingerprints.items()),
            disclosure_grant=disclosure_grant,
            capability_id=plan.capability_ref.capability_id,
            artifact_kind=plan.generation_contract.artifact_kind,
            prompt_profile_id=plan.generation_contract.prompt_profile_id,
            scene_id=str(plan.scene_ref.get("id") or ""),
            scale_profile_id=str(
                plan.scene_ref.get("scale_profile_id") or ""
            ),
            document_type_id=plan.production_contract.document_type_id,
            authoritative_fields=authoritative_fields,
        )
        adapter = AssistantContentGenerationAdapter(self._coordinator.store.root)
        service = AssistantContentGenerationService(adapter)
        worker = ContentGenerationWorker(service, request, gateway, parent=self)
        self._content_worker = worker
        job = {
            **dict(session.document_job),
            "status": "content_generation_running",
            "content_generation_turn_id": plan.created_by_turn_id,
            "content_generation_id": generation_id,
            "content_generation_purpose": (
                "revision" if normalized_revision_text else "authoring"
            ),
        }
        session = self._coordinator.update_state(session, document_job=job)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="progress",
                title="正在起草文档内容",
                body="",
                payload={
                    "actions": [],
                    "ephemeral": True,
                    "progress_kind": "content_generation",
                    "generation_id": generation_id,
                },
            ),
        )
        if self._active_session is not None and self._active_session.session_id == session.session_id:
            self._active_session = session
            self._render_active_session()
        self._composer.set_busy(True)
        worker.finished.connect(self._on_content_generation_finished)
        worker.failed.connect(
            lambda error, session_id=session.session_id: self._append_content_generation_failure(
                session_id,
                error,
            )
        )
        worker.start()
        self._sync_composer_busy_state()

    def _revise_content_draft(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
        revision_request: str,
    ) -> None:
        request_text = str(revision_request or "").strip()
        if not request_text:
            self._append_document_action_rejection(
                session,
                "assistant_content_revision_request_missing",
            )
            return
        job = dict(session.document_job)
        candidates = (
            str(job.get("generated_content_markdown_path") or "").strip(),
            str(job.get("generated_content_production_input_path") or "").strip(),
            str(plan.production_input_artifact.path)
            if plan.production_input_artifact is not None
            else "",
        )
        source_path = next(
            (
                Path(value).expanduser()
                for value in candidates
                if value and Path(value).expanduser().is_file()
            ),
            None,
        )
        if source_path is None or source_path.suffix.casefold() not in {
            ".md",
            ".markdown",
            ".json",
        }:
            self._append_document_action_rejection(
                session,
                "assistant_content_revision_source_unavailable",
            )
            return
        try:
            current_text = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            self._append_document_action_rejection(
                session,
                "assistant_content_revision_source_unreadable",
            )
            return
        if not current_text.strip() or len(current_text) > 100_000:
            self._append_document_action_rejection(
                session,
                "assistant_content_revision_source_invalid",
            )
            return

        turn_id = uuid4().hex
        retained_sources = tuple(
            source
            for source in plan.source_artifacts
            if source.role != plan.production_contract.input_role
        )
        revised_plan = replace(
            plan,
            revision=plan.revision + 1,
            intent=(
                plan.intent.rstrip()
                + "\n\n基于当前草稿执行以下修订："
                + request_text
            ),
            created_by_turn_id=turn_id,
            scene_ref={
                **dict(plan.scene_ref),
                "generation_mode": "revision_pending",
                "revision_source_draft_id": str(
                    job.get("generated_content_draft_id") or ""
                ),
            },
            input_document_ref={},
            source_artifacts=retained_sources,
            content_fragment_refs=(),
        )
        next_job = dict(job)
        next_job.pop("preflight", None)
        next_job.update(
            {
                "status": "plan_ready",
                "plan_id": revised_plan.plan_id,
                "plan_revision": revised_plan.revision,
                "request_turn_id": turn_id,
                "previous_generated_content_draft_id": str(
                    job.get("generated_content_draft_id") or ""
                ),
                "previous_plan_snapshot": plan.to_dict(),
                "revision_source_path": str(source_path),
                "revision_request": request_text,
                "invalidated_plan_revision": plan.revision,
                "invalidated_reason": "assistant_content_revision_requested",
            }
        )
        session = self._coordinator.update_state(
            session,
            active_plan=revised_plan.to_dict(),
            pending_continuation={},
            document_job=next_job,
            turn_status=TURN_COMPLETED,
        )
        self._active_session = session
        self._start_content_generation(
            session,
            revised_plan,
            approved_disclosure=True,
            revision_context_text=current_text,
            revision_context_ref=str(source_path.resolve()),
            include_plan_materials=False,
        )

    def _restore_previous_content_draft(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
    ) -> None:
        job = dict(session.document_job)
        raw_previous_plan = job.get("previous_plan_snapshot")
        previous_plan: DocumentPlan | None = None
        try:
            previous_plan = DocumentPlan.from_dict(raw_previous_plan)
            previous_source = previous_plan.production_input_artifact
        except (TypeError, ValueError):
            previous_source = None
        if (
            previous_plan is None
            or previous_source is None
            or previous_plan.plan_id != plan.plan_id
            or previous_plan.revision >= plan.revision
            or previous_source.source_kind != "assistant_generated"
            or not Path(previous_source.path).expanduser().is_file()
        ):
            self._append_document_action_rejection(
                session,
                "assistant_previous_draft_invalid",
            )
            return

        restored_plan = replace(
            previous_plan,
            revision=plan.revision + 1,
            created_by_turn_id=uuid4().hex,
            scene_ref={
                **dict(previous_plan.scene_ref),
                "generation_mode": "generated_draft",
                "restored_from_revision": plan.revision,
            },
        )
        restored_job = dict(job)
        for key in (
            "preflight",
            "error_text",
            "revision_request",
            "revision_source_path",
            "previous_plan_snapshot",
            "previous_generated_content_draft_id",
        ):
            restored_job.pop(key, None)
        restored_job.update(
            {
                "status": "content_draft_ready",
                "plan_id": restored_plan.plan_id,
                "plan_revision": restored_plan.revision,
                "generated_content_production_input_path": previous_source.path,
                "restored_plan_revision": previous_plan.revision,
            }
        )
        session = self._coordinator.update_state(
            session,
            active_plan=restored_plan.to_dict(),
            document_job=restored_job,
            pending_continuation={},
            turn_status=TURN_COMPLETED,
        )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="recovery",
                title="已恢复上一版内容草稿",
                body="",
                payload={
                    "actions": [
                        {"id": "open_content_draft", "label": "打开草稿"},
                        {"id": "preflight", "label": "检查并准备生成 Word"},
                    ]
                },
            ),
            turn_status=TURN_COMPLETED,
        )
        session = self._project_completion_read_state(session)
        if (
            self._active_session is not None
            and self._active_session.session_id == session.session_id
        ):
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)

    def _on_content_generation_finished(self, draft: object) -> None:
        worker = self._content_worker
        if worker is None or not is_generated_draft(draft):
            return
        origin_session_id = worker.request.session_id
        try:
            session = self._coordinator.load_session(origin_session_id)
            plan = DocumentPlan.from_dict(session.active_plan)
        except (OSError, ValueError, TypeError):
            self._finish_content_generation_ui()
            return
        request = worker.request
        if (
            (request.plan_id and request.plan_id != plan.plan_id)
            or (
                request.plan_revision
                and request.plan_revision != plan.revision
            )
            or (
                request.plan_fingerprint
                and request.plan_fingerprint != plan.fingerprint
            )
        ):
            self._discard_stale_content_generation(session, request)
            return
        if (
            isinstance(draft, GeneratedOfficialDraft)
            and draft.missing_user_fields
        ):
            missing_model_fields = tuple(
                field
                for field in draft.missing_user_fields
                if field in {"title", "body"}
            )
            if missing_model_fields:
                self._append_content_generation_failure(
                    session.session_id,
                    "official_content_fields_missing:"
                    + ",".join(missing_model_fields),
                )
                return
            self._queue_official_field_completion(session, plan, draft)
            return
        self._publish_generated_draft(session, plan, draft)

    def _discard_stale_content_generation(
        self,
        session: AssistantSession,
        request: ContentGenerationRequest,
    ) -> None:
        job = dict(session.document_job)
        try:
            job_revision = int(job.get("plan_revision") or 0)
        except (TypeError, ValueError):
            job_revision = 0
        if (
            str(job.get("plan_id") or "") == request.plan_id
            and job_revision == request.plan_revision
            and str(job.get("status") or "") == "content_generation_running"
        ):
            job.update(
                {
                    "status": "failed",
                    "error_text": "assistant_content_generation_plan_stale",
                }
            )
            session = self._coordinator.update_state(
                session,
                document_job=job,
                turn_status=TURN_COMPLETED,
            )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="recovery",
                title="已丢弃过期内容草稿",
                body=(
                    "内容生成期间任务方案已经变化；为避免把旧草稿绑定到新计划，"
                    "本次结果没有进入预检或正式生产。"
                ),
                payload={"actions": []},
            ),
            turn_status=TURN_COMPLETED,
        )
        if (
            self._active_session is not None
            and self._active_session.session_id == session.session_id
        ):
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list()
        self._finish_content_generation_ui()

    def _publish_generated_draft(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
        draft: object,
    ) -> None:
        if not is_generated_draft(draft):
            self._finish_content_generation_ui()
            return
        try:
            updated_plan = bind_generated_draft(plan, draft)
        except ValueError as exc:
            self._append_content_generation_failure(
                session.session_id,
                str(exc),
            )
            return
        source_ref = generated_draft_source_ref(draft)
        preview_path = str(draft.preview_path)
        production_input_path = str(draft.production_input_path)
        draft_display_name = generated_draft_display_name(
            updated_plan,
            preview_path,
        )
        job = {
            **dict(session.document_job),
            "status": "content_draft_ready",
            "plan_id": updated_plan.plan_id,
            "plan_revision": updated_plan.revision,
            "generated_content_draft_id": draft.draft_id,
            "generated_content_markdown_path": str(
                getattr(draft, "markdown_path", "")
            ),
            "generated_content_document_path": preview_path,
            "generated_content_preview_path": preview_path,
            "generated_content_production_input_path": production_input_path,
            "generated_content_artifact_kind": draft.artifact_kind,
            "generated_content_schema_id": source_ref.schema_id,
        }
        session = self._coordinator.update_state(
            session,
            active_plan=updated_plan.to_dict(),
            document_job=job,
            turn_status=TURN_COMPLETED,
        )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="artifact",
                title="内容草稿已生成",
                body=(
                    "\n".join(f"• {warning}" for warning in draft.warnings)
                    if isinstance(draft, GeneratedOfficialDraft)
                    and draft.warnings
                    else ""
                ),
                payload={
                    "draft_id": draft.draft_id,
                    "artifact_kind": draft.artifact_kind,
                    "schema_id": source_ref.schema_id,
                    "reference": {
                        "type": "file",
                        "title": draft_display_name,
                        "path": preview_path,
                    },
                    "actions": [
                        {
                            "id": "open_content_draft",
                            "label": "打开草稿",
                            "variant": "secondary",
                            "alignment": "left",
                        },
                        {
                            "id": "generate_content_draft",
                            "label": "重新生成",
                            "variant": "secondary",
                            "alignment": "left",
                        },
                        {
                            "id": "preflight",
                            "label": "生成 Word",
                            "variant": "primary",
                            "alignment": "right",
                        },
                    ],
                },
            ),
        )
        session = self._project_completion_read_state(session)
        if (
            self._active_session is not None
            and self._active_session.session_id == session.session_id
        ):
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list()
        self._finish_content_generation_ui()

    def _queue_official_field_completion(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
        draft: GeneratedOfficialDraft,
    ) -> None:
        field_keys = tuple(draft.missing_user_fields)
        completion_id = uuid4().hex
        suggestions = {
            field_key: self._official_field_suggestion(field_key, draft)
            for field_key in field_keys
        }
        continuation = {
            "kind": "official_field_completion",
            "completion_id": completion_id,
            "plan_id": plan.plan_id,
            "plan_revision": plan.revision,
            "draft_source_path": draft.source_path,
            "field_keys": list(field_keys),
            "auto_suggestions": suggestions,
        }
        job = {
            **dict(session.document_job),
            "status": "needs_official_field_completion",
            "generated_content_draft_id": draft.draft_id,
            "generated_content_document_path": draft.preview_path,
            "generated_content_preview_path": draft.preview_path,
            "generated_content_production_input_path": draft.production_input_path,
            "generated_content_artifact_kind": draft.artifact_kind,
            "generated_content_schema_id": draft.schema_id,
            "official_missing_fields": list(draft.missing_user_fields),
        }
        session = self._coordinator.update_state(
            session,
            pending_continuation=continuation,
            document_job=job,
            turn_status=TURN_WAITING_USER_QUESTION,
        )
        session = self._coordinator.append_message(
            session,
            self._official_field_question_message(
                draft,
                completion_id=completion_id,
                suggestions=suggestions,
            ),
            turn_status=TURN_WAITING_USER_QUESTION,
        )
        if (
            self._active_session is not None
            and self._active_session.session_id == session.session_id
        ):
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list()
        self._finish_content_generation_ui()

    @staticmethod
    def _official_field_suggestion(
        field_key: str,
        draft: GeneratedOfficialDraft,
    ) -> str:
        if field_key == "organization":
            return "本单位（待确认）"
        if field_key == "title":
            return "关于有关事项的通知"
        if field_key == "body":
            return "根据工作安排，现将有关事项通知如下。"
        return ""

    @staticmethod
    def _official_field_question_message(
        draft: GeneratedOfficialDraft,
        *,
        completion_id: str,
        suggestions: Mapping[str, str],
    ) -> AssistantMessage:
        field_keys = tuple(draft.missing_user_fields)
        inputs = [
            {
                "id": field_key,
                "label": official_field_label(field_key),
                "placeholder": "请填写准确内容",
                "value": str(suggestions.get(field_key) or ""),
                "required": True,
                "column_span": (
                    2 if field_key == "body" else 1
                ),
            }
            for field_key in field_keys
        ]
        return AssistantMessage.interaction(
            role=ROLE_ASSISTANT,
            interaction_type="question",
            title="请补充公文必填信息",
            body="",
            payload={
                "completion_id": completion_id,
                "field_keys": list(field_keys),
                "reference": {
                    "type": "file",
                    "title": Path(draft.preview_path).name,
                    "path": draft.preview_path,
                },
                "confirmation_request": {
                    "kind": "official_field_completion",
                    "input_columns": 2,
                    "inputs_label": "填写缺失信息",
                    "submit_label": "保存并继续",
                    "compact_heading": True,
                    "inputs": inputs,
                    "allow_skip": False,
                },
            },
        )

    def _resolve_official_field_completion(
        self,
        payload: Mapping[str, object],
    ) -> None:
        session = self._active_session
        if session is None:
            return
        continuation = dict(session.pending_continuation)
        if continuation.get("kind") != "official_field_completion":
            return
        if (
            str(payload.get("completion_id") or "")
            != str(continuation.get("completion_id") or "")
        ):
            return
        field_keys = tuple(
            str(item or "").strip()
            for item in continuation.get("field_keys", ())
            if str(item or "").strip()
        )
        if not field_keys:
            legacy_key = str(continuation.get("field_key") or "").strip()
            field_keys = (legacy_key,) if legacy_key else ()
        raw_values = payload.get("field_values")
        field_values = (
            {
                str(key or "").strip(): str(value or "").strip()
                for key, value in raw_values.items()
            }
            if isinstance(raw_values, Mapping)
            else {}
        )
        if len(field_keys) == 1 and field_keys[0] not in field_values:
            legacy_value = str(payload.get("other_text") or "").strip()
            selected_ids = {
                str(item or "").strip()
                for item in payload.get("selected_choice_ids", ())
                if str(item or "").strip()
            }
            if not legacy_value and "auto_suggestion" in selected_ids:
                legacy_value = str(
                    continuation.get("auto_suggestion") or ""
                ).strip()
            if legacy_value:
                field_values[field_keys[0]] = legacy_value
        if not field_keys or any(not field_values.get(key) for key in field_keys):
            return
        try:
            plan = DocumentPlan.from_dict(session.active_plan)
            if plan.plan_id != str(continuation.get("plan_id") or ""):
                return
            for field_key in field_keys:
                draft = complete_generated_official_draft_field(
                    str(continuation.get("draft_source_path") or ""),
                    field_key=field_key,
                    value=field_values[field_key],
                )
        except (OSError, TypeError, ValueError) as exc:
            self._append_content_generation_failure(
                session.session_id,
                str(exc),
            )
            return
        if draft.missing_user_fields:
            session = self._coordinator.update_state(
                session,
                pending_continuation={},
                turn_status=TURN_COMPLETED,
            )
            self._queue_official_field_completion(session, plan, draft)
            return
        session = self._coordinator.update_state(
            session,
            pending_continuation={},
            turn_status=TURN_COMPLETED,
        )
        self._publish_generated_draft(session, plan, draft)

    def _append_content_generation_failure(self, session_id: str, error: str) -> None:
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            self._finish_content_generation_ui()
            return
        cancelled = "cancel" in str(error or "").casefold()
        failure_title, failure_body = _content_generation_failure_presentation(error)
        job = {
            **dict(session.document_job),
            "status": "cancelled" if cancelled else "failed",
            "error_text": str(error or "content_generation_failed"),
        }
        session = self._coordinator.update_state(session, document_job=job)
        failure_actions = [
            {
                "id": "generate_content_draft",
                "label": "重新生成并自动修复",
            }
        ]
        if isinstance(job.get("previous_plan_snapshot"), Mapping):
            failure_actions.append(
                {
                    "id": "restore_previous_draft",
                    "label": "恢复上一版草稿",
                }
            )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="recovery",
                title="内容起草已取消" if cancelled else failure_title,
                body=(
                    ""
                    if cancelled
                    else failure_body
                ),
                payload={
                    "actions": failure_actions,
                },
            ),
        )
        session = self._project_completion_read_state(session)
        if self._active_session is not None and self._active_session.session_id == session_id:
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list()
        self._finish_content_generation_ui()

    def _finish_content_generation_ui(self) -> None:
        worker = self._content_worker
        if worker is not None:
            worker.deleteLater()
        self._content_worker = None
        self._sync_composer_busy_state()
        if self._execution_worker is None or not self._execution_worker.is_running:
            self._stop_button.setVisible(False)

    @staticmethod
    def _material_snapshot_for_plan(
        session: AssistantSession,
        plan: DocumentPlan,
    ) -> ExecutionMaterialSnapshot | None:
        raw = session.document_job.get("material_snapshot")
        if not isinstance(raw, Mapping):
            raise ValueError("assistant_material_snapshot_missing")
        snapshot = MaterialExecutionEnvelope.from_dict(raw)
        expected = str(plan.material_snapshot_ref.get("digest") or "")
        if not expected or expected != snapshot.digest:
            raise ValueError("assistant_material_snapshot_plan_mismatch")
        return snapshot.restore()

    @staticmethod
    def _material_field_values(
        snapshot: ExecutionMaterialSnapshot | None,
    ) -> dict[str, str]:
        if snapshot is None or len(snapshot.records) != 1:
            return {}
        return dict(snapshot.records[0].field_values)

    def _run_preflight(self, session: AssistantSession, plan: DocumentPlan) -> None:
        if self._preflight_worker is not None and self._preflight_worker.is_running:
            return
        normalized_plan = bind_official_plan(plan, bump_revision=True)
        if normalized_plan is not plan:
            plan = normalized_plan
            normalized_job = {
                **dict(session.document_job),
                "plan_id": plan.plan_id,
                "plan_revision": plan.revision,
                "normalized_from_plan_revision": normalized_plan.revision - 1,
                "normalized_reason": "official_plan_binding_upgraded",
            }
            session = self._coordinator.update_state(
                session,
                active_plan=plan.to_dict(),
                document_job=normalized_job,
            )
            if (
                self._active_session is not None
                and self._active_session.session_id == session.session_id
            ):
                self._active_session = session
        try:
            material_snapshot = self._material_snapshot_for_plan(session, plan)
        except (TypeError, ValueError):
            self._on_preflight_failed(
                session.session_id,
                "assistant_material_snapshot_unavailable",
            )
            return
        preflight_run_id = uuid4().hex
        job = {
            **dict(session.document_job),
            "status": "preflight_running",
            "preflight_run_id": preflight_run_id,
        }
        session = self._coordinator.update_state(session, document_job=job)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="progress",
                title="正在进行本地执行前检查",
                body="",
                payload={
                    "actions": [],
                    "ephemeral": True,
                    "progress_kind": "preflight",
                    "preflight_run_id": preflight_run_id,
                },
            ),
        )
        if self._active_session is not None and self._active_session.session_id == session.session_id:
            self._active_session = session
            self._render_active_session()
        worker = PreflightWorker(
            self._document_jobs,
            session_id=session.session_id,
            plan=plan,
            material_snapshot=material_snapshot,
            parent=self,
        )
        self._preflight_worker = worker
        self._composer.set_busy(True)
        worker.finished.connect(self._on_preflight_finished)
        worker.failed.connect(
            lambda error, session_id=session.session_id: self._on_preflight_failed(
                session_id,
                error,
            )
        )
        worker.start()
        self._sync_composer_busy_state()

    def _on_preflight_finished(self, preflight: object) -> None:
        worker = self._preflight_worker
        if worker is None or not isinstance(preflight, PreflightReceipt):
            return
        try:
            session = self._coordinator.load_session(worker.session_id)
            current_plan = DocumentPlan.from_dict(session.active_plan)
        except (OSError, ValueError, TypeError):
            self._finish_preflight_ui()
            return
        if current_plan.fingerprint != preflight.plan_fingerprint:
            self._on_preflight_failed(worker.session_id, "assistant_preflight_became_stale")
            return
        job = {
            **dict(session.document_job),
            "status": "needs_execution_approval" if preflight.ready else "preflight_failed",
            "preflight": preflight.to_dict(),
        }
        session = self._coordinator.update_state(session, document_job=job)
        presentation = present_preflight_card(current_plan, preflight)
        approval_facts = [
            {"label": label, "value": value}
            for label, value in presentation.facts
        ]
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type=presentation.interaction_type,
                title=presentation.title,
                body=presentation.body,
                payload={
                    "preflight_id": preflight.preflight_id,
                    "facts": approval_facts,
                    "evidence": {
                        "input_hash": preflight.input_hash,
                        "material_snapshot_digest": (
                            preflight.material_snapshot_digest
                        ),
                        "plan_fingerprint": preflight.plan_fingerprint,
                        "resource_fingerprints": dict(
                            preflight.resource_fingerprints
                        ),
                    },
                    "notices": list(presentation.notices),
                    "actions": list(presentation.actions),
                    "presentation_version": 2,
                },
            ),
        )
        session = self._project_completion_read_state(session)
        if self._active_session is not None and self._active_session.session_id == session.session_id:
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list()
        self._finish_preflight_ui()

    def _on_preflight_failed(self, session_id: str, error: str) -> None:
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            self._finish_preflight_ui()
            return
        cancelled = "cancel" in str(error or "").casefold()
        job = {
            **dict(session.document_job),
            "status": "cancelled" if cancelled else "preflight_failed",
            "error_text": str(error or "assistant_preflight_failed"),
        }
        session = self._coordinator.update_state(session, document_job=job)
        actions = [{"id": "retry_preflight", "label": "重新检查"}]
        try:
            plan = DocumentPlan.from_dict(session.active_plan)
        except (TypeError, ValueError):
            plan = None
        if plan is not None and plan.production_contract.terminal_assembler == "official":
            actions.append(
                {"id": "edit_official_plan_requirements", "label": "修改公文信息"}
            )
        elif plan is not None and plan.production_contract.terminal_assembler == "exam":
            actions.append(
                {"id": "edit_exam_plan_requirements", "label": "修改试卷要求"}
            )
        else:
            actions.append({"id": "open_workbench", "label": "返回工作台"})
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="recovery",
                title="本地检查已取消" if cancelled else "本地检查未完成",
                body="",
                payload={"actions": actions},
            ),
        )
        session = self._project_completion_read_state(session)
        if self._active_session is not None and self._active_session.session_id == session_id:
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list()
        self._finish_preflight_ui()

    def _finish_preflight_ui(self) -> None:
        worker = self._preflight_worker
        if worker is not None:
            worker.deleteLater()
        self._preflight_worker = None
        self._sync_composer_busy_state()
        if (
            (self._content_worker is None or not self._content_worker.is_running)
            and (self._execution_worker is None or not self._execution_worker.is_running)
        ):
            self._stop_button.setVisible(False)

    def _start_execution(self, session: AssistantSession, plan: DocumentPlan) -> None:
        raw_preflight = session.document_job.get("preflight")
        if not isinstance(raw_preflight, dict):
            return
        try:
            preflight = PreflightReceipt.from_dict(raw_preflight)
            approval = self._document_jobs.approve(
                session_id=session.session_id,
                plan=plan,
                preflight=preflight,
            )
        except (ValueError, TypeError):
            return
        execution_id = uuid4().hex
        try:
            material_snapshot = self._material_snapshot_for_plan(session, plan)
        except (TypeError, ValueError):
            self._on_preflight_failed(
                session.session_id,
                "assistant_material_snapshot_unavailable",
            )
            return
        job = {
            **dict(session.document_job),
            "status": "execution_running",
            "execution_id": execution_id,
            "approval": approval.to_dict(),
        }
        session = self._coordinator.update_state(session, document_job=job)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="progress",
                title="正在生成文档",
                body="",
                payload={
                    "execution_id": execution_id,
                    "actions": [],
                    "ephemeral": True,
                    "progress_kind": "execution",
                },
            ),
        )
        self._active_session = session
        self._render_active_session()
        worker = DocumentExecutionWorker(
            self._document_jobs,
            session_id=session.session_id,
            plan=plan,
            preflight=preflight,
            approval=approval,
            material_snapshot=material_snapshot,
            execution_id=execution_id,
            parent=self,
        )
        self._execution_worker = worker
        worker.progress.connect(self._on_execution_progress)
        worker.finished.connect(self._on_execution_finished)
        self._composer.set_busy(True)
        worker.start()
        self._sync_composer_busy_state()

    def _on_execution_progress(self, current: int, total: int, message: str) -> None:
        worker = self._execution_worker
        if (
            worker is None
            or self._active_session is None
            or self._active_session.session_id != worker.session_id
        ):
            return
        text = str(message or "正在生成文档")
        if total > 0:
            text = f"{text}（{current}/{total}）"
        self._conversation_title.setText(text)

    def _on_execution_finished(self, result: object) -> None:
        worker = self._execution_worker
        if worker is None or not isinstance(result, dict):
            return
        origin_session_id = worker.session_id
        try:
            session = self._coordinator.load_session(origin_session_id)
        except (OSError, ValueError, TypeError):
            session = None
        if session is not None:
            status = str(result.get("status") or "failed")
            primary_path = str(result.get("output_path") or "")
            output_references = project_output_references(result)
            if not primary_path and output_references:
                primary_path = str(output_references[0].get("path") or "")
            job = {
                **dict(session.document_job),
                "status": status,
                "result": dict(result),
                "primary_output_path": primary_path,
            }
            session = self._coordinator.update_state(session, document_job=job)
            successful = status in {"success", "partial_success"}
            exam_runtime = result.get("exam_delivery_runtime")
            exam_runtime = (
                dict(exam_runtime)
                if isinstance(exam_runtime, Mapping)
                else {}
            )
            quality_status = str(
                exam_runtime.get("quality_status") or ""
            )
            actions = []
            if successful and primary_path:
                actions.append({"id": "open_artifact", "label": "打开文档"})
                actions.append(
                    {"id": "open_output_folder", "label": "打开所在文件夹"}
                )
            if status in {"partial_success", "failed", "cancelled"}:
                actions.append(
                    {
                        "id": "retry_preflight",
                        "label": (
                            "重新生成并复检"
                            if quality_status == "quality_review_required"
                            else "重新检查后重试"
                        ),
                    }
                )
            session = self._coordinator.append_message(
                session,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="artifact" if successful else "recovery",
                    title="文档已生成" if status == "success" else ("部分文档已生成" if status == "partial_success" else "文档生成未完成"),
                    body="",
                    payload={
                        "execution_id": worker.execution_id,
                        "actions": actions,
                        "reference": {
                            "type": "file",
                            "title": Path(primary_path).name if primary_path else "",
                            "path": primary_path,
                        },
                        "references": list(output_references),
                    },
                ),
            )
            session = self._project_completion_read_state(session)
            if self._active_session is not None and self._active_session.session_id == origin_session_id:
                self._active_session = session
                self._render_active_session()
        worker.deleteLater()
        self._execution_worker = None
        self._sync_composer_busy_state()
        if (
            (self._turn_worker is None or not self._turn_worker.is_running)
            and (self._content_worker is None or not self._content_worker.is_running)
            and (self._preflight_worker is None or not self._preflight_worker.is_running)
        ):
            self._stop_button.setVisible(False)
        self._refresh_session_list()

    def _runner_for_session(self, session: AssistantSession) -> AssistantTurnRunner:
        if self._fixed_turn_runner is not None:
            return self._fixed_turn_runner
        return AssistantTurnRunner(self._provider_router.resolve(session.provider_profile_id))

    def _refresh_provider_profiles(self) -> None:
        if self._active_session is not None:
            self._active_session = self._provider_selection.synchronize_session(
                self._active_session
            )
        if self._active_session is not None:
            selected = self._active_session.provider_profile_id
        else:
            try:
                selected = self._provider_router.profiles.active_profile_id()
            except (OSError, RuntimeError, TypeError, ValueError):
                selected = (
                    self._creative_home.composer.selected_provider_id()
                    or str(self._provider_combo.currentData() or "")
                    or "mock-default"
                )
        projected_profiles: list[tuple[str, str, str, bool, str, str]] = []
        try:
            profiles = self._provider_router.profiles.list_profiles()
        except (OSError, RuntimeError, TypeError, ValueError):
            profiles = (default_mock_profile(),)
        for profile in profiles:
            readiness = self._provider_router.readiness(profile.profile_id)
            status = provider_connection_badge(profile, ready=readiness.ready)
            projected_profiles.append(
                (
                    profile.label,
                    profile.profile_id,
                    profile.model_id,
                    readiness.ready,
                    readiness.message,
                    status,
                )
            )
        self._composer.set_provider_profiles(
            projected_profiles,
            selected_id=selected,
        )
        self._creative_home.composer.set_provider_profiles(
            projected_profiles,
            selected_id=selected,
        )
        self._provider_selection.select(selected)

    def _remember_active_provider(self, profile_id: str) -> None:
        if not profile_id:
            return
        try:
            self._provider_router.profiles.set_active_profile_id(profile_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return

    def _on_provider_selected(self, _index: int) -> None:
        profile_id = str(self._provider_combo.currentData() or "")
        if profile_id:
            self._creative_home.composer.select_provider(profile_id)
        if self._active_session is None:
            self._remember_active_provider(profile_id)
            return
        profile_id, model_id = self._provider_selection.selected_identity()
        previous_profile_id = self._active_session.provider_profile_id
        if profile_id == previous_profile_id:
            self._active_session = self._coordinator.update_state(
                self._active_session,
                model_id=model_id,
                touch_activity=False,
            )
            self._remember_active_provider(profile_id)
            return
        previous_domain = self._provider_data_domain(previous_profile_id)
        target_domain = self._provider_data_domain(profile_id)
        visible_history = tuple(
            message
            for message in self._active_session.messages
            if message.visible_text()
        )
        history_grant: dict[str, object] = {}
        if visible_history and previous_domain != target_domain:
            decision = self._confirm_provider_history_transition(
                previous_profile_id,
                profile_id,
                message_count=len(visible_history),
                character_count=sum(
                    len(message.visible_text())
                    for message in visible_history
                ),
            )
            if decision == "cancel":
                self._provider_selection.select(previous_profile_id)
                return
            if decision == "new":
                self._remember_active_provider(profile_id)
                self.new_session()
                return
            history_grant = {
                "schema_version": "assistant-provider-history-grant-v1",
                "grant_id": uuid4().hex,
                "session_id": self._active_session.session_id,
                "source_profile_id": previous_profile_id,
                "source_domain": previous_domain,
                "target_profile_id": profile_id,
                "target_domain": target_domain,
                "history_message_count": len(visible_history),
                "history_character_count": sum(
                    len(message.visible_text())
                    for message in visible_history
                ),
                "history_fingerprint": history_fingerprint(
                    self._active_session.messages
                ),
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        self._active_session = self._coordinator.update_state(
            self._active_session,
            provider_profile_id=profile_id,
            model_id=model_id,
            provider_history_grant=history_grant,
            touch_activity=False,
        )
        self._remember_active_provider(profile_id)
        if history_grant:
            self._active_session = self._coordinator.append_message(
                self._active_session,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="disclosure",
                    title="已确认携带历史并切换模型服务",
                    body="",
                    payload={
                        "active": False,
                        "facts": [
                            {
                                "label": "来源服务",
                                "value": previous_profile_id,
                            },
                            {
                                "label": "目标服务",
                                "value": profile_id,
                            },
                            {
                                "label": "历史字符",
                                "value": str(
                                    history_grant[
                                        "history_character_count"
                                    ]
                                ),
                            },
                            {
                                "label": "附件权限",
                                "value": "仍需逐次确认",
                            },
                        ],
                        "actions": [],
                    },
                ),
            )
            self._render_active_session()
            self._refresh_session_list(
                select_session_id=self._active_session.session_id
            )
