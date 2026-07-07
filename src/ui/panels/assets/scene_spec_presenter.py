"""Presenter mixin for scene-derived required fields and material row specs."""

from __future__ import annotations

from src.config.material_schema_registry import build_material_requirements
from src.shared.ui.layout_sync import refresh_layout_chain_later
from src.ui.panels.assets.fields import (
    _asset_role_label,
    _format_required_fields_text,
    _normalize_required_field_keys,
)
from src.ui.panels.assets.roles import (
    _accepted_types_include_attachment,
    _asset_slot_target_for_role,
    _material_schema_ids_from_profile,
    _material_schemas_from_ids,
    _schemas_role_accept_attachment,
)
from src.ui.panels.assets.specs import (
    COMMON_ASSET_SLOTS,
    REQUIRED_FIELD_KEYS,
    AssetSlotSpec,
    AttachmentRoleSpec,
)


class SceneSpecPresenterMixin:
    """Derive scene material specs and synchronize their UI rows."""

    def _on_scene_changed(self, scene) -> None:
        old_default = self._default_required_field_keys()
        new_default = self._required_fields_from_scene(scene)
        new_asset_slots = self._asset_slots_from_scene(scene)
        new_attachment_roles = self._attachment_roles_from_scene(scene)
        asset_slots_changed = new_asset_slots != self._asset_slot_specs
        attachment_roles_changed = new_attachment_roles != self._attachment_role_specs
        if new_default == old_default:
            if asset_slots_changed or attachment_roles_changed:
                self._persist_current_profile_editor()
            if asset_slots_changed:
                self._asset_slot_specs = new_asset_slots
                self._sync_asset_slot_rows()
            if attachment_roles_changed:
                self._attachment_role_specs = new_attachment_roles
                self._sync_attachment_role_rows()
            if asset_slots_changed or attachment_roles_changed:
                self._apply_theme()
            self._refresh_summary()
            if asset_slots_changed or attachment_roles_changed:
                self._sync_material_batch_selection()
            return

        self._persist_current_profile_editor()
        should_update_editor = self._required_fields_match_default(
            self._required_field_keys(),
            default_fields=old_default,
        )
        for profile in self._profiles:
            if self._required_fields_match_default(
                profile.required_fields,
                default_fields=old_default,
            ):
                profile.required_fields = list(new_default)
        self._default_required_fields = new_default
        if should_update_editor:
            self._required_fields_edit.blockSignals(True)
            try:
                self._required_fields_edit.setText(
                    _format_required_fields_text(
                        [],
                        fallback=self._default_required_field_keys(),
                    )
                )
            finally:
                self._required_fields_edit.blockSignals(False)
        if asset_slots_changed:
            self._asset_slot_specs = new_asset_slots
            self._sync_asset_slot_rows()
        if attachment_roles_changed:
            self._attachment_role_specs = new_attachment_roles
            self._sync_attachment_role_rows()
        if asset_slots_changed or attachment_roles_changed:
            self._apply_theme()
        self._refresh_summary()
        self._sync_material_batch_selection()

    def _default_required_field_keys(self) -> tuple[str, ...]:
        return tuple(getattr(self, "_default_required_fields", REQUIRED_FIELD_KEYS))

    def _required_fields_from_scene(self, scene) -> tuple[str, ...]:
        input_profile = getattr(scene, "input_source_profile", None)
        if input_profile is None:
            return REQUIRED_FIELD_KEYS
        schema_ids = _material_schema_ids_from_profile(input_profile)
        requirements = build_material_requirements(
            getattr(input_profile, "material_schema_id", ""),
            schema_ids=schema_ids,
            extra_required_fields=getattr(input_profile, "required_material_fields", ()),
            extra_required_asset_roles=getattr(input_profile, "required_image_roles", ()),
        )
        has_material_contract = any(
            (
                getattr(input_profile, "require_material_package", False),
                getattr(input_profile, "material_schema_id", ""),
                getattr(input_profile, "material_schema_ids", ()),
                getattr(input_profile, "required_material_fields", ()),
            )
        )
        if has_material_contract:
            return tuple(requirements.required_field_keys)
        return REQUIRED_FIELD_KEYS

    def _required_fields_match_default(
        self,
        keys: list[str] | tuple[str, ...],
        *,
        default_fields: tuple[str, ...] | None = None,
    ) -> bool:
        raw_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
        if not raw_keys:
            return True
        default = tuple(default_fields if default_fields is not None else self._default_required_field_keys())
        normalized = tuple(_normalize_required_field_keys(raw_keys, fallback=()))
        return normalized == default

    def _asset_slots_from_scene(self, scene) -> tuple[AssetSlotSpec, ...]:
        slots: dict[str, AssetSlotSpec] = {
            role: AssetSlotSpec(role=role, label=label, target=target)
            for role, label, target in COMMON_ASSET_SLOTS
        }
        input_profile = getattr(scene, "input_source_profile", None)
        if input_profile is None:
            return tuple(slots.values())

        schema_ids = _material_schema_ids_from_profile(input_profile)
        schema_id = schema_ids[0] if schema_ids else ""
        extra_required_roles = tuple(getattr(input_profile, "required_image_roles", ()) or ())
        requirements = build_material_requirements(
            schema_id,
            schema_ids=schema_ids,
            extra_required_asset_roles=extra_required_roles,
        )
        required_roles = set(requirements.required_asset_roles)
        schemas = _material_schemas_from_ids(schema_ids)

        for schema in schemas:
            for role_spec in schema.asset_roles:
                role = str(role_spec.role or "").strip().lower().replace(" ", "_")
                if not role:
                    continue
                if _accepted_types_include_attachment(role_spec.accepted_types):
                    continue
                existing = slots.get(role)
                target = existing.target if existing is not None else _asset_slot_target_for_role(role)
                label = existing.label if existing is not None else role_spec.label or _asset_role_label(role)
                slots[role] = AssetSlotSpec(
                    role=role,
                    label=label,
                    target=target,
                    required=role in required_roles or bool(role_spec.required),
                )
        for role in required_roles:
            normalized_role = str(role or "").strip().lower().replace(" ", "_")
            if not normalized_role:
                continue
            if _schemas_role_accept_attachment(schemas, normalized_role):
                continue
            existing = slots.get(normalized_role)
            slots[normalized_role] = AssetSlotSpec(
                role=normalized_role,
                label=existing.label if existing is not None else _asset_role_label(normalized_role),
                target=existing.target if existing is not None else _asset_slot_target_for_role(normalized_role),
                required=True,
            )
        return tuple(slots.values())

    def _attachment_roles_from_scene(self, scene) -> tuple[AttachmentRoleSpec, ...]:
        input_profile = getattr(scene, "input_source_profile", None)
        if input_profile is None:
            return ()

        schema_ids = _material_schema_ids_from_profile(input_profile)
        schema_id = schema_ids[0] if schema_ids else ""
        extra_required_roles = tuple(getattr(input_profile, "required_image_roles", ()) or ())
        requirements = build_material_requirements(
            schema_id,
            schema_ids=schema_ids,
            extra_required_asset_roles=extra_required_roles,
        )
        required_roles = set(requirements.required_asset_roles)
        schemas = _material_schemas_from_ids(schema_ids)
        if not schemas:
            return ()

        specs: list[AttachmentRoleSpec] = []
        seen_roles: set[str] = set()
        for schema in schemas:
            for role_spec in schema.asset_roles:
                role = str(role_spec.role or "").strip().lower().replace(" ", "_")
                if (
                    not role
                    or role in seen_roles
                    or not _accepted_types_include_attachment(role_spec.accepted_types)
                ):
                    continue
                seen_roles.add(role)
                specs.append(
                    AttachmentRoleSpec(
                        role=role,
                        label=role_spec.label or _asset_role_label(role),
                        accepted_types=tuple(role_spec.accepted_types or ("image", "pdf")),
                        required=role in required_roles or bool(role_spec.required),
                    )
                )
        return tuple(specs)

    def _sync_asset_slot_rows(self) -> None:
        if not hasattr(self, "_asset_slots_layout"):
            return
        while self._asset_slots_layout.count():
            item = self._asset_slots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._asset_slot_rows = {}
        self._asset_slot_choose_buttons = {}
        self._asset_slot_thumbnail_labels = {}
        self._asset_slot_status_labels = {}
        self._asset_slot_alt_text_inputs = {}
        self._asset_slot_view_buttons = {}
        self._asset_slot_open_buttons = {}
        self._asset_slot_clear_buttons = {}
        for spec in self._asset_slot_specs:
            self._asset_slots_layout.addWidget(
                self._build_asset_slot_row(spec.role, spec.label, spec.target, parent=self._asset_slots_container)
            )
        for role, edit in self._asset_slot_alt_text_inputs.items():
            edit.blockSignals(True)
            try:
                edit.setText(str(self._asset_metadata.get(role, {}).get("alt_text", "") or ""))
            finally:
                edit.blockSignals(False)
        refresh_layout_chain_later(self._asset_slots_container)

    def _sync_attachment_role_rows(self) -> None:
        if not hasattr(self, "_attachment_roles_layout"):
            return
        while self._attachment_roles_layout.count():
            item = self._attachment_roles_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._attachment_role_rows = {}
        self._attachment_role_status_labels = {}
        self._attachment_role_choose_buttons = {}
        self._attachment_role_open_buttons = {}
        self._attachment_role_clear_buttons = {}
        has_attachments = bool(self._attachment_role_specs)
        self._attachment_inventory_label.setVisible(has_attachments)
        self._attachment_roles_container.setVisible(has_attachments)
        for spec in self._attachment_role_specs:
            self._attachment_roles_layout.addWidget(
                self._build_attachment_role_row(spec, parent=self._attachment_roles_container)
            )
        refresh_layout_chain_later(self._attachment_roles_container)


__all__ = ["SceneSpecPresenterMixin"]
