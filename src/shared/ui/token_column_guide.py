"""Quiet, responsive column guidance for editable material-token rows."""

from __future__ import annotations

from dataclasses import dataclass

from src.qt_api import QFrame, QHBoxLayout, QLabel, QSizePolicy, Qt, Signal
from src.shared.ui.compact_row_actions import compact_row_actions_width
from src.shared.ui.theme import bind_theme, get_theme


@dataclass(frozen=True, slots=True)
class TokenColumnMetrics:
    """One geometry contract shared by a guide and all rows below it."""

    index_width: int
    token_width: int
    actions_width: int
    column_gap: int
    row_margin_x: int
    guide_visible: bool


def resolve_token_column_metrics(
    available_width: int,
    *,
    action_count: int = 3,
) -> TokenColumnMetrics:
    """Resolve stable column widths without inspecting row content."""

    theme = get_theme()
    width = max(0, int(available_width))
    index_width = 28
    actions_width = compact_row_actions_width(action_count, theme=theme)
    gap = int(theme.token_row_column_gap)
    margin_x = 4
    fixed_width = (
        margin_x * 2
        + index_width
        + actions_width
        + gap * 3
    )
    flexible_width = max(0, width - fixed_width)
    guide_visible = width >= 680
    if guide_visible:
        token_width = round(flexible_width * 0.36)
        token_width = max(240, min(360, token_width))
    else:
        token_width = round(flexible_width * 0.40)
        token_width = max(150, min(220, token_width))
    return TokenColumnMetrics(
        index_width=index_width,
        token_width=token_width,
        actions_width=actions_width,
        column_gap=gap,
        row_margin_x=margin_x,
        guide_visible=guide_visible,
    )


class TokenColumnGuide(QFrame):
    """Low-emphasis labels aligned to the interactive rows below."""

    metrics_changed = Signal(object)

    def __init__(
        self,
        *,
        index_text: str = "序号",
        token_text: str = "占位符",
        value_text: str = "字段内容",
        actions_text: str = "操作",
        action_count: int = 3,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("token_column_guide")
        self._action_count = max(0, int(action_count))
        self._metrics: TokenColumnMetrics | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)

        self.index_label = QLabel(index_text, self)
        self.token_label = QLabel(token_text, self)
        self.value_label = QLabel(value_text, self)
        self.actions_label = QLabel(actions_text, self)
        self.index_label.setAlignment(Qt.AlignCenter)
        self.token_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.actions_label.setAlignment(Qt.AlignCenter)
        self.value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout.addWidget(self.index_label, 0)
        layout.addWidget(self.token_label, 0)
        layout.addWidget(self.value_label, 1)
        layout.addWidget(self.actions_label, 0)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def metrics(self) -> TokenColumnMetrics:
        width = max(self.width(), self.parentWidget().width() if self.parentWidget() else 0)
        return self._sync_metrics(width)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._sync_metrics(event.size().width())
        super().resizeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
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
            self.value_label,
            self.actions_label,
        ):
            label.setStyleSheet(label_style)
        self._sync_metrics(self.width(), force=True)

    def _sync_metrics(
        self,
        width: int,
        *,
        force: bool = False,
    ) -> TokenColumnMetrics:
        metrics = resolve_token_column_metrics(
            width,
            action_count=self._action_count,
        )
        layout = self.layout()
        layout.setContentsMargins(metrics.row_margin_x, 0, metrics.row_margin_x, 0)
        layout.setSpacing(metrics.column_gap)
        self.index_label.setFixedWidth(metrics.index_width)
        self.token_label.setFixedWidth(metrics.token_width)
        self.actions_label.setFixedWidth(metrics.actions_width)

        for label in (
            self.index_label,
            self.token_label,
            self.value_label,
            self.actions_label,
        ):
            label.setVisible(metrics.guide_visible)
        guide_height = 32 if metrics.guide_visible else 0
        self.setMinimumHeight(guide_height)
        self.setMaximumHeight(guide_height)
        divider = get_theme().divider if metrics.guide_visible else "transparent"
        self.setStyleSheet(
            "QFrame#token_column_guide {"
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
    "TokenColumnGuide",
    "TokenColumnMetrics",
    "resolve_token_column_metrics",
]
