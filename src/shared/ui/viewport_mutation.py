"""Synchronous, anchor-preserving mutations for scrollable Qt content."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import AbstractContextManager

from shiboken6 import isValid

from src.qt_api import QApplication, QEvent, QPoint, QScrollArea, QWidget
from src.shared.ui.layout_sync import refresh_layout_chain


class ViewportMutationTransaction(AbstractContextManager):
    """Commit one layout mutation without exposing intermediate geometry.

    The anchor is measured directly in viewport coordinates.  Local layouts and
    the optional outer geometry synchronizer are settled before painting is
    restored, so scroll correctness never depends on a queued timer.
    """

    def __init__(
        self,
        *,
        scroll,
        content: QWidget,
        anchor: QWidget | None = None,
        layout_roots: Iterable[QWidget] = (),
        geometry_sync=None,
        geometry_detail: QWidget | None = None,
        paint_targets: Iterable[QWidget] = (),
    ) -> None:
        self._scroll = scroll
        self._content = content
        self._anchor = anchor
        self._layout_roots = tuple(
            widget for widget in layout_roots if widget is not None
        )
        self._geometry_sync = geometry_sync
        self._geometry_detail = geometry_detail
        self._bar = scroll.verticalScrollBar() if scroll is not None else None
        self._before_scroll = self._bar.value() if self._bar is not None else 0
        self._before_anchor_y: int | None = None
        self._targets: list[QWidget] = []
        self._suspended_targets: list[QWidget] = []
        viewport = scroll.viewport() if scroll is not None else None
        for widget in (viewport, content, scroll, *paint_targets):
            if widget is not None and widget not in self._targets:
                self._targets.append(widget)

    def __enter__(self):
        viewport = self._scroll.viewport() if self._scroll is not None else None
        if (
            self._anchor is not None
            and isValid(self._anchor)
            and viewport is not None
            and isValid(viewport)
        ):
            self._before_anchor_y = self._anchor.mapTo(
                viewport,
                QPoint(0, 0),
            ).y()
        for widget in self._targets:
            # Do not change widgets that were already suspended by an outer
            # transaction.  This keeps nested transactions from re-enabling
            # painting too early when they exit.
            if isValid(widget) and widget.updatesEnabled():
                widget.setUpdatesEnabled(False)
                self._suspended_targets.append(widget)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            self._settle_layouts()
            self._restore_scroll_anchor()
        finally:
            for widget in reversed(self._suspended_targets):
                if isValid(widget):
                    widget.setUpdatesEnabled(True)
            viewport = self._scroll.viewport() if self._scroll is not None else None
            if viewport is not None and isValid(viewport):
                viewport.update()
            if isValid(self._content):
                self._content.update()
        return False

    def _settle_layouts(self) -> None:
        # QWidget removals post LayoutRequest events.  If those requests are
        # left queued, the transaction measures yesterday's geometry and the
        # scroll anchor moves one or two event-loop turns later.  Dispatch only
        # this narrow event type synchronously; user input, timers and deferred
        # deletion remain untouched.
        QApplication.sendPostedEvents(None, QEvent.LayoutRequest)
        roots = tuple(
            root
            for root in (self._layout_roots or (self._content,))
            if isValid(root)
        )
        for root in roots:
            refresh_layout_chain(root, passes=2)
        if self._geometry_sync is not None:
            self._geometry_sync.sync_now(self._geometry_detail)
        for root in roots:
            layout = root.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            root.updateGeometry()
        if self._geometry_sync is not None:
            self._geometry_sync.sync_now(self._geometry_detail)

    def _restore_scroll_anchor(self) -> None:
        if self._bar is None or not isValid(self._bar):
            return
        viewport = self._scroll.viewport()
        if (
            self._anchor is None
            or not isValid(self._anchor)
            or viewport is None
            or not isValid(viewport)
            or self._before_anchor_y is None
        ):
            target = self._before_scroll
        else:
            after_anchor_y = self._anchor.mapTo(viewport, QPoint(0, 0)).y()
            target = self._before_scroll + after_anchor_y - self._before_anchor_y
        self._bar.setValue(
            min(max(self._bar.minimum(), target), self._bar.maximum())
        )


def viewport_mutation(**kwargs) -> ViewportMutationTransaction:
    """Convenience constructor for ``with viewport_mutation(...):``."""

    return ViewportMutationTransaction(**kwargs)


def viewport_mutation_for_widget(
    widget: QWidget,
    *,
    anchor: QWidget | None = None,
    layout_roots: Iterable[QWidget] = (),
    paint_targets: Iterable[QWidget] = (),
) -> ViewportMutationTransaction:
    """Build a transaction from a widget inside a managed scroll detail.

    This keeps reusable child editors independent from the panel that hosts
    them.  The nearest ``QScrollArea`` and its optional
    ``ScrollableDetailGeometrySync`` are discovered through QObject
    ownership; standalone widgets still receive a paint/layout transaction.
    """

    cursor: QWidget | None = widget
    scroll: QScrollArea | None = None
    while cursor is not None:
        if isinstance(cursor, QScrollArea):
            scroll = cursor
            break
        cursor = cursor.parentWidget()

    content = scroll.widget() if scroll is not None else widget
    if content is None:
        content = widget
    geometry_sync = None
    geometry_detail = widget
    if scroll is not None:
        from src.shared.ui.detail_geometry import ScrollableDetailGeometrySync

        geometry_sync = content.findChild(ScrollableDetailGeometrySync)
        if geometry_sync is not None and geometry_sync.active_widget is not None:
            geometry_detail = geometry_sync.active_widget
    return ViewportMutationTransaction(
        scroll=scroll,
        content=content,
        anchor=anchor,
        layout_roots=layout_roots or (widget,),
        geometry_sync=geometry_sync,
        geometry_detail=geometry_detail,
        paint_targets=paint_targets,
    )


__all__ = [
    "ViewportMutationTransaction",
    "viewport_mutation",
    "viewport_mutation_for_widget",
]
