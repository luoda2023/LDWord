"""Presenter mixin for archive package actions in the assets panel."""

from __future__ import annotations

from pathlib import Path

from src.config.entity import EntityArchive, EntityProfile, load_entity_archive, save_entity_archive
from src.qt_api import (
    QFileDialog,
    QDesktopServices,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QUrl,
    QWidget,
)
from src.shared.ui.card import Card
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


class ArchivePresenterMixin:
    """Coordinate archive package selection and import/export actions."""

    def _setup_archive_overview_card(self) -> None:
        archive_card = Card(parent=self._section_contents["generate"])
        self._archive_card = archive_card
        archive_card.set_header("褰撳墠璧勬枡鍖?", icon_name="package")
        self._archive_id_edit = QLineEdit(archive_card)
        self._archive_name_edit = QLineEdit(archive_card)
        self._archive_id_edit.setVisible(False)
        self._archive_name_edit.setVisible(False)
        self._archive_id_edit.setPlaceholderText("璧勬枡鍖呯紪鍙?")
        self._archive_name_edit.setPlaceholderText("璧勬枡鍖呭悕绉?")
        self._archive_id_edit.textChanged.connect(lambda *_: self._refresh_summary())
        self._archive_name_edit.textChanged.connect(lambda *_: self._refresh_summary())

        self._archive_combo = StyledComboBox(archive_card)
        self._archive_combo.setObjectName("assets_overview_archive_combo")
        self._archive_combo.set_full_width_mode(True)
        self._archive_combo.currentIndexChanged.connect(self._on_archive_selector_changed)
        archive_card.add_widget(self._archive_combo)

        self._archive_action_row = LibraryActionRow(
            archive_card,
            object_name="assets_overview_archive_action_row",
        )
        self._new_archive_btn = self._archive_action_row.add_action(
            "new",
            "鏂板缓璧勬枡鍖?",
            object_name="assets_overview_new_archive_btn",
            icon_name="plus",
            callback=self._new_archive,
        )
        self._duplicate_archive_btn = self._archive_action_row.add_action(
            "duplicate",
            "鍒涘缓鍓湰",
            object_name="assets_overview_duplicate_archive_btn",
            icon_name="copy",
            callback=self._duplicate_archive,
        )
        self._rename_archive_btn = self._archive_action_row.add_action(
            "rename",
            "閲嶅懡鍚嶈祫鏂欏寘",
            object_name="assets_overview_rename_archive_btn",
            icon_name="pencil-line",
            callback=self._rename_archive,
        )
        self._open_archive_folder_btn = self._archive_action_row.add_action(
            "open_folder",
            "鎵撳紑璧勬枡鍖呮枃浠跺す",
            object_name="assets_overview_open_archive_folder_btn",
            icon_name="folder-open",
            callback=self._open_archive_folder,
        )
        self._delete_archive_btn = self._archive_action_row.add_action(
            "delete",
            "鍒犻櫎璧勬枡鍖?",
            object_name="assets_overview_delete_archive_btn",
            icon_name="trash-2",
            variant="ghost-danger",
            side="right",
            callback=self._delete_archive,
        )
        archive_card.add_widget(self._archive_action_row)
        self._section_layouts["generate"].addWidget(archive_card)

    def _setup_import_export_card(self) -> None:
        import_export_card = Card(parent=self._section_contents["io"])
        self._import_export_card = import_export_card
        import_export_card.set_header("瀵煎叆瀵煎嚭", icon_name="download")
        self._import_export_hint = QLabel(
            "鐢ㄨ祫鏂欒〃琛ュ綋鍓嶈繖涓€浠斤紝鎴栧鍏ャ€佸鍑烘暣濂楄祫鏂欏寘銆?",
            import_export_card,
        )
        self._import_export_hint.setWordWrap(True)
        import_export_card.add_widget(self._import_export_hint)
        import_actions = QWidget(import_export_card)
        import_actions_layout = QHBoxLayout(import_actions)
        import_actions_layout.setContentsMargins(0, 0, 0, 0)
        import_actions_layout.setSpacing(10)
        self._load_mapping_btn = QPushButton("瀵煎叆璧勬枡琛?", import_actions)
        self._import_batch_from_io_btn = QPushButton("鎵归噺瀵煎叆澶氫唤", import_actions)
        self._load_btn = QPushButton("瀵煎叆璧勬枡鍖?", import_actions)
        self._save_btn = QPushButton("瀵煎嚭璧勬枡鍖?", import_actions)
        self._load_mapping_btn.clicked.connect(self._load_mapping_dialog)
        self._import_batch_from_io_btn.clicked.connect(self._load_batch_profiles_dialog)
        self._load_btn.clicked.connect(self._load_archive_dialog)
        self._save_btn.clicked.connect(self._save_archive_dialog)
        import_actions_layout.addWidget(self._load_mapping_btn)
        import_actions_layout.addWidget(self._import_batch_from_io_btn)
        import_actions_layout.addWidget(self._load_btn)
        import_actions_layout.addWidget(self._save_btn)
        import_actions_layout.addStretch(1)
        import_export_card.add_widget(import_actions)
        self._section_layouts["io"].addWidget(import_export_card)

    def current_archive(self) -> EntityArchive:
        self._persist_current_profile_editor()
        return EntityArchive(
            archive_id=self._archive_id_edit.text().strip(),
            archive_name=self._archive_name_edit.text().strip(),
            profiles=[
                EntityProfile(
                    profile_id=profile.profile_id,
                    profile_name=profile.profile_name,
                    fields=dict(profile.fields),
                    assets_dir=profile.assets_dir,
                    required_fields=list(profile.required_fields),
                    field_sources=dict(profile.field_sources),
                    field_aliases=dict(profile.field_aliases),
                    asset_paths=dict(profile.asset_paths),
                    asset_metadata=_normalized_asset_metadata(profile.asset_metadata),
                    asset_items=_normalized_asset_item_payloads(profile.asset_items),
                    asset_item_history=_normalized_asset_item_history_records(
                        profile.asset_item_history
                    ),
                )
                for profile in self._profiles
            ],
        )

    def set_archive(self, archive: EntityArchive) -> None:
        self._profiles = [
            EntityProfile(
                profile_id=profile.profile_id,
                profile_name=profile.profile_name,
                fields=dict(profile.fields),
                assets_dir=profile.assets_dir,
                required_fields=list(profile.required_fields),
                field_sources=dict(profile.field_sources),
                field_aliases=dict(profile.field_aliases),
                asset_paths=dict(profile.asset_paths),
                asset_metadata=_normalized_asset_metadata(profile.asset_metadata),
                asset_items=_normalized_asset_item_payloads(profile.asset_items),
                asset_item_history=_normalized_asset_item_history_records(
                    profile.asset_item_history
                ),
            )
            for profile in archive.profiles
        ] or [EntityProfile()]
        self._current_profile_index = 0
        self._archive_id_edit.blockSignals(True)
        self._archive_name_edit.blockSignals(True)
        try:
            self._archive_id_edit.setText(archive.archive_id)
            self._archive_name_edit.setText(archive.archive_name)
        finally:
            self._archive_name_edit.blockSignals(False)
            self._archive_id_edit.blockSignals(False)
        self._reload_profile_list(select_index=0)
        profile = self._selected_profile()
        self._set_editor_values(
            archive_id=self._archive_id_edit.text().strip(),
            archive_name=self._archive_name_edit.text().strip(),
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            fields=profile.fields,
            assets_dir=profile.assets_dir,
            required_fields=profile.required_fields,
            field_sources=profile.field_sources,
            asset_paths=profile.asset_paths,
            asset_metadata=profile.asset_metadata,
            asset_items=profile.asset_items,
            image_rules="",
        )
        self._sync_material_batch_selection()

    def save_archive_to_path(self, path: str | Path) -> None:
        save_entity_archive(self.current_archive(), path)

    def load_archive_from_path(self, path: str | Path) -> EntityArchive:
        archive = load_entity_archive(path)
        self.set_archive(archive)
        return archive

    def _archive_display_name(self) -> str:
        return self._archive_name_edit.text().strip() or "鏈懡鍚嶈祫鏂欏寘"

    def _sync_archive_selector(self) -> None:
        if not hasattr(self, "_archive_combo"):
            return
        name = self._archive_display_name()
        archive_id = self._archive_id_edit.text().strip()
        was_blocked = self._archive_combo.blockSignals(True)
        try:
            if self._archive_combo.count() == 0:
                self._archive_combo.addItem(name, archive_id)
            else:
                self._archive_combo.setItemText(0, name)
                self._archive_combo.setItemData(0, archive_id)
            self._archive_combo.setCurrentIndex(0)
        finally:
            self._archive_combo.blockSignals(was_blocked)

    def _on_archive_selector_changed(self, _index: int) -> None:
        self._sync_archive_selector()

    def _blank_archive(self, name: str) -> EntityArchive:
        return EntityArchive(
            archive_name=name,
            profiles=[
                EntityProfile(
                    profile_name="杩欎竴浠?",
                    required_fields=list(self._default_required_field_keys()),
                )
            ],
        )

    def _new_archive(self) -> None:
        name = input_text(
            "鏂板缓璧勬枡鍖?",
            "璧勬枡鍖呭悕绉?",
            placeholder="璧勬枡鍖呭悕绉?",
            default="鏂拌祫鏂欏寘",
            ok_text="鏂板缓璧勬枡鍖?",
            parent=self,
        )
        if name is None:
            return
        name = name.strip() or "鏂拌祫鏂欏寘"
        self.set_archive(self._blank_archive(name))
        Toast.show_success(f"宸叉柊寤鸿祫鏂欏寘: {name}")

    def _duplicate_archive(self) -> None:
        self._persist_current_profile_editor()
        current = self.current_archive()
        default_name = f"{current.archive_name or '鏈懡鍚嶈祫鏂欏寘'} 鍓湰"
        name = input_text(
            "鍒涘缓璧勬枡鍖呭壇鏈?",
            "鍓湰鍚嶇О",
            placeholder="璧勬枡鍖呭悕绉?",
            default=default_name,
            ok_text="鍒涘缓鍓湰",
            parent=self,
        )
        if name is None:
            return
        current.archive_id = ""
        current.archive_name = name.strip() or default_name
        self.set_archive(current)
        Toast.show_success(f"宸插垱寤鸿祫鏂欏寘鍓湰: {current.archive_name}")

    def _rename_archive(self) -> None:
        current_name = self._archive_display_name()
        name = input_text(
            "閲嶅懡鍚嶈祫鏂欏寘",
            "璧勬枡鍖呭悕绉?",
            placeholder="璧勬枡鍖呭悕绉?",
            default=current_name,
            ok_text="閲嶅懡鍚嶈祫鏂欏寘",
            parent=self,
        )
        if name is None:
            return
        name = name.strip() or current_name
        self._archive_name_edit.setText(name)
        self._sync_archive_selector()
        self._refresh_summary()
        Toast.show_success(f"宸查噸鍛藉悕璧勬枡鍖? {name}")

    def _open_archive_folder(self) -> None:
        candidates = [
            self._assets_picker.path().strip() if hasattr(self, "_assets_picker") else "",
            str(getattr(self, "_current_document_path", "") or ""),
        ]
        for value in candidates:
            if not value:
                continue
            path = Path(value)
            if path.is_file():
                path = path.parent
            if path.exists() and path.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
                return
        Toast.show_warning("当前资料包还没有可打开的文件夹")

    def _delete_archive(self) -> None:
        name = self._archive_display_name()
        if not confirm(
            "删除资料包",
            f"确定删除资料包“{name}”吗？当前界面中的资料会清空。",
            confirm_text="删除资料包",
            destructive=True,
            parent=self,
        ):
            return
        self.set_archive(self._blank_archive("未命名资料包"))
        Toast.show_success(f"宸插垹闄よ祫鏂欏寘: {name}")

    def _load_archive_dialog(self) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "瀵煎叆璧勬枡鍖?",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            self.load_archive_from_path(file_path)

    def _save_archive_dialog(self) -> None:
        file_path, _selected = QFileDialog.getSaveFileName(
            self,
            "瀵煎嚭璧勬枡鍖?",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            self.save_archive_to_path(file_path)


__all__ = ["ArchivePresenterMixin"]
