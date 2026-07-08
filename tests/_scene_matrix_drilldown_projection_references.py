"""Reference builders shared by the scene matrix drilldown tests."""

from collections.abc import Callable, Iterable
from functools import lru_cache

from src.config.material_schema_registry import list_material_schemas
from src.config.plugin_manual_gate import list_plugin_manual_gates
from src.config.scene_ambiguity_clarification_ui_audit import (
    build_scene_ambiguity_clarification_ui_audit_report,
)
from src.config.scene_boundary_guarded_completion_audit import (
    build_scene_boundary_guarded_completion_audit_report,
)
from src.config.scene_boundary_maturity_release_envelope_audit import (
    build_scene_boundary_maturity_release_envelope_audit_report,
)
from src.config.scene_boundary_readiness_reconciliation_audit import (
    build_scene_boundary_readiness_reconciliation_audit_report,
)
from src.config.scene_boundary_subject_release_continuity_audit import (
    build_scene_boundary_subject_release_continuity_audit_report,
)
from src.config.scene_boundary_subject_release_dossier_audit import (
    build_scene_boundary_subject_release_dossier_audit_report,
)
from src.config.scene_control_runtime_consistency_audit import (
    build_scene_control_runtime_consistency_audit_report,
)
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
from src.config.scene_formula_output_watermark_audit import (
    build_scene_formula_output_watermark_audit_report,
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
from src.config.scene_matrix_dashboard import SCENE_MATRIX_DASHBOARD_SOURCE_IDS
from src.config.scene_matrix_drilldown import SceneMatrixDrilldownReport
from src.config.scene_non_subject_release_trace_attribution_audit import (
    build_scene_non_subject_release_trace_attribution_audit_report,
)
from src.config.scene_object_preflight_action_audit import (
    build_scene_object_preflight_action_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (
    PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS,
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_release_acceptance_certificate_audit import (
    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID,
    build_scene_release_acceptance_certificate_audit_report,
)
from src.config.scene_release_closure_ledger_audit import (
    build_scene_release_closure_ledger_audit_report,
)
from src.config.scene_release_projection_surface_parity_audit import (
    build_scene_release_projection_surface_parity_audit_report,
)
from src.config.scene_release_residual_explanation_audit import (
    build_scene_release_residual_explanation_audit_report,
)
from src.config.scene_release_residual_ratio_ledger_audit import (
    build_scene_release_residual_ratio_ledger_audit_report,
)
from src.config.scene_release_trace_partition_guard_audit import (
    build_scene_release_trace_partition_guard_audit_report,
)
from src.config.scene_report_artifact_drilldown_audit import (
    build_scene_report_artifact_drilldown_audit_report,
)
from src.config.scene_residual_warning_governance_audit import (
    build_scene_residual_warning_governance_audit_report,
)
from src.config.scene_retained_gap_exit_criteria_audit import (
    build_scene_retained_gap_exit_criteria_audit_report,
)
from src.config.scene_terminal_release_exception_audit import (
    build_scene_terminal_release_exception_audit_report,
)
from src.config.scene_word_risk_closure_audit import (
    build_scene_word_risk_closure_audit_report,
)


ProjectionReferenceKey = tuple[str, str, str]
ProjectionReferenceMap = dict[ProjectionReferenceKey, frozenset[str]]
MutableProjectionReferenceMap = dict[ProjectionReferenceKey, set[str]]
ProjectionReferenceAdder = Callable[[str, str, str, Iterable[str]], None]


def _make_projection_reference_adder(
    references: MutableProjectionReferenceMap,
    *,
    replace: bool = False,
) -> ProjectionReferenceAdder:
    def add(
        drilldown_id: str,
        row_id: str,
        field_name: str,
        reference_ids: Iterable[str],
    ) -> None:
        normalized = {reference_id for reference_id in reference_ids if reference_id}
        if not normalized:
            return
        key = (drilldown_id, row_id, field_name)
        if replace:
            references[key] = normalized
            return
        references.setdefault(key, set()).update(normalized)

    return add


def _freeze_projection_references(
    references: MutableProjectionReferenceMap,
) -> ProjectionReferenceMap:
    return {
        key: frozenset(reference_ids)
        for key, reference_ids in references.items()
    }


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
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references, replace=True)

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
    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_surface_reference_map() -> dict[tuple[str, str, str], frozenset[str]]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_path_reference_map() -> dict[tuple[str, str, str], frozenset[str]]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_evidence_reference_map() -> dict[tuple[str, str, str], frozenset[str]]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_release_marker_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_release_link_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_retained_gap_exit_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_control_runtime_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


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
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_external_handoff_contract_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_report_delivery_marker_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_requirement_dimension_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

    acceptance_report = build_scene_release_acceptance_certificate_audit_report()
    for row in acceptance_report.requirement_dimension_rows:
        add(
            "release_acceptance_certificate",
            f"requirement:{row.dimension_id}",
            "capability_ids",
            (row.dimension_id,),
        )

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_target_plugin_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)


@lru_cache(maxsize=1)
def _projection_formula_output_watermark_reference_map() -> dict[
    tuple[str, str, str], frozenset[str]
]:
    references: MutableProjectionReferenceMap = {}
    add = _make_projection_reference_adder(references)

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

    return _freeze_projection_references(references)
