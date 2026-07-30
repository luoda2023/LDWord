"""
status_indicator — 状态标记控件

●成功 ●警告 ●失败 ●跳过 圆形状态指示器。
"""

from __future__ import annotations

from src.qt_api import QBrush, QColor, QPainter, QRectF, QSize, QWidget, Qt

from src.shared.ui.theme import get_theme, bind_theme
from src.shared.ui.icons.catalog import get_icon


class StatusIndicator(QWidget):
    """圆形状态指示器。

    status 取值:
    - "success"  绿
    - "warning"  黄
    - "error"    红
    - "skipped"  灰
    - "running"  蓝
    - "pending"  空心
    """

    STATUS_ICONS = {
        "success": "check",
        "warning": "info",
        "error":   "x",
        "skipped": "minus",
        "running": "loader",
        "pending": "",
    }

    def __init__(self, status: str = "pending", size: int = 16, parent=None):
        super().__init__(parent)
        self._status = status
        self._size = size
        self.setFixedSize(size, size)
        self._icon_pixmap = None
        self._update_pixmap_cache()
        bind_theme(self, self._update_pixmap_cache)

    @property
    def status(self) -> str:
        return self._status

    def set_status(self, status: str) -> None:
        self._status = status
        self._update_pixmap_cache()

    def _update_pixmap_cache(self) -> None:
        t = get_theme()
        if self._status != "pending":
            icon = self.STATUS_ICONS.get(self._status, "")
            if icon:
                icon_size = max(8, self._size - 6)
                self._icon_pixmap = get_icon(icon, icon_size, t.text_on_primary).pixmap(icon_size, icon_size)
            else:
                self._icon_pixmap = None
        else:
            self._icon_pixmap = None
        self.update()

    def paintEvent(self, event) -> None:
        t = get_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        color_map = {
            "success": t.success, "warning": t.warning,
            "error": t.error, "skipped": t.text_disabled,
            "running": t.primary, "pending": t.border,
        }
        color = QColor(color_map.get(self._status, t.border))

        rect = QRectF(1, 1, self._size - 2, self._size - 2)

        if self._status == "pending":
            p.setPen(color)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(rect)
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(color))
            p.drawEllipse(rect)

            if self._icon_pixmap:
                # Center pixmap
                icon_size = self._icon_pixmap.width()
                x = rect.x() + (rect.width() - icon_size) / 2
                y = rect.y() + (rect.height() - icon_size) / 2
                p.drawPixmap(int(x), int(y), self._icon_pixmap)

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)
