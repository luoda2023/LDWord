"""Section-level word-limit evidence for project application reports."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from src.config.material_schema_registry import resolve_material_schema_ids
from src.shared.engine.count_engine import CountSectionLimit, get_count_profile
from src.shared.engine.document_structure_model import normalize_heading_map


APPLICATION_COUNT_PROFILE_ID = "application_word_limits"
APPLICATION_RULE_FAMILIES = ("project_application", "project_review_pack")
APPLICATION_SCHEMA_IDS = ("project_application_materials_v1",)
APPLICATION_WORD_SURFACES = (
    "w:p/w:pPr",
    "w:r/w:t",
    "w:tbl",
    "styles.xml",
    "numbering.xml",
)
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_EN_WORD_RE = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*")


@dataclass(frozen=True, slots=True)
class ApplicationSectionWordLimitIssue:
    kind: str
    section_id: str = ""
    severity: str = "warning"
    expected: str = ""
    observed: str = ""
    message: str = ""


@dataclass(frozen=True, slots=True)
class ApplicationSectionWordLimitItem:
    section_id: str
    label: str
    heading_title: str
    paragraph_index: int
    start_index: int
    end_index: int
    counts: dict[str, int] = field(default_factory=dict)
    limits: dict[str, int] = field(default_factory=dict)
    status: str = "ok"


@dataclass(frozen=True, slots=True)
class ApplicationSectionWordLimitSummary:
    section_count: int = 0
    matched_section_count: int = 0
    exceeded_section_count: int = 0
    required_missing_count: int = 0
    table_count: int = 0


@dataclass(frozen=True, slots=True)
class ApplicationSectionWordLimitResult:
    family_id: str = ""
    status: str = "not_applicable"
    profile_id: str = ""
    profile_name: str = ""
    rule_family: str = ""
    material_schema_ids: tuple[str, ...] = ()
    word_surfaces: tuple[str, ...] = APPLICATION_WORD_SURFACES
    summary: ApplicationSectionWordLimitSummary = field(
        default_factory=ApplicationSectionWordLimitSummary
    )
    sections: tuple[ApplicationSectionWordLimitItem, ...] = ()
    issues: tuple[ApplicationSectionWordLimitIssue, ...] = ()

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
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "rule_family": self.rule_family,
            "material_schema_ids": list(self.material_schema_ids),
            "word_surfaces": list(self.word_surfaces),
            "manual_confirmation_required": self.manual_confirmation_required,
            "summary": {
                "section_count": self.summary.section_count,
                "matched_section_count": self.summary.matched_section_count,
                "exceeded_section_count": self.summary.exceeded_section_count,
                "required_missing_count": self.summary.required_missing_count,
                "table_count": self.summary.table_count,
            },
            "sections": [_section_payload(section) for section in self.sections],
            "issue_count": len(self.issues),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "kind": issue.kind,
                    "section_id": issue.section_id,
                    "severity": issue.severity,
                    "expected": issue.expected,
                    "observed": issue.observed,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


def inspect_application_section_word_limits(
    config,
    doc,
    *,
    doc_tree=None,
    heading_map: Mapping[int, int] | None = None,
) -> ApplicationSectionWordLimitResult:
    """Build per-section word-limit evidence for project application reports."""

    count_profile_id = _clean_text(
        getattr(getattr(config, "compliance_profile", None), "count_profile_id", "")
    )
    rule_family = _clean_text(
        getattr(getattr(config, "compliance_profile", None), "rule_family", "")
    )
    schema_ids = _config_material_schema_ids(config)
    if not _is_application_config(
        config,
        count_profile_id=count_profile_id,
        rule_family=rule_family,
        schema_ids=schema_ids,
    ):
        return ApplicationSectionWordLimitResult()

    profile = get_count_profile(count_profile_id or APPLICATION_COUNT_PROFILE_ID)
    section_limits = tuple(getattr(profile, "section_limits", ()) or ())
    if not section_limits:
        return ApplicationSectionWordLimitResult(
            family_id="application_reports",
            status="warning",
            profile_id=profile.profile_id,
            profile_name=profile.label,
            rule_family=rule_family,
            material_schema_ids=tuple(schema_ids),
            issues=(
                ApplicationSectionWordLimitIssue(
                    kind="section_limits_not_declared",
                    expected="CountProfile.section_limits",
                    observed="0 section limit rules",
                    message="The application count profile does not declare section limits.",
                ),
            ),
        )

    headings = _build_heading_items(doc, doc_tree=doc_tree, heading_map=heading_map)
    paragraphs = [str(getattr(paragraph, "text", "") or "") for paragraph in doc.paragraphs]
    sections: list[ApplicationSectionWordLimitItem] = []
    issues: list[ApplicationSectionWordLimitIssue] = []
    matched_limit_ids: set[str] = set()

    for heading in headings:
        limit = _match_limit(heading["title"], section_limits)
        if limit is None:
            continue
        matched_limit_ids.add(limit.section_id)
        start_index = int(heading["paragraph_index"]) + 1
        end_index = int(heading["end_index"])
        if end_index < 0:
            end_index = len(paragraphs)
        text = "\n".join(paragraphs[start_index:end_index])
        counts = _count_text(text)
        limits = _limit_payload(limit)
        section_issues = _limit_issues(limit, counts)
        status = "exceeded" if section_issues else "ok"
        issues.extend(section_issues)
        sections.append(
            ApplicationSectionWordLimitItem(
                section_id=limit.section_id,
                label=limit.label,
                heading_title=heading["title"],
                paragraph_index=int(heading["paragraph_index"]),
                start_index=start_index,
                end_index=end_index,
                counts=counts,
                limits=limits,
                status=status,
            )
        )

    for limit in section_limits:
        if limit.required and limit.section_id not in matched_limit_ids:
            issues.append(
                ApplicationSectionWordLimitIssue(
                    kind="required_section_missing",
                    section_id=limit.section_id,
                    expected=limit.label,
                    observed="not found",
                    message=f"Required application section is missing: {limit.label}.",
                )
            )

    if not headings:
        issues.append(
            ApplicationSectionWordLimitIssue(
                kind="no_headings_detected",
                expected="application section headings",
                observed="0 headings",
                message="No headings were detected for application section word limits.",
            )
        )

    summary = ApplicationSectionWordLimitSummary(
        section_count=len(headings),
        matched_section_count=len(sections),
        exceeded_section_count=sum(1 for section in sections if section.status == "exceeded"),
        required_missing_count=sum(1 for issue in issues if issue.kind == "required_section_missing"),
        table_count=len(getattr(doc, "tables", []) or []),
    )
    return ApplicationSectionWordLimitResult(
        family_id="application_reports",
        status="warning" if issues else "ok",
        profile_id=profile.profile_id,
        profile_name=profile.label,
        rule_family=rule_family,
        material_schema_ids=tuple(schema_ids),
        summary=summary,
        sections=tuple(sections[:50]),
        issues=tuple(issues),
    )


def _section_payload(section: ApplicationSectionWordLimitItem) -> dict[str, object]:
    return {
        "section_id": section.section_id,
        "label": section.label,
        "heading_title": section.heading_title,
        "paragraph_index": section.paragraph_index,
        "start_index": section.start_index,
        "end_index": section.end_index,
        "counts": dict(section.counts),
        "limits": dict(section.limits),
        "status": section.status,
    }


def _is_application_config(
    config,
    *,
    count_profile_id: str,
    rule_family: str,
    schema_ids: tuple[str, ...],
) -> bool:
    scene_id = _clean_text(getattr(config, "scene_id", ""))
    category = _clean_text(getattr(config, "category", ""))
    if scene_id == "project_application" or category == "project_application":
        return True
    if count_profile_id == APPLICATION_COUNT_PROFILE_ID:
        return True
    if rule_family in APPLICATION_RULE_FAMILIES:
        return True
    return any(schema_id in APPLICATION_SCHEMA_IDS for schema_id in schema_ids)


def _config_material_schema_ids(config) -> tuple[str, ...]:
    input_profile = getattr(config, "input_source_profile", None)
    return resolve_material_schema_ids(
        _clean_text(getattr(input_profile, "material_schema_id", "")),
        list(getattr(input_profile, "material_schema_ids", []) or []),
    )


def _build_heading_items(
    doc,
    *,
    doc_tree=None,
    heading_map: Mapping[int, int] | None = None,
) -> list[dict[str, object]]:
    tree_headings = list(getattr(doc_tree, "headings", []) or [])
    if tree_headings:
        items = [
            {
                "paragraph_index": int(getattr(heading, "para_index", -1) or -1),
                "level": int(getattr(heading, "level", 0) or 0),
                "title": _clean_text(getattr(heading, "text", "")),
            }
            for heading in tree_headings
        ]
        return _with_end_indexes(items, len(getattr(doc, "paragraphs", []) or []))

    paragraphs = list(getattr(doc, "paragraphs", []) or [])
    normalized_heading_map = normalize_heading_map(heading_map)
    if not normalized_heading_map:
        normalized_heading_map = _style_heading_map(paragraphs)
    items = [
        {
            "paragraph_index": index,
            "level": level,
            "title": _clean_text(getattr(paragraphs[index], "text", "")),
        }
        for index, level in normalized_heading_map.items()
        if index < len(paragraphs)
    ]
    return _with_end_indexes(items, len(paragraphs))


def _with_end_indexes(items: list[dict[str, object]], total: int) -> list[dict[str, object]]:
    normalized = [
        item
        for item in sorted(items, key=lambda value: int(value["paragraph_index"]))
        if int(item["paragraph_index"]) >= 0 and int(item["level"]) > 0
    ]
    for index, item in enumerate(normalized):
        later = normalized[index + 1 :]
        item["end_index"] = int(later[0]["paragraph_index"]) if later else total
    return normalized


def _style_heading_map(paragraphs: list) -> dict[int, int]:
    result: dict[int, int] = {}
    for index, paragraph in enumerate(paragraphs):
        style_name = _clean_text(getattr(getattr(paragraph, "style", None), "name", ""))
        match = re.search(r"heading\s*(\d+)", style_name, re.IGNORECASE)
        if match:
            result[index] = int(match.group(1))
    return result


def _match_limit(title: str, limits: tuple[CountSectionLimit, ...]) -> CountSectionLimit | None:
    normalized = title.strip().lower()
    for limit in limits:
        patterns = tuple(getattr(limit, "heading_patterns", ()) or ())
        if not patterns:
            continue
        for pattern in patterns:
            if _clean_text(pattern).lower() in normalized:
                return limit
    return None


def _count_text(text: str) -> dict[str, int]:
    return {
        "cjk_characters": len(_CJK_RE.findall(text)),
        "english_words": len(_EN_WORD_RE.findall(text)),
        "characters_no_spaces": sum(1 for char in text if not char.isspace()),
    }


def _limit_payload(limit: CountSectionLimit) -> dict[str, int]:
    return {
        "max_characters_no_spaces": int(getattr(limit, "max_characters_no_spaces", 0) or 0),
        "max_cjk_characters": int(getattr(limit, "max_cjk_characters", 0) or 0),
        "max_english_words": int(getattr(limit, "max_english_words", 0) or 0),
    }


def _limit_issues(
    limit: CountSectionLimit,
    counts: dict[str, int],
) -> list[ApplicationSectionWordLimitIssue]:
    issues: list[ApplicationSectionWordLimitIssue] = []
    for metric, label in (
        ("characters_no_spaces", "characters without spaces"),
        ("cjk_characters", "CJK characters"),
        ("english_words", "English words"),
    ):
        max_value = int(getattr(limit, f"max_{metric}", 0) or 0)
        if max_value <= 0:
            continue
        observed = int(counts.get(metric) or 0)
        if observed <= max_value:
            continue
        issues.append(
            ApplicationSectionWordLimitIssue(
                kind="section_word_limit_exceeded",
                section_id=limit.section_id,
                expected=f"{label} <= {max_value}",
                observed=f"{observed}",
                message=(
                    f"{limit.label} exceeds the configured section limit: "
                    f"{observed}/{max_value} {label}."
                ),
            )
        )
    return issues


def _clean_text(value: object) -> str:
    return str(value or "").strip()
