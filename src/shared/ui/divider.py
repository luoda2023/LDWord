"""Divider — 水平/垂直分割线控件"""

from __future__ import annotations

from src.qt_api import QFrame

from src.shared.ui.theme import bind_theme, get_theme


class Divider(QFrame):
    """分割线控件，支持水平和垂直方向。

    用法::

        # 水平分割线（默认）
        divider = Divider()

        # 垂直分割线
        divider = Divider(orientation="vertical")
    """

    def __init__(self, orientation: str = "horizontal", *, parent=None):
        """初始化分割线。

        Args:
            orientation: 方向，"horizontal" 或 "vertical"
            parent: 父控件
        """
        super().__init__(parent)
        self._orientation = orientation
        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        if self._orientation == "vertical":
            self.setFrameShape(QFrame.VLine)
            self.setFixedWidth(1)
        else:
            self.setFrameShape(QFrame.HLine)
            self.setFixedHeight(1)
        self.setFrameShadow(QFrame.Plain)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()
        self.setStyleSheet(f"background-color: {t.divider}; border: none;")
