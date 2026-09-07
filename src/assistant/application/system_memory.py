# -*- coding: utf-8 -*-
"""Persistent "system memory" for long-document authoring.

Why this module exists
----------------------
A finished engineering report can span hundreds of pages.  When the AI writes
one chapter per request, its per-request context window cannot hold every
earlier chapter verbatim.  This module keeps a compact, durable memory file per
session so that later chapters (and later revision passes) can recall what was
already written — the outline, per-chapter summaries, key terms and any global
decisions — without re-reading the full bodies.

Layout
------
By default ``system_memory.json`` lives next to the chapter cache's
``outline.json`` in the app-internal workbench session directory
(``<assistant_storage_root()>/workbench/<session_id>/system_memory.json``).  The
user may opt (via the shared storage-location preference) to keep it next to
their current project / source document instead — ``SystemMemoryStore`` accepts
an explicit ``base_dir`` pointing at that folder, which places the file at
``<folder>/system_memory.json`` so it travels with the document.  Only small
summaries enter this file; full bodies stay in the chapter cache's sidecar
files.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.assistant.storage.paths import assistant_storage_root

_LOCK = threading.RLock()

_SCHEMA = "ldword-system-memory-v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ChapterMemoryEntry:
    """Compact memory of one finished chapter."""

    index: int
    title: str
    summary: str = ""
    key_terms: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "summary": self.summary,
            "key_terms": list(self.key_terms),
            "facts": list(self.facts),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ChapterMemoryEntry":
        return cls(
            index=max(0, int(value.get("index", 0))),
            title=str(value.get("title") or ""),
            summary=str(value.get("summary") or ""),
            key_terms=tuple(str(t) for t in (value.get("key_terms") or ())),
            facts=tuple(str(f) for f in (value.get("facts") or ())),
        )


@dataclass
class SystemMemory:
    """Durable, cross-chapter memory for one authored document."""

    session_id: str = ""
    project_brief: str = ""
    outline: tuple[str, ...] = ()
    chapters: tuple[ChapterMemoryEntry, ...] = ()
    decisions: tuple[str, ...] = ()
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA,
            "session_id": self.session_id,
            "project_brief": self.project_brief,
            "outline": list(self.outline),
            "chapters": [asdict(c) for c in self.chapters],
            "decisions": list(self.decisions),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SystemMemory":
        return cls(
            session_id=str(value.get("session_id") or ""),
            project_brief=str(value.get("project_brief") or ""),
            outline=tuple(str(t) for t in (value.get("outline") or ())),
            chapters=tuple(
                ChapterMemoryEntry.from_dict(c) for c in (value.get("chapters") or ())
            ),
            decisions=tuple(str(d) for d in (value.get("decisions") or ())),
            updated_at=str(value.get("updated_at") or ""),
        )

    def chapter_by_index(self, index: int) -> ChapterMemoryEntry | None:
        for chapter in self.chapters:
            if chapter.index == index:
                return chapter
        return None


class SystemMemoryStore:
    """Read/write the per-session system memory file.

    The memory lives in either of two homes, controlled by the shared
    storage-location preference:

    * ``base_dir`` is set  -> the file is ``<base_dir>/system_memory.json``
      (user chose to keep memory next to their project / source document).
    * ``base_dir`` is unset -> app-internal layout
      ``<assistant_storage_root()>/workbench/<session_id>/system_memory.json``
      alongside the chapter cache (default).
    """

    def __init__(
        self,
        root: Path | None = None,
        *,
        base_dir: Path | str | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else assistant_storage_root()
        self.base = self.root / "workbench"
        self.base_dir = Path(base_dir) if base_dir is not None else None

    def _path(self, session_id: str) -> Path:
        if self.base_dir is not None:
            # One memory file per project/source-document folder.  The session id
            # is recorded in the payload but not in the path, so different
            # sessions editing the same project share the durable memory.
            return self.base_dir / "system_memory.json"
        safe = "".join(
            ch for ch in str(session_id) if ch.isalnum() or ch in "-_"
        )
        if not safe:
            raise ValueError("invalid session id for system memory")
        return self.base / safe / "system_memory.json"

    def load(self, session_id: str) -> SystemMemory:
        """Return the stored memory, or an empty one when none exists yet."""
        path = self._path(session_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return SystemMemory.from_dict(raw)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return SystemMemory(session_id=str(session_id or ""))

    def save(self, memory: SystemMemory) -> SystemMemory:
        """Persist ``memory`` (atomic write, timestamped)."""
        memory.updated_at = _now_iso()
        data = memory.to_dict()
        path = self._path(memory.session_id)
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            tmp.replace(path)
        return memory

    def update_chapter(
        self,
        session_id: str,
        *,
        index: int,
        title: str,
        summary: str,
        key_terms: tuple[str, ...] = (),
        facts: tuple[str, ...] = (),
    ) -> SystemMemory:
        """Insert/replace one chapter's memory entry and persist."""
        memory = self.load(session_id)
        memory.session_id = str(session_id or "")
        entry = ChapterMemoryEntry(
            index=max(0, int(index)),
            title=str(title or ""),
            summary=str(summary or ""),
            key_terms=tuple(key_terms or ()),
            facts=tuple(facts or ()),
        )
        chapters = [c for c in memory.chapters if c.index != entry.index]
        chapters.append(entry)
        chapters.sort(key=lambda c: c.index)
        memory.chapters = tuple(chapters)
        return self.save(memory)

    def set_outline(self, session_id: str, titles: tuple[str, ...]) -> SystemMemory:
        memory = self.load(session_id)
        memory.session_id = str(session_id or "")
        memory.outline = tuple(str(t or "") for t in (titles or ()))
        return self.save(memory)

    def set_project_brief(self, session_id: str, brief: str) -> SystemMemory:
        memory = self.load(session_id)
        memory.session_id = str(session_id or "")
        memory.project_brief = str(brief or "")
        return self.save(memory)

    def migrate_to_dir(self, session_id: str, base_dir: Path | str) -> bool:
        """Copy an existing app-internal memory file next to a source document.

        Used when the user switches the storage location to ``project`` (or a
        project folder becomes available): copying the internal file keeps the
        authoring-to-editing continuity so rewrite passes that now read
        ``<base_dir>/system_memory.json`` still see what generation wrote.  The
        source file is left untouched so nothing is ever lost.  Returns True
        when a file was actually copied.
        """
        if self.base_dir is not None:
            return False
        source = self._path(session_id)
        if not source.is_file():
            return False
        destination = Path(base_dir) / "system_memory.json"
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            return True
        except OSError:
            return False


def system_memory_path(
    *,
    base_dir: Path | str | None = None,
    root: Path | None = None,
    session_id: str = "",
) -> Path:
    """Resolve the file path a ``SystemMemoryStore`` would use for *session_id*.

    Convenience for callers that need to know where the memory file lives (e.g.
    to copy it when the storage location changes / a document folder becomes
    available) without constructing a store.
    """
    store = SystemMemoryStore(root, base_dir=base_dir)
    return store._path(session_id)


def memory_summary_text(memory: SystemMemory) -> str:
    """Render the stored memory into a prompt fragment for the next chapter.

    Returns ``""`` when there is nothing worth reminding the model about, so
    callers can simply append the result (or skip it).
    """
    parts: list[str] = []
    if memory.project_brief.strip():
        parts.append("项目背景：" + memory.project_brief.strip())
    if memory.decisions:
        parts.append("已确定的关键口径：" + "；".join(memory.decisions))
    for chapter in memory.chapters:
        line = f"第 {chapter.index} 章《{chapter.title}》已覆盖：{chapter.summary}"
        parts.append(line)
    if not parts:
        return ""
    return "\n".join(parts)


__all__ = [
    "ChapterMemoryEntry",
    "SystemMemory",
    "SystemMemoryStore",
    "memory_summary_text",
    "system_memory_path",
]
