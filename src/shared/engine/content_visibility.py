"""Shared helpers for DeliveryPreset marker-block visibility rules."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable

from docx.oxml.ns import qn

from src.shared.engine.content_visibility_contract import CONTENT_VISIBILITY_MARKER_RE

_W_P = qn("w:p")
_W_T = qn("w:t")

_ALLOWED_VISIBILITY_SELECTOR_TYPES = frozenset({"marker_block"})
_ALLOWED_VISIBILITY_ACTIONS = frozenset({"remove"})
_HIGH_RISK_VISIBILITY_SELECTORS = frozenset(
    {
        "answer",
        "analysis",
        "solution",
        "question_body",
        "teacher_note",
        "knowledge_points",
        "internal",
        "internal_note",
        "review_note",
    }
)
_SELECTOR_TYPO_SIMILARITY_THRESHOLD = 0.8


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
    # Strict direct-body grammar evidence.  These fields are additive so old
    # report/UI consumers can keep using the selector/count projection above.
    grammar_valid: bool = True
    strict_plan_id: str = ""
    blocking_diagnostics: list[dict[str, object]] = field(default_factory=list)

    @property
    def has_blocking_issues(self) -> bool:
        return bool(self.blocking_diagnostics)

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
                self.blocking_diagnostics,
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
        represented_codes = {
            "orphan_end_marker",
            "mismatched_end_marker",
            "nested_marker_block",
            "unclosed_start_marker",
        }
        unrepresented = [
            item
            for item in self.blocking_diagnostics
            if str(item.get("code", "") or "") not in represented_codes
        ]
        if unrepresented:
            messages.append(
                "内容可见性块语法不受支持: "
                + "; ".join(
                    f"[{item.get('code', 'invalid')}] {item.get('message', '')}"
                    for item in unrepresented
                )
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
    start_body_index: int = -1
    end_body_index: int = -1
    body_element_count: int = 0
    table_count: int = 0
    content_image_markers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ContentVisibilityPresetPreview:
    preset_id: str = ""
    label: str = ""
    remove_selectors: list[str] = field(default_factory=list)
    matched_selectors: list[str] = field(default_factory=list)
    missing_selectors: list[str] = field(default_factory=list)
    removed_block_count: int = 0
    removed_paragraph_count: int = 0
    removed_body_element_count: int = 0
    removed_table_count: int = 0
    stripped_marker_paragraph_count: int = 0
    removed_text_samples: list[str] = field(default_factory=list)
    removed_blocks: list[ContentVisibilityBlockPreview] = field(default_factory=list)
    strict_plan_id: str = ""


def scan_content_visibility_markers(
    document,
    presets: Iterable[object] | None = None,
) -> ContentVisibilityScanResult:
    """Inventory markers and validate the one production block grammar.

    Counting markers is intentionally separate from parsing their ranges.  The
    latter is delegated to :func:`build_block_visibility_plan`, which is also
    the authority used by delivery mutation.  Invalid grammar is projected to
    the legacy issue counters and retained as structured blocking diagnostics.
    """

    start_counts: Counter[str] = Counter()
    end_counts: Counter[str] = Counter()
    marker_paragraph_count = 0

    for paragraph_index, paragraph in enumerate(_iter_document_paragraphs(document)):
        markers = visibility_markers(getattr(paragraph, "text", ""), paragraph_index)
        if markers:
            marker_paragraph_count += 1
        for marker in markers:
            selector = marker.selector
            if marker.marker_type == "#":
                start_counts[selector] += 1
            else:
                end_counts[selector] += 1

    normalized_presets = list(presets or ())
    document_selectors = sorted(set(start_counts) | set(end_counts))
    used_rule_selectors = sorted(
        extract_content_visibility_rule_selectors(normalized_presets)
    )
    missing_rule_selectors = [
        selector for selector in used_rule_selectors if selector not in start_counts
    ]
    unused_document_selectors = [
        selector for selector in document_selectors if selector not in used_rule_selectors
    ]
    strict_plan_id = ""
    configuration_diagnostics = content_visibility_configuration_diagnostics(
        normalized_presets
    )
    grammar_diagnostics: list[dict[str, object]] = []
    try:
        strict_plan = _build_strict_visibility_plan(
            document,
            remove_selectors=document_selectors,
        )
        strict_plan_id = str(getattr(strict_plan, "plan_id", "") or "")
    except Exception as exc:
        diagnostics = getattr(exc, "diagnostics", None)
        if diagnostics is None:
            raise
        grammar_diagnostics = [item.to_dict() for item in diagnostics]

    blocking_diagnostics = [
        *configuration_diagnostics,
        *grammar_diagnostics,
        *_sensitive_selector_mismatch_diagnostics(
            normalized_presets,
            document_selectors=document_selectors,
        ),
    ]

    orphan_end_selectors = _diagnostic_selector_counts(
        grammar_diagnostics,
        "orphan_end_marker",
    )
    mismatched_end_selectors = _diagnostic_selector_counts(
        grammar_diagnostics,
        "mismatched_end_marker",
    )
    nested_selectors = _diagnostic_selector_counts(
        grammar_diagnostics,
        "nested_marker_block",
    )
    unclosed_selectors = _diagnostic_selector_counts(
        grammar_diagnostics,
        "unclosed_start_marker",
    )
    return ContentVisibilityScanResult(
        selectors=document_selectors,
        start_counts=dict(sorted(start_counts.items())),
        end_counts=dict(sorted(end_counts.items())),
        marker_paragraph_count=marker_paragraph_count,
        used_rule_selectors=used_rule_selectors,
        missing_rule_selectors=missing_rule_selectors,
        unused_document_selectors=unused_document_selectors,
        orphan_end_selectors=dict(sorted(orphan_end_selectors.items())),
        mismatched_end_selectors=dict(sorted(mismatched_end_selectors.items())),
        nested_selectors=dict(sorted(nested_selectors.items())),
        unclosed_selectors=dict(sorted(unclosed_selectors.items())),
        grammar_valid=not grammar_diagnostics,
        strict_plan_id=strict_plan_id,
        blocking_diagnostics=blocking_diagnostics,
    )


def preview_content_visibility_effects(
    document,
    presets: Iterable[object],
    *,
    sample_limit: int = 5,
) -> list[ContentVisibilityPresetPreview]:
    return [
        _preview_preset_visibility_effects(
            document,
            preset,
            sample_limit=sample_limit,
        )
        for preset in list(presets or [])
        if str(_visibility_rule_value(preset, "preset_id", "") or "").strip()
    ]


def _preview_preset_visibility_effects(
    document,
    preset,
    *,
    sample_limit: int,
) -> ContentVisibilityPresetPreview:
    remove_selectors = sorted(_preset_content_visibility_rule_selectors(preset))
    plan = _build_strict_visibility_plan(
        document,
        remove_selectors=remove_selectors,
    )
    body = document.element.body
    children = tuple(body)
    removed_samples: list[str] = []
    removed_blocks: list[ContentVisibilityBlockPreview] = []
    for visibility_range in plan.remove_ranges:
        block_samples: list[str] = []
        for element in children[
            visibility_range.start_body_index : visibility_range.end_body_index + 1
        ]:
            for text in _body_element_paragraph_texts(element):
                _append_visibility_sample(
                    block_samples,
                    text,
                    sample_limit=sample_limit,
                )
                _append_visibility_sample(
                    removed_samples,
                    text,
                    sample_limit=sample_limit,
                )
        removed_blocks.append(
            ContentVisibilityBlockPreview(
                selector=visibility_range.selector,
                start_paragraph_index=_direct_body_paragraph_ordinal(
                    children,
                    visibility_range.start_body_index,
                ),
                end_paragraph_index=_direct_body_paragraph_ordinal(
                    children,
                    visibility_range.end_body_index,
                ),
                paragraph_count=visibility_range.paragraph_count,
                text_samples=block_samples,
                context_before=_nearest_body_context(
                    children,
                    visibility_range.start_body_index,
                    step=-1,
                ),
                context_after=_nearest_body_context(
                    children,
                    visibility_range.end_body_index,
                    step=1,
                ),
                start_body_index=visibility_range.start_body_index,
                end_body_index=visibility_range.end_body_index,
                body_element_count=visibility_range.body_element_count,
                table_count=visibility_range.table_count,
                content_image_markers=list(visibility_range.content_image_markers),
            )
        )

    preset_id = str(_visibility_rule_value(preset, "preset_id", "") or "").strip()
    return ContentVisibilityPresetPreview(
        preset_id=preset_id,
        label=str(_visibility_rule_value(preset, "label", "") or preset_id).strip(),
        remove_selectors=remove_selectors,
        matched_selectors=list(plan.matched_remove_selectors),
        missing_selectors=list(plan.unmatched_remove_selectors),
        removed_block_count=len(removed_blocks),
        removed_paragraph_count=sum(
            item.paragraph_count for item in plan.remove_ranges
        ),
        removed_body_element_count=sum(
            item.body_element_count for item in plan.remove_ranges
        ),
        removed_table_count=sum(item.table_count for item in plan.remove_ranges),
        stripped_marker_paragraph_count=len(plan.retained_marker_paragraphs),
        removed_text_samples=removed_samples,
        removed_blocks=removed_blocks,
        strict_plan_id=plan.plan_id,
    )


def extract_content_visibility_rule_selectors(
    presets: Iterable[object],
) -> set[str]:
    selectors: set[str] = set()
    for preset in list(presets or []):
        if isinstance(preset, Mapping):
            rules = preset.get("content_visibility_rules", [])
        else:
            rules = getattr(preset, "content_visibility_rules", [])
        for rule in list(rules or []):
            selector = executable_content_visibility_rule_selector(rule)
            if selector:
                selectors.add(selector)
    return selectors


def executable_content_visibility_rule_selector(rule: object) -> str:
    """Return the selector only when a rule belongs to the production contract."""

    selector_type = str(
        _visibility_rule_value(rule, "selector_type", "marker_block") or ""
    ).strip().lower()
    action = str(
        _visibility_rule_value(rule, "action", "remove") or ""
    ).strip().lower()
    if (
        selector_type not in _ALLOWED_VISIBILITY_SELECTOR_TYPES
        or action not in _ALLOWED_VISIBILITY_ACTIONS
    ):
        return ""
    return normalize_content_visibility_selector(
        _visibility_rule_value(rule, "selector", "")
    )


def content_visibility_configuration_diagnostics(
    presets: Iterable[object],
) -> list[dict[str, object]]:
    """Return fail-closed diagnostics for malformed executable rules."""

    diagnostics: list[dict[str, object]] = []
    for preset_index, preset in enumerate(list(presets or [])):
        preset_id = str(
            _visibility_rule_value(preset, "preset_id", "") or ""
        ).strip()
        rules = _preset_content_visibility_rules(preset)
        for rule_index, rule in enumerate(rules):
            selector_type = str(
                _visibility_rule_value(rule, "selector_type", "marker_block")
                or ""
            ).strip().lower()
            action = str(
                _visibility_rule_value(rule, "action", "remove") or ""
            ).strip().lower()
            selector = normalize_content_visibility_selector(
                _visibility_rule_value(rule, "selector", "")
            )
            rule_id = str(
                _visibility_rule_value(rule, "rule_id", "") or ""
            ).strip()
            location = (
                f"delivery_presets[{preset_index}]."
                f"content_visibility_rules[{rule_index}]"
            )
            identity = rule_id or selector or f"rule-{rule_index + 1}"
            if selector_type not in _ALLOWED_VISIBILITY_SELECTOR_TYPES:
                diagnostics.append(
                    {
                        "code": "content_visibility_selector_type_invalid",
                        "message": (
                            f"Visibility rule '{identity}' in preset "
                            f"'{preset_id or preset_index}' has unsupported "
                            f"selector_type '{selector_type or '<empty>'}'."
                        ),
                        "selector": selector,
                        "preset_id": preset_id,
                        "rule_id": rule_id,
                        "location": f"{location}.selector_type",
                    }
                )
            if action not in _ALLOWED_VISIBILITY_ACTIONS:
                diagnostics.append(
                    {
                        "code": "content_visibility_action_invalid",
                        "message": (
                            f"Visibility rule '{identity}' in preset "
                            f"'{preset_id or preset_index}' has unsupported "
                            f"action '{action or '<empty>'}'."
                        ),
                        "selector": selector,
                        "preset_id": preset_id,
                        "rule_id": rule_id,
                        "location": f"{location}.action",
                    }
                )
            if not selector:
                diagnostics.append(
                    {
                        "code": "content_visibility_selector_missing",
                        "message": (
                            f"Visibility rule '{identity}' in preset "
                            f"'{preset_id or preset_index}' has no selector."
                        ),
                        "selector": "",
                        "preset_id": preset_id,
                        "rule_id": rule_id,
                        "location": f"{location}.selector",
                    }
                )
    return diagnostics


def _sensitive_selector_mismatch_diagnostics(
    presets: Iterable[object],
    *,
    document_selectors: Iterable[str],
) -> list[dict[str, object]]:
    """Detect likely typos only when a preset leaves a risky near-match uncontrolled."""

    document_selector_set = {
        normalize_content_visibility_selector(selector)
        for selector in document_selectors
        if normalize_content_visibility_selector(selector)
    }
    risky_document_selectors = sorted(
        document_selector_set & _HIGH_RISK_VISIBILITY_SELECTORS
    )
    if not risky_document_selectors:
        return []

    diagnostics: list[dict[str, object]] = []
    for preset_index, preset in enumerate(list(presets or [])):
        preset_id = str(
            _visibility_rule_value(preset, "preset_id", "") or ""
        ).strip()
        configured_selectors = _preset_content_visibility_rule_selectors(preset)
        for configured_selector in sorted(configured_selectors - document_selector_set):
            for document_selector in risky_document_selectors:
                if document_selector in configured_selectors:
                    continue
                similarity = _selector_similarity(
                    configured_selector,
                    document_selector,
                )
                if similarity < _SELECTOR_TYPO_SIMILARITY_THRESHOLD:
                    continue
                diagnostics.append(
                    {
                        "code": "content_visibility_sensitive_selector_mismatch",
                        "message": (
                            f"Preset '{preset_id or preset_index}' configures "
                            f"selector '{configured_selector}', but the document "
                            f"contains high-risk selector '{document_selector}'. "
                            "The near-match is treated as a probable typo because "
                            "continuing would retain the protected block while "
                            "stripping its markers."
                        ),
                        "selector": configured_selector,
                        "observed_selector": document_selector,
                        "preset_id": preset_id,
                        "similarity": round(similarity, 3),
                        "location": (
                            f"delivery_presets[{preset_index}]."
                            "content_visibility_rules"
                        ),
                    }
                )
                break
    return diagnostics


def _preset_content_visibility_rules(preset) -> list[object]:
    if isinstance(preset, dict):
        rules = preset.get("content_visibility_rules", [])
    else:
        rules = getattr(preset, "content_visibility_rules", [])
    return list(rules or [])


def _selector_similarity(left: str, right: str) -> float:
    normalized_left = normalize_content_visibility_selector(left)
    normalized_right = normalize_content_visibility_selector(right)
    if not normalized_left or not normalized_right or normalized_left == normalized_right:
        return 0.0
    if min(len(normalized_left), len(normalized_right)) < 4:
        return 0.0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


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


def _build_strict_visibility_plan(document, *, remove_selectors: Iterable[str]):
    # Lazy import avoids a module cycle: block_visibility owns the grammar but
    # imports the shared marker regex defined by this module.
    from src.shared.engine.block_visibility import build_block_visibility_plan

    return build_block_visibility_plan(
        document,
        remove_selectors=remove_selectors,
    )


def _diagnostic_selector_counts(
    diagnostics: list[dict[str, object]],
    code: str,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in diagnostics:
        if str(item.get("code", "") or "") != code:
            continue
        selectors = str(item.get("selector", "") or "").split(",")
        for selector in selectors:
            normalized = normalize_content_visibility_selector(selector)
            if normalized:
                counts[normalized] += 1
    return counts


def _body_element_paragraph_texts(element) -> list[str]:
    return [
        "".join(str(node.text or "") for node in paragraph.iter(_W_T))
        for paragraph in element.iter(_W_P)
    ]


def _direct_body_paragraph_ordinal(children, body_index: int) -> int:
    if body_index < 0:
        return -1
    return sum(1 for element in children[:body_index] if element.tag == _W_P)


def _nearest_body_context(children, body_index: int, *, step: int) -> str:
    index = body_index + step
    while 0 <= index < len(children):
        for text in _body_element_paragraph_texts(children[index]):
            cleaned = _clean_visibility_text(text)
            if cleaned:
                return cleaned
        index += step
    return ""


def _clean_visibility_text(text: str) -> str:
    return CONTENT_VISIBILITY_MARKER_RE.sub("", str(text or "")).strip()


def _visibility_rule_value(rule, key: str, default=""):
    if isinstance(rule, Mapping):
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
