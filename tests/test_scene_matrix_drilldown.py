import json
import subprocess
import sys
from dataclasses import replace
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.material_schema_registry import list_material_schemas  # noqa: E402
from src.config.plugin_manual_gate import list_plugin_manual_gates  # noqa: E402
from src.config.scene_coverage_manifest import list_scene_coverage_packs  # noqa: E402
from src.config.scene_ambiguity_clarification_ui_audit import (  # noqa: E402
    build_scene_ambiguity_clarification_ui_audit_report,
)
from src.config.scene_boundary_guarded_completion_audit import (  # noqa: E402
    build_scene_boundary_guarded_completion_audit_report,
)
from src.config.scene_boundary_maturity_release_envelope_audit import (  # noqa: E402
    build_scene_boundary_maturity_release_envelope_audit_report,
)
from src.config.scene_boundary_readiness_reconciliation_audit import (  # noqa: E402
    build_scene_boundary_readiness_reconciliation_audit_report,
)
from src.config.scene_boundary_subject_release_continuity_audit import (  # noqa: E402
    build_scene_boundary_subject_release_continuity_audit_report,
)
from src.config.scene_boundary_subject_release_dossier_audit import (  # noqa: E402
    build_scene_boundary_subject_release_dossier_audit_report,
)
from src.config.scene_control_runtime_consistency_audit import (  # noqa: E402
    build_scene_control_runtime_consistency_audit_report,
)
from src.config.scene_non_subject_release_trace_attribution_audit import (  # noqa: E402
    build_scene_non_subject_release_trace_attribution_audit_report,
)
from src.config.scene_release_acceptance_certificate_audit import (  # noqa: E402
    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID,
    build_scene_release_acceptance_certificate_audit_report,
)
from src.config.scene_release_closure_ledger_audit import (  # noqa: E402
    build_scene_release_closure_ledger_audit_report,
)
from src.config.scene_release_projection_surface_parity_audit import (  # noqa: E402
    build_scene_release_projection_surface_parity_audit_report,
)
from src.config.scene_release_residual_explanation_audit import (  # noqa: E402
    build_scene_release_residual_explanation_audit_report,
)
from src.config.scene_release_residual_ratio_ledger_audit import (  # noqa: E402
    build_scene_release_residual_ratio_ledger_audit_report,
)
from src.config.scene_release_trace_partition_guard_audit import (  # noqa: E402
    build_scene_release_trace_partition_guard_audit_report,
)
from src.config.scene_residual_warning_governance_audit import (  # noqa: E402
    build_scene_residual_warning_governance_audit_report,
)
from src.config.scene_terminal_release_exception_audit import (  # noqa: E402
    build_scene_terminal_release_exception_audit_report,
)
from src.config.scene_delivery_preset_audit import (  # noqa: E402
    DELIVERY_ARTIFACT_PSEUDO_IDS,
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_delivery_preset_execution_audit import (  # noqa: E402
    build_scene_delivery_preset_execution_audit_report,
)
from src.config.scene_formula_output_watermark_audit import (  # noqa: E402
    build_scene_formula_output_watermark_audit_report,
)
from src.config.scene_family_registry import list_planned_scene_families  # noqa: E402
from src.config.scene_fixed_layout_profile_audit import (  # noqa: E402
    build_scene_fixed_layout_profile_audit_report,
)
from src.config.scene_report_artifact_drilldown_audit import (  # noqa: E402
    build_scene_report_artifact_drilldown_audit_report,
)
from src.config.scene_external_handoff_contract_audit import (  # noqa: E402
    build_scene_external_handoff_contract_audit_report,
)
from src.config.scene_input_source_audit import (  # noqa: E402
    build_scene_input_source_audit_report,
)
from src.config.scene_request_cell_fixture_registry import (  # noqa: E402
    list_scene_request_cell_fixtures,
)
from src.config.scene_sample_fixture_registry import list_scene_sample_fixtures  # noqa: E402
from src.config.scene_material_schema_audit import (  # noqa: E402
    build_scene_material_schema_audit_report,
)
from src.config.scene_material_repair_flow_audit import (  # noqa: E402
    build_scene_material_repair_flow_audit_report,
)
from src.config.scene_object_preflight_action_audit import (  # noqa: E402
    build_scene_object_preflight_action_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (  # noqa: E402
    PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS,
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_retained_gap_exit_criteria_audit import (  # noqa: E402
    build_scene_retained_gap_exit_criteria_audit_report,
)
from src.config.scene_word_risk_closure_audit import (  # noqa: E402
    build_scene_word_risk_closure_audit_report,
)
from src.config.scene_matrix_drilldown import (  # noqa: E402
    REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS,
    SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP,
    SceneMatrixDrilldownItem,
    SceneMatrixDrilldownReport,
    audit_scene_matrix_drilldown_report,
    build_scene_matrix_drilldown_report,
)
from src.config.scene_matrix_dashboard import (  # noqa: E402
    SCENE_MATRIX_DASHBOARD_SOURCE_IDS,
)
from src.ui.panels.scene_summary_projection import (  # noqa: E402
    build_scene_matrix_drilldown_summary_items,
)
from src.shared.engine.count_engine import list_count_profiles  # noqa: E402


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
    guarded_report = build_scene_boundary_guarded_completion_audit_report()
    dossier_report = build_scene_boundary_subject_release_dossier_audit_report()
    external_report = build_scene_external_handoff_contract_audit_report()
    envelope_report = build_scene_boundary_maturity_release_envelope_audit_report()
    exit_report = build_scene_retained_gap_exit_criteria_audit_report()
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


def _projection_source_reference_ids(
    report: SceneMatrixDrilldownReport,
) -> set[str]:
    ids: set[str] = set(SCENE_MATRIX_DASHBOARD_SOURCE_IDS)
    ids.add(SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID)
    ids.update(evidence.source_id for evidence in report.source_evidence)
    ids.update(item.source_id for item in report.items)
    return ids


@lru_cache(maxsize=1)
def _projection_source_reference_map() -> dict[tuple[str, str, str], frozenset[str]]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        source_ids: tuple[str, ...],
    ) -> None:
        normalized = {source_id for source_id in source_ids if source_id}
        if normalized:
            references[(drilldown_id, row_id, field_name)] = normalized

    for row in build_scene_terminal_release_exception_audit_report().rows:
        add(
            "terminal_release_exception",
            row.exception_id,
            "capability_ids",
            row.source_ids,
        )
    for row in build_scene_non_subject_release_trace_attribution_audit_report().rows:
        add(
            "non_subject_release_trace_attribution",
            row.trace_id,
            "capability_ids",
            (row.surface_source_id,),
        )
    for row in build_scene_release_projection_surface_parity_audit_report().rows:
        add(
            "release_projection_surface_parity",
            row.projection_id,
            "capability_ids",
            (row.audit_source_id,),
        )
    for row in build_scene_release_closure_ledger_audit_report().rows:
        add(
            "release_closure_ledger",
            row.stage_id,
            "capability_ids",
            (row.source_id,),
        )
    acceptance_report = build_scene_release_acceptance_certificate_audit_report()
    for row in acceptance_report.rows:
        add(
            "release_acceptance_certificate",
            row.certificate_id,
            "capability_ids",
            (row.source_id,),
        )
    for row in acceptance_report.requirement_dimension_rows:
        add(
            "release_acceptance_certificate",
            f"requirement:{row.dimension_id}",
            "capability_ids",
            row.source_ids,
        )
    return {
        key: frozenset(source_ids)
        for key, source_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_surface_reference_map() -> dict[tuple[str, str, str], frozenset[str]]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        surface_ids: tuple[str, ...],
    ) -> None:
        normalized = {surface_id for surface_id in surface_ids if surface_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_ambiguity_clarification_ui_audit_report().rows:
        add(
            "ambiguity_clarification",
            row.clarification_id,
            "capability_ids",
            row.ui_surface_ids,
        )
    for row in build_scene_external_handoff_contract_audit_report().rows:
        add(
            "external_handoff_contract",
            row.contract_id,
            "capability_ids",
            row.ui_surface_ids,
        )
    for row in build_scene_material_repair_flow_audit_report().rows:
        add(
            "material_repair_flow",
            row.flow_id,
            "action_behavior_ids",
            row.runtime_surface_ids,
        )
        add(
            "material_repair_flow",
            row.flow_id,
            "capability_ids",
            row.ui_surface_ids,
        )
    for row in build_scene_fixed_layout_profile_audit_report().rows:
        add(
            "fixed_layout_profile",
            row.profile_channel_id,
            "action_behavior_ids",
            row.runtime_surface_ids,
        )
        add(
            "fixed_layout_profile",
            row.profile_channel_id,
            "capability_ids",
            row.ui_surface_ids,
        )
        add(
            "fixed_layout_profile",
            row.profile_channel_id,
            "capability_ids",
            row.report_surface_ids,
        )
    for row in build_scene_report_artifact_drilldown_audit_report().rows:
        add(
            "report_artifact_drilldown",
            row.drilldown_channel_id,
            "action_behavior_ids",
            row.runtime_surface_ids,
        )
        add(
            "report_artifact_drilldown",
            row.drilldown_channel_id,
            "capability_ids",
            row.ui_surface_ids,
        )
        add(
            "report_artifact_drilldown",
            row.drilldown_channel_id,
            "capability_ids",
            row.report_surface_ids,
        )
    for row in build_scene_delivery_preset_execution_audit_report().rows:
        add(
            "delivery_execution",
            row.execution_id,
            "action_behavior_ids",
            row.runtime_surface_ids,
        )
        add(
            "delivery_execution",
            row.execution_id,
            "capability_ids",
            row.ui_surface_ids,
        )
        add(
            "delivery_execution",
            row.execution_id,
            "capability_ids",
            row.report_surface_ids,
        )

    return {
        key: frozenset(surface_ids)
        for key, surface_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_path_reference_map() -> dict[tuple[str, str, str], frozenset[str]]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        path_ids: tuple[str, ...],
    ) -> None:
        normalized = {path_id for path_id in path_ids if path_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_release_projection_surface_parity_audit_report().rows:
        add(
            "release_projection_surface_parity",
            row.projection_id,
            "capability_ids",
            (
                row.export_script_path,
                row.test_path,
                row.closure_doc_path,
                *row.supplemental_closure_doc_paths,
            ),
        )
    for row in build_scene_release_closure_ledger_audit_report().rows:
        add(
            "release_closure_ledger",
            row.stage_id,
            "capability_ids",
            (
                row.export_script_path,
                row.test_path,
                row.closure_doc_path,
                *row.supplemental_closure_doc_paths,
            ),
        )

    return {
        key: frozenset(path_ids)
        for key, path_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_evidence_reference_map() -> dict[tuple[str, str, str], frozenset[str]]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        evidence_ids: tuple[str, ...],
    ) -> None:
        normalized = {evidence_id for evidence_id in evidence_ids if evidence_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_boundary_guarded_completion_audit_report().rows:
        add(
            "boundary_guarded_completion",
            f"{row.subject_type}:{row.subject_id}",
            "action_behavior_ids",
            row.evidence_ids,
        )
    for row in build_scene_residual_warning_governance_audit_report().rows:
        add(
            "residual_warning_governance",
            row.row_id,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_boundary_readiness_reconciliation_audit_report().rows:
        add(
            "boundary_readiness_reconciliation",
            row.row_id,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_terminal_release_exception_audit_report().rows:
        add(
            "terminal_release_exception",
            row.exception_id,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_boundary_subject_release_dossier_audit_report().rows:
        add(
            "boundary_subject_release_dossier",
            row.subject_key,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_non_subject_release_trace_attribution_audit_report().rows:
        add(
            "non_subject_release_trace_attribution",
            row.trace_id,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_release_trace_partition_guard_audit_report().rows:
        add(
            "release_trace_partition_guard",
            row.partition_id,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_release_projection_surface_parity_audit_report().rows:
        add(
            "release_projection_surface_parity",
            row.projection_id,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_boundary_subject_release_continuity_audit_report().rows:
        add(
            "boundary_subject_release_continuity",
            row.subject_key,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_release_closure_ledger_audit_report().rows:
        add(
            "release_closure_ledger",
            row.stage_id,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_boundary_maturity_release_envelope_audit_report().rows:
        add(
            "boundary_maturity_release_envelope",
            row.envelope_id,
            "capability_ids",
            row.evidence_ids,
        )
    for row in build_scene_release_residual_ratio_ledger_audit_report().rows:
        add(
            "release_residual_ratio_ledger",
            row.ratio_id,
            "capability_ids",
            row.evidence_ids,
        )
    acceptance_report = build_scene_release_acceptance_certificate_audit_report()
    for row in acceptance_report.rows:
        add(
            "release_acceptance_certificate",
            row.certificate_id,
            "capability_ids",
            row.evidence_ids,
        )
    for row in acceptance_report.requirement_dimension_rows:
        add(
            "release_acceptance_certificate",
            f"requirement:{row.dimension_id}",
            "capability_ids",
            row.evidence_ids,
        )

    return {
        key: frozenset(evidence_ids)
        for key, evidence_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_release_marker_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        marker_ids: tuple[str, ...],
    ) -> None:
        normalized = {marker_id for marker_id in marker_ids if marker_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_release_projection_surface_parity_audit_report().rows:
        add(
            "release_projection_surface_parity",
            row.projection_id,
            "action_behavior_ids",
            (
                row.release_gate_check_id,
                row.dashboard_card_id,
                row.drilldown_id,
            ),
        )
        add(
            "release_projection_surface_parity",
            row.projection_id,
            "capability_ids",
            (row.summary_marker,),
        )
    for row in build_scene_release_closure_ledger_audit_report().rows:
        add(
            "release_closure_ledger",
            row.stage_id,
            "action_behavior_ids",
            (
                row.release_gate_check_id,
                row.dashboard_card_id,
                row.drilldown_id,
                row.summary_marker,
            ),
        )

    return {
        key: frozenset(marker_ids)
        for key, marker_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_release_link_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        link_ids: tuple[str, ...],
    ) -> None:
        normalized = {link_id for link_id in link_ids if link_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_terminal_release_exception_audit_report().rows:
        add(
            "terminal_release_exception",
            row.exception_id,
            "capability_ids",
            row.source_trace_ids,
        )
    for row in build_scene_boundary_subject_release_dossier_audit_report().rows:
        add(
            "boundary_subject_release_dossier",
            row.subject_key,
            "action_behavior_ids",
            row.terminal_exception_ids,
        )
        add(
            "boundary_subject_release_dossier",
            row.subject_key,
            "capability_ids",
            (
                *row.readiness_reconciliation_row_ids,
                *row.release_exception_trace_ids,
            ),
        )
    for row in build_scene_non_subject_release_trace_attribution_audit_report().rows:
        add(
            "non_subject_release_trace_attribution",
            row.trace_id,
            "action_behavior_ids",
            (row.terminal_exception_id,),
        )
        add(
            "non_subject_release_trace_attribution",
            row.trace_id,
            "capability_ids",
            (row.source_trace_id,),
        )
    for row in build_scene_release_trace_partition_guard_audit_report().rows:
        add(
            "release_trace_partition_guard",
            row.partition_id,
            "capability_ids",
            row.trace_ids,
        )
    for row in build_scene_boundary_subject_release_continuity_audit_report().rows:
        add(
            "boundary_subject_release_continuity",
            row.subject_key,
            "capability_ids",
            (
                *row.readiness_row_ids,
                *row.terminal_trace_ids,
                *row.dossier_trace_ids,
            ),
        )
    for row in build_scene_release_closure_ledger_audit_report().rows:
        add(
            "release_closure_ledger",
            row.stage_id,
            "capability_ids",
            row.upstream_stage_ids,
        )
    for row in build_scene_boundary_maturity_release_envelope_audit_report().rows:
        add(
            "boundary_maturity_release_envelope",
            row.envelope_id,
            "capability_ids",
            (
                *row.readiness_row_ids,
                *row.terminal_trace_ids,
                *row.dossier_trace_ids,
            ),
        )
    for row in build_scene_retained_gap_exit_criteria_audit_report().rows:
        add(
            "retained_gap_exit_criteria",
            row.criteria_id,
            "action_behavior_ids",
            (row.release_envelope_id,),
        )
    for row in build_scene_release_residual_ratio_ledger_audit_report().rows:
        add(
            "release_residual_ratio_ledger",
            row.ratio_id,
            "action_behavior_ids",
            row.terminal_exception_ids,
        )
        add(
            "release_residual_ratio_ledger",
            row.ratio_id,
            "capability_ids",
            (
                *row.readiness_reconciliation_row_ids,
                *row.release_envelope_ids,
                *row.retained_gap_exit_criteria_ids,
                *row.retained_gap_receipt_alignment_ids,
            ),
        )

    return {
        key: frozenset(link_ids)
        for key, link_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_retained_gap_exit_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        reference_ids: tuple[str, ...],
    ) -> None:
        normalized = {reference_id for reference_id in reference_ids if reference_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_retained_gap_exit_criteria_audit_report().rows:
        add(
            "retained_gap_exit_criteria",
            row.criteria_id,
            "action_behavior_ids",
            (
                row.external_handoff_contract_id,
                *row.release_condition_ids,
            ),
        )
        add(
            "retained_gap_exit_criteria",
            row.criteria_id,
            "capability_ids",
            (
                row.gap_id,
                *row.exit_signal_ids,
                *row.prohibited_core_claim_ids,
            ),
        )

    return {
        key: frozenset(reference_ids)
        for key, reference_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_control_runtime_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        reference_ids: tuple[str, ...],
    ) -> None:
        normalized = {reference_id for reference_id in reference_ids if reference_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_control_runtime_consistency_audit_report().rows:
        add(
            "control_runtime_consistency",
            row.runtime_id,
            "action_behavior_ids",
            row.required_semantics,
        )
        add(
            "control_runtime_consistency",
            row.runtime_id,
            "capability_ids",
            (
                *row.contract_ids,
                *row.shared_component_ids,
                *row.scene_surface_ids,
                *row.template_surface_ids,
                *row.runtime_consumer_ids,
            ),
        )

    return {
        key: frozenset(reference_ids)
        for key, reference_ids in references.items()
    }


def _release_residual_metric_action_ids(row: object) -> tuple[str, ...]:
    receipt_count = len(
        getattr(row, "retained_gap_receipt_alignment_ids", ()) or ()
    )
    exit_criteria_count = len(
        getattr(row, "retained_gap_exit_criteria_ids", ()) or ()
    )
    action_ids = [f"receipt_alignments={receipt_count}/{exit_criteria_count}"]
    ratio_id = str(getattr(row, "ratio_id", "") or "")
    if ratio_id in ("count_profiles", "delivery_families"):
        action_ids.append(f"count_delivery_receipts={receipt_count}/{exit_criteria_count}")
    elif ratio_id == "maturity_l5_blocked":
        action_ids.append(f"maturity_l5_receipts={receipt_count}/{exit_criteria_count}")
    return tuple(action_ids)


@lru_cache(maxsize=1)
def _projection_release_metric_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        metric_ids: tuple[str, ...],
    ) -> None:
        normalized = {metric_id for metric_id in metric_ids if metric_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_release_residual_ratio_ledger_audit_report().rows:
        add(
            "release_residual_ratio_ledger",
            row.ratio_id,
            "action_behavior_ids",
            _release_residual_metric_action_ids(row),
        )
    for row in build_scene_release_residual_explanation_audit_report().rows:
        add(
            "release_residual_explanation",
            row.residual_id,
            "action_behavior_ids",
            (row.summary_marker,),
        )

    return {
        key: frozenset(metric_ids)
        for key, metric_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_external_handoff_contract_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        contract_ids: tuple[str, ...],
    ) -> None:
        normalized = {contract_id for contract_id in contract_ids if contract_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_boundary_guarded_completion_audit_report().rows:
        add(
            "boundary_guarded_completion",
            f"{row.subject_type}:{row.subject_id}",
            "capability_ids",
            row.external_handoff_contract_ids,
        )
    for row in build_scene_boundary_subject_release_dossier_audit_report().rows:
        add(
            "boundary_subject_release_dossier",
            row.subject_key,
            "capability_ids",
            row.external_handoff_contract_ids,
        )
    for row in build_scene_boundary_maturity_release_envelope_audit_report().rows:
        add(
            "boundary_maturity_release_envelope",
            row.envelope_id,
            "action_behavior_ids",
            (row.external_handoff_contract_id,),
        )
    for row in build_scene_retained_gap_exit_criteria_audit_report().rows:
        add(
            "retained_gap_exit_criteria",
            row.criteria_id,
            "action_behavior_ids",
            (row.external_handoff_contract_id,),
        )

    return {
        key: frozenset(contract_ids)
        for key, contract_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_report_delivery_marker_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        marker_ids: tuple[str, ...],
    ) -> None:
        normalized = {marker_id for marker_id in marker_ids if marker_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_report_artifact_drilldown_audit_report().rows:
        add(
            "report_artifact_drilldown",
            row.drilldown_channel_id,
            "capability_ids",
            row.artifact_kind_ids,
        )
    for row in build_scene_delivery_preset_execution_audit_report().rows:
        add(
            "delivery_execution",
            row.execution_id,
            "action_behavior_ids",
            row.payload_keys,
        )
        add(
            "delivery_execution",
            row.execution_id,
            "capability_ids",
            row.required_output_signal_ids,
        )

    return {
        key: frozenset(marker_ids)
        for key, marker_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_requirement_dimension_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        dimension_ids: tuple[str, ...],
    ) -> None:
        normalized = {dimension_id for dimension_id in dimension_ids if dimension_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    acceptance_report = build_scene_release_acceptance_certificate_audit_report()
    for row in acceptance_report.requirement_dimension_rows:
        add(
            "release_acceptance_certificate",
            f"requirement:{row.dimension_id}",
            "capability_ids",
            (row.dimension_id,),
        )

    return {
        key: frozenset(dimension_ids)
        for key, dimension_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_target_plugin_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        target_plugin_ids: tuple[str, ...],
    ) -> None:
        normalized = {plugin_id for plugin_id in target_plugin_ids if plugin_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    for row in build_scene_external_handoff_contract_audit_report().rows:
        add(
            "external_handoff_contract",
            row.contract_id,
            "capability_ids",
            (row.target_plugin_id,),
        )
    for row in build_scene_boundary_guarded_completion_audit_report().rows:
        add(
            "boundary_guarded_completion",
            f"{row.subject_type}:{row.subject_id}",
            "capability_ids",
            row.target_plugin_ids,
        )

    return {
        key: frozenset(target_plugin_ids)
        for key, target_plugin_ids in references.items()
    }


@lru_cache(maxsize=1)
def _projection_formula_output_watermark_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: dict[tuple[str, str, str], set[str]] = {}

    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        reference_ids: tuple[str, ...],
    ) -> None:
        normalized = {reference_id for reference_id in reference_ids if reference_id}
        if normalized:
            references.setdefault((drilldown_id, row_id, field_name), set()).update(
                normalized
            )

    report = build_scene_formula_output_watermark_audit_report()
    for row in report.capability_rows:
        add(
            "formula_output_watermark",
            f"capability:{row.capability_id}",
            "action_behavior_ids",
            (row.expected_owner_layer,),
        )
        add(
            "formula_output_watermark",
            f"capability:{row.capability_id}",
            "capability_ids",
            (
                row.capability_id,
                *row.parameter_paths,
                *row.template_baseline_paths,
                *row.control_contract_ids,
                *row.execution_consumers,
            ),
        )
    for row in report.family_rows:
        add(
            "formula_output_watermark",
            row.family_id,
            "capability_ids",
            row.capability_ids,
        )

    return {
        key: frozenset(reference_ids)
        for key, reference_ids in references.items()
    }


def test_scene_matrix_drilldown_indexes_required_frontend_sources():
    report = build_scene_matrix_drilldown_report(project_root=ROOT)
    payload = report.to_payload()
    items = {item.drilldown_id: item for item in report.items}
    coverage_pack_ids = {pack.pack_id for pack in list_scene_coverage_packs()}
    planned_family_ids = {
        family.family_id for family in list_planned_scene_families()
    }
    request_cell_ids = {
        cell.sample_id for cell in list_scene_request_cell_fixtures()
    }
    sample_fixture_ids = {
        fixture.fixture_id for fixture in list_scene_sample_fixtures()
    }
    count_profile_ids = {
        profile.profile_id for profile in list_count_profiles()
    }
    delivery_reference_ids = _delivery_reference_ids()
    material_reference_ids = _material_reference_ids()
    input_source_reference_ids, render_source_reference_ids = (
        _input_render_reference_ids()
    )
    object_preflight_reference_ids = _object_preflight_reference_ids()
    word_risk_surface_reference_ids = _word_risk_surface_reference_ids()
    plugin_gate_reference_ids = _plugin_gate_reference_ids()
    target_plugin_reference_ids = _target_plugin_reference_ids()
    risk_domain_reference_ids = _risk_domain_reference_ids()
    maturity_gap_reference_ids = _maturity_gap_reference_ids()
    external_handoff_contract_reference_ids = (
        _external_handoff_contract_reference_ids()
    )
    projection_test_reference_ids = _projection_test_reference_ids()
    projection_source_reference_ids = _projection_source_reference_ids(report)
    projection_source_reference_map = _projection_source_reference_map()
    projection_surface_reference_map = _projection_surface_reference_map()
    projection_path_reference_map = _projection_path_reference_map()
    projection_evidence_reference_map = _projection_evidence_reference_map()
    projection_release_marker_reference_map = (
        _projection_release_marker_reference_map()
    )
    projection_release_link_reference_map = _projection_release_link_reference_map()
    projection_retained_gap_exit_reference_map = (
        _projection_retained_gap_exit_reference_map()
    )
    projection_control_runtime_reference_map = (
        _projection_control_runtime_reference_map()
    )
    projection_release_metric_reference_map = (
        _projection_release_metric_reference_map()
    )
    projection_external_handoff_contract_reference_map = (
        _projection_external_handoff_contract_reference_map()
    )
    projection_report_delivery_marker_reference_map = (
        _projection_report_delivery_marker_reference_map()
    )
    projection_requirement_dimension_reference_map = (
        _projection_requirement_dimension_reference_map()
    )
    projection_target_plugin_reference_map = (
        _projection_target_plugin_reference_map()
    )
    projection_formula_output_watermark_reference_map = (
        _projection_formula_output_watermark_reference_map()
    )

    assert report.status == "passed"
    assert audit_scene_matrix_drilldown_report(report) == ()
    assert tuple(payload["required_drilldown_ids"]) == (
        REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS
    )
    assert report.item_count == 37
    assert report.ready_count == 37
    assert report.row_count == 556
    assert report.visible_row_count == 556
    assert report.source_evidence_count == 107
    assert report.ready_source_evidence_count == 107
    assert report.missing_source_evidence_count == 0
    drilldown_ids = [item.drilldown_id for item in report.items]
    assert len(drilldown_ids) == len(set(drilldown_ids))
    item_source_ids = [item.source_id for item in report.items]
    for item in report.items:
        row_ids = [row.row_id for row in item.rows]
        assert len(row_ids) == len(set(row_ids))
        row_source_ids = [row.source_id for row in item.rows]
        assert set(row_source_ids) == {item.source_id}
        projection_profile = SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP.get(
            item.drilldown_id
        )
        if any(row.action_behavior_ids for row in item.rows):
            assert projection_profile is not None
            assert projection_profile.source_id == item.source_id
            assert projection_profile.action_source_fields
            assert projection_profile.action_token_kinds
        if any(row.capability_ids for row in item.rows):
            assert projection_profile is not None
            assert projection_profile.source_id == item.source_id
            assert projection_profile.capability_source_fields
            assert projection_profile.capability_token_kinds
        for row in item.rows:
            assert set(row.pack_ids).issubset(coverage_pack_ids)
            assert set(row.family_ids).issubset(planned_family_ids)
            assert set(row.request_cell_ids).issubset(request_cell_ids)
            assert set(row.fixture_ids).issubset(sample_fixture_ids)
            assert set(row.count_profile_ids).issubset(count_profile_ids)
            assert set(row.delivery_preset_ids).issubset(delivery_reference_ids)
            assert set(row.material_schema_ids).issubset(material_reference_ids)
            assert set(row.input_source_ids).issubset(input_source_reference_ids)
            assert set(row.render_source_ids).issubset(render_source_reference_ids)
            assert set(row.object_preflight_target_ids).issubset(
                object_preflight_reference_ids
            )
            assert set(row.word_risk_surface_ids).issubset(
                word_risk_surface_reference_ids
            )
            assert set(row.plugin_gate_ids).issubset(plugin_gate_reference_ids)
            assert set(row.risk_domain_ids).issubset(risk_domain_reference_ids)
            assert set(row.maturity_gap_domain_ids).issubset(
                maturity_gap_reference_ids
            )
            for projection_id in (
                *row.action_behavior_ids,
                *row.capability_ids,
            ):
                if projection_id.startswith("test_"):
                    assert projection_id in projection_test_reference_ids
            for field_name in ("action_behavior_ids", "capability_ids"):
                expected_source_ids = projection_source_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                )
                assert expected_source_ids.issubset(projection_source_reference_ids)
                assert expected_source_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_surface_ids = projection_surface_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                )
                assert expected_surface_ids.issubset(set(getattr(row, field_name)))
                expected_path_ids = projection_path_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                )
                assert expected_path_ids.issubset(set(getattr(row, field_name)))
                for expected_path_id in expected_path_ids:
                    assert (ROOT / expected_path_id).exists()
                expected_evidence_ids = projection_evidence_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                )
                assert expected_evidence_ids.issubset(set(getattr(row, field_name)))
                expected_release_marker_ids = (
                    projection_release_marker_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                )
                assert expected_release_marker_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_release_link_ids = projection_release_link_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                )
                assert expected_release_link_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_retained_gap_exit_ids = (
                    projection_retained_gap_exit_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                )
                assert expected_retained_gap_exit_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_control_runtime_ids = (
                    projection_control_runtime_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                )
                assert expected_control_runtime_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_release_metric_ids = (
                    projection_release_metric_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                )
                assert expected_release_metric_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_handoff_contract_ids = (
                    projection_external_handoff_contract_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                )
                assert expected_handoff_contract_ids.issubset(
                    external_handoff_contract_reference_ids
                )
                assert expected_handoff_contract_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_report_delivery_marker_ids = (
                    projection_report_delivery_marker_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                )
                assert expected_report_delivery_marker_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_requirement_dimension_ids = (
                    projection_requirement_dimension_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                )
                assert expected_requirement_dimension_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_target_plugin_ids = (
                    projection_target_plugin_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                )
                assert expected_target_plugin_ids.issubset(
                    target_plugin_reference_ids
                )
                assert expected_target_plugin_ids.issubset(
                    set(getattr(row, field_name))
                )
                expected_formula_output_watermark_ids = (
                    projection_formula_output_watermark_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                )
                assert expected_formula_output_watermark_ids.issubset(
                    set(getattr(row, field_name))
                )
    assert len(report.source_evidence) == report.source_evidence_count
    report_source_ids = [item.source_id for item in report.source_evidence]
    assert len(report_source_ids) == len(set(report_source_ids))
    assert set(item_source_ids).issubset(set(report_source_ids))
    report_row_source_ids = [
        row.source_id for item in report.items for row in item.rows
    ]
    assert set(report_row_source_ids).issubset(set(report_source_ids))
    assert payload["counts"]["source_evidence_count"] == 107
    assert payload["counts"]["ready_source_evidence_count"] == 107
    assert payload["counts"]["missing_source_evidence_count"] == 0
    payload_drilldown_ids = [item["drilldown_id"] for item in payload["items"]]
    assert len(payload_drilldown_ids) == len(set(payload_drilldown_ids))
    for item in payload["items"]:
        payload_row_ids = [row["row_id"] for row in item["rows"]]
        assert len(payload_row_ids) == len(set(payload_row_ids))
    assert len(payload["source_evidence"]) == payload["counts"]["source_evidence_count"]
    payload_source_ids = [item["source_id"] for item in payload["source_evidence"]]
    assert len(payload_source_ids) == len(set(payload_source_ids))
    payload_item_source_ids = [item["source_id"] for item in payload["items"]]
    assert set(payload_item_source_ids).issubset(set(payload_source_ids))
    payload_row_source_ids = [
        row["source_id"] for item in payload["items"] for row in item["rows"]
    ]
    assert set(payload_row_source_ids).issubset(set(payload_source_ids))
    for item in payload["items"]:
        assert {row["source_id"] for row in item["rows"]} == {item["source_id"]}
        for row in item["rows"]:
            assert set(row["pack_ids"]).issubset(coverage_pack_ids)
            assert set(row["family_ids"]).issubset(planned_family_ids)
            assert set(row["request_cell_ids"]).issubset(request_cell_ids)
            assert set(row["fixture_ids"]).issubset(sample_fixture_ids)
            assert set(row["count_profile_ids"]).issubset(count_profile_ids)
            assert set(row["delivery_preset_ids"]).issubset(delivery_reference_ids)
            assert set(row["material_schema_ids"]).issubset(material_reference_ids)
            assert set(row["input_source_ids"]).issubset(input_source_reference_ids)
            assert set(row["render_source_ids"]).issubset(render_source_reference_ids)
            assert set(row["object_preflight_target_ids"]).issubset(
                object_preflight_reference_ids
            )
            assert set(row["word_risk_surface_ids"]).issubset(
                word_risk_surface_reference_ids
            )
            assert set(row["plugin_gate_ids"]).issubset(plugin_gate_reference_ids)
            assert set(row["risk_domain_ids"]).issubset(risk_domain_reference_ids)
            assert set(row["maturity_gap_domain_ids"]).issubset(
                maturity_gap_reference_ids
            )
            for projection_id in (
                *row["action_behavior_ids"],
                *row["capability_ids"],
            ):
                if projection_id.startswith("test_"):
                    assert projection_id in projection_test_reference_ids
            for field_name in ("action_behavior_ids", "capability_ids"):
                expected_source_ids = projection_source_reference_map.get(
                    (item["drilldown_id"], row["row_id"], field_name),
                    set(),
                )
                assert expected_source_ids.issubset(projection_source_reference_ids)
                assert expected_source_ids.issubset(set(row[field_name]))
                expected_surface_ids = projection_surface_reference_map.get(
                    (item["drilldown_id"], row["row_id"], field_name),
                    set(),
                )
                assert expected_surface_ids.issubset(set(row[field_name]))
                expected_path_ids = projection_path_reference_map.get(
                    (item["drilldown_id"], row["row_id"], field_name),
                    set(),
                )
                assert expected_path_ids.issubset(set(row[field_name]))
                for expected_path_id in expected_path_ids:
                    assert (ROOT / expected_path_id).exists()
                expected_evidence_ids = projection_evidence_reference_map.get(
                    (item["drilldown_id"], row["row_id"], field_name),
                    set(),
                )
                assert expected_evidence_ids.issubset(set(row[field_name]))
                expected_release_marker_ids = (
                    projection_release_marker_reference_map.get(
                        (item["drilldown_id"], row["row_id"], field_name),
                        set(),
                    )
                )
                assert expected_release_marker_ids.issubset(set(row[field_name]))
                expected_release_link_ids = projection_release_link_reference_map.get(
                    (item["drilldown_id"], row["row_id"], field_name),
                    set(),
                )
                assert expected_release_link_ids.issubset(set(row[field_name]))
                expected_retained_gap_exit_ids = (
                    projection_retained_gap_exit_reference_map.get(
                        (item["drilldown_id"], row["row_id"], field_name),
                        set(),
                    )
                )
                assert expected_retained_gap_exit_ids.issubset(set(row[field_name]))
                expected_control_runtime_ids = (
                    projection_control_runtime_reference_map.get(
                        (item["drilldown_id"], row["row_id"], field_name),
                        set(),
                    )
                )
                assert expected_control_runtime_ids.issubset(set(row[field_name]))
                expected_release_metric_ids = (
                    projection_release_metric_reference_map.get(
                        (item["drilldown_id"], row["row_id"], field_name),
                        set(),
                    )
                )
                assert expected_release_metric_ids.issubset(set(row[field_name]))
                expected_handoff_contract_ids = (
                    projection_external_handoff_contract_reference_map.get(
                        (item["drilldown_id"], row["row_id"], field_name),
                        set(),
                    )
                )
                assert expected_handoff_contract_ids.issubset(
                    external_handoff_contract_reference_ids
                )
                assert expected_handoff_contract_ids.issubset(set(row[field_name]))
    assert (
        sum(1 for item in payload["source_evidence"] if item["status"] == "ready")
        == payload["counts"]["ready_source_evidence_count"]
    )
    assert (
        sum(1 for item in payload["source_evidence"] if item["status"] != "ready")
        == payload["counts"]["missing_source_evidence_count"]
    )
    source_status = {
        evidence.source_id: evidence.status for evidence in report.source_evidence
    }
    assert (
        source_status["scene_matrix_drilldown_acceptance_receipt_projection"]
        == "ready"
    )
    assert source_status["scene_matrix_drilldown_residual_receipt_projection"] == (
        "ready"
    )
    assert source_status["scene_matrix_drilldown_export_receipt_projection"] == (
        "ready"
    )
    assert source_status["scene_matrix_drilldown_export_source_summary_projection"] == (
        "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_export_json_source_summary_projection"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_source_evidence_payload_consistency_tests"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_source_evidence_unique_id_tests"]
        == "ready"
    )
    assert source_status["scene_matrix_drilldown_source_summary_projection"] == (
        "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_source_summary_readiness_projection"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_release_gate_source_summary_projection"]
        == "ready"
    )
    assert source_status["scene_matrix_drilldown_item_row_identity_audit"] == "ready"
    assert (
        source_status["scene_matrix_drilldown_item_source_evidence_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_row_source_evidence_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_row_pack_family_registry_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_row_request_fixture_registry_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_row_count_delivery_registry_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_row_material_reference_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_row_input_object_word_registry_audit"]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_row_plugin_risk_maturity_registry_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_action_capability_projection_profile_audit"
        ]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_projection_test_reference_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_projection_source_reference_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_projection_surface_reference_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_projection_path_reference_audit"]
        == "ready"
    )
    assert (
        source_status["scene_matrix_drilldown_projection_evidence_reference_audit"]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_release_marker_reference_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_release_link_reference_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_retained_gap_exit_reference_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_control_runtime_reference_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_release_metric_reference_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_external_handoff_reference_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_report_delivery_marker_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_requirement_dimension_reference_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_target_plugin_reference_audit"
        ]
        == "ready"
    )
    assert (
        source_status[
            "scene_matrix_drilldown_projection_formula_output_watermark_reference_audit"
        ]
        == "ready"
    )
    assert source_status["n2_402_acceptance_drilldown_trace_plan"] == "ready"
    assert source_status["n2_407_residual_receipt_drilldown_plan"] == "ready"
    assert source_status["n2_408_residual_receipt_export_plan"] == "ready"
    assert source_status["n2_409_residual_receipt_source_summary_plan"] == "ready"
    assert (
        source_status["n2_410_drilldown_source_evidence_release_summary_plan"]
        == "ready"
    )
    assert (
        source_status["n2_411_drilldown_source_summary_ready_total_plan"]
        == "ready"
    )
    assert (
        source_status["n2_412_drilldown_export_source_summary_plan"]
        == "ready"
    )
    assert (
        source_status["n2_413_drilldown_json_export_source_summary_plan"]
        == "ready"
    )
    assert (
        source_status["n2_414_drilldown_source_evidence_payload_consistency_plan"]
        == "ready"
    )
    assert (
        source_status["n2_415_drilldown_source_evidence_unique_id_plan"]
        == "ready"
    )
    assert (
        source_status["n2_416_drilldown_item_row_unique_id_plan"]
        == "ready"
    )
    assert (
        source_status["n2_417_drilldown_item_source_evidence_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_418_drilldown_row_source_evidence_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_419_drilldown_row_pack_family_registry_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_420_drilldown_row_request_fixture_registry_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_421_drilldown_row_count_delivery_registry_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_422_drilldown_row_material_reference_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_423_drilldown_row_input_object_word_registry_trace_plan"]
        == "ready"
    )
    assert (
        source_status[
            "n2_424_drilldown_row_plugin_risk_maturity_registry_trace_plan"
        ]
        == "ready"
    )
    assert (
        source_status[
            "n2_425_drilldown_action_capability_projection_profile_trace_plan"
        ]
        == "ready"
    )
    assert (
        source_status["n2_426_drilldown_projection_test_reference_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_427_drilldown_projection_source_reference_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_428_drilldown_projection_surface_reference_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_429_drilldown_projection_path_reference_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_430_drilldown_projection_evidence_reference_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_431_drilldown_projection_release_marker_trace_plan"]
        == "ready"
    )
    assert (
        source_status["n2_432_drilldown_projection_release_link_trace_plan"]
        == "ready"
    )
    assert (
        source_status[
            "n2_433_drilldown_projection_retained_gap_exit_reference_trace_plan"
        ]
        == "ready"
    )
    assert (
        source_status[
            "n2_434_drilldown_projection_control_runtime_reference_trace_plan"
        ]
        == "ready"
    )
    assert (
        source_status[
            "n2_435_drilldown_projection_release_metric_reference_trace_plan"
        ]
        == "ready"
    )
    assert (
        source_status[
            "n2_436_drilldown_projection_external_handoff_reference_trace_plan"
        ]
        == "ready"
    )
    assert (
        source_status[
            "n2_437_drilldown_projection_report_delivery_marker_trace_plan"
        ]
        == "ready"
    )
    assert (
        source_status[
            "n2_438_drilldown_projection_requirement_dimension_trace_plan"
        ]
        == "ready"
    )
    assert (
        source_status[
            "n2_439_drilldown_projection_target_plugin_trace_plan"
        ]
        == "ready"
    )
    assert (
        source_status[
            "n2_440_drilldown_projection_formula_output_watermark_trace_plan"
        ]
        == "ready"
    )

    assert items["matrix_dashboard"].source_id == "scene_matrix_dashboard"
    assert items["matrix_dashboard"].row_count == 12
    assert items["request_cells"].source_id == "scene_request_cell_registry_browser"
    assert items["request_cells"].row_count == 53
    assert items["ambiguity_clarification"].source_id == (
        "scene_ambiguity_clarification_ui_audit"
    )
    assert items["ambiguity_clarification"].row_count == 6
    assert items["user_journey_fixture"].source_id == (
        "scene_user_journey_fixture_audit"
    )
    assert items["user_journey_fixture"].row_count == 100
    assert items["business_capability_matrix"].source_id == (
        "scene_business_capability_matrix_audit"
    )
    assert items["business_capability_matrix"].row_count == 18
    assert items["control_runtime_consistency"].source_id == (
        "scene_control_runtime_consistency_audit"
    )
    assert items["control_runtime_consistency"].row_count == 12
    assert items["plugin_boundary"].source_id == (
        "scene_plugin_boundary_confirmation_audit"
    )
    assert items["plugin_boundary"].row_count == 4
    assert items["external_handoff_contract"].source_id == (
        "scene_external_handoff_contract_audit"
    )
    assert items["external_handoff_contract"].row_count == 6
    assert items["boundary_guarded_completion"].source_id == (
        "scene_boundary_guarded_completion_audit"
    )
    assert items["boundary_guarded_completion"].row_count == 6
    assert items["residual_warning_governance"].source_id == (
        "scene_residual_warning_governance_audit"
    )
    assert items["residual_warning_governance"].row_count == 10
    assert items["boundary_readiness_reconciliation"].source_id == (
        "scene_boundary_readiness_reconciliation_audit"
    )
    assert items["boundary_readiness_reconciliation"].row_count == 15
    assert items["terminal_release_exception"].source_id == (
        "scene_terminal_release_exception_audit"
    )
    assert items["terminal_release_exception"].row_count == 5
    assert items["boundary_subject_release_dossier"].source_id == (
        "scene_boundary_subject_release_dossier_audit"
    )
    assert items["boundary_subject_release_dossier"].row_count == 6
    assert items["non_subject_release_trace_attribution"].source_id == (
        "scene_non_subject_release_trace_attribution_audit"
    )
    assert items["non_subject_release_trace_attribution"].row_count == 10
    assert items["release_trace_partition_guard"].source_id == (
        "scene_release_trace_partition_guard_audit"
    )
    assert items["release_trace_partition_guard"].row_count == 3
    assert items["release_projection_surface_parity"].source_id == (
        "scene_release_projection_surface_parity_audit"
    )
    assert items["release_projection_surface_parity"].row_count == 13
    assert items["boundary_subject_release_continuity"].source_id == (
        "scene_boundary_subject_release_continuity_audit"
    )
    assert items["boundary_subject_release_continuity"].row_count == 6
    assert items["release_closure_ledger"].source_id == (
        "scene_release_closure_ledger_audit"
    )
    assert items["release_closure_ledger"].row_count == 13
    assert items["boundary_maturity_release_envelope"].source_id == (
        "scene_boundary_maturity_release_envelope_audit"
    )
    assert items["boundary_maturity_release_envelope"].row_count == 6
    assert items["retained_gap_exit_criteria"].source_id == (
        "scene_retained_gap_exit_criteria_audit"
    )
    assert items["retained_gap_exit_criteria"].row_count == 6
    assert items["release_residual_ratio_ledger"].source_id == (
        "scene_release_residual_ratio_ledger_audit"
    )
    assert items["release_residual_ratio_ledger"].row_count == 3
    assert (
        "count_delivery_receipts=4/4"
        in items["release_residual_ratio_ledger"].detail
    )
    assert (
        "maturity_l5_receipts=6/6"
        in items["release_residual_ratio_ledger"].detail
    )
    assert items["release_residual_explanation"].source_id == (
        "scene_release_residual_explanation_audit"
    )
    assert items["release_residual_explanation"].row_count == 14
    assert items["release_acceptance_certificate"].source_id == (
        "scene_release_acceptance_certificate_audit"
    )
    assert items["release_acceptance_certificate"].row_count == 24
    assert items["word_risk"].source_id == "scene_word_risk_closure_audit"
    assert items["word_risk"].row_count == 15
    assert items["import_handoff"].source_id == "scene_import_handoff_audit"
    assert items["import_handoff"].row_count == 1
    assert items["input_source"].source_id == "scene_input_source_audit"
    assert items["input_source"].row_count == 15
    assert items["object_preflight_action"].source_id == (
        "scene_object_preflight_action_audit"
    )
    assert items["object_preflight_action"].row_count == 26
    assert items["family_fixture_depth"].source_id == (
        "scene_family_fixture_depth_audit"
    )
    assert items["family_fixture_depth"].row_count == 15
    assert items["count_profile"].source_id == "scene_count_profile_audit"
    assert items["count_profile"].row_count == 15
    assert items["material_schema"].source_id == "scene_material_schema_audit"
    assert items["material_schema"].row_count == 15
    assert items["material_repair_flow"].source_id == (
        "scene_material_repair_flow_audit"
    )
    assert items["material_repair_flow"].row_count == 11
    assert items["fixed_layout_profile"].source_id == (
        "scene_fixed_layout_profile_audit"
    )
    assert items["fixed_layout_profile"].row_count == 12
    assert items["report_artifact_drilldown"].source_id == (
        "scene_report_artifact_drilldown_audit"
    )
    assert items["report_artifact_drilldown"].row_count == 10
    assert items["delivery_preset"].source_id == "scene_delivery_preset_audit"
    assert items["delivery_preset"].row_count == 15
    assert items["delivery_execution"].source_id == (
        "scene_delivery_preset_execution_audit"
    )
    assert items["delivery_execution"].row_count == 10
    assert items["formula_output_watermark"].source_id == (
        "scene_formula_output_watermark_audit"
    )
    assert items["formula_output_watermark"].row_count == 18
    assert items["maturity_upgrade"].source_id == (
        "scene_product_maturity_upgrade_audit"
    )
    assert items["maturity_upgrade"].row_count == 27


    assert {row.row_id for row in items["import_handoff"].rows} == {
        "pdf_thesis_import_to_chinese_academic"
    }
    assert {row.row_id for row in items["ambiguity_clarification"].rows}.issuperset(
        {"clarify:ambiguous_product_manual", "clarify:ambiguous_batch_notice"}
    )
    assert {row.row_id for row in items["user_journey_fixture"].rows}.issuperset(
        {
            "handoff:import_pdf_thesis",
            "degraded:technical_product_manual",
            "degraded:chinese_thesis_count",
            "manual_boundary:chinese_thesis_count",
            "degraded:english_journal_submission_package",
            "manual_boundary:english_journal_response_letter",
            "degraded:official_notice_formal_archive",
            "manual_boundary:official_notice_formal_archive",
            "manual_boundary:technical_sop_chapter_inventory",
            "degraded:bidding_license_archive",
            "manual_boundary:bidding_original_copy",
            "degraded:application_project_limits",
            "manual_boundary:application_review_budget",
            "degraded:application_customer_product_manual",
            "manual_boundary:application_presales_plan",
            "degraded:professional_finance_quote",
            "degraded:import_ocr_pdf",
        }
    )
    assert {row.row_id for row in items["business_capability_matrix"].rows}.issuperset(
        {
            "exam_teaching",
            "import_ai_assistance_boundary",
            "journal_en",
            "meeting_policy_documents",
            "long_document_publishing",
            "qualification_archive_packages",
        }
    )
    assert any(
        row.row_id == "exam_teaching"
        and "exam_generator_tech_stack_record" in row.capability_ids
        and "success" in row.action_behavior_ids
        for row in items["business_capability_matrix"].rows
    )
    assert any(
        row.row_id == "finance_quote_plugin_handoff"
        and "external_receipt_id" in row.action_behavior_ids
        and "finance_assurance_review_plugin" in row.capability_ids
        for row in items["external_handoff_contract"].rows
    )
    assert any(
        row.row_id == "family:finance_quote_documents"
        and row.status == "boundary_guarded_complete"
        and "finance_quote_plugin_handoff" in row.capability_ids
        and "external_handoff_contract_ready" in row.action_behavior_ids
        for row in items["boundary_guarded_completion"].rows
    )
    assert any(
        row.row_id == "pack:professional_disclosure"
        and "professional_disclosure_plugin_ecosystem_handoff" in row.capability_ids
        for row in items["boundary_subject_release_dossier"].rows
    )
    assert any(
        row.row_id
        == "scene_input_source_audit:pack:exam_education:pack_requires_plugin_or_manual_input_boundary"
        and row.status == "managed_warning"
        and "exam_ai_complex_diagram_gate" in row.plugin_gate_ids
        for row in items["residual_warning_governance"].rows
    )
    assert any(
        row.row_id
        == "scene_count_profile_audit:pack_not_applicable_delta:pack:quick_formatting"
        and row.status == "reconciled"
        and "not_applicable_count_surface" in row.action_behavior_ids
        for row in items["boundary_readiness_reconciliation"].rows
    )
    assert any(
        row.row_id == "managed_residual_warnings"
        and row.status == "governed"
        and "managed_warning_governance" in row.capability_ids
        and "10 traces" in row.detail
        and any(
            capability_id.startswith("scene_residual_warning_governance_audit:")
            for capability_id in row.capability_ids
        )
        for row in items["terminal_release_exception"].rows
    )
    assert any(
        row.row_id == "family:ip_patent_documents"
        and row.status == "release_dossier_ready"
        and "7 traces" in row.detail
        and "boundary_guarded_maturity" in row.action_behavior_ids
        for row in items["boundary_subject_release_dossier"].rows
    )
    assert any(
        row.status == "attributed"
        and "generic_not_applicable_surface" in row.action_behavior_ids
        and "quick_formatting" in row.pack_ids
        for row in items["non_subject_release_trace_attribution"].rows
    )
    assert any(
        row.row_id == "terminal_release_trace_total"
        and row.status == "partition_ready"
        and "36/36 traces" in row.detail
        and "complete_trace_partition" in row.capability_ids
        for row in items["release_trace_partition_guard"].rows
    )
    assert any(
        row.row_id == "release_trace_partition_guard"
        and row.status == "projection_ready"
        and "release_trace_partition" in row.action_behavior_ids
        and "trace partition" in row.capability_ids
        for row in items["release_projection_surface_parity"].rows
    )
    assert any(
        row.row_id == "family:ip_patent_documents"
        and row.status == "continuity_ready"
        and "terminal_release" in row.action_behavior_ids
        and "boundary_subject_release_dossier" in row.capability_ids
        for row in items["boundary_subject_release_continuity"].rows
    )
    assert any(
        row.row_id == "release_projection_surface_parity"
        and row.status == "ledger_stage_ready"
        and "release_trace_partition_guard" in row.capability_ids
        and "scene_release_projection_surface_parity_audit"
        in row.action_behavior_ids
        for row in items["release_closure_ledger"].rows
    )
    assert any(
        row.row_id == "maturity_l5_blocked"
        and row.status == "published_residual_ratio"
        and "boundary_maturity_retained" in row.action_behavior_ids
        and "boundary_scope_guarded" in row.action_behavior_ids
        and "receipt_alignments=6/6" in row.action_behavior_ids
        and "maturity_l5_receipts=6/6" in row.action_behavior_ids
        and "pack:professional_disclosure:real plugin ecosystem"
        in row.capability_ids
        and "professional_disclosure_boundary_matrix" in row.capability_ids
        and "receipt_alignments=6/6" in row.detail
        and "maturity_l5_receipts=6/6" in row.detail
        and "audit opinion" in row.detail
        for row in items["release_residual_ratio_ledger"].rows
    )
    assert any(
        row.row_id == "count_profiles"
        and row.status == "published_residual_ratio"
        and "boundary_scope_guarded" in row.action_behavior_ids
        and "receipt_alignments=2/2" in row.action_behavior_ids
        and "count_delivery_receipts=2/2" in row.action_behavior_ids
        and "ip_patent_boundary_depth" in row.capability_ids
        and "import_ai_boundary_confidence_matrix" in row.capability_ids
        and "receipt_alignments=2/2" in row.detail
        and "count_delivery_receipts=2/2" in row.detail
        and "claim quality judgment" in row.detail
        and "lossless PDF to Word" in row.detail
        for row in items["release_residual_ratio_ledger"].rows
    )
    assert any(
        row.row_id == "delivery_families"
        and row.status == "published_residual_ratio"
        and "receipt_alignments=2/2" in row.action_behavior_ids
        and "count_delivery_receipts=2/2" in row.action_behavior_ids
        and "receipt_alignments=2/2" in row.detail
        and "count_delivery_receipts=2/2" in row.detail
        and "boundary_delivery_surface" in row.action_behavior_ids
        for row in items["release_residual_ratio_ledger"].rows
    )
    assert any(
        row.row_id == "count_delivery_alignment"
        and row.status == "covered"
        and "count_delivery_alignment=" in row.action_behavior_ids
        for row in items["release_residual_explanation"].rows
    )
    assert any(
        row.row_id == "maturity_l5_alignment"
        and row.status == "covered"
        and "maturity_l5_alignment=" in row.action_behavior_ids
        for row in items["release_residual_explanation"].rows
    )
    assert any(
        row.row_id == "boundary_scope_alignment"
        and row.status == "covered"
        and "boundary_scope_alignment=" in row.action_behavior_ids
        for row in items["release_residual_explanation"].rows
    )
    assert any(
        row.row_id == "release_projection_surface_parity"
        and row.status == "certificate_ready"
        and "scene_release_projection_surface_parity_audit" in row.capability_ids
        for row in items["release_acceptance_certificate"].rows
    )
    assert any(
        row.row_id == "high_frequency_coverage"
        and row.status == "certificate_ready"
        and "high_frequency_coverage" in row.capability_ids
        and "high_frequency_completeness_audit" in row.capability_ids
        for row in items["release_acceptance_certificate"].rows
    )
    assert any(
        row.row_id == "count_delivery_boundary_alignment"
        and row.status == "certificate_ready"
        and "scene_release_residual_ratio_ledger_audit" in row.capability_ids
        for row in items["release_acceptance_certificate"].rows
    )
    assert any(
        row.row_id == "maturity_l5_blocker_alignment"
        and row.status == "certificate_ready"
        and "scene_release_residual_ratio_ledger_audit" in row.capability_ids
        for row in items["release_acceptance_certificate"].rows
    )
    assert any(
        row.row_id == "release_residual_boundary_scope_alignment"
        and row.status == "certificate_ready"
        and "scene_release_residual_ratio_ledger_audit" in row.capability_ids
        for row in items["release_acceptance_certificate"].rows
    )
    assert any(
        row.row_id == "release_residual_ratio_receipts"
        and row.status == "certificate_ready"
        and "acceptance_receipt_trace" in row.action_behavior_ids
        and "scene_release_residual_ratio_ledger_audit" in row.capability_ids
        for row in items["release_acceptance_certificate"].rows
    )
    assert any(
        row.row_id == "retained_gap_external_receipts"
        and row.status == "certificate_ready"
        and "acceptance_receipt_trace" in row.action_behavior_ids
        and "scene_retained_gap_exit_criteria_audit" in row.capability_ids
        for row in items["release_acceptance_certificate"].rows
    )
    assert any(
        row.row_id == "requirement:formula_output_watermark_scene_ownership"
        and row.status == "dimension_ready"
        and "requirement_dimension_trace" in row.action_behavior_ids
        and "scene_formula_output_watermark_audit" in row.capability_ids
        for row in items["release_acceptance_certificate"].rows
    )
    assert any(
        row.row_id == "journal_en"
        and "count_engine_tech_record" in row.capability_ids
        for row in items["business_capability_matrix"].rows
    )
    assert {row.row_id for row in items["control_runtime_consistency"].rows}.issuperset(
        {"paragraph_indent_pair", "special_indent_switch", "line_spacing_binding"}
    )
    assert any(
        "fixed_row_height" in row.word_risk_surface_ids
        for row in items["control_runtime_consistency"].rows
    )
    assert any(
        row.row_id == "paragraph_indent_pair"
        and "TemplateStyleDetail._left_indent" in row.capability_ids
        and "TemplateStyleDetail._right_indent" in row.capability_ids
        and "style.left_indent_unit" in row.capability_ids
        and "style.right_indent_unit" in row.capability_ids
        for row in items["control_runtime_consistency"].rows
    )
    assert any(
        row.row_id == "special_indent_switch"
        and "TemplateStyleDetail._special_indent" in row.capability_ids
        and "style.special_indent_mode" in row.capability_ids
        and "style.special_indent_unit" in row.capability_ids
        for row in items["control_runtime_consistency"].rows
    )
    assert any(
        "fixed_row_height" in row.word_risk_surface_ids
        for row in items["word_risk"].rows
    )
    assert any(
        "json" in row.input_source_ids and "structured_intermediate" in row.render_source_ids
        for row in items["input_source"].rows
    )
    assert any(
        row.row_id == "failed_run_material_package_outputs"
        and "failed_run_material_package" in row.delivery_preset_ids
        for row in items["delivery_execution"].rows
    )
    assert any(
        row.row_id == "schema_replacement_recommendation_flow"
        and "schema_alias_recommendation" in row.capability_ids
        for row in items["material_repair_flow"].rows
    )
    assert any(
        row.row_id == "batch_profile_material_repair_targets"
        and "profile_field" in row.action_behavior_ids
        for row in items["material_repair_flow"].rows
    )
    assert any(
        row.row_id == "fixed_layout_repair_route"
        and "row_height" in row.action_behavior_ids
        for row in items["fixed_layout_profile"].rows
    )
    assert any(
        row.row_id == "row_height_ooxml_runtime"
        and "w:trHeight" in row.capability_ids
        for row in items["fixed_layout_profile"].rows
    )
    assert any(
        row.row_id == "recent_run_artifact_browser"
        and "QDesktopServices.openUrl" in row.capability_ids
        for row in items["report_artifact_drilldown"].rows
    )
    assert any(
        row.row_id == "output_target_warning_repair"
        and "output_target" in row.action_behavior_ids
        for row in items["report_artifact_drilldown"].rows
    )
    assert any(
        "fields" in row.object_preflight_target_ids
        and "repair_route" in row.action_behavior_ids
        for row in items["object_preflight_action"].rows
    )


def test_scene_matrix_drilldown_audit_rejects_duplicate_item_row_and_source_ids():
    report = build_scene_matrix_drilldown_report(project_root=ROOT)
    first_item = report.items[0]
    first_row = first_item.rows[0]
    profiled_item = next(
        item for item in report.items if item.drilldown_id == "material_repair_flow"
    )
    profiled_row = profiled_item.rows[0]
    surface_profiled_expected_ids = _projection_surface_reference_map()[
        (
            profiled_item.drilldown_id,
            profiled_row.row_id,
            "action_behavior_ids",
        )
    ]
    source_profiled_item = next(
        item for item in report.items if item.drilldown_id == "release_closure_ledger"
    )
    source_profiled_row = source_profiled_item.rows[0]
    source_profiled_expected_ids = _projection_source_reference_map()[
        (
            source_profiled_item.drilldown_id,
            source_profiled_row.row_id,
            "capability_ids",
        )
    ]
    path_profiled_item = source_profiled_item
    path_profiled_row = next(
        row
        for row in path_profiled_item.rows
        if row.row_id == "release_acceptance_certificate"
    )
    path_profiled_expected_ids = _projection_path_reference_map()[
        (
            path_profiled_item.drilldown_id,
            path_profiled_row.row_id,
            "capability_ids",
        )
    ]
    evidence_profiled_item = next(
        item
        for item in report.items
        if item.drilldown_id == "boundary_guarded_completion"
    )
    evidence_profiled_row = evidence_profiled_item.rows[0]
    evidence_profiled_expected_ids = _projection_evidence_reference_map()[
        (
            evidence_profiled_item.drilldown_id,
            evidence_profiled_row.row_id,
            "action_behavior_ids",
        )
    ]
    release_marker_profiled_item = source_profiled_item
    release_marker_profiled_row = source_profiled_row
    release_marker_profiled_expected_ids = (
        _projection_release_marker_reference_map()[
            (
                release_marker_profiled_item.drilldown_id,
                release_marker_profiled_row.row_id,
                "action_behavior_ids",
            )
        ]
    )
    release_link_profiled_item = source_profiled_item
    release_link_reference_map = _projection_release_link_reference_map()
    release_link_profiled_row = next(
        row
        for row in release_link_profiled_item.rows
        if release_link_reference_map.get(
            (
                release_link_profiled_item.drilldown_id,
                row.row_id,
                "capability_ids",
            )
        )
    )
    release_link_profiled_expected_ids = release_link_reference_map[
        (
            release_link_profiled_item.drilldown_id,
            release_link_profiled_row.row_id,
            "capability_ids",
        )
    ]
    retained_gap_exit_profiled_item = next(
        item
        for item in report.items
        if item.drilldown_id == "retained_gap_exit_criteria"
    )
    retained_gap_exit_reference_map = _projection_retained_gap_exit_reference_map()
    retained_gap_exit_profiled_row = next(
        row
        for row in retained_gap_exit_profiled_item.rows
        if retained_gap_exit_reference_map.get(
            (
                retained_gap_exit_profiled_item.drilldown_id,
                row.row_id,
                "action_behavior_ids",
            )
        )
    )
    retained_gap_exit_profiled_expected_ids = retained_gap_exit_reference_map[
        (
            retained_gap_exit_profiled_item.drilldown_id,
            retained_gap_exit_profiled_row.row_id,
            "action_behavior_ids",
        )
    ]
    control_runtime_profiled_item = next(
        item
        for item in report.items
        if item.drilldown_id == "control_runtime_consistency"
    )
    control_runtime_reference_map = _projection_control_runtime_reference_map()
    control_runtime_profiled_row = next(
        row
        for row in control_runtime_profiled_item.rows
        if control_runtime_reference_map.get(
            (
                control_runtime_profiled_item.drilldown_id,
                row.row_id,
                "capability_ids",
            )
        )
    )
    control_runtime_profiled_expected_ids = control_runtime_reference_map[
        (
            control_runtime_profiled_item.drilldown_id,
            control_runtime_profiled_row.row_id,
            "capability_ids",
        )
    ]
    release_metric_profiled_item = next(
        item
        for item in report.items
        if item.drilldown_id == "release_residual_ratio_ledger"
    )
    release_metric_reference_map = _projection_release_metric_reference_map()
    release_metric_profiled_row = next(
        row
        for row in release_metric_profiled_item.rows
        if release_metric_reference_map.get(
            (
                release_metric_profiled_item.drilldown_id,
                row.row_id,
                "action_behavior_ids",
            )
        )
    )
    release_metric_profiled_expected_ids = release_metric_reference_map[
        (
            release_metric_profiled_item.drilldown_id,
            release_metric_profiled_row.row_id,
            "action_behavior_ids",
        )
    ]
    handoff_contract_profiled_item = next(
        item
        for item in report.items
        if item.drilldown_id == "boundary_subject_release_dossier"
    )
    handoff_contract_reference_map = (
        _projection_external_handoff_contract_reference_map()
    )
    handoff_contract_profiled_row = next(
        row
        for row in handoff_contract_profiled_item.rows
        if handoff_contract_reference_map.get(
            (
                handoff_contract_profiled_item.drilldown_id,
                row.row_id,
                "capability_ids",
            )
        )
    )
    handoff_contract_profiled_expected_ids = handoff_contract_reference_map[
        (
            handoff_contract_profiled_item.drilldown_id,
            handoff_contract_profiled_row.row_id,
            "capability_ids",
        )
    ]
    report_delivery_marker_profiled_item = next(
        item
        for item in report.items
        if item.drilldown_id == "report_artifact_drilldown"
    )
    report_delivery_marker_reference_map = (
        _projection_report_delivery_marker_reference_map()
    )
    report_delivery_marker_profiled_row = next(
        row
        for row in report_delivery_marker_profiled_item.rows
        if report_delivery_marker_reference_map.get(
            (
                report_delivery_marker_profiled_item.drilldown_id,
                row.row_id,
                "capability_ids",
            )
        )
    )
    report_delivery_marker_profiled_expected_ids = (
        report_delivery_marker_reference_map[
            (
                report_delivery_marker_profiled_item.drilldown_id,
                report_delivery_marker_profiled_row.row_id,
                "capability_ids",
            )
        ]
    )
    requirement_dimension_profiled_item = next(
        item
        for item in report.items
        if item.drilldown_id == "release_acceptance_certificate"
    )
    requirement_dimension_reference_map = (
        _projection_requirement_dimension_reference_map()
    )
    requirement_dimension_profiled_row = next(
        row
        for row in requirement_dimension_profiled_item.rows
        if requirement_dimension_reference_map.get(
            (
                requirement_dimension_profiled_item.drilldown_id,
                row.row_id,
                "capability_ids",
            )
        )
    )
    requirement_dimension_profiled_expected_ids = (
        requirement_dimension_reference_map[
            (
                requirement_dimension_profiled_item.drilldown_id,
                requirement_dimension_profiled_row.row_id,
                "capability_ids",
            )
        ]
    )
    target_plugin_profiled_item = next(
        item
        for item in report.items
        if item.drilldown_id == "external_handoff_contract"
    )
    target_plugin_reference_map = _projection_target_plugin_reference_map()
    target_plugin_profiled_row = next(
        row
        for row in target_plugin_profiled_item.rows
        if target_plugin_reference_map.get(
            (
                target_plugin_profiled_item.drilldown_id,
                row.row_id,
                "capability_ids",
            )
        )
    )
    target_plugin_profiled_expected_ids = target_plugin_reference_map[
        (
            target_plugin_profiled_item.drilldown_id,
            target_plugin_profiled_row.row_id,
            "capability_ids",
        )
    ]
    formula_output_watermark_profiled_item = next(
        item
        for item in report.items
        if item.drilldown_id == "formula_output_watermark"
    )
    formula_output_watermark_reference_map = (
        _projection_formula_output_watermark_reference_map()
    )
    formula_output_watermark_profiled_row = next(
        row
        for row in formula_output_watermark_profiled_item.rows
        if formula_output_watermark_reference_map.get(
            (
                formula_output_watermark_profiled_item.drilldown_id,
                row.row_id,
                "capability_ids",
            )
        )
    )
    formula_output_watermark_profiled_expected_ids = (
        formula_output_watermark_reference_map[
            (
                formula_output_watermark_profiled_item.drilldown_id,
                formula_output_watermark_profiled_row.row_id,
                "capability_ids",
            )
        ]
    )

    duplicate_item_report = SceneMatrixDrilldownReport(
        items=(first_item, first_item),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    duplicate_row_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id=first_item.source_id,
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=(first_row, first_row),
        visible_rows=(first_row, first_row),
    )
    duplicate_row_report = SceneMatrixDrilldownReport(
        items=(duplicate_row_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    missing_source_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id="unregistered_scene_matrix_source",
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=first_item.rows,
        visible_rows=first_item.visible_rows,
    )
    missing_source_report = SceneMatrixDrilldownReport(
        items=(missing_source_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    mismatched_row = replace(
        first_row,
        source_id="unregistered_scene_matrix_row_source",
    )
    missing_row_source_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id=first_item.source_id,
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=(mismatched_row,),
        visible_rows=(mismatched_row,),
    )
    missing_row_source_report = SceneMatrixDrilldownReport(
        items=(missing_row_source_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    unknown_pack_family_row = replace(
        first_row,
        pack_ids=("unknown_scene_pack",),
        family_ids=("unknown_scene_family",),
    )
    unknown_pack_family_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id=first_item.source_id,
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=(unknown_pack_family_row,),
        visible_rows=(unknown_pack_family_row,),
    )
    unknown_pack_family_report = SceneMatrixDrilldownReport(
        items=(unknown_pack_family_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    unknown_request_fixture_row = replace(
        first_row,
        request_cell_ids=("unknown_request_cell",),
        fixture_ids=("unknown_scene_fixture",),
    )
    unknown_request_fixture_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id=first_item.source_id,
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=(unknown_request_fixture_row,),
        visible_rows=(unknown_request_fixture_row,),
    )
    unknown_request_fixture_report = SceneMatrixDrilldownReport(
        items=(unknown_request_fixture_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    unknown_count_delivery_row = replace(
        first_row,
        count_profile_ids=("unknown_count_profile",),
        delivery_preset_ids=("unknown_delivery_reference",),
    )
    unknown_count_delivery_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id=first_item.source_id,
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=(unknown_count_delivery_row,),
        visible_rows=(unknown_count_delivery_row,),
    )
    unknown_count_delivery_report = SceneMatrixDrilldownReport(
        items=(unknown_count_delivery_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    unknown_material_reference_row = replace(
        first_row,
        material_schema_ids=("unknown_material_reference",),
    )
    unknown_material_reference_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id=first_item.source_id,
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=(unknown_material_reference_row,),
        visible_rows=(unknown_material_reference_row,),
    )
    unknown_material_reference_report = SceneMatrixDrilldownReport(
        items=(unknown_material_reference_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    unknown_input_object_word_row = replace(
        first_row,
        input_source_ids=("unknown_input_source",),
        render_source_ids=("unknown_render_source",),
        object_preflight_target_ids=("unknown_object_preflight_target",),
        word_risk_surface_ids=("unknown_word_risk_surface",),
    )
    unknown_input_object_word_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id=first_item.source_id,
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=(unknown_input_object_word_row,),
        visible_rows=(unknown_input_object_word_row,),
    )
    unknown_input_object_word_report = SceneMatrixDrilldownReport(
        items=(unknown_input_object_word_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    unknown_plugin_risk_maturity_row = replace(
        first_row,
        plugin_gate_ids=("unknown_plugin_gate",),
        risk_domain_ids=("unknown_risk_domain",),
        maturity_gap_domain_ids=("unknown_maturity_gap_reference",),
    )
    unknown_plugin_risk_maturity_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id=first_item.source_id,
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=(unknown_plugin_risk_maturity_row,),
        visible_rows=(unknown_plugin_risk_maturity_row,),
    )
    unknown_plugin_risk_maturity_report = SceneMatrixDrilldownReport(
        items=(unknown_plugin_risk_maturity_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    unprofiled_projection_row = replace(
        first_row,
        action_behavior_ids=("unprofiled_action",),
        capability_ids=("unprofiled_capability",),
    )
    unprofiled_projection_item = SceneMatrixDrilldownItem(
        drilldown_id=first_item.drilldown_id,
        label=first_item.label,
        source_id=first_item.source_id,
        lens_ids=first_item.lens_ids,
        route_hint=first_item.route_hint,
        detail=first_item.detail,
        rows=(unprofiled_projection_row,),
        visible_rows=(unprofiled_projection_row,),
    )
    unprofiled_projection_report = SceneMatrixDrilldownReport(
        items=(unprofiled_projection_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=first_item.source_id,
    )
    unknown_projection_test_row = replace(
        profiled_row,
        capability_ids=("test_unknown_projection_reference",),
    )
    unknown_projection_test_item = SceneMatrixDrilldownItem(
        drilldown_id=profiled_item.drilldown_id,
        label=profiled_item.label,
        source_id=profiled_item.source_id,
        lens_ids=profiled_item.lens_ids,
        route_hint=profiled_item.route_hint,
        detail=profiled_item.detail,
        rows=(unknown_projection_test_row,),
        visible_rows=(unknown_projection_test_row,),
    )
    unknown_projection_test_report = SceneMatrixDrilldownReport(
        items=(unknown_projection_test_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=profiled_item.source_id,
    )
    missing_projection_surface_row = replace(
        profiled_row,
        action_behavior_ids=tuple(
            value
            for value in profiled_row.action_behavior_ids
            if value not in surface_profiled_expected_ids
        ),
    )
    missing_projection_surface_item = SceneMatrixDrilldownItem(
        drilldown_id=profiled_item.drilldown_id,
        label=profiled_item.label,
        source_id=profiled_item.source_id,
        lens_ids=profiled_item.lens_ids,
        route_hint=profiled_item.route_hint,
        detail=profiled_item.detail,
        rows=(missing_projection_surface_row,),
        visible_rows=(missing_projection_surface_row,),
    )
    missing_projection_surface_report = SceneMatrixDrilldownReport(
        items=(missing_projection_surface_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=profiled_item.source_id,
    )
    missing_projection_source_row = replace(
        source_profiled_row,
        capability_ids=tuple(
            value
            for value in source_profiled_row.capability_ids
            if value not in source_profiled_expected_ids
        ),
    )
    missing_projection_source_item = SceneMatrixDrilldownItem(
        drilldown_id=source_profiled_item.drilldown_id,
        label=source_profiled_item.label,
        source_id=source_profiled_item.source_id,
        lens_ids=source_profiled_item.lens_ids,
        route_hint=source_profiled_item.route_hint,
        detail=source_profiled_item.detail,
        rows=(missing_projection_source_row,),
        visible_rows=(missing_projection_source_row,),
    )
    missing_projection_source_report = SceneMatrixDrilldownReport(
        items=(missing_projection_source_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=source_profiled_item.source_id,
    )
    missing_projection_path_row = replace(
        path_profiled_row,
        capability_ids=tuple(
            value
            for value in path_profiled_row.capability_ids
            if value not in path_profiled_expected_ids
        ),
    )
    missing_projection_path_item = SceneMatrixDrilldownItem(
        drilldown_id=path_profiled_item.drilldown_id,
        label=path_profiled_item.label,
        source_id=path_profiled_item.source_id,
        lens_ids=path_profiled_item.lens_ids,
        route_hint=path_profiled_item.route_hint,
        detail=path_profiled_item.detail,
        rows=(missing_projection_path_row,),
        visible_rows=(missing_projection_path_row,),
    )
    missing_projection_path_report = SceneMatrixDrilldownReport(
        items=(missing_projection_path_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=path_profiled_item.source_id,
    )
    missing_projection_evidence_row = replace(
        evidence_profiled_row,
        action_behavior_ids=tuple(
            value
            for value in evidence_profiled_row.action_behavior_ids
            if value not in evidence_profiled_expected_ids
        ),
    )
    missing_projection_evidence_item = SceneMatrixDrilldownItem(
        drilldown_id=evidence_profiled_item.drilldown_id,
        label=evidence_profiled_item.label,
        source_id=evidence_profiled_item.source_id,
        lens_ids=evidence_profiled_item.lens_ids,
        route_hint=evidence_profiled_item.route_hint,
        detail=evidence_profiled_item.detail,
        rows=(missing_projection_evidence_row,),
        visible_rows=(missing_projection_evidence_row,),
    )
    missing_projection_evidence_report = SceneMatrixDrilldownReport(
        items=(missing_projection_evidence_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=evidence_profiled_item.source_id,
    )
    missing_projection_release_marker_row = replace(
        release_marker_profiled_row,
        action_behavior_ids=tuple(
            value
            for value in release_marker_profiled_row.action_behavior_ids
            if value not in release_marker_profiled_expected_ids
        ),
    )
    missing_projection_release_marker_item = SceneMatrixDrilldownItem(
        drilldown_id=release_marker_profiled_item.drilldown_id,
        label=release_marker_profiled_item.label,
        source_id=release_marker_profiled_item.source_id,
        lens_ids=release_marker_profiled_item.lens_ids,
        route_hint=release_marker_profiled_item.route_hint,
        detail=release_marker_profiled_item.detail,
        rows=(missing_projection_release_marker_row,),
        visible_rows=(missing_projection_release_marker_row,),
    )
    missing_projection_release_marker_report = SceneMatrixDrilldownReport(
        items=(missing_projection_release_marker_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=release_marker_profiled_item.source_id,
    )
    missing_projection_release_link_row = replace(
        release_link_profiled_row,
        capability_ids=tuple(
            value
            for value in release_link_profiled_row.capability_ids
            if value not in release_link_profiled_expected_ids
        ),
    )
    missing_projection_release_link_item = SceneMatrixDrilldownItem(
        drilldown_id=release_link_profiled_item.drilldown_id,
        label=release_link_profiled_item.label,
        source_id=release_link_profiled_item.source_id,
        lens_ids=release_link_profiled_item.lens_ids,
        route_hint=release_link_profiled_item.route_hint,
        detail=release_link_profiled_item.detail,
        rows=(missing_projection_release_link_row,),
        visible_rows=(missing_projection_release_link_row,),
    )
    missing_projection_release_link_report = SceneMatrixDrilldownReport(
        items=(missing_projection_release_link_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=release_link_profiled_item.source_id,
    )
    missing_projection_retained_gap_exit_row = replace(
        retained_gap_exit_profiled_row,
        action_behavior_ids=tuple(
            value
            for value in retained_gap_exit_profiled_row.action_behavior_ids
            if value not in retained_gap_exit_profiled_expected_ids
        ),
    )
    missing_projection_retained_gap_exit_item = SceneMatrixDrilldownItem(
        drilldown_id=retained_gap_exit_profiled_item.drilldown_id,
        label=retained_gap_exit_profiled_item.label,
        source_id=retained_gap_exit_profiled_item.source_id,
        lens_ids=retained_gap_exit_profiled_item.lens_ids,
        route_hint=retained_gap_exit_profiled_item.route_hint,
        detail=retained_gap_exit_profiled_item.detail,
        rows=(missing_projection_retained_gap_exit_row,),
        visible_rows=(missing_projection_retained_gap_exit_row,),
    )
    missing_projection_retained_gap_exit_report = SceneMatrixDrilldownReport(
        items=(missing_projection_retained_gap_exit_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=retained_gap_exit_profiled_item.source_id,
    )
    missing_projection_control_runtime_row = replace(
        control_runtime_profiled_row,
        capability_ids=tuple(
            value
            for value in control_runtime_profiled_row.capability_ids
            if value not in control_runtime_profiled_expected_ids
        ),
    )
    missing_projection_control_runtime_item = SceneMatrixDrilldownItem(
        drilldown_id=control_runtime_profiled_item.drilldown_id,
        label=control_runtime_profiled_item.label,
        source_id=control_runtime_profiled_item.source_id,
        lens_ids=control_runtime_profiled_item.lens_ids,
        route_hint=control_runtime_profiled_item.route_hint,
        detail=control_runtime_profiled_item.detail,
        rows=(missing_projection_control_runtime_row,),
        visible_rows=(missing_projection_control_runtime_row,),
    )
    missing_projection_control_runtime_report = SceneMatrixDrilldownReport(
        items=(missing_projection_control_runtime_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=control_runtime_profiled_item.source_id,
    )
    missing_projection_release_metric_row = replace(
        release_metric_profiled_row,
        action_behavior_ids=tuple(
            value
            for value in release_metric_profiled_row.action_behavior_ids
            if value not in release_metric_profiled_expected_ids
        ),
    )
    missing_projection_release_metric_item = SceneMatrixDrilldownItem(
        drilldown_id=release_metric_profiled_item.drilldown_id,
        label=release_metric_profiled_item.label,
        source_id=release_metric_profiled_item.source_id,
        lens_ids=release_metric_profiled_item.lens_ids,
        route_hint=release_metric_profiled_item.route_hint,
        detail=release_metric_profiled_item.detail,
        rows=(missing_projection_release_metric_row,),
        visible_rows=(missing_projection_release_metric_row,),
    )
    missing_projection_release_metric_report = SceneMatrixDrilldownReport(
        items=(missing_projection_release_metric_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=release_metric_profiled_item.source_id,
    )
    missing_projection_handoff_contract_row = replace(
        handoff_contract_profiled_row,
        capability_ids=tuple(
            value
            for value in handoff_contract_profiled_row.capability_ids
            if value not in handoff_contract_profiled_expected_ids
        ),
    )
    missing_projection_handoff_contract_item = SceneMatrixDrilldownItem(
        drilldown_id=handoff_contract_profiled_item.drilldown_id,
        label=handoff_contract_profiled_item.label,
        source_id=handoff_contract_profiled_item.source_id,
        lens_ids=handoff_contract_profiled_item.lens_ids,
        route_hint=handoff_contract_profiled_item.route_hint,
        detail=handoff_contract_profiled_item.detail,
        rows=(missing_projection_handoff_contract_row,),
        visible_rows=(missing_projection_handoff_contract_row,),
    )
    missing_projection_handoff_contract_report = SceneMatrixDrilldownReport(
        items=(missing_projection_handoff_contract_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=handoff_contract_profiled_item.source_id,
    )
    missing_projection_report_delivery_marker_row = replace(
        report_delivery_marker_profiled_row,
        capability_ids=tuple(
            value
            for value in report_delivery_marker_profiled_row.capability_ids
            if value not in report_delivery_marker_profiled_expected_ids
        ),
    )
    missing_projection_report_delivery_marker_item = SceneMatrixDrilldownItem(
        drilldown_id=report_delivery_marker_profiled_item.drilldown_id,
        label=report_delivery_marker_profiled_item.label,
        source_id=report_delivery_marker_profiled_item.source_id,
        lens_ids=report_delivery_marker_profiled_item.lens_ids,
        route_hint=report_delivery_marker_profiled_item.route_hint,
        detail=report_delivery_marker_profiled_item.detail,
        rows=(missing_projection_report_delivery_marker_row,),
        visible_rows=(missing_projection_report_delivery_marker_row,),
    )
    missing_projection_report_delivery_marker_report = SceneMatrixDrilldownReport(
        items=(missing_projection_report_delivery_marker_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=report_delivery_marker_profiled_item.source_id,
    )
    missing_projection_requirement_dimension_row = replace(
        requirement_dimension_profiled_row,
        capability_ids=tuple(
            value
            for value in requirement_dimension_profiled_row.capability_ids
            if value not in requirement_dimension_profiled_expected_ids
        ),
    )
    missing_projection_requirement_dimension_item = SceneMatrixDrilldownItem(
        drilldown_id=requirement_dimension_profiled_item.drilldown_id,
        label=requirement_dimension_profiled_item.label,
        source_id=requirement_dimension_profiled_item.source_id,
        lens_ids=requirement_dimension_profiled_item.lens_ids,
        route_hint=requirement_dimension_profiled_item.route_hint,
        detail=requirement_dimension_profiled_item.detail,
        rows=(missing_projection_requirement_dimension_row,),
        visible_rows=(missing_projection_requirement_dimension_row,),
    )
    missing_projection_requirement_dimension_report = SceneMatrixDrilldownReport(
        items=(missing_projection_requirement_dimension_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=requirement_dimension_profiled_item.source_id,
    )
    missing_projection_target_plugin_row = replace(
        target_plugin_profiled_row,
        capability_ids=tuple(
            value
            for value in target_plugin_profiled_row.capability_ids
            if value not in target_plugin_profiled_expected_ids
        ),
    )
    missing_projection_target_plugin_item = SceneMatrixDrilldownItem(
        drilldown_id=target_plugin_profiled_item.drilldown_id,
        label=target_plugin_profiled_item.label,
        source_id=target_plugin_profiled_item.source_id,
        lens_ids=target_plugin_profiled_item.lens_ids,
        route_hint=target_plugin_profiled_item.route_hint,
        detail=target_plugin_profiled_item.detail,
        rows=(missing_projection_target_plugin_row,),
        visible_rows=(missing_projection_target_plugin_row,),
    )
    missing_projection_target_plugin_report = SceneMatrixDrilldownReport(
        items=(missing_projection_target_plugin_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=target_plugin_profiled_item.source_id,
    )
    missing_projection_formula_output_watermark_row = replace(
        formula_output_watermark_profiled_row,
        capability_ids=tuple(
            value
            for value in formula_output_watermark_profiled_row.capability_ids
            if value not in formula_output_watermark_profiled_expected_ids
        ),
    )
    missing_projection_formula_output_watermark_item = SceneMatrixDrilldownItem(
        drilldown_id=formula_output_watermark_profiled_item.drilldown_id,
        label=formula_output_watermark_profiled_item.label,
        source_id=formula_output_watermark_profiled_item.source_id,
        lens_ids=formula_output_watermark_profiled_item.lens_ids,
        route_hint=formula_output_watermark_profiled_item.route_hint,
        detail=formula_output_watermark_profiled_item.detail,
        rows=(missing_projection_formula_output_watermark_row,),
        visible_rows=(missing_projection_formula_output_watermark_row,),
    )
    missing_projection_formula_output_watermark_report = SceneMatrixDrilldownReport(
        items=(missing_projection_formula_output_watermark_item,),
        issues=(),
        source_evidence=report.source_evidence,
        source_filter=formula_output_watermark_profiled_item.source_id,
    )

    assert any(
        issue.kind == "duplicate_drilldown_id"
        for issue in audit_scene_matrix_drilldown_report(duplicate_item_report)
    )
    assert any(
        issue.kind == "duplicate_row_id"
        for issue in audit_scene_matrix_drilldown_report(duplicate_row_report)
    )
    assert any(
        issue.kind == "missing_item_source_evidence"
        for issue in audit_scene_matrix_drilldown_report(missing_source_report)
    )
    row_source_issues = audit_scene_matrix_drilldown_report(
        missing_row_source_report
    )
    assert any(
        issue.kind == "missing_row_source_evidence"
        for issue in row_source_issues
    )
    assert any(
        issue.kind == "row_source_mismatch"
        for issue in row_source_issues
    )
    pack_family_issues = audit_scene_matrix_drilldown_report(
        unknown_pack_family_report
    )
    assert any(
        issue.kind == "unknown_row_pack_id"
        for issue in pack_family_issues
    )
    assert any(
        issue.kind == "unknown_row_family_id"
        for issue in pack_family_issues
    )
    request_fixture_issues = audit_scene_matrix_drilldown_report(
        unknown_request_fixture_report
    )
    assert any(
        issue.kind == "unknown_row_request_cell_id"
        for issue in request_fixture_issues
    )
    assert any(
        issue.kind == "unknown_row_fixture_id"
        for issue in request_fixture_issues
    )
    count_delivery_issues = audit_scene_matrix_drilldown_report(
        unknown_count_delivery_report
    )
    assert any(
        issue.kind == "unknown_row_count_profile_id"
        for issue in count_delivery_issues
    )
    assert any(
        issue.kind == "unknown_row_delivery_reference_id"
        for issue in count_delivery_issues
    )
    material_reference_issues = audit_scene_matrix_drilldown_report(
        unknown_material_reference_report
    )
    assert any(
        issue.kind == "unknown_row_material_reference_id"
        for issue in material_reference_issues
    )
    input_object_word_issues = audit_scene_matrix_drilldown_report(
        unknown_input_object_word_report
    )
    assert any(
        issue.kind == "unknown_row_input_source_id"
        for issue in input_object_word_issues
    )
    assert any(
        issue.kind == "unknown_row_render_source_id"
        for issue in input_object_word_issues
    )
    assert any(
        issue.kind == "unknown_row_object_preflight_target_id"
        for issue in input_object_word_issues
    )
    assert any(
        issue.kind == "unknown_row_word_risk_surface_id"
        for issue in input_object_word_issues
    )
    plugin_risk_maturity_issues = audit_scene_matrix_drilldown_report(
        unknown_plugin_risk_maturity_report
    )
    assert any(
        issue.kind == "unknown_row_plugin_gate_id"
        for issue in plugin_risk_maturity_issues
    )
    assert any(
        issue.kind == "unknown_row_risk_domain_id"
        for issue in plugin_risk_maturity_issues
    )
    assert any(
        issue.kind == "unknown_row_maturity_gap_reference_id"
        for issue in plugin_risk_maturity_issues
    )
    unprofiled_projection_issues = audit_scene_matrix_drilldown_report(
        unprofiled_projection_report
    )
    assert any(
        issue.kind == "missing_action_behavior_projection_profile"
        for issue in unprofiled_projection_issues
    )
    assert any(
        issue.kind == "missing_capability_projection_profile"
        for issue in unprofiled_projection_issues
    )
    unknown_projection_test_issues = audit_scene_matrix_drilldown_report(
        unknown_projection_test_report
    )
    assert any(
        issue.kind == "unknown_projection_test_reference_id"
        for issue in unknown_projection_test_issues
    )
    missing_projection_source_issues = audit_scene_matrix_drilldown_report(
        missing_projection_source_report
    )
    assert any(
        issue.kind == "missing_projection_source_reference_id"
        for issue in missing_projection_source_issues
    )
    missing_projection_surface_issues = audit_scene_matrix_drilldown_report(
        missing_projection_surface_report
    )
    assert any(
        issue.kind == "missing_projection_surface_reference_id"
        for issue in missing_projection_surface_issues
    )
    missing_projection_path_issues = audit_scene_matrix_drilldown_report(
        missing_projection_path_report
    )
    assert any(
        issue.kind == "missing_projection_path_reference_id"
        for issue in missing_projection_path_issues
    )
    missing_projection_evidence_issues = audit_scene_matrix_drilldown_report(
        missing_projection_evidence_report
    )
    assert any(
        issue.kind == "missing_projection_evidence_reference_id"
        for issue in missing_projection_evidence_issues
    )
    missing_projection_release_marker_issues = audit_scene_matrix_drilldown_report(
        missing_projection_release_marker_report
    )
    assert any(
        issue.kind == "missing_projection_release_marker_reference_id"
        for issue in missing_projection_release_marker_issues
    )
    missing_projection_release_link_issues = audit_scene_matrix_drilldown_report(
        missing_projection_release_link_report
    )
    assert any(
        issue.kind == "missing_projection_release_link_reference_id"
        for issue in missing_projection_release_link_issues
    )
    missing_projection_retained_gap_exit_issues = (
        audit_scene_matrix_drilldown_report(
            missing_projection_retained_gap_exit_report
        )
    )
    assert any(
        issue.kind == "missing_projection_retained_gap_exit_reference_id"
        for issue in missing_projection_retained_gap_exit_issues
    )
    missing_projection_control_runtime_issues = audit_scene_matrix_drilldown_report(
        missing_projection_control_runtime_report
    )
    assert any(
        issue.kind == "missing_projection_control_runtime_reference_id"
        for issue in missing_projection_control_runtime_issues
    )
    missing_projection_release_metric_issues = audit_scene_matrix_drilldown_report(
        missing_projection_release_metric_report
    )
    assert any(
        issue.kind == "missing_projection_release_metric_reference_id"
        for issue in missing_projection_release_metric_issues
    )
    missing_projection_handoff_contract_issues = (
        audit_scene_matrix_drilldown_report(
            missing_projection_handoff_contract_report
        )
    )
    assert any(
        issue.kind
        == "missing_projection_external_handoff_contract_reference_id"
        for issue in missing_projection_handoff_contract_issues
    )
    missing_projection_report_delivery_marker_issues = (
        audit_scene_matrix_drilldown_report(
            missing_projection_report_delivery_marker_report
        )
    )
    assert any(
        issue.kind == "missing_projection_report_delivery_marker_reference_id"
        for issue in missing_projection_report_delivery_marker_issues
    )
    missing_projection_requirement_dimension_issues = (
        audit_scene_matrix_drilldown_report(
            missing_projection_requirement_dimension_report
        )
    )
    assert any(
        issue.kind == "missing_projection_requirement_dimension_reference_id"
        for issue in missing_projection_requirement_dimension_issues
    )
    missing_projection_target_plugin_issues = audit_scene_matrix_drilldown_report(
        missing_projection_target_plugin_report
    )
    assert any(
        issue.kind == "missing_projection_target_plugin_reference_id"
        for issue in missing_projection_target_plugin_issues
    )
    missing_projection_formula_output_watermark_issues = (
        audit_scene_matrix_drilldown_report(
            missing_projection_formula_output_watermark_report
        )
    )
    assert any(
        issue.kind == "missing_projection_formula_output_watermark_reference_id"
        for issue in missing_projection_formula_output_watermark_issues
    )


def test_scene_matrix_drilldown_filters_for_pack_family_source_and_query():
    family_report = build_scene_matrix_drilldown_report(
        family_id="hr_batch_documents",
        project_root=ROOT,
    )
    source_report = build_scene_matrix_drilldown_report(
        source_id="scene_word_risk_closure_audit",
        query="fixed_row_height",
        project_root=ROOT,
    )
    external_report = build_scene_matrix_drilldown_report(
        source_id="scene_external_handoff_contract_audit",
        query="external_receipt_id",
        project_root=ROOT,
    )
    guarded_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_guarded_completion_audit",
        query="boundary_guarded_complete",
        project_root=ROOT,
    )
    residual_report = build_scene_matrix_drilldown_report(
        source_id="scene_residual_warning_governance_audit",
        query="registry_only_profile",
        project_root=ROOT,
    )
    reconciliation_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_readiness_reconciliation_audit",
        query="not_applicable_count_surface",
        project_root=ROOT,
    )
    terminal_report = build_scene_matrix_drilldown_report(
        source_id="scene_terminal_release_exception_audit",
        query="managed_residual_warnings",
        project_root=ROOT,
    )
    dossier_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_subject_release_dossier_audit",
        query="ip_patent_documents",
        project_root=ROOT,
    )
    non_subject_report = build_scene_matrix_drilldown_report(
        source_id="scene_non_subject_release_trace_attribution_audit",
        query="generic_not_applicable_surface",
        project_root=ROOT,
    )
    partition_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_trace_partition_guard_audit",
        query="terminal_release_trace_total",
        project_root=ROOT,
    )
    projection_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_projection_surface_parity_audit",
        query="release_trace_partition_guard",
        project_root=ROOT,
    )
    continuity_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_subject_release_continuity_audit",
        query="ip_patent_documents",
        project_root=ROOT,
    )
    release_ledger_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_closure_ledger_audit",
        query="release_projection_surface_parity",
        project_root=ROOT,
    )
    release_envelope_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_maturity_release_envelope_audit",
        query="ip_patent_documents",
        project_root=ROOT,
    )
    release_ratio_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_residual_ratio_ledger_audit",
        query="maturity_l5_blocked",
        project_root=ROOT,
    )
    release_acceptance_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_acceptance_certificate_audit",
        query="release_projection_surface_parity",
        project_root=ROOT,
    )
    acceptance_receipt_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_acceptance_certificate_audit",
        query="acceptance_receipt_trace",
        project_root=ROOT,
    )
    batch_report = build_scene_matrix_drilldown_report(
        pack_id="batch_forms",
        project_root=ROOT,
    )

    family_items = {item.drilldown_id: item for item in family_report.items}
    source_items = {item.drilldown_id: item for item in source_report.items}
    external_items = {item.drilldown_id: item for item in external_report.items}
    guarded_items = {item.drilldown_id: item for item in guarded_report.items}
    residual_items = {item.drilldown_id: item for item in residual_report.items}
    reconciliation_items = {
        item.drilldown_id: item for item in reconciliation_report.items
    }
    terminal_items = {item.drilldown_id: item for item in terminal_report.items}
    dossier_items = {item.drilldown_id: item for item in dossier_report.items}
    non_subject_items = {
        item.drilldown_id: item for item in non_subject_report.items
    }
    partition_items = {
        item.drilldown_id: item for item in partition_report.items
    }
    projection_items = {
        item.drilldown_id: item for item in projection_report.items
    }
    continuity_items = {
        item.drilldown_id: item for item in continuity_report.items
    }
    release_ledger_items = {
        item.drilldown_id: item for item in release_ledger_report.items
    }
    release_envelope_items = {
        item.drilldown_id: item for item in release_envelope_report.items
    }
    release_ratio_items = {
        item.drilldown_id: item for item in release_ratio_report.items
    }
    release_acceptance_items = {
        item.drilldown_id: item for item in release_acceptance_report.items
    }
    acceptance_receipt_items = {
        item.drilldown_id: item for item in acceptance_receipt_report.items
    }
    batch_items = {item.drilldown_id: item for item in batch_report.items}

    assert family_report.status == "passed"
    assert family_items["matrix_dashboard"].visible_count == 1
    assert family_items["request_cells"].visible_count == 2
    assert family_items["ambiguity_clarification"].visible_count == 1
    assert family_items["user_journey_fixture"].visible_count == 5
    assert family_items["business_capability_matrix"].visible_count == 1
    assert family_items["boundary_guarded_completion"].visible_count == 0
    assert family_items["residual_warning_governance"].visible_count == 0
    assert family_items["boundary_readiness_reconciliation"].visible_count == 0
    assert family_items["terminal_release_exception"].visible_count == 0
    assert family_items["boundary_subject_release_dossier"].visible_count == 0
    assert family_items["non_subject_release_trace_attribution"].visible_count == 0
    assert family_items["release_trace_partition_guard"].visible_count == 0
    assert family_items["release_projection_surface_parity"].visible_count == 0
    assert family_items["boundary_subject_release_continuity"].visible_count == 0
    assert family_items["release_closure_ledger"].visible_count == 0
    assert family_items["boundary_maturity_release_envelope"].visible_count == 0
    assert family_items["release_residual_ratio_ledger"].visible_count == 0
    assert family_items["release_acceptance_certificate"].visible_count == 0
    assert family_items["control_runtime_consistency"].visible_count == 0
    assert family_items["input_source"].visible_count == 1
    assert family_items["object_preflight_action"].visible_count == 1
    assert family_items["family_fixture_depth"].visible_count == 1
    assert family_items["count_profile"].visible_count == 1
    assert family_items["material_schema"].visible_count == 1
    assert family_items["material_repair_flow"].visible_count == 11
    assert family_items["fixed_layout_profile"].visible_count == 3
    assert family_items["report_artifact_drilldown"].visible_count == 10
    assert family_items["delivery_preset"].visible_count == 1
    assert family_items["delivery_execution"].visible_count == 7
    assert family_items["formula_output_watermark"].visible_count == 2
    assert family_items["maturity_upgrade"].visible_count == 2
    assert family_items["family_fixture_depth"].visible_rows[0].row_id == (
        "hr_batch_documents"
    )

    assert [item.drilldown_id for item in source_report.items] == ["word_risk"]
    assert source_items["word_risk"].visible_count == 1
    assert source_items["word_risk"].visible_rows[0].row_id == "fixed_row_height"
    assert [item.drilldown_id for item in external_report.items] == [
        "external_handoff_contract"
    ]
    assert external_items["external_handoff_contract"].visible_count == 6
    assert [item.drilldown_id for item in guarded_report.items] == [
        "boundary_guarded_completion"
    ]
    assert guarded_items["boundary_guarded_completion"].visible_count == 6
    assert [item.drilldown_id for item in residual_report.items] == [
        "residual_warning_governance"
    ]
    assert residual_items["residual_warning_governance"].visible_count == 2
    assert [item.drilldown_id for item in reconciliation_report.items] == [
        "boundary_readiness_reconciliation"
    ]
    assert (
        reconciliation_items["boundary_readiness_reconciliation"].visible_count
        == 2
    )
    assert [item.drilldown_id for item in terminal_report.items] == [
        "terminal_release_exception"
    ]
    assert terminal_items["terminal_release_exception"].visible_count == 1
    assert [item.drilldown_id for item in dossier_report.items] == [
        "boundary_subject_release_dossier"
    ]
    assert dossier_items["boundary_subject_release_dossier"].visible_count == 1
    assert [item.drilldown_id for item in non_subject_report.items] == [
        "non_subject_release_trace_attribution"
    ]
    assert (
        non_subject_items["non_subject_release_trace_attribution"].visible_count
        == 1
    )
    assert [item.drilldown_id for item in partition_report.items] == [
        "release_trace_partition_guard"
    ]
    assert partition_items["release_trace_partition_guard"].visible_count == 1
    assert [item.drilldown_id for item in projection_report.items] == [
        "release_projection_surface_parity"
    ]
    assert projection_items["release_projection_surface_parity"].visible_count == 1
    assert [item.drilldown_id for item in continuity_report.items] == [
        "boundary_subject_release_continuity"
    ]
    assert continuity_items["boundary_subject_release_continuity"].visible_count == 1
    assert [item.drilldown_id for item in release_ledger_report.items] == [
        "release_closure_ledger"
    ]
    assert release_ledger_items["release_closure_ledger"].visible_count == 4
    assert [item.drilldown_id for item in release_envelope_report.items] == [
        "boundary_maturity_release_envelope"
    ]
    assert (
        release_envelope_items[
            "boundary_maturity_release_envelope"
        ].visible_count
        == 1
    )
    assert [item.drilldown_id for item in release_ratio_report.items] == [
        "release_residual_ratio_ledger"
    ]
    assert release_ratio_items["release_residual_ratio_ledger"].visible_count == 1
    assert [item.drilldown_id for item in release_acceptance_report.items] == [
        "release_acceptance_certificate"
    ]
    assert (
        release_acceptance_items["release_acceptance_certificate"].visible_count
        == 2
    )
    assert {
        row.row_id
        for row in release_acceptance_items[
            "release_acceptance_certificate"
        ].visible_rows
    } == {
        "release_projection_surface_parity",
        "requirement:projection_export_visibility",
    }
    assert [item.drilldown_id for item in acceptance_receipt_report.items] == [
        "release_acceptance_certificate"
    ]
    assert (
        acceptance_receipt_items["release_acceptance_certificate"].visible_count
        == 2
    )
    assert {
        row.row_id
        for row in acceptance_receipt_items[
            "release_acceptance_certificate"
        ].visible_rows
    } == {
        "release_residual_ratio_receipts",
        "retained_gap_external_receipts",
    }

    assert batch_items["matrix_dashboard"].visible_count == 1
    assert batch_items["request_cells"].visible_count == 7
    assert batch_items["ambiguity_clarification"].visible_count == 3
    assert batch_items["user_journey_fixture"].visible_count == 16
    assert batch_items["business_capability_matrix"].visible_count == 2
    assert batch_items["boundary_guarded_completion"].visible_count == 0
    assert batch_items["residual_warning_governance"].visible_count == 0
    assert batch_items["boundary_readiness_reconciliation"].visible_count == 0
    assert batch_items["terminal_release_exception"].visible_count == 0
    assert batch_items["boundary_subject_release_dossier"].visible_count == 0
    assert batch_items["non_subject_release_trace_attribution"].visible_count == 0
    assert batch_items["release_trace_partition_guard"].visible_count == 0
    assert batch_items["release_projection_surface_parity"].visible_count == 0
    assert batch_items["boundary_subject_release_continuity"].visible_count == 0
    assert batch_items["release_closure_ledger"].visible_count == 0
    assert batch_items["boundary_maturity_release_envelope"].visible_count == 0
    assert batch_items["release_residual_ratio_ledger"].visible_count == 0
    assert batch_items["release_acceptance_certificate"].visible_count == 0
    assert batch_items["control_runtime_consistency"].visible_count == 0
    assert batch_items["input_source"].visible_count == 2
    assert batch_items["object_preflight_action"].visible_count == 5
    assert batch_items["family_fixture_depth"].visible_count == 2
    assert batch_items["count_profile"].visible_count == 2
    assert batch_items["material_schema"].visible_count == 2
    assert batch_items["material_repair_flow"].visible_count == 11
    assert batch_items["fixed_layout_profile"].visible_count == 11
    assert batch_items["report_artifact_drilldown"].visible_count == 10
    assert batch_items["delivery_preset"].visible_count == 2
    assert batch_items["delivery_execution"].visible_count == 7
    assert batch_items["formula_output_watermark"].visible_count == 3
    assert batch_items["maturity_upgrade"].visible_count == 3


def test_scene_matrix_drilldown_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_matrix_drilldown.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
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
    assert payload["counts"]["item_count"] == 37
    assert payload["counts"]["visible_row_count"] == 51
    assert payload["counts"]["source_evidence_count"] == 107
    assert payload["counts"]["ready_source_evidence_count"] == 107
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert len(payload["source_evidence"]) == payload["counts"]["source_evidence_count"]
    payload_source_ids = [item["source_id"] for item in payload["source_evidence"]]
    assert len(payload_source_ids) == len(set(payload_source_ids))
    assert (
        sum(1 for item in payload["source_evidence"] if item["status"] == "ready")
        == payload["counts"]["ready_source_evidence_count"]
    )
    assert (
        sum(1 for item in payload["source_evidence"] if item["status"] != "ready")
        == payload["counts"]["missing_source_evidence_count"]
    )
    assert {
        item["source_id"]: item["status"] for item in payload["source_evidence"]
    }["scene_matrix_drilldown_export_json_source_summary_projection"] == "ready"
    assert payload["items"][0]["drilldown_id"] == "matrix_dashboard"

    receipt_output_path = tmp_path / "scene_matrix_residual_receipts.json"
    receipt_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
            "--format",
            "json",
            "--source",
            "scene_release_residual_ratio_ledger_audit",
            "--output",
            str(receipt_output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    receipt_payload = json.loads(receipt_output_path.read_text(encoding="utf-8"))
    receipt_item = receipt_payload["items"][0]
    receipt_rows = {row["row_id"]: row for row in receipt_item["rows"]}

    assert receipt_result.stdout == ""
    assert receipt_payload["status"] == "passed"
    assert receipt_payload["counts"]["item_count"] == 1
    assert "count_delivery_receipts=4/4" in receipt_item["detail"]
    assert "maturity_l5_receipts=6/6" in receipt_item["detail"]
    assert "receipt_alignments=2/2" in receipt_rows["count_profiles"]["detail"]
    assert "count_delivery_receipts=2/2" in receipt_rows["count_profiles"]["detail"]
    assert "receipt_alignments=2/2" in receipt_rows["delivery_families"]["detail"]
    assert (
        "count_delivery_receipts=2/2"
        in receipt_rows["delivery_families"]["action_behavior_ids"]
    )
    assert "receipt_alignments=6/6" in receipt_rows["maturity_l5_blocked"]["detail"]
    assert (
        "maturity_l5_receipts=6/6"
        in receipt_rows["maturity_l5_blocked"]["action_behavior_ids"]
    )


def test_scene_matrix_drilldown_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
            "--format",
            "markdown",
            "--source",
            "scene_plugin_boundary_confirmation_audit",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Matrix Drilldown" in result.stdout
    assert "- Source evidence: 107 / 107 ready (0 missing)" in result.stdout
    assert "| Drilldown | Source | Status | Rows | Visible | Lenses | Route |" in (
        result.stdout
    )
    assert "plugin_boundary" in result.stdout
    assert "exam_ai_complex_diagram_gate" in result.stdout
    assert "scene_plugin_boundary_confirmation_audit" in result.stdout

    receipt_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
            "--format",
            "markdown",
            "--source",
            "scene_release_acceptance_certificate_audit",
            "--query",
            "acceptance_receipt_trace",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "release_residual_ratio_receipts" in receipt_result.stdout
    assert "retained_gap_external_receipts" in receipt_result.stdout

    residual_receipt_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
            "--format",
            "markdown",
            "--source",
            "scene_release_residual_ratio_ledger_audit",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "count_delivery_receipts=4/4" in residual_receipt_result.stdout
    assert "maturity_l5_receipts=6/6" in residual_receipt_result.stdout
    assert "receipt_alignments=2/2" in residual_receipt_result.stdout
    assert "count_delivery_receipts=2/2" in residual_receipt_result.stdout
    assert "receipt_alignments=6/6" in residual_receipt_result.stdout


def test_release_gate_includes_scene_matrix_drilldown(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_matrix_drilldown"]["status"] == "passed"
    assert payload["counts"]["scene_matrix_drilldown_item_count"] == 37
    assert payload["counts"]["scene_matrix_drilldown_ready_count"] == 37
    assert payload["counts"]["scene_matrix_drilldown_row_count"] == 556
    assert payload["counts"]["scene_matrix_drilldown_visible_row_count"] == 556
    assert payload["counts"]["scene_matrix_drilldown_issue_count"] == 0
    assert payload["counts"]["scene_matrix_drilldown_source_evidence_count"] == 107
    assert (
        payload["counts"]["scene_matrix_drilldown_ready_source_evidence_count"]
        == 107
    )
    assert (
        payload["counts"]["scene_matrix_drilldown_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_matrix_drilldown"]["status"] == "passed"
    assert payload["scene_matrix_drilldown"]["counts"]["item_count"] == 37


def test_scene_summary_projection_exposes_matrix_drilldown_items():
    items = {
        item.key: item for item in build_scene_matrix_drilldown_summary_items()
    }

    assert items["scene_matrix_drilldown"].value == "37/37 ready"
    assert "556 visible rows" in items["scene_matrix_drilldown"].detail
    assert "request-cell" in items["scene_matrix_drilldown"].detail
    assert "Ambiguity clarification" in items["scene_matrix_drilldown"].detail
    assert "User journey fixtures" in items["scene_matrix_drilldown"].detail
    assert "Business capability matrix" in items["scene_matrix_drilldown"].detail
    assert "external handoff contracts" in items["scene_matrix_drilldown"].detail
    assert "Boundary guarded completion" in items["scene_matrix_drilldown"].detail
    assert "Residual warning governance" in items["scene_matrix_drilldown"].detail
    assert "Boundary readiness reconciliation" in items["scene_matrix_drilldown"].detail
    assert "Terminal release exceptions" in items["scene_matrix_drilldown"].detail
    assert "Boundary subject release dossiers" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Non-subject release trace attribution" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release trace partition guard" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release projection parity" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Boundary subject release continuity" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release closure ledger" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Boundary maturity release envelope" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Retained gap exit criteria" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release residual ratio ledger" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release residual explanations" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release acceptance certificate" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "InputSourceProfile" in items["scene_matrix_drilldown"].detail
    assert "ObjectPreflight actions" in items["scene_matrix_drilldown"].detail
    assert "CountProfile" in items["scene_matrix_drilldown"].detail
    assert "MaterialSchema" in items["scene_matrix_drilldown"].detail
    assert "Material repair flow" in items["scene_matrix_drilldown"].detail
    assert "Fixed-layout profile" in items["scene_matrix_drilldown"].detail
    assert "Report/artifact drilldown" in items["scene_matrix_drilldown"].detail
    assert "DeliveryPreset" in items["scene_matrix_drilldown"].detail
    assert "Delivery execution" in items["scene_matrix_drilldown"].detail
    assert "Formula/output/watermark" in items["scene_matrix_drilldown"].detail
    assert "Control runtime consistency" in items["scene_matrix_drilldown"].detail
    assert "Maturity upgrade" in items["scene_matrix_drilldown"].detail
    assert items["scene_matrix_drilldown_sources"].value == "107/107 ready"
    assert "0 missing" in items["scene_matrix_drilldown_sources"].detail
    assert "scene_ambiguity_clarification_ui_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_user_journey_fixture_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_business_capability_matrix_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_external_handoff_contract_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_guarded_completion_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_residual_warning_governance_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_readiness_reconciliation_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_terminal_release_exception_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_subject_release_dossier_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_non_subject_release_trace_attribution_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_trace_partition_guard_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_projection_surface_parity_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_subject_release_continuity_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_closure_ledger_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_maturity_release_envelope_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_retained_gap_exit_criteria_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_residual_ratio_ledger_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_residual_explanation_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_acceptance_certificate_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_material_repair_flow_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_fixed_layout_profile_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_report_artifact_drilldown_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_control_runtime_consistency_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_word_risk_closure_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_residual_receipt_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_export_receipt_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_export_source_summary_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_export_json_source_summary_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_source_evidence_payload_consistency_tests" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_source_evidence_unique_id_tests" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_source_summary_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_source_summary_readiness_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_test_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_source_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_surface_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_path_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_evidence_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_release_marker_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_release_link_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_retained_gap_exit_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_control_runtime_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_release_metric_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_external_handoff_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_report_delivery_marker_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_requirement_dimension_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_target_plugin_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_formula_output_watermark_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_407_residual_receipt_drilldown_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_408_residual_receipt_export_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_409_residual_receipt_source_summary_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_release_gate_source_summary_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_item_row_identity_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_item_source_evidence_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_row_source_evidence_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_row_pack_family_registry_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_row_request_fixture_registry_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_row_count_delivery_registry_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_410_drilldown_source_evidence_release_summary_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_411_drilldown_source_summary_ready_total_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_412_drilldown_export_source_summary_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_413_drilldown_json_export_source_summary_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_414_drilldown_source_evidence_payload_consistency_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_415_drilldown_source_evidence_unique_id_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_416_drilldown_item_row_unique_id_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_417_drilldown_item_source_evidence_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_418_drilldown_row_source_evidence_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_419_drilldown_row_pack_family_registry_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_420_drilldown_row_request_fixture_registry_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_421_drilldown_row_count_delivery_registry_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_437_drilldown_projection_report_delivery_marker_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_438_drilldown_projection_requirement_dimension_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_439_drilldown_projection_target_plugin_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_440_drilldown_projection_formula_output_watermark_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
