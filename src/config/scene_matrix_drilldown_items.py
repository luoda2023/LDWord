"""Item factories for scene matrix drilldown reports."""

from __future__ import annotations

from typing import Callable

from src.config.scene_ambiguity_clarification_ui_audit import (
    build_scene_ambiguity_clarification_ui_audit_report,
)
from src.config.scene_business_capability_matrix_audit import (
    build_scene_business_capability_matrix_audit_report,
)
from src.config.scene_control_runtime_consistency_audit import (
    build_scene_control_runtime_consistency_audit_report,
)
from src.config.scene_count_profile_audit import (
    build_scene_count_profile_audit_report,
)
from src.config.scene_delivery_preset_audit import (
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_delivery_preset_execution_audit import (
    build_scene_delivery_preset_execution_audit_report,
)
from src.config.scene_external_handoff_contract_audit import (
    build_scene_external_handoff_contract_audit_report,
)
from src.config.scene_family_fixture_depth_audit import (
    build_scene_family_fixture_depth_audit_report,
)
from src.config.scene_fixed_layout_profile_audit import (
    build_scene_fixed_layout_profile_audit_report,
)
from src.config.scene_formula_output_watermark_audit import (
    build_scene_formula_output_watermark_audit_report,
)
from src.config.scene_import_handoff_audit import (
    build_scene_import_handoff_audit_report,
)
from src.config.scene_input_source_audit import (
    build_scene_input_source_audit_report,
)
from src.config.scene_material_repair_flow_audit import (
    build_scene_material_repair_flow_audit_report,
)
from src.config.scene_material_schema_audit import (
    build_scene_material_schema_audit_report,
)
from src.config.scene_matrix_dashboard import build_scene_matrix_dashboard
from src.config.scene_matrix_drilldown_models import (
    SceneMatrixDrilldownItem,
    SceneMatrixDrilldownRow,
)
from src.config.scene_matrix_drilldown_release_items import (
    _boundary_guarded_completion_item,
    _boundary_maturity_release_envelope_item,
    _boundary_readiness_reconciliation_item,
    _boundary_subject_release_continuity_item,
    _boundary_subject_release_dossier_item,
    _non_subject_release_trace_attribution_item,
    _release_acceptance_certificate_item,
    _release_closure_ledger_item,
    _release_projection_surface_parity_item,
    _release_residual_explanation_item,
    _release_residual_ratio_ledger_item,
    _release_trace_partition_guard_item,
    _residual_warning_governance_item,
    _retained_gap_exit_criteria_item,
    _terminal_release_exception_item,
)
from src.config.scene_object_preflight_action_audit import (
    build_scene_object_preflight_action_audit_report,
)
from src.config.scene_plugin_boundary_confirmation_audit import (
    build_scene_plugin_boundary_confirmation_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_report_artifact_drilldown_audit import (
    build_scene_report_artifact_drilldown_audit_report,
)
from src.config.scene_request_cell_fixture_registry import (
    build_scene_request_cell_registry_browser,
)
from src.config.scene_user_journey_fixture_audit import (
    build_scene_user_journey_fixture_audit_report,
)
from src.config.scene_word_risk_closure_audit import (
    build_scene_word_risk_closure_audit_report,
)


SceneMatrixDrilldownItemFactory = Callable[[], SceneMatrixDrilldownItem]


def _item_factories_for_source(
    source_id: str,
) -> tuple[SceneMatrixDrilldownItemFactory, ...]:
    factories: tuple[
        tuple[str, SceneMatrixDrilldownItemFactory],
        ...,
    ] = (
        ("scene_matrix_dashboard", _dashboard_item),
        ("scene_request_cell_registry_browser", _request_cell_item),
        (
            "scene_ambiguity_clarification_ui_audit",
            _ambiguity_clarification_item,
        ),
        ("scene_user_journey_fixture_audit", _user_journey_fixture_item),
        (
            "scene_business_capability_matrix_audit",
            _business_capability_matrix_item,
        ),
        (
            "scene_control_runtime_consistency_audit",
            _control_runtime_consistency_item,
        ),
        ("scene_plugin_boundary_confirmation_audit", _plugin_boundary_item),
        ("scene_external_handoff_contract_audit", _external_handoff_contract_item),
        (
            "scene_boundary_guarded_completion_audit",
            _boundary_guarded_completion_item,
        ),
        (
            "scene_residual_warning_governance_audit",
            _residual_warning_governance_item,
        ),
        (
            "scene_boundary_readiness_reconciliation_audit",
            _boundary_readiness_reconciliation_item,
        ),
        ("scene_terminal_release_exception_audit", _terminal_release_exception_item),
        (
            "scene_boundary_subject_release_dossier_audit",
            _boundary_subject_release_dossier_item,
        ),
        (
            "scene_non_subject_release_trace_attribution_audit",
            _non_subject_release_trace_attribution_item,
        ),
        (
            "scene_release_trace_partition_guard_audit",
            _release_trace_partition_guard_item,
        ),
        (
            "scene_release_projection_surface_parity_audit",
            _release_projection_surface_parity_item,
        ),
        (
            "scene_boundary_subject_release_continuity_audit",
            _boundary_subject_release_continuity_item,
        ),
        ("scene_release_closure_ledger_audit", _release_closure_ledger_item),
        (
            "scene_boundary_maturity_release_envelope_audit",
            _boundary_maturity_release_envelope_item,
        ),
        (
            "scene_retained_gap_exit_criteria_audit",
            _retained_gap_exit_criteria_item,
        ),
        (
            "scene_release_residual_ratio_ledger_audit",
            _release_residual_ratio_ledger_item,
        ),
        (
            "scene_release_residual_explanation_audit",
            _release_residual_explanation_item,
        ),
        (
            "scene_release_acceptance_certificate_audit",
            _release_acceptance_certificate_item,
        ),
        ("scene_word_risk_closure_audit", _word_risk_item),
        ("scene_import_handoff_audit", _import_handoff_item),
        ("scene_input_source_audit", _input_source_item),
        ("scene_object_preflight_action_audit", _object_preflight_action_item),
        ("scene_family_fixture_depth_audit", _family_fixture_depth_item),
        ("scene_count_profile_audit", _count_profile_item),
        ("scene_material_schema_audit", _material_schema_item),
        ("scene_material_repair_flow_audit", _material_repair_flow_item),
        ("scene_fixed_layout_profile_audit", _fixed_layout_profile_item),
        (
            "scene_report_artifact_drilldown_audit",
            _report_artifact_drilldown_item,
        ),
        ("scene_delivery_preset_audit", _delivery_preset_item),
        ("scene_delivery_preset_execution_audit", _delivery_execution_item),
        (
            "scene_formula_output_watermark_audit",
            _formula_output_watermark_item,
        ),
        ("scene_product_maturity_upgrade_audit", _maturity_upgrade_item),
    )
    if not source_id:
        return tuple(factory for _, factory in factories)
    return tuple(
        factory for item_source_id, factory in factories if item_source_id == source_id
    )


def _dashboard_item() -> SceneMatrixDrilldownItem:
    report = build_scene_matrix_dashboard()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.pack_id,
            label=row.label,
            status=row.status,
            source_id="scene_matrix_dashboard",
            detail=(
                f"{row.request_cell_count} request cells / "
                f"{row.family_count} families / "
                f"{row.sample_fixture_count} fixtures / "
                f"{row.product_readiness_level}"
            ),
            pack_ids=(row.pack_id,),
            family_ids=row.family_ids,
            request_cell_ids=row.request_cell_sample_ids,
            fixture_ids=row.sample_fixture_ids,
            material_schema_ids=row.material_schema_ids,
            delivery_preset_ids=row.delivery_preset_ids,
            input_source_ids=(*row.input_formats, *row.input_structured_formats),
            render_source_ids=row.input_render_source_ids,
            object_preflight_target_ids=row.object_preflight_target_ids,
            word_risk_surface_ids=row.word_risk_surface_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="matrix_dashboard",
        label="Matrix dashboard",
        source_id="scene_matrix_dashboard",
        lens_ids=tuple(lens.lens_id for lens in report.lenses),
        route_hint="pack -> lenses -> source rows",
        detail="Browse the 12 pack rows and their lens/source evidence.",
        rows=rows,
        visible_rows=rows,
    )


def _request_cell_item() -> SceneMatrixDrilldownItem:
    browser = build_scene_request_cell_registry_browser()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=item.sample_id,
            label=item.request_text,
            status=item.expected_status,
            source_id="scene_request_cell_registry_browser",
            detail=f"{item.coverage_label} / {item.status_label}",
            pack_ids=item.expected_pack_ids,
            family_ids=item.expected_family_ids,
            request_cell_ids=(item.sample_id,),
            fixture_ids=item.fixture_ids,
            plugin_gate_ids=item.manual_gate_ids,
            issue_ids=(),
        )
        for item in browser.items
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="request_cells",
        label="Request cells",
        source_id="scene_request_cell_registry_browser",
        lens_ids=("user_request", "evidence_chain", "boundary"),
        route_hint="request-cell -> fixture/manual/negative evidence",
        detail="Browse high-frequency request samples and their fixture evidence.",
        rows=rows,
        visible_rows=rows,
    )


def _ambiguity_clarification_item() -> SceneMatrixDrilldownItem:
    report = build_scene_ambiguity_clarification_ui_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.clarification_id,
            label=row.request_text,
            status=row.status,
            source_id="scene_ambiguity_clarification_ui_audit",
            detail=(
                f"{row.clarification_axis}; "
                f"routes={','.join(row.candidate_route_ids) or '-'}; "
                f"anchor={row.report_anchor_id}"
            ),
            pack_ids=row.candidate_pack_ids,
            family_ids=row.candidate_family_ids,
            request_cell_ids=(row.sample_id,),
            fixture_ids=row.fixture_ids,
            action_behavior_ids=(
                "ambiguity_clarification",
                *row.decision_record_fields,
            ),
            capability_ids=row.ui_surface_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="ambiguity_clarification",
        label="Ambiguity clarification",
        source_id="scene_ambiguity_clarification_ui_audit",
        lens_ids=("user_request", "boundary", "evidence_chain"),
        route_hint="ambiguous request -> clarification prompt -> candidate route/pack -> decision record",
        detail="Browse visible clarification questions, candidate landings, UI surfaces, and decision-record fields.",
        rows=rows,
        visible_rows=rows,
    )


def _user_journey_fixture_item() -> SceneMatrixDrilldownItem:
    report = build_scene_user_journey_fixture_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.path_id,
            label=row.label,
            status=row.status,
            source_id="scene_user_journey_fixture_audit",
            detail=(
                f"{row.journey_type} / "
                f"sources={','.join(row.source_ids) or '-'} / "
                f"behaviors={','.join(row.expected_behaviors) or '-'}"
            ),
            pack_ids=row.pack_ids,
            family_ids=row.family_ids,
            request_cell_ids=row.request_cell_ids,
            fixture_ids=row.fixture_ids,
            plugin_gate_ids=row.manual_gate_ids,
            action_behavior_ids=(row.journey_type, *row.expected_behaviors),
            issue_ids=row.issue_ids,
        )
        for row in report.path_rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="user_journey_fixture",
        label="User journey fixtures",
        source_id="scene_user_journey_fixture_audit",
        lens_ids=("user_request", "boundary", "evidence_chain"),
        route_hint="journey type -> request cell -> fixture/manual/handoff evidence",
        detail="Browse success, degraded, failure, manual-boundary, ambiguous, handoff, and negative-control user journeys.",
        rows=rows,
        visible_rows=rows,
    )


def _business_capability_matrix_item() -> SceneMatrixDrilldownItem:
    report = build_scene_business_capability_matrix_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.capability_id,
            label=row.label,
            status=row.status,
            source_id="scene_business_capability_matrix_audit",
            detail=(
                f"{row.priority} / {row.group_id} / "
                f"boundary={row.boundary_policy} / "
                f"missing={','.join(row.missing_journey_groups) or '-'}"
            ),
            pack_ids=row.pack_ids,
            family_ids=row.family_ids,
            request_cell_ids=row.request_cell_ids,
            fixture_ids=row.fixture_ids,
            count_profile_ids=row.count_profile_ids,
            material_schema_ids=row.material_schema_ids,
            delivery_preset_ids=row.delivery_preset_ids,
            input_source_ids=row.input_format_ids,
            action_behavior_ids=(
                *row.journey_type_ids,
                *row.required_journey_groups,
                *row.missing_journey_groups,
            ),
            capability_ids=(
                row.group_id,
                row.boundary_policy,
                *row.adopted_external_record_ids,
                *row.control_alignment_ids,
            ),
            plugin_gate_ids=row.manual_gate_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="business_capability_matrix",
        label="Business capability matrix",
        source_id="scene_business_capability_matrix_audit",
        lens_ids=(
            "user_request",
            "carrier_layer",
            "fact_source",
            "boundary",
            "evidence_chain",
            "product_readiness",
        ),
        route_hint="business capability -> pack/family -> request cell -> fixture/journey/boundary",
        detail=(
            "Browse high-frequency business capabilities, boundary policies, "
            "absorbed planning records, and missing journey-depth groups."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _control_runtime_consistency_item() -> SceneMatrixDrilldownItem:
    report = build_scene_control_runtime_consistency_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.runtime_id,
            label=row.label,
            status=row.status,
            source_id="scene_control_runtime_consistency_audit",
            detail=(
                f"{len(row.contract_ids)} contracts / "
                f"{len(row.shared_component_ids)} components / "
                f"{len(row.runtime_consumer_ids)} consumers / "
                f"{row.scope}"
            ),
            action_behavior_ids=row.required_semantics,
            capability_ids=(
                *row.contract_ids,
                *row.shared_component_ids,
                *row.scene_surface_ids,
                *row.template_surface_ids,
                *row.runtime_consumer_ids,
            ),
            word_risk_surface_ids=(
                ("fixed_row_height",)
                if row.runtime_id == "fixed_layout_row_height_profile"
                else ()
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="control_runtime_consistency",
        label="Control runtime consistency",
        source_id="scene_control_runtime_consistency_audit",
        lens_ids=("control_contract", "evidence_chain"),
        route_hint="runtime control group -> shared component -> scene/template evidence -> consumer path",
        detail="Browse scene controls that must stay aligned with template-management naming, units, grouping, disabled state, and runtime consumers.",
        rows=rows,
        visible_rows=rows,
    )


def _plugin_boundary_item() -> SceneMatrixDrilldownItem:
    report = build_scene_plugin_boundary_confirmation_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.gate_id,
            label=row.label,
            status=row.status,
            source_id="scene_plugin_boundary_confirmation_audit",
            detail=(
                f"{len(row.risk_domain_ids)} risk domains / "
                f"{len(row.request_cell_sample_ids)} request cells"
            ),
            pack_ids=(row.pack_id,),
            request_cell_ids=row.request_cell_sample_ids,
            fixture_ids=row.manual_fixture_ids,
            plugin_gate_ids=(row.gate_id,),
            risk_domain_ids=row.risk_domain_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="plugin_boundary",
        label="Plugin/manual boundary",
        source_id="scene_plugin_boundary_confirmation_audit",
        lens_ids=("boundary", "evidence_chain"),
        route_hint="gate -> risk domains -> manual confirmation evidence",
        detail="Browse plugin/manual gates and the non-core promises they guard.",
        rows=rows,
        visible_rows=rows,
    )


def _external_handoff_contract_item() -> SceneMatrixDrilldownItem:
    report = build_scene_external_handoff_contract_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.contract_id,
            label=row.label,
            status=row.status,
            source_id="scene_external_handoff_contract_audit",
            detail=(
                f"gap={row.gap_id} / "
                f"{len(row.required_report_ids)} reports / "
                f"{len(row.status_ids)} states / "
                f"{len(row.failure_policy_ids)} failure policies"
            ),
            pack_ids=(row.subject_id,) if row.subject_type == "pack" else (),
            family_ids=(row.subject_id,) if row.subject_type == "family" else (),
            fixture_ids=row.fixture_ids,
            action_behavior_ids=(
                *row.status_ids,
                *row.failure_policy_ids,
                *row.payload_field_ids,
            ),
            capability_ids=(
                row.gap_id,
                row.target_plugin_id,
                *row.boundary_capability_ids,
                *row.required_report_ids,
                *row.ui_surface_ids,
                *row.excluded_core_claims,
            ),
            maturity_gap_domain_ids=("boundary_gate",),
            plugin_gate_ids=(row.gate_id,),
            risk_domain_ids=row.risk_domain_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="external_handoff_contract",
        label="External handoff contracts",
        source_id="scene_external_handoff_contract_audit",
        lens_ids=("boundary", "evidence_chain", "product_readiness"),
        route_hint="remaining gap -> plugin gate -> payload/status/failure policy -> receipt",
        detail="Browse external plugin/professional handoff contracts for Blue/Boundary subjects.",
        rows=rows,
        visible_rows=rows,
    )


def _word_risk_item() -> SceneMatrixDrilldownItem:
    report = build_scene_word_risk_closure_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.surface_id,
            label=row.label,
            status=row.status,
            source_id="scene_word_risk_closure_audit",
            detail=(
                f"{len(row.pack_ids)} packs / "
                f"{len(row.sample_fixture_ids)} fixtures / "
                f"{len(row.preflight_targets)} preflight targets"
            ),
            pack_ids=row.pack_ids,
            fixture_ids=row.sample_fixture_ids,
            word_risk_surface_ids=(row.surface_id,),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="word_risk",
        label="Word/OOXML risk",
        source_id="scene_word_risk_closure_audit",
        lens_ids=("word_risk", "evidence_chain"),
        route_hint="risk surface -> packs -> fixtures -> preflight targets",
        detail="Browse OOXML risk surfaces touched by high-frequency scenes.",
        rows=rows,
        visible_rows=rows,
    )


def _import_handoff_item() -> SceneMatrixDrilldownItem:
    report = build_scene_import_handoff_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.handoff_id,
            label=row.request_text,
            status=row.status,
            source_id="scene_import_handoff_audit",
            detail=(
                f"{row.source_pack_id} -> {row.target_pack_id}/"
                f"{row.target_family_id}; fallback={row.fallback_strategy}"
            ),
            pack_ids=(row.source_pack_id, row.target_pack_id),
            family_ids=(row.target_family_id,),
            request_cell_ids=(row.sample_id,),
            fixture_ids=row.request_cell_fixture_ids,
            plugin_gate_ids=(row.plugin_gate_id,),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="import_handoff",
        label="Import/AI handoff",
        source_id="scene_import_handoff_audit",
        lens_ids=("boundary", "evidence_chain"),
        route_hint="source pack -> manual gate -> target pack/family",
        detail="Browse import/AI requests that can hand off to a target scene.",
        rows=rows,
        visible_rows=rows,
    )


def _input_source_item() -> SceneMatrixDrilldownItem:
    report = build_scene_input_source_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.family_id,
            label=row.name,
            status=row.status,
            source_id="scene_input_source_audit",
            detail=(
                f"{','.join(row.actual_accepted_formats) or '-'} / "
                f"structured={','.join(row.structured_formats) or '-'} / "
                f"render={','.join(row.render_source_ids) or '-'}"
            ),
            pack_ids=row.pack_ids,
            family_ids=(row.family_id,),
            input_source_ids=(
                *row.actual_accepted_formats,
                *row.structured_formats,
                *row.high_risk_imports,
            ),
            material_schema_ids=row.actual_material_schema_ids,
            delivery_preset_ids=row.delivery_preset_ids,
            render_source_ids=row.render_source_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.family_rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="input_source",
        label="InputSourceProfile",
        source_id="scene_input_source_audit",
        lens_ids=("fact_source", "boundary", "evidence_chain"),
        route_hint="family -> accepted formats -> structured/material/render sources",
        detail="Browse input source formats, structured material schemas, render sources, and boundary imports.",
        rows=rows,
        visible_rows=rows,
    )


def _object_preflight_action_item() -> SceneMatrixDrilldownItem:
    report = build_scene_object_preflight_action_audit_report()
    target_rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=f"target:{row.target_id}",
            label=row.target_id,
            status=row.status,
            source_id="scene_object_preflight_action_audit",
            detail=(
                f"{len(row.fixture_ids)} fixtures / "
                f"{','.join(row.action_behavior_ids) or '-'} / "
                f"{len(row.block_policy_family_ids)} block families / "
                f"{len(row.skip_module_ids)} skip modules"
            ),
            pack_ids=row.pack_ids,
            fixture_ids=row.fixture_ids,
            object_preflight_target_ids=(row.target_id,),
            action_behavior_ids=row.action_behavior_ids,
            word_risk_surface_ids=row.word_risk_surface_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.target_rows
    )
    family_rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=f"family:{row.family_id}",
            label=row.name,
            status=row.status,
            source_id="scene_object_preflight_action_audit",
            detail=(
                f"{row.preservation_mode} / "
                f"recommended={','.join(row.recommended_scan_targets) or '-'} / "
                f"fixtures={','.join(row.fixture_ids) or '-'}"
            ),
            pack_ids=row.pack_ids,
            family_ids=(row.family_id,),
            fixture_ids=row.fixture_ids,
            object_preflight_target_ids=row.recommended_scan_targets,
            issue_ids=row.issue_ids,
        )
        for row in report.family_rows
    )
    rows = (*target_rows, *family_rows)
    return SceneMatrixDrilldownItem(
        drilldown_id="object_preflight_action",
        label="ObjectPreflight actions",
        source_id="scene_object_preflight_action_audit",
        lens_ids=("word_risk", "evidence_chain"),
        route_hint="target/family -> scan targets -> action behavior -> repair route",
        detail="Browse ObjectPreflight detection, blocking, module-skip, manual-confirmation, and fixture behavior.",
        rows=rows,
        visible_rows=rows,
    )


def _family_fixture_depth_item() -> SceneMatrixDrilldownItem:
    report = build_scene_family_fixture_depth_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.family_id,
            label=row.name,
            status=row.status,
            source_id="scene_family_fixture_depth_audit",
            detail=(
                f"{row.priority} / {row.independent_fixture_count} independent / "
                f"{row.manual_boundary_fixture_count} manual-boundary fixtures"
            ),
            pack_ids=row.pack_ids,
            family_ids=(row.family_id,),
            request_cell_ids=row.request_cell_sample_ids,
            fixture_ids=(
                *row.independent_fixture_ids,
                *row.manual_boundary_fixture_ids,
            ),
            plugin_gate_ids=row.plugin_gate_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="family_fixture_depth",
        label="Family fixture depth",
        source_id="scene_family_fixture_depth_audit",
        lens_ids=("carrier_layer", "fact_source", "evidence_chain"),
        route_hint="family -> request cells -> independent/manual fixtures",
        detail="Browse P1 family fixture depth and manual-boundary evidence.",
        rows=rows,
        visible_rows=rows,
    )


def _count_profile_item() -> SceneMatrixDrilldownItem:
    report = build_scene_count_profile_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.family_id,
            label=row.name,
            status=row.status,
            source_id="scene_count_profile_audit",
            detail=(
                f"{len(row.count_profile_ids)} profiles / "
                f"default={row.executable_default_count_profile_id or '-'} / "
                f"{len(row.primary_metrics)} metrics / "
                f"{len(row.rule_source_ids)} rule sources"
            ),
            pack_ids=row.pack_ids,
            family_ids=(row.family_id,),
            count_profile_ids=row.count_profile_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.family_rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="count_profile",
        label="CountProfile",
        source_id="scene_count_profile_audit",
        lens_ids=("fact_source", "evidence_chain"),
        route_hint="family -> CountProfile -> scope/metrics/rule source/report",
        detail="Browse CountProfile coverage and rule-source/report evidence for scene families.",
        rows=rows,
        visible_rows=rows,
    )


def _material_schema_item() -> SceneMatrixDrilldownItem:
    report = build_scene_material_schema_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.family_id,
            label=row.name,
            status=row.status,
            source_id="scene_material_schema_audit",
            detail=(
                f"{len(row.material_schema_ids)} schemas / "
                f"{len(row.required_field_keys)} fields / "
                f"{len(row.required_asset_roles)} assets / "
                f"batch={','.join(row.batch_modes) or '-'}"
            ),
            pack_ids=row.pack_ids,
            family_ids=(row.family_id,),
            material_schema_ids=row.material_schema_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.family_rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="material_schema",
        label="MaterialSchema",
        source_id="scene_material_schema_audit",
        lens_ids=("fact_source", "evidence_chain"),
        route_hint="family -> schema ids -> fields/assets/batch/report evidence",
        detail="Browse MaterialSchema coverage for high-frequency scene families.",
        rows=rows,
        visible_rows=rows,
    )


def _material_repair_flow_item() -> SceneMatrixDrilldownItem:
    report = build_scene_material_repair_flow_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.flow_id,
            label=row.label,
            status=row.status,
            source_id="scene_material_repair_flow_audit",
            detail=(
                f"{len(row.material_signal_ids)} signals / "
                f"{len(row.repair_target_types)} targets / "
                f"{len(row.runtime_surface_ids)} runtime / "
                f"{len(row.ui_surface_ids)} UI / "
                f"{len(row.test_ids)} tests"
            ),
            pack_ids=row.pack_ids,
            family_ids=row.family_ids,
            material_schema_ids=row.material_signal_ids,
            action_behavior_ids=(
                row.coverage_selector,
                *row.repair_target_types,
                *row.runtime_surface_ids,
            ),
            capability_ids=(
                *row.capability_ids,
                *row.ui_surface_ids,
                *row.test_ids,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="material_repair_flow",
        label="Material repair flow",
        source_id="scene_material_repair_flow_audit",
        lens_ids=("fact_source", "evidence_chain", "product_readiness"),
        route_hint="material signal -> repair target -> runtime/UI/test evidence",
        detail=(
            "Browse MaterialSchema input, diagnosis, issue queue, repair routing, "
            "profile focus, and manifest feedback flows."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _fixed_layout_profile_item() -> SceneMatrixDrilldownItem:
    report = build_scene_fixed_layout_profile_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.profile_channel_id,
            label=row.label,
            status=row.status,
            source_id="scene_fixed_layout_profile_audit",
            detail=(
                f"{len(row.fixed_layout_surface_ids)} surfaces / "
                f"{len(row.word_ooxml_touchpoints)} OOXML / "
                f"{len(row.runtime_surface_ids)} runtime / "
                f"{len(row.ui_surface_ids)} UI / "
                f"{len(row.test_ids)} tests"
            ),
            pack_ids=row.pack_ids,
            family_ids=row.family_ids,
            word_risk_surface_ids=row.fixed_layout_surface_ids,
            action_behavior_ids=(
                row.coverage_selector,
                *row.repair_target_types,
                *row.runtime_surface_ids,
            ),
            capability_ids=(
                *row.word_ooxml_touchpoints,
                *row.ui_surface_ids,
                *row.report_surface_ids,
                *row.test_ids,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="fixed_layout_profile",
        label="Fixed-layout profile",
        source_id="scene_fixed_layout_profile_audit",
        lens_ids=(
            "fact_source",
            "word_risk",
            "control_contract",
            "evidence_chain",
            "product_readiness",
        ),
        route_hint="fixed-layout surface -> OOXML touchpoint -> runtime/UI/report/test evidence",
        detail=(
            "Browse fixed row height, content-control, textbox, fixture, report, "
            "and repair-route evidence for fixed-layout form profiles."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _report_artifact_drilldown_item() -> SceneMatrixDrilldownItem:
    report = build_scene_report_artifact_drilldown_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.drilldown_channel_id,
            label=row.label,
            status=row.status,
            source_id="scene_report_artifact_drilldown_audit",
            detail=(
                f"{len(row.artifact_kind_ids)} artifact kinds / "
                f"{len(row.runtime_surface_ids)} runtime / "
                f"{len(row.ui_surface_ids)} UI / "
                f"{len(row.report_surface_ids)} report / "
                f"{len(row.test_ids)} tests"
            ),
            pack_ids=row.pack_ids,
            family_ids=row.family_ids,
            action_behavior_ids=(
                row.coverage_selector,
                *row.repair_target_types,
                *row.runtime_surface_ids,
            ),
            capability_ids=(
                *row.artifact_kind_ids,
                *row.ui_surface_ids,
                *row.report_surface_ids,
                *row.test_ids,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="report_artifact_drilldown",
        label="Report/artifact drilldown",
        source_id="scene_report_artifact_drilldown_audit",
        lens_ids=("fact_source", "evidence_chain", "product_readiness"),
        route_hint="artifact kind -> runtime payload -> UI row -> open/report/repair evidence",
        detail=(
            "Browse output, compare, report, intermediate, material package, "
            "sample manifest, and output-target repair evidence."
        ),
        rows=rows,
        visible_rows=rows,
    )


def _delivery_preset_item() -> SceneMatrixDrilldownItem:
    report = build_scene_delivery_preset_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.family_id,
            label=row.name,
            status=row.status,
            source_id="scene_delivery_preset_audit",
            detail=(
                f"{len(row.actual_delivery_preset_ids)} presets / "
                f"{row.final_docx_preset_count} final / "
                f"{row.compare_docx_preset_count} compare / "
                f"{row.report_only_preset_count} report-only / "
                f"{row.content_visibility_rule_count} visibility"
            ),
            pack_ids=row.pack_ids,
            family_ids=(row.family_id,),
            delivery_preset_ids=row.actual_delivery_preset_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.family_rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="delivery_preset",
        label="DeliveryPreset",
        source_id="scene_delivery_preset_audit",
        lens_ids=("fact_source", "evidence_chain"),
        route_hint="family -> delivery presets -> artifacts/report/visibility",
        detail="Browse DeliveryPreset coverage for high-frequency scene families.",
        rows=rows,
        visible_rows=rows,
    )


def _delivery_execution_item() -> SceneMatrixDrilldownItem:
    report = build_scene_delivery_preset_execution_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.execution_id,
            label=row.label,
            status=row.status,
            source_id="scene_delivery_preset_execution_audit",
            detail=(
                f"{len(row.required_output_signal_ids)} signals / "
                f"{len(row.payload_keys)} payload keys / "
                f"{len(row.runtime_surface_ids)} runtime / "
                f"{len(row.test_ids)} tests"
            ),
            pack_ids=row.pack_ids,
            family_ids=row.family_ids,
            delivery_preset_ids=row.required_output_signal_ids,
            action_behavior_ids=(
                row.coverage_selector,
                *row.payload_keys,
                *row.runtime_surface_ids,
            ),
            capability_ids=(
                *row.required_output_signal_ids,
                *row.report_surface_ids,
                *row.ui_surface_ids,
            ),
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="delivery_execution",
        label="Delivery execution",
        source_id="scene_delivery_preset_execution_audit",
        lens_ids=("fact_source", "evidence_chain"),
        route_hint="execution channel -> output signals -> payload/report/UI/test evidence",
        detail="Browse DeliveryPreset execution completeness across final DOCX, compare, reports, packages, intermediate artifacts, failure isolation, and UI surfacing.",
        rows=rows,
        visible_rows=rows,
    )


def _formula_output_watermark_item() -> SceneMatrixDrilldownItem:
    report = build_scene_formula_output_watermark_audit_report()
    capability_rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=f"capability:{row.capability_id}",
            label=row.label,
            status=row.status,
            source_id="scene_formula_output_watermark_audit",
            detail=(
                f"owner={row.expected_owner_layer} / "
                f"{len(row.parameter_paths)} params / "
                f"{len(row.control_contract_ids)} contracts / "
                f"{len(row.execution_consumers)} consumers"
            ),
            pack_ids=row.pack_ids,
            family_ids=row.family_ids,
            action_behavior_ids=(row.expected_owner_layer,),
            capability_ids=(
                row.capability_id,
                *row.parameter_paths,
                *row.template_baseline_paths,
                *row.control_contract_ids,
                *row.execution_consumers,
            ),
            plugin_gate_ids=row.plugin_gate_ids,
            risk_domain_ids=row.plugin_risk_domain_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.capability_rows
    )
    family_rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=row.family_id,
            label=row.name,
            status=row.status,
            source_id="scene_formula_output_watermark_audit",
            detail=(
                f"{','.join(row.capability_ids)} / "
                f"formula={row.formula_relevant} / "
                f"output={row.output_relevant} / "
                f"watermark={row.watermark_relevant}"
            ),
            pack_ids=row.pack_ids,
            family_ids=(row.family_id,),
            delivery_preset_ids=row.delivery_preset_ids,
            capability_ids=row.capability_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.family_rows
    )
    rows = (*capability_rows, *family_rows)
    return SceneMatrixDrilldownItem(
        drilldown_id="formula_output_watermark",
        label="Formula/output/watermark",
        source_id="scene_formula_output_watermark_audit",
        lens_ids=("fact_source", "control_contract", "evidence_chain"),
        route_hint="family -> formula/output/watermark capability ownership",
        detail="Browse formula, output, and watermark ownership for scene families.",
        rows=rows,
        visible_rows=rows,
    )


def _maturity_upgrade_item() -> SceneMatrixDrilldownItem:
    report = build_scene_product_maturity_upgrade_audit_report()
    rows = tuple(
        SceneMatrixDrilldownRow(
            row_id=f"{row.subject_type}:{row.subject_id}",
            label=row.label,
            status=row.status,
            source_id="scene_product_maturity_upgrade_audit",
            detail=(
                f"{row.current_readiness_level} -> {row.next_upgrade_goal}; "
                f"{row.l5_blocker_count} gaps / "
                f"{','.join(row.gap_domain_ids) or '-'}"
            ),
            pack_ids=row.pack_ids,
            family_ids=row.family_ids,
            maturity_gap_domain_ids=row.gap_domain_ids,
            issue_ids=row.issue_ids,
        )
        for row in report.rows
    )
    return SceneMatrixDrilldownItem(
        drilldown_id="maturity_upgrade",
        label="Maturity upgrade",
        source_id="scene_product_maturity_upgrade_audit",
        lens_ids=("product_readiness", "evidence_chain"),
        route_hint="pack/family -> readiness level -> L5 blocker domains",
        detail="Browse product maturity gaps that block Green/L5 promotion.",
        rows=rows,
        visible_rows=rows,
    )


__all__ = [
    "SceneMatrixDrilldownItemFactory",
    "_item_factories_for_source",
]
