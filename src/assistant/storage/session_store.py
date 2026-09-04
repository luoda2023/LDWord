"""Atomic, versioned local assistant session store."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.assistant.contracts.serialization import plain_data
from src.assistant.storage.models import AssistantSession, AssistantSessionSummary
from src.assistant.storage.paths import assistant_storage_root

_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SIDEBAR_STATE_SCHEMA = "assistant-sidebar-state-v1"
_SUMMARY_CACHE_SCHEMA = "assistant-summary-cache-v1"


class AssistantSessionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else assistant_storage_root()
        self.sessions_dir = self.root / "sessions"
        self.summaries_dir = self.root / "summaries"
        self.sidebar_state_path = self.root / "sidebar-state.json"

    def list_summaries(self) -> tuple[AssistantSessionSummary, ...]:
        if not self.sessions_dir.is_dir():
            return ()
        sidebar_layout = self._load_sidebar_layout()
        summaries: list[AssistantSessionSummary] = []
        for path in self.sessions_dir.glob("*.json"):
            try:
                summary = self._load_cached_summary(path)
                if summary is None:
                    summary = self._load_path(path).summary()
                    self._try_write_summary_cache(path, summary)
                summaries.append(
                    _apply_sidebar_summary(
                        summary,
                        sidebar_layout.get(summary.session_id),
                    )
                )
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
                        activity_at=updated_at,
                    )
                )
        return (
            *_ordered_summary_group(
                item for item in summaries if item.pinned
            ),
            *_ordered_summary_group(
                item for item in summaries if not item.pinned
            ),
        )

    def load(self, session_id: str) -> AssistantSession:
        session = self._load_path(self._session_path(session_id))
        return _apply_sidebar_session(
            session,
            self._load_sidebar_layout().get(session.session_id),
        )

    def save(
        self,
        session: AssistantSession,
        *,
        update_summary_cache: bool = True,
    ) -> None:
        path = self._session_path(session.session_id)
        payload = plain_data(session.to_dict())
        self._atomic_write_json(path, payload)
        if update_summary_cache:
            self._try_write_summary_cache(path, session.summary())

    def save_sidebar_layout(
        self,
        entries: Mapping[str, tuple[bool, int | None]],
    ) -> None:
        normalized: dict[str, dict[str, object]] = {}
        for session_id, state in entries.items():
            normalized_id = str(session_id or "").strip()
            if not _SAFE_SESSION_ID.fullmatch(normalized_id):
                raise ValueError("Unsafe assistant session id in sidebar layout")
            pinned, order = state
            normalized_order = _optional_nonnegative_int(order)
            if order is not None and normalized_order is None:
                raise ValueError("Assistant sidebar order must be non-negative")
            normalized[normalized_id] = {
                "pinned": bool(pinned),
                "order": normalized_order,
            }
        self._atomic_write_json(
            self.sidebar_state_path,
            {
                "schema_version": _SIDEBAR_STATE_SCHEMA,
                "entries": normalized,
            },
        )

    def _atomic_write_json(
        self,
        path: Path,
        payload: object,
        *,
        durable: bool = True,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(
            f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp"
        )
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                if durable:
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
        try:
            self._summary_path(path).unlink(missing_ok=True)
        except OSError:
            pass
        self._try_forget_sidebar_entry(session_id)
        return True

    def quarantine_corrupt(self, recovery_path: str) -> Path:
        """Move one corrupt session JSON out of the live session directory."""

        sessions_root = self.sessions_dir.resolve(strict=False)
        target = Path(str(recovery_path or "")).resolve(strict=False)
        if target.parent != sessions_root or target.suffix.lower() != ".json":
            raise ValueError("Unsafe corrupt assistant session path")
        if not target.is_file():
            raise FileNotFoundError(target)
        quarantine_dir = self.root / "recovery"
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = quarantine_dir / f"{target.stem}.{timestamp}.json"
        os.replace(target, destination)
        try:
            self._summary_path(target).unlink(missing_ok=True)
        except OSError:
            pass
        self._try_forget_sidebar_entry(target.stem)
        return destination

    def _load_cached_summary(
        self,
        session_path: Path,
    ) -> AssistantSessionSummary | None:
        cache_path = self._summary_path(session_path)
        try:
            source_stat = session_path.stat()
            with cache_path.open("r", encoding="utf-8") as handle:
                payload: Any = json.load(handle)
            if not isinstance(payload, Mapping):
                return None
            if str(payload.get("schema_version") or "") != _SUMMARY_CACHE_SCHEMA:
                return None
            if int(payload.get("source_mtime_ns") or -1) != source_stat.st_mtime_ns:
                return None
            if int(payload.get("source_size") or -1) != source_stat.st_size:
                return None
            raw_summary = payload.get("summary")
            if not isinstance(raw_summary, Mapping):
                return None
            summary = AssistantSessionSummary.from_dict(raw_summary)
            if summary.session_id != session_path.stem or summary.corrupt:
                return None
            return summary
        except (
            OSError,
            TypeError,
            ValueError,
            OverflowError,
            json.JSONDecodeError,
        ):
            return None

    def _try_write_summary_cache(
        self,
        session_path: Path,
        summary: AssistantSessionSummary,
    ) -> None:
        try:
            source_stat = session_path.stat()
            self._atomic_write_json(
                self._summary_path(session_path),
                {
                    "schema_version": _SUMMARY_CACHE_SCHEMA,
                    "source_mtime_ns": source_stat.st_mtime_ns,
                    "source_size": source_stat.st_size,
                    "summary": plain_data(summary.to_dict()),
                },
                durable=False,
            )
        except (OSError, TypeError, ValueError):
            try:
                self._summary_path(session_path).unlink(missing_ok=True)
            except OSError:
                pass

    def _summary_path(self, session_path: Path) -> Path:
        return self.summaries_dir / session_path.name

    def _load_sidebar_layout(self) -> dict[str, tuple[bool, int | None]]:
        try:
            with self.sidebar_state_path.open("r", encoding="utf-8") as handle:
                payload: Any = json.load(handle)
        except (
            FileNotFoundError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return {}
        if (
            not isinstance(payload, Mapping)
            or str(payload.get("schema_version") or "") != _SIDEBAR_STATE_SCHEMA
        ):
            return {}
        raw_entries = payload.get("entries")
        if not isinstance(raw_entries, Mapping):
            return {}
        entries: dict[str, tuple[bool, int | None]] = {}
        for session_id, raw_state in raw_entries.items():
            normalized_id = str(session_id or "").strip()
            if (
                not _SAFE_SESSION_ID.fullmatch(normalized_id)
                or not isinstance(raw_state, Mapping)
            ):
                continue
            entries[normalized_id] = (
                bool(raw_state.get("pinned", False)),
                _optional_nonnegative_int(raw_state.get("order")),
            )
        return entries

    def _try_forget_sidebar_entry(self, session_id: str) -> None:
        layout = self._load_sidebar_layout()
        if session_id not in layout:
            return
        layout.pop(session_id, None)
        try:
            self.save_sidebar_layout(layout)
        except (OSError, TypeError, ValueError):
            pass

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


def _ordered_summary_group(
    summaries: Iterable[AssistantSessionSummary],
) -> tuple[AssistantSessionSummary, ...]:
    values = tuple(summaries)
    unranked = sorted(
        (item for item in values if item.sidebar_order is None),
        key=lambda item: item.activity_at or item.updated_at,
        reverse=True,
    )
    ranked = sorted(
        (item for item in values if item.sidebar_order is not None),
        key=lambda item: int(item.sidebar_order or 0),
    )
    return (*unranked, *ranked)


def _apply_sidebar_summary(
    summary: AssistantSessionSummary,
    state: tuple[bool, int | None] | None,
) -> AssistantSessionSummary:
    if state is None:
        return summary
    pinned, order = state
    return replace(summary, pinned=pinned, sidebar_order=order)


def _apply_sidebar_session(
    session: AssistantSession,
    state: tuple[bool, int | None] | None,
) -> AssistantSession:
    if state is None:
        return session
    pinned, order = state
    return replace(session, pinned=pinned, sidebar_order=order)


def _optional_nonnegative_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return normalized if normalized >= 0 else None


__all__ = ["AssistantSessionStore"]
