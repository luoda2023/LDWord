from __future__ import annotations

import copy
import os
import sys
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scripts.verify_scene_sample_fixtures import verify_scene_sample_fixture_library  # noqa: E402
from src.config.scene_ambiguous_boundary_audit import (  # noqa: E402
    audit_scene_ambiguous_boundary_report,
    build_scene_ambiguous_boundary_audit_report,
)
from src.config.scene_ambiguity_clarification_ui_audit import (  # noqa: E402
    audit_scene_ambiguity_clarification_ui_report,
    build_scene_ambiguity_clarification_ui_audit_report,
)
from src.config.scene_coverage_manifest import (  # noqa: E402
    SCENE_COVERAGE_PACK_MAP,
    audit_scene_closure_validation_commands,
    audit_scene_pack_completeness,
    audit_scene_pack_matrix_alignment,
)
from src.config.scene_high_frequency_request_samples import (  # noqa: E402
    audit_high_frequency_request_samples,
    list_high_frequency_request_samples,
)
from src.config.scene_high_frequency_task_lexicon_audit import (  # noqa: E402
    audit_high_frequency_task_lexicon_report,
    build_high_frequency_task_lexicon_audit_report,
)
from src.config.scene_import_handoff_audit import (  # noqa: E402
    audit_scene_import_handoff_report,
    build_scene_import_handoff_audit_report,
)
from src.config.scene_input_source_audit import (  # noqa: E402
    audit_scene_input_source_report,
    build_scene_input_source_audit_report,
)
from src.config.scene_high_frequency_completeness_audit import (  # noqa: E402
    audit_high_frequency_completeness_report,
    build_high_frequency_completeness_audit_report,
)
from src.config.scene_business_capability_matrix_audit import (  # noqa: E402
    audit_scene_business_capability_matrix_report,
    build_scene_business_capability_matrix_audit_report,
)
from src.config.scene_boundary_capability_matrix import (  # noqa: E402
    audit_scene_boundary_capability_report,
    build_scene_boundary_capability_audit_report,
)
from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
    SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS,
    SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS,
    build_scene_release_governance_report,
    resolve_scene_release_governance_functions,
    scene_release_governance_count_entries,
    scene_release_governance_detail_count_entries,
    scene_release_governance_payload_entries,
    scene_release_governance_report_pairs,
    scene_release_governance_report_spec,
)
from src.config.scene_external_handoff_contract_audit import (  # noqa: E402
    audit_scene_external_handoff_contract_report,
    build_scene_external_handoff_contract_audit_report,
)
from src.config.scene_matrix_dashboard import (  # noqa: E402
    audit_scene_matrix_dashboard,
    build_scene_matrix_dashboard,
)
from src.config.scene_matrix_drilldown import (  # noqa: E402
    build_scene_matrix_drilldown_report,
)
from src.config.scene_material_schema_audit import (  # noqa: E402
    audit_scene_material_schema_report,
    build_scene_material_schema_audit_report,
)
from src.config.scene_material_repair_flow_audit import (  # noqa: E402
    audit_scene_material_repair_flow_report,
    build_scene_material_repair_flow_audit_report,
)
from src.config.scene_fixed_layout_profile_audit import (  # noqa: E402
    audit_scene_fixed_layout_profile_report,
    build_scene_fixed_layout_profile_audit_report,
)
from src.config.scene_report_artifact_drilldown_audit import (  # noqa: E402
    audit_scene_report_artifact_drilldown_report,
    build_scene_report_artifact_drilldown_audit_report,
)
from src.config.scene_object_preflight_action_audit import (  # noqa: E402
    audit_scene_object_preflight_action_report,
    build_scene_object_preflight_action_audit_report,
)
from src.config.scene_user_journey_fixture_audit import (  # noqa: E402
    audit_scene_user_journey_fixture_report,
    build_scene_user_journey_fixture_audit_report,
)
from src.config.scene_plugin_boundary_confirmation_audit import (  # noqa: E402
    audit_scene_plugin_boundary_confirmation_report,
    build_scene_plugin_boundary_confirmation_audit_report,
)
from src.config.scene_family_subscene_audit import (  # noqa: E402
    audit_scene_family_subscene_report,
    build_scene_family_subscene_audit_report,
)
from src.config.scene_family_fixture_depth_audit import (  # noqa: E402
    audit_scene_family_fixture_depth_report,
    build_scene_family_fixture_depth_audit_report,
)
from src.config.scene_control_consistency_audit import (  # noqa: E402
    audit_scene_control_consistency_report,
    build_scene_control_consistency_audit_report,
)
from src.config.scene_control_runtime_consistency_audit import (  # noqa: E402
    audit_scene_control_runtime_consistency_report,
    build_scene_control_runtime_consistency_audit_report,
)
from src.config.scene_count_profile_audit import (  # noqa: E402
    audit_scene_count_profile_report,
    build_scene_count_profile_audit_report,
)
from src.config.scene_delivery_preset_audit import (  # noqa: E402
    audit_scene_delivery_preset_report,
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_delivery_preset_execution_audit import (  # noqa: E402
    audit_scene_delivery_preset_execution_report,
    build_scene_delivery_preset_execution_audit_report,
)
from src.config.scene_formula_output_watermark_audit import (  # noqa: E402
    audit_scene_formula_output_watermark_report,
    build_scene_formula_output_watermark_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (  # noqa: E402
    audit_scene_product_maturity_upgrade_report,
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_word_risk_closure_audit import (  # noqa: E402
    audit_scene_word_risk_closure_report,
    build_scene_word_risk_closure_audit_report,
)
from src.config.scene_product_readiness import (  # noqa: E402
    audit_scene_product_readiness,
    list_scene_product_readiness_specs,
    static_closed_but_not_green_specs,
)
from src.config.scene_request_cell_fixture_registry import (  # noqa: E402
    audit_scene_request_cell_fixtures,
    build_scene_request_cell_fixture_summary,
    build_scene_request_cell_registry_browser,
)
from src.config.scene_sample_fixture_registry import (  # noqa: E402
    REQUIRED_SAMPLE_PACK_IDS,
    audit_scene_sample_fixtures,
    list_scene_sample_fixtures,
)


_PYTEST_RELEASE_GATE_PAYLOAD_CACHE: dict[str, object] | None = None

SCENE_MATRIX_DASHBOARD_RELEASE_GATE_PAYLOAD_FIELD_COUNTS: tuple[
    tuple[str, str],
    ...,
] = (
    ("scene_matrix_dashboard_pack_count", "pack_count"),
    ("scene_matrix_dashboard_visible_count", "visible_count"),
    ("scene_matrix_dashboard_issue_count", "issue_count"),
    ("scene_matrix_dashboard_warning_count", "warning_count"),
)

SCENE_MATRIX_DRILLDOWN_RELEASE_GATE_COUNT_IDS: tuple[str, ...] = (
    "item_count",
    "ready_count",
    "row_count",
    "visible_row_count",
    "issue_count",
    "source_evidence_count",
    "ready_source_evidence_count",
    "missing_source_evidence_count",
)


def _pytest_release_gate_lightweight_enabled() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and not bool(
        os.environ.get("LARK_FULL_SCENE_RELEASE_GATE_IN_TESTS")
    )


def _release_gate_payload_for_output_dir(
    payload: dict[str, object],
    output_dir: Path,
) -> dict[str, object]:
    cloned = copy.deepcopy(payload)
    cloned["fixture_library_output_dir"] = str(output_dir)
    return cloned


def _prefixed_payload_count_entries(
    payload: dict[str, object],
    *,
    prefix: str,
    count_ids: tuple[str, ...],
) -> dict[str, int]:
    counts = payload["counts"]
    if not isinstance(counts, dict):
        raise TypeError(f"{prefix} payload counts must be a mapping.")
    return {
        f"{prefix}_{count_id}": int(counts[count_id])
        for count_id in count_ids
    }


def _scene_matrix_dashboard_release_gate_counts(
    payload: dict[str, object],
) -> dict[str, int]:
    counts = {
        release_gate_count_id: int(payload[payload_field_id])
        for (
            release_gate_count_id,
            payload_field_id,
        ) in SCENE_MATRIX_DASHBOARD_RELEASE_GATE_PAYLOAD_FIELD_COUNTS
    }
    counts.update(
        {
            "scene_matrix_dashboard_lens_count": len(payload["lenses"]),
            "scene_matrix_dashboard_source_count": len(payload["source_ids"]),
        }
    )
    return counts


@dataclass(slots=True)
class _ReleaseGateFoundation:
    checks: dict[str, object]
    request_cell_summary: object
    request_cell_browser: object
    completeness_report: object
    task_lexicon_report: object


@dataclass(slots=True)
class _ReleaseGovernanceExportEvidenceGate:
    evidence: list[dict[str, object]]
    counts: dict[str, int]


@dataclass(slots=True)
class _ReleaseGateMaterialDeliveryReports:
    material_schema_report: object
    material_repair_flow_report: object
    fixed_layout_profile_report: object
    report_artifact_drilldown_report: object
    delivery_preset_report: object
    delivery_execution_report: object
    formula_output_watermark_report: object
    maturity_upgrade_report: object


@dataclass(slots=True)
class _ReleaseGateDashboardResidualReports:
    matrix_dashboard: object
    release_residual_explanation_report: object


@dataclass(slots=True)
class _ReleaseGateEarlyReports:
    ambiguous_boundary_report: object
    ambiguity_clarification_report: object
    import_handoff_report: object
    input_source_report: object
    family_subscene_report: object
    family_fixture_depth_report: object
    scene_control_report: object
    scene_control_runtime_report: object
    count_profile_report: object
    word_risk_report: object
    object_preflight_action_report: object
    user_journey_fixture_report: object
    business_capability_matrix_report: object
    boundary_capability_report: object
    plugin_boundary_report: object
    external_handoff_contract_report: object


@dataclass(slots=True)
class _ReleaseGateGovernanceReports:
    boundary_guarded_completion_report: object
    residual_warning_governance_report: object
    boundary_readiness_reconciliation_report: object
    terminal_release_exception_report: object
    boundary_subject_release_dossier_report: object
    non_subject_release_trace_attribution_report: object
    release_trace_partition_guard_report: object
    release_projection_surface_parity_report: object
    boundary_subject_release_continuity_report: object
    release_closure_ledger_report: object
    boundary_maturity_release_envelope_report: object
    retained_gap_exit_criteria_report: object
    release_residual_ratio_ledger_report: object
    release_acceptance_certificate_report: object


def _build_release_governance_export_script_evidence(
    reports: tuple[tuple[str, object], ...],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for expected_source_id, report in reports:
        payload = report.to_payload()
        source_evidence = list(payload.get("source_evidence") or [])
        source_status = {
            item.get("source_id"): item.get("status") for item in source_evidence
        }
        export_script_status = source_status.get("export_script")
        rows.append(
            {
                "report_id": expected_source_id,
                "payload_source_id": payload.get("source_id"),
                "export_script_status": export_script_status or "missing",
                "source_evidence_count": len(source_evidence),
            }
        )
    return rows


def _release_governance_export_script_evidence_issues(
    rows: list[dict[str, object]],
) -> list[str]:
    issues: list[str] = []
    for row in rows:
        report_id = str(row["report_id"])
        payload_source_id = str(row.get("payload_source_id") or "")
        export_script_status = str(row["export_script_status"])
        if payload_source_id != report_id:
            issues.append(
                f"{report_id} payload source_id mismatch: {payload_source_id}"
            )
        if export_script_status == "missing":
            issues.append(f"{report_id} is missing export_script source evidence.")
        elif export_script_status != "ready":
            issues.append(
                f"{report_id} export_script source evidence is {export_script_status}."
            )
    return issues


def _release_governance_export_script_evidence_counts(
    rows: list[dict[str, object]],
) -> dict[str, int]:
    ready_count = sum(
        1 for row in rows if row["export_script_status"] == "ready"
    )
    missing_count = sum(
        1 for row in rows if row["export_script_status"] == "missing"
    )
    return {
        "report_count": len(rows),
        "ready_count": ready_count,
        "missing_count": missing_count,
        "unready_count": len(rows) - ready_count - missing_count,
    }


def _release_governance_issue_check(report_id: str, report: object) -> dict[str, object]:
    spec = scene_release_governance_report_spec(report_id)
    _builder, auditor = resolve_scene_release_governance_functions(spec)
    return _issue_check(auditor(report))


def _build_release_governance_export_evidence_gate(
    *,
    checks: dict[str, object],
    boundary_guarded_completion_report: object,
    residual_warning_governance_report: object,
    boundary_readiness_reconciliation_report: object,
    terminal_release_exception_report: object,
    boundary_subject_release_dossier_report: object,
    non_subject_release_trace_attribution_report: object,
    release_trace_partition_guard_report: object,
    release_projection_surface_parity_report: object,
    boundary_subject_release_continuity_report: object,
    boundary_maturity_release_envelope_report: object,
    retained_gap_exit_criteria_report: object,
    release_residual_ratio_ledger_report: object,
    release_residual_explanation_report: object,
    release_closure_ledger_report: object,
    release_acceptance_certificate_report: object,
) -> _ReleaseGovernanceExportEvidenceGate:
    evidence = _build_release_governance_export_script_evidence(
        scene_release_governance_report_pairs(locals())
    )
    checks["scene_release_governance_export_script_evidence"] = (
        _string_issue_check(
            _release_governance_export_script_evidence_issues(evidence)
        )
    )
    return _ReleaseGovernanceExportEvidenceGate(
        evidence=evidence,
        counts=_release_governance_export_script_evidence_counts(evidence),
    )


def _build_release_gate_foundation(output_dir: Path) -> _ReleaseGateFoundation:
    checks = {
        "coverage_pack_completeness": _issue_check(audit_scene_pack_completeness()),
        "coverage_pack_matrix_alignment": _issue_check(
            audit_scene_pack_matrix_alignment()
        ),
        "coverage_closure_validation": _issue_check(
            [
                item
                for item in audit_scene_closure_validation_commands()
                if not item.is_valid
            ]
        ),
        "high_frequency_request_samples": _issue_check(
            audit_high_frequency_request_samples()
        ),
        "scene_product_readiness": _issue_check(audit_scene_product_readiness()),
        "scene_sample_fixtures": _issue_check(audit_scene_sample_fixtures()),
        "scene_request_cell_fixtures": _issue_check(
            audit_scene_request_cell_fixtures()
        ),
    }
    fixture_library_issues = verify_scene_sample_fixture_library(output_dir)
    checks["scene_sample_fixture_library"] = _string_issue_check(
        fixture_library_issues
    )

    request_cell_summary = build_scene_request_cell_fixture_summary()
    checks["scene_request_cell_release_threshold"] = _string_issue_check(
        _hard_gate_issues(request_cell_summary)
    )
    request_cell_browser = build_scene_request_cell_registry_browser()
    checks["scene_request_cell_registry_browser"] = _string_issue_check(
        _request_cell_browser_gate_issues(request_cell_summary, request_cell_browser)
    )
    completeness_report = build_high_frequency_completeness_audit_report()
    checks["high_frequency_completeness_audit"] = _issue_check(
        audit_high_frequency_completeness_report(completeness_report)
    )
    task_lexicon_report = build_high_frequency_task_lexicon_audit_report()
    checks["high_frequency_task_lexicon_audit"] = _issue_check(
        audit_high_frequency_task_lexicon_report(task_lexicon_report)
    )
    return _ReleaseGateFoundation(
        checks=checks,
        request_cell_summary=request_cell_summary,
        request_cell_browser=request_cell_browser,
        completeness_report=completeness_report,
        task_lexicon_report=task_lexicon_report,
    )


def _build_release_gate_early_reports(
    *, checks: dict[str, object]
) -> _ReleaseGateEarlyReports:
    ambiguous_boundary_report = build_scene_ambiguous_boundary_audit_report(
        project_root=ROOT
    )
    checks["scene_ambiguous_boundary_audit"] = _issue_check(
        audit_scene_ambiguous_boundary_report(ambiguous_boundary_report)
    )
    ambiguity_clarification_report = (
        build_scene_ambiguity_clarification_ui_audit_report(project_root=ROOT)
    )
    ambiguity_clarification_issues, _ambiguity_clarification_warnings = (
        audit_scene_ambiguity_clarification_ui_report(
            ambiguity_clarification_report
        )
    )
    checks["scene_ambiguity_clarification_ui_audit"] = _issue_check(
        ambiguity_clarification_issues
    )
    import_handoff_report = build_scene_import_handoff_audit_report(
        project_root=ROOT
    )
    checks["scene_import_handoff_audit"] = _issue_check(
        audit_scene_import_handoff_report(import_handoff_report)
    )
    input_source_report = build_scene_input_source_audit_report(project_root=ROOT)
    input_source_issues, _input_source_warnings = audit_scene_input_source_report(
        input_source_report
    )
    checks["scene_input_source_audit"] = _issue_check(input_source_issues)
    family_subscene_report = build_scene_family_subscene_audit_report()
    checks["scene_family_subscene_audit"] = _issue_check(
        audit_scene_family_subscene_report(family_subscene_report)
    )
    family_fixture_depth_report = build_scene_family_fixture_depth_audit_report(
        project_root=ROOT
    )
    checks["scene_family_fixture_depth_audit"] = _issue_check(
        audit_scene_family_fixture_depth_report(family_fixture_depth_report)
    )
    scene_control_report = build_scene_control_consistency_audit_report()
    checks["scene_control_consistency_audit"] = _issue_check(
        audit_scene_control_consistency_report(scene_control_report)
    )
    scene_control_runtime_report = (
        build_scene_control_runtime_consistency_audit_report(project_root=ROOT)
    )
    checks["scene_control_runtime_consistency_audit"] = _issue_check(
        audit_scene_control_runtime_consistency_report(scene_control_runtime_report)
    )
    count_profile_report = build_scene_count_profile_audit_report(project_root=ROOT)
    count_profile_issues, _count_profile_warnings = (
        audit_scene_count_profile_report(count_profile_report)
    )
    checks["scene_count_profile_audit"] = _issue_check(count_profile_issues)
    word_risk_report = build_scene_word_risk_closure_audit_report()
    checks["scene_word_risk_closure_audit"] = _issue_check(
        audit_scene_word_risk_closure_report(word_risk_report)
    )
    object_preflight_action_report = (
        build_scene_object_preflight_action_audit_report(project_root=ROOT)
    )
    object_preflight_action_issues, _object_preflight_action_warnings = (
        audit_scene_object_preflight_action_report(object_preflight_action_report)
    )
    checks["scene_object_preflight_action_audit"] = _issue_check(
        object_preflight_action_issues
    )
    user_journey_fixture_report = build_scene_user_journey_fixture_audit_report(
        project_root=ROOT
    )
    user_journey_fixture_issues, _user_journey_fixture_warnings = (
        audit_scene_user_journey_fixture_report(user_journey_fixture_report)
    )
    checks["scene_user_journey_fixture_audit"] = _issue_check(
        user_journey_fixture_issues
    )
    business_capability_matrix_report = (
        build_scene_business_capability_matrix_audit_report(project_root=ROOT)
    )
    business_capability_matrix_issues, _business_capability_matrix_warnings = (
        audit_scene_business_capability_matrix_report(
            business_capability_matrix_report
        )
    )
    checks["scene_business_capability_matrix_audit"] = _issue_check(
        business_capability_matrix_issues
    )
    boundary_capability_report = build_scene_boundary_capability_audit_report(
        project_root=ROOT
    )
    checks["scene_boundary_capability_matrix"] = _issue_check(
        audit_scene_boundary_capability_report(boundary_capability_report)
    )
    plugin_boundary_report = build_scene_plugin_boundary_confirmation_audit_report()
    checks["scene_plugin_boundary_confirmation_audit"] = _issue_check(
        audit_scene_plugin_boundary_confirmation_report(plugin_boundary_report)
    )
    external_handoff_contract_report = (
        build_scene_external_handoff_contract_audit_report(project_root=ROOT)
    )
    checks["scene_external_handoff_contract_audit"] = _issue_check(
        audit_scene_external_handoff_contract_report(
            external_handoff_contract_report
        )
    )
    return _ReleaseGateEarlyReports(
        ambiguous_boundary_report=ambiguous_boundary_report,
        ambiguity_clarification_report=ambiguity_clarification_report,
        import_handoff_report=import_handoff_report,
        input_source_report=input_source_report,
        family_subscene_report=family_subscene_report,
        family_fixture_depth_report=family_fixture_depth_report,
        scene_control_report=scene_control_report,
        scene_control_runtime_report=scene_control_runtime_report,
        count_profile_report=count_profile_report,
        word_risk_report=word_risk_report,
        object_preflight_action_report=object_preflight_action_report,
        user_journey_fixture_report=user_journey_fixture_report,
        business_capability_matrix_report=business_capability_matrix_report,
        boundary_capability_report=boundary_capability_report,
        plugin_boundary_report=plugin_boundary_report,
        external_handoff_contract_report=external_handoff_contract_report,
    )


def _build_release_gate_governance_reports(
    *,
    checks: dict[str, object],
    external_handoff_contract_report: object,
) -> _ReleaseGateGovernanceReports:
    reports_by_attribute: dict[str, object] = {
        "external_handoff_contract_report": external_handoff_contract_report,
    }
    for report_id in SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS:
        spec = scene_release_governance_report_spec(report_id)
        report = build_scene_release_governance_report(
            report_id,
            project_root=ROOT,
            dependencies=reports_by_attribute,
            require_dependencies=bool(spec.builder_dependency_names),
        )
        reports_by_attribute[spec.report_attribute] = report
        checks[report_id] = _release_governance_issue_check(report_id, report)

    return _ReleaseGateGovernanceReports(
        **{
            field.name: reports_by_attribute[field.name]
            for field in fields(_ReleaseGateGovernanceReports)
        }
    )


def _build_release_gate_material_delivery_reports(
    *, checks: dict[str, object]
) -> _ReleaseGateMaterialDeliveryReports:
    material_schema_report = build_scene_material_schema_audit_report(project_root=ROOT)
    material_schema_issues, _material_schema_warnings = (
        audit_scene_material_schema_report(material_schema_report)
    )
    checks["scene_material_schema_audit"] = _issue_check(material_schema_issues)
    material_repair_flow_report = build_scene_material_repair_flow_audit_report(
        project_root=ROOT
    )
    checks["scene_material_repair_flow_audit"] = _issue_check(
        audit_scene_material_repair_flow_report(material_repair_flow_report)
    )
    fixed_layout_profile_report = build_scene_fixed_layout_profile_audit_report(
        project_root=ROOT
    )
    checks["scene_fixed_layout_profile_audit"] = _issue_check(
        audit_scene_fixed_layout_profile_report(fixed_layout_profile_report)
    )
    report_artifact_drilldown_report = (
        build_scene_report_artifact_drilldown_audit_report(project_root=ROOT)
    )
    checks["scene_report_artifact_drilldown_audit"] = _issue_check(
        audit_scene_report_artifact_drilldown_report(
            report_artifact_drilldown_report
        )
    )
    delivery_preset_report = build_scene_delivery_preset_audit_report(
        project_root=ROOT
    )
    delivery_preset_issues, _delivery_preset_warnings = (
        audit_scene_delivery_preset_report(delivery_preset_report)
    )
    checks["scene_delivery_preset_audit"] = _issue_check(delivery_preset_issues)
    delivery_execution_report = build_scene_delivery_preset_execution_audit_report(
        project_root=ROOT
    )
    checks["scene_delivery_preset_execution_audit"] = _issue_check(
        audit_scene_delivery_preset_execution_report(delivery_execution_report)
    )
    formula_output_watermark_report = (
        build_scene_formula_output_watermark_audit_report(project_root=ROOT)
    )
    formula_output_watermark_issues, _formula_output_watermark_warnings = (
        audit_scene_formula_output_watermark_report(
            formula_output_watermark_report
        )
    )
    checks["scene_formula_output_watermark_audit"] = _issue_check(
        formula_output_watermark_issues
    )
    maturity_upgrade_report = build_scene_product_maturity_upgrade_audit_report(
        project_root=ROOT
    )
    maturity_upgrade_issues, _maturity_upgrade_warnings = (
        audit_scene_product_maturity_upgrade_report(maturity_upgrade_report)
    )
    checks["scene_product_maturity_upgrade_audit"] = _issue_check(
        maturity_upgrade_issues
    )
    return _ReleaseGateMaterialDeliveryReports(
        material_schema_report=material_schema_report,
        material_repair_flow_report=material_repair_flow_report,
        fixed_layout_profile_report=fixed_layout_profile_report,
        report_artifact_drilldown_report=report_artifact_drilldown_report,
        delivery_preset_report=delivery_preset_report,
        delivery_execution_report=delivery_execution_report,
        formula_output_watermark_report=formula_output_watermark_report,
        maturity_upgrade_report=maturity_upgrade_report,
    )


def _build_release_gate_dashboard_residual_reports(
    *,
    checks: dict[str, object],
    input_source_report: object,
    count_profile_report: object,
    residual_warning_governance_report: object,
    terminal_release_exception_report: object,
    boundary_maturity_release_envelope_report: object,
    release_residual_ratio_ledger_report: object,
    maturity_upgrade_report: object,
) -> _ReleaseGateDashboardResidualReports:
    matrix_dashboard = build_scene_matrix_dashboard()
    checks["scene_matrix_dashboard"] = _issue_check(
        audit_scene_matrix_dashboard(matrix_dashboard)
    )
    reports_by_attribute: dict[str, object] = {
        "input_source_report": input_source_report,
        "count_profile_report": count_profile_report,
        "residual_warning_governance_report": residual_warning_governance_report,
        "terminal_release_exception_report": terminal_release_exception_report,
        "boundary_maturity_release_envelope_report": (
            boundary_maturity_release_envelope_report
        ),
        "release_residual_ratio_ledger_report": (
            release_residual_ratio_ledger_report
        ),
        "maturity_upgrade_report": maturity_upgrade_report,
        "matrix_dashboard": matrix_dashboard,
        "dashboard_warning_count": matrix_dashboard.warning_count,
    }
    for report_id in SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS:
        spec = scene_release_governance_report_spec(report_id)
        report = build_scene_release_governance_report(
            report_id,
            project_root=ROOT,
            dependencies=reports_by_attribute,
            require_dependencies=bool(spec.builder_dependency_names),
        )
        reports_by_attribute[spec.report_attribute] = report
        checks[report_id] = _release_governance_issue_check(report_id, report)

    return _ReleaseGateDashboardResidualReports(
        **{
            field.name: reports_by_attribute[field.name]
            for field in fields(_ReleaseGateDashboardResidualReports)
        }
    )


def build_scene_matrix_release_gate_payload(output_dir: Path) -> dict[str, object]:
    global _PYTEST_RELEASE_GATE_PAYLOAD_CACHE
    if (
        _pytest_release_gate_lightweight_enabled()
        and _PYTEST_RELEASE_GATE_PAYLOAD_CACHE is not None
    ):
        return _release_gate_payload_for_output_dir(
            _PYTEST_RELEASE_GATE_PAYLOAD_CACHE,
            output_dir,
        )

    foundation = _build_release_gate_foundation(output_dir)
    checks = foundation.checks
    request_cell_summary = foundation.request_cell_summary
    request_cell_browser = foundation.request_cell_browser
    completeness_report = foundation.completeness_report
    task_lexicon_report = foundation.task_lexicon_report
    early_reports = _build_release_gate_early_reports(checks=checks)
    ambiguous_boundary_report = early_reports.ambiguous_boundary_report
    ambiguity_clarification_report = early_reports.ambiguity_clarification_report
    import_handoff_report = early_reports.import_handoff_report
    input_source_report = early_reports.input_source_report
    family_subscene_report = early_reports.family_subscene_report
    family_fixture_depth_report = early_reports.family_fixture_depth_report
    scene_control_report = early_reports.scene_control_report
    scene_control_runtime_report = early_reports.scene_control_runtime_report
    count_profile_report = early_reports.count_profile_report
    word_risk_report = early_reports.word_risk_report
    object_preflight_action_report = early_reports.object_preflight_action_report
    user_journey_fixture_report = early_reports.user_journey_fixture_report
    business_capability_matrix_report = (
        early_reports.business_capability_matrix_report
    )
    boundary_capability_report = early_reports.boundary_capability_report
    plugin_boundary_report = early_reports.plugin_boundary_report
    external_handoff_contract_report = early_reports.external_handoff_contract_report
    governance_reports = _build_release_gate_governance_reports(
        checks=checks,
        external_handoff_contract_report=external_handoff_contract_report,
    )
    boundary_guarded_completion_report = (
        governance_reports.boundary_guarded_completion_report
    )
    residual_warning_governance_report = (
        governance_reports.residual_warning_governance_report
    )
    boundary_readiness_reconciliation_report = (
        governance_reports.boundary_readiness_reconciliation_report
    )
    terminal_release_exception_report = (
        governance_reports.terminal_release_exception_report
    )
    boundary_subject_release_dossier_report = (
        governance_reports.boundary_subject_release_dossier_report
    )
    non_subject_release_trace_attribution_report = (
        governance_reports.non_subject_release_trace_attribution_report
    )
    release_trace_partition_guard_report = (
        governance_reports.release_trace_partition_guard_report
    )
    release_projection_surface_parity_report = (
        governance_reports.release_projection_surface_parity_report
    )
    boundary_subject_release_continuity_report = (
        governance_reports.boundary_subject_release_continuity_report
    )
    release_closure_ledger_report = governance_reports.release_closure_ledger_report
    boundary_maturity_release_envelope_report = (
        governance_reports.boundary_maturity_release_envelope_report
    )
    retained_gap_exit_criteria_report = (
        governance_reports.retained_gap_exit_criteria_report
    )
    release_residual_ratio_ledger_report = (
        governance_reports.release_residual_ratio_ledger_report
    )
    release_acceptance_certificate_report = (
        governance_reports.release_acceptance_certificate_report
    )
    material_delivery_reports = _build_release_gate_material_delivery_reports(
        checks=checks
    )
    material_schema_report = material_delivery_reports.material_schema_report
    material_repair_flow_report = (
        material_delivery_reports.material_repair_flow_report
    )
    fixed_layout_profile_report = (
        material_delivery_reports.fixed_layout_profile_report
    )
    report_artifact_drilldown_report = (
        material_delivery_reports.report_artifact_drilldown_report
    )
    delivery_preset_report = material_delivery_reports.delivery_preset_report
    delivery_execution_report = material_delivery_reports.delivery_execution_report
    formula_output_watermark_report = (
        material_delivery_reports.formula_output_watermark_report
    )
    maturity_upgrade_report = material_delivery_reports.maturity_upgrade_report
    dashboard_residual_reports = _build_release_gate_dashboard_residual_reports(
        checks=checks,
        input_source_report=input_source_report,
        count_profile_report=count_profile_report,
        residual_warning_governance_report=residual_warning_governance_report,
        terminal_release_exception_report=terminal_release_exception_report,
        boundary_maturity_release_envelope_report=(
            boundary_maturity_release_envelope_report
        ),
        release_residual_ratio_ledger_report=release_residual_ratio_ledger_report,
        maturity_upgrade_report=maturity_upgrade_report,
    )
    matrix_dashboard = dashboard_residual_reports.matrix_dashboard
    release_residual_explanation_report = (
        dashboard_residual_reports.release_residual_explanation_report
    )
    release_governance_export_gate = (
        _build_release_governance_export_evidence_gate(
            checks=checks,
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
            boundary_maturity_release_envelope_report=(
                boundary_maturity_release_envelope_report
            ),
            retained_gap_exit_criteria_report=retained_gap_exit_criteria_report,
            release_residual_ratio_ledger_report=release_residual_ratio_ledger_report,
            release_residual_explanation_report=release_residual_explanation_report,
            release_closure_ledger_report=release_closure_ledger_report,
            release_acceptance_certificate_report=release_acceptance_certificate_report,
        )
    )
    release_governance_export_script_evidence = (
        release_governance_export_gate.evidence
    )
    release_governance_export_script_counts = release_governance_export_gate.counts
    matrix_drilldown = build_scene_matrix_drilldown_report(project_root=ROOT)
    matrix_drilldown_issues = matrix_drilldown.issues
    checks["scene_matrix_drilldown"] = _issue_check(matrix_drilldown_issues)

    failed = {
        check_id: check
        for check_id, check in checks.items()
        if check["status"] != "passed"
    }
    user_journey_counts = user_journey_fixture_report.to_payload()["counts"]
    release_governance_payload_entries = scene_release_governance_payload_entries(
        locals()
    )
    release_governance_summary_counts = scene_release_governance_count_entries(
        locals(),
        SCENE_RELEASE_GOVERNANCE_SUMMARY_COUNT_SPECS,
    )
    release_governance_detail_counts = (
        scene_release_governance_detail_count_entries(locals())
    )
    matrix_dashboard_payload = matrix_dashboard.to_payload()
    matrix_drilldown_payload = matrix_drilldown.to_payload()
    matrix_dashboard_counts = _scene_matrix_dashboard_release_gate_counts(
        matrix_dashboard_payload
    )
    matrix_drilldown_counts = _prefixed_payload_count_entries(
        matrix_drilldown_payload,
        prefix="scene_matrix_drilldown",
        count_ids=SCENE_MATRIX_DRILLDOWN_RELEASE_GATE_COUNT_IDS,
    )
    payload = {
        "status": "passed" if not failed else "failed",
        "checks": checks,
        "failed_check_ids": list(failed),
        "counts": {
            "coverage_pack_count": len(SCENE_COVERAGE_PACK_MAP),
            "sample_fixture_count": len(list_scene_sample_fixtures()),
            "required_sample_pack_count": len(REQUIRED_SAMPLE_PACK_IDS),
            "high_frequency_request_sample_count": len(
                list_high_frequency_request_samples()
            ),
            "request_cell_count": request_cell_summary.cell_count,
            "request_cell_browser_visible_count": request_cell_browser.visible_count,
            "request_cell_fixture_cell_count": request_cell_summary.fixture_cell_count,
            "request_cell_negative_control_count": (
                request_cell_summary.negative_control_count
            ),
            "request_cell_family_proxy_count": (
                request_cell_summary.family_proxy_count
            ),
            "product_readiness_subject_count": len(
                list_scene_product_readiness_specs()
            ),
            "static_closed_but_not_green_count": len(
                static_closed_but_not_green_specs()
            ),
            **release_governance_summary_counts,
            "gap_domain_classified_count": maturity_upgrade_report.gap_domain_count,
            "high_frequency_completeness_pack_count": (
                completeness_report.pack_count
            ),
            "high_frequency_completeness_ready_pack_count": (
                completeness_report.ready_pack_count
            ),
            "high_frequency_completeness_warning_count": (
                completeness_report.warning_count
            ),
            "high_frequency_task_lexicon_task_count": (
                task_lexicon_report.task_count
            ),
            "high_frequency_task_lexicon_phrase_count": (
                task_lexicon_report.phrase_count
            ),
            "high_frequency_task_lexicon_negative_task_count": (
                task_lexicon_report.negative_task_count
            ),
            "high_frequency_task_lexicon_ambiguous_task_count": (
                task_lexicon_report.ambiguous_task_count
            ),
            "high_frequency_task_lexicon_issue_count": (
                task_lexicon_report.issue_count
            ),
            "scene_ambiguous_boundary_count": (
                ambiguous_boundary_report.boundary_count
            ),
            "scene_ambiguous_boundary_pack_pair_count": (
                ambiguous_boundary_report.pack_pair_count
            ),
            "scene_ambiguous_boundary_fixture_backed_count": (
                ambiguous_boundary_report.fixture_backed_count
            ),
            "scene_ambiguous_boundary_issue_count": (
                ambiguous_boundary_report.issue_count
            ),
            "scene_ambiguous_boundary_missing_source_evidence_count": (
                ambiguous_boundary_report.missing_source_evidence_count
            ),
            "scene_ambiguity_clarification_count": (
                ambiguity_clarification_report.clarification_count
            ),
            "scene_ambiguity_clarification_ready_count": (
                ambiguity_clarification_report.ready_clarification_count
            ),
            "scene_ambiguity_clarification_candidate_route_count": (
                ambiguity_clarification_report.candidate_route_count
            ),
            "scene_ambiguity_clarification_candidate_pack_count": (
                ambiguity_clarification_report.candidate_pack_count
            ),
            "scene_ambiguity_clarification_fixture_backed_count": (
                ambiguity_clarification_report.fixture_backed_count
            ),
            "scene_ambiguity_clarification_issue_count": (
                ambiguity_clarification_report.issue_count
            ),
            "scene_ambiguity_clarification_warning_count": (
                ambiguity_clarification_report.warning_count
            ),
            "scene_ambiguity_clarification_missing_source_evidence_count": (
                ambiguity_clarification_report.missing_source_evidence_count
            ),
            "scene_import_handoff_count": import_handoff_report.handoff_count,
            "scene_import_handoff_ready_count": (
                import_handoff_report.ready_handoff_count
            ),
            "scene_import_handoff_target_pack_count": (
                import_handoff_report.target_pack_count
            ),
            "scene_import_handoff_fallback_strategy_count": (
                import_handoff_report.fallback_strategy_count
            ),
            "scene_import_handoff_issue_count": import_handoff_report.issue_count,
            "scene_import_handoff_missing_source_evidence_count": (
                import_handoff_report.missing_source_evidence_count
            ),
            "scene_input_source_family_count": input_source_report.family_count,
            "scene_input_source_ready_family_count": (
                input_source_report.ready_family_count
            ),
            "scene_input_source_boundary_family_count": (
                input_source_report.boundary_family_count
            ),
            "scene_input_source_pack_count": input_source_report.pack_count,
            "scene_input_source_input_pack_count": (
                input_source_report.input_pack_count
            ),
            "scene_input_source_ready_input_pack_count": (
                input_source_report.ready_input_pack_count
            ),
            "scene_input_source_accepted_format_count": (
                input_source_report.accepted_format_count
            ),
            "scene_input_source_structured_format_count": (
                input_source_report.structured_format_count
            ),
            "scene_input_source_material_required_family_count": (
                input_source_report.material_required_family_count
            ),
            "scene_input_source_markdown_enabled_family_count": (
                input_source_report.markdown_enabled_family_count
            ),
            "scene_input_source_latex_fragment_family_count": (
                input_source_report.latex_fragment_family_count
            ),
            "scene_input_source_render_source_count": (
                input_source_report.render_source_count
            ),
            "scene_input_source_target_template_count": (
                input_source_report.target_template_count
            ),
            "scene_input_source_boundary_input_source_count": (
                input_source_report.boundary_input_source_count
            ),
            "scene_input_source_format_count": input_source_report.format_count,
            "scene_input_source_issue_count": input_source_report.issue_count,
            "scene_input_source_warning_count": input_source_report.warning_count,
            "scene_input_source_missing_source_evidence_count": (
                input_source_report.missing_source_evidence_count
            ),
            "scene_family_subscene_family_count": (
                family_subscene_report.family_count
            ),
            "scene_family_subscene_issue_count": (
                family_subscene_report.issue_count
            ),
            "scene_family_subscene_warning_count": (
                family_subscene_report.warning_count
            ),
            "scene_family_subscene_request_cell_count": (
                family_subscene_report.request_cell_count
            ),
            "scene_family_fixture_depth_family_count": (
                family_fixture_depth_report.family_count
            ),
            "scene_family_fixture_depth_p1_family_count": (
                family_fixture_depth_report.p1_family_count
            ),
            "scene_family_fixture_depth_p1_ready_count": (
                family_fixture_depth_report.p1_ready_count
            ),
            "scene_family_fixture_depth_independent_family_count": (
                family_fixture_depth_report.independent_family_fixture_count
            ),
            "scene_family_fixture_depth_manual_boundary_family_count": (
                family_fixture_depth_report.manual_boundary_fixture_family_count
            ),
            "scene_family_fixture_depth_issue_count": (
                family_fixture_depth_report.issue_count
            ),
            "scene_family_fixture_depth_missing_source_evidence_count": (
                family_fixture_depth_report.missing_source_evidence_count
            ),
            "scene_control_consistency_contract_count": (
                scene_control_report.contract_count
            ),
            "scene_control_consistency_issue_count": (
                scene_control_report.issue_count
            ),
            "scene_control_runtime_control_count": (
                scene_control_runtime_report.runtime_control_count
            ),
            "scene_control_runtime_ready_control_count": (
                scene_control_runtime_report.ready_runtime_control_count
            ),
            "scene_control_runtime_contract_link_count": (
                scene_control_runtime_report.control_contract_link_count
            ),
            "scene_control_runtime_scene_surface_count": (
                scene_control_runtime_report.scene_surface_count
            ),
            "scene_control_runtime_template_surface_count": (
                scene_control_runtime_report.template_surface_count
            ),
            "scene_control_runtime_shared_component_count": (
                scene_control_runtime_report.shared_component_count
            ),
            "scene_control_runtime_consumer_count": (
                scene_control_runtime_report.runtime_consumer_count
            ),
            "scene_control_runtime_issue_count": (
                scene_control_runtime_report.issue_count
            ),
            "scene_control_runtime_missing_source_evidence_count": (
                scene_control_runtime_report.missing_source_evidence_count
            ),
            "scene_count_profile_profile_count": count_profile_report.profile_count,
            "scene_count_profile_referenced_profile_count": (
                count_profile_report.referenced_profile_count
            ),
            "scene_count_profile_rule_source_profile_count": (
                count_profile_report.rule_source_profile_count
            ),
            "scene_count_profile_registry_only_profile_count": (
                count_profile_report.registry_only_profile_count
            ),
            "scene_count_profile_rule_source_only_profile_count": (
                count_profile_report.rule_source_only_profile_count
            ),
            "scene_count_profile_section_limit_profile_count": (
                count_profile_report.section_limit_profile_count
            ),
            "scene_count_profile_unique_scope_count": (
                count_profile_report.unique_scope_count
            ),
            "scene_count_profile_unique_primary_metric_count": (
                count_profile_report.unique_primary_metric_count
            ),
            "scene_count_profile_family_count": count_profile_report.family_count,
            "scene_count_profile_ready_family_count": (
                count_profile_report.ready_family_count
            ),
            "scene_count_profile_boundary_family_count": (
                count_profile_report.boundary_family_count
            ),
            "scene_count_profile_accounted_family_count": (
                count_profile_report.accounted_family_count
            ),
            "scene_count_profile_pack_count": count_profile_report.pack_count,
            "scene_count_profile_count_profile_pack_count": (
                count_profile_report.count_profile_pack_count
            ),
            "scene_count_profile_ready_count_profile_pack_count": (
                count_profile_report.ready_count_profile_pack_count
            ),
            "scene_count_profile_runtime_consumer_count": (
                count_profile_report.runtime_consumer_count
            ),
            "scene_count_profile_report_surface_count": (
                count_profile_report.report_surface_count
            ),
            "scene_count_profile_issue_count": count_profile_report.issue_count,
            "scene_count_profile_warning_count": count_profile_report.warning_count,
            "scene_count_profile_missing_source_evidence_count": (
                count_profile_report.missing_source_evidence_count
            ),
            "scene_word_risk_surface_count": word_risk_report.surface_count,
            "scene_word_risk_issue_count": word_risk_report.issue_count,
            "scene_word_risk_preflight_surface_count": (
                word_risk_report.preflight_surface_count
            ),
            "scene_word_risk_sample_fixture_link_count": (
                word_risk_report.sample_fixture_link_count
            ),
            "scene_object_preflight_action_target_count": (
                object_preflight_action_report.target_count
            ),
            "scene_object_preflight_action_ready_target_count": (
                object_preflight_action_report.ready_target_count
            ),
            "scene_object_preflight_action_warning_target_count": (
                object_preflight_action_report.warning_target_count
            ),
            "scene_object_preflight_action_high_risk_target_count": (
                object_preflight_action_report.high_risk_target_count
            ),
            "scene_object_preflight_action_fixture_backed_target_count": (
                object_preflight_action_report.fixture_backed_target_count
            ),
            "scene_object_preflight_action_blockable_target_count": (
                object_preflight_action_report.blockable_target_count
            ),
            "scene_object_preflight_action_skippable_target_count": (
                object_preflight_action_report.skippable_target_count
            ),
            "scene_object_preflight_action_manual_confirmation_target_count": (
                object_preflight_action_report.manual_confirmation_target_count
            ),
            "scene_object_preflight_action_family_count": (
                object_preflight_action_report.family_count
            ),
            "scene_object_preflight_action_ready_family_count": (
                object_preflight_action_report.ready_family_count
            ),
            "scene_object_preflight_action_boundary_family_count": (
                object_preflight_action_report.boundary_family_count
            ),
            "scene_object_preflight_action_strict_family_count": (
                object_preflight_action_report.strict_family_count
            ),
            "scene_object_preflight_action_family_with_fixture_count": (
                object_preflight_action_report.family_with_fixture_count
            ),
            "scene_object_preflight_action_issue_count": (
                object_preflight_action_report.issue_count
            ),
            "scene_object_preflight_action_warning_count": (
                object_preflight_action_report.warning_count
            ),
            "scene_object_preflight_action_missing_source_evidence_count": (
                object_preflight_action_report.missing_source_evidence_count
            ),
            "scene_user_journey_pack_count": (
                user_journey_fixture_report.pack_count
            ),
            "scene_user_journey_ready_pack_count": (
                user_journey_fixture_report.ready_pack_count
            ),
            "scene_user_journey_warning_pack_count": (
                user_journey_fixture_report.warning_pack_count
            ),
            "scene_user_journey_family_count": (
                user_journey_fixture_report.family_count
            ),
            "scene_user_journey_ready_family_count": (
                user_journey_fixture_report.ready_family_count
            ),
            "scene_user_journey_warning_family_count": (
                user_journey_fixture_report.warning_family_count
            ),
            "scene_user_journey_p1_family_count": (
                user_journey_fixture_report.p1_family_count
            ),
            "scene_user_journey_p1_ready_family_count": (
                user_journey_fixture_report.p1_ready_family_count
            ),
            "scene_user_journey_path_count": (
                user_journey_fixture_report.path_count
            ),
            "scene_user_journey_success_path_count": int(
                user_journey_counts["success_path_count"]
            ),
            "scene_user_journey_degraded_path_count": int(
                user_journey_counts["degraded_path_count"]
            ),
            "scene_user_journey_failure_path_count": int(
                user_journey_counts["failure_path_count"]
            ),
            "scene_user_journey_manual_boundary_path_count": int(
                user_journey_counts["manual_boundary_path_count"]
            ),
            "scene_user_journey_ambiguous_decision_path_count": int(
                user_journey_counts["ambiguous_decision_path_count"]
            ),
            "scene_user_journey_handoff_path_count": int(
                user_journey_counts["handoff_path_count"]
            ),
            "scene_user_journey_negative_control_path_count": int(
                user_journey_counts["negative_control_path_count"]
            ),
            "scene_user_journey_issue_count": (
                user_journey_fixture_report.issue_count
            ),
            "scene_user_journey_warning_count": (
                user_journey_fixture_report.warning_count
            ),
            "scene_user_journey_missing_source_evidence_count": (
                user_journey_fixture_report.missing_source_evidence_count
            ),
            "scene_business_capability_matrix_count": (
                business_capability_matrix_report.capability_count
            ),
            "scene_business_capability_matrix_ready_count": (
                business_capability_matrix_report.ready_capability_count
            ),
            "scene_business_capability_matrix_high_priority_count": (
                business_capability_matrix_report.high_priority_capability_count
            ),
            "scene_business_capability_matrix_high_priority_ready_count": (
                business_capability_matrix_report.high_priority_ready_count
            ),
            "scene_business_capability_matrix_boundary_count": (
                business_capability_matrix_report.boundary_capability_count
            ),
            "scene_business_capability_matrix_manual_gate_count": (
                business_capability_matrix_report.manual_gate_capability_count
            ),
            "scene_business_capability_matrix_missing_journey_group_count": (
                business_capability_matrix_report.missing_journey_group_count
            ),
            "scene_business_capability_matrix_adopted_external_record_count": (
                business_capability_matrix_report.adopted_external_record_count
            ),
            "scene_business_capability_matrix_issue_count": (
                business_capability_matrix_report.issue_count
            ),
            "scene_business_capability_matrix_warning_count": (
                business_capability_matrix_report.warning_count
            ),
            "scene_business_capability_matrix_missing_source_evidence_count": (
                business_capability_matrix_report.missing_source_evidence_count
            ),
            "scene_boundary_capability_count": (
                boundary_capability_report.capability_count
            ),
            "scene_boundary_capability_ready_count": (
                boundary_capability_report.ready_capability_count
            ),
            "scene_boundary_capability_professional_count": (
                boundary_capability_report.professional_capability_count
            ),
            "scene_boundary_capability_import_ai_count": (
                boundary_capability_report.import_ai_capability_count
            ),
            "scene_boundary_capability_fixture_count": (
                boundary_capability_report.fixture_count
            ),
            "scene_boundary_capability_report_expectation_count": (
                boundary_capability_report.report_expectation_count
            ),
            "scene_boundary_capability_ui_surface_count": (
                boundary_capability_report.ui_surface_count
            ),
            "scene_boundary_capability_risk_domain_count": (
                boundary_capability_report.risk_domain_count
            ),
            "scene_boundary_capability_decision_requirement_count": (
                boundary_capability_report.decision_requirement_count
            ),
            "scene_boundary_capability_external_receipt_count": (
                boundary_capability_report.external_receipt_count
            ),
            "scene_boundary_capability_release_guardrail_count": (
                boundary_capability_report.release_guardrail_count
            ),
            "scene_boundary_capability_issue_count": (
                boundary_capability_report.issue_count
            ),
            "scene_boundary_capability_missing_source_evidence_count": (
                boundary_capability_report.missing_source_evidence_count
            ),
            "scene_plugin_boundary_gate_count": (
                plugin_boundary_report.gate_count
            ),
            "scene_plugin_boundary_risk_domain_count": (
                plugin_boundary_report.risk_domain_count
            ),
            "scene_plugin_boundary_route_count": (
                plugin_boundary_report.route_count
            ),
            "scene_plugin_boundary_request_sample_count": (
                plugin_boundary_report.request_sample_count
            ),
            "scene_plugin_boundary_manual_fixture_count": (
                plugin_boundary_report.manual_fixture_count
            ),
            "scene_plugin_boundary_issue_count": (
                plugin_boundary_report.issue_count
            ),
            "scene_plugin_boundary_missing_source_evidence_count": (
                plugin_boundary_report.missing_source_evidence_count
            ),
            "scene_external_handoff_contract_count": (
                external_handoff_contract_report.contract_count
            ),
            "scene_external_handoff_contract_ready_count": (
                external_handoff_contract_report.ready_contract_count
            ),
            "scene_external_handoff_contract_pack_count": (
                external_handoff_contract_report.pack_contract_count
            ),
            "scene_external_handoff_contract_family_count": (
                external_handoff_contract_report.family_contract_count
            ),
            "scene_external_handoff_contract_plugin_gate_count": (
                external_handoff_contract_report.plugin_gate_count
            ),
            "scene_external_handoff_contract_target_plugin_count": (
                external_handoff_contract_report.target_plugin_count
            ),
            "scene_external_handoff_contract_risk_domain_count": (
                external_handoff_contract_report.risk_domain_count
            ),
            "scene_external_handoff_contract_report_count": (
                external_handoff_contract_report.report_count
            ),
            "scene_external_handoff_contract_ui_surface_count": (
                external_handoff_contract_report.ui_surface_count
            ),
            "scene_external_handoff_contract_fixture_count": (
                external_handoff_contract_report.fixture_count
            ),
            "scene_external_handoff_contract_status_state_count": (
                external_handoff_contract_report.status_state_count
            ),
            "scene_external_handoff_contract_failure_policy_count": (
                external_handoff_contract_report.failure_policy_count
            ),
            "scene_external_handoff_contract_issue_count": (
                external_handoff_contract_report.issue_count
            ),
            "scene_external_handoff_contract_missing_source_evidence_count": (
                external_handoff_contract_report.missing_source_evidence_count
            ),
            **release_governance_detail_counts,
            "scene_material_schema_family_count": (
                material_schema_report.family_count
            ),
            "scene_material_schema_material_family_count": (
                material_schema_report.material_family_count
            ),
            "scene_material_schema_ready_material_family_count": (
                material_schema_report.ready_material_family_count
            ),
            "scene_material_schema_pack_count": (
                material_schema_report.pack_count
            ),
            "scene_material_schema_material_pack_count": (
                material_schema_report.material_pack_count
            ),
            "scene_material_schema_ready_material_pack_count": (
                material_schema_report.ready_material_pack_count
            ),
            "scene_material_schema_schema_count": (
                material_schema_report.schema_count
            ),
            "scene_material_schema_referenced_schema_count": (
                material_schema_report.referenced_schema_count
            ),
            "scene_material_schema_registry_only_schema_count": (
                material_schema_report.registry_only_schema_count
            ),
            "scene_material_schema_required_field_count": (
                material_schema_report.required_field_count
            ),
            "scene_material_schema_required_asset_count": (
                material_schema_report.required_asset_count
            ),
            "scene_material_schema_issue_count": (
                material_schema_report.issue_count
            ),
            "scene_material_schema_warning_count": (
                material_schema_report.warning_count
            ),
            "scene_material_schema_missing_source_evidence_count": (
                material_schema_report.missing_source_evidence_count
            ),
            "scene_material_repair_flow_count": (
                material_repair_flow_report.flow_count
            ),
            "scene_material_repair_flow_ready_count": (
                material_repair_flow_report.ready_flow_count
            ),
            "scene_material_repair_flow_capability_count": (
                material_repair_flow_report.capability_count
            ),
            "scene_material_repair_flow_signal_count": (
                material_repair_flow_report.material_signal_count
            ),
            "scene_material_repair_flow_target_type_count": (
                material_repair_flow_report.repair_target_type_count
            ),
            "scene_material_repair_flow_runtime_surface_count": (
                material_repair_flow_report.runtime_surface_count
            ),
            "scene_material_repair_flow_ui_surface_count": (
                material_repair_flow_report.ui_surface_count
            ),
            "scene_material_repair_flow_test_evidence_count": (
                material_repair_flow_report.test_evidence_count
            ),
            "scene_material_repair_flow_covered_pack_count": (
                material_repair_flow_report.covered_pack_count
            ),
            "scene_material_repair_flow_covered_family_count": (
                material_repair_flow_report.covered_family_count
            ),
            "scene_material_repair_flow_issue_count": (
                material_repair_flow_report.issue_count
            ),
            "scene_material_repair_flow_missing_source_evidence_count": (
                material_repair_flow_report.missing_source_evidence_count
            ),
            "scene_fixed_layout_profile_channel_count": (
                fixed_layout_profile_report.profile_channel_count
            ),
            "scene_fixed_layout_profile_ready_channel_count": (
                fixed_layout_profile_report.ready_profile_channel_count
            ),
            "scene_fixed_layout_profile_surface_count": (
                fixed_layout_profile_report.fixed_layout_surface_count
            ),
            "scene_fixed_layout_profile_ooxml_touchpoint_count": (
                fixed_layout_profile_report.word_ooxml_touchpoint_count
            ),
            "scene_fixed_layout_profile_runtime_surface_count": (
                fixed_layout_profile_report.runtime_surface_count
            ),
            "scene_fixed_layout_profile_ui_surface_count": (
                fixed_layout_profile_report.ui_surface_count
            ),
            "scene_fixed_layout_profile_report_surface_count": (
                fixed_layout_profile_report.report_surface_count
            ),
            "scene_fixed_layout_profile_repair_target_type_count": (
                fixed_layout_profile_report.repair_target_type_count
            ),
            "scene_fixed_layout_profile_test_evidence_count": (
                fixed_layout_profile_report.test_evidence_count
            ),
            "scene_fixed_layout_profile_covered_pack_count": (
                fixed_layout_profile_report.covered_pack_count
            ),
            "scene_fixed_layout_profile_covered_family_count": (
                fixed_layout_profile_report.covered_family_count
            ),
            "scene_fixed_layout_profile_issue_count": (
                fixed_layout_profile_report.issue_count
            ),
            "scene_fixed_layout_profile_missing_source_evidence_count": (
                fixed_layout_profile_report.missing_source_evidence_count
            ),
            "scene_report_artifact_drilldown_channel_count": (
                report_artifact_drilldown_report.drilldown_channel_count
            ),
            "scene_report_artifact_drilldown_ready_channel_count": (
                report_artifact_drilldown_report.ready_drilldown_channel_count
            ),
            "scene_report_artifact_drilldown_artifact_kind_count": (
                report_artifact_drilldown_report.artifact_kind_count
            ),
            "scene_report_artifact_drilldown_runtime_surface_count": (
                report_artifact_drilldown_report.runtime_surface_count
            ),
            "scene_report_artifact_drilldown_ui_surface_count": (
                report_artifact_drilldown_report.ui_surface_count
            ),
            "scene_report_artifact_drilldown_report_surface_count": (
                report_artifact_drilldown_report.report_surface_count
            ),
            "scene_report_artifact_drilldown_repair_target_type_count": (
                report_artifact_drilldown_report.repair_target_type_count
            ),
            "scene_report_artifact_drilldown_test_evidence_count": (
                report_artifact_drilldown_report.test_evidence_count
            ),
            "scene_report_artifact_drilldown_covered_pack_count": (
                report_artifact_drilldown_report.covered_pack_count
            ),
            "scene_report_artifact_drilldown_covered_family_count": (
                report_artifact_drilldown_report.covered_family_count
            ),
            "scene_report_artifact_drilldown_issue_count": (
                report_artifact_drilldown_report.issue_count
            ),
            "scene_report_artifact_drilldown_missing_source_evidence_count": (
                report_artifact_drilldown_report.missing_source_evidence_count
            ),
            "scene_delivery_preset_family_count": (
                delivery_preset_report.family_count
            ),
            "scene_delivery_preset_ready_family_count": (
                delivery_preset_report.ready_family_count
            ),
            "scene_delivery_preset_boundary_family_count": (
                delivery_preset_report.boundary_family_count
            ),
            "scene_delivery_preset_accounted_family_count": (
                delivery_preset_report.accounted_family_count
            ),
            "scene_delivery_preset_pack_count": (
                delivery_preset_report.pack_count
            ),
            "scene_delivery_preset_delivery_pack_count": (
                delivery_preset_report.delivery_pack_count
            ),
            "scene_delivery_preset_ready_delivery_pack_count": (
                delivery_preset_report.ready_delivery_pack_count
            ),
            "scene_delivery_preset_boundary_delivery_pack_count": (
                delivery_preset_report.boundary_delivery_pack_count
            ),
            "scene_delivery_preset_accounted_delivery_pack_count": (
                delivery_preset_report.accounted_delivery_pack_count
            ),
            "scene_delivery_preset_unique_preset_count": (
                delivery_preset_report.delivery_preset_count
            ),
            "scene_delivery_preset_final_docx_preset_count": (
                delivery_preset_report.final_docx_preset_count
            ),
            "scene_delivery_preset_compare_docx_preset_count": (
                delivery_preset_report.compare_docx_preset_count
            ),
            "scene_delivery_preset_report_only_preset_count": (
                delivery_preset_report.report_only_preset_count
            ),
            "scene_delivery_preset_material_package_preset_count": (
                delivery_preset_report.material_package_preset_count
            ),
            "scene_delivery_preset_structured_intermediate_preset_count": (
                delivery_preset_report.structured_intermediate_preset_count
            ),
            "scene_delivery_preset_content_visibility_rule_count": (
                delivery_preset_report.content_visibility_rule_count
            ),
            "scene_delivery_preset_issue_count": (
                delivery_preset_report.issue_count
            ),
            "scene_delivery_preset_warning_count": (
                delivery_preset_report.warning_count
            ),
            "scene_delivery_preset_missing_source_evidence_count": (
                delivery_preset_report.missing_source_evidence_count
            ),
            "scene_delivery_execution_channel_count": (
                delivery_execution_report.execution_channel_count
            ),
            "scene_delivery_execution_ready_channel_count": (
                delivery_execution_report.ready_execution_channel_count
            ),
            "scene_delivery_execution_required_output_signal_count": (
                delivery_execution_report.required_output_signal_count
            ),
            "scene_delivery_execution_payload_key_count": (
                delivery_execution_report.payload_key_count
            ),
            "scene_delivery_execution_runtime_surface_count": (
                delivery_execution_report.runtime_surface_count
            ),
            "scene_delivery_execution_report_surface_count": (
                delivery_execution_report.report_surface_count
            ),
            "scene_delivery_execution_ui_surface_count": (
                delivery_execution_report.ui_surface_count
            ),
            "scene_delivery_execution_test_evidence_count": (
                delivery_execution_report.test_evidence_count
            ),
            "scene_delivery_execution_covered_pack_count": (
                delivery_execution_report.covered_pack_count
            ),
            "scene_delivery_execution_covered_family_count": (
                delivery_execution_report.covered_family_count
            ),
            "scene_delivery_execution_issue_count": (
                delivery_execution_report.issue_count
            ),
            "scene_delivery_execution_missing_source_evidence_count": (
                delivery_execution_report.missing_source_evidence_count
            ),
            "scene_formula_output_watermark_capability_count": (
                formula_output_watermark_report.capability_count
            ),
            "scene_formula_output_watermark_ready_capability_count": (
                formula_output_watermark_report.ready_capability_count
            ),
            "scene_formula_output_watermark_family_count": (
                formula_output_watermark_report.family_count
            ),
            "scene_formula_output_watermark_ready_family_count": (
                formula_output_watermark_report.ready_family_count
            ),
            "scene_formula_output_watermark_boundary_family_count": (
                formula_output_watermark_report.boundary_family_count
            ),
            "scene_formula_output_watermark_accounted_family_count": (
                formula_output_watermark_report.accounted_family_count
            ),
            "scene_formula_output_watermark_formula_family_count": (
                formula_output_watermark_report.formula_family_count
            ),
            "scene_formula_output_watermark_output_family_count": (
                formula_output_watermark_report.output_family_count
            ),
            "scene_formula_output_watermark_watermark_family_count": (
                formula_output_watermark_report.watermark_family_count
            ),
            "scene_formula_output_watermark_plugin_gate_count": (
                formula_output_watermark_report.plugin_gate_count
            ),
            "scene_formula_output_watermark_control_contract_count": (
                formula_output_watermark_report.control_contract_count
            ),
            "scene_formula_output_watermark_parameter_path_count": (
                formula_output_watermark_report.parameter_path_count
            ),
            "scene_formula_output_watermark_template_baseline_path_count": (
                formula_output_watermark_report.template_baseline_path_count
            ),
            "scene_formula_output_watermark_issue_count": (
                formula_output_watermark_report.issue_count
            ),
            "scene_formula_output_watermark_warning_count": (
                formula_output_watermark_report.warning_count
            ),
            "scene_formula_output_watermark_missing_source_evidence_count": (
                formula_output_watermark_report.missing_source_evidence_count
            ),
            "scene_product_maturity_upgrade_subject_count": (
                maturity_upgrade_report.subject_count
            ),
            "scene_product_maturity_upgrade_green_subject_count": (
                maturity_upgrade_report.green_subject_count
            ),
            "scene_product_maturity_upgrade_l5_blocked_subject_count": (
                maturity_upgrade_report.l5_blocked_subject_count
            ),
            "scene_product_maturity_upgrade_l3_subject_count": (
                maturity_upgrade_report.l3_subject_count
            ),
            "scene_product_maturity_upgrade_l4_subject_count": (
                maturity_upgrade_report.l4_subject_count
            ),
            "scene_product_maturity_upgrade_boundary_subject_count": (
                maturity_upgrade_report.boundary_subject_count
            ),
            "scene_product_maturity_upgrade_gap_count": (
                maturity_upgrade_report.gap_count
            ),
            "scene_product_maturity_upgrade_gap_domain_count": (
                maturity_upgrade_report.gap_domain_count
            ),
            "scene_product_maturity_upgrade_issue_count": (
                maturity_upgrade_report.issue_count
            ),
            "scene_product_maturity_upgrade_warning_count": (
                maturity_upgrade_report.warning_count
            ),
            "scene_product_maturity_upgrade_missing_source_evidence_count": (
                maturity_upgrade_report.missing_source_evidence_count
            ),
            **matrix_dashboard_counts,
            **matrix_drilldown_counts,
        },
        "request_cell_summary": request_cell_summary.to_payload(),
        "request_cell_registry_browser": request_cell_browser.to_payload(),
        "high_frequency_completeness_audit": completeness_report.to_payload(),
        "high_frequency_task_lexicon_audit": task_lexicon_report.to_payload(),
        "scene_ambiguous_boundary_audit": ambiguous_boundary_report.to_payload(),
        "scene_ambiguity_clarification_ui_audit": (
            ambiguity_clarification_report.to_payload()
        ),
        "scene_import_handoff_audit": import_handoff_report.to_payload(),
        "scene_input_source_audit": input_source_report.to_payload(),
        "scene_family_subscene_audit": family_subscene_report.to_payload(),
        "scene_family_fixture_depth_audit": family_fixture_depth_report.to_payload(),
        "scene_control_consistency_audit": scene_control_report.to_payload(),
        "scene_control_runtime_consistency_audit": (
            scene_control_runtime_report.to_payload()
        ),
        "scene_count_profile_audit": count_profile_report.to_payload(),
        "scene_word_risk_closure_audit": word_risk_report.to_payload(),
        "scene_object_preflight_action_audit": (
            object_preflight_action_report.to_payload()
        ),
        "scene_user_journey_fixture_audit": (
            user_journey_fixture_report.to_payload()
        ),
        "scene_business_capability_matrix_audit": (
            business_capability_matrix_report.to_payload()
        ),
        "scene_boundary_capability_matrix": (
            boundary_capability_report.to_payload()
        ),
        "scene_plugin_boundary_confirmation_audit": (
            plugin_boundary_report.to_payload()
        ),
        "scene_external_handoff_contract_audit": (
            external_handoff_contract_report.to_payload()
        ),
        **release_governance_payload_entries,
        "scene_release_governance_export_script_evidence": (
            release_governance_export_script_evidence
        ),
        "scene_material_schema_audit": material_schema_report.to_payload(),
        "scene_material_repair_flow_audit": (
            material_repair_flow_report.to_payload()
        ),
        "scene_fixed_layout_profile_audit": (
            fixed_layout_profile_report.to_payload()
        ),
        "scene_report_artifact_drilldown_audit": (
            report_artifact_drilldown_report.to_payload()
        ),
        "scene_delivery_preset_audit": delivery_preset_report.to_payload(),
        "scene_delivery_preset_execution_audit": (
            delivery_execution_report.to_payload()
        ),
        "scene_formula_output_watermark_audit": (
            formula_output_watermark_report.to_payload()
        ),
        "scene_product_maturity_upgrade_audit": (
            maturity_upgrade_report.to_payload()
        ),
        "scene_matrix_dashboard": matrix_dashboard_payload,
        "scene_matrix_drilldown": matrix_drilldown_payload,
        "fixture_library_output_dir": str(output_dir),
    }
    if _pytest_release_gate_lightweight_enabled():
        _PYTEST_RELEASE_GATE_PAYLOAD_CACHE = copy.deepcopy(payload)
    return payload


def _hard_gate_issues(request_cell_summary) -> list[str]:
    issues: list[str] = []
    if request_cell_summary.family_proxy_count:
        issues.append("Request-cell family proxy count must be zero for release.")
    if (
        request_cell_summary.fixture_cell_count
        + request_cell_summary.negative_control_count
        != request_cell_summary.cell_count
    ):
        issues.append(
            "Every request cell must either have fixture evidence or be a negative control."
        )
    if set(request_cell_summary.pack_ids) != set(REQUIRED_SAMPLE_PACK_IDS):
        issues.append("Request-cell pack set does not match required sample packs.")
    return issues


def _request_cell_browser_gate_issues(request_cell_summary, browser) -> list[str]:
    issues: list[str] = []
    if browser.total_count != request_cell_summary.cell_count:
        issues.append("Request-cell browser total count does not match summary.")
    if browser.visible_count != request_cell_summary.cell_count:
        issues.append("Unfiltered request-cell browser must show every cell.")
    if dict(browser.coverage_level_counts) != dict(
        request_cell_summary.coverage_level_counts
    ):
        issues.append("Request-cell browser coverage counts do not match summary.")
    if set(browser.pack_options) != set(request_cell_summary.pack_ids):
        issues.append("Request-cell browser pack options do not match summary packs.")
    negative = build_scene_request_cell_registry_browser(
        coverage_level="negative_control"
    )
    if negative.visible_count != request_cell_summary.negative_control_count:
        issues.append("Request-cell browser negative-control filter is inconsistent.")
    manual = build_scene_request_cell_registry_browser(
        coverage_level="manual_boundary_fixture"
    )
    if manual.visible_count != request_cell_summary.manual_boundary_count:
        issues.append("Request-cell browser manual-boundary filter is inconsistent.")
    unknown = build_scene_request_cell_registry_browser(
        query="unknown_stays_unmatched"
    )
    if unknown.visible_count != 1:
        issues.append("Request-cell browser query filter must expose the negative control.")
    return issues


def _issue_check(issues) -> dict[str, object]:
    issue_items = list(issues or [])
    return {
        "status": "passed" if not issue_items else "failed",
        "issue_count": len(issue_items),
        "issues": [_issue_payload(issue) for issue in issue_items[:20]],
    }


def _string_issue_check(issues: list[str]) -> dict[str, object]:
    return {
        "status": "passed" if not issues else "failed",
        "issue_count": len(issues),
        "issues": issues[:20],
    }


def _issue_payload(issue) -> dict[str, object]:
    if is_dataclass(issue):
        return asdict(issue)
    if isinstance(issue, dict):
        return dict(issue)
    return {"message": str(issue)}
