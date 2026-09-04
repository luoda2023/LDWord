"""Cross-scene rule source governance registry.

This registry does not fetch or trust external rule sheets at runtime. It records
which high-frequency scene packs have a known rule source contract, whether that
source is reviewed, and when manual or plugin confirmation is still required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.journal_rule_source_catalog import get_journal_rule_source
from src.config.material_schema_registry import MATERIAL_SCHEMA_MAP
from src.config.plugin_manual_gate import plugin_manual_gate_for_pack
from src.config.scene_coverage_manifest import SCENE_COVERAGE_PACK_MAP
from src.config.scene_family_registry import PLANNED_SCENE_FAMILY_MAP
from src.shared.engine.count_engine import COUNT_PROFILE_MAP


RULE_SOURCE_REVIEW_STATUSES: tuple[str, ...] = (
    "reviewed",
    "reviewed_generic",
    "manual_required",
    "plugin_required",
)
RULE_SOURCE_TYPES: tuple[str, ...] = (
    "local_profile_default",
    "reviewed_generic_registry",
    "user_supplied_rule_sheet",
    "plugin_boundary",
)
REQUIRED_RULE_SOURCE_PACK_IDS: tuple[str, ...] = (
    "chinese_academic",
    "english_journal",
    "application_reports",
    "bidding_materials",
    "professional_disclosure",
)


@dataclass(frozen=True, slots=True)
class SceneRuleSourceSpec:
    """Planning contract for one pack/family rule source."""

    source_id: str
    label: str
    pack_id: str
    rule_domain: str
    source_type: str
    review_status: str
    version: str
    family_ids: tuple[str, ...] = ()
    count_profile_ids: tuple[str, ...] = ()
    material_schema_ids: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()
    source_urls: tuple[str, ...] = ()
    upstream_source_ids: tuple[str, ...] = ()
    reviewed_by: str = ""
    reviewed_on: str = ""
    manual_confirmation_required: bool = True
    plugin_gate_id: str = ""
    include_scope_summary: tuple[str, ...] = ()
    exclude_scope_summary: tuple[str, ...] = ()
    boundary_notes: tuple[str, ...] = ()
    evidence_markers: tuple[str, ...] = ()
    report_surfaces: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()

    @property
    def is_reviewed(self) -> bool:
        return self.review_status in {"reviewed", "reviewed_generic"}

    @property
    def is_strictly_executable(self) -> bool:
        return self.review_status == "reviewed" and not self.manual_confirmation_required

    def to_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "label": self.label,
            "pack_id": self.pack_id,
            "rule_domain": self.rule_domain,
            "source_type": self.source_type,
            "review_status": self.review_status,
            "version": self.version,
            "family_ids": list(self.family_ids),
            "count_profile_ids": list(self.count_profile_ids),
            "material_schema_ids": list(self.material_schema_ids),
            "source_references": list(self.source_references),
            "source_urls": list(self.source_urls),
            "upstream_source_ids": list(self.upstream_source_ids),
            "reviewed_by": self.reviewed_by,
            "reviewed_on": self.reviewed_on,
            "manual_confirmation_required": self.manual_confirmation_required,
            "plugin_gate_id": self.plugin_gate_id,
            "include_scope_summary": list(self.include_scope_summary),
            "exclude_scope_summary": list(self.exclude_scope_summary),
            "boundary_notes": list(self.boundary_notes),
            "evidence_markers": list(self.evidence_markers),
            "report_surfaces": list(self.report_surfaces),
            "next_actions": list(self.next_actions),
            "strictly_executable": self.is_strictly_executable,
        }


@dataclass(frozen=True, slots=True)
class SceneRuleSourceGovernanceIssue:
    """One static audit issue for scene rule source governance."""

    source_id: str
    kind: str
    message: str
    severity: str = "error"


SCENE_RULE_SOURCE_SPECS: tuple[SceneRuleSourceSpec, ...] = (
    SceneRuleSourceSpec(
        source_id="school_thesis_rule_defaults",
        label="School thesis rule defaults with manual school confirmation",
        pack_id="chinese_academic",
        rule_domain="school_thesis_rules",
        source_type="local_profile_default",
        review_status="manual_required",
        version="2026-06-18",
        family_ids=("thesis_cn",),
        count_profile_ids=("school_thesis", "thesis_cn"),
        material_schema_ids=("thesis_school_rule_context_v1",),
        source_references=(
            "count_profiles/builtin.json",
            "src/config/scene_family_registry.py",
            "src/config/material_schema_registry.py",
        ),
        include_scope_summary=(
            "Chinese thesis body, references, figures, tables, and equations are counted by local profiles.",
            "The school_thesis profile is the scene default for thesis checks.",
        ),
        exclude_scope_summary=(
            "The local school_thesis profile is not authoritative for every institution.",
            "School-specific exclusions must be provided as reviewed profile data before strict compliance.",
        ),
        boundary_notes=(
            "Use this source for first-pass thesis count evidence only.",
            "Manual confirmation is required whenever the user expects a named-school rule sheet.",
        ),
        evidence_markers=(
            "Scene default for thesis; exact school rules still need profile data.",
            "thesis_school_rule_context_v1",
            "section_classifier_decisions",
            "does not claim one school count profile is authoritative for every institution",
        ),
        report_surfaces=(
            "count report",
            "compliance report",
            "input-source validation summary",
            "scene overview school rule evidence",
            "section classifier confirmation report",
        ),
        next_actions=(
            "Add reviewed school-specific rule-sheet profiles with version and reviewer metadata.",
            "Add import/validation for user-supplied school rule sheets before strict compliance.",
        ),
    ),
    SceneRuleSourceSpec(
        source_id="journal_submission_reviewed_generic_rules",
        label="Reviewed generic English journal submission rules",
        pack_id="english_journal",
        rule_domain="journal_submission_rules",
        source_type="reviewed_generic_registry",
        review_status="reviewed_generic",
        version="2026-06-18",
        family_ids=("journal_en",),
        count_profile_ids=("journal_words", "journal_display_items"),
        material_schema_ids=("journal_submission_materials_v1",),
        source_references=(
            "src/config/journal_rule_source_catalog.py",
            "count_profiles/builtin.json",
        ),
        upstream_source_ids=("journal_en_default_rules",),
        reviewed_by="LDWord scene matrix",
        reviewed_on="2026-06-18",
        include_scope_summary=(
            "Main manuscript words and display items are covered by reviewed generic defaults.",
            "BibTeX/CSL and submission package evidence stay in the journal scene family.",
        ),
        exclude_scope_summary=(
            "Publisher-specific limits are not executable unless a reviewed source update exists.",
            "The generic profile does not promise publisher-final layout.",
        ),
        boundary_notes=(
            "This source reuses the existing journal-only reviewed registry.",
            "Manual confirmation remains required for target-journal compliance.",
        ),
        evidence_markers=(
            "journal_en_default_rules",
            "reviewed_generic",
        ),
        report_surfaces=("journal_rule_source_governance", "JSON report", "Markdown report"),
        next_actions=(
            "Promote target-journal profiles only after source review and version pinning.",
        ),
    ),
    SceneRuleSourceSpec(
        source_id="project_application_rule_defaults",
        label="Project application section-limit and attachment defaults",
        pack_id="application_reports",
        rule_domain="project_application_rules",
        source_type="local_profile_default",
        review_status="manual_required",
        version="2026-06-18",
        family_ids=("project_application",),
        count_profile_ids=("application_word_limits", "attachment_inventory"),
        material_schema_ids=("project_application_materials_v1",),
        source_references=(
            "count_profiles/builtin.json",
            "src/config/material_schema_registry.py",
            "src/config/scene_family_registry.py",
        ),
        include_scope_summary=(
            "Section-level word or character limits have first-pass defaults.",
            "Project, team, budget, and attachment metadata are represented by a material schema.",
        ),
        exclude_scope_summary=(
            "External submission-system rules are not inferred automatically.",
            "Attachment truthfulness and review scoring are outside core execution.",
        ),
        boundary_notes=(
            "Manual confirmation is required for named call-for-proposal or agency rule sheets.",
            "Reviewed application-specific rules should override local defaults.",
        ),
        evidence_markers=(
            "Section limits are first-pass defaults and should be overridden by reviewed application-specific rules when available.",
            "does not replace external submission systems",
        ),
        report_surfaces=("count report", "material package report", "delivery manifest"),
        next_actions=(
            "Add reviewed agency/project-specific rule source ids.",
            "Expose rule source choice beside project application count profile selection.",
        ),
    ),
    SceneRuleSourceSpec(
        source_id="procurement_bidding_rule_defaults",
        label="Procurement and bidding package rule defaults",
        pack_id="bidding_materials",
        rule_domain="procurement_bidding_rules",
        source_type="local_profile_default",
        review_status="manual_required",
        version="2026-06-18",
        family_ids=("qualification_archive_packages",),
        count_profile_ids=("bid_package", "attachment_inventory"),
        material_schema_ids=("bid_materials_v1", "qualification_archive_assets_v1"),
        source_references=(
            "count_profiles/builtin.json",
            "src/config/material_schema_registry.py",
            "src/config/scene_coverage_manifest.py",
        ),
        include_scope_summary=(
            "Bid body, tables, figures, certificates, licenses, and attachments are tracked as package content.",
            "Qualification archive directory rules are represented by schema and package paths.",
        ),
        exclude_scope_summary=(
            "Bid strategy, certificate authenticity, and legal validity are not judged by core execution.",
            "Procurement platform-specific rule sheets require manual confirmation.",
        ),
        boundary_notes=(
            "Use local defaults for package inventory and missing-item reports.",
            "Manual confirmation is required before claiming procurement-rule compliance.",
        ),
        evidence_markers=(
            "Bidding documents treat attachments and tables as package content.",
            "does not judge bid strategy or legal validity",
        ),
        report_surfaces=("material package report", "batch report", "archive manifest"),
        next_actions=(
            "Add reviewed procurement-platform rule sheets and expiration metadata.",
            "Separate bid body formatting rules from qualification archive inventory rules.",
        ),
    ),
    SceneRuleSourceSpec(
        source_id="professional_disclosure_boundary_rules",
        label="Professional disclosure and finance/IP/bilingual boundary rules",
        pack_id="professional_disclosure",
        rule_domain="regulated_disclosure_and_professional_rules",
        source_type="plugin_boundary",
        review_status="plugin_required",
        version="2026-06-18",
        family_ids=(
            "finance_quote_documents",
            "regulated_disclosure_documents",
            "ip_patent_documents",
            "bilingual_translation_documents",
        ),
        count_profile_ids=(
            "finance_attachment_inventory",
            "disclosure_section_inventory",
            "patent_section_inventory",
            "bilingual_parallel_text",
        ),
        material_schema_ids=(
            "finance_quote_fields_v1",
            "regulated_disclosure_materials_v1",
            "patent_document_fields_v1",
            "bilingual_terms_v1",
        ),
        source_references=(
            "src/config/plugin_manual_gate.py",
            "src/config/material_schema_registry.py",
            "count_profiles/builtin.json",
        ),
        plugin_gate_id="professional_disclosure_review_gate",
        include_scope_summary=(
            "Core can inventory sections, tables, attachments, comments, and archive packages.",
            "Professional review responsibility is represented by a plugin/manual gate.",
        ),
        exclude_scope_summary=(
            "Core does not decide audit, legal, patent, finance, disclosure, or translation-quality conclusions.",
            "Archive packages are evidence bundles, not compliance proof.",
        ),
        boundary_notes=(
            "Plugin or professional review is required before business-critical disclosure claims.",
            "Manual confirmation must state who owns the professional review.",
        ),
        evidence_markers=(
            "professional_disclosure_review_gate",
            "does not perform audit or assurance judgment",
        ),
        report_surfaces=("plugin boundary report", "archive manifest", "manual confirmation"),
        next_actions=(
            "Connect professional plugins when available.",
            "Keep core report wording limited to inventory, package, and boundary evidence.",
        ),
    ),
)

SCENE_RULE_SOURCE_MAP: dict[str, SceneRuleSourceSpec] = {
    spec.source_id: spec for spec in SCENE_RULE_SOURCE_SPECS
}


def list_scene_rule_sources() -> tuple[SceneRuleSourceSpec, ...]:
    return SCENE_RULE_SOURCE_SPECS


def get_scene_rule_source(source_id: str) -> SceneRuleSourceSpec:
    normalized = str(source_id or "").strip()
    try:
        return SCENE_RULE_SOURCE_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown scene rule source: {source_id}") from exc


def scene_rule_sources_for_pack(pack_id: str) -> tuple[SceneRuleSourceSpec, ...]:
    normalized = str(pack_id or "").strip()
    return tuple(spec for spec in SCENE_RULE_SOURCE_SPECS if spec.pack_id == normalized)


def scene_rule_sources_for_family(family_id: str) -> tuple[SceneRuleSourceSpec, ...]:
    normalized = str(family_id or "").strip()
    return tuple(
        spec for spec in SCENE_RULE_SOURCE_SPECS if normalized in spec.family_ids
    )


def scene_rule_sources_for_count_profile(
    count_profile_id: str,
) -> tuple[SceneRuleSourceSpec, ...]:
    normalized = str(count_profile_id or "").strip()
    return tuple(
        spec for spec in SCENE_RULE_SOURCE_SPECS if normalized in spec.count_profile_ids
    )


def scene_rule_source_payload_for_pack(pack_id: str) -> dict[str, object]:
    sources = scene_rule_sources_for_pack(pack_id)
    return {
        "pack_id": str(pack_id or "").strip(),
        "rule_source_count": len(sources),
        "manual_confirmation_required": any(
            source.manual_confirmation_required for source in sources
        ),
        "plugin_required": any(source.review_status == "plugin_required" for source in sources),
        "sources": [source.to_payload() for source in sources],
    }


def build_scene_rule_source_summary(source: SceneRuleSourceSpec) -> str:
    return (
        f"{source.source_id}: pack={source.pack_id}; "
        f"families={','.join(source.family_ids) or '-'}; "
        f"profiles={','.join(source.count_profile_ids) or '-'}; "
        f"review={source.review_status}; "
        f"manual={source.manual_confirmation_required}; "
        f"plugin_gate={source.plugin_gate_id or '-'}"
    )


def audit_scene_rule_source_governance(
    root: str | Path = ".",
) -> tuple[SceneRuleSourceGovernanceIssue, ...]:
    root_path = Path(root)
    issues: list[SceneRuleSourceGovernanceIssue] = []
    seen: set[str] = set()
    covered_packs: set[str] = set()
    for source in SCENE_RULE_SOURCE_SPECS:
        if not source.source_id:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id="",
                    kind="missing_source_id",
                    message="Scene rule source requires source_id.",
                )
            )
            continue
        if source.source_id in seen:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=source.source_id,
                    kind="duplicate_source_id",
                    message=f"Duplicate scene rule source id: {source.source_id}",
                )
            )
        seen.add(source.source_id)
        covered_packs.add(source.pack_id)
        issues.extend(_audit_one_scene_rule_source(source, root_path))
    for pack_id in REQUIRED_RULE_SOURCE_PACK_IDS:
        if pack_id not in covered_packs:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=pack_id,
                    kind="missing_required_pack_source",
                    message=f"Required pack '{pack_id}' has no rule source governance entry.",
                )
            )
    return tuple(issues)


def _audit_one_scene_rule_source(
    source: SceneRuleSourceSpec,
    root_path: Path,
) -> tuple[SceneRuleSourceGovernanceIssue, ...]:
    issues: list[SceneRuleSourceGovernanceIssue] = []
    if source.pack_id not in SCENE_COVERAGE_PACK_MAP:
        issues.append(
            SceneRuleSourceGovernanceIssue(
                source_id=source.source_id,
                kind="unknown_pack",
                message=f"Unknown scene coverage pack: {source.pack_id}",
            )
        )
    else:
        pack = SCENE_COVERAGE_PACK_MAP[source.pack_id]
        for family_id in source.family_ids:
            if family_id not in pack.planned_family_ids:
                issues.append(
                    SceneRuleSourceGovernanceIssue(
                        source_id=source.source_id,
                        kind="family_not_declared_by_pack",
                        message=(
                            f"Family '{family_id}' is not declared by pack "
                            f"'{source.pack_id}'."
                        ),
                    )
                )
    if source.source_type not in RULE_SOURCE_TYPES:
        issues.append(
            SceneRuleSourceGovernanceIssue(
                source_id=source.source_id,
                kind="invalid_source_type",
                message=f"Invalid rule source type: {source.source_type}",
            )
        )
    if source.review_status not in RULE_SOURCE_REVIEW_STATUSES:
        issues.append(
            SceneRuleSourceGovernanceIssue(
                source_id=source.source_id,
                kind="invalid_review_status",
                message=f"Invalid rule source review status: {source.review_status}",
            )
        )
    if not source.source_references and not source.source_urls:
        issues.append(
            SceneRuleSourceGovernanceIssue(
                source_id=source.source_id,
                kind="missing_source_reference",
                message="Scene rule source requires a local reference or source URL.",
            )
        )
    if source.is_reviewed and (not source.reviewed_by or not source.reviewed_on):
        issues.append(
            SceneRuleSourceGovernanceIssue(
                source_id=source.source_id,
                kind="missing_review_metadata",
                message="Reviewed rule source needs reviewed_by and reviewed_on.",
            )
        )
    if source.review_status in {"manual_required", "plugin_required", "reviewed_generic"}:
        if not source.manual_confirmation_required:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=source.source_id,
                    kind="missing_manual_confirmation",
                    message=(
                        f"Review status '{source.review_status}' requires manual confirmation."
                    ),
                )
            )
    for family_id in source.family_ids:
        if family_id not in PLANNED_SCENE_FAMILY_MAP:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=source.source_id,
                    kind="unknown_family",
                    message=f"Unknown planned scene family: {family_id}",
                )
            )
    for profile_id in source.count_profile_ids:
        if profile_id not in COUNT_PROFILE_MAP:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=source.source_id,
                    kind="unknown_count_profile",
                    message=f"Unknown CountProfile: {profile_id}",
                )
            )
    for schema_id in source.material_schema_ids:
        if schema_id not in MATERIAL_SCHEMA_MAP:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=source.source_id,
                    kind="unknown_material_schema",
                    message=f"Unknown MaterialSchema: {schema_id}",
                )
            )
    for upstream_source_id in source.upstream_source_ids:
        try:
            get_journal_rule_source(upstream_source_id)
        except KeyError:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=source.source_id,
                    kind="unknown_upstream_source",
                    message=f"Unknown upstream journal rule source: {upstream_source_id}",
                )
            )
    if source.plugin_gate_id:
        gate = plugin_manual_gate_for_pack(source.pack_id)
        if gate is None or gate.gate_id != source.plugin_gate_id:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=source.source_id,
                    kind="unknown_plugin_gate",
                    message=(
                        f"Plugin gate '{source.plugin_gate_id}' is not registered "
                        f"for pack '{source.pack_id}'."
                    ),
                )
            )
    issues.extend(_audit_source_references(source, root_path))
    return tuple(issues)


def _audit_source_references(
    source: SceneRuleSourceSpec,
    root_path: Path,
) -> tuple[SceneRuleSourceGovernanceIssue, ...]:
    issues: list[SceneRuleSourceGovernanceIssue] = []
    readable_texts: list[str] = []
    for reference in source.source_references:
        normalized = str(reference or "").strip()
        if not normalized:
            continue
        if "://" in normalized:
            continue
        path = root_path / normalized
        if not path.exists():
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=source.source_id,
                    kind="missing_source_reference_path",
                    message=f"Rule source reference path does not exist: {normalized}",
                )
            )
            continue
        if path.is_file():
            readable_texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    evidence_text = "\n".join(readable_texts)
    for marker in source.evidence_markers:
        if str(marker or "").strip() and marker not in evidence_text:
            issues.append(
                SceneRuleSourceGovernanceIssue(
                    source_id=source.source_id,
                    kind="missing_evidence_marker",
                    message=f"Evidence marker was not found in source references: {marker}",
                )
            )
    return tuple(issues)


__all__ = [
    "REQUIRED_RULE_SOURCE_PACK_IDS",
    "RULE_SOURCE_REVIEW_STATUSES",
    "RULE_SOURCE_TYPES",
    "SCENE_RULE_SOURCE_MAP",
    "SCENE_RULE_SOURCE_SPECS",
    "SceneRuleSourceGovernanceIssue",
    "SceneRuleSourceSpec",
    "audit_scene_rule_source_governance",
    "build_scene_rule_source_summary",
    "get_scene_rule_source",
    "list_scene_rule_sources",
    "scene_rule_source_payload_for_pack",
    "scene_rule_sources_for_count_profile",
    "scene_rule_sources_for_family",
    "scene_rule_sources_for_pack",
]
