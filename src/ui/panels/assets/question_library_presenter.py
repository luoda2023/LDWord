"""Presenter mixin for local question-figure library metadata rows."""

from __future__ import annotations

from src.qt_api import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.services.material_assets import (
    apply_question_figure_library_metadata,
    asset_item_alt_text,
    asset_item_library_asset_id,
    asset_item_source,
    normalized_asset_item_history_records,
    question_figure_items,
    question_figure_library_row_entries,
    question_figure_target_label,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import get_theme


class QuestionFigureLibraryPresenterMixin:
    """Render and coordinate local question-figure library rows."""

    def _setup_question_figure_library_card(self, image_card) -> None:
        self._question_figure_library_table = QTableWidget(image_card)
        self._question_figure_library_table.setObjectName("question_figure_asset_library_table")
        self._question_figure_library_table.setColumnCount(6)
        self._question_figure_library_table.setHorizontalHeaderLabels(
            ["题目", "库来源", "素材ID", "本地/预览", "状态", "处理"]
        )
        self._question_figure_library_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._question_figure_library_table.setSelectionMode(QTableWidget.SingleSelection)
        self._question_figure_library_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._question_figure_library_table.itemSelectionChanged.connect(
            self._on_question_figure_library_selection_changed
        )
        self._question_figure_library_table.setAlternatingRowColors(True)
        self._question_figure_library_table.setShowGrid(False)
        self._question_figure_library_table.setWordWrap(True)
        self._question_figure_library_table.setMinimumHeight(72)
        self._question_figure_library_table.setMaximumHeight(150)
        self._question_figure_library_table.verticalHeader().setVisible(False)
        library_header = self._question_figure_library_table.horizontalHeader()
        library_header.setStretchLastSection(False)
        library_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        library_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        library_header.setSectionResizeMode(2, QHeaderView.Stretch)
        library_header.setSectionResizeMode(3, QHeaderView.Stretch)
        library_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        library_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._question_figure_library_table.setVisible(False)
        image_card.add_widget(self._question_figure_library_table)
        self._question_figure_library_editor = QWidget(image_card)
        self._question_figure_library_editor.setObjectName("question_figure_asset_library_editor")
        library_editor_layout = QVBoxLayout(self._question_figure_library_editor)
        library_editor_layout.setContentsMargins(0, 0, 0, 0)
        library_editor_layout.setSpacing(6)
        library_editor_inputs = QWidget(self._question_figure_library_editor)
        library_editor_inputs_layout = QHBoxLayout(library_editor_inputs)
        library_editor_inputs_layout.setContentsMargins(0, 0, 0, 0)
        library_editor_inputs_layout.setSpacing(8)
        self._question_figure_library_source_edit = QLineEdit(library_editor_inputs)
        self._question_figure_library_source_edit.setObjectName(
            "question_figure_asset_library_source_edit"
        )
        self._question_figure_library_source_edit.setPlaceholderText("库来源")
        self._question_figure_library_asset_id_edit = QLineEdit(library_editor_inputs)
        self._question_figure_library_asset_id_edit.setObjectName(
            "question_figure_asset_library_asset_id_edit"
        )
        self._question_figure_library_asset_id_edit.setPlaceholderText("素材ID")
        self._question_figure_library_alt_text_edit = QLineEdit(library_editor_inputs)
        self._question_figure_library_alt_text_edit.setObjectName(
            "question_figure_asset_library_alt_text_edit"
        )
        self._question_figure_library_alt_text_edit.setPlaceholderText("图片说明")
        self._question_figure_library_save_btn = QPushButton("保存", library_editor_inputs)
        self._question_figure_library_save_btn.clicked.connect(
            self._save_question_figure_library_metadata
        )
        apply_button_variant(self._question_figure_library_save_btn, "primary")
        self._question_figure_library_status_label = QLabel(self._question_figure_library_editor)
        self._question_figure_library_status_label.setObjectName(
            "question_figure_asset_library_status_label"
        )
        self._question_figure_library_status_label.setWordWrap(True)
        library_editor_inputs_layout.addWidget(self._question_figure_library_source_edit, 1)
        library_editor_inputs_layout.addWidget(self._question_figure_library_asset_id_edit, 1)
        library_editor_inputs_layout.addWidget(self._question_figure_library_alt_text_edit, 2)
        library_editor_inputs_layout.addWidget(self._question_figure_library_save_btn)
        library_editor_layout.addWidget(library_editor_inputs)
        library_editor_layout.addWidget(self._question_figure_library_status_label)
        self._question_figure_library_editor.setVisible(False)
        image_card.add_widget(self._question_figure_library_editor)

    def _refresh_question_figure_library_table(self, asset_items) -> None:
        table = getattr(self, "_question_figure_library_table", None)
        if table is None:
            return
        entries = question_figure_library_row_entries(asset_items)
        was_blocked = table.blockSignals(True)
        table.setVisible(bool(entries))
        table.clearContents()
        table.setRowCount(len(entries))
        selected_question_row = -1
        for row_index, (question_row_index, row) in enumerate(entries):
            for column, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, question_row_index)
                item.setToolTip(str(value))
                table.setItem(row_index, column, item)
            button = QPushButton("定位", table)
            apply_button_variant(button, "secondary")
            button.setStyleSheet(build_button_stylesheet(get_theme()))
            button.setToolTip("定位到这道题的素材")
            button.clicked.connect(
                lambda *_args, selected_row=row_index: self._select_question_figure_library_row(
                    selected_row
                )
            )
            table.setCellWidget(row_index, 5, button)
            if row_index == table.currentRow():
                selected_question_row = question_row_index
        table.blockSignals(was_blocked)
        table.resizeRowsToContents()
        self._refresh_question_figure_library_editor(selected_question_row)

    def _on_question_figure_library_selection_changed(self) -> None:
        table = getattr(self, "_question_figure_library_table", None)
        if table is None:
            return
        self._select_question_figure_library_row(table.currentRow())

    def _select_question_figure_library_row(self, row_index: int) -> bool:
        table = getattr(self, "_question_figure_library_table", None)
        question_table = getattr(self, "_question_figure_items_table", None)
        if table is None or question_table is None:
            return False
        if row_index < 0 or row_index >= table.rowCount():
            return False
        item = table.item(row_index, 0)
        question_row_index = item.data(Qt.UserRole) if item is not None else None
        try:
            question_row = int(question_row_index)
        except (TypeError, ValueError):
            return False
        if question_row < 0 or question_row >= question_table.rowCount():
            return False
        question_table.selectRow(question_row)
        self._on_question_figure_item_selection_changed()
        self._refresh_question_figure_library_editor(question_row)
        return True


    def _refresh_question_figure_library_editor(self, question_row: int = -1) -> None:
        editor = getattr(self, "_question_figure_library_editor", None)
        if editor is None:
            return
        question_items = question_figure_items(self._current_asset_items())
        has_row = 0 <= question_row < len(question_items)
        editor.setVisible(bool(question_items))
        source_edit = self._question_figure_library_source_edit
        asset_id_edit = self._question_figure_library_asset_id_edit
        alt_text_edit = self._question_figure_library_alt_text_edit
        widgets = (source_edit, asset_id_edit, alt_text_edit)
        for widget in widgets:
            widget.blockSignals(True)
        try:
            if has_row:
                item = question_items[question_row]
                source_edit.setText(asset_item_source(item))
                asset_id_edit.setText(asset_item_library_asset_id(item))
                alt_text_edit.setText(asset_item_alt_text(item))
                self._question_figure_library_status_label.setText(
                    f"\u6b63\u5728\u7f16\u8f91\uff1a{question_figure_target_label(item)}"
                )
            else:
                source_edit.setText("")
                asset_id_edit.setText("")
                alt_text_edit.setText("")
                self._question_figure_library_status_label.setText(
                    "\u9009\u62e9\u4e00\u6761\u9898\u56fe\u7d20\u6750\u540e\u7f16\u8f91"
                )
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        for widget in (*widgets, self._question_figure_library_save_btn):
            widget.setEnabled(has_row)

    def _save_question_figure_library_metadata(self) -> bool:
        table = getattr(self, "_question_figure_library_table", None)
        if table is None:
            return False
        row_index = table.currentRow()
        if row_index < 0 or row_index >= table.rowCount():
            self._refresh_question_figure_library_editor(-1)
            return False
        item = table.item(row_index, 0)
        try:
            question_row = int(item.data(Qt.UserRole) if item is not None else -1)
        except (TypeError, ValueError):
            return False
        question_items = question_figure_items(self._current_asset_items())
        if question_row < 0 or question_row >= len(question_items):
            return False
        result = apply_question_figure_library_metadata(
            self._asset_item_payloads,
            question_items[question_row],
            source=self._question_figure_library_source_edit.text(),
            asset_id=self._question_figure_library_asset_id_edit.text(),
            alt_text=self._question_figure_library_alt_text_edit.text(),
        )
        if not bool(result.get("updated")):
            self._question_figure_library_status_label.setText(
                "\u5f53\u524d\u9898\u56fe\u4e0d\u662f\u7ed3\u6784\u5316\u7d20\u6750\u6761\u76ee\uff0c\u6682\u65f6\u4e0d\u80fd\u7f16\u8f91"
            )
            return False
        snapshot = self._capture_question_figure_mutation_snapshot()
        if snapshot is None:
            return False
        profile = self._selected_profile()
        self._asset_item_payloads = list(result.get("payloads") or [])
        history_record = result.get("history_record")
        if history_record:
            profile.asset_item_history = [
                *normalized_asset_item_history_records(profile.asset_item_history),
                dict(history_record),
            ]
        if not self._publish_question_figure_mutation(snapshot):
            return False
        self._refresh_summary()
        if row_index < table.rowCount():
            table.selectRow(row_index)
        self._question_figure_library_status_label.setText(
            "\u9898\u56fe\u7d20\u6750\u4fe1\u606f\u5df2\u4fdd\u5b58"
        )
        return True

__all__ = ["QuestionFigureLibraryPresenterMixin"]
