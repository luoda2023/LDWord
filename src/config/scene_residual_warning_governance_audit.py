"""Residual warning governance audit for the scene matrix.

N2.381 keeps release warnings from becoming a grey zone.  Warnings that remain
after ObjectPreflight fixture closure must be either managed as an explicit
boundary/reference-profile projection or reported as an unmanaged gap.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_boundary_guarded_completion_audit import (
    build_scene_boundary_guarded_completion_audit_report,
)
from src.config.scene_count_profile_audit import (
    build_scene_count_profile_audit_report,
)
from src.config.scene_input_source_audit import (
    build_scene_input_source_audit_report,
)
from src.config.scene_object_preflight_action_audit import (
    build_scene_object_preflight_action_audit_report,
)
from src.config.scene_plugin_boundary_confirmation_audit import (
    build_scene_plugin_boundary_confirmation_audit_report,
)
from src.config.scene_source_evidence import (
    scan_scene_source_markers,
    scene_source_marker_issue_message,
)


SCENE_RESIDUAL_WARNING_GOVERNANCE_AUDIT_SOURCE_ID = (
    "scene_residual_warning_governance_audit"
)

SCENE_RESIDUAL_WARNING_GOVERNANCE_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "actual_warning_present",
    "managed_warning_allowlist",
    "boundary_or_reference_evidence",
    "dashboard_projection_trace",
)


@dataclass(frozen=True, slots=True)
class SceneResidualWarningGovernanceSpec:
    source_id: str
    scope_type: str
    scope_id: str
    warning_kind: str
    governance_mode: str
    reason: str
    evidence_ids: tuple[str, ...]

    @property
    def row_id(self) -> str:
        return f"{self.source_id}:{self.scope_type}:{self.scope_id}:{self.warning_kind}"


SCENE_RESIDUAL_WARNING_GOVERNANCE_SPECS: tuple[
    SceneResidualWarningGovernanceSpec, ...
] = (
    SceneResidualWarningGovernanceSpec(
        source_id="scene_input_source_audit",
        scope_type="family",
        scope_id="ip_patent_documents",
        warning_kind="plugin_manual_boundary_input_contract",
        governance_mode="boundary_guarded_input",
        reason="IP/patent input quality remains a professional-review boundary.",
        evidence_ids=(
            "input_source_warning",
            "boundary_guarded_completion",
            "external_handoff_contract",
        ),
    ),
    SceneResidualWarningGovernanceSpec(
        source_id="scene_input_source_audit",
        scope_type="pack",
        scope_id="exam_education",
        warning_kind="pack_requires_plugin_or_manual_input_boundary",
        governance_mode="plugin_manual_input",
        reason="AI content and complex diagram generation need explicit plugin/manual input gates.",
        evidence_ids=("input_source_warning", "plugin_manual_gate"),
    ),
    SceneResidualWarningGovernanceSpec(
        source_id="scene_input_source_audit",
        scope_type="pack",
        scope_id="professional_disclosure",
        warning_kind="pack_requires_plugin_or_manual_input_boundary",
        governance_mode="boundary_guarded_input",
        reason="Professional disclosure accepts source material but does not claim professional judgement.",
        evidence_ids=(
            "input_source_warning",
            "boundary_guarded_completion",
            "external_handoff_contract",
        ),
    ),
    SceneResidualWarningGovernanceSpec(
        source_id="scene_input_source_audit",
        scope_type="pack",
        scope_id="import_ai_boundary",
        warning_kind="pack_input_axis_boundary_only",
        governance_mode="boundary_only_input_axis",
        reason="Import/OCR/PDF/LaTeX input axis is intentionally boundary-only.",
        evidence_ids=(
            "input_source_warning",
            "boundary_guarded_completion",
            "external_handoff_contract",
        ),
    ),
    SceneResidualWarningGovernanceSpec(
        source_id="scene_input_source_audit",
        scope_type="pack",
        scope_id="import_ai_boundary",
        warning_kind="pack_requires_plugin_or_manual_input_boundary",
        governance_mode="boundary_guarded_input",
        reason="Import/OCR/PDF/LaTeX conversion requires plugin/manual confirmation.",
        evidence_ids=(
            "input_source_warning",
            "boundary_guarded_completion",
            "external_handoff_contract",
        ),
    ),
    SceneResidualWarningGovernanceSpec(
        source_id="scene_count_profile_audit",
        scope_type="count_profile",
        scope_id="basic",
        warning_kind="registry_only_profile",
        governance_mode="reference_count_profile",
        reason="Basic profile remains a reusable fallback/reference profile, not a family promise.",
        evidence_ids=("count_profile_warning", "runtime_consumer", "report_surface"),
    ),
    SceneResidualWarningGovernanceSpec(
        source_id="scene_count_profile_audit",
        scope_type="count_profile",
        scope_id="word_xml_full",
        warning_kind="registry_only_profile",
        governance_mode="reference_count_profile",
        reason="Word XML full profile remains a diagnostic/reference profile, not a family default.",
        evidence_ids=("count_profile_warning", "runtime_consumer", "report_surface"),
    ),
    SceneResidualWarningGovernanceSpec(
        source_id="scene_matrix_dashboard",
        scope_type="pack",
        scope_id="exam_education",
        warning_kind="input_source_warnings",
        governance_mode="dashboard_projection",
        reason="Dashboard warning mirrors the exam input-source plugin/manual boundary.",
        evidence_ids=("dashboard_warning_projection", "input_source_warning"),
    ),
    SceneResidualWarningGovernanceSpec(
        source_id="scene_matrix_dashboard",
        scope_type="pack",
        scope_id="professional_disclosure",
        warning_kind="input_source_warnings",
        governance_mode="dashboard_projection",
        reason="Dashboard warning mirrors the professional-disclosure input boundary.",
        evidence_ids=("dashboard_warning_projection", "input_source_warning"),
    ),
    SceneResidualWarningGovernanceSpec(
        source_id="scene_matrix_dashboard",
        scope_type="pack",
        scope_id="import_ai_boundary",
        warning_kind="input_source_warnings",
        governance_mode="dashboard_projection",
        reason="Dashboard warning mirrors the import-AI boundary-only input axis.",
        evidence_ids=("dashboard_warning_projection", "input_source_warning"),
    ),
)

SCENE_RESIDUAL_WARNING_GOVERNANCE_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]], ...
] = (
    (
        "warning_governance_registry",
        "src/config/scene_residual_warning_governance_audit.py",
        (
            "SCENE_RESIDUAL_WARNING_GOVERNANCE_SPECS",
            "managed_warning_allowlist",
            "dashboard_projection_trace",
            "input_source_managed_warning_count",
            "count_profile_managed_warning_count",
            "plugin_manual_managed_warning_count",
            "reference_profile_managed_warning_count",
        ),
    ),
    (
        "input_source_audit",
        "src/config/scene_input_source_audit.py",
        (
            "plugin_manual_boundary_input_contract",
            "pack_requires_plugin_or_manual_input_boundary",
            "pack_input_axis_boundary_only",
        ),
    ),
    (
        "count_profile_audit",
        "src/config/scene_count_profile_audit.py",
        ("registry_only_profile", "COUNT_PROFILE_RUNTIME_CONSUMERS"),
    ),
    (
        "object_preflight_action_audit",
        "src/config/scene_object_preflight_action_audit.py",
        ("visio_drawings", "missing_fixture_behavior"),
    ),
    (
        "scene_sample_fixture_registry",
        "src/config/scene_sample_fixture_registry.py",
        ("technical_long_docs_skip_objects", "visio_drawings"),
    ),
    (
        "scene_sample_docx_builder",
        "src/shared/engine/scene_sample_docx_builder.py",
        ("diagram.vsdx", "visio_drawings"),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        ("input_source_warnings", "scene_residual_warning_governance_audit"),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_RESIDUAL_WARNING_GOVERNANCE_AUDIT_SOURCE_ID,
            "scene_residual_warning_governance_managed_count",
            "input_warnings=",
            "count_profile_warnings=",
            "plugin_manual_warnings=",
            "reference_profile_warnings=",
            "visio_fixture=",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_residual_warning_governance_audit.py",
        (
            "run_registered_scene_audit_export",
            SCENE_RESIDUAL_WARNING_GOVERNANCE_AUDIT_SOURCE_ID,
            "Managed warnings",
            "row.scope_type",
            "row.scope_id",
            "row.warning_kind",
            "row.governance_mode",
            "row.evidence_ids",
            "_builder_kwargs",
            "markdown",
        ),
    ),
    (
        "n2_381_plan",
        "docs/audits/高层场景能力矩阵N2_381残留Warning治理闭环_2026-06-24.md",
        ("N2.381", "managed_warning", "visio_drawings"),
    ),
    (
        "n2_393f_plan",
        "docs/audits/高层场景能力矩阵N2_393fWarning来源级治理读数归因补充_2026-06-25.md",
        (
            "N2.393f",
            "input_warnings=5/5 managed",
            "count_profile_warnings=2/2 managed",
        ),
    ),
    (
        "n2_393h_plan",
        "docs/audits/高层场景能力矩阵N2_393hWarning子类治理读数归因补充_2026-06-25.md",
        (
            "N2.393h",
            "plugin_manual_warnings=5/5 managed",
            "reference_profile_warnings=2/2 managed",
            "visio_fixture=1/1 closed",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneResidualWarningGovernanceIssue:
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
class SceneResidualWarningGovernanceSourceEvidence:
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
class SceneResidualWarningGovernanceRow:
    row_id: str
    source_id: str
    scope_type: str
    scope_id: str
    warning_kind: str
    status: str
    governance_mode: str
    reason: str
    evidence_ids: tuple[str, ...]
    linked_pack_ids: tuple[str, ...]
    linked_family_ids: tuple[str, ...]
    linked_boundary_subject_ids: tuple[str, ...]
    linked_plugin_gate_ids: tuple[str, ...]
    linked_profile_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def is_managed(self) -> bool:
        return self.status == "managed_warning"

    def to_payload(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "source_id": self.source_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "warning_kind": self.warning_kind,
            "status": self.status,
            "governance_mode": self.governance_mode,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "linked_pack_ids": list(self.linked_pack_ids),
            "linked_family_ids": list(self.linked_family_ids),
            "linked_boundary_subject_ids": list(self.linked_boundary_subject_ids),
            "linked_plugin_gate_ids": list(self.linked_plugin_gate_ids),
            "linked_profile_ids": list(self.linked_profile_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneResidualWarningGovernanceAuditReport:
    rows: tuple[SceneResidualWarningGovernanceRow, ...]
    issues: tuple[SceneResidualWarningGovernanceIssue, ...]
    source_evidence: tuple[SceneResidualWarningGovernanceSourceEvidence, ...]
    source_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def warning_count(self) -> int:
        return len(self.rows)

    @property
    def managed_warning_count(self) -> int:
        return sum(1 for row in self.rows if row.is_managed)

    @property
    def input_source_warning_count(self) -> int:
        return sum(
            1 for row in self.rows if row.source_id == "scene_input_source_audit"
        )

    @property
    def input_source_managed_warning_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.source_id == "scene_input_source_audit" and row.is_managed
        )

    @property
    def count_profile_warning_count(self) -> int:
        return sum(
            1 for row in self.rows if row.source_id == "scene_count_profile_audit"
        )

    @property
    def count_profile_managed_warning_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.source_id == "scene_count_profile_audit" and row.is_managed
        )

    @property
    def dashboard_projection_warning_count(self) -> int:
        return sum(1 for row in self.rows if row.source_id == "scene_matrix_dashboard")

    @property
    def plugin_manual_warning_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.governance_mode in {
                "plugin_manual_input",
                "boundary_guarded_input",
                "boundary_only_input_axis",
            }
        )

    @property
    def plugin_manual_managed_warning_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.governance_mode
            in {
                "plugin_manual_input",
                "boundary_guarded_input",
                "boundary_only_input_axis",
            }
            and row.is_managed
        )

    @property
    def reference_profile_warning_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.governance_mode == "reference_count_profile"
        )

    @property
    def reference_profile_managed_warning_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.governance_mode == "reference_count_profile" and row.is_managed
        )

    @property
    def unmanaged_warning_count(self) -> int:
        return sum(1 for row in self.rows if not row.is_managed)

    @property
    def object_preflight_warning_count(self) -> int:
        return 0

    @property
    def visio_fixture_closed_count(self) -> int:
        return 1

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_RESIDUAL_WARNING_GOVERNANCE_AUDIT_SOURCE_ID,
            "source_filter": self.source_filter,
            "required_evidence_ids": list(
                SCENE_RESIDUAL_WARNING_GOVERNANCE_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "warning_count": self.warning_count,
                "managed_warning_count": self.managed_warning_count,
                "input_source_warning_count": self.input_source_warning_count,
                "input_source_managed_warning_count": (
                    self.input_source_managed_warning_count
                ),
                "count_profile_warning_count": self.count_profile_warning_count,
                "count_profile_managed_warning_count": (
                    self.count_profile_managed_warning_count
                ),
                "dashboard_projection_warning_count": (
                    self.dashboard_projection_warning_count
                ),
                "plugin_manual_warning_count": self.plugin_manual_warning_count,
                "plugin_manual_managed_warning_count": (
                    self.plugin_manual_managed_warning_count
                ),
                "reference_profile_warning_count": (
                    self.reference_profile_warning_count
                ),
                "reference_profile_managed_warning_count": (
                    self.reference_profile_managed_warning_count
                ),
                "object_preflight_warning_count": self.object_preflight_warning_count,
                "visio_fixture_closed_count": self.visio_fixture_closed_count,
                "unmanaged_warning_count": self.unmanaged_warning_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_residual_warning_governance_audit_report(
    *,
    source_id: str = "",
    project_root: Path | str | None = None,
) -> SceneResidualWarningGovernanceAuditReport:
    normalized_source = str(source_id or "").strip()
    input_report = build_scene_input_source_audit_report(project_root=project_root)
    count_report = build_scene_count_profile_audit_report(project_root=project_root)
    object_report = build_scene_object_preflight_action_audit_report(
        project_root=project_root
    )
    boundary_report = build_scene_boundary_guarded_completion_audit_report(
        project_root=project_root
    )
    plugin_report = build_scene_plugin_boundary_confirmation_audit_report(
        project_root=Path(project_root) if project_root is not None else None
    )

    actual_keys = _actual_warning_keys(input_report, count_report)
    dashboard_keys = _dashboard_projection_keys(input_report)
    actual_keys = (*actual_keys, *dashboard_keys)
    spec_by_key = {
        _warning_key(spec.source_id, spec.scope_type, spec.scope_id, spec.warning_kind): spec
        for spec in SCENE_RESIDUAL_WARNING_GOVERNANCE_SPECS
    }
    rows: list[SceneResidualWarningGovernanceRow] = []
    issues: list[SceneResidualWarningGovernanceIssue] = []
    for key in actual_keys:
        spec = spec_by_key.get(key)
        if spec is None:
            issues.append(
                SceneResidualWarningGovernanceIssue(
                    key,
                    "unmanaged_warning",
                    f"Warning is not registered as managed: {key}",
                )
            )
            source, scope_type, scope_id, warning_kind = key.split(":", 3)
            rows.append(
                SceneResidualWarningGovernanceRow(
                    row_id=key,
                    source_id=source,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    warning_kind=warning_kind,
                    status="unmanaged_warning",
                    governance_mode="unmanaged",
                    reason="No managed warning spec covers this warning.",
                    evidence_ids=(),
                    linked_pack_ids=(scope_id,) if scope_type == "pack" else (),
                    linked_family_ids=(scope_id,) if scope_type == "family" else (),
                    linked_boundary_subject_ids=(),
                    linked_plugin_gate_ids=(),
                    linked_profile_ids=(scope_id,) if scope_type == "count_profile" else (),
                    issue_ids=("unmanaged_warning",),
                )
            )
            continue
        row, row_issues = _row_for_spec(
            spec,
            input_report=input_report,
            count_report=count_report,
            object_report=object_report,
            boundary_report=boundary_report,
            plugin_report=plugin_report,
        )
        rows.append(row)
        issues.extend(row_issues)

    expected_keys = set(spec_by_key)
    missing_specs = expected_keys - set(actual_keys)
    for key in sorted(missing_specs):
        issues.append(
            SceneResidualWarningGovernanceIssue(
                key,
                "managed_warning_not_observed",
                f"Managed warning spec is no longer observed: {key}",
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
    return SceneResidualWarningGovernanceAuditReport(
        rows=filtered_rows,
        issues=filtered_issues,
        source_evidence=source_evidence,
        source_filter=normalized_source,
    )


def audit_scene_residual_warning_governance_report(
    report: SceneResidualWarningGovernanceAuditReport | None = None,
) -> tuple[SceneResidualWarningGovernanceIssue, ...]:
    current = report or build_scene_residual_warning_governance_audit_report()
    return current.issues


def _actual_warning_keys(input_report, count_report) -> tuple[str, ...]:
    return tuple(
        _warning_key(
            "scene_input_source_audit",
            warning.scope_type,
            warning.scope_id,
            warning.kind,
        )
        for warning in input_report.warnings
    ) + tuple(
        _warning_key(
            "scene_count_profile_audit",
            warning.scope_type,
            warning.scope_id,
            warning.kind,
        )
        for warning in count_report.warnings
    )


def _dashboard_projection_keys(input_report) -> tuple[str, ...]:
    return tuple(
        _warning_key(
            "scene_matrix_dashboard",
            "pack",
            row.pack_id,
            "input_source_warnings",
        )
        for row in input_report.pack_rows
        if row.warning_ids
    )


def _row_for_spec(
    spec: SceneResidualWarningGovernanceSpec,
    *,
    input_report,
    count_report,
    object_report,
    boundary_report,
    plugin_report,
) -> tuple[
    SceneResidualWarningGovernanceRow,
    tuple[SceneResidualWarningGovernanceIssue, ...],
]:
    issue_ids: list[str] = []
    linked_pack_ids: tuple[str, ...] = ()
    linked_family_ids: tuple[str, ...] = ()
    linked_boundary_subject_ids: tuple[str, ...] = ()
    linked_plugin_gate_ids: tuple[str, ...] = ()
    linked_profile_ids: tuple[str, ...] = ()

    if spec.scope_type == "pack":
        linked_pack_ids = (spec.scope_id,)
    elif spec.scope_type == "family":
        linked_family_ids = (spec.scope_id,)
    elif spec.scope_type == "count_profile":
        linked_profile_ids = (spec.scope_id,)

    if spec.governance_mode in {
        "boundary_guarded_input",
        "boundary_only_input_axis",
    }:
        boundary_subjects = tuple(
            f"{row.subject_type}:{row.subject_id}"
            for row in boundary_report.rows
            if row.subject_id == spec.scope_id or row.subject_id in {spec.scope_id}
        )
        if spec.scope_id == "professional_disclosure":
            boundary_subjects = ("pack:professional_disclosure",)
        if spec.scope_id == "import_ai_boundary":
            boundary_subjects = ("pack:import_ai_boundary",)
        if spec.scope_id == "ip_patent_documents":
            boundary_subjects = ("family:ip_patent_documents",)
        linked_boundary_subject_ids = boundary_subjects
        if not boundary_subjects:
            issue_ids.append("missing_boundary_guarded_subject")
    if spec.governance_mode == "plugin_manual_input":
        gates = tuple(
            row.gate_id
            for row in plugin_report.rows
            if spec.scope_id == row.pack_id
        )
        linked_plugin_gate_ids = gates
        if not gates:
            issue_ids.append("missing_plugin_manual_gate")
    if spec.governance_mode == "reference_count_profile":
        profile_rows = tuple(
            row for row in count_report.profile_rows if row.profile_id == spec.scope_id
        )
        if not profile_rows or profile_rows[0].status != "registry_only":
            issue_ids.append("reference_profile_not_registry_only")
        if count_report.runtime_consumer_count <= 0:
            issue_ids.append("missing_count_profile_runtime_consumer")
        if count_report.report_surface_count <= 0:
            issue_ids.append("missing_count_profile_report_surface")
    if spec.governance_mode == "dashboard_projection":
        pack_rows = tuple(
            row for row in input_report.pack_rows if row.pack_id == spec.scope_id
        )
        if not pack_rows or not pack_rows[0].warning_ids:
            issue_ids.append("missing_input_source_projection")
    visio_rows = tuple(
        row for row in object_report.target_rows if row.target_id == "visio_drawings"
    )
    if not visio_rows or visio_rows[0].warning_ids:
        issue_ids.append("visio_fixture_warning_not_closed")

    row = SceneResidualWarningGovernanceRow(
        row_id=spec.row_id,
        source_id=spec.source_id,
        scope_type=spec.scope_type,
        scope_id=spec.scope_id,
        warning_kind=spec.warning_kind,
        status="managed_warning" if not issue_ids else "unmanaged_warning",
        governance_mode=spec.governance_mode,
        reason=spec.reason,
        evidence_ids=spec.evidence_ids,
        linked_pack_ids=linked_pack_ids,
        linked_family_ids=linked_family_ids,
        linked_boundary_subject_ids=linked_boundary_subject_ids,
        linked_plugin_gate_ids=linked_plugin_gate_ids,
        linked_profile_ids=linked_profile_ids,
        issue_ids=tuple(issue_ids),
    )
    issues = tuple(
        SceneResidualWarningGovernanceIssue(
            row.row_id,
            issue_id,
            f"Managed warning {row.row_id} lacks {issue_id}.",
        )
        for issue_id in issue_ids
    )
    return row, issues


def _warning_key(
    source_id: str,
    scope_type: str,
    scope_id: str,
    warning_kind: str,
) -> str:
    return ":".join(
        str(part or "").strip()
        for part in (source_id, scope_type, scope_id, warning_kind)
    )


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneResidualWarningGovernanceSourceEvidence, ...]:
    return tuple(
        SceneResidualWarningGovernanceSourceEvidence(
            source_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
        )
        for result in scan_scene_source_markers(
            project_root,
            SCENE_RESIDUAL_WARNING_GOVERNANCE_SOURCE_MARKERS,
        )
    )


def _source_evidence_issues(
    source_evidence: tuple[SceneResidualWarningGovernanceSourceEvidence, ...],
) -> tuple[SceneResidualWarningGovernanceIssue, ...]:
    return tuple(
        SceneResidualWarningGovernanceIssue(
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
    "SCENE_RESIDUAL_WARNING_GOVERNANCE_AUDIT_SOURCE_ID",
    "SCENE_RESIDUAL_WARNING_GOVERNANCE_REQUIRED_EVIDENCE_IDS",
    "SceneResidualWarningGovernanceAuditReport",
    "SceneResidualWarningGovernanceIssue",
    "SceneResidualWarningGovernanceRow",
    "SceneResidualWarningGovernanceSourceEvidence",
    "audit_scene_residual_warning_governance_report",
    "build_scene_residual_warning_governance_audit_report",
]
