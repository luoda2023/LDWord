"""Payload models for the scene matrix dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.scene_matrix_dashboard_lenses import SceneMatrixDashboardLens


@dataclass(frozen=True, slots=True)
class SceneMatrixDashboardIssue:
    scope_type: str
    scope_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneMatrixDashboardCard:
    card_id: str
    label: str
    value: str
    detail: str
    variant: str
    source_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "card_id": self.card_id,
            "label": self.label,
            "value": self.value,
            "detail": self.detail,
            "variant": self.variant,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneMatrixDashboardRow:
    pack_id: str
    label: str
    product_readiness_level: str
    static_closure_level: str
    product_gap_count: int
    plugin_boundary: bool
    boundary: str
    boundary_signal_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    family_count: int
    family_status_counts: tuple[tuple[str, int], ...]
    family_issue_count: int
    family_warning_count: int
    family_request_cell_count: int
    material_schema_ids: tuple[str, ...]
    material_schema_count: int
    material_required_field_count: int
    material_required_asset_count: int
    material_schema_issue_count: int
    material_repair_flow_count: int
    material_repair_flow_issue_count: int
    fixed_layout_profile_channel_count: int
    fixed_layout_profile_issue_count: int
    report_artifact_drilldown_channel_count: int
    report_artifact_drilldown_issue_count: int
    delivery_preset_ids: tuple[str, ...]
    delivery_preset_count: int
    delivery_compare_preset_count: int
    delivery_report_only_preset_count: int
    delivery_material_package_preset_count: int
    delivery_structured_intermediate_preset_count: int
    delivery_content_visibility_rule_count: int
    delivery_preset_issue_count: int
    delivery_execution_channel_count: int
    delivery_execution_issue_count: int
    input_formats: tuple[str, ...]
    input_structured_formats: tuple[str, ...]
    input_render_source_ids: tuple[str, ...]
    input_boundary_source_ids: tuple[str, ...]
    input_source_issue_count: int
    request_cell_count: int
    matched_request_cell_count: int
    ambiguous_request_cell_count: int
    manual_boundary_request_cell_count: int
    negative_request_cell_count: int
    request_cell_sample_ids: tuple[str, ...]
    ambiguity_clarification_count: int
    ambiguity_clarification_issue_count: int
    user_journey_path_type_ids: tuple[str, ...]
    user_journey_path_count: int
    user_journey_issue_count: int
    user_journey_warning_count: int
    business_capability_ids: tuple[str, ...]
    business_capability_count: int
    business_capability_issue_count: int
    business_capability_warning_count: int
    capability_axis_ids: tuple[str, ...]
    workflow_archetype_ids: tuple[str, ...]
    word_risk_surface_ids: tuple[str, ...]
    word_risk_issue_count: int
    preflight_word_risk_surface_count: int
    object_preflight_target_ids: tuple[str, ...]
    object_preflight_action_count: int
    object_preflight_action_issue_count: int
    object_preflight_action_warning_count: int
    sample_fixture_count: int
    sample_fixture_ids: tuple[str, ...]
    report_anchor_count: int
    control_contract_count: int
    control_contract_issue_count: int
    control_runtime_control_count: int
    control_runtime_issue_count: int
    dashboard_lens_ids: tuple[str, ...]
    missing_lens_ids: tuple[str, ...]
    drilldown_source_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]
    warning_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        if self.issue_ids:
            return "blocked"
        if self.warning_ids:
            return "needs_depth"
        return "ready"

    def to_payload(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "label": self.label,
            "status": self.status,
            "product_readiness_level": self.product_readiness_level,
            "static_closure_level": self.static_closure_level,
            "product_gap_count": self.product_gap_count,
            "plugin_boundary": self.plugin_boundary,
            "boundary": self.boundary,
            "boundary_signal_ids": list(self.boundary_signal_ids),
            "family_ids": list(self.family_ids),
            "family_count": self.family_count,
            "family_status_counts": [
                {"status": status, "count": count}
                for status, count in self.family_status_counts
            ],
            "family_issue_count": self.family_issue_count,
            "family_warning_count": self.family_warning_count,
            "family_request_cell_count": self.family_request_cell_count,
            "material_schema_ids": list(self.material_schema_ids),
            "material_schema_count": self.material_schema_count,
            "material_required_field_count": self.material_required_field_count,
            "material_required_asset_count": self.material_required_asset_count,
            "material_schema_issue_count": self.material_schema_issue_count,
            "material_repair_flow_count": self.material_repair_flow_count,
            "material_repair_flow_issue_count": (
                self.material_repair_flow_issue_count
            ),
            "fixed_layout_profile_channel_count": (
                self.fixed_layout_profile_channel_count
            ),
            "fixed_layout_profile_issue_count": (
                self.fixed_layout_profile_issue_count
            ),
            "report_artifact_drilldown_channel_count": (
                self.report_artifact_drilldown_channel_count
            ),
            "report_artifact_drilldown_issue_count": (
                self.report_artifact_drilldown_issue_count
            ),
            "delivery_preset_ids": list(self.delivery_preset_ids),
            "delivery_preset_count": self.delivery_preset_count,
            "delivery_compare_preset_count": self.delivery_compare_preset_count,
            "delivery_report_only_preset_count": self.delivery_report_only_preset_count,
            "delivery_material_package_preset_count": (
                self.delivery_material_package_preset_count
            ),
            "delivery_structured_intermediate_preset_count": (
                self.delivery_structured_intermediate_preset_count
            ),
            "delivery_content_visibility_rule_count": (
                self.delivery_content_visibility_rule_count
            ),
            "delivery_preset_issue_count": self.delivery_preset_issue_count,
            "delivery_execution_channel_count": (
                self.delivery_execution_channel_count
            ),
            "delivery_execution_issue_count": self.delivery_execution_issue_count,
            "input_formats": list(self.input_formats),
            "input_structured_formats": list(self.input_structured_formats),
            "input_render_source_ids": list(self.input_render_source_ids),
            "input_boundary_source_ids": list(self.input_boundary_source_ids),
            "input_source_issue_count": self.input_source_issue_count,
            "request_cell_count": self.request_cell_count,
            "matched_request_cell_count": self.matched_request_cell_count,
            "ambiguous_request_cell_count": self.ambiguous_request_cell_count,
            "manual_boundary_request_cell_count": (
                self.manual_boundary_request_cell_count
            ),
            "negative_request_cell_count": self.negative_request_cell_count,
            "request_cell_sample_ids": list(self.request_cell_sample_ids),
            "ambiguity_clarification_count": self.ambiguity_clarification_count,
            "ambiguity_clarification_issue_count": (
                self.ambiguity_clarification_issue_count
            ),
            "user_journey_path_type_ids": list(self.user_journey_path_type_ids),
            "user_journey_path_count": self.user_journey_path_count,
            "user_journey_issue_count": self.user_journey_issue_count,
            "user_journey_warning_count": self.user_journey_warning_count,
            "business_capability_ids": list(self.business_capability_ids),
            "business_capability_count": self.business_capability_count,
            "business_capability_issue_count": self.business_capability_issue_count,
            "business_capability_warning_count": (
                self.business_capability_warning_count
            ),
            "capability_axis_ids": list(self.capability_axis_ids),
            "workflow_archetype_ids": list(self.workflow_archetype_ids),
            "word_risk_surface_ids": list(self.word_risk_surface_ids),
            "word_risk_issue_count": self.word_risk_issue_count,
            "preflight_word_risk_surface_count": self.preflight_word_risk_surface_count,
            "object_preflight_target_ids": list(self.object_preflight_target_ids),
            "object_preflight_action_count": self.object_preflight_action_count,
            "object_preflight_action_issue_count": (
                self.object_preflight_action_issue_count
            ),
            "object_preflight_action_warning_count": (
                self.object_preflight_action_warning_count
            ),
            "sample_fixture_count": self.sample_fixture_count,
            "sample_fixture_ids": list(self.sample_fixture_ids),
            "report_anchor_count": self.report_anchor_count,
            "control_contract_count": self.control_contract_count,
            "control_contract_issue_count": self.control_contract_issue_count,
            "control_runtime_control_count": self.control_runtime_control_count,
            "control_runtime_issue_count": self.control_runtime_issue_count,
            "dashboard_lens_ids": list(self.dashboard_lens_ids),
            "missing_lens_ids": list(self.missing_lens_ids),
            "drilldown_source_ids": list(self.drilldown_source_ids),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneMatrixDashboardReport:
    rows: tuple[SceneMatrixDashboardRow, ...]
    issues: tuple[SceneMatrixDashboardIssue, ...]
    warnings: tuple[SceneMatrixDashboardIssue, ...]
    cards: tuple[SceneMatrixDashboardCard, ...]
    lenses: tuple[SceneMatrixDashboardLens, ...]
    source_ids: tuple[str, ...]
    total_count: int
    pack_filter: str = ""
    family_filter: str = ""
    readiness_filter: str = ""
    boundary_filter: str = ""
    status_filter: str = ""
    request_cell_count: int = 0
    request_cell_pack_link_count: int = 0
    high_frequency_completeness_ready_pack_count: int = 0
    task_lexicon_task_count: int = 0
    task_lexicon_phrase_count: int = 0
    task_lexicon_negative_task_count: int = 0
    task_lexicon_issue_count: int = 0
    ambiguous_boundary_count: int = 0
    ambiguous_boundary_pack_pair_count: int = 0
    ambiguous_boundary_issue_count: int = 0
    ambiguity_clarification_count: int = 0
    ambiguity_clarification_ready_count: int = 0
    ambiguity_clarification_candidate_route_count: int = 0
    ambiguity_clarification_candidate_pack_count: int = 0
    ambiguity_clarification_fixture_backed_count: int = 0
    ambiguity_clarification_issue_count: int = 0
    ambiguity_clarification_warning_count: int = 0
    ambiguity_clarification_missing_source_evidence_count: int = 0
    import_handoff_count: int = 0
    import_handoff_ready_count: int = 0
    import_handoff_issue_count: int = 0
    input_source_family_count: int = 0
    input_source_ready_family_count: int = 0
    input_source_boundary_family_count: int = 0
    input_source_pack_count: int = 0
    input_source_input_pack_count: int = 0
    input_source_ready_input_pack_count: int = 0
    input_source_accepted_format_count: int = 0
    input_source_structured_format_count: int = 0
    input_source_material_required_family_count: int = 0
    input_source_markdown_enabled_family_count: int = 0
    input_source_latex_fragment_family_count: int = 0
    input_source_render_source_count: int = 0
    input_source_target_template_count: int = 0
    input_source_boundary_input_source_count: int = 0
    input_source_format_count: int = 0
    input_source_issue_count: int = 0
    input_source_warning_count: int = 0
    input_source_missing_source_evidence_count: int = 0
    family_count: int = 0
    family_fixture_depth_family_count: int = 0
    family_fixture_depth_p1_family_count: int = 0
    family_fixture_depth_p1_ready_count: int = 0
    family_fixture_depth_issue_count: int = 0
    sample_fixture_count: int = 0
    control_contract_count: int = 0
    control_runtime_control_count: int = 0
    control_runtime_ready_control_count: int = 0
    control_runtime_contract_link_count: int = 0
    control_runtime_scene_surface_count: int = 0
    control_runtime_template_surface_count: int = 0
    control_runtime_shared_component_count: int = 0
    control_runtime_consumer_count: int = 0
    control_runtime_issue_count: int = 0
    control_runtime_missing_source_evidence_count: int = 0
    word_risk_surface_count: int = 0
    object_preflight_action_target_count: int = 0
    object_preflight_action_ready_target_count: int = 0
    object_preflight_action_warning_target_count: int = 0
    object_preflight_action_high_risk_target_count: int = 0
    object_preflight_action_fixture_backed_target_count: int = 0
    object_preflight_action_blockable_target_count: int = 0
    object_preflight_action_skippable_target_count: int = 0
    object_preflight_action_manual_confirmation_target_count: int = 0
    object_preflight_action_family_count: int = 0
    object_preflight_action_ready_family_count: int = 0
    object_preflight_action_boundary_family_count: int = 0
    object_preflight_action_strict_family_count: int = 0
    object_preflight_action_family_with_fixture_count: int = 0
    object_preflight_action_issue_count: int = 0
    object_preflight_action_warning_count: int = 0
    object_preflight_action_missing_source_evidence_count: int = 0
    user_journey_pack_count: int = 0
    user_journey_ready_pack_count: int = 0
    user_journey_warning_pack_count: int = 0
    user_journey_family_count: int = 0
    user_journey_ready_family_count: int = 0
    user_journey_warning_family_count: int = 0
    user_journey_path_count: int = 0
    user_journey_success_path_count: int = 0
    user_journey_degraded_path_count: int = 0
    user_journey_failure_path_count: int = 0
    user_journey_manual_boundary_path_count: int = 0
    user_journey_ambiguous_decision_path_count: int = 0
    user_journey_handoff_path_count: int = 0
    user_journey_negative_control_path_count: int = 0
    user_journey_issue_count: int = 0
    user_journey_warning_count: int = 0
    user_journey_missing_source_evidence_count: int = 0
    business_capability_matrix_count: int = 0
    business_capability_matrix_ready_count: int = 0
    business_capability_matrix_high_priority_count: int = 0
    business_capability_matrix_high_priority_ready_count: int = 0
    business_capability_matrix_boundary_count: int = 0
    business_capability_matrix_manual_gate_count: int = 0
    business_capability_matrix_missing_journey_group_count: int = 0
    business_capability_matrix_issue_count: int = 0
    business_capability_matrix_warning_count: int = 0
    business_capability_matrix_missing_source_evidence_count: int = 0
    boundary_capability_count: int = 0
    boundary_capability_ready_count: int = 0
    boundary_capability_professional_count: int = 0
    boundary_capability_import_ai_count: int = 0
    boundary_capability_fixture_count: int = 0
    boundary_capability_report_expectation_count: int = 0
    boundary_capability_ui_surface_count: int = 0
    boundary_capability_risk_domain_count: int = 0
    boundary_capability_decision_requirement_count: int = 0
    boundary_capability_external_receipt_count: int = 0
    boundary_capability_release_guardrail_count: int = 0
    boundary_capability_issue_count: int = 0
    boundary_capability_missing_source_evidence_count: int = 0
    plugin_boundary_gate_count: int = 0
    plugin_boundary_risk_domain_count: int = 0
    plugin_boundary_issue_count: int = 0
    external_handoff_contract_count: int = 0
    external_handoff_contract_ready_count: int = 0
    external_handoff_contract_pack_count: int = 0
    external_handoff_contract_family_count: int = 0
    external_handoff_contract_plugin_gate_count: int = 0
    external_handoff_contract_target_plugin_count: int = 0
    external_handoff_contract_risk_domain_count: int = 0
    external_handoff_contract_report_count: int = 0
    external_handoff_contract_ui_surface_count: int = 0
    external_handoff_contract_fixture_count: int = 0
    external_handoff_contract_status_state_count: int = 0
    external_handoff_contract_failure_policy_count: int = 0
    external_handoff_contract_issue_count: int = 0
    external_handoff_contract_missing_source_evidence_count: int = 0
    boundary_guarded_completion_subject_count: int = 0
    boundary_guarded_completion_ready_count: int = 0
    boundary_guarded_completion_pack_count: int = 0
    boundary_guarded_completion_family_count: int = 0
    boundary_guarded_completion_retained_gap_count: int = 0
    boundary_guarded_completion_external_contract_count: int = 0
    boundary_guarded_completion_boundary_capability_count: int = 0
    boundary_guarded_completion_plugin_gate_count: int = 0
    boundary_guarded_completion_target_plugin_count: int = 0
    boundary_guarded_completion_risk_domain_count: int = 0
    boundary_guarded_completion_excluded_core_claim_count: int = 0
    boundary_guarded_completion_issue_count: int = 0
    boundary_guarded_completion_missing_source_evidence_count: int = 0
    residual_warning_governance_warning_count: int = 0
    residual_warning_governance_managed_count: int = 0
    residual_warning_governance_input_source_warning_count: int = 0
    residual_warning_governance_input_source_managed_warning_count: int = 0
    residual_warning_governance_count_profile_warning_count: int = 0
    residual_warning_governance_count_profile_managed_warning_count: int = 0
    residual_warning_governance_dashboard_projection_warning_count: int = 0
    dashboard_warning_projection_governed_count: int = 0
    residual_warning_governance_plugin_manual_warning_count: int = 0
    residual_warning_governance_plugin_manual_managed_warning_count: int = 0
    residual_warning_governance_reference_profile_warning_count: int = 0
    residual_warning_governance_reference_profile_managed_warning_count: int = 0
    residual_warning_governance_object_preflight_warning_count: int = 0
    residual_warning_governance_visio_fixture_closed_count: int = 0
    residual_warning_governance_visio_fixture_verified_count: int = 0
    residual_warning_governance_unmanaged_warning_count: int = 0
    residual_warning_governance_issue_count: int = 0
    residual_warning_governance_missing_source_evidence_count: int = 0
    boundary_readiness_reconciliation_count: int = 0
    boundary_readiness_reconciliation_reconciled_count: int = 0
    boundary_readiness_reconciliation_unreconciled_count: int = 0
    boundary_readiness_reconciliation_readiness_delta_count: int = 0
    boundary_readiness_reconciliation_not_applicable_count: int = 0
    boundary_readiness_reconciliation_static_closed_boundary_count: int = 0
    boundary_readiness_reconciliation_maturity_boundary_guarded_count: int = 0
    boundary_readiness_reconciliation_boundary_subject_count: int = 0
    boundary_readiness_reconciliation_issue_count: int = 0
    boundary_readiness_reconciliation_missing_source_evidence_count: int = 0
    terminal_release_exception_count: int = 0
    terminal_release_exception_governed_count: int = 0
    terminal_release_exception_ungoverned_count: int = 0
    terminal_release_exception_managed_warning_count: int = 0
    terminal_release_exception_warning_projection_count: int = 0
    terminal_release_exception_readiness_reconciliation_count: int = 0
    terminal_release_exception_boundary_guarded_maturity_count: int = 0
    terminal_release_exception_static_closed_boundary_count: int = 0
    terminal_release_exception_trace_count: int = 0
    terminal_release_exception_unique_source_trace_count: int = 0
    terminal_release_exception_linked_boundary_subject_count: int = 0
    terminal_release_exception_issue_count: int = 0
    terminal_release_exception_missing_source_evidence_count: int = 0
    boundary_subject_release_dossier_subject_count: int = 0
    boundary_subject_release_dossier_ready_count: int = 0
    boundary_subject_release_dossier_pack_subject_count: int = 0
    boundary_subject_release_dossier_family_subject_count: int = 0
    boundary_subject_release_dossier_subject_trace_count: int = 0
    boundary_subject_release_dossier_unique_source_trace_count: int = 0
    boundary_subject_release_dossier_readiness_reconciliation_row_count: int = 0
    boundary_subject_release_dossier_terminal_exception_count: int = 0
    boundary_subject_release_dossier_issue_count: int = 0
    boundary_subject_release_dossier_missing_source_evidence_count: int = 0
    non_subject_release_trace_attribution_count: int = 0
    non_subject_release_trace_attribution_ready_count: int = 0
    non_subject_release_trace_attribution_unattributed_count: int = 0
    non_subject_release_trace_attribution_dashboard_projection_count: int = 0
    non_subject_release_trace_attribution_registry_only_profile_count: int = 0
    non_subject_release_trace_attribution_plugin_manual_pack_count: int = 0
    non_subject_release_trace_attribution_generic_not_applicable_count: int = 0
    non_subject_release_trace_attribution_issue_count: int = 0
    non_subject_release_trace_attribution_missing_source_evidence_count: int = 0
    release_trace_partition_guard_partition_count: int = 0
    release_trace_partition_guard_ready_count: int = 0
    release_trace_partition_guard_terminal_trace_count: int = 0
    release_trace_partition_guard_subject_trace_count: int = 0
    release_trace_partition_guard_non_subject_trace_count: int = 0
    release_trace_partition_guard_partitioned_trace_count: int = 0
    release_trace_partition_guard_missing_trace_count: int = 0
    release_trace_partition_guard_overlap_trace_count: int = 0
    release_trace_partition_guard_extra_trace_count: int = 0
    release_trace_partition_guard_issue_count: int = 0
    release_trace_partition_guard_missing_source_evidence_count: int = 0
    release_projection_surface_parity_count: int = 0
    release_projection_surface_parity_ready_count: int = 0
    release_projection_surface_parity_release_gate_check_count: int = 0
    release_projection_surface_parity_dashboard_source_count: int = 0
    release_projection_surface_parity_dashboard_card_count: int = 0
    release_projection_surface_parity_drilldown_item_count: int = 0
    release_projection_surface_parity_summary_projection_count: int = 0
    release_projection_surface_parity_export_script_count: int = 0
    release_projection_surface_parity_workflow_test_count: int = 0
    release_projection_surface_parity_closure_doc_count: int = 0
    release_projection_surface_parity_issue_count: int = 0
    release_projection_surface_parity_missing_source_evidence_count: int = 0
    boundary_subject_release_continuity_subject_count: int = 0
    boundary_subject_release_continuity_ready_count: int = 0
    boundary_subject_release_continuity_maturity_subject_count: int = 0
    boundary_subject_release_continuity_guarded_completion_subject_count: int = 0
    boundary_subject_release_continuity_readiness_reconciliation_subject_count: int = 0
    boundary_subject_release_continuity_terminal_release_subject_count: int = 0
    boundary_subject_release_continuity_dossier_count: int = 0
    boundary_subject_release_continuity_readiness_row_count: int = 0
    boundary_subject_release_continuity_terminal_trace_count: int = 0
    boundary_subject_release_continuity_dossier_trace_count: int = 0
    boundary_subject_release_continuity_mismatch_count: int = 0
    boundary_subject_release_continuity_issue_count: int = 0
    boundary_subject_release_continuity_missing_source_evidence_count: int = 0
    release_closure_ledger_stage_count: int = 0
    release_closure_ledger_ready_count: int = 0
    release_closure_ledger_stage_order_count: int = 0
    release_closure_ledger_upstream_dependency_count: int = 0
    release_closure_ledger_upstream_dependency_ready_count: int = 0
    release_closure_ledger_release_gate_check_count: int = 0
    release_closure_ledger_dashboard_source_count: int = 0
    release_closure_ledger_dashboard_card_count: int = 0
    release_closure_ledger_drilldown_item_count: int = 0
    release_closure_ledger_summary_projection_count: int = 0
    release_closure_ledger_export_script_count: int = 0
    release_closure_ledger_workflow_test_count: int = 0
    release_closure_ledger_closure_doc_count: int = 0
    release_closure_ledger_issue_count: int = 0
    release_closure_ledger_missing_source_evidence_count: int = 0
    boundary_maturity_release_envelope_count: int = 0
    boundary_maturity_release_envelope_ready_count: int = 0
    boundary_maturity_release_envelope_l5_blocker_enveloped_count: int = 0
    boundary_maturity_release_envelope_maturity_boundary_count: int = 0
    boundary_maturity_release_envelope_external_handoff_count: int = 0
    boundary_maturity_release_envelope_guarded_completion_count: int = 0
    boundary_maturity_release_envelope_readiness_reconciliation_count: int = 0
    boundary_maturity_release_envelope_terminal_trace_count: int = 0
    boundary_maturity_release_envelope_release_dossier_count: int = 0
    boundary_maturity_release_envelope_subject_continuity_count: int = 0
    boundary_maturity_release_envelope_retained_gap_count: int = 0
    retained_gap_enveloped_count: int = 0
    boundary_maturity_release_envelope_issue_count: int = 0
    boundary_maturity_release_envelope_missing_source_evidence_count: int = 0
    retained_gap_exit_criteria_count: int = 0
    retained_gap_exit_criteria_release_allowed_count: int = 0
    retained_gap_exit_criteria_envelope_link_count: int = 0
    retained_gap_exit_criteria_handoff_link_count: int = 0
    retained_gap_exit_criteria_guarded_completion_link_count: int = 0
    retained_gap_exit_criteria_boundary_capability_link_count: int = 0
    retained_gap_exit_criteria_exit_signal_count: int = 0
    retained_gap_external_receipt_target_count: int = 0
    retained_gap_external_receipt_alignment_count: int = 0
    retained_gap_exit_criteria_prohibited_core_claim_count: int = 0
    retained_gap_exit_criteria_issue_count: int = 0
    retained_gap_exit_criteria_missing_source_evidence_count: int = 0
    release_residual_ratio_ledger_count: int = 0
    release_residual_ratio_ledger_published_count: int = 0
    release_residual_ratio_ledger_non_full_count: int = 0
    release_residual_ratio_ledger_readiness_reconciliation_link_count: int = 0
    release_residual_ratio_ledger_terminal_exception_link_count: int = 0
    release_residual_ratio_ledger_release_envelope_link_count: int = 0
    release_residual_ratio_ledger_exit_criteria_link_count: int = 0
    release_residual_ratio_ledger_receipt_alignment_link_count: int = 0
    release_residual_ratio_ledger_count_delivery_boundary_alignment_count: int = 0
    release_residual_ratio_ledger_count_delivery_boundary_link_count: int = 0
    release_residual_ratio_ledger_count_delivery_receipt_alignment_count: int = 0
    release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count: int = 0
    release_residual_ratio_ledger_maturity_l5_blocker_alignment_count: int = 0
    release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count: int = 0
    release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count: int = 0
    release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count: int = 0
    release_residual_ratio_ledger_boundary_scope_alignment_count: int = 0
    release_residual_ratio_ledger_boundary_scope_link_count: int = 0
    release_residual_ratio_ledger_issue_count: int = 0
    release_residual_ratio_ledger_missing_source_evidence_count: int = 0
    release_residual_explanation_count: int = 0
    release_residual_explanation_covered_count: int = 0
    release_residual_explanation_mismatch_count: int = 0
    release_residual_explanation_missing_summary_marker_count: int = 0
    release_residual_explanation_issue_count: int = 0
    release_residual_explanation_missing_source_evidence_count: int = 0
    release_acceptance_certificate_count: int = 0
    release_acceptance_certificate_ready_count: int = 0
    release_acceptance_certificate_receipt_count: int = 0
    release_acceptance_certificate_ready_receipt_count: int = 0
    release_acceptance_certificate_component_report_count: int = 0
    release_acceptance_certificate_requirement_dimension_count: int = 0
    release_acceptance_certificate_ready_requirement_dimension_count: int = 0
    release_acceptance_certificate_expected_count_match_count: int = 0
    release_acceptance_certificate_source_evidence_count: int = 0
    release_acceptance_certificate_ready_source_evidence_count: int = 0
    release_acceptance_certificate_issue_count: int = 0
    release_acceptance_certificate_missing_source_evidence_count: int = 0
    material_schema_family_count: int = 0
    material_schema_material_family_count: int = 0
    material_schema_ready_material_family_count: int = 0
    material_schema_pack_count: int = 0
    material_schema_material_pack_count: int = 0
    material_schema_ready_material_pack_count: int = 0
    material_schema_schema_count: int = 0
    material_schema_referenced_schema_count: int = 0
    material_schema_registry_only_schema_count: int = 0
    material_schema_required_field_count: int = 0
    material_schema_required_asset_count: int = 0
    material_schema_issue_count: int = 0
    material_repair_flow_count: int = 0
    material_repair_flow_ready_count: int = 0
    material_repair_flow_capability_count: int = 0
    material_repair_flow_signal_count: int = 0
    material_repair_flow_target_type_count: int = 0
    material_repair_flow_runtime_surface_count: int = 0
    material_repair_flow_ui_surface_count: int = 0
    material_repair_flow_test_evidence_count: int = 0
    material_repair_flow_covered_pack_count: int = 0
    material_repair_flow_covered_family_count: int = 0
    material_repair_flow_issue_count: int = 0
    material_repair_flow_missing_source_evidence_count: int = 0
    fixed_layout_profile_channel_count: int = 0
    fixed_layout_profile_ready_channel_count: int = 0
    fixed_layout_profile_surface_count: int = 0
    fixed_layout_profile_ooxml_touchpoint_count: int = 0
    fixed_layout_profile_runtime_surface_count: int = 0
    fixed_layout_profile_ui_surface_count: int = 0
    fixed_layout_profile_report_surface_count: int = 0
    fixed_layout_profile_repair_target_type_count: int = 0
    fixed_layout_profile_test_evidence_count: int = 0
    fixed_layout_profile_covered_pack_count: int = 0
    fixed_layout_profile_covered_family_count: int = 0
    fixed_layout_profile_issue_count: int = 0
    fixed_layout_profile_missing_source_evidence_count: int = 0
    report_artifact_drilldown_channel_count: int = 0
    report_artifact_drilldown_ready_channel_count: int = 0
    report_artifact_drilldown_artifact_kind_count: int = 0
    report_artifact_drilldown_runtime_surface_count: int = 0
    report_artifact_drilldown_ui_surface_count: int = 0
    report_artifact_drilldown_report_surface_count: int = 0
    report_artifact_drilldown_repair_target_type_count: int = 0
    report_artifact_drilldown_test_evidence_count: int = 0
    report_artifact_drilldown_covered_pack_count: int = 0
    report_artifact_drilldown_covered_family_count: int = 0
    report_artifact_drilldown_issue_count: int = 0
    report_artifact_drilldown_missing_source_evidence_count: int = 0
    delivery_preset_family_count: int = 0
    delivery_preset_ready_family_count: int = 0
    delivery_preset_boundary_family_count: int = 0
    delivery_preset_accounted_family_count: int = 0
    delivery_preset_pack_count: int = 0
    delivery_preset_delivery_pack_count: int = 0
    delivery_preset_ready_delivery_pack_count: int = 0
    delivery_preset_boundary_delivery_pack_count: int = 0
    delivery_preset_accounted_delivery_pack_count: int = 0
    delivery_preset_unique_preset_count: int = 0
    delivery_preset_final_docx_preset_count: int = 0
    delivery_preset_compare_docx_preset_count: int = 0
    delivery_preset_report_only_preset_count: int = 0
    delivery_preset_material_package_preset_count: int = 0
    delivery_preset_structured_intermediate_preset_count: int = 0
    delivery_preset_content_visibility_rule_count: int = 0
    delivery_preset_issue_count: int = 0
    delivery_execution_channel_count: int = 0
    delivery_execution_ready_channel_count: int = 0
    delivery_execution_required_output_signal_count: int = 0
    delivery_execution_payload_key_count: int = 0
    delivery_execution_runtime_surface_count: int = 0
    delivery_execution_report_surface_count: int = 0
    delivery_execution_ui_surface_count: int = 0
    delivery_execution_test_evidence_count: int = 0
    delivery_execution_covered_pack_count: int = 0
    delivery_execution_covered_family_count: int = 0
    delivery_execution_issue_count: int = 0
    delivery_execution_missing_source_evidence_count: int = 0
    formula_output_watermark_capability_count: int = 0
    formula_output_watermark_ready_capability_count: int = 0
    formula_output_watermark_family_count: int = 0
    formula_output_watermark_ready_family_count: int = 0
    formula_output_watermark_boundary_family_count: int = 0
    formula_output_watermark_accounted_family_count: int = 0
    formula_output_watermark_formula_family_count: int = 0
    formula_output_watermark_output_family_count: int = 0
    formula_output_watermark_watermark_family_count: int = 0
    formula_output_watermark_plugin_gate_count: int = 0
    formula_output_watermark_control_contract_count: int = 0
    formula_output_watermark_parameter_path_count: int = 0
    formula_output_watermark_template_baseline_path_count: int = 0
    formula_output_watermark_issue_count: int = 0
    product_readiness_subject_count: int = 0
    static_closed_but_not_green_count: int = 0
    static_closed_not_green_governed_count: int = 0
    count_profile_profile_count: int = 0
    count_profile_referenced_profile_count: int = 0
    count_profile_rule_source_profile_count: int = 0
    count_profile_registry_only_profile_count: int = 0
    count_profile_rule_source_only_profile_count: int = 0
    count_profile_section_limit_profile_count: int = 0
    count_profile_unique_scope_count: int = 0
    count_profile_unique_primary_metric_count: int = 0
    count_profile_family_count: int = 0
    count_profile_ready_family_count: int = 0
    count_profile_boundary_family_count: int = 0
    count_profile_accounted_family_count: int = 0
    count_profile_pack_count: int = 0
    count_profile_count_profile_pack_count: int = 0
    count_profile_ready_count_profile_pack_count: int = 0
    count_profile_runtime_consumer_count: int = 0
    count_profile_report_surface_count: int = 0
    count_profile_issue_count: int = 0
    count_profile_warning_count: int = 0
    count_profile_missing_source_evidence_count: int = 0
    maturity_upgrade_subject_count: int = 0
    maturity_upgrade_green_subject_count: int = 0
    maturity_upgrade_l5_blocked_subject_count: int = 0
    maturity_upgrade_l3_subject_count: int = 0
    maturity_upgrade_l4_subject_count: int = 0
    maturity_upgrade_boundary_subject_count: int = 0
    maturity_upgrade_gap_count: int = 0
    maturity_upgrade_gap_domain_count: int = 0
    maturity_upgrade_gap_domain_classified_count: int = 0
    maturity_upgrade_issue_count: int = 0
    maturity_upgrade_warning_count: int = 0
    maturity_upgrade_missing_source_evidence_count: int = 0

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def pack_count(self) -> int:
        return len(self.rows)

    @property
    def visible_count(self) -> int:
        return len(self.rows)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "pack_filter": self.pack_filter,
            "family_filter": self.family_filter,
            "readiness_filter": self.readiness_filter,
            "boundary_filter": self.boundary_filter,
            "status_filter": self.status_filter,
            "total_count": self.total_count,
            "visible_count": self.visible_count,
            "pack_count": self.pack_count,
            "issue_count": self.issue_count,
            "warning_count": self.warning_count,
            "source_ids": list(self.source_ids),
            "lenses": [lens.to_payload() for lens in self.lenses],
            "cards": [card.to_payload() for card in self.cards],
            "counts": {
                "request_cell_count": self.request_cell_count,
                "request_cell_pack_link_count": self.request_cell_pack_link_count,
                "high_frequency_completeness_ready_pack_count": (
                    self.high_frequency_completeness_ready_pack_count
                ),
                "task_lexicon_task_count": self.task_lexicon_task_count,
                "task_lexicon_phrase_count": self.task_lexicon_phrase_count,
                "task_lexicon_negative_task_count": (
                    self.task_lexicon_negative_task_count
                ),
                "task_lexicon_issue_count": self.task_lexicon_issue_count,
                "ambiguous_boundary_count": self.ambiguous_boundary_count,
                "ambiguous_boundary_pack_pair_count": (
                    self.ambiguous_boundary_pack_pair_count
                ),
                "ambiguous_boundary_issue_count": (
                    self.ambiguous_boundary_issue_count
                ),
                "ambiguity_clarification_count": (
                    self.ambiguity_clarification_count
                ),
                "ambiguity_clarification_ready_count": (
                    self.ambiguity_clarification_ready_count
                ),
                "ambiguity_clarification_candidate_route_count": (
                    self.ambiguity_clarification_candidate_route_count
                ),
                "ambiguity_clarification_candidate_pack_count": (
                    self.ambiguity_clarification_candidate_pack_count
                ),
                "ambiguity_clarification_fixture_backed_count": (
                    self.ambiguity_clarification_fixture_backed_count
                ),
                "ambiguity_clarification_issue_count": (
                    self.ambiguity_clarification_issue_count
                ),
                "ambiguity_clarification_warning_count": (
                    self.ambiguity_clarification_warning_count
                ),
                "ambiguity_clarification_missing_source_evidence_count": (
                    self.ambiguity_clarification_missing_source_evidence_count
                ),
                "import_handoff_count": self.import_handoff_count,
                "import_handoff_ready_count": self.import_handoff_ready_count,
                "import_handoff_issue_count": self.import_handoff_issue_count,
                "input_source_family_count": self.input_source_family_count,
                "input_source_ready_family_count": (
                    self.input_source_ready_family_count
                ),
                "input_source_boundary_family_count": (
                    self.input_source_boundary_family_count
                ),
                "input_source_pack_count": self.input_source_pack_count,
                "input_source_input_pack_count": self.input_source_input_pack_count,
                "input_source_ready_input_pack_count": (
                    self.input_source_ready_input_pack_count
                ),
                "input_source_accepted_format_count": (
                    self.input_source_accepted_format_count
                ),
                "input_source_structured_format_count": (
                    self.input_source_structured_format_count
                ),
                "input_source_material_required_family_count": (
                    self.input_source_material_required_family_count
                ),
                "input_source_markdown_enabled_family_count": (
                    self.input_source_markdown_enabled_family_count
                ),
                "input_source_latex_fragment_family_count": (
                    self.input_source_latex_fragment_family_count
                ),
                "input_source_render_source_count": (
                    self.input_source_render_source_count
                ),
                "input_source_target_template_count": (
                    self.input_source_target_template_count
                ),
                "input_source_boundary_input_source_count": (
                    self.input_source_boundary_input_source_count
                ),
                "input_source_format_count": self.input_source_format_count,
                "input_source_issue_count": self.input_source_issue_count,
                "input_source_warning_count": self.input_source_warning_count,
                "input_source_missing_source_evidence_count": (
                    self.input_source_missing_source_evidence_count
                ),
                "family_count": self.family_count,
                "family_fixture_depth_family_count": (
                    self.family_fixture_depth_family_count
                ),
                "family_fixture_depth_p1_family_count": (
                    self.family_fixture_depth_p1_family_count
                ),
                "family_fixture_depth_p1_ready_count": (
                    self.family_fixture_depth_p1_ready_count
                ),
                "family_fixture_depth_issue_count": (
                    self.family_fixture_depth_issue_count
                ),
                "sample_fixture_count": self.sample_fixture_count,
                "plugin_boundary_pack_count": sum(
                    1 for row in self.rows if row.plugin_boundary
                ),
                "manual_boundary_pack_count": sum(
                    1
                    for row in self.rows
                    if row.manual_boundary_request_cell_count
                ),
                "ambiguous_pack_count": sum(
                    1 for row in self.rows if row.ambiguous_request_cell_count
                ),
                "control_contract_count": self.control_contract_count,
                "control_runtime_control_count": (
                    self.control_runtime_control_count
                ),
                "control_runtime_ready_control_count": (
                    self.control_runtime_ready_control_count
                ),
                "control_runtime_contract_link_count": (
                    self.control_runtime_contract_link_count
                ),
                "control_runtime_scene_surface_count": (
                    self.control_runtime_scene_surface_count
                ),
                "control_runtime_template_surface_count": (
                    self.control_runtime_template_surface_count
                ),
                "control_runtime_shared_component_count": (
                    self.control_runtime_shared_component_count
                ),
                "control_runtime_consumer_count": (
                    self.control_runtime_consumer_count
                ),
                "control_runtime_issue_count": self.control_runtime_issue_count,
                "control_runtime_missing_source_evidence_count": (
                    self.control_runtime_missing_source_evidence_count
                ),
                "word_risk_surface_count": self.word_risk_surface_count,
                "object_preflight_action_target_count": (
                    self.object_preflight_action_target_count
                ),
                "object_preflight_action_ready_target_count": (
                    self.object_preflight_action_ready_target_count
                ),
                "object_preflight_action_warning_target_count": (
                    self.object_preflight_action_warning_target_count
                ),
                "object_preflight_action_high_risk_target_count": (
                    self.object_preflight_action_high_risk_target_count
                ),
                "object_preflight_action_fixture_backed_target_count": (
                    self.object_preflight_action_fixture_backed_target_count
                ),
                "object_preflight_action_blockable_target_count": (
                    self.object_preflight_action_blockable_target_count
                ),
                "object_preflight_action_skippable_target_count": (
                    self.object_preflight_action_skippable_target_count
                ),
                "object_preflight_action_manual_confirmation_target_count": (
                    self.object_preflight_action_manual_confirmation_target_count
                ),
                "object_preflight_action_family_count": (
                    self.object_preflight_action_family_count
                ),
                "object_preflight_action_ready_family_count": (
                    self.object_preflight_action_ready_family_count
                ),
                "object_preflight_action_boundary_family_count": (
                    self.object_preflight_action_boundary_family_count
                ),
                "object_preflight_action_strict_family_count": (
                    self.object_preflight_action_strict_family_count
                ),
                "object_preflight_action_family_with_fixture_count": (
                    self.object_preflight_action_family_with_fixture_count
                ),
                "object_preflight_action_issue_count": (
                    self.object_preflight_action_issue_count
                ),
                "object_preflight_action_warning_count": (
                    self.object_preflight_action_warning_count
                ),
                "object_preflight_action_missing_source_evidence_count": (
                    self.object_preflight_action_missing_source_evidence_count
                ),
                "user_journey_pack_count": self.user_journey_pack_count,
                "user_journey_ready_pack_count": (
                    self.user_journey_ready_pack_count
                ),
                "user_journey_warning_pack_count": (
                    self.user_journey_warning_pack_count
                ),
                "user_journey_family_count": self.user_journey_family_count,
                "user_journey_ready_family_count": (
                    self.user_journey_ready_family_count
                ),
                "user_journey_warning_family_count": (
                    self.user_journey_warning_family_count
                ),
                "user_journey_path_count": self.user_journey_path_count,
                "user_journey_success_path_count": (
                    self.user_journey_success_path_count
                ),
                "user_journey_degraded_path_count": (
                    self.user_journey_degraded_path_count
                ),
                "user_journey_failure_path_count": (
                    self.user_journey_failure_path_count
                ),
                "user_journey_manual_boundary_path_count": (
                    self.user_journey_manual_boundary_path_count
                ),
                "user_journey_ambiguous_decision_path_count": (
                    self.user_journey_ambiguous_decision_path_count
                ),
                "user_journey_handoff_path_count": (
                    self.user_journey_handoff_path_count
                ),
                "user_journey_negative_control_path_count": (
                    self.user_journey_negative_control_path_count
                ),
                "user_journey_issue_count": self.user_journey_issue_count,
                "user_journey_warning_count": self.user_journey_warning_count,
                "user_journey_missing_source_evidence_count": (
                    self.user_journey_missing_source_evidence_count
                ),
                "business_capability_matrix_count": (
                    self.business_capability_matrix_count
                ),
                "business_capability_matrix_ready_count": (
                    self.business_capability_matrix_ready_count
                ),
                "business_capability_matrix_high_priority_count": (
                    self.business_capability_matrix_high_priority_count
                ),
                "business_capability_matrix_high_priority_ready_count": (
                    self.business_capability_matrix_high_priority_ready_count
                ),
                "business_capability_matrix_boundary_count": (
                    self.business_capability_matrix_boundary_count
                ),
                "business_capability_matrix_manual_gate_count": (
                    self.business_capability_matrix_manual_gate_count
                ),
                "business_capability_matrix_missing_journey_group_count": (
                    self.business_capability_matrix_missing_journey_group_count
                ),
                "business_capability_matrix_issue_count": (
                    self.business_capability_matrix_issue_count
                ),
                "business_capability_matrix_warning_count": (
                    self.business_capability_matrix_warning_count
                ),
                "business_capability_matrix_missing_source_evidence_count": (
                    self.business_capability_matrix_missing_source_evidence_count
                ),
                "boundary_capability_count": self.boundary_capability_count,
                "boundary_capability_ready_count": (
                    self.boundary_capability_ready_count
                ),
                "boundary_capability_professional_count": (
                    self.boundary_capability_professional_count
                ),
                "boundary_capability_import_ai_count": (
                    self.boundary_capability_import_ai_count
                ),
                "boundary_capability_fixture_count": (
                    self.boundary_capability_fixture_count
                ),
                "boundary_capability_report_expectation_count": (
                    self.boundary_capability_report_expectation_count
                ),
                "boundary_capability_ui_surface_count": (
                    self.boundary_capability_ui_surface_count
                ),
                "boundary_capability_risk_domain_count": (
                    self.boundary_capability_risk_domain_count
                ),
                "boundary_capability_decision_requirement_count": (
                    self.boundary_capability_decision_requirement_count
                ),
                "boundary_capability_external_receipt_count": (
                    self.boundary_capability_external_receipt_count
                ),
                "boundary_capability_release_guardrail_count": (
                    self.boundary_capability_release_guardrail_count
                ),
                "boundary_capability_issue_count": self.boundary_capability_issue_count,
                "boundary_capability_missing_source_evidence_count": (
                    self.boundary_capability_missing_source_evidence_count
                ),
                "plugin_boundary_gate_count": self.plugin_boundary_gate_count,
                "plugin_boundary_risk_domain_count": (
                    self.plugin_boundary_risk_domain_count
                ),
                "plugin_boundary_issue_count": self.plugin_boundary_issue_count,
                "external_handoff_contract_count": (
                    self.external_handoff_contract_count
                ),
                "external_handoff_contract_ready_count": (
                    self.external_handoff_contract_ready_count
                ),
                "external_handoff_contract_pack_count": (
                    self.external_handoff_contract_pack_count
                ),
                "external_handoff_contract_family_count": (
                    self.external_handoff_contract_family_count
                ),
                "external_handoff_contract_plugin_gate_count": (
                    self.external_handoff_contract_plugin_gate_count
                ),
                "external_handoff_contract_target_plugin_count": (
                    self.external_handoff_contract_target_plugin_count
                ),
                "external_handoff_contract_risk_domain_count": (
                    self.external_handoff_contract_risk_domain_count
                ),
                "external_handoff_contract_report_count": (
                    self.external_handoff_contract_report_count
                ),
                "external_handoff_contract_ui_surface_count": (
                    self.external_handoff_contract_ui_surface_count
                ),
                "external_handoff_contract_fixture_count": (
                    self.external_handoff_contract_fixture_count
                ),
                "external_handoff_contract_status_state_count": (
                    self.external_handoff_contract_status_state_count
                ),
                "external_handoff_contract_failure_policy_count": (
                    self.external_handoff_contract_failure_policy_count
                ),
                "external_handoff_contract_issue_count": (
                    self.external_handoff_contract_issue_count
                ),
                "external_handoff_contract_missing_source_evidence_count": (
                    self.external_handoff_contract_missing_source_evidence_count
                ),
                "boundary_guarded_completion_subject_count": (
                    self.boundary_guarded_completion_subject_count
                ),
                "boundary_guarded_completion_ready_count": (
                    self.boundary_guarded_completion_ready_count
                ),
                "boundary_guarded_completion_pack_count": (
                    self.boundary_guarded_completion_pack_count
                ),
                "boundary_guarded_completion_family_count": (
                    self.boundary_guarded_completion_family_count
                ),
                "boundary_guarded_completion_retained_gap_count": (
                    self.boundary_guarded_completion_retained_gap_count
                ),
                "boundary_guarded_completion_external_contract_count": (
                    self.boundary_guarded_completion_external_contract_count
                ),
                "boundary_guarded_completion_boundary_capability_count": (
                    self.boundary_guarded_completion_boundary_capability_count
                ),
                "boundary_guarded_completion_plugin_gate_count": (
                    self.boundary_guarded_completion_plugin_gate_count
                ),
                "boundary_guarded_completion_target_plugin_count": (
                    self.boundary_guarded_completion_target_plugin_count
                ),
                "boundary_guarded_completion_risk_domain_count": (
                    self.boundary_guarded_completion_risk_domain_count
                ),
                "boundary_guarded_completion_excluded_core_claim_count": (
                    self.boundary_guarded_completion_excluded_core_claim_count
                ),
                "boundary_guarded_completion_issue_count": (
                    self.boundary_guarded_completion_issue_count
                ),
                "boundary_guarded_completion_missing_source_evidence_count": (
                    self.boundary_guarded_completion_missing_source_evidence_count
                ),
                "residual_warning_governance_warning_count": (
                    self.residual_warning_governance_warning_count
                ),
                "residual_warning_governance_managed_count": (
                    self.residual_warning_governance_managed_count
                ),
                "residual_warning_governance_input_source_warning_count": (
                    self.residual_warning_governance_input_source_warning_count
                ),
                "residual_warning_governance_input_source_managed_warning_count": (
                    self.residual_warning_governance_input_source_managed_warning_count
                ),
                "residual_warning_governance_count_profile_warning_count": (
                    self.residual_warning_governance_count_profile_warning_count
                ),
                "residual_warning_governance_count_profile_managed_warning_count": (
                    self.residual_warning_governance_count_profile_managed_warning_count
                ),
                "residual_warning_governance_dashboard_projection_warning_count": (
                    self.residual_warning_governance_dashboard_projection_warning_count
                ),
                "dashboard_warning_projection_governed_count": (
                    self.dashboard_warning_projection_governed_count
                ),
                "residual_warning_governance_plugin_manual_warning_count": (
                    self.residual_warning_governance_plugin_manual_warning_count
                ),
                "residual_warning_governance_plugin_manual_managed_warning_count": (
                    self.residual_warning_governance_plugin_manual_managed_warning_count
                ),
                "residual_warning_governance_reference_profile_warning_count": (
                    self.residual_warning_governance_reference_profile_warning_count
                ),
                "residual_warning_governance_reference_profile_managed_warning_count": (
                    self.residual_warning_governance_reference_profile_managed_warning_count
                ),
                "residual_warning_governance_object_preflight_warning_count": (
                    self.residual_warning_governance_object_preflight_warning_count
                ),
                "residual_warning_governance_visio_fixture_closed_count": (
                    self.residual_warning_governance_visio_fixture_closed_count
                ),
                "residual_warning_governance_visio_fixture_verified_count": (
                    self.residual_warning_governance_visio_fixture_verified_count
                ),
                "residual_warning_governance_unmanaged_warning_count": (
                    self.residual_warning_governance_unmanaged_warning_count
                ),
                "residual_warning_governance_issue_count": (
                    self.residual_warning_governance_issue_count
                ),
                "residual_warning_governance_missing_source_evidence_count": (
                    self.residual_warning_governance_missing_source_evidence_count
                ),
                "boundary_readiness_reconciliation_count": (
                    self.boundary_readiness_reconciliation_count
                ),
                "boundary_readiness_reconciliation_reconciled_count": (
                    self.boundary_readiness_reconciliation_reconciled_count
                ),
                "boundary_readiness_reconciliation_unreconciled_count": (
                    self.boundary_readiness_reconciliation_unreconciled_count
                ),
                "boundary_readiness_reconciliation_readiness_delta_count": (
                    self.boundary_readiness_reconciliation_readiness_delta_count
                ),
                "boundary_readiness_reconciliation_not_applicable_count": (
                    self.boundary_readiness_reconciliation_not_applicable_count
                ),
                "boundary_readiness_reconciliation_static_closed_boundary_count": (
                    self.boundary_readiness_reconciliation_static_closed_boundary_count
                ),
                "boundary_readiness_reconciliation_maturity_boundary_guarded_count": (
                    self.boundary_readiness_reconciliation_maturity_boundary_guarded_count
                ),
                "boundary_readiness_reconciliation_boundary_subject_count": (
                    self.boundary_readiness_reconciliation_boundary_subject_count
                ),
                "boundary_readiness_reconciliation_issue_count": (
                    self.boundary_readiness_reconciliation_issue_count
                ),
                "boundary_readiness_reconciliation_missing_source_evidence_count": (
                    self.boundary_readiness_reconciliation_missing_source_evidence_count
                ),
                "terminal_release_exception_count": (
                    self.terminal_release_exception_count
                ),
                "terminal_release_exception_governed_count": (
                    self.terminal_release_exception_governed_count
                ),
                "terminal_release_exception_ungoverned_count": (
                    self.terminal_release_exception_ungoverned_count
                ),
                "terminal_release_exception_managed_warning_count": (
                    self.terminal_release_exception_managed_warning_count
                ),
                "terminal_release_exception_warning_projection_count": (
                    self.terminal_release_exception_warning_projection_count
                ),
                "terminal_release_exception_readiness_reconciliation_count": (
                    self.terminal_release_exception_readiness_reconciliation_count
                ),
                "terminal_release_exception_boundary_guarded_maturity_count": (
                    self.terminal_release_exception_boundary_guarded_maturity_count
                ),
                "terminal_release_exception_static_closed_boundary_count": (
                    self.terminal_release_exception_static_closed_boundary_count
                ),
                "terminal_release_exception_trace_count": (
                    self.terminal_release_exception_trace_count
                ),
                "terminal_release_exception_unique_source_trace_count": (
                    self.terminal_release_exception_unique_source_trace_count
                ),
                "terminal_release_exception_linked_boundary_subject_count": (
                    self.terminal_release_exception_linked_boundary_subject_count
                ),
                "terminal_release_exception_issue_count": (
                    self.terminal_release_exception_issue_count
                ),
                "terminal_release_exception_missing_source_evidence_count": (
                    self.terminal_release_exception_missing_source_evidence_count
                ),
                "boundary_subject_release_dossier_subject_count": (
                    self.boundary_subject_release_dossier_subject_count
                ),
                "boundary_subject_release_dossier_ready_count": (
                    self.boundary_subject_release_dossier_ready_count
                ),
                "boundary_subject_release_dossier_pack_subject_count": (
                    self.boundary_subject_release_dossier_pack_subject_count
                ),
                "boundary_subject_release_dossier_family_subject_count": (
                    self.boundary_subject_release_dossier_family_subject_count
                ),
                "boundary_subject_release_dossier_subject_trace_count": (
                    self.boundary_subject_release_dossier_subject_trace_count
                ),
                "boundary_subject_release_dossier_unique_source_trace_count": (
                    self.boundary_subject_release_dossier_unique_source_trace_count
                ),
                "boundary_subject_release_dossier_readiness_reconciliation_row_count": (
                    self.boundary_subject_release_dossier_readiness_reconciliation_row_count
                ),
                "boundary_subject_release_dossier_terminal_exception_count": (
                    self.boundary_subject_release_dossier_terminal_exception_count
                ),
                "boundary_subject_release_dossier_issue_count": (
                    self.boundary_subject_release_dossier_issue_count
                ),
                "boundary_subject_release_dossier_missing_source_evidence_count": (
                    self.boundary_subject_release_dossier_missing_source_evidence_count
                ),
                "non_subject_release_trace_attribution_count": (
                    self.non_subject_release_trace_attribution_count
                ),
                "non_subject_release_trace_attribution_ready_count": (
                    self.non_subject_release_trace_attribution_ready_count
                ),
                "non_subject_release_trace_attribution_unattributed_count": (
                    self.non_subject_release_trace_attribution_unattributed_count
                ),
                "non_subject_release_trace_attribution_dashboard_projection_count": (
                    self.non_subject_release_trace_attribution_dashboard_projection_count
                ),
                "non_subject_release_trace_attribution_registry_only_profile_count": (
                    self.non_subject_release_trace_attribution_registry_only_profile_count
                ),
                "non_subject_release_trace_attribution_plugin_manual_pack_count": (
                    self.non_subject_release_trace_attribution_plugin_manual_pack_count
                ),
                "non_subject_release_trace_attribution_generic_not_applicable_count": (
                    self.non_subject_release_trace_attribution_generic_not_applicable_count
                ),
                "non_subject_release_trace_attribution_issue_count": (
                    self.non_subject_release_trace_attribution_issue_count
                ),
                "non_subject_release_trace_attribution_missing_source_evidence_count": (
                    self.non_subject_release_trace_attribution_missing_source_evidence_count
                ),
                "release_trace_partition_guard_partition_count": (
                    self.release_trace_partition_guard_partition_count
                ),
                "release_trace_partition_guard_ready_count": (
                    self.release_trace_partition_guard_ready_count
                ),
                "release_trace_partition_guard_terminal_trace_count": (
                    self.release_trace_partition_guard_terminal_trace_count
                ),
                "release_trace_partition_guard_subject_trace_count": (
                    self.release_trace_partition_guard_subject_trace_count
                ),
                "release_trace_partition_guard_non_subject_trace_count": (
                    self.release_trace_partition_guard_non_subject_trace_count
                ),
                "release_trace_partition_guard_partitioned_trace_count": (
                    self.release_trace_partition_guard_partitioned_trace_count
                ),
                "release_trace_partition_guard_missing_trace_count": (
                    self.release_trace_partition_guard_missing_trace_count
                ),
                "release_trace_partition_guard_overlap_trace_count": (
                    self.release_trace_partition_guard_overlap_trace_count
                ),
                "release_trace_partition_guard_extra_trace_count": (
                    self.release_trace_partition_guard_extra_trace_count
                ),
                "release_trace_partition_guard_issue_count": (
                    self.release_trace_partition_guard_issue_count
                ),
                "release_trace_partition_guard_missing_source_evidence_count": (
                    self.release_trace_partition_guard_missing_source_evidence_count
                ),
                "release_projection_surface_parity_count": (
                    self.release_projection_surface_parity_count
                ),
                "release_projection_surface_parity_ready_count": (
                    self.release_projection_surface_parity_ready_count
                ),
                "release_projection_surface_parity_release_gate_check_count": (
                    self.release_projection_surface_parity_release_gate_check_count
                ),
                "release_projection_surface_parity_dashboard_source_count": (
                    self.release_projection_surface_parity_dashboard_source_count
                ),
                "release_projection_surface_parity_dashboard_card_count": (
                    self.release_projection_surface_parity_dashboard_card_count
                ),
                "release_projection_surface_parity_drilldown_item_count": (
                    self.release_projection_surface_parity_drilldown_item_count
                ),
                "release_projection_surface_parity_summary_projection_count": (
                    self.release_projection_surface_parity_summary_projection_count
                ),
                "release_projection_surface_parity_export_script_count": (
                    self.release_projection_surface_parity_export_script_count
                ),
                "release_projection_surface_parity_workflow_test_count": (
                    self.release_projection_surface_parity_workflow_test_count
                ),
                "release_projection_surface_parity_closure_doc_count": (
                    self.release_projection_surface_parity_closure_doc_count
                ),
                "release_projection_surface_parity_issue_count": (
                    self.release_projection_surface_parity_issue_count
                ),
                "release_projection_surface_parity_missing_source_evidence_count": (
                    self.release_projection_surface_parity_missing_source_evidence_count
                ),
                "boundary_subject_release_continuity_subject_count": (
                    self.boundary_subject_release_continuity_subject_count
                ),
                "boundary_subject_release_continuity_ready_count": (
                    self.boundary_subject_release_continuity_ready_count
                ),
                "boundary_subject_release_continuity_maturity_subject_count": (
                    self.boundary_subject_release_continuity_maturity_subject_count
                ),
                "boundary_subject_release_continuity_guarded_completion_subject_count": (
                    self.boundary_subject_release_continuity_guarded_completion_subject_count
                ),
                "boundary_subject_release_continuity_readiness_reconciliation_subject_count": (
                    self.boundary_subject_release_continuity_readiness_reconciliation_subject_count
                ),
                "boundary_subject_release_continuity_terminal_release_subject_count": (
                    self.boundary_subject_release_continuity_terminal_release_subject_count
                ),
                "boundary_subject_release_continuity_dossier_count": (
                    self.boundary_subject_release_continuity_dossier_count
                ),
                "boundary_subject_release_continuity_readiness_row_count": (
                    self.boundary_subject_release_continuity_readiness_row_count
                ),
                "boundary_subject_release_continuity_terminal_trace_count": (
                    self.boundary_subject_release_continuity_terminal_trace_count
                ),
                "boundary_subject_release_continuity_dossier_trace_count": (
                    self.boundary_subject_release_continuity_dossier_trace_count
                ),
                "boundary_subject_release_continuity_mismatch_count": (
                    self.boundary_subject_release_continuity_mismatch_count
                ),
                "boundary_subject_release_continuity_issue_count": (
                    self.boundary_subject_release_continuity_issue_count
                ),
                "boundary_subject_release_continuity_missing_source_evidence_count": (
                    self.boundary_subject_release_continuity_missing_source_evidence_count
                ),
                "release_closure_ledger_stage_count": (
                    self.release_closure_ledger_stage_count
                ),
                "release_closure_ledger_ready_count": (
                    self.release_closure_ledger_ready_count
                ),
                "release_closure_ledger_stage_order_count": (
                    self.release_closure_ledger_stage_order_count
                ),
                "release_closure_ledger_upstream_dependency_count": (
                    self.release_closure_ledger_upstream_dependency_count
                ),
                "release_closure_ledger_upstream_dependency_ready_count": (
                    self.release_closure_ledger_upstream_dependency_ready_count
                ),
                "release_closure_ledger_release_gate_check_count": (
                    self.release_closure_ledger_release_gate_check_count
                ),
                "release_closure_ledger_dashboard_source_count": (
                    self.release_closure_ledger_dashboard_source_count
                ),
                "release_closure_ledger_dashboard_card_count": (
                    self.release_closure_ledger_dashboard_card_count
                ),
                "release_closure_ledger_drilldown_item_count": (
                    self.release_closure_ledger_drilldown_item_count
                ),
                "release_closure_ledger_summary_projection_count": (
                    self.release_closure_ledger_summary_projection_count
                ),
                "release_closure_ledger_export_script_count": (
                    self.release_closure_ledger_export_script_count
                ),
                "release_closure_ledger_workflow_test_count": (
                    self.release_closure_ledger_workflow_test_count
                ),
                "release_closure_ledger_closure_doc_count": (
                    self.release_closure_ledger_closure_doc_count
                ),
                "release_closure_ledger_issue_count": (
                    self.release_closure_ledger_issue_count
                ),
                "release_closure_ledger_missing_source_evidence_count": (
                    self.release_closure_ledger_missing_source_evidence_count
                ),
                "boundary_maturity_release_envelope_count": (
                    self.boundary_maturity_release_envelope_count
                ),
                "boundary_maturity_release_envelope_ready_count": (
                    self.boundary_maturity_release_envelope_ready_count
                ),
                "boundary_maturity_release_envelope_l5_blocker_enveloped_count": (
                    self.boundary_maturity_release_envelope_l5_blocker_enveloped_count
                ),
                "boundary_maturity_release_envelope_maturity_boundary_count": (
                    self.boundary_maturity_release_envelope_maturity_boundary_count
                ),
                "boundary_maturity_release_envelope_external_handoff_count": (
                    self.boundary_maturity_release_envelope_external_handoff_count
                ),
                "boundary_maturity_release_envelope_guarded_completion_count": (
                    self.boundary_maturity_release_envelope_guarded_completion_count
                ),
                "boundary_maturity_release_envelope_readiness_reconciliation_count": (
                    self.boundary_maturity_release_envelope_readiness_reconciliation_count
                ),
                "boundary_maturity_release_envelope_terminal_trace_count": (
                    self.boundary_maturity_release_envelope_terminal_trace_count
                ),
                "boundary_maturity_release_envelope_release_dossier_count": (
                    self.boundary_maturity_release_envelope_release_dossier_count
                ),
                "boundary_maturity_release_envelope_subject_continuity_count": (
                    self.boundary_maturity_release_envelope_subject_continuity_count
                ),
                "boundary_maturity_release_envelope_retained_gap_count": (
                    self.boundary_maturity_release_envelope_retained_gap_count
                ),
                "retained_gap_enveloped_count": self.retained_gap_enveloped_count,
                "boundary_maturity_release_envelope_issue_count": (
                    self.boundary_maturity_release_envelope_issue_count
                ),
                "boundary_maturity_release_envelope_missing_source_evidence_count": (
                    self.boundary_maturity_release_envelope_missing_source_evidence_count
                ),
                "retained_gap_exit_criteria_count": (
                    self.retained_gap_exit_criteria_count
                ),
                "retained_gap_exit_criteria_release_allowed_count": (
                    self.retained_gap_exit_criteria_release_allowed_count
                ),
                "retained_gap_exit_criteria_envelope_link_count": (
                    self.retained_gap_exit_criteria_envelope_link_count
                ),
                "retained_gap_exit_criteria_handoff_link_count": (
                    self.retained_gap_exit_criteria_handoff_link_count
                ),
                "retained_gap_exit_criteria_guarded_completion_link_count": (
                    self.retained_gap_exit_criteria_guarded_completion_link_count
                ),
                "retained_gap_exit_criteria_boundary_capability_link_count": (
                    self.retained_gap_exit_criteria_boundary_capability_link_count
                ),
                "retained_gap_exit_criteria_exit_signal_count": (
                    self.retained_gap_exit_criteria_exit_signal_count
                ),
                "retained_gap_external_receipt_target_count": (
                    self.retained_gap_external_receipt_target_count
                ),
                "retained_gap_external_receipt_alignment_count": (
                    self.retained_gap_external_receipt_alignment_count
                ),
                "retained_gap_exit_criteria_prohibited_core_claim_count": (
                    self.retained_gap_exit_criteria_prohibited_core_claim_count
                ),
                "retained_gap_exit_criteria_issue_count": (
                    self.retained_gap_exit_criteria_issue_count
                ),
                "retained_gap_exit_criteria_missing_source_evidence_count": (
                    self.retained_gap_exit_criteria_missing_source_evidence_count
                ),
                "release_residual_ratio_ledger_count": (
                    self.release_residual_ratio_ledger_count
                ),
                "release_residual_ratio_ledger_published_count": (
                    self.release_residual_ratio_ledger_published_count
                ),
                "release_residual_ratio_ledger_non_full_count": (
                    self.release_residual_ratio_ledger_non_full_count
                ),
                "release_residual_ratio_ledger_readiness_reconciliation_link_count": (
                    self.release_residual_ratio_ledger_readiness_reconciliation_link_count
                ),
                "release_residual_ratio_ledger_terminal_exception_link_count": (
                    self.release_residual_ratio_ledger_terminal_exception_link_count
                ),
                "release_residual_ratio_ledger_release_envelope_link_count": (
                    self.release_residual_ratio_ledger_release_envelope_link_count
                ),
                "release_residual_ratio_ledger_exit_criteria_link_count": (
                    self.release_residual_ratio_ledger_exit_criteria_link_count
                ),
                "release_residual_ratio_ledger_receipt_alignment_link_count": (
                    self.release_residual_ratio_ledger_receipt_alignment_link_count
                ),
                "release_residual_ratio_ledger_count_delivery_boundary_alignment_count": (
                    self.release_residual_ratio_ledger_count_delivery_boundary_alignment_count
                ),
                "release_residual_ratio_ledger_count_delivery_boundary_link_count": (
                    self.release_residual_ratio_ledger_count_delivery_boundary_link_count
                ),
                "release_residual_ratio_ledger_count_delivery_receipt_alignment_count": (
                    self.release_residual_ratio_ledger_count_delivery_receipt_alignment_count
                ),
                "release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count": (
                    self.release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count
                ),
                "release_residual_ratio_ledger_maturity_l5_blocker_alignment_count": (
                    self.release_residual_ratio_ledger_maturity_l5_blocker_alignment_count
                ),
                "release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count": (
                    self.release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count
                ),
                "release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count": (
                    self.release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count
                ),
                "release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count": (
                    self.release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count
                ),
                "release_residual_ratio_ledger_boundary_scope_alignment_count": (
                    self.release_residual_ratio_ledger_boundary_scope_alignment_count
                ),
                "release_residual_ratio_ledger_boundary_scope_link_count": (
                    self.release_residual_ratio_ledger_boundary_scope_link_count
                ),
                "release_residual_ratio_ledger_issue_count": (
                    self.release_residual_ratio_ledger_issue_count
                ),
                "release_residual_ratio_ledger_missing_source_evidence_count": (
                    self.release_residual_ratio_ledger_missing_source_evidence_count
                ),
                "release_residual_explanation_count": (
                    self.release_residual_explanation_count
                ),
                "release_residual_explanation_covered_count": (
                    self.release_residual_explanation_covered_count
                ),
                "release_residual_explanation_mismatch_count": (
                    self.release_residual_explanation_mismatch_count
                ),
                "release_residual_explanation_missing_summary_marker_count": (
                    self.release_residual_explanation_missing_summary_marker_count
                ),
                "release_residual_explanation_issue_count": (
                    self.release_residual_explanation_issue_count
                ),
                "release_residual_explanation_missing_source_evidence_count": (
                    self.release_residual_explanation_missing_source_evidence_count
                ),
                "release_acceptance_certificate_count": (
                    self.release_acceptance_certificate_count
                ),
                "release_acceptance_certificate_ready_count": (
                    self.release_acceptance_certificate_ready_count
                ),
                "release_acceptance_certificate_receipt_count": (
                    self.release_acceptance_certificate_receipt_count
                ),
                "release_acceptance_certificate_ready_receipt_count": (
                    self.release_acceptance_certificate_ready_receipt_count
                ),
                "release_acceptance_certificate_component_report_count": (
                    self.release_acceptance_certificate_component_report_count
                ),
                "release_acceptance_certificate_requirement_dimension_count": (
                    self.release_acceptance_certificate_requirement_dimension_count
                ),
                "release_acceptance_certificate_ready_requirement_dimension_count": (
                    self.release_acceptance_certificate_ready_requirement_dimension_count
                ),
                "release_acceptance_certificate_expected_count_match_count": (
                    self.release_acceptance_certificate_expected_count_match_count
                ),
                "release_acceptance_certificate_source_evidence_count": (
                    self.release_acceptance_certificate_source_evidence_count
                ),
                "release_acceptance_certificate_ready_source_evidence_count": (
                    self.release_acceptance_certificate_ready_source_evidence_count
                ),
                "release_acceptance_certificate_issue_count": (
                    self.release_acceptance_certificate_issue_count
                ),
                "release_acceptance_certificate_missing_source_evidence_count": (
                    self.release_acceptance_certificate_missing_source_evidence_count
                ),
                "material_schema_family_count": self.material_schema_family_count,
                "material_schema_material_family_count": (
                    self.material_schema_material_family_count
                ),
                "material_schema_ready_material_family_count": (
                    self.material_schema_ready_material_family_count
                ),
                "material_schema_pack_count": self.material_schema_pack_count,
                "material_schema_material_pack_count": (
                    self.material_schema_material_pack_count
                ),
                "material_schema_ready_material_pack_count": (
                    self.material_schema_ready_material_pack_count
                ),
                "material_schema_schema_count": self.material_schema_schema_count,
                "material_schema_referenced_schema_count": (
                    self.material_schema_referenced_schema_count
                ),
                "material_schema_registry_only_schema_count": (
                    self.material_schema_registry_only_schema_count
                ),
                "material_schema_required_field_count": (
                    self.material_schema_required_field_count
                ),
                "material_schema_required_asset_count": (
                    self.material_schema_required_asset_count
                ),
                "material_schema_issue_count": self.material_schema_issue_count,
                "material_repair_flow_count": self.material_repair_flow_count,
                "material_repair_flow_ready_count": (
                    self.material_repair_flow_ready_count
                ),
                "material_repair_flow_capability_count": (
                    self.material_repair_flow_capability_count
                ),
                "material_repair_flow_signal_count": (
                    self.material_repair_flow_signal_count
                ),
                "material_repair_flow_target_type_count": (
                    self.material_repair_flow_target_type_count
                ),
                "material_repair_flow_runtime_surface_count": (
                    self.material_repair_flow_runtime_surface_count
                ),
                "material_repair_flow_ui_surface_count": (
                    self.material_repair_flow_ui_surface_count
                ),
                "material_repair_flow_test_evidence_count": (
                    self.material_repair_flow_test_evidence_count
                ),
                "material_repair_flow_covered_pack_count": (
                    self.material_repair_flow_covered_pack_count
                ),
                "material_repair_flow_covered_family_count": (
                    self.material_repair_flow_covered_family_count
                ),
                "material_repair_flow_issue_count": (
                    self.material_repair_flow_issue_count
                ),
                "material_repair_flow_missing_source_evidence_count": (
                    self.material_repair_flow_missing_source_evidence_count
                ),
                "fixed_layout_profile_channel_count": (
                    self.fixed_layout_profile_channel_count
                ),
                "fixed_layout_profile_ready_channel_count": (
                    self.fixed_layout_profile_ready_channel_count
                ),
                "fixed_layout_profile_surface_count": (
                    self.fixed_layout_profile_surface_count
                ),
                "fixed_layout_profile_ooxml_touchpoint_count": (
                    self.fixed_layout_profile_ooxml_touchpoint_count
                ),
                "fixed_layout_profile_runtime_surface_count": (
                    self.fixed_layout_profile_runtime_surface_count
                ),
                "fixed_layout_profile_ui_surface_count": (
                    self.fixed_layout_profile_ui_surface_count
                ),
                "fixed_layout_profile_report_surface_count": (
                    self.fixed_layout_profile_report_surface_count
                ),
                "fixed_layout_profile_repair_target_type_count": (
                    self.fixed_layout_profile_repair_target_type_count
                ),
                "fixed_layout_profile_test_evidence_count": (
                    self.fixed_layout_profile_test_evidence_count
                ),
                "fixed_layout_profile_covered_pack_count": (
                    self.fixed_layout_profile_covered_pack_count
                ),
                "fixed_layout_profile_covered_family_count": (
                    self.fixed_layout_profile_covered_family_count
                ),
                "fixed_layout_profile_issue_count": (
                    self.fixed_layout_profile_issue_count
                ),
                "fixed_layout_profile_missing_source_evidence_count": (
                    self.fixed_layout_profile_missing_source_evidence_count
                ),
                "report_artifact_drilldown_channel_count": (
                    self.report_artifact_drilldown_channel_count
                ),
                "report_artifact_drilldown_ready_channel_count": (
                    self.report_artifact_drilldown_ready_channel_count
                ),
                "report_artifact_drilldown_artifact_kind_count": (
                    self.report_artifact_drilldown_artifact_kind_count
                ),
                "report_artifact_drilldown_runtime_surface_count": (
                    self.report_artifact_drilldown_runtime_surface_count
                ),
                "report_artifact_drilldown_ui_surface_count": (
                    self.report_artifact_drilldown_ui_surface_count
                ),
                "report_artifact_drilldown_report_surface_count": (
                    self.report_artifact_drilldown_report_surface_count
                ),
                "report_artifact_drilldown_repair_target_type_count": (
                    self.report_artifact_drilldown_repair_target_type_count
                ),
                "report_artifact_drilldown_test_evidence_count": (
                    self.report_artifact_drilldown_test_evidence_count
                ),
                "report_artifact_drilldown_covered_pack_count": (
                    self.report_artifact_drilldown_covered_pack_count
                ),
                "report_artifact_drilldown_covered_family_count": (
                    self.report_artifact_drilldown_covered_family_count
                ),
                "report_artifact_drilldown_issue_count": (
                    self.report_artifact_drilldown_issue_count
                ),
                "report_artifact_drilldown_missing_source_evidence_count": (
                    self.report_artifact_drilldown_missing_source_evidence_count
                ),
                "delivery_preset_family_count": self.delivery_preset_family_count,
                "delivery_preset_ready_family_count": (
                    self.delivery_preset_ready_family_count
                ),
                "delivery_preset_boundary_family_count": (
                    self.delivery_preset_boundary_family_count
                ),
                "delivery_preset_accounted_family_count": (
                    self.delivery_preset_accounted_family_count
                ),
                "delivery_preset_pack_count": self.delivery_preset_pack_count,
                "delivery_preset_delivery_pack_count": (
                    self.delivery_preset_delivery_pack_count
                ),
                "delivery_preset_ready_delivery_pack_count": (
                    self.delivery_preset_ready_delivery_pack_count
                ),
                "delivery_preset_boundary_delivery_pack_count": (
                    self.delivery_preset_boundary_delivery_pack_count
                ),
                "delivery_preset_accounted_delivery_pack_count": (
                    self.delivery_preset_accounted_delivery_pack_count
                ),
                "delivery_preset_unique_preset_count": (
                    self.delivery_preset_unique_preset_count
                ),
                "delivery_preset_final_docx_preset_count": (
                    self.delivery_preset_final_docx_preset_count
                ),
                "delivery_preset_compare_docx_preset_count": (
                    self.delivery_preset_compare_docx_preset_count
                ),
                "delivery_preset_report_only_preset_count": (
                    self.delivery_preset_report_only_preset_count
                ),
                "delivery_preset_material_package_preset_count": (
                    self.delivery_preset_material_package_preset_count
                ),
                "delivery_preset_structured_intermediate_preset_count": (
                    self.delivery_preset_structured_intermediate_preset_count
                ),
                "delivery_preset_content_visibility_rule_count": (
                    self.delivery_preset_content_visibility_rule_count
                ),
                "delivery_preset_issue_count": self.delivery_preset_issue_count,
                "delivery_execution_channel_count": (
                    self.delivery_execution_channel_count
                ),
                "delivery_execution_ready_channel_count": (
                    self.delivery_execution_ready_channel_count
                ),
                "delivery_execution_required_output_signal_count": (
                    self.delivery_execution_required_output_signal_count
                ),
                "delivery_execution_payload_key_count": (
                    self.delivery_execution_payload_key_count
                ),
                "delivery_execution_runtime_surface_count": (
                    self.delivery_execution_runtime_surface_count
                ),
                "delivery_execution_report_surface_count": (
                    self.delivery_execution_report_surface_count
                ),
                "delivery_execution_ui_surface_count": (
                    self.delivery_execution_ui_surface_count
                ),
                "delivery_execution_test_evidence_count": (
                    self.delivery_execution_test_evidence_count
                ),
                "delivery_execution_covered_pack_count": (
                    self.delivery_execution_covered_pack_count
                ),
                "delivery_execution_covered_family_count": (
                    self.delivery_execution_covered_family_count
                ),
                "delivery_execution_issue_count": self.delivery_execution_issue_count,
                "delivery_execution_missing_source_evidence_count": (
                    self.delivery_execution_missing_source_evidence_count
                ),
                "formula_output_watermark_capability_count": (
                    self.formula_output_watermark_capability_count
                ),
                "formula_output_watermark_ready_capability_count": (
                    self.formula_output_watermark_ready_capability_count
                ),
                "formula_output_watermark_family_count": (
                    self.formula_output_watermark_family_count
                ),
                "formula_output_watermark_ready_family_count": (
                    self.formula_output_watermark_ready_family_count
                ),
                "formula_output_watermark_boundary_family_count": (
                    self.formula_output_watermark_boundary_family_count
                ),
                "formula_output_watermark_accounted_family_count": (
                    self.formula_output_watermark_accounted_family_count
                ),
                "formula_output_watermark_formula_family_count": (
                    self.formula_output_watermark_formula_family_count
                ),
                "formula_output_watermark_output_family_count": (
                    self.formula_output_watermark_output_family_count
                ),
                "formula_output_watermark_watermark_family_count": (
                    self.formula_output_watermark_watermark_family_count
                ),
                "formula_output_watermark_plugin_gate_count": (
                    self.formula_output_watermark_plugin_gate_count
                ),
                "formula_output_watermark_control_contract_count": (
                    self.formula_output_watermark_control_contract_count
                ),
                "formula_output_watermark_parameter_path_count": (
                    self.formula_output_watermark_parameter_path_count
                ),
                "formula_output_watermark_template_baseline_path_count": (
                    self.formula_output_watermark_template_baseline_path_count
                ),
                "formula_output_watermark_issue_count": (
                    self.formula_output_watermark_issue_count
                ),
                "product_readiness_subject_count": (
                    self.product_readiness_subject_count
                ),
                "static_closed_but_not_green_count": (
                    self.static_closed_but_not_green_count
                ),
                "static_closed_not_green_governed_count": (
                    self.static_closed_not_green_governed_count
                ),
                "count_profile_profile_count": self.count_profile_profile_count,
                "count_profile_referenced_profile_count": (
                    self.count_profile_referenced_profile_count
                ),
                "count_profile_rule_source_profile_count": (
                    self.count_profile_rule_source_profile_count
                ),
                "count_profile_registry_only_profile_count": (
                    self.count_profile_registry_only_profile_count
                ),
                "count_profile_rule_source_only_profile_count": (
                    self.count_profile_rule_source_only_profile_count
                ),
                "count_profile_section_limit_profile_count": (
                    self.count_profile_section_limit_profile_count
                ),
                "count_profile_unique_scope_count": (
                    self.count_profile_unique_scope_count
                ),
                "count_profile_unique_primary_metric_count": (
                    self.count_profile_unique_primary_metric_count
                ),
                "count_profile_family_count": self.count_profile_family_count,
                "count_profile_ready_family_count": (
                    self.count_profile_ready_family_count
                ),
                "count_profile_boundary_family_count": (
                    self.count_profile_boundary_family_count
                ),
                "count_profile_accounted_family_count": (
                    self.count_profile_accounted_family_count
                ),
                "count_profile_pack_count": self.count_profile_pack_count,
                "count_profile_count_profile_pack_count": (
                    self.count_profile_count_profile_pack_count
                ),
                "count_profile_ready_count_profile_pack_count": (
                    self.count_profile_ready_count_profile_pack_count
                ),
                "count_profile_runtime_consumer_count": (
                    self.count_profile_runtime_consumer_count
                ),
                "count_profile_report_surface_count": (
                    self.count_profile_report_surface_count
                ),
                "count_profile_issue_count": self.count_profile_issue_count,
                "count_profile_warning_count": self.count_profile_warning_count,
                "count_profile_missing_source_evidence_count": (
                    self.count_profile_missing_source_evidence_count
                ),
                "maturity_upgrade_subject_count": (
                    self.maturity_upgrade_subject_count
                ),
                "maturity_upgrade_green_subject_count": (
                    self.maturity_upgrade_green_subject_count
                ),
                "maturity_upgrade_l5_blocked_subject_count": (
                    self.maturity_upgrade_l5_blocked_subject_count
                ),
                "maturity_upgrade_l3_subject_count": (
                    self.maturity_upgrade_l3_subject_count
                ),
                "maturity_upgrade_l4_subject_count": (
                    self.maturity_upgrade_l4_subject_count
                ),
                "maturity_upgrade_boundary_subject_count": (
                    self.maturity_upgrade_boundary_subject_count
                ),
                "maturity_upgrade_gap_count": self.maturity_upgrade_gap_count,
                "maturity_upgrade_gap_domain_count": (
                    self.maturity_upgrade_gap_domain_count
                ),
                "maturity_upgrade_gap_domain_classified_count": (
                    self.maturity_upgrade_gap_domain_classified_count
                ),
                "maturity_upgrade_issue_count": self.maturity_upgrade_issue_count,
                "maturity_upgrade_warning_count": (
                    self.maturity_upgrade_warning_count
                ),
                "maturity_upgrade_missing_source_evidence_count": (
                    self.maturity_upgrade_missing_source_evidence_count
                ),
            },
            "filters": {
                "pack_options": sorted(row.pack_id for row in self.rows),
                "family_options": sorted(
                    {
                        family_id
                        for row in self.rows
                        for family_id in row.family_ids
                    }
                ),
                "readiness_options": sorted(
                    {row.product_readiness_level for row in self.rows}
                ),
                "boundary_options": sorted(
                    {
                        signal_id
                        for row in self.rows
                        for signal_id in row.boundary_signal_ids
                    }
                ),
                "status_options": sorted({row.status for row in self.rows}),
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
        }


__all__ = [
    "SceneMatrixDashboardCard",
    "SceneMatrixDashboardIssue",
    "SceneMatrixDashboardReport",
    "SceneMatrixDashboardRow",
]
