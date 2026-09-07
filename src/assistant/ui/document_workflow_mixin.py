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
from src.assistant.application.active_document_continuation import (
    ACTION_CONFIRM_OUTLINE_AND_GENERATE,
)
from src.assistant.application.capability_registry import (
    ENGINEERING_PROMPT_PROFILE_ID,
)
from src.assistant.application.content_generation_service import (
    AssistantContentGenerationService,
    ContentGenerationRequest,
)
from src.assistant.application.document_job_controller import DocumentJobController
from src.assistant.application.knowledge_sample_loader import (
    extract_knowledge_samples,
)
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
from src.assistant.ui.chapter_outline_panel import ChapterOutlinePanel
from src.assistant.ui.creative_home import AssistantCreativeHome, AssistantHeroComposer
from src.config.app_preferences import (
    material_disclosure_approved,
    material_disclosure_remember,
    set_material_disclosure_approved,
)
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
from src.config.app_preferences import streaming_reveal_interval_ms
from src.config.engineering_stage_library import resolve_engineering_guide
from src.config.library import load_scene_from_library
from src.qt_api import (
    QComboBox,
    QDesktopServices,
    QEvent,
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


# Cadence (ms) for feeding buffered stream text to the live chapter widget one
# line at a time.  Keeps large upstream SSE chunks readable as typewriter
# growth (tables gain rows row by row) instead of popping in all at once.
_CHAPTER_REVEAL_INTERVAL_MS = 42


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


def _execution_result_body(status: str, result: Mapping[str, object]) -> str:
    """Project terminal evidence into a concise user-visible explanation."""

    summary = " ".join(str(result.get("summary") or "").split())
    if status == "success":
        return summary
    if status == "partial_success":
        prefix = "候选文档已经生成并保留；存在需要人工复核的内容或质量项。"
        return f"{prefix}\n{summary}" if summary else prefix
    if status == "cancelled":
        return "生成已取消，没有覆盖原文件。"
    error = " ".join(str(result.get("error_text") or "").split())
    if not error:
        return "执行未能完成，且底层没有返回具体原因。请保留本次执行记录后重试。"
    if "exam_markdown_invalid:" in error:
        detail = error.split("exam_markdown_invalid:", 1)[1]
        parts = detail.split(":", 2)
        field_path = parts[0] if parts else "题稿字段"
        reason = parts[2] if len(parts) > 2 else detail
        return f"题稿字段 {field_path} 无法渲染：{reason}"
    if len(error) > 600:
        error = error[:599] + "…"
    return f"失败原因：{error}"


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
        # 可记住的一次性授权：偏好里开启“记住材料授权”且已同意过一次，
        # 后续逐章写作的材料确认卡不再重复弹出，直接按已授权继续。
        if (
            material_disclosure_remember()
            and material_disclosure_approved()
        ):
            self._active_session = session
            self._resolve_content_disclosure(
                {"disclosure_id": disclosure_id},
                approved=True,
            )
            return
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
        if approved and material_disclosure_remember():
            set_material_disclosure_approved(True)
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
        # 披露同意后的再入：一条龙意图已记入任务状态（确认卡点下时置位），
        # 继续携带，保证写作完成后仍自动预检并落盘。
        self._start_content_generation(
            session,
            plan,
            approved_disclosure=True,
            auto_generate_word=bool(
                dict(session.document_job or {}).get("auto_generate_word")
            ),
        )

    def _attempt_auto_outline(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
    ) -> bool:
        """Skip the intermediate plan card for fresh authoring requests.

        When a new multi-chapter document request lands on a deterministic Form
        plan (engineering / custom / generic), we want the assistant to look
        intelligent: it should go straight to the chapter-directory card instead
        of making the user first read and click a “文档处理计划” plan card.  Exam
        and official documents keep their own dedicated intake editors, so they
        are excluded here and continue to present the plan card as before.
        """
        if not plan.generation_required or plan.blocking_issues:
            return False
        if str(plan.work_mode_id or "").strip() in {"exam", "official"}:
            return False
        if str(
            getattr(plan.scene_ref or {}, "get", lambda *_: "")(
                "generation_mode"
            )
            or ""
        ) == "revision_pending":
            return False
        # Pre-flight the provider so an unconfigured model falls back to the
        # classic plan card (which still carries the “generate” action) rather
        # than leaving the user with nothing to press.
        try:
            if self._fixed_turn_runner is not None:
                gateway = self._fixed_turn_runner.gateway
            else:
                gateway = self._provider_router.resolve(
                    session.provider_profile_id
                )
        except (ProviderResolutionError, RuntimeError, ValueError, TypeError):
            return False
        if gateway is None:
            return False
        self._active_session = session
        try:
            self._start_content_generation(
                session,
                plan,
                outline_confirmed=False,
            )
        except Exception:  # noqa: BLE001 - never let auto-continue wedge the turn
            return False
        return True

    def _start_content_generation(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
        *,
        approved_disclosure: bool = False,
        revision_context_text: str = "",
        revision_context_ref: str = "",
        include_plan_materials: bool = True,
        outline_confirmed: bool = False,
        auto_generate_word: bool = False,
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
        is_revision_run = bool(str(revision_context_text or "").strip())
        # 材料披露只会在目录确认之后出现（此门更靠前并先返回），所以带
        # approved_disclosure 的再入意味着目录已确认，跳过二次确认门。
        if (
            not outline_confirmed
            and not approved_disclosure
            and not is_revision_run
        ):
            # 多章节起草：先让用户核对解析出的章节目录，点“确认目录”后才真正
            # 开始逐章写正文。目录在确认前只出现在这张确认卡片里，不提前写入
            # 左侧章节目录列表（确认后由下方的 _prepare_chapter_board 写入）。
            engineering_probe = _resolve_engineering_request_outline(
                plan.generation_contract.prompt_profile_id,
                plan.intent,
                material_refs=tuple(dict(item) for item in plan.material_refs),
            )
            probe_titles = tuple(
                str(item).strip()
                for item in engineering_probe[2]
                if str(item).strip()
            )
            # 用户在确认卡上编辑过的目录优先于重新解析的结果，二次打开
            # 卡片时仍显示已编辑的版本。
            try:
                edited_titles = tuple(
                    str(item).strip()
                    for item in (
                        session.document_job.get("outline_edited_titles") or ()
                    )
                    if str(item).strip()
                )
            except (AttributeError, TypeError, ValueError):
                edited_titles = ()
            if edited_titles:
                probe_titles = edited_titles
            if probe_titles:
                numbered = "\n".join(
                    f"{index}. {title}"
                    for index, title in enumerate(probe_titles, start=1)
                )
                updated = self._coordinator.append_message(
                    session,
                    AssistantMessage.interaction(
                        role=ROLE_ASSISTANT,
                        interaction_type="outline_confirm",
                        title="请确认章节目录",
                        body=(
                            f"按你的要求整理出 {len(probe_titles)} 章，请核对。"
                            f"确认后目录会进入左侧章节目录列表，随后逐章写正文：\n\n{numbered}"
                        ),
                        payload={
                            "plan_id": plan.plan_id,
                            "revision": plan.revision,
                            "editable_outline": list(probe_titles),
                            "actions": [
                                {
                                    "id": ACTION_CONFIRM_OUTLINE_AND_GENERATE,
                                    "label": "确认目录，开始写正文",
                                    "variant": "primary",
                                }
                            ],
                        },
                    ),
                    turn_status=TURN_COMPLETED,
                )
                self._active_session = updated
                self._render_active_session()
                self._refresh_session_list(select_session_id=updated.session_id)
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
        engineering_outline = _resolve_engineering_request_outline(
            plan.generation_contract.prompt_profile_id,
            plan.intent,
            material_refs=tuple(dict(item) for item in plan.material_refs),
        )
        # 用户在章节目录确认卡上编辑过的目录优先于附件解析与内置指南：
        # 确认时已写入任务状态，这里用编辑结果覆盖生成的标题清单。
        if not normalized_revision_text:
            try:
                override_titles = tuple(
                    str(item).strip()
                    for item in (
                        session.document_job.get("outline_edited_titles") or ()
                    )
                    if str(item).strip()
                )
            except (AttributeError, TypeError, ValueError):
                override_titles = ()
            if override_titles and engineering_outline[2]:
                # 仅当章数一致（用户只改名/排序）时保留逐章注释；
                # 增删章后注释与章节错位，整体丢弃以免误导写作。
                outline_notes = (
                    engineering_outline[3]
                    if len(engineering_outline[3]) == len(override_titles)
                    else ()
                )
                engineering_outline = (
                    engineering_outline[0],
                    engineering_outline[1],
                    override_titles,
                    outline_notes,
                )
        directory_payload = _directory_authoring_payload_from_plan(plan, engineering_outline)
        typesetting_template_id = self._active_typesetting_template_id()
        layout_template_id = str(plan.template_ref.get("id") or "").strip()
        knowledge_samples = (
            self._engineering_knowledge_samples(plan)
            if engineering_outline[2]
            else ()
        )
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
            outline_titles=engineering_outline[2],
            outline_notes=engineering_outline[3],
            engineering_stage_id=engineering_outline[0],
            engineering_doc_kind=engineering_outline[1],
            directory_outline_text=directory_payload["outline_text"],
            directory_doc_hint=directory_payload["doc_hint"],
            directory_root_title=directory_payload["root_title"],
            typesetting_template_id=typesetting_template_id,
            template_id=layout_template_id,
            mode_id=plan.work_mode_id,
            knowledge_samples=knowledge_samples,
            memory_dir=str(self._resolve_memory_dir() or ""),
        )
        adapter = AssistantContentGenerationAdapter(self._coordinator.store.root)
        service = AssistantContentGenerationService(adapter)
        worker = ContentGenerationWorker(service, request, gateway, parent=self)
        self._content_worker = worker
        # 多章节写作：右上角章节总览浮板显示已确认大纲，并逐章流式显示
        # AI 正在书写的正文；单章(无大纲)与整篇续写不进浮板。
        outline_titles = tuple(request.outline_titles or ())
        if outline_titles and not normalized_revision_text:
            self._prepare_chapter_board(
                list(outline_titles),
                session_id=session.session_id,
            )
            worker.chapter_event.connect(self._on_chapter_event)
        job = {
            **dict(session.document_job),
            "status": "content_generation_running",
            "content_generation_turn_id": plan.created_by_turn_id,
            "content_generation_id": generation_id,
            "content_generation_purpose": (
                "revision" if normalized_revision_text else "authoring"
            ),
        }
        # 一条龙模式：用户在章节目录确认卡上确认后，写作完成即自动
        # 预检并落盘成 Word，不再要求第二次“生成 Word”点按。意图记入
        # 任务状态，草稿完成钩子据此自动接管后续链路。
        if auto_generate_word:
            job["auto_generate_word"] = True
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

    def _active_typesetting_template_id(self) -> str:
        """Return the currently active visual typesetting template id.

        Reads the persisted active id from the template store (set from the
        visual template dialog).  Falls back to the built-in default when no
        override is stored, so authoring is never blocked.
        """
        try:
            from src.assistant.application.typesetting_templates import (
                TypesettingTemplateStore,
            )

            return TypesettingTemplateStore().active_template_id()
        except Exception:
            return ""

    def _engineering_knowledge_samples(self, plan: DocumentPlan) -> tuple:
        """Slice attached engineering sample docs into per-chapter excerpts.

        Only used for the chapter-by-chapter engineering authoring flow;
        reads each existing material reference (docx/doc/wps/md) and keeps
        a bounded amount of real prose so the AI learns the trade style.
        """
        samples: list = []
        for raw in tuple(getattr(plan, "material_refs", ()) or ()):
            if not isinstance(raw, dict):
                continue
            path_text = str(
                raw.get("path") or raw.get("file_path") or raw.get("local_path") or ""
            ).strip()
            if not path_text:
                continue
            path = Path(path_text).expanduser()
            if not path.is_file():
                continue
            suffix = path.suffix.casefold()
            if suffix not in {".docx", ".doc", ".wps", ".md", ".markdown", ".txt"}:
                continue
            try:
                from src.assistant.application.knowledge_sample_loader import (
                    extract_knowledge_samples,
                )

                samples.extend(extract_knowledge_samples(path))
            except Exception:
                continue
        return tuple(samples)

    # ---- 章节写作总览：右上角浮板 + 对话内流式正文 -------------------
    def _prepare_chapter_board(
        self,
        titles: list[str],
        *,
        session_id: str,
    ) -> None:
        """Open (or refresh) the top-right chapter overview board."""
        message_scroll = getattr(self, "_message_scroll", None)
        if message_scroll is None or not hasattr(message_scroll, "viewport"):
            return
        viewport = message_scroll.viewport()
        board = getattr(self, "_chapter_board", None)
        if board is None or board.parentWidget() is not viewport:
            if board is not None:
                board.deleteLater()
            board = ChapterOutlinePanel(viewport)
            board.closed.connect(self._on_chapter_board_hidden)
            self._chapter_board = board
        self._chapter_run_session_id = str(session_id or "")
        self._chapter_done_ids = set()
        self._chapter_chars = {}
        self._chapter_live_widget = None
        self._chapter_buffers: dict[int, str] = {}
        # Line-by-line reveal queue: upstream SSE chunks can carry several
        # markdown rows at once (a whole table / paragraph).  Feeding them to
        # the live widget one line at a time keeps the typewriter feel even
        # for large chunks, so tables grow row by row instead of popping.
        reveal_timer = getattr(self, "_chapter_reveal_timer", None)
        if reveal_timer is None:
            reveal_timer = QTimer(self)
            reveal_timer.setSingleShot(True)
            reveal_timer.timeout.connect(self._on_chapter_reveal_tick)
            self._chapter_reveal_timer = reveal_timer
        else:
            reveal_timer.stop()
        reveal_timer.setInterval(streaming_reveal_interval_ms(_CHAPTER_REVEAL_INTERVAL_MS))
        self._chapter_reveal_pending = ""
        self._chapter_reveal_widget = None
        self._chapter_reveal_index = 0
        board.set_outline(list(titles or ()))
        board.set_collapsed(False)
        board.show_board()
        # Mirror the outline into the persistent left dock too.
        dock_present = getattr(self, "_dock_outline_present", None)
        if dock_present is not None:
            dock_present(list(titles or ()))
        # 默认打开右侧 Markdown 编辑视图并停在第一章：用户确认目录后就要
        # 逐章看 AI 写作，右侧编辑器应当直接可见（可随时点“收起”关掉），
        # 不需要用户再手动点开。后续点章节浏览不会再次自动弹出。
        marktext_view = getattr(self, "_marktext_view", None)
        if marktext_view is not None and not marktext_view.isVisible():
            try:
                self._refresh_marktext_view()
            except (OSError, ValueError, RuntimeError):
                pass
            marktext_view.show()
            marktext_view.raise_()
            try:
                marktext_view.set_active_chapter(1)
            except (AttributeError, TypeError, ValueError):
                pass

    def _hide_chapter_board(self) -> None:
        board = getattr(self, "_chapter_board", None)
        if board is not None:
            board.close_board()
        self._discard_chapter_reveal()
        self._chapter_live_widget = None
        self._chapter_run_session_id = ""

    def _on_chapter_board_hidden(self) -> None:
        # 用户手动隐藏浮板；流式正文不受影响，下一次写作会重新打开。
        pass

    def _reposition_chapter_board(self) -> None:
        board = getattr(self, "_chapter_board", None)
        if board is not None:
            board._reposition_in_parent()

    def _finish_chapter_run(self, *, mark_failed: bool = False) -> None:
        self._finalize_any_live_chapter_message(
            status_text="该章生成中断，已保留已写部分" if mark_failed else "已完成",
            persist=mark_failed,
        )
        board = getattr(self, "_chapter_board", None)
        if board is not None and mark_failed:
            board.fail()

    def _on_chapter_event(
        self,
        phase: str,
        index: int,
        total: int,
        title: str,
        chars: int,
        text: str,
    ) -> None:
        """UI-thread handler for worker chapter events."""
        active = getattr(self, "_active_session", None)
        if (
            active is None
            or active.session_id != getattr(self, "_chapter_run_session_id", "")
        ):
            return
        # Word-workbench live view: mirror the stream when visible and
        # parked on the chapter being written; refresh score at 'done'.
        session_id = (
            getattr(self, "_workbench_session_id", "")
            or active.session_id
        )
        # Keep a sidecar copy so scoring + reload work even when the
        # workbench was opened mid-run (no begin_run outline).
        try:
            self._cache.ensure_chapter(session_id, int(index), str(title))
        except (OSError, ValueError, RuntimeError):
            pass
        if phase == "delta" and str(text or ""):
            try:
                self._cache.append_chapter(session_id, int(index), str(text))
            except (OSError, ValueError, RuntimeError):
                pass
            # The right-side MarkText view receives this same stream through
            # the line-by-line reveal queue (_pump_chapter_reveal mirrors each
            # revealed line via _marktext_view_for) so its tables grow row by
            # row in lock-step with the left message.  No direct whole-chunk
            # append here — a large upstream chunk would jump the whole table
            # in at once.
        # Materialise inline data-URL images as soon as the chapter finishes,
        # independent of which panes are visible, so the right-side editor (and
        # any later export) always sees relative image paths instead of raw
        # base64.  This also pushes the final body back into the live editor.
        if phase == "done":
            try:
                self._materialize_chapter_images(session_id, int(index))
            except (OSError, ValueError, RuntimeError):
                pass
        bench = getattr(self, "_chapter_workbench", None)
        if bench is not None and bench.isVisible():
            current = int(getattr(bench, "_current_index", 0) or 0)
            if phase == "done":
                try:
                    entry = self._cache.update_state(
                        session_id, int(index), "done", rescan_score=True
                    )
                except (OSError, ValueError, RuntimeError):  # noqa: BLE001
                    entry = None
                if entry is not None:
                    bench.navigator.set_state(int(index), entry.state)
                    bench.navigator.set_stats(
                        int(index),
                        chars=entry.chars,
                        score=entry.score,
                        grade=entry.grade,
                    )
                    if current == int(index):
                        body = self._cache.read_chapter(session_id, int(index))
                        if str(body or "").strip():
                            self._render_workbench_chapter(int(index))
        board = getattr(self, "_chapter_board", None)
        if board is not None:
            if phase == "start":
                board.begin(index=index, total=total, title=title)
            elif phase == "delta":
                accumulated = int(self._chapter_chars.get(index, 0)) + len(
                    str(text or "")
                )
                self._chapter_chars[index] = accumulated
                board.delta(index=index, chars=accumulated)
            elif phase == "done":
                board.done(index=index, chars=max(0, int(chars)))
        if phase == "start":
            self._begin_chapter_live_message(index, str(title or f"第 {index} 章"))
            # Reset the embedded MarkText buffer and park it on the chapter
            # being written so the live stream is visible immediately.
            marktext_view = getattr(self, "_marktext_view", None)
            if marktext_view is not None and marktext_view.isVisible():
                marktext_view.start_chapter(int(index))
                marktext_view.set_active_chapter(int(index))
        elif phase == "delta":
            self._stream_chapter_delta(index, str(text or ""))
        elif phase == "done":
            self._finish_chapter_live_message(index, max(0, int(chars)))

        # Keep the persistent left outline dock in sync.
        dock_sync_state = getattr(self, "_dock_sync_state", None)
        if dock_sync_state is not None:
            if phase == "start":
                dock_sync_state(index, "running")
            elif phase == "done":
                dock_sync_state(index, "done")
                dock_sync_stats = getattr(self, "_dock_sync_stats", None)
                if dock_sync_stats is not None:
                    entry = None
                    try:
                        entry = self._cache.update_state(
                            session_id, int(index), "done", rescan_score=True
                        )
                    except (OSError, ValueError, RuntimeError):
                        entry = None
                    if entry is not None:
                        dock_sync_stats(
                            int(index),
                            chars=entry.chars,
                            score=entry.score,
                            grade=entry.grade,
                        )
        if phase == "reconcile_report" and str(text or ""):
            self._show_typesetting_reconcile_report(str(text))

    def _show_typesetting_reconcile_report(self, raw_json: str) -> None:
        """Surface the post-generation typesetting reconcile report as a chat
        message: a non-blocking quality note telling the user which layout rules
        were checked and any deviations found."""
        try:
            import json as _json

            payload = _json.loads(raw_json)
        except (ValueError, TypeError):
            return
        deviations = payload.get("deviations") or []
        warn_count = int(payload.get("warn_count") or 0)
        fix_count = int(payload.get("fix_count") or 0)
        checked = payload.get("checked") or []
        lines: list[str] = []
        lines.append("排版复核校准已完成。")
        if checked:
            lines.append("已核对：" + "、".join(str(item) for item in checked) + "。")
        if deviations:
            for item in deviations:
                severity = str(item.get("severity") or "info")
                message_text = str(item.get("message") or "")
                auto_fixed = bool(item.get("auto_fixed"))
                prefix = "已自动修正" if auto_fixed else ("提示" if severity == "warn" else "")
                if prefix:
                    lines.append(f"- {prefix}：{message_text}")
                else:
                    lines.append(f"- {message_text}")
        else:
            lines.append("未发现需要修正的排版偏差。")
        if fix_count:
            lines.append(f"（本次自动修正 {fix_count} 处。）")
        elif warn_count:
            lines.append(f"（存在 {warn_count} 处建议关注项。）")
        session = getattr(self, "_active_session", None)
        if session is None:
            return
        try:
            updated = self._coordinator.append_message(
                session,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="progress",
                    title="排版复核校准",
                    body="\n".join(lines),
                    payload={
                        "actions": [],
                        "ephemeral": False,
                        "progress_kind": "typesetting_reconcile",
                        "reconcile_report": payload,
                    },
                ),
            )
        except (OSError, ValueError, RuntimeError):
            return
        if getattr(self, "_active_session", None) is not None and \
                getattr(self, "_active_session", None).session_id == session.session_id:
            self._active_session = updated
            self._render_active_session()

    def _begin_chapter_live_message(self, index: int, title: str) -> None:
        """Open a live AI message in the conversation for this chapter."""
        if (
            getattr(self, "_conversation_stack", None) is None
            or self._conversation_stack.currentWidget() is not self._active_page
        ):
            self._chapter_live_widget = None
            return
        self._finalize_any_live_chapter_message()
        message_host = getattr(self, "_message_host", None)
        if message_host is None or not hasattr(self, "_message_layout"):
            self._chapter_live_widget = None
            return
        message = AssistantConversationMessage(
            text="",
            role=ROLE_ASSISTANT,
            live=True,
            status_text=f"正在撰写第 {index} 章 · {title}",
            parent=message_host,
        )
        message._chapter_index = int(index)
        if hasattr(self, "_wire_message_widget"):
            self._wire_message_widget(message)
        self._message_layout.insertWidget(
            self._message_layout.count() - 1,
            message,
        )
        self._chapter_live_widget = message
        if hasattr(self, "_begin_follow_latest_layout_settle"):
            self._begin_follow_latest_layout_settle()

    def _materialize_chapter_images(self, session_id: str, index: int) -> None:
        """Decode inline data-URL images in a finished chapter, rewrite the
        cached body to relative paths, and accumulate the resource mapping."""

        body = self._cache.read_chapter(session_id, int(index))
        if not body:
            return
        rewritten, mapping = self._cache.extract_images(session_id, body)
        if mapping:
            try:
                self._cache.replace_chapter(session_id, int(index), rewritten)
            except (OSError, ValueError, RuntimeError):
                return
            accumulated = getattr(self, "_session_resource_paths", None)
            if accumulated is None:
                accumulated = {}
                self._session_resource_paths = accumulated
            accumulated.update(mapping)
            # The right-side editor streamed the raw base64 delta; push the
            # materialised relative-path body so its images render immediately
            # instead of staying as un-decoded data URLs.
            marktext_view = getattr(self, "_marktext_view", None)
            if marktext_view is not None and marktext_view.isVisible():
                marktext_view.refresh_chapter(int(index), rewritten)

    def _stream_chapter_delta(self, index: int, delta: str) -> None:
        message = getattr(self, "_chapter_live_widget", None)
        buffers = getattr(self, "_chapter_buffers", None)
        if buffers is not None:
            buffers[index] = buffers.get(index, "") + delta
        accumulated = int(self._chapter_chars.get(index, 0))
        if not delta:
            return
        # The reveal queue serves both panes.  Each side is independent: the
        # left live message (may not be laid out / visible on the very first
        # frame) and the right-side rich-text view (only while it is visible
        # and parked on this chapter).  If neither consumer is alive the whole
        # delta is dropped from the UI queue — the body is already cached and
        # buffered above, so nothing is ever lost.
        left_done = (
            message is None
            or id(message) in getattr(self, "_chapter_done_ids", set())
        )
        right = self._marktext_view_for(index)
        if left_done and right is None:
            self._discard_chapter_reveal()
            return
        self._chapter_reveal_index = int(index)
        self._chapter_reveal_widget = message
        self._chapter_reveal_pending = (
            getattr(self, "_chapter_reveal_pending", "") + delta
        )
        self._pump_chapter_reveal(
            index=index,
            accumulated=accumulated,
            force=False,
        )

    def _pump_chapter_reveal(
        self,
        *,
        index: int,
        accumulated: int,
        force: bool,
    ) -> None:
        """Feed at most one completed line of buffered delta to each pane.

        ``force`` feeds everything to the left message at once (used right
        before a chapter is finalised so no text is left unplayed); the right
        view is never force-fed because ``done`` pushes the final body
        wholesale.  When buffered text remains, the single-shot reveal timer
        continues the typewriter cadence for both panes in lock-step.
        """
        pending = getattr(self, "_chapter_reveal_pending", "")
        if not pending:
            return
        message = getattr(self, "_chapter_live_widget", None)
        left_alive = bool(
            message is not None
            and self._chapter_reveal_widget is message
            and id(message)
            not in getattr(self, "_chapter_done_ids", set())
        )
        right = self._marktext_view_for(index) if not force else None
        if not left_alive and right is None:
            self._discard_chapter_reveal()
            return
        if force:
            feed, rest = pending, ""
        else:
            boundary = pending.find("\n")
            if boundary < 0:
                feed, rest = pending, ""
            else:
                feed, rest = pending[: boundary + 1], pending[boundary + 1 :]
        self._chapter_reveal_pending = rest
        if feed:
            if left_alive:
                message.append_live_delta(
                    delta=feed,
                    status_text=f"正在撰写第 {index} 章 · 已写约 {accumulated} 字",
                )
            if right is not None:
                try:
                    right.append_chapter_delta(int(index or 0), str(feed))
                except (OSError, ValueError, RuntimeError):
                    pass
            if not force:
                bench_ed = self._workbench_editor_for(index)
                if bench_ed is not None:
                    try:
                        bench_ed.append_raw(str(feed))
                    except (OSError, ValueError, RuntimeError):
                        pass
        if feed:
            # 逐章写作期间始终把对话区钉在最新正文：无论用户此前是否滚动
            # 离开底部，每一行新正文都会自动滚回让正在写的文字保持可见。
            # (layout settle timer 在静止 ~80ms 后解除钉住，所以流式一停
            # 用户即可自由翻阅已写内容。)
            scroll = getattr(self, "_schedule_stream_scroll_to_bottom", None)
            if scroll is not None:
                scroll()
        if rest:
            timer = getattr(self, "_chapter_reveal_timer", None)
            if timer is not None and not timer.isActive():
                timer.start()

    def _on_chapter_reveal_tick(self) -> None:
        """Reveal tick: feed the next buffered line to each live pane."""
        index = int(getattr(self, "_chapter_reveal_index", 0) or 0)
        accumulated = int(getattr(self, "_chapter_chars", {}).get(index, 0))
        self._pump_chapter_reveal(
            index=index,
            accumulated=accumulated,
            force=False,
        )

    def _marktext_view_for(self, index: int) -> object | None:
        """The right-side rich-text view when it should receive this chapter's
        stream: visible and parked on the chapter being written.

        While hidden the view receives nothing (its chapter buffer starts
        clean on the next visible run); the final body is pushed wholesale on
        ``done`` by ``_finish_chapter_live_message``.
        """
        marktext_view = getattr(self, "_marktext_view", None)
        if marktext_view is None or not marktext_view.isVisible():
            return None
        try:
            active = int(marktext_view.bridge.active_chapter() or 0)
        except (AttributeError, TypeError, ValueError):
            return None
        if active != int(index or 0):
            return None
        return marktext_view

    def _workbench_editor_for(self, index: int):
        """The left chapter workbench editor when it should receive this
        chapter's stream: visible and parked on the chapter being written.

        Returns the editor widget or ``None`` when the workbench is hidden
        or showing a different chapter.
        """
        bench = getattr(self, "_chapter_workbench", None)
        if bench is None or not bench.isVisible():
            return None
        try:
            current = int(getattr(bench, "_current_index", 0) or 0)
        except (TypeError, ValueError):
            return None
        if current != int(index or 0):
            return None
        return getattr(bench, "editor", None)

    def _flush_chapter_reveal(self) -> None:
        """Force-feed buffered reveal text before the chapter widget ends."""
        message = getattr(self, "_chapter_live_widget", None)
        if message is None:
            self._discard_chapter_reveal()
            return
        index = 0
        try:
            index = int(getattr(message, "_chapter_index", 0) or 0)
        except (TypeError, ValueError):
            index = 0
        accumulated = int(getattr(self, "_chapter_chars", {}).get(index, 0))
        self._pump_chapter_reveal(
            index=index,
            accumulated=accumulated,
            force=True,
        )
        self._discard_chapter_reveal()

    def _discard_chapter_reveal(self) -> None:
        """Stop the reveal timer and drop buffered-but-unplayed UI text.

        The full body is already persisted to the chapter cache / side buffers
        before reaching this queue, so discarding never loses content.
        """
        timer = getattr(self, "_chapter_reveal_timer", None)
        if timer is not None:
            timer.stop()
        self._chapter_reveal_pending = ""
        self._chapter_reveal_widget = None
        self._chapter_reveal_index = 0

    def _finish_chapter_live_message(self, index: int, chars: int) -> None:
        # Play any buffered-but-unrevealed lines before the widget is closed
        # so the finished chapter shows every streamed character.
        self._flush_chapter_reveal()
        message = getattr(self, "_chapter_live_widget", None)
        self._chapter_live_widget = None
        if message is None or id(message) in getattr(self, "_chapter_done_ids", set()):
            return
        message.finalize_live(status_text=f"第 {index} 章已完成 · 共 {chars:,} 字")
        self._chapter_done_ids.add(id(message))
        self._chapter_chars.pop(index, None)
        buffers = getattr(self, "_chapter_buffers", None)
        text = str(getattr(message, "_text", "") or "")
        if not text and buffers is not None:
            text = str(buffers.get(index, "") or "")
        if text:
            self._append_chapter_message_to_history(index, text)
        if buffers is not None:
            buffers.pop(index, None)
        # On 'done' push the chapter's final (image-materialised) body into the
        # right-side rich-text view wholesale, so it ends complete whether the
        # user had it open during the run or opened it mid-run (the stream only
        # reaches it while visible).
        marktext_view = getattr(self, "_marktext_view", None)
        if marktext_view is not None and marktext_view.isVisible():
            active = getattr(self, "_active_session", None)
            session_id = (
                getattr(self, "_workbench_session_id", "")
                or (active.session_id if active is not None else "")
            )
            final_body = ""
            try:
                final_body = self._cache.read_chapter(session_id, int(index))
            except (OSError, ValueError, RuntimeError):
                final_body = ""
            if str(final_body or "").strip():
                try:
                    marktext_view.refresh_chapter(int(index), str(final_body))
                except (OSError, ValueError, RuntimeError):
                    pass
        if hasattr(self, "_begin_follow_latest_layout_settle"):
            self._begin_follow_latest_layout_settle()

    def _append_chapter_message_to_history(self, index: int, text: str) -> None:
        """Persist one finished chapter as a normal assistant chat message."""
        session = getattr(self, "_active_session", None)
        if session is None:
            return
        try:
            updated = self._coordinator.append_message(
                session,
                AssistantMessage.text(
                    role=ROLE_ASSISTANT,
                    text=str(text or ""),
                ),
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            return
        if updated is not None:
            self._active_session = updated

    def _finalize_any_live_chapter_message(
        self,
        *,
        status_text: str = "本章已完成",
        persist: bool = False,
    ) -> None:
        message = getattr(self, "_chapter_live_widget", None)
        # Play buffered-but-unrevealed lines before the widget is closed so
        # interrupted/stopped chapters still show their full streamed body.
        self._flush_chapter_reveal()
        self._chapter_live_widget = None
        if message is None:
            return
        index = 0
        try:
            index = int(getattr(message, "_chapter_index", 0) or 0)
        except (TypeError, ValueError):
            index = 0
        if index and persist:
            text = str(getattr(message, "_text", "") or "")
            buffers = getattr(self, "_chapter_buffers", None)
            if not text and buffers is not None:
                text = str(buffers.get(index, "") or "")
            if text:
                self._append_chapter_message_to_history(index, text)
            if buffers is not None:
                buffers.pop(index, None)
            # Flag the chapter as failed in the right-side embedded view so the
            # user sees the interruption while the partial body stays visible.
            marktext_view = getattr(self, "_marktext_view", None)
            if marktext_view is not None and marktext_view.isVisible():
                marktext_view.fail_chapter(index)
        message.finalize_live(status_text=status_text)
        self._chapter_done_ids.add(id(message))

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
        # 一条龙：确认目录时已表明“直接出 Word”，草稿完成后自动接管
        # 预检→落盘链路（仍保留覆盖文件等必要闸门），并保留打开草稿
        # 等次级动作，用户无需第二次点按。
        auto_generate_word = bool(
            dict(session.document_job or {}).get("auto_generate_word")
        )
        if auto_generate_word:
            session = self._coordinator.update_state(
                session,
                active_plan=updated_plan.to_dict(),
                document_job={
                    **dict(session.document_job),
                    "auto_generate_word": False,
                },
                turn_status=TURN_COMPLETED,
            )
            self._active_session = session
            self._run_preflight(session, updated_plan)
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
        # 分章写作失败/取消：浮板当前章节标记为中断，正文消息收尾。
        if not cancelled and getattr(self, "_chapter_run_session_id", "") == session_id:
            self._finish_chapter_run(mark_failed=True)
        else:
            self._chapter_live_widget = None
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
        self._discard_chapter_reveal()
        self._sync_composer_busy_state()
        if self._execution_worker is None or not self._execution_worker.is_running:
            self._stop_button.setVisible(False)
        if not hasattr(self, "_chapter_live_widget"):
            self._chapter_live_widget = None
        if not hasattr(self, "_chapter_run_session_id"):
            self._chapter_run_session_id = ""

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
        # 智能精简：当本地检查干净通过、且没有需要用户亲眼确认的情形（覆盖
        # 已有文件、或试卷需要复核的候选版）时，不再额外弹一张“确认生成”卡，
        # 直接从用户那一次“生成 Word”点按继续执行到落盘。
        if (
            preflight.ready
            and not self._preflight_needs_confirmation(current_plan, preflight)
        ):
            self._start_execution(session, current_plan)
            self._finish_preflight_ui()
            return
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

    def _preflight_needs_confirmation(
        self,
        plan: DocumentPlan,
        preflight: object,
    ) -> bool:
        """Whether a ready preflight still needs the user to confirm execution.

        We auto-continue after a clean preflight so the “生成 Word” click flows
        straight through to the finished document.  A confirmation gate is kept
        only when the user's eyes are genuinely needed: replacing an existing
        output file, or an exam candidate version that is offered for review.
        """
        warnings = tuple(str(item or "") for item in preflight.warnings)
        if bool(getattr(plan.output_policy, "overwrite", False)):
            return True
        if any("output_replacement_requested" in item for item in warnings):
            return True
        if any("exam_source_warning" in item for item in warnings):
            return True
        return False

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
                    title=(
                        "文档已生成"
                        if status == "success"
                        else (
                            "候选文档已生成，建议复核"
                            if status == "partial_success"
                            else "文档生成未完成"
                        )
                    ),
                    body=_execution_result_body(status, result),
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


def _directory_authoring_payload_from_plan(
    plan: DocumentPlan,
    engineering_outline: tuple[str, str, tuple[str, ...], tuple[str, ...]],
) -> dict[str, object]:
    """Build directory metadata for the content request (may be empty)."""
    payload: dict[str, object] = {
        "outline_text": "",
        "doc_hint": "",
        "root_title": "",
    }
    if str(plan.generation_contract.prompt_profile_id or "").strip() != ENGINEERING_PROMPT_PROFILE_ID:
        return payload
    from src.assistant.application.directory_authoring_parser import (
        parse_authoring_payload,
    )
    parsed = parse_authoring_payload(
        plan.intent,
        attachments=tuple(dict(item) for item in plan.material_refs),
        context_text="",
    )
    if not parsed["found_any"]:
        return payload
    titles = tuple(parsed["titles"])
    if not titles:
        return payload
    payload["outline_text"] = str(parsed["outline_text"] or "")
    payload["doc_hint"] = str(parsed["doc_hint"] or "")
    payload["root_title"] = str(parsed["root_title"] or "")
    return payload


def _resolve_engineering_request_outline(
    prompt_profile_id: str,
    intent: str,
    *,
    material_refs: tuple[dict[str, object], ...] = (),
) -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
    """Resolve engineering stage/doc outline plus per-chapter notes.

    A user-attached outline (Markdown/plain text chapter list) always wins
    over the built-in keyword-matched guide, so the software writes strictly
    by the user's own directory.
    """
    if str(prompt_profile_id or "").strip() != ENGINEERING_PROMPT_PROFILE_ID:
        return ("", "", (), ())
    from src.assistant.application.directory_authoring_parser import (
        parse_directory_attachments,
    )
    parsed_titles, parsed_notes, _outline_text, _error, found = (
        parse_directory_attachments(material_refs)
    )
    if found and parsed_titles:
        return (
            "",
            "",
            tuple(str(item).strip() for item in parsed_titles if str(item).strip()),
            tuple(str(item).strip() for item in parsed_notes),
        )
    return resolve_engineering_guide(intent)

