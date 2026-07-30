"""EmptyState — 空状态占位控件"""

from __future__ import annotations

from src.qt_api import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.typography import Typography
from src.shared.ui.icons.catalog import get_icon


class EmptyState(QWidget):
    """空状态占位控件，显示图标、文案和操作按钮。

    用法::

        # 基础用法
        empty = EmptyState(
            icon="file-text",
            title="暂无文档",
            description="拖入文档开始排版"
        )

        # 带操作按钮
        empty = EmptyState(
            icon="folder-open",
            title="文件夹为空",
            description="点击下方按钮添加文件",
            action_text="添加文件"
        )
        empty.action_clicked.connect(lambda: print("添加文件"))
    """

    action_clicked = Signal()  # 操作按钮点击信号

    def __init__(
        self,
        *,
        icon: str = "",
        title: str = "",
        description: str = "",
        action_text: str = "",
        parent=None,
    ):
        """初始化空状态控件。

        Args:
            icon: ``src.shared.ui.icons.catalog`` 中登记的图标名称
            title: 标题
            description: 描述文字
            action_text: 操作按钮文字
            parent: 父控件
        """
        super().__init__(parent)
        self._icon = icon
        self._title = title
        self._description = description
        self._action_text = action_text

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignCenter)

        # 图标
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(72, 72)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setVisible(bool(self._icon))
        layout.addWidget(self._icon_label, 0, Qt.AlignCenter)

        # 标题
        if self._title:
            self._title_label = Typography(self._title, variant="h3")
            self._title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self._title_label, 0, Qt.AlignCenter)

        # 描述
        if self._description:
            self._desc_label = Typography(self._description, variant="caption")
            self._desc_label.setAlignment(Qt.AlignCenter)
            self._desc_label.setWordWrap(True)
            layout.addWidget(self._desc_label, 0, Qt.AlignCenter)

        # 操作按钮
        if self._action_text:
            self._action_btn = QPushButton(self._action_text)
            self._action_btn.setCursor(Qt.PointingHandCursor)
            self._action_btn.clicked.connect(self.action_clicked.emit)
            layout.addWidget(self._action_btn, 0, Qt.AlignCenter)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        self.setStyleSheet(
            """
            EmptyState {{
                background: transparent;
            }}
            """
        )

        # 图标样式
        if self._icon:
            self._icon_label.setPixmap(
                get_icon(self._icon, 56, t.text_hint).pixmap(56, 56)
            )
            self._icon_label.setStyleSheet(
                """
                QLabel {{
                    background: transparent;
                    border: none;
                }}
                """
            )

        # 操作按钮样式
        if self._action_text and hasattr(self, "_action_btn"):
            apply_button_variant(self._action_btn, "primary")
            apply_size_class(self._action_btn, "md")
            self._action_btn.setStyleSheet(build_button_stylesheet(t))

    def set_icon(self, icon: str) -> None:
        """设置图标"""
        self._icon = icon
        self._icon_label.setVisible(bool(icon))
        self._apply_theme()

    def set_title(self, title: str) -> None:
        """设置标题"""
        self._title = title
        if hasattr(self, "_title_label"):
            self._title_label.setText(title)

    def set_description(self, description: str) -> None:
        """设置描述"""
        self._description = description
        if hasattr(self, "_desc_label"):
            self._desc_label.setText(description)

    def set_action_text(self, text: str) -> None:
        """设置操作按钮文字"""
        self._action_text = text
        if hasattr(self, "_action_btn"):
            self._action_btn.setText(text)
