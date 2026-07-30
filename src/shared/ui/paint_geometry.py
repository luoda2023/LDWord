"""DPR-aware stroke helpers shared by custom-painted UI controls."""

from __future__ import annotations

from src.qt_api import QColor, QPainter, QPen, Qt


STROKE_STANDARD = 1.0
STROKE_ICON = 1.5
STROKE_FOCUS = 2.0


def painter_dpr(painter: QPainter) -> float:
    device = painter.device()
    if device is None:
        return 1.0
    getter = getattr(device, "devicePixelRatioF", None)
    if callable(getter):
        return max(1.0, float(getter()))
    getter = getattr(device, "devicePixelRatio", None)
    if callable(getter):
        return max(1.0, float(getter()))
    return 1.0


def snapped_pen_width(logical_width: float, painter: QPainter) -> float:
    """Return a logical width that maps to an integer physical-pixel width."""

    dpr = painter_dpr(painter)
    physical_width = max(1, round(max(0.0, float(logical_width)) * dpr))
    return physical_width / dpr


def snapped_stroke_coordinate(
    logical_coordinate: float,
    logical_width: float,
    painter: QPainter,
) -> float:
    """Align an axis-aligned stroke center to its physical-pixel phase."""

    dpr = painter_dpr(painter)
    physical_width = max(1, round(max(0.0, float(logical_width)) * dpr))
    physical_coordinate = float(logical_coordinate) * dpr
    if physical_width % 2:
        physical_coordinate = round(physical_coordinate - 0.5) + 0.5
    else:
        physical_coordinate = round(physical_coordinate)
    return physical_coordinate / dpr


def stroke_pen(
    painter: QPainter,
    color,
    logical_width: float = STROKE_STANDARD,
    *,
    cap=Qt.RoundCap,
    join=Qt.RoundJoin,
    style=Qt.SolidLine,
) -> QPen:
    resolved_color = color if isinstance(color, QColor) else QColor(color)
    pen = QPen(resolved_color, snapped_pen_width(logical_width, painter), style)
    pen.setCapStyle(cap)
    pen.setJoinStyle(join)
    return pen


__all__ = [
    "STROKE_FOCUS",
    "STROKE_ICON",
    "STROKE_STANDARD",
    "painter_dpr",
    "snapped_pen_width",
    "snapped_stroke_coordinate",
    "stroke_pen",
]
