"""Pure UI/report projections for the material dependency graph.

Ownership remains in field/image/attachment configuration.  These projections
only describe cross-resource usage and the attachment package tree; callers
must never write them back into a profile or snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.config.attachment_materials import (
    AttachmentBinding,
    attachment_natural_path_key,
)
from src.shared.engine.material_dependency_index import MaterialDependencyIndex


def project_material_dependency_usage(
    index: MaterialDependencyIndex | Mapping[str, object],
) -> dict[str, object]:
    payload = _index_payload(index)
    occurrences = [
        dict(item)
        for item in _sequence(payload.get("occurrences"))
        if isinstance(item, Mapping)
    ]
    diagnostics = [
        dict(item)
        for item in _sequence(payload.get("diagnostics"))
        if isinstance(item, Mapping)
    ]
    consumers: dict[str, dict[str, object]] = {}
    resources: dict[tuple[str, str], dict[str, object]] = {}
    for occurrence in occurrences:
        consumer = _mapping(occurrence.get("consumer"))
        consumer_id = str(consumer.get("consumer_id") or "")
        kind = str(occurrence.get("kind") or "")
        resource_key = str(occurrence.get("resource_key") or "")
        consumer_row = consumers.setdefault(
            consumer_id,
            {
                "consumer": consumer,
                "occurrences": [],
                "tokens": [],
                "field_count": 0,
                "image_count": 0,
                "content_count": 0,
                "diagnostics": [],
            },
        )
        consumer_row["occurrences"].append(occurrence)  # type: ignore[union-attr]
        _append_unique(consumer_row["tokens"], str(occurrence.get("token") or ""))
        counter = f"{kind}_count"
        if counter in consumer_row:
            consumer_row[counter] = int(consumer_row[counter]) + 1

        resource_row = resources.setdefault(
            (kind, resource_key),
            {
                "kind": kind,
                "resource_key": resource_key,
                "tokens": [],
                "occurrences": [],
                "consumers": {},
            },
        )
        _append_unique(resource_row["tokens"], str(occurrence.get("token") or ""))
        resource_row["occurrences"].append(occurrence)  # type: ignore[union-attr]
        consumer_usage = resource_row["consumers"].setdefault(  # type: ignore[union-attr]
            consumer_id,
            {
                "consumer": consumer,
                "occurrence_count": 0,
                "occurrence_ids": [],
            },
        )
        consumer_usage["occurrence_count"] += 1
        consumer_usage["occurrence_ids"].append(
            str(occurrence.get("occurrence_id") or "")
        )

    for diagnostic in diagnostics:
        consumer = _mapping(diagnostic.get("consumer"))
        consumer_id = str(consumer.get("consumer_id") or "")
        row = consumers.setdefault(
            consumer_id,
            {
                "consumer": consumer,
                "occurrences": [],
                "tokens": [],
                "field_count": 0,
                "image_count": 0,
                "content_count": 0,
                "diagnostics": [],
            },
        )
        row["diagnostics"].append(diagnostic)  # type: ignore[union-attr]

    consumer_rows = []
    for consumer_id, row in sorted(
        consumers.items(),
        key=lambda item: item[0].casefold(),
    ):
        consumer_rows.append(
            {
                **row,
                "consumer_id": consumer_id,
                "occurrence_count": len(row["occurrences"]),
                "diagnostic_count": len(row["diagnostics"]),
            }
        )
    resource_rows = []
    for _identity, row in sorted(
        resources.items(),
        key=lambda item: (item[0][0], item[0][1].casefold()),
    ):
        consumer_values = list(row.pop("consumers").values())
        kinds = [
            str(_mapping(item.get("consumer")).get("kind") or "")
            for item in consumer_values
        ]
        resource_rows.append(
            {
                **row,
                "occurrence_count": len(row["occurrences"]),
                "consumer_count": len(consumer_values),
                "main_consumer_count": kinds.count("main_document"),
                "content_consumer_count": kinds.count("content_source"),
                "attachment_consumer_count": kinds.count("attachment_item"),
                "consumers": consumer_values,
            }
        )
    return {
        "index_id": str(payload.get("index_id") or ""),
        "scanner_contract": str(payload.get("scanner_contract") or ""),
        "occurrence_count": len(occurrences),
        "diagnostic_count": len(diagnostics),
        "consumers": consumer_rows,
        "resources": resource_rows,
        "fields": [item for item in resource_rows if item["kind"] == "field"],
        "images": [item for item in resource_rows if item["kind"] == "image"],
        "content": [item for item in resource_rows if item["kind"] == "content"],
    }


def project_attachment_binding(
    binding: AttachmentBinding,
    dependency_index: MaterialDependencyIndex | Mapping[str, object] | None = None,
) -> dict[str, object]:
    if not isinstance(binding, AttachmentBinding):
        raise TypeError("binding must be an AttachmentBinding")
    usage = (
        project_material_dependency_usage(dependency_index)
        if dependency_index is not None
        else {"consumers": []}
    )
    usage_by_consumer = {
        str(item.get("consumer_id") or ""): item
        for item in _sequence(usage.get("consumers"))
        if isinstance(item, Mapping)
    }
    files = []
    for item in binding.items:
        consumer_id = f"attachment:{binding.role}:{item.item_id}"
        dependency = dict(usage_by_consumer.get(consumer_id, {}))
        files.append(
            {
                "item_id": item.item_id,
                "relative_path": item.relative_path,
                "original_name": item.file_ref.original_name,
                "media_type": item.file_ref.media_type,
                "byte_size": item.file_ref.byte_size,
                "consumer_id": consumer_id,
                "dependency": dependency,
            }
        )
    return {
        "role": binding.role,
        "label": binding.label or binding.role,
        "source_kind": binding.source_kind.value,
        "processing_mode": binding.processing_mode.value,
        "recursive": binding.recursive,
        "binding_revision": binding.binding_revision,
        "file_count": len(files),
        "processable_docx_count": sum(
            1
            for item in binding.items
            if item.relative_path.casefold().endswith(".docx")
        ),
        "opaque_file_count": sum(
            1
            for item in binding.items
            if not item.relative_path.casefold().endswith(".docx")
        ),
        "field_occurrence_count": sum(
            int(_mapping(item["dependency"]).get("field_count") or 0)
            for item in files
        ),
        "image_occurrence_count": sum(
            int(_mapping(item["dependency"]).get("image_count") or 0)
            for item in files
        ),
        "diagnostic_count": sum(
            int(_mapping(item["dependency"]).get("diagnostic_count") or 0)
            for item in files
        ),
        "files": files,
        "tree": _attachment_tree(item.relative_path for item in binding.items),
    }


def _attachment_tree(relative_paths) -> list[dict[str, object]]:
    root: dict[str, Any] = {}
    for relative_path in sorted(relative_paths, key=attachment_natural_path_key):
        parts = str(relative_path).split("/")
        cursor = root
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {"__files__": []})
        cursor.setdefault("__files__", []).append(parts[-1])

    def project(node: dict[str, Any], prefix: tuple[str, ...]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for name in sorted(
            (key for key in node if key != "__files__"),
            key=attachment_natural_path_key,
        ):
            path = (*prefix, name)
            rows.append(
                {
                    "kind": "directory",
                    "name": name,
                    "path": "/".join(path),
                    "children": project(node[name], path),
                }
            )
        for name in sorted(
            node.get("__files__", []),
            key=attachment_natural_path_key,
        ):
            path = (*prefix, name)
            rows.append(
                {
                    "kind": "file",
                    "name": name,
                    "path": "/".join(path),
                    "children": [],
                }
            )
        return rows

    return project(root, ())


def _index_payload(
    index: MaterialDependencyIndex | Mapping[str, object],
) -> dict[str, object]:
    if isinstance(index, MaterialDependencyIndex):
        return index.to_dict()
    if isinstance(index, Mapping):
        return dict(index)
    raise TypeError("index must be a MaterialDependencyIndex or mapping")


def _append_unique(values: object, value: str) -> None:
    if not value or not isinstance(values, list) or value in values:
        return
    values.append(value)


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


__all__ = [
    "project_attachment_binding",
    "project_material_dependency_usage",
]
