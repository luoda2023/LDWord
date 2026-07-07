"""Common scalar helpers shared by material asset service modules."""

from __future__ import annotations

from datetime import datetime, timezone

def _ui_utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _first_non_empty(*values: object, fallback: str = "") -> str:
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned:
            return cleaned
    return fallback


def _metric_int(value: object) -> int:
    try:
        return int(float(str(value or "0")))
    except (TypeError, ValueError):
        return 0


def _metric_float(value: object) -> float:
    try:
        return float(str(value or "0"))
    except (TypeError, ValueError):
        return 0.0


def _metric_time_label(value: object) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return "未记录"
    return cleaned.replace("T", " ").replace("Z", "")[:19]


__all__ = [
    '_ui_utc_now_iso',
    '_first_non_empty',
    '_metric_int',
    '_metric_float',
    '_metric_time_label',
]
