from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.scene_matrix_release_gate_payload import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
    SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID,
)


RELEASE_GATE_PAYLOAD_CHECK_IDS: tuple[str, ...] = (
    "coverage_pack_completeness",
    "coverage_pack_matrix_alignment",
    "coverage_closure_validation",
    "high_frequency_request_samples",
    "scene_product_readiness",
    "scene_sample_fixtures",
    "scene_request_cell_fixtures",
    "scene_sample_fixture_library",
    "scene_request_cell_release_threshold",
    "scene_request_cell_registry_browser",
    "high_frequency_completeness_audit",
    "high_frequency_task_lexicon_audit",
    "scene_ambiguous_boundary_audit",
    "scene_ambiguity_clarification_ui_audit",
    "scene_import_handoff_audit",
    "scene_input_source_audit",
    "scene_family_subscene_audit",
    "scene_family_fixture_depth_audit",
    "scene_control_consistency_audit",
    "scene_control_runtime_consistency_audit",
    "scene_count_profile_audit",
    "scene_word_risk_closure_audit",
    "scene_object_preflight_action_audit",
    "scene_user_journey_fixture_audit",
    "scene_business_capability_matrix_audit",
    "scene_boundary_capability_matrix",
    "scene_plugin_boundary_confirmation_audit",
    "scene_external_handoff_contract_audit",
    *SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS,
    "scene_material_schema_audit",
    "scene_material_repair_flow_audit",
    "scene_fixed_layout_profile_audit",
    "scene_report_artifact_drilldown_audit",
    "scene_delivery_preset_audit",
    "scene_delivery_preset_execution_audit",
    "scene_formula_output_watermark_audit",
    "scene_product_maturity_upgrade_audit",
    "scene_matrix_dashboard",
    *SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID,
    "scene_matrix_drilldown",
)


RELEASE_GATE_RELEASE_GOVERNANCE_SOURCE_MARKER_IDS: tuple[str, ...] = (
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
    "scene_release_acceptance_certificate_audit",
    "scene_release_residual_explanation_audit",
)


RELEASE_GATE_HUMAN_SUMMARY_PARTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("{coverage_pack_count} packs", ("coverage_pack_count",)),
    ("high_frequency_coverage={high_frequency_completeness_ready_pack_count}/{high_frequency_completeness_pack_count}", ("high_frequency_completeness_ready_pack_count", "high_frequency_completeness_pack_count")),
    ("{sample_fixture_count} sample fixtures", ("sample_fixture_count",)),
    ("{high_frequency_request_sample_count} request samples", ("high_frequency_request_sample_count",)),
    ("{request_cell_count} request cells", ("request_cell_count",)),
    ("family_proxy={request_cell_family_proxy_count}", ("request_cell_family_proxy_count",)),
    ("product_readiness_subjects={product_readiness_subject_count}", ("product_readiness_subject_count",)),
    ("task_lexicon={high_frequency_task_lexicon_task_count}", ("high_frequency_task_lexicon_task_count",)),
    ("ambiguous_boundaries={scene_ambiguous_boundary_count}", ("scene_ambiguous_boundary_count",)),
    ("ambiguity_clarifications={scene_ambiguity_clarification_ready_count}/{scene_ambiguity_clarification_count}", ("scene_ambiguity_clarification_ready_count", "scene_ambiguity_clarification_count")),
    ("import_handoffs={scene_import_handoff_count}", ("scene_import_handoff_count",)),
    ("input_sources={scene_input_source_ready_input_pack_count}/{scene_input_source_input_pack_count}", ("scene_input_source_ready_input_pack_count", "scene_input_source_input_pack_count")),
    ("family_subscenes={scene_family_subscene_family_count}", ("scene_family_subscene_family_count",)),
    ("family_fixture_p1={scene_family_fixture_depth_p1_ready_count}/{scene_family_fixture_depth_p1_family_count}", ("scene_family_fixture_depth_p1_ready_count", "scene_family_fixture_depth_p1_family_count")),
    ("control_runtime={scene_control_runtime_ready_control_count}/{scene_control_runtime_control_count}", ("scene_control_runtime_ready_control_count", "scene_control_runtime_control_count")),
    ("count_profiles={scene_count_profile_ready_family_count}/{scene_count_profile_family_count} ready", ("scene_count_profile_ready_family_count", "scene_count_profile_family_count")),
    ("CountProfile accounted: count_profile_accounted={scene_count_profile_accounted_family_count}/{scene_count_profile_family_count}", ("scene_count_profile_accounted_family_count", "scene_count_profile_family_count")),
    ("word_risk_surfaces={scene_word_risk_surface_count}", ("scene_word_risk_surface_count",)),
    ("object_preflight_actions={scene_object_preflight_action_ready_target_count}/{scene_object_preflight_action_target_count}", ("scene_object_preflight_action_ready_target_count", "scene_object_preflight_action_target_count")),
    ("user_journeys={scene_user_journey_ready_pack_count}/{scene_user_journey_pack_count} packs/{scene_user_journey_path_count} paths", ("scene_user_journey_ready_pack_count", "scene_user_journey_pack_count", "scene_user_journey_path_count")),
    ("business_capabilities={scene_business_capability_matrix_ready_count}/{scene_business_capability_matrix_count} ({scene_business_capability_matrix_missing_journey_group_count} gaps)", ("scene_business_capability_matrix_ready_count", "scene_business_capability_matrix_count", "scene_business_capability_matrix_missing_journey_group_count")),
    ("boundary_capabilities={scene_boundary_capability_ready_count}/{scene_boundary_capability_count}", ("scene_boundary_capability_ready_count", "scene_boundary_capability_count")),
    ("boundary_risks={scene_boundary_capability_risk_domain_count}", ("scene_boundary_capability_risk_domain_count",)),
    ("boundary_receipts={scene_boundary_capability_external_receipt_count}", ("scene_boundary_capability_external_receipt_count",)),
    ("plugin_boundary_gates={scene_plugin_boundary_gate_count}", ("scene_plugin_boundary_gate_count",)),
    ("external_handoffs={scene_external_handoff_contract_ready_count}/{scene_external_handoff_contract_count}", ("scene_external_handoff_contract_ready_count", "scene_external_handoff_contract_count")),
    ("boundary guarded: boundary_guarded={scene_boundary_guarded_completion_ready_count}/{scene_boundary_guarded_completion_subject_count}", ("scene_boundary_guarded_completion_ready_count", "scene_boundary_guarded_completion_subject_count")),
    ("managed warnings: managed_warnings={scene_residual_warning_governance_managed_count}/{scene_residual_warning_governance_warning_count} (unmanaged={scene_residual_warning_governance_unmanaged_warning_count})", ("scene_residual_warning_governance_managed_count", "scene_residual_warning_governance_warning_count", "scene_residual_warning_governance_unmanaged_warning_count")),
    ("input_warnings={input_source_warning_managed_count}/{scene_input_source_warning_count} managed", ("input_source_warning_managed_count", "scene_input_source_warning_count")),
    ("count_profile_warnings={count_profile_warning_managed_count}/{scene_count_profile_warning_count} managed", ("count_profile_warning_managed_count", "scene_count_profile_warning_count")),
    ("plugin_manual_warnings={plugin_manual_warning_managed_count}/{scene_residual_warning_governance_plugin_manual_warning_count} managed", ("plugin_manual_warning_managed_count", "scene_residual_warning_governance_plugin_manual_warning_count")),
    ("reference_profile_warnings={reference_profile_warning_managed_count}/{scene_residual_warning_governance_reference_profile_warning_count} managed", ("reference_profile_warning_managed_count", "scene_residual_warning_governance_reference_profile_warning_count")),
    ("visio_fixture={visio_fixture_closed_verified_count}/{scene_residual_warning_governance_visio_fixture_closed_count} closed", ("visio_fixture_closed_verified_count", "scene_residual_warning_governance_visio_fixture_closed_count")),
    ("dashboard_warning_projection={dashboard_warning_projection_governed_count}/{scene_matrix_dashboard_warning_count} governed", ("dashboard_warning_projection_governed_count", "scene_matrix_dashboard_warning_count")),
    ("readiness reconciled: readiness_reconciled={scene_boundary_readiness_reconciliation_reconciled_count}/{scene_boundary_readiness_reconciliation_count}", ("scene_boundary_readiness_reconciliation_reconciled_count", "scene_boundary_readiness_reconciliation_count")),
    ("release exceptions: release_exceptions={scene_terminal_release_exception_governed_count}/{scene_terminal_release_exception_count} (exception traces: traces={scene_terminal_release_exception_trace_count})", ("scene_terminal_release_exception_governed_count", "scene_terminal_release_exception_count", "scene_terminal_release_exception_trace_count")),
    ("static_closed_not_green={static_closed_not_green_governed_count}/{static_closed_but_not_green_count} governed", ("static_closed_not_green_governed_count", "static_closed_but_not_green_count")),
    ("boundary dossiers: boundary_subject_dossiers={scene_boundary_subject_release_dossier_ready_count}/{scene_boundary_subject_release_dossier_subject_count} (traces={scene_boundary_subject_release_dossier_subject_trace_count})", ("scene_boundary_subject_release_dossier_ready_count", "scene_boundary_subject_release_dossier_subject_count", "scene_boundary_subject_release_dossier_subject_trace_count")),
    ("non-subject traces: non_subject_traces={scene_non_subject_release_trace_attribution_ready_count}/{scene_non_subject_release_trace_attribution_count}", ("scene_non_subject_release_trace_attribution_ready_count", "scene_non_subject_release_trace_attribution_count")),
    ("trace partition: trace_partition={scene_release_trace_partition_guard_partitioned_trace_count}/{scene_release_trace_partition_guard_terminal_trace_count}", ("scene_release_trace_partition_guard_partitioned_trace_count", "scene_release_trace_partition_guard_terminal_trace_count")),
    ("Release projection parity / release projections: release_projection={scene_release_projection_surface_parity_ready_count}/{scene_release_projection_surface_parity_count}", ("scene_release_projection_surface_parity_ready_count", "scene_release_projection_surface_parity_count")),
    ("subject continuity: subject_continuity={scene_boundary_subject_release_continuity_ready_count}/{scene_boundary_subject_release_continuity_subject_count}", ("scene_boundary_subject_release_continuity_ready_count", "scene_boundary_subject_release_continuity_subject_count")),
    ("Release closure ledger: release_ledger={scene_release_closure_ledger_ready_count}/{scene_release_closure_ledger_stage_count}", ("scene_release_closure_ledger_ready_count", "scene_release_closure_ledger_stage_count")),
    ("boundary release envelopes: boundary_envelopes={scene_boundary_maturity_release_envelope_ready_count}/{scene_boundary_maturity_release_envelope_count}", ("scene_boundary_maturity_release_envelope_ready_count", "scene_boundary_maturity_release_envelope_count")),
    ("L5 blockers enveloped: maturity_l5_enveloped={scene_boundary_maturity_release_envelope_l5_blocker_enveloped_count}/{scene_product_maturity_upgrade_l5_blocked_subject_count}", ("scene_boundary_maturity_release_envelope_l5_blocker_enveloped_count", "scene_product_maturity_upgrade_l5_blocked_subject_count")),
    ("L5 blockers aligned: maturity_l5_alignment={scene_release_residual_ratio_ledger_maturity_l5_blocker_alignment_count}/{scene_release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count}", ("scene_release_residual_ratio_ledger_maturity_l5_blocker_alignment_count", "scene_release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count")),
    ("L5 receipts aligned: maturity_l5_receipts={scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count}/{scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count}", ("scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count", "scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count")),
    ("boundary scopes guarded: boundary_scope_alignment={scene_release_residual_ratio_ledger_boundary_scope_alignment_count}/{scene_release_residual_ratio_ledger_boundary_scope_link_count}", ("scene_release_residual_ratio_ledger_boundary_scope_alignment_count", "scene_release_residual_ratio_ledger_boundary_scope_link_count")),
    ("retained_gaps={retained_gap_enveloped_count}/{scene_product_maturity_upgrade_gap_count} enveloped", ("retained_gap_enveloped_count", "scene_product_maturity_upgrade_gap_count")),
    ("retained gap exit criteria: retained_gap_exit_criteria={scene_retained_gap_exit_criteria_release_allowed_count}/{scene_retained_gap_exit_criteria_count} release-allowed", ("scene_retained_gap_exit_criteria_release_allowed_count", "scene_retained_gap_exit_criteria_count")),
    ("retained gap receipts: retained_gap_receipts={scene_retained_gap_external_receipt_alignment_count}/{scene_retained_gap_exit_criteria_count} aligned", ("scene_retained_gap_external_receipt_alignment_count", "scene_retained_gap_exit_criteria_count")),
    ("gap_domains={gap_domain_classified_count}/{scene_product_maturity_upgrade_gap_domain_count} classified", ("gap_domain_classified_count", "scene_product_maturity_upgrade_gap_domain_count")),
    ("release residual ratios: residual_ratios={scene_release_residual_ratio_ledger_published_count}/{scene_release_residual_ratio_ledger_count}", ("scene_release_residual_ratio_ledger_published_count", "scene_release_residual_ratio_ledger_count")),
    ("residual_ratio_exit_criteria={scene_release_residual_ratio_ledger_exit_criteria_link_count}/{scene_release_residual_ratio_ledger_release_envelope_link_count}", ("scene_release_residual_ratio_ledger_exit_criteria_link_count", "scene_release_residual_ratio_ledger_release_envelope_link_count")),
    ("residual ratio receipts: residual_ratio_receipts={scene_release_residual_ratio_ledger_receipt_alignment_link_count}/{scene_release_residual_ratio_ledger_exit_criteria_link_count}", ("scene_release_residual_ratio_ledger_receipt_alignment_link_count", "scene_release_residual_ratio_ledger_exit_criteria_link_count")),
    ("count/delivery boundary links aligned: count_delivery_alignment={scene_release_residual_ratio_ledger_count_delivery_boundary_alignment_count}/{scene_release_residual_ratio_ledger_count_delivery_boundary_link_count}", ("scene_release_residual_ratio_ledger_count_delivery_boundary_alignment_count", "scene_release_residual_ratio_ledger_count_delivery_boundary_link_count")),
    ("count/delivery receipts aligned: count_delivery_receipts={scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_count}/{scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count}", ("scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_count", "scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count")),
    ("residual explanations: residual_explanations={scene_release_residual_explanation_covered_count}/{scene_release_residual_explanation_count} covered", ("scene_release_residual_explanation_covered_count", "scene_release_residual_explanation_count")),
    ("release acceptance certificate: acceptance_certificate={scene_release_acceptance_certificate_ready_count}/{scene_release_acceptance_certificate_count}", ("scene_release_acceptance_certificate_ready_count", "scene_release_acceptance_certificate_count")),
    ("receipt certificates: acceptance_receipts={scene_release_acceptance_certificate_ready_receipt_count}/{scene_release_acceptance_certificate_receipt_count}", ("scene_release_acceptance_certificate_ready_receipt_count", "scene_release_acceptance_certificate_receipt_count")),
    ("requirement dimensions: requirement_dimensions={scene_release_acceptance_certificate_ready_requirement_dimension_count}/{scene_release_acceptance_certificate_requirement_dimension_count}", ("scene_release_acceptance_certificate_ready_requirement_dimension_count", "scene_release_acceptance_certificate_requirement_dimension_count")),
    ("acceptance evidence: acceptance_evidence={scene_release_acceptance_certificate_ready_source_evidence_count}/{scene_release_acceptance_certificate_source_evidence_count}", ("scene_release_acceptance_certificate_ready_source_evidence_count", "scene_release_acceptance_certificate_source_evidence_count")),
    ("release_export_scripts={scene_release_governance_export_script_ready_count}/{scene_release_governance_export_script_report_count} ready", ("scene_release_governance_export_script_ready_count", "scene_release_governance_export_script_report_count")),
    ("material_schema_families={scene_material_schema_ready_material_family_count}/{scene_material_schema_material_family_count}", ("scene_material_schema_ready_material_family_count", "scene_material_schema_material_family_count")),
    ("material_repair_flows={scene_material_repair_flow_ready_count}/{scene_material_repair_flow_count}", ("scene_material_repair_flow_ready_count", "scene_material_repair_flow_count")),
    ("fixed-layout profile: fixed_layout_profile={scene_fixed_layout_profile_ready_channel_count}/{scene_fixed_layout_profile_channel_count}", ("scene_fixed_layout_profile_ready_channel_count", "scene_fixed_layout_profile_channel_count")),
    ("report/artifact drilldown: report_artifact_drilldown={scene_report_artifact_drilldown_ready_channel_count}/{scene_report_artifact_drilldown_channel_count}", ("scene_report_artifact_drilldown_ready_channel_count", "scene_report_artifact_drilldown_channel_count")),
    ("delivery_families={scene_delivery_preset_ready_family_count}/{scene_delivery_preset_family_count} ready", ("scene_delivery_preset_ready_family_count", "scene_delivery_preset_family_count")),
    ("delivery accounted: delivery_family_accounted={scene_delivery_preset_accounted_family_count}/{scene_delivery_preset_family_count}", ("scene_delivery_preset_accounted_family_count", "scene_delivery_preset_family_count")),
    ("delivery_pack_accounted={scene_delivery_preset_accounted_delivery_pack_count}/{scene_delivery_preset_delivery_pack_count}", ("scene_delivery_preset_accounted_delivery_pack_count", "scene_delivery_preset_delivery_pack_count")),
    ("delivery_execution={scene_delivery_execution_ready_channel_count}/{scene_delivery_execution_channel_count}", ("scene_delivery_execution_ready_channel_count", "scene_delivery_execution_channel_count")),
    ("formula_output_watermark={scene_formula_output_watermark_ready_capability_count}/{scene_formula_output_watermark_capability_count}", ("scene_formula_output_watermark_ready_capability_count", "scene_formula_output_watermark_capability_count")),
    ("fow_family_accounted={scene_formula_output_watermark_accounted_family_count}/{scene_formula_output_watermark_family_count}", ("scene_formula_output_watermark_accounted_family_count", "scene_formula_output_watermark_family_count")),
    ("scene_matrix_readiness: maturity_l5_blocked={scene_product_maturity_upgrade_l5_blocked_subject_count}/{scene_product_maturity_upgrade_subject_count}", ("scene_product_maturity_upgrade_l5_blocked_subject_count", "scene_product_maturity_upgrade_subject_count")),
    ("dashboard_packs={scene_matrix_dashboard_pack_count}", ("scene_matrix_dashboard_pack_count",)),
    ("drilldowns={scene_matrix_drilldown_ready_count}/{scene_matrix_drilldown_item_count}", ("scene_matrix_drilldown_ready_count", "scene_matrix_drilldown_item_count")),
    ("drilldown_rows={scene_matrix_drilldown_visible_row_count}/{scene_matrix_drilldown_row_count}", ("scene_matrix_drilldown_visible_row_count", "scene_matrix_drilldown_row_count")),
    ("drilldown_sources={scene_matrix_drilldown_ready_source_evidence_count}/{scene_matrix_drilldown_source_evidence_count} ready", ("scene_matrix_drilldown_ready_source_evidence_count", "scene_matrix_drilldown_source_evidence_count")),
)


def _format_summary_part(
    counts: dict[str, object],
    template: str,
    count_ids: tuple[str, ...],
) -> str:
    return template.format(
        **{count_id: counts[count_id] for count_id in count_ids}
    )


def _print_human(payload: dict[str, object]) -> None:
    print(f"Scene matrix release gate: {payload['status']}")
    for check_id, check in payload["checks"].items():
        print(f"- {check_id}: {check['status']} ({check['issue_count']} issues)")
        for issue in list(check.get("issues") or [])[:5]:
            if isinstance(issue, dict):
                text = issue.get("message") or issue.get("issue") or json.dumps(
                    issue,
                    ensure_ascii=False,
                )
            else:
                text = str(issue)
            print(f"  - {text}")
    counts = payload["counts"]
    summary_parts = tuple(
        _format_summary_part(counts, template, count_ids)
        for template, count_ids in RELEASE_GATE_HUMAN_SUMMARY_PARTS
    )
    summary_prefix = "[OK]" if payload["status"] == "passed" else "[FAILED]"
    print(f"{summary_prefix} " + ", ".join(summary_parts))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the high-level scene matrix release gate: coverage manifest, "
            "routing samples, product readiness, request-cell fixtures, and "
            "openable DOCX sample library."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for generated temporary sample fixtures. Defaults to a temp dir.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON payload.",
    )
    args = parser.parse_args(argv)

    if args.output_dir:
        output_dir = Path(args.output_dir)
        payload = build_scene_matrix_release_gate_payload(output_dir)
    else:
        with tempfile.TemporaryDirectory(prefix="scene_matrix_gate_") as temp_dir:
            payload = build_scene_matrix_release_gate_payload(Path(temp_dir))

    if args.json:
        # Machine-readable stdout must survive Windows legacy console/code-page
        # encodings. JSON escapes preserve the exact Unicode values while the
        # emitted byte repertoire stays ASCII for callers using ``text=True``.
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        _print_human(payload)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
