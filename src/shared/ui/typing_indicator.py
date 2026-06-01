"""TypingIndicator — 输入中指示器控件"""

from __future__ import annotations

from src.qt_api import (
    QGraphicsOpacityEffect,
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

        indicator = TypingIndicator()
        indicator.start()

        indicator.stop()
    """

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._animations: list[QPropertyAnimation] = []
        self._effects: list[QGraphicsOpacityEffect] = []

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        for i in range(3):
            dot = QLabel("●")
            dot.setAlignment(Qt.AlignCenter)
            dot.setFixedSize(12, 12)
            layout.addWidget(dot)

            opacity = QGraphicsOpacityEffect(dot)
            opacity.setOpacity(0.3)
            dot.setGraphicsEffect(opacity)
            self._effects.append(opacity)

            anim = QPropertyAnimation(opacity, b"opacity", dot)
            anim.setDuration(600)
            anim.setKeyValueAt(0.0, 0.3)
            anim.setKeyValueAt(0.5, 1.0)
            anim.setKeyValueAt(1.0, 0.3)
            anim.setLoopCount(-1)
            self._animations.append(anim)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(
            f"TypingIndicator {{ background: {t.bg_hover}; "
            f"border-radius: {t.radius_md}px; }}"
        )
        for effect in self._effects:
            parent = effect.parent()
            if isinstance(parent, QLabel):
                parent.setStyleSheet(
                    f"QLabel {{ color: {t.text_hint}; font-size: 8px; "
                    f"background: transparent; border: none; }}"
                )

    def start(self) -> None:
        for i, anim in enumerate(self._animations):
            QTimer.singleShot(i * 200, anim.start)
        self.show()

    def stop(self) -> None:
        for anim in self._animations:
            anim.stop()
        self.hide()

    def is_running(self) -> bool:
        from PySide6.QtCore import QAbstractAnimation
        return any(
            anim.state() == QAbstractAnimation.Running
            for anim in self._animations
        )
