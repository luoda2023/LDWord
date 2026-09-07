"""Pure projection from Form assistant contracts to Design-style view models.

This module deliberately has no Qt imports.  Form remains the owner of session,
plan, approval and execution state; widgets consume only the normalized values
defined here and emit user intent back to the owning panel.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.assistant.application.output_references import project_output_references

_IMAGE_SUFFIXES = frozenset({"BMP", "GIF", "JPEG", "JPG", "PNG", "SVG", "WEBP"})

# These cards already communicate their complete state through the header and
# structured regions (facts, notices, files, progress, and actions).  A free-
# form description only repeats that information and makes dense conversations
# harder to scan.  Keep this policy in the projection layer so persisted cards
# from earlier builds are cleaned up when they are rendered too.
_BODYLESS_INTERACTION_TYPES = frozenset(
    {
        "approval",
        "disclosure",
        "format_evidence",
        "plan",
        "plan_candidate",
        "progress",
    }
)

_RIGHT_FLOW_ACTION_IDS = frozenset(
    {
        "approve_content_disclosure",
        "approve_execute",
        "approve_provider_disclosure",
        "confirm_outline_then_generate",
        "focus_continuation_response",
        "preflight",
    }
)
_LEFT_ACTION_ID_PREFIXES = (
    "deny_",
    "edit_",
    "open_",
    "restore_",
    "retry_",
    "runtime_open_",
)
_LEFT_ACTION_LABEL_PREFIXES = (
    "不发送",
    "修改",
    "取消",
    "打开",
    "拒绝",
    "恢复",
    "查看",
    "返回",
    "重新",
    "重试",
)
_RIGHT_ACTION_LABEL_MARKERS = ("下一步", "填写", "生成", "继续", "提交")
_ACTION_ICONS = {
    "approve_content_disclosure": "shield-check",
    "approve_execute": "file-output",
    "approve_provider_disclosure": "shield-check",
    "deny_content_disclosure": "x",
    "deny_provider_disclosure": "x",
    "edit_exam_plan_requirements": "pencil-line",
    "edit_official_plan_requirements": "pencil-line",
    "focus_continuation_response": "message-circle",
    "open_ai_settings": "settings",
    "open_artifact": "file-text",
    "open_content_draft": "file-text",
    "open_output_folder": "folder-open",
    "open_template_artifact": "file-text",
    "restore_previous_draft": "repeat",
    "retry_preflight": "refresh-ccw",
    "retry_provider_request": "refresh-ccw",
    "runtime_open_reference": "square-arrow-out-up-right",
    "skip_question_answer": "skip-forward",
}


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence_of_mappings(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, Mapping))


def _positive_int(value: object, *, maximum: int = 3) -> int:
    try:
        parsed = int(value or 1)
    except (TypeError, ValueError):
        parsed = 1
    return max(1, min(maximum, parsed))


def _target(reference: Mapping[str, object]) -> str:
    return str(
        reference.get("path")
        or reference.get("file_path")
        or reference.get("local_path")
        or reference.get("url")
        or reference.get("href")
        or reference.get("uri")
        or ""
    ).strip()


@dataclass(frozen=True, slots=True)
class FilePresentation:
    """A file at one point in the conversation lifecycle."""

    title: str
    suffix: str
    target: str
    kind: str
    state: str
    subtitle: str = ""
    reference: Mapping[str, Any] = field(default_factory=dict)

    @property
    def actionable(self) -> bool:
        return self.state in {"available", "external"}


@dataclass(frozen=True, slots=True)
class ChoicePresentation:
    choice_id: str
    label: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class QuestionInputPresentation:
    input_id: str
    label: str
    placeholder: str = ""
    value: str = ""
    required: bool = False
    column_span: int = 1


@dataclass(frozen=True, slots=True)
class ActionPresentation:
    action_id: str
    label: str
    variant: str = "secondary"
    enabled: bool = True
    alignment: str = "left"
    icon_name: str = "circle"


@dataclass(frozen=True, slots=True)
class InteractionPresentation:
    interaction_type: str
    eyebrow: str
    title: str
    body: str
    tone: str
    actions: tuple[ActionPresentation, ...] = ()
    files: tuple[FilePresentation, ...] = ()
    choices: tuple[ChoicePresentation, ...] = ()
    question_inputs: tuple[QuestionInputPresentation, ...] = ()
    choice_columns: int = 1
    question_input_columns: int = 1
    initial_choice_count: int = 0
    choices_label: str = ""
    expand_choices_label: str = ""
    collapse_choices_label: str = ""
    inputs_label: str = ""
    submit_label: str = "提交"
    compact_heading: bool = False
    multiple: bool = False
    allow_other: bool = False
    other_placeholder: str = ""
    requires_choice: bool = False
    can_skip: bool = False
    active: bool = True
    facts: tuple[tuple[str, str], ...] = ()
    notices: tuple[str, ...] = ()


def project_file_reference(reference: Mapping[str, object]) -> FilePresentation:
    """Normalize local files, folders and URLs without inventing availability."""

    raw = dict(reference)
    target = _target(raw)
    title = str(raw.get("title") or raw.get("name") or "").strip()
    path = Path(target).expanduser() if target and "://" not in target else None
    if not title:
        title = path.name if path is not None else target
    title = title or "未命名文件"

    explicit_suffix = str(raw.get("suffix") or raw.get("extension") or "").strip()
    suffix = explicit_suffix.lstrip(".").upper()
    if not suffix and path is not None:
        suffix = path.suffix.lstrip(".").upper()

    declared_kind = str(raw.get("kind") or raw.get("type") or "").strip().casefold()
    if declared_kind in {"url", "link", "web"} or (
        target and "://" in target and not target.casefold().startswith("file://")
    ):
        kind = "link"
        state = "external"
    elif declared_kind == "folder" or (path is not None and path.is_dir()):
        kind = "folder"
        state = "available" if path is not None and path.exists() else "missing"
    else:
        kind = "image" if suffix in _IMAGE_SUFFIXES or declared_kind == "image" else "file"
        if path is None or not target:
            state = "unknown"
        else:
            state = "available" if path.is_file() else "missing"

    subtitle = str(raw.get("description") or raw.get("summary") or "").strip()
    if not subtitle:
        if state == "missing":
            subtitle = "文件不可用"
        elif kind == "link":
            subtitle = "外部链接"

    return FilePresentation(
        title=title,
        suffix=suffix or ("LINK" if kind == "link" else "FILE"),
        target=target,
        kind=kind,
        state=state,
        subtitle=subtitle,
        reference=raw,
    )


def project_file_references(
    references: object,
) -> tuple[FilePresentation, ...]:
    return tuple(project_file_reference(item) for item in _sequence_of_mappings(references))


def _choice_rows(payload: Mapping[str, object]) -> tuple[dict[str, Any], ...]:
    request = _mapping(payload.get("confirmation_request"))
    raw = (
        request.get("options")
        or request.get("choices")
        or payload.get("options")
        or payload.get("choices")
        or ()
    )
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return ()
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            row = dict(item)
        else:
            row = {"id": str(index), "label": str(item)}
        if str(row.get("label") or row.get("title") or row.get("value") or "").strip():
            rows.append(row)
    return tuple(rows)


def _question_input_rows(payload: Mapping[str, object]) -> tuple[dict[str, Any], ...]:
    request = _mapping(payload.get("confirmation_request"))
    raw = request.get("inputs") or payload.get("inputs") or ()
    return tuple(
        row
        for row in _sequence_of_mappings(raw)
        if str(row.get("id") or row.get("key") or "").strip()
        and str(row.get("label") or "").strip()
    )


def _action_alignment(
    item: Mapping[str, object],
    *,
    action_id: str,
    label: str,
) -> str:
    explicit = str(item.get("alignment") or item.get("align") or "").strip().casefold()
    if explicit in {"left", "right"}:
        return explicit

    normalized_id = action_id.casefold()
    if label.startswith(_LEFT_ACTION_LABEL_PREFIXES):
        return "left"
    if normalized_id in _RIGHT_FLOW_ACTION_IDS:
        return "right"
    if normalized_id == "generate_content_draft":
        return "right"
    if normalized_id.startswith(("approve_", "continue_", "submit_")):
        return "right"
    if any(marker in label for marker in _RIGHT_ACTION_LABEL_MARKERS):
        return "right"
    if normalized_id.startswith(_LEFT_ACTION_ID_PREFIXES):
        return "left"
    return "left"


def _action_variant(item: Mapping[str, object], *, alignment: str) -> str:
    explicit = str(item.get("variant") or "").strip().casefold()
    if explicit in {"danger", "ghost-danger"}:
        return explicit
    return "primary" if alignment == "right" else "secondary"


def action_icon_name(
    action_id: str,
    label: str,
    *,
    alignment: str = "left",
    explicit_icon: str = "",
) -> str:
    """Resolve one durable Lucide icon from action intent, not button order."""

    explicit = str(explicit_icon or "").strip()
    if explicit:
        return explicit

    normalized_id = str(action_id or "").strip().casefold()
    normalized_label = str(label or "").strip()
    if normalized_id == "submit_question_answer":
        if "生成" in normalized_label:
            return "sparkles"
        if "下一步" in normalized_label or "继续" in normalized_label:
            return "chevron-right"
        return "send"
    if normalized_id == "confirm_outline_then_generate":
        return "check"
    if normalized_id == "generate_content_draft":
        return "refresh-ccw" if normalized_label.startswith("重新") else "sparkles"
    if normalized_id == "preflight":
        return (
            "file-output"
            if "Word" in normalized_label or "生成" in normalized_label
            else "file-check-2"
        )
    if normalized_id == "open_workbench":
        return "chevron-left" if normalized_label.startswith("返回") else "layout-dashboard"
    mapped = _ACTION_ICONS.get(normalized_id)
    if mapped:
        return mapped
    if normalized_label.startswith(("重新", "重试")):
        return "refresh-ccw"
    if normalized_label.startswith(("不发送", "取消", "拒绝")):
        return "x"
    if normalized_label.startswith("返回"):
        return "chevron-left"
    if "文件夹" in normalized_label:
        return "folder-open"
    if normalized_label.startswith(("打开", "查看")):
        return "eye"
    if normalized_label.startswith(("修改", "填写", "补充")):
        return "pencil-line"
    if "设置" in normalized_label:
        return "settings"
    if "生成" in normalized_label:
        return "sparkles"
    if "检查" in normalized_label:
        return "scan"
    if "下一步" in normalized_label or "继续" in normalized_label:
        return "chevron-right"
    if "提交" in normalized_label or "发送" in normalized_label:
        return "send"
    return "chevron-right" if alignment == "right" else "circle"


def _action_rows(payload: Mapping[str, object]) -> tuple[ActionPresentation, ...]:
    actions: list[ActionPresentation] = []
    card_active = bool(payload.get("active", True))
    for index, item in enumerate(_sequence_of_mappings(payload.get("actions"))):
        action_id = str(item.get("id") or f"action-{index}").strip()
        label = str(item.get("label") or "继续").strip()
        if not action_id or not label:
            continue
        alignment = _action_alignment(item, action_id=action_id, label=label)
        actions.append(
            ActionPresentation(
                action_id=action_id,
                label=label,
                variant=_action_variant(item, alignment=alignment),
                enabled=bool(item.get("enabled", True))
                and (
                    card_active
                    or action_id == "runtime_open_reference"
                ),
                alignment=alignment,
                icon_name=action_icon_name(
                    action_id,
                    label,
                    alignment=alignment,
                    explicit_icon=str(
                        item.get("icon_name") or item.get("icon") or ""
                    ),
                ),
            )
        )
    return tuple(actions)


def _interaction_files(payload: Mapping[str, object]) -> tuple[FilePresentation, ...]:
    rows: list[Mapping[str, object]] = []
    references = payload.get("references")
    if isinstance(references, Sequence) and not isinstance(
        references, (str, bytes, bytearray)
    ):
        rows.extend(
            item
            for item in references
            if isinstance(item, Mapping)
            and (
                _target(item)
                or str(item.get("title") or item.get("name") or "").strip()
            )
        )
    reference = payload.get("reference")
    if isinstance(reference, Mapping):
        target = _target(reference)
        has_identity = bool(
            target or str(reference.get("title") or reference.get("name") or "").strip()
        )
        if has_identity and not any(_target(item) == target for item in rows):
            rows.insert(0, reference)
    return tuple(project_file_reference(item) for item in rows)


def _reference_is_form_owned(value: object) -> bool:
    return bool(
        isinstance(value, Mapping)
        and str(value.get("owner") or "").strip().casefold() == "form"
    )


def _project_interaction_body(
    *,
    kind: str,
    body: str,
    payload: Mapping[str, object],
    choices: tuple[ChoicePresentation, ...],
    question_inputs: tuple[QuestionInputPresentation, ...],
) -> str:
    """Keep only body copy that adds information beyond card structure."""

    if kind in _BODYLESS_INTERACTION_TYPES:
        return ""
    if kind == "question" and (choices or question_inputs):
        return ""
    if kind == "artifact":
        references = _sequence_of_mappings(payload.get("references"))
        action_ids = {
            str(item.get("id") or "").strip().casefold()
            for item in _sequence_of_mappings(payload.get("actions"))
        }
        is_provider_reference = "runtime_open_reference" in action_ids
        is_local_form_artifact = bool(
            payload.get("draft_id")
            or payload.get("execution_id")
            or _reference_is_form_owned(payload.get("reference"))
            or any(_reference_is_form_owned(item) for item in references)
            or not is_provider_reference
        )
        if is_local_form_artifact:
            return ""
    return str(body or "").strip()


def project_interaction(
    *,
    interaction_type: str,
    title: str,
    body: str,
    payload: Mapping[str, object] | None = None,
) -> InteractionPresentation:
    """Project one typed Form interaction into Design's visual vocabulary."""

    kind = str(interaction_type or "info").strip().casefold()
    raw = dict(payload or {})
    labels = {
        "question": "需要补充",
        "outline_confirm": "确认章节目录",
        "disclosure": "数据披露",
        "permission": "权限确认",
        "plan_candidate": "下一步",
        "plan": "生成计划",
        "preflight": "执行前检查",
        "approval": "执行确认",
        "progress": "正在处理",
        "artifact": "文档产物",
        "format_evidence": "格式证据",
        "boundary": "能力边界",
        "recovery": "需要处理",
    }
    tones = {
        "disclosure": "warning",
        "permission": "warning",
        "preflight": "danger",
        "approval": "warning",
        "boundary": "warning",
        "recovery": "danger",
        "progress": "progress",
        "artifact": "success",
    }
    request = _mapping(raw.get("confirmation_request"))
    choice_rows = _choice_rows(raw)
    choices = tuple(
        ChoicePresentation(
            choice_id=str(
                item.get("id")
                or item.get("value")
                or item.get("key")
                or index
            ),
            label=str(item.get("label") or item.get("title") or item.get("value") or ""),
            description=str(item.get("description") or item.get("hint") or ""),
        )
        for index, item in enumerate(choice_rows)
    )
    question_inputs = tuple(
        QuestionInputPresentation(
            input_id=str(item.get("id") or item.get("key") or "").strip(),
            label=str(item.get("label") or "").strip(),
            placeholder=str(item.get("placeholder") or item.get("hint") or "").strip(),
            value=str(item.get("value") or item.get("default") or "").strip(),
            required=bool(item.get("required")),
            column_span=_positive_int(item.get("column_span")),
        )
        for item in _question_input_rows(raw)
    )
    selection_mode = str(
        request.get("selection_mode")
        or request.get("mode")
        or raw.get("selection_mode")
        or raw.get("mode")
        or ""
    ).casefold()
    multiple = bool(
        request.get("multiple")
        or raw.get("multiple")
        or selection_mode in {"multiple", "multi", "checkbox"}
    )
    try:
        choice_columns = max(
            1,
            min(
                3,
                int(
                    request.get("choice_columns")
                    or raw.get("choice_columns")
                    or 1
                ),
            ),
        )
    except (TypeError, ValueError):
        choice_columns = 1
    try:
        question_input_columns = max(
            1,
            min(
                3,
                int(
                    request.get("input_columns")
                    or raw.get("input_columns")
                    or 1
                ),
            ),
        )
    except (TypeError, ValueError):
        question_input_columns = 1
    try:
        initial_choice_count = max(
            0,
            min(
                len(choices),
                int(
                    request.get("initial_choice_count")
                    or raw.get("initial_choice_count")
                    or 0
                ),
            ),
        )
    except (TypeError, ValueError):
        initial_choice_count = 0
    allow_other = bool(
        request.get("allow_other")
        or request.get("other")
        or raw.get("allow_other")
    )
    other_placeholder = str(
        request.get("other_placeholder")
        or raw.get("other_placeholder")
        or ""
    ).strip()
    requires_choice = bool(
        request.get("requires_choice") or raw.get("requires_choice")
    )
    can_skip = bool(
        request.get("optional")
        or request.get("allow_skip")
        or raw.get("allow_skip")
    )
    facts: list[tuple[str, str]] = []
    raw_facts = raw.get("facts")
    if isinstance(raw_facts, Sequence) and not isinstance(
        raw_facts, (str, bytes, bytearray)
    ):
        for item in raw_facts:
            if isinstance(item, Mapping):
                label = str(item.get("label") or "").strip()
                value = str(item.get("value") or "").strip()
            elif isinstance(item, Sequence) and len(item) >= 2:
                label, value = str(item[0]).strip(), str(item[1]).strip()
            else:
                continue
            if label and value:
                facts.append((label, value))
    notices = tuple(
        str(item).strip()
        for item in (
            raw.get("notices")
            if isinstance(raw.get("notices"), Sequence)
            and not isinstance(raw.get("notices"), (str, bytes, bytearray))
            else ()
        )
        if str(item).strip()
    )
    projected_body = _project_interaction_body(
        kind=kind,
        body=body,
        payload=raw,
        choices=choices,
        question_inputs=question_inputs,
    )
    return InteractionPresentation(
        interaction_type=kind,
        eyebrow=labels.get(kind, "文档助手"),
        title=str(title or "需要确认"),
        body=projected_body,
        tone=tones.get(kind, "primary"),
        actions=_action_rows(raw),
        files=_interaction_files(raw),
        choices=choices,
        question_inputs=question_inputs,
        choice_columns=choice_columns,
        question_input_columns=question_input_columns,
        initial_choice_count=initial_choice_count,
        choices_label=str(
            request.get("choices_label") or raw.get("choices_label") or ""
        ).strip(),
        expand_choices_label=str(
            request.get("expand_choices_label")
            or raw.get("expand_choices_label")
            or ""
        ).strip(),
        collapse_choices_label=str(
            request.get("collapse_choices_label")
            or raw.get("collapse_choices_label")
            or ""
        ).strip(),
        inputs_label=str(
            request.get("inputs_label") or raw.get("inputs_label") or ""
        ).strip(),
        submit_label=str(
            request.get("submit_label") or raw.get("submit_label") or "提交"
        ).strip(),
        compact_heading=bool(
            request.get("compact_heading") or raw.get("compact_heading")
        ),
        multiple=multiple,
        allow_other=allow_other,
        other_placeholder=other_placeholder,
        requires_choice=requires_choice,
        can_skip=can_skip,
        active=bool(raw.get("active", True)),
        facts=tuple(facts),
        notices=notices,
    )


def build_question_response(
    labels: Sequence[str],
    *,
    other_text: str = "",
    skipped: bool = False,
) -> str:
    """Build the ordinary user message consumed by Form's continuation path."""

    if skipped:
        return "跳过这个问题"
    values = [str(item).strip() for item in labels if str(item).strip()]
    extra = str(other_text or "").strip()
    if extra:
        values.append(extra)
    return "；".join(values)


_PENDING_ID_KEYS = (
    "clarification_id",
    "completion_id",
    "disclosure_id",
    "continuation_id",
    "cursor",
    "turn_id",
)


def interaction_matches_pending_continuation(
    payload: Mapping[str, object],
    pending_continuation: Mapping[str, object] | None,
) -> bool:
    """Prove that a question-like card owns the pending continuation."""

    pending = dict(pending_continuation or {})
    if not pending:
        return False
    for key in _PENDING_ID_KEYS:
        candidate = str(payload.get(key) or "").strip()
        if candidate:
            return candidate == str(pending.get(key) or "").strip()
    continuation_ref = _mapping(payload.get("continuation_ref"))
    for key in _PENDING_ID_KEYS:
        candidate = str(continuation_ref.get(key) or "").strip()
        if candidate:
            return candidate == str(pending.get(key) or "").strip()
    request = _mapping(payload.get("confirmation_request"))
    for key in ("request_id", "confirmation_id", "id"):
        candidate = str(request.get(key) or "").strip()
        if candidate:
            return candidate == str(pending.get(key) or "").strip()
    # Legacy cards without a durable identity cannot safely answer a newer
    # continuation. The composer remains available as the recovery path.
    return False


def build_interaction_action_scope(
    *,
    pending_continuation: Mapping[str, object] | None,
    active_plan: Mapping[str, object] | None,
    document_job: Mapping[str, object] | None,
    turn_status: str = "",
) -> dict[str, object]:
    """Snapshot host-owned identities so click-time races fail closed."""

    pending = dict(pending_continuation or {})
    plan = dict(active_plan or {})
    job = dict(document_job or {})
    raw_preflight = job.get("preflight")
    preflight = dict(raw_preflight) if isinstance(raw_preflight, Mapping) else {}
    try:
        job_plan_revision = int(job.get("plan_revision") or 0)
    except (TypeError, ValueError):
        job_plan_revision = 0
    try:
        active_plan_revision = int(plan.get("revision") or 0)
    except (TypeError, ValueError):
        active_plan_revision = 0
    return {
        "version": 1,
        "turn_status": str(turn_status or ""),
        "job_id": str(job.get("job_id") or ""),
        "job_status": str(job.get("status") or ""),
        "job_plan_id": str(job.get("plan_id") or ""),
        "job_plan_revision": job_plan_revision,
        "active_plan_id": str(plan.get("plan_id") or ""),
        "active_plan_revision": active_plan_revision,
        "draft_id": str(job.get("generated_content_draft_id") or ""),
        "preflight_id": str(preflight.get("preflight_id") or ""),
        "execution_id": str(job.get("execution_id") or ""),
        "pending_kind": str(pending.get("kind") or ""),
        "pending_id": next(
            (
                str(pending.get(key) or "")
                for key in _PENDING_ID_KEYS
                if str(pending.get(key) or "").strip()
            ),
            "",
        ),
    }


def interaction_action_scope_is_current(
    scope: Mapping[str, object] | None,
    *,
    pending_continuation: Mapping[str, object] | None,
    active_plan: Mapping[str, object] | None,
    document_job: Mapping[str, object] | None,
    turn_status: str = "",
) -> bool:
    """Return true only for a scope created from the exact current state."""

    if not isinstance(scope, Mapping):
        return False
    try:
        if int(scope.get("version") or 0) != 1:
            return False
        return dict(scope) == build_interaction_action_scope(
            pending_continuation=pending_continuation,
            active_plan=active_plan,
            document_job=document_job,
            turn_status=turn_status,
        )
    except (TypeError, ValueError):
        return False


def interaction_is_active(
    *,
    interaction_type: str,
    payload: Mapping[str, object],
    pending_continuation: Mapping[str, object] | None,
    active_plan: Mapping[str, object] | None,
    document_job: Mapping[str, object] | None,
    turn_status: str = "",
) -> bool:
    """Resolve mutable card state outside widgets from persisted Form evidence."""

    kind = str(interaction_type or "info").casefold()
    job = dict(document_job or {})
    plan = dict(active_plan or {})
    pending = dict(pending_continuation or {})
    status = str(job.get("status") or "").casefold()
    if kind == "question":
        return interaction_matches_pending_continuation(payload, pending)
    if kind == "disclosure":
        return bool(
            str(pending.get("kind") or "") in {
                "local_provider_disclosure",
                "local_content_disclosure",
            }
            and str(pending.get("disclosure_id") or "")
            == str(payload.get("disclosure_id") or "")
        )
    if kind == "permission":
        # Form currently refuses to expose unverifiable Tool Call resume actions.
        return False
    if kind == "plan_candidate":
        # Retained only for read-only rendering of sessions created by older
        # builds. New requests create a deterministic Form plan directly.
        return False
    if kind == "plan":
        return bool(
            plan
            and str(plan.get("plan_id") or "") == str(payload.get("plan_id") or "")
            and int(plan.get("revision") or 0) == int(payload.get("revision") or 0)
            and status == "plan_ready"
        )
    if kind == "outline_confirm":
        # The directory-confirm card stays actionable only while the plan is
        # ready and no content generation attempt has started for it.
        return bool(
            plan
            and str(plan.get("plan_id") or "") == str(payload.get("plan_id") or "")
            and int(plan.get("revision") or 0) == int(payload.get("revision") or 0)
            and status in {"plan_ready", "content_generation_ready"}
        )
    if kind == "approval":
        preflight = job.get("preflight")
        current_id = (
            str(preflight.get("preflight_id") or "")
            if isinstance(preflight, Mapping)
            else ""
        )
        return bool(
            status == "needs_execution_approval"
            and current_id
            and current_id == str(payload.get("preflight_id") or "")
        )
    if kind == "progress":
        progress_kind = str(payload.get("progress_kind") or "")
        if progress_kind == "content_generation":
            generation_id = str(payload.get("generation_id") or "")
            return bool(
                status == "content_generation_running"
                and generation_id
                and generation_id == str(job.get("content_generation_id") or "")
            )
        if progress_kind == "preflight":
            preflight_run_id = str(payload.get("preflight_run_id") or "")
            return bool(
                status == "preflight_running"
                and preflight_run_id
                and preflight_run_id == str(job.get("preflight_run_id") or "")
            )
        if progress_kind == "execution":
            execution_id = str(payload.get("execution_id") or "")
            return bool(
                status == "execution_running"
                and execution_id
                and execution_id == str(job.get("execution_id") or "")
            )
        if bool(payload.get("ephemeral")) and any(
            str(job.get(key) or "")
            for key in (
                "content_generation_id",
                "preflight_run_id",
                "execution_id",
            )
        ):
            # Legacy progress cards had no run identity. Once a new identified
            # run exists they cannot represent the active attempt.
            return False
        return status in {
            "content_generation_running",
            "preflight_running",
            "execution_running",
        }
    if kind == "recovery":
        return bool(payload.get("_is_latest_recovery")) and bool(
            payload.get("actions")
        ) and str(turn_status or "").casefold() not in {
            "provider_running",
            "local_processing",
        } and status not in {
            "content_generation_running",
            "preflight_running",
            "execution_queued",
            "execution_running",
            "success",
            "partial_success",
        }
    if kind == "preflight":
        preflight = job.get("preflight")
        current_id = (
            str(preflight.get("preflight_id") or "")
            if isinstance(preflight, Mapping)
            else ""
        )
        return bool(
            status == "preflight_failed"
            and current_id
            and current_id == str(payload.get("preflight_id") or "")
        )
    if kind == "artifact":
        draft_id = str(payload.get("draft_id") or "").strip()
        if draft_id:
            return bool(
                status == "content_draft_ready"
                and draft_id
                == str(job.get("generated_content_draft_id") or "").strip()
            )
        execution_id = str(payload.get("execution_id") or "").strip()
        if execution_id:
            return bool(
                status in {"success", "partial_success"}
                and execution_id == str(job.get("execution_id") or "").strip()
            )
        action_ids = {
            str(item.get("id") or "").strip()
            for item in _sequence_of_mappings(payload.get("actions"))
        }
        workflow_actions = {
            "open_artifact",
            "open_output_folder",
            "open_content_draft",
            "generate_content_draft",
            "preflight",
            "retry_preflight",
            "approve_execute",
        }
        # Provider-returned artifacts are immutable references, not Form
        # workflow controls. They remain readable across later job stages.
        has_reference = bool(
            _mapping(payload.get("reference"))
            or _sequence_of_mappings(payload.get("references"))
        )
        return bool(
            ("runtime_open_reference" in action_ids or has_reference)
            and not action_ids.intersection(workflow_actions)
        )
    if kind in {"info", "boundary", "format_evidence"}:
        return bool(payload.get("active", True))
    return False


__all__ = [
    "ActionPresentation",
    "ChoicePresentation",
    "FilePresentation",
    "InteractionPresentation",
    "QuestionInputPresentation",
    "action_icon_name",
    "build_interaction_action_scope",
    "build_question_response",
    "interaction_action_scope_is_current",
    "interaction_is_active",
    "interaction_matches_pending_continuation",
    "project_file_reference",
    "project_file_references",
    "project_interaction",
    "project_output_references",
]
