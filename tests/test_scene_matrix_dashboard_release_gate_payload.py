import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    _print_human,
    build_scene_matrix_release_gate_payload,
)
from tests._scene_matrix_dashboard_assertions import (  # noqa: E402
    assert_expected_count_values,
)


@pytest.fixture(scope="module")
def release_gate_payload(tmp_path_factory):
    return build_scene_matrix_release_gate_payload(
        tmp_path_factory.mktemp("scene_matrix_dashboard_release_gate")
    )


EXPECTED_RELEASE_GATE_PAYLOAD_COUNTS: dict[str, int] = {
    "scene_matrix_dashboard_pack_count": 12,
    "high_frequency_completeness_ready_pack_count": 12,
    "scene_matrix_dashboard_visible_count": 12,
    "scene_matrix_dashboard_issue_count": 0,
    "scene_matrix_dashboard_warning_count": 3,
    "scene_matrix_dashboard_lens_count": 9,
    "scene_matrix_dashboard_source_count": 43,
    "scene_input_source_family_count": 15,
    "scene_input_source_ready_family_count": 14,
    "scene_input_source_ready_input_pack_count": 12,
    "scene_input_source_input_pack_count": 12,
    "scene_input_source_warning_count": 5,
    "scene_object_preflight_action_target_count": 11,
    "scene_object_preflight_action_warning_count": 0,
    "scene_ambiguity_clarification_count": 6,
    "scene_ambiguity_clarification_ready_count": 6,
    "scene_ambiguity_clarification_issue_count": 0,
    "scene_user_journey_pack_count": 12,
    "scene_user_journey_ready_pack_count": 12,
    "scene_user_journey_path_count": 100,
    "scene_user_journey_warning_count": 0,
    "scene_business_capability_matrix_count": 18,
    "scene_business_capability_matrix_ready_count": 18,
    "scene_business_capability_matrix_boundary_count": 7,
    "scene_business_capability_matrix_manual_gate_count": 10,
    "scene_business_capability_matrix_issue_count": 0,
    "scene_business_capability_matrix_warning_count": 0,
    "scene_boundary_capability_count": 6,
    "scene_boundary_capability_ready_count": 6,
    "scene_boundary_capability_professional_count": 5,
    "scene_boundary_capability_import_ai_count": 1,
    "scene_boundary_capability_risk_domain_count": 9,
    "scene_boundary_capability_external_receipt_count": 8,
    "scene_boundary_capability_release_guardrail_count": 4,
    "scene_boundary_capability_issue_count": 0,
    "scene_boundary_guarded_completion_subject_count": 6,
    "scene_boundary_guarded_completion_ready_count": 6,
    "scene_boundary_guarded_completion_retained_gap_count": 6,
    "scene_boundary_guarded_completion_issue_count": 0,
    "scene_residual_warning_governance_warning_count": 10,
    "scene_residual_warning_governance_managed_count": 10,
    "scene_boundary_readiness_reconciliation_count": 15,
    "scene_terminal_release_exception_count": 5,
    "scene_terminal_release_exception_governed_count": 5,
    "scene_terminal_release_exception_ungoverned_count": 0,
    "scene_terminal_release_exception_trace_count": 36,
    "scene_boundary_subject_release_dossier_subject_count": 6,
    "scene_boundary_subject_release_dossier_ready_count": 6,
    "scene_non_subject_release_trace_attribution_count": 10,
    "scene_release_trace_partition_guard_partition_count": 3,
    "scene_release_trace_partition_guard_ready_count": 3,
    "scene_release_projection_surface_parity_count": 13,
    "scene_release_closure_ledger_stage_count": 13,
    "scene_release_closure_ledger_ready_count": 13,
    "scene_release_closure_ledger_stage_order_count": 13,
    "scene_release_closure_ledger_dashboard_card_count": 13,
    "scene_release_closure_ledger_drilldown_item_count": 13,
    "scene_release_closure_ledger_issue_count": 0,
    "scene_retained_gap_exit_criteria_count": 6,
    "scene_retained_gap_external_receipt_target_count": 8,
    "scene_retained_gap_exit_criteria_issue_count": 0,
    "scene_release_residual_ratio_ledger_count": 3,
    "scene_release_residual_ratio_ledger_issue_count": 0,
    "scene_release_residual_explanation_count": 14,
    "scene_release_residual_explanation_issue_count": 0,
    "scene_release_acceptance_certificate_count": 14,
    "scene_release_acceptance_certificate_ready_count": 14,
    "scene_release_acceptance_certificate_receipt_count": 2,
    "scene_release_acceptance_certificate_issue_count": 0,
    "scene_control_runtime_control_count": 12,
    "scene_control_runtime_ready_control_count": 12,
    "scene_control_runtime_contract_link_count": 16,
    "scene_control_runtime_issue_count": 0,
    "scene_delivery_execution_channel_count": 10,
    "scene_delivery_execution_ready_channel_count": 10,
    "scene_delivery_execution_issue_count": 0,
    "scene_material_repair_flow_count": 11,
    "scene_material_repair_flow_ready_count": 11,
    "scene_material_repair_flow_issue_count": 0,
    "scene_fixed_layout_profile_channel_count": 12,
    "scene_fixed_layout_profile_ready_channel_count": 12,
    "scene_fixed_layout_profile_issue_count": 0,
    "scene_report_artifact_drilldown_channel_count": 10,
    "scene_report_artifact_drilldown_issue_count": 0,
    "scene_count_profile_profile_count": 20,
    "scene_count_profile_accounted_family_count": 15,
    "scene_delivery_preset_accounted_family_count": 15,
    "static_closed_but_not_green_count": 2,
    "static_closed_not_green_governed_count": 2,
    "dashboard_warning_projection_governed_count": 3,
    "input_source_warning_managed_count": 5,
    "count_profile_warning_managed_count": 2,
    "plugin_manual_warning_managed_count": 5,
    "reference_profile_warning_managed_count": 2,
    "visio_fixture_closed_verified_count": 1,
    "retained_gap_enveloped_count": 6,
    "gap_domain_classified_count": 3,
}

EXPECTED_SCENE_MATRIX_DASHBOARD_PAYLOAD_COUNTS: dict[str, int] = {
    "request_cell_count": 53,
    "import_handoff_count": 1,
}


def _assert_scene_matrix_dashboard_release_gate_payload(payload):
    assert payload["status"] == "passed"
    assert_expected_count_values(
        payload["counts"],
        EXPECTED_RELEASE_GATE_PAYLOAD_COUNTS,
    )
    assert_expected_count_values(
        payload["scene_matrix_dashboard"]["counts"],
        EXPECTED_SCENE_MATRIX_DASHBOARD_PAYLOAD_COUNTS,
    )
    drilldown_payload = payload["scene_matrix_drilldown"]
    assert drilldown_payload["status"] == "passed"
    assert len(drilldown_payload["items"]) == 37
    assert len(drilldown_payload["source_evidence"]) == 107
    assert payload["checks"]["scene_matrix_drilldown"]["status"] == "passed"
    assert payload["checks"]["scene_matrix_dashboard"]["status"] == "passed"
    assert payload["checks"]["scene_input_source_audit"]["status"] == "passed"
    assert payload["checks"]["scene_material_repair_flow_audit"]["status"] == "passed"
    assert payload["checks"]["scene_fixed_layout_profile_audit"]["status"] == (
        "passed"
    )
    assert (
        payload["checks"]["scene_report_artifact_drilldown_audit"]["status"]
        == "passed"
    )
    assert (
        payload["checks"]["scene_object_preflight_action_audit"]["status"]
        == "passed"
    )
    assert (
        payload["counts"]["scene_object_preflight_action_ready_target_count"]
        == 11
    )
    assert (
        payload["counts"]["scene_business_capability_matrix_high_priority_count"]
        == 11
    )
    assert (
        payload["counts"][
            "scene_business_capability_matrix_high_priority_ready_count"
        ]
        == 11
    )
    assert (
        payload["counts"][
            "scene_business_capability_matrix_missing_journey_group_count"
        ]
        == 0
    )
    assert (
        payload["counts"][
            "scene_business_capability_matrix_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["checks"]["scene_boundary_capability_matrix"]["status"] == "passed"
    assert (
        payload["counts"]["scene_boundary_capability_decision_requirement_count"]
        == 4
    )
    assert payload["checks"]["scene_boundary_guarded_completion_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"][
            "scene_boundary_guarded_completion_external_contract_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_guarded_completion_boundary_capability_count"
        ]
        == 6
    )
    assert payload["checks"]["scene_residual_warning_governance_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"][
            "scene_residual_warning_governance_input_source_warning_count"
        ]
        == 5
    )
    assert (
        payload["counts"][
            "scene_residual_warning_governance_count_profile_warning_count"
        ]
        == 2
    )
    assert (
        payload["counts"][
            "scene_residual_warning_governance_dashboard_projection_warning_count"
        ]
        == 3
    )
    assert (
        payload["counts"][
            "scene_residual_warning_governance_object_preflight_warning_count"
        ]
        == 0
    )
    assert (
        payload["counts"][
            "scene_residual_warning_governance_unmanaged_warning_count"
        ]
        == 0
    )
    assert (
        payload["checks"]["scene_boundary_readiness_reconciliation_audit"][
            "status"
        ]
        == "passed"
    )
    assert (
        payload["counts"][
            "scene_boundary_readiness_reconciliation_reconciled_count"
        ]
        == 15
    )
    assert (
        payload["counts"][
            "scene_boundary_readiness_reconciliation_unreconciled_count"
        ]
        == 0
    )
    assert (
        payload["counts"][
            "scene_boundary_readiness_reconciliation_not_applicable_count"
        ]
        == 2
    )
    assert payload["checks"]["scene_terminal_release_exception_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"]["scene_terminal_release_exception_managed_warning_count"]
        == 10
    )
    assert (
        payload["counts"][
            "scene_terminal_release_exception_unique_source_trace_count"
        ]
        == 31
    )
    assert payload["checks"]["scene_boundary_subject_release_dossier_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"]["scene_boundary_subject_release_dossier_subject_trace_count"]
        == 26
    )
    assert (
        payload["counts"][
            "scene_boundary_subject_release_dossier_unique_source_trace_count"
        ]
        == 24
    )
    assert payload["checks"]["scene_non_subject_release_trace_attribution_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"]["scene_non_subject_release_trace_attribution_ready_count"]
        == 10
    )
    assert (
        payload["counts"][
            "scene_non_subject_release_trace_attribution_unattributed_count"
        ]
        == 0
    )
    assert payload["checks"]["scene_release_trace_partition_guard_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"]["scene_release_trace_partition_guard_terminal_trace_count"]
        == 36
    )
    assert (
        payload["counts"]["scene_release_trace_partition_guard_partitioned_trace_count"]
        == 36
    )
    assert (
        payload["counts"]["scene_release_trace_partition_guard_missing_trace_count"]
        == 0
    )
    assert (
        payload["counts"]["scene_release_trace_partition_guard_overlap_trace_count"]
        == 0
    )
    assert payload["checks"]["scene_release_projection_surface_parity_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"]["scene_release_projection_surface_parity_ready_count"]
        == 13
    )
    assert (
        payload["counts"][
            "scene_release_projection_surface_parity_release_gate_check_count"
        ]
        == 13
    )
    assert (
        payload["counts"][
            "scene_release_projection_surface_parity_dashboard_card_count"
        ]
        == 13
    )
    assert (
        payload["counts"][
            "scene_release_projection_surface_parity_drilldown_item_count"
        ]
        == 13
    )
    assert (
        payload["counts"]["scene_release_projection_surface_parity_issue_count"]
        == 0
    )
    assert payload["checks"]["scene_boundary_subject_release_continuity_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"]["scene_boundary_subject_release_continuity_subject_count"]
        == 6
    )
    assert (
        payload["counts"]["scene_boundary_subject_release_continuity_ready_count"]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_subject_release_continuity_terminal_release_subject_count"
        ]
        == 6
    )
    assert (
        payload["counts"]["scene_boundary_subject_release_continuity_mismatch_count"]
        == 0
    )
    assert payload["checks"]["scene_release_closure_ledger_audit"]["status"] == (
        "passed"
    )
    assert (
        payload["counts"]["scene_release_closure_ledger_upstream_dependency_count"]
        == 18
    )
    assert (
        payload["counts"][
            "scene_release_closure_ledger_upstream_dependency_ready_count"
        ]
        == 18
    )
    assert (
        payload["counts"]["scene_release_closure_ledger_release_gate_check_count"]
        == 13
    )
    assert (
        payload["counts"]["scene_release_closure_ledger_summary_projection_count"]
        == 13
    )
    assert (
        payload["counts"]["scene_boundary_maturity_release_envelope_count"] == 6
    )
    assert (
        payload["counts"]["scene_boundary_maturity_release_envelope_ready_count"]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_maturity_release_envelope_l5_blocker_enveloped_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_boundary_maturity_release_envelope_subject_continuity_count"
        ]
        == 6
    )
    assert (
        payload["counts"]["scene_boundary_maturity_release_envelope_issue_count"]
        == 0
    )
    assert payload["checks"]["scene_retained_gap_exit_criteria_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"][
            "scene_retained_gap_exit_criteria_release_allowed_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_retained_gap_exit_criteria_boundary_capability_link_count"
        ]
        == 6
    )
    assert (
        payload["counts"]["scene_retained_gap_external_receipt_alignment_count"]
        == 6
    )
    assert payload["checks"]["scene_release_residual_ratio_ledger_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"]["scene_release_residual_ratio_ledger_published_count"]
        == 3
    )
    assert (
        payload["counts"]["scene_release_residual_ratio_ledger_release_envelope_link_count"]
        == 10
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_exit_criteria_link_count"
        ]
        == 10
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
            "scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count"
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
    assert payload["checks"]["scene_release_residual_explanation_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"]["scene_release_residual_explanation_covered_count"]
        == 14
    )
    assert (
        payload["counts"]["scene_release_residual_explanation_mismatch_count"]
        == 0
    )
    assert (
        payload["counts"][
            "scene_release_residual_explanation_missing_summary_marker_count"
        ]
        == 0
    )
    assert payload["checks"]["scene_release_acceptance_certificate_audit"][
        "status"
    ] == "passed"
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_ready_receipt_count"
        ]
        == 2
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_source_evidence_count"
        ]
        == 15
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
            "scene_release_acceptance_certificate_ready_source_evidence_count"
        ]
        == 15
    )
    assert (
        payload["counts"]["scene_material_repair_flow_missing_source_evidence_count"]
        == 0
    )
    assert (
        payload["counts"]["scene_fixed_layout_profile_missing_source_evidence_count"]
        == 0
    )
    assert (
        payload["counts"]["scene_report_artifact_drilldown_ready_channel_count"]
        == 10
    )
    assert (
        payload["counts"][
            "scene_report_artifact_drilldown_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_matrix_dashboard"]["status"] == "passed"
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "external_handoff_contract_ready_count"
        ]
        == 6
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "boundary_guarded_completion_ready_count"
        ]
        == 6
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "family_fixture_depth_p1_ready_count"
        ]
        == 11
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "input_source_ready_input_pack_count"
        ]
        == 12
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "material_schema_ready_material_family_count"
        ]
        == 15
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "material_repair_flow_ready_count"
        ]
        == 11
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "fixed_layout_profile_ready_channel_count"
        ]
        == 12
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "report_artifact_drilldown_ready_channel_count"
        ]
        == 10
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "delivery_preset_ready_family_count"
        ]
        == 14
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "delivery_preset_accounted_family_count"
        ]
        == 15
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "delivery_preset_accounted_delivery_pack_count"
        ]
        == 12
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "delivery_execution_ready_channel_count"
        ]
        == 10
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "formula_output_watermark_ready_capability_count"
        ]
        == 3
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "formula_output_watermark_accounted_family_count"
        ]
        == 15
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"]["count_profile_ready_family_count"]
        == 14
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "count_profile_accounted_family_count"
        ]
        == 15
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "control_runtime_ready_control_count"
        ]
        == 12
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
                "business_capability_matrix_ready_count"
            ]
            == 18
        )
    assert (
        payload["counts"]["scene_delivery_preset_accounted_delivery_pack_count"]
        == 12
    )
    assert (
        payload["counts"][
            "scene_formula_output_watermark_accounted_family_count"
        ]
        == 15
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "maturity_upgrade_l5_blocked_subject_count"
        ]
        == 6
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "boundary_maturity_release_envelope_l5_blocker_enveloped_count"
        ]
        == 6
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"]["retained_gap_enveloped_count"]
        == 6
    )
    assert (
        payload["counts"]["static_closed_not_green_governed_count"]
        == payload["counts"]["static_closed_but_not_green_count"]
    )
    assert (
        payload["counts"][
            "scene_terminal_release_exception_static_closed_boundary_count"
        ]
        == 2
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "static_closed_not_green_governed_count"
        ]
        == 2
    )
    assert (
        payload["counts"]["dashboard_warning_projection_governed_count"]
        == payload["counts"]["scene_matrix_dashboard_warning_count"]
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "dashboard_warning_projection_governed_count"
        ]
        == 3
    )
    assert (
        payload["counts"]["input_source_warning_managed_count"]
        == payload["counts"]["scene_input_source_warning_count"]
    )
    assert (
        payload["counts"]["count_profile_warning_managed_count"]
        == payload["counts"]["scene_count_profile_warning_count"]
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "residual_warning_governance_input_source_managed_warning_count"
        ]
        == 5
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "residual_warning_governance_count_profile_managed_warning_count"
        ]
        == 2
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "residual_warning_governance_plugin_manual_managed_warning_count"
        ]
        == 5
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "residual_warning_governance_reference_profile_managed_warning_count"
        ]
        == 2
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "residual_warning_governance_visio_fixture_verified_count"
        ]
        == 1
    )
    assert (
        payload["counts"]["scene_product_maturity_upgrade_gap_count"]
        == 6
    )
    assert (
        payload["counts"]["retained_gap_enveloped_count"]
        == payload["counts"]["scene_product_maturity_upgrade_gap_count"]
    )
    assert (
        payload["counts"]["gap_domain_classified_count"]
        == payload["counts"]["scene_product_maturity_upgrade_gap_domain_count"]
    )
    assert (
        payload["scene_matrix_dashboard"]["counts"][
            "maturity_upgrade_gap_domain_classified_count"
        ]
        == 3
    )



def _assert_scene_matrix_dashboard_release_gate_human_output(payload, capsys):
    _print_human(payload)
    output = capsys.readouterr().out
    assert "[OK]" in output
    assert "high_frequency_coverage=12/12" in output
    assert "static_closed_not_green=2/2 governed" in output
    assert "dashboard_warning_projection=3/3 governed" in output
    assert "input_warnings=5/5 managed" in output
    assert "count_profile_warnings=2/2 managed" in output
    assert "plugin_manual_warnings=5/5 managed" in output
    assert "reference_profile_warnings=2/2 managed" in output
    assert "visio_fixture=1/1 closed" in output
    assert "retained_gaps=6/6 enveloped" in output
    assert "retained_gap_exit_criteria=6/6 release-allowed" in output
    assert "retained_gap_receipts=6/6 aligned" in output
    assert "gap_domains=3/3 classified" in output
    assert "residual_ratio_exit_criteria=10/10" in output
    assert "residual_ratio_receipts=10/10" in output
    assert "count_delivery_receipts=4/4" in output
    assert "maturity_l5_receipts=6/6" in output
    assert "boundary_scope_alignment=6/6" in output
    assert "residual_explanations=14/14 covered" in output
    assert "acceptance_receipts=2/2" in output
    assert "drilldown_rows=556/556" in output
    assert "drilldown_sources=107/107 ready" in output

    failed_payload = dict(payload)
    failed_payload["status"] = "failed"
    _print_human(failed_payload)
    failed_output = capsys.readouterr().out
    assert "[FAILED]" in failed_output
    assert "[OK]" not in failed_output


def run_scene_matrix_dashboard_release_gate_payload_coverage(tmp_path, capsys):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    _assert_scene_matrix_dashboard_release_gate_payload(payload)
    _assert_scene_matrix_dashboard_release_gate_human_output(payload, capsys)


def test_scene_matrix_dashboard_release_gate_payload(release_gate_payload):
    _assert_scene_matrix_dashboard_release_gate_payload(release_gate_payload)


def test_scene_matrix_dashboard_release_gate_human_output(
    release_gate_payload,
    capsys,
):
    _assert_scene_matrix_dashboard_release_gate_human_output(
        release_gate_payload,
        capsys,
    )
