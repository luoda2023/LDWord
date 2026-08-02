"""Presenter mixin for applying material context and mapping payloads."""

from __future__ import annotations

import copy

from pathlib import Path

from src.config.asset_resolution import asset_diagnostic_payload
from src.config.material_context import MaterialExecutionContext
from src.config.material_mappings import MaterialMappingPayload, load_material_mapping
from src.qt_api import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    Qt,
)
from src.shared.ui.card import Card
from src.shared.ui.toast import Toast
from src.shared.engine.material_timeline import timeline_owned_field_keys
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    material_token,
)
from src.ui.panels.assets.fields import (
    MATERIAL_FIELD_DRAFT_PREFIX,
    _imported_field_keys_from_sources,
)
from src.ui.panels.assets.items import (
    _normalized_asset_item_payloads,
    _normalized_asset_metadata,
)
from src.ui.panels.assets.mutation_transaction import (
    capture_material_mutation_snapshot,
    publish_or_rollback_material_mutation,
)


def _material_execution_field_values(
    *,
    package_fields: dict[str, object],
    task_values: dict[str, object],
    fixed_keys: list[str],
    floating_keys: list[str],
) -> dict[str, str]:
    values = {
        key: str(package_fields.get(key, "") or "")
        for key in fixed_keys
        if key in package_fields
    }
    values.update(
        {
            key: str(task_values.get(key, "") or "")
            for key in floating_keys
            if key in task_values
        }
    )
    return values


class MaterialContextApplicationPresenterMixin:
    """Apply profile, mapping, and bridge material-context data to the editor."""

    def _setup_generation_actions_card(self) -> None:
        generate_card = Card(parent=self._section_contents["generate"])
        self._generate_card = generate_card
        generate_card.set_header("资料 Token", icon_name="type")
        self._generation_status_label = QLabel(generate_card)
        self._generation_status_label.setWordWrap(True)
        self._generation_detail_label = QLabel(generate_card)
        self._generation_detail_label.setWordWrap(True)
        self._generation_detail_label.setVisible(True)
        generate_card.add_widget(self._generation_status_label)
        generate_card.add_widget(self._generation_detail_label)

        self._overview_preview_table = QTableWidget(generate_card)
        self._overview_preview_table.setObjectName("assets_overview_preview_table")
        self._overview_preview_table.setColumnCount(3)
        self._overview_preview_table.setHorizontalHeaderLabels(
            ["资料 Token", "当前内容", "状态"]
        )
        self._overview_preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._overview_preview_table.setSelectionMode(QTableWidget.NoSelection)
        self._overview_preview_table.setFocusPolicy(Qt.NoFocus)
        self._overview_preview_table.setAlternatingRowColors(False)
        self._overview_preview_table.setShowGrid(False)
        self._overview_preview_table.verticalHeader().setVisible(False)
        self._overview_preview_table.verticalHeader().setDefaultSectionSize(38)
        self._overview_preview_table.setMinimumHeight(150)
        self._overview_preview_table.setMaximumHeight(250)
        overview_header = self._overview_preview_table.horizontalHeader()
        overview_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        overview_header.setSectionResizeMode(1, QHeaderView.Stretch)
        overview_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        generate_card.add_widget(self._overview_preview_table)

        self._section_layouts["generate"].addWidget(generate_card)

    def _refresh_overview_material_preview(
        self,
        rows: list[dict[str, object]],
    ) -> None:
        if not hasattr(self, "_overview_preview_table"):
            return
        fields = self._material_preview_fields()
        fixed, floating = self._material_token_scope_keys()
        token_rows = [
            (key, "fixed") for key in fixed
        ] + [
            (key, "floating") for key in floating
        ]
        visible_rows = list(token_rows[:8])
        time_fields = set(
            timeline_owned_field_keys(
                self._selected_profile().timeline_plans,
                include_inactive=True,
            )
        )
        self._overview_preview_table.setVisible(bool(token_rows))
        self._overview_preview_table.clearContents()
        self._overview_preview_table.setRowCount(len(visible_rows))
        for row_index, (field_key, scope) in enumerate(visible_rows):
            raw_value = str(fields.get(field_key, "") or "")
            display_identifier = (
                self._official_field_display_label(field_key)
                if str(getattr(self._current_execution_target(), "mode_id", "") or "")
                == "official"
                else field_key
            )
            display_label = material_token(
                MaterialTokenNamespace.TIME
                if field_key in time_fields
                else MaterialTokenNamespace.TEXT,
                display_identifier,
            )
            values = (
                display_label,
                raw_value or "—",
                "已填写" if raw_value else "工作台填写" if scope == "floating" else "未填写",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._overview_preview_table.setItem(row_index, column, item)
            self._overview_preview_table.setRowHeight(row_index, 38)
        if visible_rows:
            header_height = max(32, self._overview_preview_table.horizontalHeader().height())
            table_height = header_height + (38 * len(visible_rows)) + 2
            resolved_height = min(250, max(110, table_height))
            self._overview_preview_table.setMinimumHeight(resolved_height)
            self._overview_preview_table.setMaximumHeight(resolved_height)

    def material_context(self) -> MaterialExecutionContext:
        if not self._persist_current_profile_editor():
            conflicts = ",".join(self._field_conflict_keys())
            raise ValueError(f"material_field_conflicts:{conflicts}")
        profile = self._selected_profile()
        fixed_keys, floating_keys = self._official_field_scope_projection()
        archive = self._current_archive_snapshot()
        package_fields = dict(profile.fields)
        task_values: dict[str, str] = {}
        current_context = self.bridge.current_material_context()
        if self._context_matches_current_package_profile(current_context):
            task_values.update(dict(current_context.entity_data))
        task_values.update(dict(getattr(self, "_task_field_values", {}) or {}))
        execution_fields = _material_execution_field_values(
            package_fields=package_fields,
            task_values=task_values,
            fixed_keys=fixed_keys,
            floating_keys=floating_keys,
        )
        asset_items = self._asset_items_for_profile(profile)
        return MaterialExecutionContext(
            mode_id=str(self.bridge.current_work_mode_id() or "").strip(),
            scene_id=str(self.bridge.current_scene_id() or "").strip(),
            package_id=str(archive.package_id or archive.archive_id or "").strip(),
            material_schema_ids=tuple(archive.material_schema_ids),
            archive_id=archive.archive_id,
            archive_name=archive.archive_name,
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            entity_data=execution_fields,
            field_scopes={
                **{key: "fixed" for key in fixed_keys},
                **{key: "floating" for key in floating_keys},
            },
            field_functions=copy.deepcopy(profile.field_functions),
            timeline_plans=copy.deepcopy(profile.timeline_plans),
            field_aliases=dict(profile.field_aliases),
            exact_material_placeholders=True,
            entity_assets_dir=profile.assets_dir,
            asset_items=asset_items,
            asset_diagnostics=[
                asset_diagnostic_payload(item)
                for item in list(
                    getattr(self, "_asset_resolution_diagnostics", ()) or ()
                )
            ],
            image_material_rules=copy.deepcopy(profile.image_material_rules),
            content_bindings=copy.deepcopy(profile.content_bindings),
            content_rules=copy.deepcopy(profile.content_rules),
            attachment_bindings=copy.deepcopy(profile.attachment_bindings),
        )

    def load_mapping_from_path(self, path: str | Path) -> MaterialMappingPayload:
        payload = load_material_mapping(path)
        self._apply_mapping_payload(payload)
        return payload

    def _apply_current_profile(self) -> bool:
        try:
            next_context = self.material_context()
        except ValueError as exc:
            if not str(exc).startswith("material_field_conflicts:"):
                raise
            conflicts = "、".join(self._field_conflict_keys())
            Toast.show_warning(f"资料字段存在冲突，无法写入：{conflicts}")
            return False
        snapshot = capture_material_mutation_snapshot(
            local_state={
                "material_context": self.bridge.current_material_context(),
                "official_document_type_id": (
                    self.bridge.current_official_document_type_id()
                ),
                "official_document_type_source": (
                    self.bridge.current_official_document_type_source()
                ),
            },
            profile_state=self._selected_profile(),
            profile_index=self._current_profile_index,
            batch_selection=self.bridge.current_material_batch_selection(),
        )
        return publish_or_rollback_material_mutation(
            snapshot,
            publish=lambda: self._publish_current_profile_context(next_context),
            restore_selection=lambda selection: (
                self._restore_current_profile_bridge_state(
                    snapshot.local_state,
                    selection,
                )
            ),
            restore_profile=self._restore_current_profile_mutation_profile,
            restore_local=lambda _state: None,
            refresh=lambda: None,
        )

    def _publish_current_profile_context(
        self,
        context: MaterialExecutionContext,
    ) -> bool:
        # The context signal is observable outside this panel.  Publish the
        # matching batch selection first so observers never receive half of
        # the new state pair.
        if not self._sync_material_batch_selection():
            return False
        self._suppress_material_context_sync = True
        try:
            self.bridge.set_current_material_context(context)
        finally:
            self._suppress_material_context_sync = False
        return True

    def _restore_current_profile_mutation_profile(self, index: int, profile) -> None:
        self._profiles[index] = profile
        self._update_profile_item(index)

    def _restore_current_profile_bridge_state(self, state, selection) -> None:
        self._suppress_material_context_sync = True
        try:
            # Restore the batch first so context/target observers receive a
            # coherent old state when the recovery signals are broadcast.
            self.bridge.set_current_material_batch_selection(selection)
            self.bridge.set_current_material_context(
                state["material_context"],
            )
            self.bridge.set_current_official_document_type_id(
                state["official_document_type_id"],
                source=state["official_document_type_source"],
            )
        finally:
            self._suppress_material_context_sync = False

    def _open_document_generation(self) -> None:
        if self._apply_current_profile():
            self.bridge.navigate_to_panel.emit(0)

    def _apply_mapping_payload(self, payload: MaterialMappingPayload) -> bool:
        if not self._persist_current_profile_editor():
            return False
        snapshot = capture_material_mutation_snapshot(
            local_state={
                "declared_field_keys": self._declared_field_keys,
                "manual_field_keys": self._manual_field_keys,
                "imported_field_keys": self._imported_field_keys,
                "preserve_import_sources": self._preserve_import_sources,
            },
            profile_state=self._selected_profile(),
            profile_index=self._current_profile_index,
            batch_selection=self.bridge.current_material_batch_selection(),
        )
        if payload.entity_data:
            previous_manual_order = tuple(getattr(self, "_manual_field_keys", ()))
            incoming_order = tuple(
                str(key or "").strip()
                for key in payload.entity_data
                if str(key or "").strip()
            )
            self._declared_field_keys.update(
                incoming_order
            )
            self._preserve_import_sources = True
            try:
                self._set_structured_fields(payload.entity_data)
            finally:
                self._preserve_import_sources = False
            self._manual_field_keys = list(
                dict.fromkeys(
                    key
                    for key in (*previous_manual_order, *incoming_order)
                    if key not in self._field_inputs
                    and not key.startswith(MATERIAL_FIELD_DRAFT_PREFIX)
                )
            )
            self._imported_field_keys = {
                str(key)
                for key, value in payload.entity_data.items()
                if str(key or "").strip() and str(value or "").strip()
            }
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_mapping_mutation_selection,
            restore_profile=self._restore_mapping_mutation_profile,
            restore_local=self._restore_mapping_mutation_local,
            refresh=lambda: self._load_profile_to_editor(
                self._profiles[snapshot.profile_index]
            ),
        ):
            return False
        self._refresh_summary()
        return True

    def _restore_mapping_mutation_selection(self, selection) -> None:
        self.bridge.set_current_material_batch_selection(selection)

    def _restore_mapping_mutation_profile(self, index: int, profile) -> None:
        self._profiles[index] = profile
        self._current_profile_index = index
        self._update_profile_item(index)

    def _restore_mapping_mutation_local(self, state) -> None:
        self._declared_field_keys = state["declared_field_keys"]
        self._manual_field_keys = state["manual_field_keys"]
        self._imported_field_keys = state["imported_field_keys"]
        self._preserve_import_sources = state["preserve_import_sources"]

    def _on_material_context_changed(self, context) -> None:
        if self._suppress_material_context_sync:
            return
        if not isinstance(context, MaterialExecutionContext):
            return
        previous_task_values = dict(getattr(self, "_task_field_values", {}) or {})
        self._last_received_material_context = context.clone()
        context_matches = self._context_matches_current_package_profile(context)
        self._task_field_values = (
            {
                str(key): str(value or "")
                for key, value in dict(context.entity_data or {}).items()
                if str(key or "").strip()
            }
            if context_matches
            else {}
        )
        # MaterialExecutionContext is an execution snapshot.  Receiving it
        # from the workbench must not replace package identity, field
        # inventory, field values, functions, aliases, or asset source
        # ownership. Package-owned non-field contracts are handled below.
        if context_matches and self._apply_received_non_field_material_domains(context):
            return
        self._apply_field_only_material_context(
            context,
            previous_task_values=previous_task_values,
        )

    def _apply_received_non_field_material_domains(
        self,
        context: MaterialExecutionContext,
    ) -> bool:
        """Apply package-owned non-field domains from a matching snapshot.

        Asset sources deliberately do not participate: ``asset_items`` and
        ``entity_assets_dir`` are derived execution projections, never a
        profile-authoring source.  Empty values in a partial runtime context
        also do not erase an existing package domain.
        """

        profile = self._selected_profile()
        changed = False

        if context.timeline_plans and profile.timeline_plans != context.timeline_plans:
            profile.timeline_plans = copy.deepcopy(context.timeline_plans)
            changed = True
        for incoming, current, assign in (
            (
                context.content_bindings,
                profile.content_bindings,
                lambda value: setattr(profile, "content_bindings", copy.deepcopy(value)),
            ),
            (
                context.content_rules,
                profile.content_rules,
                lambda value: setattr(profile, "content_rules", copy.deepcopy(value)),
            ),
            (
                context.attachment_bindings,
                profile.attachment_bindings,
                lambda value: setattr(profile, "attachment_bindings", copy.deepcopy(value)),
            ),
            (
                context.image_material_rules,
                profile.image_material_rules,
                lambda value: setattr(profile, "image_material_rules", copy.deepcopy(value)),
            ),
        ):
            if incoming and current != incoming:
                assign(incoming)
                changed = True

        if not changed:
            return False
        self._update_profile_item(self._current_profile_index)
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
        return True

    def _context_matches_current_package_profile(
        self,
        context: MaterialExecutionContext,
    ) -> bool:
        if not isinstance(context, MaterialExecutionContext):
            return False
        current_entry = self._material_persistence.current_entry
        expected_package_id = (
            str(getattr(current_entry, "package_id", "") or "").strip()
            or self._archive_id_edit.text().strip()
        )
        context_package_id = str(
            context.package_id or context.archive_id or ""
        ).strip()
        if not expected_package_id or not context_package_id:
            return False
        if expected_package_id != context_package_id:
            return False
        expected_profile_id = str(self._selected_profile().profile_id or "").strip()
        context_profile_id = str(context.profile_id or "").strip()
        if not expected_profile_id or not context_profile_id:
            return False
        if expected_profile_id != context_profile_id:
            return False
        return True

    def _apply_field_only_material_context(
        self,
        context: MaterialExecutionContext,
        *,
        previous_task_values: dict[str, str] | None = None,
    ) -> None:
        profile = self._selected_profile()
        previous_fields = dict(previous_task_values or {})
        next_fields = dict(getattr(self, "_task_field_values", {}) or {})
        changed_keys = [
            key
            for key in dict.fromkeys((*previous_fields, *next_fields))
            if str(previous_fields.get(key, "") or "")
            != str(next_fields.get(key, "") or "")
        ]
        floating_keys = set(self._official_field_scope_projection()[1])
        for key in changed_keys:
            if key not in floating_keys:
                continue
            value = self._material_field_render_value(key, "floating")
            edit = self._official_floating_field_previews.get(key)
            if edit is None:
                continue
            blocked = edit.blockSignals(True)
            try:
                edit.setText(value)
            finally:
                edit.blockSignals(blocked)
            self._update_preview_field_value(key, value.strip())
        self._refresh_field_conflict_state()
        refresh_fields = getattr(self, "_refresh_field_only_projection", None)
        if callable(refresh_fields):
            refresh_fields()
        timeline_anchor_keys = {
            str(plan.get(field_name, "") or "").strip()
            for plan in dict(profile.timeline_plans or {}).values()
            if isinstance(plan, dict)
            for field_name in ("start_field", "end_field")
            if str(plan.get(field_name, "") or "").strip()
        }
        if timeline_anchor_keys.intersection(changed_keys):
            refresh_timeline = getattr(self, "_refresh_timeline_ui", None)
            if callable(refresh_timeline):
                refresh_timeline()

    def _set_editor_values(
        self,
        *,
        archive_id: str,
        archive_name: str,
        profile_id: str,
        profile_name: str,
        fields: dict[str, str],
        assets_dir: str,
        declared_field_keys: list[str] | tuple[str, ...] | None = None,
        field_sources: dict[str, str] | None = None,
        asset_paths: dict[str, str] | None = None,
        asset_bindings: dict[str, object] | None = None,
        asset_metadata: dict[str, dict[str, str]] | None = None,
        asset_items: list[dict[str, object]] | None = None,
        image_material_rules: dict[str, object] | None = None,
        content_bindings: dict[str, object] | None = None,
        content_rules: list[object] | None = None,
        attachment_bindings: dict[str, object] | None = None,
    ) -> None:
        ordered_declared_keys = list(
            dict.fromkeys(
                str(key or "").strip()
                for key in (*tuple(declared_field_keys or ()), *fields.keys())
                if str(key or "").strip()
            )
        )
        widgets = [
            self._archive_id_edit,
            self._archive_name_edit,
            self._profile_id_edit,
            self._profile_name_edit,
            self._fields_edit,
            self._assets_picker,
            *self._field_inputs.values(),
            *self._asset_slot_alt_text_inputs.values(),
        ]
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self._archive_id_edit.setText(str(archive_id or ""))
            self._archive_name_edit.setText(str(archive_name or ""))
            self._profile_id_edit.setText(str(profile_id or ""))
            self._profile_name_edit.setText(str(profile_name or ""))
            self._declared_field_keys = set(ordered_declared_keys)
            self._set_structured_fields(fields)
            self._manual_field_keys = [
                key
                for key in ordered_declared_keys
                if key not in self._field_inputs
                and not key.startswith(MATERIAL_FIELD_DRAFT_PREFIX)
            ]
            self._assets_picker.set_path(str(assets_dir or ""))
            self._imported_field_keys = _imported_field_keys_from_sources(field_sources)
            self._asset_paths = {
                str(role): str(path)
                for role, path in dict(asset_paths or {}).items()
                if str(role or "").strip() and str(path or "").strip()
            }
            self._asset_bindings = copy.deepcopy(dict(asset_bindings or {}))
            self._asset_metadata = _normalized_asset_metadata(asset_metadata or {})
            self._asset_item_payloads = _normalized_asset_item_payloads(asset_items or [])
            self._image_material_rules = copy.deepcopy(
                dict(image_material_rules or {})
            )
            self._content_bindings = copy.deepcopy(dict(content_bindings or {}))
            self._content_rules = copy.deepcopy(list(content_rules or []))
            self._attachment_bindings = copy.deepcopy(
                dict(attachment_bindings or {})
            )
            migrate_attachments = getattr(
                self, "_migrate_legacy_attachment_paths", None
            )
            if callable(migrate_attachments):
                migrate_attachments()
            for role, edit in self._asset_slot_alt_text_inputs.items():
                edit.setText(
                    str(self._asset_metadata.get(role, {}).get("alt_text", "") or "")
                )
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        refresh_timeline = getattr(self, "_refresh_timeline_ui", None)
        if callable(refresh_timeline):
            refresh_timeline()
        if hasattr(self, "_asset_slots_layout"):
            self._asset_slot_specs = self._asset_slots_from_scene(
                self.bridge.current_scene()
            )
            self._sync_asset_slot_rows()
        sync_content = getattr(self, "_sync_content_material_rows", None)
        if callable(sync_content):
            sync_content()
        sync_attachments = getattr(self, "_sync_attachment_role_rows", None)
        if callable(sync_attachments):
            self._attachment_role_specs = self._attachment_roles_from_scene(
                self.bridge.current_scene()
            )
            sync_attachments()
        refresh_groups = getattr(self, "_sync_asset_group_rows", None)
        if callable(refresh_groups):
            self._asset_group_specs = self._asset_groups_from_scene(
                self.bridge.current_scene()
            )
            refresh_groups()
        self._refresh_summary()


__all__ = ["MaterialContextApplicationPresenterMixin"]
