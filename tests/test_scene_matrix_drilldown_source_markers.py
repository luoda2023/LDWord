import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_matrix_drilldown_sources import (  # noqa: E402
    SCENE_MATRIX_DRILLDOWN_AUDIT_DOCS_PATH,
    SCENE_MATRIX_DRILLDOWN_CONFIG_SOURCE_PATH,
    SCENE_MATRIX_DRILLDOWN_EXPORT_SCRIPT_SOURCE_PATH,
    SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_SOURCE_PATH,
    SCENE_MATRIX_DRILLDOWN_RELEASE_ITEMS_SOURCE_PATH,
    SCENE_MATRIX_DRILLDOWN_RUNTIME_SOURCE_PATH,
    SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS,
    SCENE_MATRIX_DRILLDOWN_SUMMARY_PROJECTION_SOURCE_PATH,
    SCENE_MATRIX_DRILLDOWN_TEST_SOURCE_PATH,
)


def test_drilldown_sources_group_runtime_audit_source_markers():
    source = (
        ROOT / "src" / "config" / "scene_matrix_drilldown_sources.py"
    ).read_text(encoding="utf-8")
    expected_source_ids = (
        "scene_matrix_drilldown_item_row_identity_audit",
        "scene_matrix_drilldown_item_source_evidence_audit",
        "scene_matrix_drilldown_row_source_evidence_audit",
        "scene_matrix_drilldown_row_pack_family_registry_audit",
        "scene_matrix_drilldown_row_request_fixture_registry_audit",
        "scene_matrix_drilldown_row_count_delivery_registry_audit",
        "scene_matrix_drilldown_row_material_reference_audit",
        "scene_matrix_drilldown_row_input_object_word_registry_audit",
        "scene_matrix_drilldown_row_plugin_risk_maturity_registry_audit",
        "scene_matrix_drilldown_projection_test_reference_audit",
        "scene_matrix_drilldown_projection_source_reference_audit",
        "scene_matrix_drilldown_projection_surface_reference_audit",
        "scene_matrix_drilldown_projection_path_reference_audit",
        "scene_matrix_drilldown_projection_evidence_reference_audit",
        "scene_matrix_drilldown_projection_release_marker_reference_audit",
        "scene_matrix_drilldown_projection_release_link_reference_audit",
        "scene_matrix_drilldown_projection_retained_gap_exit_reference_audit",
        "scene_matrix_drilldown_projection_control_runtime_reference_audit",
        "scene_matrix_drilldown_projection_release_metric_reference_audit",
        "scene_matrix_drilldown_projection_external_handoff_reference_audit",
        "scene_matrix_drilldown_projection_report_delivery_marker_audit",
        "scene_matrix_drilldown_projection_requirement_dimension_reference_audit",
        "scene_matrix_drilldown_projection_target_plugin_reference_audit",
        "scene_matrix_drilldown_projection_formula_output_watermark_reference_audit",
    )
    runtime_source_ids = tuple(
        source_id
        for source_id, source_path, _markers in SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS
        if source_path == SCENE_MATRIX_DRILLDOWN_RUNTIME_SOURCE_PATH
    )

    assert "_drilldown_runtime_source_marker_entry" in source
    assert source.count(f'"{SCENE_MATRIX_DRILLDOWN_RUNTIME_SOURCE_PATH}"') == 1
    assert runtime_source_ids == expected_source_ids


def test_projection_profile_class_marker_uses_its_definition_module():
    marker_by_source_id = {
        source_id: (source_path, markers)
        for source_id, source_path, markers in SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS
    }

    definition_path, definition_markers = marker_by_source_id[
        "scene_matrix_drilldown_action_capability_projection_profile_audit"
    ]

    assert definition_path == SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_SOURCE_PATH
    assert "SceneMatrixDrilldownProjectionProfile" in definition_markers
    assert "SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP" in definition_markers


def test_drilldown_sources_group_historical_audit_doc_markers():
    source = (
        ROOT / "src" / "config" / "scene_matrix_drilldown_sources.py"
    ).read_text(encoding="utf-8")
    expected_source_ids = (
        "n2_402_acceptance_drilldown_trace_plan",
        "n2_407_residual_receipt_drilldown_plan",
        "n2_408_residual_receipt_export_plan",
        "n2_409_residual_receipt_source_summary_plan",
        "n2_410_drilldown_source_evidence_release_summary_plan",
        "n2_411_drilldown_source_summary_ready_total_plan",
        "n2_412_drilldown_export_source_summary_plan",
        "n2_413_drilldown_json_export_source_summary_plan",
        "n2_414_drilldown_source_evidence_payload_consistency_plan",
        "n2_415_drilldown_source_evidence_unique_id_plan",
        "n2_416_drilldown_item_row_unique_id_plan",
        "n2_417_drilldown_item_source_evidence_trace_plan",
        "n2_418_drilldown_row_source_evidence_trace_plan",
        "n2_419_drilldown_row_pack_family_registry_trace_plan",
        "n2_420_drilldown_row_request_fixture_registry_trace_plan",
        "n2_421_drilldown_row_count_delivery_registry_trace_plan",
        "n2_422_drilldown_row_material_reference_trace_plan",
        "n2_423_drilldown_row_input_object_word_registry_trace_plan",
        "n2_424_drilldown_row_plugin_risk_maturity_registry_trace_plan",
        "n2_425_drilldown_action_capability_projection_profile_trace_plan",
        "n2_426_drilldown_projection_test_reference_trace_plan",
        "n2_427_drilldown_projection_source_reference_trace_plan",
        "n2_428_drilldown_projection_surface_reference_trace_plan",
        "n2_429_drilldown_projection_path_reference_trace_plan",
        "n2_430_drilldown_projection_evidence_reference_trace_plan",
        "n2_431_drilldown_projection_release_marker_trace_plan",
        "n2_432_drilldown_projection_release_link_trace_plan",
        "n2_433_drilldown_projection_retained_gap_exit_reference_trace_plan",
        "n2_434_drilldown_projection_control_runtime_reference_trace_plan",
        "n2_435_drilldown_projection_release_metric_reference_trace_plan",
        "n2_436_drilldown_projection_external_handoff_reference_trace_plan",
        "n2_437_drilldown_projection_report_delivery_marker_trace_plan",
        "n2_438_drilldown_projection_requirement_dimension_trace_plan",
        "n2_439_drilldown_projection_target_plugin_trace_plan",
        "n2_440_drilldown_projection_formula_output_watermark_trace_plan",
    )
    historical_source_ids = tuple(
        source_id
        for source_id, source_path, _markers in SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS
        if source_id.startswith("n2_")
        and source_path.startswith(f"{SCENE_MATRIX_DRILLDOWN_AUDIT_DOCS_PATH}/")
    )

    assert "_drilldown_audit_doc_source_marker_entry" in source
    assert source.count(f'"{SCENE_MATRIX_DRILLDOWN_AUDIT_DOCS_PATH}"') == 1
    assert historical_source_ids == expected_source_ids


def test_drilldown_sources_group_config_path_source_markers():
    source = (
        ROOT / "src" / "config" / "scene_matrix_drilldown_sources.py"
    ).read_text(encoding="utf-8")
    expected_source_ids = (
        "scene_matrix_dashboard",
        "scene_ambiguity_clarification_ui_audit",
        "scene_user_journey_fixture_audit",
        "scene_external_handoff_contract_audit",
        "scene_business_capability_matrix_audit",
        "scene_control_runtime_consistency_audit",
        "scene_plugin_boundary_confirmation_audit",
        "scene_word_risk_closure_audit",
        "scene_import_handoff_audit",
        "scene_input_source_audit",
        "scene_object_preflight_action_audit",
        "scene_family_fixture_depth_audit",
        "scene_count_profile_audit",
        "scene_material_schema_audit",
        "scene_material_repair_flow_audit",
        "scene_fixed_layout_profile_audit",
        "scene_report_artifact_drilldown_audit",
        "scene_delivery_preset_audit",
        "scene_delivery_preset_execution_audit",
        "scene_formula_output_watermark_audit",
        "scene_product_maturity_upgrade_audit",
    )
    config_path_source_ids = tuple(
        source_id
        for source_id, source_path, _markers in SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS
        if source_id in expected_source_ids
        and source_path == f"{SCENE_MATRIX_DRILLDOWN_CONFIG_SOURCE_PATH}/{source_id}.py"
    )
    request_cell_source_path = next(
        source_path
        for source_id, source_path, _markers in SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS
        if source_id == "scene_request_cell_registry_browser"
    )

    assert "_scene_config_source_marker_entry" in source
    assert "_scene_config_audit_source_marker_entry" not in source
    assert source.count(f'"{SCENE_MATRIX_DRILLDOWN_CONFIG_SOURCE_PATH}"') == 1
    assert config_path_source_ids == expected_source_ids
    assert request_cell_source_path == "src/config/scene_request_cell_fixture_registry.py"


def test_drilldown_sources_group_middle_repeated_source_paths():
    source = (
        ROOT / "src" / "config" / "scene_matrix_drilldown_sources.py"
    ).read_text(encoding="utf-8")
    expected_groups = (
        (
            SCENE_MATRIX_DRILLDOWN_RELEASE_ITEMS_SOURCE_PATH,
            (
                "scene_matrix_drilldown_acceptance_receipt_projection",
                "scene_matrix_drilldown_residual_receipt_projection",
            ),
        ),
        (
            SCENE_MATRIX_DRILLDOWN_EXPORT_SCRIPT_SOURCE_PATH,
            (
                "scene_matrix_drilldown_export_receipt_projection",
                "scene_matrix_drilldown_export_source_summary_projection",
                "scene_matrix_drilldown_export_json_source_summary_projection",
            ),
        ),
        (
            SCENE_MATRIX_DRILLDOWN_TEST_SOURCE_PATH,
            (
                "scene_matrix_drilldown_source_evidence_payload_consistency_tests",
                "scene_matrix_drilldown_source_evidence_unique_id_tests",
            ),
        ),
        (
            SCENE_MATRIX_DRILLDOWN_SUMMARY_PROJECTION_SOURCE_PATH,
            (
                "scene_matrix_drilldown_source_summary_projection",
                "scene_matrix_drilldown_source_summary_readiness_projection",
            ),
        ),
    )

    for source_path, expected_source_ids in expected_groups:
        grouped_source_ids = tuple(
            source_id
            for source_id, marker_source_path, _markers in (
                SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS
            )
            if marker_source_path == source_path
        )

        assert source.count(f'"{source_path}"') == 1
        assert grouped_source_ids == expected_source_ids


def test_drilldown_sources_only_repeat_governed_source_paths():
    expected_repeated_source_path_counts = {
        SCENE_MATRIX_DRILLDOWN_RUNTIME_SOURCE_PATH: 24,
        SCENE_MATRIX_DRILLDOWN_RELEASE_ITEMS_SOURCE_PATH: 2,
        SCENE_MATRIX_DRILLDOWN_EXPORT_SCRIPT_SOURCE_PATH: 3,
        SCENE_MATRIX_DRILLDOWN_TEST_SOURCE_PATH: 2,
        SCENE_MATRIX_DRILLDOWN_SUMMARY_PROJECTION_SOURCE_PATH: 2,
    }
    source_paths = tuple(
        dict.fromkeys(
            source_path
            for _source_id, source_path, _markers in (
                SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS
            )
        )
    )
    repeated_source_path_counts = {
        source_path: sum(
            1
            for _source_id, marker_source_path, _markers in (
                SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS
            )
            if marker_source_path == source_path
        )
        for source_path in source_paths
    }
    repeated_source_path_counts = {
        source_path: count
        for source_path, count in repeated_source_path_counts.items()
        if count > 1
    }

    assert repeated_source_path_counts == expected_repeated_source_path_counts
