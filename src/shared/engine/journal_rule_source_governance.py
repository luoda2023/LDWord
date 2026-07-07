"""Runtime evidence for reviewed English journal rule sources."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.config.journal_rule_source_registry import (
    JournalRuleSourceSpec,
    get_journal_rule_source,
    journal_rule_source_for_count_profile,
)
from src.config.material_schema_registry import get_material_schema, resolve_material_schema_ids


JOURNAL_FAMILY_ID = "journal_en"
JOURNAL_SCHEMA_IDS = ("journal_submission_materials_v1", "journal_materials_v1")
_RULE_SOURCE_KEYS = (
    "journal_rule_source_id",
    "journal_rules_source_id",
    "journal_profile_source_id",
)
_JOURNAL_NAME_KEYS = ("journal_name", "target_journal", "publisher_journal")


@dataclass(frozen=True, slots=True)
class JournalRuleSourceIssue:
    """One issue in journal rule source governance evidence."""

    path: str
    kind: str
    message: str
    severity: str = "warning"
    expected: str = ""
    observed: str = ""


@dataclass(frozen=True, slots=True)
class JournalRuleSourceSummary:
    """Compact counts used by reports and Workbench summaries."""

    declared_count_profile_count: int = 0
    matched_count_profile_count: int = 0
    reviewed_source_count: int = 0
    generic_source_count: int = 0
    target_journal_declared: bool = False


@dataclass(frozen=True, slots=True)
class JournalRuleSourceGovernanceResult:
    """Structured evidence for journal rule source review governance."""

    family_id: str = ""
    status: str = "not_applicable"
    rule_source_id: str = ""
    rule_source_label: str = ""
    source_type: str = ""
    source_reference: str = ""
    version: str = ""
    review_status: str = ""
    reviewed_by: str = ""
    reviewed_on: str = ""
    count_profile_id: str = ""
    target_journal_name: str = ""
    declared_count_profile_ids: tuple[str, ...] = ()
    include_scope_summary: tuple[str, ...] = ()
    exclude_scope_summary: tuple[str, ...] = ()
    boundary_notes: tuple[str, ...] = ()
    summary: JournalRuleSourceSummary = field(default_factory=JournalRuleSourceSummary)
    issues: tuple[JournalRuleSourceIssue, ...] = ()

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
        return bool(
            self.issues
            or self.summary.generic_source_count
            or self.review_status != "reviewed"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "status": self.status,
            "rule_source_id": self.rule_source_id,
            "rule_source_label": self.rule_source_label,
            "source_type": self.source_type,
            "source_reference": self.source_reference,
            "version": self.version,
            "review_status": self.review_status,
            "reviewed_by": self.reviewed_by,
            "reviewed_on": self.reviewed_on,
            "count_profile_id": self.count_profile_id,
            "target_journal_name": self.target_journal_name,
            "manual_confirmation_required": self.manual_confirmation_required,
            "declared_count_profile_ids": list(self.declared_count_profile_ids),
            "include_scope_summary": list(self.include_scope_summary),
            "exclude_scope_summary": list(self.exclude_scope_summary),
            "boundary_notes": list(self.boundary_notes),
            "summary": {
                "declared_count_profile_count": (
                    self.summary.declared_count_profile_count
                ),
                "matched_count_profile_count": self.summary.matched_count_profile_count,
                "reviewed_source_count": self.summary.reviewed_source_count,
                "generic_source_count": self.summary.generic_source_count,
                "target_journal_declared": self.summary.target_journal_declared,
            },
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


def inspect_journal_rule_source_governance(
    config,
) -> JournalRuleSourceGovernanceResult:
    """Build governance evidence for reviewed English journal rule sources."""

    schema_ids = _config_material_schema_ids(config)
    family_id = _journal_family_for_schema_ids(schema_ids)
    if not _is_journal_config(config, schema_ids=schema_ids, family_id=family_id):
        return JournalRuleSourceGovernanceResult()

    compliance = getattr(config, "compliance_profile", None)
    count_profile_id = str(getattr(compliance, "count_profile_id", "") or "").strip()
    if not count_profile_id:
        count_profile_id = "journal_words"
    entity_data = getattr(config, "entity_data", {}) or {}
    if not isinstance(entity_data, Mapping):
        entity_data = {}
    target_journal_name = _first_entity_value(entity_data, _JOURNAL_NAME_KEYS)
    requested_source_id = _first_entity_value(entity_data, _RULE_SOURCE_KEYS)

    issues: list[JournalRuleSourceIssue] = []
    if requested_source_id:
        try:
            source = get_journal_rule_source(requested_source_id)
        except KeyError:
            source = None
            issues.append(
                JournalRuleSourceIssue(
                    path="entity_data.journal_rule_source_id",
                    kind="unregistered_rule_source",
                    severity="error",
                    expected="reviewed journal rule source id",
                    observed=requested_source_id,
                    message=(
                        "Journal rule source is not registered as reviewed and "
                        "cannot be trusted for target-journal compliance."
                    ),
                )
            )
    else:
        source = journal_rule_source_for_count_profile(count_profile_id)
    if source is None:
        issues.append(
            JournalRuleSourceIssue(
                path="compliance_profile.count_profile_id",
                kind="unregistered_count_profile",
                severity="error",
                expected="CountProfile bound to a reviewed journal rule source",
                observed=count_profile_id,
                message=(
                    f"CountProfile '{count_profile_id}' is not bound to a "
                    "reviewed journal rule source."
                ),
            )
        )
        return _result_from_source(
            None,
            family_id=family_id or JOURNAL_FAMILY_ID,
            count_profile_id=count_profile_id,
            target_journal_name=target_journal_name,
            issues=tuple(issues),
        )

    if count_profile_id not in source.count_profile_ids:
        issues.append(
            JournalRuleSourceIssue(
                path="compliance_profile.count_profile_id",
                kind="count_profile_not_declared_by_source",
                severity="error",
                expected=", ".join(source.count_profile_ids),
                observed=count_profile_id,
                message=(
                    f"CountProfile '{count_profile_id}' is not declared by "
                    f"journal rule source '{source.source_id}'."
                ),
            )
        )
    if not source.is_reviewed:
        issues.append(
            JournalRuleSourceIssue(
                path=f"journal_rule_sources.{source.source_id}.review_status",
                kind="rule_source_not_reviewed",
                severity="error",
                expected="reviewed or reviewed_generic",
                observed=source.review_status,
                message="Journal rule source must be reviewed before execution.",
            )
        )
    return _result_from_source(
        source,
        family_id=family_id or source.family_id,
        count_profile_id=count_profile_id,
        target_journal_name=target_journal_name,
        issues=tuple(issues),
    )


def _result_from_source(
    source: JournalRuleSourceSpec | None,
    *,
    family_id: str,
    count_profile_id: str,
    target_journal_name: str,
    issues: tuple[JournalRuleSourceIssue, ...],
) -> JournalRuleSourceGovernanceResult:
    if source is None:
        summary = JournalRuleSourceSummary(
            target_journal_declared=bool(target_journal_name),
        )
        return JournalRuleSourceGovernanceResult(
            family_id=family_id,
            status=_status_for_issues(issues),
            count_profile_id=count_profile_id,
            target_journal_name=target_journal_name,
            summary=summary,
            issues=issues,
        )
    matched = int(count_profile_id in source.count_profile_ids)
    summary = JournalRuleSourceSummary(
        declared_count_profile_count=len(source.count_profile_ids),
        matched_count_profile_count=matched,
        reviewed_source_count=int(source.is_reviewed),
        generic_source_count=int(source.generic_profile),
        target_journal_declared=bool(target_journal_name),
    )
    return JournalRuleSourceGovernanceResult(
        family_id=family_id,
        status=_status_for_issues(issues),
        rule_source_id=source.source_id,
        rule_source_label=source.label,
        source_type=source.source_type,
        source_reference=source.source_reference,
        version=source.version,
        review_status=source.review_status,
        reviewed_by=source.reviewed_by,
        reviewed_on=source.reviewed_on,
        count_profile_id=count_profile_id,
        target_journal_name=target_journal_name,
        declared_count_profile_ids=source.count_profile_ids,
        include_scope_summary=source.include_scope_summary,
        exclude_scope_summary=source.exclude_scope_summary,
        boundary_notes=source.boundary_notes,
        summary=summary,
        issues=issues,
    )


def _status_for_issues(issues: tuple[JournalRuleSourceIssue, ...]) -> str:
    if any(issue.severity == "error" for issue in issues):
        return "error"
    if issues:
        return "warning"
    return "ok"


def _first_entity_value(entity_data: Mapping[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(entity_data.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _config_material_schema_ids(config) -> tuple[str, ...]:
    profile = getattr(config, "input_source_profile", None)
    if profile is None:
        return ()
    schema_ids = []
    primary = str(getattr(profile, "material_schema_id", "") or "").strip()
    if primary:
        schema_ids.append(primary)
    for schema_id in list(getattr(profile, "material_schema_ids", []) or []):
        normalized = str(schema_id or "").strip()
        if normalized:
            schema_ids.append(normalized)
    return resolve_material_schema_ids(schema_ids)


def _journal_family_for_schema_ids(schema_ids: tuple[str, ...]) -> str:
    for schema_id in schema_ids:
        try:
            schema = get_material_schema(schema_id)
        except KeyError:
            continue
        if schema.family == JOURNAL_FAMILY_ID:
            return JOURNAL_FAMILY_ID
    return ""


def _is_journal_config(
    config,
    *,
    schema_ids: tuple[str, ...],
    family_id: str,
) -> bool:
    if family_id == JOURNAL_FAMILY_ID:
        return True
    if any(schema_id in JOURNAL_SCHEMA_IDS for schema_id in schema_ids):
        return True
    compliance = getattr(config, "compliance_profile", None)
    profile_values = (
        getattr(compliance, "profile_id", ""),
        getattr(compliance, "rule_family", ""),
        getattr(compliance, "count_profile_id", ""),
    )
    return any("journal" in str(value or "").lower() for value in profile_values)


__all__ = [
    "JournalRuleSourceGovernanceResult",
    "JournalRuleSourceIssue",
    "JournalRuleSourceSummary",
    "inspect_journal_rule_source_governance",
]
