# -*- coding: utf-8 -*-
"""右下角 AI 悬浮聊天（Floating AI chat）。

MarkText 视图打开时，右下角出现一个 AI 悬浮图标；点击弹出富文本悬浮对话框。
对话框内消息与回复都以 Markdown 富文本渲染（标题、表格、列表、代码），
输入后直接走主会话链路（_send_message），因此逐章流式写作、确认卡、
一条龙生成 Word 等全部能力在悬浮窗里同样可用。

设计要点：
* 图标常驻（视图可见即显示），不遮挡编辑器正文；
* 对话框可拖动、可收起回图标，生命周期跟随宿主视图；
* 回复区复用 AssistantMessageBodyRenderer 的实时 Markdown 渲染
  （表格逐行成型），与对话区观感一致。
"""
from __future__ import annotations

from src.qt_api import (
    QEvent,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPoint,
    QPushButton,
    Qt,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Signal,
)


class AiFloatingChat(QWidget):
    """悬浮 AI 图标 + 富文本对话气泡（宿主为 MarkText 视图）。"""

    message_submitted = Signal(str)

    _BUBBLE_WIDTH = 380
    _BUBBLE_HEIGHT = 320

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._drag_offset = QPoint()
        self._dragging = False

        # ---- 悬浮图标 ----------------------------------------------------
        self._fab = QPushButton("AI", parent)
        self._fab.setObjectName("ai_fab_button")
        self._fab.setFixedSize(44, 44)
        self._fab.setCursor(Qt.PointingHandCursor)
        self._fab.setToolTip("唤出 AI 助手：可以直接下达写作、修改、排版指令")
        self._fab.clicked.connect(self._toggle_bubble)
        self._fab.show()
        self._position_fab()

        # ---- 悬浮对话框 ----------------------------------------------------
        self._bubble = QFrame(parent)
        self._bubble.setObjectName("ai_floating_chat")
        self._bubble.setFixedSize(self._BUBBLE_WIDTH, self._BUBBLE_HEIGHT)
        self._bubble.hide()
        self._build_bubble()

    # ---- construction ------------------------------------------------------
    def _build_bubble(self) -> None:
        from src.assistant.ui.message_body_renderer import (
            AssistantMessageBodyRenderer,
        )

        layout = QVBoxLayout(self._bubble)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("AI 助手")
        title.setObjectName("ai_floating_title")
        header.addWidget(title)
        header.addStretch(1)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("收起（回到右下角图标）")
        close_btn.clicked.connect(self._hide_bubble)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # 复用对话区的 Markdown 渲染器：表格逐行成型、语义主题一致。
        self._transcript = AssistantMessageBodyRenderer(self._bubble)
        self._transcript.set_markdown(
            "我是你的 AI 助手，可以在这里直接指挥我：\n\n"
            "- 「把第 2 章再润色一遍」\n"
            "- 「给本章补一个参数表」\n"
            "- 「按公文模板重新排版」"
        )
        layout.addWidget(self._transcript, 1)

        self._input = QTextEdit()
        self._input.setObjectName("ai_floating_input")
        self._input.setPlaceholderText(
            "输入指令，Enter 发送（Shift+Enter 换行）"
        )
        self._input.setFixedHeight(64)
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

    # ---- positioning / drag ------------------------------------------------
    def _position_fab(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        self._fab.move(
            parent.width() - self._fab.width() - 16,
            parent.height() - self._fab.height() - 16,
        )
        self._fab.raise_()

    def reposition(self) -> None:
        """Host resized: keep the FAB pinned to the bottom-right corner."""
        self._position_fab()
        if self._bubble.isVisible():
            self._keep_bubble_inside()

    def _keep_bubble_inside(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        pos = self._bubble.pos()
        x = max(8, min(pos.x(), parent.width() - self._bubble.width() - 8))
        y = max(8, min(pos.y(), parent.height() - self._bubble.height() - 8))
        self._bubble.move(x, y)

    def _toggle_bubble(self) -> None:
        if self._bubble.isVisible():
            self._hide_bubble()
        else:
            self._show_bubble()

    def _show_bubble(self) -> None:
        parent = self.parent()
        if parent is not None:
            self._bubble.move(
                parent.width() - self._bubble.width() - 16,
                parent.height() - self._bubble.height() - 70,
            )
        self._bubble.show()
        self._bubble.raise_()
        self._input.setFocus()

    def _hide_bubble(self) -> None:
        self._bubble.hide()

    # ---- events ------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
                event.modifiers() & Qt.ShiftModifier
            ):
                self._submit()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._bubble.pos()
            self._dragging = self._bubble.isVisible()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging and self._bubble.isVisible():
            self._bubble.move(
                event.globalPosition().toPoint() - self._drag_offset
            )
            self._keep_bubble_inside()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        super().mouseReleaseEvent(event)

    # ---- messaging ---------------------------------------------------------
    def _submit(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self._append_user(text)
        self.message_submitted.emit(text)

    def _append_user(self, text: str) -> None:
        self._transcript.append_live_text("")
        self._transcript.set_markdown(
            self._current_markdown() + f"\n\n**你：** {text}\n"
        )

    def restore_pending_input(self, text: str, reason: str = "") -> None:
        """Submission rejected by the shell gate: restore the draft + say why.

        提交被拒（如逐章写作运行中）时回填输入框并浮出提示，用户输入
        不丢失，也不需要重新打字。
        """
        if str(text or "").strip():
            self._input.setPlainText(str(text or ""))
            cursor = self._input.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self._input.setTextCursor(cursor)
        if str(reason or "").strip():
            self._transcript.set_markdown(
                self._current_markdown() + f"\n> ⚠ {str(reason).strip()}\n"
            )
        self._show_bubble()

    def append_assistant_markdown(self, text: str) -> None:
        """Public hook: stream assistant replies into the floating bubble."""
        self._transcript.set_markdown(self._current_markdown() + f"\n{text}\n")

    def _current_markdown(self) -> str:
        return self._transcript._source_text if hasattr(
            self._transcript, "_source_text"
        ) else ""
