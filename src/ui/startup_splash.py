"""Small startup splash window used while the main UI preloads panels."""

from __future__ import annotations

import math

from src.app_meta import APP_DISPLAY_NAME_FULL
from src.qt_api import (
    QApplication,
    QColor,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPainter,
    QRectF,
    QSize,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.ui.theme import get_theme


class _Spinner(QWidget):
    """Tiny indeterminate loading indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self.setFixedSize(42, 42)
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def sizeHint(self):  # noqa: N802
        return QSize(42, 42)

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) / 2 - 6
        dot_radius = 3.0
        base = QColor(get_theme().primary)

        for i in range(12):
            alpha = 45 + int(210 * (i + 1) / 12)
            color = QColor(base)
            color.setAlpha(alpha)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            angle = math.radians(self._angle - i * 30)
            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius
            painter.drawEllipse(QRectF(x - dot_radius, y - dot_radius, dot_radius * 2, dot_radius * 2))


class StartupSplash(QWidget):
    """Frameless splash shown before the main window is ready."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SplashScreen | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(460, 260)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)

        surface = QFrame(self)
        surface.setObjectName("startup_surface")
        t = get_theme()

        shadow = QGraphicsDropShadowEffect(surface)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow_color = QColor(t.text_primary)
        if not shadow_color.isValid():
            shadow_color = QColor(15, 23, 42)
        shadow_color.setAlpha(55)
        shadow.setColor(shadow_color)
        surface.setGraphicsEffect(shadow)
        root.addWidget(surface)

        layout = QVBoxLayout(surface)
        layout.setContentsMargins(34, 30, 34, 28)
        layout.setSpacing(16)

        title = QLabel(APP_DISPLAY_NAME_FULL, surface)
        title.setObjectName("startup_title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("正在准备工作区", surface)
        subtitle.setObjectName("startup_subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        row = QWidget(surface)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 8, 0, 0)
        row_layout.setSpacing(14)
        row_layout.addStretch(1)
        self._spinner = _Spinner(row)
        row_layout.addWidget(self._spinner, 0, Qt.AlignVCenter)
        self._status = QLabel("正在启动...", row)
        self._status.setObjectName("startup_status")
        row_layout.addWidget(self._status, 0, Qt.AlignVCenter)
        row_layout.addStretch(1)
        layout.addWidget(row)

        hint = QLabel("首次加载会预热常用页面", surface)
        hint.setObjectName("startup_hint")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self.setStyleSheet(
            f"""
            QFrame#startup_surface {{
                background: {t.bg_card};
                border: 1px solid {t.border_light};
                border-radius: {t.radius_lg + 4}px;
            }}
            QLabel#startup_title {{
                color: {t.text_primary};
                font-size: {t.font_size_xxl + 2}px;
                font-weight: {t.font_weight_bold};
            }}
            QLabel#startup_subtitle {{
                color: {t.text_secondary};
                font-size: {t.font_size_md + 1}px;
            }}
            QLabel#startup_status {{
                color: {t.text_primary};
                font-size: {t.font_size_md}px;
                min-width: 150px;
            }}
            QLabel#startup_hint {{
                color: {t.text_hint};
                font-size: {t.font_size_sm}px;
            }}
            """
        )
        self._center_on_screen()

    def set_status(self, text: str) -> None:
        normalized = str(text or "").strip()
        if normalized:
            self._status.setText(normalized)

    def finish_and_close(self) -> None:
        self._spinner.stop()
        self.close()
        self.deleteLater()

    def _center_on_screen(self) -> None:
        screen = QApplication.screenAt(self.cursor().pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(
            rect.x() + (rect.width() - self.width()) // 2,
            rect.y() + (rect.height() - self.height()) // 2,
        )


__all__ = ["StartupSplash"]
