"""Local, structured intake for underspecified official-document requests."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from src.application.materials import ExecutionMaterialSnapshot
from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.contracts.material_snapshot import MaterialExecutionEnvelope
from src.assistant.contracts.messages import ROLE_ASSISTANT, ROLE_USER, AssistantMessage
from src.assistant.contracts.runtime import TURN_WAITING_USER_QUESTION
from src.assistant.storage.models import AssistantSession
from src.config.official_document_profiles import list_official_document_profiles
from src.services.official_draft_source import infer_official_document_type_id

_OFFICIAL_TYPE_DESCRIPTIONS = {
    "resolution": "对重大事项作出决议。",
    "decision": "对重要事项作出决定或部署。",
    "order": "公布行政法规、任免或奖惩。",
    "bulletin": "公布重要决定或重大事项。",
    "announcement": "向国内外宣布重要事项。",
    "notice_public": "在一定范围公布应知事项。",
    "opinion": "对重要问题提出见解和办法。",
    "notice": "部署或传达执行事项。",
    "circular": "表彰先进、批评错误或传达情况。",
    "report": "向上级汇报工作情况。",
    "request": "向上级请求指示或批准。",
    "approval": "答复下级机关请示。",
    "proposal": "向会议或机关提出审议事项。",
    "letter": "机关之间商洽或答复事项。",
    "minutes": "记录会议情况和议定事项。",
}
_OFFICIAL_COMMON_TYPE_IDS = (
    "notice",
    "notice_public",
    "circular",
    "report",
    "request",
    "letter",
    "minutes",
)
_OFFICIAL_TYPE_CHOICE_BY_ID = {
    profile.profile_id: {
        "id": profile.profile_id,
        "label": profile.label,
        "description": _OFFICIAL_TYPE_DESCRIPTIONS.get(
            profile.profile_id,
            "按所选文种规则起草。",
        ),
    }
    for profile in list_official_document_profiles()
}
_OFFICIAL_TYPE_CHOICES = tuple(
    _OFFICIAL_TYPE_CHOICE_BY_ID[profile_id]
    for profile_id in (
        *_OFFICIAL_COMMON_TYPE_IDS,
        *(
            profile_id
            for profile_id in _OFFICIAL_TYPE_CHOICE_BY_ID
            if profile_id not in _OFFICIAL_COMMON_TYPE_IDS
        ),
    )
)
_OFFICIAL_TYPE_LABELS = {
    str(item["id"]): str(item["label"])
    for item in _OFFICIAL_TYPE_CHOICES
}


def official_request_needs_intake(
    query: str,
    *,
    document_type_id: str = "",
) -> bool:
    """Whether the local official workflow still needs its minimum intake."""

    return not (
        str(document_type_id or "").strip()
        or infer_official_document_type_id(query)
    )


class AssistantOfficialClarificationMixin:
    def _queue_local_official_clarification(
        self,
        session: AssistantSession,
        *,
        query: str,
        turn_id: str,
        workspace: WorkspaceSnapshot,
        material_snapshot: ExecutionMaterialSnapshot | None,
        context_refs: tuple[dict[str, object], ...],
        route_id_override: str,
    ) -> AssistantSession:
        clarification_id = uuid4().hex
        durable_material = MaterialExecutionEnvelope.capture(material_snapshot)
        continuation = {
            "kind": "local_official_clarification",
            "clarification_id": clarification_id,
            "turn_id": turn_id,
            "root_query": query,
            "workspace": workspace.to_dict(include_local_path=True),
            "context_refs": [dict(item) for item in context_refs],
            "route_id_override": route_id_override,
            "options": [dict(item) for item in _OFFICIAL_TYPE_CHOICES],
            "material_snapshot": durable_material.to_dict(),
        }
        job = {
            **dict(session.document_job),
            "status": "needs_route_clarification",
            "request_turn_id": turn_id,
            "route_id": route_id_override,
            "clarification_kind": "official_requirements",
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
                title="确认公文基本要求",
                body="",
                payload={
                    "clarification_id": clarification_id,
                    "confirmation_request": {
                        "kind": "local_official_clarification",
                        "options": [
                            dict(item) for item in _OFFICIAL_TYPE_CHOICES
                        ],
                        "selection_mode": "single",
                        "choice_columns": 2,
                        "initial_choice_count": len(
                            _OFFICIAL_COMMON_TYPE_IDS
                        ),
                        "expand_choices_label": "更多文种（8）",
                        "collapse_choices_label": "收起更多文种",
                        "input_columns": 2,
                        "choices_label": "选择文种",
                        "inputs_label": "填写基本信息",
                        "submit_label": "生成计划",
                        "compact_heading": True,
                        "allow_other": True,
                        "other_placeholder": (
                            "其他文种，如：通报、公告、决定"
                        ),
                        "requires_choice": True,
                        "allow_skip": False,
                        "inputs": [
                            {
                                "id": "organization",
                                "label": "发文机关",
                                "placeholder": "例如：示例市教育局",
                                "required": True,
                            },
                            {
                                "id": "recipient",
                                "label": "主送对象",
                                "placeholder": "可选，例如：各区教育局",
                            },
                            {
                                "id": "purpose",
                                "label": "核心事项",
                                "placeholder": "说明要传达、安排或解决的事项",
                                "required": True,
                                "column_span": 2,
                            },
                        ],
                    },
                },
            ),
            turn_status=TURN_WAITING_USER_QUESTION,
        )

    def _resolve_local_official_clarification(
        self,
        payload: Mapping[str, object],
    ) -> None:
        session = self._active_session
        if session is None:
            return
        continuation = dict(session.pending_continuation)
        if continuation.get("kind") != "local_official_clarification":
            return
        if str(payload.get("clarification_id") or "") != str(
            continuation.get("clarification_id") or ""
        ):
            return

        selected_ids = tuple(
            str(item or "").strip()
            for item in payload.get("selected_choice_ids", ())
            if str(item or "").strip()
        )
        other_type = str(payload.get("other_text") or "").strip()
        document_type_id = next(
            (item for item in selected_ids if item in _OFFICIAL_TYPE_LABELS),
            "",
        ) or infer_official_document_type_id(other_type)
        if not document_type_id:
            return

        raw_fields = payload.get("field_values")
        field_values = (
            {
                str(key or "").strip(): str(value or "").strip()
                for key, value in raw_fields.items()
            }
            if isinstance(raw_fields, Mapping)
            else {}
        )
        organization = field_values.get("organization", "")
        purpose = field_values.get("purpose", "")
        if not organization or not purpose:
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

        type_label = _OFFICIAL_TYPE_LABELS.get(
            document_type_id,
            other_type or document_type_id,
        )
        details = [
            f"公文文种：{type_label}",
            f"发文机关：{organization}",
        ]
        recipient = field_values.get("recipient", "")
        if recipient:
            details.append(f"主送机关：{recipient}")
        details.append(f"核心事项：{purpose}")
        answer = "；".join(details)

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
            scene_ref_updates={
                "official_field_values": {
                    "document_type": document_type_id,
                    "organization": organization,
                    **({"recipient": recipient} if recipient else {}),
                },
                "official_content_requirements": purpose,
            },
        )
        self._active_session = session
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)


__all__ = [
    "AssistantOfficialClarificationMixin",
    "official_request_needs_intake",
]
