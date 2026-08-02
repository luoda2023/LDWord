"""Presenter mixin for scene-derived required fields and material row specs."""

from __future__ import annotations

from dataclasses import replace

from src.config.entity import AssetTokenSpec
from src.config.material_schema_registry import build_material_requirements
from src.shared.ui.dialogs import confirm
from src.shared.ui.layout_sync import refresh_layout_chain_later
from src.shared.ui.keyed_widget_list import KeyedWidgetListController
from src.shared.ui.theme import get_theme
from src.shared.ui.toast import Toast
from src.shared.ui.token_row_style import apply_token_row_style
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    MaterialTokenNamespace,
    material_token,
    parse_material_token,
)
from src.ui.panels.assets.fields import (
    _asset_role_label,
    _placeholder_key,
)
from src.ui.panels.assets.mutation_transaction import (
    capture_material_mutation_snapshot,
    publish_or_rollback_material_mutation,
)
from src.ui.panels.assets.roles import (
    _asset_slot_target_for_role,
    _attachment_path_policy,
    _material_role_is_attachment,
    _material_schema_ids_from_profile,
    _material_schemas_from_ids,
    _schemas_role_accept_attachment,
)
from src.ui.panels.assets.specs import (
    COMMON_ASSET_SLOTS,
    AssetGroupSpec,
    AssetSlotSpec,
    AttachmentRoleSpec,
)
from src.ui.panels.assets.token_naming import (
    is_numbered_series_name,
    next_numbered_name,
    next_series_name,
    numbered_series_prefix,
)


class SceneSpecPresenterMixin:
    """Derive scene material specs and synchronize their UI rows."""

    def _on_scene_changed(self, scene) -> bool:
        new_asset_slots = self._asset_slots_from_scene(scene)
        new_asset_groups = self._asset_groups_from_scene(scene)
        new_attachment_roles = self._attachment_roles_from_scene(scene)
        asset_slots_changed = new_asset_slots != self._asset_slot_specs
        asset_groups_changed = new_asset_groups != self._asset_group_specs
        attachment_roles_changed = new_attachment_roles != self._attachment_role_specs
        any_changed = asset_slots_changed or asset_groups_changed or attachment_roles_changed
        if not any_changed:
            self._refresh_summary()
            return True
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        if asset_slots_changed:
            self._asset_slot_specs = new_asset_slots
        if asset_groups_changed:
            self._asset_group_specs = new_asset_groups
        if attachment_roles_changed:
            self._attachment_role_specs = new_attachment_roles
            migrate_attachments = getattr(
                self, "_migrate_legacy_attachment_paths", None
            )
            if callable(migrate_attachments):
                migrate_attachments()
        if not self._publish_scene_spec_mutation(snapshot, scope="scene"):
            return False
        self._refresh_scene_spec_mutation_ui("scene")
        return True

    def _capture_scene_spec_mutation_snapshot(self):
        if not self._persist_current_profile_editor():
            return None
        status_label = getattr(self, "_image_assets_status_label", None)
        return capture_material_mutation_snapshot(
            local_state={
                "asset_slot_specs": self._asset_slot_specs,
                "asset_group_specs": self._asset_group_specs,
                "attachment_role_specs": self._attachment_role_specs,
                "asset_paths": self._asset_paths,
                "asset_bindings": self._asset_bindings,
                "asset_metadata": self._asset_metadata,
                "asset_item_payloads": self._asset_item_payloads,
                "image_material_rules": self._image_material_rules,
                "attachment_bindings": self._attachment_bindings,
                "attachment_legacy_errors": self._attachment_legacy_errors,
                "preview_path": self._current_image_preview_path,
                "preview_display_name": self._current_image_preview_display_name,
                "preview_compare_reference": self._current_image_preview_compare_reference,
                "preview_compare_source": self._current_image_preview_compare_source,
                "preview_compare_display_name": self._current_image_preview_compare_display_name,
                "preview_compare_options": self._current_image_preview_compare_options,
                "preview_question_figure_row": self._current_image_preview_question_figure_row,
                "preview_status_text": (
                    status_label.text() if status_label is not None else None
                ),
            },
            profile_state=self._selected_profile(),
            profile_index=self._current_profile_index,
            batch_selection=self.bridge.current_material_batch_selection(),
        )

    def _publish_scene_spec_mutation(self, snapshot, *, scope: str) -> bool:
        return publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_scene_spec_mutation_selection,
            restore_profile=self._restore_scene_spec_mutation_profile,
            restore_local=self._restore_scene_spec_mutation_local,
            refresh=lambda: self._refresh_scene_spec_mutation_ui(
                scope,
                state=snapshot.local_state,
            ),
        )

    def _restore_scene_spec_mutation_selection(self, selection) -> None:
        self.bridge.set_current_material_batch_selection(selection)

    def _restore_scene_spec_mutation_profile(self, index: int, profile) -> None:
        self._profiles[index] = profile
        self._update_profile_item(index)

    def _restore_scene_spec_mutation_local(self, state) -> None:
        self._asset_slot_specs = state["asset_slot_specs"]
        self._asset_group_specs = state["asset_group_specs"]
        self._attachment_role_specs = state["attachment_role_specs"]
        self._asset_paths = state["asset_paths"]
        self._asset_bindings = state["asset_bindings"]
        self._asset_metadata = state["asset_metadata"]
        self._asset_item_payloads = state["asset_item_payloads"]
        self._image_material_rules = state["image_material_rules"]
        self._attachment_bindings = state["attachment_bindings"]
        self._attachment_legacy_errors = state["attachment_legacy_errors"]
        self._current_image_preview_path = state["preview_path"]
        self._current_image_preview_display_name = state["preview_display_name"]
        self._current_image_preview_compare_reference = state[
            "preview_compare_reference"
        ]
        self._current_image_preview_compare_source = state["preview_compare_source"]
        self._current_image_preview_compare_display_name = state[
            "preview_compare_display_name"
        ]
        self._current_image_preview_compare_options = state[
            "preview_compare_options"
        ]
        self._current_image_preview_question_figure_row = state[
            "preview_question_figure_row"
        ]

    def _refresh_scene_spec_mutation_ui(self, scope: str, *, state=None) -> None:
        if scope in {"scene", "asset_slot"}:
            self._sync_asset_slot_rows()
        if scope in {"scene", "asset_group"}:
            self._sync_asset_group_rows()
        if scope in {"scene", "attachment"}:
            self._sync_attachment_role_rows()
        if scope == "scene":
            self._apply_theme()
        self._refresh_summary()
        if state is not None and state["preview_status_text"] is not None:
            status_label = getattr(self, "_image_assets_status_label", None)
            if status_label is not None:
                status_label.setText(state["preview_status_text"])

    def _asset_slots_from_scene(self, scene) -> tuple[AssetSlotSpec, ...]:
        profile = self._selected_profile()
        token_specs = tuple(getattr(profile, "asset_token_specs", ()) or ())
        if token_specs:
            return tuple(
                AssetSlotSpec(
                    role=spec.token_id,
                    label=spec.label or _placeholder_key(spec.token),
                    target=spec.token,
                    required=bool(spec.required),
                )
                for spec in token_specs
                if spec.cardinality != "multiple"
            )
        return self._asset_slots_with_profile_metadata(
            self._base_asset_slots_from_scene(scene)
        )

    def _base_asset_slots_from_scene(self, scene) -> tuple[AssetSlotSpec, ...]:
        slots: dict[str, AssetSlotSpec] = {
            role: AssetSlotSpec(role=role, label=label, target=target)
            for role, label, target in COMMON_ASSET_SLOTS
            if role != "qualification"
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
        multiple_roles = {
            str(role_spec.role or "").strip().lower().replace(" ", "_")
            for schema in schemas
            for role_spec in schema.asset_roles
            if str(getattr(role_spec, "cardinality", "single") or "single")
            .strip()
            .lower()
            == "multiple"
            and not _material_role_is_attachment(role_spec)
        }
        for role in multiple_roles:
            slots.pop(role, None)

        for schema in schemas:
            for role_spec in schema.asset_roles:
                role = str(role_spec.role or "").strip().lower().replace(" ", "_")
                if not role:
                    continue
                if _material_role_is_attachment(role_spec):
                    continue
                if str(getattr(role_spec, "cardinality", "single") or "single").strip().lower() == "multiple":
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

    def _asset_slots_with_profile_metadata(
        self,
        base_specs: tuple[AssetSlotSpec, ...],
    ) -> tuple[AssetSlotSpec, ...]:
        """Apply user-owned Token names, additions, removals, and ordering."""

        metadata = dict(getattr(self, "_asset_metadata", {}) or {})
        rows: list[tuple[int, int, AssetSlotSpec]] = []
        base_roles = {spec.role for spec in base_specs}
        for default_index, spec in enumerate(base_specs):
            item = dict(metadata.get(spec.role, {}) or {})
            if item.get("slot_removed") == "1":
                continue
            target = self._normalized_asset_slot_target(item.get("slot_target")) or spec.target
            label = str(item.get("slot_label", "") or "").strip() or spec.label
            try:
                order = int(item.get("slot_order", (default_index + 1) * 10))
            except (TypeError, ValueError):
                order = (default_index + 1) * 10
            rows.append(
                (
                    order,
                    default_index,
                    AssetSlotSpec(
                        role=spec.role,
                        label=label,
                        target=target,
                        required=spec.required,
                    ),
                )
            )
        custom_index = len(rows)
        for role, raw_item in metadata.items():
            item = dict(raw_item or {})
            if role in base_roles or item.get("slot_custom") != "1":
                continue
            if item.get("slot_removed") == "1":
                continue
            target = self._normalized_asset_slot_target(item.get("slot_target"))
            if not target:
                continue
            try:
                order = int(item.get("slot_order", (custom_index + 1) * 10))
            except (TypeError, ValueError):
                order = (custom_index + 1) * 10
            label = str(item.get("slot_label", "") or "").strip() or _placeholder_key(target)
            rows.append(
                (
                    order,
                    custom_index,
                    AssetSlotSpec(role=role, label=label, target=target),
                )
            )
            custom_index += 1
        rows.sort(key=lambda item: (item[0], item[1]))
        return tuple(spec for _order, _index, spec in rows)

    @staticmethod
    def _normalized_asset_slot_target(value: object) -> str:
        raw = str(value or "").strip()
        try:
            ref = parse_material_token(raw)
        except (TypeError, ValueError):
            ref = None
        if ref is not None:
            return ref.token if ref.kind is MaterialTokenKind.IMAGE else ""
        if not raw or any(char in raw for char in "{}\r\n@:"):
            return ""
        return material_token(MaterialTokenNamespace.IMAGE, raw)

    def _request_asset_slot(self) -> None:
        occupied = {
            _placeholder_key(spec.target)
            for spec in (
                *tuple(getattr(self, "_asset_slot_specs", ())),
                *tuple(getattr(self, "_asset_group_specs", ())),
            )
        }
        name = next_numbered_name("图片", occupied)
        self._insert_asset_slot(
            len(tuple(getattr(self, "_asset_slot_specs", ()))),
            target=material_token(MaterialTokenNamespace.IMAGE, name),
            role_prefix="custom_image",
        )

    def _add_asset_slot_series(self, source_role: str) -> None:
        specs = list(getattr(self, "_asset_slot_specs", ()))
        source_index = next(
            (index for index, spec in enumerate(specs) if spec.role == source_role),
            -1,
        )
        if source_index < 0:
            return
        source = specs[source_index]
        source_name = _placeholder_key(source.target)
        occupied = {
            _placeholder_key(spec.target)
            for spec in (*specs, *tuple(getattr(self, "_asset_group_specs", ())))
        }
        prefix = numbered_series_prefix(source_name)
        candidate = next_series_name(source_name, occupied)
        insert_at = source_index + 1
        while (
            insert_at < len(specs)
            and is_numbered_series_name(
                _placeholder_key(specs[insert_at].target),
                prefix,
            )
        ):
            insert_at += 1
        self._insert_asset_slot(
            insert_at,
            target=material_token(MaterialTokenNamespace.IMAGE, candidate),
            role_prefix=source_role.split("__", 1)[0],
        )

    def _insert_asset_slot(self, index: int, *, target: str, role_prefix: str) -> bool:
        specs = list(getattr(self, "_asset_slot_specs", ()))
        occupied_roles = (
            {spec.role for spec in specs}
            | {spec.role for spec in getattr(self, "_asset_group_specs", ())}
            | set(self._asset_metadata)
        )
        serial = 2
        role = f"{role_prefix}__{serial}"
        while role in occupied_roles:
            serial += 1
            role = f"{role_prefix}__{serial}"
        normalized_target = self._normalized_asset_slot_target(target)
        spec = AssetSlotSpec(
            role=role,
            label=_placeholder_key(normalized_target),
            target=normalized_target,
        )
        specs.insert(max(0, min(index, len(specs))), spec)
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._store_asset_token_inventory(single_specs=specs)
        self._asset_slot_specs = tuple(specs)
        if not self._publish_scene_spec_mutation(snapshot, scope="asset_slot"):
            return False
        self._refresh_scene_spec_mutation_ui("asset_slot")
        Toast.show_success(f"已新增 {normalized_target}")
        return True

    def _commit_asset_slot_token(self, role: str, raw_target: str) -> bool:
        current = next(
            (spec for spec in self._asset_slot_specs if spec.role == role),
            None,
        )
        if current is None:
            return False
        target = self._normalized_asset_slot_target(raw_target)
        if not target:
            Toast.show_warning("Token 不能为空，也不能包含不成对的大括号或换行")
            edit = self._asset_slot_target_edits.get(role)
            if edit is not None:
                edit.setText(current.target)
            return False
        occupied = {
            spec.target for spec in self._asset_slot_specs if spec.role != role
        } | {spec.target for spec in self._asset_group_specs}
        if target in occupied:
            Toast.show_warning(f"Token 已存在：{target}")
            edit = self._asset_slot_target_edits.get(role)
            if edit is not None:
                edit.setText(current.target)
            return False
        if target == current.target:
            return False
        specs = [
            AssetSlotSpec(
                role=spec.role,
                label=spec.label,
                target=target if spec.role == role else spec.target,
                required=spec.required,
            )
            for spec in self._asset_slot_specs
        ]
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._store_asset_token_inventory(single_specs=specs)
        self._asset_slot_specs = tuple(specs)
        if not self._publish_scene_spec_mutation(snapshot, scope="asset_slot"):
            return False
        self._refresh_scene_spec_mutation_ui("asset_slot")
        Toast.show_success(f"已修改 Token：{target}")
        return True

    def _commit_asset_slot_label(self, role: str, raw_label: str) -> bool:
        current = next(
            (spec for spec in self._asset_slot_specs if spec.role == role),
            None,
        )
        if current is None:
            return False
        label = self._normalized_asset_display_name(raw_label)
        edit = getattr(self, "_asset_slot_name_edits", {}).get(role)
        if not label:
            Toast.show_warning("名称不能为空，且最多支持 120 个字符")
            if edit is not None:
                edit.setText(current.label)
            return False
        if label == current.label:
            return False
        specs = [
            AssetSlotSpec(
                role=spec.role,
                label=label if spec.role == role else spec.label,
                target=spec.target,
                required=spec.required,
            )
            for spec in self._asset_slot_specs
        ]
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._store_asset_token_inventory(single_specs=specs)
        self._asset_slot_specs = tuple(specs)
        if not self._publish_scene_spec_mutation(snapshot, scope="asset_slot"):
            return False
        self._refresh_scene_spec_mutation_ui("asset_slot")
        return True

    @staticmethod
    def _normalized_asset_display_name(value: object) -> str:
        normalized = " ".join(str(value or "").split())
        return normalized if 0 < len(normalized) <= 120 else ""

    def _remove_asset_slot(self, role: str) -> bool:
        spec = next(
            (item for item in self._asset_slot_specs if item.role == role),
            None,
        )
        if spec is None:
            return False
        source_path = self._path_for_asset_slot(role)
        if source_path and not confirm(
            "删除单图 Token",
            f"{spec.target} 已选择图片，删除后将同时移除该图片绑定。",
            confirm_text="删除",
            destructive=True,
            parent=self,
        ):
            return False
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._asset_paths.pop(role, None)
        self._asset_bindings.pop(role, None)
        self._image_material_rules.pop(f"image:{role}", None)
        self._asset_item_payloads = [
            item
            for item in self._asset_item_payloads
            if str(item.get("role", "") or "") != role
        ]
        self._asset_slot_specs = tuple(
            item for item in self._asset_slot_specs if item.role != role
        )
        self._store_asset_token_inventory(single_specs=list(self._asset_slot_specs))
        if not self._publish_scene_spec_mutation(snapshot, scope="asset_slot"):
            return False
        self._refresh_scene_spec_mutation_ui("asset_slot")
        Toast.show_success(f"已删除 {spec.target}")
        return True

    def _store_asset_token_inventory(
        self,
        *,
        single_specs: list[AssetSlotSpec] | tuple[AssetSlotSpec, ...] | None = None,
        group_specs: list[AssetGroupSpec] | tuple[AssetGroupSpec, ...] | None = None,
    ) -> None:
        """Persist the profile-owned image Token inventory as typed data.

        Scene schemas remain defaults only.  Once the user changes the inventory,
        this explicit snapshot is the sole source for both the single-image and
        multi-image sections.
        """

        singles = tuple(
            single_specs
            if single_specs is not None
            else getattr(self, "_asset_slot_specs", ())
        )
        groups = tuple(
            group_specs
            if group_specs is not None
            else getattr(self, "_asset_group_specs", ())
        )
        token_specs: list[AssetTokenSpec] = []
        for index, spec in enumerate(singles):
            token_specs.append(
                AssetTokenSpec(
                    token_id=spec.role,
                    token=spec.target,
                    label=spec.label,
                    cardinality="single",
                    source_kind="file",
                    order=(index + 1) * 10,
                    required=bool(spec.required),
                    recursive=False,
                    min_items=0,
                    max_items=1,
                )
            )
        group_offset = len(token_specs)
        for index, spec in enumerate(groups):
            token_specs.append(
                AssetTokenSpec(
                    token_id=spec.role,
                    token=spec.target,
                    label=spec.label,
                    cardinality="multiple",
                    source_kind=spec.source_kind,
                    order=(group_offset + index + 1) * 10,
                    required=bool(spec.required),
                    recursive=bool(spec.recursive),
                    min_items=int(spec.min_items or 0),
                    max_items=spec.max_items,
                    order_policy=spec.order_policy,
                    naming_template=spec.naming_template,
                )
            )
        self._selected_profile().asset_token_specs = token_specs

    def _asset_groups_from_scene(self, scene) -> tuple[AssetGroupSpec, ...]:
        profile = self._selected_profile()
        token_specs = tuple(getattr(profile, "asset_token_specs", ()) or ())
        if token_specs:
            return tuple(
                AssetGroupSpec(
                    role=spec.token_id,
                    label=spec.label or _placeholder_key(spec.token),
                    target=spec.token,
                    required=bool(spec.required),
                    recursive=bool(spec.recursive),
                    min_items=int(spec.min_items or 0),
                    max_items=spec.max_items,
                    order_policy=spec.order_policy,
                    naming_template=spec.naming_template,
                    source_kind=spec.source_kind,
                )
                for spec in token_specs
                if spec.cardinality == "multiple"
            )
        return self._base_asset_groups_from_scene(scene)

    def _base_asset_groups_from_scene(self, scene) -> tuple[AssetGroupSpec, ...]:
        groups: dict[str, AssetGroupSpec] = {
            "qualification": AssetGroupSpec(
                role="qualification",
                label="资质证书",
                target=material_token(
                    MaterialTokenNamespace.IMAGE,
                    "资质证书1",
                ),
                required=False,
                recursive=True,
                max_items=None,
            )
        }
        input_profile = getattr(scene, "input_source_profile", None)
        if input_profile is None:
            return tuple(groups.values())
        schema_ids = _material_schema_ids_from_profile(input_profile)
        schemas = _material_schemas_from_ids(schema_ids)
        requirements = build_material_requirements(
            schema_ids[0] if schema_ids else "",
            schema_ids=schema_ids,
            extra_required_asset_roles=tuple(
                getattr(input_profile, "required_image_roles", ()) or ()
            ),
        )
        required_roles = set(requirements.required_asset_roles)
        for schema in schemas:
            for role_spec in schema.asset_roles:
                role = str(role_spec.role or "").strip().lower().replace(" ", "_")
                if (
                    not role
                    or _material_role_is_attachment(role_spec)
                    or str(getattr(role_spec, "cardinality", "single") or "single")
                    .strip()
                    .lower()
                    != "multiple"
                    or str(getattr(role_spec, "source_kind", "directory") or "directory")
                    .strip()
                    .lower()
                    != "directory"
                ):
                    continue
                required = role in required_roles or bool(role_spec.required)
                existing = groups.get(role)
                groups[role] = AssetGroupSpec(
                    role=role,
                    label=(
                        existing.label
                        if existing is not None
                        else role_spec.label or _asset_role_label(role)
                    ),
                    target=(
                        existing.target
                        if existing is not None
                        else _asset_slot_target_for_role(role)
                    ),
                    required=required,
                    recursive=bool(getattr(role_spec, "recursive", True)),
                    min_items=max(
                        int(getattr(role_spec, "min_items", 0) or 0),
                        1 if required else 0,
                    ),
                    max_items=getattr(role_spec, "max_items", None),
                    order_policy=str(
                        getattr(role_spec, "order_policy", "natural_path")
                        or "natural_path"
                    ),
                    naming_template=str(
                        getattr(role_spec, "naming_template", "{role}_{sequence:03d}")
                        or "{role}_{sequence:03d}"
                    ),
                    source_kind=str(
                        getattr(role_spec, "source_kind", "directory") or "directory"
                    ),
                )
        return tuple(groups.values())

    def _request_asset_group(self) -> None:
        occupied = {
            _placeholder_key(spec.target)
            for spec in (
                *tuple(getattr(self, "_asset_group_specs", ())),
                *tuple(getattr(self, "_asset_slot_specs", ())),
            )
        }
        name = next_numbered_name("图片组", occupied)
        self._insert_asset_group(
            len(tuple(getattr(self, "_asset_group_specs", ()))),
            target=material_token(MaterialTokenNamespace.IMAGE, name),
            role_prefix="custom_image_group",
        )

    def _add_asset_group_series(self, source_role: str) -> None:
        specs = list(getattr(self, "_asset_group_specs", ()))
        source_index = next(
            (index for index, spec in enumerate(specs) if spec.role == source_role),
            -1,
        )
        if source_index < 0:
            return
        source = specs[source_index]
        source_name = _placeholder_key(source.target)
        occupied = {
            _placeholder_key(spec.target)
            for spec in (*specs, *tuple(getattr(self, "_asset_slot_specs", ())))
        }
        prefix = numbered_series_prefix(source_name)
        candidate = next_series_name(source_name, occupied)
        insert_at = source_index + 1
        while (
            insert_at < len(specs)
            and is_numbered_series_name(
                _placeholder_key(specs[insert_at].target),
                prefix,
            )
        ):
            insert_at += 1
        self._insert_asset_group(
            insert_at,
            target=material_token(MaterialTokenNamespace.IMAGE, candidate),
            role_prefix=source_role.split("__", 1)[0],
        )

    def _insert_asset_group(self, index: int, *, target: str, role_prefix: str) -> bool:
        specs = list(getattr(self, "_asset_group_specs", ()))
        occupied_roles = (
            {spec.role for spec in specs}
            | {spec.role for spec in getattr(self, "_asset_slot_specs", ())}
            | set(self._asset_metadata)
        )
        serial = 2
        role = f"{role_prefix}__{serial}"
        while role in occupied_roles:
            serial += 1
            role = f"{role_prefix}__{serial}"
        normalized_target = self._normalized_asset_slot_target(target)
        spec = AssetGroupSpec(
            role=role,
            label=_placeholder_key(normalized_target),
            target=normalized_target,
            recursive=True,
            max_items=None,
        )
        specs.insert(max(0, min(index, len(specs))), spec)
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._store_asset_token_inventory(group_specs=specs)
        self._asset_group_specs = tuple(specs)
        if not self._publish_scene_spec_mutation(snapshot, scope="asset_group"):
            return False
        self._refresh_scene_spec_mutation_ui("asset_group")
        Toast.show_success(f"已新增 {normalized_target}")
        return True

    def _commit_asset_group_token(self, role: str, raw_target: str) -> bool:
        current = next(
            (spec for spec in self._asset_group_specs if spec.role == role),
            None,
        )
        if current is None:
            return False
        target = self._normalized_asset_slot_target(raw_target)
        if not target:
            Toast.show_warning("Token 不能为空，也不能包含不成对的大括号或换行")
            edit = self._asset_group_token_edits.get(role)
            if edit is not None:
                edit.setText(current.target)
            return False
        occupied = {
            spec.target for spec in self._asset_group_specs if spec.role != role
        } | {spec.target for spec in self._asset_slot_specs}
        if target in occupied:
            Toast.show_warning(f"Token 已存在：{target}")
            edit = self._asset_group_token_edits.get(role)
            if edit is not None:
                edit.setText(current.target)
            return False
        if target == current.target:
            return False
        specs = [
            AssetGroupSpec(
                role=spec.role,
                label=spec.label,
                target=target if spec.role == role else spec.target,
                required=spec.required,
                recursive=spec.recursive,
                min_items=spec.min_items,
                max_items=spec.max_items,
                order_policy=spec.order_policy,
                naming_template=spec.naming_template,
                source_kind=spec.source_kind,
            )
            for spec in self._asset_group_specs
        ]
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._store_asset_token_inventory(group_specs=specs)
        self._asset_group_specs = tuple(specs)
        if not self._publish_scene_spec_mutation(snapshot, scope="asset_group"):
            return False
        self._refresh_scene_spec_mutation_ui("asset_group")
        Toast.show_success(f"已修改 Token：{target}")
        return True

    def _commit_asset_group_label(self, role: str, raw_label: str) -> bool:
        current = next(
            (spec for spec in self._asset_group_specs if spec.role == role),
            None,
        )
        if current is None:
            return False
        label = self._normalized_asset_display_name(raw_label)
        edit = getattr(self, "_asset_group_name_edits", {}).get(role)
        if not label:
            Toast.show_warning("名称不能为空，且最多支持 120 个字符")
            if edit is not None:
                edit.setText(current.label)
            return False
        if label == current.label:
            return False
        specs = [
            AssetGroupSpec(
                role=spec.role,
                label=label if spec.role == role else spec.label,
                target=spec.target,
                required=spec.required,
                recursive=spec.recursive,
                min_items=spec.min_items,
                max_items=spec.max_items,
                order_policy=spec.order_policy,
                naming_template=spec.naming_template,
                source_kind=spec.source_kind,
            )
            for spec in self._asset_group_specs
        ]
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._store_asset_token_inventory(group_specs=specs)
        self._asset_group_specs = tuple(specs)
        if not self._publish_scene_spec_mutation(snapshot, scope="asset_group"):
            return False
        self._refresh_scene_spec_mutation_ui("asset_group")
        return True

    def _remove_asset_group(self, role: str) -> bool:
        spec = next(
            (item for item in self._asset_group_specs if item.role == role),
            None,
        )
        if spec is None:
            return False
        binding = self._asset_bindings.get(role)
        if binding is not None and str(binding.source_path or "").strip() and not confirm(
            "删除多图 Token",
            f"{spec.target} 已选择文件夹，删除后将同时移除该文件夹绑定。",
            confirm_text="删除",
            destructive=True,
            parent=self,
        ):
            return False
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._asset_bindings.pop(role, None)
        self._image_material_rules.pop(f"image:{role}", None)
        self._asset_paths.pop(role, None)
        self._asset_item_payloads = [
            item
            for item in self._asset_item_payloads
            if str(item.get("role", "") or "") != role
        ]
        self._asset_group_specs = tuple(
            item for item in self._asset_group_specs if item.role != role
        )
        self._store_asset_token_inventory(group_specs=list(self._asset_group_specs))
        if not self._publish_scene_spec_mutation(snapshot, scope="asset_group"):
            return False
        self._refresh_scene_spec_mutation_ui("asset_group")
        Toast.show_success(f"已删除 {spec.target}")
        return True

    def _request_independent_attachment(self) -> None:
        self._request_attachment_role(source_kind="single_file")

    def _request_attachment_folder(self) -> None:
        self._request_attachment_role(source_kind="directory_package")

    def _request_attachment_role(self, *, source_kind: str) -> bool:
        """Create a persistent unbound definition; source selection stays separate."""

        is_folder = source_kind == "directory_package"
        name_prefix = "附件文件夹" if is_folder else "附件"
        role = self._next_attachment_role_name(name_prefix)
        spec = AttachmentRoleSpec(
            role=role,
            label=role,
            accepted_types=(
                "image",
                "pdf",
                "docx",
                "xlsx",
                "csv",
                "markdown",
                "txt",
            ),
            cardinality="multiple" if is_folder else "single",
            source_kind=source_kind,
            recursive=is_folder,
            max_items=None if is_folder else 1,
            origin="profile",
        )
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._attachment_role_specs = (
            *tuple(getattr(self, "_attachment_role_specs", ())),
            spec,
        )
        self._store_attachment_role_inventory()
        if not self._publish_scene_spec_mutation(snapshot, scope="attachment"):
            return False
        self._refresh_scene_spec_mutation_ui("attachment")
        Toast.show_success(f"已新增 {spec.anchor_token}")
        return True

    def _add_attachment_role_series(self, source_role: str) -> bool:
        specs = list(getattr(self, "_attachment_role_specs", ()))
        source_index = next(
            (index for index, spec in enumerate(specs) if spec.role == source_role),
            -1,
        )
        if source_index < 0:
            return False
        source = specs[source_index]
        name_prefix = (
            "附件" if self._attachment_role_is_independent(source) else "附件文件夹"
        )
        role = self._next_attachment_role_name(name_prefix)
        specs.insert(
            source_index + 1,
            replace(
                source,
                role=role,
                label=role,
                required=False,
                min_items=0,
                origin="profile",
            ),
        )
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._attachment_role_specs = tuple(specs)
        self._store_attachment_role_inventory()
        if not self._publish_scene_spec_mutation(snapshot, scope="attachment"):
            return False
        self._refresh_scene_spec_mutation_ui("attachment")
        Toast.show_success(f"已新增 {material_token(MaterialTokenNamespace.ATTACHMENT, role)}")
        return True

    def _next_attachment_role_name(self, prefix: str) -> str:
        occupied = {
            spec.role for spec in tuple(getattr(self, "_attachment_role_specs", ()))
        } | set(getattr(self, "_attachment_bindings", {}))
        serial = 1
        candidate = f"{prefix}{serial}"
        while candidate in occupied:
            serial += 1
            candidate = f"{prefix}{serial}"
        return candidate

    def _store_attachment_role_inventory(self) -> None:
        profile = self._selected_profile()
        profile.attachment_role_specs = list(self._attachment_role_specs)
        profile.attachment_bindings = dict(self._attachment_bindings)
        self._update_profile_item(self._current_profile_index)

    def _remove_attachment_role(self, role: str) -> bool:
        spec = self._attachment_role_spec(role)
        if spec is None or not spec.deletable:
            return False
        binding = self._attachment_bindings.get(role)
        if binding is not None and tuple(getattr(binding, "items", ()) or ()):
            if not confirm(
                "删除附件",
                f"{self._attachment_role_display_name(spec)} 已选择来源，删除后将同时移除绑定。",
                confirm_text="删除",
                destructive=True,
                parent=self,
            ):
                return False
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._attachment_bindings.pop(role, None)
        self._attachment_legacy_errors.pop(role, None)
        self._asset_metadata.pop(role, None)
        self._attachment_role_specs = tuple(
            item for item in self._attachment_role_specs if item.role != role
        )
        self._store_attachment_role_inventory()
        if not self._publish_scene_spec_mutation(snapshot, scope="attachment"):
            return False
        self._refresh_scene_spec_mutation_ui("attachment")
        Toast.show_success(f"已删除 {spec.label}")
        return True

    def _attachment_roles_from_scene(self, scene) -> tuple[AttachmentRoleSpec, ...]:
        profile = self._selected_profile()
        persisted_specs = tuple(
            getattr(profile, "attachment_role_specs", ()) or ()
        )
        input_profile = getattr(scene, "input_source_profile", None)
        schema_ids = (
            _material_schema_ids_from_profile(input_profile)
            if input_profile is not None
            else ()
        )
        required_roles: set[str] = set()
        if schema_ids:
            schema_id = schema_ids[0]
            extra_required_roles = tuple(
                getattr(input_profile, "required_image_roles", ()) or ()
            )
            requirements = build_material_requirements(
                schema_id,
                schema_ids=schema_ids,
                extra_required_asset_roles=extra_required_roles,
            )
            required_roles = set(requirements.required_asset_roles)
        schemas = _material_schemas_from_ids(schema_ids)

        specs: list[AttachmentRoleSpec] = list(persisted_specs)
        seen_roles: set[str] = {spec.role for spec in specs}
        if not persisted_specs:
            for schema in schemas:
                for role_spec in schema.asset_roles:
                    role = str(role_spec.role or "").strip().lower().replace(" ", "_")
                    if (
                        not role
                        or role in seen_roles
                        or not _material_role_is_attachment(role_spec)
                    ):
                        continue
                    seen_roles.add(role)
                    cardinality = str(
                        getattr(role_spec, "cardinality", "single") or "single"
                    ).strip().casefold()
                    raw_source_kind = str(
                        getattr(role_spec, "source_kind", "file") or "file"
                    ).strip().casefold()
                    source_kind = (
                        "directory_package"
                        if raw_source_kind == "directory"
                        else (
                            "file_set"
                            if cardinality == "multiple"
                            else "single_file"
                        )
                    )
                    specs.append(
                        AttachmentRoleSpec(
                            role=role,
                            label=role_spec.label or _asset_role_label(role),
                            accepted_types=tuple(
                                role_spec.accepted_types or ("image", "pdf")
                            ),
                            required=role in required_roles
                            or bool(role_spec.required),
                            cardinality=cardinality,
                            source_kind=source_kind,
                            recursive=bool(
                                getattr(role_spec, "recursive", False)
                            ),
                            min_items=int(
                                getattr(role_spec, "min_items", 0) or 0
                            ),
                            max_items=getattr(role_spec, "max_items", 1),
                            origin="schema",
                        )
                    )

        # Profile-owned bindings are also inventory definitions. This keeps
        # user-added attachments visible after save/reload without introducing
        # a second, UI-only attachment-spec persistence model.
        bindings = dict(getattr(self, "_attachment_bindings", {}) or {})
        for role, binding in bindings.items():
            normalized_role = str(role or "").strip().lower().replace(" ", "_")
            if not normalized_role or normalized_role in seen_roles:
                continue
            seen_roles.add(normalized_role)
            source_kind = self._attachment_enum_value(
                getattr(binding, "source_kind", "single_file")
            )
            cardinality = self._attachment_enum_value(
                getattr(binding, "cardinality", "single")
            )
            specs.append(
                AttachmentRoleSpec(
                    role=normalized_role,
                    label=(
                        str(getattr(binding, "label", "") or "").strip()
                        or normalized_role
                    ),
                    accepted_types=self._attachment_types_from_binding(binding),
                    required=bool(getattr(binding, "required", False)),
                    cardinality=cardinality,
                    source_kind=source_kind,
                    recursive=bool(getattr(binding, "recursive", False)),
                    processing_mode=self._attachment_enum_value(
                        getattr(binding, "processing_mode", "passthrough")
                    ),
                    min_items=int(getattr(binding, "min_items", 0) or 0),
                    max_items=getattr(binding, "max_items", 1),
                    origin="profile",
                )
            )
        return tuple(specs)

    @staticmethod
    def _attachment_enum_value(value: object) -> str:
        return str(getattr(value, "value", value) or "").strip().casefold()

    @staticmethod
    def _attachment_types_from_binding(binding) -> tuple[str, ...]:
        media_types = {
            str(value or "").strip().casefold()
            for value in tuple(getattr(binding, "accepted_media_types", ()) or ())
        }
        extensions = {
            str(value or "").strip().casefold()
            for value in tuple(getattr(binding, "accepted_extensions", ()) or ())
        }
        resolved: list[str] = []
        contracts = (
            ("image", any(value.startswith("image/") for value in media_types)),
            ("pdf", "application/pdf" in media_types or ".pdf" in extensions),
            ("docx", ".docx" in extensions),
            ("xlsx", bool({".xlsx", ".xls"} & extensions)),
            ("csv", ".csv" in extensions),
            ("markdown", bool({".md", ".markdown"} & extensions)),
            ("txt", ".txt" in extensions),
        )
        for kind, matched in contracts:
            if matched:
                resolved.append(kind)
        return tuple(resolved) or ("image", "pdf", "docx", "xlsx", "csv", "markdown", "txt")

    def _sync_asset_slot_rows(self) -> None:
        if not hasattr(self, "_asset_slots_layout"):
            return
        controller = getattr(self, "_asset_slots_controller", None)
        if controller is None:
            controller = KeyedWidgetListController(
                layout=self._asset_slots_layout,
                create_widget=lambda spec: self._build_asset_slot_row(
                    spec.role,
                    spec.label,
                    spec.target,
                    parent=self._asset_slots_container,
                ),
                update_widget=self._update_asset_slot_row,
                dispose_widget=self._dispose_asset_slot_row,
                key=self._asset_slot_row_key,
            )
            self._asset_slots_controller = controller
        change = controller.reconcile(self._asset_slot_specs)
        if hasattr(self, "_single_assets_count"):
            self._single_assets_count.setText(f"{len(self._asset_slot_specs)} 项")
        for role, edit in self._asset_slot_alt_text_inputs.items():
            edit.blockSignals(True)
            try:
                edit.setText(str(self._asset_metadata.get(role, {}).get("alt_text", "") or ""))
            finally:
                edit.blockSignals(False)
        if change.added:
            apply_row_theme = getattr(self, "_apply_asset_row_theme", None)
            if callable(apply_row_theme):
                apply_row_theme(get_theme())
        guide = getattr(self, "_asset_slots_column_guide", None)
        if guide is not None:
            self._apply_asset_slot_column_metrics(guide.metrics())
        refresh_layout_chain_later(self._asset_slots_container)
        sync_rules = getattr(self, "_sync_image_material_rule_rows", None)
        if callable(sync_rules):
            sync_rules()

    def _sync_attachment_role_rows(self) -> None:
        if not hasattr(self, "_attachment_folders_layout"):
            return
        independent_specs = tuple(
            spec
            for spec in self._attachment_role_specs
            if self._attachment_role_is_independent(spec)
        )
        folder_specs = tuple(
            spec
            for spec in self._attachment_role_specs
            if not self._attachment_role_is_independent(spec)
        )
        independent_change = self._sync_attachment_role_section(
            specs=independent_specs,
            controller_name="_independent_attachment_roles_controller",
            layout=self._independent_attachments_layout,
            container=self._independent_attachments_container,
            count_label=self._independent_attachments_count,
            guide=self._independent_attachments_column_guide,
            scope="independent",
        )
        folder_change = self._sync_attachment_role_section(
            specs=folder_specs,
            controller_name="_attachment_folder_roles_controller",
            layout=self._attachment_folders_layout,
            container=self._attachment_folders_container,
            count_label=self._attachment_folders_count,
            guide=self._attachment_folders_column_guide,
            scope="folder",
        )
        if independent_change.added or folder_change.added:
            apply_row_theme = getattr(self, "_apply_asset_row_theme", None)
            if callable(apply_row_theme):
                apply_row_theme(get_theme())

    def _sync_attachment_role_section(
        self,
        *,
        specs: tuple[AttachmentRoleSpec, ...],
        controller_name: str,
        layout,
        container,
        count_label,
        guide,
        scope: str,
    ):
        controller = getattr(self, controller_name, None)
        if controller is None:
            controller = KeyedWidgetListController(
                layout=layout,
                create_widget=lambda spec: self._build_attachment_role_row(
                    spec,
                    parent=container,
                ),
                update_widget=self._update_attachment_role_row,
                dispose_widget=self._dispose_attachment_role_row,
                key=self._attachment_role_row_key,
            )
            setattr(self, controller_name, controller)
        change = controller.reconcile(specs)
        count_label.setText(f"{len(specs)} 项")
        self._apply_attachment_column_metrics(guide.metrics(), scope=scope)
        refresh_layout_chain_later(container)
        return change

    @staticmethod
    def _attachment_role_is_independent(spec: AttachmentRoleSpec) -> bool:
        source_kind = str(getattr(spec, "source_kind", "single_file") or "")
        return source_kind.strip().casefold() == "single_file"

    def _attachment_role_display_name(self, spec: AttachmentRoleSpec) -> str:
        binding = dict(getattr(self, "_attachment_bindings", {}) or {}).get(
            spec.role
        )
        return (
            str(getattr(binding, "label", "") or "").strip()
            or spec.label
        )

    def _commit_attachment_role_token(self, role: str, raw_token: str) -> bool:
        spec = self._attachment_role_spec(role)
        if spec is None or not spec.deletable:
            return False
        try:
            ref = parse_material_token(raw_token)
        except (TypeError, ValueError):
            ref = None
        edit = self._attachment_role_token_edits.get(role)
        if ref is None or ref.kind is not MaterialTokenKind.ATTACHMENT:
            Toast.show_warning("附件占位符必须使用 {{@attach:名称}} 格式。")
            if edit is not None:
                edit.setText(spec.anchor_token)
            return False
        new_role = ref.identifier
        if new_role == role:
            return False
        if any(item.role == new_role for item in self._attachment_role_specs):
            Toast.show_warning(f"占位符已存在：{ref.token}")
            if edit is not None:
                edit.setText(spec.anchor_token)
            return False
        updated_specs = tuple(
            replace(item, role=new_role) if item.role == role else item
            for item in self._attachment_role_specs
        )
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        binding = self._attachment_bindings.pop(role, None)
        if binding is not None:
            self._attachment_bindings[new_role] = replace(binding, role=new_role)
        legacy_error = self._attachment_legacy_errors.pop(role, "")
        if legacy_error:
            self._attachment_legacy_errors[new_role] = legacy_error
        self._attachment_role_specs = updated_specs
        self._store_attachment_role_inventory()
        if not self._publish_scene_spec_mutation(snapshot, scope="attachment"):
            return False
        self._refresh_scene_spec_mutation_ui("attachment")
        Toast.show_success(f"已修改占位符：{ref.token}")
        return True

    def _commit_attachment_role_label(self, role: str, raw_label: str) -> bool:
        spec = self._attachment_role_spec(role)
        if spec is None:
            return False
        label = self._normalized_asset_display_name(raw_label)
        edit = self._attachment_role_name_edits.get(role)
        if not label:
            Toast.show_warning("名称不能为空，且最多支持 120 个字符。")
            if edit is not None:
                edit.setText(self._attachment_role_display_name(spec))
            return False
        snapshot = self._capture_scene_spec_mutation_snapshot()
        if snapshot is None:
            return False
        self._attachment_role_specs = tuple(
            replace(item, label=label) if item.role == role else item
            for item in self._attachment_role_specs
        )
        binding = self._attachment_bindings.get(role)
        if binding is not None:
            self._attachment_bindings[role] = replace(binding, label=label)
        self._store_attachment_role_inventory()
        if not self._publish_scene_spec_mutation(snapshot, scope="attachment"):
            return False
        self._refresh_scene_spec_mutation_ui("attachment")
        return True

    def _update_attachment_role_row(
        self,
        row,
        spec: AttachmentRoleSpec,
        index: int,
    ) -> None:
        role = spec.role
        self._attachment_role_index_labels[role].setText(str(index + 1))
        token = spec.anchor_token
        token_edit = self._attachment_role_token_edits[role]
        if token_edit.text() != token:
            token_edit.setText(token)
        name_edit = self._attachment_role_name_edits[role]
        name = self._attachment_role_display_name(spec)
        if not name_edit.hasFocus() and name_edit.text() != name:
            name_edit.setText(name)
        self._attachment_role_clear_buttons[role].setToolTip(f"清除{spec.label}")
        self._attachment_role_open_buttons[role].setToolTip(
            f"打开{spec.label}所在文件夹"
        )
        chooses_directory = spec.source_kind == "directory_package"
        self._attachment_role_choose_buttons[role].setToolTip(
            f"选择{spec.label}{'文件夹' if chooses_directory else '文件'}"
        )
        add_btn = self._attachment_role_add_buttons.get(role)
        if add_btn is not None:
            add_btn.setToolTip(f"新增一项{spec.label}")
        refresh_btn = self._attachment_role_refresh_buttons.get(role)
        if refresh_btn is not None:
            refresh_btn.setToolTip(f"重新扫描{spec.label}")
        remove_btn = self._attachment_role_remove_buttons.get(role)
        if remove_btn is not None:
            remove_btn.setEnabled(spec.deletable)
            remove_btn.setToolTip(
                f"删除{spec.label}" if spec.deletable else "场景固定附件不可删除"
            )
        drop_controller = self._attachment_drop_controllers.get(role)
        if drop_controller is not None:
            drop_controller.set_policy(_attachment_path_policy(spec))
        apply_token_row_style(
            row,
            object_name="attachment_role_row",
            is_last=index
            == len(
                tuple(
                    item
                    for item in self._attachment_role_specs
                    if self._attachment_role_is_independent(item)
                    == self._attachment_role_is_independent(spec)
                )
            )
            - 1,
        )
        row.setVisible(True)

    @staticmethod
    def _asset_slot_row_key(spec: AssetSlotSpec) -> str:
        """Use the durable material role as the row identity.

        Labels and tokens are editable presentation values and are refreshed by
        ``_update_asset_slot_row``.  Treating them as identity used to destroy
        and recreate the row during restore, which also discarded focus and
        construction-time visual state.
        """

        return spec.role

    @staticmethod
    def _attachment_role_row_key(
        spec: AttachmentRoleSpec,
    ) -> str:
        """Attachment rows retain identity while presentation facts update."""

        return spec.role

    def _dispose_asset_slot_row(self, widget) -> None:
        role = str(widget.property("asset_role") or "")
        if self._asset_slot_rows.get(role) is widget:
            self._asset_slot_rows.pop(role, None)
            getattr(self, "_asset_slot_index_labels", {}).pop(role, None)
            getattr(self, "_asset_slot_target_edits", {}).pop(role, None)
            getattr(self, "_asset_slot_name_edits", {}).pop(role, None)
            getattr(self, "_asset_slot_path_edits", {}).pop(role, None)
            getattr(self, "_asset_slot_path_widgets", {}).pop(role, None)
            getattr(self, "_asset_slot_action_cells", {}).pop(role, None)
            getattr(self, "_asset_slot_column_layouts", {}).pop(role, None)
            self._asset_slot_choose_buttons.pop(role, None)
            self._asset_slot_thumbnail_labels.pop(role, None)
            self._asset_slot_status_labels.pop(role, None)
            self._asset_slot_alt_text_inputs.pop(role, None)
            self._asset_slot_open_buttons.pop(role, None)
            self._asset_slot_clear_buttons.pop(role, None)
            getattr(self, "_asset_slot_add_buttons", {}).pop(role, None)
            getattr(self, "_asset_slot_remove_buttons", {}).pop(role, None)
            getattr(self, "_asset_slot_action_strips", {}).pop(role, None)
            getattr(self, "_asset_slot_drop_controllers", {}).pop(role, None)
        widget.setParent(None)
        widget.deleteLater()

    def _dispose_attachment_role_row(self, widget) -> None:
        role = str(widget.property("attachment_role") or "")
        if self._attachment_role_rows.get(role) is widget:
            self._attachment_role_rows.pop(role, None)
            self._attachment_role_index_labels.pop(role, None)
            self._attachment_role_preview_labels.pop(role, None)
            self._attachment_role_token_edits.pop(role, None)
            self._attachment_role_name_edits.pop(role, None)
            self._attachment_role_path_edits.pop(role, None)
            self._attachment_role_source_widgets.pop(role, None)
            self._attachment_role_action_cells.pop(role, None)
            self._attachment_role_column_layouts.pop(role, None)
            self._attachment_role_status_labels.pop(role, None)
            self._attachment_role_choose_buttons.pop(role, None)
            self._attachment_role_open_buttons.pop(role, None)
            self._attachment_role_clear_buttons.pop(role, None)
            self._attachment_role_add_buttons.pop(role, None)
            self._attachment_role_remove_buttons.pop(role, None)
            self._attachment_role_refresh_buttons.pop(role, None)
            self._attachment_role_action_strips.pop(role, None)
            self._attachment_preparation_summaries.pop(role, None)
            getattr(self, "_attachment_drop_controllers", {}).pop(role, None)
        widget.setParent(None)
        widget.deleteLater()


__all__ = ["SceneSpecPresenterMixin"]
