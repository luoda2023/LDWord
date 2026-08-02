"""Presenter mixin for material profile list/editor actions."""

from __future__ import annotations

from src.config.entity import EntityProfile, clone_entity_profile
from src.config.material_field_inventory import normalize_material_field_inventory
from src.qt_api import QListWidgetItem, Qt
from src.services.material_assets import (
    normalized_asset_item_history_records as _normalized_asset_item_history_records,
)
from src.ui.panels.assets.batch_import import _profile_item_label, _profile_label
from src.ui.panels.assets.fields import (
    _field_sources_from_imported_keys,
    _format_fields_text,
    _normalized_field_aliases,
    _normalized_field_sources,
)
from src.ui.panels.assets.items import (
    _normalized_asset_item_payloads,
    _normalized_asset_metadata,
)
from src.ui.panels.assets.mutation_transaction import (
    capture_material_mutation_snapshot,
    publish_or_rollback_material_mutation,
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

    def _persist_current_profile_editor(self) -> bool:
        if self._syncing_profile_list:
            return True
        conflicts = self._field_conflict_keys()
        if conflicts:
            self._field_conflicts = conflicts
            self._refresh_field_conflict_state()
            return False
        # Harvest into a detached candidate.  Every reader below may validate,
        # normalize, or raise; mutating the shared profile before all of them
        # complete leaves a half-written package that no rollback snapshot can
        # faithfully recover.
        current_profile = self._selected_profile()
        profile_index = self._current_profile_index
        profile = clone_entity_profile(current_profile)
        profile.profile_id = self._profile_id_edit.text().strip()
        profile.profile_name = self._profile_name_edit.text().strip()
        editor_fields = self._editor_fields()
        ordered_field_keys = list(
            dict.fromkeys(
                key
                for key in (
                    *dict(profile.field_scopes or {}),
                    *tuple(profile.declared_field_keys or ()),
                    *getattr(self, "_manual_field_keys", ()),
                    *editor_fields,
                    *sorted(getattr(self, "_declared_field_keys", ())),
                )
                if str(key or "").strip()
                and not str(key).startswith("__material_field_draft__")
            )
        )
        profile.fields = {
            key: editor_fields[key]
            for key in ordered_field_keys
            if key in editor_fields
        }
        profile.declared_field_keys = ordered_field_keys
        profile.assets_dir = self._assets_picker.path().strip()
        # ``field_scopes`` is the package-owned registry and the shared rows
        # are only its projection.  UI/model refresh order must therefore
        # never rebuild the registry from whatever rows happen to be mounted
        # at this instant.
        normalize_material_field_inventory(profile)
        profile.field_sources = _field_sources_from_imported_keys(
            self._imported_field_keys
        )
        profile.asset_paths = dict(self._asset_paths)
        profile.asset_bindings = self._copy_asset_bindings()
        profile.asset_metadata = self._current_asset_metadata()
        profile.asset_items = _normalized_asset_item_payloads(self._asset_item_payloads)
        profile.image_material_rules = dict(self._image_material_rules)
        profile.content_bindings = dict(self._content_bindings)
        profile.content_rules = list(self._content_rules)
        profile.attachment_bindings = dict(self._attachment_bindings)
        self._profiles[profile_index] = profile
        try:
            self._update_profile_item(profile_index)
        except Exception:
            self._profiles[profile_index] = current_profile
            raise
        return True

    def _reload_profile_list(self, *, select_index: int = 0) -> None:
        target_index = max(0, min(select_index, len(self._profiles) - 1))
        selected_profile_fields = dict(self._profiles[target_index].fields)
        self._imported_field_keys = set()
        self._syncing_profile_list = True
        try:
            self._profile_list.clear()
            for profile in self._profiles:
                self._profile_list.addItem(self._new_profile_list_item(profile))
            if self._profile_list.count():
                self._profile_list.setCurrentRow(max(0, min(select_index, self._profile_list.count() - 1)))
        finally:
            self._syncing_profile_list = False
        self._current_profile_index = target_index
        self._refresh_profile_item_labels()
        self._load_profile_to_editor(self._selected_profile())
        # Field-row projection can trigger summary observers while retained
        # widgets are still being rebound.  Preserve the selected package's
        # model, then project fields without a concrete row into the generic
        # editor before any later harvest runs.
        selected_profile = self._selected_profile()
        selected_profile.fields = selected_profile_fields
        represented_keys = {
            *getattr(self, "_field_inputs", {}).keys(),
            *getattr(self, "_template_field_inputs", {}).keys(),
        }
        unrendered_fields = {
            str(key): str(value)
            for key, value in selected_profile_fields.items()
            if str(key).strip()
            and str(value or "").strip()
            and str(key) not in represented_keys
        }
        if unrendered_fields:
            self._fields_edit.set_text(_format_fields_text(unrendered_fields))
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
        if not self._persist_current_profile_editor():
            was_syncing = self._syncing_profile_list
            self._syncing_profile_list = True
            try:
                self._profile_list.setCurrentRow(self._current_profile_index)
            finally:
                self._syncing_profile_list = was_syncing
            return
        self._current_profile_index = row
        self._task_field_values = {}
        self._last_removed_official_field = None
        self._sync_official_remove_undo_buttons()
        self._imported_field_keys = set()
        # Summary/persistence projections can run while the editor is being
        # rebuilt.  Keep persistence suspended until every control contains
        # the newly selected profile; otherwise the first empty intermediate
        # frame can overwrite that profile before it is displayed.
        was_syncing = self._syncing_profile_list
        self._syncing_profile_list = True
        try:
            self._load_profile_to_editor(self._profiles[row])
        finally:
            self._syncing_profile_list = was_syncing
        self._refresh_profile_item_labels()
        self._refresh_summary()

    def _on_profile_item_changed(self, _item) -> None:
        if not self._syncing_profile_list:
            if not self._sync_material_batch_selection():
                self._restore_material_batch_controls_from_bridge()
            self._refresh_profile_item_labels()
            self._refresh_summary()

    def _load_profile_to_editor(self, profile: EntityProfile) -> None:
        # Batch/summary projection can persist the editor while a profile is
        # loading.  Establish the selected package's inventory first so that
        # this early persistence cannot replace a non-empty registry with the
        # previous profile's (or a blank editor's) scopes.
        inventory = normalize_material_field_inventory(profile)
        self._official_fixed_field_keys = list(inventory.fixed_keys)
        self._official_floating_field_keys = list(inventory.floating_keys)
        self._set_editor_values(
            archive_id=self._archive_id_edit.text().strip(),
            archive_name=self._archive_name_edit.text().strip(),
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            fields=profile.fields,
            assets_dir=profile.assets_dir,
            declared_field_keys=profile.declared_field_keys,
            field_sources=profile.field_sources,
            asset_paths=profile.asset_paths,
            asset_bindings=profile.asset_bindings,
            asset_metadata=profile.asset_metadata,
            asset_items=profile.asset_items,
            image_material_rules=profile.image_material_rules,
            content_bindings=profile.content_bindings,
            content_rules=profile.content_rules,
            attachment_bindings=profile.attachment_bindings,
        )
        # A field row can be absent while the detail controller is reconciling
        # a different profile inventory.  Preserve every value that did not
        # acquire a concrete editor in the generic keyed-value editor so the
        # following summary/persistence pass cannot erase it.
        editor_fields = self._editor_fields()
        unrendered_fields = {
            str(key): str(value)
            for key, value in dict(profile.fields or {}).items()
            if str(key).strip()
            and str(value or "").strip()
            and str(key) not in editor_fields
        }
        if unrendered_fields:
            self._fields_edit.set_text(_format_fields_text(unrendered_fields))

    def _capture_profile_structure_mutation_snapshot(self):
        if not self._persist_current_profile_editor():
            return None
        return capture_material_mutation_snapshot(
            local_state=self._capture_archive_editor_transaction_snapshot(),
            profile_state=self._selected_profile(),
            profile_index=self._current_profile_index,
            batch_selection=self.bridge.current_material_batch_selection(),
        )

    def _publish_profile_structure_mutation(self, snapshot) -> bool:
        return publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_profile_structure_selection,
            restore_profile=lambda _index, _profile: None,
            restore_local=self._restore_profile_structure_local,
            refresh=lambda: None,
        )

    def _restore_profile_structure_selection(self, selection) -> None:
        self.bridge.set_current_material_batch_selection(selection)

    def _restore_profile_structure_local(self, state) -> None:
        self._restore_archive_editor_transaction_snapshot(
            state,
            restore_selection=False,
        )

    def _add_profile(self) -> bool:
        snapshot = self._capture_profile_structure_mutation_snapshot()
        if snapshot is None:
            return False
        next_index = len(self._profiles) + 1
        self._insert_profile_incrementally(
            len(self._profiles),
            EntityProfile(
                profile_id=f"profile_{next_index}",
                profile_name=f"第 {next_index} 份",
            ),
        )
        return self._publish_profile_structure_mutation(snapshot)

    def _copy_current_profile(self) -> bool:
        snapshot = self._capture_profile_structure_mutation_snapshot()
        if snapshot is None:
            return False
        source = self._selected_profile()
        copy_index = len(self._profiles) + 1
        copied = clone_entity_profile(
            source,
            profile_id=self._next_profile_id(),
            profile_name=f"{_profile_label(source)} 副本",
            asset_metadata=_normalized_asset_metadata(source.asset_metadata),
            asset_items=_normalized_asset_item_payloads(source.asset_items),
            asset_item_history=_normalized_asset_item_history_records(source.asset_item_history),
        )
        if not copied.profile_name.strip():
            copied.profile_name = f"第 {copy_index} 份"
        self._insert_profile_incrementally(len(self._profiles), copied)
        return self._publish_profile_structure_mutation(snapshot)

    def _insert_profile_incrementally(
        self,
        index: int,
        profile: EntityProfile,
    ) -> None:
        insert_at = min(max(0, int(index)), len(self._profiles))
        self._profiles.insert(insert_at, profile)
        self._syncing_profile_list = True
        try:
            self._profile_list.insertItem(
                insert_at,
                self._new_profile_list_item(profile),
            )
            self._profile_list.setCurrentRow(insert_at)
        finally:
            self._syncing_profile_list = False
        self._activate_profile_after_structure_change(insert_at)

    def _append_profiles_incrementally(
        self,
        profiles: list[EntityProfile],
        *,
        select_index: int | None = None,
    ) -> None:
        """Append an imported batch without replacing existing list items."""

        if not profiles:
            return
        first_new_index = len(self._profiles)
        self._syncing_profile_list = True
        try:
            for profile in profiles:
                self._profiles.append(profile)
                self._profile_list.addItem(self._new_profile_list_item(profile))
            target_index = (
                first_new_index if select_index is None else int(select_index)
            )
            target_index = min(max(0, target_index), len(self._profiles) - 1)
            self._profile_list.setCurrentRow(target_index)
        finally:
            self._syncing_profile_list = False
        self._activate_profile_after_structure_change(target_index)

    def _activate_profile_after_structure_change(self, index: int) -> None:
        self._current_profile_index = max(
            0,
            min(int(index), len(self._profiles) - 1),
        )
        self._last_removed_official_field = None
        self._sync_official_remove_undo_buttons()
        self._imported_field_keys = set()
        self._refresh_profile_item_labels()
        self._load_profile_to_editor(self._selected_profile())
        self._refresh_summary()

    @staticmethod
    def _new_profile_list_item(profile: EntityProfile) -> QListWidgetItem:
        item = QListWidgetItem(_profile_label(profile))
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        return item

    def _has_only_empty_profile(self) -> bool:
        if len(self._profiles) != 1:
            return False
        profile = self._profiles[0]
        return not (
            profile.profile_id
            or profile.profile_name
            or profile.fields
            or profile.field_scopes
            or profile.field_functions
            or profile.timeline_plans
            or profile.declared_field_keys
            or profile.field_sources
            or profile.field_aliases
            or profile.assets_dir
            or profile.asset_paths
            or profile.asset_bindings
            or profile.asset_metadata
            or profile.asset_token_specs
            or profile.asset_items
            or profile.asset_item_history
            or profile.image_material_rules
            or profile.content_bindings
            or profile.content_rules
            or profile.attachment_role_specs
            or profile.attachment_bindings
        )

    def _normalize_imported_profile(self, profile: EntityProfile, existing_ids: set[str]) -> EntityProfile:
        profile_id = str(profile.profile_id or "").strip()
        if not profile_id or profile_id in existing_ids:
            profile_id = self._next_profile_id(existing_ids)
        existing_ids.add(profile_id)
        profile_name = str(profile.profile_name or "").strip() or profile.fields.get("company_name") or "这一份"
        fields = {str(key): str(value) for key, value in profile.fields.items() if str(key or "").strip()}
        field_sources = _normalized_field_sources(profile.field_sources)
        if not field_sources:
            field_sources = _field_sources_from_imported_keys(set(fields))
        field_aliases = _normalized_field_aliases(profile.field_aliases)
        return clone_entity_profile(
            profile,
            profile_id=profile_id,
            profile_name=profile_name,
            fields=fields,
            assets_dir=str(profile.assets_dir or "").strip(),
            declared_field_keys=list(
                dict.fromkeys((*profile.declared_field_keys, *fields.keys()))
            ),
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

    def _remove_current_profile(self) -> bool:
        try:
            if not self._persist_current_profile_editor():
                return False
            snapshot = self._capture_archive_editor_transaction_snapshot()
        except Exception:
            return False

        try:
            if len(self._profiles) <= 1:
                self._profiles = [EntityProfile()]
                self._syncing_profile_list = True
                try:
                    item = self._profile_list.item(0)
                    if item is None:
                        item = QListWidgetItem("")
                        self._profile_list.addItem(item)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)
                    self._profile_list.setCurrentRow(0)
                finally:
                    self._syncing_profile_list = False
                self._activate_profile_after_structure_change(0)
            else:
                remove_index = self._current_profile_index
                self._profiles.pop(remove_index)
                self._syncing_profile_list = True
                try:
                    removed_item = self._profile_list.takeItem(remove_index)
                    del removed_item
                    select_index = min(remove_index, len(self._profiles) - 1)
                    self._profile_list.setCurrentRow(select_index)
                finally:
                    self._syncing_profile_list = False
                self._activate_profile_after_structure_change(select_index)
            published = self._sync_material_batch_selection()
        except Exception:
            published = False
        if published:
            return True
        try:
            self._restore_archive_editor_transaction_snapshot(snapshot)
        except Exception:
            return False
        return False


__all__ = ["ProfilePresenterMixin"]
