"""Execution-report projections for section topology and page-layout policy."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def extract_section_layout_evidence(result) -> dict[str, Any] | None:
    context = getattr(result, "context", None)
    if context is None:
        return None
    inventory = getattr(context, "section_inventory", None)
    plan = getattr(context, "section_execution_plan", None)
    receipt = getattr(context, "section_execution_receipt", None)
    final_inventory = (
        getattr(context, "final_section_inventory", None)
        or getattr(context, "page_setup_final_inventory", None)
    )
    if inventory is None and plan is None and receipt is None and final_inventory is None:
        return None

    config = getattr(result, "config", None)
    page_setup = getattr(config, "page_setup", None)
    section_config = getattr(config, "section", None)
    operations = list(getattr(receipt, "applied_operations", ()) or ())
    blocked = list(
        getattr(receipt, "blocked_operations", ())
        or getattr(plan, "blocked_operations", ())
        or ()
    )
    source_count = int(
        getattr(receipt, "source_section_count", 0)
        or getattr(plan, "source_section_count", 0)
        or getattr(inventory, "section_count", 0)
        or 0
    )
    final_count = int(
        getattr(final_inventory, "section_count", 0)
        or getattr(receipt, "final_section_count", 0)
        or source_count
    )
    after_section_format_digest = str(
        getattr(receipt, "final_digest", "") or ""
    )
    final_digest = str(
        getattr(final_inventory, "digest", "") or after_section_format_digest
    )
    return {
        "boundary_mode": str(
            getattr(receipt, "boundary_mode", "")
            or getattr(plan, "boundary_mode", "")
            or getattr(section_config, "boundary_mode", "")
        ),
        "source_section_count": source_count,
        "final_section_count": final_count,
        "source_digest": str(
            getattr(receipt, "source_digest", "")
            or getattr(plan, "source_digest", "")
            or getattr(inventory, "digest", "")
        ),
        "after_section_format_digest": after_section_format_digest,
        "final_digest": final_digest,
        "paper_size_mode": str(getattr(page_setup, "paper_size_mode", "") or ""),
        "orientation_mode": str(getattr(page_setup, "orientation_mode", "") or ""),
        "margin_mode": str(getattr(page_setup, "margin_mode", "") or ""),
        "paper_size_by_section": dict(
            getattr(page_setup, "paper_size_by_section", {}) or {}
        ),
        "orientation_by_section": dict(
            getattr(page_setup, "orientation_by_section", {}) or {}
        ),
        "margin_by_section": {
            str(key): _margin_override_payload(value)
            for key, value in dict(
                getattr(page_setup, "margin_by_section", {}) or {}
            ).items()
        },
        "empty_break_policy": str(
            getattr(section_config, "empty_break_policy", "") or ""
        ),
        "caption_table_break_policy": str(
            getattr(section_config, "caption_table_break_policy", "") or ""
        ),
        "header_footer_link_mode": str(
            getattr(section_config, "header_footer_link_mode", "") or ""
        ),
        "required_semantic_starts": list(
            getattr(plan, "required_semantic_starts", ()) or ()
        ),
        "notes": list(getattr(plan, "notes", ()) or ()),
        "applied_operations": [_operation_payload(item) for item in operations],
        "blocked_operations": [_operation_payload(item) for item in blocked],
        "validation_errors": list(getattr(receipt, "validation_errors", ()) or ()),
        "final_sections": [
            _boundary_payload(item)
            for item in tuple(getattr(final_inventory, "boundaries", ()) or ())
        ],
    }


def format_section_layout_evidence_markdown(evidence: dict[str, Any]) -> list[str]:
    lines = [
        "## 分节与页面布局证据",
        "",
        f"- 分节边界策略: {evidence.get('boundary_mode') or '-'}",
        (
            "- 分节数量: "
            f"{evidence.get('source_section_count', 0)} → "
            f"{evidence.get('final_section_count', 0)}"
        ),
        (
            "- 页面策略: "
            f"纸张={evidence.get('paper_size_mode') or '-'}；"
            f"方向={evidence.get('orientation_mode') or '-'}；"
            f"页边距={evidence.get('margin_mode') or '-'}"
        ),
        (
            "- 按节覆盖: "
            f"纸张={len(evidence.get('paper_size_by_section') or {})}；"
            f"方向={len(evidence.get('orientation_by_section') or {})}；"
            f"页边距={len(evidence.get('margin_by_section') or {})}"
        ),
        (
            "- 清理策略: "
            f"空分节={evidence.get('empty_break_policy') or '-'}；"
            f"题注-表格={evidence.get('caption_table_break_policy') or '-'}"
        ),
        f"- 页眉页脚链接策略: {evidence.get('header_footer_link_mode') or '-'}",
        (
            "- 结构摘要: "
            f"源={_short_digest(evidence.get('source_digest'))}；"
            "分节阶段="
            f"{_short_digest(evidence.get('after_section_format_digest'))}；"
            f"最终={_short_digest(evidence.get('final_digest'))}"
        ),
        f"- 已执行操作: {len(evidence.get('applied_operations') or [])}",
        f"- 被阻止操作: {len(evidence.get('blocked_operations') or [])}",
    ]
    for operation in list(evidence.get("applied_operations") or [])[:20]:
        lines.append(
            f"  - {operation.get('action', '?')} @ body[{operation.get('body_index', -1)}]: "
            f"{operation.get('reason', '')}"
        )
    for operation in list(evidence.get("blocked_operations") or [])[:20]:
        lines.append(
            f"  - 阻止 {operation.get('action', '?')}: "
            f"{operation.get('blocked_reason', '')}"
        )
    for message in evidence.get("validation_errors") or []:
        lines.append(f"  - 校验错误: {message}")
    lines.append("")
    return lines


def _operation_payload(operation) -> dict[str, Any]:
    return {
        "action": str(getattr(operation, "action", "") or ""),
        "reason": str(getattr(operation, "reason", "") or ""),
        "body_index": _integer_or_default(getattr(operation, "body_index", -1), -1),
        "paragraph_index": _integer_or_default(
            getattr(operation, "paragraph_index", -1),
            -1,
        ),
        "element_path": list(getattr(operation, "element_path", ()) or ()),
        "target_break_type": str(
            getattr(operation, "target_break_type", "") or ""
        ),
        "blocked_reason": str(getattr(operation, "blocked_reason", "") or ""),
    }


def _boundary_payload(boundary) -> dict[str, Any]:
    return {
        "ordinal": _integer_or_default(getattr(boundary, "ordinal", 0), 0),
        "anchor_kind": str(getattr(boundary, "anchor_kind", "") or ""),
        "body_index": _integer_or_default(getattr(boundary, "body_index", -1), -1),
        "element_path": list(getattr(boundary, "element_path", ()) or ()),
        "break_type": str(getattr(boundary, "break_type", "") or ""),
        "page_size": dict(getattr(boundary, "page_size", ()) or ()),
        "page_margins": dict(getattr(boundary, "page_margins", ()) or ()),
        "header_footer_refs": [
            list(item) for item in tuple(getattr(boundary, "header_footer_refs", ()) or ())
        ],
        "title_page": bool(getattr(boundary, "title_page", False)),
        "page_numbering": dict(getattr(boundary, "page_numbering", ()) or ()),
        "columns": dict(getattr(boundary, "columns", ()) or ()),
        "protected_markup": list(getattr(boundary, "protected_markup", ()) or ()),
    }


def _short_digest(value: Any) -> str:
    digest = str(value or "")
    return digest[:12] if digest else "-"


def _integer_or_default(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _margin_override_payload(value) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return {}


__all__ = [
    "extract_section_layout_evidence",
    "format_section_layout_evidence_markdown",
]
