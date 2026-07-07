"""Horizontal CountProfile audit for high-frequency scenes.

N2.170 keeps counting semantics from collapsing into a single word-count
toggle.  The audit links CountProfile rows to planned families, coverage packs,
rule-source governance, runtime consumers, and report surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.scene import SceneWorkspace
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_packs_for_family,
    list_scene_coverage_packs,
)
from src.config.scene_family_application import (
    apply_planned_scene_family_defaults,
    planned_family_is_application_boundary_only,
)
from src.config.scene_family_registry import (
    PlannedSceneFamily,
    list_planned_scene_families,
)
from src.config.scene_rule_source_governance import (
    audit_scene_rule_source_governance,
    scene_rule_sources_for_count_profile,
    scene_rule_sources_for_family,
    scene_rule_sources_for_pack,
)
from src.shared.engine.count_engine import (
    COUNT_PROFILE_MAP,
    CountProfile,
    list_count_profiles,
)


SCENE_COUNT_PROFILE_AUDIT_SOURCE_ID = "scene_count_profile_audit"

SCENE_COUNT_PROFILE_SOURCE_MARKERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "count_engine",
        "src/shared/engine/count_engine.py",
        ("class CountProfile", "count_document", "CountEngineResult"),
    ),
    (
        "count_profile_registry",
        "count_profiles/builtin.json",
        ("application_word_limits", "word_xml_full", "section_limits"),
    ),
    (
        "scene_family_registry",
        "src/config/scene_family_registry.py",
        ("PLANNED_SCENE_FAMILIES", "count_profiles"),
    ),
    (
        "scene_family_application",
        "src/config/scene_family_application.py",
        ("apply_planned_scene_family_defaults", "count_profile_id"),
    ),
    (
        "validation_runtime",
        "src/modules/validate/validation.py",
        ("context.count_result", "count_engine", "count_profile_id"),
    ),
    (
        "report_writer_count_evidence",
        "src/report_writer.py",
        ("_extract_count_result", "included_scopes", "profile_name"),
    ),
    (
        "scene_rule_source_governance",
        "src/config/scene_rule_source_governance.py",
        ("scene_rule_sources_for_count_profile", "count_profile_ids"),
    ),
)

COUNT_PROFILE_RUNTIME_CONSUMERS: tuple[str, ...] = (
    "ValidationModule",
    "CountEngine",
    "ChangeTracker",
    "JSON report",
    "Markdown report",
)

COUNT_PROFILE_REPORT_SURFACES: tuple[str, ...] = (
    "counts.profile_id",
    "counts.profile_name",
    "counts.profile_source",
    "counts.scope",
    "counts.included_scopes",
    "counts.excluded_scopes",
    "counts.primary_metrics",
    "counts.counts",
)


@dataclass(frozen=True, slots=True)
class SceneCountProfileIssue:
    scope_type: str
    scope_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneCountProfileSourceEvidence:
    source_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]
    status: str

    def to_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneCountProfileProfileRow:
    profile_id: str
    label: str
    status: str
    source: str
    scope: str
    included_scopes: tuple[str, ...]
    excluded_scopes: tuple[str, ...]
    primary_metrics: tuple[str, ...]
    count_references: bool
    count_tables: bool
    count_figures: bool
    count_equations: bool
    section_limit_count: int
    family_ids: tuple[str, ...]
    pack_ids: tuple[str, ...]
    rule_source_ids: tuple[str, ...]
    note_count: int
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "label": self.label,
            "status": self.status,
            "source": self.source,
            "scope": self.scope,
            "included_scopes": list(self.included_scopes),
            "excluded_scopes": list(self.excluded_scopes),
            "primary_metrics": list(self.primary_metrics),
            "count_references": self.count_references,
            "count_tables": self.count_tables,
            "count_figures": self.count_figures,
            "count_equations": self.count_equations,
            "section_limit_count": self.section_limit_count,
            "family_ids": list(self.family_ids),
            "pack_ids": list(self.pack_ids),
            "rule_source_ids": list(self.rule_source_ids),
            "note_count": self.note_count,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneCountProfileFamilyRow:
    family_id: str
    name: str
    priority: str
    status: str
    pack_ids: tuple[str, ...]
    count_profile_ids: tuple[str, ...]
    registered_count_profile_ids: tuple[str, ...]
    missing_count_profile_ids: tuple[str, ...]
    executable_default_count_profile_id: str
    executable_default_in_declared_profiles: bool
    application_applied: bool
    plugin_boundary_only: bool
    scopes: tuple[str, ...]
    primary_metrics: tuple[str, ...]
    included_scopes: tuple[str, ...]
    excluded_scopes: tuple[str, ...]
    section_limit_count: int
    rule_source_ids: tuple[str, ...]
    rule_source_review_statuses: tuple[str, ...]
    manual_confirmation_required: bool
    report_surfaces: tuple[str, ...]
    runtime_consumers: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    @property
    def is_count_profile_family(self) -> bool:
        return bool(self.count_profile_ids)

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "count_profile_ids": list(self.count_profile_ids),
            "registered_count_profile_ids": list(self.registered_count_profile_ids),
            "missing_count_profile_ids": list(self.missing_count_profile_ids),
            "executable_default_count_profile_id": (
                self.executable_default_count_profile_id
            ),
            "executable_default_in_declared_profiles": (
                self.executable_default_in_declared_profiles
            ),
            "application_applied": self.application_applied,
            "plugin_boundary_only": self.plugin_boundary_only,
            "scopes": list(self.scopes),
            "primary_metrics": list(self.primary_metrics),
            "included_scopes": list(self.included_scopes),
            "excluded_scopes": list(self.excluded_scopes),
            "section_limit_count": self.section_limit_count,
            "rule_source_ids": list(self.rule_source_ids),
            "rule_source_review_statuses": list(self.rule_source_review_statuses),
            "manual_confirmation_required": self.manual_confirmation_required,
            "report_surfaces": list(self.report_surfaces),
            "runtime_consumers": list(self.runtime_consumers),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneCountProfilePackRow:
    pack_id: str
    label: str
    status: str
    count_profile_relevant: bool
    planned_family_ids: tuple[str, ...]
    count_profile_ids: tuple[str, ...]
    executable_default_count_profile_ids: tuple[str, ...]
    rule_source_ids: tuple[str, ...]
    manual_confirmation_required: bool
    plugin_boundary: bool
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "label": self.label,
            "status": self.status,
            "count_profile_relevant": self.count_profile_relevant,
            "planned_family_ids": list(self.planned_family_ids),
            "count_profile_ids": list(self.count_profile_ids),
            "executable_default_count_profile_ids": list(
                self.executable_default_count_profile_ids
            ),
            "rule_source_ids": list(self.rule_source_ids),
            "manual_confirmation_required": self.manual_confirmation_required,
            "plugin_boundary": self.plugin_boundary,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneCountProfileAuditReport:
    profile_rows: tuple[SceneCountProfileProfileRow, ...]
    family_rows: tuple[SceneCountProfileFamilyRow, ...]
    pack_rows: tuple[SceneCountProfilePackRow, ...]
    issues: tuple[SceneCountProfileIssue, ...]
    warnings: tuple[SceneCountProfileIssue, ...]
    source_evidence: tuple[SceneCountProfileSourceEvidence, ...]
    profile_filter: str = ""
    family_filter: str = ""
    pack_filter: str = ""
    total_family_count: int = 0

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def profile_count(self) -> int:
        return len(self.profile_rows)

    @property
    def family_count(self) -> int:
        return len(self.family_rows)

    @property
    def count_profile_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.is_count_profile_family)

    @property
    def ready_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.status == "ready")

    @property
    def boundary_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.status == "boundary")

    @property
    def accounted_family_count(self) -> int:
        return self.ready_family_count + self.boundary_family_count

    @property
    def pack_count(self) -> int:
        return len(self.pack_rows)

    @property
    def count_profile_pack_count(self) -> int:
        return sum(1 for row in self.pack_rows if row.count_profile_relevant)

    @property
    def ready_count_profile_pack_count(self) -> int:
        return sum(
            1
            for row in self.pack_rows
            if row.count_profile_relevant and row.status == "ready"
        )

    @property
    def referenced_profile_count(self) -> int:
        return len(
            _unique_values(
                profile_id
                for row in self.family_rows
                for profile_id in row.count_profile_ids
            )
        )

    @property
    def rule_source_profile_count(self) -> int:
        return sum(1 for row in self.profile_rows if row.rule_source_ids)

    @property
    def registry_only_profile_count(self) -> int:
        return sum(1 for row in self.profile_rows if row.status == "registry_only")

    @property
    def rule_source_only_profile_count(self) -> int:
        return sum(1 for row in self.profile_rows if row.status == "rule_source_only")

    @property
    def section_limit_profile_count(self) -> int:
        return sum(1 for row in self.profile_rows if row.section_limit_count)

    @property
    def unique_scope_count(self) -> int:
        return len(_unique_values(row.scope for row in self.profile_rows))

    @property
    def unique_primary_metric_count(self) -> int:
        return len(
            _unique_values(
                metric
                for row in self.profile_rows
                for metric in row.primary_metrics
            )
        )

    @property
    def runtime_consumer_count(self) -> int:
        return len(COUNT_PROFILE_RUNTIME_CONSUMERS)

    @property
    def report_surface_count(self) -> int:
        return len(COUNT_PROFILE_REPORT_SURFACES)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_COUNT_PROFILE_AUDIT_SOURCE_ID,
            "profile_filter": self.profile_filter,
            "family_filter": self.family_filter,
            "pack_filter": self.pack_filter,
            "counts": {
                "profile_count": self.profile_count,
                "referenced_profile_count": self.referenced_profile_count,
                "rule_source_profile_count": self.rule_source_profile_count,
                "registry_only_profile_count": self.registry_only_profile_count,
                "rule_source_only_profile_count": self.rule_source_only_profile_count,
                "section_limit_profile_count": self.section_limit_profile_count,
                "unique_scope_count": self.unique_scope_count,
                "unique_primary_metric_count": self.unique_primary_metric_count,
                "family_count": self.family_count,
                "total_family_count": self.total_family_count,
                "count_profile_family_count": self.count_profile_family_count,
                "ready_family_count": self.ready_family_count,
                "boundary_family_count": self.boundary_family_count,
                "accounted_family_count": self.accounted_family_count,
                "pack_count": self.pack_count,
                "count_profile_pack_count": self.count_profile_pack_count,
                "ready_count_profile_pack_count": (
                    self.ready_count_profile_pack_count
                ),
                "runtime_consumer_count": self.runtime_consumer_count,
                "report_surface_count": self.report_surface_count,
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "profile_rows": [row.to_payload() for row in self.profile_rows],
            "family_rows": [row.to_payload() for row in self.family_rows],
            "pack_rows": [row.to_payload() for row in self.pack_rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_count_profile_audit_report(
    *,
    profile_id: str = "",
    family_id: str = "",
    pack_id: str = "",
    project_root: Path | str | None = None,
) -> SceneCountProfileAuditReport:
    normalized_profile = str(profile_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_pack = str(pack_id or "").strip()

    families = list_planned_scene_families()
    packs = list_scene_coverage_packs()
    family_rows_all = tuple(_family_row(family) for family in families)
    pack_rows_all = tuple(_pack_row(pack, family_rows_all) for pack in packs)
    profile_rows_all = tuple(_profile_row(profile, family_rows_all) for profile in list_count_profiles())

    family_rows = _filter_family_rows(
        family_rows_all,
        profile_id=normalized_profile,
        family_id=normalized_family,
        pack_id=normalized_pack,
    )
    pack_rows = _filter_pack_rows(
        pack_rows_all,
        profile_id=normalized_profile,
        family_id=normalized_family,
        pack_id=normalized_pack,
    )
    profile_rows = _filter_profile_rows(
        profile_rows_all,
        profile_id=normalized_profile,
        family_id=normalized_family,
        pack_id=normalized_pack,
    )

    source_evidence = _source_evidence(project_root)
    issues, warnings = audit_scene_count_profile_report(
        SceneCountProfileAuditReport(
            profile_rows=profile_rows,
            family_rows=family_rows,
            pack_rows=pack_rows,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            profile_filter=normalized_profile,
            family_filter=normalized_family,
            pack_filter=normalized_pack,
            total_family_count=len(families),
        )
    )
    return SceneCountProfileAuditReport(
        profile_rows=profile_rows,
        family_rows=family_rows,
        pack_rows=pack_rows,
        issues=issues,
        warnings=warnings,
        source_evidence=source_evidence,
        profile_filter=normalized_profile,
        family_filter=normalized_family,
        pack_filter=normalized_pack,
        total_family_count=len(families),
    )


def audit_scene_count_profile_report(
    report: SceneCountProfileAuditReport,
) -> tuple[tuple[SceneCountProfileIssue, ...], tuple[SceneCountProfileIssue, ...]]:
    issues: list[SceneCountProfileIssue] = []
    warnings: list[SceneCountProfileIssue] = []

    for source_issue in audit_scene_rule_source_governance("."):
        issues.append(
            SceneCountProfileIssue(
                "rule_source",
                source_issue.source_id,
                source_issue.kind,
                f"Underlying rule source governance audit is not clean: {source_issue.message}",
            )
        )

    if not report.profile_rows:
        issues.append(
            SceneCountProfileIssue(
                "count_profile",
                "rows",
                "empty_profile_rows",
                "CountProfile audit must expose at least one profile row.",
            )
        )
    for row in report.profile_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneCountProfileIssue(
                    "count_profile",
                    row.profile_id,
                    issue_id,
                    f"CountProfile row has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneCountProfileIssue(
                    "count_profile",
                    row.profile_id,
                    warning_id,
                    f"CountProfile row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for row in report.family_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneCountProfileIssue(
                    "family",
                    row.family_id,
                    issue_id,
                    f"CountProfile family row has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneCountProfileIssue(
                    "family",
                    row.family_id,
                    warning_id,
                    f"CountProfile family row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for row in report.pack_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneCountProfileIssue(
                    "pack",
                    row.pack_id,
                    issue_id,
                    f"CountProfile pack row has unresolved issue: {issue_id}.",
                )
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneCountProfileIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    f"Missing source markers: {', '.join(evidence.missing_markers)}",
                )
            )
    return tuple(issues), tuple(warnings)


def _profile_row(
    profile: CountProfile,
    family_rows: tuple[SceneCountProfileFamilyRow, ...],
) -> SceneCountProfileProfileRow:
    family_ids = tuple(
        row.family_id for row in family_rows if profile.profile_id in row.count_profile_ids
    )
    pack_ids = _unique_values(
        pack_id
        for row in family_rows
        if profile.profile_id in row.count_profile_ids
        for pack_id in row.pack_ids
    )
    rule_sources = scene_rule_sources_for_count_profile(profile.profile_id)
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if not profile.scope:
        issue_ids.append("missing_scope")
    if not profile.primary_metrics:
        issue_ids.append("missing_primary_metrics")
    if not profile.included_scopes:
        issue_ids.append("missing_included_scopes")
    if not family_ids and not rule_sources:
        warning_ids.append("registry_only_profile")
    status = "family_backed"
    if not family_ids and rule_sources:
        status = "rule_source_only"
    elif not family_ids:
        status = "registry_only"
    return SceneCountProfileProfileRow(
        profile_id=profile.profile_id,
        label=profile.label,
        status=status,
        source=profile.source,
        scope=profile.scope,
        included_scopes=tuple(profile.included_scopes),
        excluded_scopes=tuple(profile.excluded_scopes),
        primary_metrics=tuple(profile.primary_metrics),
        count_references=profile.count_references,
        count_tables=profile.count_tables,
        count_figures=profile.count_figures,
        count_equations=profile.count_equations,
        section_limit_count=len(profile.section_limits),
        family_ids=family_ids,
        pack_ids=pack_ids,
        rule_source_ids=tuple(source.source_id for source in rule_sources),
        note_count=len(profile.notes),
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _family_row(family: PlannedSceneFamily) -> SceneCountProfileFamilyRow:
    profiles = tuple(
        COUNT_PROFILE_MAP[profile_id]
        for profile_id in family.count_profiles
        if profile_id in COUNT_PROFILE_MAP
    )
    registered_profile_ids = tuple(profile.profile_id for profile in profiles)
    missing_profile_ids = tuple(
        profile_id
        for profile_id in family.count_profiles
        if profile_id not in COUNT_PROFILE_MAP
    )
    default_profile_id, application_applied = _executable_default_profile_id(family.family_id)
    default_in_declared = (
        not default_profile_id or default_profile_id in family.count_profiles
    )
    rule_sources = scene_rule_sources_for_family(family.family_id)
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if family.count_profiles and missing_profile_ids:
        issue_ids.append("missing_registered_count_profile")
    if family.count_profiles and not registered_profile_ids:
        issue_ids.append("no_registered_count_profile")
    if default_profile_id and not default_in_declared:
        issue_ids.append("executable_default_not_declared")
    if not family.count_profiles:
        warning_ids.append("no_count_profile_declared")
    plugin_boundary_only = planned_family_is_application_boundary_only(family.family_id)
    if plugin_boundary_only:
        status = "boundary"
    elif issue_ids:
        status = "needs_attention"
    else:
        status = "ready"
    return SceneCountProfileFamilyRow(
        family_id=family.family_id,
        name=family.name,
        priority=family.priority,
        status=status,
        pack_ids=tuple(pack.pack_id for pack in coverage_packs_for_family(family.family_id)),
        count_profile_ids=tuple(family.count_profiles),
        registered_count_profile_ids=registered_profile_ids,
        missing_count_profile_ids=missing_profile_ids,
        executable_default_count_profile_id=default_profile_id,
        executable_default_in_declared_profiles=default_in_declared,
        application_applied=application_applied,
        plugin_boundary_only=plugin_boundary_only,
        scopes=_unique_values(profile.scope for profile in profiles),
        primary_metrics=_unique_values(
            metric for profile in profiles for metric in profile.primary_metrics
        ),
        included_scopes=_unique_values(
            scope for profile in profiles for scope in profile.included_scopes
        ),
        excluded_scopes=_unique_values(
            scope for profile in profiles for scope in profile.excluded_scopes
        ),
        section_limit_count=sum(len(profile.section_limits) for profile in profiles),
        rule_source_ids=tuple(source.source_id for source in rule_sources),
        rule_source_review_statuses=_unique_values(
            source.review_status for source in rule_sources
        ),
        manual_confirmation_required=any(
            source.manual_confirmation_required for source in rule_sources
        ),
        report_surfaces=COUNT_PROFILE_REPORT_SURFACES if family.count_profiles else (),
        runtime_consumers=COUNT_PROFILE_RUNTIME_CONSUMERS if family.count_profiles else (),
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _pack_row(
    pack: SceneCoveragePack,
    family_rows: tuple[SceneCountProfileFamilyRow, ...],
) -> SceneCountProfilePackRow:
    families = tuple(
        row for row in family_rows if row.family_id in pack.planned_family_ids
    )
    profile_ids = _unique_values(
        profile_id for row in families for profile_id in row.count_profile_ids
    )
    default_profile_ids = _unique_values(
        row.executable_default_count_profile_id
        for row in families
        if row.executable_default_count_profile_id
    )
    rule_sources = scene_rule_sources_for_pack(pack.pack_id)
    count_relevant = bool(profile_ids)
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if count_relevant and any(row.issue_ids for row in families):
        issue_ids.append("family_count_profile_issue")
    if count_relevant and not default_profile_ids:
        warning_ids.append("no_executable_default_count_profile")
    if not count_relevant and "count_profile" in pack.capability_axis_ids:
        issue_ids.append("missing_count_profile_for_count_axis")
    if issue_ids:
        status = "needs_attention"
    elif count_relevant:
        status = "ready"
    elif pack.plugin_boundary and "count_profile" in pack.capability_axis_ids:
        status = "boundary"
    else:
        status = "not_applicable"
    return SceneCountProfilePackRow(
        pack_id=pack.pack_id,
        label=pack.label,
        status=status,
        count_profile_relevant=count_relevant,
        planned_family_ids=tuple(pack.planned_family_ids),
        count_profile_ids=profile_ids,
        executable_default_count_profile_ids=default_profile_ids,
        rule_source_ids=tuple(source.source_id for source in rule_sources),
        manual_confirmation_required=any(
            source.manual_confirmation_required for source in rule_sources
        ),
        plugin_boundary=pack.plugin_boundary,
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _executable_default_profile_id(family_id: str) -> tuple[str, bool]:
    scene = SceneWorkspace(scene_id=family_id, category=family_id)
    result = apply_planned_scene_family_defaults(scene, family_id=family_id)
    if not result.applied:
        return "", False
    profile_id = str(getattr(scene.compliance_profile, "count_profile_id", "") or "").strip()
    return profile_id, True


def _filter_profile_rows(
    rows: tuple[SceneCountProfileProfileRow, ...],
    *,
    profile_id: str,
    family_id: str,
    pack_id: str,
) -> tuple[SceneCountProfileProfileRow, ...]:
    return tuple(
        row
        for row in rows
        if (not profile_id or row.profile_id == profile_id)
        and (not family_id or family_id in row.family_ids)
        and (not pack_id or pack_id in row.pack_ids)
    )


def _filter_family_rows(
    rows: tuple[SceneCountProfileFamilyRow, ...],
    *,
    profile_id: str,
    family_id: str,
    pack_id: str,
) -> tuple[SceneCountProfileFamilyRow, ...]:
    return tuple(
        row
        for row in rows
        if (not profile_id or profile_id in row.count_profile_ids)
        and (not family_id or row.family_id == family_id)
        and (not pack_id or pack_id in row.pack_ids)
    )


def _filter_pack_rows(
    rows: tuple[SceneCountProfilePackRow, ...],
    *,
    profile_id: str,
    family_id: str,
    pack_id: str,
) -> tuple[SceneCountProfilePackRow, ...]:
    return tuple(
        row
        for row in rows
        if (not profile_id or profile_id in row.count_profile_ids)
        and (not family_id or family_id in row.planned_family_ids)
        and (not pack_id or row.pack_id == pack_id)
    )


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneCountProfileSourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    evidence: list[SceneCountProfileSourceEvidence] = []
    for source_id, source_path, markers in SCENE_COUNT_PROFILE_SOURCE_MARKERS:
        path = root / source_path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneCountProfileSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
                status="ready" if path.exists() and not missing else "missing",
            )
        )
    return tuple(evidence)


def _unique_values(values) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "COUNT_PROFILE_REPORT_SURFACES",
    "COUNT_PROFILE_RUNTIME_CONSUMERS",
    "SCENE_COUNT_PROFILE_AUDIT_SOURCE_ID",
    "SceneCountProfileAuditReport",
    "SceneCountProfileFamilyRow",
    "SceneCountProfileIssue",
    "SceneCountProfilePackRow",
    "SceneCountProfileProfileRow",
    "SceneCountProfileSourceEvidence",
    "audit_scene_count_profile_report",
    "build_scene_count_profile_audit_report",
]
