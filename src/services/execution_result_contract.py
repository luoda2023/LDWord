"""Pure terminal-payload normalization shared by GUI and headless execution.

The production runners return mapping payloads with a stable core and optional
domain extensions.  Normalization must never turn that extension surface into
an allow-list: new evidence produced by a runner remains observable by every
caller unless it is one of the explicitly normalized core fields below.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
from os import PathLike


TERMINAL_STATUSES = frozenset(
    {"success", "partial_success", "failed", "cancelled"}
)

PATH_MAP_FIELDS = (
    "output_paths",
    "compare_paths",
    "intermediate_paths",
    "material_manifest_paths",
    "material_package_paths",
    "scene_sample_manifest_paths",
)

DICT_PAYLOAD_FIELDS = (
    "output_target_preflight",
    "object_preflight",
    "material_field_consistency",
    "batch_isolation",
    "question_figure_repair_queue",
    "question_figure_comparison_matrix",
    "journal_submission_package",
    "official_document_assembly",
    "official_numbering_preservation",
    "technical_chapter_inventory",
    "application_section_word_limits",
    "material_assembly",
    "material_assembly_receipt",
    "material_package_receipt",
    "material_package_receipts",
    "material_assembly_error",
    "attachment_bundles",
    "material_dependency_usage",
    "style_source",
    "content_visibility_scan",
    "content_visibility_receipts",
    "exam_question_schema",
    "exam_delivery_runtime",
    "exam_markdown_import",
    "execution_session",
)

LIST_PAYLOAD_FIELDS = (
    "items",
    "pending_record_ids",
    "failed_items",
    "material_diagnostics",
    "content_visibility_preview",
)

_NORMALIZED_FIELDS = frozenset(
    {
        "status",
        "output_path",
        "report_paths",
        "failed_count",
        "artifact_failure_count",
        "artifact_failures",
        "error",
        "error_text",
        "diagnostics_count",
        "diagnostics_summary",
        "diagnostics_items",
        "diagnostics",
        "batch_issue_items",
        *PATH_MAP_FIELDS,
        *DICT_PAYLOAD_FIELDS,
        *LIST_PAYLOAD_FIELDS,
    }
)


def execution_result_status(result) -> str:
    """Return one declared terminal status or fail closed on an unknown value."""

    _require_mapping_result(result)
    status = result_value(result, "status")
    if status in TERMINAL_STATUSES:
        return str(status)
    raise ValueError(f"Unknown execution status: {status!r}")


def normalize_execution_result(result, status: str) -> dict[str, object]:
    """Build one canonical payload without discarding mapping extensions."""

    _require_mapping_result(result)
    normalized_status = str(status or "")
    if normalized_status not in TERMINAL_STATUSES:
        raise ValueError(f"Unknown execution status: {status!r}")
    declared_status = result_value(result, "status")
    if declared_status != normalized_status:
        raise ValueError(
            "Execution result status does not match normalization request: "
            f"{declared_status!r} != {normalized_status!r}"
        )

    payload = _mapping_extensions(result)
    path_payloads = {
        name: normalize_path_map(
            result_value(result, name),
            field_name=name,
        )
        for name in PATH_MAP_FIELDS
    }
    dict_payloads = {
        name: normalize_dict_payload(result_value(result, name))
        for name in DICT_PAYLOAD_FIELDS
    }
    list_payloads = {
        name: normalize_list_payload(result_value(result, name))
        for name in LIST_PAYLOAD_FIELDS
    }
    batch_issue_items = normalize_mapping_list(
        result_value(result, "batch_issue_items")
    )
    artifact_failures = normalize_mapping_list(
        result_value(result, "artifact_failures")
    )
    artifact_failure_count = max(
        _nonnegative_count(
            result_value(result, "artifact_failure_count", 0),
            field_name="artifact_failure_count",
        ),
        len(artifact_failures),
    )
    report_paths = normalize_path_list(
        result_value(result, "report_paths"),
        field_name="report_paths",
    )
    failed_items = list_payloads["failed_items"]
    failed_count = _nonnegative_count(
        result_value(result, "failed_count", len(failed_items)),
        field_name="failed_count",
    )
    declared_error = result_value(result, "error_text", "")
    if declared_error is None or declared_error == "":
        declared_error = result_value(result, "error", "")
    error_text = _text_field(
        declared_error,
        field_name="error_text",
    )
    diagnostics_count = _nonnegative_count(
        result_value(result, "diagnostics_count", 0),
        field_name="diagnostics_count",
    )
    diagnostics_summary = _text_field(
        result_value(result, "diagnostics_summary", ""),
        field_name="diagnostics_summary",
    )
    diagnostics_items = result_diagnostics_items(result)

    output_paths = path_payloads["output_paths"]
    output_path = normalize_optional_path(
        result_value(result, "output_path", ""),
        field_name="output_path",
    )
    if not output_path and output_paths:
        output_path = str(
            output_paths.get("final") or next(iter(output_paths.values()), "")
        )

    payload.update(
        {
            "status": normalized_status,
            "output_path": output_path,
            "report_paths": report_paths,
            "failed_count": failed_count,
            "error_text": error_text,
            "diagnostics_count": diagnostics_count,
            "diagnostics_summary": diagnostics_summary,
        }
    )
    payload.update({name: item for name, item in path_payloads.items() if item})
    payload.update(
        {
            name: item
            for name, item in dict_payloads.items()
            if item or _explicit_mapping_field(result, name)
        }
    )
    payload.update({name: item for name, item in list_payloads.items() if item})
    if batch_issue_items:
        payload["batch_issue_items"] = batch_issue_items
    if diagnostics_items:
        payload["diagnostics_items"] = diagnostics_items
    if artifact_failures:
        payload["artifact_failures"] = artifact_failures
    if artifact_failure_count:
        payload["artifact_failure_count"] = artifact_failure_count
    return normalize_terminal_payload(payload)


def result_value(result, name: str, default=None):
    if isinstance(result, Mapping):
        return result.get(name, default)
    raise TypeError(
        "Execution result must be a mapping, "
        f"got {type(result).__module__}.{type(result).__qualname__}"
    )


def result_diagnostics_items(result) -> list[dict[str, object]]:
    _require_mapping_result(result)
    if "diagnostics_items" in result:
        return normalize_mapping_list(result.get("diagnostics_items"))
    raw_items = None
    if "diagnostics" in result:
        diagnostics = result.get("diagnostics")
        if diagnostics is not None and not isinstance(diagnostics, Mapping):
            raise TypeError(
                "Terminal payload field 'diagnostics' must be a mapping or null"
            )
        if isinstance(diagnostics, Mapping):
            raw_items = diagnostics.get("items")
    if raw_items is not None:
        return normalize_mapping_list(raw_items)
    if not result.get("batch_issue_items"):
        raw_items = result.get("material_diagnostics")
    return normalize_mapping_list(raw_items)


def normalize_path_map(value, *, field_name: str = "path_map") -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(
            f"Terminal payload field {field_name!r} must be a mapping or null"
        )
    payload: dict[str, str] = {}
    for raw_key, raw_path in value.items():
        key = _plain_path_token(
            raw_key,
            path=f"$.{field_name}.<key>",
        )
        path = _plain_path_token(
            raw_path,
            path=_child_path(f"$.{field_name}", key),
        )
        if key in payload:
            raise TypeError(
                f"Terminal payload key collision at $.{field_name}: {key!r}"
            )
        payload[key] = path
    return payload


def normalize_path_list(value, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise TypeError(
            f"Terminal payload field {field_name!r} must be a list, tuple, or null"
        )
    return [
        _plain_path_token(item, path=f"$.{field_name}[{index}]")
        for index, item in enumerate(value)
    ]


def normalize_optional_path(value, *, field_name: str) -> str:
    if value is None or value == "":
        return ""
    return _plain_path_token(value, path=f"$.{field_name}")


def normalize_dict_payload(value) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(
            "Terminal payload mapping field must be a mapping or null, "
            f"got {type(value).__module__}.{type(value).__qualname__}"
        )
    return plain_payload(value)


def normalize_mapping_list(value) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise TypeError(
            "Terminal payload mapping-list field must be a list, tuple, or null, "
            f"got {type(value).__module__}.{type(value).__qualname__}"
        )
    payload: list[dict[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise TypeError(
                "Terminal payload mapping-list item must be a mapping at "
                f"$[{index}], got {type(item).__module__}.{type(item).__qualname__}"
            )
        normalized = plain_payload(item)
        if not isinstance(normalized, dict):  # pragma: no cover - guarded above
            raise TypeError("Terminal mapping-list item did not normalize to a mapping")
        payload.append(normalized)
    return payload


def normalize_list_payload(value) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise TypeError(
            "Terminal payload list field must be a list, tuple, or null, "
            f"got {type(value).__module__}.{type(value).__qualname__}"
        )
    return [plain_payload(item) for item in value]


def normalize_terminal_payload(value) -> dict[str, object]:
    """Return one isolated JSON/plain-data terminal mapping.

    Terminal payloads cross worker/UI boundaries and therefore may not retain
    live Python objects.  Unsupported leaves and recursive containers are
    rejected instead of being stringified or shallow-copied.
    """

    if not isinstance(value, Mapping):
        raise TypeError(
            "Terminal payload must be a mapping, "
            f"got {type(value).__name__}"
        )
    payload = _plain_payload(value, path="$", active_container_ids=set())
    if not isinstance(payload, dict):  # pragma: no cover - guarded above
        raise TypeError("Terminal payload normalization did not produce a mapping")
    return payload


def plain_payload(value):
    """Return an isolated JSON/plain-data value or reject the live object."""

    return _plain_payload(value, path="$", active_container_ids=set())


def _plain_payload(value, *, path: str, active_container_ids: set[int]):
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(
                f"Unsupported non-finite float at {path}: {value!r}"
            )
        return float(value)
    if isinstance(value, PathLike):
        return str(value)
    if isinstance(value, Mapping):
        return _plain_mapping(
            value,
            path=path,
            active_container_ids=active_container_ids,
        )
    if isinstance(value, (list, tuple)):
        return _plain_sequence(
            value,
            path=path,
            active_container_ids=active_container_ids,
        )
    raise TypeError(
        f"Unsupported terminal payload value at {path}: "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def _plain_mapping(
    value: Mapping,
    *,
    path: str,
    active_container_ids: set[int],
) -> dict[str, object]:
    container_id = id(value)
    _enter_container(container_id, path, active_container_ids)
    try:
        payload: dict[str, object] = {}
        for key, item in value.items():
            normalized_key = _plain_mapping_key(key, path=path)
            if normalized_key in payload:
                raise TypeError(
                    f"Terminal payload key collision at {path}: "
                    f"{normalized_key!r}"
                )
            payload[normalized_key] = _plain_payload(
                item,
                path=_child_path(path, normalized_key),
                active_container_ids=active_container_ids,
            )
        return payload
    finally:
        active_container_ids.remove(container_id)


def _plain_sequence(
    value: list | tuple,
    *,
    path: str,
    active_container_ids: set[int],
) -> list[object]:
    container_id = id(value)
    _enter_container(container_id, path, active_container_ids)
    try:
        return [
            _plain_payload(
                item,
                path=f"{path}[{index}]",
                active_container_ids=active_container_ids,
            )
            for index, item in enumerate(value)
        ]
    finally:
        active_container_ids.remove(container_id)


def _plain_mapping_key(value, *, path: str) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        return str(int(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(
                f"Unsupported non-finite mapping key at {path}: {value!r}"
            )
        return str(float(value))
    if isinstance(value, PathLike):
        return str(value)
    raise TypeError(
        f"Unsupported terminal payload key at {path}: "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def _plain_path_token(value, *, path: str) -> str:
    if value is None:
        raise TypeError(f"Terminal path token must not be null at {path}")
    token = _plain_mapping_key(value, path=path)
    if not token.strip():
        raise TypeError(f"Terminal path token must not be blank at {path}")
    return token


def _enter_container(
    container_id: int,
    path: str,
    active_container_ids: set[int],
) -> None:
    if container_id in active_container_ids:
        raise TypeError(f"Recursive terminal payload container at {path}")
    active_container_ids.add(container_id)


def _child_path(path: str, key: str) -> str:
    if key.isidentifier():
        return f"{path}.{key}"
    return f"{path}[{key!r}]"


def _mapping_extensions(result) -> dict[str, object]:
    if not isinstance(result, Mapping):
        return {}
    extensions: dict[str, object] = {}
    seen_keys: set[str] = set()
    for key, value in result.items():
        normalized_key = _plain_mapping_key(key, path="$")
        if normalized_key in seen_keys:
            raise TypeError(
                "Terminal payload key collision at $: "
                f"{normalized_key!r}"
            )
        seen_keys.add(normalized_key)
        if normalized_key in _NORMALIZED_FIELDS:
            continue
        extensions[normalized_key] = value
    return normalize_terminal_payload(extensions)


def _explicit_mapping_field(result, name: str) -> bool:
    return name in result and isinstance(result.get(name), Mapping)


def _require_mapping_result(result) -> None:
    if isinstance(result, Mapping):
        return
    raise TypeError(
        "Execution result must be a mapping, "
        f"got {type(result).__module__}.{type(result).__qualname__}"
    )


def _nonnegative_count(value, *, field_name: str) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"Terminal payload field {field_name!r} must be an integer or null"
        )
    if value < 0:
        raise ValueError(
            f"Terminal payload field {field_name!r} must not be negative"
        )
    return int(value)


def _text_field(value, *, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError(
            f"Terminal payload field {field_name!r} must be a string or null"
        )
    return value


__all__ = [
    "execution_result_status",
    "normalize_dict_payload",
    "normalize_execution_result",
    "normalize_mapping_list",
    "normalize_optional_path",
    "normalize_path_list",
    "normalize_path_map",
    "normalize_terminal_payload",
    "plain_payload",
]
