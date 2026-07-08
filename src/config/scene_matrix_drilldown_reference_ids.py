"""Reference-id helpers for scene matrix drilldown audits."""

from __future__ import annotations

from functools import lru_cache

from src.config.material_schema_registry import list_material_schemas
from src.config.plugin_manual_gate import list_plugin_manual_gates
from src.config.scene_delivery_preset_audit import (
    DELIVERY_ARTIFACT_PSEUDO_IDS,
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_delivery_preset_execution_audit import (
    build_scene_delivery_preset_execution_audit_report,
)
from src.config.scene_external_handoff_contract_audit import (
    build_scene_external_handoff_contract_audit_report,
)
from src.config.scene_fixed_layout_profile_audit import (
    build_scene_fixed_layout_profile_audit_report,
)
from src.config.scene_input_source_audit import build_scene_input_source_audit_report
from src.config.scene_material_repair_flow_audit import (
    build_scene_material_repair_flow_audit_report,
)
from src.config.scene_material_schema_audit import (
    build_scene_material_schema_audit_report,
)
from src.config.scene_object_preflight_action_audit import (
    build_scene_object_preflight_action_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (
    PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS,
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_report_artifact_drilldown_audit import (
    build_scene_report_artifact_drilldown_audit_report,
)
from src.config.scene_release_governance_registry import (
    build_scene_release_governance_report,
)
from src.config.scene_word_risk_closure_audit import (
    build_scene_word_risk_closure_audit_report,
)


@lru_cache(maxsize=None)
def _release_governance_report(report_id: str) -> object:
    return build_scene_release_governance_report(report_id)


def _delivery_reference_ids() -> set[str]:
    delivery_report = build_scene_delivery_preset_audit_report()
    execution_report = build_scene_delivery_preset_execution_audit_report()
    ids: set[str] = set(DELIVERY_ARTIFACT_PSEUDO_IDS)
    for row in delivery_report.family_rows:
        ids.update(row.planned_delivery_preset_ids)
        ids.update(row.actual_delivery_preset_ids)
        ids.update(row.matched_delivery_preset_ids)
        ids.update(row.artifact_pseudo_ids)
        if row.default_delivery_preset_id:
            ids.add(row.default_delivery_preset_id)
    for row in delivery_report.pack_rows:
        ids.update(row.planned_delivery_preset_ids)
        ids.update(row.actual_delivery_preset_ids)
        ids.update(row.executable_delivery_preset_ids)
        ids.update(row.default_delivery_preset_ids)
    for row in execution_report.rows:
        ids.update(row.required_output_signal_ids)
    return ids


def _material_reference_ids() -> set[str]:
    schema_report = build_scene_material_schema_audit_report()
    repair_report = build_scene_material_repair_flow_audit_report()
    ids: set[str] = {schema.schema_id for schema in list_material_schemas()}
    for row in schema_report.family_rows:
        ids.update(row.material_schema_ids)
        ids.update(row.registered_schema_ids)
        ids.update(row.missing_schema_ids)
    for row in schema_report.pack_rows:
        ids.update(row.material_schema_ids)
        ids.update(row.family_schema_ids)
        ids.update(row.executable_schema_ids)
        ids.update(row.registered_schema_ids)
        ids.update(row.missing_schema_ids)
    for row in schema_report.schema_rows:
        ids.add(row.schema_id)
    for row in repair_report.rows:
        ids.update(row.material_signal_ids)
    return ids


def _input_render_reference_ids() -> tuple[set[str], set[str]]:
    report = build_scene_input_source_audit_report()
    input_source_ids: set[str] = set()
    render_source_ids: set[str] = set()
    for row in report.family_rows:
        input_source_ids.update(row.planned_input_formats)
        input_source_ids.update(row.actual_accepted_formats)
        input_source_ids.update(row.matched_input_formats)
        input_source_ids.update(row.missing_input_formats)
        input_source_ids.update(row.structured_formats)
        input_source_ids.update(row.high_risk_imports)
        render_source_ids.update(row.render_source_ids)
        render_source_ids.update(row.target_template_ids)
    for row in report.pack_rows:
        input_source_ids.update(row.input_formats)
        input_source_ids.update(row.structured_formats)
        input_source_ids.update(row.boundary_input_source_ids)
        render_source_ids.update(row.render_source_ids)
        render_source_ids.update(row.target_template_ids)
    for row in report.format_rows:
        input_source_ids.add(row.source_id)
    return input_source_ids, render_source_ids


def _object_preflight_reference_ids() -> set[str]:
    report = build_scene_object_preflight_action_audit_report()
    ids: set[str] = set()
    for row in report.target_rows:
        ids.add(row.target_id)
    for row in report.family_rows:
        ids.update(row.recommended_scan_targets)
        ids.update(row.actual_scan_targets)
        ids.update(row.missing_recommended_targets)
        ids.update(row.block_on)
        ids.update(row.skip_module_targets)
    return ids


def _word_risk_surface_reference_ids() -> set[str]:
    word_report = build_scene_word_risk_closure_audit_report()
    object_report = build_scene_object_preflight_action_audit_report()
    fixed_layout_report = build_scene_fixed_layout_profile_audit_report()
    ids = {row.surface_id for row in word_report.rows}
    for row in object_report.target_rows:
        ids.update(row.word_risk_surface_ids)
    for row in fixed_layout_report.rows:
        ids.update(row.fixed_layout_surface_ids)
    return ids


def _plugin_gate_reference_ids() -> set[str]:
    return {gate.gate_id for gate in list_plugin_manual_gates()}


def _target_plugin_reference_ids() -> set[str]:
    report = build_scene_external_handoff_contract_audit_report()
    return {row.target_plugin_id for row in report.rows if row.target_plugin_id}


def _risk_domain_reference_ids() -> set[str]:
    ids: set[str] = set()
    for gate in list_plugin_manual_gates():
        ids.update(gate.risk_domain_ids)
    return ids


def _maturity_gap_reference_ids() -> set[str]:
    product_report = build_scene_product_maturity_upgrade_audit_report()
    guarded_report = _release_governance_report(
        "scene_boundary_guarded_completion_audit"
    )
    dossier_report = _release_governance_report(
        "scene_boundary_subject_release_dossier_audit"
    )
    external_report = build_scene_external_handoff_contract_audit_report()
    envelope_report = _release_governance_report(
        "scene_boundary_maturity_release_envelope_audit"
    )
    exit_report = _release_governance_report(
        "scene_retained_gap_exit_criteria_audit"
    )
    ids: set[str] = set(PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS)
    for row in product_report.rows:
        ids.update(row.gap_domain_ids)
    for row in guarded_report.rows:
        ids.update(row.remaining_gap_ids)
    for row in dossier_report.rows:
        ids.update(row.retained_gap_ids)
    for row in external_report.rows:
        ids.add(row.gap_id)
    for row in envelope_report.rows:
        ids.add(row.gap_id)
    for row in exit_report.rows:
        ids.add(row.gap_id)
    return ids


def _external_handoff_contract_reference_ids() -> set[str]:
    return {
        row.contract_id
        for row in build_scene_external_handoff_contract_audit_report().rows
    }


@lru_cache(maxsize=1)
def _projection_test_reference_ids() -> frozenset[str]:
    ids: set[str] = set()
    for row in build_scene_material_repair_flow_audit_report().rows:
        ids.update(row.test_ids)
    for row in build_scene_fixed_layout_profile_audit_report().rows:
        ids.update(row.test_ids)
    for row in build_scene_report_artifact_drilldown_audit_report().rows:
        ids.update(row.test_ids)
    for row in build_scene_delivery_preset_execution_audit_report().rows:
        ids.update(row.test_ids)
    return frozenset(ids)


__all__ = [
    "_delivery_reference_ids",
    "_external_handoff_contract_reference_ids",
    "_input_render_reference_ids",
    "_material_reference_ids",
    "_maturity_gap_reference_ids",
    "_object_preflight_reference_ids",
    "_plugin_gate_reference_ids",
    "_projection_test_reference_ids",
    "_risk_domain_reference_ids",
    "_target_plugin_reference_ids",
    "_word_risk_surface_reference_ids",
]
