"""Boundary guarded-completion audit for the high-level scene matrix.

N2.380 separates ordinary unfinished maturity from intentional Blue/Boundary
completion.  A subject remains non-Green because the external judgment or
plugin is outside the core formatter, but it can still be complete as a
guarded product boundary when capability, gate, handoff contract, reports,
and excluded-core claims are all present.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from src.config.scene_boundary_capability_matrix import (
    build_scene_boundary_capability_audit_report,
)
from src.config.scene_external_handoff_contract_audit import (
    build_scene_external_handoff_contract_audit_report,
)
from src.config.scene_plugin_boundary_confirmation_audit import (
    build_scene_plugin_boundary_confirmation_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_source_evidence import (
    scan_scene_source_markers,
    scene_source_marker_issue_message,
)


SCENE_BOUNDARY_GUARDED_COMPLETION_AUDIT_SOURCE_ID = (
    "scene_boundary_guarded_completion_audit"
)

SCENE_BOUNDARY_GUARDED_COMPLETION_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "blue_boundary_readiness",
    "maturity_gap_retained",
    "boundary_capability_ready",
    "plugin_manual_gate_ready",
    "external_handoff_contract_ready",
    "excluded_core_claims_declared",
)

SCENE_BOUNDARY_GUARDED_COMPLETION_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "guarded_completion_registry",
        "src/config/scene_boundary_guarded_completion_audit.py",
        (
            "SCENE_BOUNDARY_GUARDED_COMPLETION_REQUIRED_EVIDENCE_IDS",
            "boundary_guarded_complete",
            "excluded_core_claims_declared",
        ),
    ),
    (
        "external_handoff_contracts",
        "src/config/scene_external_handoff_contract_audit.py",
        (
            "SCENE_EXTERNAL_HANDOFF_CONTRACT_SPECS",
            "external_receipt_id",
            "excluded_core_claims",
        ),
    ),
    (
        "boundary_capability_matrix",
        "src/config/scene_boundary_capability_matrix.py",
        (
            "SCENE_BOUNDARY_CAPABILITY_SPECS",
            "handoff_target_ids",
            "Boundary capability subjects must remain Blue/Boundary",
        ),
    ),
    (
        "maturity_upgrade",
        "src/config/scene_product_maturity_upgrade_audit.py",
        (
            "boundary_guarded_orange_l4",
            "boundary_subject_count",
            "remaining_product_gaps",
        ),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_BOUNDARY_GUARDED_COMPLETION_AUDIT_SOURCE_ID,
            "boundary_guarded_completion_ready_count",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_BOUNDARY_GUARDED_COMPLETION_AUDIT_SOURCE_ID,
            "scene_boundary_guarded_completion_ready_count",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_boundary_guarded_completion_audit.py",
        (
            "run_registered_scene_audit_export",
            SCENE_BOUNDARY_GUARDED_COMPLETION_AUDIT_SOURCE_ID,
            "Subjects:",
            "row.subject_type",
            "row.subject_id",
            "row.remaining_gap_ids",
            "row.external_handoff_contract_ids",
            "row.excluded_core_claims",
            "_builder_kwargs",
            "markdown",
        ),
    ),
    (
        "n2_380_plan",
        "docs/audits/高层场景能力矩阵N2_380边界守护完成度闭环_2026-06-24.md",
        (
            "N2.380",
            "boundary_guarded_complete",
            "不是 Green/L5",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneBoundaryGuardedCompletionIssue:
    subject_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "subject_id": self.subject_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneBoundaryGuardedCompletionSourceEvidence:
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
class SceneBoundaryGuardedCompletionRow:
    subject_type: str
    subject_id: str
    status: str
    readiness_level: str
    maturity_status: str
    remaining_gap_ids: tuple[str, ...]
    boundary_capability_ids: tuple[str, ...]
    plugin_gate_ids: tuple[str, ...]
    external_handoff_contract_ids: tuple[str, ...]
    target_plugin_ids: tuple[str, ...]
    risk_domain_ids: tuple[str, ...]
    report_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    excluded_core_claims: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]

    @property
    def is_guarded_complete(self) -> bool:
        return self.status == "boundary_guarded_complete"

    def to_payload(self) -> dict[str, object]:
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "status": self.status,
            "readiness_level": self.readiness_level,
            "maturity_status": self.maturity_status,
            "remaining_gap_ids": list(self.remaining_gap_ids),
            "boundary_capability_ids": list(self.boundary_capability_ids),
            "plugin_gate_ids": list(self.plugin_gate_ids),
            "external_handoff_contract_ids": list(
                self.external_handoff_contract_ids
            ),
            "target_plugin_ids": list(self.target_plugin_ids),
            "risk_domain_ids": list(self.risk_domain_ids),
            "report_ids": list(self.report_ids),
            "fixture_ids": list(self.fixture_ids),
            "excluded_core_claims": list(self.excluded_core_claims),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneBoundaryGuardedCompletionAuditReport:
    rows: tuple[SceneBoundaryGuardedCompletionRow, ...]
    issues: tuple[SceneBoundaryGuardedCompletionIssue, ...]
    source_evidence: tuple[SceneBoundaryGuardedCompletionSourceEvidence, ...]
    subject_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def subject_count(self) -> int:
        return len(self.rows)

    @property
    def ready_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.is_guarded_complete)

    @property
    def pack_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.subject_type == "pack")

    @property
    def family_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.subject_type == "family")

    @property
    def retained_gap_count(self) -> int:
        return len(_unique_values(gap for row in self.rows for gap in row.remaining_gap_ids))

    @property
    def external_contract_count(self) -> int:
        return len(
            _unique_values(
                contract
                for row in self.rows
                for contract in row.external_handoff_contract_ids
            )
        )

    @property
    def boundary_capability_count(self) -> int:
        return len(
            _unique_values(
                capability
                for row in self.rows
                for capability in row.boundary_capability_ids
            )
        )

    @property
    def plugin_gate_count(self) -> int:
        return len(_unique_values(gate for row in self.rows for gate in row.plugin_gate_ids))

    @property
    def target_plugin_count(self) -> int:
        return len(
            _unique_values(
                plugin for row in self.rows for plugin in row.target_plugin_ids
            )
        )

    @property
    def risk_domain_count(self) -> int:
        return len(_unique_values(domain for row in self.rows for domain in row.risk_domain_ids))

    @property
    def excluded_core_claim_count(self) -> int:
        return len(
            _unique_values(
                claim for row in self.rows for claim in row.excluded_core_claims
            )
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_BOUNDARY_GUARDED_COMPLETION_AUDIT_SOURCE_ID,
            "subject_filter": self.subject_filter,
            "required_evidence_ids": list(
                SCENE_BOUNDARY_GUARDED_COMPLETION_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "subject_count": self.subject_count,
                "ready_subject_count": self.ready_subject_count,
                "pack_subject_count": self.pack_subject_count,
                "family_subject_count": self.family_subject_count,
                "retained_gap_count": self.retained_gap_count,
                "external_contract_count": self.external_contract_count,
                "boundary_capability_count": self.boundary_capability_count,
                "plugin_gate_count": self.plugin_gate_count,
                "target_plugin_count": self.target_plugin_count,
                "risk_domain_count": self.risk_domain_count,
                "excluded_core_claim_count": self.excluded_core_claim_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [evidence.to_payload() for evidence in self.source_evidence],
        }


def build_scene_boundary_guarded_completion_audit_report(
    *,
    subject_id: str = "",
    project_root: Path | str | None = None,
) -> SceneBoundaryGuardedCompletionAuditReport:
    normalized_subject = str(subject_id or "").strip()
    maturity_report = build_scene_product_maturity_upgrade_audit_report(
        project_root=project_root
    )
    boundary_report = build_scene_boundary_capability_audit_report(
        project_root=project_root
    )
    plugin_report = build_scene_plugin_boundary_confirmation_audit_report(
        project_root=Path(project_root) if project_root is not None else None
    )
    handoff_report = build_scene_external_handoff_contract_audit_report(
        project_root=project_root
    )
    rows: list[SceneBoundaryGuardedCompletionRow] = []
    issues: list[SceneBoundaryGuardedCompletionIssue] = []
    for maturity_row in maturity_report.rows:
        if not maturity_row.is_boundary:
            continue
        if normalized_subject and maturity_row.subject_id != normalized_subject:
            continue
        row = _row_for_subject(
            maturity_row,
            boundary_rows=boundary_report.rows,
            plugin_rows=plugin_report.rows,
            handoff_rows=handoff_report.rows,
        )
        row_issues = _row_issues(row)
        issues.extend(row_issues)
        rows.append(
            replace(
                row,
                status=(
                    "boundary_guarded_complete"
                    if not row_issues
                    else "boundary_guarded_incomplete"
                ),
                issue_ids=tuple(issue.kind for issue in row_issues),
            )
        )
    if normalized_subject and not rows:
        issues.append(
            SceneBoundaryGuardedCompletionIssue(
                normalized_subject,
                "unknown_boundary_subject_filter",
                f"Unknown Blue/Boundary subject: {normalized_subject}",
            )
        )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneBoundaryGuardedCompletionAuditReport(
        rows=tuple(rows),
        issues=tuple(issues),
        source_evidence=source_evidence,
        subject_filter=normalized_subject,
    )


def audit_scene_boundary_guarded_completion_report(
    report: SceneBoundaryGuardedCompletionAuditReport | None = None,
) -> tuple[SceneBoundaryGuardedCompletionIssue, ...]:
    current = report or build_scene_boundary_guarded_completion_audit_report()
    return current.issues


def _row_for_subject(
    maturity_row,
    *,
    boundary_rows,
    plugin_rows,
    handoff_rows,
) -> SceneBoundaryGuardedCompletionRow:
    subject_type = maturity_row.subject_type
    subject_id = maturity_row.subject_id
    matched_boundary_rows = tuple(
        row
        for row in boundary_rows
        if row.subject_type == subject_type and row.subject_id == subject_id
    )
    matched_contract_rows = tuple(
        row
        for row in handoff_rows
        if row.subject_type == subject_type and row.subject_id == subject_id
    )
    contract_gate_ids = _unique_values(row.gate_id for row in matched_contract_rows)
    matched_plugin_rows = tuple(
        row for row in plugin_rows if row.gate_id in contract_gate_ids
    )
    return SceneBoundaryGuardedCompletionRow(
        subject_type=subject_type,
        subject_id=subject_id,
        status="boundary_guarded_incomplete",
        readiness_level=maturity_row.current_readiness_level,
        maturity_status=maturity_row.status,
        remaining_gap_ids=maturity_row.remaining_product_gaps,
        boundary_capability_ids=_unique_values(
            row.capability_id for row in matched_boundary_rows
        ),
        plugin_gate_ids=contract_gate_ids,
        external_handoff_contract_ids=_unique_values(
            row.contract_id for row in matched_contract_rows
        ),
        target_plugin_ids=_unique_values(
            row.target_plugin_id for row in matched_contract_rows
        ),
        risk_domain_ids=_unique_values(
            domain
            for row in (*matched_contract_rows, *matched_plugin_rows)
            for domain in row.risk_domain_ids
        ),
        report_ids=_unique_values(
            report_id
            for row in matched_contract_rows
            for report_id in row.required_report_ids
        ),
        fixture_ids=_unique_values(
            fixture_id
            for row in matched_contract_rows
            for fixture_id in row.fixture_ids
        ),
        excluded_core_claims=_unique_values(
            claim
            for row in matched_contract_rows
            for claim in row.excluded_core_claims
        ),
        evidence_ids=SCENE_BOUNDARY_GUARDED_COMPLETION_REQUIRED_EVIDENCE_IDS,
        issue_ids=(),
    )


def _row_issues(
    row: SceneBoundaryGuardedCompletionRow,
) -> tuple[SceneBoundaryGuardedCompletionIssue, ...]:
    issues: list[SceneBoundaryGuardedCompletionIssue] = []

    def append(kind: str, message: str) -> None:
        issues.append(SceneBoundaryGuardedCompletionIssue(row.subject_id, kind, message))

    if row.readiness_level != "blue_boundary":
        append(
            "subject_not_blue_boundary",
            "Guarded completion only applies to Blue/Boundary subjects.",
        )
    if row.maturity_status != "boundary_guarded":
        append(
            "maturity_not_boundary_guarded",
            "Maturity row must stay boundary_guarded, not Green/L5.",
        )
    if not row.remaining_gap_ids:
        append(
            "missing_retained_gap",
            "Boundary guarded completion must retain the external product gap.",
        )
    if not row.boundary_capability_ids:
        append(
            "missing_boundary_capability",
            "Boundary guarded completion requires a ready boundary capability.",
        )
    if not row.plugin_gate_ids:
        append(
            "missing_plugin_gate",
            "Boundary guarded completion requires a plugin/manual gate.",
        )
    if not row.external_handoff_contract_ids:
        append(
            "missing_external_handoff_contract",
            "Boundary guarded completion requires an external handoff contract.",
        )
    if not row.target_plugin_ids:
        append(
            "missing_target_plugin",
            "Boundary guarded completion must name the target plugin/professional handoff.",
        )
    if not row.report_ids:
        append(
            "missing_report_evidence",
            "Boundary guarded completion requires report evidence.",
        )
    if not row.fixture_ids:
        append(
            "missing_fixture_evidence",
            "Boundary guarded completion requires fixture evidence.",
        )
    if not row.excluded_core_claims:
        append(
            "missing_excluded_core_claims",
            "Boundary guarded completion must state what core will not claim.",
        )
    missing_evidence = tuple(
        evidence_id
        for evidence_id in SCENE_BOUNDARY_GUARDED_COMPLETION_REQUIRED_EVIDENCE_IDS
        if evidence_id not in row.evidence_ids
    )
    if missing_evidence:
        append(
            "missing_guarded_evidence_ids",
            "Missing guarded evidence ids: " + ", ".join(missing_evidence),
        )
    return tuple(issues)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneBoundaryGuardedCompletionSourceEvidence, ...]:
    return tuple(
        SceneBoundaryGuardedCompletionSourceEvidence(
            source_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
        )
        for result in scan_scene_source_markers(
            project_root,
            SCENE_BOUNDARY_GUARDED_COMPLETION_SOURCE_MARKERS,
        )
    )


def _source_evidence_issues(
    source_evidence: tuple[SceneBoundaryGuardedCompletionSourceEvidence, ...],
) -> tuple[SceneBoundaryGuardedCompletionIssue, ...]:
    return tuple(
        SceneBoundaryGuardedCompletionIssue(
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


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_BOUNDARY_GUARDED_COMPLETION_AUDIT_SOURCE_ID",
    "SCENE_BOUNDARY_GUARDED_COMPLETION_REQUIRED_EVIDENCE_IDS",
    "SceneBoundaryGuardedCompletionAuditReport",
    "SceneBoundaryGuardedCompletionIssue",
    "SceneBoundaryGuardedCompletionRow",
    "SceneBoundaryGuardedCompletionSourceEvidence",
    "audit_scene_boundary_guarded_completion_report",
    "build_scene_boundary_guarded_completion_audit_report",
]
