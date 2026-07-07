"""Release-trace partition guard audit for the scene matrix.

N2.387 closes the row-level release ledger by proving that every terminal
release trace is owned by exactly one partition: a boundary-subject release
dossier or an explicitly attributed non-subject trace.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_boundary_subject_release_dossier_audit import (
    build_scene_boundary_subject_release_dossier_audit_report,
)
from src.config.scene_non_subject_release_trace_attribution_audit import (
    build_scene_non_subject_release_trace_attribution_audit_report,
)
from src.config.scene_terminal_release_exception_audit import (
    build_scene_terminal_release_exception_audit_report,
)


SCENE_RELEASE_TRACE_PARTITION_GUARD_AUDIT_SOURCE_ID = (
    "scene_release_trace_partition_guard_audit"
)

SCENE_RELEASE_TRACE_PARTITION_GUARD_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "terminal_release_exception_trace",
    "boundary_subject_release_dossier_trace",
    "non_subject_trace_attribution",
    "complete_trace_partition",
    "mutually_exclusive_trace_partition",
)

SCENE_RELEASE_TRACE_PARTITION_GUARD_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "release_trace_partition_guard_registry",
        "src/config/scene_release_trace_partition_guard_audit.py",
        (
            "SCENE_RELEASE_TRACE_PARTITION_GUARD_REQUIRED_EVIDENCE_IDS",
            "release_trace_partition_guard",
            "missing_trace_count",
        ),
    ),
    (
        "terminal_release_exception",
        "src/config/scene_terminal_release_exception_audit.py",
        (
            "build_scene_terminal_release_exception_audit_report",
            "SceneTerminalReleaseExceptionTrace",
            "trace_rows",
        ),
    ),
    (
        "boundary_subject_release_dossier",
        "src/config/scene_boundary_subject_release_dossier_audit.py",
        (
            "build_scene_boundary_subject_release_dossier_audit_report",
            "release_exception_trace_ids",
        ),
    ),
    (
        "non_subject_release_trace_attribution",
        "src/config/scene_non_subject_release_trace_attribution_audit.py",
        (
            "build_scene_non_subject_release_trace_attribution_audit_report",
            "SceneNonSubjectReleaseTraceAttributionRow",
            "trace_id",
        ),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_RELEASE_TRACE_PARTITION_GUARD_AUDIT_SOURCE_ID,
            "release_trace_partition_guard_partitioned_trace_count",
        ),
    ),
    (
        "scene_matrix_drilldown",
        "src/config/scene_matrix_drilldown_release_items.py",
        (
            SCENE_RELEASE_TRACE_PARTITION_GUARD_AUDIT_SOURCE_ID,
            "release_trace_partition_guard",
        ),
    ),
    (
        "summary_projection",
        "src/ui/panels/scene_summary_projection.py",
        (
            "release_trace_partition_guard_partitioned_trace_count",
            "trace partition",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_RELEASE_TRACE_PARTITION_GUARD_AUDIT_SOURCE_ID,
            "scene_release_trace_partition_guard_partitioned_trace_count",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_release_trace_partition_guard_audit.py",
        (
            "build_scene_release_trace_partition_guard_audit_report",
            "Partitioned traces",
            "row.partition_id",
            "row.trace_count",
            "row.expected_trace_count",
            "row.evidence_ids",
            "json",
            "markdown",
        ),
    ),
    (
        "n2_387_plan",
        "docs/audits/高层场景能力矩阵N2_387发布Trace分区守门闭环_2026-06-24.md",
        ("N2.387", "release_trace_partition_guard", "36/36"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneReleaseTracePartitionGuardIssue:
    partition_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "partition_id": self.partition_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseTracePartitionGuardSourceEvidence:
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
class SceneReleaseTracePartitionGuardRow:
    partition_id: str
    label: str
    status: str
    trace_count: int
    expected_trace_count: int
    trace_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status == "partition_ready"

    def to_payload(self) -> dict[str, object]:
        return {
            "partition_id": self.partition_id,
            "label": self.label,
            "status": self.status,
            "trace_count": self.trace_count,
            "expected_trace_count": self.expected_trace_count,
            "trace_ids": list(self.trace_ids),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseTracePartitionGuardAuditReport:
    rows: tuple[SceneReleaseTracePartitionGuardRow, ...]
    issues: tuple[SceneReleaseTracePartitionGuardIssue, ...]
    source_evidence: tuple[SceneReleaseTracePartitionGuardSourceEvidence, ...]
    terminal_trace_ids: tuple[str, ...]
    subject_trace_ids: tuple[str, ...]
    non_subject_trace_ids: tuple[str, ...]
    missing_trace_ids: tuple[str, ...]
    overlap_trace_ids: tuple[str, ...]
    extra_trace_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def partition_count(self) -> int:
        return len(self.rows)

    @property
    def ready_partition_count(self) -> int:
        return sum(1 for row in self.rows if row.is_ready)

    @property
    def terminal_trace_count(self) -> int:
        return len(self.terminal_trace_ids)

    @property
    def subject_trace_count(self) -> int:
        return len(self.subject_trace_ids)

    @property
    def non_subject_trace_count(self) -> int:
        return len(self.non_subject_trace_ids)

    @property
    def partitioned_trace_count(self) -> int:
        return len(set(self.subject_trace_ids) | set(self.non_subject_trace_ids))

    @property
    def missing_trace_count(self) -> int:
        return len(self.missing_trace_ids)

    @property
    def overlap_trace_count(self) -> int:
        return len(self.overlap_trace_ids)

    @property
    def extra_trace_count(self) -> int:
        return len(self.extra_trace_ids)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_RELEASE_TRACE_PARTITION_GUARD_AUDIT_SOURCE_ID,
            "required_evidence_ids": list(
                SCENE_RELEASE_TRACE_PARTITION_GUARD_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "partition_count": self.partition_count,
                "ready_partition_count": self.ready_partition_count,
                "terminal_trace_count": self.terminal_trace_count,
                "subject_trace_count": self.subject_trace_count,
                "non_subject_trace_count": self.non_subject_trace_count,
                "partitioned_trace_count": self.partitioned_trace_count,
                "missing_trace_count": self.missing_trace_count,
                "overlap_trace_count": self.overlap_trace_count,
                "extra_trace_count": self.extra_trace_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "trace_partitions": {
                "terminal_trace_ids": list(self.terminal_trace_ids),
                "subject_trace_ids": list(self.subject_trace_ids),
                "non_subject_trace_ids": list(self.non_subject_trace_ids),
                "missing_trace_ids": list(self.missing_trace_ids),
                "overlap_trace_ids": list(self.overlap_trace_ids),
                "extra_trace_ids": list(self.extra_trace_ids),
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_release_trace_partition_guard_audit_report(
    *,
    project_root: Path | str | None = None,
) -> SceneReleaseTracePartitionGuardAuditReport:
    terminal_report = build_scene_terminal_release_exception_audit_report(
        project_root=project_root
    )
    subject_report = build_scene_boundary_subject_release_dossier_audit_report(
        project_root=project_root
    )
    non_subject_report = (
        build_scene_non_subject_release_trace_attribution_audit_report(
            project_root=project_root
        )
    )
    terminal_trace_ids = _unique_values(
        trace.trace_id for row in terminal_report.rows for trace in row.trace_rows
    )
    subject_trace_ids = _unique_values(
        trace_id
        for row in subject_report.rows
        for trace_id in row.release_exception_trace_ids
    )
    non_subject_trace_ids = _unique_values(row.trace_id for row in non_subject_report.rows)
    terminal_set = set(terminal_trace_ids)
    subject_set = set(subject_trace_ids)
    non_subject_set = set(non_subject_trace_ids)
    partitioned_set = subject_set | non_subject_set
    missing_trace_ids = tuple(sorted(terminal_set - partitioned_set))
    overlap_trace_ids = tuple(sorted(subject_set & non_subject_set))
    extra_trace_ids = tuple(sorted(partitioned_set - terminal_set))

    rows = _partition_rows(
        terminal_trace_ids=terminal_trace_ids,
        subject_trace_ids=subject_trace_ids,
        non_subject_trace_ids=non_subject_trace_ids,
        missing_trace_ids=missing_trace_ids,
        overlap_trace_ids=overlap_trace_ids,
        extra_trace_ids=extra_trace_ids,
    )
    issues: list[SceneReleaseTracePartitionGuardIssue] = []
    for row in rows:
        issues.extend(
            SceneReleaseTracePartitionGuardIssue(
                row.partition_id,
                issue_id,
                f"Release trace partition {row.partition_id} failed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    if missing_trace_ids:
        issues.append(
            SceneReleaseTracePartitionGuardIssue(
                "terminal_release_trace_total",
                "missing_partitioned_trace",
                (
                    "Terminal release traces missing from subject/non-subject "
                    f"partitions: {', '.join(missing_trace_ids)}."
                ),
            )
        )
    if overlap_trace_ids:
        issues.append(
            SceneReleaseTracePartitionGuardIssue(
                "release_trace_partition",
                "overlap_partitioned_trace",
                (
                    "Release traces appear in both subject and non-subject "
                    f"partitions: {', '.join(overlap_trace_ids)}."
                ),
            )
        )
    if extra_trace_ids:
        issues.append(
            SceneReleaseTracePartitionGuardIssue(
                "release_trace_partition",
                "extra_partitioned_trace",
                (
                    "Subject/non-subject partitions contain traces absent from "
                    f"the terminal release ledger: {', '.join(extra_trace_ids)}."
                ),
            )
        )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneReleaseTracePartitionGuardAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
        terminal_trace_ids=terminal_trace_ids,
        subject_trace_ids=subject_trace_ids,
        non_subject_trace_ids=non_subject_trace_ids,
        missing_trace_ids=missing_trace_ids,
        overlap_trace_ids=overlap_trace_ids,
        extra_trace_ids=extra_trace_ids,
    )


def audit_scene_release_trace_partition_guard_report(
    report: SceneReleaseTracePartitionGuardAuditReport | None = None,
) -> tuple[SceneReleaseTracePartitionGuardIssue, ...]:
    current = report or build_scene_release_trace_partition_guard_audit_report()
    return current.issues


def _partition_rows(
    *,
    terminal_trace_ids: tuple[str, ...],
    subject_trace_ids: tuple[str, ...],
    non_subject_trace_ids: tuple[str, ...],
    missing_trace_ids: tuple[str, ...],
    overlap_trace_ids: tuple[str, ...],
    extra_trace_ids: tuple[str, ...],
) -> tuple[SceneReleaseTracePartitionGuardRow, ...]:
    terminal_issue_ids = _issue_ids(
        missing_trace_ids,
        issue_id="missing_partitioned_trace",
    ) + _issue_ids(extra_trace_ids, issue_id="extra_partitioned_trace")
    subject_issue_ids = _issue_ids(
        overlap_trace_ids,
        issue_id="overlap_partitioned_trace",
    ) + _issue_ids(
        tuple(trace_id for trace_id in subject_trace_ids if trace_id in extra_trace_ids),
        issue_id="subject_trace_not_in_terminal",
    )
    non_subject_issue_ids = _issue_ids(
        overlap_trace_ids,
        issue_id="overlap_partitioned_trace",
    ) + _issue_ids(
        tuple(
            trace_id
            for trace_id in non_subject_trace_ids
            if trace_id in extra_trace_ids
        ),
        issue_id="non_subject_trace_not_in_terminal",
    )
    return (
        _partition_row(
            "terminal_release_trace_total",
            "Terminal release trace total",
            terminal_trace_ids,
            len(terminal_trace_ids),
            terminal_issue_ids,
        ),
        _partition_row(
            "subject_release_trace_partition",
            "Subject release trace partition",
            subject_trace_ids,
            len(subject_trace_ids),
            subject_issue_ids,
        ),
        _partition_row(
            "non_subject_release_trace_partition",
            "Non-subject release trace partition",
            non_subject_trace_ids,
            len(non_subject_trace_ids),
            non_subject_issue_ids,
        ),
    )


def _partition_row(
    partition_id: str,
    label: str,
    trace_ids: tuple[str, ...],
    expected_trace_count: int,
    issue_ids: tuple[str, ...],
) -> SceneReleaseTracePartitionGuardRow:
    return SceneReleaseTracePartitionGuardRow(
        partition_id=partition_id,
        label=label,
        status="partition_ready" if not issue_ids else "partition_gap",
        trace_count=len(trace_ids),
        expected_trace_count=expected_trace_count,
        trace_ids=trace_ids,
        evidence_ids=SCENE_RELEASE_TRACE_PARTITION_GUARD_REQUIRED_EVIDENCE_IDS,
        issue_ids=issue_ids,
    )


def _issue_ids(
    trace_ids: tuple[str, ...],
    *,
    issue_id: str,
) -> tuple[str, ...]:
    return (issue_id,) if trace_ids else ()


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneReleaseTracePartitionGuardSourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneReleaseTracePartitionGuardSourceEvidence] = []
    for source_id, source_path, markers in (
        SCENE_RELEASE_TRACE_PARTITION_GUARD_SOURCE_MARKERS
    ):
        path = Path(source_path)
        if not path.is_absolute():
            path = root / source_path
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneReleaseTracePartitionGuardSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneReleaseTracePartitionGuardSourceEvidence, ...],
) -> tuple[SceneReleaseTracePartitionGuardIssue, ...]:
    return tuple(
        SceneReleaseTracePartitionGuardIssue(
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
    "SCENE_RELEASE_TRACE_PARTITION_GUARD_AUDIT_SOURCE_ID",
    "SCENE_RELEASE_TRACE_PARTITION_GUARD_REQUIRED_EVIDENCE_IDS",
    "SceneReleaseTracePartitionGuardAuditReport",
    "SceneReleaseTracePartitionGuardIssue",
    "SceneReleaseTracePartitionGuardRow",
    "SceneReleaseTracePartitionGuardSourceEvidence",
    "audit_scene_release_trace_partition_guard_report",
    "build_scene_release_trace_partition_guard_audit_report",
]
