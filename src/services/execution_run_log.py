"""Best-effort persistent receipts for Workbench document executions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from uuid import uuid4

from src.app_paths import log_data_root


EXECUTION_RUN_LOG_SCHEMA = "workbench-execution-run-v1"
EXECUTION_RUN_LOG_FILE = "execution_runs.jsonl"
_LOCK = threading.Lock()


def append_execution_run(
    payload: Mapping[str, object],
    *,
    log_root: str | Path | None = None,
) -> Path:
    """Append one bounded JSON receipt without exposing material field values."""

    root = Path(log_root) if log_root is not None else log_data_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / EXECUTION_RUN_LOG_FILE
    record = {
        "schema_version": EXECUTION_RUN_LOG_SCHEMA,
        "execution_id": uuid4().hex,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": str(payload.get("status") or ""),
        "execution_route": str(payload.get("execution_route") or ""),
        "plan_id": str(payload.get("plan_id") or ""),
        "template_id": str(payload.get("template_id") or ""),
        "input_paths": _string_list(payload.get("input_paths")),
        "output_path": str(payload.get("output_path") or ""),
        "output_paths": _string_mapping(payload.get("output_paths")),
        "output_root": str(payload.get("output_root") or ""),
        "modules_enabled": _integer(payload.get("modules_enabled")),
        "modules_total": _integer(payload.get("modules_total")),
        "material_snapshot_id": str(
            payload.get("execution_material_snapshot_id") or ""
        ),
        "format_change_evidence": _plain_mapping(
            payload.get("format_change_evidence")
        ),
        "error_text": str(payload.get("error_text") or ""),
    }
    line = json.dumps(
        record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    with _LOCK:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line + "\n")
            stream.flush()
    return path


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if str(key or "").strip() and str(item or "").strip()
    }


def _plain_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    allowed = {
        "schema_version",
        "status",
        "reason",
        "format_changed",
        "content_changed",
        "format_elements_added",
        "format_elements_removed",
        "documents_total",
        "documents_compared",
        "documents_unchanged",
        "before",
        "after",
    }
    return {str(key): item for key, item in value.items() if key in allowed}


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "EXECUTION_RUN_LOG_FILE",
    "EXECUTION_RUN_LOG_SCHEMA",
    "append_execution_run",
]
