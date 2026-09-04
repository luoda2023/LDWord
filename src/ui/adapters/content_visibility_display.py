from __future__ import annotations

from typing import Iterable

from src.config.content_visibility_selectors import (
    COMMON_CONTENT_VISIBILITY_SELECTOR_OPTIONS,
    ContentVisibilitySelectorOption,
    content_visibility_selector_label,
)

_CONTENT_VISIBILITY_SELECTOR_DESCRIPTIONS = {
    option.selector: option.description
    for option in COMMON_CONTENT_VISIBILITY_SELECTOR_OPTIONS
}


def content_visibility_selector_display(selector: object) -> str:
    normalized = str(selector or "").strip()
    label = content_visibility_selector_label(normalized)
    if not normalized or label == normalized:
        return label
    return f"{label} ({normalized})"


def content_visibility_selector_tooltip(
    selector: object,
    description: str = "",
) -> str:
    normalized = str(selector or "").strip()
    if not normalized:
        return "选择或扫描一个内容块。"
    resolved_description = (
        str(description or "").strip()
        or _CONTENT_VISIBILITY_SELECTOR_DESCRIPTIONS.get(normalized, "")
    )
    lines = [f"内容块名：{normalized}", f"文档标记：{{{{#visibility:{normalized}}}}}"]
    if resolved_description:
        lines.insert(0, resolved_description)
    return "\n".join(lines)


def format_content_visibility_selector_list(
    selectors: Iterable[object],
    *,
    include_raw_for_known: bool = False,
    limit: int = 6,
) -> str:
    cleaned = [
        str(selector or "").strip()
        for selector in selectors
        if str(selector or "").strip()
    ]
    if not cleaned:
        return "-"
    visible = cleaned[:limit]
    suffix = "" if len(cleaned) <= limit else f" 等 {len(cleaned)} 项"
    if include_raw_for_known:
        labels = [content_visibility_selector_display(selector) for selector in visible]
    else:
        labels = [content_visibility_selector_label(selector) for selector in visible]
    return "、".join(labels) + suffix


def content_visibility_scan_issue_messages(scan) -> list[str]:
    messages: list[str] = []
    missing_rule_selectors = list(getattr(scan, "missing_rule_selectors", []) or [])
    unused_document_selectors = list(getattr(scan, "unused_document_selectors", []) or [])
    orphan_end_selectors = dict(getattr(scan, "orphan_end_selectors", {}) or {})
    mismatched_end_selectors = dict(getattr(scan, "mismatched_end_selectors", {}) or {})
    nested_selectors = dict(getattr(scan, "nested_selectors", {}) or {})
    unclosed_selectors = dict(getattr(scan, "unclosed_selectors", {}) or {})

    if missing_rule_selectors:
        messages.append(
            "规则内容块未在文档中找到: "
            + format_content_visibility_selector_list(
                missing_rule_selectors,
                include_raw_for_known=True,
            )
        )
    if unused_document_selectors:
        messages.append(
            "文档标记未被任何交付使用: "
            + format_content_visibility_selector_list(
                unused_document_selectors,
                include_raw_for_known=True,
            )
        )
    if orphan_end_selectors:
        messages.append("存在孤立结束标记: " + _format_selector_counts(orphan_end_selectors))
    if mismatched_end_selectors:
        messages.append("存在错位结束标记: " + _format_selector_counts(mismatched_end_selectors))
    if nested_selectors:
        messages.append("存在嵌套内容块: " + _format_selector_counts(nested_selectors))
    if unclosed_selectors:
        messages.append("存在未闭合内容块: " + _format_selector_counts(unclosed_selectors))
    return messages


def _format_selector_counts(counts: dict[str, int]) -> str:
    return "、".join(
        f"{content_visibility_selector_display(selector)}({count})"
        for selector, count in sorted(counts.items())
    )


__all__ = [
    "COMMON_CONTENT_VISIBILITY_SELECTOR_OPTIONS",
    "ContentVisibilitySelectorOption",
    "content_visibility_scan_issue_messages",
    "content_visibility_selector_display",
    "content_visibility_selector_label",
    "content_visibility_selector_tooltip",
    "format_content_visibility_selector_list",
]
