"""Presenter mixin for material profile list/editor actions."""

from __future__ import annotations

from src.config.entity import EntityProfile
from src.qt_api import QListWidgetItem, Qt
from src.services.material_assets import (
    normalized_asset_item_history_records as _normalized_asset_item_history_records,
)
from src.ui.panels.assets.batch_import import _profile_item_label, _profile_label
from src.ui.panels.assets.fields import (
    _field_sources_from_imported_keys,
    _normalize_required_field_keys,
    _normalized_field_aliases,
    _normalized_field_sources,
)
from src.ui.panels.assets.items import (
    _normalized_asset_item_payloads,
    _normalized_asset_metadata,
)


class ProfilePresenterMixin:
    """Coordinate material profile list state and editor persistence."""

    def _selected_profile(self) -> EntityProfile:
        if not self._profiles:
            self._profiles = [EntityProfile()]
            self._current_profile_index = 0
        self._current_profile_index = max(
            0,
            min(self._current_profile_index, len(self._profiles) - 1),
        )
        return self._profiles[self._current_profile_index]

    def _persist_current_profile_editor(self) -> None:
        if self._syncing_profile_list:
            return
        profile = self._selected_profile()
        profile.profile_id = self._profile_id_edit.text().strip()
        profile.profile_name = self._profile_name_edit.text().strip()
        profile.fields = self._editor_fields()
        profile.assets_dir = self._assets_picker.path().strip()
        profile.required_fields = list(self._required_field_keys())
        profile.field_sources = _field_sources_from_imported_keys(profile.fields, self._imported_field_keys)
        profile.asset_paths = dict(self._asset_paths)
        profile.asset_metadata = self._current_asset_metadata()
        profile.asset_items = _normalized_asset_item_payloads(self._asset_item_payloads)
        self._update_profile_item(self._current_profile_index)

    def _reload_profile_list(self, *, select_index: int = 0) -> None:
        self._imported_field_keys = set()
        self._syncing_profile_list = True
        try:
            self._profile_list.clear()
            for profile in self._profiles:
                item = QListWidgetItem(_profile_label(profile))
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self._profile_list.addItem(item)
            if self._profile_list.count():
                self._profile_list.setCurrentRow(max(0, min(select_index, self._profile_list.count() - 1)))
        finally:
            self._syncing_profile_list = False
        self._current_profile_index = max(0, min(select_index, len(self._profiles) - 1))
        self._refresh_profile_item_labels()
        self._load_profile_to_editor(self._selected_profile())
        self._refresh_summary()

    def _update_profile_item(self, index: int) -> None:
        if index < 0 or index >= self._profile_list.count() or index >= len(self._profiles):
            return
        item = self._profile_list.item(index)
        if item is not None:
            was_syncing = self._syncing_profile_list
            self._syncing_profile_list = True
            try:
                checked = item.checkState() == Qt.Checked
                item.setText(_profile_item_label(index, self._profiles[index], checked, self._current_profile_index))
            finally:
                self._syncing_profile_list = was_syncing

    def _refresh_profile_item_labels(self) -> None:
        if not hasattr(self, "_profile_list"):
            return
        was_syncing = self._syncing_profile_list
        self._syncing_profile_list = True
        try:
            for index, profile in enumerate(self._profiles):
                if index >= self._profile_list.count():
                    continue
                item = self._profile_list.item(index)
                if item is None:
                    continue
                checked = item.checkState() == Qt.Checked
                item.setText(_profile_item_label(index, profile, checked, self._current_profile_index))
        finally:
            self._syncing_profile_list = was_syncing

    def _select_profile_for_repair(self, profile_id: str, profile_name: str) -> bool:
        target_id = str(profile_id or "").strip()
        target_name = str(profile_name or "").strip()
        target_index = -1
        if target_id:
            for index, profile in enumerate(self._profiles):
                if str(profile.profile_id or "").strip() == target_id:
                    target_index = index
                    break
        if target_index < 0 and target_name:
            for index, profile in enumerate(self._profiles):
                if str(profile.profile_name or "").strip() == target_name:
                    target_index = index
                    break
        if target_index < 0:
            return False
        if target_index == self._current_profile_index:
            self._refresh_profile_item_labels()
            return True
        self._profile_list.setCurrentRow(target_index)
        return self._current_profile_index == target_index

    def _on_profile_row_changed(self, row: int) -> None:
        if self._syncing_profile_list or row < 0 or row >= len(self._profiles):
            return
        previous_index = self._current_profile_index
        self._current_profile_index = max(0, min(previous_index, len(self._profiles) - 1))
        self._persist_current_profile_editor()
        self._current_profile_index = row
        self._imported_field_keys = set()
        self._load_profile_to_editor(self._profiles[row])
        self._refresh_profile_item_labels()
        self._refresh_summary()

    def _on_profile_item_changed(self, _item) -> None:
        if not self._syncing_profile_list:
            self._refresh_profile_item_labels()
            self._refresh_summary()
            self._sync_material_batch_selection()

    def _load_profile_to_editor(self, profile: EntityProfile) -> None:
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
        )

    def _add_profile(self) -> None:
        self._persist_current_profile_editor()
        next_index = len(self._profiles) + 1
        self._profiles.append(
            EntityProfile(
                profile_id=f"profile_{next_index}",
                profile_name=f"第 {next_index} 份",
            )
        )
        self._reload_profile_list(select_index=len(self._profiles) - 1)
        self._sync_material_batch_selection()

    def _copy_current_profile(self) -> None:
        self._persist_current_profile_editor()
        source = self._selected_profile()
        copy_index = len(self._profiles) + 1
        copied = EntityProfile(
            profile_id=self._next_profile_id(),
            profile_name=f"{_profile_label(source)} 鍓湰",
            fields=dict(source.fields),
            assets_dir=source.assets_dir,
            required_fields=list(source.required_fields),
            field_sources=dict(source.field_sources),
            field_aliases=dict(source.field_aliases),
            asset_paths=dict(source.asset_paths),
            asset_metadata=_normalized_asset_metadata(source.asset_metadata),
            asset_items=_normalized_asset_item_payloads(source.asset_items),
            asset_item_history=_normalized_asset_item_history_records(source.asset_item_history),
        )
        if not copied.profile_name.strip():
            copied.profile_name = f"第 {copy_index} 份"
        self._profiles.append(copied)
        self._reload_profile_list(select_index=len(self._profiles) - 1)
        self._sync_material_batch_selection()

    def _has_only_empty_profile(self) -> bool:
        if len(self._profiles) != 1:
            return False
        profile = self._profiles[0]
        return not (
            profile.profile_id
            or profile.profile_name
            or profile.fields
            or not self._required_fields_match_default(profile.required_fields)
            or profile.field_sources
            or profile.field_aliases
            or profile.assets_dir
            or profile.asset_paths
            or profile.asset_metadata
            or profile.asset_items
            or profile.asset_item_history
        )

    def _normalize_imported_profile(self, profile: EntityProfile, existing_ids: set[str]) -> EntityProfile:
        profile_id = str(profile.profile_id or "").strip()
        if not profile_id or profile_id in existing_ids:
            profile_id = self._next_profile_id(existing_ids)
        existing_ids.add(profile_id)
        profile_name = str(profile.profile_name or "").strip() or profile.fields.get("company_name") or "杩欎竴浠?"
        fields = {str(key): str(value) for key, value in profile.fields.items() if str(key or "").strip()}
        required_fields = _normalize_required_field_keys(
            profile.required_fields,
            fallback=self._default_required_field_keys(),
        )
        field_sources = _normalized_field_sources(profile.field_sources)
        if not field_sources:
            field_sources = _field_sources_from_imported_keys(fields, set(fields))
        field_aliases = _normalized_field_aliases(profile.field_aliases)
        return EntityProfile(
            profile_id=profile_id,
            profile_name=profile_name,
            fields=fields,
            assets_dir=str(profile.assets_dir or "").strip(),
            required_fields=required_fields,
            field_sources=field_sources,
            field_aliases=field_aliases,
            asset_paths={
                str(role): str(path)
                for role, path in profile.asset_paths.items()
                if str(role or "").strip() and str(path or "").strip()
            },
            asset_metadata=_normalized_asset_metadata(profile.asset_metadata),
            asset_items=_normalized_asset_item_payloads(profile.asset_items),
            asset_item_history=_normalized_asset_item_history_records(
                profile.asset_item_history
            ),
        )

    def _next_profile_id(self, existing_ids: set[str] | None = None) -> str:
        existing = set(existing_ids) if existing_ids is not None else {profile.profile_id for profile in self._profiles if profile.profile_id}
        next_index = len(existing) + 1
        while f"profile_{next_index}" in existing:
            next_index += 1
        return f"profile_{next_index}"

    def _remove_current_profile(self) -> None:
        if len(self._profiles) <= 1:
            self._profiles = [EntityProfile()]
            self._reload_profile_list(select_index=0)
            self._sync_material_batch_selection()
            return
        remove_index = self._current_profile_index
        self._profiles.pop(remove_index)
        self._reload_profile_list(select_index=max(0, remove_index - 1))
        self._sync_material_batch_selection()


__all__ = ["ProfilePresenterMixin"]
