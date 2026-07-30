"""Presenter mixin for local question-figure repair actions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping

from src.config.materials import AssetItem, is_supported_image_path
from src.qt_api import QFileDialog, Qt
from src.shared.ui.toast import Toast
from src.services.material_assets import (
    append_question_figure_repair_audit_record,
    build_question_figure_repair_audit_record,
    build_question_figure_repair_rollback_audit_record,
    question_figure_items,
    question_figure_payload_matches_item,
    resolve_question_figure_repair_audit_dir,
)
from src.ui.panels.assets.common import _ui_utc_now_iso
from src.ui.panels.assets.image_helpers import _image_file_dialog_filter
from src.ui.panels.assets.items import _normalized_asset_item_payloads
from src.ui.panels.assets.mutation_transaction import (
    capture_material_mutation_snapshot,
    publish_or_rollback_material_mutation,
)


_LOGGER = logging.getLogger(__name__)


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
            _image_file_dialog_filter(),
        )
        if not file_path:
            return
        self._replace_question_figure_item_path(row_index, file_path)

    def _replace_question_figure_item_path(self, row_index: int, path: str) -> bool:
        new_path = str(path or "").strip()
        if not new_path:
            return False
        if not is_supported_image_path(new_path):
            Toast.show_warning("所选文件不是受支持的图片，请重新选择。")
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
        snapshot = self._capture_question_figure_mutation_snapshot()
        if snapshot is None:
            return False
        self._asset_item_payloads = payloads
        if not self._publish_question_figure_mutation(snapshot):
            return False
        self._refresh_summary()
        table = getattr(self, "_question_figure_items_table", None)
        if table is not None and row_index < table.rowCount():
            table.selectRow(row_index)
        self._set_image_preview(new_path, role="question_figure")
        return True

    def _capture_question_figure_mutation_snapshot(self):
        if not self._persist_current_profile_editor():
            return None

        def current_row(name: str) -> int:
            table = getattr(self, name, None)
            return table.currentRow() if table is not None else -1

        def text(name: str) -> str | None:
            widget = getattr(self, name, None)
            return widget.text() if widget is not None else None

        return capture_material_mutation_snapshot(
            local_state={
                "asset_item_payloads": self._asset_item_payloads,
                "question_row": current_row("_question_figure_items_table"),
                "library_row": current_row("_question_figure_library_table"),
                "history_row": current_row(
                    "_question_figure_library_version_history_table"
                ),
                "image_status_text": text("_image_assets_status_label"),
                "library_status_text": text(
                    "_question_figure_library_status_label"
                ),
                "library_source_text": text(
                    "_question_figure_library_source_edit"
                ),
                "library_asset_id_text": text(
                    "_question_figure_library_asset_id_edit"
                ),
                "library_alt_text": text(
                    "_question_figure_library_alt_text_edit"
                ),
            },
            profile_state=self._selected_profile(),
            profile_index=self._current_profile_index,
            batch_selection=self.bridge.current_material_batch_selection(),
        )

    def _publish_question_figure_mutation(self, snapshot) -> bool:
        return publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_question_figure_mutation_selection,
            restore_profile=self._restore_question_figure_mutation_profile,
            restore_local=self._restore_question_figure_mutation_local,
            refresh=lambda: self._refresh_question_figure_mutation_ui(
                snapshot.local_state
            ),
        )

    def _restore_question_figure_mutation_selection(self, selection) -> None:
        self.bridge.set_current_material_batch_selection(selection)

    def _restore_question_figure_mutation_profile(self, index: int, profile) -> None:
        self._profiles[index] = profile
        self._update_profile_item(index)

    def _restore_question_figure_mutation_local(self, state) -> None:
        self._asset_item_payloads = state["asset_item_payloads"]

    def _refresh_question_figure_mutation_ui(self, state) -> None:
        self._refresh_summary()
        library_table = getattr(self, "_question_figure_library_table", None)
        library_row = int(state["library_row"])
        question_row = int(state["question_row"])
        if (
            library_table is not None
            and 0 <= library_row < library_table.rowCount()
        ):
            library_table.selectRow(library_row)
            self._select_question_figure_library_row(library_row)
        else:
            question_table = getattr(self, "_question_figure_items_table", None)
            if (
                question_table is not None
                and 0 <= question_row < question_table.rowCount()
            ):
                question_table.selectRow(question_row)
                self._on_question_figure_item_selection_changed()
                self._refresh_question_figure_library_editor(question_row)

        history_table = getattr(
            self,
            "_question_figure_library_version_history_table",
            None,
        )
        history_row = int(state["history_row"])
        if history_table is not None and 0 <= history_row < history_table.rowCount():
            blocked = history_table.blockSignals(True)
            try:
                history_table.selectRow(history_row)
            finally:
                history_table.blockSignals(blocked)

        for name, key in (
            ("_question_figure_library_source_edit", "library_source_text"),
            ("_question_figure_library_asset_id_edit", "library_asset_id_text"),
            ("_question_figure_library_alt_text_edit", "library_alt_text"),
            ("_image_assets_status_label", "image_status_text"),
            ("_question_figure_library_status_label", "library_status_text"),
        ):
            widget = getattr(self, name, None)
            value = state[key]
            if widget is not None and value is not None:
                widget.setText(value)

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
        record = self._append_question_figure_repair_audit_best_effort(
            audit_dir,
            record,
        )
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
        record = self._append_question_figure_repair_audit_best_effort(
            audit_dir,
            record,
        )
        self._question_figure_repair_audit_records.append(dict(record))
        self._question_figure_repair_audit_records = (
            self._question_figure_repair_audit_records[-100:]
        )
        return record

    def _append_question_figure_repair_audit_best_effort(
        self,
        audit_dir: Path | None,
        record: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            stored = append_question_figure_repair_audit_record(audit_dir, record)
        except Exception:
            _LOGGER.warning(
                "Question-figure mutation succeeded but audit artifact write failed.",
                exc_info=True,
            )
            stored = {
                **dict(record),
                "artifact_path": "",
                "audit_persistence_status": "failed",
                "audit_persistence_error": "persistence_exception",
            }
        persistence_failed = (
            str(stored.get("audit_persistence_status") or "") == "failed"
            or (
                audit_dir is not None
                and not str(stored.get("artifact_path") or "")
            )
        )
        if persistence_failed:
            Toast.show_warning(
                "题图操作已生效，但审计未完整落盘；"
                "本次记录已保留在当前会话。"
            )
        return stored


__all__ = ["QuestionFigureRepairActionsPresenterMixin"]
