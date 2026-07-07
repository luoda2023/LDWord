"""Presenter mixin for applying material context and mapping payloads."""

from __future__ import annotations

from pathlib import Path

from src.config.material_context import MaterialExecutionContext
from src.config.material_mappings import MaterialMappingPayload, load_material_mapping
from src.qt_api import QFileDialog, QHBoxLayout, QLabel, QPushButton, QWidget
from src.shared.ui.card import Card
from src.ui.panels.assets.fields import (
    _format_required_fields_text,
    _imported_field_keys_from_sources,
)
from src.ui.panels.assets.items import (
    _asset_item_payload,
    _normalized_asset_item_payloads,
    _normalized_asset_metadata,
)
from src.ui.panels.assets.text_helpers import (
    _format_image_rules_text,
    _format_replacements_text,
    _parse_replacements_text,
)


class MaterialContextApplicationPresenterMixin:
    """Apply profile, mapping, and bridge material-context data to the editor."""

    def _setup_generation_actions_card(self) -> None:
        generate_card = Card(parent=self._section_contents["generate"])
        self._generate_card = generate_card
        generate_card.set_header("璧勬枡瀹屾暣搴?", icon_name="circle-check")
        self._generation_status_label = QLabel(generate_card)
        self._generation_status_label.setWordWrap(True)
        self._generation_detail_label = QLabel(generate_card)
        self._generation_detail_label.setWordWrap(True)
        generate_card.add_widget(self._generation_status_label)
        generate_card.add_widget(self._generation_detail_label)

        generate_actions = QWidget(generate_card)
        generate_actions_layout = QHBoxLayout(generate_actions)
        generate_actions_layout.setContentsMargins(0, 0, 0, 0)
        generate_actions_layout.setSpacing(10)

        self._fill_missing_btn = QPushButton("琛ラ綈璧勬枡", generate_actions)
        self._apply_btn = QPushButton("鐢熸垚鏂囨。", generate_actions)
        self._batch_generate_btn = QPushButton("鎵归噺鐢熸垚", generate_actions)
        self._fill_missing_btn.setProperty("assets_generate_action_icon", "circle-alert")
        self._apply_btn.setProperty("assets_generate_action_icon", "play")
        self._batch_generate_btn.setProperty("assets_generate_action_icon", "layers")
        self._fill_missing_btn.clicked.connect(self._focus_missing_content)
        self._apply_btn.clicked.connect(self._open_document_generation)
        self._batch_generate_btn.clicked.connect(self._open_batch_generation)
        generate_actions_layout.addWidget(self._fill_missing_btn)
        generate_actions_layout.addWidget(self._apply_btn)
        generate_actions_layout.addWidget(self._batch_generate_btn)
        generate_actions_layout.addStretch(1)
        generate_card.add_widget(generate_actions)

        self._section_layouts["generate"].addWidget(generate_card)

    def material_context(self) -> MaterialExecutionContext:
        self._persist_current_profile_editor()
        archive = self.current_archive()
        profile = self._selected_profile()
        asset_items = self._asset_items_for_profile(profile)
        image_rules = self._image_rules_for_asset_items(asset_items)
        return MaterialExecutionContext(
            archive_id=archive.archive_id,
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            entity_data=dict(profile.fields),
            field_aliases=dict(profile.field_aliases),
            entity_assets_dir=profile.assets_dir,
            replacements=_parse_replacements_text(self._replacement_rules_edit.get_text()),
            asset_items=asset_items,
            image_rules=image_rules,
        )

    def load_mapping_from_path(self, path: str | Path) -> MaterialMappingPayload:
        payload = load_material_mapping(path)
        self._apply_mapping_payload(payload)
        return payload

    def _apply_current_profile(self) -> None:
        self._persist_current_profile_editor()
        self._suppress_material_context_sync = True
        try:
            self.bridge.set_current_material_context(self.material_context())
        finally:
            self._suppress_material_context_sync = False
        self._sync_material_batch_selection()

    def _open_document_generation(self) -> None:
        self._apply_current_profile()
        self.bridge.navigate_to_panel.emit(0)

    def _load_mapping_dialog(self) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "瀵煎叆璧勬枡琛?",
            "",
            "Mapping Files (*.json *.csv *.xlsx *.xlsm);;All Files (*)",
        )
        if file_path:
            self.load_mapping_from_path(file_path)

    def _apply_mapping_payload(self, payload: MaterialMappingPayload) -> None:
        if payload.entity_data:
            self._preserve_import_sources = True
            try:
                self._set_structured_fields(payload.entity_data)
            finally:
                self._preserve_import_sources = False
            self._imported_field_keys = {
                str(key)
                for key, value in payload.entity_data.items()
                if str(key or "").strip() and str(value or "").strip()
            }
        if payload.replacements:
            self._replacement_rules_edit.set_text(
                _format_replacements_text(payload.replacements)
            )
        self._refresh_summary()
        self._sync_material_batch_selection()

    def _on_material_context_changed(self, context) -> None:
        if self._suppress_material_context_sync:
            return
        if not isinstance(context, MaterialExecutionContext):
            return
        profile = self._selected_profile()
        if context.profile_id:
            profile.profile_id = context.profile_id
        if context.profile_name:
            profile.profile_name = context.profile_name
        profile.fields = dict(context.entity_data)
        profile.assets_dir = context.entity_assets_dir
        profile.field_sources = {}
        profile.field_aliases = {}
        profile.asset_paths = {
            item.role: item.path
            for item in context.asset_items
            if item.role and item.path
        }
        profile.asset_metadata = {
            item.role: dict(getattr(item, "metadata", {}) or {})
            for item in context.asset_items
            if item.role and getattr(item, "metadata", None)
        }
        profile.asset_items = [_asset_item_payload(item) for item in context.asset_items]
        self._reload_profile_list(select_index=self._current_profile_index)
        self._set_editor_values(
            archive_id=context.archive_id or self._archive_id_edit.text().strip(),
            archive_name=self._archive_name_edit.text().strip(),
            profile_id=context.profile_id,
            profile_name=context.profile_name,
            fields=context.entity_data,
            assets_dir=context.entity_assets_dir,
            required_fields=profile.required_fields,
            field_sources=profile.field_sources,
            asset_paths=profile.asset_paths,
            asset_metadata=profile.asset_metadata,
            asset_items=profile.asset_items,
            image_rules=_format_image_rules_text(context.image_rules),
            replacements=_format_replacements_text(context.replacements),
        )
        self._sync_material_batch_selection()

    def _set_editor_values(
        self,
        *,
        archive_id: str,
        archive_name: str,
        profile_id: str,
        profile_name: str,
        fields: dict[str, str],
        assets_dir: str,
        required_fields: list[str] | None = None,
        field_sources: dict[str, str] | None = None,
        asset_paths: dict[str, str] | None = None,
        asset_metadata: dict[str, dict[str, str]] | None = None,
        asset_items: list[dict[str, object]] | None = None,
        image_rules: str = "",
        replacements: str = "",
    ) -> None:
        widgets = [
            self._archive_id_edit,
            self._archive_name_edit,
            self._profile_id_edit,
            self._profile_name_edit,
            self._required_fields_edit,
            self._fields_edit,
            self._replacement_rules_edit,
            self._image_rules_edit,
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
            self._required_fields_edit.setText(
                _format_required_fields_text(
                    required_fields or [],
                    fallback=self._default_required_field_keys(),
                )
            )
            self._set_structured_fields(fields)
            self._replacement_rules_edit.set_text(str(replacements or ""))
            self._image_rules_edit.set_text(str(image_rules or ""))
            self._assets_picker.set_path(str(assets_dir or ""))
            self._imported_field_keys = _imported_field_keys_from_sources(field_sources)
            self._asset_paths = {
                str(role): str(path)
                for role, path in dict(asset_paths or {}).items()
                if str(role or "").strip() and str(path or "").strip()
            }
            self._asset_metadata = _normalized_asset_metadata(asset_metadata or {})
            self._asset_item_payloads = _normalized_asset_item_payloads(asset_items or [])
            for role, edit in self._asset_slot_alt_text_inputs.items():
                edit.setText(
                    str(self._asset_metadata.get(role, {}).get("alt_text", "") or "")
                )
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        self._refresh_summary()


__all__ = ["MaterialContextApplicationPresenterMixin"]
