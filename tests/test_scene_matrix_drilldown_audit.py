import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_matrix_drilldown import (  # noqa: E402
    SceneMatrixDrilldownItem,
    SceneMatrixDrilldownReport,
    audit_scene_matrix_drilldown_report,
    build_scene_matrix_drilldown_report,
)
from tests._scene_matrix_drilldown_projection_references import (  # noqa: E402
    _projection_control_runtime_reference_map,
    _projection_evidence_reference_map,
    _projection_external_handoff_contract_reference_map,
    _projection_formula_output_watermark_reference_map,
    _projection_path_reference_map,
    _projection_release_link_reference_map,
    _projection_release_marker_reference_map,
    _projection_release_metric_reference_map,
    _projection_report_delivery_marker_reference_map,
    _projection_requirement_dimension_reference_map,
    _projection_retained_gap_exit_reference_map,
    _projection_source_reference_map,
    _projection_surface_reference_map,
    _projection_target_plugin_reference_map,
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
