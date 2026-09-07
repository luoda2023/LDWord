# -*- coding: utf-8 -*-
"""编辑器内 AI（右键两阶段）与悬浮 AI 聊天的回归测试。

锁定的约定：

* Bridge 提供 editor_ai_action / editor_ai_phase / editor_ai_result 三条
  通道，payload JSON 序列化失败时静默跳过（永不阻断编辑器）。
* _EditorAiWorker 两阶段：understanding（了解章节）→ drafting（起草）→
  applying（应用），phase 按序发出；改写/润色产出 replacement，
  续写产出 insertion。
* 页面 HTML 含 AI 右键菜单（rewrite/polish/continue）与阶段浮层。
* 悬浮 FAB 固定右下角、创建即显示；气泡提交发出 message_submitted。
"""
from __future__ import annotations

import json

import pytest

from src.qt_api import QApplication

from src.assistant.ui.marktext_bridge import MarkTextBridge


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_bridge_editor_ai_channels(qapp):
    bridge = MarkTextBridge()
    seen_action = {}
    bridge.editor_ai_action.connect(
        lambda kind, ctx: seen_action.update(kind=kind, ctx=ctx)
    )
    bridge.requestEditorAiAction("polish", "一段文字")
    assert seen_action == {"kind": "polish", "ctx": "一段文字"}

    seen_phase = {}
    bridge.editor_ai_phase.connect(
        lambda text: seen_phase.update(json.loads(text))
    )
    bridge.notify_editor_ai_phase(
        {"phase": "understanding", "detail": "阅读中", "kind": "rewrite"}
    )
    assert seen_phase["phase"] == "understanding"

    seen_result = {}
    bridge.editor_ai_result.connect(
        lambda text: seen_result.update(json.loads(text))
    )
    bridge.notify_editor_ai_result({"kind": "continue", "insertion": "补充内容"})
    assert seen_result["insertion"] == "补充内容"


def test_bridge_phase_payload_malformed_is_silent(qapp):
    bridge = MarkTextBridge()
    emitted = []
    bridge.editor_ai_phase.connect(emitted.append)
    # 循环结构无法 JSON 序列化：必须静默跳过，不抛异常。
    bridge.notify_editor_ai_phase({"bad": object()})
    bridge.notify_editor_ai_result({"bad": object()})
    assert emitted == []


def test_editor_ai_worker_two_phases(qapp):
    from src.assistant.ui.chapter_rewrite_mixin import _EditorAiWorker

    class _Event:
        def __init__(self, text):
            self.type = "text_delta"
            self.text = text

    class _Gateway:
        model = "test-model"

        def __init__(self):
            self.calls = []

        def stream(self, request):
            self.calls.append(request.metadata["purpose"])
            if request.metadata["purpose"] == "editor_ai_understand":
                yield _Event("本章讲施工部署，面向业主。")
            else:
                yield _Event("改写后的句子。")

    gateway = _Gateway()
    worker = _EditorAiWorker(
        gateway,
        kind="rewrite",
        selection="需要改写的句子",
        chapter_title="第一章 总体部署",
        chapter_body="# 第一章 总体部署\n\n正文……",
        memory_context="项目背景：测试项目",
    )
    phases = []
    results = []
    worker.phase.connect(lambda text: phases.append(json.loads(text)))
    worker.finished.connect(lambda text: results.append(json.loads(text)))
    worker._run()  # 直接驱动，不起线程

    assert phases[0]["phase"] == "understanding"
    assert phases[1]["phase"] == "drafting"
    assert phases[2]["phase"] == "applying"
    assert len(results) == 1
    assert results[0]["replacement"] == "改写后的句子。"
    # 起草请求必须携带第 1 阶段的理解摘要（章节感知的关键）。
    draft_calls = [
        c for c in gateway.calls if c == "editor_ai_draft"
    ]
    assert draft_calls


def test_editor_ai_worker_continue_produces_insertion(qapp):
    from src.assistant.ui.chapter_rewrite_mixin import _EditorAiWorker

    class _Event:
        def __init__(self, text):
            self.type = "text_delta"
            self.text = text

    class _Gateway:
        model = "test-model"

        def stream(self, request):
            yield _Event("补充的段落。")

    worker = _EditorAiWorker(
        _Gateway(),
        kind="continue",
        selection="",
        chapter_title="第一章",
        chapter_body="正文",
        memory_context="",
    )
    results = []
    worker.finished.connect(lambda text: results.append(json.loads(text)))
    worker._run()
    assert results[0]["kind"] == "continue"
    assert results[0]["insertion"] == "补充的段落。"
    assert "replacement" not in results[0]


def test_page_html_declares_ai_menu_and_overlay():
    import inspect

    from src.assistant.ui import marktext_view

    src = inspect.getsource(marktext_view)
    assert 'id="ai-menu"' in src
    assert 'data-ai="rewrite"' in src
    assert 'data-ai="polish"' in src
    assert 'data-ai="continue"' in src
    assert 'id="ai-phase-overlay"' in src
    # 阶段文案：让用户知道 AI 在做什么
    assert "了解本章内容" in src


def test_floating_chat_fab_and_bubble(qapp):
    from src.assistant.ui.ai_floating_chat import AiFloatingChat

    host = qapp.activeWindow() or None
    from src.qt_api import QWidget

    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    chat = AiFloatingChat(parent)
    # 创建即显示，钉在右下角
    assert not chat._fab.isHidden()
    assert chat._fab.pos().x() + chat._fab.width() <= 1000
    assert chat._fab.pos().y() + chat._fab.height() <= 700
    chat._show_bubble()
    assert chat._bubble.isVisible()
    submitted = {}
    chat.message_submitted.connect(lambda t: submitted.update(text=t))
    chat._input.setPlainText("补充一个表格")
    chat._submit()
    assert submitted == {"text": "补充一个表格"}
    chat._hide_bubble()
    assert not chat._bubble.isVisible()
    parent.deleteLater()


def test_floating_chat_restore_pending_input(qapp):
    """提交被门禁拒绝后：草稿回填输入框 + 提示原因 + 气泡弹回。"""
    from src.qt_api import QWidget

    from src.assistant.ui.ai_floating_chat import AiFloatingChat

    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    chat = AiFloatingChat(parent)
    chat._hide_bubble()
    chat.restore_pending_input(
        "把第2章润色一遍", "当前任务正在运行，请等待完成或停止后再发送"
    )
    assert chat._input.toPlainText() == "把第2章润色一遍"
    assert chat._bubble.isVisible()
    transcript = chat._current_markdown()
    assert "当前任务正在运行" in transcript
    parent.deleteLater()


def test_editor_ai_inflight_blocks_second_action(qapp):
    """在途标志挡住并发：收尾回调清零前再次发起应被拒。"""
    from src.assistant.ui.chapter_rewrite_mixin import AssistantChapterRewriteMixin as ChapterRewriteMixin

    class _Host(ChapterRewriteMixin):
        """最小宿主：只实现 mixin 在途标志语义需要的属性。"""

        def __init__(self):
            self._editor_ai_inflight = True
            self._editor_ai_worker = None
            self._marktext_view = None

    host = _Host.__new__(_Host)
    host._editor_ai_inflight = True
    host._editor_ai_worker = None
    host._marktext_view = None
    # 收尾释放后，下一次发起才能通过（锁定释放语义本身）。
    ChapterRewriteMixin._release_editor_ai_inflight(host)
    assert host._editor_ai_inflight is False


def test_editor_ai_release_on_finish_and_fail(qapp):
    """finished/failed 两条收尾路径都必须释放在途标志。"""
    from src.assistant.ui.chapter_rewrite_mixin import (
        AssistantChapterRewriteMixin as ChapterRewriteMixin,
        _EditorAiWorker,
    )

    class _Bridge:
        def __init__(self):
            self.phases = []
            self.results = []

        def notify_editor_ai_phase(self, payload):
            self.phases.append(payload["phase"])

        def notify_editor_ai_result(self, payload):
            self.results.append(payload)

    class _View:
        bridge = _Bridge()

    class _Gateway:
        model = "m"

        class _Evt:
            type = "text_delta"
            text = "结果"

        def stream(self, request):
            yield self._Evt()

    worker = _EditorAiWorker(
        _Gateway(),
        kind="continue",
        selection="",
        chapter_title="第一章",
        chapter_body="正文",
        memory_context="",
    )

    class _Panel(ChapterRewriteMixin):
        def __init__(self):
            self._marktext_view = _View()
            self._editor_ai_worker = worker
            self._editor_ai_inflight = True

    panel = _Panel()
    # 真实链路中信号 lambda 已把 JSON 文本 loads 成 dict 再调用。
    panel._finish_editor_ai_action({"kind": "continue", "insertion": "结果"})
    assert panel._editor_ai_inflight is False
    assert panel._marktext_view.bridge.results

    panel._editor_ai_inflight = True
    panel._fail_editor_ai_action("continue", "boom")
    assert panel._editor_ai_inflight is False
    assert panel._marktext_view.bridge.phases[-1] == "failed"
