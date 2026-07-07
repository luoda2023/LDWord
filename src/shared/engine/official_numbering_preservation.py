"""Runtime evidence for official-document numbering preservation."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from src.config.material_schema_registry import get_material_schema, resolve_material_schema_ids


OFFICIAL_RULE_FAMILIES = ("official_document", "meeting_policy_documents")
OFFICIAL_SCHEMA_IDS = ("official_document_v1",)
OFFICIAL_WORD_SURFACES = (
    "numbering.xml",
    "w:pPr/w:numPr",
    "w:fldSimple/w:instrText",
)


@dataclass(frozen=True, slots=True)
class OfficialNumberingIssue:
    """One numbering preservation issue surfaced in reports."""

    kind: str
    message: str
    severity: str = "warning"
    expected: str = ""
    observed: str = ""
    paragraph_index: int = -1


@dataclass(frozen=True, slots=True)
class OfficialNumberingChangeSample:
    """One heading-text difference relevant to preserve-numbering mode."""

    paragraph_index: int
    level: int
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class OfficialNumberingSummary:
    """Compact counts used by JSON/Markdown reports."""

    heading_count: int = 0
    changed_heading_count: int = 0
    heading_numbering_record_count: int = 0
    heading_numbering_changed_count: int = 0


@dataclass(frozen=True, slots=True)
class OfficialNumberingPreservationResult:
    """Structured evidence for official numbering preservation."""

    family_id: str = ""
    status: str = "not_applicable"
    strategy: str = ""
    rule_family: str = ""
    profile_id: str = ""
    material_schema_ids: tuple[str, ...] = ()
    word_surfaces: tuple[str, ...] = OFFICIAL_WORD_SURFACES
    heading_numbering_enabled: bool = False
    summary: OfficialNumberingSummary = field(default_factory=OfficialNumberingSummary)
    changed_headings: tuple[OfficialNumberingChangeSample, ...] = ()
    issues: tuple[OfficialNumberingIssue, ...] = ()

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity != "error")

    @property
    def manual_confirmation_required(self) -> bool:
        return bool(self.issues)

    def to_dict(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "status": self.status,
            "strategy": self.strategy,
            "rule_family": self.rule_family,
            "profile_id": self.profile_id,
            "material_schema_ids": list(self.material_schema_ids),
            "word_surfaces": list(self.word_surfaces),
            "heading_numbering_enabled": self.heading_numbering_enabled,
            "manual_confirmation_required": self.manual_confirmation_required,
            "summary": {
                "heading_count": self.summary.heading_count,
                "changed_heading_count": self.summary.changed_heading_count,
                "heading_numbering_record_count": self.summary.heading_numbering_record_count,
                "heading_numbering_changed_count": self.summary.heading_numbering_changed_count,
            },
            "changed_headings": [
                {
                    "paragraph_index": item.paragraph_index,
                    "level": item.level,
                    "before": item.before,
                    "after": item.after,
                }
                for item in self.changed_headings
            ],
            "issue_count": len(self.issues),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "kind": issue.kind,
                    "severity": issue.severity,
                    "expected": issue.expected,
                    "observed": issue.observed,
                    "paragraph_index": issue.paragraph_index,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


def inspect_official_numbering_preservation(
    config,
    *,
    original_doc=None,
    current_doc=None,
    heading_map: Mapping[int, int] | None = None,
    tracker_records: Sequence[Any] | None = None,
) -> OfficialNumberingPreservationResult:
    """Build report evidence for official-document preserve-numbering strategy."""

    schema_ids = _config_material_schema_ids(config)
    rule_family = _clean_text(
        getattr(getattr(config, "compliance_profile", None), "rule_family", "")
    )
    profile_id = _clean_text(
        getattr(getattr(config, "compliance_profile", None), "profile_id", "")
    )
    family_id = _official_family_for_schema_ids(schema_ids)
    if not _is_official_config(config, schema_ids=schema_ids, rule_family=rule_family):
        return OfficialNumberingPreservationResult()

    strategy = "preserve" if not bool(getattr(config, "strict_mode", True)) else "rebuild"
    heading_numbering_enabled = bool(
        dict(getattr(config, "module_switches", {}) or {}).get("heading_numbering", False)
    )
    normalized_heading_map = _normalize_heading_map(heading_map)
    changed_headings = _changed_heading_samples(
        original_doc,
        current_doc,
        normalized_heading_map,
    )
    numbering_records = [
        record
        for record in list(tracker_records or [])
        if _clean_text(getattr(record, "rule_name", "")) == "heading_numbering"
    ]
    numbering_changed_count = sum(_record_target_count(record) for record in numbering_records)

    issues: list[OfficialNumberingIssue] = []
    if strategy != "preserve":
        issues.append(
            OfficialNumberingIssue(
                kind="official_numbering_strategy_not_preserve",
                expected="preserve",
                observed=strategy,
                message=(
                    "Official-policy scenes should declare preserve-numbering "
                    "strategy unless the user explicitly chooses rebuild."
                ),
            )
        )
    if strategy == "preserve" and numbering_records:
        issues.append(
            OfficialNumberingIssue(
                kind="heading_numbering_recorded_in_preserve_mode",
                expected="no heading_numbering rewrite records",
                observed=f"{len(numbering_records)} tracker record(s)",
                message=(
                    "The run declared preserve-numbering mode, but heading_numbering "
                    "recorded changes. Review numbering.xml and heading text before delivery."
                ),
            )
        )
    if strategy == "preserve" and changed_headings:
        issues.append(
            OfficialNumberingIssue(
                kind="heading_text_changed_in_preserve_mode",
                expected="heading text unchanged",
                observed=f"{len(changed_headings)} changed heading(s)",
                message=(
                    "Heading text changed while official numbering preservation was requested."
                ),
                paragraph_index=changed_headings[0].paragraph_index,
            )
        )

    if issues:
        status = "needs_review"
    elif strategy == "preserve":
        status = "preserved"
    else:
        status = "rebuild_declared"

    return OfficialNumberingPreservationResult(
        family_id=family_id or "official_document",
        status=status,
        strategy=strategy,
        rule_family=rule_family,
        profile_id=profile_id,
        material_schema_ids=tuple(schema_ids),
        heading_numbering_enabled=heading_numbering_enabled,
        summary=OfficialNumberingSummary(
            heading_count=len(normalized_heading_map),
            changed_heading_count=len(changed_headings),
            heading_numbering_record_count=len(numbering_records),
            heading_numbering_changed_count=numbering_changed_count,
        ),
        changed_headings=tuple(changed_headings[:10]),
        issues=tuple(issues),
    )


def _is_official_config(config, *, schema_ids: tuple[str, ...], rule_family: str) -> bool:
    scene_id = _clean_text(getattr(config, "scene_id", ""))
    category = _clean_text(getattr(config, "category", ""))
    if scene_id == "official" or category in {"government", "official"}:
        return True
    if rule_family in OFFICIAL_RULE_FAMILIES:
        return True
    return any(schema_id in OFFICIAL_SCHEMA_IDS for schema_id in schema_ids)


def _config_material_schema_ids(config) -> tuple[str, ...]:
    input_profile = getattr(config, "input_source_profile", None)
    return resolve_material_schema_ids(
        _clean_text(getattr(input_profile, "material_schema_id", "")),
        list(getattr(input_profile, "material_schema_ids", []) or []),
    )


def _official_family_for_schema_ids(schema_ids: tuple[str, ...]) -> str:
    for schema_id in schema_ids:
        try:
            family = get_material_schema(schema_id).family
        except KeyError:
            continue
        if family == "official":
            return "official_document"
    return ""


def _normalize_heading_map(heading_map: Mapping[int, int] | None) -> dict[int, int]:
    result: dict[int, int] = {}
    for key, value in dict(heading_map or {}).items():
        try:
            index = int(key)
            level = int(value)
        except (TypeError, ValueError):
            continue
        if index >= 0 and level > 0:
            result[index] = level
    return dict(sorted(result.items()))


def _changed_heading_samples(
    original_doc,
    current_doc,
    heading_map: Mapping[int, int],
) -> list[OfficialNumberingChangeSample]:
    if original_doc is None or current_doc is None or not heading_map:
        return []
    original_paragraphs = list(getattr(original_doc, "paragraphs", []) or [])
    current_paragraphs = list(getattr(current_doc, "paragraphs", []) or [])
    samples: list[OfficialNumberingChangeSample] = []
    for index, level in heading_map.items():
        if index >= len(original_paragraphs) or index >= len(current_paragraphs):
            continue
        before = _clean_text(getattr(original_paragraphs[index], "text", ""))
        after = _clean_text(getattr(current_paragraphs[index], "text", ""))
        if before != after:
            samples.append(
                OfficialNumberingChangeSample(
                    paragraph_index=index,
                    level=level,
                    before=before,
                    after=after,
                )
            )
    return samples


def _record_target_count(record) -> int:
    target = _clean_text(getattr(record, "target", ""))
    match = re.search(r"(\d+)", target)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


def _clean_text(value: object) -> str:
    return str(value or "").strip()
