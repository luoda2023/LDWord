"""Customer-runtime catalog of reviewed journal rule sources."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JournalRuleSourceSpec:
    """Reviewed source contract for one journal rule profile."""

    source_id: str
    label: str
    family_id: str = "journal_en"
    source_type: str = "curated_default"
    source_reference: str = ""
    version: str = ""
    review_status: str = "draft"
    reviewed_by: str = ""
    reviewed_on: str = ""
    count_profile_ids: tuple[str, ...] = ()
    rule_family_ids: tuple[str, ...] = ()
    generic_profile: bool = True
    include_scope_summary: tuple[str, ...] = ()
    exclude_scope_summary: tuple[str, ...] = ()
    boundary_notes: tuple[str, ...] = ()

    @property
    def is_reviewed(self) -> bool:
        return self.review_status in {"reviewed", "reviewed_generic"}

    def to_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "label": self.label,
            "family_id": self.family_id,
            "source_type": self.source_type,
            "source_reference": self.source_reference,
            "version": self.version,
            "review_status": self.review_status,
            "reviewed_by": self.reviewed_by,
            "reviewed_on": self.reviewed_on,
            "count_profile_ids": list(self.count_profile_ids),
            "rule_family_ids": list(self.rule_family_ids),
            "generic_profile": self.generic_profile,
            "include_scope_summary": list(self.include_scope_summary),
            "exclude_scope_summary": list(self.exclude_scope_summary),
            "boundary_notes": list(self.boundary_notes),
        }


JOURNAL_RULE_SOURCE_SPECS: tuple[JournalRuleSourceSpec, ...] = (
    JournalRuleSourceSpec(
        source_id="journal_en_default_rules",
        label="Reviewed generic English journal submission defaults",
        source_type="curated_default",
        source_reference="count_profiles/builtin.json",
        version="2026-06-18",
        review_status="reviewed_generic",
        reviewed_by="LDWord scene matrix",
        reviewed_on="2026-06-18",
        count_profile_ids=("journal_words", "journal_display_items"),
        rule_family_ids=("journal_en", "journal_submission", "journal_revision"),
        generic_profile=True,
        include_scope_summary=(
            "journal_words counts main body text",
            "journal_display_items tracks figure/table/equation inventory",
        ),
        exclude_scope_summary=(
            "journal_words excludes references and table text from text metrics",
            "journal_display_items excludes body text and references",
        ),
        boundary_notes=(
            "This reviewed generic profile is not a publisher-specific rule sheet.",
            "Target journal limits require a reviewed source update before strict compliance.",
            "Do not fetch or trust unreviewed journal rules at runtime.",
        ),
    ),
)

JOURNAL_RULE_SOURCE_MAP: dict[str, JournalRuleSourceSpec] = {
    spec.source_id: spec for spec in JOURNAL_RULE_SOURCE_SPECS
}


def list_journal_rule_sources() -> tuple[JournalRuleSourceSpec, ...]:
    return JOURNAL_RULE_SOURCE_SPECS


def get_journal_rule_source(source_id: str) -> JournalRuleSourceSpec:
    normalized = str(source_id or "").strip()
    try:
        return JOURNAL_RULE_SOURCE_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown journal rule source: {source_id}") from exc


def journal_rule_source_for_count_profile(
    count_profile_id: str,
) -> JournalRuleSourceSpec | None:
    normalized = str(count_profile_id or "").strip()
    if not normalized:
        return None
    for spec in JOURNAL_RULE_SOURCE_SPECS:
        if normalized in spec.count_profile_ids:
            return spec
    return None


__all__ = [
    "JOURNAL_RULE_SOURCE_MAP",
    "JOURNAL_RULE_SOURCE_SPECS",
    "JournalRuleSourceSpec",
    "get_journal_rule_source",
    "journal_rule_source_for_count_profile",
    "list_journal_rule_sources",
]
