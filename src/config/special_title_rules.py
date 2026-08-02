"""Literal special-title rules shared by editing and document execution.

The user owns every rule.  Rules are never translated into semantic roles,
merged into groups, or expanded with aliases.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

SpecialTitleRuleKind = Literal["exact", "prefix"]

EXACT_RULE_KIND: SpecialTitleRuleKind = "exact"
PREFIX_RULE_KIND: SpecialTitleRuleKind = "prefix"
SPECIAL_TITLE_SELECTOR_PREFIX = "special-title"

_EXISTING_NUMBER_RE = re.compile(
    r"^\s*(?:第[一二三四五六七八九十百千万\d]+[章节篇部]\s*|"
    r"\d+(?:[.\-]\d+)*[.)、]?\s*|"
    r"[A-Za-z][.)、．]\s*|"
    r"[（(][A-Za-z][）)]\s*|"
    r"[一二三四五六七八九十]+[、.．]\s*|"
    r"[（(]?[一二三四五六七八九十]+[）)]\s*)"
)


@dataclass(frozen=True, slots=True)
class SpecialTitleMatch:
    """One literal rule match against a paragraph title."""

    kind: SpecialTitleRuleKind
    value: str
    selector: str
    clean_text: str


@dataclass(frozen=True, slots=True)
class SpecialTitleReferenceSnapshot:
    """Scope references mutated as a consequence of editing title rules."""

    header_hidden: tuple[str, ...]
    footer_hidden: tuple[str, ...]
    phase_selectors: tuple[tuple[str, ...], ...]


def normalize_special_title_values(values: Iterable[object] | None) -> list[str]:
    """Strip item-boundary whitespace without changing or merging rules."""

    return [
        value
        for raw_value in values or ()
        if (value := str(raw_value or "").strip())
    ]


def validate_special_title_values(
    exact_values: Iterable[object] | None,
    prefix_values: Iterable[object] | None,
) -> tuple[list[str], list[str]]:
    """Return normalized lists, rejecting the same literal in both categories."""

    exact = normalize_special_title_values(exact_values)
    prefixes = normalize_special_title_values(prefix_values)
    duplicate_exact = _first_duplicate(exact)
    if duplicate_exact is not None:
        raise ValueError(f"完整标题中存在重复规则“{duplicate_exact}”")
    duplicate_prefix = _first_duplicate(prefixes)
    if duplicate_prefix is not None:
        raise ValueError(f"标题前缀中存在重复规则“{duplicate_prefix}”")
    conflict = next((value for value in exact if value in prefixes), None)
    if conflict is not None:
        raise ValueError(f"“{conflict}”不能同时作为完整标题和标题前缀")
    return exact, prefixes


def _first_duplicate(values: Iterable[str]) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None


def special_title_selector(kind: SpecialTitleRuleKind, value: object) -> str:
    """Encode one literal rule as a stable, lower-case-safe scope selector."""

    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind not in {EXACT_RULE_KIND, PREFIX_RULE_KIND}:
        raise ValueError(f"unsupported special-title rule kind: {kind}")
    normalized_value = str(value or "").strip()
    if not normalized_value:
        raise ValueError("special-title rule cannot be empty")
    payload = normalized_value.encode("utf-8").hex()
    return f"{SPECIAL_TITLE_SELECTOR_PREFIX}:{normalized_kind}:{payload}"


def parse_special_title_selector(
    selector: object,
) -> tuple[SpecialTitleRuleKind, str] | None:
    """Decode a selector without inventing or normalizing its literal value."""

    raw = str(selector or "").strip()
    parts = raw.split(":", 2)
    if len(parts) != 3 or parts[0].lower() != SPECIAL_TITLE_SELECTOR_PREFIX:
        return None
    kind = parts[1].lower()
    if kind not in {EXACT_RULE_KIND, PREFIX_RULE_KIND}:
        return None
    try:
        value = bytes.fromhex(parts[2]).decode("utf-8").strip()
    except (ValueError, UnicodeDecodeError):
        return None
    if not value:
        return None
    return kind, value  # type: ignore[return-value]


def special_title_selector_label(selector: object) -> str:
    parsed = parse_special_title_selector(selector)
    if parsed is None:
        return str(selector or "").strip()
    _kind, value = parsed
    return value


def special_title_selector_options(heading_model) -> tuple[tuple[str, str], ...]:
    """Build one visible option for every configured literal rule."""

    if heading_model is None:
        return ()
    exact, prefixes = validate_special_title_values(
        getattr(heading_model, "non_numbered_title_texts", None),
        getattr(heading_model, "non_numbered_prefixes", None),
    )
    options = [
        (special_title_selector(EXACT_RULE_KIND, value), value)
        for value in exact
    ]
    options.extend(
        (
            special_title_selector(PREFIX_RULE_KIND, value),
            value,
        )
        for value in prefixes
    )
    return tuple(options)


def strip_existing_heading_number(text: object) -> str:
    """Remove only a recognized leading heading number and outer whitespace."""

    normalized = str(text or "").strip()
    match = _EXISTING_NUMBER_RE.match(normalized)
    return normalized[match.end():].strip() if match else normalized


def match_special_title(
    text: object,
    *,
    exact_values: Iterable[object] | None,
    prefix_values: Iterable[object] | None,
) -> SpecialTitleMatch | None:
    """Match exact rules first, then the longest matching prefix."""

    clean_text = strip_existing_heading_number(text)
    if not clean_text:
        return None
    exact, prefixes = validate_special_title_values(exact_values, prefix_values)
    if clean_text in exact:
        return SpecialTitleMatch(
            kind=EXACT_RULE_KIND,
            value=clean_text,
            selector=special_title_selector(EXACT_RULE_KIND, clean_text),
            clean_text=clean_text,
        )

    ordered_prefixes = sorted(
        enumerate(prefixes),
        key=lambda item: (-len(item[1]), item[0]),
    )
    for _index, prefix in ordered_prefixes:
        if clean_text.startswith(prefix):
            return SpecialTitleMatch(
                kind=PREFIX_RULE_KIND,
                value=prefix,
                selector=special_title_selector(PREFIX_RULE_KIND, prefix),
                clean_text=clean_text,
            )
    return None


def match_special_title_model(text: object, heading_model) -> SpecialTitleMatch | None:
    if heading_model is None:
        return None
    return match_special_title(
        text,
        exact_values=getattr(heading_model, "non_numbered_title_texts", None),
        prefix_values=getattr(heading_model, "non_numbered_prefixes", None),
    )


def capture_special_title_reference_snapshot(template) -> SpecialTitleReferenceSnapshot:
    header_footer = template.header_footer
    phases = list(getattr(header_footer.page_number_plan, "phases", None) or [])
    return SpecialTitleReferenceSnapshot(
        header_hidden=tuple(getattr(header_footer.header, "hidden_selectors", None) or ()),
        footer_hidden=tuple(getattr(header_footer.footer, "hidden_selectors", None) or ()),
        phase_selectors=tuple(
            tuple(getattr(phase, "selectors", None) or ())
            for phase in phases
        ),
    )


def restore_special_title_reference_snapshot(
    template,
    snapshot: SpecialTitleReferenceSnapshot,
) -> None:
    header_footer = template.header_footer
    header_footer.header.hidden_selectors = list(snapshot.header_hidden)
    header_footer.footer.hidden_selectors = list(snapshot.footer_hidden)
    phases = list(getattr(header_footer.page_number_plan, "phases", None) or [])
    for phase, selectors in zip(phases, snapshot.phase_selectors):
        phase.selectors = list(selectors)


def reconcile_special_title_references(
    template,
    *,
    kind: SpecialTitleRuleKind,
    old_values: Iterable[object] | None,
    new_values: Iterable[object] | None,
) -> None:
    """Keep literal-rule scope references aligned after add/edit/delete.

    A same-length replacement is treated as an edit and preserves selection.
    Additions are never selected automatically.  Removed rules are deleted
    from every header, footer-text, and page-number selector list.
    """

    old = normalize_special_title_values(old_values)
    new = normalize_special_title_values(new_values)
    unchanged = set(old) & set(new)
    removed_values = [value for value in old if value not in unchanged]
    added_values = [value for value in new if value not in unchanged]

    replacements: dict[str, str] = {}
    if len(old) == len(new) and len(removed_values) == len(added_values):
        replacements = {
            special_title_selector(kind, old_value): special_title_selector(kind, new_value)
            for old_value, new_value in zip(removed_values, added_values)
        }
        removed_selectors: set[str] = set()
    else:
        removed_selectors = {
            special_title_selector(kind, value)
            for value in removed_values
        }

    header_footer = template.header_footer
    header_footer.header.hidden_selectors = _rewrite_selector_list(
        getattr(header_footer.header, "hidden_selectors", None),
        replacements,
        removed_selectors,
    )
    header_footer.footer.hidden_selectors = _rewrite_selector_list(
        getattr(header_footer.footer, "hidden_selectors", None),
        replacements,
        removed_selectors,
    )
    for phase in list(getattr(header_footer.page_number_plan, "phases", None) or []):
        phase.selectors = _rewrite_selector_list(
            getattr(phase, "selectors", None),
            replacements,
            removed_selectors,
        )


def _rewrite_selector_list(
    selectors: Iterable[object] | None,
    replacements: dict[str, str],
    removed_selectors: set[str],
) -> list[str]:
    result: list[str] = []
    for raw_selector in selectors or ():
        selector = str(raw_selector or "").strip()
        if not selector or selector in removed_selectors:
            continue
        selector = replacements.get(selector, selector)
        if selector not in result:
            result.append(selector)
    return result


__all__ = [
    "EXACT_RULE_KIND",
    "PREFIX_RULE_KIND",
    "SPECIAL_TITLE_SELECTOR_PREFIX",
    "SpecialTitleMatch",
    "SpecialTitleReferenceSnapshot",
    "capture_special_title_reference_snapshot",
    "match_special_title",
    "match_special_title_model",
    "normalize_special_title_values",
    "parse_special_title_selector",
    "reconcile_special_title_references",
    "restore_special_title_reference_snapshot",
    "special_title_selector",
    "special_title_selector_label",
    "special_title_selector_options",
    "strip_existing_heading_number",
    "validate_special_title_values",
]
