"""Design-style active conversation surfaces for the document assistant."""

from __future__ import annotations

from pathlib import Path

from src.assistant.ui.conversation_presentation import project_file_references
from src.assistant.ui.message_body_renderer import AssistantMessageBodyRenderer
from src.assistant.ui.message_components import AssistantAttachmentStrip
from src.qt_api import (
    QApplication,
    QColor,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPainter,
    QPen,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


_USER_BUBBLE_HORIZONTAL_MARGIN = 13
_USER_BUBBLE_BORDER_WIDTH = 1
_MESSAGE_SIDE_MARGIN = 16
# 阅读列最宽不超过所在视口宽度的 3/4；低于 3/4 视口很窄时退化为整行减去
# 两侧边距，避免消息被挤压到无法阅读。AI/系统消息贴左缘、用户消息贴右缘，
# 双方共用同一条 3/4 阅读宽度，不再整体居中留下双侧大空白。
_READING_WIDTH_RATIO = 0.75
_READING_MIN_COLUMN = 420


class AssistantConversationSurface(QWidget):
    """First-level conversation canvas retaining the creative-home identity."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("assistant_active_page")
        self.setAttribute(Qt.WA_StyledBackground, True)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        theme = get_theme()
        color = QColor(theme.border_light)
        color.setAlpha(42)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QPen(color, 1))
        spacing = 42
        height = self.height()
        width = self.width()
        vertical_shift = int(height * 0.12)
        for x in range(-vertical_shift, width + spacing, spacing):
            painter.drawLine(x, 0, x + vertical_shift, height)
        horizontal_shift = int(width * 0.05)
        for y in range(-spacing, height + spacing, spacing):
            painter.drawLine(0, y, width, y - horizontal_shift)
        painter.end()


_AutoHeightMarkdown = AssistantMessageBodyRenderer


def _source_title(source: dict[str, object]) -> str:
    title = str(source.get("title") or source.get("name") or "").strip()
    if title:
        return title
    path = str(
        source.get("path") or source.get("file_path") or source.get("local_path") or ""
    ).strip()
    if path:
        return Path(path).name or path
    return str(source.get("url") or source.get("href") or "来源").strip() or "来源"


class AssistantSourceStrip(QWidget):
    """Compact, actionable projection of source and attachment references."""

    source_requested = Signal(object)

    def __init__(
        self,
        sources: tuple[dict[str, object], ...],
        *,
        label: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("assistant_source_strip")
        self._sources = tuple(dict(item) for item in sources)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(5)
        self._label = QLabel(f"{label} · {len(self._sources)}", self)
        self._label.setObjectName("assistant_source_label")
        row.addWidget(self._label)
        self._buttons: list[QToolButton] = []
        for source in self._sources[:3]:
            button = self._source_button(source)
            row.addWidget(button)
            self._buttons.append(button)
        if len(self._sources) > 3:
            more = QToolButton(self)
            more.setObjectName("assistant_source_more")
            more.setText(f"+{len(self._sources) - 3}")
            more.setCursor(Qt.PointingHandCursor)
            more.setPopupMode(QToolButton.InstantPopup)
            menu = QMenu(more)
            for source in self._sources[3:]:
                action = menu.addAction(_source_title(source))
                action.triggered.connect(
                    lambda _checked=False, ref=dict(source): self.source_requested.emit(
                        ref
                    )
                )
            more.setMenu(menu)
            row.addWidget(more)
            self._buttons.append(more)
        row.addStretch(1)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _source_button(self, source: dict[str, object]) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("assistant_source_chip")
        button.setText(_source_title(source))
        button.setToolTip(_source_title(source))
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(
            lambda _checked=False, ref=dict(source): self.source_requested.emit(ref)
        )
        return button

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#assistant_source_strip {{ background: transparent; border: none; }}
            QLabel#assistant_source_label {{
                color: {theme.text_hint}; background: transparent;
                font-size: {theme.font_size_sm}px;
            }}
            QToolButton#assistant_source_chip,
            QToolButton#assistant_source_more {{
                color: {theme.text_secondary}; background: transparent;
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px; padding: 2px 6px;
                font-size: {theme.font_size_sm}px;
            }}
            QToolButton#assistant_source_chip:hover,
            QToolButton#assistant_source_more:hover {{
                color: {theme.primary}; background: {theme.bg_hover};
                border-color: {theme.primary};
            }}
            """
        )


class AssistantConversationMessage(QWidget):
    """Role-aware message row for LDWord conversation geometry."""

    source_requested = Signal(object)
    link_requested = Signal(str)
    action_requested = Signal(str, str)

    def __init__(
        self,
        *,
        text: str,
        role: str,
        message_id: str = "",
        source_refs: tuple[dict[str, object], ...] = (),
        live: bool = False,
        status_text: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._role = str(role or "assistant")
        self._text = str(text or "")
        self._message_id = str(message_id or "")
        self._source_refs = tuple(source_refs or ())
        self._live = bool(live)
        self.setObjectName("assistant_conversation_message")
        self.setProperty("role", self._role)
        self.setAttribute(Qt.WA_StyledBackground, True)
        # The reading row is fluid. Ignoring its desktop-oriented size hint lets
        # the scroll-area viewport contract the row and reflow its contents in
        # compact mode instead of creating a horizontal document canvas.
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 12, 0, 12)
        outer.setSpacing(0)
        self._column = QWidget(self)
        self._column.setObjectName("assistant_message_column")
        self._column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        if self._role == "user":
            # 我方消息贴右缘：左侧弹性区吸收剩余宽度，内容从右侧铺开
            outer.addStretch(1)
            outer.addWidget(self._column)
        else:
            # AI/系统消息贴左缘：内容从左侧铺开，右侧为呼吸区
            outer.addWidget(self._column)
            outer.addStretch(1)

        if self._role == "user":
            self._build_user_message()
        else:
            self._build_assistant_message(status_text)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        row_width = max(0, event.size().width())
        # AI/系统消息贴左缘、用户消息贴右缘，阅读内容最宽统一为视口宽度的
        # 3/4；两侧只保留 16px 呼吸边距，不再整体居中造成大段左右留白。
        if row_width <= 0:
            return
        edge_gap = _MESSAGE_SIDE_MARGIN
        # 阅读列最宽 = 视口宽度的 3/4（不再受 860 硬顶截断，宽屏下继续铺开）。
        # 窄视口低于 3/4 时退化为整行，保证可读性。
        ratio_cap = max(
            _READING_MIN_COLUMN,
            int((row_width - edge_gap) * _READING_WIDTH_RATIO),
        )
        column_width = min(ratio_cap, row_width)
        self._column.setFixedWidth(column_width)
        outer = self.layout()
        if isinstance(outer, QHBoxLayout):
            if self._role == "user":
                outer.setContentsMargins(0, 12, edge_gap, 12)
            else:
                outer.setContentsMargins(edge_gap, 12, 0, 12)
        if not hasattr(self, "_column_layout"):
            return
        if self._role == "user":
            # 用户气泡在列内右对齐，气泡宽度自适应文本（至多铺满阅读列）。
            self._column_layout.setContentsMargins(0, 0, 0, 0)
            self._sync_user_bubble_width(column_width)
        else:
            # AI 文本块顶满整个阅读列，随列宽动态铺开（3/4 视口）。
            self._column_layout.setContentsMargins(0, 0, 0, 0)
            if self._assistant_body.width() != column_width:
                self._assistant_body.setFixedWidth(column_width)

    def _sync_user_bubble_width(self, available_width: int) -> None:
        """Keep user text compact without trusting QLabel's wrapped size hint."""

        if not hasattr(self, "_bubble"):
            return
        lines = self._text.splitlines() or [""]
        metrics = self._body_label.fontMetrics()
        natural_text_width = max(metrics.horizontalAdvance(line) for line in lines)
        horizontal_chrome = 2 * (
            _USER_BUBBLE_HORIZONTAL_MARGIN + _USER_BUBBLE_BORDER_WIDTH
        )
        preferred_width = min(
            int(available_width),
            natural_text_width + horizontal_chrome,
        )
        target_width = max(0, preferred_width)
        if self._bubble.width() == target_width:
            return
        self._bubble.setFixedWidth(target_width)
        self._bubble.updateGeometry()

    def _build_user_message(self) -> None:
        layout = QVBoxLayout(self._column)
        self._column_layout = layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        files = project_file_references(self._source_refs)
        if files:
            attachment_row = QHBoxLayout()
            attachment_row.setContentsMargins(0, 0, 0, 0)
            attachment_row.setSpacing(0)
            attachment_row.addStretch(1)
            self._attachment_strip = AssistantAttachmentStrip(
                files,
                parent=self._column,
            )
            self._attachment_strip.reference_requested.connect(
                self.source_requested.emit
            )
            attachment_row.addWidget(self._attachment_strip)
            layout.addLayout(attachment_row)
        bubble_row = QHBoxLayout()
        bubble_row.setContentsMargins(0, 0, 0, 0)
        bubble_row.setSpacing(0)
        bubble_row.addStretch(1)
        self._bubble = QFrame(self._column)
        self._bubble.setObjectName("assistant_user_bubble")
        # 最大宽度由 resizeEvent 随“视口 3/4 阅读列”动态 clamp，不在构造期
        # 用 820 之类硬顶截断宽屏下的铺开空间。
        self._bubble.setMaximumWidth(1 << 20)
        self._bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        bubble_layout = QVBoxLayout(self._bubble)
        bubble_layout.setContentsMargins(
            _USER_BUBBLE_HORIZONTAL_MARGIN,
            8,
            _USER_BUBBLE_HORIZONTAL_MARGIN,
            8,
        )
        bubble_layout.setSpacing(0)
        self._body_label = QLabel(self._text, self._bubble)
        self._body_label.setObjectName("assistant_user_text")
        self._body_label.setTextFormat(Qt.PlainText)
        self._body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._body_label.setWordWrap(True)
        self._body_label.setMaximumWidth(1 << 20)
        bubble_layout.addWidget(self._body_label)
        bubble_row.addWidget(self._bubble)
        layout.addLayout(bubble_row)

    def _build_assistant_message(self, status_text: str) -> None:
        layout = QVBoxLayout(self._column)
        self._column_layout = layout
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(8)
        self._assistant_body = QWidget(self._column)
        self._assistant_body.setObjectName("assistant_response_body")
        # 动态宽度由 resizeEvent 统一 clamp 到“视口 3/4 阅读列”。
        self._assistant_body.setMaximumWidth(1 << 20)
        body_layout = QVBoxLayout(self._assistant_body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        self._status_row = QWidget(self._assistant_body)
        self._status_row.setObjectName("assistant_live_status")
        status_layout = QHBoxLayout(self._status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(7)
        self._status_icon = QLabel(self._status_row)
        self._status_icon.setObjectName("assistant_live_status_icon")
        self._status_icon.setFixedSize(18, 18)
        self._status_label = QLabel(status_text, self._status_row)
        self._status_label.setObjectName("assistant_live_status_text")
        status_layout.addWidget(self._status_icon)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch(1)
        self._status_row.setVisible(self._live or bool(status_text))
        body_layout.addWidget(self._status_row)

        self._markdown = _AutoHeightMarkdown(self._assistant_body)
        if self._live:
            self._markdown.set_live_text(self._text)
        else:
            self._markdown.set_markdown(self._text)
        self._markdown.link_requested.connect(self.link_requested.emit)
        self._markdown.setVisible(bool(self._text))
        body_layout.addWidget(self._markdown)

        if self._source_refs:
            self._source_strip = AssistantSourceStrip(
                self._source_refs,
                label="来源",
                parent=self._assistant_body,
            )
            self._source_strip.source_requested.connect(self.source_requested.emit)
            body_layout.addWidget(self._source_strip)

        self._footer = QWidget(self._assistant_body)
        self._footer.setObjectName("assistant_message_footer")
        footer = QHBoxLayout(self._footer)
        footer.setContentsMargins(0, 1, 0, 0)
        footer.setSpacing(6)
        self._copy_button = QToolButton(self._footer)
        self._copy_button.setObjectName("assistant_message_copy")
        self._copy_button.setText("复制")
        self._copy_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._copy_button.setCursor(Qt.PointingHandCursor)
        self._copy_button.setAccessibleName("复制回复")
        self._copy_button.clicked.connect(self._copy_text)
        footer.addWidget(self._copy_button)
        self._quote_button = QToolButton(self._footer)
        self._quote_button.setObjectName("assistant_message_quote")
        self._quote_button.setText("引用")
        self._quote_button.setCursor(Qt.PointingHandCursor)
        self._quote_button.setAccessibleName("引用回复")
        self._quote_button.clicked.connect(
            lambda: self.action_requested.emit("quote", self._message_id)
        )
        footer.addWidget(self._quote_button)
        self._retry_button = QToolButton(self._footer)
        self._retry_button.setObjectName("assistant_message_retry")
        self._retry_button.setText("重试")
        self._retry_button.setCursor(Qt.PointingHandCursor)
        self._retry_button.setAccessibleName("从此处重试")
        self._retry_button.clicked.connect(
            lambda: self.action_requested.emit("retry", self._message_id)
        )
        footer.addWidget(self._retry_button)
        footer.addStretch(1)
        self._footer.setVisible(not self._live and bool(self._text))
        body_layout.addWidget(self._footer)
        layout.addWidget(self._assistant_body)

    def set_live_state(self, *, text: str, status_text: str) -> None:
        if self._role == "user":
            return
        new_text = str(text or "")
        previous = self._text
        if new_text.startswith(previous):
            self.append_live_delta(
                delta=new_text[len(previous) :],
                status_text=status_text,
            )
            return
        self._live = True
        self._text = new_text
        self._status_label.setText(str(status_text or "正在处理"))
        self._status_row.show()
        self._markdown.set_live_text(new_text)
        self._markdown.setVisible(bool(self._text))
        self._footer.hide()

    def append_live_delta(self, *, delta: str, status_text: str) -> None:
        if self._role == "user":
            return
        appended = str(delta or "")
        self._live = True
        if appended:
            self._text += appended
        status = str(status_text or "正在处理")
        if self._status_label.text() != status:
            self._status_label.setText(status)
        self._status_row.show()
        if appended:
            self._markdown.append_live_text(appended)
        self._markdown.setVisible(bool(self._text))
        self._footer.hide()

    def _copy_text(self) -> None:
        QApplication.clipboard().setText(self._text)
        self._copy_button.setText("已复制")

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#assistant_conversation_message,
            QWidget#assistant_message_column,
            QWidget#assistant_response_body,
            QWidget#assistant_live_status,
            QWidget#assistant_message_footer {{
                background: transparent;
                border: none;
            }}
            QFrame#assistant_user_bubble {{
                color: {theme.text_primary};
                background: {theme.bg_selected};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            QLabel#assistant_user_text {{
                color: {theme.text_primary};
                background: transparent;
                font-size: {theme.font_size_md}px;
            }}
            QTextEdit#assistant_message_markdown {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
                padding: 0;
                font-size: 14px;
                selection-background-color: {theme.primary_light};
            }}
            QLabel#assistant_live_status_text {{
                color: {theme.text_secondary};
                background: transparent;
                font-size: {theme.font_size_sm}px;
            }}
            QToolButton#assistant_message_copy,
            QToolButton#assistant_message_quote,
            QToolButton#assistant_message_retry {{
                color: {theme.text_secondary};
                background: transparent;
                border: 1px solid transparent;
                border-radius: {theme.radius_sm}px;
                padding: 3px 6px;
            }}
            QToolButton#assistant_message_copy:hover,
            QToolButton#assistant_message_quote:hover,
            QToolButton#assistant_message_retry:hover {{
                color: {theme.text_primary};
                background: {theme.bg_hover};
                border-color: {theme.border_light};
            }}
            """
        )
        if self._role != "user":
            self._markdown.apply_semantic_theme()
            self._status_icon.setPixmap(
                get_icon("sparkles", 16, theme.primary).pixmap(16, 16)
            )
            self._copy_button.setIcon(get_icon("copy", 14, theme.icon_secondary))


__all__ = [
    "AssistantConversationMessage",
    "AssistantConversationSurface",
    "AssistantSourceStrip",
]
