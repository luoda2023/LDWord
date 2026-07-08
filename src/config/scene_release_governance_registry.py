from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass


SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID = (
    "scene_release_acceptance_certificate_audit"
)
SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID = (
    "scene_release_governance_export_script_evidence"
)


@dataclass(frozen=True, slots=True)
class SceneReleaseGovernanceReportSpec:
    report_id: str
    report_attribute: str
    module_path: str
    builder_name: str
    audit_name: str
    export_script_path: str
    test_path: str
    category: str
    builder_dependency_names: tuple[str, ...] = ()
    drilldown_source_markers: tuple[str, ...] = ()
    release_only: bool = True
    ui_visible: bool = False


@dataclass(frozen=True, slots=True)
class SceneReleaseGovernanceCountSpec:
    count_id: str
    report_attribute: str
    value_attribute: str


SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS: tuple[
    SceneReleaseGovernanceReportSpec, ...
] = (
    SceneReleaseGovernanceReportSpec(
        report_id="scene_boundary_guarded_completion_audit",
        report_attribute="boundary_guarded_completion_report",
        module_path="src.config.scene_boundary_guarded_completion_audit",
        builder_name="build_scene_boundary_guarded_completion_audit_report",
        audit_name="audit_scene_boundary_guarded_completion_report",
        export_script_path="scripts/export_scene_boundary_guarded_completion_audit.py",
        test_path="tests/test_scene_boundary_guarded_completion_audit.py",
        category="boundary",
        drilldown_source_markers=("SceneBoundaryGuardedCompletionRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_residual_warning_governance_audit",
        report_attribute="residual_warning_governance_report",
        module_path="src.config.scene_residual_warning_governance_audit",
        builder_name="build_scene_residual_warning_governance_audit_report",
        audit_name="audit_scene_residual_warning_governance_report",
        export_script_path="scripts/export_scene_residual_warning_governance_audit.py",
        test_path="tests/test_scene_residual_warning_governance_audit.py",
        category="residual",
        drilldown_source_markers=("SceneResidualWarningGovernanceRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_boundary_readiness_reconciliation_audit",
        report_attribute="boundary_readiness_reconciliation_report",
        module_path="src.config.scene_boundary_readiness_reconciliation_audit",
        builder_name="build_scene_boundary_readiness_reconciliation_audit_report",
        audit_name="audit_scene_boundary_readiness_reconciliation_report",
        export_script_path=(
            "scripts/export_scene_boundary_readiness_reconciliation_audit.py"
        ),
        test_path="tests/test_scene_boundary_readiness_reconciliation_audit.py",
        category="boundary",
        drilldown_source_markers=("SceneBoundaryReadinessReconciliationRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_terminal_release_exception_audit",
        report_attribute="terminal_release_exception_report",
        module_path="src.config.scene_terminal_release_exception_audit",
        builder_name="build_scene_terminal_release_exception_audit_report",
        audit_name="audit_scene_terminal_release_exception_report",
        export_script_path="scripts/export_scene_terminal_release_exception_audit.py",
        test_path="tests/test_scene_terminal_release_exception_audit.py",
        category="terminal",
        drilldown_source_markers=("SceneTerminalReleaseExceptionRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_boundary_subject_release_dossier_audit",
        report_attribute="boundary_subject_release_dossier_report",
        module_path="src.config.scene_boundary_subject_release_dossier_audit",
        builder_name="build_scene_boundary_subject_release_dossier_audit_report",
        audit_name="audit_scene_boundary_subject_release_dossier_report",
        export_script_path=(
            "scripts/export_scene_boundary_subject_release_dossier_audit.py"
        ),
        test_path="tests/test_scene_boundary_subject_release_dossier_audit.py",
        category="boundary",
        drilldown_source_markers=("SceneBoundarySubjectReleaseDossierRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_non_subject_release_trace_attribution_audit",
        report_attribute="non_subject_release_trace_attribution_report",
        module_path="src.config.scene_non_subject_release_trace_attribution_audit",
        builder_name=(
            "build_scene_non_subject_release_trace_attribution_audit_report"
        ),
        audit_name="audit_scene_non_subject_release_trace_attribution_report",
        export_script_path=(
            "scripts/export_scene_non_subject_release_trace_attribution_audit.py"
        ),
        test_path="tests/test_scene_non_subject_release_trace_attribution_audit.py",
        category="trace",
        drilldown_source_markers=(
            "SceneNonSubjectReleaseTraceAttributionRow",
        ),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_release_trace_partition_guard_audit",
        report_attribute="release_trace_partition_guard_report",
        module_path="src.config.scene_release_trace_partition_guard_audit",
        builder_name="build_scene_release_trace_partition_guard_audit_report",
        audit_name="audit_scene_release_trace_partition_guard_report",
        export_script_path="scripts/export_scene_release_trace_partition_guard_audit.py",
        test_path="tests/test_scene_release_trace_partition_guard_audit.py",
        category="trace",
        drilldown_source_markers=("SceneReleaseTracePartitionGuardRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_release_projection_surface_parity_audit",
        report_attribute="release_projection_surface_parity_report",
        module_path="src.config.scene_release_projection_surface_parity_audit",
        builder_name="build_scene_release_projection_surface_parity_audit_report",
        audit_name="audit_scene_release_projection_surface_parity_report",
        export_script_path=(
            "scripts/export_scene_release_projection_surface_parity_audit.py"
        ),
        test_path="tests/test_scene_release_projection_surface_parity_audit.py",
        category="projection",
        drilldown_source_markers=("SceneReleaseProjectionSurfaceParityRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_boundary_subject_release_continuity_audit",
        report_attribute="boundary_subject_release_continuity_report",
        module_path="src.config.scene_boundary_subject_release_continuity_audit",
        builder_name="build_scene_boundary_subject_release_continuity_audit_report",
        audit_name="audit_scene_boundary_subject_release_continuity_report",
        export_script_path=(
            "scripts/export_scene_boundary_subject_release_continuity_audit.py"
        ),
        test_path="tests/test_scene_boundary_subject_release_continuity_audit.py",
        category="boundary",
        drilldown_source_markers=("SceneBoundarySubjectReleaseContinuityRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_boundary_maturity_release_envelope_audit",
        report_attribute="boundary_maturity_release_envelope_report",
        module_path="src.config.scene_boundary_maturity_release_envelope_audit",
        builder_name="build_scene_boundary_maturity_release_envelope_audit_report",
        audit_name="audit_scene_boundary_maturity_release_envelope_report",
        export_script_path=(
            "scripts/export_scene_boundary_maturity_release_envelope_audit.py"
        ),
        test_path="tests/test_scene_boundary_maturity_release_envelope_audit.py",
        category="boundary",
        drilldown_source_markers=("SceneBoundaryMaturityReleaseEnvelopeRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_retained_gap_exit_criteria_audit",
        report_attribute="retained_gap_exit_criteria_report",
        module_path="src.config.scene_retained_gap_exit_criteria_audit",
        builder_name="build_scene_retained_gap_exit_criteria_audit_report",
        audit_name="audit_scene_retained_gap_exit_criteria_report",
        export_script_path="scripts/export_scene_retained_gap_exit_criteria_audit.py",
        test_path="tests/test_scene_retained_gap_exit_criteria_audit.py",
        category="retained_gap",
        drilldown_source_markers=("SceneRetainedGapExitCriteriaRow",),
        builder_dependency_names=(
            "boundary_maturity_release_envelope_report",
            "external_handoff_contract_report",
            "boundary_guarded_completion_report",
        ),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_release_residual_ratio_ledger_audit",
        report_attribute="release_residual_ratio_ledger_report",
        module_path="src.config.scene_release_residual_ratio_ledger_audit",
        builder_name="build_scene_release_residual_ratio_ledger_audit_report",
        audit_name="audit_scene_release_residual_ratio_ledger_report",
        export_script_path=(
            "scripts/export_scene_release_residual_ratio_ledger_audit.py"
        ),
        test_path="tests/test_scene_release_residual_ratio_ledger_audit.py",
        category="residual",
        drilldown_source_markers=("SceneReleaseResidualRatioLedgerRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_release_residual_explanation_audit",
        report_attribute="release_residual_explanation_report",
        module_path="src.config.scene_release_residual_explanation_audit",
        builder_name="build_scene_release_residual_explanation_audit_report",
        audit_name="audit_scene_release_residual_explanation_report",
        export_script_path=(
            "scripts/export_scene_release_residual_explanation_audit.py"
        ),
        test_path="tests/test_scene_release_residual_explanation_audit.py",
        category="residual",
        drilldown_source_markers=("SceneReleaseResidualExplanationRow",),
        builder_dependency_names=(
            "input_source_report",
            "count_profile_report",
            "residual_warning_governance_report",
            "terminal_release_exception_report",
            "boundary_maturity_release_envelope_report",
            "release_residual_ratio_ledger_report",
            "maturity_upgrade_report",
            "matrix_dashboard",
        ),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id="scene_release_closure_ledger_audit",
        report_attribute="release_closure_ledger_report",
        module_path="src.config.scene_release_closure_ledger_audit",
        builder_name="build_scene_release_closure_ledger_audit_report",
        audit_name="audit_scene_release_closure_ledger_report",
        export_script_path="scripts/export_scene_release_closure_ledger_audit.py",
        test_path="tests/test_scene_release_closure_ledger_audit.py",
        category="closure",
        drilldown_source_markers=("SceneReleaseClosureLedgerStageRow",),
    ),
    SceneReleaseGovernanceReportSpec(
        report_id=SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
        report_attribute="release_acceptance_certificate_report",
        module_path="src.config.scene_release_acceptance_certificate_audit",
        builder_name="build_scene_release_acceptance_certificate_audit_report",
        audit_name="audit_scene_release_acceptance_certificate_report",
        export_script_path=(
            "scripts/export_scene_release_acceptance_certificate_audit.py"
        ),
        test_path="tests/test_scene_release_acceptance_certificate_audit.py",
        category="certificate",
        drilldown_source_markers=(
            "SceneReleaseAcceptanceCertificateRow",
            "release_residual_ratio_receipts",
            "retained_gap_external_receipts",
            "acceptance_evidence=15/15",
        ),
    ),
)

SCENE_RELEASE_GOVERNANCE_CORE_REPORT_SPECS: tuple[
    SceneReleaseGovernanceReportSpec, ...
] = tuple(
    spec
    for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    if spec.report_id != SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID
)

SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_IDS: tuple[str, ...] = tuple(
    spec.report_id for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
)

_SCENE_RELEASE_GOVERNANCE_REPORT_SPECS_BY_ID: dict[
    str, SceneReleaseGovernanceReportSpec
] = {
    spec.report_id: spec for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
}
_SCENE_RELEASE_GOVERNANCE_REPORT_SPECS_BY_ATTRIBUTE: dict[
    str, SceneReleaseGovernanceReportSpec
] = {
    spec.report_attribute: spec
    for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
}

SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS: tuple[str, ...] = (
    "scene_boundary_guarded_completion_audit",
    "scene_residual_warning_governance_audit",
    "scene_boundary_readiness_reconciliation_audit",
    "scene_terminal_release_exception_audit",
    "scene_boundary_subject_release_dossier_audit",
    "scene_non_subject_release_trace_attribution_audit",
    "scene_release_trace_partition_guard_audit",
    "scene_release_projection_surface_parity_audit",
    "scene_boundary_subject_release_continuity_audit",
    "scene_release_closure_ledger_audit",
    "scene_boundary_maturity_release_envelope_audit",
    "scene_retained_gap_exit_criteria_audit",
    "scene_release_residual_ratio_ledger_audit",
    SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
)

SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS: tuple[str, ...] = (
    "scene_release_residual_explanation_audit",
)

SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS: tuple[str, ...] = (
    *(
        report_id
        for report_id in SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS
        if report_id != SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID
    ),
    *SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
    SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
)

SCENE_RELEASE_GOVERNANCE_GATE_REPORT_IDS: tuple[str, ...] = (
    *SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS,
    *SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
)

SCENE_RELEASE_GOVERNANCE_PAYLOAD_REPORT_IDS: tuple[str, ...] = tuple(
    report_id
    for report_id in SCENE_RELEASE_GOVERNANCE_GATE_REPORT_IDS
    if report_id != SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID
) + (SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,)

SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="static_closed_not_green_governed_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="static_closed_boundary_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="dashboard_warning_projection_governed_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="warning_projection_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="input_source_warning_managed_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="input_source_managed_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="count_profile_warning_managed_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="count_profile_managed_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="plugin_manual_warning_managed_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="plugin_manual_managed_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="reference_profile_warning_managed_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="reference_profile_managed_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="visio_fixture_closed_verified_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="visio_fixture_closed_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="retained_gap_enveloped_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="retained_gap_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_RESIDUAL_WARNING_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_warning_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_managed_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="managed_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_input_source_warning_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="input_source_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_count_profile_warning_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="count_profile_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_residual_warning_governance_dashboard_projection_warning_count"
        ),
        report_attribute="residual_warning_governance_report",
        value_attribute="dashboard_projection_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_plugin_manual_warning_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="plugin_manual_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_reference_profile_warning_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="reference_profile_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_object_preflight_warning_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="object_preflight_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_visio_fixture_closed_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="visio_fixture_closed_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_unmanaged_warning_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="unmanaged_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_issue_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_residual_warning_governance_missing_source_evidence_count",
        report_attribute="residual_warning_governance_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_BOUNDARY_GUARDED_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_subject_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_ready_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="ready_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_pack_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="pack_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_family_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="family_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_retained_gap_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="retained_gap_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_external_contract_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="external_contract_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_boundary_capability_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="boundary_capability_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_plugin_gate_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="plugin_gate_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_target_plugin_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="target_plugin_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_risk_domain_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="risk_domain_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_excluded_core_claim_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="excluded_core_claim_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_issue_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_guarded_completion_missing_source_evidence_count",
        report_attribute="boundary_guarded_completion_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_BOUNDARY_READINESS_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_readiness_reconciliation_count",
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="row_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_readiness_reconciliation_reconciled_count",
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="reconciled_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_readiness_reconciliation_unreconciled_count",
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="unreconciled_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_readiness_reconciliation_readiness_delta_count",
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="readiness_delta_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_readiness_reconciliation_not_applicable_count",
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="not_applicable_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_readiness_reconciliation_static_closed_boundary_count"
        ),
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="static_closed_boundary_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_readiness_reconciliation_maturity_boundary_guarded_count"
        ),
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="maturity_boundary_guarded_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_readiness_reconciliation_boundary_subject_count",
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="boundary_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_readiness_reconciliation_issue_count",
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_readiness_reconciliation_missing_source_evidence_count"
        ),
        report_attribute="boundary_readiness_reconciliation_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_TERMINAL_EXCEPTION_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="exception_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_governed_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="governed_exception_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_ungoverned_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="ungoverned_exception_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_managed_warning_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="managed_warning_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_warning_projection_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="warning_projection_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_readiness_reconciliation_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="readiness_reconciliation_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_boundary_guarded_maturity_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="boundary_guarded_maturity_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_static_closed_boundary_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="static_closed_boundary_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_trace_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="exception_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_unique_source_trace_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="unique_source_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_linked_boundary_subject_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="linked_boundary_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_issue_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_terminal_release_exception_missing_source_evidence_count",
        report_attribute="terminal_release_exception_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_SUBJECT_DOSSIER_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_dossier_subject_count",
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_dossier_ready_count",
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="ready_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_dossier_pack_subject_count",
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="pack_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_dossier_family_subject_count",
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="family_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_dossier_subject_trace_count",
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="subject_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_subject_release_dossier_unique_source_trace_count"
        ),
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="unique_source_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_subject_release_dossier_readiness_reconciliation_row_count"
        ),
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="readiness_reconciliation_row_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_dossier_terminal_exception_count",
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="terminal_exception_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_dossier_issue_count",
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_subject_release_dossier_missing_source_evidence_count"
        ),
        report_attribute="boundary_subject_release_dossier_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_NON_SUBJECT_TRACE_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_non_subject_release_trace_attribution_count",
        report_attribute="non_subject_release_trace_attribution_report",
        value_attribute="trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_non_subject_release_trace_attribution_ready_count",
        report_attribute="non_subject_release_trace_attribution_report",
        value_attribute="attributed_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_non_subject_release_trace_attribution_unattributed_count",
        report_attribute="non_subject_release_trace_attribution_report",
        value_attribute="unattributed_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_non_subject_release_trace_attribution_dashboard_projection_count"
        ),
        report_attribute="non_subject_release_trace_attribution_report",
        value_attribute="dashboard_projection_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_non_subject_release_trace_attribution_registry_only_profile_count"
        ),
        report_attribute="non_subject_release_trace_attribution_report",
        value_attribute="registry_only_profile_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_non_subject_release_trace_attribution_plugin_manual_pack_count"
        ),
        report_attribute="non_subject_release_trace_attribution_report",
        value_attribute="plugin_manual_pack_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_non_subject_release_trace_attribution_generic_not_applicable_count"
        ),
        report_attribute="non_subject_release_trace_attribution_report",
        value_attribute="generic_not_applicable_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_non_subject_release_trace_attribution_issue_count",
        report_attribute="non_subject_release_trace_attribution_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_non_subject_release_trace_attribution_missing_source_evidence_count"
        ),
        report_attribute="non_subject_release_trace_attribution_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_TRACE_PARTITION_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_partition_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="partition_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_ready_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="ready_partition_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_terminal_trace_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="terminal_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_subject_trace_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="subject_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_non_subject_trace_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="non_subject_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_partitioned_trace_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="partitioned_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_missing_trace_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="missing_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_overlap_trace_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="overlap_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_extra_trace_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="extra_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_issue_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_trace_partition_guard_missing_source_evidence_count",
        report_attribute="release_trace_partition_guard_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_PROJECTION_PARITY_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="projection_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_ready_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="ready_projection_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_release_gate_check_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="release_gate_check_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_dashboard_source_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="dashboard_source_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_dashboard_card_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="dashboard_card_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_drilldown_item_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="drilldown_item_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_summary_projection_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="summary_projection_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_export_script_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="export_script_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_workflow_test_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="workflow_test_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_closure_doc_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="closure_doc_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_projection_surface_parity_issue_count",
        report_attribute="release_projection_surface_parity_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_projection_surface_parity_missing_source_evidence_count"
        ),
        report_attribute="release_projection_surface_parity_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_SUBJECT_CONTINUITY_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_continuity_subject_count",
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_continuity_ready_count",
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="ready_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_continuity_maturity_subject_count",
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="maturity_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_subject_release_continuity_guarded_completion_subject_count"
        ),
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="guarded_completion_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_subject_release_continuity_readiness_reconciliation_subject_count"
        ),
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="readiness_reconciliation_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_subject_release_continuity_terminal_release_subject_count"
        ),
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="terminal_release_subject_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_continuity_dossier_count",
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="subject_dossier_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_continuity_readiness_row_count",
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="readiness_row_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_continuity_terminal_trace_count",
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="terminal_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_continuity_dossier_trace_count",
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="dossier_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_continuity_mismatch_count",
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="mismatch_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_subject_release_continuity_issue_count",
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_subject_release_continuity_missing_source_evidence_count"
        ),
        report_attribute="boundary_subject_release_continuity_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_CLOSURE_LEDGER_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_stage_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="stage_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_ready_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="ready_stage_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_stage_order_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="stage_order_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_upstream_dependency_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="upstream_dependency_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_upstream_dependency_ready_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="upstream_dependency_ready_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_release_gate_check_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="release_gate_check_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_dashboard_source_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="dashboard_source_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_dashboard_card_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="dashboard_card_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_drilldown_item_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="drilldown_item_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_summary_projection_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="summary_projection_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_export_script_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="export_script_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_workflow_test_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="workflow_test_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_closure_doc_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="closure_doc_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_issue_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_closure_ledger_missing_source_evidence_count",
        report_attribute="release_closure_ledger_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_BOUNDARY_MATURITY_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="envelope_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_ready_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="ready_envelope_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_maturity_release_envelope_l5_blocker_enveloped_count"
        ),
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="l5_blocker_enveloped_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_maturity_boundary_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="maturity_boundary_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_external_handoff_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="external_handoff_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_guarded_completion_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="guarded_completion_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_maturity_release_envelope_readiness_reconciliation_count"
        ),
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="readiness_reconciliation_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_terminal_trace_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="terminal_trace_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_release_dossier_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="release_dossier_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_subject_continuity_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="subject_continuity_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_retained_gap_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="retained_gap_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_boundary_maturity_release_envelope_issue_count",
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_boundary_maturity_release_envelope_missing_source_evidence_count"
        ),
        report_attribute="boundary_maturity_release_envelope_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_RETAINED_GAP_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="criteria_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_release_allowed_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="release_allowed_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_envelope_link_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="envelope_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_handoff_link_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="handoff_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_guarded_completion_link_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="guarded_completion_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_boundary_capability_link_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="boundary_capability_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_exit_signal_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="exit_signal_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_external_receipt_target_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="external_receipt_target_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_external_receipt_alignment_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="external_receipt_alignment_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_prohibited_core_claim_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="prohibited_core_claim_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_issue_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_retained_gap_exit_criteria_missing_source_evidence_count",
        report_attribute="retained_gap_exit_criteria_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_RESIDUAL_RATIO_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="ratio_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_published_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="published_ratio_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_non_full_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="non_full_ratio_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_residual_ratio_ledger_readiness_reconciliation_link_count"
        ),
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="readiness_reconciliation_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_terminal_exception_link_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="terminal_exception_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_release_envelope_link_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="release_envelope_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_exit_criteria_link_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="retained_gap_exit_criteria_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_receipt_alignment_link_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="retained_gap_receipt_alignment_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_residual_ratio_ledger_count_delivery_boundary_alignment_count"
        ),
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="count_delivery_boundary_alignment_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_residual_ratio_ledger_count_delivery_boundary_link_count"
        ),
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="count_delivery_boundary_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_count"
        ),
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="count_delivery_receipt_alignment_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count"
        ),
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="count_delivery_receipt_alignment_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_alignment_count"
        ),
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="maturity_l5_blocker_alignment_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count"
        ),
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="maturity_l5_blocker_release_envelope_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count"
        ),
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="maturity_l5_blocker_receipt_alignment_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count"
        ),
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="maturity_l5_blocker_receipt_alignment_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_boundary_scope_alignment_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="boundary_scope_alignment_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_boundary_scope_link_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="boundary_scope_link_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_issue_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_ratio_ledger_missing_source_evidence_count",
        report_attribute="release_residual_ratio_ledger_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_RESIDUAL_EXPLANATION_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_explanation_count",
        report_attribute="release_residual_explanation_report",
        value_attribute="row_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_explanation_covered_count",
        report_attribute="release_residual_explanation_report",
        value_attribute="covered_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_explanation_mismatch_count",
        report_attribute="release_residual_explanation_report",
        value_attribute="mismatch_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_explanation_missing_summary_marker_count",
        report_attribute="release_residual_explanation_report",
        value_attribute="missing_summary_marker_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_explanation_issue_count",
        report_attribute="release_residual_explanation_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_residual_explanation_missing_source_evidence_count",
        report_attribute="release_residual_explanation_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_governance_export_script_report_count",
        report_attribute="release_governance_export_script_counts",
        value_attribute="report_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_governance_export_script_ready_count",
        report_attribute="release_governance_export_script_counts",
        value_attribute="ready_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_governance_export_script_missing_count",
        report_attribute="release_governance_export_script_counts",
        value_attribute="missing_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_governance_export_script_unready_count",
        report_attribute="release_governance_export_script_counts",
        value_attribute="unready_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_ACCEPTANCE_CERTIFICATE_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = (
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_acceptance_certificate_count",
        report_attribute="release_acceptance_certificate_report",
        value_attribute="certificate_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_acceptance_certificate_ready_count",
        report_attribute="release_acceptance_certificate_report",
        value_attribute="ready_certificate_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_acceptance_certificate_receipt_count",
        report_attribute="release_acceptance_certificate_report",
        value_attribute="receipt_certificate_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_acceptance_certificate_ready_receipt_count",
        report_attribute="release_acceptance_certificate_report",
        value_attribute="ready_receipt_certificate_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_acceptance_certificate_component_report_count",
        report_attribute="release_acceptance_certificate_report",
        value_attribute="component_report_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_acceptance_certificate_requirement_dimension_count"
        ),
        report_attribute="release_acceptance_certificate_report",
        value_attribute="requirement_dimension_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_acceptance_certificate_ready_requirement_dimension_count"
        ),
        report_attribute="release_acceptance_certificate_report",
        value_attribute="ready_requirement_dimension_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_acceptance_certificate_expected_count_match_count",
        report_attribute="release_acceptance_certificate_report",
        value_attribute="expected_count_match_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_acceptance_certificate_source_evidence_count",
        report_attribute="release_acceptance_certificate_report",
        value_attribute="source_evidence_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_acceptance_certificate_ready_source_evidence_count",
        report_attribute="release_acceptance_certificate_report",
        value_attribute="ready_source_evidence_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id="scene_release_acceptance_certificate_issue_count",
        report_attribute="release_acceptance_certificate_report",
        value_attribute="issue_count",
    ),
    SceneReleaseGovernanceCountSpec(
        count_id=(
            "scene_release_acceptance_certificate_missing_source_evidence_count"
        ),
        report_attribute="release_acceptance_certificate_report",
        value_attribute="missing_source_evidence_count",
    ),
)

SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPEC_GROUPS: tuple[
    tuple[SceneReleaseGovernanceCountSpec, ...], ...
] = (
    SCENE_RELEASE_GOVERNANCE_BOUNDARY_GUARDED_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_RESIDUAL_WARNING_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_BOUNDARY_READINESS_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_TERMINAL_EXCEPTION_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_SUBJECT_DOSSIER_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_NON_SUBJECT_TRACE_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_TRACE_PARTITION_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_PROJECTION_PARITY_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_SUBJECT_CONTINUITY_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_CLOSURE_LEDGER_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_BOUNDARY_MATURITY_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_RETAINED_GAP_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_RESIDUAL_RATIO_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_RESIDUAL_EXPLANATION_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_ACCEPTANCE_CERTIFICATE_COUNT_SPECS,
)

SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS: tuple[
    SceneReleaseGovernanceCountSpec, ...
] = tuple(
    count_spec
    for count_group in SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPEC_GROUPS
    for count_spec in count_group
)


def scene_release_governance_report_pairs(
    reports_by_attribute: Mapping[str, object],
    *,
    include_acceptance_certificate: bool = True,
) -> tuple[tuple[str, object], ...]:
    specs = (
        SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
        if include_acceptance_certificate
        else SCENE_RELEASE_GOVERNANCE_CORE_REPORT_SPECS
    )
    missing = tuple(
        spec.report_attribute
        for spec in specs
        if spec.report_attribute not in reports_by_attribute
    )
    if missing:
        missing_text = ", ".join(missing)
        raise KeyError(f"Missing release governance reports: {missing_text}")
    return tuple(
        (spec.report_id, reports_by_attribute[spec.report_attribute])
        for spec in specs
    )


def scene_release_governance_payload_entries(
    reports_by_attribute: Mapping[str, object],
) -> dict[str, object]:
    entries: dict[str, object] = {}
    for report_id in SCENE_RELEASE_GOVERNANCE_PAYLOAD_REPORT_IDS:
        spec = scene_release_governance_report_spec(report_id)
        if spec.report_attribute not in reports_by_attribute:
            raise KeyError(
                f"Missing release governance report: {spec.report_attribute}"
            )
        report = reports_by_attribute[spec.report_attribute]
        to_payload = getattr(report, "to_payload", None)
        if not callable(to_payload):
            raise TypeError(f"{report_id} report does not expose to_payload().")
        entries[report_id] = to_payload()
    return entries


def scene_release_governance_count_entries(
    reports_by_attribute: Mapping[str, object],
    count_specs: tuple[
        SceneReleaseGovernanceCountSpec, ...
    ] = SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS,
) -> dict[str, object]:
    entries: dict[str, object] = {}
    for spec in count_specs:
        if spec.report_attribute not in reports_by_attribute:
            raise KeyError(
                f"Missing release governance report: {spec.report_attribute}"
            )
        source = reports_by_attribute[spec.report_attribute]
        if isinstance(source, Mapping):
            entries[spec.count_id] = source[spec.value_attribute]
        else:
            entries[spec.count_id] = getattr(source, spec.value_attribute)
    return entries


def scene_release_governance_detail_count_entries(
    reports_by_attribute: Mapping[str, object],
) -> dict[str, object]:
    return scene_release_governance_count_entries(
        reports_by_attribute,
        SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS,
    )


def scene_release_governance_drilldown_source_marker_entries() -> tuple[
    tuple[str, str, tuple[str, ...]], ...
]:
    return tuple(
        (
            spec.report_id,
            f"{spec.module_path.replace('.', '/')}.py",
            (spec.builder_name, *spec.drilldown_source_markers),
        )
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )


def resolve_scene_release_governance_functions(
    spec: SceneReleaseGovernanceReportSpec,
) -> tuple[Callable[..., object], Callable[..., object]]:
    module = importlib.import_module(spec.module_path)
    builder = getattr(module, spec.builder_name)
    auditor = getattr(module, spec.audit_name)
    if not callable(builder) or not callable(auditor):
        raise TypeError(f"{spec.report_id} builder/audit metadata is not callable.")
    return builder, auditor


def build_scene_release_governance_report(
    report_id: str,
    *,
    project_root: object = None,
    dependencies: Mapping[str, object] | None = None,
    require_dependencies: bool = False,
    builder_kwargs: Mapping[str, object] | None = None,
) -> object:
    spec = scene_release_governance_report_spec(report_id)
    builder, _auditor = resolve_scene_release_governance_functions(spec)
    dependency_map = dependencies or {}
    explicit_kwargs = builder_kwargs or {}
    if require_dependencies:
        missing_declared = tuple(
            name
            for name in spec.builder_dependency_names
            if name not in dependency_map
        )
        if missing_declared:
            missing_text = ", ".join(missing_declared)
            raise KeyError(
                f"{report_id} missing declared builder dependencies: "
                f"{missing_text}"
            )
    signature = inspect.signature(builder)
    kwargs: dict[str, object] = {}
    missing_required: list[str] = []
    for name, parameter in signature.parameters.items():
        if name == "project_root":
            kwargs[name] = project_root
        elif name in explicit_kwargs:
            kwargs[name] = explicit_kwargs[name]
        elif name in spec.builder_dependency_names and name in dependency_map:
            kwargs[name] = dependency_map[name]
        elif not spec.builder_dependency_names and name in dependency_map:
            kwargs[name] = dependency_map[name]
        elif (
            parameter.default is inspect.Parameter.empty
            and parameter.kind
            in (
                inspect.Parameter.KEYWORD_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ):
            missing_required.append(name)
    if missing_required:
        missing_text = ", ".join(missing_required)
        raise KeyError(f"{report_id} missing builder dependencies: {missing_text}")
    return builder(**kwargs)


def scene_release_governance_report_spec(
    report_id: str,
) -> SceneReleaseGovernanceReportSpec:
    return _SCENE_RELEASE_GOVERNANCE_REPORT_SPECS_BY_ID[report_id]


def scene_release_governance_report_id(report_attribute: str) -> str:
    return _SCENE_RELEASE_GOVERNANCE_REPORT_SPECS_BY_ATTRIBUTE[
        report_attribute
    ].report_id


def scene_release_governance_drilldown_id(report_attribute: str) -> str:
    scene_release_governance_report_id(report_attribute)
    return report_attribute.removesuffix("_report")


__all__ = [
    "SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID",
    "SCENE_RELEASE_GOVERNANCE_ACCEPTANCE_CERTIFICATE_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_BOUNDARY_GUARDED_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_BOUNDARY_MATURITY_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_BOUNDARY_READINESS_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_CLOSURE_LEDGER_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_CORE_REPORT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS",
    "SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS",
    "SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPEC_GROUPS",
    "SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS",
    "SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_IDS",
    "SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID",
    "SCENE_RELEASE_GOVERNANCE_GATE_REPORT_IDS",
    "SCENE_RELEASE_GOVERNANCE_NON_SUBJECT_TRACE_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_PAYLOAD_REPORT_IDS",
    "SCENE_RELEASE_GOVERNANCE_PROJECTION_PARITY_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_RESIDUAL_EXPLANATION_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_RESIDUAL_WARNING_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_RESIDUAL_RATIO_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_RETAINED_GAP_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_SUBJECT_CONTINUITY_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_SUBJECT_DOSSIER_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_TERMINAL_EXCEPTION_COUNT_SPECS",
    "SCENE_RELEASE_GOVERNANCE_TRACE_PARTITION_COUNT_SPECS",
    "SceneReleaseGovernanceCountSpec",
    "SceneReleaseGovernanceReportSpec",
    "build_scene_release_governance_report",
    "resolve_scene_release_governance_functions",
    "scene_release_governance_count_entries",
    "scene_release_governance_detail_count_entries",
    "scene_release_governance_drilldown_source_marker_entries",
    "scene_release_governance_drilldown_id",
    "scene_release_governance_payload_entries",
    "scene_release_governance_report_id",
    "scene_release_governance_report_pairs",
    "scene_release_governance_report_spec",
]
