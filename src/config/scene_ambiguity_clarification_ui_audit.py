"""Ambiguity clarification UI audit for high-frequency scene requests.

N2.174 promotes ambiguous request-cell evidence into a front-end-facing
clarification contract.  The audit does not choose a route for the user; it
checks that each ambiguous boundary exposes a visible question, candidate
landings, decision-record fields, and report evidence.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_ambiguous_boundary_audit import (
    SceneAmbiguousBoundaryRow,
    build_scene_ambiguous_boundary_audit_report,
)
from src.config.scene_source_evidence import scan_scene_source_markers
from src.config.scene_natural_request_router import (
    natural_request_route_payload,
    route_natural_scene_request,
)


SCENE_AMBIGUITY_CLARIFICATION_UI_AUDIT_SOURCE_ID = (
    "scene_ambiguity_clarification_ui_audit"
)

SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_UI_SURFACES: tuple[str, ...] = (
    "scene_panel_request_cell_filter",
    "scene_panel_request_cell_tooltip",
    "router_payload",
    "request_cell_report",
    "dashboard_boundary_card",
    "drilldown_ambiguity_clarification",
)

SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_DECISION_FIELDS: tuple[str, ...] = (
    "sample_id",
    "request_text",
    "clarification_prompt",
    "candidate_route_ids",
    "candidate_pack_ids",
    "selected_route_id",
    "selected_pack_id",
    "selected_family_id",
    "rejected_route_ids",
    "decision_source",
)

SCENE_AMBIGUITY_CLARIFICATION_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "v38_plan",
        "docs/audits/高层场景能力矩阵V38完整产品能力矩阵与高频边界深化规划_2026-06-19.md",
        ("N2.174", "ambiguous request-cell", "候选落点"),
    ),
    (
        "ambiguous_boundary_audit",
        "src/config/scene_ambiguous_boundary_audit.py",
        ("disambiguation_prompt", "candidate_route_ids", "clarification_axis"),
    ),
    (
        "natural_request_router",
        "src/config/scene_natural_request_router.py",
        ("natural_request_route_payload", "candidate_route_ids", "disambiguation_prompt"),
    ),
    (
        "scene_panel_ui",
        "src/ui/panels/scene_summary_projection.py",
        ("需要先澄清", "候选资料包", "常见说法"),
    ),
    (
        "user_journey_fixture",
        "src/config/scene_user_journey_fixture_audit.py",
        ("ambiguous_decision", "SceneUserJourneyPathRow"),
    ),
    (
        "dashboard_ambiguity_clarification",
        "src/config/scene_matrix_dashboard.py",
        ("scene_ambiguity_clarification_ui_audit", "ambiguity_clarification_count"),
    ),
    (
        "release_gate_ambiguity_clarification",
        "scripts/verify_scene_matrix_release_gate.py",
        ("scene_ambiguity_clarification_ui_audit", "scene_ambiguity_clarification_count"),
    ),
    (
        "drilldown_ambiguity_clarification",
        "src/config/scene_matrix_drilldown_items.py",
        ("ambiguity_clarification", "scene_ambiguity_clarification_ui_audit"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneAmbiguityClarificationIssue:
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
class SceneAmbiguityClarificationSourceEvidence:
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
class SceneAmbiguityClarificationRow:
    clarification_id: str
    boundary_id: str
    sample_id: str
    request_text: str
    status: str
    clarification_axis: str
    clarification_prompt: str
    candidate_route_ids: tuple[str, ...]
    candidate_pack_ids: tuple[str, ...]
    candidate_family_ids: tuple[str, ...]
    candidate_labels: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    decision_record_fields: tuple[str, ...]
    report_anchor_id: str
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "clarification_id": self.clarification_id,
            "boundary_id": self.boundary_id,
            "sample_id": self.sample_id,
            "request_text": self.request_text,
            "status": self.status,
            "clarification_axis": self.clarification_axis,
            "clarification_prompt": self.clarification_prompt,
            "candidate_route_ids": list(self.candidate_route_ids),
            "candidate_pack_ids": list(self.candidate_pack_ids),
            "candidate_family_ids": list(self.candidate_family_ids),
            "candidate_labels": list(self.candidate_labels),
            "fixture_ids": list(self.fixture_ids),
            "ui_surface_ids": list(self.ui_surface_ids),
            "decision_record_fields": list(self.decision_record_fields),
            "report_anchor_id": self.report_anchor_id,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneAmbiguityClarificationAuditReport:
    rows: tuple[SceneAmbiguityClarificationRow, ...]
    issues: tuple[SceneAmbiguityClarificationIssue, ...]
    warnings: tuple[SceneAmbiguityClarificationIssue, ...]
    source_evidence: tuple[SceneAmbiguityClarificationSourceEvidence, ...]
    boundary_filter: str = ""
    pack_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def clarification_count(self) -> int:
        return len(self.rows)

    @property
    def ready_clarification_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def candidate_route_count(self) -> int:
        return len({route_id for row in self.rows for route_id in row.candidate_route_ids})

    @property
    def candidate_pack_count(self) -> int:
        return len({pack_id for row in self.rows for pack_id in row.candidate_pack_ids})

    @property
    def fixture_backed_count(self) -> int:
        return sum(1 for row in self.rows if row.fixture_ids)

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
            "source_id": SCENE_AMBIGUITY_CLARIFICATION_UI_AUDIT_SOURCE_ID,
            "boundary_filter": self.boundary_filter,
            "pack_filter": self.pack_filter,
            "required_ui_surfaces": list(
                SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_UI_SURFACES
            ),
            "required_decision_fields": list(
                SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_DECISION_FIELDS
            ),
            "counts": {
                "clarification_count": self.clarification_count,
                "ready_clarification_count": self.ready_clarification_count,
                "candidate_route_count": self.candidate_route_count,
                "candidate_pack_count": self.candidate_pack_count,
                "fixture_backed_count": self.fixture_backed_count,
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_ambiguity_clarification_ui_audit_report(
    *,
    boundary_id: str = "",
    pack_id: str = "",
    project_root: Path | str | None = None,
) -> SceneAmbiguityClarificationAuditReport:
    normalized_boundary = str(boundary_id or "").strip()
    normalized_pack = str(pack_id or "").strip()
    boundary_report = build_scene_ambiguous_boundary_audit_report(
        boundary_id=normalized_boundary,
        pack_id=normalized_pack,
        project_root=project_root,
    )
    rows = tuple(_clarification_row(row) for row in boundary_report.rows)
    source_evidence = _source_evidence(project_root)
    issues, warnings = audit_scene_ambiguity_clarification_ui_report(
        SceneAmbiguityClarificationAuditReport(
            rows=rows,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            boundary_filter=normalized_boundary,
            pack_filter=normalized_pack,
        )
    )
    return SceneAmbiguityClarificationAuditReport(
        rows=rows,
        issues=issues,
        warnings=warnings,
        source_evidence=source_evidence,
        boundary_filter=normalized_boundary,
        pack_filter=normalized_pack,
    )


def audit_scene_ambiguity_clarification_ui_report(
    report: SceneAmbiguityClarificationAuditReport,
) -> tuple[
    tuple[SceneAmbiguityClarificationIssue, ...],
    tuple[SceneAmbiguityClarificationIssue, ...],
]:
    issues: list[SceneAmbiguityClarificationIssue] = []
    warnings: list[SceneAmbiguityClarificationIssue] = []
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneAmbiguityClarificationIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    f"Missing source markers: {', '.join(evidence.missing_markers)}",
                )
            )
    for row in report.rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneAmbiguityClarificationIssue(
                    "clarification",
                    row.clarification_id,
                    issue_id,
                    f"Clarification {row.clarification_id} has {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneAmbiguityClarificationIssue(
                    "clarification",
                    row.clarification_id,
                    warning_id,
                    f"Clarification {row.clarification_id} has {warning_id}.",
                    severity="warning",
                )
            )
    return tuple(issues), tuple(warnings)


def _clarification_row(
    boundary_row: SceneAmbiguousBoundaryRow,
) -> SceneAmbiguityClarificationRow:
    route_result = route_natural_scene_request(boundary_row.phrase)
    route_payload = natural_request_route_payload(route_result)
    candidate_route_ids = _unique_values(route_payload.get("candidate_route_ids", ()))
    candidate_pack_ids = _unique_values(route_payload.get("candidate_pack_ids", ()))
    candidate_family_ids = _unique_values(
        match.route.family_id for match in route_result.matches if match.route.family_id
    )
    candidate_labels = _unique_values(match.route.label for match in route_result.matches)
    prompt = str(route_payload.get("disambiguation_prompt", "") or "").strip()
    ui_surface_ids = SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_UI_SURFACES
    decision_fields = SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_DECISION_FIELDS
    issue_ids: list[str] = []
    if route_result.status != "ambiguous":
        issue_ids.append("router_not_ambiguous")
    if not prompt:
        issue_ids.append("missing_clarification_prompt")
    if len(candidate_route_ids) < 2:
        issue_ids.append("missing_candidate_routes")
    if len(candidate_pack_ids) < 2:
        issue_ids.append("missing_candidate_packs")
    if not set(boundary_row.expected_route_ids).issubset(set(candidate_route_ids)):
        issue_ids.append("candidate_routes_do_not_cover_boundary")
    if not set(boundary_row.expected_pack_ids).issubset(set(candidate_pack_ids)):
        issue_ids.append("candidate_packs_do_not_cover_boundary")
    if not boundary_row.fixture_ids:
        issue_ids.append("missing_fixture_evidence")
    missing_surfaces = tuple(
        surface
        for surface in SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_UI_SURFACES
        if surface not in ui_surface_ids
    )
    if missing_surfaces:
        issue_ids.append("missing_ui_surface")
    missing_fields = tuple(
        field
        for field in SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_DECISION_FIELDS
        if field not in decision_fields
    )
    if missing_fields:
        issue_ids.append("missing_decision_record_fields")
    return SceneAmbiguityClarificationRow(
        clarification_id=f"clarify:{boundary_row.sample_id}",
        boundary_id=boundary_row.boundary_id,
        sample_id=boundary_row.sample_id,
        request_text=boundary_row.phrase,
        status="ready" if not issue_ids else "blocked",
        clarification_axis=boundary_row.clarification_axis,
        clarification_prompt=prompt,
        candidate_route_ids=candidate_route_ids,
        candidate_pack_ids=candidate_pack_ids,
        candidate_family_ids=candidate_family_ids,
        candidate_labels=candidate_labels,
        fixture_ids=boundary_row.fixture_ids,
        ui_surface_ids=ui_surface_ids,
        decision_record_fields=decision_fields,
        report_anchor_id=_request_cell_anchor(boundary_row.sample_id),
        issue_ids=tuple(issue_ids),
    )


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneAmbiguityClarificationSourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    return tuple(
        SceneAmbiguityClarificationSourceEvidence(
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
            SCENE_AMBIGUITY_CLARIFICATION_SOURCE_MARKERS,
        )
    )


def _request_cell_anchor(sample_id: str) -> str:
    normalized = "".join(
        char.lower() if char.isalnum() else "-"
        for char in str(sample_id or "").strip()
    ).strip("-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return f"request-cell-{normalized or 'unknown'}"


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_DECISION_FIELDS",
    "SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_UI_SURFACES",
    "SCENE_AMBIGUITY_CLARIFICATION_UI_AUDIT_SOURCE_ID",
    "SceneAmbiguityClarificationAuditReport",
    "SceneAmbiguityClarificationIssue",
    "SceneAmbiguityClarificationRow",
    "SceneAmbiguityClarificationSourceEvidence",
    "audit_scene_ambiguity_clarification_ui_report",
    "build_scene_ambiguity_clarification_ui_audit_report",
]
