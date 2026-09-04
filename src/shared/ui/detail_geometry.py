from __future__ import annotations

from typing import TYPE_CHECKING

from src.qt_api import QEvent, QObject
from src.shared.ui.deferred_call import defer_qt_method

if TYPE_CHECKING:
    from src.qt_api import QScrollArea, QVBoxLayout, QWidget


class ScrollableDetailGeometrySync(QObject):
    """Keep a scroll area's detail content sized to its layout hint."""

    def __init__(
        self,
        detail_container: "QWidget",
        detail_layout: "QVBoxLayout",
        detail_scroll: "QScrollArea",
        *,
        parent: "QObject | None" = None,
    ) -> None:
        super().__init__(parent or detail_container)
        self._detail_container = detail_container
        self._detail_layout = detail_layout
        self._detail_scroll = detail_scroll
        self._active_widget: QWidget | None = None
        self._sync_pending = False
        self._syncing_geometry = False

    @property
    def active_widget(self) -> "QWidget | None":
        return self._active_widget

    def set_active_widget(self, widget: "QWidget | None") -> None:
        if widget is self._active_widget:
            return
        if self._active_widget is not None:
            self._active_widget.removeEventFilter(self)
        self._active_widget = widget
        if self._active_widget is not None:
            self._active_widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self._active_widget
            and event.type()
            in (QEvent.LayoutRequest, QEvent.Resize, QEvent.Show, QEvent.Hide)
        ):
            self.schedule()
        return super().eventFilter(watched, event)

    def schedule(self) -> None:
        if self._sync_pending or self._syncing_geometry or self._active_widget is None:
            return
        self._sync_pending = True
        defer_qt_method(self, "_run_deferred_sync")

    def sync_now(self, detail: "QWidget | None" = None) -> None:
        self._syncing_geometry = True
        try:
            viewport = self._detail_scroll.viewport()
            viewport_size = viewport.size() if viewport is not None else self._detail_scroll.size()
            width = max(1, viewport_size.width())
            if self._detail_container.width() != width:
                self._detail_container.resize(
                    width,
                    max(1, self._detail_container.height(), viewport_size.height()),
                )

            detail_widget = detail or self._active_widget
            # ``minimumHeight`` stores the result of the previous measurement.
            # Keeping that stale floor while asking ``sizeHint()`` for a new
            # value makes a shrinking detail self-reference its old height.
            # Clear it before every measurement so removals/collapses settle in
            # this transaction instead of a later QLayoutRequest.
            if self._detail_container.minimumHeight() != 0:
                self._detail_container.setMinimumHeight(0)
                self._detail_layout.invalidate()
                self._detail_layout.activate()
            last_content_height = None
            for _ in range(3):
                self._detail_layout.invalidate()
                self._detail_layout.activate()
                if detail_widget is not None:
                    detail_widget.updateGeometry()
                self._detail_container.updateGeometry()

                hint = self._detail_container.sizeHint()
                content_height = max(1, hint.height())
                height = max(1, viewport_size.height(), content_height)
                if self._detail_container.minimumHeight() != content_height:
                    self._detail_container.setMinimumHeight(content_height)
                if self._detail_container.width() != width or self._detail_container.height() != height:
                    self._detail_container.resize(width, height)
                    self._detail_layout.activate()
                if last_content_height == content_height:
                    break
                last_content_height = content_height
        finally:
            self._syncing_geometry = False

    def _run_deferred_sync(self) -> None:
        self._sync_pending = False
        if self._active_widget is None:
            return
        self.sync_now(self._active_widget)


__all__ = ["ScrollableDetailGeometrySync"]
