"""One-shot durable continuations for questions and permission waits."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any

from src.assistant.contracts.serialization import plain_data
from src.assistant.storage.paths import assistant_storage_root


CONTINUATION_SCHEMA_VERSION = "form-assistant-continuation-v1"
CONTINUATION_KINDS = frozenset({"user_question", "data_permission", "tool_permission"})
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


@dataclass(frozen=True, slots=True)
class ContinuationRecord:
    continuation_id: str
    session_id: str
    turn_id: str
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.kind not in CONTINUATION_KINDS:
            raise ValueError(f"Unsupported continuation kind: {self.kind!r}")
        for name in ("continuation_id", "session_id", "turn_id"):
            if not _SAFE_ID.fullmatch(str(getattr(self, name) or "")):
                raise ValueError(f"Unsafe continuation identity: {name}")
        object.__setattr__(self, "payload", dict(plain_data(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CONTINUATION_SCHEMA_VERSION,
            "contract_kind": "assistant_continuation",
            "continuation_id": self.continuation_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "kind": self.kind,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ContinuationRecord":
        if str(value.get("schema_version") or "") != CONTINUATION_SCHEMA_VERSION:
            raise ValueError("Unsupported assistant continuation schema")
        return cls(
            continuation_id=str(value.get("continuation_id") or ""),
            session_id=str(value.get("session_id") or ""),
            turn_id=str(value.get("turn_id") or ""),
            kind=str(value.get("kind") or ""),
            payload=value.get("payload") if isinstance(value.get("payload"), Mapping) else {},
            created_at=str(value.get("created_at") or ""),
        )


class ContinuationStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else assistant_storage_root() / "continuations"

    def save(self, record: ContinuationRecord) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(record.continuation_id)
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

    def load(self, continuation_id: str) -> ContinuationRecord:
        path = self._path(continuation_id)
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, Mapping):
            raise TypeError("Continuation root must be an object")
        record = ContinuationRecord.from_dict(payload)
        if record.continuation_id != path.stem:
            raise ValueError("Continuation identity mismatch")
        return record

    def consume(self, continuation_id: str) -> ContinuationRecord:
        record = self.load(continuation_id)
        self._path(continuation_id).unlink()
        return record

    def list_pending(self) -> tuple[ContinuationRecord, ...]:
        if not self.root.is_dir():
            return ()
        records: list[ContinuationRecord] = []
        for path in self.root.glob("*.json"):
            try:
                records.append(self.load(path.stem))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return tuple(sorted(records, key=lambda item: item.created_at))

    def _path(self, continuation_id: str) -> Path:
        normalized = str(continuation_id or "").strip()
        if not _SAFE_ID.fullmatch(normalized):
            raise ValueError("Unsafe continuation id")
        return self.root / f"{normalized}.json"


__all__ = [
    "CONTINUATION_KINDS",
    "CONTINUATION_SCHEMA_VERSION",
    "ContinuationRecord",
    "ContinuationStore",
]
