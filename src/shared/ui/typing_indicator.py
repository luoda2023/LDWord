"""TypingIndicator — 输入中指示器控件"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QPropertyAnimation,
    QTimer,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme


class TypingIndicator(QWidget):
    """输入中指示器，显示三点脉动动画。

    用法::

        # 基础用法
        indicator = TypingIndicator()
        indicator.start()

        # 停止动画
        indicator.stop()
    """

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._animations = []

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # 创建三个点
        self._dots = []
        for i in range(3):
            dot = QLabel("●")
            dot.setAlignment(Qt.AlignCenter)
            dot.setFixedSize(12, 12)
            layout.addWidget(dot)
            self._dots.append(dot)

            # 创建透明度动画
            animation = QPropertyAnimation(dot, b"windowOpacity")
            animation.setDuration(600)
            animation.setStartValue(0.3)
            animation.setEndValue(1.0)
            animation.setLoopCount(-1)  # 无限循环
            self._animations.append(animation)

        # 设置动画延迟
        for i, animation in enumerate(self._animations):
            animation.setStartValue(0.3 + i * 0.1)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        self.setStyleSheet(
            f"""
            TypingIndicator {{
                background: {t.bg_hover};
                border-radius: {t.radius_md}px;
            }}
            """
        )

        for dot in self._dots:
            dot.setStyleSheet(
                f"""
                QLabel {{
                    color: {t.text_hint};
                    font-size: 8px;
                    background: transparent;
                    border: none;
                }}
                """
            )

    def start(self) -> None:
        """开始动画"""
        for i, animation in enumerate(self._animations):
            QTimer.singleShot(i * 200, animation.start)
        self.show()

    def stop(self) -> None:
        """停止动画"""
        for animation in self._animations:
            animation.stop()
        self.hide()

    def is_running(self) -> bool:
        """判断动画是否运行中"""
        from PySide6.QtCore import QAbstractAnimation
        return any(
            anim.state() == QAbstractAnimation.Running
            for anim in self._animations
        )
