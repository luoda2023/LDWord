"""Non-subject release-trace attribution audit for the scene matrix.

N2.386 complements boundary-subject release dossiers.  Some terminal release
traces are intentionally not owned by a Blue/Boundary subject: dashboard
projection rows, registry-only reference profiles, pack-level plugin/manual
warnings, and generic not-applicable surfaces.  They still need explicit
attribution so the terminal release ledger has no floating residual traces.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_terminal_release_exception_audit import (
    build_scene_terminal_release_exception_audit_report,
)


SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_AUDIT_SOURCE_ID = (
    "scene_non_subject_release_trace_attribution_audit"
)

SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_REQUIRED_EVIDENCE_IDS: tuple[
    str, ...
] = (
    "terminal_release_exception_trace",
    "non_subject_trace_attribution",
    "dashboard_projection_surface",
    "registry_only_profile_reference",
    "plugin_manual_pack_boundary",
    "generic_not_applicable_surface",
)

SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "non_subject_release_trace_registry",
        "src/config/scene_non_subject_release_trace_attribution_audit.py",
        (
            "SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_REQUIRED_EVIDENCE_IDS",
            "non_subject_trace_attribution",
            "dashboard_projection_surface",
        ),
    ),
    (
        "terminal_release_exception",
        "src/config/scene_terminal_release_exception_audit.py",
        ("SceneTerminalReleaseExceptionTrace", "linked_boundary_subject_ids"),
    ),
    (
        "residual_warning_governance",
        "src/config/scene_residual_warning_governance_audit.py",
        ("dashboard_projection_trace", "registry_only_profile"),
    ),
    (
        "boundary_readiness_reconciliation",
        "src/config/scene_boundary_readiness_reconciliation_audit.py",
        ("not_applicable_count_surface", "generic_formatting_scope"),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_AUDIT_SOURCE_ID,
            "non_subject_release_trace_attribution_ready_count",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_AUDIT_SOURCE_ID,
            "scene_non_subject_release_trace_attribution_ready_count",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_non_subject_release_trace_attribution_audit.py",
        (
            "build_scene_non_subject_release_trace_attribution_audit_report",
            "Attributed traces",
            "row.trace_id",
            "row.attribution_kind",
            "row.scope_type",
            "row.scope_id",
            "row.evidence_ids",
            "json",
            "markdown",
        ),
    ),
    (
        "n2_386_plan",
        "docs/audits/高层场景能力矩阵N2_386非主体发布Trace归因闭环_2026-06-24.md",
        ("N2.386", "non_subject_trace_attribution", "unattributed_trace_count"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneNonSubjectReleaseTraceAttributionIssue:
    trace_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneNonSubjectReleaseTraceAttributionSourceEvidence:
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
class SceneNonSubjectReleaseTraceAttributionRow:
    trace_id: str
    terminal_exception_id: str
    attribution_kind: str
    status: str
    source_trace_id: str
    audit_source_id: str
    surface_source_id: str
    scope_type: str
    scope_id: str
    reason: str
    evidence_ids: tuple[str, ...]
    linked_pack_ids: tuple[str, ...] = ()
    linked_profile_ids: tuple[str, ...] = ()
    issue_ids: tuple[str, ...] = ()

    @property
    def is_attributed(self) -> bool:
        return self.status == "attributed"

    def to_payload(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "terminal_exception_id": self.terminal_exception_id,
            "attribution_kind": self.attribution_kind,
            "status": self.status,
            "source_trace_id": self.source_trace_id,
            "audit_source_id": self.audit_source_id,
            "surface_source_id": self.surface_source_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "linked_pack_ids": list(self.linked_pack_ids),
            "linked_profile_ids": list(self.linked_profile_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneNonSubjectReleaseTraceAttributionAuditReport:
    rows: tuple[SceneNonSubjectReleaseTraceAttributionRow, ...]
    issues: tuple[SceneNonSubjectReleaseTraceAttributionIssue, ...]
    source_evidence: tuple[
        SceneNonSubjectReleaseTraceAttributionSourceEvidence, ...
    ]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def trace_count(self) -> int:
        return len(self.rows)

    @property
    def attributed_trace_count(self) -> int:
        return sum(1 for row in self.rows if row.is_attributed)

    @property
    def unattributed_trace_count(self) -> int:
        return sum(1 for row in self.rows if not row.is_attributed)

    @property
    def dashboard_projection_trace_count(self) -> int:
        return _kind_count(self.rows, "dashboard_projection_surface")

    @property
    def registry_only_profile_trace_count(self) -> int:
        return _kind_count(self.rows, "registry_only_profile_reference")

    @property
    def plugin_manual_pack_trace_count(self) -> int:
        return _kind_count(self.rows, "plugin_manual_pack_boundary")

    @property
    def generic_not_applicable_trace_count(self) -> int:
        return _kind_count(self.rows, "generic_not_applicable_surface")

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_AUDIT_SOURCE_ID,
            "required_evidence_ids": list(
                SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "trace_count": self.trace_count,
                "attributed_trace_count": self.attributed_trace_count,
                "unattributed_trace_count": self.unattributed_trace_count,
                "dashboard_projection_trace_count": (
                    self.dashboard_projection_trace_count
                ),
                "registry_only_profile_trace_count": (
                    self.registry_only_profile_trace_count
                ),
                "plugin_manual_pack_trace_count": self.plugin_manual_pack_trace_count,
                "generic_not_applicable_trace_count": (
                    self.generic_not_applicable_trace_count
                ),
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_non_subject_release_trace_attribution_audit_report(
    *,
    project_root: Path | str | None = None,
) -> SceneNonSubjectReleaseTraceAttributionAuditReport:
    terminal_report = build_scene_terminal_release_exception_audit_report(
        project_root=project_root
    )
    rows = tuple(
        _row_for_trace(exception_id, trace)
        for exception_id, trace in (
            (row.exception_id, trace)
            for row in terminal_report.rows
            for trace in row.trace_rows
            if not trace.linked_boundary_subject_ids
        )
    )
    issues: list[SceneNonSubjectReleaseTraceAttributionIssue] = []
    for row in rows:
        issues.extend(
            SceneNonSubjectReleaseTraceAttributionIssue(
                row.trace_id,
                issue_id,
                f"Non-subject release trace {row.trace_id} failed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneNonSubjectReleaseTraceAttributionAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
    )


def audit_scene_non_subject_release_trace_attribution_report(
    report: SceneNonSubjectReleaseTraceAttributionAuditReport | None = None,
) -> tuple[SceneNonSubjectReleaseTraceAttributionIssue, ...]:
    current = report or build_scene_non_subject_release_trace_attribution_audit_report()
    return current.issues


def _row_for_trace(
    exception_id: str,
    trace,
) -> SceneNonSubjectReleaseTraceAttributionRow:
    kind, reason, evidence_ids, linked_pack_ids, linked_profile_ids, issue_ids = (
        _classify_trace(exception_id, trace)
    )
    return SceneNonSubjectReleaseTraceAttributionRow(
        trace_id=trace.trace_id,
        terminal_exception_id=exception_id,
        attribution_kind=kind,
        status="attributed" if not issue_ids else "unattributed",
        source_trace_id=trace.source_trace_id,
        audit_source_id=trace.audit_source_id,
        surface_source_id=trace.surface_source_id,
        scope_type=trace.scope_type,
        scope_id=trace.scope_id,
        reason=reason,
        evidence_ids=evidence_ids,
        linked_pack_ids=linked_pack_ids,
        linked_profile_ids=linked_profile_ids,
        issue_ids=issue_ids,
    )


def _classify_trace(
    exception_id: str,
    trace,
) -> tuple[str, str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if trace.surface_source_id == "scene_matrix_dashboard":
        return (
            "dashboard_projection_surface",
            "Dashboard warning rows are projection surfaces and do not own a boundary subject.",
            ("terminal_release_exception_trace", "dashboard_projection_surface"),
            ((trace.scope_id,) if trace.scope_type == "pack" else ()),
            (),
            (),
        )
    if (
        trace.surface_source_id == "scene_count_profile_audit"
        and trace.scope_type == "count_profile"
    ):
        return (
            "registry_only_profile_reference",
            "Registry-only CountProfile rows are shared references, not scene subjects.",
            ("terminal_release_exception_trace", "registry_only_profile_reference"),
            (),
            (trace.scope_id,),
            (),
        )
    if (
        trace.surface_source_id == "scene_input_source_audit"
        and trace.scope_type == "pack"
        and trace.scope_id == "exam_education"
    ):
        return (
            "plugin_manual_pack_boundary",
            "Exam education keeps AI/complex diagram work behind a pack-level plugin/manual gate.",
            ("terminal_release_exception_trace", "plugin_manual_pack_boundary"),
            (trace.scope_id,),
            (),
            (),
        )
    if (
        trace.surface_source_id == "scene_count_profile_audit"
        and trace.scope_type == "pack"
        and trace.scope_id == "quick_formatting"
    ):
        return (
            "generic_not_applicable_surface",
            "Quick formatting has no scene-specific CountProfile promise.",
            ("terminal_release_exception_trace", "generic_not_applicable_surface"),
            (trace.scope_id,),
            (),
            (),
        )
    return (
        "unknown_non_subject_trace",
        "Non-subject release trace has no known attribution rule.",
        ("terminal_release_exception_trace",),
        ((trace.scope_id,) if trace.scope_type == "pack" else ()),
        ((trace.scope_id,) if trace.scope_type == "count_profile" else ()),
        ("unknown_non_subject_trace",),
    )


def _kind_count(
    rows: tuple[SceneNonSubjectReleaseTraceAttributionRow, ...],
    attribution_kind: str,
) -> int:
    return sum(1 for row in rows if row.attribution_kind == attribution_kind)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneNonSubjectReleaseTraceAttributionSourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneNonSubjectReleaseTraceAttributionSourceEvidence] = []
    for source_id, source_path, markers in (
        SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_SOURCE_MARKERS
    ):
        path = Path(source_path)
        if not path.is_absolute():
            path = root / source_path
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneNonSubjectReleaseTraceAttributionSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneNonSubjectReleaseTraceAttributionSourceEvidence, ...],
) -> tuple[SceneNonSubjectReleaseTraceAttributionIssue, ...]:
    return tuple(
        SceneNonSubjectReleaseTraceAttributionIssue(
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
    "SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_AUDIT_SOURCE_ID",
    "SCENE_NON_SUBJECT_RELEASE_TRACE_ATTRIBUTION_REQUIRED_EVIDENCE_IDS",
    "SceneNonSubjectReleaseTraceAttributionAuditReport",
    "SceneNonSubjectReleaseTraceAttributionIssue",
    "SceneNonSubjectReleaseTraceAttributionRow",
    "SceneNonSubjectReleaseTraceAttributionSourceEvidence",
    "audit_scene_non_subject_release_trace_attribution_report",
    "build_scene_non_subject_release_trace_attribution_audit_report",
]
