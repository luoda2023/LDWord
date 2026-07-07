"""Asset item normalization helpers for the assets panel."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

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


def _normalized_asset_item_payloads(items: object) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return normalized
    for item in items:
        if isinstance(item, AssetItem):
            payload = _asset_item_payload(item)
        elif isinstance(item, Mapping):
            metadata = item.get("metadata", {})
            if not isinstance(metadata, Mapping):
                metadata = {}
            role = str(item.get("role", "") or "").strip().lower().replace(" ", "_")
            path = str(item.get("path", "") or "").strip()
            asset_id = str(metadata.get("asset_id") or metadata.get("assetId") or "").strip()
            if not role or (not path and not asset_id):
                continue
            width = item.get("width_cm")
            try:
                width_cm = float(width) if width not in (None, "") else None
            except (TypeError, ValueError):
                width_cm = None
            raw_tags = item.get("tags", [])
            tags = (
                [str(tag) for tag in raw_tags]
                if isinstance(raw_tags, Sequence) and not isinstance(raw_tags, (str, bytes))
                else []
            )
            payload = {
                "item_id": str(item.get("item_id", "") or ""),
                "label": str(item.get("label", "") or "") or Path(path).stem or asset_id or role,
                "role": role,
                "path": path,
                "metadata": {
                    str(key): str(value)
                    for key, value in metadata.items()
                    if str(key or "").strip() and str(value or "").strip()
                },
            }
            mime_type = str(item.get("mime_type", "") or "")
            if mime_type:
                payload["mime_type"] = mime_type
            if tags:
                payload["tags"] = tags
            if width_cm is not None:
                payload["width_cm"] = width_cm
        else:
            continue
        normalized.append(payload)
    return normalized


def _asset_items_from_payloads(items: object) -> list[AssetItem]:
    result: list[AssetItem] = []
    for item in _normalized_asset_item_payloads(items):
        result.append(
            AssetItem(
                item_id=str(item.get("item_id", "") or ""),
                label=str(item.get("label", "") or ""),
                role=str(item.get("role", "") or ""),
                path=str(item.get("path", "") or ""),
                mime_type=str(item.get("mime_type", "") or ""),
                tags=[str(tag) for tag in item.get("tags", [])] if isinstance(item.get("tags"), list) else [],
                width_cm=item.get("width_cm") if isinstance(item.get("width_cm"), (int, float)) else None,
                metadata={
                    str(key): str(value)
                    for key, value in dict(item.get("metadata", {}) or {}).items()
                    if str(key or "").strip() and str(value or "").strip()
                },
            )
        )
    return result


def _asset_item_payload(item: AssetItem) -> dict[str, object]:
    payload: dict[str, object] = {
        "item_id": str(getattr(item, "item_id", "") or ""),
        "label": str(getattr(item, "label", "") or ""),
        "role": str(getattr(item, "role", "") or "").strip().lower().replace(" ", "_"),
        "path": str(getattr(item, "path", "") or ""),
        "metadata": {
            str(key): str(value)
            for key, value in dict(getattr(item, "metadata", {}) or {}).items()
            if str(key or "").strip() and str(value or "").strip()
        },
    }
    mime_type = str(getattr(item, "mime_type", "") or "")
    if mime_type:
        payload["mime_type"] = mime_type
    tags = [str(tag) for tag in list(getattr(item, "tags", []) or [])]
    if tags:
        payload["tags"] = tags
    width_cm = getattr(item, "width_cm", None)
    if width_cm is not None:
        payload["width_cm"] = width_cm
    return payload


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
    '_asset_items_from_payloads',
    '_asset_item_payload',
    '_dedupe_asset_items',
]
