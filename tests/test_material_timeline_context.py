from datetime import datetime, timezone

from src.config.entity import (
    EntityArchive,
    EntityProfile,
    load_entity_archive,
    save_entity_archive,
)
from src.config.material_batch import build_material_batch_items
from src.config.material_context import MaterialExecutionContext
from src.shared.engine.material_timeline import (
    default_timeline_plan,
    default_timeline_segment,
    normalize_timeline_plans,
)


def _plans(*, output_field="节点日期"):
    plan = default_timeline_plan()
    plan["nodes"] = [
        {
            "node_id": "middle",
            "label": "中点",
            "rule": {"operation": "ratio", "value": "0.5"},
            "outputs": [{"field": output_field, "format": "yyyy年M月d日"}],
        }
    ]
    return {"primary": plan}


def test_material_context_normalizes_clones_and_resolves_timeline_plans():
    context = MaterialExecutionContext.from_payload(
        {
            "entity_data": {"项目开始日期": "2025-10-01", "项目结束日期": "2025-10-11"},
            "timeline_plans": _plans(),
        }
    )
    clone = context.clone()
    assert not context.is_empty()
    assert clone.timeline_plans == context.timeline_plans
    assert clone.timeline_plans is not context.timeline_plans
    assert context.resolved_entity_data()["节点日期"] == "2025年10月6日"


def test_recycling_metadata_survives_context_payload_normalization_and_clone():
    deleted = default_timeline_segment(4, node_count=3)
    deleted.update(
        {
            "deleted": True,
            "enabled": False,
            "number_state": "reusable",
            "token_copied": True,
            "retired_outputs": ["{{时间节点4-4}}", "时间节点4-5"],
        }
    )

    context = MaterialExecutionContext.from_payload(
        {"timeline_plans": {"segment_4": deleted}}
    )
    clone = context.clone()

    normalized = context.timeline_plans["segment_4"]
    assert normalized["number_state"] == "reusable"
    assert normalized["token_copied"] is True
    assert normalized["retired_outputs"] == ["时间节点4-4", "时间节点4-5"]
    assert clone.timeline_plans == context.timeline_plans
    assert clone.timeline_plans is not context.timeline_plans
    assert (
        clone.timeline_plans["segment_4"]["retired_outputs"]
        is not normalized["retired_outputs"]
    )


def test_material_context_resolves_realtime_function_anchor_before_timeline():
    context = MaterialExecutionContext(
        entity_data={"结束": "2025-10-11"},
        field_functions={"开始": {"function": "realtime_date"}},
        timeline_plans={
            "primary": {
                **next(iter(_plans().values())),
                "start_field": "开始",
                "end_field": "结束",
            }
        },
    )
    resolution = context.resolve_material_fields(
        now=datetime(2025, 10, 1, tzinfo=timezone.utc)
    )
    assert resolution.values["节点日期"] == "2025年10月6日"


def test_material_context_reports_field_function_and_timeline_output_conflicts():
    context = MaterialExecutionContext(
        entity_data={"项目开始日期": "2025-10-01", "项目结束日期": "2025-10-11"},
        field_functions={"节点日期": {"function": "realtime_date"}},
        timeline_plans=_plans(),
    )
    resolution = context.resolve_material_fields()
    assert any(
        issue.code == "field_function_conflict"
        for issue in resolution.timeline_issues
    )


def test_timeline_plans_round_trip_in_material_archives(tmp_path):
    target = tmp_path / "timeline.material.json"
    canonical = normalize_timeline_plans(_plans())
    save_entity_archive(
        EntityArchive(
            archive_id="timeline",
            profiles=[EntityProfile(profile_id="one", timeline_plans=canonical)],
        ),
        target,
    )
    loaded = load_entity_archive(target)
    assert loaded.profiles[0].timeline_plans == canonical


def test_deleted_segment_tombstone_round_trips_to_reserve_public_token_number(tmp_path):
    target = tmp_path / "timeline-segments.material.json"
    deleted = default_timeline_segment(1, node_count=3)
    deleted["deleted"] = True
    deleted["enabled"] = False
    deleted["number_state"] = "reserved"
    deleted["token_copied"] = True
    deleted["retired_outputs"] = ["时间节点1-4", "时间节点1-5"]
    active = default_timeline_segment(2, node_count=3)
    save_entity_archive(
        EntityArchive(
            archive_id="timeline-segments",
            profiles=[
                EntityProfile(
                    profile_id="one",
                    timeline_plans={"segment_1": deleted, "segment_2": active},
                )
            ],
        ),
        target,
    )

    plans = load_entity_archive(target).profiles[0].timeline_plans

    assert plans["segment_1"]["deleted"] is True
    assert plans["segment_1"]["segment_no"] == 1
    assert plans["segment_1"]["number_state"] == "reserved"
    assert plans["segment_1"]["token_copied"] is True
    assert plans["segment_1"]["retired_outputs"] == ["时间节点1-4", "时间节点1-5"]
    assert plans["segment_2"]["segment_no"] == 2


def test_batch_profile_plan_atomically_overrides_same_named_base_plan(tmp_path):
    profile_plan = _plans(output_field="资料节点")
    base_plan = _plans(output_field="基础节点")
    archive = EntityArchive(
        profiles=[
            EntityProfile(
                profile_id="one",
                profile_name="One",
                fields={"项目开始日期": "2025-10-01", "项目结束日期": "2025-10-11"},
                timeline_plans=profile_plan,
            )
        ]
    )
    [item] = build_material_batch_items(
        archive,
        base_output_dir=tmp_path,
        base_context=MaterialExecutionContext(timeline_plans=base_plan),
    )
    assert "资料节点" in item.context.resolved_entity_data()
    assert "基础节点" not in item.context.resolved_entity_data()
