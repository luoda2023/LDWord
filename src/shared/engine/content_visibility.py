"""Shared helpers for DeliveryPreset marker-block visibility rules."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable


CONTENT_VISIBILITY_MARKER_RE = re.compile(
    r"\{\{\s*([#/])\s*(?:visibility|content)\s*:\s*([A-Za-z0-9_.-]+)\s*\}\}"
)


@dataclass(frozen=True)
class ContentVisibilityMarker:
    marker_type: str
    selector: str
    paragraph_index: int


@dataclass(slots=True)
class ContentVisibilityScanResult:
    selectors: list[str] = field(default_factory=list)
    start_counts: dict[str, int] = field(default_factory=dict)
    end_counts: dict[str, int] = field(default_factory=dict)
    marker_paragraph_count: int = 0
    used_rule_selectors: list[str] = field(default_factory=list)
    missing_rule_selectors: list[str] = field(default_factory=list)
    unused_document_selectors: list[str] = field(default_factory=list)
    orphan_end_selectors: dict[str, int] = field(default_factory=dict)
    mismatched_end_selectors: dict[str, int] = field(default_factory=dict)
    nested_selectors: dict[str, int] = field(default_factory=dict)
    unclosed_selectors: dict[str, int] = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return any(
            (
                self.missing_rule_selectors,
                self.orphan_end_selectors,
                self.mismatched_end_selectors,
                self.nested_selectors,
                self.unclosed_selectors,
                self.unused_document_selectors,
            )
        )

    def issue_messages(self) -> list[str]:
        messages: list[str] = []
        if self.missing_rule_selectors:
            messages.append(
                "规则 selector 未在文档中找到: "
                + ", ".join(self.missing_rule_selectors)
            )
        if self.unused_document_selectors:
            messages.append(
                "文档 marker 未被任何 preset 使用: "
                + ", ".join(self.unused_document_selectors)
            )
        if self.orphan_end_selectors:
            messages.append(
                "存在孤立结束 marker: " + _format_counts(self.orphan_end_selectors)
            )
        if self.mismatched_end_selectors:
            messages.append(
                "存在错位结束 marker: " + _format_counts(self.mismatched_end_selectors)
            )
        if self.nested_selectors:
            messages.append(
                "存在嵌套 marker block: " + _format_counts(self.nested_selectors)
            )
        if self.unclosed_selectors:
            messages.append(
                "存在未闭合 marker block: " + _format_counts(self.unclosed_selectors)
            )
        return messages


@dataclass(slots=True)
class ContentVisibilityBlockPreview:
    selector: str = ""
    start_paragraph_index: int = -1
    end_paragraph_index: int = -1
    paragraph_count: int = 0
    text_samples: list[str] = field(default_factory=list)
    context_before: str = ""
    context_after: str = ""


@dataclass(slots=True)
class ContentVisibilityPresetPreview:
    preset_id: str = ""
    label: str = ""
    remove_selectors: list[str] = field(default_factory=list)
    matched_selectors: list[str] = field(default_factory=list)
    missing_selectors: list[str] = field(default_factory=list)
    removed_block_count: int = 0
    removed_paragraph_count: int = 0
    stripped_marker_paragraph_count: int = 0
    removed_text_samples: list[str] = field(default_factory=list)
    removed_blocks: list[ContentVisibilityBlockPreview] = field(default_factory=list)


def scan_content_visibility_markers(
    document,
    presets: Iterable[object] | None = None,
) -> ContentVisibilityScanResult:
    start_counts: Counter[str] = Counter()
    end_counts: Counter[str] = Counter()
    orphan_end_selectors: Counter[str] = Counter()
    mismatched_end_selectors: Counter[str] = Counter()
    nested_selectors: Counter[str] = Counter()
    active_stack: list[str] = []
    marker_paragraph_count = 0

    for paragraph_index, paragraph in enumerate(_iter_document_paragraphs(document)):
        markers = visibility_markers(getattr(paragraph, "text", ""), paragraph_index)
        if markers:
            marker_paragraph_count += 1
        for marker in markers:
            selector = marker.selector
            if marker.marker_type == "#":
                start_counts[selector] += 1
                if active_stack:
                    nested_selectors[selector] += 1
                active_stack.append(selector)
                continue

            end_counts[selector] += 1
            if active_stack and active_stack[-1] == selector:
                active_stack.pop()
            elif selector in active_stack:
                mismatched_end_selectors[selector] += 1
                reverse_index = active_stack[::-1].index(selector)
                del active_stack[len(active_stack) - reverse_index - 1 :]
            else:
                orphan_end_selectors[selector] += 1

    unclosed_selectors = Counter(active_stack)
    document_selectors = sorted(set(start_counts) | set(end_counts))
    used_rule_selectors = sorted(extract_content_visibility_rule_selectors(presets or ()))
    return ContentVisibilityScanResult(
        selectors=document_selectors,
        start_counts=dict(sorted(start_counts.items())),
        end_counts=dict(sorted(end_counts.items())),
        marker_paragraph_count=marker_paragraph_count,
        used_rule_selectors=used_rule_selectors,
        missing_rule_selectors=[
            selector for selector in used_rule_selectors if selector not in start_counts
        ],
        unused_document_selectors=[
            selector for selector in document_selectors if selector not in used_rule_selectors
        ],
        orphan_end_selectors=dict(sorted(orphan_end_selectors.items())),
        mismatched_end_selectors=dict(sorted(mismatched_end_selectors.items())),
        nested_selectors=dict(sorted(nested_selectors.items())),
        unclosed_selectors=dict(sorted(unclosed_selectors.items())),
    )


def preview_content_visibility_effects(
    document,
    presets: Iterable[object],
    *,
    sample_limit: int = 5,
) -> list[ContentVisibilityPresetPreview]:
    paragraphs = [
        str(getattr(paragraph, "text", "") or "")
        for paragraph in _iter_document_paragraphs(document)
    ]
    document_start_selectors = {
        marker.selector
        for text in paragraphs
        for marker in visibility_markers(text)
        if marker.marker_type == "#"
    }
    return [
        _preview_preset_visibility_effects(
            preset,
            paragraphs,
            document_start_selectors=document_start_selectors,
            sample_limit=sample_limit,
        )
        for preset in list(presets or [])
        if str(_visibility_rule_value(preset, "preset_id", "") or "").strip()
    ]


def _preview_preset_visibility_effects(
    preset,
    paragraphs: list[str],
    *,
    document_start_selectors: set[str],
    sample_limit: int,
) -> ContentVisibilityPresetPreview:
    remove_selectors = sorted(_preset_content_visibility_rule_selectors(preset))
    matched_selectors: set[str] = set()
    removed_paragraph_count = 0
    stripped_marker_paragraph_count = 0
    removed_samples: list[str] = []
    removed_blocks: list[ContentVisibilityBlockPreview] = []
    active_remove_selector = ""
    active_start_index = -1
    active_paragraph_count = 0
    active_samples: list[str] = []

    for paragraph_index, text in enumerate(paragraphs):
        markers = visibility_markers(text)

        if active_remove_selector:
            removed_paragraph_count += 1
            active_paragraph_count += 1
            _append_visibility_sample(
                removed_samples,
                text,
                sample_limit=sample_limit,
            )
            _append_visibility_sample(
                active_samples,
                text,
                sample_limit=sample_limit,
            )
            if _has_visibility_end(markers, active_remove_selector):
                removed_blocks.append(
                    _build_visibility_block_preview(
                        selector=active_remove_selector,
                        start_index=active_start_index,
                        end_index=paragraph_index,
                        paragraph_count=active_paragraph_count,
                        text_samples=active_samples,
                        paragraphs=paragraphs,
                    )
                )
                active_remove_selector = ""
                active_start_index = -1
                active_paragraph_count = 0
                active_samples = []
            continue

        start_remove_selector = next(
            (
                marker.selector
                for marker in markers
                if marker.marker_type == "#" and marker.selector in remove_selectors
            ),
            "",
        )
        if start_remove_selector:
            matched_selectors.add(start_remove_selector)
            removed_paragraph_count += 1
            block_samples: list[str] = []
            _append_visibility_sample(
                removed_samples,
                text,
                sample_limit=sample_limit,
            )
            _append_visibility_sample(
                block_samples,
                text,
                sample_limit=sample_limit,
            )
            if _has_visibility_end(markers, start_remove_selector):
                removed_blocks.append(
                    _build_visibility_block_preview(
                        selector=start_remove_selector,
                        start_index=paragraph_index,
                        end_index=paragraph_index,
                        paragraph_count=1,
                        text_samples=block_samples,
                        paragraphs=paragraphs,
                    )
                )
            else:
                active_remove_selector = start_remove_selector
                active_start_index = paragraph_index
                active_paragraph_count = 1
                active_samples = block_samples
            continue

        if markers:
            stripped_marker_paragraph_count += 1

    if active_remove_selector:
        removed_blocks.append(
            _build_visibility_block_preview(
                selector=active_remove_selector,
                start_index=active_start_index,
                end_index=len(paragraphs) - 1,
                paragraph_count=active_paragraph_count,
                text_samples=active_samples,
                paragraphs=paragraphs,
            )
        )

    preset_id = str(_visibility_rule_value(preset, "preset_id", "") or "").strip()
    return ContentVisibilityPresetPreview(
        preset_id=preset_id,
        label=str(_visibility_rule_value(preset, "label", "") or preset_id).strip(),
        remove_selectors=remove_selectors,
        matched_selectors=sorted(matched_selectors),
        missing_selectors=[
            selector for selector in remove_selectors if selector not in document_start_selectors
        ],
        removed_block_count=len(removed_blocks),
        removed_paragraph_count=removed_paragraph_count,
        stripped_marker_paragraph_count=stripped_marker_paragraph_count,
        removed_text_samples=removed_samples,
        removed_blocks=removed_blocks,
    )


def extract_content_visibility_rule_selectors(
    presets: Iterable[object],
) -> set[str]:
    selectors: set[str] = set()
    for preset in list(presets or []):
        if isinstance(preset, dict):
            rules = preset.get("content_visibility_rules", [])
        else:
            rules = getattr(preset, "content_visibility_rules", [])
        for rule in list(rules or []):
            selector_type = str(
                _visibility_rule_value(rule, "selector_type", "marker_block")
            ).strip().lower()
            action = str(_visibility_rule_value(rule, "action", "remove")).strip().lower()
            selector = normalize_content_visibility_selector(
                _visibility_rule_value(rule, "selector", "")
            )
            if selector_type != "marker_block" or action not in {"remove", "hide", "exclude"}:
                continue
            if selector:
                selectors.add(selector)
    return selectors


def _preset_content_visibility_rule_selectors(preset) -> set[str]:
    return extract_content_visibility_rule_selectors([preset])


def visibility_markers(text: str, paragraph_index: int = -1) -> list[ContentVisibilityMarker]:
    return [
        ContentVisibilityMarker(
            marker_type=match.group(1),
            selector=normalize_content_visibility_selector(match.group(2)),
            paragraph_index=paragraph_index,
        )
        for match in CONTENT_VISIBILITY_MARKER_RE.finditer(text or "")
    ]


def normalize_content_visibility_selector(value) -> str:
    return str(value or "").strip().lower()


def _has_visibility_end(markers: list[ContentVisibilityMarker], selector: str) -> bool:
    return any(
        marker.marker_type == "/" and marker.selector == selector
        for marker in markers
    )


def _append_visibility_sample(
    samples: list[str],
    text: str,
    *,
    sample_limit: int,
) -> None:
    if len(samples) >= sample_limit:
        return
    cleaned = _clean_visibility_text(text)
    if cleaned:
        samples.append(cleaned)


def _build_visibility_block_preview(
    *,
    selector: str,
    start_index: int,
    end_index: int,
    paragraph_count: int,
    text_samples: list[str],
    paragraphs: list[str],
) -> ContentVisibilityBlockPreview:
    return ContentVisibilityBlockPreview(
        selector=selector,
        start_paragraph_index=start_index,
        end_paragraph_index=end_index,
        paragraph_count=paragraph_count,
        text_samples=list(text_samples),
        context_before=_nearest_visibility_context_before(paragraphs, start_index),
        context_after=_nearest_visibility_context_after(paragraphs, end_index),
    )


def _nearest_visibility_context_before(paragraphs: list[str], start_index: int) -> str:
    for index in range(max(0, start_index) - 1, -1, -1):
        cleaned = _clean_visibility_text(paragraphs[index])
        if cleaned:
            return cleaned
    return ""


def _nearest_visibility_context_after(paragraphs: list[str], end_index: int) -> str:
    for index in range(max(-1, end_index) + 1, len(paragraphs)):
        cleaned = _clean_visibility_text(paragraphs[index])
        if cleaned:
            return cleaned
    return ""


def _clean_visibility_text(text: str) -> str:
    return CONTENT_VISIBILITY_MARKER_RE.sub("", str(text or "")).strip()


def _visibility_rule_value(rule, key: str, default=""):
    if isinstance(rule, dict):
        return rule.get(key, default)
    return getattr(rule, key, default)


def _iter_document_paragraphs(container):
    for paragraph in list(getattr(container, "paragraphs", []) or []):
        yield paragraph
    for table in list(getattr(container, "tables", []) or []):
        for row in list(getattr(table, "rows", []) or []):
            for cell in list(getattr(row, "cells", []) or []):
                yield from _iter_document_paragraphs(cell)


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{selector}({count})" for selector, count in counts.items())
