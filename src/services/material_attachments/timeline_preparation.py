"""Ownership boundary for timeline plans created by attachment preparation.

The main timeline editor and the attachment workbench both persist plans on an
``EntityProfile``.  They must not silently rewrite each other's plans.  This
module gives attachment-created plans an explicit owner and applies them as one
validated transaction across the selected profiles.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
import re

from src.config.entity import EntityProfile
from src.shared.engine.material_timeline import (
    ATTACHMENT_WORKBENCH_TIMELINE_PRESET,
    normalize_timeline_plans,
    timeline_output_field_keys,
)


ATTACHMENT_TIMELINE_PRESET_ID = ATTACHMENT_WORKBENCH_TIMELINE_PRESET[0]


@dataclass(frozen=True, slots=True)
class AttachmentTimelineConflict(Exception):
    """A non-attachment plan already owns one requested output field."""

    profile_name: str
    plan_id: str
    output_fields: tuple[str, ...]

    def __str__(self) -> str:
        fields = "、".join(self.output_fields)
        return (
            f"{self.profile_name or '未命名数据'} 的时间计划 {self.plan_id} "
            f"已生成：{fields}"
        )


def attachment_timeline_plan_id(role: str) -> str:
    safe_role = re.sub(r"[^\w\-]+", "_", str(role or ""), flags=re.UNICODE)
    return f"attachment_{safe_role.strip('_') or 'package'}_timeline"


def is_attachment_timeline_plan(plan: Mapping[str, object]) -> bool:
    preset = dict(plan.get("preset", {}) or {})
    return str(preset.get("id", "") or "") == ATTACHMENT_TIMELINE_PRESET_ID


def build_attachment_timeline_plan(
    *,
    start_field: str,
    end_field: str,
    outputs: Sequence[tuple[str, Decimal | str]],
    date_format: str,
) -> dict[str, object]:
    """Build the canonical attachment-owned ratio plan."""

    start = str(start_field or "").strip()
    end = str(end_field or "").strip()
    if not start or not end:
        raise ValueError("attachment_timeline_anchor_missing")
    nodes: list[dict[str, object]] = []
    for index, (raw_field, raw_ratio) in enumerate(outputs, start=1):
        field = str(raw_field or "").strip()
        if not field:
            raise ValueError("attachment_timeline_output_missing")
        ratio = Decimal(str(raw_ratio))
        if ratio < 0 or ratio > 1:
            raise ValueError("attachment_timeline_ratio_out_of_bounds")
        nodes.append(
            {
                "node_id": f"node_{index}",
                "node_no": index,
                "active": True,
                "label": field,
                "rule": {
                    "operation": "ratio",
                    "value": _decimal_text(ratio),
                },
                "outputs": [{"field": field, "format": str(date_format)}],
            }
        )
    plan = {
        "schema_version": 1,
        "label": "附件包时间计划",
        "enabled": True,
        "deleted": False,
        "number_state": "active",
        "segment_no": 0,
        "input_scope": "floating",
        "start_field": start,
        "end_field": end,
        "output_format": str(date_format),
        "format_mode": "auto",
        "rounding": "half_up",
        "calendar": {"basis": "calendar_day", "weekend_adjust": "none"},
        "constraints": {
            "bounds": "warning",
            "order": "error",
            "same_day": "warning",
        },
        "nodes": nodes,
        "overrides": {},
        "preset": {
            "id": ATTACHMENT_TIMELINE_PRESET_ID,
            "version": ATTACHMENT_WORKBENCH_TIMELINE_PRESET[1],
        },
    }
    return normalize_timeline_plans({"attachment": plan})["attachment"]


def common_attachment_timeline_plan(
    profiles: Sequence[EntityProfile],
    output_fields: Sequence[str],
) -> tuple[str, dict[str, object] | None]:
    """Return a plan only when every profile has the same owned definition."""

    targets = _normalized_fields(output_fields)
    if not profiles or not targets:
        return "", None
    matches: list[tuple[str, dict[str, object]]] = []
    for profile in profiles:
        profile_matches = [
            (plan_id, plan)
            for plan_id, plan in normalize_timeline_plans(
                profile.timeline_plans
            ).items()
            if is_attachment_timeline_plan(plan)
            and targets.intersection(
                timeline_output_field_keys({plan_id: plan}, include_inactive=True)
            )
        ]
        if len(profile_matches) != 1:
            return "", None
        matches.append(profile_matches[0])
    first_id, first_plan = matches[0]
    comparable = _comparable_plan(first_plan)
    if any(_comparable_plan(plan) != comparable for _plan_id, plan in matches[1:]):
        return "", None
    return first_id, copy.deepcopy(first_plan)


def apply_attachment_timeline_plan(
    profiles: Sequence[EntityProfile],
    *,
    role: str,
    plan: Mapping[str, object],
) -> str:
    """Validate ownership, replace old attachment plans, then commit atomically."""

    normalized_plan = normalize_timeline_plans({"attachment": dict(plan)})[
        "attachment"
    ]
    if not is_attachment_timeline_plan(normalized_plan):
        raise ValueError("attachment_timeline_owner_invalid")
    target_fields = set(
        timeline_output_field_keys(
            {"attachment": normalized_plan},
            include_inactive=True,
        )
    )
    if not target_fields:
        raise ValueError("attachment_timeline_outputs_missing")

    prepared_plans: list[dict[str, dict[str, object]]] = []
    stable_id = attachment_timeline_plan_id(role)
    for profile in profiles:
        plans = normalize_timeline_plans(profile.timeline_plans)
        retained: dict[str, dict[str, object]] = {}
        for plan_id, existing in plans.items():
            overlap = target_fields.intersection(
                timeline_output_field_keys(
                    {plan_id: existing},
                    include_inactive=True,
                )
            )
            if not overlap:
                retained[plan_id] = existing
                continue
            if is_attachment_timeline_plan(existing):
                continue
            raise AttachmentTimelineConflict(
                profile_name=str(profile.profile_name or profile.profile_id or ""),
                plan_id=plan_id,
                output_fields=tuple(sorted(overlap)),
            )
        retained[stable_id] = copy.deepcopy(normalized_plan)
        prepared_plans.append(retained)

    anchors = (
        str(normalized_plan.get("start_field", "") or "").strip(),
        str(normalized_plan.get("end_field", "") or "").strip(),
    )
    for profile, plans in zip(profiles, prepared_plans):
        profile.timeline_plans = plans
        profile.declared_field_keys = list(
            dict.fromkeys(
                (
                    *profile.declared_field_keys,
                    *(key for key in anchors if key),
                    *profile.fields.keys(),
                )
            )
        )
    return stable_id


def attachment_owned_timeline_plans(
    plans: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Copy only plans explicitly owned by attachment preparation."""

    return {
        plan_id: copy.deepcopy(plan)
        for plan_id, plan in normalize_timeline_plans(plans).items()
        if is_attachment_timeline_plan(plan)
    }


def _normalized_fields(values: Sequence[str]) -> set[str]:
    return {
        str(value or "").strip()
        for value in values
        if str(value or "").strip()
    }


def _comparable_plan(plan: Mapping[str, object]) -> dict[str, object]:
    return copy.deepcopy(dict(plan))


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


__all__ = [
    "ATTACHMENT_TIMELINE_PRESET_ID",
    "AttachmentTimelineConflict",
    "apply_attachment_timeline_plan",
    "attachment_owned_timeline_plans",
    "attachment_timeline_plan_id",
    "build_attachment_timeline_plan",
    "common_attachment_timeline_plan",
    "is_attachment_timeline_plan",
]
