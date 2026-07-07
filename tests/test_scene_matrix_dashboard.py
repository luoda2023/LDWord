import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    _print_human,
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_matrix_dashboard import (  # noqa: E402
    SCENE_MATRIX_DASHBOARD_LENS_IDS,
    SCENE_MATRIX_DASHBOARD_SOURCE_IDS,
    audit_scene_matrix_dashboard,
    build_scene_matrix_dashboard,
)
from src.ui.panels.scene_summary_projection import (  # noqa: E402
    build_scene_matrix_dashboard_summary_items,
)


def test_scene_matrix_dashboard_aggregates_global_closure_lenses():
    report = build_scene_matrix_dashboard()
    payload = report.to_payload()
    rows = {row.pack_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.pack_count == 12
    assert report.visible_count == 12
    assert report.issue_count == 0
    assert report.warning_count == 3
    assert audit_scene_matrix_dashboard(report) == ()
    assert tuple(payload["source_ids"]) == SCENE_MATRIX_DASHBOARD_SOURCE_IDS
    assert tuple(lens["lens_id"] for lens in payload["lenses"]) == (
        SCENE_MATRIX_DASHBOARD_LENS_IDS
    )
    assert payload["counts"]["request_cell_count"] == 53
    assert payload["counts"]["request_cell_pack_link_count"] == 57
    assert payload["counts"]["high_frequency_completeness_ready_pack_count"] == 12
    assert payload["counts"]["task_lexicon_task_count"] == 29
    assert payload["counts"]["task_lexicon_phrase_count"] == 31
    assert payload["counts"]["task_lexicon_negative_task_count"] == 1
    assert payload["counts"]["task_lexicon_issue_count"] == 0
    assert payload["counts"]["ambiguous_boundary_count"] == 6
    assert payload["counts"]["ambiguous_boundary_pack_pair_count"] == 6
    assert payload["counts"]["ambiguous_boundary_issue_count"] == 0
    assert payload["counts"]["ambiguity_clarification_count"] == 6
    assert payload["counts"]["ambiguity_clarification_ready_count"] == 6
    assert payload["counts"]["ambiguity_clarification_candidate_route_count"] == 10
    assert payload["counts"]["ambiguity_clarification_candidate_pack_count"] == 7
    assert payload["counts"]["ambiguity_clarification_fixture_backed_count"] == 6
    assert payload["counts"]["ambiguity_clarification_issue_count"] == 0
    assert payload["counts"]["ambiguity_clarification_warning_count"] == 0
    assert (
        payload["counts"]["ambiguity_clarification_missing_source_evidence_count"]
        == 0
    )
    assert payload["counts"]["import_handoff_count"] == 1
    assert payload["counts"]["import_handoff_ready_count"] == 1
    assert payload["counts"]["import_handoff_issue_count"] == 0
    assert payload["counts"]["input_source_family_count"] == 15
    assert payload["counts"]["input_source_ready_family_count"] == 14
    assert payload["counts"]["input_source_boundary_family_count"] == 1
    assert payload["counts"]["input_source_input_pack_count"] == 12
    assert payload["counts"]["input_source_ready_input_pack_count"] == 12
    assert payload["counts"]["input_source_accepted_format_count"] == 6
    assert payload["counts"]["input_source_structured_format_count"] == 4
    assert payload["counts"]["input_source_boundary_input_source_count"] == 4
    assert payload["counts"]["input_source_render_source_count"] == 8
    assert payload["counts"]["input_source_issue_count"] == 0
    assert payload["counts"]["input_source_warning_count"] == 5
    assert payload["counts"]["input_source_missing_source_evidence_count"] == 0
    assert payload["counts"]["family_count"] == 15
    assert payload["counts"]["family_fixture_depth_family_count"] == 15
    assert payload["counts"]["family_fixture_depth_p1_family_count"] == 11
    assert payload["counts"]["family_fixture_depth_p1_ready_count"] == 11
    assert payload["counts"]["family_fixture_depth_issue_count"] == 0
    assert payload["counts"]["sample_fixture_count"] == 42
    assert payload["counts"]["control_contract_count"] == 13
    assert payload["counts"]["control_runtime_control_count"] == 12
    assert payload["counts"]["control_runtime_ready_control_count"] == 12
    assert payload["counts"]["control_runtime_contract_link_count"] == 16
    assert payload["counts"]["control_runtime_shared_component_count"] >= 15
    assert payload["counts"]["control_runtime_issue_count"] == 0
    assert payload["counts"]["control_runtime_missing_source_evidence_count"] == 0
    assert payload["counts"]["word_risk_surface_count"] == 15
    assert payload["counts"]["object_preflight_action_target_count"] == 11
    assert payload["counts"]["object_preflight_action_ready_target_count"] == 11
    assert payload["counts"]["object_preflight_action_warning_target_count"] == 0
    assert payload["counts"]["object_preflight_action_high_risk_target_count"] == 5
    assert payload["counts"]["object_preflight_action_fixture_backed_target_count"] == 11
    assert payload["counts"]["object_preflight_action_blockable_target_count"] == 3
    assert payload["counts"]["object_preflight_action_skippable_target_count"] == 11
    assert (
        payload["counts"]["object_preflight_action_manual_confirmation_target_count"]
        == 10
    )
    assert payload["counts"]["object_preflight_action_family_count"] == 15
    assert payload["counts"]["object_preflight_action_ready_family_count"] == 14
    assert payload["counts"]["object_preflight_action_boundary_family_count"] == 1
    assert payload["counts"]["object_preflight_action_strict_family_count"] == 2
    assert payload["counts"]["object_preflight_action_family_with_fixture_count"] == 15
    assert payload["counts"]["object_preflight_action_issue_count"] == 0
    assert payload["counts"]["object_preflight_action_warning_count"] == 0
    assert (
        payload["counts"]["object_preflight_action_missing_source_evidence_count"]
        == 0
    )
    assert payload["counts"]["user_journey_pack_count"] == 12
    assert payload["counts"]["user_journey_ready_pack_count"] == 12
    assert payload["counts"]["user_journey_warning_pack_count"] == 0
    assert payload["counts"]["user_journey_family_count"] == 15
    assert payload["counts"]["user_journey_ready_family_count"] == 15
    assert payload["counts"]["user_journey_warning_family_count"] == 0
    assert payload["counts"]["user_journey_path_count"] == 100
    assert payload["counts"]["user_journey_success_path_count"] == 31
    assert payload["counts"]["user_journey_degraded_path_count"] == 29
    assert payload["counts"]["user_journey_failure_path_count"] == 4
    assert payload["counts"]["user_journey_manual_boundary_path_count"] == 25
    assert payload["counts"]["user_journey_ambiguous_decision_path_count"] == 7
    assert payload["counts"]["user_journey_handoff_path_count"] == 1
    assert payload["counts"]["user_journey_negative_control_path_count"] == 3
    assert payload["counts"]["user_journey_issue_count"] == 0
    assert payload["counts"]["user_journey_warning_count"] == 0
    assert payload["counts"]["user_journey_missing_source_evidence_count"] == 0
    assert payload["counts"]["business_capability_matrix_count"] == 18
    assert payload["counts"]["business_capability_matrix_ready_count"] == 18
    assert payload["counts"]["business_capability_matrix_high_priority_count"] == 11
    assert (
        payload["counts"]["business_capability_matrix_high_priority_ready_count"]
        == 11
    )
    assert payload["counts"]["business_capability_matrix_boundary_count"] == 7
    assert payload["counts"]["business_capability_matrix_manual_gate_count"] == 10
    assert (
        payload["counts"]["business_capability_matrix_missing_journey_group_count"]
        == 0
    )
    assert payload["counts"]["business_capability_matrix_issue_count"] == 0
    assert payload["counts"]["business_capability_matrix_warning_count"] == 0
    assert (
        payload["counts"]["business_capability_matrix_missing_source_evidence_count"]
        == 0
    )
    assert payload["counts"]["boundary_capability_count"] == 6
    assert payload["counts"]["boundary_capability_ready_count"] == 6
    assert payload["counts"]["boundary_capability_professional_count"] == 5
    assert payload["counts"]["boundary_capability_import_ai_count"] == 1
    assert payload["counts"]["boundary_capability_fixture_count"] == 9
    assert payload["counts"]["boundary_capability_report_expectation_count"] == 19
    assert payload["counts"]["boundary_capability_ui_surface_count"] == 7
    assert payload["counts"]["boundary_capability_risk_domain_count"] == 9
    assert payload["counts"]["boundary_capability_decision_requirement_count"] == 4
    assert payload["counts"]["boundary_capability_external_receipt_count"] == 8
    assert payload["counts"]["boundary_capability_release_guardrail_count"] == 4
    assert payload["counts"]["boundary_capability_issue_count"] == 0
    assert payload["counts"]["boundary_capability_missing_source_evidence_count"] == 0
    assert payload["counts"]["plugin_boundary_gate_count"] == 4
    assert payload["counts"]["plugin_boundary_risk_domain_count"] == 14
    assert payload["counts"]["plugin_boundary_issue_count"] == 0
    assert payload["counts"]["external_handoff_contract_count"] == 6
    assert payload["counts"]["external_handoff_contract_ready_count"] == 6
    assert payload["counts"]["external_handoff_contract_pack_count"] == 2
    assert payload["counts"]["external_handoff_contract_family_count"] == 4
    assert payload["counts"]["external_handoff_contract_plugin_gate_count"] == 2
    assert payload["counts"]["external_handoff_contract_target_plugin_count"] == 6
    assert payload["counts"]["external_handoff_contract_risk_domain_count"] == 9
    assert payload["counts"]["external_handoff_contract_report_count"] == 19
    assert payload["counts"]["external_handoff_contract_ui_surface_count"] == 14
    assert payload["counts"]["external_handoff_contract_fixture_count"] == 8
    assert payload["counts"]["external_handoff_contract_status_state_count"] == 8
    assert payload["counts"]["external_handoff_contract_failure_policy_count"] == 4
    assert payload["counts"]["external_handoff_contract_issue_count"] == 0
    assert (
        payload["counts"]["external_handoff_contract_missing_source_evidence_count"]
        == 0
    )
    assert payload["counts"]["boundary_guarded_completion_subject_count"] == 6
    assert payload["counts"]["boundary_guarded_completion_ready_count"] == 6
    assert payload["counts"]["boundary_guarded_completion_pack_count"] == 2
    assert payload["counts"]["boundary_guarded_completion_family_count"] == 4
    assert payload["counts"]["boundary_guarded_completion_retained_gap_count"] == 6
    assert (
        payload["counts"]["boundary_guarded_completion_external_contract_count"]
        == 6
    )
    assert (
        payload["counts"]["boundary_guarded_completion_boundary_capability_count"]
        == 6
    )
    assert payload["counts"]["boundary_guarded_completion_plugin_gate_count"] == 2
    assert payload["counts"]["boundary_guarded_completion_target_plugin_count"] == 6
    assert payload["counts"]["boundary_guarded_completion_risk_domain_count"] == 11
    assert (
        payload["counts"]["boundary_guarded_completion_excluded_core_claim_count"]
        == 14
    )
    assert payload["counts"]["boundary_guarded_completion_issue_count"] == 0
    assert (
        payload["counts"][
            "boundary_guarded_completion_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["counts"]["residual_warning_governance_warning_count"] == 10
    assert payload["counts"]["residual_warning_governance_managed_count"] == 10
    assert (
        payload["counts"]["residual_warning_governance_input_source_warning_count"]
        == 5
    )
    assert (
        payload["counts"][
            "residual_warning_governance_input_source_managed_warning_count"
        ]
        == 5
    )
    assert (
        payload["counts"]["residual_warning_governance_count_profile_warning_count"]
        == 2
    )
    assert (
        payload["counts"][
            "residual_warning_governance_count_profile_managed_warning_count"
        ]
        == 2
    )
    assert (
        payload["counts"][
            "residual_warning_governance_dashboard_projection_warning_count"
        ]
        == 3
    )
    assert payload["counts"]["residual_warning_governance_plugin_manual_warning_count"] == 5
    assert (
        payload["counts"][
            "residual_warning_governance_plugin_manual_managed_warning_count"
        ]
        == 5
    )
    assert (
        payload["counts"][
            "residual_warning_governance_reference_profile_warning_count"
        ]
        == 2
    )
    assert (
        payload["counts"][
            "residual_warning_governance_reference_profile_managed_warning_count"
        ]
        == 2
    )
    assert payload["counts"]["residual_warning_governance_visio_fixture_closed_count"] == 1
    assert (
        payload["counts"]["residual_warning_governance_visio_fixture_verified_count"]
        == 1
    )
    assert payload["counts"]["dashboard_warning_projection_governed_count"] == 3
    assert (
        payload["counts"][
            "residual_warning_governance_object_preflight_warning_count"
        ]
        == 0
    )
    assert payload["counts"]["residual_warning_governance_unmanaged_warning_count"] == 0
    assert payload["counts"]["residual_warning_governance_issue_count"] == 0
    assert payload["counts"]["boundary_readiness_reconciliation_count"] == 15
    assert payload["counts"]["boundary_readiness_reconciliation_reconciled_count"] == 15
    assert (
        payload["counts"]["boundary_readiness_reconciliation_unreconciled_count"]
        == 0
    )
    assert (
        payload["counts"]["boundary_readiness_reconciliation_readiness_delta_count"]
        == 5
    )
    assert payload["counts"]["boundary_readiness_reconciliation_not_applicable_count"] == 2
    assert (
        payload["counts"][
            "boundary_readiness_reconciliation_static_closed_boundary_count"
        ]
        == 2
    )
    assert (
        payload["counts"][
            "boundary_readiness_reconciliation_maturity_boundary_guarded_count"
        ]
        == 6
    )
    assert payload["counts"]["boundary_readiness_reconciliation_issue_count"] == 0
    assert payload["counts"]["terminal_release_exception_count"] == 5
    assert payload["counts"]["terminal_release_exception_governed_count"] == 5
    assert payload["counts"]["terminal_release_exception_ungoverned_count"] == 0
    assert payload["counts"]["terminal_release_exception_managed_warning_count"] == 10
    assert (
        payload["counts"]["terminal_release_exception_warning_projection_count"]
        == 3
    )
    assert (
        payload["counts"][
            "terminal_release_exception_readiness_reconciliation_count"
        ]
        == 15
    )
    assert (
        payload["counts"][
            "terminal_release_exception_boundary_guarded_maturity_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "terminal_release_exception_static_closed_boundary_count"
        ]
        == 2
    )
    assert payload["counts"]["terminal_release_exception_trace_count"] == 36
    assert (
        payload["counts"][
            "terminal_release_exception_unique_source_trace_count"
        ]
        == 31
    )
    assert (
        payload["counts"][
            "terminal_release_exception_linked_boundary_subject_count"
        ]
        == 6
    )
    assert payload["counts"]["terminal_release_exception_issue_count"] == 0
    assert payload["counts"]["boundary_subject_release_dossier_subject_count"] == 6
    assert payload["counts"]["boundary_subject_release_dossier_ready_count"] == 6
    assert (
        payload["counts"]["boundary_subject_release_dossier_subject_trace_count"]
        == 26
    )
    assert (
        payload["counts"][
            "boundary_subject_release_dossier_unique_source_trace_count"
        ]
        == 24
    )
    assert (
        payload["counts"][
            "boundary_subject_release_dossier_readiness_reconciliation_row_count"
        ]
        == 14
    )
    assert payload["counts"]["boundary_subject_release_dossier_issue_count"] == 0
    assert payload["counts"]["non_subject_release_trace_attribution_count"] == 10
    assert payload["counts"]["non_subject_release_trace_attribution_ready_count"] == 10
    assert (
        payload["counts"][
            "non_subject_release_trace_attribution_unattributed_count"
        ]
        == 0
    )
    assert (
        payload["counts"][
            "non_subject_release_trace_attribution_dashboard_projection_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "non_subject_release_trace_attribution_registry_only_profile_count"
        ]
        == 2
    )
    assert payload["counts"]["release_trace_partition_guard_partition_count"] == 3
    assert payload["counts"]["release_trace_partition_guard_ready_count"] == 3
    assert payload["counts"]["release_trace_partition_guard_terminal_trace_count"] == 36
    assert payload["counts"]["release_trace_partition_guard_subject_trace_count"] == 26
    assert (
        payload["counts"]["release_trace_partition_guard_non_subject_trace_count"]
        == 10
    )
    assert (
        payload["counts"]["release_trace_partition_guard_partitioned_trace_count"]
        == 36
    )
    assert payload["counts"]["release_trace_partition_guard_missing_trace_count"] == 0
    assert payload["counts"]["release_trace_partition_guard_overlap_trace_count"] == 0
    assert payload["counts"]["release_trace_partition_guard_extra_trace_count"] == 0
    assert payload["counts"]["release_trace_partition_guard_issue_count"] == 0
    assert payload["counts"]["release_projection_surface_parity_count"] == 13
    assert payload["counts"]["release_projection_surface_parity_ready_count"] == 13
    assert (
        payload["counts"][
            "release_projection_surface_parity_release_gate_check_count"
        ]
        == 13
    )
    assert payload["counts"]["release_projection_surface_parity_dashboard_card_count"] == 13
    assert payload["counts"]["release_projection_surface_parity_drilldown_item_count"] == 13
    assert (
        payload["counts"]["release_projection_surface_parity_summary_projection_count"]
        == 13
    )
    assert payload["counts"]["release_projection_surface_parity_issue_count"] == 0
    assert payload["counts"]["boundary_subject_release_continuity_subject_count"] == 6
    assert payload["counts"]["boundary_subject_release_continuity_ready_count"] == 6
    assert (
        payload["counts"][
            "boundary_subject_release_continuity_maturity_subject_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "boundary_subject_release_continuity_guarded_completion_subject_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "boundary_subject_release_continuity_terminal_release_subject_count"
        ]
        == 6
    )
    assert payload["counts"]["boundary_subject_release_continuity_mismatch_count"] == 0
    assert payload["counts"]["release_closure_ledger_stage_count"] == 13
    assert payload["counts"]["release_closure_ledger_ready_count"] == 13
    assert payload["counts"]["release_closure_ledger_stage_order_count"] == 13
    assert payload["counts"]["release_closure_ledger_upstream_dependency_count"] == 18
    assert (
        payload["counts"]["release_closure_ledger_upstream_dependency_ready_count"]
        == 18
    )
    assert payload["counts"]["release_closure_ledger_release_gate_check_count"] == 13
    assert payload["counts"]["release_closure_ledger_dashboard_card_count"] == 13
    assert payload["counts"]["release_closure_ledger_drilldown_item_count"] == 13
    assert payload["counts"]["release_closure_ledger_summary_projection_count"] == 13
    assert payload["counts"]["release_closure_ledger_issue_count"] == 0
    assert payload["counts"]["boundary_maturity_release_envelope_count"] == 6
    assert payload["counts"]["boundary_maturity_release_envelope_ready_count"] == 6
    assert (
        payload["counts"][
            "boundary_maturity_release_envelope_l5_blocker_enveloped_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "boundary_maturity_release_envelope_external_handoff_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "boundary_maturity_release_envelope_subject_continuity_count"
        ]
        == 6
    )
    assert (
        payload["counts"]["boundary_maturity_release_envelope_retained_gap_count"]
        == 6
    )
    assert payload["counts"]["retained_gap_enveloped_count"] == 6
    assert payload["counts"]["boundary_maturity_release_envelope_issue_count"] == 0
    assert payload["counts"]["retained_gap_exit_criteria_count"] == 6
    assert payload["counts"]["retained_gap_exit_criteria_release_allowed_count"] == 6
    assert payload["counts"]["retained_gap_exit_criteria_envelope_link_count"] == 6
    assert payload["counts"]["retained_gap_exit_criteria_handoff_link_count"] == 6
    assert (
        payload["counts"][
            "retained_gap_exit_criteria_guarded_completion_link_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "retained_gap_exit_criteria_boundary_capability_link_count"
        ]
        == 6
    )
    assert payload["counts"]["retained_gap_exit_criteria_exit_signal_count"] == 14
    assert payload["counts"]["retained_gap_external_receipt_target_count"] == 8
    assert payload["counts"]["retained_gap_external_receipt_alignment_count"] == 6
    assert (
        payload["counts"]["retained_gap_exit_criteria_prohibited_core_claim_count"]
        == 14
    )
    assert payload["counts"]["retained_gap_exit_criteria_issue_count"] == 0
    assert payload["counts"]["release_residual_ratio_ledger_count"] == 3
    assert payload["counts"]["release_residual_ratio_ledger_published_count"] == 3
    assert payload["counts"]["release_residual_ratio_ledger_non_full_count"] == 3
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_readiness_reconciliation_link_count"
        ]
        == 11
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_release_envelope_link_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_exit_criteria_link_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_receipt_alignment_link_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_count_delivery_boundary_alignment_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_count_delivery_boundary_link_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_count_delivery_receipt_alignment_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_maturity_l5_blocker_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count"
        ]
        == 6
    )
    assert payload["counts"]["release_residual_ratio_ledger_boundary_scope_alignment_count"] == 6
    assert payload["counts"]["release_residual_ratio_ledger_boundary_scope_link_count"] == 6
    assert payload["counts"]["release_residual_ratio_ledger_issue_count"] == 0
    assert payload["counts"]["release_residual_explanation_count"] == 14
    assert payload["counts"]["release_residual_explanation_covered_count"] == 14
    assert payload["counts"]["release_residual_explanation_mismatch_count"] == 0
    assert (
        payload["counts"][
            "release_residual_explanation_missing_summary_marker_count"
        ]
        == 0
    )
    assert payload["counts"]["release_residual_explanation_issue_count"] == 0
    assert payload["counts"]["release_acceptance_certificate_count"] == 14
    assert payload["counts"]["release_acceptance_certificate_ready_count"] == 14
    assert payload["counts"]["release_acceptance_certificate_receipt_count"] == 2
    assert (
        payload["counts"]["release_acceptance_certificate_ready_receipt_count"]
        == 2
    )
    assert (
        payload["counts"][
            "release_acceptance_certificate_expected_count_match_count"
        ]
        == 14
    )
    assert payload["counts"]["release_acceptance_certificate_source_evidence_count"] == 15
    assert (
        payload["counts"][
            "release_acceptance_certificate_ready_source_evidence_count"
        ]
        == 15
    )
    assert payload["counts"]["release_acceptance_certificate_requirement_dimension_count"] == 10
    assert (
        payload["counts"][
            "release_acceptance_certificate_ready_requirement_dimension_count"
        ]
        == 10
    )
    assert payload["counts"]["release_acceptance_certificate_issue_count"] == 0
    assert payload["counts"]["count_profile_profile_count"] == 20
    assert payload["counts"]["count_profile_referenced_profile_count"] == 17
    assert payload["counts"]["count_profile_rule_source_profile_count"] == 11
    assert payload["counts"]["count_profile_registry_only_profile_count"] == 2
    assert payload["counts"]["count_profile_rule_source_only_profile_count"] == 1
    assert payload["counts"]["count_profile_section_limit_profile_count"] == 1
    assert payload["counts"]["count_profile_unique_scope_count"] == 19
    assert payload["counts"]["count_profile_unique_primary_metric_count"] == 18
    assert payload["counts"]["count_profile_family_count"] == 15
    assert payload["counts"]["count_profile_ready_family_count"] == 14
    assert payload["counts"]["count_profile_boundary_family_count"] == 1
    assert payload["counts"]["count_profile_accounted_family_count"] == 15
    assert payload["counts"]["count_profile_count_profile_pack_count"] == 10
    assert payload["counts"]["count_profile_ready_count_profile_pack_count"] == 10
    assert payload["counts"]["count_profile_issue_count"] == 0
    assert payload["counts"]["count_profile_warning_count"] == 2
    assert payload["counts"]["material_schema_family_count"] == 15
    assert payload["counts"]["material_schema_material_family_count"] == 15
    assert payload["counts"]["material_schema_ready_material_family_count"] == 15
    assert payload["counts"]["material_schema_pack_count"] == 12
    assert payload["counts"]["material_schema_material_pack_count"] == 10
    assert payload["counts"]["material_schema_ready_material_pack_count"] == 10
    assert payload["counts"]["material_schema_schema_count"] == 22
    assert payload["counts"]["material_schema_referenced_schema_count"] == 21
    assert payload["counts"]["material_schema_registry_only_schema_count"] == 1
    assert payload["counts"]["material_schema_required_field_count"] == 41
    assert payload["counts"]["material_schema_required_asset_count"] == 6
    assert payload["counts"]["material_schema_issue_count"] == 0
    assert payload["counts"]["material_repair_flow_count"] == 11
    assert payload["counts"]["material_repair_flow_ready_count"] == 11
    assert payload["counts"]["material_repair_flow_capability_count"] == 33
    assert payload["counts"]["material_repair_flow_signal_count"] == 35
    assert payload["counts"]["material_repair_flow_target_type_count"] == 8
    assert payload["counts"]["material_repair_flow_runtime_surface_count"] == 21
    assert payload["counts"]["material_repair_flow_ui_surface_count"] == 19
    assert payload["counts"]["material_repair_flow_test_evidence_count"] == 26
    assert payload["counts"]["material_repair_flow_covered_pack_count"] == 10
    assert payload["counts"]["material_repair_flow_covered_family_count"] == 15
    assert payload["counts"]["material_repair_flow_issue_count"] == 0
    assert payload["counts"]["material_repair_flow_missing_source_evidence_count"] == 0
    assert payload["counts"]["fixed_layout_profile_channel_count"] == 12
    assert payload["counts"]["fixed_layout_profile_ready_channel_count"] == 12
    assert payload["counts"]["fixed_layout_profile_surface_count"] == 5
    assert payload["counts"]["fixed_layout_profile_ooxml_touchpoint_count"] == 11
    assert payload["counts"]["fixed_layout_profile_runtime_surface_count"] == 28
    assert payload["counts"]["fixed_layout_profile_ui_surface_count"] == 20
    assert payload["counts"]["fixed_layout_profile_report_surface_count"] == 15
    assert payload["counts"]["fixed_layout_profile_repair_target_type_count"] == 6
    assert payload["counts"]["fixed_layout_profile_test_evidence_count"] == 25
    assert payload["counts"]["fixed_layout_profile_covered_pack_count"] == 6
    assert payload["counts"]["fixed_layout_profile_covered_family_count"] == 6
    assert payload["counts"]["fixed_layout_profile_issue_count"] == 0
    assert payload["counts"]["fixed_layout_profile_missing_source_evidence_count"] == 0
    assert payload["counts"]["report_artifact_drilldown_channel_count"] == 10
    assert payload["counts"]["report_artifact_drilldown_ready_channel_count"] == 10
    assert payload["counts"]["report_artifact_drilldown_artifact_kind_count"] == 13
    assert payload["counts"]["report_artifact_drilldown_runtime_surface_count"] == 24
    assert payload["counts"]["report_artifact_drilldown_ui_surface_count"] == 18
    assert payload["counts"]["report_artifact_drilldown_report_surface_count"] == 21
    assert payload["counts"]["report_artifact_drilldown_repair_target_type_count"] == 3
    assert payload["counts"]["report_artifact_drilldown_test_evidence_count"] == 16
    assert payload["counts"]["report_artifact_drilldown_covered_pack_count"] == 12
    assert payload["counts"]["report_artifact_drilldown_covered_family_count"] == 15
    assert payload["counts"]["report_artifact_drilldown_issue_count"] == 0
    assert payload["counts"]["report_artifact_drilldown_missing_source_evidence_count"] == 0
    assert payload["counts"]["delivery_preset_family_count"] == 15
    assert payload["counts"]["delivery_preset_ready_family_count"] == 14
    assert payload["counts"]["delivery_preset_boundary_family_count"] == 1
    assert payload["counts"]["delivery_preset_accounted_family_count"] == 15
    assert payload["counts"]["delivery_preset_pack_count"] == 12
    assert payload["counts"]["delivery_preset_delivery_pack_count"] == 12
    assert payload["counts"]["delivery_preset_ready_delivery_pack_count"] == 11
    assert payload["counts"]["delivery_preset_boundary_delivery_pack_count"] == 1
    assert payload["counts"]["delivery_preset_accounted_delivery_pack_count"] == 12
    assert payload["counts"]["delivery_preset_unique_preset_count"] == 41
    assert payload["counts"]["delivery_preset_final_docx_preset_count"] == 35
    assert payload["counts"]["delivery_preset_compare_docx_preset_count"] == 17
    assert payload["counts"]["delivery_preset_report_only_preset_count"] == 18
    assert payload["counts"]["delivery_preset_material_package_preset_count"] == 15
    assert payload["counts"]["delivery_preset_content_visibility_rule_count"] == 18
    assert payload["counts"]["delivery_preset_issue_count"] == 0
    assert payload["counts"]["delivery_execution_channel_count"] == 10
    assert payload["counts"]["delivery_execution_ready_channel_count"] == 10
    assert payload["counts"]["delivery_execution_required_output_signal_count"] == 27
    assert payload["counts"]["delivery_execution_payload_key_count"] == 16
    assert payload["counts"]["delivery_execution_issue_count"] == 0
    assert payload["counts"]["delivery_execution_missing_source_evidence_count"] == 0
    assert payload["counts"]["formula_output_watermark_capability_count"] == 3
    assert payload["counts"]["formula_output_watermark_ready_capability_count"] == 3
    assert payload["counts"]["formula_output_watermark_family_count"] == 15
    assert payload["counts"]["formula_output_watermark_ready_family_count"] == 14
    assert payload["counts"]["formula_output_watermark_boundary_family_count"] == 1
    assert payload["counts"]["formula_output_watermark_accounted_family_count"] == 15
    assert payload["counts"]["formula_output_watermark_formula_family_count"] == 3
    assert payload["counts"]["formula_output_watermark_output_family_count"] == 15
    assert payload["counts"]["formula_output_watermark_watermark_family_count"] == 1
    assert payload["counts"]["formula_output_watermark_plugin_gate_count"] == 2
    assert payload["counts"]["formula_output_watermark_issue_count"] == 0
    assert payload["counts"]["product_readiness_subject_count"] == 27
    assert payload["counts"]["static_closed_but_not_green_count"] == 2
    assert payload["counts"]["static_closed_not_green_governed_count"] == 2
    assert payload["counts"]["maturity_upgrade_subject_count"] == 27
    assert payload["counts"]["maturity_upgrade_green_subject_count"] == 21
    assert payload["counts"]["maturity_upgrade_l5_blocked_subject_count"] == 6
    assert payload["counts"]["maturity_upgrade_l3_subject_count"] == 0
    assert payload["counts"]["maturity_upgrade_l4_subject_count"] == 0
    assert payload["counts"]["maturity_upgrade_boundary_subject_count"] == 6
    assert payload["counts"]["maturity_upgrade_gap_count"] == 6
    assert payload["counts"]["maturity_upgrade_gap_domain_count"] == 3
    assert payload["counts"]["maturity_upgrade_gap_domain_classified_count"] == 3
    assert payload["counts"]["maturity_upgrade_issue_count"] == 0
    assert {
        "input_sources",
        "user_journeys",
        "business_capability_matrix",
        "boundary_capability_matrix",
        "external_handoff_contracts",
        "boundary_guarded_completion",
        "residual_warning_governance",
        "boundary_readiness_reconciliation",
        "terminal_release_exceptions",
        "boundary_subject_dossiers",
        "non_subject_release_traces",
        "release_trace_partition",
        "release_projection_surfaces",
        "boundary_subject_continuity",
        "release_closure_ledger",
        "boundary_release_envelopes",
        "retained_gap_exit_criteria",
        "release_residual_ratios",
        "release_residual_explanations",
        "release_acceptance_certificate",
        "ambiguity_clarifications",
        "control_runtime",
        "material_repair_flow",
        "fixed_layout_profile",
        "report_artifact_drilldown",
        "delivery_execution",
    }.issubset({card["card_id"] for card in payload["cards"]})
    cards_by_id = {card["card_id"]: card for card in payload["cards"]}
    assert "high_frequency_coverage=12/12" in cards_by_id["coverage"]["detail"]
    assert cards_by_id["release_acceptance_certificate"]["value"] == "14/14 certified"
    assert (
        "2/2 receipt certificates"
        in cards_by_id["release_acceptance_certificate"]["detail"]
    )
    assert (
        "4/4 count/delivery boundary links aligned"
        in cards_by_id["release_residual_ratios"]["detail"]
    )
    assert (
        "4/4 count/delivery receipts aligned"
        in cards_by_id["release_residual_ratios"]["detail"]
    )
    assert (
        "6/6 L5 receipts aligned"
        in cards_by_id["release_residual_ratios"]["detail"]
    )
    assert (
        "6/6 L5 blockers aligned"
        in cards_by_id["release_acceptance_certificate"]["detail"]
    )
    assert (
        "6/6 boundary scopes guarded"
        in cards_by_id["release_residual_ratios"]["detail"]
    )
    assert "10 receipt alignments" in cards_by_id["release_residual_ratios"]["detail"]
    assert (
        "10/10 requirement dimensions"
        in cards_by_id["release_acceptance_certificate"]["detail"]
    )
    assert "15/15 evidence" in cards_by_id["release_acceptance_certificate"]["detail"]
    assert "6/6 L5 blockers enveloped" in cards_by_id["boundary_release_envelopes"]["detail"]
    assert "6/6 retained gaps enveloped" in cards_by_id["boundary_release_envelopes"]["detail"]
    assert cards_by_id["retained_gap_exit_criteria"]["value"] == "6/6 release-allowed"
    assert "6 boundary rows" in cards_by_id["retained_gap_exit_criteria"]["detail"]
    assert "6/6 receipt-aligned" in cards_by_id["retained_gap_exit_criteria"]["detail"]
    assert "8 receipts" in cards_by_id["retained_gap_exit_criteria"]["detail"]
    assert "14 prohibited claims" in cards_by_id["retained_gap_exit_criteria"]["detail"]
    assert "10 envelopes" in cards_by_id["release_residual_ratios"]["detail"]
    assert "10 exit criteria" in cards_by_id["release_residual_ratios"]["detail"]
    assert "6/6 L5 enveloped" in cards_by_id["release_residual_ratios"]["detail"]
    assert cards_by_id["release_residual_explanations"]["value"] == "14/14 covered"
    assert "0 marker gaps" in cards_by_id["release_residual_explanations"]["detail"]
    assert "6/6 L5 enveloped" in cards_by_id["maturity_upgrade"]["detail"]
    assert "6/6 retained gaps enveloped" in cards_by_id["maturity_upgrade"]["detail"]
    assert "3/3 domains classified" in cards_by_id["maturity_upgrade"]["detail"]
    assert "5/5 input managed" in cards_by_id["residual_warning_governance"]["detail"]
    assert (
        "2/2 count profiles managed"
        in cards_by_id["residual_warning_governance"]["detail"]
    )
    assert (
        "5/5 plugin/manual managed"
        in cards_by_id["residual_warning_governance"]["detail"]
    )
    assert (
        "2/2 reference profiles managed"
        in cards_by_id["residual_warning_governance"]["detail"]
    )
    assert (
        "1/1 Visio fixture closed"
        in cards_by_id["residual_warning_governance"]["detail"]
    )
    assert (
        "2/2 static boundary governed"
        in cards_by_id["boundary_readiness_reconciliation"]["detail"]
    )
    assert (
        "2/2 static boundary governed"
        in cards_by_id["terminal_release_exceptions"]["detail"]
    )
    assert "3/3 dashboard projected" in cards_by_id["residual_warning_governance"]["detail"]
    assert "3/3 dashboard warnings" in cards_by_id["terminal_release_exceptions"]["detail"]
    assert "2/2 static-closed governed" in cards_by_id["readiness"]["detail"]
    assert "15/15 accounted" in cards_by_id["count_profiles"]["detail"]
    assert "15/15 families accounted" in cards_by_id["delivery_presets"]["detail"]
    assert "12/12 packs accounted" in cards_by_id["delivery_presets"]["detail"]

    for row in report.rows:
        assert row.status in {"ready", "needs_depth"}
        assert row.missing_lens_ids == ()
        assert row.issue_ids == ()
        assert row.dashboard_lens_ids == SCENE_MATRIX_DASHBOARD_LENS_IDS
        assert row.drilldown_source_ids == SCENE_MATRIX_DASHBOARD_SOURCE_IDS
        assert row.request_cell_count > 0
        assert row.sample_fixture_count > 0
        assert row.report_anchor_count == row.request_cell_count
        assert row.control_contract_count == 13
        assert row.control_runtime_control_count == 12
        assert row.control_runtime_issue_count == 0
        assert row.material_schema_issue_count == 0
        if row.material_schema_count:
            assert row.material_repair_flow_count == 11
        else:
            assert row.material_repair_flow_count == 0
        assert row.material_repair_flow_issue_count == 0
        assert row.fixed_layout_profile_issue_count == 0
        assert row.report_artifact_drilldown_issue_count == 0
        assert row.delivery_preset_issue_count == 0
        assert row.delivery_execution_issue_count == 0
        assert row.input_source_issue_count == 0
        assert row.ambiguity_clarification_issue_count == 0
        assert row.object_preflight_action_issue_count == 0
        assert row.user_journey_path_count > 0
        assert row.user_journey_issue_count == 0
        assert row.user_journey_path_type_ids
        assert row.business_capability_count > 0
        assert row.business_capability_issue_count == 0
        assert row.business_capability_ids
        assert row.input_formats or row.input_boundary_source_ids

    batch = rows["batch_forms"]
    assert batch.family_ids == ("hr_batch_documents", "form_batch_documents")
    assert batch.family_count == 2
    assert batch.request_cell_count == 7
    assert batch.matched_request_cell_count == 4
    assert "fixed_row_height" in batch.word_risk_surface_ids
    assert "ambiguous_request_cell" in batch.boundary_signal_ids
    assert batch.material_schema_ids == (
        "personnel_records_v1",
        "form_batch_fields_v1",
    )
    assert batch.material_repair_flow_count == 11
    assert batch.fixed_layout_profile_channel_count == 11
    assert batch.report_artifact_drilldown_channel_count == 10
    assert batch.delivery_execution_channel_count == 7
    assert batch.product_readiness_level == "green_l5"
    assert batch.product_gap_count == 0
    assert batch.business_capability_ids == (
        "hr_batch_documents",
        "form_batch_documents",
    )
    assert batch.business_capability_warning_count == 0
    assert batch.family_status_counts == (("ready", 2),)
    assert batch.sample_fixture_count == 4
    assert batch.user_journey_path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert batch.user_journey_warning_count == 0

    professional = rows["professional_disclosure"]
    assert professional.status == "needs_depth"
    assert professional.plugin_boundary is True
    assert professional.manual_boundary_request_cell_count == 6
    assert professional.family_count == 4
    assert professional.material_schema_count == 4
    assert professional.material_repair_flow_count == 11
    assert "finance_quote_fields_v1" in professional.material_schema_ids
    assert "boundary_readiness" in professional.boundary_signal_ids
    assert "family_plugin_boundary_only" in professional.boundary_signal_ids
    assert professional.delivery_preset_count == 10
    assert professional.input_boundary_source_ids == ("ai_content_generation",)
    assert professional.business_capability_count == 5
    assert professional.business_capability_ids == (
        "finance_quote_documents",
        "ip_patent_documents",
        "bilingual_translation_documents",
        "regulated_disclosure_documents",
        "professional_disclosure_boundary",
    )
    assert professional.business_capability_warning_count == 0

    application = rows["application_reports"]
    assert application.product_readiness_level == "green_l5"
    assert application.product_gap_count == 0
    assert application.material_schema_ids == (
        "project_application_materials_v1",
        "product_assets_v1",
        "case_study_assets_v1",
    )
    assert application.family_status_counts == (("ready", 2),)

    exam = rows["exam_education"]
    assert exam.status == "needs_depth"
    assert "answer_sheet" in exam.delivery_preset_ids
    assert exam.fixed_layout_profile_channel_count == 2
    assert exam.report_artifact_drilldown_channel_count == 10
    assert exam.delivery_content_visibility_rule_count == 20
    assert exam.delivery_structured_intermediate_preset_count == 5
    assert exam.delivery_execution_channel_count >= 5
    assert {"json", "xlsx"}.issubset(set(exam.input_structured_formats))
    assert {"ai_content_generation", "complex_diagram_generation"}.issubset(
        set(exam.input_boundary_source_ids)
    )
    assert exam.business_capability_ids == ("exam_teaching",)
    assert exam.business_capability_warning_count == 0

    contract = rows["contract_delivery"]
    assert contract.delivery_compare_preset_count >= 2
    assert "field_consistency_report" in contract.delivery_preset_ids
    assert contract.business_capability_ids == ("contract_delivery",)
    assert contract.business_capability_warning_count == 0
    assert contract.product_readiness_level == "green_l5"
    assert contract.sample_fixture_count == 2
    assert contract.request_cell_count == 4
    assert contract.user_journey_path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )

    quick = rows["quick_formatting"]
    assert quick.family_count == 0
    assert quick.sample_fixture_count == 3
    assert quick.sample_fixture_ids == (
        "quick_formatting_fields_comments",
        "quick_formatting_preserve_fields_degraded",
        "quick_formatting_business_template_cleanup",
    )
    assert quick.report_artifact_drilldown_channel_count == 9
    assert "carrier_layer" in quick.dashboard_lens_ids
    assert quick.product_readiness_level == "green_l5"
    assert quick.input_formats == ("docx", "markdown")
    assert quick.business_capability_ids == ("quick_word_formatting",)
    assert quick.business_capability_warning_count == 0

    chinese = rows["chinese_academic"]
    assert chinese.status == "ready"
    assert chinese.sample_fixture_count == 3
    assert chinese.sample_fixture_ids == (
        "chinese_academic_hidden_formula",
        "chinese_academic_rule_source_degraded",
        "chinese_academic_school_rule_section_confirmation",
    )
    assert chinese.material_schema_ids == ("thesis_school_rule_context_v1",)
    assert chinese.product_readiness_level == "green_l5"
    assert chinese.product_gap_count == 0
    assert chinese.user_journey_path_type_ids == (
        "success",
        "degraded",
        "failure",
        "manual_boundary",
        "handoff",
    )
    assert chinese.user_journey_warning_count == 0
    assert chinese.business_capability_warning_count == 0

    journal = rows["english_journal"]
    assert journal.status == "ready"
    assert journal.sample_fixture_count == 3
    assert journal.user_journey_path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
    )
    assert journal.manual_boundary_request_cell_count == 1
    assert journal.user_journey_warning_count == 0
    assert journal.business_capability_warning_count == 0
    assert "family_plugin_gate" in journal.boundary_signal_ids
    assert journal.product_readiness_level == "green_l5"
    assert journal.product_gap_count == 0

    official = rows["official_policy"]
    assert official.sample_fixture_count == 3
    assert official.sample_fixture_ids == (
        "official_policy_fields_comments",
        "official_policy_formal_archive_manual_boundary",
        "official_policy_metadata_archive_report",
    )
    assert official.product_readiness_level == "green_l5"
    assert official.product_gap_count == 0
    assert official.user_journey_path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert official.user_journey_warning_count == 0
    assert official.business_capability_warning_count == 0
    assert official.business_capability_ids == ("meeting_policy_documents",)

    technical = rows["technical_long_docs"]
    assert technical.sample_fixture_count == 3
    assert technical.sample_fixture_ids == (
        "technical_long_docs_skip_objects",
        "technical_long_docs_chapter_inventory_manual_boundary",
        "technical_long_docs_index_appendix_merge_boundary",
    )
    assert technical.product_readiness_level == "green_l5"
    assert technical.product_gap_count == 0
    assert technical.user_journey_path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert technical.user_journey_warning_count == 0
    assert technical.business_capability_warning_count == 0
    assert technical.business_capability_ids == ("long_document_publishing",)

    bidding = rows["bidding_materials"]
    assert bidding.status == "ready"
    assert bidding.sample_fixture_count == 4
    assert bidding.sample_fixture_ids == (
        "bidding_materials_attachments",
        "bidding_materials_missing_attachment_degraded",
        "bidding_materials_original_copy_manual_boundary",
        "bidding_materials_consortium_seal_residue_degraded",
    )
    assert bidding.user_journey_path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert bidding.user_journey_warning_count == 0
    assert bidding.business_capability_warning_count == 0
    assert bidding.business_capability_ids == ("qualification_archive_packages",)

    application = rows["application_reports"]
    assert application.status == "ready"
    assert application.sample_fixture_count == 6
    assert application.user_journey_warning_count == 0
    assert application.user_journey_path_type_ids == (
        "success",
        "degraded",
        "manual_boundary",
        "ambiguous_decision",
    )
    assert application.business_capability_warning_count == 0

    professional = rows["professional_disclosure"]
    assert professional.user_journey_warning_count == 0
    assert professional.sample_fixture_count == 6
    assert "professional_disclosure_finance_table_mapping_boundary" in (
        professional.sample_fixture_ids
    )
    assert "professional_disclosure_regulated_assurance_boundary" in (
        professional.sample_fixture_ids
    )
    assert "degraded" in professional.user_journey_path_type_ids

    import_boundary = rows["import_ai_boundary"]
    assert import_boundary.user_journey_warning_count == 0
    assert import_boundary.sample_fixture_count == 3
    assert "import_ai_boundary_latex_handoff_confidence" in (
        import_boundary.sample_fixture_ids
    )
    assert import_boundary.user_journey_path_type_ids == (
        "degraded",
        "failure",
        "manual_boundary",
        "handoff",
    )


def test_scene_matrix_dashboard_filters_for_drilldown():
    family_report = build_scene_matrix_dashboard(family_id="hr_batch_documents")
    manual_report = build_scene_matrix_dashboard(
        boundary_signal="manual_boundary_request_cell"
    )
    boundary_report = build_scene_matrix_dashboard(readiness_level="blue_boundary")

    assert [row.pack_id for row in family_report.rows] == ["batch_forms"]
    assert [row.pack_id for row in manual_report.rows] == [
        "english_journal",
        "exam_education",
        "professional_disclosure",
        "import_ai_boundary",
    ]
    assert [row.pack_id for row in boundary_report.rows] == [
        "professional_disclosure",
        "import_ai_boundary",
    ]
    assert family_report.to_payload()["family_filter"] == "hr_batch_documents"
    assert manual_report.to_payload()["boundary_filter"] == (
        "manual_boundary_request_cell"
    )


def test_scene_matrix_dashboard_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_matrix_dashboard.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_dashboard.py",
            "--format",
            "json",
            "--family",
            "hr_batch_documents",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.stdout == ""
    assert payload["status"] == "passed"
    assert payload["visible_count"] == 1
    assert payload["rows"][0]["pack_id"] == "batch_forms"
    assert payload["rows"][0]["family_ids"] == [
        "hr_batch_documents",
        "form_batch_documents",
    ]


def test_scene_matrix_dashboard_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_dashboard.py",
            "--format",
            "markdown",
            "--pack",
            "professional_disclosure",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Matrix Dashboard" in result.stdout
    assert "| Pack | Status | Readiness | Cells | Families | Boundaries |" in (
        result.stdout
    )
    assert "professional_disclosure" in result.stdout
    assert "manual_boundary_request_cell" in result.stdout
    assert "high_frequency_task_lexicon_audit" in result.stdout
    assert "scene_ambiguous_boundary_audit" in result.stdout
    assert "scene_ambiguity_clarification_ui_audit" in result.stdout
    assert "scene_import_handoff_audit" in result.stdout
    assert "scene_object_preflight_action_audit" in result.stdout
    assert "scene_user_journey_fixture_audit" in result.stdout
    assert "scene_business_capability_matrix_audit" in result.stdout
    assert "scene_control_runtime_consistency_audit" in result.stdout
    assert "scene_family_fixture_depth_audit" in result.stdout
    assert "scene_material_schema_audit" in result.stdout
    assert "scene_material_repair_flow_audit" in result.stdout
    assert "scene_fixed_layout_profile_audit" in result.stdout
    assert "scene_report_artifact_drilldown_audit" in result.stdout
    assert "scene_delivery_preset_audit" in result.stdout
    assert "scene_delivery_preset_execution_audit" in result.stdout
    assert "scene_formula_output_watermark_audit" in result.stdout
    assert "scene_input_source_audit" in result.stdout
    assert "scene_count_profile_audit" in result.stdout
    assert "scene_product_maturity_upgrade_audit" in result.stdout
    assert "scene_word_risk_closure_audit" in result.stdout
    assert "scene_plugin_boundary_confirmation_audit" in result.stdout
    assert "scene_residual_warning_governance_audit" in result.stdout
    assert "scene_boundary_readiness_reconciliation_audit" in result.stdout
    assert "scene_terminal_release_exception_audit" in result.stdout
    assert "scene_boundary_subject_release_dossier_audit" in result.stdout
    assert "scene_non_subject_release_trace_attribution_audit" in result.stdout
    assert "scene_release_trace_partition_guard_audit" in result.stdout
    assert "scene_release_projection_surface_parity_audit" in result.stdout
    assert "scene_boundary_subject_release_continuity_audit" in result.stdout
    assert "scene_release_closure_ledger_audit" in result.stdout
    assert "scene_boundary_maturity_release_envelope_audit" in result.stdout
    assert "scene_retained_gap_exit_criteria_audit" in result.stdout
    assert "scene_release_residual_ratio_ledger_audit" in result.stdout
    assert "scene_release_residual_explanation_audit" in result.stdout


def test_release_gate_includes_scene_matrix_dashboard(tmp_path, capsys):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_matrix_dashboard"]["status"] == "passed"
    assert payload["counts"]["scene_matrix_dashboard_pack_count"] == 12
    assert payload["counts"]["high_frequency_completeness_ready_pack_count"] == 12
    assert payload["counts"]["scene_matrix_dashboard_visible_count"] == 12
    assert payload["counts"]["scene_matrix_dashboard_issue_count"] == 0
    assert payload["counts"]["scene_matrix_dashboard_warning_count"] == 3
    assert payload["counts"]["scene_matrix_dashboard_lens_count"] == 9
    assert payload["counts"]["scene_matrix_dashboard_source_count"] == 43
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
    assert payload["counts"]["scene_input_source_family_count"] == 15
    assert payload["counts"]["scene_input_source_ready_family_count"] == 14
    assert payload["counts"]["scene_input_source_ready_input_pack_count"] == 12
    assert payload["counts"]["scene_input_source_input_pack_count"] == 12
    assert payload["counts"]["scene_input_source_warning_count"] == 5
    assert payload["counts"]["scene_object_preflight_action_target_count"] == 11
    assert (
        payload["counts"]["scene_object_preflight_action_ready_target_count"]
        == 11
    )
    assert payload["counts"]["scene_object_preflight_action_warning_count"] == 0
    assert payload["counts"]["scene_ambiguity_clarification_count"] == 6
    assert payload["counts"]["scene_ambiguity_clarification_ready_count"] == 6
    assert payload["counts"]["scene_ambiguity_clarification_issue_count"] == 0
    assert payload["counts"]["scene_user_journey_pack_count"] == 12
    assert payload["counts"]["scene_user_journey_ready_pack_count"] == 12
    assert payload["counts"]["scene_user_journey_path_count"] == 100
    assert payload["counts"]["scene_user_journey_warning_count"] == 0
    assert payload["counts"]["scene_business_capability_matrix_count"] == 18
    assert payload["counts"]["scene_business_capability_matrix_ready_count"] == 18
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
    assert payload["counts"]["scene_business_capability_matrix_boundary_count"] == 7
    assert payload["counts"]["scene_business_capability_matrix_manual_gate_count"] == 10
    assert (
        payload["counts"][
            "scene_business_capability_matrix_missing_journey_group_count"
        ]
        == 0
    )
    assert payload["counts"]["scene_business_capability_matrix_issue_count"] == 0
    assert payload["counts"]["scene_business_capability_matrix_warning_count"] == 0
    assert (
        payload["counts"][
            "scene_business_capability_matrix_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["checks"]["scene_boundary_capability_matrix"]["status"] == "passed"
    assert payload["counts"]["scene_boundary_capability_count"] == 6
    assert payload["counts"]["scene_boundary_capability_ready_count"] == 6
    assert payload["counts"]["scene_boundary_capability_professional_count"] == 5
    assert payload["counts"]["scene_boundary_capability_import_ai_count"] == 1
    assert payload["counts"]["scene_boundary_capability_risk_domain_count"] == 9
    assert (
        payload["counts"]["scene_boundary_capability_decision_requirement_count"]
        == 4
    )
    assert payload["counts"]["scene_boundary_capability_external_receipt_count"] == 8
    assert payload["counts"]["scene_boundary_capability_release_guardrail_count"] == 4
    assert payload["counts"]["scene_boundary_capability_issue_count"] == 0
    assert payload["checks"]["scene_boundary_guarded_completion_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_boundary_guarded_completion_subject_count"] == 6
    assert payload["counts"]["scene_boundary_guarded_completion_ready_count"] == 6
    assert payload["counts"]["scene_boundary_guarded_completion_retained_gap_count"] == 6
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
    assert payload["counts"]["scene_boundary_guarded_completion_issue_count"] == 0
    assert payload["checks"]["scene_residual_warning_governance_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_residual_warning_governance_warning_count"] == 10
    assert payload["counts"]["scene_residual_warning_governance_managed_count"] == 10
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
    assert payload["counts"]["scene_boundary_readiness_reconciliation_count"] == 15
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
    assert payload["counts"]["scene_terminal_release_exception_count"] == 5
    assert payload["counts"]["scene_terminal_release_exception_governed_count"] == 5
    assert payload["counts"]["scene_terminal_release_exception_ungoverned_count"] == 0
    assert (
        payload["counts"]["scene_terminal_release_exception_managed_warning_count"]
        == 10
    )
    assert payload["counts"]["scene_terminal_release_exception_trace_count"] == 36
    assert (
        payload["counts"][
            "scene_terminal_release_exception_unique_source_trace_count"
        ]
        == 31
    )
    assert payload["checks"]["scene_boundary_subject_release_dossier_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_boundary_subject_release_dossier_subject_count"] == 6
    assert payload["counts"]["scene_boundary_subject_release_dossier_ready_count"] == 6
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
    assert payload["counts"]["scene_non_subject_release_trace_attribution_count"] == 10
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
    assert payload["counts"]["scene_release_trace_partition_guard_partition_count"] == 3
    assert payload["counts"]["scene_release_trace_partition_guard_ready_count"] == 3
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
    assert payload["counts"]["scene_release_projection_surface_parity_count"] == 13
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
    assert payload["counts"]["scene_release_closure_ledger_stage_count"] == 13
    assert payload["counts"]["scene_release_closure_ledger_ready_count"] == 13
    assert payload["counts"]["scene_release_closure_ledger_stage_order_count"] == 13
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
    assert payload["counts"]["scene_release_closure_ledger_dashboard_card_count"] == 13
    assert payload["counts"]["scene_release_closure_ledger_drilldown_item_count"] == 13
    assert (
        payload["counts"]["scene_release_closure_ledger_summary_projection_count"]
        == 13
    )
    assert payload["counts"]["scene_release_closure_ledger_issue_count"] == 0
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
    assert payload["counts"]["scene_retained_gap_exit_criteria_count"] == 6
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
    assert payload["counts"]["scene_retained_gap_external_receipt_target_count"] == 8
    assert (
        payload["counts"]["scene_retained_gap_external_receipt_alignment_count"]
        == 6
    )
    assert payload["counts"]["scene_retained_gap_exit_criteria_issue_count"] == 0
    assert payload["checks"]["scene_release_residual_ratio_ledger_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_release_residual_ratio_ledger_count"] == 3
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
    assert payload["counts"]["scene_release_residual_ratio_ledger_issue_count"] == 0
    assert payload["checks"]["scene_release_residual_explanation_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_release_residual_explanation_count"] == 14
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
    assert payload["counts"]["scene_release_residual_explanation_issue_count"] == 0
    assert payload["checks"]["scene_release_acceptance_certificate_audit"][
        "status"
    ] == "passed"
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
    assert payload["counts"]["scene_release_acceptance_certificate_issue_count"] == 0
    assert payload["counts"]["scene_control_runtime_control_count"] == 12
    assert payload["counts"]["scene_control_runtime_ready_control_count"] == 12
    assert payload["counts"]["scene_control_runtime_contract_link_count"] == 16
    assert payload["counts"]["scene_control_runtime_issue_count"] == 0
    assert payload["counts"]["scene_delivery_execution_channel_count"] == 10
    assert payload["counts"]["scene_delivery_execution_ready_channel_count"] == 10
    assert payload["counts"]["scene_delivery_execution_issue_count"] == 0
    assert payload["counts"]["scene_material_repair_flow_count"] == 11
    assert payload["counts"]["scene_material_repair_flow_ready_count"] == 11
    assert payload["counts"]["scene_material_repair_flow_issue_count"] == 0
    assert (
        payload["counts"]["scene_material_repair_flow_missing_source_evidence_count"]
        == 0
    )
    assert payload["counts"]["scene_fixed_layout_profile_channel_count"] == 12
    assert payload["counts"]["scene_fixed_layout_profile_ready_channel_count"] == 12
    assert payload["counts"]["scene_fixed_layout_profile_issue_count"] == 0
    assert (
        payload["counts"]["scene_fixed_layout_profile_missing_source_evidence_count"]
        == 0
    )
    assert payload["counts"]["scene_report_artifact_drilldown_channel_count"] == 10
    assert (
        payload["counts"]["scene_report_artifact_drilldown_ready_channel_count"]
        == 10
    )
    assert payload["counts"]["scene_report_artifact_drilldown_issue_count"] == 0
    assert (
        payload["counts"][
            "scene_report_artifact_drilldown_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_matrix_dashboard"]["status"] == "passed"
    assert payload["scene_matrix_dashboard"]["counts"]["request_cell_count"] == 53
    assert payload["scene_matrix_dashboard"]["counts"]["import_handoff_count"] == 1
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
    assert payload["counts"]["scene_count_profile_profile_count"] == 20
    assert payload["counts"]["scene_count_profile_accounted_family_count"] == 15
    assert payload["counts"]["scene_delivery_preset_accounted_family_count"] == 15
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
    assert payload["counts"]["static_closed_but_not_green_count"] == 2
    assert payload["counts"]["static_closed_not_green_governed_count"] == 2
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
    assert payload["counts"]["dashboard_warning_projection_governed_count"] == 3
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
    assert payload["counts"]["input_source_warning_managed_count"] == 5
    assert payload["counts"]["count_profile_warning_managed_count"] == 2
    assert payload["counts"]["plugin_manual_warning_managed_count"] == 5
    assert payload["counts"]["reference_profile_warning_managed_count"] == 2
    assert payload["counts"]["visio_fixture_closed_verified_count"] == 1
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
    assert payload["counts"]["retained_gap_enveloped_count"] == 6
    assert (
        payload["counts"]["retained_gap_enveloped_count"]
        == payload["counts"]["scene_product_maturity_upgrade_gap_count"]
    )
    assert payload["counts"]["gap_domain_classified_count"] == 3
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

    _print_human(payload)
    output = capsys.readouterr().out
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


def test_scene_summary_projection_exposes_dashboard_cards():
    items = {
        item.key: item for item in build_scene_matrix_dashboard_summary_items()
    }

    assert items["scene_matrix_dashboard"].value == "12/12 packs"
    assert "high_frequency_coverage=12/12" in items["scene_matrix_dashboard"].detail
    assert "15 families" in items["scene_matrix_dashboard"].detail
    assert "11/11 P1 fixtures" in items["scene_matrix_dashboard"].detail
    assert "29 task families" in items["scene_matrix_dashboard"].detail
    assert "6 ambiguous pairs" in items["scene_matrix_dashboard"].detail
    assert "6/6 clarifications" in items["scene_matrix_dashboard"].detail
    assert "1 handoff" in items["scene_matrix_dashboard"].detail
    assert "12/12 input packs" in items["scene_matrix_dashboard"].detail
    assert "53 request cells" in items["scene_matrix_dashboard"].detail
    assert "100 user journeys" in items["scene_matrix_dashboard"].detail
    assert "18/18 business capabilities" in items["scene_matrix_dashboard"].detail
    assert "6/6 external handoffs" in items["scene_matrix_boundary"].detail
    assert "6/6 guarded" in items["scene_matrix_boundary"].detail
    assert "10/10 managed warnings" in items["scene_matrix_boundary"].detail
    assert "5/5 input warnings managed" in items["scene_matrix_boundary"].detail
    assert "2/2 count warnings managed" in items["scene_matrix_boundary"].detail
    assert "5/5 plugin/manual warnings managed" in items["scene_matrix_boundary"].detail
    assert "2/2 reference warnings managed" in items["scene_matrix_boundary"].detail
    assert "1/1 Visio fixture closed" in items["scene_matrix_boundary"].detail
    assert "3/3 dashboard warnings governed" in items["scene_matrix_boundary"].detail
    assert "15/15 readiness reconciled" in items["scene_matrix_boundary"].detail
    assert "5/5 release exceptions" in items["scene_matrix_boundary"].detail
    assert "2/2 static-closed governed" in items["scene_matrix_boundary"].detail
    assert "36 exception traces" in items["scene_matrix_boundary"].detail
    assert "6/6 boundary dossiers" in items["scene_matrix_boundary"].detail
    assert "10/10 non-subject traces" in items["scene_matrix_boundary"].detail
    assert "36/36 trace partition" in items["scene_matrix_boundary"].detail
    assert "13/13 release projections" in items["scene_matrix_boundary"].detail
    assert "6/6 subject continuity" in items["scene_matrix_boundary"].detail
    assert "13/13 release ledger" in items["scene_matrix_boundary"].detail
    assert "6/6 boundary release envelopes" in items["scene_matrix_boundary"].detail
    assert "6/6 L5 blockers enveloped" in items["scene_matrix_boundary"].detail
    assert "6/6 L5 blockers aligned" in items["scene_matrix_boundary"].detail
    assert "6/6 L5 receipts aligned" in items["scene_matrix_boundary"].detail
    assert "6/6 retained gaps enveloped" in items["scene_matrix_boundary"].detail
    assert "6/6 retained gap exit criteria" in items["scene_matrix_boundary"].detail
    assert "6/6 retained gap receipts" in items["scene_matrix_boundary"].detail
    assert "3/3 gap domains classified" in items["scene_matrix_boundary"].detail
    assert "3/3 release residual ratios" in items["scene_matrix_boundary"].detail
    assert "10 residual ratio exit criteria" in items["scene_matrix_boundary"].detail
    assert "10 residual ratio receipts" in items["scene_matrix_boundary"].detail
    assert (
        "4/4 count/delivery boundary links aligned"
        in items["scene_matrix_boundary"].detail
    )
    assert (
        "4/4 count/delivery receipts aligned"
        in items["scene_matrix_boundary"].detail
    )
    assert "6/6 boundary scopes guarded" in items["scene_matrix_boundary"].detail
    assert "14/14 residual explanations" in items["scene_matrix_boundary"].detail
    assert "14/14 release acceptance certificate" in items["scene_matrix_boundary"].detail
    assert "2/2 receipt certificates" in items["scene_matrix_boundary"].detail
    assert "10/10 requirement dimensions" in items["scene_matrix_boundary"].detail
    assert "15/15 acceptance evidence" in items["scene_matrix_boundary"].detail
    assert "6/6 handoff contracts" in items["scene_matrix_evidence"].detail
    assert "6/6 guarded completions" in items["scene_matrix_evidence"].detail
    assert "10/10 managed warnings" in items["scene_matrix_evidence"].detail
    assert "5/5 input warnings managed" in items["scene_matrix_evidence"].detail
    assert "2/2 count warnings managed" in items["scene_matrix_evidence"].detail
    assert "5/5 plugin/manual warnings managed" in items["scene_matrix_evidence"].detail
    assert "2/2 reference warnings managed" in items["scene_matrix_evidence"].detail
    assert "1/1 Visio fixture closed" in items["scene_matrix_evidence"].detail
    assert "3/3 dashboard warnings governed" in items["scene_matrix_evidence"].detail
    assert "15/15 readiness reconciled" in items["scene_matrix_evidence"].detail
    assert "5/5 release exceptions" in items["scene_matrix_evidence"].detail
    assert "2/2 static-closed governed" in items["scene_matrix_evidence"].detail
    assert "36 exception traces" in items["scene_matrix_evidence"].detail
    assert "6/6 boundary dossiers" in items["scene_matrix_evidence"].detail
    assert "10/10 non-subject traces" in items["scene_matrix_evidence"].detail
    assert "36/36 trace partition" in items["scene_matrix_evidence"].detail
    assert "13/13 release projections" in items["scene_matrix_evidence"].detail
    assert "6/6 subject continuity" in items["scene_matrix_evidence"].detail
    assert "13/13 Release closure ledger" in items["scene_matrix_evidence"].detail
    assert "6/6 boundary release envelopes" in items["scene_matrix_evidence"].detail
    assert "6/6 L5 blockers enveloped" in items["scene_matrix_evidence"].detail
    assert "6/6 L5 blockers aligned" in items["scene_matrix_evidence"].detail
    assert "6/6 L5 receipts aligned" in items["scene_matrix_evidence"].detail
    assert "6/6 retained gaps enveloped" in items["scene_matrix_evidence"].detail
    assert "6/6 retained gap exit criteria" in items["scene_matrix_evidence"].detail
    assert "3/3 gap domains classified" in items["scene_matrix_evidence"].detail
    assert "3/3 release residual ratios" in items["scene_matrix_evidence"].detail
    assert "10 residual ratio exit criteria" in items["scene_matrix_evidence"].detail
    assert "10 residual ratio receipts" in items["scene_matrix_evidence"].detail
    assert (
        "4/4 count/delivery boundary links aligned"
        in items["scene_matrix_evidence"].detail
    )
    assert (
        "4/4 count/delivery receipts aligned"
        in items["scene_matrix_evidence"].detail
    )
    assert "6/6 boundary scopes guarded" in items["scene_matrix_evidence"].detail
    assert "14/14 residual explanations" in items["scene_matrix_evidence"].detail
    assert "14/14 release acceptance certificate" in items["scene_matrix_evidence"].detail
    assert "2/2 receipt certificates" in items["scene_matrix_evidence"].detail
    assert "10/10 requirement dimensions" in items["scene_matrix_evidence"].detail
    assert "15/15 acceptance evidence" in items["scene_matrix_evidence"].detail
    assert items["scene_matrix_boundary"].value == "4 plugin packs"
    assert "4 manual-boundary packs" in items["scene_matrix_boundary"].detail
    assert "6 ambiguous pairs" in items["scene_matrix_boundary"].detail
    assert "1 handoff" in items["scene_matrix_boundary"].detail
    assert "4 gates" in items["scene_matrix_boundary"].detail
    assert "14 risk domains" in items["scene_matrix_boundary"].detail
    assert items["scene_matrix_evidence"].value == "15 Word risks"
    assert "13 control contracts" in items["scene_matrix_evidence"].detail
    assert "42 DOCX fixtures" in items["scene_matrix_evidence"].detail
    assert "100 user journeys" in items["scene_matrix_evidence"].detail
    assert "18/18 business capabilities" in items["scene_matrix_evidence"].detail
    assert "12/12 control runtime" in items["scene_matrix_evidence"].detail
    assert "11/11 ObjectPreflight actions" in (
        items["scene_matrix_evidence"].detail
    )
    assert "14/15 CountProfile families" in items["scene_matrix_evidence"].detail
    assert "15/15 CountProfile accounted" in items["scene_matrix_evidence"].detail
    assert "14 InputSourceProfile families" in items["scene_matrix_evidence"].detail
    assert "15 material families" in items["scene_matrix_evidence"].detail
    assert "14/15 delivery families" in items["scene_matrix_evidence"].detail
    assert "15/15 delivery accounted" in items["scene_matrix_evidence"].detail
    assert "12/12 fixed-layout profile" in items["scene_matrix_evidence"].detail
    assert "10/10 report/artifact drilldown" in items["scene_matrix_evidence"].detail
    assert "3/3 F/O/W" in items["scene_matrix_evidence"].detail
    assert "15/15 F/O/W families accounted" in items["scene_matrix_evidence"].detail
    assert "11 P1 family fixtures" in items["scene_matrix_evidence"].detail
    assert items["scene_matrix_readiness"].value == "27 subjects"
    assert "Green/L5" in items["scene_matrix_readiness"].detail
    assert "2/2 static-closed governed" in items["scene_matrix_readiness"].detail
    assert "6 L5-blocked" in items["scene_matrix_readiness"].detail
    assert "6/6 retained gaps enveloped" in items["scene_matrix_readiness"].detail
    assert "6/6 retained gap exit criteria" in items["scene_matrix_readiness"].detail
    assert "6/6 retained gap receipts" in items["scene_matrix_readiness"].detail
    assert "3/3 gap domains classified" in items["scene_matrix_readiness"].detail
    assert "6/6 L5 blockers enveloped" in items["scene_matrix_readiness"].detail
    assert "6/6 L5 receipts aligned" in items["scene_matrix_readiness"].detail
    assert "6 gaps" in items["scene_matrix_readiness"].detail
    assert "3 domains" in items["scene_matrix_readiness"].detail
    assert "6/6 boundary guarded" in items["scene_matrix_readiness"].detail
    assert "5/5 input warnings managed" in items["scene_matrix_readiness"].detail
    assert "2/2 count warnings managed" in items["scene_matrix_readiness"].detail
    assert "5/5 plugin/manual warnings managed" in items["scene_matrix_readiness"].detail
    assert "2/2 reference warnings managed" in items["scene_matrix_readiness"].detail
    assert "1/1 Visio fixture closed" in items["scene_matrix_readiness"].detail
    assert "3/3 dashboard warnings governed" in items["scene_matrix_readiness"].detail
    assert "0 unmanaged warnings" in items["scene_matrix_readiness"].detail
    assert "0 unreconciled readiness" in items["scene_matrix_readiness"].detail
    assert "0 ungoverned exceptions" in items["scene_matrix_readiness"].detail
    assert "0 dossier issues" in items["scene_matrix_readiness"].detail
    assert "0 unattributed traces" in items["scene_matrix_readiness"].detail
    assert "0 trace partition gaps" in items["scene_matrix_readiness"].detail
    assert "0 release projection gaps" in items["scene_matrix_readiness"].detail
    assert "0 subject continuity gaps" in items["scene_matrix_readiness"].detail
    assert "0 boundary envelope gaps" in items["scene_matrix_readiness"].detail
    assert "0 residual ratio gaps" in items["scene_matrix_readiness"].detail
    assert "10 residual ratio exit criteria" in items["scene_matrix_readiness"].detail
    assert "10 residual ratio receipts" in items["scene_matrix_readiness"].detail
    assert (
        "4/4 count/delivery receipts aligned"
        in items["scene_matrix_readiness"].detail
    )
