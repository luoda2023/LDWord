"""Shared wheel-zoom and drag interaction for preview dialogs."""

from __future__ import annotations

from src.qt_api import QPoint, QScrollArea, Qt, Signal


class InteractivePreviewScrollArea(QScrollArea):
    """Emit zoom requests and pan oversized preview content.

    Window movement deliberately does not live here.  A preview canvas has one
    predictable pointer contract: it pans only when the rendered content is
    larger than the viewport.  Frameless-window movement belongs to the title
    header instead.
    """

    wheel_zoom_requested = Signal(int, object)
    double_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pan_enabled = False
        self._dragging = False
        self._drag_start_global = QPoint()
        self._drag_start_h = 0
        self._drag_start_v = 0
        self._sync_cursor()

    def set_pan_enabled(self, enabled: bool) -> None:
        self._pan_enabled = bool(enabled)
        if not self._pan_enabled:
            self._dragging = False
        self._sync_cursor()

    def _sync_cursor(self) -> None:
        if not self._pan_enabled:
            cursor = Qt.ArrowCursor
        else:
            cursor = Qt.ClosedHandCursor if self._dragging else Qt.OpenHandCursor
        self.viewport().setCursor(cursor)

    def _start_drag(self, global_position: QPoint) -> None:
        self._dragging = True
        self._drag_start_global = global_position
        self._drag_start_h = self.horizontalScrollBar().value()
        self._drag_start_v = self.verticalScrollBar().value()
        self._sync_cursor()

    def _move_drag(self, global_position: QPoint) -> None:
        if not self._dragging:
            return
        delta = self._drag_start_global - global_position
        self.horizontalScrollBar().setValue(self._drag_start_h + delta.x())
        self.verticalScrollBar().setValue(self._drag_start_v + delta.y())

    def _finish_drag(self) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self._sync_cursor()

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API contract
        delta = event.angleDelta().y()
        if delta:
            self.wheel_zoom_requested.emit(delta, event.position().toPoint())
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API contract
        if event.button() == Qt.LeftButton and self._pan_enabled:
            self._start_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API contract
        if self._dragging and event.buttons() & Qt.LeftButton:
            self._move_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API contract
        if event.button() == Qt.LeftButton and self._dragging:
            self._finish_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API contract
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


__all__ = ["InteractivePreviewScrollArea"]
