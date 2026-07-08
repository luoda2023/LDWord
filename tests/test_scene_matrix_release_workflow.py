import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    RELEASE_GATE_HUMAN_SUMMARY_PARTS,
)
from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS,
)

RELEASE_GOVERNANCE_WORKFLOW_EVIDENCE = (
    (
        "scripts/export_scene_release_acceptance_certificate_audit.py",
        "tests/test_scene_release_acceptance_certificate_audit.py",
    ),
    (
        "scripts/export_scene_release_closure_ledger_audit.py",
        "tests/test_scene_release_closure_ledger_audit.py",
    ),
    (
        "scripts/export_scene_release_projection_surface_parity_audit.py",
        "tests/test_scene_release_projection_surface_parity_audit.py",
    ),
)

RELEASE_GATE_HUMAN_SUMMARY_SOURCE_MARKERS = (
    "RELEASE_GATE_HUMAN_SUMMARY_PARTS",
    "def _format_summary_part(",
    "for template, count_ids in RELEASE_GATE_HUMAN_SUMMARY_PARTS",
    "high_frequency_coverage=",
    "count_delivery_alignment=",
    "maturity_l5_alignment=",
    "boundary_scope_alignment=",
    "retained_gap_receipts=",
    "residual_ratio_receipts=",
    "acceptance_certificate=",
    "acceptance_receipts=",
    "requirement_dimensions=",
    "acceptance_evidence=",
    "release_export_scripts=",
    "dashboard_packs=",
    "drilldown_rows=",
    "drilldown_sources=",
    "scene_release_acceptance_certificate_ready_count",
    "scene_release_acceptance_certificate_ready_receipt_count",
    "scene_release_acceptance_certificate_ready_requirement_dimension_count",
    "scene_release_acceptance_certificate_ready_source_evidence_count",
    "scene_release_governance_export_script_ready_count",
    "scene_matrix_drilldown_ready_source_evidence_count",
)

RELEASE_GATE_RELEASE_GOVERNANCE_COUNT_PREFIXES = (
    "scene_boundary_guarded_completion_",
    "scene_boundary_maturity_release_envelope_",
    "scene_boundary_readiness_reconciliation_",
    "scene_boundary_subject_release_continuity_",
    "scene_boundary_subject_release_dossier_",
    "scene_non_subject_release_trace_attribution_",
    "scene_release_",
    "scene_residual_warning_governance_",
    "scene_retained_gap_",
    "scene_terminal_release_exception_",
)

SCENE_MATRIX_RELEASE_WORKFLOW_TEST_PATHS = (
    "tests/test_scene_coverage_manifest.py",
    "tests/test_scene_audit_exporter.py",
    "tests/test_scene_matrix_release_workflow.py",
    "tests/test_scene_ambiguity_clarification_ui_audit.py",
    "tests/test_scene_ambiguous_boundary_audit.py",
    "tests/test_scene_boundary_capability_matrix.py",
    "tests/test_scene_boundary_readiness_reconciliation_audit.py",
    "tests/test_scene_boundary_guarded_completion_audit.py",
    "tests/test_scene_boundary_subject_release_continuity_audit.py",
    "tests/test_scene_boundary_subject_release_dossier_audit.py",
    "tests/test_scene_business_capability_matrix_audit.py",
    "tests/test_scene_control_consistency_audit.py",
    "tests/test_scene_control_runtime_consistency_audit.py",
    "tests/test_scene_count_profile_audit.py",
    "tests/test_scene_delivery_preset_audit.py",
    "tests/test_scene_delivery_preset_execution_audit.py",
    "tests/test_scene_external_handoff_contract_audit.py",
    "tests/test_scene_family_fixture_depth_audit.py",
    "tests/test_scene_family_subscene_audit.py",
    "tests/test_scene_formula_output_watermark_audit.py",
    "tests/test_scene_high_frequency_completeness_audit.py",
    "tests/test_scene_high_frequency_request_samples.py",
    "tests/test_scene_high_frequency_task_lexicon_audit.py",
    "tests/test_scene_import_handoff_audit.py",
    "tests/test_scene_input_source_audit.py",
    "tests/test_scene_non_subject_release_trace_attribution_audit.py",
    "tests/test_scene_release_trace_partition_guard_audit.py",
    "tests/test_scene_release_projection_surface_parity_audit.py",
    "tests/test_scene_release_closure_ledger_audit.py",
    "tests/test_scene_boundary_maturity_release_envelope_audit.py",
    "tests/test_scene_retained_gap_exit_criteria_audit.py",
    "tests/test_scene_release_residual_ratio_ledger_audit.py",
    "tests/test_scene_release_residual_explanation_audit.py",
    "tests/test_scene_release_acceptance_certificate_audit.py",
    "tests/test_scene_material_schema_audit.py",
    "tests/test_scene_material_repair_flow_audit.py",
    "tests/test_scene_fixed_layout_profile_audit.py",
    "tests/test_scene_report_artifact_drilldown_audit.py",
    "tests/test_scene_residual_warning_governance_audit.py",
    "tests/test_scene_terminal_release_exception_audit.py",
    "tests/test_scene_matrix_dashboard_aggregate.py",
    "tests/test_scene_matrix_dashboard_export.py",
    "tests/test_scene_matrix_dashboard_release_gate_payload.py",
    "tests/test_scene_matrix_dashboard_release_governance_registry.py",
    "tests/test_scene_matrix_dashboard_summary.py",
    "tests/test_scene_matrix_drilldown_audit.py",
    "tests/test_scene_matrix_drilldown_behavior.py",
    "tests/test_scene_matrix_drilldown_frontend_sources.py",
    "tests/test_scene_matrix_drilldown_release_governance_registry.py",
    "tests/test_scene_matrix_drilldown_source_markers.py",
    "tests/test_scene_object_preflight_action_audit.py",
    "tests/test_scene_pack_slot_audit.py",
    "tests/test_scene_parameter_ownership.py",
    "tests/test_scene_plugin_boundary_confirmation_audit.py",
    "tests/test_scene_product_maturity_upgrade_audit.py",
    "tests/test_scene_request_cell_registry_browser.py",
    "tests/test_scene_rule_source_governance.py",
    "tests/test_scene_sample_fixture_regression.py",
    "tests/test_scene_user_journey_fixture_audit.py",
    "tests/test_scene_word_risk_closure_audit.py",
)


def _read_scene_matrix_release_workflow() -> str:
    return (
        ROOT / ".github" / "workflows" / "scene-matrix-release-gate.yml"
    ).read_text(encoding="utf-8")


def _workflow_regression_test_paths(workflow: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in workflow.splitlines()
        if line.strip().startswith("tests/")
    )


def _release_gate_human_summary_count_ids() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            count_id
            for _template, count_ids in RELEASE_GATE_HUMAN_SUMMARY_PARTS
            for count_id in count_ids
        )
    )


def test_scene_matrix_release_gate_is_wired_into_ci_workflow():
    workflow = _read_scene_matrix_release_workflow()

    assert "Scene Matrix Release Gate" in workflow
    assert "workflow_dispatch" in workflow
    assert "python scripts/verify_scene_matrix_release_gate.py" in workflow
    assert (
        _workflow_regression_test_paths(workflow)
        == SCENE_MATRIX_RELEASE_WORKFLOW_TEST_PATHS
    )


def test_scene_matrix_release_workflow_keeps_release_governance_evidence_visible():
    workflow = _read_scene_matrix_release_workflow()

    assert "tests/test_scene_audit_exporter.py" in workflow
    for export_script_path, audit_test_path in RELEASE_GOVERNANCE_WORKFLOW_EVIDENCE:
        assert (ROOT / export_script_path).exists()
        assert audit_test_path in workflow


def test_scene_matrix_release_gate_cli_stays_thin_and_delegates_payload_builder():
    script = (ROOT / "scripts" / "verify_scene_matrix_release_gate.py").read_text(
        encoding="utf-8"
    )
    payload_module = (
        ROOT / "scripts" / "scene_matrix_release_gate_payload.py"
    ).read_text(encoding="utf-8")

    assert "from scripts.scene_matrix_release_gate_payload import" in script
    assert "from src.config.scene_release_governance_registry import" in script
    assert "def build_scene_matrix_release_gate_payload" not in script
    assert tuple(
        line
        for line in script.splitlines()
        if line.startswith("from src.config.")
    ) == ("from src.config.scene_release_governance_registry import (  # noqa: E402",)
    assert len(script.splitlines()) <= 350

    assert "def build_scene_matrix_release_gate_payload" in payload_module
    assert "from src.config." in payload_module


def test_scene_matrix_release_gate_human_summary_keeps_source_markers_visible():
    script = (ROOT / "scripts" / "verify_scene_matrix_release_gate.py").read_text(
        encoding="utf-8"
    )

    for marker in RELEASE_GATE_HUMAN_SUMMARY_SOURCE_MARKERS:
        assert marker in script


def test_scene_matrix_release_gate_human_summary_release_counts_are_registry_backed():
    human_count_ids = _release_gate_human_summary_count_ids()
    registry_summary_count_ids = {
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS
    }
    registry_count_ids = {
        spec.count_id
        for spec in (
            *SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS,
            *SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS,
        )
    }
    release_prefixed_human_count_ids = {
        count_id
        for count_id in human_count_ids
        if count_id.startswith(RELEASE_GATE_RELEASE_GOVERNANCE_COUNT_PREFIXES)
    }

    assert registry_summary_count_ids <= set(human_count_ids)
    assert release_prefixed_human_count_ids <= registry_count_ids
    assert "scene_release_projection_surface_parity_ready_count" in human_count_ids
    assert "scene_release_closure_ledger_ready_count" in human_count_ids
    assert "scene_release_governance_export_script_ready_count" in human_count_ids
