"""Boundary-subject release-continuity audit for the scene matrix.

N2.389 proves that the same Blue/Boundary subjects flow through maturity,
guarded completion, readiness reconciliation, terminal release traces, and
subject release dossiers.  This prevents a subject from silently appearing in
one release layer while disappearing from another.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_boundary_guarded_completion_audit import (
    build_scene_boundary_guarded_completion_audit_report,
)
from src.config.scene_boundary_readiness_reconciliation_audit import (
    build_scene_boundary_readiness_reconciliation_audit_report,
)
from src.config.scene_boundary_subject_release_dossier_audit import (
    build_scene_boundary_subject_release_dossier_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_source_evidence import (
    scan_scene_source_markers,
    scene_source_marker_issue_message,
)
from src.config.scene_terminal_release_exception_audit import (
    build_scene_terminal_release_exception_audit_report,
)


SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_AUDIT_SOURCE_ID = (
    "scene_boundary_subject_release_continuity_audit"
)

SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "maturity_boundary_subject",
    "boundary_guarded_completion_subject",
    "readiness_reconciliation_subject",
    "terminal_release_exception_subject_trace",
    "boundary_subject_release_dossier",
)

SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "boundary_subject_release_continuity_registry",
        "src/config/scene_boundary_subject_release_continuity_audit.py",
        (
            "SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_REQUIRED_EVIDENCE_IDS",
            "boundary_subject_release_continuity",
            "maturity_subject_count",
        ),
    ),
    (
        "maturity_upgrade",
        "src/config/scene_product_maturity_upgrade_audit.py",
        ("boundary_subject_count", "blue_boundary"),
    ),
    (
        "boundary_guarded_completion",
        "src/config/scene_boundary_guarded_completion_audit.py",
        ("boundary_guarded_complete", "ready_subject_count"),
    ),
    (
        "boundary_readiness_reconciliation",
        "src/config/scene_boundary_readiness_reconciliation_audit.py",
        ("linked_boundary_subject_ids", "boundary_subject_count"),
    ),
    (
        "terminal_release_exception",
        "src/config/scene_terminal_release_exception_audit.py",
        ("linked_boundary_subject_ids", "linked_boundary_subject_count"),
    ),
    (
        "boundary_subject_release_dossier",
        "src/config/scene_boundary_subject_release_dossier_audit.py",
        ("subject_key", "ready_subject_count"),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_AUDIT_SOURCE_ID,
            "boundary_subject_release_continuity_ready_count",
        ),
    ),
    (
        "scene_matrix_drilldown",
        "src/config/scene_matrix_drilldown_release_items.py",
        (
            SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_AUDIT_SOURCE_ID,
            "boundary_subject_release_continuity",
        ),
    ),
    (
        "summary_projection",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            "boundary_subject_release_continuity_ready_count",
            "subject continuity",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_AUDIT_SOURCE_ID,
            "scene_boundary_subject_release_continuity_ready_count",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_boundary_subject_release_continuity_audit.py",
        (
            "run_registered_scene_audit_export",
            SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_AUDIT_SOURCE_ID,
            "Subjects ready",
            "row.subject_key",
            "row.readiness_row_ids",
            "row.terminal_trace_ids",
            "row.evidence_ids",
            "markdown",
        ),
    ),
    (
        "n2_389_plan",
        "docs/audits/高层场景能力矩阵N2_389边界主体发布链连续性闭环_2026-06-24.md",
        ("N2.389", "boundary_subject_release_continuity", "6/6"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneBoundarySubjectReleaseContinuityIssue:
    subject_key: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "subject_key": self.subject_key,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneBoundarySubjectReleaseContinuitySourceEvidence:
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
class SceneBoundarySubjectReleaseContinuityRow:
    subject_key: str
    subject_type: str
    subject_id: str
    status: str
    in_maturity: bool
    in_guarded_completion: bool
    in_readiness_reconciliation: bool
    in_terminal_release_exception: bool
    in_subject_dossier: bool
    readiness_row_ids: tuple[str, ...]
    terminal_trace_ids: tuple[str, ...]
    dossier_trace_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status == "continuity_ready"

    def to_payload(self) -> dict[str, object]:
        return {
            "subject_key": self.subject_key,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "status": self.status,
            "in_maturity": self.in_maturity,
            "in_guarded_completion": self.in_guarded_completion,
            "in_readiness_reconciliation": self.in_readiness_reconciliation,
            "in_terminal_release_exception": self.in_terminal_release_exception,
            "in_subject_dossier": self.in_subject_dossier,
            "readiness_row_ids": list(self.readiness_row_ids),
            "terminal_trace_ids": list(self.terminal_trace_ids),
            "dossier_trace_ids": list(self.dossier_trace_ids),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneBoundarySubjectReleaseContinuityAuditReport:
    rows: tuple[SceneBoundarySubjectReleaseContinuityRow, ...]
    issues: tuple[SceneBoundarySubjectReleaseContinuityIssue, ...]
    source_evidence: tuple[SceneBoundarySubjectReleaseContinuitySourceEvidence, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def subject_count(self) -> int:
        return len(self.rows)

    @property
    def ready_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.is_ready)

    @property
    def maturity_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.in_maturity)

    @property
    def guarded_completion_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.in_guarded_completion)

    @property
    def readiness_reconciliation_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.in_readiness_reconciliation)

    @property
    def terminal_release_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.in_terminal_release_exception)

    @property
    def subject_dossier_count(self) -> int:
        return sum(1 for row in self.rows if row.in_subject_dossier)

    @property
    def readiness_row_count(self) -> int:
        return len(
            _unique_values(
                row_id for row in self.rows for row_id in row.readiness_row_ids
            )
        )

    @property
    def terminal_trace_count(self) -> int:
        return len(
            _unique_values(
                trace_id for row in self.rows for trace_id in row.terminal_trace_ids
            )
        )

    @property
    def dossier_trace_count(self) -> int:
        return len(
            _unique_values(
                trace_id for row in self.rows for trace_id in row.dossier_trace_ids
            )
        )

    @property
    def mismatch_count(self) -> int:
        return sum(1 for row in self.rows if row.issue_ids)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_AUDIT_SOURCE_ID,
            "required_evidence_ids": list(
                SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "subject_count": self.subject_count,
                "ready_subject_count": self.ready_subject_count,
                "maturity_subject_count": self.maturity_subject_count,
                "guarded_completion_subject_count": (
                    self.guarded_completion_subject_count
                ),
                "readiness_reconciliation_subject_count": (
                    self.readiness_reconciliation_subject_count
                ),
                "terminal_release_subject_count": self.terminal_release_subject_count,
                "subject_dossier_count": self.subject_dossier_count,
                "readiness_row_count": self.readiness_row_count,
                "terminal_trace_count": self.terminal_trace_count,
                "dossier_trace_count": self.dossier_trace_count,
                "mismatch_count": self.mismatch_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_boundary_subject_release_continuity_audit_report(
    *,
    project_root: Path | str | None = None,
) -> SceneBoundarySubjectReleaseContinuityAuditReport:
    maturity_report = build_scene_product_maturity_upgrade_audit_report(
        project_root=project_root
    )
    guarded_report = build_scene_boundary_guarded_completion_audit_report(
        project_root=project_root
    )
    readiness_report = build_scene_boundary_readiness_reconciliation_audit_report(
        project_root=project_root
    )
    terminal_report = build_scene_terminal_release_exception_audit_report(
        project_root=project_root
    )
    dossier_report = build_scene_boundary_subject_release_dossier_audit_report(
        project_root=project_root
    )

    maturity_subjects = {
        f"{row.subject_type}:{row.subject_id}"
        for row in maturity_report.rows
        if row.is_boundary
    }
    guarded_subjects = {
        f"{row.subject_type}:{row.subject_id}" for row in guarded_report.rows
    }
    readiness_subjects = {
        subject
        for row in readiness_report.rows
        for subject in row.linked_boundary_subject_ids
    }
    terminal_subjects = {
        subject
        for row in terminal_report.rows
        for trace in row.trace_rows
        for subject in trace.linked_boundary_subject_ids
    }
    dossier_subjects = {row.subject_key for row in dossier_report.rows}
    subject_keys = tuple(
        sorted(
            maturity_subjects
            | guarded_subjects
            | readiness_subjects
            | terminal_subjects
            | dossier_subjects
        )
    )
    rows = tuple(
        _row_for_subject(
            subject_key,
            maturity_subjects=maturity_subjects,
            guarded_subjects=guarded_subjects,
            readiness_rows=readiness_report.rows,
            terminal_rows=terminal_report.rows,
            dossier_rows=dossier_report.rows,
        )
        for subject_key in subject_keys
    )
    issues: list[SceneBoundarySubjectReleaseContinuityIssue] = []
    for row in rows:
        issues.extend(
            SceneBoundarySubjectReleaseContinuityIssue(
                row.subject_key,
                issue_id,
                f"Boundary subject release continuity {row.subject_key} failed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneBoundarySubjectReleaseContinuityAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
    )


def audit_scene_boundary_subject_release_continuity_report(
    report: SceneBoundarySubjectReleaseContinuityAuditReport | None = None,
) -> tuple[SceneBoundarySubjectReleaseContinuityIssue, ...]:
    current = report or build_scene_boundary_subject_release_continuity_audit_report()
    return current.issues


def _row_for_subject(
    subject_key: str,
    *,
    maturity_subjects: set[str],
    guarded_subjects: set[str],
    readiness_rows,
    terminal_rows,
    dossier_rows,
) -> SceneBoundarySubjectReleaseContinuityRow:
    subject_type, subject_id = subject_key.split(":", 1)
    readiness_row_ids = tuple(
        row.row_id for row in readiness_rows if subject_key in row.linked_boundary_subject_ids
    )
    terminal_trace_ids = tuple(
        trace.trace_id
        for terminal_row in terminal_rows
        for trace in terminal_row.trace_rows
        if subject_key in trace.linked_boundary_subject_ids
    )
    matched_dossier_rows = tuple(
        row for row in dossier_rows if row.subject_key == subject_key
    )
    dossier_trace_ids = tuple(
        trace_id
        for row in matched_dossier_rows
        for trace_id in row.release_exception_trace_ids
    )
    in_maturity = subject_key in maturity_subjects
    in_guarded = subject_key in guarded_subjects
    in_readiness = bool(readiness_row_ids)
    in_terminal = bool(terminal_trace_ids)
    in_dossier = bool(matched_dossier_rows)
    issue_ids = _issue_ids(
        in_maturity=in_maturity,
        in_guarded=in_guarded,
        in_readiness=in_readiness,
        in_terminal=in_terminal,
        in_dossier=in_dossier,
    )
    return SceneBoundarySubjectReleaseContinuityRow(
        subject_key=subject_key,
        subject_type=subject_type,
        subject_id=subject_id,
        status="continuity_ready" if not issue_ids else "continuity_gap",
        in_maturity=in_maturity,
        in_guarded_completion=in_guarded,
        in_readiness_reconciliation=in_readiness,
        in_terminal_release_exception=in_terminal,
        in_subject_dossier=in_dossier,
        readiness_row_ids=readiness_row_ids,
        terminal_trace_ids=terminal_trace_ids,
        dossier_trace_ids=dossier_trace_ids,
        evidence_ids=SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_REQUIRED_EVIDENCE_IDS,
        issue_ids=issue_ids,
    )


def _issue_ids(
    *,
    in_maturity: bool,
    in_guarded: bool,
    in_readiness: bool,
    in_terminal: bool,
    in_dossier: bool,
) -> tuple[str, ...]:
    issue_ids: list[str] = []
    if not in_maturity:
        issue_ids.append("missing_maturity_boundary_subject")
    if not in_guarded:
        issue_ids.append("missing_guarded_completion_subject")
    if not in_readiness:
        issue_ids.append("missing_readiness_reconciliation_subject")
    if not in_terminal:
        issue_ids.append("missing_terminal_release_subject")
    if not in_dossier:
        issue_ids.append("missing_subject_release_dossier")
    return tuple(issue_ids)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneBoundarySubjectReleaseContinuitySourceEvidence, ...]:
    return tuple(
        SceneBoundarySubjectReleaseContinuitySourceEvidence(
            source_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
        )
        for result in scan_scene_source_markers(
            project_root,
            SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_SOURCE_MARKERS,
        )
    )


def _source_evidence_issues(
    source_evidence: tuple[SceneBoundarySubjectReleaseContinuitySourceEvidence, ...],
) -> tuple[SceneBoundarySubjectReleaseContinuityIssue, ...]:
    return tuple(
        SceneBoundarySubjectReleaseContinuityIssue(
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
    "SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_AUDIT_SOURCE_ID",
    "SCENE_BOUNDARY_SUBJECT_RELEASE_CONTINUITY_REQUIRED_EVIDENCE_IDS",
    "SceneBoundarySubjectReleaseContinuityAuditReport",
    "SceneBoundarySubjectReleaseContinuityIssue",
    "SceneBoundarySubjectReleaseContinuityRow",
    "SceneBoundarySubjectReleaseContinuitySourceEvidence",
    "audit_scene_boundary_subject_release_continuity_report",
    "build_scene_boundary_subject_release_continuity_audit_report",
]
