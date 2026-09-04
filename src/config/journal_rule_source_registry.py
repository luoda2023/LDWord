"""Reviewed journal rule source registry.

The registry records which local journal rule/count profiles are allowed to
drive English journal checks. It is intentionally not a web fetcher: target
journal rules must be reviewed and versioned before they become executable.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.journal_rule_source_catalog import (
    JOURNAL_RULE_SOURCE_MAP,
    JOURNAL_RULE_SOURCE_SPECS,
    JournalRuleSourceSpec,
    get_journal_rule_source,
    journal_rule_source_for_count_profile,
    list_journal_rule_sources,
)
from src.shared.engine.count_engine import get_count_profile


@dataclass(frozen=True, slots=True)
class JournalRuleSourceRegistryIssue:
    """Static registry audit issue."""

    source_id: str
    kind: str
    message: str
    severity: str = "error"


def audit_journal_rule_source_registry() -> tuple[JournalRuleSourceRegistryIssue, ...]:
    issues: list[JournalRuleSourceRegistryIssue] = []
    seen: set[str] = set()
    for spec in JOURNAL_RULE_SOURCE_SPECS:
        if not spec.source_id:
            issues.append(
                JournalRuleSourceRegistryIssue(
                    source_id="",
                    kind="missing_source_id",
                    message="Journal rule source requires source_id.",
                )
            )
            continue
        if spec.source_id in seen:
            issues.append(
                JournalRuleSourceRegistryIssue(
                    source_id=spec.source_id,
                    kind="duplicate_source_id",
                    message=f"Duplicate journal rule source id: {spec.source_id}",
                )
            )
        seen.add(spec.source_id)
        if not spec.count_profile_ids:
            issues.append(
                JournalRuleSourceRegistryIssue(
                    source_id=spec.source_id,
                    kind="missing_count_profiles",
                    message="Journal rule source must bind at least one CountProfile.",
                )
            )
        for profile_id in spec.count_profile_ids:
            profile = get_count_profile(profile_id)
            if profile.profile_id != profile_id:
                issues.append(
                    JournalRuleSourceRegistryIssue(
                        source_id=spec.source_id,
                        kind="unknown_count_profile",
                        message=f"CountProfile '{profile_id}' is not registered.",
                    )
                )
        if spec.is_reviewed and (not spec.reviewed_by or not spec.reviewed_on):
            issues.append(
                JournalRuleSourceRegistryIssue(
                    source_id=spec.source_id,
                    kind="missing_review_metadata",
                    message="Reviewed journal rule source needs reviewer and date.",
                )
            )
        if not spec.source_reference:
            issues.append(
                JournalRuleSourceRegistryIssue(
                    source_id=spec.source_id,
                    kind="missing_source_reference",
                    message="Journal rule source needs source_reference.",
                )
            )
    return tuple(issues)


__all__ = [
    "JOURNAL_RULE_SOURCE_MAP",
    "JOURNAL_RULE_SOURCE_SPECS",
    "JournalRuleSourceRegistryIssue",
    "JournalRuleSourceSpec",
    "audit_journal_rule_source_registry",
    "get_journal_rule_source",
    "journal_rule_source_for_count_profile",
    "list_journal_rule_sources",
]
