"""Runtime validation for English journal BibTeX / CSL citation sources."""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from src.config.material_schema_registry import get_material_schema, resolve_material_schema_ids


JOURNAL_FAMILY_ID = "journal_en"
JOURNAL_SCHEMA_IDS = ("journal_submission_materials_v1", "journal_materials_v1")

_BIBTEX_SOURCE_KEYS = (
    "bibtex",
    "bib",
    "references_bibtex",
    "bibliography_bibtex",
)
_CSL_SOURCE_KEYS = (
    "csl_json",
    "csl",
    "references_csl",
    "references_json",
    "bibliography_json",
)
_CITATION_SOURCE_KEYS = (
    "citation_keys",
    "citations",
    "body_citations",
    "manuscript_citations",
)
_CITE_COMMAND_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*)*\{([^}]+)\}")
_AT_CITATION_RE = re.compile(r"(?<![\w.])@([A-Za-z0-9_:.+-]+)")


@dataclass(frozen=True, slots=True)
class JournalCitationIssue:
    """One validation issue in journal citation source evidence."""

    path: str
    kind: str
    message: str
    severity: str = "warning"
    expected: str = ""
    observed: str = ""


@dataclass(frozen=True, slots=True)
class JournalReferenceEntry:
    """One parsed BibTeX / CSL reference entry."""

    key: str
    entry_type: str = ""
    source_format: str = ""
    fields: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JournalCitationSummary:
    """Compact counts used by reports and Workbench summaries."""

    source_format: str = ""
    reference_count: int = 0
    citation_count: int = 0
    matched_citation_count: int = 0
    missing_reference_count: int = 0
    unreferenced_source_count: int = 0
    duplicate_key_count: int = 0
    incomplete_reference_count: int = 0


@dataclass(frozen=True, slots=True)
class JournalCitationValidationResult:
    """Structured runtime evidence for journal citation source validation."""

    schema_id: str = ""
    family_id: str = ""
    status: str = "not_applicable"
    source_key: str = ""
    citation_source: str = ""
    summary: JournalCitationSummary = field(default_factory=JournalCitationSummary)
    reference_keys: tuple[str, ...] = ()
    citation_keys: tuple[str, ...] = ()
    issues: tuple[JournalCitationIssue, ...] = ()

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
            "schema_id": self.schema_id,
            "family_id": self.family_id,
            "status": self.status,
            "source_key": self.source_key,
            "citation_source": self.citation_source,
            "manual_confirmation_required": self.manual_confirmation_required,
            "summary": {
                "source_format": self.summary.source_format,
                "reference_count": self.summary.reference_count,
                "citation_count": self.summary.citation_count,
                "matched_citation_count": self.summary.matched_citation_count,
                "missing_reference_count": self.summary.missing_reference_count,
                "unreferenced_source_count": self.summary.unreferenced_source_count,
                "duplicate_key_count": self.summary.duplicate_key_count,
                "incomplete_reference_count": self.summary.incomplete_reference_count,
            },
            "reference_keys": list(self.reference_keys),
            "citation_keys": list(self.citation_keys),
            "issue_count": len(self.issues),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "path": issue.path,
                    "kind": issue.kind,
                    "severity": issue.severity,
                    "expected": issue.expected,
                    "observed": issue.observed,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


def inspect_journal_citations(config, doc: Any | None = None) -> JournalCitationValidationResult:
    """Validate BibTeX / CSL sources for English journal workflows."""

    schema_ids = _config_material_schema_ids(config)
    family_id = _journal_family_for_schema_ids(schema_ids)
    if not _is_journal_config(config, schema_ids=schema_ids, family_id=family_id):
        return JournalCitationValidationResult()

    entity_data = getattr(config, "entity_data", {}) or {}
    entries, source_key, source_format, parse_issues = _extract_reference_entries(entity_data)
    citation_keys, citation_source = _extract_citation_keys(entity_data, doc)

    if not entries and not parse_issues:
        parse_issues.append(
            JournalCitationIssue(
                path="entity_data",
                kind="missing_reference_source",
                severity="error",
                expected="bibtex/csl_json reference source",
                message=(
                    "English journal workflows require one BibTeX or CSL JSON "
                    "reference source before citation checks can be trusted."
                ),
            )
        )

    issues = list(parse_issues)
    reference_keys = [entry.key for entry in entries if entry.key]
    duplicate_keys = _duplicate_values(reference_keys)
    for key in duplicate_keys:
        issues.append(
            JournalCitationIssue(
                path=f"{source_key}.{key}" if source_key else key,
                kind="duplicate_reference_key",
                severity="error",
                expected="unique BibTeX/CSL ids",
                observed=key,
                message=f"Reference key '{key}' appears more than once.",
            )
        )

    unique_reference_keys = tuple(_unique_values(reference_keys))
    unique_citation_keys = tuple(_unique_values(citation_keys))
    reference_key_set = set(unique_reference_keys)
    citation_key_set = set(unique_citation_keys)

    missing_keys = sorted(citation_key_set - reference_key_set)
    for key in missing_keys:
        issues.append(
            JournalCitationIssue(
                path=f"citations.{key}",
                kind="missing_reference_for_citation",
                severity="error",
                expected="citation key present in BibTeX/CSL source",
                observed=key,
                message=f"Citation key '{key}' is used in the manuscript but missing from the reference source.",
            )
        )

    unreferenced_keys = sorted(reference_key_set - citation_key_set) if citation_key_set else []
    for key in unreferenced_keys:
        issues.append(
            JournalCitationIssue(
                path=f"{source_key}.{key}" if source_key else key,
                kind="unreferenced_source_entry",
                severity="warning",
                expected="source entry cited in manuscript",
                observed=key,
                message=f"Reference key '{key}' is present in the source but was not cited.",
            )
        )

    incomplete_keys = _incomplete_reference_keys(entries)
    for key, missing_fields in incomplete_keys.items():
        issues.append(
            JournalCitationIssue(
                path=f"{source_key}.{key}" if source_key else key,
                kind="incomplete_reference_metadata",
                severity="warning",
                expected=", ".join(missing_fields),
                observed=key,
                message=f"Reference key '{key}' is missing metadata: {', '.join(missing_fields)}.",
            )
        )

    summary = JournalCitationSummary(
        source_format=source_format,
        reference_count=len(unique_reference_keys),
        citation_count=len(unique_citation_keys),
        matched_citation_count=len(citation_key_set & reference_key_set),
        missing_reference_count=len(missing_keys),
        unreferenced_source_count=len(unreferenced_keys),
        duplicate_key_count=len(duplicate_keys),
        incomplete_reference_count=len(incomplete_keys),
    )
    status = "error" if any(issue.severity == "error" for issue in issues) else "ok"
    if issues and status != "error":
        status = "warning"
    return JournalCitationValidationResult(
        schema_id=schema_ids[0] if schema_ids else JOURNAL_SCHEMA_IDS[0],
        family_id=family_id or JOURNAL_FAMILY_ID,
        status=status,
        source_key=source_key,
        citation_source=citation_source,
        summary=summary,
        reference_keys=unique_reference_keys,
        citation_keys=unique_citation_keys,
        issues=tuple(issues),
    )


def _config_material_schema_ids(config) -> tuple[str, ...]:
    profile = getattr(config, "input_source_profile", None)
    return resolve_material_schema_ids(
        str(getattr(profile, "material_schema_id", "") or "").strip(),
        list(getattr(profile, "material_schema_ids", []) or []),
    )


def _journal_family_for_schema_ids(schema_ids: tuple[str, ...]) -> str:
    for schema_id in schema_ids:
        try:
            family = get_material_schema(schema_id).family
        except KeyError:
            continue
        if family == JOURNAL_FAMILY_ID:
            return family
    return ""


def _is_journal_config(config, *, schema_ids: tuple[str, ...], family_id: str) -> bool:
    if family_id == JOURNAL_FAMILY_ID or any(schema_id in JOURNAL_SCHEMA_IDS for schema_id in schema_ids):
        return True
    compliance = getattr(config, "compliance_profile", None)
    profile_values = (
        getattr(compliance, "profile_id", ""),
        getattr(compliance, "rule_family", ""),
        getattr(compliance, "count_profile_id", ""),
    )
    if any("journal" in str(value or "").lower() for value in profile_values):
        return True
    input_profile = getattr(config, "input_source_profile", None)
    input_formats = {
        str(value or "").strip().lower()
        for value in [
            *(getattr(input_profile, "accepted_formats", []) or []),
            *(getattr(input_profile, "structured_formats", []) or []),
        ]
    }
    return bool({"bibtex", "csl_json"} & input_formats)


def _extract_reference_entries(
    entity_data: object,
) -> tuple[list[JournalReferenceEntry], str, str, list[JournalCitationIssue]]:
    issues: list[JournalCitationIssue] = []
    if not isinstance(entity_data, Mapping):
        return [], "", "", issues

    for key in _BIBTEX_SOURCE_KEYS:
        value = entity_data.get(key)
        if not str(value or "").strip():
            continue
        entries, parse_issues = _parse_bibtex(str(value), source_key=f"entity_data.{key}")
        issues.extend(parse_issues)
        if entries or parse_issues:
            return entries, f"entity_data.{key}", "bibtex", issues

    for key in _CSL_SOURCE_KEYS:
        value = entity_data.get(key)
        if not str(value or "").strip():
            continue
        entries, parse_issues = _parse_csl_json(value, source_key=f"entity_data.{key}")
        issues.extend(parse_issues)
        if entries or parse_issues:
            return entries, f"entity_data.{key}", "csl_json", issues

    return [], "", "", issues


def _parse_bibtex(
    text: str,
    *,
    source_key: str,
) -> tuple[list[JournalReferenceEntry], list[JournalCitationIssue]]:
    entries: list[JournalReferenceEntry] = []
    issues: list[JournalCitationIssue] = []
    pos = 0
    while True:
        match = re.search(r"@([A-Za-z]+)\s*([{(])", text[pos:])
        if match is None:
            break
        entry_type = match.group(1).lower()
        open_char = match.group(2)
        close_char = "}" if open_char == "{" else ")"
        start = pos + match.end()
        end = _find_balanced_end(text, start, open_char=open_char, close_char=close_char)
        if end < 0:
            issues.append(
                JournalCitationIssue(
                    path=source_key,
                    kind="invalid_bibtex_entry",
                    severity="error",
                    expected=f"balanced {open_char}{close_char} entry",
                    observed=text[pos + match.start() : pos + match.start() + 40],
                    message="BibTeX entry is not balanced.",
                )
            )
            break
        body = text[start:end]
        key, field_text = _split_bibtex_entry_body(body)
        if not key:
            issues.append(
                JournalCitationIssue(
                    path=source_key,
                    kind="missing_bibtex_key",
                    severity="error",
                    expected="entry key before first comma",
                    observed=body[:40],
                    message="BibTeX entry is missing its citation key.",
                )
            )
        else:
            entries.append(
                JournalReferenceEntry(
                    key=key,
                    entry_type=entry_type,
                    source_format="bibtex",
                    fields=_parse_bibtex_fields(field_text),
                )
            )
        pos = end + 1
    return entries, issues


def _find_balanced_end(text: str, start: int, *, open_char: str, close_char: str) -> int:
    depth = 1
    quote = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            quote = not quote
            continue
        if quote:
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _split_bibtex_entry_body(body: str) -> tuple[str, str]:
    depth = 0
    quote = False
    for index, char in enumerate(body):
        if char == '"':
            quote = not quote
        elif not quote and char in "{(":
            depth += 1
        elif not quote and char in "})" and depth > 0:
            depth -= 1
        elif not quote and depth == 0 and char == ",":
            return body[:index].strip(), body[index + 1 :]
    return body.strip(), ""


def _parse_bibtex_fields(text: str) -> dict[str, object]:
    fields: dict[str, object] = {}
    pos = 0
    while pos < len(text):
        match = re.search(r"([A-Za-z][\w-]*)\s*=", text[pos:])
        if match is None:
            break
        name = match.group(1).lower()
        value_start = pos + match.end()
        value, value_end = _parse_bibtex_value(text, value_start)
        fields[name] = value
        pos = value_end + 1
    return fields


def _parse_bibtex_value(text: str, start: int) -> tuple[str, int]:
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text):
        return "", start
    if text[start] in "{(":
        close_char = "}" if text[start] == "{" else ")"
        end = _find_balanced_end(text, start + 1, open_char=text[start], close_char=close_char)
        if end >= 0:
            return _clean_reference_value(text[start + 1 : end]), end
    if text[start] == '"':
        index = start + 1
        escaped = False
        while index < len(text):
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                return _clean_reference_value(text[start + 1 : index]), index
            index += 1
    comma = text.find(",", start)
    if comma < 0:
        return _clean_reference_value(text[start:]), len(text)
    return _clean_reference_value(text[start:comma]), comma


def _parse_csl_json(
    value: object,
    *,
    source_key: str,
) -> tuple[list[JournalReferenceEntry], list[JournalCitationIssue]]:
    parsed = _parse_structured_value(value)
    if isinstance(parsed, Mapping):
        for collection_key in ("items", "references", "bibliography"):
            maybe_items = parsed.get(collection_key)
            if _is_sequence(maybe_items):
                parsed = list(maybe_items)
                break
    if not _is_sequence(parsed):
        return [], [
            JournalCitationIssue(
                path=source_key,
                kind="invalid_csl_json",
                severity="error",
                expected="CSL JSON array or object with items/references",
                observed=type(parsed).__name__,
                message="CSL JSON source could not be parsed as a reference list.",
            )
        ]
    entries: list[JournalReferenceEntry] = []
    issues: list[JournalCitationIssue] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, Mapping):
            issues.append(
                JournalCitationIssue(
                    path=f"{source_key}.{index}",
                    kind="invalid_csl_item",
                    severity="error",
                    expected="CSL item object",
                    observed=type(item).__name__,
                    message="CSL reference item must be an object.",
                )
            )
            continue
        key = str(item.get("id") or item.get("key") or "").strip()
        if not key:
            issues.append(
                JournalCitationIssue(
                    path=f"{source_key}.{index}",
                    kind="missing_csl_id",
                    severity="error",
                    expected="id",
                    message="CSL reference item is missing an id.",
                )
            )
            continue
        entries.append(
            JournalReferenceEntry(
                key=key,
                entry_type=str(item.get("type") or "").strip(),
                source_format="csl_json",
                fields=dict(item),
            )
        )
    return entries, issues


def _parse_structured_value(value: object) -> object | None:
    if isinstance(value, Mapping):
        return dict(value)
    if _is_sequence(value):
        return list(value)
    text = str(value or "").strip()
    if not text:
        return None
    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(text)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
    return None


def _extract_citation_keys(entity_data: object, doc: Any | None) -> tuple[tuple[str, ...], str]:
    keys: list[str] = []
    sources: list[str] = []
    if isinstance(entity_data, Mapping):
        for key in _CITATION_SOURCE_KEYS:
            if key not in entity_data:
                continue
            extracted = _citation_keys_from_value(entity_data.get(key))
            if extracted:
                keys.extend(extracted)
                sources.append(f"entity_data.{key}")
    if doc is not None:
        extracted = _citation_keys_from_text("\n".join(_document_paragraph_text(doc)))
        if extracted:
            keys.extend(extracted)
            sources.append("document.paragraphs")
    return tuple(_unique_values(keys)), ", ".join(sources)


def _citation_keys_from_value(value: object) -> list[str]:
    parsed = _parse_structured_value(value)
    if _is_sequence(parsed):
        keys: list[str] = []
        for item in parsed:
            if isinstance(item, Mapping):
                keys.append(str(item.get("id") or item.get("key") or "").strip())
            else:
                keys.extend(_split_citation_key_text(str(item or "")))
        return [key for key in keys if key]
    text = str(value or "")
    keys = _citation_keys_from_text(text)
    return keys or _split_citation_key_text(text)


def _citation_keys_from_text(text: str) -> list[str]:
    keys: list[str] = []
    for match in _CITE_COMMAND_RE.finditer(text or ""):
        keys.extend(_split_citation_key_text(match.group(1)))
    for match in _AT_CITATION_RE.finditer(text or ""):
        keys.append(match.group(1).rstrip(".,;:"))
    return [key for key in keys if key]


def _split_citation_key_text(text: str) -> list[str]:
    return [
        token.strip().lstrip("@").rstrip(".,;:")
        for token in re.split(r"[,;\s]+", text or "")
        if token.strip().lstrip("@").rstrip(".,;:")
    ]


def _document_paragraph_text(doc: Any) -> list[str]:
    return [str(getattr(para, "text", "") or "") for para in list(getattr(doc, "paragraphs", []) or [])]


def _incomplete_reference_keys(entries: Sequence[JournalReferenceEntry]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        if not entry.key:
            continue
        fields = {str(key).lower(): value for key, value in dict(entry.fields or {}).items()}
        missing: list[str] = []
        if not _has_any_field(fields, ("title",)):
            missing.append("title")
        if not _has_any_field(fields, ("author", "editor")):
            missing.append("author/editor")
        if not _has_year_field(fields):
            missing.append("year/issued")
        if missing:
            result.setdefault(entry.key, tuple(missing))
    return result


def _has_any_field(fields: Mapping[str, object], names: Sequence[str]) -> bool:
    return any(str(fields.get(name) or "").strip() for name in names)


def _has_year_field(fields: Mapping[str, object]) -> bool:
    if _has_any_field(fields, ("year", "date", "issued")):
        return True
    issued = fields.get("issued")
    return isinstance(issued, Mapping) and bool(issued.get("date-parts"))


def _duplicate_values(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def _unique_values(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _clean_reference_value(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


__all__ = [
    "JournalCitationIssue",
    "JournalCitationSummary",
    "JournalCitationValidationResult",
    "inspect_journal_citations",
]
