"""Global dashboard model for the high-level scene capability matrix.

N2.159 turns the separate scene-matrix audits into one front-end-friendly
payload.  The dashboard does not create new scene promises; it exposes whether
each high-frequency pack can be explained through request cells, carrier
layers, fact sources, workflows, Word risks, control contracts, boundaries,
evidence, and product-readiness maturity.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import replace
from functools import lru_cache

from src.config.scene_ambiguous_boundary_audit import (
    build_scene_ambiguous_boundary_audit_report,
)
from src.config.scene_ambiguity_clarification_ui_audit import (
    SceneAmbiguityClarificationRow,
    build_scene_ambiguity_clarification_ui_audit_report,
)
from src.config.scene_control_consistency_audit import (
    build_scene_control_consistency_audit_report,
)
from src.config.scene_control_runtime_consistency_audit import (
    build_scene_control_runtime_consistency_audit_report,
)
from src.config.scene_count_profile_audit import (
    build_scene_count_profile_audit_report,
)
from src.config.scene_delivery_preset_audit import (
    SceneDeliveryPresetPackRow,
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_delivery_preset_execution_audit import (
    SceneDeliveryPresetExecutionRow,
    build_scene_delivery_preset_execution_audit_report,
)
from src.config.scene_family_subscene_audit import (
    SceneFamilySubsceneAuditRow,
    build_scene_family_subscene_audit_report,
)
from src.config.scene_family_fixture_depth_audit import (
    build_scene_family_fixture_depth_audit_report,
)
from src.config.scene_formula_output_watermark_audit import (
    build_scene_formula_output_watermark_audit_report,
)
from src.config.scene_high_frequency_completeness_audit import (
    SceneHighFrequencyCompletenessPackRow,
    build_high_frequency_completeness_audit_report,
)
from src.config.scene_business_capability_matrix_audit import (
    SceneBusinessCapabilityRow,
    build_scene_business_capability_matrix_audit_report,
)
from src.config.scene_boundary_capability_matrix import (
    build_scene_boundary_capability_audit_report,
)
from src.config.scene_boundary_guarded_completion_audit import (
    build_scene_boundary_guarded_completion_audit_report,
)
from src.config.scene_residual_warning_governance_audit import (
    build_scene_residual_warning_governance_audit_report,
)
from src.config.scene_boundary_readiness_reconciliation_audit import (
    build_scene_boundary_readiness_reconciliation_audit_report,
)
from src.config.scene_terminal_release_exception_audit import (
    build_scene_terminal_release_exception_audit_report,
)
from src.config.scene_boundary_subject_release_dossier_audit import (
    build_scene_boundary_subject_release_dossier_audit_report,
)
from src.config.scene_non_subject_release_trace_attribution_audit import (
    build_scene_non_subject_release_trace_attribution_audit_report,
)
from src.config.scene_release_trace_partition_guard_audit import (
    build_scene_release_trace_partition_guard_audit_report,
)
from src.config.scene_release_projection_surface_parity_audit import (
    build_scene_release_projection_surface_parity_audit_report,
)
from src.config.scene_boundary_subject_release_continuity_audit import (
    build_scene_boundary_subject_release_continuity_audit_report,
)
from src.config.scene_release_closure_ledger_audit import (
    build_scene_release_closure_ledger_audit_report,
)
from src.config.scene_boundary_maturity_release_envelope_audit import (
    build_scene_boundary_maturity_release_envelope_audit_report,
)
from src.config.scene_retained_gap_exit_criteria_audit import (
    build_scene_retained_gap_exit_criteria_audit_report,
)
from src.config.scene_release_residual_ratio_ledger_audit import (
    build_scene_release_residual_ratio_ledger_audit_report,
)
from src.config.scene_release_residual_explanation_audit import (
    build_scene_release_residual_explanation_audit_report,
)
from src.config.scene_release_acceptance_certificate_audit import (
    build_scene_release_acceptance_certificate_audit_report,
)
from src.config.scene_external_handoff_contract_audit import (
    build_scene_external_handoff_contract_audit_report,
)
from src.config.scene_high_frequency_task_lexicon_audit import (
    build_high_frequency_task_lexicon_audit_report,
)
from src.config.scene_import_handoff_audit import (
    build_scene_import_handoff_audit_report,
)
from src.config.scene_input_source_audit import (
    SceneInputSourcePackRow,
    build_scene_input_source_audit_report,
)
from src.config.scene_material_schema_audit import (
    SceneMaterialSchemaPackRow,
    build_scene_material_schema_audit_report,
)
from src.config.scene_material_repair_flow_audit import (
    SceneMaterialRepairFlowRow,
    build_scene_material_repair_flow_audit_report,
)
from src.config.scene_matrix_dashboard_lenses import (
    SCENE_MATRIX_DASHBOARD_LENSES,
    SCENE_MATRIX_DASHBOARD_LENS_IDS,
    SCENE_MATRIX_DASHBOARD_SOURCE_IDS,
    SceneMatrixDashboardLens,
)
from src.config.scene_matrix_dashboard_models import (
    SceneMatrixDashboardCard,
    SceneMatrixDashboardIssue,
    SceneMatrixDashboardReport,
    SceneMatrixDashboardRow,
)
from src.config.scene_fixed_layout_profile_audit import (
    SceneFixedLayoutProfileRow,
    build_scene_fixed_layout_profile_audit_report,
)
from src.config.scene_report_artifact_drilldown_audit import (
    SceneReportArtifactDrilldownRow,
    build_scene_report_artifact_drilldown_audit_report,
)
from src.config.scene_object_preflight_action_audit import (
    SceneObjectPreflightTargetRow,
    build_scene_object_preflight_action_audit_report,
)
from src.config.scene_product_readiness import (
    SceneProductReadinessSpec,
    list_scene_product_readiness_specs,
    product_readiness_for,
    static_closed_but_not_green_specs,
)
from src.config.scene_product_maturity_upgrade_audit import (
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_plugin_boundary_confirmation_audit import (
    build_scene_plugin_boundary_confirmation_audit_report,
)
from src.config.scene_request_cell_fixture_registry import (
    build_scene_request_cell_fixture_summary,
    build_scene_request_cell_registry_browser,
)
from src.config.scene_sample_fixture_registry import list_scene_sample_fixtures
from src.config.scene_user_journey_fixture_audit import (
    SceneUserJourneyPackRow,
    build_scene_user_journey_fixture_audit_report,
)
from src.config.scene_word_risk_closure_audit import (
    SceneWordRiskClosureRow,
    build_scene_word_risk_closure_audit_report,
)


def _pytest_scene_matrix_dashboard_cache_enabled() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and not bool(
        os.environ.get("LARK_DISABLE_SCENE_MATRIX_TEST_CACHE")
    )


@lru_cache(maxsize=1)
def _cached_scene_matrix_dashboard_base() -> SceneMatrixDashboardReport:
    return _build_scene_matrix_dashboard_uncached()


def build_scene_matrix_dashboard(
    *,
    pack_id: str = "",
    family_id: str = "",
    readiness_level: str = "",
    boundary_signal: str = "",
    status: str = "",
) -> SceneMatrixDashboardReport:
    """Build a filterable global dashboard payload for scene-matrix completeness."""

    normalized_pack = str(pack_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_readiness = str(readiness_level or "").strip()
    normalized_boundary = str(boundary_signal or "").strip()
    normalized_status = str(status or "").strip()
    if _pytest_scene_matrix_dashboard_cache_enabled():
        base = _cached_scene_matrix_dashboard_base()
        if not (
            normalized_pack
            or normalized_family
            or normalized_readiness
            or normalized_boundary
            or normalized_status
        ):
            return base
        return replace(
            base,
            rows=_filter_rows(
                base.rows,
                pack_id=normalized_pack,
                family_id=normalized_family,
                readiness_level=normalized_readiness,
                boundary_signal=normalized_boundary,
                status=normalized_status,
            ),
            pack_filter=normalized_pack,
            family_filter=normalized_family,
            readiness_filter=normalized_readiness,
            boundary_filter=normalized_boundary,
            status_filter=normalized_status,
        )
    return _build_scene_matrix_dashboard_uncached(
        pack_id=normalized_pack,
        family_id=normalized_family,
        readiness_level=normalized_readiness,
        boundary_signal=normalized_boundary,
        status=normalized_status,
    )


def _build_scene_matrix_dashboard_uncached(
    *,
    pack_id: str = "",
    family_id: str = "",
    readiness_level: str = "",
    boundary_signal: str = "",
    status: str = "",
) -> SceneMatrixDashboardReport:
    """Build a filterable global dashboard payload for scene-matrix completeness."""

    pack_report = build_high_frequency_completeness_audit_report()
    task_lexicon_report = build_high_frequency_task_lexicon_audit_report()
    ambiguous_boundary_report = build_scene_ambiguous_boundary_audit_report()
    ambiguity_clarification_report = (
        build_scene_ambiguity_clarification_ui_audit_report()
    )
    import_handoff_report = build_scene_import_handoff_audit_report()
    input_source_report = build_scene_input_source_audit_report()
    family_report = build_scene_family_subscene_audit_report()
    family_fixture_depth_report = build_scene_family_fixture_depth_audit_report()
    control_report = build_scene_control_consistency_audit_report()
    control_runtime_report = build_scene_control_runtime_consistency_audit_report()
    count_profile_report = build_scene_count_profile_audit_report()
    word_risk_report = build_scene_word_risk_closure_audit_report()
    object_preflight_action_report = (
        build_scene_object_preflight_action_audit_report()
    )
    user_journey_fixture_report = build_scene_user_journey_fixture_audit_report()
    business_capability_matrix_report = (
        build_scene_business_capability_matrix_audit_report()
    )
    boundary_capability_report = build_scene_boundary_capability_audit_report()
    plugin_boundary_report = build_scene_plugin_boundary_confirmation_audit_report()
    external_handoff_contract_report = (
        build_scene_external_handoff_contract_audit_report()
    )
    boundary_guarded_completion_report = (
        build_scene_boundary_guarded_completion_audit_report()
    )
    residual_warning_governance_report = (
        build_scene_residual_warning_governance_audit_report()
    )
    boundary_readiness_reconciliation_report = (
        build_scene_boundary_readiness_reconciliation_audit_report()
    )
    terminal_release_exception_report = (
        build_scene_terminal_release_exception_audit_report()
    )
    boundary_subject_release_dossier_report = (
        build_scene_boundary_subject_release_dossier_audit_report()
    )
    non_subject_release_trace_attribution_report = (
        build_scene_non_subject_release_trace_attribution_audit_report()
    )
    release_trace_partition_guard_report = (
        build_scene_release_trace_partition_guard_audit_report()
    )
    release_projection_surface_parity_report = (
        build_scene_release_projection_surface_parity_audit_report()
    )
    boundary_subject_release_continuity_report = (
        build_scene_boundary_subject_release_continuity_audit_report()
    )
    release_closure_ledger_report = build_scene_release_closure_ledger_audit_report()
    boundary_maturity_release_envelope_report = (
        build_scene_boundary_maturity_release_envelope_audit_report()
    )
    retained_gap_exit_criteria_report = (
        build_scene_retained_gap_exit_criteria_audit_report(
            boundary_maturity_release_envelope_report=(
                boundary_maturity_release_envelope_report
            ),
            external_handoff_contract_report=external_handoff_contract_report,
            boundary_guarded_completion_report=boundary_guarded_completion_report,
        )
    )
    release_residual_ratio_ledger_report = (
        build_scene_release_residual_ratio_ledger_audit_report()
    )
    release_acceptance_certificate_report = (
        build_scene_release_acceptance_certificate_audit_report()
    )
    material_schema_report = build_scene_material_schema_audit_report()
    material_repair_flow_report = build_scene_material_repair_flow_audit_report()
    fixed_layout_profile_report = build_scene_fixed_layout_profile_audit_report()
    report_artifact_drilldown_report = (
        build_scene_report_artifact_drilldown_audit_report()
    )
    delivery_preset_report = build_scene_delivery_preset_audit_report()
    delivery_execution_report = build_scene_delivery_preset_execution_audit_report()
    formula_output_watermark_report = (
        build_scene_formula_output_watermark_audit_report()
    )
    maturity_upgrade_report = build_scene_product_maturity_upgrade_audit_report()
    request_summary = build_scene_request_cell_fixture_summary()
    request_browser = build_scene_request_cell_registry_browser()
    all_rows = tuple(
        _build_dashboard_row(
            pack_row,
            family_rows=family_report.rows,
            material_pack_rows=material_schema_report.pack_rows,
            material_repair_flow_rows=material_repair_flow_report.rows,
            fixed_layout_profile_rows=fixed_layout_profile_report.rows,
            report_artifact_drilldown_rows=report_artifact_drilldown_report.rows,
            delivery_pack_rows=delivery_preset_report.pack_rows,
            delivery_execution_rows=delivery_execution_report.rows,
            input_pack_rows=input_source_report.pack_rows,
            ambiguity_clarification_rows=ambiguity_clarification_report.rows,
            object_preflight_target_rows=(
                object_preflight_action_report.target_rows
            ),
            user_journey_pack_rows=user_journey_fixture_report.pack_rows,
            business_capability_rows=business_capability_matrix_report.rows,
            control_contract_count=control_report.contract_count,
            control_contract_issue_count=control_report.issue_count,
            control_runtime_control_count=(
                control_runtime_report.runtime_control_count
            ),
            control_runtime_issue_count=control_runtime_report.issue_count,
            word_risk_rows=word_risk_report.rows,
        )
        for pack_row in pack_report.rows
    )
    rows = _filter_rows(
        all_rows,
        pack_id=pack_id,
        family_id=family_id,
        readiness_level=readiness_level,
        boundary_signal=boundary_signal,
        status=status,
    )
    issues, warnings = _dashboard_issues(
        rows=all_rows,
        pack_report=pack_report,
        task_lexicon_report=task_lexicon_report,
        ambiguous_boundary_report=ambiguous_boundary_report,
        ambiguity_clarification_report=ambiguity_clarification_report,
        import_handoff_report=import_handoff_report,
        input_source_report=input_source_report,
        family_report=family_report,
        family_fixture_depth_report=family_fixture_depth_report,
        control_report=control_report,
        control_runtime_report=control_runtime_report,
        count_profile_report=count_profile_report,
        word_risk_report=word_risk_report,
        object_preflight_action_report=object_preflight_action_report,
        user_journey_fixture_report=user_journey_fixture_report,
        business_capability_matrix_report=business_capability_matrix_report,
        boundary_capability_report=boundary_capability_report,
        plugin_boundary_report=plugin_boundary_report,
        external_handoff_contract_report=external_handoff_contract_report,
        boundary_guarded_completion_report=boundary_guarded_completion_report,
        residual_warning_governance_report=residual_warning_governance_report,
        boundary_readiness_reconciliation_report=(
            boundary_readiness_reconciliation_report
        ),
        terminal_release_exception_report=terminal_release_exception_report,
        boundary_subject_release_dossier_report=(
            boundary_subject_release_dossier_report
        ),
        non_subject_release_trace_attribution_report=(
            non_subject_release_trace_attribution_report
        ),
        release_trace_partition_guard_report=release_trace_partition_guard_report,
        release_projection_surface_parity_report=(
            release_projection_surface_parity_report
        ),
        boundary_subject_release_continuity_report=(
            boundary_subject_release_continuity_report
        ),
        release_closure_ledger_report=release_closure_ledger_report,
        boundary_maturity_release_envelope_report=(
            boundary_maturity_release_envelope_report
        ),
        retained_gap_exit_criteria_report=retained_gap_exit_criteria_report,
        release_residual_ratio_ledger_report=(
            release_residual_ratio_ledger_report
        ),
        release_acceptance_certificate_report=(
            release_acceptance_certificate_report
        ),
        material_schema_report=material_schema_report,
        material_repair_flow_report=material_repair_flow_report,
        fixed_layout_profile_report=fixed_layout_profile_report,
        report_artifact_drilldown_report=report_artifact_drilldown_report,
        delivery_preset_report=delivery_preset_report,
        delivery_execution_report=delivery_execution_report,
        formula_output_watermark_report=formula_output_watermark_report,
        maturity_upgrade_report=maturity_upgrade_report,
        request_summary=request_summary,
        request_browser=request_browser,
        sample_fixture_count=len(list_scene_sample_fixtures()),
    )
    release_residual_explanation_report = (
        build_scene_release_residual_explanation_audit_report(
            input_source_report=input_source_report,
            count_profile_report=count_profile_report,
            residual_warning_governance_report=residual_warning_governance_report,
            terminal_release_exception_report=terminal_release_exception_report,
            boundary_maturity_release_envelope_report=(
                boundary_maturity_release_envelope_report
            ),
            release_residual_ratio_ledger_report=(
                release_residual_ratio_ledger_report
            ),
            maturity_upgrade_report=maturity_upgrade_report,
            dashboard_warning_count=len(warnings),
        )
    )
    if release_residual_explanation_report.issues:
        issue_list = list(issues)
        _extend_source_issues(
            issue_list,
            "release_residual_explanation",
            release_residual_explanation_report.issues,
        )
        issues = tuple(issue_list)
    cards = _dashboard_cards(
        rows=all_rows,
        request_cell_count=request_summary.cell_count,
        task_lexicon_task_count=task_lexicon_report.task_count,
        task_lexicon_phrase_count=task_lexicon_report.phrase_count,
        task_lexicon_negative_task_count=task_lexicon_report.negative_task_count,
        high_frequency_ready_pack_count=pack_report.ready_pack_count,
        ambiguous_boundary_pack_pair_count=(
            ambiguous_boundary_report.pack_pair_count
        ),
        ambiguity_clarification_report=ambiguity_clarification_report,
        import_handoff_count=import_handoff_report.handoff_count,
        input_source_report=input_source_report,
        family_count=family_report.family_count,
        family_fixture_depth_p1_family_count=(
            family_fixture_depth_report.p1_family_count
        ),
        family_fixture_depth_p1_ready_count=(
            family_fixture_depth_report.p1_ready_count
        ),
        sample_fixture_count=len(list_scene_sample_fixtures()),
        control_contract_count=control_report.contract_count,
        control_runtime_report=control_runtime_report,
        count_profile_report=count_profile_report,
        word_risk_surface_count=word_risk_report.surface_count,
        object_preflight_action_report=object_preflight_action_report,
        user_journey_fixture_report=user_journey_fixture_report,
        business_capability_matrix_report=business_capability_matrix_report,
        boundary_capability_report=boundary_capability_report,
        plugin_boundary_gate_count=plugin_boundary_report.gate_count,
        plugin_boundary_risk_domain_count=plugin_boundary_report.risk_domain_count,
        external_handoff_contract_report=external_handoff_contract_report,
        boundary_guarded_completion_report=boundary_guarded_completion_report,
        residual_warning_governance_report=residual_warning_governance_report,
        boundary_readiness_reconciliation_report=(
            boundary_readiness_reconciliation_report
        ),
        terminal_release_exception_report=terminal_release_exception_report,
        boundary_subject_release_dossier_report=(
            boundary_subject_release_dossier_report
        ),
        non_subject_release_trace_attribution_report=(
            non_subject_release_trace_attribution_report
        ),
        release_trace_partition_guard_report=release_trace_partition_guard_report,
        release_projection_surface_parity_report=(
            release_projection_surface_parity_report
        ),
        boundary_subject_release_continuity_report=(
            boundary_subject_release_continuity_report
        ),
        release_closure_ledger_report=release_closure_ledger_report,
        boundary_maturity_release_envelope_report=(
            boundary_maturity_release_envelope_report
        ),
        retained_gap_exit_criteria_report=retained_gap_exit_criteria_report,
        release_residual_ratio_ledger_report=(
            release_residual_ratio_ledger_report
        ),
        release_residual_explanation_report=(
            release_residual_explanation_report
        ),
        release_acceptance_certificate_report=(
            release_acceptance_certificate_report
        ),
        material_schema_report=material_schema_report,
        material_repair_flow_report=material_repair_flow_report,
        fixed_layout_profile_report=fixed_layout_profile_report,
        report_artifact_drilldown_report=report_artifact_drilldown_report,
        delivery_preset_report=delivery_preset_report,
        delivery_execution_report=delivery_execution_report,
        formula_output_watermark_report=formula_output_watermark_report,
        maturity_upgrade_report=maturity_upgrade_report,
        product_readiness_subject_count=len(list_scene_product_readiness_specs()),
        static_closed_but_not_green_count=len(static_closed_but_not_green_specs()),
        issue_count=len(issues),
        warning_count=len(warnings),
    )
    payload_counts = pack_report.to_payload()["counts"]
    user_journey_counts = user_journey_fixture_report.to_payload()["counts"]
    return SceneMatrixDashboardReport(
        rows=rows,
        issues=issues,
        warnings=warnings,
        cards=cards,
        lenses=SCENE_MATRIX_DASHBOARD_LENSES,
        source_ids=SCENE_MATRIX_DASHBOARD_SOURCE_IDS,
        total_count=len(all_rows),
        pack_filter=str(pack_id or "").strip(),
        family_filter=str(family_id or "").strip(),
        readiness_filter=str(readiness_level or "").strip(),
        boundary_filter=str(boundary_signal or "").strip(),
        status_filter=str(status or "").strip(),
        request_cell_count=request_summary.cell_count,
        request_cell_pack_link_count=int(
            payload_counts.get("request_cell_pack_link_count") or 0
        ),
        high_frequency_completeness_ready_pack_count=pack_report.ready_pack_count,
        task_lexicon_task_count=task_lexicon_report.task_count,
        task_lexicon_phrase_count=task_lexicon_report.phrase_count,
        task_lexicon_negative_task_count=task_lexicon_report.negative_task_count,
        task_lexicon_issue_count=task_lexicon_report.issue_count,
        ambiguous_boundary_count=ambiguous_boundary_report.boundary_count,
        ambiguous_boundary_pack_pair_count=ambiguous_boundary_report.pack_pair_count,
        ambiguous_boundary_issue_count=ambiguous_boundary_report.issue_count,
        ambiguity_clarification_count=(
            ambiguity_clarification_report.clarification_count
        ),
        ambiguity_clarification_ready_count=(
            ambiguity_clarification_report.ready_clarification_count
        ),
        ambiguity_clarification_candidate_route_count=(
            ambiguity_clarification_report.candidate_route_count
        ),
        ambiguity_clarification_candidate_pack_count=(
            ambiguity_clarification_report.candidate_pack_count
        ),
        ambiguity_clarification_fixture_backed_count=(
            ambiguity_clarification_report.fixture_backed_count
        ),
        ambiguity_clarification_issue_count=(
            ambiguity_clarification_report.issue_count
        ),
        ambiguity_clarification_warning_count=(
            ambiguity_clarification_report.warning_count
        ),
        ambiguity_clarification_missing_source_evidence_count=(
            ambiguity_clarification_report.missing_source_evidence_count
        ),
        import_handoff_count=import_handoff_report.handoff_count,
        import_handoff_ready_count=import_handoff_report.ready_handoff_count,
        import_handoff_issue_count=import_handoff_report.issue_count,
        input_source_family_count=input_source_report.family_count,
        input_source_ready_family_count=input_source_report.ready_family_count,
        input_source_boundary_family_count=input_source_report.boundary_family_count,
        input_source_pack_count=input_source_report.pack_count,
        input_source_input_pack_count=input_source_report.input_pack_count,
        input_source_ready_input_pack_count=(
            input_source_report.ready_input_pack_count
        ),
        input_source_accepted_format_count=input_source_report.accepted_format_count,
        input_source_structured_format_count=(
            input_source_report.structured_format_count
        ),
        input_source_material_required_family_count=(
            input_source_report.material_required_family_count
        ),
        input_source_markdown_enabled_family_count=(
            input_source_report.markdown_enabled_family_count
        ),
        input_source_latex_fragment_family_count=(
            input_source_report.latex_fragment_family_count
        ),
        input_source_render_source_count=input_source_report.render_source_count,
        input_source_target_template_count=input_source_report.target_template_count,
        input_source_boundary_input_source_count=(
            input_source_report.boundary_input_source_count
        ),
        input_source_format_count=input_source_report.format_count,
        input_source_issue_count=input_source_report.issue_count,
        input_source_warning_count=input_source_report.warning_count,
        input_source_missing_source_evidence_count=(
            input_source_report.missing_source_evidence_count
        ),
        family_count=family_report.family_count,
        family_fixture_depth_family_count=family_fixture_depth_report.family_count,
        family_fixture_depth_p1_family_count=(
            family_fixture_depth_report.p1_family_count
        ),
        family_fixture_depth_p1_ready_count=(
            family_fixture_depth_report.p1_ready_count
        ),
        family_fixture_depth_issue_count=family_fixture_depth_report.issue_count,
        sample_fixture_count=len(list_scene_sample_fixtures()),
        control_contract_count=control_report.contract_count,
        control_runtime_control_count=control_runtime_report.runtime_control_count,
        control_runtime_ready_control_count=(
            control_runtime_report.ready_runtime_control_count
        ),
        control_runtime_contract_link_count=(
            control_runtime_report.control_contract_link_count
        ),
        control_runtime_scene_surface_count=(
            control_runtime_report.scene_surface_count
        ),
        control_runtime_template_surface_count=(
            control_runtime_report.template_surface_count
        ),
        control_runtime_shared_component_count=(
            control_runtime_report.shared_component_count
        ),
        control_runtime_consumer_count=control_runtime_report.runtime_consumer_count,
        control_runtime_issue_count=control_runtime_report.issue_count,
        control_runtime_missing_source_evidence_count=(
            control_runtime_report.missing_source_evidence_count
        ),
        count_profile_profile_count=count_profile_report.profile_count,
        count_profile_referenced_profile_count=(
            count_profile_report.referenced_profile_count
        ),
        count_profile_rule_source_profile_count=(
            count_profile_report.rule_source_profile_count
        ),
        count_profile_registry_only_profile_count=(
            count_profile_report.registry_only_profile_count
        ),
        count_profile_rule_source_only_profile_count=(
            count_profile_report.rule_source_only_profile_count
        ),
        count_profile_section_limit_profile_count=(
            count_profile_report.section_limit_profile_count
        ),
        count_profile_unique_scope_count=count_profile_report.unique_scope_count,
        count_profile_unique_primary_metric_count=(
            count_profile_report.unique_primary_metric_count
        ),
        count_profile_family_count=count_profile_report.family_count,
        count_profile_ready_family_count=count_profile_report.ready_family_count,
        count_profile_boundary_family_count=count_profile_report.boundary_family_count,
        count_profile_accounted_family_count=(
            count_profile_report.accounted_family_count
        ),
        count_profile_pack_count=count_profile_report.pack_count,
        count_profile_count_profile_pack_count=(
            count_profile_report.count_profile_pack_count
        ),
        count_profile_ready_count_profile_pack_count=(
            count_profile_report.ready_count_profile_pack_count
        ),
        count_profile_runtime_consumer_count=count_profile_report.runtime_consumer_count,
        count_profile_report_surface_count=count_profile_report.report_surface_count,
        count_profile_issue_count=count_profile_report.issue_count,
        count_profile_warning_count=count_profile_report.warning_count,
        count_profile_missing_source_evidence_count=(
            count_profile_report.missing_source_evidence_count
        ),
        word_risk_surface_count=word_risk_report.surface_count,
        object_preflight_action_target_count=(
            object_preflight_action_report.target_count
        ),
        object_preflight_action_ready_target_count=(
            object_preflight_action_report.ready_target_count
        ),
        object_preflight_action_warning_target_count=(
            object_preflight_action_report.warning_target_count
        ),
        object_preflight_action_high_risk_target_count=(
            object_preflight_action_report.high_risk_target_count
        ),
        object_preflight_action_fixture_backed_target_count=(
            object_preflight_action_report.fixture_backed_target_count
        ),
        object_preflight_action_blockable_target_count=(
            object_preflight_action_report.blockable_target_count
        ),
        object_preflight_action_skippable_target_count=(
            object_preflight_action_report.skippable_target_count
        ),
        object_preflight_action_manual_confirmation_target_count=(
            object_preflight_action_report.manual_confirmation_target_count
        ),
        object_preflight_action_family_count=(
            object_preflight_action_report.family_count
        ),
        object_preflight_action_ready_family_count=(
            object_preflight_action_report.ready_family_count
        ),
        object_preflight_action_boundary_family_count=(
            object_preflight_action_report.boundary_family_count
        ),
        object_preflight_action_strict_family_count=(
            object_preflight_action_report.strict_family_count
        ),
        object_preflight_action_family_with_fixture_count=(
            object_preflight_action_report.family_with_fixture_count
        ),
        object_preflight_action_issue_count=(
            object_preflight_action_report.issue_count
        ),
        object_preflight_action_warning_count=(
            object_preflight_action_report.warning_count
        ),
        object_preflight_action_missing_source_evidence_count=(
            object_preflight_action_report.missing_source_evidence_count
        ),
        user_journey_pack_count=user_journey_fixture_report.pack_count,
        user_journey_ready_pack_count=user_journey_fixture_report.ready_pack_count,
        user_journey_warning_pack_count=(
            user_journey_fixture_report.warning_pack_count
        ),
        user_journey_family_count=user_journey_fixture_report.family_count,
        user_journey_ready_family_count=(
            user_journey_fixture_report.ready_family_count
        ),
        user_journey_warning_family_count=(
            user_journey_fixture_report.warning_family_count
        ),
        user_journey_path_count=user_journey_fixture_report.path_count,
        user_journey_success_path_count=int(
            user_journey_counts["success_path_count"]
        ),
        user_journey_degraded_path_count=int(
            user_journey_counts["degraded_path_count"]
        ),
        user_journey_failure_path_count=int(
            user_journey_counts["failure_path_count"]
        ),
        user_journey_manual_boundary_path_count=int(
            user_journey_counts["manual_boundary_path_count"]
        ),
        user_journey_ambiguous_decision_path_count=int(
            user_journey_counts["ambiguous_decision_path_count"]
        ),
        user_journey_handoff_path_count=int(
            user_journey_counts["handoff_path_count"]
        ),
        user_journey_negative_control_path_count=int(
            user_journey_counts["negative_control_path_count"]
        ),
        user_journey_issue_count=user_journey_fixture_report.issue_count,
        user_journey_warning_count=user_journey_fixture_report.warning_count,
        user_journey_missing_source_evidence_count=(
            user_journey_fixture_report.missing_source_evidence_count
        ),
        business_capability_matrix_count=(
            business_capability_matrix_report.capability_count
        ),
        business_capability_matrix_ready_count=(
            business_capability_matrix_report.ready_capability_count
        ),
        business_capability_matrix_high_priority_count=(
            business_capability_matrix_report.high_priority_capability_count
        ),
        business_capability_matrix_high_priority_ready_count=(
            business_capability_matrix_report.high_priority_ready_count
        ),
        business_capability_matrix_boundary_count=(
            business_capability_matrix_report.boundary_capability_count
        ),
        business_capability_matrix_manual_gate_count=(
            business_capability_matrix_report.manual_gate_capability_count
        ),
        business_capability_matrix_missing_journey_group_count=(
            business_capability_matrix_report.missing_journey_group_count
        ),
        business_capability_matrix_issue_count=(
            business_capability_matrix_report.issue_count
        ),
        business_capability_matrix_warning_count=(
            business_capability_matrix_report.warning_count
        ),
        business_capability_matrix_missing_source_evidence_count=(
            business_capability_matrix_report.missing_source_evidence_count
        ),
        boundary_capability_count=boundary_capability_report.capability_count,
        boundary_capability_ready_count=(
            boundary_capability_report.ready_capability_count
        ),
        boundary_capability_professional_count=(
            boundary_capability_report.professional_capability_count
        ),
        boundary_capability_import_ai_count=(
            boundary_capability_report.import_ai_capability_count
        ),
        boundary_capability_fixture_count=boundary_capability_report.fixture_count,
        boundary_capability_report_expectation_count=(
            boundary_capability_report.report_expectation_count
        ),
        boundary_capability_ui_surface_count=(
            boundary_capability_report.ui_surface_count
        ),
        boundary_capability_risk_domain_count=(
            boundary_capability_report.risk_domain_count
        ),
        boundary_capability_decision_requirement_count=(
            boundary_capability_report.decision_requirement_count
        ),
        boundary_capability_external_receipt_count=(
            boundary_capability_report.external_receipt_count
        ),
        boundary_capability_release_guardrail_count=(
            boundary_capability_report.release_guardrail_count
        ),
        boundary_capability_issue_count=boundary_capability_report.issue_count,
        boundary_capability_missing_source_evidence_count=(
            boundary_capability_report.missing_source_evidence_count
        ),
        plugin_boundary_gate_count=plugin_boundary_report.gate_count,
        plugin_boundary_risk_domain_count=plugin_boundary_report.risk_domain_count,
        plugin_boundary_issue_count=plugin_boundary_report.issue_count,
        external_handoff_contract_count=(
            external_handoff_contract_report.contract_count
        ),
        external_handoff_contract_ready_count=(
            external_handoff_contract_report.ready_contract_count
        ),
        external_handoff_contract_pack_count=(
            external_handoff_contract_report.pack_contract_count
        ),
        external_handoff_contract_family_count=(
            external_handoff_contract_report.family_contract_count
        ),
        external_handoff_contract_plugin_gate_count=(
            external_handoff_contract_report.plugin_gate_count
        ),
        external_handoff_contract_target_plugin_count=(
            external_handoff_contract_report.target_plugin_count
        ),
        external_handoff_contract_risk_domain_count=(
            external_handoff_contract_report.risk_domain_count
        ),
        external_handoff_contract_report_count=external_handoff_contract_report.report_count,
        external_handoff_contract_ui_surface_count=(
            external_handoff_contract_report.ui_surface_count
        ),
        external_handoff_contract_fixture_count=(
            external_handoff_contract_report.fixture_count
        ),
        external_handoff_contract_status_state_count=(
            external_handoff_contract_report.status_state_count
        ),
        external_handoff_contract_failure_policy_count=(
            external_handoff_contract_report.failure_policy_count
        ),
        external_handoff_contract_issue_count=external_handoff_contract_report.issue_count,
        external_handoff_contract_missing_source_evidence_count=(
            external_handoff_contract_report.missing_source_evidence_count
        ),
        boundary_guarded_completion_subject_count=(
            boundary_guarded_completion_report.subject_count
        ),
        boundary_guarded_completion_ready_count=(
            boundary_guarded_completion_report.ready_subject_count
        ),
        boundary_guarded_completion_pack_count=(
            boundary_guarded_completion_report.pack_subject_count
        ),
        boundary_guarded_completion_family_count=(
            boundary_guarded_completion_report.family_subject_count
        ),
        boundary_guarded_completion_retained_gap_count=(
            boundary_guarded_completion_report.retained_gap_count
        ),
        boundary_guarded_completion_external_contract_count=(
            boundary_guarded_completion_report.external_contract_count
        ),
        boundary_guarded_completion_boundary_capability_count=(
            boundary_guarded_completion_report.boundary_capability_count
        ),
        boundary_guarded_completion_plugin_gate_count=(
            boundary_guarded_completion_report.plugin_gate_count
        ),
        boundary_guarded_completion_target_plugin_count=(
            boundary_guarded_completion_report.target_plugin_count
        ),
        boundary_guarded_completion_risk_domain_count=(
            boundary_guarded_completion_report.risk_domain_count
        ),
        boundary_guarded_completion_excluded_core_claim_count=(
            boundary_guarded_completion_report.excluded_core_claim_count
        ),
        boundary_guarded_completion_issue_count=(
            boundary_guarded_completion_report.issue_count
        ),
        boundary_guarded_completion_missing_source_evidence_count=(
            boundary_guarded_completion_report.missing_source_evidence_count
        ),
        residual_warning_governance_warning_count=(
            residual_warning_governance_report.warning_count
        ),
        residual_warning_governance_managed_count=(
            residual_warning_governance_report.managed_warning_count
        ),
        residual_warning_governance_input_source_warning_count=(
            residual_warning_governance_report.input_source_warning_count
        ),
        residual_warning_governance_input_source_managed_warning_count=(
            residual_warning_governance_report.input_source_managed_warning_count
        ),
        residual_warning_governance_count_profile_warning_count=(
            residual_warning_governance_report.count_profile_warning_count
        ),
        residual_warning_governance_count_profile_managed_warning_count=(
            residual_warning_governance_report.count_profile_managed_warning_count
        ),
        residual_warning_governance_dashboard_projection_warning_count=(
            residual_warning_governance_report.dashboard_projection_warning_count
        ),
        dashboard_warning_projection_governed_count=(
            terminal_release_exception_report.warning_projection_count
        ),
        residual_warning_governance_plugin_manual_warning_count=(
            residual_warning_governance_report.plugin_manual_warning_count
        ),
        residual_warning_governance_plugin_manual_managed_warning_count=(
            residual_warning_governance_report.plugin_manual_managed_warning_count
        ),
        residual_warning_governance_reference_profile_warning_count=(
            residual_warning_governance_report.reference_profile_warning_count
        ),
        residual_warning_governance_reference_profile_managed_warning_count=(
            residual_warning_governance_report.reference_profile_managed_warning_count
        ),
        residual_warning_governance_object_preflight_warning_count=(
            residual_warning_governance_report.object_preflight_warning_count
        ),
        residual_warning_governance_visio_fixture_closed_count=(
            residual_warning_governance_report.visio_fixture_closed_count
        ),
        residual_warning_governance_visio_fixture_verified_count=(
            residual_warning_governance_report.visio_fixture_closed_count
        ),
        residual_warning_governance_unmanaged_warning_count=(
            residual_warning_governance_report.unmanaged_warning_count
        ),
        residual_warning_governance_issue_count=(
            residual_warning_governance_report.issue_count
        ),
        residual_warning_governance_missing_source_evidence_count=(
            residual_warning_governance_report.missing_source_evidence_count
        ),
        boundary_readiness_reconciliation_count=(
            boundary_readiness_reconciliation_report.row_count
        ),
        boundary_readiness_reconciliation_reconciled_count=(
            boundary_readiness_reconciliation_report.reconciled_count
        ),
        boundary_readiness_reconciliation_unreconciled_count=(
            boundary_readiness_reconciliation_report.unreconciled_count
        ),
        boundary_readiness_reconciliation_readiness_delta_count=(
            boundary_readiness_reconciliation_report.readiness_delta_count
        ),
        boundary_readiness_reconciliation_not_applicable_count=(
            boundary_readiness_reconciliation_report.not_applicable_count
        ),
        boundary_readiness_reconciliation_static_closed_boundary_count=(
            boundary_readiness_reconciliation_report.static_closed_boundary_count
        ),
        boundary_readiness_reconciliation_maturity_boundary_guarded_count=(
            boundary_readiness_reconciliation_report.maturity_boundary_guarded_count
        ),
        boundary_readiness_reconciliation_boundary_subject_count=(
            boundary_readiness_reconciliation_report.boundary_subject_count
        ),
        boundary_readiness_reconciliation_issue_count=(
            boundary_readiness_reconciliation_report.issue_count
        ),
        boundary_readiness_reconciliation_missing_source_evidence_count=(
            boundary_readiness_reconciliation_report.missing_source_evidence_count
        ),
        terminal_release_exception_count=(
            terminal_release_exception_report.exception_count
        ),
        terminal_release_exception_governed_count=(
            terminal_release_exception_report.governed_exception_count
        ),
        terminal_release_exception_ungoverned_count=(
            terminal_release_exception_report.ungoverned_exception_count
        ),
        terminal_release_exception_managed_warning_count=(
            terminal_release_exception_report.managed_warning_count
        ),
        terminal_release_exception_warning_projection_count=(
            terminal_release_exception_report.warning_projection_count
        ),
        terminal_release_exception_readiness_reconciliation_count=(
            terminal_release_exception_report.readiness_reconciliation_count
        ),
        terminal_release_exception_boundary_guarded_maturity_count=(
            terminal_release_exception_report.boundary_guarded_maturity_count
        ),
        terminal_release_exception_static_closed_boundary_count=(
            terminal_release_exception_report.static_closed_boundary_count
        ),
        terminal_release_exception_trace_count=(
            terminal_release_exception_report.exception_trace_count
        ),
        terminal_release_exception_unique_source_trace_count=(
            terminal_release_exception_report.unique_source_trace_count
        ),
        terminal_release_exception_linked_boundary_subject_count=(
            terminal_release_exception_report.linked_boundary_subject_count
        ),
        terminal_release_exception_issue_count=(
            terminal_release_exception_report.issue_count
        ),
        terminal_release_exception_missing_source_evidence_count=(
            terminal_release_exception_report.missing_source_evidence_count
        ),
        boundary_subject_release_dossier_subject_count=(
            boundary_subject_release_dossier_report.subject_count
        ),
        boundary_subject_release_dossier_ready_count=(
            boundary_subject_release_dossier_report.ready_subject_count
        ),
        boundary_subject_release_dossier_pack_subject_count=(
            boundary_subject_release_dossier_report.pack_subject_count
        ),
        boundary_subject_release_dossier_family_subject_count=(
            boundary_subject_release_dossier_report.family_subject_count
        ),
        boundary_subject_release_dossier_subject_trace_count=(
            boundary_subject_release_dossier_report.subject_trace_count
        ),
        boundary_subject_release_dossier_unique_source_trace_count=(
            boundary_subject_release_dossier_report.unique_source_trace_count
        ),
        boundary_subject_release_dossier_readiness_reconciliation_row_count=(
            boundary_subject_release_dossier_report.readiness_reconciliation_row_count
        ),
        boundary_subject_release_dossier_terminal_exception_count=(
            boundary_subject_release_dossier_report.terminal_exception_count
        ),
        boundary_subject_release_dossier_issue_count=(
            boundary_subject_release_dossier_report.issue_count
        ),
        boundary_subject_release_dossier_missing_source_evidence_count=(
            boundary_subject_release_dossier_report.missing_source_evidence_count
        ),
        non_subject_release_trace_attribution_count=(
            non_subject_release_trace_attribution_report.trace_count
        ),
        non_subject_release_trace_attribution_ready_count=(
            non_subject_release_trace_attribution_report.attributed_trace_count
        ),
        non_subject_release_trace_attribution_unattributed_count=(
            non_subject_release_trace_attribution_report.unattributed_trace_count
        ),
        non_subject_release_trace_attribution_dashboard_projection_count=(
            non_subject_release_trace_attribution_report.dashboard_projection_trace_count
        ),
        non_subject_release_trace_attribution_registry_only_profile_count=(
            non_subject_release_trace_attribution_report.registry_only_profile_trace_count
        ),
        non_subject_release_trace_attribution_plugin_manual_pack_count=(
            non_subject_release_trace_attribution_report.plugin_manual_pack_trace_count
        ),
        non_subject_release_trace_attribution_generic_not_applicable_count=(
            non_subject_release_trace_attribution_report.generic_not_applicable_trace_count
        ),
        non_subject_release_trace_attribution_issue_count=(
            non_subject_release_trace_attribution_report.issue_count
        ),
        non_subject_release_trace_attribution_missing_source_evidence_count=(
            non_subject_release_trace_attribution_report.missing_source_evidence_count
        ),
        release_trace_partition_guard_partition_count=(
            release_trace_partition_guard_report.partition_count
        ),
        release_trace_partition_guard_ready_count=(
            release_trace_partition_guard_report.ready_partition_count
        ),
        release_trace_partition_guard_terminal_trace_count=(
            release_trace_partition_guard_report.terminal_trace_count
        ),
        release_trace_partition_guard_subject_trace_count=(
            release_trace_partition_guard_report.subject_trace_count
        ),
        release_trace_partition_guard_non_subject_trace_count=(
            release_trace_partition_guard_report.non_subject_trace_count
        ),
        release_trace_partition_guard_partitioned_trace_count=(
            release_trace_partition_guard_report.partitioned_trace_count
        ),
        release_trace_partition_guard_missing_trace_count=(
            release_trace_partition_guard_report.missing_trace_count
        ),
        release_trace_partition_guard_overlap_trace_count=(
            release_trace_partition_guard_report.overlap_trace_count
        ),
        release_trace_partition_guard_extra_trace_count=(
            release_trace_partition_guard_report.extra_trace_count
        ),
        release_trace_partition_guard_issue_count=(
            release_trace_partition_guard_report.issue_count
        ),
        release_trace_partition_guard_missing_source_evidence_count=(
            release_trace_partition_guard_report.missing_source_evidence_count
        ),
        release_projection_surface_parity_count=(
            release_projection_surface_parity_report.projection_count
        ),
        release_projection_surface_parity_ready_count=(
            release_projection_surface_parity_report.ready_projection_count
        ),
        release_projection_surface_parity_release_gate_check_count=(
            release_projection_surface_parity_report.release_gate_check_count
        ),
        release_projection_surface_parity_dashboard_source_count=(
            release_projection_surface_parity_report.dashboard_source_count
        ),
        release_projection_surface_parity_dashboard_card_count=(
            release_projection_surface_parity_report.dashboard_card_count
        ),
        release_projection_surface_parity_drilldown_item_count=(
            release_projection_surface_parity_report.drilldown_item_count
        ),
        release_projection_surface_parity_summary_projection_count=(
            release_projection_surface_parity_report.summary_projection_count
        ),
        release_projection_surface_parity_export_script_count=(
            release_projection_surface_parity_report.export_script_count
        ),
        release_projection_surface_parity_workflow_test_count=(
            release_projection_surface_parity_report.workflow_test_count
        ),
        release_projection_surface_parity_closure_doc_count=(
            release_projection_surface_parity_report.closure_doc_count
        ),
        release_projection_surface_parity_issue_count=(
            release_projection_surface_parity_report.issue_count
        ),
        release_projection_surface_parity_missing_source_evidence_count=(
            release_projection_surface_parity_report.missing_source_evidence_count
        ),
        boundary_subject_release_continuity_subject_count=(
            boundary_subject_release_continuity_report.subject_count
        ),
        boundary_subject_release_continuity_ready_count=(
            boundary_subject_release_continuity_report.ready_subject_count
        ),
        boundary_subject_release_continuity_maturity_subject_count=(
            boundary_subject_release_continuity_report.maturity_subject_count
        ),
        boundary_subject_release_continuity_guarded_completion_subject_count=(
            boundary_subject_release_continuity_report.guarded_completion_subject_count
        ),
        boundary_subject_release_continuity_readiness_reconciliation_subject_count=(
            boundary_subject_release_continuity_report.readiness_reconciliation_subject_count
        ),
        boundary_subject_release_continuity_terminal_release_subject_count=(
            boundary_subject_release_continuity_report.terminal_release_subject_count
        ),
        boundary_subject_release_continuity_dossier_count=(
            boundary_subject_release_continuity_report.subject_dossier_count
        ),
        boundary_subject_release_continuity_readiness_row_count=(
            boundary_subject_release_continuity_report.readiness_row_count
        ),
        boundary_subject_release_continuity_terminal_trace_count=(
            boundary_subject_release_continuity_report.terminal_trace_count
        ),
        boundary_subject_release_continuity_dossier_trace_count=(
            boundary_subject_release_continuity_report.dossier_trace_count
        ),
        boundary_subject_release_continuity_mismatch_count=(
            boundary_subject_release_continuity_report.mismatch_count
        ),
        boundary_subject_release_continuity_issue_count=(
            boundary_subject_release_continuity_report.issue_count
        ),
        boundary_subject_release_continuity_missing_source_evidence_count=(
            boundary_subject_release_continuity_report.missing_source_evidence_count
        ),
        release_closure_ledger_stage_count=(
            release_closure_ledger_report.stage_count
        ),
        release_closure_ledger_ready_count=(
            release_closure_ledger_report.ready_stage_count
        ),
        release_closure_ledger_stage_order_count=(
            release_closure_ledger_report.stage_order_count
        ),
        release_closure_ledger_upstream_dependency_count=(
            release_closure_ledger_report.upstream_dependency_count
        ),
        release_closure_ledger_upstream_dependency_ready_count=(
            release_closure_ledger_report.upstream_dependency_ready_count
        ),
        release_closure_ledger_release_gate_check_count=(
            release_closure_ledger_report.release_gate_check_count
        ),
        release_closure_ledger_dashboard_source_count=(
            release_closure_ledger_report.dashboard_source_count
        ),
        release_closure_ledger_dashboard_card_count=(
            release_closure_ledger_report.dashboard_card_count
        ),
        release_closure_ledger_drilldown_item_count=(
            release_closure_ledger_report.drilldown_item_count
        ),
        release_closure_ledger_summary_projection_count=(
            release_closure_ledger_report.summary_projection_count
        ),
        release_closure_ledger_export_script_count=(
            release_closure_ledger_report.export_script_count
        ),
        release_closure_ledger_workflow_test_count=(
            release_closure_ledger_report.workflow_test_count
        ),
        release_closure_ledger_closure_doc_count=(
            release_closure_ledger_report.closure_doc_count
        ),
        release_closure_ledger_issue_count=(
            release_closure_ledger_report.issue_count
        ),
        release_closure_ledger_missing_source_evidence_count=(
            release_closure_ledger_report.missing_source_evidence_count
        ),
        boundary_maturity_release_envelope_count=(
            boundary_maturity_release_envelope_report.envelope_count
        ),
        boundary_maturity_release_envelope_ready_count=(
            boundary_maturity_release_envelope_report.ready_envelope_count
        ),
        boundary_maturity_release_envelope_l5_blocker_enveloped_count=(
            boundary_maturity_release_envelope_report.l5_blocker_enveloped_count
        ),
        boundary_maturity_release_envelope_maturity_boundary_count=(
            boundary_maturity_release_envelope_report.maturity_boundary_count
        ),
        boundary_maturity_release_envelope_external_handoff_count=(
            boundary_maturity_release_envelope_report.external_handoff_count
        ),
        boundary_maturity_release_envelope_guarded_completion_count=(
            boundary_maturity_release_envelope_report.guarded_completion_count
        ),
        boundary_maturity_release_envelope_readiness_reconciliation_count=(
            boundary_maturity_release_envelope_report.readiness_reconciliation_count
        ),
        boundary_maturity_release_envelope_terminal_trace_count=(
            boundary_maturity_release_envelope_report.terminal_trace_count
        ),
        boundary_maturity_release_envelope_release_dossier_count=(
            boundary_maturity_release_envelope_report.release_dossier_count
        ),
        boundary_maturity_release_envelope_subject_continuity_count=(
            boundary_maturity_release_envelope_report.subject_continuity_count
        ),
        boundary_maturity_release_envelope_retained_gap_count=(
            boundary_maturity_release_envelope_report.retained_gap_count
        ),
        retained_gap_enveloped_count=(
            boundary_maturity_release_envelope_report.retained_gap_count
        ),
        boundary_maturity_release_envelope_issue_count=(
            boundary_maturity_release_envelope_report.issue_count
        ),
        boundary_maturity_release_envelope_missing_source_evidence_count=(
            boundary_maturity_release_envelope_report.missing_source_evidence_count
        ),
        retained_gap_exit_criteria_count=(
            retained_gap_exit_criteria_report.criteria_count
        ),
        retained_gap_exit_criteria_release_allowed_count=(
            retained_gap_exit_criteria_report.release_allowed_count
        ),
        retained_gap_exit_criteria_envelope_link_count=(
            retained_gap_exit_criteria_report.envelope_link_count
        ),
        retained_gap_exit_criteria_handoff_link_count=(
            retained_gap_exit_criteria_report.handoff_link_count
        ),
        retained_gap_exit_criteria_guarded_completion_link_count=(
            retained_gap_exit_criteria_report.guarded_completion_link_count
        ),
        retained_gap_exit_criteria_boundary_capability_link_count=(
            retained_gap_exit_criteria_report.boundary_capability_link_count
        ),
        retained_gap_exit_criteria_exit_signal_count=(
            retained_gap_exit_criteria_report.exit_signal_count
        ),
        retained_gap_external_receipt_target_count=(
            retained_gap_exit_criteria_report.external_receipt_target_count
        ),
        retained_gap_external_receipt_alignment_count=(
            retained_gap_exit_criteria_report.external_receipt_alignment_count
        ),
        retained_gap_exit_criteria_prohibited_core_claim_count=(
            retained_gap_exit_criteria_report.prohibited_core_claim_count
        ),
        retained_gap_exit_criteria_issue_count=(
            retained_gap_exit_criteria_report.issue_count
        ),
        retained_gap_exit_criteria_missing_source_evidence_count=(
            retained_gap_exit_criteria_report.missing_source_evidence_count
        ),
        release_residual_ratio_ledger_count=(
            release_residual_ratio_ledger_report.ratio_count
        ),
        release_residual_ratio_ledger_published_count=(
            release_residual_ratio_ledger_report.published_ratio_count
        ),
        release_residual_ratio_ledger_non_full_count=(
            release_residual_ratio_ledger_report.non_full_ratio_count
        ),
        release_residual_ratio_ledger_readiness_reconciliation_link_count=(
            release_residual_ratio_ledger_report.readiness_reconciliation_link_count
        ),
        release_residual_ratio_ledger_terminal_exception_link_count=(
            release_residual_ratio_ledger_report.terminal_exception_link_count
        ),
        release_residual_ratio_ledger_release_envelope_link_count=(
            release_residual_ratio_ledger_report.release_envelope_link_count
        ),
        release_residual_ratio_ledger_exit_criteria_link_count=(
            release_residual_ratio_ledger_report.retained_gap_exit_criteria_link_count
        ),
        release_residual_ratio_ledger_receipt_alignment_link_count=(
            release_residual_ratio_ledger_report.retained_gap_receipt_alignment_link_count
        ),
        release_residual_ratio_ledger_count_delivery_boundary_alignment_count=(
            release_residual_ratio_ledger_report.count_delivery_boundary_alignment_count
        ),
        release_residual_ratio_ledger_count_delivery_boundary_link_count=(
            release_residual_ratio_ledger_report.count_delivery_boundary_link_count
        ),
        release_residual_ratio_ledger_count_delivery_receipt_alignment_count=(
            release_residual_ratio_ledger_report.count_delivery_receipt_alignment_count
        ),
        release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count=(
            release_residual_ratio_ledger_report.count_delivery_receipt_alignment_link_count
        ),
        release_residual_ratio_ledger_maturity_l5_blocker_alignment_count=(
            release_residual_ratio_ledger_report.maturity_l5_blocker_alignment_count
        ),
        release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count=(
            release_residual_ratio_ledger_report.maturity_l5_blocker_release_envelope_count
        ),
        release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count=(
            release_residual_ratio_ledger_report.maturity_l5_blocker_receipt_alignment_count
        ),
        release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count=(
            release_residual_ratio_ledger_report.maturity_l5_blocker_receipt_alignment_link_count
        ),
        release_residual_ratio_ledger_boundary_scope_alignment_count=(
            release_residual_ratio_ledger_report.boundary_scope_alignment_count
        ),
        release_residual_ratio_ledger_boundary_scope_link_count=(
            release_residual_ratio_ledger_report.boundary_scope_link_count
        ),
        release_residual_ratio_ledger_issue_count=(
            release_residual_ratio_ledger_report.issue_count
        ),
        release_residual_ratio_ledger_missing_source_evidence_count=(
            release_residual_ratio_ledger_report.missing_source_evidence_count
        ),
        release_residual_explanation_count=(
            release_residual_explanation_report.row_count
        ),
        release_residual_explanation_covered_count=(
            release_residual_explanation_report.covered_count
        ),
        release_residual_explanation_mismatch_count=(
            release_residual_explanation_report.mismatch_count
        ),
        release_residual_explanation_missing_summary_marker_count=(
            release_residual_explanation_report.missing_summary_marker_count
        ),
        release_residual_explanation_issue_count=(
            release_residual_explanation_report.issue_count
        ),
        release_residual_explanation_missing_source_evidence_count=(
            release_residual_explanation_report.missing_source_evidence_count
        ),
        release_acceptance_certificate_count=(
            release_acceptance_certificate_report.certificate_count
        ),
        release_acceptance_certificate_ready_count=(
            release_acceptance_certificate_report.ready_certificate_count
        ),
        release_acceptance_certificate_receipt_count=(
            release_acceptance_certificate_report.receipt_certificate_count
        ),
        release_acceptance_certificate_ready_receipt_count=(
            release_acceptance_certificate_report.ready_receipt_certificate_count
        ),
        release_acceptance_certificate_component_report_count=(
            release_acceptance_certificate_report.component_report_count
        ),
        release_acceptance_certificate_requirement_dimension_count=(
            release_acceptance_certificate_report.requirement_dimension_count
        ),
        release_acceptance_certificate_ready_requirement_dimension_count=(
            release_acceptance_certificate_report.ready_requirement_dimension_count
        ),
        release_acceptance_certificate_expected_count_match_count=(
            release_acceptance_certificate_report.expected_count_match_count
        ),
        release_acceptance_certificate_source_evidence_count=(
            release_acceptance_certificate_report.source_evidence_count
        ),
        release_acceptance_certificate_ready_source_evidence_count=(
            release_acceptance_certificate_report.ready_source_evidence_count
        ),
        release_acceptance_certificate_issue_count=(
            release_acceptance_certificate_report.issue_count
        ),
        release_acceptance_certificate_missing_source_evidence_count=(
            release_acceptance_certificate_report.missing_source_evidence_count
        ),
        material_schema_family_count=material_schema_report.family_count,
        material_schema_material_family_count=(
            material_schema_report.material_family_count
        ),
        material_schema_ready_material_family_count=(
            material_schema_report.ready_material_family_count
        ),
        material_schema_pack_count=material_schema_report.pack_count,
        material_schema_material_pack_count=material_schema_report.material_pack_count,
        material_schema_ready_material_pack_count=(
            material_schema_report.ready_material_pack_count
        ),
        material_schema_schema_count=material_schema_report.schema_count,
        material_schema_referenced_schema_count=(
            material_schema_report.referenced_schema_count
        ),
        material_schema_registry_only_schema_count=(
            material_schema_report.registry_only_schema_count
        ),
        material_schema_required_field_count=(
            material_schema_report.required_field_count
        ),
        material_schema_required_asset_count=(
            material_schema_report.required_asset_count
        ),
        material_schema_issue_count=material_schema_report.issue_count,
        material_repair_flow_count=material_repair_flow_report.flow_count,
        material_repair_flow_ready_count=material_repair_flow_report.ready_flow_count,
        material_repair_flow_capability_count=(
            material_repair_flow_report.capability_count
        ),
        material_repair_flow_signal_count=(
            material_repair_flow_report.material_signal_count
        ),
        material_repair_flow_target_type_count=(
            material_repair_flow_report.repair_target_type_count
        ),
        material_repair_flow_runtime_surface_count=(
            material_repair_flow_report.runtime_surface_count
        ),
        material_repair_flow_ui_surface_count=(
            material_repair_flow_report.ui_surface_count
        ),
        material_repair_flow_test_evidence_count=(
            material_repair_flow_report.test_evidence_count
        ),
        material_repair_flow_covered_pack_count=(
            material_repair_flow_report.covered_pack_count
        ),
        material_repair_flow_covered_family_count=(
            material_repair_flow_report.covered_family_count
        ),
        material_repair_flow_issue_count=material_repair_flow_report.issue_count,
        material_repair_flow_missing_source_evidence_count=(
            material_repair_flow_report.missing_source_evidence_count
        ),
        fixed_layout_profile_channel_count=(
            fixed_layout_profile_report.profile_channel_count
        ),
        fixed_layout_profile_ready_channel_count=(
            fixed_layout_profile_report.ready_profile_channel_count
        ),
        fixed_layout_profile_surface_count=(
            fixed_layout_profile_report.fixed_layout_surface_count
        ),
        fixed_layout_profile_ooxml_touchpoint_count=(
            fixed_layout_profile_report.word_ooxml_touchpoint_count
        ),
        fixed_layout_profile_runtime_surface_count=(
            fixed_layout_profile_report.runtime_surface_count
        ),
        fixed_layout_profile_ui_surface_count=(
            fixed_layout_profile_report.ui_surface_count
        ),
        fixed_layout_profile_report_surface_count=(
            fixed_layout_profile_report.report_surface_count
        ),
        fixed_layout_profile_repair_target_type_count=(
            fixed_layout_profile_report.repair_target_type_count
        ),
        fixed_layout_profile_test_evidence_count=(
            fixed_layout_profile_report.test_evidence_count
        ),
        fixed_layout_profile_covered_pack_count=(
            fixed_layout_profile_report.covered_pack_count
        ),
        fixed_layout_profile_covered_family_count=(
            fixed_layout_profile_report.covered_family_count
        ),
        fixed_layout_profile_issue_count=fixed_layout_profile_report.issue_count,
        fixed_layout_profile_missing_source_evidence_count=(
            fixed_layout_profile_report.missing_source_evidence_count
        ),
        report_artifact_drilldown_channel_count=(
            report_artifact_drilldown_report.drilldown_channel_count
        ),
        report_artifact_drilldown_ready_channel_count=(
            report_artifact_drilldown_report.ready_drilldown_channel_count
        ),
        report_artifact_drilldown_artifact_kind_count=(
            report_artifact_drilldown_report.artifact_kind_count
        ),
        report_artifact_drilldown_runtime_surface_count=(
            report_artifact_drilldown_report.runtime_surface_count
        ),
        report_artifact_drilldown_ui_surface_count=(
            report_artifact_drilldown_report.ui_surface_count
        ),
        report_artifact_drilldown_report_surface_count=(
            report_artifact_drilldown_report.report_surface_count
        ),
        report_artifact_drilldown_repair_target_type_count=(
            report_artifact_drilldown_report.repair_target_type_count
        ),
        report_artifact_drilldown_test_evidence_count=(
            report_artifact_drilldown_report.test_evidence_count
        ),
        report_artifact_drilldown_covered_pack_count=(
            report_artifact_drilldown_report.covered_pack_count
        ),
        report_artifact_drilldown_covered_family_count=(
            report_artifact_drilldown_report.covered_family_count
        ),
        report_artifact_drilldown_issue_count=(
            report_artifact_drilldown_report.issue_count
        ),
        report_artifact_drilldown_missing_source_evidence_count=(
            report_artifact_drilldown_report.missing_source_evidence_count
        ),
        delivery_preset_family_count=delivery_preset_report.family_count,
        delivery_preset_ready_family_count=delivery_preset_report.ready_family_count,
        delivery_preset_boundary_family_count=(
            delivery_preset_report.boundary_family_count
        ),
        delivery_preset_accounted_family_count=(
            delivery_preset_report.accounted_family_count
        ),
        delivery_preset_pack_count=delivery_preset_report.pack_count,
        delivery_preset_delivery_pack_count=delivery_preset_report.delivery_pack_count,
        delivery_preset_ready_delivery_pack_count=(
            delivery_preset_report.ready_delivery_pack_count
        ),
        delivery_preset_boundary_delivery_pack_count=(
            delivery_preset_report.boundary_delivery_pack_count
        ),
        delivery_preset_accounted_delivery_pack_count=(
            delivery_preset_report.accounted_delivery_pack_count
        ),
        delivery_preset_unique_preset_count=(
            delivery_preset_report.delivery_preset_count
        ),
        delivery_preset_final_docx_preset_count=(
            delivery_preset_report.final_docx_preset_count
        ),
        delivery_preset_compare_docx_preset_count=(
            delivery_preset_report.compare_docx_preset_count
        ),
        delivery_preset_report_only_preset_count=(
            delivery_preset_report.report_only_preset_count
        ),
        delivery_preset_material_package_preset_count=(
            delivery_preset_report.material_package_preset_count
        ),
        delivery_preset_structured_intermediate_preset_count=(
            delivery_preset_report.structured_intermediate_preset_count
        ),
        delivery_preset_content_visibility_rule_count=(
            delivery_preset_report.content_visibility_rule_count
        ),
        delivery_preset_issue_count=delivery_preset_report.issue_count,
        delivery_execution_channel_count=(
            delivery_execution_report.execution_channel_count
        ),
        delivery_execution_ready_channel_count=(
            delivery_execution_report.ready_execution_channel_count
        ),
        delivery_execution_required_output_signal_count=(
            delivery_execution_report.required_output_signal_count
        ),
        delivery_execution_payload_key_count=delivery_execution_report.payload_key_count,
        delivery_execution_runtime_surface_count=(
            delivery_execution_report.runtime_surface_count
        ),
        delivery_execution_report_surface_count=(
            delivery_execution_report.report_surface_count
        ),
        delivery_execution_ui_surface_count=delivery_execution_report.ui_surface_count,
        delivery_execution_test_evidence_count=(
            delivery_execution_report.test_evidence_count
        ),
        delivery_execution_covered_pack_count=delivery_execution_report.covered_pack_count,
        delivery_execution_covered_family_count=(
            delivery_execution_report.covered_family_count
        ),
        delivery_execution_issue_count=delivery_execution_report.issue_count,
        delivery_execution_missing_source_evidence_count=(
            delivery_execution_report.missing_source_evidence_count
        ),
        formula_output_watermark_capability_count=(
            formula_output_watermark_report.capability_count
        ),
        formula_output_watermark_ready_capability_count=(
            formula_output_watermark_report.ready_capability_count
        ),
        formula_output_watermark_family_count=(
            formula_output_watermark_report.family_count
        ),
        formula_output_watermark_ready_family_count=(
            formula_output_watermark_report.ready_family_count
        ),
        formula_output_watermark_boundary_family_count=(
            formula_output_watermark_report.boundary_family_count
        ),
        formula_output_watermark_accounted_family_count=(
            formula_output_watermark_report.accounted_family_count
        ),
        formula_output_watermark_formula_family_count=(
            formula_output_watermark_report.formula_family_count
        ),
        formula_output_watermark_output_family_count=(
            formula_output_watermark_report.output_family_count
        ),
        formula_output_watermark_watermark_family_count=(
            formula_output_watermark_report.watermark_family_count
        ),
        formula_output_watermark_plugin_gate_count=(
            formula_output_watermark_report.plugin_gate_count
        ),
        formula_output_watermark_control_contract_count=(
            formula_output_watermark_report.control_contract_count
        ),
        formula_output_watermark_parameter_path_count=(
            formula_output_watermark_report.parameter_path_count
        ),
        formula_output_watermark_template_baseline_path_count=(
            formula_output_watermark_report.template_baseline_path_count
        ),
        formula_output_watermark_issue_count=formula_output_watermark_report.issue_count,
        product_readiness_subject_count=len(list_scene_product_readiness_specs()),
        static_closed_but_not_green_count=len(static_closed_but_not_green_specs()),
        static_closed_not_green_governed_count=(
            terminal_release_exception_report.static_closed_boundary_count
        ),
        maturity_upgrade_subject_count=maturity_upgrade_report.subject_count,
        maturity_upgrade_green_subject_count=(
            maturity_upgrade_report.green_subject_count
        ),
        maturity_upgrade_l5_blocked_subject_count=(
            maturity_upgrade_report.l5_blocked_subject_count
        ),
        maturity_upgrade_l3_subject_count=maturity_upgrade_report.l3_subject_count,
        maturity_upgrade_l4_subject_count=maturity_upgrade_report.l4_subject_count,
        maturity_upgrade_boundary_subject_count=(
            maturity_upgrade_report.boundary_subject_count
        ),
        maturity_upgrade_gap_count=maturity_upgrade_report.gap_count,
        maturity_upgrade_gap_domain_count=maturity_upgrade_report.gap_domain_count,
        maturity_upgrade_gap_domain_classified_count=(
            maturity_upgrade_report.gap_domain_count
        ),
        maturity_upgrade_issue_count=maturity_upgrade_report.issue_count,
        maturity_upgrade_warning_count=maturity_upgrade_report.warning_count,
        maturity_upgrade_missing_source_evidence_count=(
            maturity_upgrade_report.missing_source_evidence_count
        ),
    )


def audit_scene_matrix_dashboard(
    report: SceneMatrixDashboardReport | None = None,
) -> tuple[SceneMatrixDashboardIssue, ...]:
    current = report or build_scene_matrix_dashboard()
    return tuple(issue for issue in current.issues if issue.severity == "error")


def _build_dashboard_row(
    pack_row: SceneHighFrequencyCompletenessPackRow,
    *,
    family_rows: Sequence[SceneFamilySubsceneAuditRow],
    material_pack_rows: Sequence[SceneMaterialSchemaPackRow],
    material_repair_flow_rows: Sequence[SceneMaterialRepairFlowRow],
    fixed_layout_profile_rows: Sequence[SceneFixedLayoutProfileRow],
    report_artifact_drilldown_rows: Sequence[SceneReportArtifactDrilldownRow],
    delivery_pack_rows: Sequence[SceneDeliveryPresetPackRow],
    delivery_execution_rows: Sequence[SceneDeliveryPresetExecutionRow],
    input_pack_rows: Sequence[SceneInputSourcePackRow],
    ambiguity_clarification_rows: Sequence[SceneAmbiguityClarificationRow],
    object_preflight_target_rows: Sequence[SceneObjectPreflightTargetRow],
    user_journey_pack_rows: Sequence[SceneUserJourneyPackRow],
    business_capability_rows: Sequence[SceneBusinessCapabilityRow],
    control_contract_count: int,
    control_contract_issue_count: int,
    control_runtime_control_count: int,
    control_runtime_issue_count: int,
    word_risk_rows: Sequence[SceneWordRiskClosureRow],
) -> SceneMatrixDashboardRow:
    families = tuple(
        row for row in family_rows if row.family_id in pack_row.planned_family_ids
    )
    readiness = _readiness_for_pack(pack_row.pack_id)
    word_rows = tuple(
        row
        for row in word_risk_rows
        if row.surface_id in pack_row.word_risk_surface_ids
    )
    object_preflight_rows = tuple(
        row
        for row in object_preflight_target_rows
        if pack_row.pack_id in row.pack_ids
    )
    material_row = _material_pack_row(pack_row.pack_id, material_pack_rows)
    material_repair_rows = _material_repair_flow_rows_for_pack(
        pack_row.pack_id,
        material_repair_flow_rows,
    )
    fixed_layout_rows = _fixed_layout_profile_rows_for_pack(
        pack_row.pack_id,
        fixed_layout_profile_rows,
    )
    report_artifact_rows = _report_artifact_drilldown_rows_for_pack(
        pack_row.pack_id,
        report_artifact_drilldown_rows,
    )
    delivery_row = _delivery_pack_row(pack_row.pack_id, delivery_pack_rows)
    delivery_execution_pack_rows = _delivery_execution_rows_for_pack(
        pack_row.pack_id,
        delivery_execution_rows,
    )
    input_row = _input_pack_row(pack_row.pack_id, input_pack_rows)
    clarification_rows = tuple(
        row
        for row in ambiguity_clarification_rows
        if pack_row.pack_id in row.candidate_pack_ids
    )
    user_journey_row = _user_journey_pack_row(
        pack_row.pack_id,
        user_journey_pack_rows,
    )
    business_rows = _business_capability_rows_for_pack(
        pack_row.pack_id,
        business_capability_rows,
    )
    boundary_signals = _boundary_signal_ids(pack_row, families, readiness)
    lens_ids = _dashboard_lens_ids(
        pack_row=pack_row,
        families=families,
        material_row=material_row,
        material_repair_flow_rows=material_repair_rows,
        fixed_layout_profile_rows=fixed_layout_rows,
        report_artifact_drilldown_rows=report_artifact_rows,
        delivery_row=delivery_row,
        delivery_execution_rows=delivery_execution_pack_rows,
        input_row=input_row,
        user_journey_row=user_journey_row,
        readiness=readiness,
        boundary_signals=boundary_signals,
        control_contract_count=control_contract_count,
        control_contract_issue_count=control_contract_issue_count,
        control_runtime_control_count=control_runtime_control_count,
        control_runtime_issue_count=control_runtime_issue_count,
        word_rows=word_rows,
    )
    missing_lens_ids = tuple(
        lens_id
        for lens_id in SCENE_MATRIX_DASHBOARD_LENS_IDS
        if lens_id not in lens_ids
    )
    issue_ids = [f"missing_lens.{lens_id}" for lens_id in missing_lens_ids]
    if pack_row.issue_ids:
        issue_ids.extend(f"pack.{issue_id}" for issue_id in pack_row.issue_ids)
    if any(row.issue_ids for row in families):
        issue_ids.append("family_subscene_issues")
    if material_row is not None and material_row.issue_ids:
        issue_ids.append("material_schema_issues")
    if any(row.issue_ids for row in material_repair_rows):
        issue_ids.append("material_repair_flow_issues")
    if any(row.issue_ids for row in fixed_layout_rows):
        issue_ids.append("fixed_layout_profile_issues")
    if any(row.issue_ids for row in report_artifact_rows):
        issue_ids.append("report_artifact_drilldown_issues")
    if delivery_row is not None and delivery_row.issue_ids:
        issue_ids.append("delivery_preset_issues")
    if any(row.issue_ids for row in delivery_execution_pack_rows):
        issue_ids.append("delivery_execution_issues")
    if input_row is not None and input_row.issue_ids:
        issue_ids.append("input_source_issues")
    if any(row.issue_ids for row in clarification_rows):
        issue_ids.append("ambiguity_clarification_issues")
    if user_journey_row is not None and user_journey_row.issue_ids:
        issue_ids.append("user_journey_issues")
    if any(row.issue_ids for row in business_rows):
        issue_ids.append("business_capability_matrix_issues")
    if control_runtime_issue_count:
        issue_ids.append("control_runtime_issues")
    if not pack_row.boundary.strip():
        issue_ids.append("missing_boundary_statement")

    warning_ids: list[str] = []
    if pack_row.warning_ids:
        warning_ids.extend(f"pack.{warning_id}" for warning_id in pack_row.warning_ids)
    if any(row.warning_ids for row in families):
        warning_ids.append("family_subscene_warnings")
    if material_row is not None and material_row.warning_ids:
        warning_ids.append("material_schema_warnings")
    if delivery_row is not None and delivery_row.warning_ids:
        warning_ids.append("delivery_preset_warnings")
    if input_row is not None and input_row.warning_ids:
        warning_ids.append("input_source_warnings")
    if any(row.warning_ids for row in business_rows):
        warning_ids.append("business_capability_matrix_warnings")

    return SceneMatrixDashboardRow(
        pack_id=pack_row.pack_id,
        label=pack_row.label,
        product_readiness_level=readiness.product_readiness_level,
        static_closure_level=readiness.static_closure_level,
        product_gap_count=len(readiness.remaining_product_gaps),
        plugin_boundary=pack_row.plugin_boundary,
        boundary=pack_row.boundary,
        boundary_signal_ids=boundary_signals,
        family_ids=pack_row.planned_family_ids,
        family_count=len(families),
        family_status_counts=_status_counts(row.status for row in families),
        family_issue_count=sum(len(row.issue_ids) for row in families),
        family_warning_count=sum(len(row.warning_ids) for row in families),
        family_request_cell_count=sum(row.request_cell_count for row in families),
        material_schema_ids=(
            material_row.material_schema_ids if material_row is not None else ()
        ),
        material_schema_count=(
            len(material_row.material_schema_ids) if material_row is not None else 0
        ),
        material_required_field_count=(
            material_row.required_field_count if material_row is not None else 0
        ),
        material_required_asset_count=(
            material_row.required_asset_count if material_row is not None else 0
        ),
        material_schema_issue_count=(
            len(material_row.issue_ids) if material_row is not None else 0
        ),
        material_repair_flow_count=len(material_repair_rows),
        material_repair_flow_issue_count=sum(
            len(row.issue_ids) for row in material_repair_rows
        ),
        fixed_layout_profile_channel_count=len(fixed_layout_rows),
        fixed_layout_profile_issue_count=sum(
            len(row.issue_ids) for row in fixed_layout_rows
        ),
        report_artifact_drilldown_channel_count=len(report_artifact_rows),
        report_artifact_drilldown_issue_count=sum(
            len(row.issue_ids) for row in report_artifact_rows
        ),
        delivery_preset_ids=(
            delivery_row.actual_delivery_preset_ids if delivery_row is not None else ()
        ),
        delivery_preset_count=(
            len(delivery_row.actual_delivery_preset_ids)
            if delivery_row is not None
            else 0
        ),
        delivery_compare_preset_count=(
            delivery_row.compare_docx_preset_count if delivery_row is not None else 0
        ),
        delivery_report_only_preset_count=(
            delivery_row.report_only_preset_count if delivery_row is not None else 0
        ),
        delivery_material_package_preset_count=(
            delivery_row.material_package_preset_count
            if delivery_row is not None
            else 0
        ),
        delivery_structured_intermediate_preset_count=(
            delivery_row.structured_intermediate_preset_count
            if delivery_row is not None
            else 0
        ),
        delivery_content_visibility_rule_count=(
            delivery_row.content_visibility_rule_count
            if delivery_row is not None
            else 0
        ),
        delivery_preset_issue_count=(
            len(delivery_row.issue_ids) if delivery_row is not None else 0
        ),
        delivery_execution_channel_count=len(delivery_execution_pack_rows),
        delivery_execution_issue_count=sum(
            len(row.issue_ids) for row in delivery_execution_pack_rows
        ),
        input_formats=input_row.input_formats if input_row is not None else (),
        input_structured_formats=(
            input_row.structured_formats if input_row is not None else ()
        ),
        input_render_source_ids=(
            input_row.render_source_ids if input_row is not None else ()
        ),
        input_boundary_source_ids=(
            input_row.boundary_input_source_ids if input_row is not None else ()
        ),
        input_source_issue_count=(
            len(input_row.issue_ids) if input_row is not None else 0
        ),
        request_cell_count=pack_row.request_cell_count,
        matched_request_cell_count=pack_row.matched_request_cell_count,
        ambiguous_request_cell_count=pack_row.ambiguous_request_cell_count,
        manual_boundary_request_cell_count=(
            pack_row.manual_boundary_request_cell_count
        ),
        negative_request_cell_count=pack_row.negative_request_cell_count,
        request_cell_sample_ids=pack_row.request_cell_sample_ids,
        ambiguity_clarification_count=len(clarification_rows),
        ambiguity_clarification_issue_count=sum(
            len(row.issue_ids) for row in clarification_rows
        ),
        user_journey_path_type_ids=(
            user_journey_row.path_type_ids if user_journey_row is not None else ()
        ),
        user_journey_path_count=(
            user_journey_row.path_count if user_journey_row is not None else 0
        ),
        user_journey_issue_count=(
            len(user_journey_row.issue_ids) if user_journey_row is not None else 0
        ),
        user_journey_warning_count=(
            len(user_journey_row.warning_ids) if user_journey_row is not None else 0
        ),
        business_capability_ids=tuple(row.capability_id for row in business_rows),
        business_capability_count=len(business_rows),
        business_capability_issue_count=sum(
            len(row.issue_ids) for row in business_rows
        ),
        business_capability_warning_count=sum(
            len(row.warning_ids) for row in business_rows
        ),
        capability_axis_ids=pack_row.capability_axis_ids,
        workflow_archetype_ids=pack_row.workflow_archetype_ids,
        word_risk_surface_ids=pack_row.word_risk_surface_ids,
        word_risk_issue_count=sum(len(row.issue_ids) for row in word_rows),
        preflight_word_risk_surface_count=sum(
            1 for row in word_rows if row.preflight_targets
        ),
        object_preflight_target_ids=tuple(
            row.target_id for row in object_preflight_rows
        ),
        object_preflight_action_count=len(object_preflight_rows),
        object_preflight_action_issue_count=sum(
            len(row.issue_ids) for row in object_preflight_rows
        ),
        object_preflight_action_warning_count=sum(
            len(row.warning_ids) for row in object_preflight_rows
        ),
        sample_fixture_count=pack_row.sample_fixture_count,
        sample_fixture_ids=pack_row.sample_fixture_ids,
        report_anchor_count=pack_row.request_cell_report_anchor_count,
        control_contract_count=control_contract_count,
        control_contract_issue_count=control_contract_issue_count,
        control_runtime_control_count=control_runtime_control_count,
        control_runtime_issue_count=control_runtime_issue_count,
        dashboard_lens_ids=lens_ids,
        missing_lens_ids=missing_lens_ids,
        drilldown_source_ids=SCENE_MATRIX_DASHBOARD_SOURCE_IDS,
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _readiness_for_pack(pack_id: str) -> SceneProductReadinessSpec:
    return product_readiness_for(pack_id, subject_type="pack")


def _material_pack_row(
    pack_id: str,
    rows: Sequence[SceneMaterialSchemaPackRow],
) -> SceneMaterialSchemaPackRow | None:
    for row in rows:
        if row.pack_id == pack_id:
            return row
    return None


def _material_repair_flow_rows_for_pack(
    pack_id: str,
    rows: Sequence[SceneMaterialRepairFlowRow],
) -> tuple[SceneMaterialRepairFlowRow, ...]:
    return tuple(row for row in rows if pack_id in row.pack_ids)


def _fixed_layout_profile_rows_for_pack(
    pack_id: str,
    rows: Sequence[SceneFixedLayoutProfileRow],
) -> tuple[SceneFixedLayoutProfileRow, ...]:
    return tuple(row for row in rows if pack_id in row.pack_ids)


def _report_artifact_drilldown_rows_for_pack(
    pack_id: str,
    rows: Sequence[SceneReportArtifactDrilldownRow],
) -> tuple[SceneReportArtifactDrilldownRow, ...]:
    return tuple(row for row in rows if pack_id in row.pack_ids)


def _delivery_pack_row(
    pack_id: str,
    rows: Sequence[SceneDeliveryPresetPackRow],
) -> SceneDeliveryPresetPackRow | None:
    for row in rows:
        if row.pack_id == pack_id:
            return row
    return None


def _input_pack_row(
    pack_id: str,
    rows: Sequence[SceneInputSourcePackRow],
) -> SceneInputSourcePackRow | None:
    for row in rows:
        if row.pack_id == pack_id:
            return row
    return None


def _delivery_execution_rows_for_pack(
    pack_id: str,
    rows: Sequence[SceneDeliveryPresetExecutionRow],
) -> tuple[SceneDeliveryPresetExecutionRow, ...]:
    return tuple(row for row in rows if pack_id in row.pack_ids)


def _user_journey_pack_row(
    pack_id: str,
    rows: Sequence[SceneUserJourneyPackRow],
) -> SceneUserJourneyPackRow | None:
    for row in rows:
        if row.pack_id == pack_id:
            return row
    return None


def _business_capability_rows_for_pack(
    pack_id: str,
    rows: Sequence[SceneBusinessCapabilityRow],
) -> tuple[SceneBusinessCapabilityRow, ...]:
    return tuple(row for row in rows if pack_id in row.pack_ids)


def _boundary_signal_ids(
    pack_row: SceneHighFrequencyCompletenessPackRow,
    families: Sequence[SceneFamilySubsceneAuditRow],
    readiness: SceneProductReadinessSpec,
) -> tuple[str, ...]:
    signals = ["pack_boundary"]
    if pack_row.plugin_boundary:
        signals.append("plugin_boundary")
    if pack_row.manual_boundary_request_cell_count:
        signals.append("manual_boundary_request_cell")
    if pack_row.ambiguous_request_cell_count:
        signals.append("ambiguous_request_cell")
    if pack_row.negative_request_cell_count:
        signals.append("negative_control")
    if readiness.is_boundary:
        signals.append("boundary_readiness")
    if any(row.plugin_gate_ids for row in families):
        signals.append("family_plugin_gate")
    if any(row.plugin_boundary_only for row in families):
        signals.append("family_plugin_boundary_only")
    if "plugin_manual_gate" in pack_row.workflow_archetype_ids:
        signals.append("plugin_manual_workflow")
    return _unique_values(signals)


def _dashboard_lens_ids(
    *,
    pack_row: SceneHighFrequencyCompletenessPackRow,
    families: Sequence[SceneFamilySubsceneAuditRow],
    material_row: SceneMaterialSchemaPackRow | None,
    material_repair_flow_rows: Sequence[SceneMaterialRepairFlowRow],
    fixed_layout_profile_rows: Sequence[SceneFixedLayoutProfileRow],
    report_artifact_drilldown_rows: Sequence[SceneReportArtifactDrilldownRow],
    delivery_row: SceneDeliveryPresetPackRow | None,
    delivery_execution_rows: Sequence[SceneDeliveryPresetExecutionRow],
    input_row: SceneInputSourcePackRow | None,
    user_journey_row: SceneUserJourneyPackRow | None,
    readiness: SceneProductReadinessSpec,
    boundary_signals: Sequence[str],
    control_contract_count: int,
    control_contract_issue_count: int,
    control_runtime_control_count: int,
    control_runtime_issue_count: int,
    word_rows: Sequence[SceneWordRiskClosureRow],
) -> tuple[str, ...]:
    lens_ids: list[str] = []
    if pack_row.request_cell_count and pack_row.matched_request_cell_count:
        lens_ids.append("user_request")
    if (
        pack_row.primary_landings
        or pack_row.secondary_landings
        or pack_row.executable_scene_ids
        or pack_row.planned_family_ids
        or pack_row.plugin_boundary
    ):
        lens_ids.append("carrier_layer")
    if (
        pack_row.capability_axis_ids
        or any(row.material_schema_ids or row.count_profile_ids for row in families)
        or (
            material_row is not None
            and material_row.material_relevant
            and not material_row.issue_ids
        )
        or (
            material_repair_flow_rows
            and all(not row.issue_ids for row in material_repair_flow_rows)
        )
        or (
            fixed_layout_profile_rows
            and all(not row.issue_ids for row in fixed_layout_profile_rows)
        )
        or (
            report_artifact_drilldown_rows
            and all(not row.issue_ids for row in report_artifact_drilldown_rows)
        )
        or (
            delivery_row is not None
            and delivery_row.delivery_relevant
            and not delivery_row.issue_ids
        )
        or (
            delivery_execution_rows
            and all(not row.issue_ids for row in delivery_execution_rows)
        )
        or (
            input_row is not None
            and input_row.input_relevant
            and not input_row.issue_ids
        )
        or readiness.evidence_surfaces
    ):
        lens_ids.append("fact_source")
    if pack_row.workflow_archetype_ids and pack_row.capability_axis_ids:
        lens_ids.append("workflow")
    if pack_row.word_risk_surface_ids and word_rows and all(
        row.status == "ready" for row in word_rows
    ):
        lens_ids.append("word_risk")
    if (
        control_contract_count > 0
        and control_contract_issue_count == 0
        and control_runtime_control_count > 0
        and control_runtime_issue_count == 0
    ):
        lens_ids.append("control_contract")
    if "pack_boundary" in boundary_signals:
        lens_ids.append("boundary")
    if (
        pack_row.sample_fixture_count
        and pack_row.request_cell_report_anchor_count == pack_row.request_cell_count
        and pack_row.request_cell_count
        and (material_row is None or not material_row.issue_ids)
        and all(not row.issue_ids for row in material_repair_flow_rows)
        and all(not row.issue_ids for row in fixed_layout_profile_rows)
        and all(not row.issue_ids for row in report_artifact_drilldown_rows)
        and (delivery_row is None or not delivery_row.issue_ids)
        and all(not row.issue_ids for row in delivery_execution_rows)
        and (input_row is None or not input_row.issue_ids)
        and (user_journey_row is None or not user_journey_row.issue_ids)
    ):
        lens_ids.append("evidence_chain")
    if readiness.product_readiness_level and readiness.static_closure_level:
        lens_ids.append("product_readiness")
    return tuple(lens_ids)


def _filter_rows(
    rows: Sequence[SceneMatrixDashboardRow],
    *,
    pack_id: str,
    family_id: str,
    readiness_level: str,
    boundary_signal: str,
    status: str,
) -> tuple[SceneMatrixDashboardRow, ...]:
    normalized_pack = str(pack_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_readiness = str(readiness_level or "").strip()
    normalized_boundary = str(boundary_signal or "").strip()
    normalized_status = str(status or "").strip()
    return tuple(
        row
        for row in rows
        if (not normalized_pack or row.pack_id == normalized_pack)
        and (not normalized_family or normalized_family in row.family_ids)
        and (
            not normalized_readiness
            or row.product_readiness_level == normalized_readiness
        )
        and (
            not normalized_boundary
            or normalized_boundary in row.boundary_signal_ids
        )
        and (not normalized_status or row.status == normalized_status)
    )


def _dashboard_issues(
    *,
    rows,
    pack_report,
    task_lexicon_report,
    ambiguous_boundary_report,
    ambiguity_clarification_report,
    import_handoff_report,
    input_source_report,
    family_report,
    family_fixture_depth_report,
    control_report,
    control_runtime_report,
    count_profile_report,
    word_risk_report,
    object_preflight_action_report,
    user_journey_fixture_report,
    business_capability_matrix_report,
    boundary_capability_report,
    plugin_boundary_report,
    external_handoff_contract_report,
    boundary_guarded_completion_report,
    residual_warning_governance_report,
    boundary_readiness_reconciliation_report,
    terminal_release_exception_report,
    boundary_subject_release_dossier_report,
    non_subject_release_trace_attribution_report,
    release_trace_partition_guard_report,
    release_projection_surface_parity_report,
    boundary_subject_release_continuity_report,
    release_closure_ledger_report,
    boundary_maturity_release_envelope_report,
    retained_gap_exit_criteria_report,
    release_residual_ratio_ledger_report,
    release_acceptance_certificate_report,
    material_schema_report,
    material_repair_flow_report,
    fixed_layout_profile_report,
    report_artifact_drilldown_report,
    delivery_preset_report,
    delivery_execution_report,
    formula_output_watermark_report,
    maturity_upgrade_report,
    request_summary,
    request_browser,
    sample_fixture_count: int,
) -> tuple[
    tuple[SceneMatrixDashboardIssue, ...],
    tuple[SceneMatrixDashboardIssue, ...],
]:
    issues: list[SceneMatrixDashboardIssue] = []
    warnings: list[SceneMatrixDashboardIssue] = []

    if len(SCENE_MATRIX_DASHBOARD_SOURCE_IDS) != len(
        _unique_values(SCENE_MATRIX_DASHBOARD_SOURCE_IDS)
    ):
        issues.append(
            _issue(
                "dashboard",
                "sources",
                "duplicate_source_id",
                "Dashboard source ids must be unique.",
            )
        )
    if pack_report.pack_count != len(rows):
        issues.append(
            _issue(
                "dashboard",
                "rows",
                "pack_row_count_mismatch",
                "Dashboard row count must match pack completeness rows.",
            )
        )
    if request_summary.cell_count != request_browser.total_count:
        issues.append(
            _issue(
                "dashboard",
                "request_cell_registry",
                "request_cell_count_mismatch",
                "Request-cell summary and browser counts differ.",
            )
        )
    if sample_fixture_count <= 0:
        issues.append(
            _issue(
                "dashboard",
                "sample_fixtures",
                "missing_sample_fixture_library",
                "Dashboard needs at least one DOCX fixture to be evidence-backed.",
            )
        )

    _extend_source_issues(issues, "pack", pack_report.issues)
    _extend_source_issues(issues, "task_lexicon", task_lexicon_report.issues)
    _extend_source_issues(
        issues, "ambiguous_boundary", ambiguous_boundary_report.issues
    )
    _extend_source_issues(
        issues,
        "ambiguity_clarification",
        ambiguity_clarification_report.issues,
    )
    _extend_source_issues(issues, "import_handoff", import_handoff_report.issues)
    _extend_source_issues(issues, "input_source", input_source_report.issues)
    _extend_source_issues(issues, "family", family_report.issues)
    _extend_source_issues(
        issues, "family_fixture_depth", family_fixture_depth_report.issues
    )
    _extend_source_issues(issues, "control", control_report.issues)
    _extend_source_issues(
        issues,
        "control_runtime",
        control_runtime_report.issues,
    )
    _extend_source_issues(issues, "count_profile", count_profile_report.issues)
    _extend_source_issues(issues, "word_risk", word_risk_report.issues)
    _extend_source_issues(
        issues,
        "object_preflight_action",
        object_preflight_action_report.issues,
    )
    _extend_source_issues(
        issues,
        "user_journey",
        user_journey_fixture_report.issues,
    )
    _extend_source_issues(
        issues,
        "business_capability_matrix",
        business_capability_matrix_report.issues,
    )
    _extend_source_issues(
        issues,
        "boundary_capability_matrix",
        boundary_capability_report.issues,
    )
    _extend_source_issues(issues, "plugin_boundary", plugin_boundary_report.issues)
    _extend_source_issues(
        issues,
        "external_handoff_contract",
        external_handoff_contract_report.issues,
    )
    _extend_source_issues(
        issues,
        "boundary_guarded_completion",
        boundary_guarded_completion_report.issues,
    )
    _extend_source_issues(
        issues,
        "residual_warning_governance",
        residual_warning_governance_report.issues,
    )
    _extend_source_issues(
        issues,
        "boundary_readiness_reconciliation",
        boundary_readiness_reconciliation_report.issues,
    )
    _extend_source_issues(
        issues,
        "terminal_release_exception",
        terminal_release_exception_report.issues,
    )
    _extend_source_issues(
        issues,
        "boundary_subject_release_dossier",
        boundary_subject_release_dossier_report.issues,
    )
    _extend_source_issues(
        issues,
        "non_subject_release_trace_attribution",
        non_subject_release_trace_attribution_report.issues,
    )
    _extend_source_issues(
        issues,
        "release_trace_partition_guard",
        release_trace_partition_guard_report.issues,
    )
    _extend_source_issues(
        issues,
        "release_projection_surface_parity",
        release_projection_surface_parity_report.issues,
    )
    _extend_source_issues(
        issues,
        "boundary_subject_release_continuity",
        boundary_subject_release_continuity_report.issues,
    )
    _extend_source_issues(
        issues,
        "release_closure_ledger",
        release_closure_ledger_report.issues,
    )
    _extend_source_issues(
        issues,
        "boundary_maturity_release_envelope",
        boundary_maturity_release_envelope_report.issues,
    )
    _extend_source_issues(
        issues,
        "retained_gap_exit_criteria",
        retained_gap_exit_criteria_report.issues,
    )
    _extend_source_issues(
        issues,
        "release_residual_ratio_ledger",
        release_residual_ratio_ledger_report.issues,
    )
    _extend_source_issues(
        issues,
        "release_acceptance_certificate",
        release_acceptance_certificate_report.issues,
    )
    _extend_source_issues(issues, "material_schema", material_schema_report.issues)
    _extend_source_issues(
        issues,
        "material_repair_flow",
        material_repair_flow_report.issues,
    )
    _extend_source_issues(
        issues,
        "fixed_layout_profile",
        fixed_layout_profile_report.issues,
    )
    _extend_source_issues(
        issues,
        "report_artifact_drilldown",
        report_artifact_drilldown_report.issues,
    )
    _extend_source_issues(issues, "delivery_preset", delivery_preset_report.issues)
    _extend_source_issues(
        issues,
        "delivery_execution",
        delivery_execution_report.issues,
    )
    _extend_source_issues(
        issues,
        "formula_output_watermark",
        formula_output_watermark_report.issues,
    )
    _extend_source_issues(
        issues,
        "maturity_upgrade",
        maturity_upgrade_report.issues,
    )

    for row in rows:
        for issue_id in row.issue_ids:
            issues.append(
                _issue(
                    "pack",
                    row.pack_id,
                    issue_id,
                    f"Dashboard row '{row.pack_id}' is missing {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                _issue(
                    "pack",
                    row.pack_id,
                    warning_id,
                    f"Dashboard row '{row.pack_id}' has {warning_id}.",
                    severity="warning",
                )
            )
    return tuple(issues), tuple(warnings)


def _extend_source_issues(
    issues: list[SceneMatrixDashboardIssue],
    source_scope: str,
    source_issues: Iterable[object],
) -> None:
    for item in source_issues:
        scope_id = str(
            getattr(item, "pack_id", "")
            or getattr(item, "boundary_id", "")
            or getattr(item, "handoff_id", "")
            or getattr(item, "task_id", "")
            or getattr(item, "family_id", "")
            or getattr(item, "contract_id", "")
            or getattr(item, "surface_id", "")
            or getattr(item, "gate_id", "")
            or getattr(item, "execution_id", "")
            or getattr(item, "envelope_id", "")
            or getattr(item, "criteria_id", "")
            or getattr(item, "ratio_id", "")
            or getattr(item, "residual_id", "")
            or getattr(item, "certificate_id", "")
            or getattr(item, "profile_channel_id", "")
            or getattr(item, "drilldown_channel_id", "")
            or getattr(item, "scope_id", "")
            or source_scope
        )
        kind = str(getattr(item, "kind", "") or getattr(item, "issue", "") or "issue")
        message = str(getattr(item, "message", "") or item)
        issues.append(_issue(source_scope, scope_id, kind, message))


def _dashboard_cards(
    *,
    rows: Sequence[SceneMatrixDashboardRow],
    request_cell_count: int,
    task_lexicon_task_count: int,
    task_lexicon_phrase_count: int,
    task_lexicon_negative_task_count: int,
    high_frequency_ready_pack_count: int,
    ambiguous_boundary_pack_pair_count: int,
    ambiguity_clarification_report,
    import_handoff_count: int,
    family_count: int,
    family_fixture_depth_p1_family_count: int,
    family_fixture_depth_p1_ready_count: int,
    sample_fixture_count: int,
    control_contract_count: int,
    control_runtime_report,
    count_profile_report,
    input_source_report,
    word_risk_surface_count: int,
    object_preflight_action_report,
    user_journey_fixture_report,
    business_capability_matrix_report,
    boundary_capability_report,
    plugin_boundary_gate_count: int,
    plugin_boundary_risk_domain_count: int,
    external_handoff_contract_report,
    boundary_guarded_completion_report,
    residual_warning_governance_report,
    boundary_readiness_reconciliation_report,
    terminal_release_exception_report,
    boundary_subject_release_dossier_report,
    non_subject_release_trace_attribution_report,
    release_trace_partition_guard_report,
    release_projection_surface_parity_report,
    boundary_subject_release_continuity_report,
    release_closure_ledger_report,
    boundary_maturity_release_envelope_report,
    retained_gap_exit_criteria_report,
    release_residual_ratio_ledger_report,
    release_residual_explanation_report,
    release_acceptance_certificate_report,
    material_schema_report,
    material_repair_flow_report,
    fixed_layout_profile_report,
    report_artifact_drilldown_report,
    delivery_preset_report,
    delivery_execution_report,
    formula_output_watermark_report,
    maturity_upgrade_report,
    product_readiness_subject_count: int,
    static_closed_but_not_green_count: int,
    issue_count: int,
    warning_count: int,
) -> tuple[SceneMatrixDashboardCard, ...]:
    ready_count = sum(1 for row in rows if row.status == "ready")
    manual_count = sum(row.manual_boundary_request_cell_count for row in rows)
    ambiguous_count = sum(row.ambiguous_request_cell_count for row in rows)
    plugin_count = sum(1 for row in rows if row.plugin_boundary)
    user_journey_counts = user_journey_fixture_report.to_payload()["counts"]
    return (
        SceneMatrixDashboardCard(
            card_id="coverage",
            label="Coverage",
            value=f"{ready_count}/{len(rows)} ready",
            detail=(
                f"high_frequency_coverage={high_frequency_ready_pack_count}/{len(rows)} / "
                f"{family_count} families / "
                f"{family_fixture_depth_p1_ready_count}/"
                f"{family_fixture_depth_p1_family_count} P1 fixtures / "
                f"{sample_fixture_count} DOCX fixtures"
            ),
            variant="success" if ready_count == len(rows) else "warning",
            source_ids=(
                "high_frequency_completeness_audit",
                "scene_family_subscene_audit",
                "scene_family_fixture_depth_audit",
            ),
        ),
        SceneMatrixDashboardCard(
            card_id="request_cells",
            label="Request cells",
            value=str(request_cell_count),
            detail=(
                f"{task_lexicon_task_count} task families / "
                f"{task_lexicon_phrase_count} phrases / "
                f"{ambiguous_boundary_pack_pair_count} ambiguous pairs / "
                f"{import_handoff_count} handoff / "
                f"{task_lexicon_negative_task_count} negative task"
            ),
            variant="success",
            source_ids=(
                "scene_request_cell_registry_browser",
                "high_frequency_task_lexicon_audit",
                "scene_ambiguous_boundary_audit",
                "scene_import_handoff_audit",
            ),
        ),
        SceneMatrixDashboardCard(
            card_id="ambiguity_clarifications",
            label="Clarifications",
            value=(
                f"{ambiguity_clarification_report.ready_clarification_count}/"
                f"{ambiguity_clarification_report.clarification_count} ready"
            ),
            detail=(
                f"{ambiguity_clarification_report.candidate_route_count} candidate routes / "
                f"{ambiguity_clarification_report.candidate_pack_count} candidate packs / "
                f"{ambiguity_clarification_report.fixture_backed_count} fixture-backed"
            ),
            variant=(
                "success"
                if ambiguity_clarification_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_ambiguity_clarification_ui_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="boundaries",
            label="Boundaries",
            value=f"{plugin_count} plugin packs",
            detail=(
                f"{manual_count} manual cells / {ambiguous_count} ambiguous cells / "
                f"{ambiguous_boundary_pack_pair_count} ambiguous pairs / "
                f"{import_handoff_count} handoff / "
                f"{plugin_boundary_gate_count} gates / "
                f"{plugin_boundary_risk_domain_count} risk domains / "
                f"{boundary_guarded_completion_report.ready_subject_count}/"
                f"{boundary_guarded_completion_report.subject_count} guarded"
            ),
            variant="info" if manual_count or ambiguous_count else "success",
            source_ids=(
                "scene_request_cell_registry_browser",
                "scene_ambiguous_boundary_audit",
                "scene_import_handoff_audit",
                "scene_family_subscene_audit",
                "scene_plugin_boundary_confirmation_audit",
                "scene_external_handoff_contract_audit",
                "scene_boundary_guarded_completion_audit",
            ),
        ),
        SceneMatrixDashboardCard(
            card_id="word_risk",
            label="Word risk",
            value=f"{word_risk_surface_count} surfaces",
            detail="OOXML risk surfaces linked to packs, fixtures, and source evidence",
            variant="success",
            source_ids=("scene_word_risk_closure_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="object_preflight_actions",
            label="Object preflight",
            value=(
                f"{object_preflight_action_report.ready_target_count}/"
                f"{object_preflight_action_report.target_count} targets"
            ),
            detail=(
                f"{object_preflight_action_report.fixture_backed_target_count} fixture-backed / "
                f"{object_preflight_action_report.blockable_target_count} blockable / "
                f"{object_preflight_action_report.skippable_target_count} skippable / "
                f"{object_preflight_action_report.manual_confirmation_target_count} manual"
            ),
            variant=(
                "success"
                if object_preflight_action_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_object_preflight_action_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="user_journeys",
            label="User journeys",
            value=(
                f"{user_journey_fixture_report.ready_pack_count}/"
                f"{user_journey_fixture_report.pack_count} packs"
            ),
            detail=(
                f"{user_journey_fixture_report.path_count} paths / "
                f"{user_journey_counts['success_path_count']} success / "
                f"{user_journey_counts['degraded_path_count']} degraded / "
                f"{user_journey_counts['failure_path_count']} failure / "
                f"{user_journey_counts['manual_boundary_path_count']} manual / "
                f"{user_journey_counts['handoff_path_count']} handoff"
            ),
            variant=(
                "success"
                if user_journey_fixture_report.warning_count == 0
                else "warning"
            ),
            source_ids=("scene_user_journey_fixture_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="business_capability_matrix",
            label="Business capabilities",
            value=(
                f"{business_capability_matrix_report.ready_capability_count}/"
                f"{business_capability_matrix_report.capability_count} ready"
            ),
            detail=(
                f"{business_capability_matrix_report.high_priority_ready_count}/"
                f"{business_capability_matrix_report.high_priority_capability_count} "
                "P1/P1 candidate ready / "
                f"{business_capability_matrix_report.boundary_capability_count} boundary / "
                f"{business_capability_matrix_report.missing_journey_group_count} journey gaps / "
                f"{business_capability_matrix_report.adopted_external_record_count} absorbed records"
            ),
            variant=(
                "success"
                if business_capability_matrix_report.warning_count == 0
                else "warning"
            ),
            source_ids=("scene_business_capability_matrix_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="boundary_capability_matrix",
            label="Boundary capabilities",
            value=(
                f"{boundary_capability_report.ready_capability_count}/"
                f"{boundary_capability_report.capability_count} ready"
            ),
            detail=(
                f"{boundary_capability_report.professional_capability_count} professional / "
                f"{boundary_capability_report.import_ai_capability_count} import-AI / "
                f"{boundary_capability_report.fixture_count} fixtures / "
                f"{boundary_capability_report.report_expectation_count} reports / "
                f"{boundary_capability_report.ui_surface_count} UI surfaces / "
                f"{boundary_capability_report.risk_domain_count} risks / "
                f"{boundary_capability_report.external_receipt_count} receipts"
            ),
            variant=(
                "success"
                if boundary_capability_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_boundary_capability_matrix",),
        ),
        SceneMatrixDashboardCard(
            card_id="external_handoff_contracts",
            label="External handoffs",
            value=(
                f"{external_handoff_contract_report.ready_contract_count}/"
                f"{external_handoff_contract_report.contract_count} ready"
            ),
            detail=(
                f"{external_handoff_contract_report.pack_contract_count} pack / "
                f"{external_handoff_contract_report.family_contract_count} family / "
                f"{external_handoff_contract_report.target_plugin_count} target plugins / "
                f"{external_handoff_contract_report.report_count} reports / "
                f"{external_handoff_contract_report.status_state_count} states / "
                f"{external_handoff_contract_report.failure_policy_count} failure policies"
            ),
            variant=(
                "success"
                if external_handoff_contract_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_external_handoff_contract_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="boundary_guarded_completion",
            label="Guarded boundaries",
            value=(
                f"{boundary_guarded_completion_report.ready_subject_count}/"
                f"{boundary_guarded_completion_report.subject_count} guarded"
            ),
            detail=(
                f"{boundary_guarded_completion_report.retained_gap_count} retained gaps / "
                f"{boundary_guarded_completion_report.external_contract_count} contracts / "
                f"{boundary_guarded_completion_report.boundary_capability_count} capabilities / "
                f"{boundary_guarded_completion_report.excluded_core_claim_count} excluded claims"
            ),
            variant=(
                "success"
                if boundary_guarded_completion_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_boundary_guarded_completion_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="residual_warning_governance",
            label="Managed warnings",
            value=(
                f"{residual_warning_governance_report.managed_warning_count}/"
                f"{residual_warning_governance_report.warning_count} managed"
            ),
            detail=(
                f"{residual_warning_governance_report.input_source_managed_warning_count}/"
                f"{residual_warning_governance_report.input_source_warning_count} input managed / "
                f"{residual_warning_governance_report.count_profile_managed_warning_count}/"
                f"{residual_warning_governance_report.count_profile_warning_count} count profiles managed / "
                f"{residual_warning_governance_report.plugin_manual_managed_warning_count}/"
                f"{residual_warning_governance_report.plugin_manual_warning_count} plugin/manual managed / "
                f"{residual_warning_governance_report.reference_profile_managed_warning_count}/"
                f"{residual_warning_governance_report.reference_profile_warning_count} reference profiles managed / "
                f"{terminal_release_exception_report.warning_projection_count}/"
                f"{residual_warning_governance_report.dashboard_projection_warning_count} dashboard projected / "
                f"{residual_warning_governance_report.visio_fixture_closed_count}/"
                f"{residual_warning_governance_report.visio_fixture_closed_count} Visio fixture closed / "
                f"{residual_warning_governance_report.object_preflight_warning_count} ObjectPreflight / "
                f"{residual_warning_governance_report.unmanaged_warning_count} unmanaged"
            ),
            variant=(
                "success"
                if residual_warning_governance_report.unmanaged_warning_count == 0
                and residual_warning_governance_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_residual_warning_governance_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="boundary_readiness_reconciliation",
            label="Readiness reconciliation",
            value=(
                f"{boundary_readiness_reconciliation_report.reconciled_count}/"
                f"{boundary_readiness_reconciliation_report.row_count} reconciled"
            ),
            detail=(
                f"{boundary_readiness_reconciliation_report.readiness_delta_count} deltas / "
                f"{boundary_readiness_reconciliation_report.not_applicable_count} not applicable / "
                f"{boundary_readiness_reconciliation_report.static_closed_boundary_count}/"
                f"{static_closed_but_not_green_count} static boundary governed / "
                f"{boundary_readiness_reconciliation_report.maturity_boundary_guarded_count} guarded maturity"
            ),
            variant=(
                "success"
                if boundary_readiness_reconciliation_report.unreconciled_count == 0
                and boundary_readiness_reconciliation_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_boundary_readiness_reconciliation_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="terminal_release_exceptions",
            label="Release exceptions",
            value=(
                f"{terminal_release_exception_report.governed_exception_count}/"
                f"{terminal_release_exception_report.exception_count} governed"
            ),
            detail=(
                f"{terminal_release_exception_report.managed_warning_count} managed warnings / "
                f"{terminal_release_exception_report.warning_projection_count}/"
                f"{residual_warning_governance_report.dashboard_projection_warning_count} dashboard warnings / "
                f"{terminal_release_exception_report.readiness_reconciliation_count} readiness / "
                f"{terminal_release_exception_report.boundary_guarded_maturity_count} maturity / "
                f"{terminal_release_exception_report.static_closed_boundary_count}/"
                f"{static_closed_but_not_green_count} static boundary governed / "
                f"{terminal_release_exception_report.exception_trace_count} traces"
            ),
            variant=(
                "success"
                if terminal_release_exception_report.ungoverned_exception_count == 0
                and terminal_release_exception_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_terminal_release_exception_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="boundary_subject_dossiers",
            label="Boundary subject dossiers",
            value=(
                f"{boundary_subject_release_dossier_report.ready_subject_count}/"
                f"{boundary_subject_release_dossier_report.subject_count} ready"
            ),
            detail=(
                f"{boundary_subject_release_dossier_report.subject_trace_count} traces / "
                f"{boundary_subject_release_dossier_report.readiness_reconciliation_row_count} readiness rows / "
                f"{boundary_subject_release_dossier_report.terminal_exception_count} exception kinds"
            ),
            variant=(
                "success"
                if boundary_subject_release_dossier_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_boundary_subject_release_dossier_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="non_subject_release_traces",
            label="Non-subject release traces",
            value=(
                f"{non_subject_release_trace_attribution_report.attributed_trace_count}/"
                f"{non_subject_release_trace_attribution_report.trace_count} attributed"
            ),
            detail=(
                f"{non_subject_release_trace_attribution_report.dashboard_projection_trace_count} dashboard / "
                f"{non_subject_release_trace_attribution_report.registry_only_profile_trace_count} registry profiles / "
                f"{non_subject_release_trace_attribution_report.plugin_manual_pack_trace_count} plugin pack / "
                f"{non_subject_release_trace_attribution_report.generic_not_applicable_trace_count} generic n/a"
            ),
            variant=(
                "success"
                if non_subject_release_trace_attribution_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_non_subject_release_trace_attribution_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="release_trace_partition",
            label="Release trace partition",
            value=(
                f"{release_trace_partition_guard_report.partitioned_trace_count}/"
                f"{release_trace_partition_guard_report.terminal_trace_count} partitioned"
            ),
            detail=(
                f"{release_trace_partition_guard_report.subject_trace_count} subject / "
                f"{release_trace_partition_guard_report.non_subject_trace_count} non-subject / "
                f"{release_trace_partition_guard_report.missing_trace_count} missing / "
                f"{release_trace_partition_guard_report.overlap_trace_count} overlap"
            ),
            variant=(
                "success"
                if release_trace_partition_guard_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_release_trace_partition_guard_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="release_projection_surfaces",
            label="Release projections",
            value=(
                f"{release_projection_surface_parity_report.ready_projection_count}/"
                f"{release_projection_surface_parity_report.projection_count} ready"
            ),
            detail=(
                f"{release_projection_surface_parity_report.release_gate_check_count} gate / "
                f"{release_projection_surface_parity_report.dashboard_card_count} dashboard / "
                f"{release_projection_surface_parity_report.drilldown_item_count} drilldown / "
                f"{release_projection_surface_parity_report.summary_projection_count} summary"
            ),
            variant=(
                "success"
                if release_projection_surface_parity_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_release_projection_surface_parity_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="boundary_subject_continuity",
            label="Boundary subject continuity",
            value=(
                f"{boundary_subject_release_continuity_report.ready_subject_count}/"
                f"{boundary_subject_release_continuity_report.subject_count} ready"
            ),
            detail=(
                f"{boundary_subject_release_continuity_report.maturity_subject_count} maturity / "
                f"{boundary_subject_release_continuity_report.guarded_completion_subject_count} guarded / "
                f"{boundary_subject_release_continuity_report.readiness_reconciliation_subject_count} readiness / "
                f"{boundary_subject_release_continuity_report.terminal_release_subject_count} terminal"
            ),
            variant=(
                "success"
                if boundary_subject_release_continuity_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_boundary_subject_release_continuity_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="release_closure_ledger",
            label="Release closure ledger",
            value=(
                f"{release_closure_ledger_report.ready_stage_count}/"
                f"{release_closure_ledger_report.stage_count} ready"
            ),
            detail=(
                f"{release_closure_ledger_report.stage_order_count} ordered / "
                f"{release_closure_ledger_report.upstream_dependency_ready_count}/"
                f"{release_closure_ledger_report.upstream_dependency_count} deps / "
                f"{release_closure_ledger_report.release_gate_check_count} gate / "
                f"{release_closure_ledger_report.dashboard_card_count} cards"
            ),
            variant=(
                "success"
                if release_closure_ledger_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_release_closure_ledger_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="boundary_release_envelopes",
            label="Boundary release envelopes",
            value=(
                f"{boundary_maturity_release_envelope_report.ready_envelope_count}/"
                f"{boundary_maturity_release_envelope_report.envelope_count} ready"
            ),
            detail=(
                f"{boundary_maturity_release_envelope_report.l5_blocker_enveloped_count}/"
                f"{boundary_maturity_release_envelope_report.envelope_count} L5 blockers enveloped / "
                f"{boundary_maturity_release_envelope_report.external_handoff_count} handoff / "
                f"{boundary_maturity_release_envelope_report.guarded_completion_count} guarded / "
                f"{boundary_maturity_release_envelope_report.terminal_trace_count} terminal / "
                f"{boundary_maturity_release_envelope_report.retained_gap_count}/"
                f"{maturity_upgrade_report.gap_count} retained gaps enveloped"
            ),
            variant=(
                "success"
                if boundary_maturity_release_envelope_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_boundary_maturity_release_envelope_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="retained_gap_exit_criteria",
            label="Retained gap exit criteria",
            value=(
                f"{retained_gap_exit_criteria_report.release_allowed_count}/"
                f"{retained_gap_exit_criteria_report.criteria_count} release-allowed"
            ),
            detail=(
                f"{retained_gap_exit_criteria_report.envelope_link_count} envelopes / "
                f"{retained_gap_exit_criteria_report.handoff_link_count} handoffs / "
                f"{retained_gap_exit_criteria_report.guarded_completion_link_count} guarded / "
                f"{retained_gap_exit_criteria_report.boundary_capability_link_count} boundary rows / "
                f"{retained_gap_exit_criteria_report.external_receipt_alignment_count}/"
                f"{retained_gap_exit_criteria_report.criteria_count} receipt-aligned / "
                f"{retained_gap_exit_criteria_report.external_receipt_target_count} receipts / "
                f"{retained_gap_exit_criteria_report.exit_signal_count} exit signals / "
                f"{retained_gap_exit_criteria_report.prohibited_core_claim_count} prohibited claims"
            ),
            variant=(
                "success"
                if retained_gap_exit_criteria_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_retained_gap_exit_criteria_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="release_residual_ratios",
            label="Release residual ratios",
            value=(
                f"{release_residual_ratio_ledger_report.published_ratio_count}/"
                f"{release_residual_ratio_ledger_report.ratio_count} published"
            ),
            detail=(
                f"{release_residual_ratio_ledger_report.non_full_ratio_count} non-full / "
                f"{release_residual_ratio_ledger_report.readiness_reconciliation_link_count} readiness links / "
                f"{release_residual_ratio_ledger_report.release_envelope_link_count} envelopes / "
                f"{release_residual_ratio_ledger_report.retained_gap_exit_criteria_link_count} exit criteria / "
                f"{release_residual_ratio_ledger_report.retained_gap_receipt_alignment_link_count} receipt alignments / "
                f"{release_residual_ratio_ledger_report.count_delivery_boundary_alignment_count}/"
                f"{release_residual_ratio_ledger_report.count_delivery_boundary_link_count} "
                "count/delivery boundary links aligned / "
                f"{release_residual_ratio_ledger_report.count_delivery_receipt_alignment_count}/"
                f"{release_residual_ratio_ledger_report.count_delivery_receipt_alignment_link_count} "
                "count/delivery receipts aligned / "
                f"{release_residual_ratio_ledger_report.boundary_scope_alignment_count}/"
                f"{release_residual_ratio_ledger_report.boundary_scope_link_count} "
                "boundary scopes guarded / "
                f"{boundary_maturity_release_envelope_report.l5_blocker_enveloped_count}/"
                f"{boundary_maturity_release_envelope_report.envelope_count} L5 enveloped / "
                f"{release_residual_ratio_ledger_report.maturity_l5_blocker_receipt_alignment_count}/"
                f"{release_residual_ratio_ledger_report.maturity_l5_blocker_receipt_alignment_link_count} "
                "L5 receipts aligned"
            ),
            variant=(
                "success"
                if release_residual_ratio_ledger_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_release_residual_ratio_ledger_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="release_residual_explanations",
            label="Release residual explanations",
            value=(
                f"{release_residual_explanation_report.covered_count}/"
                f"{release_residual_explanation_report.row_count} covered"
            ),
            detail=(
                f"{release_residual_explanation_report.mismatch_count} mismatches / "
                f"{release_residual_explanation_report.missing_summary_marker_count} marker gaps / "
                f"{release_residual_explanation_report.missing_source_evidence_count} source gaps"
            ),
            variant=(
                "success"
                if release_residual_explanation_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_release_residual_explanation_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="release_acceptance_certificate",
            label="Release acceptance",
            value=(
                f"{release_acceptance_certificate_report.ready_certificate_count}/"
                f"{release_acceptance_certificate_report.certificate_count} certified"
            ),
            detail=(
                f"{release_acceptance_certificate_report.component_report_count} components / "
                f"{release_acceptance_certificate_report.expected_count_match_count} count matches / "
                f"{release_acceptance_certificate_report.ready_receipt_certificate_count}/"
                f"{release_acceptance_certificate_report.receipt_certificate_count} "
                "receipt certificates / "
                f"{release_residual_ratio_ledger_report.maturity_l5_blocker_alignment_count}/"
                f"{release_residual_ratio_ledger_report.maturity_l5_blocker_release_envelope_count} "
                "L5 blockers aligned / "
                f"{release_acceptance_certificate_report.ready_requirement_dimension_count}/"
                f"{release_acceptance_certificate_report.requirement_dimension_count} "
                "requirement dimensions / "
                f"{release_acceptance_certificate_report.ready_source_evidence_count}/"
                f"{release_acceptance_certificate_report.source_evidence_count} evidence / "
                f"{release_acceptance_certificate_report.missing_source_evidence_count} source gaps"
            ),
            variant=(
                "success"
                if release_acceptance_certificate_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_release_acceptance_certificate_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="control_contracts",
            label="Control contracts",
            value=f"{control_contract_count} contracts",
            detail="scene controls share template-management semantics",
            variant="success",
            source_ids=("scene_control_consistency_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="control_runtime",
            label="Control runtime",
            value=(
                f"{control_runtime_report.ready_runtime_control_count}/"
                f"{control_runtime_report.runtime_control_count} runtime"
            ),
            detail=(
                f"{control_runtime_report.control_contract_link_count} contract links / "
                f"{control_runtime_report.shared_component_count} shared components / "
                f"{control_runtime_report.scene_surface_count} scene surfaces / "
                f"{control_runtime_report.runtime_consumer_count} consumers"
            ),
            variant=(
                "success" if control_runtime_report.issue_count == 0 else "warning"
            ),
            source_ids=("scene_control_runtime_consistency_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="count_profiles",
            label="CountProfiles",
            value=(
                f"{count_profile_report.ready_family_count}/"
                f"{count_profile_report.family_count} families"
            ),
            detail=(
                f"{count_profile_report.referenced_profile_count}/"
                f"{count_profile_report.profile_count} profiles referenced / "
                f"{count_profile_report.accounted_family_count}/"
                f"{count_profile_report.family_count} accounted / "
                f"{count_profile_report.boundary_family_count} boundary / "
                f"{count_profile_report.unique_scope_count} scopes / "
                f"{count_profile_report.unique_primary_metric_count} metrics / "
                f"{count_profile_report.rule_source_profile_count} rule-backed"
            ),
            variant=(
                "success" if count_profile_report.issue_count == 0 else "warning"
            ),
            source_ids=("scene_count_profile_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="input_sources",
            label="Input sources",
            value=(
                f"{input_source_report.ready_input_pack_count}/"
                f"{input_source_report.input_pack_count} packs"
            ),
            detail=(
                f"{input_source_report.ready_family_count}/"
                f"{input_source_report.family_count} families / "
                f"{input_source_report.accepted_format_count} formats / "
                f"{input_source_report.structured_format_count} structured / "
                f"{input_source_report.boundary_input_source_count} boundary"
            ),
            variant=(
                "success" if input_source_report.issue_count == 0 else "warning"
            ),
            source_ids=("scene_input_source_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="material_schema",
            label="Material schemas",
            value=(
                f"{material_schema_report.referenced_schema_count}/"
                f"{material_schema_report.schema_count} referenced"
            ),
            detail=(
                f"{material_schema_report.ready_material_family_count}/"
                f"{material_schema_report.material_family_count} material families / "
                f"{material_schema_report.ready_material_pack_count}/"
                f"{material_schema_report.material_pack_count} packs / "
                f"{material_schema_report.required_field_count} fields / "
                f"{material_schema_report.required_asset_count} assets"
            ),
            variant=(
                "success" if material_schema_report.issue_count == 0 else "warning"
            ),
            source_ids=("scene_material_schema_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="material_repair_flow",
            label="Material repair",
            value=(
                f"{material_repair_flow_report.ready_flow_count}/"
                f"{material_repair_flow_report.flow_count} flows"
            ),
            detail=(
                f"{material_repair_flow_report.material_signal_count} signals / "
                f"{material_repair_flow_report.repair_target_type_count} targets / "
                f"{material_repair_flow_report.ui_surface_count} UI surfaces / "
                f"{material_repair_flow_report.test_evidence_count} tests"
            ),
            variant=(
                "success"
                if material_repair_flow_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_material_repair_flow_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="fixed_layout_profile",
            label="Fixed layout",
            value=(
                f"{fixed_layout_profile_report.ready_profile_channel_count}/"
                f"{fixed_layout_profile_report.profile_channel_count} channels"
            ),
            detail=(
                f"{fixed_layout_profile_report.fixed_layout_surface_count} surfaces / "
                f"{fixed_layout_profile_report.word_ooxml_touchpoint_count} OOXML / "
                f"{fixed_layout_profile_report.runtime_surface_count} runtime / "
                f"{fixed_layout_profile_report.test_evidence_count} tests"
            ),
            variant=(
                "success"
                if fixed_layout_profile_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_fixed_layout_profile_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="report_artifact_drilldown",
            label="Report artifacts",
            value=(
                f"{report_artifact_drilldown_report.ready_drilldown_channel_count}/"
                f"{report_artifact_drilldown_report.drilldown_channel_count} channels"
            ),
            detail=(
                f"{report_artifact_drilldown_report.artifact_kind_count} kinds / "
                f"{report_artifact_drilldown_report.runtime_surface_count} runtime / "
                f"{report_artifact_drilldown_report.ui_surface_count} UI / "
                f"{report_artifact_drilldown_report.test_evidence_count} tests"
            ),
            variant=(
                "success"
                if report_artifact_drilldown_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_report_artifact_drilldown_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="delivery_presets",
            label="Delivery presets",
            value=(
                f"{delivery_preset_report.ready_family_count}/"
                f"{delivery_preset_report.family_count} families"
            ),
            detail=(
                f"{delivery_preset_report.delivery_preset_count} unique presets / "
                f"{delivery_preset_report.accounted_family_count}/"
                f"{delivery_preset_report.family_count} families accounted / "
                f"{delivery_preset_report.accounted_delivery_pack_count}/"
                f"{delivery_preset_report.delivery_pack_count} packs accounted / "
                f"{delivery_preset_report.compare_docx_preset_count} compare / "
                f"{delivery_preset_report.report_only_preset_count} report-only / "
                f"{delivery_preset_report.material_package_preset_count} package / "
                f"{delivery_preset_report.content_visibility_rule_count} visibility rules"
            ),
            variant=(
                "success" if delivery_preset_report.issue_count == 0 else "warning"
            ),
            source_ids=("scene_delivery_preset_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="delivery_execution",
            label="Delivery execution",
            value=(
                f"{delivery_execution_report.ready_execution_channel_count}/"
                f"{delivery_execution_report.execution_channel_count} channels"
            ),
            detail=(
                f"{delivery_execution_report.required_output_signal_count} output signals / "
                f"{delivery_execution_report.payload_key_count} payload keys / "
                f"{delivery_execution_report.runtime_surface_count} runtime surfaces / "
                f"{delivery_execution_report.test_evidence_count} tests"
            ),
            variant=(
                "success"
                if delivery_execution_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_delivery_preset_execution_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="formula_output_watermark",
            label="Formula/output/watermark",
            value=(
                f"{formula_output_watermark_report.ready_capability_count}/"
                f"{formula_output_watermark_report.capability_count} ready"
            ),
            detail=(
                f"{formula_output_watermark_report.formula_family_count} formula / "
                f"{formula_output_watermark_report.output_family_count} output / "
                f"{formula_output_watermark_report.watermark_family_count} watermark families / "
                f"{formula_output_watermark_report.plugin_gate_count} plugin gates"
            ),
            variant=(
                "success"
                if formula_output_watermark_report.issue_count == 0
                else "warning"
            ),
            source_ids=("scene_formula_output_watermark_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="readiness",
            label="Readiness",
            value=f"{product_readiness_subject_count} subjects",
            detail=(
                f"{terminal_release_exception_report.static_closed_boundary_count}/"
                f"{static_closed_but_not_green_count} static-closed governed; "
                "not overclaimed as Green/L5"
            ),
            variant="warning" if static_closed_but_not_green_count else "success",
            source_ids=("scene_product_readiness",),
        ),
        SceneMatrixDashboardCard(
            card_id="maturity_upgrade",
            label="Maturity upgrade",
            value=(
                f"{maturity_upgrade_report.green_subject_count}/"
                f"{maturity_upgrade_report.subject_count} Green"
            ),
            detail=(
                f"{maturity_upgrade_report.l5_blocked_subject_count} L5-blocked / "
                f"{boundary_maturity_release_envelope_report.l5_blocker_enveloped_count}/"
                f"{maturity_upgrade_report.l5_blocked_subject_count} L5 enveloped / "
                f"{boundary_maturity_release_envelope_report.retained_gap_count}/"
                f"{maturity_upgrade_report.gap_count} retained gaps enveloped / "
                f"{maturity_upgrade_report.gap_count} gaps / "
                f"{maturity_upgrade_report.gap_domain_count}/"
                f"{maturity_upgrade_report.gap_domain_count} domains classified / "
                f"{maturity_upgrade_report.boundary_subject_count} boundary subjects"
            ),
            variant=(
                "success"
                if maturity_upgrade_report.l5_blocked_subject_count == 0
                else "warning"
            ),
            source_ids=("scene_product_maturity_upgrade_audit",),
        ),
        SceneMatrixDashboardCard(
            card_id="gate",
            label="Gate",
            value="passed" if issue_count == 0 else "failed",
            detail=f"{issue_count} blockers / {warning_count} warnings",
            variant="success" if issue_count == 0 else "warning",
            source_ids=SCENE_MATRIX_DASHBOARD_SOURCE_IDS,
        ),
    )


def _status_counts(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    counts = Counter(value for value in values if value)
    return tuple(sorted(counts.items()))


def _issue(
    scope_type: str,
    scope_id: str,
    kind: str,
    message: str,
    *,
    severity: str = "error",
) -> SceneMatrixDashboardIssue:
    return SceneMatrixDashboardIssue(
        scope_type=scope_type,
        scope_id=scope_id,
        kind=kind,
        message=message,
        severity=severity,
    )


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_MATRIX_DASHBOARD_LENS_IDS",
    "SCENE_MATRIX_DASHBOARD_LENSES",
    "SCENE_MATRIX_DASHBOARD_SOURCE_IDS",
    "SceneMatrixDashboardCard",
    "SceneMatrixDashboardIssue",
    "SceneMatrixDashboardLens",
    "SceneMatrixDashboardReport",
    "SceneMatrixDashboardRow",
    "audit_scene_matrix_dashboard",
    "build_scene_matrix_dashboard",
]
