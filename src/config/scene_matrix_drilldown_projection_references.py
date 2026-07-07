"""Projection reference maps for scene matrix drilldown audits."""

from __future__ import annotations

from functools import lru_cache

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
from src.config.scene_material_repair_flow_audit import (
    build_scene_material_repair_flow_audit_report,
)
from src.config.scene_matrix_dashboard_lenses import SCENE_MATRIX_DASHBOARD_SOURCE_IDS
from src.config.scene_matrix_drilldown_models import SceneMatrixDrilldownReport
from src.config.scene_non_subject_release_trace_attribution_audit import (
    build_scene_non_subject_release_trace_attribution_audit_report,
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

    terminal_report = build_scene_terminal_release_exception_audit_report()
    for row in terminal_report.rows:
        add(
            "terminal_release_exception",
            row.exception_id,
            "capability_ids",
            row.source_ids,
        )

    non_subject_report = (
        build_scene_non_subject_release_trace_attribution_audit_report()
    )
    for row in non_subject_report.rows:
        add(
            "non_subject_release_trace_attribution",
            row.trace_id,
            "capability_ids",
            (row.surface_source_id,),
        )

    parity_report = build_scene_release_projection_surface_parity_audit_report()
    for row in parity_report.rows:
        add(
            "release_projection_surface_parity",
            row.projection_id,
            "capability_ids",
            (row.audit_source_id,),
        )

    closure_report = build_scene_release_closure_ledger_audit_report()
    for row in closure_report.rows:
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


def _release_residual_receipt_action_ids(row: object) -> tuple[str, ...]:
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
            _release_residual_receipt_action_ids(row),
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


__all__ = [
    "_projection_control_runtime_reference_map",
    "_projection_evidence_reference_map",
    "_projection_external_handoff_contract_reference_map",
    "_projection_formula_output_watermark_reference_map",
    "_projection_path_reference_map",
    "_projection_release_link_reference_map",
    "_projection_release_marker_reference_map",
    "_projection_release_metric_reference_map",
    "_projection_report_delivery_marker_reference_map",
    "_projection_requirement_dimension_reference_map",
    "_projection_retained_gap_exit_reference_map",
    "_projection_source_reference_ids",
    "_projection_source_reference_map",
    "_projection_surface_reference_map",
    "_projection_target_plugin_reference_map",
    "_release_residual_receipt_action_ids",
]
