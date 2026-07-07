"""Presenter mixin for batch material output actions."""

from __future__ import annotations

from pathlib import Path

from src.config.entity import EntityProfile
from src.config.material_batch import MaterialBatchSelection, build_material_batch_items
from src.config.material_context import MaterialExecutionContext
from src.qt_api import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    Qt,
    QWidget,
)
from src.shared.ui.card import Card
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later, updates_suspended
from src.ui.panels.assets import BATCH_OUTPUT_CUSTOM_TEMPLATE, BATCH_OUTPUT_NAMING_OPTIONS
from src.ui.panels.assets.batch_import import _load_batch_profiles_from_path
from src.ui.panels.assets.items import (
    _normalized_asset_item_payloads,
    _normalized_asset_metadata,
)
from src.ui.panels.assets.text_helpers import _parse_replacements_text
from src.services.material_assets import (
    normalized_asset_item_history_records as _normalized_asset_item_history_records,
)


class BatchOutputPresenterMixin:
    """Coordinate batch profile selection and output naming state."""

    def _setup_batch_profile_output_card(self) -> None:
        profile_list_card = Card(parent=self._section_contents["batch"])
        self._profile_list_card = profile_list_card
        profile_list_card.set_header("澶氫唤鐢熸垚", icon_name="layers")
        self._profile_list = QListWidget(profile_list_card)
        self._profile_list.setObjectName("assets_profile_list")
        self._profile_list.currentRowChanged.connect(self._on_profile_row_changed)
        self._profile_list.itemChanged.connect(self._on_profile_item_changed)
        profile_list_card.add_widget(self._profile_list)

        profile_actions = QWidget(profile_list_card)
        profile_actions_layout = QHBoxLayout(profile_actions)
        profile_actions_layout.setContentsMargins(0, 0, 0, 0)
        profile_actions_layout.setSpacing(10)
        self._add_profile_btn = QPushButton("鏂板涓€浠?", profile_actions)
        self._copy_profile_btn = QPushButton("澶嶅埗褰撳墠", profile_actions)
        self._import_batch_profiles_btn = QPushButton("鎵归噺瀵煎叆", profile_actions)
        self._remove_profile_btn = QPushButton("绉婚櫎", profile_actions)
        self._add_profile_btn.clicked.connect(self._add_profile)
        self._copy_profile_btn.clicked.connect(self._copy_current_profile)
        self._import_batch_profiles_btn.clicked.connect(self._load_batch_profiles_dialog)
        self._remove_profile_btn.clicked.connect(self._remove_current_profile)
        profile_actions_layout.addWidget(self._add_profile_btn)
        profile_actions_layout.addWidget(self._copy_profile_btn)
        profile_actions_layout.addWidget(self._import_batch_profiles_btn)
        profile_actions_layout.addWidget(self._remove_profile_btn)
        profile_actions_layout.addStretch(1)
        profile_list_card.add_widget(profile_actions)

        self._batch_output_naming_combo = QComboBox(profile_list_card)
        for label, template in BATCH_OUTPUT_NAMING_OPTIONS:
            self._batch_output_naming_combo.addItem(label, template)
        self._batch_output_naming_combo.currentIndexChanged.connect(
            lambda *_: self._on_batch_output_naming_changed()
        )
        batch_form = InspectorForm(parent=profile_list_card)
        batch_form.add_field("淇濆瓨涓?", self._batch_output_naming_combo)
        profile_list_card.add_widget(batch_form)
        self._batch_preview = QLabel(profile_list_card)
        self._batch_preview.setWordWrap(True)
        profile_list_card.add_widget(self._batch_preview)
        self._section_layouts["batch"].addWidget(profile_list_card)

    def _open_batch_generation(self) -> None:
        self._apply_current_profile()
        self._sync_material_batch_selection()
        self.bridge.navigate_to_panel.emit(0)

    def material_batch_selection(self) -> MaterialBatchSelection:
        return MaterialBatchSelection(
            archive=self.current_archive(),
            profile_ids=self.selected_batch_profile_ids(),
            output_dir_template=self._batch_output_template(),
            base_context=self._shared_batch_context(),
        )

    def selected_batch_profile_ids(self) -> list[str]:
        self._persist_current_profile_editor()
        selected: list[str] = []
        for index in range(self._profile_list.count()):
            item = self._profile_list.item(index)
            if item is None or item.checkState() != Qt.Checked:
                continue
            profile = self._profiles[index]
            selected.append(profile.profile_id)
        return selected

    def batch_output_preview(self, *, base_output_dir: str | Path = "") -> list[str]:
        self._persist_current_profile_editor()
        archive = self.current_archive()
        items = build_material_batch_items(
            archive,
            profile_ids=self.selected_batch_profile_ids(),
            base_output_dir=base_output_dir,
            output_dir_template=self._batch_output_template(),
            base_context=self._shared_batch_context(),
        )
        return [item.output_dir for item in items]

    def _load_batch_profiles_dialog(self) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "鎵归噺瀵煎叆澶氫唤璧勬枡",
            "",
            "Material Tables (*.json *.csv *.xlsx *.xlsm);;All Files (*)",
        )
        if file_path:
            self.load_batch_profiles_from_path(file_path)

    def load_batch_profiles_from_path(self, path: str | Path) -> list[EntityProfile]:
        imported_profiles = _load_batch_profiles_from_path(path)
        if not imported_profiles:
            return []

        self._persist_current_profile_editor()
        replace_empty_profile = self._has_only_empty_profile()
        existing_ids = (
            set()
            if replace_empty_profile
            else {profile.profile_id for profile in self._profiles if profile.profile_id}
        )
        profiles = [
            self._normalize_imported_profile(profile, existing_ids)
            for profile in imported_profiles
        ]

        if replace_empty_profile:
            self._profiles = profiles
            select_index = 0
        else:
            select_index = len(self._profiles)
            self._profiles.extend(profiles)

        self._reload_profile_list(select_index=select_index)
        self._refresh_summary()
        self._sync_material_batch_selection()
        return [
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
            for profile in profiles
        ]

    def _on_batch_output_template_changed(self) -> None:
        if not self._syncing_output_naming:
            self._select_batch_output_naming_for_template(self._batch_output_template_edit.text().strip())
        self._refresh_summary()
        self._sync_material_batch_selection()

    def _on_batch_output_naming_changed(self) -> None:
        if self._syncing_output_naming:
            return
        template = self._current_batch_output_naming_template()
        custom = template == BATCH_OUTPUT_CUSTOM_TEMPLATE
        self._syncing_output_naming = True
        try:
            if hasattr(self, "_batch_output_template_row"):
                with updates_suspended(
                    self._batch_output_template_row,
                    getattr(self, "_detail_shell", self),
                ):
                    self._batch_output_template_row.setVisible(custom)
                    refresh_layout_chain(self._batch_output_template_row)
            if not custom:
                self._batch_output_template_edit.setText(template)
        finally:
            self._syncing_output_naming = False
        if hasattr(self, "_batch_output_template_row"):
            refresh_layout_chain_later(self._batch_output_template_row)
        self._refresh_summary()
        self._sync_material_batch_selection()

    def _batch_output_template(self) -> str:
        template = self._current_batch_output_naming_template()
        if template == BATCH_OUTPUT_CUSTOM_TEMPLATE:
            return self._batch_output_template_edit.text().strip() or "{entity_name}"
        return template or "{entity_name}"

    def _current_batch_output_naming_template(self) -> str:
        if not hasattr(self, "_batch_output_naming_combo"):
            return "{entity_name}"
        data = self._batch_output_naming_combo.currentData()
        return str(data or "{entity_name}")

    def _select_batch_output_naming_for_template(self, template: str) -> None:
        if not hasattr(self, "_batch_output_naming_combo"):
            return
        cleaned = str(template or "").strip() or "{entity_name}"
        target_index = -1
        custom_index = -1
        for index, (_label, option_template) in enumerate(BATCH_OUTPUT_NAMING_OPTIONS):
            if option_template == BATCH_OUTPUT_CUSTOM_TEMPLATE:
                custom_index = index
                continue
            if option_template == cleaned:
                target_index = index
                break
        if target_index < 0:
            target_index = custom_index
        if target_index < 0:
            return
        self._syncing_output_naming = True
        try:
            self._batch_output_naming_combo.setCurrentIndex(target_index)
            if hasattr(self, "_batch_output_template_row"):
                option_template = self._batch_output_naming_combo.currentData()
                with updates_suspended(
                    self._batch_output_template_row,
                    getattr(self, "_detail_shell", self),
                ):
                    self._batch_output_template_row.setVisible(option_template == BATCH_OUTPUT_CUSTOM_TEMPLATE)
                    refresh_layout_chain(self._batch_output_template_row)
        finally:
            self._syncing_output_naming = False
        if hasattr(self, "_batch_output_template_row"):
            refresh_layout_chain_later(self._batch_output_template_row)

    def _shared_batch_context(self) -> MaterialExecutionContext:
        return MaterialExecutionContext(
            replacements=_parse_replacements_text(self._replacement_rules_edit.get_text()),
            asset_items=self._current_asset_items(),
            image_rules=self._image_rules_for_asset_items(self._current_asset_items()),
        )

    def _sync_material_batch_selection(self) -> None:
        set_selection = getattr(self.bridge, "set_current_material_batch_selection", None)
        if callable(set_selection):
            set_selection(self.material_batch_selection())


__all__ = ["BatchOutputPresenterMixin"]
