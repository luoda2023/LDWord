"""Atomic, versioned local assistant session store."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import hashlib
from datetime import datetime, timezone
from typing import Any

from src.assistant.contracts.serialization import plain_data
from src.assistant.storage.models import AssistantSession, AssistantSessionSummary
from src.assistant.storage.paths import assistant_storage_root


_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class AssistantSessionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else assistant_storage_root()
        self.sessions_dir = self.root / "sessions"

    def list_summaries(self) -> tuple[AssistantSessionSummary, ...]:
        if not self.sessions_dir.is_dir():
            return ()
        summaries: list[AssistantSessionSummary] = []
        for path in self.sessions_dir.glob("*.json"):
            try:
                summaries.append(self._load_path(path).summary())
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                identity = hashlib.sha256(
                    str(path.resolve(strict=False)).encode("utf-8")
                ).hexdigest()[:24]
                try:
                    updated_at = datetime.fromtimestamp(
                        path.stat().st_mtime,
                        tz=timezone.utc,
                    ).isoformat()
                except OSError:
                    updated_at = ""
                summaries.append(
                    AssistantSessionSummary(
                        session_id=f"corrupt_{identity}",
                        title=f"待恢复会话：{path.name}",
                        updated_at=updated_at,
                        turn_status="failed",
                        document_job_status="recovery_required",
                        corrupt=True,
                        recovery_path=str(path.resolve(strict=False)),
                    )
                )
        # Stable two-pass ordering keeps pinned sessions first while preserving
        # newest-first order inside both Design sidebar sections.
        newest_first = sorted(
            summaries,
            key=lambda item: item.updated_at,
            reverse=True,
        )
        return tuple(sorted(newest_first, key=lambda item: not item.pinned))

    def load(self, session_id: str) -> AssistantSession:
        return self._load_path(self._session_path(session_id))

    def save(self, session: AssistantSession) -> None:
        path = self._session_path(session.session_id)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        payload = plain_data(session.to_dict())
        temporary = path.with_suffix(f".json.{os.getpid()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def delete(self, session_id: str) -> bool:
        path = self._session_path(session_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    def _load_path(self, path: Path) -> AssistantSession:
        with path.open("r", encoding="utf-8") as handle:
            payload: Any = json.load(handle)
        if not isinstance(payload, dict):
            raise TypeError("Assistant session file root must be an object")
        session = AssistantSession.from_dict(payload)
        if path.stem != session.session_id:
            raise ValueError("Assistant session file identity mismatch")
        return session

    def _session_path(self, session_id: str) -> Path:
        normalized = str(session_id or "").strip()
        if not _SAFE_SESSION_ID.fullmatch(normalized):
            raise ValueError("Unsafe assistant session id")
        path = self.sessions_dir / f"{normalized}.json"
        resolved_parent = path.parent.resolve(strict=False)
        if resolved_parent != self.sessions_dir.resolve(strict=False):
            raise ValueError("Assistant session path escaped its store")
        return path


__all__ = ["AssistantSessionStore"]
