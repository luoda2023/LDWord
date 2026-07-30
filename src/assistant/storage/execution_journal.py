"""Atomic execution journal used to reconcile document jobs after a restart."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path
import re
from typing import Any

from src.assistant.contracts.serialization import plain_data
from src.assistant.storage.paths import assistant_storage_root


EXECUTION_JOURNAL_SCHEMA_VERSION = "form-assistant-execution-v1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


@dataclass(frozen=True, slots=True)
class ExecutionJournalRecord:
    execution_id: str
    session_id: str
    plan_id: str
    plan_revision: int
    plan_fingerprint: str
    status: str
    started_at: str
    completed_at: str = ""
    result: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("execution_id", "session_id", "plan_id"):
            if not _SAFE_ID.fullmatch(str(getattr(self, name) or "")):
                raise ValueError(f"Unsafe execution journal identity: {name}")
        if self.plan_revision < 1:
            raise ValueError("Execution journal plan revision must be positive")
        if not str(self.plan_fingerprint or "").strip():
            raise ValueError("Execution journal plan fingerprint is required")
        if self.status not in {
            "running",
            "success",
            "partial_success",
            "failed",
            "cancelled",
        }:
            raise ValueError(f"Unsupported execution journal status: {self.status!r}")
        object.__setattr__(self, "result", dict(plain_data(self.result)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": EXECUTION_JOURNAL_SCHEMA_VERSION,
            "contract_kind": "assistant_execution_journal",
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "plan_id": self.plan_id,
            "plan_revision": self.plan_revision,
            "plan_fingerprint": self.plan_fingerprint,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": dict(self.result),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExecutionJournalRecord":
        if str(value.get("schema_version") or "") != EXECUTION_JOURNAL_SCHEMA_VERSION:
            raise ValueError("Unsupported execution journal schema")
        return cls(
            execution_id=str(value.get("execution_id") or ""),
            session_id=str(value.get("session_id") or ""),
            plan_id=str(value.get("plan_id") or ""),
            plan_revision=int(value.get("plan_revision") or 0),
            plan_fingerprint=str(value.get("plan_fingerprint") or ""),
            status=str(value.get("status") or ""),
            started_at=str(value.get("started_at") or ""),
            completed_at=str(value.get("completed_at") or ""),
            result=value.get("result") if isinstance(value.get("result"), Mapping) else {},
        )


class ExecutionJournalStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (
            Path(root)
            if root is not None
            else assistant_storage_root() / "executions"
        )

    def begin(self, record: ExecutionJournalRecord) -> None:
        if record.status != "running":
            raise ValueError("A new execution journal must start in running state")
        if self._path(record.execution_id).exists():
            raise FileExistsError(f"Execution journal already exists: {record.execution_id}")
        self._write(record)

    def finish(
        self,
        execution_id: str,
        *,
        status: str,
        completed_at: str,
        result: Mapping[str, Any],
    ) -> ExecutionJournalRecord:
        current = self.load(execution_id)
        if current.status != "running":
            return current
        terminal = replace(
            current,
            status=status,
            completed_at=completed_at,
            result=dict(result),
        )
        self._write(terminal)
        return terminal

    def load(self, execution_id: str) -> ExecutionJournalRecord:
        path = self._path(execution_id)
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, Mapping):
            raise TypeError("Execution journal root must be an object")
        record = ExecutionJournalRecord.from_dict(payload)
        if record.execution_id != path.stem:
            raise ValueError("Execution journal identity mismatch")
        return record

    def list_records(self) -> tuple[ExecutionJournalRecord, ...]:
        if not self.root.is_dir():
            return ()
        records: list[ExecutionJournalRecord] = []
        for path in self.root.glob("*.json"):
            try:
                records.append(self.load(path.stem))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return tuple(sorted(records, key=lambda item: item.started_at))

    def _write(self, record: ExecutionJournalRecord) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(record.execution_id)
        temporary = path.with_suffix(f".json.{os.getpid()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(record.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _path(self, execution_id: str) -> Path:
        normalized = str(execution_id or "").strip()
        if not _SAFE_ID.fullmatch(normalized):
            raise ValueError("Unsafe execution id")
        return self.root / f"{normalized}.json"


__all__ = [
    "EXECUTION_JOURNAL_SCHEMA_VERSION",
    "ExecutionJournalRecord",
    "ExecutionJournalStore",
]
