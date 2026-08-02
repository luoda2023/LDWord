"""Presenter mixin for local asset file path operations."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.config.materials import is_supported_image_path
from src.config.attachment_materials import AttachmentProcessingMode
from src.qt_api import QDesktopServices, QFileDialog, QUrl
from src.services.material_attachments import (
    AttachmentRequirementKind,
    build_attachment_binding,
    build_directory_attachment_binding,
    scan_attachment_token_requirements,
)
from src.shared.ui.toast import Toast
from src.ui.panels.assets import AttachmentRoleSpec
from src.ui.panels.assets.fields import _asset_role_label
from src.ui.panels.assets.image_helpers import _image_file_dialog_filter
from src.ui.panels.assets.mutation_transaction import (
    capture_material_mutation_snapshot,
    publish_or_rollback_material_mutation,
)
from src.ui.panels.assets.roles import _attachment_path_policy


class AssetFileOperationsPresenterMixin:
    """Select, drag, clear, reveal, and open local material paths."""

    def _path_for_asset_slot(self, role: str, asset_items=None) -> str:
        items = asset_items if asset_items is not None else self._current_asset_items()
        for item in items:
            if item.role == role and item.path:
                return item.path
        return str(self._asset_paths.get(role) or "")

    def _select_asset_file(self, role: str) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            _image_file_dialog_filter(),
        )
        if not file_path:
            return
        self._apply_asset_slot_path(role, file_path)

    def _select_attachment_file(self, role: str) -> None:
        spec = self._attachment_role_spec(role)
        if spec is None:
            Toast.show_warning("附件角色已不存在，请刷新后重试。")
            return
        policy = _attachment_path_policy(spec)
        if policy.path_kind == "directory":
            directory = QFileDialog.getExistingDirectory(
                self,
                f"选择{spec.label}文件夹",
                "",
            )
            file_paths = [directory] if directory else []
        elif policy.cardinality == "multiple":
            file_paths, _selected = QFileDialog.getOpenFileNames(
                self,
                f"选择{spec.label}",
                "",
                policy.dialog_filter,
            )
        else:
            file_path, _selected = QFileDialog.getOpenFileName(
                self,
                f"选择{spec.label}",
                "",
                policy.dialog_filter,
            )
            file_paths = [file_path] if file_path else []
        if not file_paths:
            return
        self._apply_attachment_paths(role, file_paths)

    def _apply_attachment_paths(
        self,
        role: str,
        file_paths: tuple[str, ...] | list[str],
    ) -> bool:
        spec = self._attachment_role_spec(role)
        accepted_types = spec.accepted_types if spec is not None else ("image", "pdf")
        cardinality = str(
            getattr(spec, "cardinality", "single") or "single"
        ).strip().casefold()
        source_kind = str(
            getattr(spec, "source_kind", "single_file") or "single_file"
        ).strip().casefold()
        try:
            common = {
                "role": role,
                "accepted_types": accepted_types,
                "required": bool(getattr(spec, "required", False)),
                "min_items": int(getattr(spec, "min_items", 0) or 0),
                "max_items": getattr(spec, "max_items", 1),
                "label": self._attachment_role_display_name(spec),
                "processing_mode": str(
                    getattr(spec, "processing_mode", "passthrough")
                    or "passthrough"
                ),
            }
            if source_kind == "directory_package":
                if len(tuple(file_paths or ())) != 1:
                    raise ValueError("目录附件包必须选择一个根目录")
                binding = build_directory_attachment_binding(
                    source_directory=tuple(file_paths)[0],
                    recursive=bool(getattr(spec, "recursive", False)),
                    **common,
                )
            else:
                binding = build_attachment_binding(
                    source_paths=tuple(file_paths or ()),
                    source_kind=source_kind,
                    cardinality=cardinality,
                    **common,
                )
            requirement_report = scan_attachment_token_requirements(binding)
            has_strict_requirements = any(
                item.kind
                in {
                    AttachmentRequirementKind.FIELD,
                    AttachmentRequirementKind.IMAGE,
                }
                for item in requirement_report.requirements
            )
            if (
                has_strict_requirements
                and spec is not None
                and spec.deletable
                and binding.processing_mode is AttachmentProcessingMode.PASSTHROUGH
            ):
                spec = replace(spec, processing_mode="substitute_copy")
                binding = replace(
                    binding,
                    processing_mode=AttachmentProcessingMode.SUBSTITUTE_COPY,
                )
        except Exception as exc:
            Toast.show_warning(f"附件未通过文件预检：{exc}")
            return False
        if spec is not None and spec.deletable and spec.label == spec.role:
            selected = Path(str(tuple(file_paths)[0]))
            inferred_label = selected.name if source_kind == "directory_package" else selected.stem
            inferred_label = " ".join(inferred_label.split())
            if inferred_label:
                spec = replace(spec, label=inferred_label)
                binding = replace(binding, label=inferred_label)

        snapshot = self._capture_asset_file_mutation_snapshot()
        if snapshot is None:
            return False
        if spec is not None:
            self._attachment_role_specs = tuple(
                spec if item.role == role else item
                for item in self._attachment_role_specs
            )
        self._attachment_bindings[role] = binding
        # A migrated role must never remain visible to legacy image resolution.
        self._asset_paths.pop(role, None)
        self._attachment_legacy_errors.pop(role, None)
        self._store_attachment_role_inventory()
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_asset_file_mutation_selection,
            restore_profile=self._restore_asset_file_mutation_profile,
            restore_local=self._restore_asset_file_mutation_local,
            refresh=lambda: self._refresh_asset_file_mutation_ui(
                snapshot.local_state
            ),
        ):
            return False
        self._refresh_asset_file_mutation_ui()
        if requirement_report.legacy_count:
            Toast.show_warning(
                f"检测到 {requirement_report.legacy_count} 个旧 Token；"
                "已列出迁移建议，源文件不会被自动修改。"
            )
        # Strict Token readiness is rendered by the attachment row summary.
        # A second transient success card would duplicate that state and can
        # remain over the modal workbench after it opens.
        return True

    def _attachment_role_spec(self, role: str) -> AttachmentRoleSpec | None:
        normalized = str(role or "").strip()
        for spec in self._attachment_role_specs:
            if spec.role == normalized or spec.role.casefold() == normalized.casefold():
                return spec
        return None

    def _apply_asset_slot_path(self, role: str, path: str) -> bool:
        if not is_supported_image_path(path):
            Toast.show_warning("所选文件不是受支持的图片，请重新选择。")
            return False
        snapshot = self._capture_asset_file_mutation_snapshot()
        if snapshot is None:
            return False
        self._asset_paths[role] = str(path)
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_asset_file_mutation_selection,
            restore_profile=self._restore_asset_file_mutation_profile,
            restore_local=self._restore_asset_file_mutation_local,
            refresh=lambda: self._refresh_asset_file_mutation_ui(
                snapshot.local_state
            ),
        ):
            return False
        self._refresh_asset_file_mutation_ui()
        self._set_image_preview(str(path), role=role)
        return True

    def _clear_asset_file(self, role: str) -> bool:
        snapshot = self._capture_asset_file_mutation_snapshot()
        if snapshot is None:
            return False
        self._asset_paths.pop(role, None)
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_asset_file_mutation_selection,
            restore_profile=self._restore_asset_file_mutation_profile,
            restore_local=self._restore_asset_file_mutation_local,
            refresh=lambda: self._refresh_asset_file_mutation_ui(
                snapshot.local_state
            ),
        ):
            return False
        self._refresh_asset_file_mutation_ui()
        return True

    def _clear_attachment_file(self, role: str) -> bool:
        snapshot = self._capture_asset_file_mutation_snapshot()
        if snapshot is None:
            return False
        self._attachment_bindings.pop(role, None)
        self._asset_paths.pop(role, None)
        self._attachment_legacy_errors.pop(role, None)
        self._store_attachment_role_inventory()
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_asset_file_mutation_selection,
            restore_profile=self._restore_asset_file_mutation_profile,
            restore_local=self._restore_asset_file_mutation_local,
            refresh=lambda: self._refresh_asset_file_mutation_ui(
                snapshot.local_state
            ),
        ):
            return False
        self._refresh_asset_file_mutation_ui()
        return True

    def _capture_asset_file_mutation_snapshot(self):
        if not self._persist_current_profile_editor():
            return None
        status_label = getattr(self, "_image_assets_status_label", None)
        return capture_material_mutation_snapshot(
            local_state={
                "asset_paths": self._asset_paths,
                "attachment_bindings": self._attachment_bindings,
                "attachment_legacy_errors": self._attachment_legacy_errors,
                "attachment_role_specs": self._attachment_role_specs,
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

    def _restore_asset_file_mutation_selection(self, selection) -> None:
        self.bridge.set_current_material_batch_selection(selection)

    def _restore_asset_file_mutation_profile(self, index: int, profile) -> None:
        self._profiles[index] = profile
        self._update_profile_item(index)

    def _restore_asset_file_mutation_local(self, state) -> None:
        self._asset_paths = state["asset_paths"]
        self._attachment_bindings = state["attachment_bindings"]
        self._attachment_legacy_errors = state["attachment_legacy_errors"]
        self._attachment_role_specs = state["attachment_role_specs"]
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

    def _refresh_asset_file_mutation_ui(self, state=None) -> None:
        self._sync_attachment_role_rows()
        self._refresh_summary()
        if state is not None and state["preview_status_text"] is not None:
            status_label = getattr(self, "_image_assets_status_label", None)
            if status_label is not None:
                status_label.setText(state["preview_status_text"])

    def _refresh_attachment_folder(self, role: str) -> None:
        spec = self._attachment_role_spec(role)
        binding = self._attachment_bindings.get(role)
        source_path = str(getattr(binding, "source_path", "") or "")
        if spec is None or spec.source_kind != "directory_package" or not source_path:
            return
        self._apply_attachment_paths(role, (source_path,))

    def _show_asset_slot_path(self, role: str) -> None:
        path = self._path_for_asset_slot(role)
        self._set_image_preview(path, role=role)
        if path:
            self._open_current_image_preview_dialog()

    def _open_asset_slot_path(self, role: str) -> None:
        path = self._path_for_asset_slot(role)
        if not path:
            status = self._asset_slot_status_labels.get(role)
            if status is not None:
                status.setText(f"请先选择{_asset_role_label(role, self._asset_slot_specs)}。")
            return
        self._open_file_path(str(Path(path).parent))

    def _open_attachment_path(self, role: str) -> None:
        binding = self._attachment_bindings.get(role)
        path = str(getattr(binding, "source_path", "") or "")
        if not path and binding is not None and binding.items:
            path = binding.items[0].file_ref.source_path
        if not path:
            status = self._attachment_role_status_labels.get(role)
            spec = self._attachment_role_spec(role)
            if status is not None:
                status.setText(f"请先选择{spec.label if spec is not None else role}。")
            return
        target = Path(path)
        self._open_file_path(str(target if target.is_dir() else target.parent))

    def _open_file_path(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


__all__ = ["AssetFileOperationsPresenterMixin"]
