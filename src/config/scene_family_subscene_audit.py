"""Family-level subscene completeness audit for the scene matrix.

N2.158 audits the layer between top-level coverage packs and concrete request
cells.  A high-frequency matrix is incomplete if a planned family has no pack
landing, no natural request evidence, no fixture/manual-boundary evidence, or
no executable defaults/plugin boundary.  This module keeps those checks
separate from pack-level completeness so family omissions cannot hide behind a
healthy parent pack.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from src.config.material_schema_registry import MATERIAL_SCHEMA_MAP
from src.config.plugin_manual_gate import list_plugin_manual_gates
from src.config.scene_coverage_manifest import coverage_packs_for_family
from src.config.scene_family_application import (
    apply_planned_scene_family_defaults,
    planned_family_is_application_boundary_only,
)
from src.config.scene_family_registry import (
    PlannedSceneFamily,
    list_planned_scene_families,
)
from src.config.scene_request_cell_fixture_registry import (
    SceneRequestCellFixtureSpec,
    list_scene_request_cell_fixtures,
)
from src.config.scene_rule_source_governance import scene_rule_sources_for_family
from src.config.scene_sample_fixture_registry import (
    SceneSampleFixtureSpec,
    list_scene_sample_fixtures,
)
from src.config.scene import SceneWorkspace
from src.shared.engine.count_engine import COUNT_PROFILE_MAP


MIN_REQUEST_CELLS_BY_PRIORITY: dict[str, int] = {
    "P1": 2,
    "P1_CANDIDATE": 2,
    "P2": 1,
}


@dataclass(frozen=True, slots=True)
class SceneFamilySubsceneAuditIssue:
    family_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneFamilySubsceneAuditRow:
    family_id: str
    name: str
    priority: str
    intended_landing: str
    maturity_level: str
    pack_ids: tuple[str, ...]
    request_cell_sample_ids: tuple[str, ...]
    matched_request_cell_count: int
    direct_request_cell_count: int
    manual_boundary_request_cell_count: int
    ambiguous_request_cell_count: int
    family_proxy_gap_ids: tuple[str, ...]
    sample_fixture_ids: tuple[str, ...]
    manual_boundary_fixture_ids: tuple[str, ...]
    material_schema_ids: tuple[str, ...]
    count_profile_ids: tuple[str, ...]
    delivery_preset_ids: tuple[str, ...]
    workflow_archetype_ids: tuple[str, ...]
    ooxml_touchpoints: tuple[str, ...]
    rule_source_ids: tuple[str, ...]
    plugin_gate_ids: tuple[str, ...]
    has_application_defaults: bool
    application_default_delivery_preset_id: str
    plugin_boundary_only: bool
    required_closure_count: int
    boundary_count: int
    issue_ids: tuple[str, ...]
    warning_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        if self.issue_ids:
            return "needs_attention"
        if self.warning_ids:
            return "needs_depth"
        return "ready"

    @property
    def request_cell_count(self) -> int:
        return len(self.request_cell_sample_ids)

    @property
    def sample_fixture_count(self) -> int:
        return len(self.sample_fixture_ids)

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "name": self.name,
            "priority": self.priority,
            "intended_landing": self.intended_landing,
            "maturity_level": self.maturity_level,
            "pack_ids": list(self.pack_ids),
            "request_cell_count": self.request_cell_count,
            "request_cell_sample_ids": list(self.request_cell_sample_ids),
            "matched_request_cell_count": self.matched_request_cell_count,
            "direct_request_cell_count": self.direct_request_cell_count,
            "manual_boundary_request_cell_count": (
                self.manual_boundary_request_cell_count
            ),
            "ambiguous_request_cell_count": self.ambiguous_request_cell_count,
            "family_proxy_gap_ids": list(self.family_proxy_gap_ids),
            "sample_fixture_count": self.sample_fixture_count,
            "sample_fixture_ids": list(self.sample_fixture_ids),
            "manual_boundary_fixture_ids": list(self.manual_boundary_fixture_ids),
            "material_schema_ids": list(self.material_schema_ids),
            "count_profile_ids": list(self.count_profile_ids),
            "delivery_preset_ids": list(self.delivery_preset_ids),
            "workflow_archetype_ids": list(self.workflow_archetype_ids),
            "ooxml_touchpoints": list(self.ooxml_touchpoints),
            "rule_source_ids": list(self.rule_source_ids),
            "plugin_gate_ids": list(self.plugin_gate_ids),
            "has_application_defaults": self.has_application_defaults,
            "application_default_delivery_preset_id": (
                self.application_default_delivery_preset_id
            ),
            "plugin_boundary_only": self.plugin_boundary_only,
            "required_closure_count": self.required_closure_count,
            "boundary_count": self.boundary_count,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneFamilySubsceneAuditReport:
    rows: tuple[SceneFamilySubsceneAuditRow, ...]
    issues: tuple[SceneFamilySubsceneAuditIssue, ...]
    warnings: tuple[SceneFamilySubsceneAuditIssue, ...]
    family_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def family_count(self) -> int:
        return len(self.rows)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def request_cell_count(self) -> int:
        return sum(row.request_cell_count for row in self.rows)

    @property
    def direct_family_fixture_count(self) -> int:
        return sum(1 for row in self.rows if row.sample_fixture_ids)

    @property
    def manual_boundary_family_count(self) -> int:
        return sum(1 for row in self.rows if row.manual_boundary_request_cell_count)

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "family_filter": self.family_filter,
            "family_count": self.family_count,
            "issue_count": self.issue_count,
            "warning_count": self.warning_count,
            "request_cell_count": self.request_cell_count,
            "direct_family_fixture_count": self.direct_family_fixture_count,
            "manual_boundary_family_count": self.manual_boundary_family_count,
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
        }


def build_scene_family_subscene_audit_report(
    *,
    family_id: str = "",
) -> SceneFamilySubsceneAuditReport:
    normalized_family = str(family_id or "").strip()
    families = tuple(
        family
        for family in list_planned_scene_families()
        if not normalized_family or family.family_id == normalized_family
    )
    if normalized_family and not families:
        issue = SceneFamilySubsceneAuditIssue(
            family_id=normalized_family,
            kind="unknown_family",
            message=f"Unknown planned scene family: {normalized_family}",
        )
        return SceneFamilySubsceneAuditReport(
            rows=(),
            issues=(issue,),
            warnings=(),
            family_filter=normalized_family,
        )

    cells = list_scene_request_cell_fixtures()
    fixtures = list_scene_sample_fixtures()
    rows = tuple(_build_family_row(family, cells, fixtures) for family in families)
    row_issues = tuple(issue for row in rows for issue in _row_issues(row))
    issues = tuple(issue for issue in row_issues if issue.severity == "error")
    warnings = tuple(issue for issue in row_issues if issue.severity != "error")
    return SceneFamilySubsceneAuditReport(
        rows=rows,
        issues=issues,
        warnings=warnings,
        family_filter=normalized_family,
    )


def audit_scene_family_subscene_report(
    report: SceneFamilySubsceneAuditReport | None = None,
) -> tuple[SceneFamilySubsceneAuditIssue, ...]:
    current = report or build_scene_family_subscene_audit_report()
    return current.issues


def _build_family_row(
    family: PlannedSceneFamily,
    cells: tuple[SceneRequestCellFixtureSpec, ...],
    fixtures: tuple[SceneSampleFixtureSpec, ...],
) -> SceneFamilySubsceneAuditRow:
    family_cells = tuple(
        cell for cell in cells if family.family_id in cell.expected_family_ids
    )
    family_fixtures = tuple(
        fixture for fixture in fixtures if fixture.family_id == family.family_id
    )
    manual_boundary_cells = tuple(
        cell for cell in family_cells if cell.coverage_level == "manual_boundary_fixture"
    )
    manual_boundary_fixture_ids = _unique_values(
        fixture_id for cell in manual_boundary_cells for fixture_id in cell.fixture_ids
    )
    application = _application_result_for_family(family.family_id)
    plugin_boundary_only = planned_family_is_application_boundary_only(family.family_id)
    plugin_gate_ids = _plugin_gate_ids_for_family(family, family_cells)
    row = SceneFamilySubsceneAuditRow(
        family_id=family.family_id,
        name=family.name,
        priority=family.priority,
        intended_landing=family.intended_landing,
        maturity_level=family.maturity_level,
        pack_ids=tuple(pack.pack_id for pack in coverage_packs_for_family(family.family_id)),
        request_cell_sample_ids=tuple(cell.sample_id for cell in family_cells),
        matched_request_cell_count=sum(
            1 for cell in family_cells if cell.expected_status == "matched"
        ),
        direct_request_cell_count=sum(
            1 for cell in family_cells if cell.coverage_level == "direct_family_fixture"
        ),
        manual_boundary_request_cell_count=len(manual_boundary_cells),
        ambiguous_request_cell_count=sum(
            1 for cell in family_cells if cell.coverage_level == "ambiguous_fixture_set"
        ),
        family_proxy_gap_ids=_unique_values(
            gap_id for cell in family_cells for gap_id in cell.family_proxy_gap_ids
        ),
        sample_fixture_ids=tuple(fixture.fixture_id for fixture in family_fixtures),
        manual_boundary_fixture_ids=manual_boundary_fixture_ids,
        material_schema_ids=family.material_schema_ids,
        count_profile_ids=family.count_profiles,
        delivery_preset_ids=family.delivery_presets,
        workflow_archetype_ids=family.workflow_archetypes,
        ooxml_touchpoints=family.ooxml_touchpoints,
        rule_source_ids=tuple(
            source.source_id for source in scene_rule_sources_for_family(family.family_id)
        ),
        plugin_gate_ids=plugin_gate_ids,
        has_application_defaults=application.applied,
        application_default_delivery_preset_id=application.default_delivery_preset_id,
        plugin_boundary_only=plugin_boundary_only,
        required_closure_count=len(family.required_closures),
        boundary_count=len(family.boundaries),
        issue_ids=(),
        warning_ids=(),
    )
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    for issue in _row_issues(row):
        if issue.severity == "error":
            issue_ids.append(issue.kind)
        else:
            warning_ids.append(issue.kind)
    return replace(
        row,
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _row_issues(
    row: SceneFamilySubsceneAuditRow,
) -> tuple[SceneFamilySubsceneAuditIssue, ...]:
    issues: list[SceneFamilySubsceneAuditIssue] = []

    def append(kind: str, message: str, severity: str = "error") -> None:
        issues.append(
            SceneFamilySubsceneAuditIssue(
                family_id=row.family_id,
                kind=kind,
                message=message,
                severity=severity,
            )
        )

    if not row.pack_ids:
        append("missing_coverage_pack", "Family is not referenced by a coverage pack.")
    min_cells = MIN_REQUEST_CELLS_BY_PRIORITY.get(row.priority, 1)
    if row.request_cell_count < min_cells:
        append(
            "low_family_request_cell_depth",
            (
                f"Family has {row.request_cell_count} request cells; "
                f"priority {row.priority} requires at least {min_cells}."
            ),
        )
    if row.matched_request_cell_count <= 0:
        append("missing_matched_request_cell", "Family has no matched request cell.")
    has_evidence = bool(row.sample_fixture_ids or row.manual_boundary_fixture_ids)
    if not has_evidence:
        append(
            "missing_family_fixture_or_manual_boundary",
            "Family has no direct fixture or manual-boundary fixture evidence.",
        )
    if row.family_proxy_gap_ids and not row.manual_boundary_request_cell_count:
        append(
            "unresolved_family_proxy_gap",
            "Family proxy gaps are present outside an explicit manual boundary.",
        )
    if not row.has_application_defaults and not row.plugin_boundary_only:
        append(
            "missing_application_defaults",
            "Family has neither scene-family defaults nor plugin/manual-only boundary.",
        )
    if row.has_application_defaults and not row.application_default_delivery_preset_id:
        append(
            "missing_default_delivery_preset",
            "Applied family defaults did not declare a default delivery preset.",
        )
    if not row.delivery_preset_ids:
        append("missing_delivery_presets", "Family must declare delivery presets.")
    if not row.workflow_archetype_ids:
        append("missing_workflow_archetypes", "Family must declare workflows.")
    if not row.ooxml_touchpoints:
        append("missing_ooxml_touchpoints", "Family must declare OOXML touchpoints.")
    if row.required_closure_count <= 0:
        append("missing_required_closures", "Family must declare required closures.")
    if row.boundary_count <= 0:
        append("missing_boundaries", "Family must declare boundary statements.")
    for schema_id in row.material_schema_ids:
        if schema_id not in MATERIAL_SCHEMA_MAP:
            append(
                "unknown_material_schema",
                f"Unknown material schema declared by family: {schema_id}.",
            )
    for profile_id in row.count_profile_ids:
        if profile_id not in COUNT_PROFILE_MAP:
            append(
                "unknown_count_profile",
                f"Unknown count profile declared by family: {profile_id}.",
            )
    if row.plugin_boundary_only and not row.plugin_gate_ids:
        append(
            "missing_plugin_gate",
            "Plugin/manual-only family must be represented by at least one plugin gate.",
        )
    if (
        row.priority in {"P1", "P1_CANDIDATE"}
        and row.manual_boundary_request_cell_count
        and row.direct_request_cell_count <= 0
    ):
        append(
            "core_family_uses_manual_boundary",
            "P1/P1_CANDIDATE families should not rely on manual-boundary request cells.",
            severity="warning",
        )
    if row.priority == "P2" and not row.rule_source_ids:
        append(
            "missing_rule_source_governance",
            "P2 professional/boundary family should have rule-source governance.",
            severity="warning",
        )
    return tuple(issues)


def _application_result_for_family(family_id: str):
    scene = SceneWorkspace(scene_id=family_id, category=family_id)
    return apply_planned_scene_family_defaults(scene, family_id=family_id)


def _plugin_gate_ids_for_family(
    family: PlannedSceneFamily,
    cells: tuple[SceneRequestCellFixtureSpec, ...],
) -> tuple[str, ...]:
    gate_ids = [
        gate.gate_id
        for gate in list_plugin_manual_gates()
        if gate.pack_id in {pack.pack_id for pack in coverage_packs_for_family(family.family_id)}
    ]
    gate_ids.extend(gate_id for cell in cells for gate_id in cell.manual_gate_ids)
    return _unique_values(gate_ids)


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "MIN_REQUEST_CELLS_BY_PRIORITY",
    "SceneFamilySubsceneAuditIssue",
    "SceneFamilySubsceneAuditReport",
    "SceneFamilySubsceneAuditRow",
    "audit_scene_family_subscene_report",
    "build_scene_family_subscene_audit_report",
]
