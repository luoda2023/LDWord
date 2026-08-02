import ast
import sys
from dataclasses import fields
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_matrix_dashboard import (
    SCENE_MATRIX_DASHBOARD_AMBIGUITY_CLARIFICATION_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_AMBIGUOUS_BOUNDARY_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_BOUNDARY_CAPABILITY_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_BUSINESS_CAPABILITY_MATRIX_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_CONTROL_RUNTIME_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_COUNT_PROFILES,
    SCENE_MATRIX_DASHBOARD_DELIVERY_EXECUTION_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_DELIVERY_PRESET_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_DIRECT_COUNT_FIELD_CLASSIFICATIONS,
    SCENE_MATRIX_DASHBOARD_EXTERNAL_HANDOFF_CONTRACT_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_FIXED_LAYOUT_PROFILE_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_GENERATED_COUNT_MARKER_IDS,
    SCENE_MATRIX_DASHBOARD_IMPORT_HANDOFF_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_LENS_IDS,
    SCENE_MATRIX_DASHBOARD_MATERIAL_REPAIR_FLOW_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_MATURITY_UPGRADE_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_REPORT_ARTIFACT_DRILLDOWN_COUNT_RENAMES,
    SCENE_MATRIX_DASHBOARD_SOURCE_IDS,
    SCENE_MATRIX_DASHBOARD_TASK_LEXICON_COUNT_PROFILE,
    _dashboard_prefixed_count_entries,
    _dashboard_profiled_count_entries,
    audit_scene_matrix_dashboard,
    build_scene_matrix_dashboard,
)
from src.config.scene_matrix_dashboard_models import (
    SceneMatrixDashboardReport,
)
from tests._scene_matrix_dashboard_assertions import (
    assert_expected_count_values,
)


@pytest.fixture(scope="module")
def dashboard_report():
    return build_scene_matrix_dashboard()


@pytest.fixture(scope="module")
def dashboard_payload(dashboard_report):
    return dashboard_report.to_payload()


@pytest.fixture(scope="module")
def dashboard_rows(dashboard_report):
    return {row.pack_id: row for row in dashboard_report.rows}


EXPECTED_SCENE_MATRIX_DASHBOARD_AGGREGATE_COUNTS: dict[str, int] = {
    "request_cell_count": 53,
    "request_cell_pack_link_count": 57,
    "high_frequency_completeness_ready_pack_count": 12,
    "task_lexicon_task_count": 30,
    "task_lexicon_phrase_count": 32,
    "task_lexicon_negative_task_count": 1,
    "task_lexicon_issue_count": 0,
    "ambiguous_boundary_count": 6,
    "ambiguous_boundary_pack_pair_count": 6,
    "ambiguous_boundary_issue_count": 0,
    "ambiguity_clarification_count": 6,
    "ambiguity_clarification_ready_count": 6,
    "ambiguity_clarification_candidate_route_count": 10,
    "ambiguity_clarification_candidate_pack_count": 7,
    "ambiguity_clarification_fixture_backed_count": 6,
    "ambiguity_clarification_issue_count": 0,
    "ambiguity_clarification_warning_count": 0,
    "import_handoff_count": 1,
    "import_handoff_ready_count": 1,
    "import_handoff_issue_count": 0,
    "input_source_family_count": 15,
    "input_source_ready_family_count": 14,
    "input_source_boundary_family_count": 1,
    "input_source_input_pack_count": 12,
    "input_source_ready_input_pack_count": 12,
    "input_source_accepted_format_count": 6,
    "input_source_structured_format_count": 4,
    "input_source_boundary_input_source_count": 4,
    "input_source_render_source_count": 8,
    "input_source_issue_count": 0,
    "input_source_warning_count": 5,
    "input_source_missing_source_evidence_count": 0,
    "family_count": 15,
    "family_fixture_depth_family_count": 15,
    "family_fixture_depth_p1_family_count": 11,
    "family_fixture_depth_p1_ready_count": 11,
    "family_fixture_depth_issue_count": 0,
    "sample_fixture_count": 42,
    "control_contract_count": 13,
    "control_runtime_control_count": 12,
    "control_runtime_ready_control_count": 12,
    "control_runtime_contract_link_count": 16,
    "control_runtime_issue_count": 0,
    "control_runtime_missing_source_evidence_count": 0,
    "word_risk_surface_count": 15,
    "object_preflight_action_target_count": 11,
    "object_preflight_action_ready_target_count": 11,
    "object_preflight_action_warning_target_count": 0,
    "object_preflight_action_high_risk_target_count": 5,
    "object_preflight_action_fixture_backed_target_count": 11,
    "object_preflight_action_blockable_target_count": 3,
    "object_preflight_action_skippable_target_count": 11,
    "object_preflight_action_family_count": 15,
    "object_preflight_action_ready_family_count": 14,
    "object_preflight_action_boundary_family_count": 1,
    "object_preflight_action_strict_family_count": 2,
    "object_preflight_action_family_with_fixture_count": 15,
    "object_preflight_action_issue_count": 0,
    "object_preflight_action_warning_count": 0,
    "user_journey_pack_count": 12,
    "user_journey_ready_pack_count": 12,
    "user_journey_warning_pack_count": 0,
    "user_journey_family_count": 15,
    "user_journey_ready_family_count": 15,
    "user_journey_warning_family_count": 0,
    "user_journey_path_count": 100,
    "user_journey_success_path_count": 31,
    "user_journey_degraded_path_count": 29,
    "user_journey_failure_path_count": 4,
    "user_journey_manual_boundary_path_count": 25,
    "user_journey_ambiguous_decision_path_count": 7,
    "user_journey_handoff_path_count": 1,
    "user_journey_negative_control_path_count": 3,
    "user_journey_issue_count": 0,
    "user_journey_warning_count": 0,
    "user_journey_missing_source_evidence_count": 0,
    "business_capability_matrix_count": 18,
    "business_capability_matrix_ready_count": 18,
    "business_capability_matrix_high_priority_count": 11,
    "business_capability_matrix_boundary_count": 7,
    "business_capability_matrix_manual_gate_count": 10,
    "business_capability_matrix_issue_count": 0,
    "business_capability_matrix_warning_count": 0,
    "boundary_capability_count": 6,
    "boundary_capability_ready_count": 6,
    "boundary_capability_professional_count": 5,
    "boundary_capability_import_ai_count": 1,
    "boundary_capability_fixture_count": 9,
    "boundary_capability_report_expectation_count": 19,
    "boundary_capability_ui_surface_count": 7,
    "boundary_capability_risk_domain_count": 9,
    "boundary_capability_decision_requirement_count": 4,
    "boundary_capability_external_receipt_count": 8,
    "boundary_capability_release_guardrail_count": 4,
    "boundary_capability_issue_count": 0,
    "boundary_capability_missing_source_evidence_count": 0,
    "plugin_boundary_gate_count": 4,
    "plugin_boundary_risk_domain_count": 14,
    "plugin_boundary_issue_count": 0,
    "external_handoff_contract_count": 6,
    "external_handoff_contract_ready_count": 6,
    "external_handoff_contract_pack_count": 2,
    "external_handoff_contract_family_count": 4,
    "external_handoff_contract_plugin_gate_count": 2,
    "external_handoff_contract_target_plugin_count": 6,
    "external_handoff_contract_risk_domain_count": 9,
    "external_handoff_contract_report_count": 19,
    "external_handoff_contract_ui_surface_count": 14,
    "external_handoff_contract_fixture_count": 8,
    "external_handoff_contract_status_state_count": 8,
    "external_handoff_contract_failure_policy_count": 4,
    "external_handoff_contract_issue_count": 0,
    "boundary_guarded_completion_subject_count": 6,
    "boundary_guarded_completion_ready_count": 6,
    "boundary_guarded_completion_pack_count": 2,
    "boundary_guarded_completion_family_count": 4,
    "boundary_guarded_completion_retained_gap_count": 6,
    "boundary_guarded_completion_plugin_gate_count": 2,
    "boundary_guarded_completion_target_plugin_count": 6,
    "boundary_guarded_completion_risk_domain_count": 11,
    "boundary_guarded_completion_issue_count": 0,
    "residual_warning_governance_warning_count": 10,
    "residual_warning_governance_managed_count": 10,
    "residual_warning_governance_plugin_manual_warning_count": 5,
    "residual_warning_governance_visio_fixture_closed_count": 1,
    "dashboard_warning_projection_governed_count": 3,
    "residual_warning_governance_unmanaged_warning_count": 0,
    "residual_warning_governance_issue_count": 0,
    "boundary_readiness_reconciliation_count": 15,
    "boundary_readiness_reconciliation_reconciled_count": 15,
    "boundary_readiness_reconciliation_not_applicable_count": 2,
    "boundary_readiness_reconciliation_issue_count": 0,
    "terminal_release_exception_count": 5,
    "terminal_release_exception_governed_count": 5,
    "terminal_release_exception_ungoverned_count": 0,
    "terminal_release_exception_managed_warning_count": 10,
    "terminal_release_exception_trace_count": 36,
    "terminal_release_exception_issue_count": 0,
    "boundary_subject_release_dossier_subject_count": 6,
    "boundary_subject_release_dossier_ready_count": 6,
    "boundary_subject_release_dossier_issue_count": 0,
    "non_subject_release_trace_attribution_count": 10,
    "non_subject_release_trace_attribution_ready_count": 10,
    "release_trace_partition_guard_partition_count": 3,
    "release_trace_partition_guard_ready_count": 3,
    "release_trace_partition_guard_terminal_trace_count": 36,
    "release_trace_partition_guard_subject_trace_count": 26,
    "release_trace_partition_guard_missing_trace_count": 0,
    "release_trace_partition_guard_overlap_trace_count": 0,
    "release_trace_partition_guard_extra_trace_count": 0,
    "release_trace_partition_guard_issue_count": 0,
    "release_projection_surface_parity_count": 13,
    "release_projection_surface_parity_ready_count": 13,
    "release_projection_surface_parity_dashboard_card_count": 13,
    "release_projection_surface_parity_drilldown_item_count": 13,
    "release_projection_surface_parity_issue_count": 0,
    "boundary_subject_release_continuity_subject_count": 6,
    "boundary_subject_release_continuity_ready_count": 6,
    "boundary_subject_release_continuity_mismatch_count": 0,
    "release_closure_ledger_stage_count": 13,
    "release_closure_ledger_ready_count": 13,
    "release_closure_ledger_stage_order_count": 13,
    "release_closure_ledger_upstream_dependency_count": 18,
    "release_closure_ledger_release_gate_check_count": 13,
    "release_closure_ledger_dashboard_card_count": 13,
    "release_closure_ledger_drilldown_item_count": 13,
    "release_closure_ledger_summary_projection_count": 13,
    "release_closure_ledger_issue_count": 0,
    "boundary_maturity_release_envelope_count": 6,
    "boundary_maturity_release_envelope_ready_count": 6,
    "retained_gap_enveloped_count": 6,
    "boundary_maturity_release_envelope_issue_count": 0,
    "retained_gap_exit_criteria_count": 6,
    "retained_gap_exit_criteria_release_allowed_count": 6,
    "retained_gap_exit_criteria_envelope_link_count": 6,
    "retained_gap_exit_criteria_handoff_link_count": 6,
    "retained_gap_exit_criteria_exit_signal_count": 14,
    "retained_gap_external_receipt_target_count": 8,
    "retained_gap_external_receipt_alignment_count": 6,
    "retained_gap_exit_criteria_issue_count": 0,
    "release_residual_ratio_ledger_count": 3,
    "release_residual_ratio_ledger_published_count": 3,
    "release_residual_ratio_ledger_non_full_count": 3,
    "release_residual_ratio_ledger_boundary_scope_alignment_count": 6,
    "release_residual_ratio_ledger_boundary_scope_link_count": 6,
    "release_residual_ratio_ledger_issue_count": 0,
    "release_residual_explanation_count": 14,
    "release_residual_explanation_covered_count": 14,
    "release_residual_explanation_mismatch_count": 0,
    "release_residual_explanation_issue_count": 0,
    "release_acceptance_certificate_count": 14,
    "release_acceptance_certificate_ready_count": 14,
    "release_acceptance_certificate_receipt_count": 2,
    "release_acceptance_certificate_source_evidence_count": 15,
    "release_acceptance_certificate_requirement_dimension_count": 10,
    "release_acceptance_certificate_issue_count": 0,
    "count_profile_profile_count": 20,
    "count_profile_referenced_profile_count": 17,
    "count_profile_rule_source_profile_count": 11,
    "count_profile_registry_only_profile_count": 2,
    "count_profile_rule_source_only_profile_count": 1,
    "count_profile_section_limit_profile_count": 1,
    "count_profile_unique_scope_count": 19,
    "count_profile_unique_primary_metric_count": 18,
    "count_profile_family_count": 15,
    "count_profile_ready_family_count": 14,
    "count_profile_boundary_family_count": 1,
    "count_profile_accounted_family_count": 15,
    "count_profile_count_profile_pack_count": 10,
    "count_profile_ready_count_profile_pack_count": 10,
    "count_profile_issue_count": 0,
    "count_profile_warning_count": 2,
    "material_schema_family_count": 15,
    "material_schema_material_family_count": 15,
    "material_schema_ready_material_family_count": 15,
    "material_schema_pack_count": 12,
    "material_schema_material_pack_count": 10,
    "material_schema_ready_material_pack_count": 10,
    "material_schema_schema_count": 23,
    "material_schema_referenced_schema_count": 22,
    "material_schema_registry_only_schema_count": 1,
    "material_schema_required_field_count": 41,
    "material_schema_required_asset_count": 6,
    "material_schema_issue_count": 0,
    "material_repair_flow_count": 11,
    "material_repair_flow_ready_count": 11,
    "material_repair_flow_capability_count": 33,
    "material_repair_flow_signal_count": 36,
    "material_repair_flow_target_type_count": 8,
    "material_repair_flow_runtime_surface_count": 21,
    "material_repair_flow_ui_surface_count": 16,
    "material_repair_flow_test_evidence_count": 25,
    "material_repair_flow_covered_pack_count": 10,
    "material_repair_flow_covered_family_count": 15,
    "material_repair_flow_issue_count": 0,
    "material_repair_flow_missing_source_evidence_count": 0,
    "fixed_layout_profile_channel_count": 12,
    "fixed_layout_profile_ready_channel_count": 12,
    "fixed_layout_profile_surface_count": 5,
    "fixed_layout_profile_ooxml_touchpoint_count": 11,
    "fixed_layout_profile_runtime_surface_count": 28,
    "fixed_layout_profile_ui_surface_count": 20,
    "fixed_layout_profile_report_surface_count": 15,
    "fixed_layout_profile_repair_target_type_count": 6,
    "fixed_layout_profile_test_evidence_count": 25,
    "fixed_layout_profile_covered_pack_count": 6,
    "fixed_layout_profile_covered_family_count": 6,
    "fixed_layout_profile_issue_count": 0,
    "fixed_layout_profile_missing_source_evidence_count": 0,
    "report_artifact_drilldown_channel_count": 10,
    "report_artifact_drilldown_ready_channel_count": 10,
    "report_artifact_drilldown_artifact_kind_count": 13,
    "report_artifact_drilldown_runtime_surface_count": 24,
    "report_artifact_drilldown_ui_surface_count": 18,
    "report_artifact_drilldown_report_surface_count": 21,
    "report_artifact_drilldown_repair_target_type_count": 3,
    "report_artifact_drilldown_test_evidence_count": 16,
    "report_artifact_drilldown_covered_pack_count": 12,
    "report_artifact_drilldown_covered_family_count": 15,
    "report_artifact_drilldown_issue_count": 0,
    "report_artifact_drilldown_missing_source_evidence_count": 0,
    "delivery_preset_family_count": 15,
    "delivery_preset_ready_family_count": 14,
    "delivery_preset_boundary_family_count": 1,
    "delivery_preset_accounted_family_count": 15,
    "delivery_preset_pack_count": 12,
    "delivery_preset_delivery_pack_count": 12,
    "delivery_preset_ready_delivery_pack_count": 11,
    "delivery_preset_boundary_delivery_pack_count": 1,
    "delivery_preset_accounted_delivery_pack_count": 12,
    "delivery_preset_unique_preset_count": 41,
    "delivery_preset_final_docx_preset_count": 35,
    "delivery_preset_compare_docx_preset_count": 17,
    "delivery_preset_report_only_preset_count": 18,
    "delivery_preset_material_package_preset_count": 15,
    "delivery_preset_content_visibility_rule_count": 18,
    "delivery_preset_issue_count": 0,
    "delivery_execution_channel_count": 10,
    "delivery_execution_ready_channel_count": 10,
    "delivery_execution_required_output_signal_count": 27,
    "delivery_execution_payload_key_count": 16,
    "delivery_execution_issue_count": 0,
    "delivery_execution_missing_source_evidence_count": 0,
    "formula_output_watermark_capability_count": 3,
    "formula_output_watermark_ready_capability_count": 3,
    "formula_output_watermark_family_count": 15,
    "formula_output_watermark_ready_family_count": 14,
    "formula_output_watermark_boundary_family_count": 1,
    "formula_output_watermark_accounted_family_count": 15,
    "formula_output_watermark_formula_family_count": 1,
    "formula_output_watermark_output_family_count": 15,
    "formula_output_watermark_watermark_family_count": 1,
    "formula_output_watermark_plugin_gate_count": 2,
    "formula_output_watermark_issue_count": 0,
    "product_readiness_subject_count": 27,
    "static_closed_but_not_green_count": 2,
    "static_closed_not_green_governed_count": 2,
    "maturity_upgrade_subject_count": 27,
    "maturity_upgrade_green_subject_count": 21,
    "maturity_upgrade_l5_blocked_subject_count": 6,
    "maturity_upgrade_l3_subject_count": 0,
    "maturity_upgrade_l4_subject_count": 0,
    "maturity_upgrade_boundary_subject_count": 6,
    "maturity_upgrade_gap_count": 6,
    "maturity_upgrade_gap_domain_count": 3,
    "maturity_upgrade_gap_domain_classified_count": 3,
    "maturity_upgrade_issue_count": 0,
}


def _assert_scene_matrix_dashboard_aggregate_counts(report, payload):
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
    assert_expected_count_values(
        payload["counts"],
        EXPECTED_SCENE_MATRIX_DASHBOARD_AGGREGATE_COUNTS,
    )
    assert (
        payload["counts"]["ambiguity_clarification_missing_source_evidence_count"] == 0
    )
    assert payload["counts"]["control_runtime_shared_component_count"] >= 15
    assert (
        payload["counts"]["object_preflight_action_manual_confirmation_target_count"]
        == 10
    )
    assert (
        payload["counts"]["object_preflight_action_missing_source_evidence_count"] == 0
    )
    assert (
        payload["counts"]["business_capability_matrix_high_priority_ready_count"] == 11
    )
    assert (
        payload["counts"]["business_capability_matrix_missing_journey_group_count"] == 0
    )
    assert (
        payload["counts"]["business_capability_matrix_missing_source_evidence_count"]
        == 0
    )
    assert (
        payload["counts"]["external_handoff_contract_missing_source_evidence_count"]
        == 0
    )
    assert payload["counts"]["boundary_guarded_completion_external_contract_count"] == 6
    assert (
        payload["counts"]["boundary_guarded_completion_boundary_capability_count"] == 6
    )
    assert (
        payload["counts"]["boundary_guarded_completion_excluded_core_claim_count"] == 14
    )
    assert (
        payload["counts"]["boundary_guarded_completion_missing_source_evidence_count"]
        == 0
    )
    assert (
        payload["counts"]["residual_warning_governance_input_source_warning_count"] == 5
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
    assert (
        payload["counts"][
            "residual_warning_governance_plugin_manual_managed_warning_count"
        ]
        == 5
    )
    assert (
        payload["counts"]["residual_warning_governance_reference_profile_warning_count"]
        == 2
    )
    assert (
        payload["counts"][
            "residual_warning_governance_reference_profile_managed_warning_count"
        ]
        == 2
    )
    assert (
        payload["counts"]["residual_warning_governance_visio_fixture_verified_count"]
        == 1
    )
    assert (
        payload["counts"]["residual_warning_governance_object_preflight_warning_count"]
        == 0
    )
    assert (
        payload["counts"]["boundary_readiness_reconciliation_unreconciled_count"] == 0
    )
    assert (
        payload["counts"]["boundary_readiness_reconciliation_readiness_delta_count"]
        == 5
    )
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
    assert payload["counts"]["terminal_release_exception_warning_projection_count"] == 3
    assert (
        payload["counts"]["terminal_release_exception_readiness_reconciliation_count"]
        == 15
    )
    assert (
        payload["counts"]["terminal_release_exception_boundary_guarded_maturity_count"]
        == 6
    )
    assert (
        payload["counts"]["terminal_release_exception_static_closed_boundary_count"]
        == 2
    )
    assert (
        payload["counts"]["terminal_release_exception_unique_source_trace_count"] == 31
    )
    assert (
        payload["counts"]["terminal_release_exception_linked_boundary_subject_count"]
        == 6
    )
    assert (
        payload["counts"]["boundary_subject_release_dossier_subject_trace_count"] == 26
    )
    assert (
        payload["counts"]["boundary_subject_release_dossier_unique_source_trace_count"]
        == 24
    )
    assert (
        payload["counts"][
            "boundary_subject_release_dossier_readiness_reconciliation_row_count"
        ]
        == 14
    )
    assert (
        payload["counts"]["non_subject_release_trace_attribution_unattributed_count"]
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
    assert (
        payload["counts"]["release_trace_partition_guard_non_subject_trace_count"] == 10
    )
    assert (
        payload["counts"]["release_trace_partition_guard_partitioned_trace_count"] == 36
    )
    assert (
        payload["counts"]["release_projection_surface_parity_release_gate_check_count"]
        == 13
    )
    assert (
        payload["counts"]["release_projection_surface_parity_summary_projection_count"]
        == 13
    )
    assert (
        payload["counts"]["boundary_subject_release_continuity_maturity_subject_count"]
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
    assert (
        payload["counts"]["release_closure_ledger_upstream_dependency_ready_count"]
        == 18
    )
    assert (
        payload["counts"][
            "boundary_maturity_release_envelope_l5_blocker_enveloped_count"
        ]
        == 6
    )
    assert (
        payload["counts"]["boundary_maturity_release_envelope_external_handoff_count"]
        == 6
    )
    assert (
        payload["counts"]["boundary_maturity_release_envelope_subject_continuity_count"]
        == 6
    )
    assert (
        payload["counts"]["boundary_maturity_release_envelope_retained_gap_count"] == 6
    )
    assert (
        payload["counts"]["retained_gap_exit_criteria_guarded_completion_link_count"]
        == 6
    )
    assert (
        payload["counts"]["retained_gap_exit_criteria_boundary_capability_link_count"]
        == 6
    )
    assert (
        payload["counts"]["retained_gap_exit_criteria_prohibited_core_claim_count"]
        == 14
    )
    assert (
        payload["counts"][
            "release_residual_ratio_ledger_readiness_reconciliation_link_count"
        ]
        == 11
    )
    assert (
        payload["counts"]["release_residual_ratio_ledger_release_envelope_link_count"]
        == 10
    )
    assert (
        payload["counts"]["release_residual_ratio_ledger_exit_criteria_link_count"]
        == 10
    )
    assert (
        payload["counts"]["release_residual_ratio_ledger_receipt_alignment_link_count"]
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
    assert (
        payload["counts"]["release_residual_explanation_missing_summary_marker_count"]
        == 0
    )
    assert payload["counts"]["release_acceptance_certificate_ready_receipt_count"] == 2
    assert (
        payload["counts"]["release_acceptance_certificate_expected_count_match_count"]
        == 14
    )
    assert (
        payload["counts"]["release_acceptance_certificate_ready_source_evidence_count"]
        == 15
    )
    assert (
        payload["counts"][
            "release_acceptance_certificate_ready_requirement_dimension_count"
        ]
        == 10
    )


def _assert_scene_matrix_dashboard_aggregate_cards(payload):
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
    assert "6/6 L5 receipts aligned" in cards_by_id["release_residual_ratios"]["detail"]
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
    assert (
        "6/6 L5 blockers enveloped"
        in cards_by_id["boundary_release_envelopes"]["detail"]
    )
    assert (
        "6/6 retained gaps enveloped"
        in cards_by_id["boundary_release_envelopes"]["detail"]
    )
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
    assert (
        "3/3 dashboard projected"
        in cards_by_id["residual_warning_governance"]["detail"]
    )
    assert (
        "3/3 dashboard warnings" in cards_by_id["terminal_release_exceptions"]["detail"]
    )
    assert "2/2 static-closed governed" in cards_by_id["readiness"]["detail"]
    assert "15/15 accounted" in cards_by_id["count_profiles"]["detail"]
    assert "15/15 families accounted" in cards_by_id["delivery_presets"]["detail"]
    assert "12/12 packs accounted" in cards_by_id["delivery_presets"]["detail"]


def _assert_scene_matrix_dashboard_aggregate_rows(report, rows):
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
    assert exam.delivery_content_visibility_rule_count == 24
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


def run_scene_matrix_dashboard_aggregate_coverage():
    report = build_scene_matrix_dashboard()
    payload = report.to_payload()
    rows = {row.pack_id: row for row in report.rows}

    _assert_scene_matrix_dashboard_aggregate_counts(report, payload)
    _assert_scene_matrix_dashboard_aggregate_cards(payload)
    _assert_scene_matrix_dashboard_aggregate_rows(report, rows)


def test_scene_matrix_dashboard_aggregate_counts(
    dashboard_report,
    dashboard_payload,
):
    _assert_scene_matrix_dashboard_aggregate_counts(
        dashboard_report,
        dashboard_payload,
    )


def test_scene_matrix_dashboard_count_payload_is_derived_from_model_fields(
    dashboard_report,
    dashboard_payload,
):
    derived_count_keys = (
        "plugin_boundary_pack_count",
        "manual_boundary_pack_count",
        "ambiguous_pack_count",
    )
    model_fields = fields(SceneMatrixDashboardReport)
    expected_count_keys = [
        field.name
        for field in model_fields
        if field.name.endswith("_count") and field.name != "total_count"
    ]
    model_field_names = {field.name for field in model_fields}
    sample_fixture_index = expected_count_keys.index("sample_fixture_count")
    expected_count_keys[sample_fixture_index + 1 : sample_fixture_index + 1] = (
        derived_count_keys
    )

    assert list(dashboard_payload["counts"]) == expected_count_keys
    assert set(derived_count_keys).isdisjoint(model_field_names)
    assert dashboard_payload["counts"]["plugin_boundary_pack_count"] == sum(
        1 for row in dashboard_report.rows if row.plugin_boundary
    )
    assert dashboard_payload["counts"]["manual_boundary_pack_count"] == sum(
        1 for row in dashboard_report.rows if row.manual_boundary_request_cell_count
    )
    assert dashboard_payload["counts"]["ambiguous_pack_count"] == sum(
        1 for row in dashboard_report.rows if row.ambiguous_request_cell_count
    )


def test_scene_matrix_dashboard_prefixed_count_entries_filter_model_fields():
    entries = _dashboard_prefixed_count_entries(
        "input_source",
        {
            "family_count": 15,
            "total_family_count": 99,
            "warning_count": 5,
        },
    )

    assert entries == {
        "input_source_family_count": 15,
        "input_source_warning_count": 5,
    }


def test_scene_matrix_dashboard_prefixed_count_entries_support_renames():
    entries = _dashboard_prefixed_count_entries(
        "material_repair_flow",
        {
            "flow_count": 11,
            "capability_count": 33,
            "source_evidence_count": 34,
        },
        renames=SCENE_MATRIX_DASHBOARD_MATERIAL_REPAIR_FLOW_COUNT_RENAMES,
    )

    assert entries == {
        "material_repair_flow_count": 11,
        "material_repair_flow_capability_count": 33,
    }

    with pytest.raises(KeyError):
        _dashboard_prefixed_count_entries(
            "material_repair_flow",
            {"flow_count": 11},
            renames={"flow_count": "material_repair_flow_missing_count"},
        )


def test_scene_matrix_dashboard_profiled_count_entries_require_profile_fields():
    entries = _dashboard_profiled_count_entries(
        SCENE_MATRIX_DASHBOARD_TASK_LEXICON_COUNT_PROFILE,
        {
            "task_count": 30,
            "phrase_count": 32,
            "negative_task_count": 1,
            "issue_count": 0,
            "missing_source_evidence_count": 99,
        },
    )

    assert entries == {
        "task_lexicon_task_count": 30,
        "task_lexicon_phrase_count": 32,
        "task_lexicon_negative_task_count": 1,
        "task_lexicon_issue_count": 0,
    }

    with pytest.raises(KeyError):
        _dashboard_profiled_count_entries(
            SCENE_MATRIX_DASHBOARD_TASK_LEXICON_COUNT_PROFILE,
            {
                "task_count": 30,
                "phrase_count": 32,
                "negative_task_count": 1,
            },
        )


def test_scene_matrix_dashboard_generated_count_markers_are_model_fields():
    model_field_names = {field.name for field in fields(SceneMatrixDashboardReport)}
    profile_count_ids = {
        count_id
        for profile in SCENE_MATRIX_DASHBOARD_COUNT_PROFILES
        for count_id in profile.dashboard_count_ids
    }
    profile_rename_count_ids = {
        count_id
        for profile in SCENE_MATRIX_DASHBOARD_COUNT_PROFILES
        for count_id in (profile.renames or {}).values()
    }
    rename_specs = (
        SCENE_MATRIX_DASHBOARD_AMBIGUOUS_BOUNDARY_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_AMBIGUITY_CLARIFICATION_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_IMPORT_HANDOFF_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_CONTROL_RUNTIME_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_MATURITY_UPGRADE_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_BUSINESS_CAPABILITY_MATRIX_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_BOUNDARY_CAPABILITY_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_EXTERNAL_HANDOFF_CONTRACT_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_MATERIAL_REPAIR_FLOW_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_FIXED_LAYOUT_PROFILE_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_REPORT_ARTIFACT_DRILLDOWN_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_DELIVERY_EXECUTION_COUNT_RENAMES,
        SCENE_MATRIX_DASHBOARD_DELIVERY_PRESET_COUNT_RENAMES,
    )

    assert len(SCENE_MATRIX_DASHBOARD_GENERATED_COUNT_MARKER_IDS) == len(
        set(SCENE_MATRIX_DASHBOARD_GENERATED_COUNT_MARKER_IDS)
    )
    assert set(SCENE_MATRIX_DASHBOARD_GENERATED_COUNT_MARKER_IDS) <= (model_field_names)
    assert profile_count_ids <= set(SCENE_MATRIX_DASHBOARD_GENERATED_COUNT_MARKER_IDS)
    assert profile_count_ids <= model_field_names
    assert profile_rename_count_ids <= profile_count_ids
    assert {
        dashboard_count_id
        for rename_spec in rename_specs
        for dashboard_count_id in rename_spec.values()
    } <= model_field_names


def test_scene_matrix_dashboard_direct_count_kwargs_are_classified():
    source_path = ROOT / "src" / "config" / "scene_matrix_dashboard.py"
    source_tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
    direct_count_kwargs: set[str] = set()
    for node in ast.walk(source_tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", "") == "SceneMatrixDashboardReport"
        ):
            direct_count_kwargs.update(
                keyword.arg
                for keyword in node.keywords
                if keyword.arg and keyword.arg.endswith("_count")
            )

    model_field_names = {field.name for field in fields(SceneMatrixDashboardReport)}
    classified_count_ids = set(
        SCENE_MATRIX_DASHBOARD_DIRECT_COUNT_FIELD_CLASSIFICATIONS
    )

    assert direct_count_kwargs == classified_count_ids
    assert classified_count_ids <= model_field_names
    assert set(SCENE_MATRIX_DASHBOARD_GENERATED_COUNT_MARKER_IDS).isdisjoint(
        classified_count_ids
    )


def test_scene_matrix_dashboard_aggregate_cards(dashboard_payload):
    _assert_scene_matrix_dashboard_aggregate_cards(dashboard_payload)


def test_scene_matrix_dashboard_aggregate_rows(
    dashboard_report,
    dashboard_rows,
):
    _assert_scene_matrix_dashboard_aggregate_rows(
        dashboard_report,
        dashboard_rows,
    )
