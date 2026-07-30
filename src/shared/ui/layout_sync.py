"""Helpers for settling Qt layout changes without exposing intermediate frames."""

from __future__ import annotations

import weakref
from collections.abc import Iterator
from contextlib import contextmanager

from shiboken6 import isValid

from src.qt_api import QTimer, QWidget


_pending_layout_refreshes: dict[
    int,
    tuple[weakref.ReferenceType[QWidget], int],
] = {}
_layout_refresh_flush_scheduled = False


def refresh_layout_chain(start: QWidget | None, *, passes: int = 3) -> None:
    """Invalidate and activate layouts from ``start`` up through its parents."""

    if start is None:
        return

    for _ in range(max(1, int(passes))):
        widget: QWidget | None = start
        while widget is not None:
            layout = widget.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            widget.updateGeometry()
            widget = widget.parentWidget()


def refresh_layout_chain_later(start: QWidget | None, *, passes: int = 3) -> None:
    """Coalesce deferred layout settles into one event-loop commit.

    Repeated requests for the same widget retain the largest pass count.  If a
    child and its ancestor are both pending, only the child is refreshed
    because ``refresh_layout_chain`` already walks upward through that
    ancestor.  Sibling roots remain independent but are flushed in the same
    callback/frame.
    """

    if start is None:
        return
    key = id(start)
    requested_passes = max(1, int(passes))
    existing = _pending_layout_refreshes.get(key)
    if existing is not None and existing[0]() is start:
        requested_passes = max(requested_passes, existing[1])
    _pending_layout_refreshes[key] = (weakref.ref(start), requested_passes)

    global _layout_refresh_flush_scheduled
    if _layout_refresh_flush_scheduled:
        return
    _layout_refresh_flush_scheduled = True
    QTimer.singleShot(0, _flush_pending_layout_refreshes)


def _flush_pending_layout_refreshes() -> None:
    global _layout_refresh_flush_scheduled
    pending = list(_pending_layout_refreshes.values())
    _pending_layout_refreshes.clear()
    _layout_refresh_flush_scheduled = False

    live: list[tuple[QWidget, int]] = []
    for widget_ref, passes in pending:
        widget = widget_ref()
        if widget is not None and isValid(widget):
            live.append((widget, passes))
    live.sort(key=lambda entry: _widget_depth(entry[0]), reverse=True)

    roots: list[tuple[QWidget, int]] = []
    for widget, passes in live:
        for index, (descendant, descendant_passes) in enumerate(roots):
            if _is_widget_ancestor(widget, descendant):
                roots[index] = (descendant, max(passes, descendant_passes))
                break
        else:
            roots.append((widget, passes))

    for widget, passes in roots:
        if isValid(widget):
            refresh_layout_chain(widget, passes=passes)


def _widget_depth(widget: QWidget) -> int:
    depth = 0
    cursor = widget.parentWidget()
    while cursor is not None:
        depth += 1
        cursor = cursor.parentWidget()
    return depth


def _is_widget_ancestor(ancestor: QWidget, widget: QWidget) -> bool:
    cursor = widget.parentWidget()
    while cursor is not None:
        if cursor is ancestor:
            return True
        cursor = cursor.parentWidget()
    return False


def set_visible_if_changed(widget: QWidget, visible: bool) -> bool:
    """Set visibility only when it changes, reducing redundant layout churn."""

    hidden = not bool(visible)
    if widget.isHidden() == hidden:
        return False
    widget.setVisible(bool(visible))
    return True


def reserve_visible_height(widget: QWidget, height: int | None = None) -> None:
    """Reserve a positive height before showing widgets that would otherwise paint at 0px."""

    hint_height = max(0, int(height if height is not None else widget.sizeHint().height()))
    if hint_height > 0 and widget.minimumHeight() != hint_height:
        widget.setMinimumHeight(hint_height)
        widget.updateGeometry()


@contextmanager
def updates_suspended(*widgets: QWidget | None) -> Iterator[None]:
    """Temporarily suspend painting while a batch of layout-affecting changes lands."""

    targets: list[QWidget] = []
    for widget in widgets:
        if widget is not None and widget not in targets:
            targets.append(widget)

    suspended_here: list[QWidget] = []
    for widget in targets:
        if isValid(widget) and widget.updatesEnabled():
            widget.setUpdatesEnabled(False)
            suspended_here.append(widget)
    try:
        yield
    finally:
        for widget in reversed(suspended_here):
            if isValid(widget):
                widget.setUpdatesEnabled(True)
                widget.update()


__all__ = [
    "refresh_layout_chain",
    "refresh_layout_chain_later",
    "reserve_visible_height",
    "set_visible_if_changed",
    "updates_suspended",
]
