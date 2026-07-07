"""Boundary maturity release-envelope audit for the scene matrix.

N2.392 keeps the remaining Blue/Boundary maturity blockers honest without
promoting them to Green/L5.  Each retained blocker must be packaged as a
release envelope that links product maturity, external handoff, guarded
completion, readiness reconciliation, terminal release trace, subject dossier,
and subject-continuity evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.scene_boundary_guarded_completion_audit import (
    build_scene_boundary_guarded_completion_audit_report,
)
from src.config.scene_boundary_subject_release_continuity_audit import (
    build_scene_boundary_subject_release_continuity_audit_report,
)
from src.config.scene_boundary_subject_release_dossier_audit import (
    build_scene_boundary_subject_release_dossier_audit_report,
)
from src.config.scene_external_handoff_contract_audit import (
    build_scene_external_handoff_contract_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (
    build_scene_product_maturity_upgrade_audit_report,
)


SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_AUDIT_SOURCE_ID = (
    "scene_boundary_maturity_release_envelope_audit"
)

SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "maturity_boundary_gap",
    "external_handoff_contract",
    "boundary_guarded_completion",
    "readiness_reconciliation",
    "terminal_release_trace",
    "boundary_subject_release_dossier",
    "boundary_subject_release_continuity",
)

SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "boundary_maturity_release_envelope_registry",
        "src/config/scene_boundary_maturity_release_envelope_audit.py",
        (
            "SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_REQUIRED_EVIDENCE_IDS",
            "boundary_maturity_release_envelope",
            "maturity_boundary_gap",
        ),
    ),
    (
        "maturity_upgrade",
        "src/config/scene_product_maturity_upgrade_audit.py",
        ("maturity_upgrade_l5_blocked_subject_count", "blue_boundary"),
    ),
    (
        "external_handoff_contract",
        "src/config/scene_external_handoff_contract_audit.py",
        ("SceneExternalHandoffContractRow", "gap_id", "external_receipt_id"),
    ),
    (
        "boundary_guarded_completion",
        "src/config/scene_boundary_guarded_completion_audit.py",
        ("boundary_guarded_complete", "remaining_gap_ids"),
    ),
    (
        "boundary_subject_release_dossier",
        "src/config/scene_boundary_subject_release_dossier_audit.py",
        ("retained_gap_ids", "release_exception_trace_ids"),
    ),
    (
        "boundary_subject_release_continuity",
        "src/config/scene_boundary_subject_release_continuity_audit.py",
        ("boundary_subject_release_continuity", "terminal_trace_ids"),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_AUDIT_SOURCE_ID,
            "boundary_maturity_release_envelope_ready_count",
        ),
    ),
    (
        "scene_matrix_drilldown",
        "src/config/scene_matrix_drilldown_release_items.py",
        (
            SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_AUDIT_SOURCE_ID,
            "boundary_maturity_release_envelope",
        ),
    ),
    (
        "summary_projection",
        "src/ui/panels/scene_summary_projection.py",
        (
            "boundary_maturity_release_envelope_ready_count",
            "boundary release envelopes",
            "L5 blockers enveloped",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_AUDIT_SOURCE_ID,
            "scene_boundary_maturity_release_envelope_ready_count",
            "maturity_l5_enveloped=",
            "retained_gaps=",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_boundary_maturity_release_envelope_audit.py",
        (
            "build_scene_boundary_maturity_release_envelope_audit_report",
            "Envelopes ready",
            "row.envelope_id",
            "row.external_handoff_contract_id",
            "row.subject_continuity_status",
            "row.evidence_ids",
            "json",
            "markdown",
        ),
    ),
    (
        "workflow",
        ".github/workflows/scene-matrix-release-gate.yml",
        ("tests/test_scene_boundary_maturity_release_envelope_audit.py",),
    ),
    (
        "n2_392_plan",
        "docs/audits/高层场景能力矩阵N2_392边界成熟度发布保留项证据封套闭环_2026-06-24.md",
        ("N2.392", "boundary_maturity_release_envelope", "6/6"),
    ),
    (
        "n2_393e_plan",
        "docs/audits/高层场景能力矩阵N2_393e保留Gap封套读数归因补充_2026-06-25.md",
        ("N2.393e", "retained_gaps=6/6 enveloped", "retained_gap_count"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneBoundaryMaturityReleaseEnvelopeIssue:
    envelope_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "envelope_id": self.envelope_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneBoundaryMaturityReleaseEnvelopeSourceEvidence:
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
class SceneBoundaryMaturityReleaseEnvelopeRow:
    envelope_id: str
    subject_type: str
    subject_id: str
    gap_id: str
    status: str
    external_handoff_contract_id: str
    guarded_completion_status: str
    readiness_row_ids: tuple[str, ...]
    terminal_trace_ids: tuple[str, ...]
    dossier_trace_ids: tuple[str, ...]
    release_dossier_status: str
    subject_continuity_status: str
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status == "release_envelope_ready"

    def to_payload(self) -> dict[str, object]:
        return {
            "envelope_id": self.envelope_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "gap_id": self.gap_id,
            "status": self.status,
            "external_handoff_contract_id": self.external_handoff_contract_id,
            "guarded_completion_status": self.guarded_completion_status,
            "readiness_row_ids": list(self.readiness_row_ids),
            "terminal_trace_ids": list(self.terminal_trace_ids),
            "dossier_trace_ids": list(self.dossier_trace_ids),
            "release_dossier_status": self.release_dossier_status,
            "subject_continuity_status": self.subject_continuity_status,
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneBoundaryMaturityReleaseEnvelopeAuditReport:
    rows: tuple[SceneBoundaryMaturityReleaseEnvelopeRow, ...]
    issues: tuple[SceneBoundaryMaturityReleaseEnvelopeIssue, ...]
    source_evidence: tuple[SceneBoundaryMaturityReleaseEnvelopeSourceEvidence, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def envelope_count(self) -> int:
        return len(self.rows)

    @property
    def ready_envelope_count(self) -> int:
        return sum(1 for row in self.rows if row.is_ready)

    @property
    def l5_blocker_enveloped_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.is_ready and "missing_maturity_gap" not in row.issue_ids
        )

    @property
    def maturity_boundary_count(self) -> int:
        return sum(1 for row in self.rows if "missing_maturity_gap" not in row.issue_ids)

    @property
    def external_handoff_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_external_handoff_contract" not in row.issue_ids
        )

    @property
    def guarded_completion_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_guarded_completion" not in row.issue_ids
        )

    @property
    def readiness_reconciliation_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_readiness_reconciliation" not in row.issue_ids
        )

    @property
    def terminal_trace_count(self) -> int:
        return sum(1 for row in self.rows if "missing_terminal_trace" not in row.issue_ids)

    @property
    def release_dossier_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_subject_release_dossier" not in row.issue_ids
        )

    @property
    def subject_continuity_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_subject_continuity" not in row.issue_ids
        )

    @property
    def retained_gap_count(self) -> int:
        return len(_unique_values(row.gap_id for row in self.rows))

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_AUDIT_SOURCE_ID,
            "required_evidence_ids": list(
                SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "envelope_count": self.envelope_count,
                "ready_envelope_count": self.ready_envelope_count,
                "l5_blocker_enveloped_count": self.l5_blocker_enveloped_count,
                "maturity_boundary_count": self.maturity_boundary_count,
                "external_handoff_count": self.external_handoff_count,
                "guarded_completion_count": self.guarded_completion_count,
                "readiness_reconciliation_count": self.readiness_reconciliation_count,
                "terminal_trace_count": self.terminal_trace_count,
                "release_dossier_count": self.release_dossier_count,
                "subject_continuity_count": self.subject_continuity_count,
                "retained_gap_count": self.retained_gap_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_boundary_maturity_release_envelope_audit_report(
    *,
    project_root: Path | str | None = None,
) -> SceneBoundaryMaturityReleaseEnvelopeAuditReport:
    maturity_report = build_scene_product_maturity_upgrade_audit_report(
        project_root=project_root
    )
    handoff_report = build_scene_external_handoff_contract_audit_report(
        project_root=project_root
    )
    guarded_report = build_scene_boundary_guarded_completion_audit_report(
        project_root=project_root
    )
    dossier_report = build_scene_boundary_subject_release_dossier_audit_report(
        project_root=project_root
    )
    continuity_report = build_scene_boundary_subject_release_continuity_audit_report(
        project_root=project_root
    )

    handoff_by_subject_gap = {
        (row.subject_type, row.subject_id, row.gap_id): row for row in handoff_report.rows
    }
    guarded_by_subject = {
        (row.subject_type, row.subject_id): row for row in guarded_report.rows
    }
    dossier_by_subject = {
        (row.subject_type, row.subject_id): row for row in dossier_report.rows
    }
    continuity_by_subject = {
        (row.subject_type, row.subject_id): row for row in continuity_report.rows
    }

    rows = tuple(
        _row_for_gap(
            maturity_row,
            gap_id,
            handoff_by_subject_gap=handoff_by_subject_gap,
            guarded_by_subject=guarded_by_subject,
            dossier_by_subject=dossier_by_subject,
            continuity_by_subject=continuity_by_subject,
        )
        for maturity_row in maturity_report.rows
        if maturity_row.is_boundary
        for gap_id in maturity_row.remaining_product_gaps
    )
    issues: list[SceneBoundaryMaturityReleaseEnvelopeIssue] = []
    for row in rows:
        issues.extend(
            SceneBoundaryMaturityReleaseEnvelopeIssue(
                row.envelope_id,
                issue_id,
                f"Boundary maturity release envelope {row.envelope_id} failed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneBoundaryMaturityReleaseEnvelopeAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
    )


def audit_scene_boundary_maturity_release_envelope_report(
    report: SceneBoundaryMaturityReleaseEnvelopeAuditReport | None = None,
) -> tuple[SceneBoundaryMaturityReleaseEnvelopeIssue, ...]:
    current = report or build_scene_boundary_maturity_release_envelope_audit_report()
    return current.issues


def _row_for_gap(
    maturity_row,
    gap_id: str,
    *,
    handoff_by_subject_gap: dict[tuple[str, str, str], object],
    guarded_by_subject: dict[tuple[str, str], object],
    dossier_by_subject: dict[tuple[str, str], object],
    continuity_by_subject: dict[tuple[str, str], object],
) -> SceneBoundaryMaturityReleaseEnvelopeRow:
    subject_key = (maturity_row.subject_type, maturity_row.subject_id)
    envelope_id = f"{maturity_row.subject_type}:{maturity_row.subject_id}:{gap_id}"
    handoff_row = handoff_by_subject_gap.get((*subject_key, gap_id))
    guarded_row = guarded_by_subject.get(subject_key)
    dossier_row = dossier_by_subject.get(subject_key)
    continuity_row = continuity_by_subject.get(subject_key)
    issue_ids: list[str] = []

    if not gap_id:
        issue_ids.append("missing_maturity_gap")
    if handoff_row is None:
        issue_ids.append("missing_external_handoff_contract")
    if guarded_row is None:
        issue_ids.append("missing_guarded_completion")
    elif gap_id not in guarded_row.remaining_gap_ids:
        issue_ids.append("guarded_completion_gap_mismatch")
    if continuity_row is None:
        issue_ids.append("missing_subject_continuity")
    else:
        if not continuity_row.in_readiness_reconciliation:
            issue_ids.append("missing_readiness_reconciliation")
        if not continuity_row.in_terminal_release_exception:
            issue_ids.append("missing_terminal_trace")
        if not continuity_row.in_subject_dossier:
            issue_ids.append("missing_subject_release_dossier")
        if continuity_row.issue_ids:
            issue_ids.append("subject_continuity_gap")
    if dossier_row is None:
        issue_ids.append("missing_subject_release_dossier")
    elif gap_id not in dossier_row.retained_gap_ids:
        issue_ids.append("release_dossier_gap_mismatch")

    readiness_row_ids = (
        tuple(continuity_row.readiness_row_ids) if continuity_row is not None else ()
    )
    terminal_trace_ids = (
        tuple(continuity_row.terminal_trace_ids) if continuity_row is not None else ()
    )
    dossier_trace_ids = (
        tuple(continuity_row.dossier_trace_ids) if continuity_row is not None else ()
    )
    return SceneBoundaryMaturityReleaseEnvelopeRow(
        envelope_id=envelope_id,
        subject_type=maturity_row.subject_type,
        subject_id=maturity_row.subject_id,
        gap_id=gap_id,
        status="release_envelope_ready" if not issue_ids else "release_envelope_gap",
        external_handoff_contract_id=(
            handoff_row.contract_id if handoff_row is not None else ""
        ),
        guarded_completion_status=guarded_row.status if guarded_row is not None else "",
        readiness_row_ids=readiness_row_ids,
        terminal_trace_ids=terminal_trace_ids,
        dossier_trace_ids=dossier_trace_ids,
        release_dossier_status=dossier_row.status if dossier_row is not None else "",
        subject_continuity_status=(
            continuity_row.status if continuity_row is not None else ""
        ),
        evidence_ids=SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_REQUIRED_EVIDENCE_IDS,
        issue_ids=tuple(_unique_values(issue_ids)),
    )


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneBoundaryMaturityReleaseEnvelopeSourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneBoundaryMaturityReleaseEnvelopeSourceEvidence] = []
    for source_id, source_path, markers in (
        SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_SOURCE_MARKERS
    ):
        text = _read_text(root / source_path)
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneBoundaryMaturityReleaseEnvelopeSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneBoundaryMaturityReleaseEnvelopeSourceEvidence, ...],
) -> tuple[SceneBoundaryMaturityReleaseEnvelopeIssue, ...]:
    return tuple(
        SceneBoundaryMaturityReleaseEnvelopeIssue(
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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _unique_values(values) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_AUDIT_SOURCE_ID",
    "SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE_REQUIRED_EVIDENCE_IDS",
    "SceneBoundaryMaturityReleaseEnvelopeAuditReport",
    "SceneBoundaryMaturityReleaseEnvelopeIssue",
    "SceneBoundaryMaturityReleaseEnvelopeRow",
    "SceneBoundaryMaturityReleaseEnvelopeSourceEvidence",
    "audit_scene_boundary_maturity_release_envelope_report",
    "build_scene_boundary_maturity_release_envelope_audit_report",
]
