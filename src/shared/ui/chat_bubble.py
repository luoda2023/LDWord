"""ChatBubble — 聊天气泡控件"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography import Typography


class ChatBubble(QWidget):
    """聊天气泡控件，支持用户和 AI 两种样式。

    用法::

        # 用户消息
        bubble = ChatBubble(
            message="你好，请帮我排版这个文档",
            role="user",
            avatar="👤",
            timestamp="14:30"
        )

        # AI 消息
        bubble = ChatBubble(
            message="好的，我来帮你排版",
            role="assistant",
            avatar="🤖",
            timestamp="14:31"
        )
    """

    def __init__(
        self,
        message: str = "",
        role: str = "user",
        *,
        avatar: str = "",
        timestamp: str = "",
        parent=None,
    ):
        """初始化聊天气泡。

        Args:
            message: 消息内容
            role: 角色 (user/assistant)
            avatar: 头像（emoji 或文字）
            timestamp: 时间戳
            parent: 父控件
        """
        super().__init__(parent)
        self._message = message
        self._role = role
        self._avatar = avatar
        self._timestamp = timestamp

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        if self._role == "user":
            main_layout.addStretch()

        # 头像
        if self._avatar:
            self._avatar_label = QLabel(self._avatar)
            self._avatar_label.setFixedSize(32, 32)
            self._avatar_label.setAlignment(Qt.AlignCenter)
            if self._role == "user":
                main_layout.addWidget(self._avatar_label)

        # 消息容器
        message_container = QWidget()
        message_layout = QVBoxLayout(message_container)
        message_layout.setContentsMargins(12, 8, 12, 8)
        message_layout.setSpacing(4)

        # 消息文本
        self._message_label = QLabel(self._message)
        self._message_label.setWordWrap(True)
        self._message_label.setTextFormat(Qt.PlainText)
        message_layout.addWidget(self._message_label)

        # 时间戳
        if self._timestamp:
            self._timestamp_label = Typography(self._timestamp, variant="caption")
            self._timestamp_label.setAlignment(
                Qt.AlignRight if self._role == "user" else Qt.AlignLeft
            )
            message_layout.addWidget(self._timestamp_label)

        self._message_container = message_container
        main_layout.addWidget(message_container)

        # 头像（AI 在右侧）
        if self._avatar and self._role == "assistant":
            self._avatar_label = QLabel(self._avatar)
            self._avatar_label.setFixedSize(32, 32)
            self._avatar_label.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(self._avatar_label)

        if self._role == "assistant":
            main_layout.addStretch()

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        # 根据角色选择颜色
        if self._role == "user":
            bg = t.primary
            text_color = t.text_on_primary
        else:
            bg = t.bg_hover
            text_color = t.text_primary

        self._message_container.setStyleSheet(
            f"""
            QWidget {{
                background: {bg};
                border-radius: {t.radius_md}px;
            }}
            """
        )

        self._message_label.setStyleSheet(
            f"""
            QLabel {{
                color: {text_color};
                font-size: {t.font_size_md}px;
                background: transparent;
                border: none;
            }}
            """
        )

        # 头像样式
        if self._avatar:
            self._avatar_label.setStyleSheet(
                f"""
                QLabel {{
                    font-size: 24px;
                    background: {t.bg_card};
                    border: 1px solid {t.border_light};
                    border-radius: 16px;
                }}
                """
            )

    def set_message(self, message: str) -> None:
        """设置消息内容"""
        self._message = message
        self._message_label.setText(message)

    def message(self) -> str:
        """获取消息内容"""
        return self._message

    def set_timestamp(self, timestamp: str) -> None:
        """设置时间戳"""
        self._timestamp = timestamp
        if hasattr(self, "_timestamp_label"):
            self._timestamp_label.setText(timestamp)

    def timestamp(self) -> str:
        """获取时间戳"""
        return self._timestamp
