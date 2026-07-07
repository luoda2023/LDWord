"""Shared summary card for template detail panes."""

from __future__ import annotations

from collections.abc import Sequence

from src.qt_api import QPushButton, QSize, QSizePolicy, QTimer
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.layout_sync import refresh_layout_chain
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem
from src.shared.ui.template_summary_header import DetailSummaryHeader
from src.shared.ui.theme import get_theme


_UNBOUNDED_HEIGHT = 16777215


def apply_detail_summary_action_button(
    button: QPushButton,
    variant: str,
) -> QPushButton:
    """Apply the compact action-button contract used in detail summary headers."""

    theme = get_theme()
    button.setIconSize(QSize(16, 16))
    button.setStyleSheet(
        build_button_stylesheet(
            theme,
            selector="QPushButton",
            min_height=28,
            padding_x=12,
            padding_y=3,
            font_size=theme.font_size_sm,
        )
    )
    apply_button_variant(button, variant)
    return button


apply_template_summary_action_button = apply_detail_summary_action_button


class DetailSummaryCard(Card):
    """Card containing a detail summary header and module summary grid."""

    def __init__(
        self,
        title: str,
        icon_name: str,
        *,
        columns: int = 12,
        compact_header: bool = False,
        parent=None,
    ):
        super().__init__(parent=parent)
        self._syncing_content_height_limit = False
        self._content_height_sync_queued = False
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.header = DetailSummaryHeader(
            title,
            icon_name,
            compact=compact_header,
            parent=self,
        )
        self.header.setMinimumWidth(0)
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.add_widget(self.header)
        self.summary_grid = SummaryGrid(
            columns=columns,
            tile_style="module",
            layout_policy="single_row_preferred",
            parent=self,
        )
        self.summary_grid.setMinimumWidth(0)
        self.summary_grid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.summary_grid.setVisible(False)
        self.add_widget(self.summary_grid)
        self._sync_content_height_limit()

    def add_control(self, widget) -> None:
        self.header.add_control(widget)

    def add_action(self, widget) -> None:
        self.header.add_action(widget)

    def set_summary_items(self, items: Sequence[SummaryGridItem]) -> None:
        normalized_items = tuple(items)
        self.summary_grid.setVisible(bool(normalized_items))
        self.summary_grid.set_items(normalized_items)
        self._sync_content_height_limit()
        self._queue_content_height_sync()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_content_height_limit()
        self._queue_content_height_sync()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_content_height_limit()
        self._queue_content_height_sync()

    def _queue_content_height_sync(self) -> None:
        if self._content_height_sync_queued:
            return
        self._content_height_sync_queued = True
        QTimer.singleShot(0, self._run_queued_content_height_sync)

    def _run_queued_content_height_sync(self) -> None:
        self._content_height_sync_queued = False
        try:
            self._sync_content_height_limit()
        except RuntimeError:
            # Qt may deliver a queued sync after the C++ widget has been deleted.
            return

    def _sync_content_height_limit(self) -> None:
        height = self._content_height_hint()
        if height <= 0:
            return
        height_limits_current = (
            self.minimumHeight() == height
            and self.maximumHeight() == _UNBOUNDED_HEIGHT
        )
        if height_limits_current and self.height() == height:
            return

        if not height_limits_current:
            self.setMinimumHeight(height)
            if self.maximumHeight() != _UNBOUNDED_HEIGHT:
                self.setMaximumHeight(_UNBOUNDED_HEIGHT)
        self.updateGeometry()
        if self._syncing_content_height_limit:
            return

        parent = self.parentWidget()
        parent_layout = parent.layout() if parent is not None else None
        if parent_layout is None:
            return

        self._syncing_content_height_limit = True
        try:
            parent_layout.invalidate()
            parent_layout.activate()
            refresh_layout_chain(parent, passes=2)
        finally:
            self._syncing_content_height_limit = False

    def _content_height_hint(self) -> int:
        layout = self.layout()
        if layout is None:
            return max(0, self._content_layout_height_hint())

        margins = layout.contentsMargins()
        return max(
            0,
            margins.top()
            + self._content_layout_height_hint()
            + margins.bottom(),
        )

    def _content_layout_height_hint(self) -> int:
        margins = self._content_layout.contentsMargins()
        height = margins.top() + margins.bottom()
        visible_items = 0
        for index in range(self._content_layout.count()):
            item = self._content_layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            if visible_items:
                height += max(0, self._content_layout.spacing())
            if widget is self.summary_grid:
                height += self.summary_grid.content_height_hint(
                    self._summary_grid_width_hint()
                )
            else:
                height += max(0, item.sizeHint().height())
            visible_items += 1
        return height

    def _summary_grid_width_hint(self) -> int:
        if self.width() <= 0:
            return max(0, self.summary_grid._layout_width_hint())
        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else None
        horizontal_margins = 0 if margins is None else margins.left() + margins.right()
        return max(0, self.width() - horizontal_margins)


class TemplateSummaryCard(DetailSummaryCard):
    """Backward-compatible name for template detail panes."""


__all__ = [
    "DetailSummaryCard",
    "TemplateSummaryCard",
    "apply_detail_summary_action_button",
    "apply_template_summary_action_button",
]
