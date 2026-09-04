"""Responsive column geometry shared by time-node list rows."""

from __future__ import annotations

from dataclasses import dataclass

from src.qt_api import QFrame, QHBoxLayout, QLabel, QSizePolicy, Qt, Signal
from src.shared.ui.theme import bind_theme, get_theme


@dataclass(frozen=True, slots=True)
class TimelineNodeColumnMetrics:
    """One geometry contract for the time-node guide and its rows."""

    index_width: int
    position_width: int
    token_min_width: int
    result_min_width: int
    token_stretch: int
    result_stretch: int
    column_gap: int
    row_margin_x: int
    guide_visible: bool


def resolve_timeline_node_column_metrics(
    available_width: int,
) -> TimelineNodeColumnMetrics:
    """Resolve a compact, readable four-column time-node layout."""

    theme = get_theme()
    width = max(0, int(available_width))
    index_width = 38
    position_width = max(140, min(186, round(width * 0.15)))
    column_gap = int(theme.token_row_column_gap)
    row_margin_x = 4
    return TimelineNodeColumnMetrics(
        index_width=index_width,
        position_width=position_width,
        token_min_width=140,
        result_min_width=140,
        token_stretch=3,
        result_stretch=2,
        column_gap=column_gap,
        row_margin_x=row_margin_x,
        guide_visible=width >= 680,
    )


class TimelineNodeColumnGuide(QFrame):
    """Low-emphasis headers aligned with editable time-node rows."""

    metrics_changed = Signal(object)

    def __init__(self, *, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("timeline_node_column_guide")
        self._metrics: TimelineNodeColumnMetrics | None = None

        layout = QHBoxLayout(self)
        self.index_label = QLabel("序号", self)
        self.token_label = QLabel("时间字段", self)
        self.position_label = QLabel("位置（%）", self)
        self.result_label = QLabel("日期结果", self)
        self.index_label.setAlignment(Qt.AlignCenter)
        for label in (
            self.token_label,
            self.position_label,
            self.result_label,
        ):
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.token_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )
        self.result_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        layout.addWidget(self.index_label, 0)
        layout.addWidget(self.token_label, 3)
        layout.addWidget(self.position_label, 0)
        layout.addWidget(self.result_label, 2)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def metrics(self) -> TimelineNodeColumnMetrics:
        parent_width = self.parentWidget().width() if self.parentWidget() else 0
        return self._sync_metrics(max(self.width(), parent_width))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API contract
        self._sync_metrics(event.size().width())
        super().resizeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API contract
        self._sync_metrics(self.width(), force=True)
        super().showEvent(event)

    def _apply_theme(self) -> None:
        theme = get_theme()
        label_style = (
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_medium}; "
            f"color: {theme.text_hint}; background: transparent; border: none;"
        )
        for label in (
            self.index_label,
            self.token_label,
            self.position_label,
            self.result_label,
        ):
            label.setStyleSheet(label_style)
        self._sync_metrics(self.width(), force=True)

    def _sync_metrics(
        self,
        width: int,
        *,
        force: bool = False,
    ) -> TimelineNodeColumnMetrics:
        metrics = resolve_timeline_node_column_metrics(width)
        layout = self.layout()
        layout.setContentsMargins(
            metrics.row_margin_x,
            0,
            metrics.row_margin_x,
            0,
        )
        layout.setSpacing(metrics.column_gap)
        layout.setStretch(1, metrics.token_stretch)
        layout.setStretch(3, metrics.result_stretch)
        self.index_label.setFixedWidth(metrics.index_width)
        self.position_label.setFixedWidth(metrics.position_width)
        self.token_label.setMinimumWidth(metrics.token_min_width)
        self.token_label.setMaximumWidth(16777215)
        self.result_label.setMinimumWidth(metrics.result_min_width)
        self.result_label.setMaximumWidth(16777215)

        for label in (
            self.index_label,
            self.token_label,
            self.position_label,
            self.result_label,
        ):
            label.setVisible(metrics.guide_visible)
        guide_height = 32 if metrics.guide_visible else 0
        self.setMinimumHeight(guide_height)
        self.setMaximumHeight(guide_height)
        divider = get_theme().divider if metrics.guide_visible else "transparent"
        self.setStyleSheet(
            "QFrame#timeline_node_column_guide {"
            "background: transparent; border: none; "
            f"border-bottom: 1px solid {divider};"
            "}"
        )

        changed = force or metrics != self._metrics
        self._metrics = metrics
        if changed:
            self.metrics_changed.emit(metrics)
        return metrics


__all__ = [
    "TimelineNodeColumnGuide",
    "TimelineNodeColumnMetrics",
    "resolve_timeline_node_column_metrics",
]
