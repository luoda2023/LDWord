import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    RELEASE_GATE_PAYLOAD_CHECK_IDS,
    RELEASE_GATE_RELEASE_GOVERNANCE_SOURCE_MARKER_IDS,
    _print_human,
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_release_acceptance_certificate_audit import (  # noqa: E402
    audit_scene_release_acceptance_certificate_report,
    build_scene_release_acceptance_certificate_audit_report,
)
from src.config.scene_external_handoff_contract_audit import (  # noqa: E402
    build_scene_external_handoff_contract_audit_report,
)
from src.config.scene_matrix_dashboard_lenses import (  # noqa: E402
    SCENE_MATRIX_DASHBOARD_LENSES,
    SCENE_MATRIX_DASHBOARD_SOURCE_IDS,
)
from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
    SCENE_RELEASE_GOVERNANCE_ACCEPTANCE_CERTIFICATE_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_BOUNDARY_GUARDED_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_BOUNDARY_MATURITY_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_BOUNDARY_READINESS_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_CLOSURE_LEDGER_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
    SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPEC_GROUPS,
    SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_IDS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID,
    SCENE_RELEASE_GOVERNANCE_GATE_REPORT_IDS,
    SCENE_RELEASE_GOVERNANCE_NON_SUBJECT_TRACE_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_PAYLOAD_REPORT_IDS,
    SCENE_RELEASE_GOVERNANCE_PROJECTION_PARITY_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_RESIDUAL_EXPLANATION_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_RESIDUAL_RATIO_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_RESIDUAL_WARNING_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_RETAINED_GAP_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_SUBJECT_CONTINUITY_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_SUBJECT_DOSSIER_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_TERMINAL_EXCEPTION_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_TRACE_PARTITION_COUNT_SPECS,
    build_scene_release_governance_report,
    resolve_scene_release_governance_functions,
    scene_release_governance_count_entries,
    scene_release_governance_detail_count_entries,
    scene_release_governance_payload_entries,
    scene_release_governance_report_id,
    scene_release_governance_report_spec,
)


class _FakeReleaseGovernanceReport:
    def __init__(self, source_id: str, **counts: int) -> None:
        self.source_id = source_id
        for name, value in counts.items():
            setattr(self, name, value)

    def to_payload(self) -> dict[str, str]:
        return {"source_id": self.source_id}


def test_release_governance_registry_defines_export_certificate_surface():
    # Fixed 15 is the release-governance scope contract, not a derived helper count.
    assert len(SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS) == 15
    assert len(set(SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_IDS)) == 15
    assert SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_IDS[-1] == (
        SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID
    )
    assert all(
        spec.export_script_path.startswith("scripts/export_scene_")
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert all(
        (ROOT / spec.export_script_path).exists()
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert all(
        (ROOT / spec.test_path).exists()
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert all(
        spec.module_path.startswith("src.config.")
        and spec.builder_name.startswith("build_scene_")
        and spec.audit_name.startswith("audit_scene_")
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert all(
        scene_release_governance_report_spec(spec.report_id) == spec
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert len(
        {spec.report_attribute for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS}
    ) == 15
    assert all(
        scene_release_governance_report_id(spec.report_attribute) == spec.report_id
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert scene_release_governance_report_spec(
        "scene_retained_gap_exit_criteria_audit"
    ).builder_dependency_names == (
        "boundary_maturity_release_envelope_report",
        "external_handoff_contract_report",
        "boundary_guarded_completion_report",
    )
    assert scene_release_governance_report_spec(
        "scene_release_residual_explanation_audit"
    ).builder_dependency_names == (
        "input_source_report",
        "count_profile_report",
        "residual_warning_governance_report",
        "terminal_release_exception_report",
        "boundary_maturity_release_envelope_report",
        "release_residual_ratio_ledger_report",
        "maturity_upgrade_report",
        "dashboard_warning_count",
    )


def test_release_governance_registry_matches_dashboard_gate_and_workflow(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)
    workflow = (
        ROOT / ".github" / "workflows" / "scene-matrix-release-gate.yml"
    ).read_text(encoding="utf-8")
    report_ids = tuple(
        spec.report_id for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    registry_count_ids = tuple(
        spec.count_id
        for spec in (
            *SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS,
            *SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS,
        )
    )

    assert set(report_ids) <= set(SCENE_MATRIX_DASHBOARD_SOURCE_IDS)
    assert set(SCENE_RELEASE_GOVERNANCE_GATE_REPORT_IDS) <= set(payload["checks"])
    assert set(SCENE_RELEASE_GOVERNANCE_PAYLOAD_REPORT_IDS) <= set(payload)
    assert set(registry_count_ids) <= set(payload["counts"])
    assert len(set(registry_count_ids)) == len(registry_count_ids)
    assert all(
        spec.test_path in workflow
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    lenses = {
        lens.lens_id: lens for lens in SCENE_MATRIX_DASHBOARD_LENSES
    }
    for lens_id in (
        "user_request",
        "carrier_layer",
        "boundary",
        "evidence_chain",
        "product_readiness",
    ):
        assert set(report_ids) <= set(lenses[lens_id].source_ids)


def test_release_governance_registry_resolves_builder_and_audit_functions():
    resolved = tuple(
        resolve_scene_release_governance_functions(spec)
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )

    assert len(resolved) == len(SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS)
    assert all(
        callable(builder) and callable(auditor) for builder, auditor in resolved
    )


def test_release_governance_registry_builds_reports_with_dependencies():
    guarded_report = build_scene_release_governance_report(
        "scene_boundary_guarded_completion_audit",
        project_root=ROOT,
    )
    envelope_report = build_scene_release_governance_report(
        "scene_boundary_maturity_release_envelope_audit",
        project_root=ROOT,
    )
    external_handoff_report = build_scene_external_handoff_contract_audit_report(
        project_root=ROOT
    )
    retained_gap_report = build_scene_release_governance_report(
        "scene_retained_gap_exit_criteria_audit",
        project_root=ROOT,
        dependencies={
            "boundary_maturity_release_envelope_report": envelope_report,
            "external_handoff_contract_report": external_handoff_report,
            "boundary_guarded_completion_report": guarded_report,
        },
        require_dependencies=True,
    )

    assert guarded_report.status == "passed"
    assert envelope_report.status == "passed"
    assert external_handoff_report.status == "passed"
    assert retained_gap_report.status == "passed"

    with pytest.raises(KeyError, match="external_handoff_contract_report"):
        build_scene_release_governance_report(
            "scene_retained_gap_exit_criteria_audit",
            project_root=ROOT,
            dependencies={
                "boundary_maturity_release_envelope_report": envelope_report,
                "boundary_guarded_completion_report": guarded_report,
            },
            require_dependencies=True,
        )


def test_release_governance_registry_matches_release_gate_check_ids():
    assert set(SCENE_RELEASE_GOVERNANCE_GATE_REPORT_IDS) == set(
        SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_IDS
    )

    release_governance_check_set = set(SCENE_RELEASE_GOVERNANCE_GATE_REPORT_IDS)
    gate_release_governance_ids = tuple(
        check_id
        for check_id in RELEASE_GATE_PAYLOAD_CHECK_IDS
        if check_id in release_governance_check_set
    )

    assert gate_release_governance_ids == (
        *SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS,
        *SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
    )
    assert RELEASE_GATE_RELEASE_GOVERNANCE_SOURCE_MARKER_IDS == (
        *SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS,
        *SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
    )
    assert (
        SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID
        in RELEASE_GATE_PAYLOAD_CHECK_IDS
    )


def test_release_governance_registry_builds_payload_entries():
    reports = {
        spec.report_attribute: _FakeReleaseGovernanceReport(spec.report_id)
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    }

    entries = scene_release_governance_payload_entries(reports)

    assert tuple(entries) == SCENE_RELEASE_GOVERNANCE_PAYLOAD_REPORT_IDS
    assert set(entries) == set(SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_IDS)
    assert all(
        entries[report_id]["source_id"] == report_id
        for report_id in SCENE_RELEASE_GOVERNANCE_PAYLOAD_REPORT_IDS
    )

    missing_spec = scene_release_governance_report_spec(
        "scene_release_residual_explanation_audit"
    )
    incomplete_reports = dict(reports)
    incomplete_reports.pop(missing_spec.report_attribute)
    with pytest.raises(KeyError, match=missing_spec.report_attribute):
        scene_release_governance_payload_entries(incomplete_reports)


def test_release_governance_registry_builds_summary_count_entries():
    reports = {
        "terminal_release_exception_report": _FakeReleaseGovernanceReport(
            "scene_terminal_release_exception_audit",
            static_closed_boundary_count=2,
            warning_projection_count=3,
        ),
        "residual_warning_governance_report": _FakeReleaseGovernanceReport(
            "scene_residual_warning_governance_audit",
            input_source_managed_warning_count=5,
            count_profile_managed_warning_count=2,
            plugin_manual_managed_warning_count=5,
            reference_profile_managed_warning_count=2,
            visio_fixture_closed_count=1,
        ),
        "boundary_maturity_release_envelope_report": (
            _FakeReleaseGovernanceReport(
                "scene_boundary_maturity_release_envelope_audit",
                retained_gap_count=6,
            )
        ),
    }

    entries = scene_release_governance_count_entries(reports)

    assert tuple(entries) == tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS
    )
    assert entries == {
        "static_closed_not_green_governed_count": 2,
        "dashboard_warning_projection_governed_count": 3,
        "input_source_warning_managed_count": 5,
        "count_profile_warning_managed_count": 2,
        "plugin_manual_warning_managed_count": 5,
        "reference_profile_warning_managed_count": 2,
        "visio_fixture_closed_verified_count": 1,
        "retained_gap_enveloped_count": 6,
    }

    incomplete_reports = dict(reports)
    incomplete_reports.pop("boundary_maturity_release_envelope_report")
    with pytest.raises(KeyError, match="boundary_maturity_release_envelope_report"):
        scene_release_governance_count_entries(incomplete_reports)


def test_release_governance_registry_builds_residual_warning_count_entries():
    reports = {
        "residual_warning_governance_report": _FakeReleaseGovernanceReport(
            "scene_residual_warning_governance_audit",
            warning_count=10,
            managed_warning_count=10,
            input_source_warning_count=5,
            count_profile_warning_count=2,
            dashboard_projection_warning_count=3,
            plugin_manual_warning_count=5,
            reference_profile_warning_count=2,
            object_preflight_warning_count=1,
            visio_fixture_closed_count=1,
            unmanaged_warning_count=0,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_RESIDUAL_WARNING_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id
        for spec in SCENE_RELEASE_GOVERNANCE_RESIDUAL_WARNING_COUNT_SPECS
    )
    assert entries == {
        "scene_residual_warning_governance_warning_count": 10,
        "scene_residual_warning_governance_managed_count": 10,
        "scene_residual_warning_governance_input_source_warning_count": 5,
        "scene_residual_warning_governance_count_profile_warning_count": 2,
        "scene_residual_warning_governance_dashboard_projection_warning_count": 3,
        "scene_residual_warning_governance_plugin_manual_warning_count": 5,
        "scene_residual_warning_governance_reference_profile_warning_count": 2,
        "scene_residual_warning_governance_object_preflight_warning_count": 1,
        "scene_residual_warning_governance_visio_fixture_closed_count": 1,
        "scene_residual_warning_governance_unmanaged_warning_count": 0,
        "scene_residual_warning_governance_issue_count": 0,
        "scene_residual_warning_governance_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="residual_warning_governance_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_RESIDUAL_WARNING_COUNT_SPECS,
        )


def test_release_governance_registry_builds_boundary_guarded_count_entries():
    reports = {
        "boundary_guarded_completion_report": _FakeReleaseGovernanceReport(
            "scene_boundary_guarded_completion_audit",
            subject_count=6,
            ready_subject_count=6,
            pack_subject_count=4,
            family_subject_count=2,
            retained_gap_count=6,
            external_contract_count=6,
            boundary_capability_count=6,
            plugin_gate_count=4,
            target_plugin_count=3,
            risk_domain_count=5,
            excluded_core_claim_count=0,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_BOUNDARY_GUARDED_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_BOUNDARY_GUARDED_COUNT_SPECS
    )
    assert entries == {
        "scene_boundary_guarded_completion_subject_count": 6,
        "scene_boundary_guarded_completion_ready_count": 6,
        "scene_boundary_guarded_completion_pack_count": 4,
        "scene_boundary_guarded_completion_family_count": 2,
        "scene_boundary_guarded_completion_retained_gap_count": 6,
        "scene_boundary_guarded_completion_external_contract_count": 6,
        "scene_boundary_guarded_completion_boundary_capability_count": 6,
        "scene_boundary_guarded_completion_plugin_gate_count": 4,
        "scene_boundary_guarded_completion_target_plugin_count": 3,
        "scene_boundary_guarded_completion_risk_domain_count": 5,
        "scene_boundary_guarded_completion_excluded_core_claim_count": 0,
        "scene_boundary_guarded_completion_issue_count": 0,
        "scene_boundary_guarded_completion_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="boundary_guarded_completion_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_BOUNDARY_GUARDED_COUNT_SPECS,
        )


def test_release_governance_registry_builds_boundary_readiness_count_entries():
    reports = {
        "boundary_readiness_reconciliation_report": _FakeReleaseGovernanceReport(
            "scene_boundary_readiness_reconciliation_audit",
            row_count=15,
            reconciled_count=15,
            unreconciled_count=0,
            readiness_delta_count=4,
            not_applicable_count=1,
            static_closed_boundary_count=2,
            maturity_boundary_guarded_count=6,
            boundary_subject_count=6,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_BOUNDARY_READINESS_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id
        for spec in SCENE_RELEASE_GOVERNANCE_BOUNDARY_READINESS_COUNT_SPECS
    )
    assert entries == {
        "scene_boundary_readiness_reconciliation_count": 15,
        "scene_boundary_readiness_reconciliation_reconciled_count": 15,
        "scene_boundary_readiness_reconciliation_unreconciled_count": 0,
        "scene_boundary_readiness_reconciliation_readiness_delta_count": 4,
        "scene_boundary_readiness_reconciliation_not_applicable_count": 1,
        "scene_boundary_readiness_reconciliation_static_closed_boundary_count": 2,
        "scene_boundary_readiness_reconciliation_maturity_boundary_guarded_count": 6,
        "scene_boundary_readiness_reconciliation_boundary_subject_count": 6,
        "scene_boundary_readiness_reconciliation_issue_count": 0,
        "scene_boundary_readiness_reconciliation_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="boundary_readiness_reconciliation_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_BOUNDARY_READINESS_COUNT_SPECS,
        )


def test_release_governance_registry_builds_terminal_exception_count_entries():
    reports = {
        "terminal_release_exception_report": _FakeReleaseGovernanceReport(
            "scene_terminal_release_exception_audit",
            exception_count=5,
            governed_exception_count=5,
            ungoverned_exception_count=0,
            managed_warning_count=10,
            warning_projection_count=3,
            readiness_reconciliation_count=15,
            boundary_guarded_maturity_count=6,
            static_closed_boundary_count=2,
            exception_trace_count=36,
            unique_source_trace_count=12,
            linked_boundary_subject_count=6,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_TERMINAL_EXCEPTION_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id
        for spec in SCENE_RELEASE_GOVERNANCE_TERMINAL_EXCEPTION_COUNT_SPECS
    )
    assert entries == {
        "scene_terminal_release_exception_count": 5,
        "scene_terminal_release_exception_governed_count": 5,
        "scene_terminal_release_exception_ungoverned_count": 0,
        "scene_terminal_release_exception_managed_warning_count": 10,
        "scene_terminal_release_exception_warning_projection_count": 3,
        "scene_terminal_release_exception_readiness_reconciliation_count": 15,
        "scene_terminal_release_exception_boundary_guarded_maturity_count": 6,
        "scene_terminal_release_exception_static_closed_boundary_count": 2,
        "scene_terminal_release_exception_trace_count": 36,
        "scene_terminal_release_exception_unique_source_trace_count": 12,
        "scene_terminal_release_exception_linked_boundary_subject_count": 6,
        "scene_terminal_release_exception_issue_count": 0,
        "scene_terminal_release_exception_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="terminal_release_exception_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_TERMINAL_EXCEPTION_COUNT_SPECS,
        )


def test_release_governance_registry_builds_subject_dossier_count_entries():
    reports = {
        "boundary_subject_release_dossier_report": _FakeReleaseGovernanceReport(
            "scene_boundary_subject_release_dossier_audit",
            subject_count=6,
            ready_subject_count=6,
            pack_subject_count=4,
            family_subject_count=2,
            subject_trace_count=26,
            unique_source_trace_count=12,
            readiness_reconciliation_row_count=15,
            terminal_exception_count=5,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_SUBJECT_DOSSIER_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_SUBJECT_DOSSIER_COUNT_SPECS
    )
    assert entries == {
        "scene_boundary_subject_release_dossier_subject_count": 6,
        "scene_boundary_subject_release_dossier_ready_count": 6,
        "scene_boundary_subject_release_dossier_pack_subject_count": 4,
        "scene_boundary_subject_release_dossier_family_subject_count": 2,
        "scene_boundary_subject_release_dossier_subject_trace_count": 26,
        "scene_boundary_subject_release_dossier_unique_source_trace_count": 12,
        "scene_boundary_subject_release_dossier_readiness_reconciliation_row_count": 15,
        "scene_boundary_subject_release_dossier_terminal_exception_count": 5,
        "scene_boundary_subject_release_dossier_issue_count": 0,
        "scene_boundary_subject_release_dossier_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="boundary_subject_release_dossier_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_SUBJECT_DOSSIER_COUNT_SPECS,
        )


def test_release_governance_registry_builds_non_subject_trace_count_entries():
    reports = {
        "non_subject_release_trace_attribution_report": (
            _FakeReleaseGovernanceReport(
                "scene_non_subject_release_trace_attribution_audit",
                trace_count=10,
                attributed_trace_count=10,
                unattributed_trace_count=0,
                dashboard_projection_trace_count=3,
                registry_only_profile_trace_count=2,
                plugin_manual_pack_trace_count=5,
                generic_not_applicable_trace_count=1,
                issue_count=0,
                missing_source_evidence_count=0,
            )
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_NON_SUBJECT_TRACE_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id
        for spec in SCENE_RELEASE_GOVERNANCE_NON_SUBJECT_TRACE_COUNT_SPECS
    )
    assert entries == {
        "scene_non_subject_release_trace_attribution_count": 10,
        "scene_non_subject_release_trace_attribution_ready_count": 10,
        "scene_non_subject_release_trace_attribution_unattributed_count": 0,
        "scene_non_subject_release_trace_attribution_dashboard_projection_count": 3,
        "scene_non_subject_release_trace_attribution_registry_only_profile_count": 2,
        "scene_non_subject_release_trace_attribution_plugin_manual_pack_count": 5,
        "scene_non_subject_release_trace_attribution_generic_not_applicable_count": 1,
        "scene_non_subject_release_trace_attribution_issue_count": 0,
        "scene_non_subject_release_trace_attribution_missing_source_evidence_count": 0,
    }

    with pytest.raises(
        KeyError,
        match="non_subject_release_trace_attribution_report",
    ):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_NON_SUBJECT_TRACE_COUNT_SPECS,
        )


def test_release_governance_registry_builds_trace_partition_count_entries():
    reports = {
        "release_trace_partition_guard_report": _FakeReleaseGovernanceReport(
            "scene_release_trace_partition_guard_audit",
            partition_count=36,
            ready_partition_count=36,
            terminal_trace_count=12,
            subject_trace_count=14,
            non_subject_trace_count=10,
            partitioned_trace_count=36,
            missing_trace_count=0,
            overlap_trace_count=0,
            extra_trace_count=0,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_TRACE_PARTITION_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_TRACE_PARTITION_COUNT_SPECS
    )
    assert entries == {
        "scene_release_trace_partition_guard_partition_count": 36,
        "scene_release_trace_partition_guard_ready_count": 36,
        "scene_release_trace_partition_guard_terminal_trace_count": 12,
        "scene_release_trace_partition_guard_subject_trace_count": 14,
        "scene_release_trace_partition_guard_non_subject_trace_count": 10,
        "scene_release_trace_partition_guard_partitioned_trace_count": 36,
        "scene_release_trace_partition_guard_missing_trace_count": 0,
        "scene_release_trace_partition_guard_overlap_trace_count": 0,
        "scene_release_trace_partition_guard_extra_trace_count": 0,
        "scene_release_trace_partition_guard_issue_count": 0,
        "scene_release_trace_partition_guard_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="release_trace_partition_guard_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_TRACE_PARTITION_COUNT_SPECS,
        )


def test_release_governance_registry_builds_projection_parity_count_entries():
    reports = {
        "release_projection_surface_parity_report": _FakeReleaseGovernanceReport(
            "scene_release_projection_surface_parity_audit",
            projection_count=13,
            ready_projection_count=13,
            release_gate_check_count=15,
            dashboard_source_count=13,
            dashboard_card_count=13,
            drilldown_item_count=37,
            summary_projection_count=13,
            export_script_count=15,
            workflow_test_count=12,
            closure_doc_count=1,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_PROJECTION_PARITY_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id
        for spec in SCENE_RELEASE_GOVERNANCE_PROJECTION_PARITY_COUNT_SPECS
    )
    assert entries == {
        "scene_release_projection_surface_parity_count": 13,
        "scene_release_projection_surface_parity_ready_count": 13,
        "scene_release_projection_surface_parity_release_gate_check_count": 15,
        "scene_release_projection_surface_parity_dashboard_source_count": 13,
        "scene_release_projection_surface_parity_dashboard_card_count": 13,
        "scene_release_projection_surface_parity_drilldown_item_count": 37,
        "scene_release_projection_surface_parity_summary_projection_count": 13,
        "scene_release_projection_surface_parity_export_script_count": 15,
        "scene_release_projection_surface_parity_workflow_test_count": 12,
        "scene_release_projection_surface_parity_closure_doc_count": 1,
        "scene_release_projection_surface_parity_issue_count": 0,
        "scene_release_projection_surface_parity_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="release_projection_surface_parity_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_PROJECTION_PARITY_COUNT_SPECS,
        )


def test_release_governance_registry_builds_subject_continuity_count_entries():
    reports = {
        "boundary_subject_release_continuity_report": _FakeReleaseGovernanceReport(
            "scene_boundary_subject_release_continuity_audit",
            subject_count=6,
            ready_subject_count=6,
            maturity_subject_count=6,
            guarded_completion_subject_count=6,
            readiness_reconciliation_subject_count=6,
            terminal_release_subject_count=6,
            subject_dossier_count=6,
            readiness_row_count=15,
            terminal_trace_count=12,
            dossier_trace_count=26,
            mismatch_count=0,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_SUBJECT_CONTINUITY_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id
        for spec in SCENE_RELEASE_GOVERNANCE_SUBJECT_CONTINUITY_COUNT_SPECS
    )
    assert entries == {
        "scene_boundary_subject_release_continuity_subject_count": 6,
        "scene_boundary_subject_release_continuity_ready_count": 6,
        "scene_boundary_subject_release_continuity_maturity_subject_count": 6,
        "scene_boundary_subject_release_continuity_guarded_completion_subject_count": 6,
        "scene_boundary_subject_release_continuity_readiness_reconciliation_subject_count": 6,
        "scene_boundary_subject_release_continuity_terminal_release_subject_count": 6,
        "scene_boundary_subject_release_continuity_dossier_count": 6,
        "scene_boundary_subject_release_continuity_readiness_row_count": 15,
        "scene_boundary_subject_release_continuity_terminal_trace_count": 12,
        "scene_boundary_subject_release_continuity_dossier_trace_count": 26,
        "scene_boundary_subject_release_continuity_mismatch_count": 0,
        "scene_boundary_subject_release_continuity_issue_count": 0,
        "scene_boundary_subject_release_continuity_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="boundary_subject_release_continuity_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_SUBJECT_CONTINUITY_COUNT_SPECS,
        )


def test_release_governance_registry_builds_closure_ledger_count_entries():
    reports = {
        "release_closure_ledger_report": _FakeReleaseGovernanceReport(
            "scene_release_closure_ledger_audit",
            stage_count=13,
            ready_stage_count=13,
            stage_order_count=13,
            upstream_dependency_count=12,
            upstream_dependency_ready_count=12,
            release_gate_check_count=15,
            dashboard_source_count=13,
            dashboard_card_count=13,
            drilldown_item_count=37,
            summary_projection_count=13,
            export_script_count=15,
            workflow_test_count=12,
            closure_doc_count=1,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_CLOSURE_LEDGER_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_CLOSURE_LEDGER_COUNT_SPECS
    )
    assert entries == {
        "scene_release_closure_ledger_stage_count": 13,
        "scene_release_closure_ledger_ready_count": 13,
        "scene_release_closure_ledger_stage_order_count": 13,
        "scene_release_closure_ledger_upstream_dependency_count": 12,
        "scene_release_closure_ledger_upstream_dependency_ready_count": 12,
        "scene_release_closure_ledger_release_gate_check_count": 15,
        "scene_release_closure_ledger_dashboard_source_count": 13,
        "scene_release_closure_ledger_dashboard_card_count": 13,
        "scene_release_closure_ledger_drilldown_item_count": 37,
        "scene_release_closure_ledger_summary_projection_count": 13,
        "scene_release_closure_ledger_export_script_count": 15,
        "scene_release_closure_ledger_workflow_test_count": 12,
        "scene_release_closure_ledger_closure_doc_count": 1,
        "scene_release_closure_ledger_issue_count": 0,
        "scene_release_closure_ledger_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="release_closure_ledger_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_CLOSURE_LEDGER_COUNT_SPECS,
        )


def test_release_governance_registry_builds_boundary_maturity_count_entries():
    reports = {
        "boundary_maturity_release_envelope_report": _FakeReleaseGovernanceReport(
            "scene_boundary_maturity_release_envelope_audit",
            envelope_count=6,
            ready_envelope_count=6,
            l5_blocker_enveloped_count=6,
            maturity_boundary_count=6,
            external_handoff_count=6,
            guarded_completion_count=6,
            readiness_reconciliation_count=15,
            terminal_trace_count=12,
            release_dossier_count=6,
            subject_continuity_count=6,
            retained_gap_count=6,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_BOUNDARY_MATURITY_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id
        for spec in SCENE_RELEASE_GOVERNANCE_BOUNDARY_MATURITY_COUNT_SPECS
    )
    assert entries == {
        "scene_boundary_maturity_release_envelope_count": 6,
        "scene_boundary_maturity_release_envelope_ready_count": 6,
        "scene_boundary_maturity_release_envelope_l5_blocker_enveloped_count": 6,
        "scene_boundary_maturity_release_envelope_maturity_boundary_count": 6,
        "scene_boundary_maturity_release_envelope_external_handoff_count": 6,
        "scene_boundary_maturity_release_envelope_guarded_completion_count": 6,
        "scene_boundary_maturity_release_envelope_readiness_reconciliation_count": 15,
        "scene_boundary_maturity_release_envelope_terminal_trace_count": 12,
        "scene_boundary_maturity_release_envelope_release_dossier_count": 6,
        "scene_boundary_maturity_release_envelope_subject_continuity_count": 6,
        "scene_boundary_maturity_release_envelope_retained_gap_count": 6,
        "scene_boundary_maturity_release_envelope_issue_count": 0,
        "scene_boundary_maturity_release_envelope_missing_source_evidence_count": 0,
    }

    with pytest.raises(
        KeyError,
        match="boundary_maturity_release_envelope_report",
    ):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_BOUNDARY_MATURITY_COUNT_SPECS,
        )


def test_release_governance_registry_builds_retained_gap_count_entries():
    reports = {
        "retained_gap_exit_criteria_report": _FakeReleaseGovernanceReport(
            "scene_retained_gap_exit_criteria_audit",
            criteria_count=6,
            release_allowed_count=6,
            envelope_link_count=6,
            handoff_link_count=6,
            guarded_completion_link_count=6,
            boundary_capability_link_count=6,
            exit_signal_count=6,
            external_receipt_target_count=6,
            external_receipt_alignment_count=6,
            prohibited_core_claim_count=0,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_RETAINED_GAP_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_RETAINED_GAP_COUNT_SPECS
    )
    assert entries == {
        "scene_retained_gap_exit_criteria_count": 6,
        "scene_retained_gap_exit_criteria_release_allowed_count": 6,
        "scene_retained_gap_exit_criteria_envelope_link_count": 6,
        "scene_retained_gap_exit_criteria_handoff_link_count": 6,
        "scene_retained_gap_exit_criteria_guarded_completion_link_count": 6,
        "scene_retained_gap_exit_criteria_boundary_capability_link_count": 6,
        "scene_retained_gap_exit_criteria_exit_signal_count": 6,
        "scene_retained_gap_external_receipt_target_count": 6,
        "scene_retained_gap_external_receipt_alignment_count": 6,
        "scene_retained_gap_exit_criteria_prohibited_core_claim_count": 0,
        "scene_retained_gap_exit_criteria_issue_count": 0,
        "scene_retained_gap_exit_criteria_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="retained_gap_exit_criteria_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_RETAINED_GAP_COUNT_SPECS,
        )


def test_release_governance_registry_builds_residual_ratio_count_entries():
    reports = {
        "release_residual_ratio_ledger_report": _FakeReleaseGovernanceReport(
            "scene_release_residual_ratio_ledger_audit",
            ratio_count=3,
            published_ratio_count=3,
            non_full_ratio_count=3,
            readiness_reconciliation_link_count=3,
            terminal_exception_link_count=3,
            release_envelope_link_count=3,
            retained_gap_exit_criteria_link_count=10,
            retained_gap_receipt_alignment_link_count=10,
            count_delivery_boundary_alignment_count=4,
            count_delivery_boundary_link_count=4,
            count_delivery_receipt_alignment_count=4,
            count_delivery_receipt_alignment_link_count=4,
            maturity_l5_blocker_alignment_count=6,
            maturity_l5_blocker_release_envelope_count=6,
            maturity_l5_blocker_receipt_alignment_count=6,
            maturity_l5_blocker_receipt_alignment_link_count=6,
            boundary_scope_alignment_count=6,
            boundary_scope_link_count=6,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_RESIDUAL_RATIO_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_RESIDUAL_RATIO_COUNT_SPECS
    )
    assert entries == {
        "scene_release_residual_ratio_ledger_count": 3,
        "scene_release_residual_ratio_ledger_published_count": 3,
        "scene_release_residual_ratio_ledger_non_full_count": 3,
        "scene_release_residual_ratio_ledger_readiness_reconciliation_link_count": 3,
        "scene_release_residual_ratio_ledger_terminal_exception_link_count": 3,
        "scene_release_residual_ratio_ledger_release_envelope_link_count": 3,
        "scene_release_residual_ratio_ledger_exit_criteria_link_count": 10,
        "scene_release_residual_ratio_ledger_receipt_alignment_link_count": 10,
        "scene_release_residual_ratio_ledger_count_delivery_boundary_alignment_count": 4,
        "scene_release_residual_ratio_ledger_count_delivery_boundary_link_count": 4,
        "scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_count": 4,
        "scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count": 4,
        "scene_release_residual_ratio_ledger_maturity_l5_blocker_alignment_count": 6,
        "scene_release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count": 6,
        "scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count": 6,
        "scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count": 6,
        "scene_release_residual_ratio_ledger_boundary_scope_alignment_count": 6,
        "scene_release_residual_ratio_ledger_boundary_scope_link_count": 6,
        "scene_release_residual_ratio_ledger_issue_count": 0,
        "scene_release_residual_ratio_ledger_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="release_residual_ratio_ledger_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_RESIDUAL_RATIO_COUNT_SPECS,
        )


def test_release_governance_registry_builds_residual_explanation_count_entries():
    reports = {
        "release_residual_explanation_report": _FakeReleaseGovernanceReport(
            "scene_release_residual_explanation_audit",
            row_count=14,
            covered_count=14,
            mismatch_count=0,
            missing_summary_marker_count=0,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_RESIDUAL_EXPLANATION_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id
        for spec in SCENE_RELEASE_GOVERNANCE_RESIDUAL_EXPLANATION_COUNT_SPECS
    )
    assert entries == {
        "scene_release_residual_explanation_count": 14,
        "scene_release_residual_explanation_covered_count": 14,
        "scene_release_residual_explanation_mismatch_count": 0,
        "scene_release_residual_explanation_missing_summary_marker_count": 0,
        "scene_release_residual_explanation_issue_count": 0,
        "scene_release_residual_explanation_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="release_residual_explanation_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_RESIDUAL_EXPLANATION_COUNT_SPECS,
        )


def test_release_governance_registry_builds_export_script_count_entries():
    reports = {
        "release_governance_export_script_counts": {
            "report_count": 15,
            "ready_count": 15,
            "missing_count": 0,
            "unready_count": 0,
        }
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_COUNT_SPECS
    )
    assert entries == {
        "scene_release_governance_export_script_report_count": 15,
        "scene_release_governance_export_script_ready_count": 15,
        "scene_release_governance_export_script_missing_count": 0,
        "scene_release_governance_export_script_unready_count": 0,
    }

    with pytest.raises(KeyError, match="release_governance_export_script_counts"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_COUNT_SPECS,
        )


def test_release_governance_registry_builds_acceptance_certificate_count_entries():
    reports = {
        "release_acceptance_certificate_report": _FakeReleaseGovernanceReport(
            "scene_release_acceptance_certificate_audit",
            certificate_count=14,
            ready_certificate_count=14,
            receipt_certificate_count=2,
            ready_receipt_certificate_count=2,
            component_report_count=14,
            requirement_dimension_count=10,
            ready_requirement_dimension_count=10,
            expected_count_match_count=14,
            source_evidence_count=15,
            ready_source_evidence_count=15,
            issue_count=0,
            missing_source_evidence_count=0,
        )
    }

    entries = scene_release_governance_count_entries(
        reports,
        SCENE_RELEASE_GOVERNANCE_ACCEPTANCE_CERTIFICATE_COUNT_SPECS,
    )

    assert tuple(entries) == tuple(
        spec.count_id
        for spec in SCENE_RELEASE_GOVERNANCE_ACCEPTANCE_CERTIFICATE_COUNT_SPECS
    )
    assert entries == {
        "scene_release_acceptance_certificate_count": 14,
        "scene_release_acceptance_certificate_ready_count": 14,
        "scene_release_acceptance_certificate_receipt_count": 2,
        "scene_release_acceptance_certificate_ready_receipt_count": 2,
        "scene_release_acceptance_certificate_component_report_count": 14,
        "scene_release_acceptance_certificate_requirement_dimension_count": 10,
        "scene_release_acceptance_certificate_ready_requirement_dimension_count": 10,
        "scene_release_acceptance_certificate_expected_count_match_count": 14,
        "scene_release_acceptance_certificate_source_evidence_count": 15,
        "scene_release_acceptance_certificate_ready_source_evidence_count": 15,
        "scene_release_acceptance_certificate_issue_count": 0,
        "scene_release_acceptance_certificate_missing_source_evidence_count": 0,
    }

    with pytest.raises(KeyError, match="release_acceptance_certificate_report"):
        scene_release_governance_count_entries(
            {},
            SCENE_RELEASE_GOVERNANCE_ACCEPTANCE_CERTIFICATE_COUNT_SPECS,
        )


def test_release_governance_registry_builds_detail_count_entries():
    reports = {}
    expected_values: dict[str, int] = {}
    for value, spec in enumerate(
        SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS,
        start=1,
    ):
        expected_values[spec.count_id] = value
        if spec.report_attribute == "release_governance_export_script_counts":
            reports.setdefault(spec.report_attribute, {})[spec.value_attribute] = value
        else:
            report = reports.setdefault(
                spec.report_attribute,
                _FakeReleaseGovernanceReport(spec.report_attribute),
            )
            setattr(report, spec.value_attribute, value)

    entries = scene_release_governance_detail_count_entries(reports)

    assert len(SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS) == sum(
        len(group) for group in SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPEC_GROUPS
    )
    detail_count_ids = tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS
    )
    assert len(set(detail_count_ids)) == len(detail_count_ids)
    assert tuple(entries) == tuple(
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS
    )
    assert entries == expected_values

    incomplete_reports = dict(reports)
    incomplete_reports.pop("release_governance_export_script_counts")
    with pytest.raises(KeyError, match="release_governance_export_script_counts"):
        scene_release_governance_detail_count_entries(incomplete_reports)


def test_release_acceptance_certificate_certifies_release_surfaces():
    report = build_scene_release_acceptance_certificate_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.certificate_id: row for row in report.rows}

    assert report.status == "passed"
    assert audit_scene_release_acceptance_certificate_report(report) == ()
    assert payload["source_id"] == "scene_release_acceptance_certificate_audit"
    assert report.certificate_count == 14
    assert report.ready_certificate_count == 14
    assert report.receipt_certificate_count == 2
    assert report.ready_receipt_certificate_count == 2
    assert report.component_report_count == 14
    assert report.expected_count_match_count == 14
    assert payload["counts"]["receipt_certificate_count"] == 2
    assert payload["counts"]["ready_receipt_certificate_count"] == 2
    assert payload["counts"]["requirement_dimension_count"] == 10
    assert payload["counts"]["ready_requirement_dimension_count"] == 10
    # Acceptance evidence must cover the full release-governance scope.
    assert payload["counts"]["source_evidence_count"] == 15
    assert payload["counts"]["ready_source_evidence_count"] == 15
    assert report.issue_count == 0
    assert report.missing_source_evidence_count == 0
    source_status = {
        item["source_id"]: item["status"] for item in payload["source_evidence"]
    }
    assert source_status["scene_matrix_dashboard"] == "ready"
    assert source_status["summary_projection"] == "ready"
    assert source_status["release_gate"] == "ready"
    assert source_status["export_script"] == "ready"
    assert source_status["acceptance_certificate_test"] == "ready"
    assert source_status["n2_394_plan"] == "ready"
    assert source_status["n2_395_requirement_trace_plan"] == "ready"
    assert source_status["n2_397_retained_gap_receipt_plan"] == "ready"
    assert source_status["n2_398_residual_ratio_receipt_plan"] == "ready"
    assert source_status["n2_399_projection_trace_plan"] == "ready"
    assert source_status["n2_400_acceptance_receipt_plan"] == "ready"

    assert rows["high_frequency_coverage"].observed_ratio == "12/12"
    assert rows["release_projection_surface_parity"].observed_ratio == "13/13"
    assert rows["release_closure_ledger"].observed_ratio == "13/13"
    assert rows["boundary_maturity_release_envelope"].observed_ratio == "6/6"
    assert rows["release_residual_ratio_ledger"].observed_ratio == "3/3"
    assert rows["release_residual_ratio_exit_criteria"].observed_ratio == "10/10"
    assert rows["release_residual_ratio_receipts"].observed_ratio == "10/10"
    assert rows["count_delivery_boundary_alignment"].observed_ratio == "4/4"
    assert rows["maturity_l5_blocker_alignment"].observed_ratio == "6/6"
    assert rows["release_residual_boundary_scope_alignment"].observed_ratio == "6/6"
    assert rows["release_residual_explanation"].observed_ratio == "14/14"
    assert rows["retained_gap_exit_criteria"].observed_ratio == "6/6"
    assert rows["retained_gap_external_receipts"].observed_ratio == "6/6"
    assert rows["release_governance_export_scripts"].observed_ratio == "15/15"
    assert all(row.status == "certificate_ready" for row in report.rows)

    dimensions = {row.dimension_id: row for row in report.requirement_dimension_rows}
    assert dimensions["high_frequency_scene_coverage"].observed_ratio == "12/12"
    assert dimensions["scene_board_control_style_consistency"].observed_ratio == "25/25"
    assert dimensions["formula_output_watermark_scene_ownership"].observed_ratio == "18/18"
    assert (
        dimensions["residual_boundary_release_governance"].observed_ratio
        == "65/65"
    )
    assert dimensions["projection_export_visibility"].observed_ratio == "28/28"
    assert all(row.status == "dimension_ready" for row in report.requirement_dimension_rows)


def test_release_acceptance_certificate_export_script_supports_json_and_markdown(
    tmp_path,
):
    output_path = tmp_path / "scene_release_acceptance_certificate.json"

    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_acceptance_certificate_audit.py",
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert json_result.stdout == ""
    assert payload["status"] == "passed"
    assert payload["counts"]["ready_certificate_count"] == 14
    assert payload["counts"]["ready_receipt_certificate_count"] == 2
    assert payload["counts"]["receipt_certificate_count"] == 2
    assert payload["counts"]["ready_requirement_dimension_count"] == 10
    rows = {row["certificate_id"]: row for row in payload["rows"]}
    dimensions = {row["dimension_id"]: row for row in payload["requirement_dimension_rows"]}
    assert rows["high_frequency_coverage"]["observed_ratio"] == "12/12"
    assert rows["high_frequency_coverage"]["expected_ratio"] == "12/12"
    assert rows["high_frequency_coverage"]["status"] == "certificate_ready"
    assert rows["release_governance_export_scripts"]["observed_ratio"] == "15/15"
    assert rows["release_governance_export_scripts"]["expected_ratio"] == "15/15"
    assert rows["count_delivery_boundary_alignment"]["observed_ratio"] == "4/4"
    assert rows["count_delivery_boundary_alignment"]["expected_ratio"] == "4/4"
    assert rows["maturity_l5_blocker_alignment"]["observed_ratio"] == "6/6"
    assert rows["maturity_l5_blocker_alignment"]["expected_ratio"] == "6/6"
    assert rows["release_residual_ratio_receipts"]["observed_ratio"] == "10/10"
    assert rows["release_residual_ratio_receipts"]["expected_ratio"] == "10/10"
    assert (
        rows["release_residual_boundary_scope_alignment"]["observed_ratio"]
        == "6/6"
    )
    assert (
        rows["release_residual_boundary_scope_alignment"]["expected_ratio"]
        == "6/6"
    )
    assert rows["retained_gap_external_receipts"]["observed_ratio"] == "6/6"
    assert rows["retained_gap_external_receipts"]["expected_ratio"] == "6/6"
    assert dimensions["high_frequency_scene_coverage"]["observed_ratio"] == "12/12"
    assert dimensions["formula_output_watermark_scene_ownership"]["status"] == (
        "dimension_ready"
    )

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_acceptance_certificate_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Release Acceptance Certificate Audit" in markdown_result.stdout
    assert "Certificates ready: 14/14" in markdown_result.stdout
    assert "Receipt certificates ready: 2/2" in markdown_result.stdout
    assert "Requirement dimensions ready: 10/10" in markdown_result.stdout
    assert "high_frequency_coverage" in markdown_result.stdout
    assert "high_frequency_scene_coverage" in markdown_result.stdout
    assert "release_projection_surface_parity" in markdown_result.stdout
    assert "release_residual_ratio_ledger" in markdown_result.stdout
    assert "release_residual_ratio_exit_criteria" in markdown_result.stdout
    assert "release_residual_ratio_receipts" in markdown_result.stdout
    assert "count_delivery_boundary_alignment" in markdown_result.stdout
    assert "maturity_l5_blocker_alignment" in markdown_result.stdout
    assert "release_residual_boundary_scope_alignment" in markdown_result.stdout
    assert "release_residual_explanation" in markdown_result.stdout
    assert "retained_gap_exit_criteria" in markdown_result.stdout
    assert "retained_gap_external_receipts" in markdown_result.stdout
    assert "release_governance_export_scripts" in markdown_result.stdout
    assert "formula_output_watermark_scene_ownership" in markdown_result.stdout


def test_release_gate_includes_release_acceptance_certificate(tmp_path, capsys):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_release_acceptance_certificate_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["high_frequency_completeness_ready_pack_count"] == 12
    assert payload["counts"]["high_frequency_completeness_pack_count"] == 12
    assert payload["counts"]["scene_release_acceptance_certificate_count"] == 14
    assert payload["counts"]["scene_release_acceptance_certificate_ready_count"] == 14
    assert payload["counts"]["scene_release_acceptance_certificate_receipt_count"] == 2
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_ready_receipt_count"
        ]
        == 2
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_requirement_dimension_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_ready_requirement_dimension_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_expected_count_match_count"
        ]
        == 14
    )
    assert payload["counts"]["scene_release_acceptance_certificate_issue_count"] == 0
    assert (
        payload["counts"]["scene_release_governance_export_script_report_count"]
        == 15
    )
    assert (
        payload["counts"]["scene_release_governance_export_script_ready_count"]
        == 15
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_source_evidence_count"
        ]
        == 15
    )
    assert (
        payload["counts"][
            "scene_retained_gap_external_receipt_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_receipt_alignment_link_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_count_delivery_boundary_alignment_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_count_delivery_boundary_link_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_boundary_scope_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_boundary_scope_link_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_ready_source_evidence_count"
        ]
        == 15
    )
    assert (
        payload["scene_release_acceptance_certificate_audit"]["counts"][
            "ready_certificate_count"
        ]
        == 14
    )
    assert (
        payload["scene_release_acceptance_certificate_audit"]["counts"][
            "ready_receipt_certificate_count"
        ]
        == 2
    )
    assert (
        payload["scene_release_acceptance_certificate_audit"]["counts"][
            "ready_source_evidence_count"
        ]
        == 15
    )

    _print_human(payload)
    output = capsys.readouterr().out
    assert "acceptance_certificate=14/14" in output
    assert "acceptance_receipts=2/2" in output
    assert "retained_gap_receipts=6/6" in output
    assert "residual_ratio_receipts=10/10" in output
    assert "count_delivery_alignment=4/4" in output
    assert "maturity_l5_alignment=6/6" in output
    assert "boundary_scope_alignment=6/6" in output
    assert "requirement_dimensions=10/10" in output
    assert "acceptance_evidence=15/15" in output
    assert "release_export_scripts=15/15 ready" in output
