"""TextArea — 多行文本输入控件"""

from __future__ import annotations

from src.qt_api import (
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme


class TextArea(QWidget):
    """多行文本输入框，支持自适应高度和字数统计。

    用法::

        # 基础用法
        text_area = TextArea(placeholder="请输入内容...")

        # 带字数统计
        text_area = TextArea(
            placeholder="请输入内容...",
            show_count=True,
            max_length=500
        )
        text_area.text_changed.connect(lambda: print(text_area.get_text()))
    """

    text_changed = Signal()  # 文本变化信号

    def __init__(
        self,
        *,
        placeholder: str = "",
        show_count: bool = False,
        max_length: int = 0,
        min_height: int = 80,
        max_height: int = 300,
        parent=None,
    ):
        """初始化文本输入框。

        Args:
            placeholder: 占位符文字
            show_count: 是否显示字数统计
            max_length: 最大字数限制（0 表示无限制）
            min_height: 最小高度
            max_height: 最大高度
            parent: 父控件
        """
        super().__init__(parent)
        self._placeholder = placeholder
        self._show_count = show_count
        self._max_length = max_length
        self._min_height = min_height
        self._max_height = max_height

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 文本编辑器
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(self._placeholder)
        self._text_edit.setMinimumHeight(self._min_height)
        self._text_edit.setMaximumHeight(self._max_height)
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit)

        # 字数统计
        if self._show_count:
            self._count_label = QLabel()
            self._count_label.setAlignment(Qt.AlignRight)
            layout.addWidget(self._count_label)
            self._update_count()

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
            QTextEdit:disabled {{
                background: {t.bg_hover};
                color: {t.text_disabled};
            }}
            """
        )

        if self._show_count:
            self._count_label.setStyleSheet(
                f"""
                QLabel {{
                    color: {t.text_hint};
                    font-size: {t.font_size_sm}px;
                    background: transparent;
                    border: none;
                }}
                """
            )

    def _on_text_changed(self) -> None:
        """处理文本变化"""
        # 字数限制
        if self._max_length > 0:
            text = self._text_edit.toPlainText()
            if len(text) > self._max_length:
                cursor = self._text_edit.textCursor()
                cursor.deletePreviousChar()

        # 更新字数统计
        if self._show_count:
            self._update_count()

        self.text_changed.emit()

    def _update_count(self) -> None:
        """更新字数统计"""
        if not self._show_count:
            return

        current = len(self._text_edit.toPlainText())
        if self._max_length > 0:
            self._count_label.setText(f"{current} / {self._max_length}")
        else:
            self._count_label.setText(f"{current}")

    def get_text(self) -> str:
        """获取文本内容"""
        return self._text_edit.toPlainText()

    def set_text(self, text: str) -> None:
        """设置文本内容"""
        self._text_edit.setPlainText(text)

    def clear(self) -> None:
        """清空文本"""
        self._text_edit.clear()

    def set_placeholder(self, placeholder: str) -> None:
        """设置占位符"""
        self._placeholder = placeholder
        self._text_edit.setPlaceholderText(placeholder)

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态"""
        self._text_edit.setEnabled(enabled)

    def is_empty(self) -> bool:
        """判断是否为空"""
        return len(self._text_edit.toPlainText().strip()) == 0
