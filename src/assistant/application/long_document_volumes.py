# -*- coding: utf-8 -*-
"""超长文档的篇/卷规划与磁盘检查点。

长文档不把所有正文塞进一个 JSON：
``<workbench>/<session>/long_document/volumes/volume-001/chapters/0001.md``
保存已完成章节，manifest 只保存规划、状态和路径。进程中断后，下一次
使用同一 session、需求和目录重新生成时会跳过已完成章节，从中断处继续。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.assistant.application.length_targeting import CHARS_PER_PAGE
from src.assistant.storage.paths import assistant_storage_root

_SCHEMA = "ldword-long-document-checkpoint-v1"
_SAFE_ID = re.compile(r"[^0-9A-Za-z_-]+")
DEFAULT_VOLUME_PAGES = 100


def _safe_id(value: str) -> str:
    result = _SAFE_ID.sub("_", str(value or "")).strip("_")
    return result or "session"


def request_fingerprint(
    prompt: str,
    outline_titles: tuple[str, ...] | list[str],
    *,
    volume_pages: int = DEFAULT_VOLUME_PAGES,
) -> str:
    payload = {
        "prompt": str(prompt or "").strip(),
        "outline": [str(title or "").strip() for title in outline_titles],
        "volume_pages": max(1, int(volume_pages or DEFAULT_VOLUME_PAGES)),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class VolumePlan:
    """连续的一组章节；章节不会被拆到两个卷。"""

    index: int
    chapter_indices: tuple[int, ...]
    chapter_titles: tuple[str, ...]
    target_chars: int

    @property
    def label(self) -> str:
        return f"第{self.index}卷"


def plan_volumes(
    outline_titles: tuple[str, ...] | list[str],
    total_chars: int,
    *,
    volume_pages: int = DEFAULT_VOLUME_PAGES,
) -> tuple[VolumePlan, ...]:
    """按目标篇幅把连续章节划分为多个卷。

    ``volume_pages`` 是每卷目标页数，默认 100 页。没有明确总篇幅时不
    猜测文档规模，返回一个卷；明确 1000 页时通常得到约 10 个卷。
    每卷按章节边界切分，最后一章即使超过容量也不会被硬拆。
    """
    titles = tuple(str(title).strip() for title in outline_titles if str(title).strip())
    if not titles:
        return ()
    capacity = max(1, int(volume_pages or DEFAULT_VOLUME_PAGES)) * CHARS_PER_PAGE
    total = max(0, int(total_chars or 0))
    if total <= capacity:
        return (VolumePlan(1, tuple(range(1, len(titles) + 1)), titles, total),)

    chapter_budget = total / len(titles)
    plans: list[VolumePlan] = []
    current_indices: list[int] = []
    current_titles: list[str] = []
    current_target = 0
    for index, title in enumerate(titles, start=1):
        estimate = max(1, int(round(chapter_budget)))
        if current_indices and current_target + estimate > capacity:
            plans.append(
                VolumePlan(
                    len(plans) + 1,
                    tuple(current_indices),
                    tuple(current_titles),
                    current_target,
                )
            )
            current_indices = []
            current_titles = []
            current_target = 0
        current_indices.append(index)
        current_titles.append(title)
        current_target += estimate
    if current_indices:
        plans.append(
            VolumePlan(
                len(plans) + 1,
                tuple(current_indices),
                tuple(current_titles),
                current_target,
            )
        )
    return tuple(plans)


class LongDocumentCheckpointStore:
    """保存卷/章完成状态与正文，支持中断后的安全恢复。"""

    def __init__(self, session_id: str, *, root: Path | None = None) -> None:
        base = Path(root) if root is not None else assistant_storage_root()
        self.root = base / "workbench" / _safe_id(session_id) / "long_document"
        self.manifest_path = self.root / "manifest.json"

    def initialize(
        self,
        *,
        session_id: str,
        prompt: str,
        outline_titles: tuple[str, ...],
        total_chars: int,
        volume_pages: int,
    ) -> dict[str, Any]:
        """加载同一任务的 manifest，否则创建新的卷目录。"""
        fingerprint = request_fingerprint(
            prompt, outline_titles, volume_pages=volume_pages
        )
        current = self.load()
        if (
            current
            and current.get("fingerprint") == fingerprint
            and tuple(current.get("outline_titles") or ()) == tuple(outline_titles)
        ):
            return current

        plans = plan_volumes(
            outline_titles, total_chars, volume_pages=volume_pages
        )
        manifest: dict[str, Any] = {
            "schema_version": _SCHEMA,
            "session_id": str(session_id or ""),
            "fingerprint": fingerprint,
            "outline_titles": list(outline_titles),
            "total_chars": int(total_chars or 0),
            "volume_pages": max(1, int(volume_pages or DEFAULT_VOLUME_PAGES)),
            "status": "pending",
            "volumes": [
                {
                    "index": plan.index,
                    "label": plan.label,
                    "chapter_indices": list(plan.chapter_indices),
                    "chapter_titles": list(plan.chapter_titles),
                    "target_chars": plan.target_chars,
                    "status": "pending",
                    "chapters": [],
                }
                for plan in plans
            ],
        }
        self._write(manifest)
        return manifest

    def load(self) -> dict[str, Any] | None:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def set_status(self, status: str) -> None:
        manifest = self.load()
        if manifest is None:
            return
        manifest["status"] = str(status or "pending")
        self._write(manifest)

    def chapter_markdown(self, chapter_index: int) -> str | None:
        manifest = self.load()
        item = self._chapter_item(manifest, chapter_index)
        if not item or item.get("status") != "completed":
            return None
        path = self.root / str(item.get("path") or "")
        try:
            return path.read_text(encoding="utf-8") if path.is_file() else None
        except OSError:
            return None

    def save_chapter(
        self,
        *,
        volume_index: int,
        chapter_index: int,
        title: str,
        markdown: str,
    ) -> None:
        manifest = self.load()
        if manifest is None:
            return
        volume_dir = self.root / "volumes" / f"volume-{volume_index:03d}" / "chapters"
        volume_dir.mkdir(parents=True, exist_ok=True)
        relative = Path("volumes") / f"volume-{volume_index:03d}" / "chapters" / f"{chapter_index:04d}.md"
        path = self.root / relative
        path.write_text(str(markdown or ""), encoding="utf-8")
        volume = self._volume_item(manifest, volume_index)
        if volume is None:
            return
        chapters = [
            item for item in (volume.get("chapters") or ())
            if int(item.get("index", -1)) != chapter_index
        ]
        chapters.append(
            {
                "index": chapter_index,
                "title": str(title or ""),
                "status": "completed",
                "path": str(relative).replace("\\", "/"),
                "chars": len(str(markdown or "")),
            }
        )
        chapters.sort(key=lambda item: int(item.get("index", 0)))
        volume["chapters"] = chapters
        expected = set(int(i) for i in (volume.get("chapter_indices") or ()))
        actual = {int(item.get("index", -1)) for item in chapters if item.get("status") == "completed"}
        volume["status"] = "completed" if expected and expected <= actual else "running"
        manifest["status"] = "running"
        self._write(manifest)

    def finalize(self) -> None:
        manifest = self.load()
        if manifest is None:
            return
        all_complete = True
        for volume in manifest.get("volumes") or ():
            if volume.get("status") != "completed":
                all_complete = False
                continue
            volume_dir = self.root / "volumes" / f"volume-{int(volume.get('index', 0)):03d}"
            parts: list[str] = []
            for chapter in sorted(volume.get("chapters") or (), key=lambda x: int(x.get("index", 0))):
                path = self.root / str(chapter.get("path") or "")
                if path.is_file():
                    parts.append(path.read_text(encoding="utf-8").strip())
            (volume_dir / "volume.md").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
        manifest["status"] = "completed" if all_complete else "running"
        self._write(manifest)

    def _volume_item(self, manifest: dict[str, Any] | None, index: int) -> dict[str, Any] | None:
        if not manifest:
            return None
        for volume in manifest.get("volumes") or ():
            if int(volume.get("index", -1)) == int(index):
                return volume
        return None

    def _chapter_item(self, manifest: dict[str, Any] | None, chapter_index: int) -> dict[str, Any] | None:
        if not manifest:
            return None
        for volume in manifest.get("volumes") or ():
            for chapter in volume.get("chapters") or ():
                if int(chapter.get("index", -1)) == int(chapter_index):
                    return chapter
        return None

    def _write(self, manifest: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.manifest_path)


__all__ = [
    "DEFAULT_VOLUME_PAGES",
    "LongDocumentCheckpointStore",
    "VolumePlan",
    "plan_volumes",
    "request_fingerprint",
]
