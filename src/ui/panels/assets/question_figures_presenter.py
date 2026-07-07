"""Presenter mixin for local question-figure item rows."""

from __future__ import annotations

from src.qt_api import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    Qt,
)
from src.services.material_assets import (
    asset_item_preview_reference,
    asset_item_source,
    question_figure_compare_options,
    question_figure_detail_rows,
    question_figure_items,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import get_theme


class QuestionFigureItemsPresenterMixin:
    """Render and coordinate local question-figure item rows."""

    def _setup_question_figure_items_table(self, image_card) -> None:
        self._question_figure_items_table = QTableWidget(image_card)
        self._question_figure_items_table.setObjectName("question_figure_asset_items_table")
        self._question_figure_items_table.setColumnCount(5)
        self._question_figure_items_table.setHorizontalHeaderLabels(["题目", "图片", "说明", "状态", "处理"])
        self._question_figure_items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._question_figure_items_table.setSelectionMode(QTableWidget.SingleSelection)
        self._question_figure_items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._question_figure_items_table.itemSelectionChanged.connect(
            self._on_question_figure_item_selection_changed
        )
        self._question_figure_items_table.setAlternatingRowColors(True)
        self._question_figure_items_table.setShowGrid(False)
        self._question_figure_items_table.setWordWrap(True)
        self._question_figure_items_table.setMinimumHeight(96)
        self._question_figure_items_table.setMaximumHeight(180)
        self._question_figure_items_table.verticalHeader().setVisible(False)
        question_header = self._question_figure_items_table.horizontalHeader()
        question_header.setStretchLastSection(False)
        question_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        question_header.setSectionResizeMode(1, QHeaderView.Stretch)
        question_header.setSectionResizeMode(2, QHeaderView.Stretch)
        question_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        question_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._question_figure_items_table.setVisible(False)
        image_card.add_widget(self._question_figure_items_table)

    def _refresh_question_figure_items_table(self, asset_items) -> None:
        table = getattr(self, "_question_figure_items_table", None)
        if table is None:
            return
        rows = question_figure_detail_rows(asset_items)
        question_items = question_figure_items(asset_items)
        was_blocked = table.blockSignals(True)
        table.setVisible(bool(rows))
        table.clearContents()
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            preview_reference = (
                asset_item_preview_reference(question_items[row_index])
                if row_index < len(question_items)
                else ""
            )
            preview_source = (
                asset_item_source(question_items[row_index])
                if row_index < len(question_items)
                else ""
            )
            preview_kind = ""
            compare_reference = ""
            compare_display_name = ""
            for column, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, preview_reference)
                item.setData(Qt.UserRole + 1, preview_source)
                item.setData(Qt.UserRole + 2, preview_kind)
                item.setData(Qt.UserRole + 3, compare_reference)
                item.setData(Qt.UserRole + 4, preview_source)
                item.setData(Qt.UserRole + 5, compare_display_name)
                item.setToolTip(str(value))
                table.setItem(row_index, column, item)
            button = QPushButton("替换", table)
            apply_button_variant(button, "secondary")
            button.setStyleSheet(build_button_stylesheet(get_theme()))
            button.setToolTip("替换这一题的图片")
            button.clicked.connect(
                lambda *_args, selected_row=row_index: self._select_question_figure_item_file(
                    selected_row
                )
            )
            table.setCellWidget(row_index, 4, button)
        table.blockSignals(was_blocked)
        table.resizeRowsToContents()

    def _on_question_figure_item_selection_changed(self) -> None:
        table = getattr(self, "_question_figure_items_table", None)
        if table is None:
            return
        row = table.currentRow()
        if row < 0:
            return
        item = table.item(row, 0)
        preview_reference = str(item.data(Qt.UserRole) if item is not None else "").strip()
        preview_source = str(item.data(Qt.UserRole + 1) if item is not None else "").strip()
        preview_kind = str(item.data(Qt.UserRole + 2) if item is not None else "").strip()
        compare_reference = str(item.data(Qt.UserRole + 3) if item is not None else "").strip()
        compare_source = str(item.data(Qt.UserRole + 4) if item is not None else "").strip()
        compare_display_name = str(item.data(Qt.UserRole + 5) if item is not None else "").strip()
        compare_options = question_figure_compare_options(
            question_figure_items(self._current_asset_items()),
            row,
        )
        if not preview_reference:
            return
        self._set_image_preview(preview_reference, role="question_figure")
        self._set_current_image_preview_path(
            preview_reference,
            compare_reference=compare_reference,
            compare_source=compare_source,
            compare_display_name=compare_display_name,
            compare_options=compare_options,
            question_figure_row=row,
        )

__all__ = ["QuestionFigureItemsPresenterMixin"]
