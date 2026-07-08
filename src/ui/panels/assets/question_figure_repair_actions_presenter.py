"""Presenter mixin for local question-figure repair actions."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from src.config.materials import AssetItem
from src.qt_api import QFileDialog, Qt
from src.services.material_assets import (
    append_question_figure_repair_audit_record,
    build_question_figure_repair_audit_record,
    build_question_figure_repair_rollback_audit_record,
    question_figure_items,
    question_figure_payload_matches_item,
    resolve_question_figure_repair_audit_dir,
)
from src.ui.panels.assets.common import _ui_utc_now_iso
from src.ui.panels.assets.items import _normalized_asset_item_payloads


class QuestionFigureRepairActionsPresenterMixin:
    """Apply local question-figure replacements and repair audit records."""

    def current_question_figure_repair_audit_records(self) -> list[dict[str, object]]:
        return [dict(record) for record in self._question_figure_repair_audit_records]

    def revert_question_figure_repair_audit_record(
        self,
        audit_record: Mapping[str, object],
        *,
        confirmed: bool = False,
    ) -> bool:
        if not confirmed or not isinstance(audit_record, Mapping):
            return False
        if str(audit_record.get("status") or "").strip() != "applied":
            return False
        if str(audit_record.get("action") or "").strip() != (
            "frontstage_question_figure_repair_apply"
        ):
            return False
        original_path = str(audit_record.get("original_path") or "").strip()
        if not original_path or not Path(original_path).is_file():
            return False
        row_index = self._question_figure_item_row_for_repair_audit_record(
            audit_record
        )
        if row_index < 0:
            return False
        question_items = question_figure_items(self._current_asset_items())
        if row_index >= len(question_items):
            return False
        current_item = question_items[row_index]
        current_path = str(getattr(current_item, "path", "") or "").strip()
        applied_path = str(audit_record.get("applied_path") or "").strip()
        if applied_path and current_path != applied_path:
            return False
        if not self._replace_question_figure_item_path(row_index, original_path):
            return False
        self._record_question_figure_repair_rollback(
            audit_record,
            rollback_from_item=current_item,
            rollback_path=original_path,
        )
        return True

    def _select_question_figure_library_issue_question_row(
        self,
        question_row: int,
    ) -> bool:
        library_table = getattr(self, "_question_figure_library_table", None)
        question_table = getattr(self, "_question_figure_items_table", None)
        if question_table is None:
            return False
        if library_table is not None:
            for library_row in range(library_table.rowCount()):
                library_item = library_table.item(library_row, 0)
                if library_item is None:
                    continue
                try:
                    library_question_row = int(library_item.data(Qt.UserRole))
                except (TypeError, ValueError):
                    continue
                if library_question_row == question_row:
                    library_table.selectRow(library_row)
                    self._select_question_figure_library_row(library_row)
                    return True
        if question_row < 0 or question_row >= question_table.rowCount():
            return False
        question_table.selectRow(question_row)
        self._on_question_figure_item_selection_changed()
        self._refresh_question_figure_library_editor(question_row)
        return True

    def _select_question_figure_item_file(self, row_index: int) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "替换题目图片",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff);;All Files (*)",
        )
        if not file_path:
            return
        self._replace_question_figure_item_path(row_index, file_path)

    def _replace_question_figure_item_path(self, row_index: int, path: str) -> bool:
        new_path = str(path or "").strip()
        if not new_path:
            return False
        question_items = question_figure_items(self._current_asset_items())
        if row_index < 0 or row_index >= len(question_items):
            return False
        target = question_items[row_index]
        payloads = _normalized_asset_item_payloads(self._asset_item_payloads)
        updated = False
        for payload in payloads:
            if question_figure_payload_matches_item(payload, target):
                payload["path"] = new_path
                updated = True
                break
        if not updated:
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText(
                    "当前题图不是结构化题图条目，暂不能在明细表中替换。"
                )
            return False
        self._asset_item_payloads = payloads
        self._persist_current_profile_editor()
        self._refresh_summary()
        table = getattr(self, "_question_figure_items_table", None)
        if table is not None and row_index < table.rowCount():
            table.selectRow(row_index)
        self._sync_material_batch_selection()
        self._set_image_preview(new_path, role="question_figure")
        return True

    def apply_question_figure_repair_candidate(
        self,
        candidate: Mapping[str, object],
        *,
        confirmed: bool = False,
    ) -> bool:
        if not confirmed or not isinstance(candidate, Mapping):
            return False
        if str(candidate.get("confirmation_status") or "").strip() != "ready":
            return False
        if not bool(candidate.get("confirmation_apply_supported")):
            return False
        replacement_path = str(candidate.get("replacement_source_path") or "").strip()
        if not replacement_path or not Path(replacement_path).is_file():
            return False
        target_key = str(candidate.get("repair_target_key") or "").strip()
        row_index = self._question_figure_item_row_for_target(target_key)
        if row_index < 0:
            return False
        question_items = question_figure_items(self._current_asset_items())
        if row_index >= len(question_items):
            return False
        original_item = question_items[row_index]
        if not self._replace_question_figure_item_path(row_index, replacement_path):
            return False
        self._record_question_figure_repair_application(
            candidate,
            original_item=original_item,
            replacement_path=replacement_path,
        )
        return True

    def _record_question_figure_repair_application(
        self,
        candidate: Mapping[str, object],
        *,
        original_item: AssetItem,
        replacement_path: str,
    ) -> dict[str, object]:
        self._persist_current_profile_editor()
        profile = self._selected_profile()
        archive_id = self._archive_id_edit.text().strip()
        archive_name = self._archive_name_edit.text().strip()
        applied_at = _ui_utc_now_iso()
        audit_dir = resolve_question_figure_repair_audit_dir(
            profile.assets_dir,
            str(getattr(original_item, "path", "") or ""),
            replacement_path,
        )
        record = build_question_figure_repair_audit_record(
            candidate,
            original_item=original_item,
            replacement_path=replacement_path,
            archive_id=archive_id,
            archive_name=archive_name,
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            applied_at=applied_at,
        )
        record = append_question_figure_repair_audit_record(audit_dir, record)
        self._question_figure_repair_audit_records.append(dict(record))
        self._question_figure_repair_audit_records = (
            self._question_figure_repair_audit_records[-100:]
        )
        return record

    def _record_question_figure_repair_rollback(
        self,
        audit_record: Mapping[str, object],
        *,
        rollback_from_item: AssetItem,
        rollback_path: str,
    ) -> dict[str, object]:
        self._persist_current_profile_editor()
        profile = self._selected_profile()
        archive_id = self._archive_id_edit.text().strip()
        archive_name = self._archive_name_edit.text().strip()
        rolled_back_at = _ui_utc_now_iso()
        audit_dir = resolve_question_figure_repair_audit_dir(
            profile.assets_dir,
            str(audit_record.get("original_path") or ""),
            str(audit_record.get("applied_path") or ""),
        )
        record = build_question_figure_repair_rollback_audit_record(
            audit_record,
            rollback_from_item=rollback_from_item,
            rollback_path=rollback_path,
            archive_id=archive_id,
            archive_name=archive_name,
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            rolled_back_at=rolled_back_at,
        )
        record = append_question_figure_repair_audit_record(audit_dir, record)
        self._question_figure_repair_audit_records.append(dict(record))
        self._question_figure_repair_audit_records = (
            self._question_figure_repair_audit_records[-100:]
        )
        return record


__all__ = ["QuestionFigureRepairActionsPresenterMixin"]
