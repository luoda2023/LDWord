"""Presenter mixin for local question-figure library version history."""

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
    question_figure_library_version_history_entries,
    rollback_question_figure_library_metadata,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.theme import get_theme


class QuestionFigureLibraryHistoryPresenterMixin:
    """Render local metadata history and coordinate local rollback actions."""

    def _setup_question_figure_library_version_history_table(self, image_card) -> None:
        self._question_figure_library_version_history_table = QTableWidget(image_card)
        self._question_figure_library_version_history_table.setObjectName(
            "question_figure_asset_library_version_history_table"
        )
        self._question_figure_library_version_history_table.setColumnCount(5)
        self._question_figure_library_version_history_table.setHorizontalHeaderLabels(
            ["时间", "题目", "字段", "变更", "处理"]
        )
        self._question_figure_library_version_history_table.setSelectionBehavior(
            QTableWidget.SelectRows
        )
        self._question_figure_library_version_history_table.setSelectionMode(
            QTableWidget.SingleSelection
        )
        self._question_figure_library_version_history_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self._question_figure_library_version_history_table.itemSelectionChanged.connect(
            self._on_question_figure_library_version_history_selection_changed
        )
        self._question_figure_library_version_history_table.setAlternatingRowColors(True)
        self._question_figure_library_version_history_table.setShowGrid(False)
        self._question_figure_library_version_history_table.setWordWrap(True)
        self._question_figure_library_version_history_table.setMinimumHeight(72)
        self._question_figure_library_version_history_table.setMaximumHeight(150)
        self._question_figure_library_version_history_table.verticalHeader().setVisible(False)
        version_history_header = (
            self._question_figure_library_version_history_table.horizontalHeader()
        )
        version_history_header.setStretchLastSection(False)
        version_history_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        version_history_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        version_history_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        version_history_header.setSectionResizeMode(3, QHeaderView.Stretch)
        version_history_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._question_figure_library_version_history_table.setVisible(False)
        image_card.add_widget(self._question_figure_library_version_history_table)

    def _refresh_question_figure_library_version_history_table(self, asset_items) -> None:
        table = getattr(self, "_question_figure_library_version_history_table", None)
        if table is None:
            return
        profile = self._selected_profile()
        entries = question_figure_library_version_history_entries(
            profile.asset_item_history,
            asset_items,
        )
        was_blocked = table.blockSignals(True)
        table.setVisible(bool(entries))
        table.clearContents()
        table.setRowCount(len(entries))
        for row_index, (record_index, question_row_index, row) in enumerate(entries):
            for column, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, question_row_index)
                item.setData(Qt.UserRole + 1, record_index)
                item.setToolTip(str(value))
                table.setItem(row_index, column, item)
            button = QPushButton("\u56de\u6eda", table)
            apply_button_variant(button, "secondary")
            button.setStyleSheet(build_button_stylesheet(get_theme()))
            button.setToolTip(
                "\u6309\u8fd9\u6761\u7248\u672c\u8bb0\u5f55\u56de\u6eda"
                "\u9898\u56fe\u7d20\u6750 metadata"
            )
            button.clicked.connect(
                lambda *_args, selected_row=row_index: defer_qt_method(
                    self,
                    "_rollback_question_figure_library_version_history_row",
                    selected_row,
                    confirmed=True,
                )
            )
            table.setCellWidget(row_index, 4, button)
        table.blockSignals(was_blocked)
        table.resizeRowsToContents()

    def _on_question_figure_library_version_history_selection_changed(self) -> None:
        table = getattr(self, "_question_figure_library_version_history_table", None)
        if table is None:
            return
        self._select_question_figure_library_version_history_row(table.currentRow())

    def _select_question_figure_library_version_history_row(self, row_index: int) -> bool:
        table = getattr(self, "_question_figure_library_version_history_table", None)
        if table is None:
            return False
        if row_index < 0 or row_index >= table.rowCount():
            return False
        item = table.item(row_index, 0)
        try:
            question_row = int(item.data(Qt.UserRole) if item is not None else -1)
        except (TypeError, ValueError):
            return False
        return self._select_question_figure_library_issue_question_row(question_row)

    def _rollback_question_figure_library_version_history_row(
        self,
        row_index: int,
        *,
        confirmed: bool = False,
    ) -> bool:
        if not confirmed:
            return False
        table = getattr(self, "_question_figure_library_version_history_table", None)
        if table is None or row_index < 0 or row_index >= table.rowCount():
            return False
        item = table.item(row_index, 0)
        try:
            record_index = int(item.data(Qt.UserRole + 1) if item is not None else -1)
        except (TypeError, ValueError):
            return False
        profile = self._selected_profile()
        result = rollback_question_figure_library_metadata(
            self._asset_item_payloads,
            profile.asset_item_history,
            self._current_asset_items(),
            record_index,
        )
        if not bool(result.get("updated")):
            self._question_figure_library_status_label.setText(
                _ROLLBACK_STATUS_LABELS.get(
                    str(result.get("status") or ""),
                    "\u5386\u53f2\u8bb0\u5f55\u65e0\u6548\uff0c\u65e0\u6cd5\u56de\u6eda",
                )
            )
            return False
        snapshot = self._capture_question_figure_mutation_snapshot()
        if snapshot is None:
            return False
        self._asset_item_payloads = list(result.get("payloads") or [])
        profile.asset_item_history = [
            dict(record)
            for record in list(result.get("records") or [])
            if isinstance(record, dict)
        ]
        if not self._publish_question_figure_mutation(snapshot):
            return False
        self._refresh_summary()
        try:
            question_row = int(result.get("question_row", -1))
        except (TypeError, ValueError):
            question_row = -1
        self._select_question_figure_library_issue_question_row(question_row)
        self._question_figure_library_status_label.setText(
            _ROLLBACK_STATUS_LABELS["rolled_back"]
        )
        return True


_ROLLBACK_STATUS_LABELS = {
    "missing_record": "\u5386\u53f2\u8bb0\u5f55\u65e0\u6548\uff0c\u65e0\u6cd5\u56de\u6eda",
    "missing_item": "\u5386\u53f2\u8bb0\u5f55\u5bf9\u5e94\u9898\u56fe\u5df2\u4e0d\u5b58\u5728",
    "conflict": "\u7248\u672c\u5df2\u53d8\u66f4\uff0c\u65e0\u6cd5\u76f4\u63a5\u56de\u6eda",
    "no_change": "\u8be5\u5386\u53f2\u8bb0\u5f55\u65e0\u9700\u56de\u6eda",
    "not_structured": (
        "\u5386\u53f2\u8bb0\u5f55\u5bf9\u5e94\u9898\u56fe"
        "\u4e0d\u662f\u7ed3\u6784\u5316\u7d20\u6750\u6761\u76ee"
    ),
    "rolled_back": "\u9898\u56fe\u7d20\u6750\u7248\u672c\u5df2\u56de\u6eda",
}


__all__ = ["QuestionFigureLibraryHistoryPresenterMixin"]
