"""SplitPane — 可拖拽双栏分割控件"""

from __future__ import annotations

from src.qt_api import (
    QSplitter,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme


class SplitPane(QSplitter):
    """可拖拽的双栏分割控件。

    用法::

        # 水平分割
        split = SplitPane(orientation="horizontal")
        split.add_widget(left_widget)
        split.add_widget(right_widget)

        # 垂直分割
        split = SplitPane(orientation="vertical")
        split.add_widget(top_widget)
        split.add_widget(bottom_widget)

        # 设置初始比例
        split.set_sizes([300, 700])
    """

    def __init__(self, orientation: str = "horizontal", *, parent=None):
        """初始化分割控件。

        Args:
            orientation: 方向，"horizontal" 或 "vertical"
            parent: 父控件
        """
        if orientation == "vertical":
            super().__init__(Qt.Vertical, parent)
        else:
            super().__init__(Qt.Horizontal, parent)

        self._orientation = orientation

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        self.setChildrenCollapsible(False)
        self.setHandleWidth(1)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        self.setStyleSheet(
            f"""
            QSplitter::handle {{
                background: {t.border};
            }}
            QSplitter::handle:hover {{
                background: {t.border_focus};
            }}
            QSplitter::handle:horizontal {{
                width: 1px;
            }}
            QSplitter::handle:vertical {{
                height: 1px;
            }}
            """
        )

    def add_widget(self, widget: QWidget) -> None:
        """添加子控件"""
        self.addWidget(widget)

    def set_sizes(self, sizes: list) -> None:
        """设置各部分的大小"""
        self.setSizes(sizes)

    def get_sizes(self) -> list:
        """获取各部分的大小"""
        return self.sizes()
