"""Terminal release-exception ledger for the scene matrix.

N2.383 ties together the managed warning, readiness reconciliation, and
boundary-guarded maturity audits so release-gate residual states are visible as
governed exceptions instead of scattered counters.
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
from src.config.scene_product_maturity_upgrade_audit import (
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_residual_warning_governance_audit import (
    build_scene_residual_warning_governance_audit_report,
)


SCENE_TERMINAL_RELEASE_EXCEPTION_AUDIT_SOURCE_ID = (
    "scene_terminal_release_exception_audit"
)

SCENE_TERMINAL_RELEASE_EXCEPTION_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "managed_warning_governance",
    "readiness_delta_reconciliation",
    "boundary_guarded_completion",
    "release_gate_projection",
    "row_level_exception_trace",
)


@dataclass(frozen=True, slots=True)
class SceneTerminalReleaseExceptionSpec:
    exception_id: str
    exception_kind: str
    source_ids: tuple[str, ...]
    reason: str
    evidence_ids: tuple[str, ...]


SCENE_TERMINAL_RELEASE_EXCEPTION_SPECS: tuple[
    SceneTerminalReleaseExceptionSpec, ...
] = (
    SceneTerminalReleaseExceptionSpec(
        exception_id="managed_residual_warnings",
        exception_kind="warning_exception",
        source_ids=("scene_residual_warning_governance_audit",),
        reason="All residual warnings must be explicitly managed.",
        evidence_ids=("managed_warning_governance",),
    ),
    SceneTerminalReleaseExceptionSpec(
        exception_id="dashboard_warning_projection",
        exception_kind="warning_projection_exception",
        source_ids=(
            "scene_residual_warning_governance_audit",
            "scene_matrix_dashboard",
        ),
        reason="Dashboard warnings must mirror managed source warnings.",
        evidence_ids=("managed_warning_governance", "dashboard_projection_trace"),
    ),
    SceneTerminalReleaseExceptionSpec(
        exception_id="boundary_readiness_reconciliation",
        exception_kind="readiness_exception",
        source_ids=("scene_boundary_readiness_reconciliation_audit",),
        reason="Non-full readiness counters must be reconciled.",
        evidence_ids=("readiness_delta_reconciliation",),
    ),
    SceneTerminalReleaseExceptionSpec(
        exception_id="boundary_guarded_maturity",
        exception_kind="maturity_exception",
        source_ids=(
            "scene_boundary_guarded_completion_audit",
            "scene_product_maturity_upgrade_audit",
        ),
        reason="L5-blocked boundary subjects must be guarded, not hidden.",
        evidence_ids=("boundary_guarded_completion",),
    ),
    SceneTerminalReleaseExceptionSpec(
        exception_id="static_closed_boundary",
        exception_kind="readiness_level_exception",
        source_ids=(
            "scene_boundary_readiness_reconciliation_audit",
            "scene_product_readiness",
        ),
        reason="Static-closed Blue/Boundary subjects must not be promoted to Green/L5.",
        evidence_ids=("readiness_delta_reconciliation", "product_readiness_boundary"),
    ),
)


SCENE_TERMINAL_RELEASE_EXCEPTION_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]], ...
] = (
    (
        "terminal_exception_registry",
        "src/config/scene_terminal_release_exception_audit.py",
        (
            "SCENE_TERMINAL_RELEASE_EXCEPTION_SPECS",
            "SceneTerminalReleaseExceptionTrace",
            "managed_warning_governance",
            "row_level_exception_trace",
            "release_gate_projection",
        ),
    ),
    (
        "residual_warning_governance",
        "src/config/scene_residual_warning_governance_audit.py",
        ("managed_warning_count", "unmanaged_warning_count"),
    ),
    (
        "boundary_readiness_reconciliation",
        "src/config/scene_boundary_readiness_reconciliation_audit.py",
        ("reconciled_count", "unreconciled_count"),
    ),
    (
        "boundary_guarded_completion",
        "src/config/scene_boundary_guarded_completion_audit.py",
        ("boundary_guarded_complete", "ready_subject_count"),
    ),
    (
        "product_maturity_upgrade",
        "src/config/scene_product_maturity_upgrade_audit.py",
        ("l5_blocked_subject_count", "boundary_guarded"),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_TERMINAL_RELEASE_EXCEPTION_AUDIT_SOURCE_ID,
            "terminal_release_exception_count",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_TERMINAL_RELEASE_EXCEPTION_AUDIT_SOURCE_ID,
            "scene_terminal_release_exception_count",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_terminal_release_exception_audit.py",
        (
            "build_scene_terminal_release_exception_audit_report",
            "Governed exceptions",
            "row.exception_id",
            "row.trace_count",
            "row.evidence_ids",
            "json",
            "markdown",
        ),
    ),
    (
        "n2_383_plan",
        "docs/audits/高层场景能力矩阵N2_383发布例外账本闭环_2026-06-24.md",
        ("N2.383", "release_gate_projection", "managed_warning_governance"),
    ),
    (
        "n2_384_plan",
        "docs/audits/高层场景能力矩阵N2_384发布例外账本行级追踪闭环_2026-06-24.md",
        ("N2.384", "row_level_exception_trace", "exception_trace_count"),
    ),
    (
        "n2_393c_plan",
        "docs/audits/高层场景能力矩阵N2_393c静态闭合非绿读数归因补充_2026-06-25.md",
        (
            "N2.393c",
            "static_closed_not_green=2/2 governed",
            "static_closed_boundary",
        ),
    ),
    (
        "n2_393d_plan",
        "docs/audits/高层场景能力矩阵N2_393d看板Warning投影读数归因补充_2026-06-25.md",
        (
            "N2.393d",
            "dashboard_warning_projection=3/3 governed",
            "dashboard_warning_projection",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneTerminalReleaseExceptionIssue:
    exception_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "exception_id": self.exception_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneTerminalReleaseExceptionSourceEvidence:
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
class SceneTerminalReleaseExceptionTrace:
    trace_id: str
    audit_source_id: str
    source_row_id: str
    surface_source_id: str
    scope_type: str
    scope_id: str
    status: str
    linked_pack_ids: tuple[str, ...] = ()
    linked_family_ids: tuple[str, ...] = ()
    linked_boundary_subject_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @property
    def source_trace_id(self) -> str:
        return f"{self.audit_source_id}:{self.source_row_id}"

    def to_payload(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "audit_source_id": self.audit_source_id,
            "source_row_id": self.source_row_id,
            "source_trace_id": self.source_trace_id,
            "surface_source_id": self.surface_source_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "status": self.status,
            "linked_pack_ids": list(self.linked_pack_ids),
            "linked_family_ids": list(self.linked_family_ids),
            "linked_boundary_subject_ids": list(self.linked_boundary_subject_ids),
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneTerminalReleaseExceptionRow:
    exception_id: str
    exception_kind: str
    status: str
    observed_count: int
    governed_count: int
    source_ids: tuple[str, ...]
    reason: str
    evidence_ids: tuple[str, ...]
    trace_rows: tuple[SceneTerminalReleaseExceptionTrace, ...] = ()
    issue_ids: tuple[str, ...] = ()

    @property
    def is_governed(self) -> bool:
        return self.status == "governed"

    @property
    def trace_count(self) -> int:
        return len(self.trace_rows)

    @property
    def trace_ids(self) -> tuple[str, ...]:
        return tuple(trace.trace_id for trace in self.trace_rows)

    @property
    def source_trace_ids(self) -> tuple[str, ...]:
        return tuple(trace.source_trace_id for trace in self.trace_rows)

    @property
    def linked_pack_ids(self) -> tuple[str, ...]:
        return _unique_values(
            pack_id for trace in self.trace_rows for pack_id in trace.linked_pack_ids
        )

    @property
    def linked_family_ids(self) -> tuple[str, ...]:
        return _unique_values(
            family_id
            for trace in self.trace_rows
            for family_id in trace.linked_family_ids
        )

    @property
    def linked_boundary_subject_ids(self) -> tuple[str, ...]:
        return _unique_values(
            subject_id
            for trace in self.trace_rows
            for subject_id in trace.linked_boundary_subject_ids
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "exception_id": self.exception_id,
            "exception_kind": self.exception_kind,
            "status": self.status,
            "observed_count": self.observed_count,
            "governed_count": self.governed_count,
            "trace_count": self.trace_count,
            "source_ids": list(self.source_ids),
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "trace_ids": list(self.trace_ids),
            "source_trace_ids": list(self.source_trace_ids),
            "linked_pack_ids": list(self.linked_pack_ids),
            "linked_family_ids": list(self.linked_family_ids),
            "linked_boundary_subject_ids": list(self.linked_boundary_subject_ids),
            "trace_rows": [trace.to_payload() for trace in self.trace_rows],
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneTerminalReleaseExceptionAuditReport:
    rows: tuple[SceneTerminalReleaseExceptionRow, ...]
    issues: tuple[SceneTerminalReleaseExceptionIssue, ...]
    source_evidence: tuple[SceneTerminalReleaseExceptionSourceEvidence, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def exception_count(self) -> int:
        return len(self.rows)

    @property
    def governed_exception_count(self) -> int:
        return sum(1 for row in self.rows if row.is_governed)

    @property
    def ungoverned_exception_count(self) -> int:
        return sum(1 for row in self.rows if not row.is_governed)

    @property
    def managed_warning_count(self) -> int:
        return _row_count(self.rows, "managed_residual_warnings", "governed_count")

    @property
    def warning_projection_count(self) -> int:
        return _row_count(self.rows, "dashboard_warning_projection", "observed_count")

    @property
    def readiness_reconciliation_count(self) -> int:
        return _row_count(
            self.rows,
            "boundary_readiness_reconciliation",
            "governed_count",
        )

    @property
    def boundary_guarded_maturity_count(self) -> int:
        return _row_count(self.rows, "boundary_guarded_maturity", "governed_count")

    @property
    def static_closed_boundary_count(self) -> int:
        return _row_count(self.rows, "static_closed_boundary", "governed_count")

    @property
    def exception_trace_count(self) -> int:
        return sum(row.trace_count for row in self.rows)

    @property
    def unique_source_trace_count(self) -> int:
        return len(
            _unique_values(
                trace.source_trace_id
                for row in self.rows
                for trace in row.trace_rows
            )
        )

    @property
    def linked_boundary_subject_count(self) -> int:
        return len(
            _unique_values(
                subject_id
                for row in self.rows
                for subject_id in row.linked_boundary_subject_ids
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
            "source_id": SCENE_TERMINAL_RELEASE_EXCEPTION_AUDIT_SOURCE_ID,
            "required_evidence_ids": list(
                SCENE_TERMINAL_RELEASE_EXCEPTION_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "exception_count": self.exception_count,
                "governed_exception_count": self.governed_exception_count,
                "ungoverned_exception_count": self.ungoverned_exception_count,
                "managed_warning_count": self.managed_warning_count,
                "warning_projection_count": self.warning_projection_count,
                "readiness_reconciliation_count": self.readiness_reconciliation_count,
                "boundary_guarded_maturity_count": (
                    self.boundary_guarded_maturity_count
                ),
                "static_closed_boundary_count": self.static_closed_boundary_count,
                "exception_trace_count": self.exception_trace_count,
                "unique_source_trace_count": self.unique_source_trace_count,
                "linked_boundary_subject_count": self.linked_boundary_subject_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_terminal_release_exception_audit_report(
    *,
    project_root: Path | str | None = None,
) -> SceneTerminalReleaseExceptionAuditReport:
    residual_report = build_scene_residual_warning_governance_audit_report(
        project_root=project_root
    )
    readiness_report = build_scene_boundary_readiness_reconciliation_audit_report(
        project_root=project_root
    )
    guarded_report = build_scene_boundary_guarded_completion_audit_report(
        project_root=project_root
    )
    maturity_report = build_scene_product_maturity_upgrade_audit_report(
        project_root=Path(project_root) if project_root is not None else None
    )
    rows = tuple(
        _row_for_spec(
            spec,
            residual_report=residual_report,
            readiness_report=readiness_report,
            guarded_report=guarded_report,
            maturity_report=maturity_report,
        )
        for spec in SCENE_TERMINAL_RELEASE_EXCEPTION_SPECS
    )
    issues: list[SceneTerminalReleaseExceptionIssue] = []
    for row in rows:
        issues.extend(
            SceneTerminalReleaseExceptionIssue(
                row.exception_id,
                issue_id,
                f"Terminal release exception {row.exception_id} is not governed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneTerminalReleaseExceptionAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
    )


def audit_scene_terminal_release_exception_report(
    report: SceneTerminalReleaseExceptionAuditReport | None = None,
) -> tuple[SceneTerminalReleaseExceptionIssue, ...]:
    current = report or build_scene_terminal_release_exception_audit_report()
    return current.issues


def _row_for_spec(
    spec: SceneTerminalReleaseExceptionSpec,
    *,
    residual_report,
    readiness_report,
    guarded_report,
    maturity_report,
) -> SceneTerminalReleaseExceptionRow:
    observed, governed, issue_ids, trace_rows = _counts_for_exception(
        spec.exception_id,
        residual_report=residual_report,
        readiness_report=readiness_report,
        guarded_report=guarded_report,
        maturity_report=maturity_report,
    )
    return SceneTerminalReleaseExceptionRow(
        exception_id=spec.exception_id,
        exception_kind=spec.exception_kind,
        status="governed" if not issue_ids else "ungoverned",
        observed_count=observed,
        governed_count=governed,
        source_ids=spec.source_ids,
        reason=spec.reason,
        evidence_ids=spec.evidence_ids,
        trace_rows=trace_rows,
        issue_ids=issue_ids,
    )


def _counts_for_exception(
    exception_id: str,
    *,
    residual_report,
    readiness_report,
    guarded_report,
    maturity_report,
) -> tuple[int, int, tuple[str, ...], tuple[SceneTerminalReleaseExceptionTrace, ...]]:
    issue_ids: list[str] = []
    if exception_id == "managed_residual_warnings":
        observed = residual_report.warning_count
        governed = residual_report.managed_warning_count
        trace_rows = tuple(
            _trace_from_residual_warning(exception_id, row)
            for row in residual_report.rows
        )
        if residual_report.unmanaged_warning_count:
            issue_ids.append("unmanaged_warning_present")
        if observed != governed:
            issue_ids.append("managed_warning_count_mismatch")
        if observed != len(trace_rows):
            issue_ids.append("row_level_exception_trace_mismatch")
        return observed, governed, tuple(issue_ids), trace_rows
    if exception_id == "dashboard_warning_projection":
        observed = residual_report.dashboard_projection_warning_count
        trace_rows = tuple(
            _trace_from_residual_warning(exception_id, row)
            for row in residual_report.rows
            if row.source_id == "scene_matrix_dashboard"
        )
        governed = sum(
            1
            for row in residual_report.rows
            if row.source_id == "scene_matrix_dashboard" and row.is_managed
        )
        if observed != governed:
            issue_ids.append("dashboard_warning_projection_unmanaged")
        if observed != len(trace_rows):
            issue_ids.append("row_level_exception_trace_mismatch")
        return observed, governed, tuple(issue_ids), trace_rows
    if exception_id == "boundary_readiness_reconciliation":
        observed = readiness_report.row_count
        governed = readiness_report.reconciled_count
        trace_rows = tuple(
            _trace_from_readiness_reconciliation(exception_id, row)
            for row in readiness_report.rows
        )
        if readiness_report.unreconciled_count:
            issue_ids.append("unreconciled_readiness_present")
        if observed != governed:
            issue_ids.append("readiness_reconciliation_count_mismatch")
        if observed != len(trace_rows):
            issue_ids.append("row_level_exception_trace_mismatch")
        return observed, governed, tuple(issue_ids), trace_rows
    if exception_id == "boundary_guarded_maturity":
        observed = maturity_report.l5_blocked_subject_count
        governed = guarded_report.ready_subject_count
        trace_rows = tuple(
            _trace_from_maturity_boundary(exception_id, row)
            for row in maturity_report.rows
            if row.status == "boundary_guarded"
        )
        if guarded_report.ready_subject_count != guarded_report.subject_count:
            issue_ids.append("unguarded_boundary_subject_present")
        if observed != governed:
            issue_ids.append("maturity_boundary_guarded_count_mismatch")
        if observed != len(trace_rows):
            issue_ids.append("row_level_exception_trace_mismatch")
        return observed, governed, tuple(issue_ids), trace_rows
    if exception_id == "static_closed_boundary":
        observed = readiness_report.static_closed_boundary_count
        trace_rows = tuple(
            _trace_from_readiness_reconciliation(exception_id, row)
            for row in readiness_report.rows
            if row.reconciliation_mode == "static_closed_boundary"
        )
        governed = sum(
            1
            for row in readiness_report.rows
            if row.reconciliation_mode == "static_closed_boundary"
            and row.is_reconciled
        )
        if observed != governed:
            issue_ids.append("static_closed_boundary_unreconciled")
        if observed != len(trace_rows):
            issue_ids.append("row_level_exception_trace_mismatch")
        return observed, governed, tuple(issue_ids), trace_rows
    return 0, 0, ("unknown_exception_spec",), ()


def _trace_from_residual_warning(
    exception_id: str,
    row,
) -> SceneTerminalReleaseExceptionTrace:
    return SceneTerminalReleaseExceptionTrace(
        trace_id=f"{exception_id}:{row.row_id}",
        audit_source_id="scene_residual_warning_governance_audit",
        source_row_id=row.row_id,
        surface_source_id=row.source_id,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
        status=row.status,
        linked_pack_ids=tuple(row.linked_pack_ids),
        linked_family_ids=tuple(row.linked_family_ids),
        linked_boundary_subject_ids=tuple(row.linked_boundary_subject_ids),
        evidence_ids=tuple(row.evidence_ids),
    )


def _trace_from_readiness_reconciliation(
    exception_id: str,
    row,
) -> SceneTerminalReleaseExceptionTrace:
    return SceneTerminalReleaseExceptionTrace(
        trace_id=f"{exception_id}:{row.row_id}",
        audit_source_id="scene_boundary_readiness_reconciliation_audit",
        source_row_id=row.row_id,
        surface_source_id=row.source_id,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
        status=row.status,
        linked_pack_ids=tuple(row.linked_pack_ids),
        linked_family_ids=tuple(row.linked_family_ids),
        linked_boundary_subject_ids=tuple(row.linked_boundary_subject_ids),
        evidence_ids=tuple(row.evidence_ids),
    )


def _trace_from_maturity_boundary(
    exception_id: str,
    row,
) -> SceneTerminalReleaseExceptionTrace:
    source_row_id = f"{row.subject_type}:{row.subject_id}"
    return SceneTerminalReleaseExceptionTrace(
        trace_id=f"{exception_id}:{source_row_id}",
        audit_source_id="scene_product_maturity_upgrade_audit",
        source_row_id=source_row_id,
        surface_source_id="scene_product_maturity_upgrade_audit",
        scope_type=row.subject_type,
        scope_id=row.subject_id,
        status=row.status,
        linked_pack_ids=tuple(row.pack_ids),
        linked_family_ids=tuple(row.family_ids),
        linked_boundary_subject_ids=(source_row_id,),
        evidence_ids=(
            *tuple(row.evidence_domain_ids),
            "boundary_guarded_completion",
        ),
    )


def _row_count(
    rows: tuple[SceneTerminalReleaseExceptionRow, ...],
    exception_id: str,
    attr_name: str,
) -> int:
    for row in rows:
        if row.exception_id == exception_id:
            return int(getattr(row, attr_name))
    return 0


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneTerminalReleaseExceptionSourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneTerminalReleaseExceptionSourceEvidence] = []
    for source_id, source_path, markers in SCENE_TERMINAL_RELEASE_EXCEPTION_SOURCE_MARKERS:
        path = Path(source_path)
        if not path.is_absolute():
            path = root / source_path
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneTerminalReleaseExceptionSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneTerminalReleaseExceptionSourceEvidence, ...],
) -> tuple[SceneTerminalReleaseExceptionIssue, ...]:
    return tuple(
        SceneTerminalReleaseExceptionIssue(
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
    "SCENE_TERMINAL_RELEASE_EXCEPTION_AUDIT_SOURCE_ID",
    "SCENE_TERMINAL_RELEASE_EXCEPTION_REQUIRED_EVIDENCE_IDS",
    "SceneTerminalReleaseExceptionAuditReport",
    "SceneTerminalReleaseExceptionIssue",
    "SceneTerminalReleaseExceptionRow",
    "SceneTerminalReleaseExceptionSourceEvidence",
    "SceneTerminalReleaseExceptionTrace",
    "audit_scene_terminal_release_exception_report",
    "build_scene_terminal_release_exception_audit_report",
]
