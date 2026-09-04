"""Lens and source definitions for the scene matrix dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.scene_release_governance_registry import (
    SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS,
)


SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS = (
    SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS
)


SCENE_MATRIX_DASHBOARD_SOURCE_IDS: tuple[str, ...] = (
    "high_frequency_completeness_audit",
    "high_frequency_task_lexicon_audit",
    "scene_ambiguous_boundary_audit",
    "scene_ambiguity_clarification_ui_audit",
    "scene_import_handoff_audit",
    "scene_input_source_audit",
    "scene_family_subscene_audit",
    "scene_family_fixture_depth_audit",
    "scene_request_cell_registry_browser",
    "scene_user_journey_fixture_audit",
    "scene_business_capability_matrix_audit",
    "scene_boundary_capability_matrix",
    "scene_external_handoff_contract_audit",
    *SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS,
    "scene_control_consistency_audit",
    "scene_control_runtime_consistency_audit",
    "scene_count_profile_audit",
    "scene_word_risk_closure_audit",
    "scene_object_preflight_action_audit",
    "scene_plugin_boundary_confirmation_audit",
    "scene_material_schema_audit",
    "scene_material_repair_flow_audit",
    "scene_fixed_layout_profile_audit",
    "scene_report_artifact_drilldown_audit",
    "scene_delivery_preset_audit",
    "scene_delivery_preset_execution_audit",
    "scene_formula_output_watermark_audit",
    "scene_product_readiness",
    "scene_product_maturity_upgrade_audit",
)


@dataclass(frozen=True, slots=True)
class SceneMatrixDashboardLens:
    lens_id: str
    label: str
    question: str
    source_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "lens_id": self.lens_id,
            "label": self.label,
            "question": self.question,
            "source_ids": list(self.source_ids),
        }


SCENE_MATRIX_DASHBOARD_LENSES: tuple[SceneMatrixDashboardLens, ...] = (
    SceneMatrixDashboardLens(
        lens_id="user_request",
        label="User request",
        question="Can natural high-frequency user wording reach this pack?",
        source_ids=(
            "high_frequency_completeness_audit",
            "high_frequency_task_lexicon_audit",
            "scene_ambiguous_boundary_audit",
            "scene_ambiguity_clarification_ui_audit",
            "scene_request_cell_registry_browser",
            "scene_user_journey_fixture_audit",
            "scene_business_capability_matrix_audit",
            "scene_boundary_capability_matrix",
            *SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS,
        ),
    ),
    SceneMatrixDashboardLens(
        lens_id="carrier_layer",
        label="Carrier layer",
        question="Is the capability carried by a pack, family, profile, preset, or plugin gate?",
        source_ids=(
            "high_frequency_completeness_audit",
            "scene_family_subscene_audit",
            "scene_family_fixture_depth_audit",
            "scene_business_capability_matrix_audit",
            "scene_boundary_capability_matrix",
            *SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS,
        ),
    ),
    SceneMatrixDashboardLens(
        lens_id="fact_source",
        label="Fact source",
        question="Is the machine-readable source of truth represented by axes, schemas, profiles, or presets?",
        source_ids=(
            "high_frequency_completeness_audit",
            "scene_family_subscene_audit",
            "scene_family_fixture_depth_audit",
            "scene_count_profile_audit",
            "scene_input_source_audit",
            "scene_material_schema_audit",
            "scene_material_repair_flow_audit",
            "scene_fixed_layout_profile_audit",
            "scene_report_artifact_drilldown_audit",
            "scene_delivery_preset_audit",
            "scene_delivery_preset_execution_audit",
            "scene_formula_output_watermark_audit",
            "scene_business_capability_matrix_audit",
            "scene_boundary_capability_matrix",
            "scene_product_readiness",
        ),
    ),
    SceneMatrixDashboardLens(
        lens_id="workflow",
        label="Workflow",
        question="Are reusable workflow archetypes and capability axes explicit?",
        source_ids=("high_frequency_completeness_audit",),
    ),
    SceneMatrixDashboardLens(
        lens_id="word_risk",
        label="Word risk",
        question="Are the Word/OOXML risk surfaces visible and closed?",
        source_ids=(
            "high_frequency_completeness_audit",
            "scene_word_risk_closure_audit",
            "scene_object_preflight_action_audit",
            "scene_fixed_layout_profile_audit",
        ),
    ),
    SceneMatrixDashboardLens(
        lens_id="control_contract",
        label="Control contract",
        question="Do scene controls reuse the template-management control language where required?",
        source_ids=(
            "scene_control_consistency_audit",
            "scene_control_runtime_consistency_audit",
            "scene_fixed_layout_profile_audit",
            "scene_formula_output_watermark_audit",
        ),
    ),
    SceneMatrixDashboardLens(
        lens_id="boundary",
        label="Boundary",
        question="Are plugin, manual, ambiguous, negative, and non-core promises explicit?",
        source_ids=(
            "high_frequency_completeness_audit",
            "scene_family_subscene_audit",
            "scene_request_cell_registry_browser",
            "scene_ambiguous_boundary_audit",
            "scene_ambiguity_clarification_ui_audit",
            "scene_plugin_boundary_confirmation_audit",
            "scene_external_handoff_contract_audit",
            *SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS,
            "scene_import_handoff_audit",
            "scene_input_source_audit",
            "scene_user_journey_fixture_audit",
            "scene_business_capability_matrix_audit",
            "scene_boundary_capability_matrix",
            "scene_product_readiness",
        ),
    ),
    SceneMatrixDashboardLens(
        lens_id="evidence_chain",
        label="Evidence chain",
        question="Can request cells be traced to fixtures, report anchors, tests, and the release gate?",
        source_ids=(
            "high_frequency_completeness_audit",
            "scene_request_cell_registry_browser",
            "scene_ambiguity_clarification_ui_audit",
            "scene_family_fixture_depth_audit",
            "scene_import_handoff_audit",
            "scene_count_profile_audit",
            "scene_input_source_audit",
            "scene_word_risk_closure_audit",
            "scene_object_preflight_action_audit",
            "scene_user_journey_fixture_audit",
            "scene_control_runtime_consistency_audit",
            "scene_material_schema_audit",
            "scene_material_repair_flow_audit",
            "scene_fixed_layout_profile_audit",
            "scene_report_artifact_drilldown_audit",
            "scene_delivery_preset_audit",
            "scene_delivery_preset_execution_audit",
            "scene_formula_output_watermark_audit",
            "scene_business_capability_matrix_audit",
            "scene_boundary_capability_matrix",
            "scene_external_handoff_contract_audit",
            *SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS,
        ),
    ),
    SceneMatrixDashboardLens(
        lens_id="product_readiness",
        label="Product readiness",
        question="Is static closure separated from user-facing product maturity?",
        source_ids=(
            "scene_product_readiness",
            "scene_product_maturity_upgrade_audit",
            "scene_material_repair_flow_audit",
            "scene_fixed_layout_profile_audit",
            "scene_report_artifact_drilldown_audit",
            "scene_user_journey_fixture_audit",
            "scene_ambiguity_clarification_ui_audit",
            "scene_business_capability_matrix_audit",
            "scene_boundary_capability_matrix",
            "scene_external_handoff_contract_audit",
            *SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS,
        ),
    ),
)

SCENE_MATRIX_DASHBOARD_LENS_IDS: tuple[str, ...] = tuple(
    lens.lens_id for lens in SCENE_MATRIX_DASHBOARD_LENSES
)


__all__ = [
    "SCENE_MATRIX_DASHBOARD_LENSES",
    "SCENE_MATRIX_DASHBOARD_LENS_IDS",
    "SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS",
    "SCENE_MATRIX_DASHBOARD_SOURCE_IDS",
    "SceneMatrixDashboardLens",
]
