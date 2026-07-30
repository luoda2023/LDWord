"""Persistent history and retry helpers for official-document batches."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Mapping, Sequence
from uuid import uuid4

from src.config.atomic_io import atomic_write_text
from src.config.material_batch import MaterialBatchSelection
from src.shared.io.artifact_publication import StagedArtifact, publish_staged_artifacts


HISTORY_KIND = "alavette.official_document.batch_history"
HISTORY_INDEX_KIND = "alavette.official_document.batch_history_index"
HISTORY_VERSION = 1


@dataclass(frozen=True, slots=True)
class OfficialDocumentBatchHistoryRecord:
    run_id: str
    created_at: str
    status: str
    source_kind: str
    source_path: str
    item_count: int
    success_count: int
    failed_count: int
    failed_profile_ids: tuple[str, ...]
    history_path: Path
    retry_of_run_id: str = ""
    attempt_number: int = 1
    report_payload: Mapping[str, object] = field(default_factory=dict)

    @property
    def retryable(self) -> bool:
        return bool(self.failed_profile_ids)

    def summary_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "status": self.status,
            "source_kind": self.source_kind,
            "source_path": self.source_path,
            "item_count": self.item_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "failed_profile_ids": list(self.failed_profile_ids),
            "history_path": str(self.history_path),
            "retry_of_run_id": self.retry_of_run_id,
            "attempt_number": self.attempt_number,
        }


def persist_official_document_batch_history(
    output_dir: Path | str,
    report_payload: Mapping[str, object],
    *,
    run_id: str = "",
    created_at: str = "",
    retry_of_run_id: str = "",
    attempt_number: int = 1,
    before_commit: Callable[[OfficialDocumentBatchHistoryRecord], None] | None = None,
) -> OfficialDocumentBatchHistoryRecord:
    """Append one immutable batch run after any required report publication."""

    history_dir = Path(output_dir) / "batch_history"
    normalized_created_at = str(created_at or "").strip() or _utc_now_text()
    normalized_run_id = _safe_id(run_id) if str(run_id or "").strip() else _new_run_id()
    history_path = history_dir / f"{normalized_run_id}.json"
    if history_path.exists():
        normalized_run_id = f"{normalized_run_id}_{uuid4().hex[:8]}"
        history_path = history_dir / f"{normalized_run_id}.json"

    record = _record_from_report(
        report_payload,
        history_path=history_path,
        run_id=normalized_run_id,
        created_at=normalized_created_at,
        retry_of_run_id=str(retry_of_run_id or "").strip(),
        attempt_number=max(1, int(attempt_number or 1)),
    )
    if before_commit is not None:
        before_commit(record)
    history_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": HISTORY_KIND,
        "version": HISTORY_VERSION,
        "record": record.summary_dict(),
        "report": dict(report_payload),
    }
    index_path = history_dir / "batch_history_index.json"
    with TemporaryDirectory(prefix=".batch-history-", dir=str(history_dir)) as temp_dir:
        staging_dir = Path(temp_dir)
        staged_history = staging_dir / history_path.name
        staged_index = staging_dir / index_path.name
        _atomic_write_json(staged_history, payload)
        _atomic_write_json(staged_index, _history_index_payload(history_dir, record))
        publish_staged_artifacts(
            (
                StagedArtifact("batch_history_run", staged_history, history_path),
                StagedArtifact("batch_history_index", staged_index, index_path),
            ),
            execution_id=f"official-batch-history-{record.run_id}-{uuid4().hex}",
            work_root=history_dir,
        )
    return record


def load_official_document_batch_history(
    path: Path | str,
) -> OfficialDocumentBatchHistoryRecord | None:
    """Load one validated history record without executing or mutating it."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("kind") != HISTORY_KIND or payload.get("version") != HISTORY_VERSION:
        return None
    summary = payload.get("record")
    report = payload.get("report")
    if not isinstance(summary, dict) or not isinstance(report, dict):
        return None
    run_id = str(summary.get("run_id") or "").strip()
    if not run_id:
        return None
    return OfficialDocumentBatchHistoryRecord(
        run_id=run_id,
        created_at=str(summary.get("created_at") or ""),
        status=str(summary.get("status") or "failed"),
        source_kind=str(summary.get("source_kind") or ""),
        source_path=str(summary.get("source_path") or ""),
        item_count=max(0, int(summary.get("item_count") or 0)),
        success_count=max(0, int(summary.get("success_count") or 0)),
        failed_count=max(0, int(summary.get("failed_count") or 0)),
        failed_profile_ids=tuple(_clean_ids(summary.get("failed_profile_ids"))),
        history_path=source,
        retry_of_run_id=str(summary.get("retry_of_run_id") or ""),
        attempt_number=max(1, int(summary.get("attempt_number") or 1)),
        report_payload=dict(report),
    )


def list_official_document_batch_history(
    output_dir: Path | str,
    *,
    source_path: str = "",
) -> tuple[OfficialDocumentBatchHistoryRecord, ...]:
    """List newest-first valid history records, optionally for one source file."""

    history_dir = Path(output_dir) / "batch_history"
    if not history_dir.is_dir():
        return ()
    target_source = str(source_path or "").strip()
    records: list[OfficialDocumentBatchHistoryRecord] = []
    for path in history_dir.glob("*.json"):
        if path.name == "batch_history_index.json":
            continue
        record = load_official_document_batch_history(path)
        if record is None:
            continue
        if target_source and record.source_path != target_source:
            continue
        records.append(record)
    records.sort(key=lambda item: (item.created_at, item.run_id), reverse=True)
    return tuple(records)


def official_document_batch_failed_profile_ids(
    payload: Mapping[str, object],
) -> tuple[str, ...]:
    """Return stable task ids that remain eligible for a retry."""

    failed: list[str] = []
    for item in list(payload.get("items", []) or []):
        if not isinstance(item, Mapping):
            continue
        if str(item.get("status") or "failed").strip() == "success":
            continue
        profile_id = str(item.get("profile_id") or "").strip()
        if profile_id and profile_id not in failed:
            failed.append(profile_id)
    for profile_id in _clean_ids(payload.get("pending_profile_ids")):
        if profile_id not in failed:
            failed.append(profile_id)
    return tuple(failed)


def build_official_document_batch_retry_selection(
    selection: MaterialBatchSelection,
    failed_profile_ids: Sequence[str],
    *,
    retry_of_run_id: str = "",
    attempt_number: int = 2,
) -> MaterialBatchSelection:
    """Clone a batch selection narrowed to failed ids; never mutate the source."""

    cloned = selection.clone()
    available = {profile.profile_id for profile in cloned.archive.profiles}
    requested = [
        profile_id
        for profile_id in _clean_ids(failed_profile_ids)
        if profile_id in available
    ]
    cloned.profile_ids = requested
    for profile_id in requested:
        metadata = dict(cloned.item_metadata.get(profile_id, {}) or {})
        metadata["retry_of_run_id"] = str(retry_of_run_id or "").strip()
        metadata["retry_attempt_number"] = max(2, int(attempt_number or 2))
        cloned.item_metadata[profile_id] = metadata
    return cloned


def _record_from_report(
    report_payload: Mapping[str, object],
    *,
    history_path: Path,
    run_id: str,
    created_at: str,
    retry_of_run_id: str,
    attempt_number: int,
) -> OfficialDocumentBatchHistoryRecord:
    items = [
        item
        for item in list(report_payload.get("items", []) or [])
        if isinstance(item, Mapping)
    ]
    failed_ids = official_document_batch_failed_profile_ids(report_payload)
    pending_ids = _clean_ids(report_payload.get("pending_profile_ids"))
    completed_ids = {
        str(item.get("profile_id") or "").strip()
        for item in items
        if str(item.get("profile_id") or "").strip()
    }
    success_count = sum(
        1 for item in items if str(item.get("status") or "").strip() == "success"
    )
    return OfficialDocumentBatchHistoryRecord(
        run_id=run_id,
        created_at=created_at,
        status=str(report_payload.get("status") or "failed"),
        source_kind=str(report_payload.get("batch_source_kind") or ""),
        source_path=str(report_payload.get("batch_source_path") or ""),
        item_count=len(items)
        + sum(1 for profile_id in pending_ids if profile_id not in completed_ids),
        success_count=success_count,
        failed_count=len(failed_ids),
        failed_profile_ids=failed_ids,
        history_path=history_path,
        retry_of_run_id=retry_of_run_id,
        attempt_number=attempt_number,
        report_payload=dict(report_payload),
    )


def _history_index_payload(
    history_dir: Path,
    record: OfficialDocumentBatchHistoryRecord,
) -> dict[str, object]:
    index_path = history_dir / "batch_history_index.json"
    records: list[dict[str, object]] = []
    try:
        existing = json.loads(index_path.read_text(encoding="utf-8"))
        if (
            isinstance(existing, dict)
            and existing.get("kind") == HISTORY_INDEX_KIND
            and existing.get("version") == HISTORY_VERSION
        ):
            records = [
                dict(item)
                for item in list(existing.get("records", []) or [])
                if isinstance(item, dict)
            ]
    except Exception:
        records = []
    records = [item for item in records if item.get("run_id") != record.run_id]
    records.append(record.summary_dict())
    records.sort(
        key=lambda item: (str(item.get("created_at") or ""), str(item.get("run_id") or "")),
        reverse=True,
    )
    return {
        "kind": HISTORY_INDEX_KIND,
        "version": HISTORY_VERSION,
        "records": records,
    }


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"run_{stamp}_{uuid4().hex[:8]}"


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return cleaned.strip("._") or _new_run_id()


def _clean_ids(values: object) -> list[str]:
    if isinstance(values, str):
        iterable = [values]
    else:
        try:
            iterable = list(values or [])
        except TypeError:
            iterable = []
    cleaned: list[str] = []
    for value in iterable:
        normalized = str(value or "").strip()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


__all__ = [
    "HISTORY_KIND",
    "HISTORY_INDEX_KIND",
    "HISTORY_VERSION",
    "OfficialDocumentBatchHistoryRecord",
    "build_official_document_batch_retry_selection",
    "list_official_document_batch_history",
    "load_official_document_batch_history",
    "official_document_batch_failed_profile_ids",
    "persist_official_document_batch_history",
]
