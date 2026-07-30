"""Terminal-result rendering instructions for the quick-execution surface."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.execution_result_contract import normalize_terminal_payload
from src.ui.adapters.workbench_artifact_items import workbench_artifact_display_items

from .state import ExecutionResultState


@dataclass(frozen=True, slots=True)
class QuickExecutionLogEntry:
    level: str
    message: str


@dataclass(frozen=True, slots=True)
class QuickExecutionResultPresentation:
    terminal_payload: dict[str, object]
    status: str
    status_text: str
    status_tone: str
    summary: str
    error_text: str
    issue_count: int
    success: bool
    cancelled: bool
    expand_log: bool
    execute_button_text: str
    retry_profile_ids: tuple[str, ...]
    batch_run_id: str
    batch_attempt_number: int
    log_entries: tuple[QuickExecutionLogEntry, ...]


def build_execution_result_presentation(
    state: ExecutionResultState,
) -> QuickExecutionResultPresentation:
    """Convert terminal state into one immutable UI rendering instruction."""

    terminal_payload, payload_error = _safe_terminal_payload(
        getattr(state, "terminal_payload", {}) or {}
    )
    status = "failed" if payload_error else state.status
    summary = payload_error or state.summary
    error_text = payload_error or state.error_text
    issue_count = len(list(getattr(state, "issue_items", []) or []))
    success = status in {"success", "partial_success"}
    cancelled = status == "cancelled"
    if success:
        status_text = "✓ 本次生成完成"
        if issue_count:
            status_text += f"；{issue_count} 项提醒"
        status_tone = "success"
    elif cancelled:
        status_text, status_tone = "已取消", "hint"
    else:
        status_text, status_tone = "执行失败", "error"

    batch_isolation = dict(getattr(state, "batch_isolation", {}) or {})
    retry_profile_ids = tuple(
        text
        for text in (
            str(profile_id or "").strip()
            for profile_id in list(
                batch_isolation.get("retry_eligible_profile_ids", []) or []
            )
        )
        if text
    )
    return QuickExecutionResultPresentation(
        terminal_payload=terminal_payload,
        status=status,
        status_text=status_text,
        status_tone=status_tone,
        summary=summary,
        error_text=error_text,
        issue_count=issue_count,
        success=success,
        cancelled=cancelled,
        expand_log=not success and not cancelled,
        execute_button_text="重新生成" if success else "生成文档",
        retry_profile_ids=retry_profile_ids,
        batch_run_id=str(batch_isolation.get("history_run_id") or "").strip(),
        batch_attempt_number=max(1, _safe_int(batch_isolation.get("attempt_number"), 1)),
        log_entries=tuple(
            _execution_result_log_entries(
                state,
                success=success,
                cancelled=cancelled,
                summary=summary,
                error_text=error_text,
            )
        ),
    )


def _execution_result_log_entries(
    state: ExecutionResultState,
    *,
    success: bool,
    cancelled: bool,
    summary: str,
    error_text: str,
) -> list[QuickExecutionLogEntry]:
    level = "success" if success else "info" if cancelled else "error"
    entries = [
        QuickExecutionLogEntry(
            level,
            summary or ("已取消" if cancelled else "执行失败"),
        )
    ]
    _append_artifact_log_entries(entries, state)
    _append_evidence_log_entries(entries, state)
    if error_text:
        entries.append(
            QuickExecutionLogEntry("info" if cancelled else "error", error_text)
        )
    return entries


def _append_artifact_log_entries(
    entries: list[QuickExecutionLogEntry],
    state: ExecutionResultState,
) -> None:
    for label, path in workbench_artifact_display_items(
        state.output_paths,
        delivery_preset_labels=True,
    ):
        entries.append(QuickExecutionLogEntry("info", f"输出文件[{label}]：{path}"))
    if state.output_path and not state.output_paths:
        entries.append(QuickExecutionLogEntry("info", f"输出文件：{state.output_path}"))
    artifact_groups = (
        (state.compare_paths, "对比稿", True),
        (state.intermediate_paths, "中间产物", True),
        (state.material_manifest_paths, "资料清单", False),
        (state.material_package_paths, "资料包", False),
    )
    for paths, group_label, delivery_labels in artifact_groups:
        for label, path in workbench_artifact_display_items(
            paths,
            delivery_preset_labels=delivery_labels,
        ):
            entries.append(
                QuickExecutionLogEntry("info", f"{group_label}[{label}]：{path}")
            )
    for item in list(state.artifact_items or []):
        if item.detail:
            entries.append(
                QuickExecutionLogEntry(
                    "warning",
                    f"产物预检[{item.label}]：{item.detail}",
                )
            )
    if state.report_paths:
        entries.append(
            QuickExecutionLogEntry("info", f"报告文件：{', '.join(state.report_paths)}")
        )


def _append_evidence_log_entries(
    entries: list[QuickExecutionLogEntry],
    state: ExecutionResultState,
) -> None:
    if state.style_source_summary:
        entries.append(QuickExecutionLogEntry("info", state.style_source_summary))
    _append_summary_and_details(
        entries,
        summary=state.object_preflight_summary,
        payload=getattr(state, "object_preflight", {}) or {},
        count_keys=("findings_count", "module_skips_count"),
        details=list(state.object_preflight_details or []),
        detail_prefix="对象预检明细：",
        default_level="info",
    )
    _append_summary_and_details(
        entries,
        summary=state.material_field_consistency_summary,
        payload=getattr(state, "material_field_consistency", {}) or {},
        count_keys=("issue_count",),
        details=[],
        detail_prefix="",
        default_level="warning",
    )
    if state.attachment_bundle_summary:
        attachment_level = _summary_level(
            state.attachment_bundles,
            ("failed_binding_count",),
            default_level="warning",
        )
        entries.append(
            QuickExecutionLogEntry(attachment_level, state.attachment_bundle_summary)
        )
    if state.material_dependency_summary:
        entries.append(QuickExecutionLogEntry("info", state.material_dependency_summary))
    _append_summary_and_details(
        entries,
        summary=state.batch_isolation_summary,
        payload=getattr(state, "batch_isolation", {}) or {},
        count_keys=("failed_count",),
        details=list(state.batch_isolation_details or []),
        detail_prefix="Batch isolation detail: ",
        default_level="warning",
    )


def _append_summary_and_details(
    entries: list[QuickExecutionLogEntry],
    *,
    summary: str,
    payload: object,
    count_keys: tuple[str, ...],
    details: list[str],
    detail_prefix: str,
    default_level: str,
) -> None:
    if not summary:
        return
    level = _summary_level(payload, count_keys, default_level=default_level)
    entries.append(QuickExecutionLogEntry(level, summary))
    for line in details:
        entries.append(QuickExecutionLogEntry(level, f"{detail_prefix}{line}"))


def _summary_level(
    payload: object,
    count_keys: tuple[str, ...],
    *,
    default_level: str,
) -> str:
    if not isinstance(payload, dict):
        return default_level
    try:
        has_findings = any(int(payload.get(key) or 0) > 0 for key in count_keys)
    except (TypeError, ValueError):
        return default_level
    return "warning" if has_findings else "info"


def _safe_terminal_payload(value: object) -> tuple[dict[str, object], str]:
    try:
        return normalize_terminal_payload(value), ""
    except Exception as exc:
        error_text = f"Invalid terminal payload: {type(exc).__name__}: {exc}"
        return (
            {
                "status": "failed",
                "output_path": "",
                "report_paths": [],
                "failed_count": 0,
                "error_text": error_text,
                "diagnostics_count": 0,
                "diagnostics_summary": "",
                "terminal_payload_contract_error": error_text,
            },
            error_text,
        )


def _safe_int(value: object, fallback: int) -> int:
    try:
        return int(value or fallback)
    except (TypeError, ValueError):
        return fallback


__all__ = [
    "QuickExecutionLogEntry",
    "QuickExecutionResultPresentation",
    "build_execution_result_presentation",
]
