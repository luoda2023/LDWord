"""Helpers for surfacing execution-time diagnostics across reports and UI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.pipeline.result import PipelineResult


def extract_execution_diagnostics(result: "PipelineResult") -> list[dict[str, Any]]:
    """Collect user-facing diagnostics from tracker records or failed items."""
    tracker = getattr(result, "tracker", None)
    if tracker is not None:
        diagnostics = [
            _build_tracker_diagnostic(record)
            for record in tracker.get_all()
            if _is_diagnostic_record(record)
        ]
        if diagnostics:
            return diagnostics

    failed_items = list(getattr(result, "failed_items", []) or [])
    return [_build_failed_item_diagnostic(item) for item in failed_items]


def describe_execution_diagnostic(item: Mapping[str, Any]) -> str:
    """Render one diagnostic item into a compact user-facing line."""
    rule_name = str(item.get("rule_name") or "?").strip()
    target = str(item.get("target") or "").strip()
    reason = str(item.get("reason") or "").strip()

    prefix = f"[{rule_name}]"
    if target:
        prefix = f"{prefix} {target}"
    if reason:
        return f"{prefix}: {reason}"
    return prefix


def summarize_execution_diagnostics(
    diagnostics: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> str:
    """Build a short multi-line summary for workbench surfaces."""
    if not diagnostics:
        return ""

    visible_count = max(int(limit), 0)
    lines = [f"诊断提示（{len(diagnostics)}）"]
    for item in diagnostics[:visible_count]:
        lines.append(f"- {describe_execution_diagnostic(item)}")

    remaining = len(diagnostics) - visible_count
    if remaining > 0:
        lines.append(f"- 另有 {remaining} 条诊断，详见变更报告")
    return "\n".join(lines)


def build_execution_diagnostics(
    result: "PipelineResult",
    *,
    summary_limit: int = 3,
) -> dict[str, Any]:
    """Return structured diagnostics payload shared by reports and UI."""
    items = extract_execution_diagnostics(result)
    return {
        "count": len(items),
        "items": items,
        "summary": summarize_execution_diagnostics(items, limit=summary_limit),
    }


def _is_diagnostic_record(record) -> bool:
    return str(getattr(record, "change_type", "") or "") == "skip" or not bool(
        getattr(record, "success", True)
    )


def _build_tracker_diagnostic(record) -> dict[str, Any]:
    return {
        "rule_name": getattr(record, "rule_name", ""),
        "target": getattr(record, "target", ""),
        "section": getattr(record, "section", ""),
        "change_type": getattr(record, "change_type", ""),
        "before": getattr(record, "before", ""),
        "after": getattr(record, "after", ""),
        "paragraph_index": getattr(record, "paragraph_index", -1),
        "success": bool(getattr(record, "success", True)),
        "reason": _diagnostic_reason(
            failure_reason=getattr(record, "failure_reason", None),
            after=getattr(record, "after", ""),
            before=getattr(record, "before", ""),
            change_type=getattr(record, "change_type", ""),
        ),
    }


def _build_failed_item_diagnostic(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rule_name": str(item.get("rule_name") or ""),
        "target": str(item.get("target") or ""),
        "section": str(item.get("section") or ""),
        "change_type": str(item.get("change_type") or "error"),
        "before": "",
        "after": "",
        "paragraph_index": int(item.get("paragraph_index") or -1),
        "success": False,
        "reason": _diagnostic_reason(
            failure_reason=item.get("reason"),
            after="",
            before="",
            change_type=item.get("change_type"),
        ),
    }


def _diagnostic_reason(
    *,
    failure_reason: Any,
    after: Any,
    before: Any,
    change_type: Any,
) -> str:
    for value in (failure_reason, after, before, change_type):
        text = str(value or "").strip()
        if text:
            return text
    return ""
