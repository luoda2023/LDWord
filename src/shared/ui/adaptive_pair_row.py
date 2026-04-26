"""Responsive row that keeps widgets side-by-side until space gets tight."""

from __future__ import annotations

from collections.abc import Sequence

from src.qt_api import QBoxLayout, QSizePolicy, QWidget


class AdaptivePairRow(QWidget):
    """Lay out peer widgets horizontally, then stack them vertically on narrow widths."""

    def __init__(
        self,
        *widgets: QWidget,
        parent=None,
        spacing: int = 12,
        stretches: Sequence[int] | None = None,
    ):
        super().__init__(parent)
        self._widgets = list(widgets)
        provided_stretches = tuple(stretches or ())
        self._stretches = tuple(
            provided_stretches[index] if index < len(provided_stretches) else 1
            for index, _widget in enumerate(self._widgets)
        )
        self._layout = QBoxLayout(QBoxLayout.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(spacing)
        for index, widget in enumerate(self._widgets):
            stretch = self._stretches[index] if index < len(self._stretches) else 1
            if int(stretch) <= 0:
                policy = widget.sizePolicy()
                policy.setHorizontalPolicy(QSizePolicy.Maximum)
                widget.setSizePolicy(policy)
            self._layout.addWidget(widget, int(stretch))
        if self._widgets and all(int(stretch) <= 0 for stretch in self._stretches):
            self._layout.addStretch(1)
        self._last_stacked: bool | None = None
        self._sync_direction()

    def resizeEvent(self, event) -> None:
        self._sync_direction()
        super().resizeEvent(event)

    def showEvent(self, event) -> None:
        self._sync_direction()
        super().showEvent(event)

    def _sync_direction(self) -> None:
        stacked = self.width() < self._stack_breakpoint()
        if stacked == self._last_stacked:
            return
        self._last_stacked = stacked
        self._layout.setDirection(QBoxLayout.TopToBottom if stacked else QBoxLayout.LeftToRight)
        self.updateGeometry()

    def _stack_breakpoint(self) -> int:
        widths = [
            max(widget.minimumSizeHint().width(), widget.sizeHint().width())
            for widget in self._widgets
        ]
        if not widths:
            return 0
        return sum(widths) + self._layout.spacing() * (len(widths) - 1)
