"""Safe, data-driven material timelines with typed date calculation.

The timeline model deliberately keeps calculation separate from rendering:
nodes resolve to :class:`datetime.date` values and ``outputs`` decide how each
node is exposed to document placeholder fields.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_HALF_UP


TIMELINE_SCHEMA_VERSION = 1
GENERIC_EQUAL_TIMELINE_PRESET = ("generic_equal", 1)
TIMELINE_SEGMENT_PRESET = ("timeline_segment", 2)
ATTACHMENT_WORKBENCH_TIMELINE_PRESET = ("attachment_workbench_equal", 1)
SUPPORTED_TIMELINE_PRESETS = frozenset(
    {
        GENERIC_EQUAL_TIMELINE_PRESET,
        TIMELINE_SEGMENT_PRESET,
        ATTACHMENT_WORKBENCH_TIMELINE_PRESET,
    }
)
SUPPORTED_NODE_OPERATIONS = frozenset({"ratio", "fixed_date", "add_days"})
SUPPORTED_ROUNDING = frozenset({"half_up", "half_even", "floor", "ceil"})
SUPPORTED_WEEKEND_ADJUST = frozenset({"none", "forward", "backward", "nearest"})
DEFAULT_DATE_FORMAT = "yyyy-MM-dd"

_ROUNDING_MODES = {
    "half_up": ROUND_HALF_UP,
    "half_even": ROUND_HALF_EVEN,
    "floor": ROUND_FLOOR,
    "ceil": ROUND_CEILING,
}
_WEEKEND_ALIASES = {
    "following": "forward",
    "preceding": "backward",
    "previous": "backward",
}
_FORMAT_TOKEN = re.compile(r"yyyy|MM|dd|M|d")
_ALLOWED_FORMAT_TEXT = re.compile(r"^(?:yyyy|MM|M|dd|d|[-/.年月日\s])+$")


@dataclass(frozen=True, slots=True)
class TimelineIssue:
    severity: str
    code: str
    plan_id: str
    node_id: str = ""
    field: str = ""
    message: str = ""


@dataclass(frozen=True, slots=True)
class TimelineNodeResolution:
    plan_id: str
    node_id: str
    label: str
    value: date | None = None
    overridden: bool = False

    @property
    def iso_value(self) -> str:
        return self.value.isoformat() if self.value is not None else ""


@dataclass(frozen=True, slots=True)
class TimelineResolution:
    values: dict[str, str]
    nodes: tuple[TimelineNodeResolution, ...] = ()
    issues: tuple[TimelineIssue, ...] = ()

    @property
    def errors(self) -> tuple[TimelineIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[TimelineIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity != "error")


def normalize_timeline_plans(value: object) -> dict[str, dict[str, object]]:
    """Return a JSON-safe timeline mapping while retaining invalid contracts.

    Invalid operations and schema versions are retained so resolution can
    surface a visible issue instead of silently discarding user configuration.
    """

    if not isinstance(value, Mapping):
        return {}
    raw_plans: Mapping = value
    if "nodes" in value and not any(
        isinstance(item, Mapping) and "nodes" in item for item in value.values()
    ):
        raw_plans = {"primary": value}

    normalized: dict[str, dict[str, object]] = {}
    for raw_plan_id, raw_plan in raw_plans.items():
        plan_id = str(raw_plan_id or "").strip()
        if not plan_id or not isinstance(raw_plan, Mapping):
            continue
        try:
            schema_version = int(raw_plan.get("schema_version", TIMELINE_SCHEMA_VERSION))
        except (TypeError, ValueError):
            schema_version = 0
        calendar = raw_plan.get("calendar", {})
        calendar = dict(calendar) if isinstance(calendar, Mapping) else {}
        weekend = str(
            calendar.get("weekend_adjust", raw_plan.get("weekend_adjust", "none"))
            or "none"
        ).strip().lower()
        weekend = _WEEKEND_ALIASES.get(weekend, weekend)
        constraints = raw_plan.get("constraints", {})
        constraints = dict(constraints) if isinstance(constraints, Mapping) else {}
        overrides = raw_plan.get("overrides", {})
        overrides = {
            str(key or "").strip(): _canonical_date_text(item)
            for key, item in dict(overrides).items()
            if str(key or "").strip() and str(item or "").strip()
        } if isinstance(overrides, Mapping) else {}
        deleted = bool(raw_plan.get("deleted", False))
        raw_number_state = str(raw_plan.get("number_state", "") or "").strip()
        number_state = (
            raw_number_state
            if deleted and raw_number_state in {"reserved", "reusable"}
            else "reserved"
            if deleted
            else "active"
        )
        raw_retired_outputs = raw_plan.get("retired_outputs", [])
        retired_outputs = (
            list(
                dict.fromkeys(
                    _field_key(item)
                    for item in raw_retired_outputs
                    if _field_key(item)
                )
            )
            if isinstance(raw_retired_outputs, Sequence)
            and not isinstance(raw_retired_outputs, (str, bytes))
            else []
        )

        nodes: list[dict[str, object]] = []
        raw_nodes = raw_plan.get("nodes", [])
        if isinstance(raw_nodes, Sequence) and not isinstance(raw_nodes, (str, bytes)):
            for index, raw_node in enumerate(raw_nodes, start=1):
                if not isinstance(raw_node, Mapping):
                    continue
                node_id = str(raw_node.get("node_id", "") or "").strip() or f"node_{index}"
                rule = raw_node.get("rule", {})
                rule = dict(rule) if isinstance(rule, Mapping) else {}
                operation = str(rule.get("operation", "ratio") or "ratio").strip().lower()
                normalized_rule: dict[str, object] = {"operation": operation}
                if operation in {"ratio", "fixed_date"}:
                    normalized_rule["value"] = str(rule.get("value", "") or "").strip()
                elif operation == "add_days":
                    normalized_rule["source"] = str(rule.get("source", "@start") or "@start").strip()
                    normalized_rule["days"] = _safe_int(rule.get("days", 0))
                else:
                    normalized_rule.update(copy.deepcopy(rule))

                outputs: list[dict[str, str]] = []
                raw_outputs = raw_node.get("outputs", [])
                if isinstance(raw_outputs, Mapping):
                    raw_outputs = [raw_outputs]
                if isinstance(raw_outputs, Sequence) and not isinstance(raw_outputs, (str, bytes)):
                    for raw_output in raw_outputs:
                        if not isinstance(raw_output, Mapping):
                            continue
                        field_name = _field_key(raw_output.get("field", ""))
                        if field_name:
                            outputs.append(
                                {
                                    "field": field_name,
                                    "format": str(raw_output.get("format", DEFAULT_DATE_FORMAT) or DEFAULT_DATE_FORMAT).strip(),
                                }
                            )
                nodes.append(
                    {
                        "node_id": node_id,
                        "node_no": max(1, _safe_int(raw_node.get("node_no", index))),
                        "active": bool(raw_node.get("active", True)),
                        "label": str(raw_node.get("label", "") or "").strip() or f"节点 {index}",
                        "rule": normalized_rule,
                        "outputs": outputs,
                    }
                )

        normalized[plan_id] = {
            "schema_version": schema_version,
            "label": str(raw_plan.get("label", "") or "").strip() or "时间计划",
            "enabled": bool(raw_plan.get("enabled", True)),
            "deleted": deleted,
            "number_state": number_state,
            "token_copied": bool(raw_plan.get("token_copied", False)),
            "retired_outputs": retired_outputs,
            "segment_no": max(0, _safe_int(raw_plan.get("segment_no", 0))),
            "start_value": str(raw_plan.get("start_value", "") or "").strip(),
            "end_value": str(raw_plan.get("end_value", "") or "").strip(),
            "output_format": str(
                raw_plan.get("output_format", DEFAULT_DATE_FORMAT)
                or DEFAULT_DATE_FORMAT
            ).strip(),
            "format_mode": str(
                raw_plan.get("format_mode", "auto") or "auto"
            ).strip(),
            "input_scope": (
                str(raw_plan.get("input_scope", "fixed") or "fixed").strip()
                if str(raw_plan.get("input_scope", "fixed") or "fixed").strip()
                in {"fixed", "floating"}
                else "fixed"
            ),
            "start_field": _field_key(raw_plan.get("start_field", "")),
            "end_field": _field_key(raw_plan.get("end_field", "")),
            "rounding": str(raw_plan.get("rounding", "half_up") or "half_up").strip().lower(),
            "calendar": {
                "basis": str(calendar.get("basis", "calendar_day") or "calendar_day").strip().lower(),
                "weekend_adjust": weekend,
            },
            "constraints": {
                "bounds": _constraint_level(constraints.get("bounds", "warning")),
                "order": _constraint_level(constraints.get("order", "error")),
                "same_day": _constraint_level(constraints.get("same_day", "warning")),
            },
            "nodes": nodes,
            "overrides": overrides,
            "preset": copy.deepcopy(raw_plan.get("preset", {})) if isinstance(raw_plan.get("preset", {}), Mapping) else {},
        }
    return normalized


def validate_timeline_preset_payload(value: object) -> tuple[str, int]:
    """Return one exact, generator-owned timeline preset contract."""

    if type(value) is not dict:
        raise ValueError("timeline_preset_type_invalid:dict")
    expected = {"id", "version"}
    missing = sorted(expected - set(value))
    if missing:
        raise ValueError(f"timeline_preset_fields_missing:{','.join(missing)}")
    unknown = sorted(set(value) - expected)
    if unknown:
        raise ValueError(f"timeline_preset_fields_unknown:{','.join(unknown)}")
    preset_id = value["id"]
    version = value["version"]
    if type(preset_id) is not str:
        raise ValueError("timeline_preset_field_type_invalid:id:str")
    if type(version) is not int:
        raise ValueError("timeline_preset_field_type_invalid:version:int")
    contract = (preset_id, version)
    if contract not in SUPPORTED_TIMELINE_PRESETS:
        raise ValueError(f"timeline_preset_unsupported:{preset_id}:{version}")
    return contract


def _timeline_preset_payload(contract: tuple[str, int]) -> dict[str, object]:
    preset_id, version = contract
    return {"id": preset_id, "version": version}


def default_timeline_plan() -> dict[str, object]:
    """Return one editable, generic three-node plan."""

    return {
        "schema_version": TIMELINE_SCHEMA_VERSION,
        "label": "时间计划",
        "enabled": True,
        "start_field": "项目开始日期",
        "end_field": "项目结束日期",
        "rounding": "half_up",
        "calendar": {"basis": "calendar_day", "weekend_adjust": "none"},
        "constraints": {"bounds": "warning", "order": "error", "same_day": "warning"},
        "nodes": evenly_distributed_nodes(3),
        "overrides": {},
        "preset": _timeline_preset_payload(GENERIC_EQUAL_TIMELINE_PRESET),
    }


def default_timeline_segment(
    segment_no: int = 1,
    *,
    node_count: int = 3,
    start_value: str = "",
    end_value: str = "",
) -> dict[str, object]:
    """Return one direct-date segment with stable document token names."""

    number = max(1, int(segment_no))
    start_text = str(start_value or "").strip()
    end_text = str(end_value or "").strip()
    date_format = infer_timeline_date_format(start_text or end_text)
    return {
        "schema_version": TIMELINE_SCHEMA_VERSION,
        "label": f"第 {number} 段时间",
        "enabled": bool(start_text and end_text),
        "deleted": False,
        "number_state": "active",
        "token_copied": False,
        "retired_outputs": [],
        "segment_no": number,
        "start_value": start_text,
        "end_value": end_text,
        "output_format": date_format,
        "format_mode": "auto",
        "input_scope": "fixed",
        "start_field": "",
        "end_field": "",
        "rounding": "half_up",
        "calendar": {"basis": "calendar_day", "weekend_adjust": "none"},
        "constraints": {"bounds": "warning", "order": "error", "same_day": "warning"},
        "nodes": timeline_segment_nodes(number, node_count, date_format=date_format),
        "overrides": {},
        "preset": _timeline_preset_payload(TIMELINE_SEGMENT_PRESET),
    }


def timeline_segment_nodes(
    segment_no: int,
    count: int,
    *,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> list[dict[str, object]]:
    """Create evenly spaced nodes named ``时间节点<segment>-<node>``."""

    number = max(1, int(segment_no))
    node_count = max(2, int(count))
    nodes = evenly_distributed_nodes(
        node_count,
        labels=[f"时间节点{number}-{index}" for index in range(1, node_count + 1)],
        field_prefix="",
        date_format=date_format,
    )
    for index, node in enumerate(nodes, start=1):
        token_key = f"时间节点{number}-{index}"
        node["node_id"] = f"node_{index}"
        node["node_no"] = index
        node["active"] = True
        node["label"] = token_key
        node["outputs"] = [{"field": token_key, "format": date_format}]
    return nodes


def infer_timeline_date_format(value: object) -> str:
    """Infer a safe output pattern from a user's direct date spelling."""

    text = str(value or "").strip().translate(
        str.maketrans({"－": "-", "／": "/", "．": "."})
    )
    compact = re.sub(r"\s+", "", text)
    chinese = re.fullmatch(r"\d{4}年(\d{1,2})月(\d{1,2})(?:日|号)?", compact)
    if chinese:
        month, day = chinese.groups()
        return f"yyyy年{'MM' if len(month) == 2 and month.startswith('0') else 'M'}月{'dd' if len(day) == 2 and day.startswith('0') else 'd'}日"
    separated = re.fullmatch(r"\d{4}([-/\.])(\d{1,2})\1(\d{1,2})", compact)
    if separated:
        separator, month, day = separated.groups()
        month_token = "MM" if len(month) == 2 else "M"
        day_token = "dd" if len(day) == 2 else "d"
        return f"yyyy{separator}{month_token}{separator}{day_token}"
    if re.fullmatch(r"\d{8}", compact):
        return "yyyyMMdd"
    return DEFAULT_DATE_FORMAT


def evenly_distributed_nodes(
    count: int,
    *,
    labels: Sequence[str] | None = None,
    field_prefix: str = "节点_",
    date_format: str = DEFAULT_DATE_FORMAT,
) -> list[dict[str, object]]:
    """Create ``count`` ratio nodes including both endpoints."""

    node_count = max(1, int(count))
    provided = [str(item or "").strip() for item in (labels or ())]
    nodes: list[dict[str, object]] = []
    for index in range(node_count):
        if provided and index < len(provided) and provided[index]:
            label = provided[index]
        elif node_count == 1:
            label = "计划节点"
        elif index == 0:
            label = "开始节点"
        elif index == node_count - 1:
            label = "结束节点"
        else:
            label = f"节点 {index + 1}"
        ratio = Decimal(0) if node_count == 1 else Decimal(index) / Decimal(node_count - 1)
        ratio_text = _decimal_text(ratio)
        node_id = f"node_{index + 1}"
        nodes.append(
            {
                "node_id": node_id,
                "label": label,
                "rule": {"operation": "ratio", "value": ratio_text},
                "outputs": [
                    {
                        "field": f"{field_prefix}{label}",
                        "format": date_format,
                    }
                ],
            }
        )
    return nodes


def timeline_output_field_keys(
    plans: object,
    *,
    include_inactive: bool = False,
) -> tuple[str, ...]:
    fields: list[str] = []
    for plan in normalize_timeline_plans(plans).values():
        if not include_inactive and (
            not bool(plan.get("enabled", True))
            or bool(plan.get("deleted", False))
        ):
            continue
        for node in list(plan.get("nodes", []) or []):
            if not include_inactive and not bool(dict(node).get("active", True)):
                continue
            for output in list(dict(node).get("outputs", []) or []):
                field_name = _field_key(dict(output).get("field", ""))
                if field_name and field_name not in fields:
                    fields.append(field_name)
        if include_inactive:
            for field_name in list(plan.get("retired_outputs", []) or []):
                field_name = _field_key(field_name)
                if field_name and field_name not in fields:
                    fields.append(field_name)
    return tuple(fields)


def timeline_owned_field_keys(
    plans: object,
    *,
    include_inactive: bool = False,
) -> tuple[str, ...]:
    """Return every logical field whose public token belongs to ``@time``.

    This includes generated node outputs and configured start/end input fields.
    Keeping the ownership query here prevents UI, Freeze, and runtime from
    independently guessing from localized field names.
    """

    fields = list(
        timeline_output_field_keys(plans, include_inactive=include_inactive)
    )
    seen = set(fields)
    for plan in normalize_timeline_plans(plans).values():
        if not include_inactive and (
            not bool(plan.get("enabled", True)) or bool(plan.get("deleted", False))
        ):
            continue
        for name in ("start_field", "end_field"):
            key = str(plan.get(name, "") or "").strip()
            if key and key not in seen:
                fields.append(key)
                seen.add(key)
    return tuple(fields)


def resolve_timeline_plans(
    entity_data: Mapping[str, object] | None,
    plans: object,
) -> TimelineResolution:
    """Resolve enabled plans and atomically merge each successful plan."""

    values = {
        str(key): str(value or "")
        for key, value in dict(entity_data or {}).items()
        if str(key or "").strip()
    }
    normalized = normalize_timeline_plans(plans)
    owned_output_fields = set(
        timeline_output_field_keys(normalized, include_inactive=True)
    )
    for field_name in owned_output_fields:
        values.pop(field_name, None)

    all_nodes: list[TimelineNodeResolution] = []
    all_issues: list[TimelineIssue] = []
    claimed_fields: dict[str, str] = {}
    for plan_id, plan in normalized.items():
        if not bool(plan.get("enabled", True)) or bool(plan.get("deleted", False)):
            continue
        plan_values, plan_nodes, plan_issues = _resolve_plan(plan_id, plan, values)
        for field_name in plan_values:
            owner = claimed_fields.get(field_name)
            if owner and owner != plan_id:
                plan_issues.append(
                    _issue(
                        "error",
                        "duplicate_output_field",
                        plan_id,
                        field=field_name,
                        message=f"字段“{field_name}”同时由时间计划 {owner} 和 {plan_id} 输出",
                    )
                )
            else:
                claimed_fields[field_name] = plan_id
        all_nodes.extend(plan_nodes)
        all_issues.extend(plan_issues)
        if not any(issue.severity == "error" for issue in plan_issues):
            values.update(plan_values)
    return TimelineResolution(values=values, nodes=tuple(all_nodes), issues=tuple(all_issues))


def parse_timeline_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip().translate(
        str.maketrans({"－": "-", "／": "/", "．": "."})
    )
    if not text:
        raise ValueError("日期尚未填写")
    compact_text = re.sub(r"\s+", "", text)
    if compact_text.endswith("号"):
        compact_text = compact_text[:-1] + "日"
    for candidate in dict.fromkeys((text, compact_text)):
        for pattern in (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%d/%m/%Y",
            "%Y年%m月%d日",
            "%Y%m%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y.%m.%d %H:%M:%S",
            "%Y.%m.%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                return datetime.strptime(candidate, pattern).date()
            except ValueError:
                continue
    raise ValueError(f"无法识别日期：{text}")


def format_timeline_date(value: date, pattern: str = DEFAULT_DATE_FORMAT) -> str:
    format_text = str(pattern or DEFAULT_DATE_FORMAT).strip()
    if not format_text or not _ALLOWED_FORMAT_TEXT.fullmatch(format_text):
        raise ValueError(f"不支持的日期格式：{format_text}")
    replacements = {
        "yyyy": f"{value.year:04d}",
        "MM": f"{value.month:02d}",
        "M": str(value.month),
        "dd": f"{value.day:02d}",
        "d": str(value.day),
    }
    return _FORMAT_TOKEN.sub(lambda match: replacements[match.group(0)], format_text)


def _resolve_plan(
    plan_id: str,
    plan: Mapping[str, object],
    values: Mapping[str, object],
) -> tuple[dict[str, str], list[TimelineNodeResolution], list[TimelineIssue]]:
    issues: list[TimelineIssue] = []
    if int(plan.get("schema_version", 0) or 0) != TIMELINE_SCHEMA_VERSION:
        issues.append(
            _issue(
                "error",
                "unsupported_schema_version",
                plan_id,
                message=f"时间计划版本不受支持：{plan.get('schema_version')}",
            )
        )
        return {}, [], issues
    try:
        preset_contract = validate_timeline_preset_payload(plan.get("preset"))
    except ValueError as exc:
        issues.append(
            _issue(
                "error",
                "invalid_preset_contract",
                plan_id,
                message=str(exc),
            )
        )
        return {}, [], issues

    rounding = str(plan.get("rounding", "half_up") or "half_up")
    if rounding not in SUPPORTED_ROUNDING:
        issues.append(_issue("error", "invalid_rounding", plan_id, message=f"未知取整方式：{rounding}"))
    calendar = dict(plan.get("calendar", {}) or {})
    if str(calendar.get("basis", "calendar_day")) != "calendar_day":
        issues.append(
            _issue(
                "error",
                "calendar_unavailable",
                plan_id,
                message="当前版本仅支持自然日；工作日需要版本化日历",
            )
        )
    weekend = _WEEKEND_ALIASES.get(
        str(calendar.get("weekend_adjust", "none") or "none"),
        str(calendar.get("weekend_adjust", "none") or "none"),
    )
    if weekend not in SUPPORTED_WEEKEND_ADJUST:
        issues.append(_issue("error", "invalid_weekend_adjust", plan_id, message=f"未知周末策略：{weekend}"))

    raw_nodes = [
        node
        for node in list(plan.get("nodes", []) or [])
        if bool(dict(node).get("active", True))
    ]
    nodes_by_id: dict[str, Mapping[str, object]] = {}
    ordered_ids: list[str] = []
    for raw_node in raw_nodes:
        node = dict(raw_node) if isinstance(raw_node, Mapping) else {}
        node_id = str(node.get("node_id", "") or "")
        if node_id in nodes_by_id:
            issues.append(_issue("error", "duplicate_node_id", plan_id, node_id, message=f"节点编号重复：{node_id}"))
            continue
        nodes_by_id[node_id] = node
        ordered_ids.append(node_id)

    operations = [str(dict(node.get("rule", {}) or {}).get("operation", "ratio")) for node in nodes_by_id.values()]
    requires_start = any(operation == "ratio" for operation in operations) or any(
        operation == "add_days" and str(dict(node.get("rule", {}) or {}).get("source", "@start")) == "@start"
        for operation, node in zip(operations, nodes_by_id.values())
    )
    requires_end = any(operation == "ratio" for operation in operations) or any(
        operation == "add_days" and str(dict(node.get("rule", {}) or {}).get("source", "@start")) == "@end"
        for operation, node in zip(operations, nodes_by_id.values())
    )
    start_value: date | None = None
    end_value: date | None = None
    start_field = _field_key(plan.get("start_field", ""))
    end_field = _field_key(plan.get("end_field", ""))
    direct_start = str(plan.get("start_value", "") or "").strip()
    direct_end = str(plan.get("end_value", "") or "").strip()
    if requires_start:
        try:
            start_value = parse_timeline_date(
                direct_start if direct_start else values.get(start_field, "")
            )
        except ValueError as exc:
            issues.append(_issue("error", "invalid_start_date", plan_id, field=start_field, message=str(exc)))
    if requires_end:
        try:
            end_value = parse_timeline_date(
                direct_end if direct_end else values.get(end_field, "")
            )
        except ValueError as exc:
            issues.append(_issue("error", "invalid_end_date", plan_id, field=end_field, message=str(exc)))
    if start_value is not None and end_value is not None and end_value < start_value:
        issues.append(_issue("error", "end_before_start", plan_id, message="结束日期不能早于开始日期"))
    if ordered_ids and all(operation == "ratio" for operation in operations):
        ratio_values: list[tuple[str, Decimal]] = []
        for node_id in ordered_ids:
            rule = dict(nodes_by_id[node_id].get("rule", {}) or {})
            try:
                ratio_values.append(
                    (node_id, Decimal(str(rule.get("value", "") or "")))
                )
            except InvalidOperation:
                continue
        for (_previous_id, previous), (current_id, current) in zip(
            ratio_values,
            ratio_values[1:],
        ):
            if current < previous:
                issues.append(
                    _issue(
                        "error",
                        "node_ratio_order_invalid",
                        plan_id,
                        current_id,
                        message="节点累计比率不能小于前一节点",
                    )
                )
        if (
            preset_contract == TIMELINE_SEGMENT_PRESET
            and len(ratio_values) == len(ordered_ids)
            and (ratio_values[0][1] != 0 or ratio_values[-1][1] != 1)
        ):
            issues.append(
                _issue(
                    "error",
                    "node_ratio_endpoint_invalid",
                    plan_id,
                    message="时间段的首节点必须为 0%，末节点必须为 100%",
                )
            )
    if any(issue.severity == "error" for issue in issues):
        return {}, [], issues

    overrides = dict(plan.get("overrides", {}) or {})
    resolved_dates: dict[str, date] = {}
    visiting: list[str] = []
    overridden: set[str] = set()

    def resolve_node(node_id: str) -> date | None:
        if node_id in resolved_dates:
            return resolved_dates[node_id]
        if node_id in visiting:
            issues.append(_issue("error", "dependency_cycle", plan_id, node_id, message="时间节点存在循环依赖"))
            return None
        node = nodes_by_id.get(node_id)
        if node is None:
            issues.append(_issue("error", "missing_dependency", plan_id, node_id, message=f"找不到依赖节点：{node_id}"))
            return None
        visiting.append(node_id)
        try:
            if node_id in overrides:
                result = parse_timeline_date(overrides[node_id])
                overridden.add(node_id)
            else:
                rule = dict(node.get("rule", {}) or {})
                operation = str(rule.get("operation", "ratio") or "ratio")
                if operation not in SUPPORTED_NODE_OPERATIONS:
                    raise ValueError(f"不支持的节点计算：{operation}")
                if operation == "ratio":
                    if start_value is None or end_value is None:
                        raise ValueError("比例节点缺少起止日期")
                    try:
                        ratio = Decimal(str(rule.get("value", "") or ""))
                    except InvalidOperation as exc:
                        raise ValueError("节点比例不是有效数字") from exc
                    if ratio < 0 or ratio > 1:
                        raise ValueError("节点比例必须在 0% 到 100% 之间")
                    days = Decimal((end_value - start_value).days) * ratio
                    offset = int(days.quantize(Decimal("1"), rounding=_ROUNDING_MODES[rounding]))
                    result = _adjust_weekend(start_value + timedelta(days=offset), weekend)
                elif operation == "fixed_date":
                    result = parse_timeline_date(rule.get("value", ""))
                else:
                    source = str(rule.get("source", "@start") or "@start")
                    if source == "@start":
                        source_value = start_value
                    elif source == "@end":
                        source_value = end_value
                    else:
                        source_value = resolve_node(source)
                    if source_value is None:
                        raise ValueError(f"依赖节点尚未计算：{source}")
                    result = _adjust_weekend(source_value + timedelta(days=_safe_int(rule.get("days", 0))), weekend)
            resolved_dates[node_id] = result
            return result
        except (InvalidOperation, ValueError) as exc:
            issues.append(_issue("error", "node_calculation_failed", plan_id, node_id, message=str(exc)))
            return None
        finally:
            visiting.pop()

    for node_id in ordered_ids:
        resolve_node(node_id)

    node_results = [
        TimelineNodeResolution(
            plan_id=plan_id,
            node_id=node_id,
            label=str(nodes_by_id[node_id].get("label", "") or node_id),
            value=resolved_dates.get(node_id),
            overridden=node_id in overridden,
        )
        for node_id in ordered_ids
    ]
    _validate_plan_dates(plan_id, plan, node_results, start_value, end_value, issues)

    output_values: dict[str, str] = {}
    for node_result in node_results:
        if node_result.value is None:
            continue
        node = nodes_by_id[node_result.node_id]
        for output in list(node.get("outputs", []) or []):
            output = dict(output) if isinstance(output, Mapping) else {}
            field_name = _field_key(output.get("field", ""))
            if not field_name:
                continue
            if field_name in output_values:
                issues.append(
                    _issue(
                        "error",
                        "duplicate_output_field",
                        plan_id,
                        node_result.node_id,
                        field=field_name,
                        message=f"计划内重复输出字段：{field_name}",
                    )
                )
                continue
            try:
                output_values[field_name] = format_timeline_date(
                    node_result.value,
                    str(output.get("format", DEFAULT_DATE_FORMAT) or DEFAULT_DATE_FORMAT),
                )
            except ValueError as exc:
                issues.append(
                    _issue("error", "invalid_output_format", plan_id, node_result.node_id, field=field_name, message=str(exc))
                )
    if any(issue.severity == "error" for issue in issues):
        output_values = {}
    return output_values, node_results, issues


def _validate_plan_dates(
    plan_id: str,
    plan: Mapping[str, object],
    nodes: list[TimelineNodeResolution],
    start_value: date | None,
    end_value: date | None,
    issues: list[TimelineIssue],
) -> None:
    constraints = dict(plan.get("constraints", {}) or {})
    dated = [node for node in nodes if node.value is not None]
    bounds_level = _constraint_level(constraints.get("bounds", "warning"))
    if bounds_level != "allow" and start_value is not None and end_value is not None:
        for node in dated:
            if node.value < start_value or node.value > end_value:
                issues.append(
                    _issue(bounds_level, "node_out_of_bounds", plan_id, node.node_id, message=f"节点“{node.label}”超出项目周期")
                )
    order_level = _constraint_level(constraints.get("order", "error"))
    if order_level != "allow":
        for previous, current in zip(dated, dated[1:]):
            if current.value < previous.value:
                issues.append(
                    _issue(order_level, "node_order_invalid", plan_id, current.node_id, message=f"节点“{current.label}”早于前一节点")
                )
    same_day_level = _constraint_level(constraints.get("same_day", "warning"))
    if same_day_level != "allow":
        by_date: dict[date, list[TimelineNodeResolution]] = {}
        for node in dated:
            by_date.setdefault(node.value, []).append(node)
        for same_day_nodes in by_date.values():
            if len(same_day_nodes) > 1:
                labels = "、".join(node.label for node in same_day_nodes)
                issues.append(
                    _issue(same_day_level, "nodes_share_date", plan_id, same_day_nodes[-1].node_id, message=f"多个节点落在同一天：{labels}")
                )


def _adjust_weekend(value: date, policy: str) -> date:
    if value.weekday() < 5 or policy == "none":
        return value
    if policy == "forward":
        while value.weekday() >= 5:
            value += timedelta(days=1)
        return value
    if policy == "backward":
        while value.weekday() >= 5:
            value -= timedelta(days=1)
        return value
    if policy == "nearest":
        before = value
        after = value
        while before.weekday() >= 5:
            before -= timedelta(days=1)
        while after.weekday() >= 5:
            after += timedelta(days=1)
        return before if (value - before) <= (after - value) else after
    return value


def _issue(
    severity: str,
    code: str,
    plan_id: str,
    node_id: str = "",
    *,
    field: str = "",
    message: str = "",
) -> TimelineIssue:
    return TimelineIssue(
        severity="error" if severity == "error" else "warning",
        code=code,
        plan_id=plan_id,
        node_id=node_id,
        field=field,
        message=message,
    )


def _constraint_level(value: object) -> str:
    text = str(value or "warning").strip().lower()
    return text if text in {"error", "warning", "allow"} else "warning"


def _field_key(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("{{") and text.endswith("}}"):
        text = text[2:-2].strip()
    return text


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _canonical_date_text(value: object) -> str:
    try:
        return parse_timeline_date(value).isoformat()
    except ValueError:
        return str(value or "").strip()


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", ""} else text


__all__ = [
    "DEFAULT_DATE_FORMAT",
    "SUPPORTED_NODE_OPERATIONS",
    "SUPPORTED_ROUNDING",
    "SUPPORTED_WEEKEND_ADJUST",
    "TIMELINE_SCHEMA_VERSION",
    "TimelineIssue",
    "TimelineNodeResolution",
    "TimelineResolution",
    "default_timeline_segment",
    "default_timeline_plan",
    "evenly_distributed_nodes",
    "format_timeline_date",
    "infer_timeline_date_format",
    "normalize_timeline_plans",
    "parse_timeline_date",
    "resolve_timeline_plans",
    "timeline_segment_nodes",
    "timeline_output_field_keys",
    "timeline_owned_field_keys",
]
