"""Local question-figure library metadata row helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from src.config.materials import AssetItem
from src.services.material_assets.common import (
    _metric_int,
    _metric_time_label,
    _ui_utc_now_iso,
)
from src.services.material_assets.question_figures import (
    asset_item_cached_path,
    asset_item_alt_text,
    asset_item_library_asset_id,
    asset_item_source,
    asset_item_thumbnail_path,
    question_figure_payload_matches_item,
    question_figure_items,
    question_figure_target_label,
    question_figure_target_value,
)

_URL_METADATA_WRITE_BLOCKLIST = {
    "download_url": ("download_url", "downloadUrl"),
    "asset_url": ("asset_url", "assetUrl"),
    "thumbnail_url": ("thumbnail_url", "thumbnailUrl"),
    "preview_url": (
        "preview_url",
        "previewUrl",
        "full_preview_url",
        "fullPreviewUrl",
        "full_size_preview_url",
        "fullSizePreviewUrl",
    ),
}


def question_figure_library_row_entries(
    asset_items,
) -> list[tuple[int, tuple[str, str, str, str, str]]]:
    question_items = question_figure_items(asset_items)
    if not any(question_figure_has_library_metadata(item) for item in question_items):
        return []
    rows: list[tuple[int, tuple[str, str, str, str, str]]] = []
    for index, item in enumerate(question_items):
        source = asset_item_source(item) or "local"
        asset_id = (
            asset_item_library_asset_id(item)
            or str(getattr(item, "item_id", "") or "").strip()
            or str(getattr(item, "label", "") or "").strip()
            or "-"
        )
        reference = question_figure_library_reference(item)
        rows.append(
            (
                index,
                (
                    question_figure_target_label(item),
                    source,
                    asset_id,
                    reference,
                    _asset_item_local_status(item),
                ),
            )
        )
    return rows


def question_figure_library_rows(asset_items) -> list[tuple[str, str, str, str, str]]:
    return [row for _index, row in question_figure_library_row_entries(asset_items)]


def question_figure_has_library_metadata(item: AssetItem) -> bool:
    return bool(
        asset_item_source(item)
        or asset_item_library_asset_id(item)
        or asset_item_cached_path(item)
        or asset_item_thumbnail_path(item)
    )


def question_figure_library_reference(item: AssetItem) -> str:
    path = str(getattr(item, "path", "") or "").strip()
    cache_path = asset_item_cached_path(item)
    thumbnail_path = asset_item_thumbnail_path(item)
    asset_id = asset_item_library_asset_id(item)
    for value in (cache_path, thumbnail_path, path):
        if value:
            return Path(value).name or value
    return asset_id or "-"


def question_figure_library_metadata_issue_entries(
    asset_items,
) -> list[tuple[int, tuple[str, str, str, str]]]:
    question_items = question_figure_items(asset_items)
    if not any(question_figure_has_library_metadata(item) for item in question_items):
        return []
    rows: list[tuple[int, tuple[str, str, str, str]]] = []
    duplicate_groups: dict[tuple[str, str], list[tuple[int, AssetItem]]] = {}
    for index, item in enumerate(question_items):
        source = asset_item_source(item)
        asset_id = asset_item_library_asset_id(item)
        source_label = question_figure_library_source_label(item)
        asset_label = question_figure_library_asset_label(item)
        target_label = question_figure_target_label(item)
        if not asset_item_alt_text(item):
            rows.append(
                (
                    index,
                    (
                        "\u7f3a\u56fe\u7247\u8bf4\u660e",
                        target_label,
                        source_label,
                        asset_label,
                    ),
                )
            )
        if question_figure_requires_library_identity(item):
            if not source:
                rows.append(
                    (
                        index,
                        (
                            "\u7f3a\u5e93\u6765\u6e90",
                            target_label,
                            "\u7f3a\u6765\u6e90",
                            asset_label,
                        ),
                    )
                )
            if source and source.lower() != "local" and not asset_id:
                rows.append(
                    (
                        index,
                        (
                            "\u7f3a\u7d20\u6750ID",
                            target_label,
                            source_label,
                            "\u7f3a\u7d20\u6750ID",
                        ),
                    )
                )
        if source and asset_id:
            key = (source.strip().lower(), asset_id.strip().lower())
            duplicate_groups.setdefault(key, []).append((index, item))
    for duplicate_items in duplicate_groups.values():
        if len(duplicate_items) < 2:
            continue
        for index, item in duplicate_items:
            rows.append(
                (
                    index,
                    (
                        "\u91cd\u590d\u7d20\u6750ID",
                        question_figure_target_label(item),
                        question_figure_library_source_label(item),
                        question_figure_library_asset_label(item),
                    ),
                )
            )
    return rows


def question_figure_library_source_label(item: AssetItem) -> str:
    source = asset_item_source(item)
    if source:
        return source
    path = str(getattr(item, "path", "") or "").strip()
    return "local" if path else "\u7f3a\u6765\u6e90"


def question_figure_library_asset_label(item: AssetItem) -> str:
    return (
        asset_item_library_asset_id(item)
        or str(getattr(item, "item_id", "") or "").strip()
        or str(getattr(item, "label", "") or "").strip()
        or "\u7f3a\u7d20\u6750ID"
    )


def question_figure_requires_library_identity(item: AssetItem) -> bool:
    path = str(getattr(item, "path", "") or "").strip()
    if asset_item_source(item) or asset_item_library_asset_id(item):
        return True
    return not path and bool(asset_item_cached_path(item) or asset_item_thumbnail_path(item))


def _asset_item_local_status(item: AssetItem) -> str:
    path = str(getattr(item, "path", "") or "").strip()
    preview_path = asset_item_cached_path(item) or asset_item_thumbnail_path(item)
    if path:
        return "本地可用" if Path(path).is_file() else "路径不可用"
    if preview_path:
        return "本地预览" if Path(preview_path).is_file() else "预览缺失"
    if asset_item_library_asset_id(item):
        return "仅元数据"
    return "未绑定"


def question_figure_library_master_version_entries(
    profiles: Sequence[object],
) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], dict[str, object]] = {}
    for profile_index, profile in enumerate(profiles or []):
        profile_id = str(getattr(profile, "profile_id", "") or "").strip()
        profile_name = str(getattr(profile, "profile_name", "") or "").strip()
        profile_label = profile_name or profile_id or f"profile_{profile_index + 1}"
        question_items = asset_items_from_payloads(getattr(profile, "asset_items", []))
        for question_row, item in enumerate(question_figure_items(question_items)):
            metadata = dict(getattr(item, "metadata", {}) or {})
            source = asset_item_source(item)
            asset_id = asset_item_library_asset_id(item)
            if not source or source.lower() == "local" or not asset_id:
                continue
            key = (source.strip().lower(), asset_id.strip().lower())
            package_id = (
                asset_metadata_package_id_value(metadata)
                or profile_id
                or profile_label
            )
            occurrence = {
                "profile_index": profile_index,
                "profile_id": profile_id,
                "profile_name": profile_label,
                "question_row": question_row,
                "target_label": question_figure_target_label(item),
                "package_id": package_id,
                "package_label": asset_metadata_package_label_value(metadata)
                or profile_label,
                "source": source,
                "asset_id": asset_id,
                "asset_version": asset_metadata_version_value(metadata),
                "asset_etag": asset_metadata_etag_value(metadata),
                "asset_updated_at": asset_metadata_updated_at_value(metadata),
                "alt_text": _asset_metadata_alt_text_value(metadata),
                "reference": asset_metadata_reference_value(metadata),
                "metadata": metadata,
            }
            group = groups.setdefault(
                key,
                {
                    "source": source,
                    "asset_id": asset_id,
                    "occurrences": [],
                },
            )
            occurrences = group["occurrences"]
            if isinstance(occurrences, list):
                occurrences.append(occurrence)

    rows: list[dict[str, object]] = []
    for (_source_key, _asset_key), group in groups.items():
        occurrences = [
            dict(item)
            for item in group.get("occurrences", [])
            if isinstance(item, Mapping)
        ]
        package_ids = {
            str(item.get("package_id") or "").strip().lower()
            for item in occurrences
            if str(item.get("package_id") or "").strip()
        }
        if len(package_ids) < 2:
            continue
        diff_fields = question_figure_master_version_diff_fields(occurrences)
        missing_version = any(
            not question_figure_master_version_has_version_statement(item)
            for item in occurrences
        )
        source = str(group.get("source") or "").strip()
        asset_id = str(group.get("asset_id") or "").strip()
        master_key = f"{source}/{asset_id}"
        if not diff_fields and not missing_version:
            continue
        if diff_fields:
            issue_status = "version_drift"
        else:
            issue_status = "missing_version_statement"
        rows.append(
            {
                "master_key": master_key,
                "source": source,
                "asset_id": asset_id,
                "occurrences": occurrences,
                "package_ids": sorted(
                    {
                        str(item.get("package_id") or "").strip()
                        for item in occurrences
                        if str(item.get("package_id") or "").strip()
                    }
                ),
                "profile_ids": [
                    str(item.get("profile_id") or item.get("profile_name") or "").strip()
                    for item in occurrences
                ],
                "package_summary": question_figure_master_version_package_summary(
                    occurrences
                ),
                "version_summary": question_figure_master_version_summary(occurrences),
                "diff_fields": diff_fields
                or (["version_statement"] if missing_version else []),
                "diff_summary": question_figure_master_version_diff_summary(
                    diff_fields,
                    missing_version=missing_version,
                ),
                "issue_status": issue_status,
                "status_label": question_figure_master_version_status_label(
                    issue_status
                ),
            }
        )
    rows.sort(key=lambda item: str(item.get("master_key") or ""))
    return rows


def asset_items_from_payloads(items: object) -> list[AssetItem]:
    result: list[AssetItem] = []
    for item in normalize_asset_item_payloads(items):
        result.append(
            AssetItem(
                item_id=str(item.get("item_id", "") or ""),
                label=str(item.get("label", "") or ""),
                role=str(item.get("role", "") or ""),
                path=str(item.get("path", "") or ""),
                mime_type=str(item.get("mime_type", "") or ""),
                tags=(
                    [str(tag) for tag in item.get("tags", [])]
                    if isinstance(item.get("tags"), list)
                    else []
                ),
                width_cm=(
                    item.get("width_cm")
                    if isinstance(item.get("width_cm"), (int, float))
                    else None
                ),
                metadata={
                    str(key): str(value)
                    for key, value in dict(item.get("metadata", {}) or {}).items()
                    if str(key or "").strip() and str(value or "").strip()
                },
            )
        )
    return result


def json_list_from_record_value(value: object) -> list[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    text = str(value or "").strip()
    if not text:
        return []
    try:
        loaded = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return [item.strip() for item in text.split(",") if item.strip()]
    if isinstance(loaded, Sequence) and not isinstance(loaded, (str, bytes, bytearray)):
        return list(loaded)
    return []













































































































































































































































































































































































def question_figure_master_version_diff_fields(
    occurrences: Sequence[Mapping[str, object]],
) -> list[str]:
    fields = (
        "asset_version",
        "asset_etag",
        "asset_updated_at",
        "alt_text",
        "reference",
    )
    diff_fields: list[str] = []
    for field in fields:
        values = {
            str(item.get(field) or "").strip()
            for item in occurrences
            if str(item.get(field) or "").strip()
        }
        if len(values) > 1:
            diff_fields.append(field)
            continue
        if values and any(not str(item.get(field) or "").strip() for item in occurrences):
            diff_fields.append(field)
    return diff_fields


def question_figure_master_version_has_version_statement(
    occurrence: Mapping[str, object],
) -> bool:
    return bool(
        str(occurrence.get("asset_version") or "").strip()
        or str(occurrence.get("asset_etag") or "").strip()
        or str(occurrence.get("asset_updated_at") or "").strip()
    )


def question_figure_master_version_package_summary(
    occurrences: Sequence[Mapping[str, object]],
) -> str:
    labels: list[str] = []
    for occurrence in occurrences:
        label = str(
            occurrence.get("package_label")
            or occurrence.get("package_id")
            or occurrence.get("profile_name")
            or ""
        ).strip()
        if label and label not in labels:
            labels.append(label)
    preview = "\u3001".join(labels[:3])
    if len(labels) > 3:
        return f"{preview} \u7b49 {len(labels)} \u5305"
    return preview or f"{len(occurrences)} \u5305"


def question_figure_master_version_summary(
    occurrences: Sequence[Mapping[str, object]],
) -> str:
    versions: list[str] = []
    for occurrence in occurrences:
        version = str(occurrence.get("asset_version") or "").strip()
        etag = str(occurrence.get("asset_etag") or "").strip()
        updated_at = str(occurrence.get("asset_updated_at") or "").strip()
        parts = [part for part in (version, etag, updated_at) if part]
        label = "/".join(parts) if parts else "\u7f3a\u7248\u672c"
        if label not in versions:
            versions.append(label)
    preview = "\u3001".join(versions[:3])
    if len(versions) > 3:
        return f"{preview} \u7b49 {len(versions)} \u7248"
    return preview or "\u7f3a\u7248\u672c"


def question_figure_master_version_diff_summary(
    diff_fields: Sequence[str],
    *,
    missing_version: bool,
) -> str:
    labels = {
        "asset_version": "\u7248\u672c",
        "asset_etag": "ETag",
        "asset_updated_at": "\u66f4\u65b0\u65f6\u95f4",
        "alt_text": "\u56fe\u7247\u8bf4\u660e",
        "reference": "URL/\u7f13\u5b58",
        "version_statement": "\u7248\u672c\u58f0\u660e",
    }
    fields = list(diff_fields)
    if missing_version:
        fields.append("version_statement")
    ordered: list[str] = []
    for field in fields:
        label = labels.get(str(field), str(field))
        if label not in ordered:
            ordered.append(label)
    return "\u3001".join(ordered) or "\u7248\u672c\u4e00\u81f4"


def question_figure_master_version_status_label(issue_status: object) -> str:
    return {
        "version_drift": "\u7248\u672c\u4e0d\u4e00\u81f4",
        "missing_version_statement": "\u7f3a\u7248\u672c\u58f0\u660e",
    }.get(str(issue_status or "").strip(), "\u9700\u68c0\u67e5")


def asset_metadata_package_id_value(metadata: Mapping[str, object]) -> str:
    return _metadata_first(
        metadata,
        (
            "library_package_id",
            "libraryPackageId",
            "package_id",
            "packageId",
            "material_package_id",
            "materialPackageId",
            "asset_package_id",
            "assetPackageId",
            "source_package_id",
            "sourcePackageId",
        ),
    )


def asset_metadata_package_label_value(metadata: Mapping[str, object]) -> str:
    return _metadata_first(
        metadata,
        (
            "library_package_name",
            "libraryPackageName",
            "package_name",
            "packageName",
            "material_package_name",
            "materialPackageName",
            "asset_package_name",
            "assetPackageName",
        ),
    )


def asset_metadata_version_value(metadata: Mapping[str, object]) -> str:
    return _metadata_first(
        metadata,
        (
            "asset_version",
            "assetVersion",
            "library_version",
            "libraryVersion",
            "remote_version",
            "remoteVersion",
            "master_version",
            "masterVersion",
            "version",
        ),
    )


def asset_metadata_etag_value(metadata: Mapping[str, object]) -> str:
    return _metadata_first(
        metadata,
        (
            "asset_etag",
            "assetEtag",
            "remote_etag",
            "remoteEtag",
            "library_etag",
            "libraryEtag",
            "etag",
            "content_hash",
            "contentHash",
            "hash",
        ),
    )


def asset_metadata_updated_at_value(metadata: Mapping[str, object]) -> str:
    return _metadata_first(
        metadata,
        (
            "asset_updated_at",
            "assetUpdatedAt",
            "remote_updated_at",
            "remoteUpdatedAt",
            "library_updated_at",
            "libraryUpdatedAt",
            "updated_at",
            "updatedAt",
            "modified_at",
            "modifiedAt",
            "last_modified",
            "lastModified",
        ),
    )


def asset_metadata_reference_value(metadata: Mapping[str, object]) -> str:
    return _metadata_first(
        metadata,
        (
            "reference",
            "cache_path",
            "cachePath",
            "cached_path",
            "cachedPath",
            "local_path",
            "localPath",
            "local_cache_path",
            "localCachePath",
        ),
    )








def _metadata_first(
    metadata: Mapping[str, object],
    keys: Sequence[str],
) -> str:
    for key in keys:
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def apply_question_figure_library_metadata(
    payloads: object,
    target: AssetItem,
    *,
    source: object,
    asset_id: object,
    alt_text: object,
) -> dict[str, object]:
    normalized_payloads = normalize_asset_item_payloads(payloads)
    for payload in normalized_payloads:
        if not question_figure_payload_matches_item(payload, target):
            continue
        before_metadata = dict(payload.get("metadata") or {})
        metadata = dict(before_metadata)
        set_optional_metadata_value(metadata, "source", source)
        set_optional_metadata_value(metadata, "asset_id", asset_id)
        set_optional_metadata_value(metadata, "alt_text", alt_text)
        payload["metadata"] = metadata
        return {
            "updated": True,
            "payloads": normalized_payloads,
            "history_record": question_figure_library_metadata_history_record(
                target,
                before_metadata,
                metadata,
            ),
        }
    return {
        "updated": False,
        "payloads": normalized_payloads,
        "history_record": None,
    }


def normalize_asset_item_payloads(items: object) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return normalized
    for item in items:
        if isinstance(item, AssetItem):
            payload = asset_item_payload(item)
        elif isinstance(item, Mapping):
            metadata = item.get("metadata", {})
            if not isinstance(metadata, Mapping):
                metadata = {}
            role = str(item.get("role", "") or "").strip().lower().replace(" ", "_")
            path = str(item.get("path", "") or "").strip()
            item_asset_id = _asset_metadata_asset_id_value(metadata)
            if not role or (not path and not item_asset_id):
                continue
            width = item.get("width_cm")
            try:
                width_cm = float(width) if width not in (None, "") else None
            except (TypeError, ValueError):
                width_cm = None
            raw_tags = item.get("tags", [])
            tags = (
                [str(tag) for tag in raw_tags]
                if isinstance(raw_tags, Sequence)
                and not isinstance(raw_tags, (str, bytes))
                else []
            )
            payload = {
                "item_id": str(item.get("item_id", "") or ""),
                "label": str(item.get("label", "") or "")
                or Path(path).stem
                or item_asset_id
                or role,
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


def asset_item_payload(item: AssetItem) -> dict[str, object]:
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


def normalized_asset_item_history_records(records: object) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        return normalized
    for record in records:
        if not isinstance(record, Mapping):
            continue
        action = str(record.get("action") or "").strip()
        changed_at = str(record.get("changed_at") or "").strip()
        if not action or not changed_at:
            continue
        normalized.append(
            {
                str(key): (
                    ",".join(str(item) for item in value)
                    if isinstance(value, Sequence)
                    and not isinstance(value, (str, bytes, bytearray))
                    else str(value)
                )
                for key, value in record.items()
                if str(key or "").strip() and str(value or "").strip()
            }
        )
    return normalized


def question_figure_library_metadata_history_record(
    item: AssetItem,
    before_metadata: Mapping[str, object],
    after_metadata: Mapping[str, object],
) -> dict[str, object] | None:
    before = dict(before_metadata or {})
    after = dict(after_metadata or {})
    changed_fields: list[str] = []
    for key, getter in (
        ("source", _asset_metadata_source_value),
        ("asset_id", _asset_metadata_asset_id_value),
        ("alt_text", _asset_metadata_alt_text_value),
    ):
        if getter(before) != getter(after):
            changed_fields.append(key)
    if not changed_fields:
        return None
    return {
        "schema_version": "1",
        "action": "question_figure_library_metadata_update",
        "changed_at": _ui_utc_now_iso(),
        "role": "question_figure",
        "item_id": str(getattr(item, "item_id", "") or "").strip(),
        "target_label": question_figure_target_label(item),
        "question_index": question_figure_target_value(after)
        or question_figure_target_value(before),
        "changed_fields": ",".join(changed_fields),
        "source_before": _asset_metadata_source_value(before),
        "source_after": _asset_metadata_source_value(after),
        "asset_id_before": _asset_metadata_asset_id_value(before),
        "asset_id_after": _asset_metadata_asset_id_value(after),
        "alt_text_before": _asset_metadata_alt_text_value(before),
        "alt_text_after": _asset_metadata_alt_text_value(after),
        "change_summary": question_figure_library_metadata_change_summary(
            changed_fields,
            before,
            after,
        ),
    }


def question_figure_library_version_history_entries(
    records: object,
    asset_items,
) -> list[tuple[int, int, tuple[str, str, str, str]]]:
    entries: list[tuple[int, int, tuple[str, str, str, str]]] = []
    normalized_records = normalized_asset_item_history_records(records)
    for record_index in range(len(normalized_records) - 1, -1, -1):
        record = normalized_records[record_index]
        if str(record.get("action") or "").strip() not in {
            "question_figure_library_metadata_update",
            "question_figure_library_metadata_rollback",
        }:
            continue
        question_row = question_figure_history_record_question_row(record, asset_items)
        entries.append(
            (
                record_index,
                question_row,
                (
                    _metric_time_label(record.get("changed_at")),
                    str(record.get("target_label") or "").strip() or "\u9898\u56fe",
                    question_figure_history_fields_label(record.get("changed_fields")),
                    str(record.get("change_summary") or "").strip()
                    or "metadata \u5df2\u66f4\u65b0",
                ),
            )
        )
    return entries


def rollback_question_figure_library_metadata(
    payloads: object,
    records: object,
    asset_items,
    record_index: int,
) -> dict[str, object]:
    normalized_records = normalized_asset_item_history_records(records)
    if record_index < 0 or record_index >= len(normalized_records):
        return {
            "status": "missing_record",
            "updated": False,
            "payloads": normalize_asset_item_payloads(payloads),
            "records": normalized_records,
            "question_row": -1,
            "rollback_record": None,
        }
    record = normalized_records[record_index]
    question_items = question_figure_items(asset_items)
    question_row = question_figure_history_record_question_row(record, question_items)
    if question_row < 0 or question_row >= len(question_items):
        return {
            "status": "missing_item",
            "updated": False,
            "payloads": normalize_asset_item_payloads(payloads),
            "records": normalized_records,
            "question_row": question_row,
            "rollback_record": None,
        }
    target = question_items[question_row]
    normalized_payloads = normalize_asset_item_payloads(payloads)
    for payload in normalized_payloads:
        if not question_figure_payload_matches_item(payload, target):
            continue
        current_metadata = dict(payload.get("metadata") or {})
        if not question_figure_history_record_matches_current(
            record,
            current_metadata,
        ):
            return {
                "status": "conflict",
                "updated": False,
                "payloads": normalized_payloads,
                "records": normalized_records,
                "question_row": question_row,
                "rollback_record": None,
            }
        restored_metadata = dict(current_metadata)
        for field in question_figure_history_changed_fields(record):
            set_optional_metadata_value(
                restored_metadata,
                field,
                record.get(f"{field}_before"),
            )
        rollback_record = question_figure_library_metadata_rollback_record(
            record,
            target,
            current_metadata,
            restored_metadata,
        )
        if rollback_record is None:
            return {
                "status": "no_change",
                "updated": False,
                "payloads": normalized_payloads,
                "records": normalized_records,
                "question_row": question_row,
                "rollback_record": None,
            }
        payload["metadata"] = restored_metadata
        return {
            "status": "rolled_back",
            "updated": True,
            "payloads": normalized_payloads,
            "records": [*normalized_records, rollback_record],
            "question_row": question_row,
            "rollback_record": rollback_record,
        }
    return {
        "status": "not_structured",
        "updated": False,
        "payloads": normalized_payloads,
        "records": normalized_records,
        "question_row": question_row,
        "rollback_record": None,
    }


def question_figure_library_metadata_rollback_record(
    source_record: Mapping[str, object],
    item: AssetItem,
    before_metadata: Mapping[str, object],
    after_metadata: Mapping[str, object],
) -> dict[str, object] | None:
    changed_fields = question_figure_history_changed_fields(source_record)
    if not changed_fields:
        return None
    return {
        "schema_version": "1",
        "action": "question_figure_library_metadata_rollback",
        "changed_at": _ui_utc_now_iso(),
        "role": "question_figure",
        "item_id": str(getattr(item, "item_id", "") or "").strip(),
        "target_label": question_figure_target_label(item),
        "question_index": question_figure_target_value(after_metadata)
        or question_figure_target_value(before_metadata),
        "changed_fields": ",".join(changed_fields),
        "source_before": _asset_metadata_source_value(before_metadata),
        "source_after": _asset_metadata_source_value(after_metadata),
        "asset_id_before": _asset_metadata_asset_id_value(before_metadata),
        "asset_id_after": _asset_metadata_asset_id_value(after_metadata),
        "alt_text_before": _asset_metadata_alt_text_value(before_metadata),
        "alt_text_after": _asset_metadata_alt_text_value(after_metadata),
        "rollback_from_changed_at": str(source_record.get("changed_at") or "").strip(),
        "change_summary": "\u56de\u6eda\uff1a"
        + question_figure_library_metadata_change_summary(
            changed_fields,
            before_metadata,
            after_metadata,
        ),
    }


def question_figure_history_changed_fields(record: Mapping[str, object]) -> list[str]:
    fields = [
        field.strip()
        for field in str(record.get("changed_fields") or "").split(",")
        if field.strip()
    ]
    allowed = {"source", "asset_id", "alt_text"}
    return [field for field in fields if field in allowed]


def question_figure_history_record_matches_current(
    record: Mapping[str, object],
    metadata: Mapping[str, object],
) -> bool:
    for field in question_figure_history_changed_fields(record):
        expected = str(record.get(f"{field}_after") or "").strip()
        if field == "source":
            current = _asset_metadata_source_value(metadata)
        elif field == "asset_id":
            current = _asset_metadata_asset_id_value(metadata)
        elif field == "alt_text":
            current = _asset_metadata_alt_text_value(metadata)
        else:
            current = ""
        if current != expected:
            return False
    return True


def question_figure_history_record_question_row(
    record: Mapping[str, object],
    asset_items,
) -> int:
    item_id = str(record.get("item_id") or "").strip()
    question_index = str(record.get("question_index") or "").strip()
    asset_id = str(
        record.get("asset_id_after") or record.get("asset_id_before") or ""
    ).strip()
    for index, item in enumerate(question_figure_items(asset_items)):
        metadata = dict(getattr(item, "metadata", {}) or {})
        if item_id and str(getattr(item, "item_id", "") or "").strip() == item_id:
            return index
        if question_index and question_figure_target_value(metadata) == question_index:
            return index
        if asset_id and asset_item_library_asset_id(item) == asset_id:
            return index
    return -1


def question_figure_history_fields_label(value: object) -> str:
    labels = {
        "source": "\u5e93\u6765\u6e90",
        "asset_id": "\u7d20\u6750ID",
        "asset_version": "\u7d20\u6750\u7248\u672c",
        "asset_etag": "\u7d20\u6750ETag",
        "asset_updated_at": "\u7d20\u6750\u66f4\u65b0\u65f6\u95f4",
        "alt_text": "\u56fe\u7247\u8bf4\u660e",
        "reference": "\u7d20\u6750\u5f15\u7528",
    }
    fields = [
        labels.get(field.strip(), field.strip())
        for field in str(value or "").split(",")
        if field.strip()
    ]
    return "\u3001".join(fields) or "metadata"


def question_figure_library_metadata_change_summary(
    changed_fields: Sequence[str],
    before: Mapping[str, object],
    after: Mapping[str, object],
) -> str:
    labels = {
        "source": "\u5e93\u6765\u6e90",
        "asset_id": "\u7d20\u6750ID",
        "alt_text": "\u56fe\u7247\u8bf4\u660e",
    }
    getters = {
        "source": _asset_metadata_source_value,
        "asset_id": _asset_metadata_asset_id_value,
        "alt_text": _asset_metadata_alt_text_value,
    }
    parts: list[str] = []
    for field in changed_fields:
        getter = getters[field]
        before_value = getter(before) or "\u7a7a"
        after_value = getter(after) or "\u7a7a"
        parts.append(f"{labels[field]}: {before_value} -> {after_value}")
    return "\uff1b".join(parts)


def set_optional_metadata_value(
    metadata: dict[str, object],
    key: str,
    value: object,
) -> None:
    alias_keys = {
        "asset_id": ("asset_id", "assetId"),
        "source": (
            "source",
            "asset_source",
            "assetSource",
            "library_source",
            "librarySource",
        ),
        "alt_text": ("alt_text", "altText", "alt", "description", "caption"),
        "asset_version": (
            "asset_version",
            "assetVersion",
            "library_version",
            "libraryVersion",
            "remote_version",
            "remoteVersion",
            "master_version",
            "masterVersion",
            "version",
        ),
        "asset_etag": (
            "asset_etag",
            "assetEtag",
            "remote_etag",
            "remoteEtag",
            "library_etag",
            "libraryEtag",
            "etag",
            "content_hash",
            "contentHash",
            "hash",
        ),
        "asset_updated_at": (
            "asset_updated_at",
            "assetUpdatedAt",
            "remote_updated_at",
            "remoteUpdatedAt",
            "library_updated_at",
            "libraryUpdatedAt",
            "updated_at",
            "updatedAt",
            "modified_at",
            "modifiedAt",
            "last_modified",
            "lastModified",
        ),
        "cache_path": (
            "cache_path",
            "cachePath",
            "cached_path",
            "cachedPath",
            "local_path",
            "localPath",
            "local_cache_path",
            "localCachePath",
        ),
    }
    cleaned = str(value or "").strip()
    if key in _URL_METADATA_WRITE_BLOCKLIST:
        for alias in _URL_METADATA_WRITE_BLOCKLIST[key]:
            metadata.pop(alias, None)
        return
    keys = alias_keys.get(key, (key,))
    if cleaned:
        for alias in keys:
            metadata.pop(alias, None)
        metadata[key] = cleaned
        return
    for alias in keys:
        metadata.pop(alias, None)


def _asset_metadata_asset_id_value(metadata: Mapping[str, object]) -> str:
    return str(metadata.get("asset_id") or metadata.get("assetId") or "").strip()


def _asset_metadata_source_value(metadata: Mapping[str, object]) -> str:
    return str(
        metadata.get("source")
        or metadata.get("asset_source")
        or metadata.get("assetSource")
        or metadata.get("library_source")
        or metadata.get("librarySource")
        or ""
    ).strip()


def _asset_metadata_alt_text_value(metadata: Mapping[str, object]) -> str:
    for key in ("alt", "alt_text", "altText", "description", "caption"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


_apply_question_figure_library_metadata = apply_question_figure_library_metadata
_asset_item_payload = asset_item_payload
_normalized_asset_item_payloads = normalize_asset_item_payloads
_normalized_asset_item_history_records = normalized_asset_item_history_records
_question_figure_library_metadata_history_record = (
    question_figure_library_metadata_history_record
)
_question_figure_library_version_history_entries = (
    question_figure_library_version_history_entries
)
_rollback_question_figure_library_metadata = rollback_question_figure_library_metadata
_question_figure_library_metadata_rollback_record = (
    question_figure_library_metadata_rollback_record
)
_question_figure_history_changed_fields = question_figure_history_changed_fields
_question_figure_history_record_matches_current = (
    question_figure_history_record_matches_current
)
_question_figure_history_record_question_row = (
    question_figure_history_record_question_row
)
_question_figure_history_fields_label = question_figure_history_fields_label
_question_figure_library_metadata_change_summary = (
    question_figure_library_metadata_change_summary
)
_set_optional_metadata_value = set_optional_metadata_value
_question_figure_library_row_entries = question_figure_library_row_entries
_question_figure_library_rows = question_figure_library_rows
_question_figure_has_library_metadata = question_figure_has_library_metadata
_question_figure_library_reference = question_figure_library_reference
_question_figure_library_metadata_issue_entries = (
    question_figure_library_metadata_issue_entries
)
_question_figure_library_source_label = question_figure_library_source_label
_question_figure_library_asset_label = question_figure_library_asset_label
_question_figure_requires_library_identity = question_figure_requires_library_identity
_asset_items_from_payloads = asset_items_from_payloads
_question_figure_library_master_version_entries = (
    question_figure_library_master_version_entries
)
_json_list_from_record_value = json_list_from_record_value
_question_figure_master_version_diff_fields = (
    question_figure_master_version_diff_fields
)
_question_figure_master_version_has_version_statement = (
    question_figure_master_version_has_version_statement
)
_question_figure_master_version_package_summary = (
    question_figure_master_version_package_summary
)
_question_figure_master_version_summary = question_figure_master_version_summary
_question_figure_master_version_diff_summary = (
    question_figure_master_version_diff_summary
)
_question_figure_master_version_status_label = (
    question_figure_master_version_status_label
)


__all__ = [
    "apply_question_figure_library_metadata",
    "asset_item_payload",
    "asset_items_from_payloads",
    "normalize_asset_item_payloads",
    "normalized_asset_item_history_records",
    "json_list_from_record_value",
    "question_figure_has_library_metadata",
    "question_figure_library_metadata_change_summary",
    "question_figure_library_metadata_history_record",
    "question_figure_library_metadata_rollback_record",
    "question_figure_library_asset_label",
    "question_figure_library_metadata_issue_entries",
    "question_figure_library_master_version_entries",
    "question_figure_library_reference",
    "question_figure_library_row_entries",
    "question_figure_library_rows",
    "question_figure_library_source_label",
    "question_figure_library_version_history_entries",
    "question_figure_history_changed_fields",
    "question_figure_history_fields_label",
    "question_figure_history_record_matches_current",
    "question_figure_history_record_question_row",
    "question_figure_master_version_diff_fields",
    "question_figure_master_version_diff_summary",
    "question_figure_master_version_has_version_statement",
    "question_figure_master_version_package_summary",
    "question_figure_master_version_status_label",
    "question_figure_master_version_summary",
    "question_figure_requires_library_identity",
    "rollback_question_figure_library_metadata",
    "set_optional_metadata_value",
    "_apply_question_figure_library_metadata",
    "_asset_item_payload",
    "_asset_items_from_payloads",
    "_normalized_asset_item_history_records",
    "_normalized_asset_item_payloads",
    "_json_list_from_record_value",
    "_question_figure_has_library_metadata",
    "_question_figure_history_changed_fields",
    "_question_figure_history_fields_label",
    "_question_figure_history_record_matches_current",
    "_question_figure_history_record_question_row",
    "_question_figure_library_asset_label",
    "_question_figure_library_metadata_issue_entries",
    "_question_figure_library_master_version_entries",
    "_question_figure_library_metadata_change_summary",
    "_question_figure_library_metadata_history_record",
    "_question_figure_library_metadata_rollback_record",
    "_question_figure_library_reference",
    "_question_figure_library_row_entries",
    "_question_figure_library_rows",
    "_question_figure_library_source_label",
    "_question_figure_library_version_history_entries",
    "_question_figure_master_version_diff_fields",
    "_question_figure_master_version_diff_summary",
    "_question_figure_master_version_has_version_statement",
    "_question_figure_master_version_package_summary",
    "_question_figure_master_version_status_label",
    "_question_figure_master_version_summary",
    "_question_figure_requires_library_identity",
    "_rollback_question_figure_library_metadata",
    "_set_optional_metadata_value",
]
