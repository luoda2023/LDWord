"""Local exam-requirement clarification flow for the assistant UI."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from src.application.materials import ExecutionMaterialSnapshot
from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.contracts.material_snapshot import MaterialExecutionEnvelope
from src.assistant.contracts.messages import ROLE_ASSISTANT, ROLE_USER, AssistantMessage
from src.assistant.contracts.runtime import TURN_WAITING_USER_QUESTION
from src.assistant.storage.models import AssistantSession


class AssistantExamClarificationMixin:
    def _queue_local_exam_clarification(
        self,
        session: AssistantSession,
        *,
        query: str,
        turn_id: str,
        workspace: WorkspaceSnapshot,
        material_snapshot: ExecutionMaterialSnapshot | None,
        context_refs: tuple[dict[str, object], ...],
        route_id_override: str,
        clarification: Mapping[str, object],
    ) -> AssistantSession:
        clarification_id = uuid4().hex
        options = [
            dict(item)
            for item in clarification.get("options", ())
            if isinstance(item, Mapping)
        ]
        durable_material = MaterialExecutionEnvelope.capture(material_snapshot)
        continuation = {
            "kind": "local_exam_clarification",
            "clarification_id": clarification_id,
            "turn_id": turn_id,
            "root_query": query,
            "workspace": workspace.to_dict(include_local_path=True),
            "context_refs": [dict(item) for item in context_refs],
            "route_id_override": route_id_override,
            "options": options,
            "material_snapshot": durable_material.to_dict(),
        }
        job = {
            **dict(session.document_job),
            "status": "needs_route_clarification",
            "request_turn_id": turn_id,
            "route_id": route_id_override,
            "clarification_kind": "exam_requirements",
        }
        session = self._coordinator.update_state(
            session,
            pending_continuation=continuation,
            document_job=job,
            turn_status=TURN_WAITING_USER_QUESTION,
        )
        return self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="question",
                title=str(clarification.get("title") or "确认试卷要求"),
                body=str(clarification.get("prompt") or "请补充试卷要求。"),
                payload={
                    "confirmation_request": {
                        "kind": "local_exam_clarification",
                        "options": options,
                        "selection_mode": "single",
                        "allow_other": True,
                        "allow_skip": False,
                    },
                    "clarification_id": clarification_id,
                },
            ),
            turn_status=TURN_WAITING_USER_QUESTION,
        )

    def _resolve_local_exam_clarification(
        self,
        payload: Mapping[str, object],
    ) -> None:
        session = self._active_session
        if session is None:
            return
        continuation = dict(session.pending_continuation)
        if continuation.get("kind") != "local_exam_clarification":
            return
        if str(payload.get("clarification_id") or "") != str(
            continuation.get("clarification_id") or ""
        ):
            return
        option_labels = {
            str(item.get("id") or ""): str(item.get("label") or "")
            for item in continuation.get("options", ())
            if isinstance(item, Mapping)
        }
        selected_ids = tuple(
            str(item or "").strip()
            for item in payload.get("selected_choice_ids", ())
            if str(item or "").strip()
        )
        other_text = str(payload.get("other_text") or "").strip()
        answer = other_text or next(
            (
                option_labels[item]
                for item in selected_ids
                if item in option_labels
            ),
            "",
        )
        if not answer:
            return
        workspace_payload = continuation.get("workspace")
        if not isinstance(workspace_payload, Mapping):
            return
        try:
            workspace = WorkspaceSnapshot.from_dict(workspace_payload)
            raw_material = continuation.get("material_snapshot")
            material_snapshot = (
                MaterialExecutionEnvelope.from_dict(raw_material).restore()
                if isinstance(raw_material, Mapping)
                else None
            )
        except (TypeError, ValueError):
            return
        context_refs = tuple(
            dict(item)
            for item in continuation.get("context_refs", ())
            if isinstance(item, Mapping)
        )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.text(
                role=ROLE_USER,
                text=answer,
                source_refs=context_refs,
            ),
            turn_status="local_processing",
        )
        root_query = str(continuation.get("root_query") or "").strip()
        session = self._create_local_form_plan(
            session,
            query=f"{root_query}\n补充确认：{answer}",
            turn_id=str(continuation.get("turn_id") or uuid4().hex),
            workspace=workspace,
            material_snapshot=material_snapshot,
            route_id_override=str(
                continuation.get("route_id_override") or ""
            ),
        )
        self._active_session = session
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)


__all__ = ["AssistantExamClarificationMixin"]
