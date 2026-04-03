from __future__ import annotations

from src.qt_api import QColor, QFrame, QPainter, QPainterPath, QRectF, Qt, QPen, QWidget


class RoundedSurfaceFrame(QFrame):
    """Shared self-painted rounded container for window shells and dialog cards.

    Child widgets are automatically made background-transparent so that they
    cannot paint rectangular opaque fills over the parent's rounded corners.
    """

    def __init__(self, radius: int = 10, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self._radius = int(radius)
        self._background = QColor("#ffffff")
        self._border_color = QColor(Qt.transparent)
        self._border_width = 0.0
        self._border_style = Qt.SolidLine

    # ------------------------------------------------------------------
    # Enforce transparent background on every child widget added to this
    # container so that rectangular auto-fills never cover the rounded
    # corner areas painted by paintEvent.
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
        self._background = QColor(background)
        self._radius = int(radius)
        self._border_color = QColor(border_color) if border_color else QColor(Qt.transparent)
        self._border_width = float(max(0.0, border_width))
        self._border_style = border_style
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        inset = 0.5 if self._border_width > 0 else 0.0
        rect = QRectF(
            inset,
            inset,
            max(0.0, self.width() - inset * 2),
            max(0.0, self.height() - inset * 2),
        )
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        painter.setPen(Qt.NoPen)
        painter.setBrush(self._background)
        painter.drawPath(path)

        if self._border_width > 0:
            pen = QPen(self._border_color, self._border_width)
            pen.setStyle(self._border_style)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

        painter.end()


__all__ = ["RoundedSurfaceFrame"]
