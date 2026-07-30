"""Responsive row that keeps widgets side-by-side until space gets tight."""

from __future__ import annotations

from collections.abc import Sequence

from src.qt_api import QBoxLayout, QEvent, QSize, QSizePolicy, QWidget
from src.shared.ui.layout_sync import refresh_layout_chain


class AdaptivePairRow(QWidget):
    """Lay out peer widgets horizontally, then stack them vertically on narrow widths."""

    def __init__(
        self,
        *widgets: QWidget,
        parent=None,
        spacing: int = 12,
        stacked_spacing: int | None = 0,
        stretches: Sequence[int] | None = None,
        stack_slack: int = 0,
        minimum_breakpoint: bool = False,
    ):
        super().__init__(parent)
        self._widgets = list(widgets)
        self._inline_spacing = int(spacing)
        self._stacked_spacing = self._inline_spacing if stacked_spacing is None else int(stacked_spacing)
        self._stack_slack = max(0, int(stack_slack))
        self._minimum_breakpoint = bool(minimum_breakpoint)
        provided_stretches = tuple(stretches or ())
        self._stretches = tuple(
            provided_stretches[index] if index < len(provided_stretches) else 1
            for index, _widget in enumerate(self._widgets)
        )
        self._layout = QBoxLayout(QBoxLayout.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self._inline_spacing)
        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Expanding)
        policy.setVerticalPolicy(QSizePolicy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        for index, widget in enumerate(self._widgets):
            stretch = self._stretches[index] if index < len(self._stretches) else 1
            if int(stretch) <= 0:
                policy = widget.sizePolicy()
                policy.setHorizontalPolicy(QSizePolicy.Maximum)
                widget.setSizePolicy(policy)
            widget.installEventFilter(self)
            self._layout.addWidget(widget, int(stretch))
        if self._widgets and all(int(stretch) <= 0 for stretch in self._stretches):
            self._layout.addStretch(1)
        self._forced_stacked: bool | None = None
        self._last_stacked: bool | None = None
        self._sync_direction()

    def resizeEvent(self, event) -> None:
        self._sync_direction()
        self._sync_height_floor()
        super().resizeEvent(event)

    def showEvent(self, event) -> None:
        self._sync_direction()
        self._sync_height_floor()
        super().showEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if watched in self._widgets and event.type() in (QEvent.Show, QEvent.Hide):
            self._last_stacked = None
            self._sync_direction()
            parent_sync = getattr(self.parentWidget(), "_sync_responsive_mode", None)
            if callable(parent_sync):
                parent_sync()
            refresh_layout_chain(self, passes=2)
        return super().eventFilter(watched, event)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API contract
        """Report the narrow stacked minimum instead of the current row width.

        Parent layouts ask for minimum sizes before this widget has a chance to
        resize and switch direction. Returning the horizontal minimum here would
        prevent the parent from ever becoming narrow enough to trigger stacking.
        """
        widths, heights = self._visible_widget_extents(minimum=True)
        if not widths:
            return super().minimumSizeHint()
        margins = self._layout.contentsMargins()
        stacked = self._layout.direction() == QBoxLayout.TopToBottom
        spacing = self._stacked_spacing * max(0, len(heights) - 1)
        height = sum(heights) + spacing if stacked else max(heights)
        return QSize(
            max(widths) + margins.left() + margins.right(),
            height + margins.top() + margins.bottom(),
        )

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API contract
        stacked = self._layout.direction() == QBoxLayout.TopToBottom
        return self._layout_size(stacked=stacked, minimum=False)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API contract
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API contract
        return self.height_for_width(width)

    def height_for_width(self, width: int, *, stacked: bool | None = None) -> int:
        return self._layout_size(
            stacked=self._stacked_for_width(width) if stacked is None else bool(stacked),
            minimum=False,
        ).height()

    def set_forced_stacked(self, stacked: bool | None) -> None:
        """Let a parent grid coordinate one responsive mode across peer rows."""

        normalized = None if stacked is None else bool(stacked)
        if normalized == self._forced_stacked:
            return
        self._forced_stacked = normalized
        self._last_stacked = None
        self._sync_direction()

    def responsive_breakpoint(self) -> int:
        """Return the minimum usable inline width for this row."""

        return self._stack_breakpoint()

    def visible_widget_count(self) -> int:
        return len(self._visible_widgets())

    def _sync_direction(self) -> None:
        stacked = self._stacked_for_width(self.width())
        if stacked == self._last_stacked:
            return
        self._last_stacked = stacked
        self._layout.setDirection(QBoxLayout.TopToBottom if stacked else QBoxLayout.LeftToRight)
        self._layout.setSpacing(self._stacked_spacing if stacked else self._inline_spacing)
        self._sync_height_floor(stacked=stacked)
        self.updateGeometry()
        refresh_layout_chain(self, passes=2)

    def _sync_height_floor(self, *, stacked: bool | None = None) -> None:
        if stacked is None:
            stacked = self._layout.direction() == QBoxLayout.TopToBottom
        height = max(0, self._layout_size(stacked=stacked, minimum=False).height())
        if height > 0 and self.minimumHeight() != height:
            self.setMinimumHeight(height)

    def _stack_breakpoint(self) -> int:
        if self._minimum_breakpoint:
            widths = [
                max(widget.minimumWidth(), widget.minimumSizeHint().width())
                for widget in self._visible_widgets()
            ]
        else:
            widths = [
                max(widget.minimumSizeHint().width(), widget.sizeHint().width())
                for widget in self._visible_widgets()
            ]
        if not widths:
            return 0
        ideal_width = sum(widths) + self._inline_spacing * (len(widths) - 1)
        return max(max(widths), ideal_width - self._stack_slack)

    def _stacked_for_width(self, width: int) -> bool:
        if self._forced_stacked is not None:
            return self._forced_stacked
        return int(width or 0) < self._stack_breakpoint()

    def _layout_size(self, *, stacked: bool, minimum: bool) -> QSize:
        widths, heights = self._visible_widget_extents(minimum=minimum)
        if not widths:
            return super().sizeHint()
        margins = self._layout.contentsMargins()
        spacing = (
            (self._stacked_spacing if stacked else self._inline_spacing)
            * max(0, len(widths) - 1)
        )
        if stacked:
            width = max(widths)
            height = sum(heights) + spacing
        else:
            width = sum(widths) + spacing
            height = max(heights)
        return QSize(
            width + margins.left() + margins.right(),
            height + margins.top() + margins.bottom(),
        )

    def _visible_widget_extents(self, *, minimum: bool) -> tuple[list[int], list[int]]:
        widths: list[int] = []
        heights: list[int] = []
        for widget in self._visible_widgets():
            hint = widget.minimumSizeHint() if minimum else widget.sizeHint()
            min_hint = widget.minimumSizeHint()
            widths.append(max(0, widget.minimumWidth(), min_hint.width(), hint.width()))
            heights.append(max(0, widget.minimumHeight(), min_hint.height(), hint.height()))
        return widths, heights

    def _visible_widgets(self) -> list[QWidget]:
        return [widget for widget in self._widgets if not widget.isHidden()]
