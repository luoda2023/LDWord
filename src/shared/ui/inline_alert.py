"""InlineAlert — 内嵌横幅提示控件"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme, theme_rgba


class InlineAlert(QWidget):
    """内嵌横幅提示，支持多种类型和可关闭。

    用法::

        # 基础用法
        alert = InlineAlert("这是一条提示信息", variant="info")

        # 可关闭
        alert = InlineAlert(
            "这是一条警告信息",
            variant="warning",
            closable=True
        )
        alert.closed.connect(lambda: print("提示已关闭"))
    """

    closed = Signal()  # 关闭信号

    def __init__(
        self,
        message: str = "",
        variant: str = "info",
        *,
        closable: bool = False,
        parent=None,
    ):
        """初始化提示控件。

        Args:
            message: 提示消息
            variant: 类型 (info/success/warning/error)
            closable: 是否可关闭
            parent: 父控件
        """
        super().__init__(parent)
        self._message = message
        self._variant = variant
        self._closable = closable

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 图标
        icon_map = {
            "info": "ℹ️",
            "success": "✓",
            "warning": "⚠️",
            "error": "✕",
        }
        self._icon_label = QLabel(icon_map.get(self._variant, "ℹ️"))
        self._icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon_label)

        # 消息文本
        self._message_label = QLabel(self._message)
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label, 1)

        # 关闭按钮
        if self._closable:
            self._close_btn = QPushButton("×")
            self._close_btn.setFixedSize(20, 20)
            self._close_btn.setCursor(Qt.PointingHandCursor)
            self._close_btn.clicked.connect(self._on_close)
            layout.addWidget(self._close_btn)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        # 根据类型选择颜色
        variant_colors = {
            "info": (t.info, t.info_bg, t.info),
            "success": (t.success, t.success_bg, t.success),
            "warning": (t.warning, t.warning_bg, t.warning),
            "error": (t.error, t.error_bg, t.error),
        }
        accent, bg, border = variant_colors.get(
            self._variant, variant_colors["info"]
        )

        self.setStyleSheet(
            f"""
            InlineAlert {{
                background: {bg};
                border: 1px solid {border};
                border-radius: {t.radius_sm}px;
            }}
            """
        )

        self._icon_label.setStyleSheet(
            f"""
            QLabel {{
                color: {accent};
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
            """
        )

        self._message_label.setStyleSheet(
            f"""
            QLabel {{
                color: {t.text_primary};
                font-size: {t.font_size_md}px;
                background: transparent;
                border: none;
            }}
            """
        )

        if self._closable:
            self._close_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {t.text_hint};
                    font-size: 20px;
                    font-weight: bold;
                    padding: 0;
                }}
                QPushButton:hover {{
                    background: {theme_rgba(t.text_primary, 0.10)};
                    border-radius: 10px;
                    color: {t.text_primary};
                }}
                """
            )

    def _on_close(self) -> None:
        """处理关闭"""
        self.closed.emit()
        self.hide()

    def set_message(self, message: str) -> None:
        """设置消息"""
        self._message = message
        self._message_label.setText(message)

    def message(self) -> str:
        """获取消息"""
        return self._message

    def set_variant(self, variant: str) -> None:
        """设置类型"""
        self._variant = variant
        self._apply_theme()

    def variant(self) -> str:
        """获取类型"""
        return self._variant
