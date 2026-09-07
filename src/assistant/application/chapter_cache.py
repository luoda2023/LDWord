# -*- coding: utf-8 -*-
"""Large-document chapter cache & progress buffer for the LDWord workbench.

Why this module exists
----------------------
A finished engineering report can reach tens of megabytes of text.  Persisting
that inside a conversation-session JSON (or re-serializing it on every chat
message) makes the UI janky and risks losing work.  This module keeps each
chapter body in its own sidecar text file next to the session store:

* ``<root>/workbench/<session_id>/outline.json``  — outline titles + per-chapter
  states (chars, score, grade, reasons).
* ``<root>/workbench/<session_id>/chapters/0001.txt`` …  — full chapter bodies.

Only small metadata enters the session.  The reader side can memory-map or
slice the chapter files, so even a 几十 MB report stays responsive.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.assistant.application.chapter_document_editor import (
    ChapterScore,
    score_chapter_body,
)
from src.assistant.storage.paths import assistant_storage_root

_LOCK = threading.RLock()

_OUTLINE_SCHEMA = "ldword-workbench-outline-v1"

_IMAGE_SUFFIX_FROM_MIME: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
}


@dataclass(frozen=True, slots=True)
class ChapterCacheEntry:
    index: int
    title: str
    state: str  # pending | running | done | failed
    chars: int = 0
    score: int = 0
    grade: str = "待写"
    reasons: tuple[str, ...] = ()
    file_path: str = ""
    # When a document nests coarse grouping headings (篇/部分/卷/单元) above its
    # content 章, this carries the nearest ancestor grouping title so the left
    # workbench dock can render a collapsible 篇 group.  Empty for flat docs.
    part_title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "state": self.state,
            "chars": self.chars,
            "score": self.score,
            "grade": self.grade,
            "reasons": list(self.reasons),
            "file_path": self.file_path,
            "part_title": self.part_title,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ChapterCacheEntry":
        return cls(
            index=max(0, int(value.get("index", 0))),
            title=str(value.get("title") or ""),
            state=str(value.get("state") or "pending"),
            chars=max(0, int(value.get("chars", 0))),
            score=max(0, min(100, int(value.get("score", 0)))),
            grade=str(value.get("grade") or "待写"),
            reasons=tuple(str(r) for r in (value.get("reasons") or ())),
            file_path=str(value.get("file_path") or ""),
            part_title=str(value.get("part_title") or ""),
        )


class ChapterCacheStore:
    """Sidecar store for full chapter bodies + outline progress metadata."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else assistant_storage_root()
        self.base = self.root / "workbench"

    # ---- layout ---------------------------------------------------------
    def _session_dir(self, session_id: str) -> Path:
        safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")
        if not safe:
            raise ValueError("invalid session id for workbench cache")
        return self.base / safe

    def _chapters_dir(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "chapters"

    def _images_dir(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "images"

    def _outline_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "outline.json"

    # ---- outline --------------------------------------------------------
    def load_outline(self, session_id: str) -> tuple[ChapterCacheEntry, ...]:
        path = self._outline_path(session_id)
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return ()
        entries = raw.get("chapters") if isinstance(raw, dict) else None
        if not isinstance(entries, list):
            return ()
        result: list[ChapterCacheEntry] = []
        for item in entries:
            try:
                result.append(ChapterCacheEntry.from_dict(item))
            except (TypeError, ValueError):
                continue
        return tuple(result)

    def save_outline(
        self,
        session_id: str,
        entries: tuple[ChapterCacheEntry, ...],
    ) -> None:
        directory = self._session_dir(session_id)
        with _LOCK:
            directory.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": _OUTLINE_SCHEMA,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "chapters": [entry.to_dict() for entry in entries],
            }
            tmp = path = self._outline_path(session_id)
            tmp = directory / f"outline.{os.getpid()}.tmp"
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            tmp.replace(path)

    # ---- chapter bodies --------------------------------------------------
    def chapter_path(self, session_id: str, index: int) -> Path:
        return self._chapters_dir(session_id) / f"{int(index):04d}.txt"

    def read_chapter(self, session_id: str, index: int) -> str:
        path = self.chapter_path(session_id, index)
        if not path.is_file():
            return ""
        # Cap single read size defensively; reports can be large but text
        # slicing is cheap because we read whole file only when a chapter is
        # opened in the editor, not on every chat message.
        return path.read_text(encoding="utf-8", errors="replace")

    def append_chapter(
        self,
        session_id: str,
        index: int,
        delta: str,
    ) -> None:
        text = str(delta or "")
        if not text:
            return
        path = self.chapter_path(session_id, index)
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(text)

    def replace_chapter(
        self,
        session_id: str,
        index: int,
        body: str,
    ) -> None:
        path = self.chapter_path(session_id, index)
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(body or ""), encoding="utf-8", newline="")

    # ---- inline image materialisation -------------------------------------
    _DATA_IMAGE_RE = re.compile(
        r"!\[([^\]]*)\]\((data:image/[^)\s]+;base64,[A-Za-z0-9+/=]+)\)"
    )
    _REMOTE_IMAGE_RE = re.compile(
        r"!\[([^\]]*)\]\((https?://[^)\s]+)\)"
    )
    # Download guard: fail fast rather than hang the export on an unreachable
    # host.  A single image may still take longer than this on a slow link, so
    # keep the budget generous but bounded.
    _IMAGE_DOWNLOAD_TIMEOUT_S = 20

    def extract_images(
        self,
        session_id: str,
        markdown: str,
    ) -> tuple[str, dict[str, str]]:
        """Materialise inline images into files under the session's ``images/``
        directory and rewrite the markdown to reference them by relative path.

        Two sources are supported side-by-side: ``data:image/...;base64`` data
        URLs (decoded in-process) and remote ``http(s)://`` URLs (downloaded and
        saved locally).  A source that cannot be decoded or downloaded is left
        untouched rather than silently dropped.

        Returns ``(rewritten_markdown, resource_paths)`` where
        ``resource_paths`` maps each relative path to the absolute file path,
        ready to pass straight into the DOCX exporter's ``resource_paths``.
        """

        source = str(markdown or "")
        if not source:
            return source, {}
        images_dir = self._images_dir(session_id)
        resource_paths: dict[str, str] = {}

        def _land(raw: bytes, alt: str, suffix: str) -> str | None:
            """Write ``raw`` bytes under ``images/`` (content-hash dedup) and
            return the markdown-relative path, or ``None`` on failure."""
            digest = hashlib.sha256(raw).hexdigest()[:16]
            stem = alt.strip()[:24] if alt.strip() else "image"
            stem = "".join(
                ch for ch in stem if ch.isalnum() or ch in "-_"
            ) or "image"
            filename = f"{stem}_{digest}{suffix}"
            dest = images_dir / filename
            try:
                images_dir.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    dest.write_bytes(raw)
            except OSError:
                return None
            relative = f"images/{filename}"
            resource_paths[relative] = str(dest)
            return relative

        def _materialise_data(match: re.Match[str]) -> str:
            alt = match.group(1) or ""
            data_url = match.group(2)
            try:
                header, _, payload = data_url.partition(",")
                mime = header.split(";")[0].removeprefix("data:") or "image/png"
                raw = base64.b64decode(payload, validate=True)
            except (binascii.Error, ValueError):
                return match.group(0)
            suffix = _IMAGE_SUFFIX_FROM_MIME.get(mime, ".png")
            relative = _land(raw, alt, suffix)
            return f"![{alt}]({relative})" if relative else match.group(0)

        def _materialise_remote(match: re.Match[str]) -> str:
            alt = match.group(1) or ""
            url = match.group(2)
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "LDWord/1.0 image-materialiser"},
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self._IMAGE_DOWNLOAD_TIMEOUT_S
                ) as response:
                    raw = response.read()
                    content_type = (
                        response.headers.get("Content-Type", "") or ""
                    ).split(";")[0].strip().lower()
            except (OSError, ValueError):
                # Unreachable / timeout / bad URL — keep the remote reference.
                return match.group(0)
            suffix = _IMAGE_SUFFIX_FROM_MIME.get(
                content_type,
                Path(url.split("?")[0]).suffix.casefold() or ".png",
            )
            if suffix not in _IMAGE_SUFFIX_FROM_MIME.values():
                suffix = ".png"
            relative = _land(raw, alt, suffix)
            return f"![{alt}]({relative})" if relative else match.group(0)

        rewritten = self._DATA_IMAGE_RE.sub(_materialise_data, source)
        rewritten = self._REMOTE_IMAGE_RE.sub(_materialise_remote, rewritten)
        return rewritten, resource_paths

    def session_resource_paths(self, session_id: str) -> dict[str, str]:
        """Return the accumulated image mapping for a session (relative path
        -> absolute file), rebuilt by scanning the session's ``images`` dir."""

        images_dir = self._images_dir(session_id)
        if not images_dir.is_dir():
            return {}
        result: dict[str, str] = {}
        try:
            for child in images_dir.iterdir():
                if child.is_file():
                    result[f"images/{child.name}"] = str(child)
        except OSError:
            return {}
        return result

    def chapter_chars(self, session_id: str, index: int) -> int:
        path = self.chapter_path(session_id, index)
        if not path.is_file():
            return 0
        try:
            return path.stat().st_size
        except OSError:
            return 0

    def score_chapter(self, session_id: str, index: int) -> ChapterScore:
        body = self.read_chapter(session_id, index)
        return score_chapter_body(body)

    # ---- convenience helpers --------------------------------------------
    def begin_run(
        self,
        session_id: str,
        titles: list[str],
        parts: list[str] | None = None,
    ) -> tuple[ChapterCacheEntry, ...]:
        """Reset the cache for a new outline run and return fresh entries.

        ``parts`` is an optional list aligned with ``titles`` carrying each
        chapter's ancestor grouping (篇/部分/卷/单元) title, or ``""`` for a
        top-level chapter.  Flat documents pass ``None``/empty.
        """
        entries: list[ChapterCacheEntry] = []
        for i, title in enumerate(titles, start=1):
            path = self.chapter_path(session_id, i)
            try:
                if path.is_file():
                    path.unlink()
            except OSError:
                pass
            part = ""
            if parts:
                part = str(parts[i - 1]) if i - 1 < len(parts) else ""
            entries.append(
                ChapterCacheEntry(
                    index=i,
                    title=str(title),
                    state="pending",
                    part_title=part,
                )
            )
        self.save_outline(session_id, tuple(entries))
        return tuple(entries)

    def ensure_chapter(
        self,
        session_id: str,
        index: int,
        title: str = "",
    ) -> ChapterCacheEntry:
        """Return an outline row for *index*, creating it when missing."""
        entries = list(self.load_outline(session_id))
        match = next((e for e in entries if e.index == int(index)), None)
        if match is not None:
            return match
        entry = ChapterCacheEntry(
            index=int(index),
            title=str(title or f"第 {int(index)} 章"),
            state="pending",
        )
        entries.append(entry)
        entries.sort(key=lambda e: e.index)
        self.save_outline(session_id, tuple(entries))
        return entry

    def update_state(
        self,
        session_id: str,
        index: int,
        state: str | None = None,
        *,
        chars: int | None = None,
        rescan_score: bool = False,
    ) -> ChapterCacheEntry | None:
        from dataclasses import replace

        entries = list(self.load_outline(session_id))
        if not entries:
            return None
        match = next((e for e in entries if e.index == int(index)), None)
        if match is None:
            return None
        position = entries.index(match)
        new = match
        if state is not None:
            new = replace(new, state=str(state))
        if chars is not None:
            new = replace(new, chars=max(0, int(chars)))
        if rescan_score:
            scored = self.score_chapter(session_id, new.index)
            new = replace(
                new,
                chars=new.chars or scored.chars,
                score=scored.score,
                grade=scored.grade,
                reasons=scored.reasons,
                file_path=str(self.chapter_path(session_id, new.index)),
            )
        entries[position] = new
        self.save_outline(session_id, tuple(entries))
        return new


__all__ = [
    "ChapterCacheEntry",
    "ChapterCacheStore",
]
