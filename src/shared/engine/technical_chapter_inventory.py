"""Runtime chapter inventory for technical and long documents."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.config.material_schema_registry import get_material_schema, resolve_material_schema_ids


TECHNICAL_RULE_FAMILIES = (
    "technical_review",
    "long_document_structure",
    "proof_copy",
)
TECHNICAL_SCHEMA_IDS = (
    "technical_document_v1",
    "long_document_metadata_v1",
)
TECHNICAL_WORD_SURFACES = (
    "w:p/w:pPr",
    "numbering.xml",
    "w:tbl",
    "w:drawing",
    "w:fldSimple/w:instrText",
    "header*.xml/footer*.xml",
    "sectPr",
    "word/_rels/*.rels",
)


@dataclass(frozen=True, slots=True)
class TechnicalChapterInventoryIssue:
    """One issue found while building long-document inventory evidence."""

    kind: str
    message: str
    severity: str = "warning"
    expected: str = ""
    observed: str = ""


@dataclass(frozen=True, slots=True)
class TechnicalChapterInventoryItem:
    """One heading/chapter item in the inventory."""

    paragraph_index: int
    level: int
    title: str
    section_type: str = ""
    start_index: int = -1
    end_index: int = -1


@dataclass(frozen=True, slots=True)
class TechnicalChapterInventorySummary:
    """Compact counts used by reports and Workbench payloads."""

    heading_count: int = 0
    chapter_count: int = 0
    appendix_count: int = 0
    max_heading_level: int = 0
    table_count: int = 0
    figure_count: int = 0
    toc_present: bool = False


@dataclass(frozen=True, slots=True)
class TechnicalChapterInventoryResult:
    """Structured chapter inventory evidence for technical long documents."""

    family_id: str = ""
    status: str = "not_applicable"
    rule_family: str = ""
    profile_id: str = ""
    material_schema_ids: tuple[str, ...] = ()
    word_surfaces: tuple[str, ...] = TECHNICAL_WORD_SURFACES
    summary: TechnicalChapterInventorySummary = field(
        default_factory=TechnicalChapterInventorySummary
    )
    chapters: tuple[TechnicalChapterInventoryItem, ...] = ()
    headings: tuple[TechnicalChapterInventoryItem, ...] = ()
    issues: tuple[TechnicalChapterInventoryIssue, ...] = ()

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
            "rule_family": self.rule_family,
            "profile_id": self.profile_id,
            "material_schema_ids": list(self.material_schema_ids),
            "word_surfaces": list(self.word_surfaces),
            "manual_confirmation_required": self.manual_confirmation_required,
            "summary": {
                "heading_count": self.summary.heading_count,
                "chapter_count": self.summary.chapter_count,
                "appendix_count": self.summary.appendix_count,
                "max_heading_level": self.summary.max_heading_level,
                "table_count": self.summary.table_count,
                "figure_count": self.summary.figure_count,
                "toc_present": self.summary.toc_present,
            },
            "chapters": [_item_payload(item) for item in self.chapters],
            "headings": [_item_payload(item) for item in self.headings],
            "issue_count": len(self.issues),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "kind": issue.kind,
                    "severity": issue.severity,
                    "expected": issue.expected,
                    "observed": issue.observed,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


def inspect_technical_chapter_inventory(
    config,
    doc,
    *,
    doc_tree=None,
    heading_map: Mapping[int, int] | None = None,
) -> TechnicalChapterInventoryResult:
    """Build chapter/appendix/table/figure inventory evidence for long docs."""

    schema_ids = _config_material_schema_ids(config)
    rule_family = _clean_text(
        getattr(getattr(config, "compliance_profile", None), "rule_family", "")
    )
    profile_id = _clean_text(
        getattr(getattr(config, "compliance_profile", None), "profile_id", "")
    )
    family_id = _technical_family_for_schema_ids(schema_ids)
    if not _is_technical_config(config, schema_ids=schema_ids, rule_family=rule_family):
        return TechnicalChapterInventoryResult()

    headings = _build_heading_items(doc, doc_tree=doc_tree, heading_map=heading_map)
    chapters = tuple(
        item
        for item in headings
        if item.level == 1
        and item.section_type in {"", "body"}
        and not _looks_like_appendix(item.title)
    )
    appendix_items = tuple(
        item
        for item in headings
        if item.section_type == "appendix" or _looks_like_appendix(item.title)
    )
    toc_present = _section_present(doc_tree, "toc")
    issues: list[TechnicalChapterInventoryIssue] = []
    if not headings:
        issues.append(
            TechnicalChapterInventoryIssue(
                kind="no_headings_detected",
                expected="technical document headings",
                observed="0 headings",
                message="No headings were detected for the technical chapter inventory.",
            )
        )
    elif not chapters:
        issues.append(
            TechnicalChapterInventoryIssue(
                kind="no_body_chapters_detected",
                expected="at least one body level-1 chapter",
                observed=f"{len(headings)} heading(s), 0 body chapter(s)",
                message=(
                    "Technical long documents should expose at least one body "
                    "chapter before proof/review/archive delivery."
                ),
            )
        )

    table_count = len(getattr(doc, "tables", []) or [])
    figure_count = len(getattr(doc, "inline_shapes", []) or [])
    max_level = max((item.level for item in headings), default=0)
    return TechnicalChapterInventoryResult(
        family_id=family_id or "technical_long_docs",
        status="warning" if issues else "ok",
        rule_family=rule_family,
        profile_id=profile_id,
        material_schema_ids=tuple(schema_ids),
        summary=TechnicalChapterInventorySummary(
            heading_count=len(headings),
            chapter_count=len(chapters),
            appendix_count=len(appendix_items),
            max_heading_level=max_level,
            table_count=table_count,
            figure_count=figure_count,
            toc_present=toc_present,
        ),
        chapters=chapters[:20],
        headings=headings[:50],
        issues=tuple(issues),
    )


def _item_payload(item: TechnicalChapterInventoryItem) -> dict[str, object]:
    return {
        "paragraph_index": item.paragraph_index,
        "level": item.level,
        "title": item.title,
        "section_type": item.section_type,
        "start_index": item.start_index,
        "end_index": item.end_index,
    }


def _is_technical_config(config, *, schema_ids: tuple[str, ...], rule_family: str) -> bool:
    scene_id = _clean_text(getattr(config, "scene_id", ""))
    category = _clean_text(getattr(config, "category", ""))
    if scene_id == "technical" or category == "technical":
        return True
    if rule_family in TECHNICAL_RULE_FAMILIES:
        return True
    return any(schema_id in TECHNICAL_SCHEMA_IDS for schema_id in schema_ids)


def _config_material_schema_ids(config) -> tuple[str, ...]:
    input_profile = getattr(config, "input_source_profile", None)
    return resolve_material_schema_ids(
        _clean_text(getattr(input_profile, "material_schema_id", "")),
        list(getattr(input_profile, "material_schema_ids", []) or []),
    )


def _technical_family_for_schema_ids(schema_ids: tuple[str, ...]) -> str:
    for schema_id in schema_ids:
        try:
            family = get_material_schema(schema_id).family
        except KeyError:
            continue
        if family == "technical":
            return "technical_long_docs"
        if family == "long_document_publishing":
            return "long_document_publishing"
    return ""


def _build_heading_items(
    doc,
    *,
    doc_tree=None,
    heading_map: Mapping[int, int] | None = None,
) -> tuple[TechnicalChapterInventoryItem, ...]:
    headings = list(getattr(doc_tree, "headings", []) or [])
    if headings:
        result: list[TechnicalChapterInventoryItem] = []
        for heading in headings:
            index = int(getattr(heading, "para_index", -1) or -1)
            level = int(getattr(heading, "level", 0) or 0)
            title = _clean_text(getattr(heading, "text", ""))
            if index < 0 or level <= 0:
                continue
            result.append(
                TechnicalChapterInventoryItem(
                    paragraph_index=index,
                    level=level,
                    title=title,
                    section_type=_section_for_index(doc_tree, index),
                    start_index=index,
                    end_index=_next_heading_index(headings, index),
                )
            )
        return tuple(sorted(result, key=lambda item: item.paragraph_index))

    normalized_heading_map = _normalize_heading_map(heading_map)
    paragraphs = list(getattr(doc, "paragraphs", []) or [])
    result = []
    for index, level in normalized_heading_map.items():
        if index >= len(paragraphs):
            continue
        result.append(
            TechnicalChapterInventoryItem(
                paragraph_index=index,
                level=level,
                title=_clean_text(getattr(paragraphs[index], "text", "")),
                section_type=_section_for_index(doc_tree, index),
                start_index=index,
                end_index=_next_heading_map_index(normalized_heading_map, index, len(paragraphs)),
            )
        )
    return tuple(result)


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


def _section_for_index(doc_tree, index: int) -> str:
    if doc_tree is None:
        return ""
    getter = getattr(doc_tree, "get_section_for_paragraph", None)
    if callable(getter):
        try:
            return _clean_text(getter(index))
        except Exception:
            return ""
    return ""


def _section_present(doc_tree, section_type: str) -> bool:
    if doc_tree is None:
        return False
    sections = list(getattr(doc_tree, "sections", []) or [])
    if any(_clean_text(getattr(section, "section_type", "")) == section_type for section in sections):
        return True
    ranges = dict(getattr(doc_tree, "section_ranges", {}) or {})
    return section_type in ranges


def _next_heading_index(headings: list[object], index: int) -> int:
    later = [
        int(getattr(heading, "para_index", -1) or -1)
        for heading in headings
        if int(getattr(heading, "para_index", -1) or -1) > index
    ]
    return min(later) if later else -1


def _next_heading_map_index(heading_map: Mapping[int, int], index: int, total: int) -> int:
    later = [candidate for candidate in heading_map if candidate > index]
    return min(later) if later else total


def _looks_like_appendix(title: str) -> bool:
    normalized = title.strip().lower()
    return normalized.startswith("appendix") or normalized.startswith("附录")


def _clean_text(value: object) -> str:
    return str(value or "").strip()
