"""High-frequency user-journey fixture audit for the scene matrix.

N2.173 upgrades request-cell and sample-fixture evidence from static coverage
to journey evidence.  The audit classifies the existing user requests into
success, degraded, failure, manual-boundary, ambiguous-decision, handoff, and
negative-control paths without claiming that every path is already a full
Green/L5 product journey.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_coverage_manifest import (
    SCENE_COVERAGE_PACK_MAP,
    list_scene_coverage_packs,
)
from src.config.scene_family_registry import (
    PLANNED_SCENE_FAMILIES,
    PLANNED_SCENE_FAMILY_MAP,
)
from src.config.scene_high_frequency_request_samples import (
    HighFrequencyRequestSample,
    list_high_frequency_request_samples,
)
from src.config.scene_request_cell_fixture_registry import (
    SceneRequestCellFixtureSpec,
    list_scene_request_cell_fixtures,
    request_cell_family_ids,
)
from src.config.scene_sample_fixture_registry import (
    SceneSampleFixtureSpec,
    list_scene_sample_fixtures,
)
from src.config.scene_source_evidence import scan_scene_source_markers


SCENE_USER_JOURNEY_FIXTURE_AUDIT_SOURCE_ID = "scene_user_journey_fixture_audit"

SCENE_USER_JOURNEY_PATH_TYPES: tuple[str, ...] = (
    "success",
    "degraded",
    "failure",
    "manual_boundary",
    "ambiguous_decision",
    "handoff",
    "negative_control",
)

SCENE_USER_JOURNEY_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "v38_plan",
        "docs/audits/高层场景能力矩阵V38完整产品能力矩阵与高频边界深化规划_2026-06-19.md",
        ("N2.173", "成功、降级、失败/人工门", "FixtureJourney"),
    ),
    (
        "request_cell_registry",
        "src/config/scene_request_cell_fixture_registry.py",
        ("manual_boundary_fixture", "ambiguous_fixture_set", "negative_control"),
    ),
    (
        "sample_fixture_registry",
        "src/config/scene_sample_fixture_registry.py",
        ("expected_behaviors", "skip_report", "block_report", "manual_confirmation"),
    ),
    (
        "high_frequency_request_samples",
        "src/config/scene_high_frequency_request_samples.py",
        ("expected_handoff_pack_ids", "disambiguation_required", "boundary_phrase"),
    ),
    (
        "maturity_upgrade",
        "src/config/scene_product_maturity_upgrade_audit.py",
        ("fixture_sample", "remaining_product_gaps", "l5_blocker_count"),
    ),
    (
        "dashboard_user_journey",
        "src/config/scene_matrix_dashboard.py",
        ("scene_user_journey_fixture_audit", "user_journey_path_count"),
    ),
    (
        "release_gate_user_journey",
        "scripts/verify_scene_matrix_release_gate.py",
        ("scene_user_journey_fixture_audit", "scene_user_journey_path_count"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneUserJourneyFixtureIssue:
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
class SceneUserJourneySourceEvidence:
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
class SceneUserJourneyPathRow:
    path_id: str
    journey_type: str
    status: str
    label: str
    request_cell_ids: tuple[str, ...]
    pack_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    manual_gate_ids: tuple[str, ...]
    expected_behaviors: tuple[str, ...]
    report_expectations: tuple[str, ...]
    coverage_levels: tuple[str, ...]
    source_ids: tuple[str, ...]
    boundary_notes: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "path_id": self.path_id,
            "journey_type": self.journey_type,
            "status": self.status,
            "label": self.label,
            "request_cell_ids": list(self.request_cell_ids),
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "fixture_ids": list(self.fixture_ids),
            "manual_gate_ids": list(self.manual_gate_ids),
            "expected_behaviors": list(self.expected_behaviors),
            "report_expectations": list(self.report_expectations),
            "coverage_levels": list(self.coverage_levels),
            "source_ids": list(self.source_ids),
            "boundary_notes": list(self.boundary_notes),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneUserJourneyPackRow:
    pack_id: str
    label: str
    status: str
    family_ids: tuple[str, ...]
    request_cell_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    manual_gate_ids: tuple[str, ...]
    path_type_ids: tuple[str, ...]
    required_path_type_ids: tuple[str, ...]
    missing_path_type_ids: tuple[str, ...]
    path_count: int
    success_path_count: int
    degraded_path_count: int
    failure_path_count: int
    manual_boundary_path_count: int
    ambiguous_decision_path_count: int
    handoff_path_count: int
    negative_control_path_count: int
    report_expectation_count: int
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "label": self.label,
            "status": self.status,
            "family_ids": list(self.family_ids),
            "request_cell_ids": list(self.request_cell_ids),
            "fixture_ids": list(self.fixture_ids),
            "manual_gate_ids": list(self.manual_gate_ids),
            "path_type_ids": list(self.path_type_ids),
            "required_path_type_ids": list(self.required_path_type_ids),
            "missing_path_type_ids": list(self.missing_path_type_ids),
            "path_count": self.path_count,
            "success_path_count": self.success_path_count,
            "degraded_path_count": self.degraded_path_count,
            "failure_path_count": self.failure_path_count,
            "manual_boundary_path_count": self.manual_boundary_path_count,
            "ambiguous_decision_path_count": self.ambiguous_decision_path_count,
            "handoff_path_count": self.handoff_path_count,
            "negative_control_path_count": self.negative_control_path_count,
            "report_expectation_count": self.report_expectation_count,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneUserJourneyFamilyRow:
    family_id: str
    name: str
    priority: str
    status: str
    pack_ids: tuple[str, ...]
    request_cell_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    manual_gate_ids: tuple[str, ...]
    path_type_ids: tuple[str, ...]
    required_path_type_ids: tuple[str, ...]
    missing_path_type_ids: tuple[str, ...]
    path_count: int
    success_path_count: int
    degraded_path_count: int
    failure_path_count: int
    manual_boundary_path_count: int
    ambiguous_decision_path_count: int
    handoff_path_count: int
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "request_cell_ids": list(self.request_cell_ids),
            "fixture_ids": list(self.fixture_ids),
            "manual_gate_ids": list(self.manual_gate_ids),
            "path_type_ids": list(self.path_type_ids),
            "required_path_type_ids": list(self.required_path_type_ids),
            "missing_path_type_ids": list(self.missing_path_type_ids),
            "path_count": self.path_count,
            "success_path_count": self.success_path_count,
            "degraded_path_count": self.degraded_path_count,
            "failure_path_count": self.failure_path_count,
            "manual_boundary_path_count": self.manual_boundary_path_count,
            "ambiguous_decision_path_count": self.ambiguous_decision_path_count,
            "handoff_path_count": self.handoff_path_count,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneUserJourneyFixtureAuditReport:
    pack_rows: tuple[SceneUserJourneyPackRow, ...]
    family_rows: tuple[SceneUserJourneyFamilyRow, ...]
    path_rows: tuple[SceneUserJourneyPathRow, ...]
    issues: tuple[SceneUserJourneyFixtureIssue, ...]
    warnings: tuple[SceneUserJourneyFixtureIssue, ...]
    source_evidence: tuple[SceneUserJourneySourceEvidence, ...]
    pack_filter: str = ""
    family_filter: str = ""
    journey_type_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def pack_count(self) -> int:
        return len(self.pack_rows)

    @property
    def ready_pack_count(self) -> int:
        return sum(1 for row in self.pack_rows if row.status == "ready")

    @property
    def warning_pack_count(self) -> int:
        return sum(1 for row in self.pack_rows if row.status == "needs_depth")

    @property
    def family_count(self) -> int:
        return len(self.family_rows)

    @property
    def ready_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.status == "ready")

    @property
    def warning_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.status == "needs_depth")

    @property
    def p1_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.priority.startswith("P1"))

    @property
    def p1_ready_family_count(self) -> int:
        return sum(
            1
            for row in self.family_rows
            if row.priority.startswith("P1") and row.status == "ready"
        )

    @property
    def path_count(self) -> int:
        return len(self.path_rows)

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
        path_type_counts = Counter(row.journey_type for row in self.path_rows)
        pack_type_counts = {
            path_type: sum(
                1
                for row in self.pack_rows
                if path_type in row.path_type_ids
            )
            for path_type in SCENE_USER_JOURNEY_PATH_TYPES
        }
        return {
            "status": self.status,
            "source_id": SCENE_USER_JOURNEY_FIXTURE_AUDIT_SOURCE_ID,
            "pack_filter": self.pack_filter,
            "family_filter": self.family_filter,
            "journey_type_filter": self.journey_type_filter,
            "path_types": list(SCENE_USER_JOURNEY_PATH_TYPES),
            "counts": {
                "pack_count": self.pack_count,
                "ready_pack_count": self.ready_pack_count,
                "warning_pack_count": self.warning_pack_count,
                "family_count": self.family_count,
                "ready_family_count": self.ready_family_count,
                "warning_family_count": self.warning_family_count,
                "p1_family_count": self.p1_family_count,
                "p1_ready_family_count": self.p1_ready_family_count,
                "path_count": self.path_count,
                "success_path_count": int(path_type_counts.get("success", 0)),
                "degraded_path_count": int(path_type_counts.get("degraded", 0)),
                "failure_path_count": int(path_type_counts.get("failure", 0)),
                "manual_boundary_path_count": int(
                    path_type_counts.get("manual_boundary", 0)
                ),
                "ambiguous_decision_path_count": int(
                    path_type_counts.get("ambiguous_decision", 0)
                ),
                "handoff_path_count": int(path_type_counts.get("handoff", 0)),
                "negative_control_path_count": int(
                    path_type_counts.get("negative_control", 0)
                ),
                "success_pack_count": int(pack_type_counts.get("success", 0)),
                "degraded_pack_count": int(pack_type_counts.get("degraded", 0)),
                "failure_pack_count": int(pack_type_counts.get("failure", 0)),
                "manual_boundary_pack_count": int(
                    pack_type_counts.get("manual_boundary", 0)
                ),
                "ambiguous_decision_pack_count": int(
                    pack_type_counts.get("ambiguous_decision", 0)
                ),
                "handoff_pack_count": int(pack_type_counts.get("handoff", 0)),
                "negative_control_pack_count": int(
                    pack_type_counts.get("negative_control", 0)
                ),
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "path_type_counts": [
                {"journey_type": path_type, "count": int(path_type_counts.get(path_type, 0))}
                for path_type in SCENE_USER_JOURNEY_PATH_TYPES
                if path_type_counts.get(path_type, 0)
            ],
            "pack_rows": [row.to_payload() for row in self.pack_rows],
            "family_rows": [row.to_payload() for row in self.family_rows],
            "path_rows": [row.to_payload() for row in self.path_rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_user_journey_fixture_audit_report(
    *,
    pack_id: str = "",
    family_id: str = "",
    journey_type: str = "",
    project_root: Path | str | None = None,
) -> SceneUserJourneyFixtureAuditReport:
    normalized_pack = str(pack_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_type = str(journey_type or "").strip()

    samples = {sample.sample_id: sample for sample in list_high_frequency_request_samples()}
    fixtures = {fixture.fixture_id: fixture for fixture in list_scene_sample_fixtures()}
    request_cells = list_scene_request_cell_fixtures()
    all_path_rows = tuple(
        row
        for cell in request_cells
        for row in _path_rows_for_cell(
            cell,
            sample=samples[cell.sample_id],
            fixtures=fixtures,
        )
    )
    path_rows = tuple(
        row
        for row in all_path_rows
        if (not normalized_pack or normalized_pack in row.pack_ids)
        and (not normalized_family or normalized_family in row.family_ids)
        and (not normalized_type or row.journey_type == normalized_type)
    )
    pack_rows = tuple(
        _pack_row(pack_id, path_rows=all_path_rows, request_cells=request_cells, fixtures=fixtures)
        for pack_id in SCENE_COVERAGE_PACK_MAP
    )
    family_rows = tuple(
        _family_row(family.family_id, path_rows=all_path_rows, request_cells=request_cells)
        for family in PLANNED_SCENE_FAMILIES
    )
    if normalized_pack:
        pack_rows = tuple(row for row in pack_rows if row.pack_id == normalized_pack)
    if normalized_family:
        family_rows = tuple(
            row for row in family_rows if row.family_id == normalized_family
        )
        pack_rows = tuple(
            row for row in pack_rows if normalized_family in row.family_ids
        )
    if normalized_type:
        pack_rows = tuple(
            row for row in pack_rows if normalized_type in row.path_type_ids
        )
        family_rows = tuple(
            row for row in family_rows if normalized_type in row.path_type_ids
        )

    source_evidence = _source_evidence(project_root)
    issues, warnings = audit_scene_user_journey_fixture_report(
        SceneUserJourneyFixtureAuditReport(
            pack_rows=pack_rows,
            family_rows=family_rows,
            path_rows=path_rows,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            pack_filter=normalized_pack,
            family_filter=normalized_family,
            journey_type_filter=normalized_type,
        )
    )
    return SceneUserJourneyFixtureAuditReport(
        pack_rows=pack_rows,
        family_rows=family_rows,
        path_rows=path_rows,
        issues=issues,
        warnings=warnings,
        source_evidence=source_evidence,
        pack_filter=normalized_pack,
        family_filter=normalized_family,
        journey_type_filter=normalized_type,
    )


def audit_scene_user_journey_fixture_report(
    report: SceneUserJourneyFixtureAuditReport,
) -> tuple[
    tuple[SceneUserJourneyFixtureIssue, ...],
    tuple[SceneUserJourneyFixtureIssue, ...],
]:
    issues: list[SceneUserJourneyFixtureIssue] = []
    warnings: list[SceneUserJourneyFixtureIssue] = []
    if report.journey_type_filter and report.journey_type_filter not in (
        SCENE_USER_JOURNEY_PATH_TYPES
    ):
        issues.append(
            SceneUserJourneyFixtureIssue(
                "journey_type",
                report.journey_type_filter,
                "unknown_journey_type",
                f"Unknown user journey path type: {report.journey_type_filter}.",
            )
        )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneUserJourneyFixtureIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    f"Missing source markers: {', '.join(evidence.missing_markers)}",
                )
            )
    for row in report.path_rows:
        if row.journey_type not in SCENE_USER_JOURNEY_PATH_TYPES:
            issues.append(
                SceneUserJourneyFixtureIssue(
                    "path",
                    row.path_id,
                    "unknown_path_type",
                    f"Unknown path type: {row.journey_type}.",
                )
            )
        if row.issue_ids:
            issues.extend(
                SceneUserJourneyFixtureIssue(
                    "path",
                    row.path_id,
                    issue_id,
                    f"Journey path {row.path_id} has {issue_id}.",
                )
                for issue_id in row.issue_ids
            )
    for row in (*report.pack_rows, *report.family_rows):
        scope_type = "pack" if hasattr(row, "pack_id") else "family"
        scope_id = getattr(row, "pack_id", "") or getattr(row, "family_id", "")
        for issue_id in row.issue_ids:
            issues.append(
                SceneUserJourneyFixtureIssue(
                    scope_type,
                    scope_id,
                    issue_id,
                    f"{scope_type} {scope_id} has {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneUserJourneyFixtureIssue(
                    scope_type,
                    scope_id,
                    warning_id,
                    f"{scope_type} {scope_id} has {warning_id}.",
                    severity="warning",
                )
            )
    return tuple(issues), tuple(warnings)


def _path_rows_for_cell(
    cell: SceneRequestCellFixtureSpec,
    *,
    sample: HighFrequencyRequestSample,
    fixtures: dict[str, SceneSampleFixtureSpec],
) -> tuple[SceneUserJourneyPathRow, ...]:
    linked_fixtures = tuple(
        fixtures[fixture_id]
        for fixture_id in cell.fixture_ids
        if fixture_id in fixtures
    )
    fixture_behaviors = _unique_values(
        behavior for fixture in linked_fixtures for behavior in fixture.expected_behaviors
    )
    report_expectations = _unique_values(
        expectation
        for fixture in linked_fixtures
        for expectation in fixture.report_expectations
    )
    path_specs: list[tuple[str, str, tuple[str, ...]]] = []
    if cell.expected_status == "matched" and cell.fixture_ids and not cell.manual_gate_ids:
        path_specs.append(("success", "matched request with fixture evidence", ("request_cell", "sample_fixture")))
    if "skip_report" in fixture_behaviors or "preserve_layout" in fixture_behaviors:
        path_specs.append(("degraded", "module skip or preserve-layout behavior", ("sample_fixture", "report_expectation")))
    if "block_report" in fixture_behaviors:
        path_specs.append(("failure", "blocking behavior captured in fixture/report", ("sample_fixture", "object_preflight")))
    if cell.manual_gate_ids or cell.expected_plugin_gate_ids:
        path_specs.append(("manual_boundary", "manual/plugin confirmation path", ("request_cell", "plugin_manual_gate", "sample_fixture")))
    elif "manual_confirmation" in fixture_behaviors:
        path_specs.append(("manual_boundary", "manual confirmation path", ("request_cell", "sample_fixture", "manual_confirmation")))
    if cell.expected_status == "ambiguous":
        path_specs.append(("ambiguous_decision", "ambiguous request requires clarification", ("request_cell", "ambiguous_boundary")))
    if sample.expected_handoff_pack_ids or sample.expected_handoff_family_ids:
        path_specs.append(("handoff", "import/AI boundary hands off to target scene", ("request_cell", "import_handoff")))
    if cell.expected_status == "unmatched":
        path_specs.append(("negative_control", "negative request stays outside core scene matrix", ("request_cell", "negative_control")))

    if not path_specs:
        path_specs.append(("success", "matched request with route evidence", ("request_cell",)))

    rows: list[SceneUserJourneyPathRow] = []
    for journey_type, label, source_ids in path_specs:
        issue_ids: list[str] = []
        if journey_type not in {"negative_control"} and not cell.fixture_ids:
            issue_ids.append("missing_fixture_evidence")
        rows.append(
            SceneUserJourneyPathRow(
                path_id=f"{journey_type}:{cell.sample_id}",
                journey_type=journey_type,
                status="ready" if not issue_ids else "blocked",
                label=label,
                request_cell_ids=(cell.sample_id,),
                pack_ids=_unique_values(
                    (
                        *cell.expected_pack_ids,
                        *sample.expected_handoff_pack_ids,
                    )
                ),
                family_ids=_unique_values(
                    (
                        *request_cell_family_ids(cell),
                        *sample.expected_handoff_family_ids,
                    )
                ),
                fixture_ids=cell.fixture_ids,
                manual_gate_ids=_unique_values(
                    (*cell.manual_gate_ids, *cell.expected_plugin_gate_ids)
                ),
                expected_behaviors=fixture_behaviors,
                report_expectations=report_expectations,
                coverage_levels=(cell.coverage_level,),
                source_ids=source_ids,
                boundary_notes=_unique_values(
                    (*cell.boundary_notes, sample.boundary_phrase, sample.notes)
                ),
                issue_ids=tuple(issue_ids),
            )
        )
    return tuple(rows)


def _pack_row(
    pack_id: str,
    *,
    path_rows: Sequence[SceneUserJourneyPathRow],
    request_cells: Sequence[SceneRequestCellFixtureSpec],
    fixtures: dict[str, SceneSampleFixtureSpec],
) -> SceneUserJourneyPackRow:
    pack = SCENE_COVERAGE_PACK_MAP[pack_id]
    rows = tuple(row for row in path_rows if pack_id in row.pack_ids)
    pack_cells = tuple(cell for cell in request_cells if pack_id in cell.expected_pack_ids)
    fixture_ids = _unique_values(fixture_id for row in rows for fixture_id in row.fixture_ids)
    linked_fixtures = tuple(fixtures[fixture_id] for fixture_id in fixture_ids if fixture_id in fixtures)
    path_types = _ordered_path_types(row.journey_type for row in rows)
    required_types = _pack_required_path_types(pack_id, pack_cells, linked_fixtures)
    missing = tuple(path_type for path_type in required_types if path_type not in path_types)
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if pack_cells and not rows:
        issue_ids.append("missing_journey_paths")
    if missing:
        warning_ids.extend(f"missing_{path_type}_journey" for path_type in missing)
    status = "blocked" if issue_ids else ("needs_depth" if warning_ids else "ready")
    counts = Counter(row.journey_type for row in rows)
    return SceneUserJourneyPackRow(
        pack_id=pack.pack_id,
        label=pack.label,
        status=status,
        family_ids=pack.planned_family_ids,
        request_cell_ids=tuple(cell.sample_id for cell in pack_cells),
        fixture_ids=fixture_ids,
        manual_gate_ids=_unique_values(gate_id for row in rows for gate_id in row.manual_gate_ids),
        path_type_ids=path_types,
        required_path_type_ids=required_types,
        missing_path_type_ids=missing,
        path_count=len(rows),
        success_path_count=int(counts.get("success", 0)),
        degraded_path_count=int(counts.get("degraded", 0)),
        failure_path_count=int(counts.get("failure", 0)),
        manual_boundary_path_count=int(counts.get("manual_boundary", 0)),
        ambiguous_decision_path_count=int(counts.get("ambiguous_decision", 0)),
        handoff_path_count=int(counts.get("handoff", 0)),
        negative_control_path_count=int(counts.get("negative_control", 0)),
        report_expectation_count=len(
            _unique_values(
                expectation
                for row in rows
                for expectation in row.report_expectations
            )
        ),
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _family_row(
    family_id: str,
    *,
    path_rows: Sequence[SceneUserJourneyPathRow],
    request_cells: Sequence[SceneRequestCellFixtureSpec],
) -> SceneUserJourneyFamilyRow:
    family = PLANNED_SCENE_FAMILY_MAP[family_id]
    rows = tuple(row for row in path_rows if family_id in row.family_ids)
    family_cells = tuple(
        cell
        for cell in request_cells
        if family_id in request_cell_family_ids(cell)
    )
    path_types = _ordered_path_types(row.journey_type for row in rows)
    required_types = _family_required_path_types(family_id, family.priority)
    missing = tuple(path_type for path_type in required_types if path_type not in path_types)
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if family_cells and not rows:
        issue_ids.append("missing_family_journey_paths")
    if missing and family.priority.startswith("P1"):
        warning_ids.extend(f"missing_{path_type}_journey" for path_type in missing)
    status = "blocked" if issue_ids else ("needs_depth" if warning_ids else "ready")
    counts = Counter(row.journey_type for row in rows)
    return SceneUserJourneyFamilyRow(
        family_id=family.family_id,
        name=family.name,
        priority=family.priority,
        status=status,
        pack_ids=tuple(pack.pack_id for pack in list_scene_coverage_packs() if family_id in pack.planned_family_ids),
        request_cell_ids=tuple(cell.sample_id for cell in family_cells),
        fixture_ids=_unique_values(fixture_id for row in rows for fixture_id in row.fixture_ids),
        manual_gate_ids=_unique_values(gate_id for row in rows for gate_id in row.manual_gate_ids),
        path_type_ids=path_types,
        required_path_type_ids=required_types,
        missing_path_type_ids=missing,
        path_count=len(rows),
        success_path_count=int(counts.get("success", 0)),
        degraded_path_count=int(counts.get("degraded", 0)),
        failure_path_count=int(counts.get("failure", 0)),
        manual_boundary_path_count=int(counts.get("manual_boundary", 0)),
        ambiguous_decision_path_count=int(counts.get("ambiguous_decision", 0)),
        handoff_path_count=int(counts.get("handoff", 0)),
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _pack_required_path_types(
    pack_id: str,
    cells: Sequence[SceneRequestCellFixtureSpec],
    fixtures: Sequence[SceneSampleFixtureSpec],
) -> tuple[str, ...]:
    required: list[str] = []
    pack = SCENE_COVERAGE_PACK_MAP[pack_id]
    if pack_id != "import_ai_boundary" and not pack.plugin_boundary:
        required.append("success")
    if any(
        behavior in {"skip_report", "preserve_layout"}
        for fixture in fixtures
        for behavior in fixture.expected_behaviors
    ):
        required.append("degraded")
    else:
        required.append("degraded")
    if any(cell.manual_gate_ids or cell.expected_plugin_gate_ids for cell in cells):
        required.append("manual_boundary")
    elif any(
        "block_report" in fixture.expected_behaviors for fixture in fixtures
    ):
        required.append("failure")
    else:
        required.append("manual_boundary")
    if any(cell.expected_status == "ambiguous" for cell in cells):
        required.append("ambiguous_decision")
    if pack_id == "import_ai_boundary":
        required.extend(("failure", "handoff"))
    return _ordered_path_types(required)


def _family_required_path_types(
    family_id: str,
    priority: str,
) -> tuple[str, ...]:
    if not priority.startswith("P1"):
        return ()
    if family_id in {
        "finance_quote_documents",
        "ip_patent_documents",
        "bilingual_translation_documents",
        "regulated_disclosure_documents",
    }:
        return ("manual_boundary",)
    return ("success", "degraded", "manual_boundary")


def _ordered_path_types(values: Iterable[object]) -> tuple[str, ...]:
    normalized = set(str(value or "").strip() for value in values if str(value or "").strip())
    return tuple(path_type for path_type in SCENE_USER_JOURNEY_PATH_TYPES if path_type in normalized)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneUserJourneySourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    return tuple(
        SceneUserJourneySourceEvidence(
            source_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
            status=(
                "ready"
                if result.source_exists and not result.missing_markers
                else "missing"
            ),
        )
        for result in scan_scene_source_markers(
            root,
            SCENE_USER_JOURNEY_SOURCE_MARKERS,
        )
    )


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_USER_JOURNEY_FIXTURE_AUDIT_SOURCE_ID",
    "SCENE_USER_JOURNEY_PATH_TYPES",
    "SceneUserJourneyFamilyRow",
    "SceneUserJourneyFixtureAuditReport",
    "SceneUserJourneyFixtureIssue",
    "SceneUserJourneyPackRow",
    "SceneUserJourneyPathRow",
    "SceneUserJourneySourceEvidence",
    "audit_scene_user_journey_fixture_report",
    "build_scene_user_journey_fixture_audit_report",
]
