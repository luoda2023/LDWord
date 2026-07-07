"""Presenter mixin for local question-figure metadata issue rows."""

from __future__ import annotations

from src.qt_api import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    Qt,
)
from src.services.material_assets import question_figure_library_metadata_issue_entries
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import get_theme


class QuestionFigureLibraryIssuePresenterMixin:
    """Render local metadata issues for question-figure library rows."""

    def _setup_question_figure_library_issue_table(self, image_card) -> None:
        self._question_figure_library_issue_table = QTableWidget(image_card)
        self._question_figure_library_issue_table.setObjectName(
            "question_figure_asset_library_issue_table"
        )
        self._question_figure_library_issue_table.setColumnCount(5)
        self._question_figure_library_issue_table.setHorizontalHeaderLabels(
            ["问题", "题目", "库来源", "素材ID", "定位"]
        )
        self._question_figure_library_issue_table.setSelectionBehavior(
            QTableWidget.SelectRows
        )
        self._question_figure_library_issue_table.setSelectionMode(
            QTableWidget.SingleSelection
        )
        self._question_figure_library_issue_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self._question_figure_library_issue_table.itemSelectionChanged.connect(
            self._on_question_figure_library_issue_selection_changed
        )
        self._question_figure_library_issue_table.setAlternatingRowColors(True)
        self._question_figure_library_issue_table.setShowGrid(False)
        self._question_figure_library_issue_table.setWordWrap(True)
        self._question_figure_library_issue_table.setMinimumHeight(72)
        self._question_figure_library_issue_table.setMaximumHeight(150)
        self._question_figure_library_issue_table.verticalHeader().setVisible(False)
        issue_header = self._question_figure_library_issue_table.horizontalHeader()
        issue_header.setStretchLastSection(False)
        issue_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        issue_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        issue_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        issue_header.setSectionResizeMode(3, QHeaderView.Stretch)
        issue_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._question_figure_library_issue_table.setVisible(False)
        image_card.add_widget(self._question_figure_library_issue_table)

    def _refresh_question_figure_library_issue_table(self, asset_items) -> None:
        table = getattr(self, "_question_figure_library_issue_table", None)
        if table is None:
            return
        entries = question_figure_library_metadata_issue_entries(asset_items)
        was_blocked = table.blockSignals(True)
        table.setVisible(bool(entries))
        table.clearContents()
        table.setRowCount(len(entries))
        for row_index, (question_row_index, row) in enumerate(entries):
            for column, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, question_row_index)
                item.setToolTip(str(value))
                table.setItem(row_index, column, item)
            button = QPushButton("\u5b9a\u4f4d", table)
            apply_button_variant(button, "secondary")
            button.setStyleSheet(build_button_stylesheet(get_theme()))
            button.setToolTip(
                "\u5b9a\u4f4d\u5230\u9700\u8981\u68c0\u67e5\u7684"
                "\u9898\u56fe\u7d20\u6750"
            )
            button.clicked.connect(
                lambda *_args, selected_row=row_index: (
                    self._select_question_figure_library_issue_row(selected_row)
                )
            )
            table.setCellWidget(row_index, 4, button)
        table.blockSignals(was_blocked)
        table.resizeRowsToContents()

    def _on_question_figure_library_issue_selection_changed(self) -> None:
        table = getattr(self, "_question_figure_library_issue_table", None)
        if table is None:
            return
        self._select_question_figure_library_issue_row(table.currentRow())

    def _select_question_figure_library_issue_row(self, row_index: int) -> bool:
        table = getattr(self, "_question_figure_library_issue_table", None)
        if table is None:
            return False
        if row_index < 0 or row_index >= table.rowCount():
            return False
        item = table.item(row_index, 0)
        question_row_index = item.data(Qt.UserRole) if item is not None else None
        try:
            question_row = int(question_row_index)
        except (TypeError, ValueError):
            return False
        return self._select_question_figure_library_issue_question_row(question_row)


__all__ = ["QuestionFigureLibraryIssuePresenterMixin"]
