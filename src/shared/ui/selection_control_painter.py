from __future__ import annotations

from src.qt_api import QBrush, QColor, QPainter, QRectF, Qt
from src.shared.ui.paint_geometry import stroke_pen


def draw_focus_ring(painter: QPainter, rect: QRectF, *, color, width: float) -> None:
    painter.save()
    pen_color = color if isinstance(color, QColor) else QColor(color)
    painter.setPen(stroke_pen(painter, pen_color, width))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(rect)
    painter.restore()


def draw_radio_indicator(
    painter: QPainter,
    outer_rect: QRectF,
    *,
    ring_color: str,
    bg_color: str,
    ring_width: float,
    dot_color: str | None = None,
    dot_diameter: float = 0.0,
) -> None:
    painter.save()
    painter.setPen(stroke_pen(painter, QColor(ring_color), ring_width))
    painter.setBrush(QBrush(QColor(bg_color)))
    painter.drawEllipse(outer_rect)
    if dot_color and dot_diameter > 0:
        inset = (outer_rect.width() - dot_diameter) / 2.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(dot_color)))
        painter.drawEllipse(outer_rect.adjusted(inset, inset, -inset, -inset))
    painter.restore()
