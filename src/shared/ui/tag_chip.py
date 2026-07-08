"""TagChip — 状态胶囊标签控件"""

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


class TagChip(QWidget):
    """可关闭的胶囊标签，支持多种颜色变体。

    用法::

        # 基础标签
        tag = TagChip("已完成")

        # 带颜色变体
        tag = TagChip("警告", variant="warning")

        # 可关闭标签
        tag = TagChip("临时", closable=True)
        tag.closed.connect(lambda: print("标签已关闭"))
    """

    closed = Signal()  # 关闭按钮点击信号

    def __init__(
        self,
        text: str = "",
        variant: str = "default",
        *,
        closable: bool = False,
        parent=None,
    ):
        """初始化标签。

        Args:
            text: 标签文本
            variant: 颜色变体 (default/primary/success/warning/error/info)
            closable: 是否显示关闭按钮
            parent: 父控件
        """
        super().__init__(parent)
        self._text = text
        self._variant = variant
        self._closable = closable

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # 文本标签
        self._label = QLabel(self._text)
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)

        # 关闭按钮
        if self._closable:
            self._close_btn = QPushButton("×")
            self._close_btn.setFixedSize(14, 14)
            self._close_btn.setCursor(Qt.PointingHandCursor)
            self._close_btn.clicked.connect(self._on_close)
            layout.addWidget(self._close_btn)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        # 根据变体选择颜色
        variant_colors = {
            "default": (t.bg_hover, t.text_secondary, t.border_light),
            "primary": (t.primary_light, t.primary, t.primary),
            "success": (t.success_bg, t.success, t.success),
            "warning": (t.warning_bg, t.warning, t.warning),
            "error": (t.error_bg, t.error, t.error),
            "info": (t.info_bg, t.info, t.info),
        }
        bg, fg, border = variant_colors.get(
            self._variant, variant_colors["default"]
        )

        # 标签样式
        self._label.setStyleSheet(
            f"""
            QLabel {{
                color: {fg};
                font-size: {t.font_size_sm}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
            """
        )

        # 容器样式
        self.setStyleSheet(
            f"""
            TagChip {{
                background: {bg};
                border: 1px solid {border};
                border-radius: {t.radius_full}px;
            }}
            """
        )

        # 关闭按钮样式
        if self._closable:
            self._close_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {fg};
                    font-size: 16px;
                    font-weight: bold;
                    padding: 0;
                }}
                QPushButton:hover {{
                    background: {theme_rgba(fg, 0.12)};
                    border-radius: 7px;
                }}
                """
            )

    def _on_close(self) -> None:
        """处理关闭按钮点击"""
        self.closed.emit()
        self.hide()

    def set_text(self, text: str) -> None:
        """设置标签文本"""
        self._text = text
        self._label.setText(text)

    def text(self) -> str:
        """获取标签文本"""
        return self._text

    def set_variant(self, variant: str) -> None:
        """设置颜色变体"""
        self._variant = variant
        self._apply_theme()

    def variant(self) -> str:
        """获取颜色变体"""
        return self._variant
