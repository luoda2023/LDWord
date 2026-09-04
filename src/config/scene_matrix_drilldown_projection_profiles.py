"""Projection profile definitions for the scene matrix drilldown."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SceneMatrixDrilldownProjectionProfile:
    drilldown_id: str
    source_id: str
    action_source_fields: tuple[str, ...] = ()
    action_token_kinds: tuple[str, ...] = ()
    capability_source_fields: tuple[str, ...] = ()
    capability_token_kinds: tuple[str, ...] = ()


SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILES: tuple[
    SceneMatrixDrilldownProjectionProfile,
    ...,
] = (
    SceneMatrixDrilldownProjectionProfile(
        "ambiguity_clarification",
        "scene_ambiguity_clarification_ui_audit",
        action_source_fields=("decision_record_fields",),
        action_token_kinds=("workflow_action", "decision_record_field"),
        capability_source_fields=("ui_surface_ids",),
        capability_token_kinds=("ui_surface",),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "user_journey_fixture",
        "scene_user_journey_fixture_audit",
        action_source_fields=("journey_type", "expected_behaviors"),
        action_token_kinds=("journey_type", "expected_behavior"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "business_capability_matrix",
        "scene_business_capability_matrix_audit",
        action_source_fields=(
            "journey_type_ids",
            "required_journey_groups",
            "missing_journey_groups",
        ),
        action_token_kinds=("journey_type", "journey_group"),
        capability_source_fields=(
            "group_id",
            "boundary_policy",
            "adopted_external_record_ids",
            "control_alignment_ids",
        ),
        capability_token_kinds=(
            "business_group",
            "boundary_policy",
            "absorbed_record",
            "control_alignment",
        ),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "control_runtime_consistency",
        "scene_control_runtime_consistency_audit",
        action_source_fields=("required_semantics",),
        action_token_kinds=("control_semantic",),
        capability_source_fields=(
            "contract_ids",
            "shared_component_ids",
            "scene_surface_ids",
            "template_surface_ids",
            "runtime_consumer_ids",
        ),
        capability_token_kinds=(
            "contract",
            "shared_component",
            "scene_surface",
            "template_surface",
            "runtime_consumer",
        ),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "external_handoff_contract",
        "scene_external_handoff_contract_audit",
        action_source_fields=(
            "status_ids",
            "failure_policy_ids",
            "payload_field_ids",
        ),
        action_token_kinds=("handoff_status", "failure_policy", "payload_field"),
        capability_source_fields=(
            "gap_id",
            "target_plugin_id",
            "boundary_capability_ids",
            "required_report_ids",
            "ui_surface_ids",
            "excluded_core_claims",
        ),
        capability_token_kinds=(
            "retained_gap",
            "target_plugin",
            "boundary_capability",
            "report",
            "ui_surface",
            "excluded_core_claim",
        ),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "boundary_guarded_completion",
        "scene_boundary_guarded_completion_audit",
        action_source_fields=("evidence_ids",),
        action_token_kinds=("evidence_id",),
        capability_source_fields=(
            "remaining_gap_ids",
            "boundary_capability_ids",
            "external_handoff_contract_ids",
            "target_plugin_ids",
            "report_ids",
            "excluded_core_claims",
        ),
        capability_token_kinds=(
            "retained_gap",
            "boundary_capability",
            "handoff_contract",
            "target_plugin",
            "report",
            "excluded_core_claim",
        ),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "residual_warning_governance",
        "scene_residual_warning_governance_audit",
        action_source_fields=("warning_kind", "governance_mode"),
        action_token_kinds=("warning_kind", "governance_mode"),
        capability_source_fields=(
            "evidence_ids",
            "linked_boundary_subject_ids",
            "linked_profile_ids",
        ),
        capability_token_kinds=("evidence_id", "boundary_subject", "profile_id"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "boundary_readiness_reconciliation",
        "scene_boundary_readiness_reconciliation_audit",
        action_source_fields=("metric_id", "observed_status", "reconciliation_mode"),
        action_token_kinds=("metric", "status", "reconciliation_mode"),
        capability_source_fields=("evidence_ids", "linked_boundary_subject_ids"),
        capability_token_kinds=("evidence_id", "boundary_subject"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "terminal_release_exception",
        "scene_terminal_release_exception_audit",
        action_source_fields=("exception_kind", "status"),
        action_token_kinds=("exception_kind", "status"),
        capability_source_fields=("evidence_ids", "source_ids", "source_trace_ids"),
        capability_token_kinds=("evidence_id", "source_id", "trace_id"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "boundary_subject_release_dossier",
        "scene_boundary_subject_release_dossier_audit",
        action_source_fields=(
            "status",
            "readiness_level",
            "maturity_status",
            "terminal_exception_ids",
        ),
        action_token_kinds=("status", "readiness_level", "maturity_status", "exception_id"),
        capability_source_fields=(
            "evidence_ids",
            "boundary_capability_ids",
            "external_handoff_contract_ids",
            "readiness_reconciliation_row_ids",
            "release_exception_trace_ids",
        ),
        capability_token_kinds=(
            "evidence_id",
            "boundary_capability",
            "handoff_contract",
            "readiness_row",
            "release_trace",
        ),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "non_subject_release_trace_attribution",
        "scene_non_subject_release_trace_attribution_audit",
        action_source_fields=("attribution_kind", "terminal_exception_id", "status"),
        action_token_kinds=("attribution_kind", "exception_id", "status"),
        capability_source_fields=(
            "evidence_ids",
            "source_trace_id",
            "surface_source_id",
            "linked_profile_ids",
        ),
        capability_token_kinds=("evidence_id", "trace_id", "source_id", "profile_id"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "release_trace_partition_guard",
        "scene_release_trace_partition_guard_audit",
        action_source_fields=("status",),
        action_token_kinds=("status",),
        capability_source_fields=("evidence_ids", "trace_ids"),
        capability_token_kinds=("evidence_id", "trace_id"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "release_projection_surface_parity",
        "scene_release_projection_surface_parity_audit",
        action_source_fields=(
            "release_gate_check_id",
            "dashboard_card_id",
            "drilldown_id",
            "status",
        ),
        action_token_kinds=("release_gate_check", "dashboard_card", "drilldown_id", "status"),
        capability_source_fields=(
            "evidence_ids",
            "audit_source_id",
            "summary_marker",
            "export_script_path",
            "test_path",
            "closure_doc_path",
            "supplemental_closure_doc_paths",
        ),
        capability_token_kinds=("evidence_id", "source_id", "summary_marker", "path"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "boundary_subject_release_continuity",
        "scene_boundary_subject_release_continuity_audit",
        action_source_fields=(
            "status",
            "in_maturity",
            "in_guarded_completion",
            "in_readiness_reconciliation",
            "in_terminal_release_exception",
            "in_subject_dossier",
        ),
        action_token_kinds=("status", "continuity_presence"),
        capability_source_fields=(
            "evidence_ids",
            "readiness_row_ids",
            "terminal_trace_ids",
            "dossier_trace_ids",
        ),
        capability_token_kinds=("evidence_id", "readiness_row", "terminal_trace", "dossier_trace"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "release_closure_ledger",
        "scene_release_closure_ledger_audit",
        action_source_fields=(
            "status",
            "release_gate_check_id",
            "dashboard_card_id",
            "drilldown_id",
            "summary_marker",
        ),
        action_token_kinds=("status", "release_gate_check", "dashboard_card", "drilldown_id", "summary_marker"),
        capability_source_fields=(
            "evidence_ids",
            "upstream_stage_ids",
            "n2_id",
            "source_id",
            "export_script_path",
            "test_path",
            "closure_doc_path",
            "supplemental_closure_doc_paths",
        ),
        capability_token_kinds=("evidence_id", "release_stage", "n2_id", "source_id", "path"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "boundary_maturity_release_envelope",
        "scene_boundary_maturity_release_envelope_audit",
        action_source_fields=(
            "status",
            "guarded_completion_status",
            "readiness_reconciliation_mode",
            "terminal_exception_status",
            "dossier_status",
        ),
        action_token_kinds=("status", "release_layer_status"),
        capability_source_fields=(
            "evidence_ids",
            "gap_id",
            "readiness_row_ids",
            "terminal_trace_ids",
            "dossier_trace_ids",
        ),
        capability_token_kinds=("evidence_id", "retained_gap", "readiness_row", "trace_id"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "retained_gap_exit_criteria",
        "scene_retained_gap_exit_criteria_audit",
        action_source_fields=(
            "status",
            "release_envelope_id",
            "external_handoff_contract_id",
            "guarded_completion_status",
            "release_condition_ids",
        ),
        action_token_kinds=("status", "release_envelope", "handoff_contract", "release_condition"),
        capability_source_fields=(
            "gap_id",
            "exit_signal_ids",
            "prohibited_core_claim_ids",
        ),
        capability_token_kinds=("retained_gap", "exit_signal", "prohibited_core_claim"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "release_residual_ratio_ledger",
        "scene_release_residual_ratio_ledger_audit",
        action_source_fields=(
            "status",
            "residual_mode",
            "terminal_exception_ids",
            "derived_receipt_action_ids",
            "derived_boundary_scope_action_ids",
        ),
        action_token_kinds=("status", "residual_mode", "exception_id", "derived_marker"),
        capability_source_fields=(
            "evidence_ids",
            "readiness_reconciliation_row_ids",
            "release_envelope_ids",
            "retained_gap_exit_criteria_ids",
            "retained_gap_receipt_alignment_ids",
            "derived_boundary_capability_ids",
        ),
        capability_token_kinds=("evidence_id", "readiness_row", "release_envelope", "receipt_alignment", "boundary_capability"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "release_residual_explanation",
        "scene_release_residual_explanation_audit",
        action_source_fields=("status", "summary_marker"),
        action_token_kinds=("status", "summary_marker"),
        capability_source_fields=("residual_id", "static_capability_ids"),
        capability_token_kinds=("residual_id", "release_explanation_marker"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "release_acceptance_certificate",
        "scene_release_acceptance_certificate_audit",
        action_source_fields=("status", "derived_acceptance_receipt_trace", "requirement_dimension_trace"),
        action_token_kinds=("status", "acceptance_trace", "requirement_dimension_trace"),
        capability_source_fields=(
            "evidence_ids",
            "audit_source_ids",
            "requirement_dimension_ids",
        ),
        capability_token_kinds=("evidence_id", "source_id", "requirement_dimension"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "object_preflight_action",
        "scene_object_preflight_action_audit",
        action_source_fields=("action_behavior_ids",),
        action_token_kinds=("object_preflight_action",),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "material_repair_flow",
        "scene_material_repair_flow_audit",
        action_source_fields=(
            "coverage_selector",
            "repair_target_types",
            "runtime_surface_ids",
        ),
        action_token_kinds=("coverage_selector", "repair_target", "runtime_surface"),
        capability_source_fields=("capability_ids", "ui_surface_ids", "test_ids"),
        capability_token_kinds=("capability", "ui_surface", "test_id"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "fixed_layout_profile",
        "scene_fixed_layout_profile_audit",
        action_source_fields=(
            "coverage_selector",
            "repair_target_types",
            "runtime_surface_ids",
        ),
        action_token_kinds=("coverage_selector", "repair_target", "runtime_surface"),
        capability_source_fields=(
            "word_ooxml_touchpoints",
            "ui_surface_ids",
            "report_surface_ids",
            "test_ids",
        ),
        capability_token_kinds=("word_ooxml_touchpoint", "ui_surface", "report_surface", "test_id"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "report_artifact_drilldown",
        "scene_report_artifact_drilldown_audit",
        action_source_fields=(
            "coverage_selector",
            "repair_target_types",
            "runtime_surface_ids",
        ),
        action_token_kinds=("coverage_selector", "repair_target", "runtime_surface"),
        capability_source_fields=(
            "artifact_kind_ids",
            "ui_surface_ids",
            "report_surface_ids",
            "test_ids",
        ),
        capability_token_kinds=(
            "artifact_kind",
            "ui_surface",
            "report_surface",
            "test_id",
        ),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "delivery_execution",
        "scene_delivery_preset_execution_audit",
        action_source_fields=(
            "coverage_selector",
            "payload_keys",
            "runtime_surface_ids",
        ),
        action_token_kinds=("coverage_selector", "payload_key", "runtime_surface"),
        capability_source_fields=(
            "required_output_signal_ids",
            "report_surface_ids",
            "ui_surface_ids",
        ),
        capability_token_kinds=("output_signal", "report_surface", "ui_surface"),
    ),
    SceneMatrixDrilldownProjectionProfile(
        "formula_output_watermark",
        "scene_formula_output_watermark_audit",
        action_source_fields=("expected_owner_layer",),
        action_token_kinds=("owner_layer",),
        capability_source_fields=(
            "capability_ids",
            "parameter_paths",
            "template_baseline_paths",
            "control_contract_ids",
            "execution_consumers",
        ),
        capability_token_kinds=(
            "formula_output_watermark_capability",
            "parameter_path",
            "template_baseline_path",
            "control_contract",
            "execution_consumer",
        ),
    ),
)


SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP: dict[
    str,
    SceneMatrixDrilldownProjectionProfile,
] = {
    profile.drilldown_id: profile
    for profile in SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILES
}


__all__ = [
    "SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILES",
    "SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP",
    "SceneMatrixDrilldownProjectionProfile",
]
