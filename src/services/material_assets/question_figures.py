"""Local question-figure material service helpers.

This module stays on the local/material side of the boundary: it normalizes
question-figure metadata, labels, ordering, and preview references without
performing network writes or enterprise governance actions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from src.config.materials import AssetItem


def _question_figure_candidate_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]
    return [str(item or "").strip() for item in values if str(item or "").strip()]


def _question_figure_collection_summary(asset_items) -> str:
    question_items = _question_figure_asset_items(asset_items)
    if len(question_items) <= 1:
        return ""
    alt_count = sum(1 for item in question_items if _asset_item_alt_text(item))
    return f"题图 {len(question_items)} 张，图片说明 {alt_count}/{len(question_items)}"


def _question_figure_item_summary(item: AssetItem) -> str:
    prefix = _question_figure_target_label(item)
    name = (
        Path(_asset_item_preview_path(item)).name
        or _asset_item_library_asset_id(item)
        or str(getattr(item, "label", "") or "未命名")
    )
    return f"{prefix}：{name}"


def _repeated_question_figure_status(role: str, asset_items) -> str:
    if str(role or "").strip().lower().replace(" ", "_") != "question_figure":
        return ""
    question_items = _question_figure_asset_items(asset_items)
    if len(question_items) <= 1:
        return ""
    summary = _question_figure_collection_summary(question_items)
    samples = "；".join(
        _question_figure_item_summary(item)
        for item in question_items[:3]
    )
    if len(question_items) > 3:
        samples = f"{samples}；等 {len(question_items)} 张"
    return f"已配置 {len(question_items)} 张题图 · {summary} · {samples}"


def _question_figure_target_label(item: AssetItem) -> str:
    metadata = dict(getattr(item, "metadata", {}) or {})
    target = _question_figure_target_value(metadata)
    order = _question_figure_order_value(metadata)
    if target and order is not None:
        return f"题{target}-图{order}"
    if target:
        return f"题{target}"
    if order is not None:
        return f"图{order}"
    return "题图"


def _question_figure_payload_matches_item(payload: Mapping[str, object], item: AssetItem) -> bool:
    role = str(payload.get("role", "") or "").strip().lower().replace(" ", "_")
    if role != "question_figure":
        return False
    item_id = str(getattr(item, "item_id", "") or "").strip()
    if item_id and str(payload.get("item_id", "") or "").strip() == item_id:
        return True
    metadata = dict(payload.get("metadata", {}) or {}) if isinstance(payload.get("metadata", {}), Mapping) else {}
    payload_target = _question_figure_target_value(metadata)
    item_target = _question_figure_target_value(dict(getattr(item, "metadata", {}) or {}))
    if payload_target and item_target and payload_target == item_target:
        return True
    payload_path = str(payload.get("path", "") or "").strip()
    item_path = str(getattr(item, "path", "") or "").strip()
    if payload_path and item_path and payload_path == item_path:
        return True
    item_cache_path = _asset_item_cached_path(item)
    payload_cache_path = _question_figure_target_cache_path(payload)
    return bool(
        item_cache_path
        and (
            (payload_cache_path and item_cache_path == payload_cache_path)
            or (payload_path and item_cache_path == payload_path)
        )
    )


def _question_figure_repair_target_payload(value: str) -> dict[str, str]:
    text = str(value or "").strip()
    if not text:
        return {}
    parsed: object = None
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
    if isinstance(parsed, Mapping):
        metadata = parsed.get("metadata", {})
        target: dict[str, str] = {
            str(key): str(item)
            for key, item in parsed.items()
            if str(key or "").strip()
            and not isinstance(item, Mapping)
            and not (isinstance(item, Sequence) and not isinstance(item, (str, bytes)))
            and str(item or "").strip()
        }
        if isinstance(metadata, Mapping):
            for key, item in metadata.items():
                cleaned_key = str(key or "").strip()
                cleaned_item = str(item or "").strip()
                if cleaned_key and cleaned_item:
                    target[cleaned_key] = cleaned_item
        return target
    if ":" in text:
        role, target_value = text.split(":", 1)
        if role.strip().lower().replace(" ", "_") == "question_figure":
            return {"role": "question_figure", "question_index": target_value.strip()}
    return {"role": "question_figure", "question_index": text}


def _question_figure_item_matches_repair_target(
    item: AssetItem,
    target: Mapping[str, str],
) -> bool:
    role = str(target.get("role", "question_figure") or "").strip().lower().replace(" ", "_")
    if role and role != "question_figure":
        return False
    item_id = str(getattr(item, "item_id", "") or "").strip()
    target_item_id = str(target.get("item_id", "") or "").strip()
    if item_id and target_item_id and item_id == target_item_id:
        return True
    item_metadata = dict(getattr(item, "metadata", {}) or {})
    item_target = _question_figure_target_value(item_metadata)
    target_value = _question_figure_target_value(target)
    if item_target and target_value and item_target == target_value:
        return True
    path = str(getattr(item, "path", "") or "").strip()
    target_path = str(target.get("path", "") or "").strip()
    if path and target_path and path == target_path:
        return True
    preview_path = _asset_item_preview_path(item)
    if preview_path and target_path and preview_path == target_path:
        return True
    cache_path = _asset_item_cached_path(item)
    target_cache_path = _question_figure_target_cache_path(target)
    if cache_path and target_cache_path and cache_path == target_cache_path:
        return True
    if cache_path and target_path and cache_path == target_path:
        return True
    asset_id = _asset_item_library_asset_id(item)
    target_asset_id = str(target.get("asset_id") or target.get("assetId") or "").strip()
    return bool(asset_id and target_asset_id and asset_id == target_asset_id)


def _question_figure_target_cache_path(target: Mapping[str, object]) -> str:
    for key in (
        "cache_path",
        "cachePath",
        "cached_path",
        "cachedPath",
        "local_path",
        "localPath",
        "local_cache_path",
        "localCachePath",
        "resolved_path",
        "resolvedPath",
        "download_path",
        "downloadPath",
        "asset_path",
        "assetPath",
    ):
        value = str(target.get(key) or "").strip()
        if value:
            return value
    return ""


def _question_figure_target_value(metadata: Mapping[str, object]) -> str:
    metadata = dict(metadata or {})
    return (
        str(metadata.get("question_index") or metadata.get("questionIndex") or "").strip()
        or str(metadata.get("question_id") or metadata.get("questionId") or "").strip()
        or str(metadata.get("question_no") or metadata.get("questionNo") or "").strip()
        or str(metadata.get("number") or metadata.get("no") or "").strip()
    )


def _question_figure_asset_items(asset_items) -> list[AssetItem]:
    items = [
        item
        for item in list(asset_items or [])
        if str(getattr(item, "role", "") or "").strip().lower().replace(" ", "_") == "question_figure"
        and (
            str(getattr(item, "path", "") or "").strip()
            or _asset_item_library_asset_id(item)
        )
    ]
    return [
        item
        for _index, item in sorted(
            enumerate(items),
            key=lambda pair: _question_figure_asset_sort_key(pair[1], pair[0]),
        )
    ]


def _question_figure_compare_options(
    question_items: Sequence[AssetItem],
    current_index: int,
) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    seen_references: set[str] = set()
    for index, item in enumerate(question_items):
        if index == current_index:
            continue
        reference = _asset_item_preview_reference(item)
        if not reference or reference in seen_references:
            continue
        display_name = _question_figure_compare_display_name(item, reference)
        options.append(
            {
                "label": (
                    f"题图 {_question_figure_compare_index_label(item, index)}："
                    f"{display_name}"
                ),
                "reference": reference,
                "source": _asset_item_source(item),
                "display_name": display_name,
                "kind_label": "题图对比",
            }
        )
        seen_references.add(reference)
    return options


def _question_figure_compare_index_label(item: AssetItem, fallback_index: int) -> str:
    metadata = dict(getattr(item, "metadata", {}) or {})
    return _question_figure_target_value(metadata) or str(fallback_index + 1)


def _question_figure_compare_display_name(item: AssetItem, reference: str) -> str:
    text = str(reference or "").strip()
    return Path(text).name or _asset_item_library_asset_id(item) or "题图"


def _asset_item_library_asset_id(item: AssetItem) -> str:
    metadata = dict(getattr(item, "metadata", {}) or {})
    return str(metadata.get("asset_id") or metadata.get("assetId") or "").strip()


def _asset_item_source(item: AssetItem) -> str:
    metadata = dict(getattr(item, "metadata", {}) or {})
    return str(
        metadata.get("source")
        or metadata.get("asset_source")
        or metadata.get("assetSource")
        or metadata.get("library_source")
        or metadata.get("librarySource")
        or ""
    ).strip()


def _asset_item_cached_path(item: AssetItem) -> str:
    metadata = dict(getattr(item, "metadata", {}) or {})
    for key in (
        "cache_path",
        "cachePath",
        "cached_path",
        "cachedPath",
        "local_path",
        "localPath",
        "local_cache_path",
        "localCachePath",
        "resolved_path",
        "resolvedPath",
        "download_path",
        "downloadPath",
        "asset_path",
        "assetPath",
    ):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _asset_item_preview_reference(item: AssetItem) -> str:
    path = str(getattr(item, "path", "") or "").strip()
    if path and Path(path).is_file():
        return path
    cache_path = _asset_item_cached_path(item)
    if cache_path and Path(cache_path).is_file():
        return cache_path
    thumbnail_path = _asset_item_thumbnail_path(item)
    if thumbnail_path:
        return thumbnail_path
    return path or cache_path


def _asset_item_thumbnail_path(item: AssetItem) -> str:
    metadata = dict(getattr(item, "metadata", {}) or {})
    for key in (
        "thumbnail_path",
        "thumbnailPath",
        "thumbnail_cache_path",
        "thumbnailCachePath",
        "thumbnail_local_path",
        "thumbnailLocalPath",
        "preview_path",
        "previewPath",
        "preview_cache_path",
        "previewCachePath",
    ):
        value = str(metadata.get(key) or "").strip()
        if value and Path(value).is_file():
            return value
    return ""


def _asset_item_preview_path(item: AssetItem) -> str:
    path = str(getattr(item, "path", "") or "").strip()
    if path and Path(path).is_file():
        return path
    cache_path = _asset_item_cached_path(item)
    if cache_path and Path(cache_path).is_file():
        return cache_path
    thumbnail_path = _asset_item_thumbnail_path(item)
    if thumbnail_path:
        return thumbnail_path
    return path or cache_path


def _question_figure_asset_sort_key(item: AssetItem, source_index: int) -> tuple[int, str, int, int]:
    metadata = dict(getattr(item, "metadata", {}) or {})
    target = _question_figure_target_value(metadata)
    order = _question_figure_order_value(metadata)
    try:
        target_number = int(target)
    except ValueError:
        target_number = 999_999
    return (
        target_number,
        target if target_number == 999_999 else "",
        order if order is not None else 999_999,
        source_index,
    )


def _question_figure_order_value(metadata: Mapping[str, object]) -> int | None:
    metadata = dict(metadata or {})
    for key in (
        "figure_order",
        "figureOrder",
        "figure_index",
        "figureIndex",
        "image_order",
        "imageOrder",
        "asset_order",
        "assetOrder",
        "order_within_question",
        "orderWithinQuestion",
        "sort_order",
        "sortOrder",
    ):
        value = str(metadata.get(key) or "").strip()
        if not value:
            continue
        try:
            return int(value)
        except ValueError:
            continue
    return None


def _asset_item_alt_text(item: AssetItem) -> str:
    metadata = dict(getattr(item, "metadata", {}) or {})
    for key in ("alt", "alt_text", "altText", "description", "caption"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def question_figure_detail_rows(asset_items) -> list[tuple[str, str, str, str]]:
    question_items = _question_figure_asset_items(asset_items)
    if len(question_items) <= 1:
        return []
    rows: list[tuple[str, str, str, str]] = []
    for item in question_items:
        metadata = dict(getattr(item, "metadata", {}) or {})
        path = str(getattr(item, "path", "") or "").strip()
        cache_path = _asset_item_cached_path(item)
        thumbnail_path = _asset_item_thumbnail_path(item)
        preview_path = _asset_item_preview_path(item)
        asset_id = _asset_item_library_asset_id(item)
        name = (
            Path(preview_path).name
            or asset_id
            or str(getattr(item, "label", "") or "未命名")
        )
        alt_text = _asset_item_alt_text(item)
        status = "可用" if path and Path(path).exists() else "缺文件"
        if not path and cache_path:
            status = "缓存" if Path(cache_path).exists() else "缓存缺失"
        elif not path and thumbnail_path:
            status = "缩略图"
        elif not path and asset_id:
            status = "仅元数据"
        if str(metadata.get("comparison_issue_status") or "").strip().lower() == "flagged":
            status = "对比问题"
        rows.append(
            (
                _question_figure_target_label(item),
                name,
                alt_text or "缺说明",
                status,
            )
        )
    return rows


_question_figure_detail_rows = question_figure_detail_rows
question_figure_candidate_list = _question_figure_candidate_list
question_figure_collection_summary = _question_figure_collection_summary
question_figure_item_summary = _question_figure_item_summary
repeated_question_figure_status = _repeated_question_figure_status
question_figure_target_label = _question_figure_target_label
question_figure_payload_matches_item = _question_figure_payload_matches_item
parse_question_figure_repair_target = _question_figure_repair_target_payload
question_figure_item_matches_repair_target = _question_figure_item_matches_repair_target
question_figure_target_cache_path = _question_figure_target_cache_path
question_figure_target_value = _question_figure_target_value
question_figure_items = _question_figure_asset_items
question_figure_compare_options = _question_figure_compare_options
question_figure_compare_index_label = _question_figure_compare_index_label
question_figure_compare_display_name = _question_figure_compare_display_name
asset_item_library_asset_id = _asset_item_library_asset_id
asset_item_source = _asset_item_source
asset_item_cached_path = _asset_item_cached_path
asset_item_preview_reference = _asset_item_preview_reference
asset_item_thumbnail_path = _asset_item_thumbnail_path
asset_item_preview_path = _asset_item_preview_path
question_figure_asset_sort_key = _question_figure_asset_sort_key
question_figure_order_value = _question_figure_order_value
asset_item_alt_text = _asset_item_alt_text


__all__ = [
    'question_figure_candidate_list',
    'question_figure_collection_summary',
    'question_figure_item_summary',
    'repeated_question_figure_status',
    'question_figure_target_label',
    'question_figure_payload_matches_item',
    'parse_question_figure_repair_target',
    'question_figure_item_matches_repair_target',
    'question_figure_target_cache_path',
    'question_figure_target_value',
    'question_figure_items',
    'question_figure_compare_options',
    'question_figure_compare_index_label',
    'question_figure_compare_display_name',
    'asset_item_library_asset_id',
    'asset_item_source',
    'asset_item_cached_path',
    'asset_item_preview_reference',
    'asset_item_thumbnail_path',
    'asset_item_preview_path',
    'question_figure_asset_sort_key',
    'question_figure_order_value',
    'asset_item_alt_text',
    'question_figure_detail_rows',
    '_question_figure_detail_rows',
    '_question_figure_candidate_list',
    '_question_figure_collection_summary',
    '_question_figure_item_summary',
    '_repeated_question_figure_status',
    '_question_figure_target_label',
    '_question_figure_payload_matches_item',
    '_question_figure_repair_target_payload',
    '_question_figure_item_matches_repair_target',
    '_question_figure_target_cache_path',
    '_question_figure_target_value',
    '_question_figure_asset_items',
    '_question_figure_compare_options',
    '_question_figure_compare_index_label',
    '_question_figure_compare_display_name',
    '_asset_item_library_asset_id',
    '_asset_item_source',
    '_asset_item_cached_path',
    '_asset_item_preview_reference',
    '_asset_item_thumbnail_path',
    '_asset_item_preview_path',
    '_question_figure_asset_sort_key',
    '_question_figure_order_value',
    '_asset_item_alt_text',
]
