"""Presenter mixin for local question-figure version consistency rows."""

from __future__ import annotations

from typing import Mapping, Sequence

from src.qt_api import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    Qt,
)
from src.services.material_assets import question_figure_library_master_version_entries
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import get_theme


class QuestionFigureLibraryMasterVersionPresenterMixin:
    """Render read-only local version-consistency rows and locate affected assets."""

    def _setup_question_figure_library_master_version_table(self, image_card) -> None:
        self._question_figure_library_master_version_table = QTableWidget(image_card)
        self._question_figure_library_master_version_table.setObjectName(
            "question_figure_asset_library_master_version_table"
        )
        self._question_figure_library_master_version_table.setColumnCount(6)
        self._question_figure_library_master_version_table.setHorizontalHeaderLabels(
            ["素材键", "资料包", "版本", "差异", "状态", "定位"]
        )
        self._question_figure_library_master_version_table.setSelectionBehavior(
            QTableWidget.SelectRows
        )
        self._question_figure_library_master_version_table.setSelectionMode(
            QTableWidget.SingleSelection
        )
        self._question_figure_library_master_version_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self._question_figure_library_master_version_table.itemSelectionChanged.connect(
            self._on_question_figure_library_master_version_selection_changed
        )
        self._question_figure_library_master_version_table.setAlternatingRowColors(True)
        self._question_figure_library_master_version_table.setShowGrid(False)
        self._question_figure_library_master_version_table.setWordWrap(True)
        self._question_figure_library_master_version_table.setMinimumHeight(72)
        self._question_figure_library_master_version_table.setMaximumHeight(150)
        self._question_figure_library_master_version_table.verticalHeader().setVisible(False)
        master_version_header = (
            self._question_figure_library_master_version_table.horizontalHeader()
        )
        master_version_header.setStretchLastSection(False)
        master_version_header.setSectionResizeMode(0, QHeaderView.Stretch)
        master_version_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        master_version_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        master_version_header.setSectionResizeMode(3, QHeaderView.Stretch)
        master_version_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        master_version_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._question_figure_library_master_version_table.setVisible(False)
        image_card.add_widget(self._question_figure_library_master_version_table)

    def _refresh_question_figure_library_master_version_table(self) -> None:
        table = getattr(self, "_question_figure_library_master_version_table", None)
        if table is None:
            return
        entries = question_figure_library_master_version_entries(self._profiles)
        was_blocked = table.blockSignals(True)
        table.setVisible(bool(entries))
        table.clearContents()
        table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            master_key = str(entry.get("master_key") or "")
            row = (
                master_key,
                str(entry.get("package_summary") or ""),
                str(entry.get("version_summary") or ""),
                str(entry.get("diff_summary") or ""),
                str(entry.get("status_label") or ""),
            )
            for column, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, master_key)
                item.setToolTip(str(value))
                table.setItem(row_index, column, item)
            focus_button = QPushButton("\u5b9a\u4f4d", table)
            apply_button_variant(focus_button, "secondary")
            focus_button.setStyleSheet(build_button_stylesheet(get_theme()))
            focus_button.setToolTip(
                "\u5b9a\u4f4d\u5230\u9996\u4e2a"
                "\u7248\u672c\u4e0d\u4e00\u81f4\u7684\u9898\u56fe\u7d20\u6750"
            )
            focus_button.clicked.connect(
                lambda *_args, selected_row=row_index: (
                    self._select_question_figure_library_master_version_row(selected_row)
                )
            )
            table.setCellWidget(row_index, 5, focus_button)
        table.blockSignals(was_blocked)
        table.resizeRowsToContents()

    def _on_question_figure_library_master_version_selection_changed(self) -> None:
        table = getattr(self, "_question_figure_library_master_version_table", None)
        if table is None:
            return
        self._select_question_figure_library_master_version_row(table.currentRow())

    def _question_figure_library_master_version_entry_for_row(
        self,
        row_index: int,
    ) -> dict[str, object] | None:
        table = getattr(self, "_question_figure_library_master_version_table", None)
        if table is None or row_index < 0 or row_index >= table.rowCount():
            return None
        item = table.item(row_index, 0)
        master_key = str(item.data(Qt.UserRole) if item is not None else "").strip()
        if not master_key:
            return None
        for entry in question_figure_library_master_version_entries(self._profiles):
            if str(entry.get("master_key") or "") == master_key:
                return dict(entry)
        return None

    def _select_question_figure_library_master_version_row(self, row_index: int) -> bool:
        entry = self._question_figure_library_master_version_entry_for_row(row_index)
        if not entry:
            return False
        occurrences = entry.get("occurrences")
        if not isinstance(occurrences, Sequence) or isinstance(occurrences, (str, bytes)):
            return False
        first = next(
            (dict(item) for item in occurrences if isinstance(item, Mapping)),
            None,
        )
        if not first:
            return False
        try:
            profile_index = int(first.get("profile_index", -1))
            question_row = int(first.get("question_row", -1))
        except (TypeError, ValueError):
            return False
        if profile_index < 0 or profile_index >= len(self._profiles):
            return False
        if profile_index != self._current_profile_index:
            self._profile_list.setCurrentRow(profile_index)
        if question_row >= 0:
            return self._select_question_figure_library_issue_question_row(
                question_row
            )
        return False


__all__ = ["QuestionFigureLibraryMasterVersionPresenterMixin"]
