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
    "scene_material_schema_audit",
    "scene_material_repair_flow_audit",
    "scene_fixed_layout_profile_audit",
    "scene_report_artifact_drilldown_audit",
    "scene_delivery_preset_audit",
    "scene_delivery_preset_execution_audit",
    "scene_formula_output_watermark_audit",
    "scene_product_maturity_upgrade_audit",
    "scene_matrix_dashboard",
    "scene_release_residual_explanation_audit",
    "scene_release_governance_export_script_evidence",
    "scene_matrix_drilldown",
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
    print(
        "[OK] "
        f"{counts['coverage_pack_count']} packs, "
        f"high_frequency_coverage="
        f"{counts['high_frequency_completeness_ready_pack_count']}/"
        f"{counts['high_frequency_completeness_pack_count']}, "
        f"{counts['sample_fixture_count']} sample fixtures, "
        f"{counts['high_frequency_request_sample_count']} request samples, "
        f"{counts['request_cell_count']} request cells, "
        f"family_proxy={counts['request_cell_family_proxy_count']}, "
        f"product_readiness_subjects={counts['product_readiness_subject_count']}, "
        f"task_lexicon={counts['high_frequency_task_lexicon_task_count']}, "
        f"ambiguous_boundaries={counts['scene_ambiguous_boundary_count']}, "
        f"ambiguity_clarifications="
        f"{counts['scene_ambiguity_clarification_ready_count']}/"
        f"{counts['scene_ambiguity_clarification_count']}, "
        f"import_handoffs={counts['scene_import_handoff_count']}, "
        f"input_sources={counts['scene_input_source_ready_input_pack_count']}/"
        f"{counts['scene_input_source_input_pack_count']}, "
        f"family_subscenes={counts['scene_family_subscene_family_count']}, "
        f"family_fixture_p1={counts['scene_family_fixture_depth_p1_ready_count']}/"
        f"{counts['scene_family_fixture_depth_p1_family_count']}, "
        f"control_runtime={counts['scene_control_runtime_ready_control_count']}/"
        f"{counts['scene_control_runtime_control_count']}, "
        f"count_profiles={counts['scene_count_profile_ready_family_count']}/"
        f"{counts['scene_count_profile_family_count']} ready, "
        f"count_profile_accounted="
        f"{counts['scene_count_profile_accounted_family_count']}/"
        f"{counts['scene_count_profile_family_count']}, "
        f"word_risk_surfaces={counts['scene_word_risk_surface_count']}, "
        f"object_preflight_actions="
        f"{counts['scene_object_preflight_action_ready_target_count']}/"
        f"{counts['scene_object_preflight_action_target_count']}, "
        f"user_journeys={counts['scene_user_journey_ready_pack_count']}/"
        f"{counts['scene_user_journey_pack_count']} packs/"
        f"{counts['scene_user_journey_path_count']} paths, "
        f"business_capabilities="
        f"{counts['scene_business_capability_matrix_ready_count']}/"
        f"{counts['scene_business_capability_matrix_count']} "
        f"({counts['scene_business_capability_matrix_missing_journey_group_count']} gaps), "
        f"boundary_capabilities="
        f"{counts['scene_boundary_capability_ready_count']}/"
        f"{counts['scene_boundary_capability_count']}, "
        f"boundary_risks="
        f"{counts['scene_boundary_capability_risk_domain_count']}, "
        f"boundary_receipts="
        f"{counts['scene_boundary_capability_external_receipt_count']}, "
        f"plugin_boundary_gates={counts['scene_plugin_boundary_gate_count']}, "
        f"external_handoffs={counts['scene_external_handoff_contract_ready_count']}/"
        f"{counts['scene_external_handoff_contract_count']}, "
        f"boundary_guarded="
        f"{counts['scene_boundary_guarded_completion_ready_count']}/"
        f"{counts['scene_boundary_guarded_completion_subject_count']}, "
        f"managed_warnings="
        f"{counts['scene_residual_warning_governance_managed_count']}/"
        f"{counts['scene_residual_warning_governance_warning_count']} "
        f"(unmanaged={counts['scene_residual_warning_governance_unmanaged_warning_count']}), "
        f"input_warnings="
        f"{counts['input_source_warning_managed_count']}/"
        f"{counts['scene_input_source_warning_count']} managed, "
        f"count_profile_warnings="
        f"{counts['count_profile_warning_managed_count']}/"
        f"{counts['scene_count_profile_warning_count']} managed, "
        f"plugin_manual_warnings="
        f"{counts['plugin_manual_warning_managed_count']}/"
        f"{counts['scene_residual_warning_governance_plugin_manual_warning_count']} managed, "
        f"reference_profile_warnings="
        f"{counts['reference_profile_warning_managed_count']}/"
        f"{counts['scene_residual_warning_governance_reference_profile_warning_count']} managed, "
        f"visio_fixture="
        f"{counts['visio_fixture_closed_verified_count']}/"
        f"{counts['scene_residual_warning_governance_visio_fixture_closed_count']} closed, "
        f"dashboard_warning_projection="
        f"{counts['dashboard_warning_projection_governed_count']}/"
        f"{counts['scene_matrix_dashboard_warning_count']} governed, "
        f"readiness_reconciled="
        f"{counts['scene_boundary_readiness_reconciliation_reconciled_count']}/"
        f"{counts['scene_boundary_readiness_reconciliation_count']}, "
        f"release_exceptions="
        f"{counts['scene_terminal_release_exception_governed_count']}/"
        f"{counts['scene_terminal_release_exception_count']} "
        f"(traces={counts['scene_terminal_release_exception_trace_count']}), "
        f"static_closed_not_green="
        f"{counts['static_closed_not_green_governed_count']}/"
        f"{counts['static_closed_but_not_green_count']} governed, "
        f"boundary_subject_dossiers="
        f"{counts['scene_boundary_subject_release_dossier_ready_count']}/"
        f"{counts['scene_boundary_subject_release_dossier_subject_count']} "
        f"(traces={counts['scene_boundary_subject_release_dossier_subject_trace_count']}), "
        f"non_subject_traces="
        f"{counts['scene_non_subject_release_trace_attribution_ready_count']}/"
        f"{counts['scene_non_subject_release_trace_attribution_count']}, "
        f"trace_partition="
        f"{counts['scene_release_trace_partition_guard_partitioned_trace_count']}/"
        f"{counts['scene_release_trace_partition_guard_terminal_trace_count']}, "
        f"release_projection="
        f"{counts['scene_release_projection_surface_parity_ready_count']}/"
        f"{counts['scene_release_projection_surface_parity_count']}, "
        f"subject_continuity="
        f"{counts['scene_boundary_subject_release_continuity_ready_count']}/"
        f"{counts['scene_boundary_subject_release_continuity_subject_count']}, "
        f"release_ledger="
        f"{counts['scene_release_closure_ledger_ready_count']}/"
        f"{counts['scene_release_closure_ledger_stage_count']}, "
        f"boundary_envelopes="
        f"{counts['scene_boundary_maturity_release_envelope_ready_count']}/"
        f"{counts['scene_boundary_maturity_release_envelope_count']}, "
        f"maturity_l5_enveloped="
        f"{counts['scene_boundary_maturity_release_envelope_l5_blocker_enveloped_count']}/"
        f"{counts['scene_product_maturity_upgrade_l5_blocked_subject_count']}, "
        f"maturity_l5_alignment="
        f"{counts['scene_release_residual_ratio_ledger_maturity_l5_blocker_alignment_count']}/"
        f"{counts['scene_release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count']}, "
        f"maturity_l5_receipts="
        f"{counts['scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count']}/"
        f"{counts['scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count']}, "
        f"boundary_scope_alignment="
        f"{counts['scene_release_residual_ratio_ledger_boundary_scope_alignment_count']}/"
        f"{counts['scene_release_residual_ratio_ledger_boundary_scope_link_count']}, "
        f"retained_gaps="
        f"{counts['retained_gap_enveloped_count']}/"
        f"{counts['scene_product_maturity_upgrade_gap_count']} enveloped, "
        f"retained_gap_exit_criteria="
        f"{counts['scene_retained_gap_exit_criteria_release_allowed_count']}/"
        f"{counts['scene_retained_gap_exit_criteria_count']} release-allowed, "
        f"retained_gap_receipts="
        f"{counts['scene_retained_gap_external_receipt_alignment_count']}/"
        f"{counts['scene_retained_gap_exit_criteria_count']} aligned, "
        f"gap_domains="
        f"{counts['gap_domain_classified_count']}/"
        f"{counts['scene_product_maturity_upgrade_gap_domain_count']} classified, "
        f"residual_ratios="
        f"{counts['scene_release_residual_ratio_ledger_published_count']}/"
        f"{counts['scene_release_residual_ratio_ledger_count']}, "
        f"residual_ratio_exit_criteria="
        f"{counts['scene_release_residual_ratio_ledger_exit_criteria_link_count']}/"
        f"{counts['scene_release_residual_ratio_ledger_release_envelope_link_count']}, "
        f"residual_ratio_receipts="
        f"{counts['scene_release_residual_ratio_ledger_receipt_alignment_link_count']}/"
        f"{counts['scene_release_residual_ratio_ledger_exit_criteria_link_count']}, "
        f"count_delivery_alignment="
        f"{counts['scene_release_residual_ratio_ledger_count_delivery_boundary_alignment_count']}/"
        f"{counts['scene_release_residual_ratio_ledger_count_delivery_boundary_link_count']}, "
        f"count_delivery_receipts="
        f"{counts['scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_count']}/"
        f"{counts['scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count']}, "
        f"residual_explanations="
        f"{counts['scene_release_residual_explanation_covered_count']}/"
        f"{counts['scene_release_residual_explanation_count']} covered, "
        f"acceptance_certificate="
        f"{counts['scene_release_acceptance_certificate_ready_count']}/"
        f"{counts['scene_release_acceptance_certificate_count']}, "
        f"acceptance_receipts="
        f"{counts['scene_release_acceptance_certificate_ready_receipt_count']}/"
        f"{counts['scene_release_acceptance_certificate_receipt_count']}, "
        f"requirement_dimensions="
        f"{counts['scene_release_acceptance_certificate_ready_requirement_dimension_count']}/"
        f"{counts['scene_release_acceptance_certificate_requirement_dimension_count']}, "
        f"acceptance_evidence="
        f"{counts['scene_release_acceptance_certificate_ready_source_evidence_count']}/"
        f"{counts['scene_release_acceptance_certificate_source_evidence_count']}, "
        f"release_export_scripts="
        f"{counts['scene_release_governance_export_script_ready_count']}/"
        f"{counts['scene_release_governance_export_script_report_count']} ready, "
        f"material_schema_families="
        f"{counts['scene_material_schema_ready_material_family_count']}/"
        f"{counts['scene_material_schema_material_family_count']}, "
        f"material_repair_flows="
        f"{counts['scene_material_repair_flow_ready_count']}/"
        f"{counts['scene_material_repair_flow_count']}, "
        f"fixed_layout_profile="
        f"{counts['scene_fixed_layout_profile_ready_channel_count']}/"
        f"{counts['scene_fixed_layout_profile_channel_count']}, "
        f"report_artifact_drilldown="
        f"{counts['scene_report_artifact_drilldown_ready_channel_count']}/"
        f"{counts['scene_report_artifact_drilldown_channel_count']}, "
        f"delivery_families={counts['scene_delivery_preset_ready_family_count']}/"
        f"{counts['scene_delivery_preset_family_count']} ready, "
        f"delivery_family_accounted="
        f"{counts['scene_delivery_preset_accounted_family_count']}/"
        f"{counts['scene_delivery_preset_family_count']}, "
        f"delivery_pack_accounted="
        f"{counts['scene_delivery_preset_accounted_delivery_pack_count']}/"
        f"{counts['scene_delivery_preset_delivery_pack_count']}, "
        f"delivery_execution="
        f"{counts['scene_delivery_execution_ready_channel_count']}/"
        f"{counts['scene_delivery_execution_channel_count']}, "
        f"formula_output_watermark="
        f"{counts['scene_formula_output_watermark_ready_capability_count']}/"
        f"{counts['scene_formula_output_watermark_capability_count']}, "
        f"fow_family_accounted="
        f"{counts['scene_formula_output_watermark_accounted_family_count']}/"
        f"{counts['scene_formula_output_watermark_family_count']}, "
        f"maturity_l5_blocked="
        f"{counts['scene_product_maturity_upgrade_l5_blocked_subject_count']}/"
        f"{counts['scene_product_maturity_upgrade_subject_count']}, "
        f"dashboard_packs={counts['scene_matrix_dashboard_pack_count']}, "
        f"drilldowns={counts['scene_matrix_drilldown_ready_count']}/"
        f"{counts['scene_matrix_drilldown_item_count']}, "
        f"drilldown_rows={counts['scene_matrix_drilldown_visible_row_count']}/"
        f"{counts['scene_matrix_drilldown_row_count']}, "
        f"drilldown_sources="
        f"{counts['scene_matrix_drilldown_ready_source_evidence_count']}/"
        f"{counts['scene_matrix_drilldown_source_evidence_count']} ready"
    )


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
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human(payload)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
