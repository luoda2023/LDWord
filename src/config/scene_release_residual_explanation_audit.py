"""Release residual explanation coverage audit for the scene matrix.

N2.393i keeps allowed non-zero release-gate residual readings paired with
their governing readings and visible release summary markers.  The goal is not
to hide warnings, retained gaps, or boundary blockers; it is to prevent them
from reappearing as unexplained naked counters.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.scene_boundary_maturity_release_envelope_audit import (
    build_scene_boundary_maturity_release_envelope_audit_report,
)
from src.config.scene_count_profile_audit import build_scene_count_profile_audit_report
from src.config.scene_input_source_audit import build_scene_input_source_audit_report
from src.config.scene_product_maturity_upgrade_audit import (
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_product_readiness import static_closed_but_not_green_specs
from src.config.scene_release_residual_ratio_ledger_audit import (
    build_scene_release_residual_ratio_ledger_audit_report,
)
from src.config.scene_residual_warning_governance_audit import (
    build_scene_residual_warning_governance_audit_report,
)
from src.config.scene_source_evidence import (
    scan_scene_source_markers,
    scene_source_marker_issue_message,
)
from src.config.scene_terminal_release_exception_audit import (
    build_scene_terminal_release_exception_audit_report,
)


SCENE_RELEASE_RESIDUAL_EXPLANATION_AUDIT_SOURCE_ID = (
    "scene_release_residual_explanation_audit"
)


@dataclass(frozen=True, slots=True)
class SceneReleaseResidualExplanationSpec:
    residual_id: str
    label: str
    summary_marker: str
    reason: str


SCENE_RELEASE_RESIDUAL_EXPLANATION_SPECS: tuple[
    SceneReleaseResidualExplanationSpec, ...
] = (
    SceneReleaseResidualExplanationSpec(
        residual_id="managed_warnings",
        label="Managed warnings",
        summary_marker="managed_warnings=",
        reason="All residual warnings must be managed before release.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="input_warnings",
        label="Input source warnings",
        summary_marker="input_warnings=",
        reason="Input-source warnings must be plugin/manual or boundary managed.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="count_profile_warnings",
        label="CountProfile warnings",
        summary_marker="count_profile_warnings=",
        reason="CountProfile warnings must be reference-profile managed.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="plugin_manual_warnings",
        label="Plugin/manual warnings",
        summary_marker="plugin_manual_warnings=",
        reason="Plugin/manual warning subclasses must remain explicit.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="reference_profile_warnings",
        label="Reference profile warnings",
        summary_marker="reference_profile_warnings=",
        reason="Reference profile warning subclasses must remain explicit.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="visio_fixture",
        label="Visio fixture closure",
        summary_marker="visio_fixture=",
        reason="Visio fixture closure must be visible as a closed negative control.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="dashboard_warning_projection",
        label="Dashboard warning projection",
        summary_marker="dashboard_warning_projection=",
        reason="Dashboard warnings must be projections of governed source warnings.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="static_closed_not_green",
        label="Static-closed but not Green/L5",
        summary_marker="static_closed_not_green=",
        reason="Static-closed boundary subjects must not be overclaimed as Green/L5.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="maturity_l5_enveloped",
        label="Maturity L5 blockers",
        summary_marker="maturity_l5_enveloped=",
        reason="L5 blockers must be release-envelope governed.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="maturity_l5_alignment",
        label="Maturity L5 blocker alignment",
        summary_marker="maturity_l5_alignment=",
        reason="L5 blocker release envelopes must align with retained-gap exit criteria.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="retained_gaps",
        label="Retained gaps",
        summary_marker="retained_gaps=",
        reason="Retained gaps must be release-envelope governed.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="gap_domains",
        label="Gap domains",
        summary_marker="gap_domains=",
        reason="Gap domains must be classified, not exposed as unexplained gaps.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="count_delivery_alignment",
        label="Count/delivery boundary alignment",
        summary_marker="count_delivery_alignment=",
        reason="CountProfile and DeliveryPreset residuals must share boundary exit criteria.",
    ),
    SceneReleaseResidualExplanationSpec(
        residual_id="boundary_scope_alignment",
        label="Boundary scope alignment",
        summary_marker="boundary_scope_alignment=",
        reason=(
            "Residual release envelopes must expose local capabilities and "
            "excluded core claims before they are release-allowed."
        ),
    ),
)

SCENE_RELEASE_RESIDUAL_EXPLANATION_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]], ...
] = (
    (
        "release_residual_explanation_registry",
        "src/config/scene_release_residual_explanation_audit.py",
        (
            "SCENE_RELEASE_RESIDUAL_EXPLANATION_SPECS",
            "summary_marker",
            "governed_count",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        tuple(spec.summary_marker for spec in SCENE_RELEASE_RESIDUAL_EXPLANATION_SPECS),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            "release_residual_explanations",
            "covered",
            "marker gaps",
        ),
    ),
    (
        "summary_projection",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            "residual explanations",
            "release_residual_explanation_covered_count",
            "release_residual_explanation_count",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_release_residual_explanation_audit.py",
        (
            "run_registered_scene_audit_export",
            SCENE_RELEASE_RESIDUAL_EXPLANATION_AUDIT_SOURCE_ID,
            "Residual explanations covered",
            "markdown",
        ),
    ),
    (
        "n2_393i_plan",
        "docs/audits/高层场景能力矩阵N2_393i发布残留解释覆盖审计_2026-06-25.md",
        (
            "N2.393i",
            "residual_explanations=14/14 covered",
            "SCENE_RELEASE_RESIDUAL_EXPLANATION_SPECS",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneReleaseResidualExplanationIssue:
    residual_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "residual_id": self.residual_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseResidualExplanationSourceEvidence:
    source_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseResidualExplanationRow:
    residual_id: str
    label: str
    residual_count: int
    governed_count: int
    summary_marker: str
    reason: str
    summary_marker_present: bool
    issue_ids: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return "covered" if not self.issue_ids else "uncovered"

    @property
    def is_covered(self) -> bool:
        return self.status == "covered"

    def to_payload(self) -> dict[str, object]:
        return {
            "residual_id": self.residual_id,
            "label": self.label,
            "residual_count": self.residual_count,
            "governed_count": self.governed_count,
            "summary_marker": self.summary_marker,
            "summary_marker_present": self.summary_marker_present,
            "reason": self.reason,
            "status": self.status,
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseResidualExplanationAuditReport:
    rows: tuple[SceneReleaseResidualExplanationRow, ...]
    issues: tuple[SceneReleaseResidualExplanationIssue, ...]
    source_evidence: tuple[SceneReleaseResidualExplanationSourceEvidence, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def covered_count(self) -> int:
        return sum(1 for row in self.rows if row.is_covered)

    @property
    def mismatch_count(self) -> int:
        return sum(1 for row in self.rows if "count_mismatch" in row.issue_ids)

    @property
    def missing_summary_marker_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_summary_marker" in row.issue_ids
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_RELEASE_RESIDUAL_EXPLANATION_AUDIT_SOURCE_ID,
            "counts": {
                "row_count": self.row_count,
                "covered_count": self.covered_count,
                "mismatch_count": self.mismatch_count,
                "missing_summary_marker_count": self.missing_summary_marker_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_release_residual_explanation_audit_report(
    *,
    project_root: Path | str | None = None,
    input_source_report=None,
    count_profile_report=None,
    residual_warning_governance_report=None,
    terminal_release_exception_report=None,
    boundary_maturity_release_envelope_report=None,
    release_residual_ratio_ledger_report=None,
    maturity_upgrade_report=None,
    dashboard_warning_count: int | None = None,
) -> SceneReleaseResidualExplanationAuditReport:
    root = Path(project_root) if project_root is not None else Path.cwd()
    input_report = input_source_report or build_scene_input_source_audit_report(
        project_root=root
    )
    count_report = count_profile_report or build_scene_count_profile_audit_report(
        project_root=root
    )
    residual_report = (
        residual_warning_governance_report
        or build_scene_residual_warning_governance_audit_report(project_root=root)
    )
    terminal_report = (
        terminal_release_exception_report
        or build_scene_terminal_release_exception_audit_report(project_root=root)
    )
    envelope_report = (
        boundary_maturity_release_envelope_report
        or build_scene_boundary_maturity_release_envelope_audit_report(
            project_root=root
        )
    )
    residual_ratio_report = (
        release_residual_ratio_ledger_report
        or build_scene_release_residual_ratio_ledger_audit_report(project_root=root)
    )
    maturity_report = (
        maturity_upgrade_report
        or build_scene_product_maturity_upgrade_audit_report(project_root=root)
    )
    if dashboard_warning_count is None:
        dashboard_warning_count = int(
            residual_report.dashboard_projection_warning_count
        )
    release_gate_text = _source_text(root, "scripts/verify_scene_matrix_release_gate.py")
    counts = {
        "managed_warnings": (
            residual_report.warning_count,
            residual_report.managed_warning_count,
        ),
        "input_warnings": (
            input_report.warning_count,
            residual_report.input_source_managed_warning_count,
        ),
        "count_profile_warnings": (
            count_report.warning_count,
            residual_report.count_profile_managed_warning_count,
        ),
        "plugin_manual_warnings": (
            residual_report.plugin_manual_warning_count,
            residual_report.plugin_manual_managed_warning_count,
        ),
        "reference_profile_warnings": (
            residual_report.reference_profile_warning_count,
            residual_report.reference_profile_managed_warning_count,
        ),
        "visio_fixture": (
            residual_report.visio_fixture_closed_count,
            residual_report.visio_fixture_closed_count,
        ),
        "dashboard_warning_projection": (
            dashboard_warning_count,
            terminal_report.warning_projection_count,
        ),
        "static_closed_not_green": (
            len(static_closed_but_not_green_specs()),
            terminal_report.static_closed_boundary_count,
        ),
        "maturity_l5_enveloped": (
            maturity_report.l5_blocked_subject_count,
            envelope_report.l5_blocker_enveloped_count,
        ),
        "maturity_l5_alignment": (
            residual_ratio_report.maturity_l5_blocker_release_envelope_count,
            residual_ratio_report.maturity_l5_blocker_alignment_count,
        ),
        "retained_gaps": (
            maturity_report.gap_count,
            envelope_report.retained_gap_count,
        ),
        "gap_domains": (
            maturity_report.gap_domain_count,
            maturity_report.gap_domain_count,
        ),
        "count_delivery_alignment": (
            residual_ratio_report.count_delivery_boundary_link_count,
            residual_ratio_report.count_delivery_boundary_alignment_count,
        ),
        "boundary_scope_alignment": (
            residual_ratio_report.boundary_scope_link_count,
            residual_ratio_report.boundary_scope_alignment_count,
        ),
    }
    rows = tuple(
        _row_for_spec(spec, counts, release_gate_text)
        for spec in SCENE_RELEASE_RESIDUAL_EXPLANATION_SPECS
    )
    source_evidence = _source_evidence(root)
    issues = (
        *_row_issues(rows),
        *_source_evidence_issues(source_evidence),
    )
    return SceneReleaseResidualExplanationAuditReport(
        rows=rows,
        issues=issues,
        source_evidence=source_evidence,
    )


def audit_scene_release_residual_explanation_report(
    report: SceneReleaseResidualExplanationAuditReport | None = None,
) -> tuple[SceneReleaseResidualExplanationIssue, ...]:
    current = report or build_scene_release_residual_explanation_audit_report()
    return current.issues


def _row_for_spec(
    spec: SceneReleaseResidualExplanationSpec,
    counts: dict[str, tuple[int, int]],
    release_gate_text: str,
) -> SceneReleaseResidualExplanationRow:
    residual_count, governed_count = counts[spec.residual_id]
    issue_ids: list[str] = []
    marker_present = spec.summary_marker in release_gate_text
    if residual_count != governed_count:
        issue_ids.append("count_mismatch")
    if not marker_present:
        issue_ids.append("missing_summary_marker")
    return SceneReleaseResidualExplanationRow(
        residual_id=spec.residual_id,
        label=spec.label,
        residual_count=residual_count,
        governed_count=governed_count,
        summary_marker=spec.summary_marker,
        reason=spec.reason,
        summary_marker_present=marker_present,
        issue_ids=tuple(issue_ids),
    )


def _row_issues(
    rows: tuple[SceneReleaseResidualExplanationRow, ...],
) -> tuple[SceneReleaseResidualExplanationIssue, ...]:
    issues: list[SceneReleaseResidualExplanationIssue] = []
    for row in rows:
        if "count_mismatch" in row.issue_ids:
            issues.append(
                SceneReleaseResidualExplanationIssue(
                    row.residual_id,
                    "count_mismatch",
                    (
                        f"{row.residual_id} residual_count={row.residual_count} "
                        f"but governed_count={row.governed_count}"
                    ),
                )
            )
        if "missing_summary_marker" in row.issue_ids:
            issues.append(
                SceneReleaseResidualExplanationIssue(
                    row.residual_id,
                    "missing_summary_marker",
                    f"Release gate summary missing {row.summary_marker}",
                )
            )
    return tuple(issues)


def _source_evidence(
    root: Path,
) -> tuple[SceneReleaseResidualExplanationSourceEvidence, ...]:
    return tuple(
        SceneReleaseResidualExplanationSourceEvidence(
            source_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
        )
        for result in scan_scene_source_markers(
            root,
            SCENE_RELEASE_RESIDUAL_EXPLANATION_SOURCE_MARKERS,
        )
    )


def _source_text(root: Path, source_path: str) -> str:
    path = Path(source_path)
    if not path.is_absolute():
        path = root / source_path
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _source_evidence_issues(
    source_evidence: tuple[SceneReleaseResidualExplanationSourceEvidence, ...],
) -> tuple[SceneReleaseResidualExplanationIssue, ...]:
    return tuple(
        SceneReleaseResidualExplanationIssue(
            evidence.source_id,
            "missing_source_evidence",
            scene_source_marker_issue_message(
                evidence.source_path,
                evidence.missing_markers,
            ),
        )
        for evidence in source_evidence
        if evidence.missing_markers
    )


__all__ = [
    "SCENE_RELEASE_RESIDUAL_EXPLANATION_AUDIT_SOURCE_ID",
    "SCENE_RELEASE_RESIDUAL_EXPLANATION_SPECS",
    "SceneReleaseResidualExplanationAuditReport",
    "SceneReleaseResidualExplanationIssue",
    "SceneReleaseResidualExplanationRow",
    "audit_scene_release_residual_explanation_report",
    "build_scene_release_residual_explanation_audit_report",
]
