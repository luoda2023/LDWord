"""Release acceptance-certificate audit for the high-level scene matrix.

N2.394 turns the current release state into a single certificate surface.  It
does not promote boundary subjects to Green/L5; it proves that the final
release projection, closure ledger, retained-boundary envelopes, and residual
ratio governance are all present, ready, exported, and visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.scene_source_evidence import (
    scan_scene_source_markers,
    scene_source_marker_issue_message,
)
from src.config.scene_boundary_guarded_completion_audit import (
    build_scene_boundary_guarded_completion_audit_report,
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
from src.config.scene_high_frequency_completeness_audit import (
    build_high_frequency_completeness_audit_report,
)
from src.config.scene_boundary_capability_matrix import (
    build_scene_boundary_capability_audit_report,
)
from src.config.scene_business_capability_matrix_audit import (
    build_scene_business_capability_matrix_audit_report,
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
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_delivery_preset_execution_audit import (
    build_scene_delivery_preset_execution_audit_report,
)
from src.config.scene_fixed_layout_profile_audit import (
    build_scene_fixed_layout_profile_audit_report,
)
from src.config.scene_formula_output_watermark_audit import (
    build_scene_formula_output_watermark_audit_report,
)
from src.config.scene_high_frequency_task_lexicon_audit import (
    build_high_frequency_task_lexicon_audit_report,
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
from src.config.scene_boundary_maturity_release_envelope_audit import (
    build_scene_boundary_maturity_release_envelope_audit_report,
)
from src.config.scene_non_subject_release_trace_attribution_audit import (
    build_scene_non_subject_release_trace_attribution_audit_report,
)
from src.config.scene_object_preflight_action_audit import (
    build_scene_object_preflight_action_audit_report,
)
from src.config.scene_report_artifact_drilldown_audit import (
    build_scene_report_artifact_drilldown_audit_report,
)
from src.config.scene_user_journey_fixture_audit import (
    build_scene_user_journey_fixture_audit_report,
)
from src.config.scene_word_risk_closure_audit import (
    build_scene_word_risk_closure_audit_report,
)
from src.config.scene_release_closure_ledger_audit import (
    build_scene_release_closure_ledger_audit_report,
)
from src.config.scene_release_governance_registry import (
    SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
    SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID,
    scene_release_governance_report_pairs,
)
from src.config.scene_release_projection_surface_parity_audit import (
    build_scene_release_projection_surface_parity_audit_report,
)
from src.config.scene_release_residual_ratio_ledger_audit import (
    build_scene_release_residual_ratio_ledger_audit_report,
)
from src.config.scene_release_residual_explanation_audit import (
    build_scene_release_residual_explanation_audit_report,
)
from src.config.scene_release_trace_partition_guard_audit import (
    build_scene_release_trace_partition_guard_audit_report,
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


SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "component_report_passed",
    "expected_release_count",
    "dashboard_projection",
    "release_gate_projection",
    "drilldown_projection",
    "summary_projection",
    "export_script",
    "workflow_test",
    "closure_doc",
)


@dataclass(frozen=True, slots=True)
class SceneReleaseAcceptanceCertificateSpec:
    certificate_id: str
    source_id: str
    observed_numerator_attr: str
    observed_denominator_attr: str
    expected_numerator: int
    expected_denominator: int
    summary: str


SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_SPECS: tuple[
    SceneReleaseAcceptanceCertificateSpec, ...
] = (
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="high_frequency_coverage",
        source_id="high_frequency_completeness_audit",
        observed_numerator_attr="ready_pack_count",
        observed_denominator_attr="pack_count",
        expected_numerator=12,
        expected_denominator=12,
        summary=(
            "Every high-frequency scene pack has request-cell, fixture, "
            "workflow, Word-risk, and report evidence."
        ),
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="release_projection_surface_parity",
        source_id="scene_release_projection_surface_parity_audit",
        observed_numerator_attr="ready_projection_count",
        observed_denominator_attr="projection_count",
        expected_numerator=13,
        expected_denominator=13,
        summary="Every release audit has a public projection surface.",
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="release_closure_ledger",
        source_id="scene_release_closure_ledger_audit",
        observed_numerator_attr="ready_stage_count",
        observed_denominator_attr="stage_count",
        expected_numerator=13,
        expected_denominator=13,
        summary="Every release stage is ordered and connected to its evidence.",
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="boundary_maturity_release_envelope",
        source_id="scene_boundary_maturity_release_envelope_audit",
        observed_numerator_attr="ready_envelope_count",
        observed_denominator_attr="envelope_count",
        expected_numerator=6,
        expected_denominator=6,
        summary="Every retained Blue/Boundary blocker has a release envelope.",
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="release_residual_ratio_ledger",
        source_id="scene_release_residual_ratio_ledger_audit",
        observed_numerator_attr="published_ratio_count",
        observed_denominator_attr="ratio_count",
        expected_numerator=3,
        expected_denominator=3,
        summary="Every non-full terminal release ratio is published with evidence.",
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="release_residual_ratio_exit_criteria",
        source_id="scene_release_residual_ratio_ledger_audit",
        observed_numerator_attr="retained_gap_exit_criteria_link_count",
        observed_denominator_attr="release_envelope_link_count",
        expected_numerator=10,
        expected_denominator=10,
        summary=(
            "Every retained residual ratio envelope has a matching exit "
            "criteria link."
        ),
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="release_residual_ratio_receipts",
        source_id="scene_release_residual_ratio_ledger_audit",
        observed_numerator_attr="retained_gap_receipt_alignment_link_count",
        observed_denominator_attr="retained_gap_exit_criteria_link_count",
        expected_numerator=10,
        expected_denominator=10,
        summary=(
            "Every residual-ratio exit criteria link retains the external "
            "receipt evidence from its retained gap."
        ),
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="count_delivery_boundary_alignment",
        source_id="scene_release_residual_ratio_ledger_audit",
        observed_numerator_attr="count_delivery_boundary_alignment_count",
        observed_denominator_attr="count_delivery_boundary_link_count",
        expected_numerator=4,
        expected_denominator=4,
        summary=(
            "The CountProfile and DeliveryPreset residual ratios share the "
            "same retained boundary and exit criteria ID set."
        ),
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="maturity_l5_blocker_alignment",
        source_id="scene_release_residual_ratio_ledger_audit",
        observed_numerator_attr="maturity_l5_blocker_alignment_count",
        observed_denominator_attr="maturity_l5_blocker_release_envelope_count",
        expected_numerator=6,
        expected_denominator=6,
        summary=(
            "Every retained L5 maturity blocker is aligned to the same "
            "release envelope and retained-gap exit criteria ID set."
        ),
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="release_residual_boundary_scope_alignment",
        source_id="scene_release_residual_ratio_ledger_audit",
        observed_numerator_attr="boundary_scope_alignment_count",
        observed_denominator_attr="boundary_scope_link_count",
        expected_numerator=6,
        expected_denominator=6,
        summary=(
            "Every retained residual boundary scope exposes local capability "
            "evidence and excluded core claims."
        ),
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="release_residual_explanation",
        source_id="scene_release_residual_explanation_audit",
        observed_numerator_attr="covered_count",
        observed_denominator_attr="row_count",
        expected_numerator=14,
        expected_denominator=14,
        summary="Every exposed residual release reading is governed and explained.",
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="retained_gap_exit_criteria",
        source_id="scene_retained_gap_exit_criteria_audit",
        observed_numerator_attr="release_allowed_count",
        observed_denominator_attr="criteria_count",
        expected_numerator=6,
        expected_denominator=6,
        summary="Every retained gap has release limits and explicit exit criteria.",
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="release_governance_export_scripts",
        source_id=SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID,
        observed_numerator_attr="ready_export_script_count",
        observed_denominator_attr="report_count",
        expected_numerator=len(SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS),
        expected_denominator=len(SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS),
        summary=(
            "Every release governance report exposes export_script as ready "
            "source evidence."
        ),
    ),
    SceneReleaseAcceptanceCertificateSpec(
        certificate_id="retained_gap_external_receipts",
        source_id="scene_retained_gap_exit_criteria_audit",
        observed_numerator_attr="external_receipt_alignment_count",
        observed_denominator_attr="criteria_count",
        expected_numerator=6,
        expected_denominator=6,
        summary=(
            "Every retained gap exit path has the external receipt evidence "
            "declared by the boundary capability matrix."
        ),
    ),
)

SCENE_RELEASE_ACCEPTANCE_RECEIPT_CERTIFICATE_IDS: tuple[str, ...] = (
    "release_residual_ratio_receipts",
    "retained_gap_external_receipts",
)


@dataclass(frozen=True, slots=True)
class SceneReleaseRequirementDimensionSpec:
    dimension_id: str
    label: str
    requirement: str
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


SCENE_RELEASE_REQUIREMENT_DIMENSION_SPECS: tuple[
    SceneReleaseRequirementDimensionSpec, ...
] = (
    SceneReleaseRequirementDimensionSpec(
        dimension_id="high_frequency_scene_coverage",
        label="High-frequency scene coverage",
        requirement=(
            "The scenario matrix must not miss high-frequency scene packs or "
            "hide them behind generic custom configuration."
        ),
        source_ids=("high_frequency_completeness_audit",),
        evidence_ids=("12 high-frequency packs", "request/fixture/report coverage"),
    ),
    SceneReleaseRequirementDimensionSpec(
        dimension_id="natural_request_to_scene_route",
        label="Natural request routing",
        requirement=(
            "User wording, request cells, journeys, and ambiguous/manual "
            "boundaries must route to explicit scene carriers."
        ),
        source_ids=(
            "high_frequency_task_lexicon_audit",
            "scene_user_journey_fixture_audit",
        ),
        evidence_ids=("task lexicon", "request cells", "user journeys"),
    ),
    SceneReleaseRequirementDimensionSpec(
        dimension_id="scene_board_control_style_consistency",
        label="Scene control style consistency",
        requirement=(
            "Scene controls must keep the same canonical control contract, "
            "pairing, disabled-state, unit, and runtime semantics as template "
            "management."
        ),
        source_ids=(
            "scene_control_consistency_audit",
            "scene_control_runtime_consistency_audit",
        ),
        evidence_ids=("control contracts", "runtime control consumers"),
    ),
    SceneReleaseRequirementDimensionSpec(
        dimension_id="input_material_scope",
        label="Input and material scope",
        requirement=(
            "Processing scope, input profiles, material schemas, and repair "
            "flows must be explicit instead of being implicit UI-only choices."
        ),
        source_ids=(
            "scene_input_source_audit",
            "scene_material_schema_audit",
            "scene_material_repair_flow_audit",
        ),
        evidence_ids=("input packs", "material families", "repair flows"),
    ),
    SceneReleaseRequirementDimensionSpec(
        dimension_id="word_ooxml_risk_scope",
        label="Word/OOXML risk scope",
        requirement=(
            "Word XML risk surfaces, object preflight, fixed-layout row-height "
            "handling, and count profiles must be visible and release-gated."
        ),
        source_ids=(
            "scene_word_risk_closure_audit",
            "scene_object_preflight_action_audit",
            "scene_fixed_layout_profile_audit",
            "scene_count_profile_audit",
        ),
        evidence_ids=("Word risks", "object preflight", "fixed layout", "counts"),
    ),
    SceneReleaseRequirementDimensionSpec(
        dimension_id="formula_output_watermark_scene_ownership",
        label="Formula/output/watermark ownership",
        requirement=(
            "Formula, output, and watermark parameters must be treated as "
            "scene capabilities with owner layers, contracts, execution "
            "consumers, and plugin/manual boundaries."
        ),
        source_ids=("scene_formula_output_watermark_audit",),
        evidence_ids=("formula capability", "output capability", "watermark capability"),
    ),
    SceneReleaseRequirementDimensionSpec(
        dimension_id="delivery_artifact_chain",
        label="Delivery artifact chain",
        requirement=(
            "Delivery presets must drive runtime outputs, reports, structured "
            "intermediates, artifact drilldown, and content-visibility rules."
        ),
        source_ids=(
            "scene_delivery_preset_audit",
            "scene_delivery_preset_execution_audit",
            "scene_report_artifact_drilldown_audit",
        ),
        evidence_ids=("delivery presets", "execution channels", "artifact drilldowns"),
    ),
    SceneReleaseRequirementDimensionSpec(
        dimension_id="business_family_boundary_catalog",
        label="Business family and boundary catalog",
        requirement=(
            "High-frequency business capabilities, planned families, "
            "professional boundaries, and import/AI boundaries must be "
            "cataloged with explicit local scope and excluded claims."
        ),
        source_ids=(
            "scene_business_capability_matrix_audit",
            "scene_boundary_capability_matrix",
        ),
        evidence_ids=("business capabilities", "boundary capabilities"),
    ),
    SceneReleaseRequirementDimensionSpec(
        dimension_id="residual_boundary_release_governance",
        label="Residual boundary governance",
        requirement=(
            "Retained gaps, external receipts, L5 blockers, residual ratios, "
            "explanations, boundary scopes, and acceptance certificates must "
            "be governed without promoting boundary subjects to Green/L5."
        ),
        source_ids=(
            "scene_boundary_maturity_release_envelope_audit",
            "scene_retained_gap_exit_criteria_audit",
            "scene_release_residual_ratio_ledger_audit",
            "scene_release_residual_explanation_audit",
        ),
        evidence_ids=(
            "release envelopes",
            "exit criteria",
            "external receipts",
            "residual ratio receipt alignment",
            "residual explanations",
            "acceptance certificate rows",
        ),
    ),
    SceneReleaseRequirementDimensionSpec(
        dimension_id="projection_export_visibility",
        label="Projection and export visibility",
        requirement=(
            "Release proof must reach release gate, dashboard, drilldown, "
            "summary projection, export scripts, workflow, and closure docs."
        ),
        source_ids=(
            "scene_release_projection_surface_parity_audit",
            SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID,
        ),
        evidence_ids=("projection surfaces", "export scripts", "self evidence"),
    ),
)

SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "release_acceptance_certificate_registry",
        "src/config/scene_release_acceptance_certificate_audit.py",
        (
            "SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_SPECS",
            "SCENE_RELEASE_REQUIREMENT_DIMENSION_SPECS",
            "requirement_dimension_rows",
            "component_report_passed",
            "high_frequency_coverage",
            "high_frequency_scene_coverage",
            "release_acceptance_certificate",
            "release_residual_ratio_exit_criteria",
            "release_residual_ratio_receipts",
            "SCENE_RELEASE_ACCEPTANCE_RECEIPT_CERTIFICATE_IDS",
            "count_delivery_boundary_alignment",
            "maturity_l5_blocker_alignment",
            "release_residual_boundary_scope_alignment",
            "release_residual_explanation",
            "release_governance_export_scripts",
            "retained_gap_exit_criteria",
            "retained_gap_external_receipts",
        ),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
            "high_frequency_coverage=",
            "count/delivery boundary links aligned",
            "L5 blockers aligned",
            "boundary scopes guarded",
            "receipt alignments",
            "receipt certificates",
            "requirement dimensions",
            "release_acceptance_certificate_ready_count",
            "release_acceptance_certificate_ready_receipt_count",
            "release_acceptance_certificate_ready_requirement_dimension_count",
            "release_acceptance_certificate",
        ),
    ),
    (
        "scene_matrix_drilldown",
        "src/config/scene_matrix_drilldown_release_items.py",
        (
            SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
            "release_acceptance_certificate",
            "requirement_dimension_rows",
            "requirement_dimension_trace",
            "row.certificate_id",
        ),
    ),
    (
        "summary_projection",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            "high_frequency_coverage=",
            "count/delivery boundary links aligned",
            "L5 blockers aligned",
            "boundary scopes guarded",
            "residual ratio receipts",
            "retained gap receipts",
            "receipt certificates",
            "requirement dimensions",
            "release_acceptance_certificate_ready_count",
            "release_acceptance_certificate_ready_receipt_count",
            "release acceptance certificate",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
            "high_frequency_coverage=",
            "count_delivery_alignment=",
            "maturity_l5_alignment=",
            "boundary_scope_alignment=",
            "retained_gap_receipts=",
            "residual_ratio_receipts=",
            "acceptance_receipts=",
            "requirement_dimensions=",
            "scene_release_acceptance_certificate_ready_requirement_dimension_count",
            "scene_release_acceptance_certificate_ready_count",
            "scene_release_acceptance_certificate_ready_receipt_count",
            "acceptance_certificate=",
            "acceptance_evidence=",
            "scene_release_governance_export_script_ready_count",
            "release_export_scripts=",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_release_acceptance_certificate_audit.py",
        (
            "run_registered_scene_audit_export",
            SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
            "Certificates ready",
            "Receipt certificates ready",
            "Requirement dimensions ready",
            "requirement_dimension_rows",
            "row.certificate_id",
            "row.observed_ratio",
            "row.expected_ratio",
            "markdown",
        ),
    ),
    (
        "workflow",
        ".github/workflows/scene-matrix-release-gate.yml",
        ("tests/test_scene_release_acceptance_certificate_audit.py",),
    ),
    (
        "acceptance_certificate_test",
        "tests/test_scene_release_acceptance_certificate_audit.py",
        (
            "scene_release_acceptance_certificate_audit",
            "Certificates ready: 14/14",
            "Requirement dimensions ready: 10/10",
            "high_frequency_coverage",
            "high_frequency_scene_coverage",
            "count_delivery_boundary_alignment",
            "maturity_l5_blocker_alignment",
            "release_residual_boundary_scope_alignment",
            "release_residual_ratio_receipts",
            "retained_gap_external_receipts",
            "release_governance_export_scripts",
            "Receipt certificates ready: 2/2",
            "requirement_dimensions=10/10",
            "retained_gap_receipts=6/6",
            "residual_ratio_receipts=10/10",
            "acceptance_receipts=2/2",
            "release_export_scripts=15/15 ready",
            "build_scene_matrix_release_gate_payload",
        ),
    ),
    (
        "release_shell",
        "tests/test_scene_matrix_release_workflow.py",
        (
            "export_scene_release_acceptance_certificate_audit.py",
            "test_scene_release_acceptance_certificate_audit.py",
        ),
    ),
    (
        "n2_394_plan",
        "docs/audits/高层场景能力矩阵N2_394发布验收证书闭环_2026-06-24.md",
        (
            "N2.394",
            "release_acceptance_certificate",
            "12/12",
            "count_delivery_boundary_alignment",
            "maturity_l5_blocker_alignment",
            "release_residual_boundary_scope_alignment",
            "release_governance_export_scripts",
            "15/15",
            "self-surface evidence",
        ),
    ),
    (
        "n2_395_requirement_trace_plan",
        "docs/audits/scene_release_acceptance_requirement_trace_N2_395_2026-06-25.md",
        (
            "N2.395",
            "SCENE_RELEASE_REQUIREMENT_DIMENSION_SPECS",
            "requirement_dimensions=10/10",
            "high_frequency_scene_coverage",
            "formula_output_watermark_scene_ownership",
            "projection_export_visibility",
        ),
    ),
    (
        "n2_397_retained_gap_receipt_plan",
        "docs/audits/scene_retained_gap_receipt_alignment_N2_397_2026-06-25.md",
        (
            "N2.397",
            "retained_gap_receipt_alignment=6/6",
            "external_receipt_targets=8",
        ),
    ),
    (
        "n2_398_residual_ratio_receipt_plan",
        "docs/audits/scene_release_residual_ratio_receipt_alignment_N2_398_2026-06-25.md",
        (
            "N2.398",
            "residual_ratio_receipt_alignment=10/10",
            "retained_gap_receipts=6/6",
        ),
    ),
    (
        "n2_399_projection_trace_plan",
        "docs/audits/scene_release_residual_ratio_projection_trace_N2_399_2026-06-25.md",
        (
            "N2.399",
            "residual_ratio_receipt_alignment_trace",
            "release_residual_ratio_ledger",
        ),
    ),
    (
        "n2_400_acceptance_receipt_plan",
        "docs/audits/scene_release_acceptance_receipt_trace_N2_400_2026-06-25.md",
        (
            "N2.400",
            "acceptance_certificate=14/14",
            "acceptance_evidence=15/15",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneReleaseAcceptanceCertificateIssue:
    certificate_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "certificate_id": self.certificate_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseAcceptanceCertificateSourceEvidence:
    source_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseRequirementDimensionRow:
    dimension_id: str
    label: str
    requirement: str
    observed_numerator: int
    observed_denominator: int
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return "dimension_ready" if not self.issue_ids else "dimension_gap"

    @property
    def is_ready(self) -> bool:
        return self.status == "dimension_ready"

    @property
    def observed_ratio(self) -> str:
        return f"{self.observed_numerator}/{self.observed_denominator}"

    def to_payload(self) -> dict[str, object]:
        return {
            "dimension_id": self.dimension_id,
            "label": self.label,
            "requirement": self.requirement,
            "observed_numerator": self.observed_numerator,
            "observed_denominator": self.observed_denominator,
            "observed_ratio": self.observed_ratio,
            "source_ids": list(self.source_ids),
            "evidence_ids": list(self.evidence_ids),
            "status": self.status,
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseGovernanceExportScriptEvidenceRow:
    report_id: str
    payload_source_id: str
    export_script_status: str
    source_evidence_count: int

    @property
    def is_ready(self) -> bool:
        return (
            self.payload_source_id == self.report_id
            and self.export_script_status == "ready"
        )


@dataclass(frozen=True, slots=True)
class SceneReleaseGovernanceExportScriptEvidenceReport:
    rows: tuple[SceneReleaseGovernanceExportScriptEvidenceRow, ...]

    @property
    def status(self) -> str:
        return "passed" if self.ready_export_script_count == self.report_count else "failed"

    @property
    def report_count(self) -> int:
        return len(self.rows)

    @property
    def ready_export_script_count(self) -> int:
        return sum(1 for row in self.rows if row.is_ready)


@dataclass(frozen=True, slots=True)
class SceneReleaseAcceptanceCertificateRow:
    certificate_id: str
    source_id: str
    observed_numerator: int
    observed_denominator: int
    expected_numerator: int
    expected_denominator: int
    status: str
    summary: str
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status == "certificate_ready"

    @property
    def observed_ratio(self) -> str:
        return f"{self.observed_numerator}/{self.observed_denominator}"

    @property
    def expected_ratio(self) -> str:
        return f"{self.expected_numerator}/{self.expected_denominator}"

    def to_payload(self) -> dict[str, object]:
        return {
            "certificate_id": self.certificate_id,
            "source_id": self.source_id,
            "observed_numerator": self.observed_numerator,
            "observed_denominator": self.observed_denominator,
            "observed_ratio": self.observed_ratio,
            "expected_numerator": self.expected_numerator,
            "expected_denominator": self.expected_denominator,
            "expected_ratio": self.expected_ratio,
            "status": self.status,
            "summary": self.summary,
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseAcceptanceCertificateAuditReport:
    rows: tuple[SceneReleaseAcceptanceCertificateRow, ...]
    requirement_dimension_rows: tuple[SceneReleaseRequirementDimensionRow, ...]
    issues: tuple[SceneReleaseAcceptanceCertificateIssue, ...]
    source_evidence: tuple[SceneReleaseAcceptanceCertificateSourceEvidence, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def certificate_count(self) -> int:
        return len(self.rows)

    @property
    def ready_certificate_count(self) -> int:
        return sum(1 for row in self.rows if row.is_ready)

    @property
    def receipt_certificate_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.certificate_id
            in SCENE_RELEASE_ACCEPTANCE_RECEIPT_CERTIFICATE_IDS
        )

    @property
    def ready_receipt_certificate_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.certificate_id
            in SCENE_RELEASE_ACCEPTANCE_RECEIPT_CERTIFICATE_IDS
            and row.is_ready
        )

    @property
    def component_report_count(self) -> int:
        return len(self.rows)

    @property
    def requirement_dimension_count(self) -> int:
        return len(self.requirement_dimension_rows)

    @property
    def ready_requirement_dimension_count(self) -> int:
        return sum(row.is_ready for row in self.requirement_dimension_rows)

    @property
    def expected_count_match_count(self) -> int:
        return sum(
            1 for row in self.rows if "unexpected_release_count" not in row.issue_ids
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def source_evidence_count(self) -> int:
        return len(self.source_evidence)

    @property
    def ready_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status == "ready")

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
            "required_evidence_ids": list(
                SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "certificate_count": self.certificate_count,
                "ready_certificate_count": self.ready_certificate_count,
                "receipt_certificate_count": self.receipt_certificate_count,
                "ready_receipt_certificate_count": (
                    self.ready_receipt_certificate_count
                ),
                "component_report_count": self.component_report_count,
                "requirement_dimension_count": self.requirement_dimension_count,
                "ready_requirement_dimension_count": (
                    self.ready_requirement_dimension_count
                ),
                "expected_count_match_count": self.expected_count_match_count,
                "source_evidence_count": self.source_evidence_count,
                "ready_source_evidence_count": self.ready_source_evidence_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "requirement_dimension_rows": [
                row.to_payload() for row in self.requirement_dimension_rows
            ],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [evidence.to_payload() for evidence in self.source_evidence],
        }


def build_scene_release_acceptance_certificate_audit_report(
    *,
    project_root: Path | str | None = None,
) -> SceneReleaseAcceptanceCertificateAuditReport:
    root = Path(project_root) if project_root is not None else Path.cwd()
    source_evidence = _source_evidence(root)
    reports = _component_reports(root, acceptance_source_evidence=source_evidence)
    rows = tuple(
        _row_for_spec(spec, reports)
        for spec in SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_SPECS
    )
    requirement_dimension_rows = _requirement_dimension_rows(reports, rows)
    issues: list[SceneReleaseAcceptanceCertificateIssue] = []
    for row in rows:
        issues.extend(
            SceneReleaseAcceptanceCertificateIssue(
                row.certificate_id,
                issue_id,
                f"Release acceptance certificate {row.certificate_id} failed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    for row in requirement_dimension_rows:
        issues.extend(
            SceneReleaseAcceptanceCertificateIssue(
                row.dimension_id,
                issue_id,
                f"Release requirement dimension {row.dimension_id} failed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneReleaseAcceptanceCertificateAuditReport(
        rows=rows,
        requirement_dimension_rows=requirement_dimension_rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
    )


def audit_scene_release_acceptance_certificate_report(
    report: SceneReleaseAcceptanceCertificateAuditReport | None = None,
) -> tuple[SceneReleaseAcceptanceCertificateIssue, ...]:
    current = report or build_scene_release_acceptance_certificate_audit_report()
    return current.issues


def _component_reports(
    root: Path,
    *,
    acceptance_source_evidence: (
        tuple[SceneReleaseAcceptanceCertificateSourceEvidence, ...]
    ),
) -> dict[str, object]:
    high_frequency_completeness_report = (
        build_high_frequency_completeness_audit_report()
    )
    high_frequency_task_lexicon_report = (
        build_high_frequency_task_lexicon_audit_report()
    )
    user_journey_fixture_report = build_scene_user_journey_fixture_audit_report(
        project_root=root
    )
    control_consistency_report = build_scene_control_consistency_audit_report(
        project_root=root
    )
    control_runtime_consistency_report = (
        build_scene_control_runtime_consistency_audit_report(project_root=root)
    )
    input_source_report = build_scene_input_source_audit_report(project_root=root)
    material_schema_report = build_scene_material_schema_audit_report(
        project_root=root
    )
    material_repair_flow_report = build_scene_material_repair_flow_audit_report(
        project_root=root
    )
    word_risk_closure_report = build_scene_word_risk_closure_audit_report(
        project_root=root
    )
    object_preflight_action_report = (
        build_scene_object_preflight_action_audit_report(project_root=root)
    )
    fixed_layout_profile_report = build_scene_fixed_layout_profile_audit_report(
        project_root=root
    )
    count_profile_report = build_scene_count_profile_audit_report(project_root=root)
    formula_output_watermark_report = (
        build_scene_formula_output_watermark_audit_report(project_root=root)
    )
    delivery_preset_report = build_scene_delivery_preset_audit_report(
        project_root=root
    )
    delivery_preset_execution_report = (
        build_scene_delivery_preset_execution_audit_report(project_root=root)
    )
    report_artifact_drilldown_report = (
        build_scene_report_artifact_drilldown_audit_report(project_root=root)
    )
    business_capability_matrix_report = (
        build_scene_business_capability_matrix_audit_report(project_root=root)
    )
    boundary_capability_matrix_report = (
        build_scene_boundary_capability_audit_report(project_root=root)
    )
    boundary_guarded_completion_report = (
        build_scene_boundary_guarded_completion_audit_report(project_root=root)
    )
    residual_warning_governance_report = (
        build_scene_residual_warning_governance_audit_report(project_root=root)
    )
    boundary_readiness_reconciliation_report = (
        build_scene_boundary_readiness_reconciliation_audit_report(
            project_root=root
        )
    )
    terminal_release_exception_report = (
        build_scene_terminal_release_exception_audit_report(project_root=root)
    )
    boundary_subject_release_dossier_report = (
        build_scene_boundary_subject_release_dossier_audit_report(
            project_root=root
        )
    )
    non_subject_release_trace_attribution_report = (
        build_scene_non_subject_release_trace_attribution_audit_report(
            project_root=root
        )
    )
    release_trace_partition_guard_report = (
        build_scene_release_trace_partition_guard_audit_report(project_root=root)
    )
    release_projection_surface_parity_report = (
        build_scene_release_projection_surface_parity_audit_report(
            project_root=root
        )
    )
    boundary_subject_release_continuity_report = (
        build_scene_boundary_subject_release_continuity_audit_report(
            project_root=root
        )
    )
    release_closure_ledger_report = build_scene_release_closure_ledger_audit_report(
        project_root=root
    )
    boundary_maturity_release_envelope_report = (
        build_scene_boundary_maturity_release_envelope_audit_report(
            project_root=root
        )
    )
    release_residual_ratio_ledger_report = (
        build_scene_release_residual_ratio_ledger_audit_report(project_root=root)
    )
    retained_gap_exit_criteria_report = (
        build_scene_retained_gap_exit_criteria_audit_report(
            project_root=root,
            boundary_maturity_release_envelope_report=(
                boundary_maturity_release_envelope_report
            ),
        )
    )
    release_residual_explanation_report = (
        build_scene_release_residual_explanation_audit_report(
            project_root=root,
            terminal_release_exception_report=terminal_release_exception_report,
            boundary_maturity_release_envelope_report=(
                boundary_maturity_release_envelope_report
            ),
            dashboard_warning_count=(
                terminal_release_exception_report.warning_projection_count
            ),
        )
    )
    release_governance_export_script_evidence_report = (
        _release_governance_export_script_evidence_report(
            scene_release_governance_report_pairs(
                locals(),
                include_acceptance_certificate=False,
            ),
            acceptance_source_evidence=acceptance_source_evidence,
        )
    )
    return {
        "high_frequency_completeness_audit": (
            high_frequency_completeness_report
        ),
        "high_frequency_task_lexicon_audit": (
            high_frequency_task_lexicon_report
        ),
        "scene_user_journey_fixture_audit": user_journey_fixture_report,
        "scene_control_consistency_audit": control_consistency_report,
        "scene_control_runtime_consistency_audit": (
            control_runtime_consistency_report
        ),
        "scene_input_source_audit": input_source_report,
        "scene_material_schema_audit": material_schema_report,
        "scene_material_repair_flow_audit": material_repair_flow_report,
        "scene_word_risk_closure_audit": word_risk_closure_report,
        "scene_object_preflight_action_audit": object_preflight_action_report,
        "scene_fixed_layout_profile_audit": fixed_layout_profile_report,
        "scene_count_profile_audit": count_profile_report,
        "scene_formula_output_watermark_audit": formula_output_watermark_report,
        "scene_delivery_preset_audit": delivery_preset_report,
        "scene_delivery_preset_execution_audit": (
            delivery_preset_execution_report
        ),
        "scene_report_artifact_drilldown_audit": (
            report_artifact_drilldown_report
        ),
        "scene_business_capability_matrix_audit": (
            business_capability_matrix_report
        ),
        "scene_boundary_capability_matrix": boundary_capability_matrix_report,
        "scene_release_projection_surface_parity_audit": (
            release_projection_surface_parity_report
        ),
        "scene_release_closure_ledger_audit": (
            release_closure_ledger_report
        ),
        "scene_boundary_maturity_release_envelope_audit": (
            boundary_maturity_release_envelope_report
        ),
        "scene_release_residual_ratio_ledger_audit": (
            release_residual_ratio_ledger_report
        ),
        "scene_release_residual_explanation_audit": (
            release_residual_explanation_report
        ),
        "scene_retained_gap_exit_criteria_audit": (
            retained_gap_exit_criteria_report
        ),
        SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID: (
            release_governance_export_script_evidence_report
        ),
    }


def _release_governance_export_script_evidence_report(
    reports: tuple[tuple[str, object], ...],
    *,
    acceptance_source_evidence: (
        tuple[SceneReleaseAcceptanceCertificateSourceEvidence, ...]
    ),
) -> SceneReleaseGovernanceExportScriptEvidenceReport:
    rows = [
        _release_export_script_row(report_id, report)
        for report_id, report in reports
    ]
    acceptance_export_evidence = {
        evidence.source_id: evidence.status for evidence in acceptance_source_evidence
    }
    rows.append(
        SceneReleaseGovernanceExportScriptEvidenceRow(
            report_id=SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
            payload_source_id=SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
            export_script_status=acceptance_export_evidence.get(
                "export_script",
                "missing",
            ),
            source_evidence_count=len(acceptance_source_evidence),
        )
    )
    return SceneReleaseGovernanceExportScriptEvidenceReport(rows=tuple(rows))


def _release_export_script_row(
    report_id: str,
    report: object,
) -> SceneReleaseGovernanceExportScriptEvidenceRow:
    payload = report.to_payload()
    source_evidence = list(payload.get("source_evidence") or [])
    source_status = {
        item.get("source_id"): item.get("status") for item in source_evidence
    }
    return SceneReleaseGovernanceExportScriptEvidenceRow(
        report_id=report_id,
        payload_source_id=str(payload.get("source_id") or ""),
        export_script_status=str(source_status.get("export_script") or "missing"),
        source_evidence_count=len(source_evidence),
    )


def _row_for_spec(
    spec: SceneReleaseAcceptanceCertificateSpec,
    reports: dict[str, object],
) -> SceneReleaseAcceptanceCertificateRow:
    issue_ids: list[str] = []
    report = reports.get(spec.source_id)
    if report is None:
        issue_ids.append("missing_component_report")
        observed_numerator = 0
        observed_denominator = 0
    else:
        if getattr(report, "status", "") != "passed":
            issue_ids.append("component_report_failed")
        observed_numerator = int(getattr(report, spec.observed_numerator_attr, 0))
        observed_denominator = int(getattr(report, spec.observed_denominator_attr, 0))
        if (
            observed_numerator != spec.expected_numerator
            or observed_denominator != spec.expected_denominator
        ):
            issue_ids.append("unexpected_release_count")
    return SceneReleaseAcceptanceCertificateRow(
        certificate_id=spec.certificate_id,
        source_id=spec.source_id,
        observed_numerator=observed_numerator,
        observed_denominator=observed_denominator,
        expected_numerator=spec.expected_numerator,
        expected_denominator=spec.expected_denominator,
        status="certificate_ready" if not issue_ids else "certificate_gap",
        summary=spec.summary,
        evidence_ids=SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_REQUIRED_EVIDENCE_IDS,
        issue_ids=tuple(dict.fromkeys(issue_ids)),
    )


def _requirement_dimension_rows(
    reports: dict[str, object],
    certificate_rows: tuple[SceneReleaseAcceptanceCertificateRow, ...],
) -> tuple[SceneReleaseRequirementDimensionRow, ...]:
    ready_certificate_count = sum(row.is_ready for row in certificate_rows)
    certificate_count = len(certificate_rows)
    ratio_by_dimension: dict[str, tuple[int, int]] = {
        "high_frequency_scene_coverage": _ratio_sum(
            (
                _ratio(
                    reports,
                    "high_frequency_completeness_audit",
                    "ready_pack_count",
                    "pack_count",
                ),
            )
        ),
        "natural_request_to_scene_route": _ratio_sum(
            (
                _passed_total(
                    reports,
                    "high_frequency_task_lexicon_audit",
                    "task_count",
                ),
                _passed_total(
                    reports,
                    "high_frequency_task_lexicon_audit",
                    "request_cell_count",
                ),
                _ratio(
                    reports,
                    "scene_user_journey_fixture_audit",
                    "ready_pack_count",
                    "pack_count",
                ),
            )
        ),
        "scene_board_control_style_consistency": _ratio_sum(
            (
                _passed_total(
                    reports,
                    "scene_control_consistency_audit",
                    "contract_count",
                ),
                _ratio(
                    reports,
                    "scene_control_runtime_consistency_audit",
                    "ready_runtime_control_count",
                    "runtime_control_count",
                ),
            )
        ),
        "input_material_scope": _ratio_sum(
            (
                _ratio(
                    reports,
                    "scene_input_source_audit",
                    "ready_input_pack_count",
                    "input_pack_count",
                ),
                _ratio(
                    reports,
                    "scene_material_schema_audit",
                    "ready_material_family_count",
                    "material_family_count",
                ),
                _ratio(
                    reports,
                    "scene_material_repair_flow_audit",
                    "ready_flow_count",
                    "flow_count",
                ),
            )
        ),
        "word_ooxml_risk_scope": _ratio_sum(
            (
                _passed_total(
                    reports,
                    "scene_word_risk_closure_audit",
                    "surface_count",
                ),
                _ratio(
                    reports,
                    "scene_object_preflight_action_audit",
                    "ready_target_count",
                    "target_count",
                ),
                _ratio(
                    reports,
                    "scene_fixed_layout_profile_audit",
                    "ready_profile_channel_count",
                    "profile_channel_count",
                ),
                _ratio(
                    reports,
                    "scene_count_profile_audit",
                    "accounted_family_count",
                    "count_profile_family_count",
                ),
            )
        ),
        "formula_output_watermark_scene_ownership": _ratio_sum(
            (
                _ratio(
                    reports,
                    "scene_formula_output_watermark_audit",
                    "ready_capability_count",
                    "capability_count",
                ),
                _ratio(
                    reports,
                    "scene_formula_output_watermark_audit",
                    "accounted_family_count",
                    "family_count",
                ),
            )
        ),
        "delivery_artifact_chain": _ratio_sum(
            (
                _ratio(
                    reports,
                    "scene_delivery_preset_audit",
                    "accounted_family_count",
                    "family_count",
                ),
                _ratio(
                    reports,
                    "scene_delivery_preset_execution_audit",
                    "ready_execution_channel_count",
                    "execution_channel_count",
                ),
                _ratio(
                    reports,
                    "scene_report_artifact_drilldown_audit",
                    "ready_drilldown_channel_count",
                    "drilldown_channel_count",
                ),
            )
        ),
        "business_family_boundary_catalog": _ratio_sum(
            (
                _ratio(
                    reports,
                    "scene_business_capability_matrix_audit",
                    "ready_capability_count",
                    "capability_count",
                ),
                _ratio(
                    reports,
                    "scene_boundary_capability_matrix",
                    "ready_capability_count",
                    "capability_count",
                ),
            )
        ),
        "residual_boundary_release_governance": _ratio_sum(
            (
                _ratio(
                    reports,
                    "scene_boundary_maturity_release_envelope_audit",
                    "ready_envelope_count",
                    "envelope_count",
                ),
                _ratio(
                    reports,
                    "scene_retained_gap_exit_criteria_audit",
                    "release_allowed_count",
                    "criteria_count",
                ),
                _ratio(
                    reports,
                    "scene_retained_gap_exit_criteria_audit",
                    "external_receipt_alignment_count",
                    "criteria_count",
                ),
                _ratio(
                    reports,
                    "scene_release_residual_ratio_ledger_audit",
                    "published_ratio_count",
                    "ratio_count",
                ),
                _ratio(
                    reports,
                    "scene_release_residual_ratio_ledger_audit",
                    "retained_gap_receipt_alignment_link_count",
                    "retained_gap_exit_criteria_link_count",
                ),
                _ratio(
                    reports,
                    "scene_release_residual_ratio_ledger_audit",
                    "boundary_scope_alignment_count",
                    "boundary_scope_link_count",
                ),
                _ratio(
                    reports,
                    "scene_release_residual_explanation_audit",
                    "covered_count",
                    "row_count",
                ),
                (ready_certificate_count, certificate_count),
            )
        ),
        "projection_export_visibility": _ratio_sum(
            (
                _ratio(
                    reports,
                    "scene_release_projection_surface_parity_audit",
                    "ready_projection_count",
                    "projection_count",
                ),
                _ratio(
                    reports,
                    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID,
                    "ready_export_script_count",
                    "report_count",
                ),
            )
        ),
    }
    return tuple(
        _requirement_dimension_row(spec, reports, ratio_by_dimension[spec.dimension_id])
        for spec in SCENE_RELEASE_REQUIREMENT_DIMENSION_SPECS
    )


def _requirement_dimension_row(
    spec: SceneReleaseRequirementDimensionSpec,
    reports: dict[str, object],
    observed: tuple[int, int],
) -> SceneReleaseRequirementDimensionRow:
    observed_numerator, observed_denominator = observed
    issue_ids: list[str] = []
    missing_sources = [
        source_id for source_id in spec.source_ids if source_id not in reports
    ]
    failed_sources = [
        source_id
        for source_id in spec.source_ids
        if source_id in reports and getattr(reports[source_id], "status", "") != "passed"
    ]
    if missing_sources:
        issue_ids.append("missing_dimension_source")
    if failed_sources:
        issue_ids.append("dimension_source_failed")
    if observed_denominator <= 0:
        issue_ids.append("empty_dimension_evidence")
    elif observed_numerator != observed_denominator:
        issue_ids.append("dimension_ratio_mismatch")
    return SceneReleaseRequirementDimensionRow(
        dimension_id=spec.dimension_id,
        label=spec.label,
        requirement=spec.requirement,
        observed_numerator=observed_numerator,
        observed_denominator=observed_denominator,
        source_ids=spec.source_ids,
        evidence_ids=spec.evidence_ids,
        issue_ids=tuple(dict.fromkeys(issue_ids)),
    )


def _ratio_sum(values: tuple[tuple[int, int], ...]) -> tuple[int, int]:
    return (
        sum(numerator for numerator, _ in values),
        sum(denominator for _, denominator in values),
    )


def _ratio(
    reports: dict[str, object],
    source_id: str,
    numerator_attr: str,
    denominator_attr: str,
) -> tuple[int, int]:
    report = reports.get(source_id)
    if report is None:
        return (0, 0)
    return (
        int(getattr(report, numerator_attr, 0)),
        int(getattr(report, denominator_attr, 0)),
    )


def _passed_total(
    reports: dict[str, object],
    source_id: str,
    denominator_attr: str,
) -> tuple[int, int]:
    report = reports.get(source_id)
    if report is None:
        return (0, 0)
    denominator = int(getattr(report, denominator_attr, 0))
    numerator = denominator if getattr(report, "status", "") == "passed" else 0
    return (numerator, denominator)


def _source_evidence(
    root: Path,
) -> tuple[SceneReleaseAcceptanceCertificateSourceEvidence, ...]:
    return tuple(
        SceneReleaseAcceptanceCertificateSourceEvidence(
            source_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
        )
        for result in scan_scene_source_markers(
            root,
            SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_SOURCE_MARKERS,
        )
    )


def _source_evidence_issues(
    source_evidence: tuple[SceneReleaseAcceptanceCertificateSourceEvidence, ...],
) -> tuple[SceneReleaseAcceptanceCertificateIssue, ...]:
    return tuple(
        SceneReleaseAcceptanceCertificateIssue(
            evidence.source_id,
            "missing_source_evidence",
            scene_source_marker_issue_message(
                evidence.source_path,
                evidence.missing_markers,
            ),
        )
        for evidence in source_evidence
        if evidence.missing_markers
    )


__all__ = [
    "SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID",
    "SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_REQUIRED_EVIDENCE_IDS",
    "SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_SPECS",
    "SCENE_RELEASE_REQUIREMENT_DIMENSION_SPECS",
    "SceneReleaseAcceptanceCertificateAuditReport",
    "SceneReleaseAcceptanceCertificateIssue",
    "SceneReleaseAcceptanceCertificateRow",
    "SceneReleaseAcceptanceCertificateSourceEvidence",
    "SceneReleaseAcceptanceCertificateSpec",
    "SceneReleaseRequirementDimensionRow",
    "SceneReleaseRequirementDimensionSpec",
    "audit_scene_release_acceptance_certificate_report",
    "build_scene_release_acceptance_certificate_audit_report",
]
