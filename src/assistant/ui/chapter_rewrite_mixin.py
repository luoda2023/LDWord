# -*- coding: utf-8 -*-
"""Document chapter editing entry for the assistant panel.

Phase-A UI: lets the user ask the assistant to improve / rewrite one chapter
of an already formatted document that they opened in the conversation.

Flow
----
1. The user attaches a .docx (or .doc/.wps) and asks to list its chapters, or
   the panel is asked to "open a document and list its outline".
2. :meth:`_show_chapter_outline_card` detects the chapter outline and appends
   an interaction card that lists every chapter with an "优化此章" action.
3. Clicking an action dispatches :meth:`_handle_chapter_rewrite_action`, which
   streams the chapter body + the user instruction to the current model and,
   when the model returns the revised text, writes it back into a *copy* of
   the source document via :mod:`chapter_document_editor` (layout preserved).

The rewrite runs on a background worker (mirroring ContentGenerationWorker)
so the UI stays responsive and the conversation keeps streaming text.
"""
from __future__ import annotations

import json

from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

from src.assistant.application.chapter_document_editor import (
    ChapterEditRequest,
    apply_chapter_edit,
    chapter_body_text,
    detect_chapter_outline,
)
from src.assistant.application.legacy_image_migration import (
    migrate_legacy_images,
    rewrite_markdown_references,
)
from src.assistant.contracts.messages import AssistantMessage
from src.assistant.runtime.cancellation import AssistantCancellationToken
from src.qt_api import QObject, Qt, QTimer, Signal

CHAPTER_REWRITE_ACTION = "rewrite_document_chapter"
CHAPTER_OUTLINE_ACTION = "show_document_chapter_outline"
CHAPTER_WORKBENCH_ACTION = "open_document_workbench"

# 编辑器内 AI 动作（右键菜单）：kind → 动作说明
EDITOR_AI_ACTIONS = {
    "rewrite": "重新改写所选内容",
    "polish": "润色优化所选内容",
    "continue": "在光标处补充内容",
}


class _EditorAiWorker(QObject):
    """编辑器内 AI 操作的两阶段后台 worker。

    阶段 1（understanding）：把本章正文 + 全局记忆摘要交给模型，产出一份
    「本章理解」短摘要——这就是用户看到的"AI 先了解这一章写什么"。
    阶段 2（drafting）：带着第 1 阶段的理解 + 用户指令（选区文本或空）
    产出改写/润色/续写结果。

    每个阶段开始时发 phase 信号，结束发 finished（成功）或 failed。
    """

    phase = Signal(str)          # JSON payload → 右下角状态浮层
    finished = Signal(str)       # JSON：{replacement | insertion}
    failed = Signal(str)

    def __init__(
        self,
        gateway,
        *,
        kind: str,
        selection: str,
        chapter_title: str,
        chapter_body: str,
        memory_context: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._gateway = gateway
        self._kind = str(kind or "")
        self._selection = str(selection or "")
        self._chapter_title = str(chapter_title or "")
        self._chapter_body = str(chapter_body or "")
        self._memory_context = str(memory_context or "")
        self._cancellation = AssistantCancellationToken()
        self._thread = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        from threading import Thread

        if self.is_running:
            raise RuntimeError("editor AI worker already running")
        self._thread = Thread(target=self._run, name="editor-ai", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancellation.cancel()

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        self.cancel()
        thread = self._thread
        if thread is None:
            return True
        thread.join(max(0, timeout_ms) / 1000)
        return not thread.is_alive()

    # ---- prompt builders ------------------------------------------------
    def _base_context(self) -> str:
        parts = [f"所在章节：{self._chapter_title}"]
        if self._memory_context:
            parts.append(self._memory_context)
        parts.append(f"【本章全文】\n{self._chapter_body}")
        return "\n\n".join(parts)

    def _understand_request(self):
        from src.assistant.runtime.provider_contract import ProviderRequest

        prompt = (
            self._base_context()
            + "\n\n【任务】请用 3-4 句话概括：这一章讲了什么、面向什么读者、"
            "行文风格与结构特点、与相邻章节如何衔接。只输出这份理解摘要，"
            "不要输出正文。"
        )
        return ProviderRequest(
            request_id=uuid4().hex,
            model=getattr(self._gateway, "model", "") or "assistant",
            system_prompt=(
                "你是 LDWord 文档写作助手。用户即将让你改写/润色/续写一段"
                "章节内容。先阅读给定的章节全文与项目背景，输出简短的理解"
                "摘要（3-4 句），帮助后续改写保持全文一致。"
            ),
            messages=({"role": "user", "content": prompt},),
            metadata={"purpose": "editor_ai_understand"},
        )

    def _draft_request(self, understanding: str):
        from src.assistant.runtime.provider_contract import ProviderRequest

        kind_text = EDITOR_AI_ACTIONS.get(self._kind, "优化内容")
        if self._kind in {"rewrite", "polish"}:
            task = (
                f"【待处理选段】\n{self._selection}\n\n"
                f"【要求】{kind_text}。保持与本章其余部分及相邻章节的衔接，"
                "保留原有编号与 Markdown 格式（标题/表格/列表）。"
                "只输出处理后的这段文本，不要解释。"
            )
        else:  # continue
            task = (
                "【要求】从光标所在位置继续补充内容，自然承接上文，"
                "符合本章主题与行文风格，输出 1-3 段内容。"
                "只输出新增内容，不要重复已有文本，不要解释。"
            )
        prompt = (
            self._base_context()
            + (f"\n\n【对本章的理解】\n{understanding}" if understanding else "")
            + "\n\n" + task
        )
        return ProviderRequest(
            request_id=uuid4().hex,
            model=getattr(self._gateway, "model", "") or "assistant",
            system_prompt=(
                "你是 LDWord 文档写作助手。基于对章节的理解执行改写/润色/"
                "续写，输出 UTF-8 Markdown 正文，不要解释、不要代码围栏。"
            ),
            messages=({"role": "user", "content": prompt},),
            metadata={"purpose": "editor_ai_draft"},
        )

    # ---- two-phase run ----------------------------------------------------
    def _emit_phase(self, phase: str, detail: str = "") -> None:
        self.phase.emit(
            json.dumps(
                {"phase": phase, "detail": detail, "kind": self._kind},
                ensure_ascii=False,
            )
        )

    def _stream_text(self, request) -> str:
        parts: list[str] = []
        for event in self._gateway.stream(request):
            if self._cancellation.cancelled():
                raise RuntimeError("editor_ai_cancelled")
            if event.type == "text_delta":
                parts.append(event.text)
            elif event.type == "error":
                raise RuntimeError(event.text or "editor_ai_provider_failed")
        return "".join(parts).strip()

    def _run(self) -> None:
        try:
            # 阶段 1：了解章节
            self._emit_phase("understanding", f"正在阅读《{self._chapter_title}》全文")
            understanding = ""
            try:
                understanding = self._stream_text(self._understand_request())
            except RuntimeError as exc:
                if "cancelled" in str(exc):
                    raise
                # 了解阶段失败不阻断主任务，直接进入起草。
                understanding = ""
            # 阶段 2：起草
            detail = understanding[:80] + ("…" if len(understanding) > 80 else "")
            self._emit_phase("drafting", detail)
            result_text = self._stream_text(self._draft_request(understanding))
            if not result_text:
                raise RuntimeError("editor_ai_empty_result")
            # 阶段 3：应用
            self._emit_phase("applying", "正在写入编辑器")
            payload = (
                {"kind": self._kind, "replacement": result_text}
                if self._kind in {"rewrite", "polish"}
                else {"kind": self._kind, "insertion": result_text}
            )
            self.finished.emit(json.dumps(payload, ensure_ascii=False))
        except RuntimeError as exc:
            message = str(exc)
            if "cancelled" in message:
                return
            self.failed.emit(message)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class _ChapterRewriteWorker(QObject):
    """Background worker that streams one chapter rewrite from the model."""

    delta = Signal(str)
    finished = Signal(str, object)  # (session_id, receipt-or-error)
    failed = Signal(str, str)

    def __init__(self, gateway, chapter_prompt: str, chapter_title: str, parent=None) -> None:
        super().__init__(parent)
        self._gateway = gateway
        self._prompt = str(chapter_prompt or "")
        self._title = str(chapter_title or "")
        self._cancellation = AssistantCancellationToken()
        self._thread = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        from threading import Thread

        if self.is_running:
            raise RuntimeError("Chapter rewrite worker already running")
        self._thread = Thread(target=self._run, name="chapter-rewrite", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancellation.cancel()

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        self.cancel()
        thread = self._thread
        if thread is None:
            return True
        thread.join(max(0, timeout_ms) / 1000)
        return not thread.is_alive()

    def _run(self) -> None:
        try:
            parts: list[str] = []
            for event in self._gateway.stream(self._request()):
                if self._cancellation.cancelled():
                    raise RuntimeError("chapter_rewrite_cancelled")
                if event.type == "text_delta":
                    parts.append(event.text)
                    self.delta.emit(event.text)
                elif event.type == "error":
                    raise RuntimeError(event.text or "chapter_rewrite_provider_failed")
            text = "".join(parts).strip()
            if not text:
                raise RuntimeError("chapter_rewrite_empty")
            self.finished.emit("", text)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit("", str(exc) or type(exc).__name__)

    def _request(self):
        from src.assistant.runtime.provider_contract import ProviderRequest

        return ProviderRequest(
            request_id=uuid4().hex,
            model=getattr(self._gateway, "model", "") or "assistant",
            system_prompt=(
                "你是 LDWord 文档排版助手。用户给出某文档一个章节的现稿，"
                "以及它的修改要求。你只重写该章节正文：返回可直接替换该章节的文本，"
                "保留原有小节编号（如 1.1/1.2），不要输出文档全标题、前言、目录或其它章节；"
                "不要伪造事实，缺失处用“待补充”占位。"
            ),
            messages=({"role": "user", "content": self._prompt},),
            metadata={"purpose": "chapter_rewrite", "chapter_title": self._title},
        )


class AssistantChapterRewriteMixin:
    """Own the chapter-outline card and per-chapter rewrite action."""

    # ---- entry points ---------------------------------------------------
    def _chapter_rewrite_available(self) -> bool:
        return hasattr(self, "_coordinator") and hasattr(self, "_active_session")

    def _on_open_document_for_chapter_edit(self) -> None:
        """Pick a formatted Word/WPS file, ensure a session, list its chapters."""
        from src.qt_api import QFileDialog

        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "选择要按章节优化的文档",
            "",
            "Word / WPS 文档 (*.docx *.doc *.wps)",
        )
        if not path_text:
            return
        path = Path(path_text).expanduser()
        if not path.is_file():
            return
        session = self._active_session
        if session is None or not session.messages:
            profile_id, model_id = self._provider_selection.selected_identity()
            try:
                session = self._coordinator.create_session(
                    provider_profile_id=profile_id,
                    model_id=model_id,
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                self._show_session_navigation_error("无法新建对话", exc)
                return
            self._active_session = session
        self._show_document_chapter_outline(str(path.resolve()))
    def _open_document_in_workbench(self, path_text: str) -> None:
        """Open a formatted document in the Word-style workbench editor.

        Extracts every chapter body from the source document into the
        sidecar chapter cache, then shows the workbench with the outline
        navigator + rich-text viewport so the user can read / keep editing
        each chapter and save a new .docx.
        """
        session = self._active_session
        if session is None:
            return
        path = Path(str(path_text or "")).expanduser()
        if not path.is_file():
            self._append_chapter_rewrite_message(
                session, "找不到文档", f"文件不存在：{path}", actions=()
            )
            return
        try:
            chapters = detect_chapter_outline(path)
        except Exception as exc:  # noqa: BLE001 - forward parse errors
            self._append_chapter_rewrite_message(
                session, "无法识别章节", f"没能从文档中识别出章节大纲：{exc}", actions=()
            )
            return
        if not chapters:
            self._append_chapter_rewrite_message(
                session,
                "未识别到章节",
                "这份文档没有可识别的章节目录，无法在工作台分章编辑。",
                actions=(),
            )
            return
        session_id = session.session_id
        try:
            # Seed the cache with each chapter plus its ancestor group (篇/部分/
            # 卷/单元) so the left dock can render collapsible groups later.
            self._cache.begin_run(
                session_id,
                [c.title for c in chapters],
                parts=[getattr(c, "part_title", "") or "" for c in chapters],
            )
            for c in chapters:
                body = chapter_body_text(path, c)
                if body.strip():
                    self._cache.replace_chapter(session_id, c.index, body)
                entry = self._cache.update_state(
                    session_id, c.index, "done", rescan_score=True
                )
            self._workbench_source_path = str(path.resolve())
            # When the user keeps memory next to their documents, bring any
            # app-internal system memory to the now-bound source folder so later
            # rewrite passes read what generation wrote.
            if hasattr(self, "_migrate_session_memory_to_document"):
                self._migrate_session_memory_to_document(session_id)
            self._sync_marktext_image_directory()
            # Migrate any legacy ``_1/_2`` image files left next to the source
            # document and rewrite the just-loaded chapter bodies so references
            # point at the content-hash names.
            self._migrate_workbench_images(session_id, path)
            if hasattr(self, "_open_workbench_document"):
                self._open_workbench_document(
                    source_path=str(path.resolve()),
                    titles=[c.title for c in chapters],
                )
        except (OSError, ValueError, RuntimeError) as exc:  # noqa: BLE001
            self._append_chapter_rewrite_message(
                session, "打开工作台失败", str(exc), actions=()
            )
            return
        self._append_chapter_rewrite_message(
            session,
            "已在文档工作台打开",
            f"共 {len(chapters)} 章已载入工作台，可在 Word 式视口逐章查看、继续编辑，"
            "支持撤销/重做与另存为新文档（不覆盖原文件）。",
            actions=(),
        )

    def _sync_marktext_image_directory(self) -> None:
        """Point the embedded MarkText editor's image persistence at the
        workbench source directory so pasted images land next to the document."""
        source = str(getattr(self, "_workbench_source_path", "") or "")
        view = getattr(self, "_marktext_view", None)
        if view is None:
            return
        if source:
            base = str(Path(source).resolve().parent)
        else:
            base = str(Path.cwd())
        view.set_image_directory(base)

    def _migrate_workbench_images(self, session_id: str, source_path: Path) -> None:
        """Migrate legacy ``_1/_2`` images next to ``source_path`` and rewrite
        the loaded chapter bodies that reference the old filenames.

        Runs once when a document is opened in the workbench so that a one-off
        set of old files (from versions that used ``_1``/``_2`` collision names)
        is normalised to content-hash names and chapter markdown references are
        kept valid.
        """
        try:
            images_dir = Path(source_path).resolve().parent / "images"
        except OSError:
            return
        try:
            mapping = migrate_legacy_images(images_dir)
        except OSError:
            return
        if not mapping:
            return
        try:
            entries = self._cache.load_outline(session_id)
        except (OSError, ValueError, RuntimeError):
            return
        for entry in entries:
            index = int(getattr(entry, "index", 0) or 0)
            if index <= 0:
                continue
            try:
                body = self._cache.read_chapter(session_id, index)
            except (OSError, ValueError, RuntimeError):
                continue
            rewritten = rewrite_markdown_references(body, mapping)
            if rewritten != body:
                try:
                    self._cache.replace_chapter(session_id, index, rewritten)
                except (OSError, ValueError, RuntimeError):
                    pass

    def _show_document_chapter_outline(self, path_text: str) -> None:
        """Detect and render the outline card for a user-opened document."""
        session = self._active_session
        if session is None:
            return
        path = Path(str(path_text or "")).expanduser()
        if not path.is_file():
            self._append_chapter_rewrite_message(
                session, "找不到文档", f"文件不存在：{path}", actions=()
            )
            return
        try:
            chapters = detect_chapter_outline(path)
        except Exception as exc:  # noqa: BLE001 - forward parse errors
            self._append_chapter_rewrite_message(
                session,
                "无法识别章节",
                f"没能从文档中识别出章节大纲：{exc}",
                actions=(),
            )
            return
        if not chapters:
            self._append_chapter_rewrite_message(
                session,
                "未识别到章节",
                "这份文档没有可识别的章节目录（需要标题样式或“第X章/一、”前缀）。",
                actions=(),
            )
            return
        document_path = str(path.resolve())
        chapter_lines = []
        chapter_actions = []
        last_part = None
        for c in chapters:
            # Documents that nest coarse grouping headings (篇/部分/卷/单元)
            # above their 第X章 carry a ``part_title``; render a light grouping
            # row whenever the part changes so the user sees 篇 > 章 structure.
            part = getattr(c, "part_title", "") or ""
            if part and part != last_part:
                chapter_lines.append(f"▍{part}")
                last_part = part
            count_text = (
                f"（约 {c.paragraph_count} 段）" if c.paragraph_count >= 0 else ""
            )
            chapter_lines.append(f"  第 {c.index} 章  {c.title}{count_text}")
            chapter_actions.append(
                {
                    "id": f"{CHAPTER_REWRITE_ACTION}:{c.index}",
                    "label": f"✏️ 优化/重写：{c.title}",
                    "variant": "secondary",
                    "alignment": "left",
                    "chapter_title": c.title,
                    "part_title": part,
                }
            )
        chapter_actions.append(
            {
                "id": CHAPTER_WORKBENCH_ACTION,
                "label": "📖 在工作台打开/编辑全文",
                "variant": "primary",
                "alignment": "left",
                "document_path": document_path,
            }
        )
        chapter_actions.append(
            {
                "id": CHAPTER_OUTLINE_ACTION,
                "label": "🔄 重新识别章节",
                "variant": "ghost-primary",
                "alignment": "left",
                "document_path": document_path,
            }
        )
        payload = {
            "document_path": document_path,
            "chapters": [
                {
                    "index": c.index,
                    "title": c.title,
                    "part_title": getattr(c, "part_title", "") or "",
                    "heading_index": c.heading_para_index,
                    "paragraph_count": c.paragraph_count,
                }
                for c in chapters
            ],
        }
        body_text = (
            f"已识别 {path.name} 的章节目录，共 {len(chapters)} 章。\n"
            + "\n".join(chapter_lines)
            + "\n\n点击下方某章的按钮，AI 会读取该章现稿并按你的附加要求改写，"
            "改写只作用于该章、保留原排版，另存为新文件（不覆盖原文档）。"
        )
        self._append_chapter_rewrite_message(
            session,
            "文档章节已识别",
            body_text,
            actions=tuple(chapter_actions),
            extra_payload=payload,
        )

    # ---- card action dispatch ------------------------------------------
    def _handle_chapter_rewrite_action(self, action_id: str, payload: Mapping) -> bool:
        """Return True when the action belongs to this mixin and was handled."""
        if action_id == CHAPTER_WORKBENCH_ACTION:
            document_path = str(payload.get("document_path") or "")
            if document_path:
                self._open_document_in_workbench(document_path)
            return True
        if action_id == CHAPTER_OUTLINE_ACTION:
            document_path = str(payload.get("document_path") or "")
            if document_path:
                self._show_document_chapter_outline(document_path)
            return True
        if action_id == CHAPTER_REWRITE_ACTION or action_id.startswith(
            CHAPTER_REWRITE_ACTION + ":"
        ):
            index_text = action_id.split(":", 1)[1] if ":" in action_id else ""
            if index_text:
                payload = dict(payload or {})
                payload["chapter_index"] = index_text
            self._start_chapter_rewrite(payload)
            return True
        if action_id == "editor_ai":
            self._start_editor_ai_action(payload)
            return True
        return False

    # ---- 编辑器内 AI（右键）：两阶段状态反馈 -------------------------------
    def _start_editor_ai_action(self, payload: Mapping) -> None:
        """编辑器右键 AI 动作入口：先了解章节，再改写/润色/续写。

        全程通过 bridge.editor_ai_phase 推送阶段状态到右下角等待浮层，
        让用户随时知道 AI 在做什么、做到哪一步（不再是无声进度条）。
        """
        payload = dict(payload or {})
        kind = str(payload.get("kind") or "rewrite").strip()
        if kind not in EDITOR_AI_ACTIONS:
            kind = "rewrite"
        selection = str(payload.get("selection") or "")
        session = self._active_session
        if session is None:
            return
        view = getattr(self, "_marktext_view", None)
        if view is None:
            return
        bridge = view.bridge
        if getattr(self, "_editor_ai_worker", None) is not None and (
            self._editor_ai_worker.is_running
        ):
            bridge.notify_editor_ai_phase(
                {"phase": "failed", "detail": "上一项 AI 操作尚未结束", "kind": kind}
            )
            return
        # 定位当前章节与正文（章节缓存优先，退回整篇解析）。
        index = int(getattr(bridge, "_active_chapter", 0) or 0)
        session_id = getattr(self, "_workbench_session_id", "") or session.session_id
        cache = self._cache
        title = ""
        body = ""
        outline_title = ""
        if index > 0:
            try:
                entries = cache.load_outline(session_id)
                outline_title = next(
                    (e.title for e in entries if e.index == index), ""
                )
            except (OSError, ValueError):
                outline_title = ""
            try:
                body = cache.read_chapter(session_id, index)
            except OSError:
                body = ""
        if not body.strip():
            # 缓存没有正文（例如打开的本地文档未入缓存）时退回整篇。
            body = str(getattr(bridge, "_content_markdown", "") or "")
            title = "当前文档"
        if kind in {"rewrite", "polish"} and not selection.strip():
            bridge.notify_editor_ai_phase(
                {"phase": "failed", "detail": "请先选中要处理的文字", "kind": kind}
            )
            return
        # 全局记忆（项目背景/相邻章节摘要），与整章改写共用。
        memory_context = self._rewrite_memory_context(
            session_id, index, source_path=""
        )
        title = title or outline_title or (f"第 {index} 章" if index else "当前文档")
        try:
            runner = getattr(self, "_fixed_turn_runner", None)
            gateway = (
                runner.gateway
                if runner is not None and getattr(runner, "gateway", None) is not None
                else self._provider_router.resolve(session.provider_profile_id)
            )
        except Exception as exc:  # noqa: BLE001
            bridge.notify_editor_ai_phase(
                {"phase": "failed", "detail": f"模型不可用：{exc}", "kind": kind}
            )
            return
        worker = _EditorAiWorker(
            gateway,
            kind=kind,
            selection=selection,
            chapter_title=title,
            chapter_body=body,
            memory_context=memory_context,
            parent=self,
        )
        self._editor_ai_worker = worker
        worker.phase.connect(
            lambda text: bridge.notify_editor_ai_phase(json.loads(text))
        )
        worker.finished.connect(
            lambda text: self._finish_editor_ai_action(json.loads(text))
        )
        worker.failed.connect(
            lambda message: self._fail_editor_ai_action(kind, message)
        )
        worker.start()

    def _finish_editor_ai_action(self, payload: dict) -> None:
        bridge = getattr(getattr(self, "_marktext_view", None), "bridge", None)
        if bridge is None:
            return
        bridge.notify_editor_ai_result(payload)
        kind = str(payload.get("kind") or "")
        done_text = (
            "改写已替换进编辑器（Ctrl+Z 可撤销）"
            if kind in {"rewrite", "polish"}
            else "内容已插入光标处（Ctrl+Z 可撤销）"
        )
        bridge.notify_editor_ai_phase(
            {"phase": "done", "detail": done_text, "kind": kind}
        )
        # 结果落进章节缓存，使保存/导出链拿到的是最新内容。
        # 编辑器 change 事件会触发 request_live_edit → 缓存同步，这里不重复写。
        self._editor_ai_worker = None

    def _fail_editor_ai_action(self, kind: str, message: str) -> None:
        bridge = getattr(getattr(self, "_marktext_view", None), "bridge", None)
        if bridge is not None:
            bridge.notify_editor_ai_phase(
                {"phase": "failed", "detail": message, "kind": kind}
            )
        self._editor_ai_worker = None

    def _handle_card_action(self, action_id: str, payload: object) -> None:
        """Route chapter-rewrite actions first, then the general card actions."""
        if action_id in {
            CHAPTER_OUTLINE_ACTION,
            CHAPTER_WORKBENCH_ACTION,
            CHAPTER_REWRITE_ACTION,
        } or action_id.startswith(CHAPTER_REWRITE_ACTION + ":"):
            if isinstance(payload, Mapping):
                self._handle_chapter_rewrite_action(action_id, payload)
            return
        super()._handle_card_action(action_id, payload)

    def _rewrite_memory_context(
        self, session_id, chapter_index: int, *, source_path: str = ""
    ) -> str:
        """Build a compact system-memory context block for a single-chapter
        rewrite.

        Reads ``system_memory.json`` for the session / source document and
        returns a prompt fragment carrying the global background (project brief
        + locked decisions), the neighboring outline titles, and the summaries
        of the chapters immediately before / after the one being rewritten.
        This keeps the model from "losing memory" while it rewrites one chapter
        in isolation: it still sees the whole-document context and what its
        neighbours already established.  Returns ``""`` when there is no
        memory worth reminding the model about.

        The memory is looked up next to the bound source document when the
        user's storage-location preference is ``project``; otherwise (and when
        no real file is bound) it falls back to the app-internal session cache.
        """

        from src.assistant.application.system_memory import SystemMemoryStore

        try:
            base_dir = self._resolve_memory_dir(source_path=source_path)
        except Exception:  # noqa: BLE001 - never block rewrite
            base_dir = None
        try:
            memory = SystemMemoryStore(base_dir=base_dir).load(
                str(session_id or "")
            )
        except (OSError, ValueError, TypeError):  # noqa: BLE001 - never block rewrite
            return ""

        lines: list[str] = []

        # --- 全局背景 ---------------------------------------------------
        brief = str(getattr(memory, "project_brief", "") or "").strip()
        if brief:
            lines.append("项目背景：" + brief)
        decisions = tuple(getattr(memory, "decisions", ()) or ())
        if decisions:
            lines.append(
                "已确定的关键口径：" + "；".join(str(d) for d in decisions)
            )

        # --- 相邻章节的标题（保持衔接与编号一致） -------------------------
        outline = tuple(
            str(t) for t in (getattr(memory, "outline", ()) or ()) if str(t).strip()
        )
        chapter_index = max(0, int(chapter_index or 0))
        if outline and chapter_index:
            neighbor_indexes = sorted(
                idx
                for idx in (
                    chapter_index - 2,
                    chapter_index - 1,
                    chapter_index + 1,
                    chapter_index + 2,
                )
                if 1 <= idx <= len(outline)
            )
            if neighbor_indexes:
                lines.append("相邻章节标题（改写本章须保持与它们的衔接与编号一致）：")
                lines.extend(
                    f"  第 {i} 章：{outline[i - 1]}" for i in neighbor_indexes
                )

        # --- 紧邻章节已覆盖内容摘要 --------------------------------------
        by_index: dict[int, object] = {}
        for chapter in getattr(memory, "chapters", ()) or ():
            by_index[max(0, int(getattr(chapter, "index", 0) or 0))] = chapter
        adjacent = sorted({chapter_index - 1, chapter_index + 1} & set(by_index))
        adjacent_summaries: list[str] = []
        for idx in adjacent:
            entry = by_index[idx]
            title = str(getattr(entry, "title", "") or "").strip()
            summary = str(getattr(entry, "summary", "") or "").strip()
            if not summary:
                continue
            name = f"《{title}》" if title else ""
            adjacent_summaries.append(f"第 {idx} 章{name}已覆盖：{summary}")
        if adjacent_summaries:
            lines.append(
                "相邻章节已覆盖内容（改写本章时不得与它们矛盾，也不得整段复述）："
            )
            lines.extend("  " + text for text in adjacent_summaries)

        if not lines:
            return ""
        header = (
            "【系统记忆 · 全局背景】以下是整篇文档的持久记忆，用于让你在单独"
            "改写本章时不丢失上下文："
        )
        return "\n".join([header, *lines])

    def _start_chapter_rewrite(self, payload: Mapping) -> None:
        session = self._active_session
        if session is None:
            return
        document_path = str(payload.get("document_path") or "")
        try:
            chapter_index = int(payload.get("chapter_index") or payload.get("index") or 0)
        except (TypeError, ValueError):
            chapter_index = 0
        instruction = str(payload.get("instruction") or "").strip()
        self._rewrite_chapter_index = int(chapter_index)
        path = Path(document_path).expanduser()
        if not path.is_file() or chapter_index <= 0:
            return
        if getattr(self, "_chapter_rewrite_worker", None) is not None and self._chapter_rewrite_worker.is_running:
            self._append_chapter_rewrite_message(
                session,
                "正在改写另一章",
                "上一章的改写尚未结束，请稍候再试。",
                actions=(),
            )
            return
        try:
            chapters = detect_chapter_outline(path)
        except Exception as exc:  # noqa: BLE001
            self._append_chapter_rewrite_message(session, "识别章节失败", str(exc), actions=())
            return
        match = next((c for c in chapters if c.index == chapter_index), None)
        if match is None:
            self._append_chapter_rewrite_message(
                session, "章节不存在", f"文档里没有第 {chapter_index} 章。", actions=()
            )
            return
        current_text = chapter_body_text(path, match)
        if not current_text.strip():
            self._append_chapter_rewrite_message(
                session, "章节为空", f"第 {chapter_index} 章没有可改写的正文。", actions=()
            )
            return
        # Resolve the gateway the same way content generation does.  The
        # fixed-turn runner (when injected by the host / tests) wins so the
        # panel can run fully offline with a mock gateway.
        try:
            runner = getattr(self, "_fixed_turn_runner", None)
            gateway = (
                runner.gateway
                if runner is not None and getattr(runner, "gateway", None) is not None
                else self._provider_router.resolve(session.provider_profile_id)
            )
        except Exception as exc:  # noqa: BLE001
            self._append_chapter_rewrite_message(session, "模型不可用", str(exc), actions=())
            return
        # Prepend the persisted system memory (global background + adjacent
        # chapter summaries) so rewriting one chapter does not lose the
        # overall document context or contradict what its neighbors covered.
        memory_context = self._rewrite_memory_context(
            session.session_id, chapter_index, source_path=str(path)
        )
        prompt = (
            f"文档章节：{match.title}\n\n"
            + ((memory_context + "\n\n") if memory_context else "")
            + f"【该章现有正文】\n{current_text}\n\n"
            + f"【修改要求】\n{instruction or '请优化本章内容，使行文更专业、结构更清晰。'}\n"
            "请只返回改写后的该章正文。"
        )
        # A conversation progress card + streaming text row.
        self._append_chapter_rewrite_message(
            session,
            f"正在改写：{match.title}",
            "",
            actions=(),
            progress=True,
            extra_payload={
                "document_path": str(path.resolve()),
                "chapter_index": match.index,
                "chapter_title": match.title,
                "chapter_source": current_text[:400],
            },
        )
        worker = _ChapterRewriteWorker(gateway, prompt, match.title, parent=self)
        self._chapter_rewrite_worker = worker
        worker.delta.connect(
            lambda delta: self._stream_chapter_rewrite_delta(session.session_id, delta)
        )
        worker.finished.connect(
            lambda _sid, text: self._finish_chapter_rewrite(
                path, match.index, match.title, text
            )
        )
        worker.failed.connect(
            lambda _sid, error: self._fail_chapter_rewrite(session.session_id, error)
        )
        worker.start()

    # ---- streaming / finish / fail -------------------------------------
    def _stream_chapter_rewrite_delta(self, session_id: str, delta: str) -> None:
        session = self._active_session
        if session is None or session.session_id != session_id:
            return
        self._composer.set_busy(True)
        # Live typing into the workbench editor when it is visible and
        # parked on this chapter:文字/回车/缩进即时可见 (Word-like view).
        bench = getattr(self, "_chapter_workbench", None)
        if (
            bench is not None
            and bench.isVisible()
            and int(getattr(bench, "_current_index", 0) or 0)
            == int(getattr(self, "_rewrite_chapter_index", 0) or 0)
        ):
            bench.editor.append_raw(str(delta or ""))
        # Reuse the same live-message mechanism as per-chapter generation when
        # available; otherwise fall back to a lightweight caption update.
        if hasattr(self, "_chapter_live_widget") and self._chapter_live_widget is not None:
            if hasattr(self._chapter_live_widget, "append_live_delta"):
                self._chapter_live_widget.append_live_delta(
                    delta=delta,
                    status_text=f"正在改写 · 已写约 {len(str(getattr(self._chapter_live_widget, '_text', ''))) + len(delta)} 字",
                )
                return
        # Simple fallback: nothing to do (worker failure path reports errors).
        self._composer.set_busy(True)

    def _finish_chapter_rewrite(
        self,
        path: Path,
        chapter_index: int,
        chapter_title: str,
        revised_text: str,
    ) -> None:
        session = self._active_session
        if session is None:
            return
        try:
            receipt = apply_chapter_edit(
                path,
                ChapterEditRequest(
                    chapter_index=chapter_index,
                    revised_markdown=revised_text,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self._append_chapter_rewrite_message(
                session, "回写失败", f"{exc}", actions=()
            )
            return
        self._append_chapter_rewrite_message(
            session,
            "章节改写完成",
            f"《{chapter_title}》已改写并另存（未覆盖原文件）",
            actions=(),
            reference={
                "type": "file",
                "title": Path(receipt.output_path).name,
                "path": receipt.output_path,
            },
        )
        self._workbench_refresh_after_rewrite(
            int(chapter_index), str(revised_text or "")
        )
        self._composer.set_busy(False)

    def _workbench_refresh_after_rewrite(
        self, chapter_index: int, revised_text: str
    ) -> None:
        """Mirror a finished rewrite into the workbench cache + viewport."""
        session = getattr(self, "_active_session", None)
        bench = getattr(self, "_chapter_workbench", None)
        if session is None or not str(revised_text or "").strip():
            return
        session_id = getattr(self, "_workbench_session_id", "") or session.session_id
        try:
            self._cache.replace_chapter(session_id, chapter_index, revised_text)
            entry = self._cache.update_state(
                session_id, chapter_index, "done", rescan_score=True
            )
        except (OSError, ValueError, RuntimeError):  # noqa: BLE001
            return
        if entry is not None:
            if bench is not None:
                bench.navigator.set_state(chapter_index, entry.state)
                bench.navigator.set_stats(
                    chapter_index,
                    chars=entry.chars,
                    score=entry.score,
                    grade=entry.grade,
                )
                if (
                    bench.isVisible()
                    and int(getattr(bench, "_current_index", 0) or 0)
                    == int(chapter_index)
                ):
                    self._render_workbench_chapter(chapter_index)
        self._rewrite_chapter_index = 0

    def _fail_chapter_rewrite(self, session_id: str, error: str) -> None:
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            session = None
        if session is not None:
            self._append_chapter_rewrite_message(
                session, "章节改写失败", str(error), actions=()
            )
        self._composer.set_busy(False)

    # ---- message helpers ------------------------------------------------
    def _append_chapter_rewrite_message(
        self,
        session,
        title: str,
        body: str,
        *,
        actions: tuple[dict[str, object], ...],
        reference: dict[str, object] | None = None,
        progress: bool = False,
        extra_payload: dict[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = dict(extra_payload or {})
        if progress:
            payload.update(
                {
                    "interaction_type": "progress",
                    "title": title,
                    "actions": [],
                    "ephemeral": True,
                }
            )
        else:
            payload.update(
                {
                    "interaction_type": "info",
                    "title": title,
                }
            )
            if reference:
                payload["reference"] = reference
            if actions:
                payload["actions"] = list(actions)
        message = AssistantMessage.interaction(
            role="assistant",
            interaction_type="progress" if progress else "info",
            title=title,
            body="" if progress else body,
            payload=payload,
        )
        try:
            updated = self._coordinator.append_message(session, message)
        except (OSError, RuntimeError, TypeError, ValueError):
            return
        self._active_session = updated
        self._render_active_session()
        self._refresh_session_list(select_session_id=updated.session_id)

    def _chapter_rewrite_worker_shutdown(self, timeout_ms: int = 5000) -> bool:
        worker = getattr(self, "_chapter_rewrite_worker", None)
        if worker is None:
            return True
        return worker.shutdown(timeout_ms)

    # ---- 整篇润色（对 dock 里的一个 篇/部分 分组） ---------------------
    def _request_part_polish(self, part_title: str) -> None:
        """Entry for the dock's 「润色整篇」button.

        Polish every chapter under *part_title* in one sequential pass: the AI
        sees the whole part (all chapter titles + each chapter's current draft)
        so later chapters stay consistent, then each chapter is rewritten and
        written back.  When a source .docx is bound (docx workbench), the whole
        part is also written into a *copy* of the document so layout and titles
        are preserved; otherwise the workbench chapter cache is updated and the
        user can export later.
        """
        session = self._active_session
        dock = getattr(self, "_outline_dock", None)
        if session is None or dock is None:
            return
        if getattr(self, "_part_polish_worker", None) is not None and self._part_polish_worker.is_running:
            self._append_chapter_rewrite_message(
                session,
                "正在润色另一篇",
                "上一篇的润色尚未结束，请稍候再试。",
                actions=(),
            )
            return
        part_title = str(part_title or "").strip()
        if not part_title:
            return
        session_id = getattr(self, "_workbench_session_id", "") or session.session_id
        try:
            entries = self._cache.load_outline(session_id)
        except (OSError, ValueError, RuntimeError):
            entries = ()
        part_entries = [
            e for e in entries if str(getattr(e, "part_title", "") or "") == part_title
        ]
        part_entries.sort(key=lambda e: e.index)
        if not part_entries:
            self._append_chapter_rewrite_message(
                session,
                "找不到篇章节",
                f"没有找到《{part_title}》下的章节，无法润色。",
                actions=(),
            )
            return
        # Gather each chapter's current draft (with a placeholder note when a
        # body is missing so the model still knows the chapter exists).
        targets: list[dict[str, object]] = []
        for entry in part_entries:
            body = ""
            try:
                body = self._cache.read_chapter(session_id, entry.index)
            except (OSError, ValueError, RuntimeError):
                body = ""
            if not str(body or "").strip():
                body = f"（《{entry.title}》正文暂缺，请补充完整且专业的正文。）"
            targets.append(
                {
                    "index": entry.index,
                    "title": entry.title,
                    "body": body,
                }
            )
        # Resolve the gateway the same way single-chapter rewrites do.
        try:
            runner = getattr(self, "_fixed_turn_runner", None)
            gateway = (
                runner.gateway
                if runner is not None and getattr(runner, "gateway", None) is not None
                else self._provider_router.resolve(session.provider_profile_id)
            )
        except Exception as exc:  # noqa: BLE001
            self._append_chapter_rewrite_message(session, "模型不可用", str(exc), actions=())
            return
        source = str(getattr(self, "_workbench_source_path", "") or "")
        self._part_polish_state = {
            "part_title": part_title,
            "session_id": session_id,
            "source": source,
            "done": {},
        }
        worker = _PartPolishWorker(
            gateway,
            part_title=part_title,
            targets=targets,
            memory_context=self._part_polish_memory_context(session_id, part_title),
            parent=self,
        )
        self._part_polish_worker = worker
        worker.delta.connect(
            lambda index, delta: self._stream_part_polish_delta(index, delta)
        )
        worker.chapter_finished.connect(
            lambda index, title, text: self._note_part_polish_chapter_done(
                index, title, text
            )
        )
        worker.finished.connect(self._finish_part_polish)
        worker.failed.connect(self._fail_part_polish)
        dock.set_part_busy(part_title, True)
        self._composer.set_busy(True)
        self._append_chapter_rewrite_message(
            session,
            f"正在润色整篇：{part_title}",
            "",
            actions=(),
            progress=True,
        )
        worker.start()

    def _part_polish_memory_context(
        self, session_id: str, part_title: str
    ) -> str:
        """Build a compact whole-part context block: the neighbouring outline
        titles and, when a source docx is bound, the part's parent is implied by
        ``part_title``.  Reuses the single-chapter memory reader scoped to the
        first chapter of the part (index unknown here), falling back to the
        session-level background only."""
        from src.assistant.application.system_memory import SystemMemoryStore

        source = str(getattr(self, "_workbench_source_path", "") or "")
        try:
            base_dir = self._resolve_memory_dir(source_path=source)
        except Exception:  # noqa: BLE001
            base_dir = None
        try:
            memory = SystemMemoryStore(base_dir=base_dir).load(str(session_id or ""))
        except (OSError, ValueError, TypeError):  # noqa: BLE001
            return ""
        brief = str(getattr(memory, "project_brief", "") or "").strip()
        decisions = tuple(getattr(memory, "decisions", ()) or ())
        if not brief and not decisions:
            return ""
        lines: list[str] = []
        if brief:
            lines.append("项目背景：" + brief)
        if decisions:
            lines.append(
                "已确定的关键口径：" + "；".join(str(d) for d in decisions)
            )
        header = f"【系统记忆 · 全局背景（{part_title}）】"
        return "\n".join([header, *lines])

    def _stream_part_polish_delta(self, index: int, delta: str) -> None:
        session = self._active_session
        if session is None:
            return
        self._composer.set_busy(True)
        # Live typing into the workbench editor when it is visible and parked on
        # this chapter: Word-like view.
        bench = getattr(self, "_chapter_workbench", None)
        if (
            bench is not None
            and bench.isVisible()
            and int(getattr(bench, "_current_index", 0) or 0) == int(index)
        ):
            bench.editor.append_raw(str(delta or ""))
        live = getattr(self, "_chapter_live_widget", None)
        if live is not None and hasattr(live, "append_live_delta"):
            live.append_live_delta(
                delta=delta,
                status_text=f"正在润色 · 已写约 {len(str(getattr(live, '_text', ''))) + len(delta)} 字",
            )

    def _note_part_polish_chapter_done(
        self, index: int, _title: str, revised_text: str
    ) -> None:
        """Store a polished chapter's result and refresh the live surfaces."""
        state = getattr(self, "_part_polish_state", None)
        if state is None:
            return
        state["done"][int(index)] = str(revised_text or "")
        session_id = str(state.get("session_id") or "")
        try:
            self._cache.replace_chapter(session_id, int(index), str(revised_text or ""))
            entry = self._cache.update_state(
                session_id, int(index), "done", rescan_score=True
            )
        except (OSError, ValueError, RuntimeError):
            entry = None
        if entry is not None:
            bench = getattr(self, "_chapter_workbench", None)
            if bench is not None:
                bench.navigator.set_state(int(index), entry.state)
                bench.navigator.set_stats(
                    int(index),
                    chars=entry.chars,
                    score=entry.score,
                    grade=entry.grade,
                )
                if (
                    bench.isVisible()
                    and int(getattr(bench, "_current_index", 0) or 0) == int(index)
                ):
                    self._render_workbench_chapter(int(index))
            dock = getattr(self, "_outline_dock", None)
            if dock is not None:
                dock.set_state(int(index), entry.state)
                dock.set_stats(
                    int(index),
                    chars=entry.chars,
                    score=entry.score,
                    grade=entry.grade,
                )
        # Mirror the edited chapter into the right-side editor/bridge so a
        # later whole-document preview reflects the polish.
        marktext_view = getattr(self, "_marktext_view", None)
        if marktext_view is not None:
            marktext_view.bridge.set_chapter_content(int(index), str(revised_text or ""))

    def _finish_part_polish(self) -> None:
        """All chapters of the part polished: write a cumulative .docx copy when
        a source document is bound, then report completion."""
        session = self._active_session
        state = getattr(self, "_part_polish_state", None)
        if session is None or state is None:
            self._reset_part_polish_busy()
            return
        done = state.get("done") or {}
        source = str(state.get("source") or "")
        dock = getattr(self, "_outline_dock", None)
        written_path = ""
        if source and Path(source).is_file() and done:
            try:
                written_path = _apply_part_polish_docx(source, done)
            except Exception as exc:  # noqa: BLE001
                self._append_chapter_rewrite_message(
                    session, "整篇润色落盘失败", str(exc), actions=()
                )
        body = (
            f"已润色《{state.get('part_title')}》下 {len(done)} 章，各章标题与排版保持不变。"
            if len(done)
            else "润色完成，但没有章节产生改写结果。"
        )
        if written_path:
            body += f"\n润色结果已另存（未覆盖原文件）：\n{written_path}"
        else:
            body += "\n润色结果已写入当前工作台缓存；需要时再导出为 DOCX。"
        self._append_chapter_rewrite_message(
            session,
            "整篇润色完成",
            body,
            actions=(),
            reference=(
                {
                    "type": "file",
                    "title": Path(written_path).name,
                    "path": written_path,
                }
                if written_path
                else None
            ),
        )
        if dock is not None:
            dock.set_part_busy(str(state.get("part_title") or ""), False)
        self._composer.set_busy(False)
        self._part_polish_state = None
        self._part_polish_worker = None

    def _fail_part_polish(self, error: str) -> None:
        state = getattr(self, "_part_polish_state", None)
        dock = getattr(self, "_outline_dock", None)
        try:
            session = self._active_session
        except (OSError, ValueError, TypeError):
            session = None
        if session is not None:
            self._append_chapter_rewrite_message(
                session,
                "整篇润色中断",
                f"已保留润色成功的章节；中断原因：\n{error}",
                actions=(),
            )
        if dock is not None and state is not None:
            dock.set_part_busy(str(state.get("part_title") or ""), False)
        self._composer.set_busy(False)
        self._part_polish_state = None
        self._part_polish_worker = None

    def _reset_part_polish_busy(self) -> None:
        dock = getattr(self, "_outline_dock", None)
        state = getattr(self, "_part_polish_state", None)
        if dock is not None and state is not None:
            dock.set_part_busy(str(state.get("part_title") or ""), False)
        self._composer.set_busy(False)
        self._part_polish_state = None
        self._part_polish_worker = None

    def _part_polish_worker_shutdown(self, timeout_ms: int = 5000) -> bool:
        worker = getattr(self, "_part_polish_worker", None)
        if worker is None:
            return True
        return worker.shutdown(timeout_ms)


class _PartPolishWorker(QObject):
    """Background worker that polishes every chapter under one 篇/部分 in a
    sequential pass.

    Each chapter is a separate model call (so each rewritten body can be
    written back reliably) whose prompt includes the full part context (all
    chapter titles of the part + the part name) plus any persisted system
    memory.  Signals carry the chapter index with every streamed delta and each
    finished body so the panel can update the dock/workbench live.
    """

    delta = Signal(int, str)  # (index, text_delta)
    chapter_finished = Signal(int, str, str)  # (index, title, revised_text)
    finished = Signal()
    failed = Signal(str)

    def __init__(
        self,
        gateway,
        *,
        part_title: str,
        targets: list[dict[str, object]],
        memory_context: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._gateway = gateway
        self._part_title = str(part_title or "")
        self._targets = list(targets or [])
        self._memory_context = str(memory_context or "")
        self._cancellation = AssistantCancellationToken()
        self._thread = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        from threading import Thread

        if self.is_running:
            raise RuntimeError("Part polish worker already running")
        self._thread = Thread(target=self._run, name="part-polish", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancellation.cancel()

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        self.cancel()
        thread = self._thread
        if thread is None:
            return True
        thread.join(max(0, timeout_ms) / 1000)
        return not thread.is_alive()

    def _run(self) -> None:
        try:
            for target in self._targets:
                if self._cancellation.cancelled():
                    raise RuntimeError("part_polish_cancelled")
                index = int(target.get("index") or 0)
                title = str(target.get("title") or "")
                body = str(target.get("body") or "")
                text = self._rewrite_one(index, title, body)
                if not str(text or "").strip():
                    raise RuntimeError("part_polish_empty_chapter")
                self.chapter_finished.emit(index, title, text)
            self.finished.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or type(exc).__name__)

    def _rewrite_one(self, index: int, title: str, body: str) -> str:
        outline_lines = []
        for target in self._targets:
            outline_lines.append(f"- {target.get('title')}")
        part_heading = f"篇《{self._part_title}》"
        prompt = (
            f"整篇润色范围：{part_heading}\n"
            f"该篇各章标题（保持这些标题不变）：\n"
            + "\n".join(outline_lines)
            + (("\n\n" + self._memory_context) if self._memory_context else "")
            + f"\n\n现在润色第 {index} 章《{title}》：\n【该章现有正文】\n{body}\n\n"
            "请只返回润色后这一章的正文：在保留原结构、要点与编号（如 1.1/1.2）的"
            "前提下，让行文更专业、精炼、通顺。不要输出章标题、前言或其它章节；"
            "不要伪造事实，缺失处用“待补充”占位。"
        )
        from src.assistant.runtime.provider_contract import ProviderRequest

        request = ProviderRequest(
            request_id=uuid4().hex,
            model=getattr(self._gateway, "model", "") or "assistant",
            system_prompt=(
                "你是 LDWord 文档整篇润色助手。用户让你润色某个 篇/部分 下的一章，"
                "你在该篇整体语境里只改写当前这一章正文并保持其标题、结构和小节编号。"
            ),
            messages=(
                {
                    "role": "user",
                    "content": prompt,
                },
            ),
            metadata={"purpose": "part_polish", "chapter_index": index},
        )
        parts: list[str] = []
        for event in self._gateway.stream(request):
            if self._cancellation.cancelled():
                raise RuntimeError("part_polish_cancelled")
            if event.type == "text_delta":
                parts.append(event.text)
                self.delta.emit(index, event.text)
            elif event.type == "error":
                raise RuntimeError(event.text or "part_polish_provider_failed")
        return "".join(parts).strip()


def _apply_part_polish_docx(source: str, done: dict[int, str]) -> str:
    """Apply every polished chapter onto a running copy of *source*, so
    headings + layout are preserved, and return the output path.

    Chapters are applied in ascending index order; each edit sources from the
    current cumulative file and writes to the same ``<stem>.润色篇.docx``
    target.  Chapter indices stay stable across edits because
    :func:`apply_chapter_edit` only replaces body paragraphs (never adding or
    removing heading paragraphs).
    """
    src = Path(str(source or "")).expanduser()
    out = src.with_name(f"{src.stem}.润色篇.docx")
    current = src
    for index in sorted(int(i) for i in (done or {})):
        revised = done[int(index)]
        receipt = apply_chapter_edit(
            current,
            ChapterEditRequest(
                chapter_index=int(index),
                revised_markdown=str(revised or ""),
            ),
            output_path=out,
        )
        current = Path(receipt.output_path)
    return str(out)


__all__ = ["AssistantChapterRewriteMixin"]
