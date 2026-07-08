import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_coverage_manifest import list_scene_coverage_packs  # noqa: E402
from src.config.scene_family_registry import list_planned_scene_families  # noqa: E402
from src.config.scene_matrix_drilldown import (  # noqa: E402
    REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS,
    SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP,
    audit_scene_matrix_drilldown_report,
    build_scene_matrix_drilldown_report,
)
from src.config.scene_request_cell_fixture_registry import (  # noqa: E402
    list_scene_request_cell_fixtures,
)
from src.config.scene_sample_fixture_registry import list_scene_sample_fixtures  # noqa: E402
from src.shared.engine.count_engine import list_count_profiles  # noqa: E402
from tests._scene_matrix_drilldown_projection_references import (  # noqa: E402
    _delivery_reference_ids,
    _external_handoff_contract_reference_ids,
    _input_render_reference_ids,
    _material_reference_ids,
    _maturity_gap_reference_ids,
    _object_preflight_reference_ids,
    _plugin_gate_reference_ids,
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
    _projection_source_reference_ids,
    _projection_source_reference_map,
    _projection_surface_reference_map,
    _projection_target_plugin_reference_map,
    _projection_test_reference_ids,
    _risk_domain_reference_ids,
    _target_plugin_reference_ids,
    _word_risk_surface_reference_ids,
)

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
