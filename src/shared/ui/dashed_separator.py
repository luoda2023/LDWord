"""Dashed separator shared across workbench and detail panes."""

from __future__ import annotations

from src.qt_api import QColor, QPainter, QPen, QSizePolicy, QWidget, Qt

from src.shared.ui.theme import bind_theme, get_theme


class DashedSeparator(QWidget):
    """Painter-based dashed separator supporting both orientations."""

    def __init__(self, orientation: str = "horizontal", color: str | None = None, *, parent=None):
        super().__init__(parent)
        self._orientation = "vertical" if orientation == "vertical" else "horizontal"
        self._uses_theme_color = color is None
        self._color = QColor(color or get_theme().text_hint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._apply_geometry()
        bind_theme(self, self._on_theme_changed)

    def _apply_geometry(self) -> None:
        if self._orientation == "vertical":
            self.setFixedWidth(17)  # 8px padding + 1px line + 8px padding
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        else:
            self.setFixedHeight(13)  # 6px padding + 1px line + 6px padding
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _on_theme_changed(self) -> None:
        if self._uses_theme_color:
            self._color = QColor(get_theme().text_hint)
        self.update()

    def set_color(self, color: str) -> None:
        self._uses_theme_color = False
        self._color = QColor(color)
        self.update()

    def color(self) -> QColor:
        return QColor(self._color)

    def orientation(self) -> str:
        return self._orientation

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        pen = QPen(self._color, 1, Qt.CustomDashLine)
        pen.setDashPattern([5, 3])
        painter.setPen(pen)

        if self._orientation == "vertical":
            x = self.width() // 2
            painter.drawLine(x, 0, x, self.height())
        else:
            y = self.height() // 2
            painter.drawLine(0, y, self.width(), y)

        painter.end()


__all__ = ["DashedSeparator"]
