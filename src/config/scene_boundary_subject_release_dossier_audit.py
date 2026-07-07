"""Boundary-subject release dossier audit for the scene matrix.

N2.385 groups the row-level release-exception traces back into the six
Blue/Boundary subjects.  This keeps a subject-level release view between the
top-level terminal exception ledger and the lower-level guarded/readiness
audits.
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
from src.config.scene_terminal_release_exception_audit import (
    build_scene_terminal_release_exception_audit_report,
)


SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_AUDIT_SOURCE_ID = (
    "scene_boundary_subject_release_dossier_audit"
)

SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "boundary_guarded_completion_row",
    "readiness_reconciliation_subject_trace",
    "terminal_release_exception_trace",
    "retained_gap_declared",
    "handoff_contract_ready",
    "excluded_core_claims_declared",
)

SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "subject_release_dossier_registry",
        "src/config/scene_boundary_subject_release_dossier_audit.py",
        (
            "SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_REQUIRED_EVIDENCE_IDS",
            "boundary_subject_release_dossier",
            "terminal_release_exception_trace",
        ),
    ),
    (
        "terminal_release_exception",
        "src/config/scene_terminal_release_exception_audit.py",
        ("SceneTerminalReleaseExceptionTrace", "linked_boundary_subject_ids"),
    ),
    (
        "boundary_readiness_reconciliation",
        "src/config/scene_boundary_readiness_reconciliation_audit.py",
        ("linked_boundary_subject_ids", "boundary_subject_count"),
    ),
    (
        "boundary_guarded_completion",
        "src/config/scene_boundary_guarded_completion_audit.py",
        ("boundary_guarded_complete", "external_handoff_contract_ids"),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_AUDIT_SOURCE_ID,
            "boundary_subject_release_dossier_ready_count",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_AUDIT_SOURCE_ID,
            "scene_boundary_subject_release_dossier_ready_count",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_boundary_subject_release_dossier_audit.py",
        (
            "build_scene_boundary_subject_release_dossier_audit_report",
            "Ready subjects",
            "row.subject_key",
            "row.subject_trace_count",
            "row.readiness_reconciliation_row_ids",
            "row.terminal_exception_ids",
            "row.external_handoff_contract_ids",
            "json",
            "markdown",
        ),
    ),
    (
        "n2_385_plan",
        "docs/audits/高层场景能力矩阵N2_385边界主体发布证据包闭环_2026-06-24.md",
        ("N2.385", "boundary_subject_release_dossier", "subject_trace_count"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneBoundarySubjectReleaseDossierIssue:
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
class SceneBoundarySubjectReleaseDossierSourceEvidence:
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
class SceneBoundarySubjectReleaseDossierRow:
    subject_type: str
    subject_id: str
    status: str
    readiness_level: str
    maturity_status: str
    retained_gap_ids: tuple[str, ...]
    boundary_capability_ids: tuple[str, ...]
    plugin_gate_ids: tuple[str, ...]
    external_handoff_contract_ids: tuple[str, ...]
    target_plugin_ids: tuple[str, ...]
    readiness_reconciliation_row_ids: tuple[str, ...]
    terminal_exception_ids: tuple[str, ...]
    release_exception_trace_ids: tuple[str, ...]
    release_exception_source_trace_ids: tuple[str, ...]
    risk_domain_ids: tuple[str, ...]
    excluded_core_claims: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def subject_key(self) -> str:
        return f"{self.subject_type}:{self.subject_id}"

    @property
    def is_ready(self) -> bool:
        return self.status == "release_dossier_ready"

    @property
    def subject_trace_count(self) -> int:
        return len(self.release_exception_trace_ids)

    def to_payload(self) -> dict[str, object]:
        return {
            "subject_key": self.subject_key,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "status": self.status,
            "readiness_level": self.readiness_level,
            "maturity_status": self.maturity_status,
            "retained_gap_ids": list(self.retained_gap_ids),
            "boundary_capability_ids": list(self.boundary_capability_ids),
            "plugin_gate_ids": list(self.plugin_gate_ids),
            "external_handoff_contract_ids": list(
                self.external_handoff_contract_ids
            ),
            "target_plugin_ids": list(self.target_plugin_ids),
            "readiness_reconciliation_row_ids": list(
                self.readiness_reconciliation_row_ids
            ),
            "terminal_exception_ids": list(self.terminal_exception_ids),
            "release_exception_trace_ids": list(self.release_exception_trace_ids),
            "release_exception_source_trace_ids": list(
                self.release_exception_source_trace_ids
            ),
            "subject_trace_count": self.subject_trace_count,
            "risk_domain_ids": list(self.risk_domain_ids),
            "excluded_core_claims": list(self.excluded_core_claims),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneBoundarySubjectReleaseDossierAuditReport:
    rows: tuple[SceneBoundarySubjectReleaseDossierRow, ...]
    issues: tuple[SceneBoundarySubjectReleaseDossierIssue, ...]
    source_evidence: tuple[SceneBoundarySubjectReleaseDossierSourceEvidence, ...]

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
    def pack_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.subject_type == "pack")

    @property
    def family_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.subject_type == "family")

    @property
    def subject_trace_count(self) -> int:
        return sum(row.subject_trace_count for row in self.rows)

    @property
    def unique_source_trace_count(self) -> int:
        return len(
            _unique_values(
                source_trace_id
                for row in self.rows
                for source_trace_id in row.release_exception_source_trace_ids
            )
        )

    @property
    def readiness_reconciliation_row_count(self) -> int:
        return len(
            _unique_values(
                row_id
                for row in self.rows
                for row_id in row.readiness_reconciliation_row_ids
            )
        )

    @property
    def terminal_exception_count(self) -> int:
        return len(
            _unique_values(
                exception_id
                for row in self.rows
                for exception_id in row.terminal_exception_ids
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
            "source_id": SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_AUDIT_SOURCE_ID,
            "required_evidence_ids": list(
                SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "subject_count": self.subject_count,
                "ready_subject_count": self.ready_subject_count,
                "pack_subject_count": self.pack_subject_count,
                "family_subject_count": self.family_subject_count,
                "subject_trace_count": self.subject_trace_count,
                "unique_source_trace_count": self.unique_source_trace_count,
                "readiness_reconciliation_row_count": (
                    self.readiness_reconciliation_row_count
                ),
                "terminal_exception_count": self.terminal_exception_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_boundary_subject_release_dossier_audit_report(
    *,
    project_root: Path | str | None = None,
) -> SceneBoundarySubjectReleaseDossierAuditReport:
    guarded_report = build_scene_boundary_guarded_completion_audit_report(
        project_root=project_root
    )
    readiness_report = build_scene_boundary_readiness_reconciliation_audit_report(
        project_root=project_root
    )
    terminal_report = build_scene_terminal_release_exception_audit_report(
        project_root=project_root
    )
    rows = tuple(
        _row_for_guarded_subject(
            guarded_row,
            readiness_rows=readiness_report.rows,
            terminal_rows=terminal_report.rows,
        )
        for guarded_row in guarded_report.rows
    )
    issues: list[SceneBoundarySubjectReleaseDossierIssue] = []
    for row in rows:
        issues.extend(
            SceneBoundarySubjectReleaseDossierIssue(
                row.subject_key,
                issue_id,
                f"Boundary subject release dossier {row.subject_key} failed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneBoundarySubjectReleaseDossierAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
    )


def audit_scene_boundary_subject_release_dossier_report(
    report: SceneBoundarySubjectReleaseDossierAuditReport | None = None,
) -> tuple[SceneBoundarySubjectReleaseDossierIssue, ...]:
    current = report or build_scene_boundary_subject_release_dossier_audit_report()
    return current.issues


def _row_for_guarded_subject(
    guarded_row,
    *,
    readiness_rows,
    terminal_rows,
) -> SceneBoundarySubjectReleaseDossierRow:
    subject_key = f"{guarded_row.subject_type}:{guarded_row.subject_id}"
    matched_readiness_rows = tuple(
        row
        for row in readiness_rows
        if subject_key in row.linked_boundary_subject_ids
    )
    terminal_trace_pairs = tuple(
        (terminal_row.exception_id, trace)
        for terminal_row in terminal_rows
        for trace in terminal_row.trace_rows
        if subject_key in trace.linked_boundary_subject_ids
    )
    issue_ids = _issue_ids_for_subject(
        guarded_row=guarded_row,
        readiness_rows=matched_readiness_rows,
        terminal_trace_pairs=terminal_trace_pairs,
    )
    return SceneBoundarySubjectReleaseDossierRow(
        subject_type=guarded_row.subject_type,
        subject_id=guarded_row.subject_id,
        status="release_dossier_ready" if not issue_ids else "release_dossier_gap",
        readiness_level=guarded_row.readiness_level,
        maturity_status=guarded_row.maturity_status,
        retained_gap_ids=tuple(guarded_row.remaining_gap_ids),
        boundary_capability_ids=tuple(guarded_row.boundary_capability_ids),
        plugin_gate_ids=tuple(guarded_row.plugin_gate_ids),
        external_handoff_contract_ids=tuple(guarded_row.external_handoff_contract_ids),
        target_plugin_ids=tuple(guarded_row.target_plugin_ids),
        readiness_reconciliation_row_ids=tuple(
            row.row_id for row in matched_readiness_rows
        ),
        terminal_exception_ids=_unique_values(
            exception_id for exception_id, _trace in terminal_trace_pairs
        ),
        release_exception_trace_ids=tuple(
            trace.trace_id for _exception_id, trace in terminal_trace_pairs
        ),
        release_exception_source_trace_ids=tuple(
            trace.source_trace_id for _exception_id, trace in terminal_trace_pairs
        ),
        risk_domain_ids=tuple(guarded_row.risk_domain_ids),
        excluded_core_claims=tuple(guarded_row.excluded_core_claims),
        evidence_ids=SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_REQUIRED_EVIDENCE_IDS,
        issue_ids=issue_ids,
    )


def _issue_ids_for_subject(
    *,
    guarded_row,
    readiness_rows,
    terminal_trace_pairs,
) -> tuple[str, ...]:
    issue_ids: list[str] = []
    if guarded_row.status != "boundary_guarded_complete":
        issue_ids.append("boundary_guarded_completion_not_ready")
    if guarded_row.readiness_level != "blue_boundary":
        issue_ids.append("readiness_not_blue_boundary")
    if guarded_row.maturity_status != "boundary_guarded":
        issue_ids.append("maturity_not_boundary_guarded")
    if not guarded_row.remaining_gap_ids:
        issue_ids.append("missing_retained_gap")
    if not guarded_row.boundary_capability_ids:
        issue_ids.append("missing_boundary_capability")
    if not guarded_row.external_handoff_contract_ids:
        issue_ids.append("missing_external_handoff_contract")
    if not guarded_row.excluded_core_claims:
        issue_ids.append("missing_excluded_core_claims")
    if not readiness_rows:
        issue_ids.append("missing_readiness_reconciliation_trace")
    if not terminal_trace_pairs:
        issue_ids.append("missing_terminal_release_exception_trace")
    return tuple(issue_ids)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneBoundarySubjectReleaseDossierSourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneBoundarySubjectReleaseDossierSourceEvidence] = []
    for source_id, source_path, markers in (
        SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_SOURCE_MARKERS
    ):
        path = Path(source_path)
        if not path.is_absolute():
            path = root / source_path
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneBoundarySubjectReleaseDossierSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneBoundarySubjectReleaseDossierSourceEvidence, ...],
) -> tuple[SceneBoundarySubjectReleaseDossierIssue, ...]:
    return tuple(
        SceneBoundarySubjectReleaseDossierIssue(
            evidence.source_id,
            "missing_source_evidence",
            (
                f"{evidence.source_path} missing markers: "
                f"{', '.join(evidence.missing_markers)}"
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
    "SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_AUDIT_SOURCE_ID",
    "SCENE_BOUNDARY_SUBJECT_RELEASE_DOSSIER_REQUIRED_EVIDENCE_IDS",
    "SceneBoundarySubjectReleaseDossierAuditReport",
    "SceneBoundarySubjectReleaseDossierIssue",
    "SceneBoundarySubjectReleaseDossierRow",
    "SceneBoundarySubjectReleaseDossierSourceEvidence",
    "audit_scene_boundary_subject_release_dossier_report",
    "build_scene_boundary_subject_release_dossier_audit_report",
]
