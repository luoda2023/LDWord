"""Shared helpers for report payload normalization and markdown rendering."""

from __future__ import annotations


def _clean_text(value) -> str:
    return str(value or "").strip()


def _clean_list(values) -> list[str]:
    return [
        _clean_text(value)
        for value in list(values or [])
        if _clean_text(value)
    ]


def _clean_mapping_lists(value) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    return {
        _clean_text(key): _clean_list(items)
        for key, items in value.items()
        if _clean_text(key)
    }


def _clean_module_skips(values) -> list[dict[str, object]]:
    cleaned: list[dict[str, object]] = []
    for value in list(values or []):
        if not isinstance(value, dict):
            continue
        module_name = _clean_text(value.get("module_name", ""))
        if not module_name:
            continue
        finding_kinds = _clean_list(value.get("finding_kinds", []))
        cleaned.append(
            {
                "module_name": module_name,
                "finding_kinds": finding_kinds,
                "reason": _clean_text(value.get("reason", "")),
            }
        )
    return cleaned


def _join_or_dash(values) -> str:
    items = _clean_list(values)
    return ", ".join(items) if items else "-"


def _normalize_extra_diagnostics(items: list[dict] | None) -> list[dict]:
    if not items:
        return []
    normalized: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(dict(item))
    return normalized
