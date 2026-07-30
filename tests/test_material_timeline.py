from datetime import date, datetime

from src.shared.engine.material_timeline import (
    default_timeline_segment,
    default_timeline_plan,
    evenly_distributed_nodes,
    format_timeline_date,
    infer_timeline_date_format,
    normalize_timeline_plans,
    parse_timeline_date,
    resolve_timeline_plans,
    timeline_output_field_keys,
)


def _plan(nodes, **overrides):
    plan = default_timeline_plan()
    plan.update(overrides)
    plan["nodes"] = nodes
    return {"primary": plan}


def test_timeline_parses_clear_year_first_formats_and_formats_at_output_boundary():
    expected = date(2025, 10, 27)
    assert parse_timeline_date("2025-10-27") == expected
    assert parse_timeline_date("2025/10/27") == expected
    assert parse_timeline_date("2025.10.27") == expected
    assert parse_timeline_date("27/10/2025") == expected
    assert parse_timeline_date("2025年10月27日") == expected
    assert parse_timeline_date("2025 年 10 月 27 号") == expected
    assert parse_timeline_date("2025－10－27") == expected
    assert parse_timeline_date("20251027") == expected
    assert parse_timeline_date(datetime(2025, 10, 27, 12, 30)) == expected
    assert format_timeline_date(expected, "yyyy年M月d日") == "2025年10月27日"
    assert format_timeline_date(expected, "yyyy-MM-dd") == "2025-10-27"
    assert format_timeline_date(expected, "yyyy/MM/dd") == "2025/10/27"
    assert format_timeline_date(expected, "d/M/yyyy") == "27/10/2025"
    assert format_timeline_date(expected, "M月d日") == "10月27日"


def test_timeline_supports_arbitrary_node_count_ratios_and_multiple_outputs():
    nodes = evenly_distributed_nodes(5)
    nodes[2]["outputs"] = [
        {"field": "中文节点", "format": "yyyy年M月d日"},
        {"field": "iso_node", "format": "yyyy-MM-dd"},
    ]
    result = resolve_timeline_plans(
        {"项目开始日期": "2025-10-01", "项目结束日期": "2025-10-21"},
        _plan(nodes),
    )
    assert not result.errors
    assert [node.iso_value for node in result.nodes] == [
        "2025-10-01",
        "2025-10-06",
        "2025-10-11",
        "2025-10-16",
        "2025-10-21",
    ]
    assert result.values["中文节点"] == "2025年10月11日"
    assert result.values["iso_node"] == "2025-10-11"


def test_direct_date_segment_generates_stable_tokens_and_preserves_date_style():
    segment = default_timeline_segment(
        2,
        node_count=3,
        start_value="2025年10月1日",
        end_value="2025年10月11日",
    )

    result = resolve_timeline_plans({}, {"segment_2": segment})

    assert not result.errors
    assert result.values == {
        "时间节点2-1": "2025年10月1日",
        "时间节点2-2": "2025年10月6日",
        "时间节点2-3": "2025年10月11日",
    }
    assert [node.node_id for node in result.nodes] == ["node_1", "node_2", "node_3"]


def test_timeline_date_format_is_inferred_without_an_extra_user_setting():
    assert infer_timeline_date_format("2025-10-27") == "yyyy-MM-dd"
    assert infer_timeline_date_format("2025/10/27") == "yyyy/MM/dd"
    assert infer_timeline_date_format("2025.10.27") == "yyyy.MM.dd"
    assert infer_timeline_date_format("2025 年 3 月 7 日") == "yyyy年M月d日"
    assert infer_timeline_date_format("20250307") == "yyyyMMdd"


def test_segment_recycling_metadata_has_safe_defaults_for_new_and_legacy_plans():
    new_segment = default_timeline_segment(1)

    assert new_segment["number_state"] == "active"
    assert new_segment["token_copied"] is False
    assert new_segment["retired_outputs"] == []
    assert new_segment["format_mode"] == "auto"
    assert new_segment["input_scope"] == "fixed"

    legacy_deleted = default_timeline_segment(2)
    legacy_deleted["deleted"] = True
    legacy_deleted["enabled"] = False
    legacy_deleted.pop("number_state")
    legacy_deleted.pop("token_copied")
    legacy_deleted.pop("retired_outputs")

    normalized = normalize_timeline_plans({"segment_2": legacy_deleted})["segment_2"]

    assert normalized["number_state"] == "reserved"
    assert normalized["token_copied"] is False
    assert normalized["retired_outputs"] == []


def test_timeline_fixed_and_relative_nodes_keep_one_typed_dependency_chain():
    nodes = [
        {
            "node_id": "kickoff",
            "label": "启动",
            "rule": {"operation": "fixed_date", "value": "2025-10-27"},
            "outputs": [{"field": "启动日", "format": "yyyy-MM-dd"}],
        },
        {
            "node_id": "review",
            "label": "评审",
            "rule": {"operation": "add_days", "source": "kickoff", "days": 5},
            "outputs": [{"field": "评审日", "format": "yyyy年M月d日"}],
        },
    ]
    result = resolve_timeline_plans({}, _plan(nodes))
    assert not result.errors
    assert result.values == {"启动日": "2025-10-27", "评审日": "2025年11月1日"}


def test_timeline_weekend_adjust_is_explicit_and_bounds_are_reported():
    nodes = evenly_distributed_nodes(2)
    plans = _plan(
        nodes,
        calendar={"basis": "calendar_day", "weekend_adjust": "forward"},
        constraints={"bounds": "warning", "order": "error", "same_day": "warning"},
    )
    result = resolve_timeline_plans(
        {"项目开始日期": "2026-07-01", "项目结束日期": "2026-07-11"},
        plans,
    )
    assert result.nodes[-1].iso_value == "2026-07-13"
    assert any(issue.code == "node_out_of_bounds" for issue in result.warnings)


def test_timeline_plan_is_atomic_and_removes_stale_outputs_on_error():
    nodes = evenly_distributed_nodes(3)
    plans = _plan(nodes)
    stale = {output["field"]: "1999-01-01" for node in nodes for output in node["outputs"]}
    result = resolve_timeline_plans(
        {**stale, "项目开始日期": "2025-12-01", "项目结束日期": "2025-01-01"},
        plans,
    )
    assert result.errors
    assert not (set(stale) & set(result.values))


def test_inactive_and_deleted_segment_tokens_are_retired_without_being_reused():
    active = default_timeline_segment(
        2,
        node_count=3,
        start_value="2025-10-01",
        end_value="2025-10-11",
    )
    active["nodes"][2]["active"] = False
    active["nodes"][1]["rule"]["value"] = "1"
    deleted = default_timeline_segment(
        1,
        node_count=2,
        start_value="2025-09-01",
        end_value="2025-09-02",
    )
    deleted["deleted"] = True
    deleted["enabled"] = False

    result = resolve_timeline_plans(
        {
            "时间节点1-1": "stale",
            "时间节点1-2": "stale",
            "时间节点2-3": "stale",
        },
        {"segment_1": deleted, "segment_2": active},
    )

    assert "时间节点1-1" not in result.values
    assert "时间节点1-2" not in result.values
    assert "时间节点2-3" not in result.values
    assert result.values["时间节点2-1"] == "2025-10-01"
    assert timeline_output_field_keys(
        {"segment_1": deleted, "segment_2": active},
        include_inactive=True,
    ) == (
        "时间节点1-1",
        "时间节点1-2",
        "时间节点2-1",
        "时间节点2-2",
        "时间节点2-3",
    )


def test_retired_outputs_are_owned_and_remove_stale_values_after_number_reuse():
    reused = default_timeline_segment(
        1,
        node_count=3,
        start_value="2025-10-01",
        end_value="2025-10-11",
    )
    reused["retired_outputs"] = [
        "{{时间节点1-4}}",
        "时间节点1-5",
        "时间节点1-5",
    ]

    result = resolve_timeline_plans(
        {
            "时间节点1-4": "stale",
            "时间节点1-5": "stale",
            "非时间字段": "keep",
        },
        {"segment_1": reused},
    )

    assert not result.errors
    assert result.values["非时间字段"] == "keep"
    assert result.values["时间节点1-1"] == "2025-10-01"
    assert "时间节点1-4" not in result.values
    assert "时间节点1-5" not in result.values
    assert timeline_output_field_keys(
        {"segment_1": reused},
        include_inactive=True,
    ) == (
        "时间节点1-1",
        "时间节点1-2",
        "时间节点1-3",
        "时间节点1-4",
        "时间节点1-5",
    )


def test_timeline_override_is_exact_and_not_weekend_adjusted():
    nodes = evenly_distributed_nodes(3)
    plans = _plan(
        nodes,
        overrides={"node_2": "2025-11-02"},
        calendar={"basis": "calendar_day", "weekend_adjust": "forward"},
    )
    result = resolve_timeline_plans(
        {"项目开始日期": "2025-11-01", "项目结束日期": "2025-11-11"},
        plans,
    )
    middle = next(node for node in result.nodes if node.node_id == "node_2")
    assert middle.iso_value == "2025-11-02"
    assert middle.overridden is True


def test_timeline_dependency_cycle_is_visible_and_outputs_are_not_committed():
    nodes = [
        {
            "node_id": "a",
            "label": "A",
            "rule": {"operation": "add_days", "source": "b", "days": 1},
            "outputs": [{"field": "A日", "format": "yyyy-MM-dd"}],
        },
        {
            "node_id": "b",
            "label": "B",
            "rule": {"operation": "add_days", "source": "a", "days": 1},
            "outputs": [{"field": "B日", "format": "yyyy-MM-dd"}],
        },
    ]
    result = resolve_timeline_plans({}, _plan(nodes))
    assert any(issue.code == "dependency_cycle" for issue in result.errors)
    assert "A日" not in result.values and "B日" not in result.values


def test_segment_ratio_order_is_validated_even_when_dates_round_to_same_day():
    segment = default_timeline_segment(
        1,
        node_count=4,
        start_value="2025-10-01",
        end_value="2025-10-01",
    )
    segment["nodes"][1]["rule"]["value"] = "0.9"
    segment["nodes"][2]["rule"]["value"] = "0.1"

    result = resolve_timeline_plans({}, {"segment_1": segment})

    assert any(issue.code == "node_ratio_order_invalid" for issue in result.errors)
    assert "时间节点1-2" not in result.values


def test_malformed_preset_cannot_bypass_timeline_segment_endpoint_guard():
    segment = default_timeline_segment(
        1,
        node_count=3,
        start_value="2025-10-01",
        end_value="2025-10-11",
    )
    segment["nodes"][0]["rule"]["value"] = "0.1"
    segment["nodes"][-1]["rule"]["value"] = "0.9"
    segment["preset"] = {"id": [], "version": {}, "unknown": True}

    result = resolve_timeline_plans({}, {"segment_1": segment})

    assert [issue.code for issue in result.errors] == ["invalid_preset_contract"]
    assert result.values == {}


def test_timeline_normalization_and_output_ownership_are_json_safe():
    plans = normalize_timeline_plans({"primary": default_timeline_plan()})
    assert plans["primary"]["schema_version"] == 1
    assert len(plans["primary"]["nodes"]) == 3
    assert timeline_output_field_keys(plans) == (
        "节点_开始节点",
        "节点_节点 2",
        "节点_结束节点",
    )
