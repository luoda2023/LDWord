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


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence_of_mappings(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, Mapping))


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
class ActionPresentation:
    action_id: str
    label: str
    variant: str = "secondary"
    enabled: bool = True


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
    multiple: bool = False
    allow_other: bool = False
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
        elif suffix:
            subtitle = f"{suffix} 文件"

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


def _action_rows(payload: Mapping[str, object]) -> tuple[ActionPresentation, ...]:
    actions: list[ActionPresentation] = []
    for index, item in enumerate(_sequence_of_mappings(payload.get("actions"))):
        action_id = str(item.get("id") or f"action-{index}").strip()
        label = str(item.get("label") or "继续").strip()
        if not action_id or not label:
            continue
        actions.append(
            ActionPresentation(
                action_id=action_id,
                label=label,
                variant=str(item.get("variant") or ("primary" if index == 0 else "secondary")),
                enabled=bool(item.get("enabled", True)),
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
    allow_other = bool(
        request.get("allow_other")
        or request.get("other")
        or raw.get("allow_other")
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
    return InteractionPresentation(
        interaction_type=kind,
        eyebrow=labels.get(kind, "文档助手"),
        title=str(title or "需要确认"),
        body=str(body or ""),
        tone=tones.get(kind, "primary"),
        actions=_action_rows(raw),
        files=_interaction_files(raw),
        choices=choices,
        multiple=multiple,
        allow_other=allow_other,
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


def interaction_is_active(
    *,
    interaction_type: str,
    payload: Mapping[str, object],
    pending_continuation: Mapping[str, object] | None,
    active_plan: Mapping[str, object] | None,
    document_job: Mapping[str, object] | None,
) -> bool:
    """Resolve mutable card state outside widgets from persisted Form evidence."""

    kind = str(interaction_type or "info").casefold()
    job = dict(document_job or {})
    plan = dict(active_plan or {})
    pending = dict(pending_continuation or {})
    status = str(job.get("status") or "").casefold()
    if kind == "question":
        return bool(pending)
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
            and status not in {"execution_running", "success", "partial_success"}
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
        return status in {
            "content_generation_running",
            "preflight_running",
            "execution_running",
        }
    if kind == "recovery":
        return status not in {"execution_running", "success"}
    return bool(payload.get("active", True))


__all__ = [
    "ActionPresentation",
    "ChoicePresentation",
    "FilePresentation",
    "InteractionPresentation",
    "build_question_response",
    "interaction_is_active",
    "project_file_reference",
    "project_file_references",
    "project_interaction",
    "project_output_references",
]
