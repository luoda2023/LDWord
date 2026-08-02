"""Presenter mixin for batch material output actions."""

from __future__ import annotations

import copy
from pathlib import Path

from src.config.entity import EntityProfile, clone_entity_profile
from src.config.material_batch import MaterialBatchSelection, build_material_batch_items
from src.config.material_context import MaterialExecutionContext
from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    Qt,
    QWidget,
)
from src.shared.ui.card import Card
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later, updates_suspended
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import template_form_row
from src.ui.panels.assets import BATCH_OUTPUT_CUSTOM_TEMPLATE, BATCH_OUTPUT_NAMING_OPTIONS
from src.ui.panels.assets.archive_presenter import ProfileEditorPersistenceRejected
from src.ui.panels.assets.batch_import import _load_batch_profiles_from_path
from src.ui.panels.assets.items import (
    _normalized_asset_item_payloads,
    _normalized_asset_metadata,
)
from src.services.material_assets import (
    normalized_asset_item_history_records as _normalized_asset_item_history_records,
)


class BatchOutputPresenterMixin:
    """Coordinate batch profile selection and output naming state."""

    def _setup_batch_profile_output_card(self) -> None:
        profile_list_card = Card(parent=self._section_contents["batch"])
        self._profile_list_card = profile_list_card
        profile_list_card.set_header("多份生成", icon_name="layers")
        self._profile_list = QListWidget(profile_list_card)
        self._profile_list.setObjectName("assets_profile_list")
        self._profile_list.currentRowChanged.connect(self._on_profile_row_changed)
        self._profile_list.itemChanged.connect(self._on_profile_item_changed)
        profile_list_card.add_widget(self._profile_list)

        profile_actions = QWidget(profile_list_card)
        profile_actions_layout = QHBoxLayout(profile_actions)
        profile_actions_layout.setContentsMargins(0, 0, 0, 0)
        profile_actions_layout.setSpacing(10)
        self._add_profile_btn = QPushButton("新增一份", profile_actions)
        self._copy_profile_btn = QPushButton("复制当前", profile_actions)
        self._remove_profile_btn = QPushButton("移除", profile_actions)
        self._add_profile_btn.clicked.connect(self._add_profile)
        self._copy_profile_btn.clicked.connect(self._copy_current_profile)
        self._remove_profile_btn.clicked.connect(self._remove_current_profile)
        profile_actions_layout.addWidget(self._add_profile_btn)
        profile_actions_layout.addWidget(self._copy_profile_btn)
        profile_actions_layout.addWidget(self._remove_profile_btn)
        profile_actions_layout.addStretch(1)
        profile_list_card.add_widget(profile_actions)

        self._batch_output_naming_combo = StyledComboBox(profile_list_card)
        self._batch_output_naming_combo.set_full_width_mode()
        for label, template in BATCH_OUTPUT_NAMING_OPTIONS:
            self._batch_output_naming_combo.addItem(label, template)
        self._batch_output_naming_combo.currentIndexChanged.connect(
            lambda *_: self._on_batch_output_naming_changed()
        )
        batch_form = InspectorForm(parent=profile_list_card)
        batch_form.add_field("保存为", self._batch_output_naming_combo)
        self._batch_output_template_edit = QLineEdit(profile_list_card)
        self._batch_output_template_edit.setText("{profile_name}")
        self._batch_output_template_edit.textChanged.connect(
            lambda *_: self._on_batch_output_template_changed()
        )
        self._batch_output_template_row = template_form_row(
            "自定义目录名",
            self._batch_output_template_edit,
            parent=batch_form,
        )
        self._batch_output_template_row.setVisible(False)
        batch_form.add_widget(self._batch_output_template_row)
        profile_list_card.add_widget(batch_form)
        self._batch_preview = QLabel(profile_list_card)
        self._batch_preview.setWordWrap(True)
        profile_list_card.add_widget(self._batch_preview)
        self._section_layouts["batch"].addWidget(profile_list_card)

    def _open_batch_generation(self) -> bool:
        if not self._apply_current_profile():
            return False
        self.bridge.navigate_to_intent.emit(
            {
                "panel_id": "workbench",
                "card_id": "batch_generate",
            }
        )
        return True

    def material_batch_selection(self) -> MaterialBatchSelection:
        archive = self.current_archive()
        return MaterialBatchSelection(
            mode_id=str(self.bridge.current_work_mode_id() or "").strip(),
            scene_id=str(self.bridge.current_scene_id() or "").strip(),
            package_id=str(archive.archive_id or "").strip(),
            archive=archive,
            profile_ids=self.selected_batch_profile_ids(),
            output_dir_template=self._batch_output_template(),
            base_context=self._shared_batch_context(),
        )

    def selected_batch_profile_ids(self) -> list[str]:
        """Return the checked profile ids without mutating editor state."""

        selected: list[str] = []
        for index in range(self._profile_list.count()):
            item = self._profile_list.item(index)
            if item is None or item.checkState() != Qt.Checked:
                continue
            profile = self._profiles[index]
            selected.append(profile.profile_id)
        return selected

    def batch_output_preview(self, *, base_output_dir: str | Path = "") -> list[str]:
        try:
            archive = self.current_archive()
        except ProfileEditorPersistenceRejected:
            return []
        items = build_material_batch_items(
            archive,
            profile_ids=self.selected_batch_profile_ids(),
            base_output_dir=base_output_dir,
            output_dir_template=self._batch_output_template(),
            base_context=self._shared_batch_context(),
        )
        return [item.output_dir for item in items]

    def load_batch_profiles_from_path(self, path: str | Path) -> list[EntityProfile]:
        imported_profiles = _load_batch_profiles_from_path(path)
        if not imported_profiles:
            return []

        snapshot = self._capture_profile_structure_mutation_snapshot()
        if snapshot is None:
            return []
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
            self._reload_profile_list(select_index=select_index)
        else:
            select_index = len(self._profiles)
            self._append_profiles_incrementally(
                profiles,
                select_index=select_index,
            )

        if not self._publish_profile_structure_mutation(snapshot):
            return []
        return [
            clone_entity_profile(
                profile,
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
        if not self._sync_material_batch_selection():
            self._restore_material_batch_controls_from_bridge()
        self._refresh_summary()

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
        if not self._sync_material_batch_selection():
            self._restore_material_batch_controls_from_bridge()
        self._refresh_summary()

    def _batch_output_template(self) -> str:
        template = self._current_batch_output_naming_template()
        if template == BATCH_OUTPUT_CUSTOM_TEMPLATE:
            return self._batch_output_template_edit.text().strip() or "{profile_name}"
        return template or "{profile_name}"

    def _current_batch_output_naming_template(self) -> str:
        if not hasattr(self, "_batch_output_naming_combo"):
            return "{profile_name}"
        data = self._batch_output_naming_combo.currentData()
        return str(data or "{profile_name}")

    def _select_batch_output_naming_for_template(self, template: str) -> None:
        if not hasattr(self, "_batch_output_naming_combo"):
            return
        cleaned = str(template or "").strip() or "{profile_name}"
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
        # Asset sources are profile-owned. The batch context carries only
        # package-wide execution contracts, never a projection of the selected
        # profile's assets into every profile in the batch.
        return MaterialExecutionContext(
            mode_id=str(self.bridge.current_work_mode_id() or "").strip(),
            scene_id=str(self.bridge.current_scene_id() or "").strip(),
            package_id=str(self._archive_id_edit.text() or "").strip(),
            archive_name=str(self._archive_name_edit.text() or "").strip(),
            exact_material_placeholders=True,
            attachment_bindings=copy.deepcopy(self._attachment_bindings),
        )

    def _sync_material_batch_selection(self) -> bool:
        set_selection = getattr(self.bridge, "set_current_material_batch_selection", None)
        if not callable(set_selection):
            return True
        try:
            selection = self.material_batch_selection()
        except ProfileEditorPersistenceRejected:
            return False
        set_selection(selection)
        return True

    def _restore_material_batch_controls_from_bridge(self) -> None:
        """Restore controls to the last selection accepted by the Bridge."""

        get_selection = getattr(
            self.bridge,
            "current_material_batch_selection",
            None,
        )
        if not callable(get_selection):
            return
        selection = get_selection()
        profile_ids = {
            str(profile_id or "").strip()
            for profile_id in getattr(selection, "profile_ids", ())
        }

        was_profile_syncing = self._syncing_profile_list
        profile_signals_blocked = self._profile_list.blockSignals(True)
        self._syncing_profile_list = True
        try:
            for index in range(self._profile_list.count()):
                item = self._profile_list.item(index)
                if item is None or index >= len(self._profiles):
                    continue
                profile_id = str(self._profiles[index].profile_id or "").strip()
                item.setCheckState(
                    Qt.Checked if profile_id in profile_ids else Qt.Unchecked
                )
        finally:
            self._syncing_profile_list = was_profile_syncing
            self._profile_list.blockSignals(profile_signals_blocked)

        template = (
            str(getattr(selection, "output_dir_template", "") or "").strip()
            or "{profile_name}"
        )
        was_naming_syncing = self._syncing_output_naming
        combo_signals_blocked = self._batch_output_naming_combo.blockSignals(True)
        edit_signals_blocked = self._batch_output_template_edit.blockSignals(True)
        self._syncing_output_naming = True
        try:
            self._batch_output_template_edit.setText(template)
            self._select_batch_output_naming_for_template(template)
        finally:
            self._syncing_output_naming = was_naming_syncing
            self._batch_output_template_edit.blockSignals(edit_signals_blocked)
            self._batch_output_naming_combo.blockSignals(combo_signals_blocked)
        self._refresh_profile_item_labels()


__all__ = ["BatchOutputPresenterMixin"]
