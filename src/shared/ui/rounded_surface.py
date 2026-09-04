from __future__ import annotations

import re

from src.qt_api import QColor, QFrame, QPainter, QPainterPath, QRectF, Qt, QWidget
from src.shared.ui.paint_geometry import snapped_pen_width, stroke_pen
from src.shared.ui.theme import get_theme


class RoundedSurfaceFrame(QFrame):
    """Shared self-painted rounded container for window shells and dialog cards.

    This class owns its own fill and border geometry. Child QSS backgrounds are
    not clipped by this painter, so shell callers must not duplicate the outer
    surface background/radius on edge-to-edge descendants.
    """

    def __init__(self, radius: int = 10, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self._radius = int(radius)
        self._background = QColor(get_theme().bg_card)
        self._border_color = QColor(Qt.transparent)
        self._border_width = 0.0
        self._border_style = Qt.SolidLine

    # ------------------------------------------------------------------
    # Disable palette auto-fill on children. Explicit QSS backgrounds still
    # paint normally and are intentionally outside this method's authority.
    # ------------------------------------------------------------------
    def childEvent(self, event) -> None:
        super().childEvent(event)
        if event.added():
            child = event.child()
            if isinstance(child, QWidget):
                child.setAutoFillBackground(False)

    def configure_surface(
        self,
        *,
        background: str,
        radius: int,
        border_color: str | None = None,
        border_width: float = 0.0,
        border_style=Qt.SolidLine,
    ) -> None:
        self._background = _surface_color(background)
        self._radius = int(radius)
        self._border_color = (
            _surface_color("transparent")
            if not border_color
            else _surface_color(border_color)
        )
        self._border_width = float(max(0.0, border_width))
        self._border_style = border_style
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        fill_rect = QRectF(0.0, 0.0, float(self.width()), float(self.height()))
        fill_path = QPainterPath()
        fill_path.addRoundedRect(fill_rect, self._radius, self._radius)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._background)
        painter.drawPath(fill_path)

        if self._border_width > 0:
            rendered_width = snapped_pen_width(self._border_width, painter)
            inset = rendered_width / 2.0
            border_rect = QRectF(
                inset,
                inset,
                max(0.0, float(self.width()) - rendered_width),
                max(0.0, float(self.height()) - rendered_width),
            )
            border_radius = max(0.0, float(self._radius) - inset)
            border_path = QPainterPath()
            border_path.addRoundedRect(border_rect, border_radius, border_radius)
            pen = stroke_pen(
                painter,
                self._border_color,
                self._border_width,
                cap=Qt.RoundCap,
                join=Qt.RoundJoin,
                style=self._border_style,
            )
            pen.setStyle(self._border_style)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(border_path)

        painter.end()


def _surface_color(value: object) -> QColor:
    text = str(value or "").strip()
    if not text or text.lower() == "transparent":
        return QColor(Qt.transparent)
    match = re.fullmatch(
        r"rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([0-9.]+)\s*\)",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return QColor(text)
    red, green, blue = (
        max(0, min(255, int(component)))
        for component in match.groups()[:3]
    )
    alpha = float(match.group(4))
    if alpha > 1:
        alpha /= 255.0
    return QColor(red, green, blue, round(max(0.0, min(1.0, alpha)) * 255))


__all__ = ["RoundedSurfaceFrame"]
