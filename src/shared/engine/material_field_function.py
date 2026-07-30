"""Realtime functions for material fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SUPPORTED_FUNCTIONS = frozenset(
    {"realtime_date", "realtime_time", "realtime_datetime"}
)
REALTIME_TIMEZONE = "Asia/Shanghai"


@dataclass(frozen=True, slots=True)
class FieldFunctionResolution:
    values: dict[str, str]
    errors: dict[str, str] = field(default_factory=dict)


def normalize_field_functions(value: object) -> dict[str, dict[str, str]]:
    """Return a JSON-safe mapping containing only supported field functions."""

    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for raw_key, raw_spec in value.items():
        key = str(raw_key or "").strip()
        if not key or not isinstance(raw_spec, Mapping):
            continue
        function_name = str(raw_spec.get("function", "") or "").strip()
        if function_name not in SUPPORTED_FUNCTIONS:
            continue
        normalized[key] = {"function": function_name}
    return normalized


def resolve_field_functions(
    entity_data: Mapping[str, object] | None,
    field_functions: Mapping[str, object] | None,
    *,
    now: datetime | None = None,
) -> FieldFunctionResolution:
    """Resolve all field functions against one shared realtime snapshot."""

    values = {
        str(key): str(value or "")
        for key, value in dict(entity_data or {}).items()
        if str(key or "").strip()
    }
    functions = normalize_field_functions(field_functions)
    if not functions:
        return FieldFunctionResolution(values=values)

    errors: dict[str, str] = {}
    try:
        moment = _localized_now(now)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        message = str(exc) or "无法获取实时值"
        return FieldFunctionResolution(
            values=values,
            errors={key: message for key in functions},
        )

    for key, spec in functions.items():
        function_name = spec["function"]
        if function_name == "realtime_date":
            values[key] = _format_chinese_date(moment.date())
        elif function_name == "realtime_time":
            values[key] = moment.strftime("%H:%M:%S")
        elif function_name == "realtime_datetime":
            values[key] = f"{_format_chinese_date(moment.date())} {moment:%H:%M:%S}"
    return FieldFunctionResolution(values=values, errors=errors)


def describe_field_function(spec: Mapping[str, object] | None) -> str:
    normalized = normalize_field_functions({"_": spec or {}}).get("_", {})
    function_name = normalized.get("function", "")
    return {
        "realtime_date": "实时日期",
        "realtime_time": "实时时间",
        "realtime_datetime": "实时日期时间",
    }.get(function_name, "")


def _localized_now(now: datetime | None) -> datetime:
    try:
        zone = ZoneInfo(REALTIME_TIMEZONE)
    except ZoneInfoNotFoundError:
        zone = timezone(timedelta(hours=8), name=REALTIME_TIMEZONE)
    if now is None:
        return datetime.now(zone)
    if now.tzinfo is None:
        return now.replace(tzinfo=zone)
    return now.astimezone(zone)


def _format_chinese_date(value: date) -> str:
    return f"{value.year}年{value.month}月{value.day}日"


__all__ = [
    "FieldFunctionResolution",
    "REALTIME_TIMEZONE",
    "SUPPORTED_FUNCTIONS",
    "describe_field_function",
    "normalize_field_functions",
    "resolve_field_functions",
]
