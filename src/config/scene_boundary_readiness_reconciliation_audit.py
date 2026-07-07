"""Boundary readiness reconciliation audit for the scene matrix.

N2.382 keeps non-full readiness counters explainable.  Some counters should
remain below 100% because a subject is boundary-only, not applicable, or
static-closed but intentionally below Green/L5; those cases must be reconciled
instead of being mistaken for missing implementation.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_boundary_guarded_completion_audit import (
    build_scene_boundary_guarded_completion_audit_report,
)
from src.config.scene_count_profile_audit import build_scene_count_profile_audit_report
from src.config.scene_delivery_preset_audit import (
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_input_source_audit import build_scene_input_source_audit_report
from src.config.scene_object_preflight_action_audit import (
    build_scene_object_preflight_action_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_product_readiness import static_closed_but_not_green_specs


SCENE_BOUNDARY_READINESS_RECONCILIATION_AUDIT_SOURCE_ID = (
    "scene_boundary_readiness_reconciliation_audit"
)

SCENE_BOUNDARY_READINESS_RECONCILIATION_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "actual_non_full_readiness_present",
    "readiness_delta_reconciliation",
    "boundary_or_not_applicable_reason",
    "release_projection_trace",
)


@dataclass(frozen=True, slots=True)
class SceneBoundaryReadinessReconciliationSpec:
    source_id: str
    metric_id: str
    scope_type: str
    scope_id: str
    expected_statuses: tuple[str, ...]
    reconciliation_mode: str
    reason: str
    evidence_ids: tuple[str, ...]
    linked_boundary_subject_ids: tuple[str, ...] = ()

    @property
    def row_id(self) -> str:
        return ":".join(
            (
                self.source_id,
                self.metric_id,
                self.scope_type,
                self.scope_id,
            )
        )


SCENE_BOUNDARY_READINESS_RECONCILIATION_SPECS: tuple[
    SceneBoundaryReadinessReconciliationSpec, ...
] = (
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_input_source_audit",
        metric_id="family_readiness_delta",
        scope_type="family",
        scope_id="ip_patent_documents",
        expected_statuses=("boundary",),
        reconciliation_mode="boundary_family",
        reason="IP/patent input quality remains a professional-review boundary.",
        evidence_ids=("input_source_boundary", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("family:ip_patent_documents",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_count_profile_audit",
        metric_id="family_readiness_delta",
        scope_type="family",
        scope_id="ip_patent_documents",
        expected_statuses=("boundary",),
        reconciliation_mode="boundary_family",
        reason="IP/patent count semantics depend on professional claim review.",
        evidence_ids=("count_profile_boundary", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("family:ip_patent_documents",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_count_profile_audit",
        metric_id="pack_not_applicable_delta",
        scope_type="pack",
        scope_id="quick_formatting",
        expected_statuses=("not_applicable",),
        reconciliation_mode="not_applicable_count_surface",
        reason="Quick formatting has no scene-specific count-profile promise.",
        evidence_ids=("count_profile_not_applicable", "generic_formatting_scope"),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_count_profile_audit",
        metric_id="pack_not_applicable_delta",
        scope_type="pack",
        scope_id="import_ai_boundary",
        expected_statuses=("not_applicable",),
        reconciliation_mode="boundary_not_applicable_count_surface",
        reason="Import/OCR/PDF/LaTeX conversion is a boundary entry, not a count profile.",
        evidence_ids=("count_profile_not_applicable", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("pack:import_ai_boundary",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_object_preflight_action_audit",
        metric_id="family_readiness_delta",
        scope_type="family",
        scope_id="ip_patent_documents",
        expected_statuses=("boundary",),
        reconciliation_mode="boundary_family",
        reason="Patent object handling is guarded by professional-review boundaries.",
        evidence_ids=("object_preflight_boundary", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("family:ip_patent_documents",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_delivery_preset_audit",
        metric_id="family_readiness_delta",
        scope_type="family",
        scope_id="ip_patent_documents",
        expected_statuses=("boundary",),
        reconciliation_mode="boundary_family",
        reason="Patent delivery remains productized as a professional handoff boundary.",
        evidence_ids=("delivery_preset_boundary", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("family:ip_patent_documents",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_delivery_preset_audit",
        metric_id="pack_readiness_delta",
        scope_type="pack",
        scope_id="import_ai_boundary",
        expected_statuses=("boundary",),
        reconciliation_mode="boundary_pack",
        reason="Import-AI delivery is a handoff/report boundary, not a final DOCX promise.",
        evidence_ids=("delivery_preset_boundary", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("pack:import_ai_boundary",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_product_readiness",
        metric_id="static_closed_not_green",
        scope_type="pack",
        scope_id="professional_disclosure",
        expected_statuses=("closed->blue_boundary",),
        reconciliation_mode="static_closed_boundary",
        reason="Professional disclosure is statically closed but intentionally Blue/Boundary.",
        evidence_ids=("product_readiness_boundary", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("pack:professional_disclosure",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_product_readiness",
        metric_id="static_closed_not_green",
        scope_type="pack",
        scope_id="import_ai_boundary",
        expected_statuses=("closed->blue_boundary",),
        reconciliation_mode="static_closed_boundary",
        reason="Import-AI is statically closed as a boundary entry, not Green/L5 core.",
        evidence_ids=("product_readiness_boundary", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("pack:import_ai_boundary",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_product_maturity_upgrade_audit",
        metric_id="maturity_l5_blocked",
        scope_type="pack",
        scope_id="professional_disclosure",
        expected_statuses=("boundary_guarded",),
        reconciliation_mode="boundary_guarded_maturity",
        reason="The pack retains professional judgement gaps while the boundary is complete.",
        evidence_ids=("maturity_boundary_guarded", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("pack:professional_disclosure",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_product_maturity_upgrade_audit",
        metric_id="maturity_l5_blocked",
        scope_type="pack",
        scope_id="import_ai_boundary",
        expected_statuses=("boundary_guarded",),
        reconciliation_mode="boundary_guarded_maturity",
        reason="The import pack retains external conversion gaps while the boundary is complete.",
        evidence_ids=("maturity_boundary_guarded", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("pack:import_ai_boundary",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_product_maturity_upgrade_audit",
        metric_id="maturity_l5_blocked",
        scope_type="family",
        scope_id="finance_quote_documents",
        expected_statuses=("boundary_guarded",),
        reconciliation_mode="boundary_guarded_maturity",
        reason="Finance quote assurance remains outside core formatting.",
        evidence_ids=("maturity_boundary_guarded", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("family:finance_quote_documents",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_product_maturity_upgrade_audit",
        metric_id="maturity_l5_blocked",
        scope_type="family",
        scope_id="ip_patent_documents",
        expected_statuses=("boundary_guarded",),
        reconciliation_mode="boundary_guarded_maturity",
        reason="Patent claim quality remains outside core formatting.",
        evidence_ids=("maturity_boundary_guarded", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("family:ip_patent_documents",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_product_maturity_upgrade_audit",
        metric_id="maturity_l5_blocked",
        scope_type="family",
        scope_id="bilingual_translation_documents",
        expected_statuses=("boundary_guarded",),
        reconciliation_mode="boundary_guarded_maturity",
        reason="Translation quality remains outside core formatting.",
        evidence_ids=("maturity_boundary_guarded", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("family:bilingual_translation_documents",),
    ),
    SceneBoundaryReadinessReconciliationSpec(
        source_id="scene_product_maturity_upgrade_audit",
        metric_id="maturity_l5_blocked",
        scope_type="family",
        scope_id="regulated_disclosure_documents",
        expected_statuses=("boundary_guarded",),
        reconciliation_mode="boundary_guarded_maturity",
        reason="Regulated assurance remains outside core formatting.",
        evidence_ids=("maturity_boundary_guarded", "boundary_guarded_completion"),
        linked_boundary_subject_ids=("family:regulated_disclosure_documents",),
    ),
)


SCENE_BOUNDARY_READINESS_RECONCILIATION_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]], ...
] = (
    (
        "readiness_reconciliation_registry",
        "src/config/scene_boundary_readiness_reconciliation_audit.py",
        (
            "SCENE_BOUNDARY_READINESS_RECONCILIATION_SPECS",
            "readiness_delta_reconciliation",
            "not_applicable_count_surface",
        ),
    ),
    (
        "input_source_audit",
        "src/config/scene_input_source_audit.py",
        ("boundary", "plugin_manual_boundary_input_contract"),
    ),
    (
        "count_profile_audit",
        "src/config/scene_count_profile_audit.py",
        ("not_applicable", "plugin_boundary_only"),
    ),
    (
        "object_preflight_action_audit",
        "src/config/scene_object_preflight_action_audit.py",
        ("plugin_boundary_only", "status = \"boundary\""),
    ),
    (
        "delivery_preset_audit",
        "src/config/scene_delivery_preset_audit.py",
        ("not_applicable", "status = \"boundary\""),
    ),
    (
        "product_readiness",
        "src/config/scene_product_readiness.py",
        ("static_closed_but_not_green_specs", "blue_boundary"),
    ),
    (
        "product_maturity_upgrade",
        "src/config/scene_product_maturity_upgrade_audit.py",
        ("boundary_guarded", "l5_blocked_subject_count"),
    ),
    (
        "boundary_guarded_completion",
        "src/config/scene_boundary_guarded_completion_audit.py",
        ("SceneBoundaryGuardedCompletionRow", "boundary_guarded_complete"),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_BOUNDARY_READINESS_RECONCILIATION_AUDIT_SOURCE_ID,
            "boundary_readiness_reconciliation_count",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_BOUNDARY_READINESS_RECONCILIATION_AUDIT_SOURCE_ID,
            "scene_boundary_readiness_reconciliation_count",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_boundary_readiness_reconciliation_audit.py",
        (
            "build_scene_boundary_readiness_reconciliation_audit_report",
            "Reconciled rows",
            "row.source_id",
            "row.metric_id",
            "row.observed_status",
            "row.reconciliation_mode",
            "row.evidence_ids",
            "json",
            "markdown",
        ),
    ),
    (
        "n2_382_plan",
        "docs/audits/高层场景能力矩阵N2_382边界Readiness读数调和闭环_2026-06-24.md",
        ("N2.382", "readiness_delta_reconciliation", "not_applicable_count_surface"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneBoundaryReadinessReconciliationIssue:
    scope_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "scope_id": self.scope_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneBoundaryReadinessReconciliationSourceEvidence:
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
class SceneBoundaryReadinessReconciliationRow:
    row_id: str
    source_id: str
    metric_id: str
    scope_type: str
    scope_id: str
    status: str
    observed_status: str
    expected_statuses: tuple[str, ...]
    reconciliation_mode: str
    reason: str
    evidence_ids: tuple[str, ...]
    linked_pack_ids: tuple[str, ...]
    linked_family_ids: tuple[str, ...]
    linked_boundary_subject_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def is_reconciled(self) -> bool:
        return self.status == "reconciled"

    def to_payload(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "source_id": self.source_id,
            "metric_id": self.metric_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "status": self.status,
            "observed_status": self.observed_status,
            "expected_statuses": list(self.expected_statuses),
            "reconciliation_mode": self.reconciliation_mode,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "linked_pack_ids": list(self.linked_pack_ids),
            "linked_family_ids": list(self.linked_family_ids),
            "linked_boundary_subject_ids": list(self.linked_boundary_subject_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneBoundaryReadinessReconciliationAuditReport:
    rows: tuple[SceneBoundaryReadinessReconciliationRow, ...]
    issues: tuple[SceneBoundaryReadinessReconciliationIssue, ...]
    source_evidence: tuple[SceneBoundaryReadinessReconciliationSourceEvidence, ...]
    source_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def reconciled_count(self) -> int:
        return sum(1 for row in self.rows if row.is_reconciled)

    @property
    def unreconciled_count(self) -> int:
        return sum(1 for row in self.rows if not row.is_reconciled)

    @property
    def readiness_delta_count(self) -> int:
        return sum(1 for row in self.rows if "readiness_delta" in row.metric_id)

    @property
    def not_applicable_count(self) -> int:
        return sum("not_applicable" in row.reconciliation_mode for row in self.rows)

    @property
    def static_closed_boundary_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.reconciliation_mode == "static_closed_boundary"
        )

    @property
    def maturity_boundary_guarded_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.reconciliation_mode == "boundary_guarded_maturity"
        )

    @property
    def boundary_subject_count(self) -> int:
        return len(
            _unique_values(
                subject
                for row in self.rows
                for subject in row.linked_boundary_subject_ids
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
            "source_id": SCENE_BOUNDARY_READINESS_RECONCILIATION_AUDIT_SOURCE_ID,
            "source_filter": self.source_filter,
            "required_evidence_ids": list(
                SCENE_BOUNDARY_READINESS_RECONCILIATION_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "row_count": self.row_count,
                "reconciled_count": self.reconciled_count,
                "unreconciled_count": self.unreconciled_count,
                "readiness_delta_count": self.readiness_delta_count,
                "not_applicable_count": self.not_applicable_count,
                "static_closed_boundary_count": self.static_closed_boundary_count,
                "maturity_boundary_guarded_count": (
                    self.maturity_boundary_guarded_count
                ),
                "boundary_subject_count": self.boundary_subject_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_boundary_readiness_reconciliation_audit_report(
    *,
    source_id: str = "",
    project_root: Path | str | None = None,
) -> SceneBoundaryReadinessReconciliationAuditReport:
    normalized_source = str(source_id or "").strip()
    reports = _build_source_reports(project_root)
    boundary_subject_ids = {
        f"{row.subject_type}:{row.subject_id}"
        for row in reports["boundary_guarded_completion"].rows
    }
    rows: list[SceneBoundaryReadinessReconciliationRow] = []
    issues: list[SceneBoundaryReadinessReconciliationIssue] = []
    for spec in SCENE_BOUNDARY_READINESS_RECONCILIATION_SPECS:
        observed_status = _observed_status_for_spec(spec, reports)
        issue_ids: list[str] = []
        if observed_status not in spec.expected_statuses:
            issue_ids.append("unexpected_observed_status")
        missing_boundaries = tuple(
            subject
            for subject in spec.linked_boundary_subject_ids
            if subject not in boundary_subject_ids
        )
        if missing_boundaries:
            issue_ids.append("missing_boundary_guarded_subject")
        linked_pack_ids = (spec.scope_id,) if spec.scope_type == "pack" else ()
        linked_family_ids = (spec.scope_id,) if spec.scope_type == "family" else ()
        row = SceneBoundaryReadinessReconciliationRow(
            row_id=spec.row_id,
            source_id=spec.source_id,
            metric_id=spec.metric_id,
            scope_type=spec.scope_type,
            scope_id=spec.scope_id,
            status="reconciled" if not issue_ids else "unreconciled",
            observed_status=observed_status,
            expected_statuses=spec.expected_statuses,
            reconciliation_mode=spec.reconciliation_mode,
            reason=spec.reason,
            evidence_ids=spec.evidence_ids,
            linked_pack_ids=linked_pack_ids,
            linked_family_ids=linked_family_ids,
            linked_boundary_subject_ids=spec.linked_boundary_subject_ids,
            issue_ids=tuple(issue_ids),
        )
        rows.append(row)
        issues.extend(
            SceneBoundaryReadinessReconciliationIssue(
                row.row_id,
                issue_id,
                f"Readiness reconciliation {row.row_id} failed: {issue_id}.",
            )
            for issue_id in issue_ids
        )
    actual_keys = set(_actual_non_full_keys(reports))
    spec_keys = {
        (spec.source_id, spec.metric_id, spec.scope_type, spec.scope_id)
        for spec in SCENE_BOUNDARY_READINESS_RECONCILIATION_SPECS
    }
    for key in sorted(actual_keys - spec_keys):
        issues.append(
            SceneBoundaryReadinessReconciliationIssue(
                ":".join(key),
                "unreconciled_non_full_readiness",
                f"Non-full readiness row is not reconciled: {':'.join(key)}",
            )
        )
    for key in sorted(spec_keys - actual_keys):
        issues.append(
            SceneBoundaryReadinessReconciliationIssue(
                ":".join(key),
                "reconciliation_spec_not_observed",
                f"Reconciliation spec is no longer observed: {':'.join(key)}",
            )
        )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    filtered_rows = tuple(
        row for row in rows if not normalized_source or row.source_id == normalized_source
    )
    filtered_issues = tuple(
        issue
        for issue in issues
        if not normalized_source or normalized_source in issue.scope_id
    )
    return SceneBoundaryReadinessReconciliationAuditReport(
        rows=filtered_rows,
        issues=filtered_issues,
        source_evidence=source_evidence,
        source_filter=normalized_source,
    )


def audit_scene_boundary_readiness_reconciliation_report(
    report: SceneBoundaryReadinessReconciliationAuditReport | None = None,
) -> tuple[SceneBoundaryReadinessReconciliationIssue, ...]:
    current = report or build_scene_boundary_readiness_reconciliation_audit_report()
    return current.issues


def _build_source_reports(project_root: Path | str | None) -> dict[str, object]:
    root = Path(project_root) if project_root is not None else None
    return {
        "scene_input_source_audit": build_scene_input_source_audit_report(
            project_root=root
        ),
        "scene_count_profile_audit": build_scene_count_profile_audit_report(
            project_root=root
        ),
        "scene_object_preflight_action_audit": (
            build_scene_object_preflight_action_audit_report(project_root=root)
        ),
        "scene_delivery_preset_audit": build_scene_delivery_preset_audit_report(
            project_root=root
        ),
        "scene_product_maturity_upgrade_audit": (
            build_scene_product_maturity_upgrade_audit_report(project_root=root)
        ),
        "scene_product_readiness": tuple(static_closed_but_not_green_specs()),
        "boundary_guarded_completion": (
            build_scene_boundary_guarded_completion_audit_report(project_root=root)
        ),
    }


def _observed_status_for_spec(
    spec: SceneBoundaryReadinessReconciliationSpec,
    reports: dict[str, object],
) -> str:
    if spec.source_id == "scene_product_readiness":
        for item in reports["scene_product_readiness"]:
            if item.subject_type == spec.scope_type and item.subject_id == spec.scope_id:
                return f"{item.static_closure_level}->{item.product_readiness_level}"
        return "missing"
    if spec.source_id == "scene_product_maturity_upgrade_audit":
        for row in reports["scene_product_maturity_upgrade_audit"].rows:
            if row.subject_type == spec.scope_type and row.subject_id == spec.scope_id:
                return str(getattr(row, "status", "") or "missing")
        return "missing"
    report = reports[spec.source_id]
    rows = _rows_for_scope(report, spec.scope_type)
    for row in rows:
        row_id = getattr(row, f"{spec.scope_type}_id", "")
        if row_id == spec.scope_id:
            return str(getattr(row, "status", "") or "missing")
    return "missing"


def _rows_for_scope(report, scope_type: str) -> tuple[object, ...]:
    if scope_type == "family":
        return tuple(getattr(report, "family_rows", ()) or ())
    if scope_type == "pack":
        return tuple(getattr(report, "pack_rows", ()) or ())
    return ()


def _actual_non_full_keys(reports: dict[str, object]) -> tuple[tuple[str, str, str, str], ...]:
    keys: list[tuple[str, str, str, str]] = []
    for row in reports["scene_input_source_audit"].family_rows:
        if row.status != "ready":
            keys.append(
                (
                    "scene_input_source_audit",
                    "family_readiness_delta",
                    "family",
                    row.family_id,
                )
            )
    for row in reports["scene_count_profile_audit"].family_rows:
        if row.status != "ready":
            keys.append(
                (
                    "scene_count_profile_audit",
                    "family_readiness_delta",
                    "family",
                    row.family_id,
                )
            )
    for row in reports["scene_count_profile_audit"].pack_rows:
        if row.status == "not_applicable":
            keys.append(
                (
                    "scene_count_profile_audit",
                    "pack_not_applicable_delta",
                    "pack",
                    row.pack_id,
                )
            )
    for row in reports["scene_object_preflight_action_audit"].family_rows:
        if row.status != "ready":
            keys.append(
                (
                    "scene_object_preflight_action_audit",
                    "family_readiness_delta",
                    "family",
                    row.family_id,
                )
            )
    for row in reports["scene_delivery_preset_audit"].family_rows:
        if row.status != "ready":
            keys.append(
                (
                    "scene_delivery_preset_audit",
                    "family_readiness_delta",
                    "family",
                    row.family_id,
                )
            )
    for row in reports["scene_delivery_preset_audit"].pack_rows:
        if row.status == "boundary":
            keys.append(
                (
                    "scene_delivery_preset_audit",
                    "pack_readiness_delta",
                    "pack",
                    row.pack_id,
                )
            )
    for item in reports["scene_product_readiness"]:
        keys.append(
            (
                "scene_product_readiness",
                "static_closed_not_green",
                item.subject_type,
                item.subject_id,
            )
        )
    for row in reports["scene_product_maturity_upgrade_audit"].rows:
        if row.status == "boundary_guarded":
            keys.append(
                (
                    "scene_product_maturity_upgrade_audit",
                    "maturity_l5_blocked",
                    row.subject_type,
                    row.subject_id,
                )
            )
    return tuple(keys)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneBoundaryReadinessReconciliationSourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneBoundaryReadinessReconciliationSourceEvidence] = []
    for source_id, source_path, markers in (
        SCENE_BOUNDARY_READINESS_RECONCILIATION_SOURCE_MARKERS
    ):
        path = Path(source_path)
        if not path.is_absolute():
            path = root / source_path
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneBoundaryReadinessReconciliationSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneBoundaryReadinessReconciliationSourceEvidence, ...],
) -> tuple[SceneBoundaryReadinessReconciliationIssue, ...]:
    return tuple(
        SceneBoundaryReadinessReconciliationIssue(
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
    "SCENE_BOUNDARY_READINESS_RECONCILIATION_AUDIT_SOURCE_ID",
    "SCENE_BOUNDARY_READINESS_RECONCILIATION_REQUIRED_EVIDENCE_IDS",
    "SceneBoundaryReadinessReconciliationAuditReport",
    "SceneBoundaryReadinessReconciliationIssue",
    "SceneBoundaryReadinessReconciliationRow",
    "SceneBoundaryReadinessReconciliationSourceEvidence",
    "audit_scene_boundary_readiness_reconciliation_report",
    "build_scene_boundary_readiness_reconciliation_audit_report",
]
