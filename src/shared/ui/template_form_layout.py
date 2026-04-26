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


def _label_control_width(widget: QWidget) -> int | None:
    preferred = getattr(widget, "preferred_label_width", None)
    setter = getattr(widget, "set_label_width", None)
    if not callable(preferred) or not callable(setter):
        return None
    return int(preferred())


def _current_label_width(widget: QWidget) -> int:
    width = getattr(widget, "label_width", None)
    return width if isinstance(width, int) else 0


def _iter_template_label_controls(widgets: Sequence[QWidget]) -> list[QWidget]:
    controls: list[QWidget] = []
    for widget in widgets:
        if _label_control_width(widget) is not None:
            controls.append(widget)
        nested = getattr(widget, "template_form_label_controls", None)
        if callable(nested):
            controls.extend(nested())
    return controls


def normalize_template_form_rows(widgets: Sequence[QWidget]) -> None:
    """Align label-bearing controls inside one visual group."""

    controls = _iter_template_label_controls(widgets)
    if not controls:
        return

    label_width = max(_label_control_width(control) or 0 for control in controls)
    for control in controls:
        if isinstance(control, FormRow):
            control.set_label_alignment(Qt.AlignLeft | Qt.AlignVCenter)
        control.set_label_width(max(_current_label_width(control), label_width))


def template_form_pair_row(
    left_row: QWidget,
    right_row: QWidget,
    *,
    parent=None,
    column_gap: int = 12,
    column_stretches: Sequence[int] = (1, 1),
    normalize_labels: bool = False,
) -> "TemplateFormGrid":
    """Build one shared two-column row using the template grid baseline."""

    if normalize_labels:
        normalize_template_form_rows([left_row, right_row])
    return TemplateFormGrid(
        [[left_row, right_row]],
        parent=parent,
        column_gap=column_gap,
        column_stretches=column_stretches,
    )


class TemplateFormStack(QWidget):
    """Single-column template form block with one shared label baseline."""

    def __init__(self, widgets: Sequence[QWidget], *, parent=None, spacing: int = 0):
        super().__init__(parent)
        self._widgets = tuple(widgets)
        normalize_template_form_rows(self._widgets)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(spacing)
        for widget in self._widgets:
            self._layout.addWidget(widget)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def template_form_label_controls(self) -> list[QWidget]:
        return _iter_template_label_controls(self._widgets)


class TemplateSplitColumns(QWidget):
    """Two-column form block matching the main template editor rhythm."""

    def __init__(
        self,
        left_widgets: Sequence[QWidget],
        right_widgets: Sequence[QWidget],
        *,
        parent=None,
        gutter_padding: int = 16,
        show_divider: bool = False,
    ):
        super().__init__(parent)
        self._left_column = self._build_column(left_widgets, right_padding=gutter_padding)
        self._right_column = self._build_column(right_widgets, left_padding=gutter_padding)
        self._divider = DashedSeparator(orientation="vertical", parent=self) if show_divider else None
        self._last_stacked: bool | None = None

        self._layout = QBoxLayout(QBoxLayout.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self._left_column, 1)
        if self._divider is not None:
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
        if self._divider is not None:
            self._divider.setVisible(not stacked)
        self.updateGeometry()

    def _stack_breakpoint(self) -> int:
        divider_gap = self._divider.sizeHint().width() if self._divider is not None else 13
        return (
            self._left_column.minimumSizeHint().width()
            + self._right_column.minimumSizeHint().width()
            + divider_gap
            + 24
        )

    def _apply_theme(self) -> None:
        if self._divider is not None:
            self._divider.set_color(get_theme().divider)


class TemplateFormGrid(QWidget):
    """Responsive rows for 2x2 and compact multi-column template forms."""

    def __init__(
        self,
        rows: Sequence[Sequence[QWidget]],
        *,
        parent=None,
        column_gap: int = 28,
        column_stretches: Sequence[int] | None = None,
        show_row_separators: bool = False,
    ):
        super().__init__(parent)
        self._rows = [tuple(row) for row in rows if row]
        self._column_stretches = tuple(column_stretches or ())
        self._separators: list[DashedSeparator] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._normalize_columns()
        for row_index, row in enumerate(self._rows):
            self._layout.addWidget(
                AdaptivePairRow(
                    *row,
                    parent=self,
                    spacing=column_gap,
                    stretches=self._stretches_for_row(row),
                )
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
        for row in self._rows:
            if len(row) > 2:
                normalize_template_form_rows(row)

    def _stretches_for_row(self, row: Sequence[QWidget]) -> tuple[int, ...]:
        if not self._column_stretches:
            return tuple(1 for _widget in row)
        return tuple(
            self._column_stretches[index] if index < len(self._column_stretches) else 1
            for index, _widget in enumerate(row)
        )

    def template_form_label_controls(self) -> list[QWidget]:
        return _iter_template_label_controls(
            [widget for row in self._rows for widget in row]
        )

    def _apply_theme(self) -> None:
        for separator in self._separators:
            separator.set_color(get_theme().border_light)


__all__ = [
    "TemplateFormGrid",
    "TemplateFormStack",
    "TemplateSplitColumns",
    "normalize_template_form_rows",
    "template_form_pair_row",
    "template_form_row",
]
