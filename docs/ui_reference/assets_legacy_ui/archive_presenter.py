"""Presenter mixin for archive package actions in the assets panel."""

from __future__ import annotations

import copy
import logging
from pathlib import Path

from src.config.entity import (
    EntityArchive,
    EntityProfile,
    clone_entity_profile,
    load_entity_archive,
    save_entity_archive,
)
from src.config.material_package_library import (
    MaterialPackageLibraryEntry,
    create_material_package_in_library_with_receipt,
    delete_material_package_entry,
    duplicate_material_package_entry_with_receipt,
    list_material_package_entries,
    load_material_package_entry,
    material_package_library_watch_dirs,
    material_package_user_dir,
)
from src.config.material_schema_registry import resolve_material_schema_ids
from src.qt_api import (
    QDesktopServices,
    QLineEdit,
    QUrl,
    Qt,
)
from src.shared.ui.card import Card
from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.dialogs import confirm, input_text
from src.shared.ui.library_action_row import LibraryActionRow
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.toast import Toast
from src.services.material_assets import (
    normalized_asset_item_history_records as _normalized_asset_item_history_records,
)
from src.ui.panels.assets.items import (
    _normalized_asset_item_payloads,
    _normalized_asset_metadata,
)
from src.ui.panels.assets.fields import _format_fields_text


_LOGGER = logging.getLogger(__name__)


class ProfileEditorPersistenceRejected(RuntimeError):
    """The current profile editor could not be committed to its model."""


class ArchivePresenterMixin:
    """Coordinate the folder-backed archive package selection."""

    def _setup_archive_overview_card(self) -> None:
        archive_card = Card(parent=self._section_contents["generate"])
        self._archive_card = archive_card
        archive_card.set_header("当前资料包", icon_name="package")
        self._archive_id_edit = QLineEdit(archive_card)
        self._archive_name_edit = QLineEdit(archive_card)
        self._archive_id_edit.setVisible(False)
        self._archive_name_edit.setVisible(False)
        self._archive_id_edit.setPlaceholderText("资料包编号")
        self._archive_name_edit.setPlaceholderText("资料包名称")
        self._archive_id_edit.textChanged.connect(lambda *_: self._refresh_summary())
        self._archive_name_edit.textChanged.connect(lambda *_: self._refresh_summary())

        self._archive_combo = StyledComboBox(archive_card)
        self._archive_combo.setObjectName("assets_overview_archive_combo")
        self._archive_combo.set_full_width_mode(True)
        self._archive_combo.currentIndexChanged.connect(self._on_archive_selector_changed)
        self._archive_combo.popup_about_to_show.connect(
            self._refresh_archive_selector_from_library
        )
        archive_card.add_widget(self._archive_combo)

        self._archive_action_row = LibraryActionRow(
            archive_card,
            object_name="assets_overview_archive_action_row",
        )
        self._new_archive_btn = self._archive_action_row.add_action(
            "new",
            "新建资料包",
            object_name="assets_overview_new_archive_btn",
            icon_name="plus",
            callback=self._new_archive,
        )
        self._duplicate_archive_btn = self._archive_action_row.add_action(
            "duplicate",
            "创建副本",
            object_name="assets_overview_duplicate_archive_btn",
            icon_name="copy",
            callback=self._duplicate_archive,
        )
        self._rename_archive_btn = self._archive_action_row.add_action(
            "rename",
            "重命名资料包",
            object_name="assets_overview_rename_archive_btn",
            icon_name="pencil-line",
            callback=self._rename_archive,
        )
        self._open_archive_folder_btn = self._archive_action_row.add_action(
            "open_folder",
            "打开资料包文件夹",
            object_name="assets_overview_open_archive_folder_btn",
            icon_name="folder-open",
            callback=self._open_archive_folder,
        )
        self._delete_archive_btn = self._archive_action_row.add_action(
            "delete",
            "删除资料包",
            object_name="assets_overview_delete_archive_btn",
            icon_name="trash-2",
            variant="ghost-danger",
            side="right",
            callback=self._delete_archive,
        )
        archive_card.add_widget(self._archive_action_row)
        self._section_layouts["generate"].addWidget(archive_card)

    def current_archive(self) -> EntityArchive:
        if not self._persist_current_profile_editor():
            raise ProfileEditorPersistenceRejected(
                "material_profile_editor_persistence_rejected"
            )
        return self._current_archive_snapshot()

    def _current_archive_snapshot(self) -> EntityArchive:
        """Project the already-persisted editor model without a second commit."""

        current_mode = str(self.bridge.current_work_mode_id() or "").strip()
        current_scene = self.bridge.current_scene()
        input_profile = getattr(current_scene, "input_source_profile", None)
        schema_ids = resolve_material_schema_ids(
            str(getattr(input_profile, "material_schema_id", "") or ""),
            list(getattr(input_profile, "material_schema_ids", []) or []),
        )
        return EntityArchive(
            archive_id=(
                str(
                    getattr(
                        self._material_persistence.current_entry,
                        "package_id",
                        "",
                    )
                    or ""
                )
                or self._archive_id_edit.text().strip()
            ),
            archive_name=self._archive_name_edit.text().strip(),
            profiles=[
                clone_entity_profile(
                    profile,
                    asset_metadata=_normalized_asset_metadata(profile.asset_metadata),
                    asset_items=_normalized_asset_item_payloads(profile.asset_items),
                    asset_item_history=_normalized_asset_item_history_records(
                        profile.asset_item_history
                    ),
                )
                for profile in self._profiles
            ],
            mode_id=current_mode,
            package_id=(
                str(
                    getattr(
                        self._material_persistence.current_entry,
                        "package_id",
                        "",
                    )
                    or ""
                )
                or self._archive_id_edit.text().strip()
                or self._archive_name_edit.text().strip()
            ),
            material_schema_ids=[str(item) for item in schema_ids if str(item).strip()],
        )

    def _capture_archive_editor_transaction_snapshot(self) -> dict[str, object]:
        archive = self._current_archive_snapshot()
        editor_archive_id = self._archive_id_edit.text().strip()
        archive.archive_id = editor_archive_id
        archive.archive_name = self._archive_name_edit.text().strip()
        if editor_archive_id:
            archive.package_id = editor_archive_id
        get_selection = getattr(
            self.bridge,
            "current_material_batch_selection",
            None,
        )
        return {
            "archive": archive,
            "profile_index": int(self._current_profile_index),
            "profile_check_states": tuple(
                self._profile_list.item(index).checkState()
                for index in range(self._profile_list.count())
                if self._profile_list.item(index) is not None
            ),
            "task_field_values": copy.deepcopy(self._task_field_values),
            "last_material_context": copy.deepcopy(
                self._last_received_material_context
            ),
            "last_removed_official_field": copy.deepcopy(
                getattr(self, "_last_removed_official_field", None)
            ),
            "entry": copy.deepcopy(self._material_persistence.current_entry),
            "current_path": self._material_persistence.current_path,
            "persisted_snapshot": copy.deepcopy(
                self._material_persistence.persisted_snapshot
            ),
            "archive_combo_index": (
                int(self._archive_combo.currentIndex())
                if hasattr(self, "_archive_combo")
                else -1
            ),
            "batch_selection": (
                get_selection() if callable(get_selection) else None
            ),
        }

    def _apply_archive_editor_state(
        self,
        archive: EntityArchive,
        *,
        select_index: int,
        profile_check_states: tuple[object, ...] | None = None,
    ) -> None:
        self._task_field_values = {}
        self._last_received_material_context = None
        self._profiles = [
            clone_entity_profile(
                profile,
                asset_metadata=_normalized_asset_metadata(profile.asset_metadata),
                asset_items=_normalized_asset_item_payloads(profile.asset_items),
                asset_item_history=_normalized_asset_item_history_records(
                    profile.asset_item_history
                ),
            )
            for profile in archive.profiles
        ] or [EntityProfile()]
        self._current_profile_index = max(
            0,
            min(int(select_index), len(self._profiles) - 1),
        )
        self._archive_id_edit.blockSignals(True)
        self._archive_name_edit.blockSignals(True)
        try:
            self._archive_id_edit.setText(archive.archive_id)
            self._archive_name_edit.setText(archive.archive_name)
        finally:
            self._archive_name_edit.blockSignals(False)
            self._archive_id_edit.blockSignals(False)
        selected_profile_fields = copy.deepcopy(
            self._profiles[self._current_profile_index].fields
        )
        self._reload_profile_list(select_index=self._current_profile_index)
        # Summary refreshes that run while rows are being rebuilt can harvest
        # an incomplete editor.  Restore the package model captured before the
        # rebuild, then project any values without a concrete row below.
        self._profiles[self._current_profile_index].fields = selected_profile_fields
        # Some package fields are intentionally not materialized as structured
        # rows for the current scene/document.  Keep those package-owned values
        # in the generic editor; otherwise the next persistence harvest silently
        # drops them after a save, discard rollback, or package reload.
        represented_keys = {
            *getattr(self, "_field_inputs", {}).keys(),
            *getattr(self, "_template_field_inputs", {}).keys(),
        }
        unrendered_fields = {
            str(key): str(value)
            for key, value in dict(selected_profile_fields or {}).items()
            if str(key).strip()
            and str(value or "").strip()
            and str(key) not in represented_keys
        }
        if unrendered_fields:
            self._fields_edit.set_text(_format_fields_text(unrendered_fields))
        if profile_check_states is not None:
            was_syncing = self._syncing_profile_list
            signals_blocked = self._profile_list.blockSignals(True)
            self._syncing_profile_list = True
            try:
                for index, check_state in enumerate(profile_check_states):
                    item = self._profile_list.item(index)
                    if item is not None:
                        item.setCheckState(check_state)
            finally:
                self._syncing_profile_list = was_syncing
                self._profile_list.blockSignals(signals_blocked)
            self._refresh_profile_item_labels()

    def _restore_archive_editor_transaction_snapshot(
        self,
        snapshot: dict[str, object],
        *,
        restore_selection: bool = True,
    ) -> None:
        self._material_persistence.replace_identity(
            copy.deepcopy(snapshot.get("entry")),
            str(snapshot.get("current_path") or ""),
        )
        self._material_persistence.replace_persisted_snapshot(
            copy.deepcopy(snapshot.get("persisted_snapshot"))
        )
        try:
            self._apply_archive_editor_state(
                copy.deepcopy(snapshot["archive"]),
                select_index=int(snapshot.get("profile_index") or 0),
                profile_check_states=tuple(
                    snapshot.get("profile_check_states") or ()
                ),
            )
            self._task_field_values = copy.deepcopy(
                snapshot.get("task_field_values") or {}
            )
            self._last_received_material_context = copy.deepcopy(
                snapshot.get("last_material_context")
            )
            self._last_removed_official_field = copy.deepcopy(
                snapshot.get("last_removed_official_field")
            )
            self._sync_official_remove_undo_buttons()
            if hasattr(self, "_archive_combo"):
                signals_blocked = self._archive_combo.blockSignals(True)
                try:
                    self._archive_combo.setCurrentIndex(
                        int(snapshot.get("archive_combo_index") or 0)
                    )
                finally:
                    self._archive_combo.blockSignals(signals_blocked)
            self._material_persistence.refresh_actions()
            self._refresh_summary()
        finally:
            if restore_selection:
                selection = snapshot.get("batch_selection")
                set_selection = getattr(
                    self.bridge,
                    "set_current_material_batch_selection",
                    None,
                )
                if selection is not None and callable(set_selection):
                    set_selection(selection)

    def set_archive(self, archive: EntityArchive, *, select_index: int = 0) -> bool:
        try:
            if not self._persist_current_profile_editor():
                return False
            snapshot = self._capture_archive_editor_transaction_snapshot()
        except Exception:
            _LOGGER.exception("failed to snapshot archive editor before replacement")
            self._material_persistence.fail_closed_actions()
            return False

        try:
            self._apply_archive_editor_state(
                archive,
                select_index=select_index,
            )
            published = self._sync_material_batch_selection()
        except Exception:
            _LOGGER.exception("failed to apply or publish archive editor replacement")
            self._material_persistence.fail_closed_actions()
            published = False
        if published:
            return True
        try:
            self._restore_archive_editor_transaction_snapshot(snapshot)
        except Exception as exc:
            _LOGGER.exception("failed to restore rejected archive editor replacement")
            self._material_persistence.fail_closed_actions()
            Toast.show_error(f"回滚资料包切换失败: {exc}")
        return False

    def save_archive_to_path(self, path: str | Path) -> None:
        save_entity_archive(self.current_archive(), path)

    def load_archive_from_path(self, path: str | Path) -> EntityArchive:
        archive = load_entity_archive(path)
        self.set_archive(archive)
        return archive

    def _archive_display_name(self) -> str:
        return self._archive_name_edit.text().strip() or "未命名资料包"

    def _sync_archive_selector(self) -> None:
        if not hasattr(self, "_archive_combo"):
            return
        current_path = str(
            getattr(self._material_persistence.current_entry, "path", "") or ""
        )
        for index in range(self._archive_combo.count()):
            if str(self._archive_combo.itemData(index) or "") != current_path:
                continue
            self._archive_combo.setItemText(index, self._archive_display_name())
            if self._archive_combo.currentIndex() != index:
                was_blocked = self._archive_combo.blockSignals(True)
                try:
                    self._archive_combo.setCurrentIndex(index)
                finally:
                    self._archive_combo.blockSignals(was_blocked)
            return
        if self._archive_combo.count() == 0:
            self._refresh_archive_selector_from_library()

    def _refresh_archive_selector_from_library(self) -> None:
        if not hasattr(self, "_archive_combo"):
            return
        mode_id = str(self.bridge.current_work_mode_id() or "").strip()
        entries = list_material_package_entries(mode_id=mode_id)
        self._archive_entries_by_path = {
            str(entry.path): entry for entry in entries
        }
        current_path = str(
            getattr(self._material_persistence.current_entry, "path", "") or ""
        )
        selected_index = -1
        was_blocked = self._archive_combo.blockSignals(True)
        try:
            self._archive_combo.clear()
            for entry in entries:
                index = self._archive_combo.add_badged_item(
                    entry.display_name,
                    str(entry.path),
                    badge_text="内置" if entry.source_type == "builtin" else "用户",
                    badge_kind=entry.source_type,
                )
                self._archive_combo.setItemData(index, entry.load_error, Qt.ToolTipRole)
                if str(entry.path) == current_path:
                    selected_index = index
            if selected_index >= 0:
                self._archive_combo.setCurrentIndex(selected_index)
            elif not entries and self._material_persistence.current_entry is None:
                self._archive_combo.add_badged_item(
                    self._archive_display_name(),
                    "",
                    badge_text="未保存",
                    badge_kind="neutral",
                )
        finally:
            self._archive_combo.blockSignals(was_blocked)
        self._setup_material_package_library_watcher()

    def _on_archive_selector_changed(self, index: int) -> None:
        if index < 0:
            return
        path = str(self._archive_combo.itemData(index) or "")
        entry = getattr(self, "_archive_entries_by_path", {}).get(path)
        current = self._material_persistence.current_entry
        if entry is None or (current is not None and entry.path == current.path):
            return
        if (
            self._has_unsaved_material_changes()
            and not self._material_persistence.save_current_package()
        ):
            self._sync_archive_selector()
            return
        self._activate_archive_entry(entry)

    def _has_unsaved_material_changes(self) -> bool:
        return self._material_persistence.has_unsaved_changes()

    def has_pending_material_changes(self) -> bool:
        """Return whether user-editable package content differs from its snapshot."""
        return self._has_unsaved_material_changes()

    def save_pending_material_changes(self) -> bool:
        """Explicitly save pending edits while the owning work mode is active."""
        if not self._has_unsaved_material_changes():
            return True
        return self._material_persistence.save_current_package()

    @staticmethod
    def _accept_pending_material_dialog(
        dialog: BaseDialog,
        selected: dict[str, str],
        action: str,
    ) -> None:
        selected["action"] = action
        dialog.accept()

    def _prompt_pending_material_action(self, reason: str) -> str:
        dialog = BaseDialog(title="未保存的资料包修改", icon_style="warning", parent=self)
        dialog.add_message(
            f"当前资料包有未保存修改。{str(reason or '继续').strip()}前，"
            "请选择保存、放弃修改或取消。"
        )
        selected = {"action": "cancel"}
        cancel_button = dialog.add_secondary_button("取消")
        cancel_button.clicked.connect(dialog.reject)
        discard_button = dialog.add_secondary_button("放弃修改")
        discard_button.clicked.connect(
            lambda: self._accept_pending_material_dialog(
                dialog,
                selected,
                "discard",
            )
        )
        save_button = dialog.add_primary_button("保存")
        save_button.clicked.connect(
            lambda: self._accept_pending_material_dialog(
                dialog,
                selected,
                "save",
            )
        )
        dialog.exec()
        return str(selected["action"])

    def prepare_close_pending_changes(self) -> bool:
        transaction = self._material_change_transaction
        if not transaction.cancel():
            return False
        if not self._has_unsaved_material_changes():
            return True
        action = self._prompt_pending_material_action("关闭程序")
        if action == "cancel":
            return False
        return transaction.prepare(action)

    def commit_close_pending_changes(self) -> bool:
        return self._material_change_transaction.commit()

    def rollback_close_pending_changes(self) -> bool:
        return self._material_change_transaction.rollback()

    def finalize_close_pending_changes(self) -> None:
        self._material_change_transaction.finalize()

    def cancel_prepared_close(self) -> bool:
        return self._material_change_transaction.cancel()

    def _initialize_archive_library(self) -> None:
        mode_id = str(self.bridge.current_work_mode_id() or "").strip()
        entries = list_material_package_entries(mode_id=mode_id)
        available = [entry for entry in entries if entry.is_available]
        if not available:
            archive = self._blank_archive("未命名资料包")
            self._material_persistence.replace_identity(None, "")
            if not self.set_archive(archive):
                return
            self._material_persistence.capture_snapshot(archive)
            self._refresh_archive_selector_from_library()
            self._delete_archive_btn.setEnabled(False)
            return
        preferred = next(
            (entry for entry in available if entry.source_type == "user"),
            available[0],
        )
        self._activate_archive_entry(preferred)

    def _activate_archive_entry(self, entry: MaterialPackageLibraryEntry) -> bool:
        try:
            archive = load_material_package_entry(entry)
        except Exception as exc:
            _LOGGER.exception("failed to load material package entry")
            Toast.show_error(f"加载资料包失败: {exc}")
            return False
        activation_snapshot = self._capture_archive_editor_transaction_snapshot()
        previous_entry = copy.deepcopy(self._material_persistence.current_entry)
        previous_path = self._material_persistence.current_path
        previous_baseline = copy.deepcopy(
            self._material_persistence.persisted_snapshot
        )
        self._material_persistence.replace_identity(entry, str(entry.path))
        archive.source_path = str(entry.path)
        if not self.set_archive(archive):
            self._material_persistence.replace_identity(previous_entry, previous_path)
            self._material_persistence.replace_persisted_snapshot(previous_baseline)
            self._sync_archive_selector()
            self._material_persistence.refresh_actions()
            self._refresh_summary()
            return False
        try:
            self._material_persistence.capture_snapshot(archive)
            self._refresh_archive_selector_from_library()
            self._delete_archive_btn.setEnabled(entry.source_type == "user")
        except Exception:
            _LOGGER.exception("failed to adopt activated material package")
            try:
                self._restore_archive_editor_transaction_snapshot(
                    activation_snapshot
                )
                self._sync_archive_selector()
            except Exception:
                _LOGGER.exception("failed to recover material package activation")
                self._material_persistence.fail_closed_actions()
            raise
        return True

    def _create_archive_in_library(self, name: str) -> bool:
        mode_id = str(self.bridge.current_work_mode_id() or "").strip()
        archive = self._blank_archive(name)
        try:
            receipt = create_material_package_in_library_with_receipt(
                archive,
                mode_id=mode_id,
                requested_id=name,
            )
        except Exception as exc:
            _LOGGER.exception("failed to create material package")
            Toast.show_error(f"新建资料包失败: {exc}")
            return False
        return self._material_persistence.adopt_created_package(receipt)

    def _blank_archive(self, name: str) -> EntityArchive:
        return EntityArchive(
            archive_name=name,
            profiles=[
                EntityProfile(
                    profile_name="这一份",
                )
            ],
        )

    def _new_archive(self) -> None:
        name = input_text(
            "新建资料包",
            "资料包名称",
            placeholder="资料包名称",
            default="新资料包",
            ok_text="新建资料包",
            parent=self,
        )
        if name is None:
            return
        name = name.strip() or "新资料包"
        if (
            self._has_unsaved_material_changes()
            and not self._material_persistence.save_current_package()
        ):
            return
        if self._create_archive_in_library(name):
            Toast.show_success(f"已新建资料包: {name}")

    def _duplicate_archive(self) -> None:
        if not self._persist_current_profile_editor():
            return
        current = self._current_archive_snapshot()
        default_name = f"{current.archive_name or '未命名资料包'} 副本"
        name = input_text(
            "创建资料包副本",
            "副本名称",
            placeholder="资料包名称",
            default=default_name,
            ok_text="创建副本",
            parent=self,
        )
        if name is None:
            return
        duplicate_name = name.strip() or default_name
        try:
            receipt = duplicate_material_package_entry_with_receipt(
                current,
                mode_id=str(self.bridge.current_work_mode_id() or "").strip(),
                name=duplicate_name,
            )
        except Exception as exc:
            _LOGGER.exception("failed to duplicate material package")
            Toast.show_error(f"创建资料包副本失败: {exc}")
            return
        if self._material_persistence.adopt_created_package(receipt):
            Toast.show_success(f"已创建资料包副本: {duplicate_name}")

    def _rename_archive(self) -> None:
        if not self._persist_current_profile_editor():
            return
        current_name = self._archive_display_name()
        name = input_text(
            "重命名资料包",
            "资料包名称",
            placeholder="资料包名称",
            default=current_name,
            ok_text="重命名资料包",
            parent=self,
        )
        if name is None:
            return
        name = name.strip() or current_name
        entry = self._material_persistence.current_entry
        if entry is None or entry.source_type != "user":
            Toast.show_warning("内置资料包不能直接重命名，请先创建副本")
            return
        previous_name = self._archive_name_edit.text()
        self._archive_name_edit.setText(name)
        try:
            saved = self._material_persistence.save_current_package()
        except Exception as exc:
            self._archive_name_edit.setText(previous_name)
            _LOGGER.exception("failed to rename material package")
            Toast.show_error(f"重命名资料包失败: {exc}")
            raise
        if not saved:
            self._archive_name_edit.setText(previous_name)
            return
        self._refresh_summary()
        Toast.show_success(f"已重命名资料包: {name}")

    def _open_archive_folder(self) -> None:
        entry = self._material_persistence.current_entry
        if entry is not None:
            folder = entry.path.parent
        else:
            folder = material_package_user_dir(
                str(self.bridge.current_work_mode_id() or "").strip()
            )
        folder.mkdir(parents=True, exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve()))):
            Toast.show_error(f"无法打开资料包文件夹: {folder}")

    def _delete_archive(self) -> None:
        name = self._archive_display_name()
        entry = self._material_persistence.current_entry
        if entry is None or entry.source_type != "user":
            Toast.show_warning("内置资料包不能删除")
            return
        if not confirm(
            "删除资料包",
            f"确定删除资料包“{name}”吗？当前界面中的资料会清空。",
            confirm_text="删除资料包",
            destructive=True,
            parent=self,
        ):
            return
        try:
            delete_material_package_entry(entry)
        except Exception as exc:
            _LOGGER.exception("failed to delete material package")
            Toast.show_error(f"删除资料包失败: {exc}")
            return
        self._material_persistence.replace_identity(None, "")
        self._material_persistence.replace_persisted_snapshot(None)
        entries = list_material_package_entries(
            mode_id=str(self.bridge.current_work_mode_id() or "").strip()
        )
        available = [item for item in entries if item.is_available]
        if available:
            self._activate_archive_entry(available[0])
        else:
            self._initialize_archive_library()
        Toast.show_success(f"已删除资料包: {name}")

    def _setup_material_package_library_watcher(self) -> None:
        watcher = getattr(self, "_material_package_library_watcher", None)
        if watcher is None:
            return
        target_dirs = {
            str(path)
            for path in material_package_library_watch_dirs(
                str(self.bridge.current_work_mode_id() or "").strip()
            )
        }
        current_dirs = set(watcher.directories())
        remove_dirs = list(current_dirs - target_dirs)
        add_dirs = list(target_dirs - current_dirs)
        if remove_dirs:
            watcher.removePaths(remove_dirs)
        if add_dirs:
            watcher.addPaths(add_dirs)

    def _on_material_package_library_path_changed(self, _path: str = "") -> None:
        if bool(getattr(self, "_assets_panel_closing", False)):
            return
        if bool(getattr(self, "_material_package_library_refresh_pending", False)):
            return
        self._material_package_library_refresh_pending = True
        timer = getattr(self, "_material_package_library_refresh_timer", None)
        if timer is None:
            self._material_package_library_refresh_pending = False
            return
        timer.start()

    def _refresh_material_package_library_after_change(self) -> None:
        self._material_package_library_refresh_pending = False
        if bool(getattr(self, "_assets_panel_closing", False)):
            return
        current = self._material_persistence.current_entry
        if current is not None and not current.path.exists():
            self._initialize_archive_library()
            return
        self._refresh_archive_selector_from_library()

    def _on_material_package_work_mode_changed(self, _mode) -> None:
        # Work-mode changes only activate the target library.  Saving is an
        # explicit pre-switch decision coordinated by MainWindow while the old
        # mode still owns the editor state.
        self._material_persistence.replace_identity(None, "")
        self._material_persistence.replace_persisted_snapshot(None)
        self._initialize_archive_library()

__all__ = ["ArchivePresenterMixin", "ProfileEditorPersistenceRejected"]
