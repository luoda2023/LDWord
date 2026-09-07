# -*- coding: utf-8 -*-
"""Document-workbench wiring mixin for the assistant panel.

The workbench is the *editor view* over an engineering long-document run.  It
replaces the chat-only presentation with a Word-like editor when the user (or
the AI after an outline run) asks to see / keep editing the assembled report.

Responsibilities (delegated from the panel):
* create / show / hide the :class:`ChapterWorkbench` overlay on the active
  conversation page;
* keep the left navigator in sync with the :class:`ChapterCacheStore`
  (per-chapter state, chars, score, grade);
* on chapter navigation, load that chapter's body from the cache into the
  editor (structured: heading1/heading2/body blocks);
* expose an append API so the chapter-authoring flow can *stream* deltas into
  the visible editor as they arrive (文字/回车/缩进即时可见), while the cache
  append already happens on the worker thread;
* save: export the current editor plain text into a fresh ``.revised.docx``.
"""
from __future__ import annotations

from pathlib import Path

from src.assistant.application.chapter_cache import ChapterCacheStore
from src.assistant.ui.chapter_workbench import ChapterWorkbench
from src.qt_api import QFileDialog, Qt

_BODY = 0
_H1 = 1
_H2 = 2
_IMAGE = 4


class AssistantChapterWorkbenchMixin:
    """Mixin expected to be used *before* other UI mixins in the MRO."""

    # ---- lifecycle -------------------------------------------------------
    def _ensure_workbench(self) -> ChapterWorkbench | None:
        page = getattr(self, "_active_page", None)
        if page is None:
            return None
        bench = getattr(self, "_chapter_workbench", None)
        if bench is None or bench.parentWidget() is not page:
            if bench is not None:
                bench.deleteLater()
            bench = ChapterWorkbench(page)
            bench.closed.connect(self._hide_workbench)
            bench.save_requested.connect(self._workbench_save)
            bench.edited.connect(self._on_workbench_edited)
            bench.chapter_navigated.connect(self._on_workbench_navigate)
            self._chapter_workbench = bench
        return bench

    def _show_workbench(self) -> None:
        bench = self._ensure_workbench()
        if bench is None:
            return
        bench.show()
        bench.raise_()
        # When the persistent outline dock is present it is the single left
        # chapter index; drop the workbench's own navigator and fuse layout.
        dock = getattr(self, "_outline_dock", None)
        if dock is not None and dock.isVisible():
            try:
                if bench.navigator_visible():
                    bench.set_navigator_visible(False)
            except (AttributeError, RuntimeError):
                pass
            index = max(0, int(getattr(bench, "current_index", 0) or 0))
            if index:
                dock.set_current(index)
        self._reposition_workbench()

    def _hide_workbench(self) -> None:
        bench = getattr(self, "_chapter_workbench", None)
        if bench is not None:
            bench.hide()
        self._workbench_session_id = ""

    def _reposition_workbench(self) -> None:
        bench = getattr(self, "_chapter_workbench", None)
        page = getattr(self, "_active_page", None)
        if bench is None or page is None:
            return
        dock = getattr(self, "_outline_dock", None)
        dock_width = 0
        if dock is not None and dock.isVisible():
            dock_width = max(0, dock.width())
        available = max(420, int(page.width()) - dock_width - 16)
        bench.setGeometry(
            dock_width + 4,
            8,
            available,
            max(240, page.height() - 16),
        )
        bench.raise_()

    def _toggle_workbench(self) -> None:
        bench = getattr(self, "_chapter_workbench", None)
        if bench is not None and bench.isVisible():
            self._hide_workbench()
        else:
            self._show_workbench()

    # ---- data binding ------------------------------------------------------
    @property
    def _cache(self) -> ChapterCacheStore:
        store = getattr(self, "_chapter_cache_store", None)
        if store is None:
            store = ChapterCacheStore()
            self._chapter_cache_store = store
        return store

    def _open_workbench_document(
        self,
        *,
        source_path: str,
        titles: list[str],
    ) -> None:
        """Open (or refresh) the workbench with an outline from the cache."""
        session = getattr(self, "_active_session", None)
        if session is None:
            return
        bench = self._ensure_workbench()
        if bench is None:
            return
        self._workbench_session_id = session.session_id
        bench.open_document(source_path, str(titles[0] if titles else "文档工作台"))
        bench.set_outline(list(titles or ()))
        # hydrate from the cache store (created by the authoring run) when
        # entries exist, otherwise blank rows.
        entries = self._cache.load_outline(session.session_id)
        state_map = {e.index: e for e in entries}
        for i, _title in enumerate(titles or (), start=1):
            entry = state_map.get(i)
            if entry is not None:
                bench.navigator.set_state(i, entry.state)
                bench.navigator.set_stats(
                    i,
                    chars=entry.chars,
                    score=entry.score,
                    grade=entry.grade,
                )
            else:
                bench.navigator.set_state(i, "pending")
        bench.navigator.row(1)
        self._show_workbench()
        self._render_workbench_chapter(1)
        # Restore / populate the persistent left dock from the same cache so
        # the fused dock stays in lock-step with the workbench.
        restore = getattr(self, "_dock_restore_from_cache", None)
        if restore is not None:
            restore(session.session_id)
        else:
            dock_present = getattr(self, "_dock_outline_present", None)
            if dock_present is not None:
                dock_present(list(titles or ()))

    def _render_workbench_chapter(self, index: int) -> None:
        bench = getattr(self, "_chapter_workbench", None)
        session = getattr(self, "_active_session", None)
        if bench is None or session is None or not getattr(bench, "isVisible", lambda: False)():
            return
        session_id = getattr(self, "_workbench_session_id", "") or session.session_id
        # Re-derive the image resolution context (base dir + drop stale cached
        # image resources) so a chapter synced after an image insertion/path
        # change never reuses the old picture for the same relative path.
        prepare = getattr(bench, "prepare_for_render", None)
        if prepare is not None:
            prepare()
        body = self._cache.read_chapter(session_id, index)
        blocks = _parse_outline_blocks(body) if body else []
        resolver = getattr(self, "_resolve_workbench_image_blocks", None)
        if resolver is not None:
            blocks = resolver(blocks)
        if blocks:
            bench.editor.set_outline_document(blocks)
        else:
            bench.editor.clear_document()

    # ---- streamed append from authoring / rewrite -------------------------
    def _workbench_append_chapter(
        self,
        index: int,
        *,
        text: str,
        kind: int = _BODY,
    ) -> None:
        """Append a streamed chunk into the currently visible chapter."""
        bench = getattr(self, "_chapter_workbench", None)
        if bench is None or not bench.isVisible():
            return
        if getattr(bench, "_current_index", 0) != int(index) or not text:
            return
        bench.editor.append_live(kind, text)

    def _workbench_reload_chapter(self, index: int) -> None:
        self._render_workbench_chapter(index)

    # ---- navigation / edit hooks -------------------------------------------
    def _on_workbench_navigate(self, index: int) -> None:
        self._render_workbench_chapter(index)
        dock = getattr(self, "_outline_dock", None)
        if dock is not None and dock.isVisible():
            dock.set_current(int(index or 0))

    def _on_workbench_edited(self, snapshot: str) -> None:
        # User manually edited the editor: mirror into cache (debounced by
        # save) and mark current chapter done + rescan score.
        bench = getattr(self, "_chapter_workbench", None)
        session = getattr(self, "_active_session", None)
        if bench is None or session is None:
            return
        session_id = getattr(self, "_workbench_session_id", "") or session.session_id
        index = max(0, int(getattr(bench, "_current_index", 0) or 0))
        if index <= 0:
            return
        try:
            self._cache.replace_chapter(session_id, index, snapshot)
            entry = self._cache.update_state(
                session_id, index, "done", rescan_score=True
            )
        except (OSError, ValueError):
            return
        if entry is not None:
            bench.navigator.set_state(index, entry.state)
            bench.navigator.set_stats(
                index, chars=entry.chars, score=entry.score, grade=entry.grade
            )
            sync = getattr(self, "_dock_sync_entry", None)
            if sync is not None:
                sync(
                    index,
                    state=entry.state,
                    chars=entry.chars,
                    score=entry.score,
                    grade=entry.grade,
                )

    def _workbench_save(self) -> None:
        bench = getattr(self, "_chapter_workbench", None)
        session = getattr(self, "_active_session", None)
        if bench is None or session is None:
            return
        snapshot = bench.editor.text_snapshot()
        if not snapshot.strip():
            return
        source = str(getattr(self, "_workbench_source_path", "") or "")
        suggested = "报告全文.revised.docx"
        if source:
            p = Path(source)
            suggested = f"{p.stem}.工作台编辑.docx"
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "保存文档工作台为新文件",
            suggested,
            "Word 文档 (*.docx)",
        )
        if not path_text:
            return
        if not path_text.casefold().endswith(".docx"):
            path_text += ".docx"
        session_id = getattr(self, "_workbench_session_id", "") or session.session_id
        try:
            # Flush the visible chapter edits (user may have typed) back into
            # its cache row before assembling the full document.
            visible_index = int(getattr(bench, "_current_index", 0) or 0)
            if visible_index > 0 and snapshot.strip():
                self._cache.replace_chapter(session_id, visible_index, snapshot)
            entries = self._cache.load_outline(session_id)
            parts: list[str] = []
            for entry in entries:
                body = self._cache.read_chapter(session_id, entry.index)
                if not body.strip():
                    body = f"{entry.title}\n（该章正文暂缺，请让 AI 补充或手动填写。）"
                parts.append(body)
            full_text = "\n\n".join(parts)
            if not full_text.strip():
                full_text = snapshot
            written = write_plain_docx(str(path_text), full_text)
        except (OSError, ValueError, RuntimeError) as exc:  # noqa: BLE001
            self._show_session_navigation_error("保存失败", exc)
            return
        self._workbench_last_output = str(written)
        # Mirror the right-side editor's save feedback on the left workbench so
        # both columns report the same outcome consistently.
        from src.assistant.ui.status_toast import (
            status_toast_kind,
            status_toast_text,
        )

        show_toast = getattr(bench, "show_toast", None)
        if show_toast is not None:
            show_toast(
                status_toast_text("saved_new_kept"),
                kind=status_toast_kind("saved_new_kept"),
            )
        # Mark all cache chapters that exist as done with rescored grades after
        # a successful save so the navigator reflects the saved doc.
        for entry in self._cache.load_outline(session_id):
            updated_entry = self._cache.update_state(
                session_id, entry.index, "done", rescan_score=True
            )
            if updated_entry is not None:
                bench.navigator.set_state(entry.index, updated_entry.state)
                bench.navigator.set_stats(
                    entry.index,
                    chars=updated_entry.chars,
                    score=updated_entry.score,
                    grade=updated_entry.grade,
                )
                sync = getattr(self, "_dock_sync_entry", None)
                if sync is not None:
                    sync(
                        entry.index,
                        state=updated_entry.state,
                        chars=updated_entry.chars,
                        score=updated_entry.score,
                        grade=updated_entry.grade,
                    )
        self._append_workbench_saved_message(str(written))

    def _append_workbench_saved_message(self, path_text: str) -> None:
        from src.assistant.contracts.messages import AssistantMessage

        session = getattr(self, "_active_session", None)
        if session is None:
            return
        try:
            updated = self._coordinator.append_message(
                session,
                AssistantMessage.text(
                    role="assistant",
                    text=f"✅ 已把工作台文档另存为新文件（未覆盖原文档）：\n{path_text}",
                ),
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            return
        if updated is not None:
            self._active_session = updated
            self._render_active_session()


def _parse_outline_blocks(body: str) -> list[tuple[int, str]]:
    """Best-effort split of a chapter body into (kind, text) blocks.

    Heading 1  -> lines that look like “第X章 …” or start with “# ”
    Heading 2  -> lines starting with a numbered subsection “x.y …” or “## ”
    everything else -> body paragraph
    """
    import re

    # 统一中文章节约定：第X(单元|部分|章|篇|部|卷|分)=H1；第X节=章内小节(H2)。
    h1 = re.compile(
        r"^\s*(第\s*[一二三四五六七八九十百千万〇零两0-9１-９]+\s*(?:单元|部分|[章篇部卷分])|"
        r"[#]{1}\s+|目\s*录)",
        re.M,
    )
    h2 = re.compile(
        r"^\s*([0-9]+(?:\.[0-9]+)+[\s\u3000、．.]|"
        r"第\s*[一二三四五六七八九十百千万〇零两0-9１-９]+\s*节|[#]{2}\s+)",
        re.M,
    )
    image = re.compile(r"""^\s*!\[[^\]]*\]\(([^)\s]+)(?:\s+["'][^"']*["'])?\)\s*$""")
    result: list[tuple[int, str]] = []
    for line in str(body or "").splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        img_match = image.match(line)
        if img_match:
            # A standalone image line: store the src path so the workbench can
            # render it as an actual picture instead of markdown text.
            result.append((_IMAGE, img_match.group(1)))
        elif h2.match(line):
            result.append((_H2, line.strip()))
        elif h1.match(line):
            result.append((_H1, line.strip()))
        else:
            result.append((_BODY, line.strip()))
    return result


def write_plain_docx(output_path: str, snapshot: str) -> str:
    """Write editor plain text into a fresh .docx preserving simple styles.

    Lines that look like “第X章/一、…” become Heading 1, numbered subsections
    (x.y …) become Heading 2, the rest are Normal paragraphs.  Never touches
    the source file.
    """
    from docx import Document

    doc = Document()
    for kind, text in _parse_outline_blocks(snapshot):
        if kind == _H1:
            doc.add_heading(str(text), level=1)
        elif kind == _H2:
            doc.add_heading(str(text), level=2)
        else:
            doc.add_paragraph(str(text))
    target = Path(str(output_path)).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(target))
    return str(target)


__all__ = [
    "AssistantChapterWorkbenchMixin",
    "write_plain_docx",
]
