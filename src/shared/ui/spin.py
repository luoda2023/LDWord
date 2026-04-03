"""Spin — 加载旋转指示器控件"""

from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget, Qt

from src.shared.ui.theme import bind_theme, get_theme


class Spin(QWidget):
    """旋转加载指示器，用于表示加载状态。

    用法::

        # 基础用法
        spin = Spin()

        # 带提示文字
        spin = Spin(tip="加载中...")

        # 自定义大小
        spin = Spin(size=48)
    """

    def __init__(
        self,
        *,
        size: int = 32,
        tip: str = "",
        parent=None,
    ):
        """初始化旋转指示器。

        Args:
            size: 旋转图标大小（像素）
            tip: 提示文字
            parent: 父控件
        """
        super().__init__(parent)
        self._size = size
        self._tip = tip
        self._spinning = True

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        # 旋转图标（使用 CSS 动画实现）
        self._spinner = QLabel()
        self._spinner.setFixedSize(self._size, self._size)
        self._spinner.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._spinner, 0, Qt.AlignCenter)

        # 提示文字
        if self._tip:
            self._tip_label = QLabel(self._tip)
            self._tip_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self._tip_label, 0, Qt.AlignCenter)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        # 使用 Unicode 旋转字符或 SVG 实现旋转效果
        # 这里使用简化的圆圈字符，实际项目中可以用 QPainter 绘制或 QMovie
        self._spinner.setText("⟳")
        self._spinner.setStyleSheet(
            f"""
            QLabel {{
                color: {t.primary};
                font-size: {self._size}px;
                background: transparent;
                border: none;
            }}
            """
        )

        if self._tip:
            self._tip_label.setStyleSheet(
                f"""
                QLabel {{
                    color: {t.text_secondary};
                    font-size: {t.font_size_sm}px;
                    background: transparent;
                    border: none;
                }}
                """
            )

    def set_spinning(self, spinning: bool) -> None:
        """设置是否旋转"""
        self._spinning = spinning
        self.setVisible(spinning)

    def is_spinning(self) -> bool:
        """获取是否正在旋转"""
        return self._spinning

    def set_tip(self, tip: str) -> None:
        """设置提示文字"""
        self._tip = tip
        if hasattr(self, "_tip_label"):
            self._tip_label.setText(tip)
            self._tip_label.setVisible(bool(tip))

    def tip(self) -> str:
        """获取提示文字"""
        return self._tip
