"""QWebChannel bridge between the Qt shell and the embedded MarkText view.

The bridge is a plain QObject exposed to the page under the name ``ldword``.
JavaScript calls these slots and, in turn, the page calls back through the
``qt.webChannelTransport`` channel.  This gives two-way, fully-synchronous
communication without any external process or network listener.
"""

from __future__ import annotations

from src.qt_api import QObject, Signal
from PySide6.QtCore import Slot


class MarkTextBridge(QObject):
    """Exposes the assistant's document state to the embedded web view."""

    # Emitted from Python to push state into the page (the view binds these).
    outline_changed = Signal(str)
    content_changed = Signal(str)
    active_chapter_changed = Signal(int)
    chapter_delta = Signal(int, str)
    # (index, markdown) — a chapter's final body (e.g. after inline data-URL
    # images are materialised to relative paths) should replace the live
    # streamed buffer in the page.
    chapter_content_set = Signal(int, str)

    # Emitted when the page asks the shell to do something.
    request_export_docx = Signal(str)
    request_save_markdown = Signal(str)
    request_chapter = Signal(int)
    # Image insertion is handled synchronously inside the slots below; the
    # directory where images are persisted is set by the shell before the
    # editor is used.
    # (index, markdown) — live edits to one chapter pushed back to the cache.
    request_save_chapter = Signal(int, str)
    # (index, markdown) — real-time keystroke sync to the left workbench editor,
    # fired on every Muya change (no debounce, no disk write).
    request_live_edit = Signal(int, str)
    # Local image files dropped onto the editor (paths resolved Qt-side).  Sent
    # as one list so the page can persist + insert them sequentially in the
    # drop order through the same imageAction → requestSaveImage path used by
    # paste/pick.
    images_dropped = Signal(list)

    # ---- 编辑器内 AI 通道 ---------------------------------------------
    # Page → Qt: 右键菜单里的 AI 动作（选区改写/润色/光标处续写）。
    # kind: "rewrite" | "polish" | "continue"；context 为选中文本或空。
    editor_ai_action = Signal(str, str)
    # Qt → Page: AI 操作的阶段状态（了解章节→起草→应用），驱动等待浮层。
    # payload 为 JSON：{"phase": ..., "detail": ..., "kind": ...}
    editor_ai_phase = Signal(str)
    # Qt → Page: AI 完成，payload 为 JSON：
    # {"kind":..., "replacement": 选区替换文本, "insertion": 光标插入文本}
    editor_ai_result = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._outline_json = "[]"
        self._content_markdown = ""
        self._active_chapter = 0
        self._chapters: dict[int, str] = {}
        self._image_dir = ""
        # Lazily-built image manifest (content-hash -> relative path) so bulk
        # insertion never globs the whole ``images/`` directory per file.
        self._image_manifest: dict[str, str] | None = None
        self._image_manifest8: dict[str, str] | None = None
        self._manifest_images_dir: str = ""

    # ---- slots called by the page -----------------------------------------
    @Slot(result=str)
    def getOutline(self) -> str:  # noqa: N802 - QWebChannel JS naming
        return self._outline_json

    @Slot(result=str)
    def getContent(self) -> str:  # noqa: N802 - QWebChannel JS naming
        return self._content_markdown

    @Slot(result=int)
    def getActiveChapter(self) -> int:  # noqa: N802 - QWebChannel JS naming
        return self._active_chapter

    @Slot(int, result=str)
    def getChapterContent(self, index: int) -> str:  # noqa: N802 - QWebChannel JS naming
        return self._chapters.get(int(index or 0), "")

    @Slot(str)
    def requestExportDocx(self, markdown: str) -> None:  # noqa: N802
        self.request_export_docx.emit(str(markdown or ""))

    @Slot(str)
    def requestSaveMarkdown(self, markdown: str) -> None:  # noqa: N802
        self.request_save_markdown.emit(str(markdown or ""))

    @Slot(int)
    def requestChapter(self, index: int) -> None:  # noqa: N802
        self.request_chapter.emit(int(index or 0))

    @Slot(int, str)
    def requestSaveChapter(self, index: int, markdown: str) -> None:  # noqa: N802
        self.request_save_chapter.emit(int(index or 0), str(markdown or ""))

    @Slot(int, str)
    def requestLiveEdit(self, index: int, markdown: str) -> None:  # noqa: N802
        self.request_live_edit.emit(int(index or 0), str(markdown or ""))

    # ---- 编辑器内 AI 通道 ---------------------------------------------
    @Slot(str, str)
    def requestEditorAiAction(self, kind: str, context: str) -> None:  # noqa: N802
        """Page 右键发起的 AI 动作（rewrite/polish/continue）。"""
        self.editor_ai_action.emit(str(kind or ""), str(context or ""))

    def notify_editor_ai_phase(self, payload: dict) -> None:  # noqa: N802
        """Push an AI phase update into the page's waiting overlay."""
        import json

        try:
            text = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError):
            return
        self.editor_ai_phase.emit(text)

    def notify_editor_ai_result(self, payload: dict) -> None:  # noqa: N802
        """Push the finished AI result (replacement/insertion) into the page."""
        import json

        try:
            text = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError):
            return
        self.editor_ai_result.emit(text)

    @Slot(result=str)
    def requestPickImage(self) -> str:  # noqa: N802
        """Open a file dialog, copy the chosen image into the workbench
        directory, and return the markdown-relative path (or '' if cancelled)."""
        from pathlib import Path

        from src.qt_api import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            None,
            "插入图片",
            "",
            "图片 (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg)",
        )
        if not path:
            return ""
        return self._persist_image(path)

    @Slot(str, result=str)
    def requestSaveImage(self, path: str) -> str:  # noqa: N802
        """Copy a pasted/dropped image into the workbench directory and return
        the markdown-relative path (or the original path if copying fails)."""
        if not path:
            return ""
        return self._persist_image(str(path))

    def notifyImagesDropped(self, paths) -> None:  # noqa: N802
        """Emit the dropped local image paths (called Qt-side) as one batch so
        the page inserts them one by one, in the given order."""
        if isinstance(paths, (str, list, tuple)) and not hasattr(paths, "__fspath__"):
            paths = [paths] if isinstance(paths, str) else list(paths)
        cleaned = [str(p) for p in (paths or ()) if str(p or "").strip()]
        if cleaned:
            self.images_dropped.emit(cleaned)

    @Slot(result=str)
    def requestClipboardImagePath(self) -> str:  # noqa: N802
        """Read an image from the clipboard into a temp file and return its
        path so ``imageAction`` can then persist it (or '' if none present)."""
        from pathlib import Path
        from tempfile import mkdtemp

        from PySide6.QtGui import QClipboard, QGuiApplication

        clipboard = QGuiApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            return ""
        tmp_dir = Path(mkdtemp(prefix="ldword_clip_"))
        tmp_path = tmp_dir / "clipboard.png"
        if not image.save(str(tmp_path)):
            return ""
        return str(tmp_path)

    def set_image_directory(self, path: str) -> None:
        """Set the directory where pasted/dropped/picked images are stored.

        The markdown references are written relative to this directory so they
        round-trip through the DOCX exporter's resource resolution.
        """
        changed = str(path or "") != self._image_dir
        self._image_dir = str(path or "")
        if changed:
            # Directory switched: any cached manifest is stale.
            self._image_manifest = None
            self._image_manifest8 = None
            self._manifest_images_dir = ""

    def _ensure_image_manifest(self, images_dir: Path) -> None:
        """Build the in-memory hash -> relative-path index once per directory.

        The manifest maps a 16-hex content hash (and a legacy 8-hex table) to
        the ``images/<file>`` path so dedup is an O(1) dict lookup instead of a
        per-insert glob over the whole directory.
        """
        if (
            self._image_manifest is not None
            and self._manifest_images_dir == str(images_dir)
        ):
            return
        manifest: dict[str, str] = {}
        manifest8: dict[str, str] = {}
        if images_dir.is_dir():
            try:
                for child in images_dir.iterdir():
                    if not child.is_file():
                        continue
                    name = child.name
                    stem = child.stem
                    # ``stem`` may be ``some_name_1a2b...``; the hash is the
                    # trailing hex run after the last underscore.
                    if "_" not in stem:
                        continue
                    _, _, tail = stem.rpartition("_")
                    if len(tail) >= 16 and all(c in "0123456789abcdef" for c in tail):
                        manifest[tail] = "images/" + name
                    elif len(tail) >= 8 and all(c in "0123456789abcdef" for c in tail):
                        manifest8[tail] = "images/" + name
            except OSError:
                pass
        self._image_manifest = manifest
        self._image_manifest8 = manifest8
        self._manifest_images_dir = str(images_dir)

    def _persist_image(self, source: str) -> str:
        """Copy ``source`` into the configured image directory and return a
        markdown-relative path. Falls back to the original path on any error.

        The destination filename embeds 16 hex chars of the file's SHA-256 so
        identical images collapse to one file instead of accruing
        ``_1``/``_2`` copies, while keeping the collision risk negligible even
        with thousands of images.  Files written before this bump (8-hex
        digests) are still matched so nothing is duplicated into an archive.
        """
        from pathlib import Path

        import hashlib
        import shutil

        source_path = Path(source)
        if not source_path.is_file():
            return source
        base = Path(self._image_dir) if getattr(self, "_image_dir", "") else Path.cwd()
        images_dir = base / "images"
        try:
            images_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return source
        suffix = source_path.suffix.casefold() or ".png"
        try:
            digest16 = hashlib.sha256(source_path.read_bytes()).hexdigest()[:16]
        except OSError:
            return source
        digest8 = digest16[:8]
        # Reuse any existing file whose name already embeds this digest — this
        # is the real dedup: identical content maps to one file regardless of
        # the source filename (e.g. two pastes of the same photo).  The
        # manifest makes this an O(1) dict lookup (built once per directory);
        # prefer the full 16-hex match, then fall back to the legacy 8-hex
        # prefix so old files are still reused instead of duplicated.
        self._ensure_image_manifest(images_dir)
        manifest = self._image_manifest or {}
        manifest8 = self._image_manifest8 or {}
        hit = manifest.get(digest16)
        if hit is None:
            hit = manifest8.get(digest8)
        if hit is not None:
            return hit.replace("\\", "/")
        # Keep the filename a sane length: the stem is truncated so stem +
        # 16-hex digest + suffix stays well under the 255-char filesystem cap.
        stem = "".join(ch for ch in source_path.stem if ch.isalnum() or ch in "-_ ")
        stem = stem.strip()[:40] or "image"
        dest = images_dir / f"{stem}_{digest16}{suffix}"
        try:
            shutil.copy2(str(source_path), str(dest))
        except OSError:
            return source
        # Markdown reference is relative to the workbench directory, using
        # forward slashes for portability.
        relative = ("images/" + dest.name).replace("\\", "/")
        # Register the new file so the next insert reuses it without a glob.
        manifest[digest16] = relative
        return relative

    # ---- methods called by the Qt shell -----------------------------------
    def set_outline(self, titles: list[str]) -> None:
        import json

        self._outline_json = json.dumps(
            [{"index": i + 1, "title": str(t or "")} for i, t in enumerate(titles)],
            ensure_ascii=False,
        )
        self.outline_changed.emit(self._outline_json)

    def set_content(self, markdown: str) -> None:
        self._content_markdown = str(markdown or "")
        self.content_changed.emit(self._content_markdown)

    def set_active_chapter(self, index: int) -> None:
        self._active_chapter = max(0, int(index or 0))
        self.active_chapter_changed.emit(self._active_chapter)

    def active_chapter(self) -> int:
        """Return the chapter currently shown in the embedded view (0 = full doc)."""
        return self._active_chapter

    def set_chapter_content(self, index: int, markdown: str) -> None:
        self._chapters[int(index or 0)] = str(markdown or "")

    def set_chapter_content_now(self, index: int, markdown: str) -> None:
        """Update a chapter's cached body *and* push it to the page so the
        live streamed buffer is replaced with the final, image-materialised
        markdown (relative paths instead of raw base64)."""
        idx = int(index or 0)
        self._chapters[idx] = str(markdown or "")
        self.chapter_content_set.emit(idx, str(markdown or ""))

    def set_content_silently(self, markdown: str) -> None:
        """Update the whole-document text without emitting ``content_changed``.

        Used after an in-place chapter edit so the next whole-document preview
        is fresh without re-rendering the live editor mid-edit.
        """
        self._content_markdown = str(markdown or "")

    def set_chapters(self, chapters: dict[int, str]) -> None:
        self._chapters = {int(k): str(v or "") for k, v in (chapters or {}).items()}

    def append_delta(self, index: int, delta: str) -> None:
        """Stream one raw delta for *index* into the live chapter view."""
        self.chapter_delta.emit(int(index or 0), str(delta or ""))

    # Emitted when a chapter run starts so the page can clear its buffer.
    chapter_started = Signal(int)
    # Emitted when a chapter run fails so the page can flag the chapter red
    # while keeping the partial streamed body visible.
    chapter_failed = Signal(int)

    def start_chapter(self, index: int) -> None:
        self.chapter_started.emit(int(index or 0))

    def fail_chapter(self, index: int) -> None:
        self.chapter_failed.emit(int(index or 0))


__all__ = ["MarkTextBridge"]
