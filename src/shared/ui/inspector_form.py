"""Inspector form primitives for third-level detail panels."""

from __future__ import annotations

from collections.abc import Sequence

from src.qt_api import QSizePolicy, QVBoxLayout, QWidget

from src.shared.ui.template_form_layout import (
    TemplateFormGrid,
    TemplateSplitColumns,
    compact_form_column_gap,
    normalize_template_form_rows,
    template_form_row,
)


class InspectorForm(QWidget):
    """One label-width scope for a section/card form.

    Panels should use this when several rows visually belong to the same card.
    It keeps the label column normalized across single rows, grids, and split
    columns, so controls start from the same x-coordinate inside the section.
    """

    def __init__(self, *, parent=None, spacing: int = 0):
        super().__init__(parent)
        self._items: list[QWidget] = []
        self._label_scope: list[QWidget] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(spacing)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def add_field(
        self,
        label: str,
        widget: QWidget,
        *,
        suffix_widget: QWidget | None = None,
        label_width: int | None = None,
    ):
        row = template_form_row(
            label,
            widget,
            suffix_widget=suffix_widget,
            label_width=label_width,
            parent=self,
        )
        self.add_widget(row)
        return row

    def add_pair(
        self,
        *rows: QWidget,
        column_gap: int | None = None,
        column_stretches: Sequence[int] | None = None,
    ) -> TemplateFormGrid:
        resolved_gap = self._resolve_column_gap(column_gap, column_stretches)
        grid = TemplateFormGrid(
            [rows],
            parent=self,
            column_gap=resolved_gap,
            column_stretches=column_stretches,
        )
        self.add_widget(grid)
        return grid

    def add_grid(
        self,
        rows: Sequence[Sequence[QWidget | None]],
        *,
        column_gap: int | None = None,
        column_stretches: Sequence[int] | None = None,
    ) -> TemplateFormGrid:
        resolved_gap = self._resolve_column_gap(column_gap, column_stretches)
        grid = TemplateFormGrid(
            [self._normalize_grid_row(row) for row in rows],
            parent=self,
            column_gap=resolved_gap,
            column_stretches=column_stretches,
        )
        self.add_widget(grid)
        return grid

    def add_split_columns(
        self,
        left_widgets: Sequence[QWidget],
        right_widgets: Sequence[QWidget],
        *,
        gutter_padding: int = 16,
        show_divider: bool = False,
    ) -> TemplateSplitColumns:
        split = TemplateSplitColumns(
            left_widgets,
            right_widgets,
            parent=self,
            gutter_padding=gutter_padding,
            show_divider=show_divider,
        )
        self.add_widget(split)
        return split

    def add_widget(self, widget: QWidget) -> QWidget:
        self._items.append(widget)
        self._label_scope.append(widget)
        self._layout.addWidget(widget)
        self._normalize_label_scope()
        return widget

    def _normalize_label_scope(self) -> None:
        normalize_template_form_rows(self._label_scope)
        for item in self._label_scope:
            refresh = getattr(item, "refresh_template_form_alignment", None)
            if callable(refresh):
                refresh()

    def _empty_cell(self) -> QWidget:
        cell = QWidget(self)
        cell.setMinimumSize(0, 0)
        cell.setFixedHeight(0)
        cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        return cell

    def placeholder_cell(self) -> QWidget:
        """Return an explicit empty grid cell that still reserves its column."""

        return self._empty_cell()

    def _normalize_grid_row(self, row: Sequence[QWidget | None]) -> list[QWidget]:
        cells = list(row)
        while cells and cells[-1] is None:
            cells.pop()
        return [widget if widget is not None else self._empty_cell() for widget in cells]

    def _resolve_column_gap(
        self,
        column_gap: int | None,
        column_stretches: Sequence[int] | None,
    ) -> int | None:
        if column_gap is not None:
            return column_gap
        if column_stretches and all(int(stretch) <= 0 for stretch in column_stretches):
            return compact_form_column_gap()
        return None

    def template_form_label_controls(self) -> list[QWidget]:
        controls: list[QWidget] = []
        for item in self._label_scope:
            nested = getattr(item, "template_form_label_controls", None)
            if callable(nested):
                controls.extend(nested())
            else:
                controls.append(item)
        return controls


__all__ = ["InspectorForm"]
