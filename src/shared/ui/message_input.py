"""MessageInput — 消息输入控件"""

from __future__ import annotations

from src.qt_api import (
    QEvent,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme


class MessageInput(QWidget):
    """消息输入控件，支持多行输入和发送按钮。

    用法::

        # 基础用法
        input_widget = MessageInput(placeholder="输入消息...")
        input_widget.message_sent.connect(lambda msg: print(f"发送: {msg}"))

        # 自定义按钮文字
        input_widget = MessageInput(
            placeholder="输入消息...",
            send_button_text="发送"
        )
    """

    message_sent = Signal(str)  # 消息发送信号

    def __init__(
        self,
        *,
        placeholder: str = "",
        send_button_text: str = "发送",
        parent=None,
    ):
        """初始化消息输入控件。

        Args:
            placeholder: 占位符文字
            send_button_text: 发送按钮文字
            parent: 父控件
        """
        super().__init__(parent)
        self._placeholder = placeholder
        self._send_button_text = send_button_text

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 文本输入框
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(self._placeholder)
        self._text_edit.setMaximumHeight(120)
        self._text_edit.setMinimumHeight(40)
        self._text_edit.installEventFilter(self)
        layout.addWidget(self._text_edit, 1)

        # 发送按钮
        self._send_btn = QPushButton(self._send_button_text)
        self._send_btn.setFixedHeight(40)
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.clicked.connect(self._on_send)
        layout.addWidget(self._send_btn)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        self._text_edit.setStyleSheet(
            f"""
            QTextEdit {{
                background: {t.bg_input};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: {t.input_radius}px;
                padding: {t.input_padding_y}px {t.input_padding_x}px;
                font-size: {t.font_size_md}px;
                selection-background-color: {t.primary_light};
            }}
            QTextEdit:focus {{
                border: 1px solid {t.border_focus};
            }}
            """
        )

        self._send_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {t.primary};
                color: {t.text_on_primary};
                border: none;
                border-radius: {t.button_radius}px;
                padding: 0 {t.button_padding_x}px;
                font-size: {t.font_size_md}px;
                font-weight: {t.button_font_weight};
                min-width: 80px;
            }}
            QPushButton:hover {{
                background: {t.primary_hover};
            }}
            QPushButton:pressed {{
                background: {t.primary_pressed};
            }}
            QPushButton:disabled {{
                background: {t.bg_hover};
                color: {t.text_disabled};
            }}
            """
        )

    def eventFilter(self, obj, event) -> bool:
        """事件过滤器，处理 Ctrl+Enter 发送"""
        if obj == self._text_edit and event.type() == QEvent.KeyPress:
            if (
                event.key() == Qt.Key_Return
                and event.modifiers() == Qt.ControlModifier
            ):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    def _on_send(self) -> None:
        """处理发送"""
        text = self._text_edit.toPlainText().strip()
        if text:
            self.message_sent.emit(text)
            self._text_edit.clear()

    def get_text(self) -> str:
        """获取输入文本"""
        return self._text_edit.toPlainText()

    def set_text(self, text: str) -> None:
        """设置输入文本"""
        self._text_edit.setPlainText(text)

    def clear(self) -> None:
        """清空输入"""
        self._text_edit.clear()

    def set_placeholder(self, placeholder: str) -> None:
        """设置占位符"""
        self._placeholder = placeholder
        self._text_edit.setPlaceholderText(placeholder)

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态"""
        self._text_edit.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

    def focus_input(self) -> None:
        """聚焦输入框"""
        self._text_edit.setFocus()
