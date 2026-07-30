"""Shared numbered-name rules for editable material token inventories."""

from __future__ import annotations

import re
from collections.abc import Collection


_NUMBERED_NAME_PATTERN = re.compile(r"(.*?)(\d+)$")


def next_numbered_name(
    prefix: object,
    occupied: Collection[str],
    *,
    start: int = 1,
    width: int = 1,
) -> str:
    """Return the first free ``prefix + number`` name."""

    normalized_prefix = str(prefix or "").strip()
    if not normalized_prefix:
        raise ValueError("numbered name prefix must not be empty")
    number = max(1, int(start))
    resolved_width = max(1, int(width))
    occupied_names = {str(item or "").strip() for item in occupied}
    while True:
        candidate = f"{normalized_prefix}{number:0{resolved_width}d}"
        if candidate not in occupied_names:
            return candidate
        number += 1


def numbered_series_prefix(value: object) -> str:
    """Return the textual family prefix of a numbered or unnumbered name."""

    normalized = str(value or "").strip()
    match = _NUMBERED_NAME_PATTERN.fullmatch(normalized)
    return match.group(1) if match is not None else normalized


def next_series_name(value: object, occupied: Collection[str]) -> str:
    """Continue a row's numbered family while preserving numeric width."""

    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("series source name must not be empty")
    match = _NUMBERED_NAME_PATTERN.fullmatch(normalized)
    if match is None:
        return next_numbered_name(normalized, occupied, start=2)
    prefix, number_text = match.groups()
    return next_numbered_name(
        prefix,
        occupied,
        start=int(number_text) + 1,
        width=len(number_text),
    )


def is_numbered_series_name(value: object, prefix: object) -> bool:
    """Return whether ``value`` belongs to ``prefix``'s numbered family."""

    normalized = str(value or "").strip()
    normalized_prefix = str(prefix or "").strip()
    return bool(
        normalized_prefix
        and re.fullmatch(re.escape(normalized_prefix) + r"\d+", normalized)
    )


__all__ = [
    "is_numbered_series_name",
    "next_numbered_name",
    "next_series_name",
    "numbered_series_prefix",
]
