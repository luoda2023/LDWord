"""Helpers for settling Qt layout changes without exposing intermediate frames."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from src.qt_api import QTimer, QWidget


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
    """Run one deferred layout settle after Qt has delivered pending show/hide events."""

    if start is None:
        return
    QTimer.singleShot(0, lambda widget=start, count=passes: refresh_layout_chain(widget, passes=count))


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

    for widget in targets:
        widget.setUpdatesEnabled(False)
    try:
        yield
    finally:
        for widget in reversed(targets):
            widget.setUpdatesEnabled(True)
            widget.update()


__all__ = [
    "refresh_layout_chain",
    "refresh_layout_chain_later",
    "reserve_visible_height",
    "set_visible_if_changed",
    "updates_suspended",
]
