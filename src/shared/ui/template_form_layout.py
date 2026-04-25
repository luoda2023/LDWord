"""Shared form layout primitives for template detail panes."""

from __future__ import annotations

from collections.abc import Sequence

from src.qt_api import QBoxLayout, QSizePolicy, QVBoxLayout, QWidget, Qt

from src.shared.ui.adaptive_pair_row import AdaptivePairRow
from src.shared.ui.dashed_separator import DashedSeparator
from src.shared.ui.form_row import FormRow
from src.shared.ui.theme import bind_theme, get_theme


def template_form_row(
    label: str,
    widget: QWidget,
    *,
    suffix_widget: QWidget | None = None,
    label_width: int | None = None,
    parent=None,
) -> FormRow:
    """Build a template-detail row with the compact left-label baseline."""

    row = FormRow(
        label,
        widget,
        suffix_widget=suffix_widget,
        label_width=label_width,
        label_alignment=Qt.AlignLeft | Qt.AlignVCenter,
        parent=parent,
    )
    if label_width is None:
        row.set_label_width(row.preferred_label_width())
    return row


def normalize_template_form_rows(widgets: Sequence[QWidget]) -> None:
    """Align labels inside one visual column without hard-coded widths."""

    rows = [widget for widget in widgets if isinstance(widget, FormRow)]
    if not rows:
        return

    label_width = max(row.preferred_label_width() for row in rows)
    for row in rows:
        row.set_label_alignment(Qt.AlignLeft | Qt.AlignVCenter)
        row.set_label_width(max(row.label_width or 0, label_width))


class TemplateSplitColumns(QWidget):
    """Two-column form block matching the main template editor rhythm."""

    def __init__(
        self,
        left_widgets: Sequence[QWidget],
        right_widgets: Sequence[QWidget],
        *,
        parent=None,
        gutter_padding: int = 22,
    ):
        super().__init__(parent)
        self._left_column = self._build_column(left_widgets, right_padding=gutter_padding)
        self._right_column = self._build_column(right_widgets, left_padding=gutter_padding)
        self._divider = DashedSeparator(orientation="vertical", parent=self)
        self._last_stacked: bool | None = None

        self._layout = QBoxLayout(QBoxLayout.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self._left_column, 1)
        self._layout.addWidget(self._divider, 0)
        self._layout.addWidget(self._right_column, 1)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        bind_theme(self, self._apply_theme)
        self._apply_theme()
        self._sync_direction()

    def _build_column(
        self,
        widgets: Sequence[QWidget],
        *,
        left_padding: int = 0,
        right_padding: int = 0,
    ) -> QWidget:
        normalize_template_form_rows(widgets)
        column = QWidget(self)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(left_padding, 0, right_padding, 0)
        layout.setSpacing(0)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        return column

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
        self._divider.setVisible(not stacked)
        self.updateGeometry()

    def _stack_breakpoint(self) -> int:
        return (
            self._left_column.minimumSizeHint().width()
            + self._right_column.minimumSizeHint().width()
            + self._divider.sizeHint().width()
            + 24
        )

    def _apply_theme(self) -> None:
        self._divider.set_color(get_theme().border_light)


class TemplateFormGrid(QWidget):
    """Responsive rows for 2x2 and compact multi-column template forms."""

    def __init__(
        self,
        rows: Sequence[Sequence[QWidget]],
        *,
        parent=None,
        column_gap: int = 28,
        show_row_separators: bool = True,
    ):
        super().__init__(parent)
        self._rows = [tuple(row) for row in rows if row]
        self._separators: list[DashedSeparator] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._normalize_columns()
        for row_index, row in enumerate(self._rows):
            self._layout.addWidget(
                AdaptivePairRow(*row, parent=self, spacing=column_gap)
            )
            if show_row_separators and row_index < len(self._rows) - 1:
                separator = DashedSeparator(orientation="horizontal", parent=self)
                self._separators.append(separator)
                self._layout.addWidget(separator)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def _normalize_columns(self) -> None:
        column_count = max((len(row) for row in self._rows), default=0)
        for column_index in range(column_count):
            normalize_template_form_rows(
                [row[column_index] for row in self._rows if column_index < len(row)]
            )

    def _apply_theme(self) -> None:
        for separator in self._separators:
            separator.set_color(get_theme().border_light)


__all__ = [
    "TemplateFormGrid",
    "TemplateSplitColumns",
    "normalize_template_form_rows",
    "template_form_row",
]
