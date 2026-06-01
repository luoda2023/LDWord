"""Spin — 真正旋转的加载指示器控件"""

from __future__ import annotations

from src.qt_api import (
    QBrush,
    QColor,
    QConicalGradient,
    QPainter,
    QPen,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme

_SPIN_INTERVAL_MS = 30
_ROTATE_STEP = 12


class Spin(QWidget):
    """旋转加载指示器，使用 QPainter 绘制旋转弧线。"""

    def __init__(
        self,
        *,
        size: int = 32,
        tip: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._size = size
        self._tip = tip
        self._spinning = True
        self._angle = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(_SPIN_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self._timer.start()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        canvas_size = self._size + 8
        self._canvas = _SpinCanvas(canvas_size, parent=self)
        layout.addWidget(self._canvas, 0, Qt.AlignCenter)

        if self._tip:
            from src.qt_api import QLabel
            self._tip_label = QLabel(self._tip)
            self._tip_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self._tip_label, 0, Qt.AlignCenter)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._canvas._color = QColor(t.primary)
        if hasattr(self, "_tip_label"):
            self._tip_label.setStyleSheet(
                f"color: {t.text_secondary}; font-size: {t.font_size_sm}px;"
                "background: transparent; border: none;"
            )

    def _tick(self) -> None:
        self._angle = (self._angle + _ROTATE_STEP) % 360
        self._canvas._angle = self._angle
        self._canvas.update()

    def set_spinning(self, spinning: bool) -> None:
        self._spinning = spinning
        if spinning:
            self._timer.start()
        else:
            self._timer.stop()
        self.setVisible(spinning)

    def is_spinning(self) -> bool:
        return self._spinning

    def set_tip(self, tip: str) -> None:
        self._tip = tip
        if hasattr(self, "_tip_label"):
            self._tip_label.setText(tip)
            self._tip_label.setVisible(bool(tip))

    def tip(self) -> str:
        return self._tip


class _SpinCanvas(QWidget):
    """Internal paint surface for the spinning arc."""

    def __init__(self, size: int, parent=None):
        super().__init__(parent)
        self._angle = 0.0
        self._color = QColor("#1677FF")
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:
        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        r = min(w, h) / 2.0 - 3.0

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background track circle
        track = QColor(self._color)
        track.setAlpha(30)
        painter.setPen(QPen(track, 3.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        # Spinning arc — gradient pen via QBrush
        grad = QConicalGradient(cx, cy, self._angle)
        grad.setColorAt(0.0, QColor(self._color.red(), self._color.green(),
                                    self._color.blue(), 0))
        grad.setColorAt(0.5, QColor(self._color.red(), self._color.green(),
                                    self._color.blue(), 200))
        grad.setColorAt(1.0, self._color)
        painter.setPen(QPen(QBrush(grad), 3.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(int(cx - r), int(cy - r), int(r * 2), int(r * 2),
                        int(self._angle * 16), int(270 * 16))
