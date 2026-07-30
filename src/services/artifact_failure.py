"""Single plain-data policy for auxiliary artifact failures."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TypeVar


T = TypeVar("T")


def artifact_failure_record(
    kind: object,
    error: BaseException | object,
    *,
    path: object = "",
) -> dict[str, str]:
    """Create the canonical JSON-safe record for one auxiliary failure."""

    resolved_path = path or getattr(error, "filename", "") or ""
    error_type = type(error).__name__
    return {
        "kind": str(kind or "artifact"),
        "path": str(resolved_path),
        "error_type": error_type,
        "error": str(error) or error_type,
    }


def capture_artifact_write(
    failures: list[dict[str, str]],
    kind: str,
    writer: Callable[[], T],
    default: T,
) -> T:
    """Keep a published core result visible when an auxiliary writer fails."""

    try:
        return writer()
    except Exception as exc:
        failures.append(artifact_failure_record(kind, exc))
        return default


def with_artifact_failure_text(
    original: str,
    failures: Sequence[Mapping[str, object]],
) -> str:
    if not failures:
        return str(original or "")
    detail = "; ".join(
        f"{item.get('kind', 'artifact')}: {item.get('error', 'unknown error')}"
        for item in failures
    )
    base = str(original or "").strip()
    if base:
        return f"{base}; auxiliary artifact failures: {detail}"
    return f"auxiliary artifact failures: {detail}"


def apply_artifact_failures(
    payload: dict[str, object],
    failures: Sequence[Mapping[str, object]],
) -> None:
    """Merge new failure evidence and apply the shared terminal-status rule."""

    new_failures = [dict(item) for item in failures]
    if not new_failures:
        return
    existing = [
        dict(item)
        for item in list(payload.get("artifact_failures") or [])
        if isinstance(item, Mapping)
    ]
    payload["artifact_failures"] = [*existing, *new_failures]
    payload["artifact_failure_count"] = len(existing) + len(new_failures)
    payload["error_text"] = with_artifact_failure_text(
        str(payload.get("error_text") or ""),
        new_failures,
    )
    if str(payload.get("status") or "") == "success":
        payload["status"] = "partial_success"


def record_artifact_failure(
    payload: dict[str, object],
    kind: object,
    error: BaseException | object,
    *,
    path: object = "",
) -> None:
    apply_artifact_failures(
        payload,
        [artifact_failure_record(kind, error, path=path)],
    )


__all__ = [
    "apply_artifact_failures",
    "artifact_failure_record",
    "capture_artifact_write",
    "record_artifact_failure",
    "with_artifact_failure_text",
]
