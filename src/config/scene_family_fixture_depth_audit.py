"""Family fixture-depth audit for high-frequency scene families.

N2.164 promotes the existing family fixture evidence into its own release-gate
asset.  Pack fixtures are not enough for the high-level matrix: P1/P1 candidate
families need direct family fixture evidence, while professional boundary
families must at least have a manual-boundary fixture and plugin/manual gate
chain.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from src.config.scene_family_registry import (
    PlannedSceneFamily,
    list_planned_scene_families,
)
from src.config.scene_family_subscene_audit import (
    SceneFamilySubsceneAuditRow,
    build_scene_family_subscene_audit_report,
)
from src.config.scene_sample_fixture_registry import (
    SCENE_SAMPLE_FIXTURE_MAP,
    SceneSampleFixtureSpec,
)


N2_164_REQUIRED_PRIORITIES: tuple[str, ...] = ("P1", "P1_CANDIDATE")

N2_164_SOURCE_EVIDENCE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "v30_plan",
        "docs/audits/高层场景能力矩阵V30完整场景能力矩阵与准入验收规划_2026-06-19.md",
        ("N2.164", "P1 family", "独立 fixture", "manual-boundary fixture"),
    ),
    (
        "sample_fixture_registry",
        "src/config/scene_sample_fixture_registry.py",
        ("SceneSampleFixtureSpec", "family_id", "SCENE_SAMPLE_FIXTURES"),
    ),
    (
        "family_subscene_audit",
        "src/config/scene_family_subscene_audit.py",
        (
            "direct_family_fixture_count",
            "manual_boundary_fixture_ids",
            "missing_family_fixture_or_manual_boundary",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        ("scene_family_fixture_depth_audit", "scene_family_fixture_depth_p1_family_count"),
    ),
    (
        "matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        ("scene_family_fixture_depth_audit", "family_fixture_depth_p1_ready_count"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneFamilyFixtureDepthIssue:
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
class SceneFamilyFixtureDepthSourceEvidence:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneFamilyFixtureDepthRow:
    family_id: str
    name: str
    priority: str
    required_priority: bool
    pack_ids: tuple[str, ...]
    request_cell_sample_ids: tuple[str, ...]
    direct_request_cell_count: int
    manual_boundary_request_cell_count: int
    independent_fixture_ids: tuple[str, ...]
    manual_boundary_fixture_ids: tuple[str, ...]
    fixture_strategy: str
    docx_surfaces: tuple[str, ...]
    expected_behaviors: tuple[str, ...]
    report_expectations: tuple[str, ...]
    plugin_gate_ids: tuple[str, ...]
    plugin_boundary_only: bool
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    @property
    def independent_fixture_count(self) -> int:
        return len(self.independent_fixture_ids)

    @property
    def manual_boundary_fixture_count(self) -> int:
        return len(self.manual_boundary_fixture_ids)

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "name": self.name,
            "priority": self.priority,
            "required_priority": self.required_priority,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "request_cell_sample_ids": list(self.request_cell_sample_ids),
            "direct_request_cell_count": self.direct_request_cell_count,
            "manual_boundary_request_cell_count": (
                self.manual_boundary_request_cell_count
            ),
            "independent_fixture_count": self.independent_fixture_count,
            "manual_boundary_fixture_count": self.manual_boundary_fixture_count,
            "independent_fixture_ids": list(self.independent_fixture_ids),
            "manual_boundary_fixture_ids": list(self.manual_boundary_fixture_ids),
            "fixture_strategy": self.fixture_strategy,
            "docx_surfaces": list(self.docx_surfaces),
            "expected_behaviors": list(self.expected_behaviors),
            "report_expectations": list(self.report_expectations),
            "plugin_gate_ids": list(self.plugin_gate_ids),
            "plugin_boundary_only": self.plugin_boundary_only,
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneFamilyFixtureDepthAuditReport:
    rows: tuple[SceneFamilyFixtureDepthRow, ...]
    issues: tuple[SceneFamilyFixtureDepthIssue, ...]
    source_evidence: tuple[SceneFamilyFixtureDepthSourceEvidence, ...]
    family_filter: str = ""
    priority_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def family_count(self) -> int:
        return len(self.rows)

    @property
    def p1_family_count(self) -> int:
        return sum(1 for row in self.rows if row.required_priority)

    @property
    def p1_ready_count(self) -> int:
        return sum(
            1 for row in self.rows if row.required_priority and row.status == "ready"
        )

    @property
    def independent_family_fixture_count(self) -> int:
        return sum(1 for row in self.rows if row.independent_fixture_ids)

    @property
    def manual_boundary_fixture_family_count(self) -> int:
        return sum(1 for row in self.rows if row.manual_boundary_fixture_ids)

    @property
    def independent_fixture_count(self) -> int:
        return len(
            {
                fixture_id
                for row in self.rows
                for fixture_id in row.independent_fixture_ids
            }
        )

    @property
    def manual_boundary_fixture_count(self) -> int:
        return len(
            {
                fixture_id
                for row in self.rows
                for fixture_id in row.manual_boundary_fixture_ids
            }
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.missing_markers)

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "family_filter": self.family_filter,
            "priority_filter": self.priority_filter,
            "counts": {
                "family_count": self.family_count,
                "p1_family_count": self.p1_family_count,
                "p1_ready_count": self.p1_ready_count,
                "independent_family_fixture_count": (
                    self.independent_family_fixture_count
                ),
                "manual_boundary_fixture_family_count": (
                    self.manual_boundary_fixture_family_count
                ),
                "independent_fixture_count": self.independent_fixture_count,
                "manual_boundary_fixture_count": (
                    self.manual_boundary_fixture_count
                ),
                "issue_count": self.issue_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "required_priorities": list(N2_164_REQUIRED_PRIORITIES),
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_family_fixture_depth_audit_report(
    *,
    family_id: str = "",
    priority: str = "",
    project_root: Path | str | None = None,
) -> SceneFamilyFixtureDepthAuditReport:
    normalized_family = str(family_id or "").strip()
    normalized_priority = str(priority or "").strip().upper()
    families = tuple(
        family
        for family in list_planned_scene_families()
        if (not normalized_family or family.family_id == normalized_family)
        and (not normalized_priority or family.priority.upper() == normalized_priority)
    )
    subscene_report = build_scene_family_subscene_audit_report()
    subscene_rows = {row.family_id: row for row in subscene_report.rows}
    rows: list[SceneFamilyFixtureDepthRow] = []
    issues: list[SceneFamilyFixtureDepthIssue] = []
    for family in families:
        subscene_row = subscene_rows.get(family.family_id)
        row, row_issues = _build_row(family, subscene_row)
        rows.append(row)
        issues.extend(row_issues)
    if normalized_family and not families:
        issues.append(
            SceneFamilyFixtureDepthIssue(
                normalized_family,
                "unknown_family",
                f"Unknown planned scene family: {normalized_family}.",
            )
        )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneFamilyFixtureDepthAuditReport(
        rows=tuple(rows),
        issues=tuple(issues),
        source_evidence=source_evidence,
        family_filter=normalized_family,
        priority_filter=normalized_priority,
    )


def audit_scene_family_fixture_depth_report(
    report: SceneFamilyFixtureDepthAuditReport | None = None,
) -> tuple[SceneFamilyFixtureDepthIssue, ...]:
    current = report or build_scene_family_fixture_depth_audit_report()
    return current.issues


def _build_row(
    family: PlannedSceneFamily,
    subscene_row: SceneFamilySubsceneAuditRow | None,
) -> tuple[SceneFamilyFixtureDepthRow, tuple[SceneFamilyFixtureDepthIssue, ...]]:
    required_priority = family.priority in N2_164_REQUIRED_PRIORITIES
    independent_fixture_ids = (
        subscene_row.sample_fixture_ids if subscene_row is not None else ()
    )
    manual_boundary_fixture_ids = (
        subscene_row.manual_boundary_fixture_ids if subscene_row is not None else ()
    )
    independent_fixtures = _fixture_specs(independent_fixture_ids)
    manual_boundary_fixtures = _fixture_specs(manual_boundary_fixture_ids)
    all_fixtures = (*independent_fixtures, *manual_boundary_fixtures)
    row = SceneFamilyFixtureDepthRow(
        family_id=family.family_id,
        name=family.name,
        priority=family.priority,
        required_priority=required_priority,
        pack_ids=subscene_row.pack_ids if subscene_row is not None else (),
        request_cell_sample_ids=(
            subscene_row.request_cell_sample_ids if subscene_row is not None else ()
        ),
        direct_request_cell_count=(
            subscene_row.direct_request_cell_count if subscene_row is not None else 0
        ),
        manual_boundary_request_cell_count=(
            subscene_row.manual_boundary_request_cell_count
            if subscene_row is not None
            else 0
        ),
        independent_fixture_ids=independent_fixture_ids,
        manual_boundary_fixture_ids=manual_boundary_fixture_ids,
        fixture_strategy=_fixture_strategy(
            independent_fixture_ids, manual_boundary_fixture_ids
        ),
        docx_surfaces=_unique_values(
            surface for fixture in all_fixtures for surface in fixture.docx_surfaces
        ),
        expected_behaviors=_unique_values(
            behavior
            for fixture in all_fixtures
            for behavior in fixture.expected_behaviors
        ),
        report_expectations=_unique_values(
            expectation
            for fixture in all_fixtures
            for expectation in fixture.report_expectations
        ),
        plugin_gate_ids=subscene_row.plugin_gate_ids if subscene_row is not None else (),
        plugin_boundary_only=(
            subscene_row.plugin_boundary_only if subscene_row is not None else False
        ),
        issue_ids=(),
    )
    issues = _row_issues(row, subscene_row)
    row = replace(row, issue_ids=tuple(issue.kind for issue in issues))
    return row, tuple(issues)


def _row_issues(
    row: SceneFamilyFixtureDepthRow,
    subscene_row: SceneFamilySubsceneAuditRow | None,
) -> tuple[SceneFamilyFixtureDepthIssue, ...]:
    issues: list[SceneFamilyFixtureDepthIssue] = []

    def add(kind: str, message: str) -> None:
        issues.append(SceneFamilyFixtureDepthIssue(row.family_id, kind, message))

    if subscene_row is None:
        add("missing_family_subscene_row", "Family is absent from subscene audit.")
        return tuple(issues)
    if row.required_priority and not row.independent_fixture_ids:
        add(
            "missing_p1_independent_family_fixture",
            "P1/P1_CANDIDATE family must have an independent family fixture.",
        )
    if not (row.independent_fixture_ids or row.manual_boundary_fixture_ids):
        add(
            "missing_fixture_or_manual_boundary",
            "Family must have independent fixture or manual-boundary fixture evidence.",
        )
    if row.required_priority and row.direct_request_cell_count <= 0:
        add(
            "missing_p1_direct_request_cell",
            "P1/P1_CANDIDATE family must have a direct fixture-backed request cell.",
        )
    if not row.docx_surfaces:
        add("missing_docx_surfaces", "Family fixture evidence has no DOCX surfaces.")
    if row.independent_fixture_ids and not row.report_expectations:
        add(
            "missing_report_expectations",
            "Independent family fixture must declare report expectations.",
        )
    if row.manual_boundary_fixture_ids and not row.manual_boundary_request_cell_count:
        add(
            "manual_fixture_without_manual_request_cell",
            "Manual-boundary fixture exists without a manual-boundary request cell.",
        )
    if row.manual_boundary_fixture_ids and not row.plugin_gate_ids:
        add(
            "manual_fixture_without_plugin_gate",
            "Manual-boundary fixture must be connected to a plugin/manual gate.",
        )
    return tuple(issues)


def _fixture_specs(fixture_ids: tuple[str, ...]) -> tuple[SceneSampleFixtureSpec, ...]:
    return tuple(
        SCENE_SAMPLE_FIXTURE_MAP[fixture_id]
        for fixture_id in fixture_ids
        if fixture_id in SCENE_SAMPLE_FIXTURE_MAP
    )


def _fixture_strategy(
    independent_fixture_ids: tuple[str, ...],
    manual_boundary_fixture_ids: tuple[str, ...],
) -> str:
    if independent_fixture_ids and manual_boundary_fixture_ids:
        return "independent_and_manual_boundary_fixture"
    if independent_fixture_ids:
        return "independent_family_fixture"
    if manual_boundary_fixture_ids:
        return "manual_boundary_fixture"
    return "missing_fixture_evidence"


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneFamilyFixtureDepthSourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneFamilyFixtureDepthSourceEvidence] = []
    for evidence_id, source_path, markers in N2_164_SOURCE_EVIDENCE:
        path = root / source_path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneFamilyFixtureDepthSourceEvidence(
                evidence_id=evidence_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneFamilyFixtureDepthSourceEvidence, ...],
) -> tuple[SceneFamilyFixtureDepthIssue, ...]:
    return tuple(
        SceneFamilyFixtureDepthIssue(
            evidence.evidence_id,
            "missing_source_evidence",
            (
                f"{evidence.source_path} missing markers: "
                f"{', '.join(evidence.missing_markers)}"
            ),
        )
        for evidence in source_evidence
        if evidence.missing_markers
    )


def _unique_values(values) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "N2_164_REQUIRED_PRIORITIES",
    "SceneFamilyFixtureDepthAuditReport",
    "SceneFamilyFixtureDepthIssue",
    "audit_scene_family_fixture_depth_report",
    "build_scene_family_fixture_depth_audit_report",
]
