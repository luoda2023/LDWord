"""High-frequency scene completeness audit report.

This module aggregates the V27 lenses into a single exportable model.  It does
not make new scene promises; it shows which packs already have request-cell,
fixture, report-artifact, workflow, axis, and Word-risk evidence, and which
packs still need depth.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    list_scene_completeness_gates,
    list_scene_coverage_packs,
)
from src.config.scene_request_cell_fixture_registry import (
    REQUEST_CELL_COVERAGE_LEVELS,
    SceneRequestCellFixtureSpec,
    list_scene_request_cell_fixtures,
)
from src.config.scene_sample_fixture_registry import (
    SceneSampleFixtureSpec,
    scene_sample_fixtures_for_pack,
)


REQUEST_CELL_REPORT_ARTIFACT_NAME = "request_cell_report.md"
MIN_RECOMMENDED_MATCHED_REQUEST_CELLS_PER_PACK = 3


@dataclass(frozen=True, slots=True)
class SceneHighFrequencyCompletenessIssue:
    """One completeness audit issue or warning."""

    pack_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneHighFrequencyCompletenessPackRow:
    """One row in the high-frequency scene completeness audit."""

    pack_id: str
    label: str
    plugin_boundary: bool
    boundary: str
    primary_landings: tuple[str, ...]
    secondary_landings: tuple[str, ...]
    executable_scene_ids: tuple[str, ...]
    planned_family_ids: tuple[str, ...]
    capability_axis_ids: tuple[str, ...]
    workflow_archetype_ids: tuple[str, ...]
    word_risk_surface_ids: tuple[str, ...]
    completeness_gate_ids: tuple[str, ...]
    request_cell_count: int
    matched_request_cell_count: int
    ambiguous_request_cell_count: int
    manual_boundary_request_cell_count: int
    negative_request_cell_count: int
    request_cell_coverage_level_counts: tuple[tuple[str, int], ...]
    request_cell_sample_ids: tuple[str, ...]
    request_cell_fixture_ids: tuple[str, ...]
    request_cell_manual_gate_ids: tuple[str, ...]
    sample_fixture_count: int
    sample_fixture_ids: tuple[str, ...]
    sample_fixture_family_ids: tuple[str, ...]
    docx_surfaces: tuple[str, ...]
    expected_behaviors: tuple[str, ...]
    report_expectations: tuple[str, ...]
    sample_manual_gate_ids: tuple[str, ...]
    request_cell_report_artifact_name: str
    request_cell_report_anchor_count: int
    request_cell_report_anchor_sample_ids: tuple[str, ...]
    implemented_closure_count: int
    missing_closure_count: int
    missing_closures: tuple[str, ...]
    issue_ids: tuple[str, ...]
    warning_ids: tuple[str, ...]
    status: str

    @property
    def has_blocking_issues(self) -> bool:
        return bool(self.issue_ids)

    def to_payload(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "label": self.label,
            "plugin_boundary": self.plugin_boundary,
            "boundary": self.boundary,
            "primary_landings": list(self.primary_landings),
            "secondary_landings": list(self.secondary_landings),
            "executable_scene_ids": list(self.executable_scene_ids),
            "planned_family_ids": list(self.planned_family_ids),
            "capability_axis_ids": list(self.capability_axis_ids),
            "workflow_archetype_ids": list(self.workflow_archetype_ids),
            "word_risk_surface_ids": list(self.word_risk_surface_ids),
            "completeness_gate_ids": list(self.completeness_gate_ids),
            "request_cell_count": self.request_cell_count,
            "matched_request_cell_count": self.matched_request_cell_count,
            "ambiguous_request_cell_count": self.ambiguous_request_cell_count,
            "manual_boundary_request_cell_count": (
                self.manual_boundary_request_cell_count
            ),
            "negative_request_cell_count": self.negative_request_cell_count,
            "request_cell_coverage_level_counts": [
                {"coverage_level": level, "count": count}
                for level, count in self.request_cell_coverage_level_counts
            ],
            "request_cell_sample_ids": list(self.request_cell_sample_ids),
            "request_cell_fixture_ids": list(self.request_cell_fixture_ids),
            "request_cell_manual_gate_ids": list(self.request_cell_manual_gate_ids),
            "sample_fixture_count": self.sample_fixture_count,
            "sample_fixture_ids": list(self.sample_fixture_ids),
            "sample_fixture_family_ids": list(self.sample_fixture_family_ids),
            "docx_surfaces": list(self.docx_surfaces),
            "expected_behaviors": list(self.expected_behaviors),
            "report_expectations": list(self.report_expectations),
            "sample_manual_gate_ids": list(self.sample_manual_gate_ids),
            "request_cell_report_artifact_name": (
                self.request_cell_report_artifact_name
            ),
            "request_cell_report_anchor_count": (
                self.request_cell_report_anchor_count
            ),
            "request_cell_report_anchor_sample_ids": list(
                self.request_cell_report_anchor_sample_ids
            ),
            "implemented_closure_count": self.implemented_closure_count,
            "missing_closure_count": self.missing_closure_count,
            "missing_closures": list(self.missing_closures),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneHighFrequencyCompletenessAuditReport:
    """Full high-frequency scene completeness audit report."""

    rows: tuple[SceneHighFrequencyCompletenessPackRow, ...]
    issues: tuple[SceneHighFrequencyCompletenessIssue, ...]
    warnings: tuple[SceneHighFrequencyCompletenessIssue, ...]
    pack_filter: str = ""

    @property
    def pack_count(self) -> int:
        return len(self.rows)

    @property
    def ready_pack_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def low_matched_request_pack_ids(self) -> tuple[str, ...]:
        return tuple(
            row.pack_id
            for row in self.rows
            if row.matched_request_cell_count
            < MIN_RECOMMENDED_MATCHED_REQUEST_CELLS_PER_PACK
        )

    def to_payload(self) -> dict[str, object]:
        if self.pack_filter:
            unique_request_cell_sample_ids = _unique_values(
                sample_id
                for row in self.rows
                for sample_id in row.request_cell_sample_ids
            )
            unassigned_request_cell_count = 0
        else:
            all_cells = list_scene_request_cell_fixtures()
            unique_request_cell_sample_ids = tuple(
                cell.sample_id for cell in all_cells
            )
            unassigned_request_cell_count = sum(
                1 for cell in all_cells if not cell.expected_pack_ids
            )
        unique_report_anchor_sample_ids = unique_request_cell_sample_ids
        coverage_counts = Counter(
            level
            for row in self.rows
            for level, count in row.request_cell_coverage_level_counts
            for _ in range(count)
        )
        return {
            "status": self.status,
            "pack_filter": self.pack_filter,
            "pack_count": self.pack_count,
            "ready_pack_count": self.ready_pack_count,
            "issue_count": self.issue_count,
            "warning_count": self.warning_count,
            "counts": {
                "request_cell_count": len(unique_request_cell_sample_ids),
                "unassigned_request_cell_count": unassigned_request_cell_count,
                "request_cell_pack_link_count": sum(
                    row.request_cell_count for row in self.rows
                ),
                "sample_fixture_count": sum(
                    row.sample_fixture_count for row in self.rows
                ),
                "report_anchor_count": len(unique_report_anchor_sample_ids),
                "report_anchor_pack_link_count": sum(
                    row.request_cell_report_anchor_count for row in self.rows
                ),
                "plugin_boundary_pack_count": sum(
                    1 for row in self.rows if row.plugin_boundary
                ),
            },
            "coverage_level_counts": [
                {"coverage_level": level, "count": int(coverage_counts.get(level, 0))}
                for level in REQUEST_CELL_COVERAGE_LEVELS
                if coverage_counts.get(level, 0)
            ],
            "low_matched_request_pack_ids": list(
                self.low_matched_request_pack_ids
            ),
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "rows": [row.to_payload() for row in self.rows],
        }


def build_high_frequency_completeness_audit_report(
    *,
    pack_id: str = "",
) -> SceneHighFrequencyCompletenessAuditReport:
    """Build the exportable V27 high-frequency completeness audit report."""

    normalized_pack = str(pack_id or "").strip()
    packs = tuple(
        pack
        for pack in list_scene_coverage_packs()
        if not normalized_pack or pack.pack_id == normalized_pack
    )
    rows = tuple(_build_pack_row(pack) for pack in packs)
    issues = tuple(
        issue
        for row in rows
        for issue in _row_issues(row)
        if issue.severity == "error"
    )
    warnings = tuple(
        issue
        for row in rows
        for issue in _row_issues(row)
        if issue.severity != "error"
    )
    return SceneHighFrequencyCompletenessAuditReport(
        rows=rows,
        issues=issues,
        warnings=warnings,
        pack_filter=normalized_pack,
    )


def audit_high_frequency_completeness_report(
    report: SceneHighFrequencyCompletenessAuditReport | None = None,
) -> tuple[SceneHighFrequencyCompletenessIssue, ...]:
    """Return blocking completeness-audit issues for release gates."""

    current = report or build_high_frequency_completeness_audit_report()
    return current.issues


def _build_pack_row(
    pack: SceneCoveragePack,
) -> SceneHighFrequencyCompletenessPackRow:
    cells = tuple(
        cell
        for cell in list_scene_request_cell_fixtures()
        if pack.pack_id in cell.expected_pack_ids
    )
    fixtures = scene_sample_fixtures_for_pack(pack.pack_id)
    coverage_counts = Counter(cell.coverage_level for cell in cells)
    matched_count = sum(1 for cell in cells if cell.expected_status == "matched")
    ambiguous_count = sum(1 for cell in cells if cell.expected_status == "ambiguous")
    manual_boundary_count = sum(
        1 for cell in cells if cell.coverage_level == "manual_boundary_fixture"
    )
    negative_count = sum(
        1 for cell in cells if cell.coverage_level == "negative_control"
    )
    report_anchor_sample_ids = tuple(cell.sample_id for cell in cells)
    issue_ids = _pack_issue_ids(pack, cells, fixtures, report_anchor_sample_ids)
    warning_ids = _pack_warning_ids(cells)
    return SceneHighFrequencyCompletenessPackRow(
        pack_id=pack.pack_id,
        label=pack.label,
        plugin_boundary=pack.plugin_boundary,
        boundary=pack.boundary,
        primary_landings=pack.primary_landings,
        secondary_landings=pack.secondary_landings,
        executable_scene_ids=pack.executable_scene_ids,
        planned_family_ids=pack.planned_family_ids,
        capability_axis_ids=pack.capability_axis_ids,
        workflow_archetype_ids=pack.workflow_archetype_ids,
        word_risk_surface_ids=pack.word_risk_surface_ids,
        completeness_gate_ids=pack.completeness_gate_ids,
        request_cell_count=len(cells),
        matched_request_cell_count=matched_count,
        ambiguous_request_cell_count=ambiguous_count,
        manual_boundary_request_cell_count=manual_boundary_count,
        negative_request_cell_count=negative_count,
        request_cell_coverage_level_counts=tuple(
            (level, int(coverage_counts.get(level, 0)))
            for level in REQUEST_CELL_COVERAGE_LEVELS
            if coverage_counts.get(level, 0)
        ),
        request_cell_sample_ids=tuple(cell.sample_id for cell in cells),
        request_cell_fixture_ids=_unique_values(
            fixture_id for cell in cells for fixture_id in cell.fixture_ids
        ),
        request_cell_manual_gate_ids=_unique_values(
            gate_id for cell in cells for gate_id in cell.manual_gate_ids
        ),
        sample_fixture_count=len(fixtures),
        sample_fixture_ids=tuple(fixture.fixture_id for fixture in fixtures),
        sample_fixture_family_ids=_unique_values(
            fixture.family_id for fixture in fixtures
        ),
        docx_surfaces=_unique_values(
            surface for fixture in fixtures for surface in fixture.docx_surfaces
        ),
        expected_behaviors=_unique_values(
            behavior
            for fixture in fixtures
            for behavior in fixture.expected_behaviors
        ),
        report_expectations=_unique_values(
            expectation
            for fixture in fixtures
            for expectation in fixture.report_expectations
        ),
        sample_manual_gate_ids=_unique_values(
            fixture.manual_gate_id for fixture in fixtures
        ),
        request_cell_report_artifact_name=REQUEST_CELL_REPORT_ARTIFACT_NAME,
        request_cell_report_anchor_count=len(report_anchor_sample_ids),
        request_cell_report_anchor_sample_ids=report_anchor_sample_ids,
        implemented_closure_count=len(pack.implemented_closures),
        missing_closure_count=len(pack.missing_closures),
        missing_closures=pack.missing_closures,
        issue_ids=issue_ids,
        warning_ids=warning_ids,
        status=_row_status(issue_ids, warning_ids),
    )


def _pack_issue_ids(
    pack: SceneCoveragePack,
    cells: Sequence[SceneRequestCellFixtureSpec],
    fixtures: Sequence[SceneSampleFixtureSpec],
    report_anchor_sample_ids: Sequence[str],
) -> tuple[str, ...]:
    issue_ids: list[str] = []
    if not pack.capability_axis_ids:
        issue_ids.append("missing_capability_axes")
    if not pack.workflow_archetype_ids:
        issue_ids.append("missing_workflow_archetypes")
    if not pack.word_risk_surface_ids:
        issue_ids.append("missing_word_risk_surfaces")
    if set(pack.completeness_gate_ids) != {
        gate.gate_id for gate in list_scene_completeness_gates()
    }:
        issue_ids.append("incomplete_gate_set")
    if not cells:
        issue_ids.append("missing_request_cells")
    if not fixtures:
        issue_ids.append("missing_sample_fixtures")
    if len(report_anchor_sample_ids) != len(cells):
        issue_ids.append("request_cell_report_anchor_mismatch")
    return tuple(issue_ids)


def _pack_warning_ids(
    cells: Sequence[SceneRequestCellFixtureSpec],
) -> tuple[str, ...]:
    matched_count = sum(1 for cell in cells if cell.expected_status == "matched")
    if matched_count < MIN_RECOMMENDED_MATCHED_REQUEST_CELLS_PER_PACK:
        return ("low_matched_request_cell_depth",)
    return ()


def _row_issues(
    row: SceneHighFrequencyCompletenessPackRow,
) -> tuple[SceneHighFrequencyCompletenessIssue, ...]:
    issues = [
        SceneHighFrequencyCompletenessIssue(
            pack_id=row.pack_id,
            kind=issue_id,
            message=_issue_message(issue_id, row),
        )
        for issue_id in row.issue_ids
    ]
    warnings = [
        SceneHighFrequencyCompletenessIssue(
            pack_id=row.pack_id,
            kind=warning_id,
            message=_issue_message(warning_id, row),
            severity="warning",
        )
        for warning_id in row.warning_ids
    ]
    return tuple([*issues, *warnings])


def _issue_message(
    issue_id: str,
    row: SceneHighFrequencyCompletenessPackRow,
) -> str:
    if issue_id == "low_matched_request_cell_depth":
        return (
            f"Pack '{row.pack_id}' has {row.matched_request_cell_count} matched "
            "request cells; V27 recommends at least "
            f"{MIN_RECOMMENDED_MATCHED_REQUEST_CELLS_PER_PACK}."
        )
    return f"Pack '{row.pack_id}' has completeness issue: {issue_id}."


def _row_status(
    issue_ids: Sequence[str],
    warning_ids: Sequence[str],
) -> str:
    if issue_ids:
        return "blocked"
    if warning_ids:
        return "needs_depth"
    return "ready"


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "MIN_RECOMMENDED_MATCHED_REQUEST_CELLS_PER_PACK",
    "REQUEST_CELL_REPORT_ARTIFACT_NAME",
    "SceneHighFrequencyCompletenessAuditReport",
    "SceneHighFrequencyCompletenessIssue",
    "SceneHighFrequencyCompletenessPackRow",
    "audit_high_frequency_completeness_report",
    "build_high_frequency_completeness_audit_report",
]
