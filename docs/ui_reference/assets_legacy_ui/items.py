"""Asset item normalization helpers for the assets panel."""

from __future__ import annotations

from typing import Any, Mapping

from src.config.asset_resolution import (
    asset_item_payload as _asset_item_payload,
    normalize_asset_item_payloads as _normalized_asset_item_payloads,
)
from src.config.materials import AssetItem

def _normalized_asset_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    if not isinstance(metadata, Mapping):
        return normalized
    for raw_role, raw_value in metadata.items():
        role = str(raw_role or "").strip().lower().replace(" ", "_")
        if not role or not isinstance(raw_value, Mapping):
            continue
        item = {
            str(key): str(value)
            for key, value in raw_value.items()
            if str(key or "").strip() and str(value or "").strip()
        }
        if item:
            normalized[role] = item
    return normalized


def _asset_items_with_metadata(
    items: list[AssetItem],
    metadata: Mapping[str, Any] | None,
) -> list[AssetItem]:
    by_role = _normalized_asset_metadata(metadata)
    if not by_role:
        return _dedupe_asset_items(items)
    for item in items:
        role = str(getattr(item, "role", "") or "").strip().lower().replace(" ", "_")
        item_metadata = by_role.get(role)
        if item_metadata:
            item.metadata = {**item_metadata, **dict(getattr(item, "metadata", {}) or {})}
    return _dedupe_asset_items(items)


def _dedupe_asset_items(items: list[AssetItem]) -> list[AssetItem]:
    seen: set[tuple[str, str, str]] = set()
    result: list[AssetItem] = []
    for item in items:
        role = str(getattr(item, "role", "") or "").strip().lower().replace(" ", "_")
        path = str(getattr(item, "path", "") or "").strip()
        item_id = str(getattr(item, "item_id", "") or "").strip()
        key = (role, path, item_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


__all__ = [
    '_normalized_asset_metadata',
    '_asset_items_with_metadata',
    '_normalized_asset_item_payloads',
    '_asset_item_payload',
    '_dedupe_asset_items',
]
