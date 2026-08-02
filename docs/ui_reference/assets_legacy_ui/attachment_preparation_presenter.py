"""Presenter boundary for the attachment package preparation workbench."""

from __future__ import annotations

from src.config.entity import EntityProfile, clone_entity_profile
from src.qt_api import QDialog, Qt
from src.shared.ui.toast import Toast
from src.ui.panels.assets.attachment_preparation_dialog import (
    AttachmentPreparationDialog,
)
from src.ui.panels.assets.fields import MATERIAL_FIELD_DRAFT_PREFIX


class AttachmentPreparationPresenterMixin:
    """Use the checked generation scope for status, editing, and commit."""

    def _attachment_preparation_profile_indexes(self) -> list[int]:
        profile_list = getattr(self, "_profile_list", None)
        profiles = tuple(getattr(self, "_profiles", ()) or ())
        if profile_list is None:
            return list(range(len(profiles)))
        return [
            index
            for index in range(min(profile_list.count(), len(profiles)))
            if profile_list.item(index) is not None
            and profile_list.item(index).checkState() == Qt.Checked
        ]

    def _attachment_preparation_scope_profiles(
        self,
        indexes: list[int] | None = None,
    ) -> list[EntityProfile]:
        """Snapshot checked profiles without persisting or switching editors."""

        scope_indexes = (
            self._attachment_preparation_profile_indexes()
            if indexes is None
            else list(indexes)
        )
        profiles: list[EntityProfile] = []
        for index in scope_indexes:
            if not 0 <= index < len(self._profiles):
                continue
            profile = self._profiles[index]
            if index != self._current_profile_index:
                profiles.append(clone_entity_profile(profile))
                continue
            fields = self._editor_fields()
            declared = [
                str(key or "").strip()
                for key in (
                    *getattr(self, "_declared_field_keys", ()),
                    *getattr(self, "_manual_field_keys", ()),
                    *fields.keys(),
                )
                if str(key or "").strip()
                and not str(key).startswith(MATERIAL_FIELD_DRAFT_PREFIX)
            ]
            profiles.append(
                clone_entity_profile(
                    profile,
                    profile_id=self._profile_id_edit.text().strip(),
                    profile_name=self._profile_name_edit.text().strip(),
                    fields=fields,
                    declared_field_keys=list(dict.fromkeys(declared)),
                    assets_dir=self._assets_picker.path().strip(),
                    asset_paths=dict(self._asset_paths),
                    asset_bindings=self._copy_asset_bindings(),
                    asset_metadata=self._current_asset_metadata(),
                    asset_items=list(self._asset_item_payloads),
                    image_material_rules=dict(self._image_material_rules),
                    attachment_bindings=dict(self._attachment_bindings),
                )
            )
        return profiles

    def _open_attachment_preparation(self, role: str) -> bool:
        role = str(role or "").strip()
        binding = dict(getattr(self, "_attachment_bindings", {}) or {}).get(role)
        if binding is None or not tuple(getattr(binding, "items", ()) or ()):
            Toast.show_warning("请先选择附件文件或附件文件夹")
            return False
        snapshot = self._capture_profile_structure_mutation_snapshot()
        if snapshot is None:
            Toast.show_warning("资料字段存在冲突，暂时无法打开附件包准备")
            return False

        scope_indexes = self._attachment_preparation_profile_indexes()
        if not scope_indexes:
            Toast.show_warning("请先勾选至少一条本次生成数据")
            return False
        scope_profiles = self._attachment_preparation_scope_profiles(scope_indexes)
        if not scope_profiles:
            Toast.show_warning("本次生成数据不可用，请重新选择")
            return False
        checked_states = [
            self._profile_list.item(index).checkState() == Qt.Checked
            for index in range(self._profile_list.count())
        ]
        current_id = str(self._selected_profile().profile_id or "")
        dialog_current_index = (
            scope_indexes.index(self._current_profile_index)
            if self._current_profile_index in scope_indexes
            else 0
        )
        dialog = AttachmentPreparationDialog(
            role=role,
            binding=binding,
            profiles=scope_profiles,
            current_profile_index=dialog_current_index,
            image_token_bindings=self._attachment_image_token_bindings(),
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return False

        prepared = dialog.result_profiles()
        if not prepared:
            return False
        if dialog.profiles_replaced():
            self._profiles = prepared
            checked_states = [True] * len(prepared)
        else:
            if len(prepared) != len(scope_indexes):
                Toast.show_warning("附件包准备结果与本次生成范围不一致，未保存修改")
                return False
            for index, profile in zip(scope_indexes, prepared):
                self._profiles[index] = profile

        select_index = next(
            (
                index
                for index, profile in enumerate(self._profiles)
                if current_id and str(profile.profile_id or "") == current_id
            ),
            min(self._current_profile_index, len(self._profiles) - 1),
        )
        self._reload_profile_list(select_index=select_index)
        self._syncing_profile_list = True
        try:
            for index, checked in enumerate(checked_states[: self._profile_list.count()]):
                item = self._profile_list.item(index)
                if item is not None:
                    item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        finally:
            self._syncing_profile_list = False
        self._refresh_profile_item_labels()
        if not self._publish_profile_structure_mutation(snapshot):
            return False
        self._material_persistence.refresh_actions()
        self._refresh_summary()
        # The preparation card is the persistent confirmation surface.  Do
        # not add a transient success card after closing the workbench.
        return True


__all__ = ["AttachmentPreparationPresenterMixin"]
