"""Attach frozen-session receipts and cleanup failures to terminal payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path

from src.config.atomic_io import atomic_write_text
from src.services.execution_session import ExecutionSessionSnapshot
from src.services.artifact_failure import (
    apply_artifact_failures,
    artifact_failure_record,
    record_artifact_failure,
)
from src.services.execution_result_contract import normalize_dict_payload


def attach_execution_session(
    payload: dict[str, object],
    execution_session: Mapping | None = None,
    *,
    snapshot: ExecutionSessionSnapshot | None = None,
) -> None:
    session_payload = normalize_dict_payload(execution_session)
    if not session_payload and snapshot is not None:
        session_payload = normalize_dict_payload(snapshot.to_dict())
    if not session_payload:
        return

    payload["execution_session"] = session_payload
    try:
        receipt_path = write_execution_session_receipt(session_payload)
    except OSError as exc:
        record_auxiliary_failure(payload, "execution_session", exc)
        return
    if receipt_path:
        payload["execution_session_path"] = receipt_path
        report_paths = list(payload.get("report_paths") or [])
        if receipt_path not in report_paths:
            report_paths.append(receipt_path)
            payload["report_paths"] = report_paths


def write_execution_session_receipt(payload: Mapping) -> str:
    output_namespace = str(payload.get("output_namespace") or "").strip()
    if not output_namespace:
        return ""
    target = Path(output_namespace) / "execution_session.json"
    atomic_write_text(
        target,
        json.dumps(dict(payload), ensure_ascii=False, indent=2),
    )
    return str(target)


def record_auxiliary_failure(
    payload: dict[str, object],
    kind: str,
    error: BaseException,
) -> None:
    record_artifact_failure(payload, kind, error)


def attach_cleanup_issues(
    payload: dict[str, object],
    issues: Sequence[object],
    *,
    snapshot: ExecutionSessionSnapshot | None,
) -> None:
    normalized_issues = tuple(str(issue) for issue in issues if str(issue or ""))
    if not normalized_issues:
        return
    namespace = str(getattr(snapshot, "output_namespace", "") or "")
    failures = [
        artifact_failure_record(
            "execution_session_cleanup",
            OSError(issue),
            path=namespace,
        )
        for issue in normalized_issues
    ]
    apply_artifact_failures(payload, failures)


__all__ = [
    "attach_cleanup_issues",
    "attach_execution_session",
    "record_auxiliary_failure",
    "write_execution_session_receipt",
]
