"""Shared column guidance and geometry for image material rows."""

from __future__ import annotations

from dataclasses import dataclass

from src.qt_api import QFrame, QHBoxLayout, QLabel, QSizePolicy, Qt, Signal
from src.shared.ui.compact_row_actions import compact_row_actions_width
from src.shared.ui.theme import bind_theme, get_theme


@dataclass(frozen=True, slots=True)
class AssetColumnMetrics:
    index_width: int
    preview_width: int
    token_width: int
    name_width: int
    actions_width: int
    column_gap: int
    row_margin_x: int
    guide_visible: bool
    source_visible: bool


def resolve_asset_column_metrics(
    available_width: int,
    *,
    action_count: int,
) -> AssetColumnMetrics:
    """Resolve one deterministic geometry contract for guide and rows."""

    theme = get_theme()
    width = max(0, int(available_width))
    margin_x = 4
    gap = int(theme.token_row_column_gap)
    index_width = 34
    preview_width = 52
    actions_width = compact_row_actions_width(action_count, theme=theme)
    # Keep the navigational labels available at ordinary laptop/DPI widths.
    # The optional source column is what collapses first; hiding the complete
    # guide below 900px made every remaining column lose its meaning as well.
    guide_visible = width >= 680
    source_visible = width >= 900

    if source_visible:
        flexible = max(
            0,
            width
            - margin_x * 2
            - index_width
            - preview_width
            - actions_width
            - gap * 5,
        )
        token_width = max(160, min(250, round(flexible * 0.25)))
        name_width = max(180, min(280, round(flexible * 0.28)))
        minimum_source = 140
        overflow = max(0, token_width + name_width + minimum_source - flexible)
        if overflow:
            trim_token = min(overflow // 2, max(0, token_width - 130))
            token_width -= trim_token
            overflow -= trim_token
            name_width -= min(overflow, max(0, name_width - 150))
    else:
        flexible = max(
            0,
            width
            - margin_x * 2
            - index_width
            - preview_width
            - actions_width
            - gap * 4,
        )
        token_width = max(80, min(220, round(flexible * 0.44)))
        name_width = max(0, flexible - token_width)

    return AssetColumnMetrics(
        index_width=index_width,
        preview_width=preview_width,
        token_width=token_width,
        name_width=name_width,
        actions_width=actions_width,
        column_gap=gap,
        row_margin_x=margin_x,
        guide_visible=guide_visible,
        source_visible=source_visible,
    )


class AssetColumnGuide(QFrame):
    """Quiet labels aligned to image inventory rows below."""

    metrics_changed = Signal(object)

    def __init__(
        self,
        *,
        source_text: str,
        action_count: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("asset_column_guide")
        self._action_count = max(0, int(action_count))
        self._metrics: AssetColumnMetrics | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        self.index_label = QLabel("序号", self)
        self.preview_label = QLabel("预览", self)
        self.token_label = QLabel("占位符", self)
        self.name_label = QLabel("名称", self)
        self.source_label = QLabel(source_text, self)
        self.actions_label = QLabel("操作", self)
        for label in (
            self.index_label,
            self.preview_label,
            self.actions_label,
        ):
            label.setAlignment(Qt.AlignCenter)
        for label in (self.token_label, self.name_label, self.source_label):
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.source_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout.addWidget(self.index_label, 0)
        layout.addWidget(self.preview_label, 0)
        layout.addWidget(self.token_label, 0)
        layout.addWidget(self.name_label, 0)
        layout.addWidget(self.source_label, 1)
        layout.addWidget(self.actions_label, 0)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def metrics(self) -> AssetColumnMetrics:
        width = max(self.width(), self.parentWidget().width() if self.parentWidget() else 0)
        return self._sync_metrics(width)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._sync_metrics(event.size().width())
        super().resizeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        self._sync_metrics(self.width(), force=True)
        super().showEvent(event)

    def _apply_theme(self) -> None:
        theme = get_theme()
        style = (
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_medium}; color: {theme.text_hint}; "
            "background: transparent; border: none;"
        )
        for label in (
            self.index_label,
            self.preview_label,
            self.token_label,
            self.name_label,
            self.source_label,
            self.actions_label,
        ):
            label.setStyleSheet(style)
        self._sync_metrics(self.width(), force=True)

    def _sync_metrics(
        self,
        width: int,
        *,
        force: bool = False,
    ) -> AssetColumnMetrics:
        metrics = resolve_asset_column_metrics(
            width,
            action_count=self._action_count,
        )
        layout = self.layout()
        layout.setContentsMargins(metrics.row_margin_x, 0, metrics.row_margin_x, 0)
        layout.setSpacing(metrics.column_gap)
        self.index_label.setFixedWidth(metrics.index_width)
        self.preview_label.setFixedWidth(metrics.preview_width)
        self.token_label.setFixedWidth(metrics.token_width)
        self.name_label.setFixedWidth(metrics.name_width)
        self.actions_label.setFixedWidth(metrics.actions_width)
        for label in (
            self.index_label,
            self.preview_label,
            self.token_label,
            self.name_label,
            self.actions_label,
        ):
            label.setVisible(metrics.guide_visible)
        self.source_label.setVisible(
            metrics.guide_visible and metrics.source_visible
        )
        height = 32 if metrics.guide_visible else 0
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)
        divider = get_theme().divider if metrics.guide_visible else "transparent"
        self.setStyleSheet(
            "QFrame#asset_column_guide {"
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
    "AssetColumnGuide",
    "AssetColumnMetrics",
    "resolve_asset_column_metrics",
]
