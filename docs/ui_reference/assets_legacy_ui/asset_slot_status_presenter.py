"""Presenter mixin for asset and attachment slot status projection."""

from __future__ import annotations

from pathlib import Path

from src.qt_api import QSize
from src.services.material_assets import repeated_question_figure_status
from src.services.material_attachments import (
    build_attachment_preparation_report,
    scan_attachment_token_requirements,
)
from src.shared.engine.material_dependency_projection import (
    project_attachment_binding,
)
from src.ui.panels.assets.image_helpers import _load_scaled_pixmap


class AssetSlotStatusPresenterMixin:
    """Refresh local asset/attachment slot labels, buttons, and thumbnails."""

    def _refresh_asset_slot_statuses(self, asset_items) -> None:
        for spec in self._asset_slot_specs:
            role = spec.role
            path = self._path_for_asset_slot(role, asset_items)
            path_edit = getattr(self, "_asset_slot_path_edits", {}).get(role)
            if path_edit is not None:
                path_edit.setText(str(path or ""))
                path_edit.setAccessibleName(str(path or ""))
            status = self._asset_slot_status_labels.get(role)
            if status is not None:
                diagnostic = repeated_question_figure_status(role, asset_items)
                if self._asset_role_has_source_conflict(role):
                    diagnostic = "图片来源冲突"
                status.setText(diagnostic)
                status.setVisible(bool(diagnostic))
            clear_btn = self._asset_slot_clear_buttons.get(role)
            if clear_btn is not None:
                clear_btn.setEnabled(bool(path))
                clear_btn.setVisible(True)
            open_btn = self._asset_slot_open_buttons.get(role)
            if open_btn is not None:
                open_btn.setEnabled(bool(path))
                open_btn.setVisible(True)
            action_strip = getattr(self, "_asset_slot_action_strips", {}).get(role)
            if action_strip is not None:
                action_strip.sync_visibility()
            self._set_asset_thumbnail(role, path)

    def _refresh_attachment_role_statuses(self, asset_items=None) -> None:
        image_token_bindings = self._attachment_image_token_bindings()
        scope_profiles = self._attachment_preparation_scope_profiles()
        for spec in self._attachment_role_specs:
            binding = self._attachment_bindings.get(spec.role)
            items = tuple(binding.items) if binding is not None else ()
            requirement_report = None
            preparation_report = None
            if binding is not None and items:
                requirement_report = scan_attachment_token_requirements(binding)
                preparation_report = build_attachment_preparation_report(
                    binding,
                    scope_profiles,
                    requirement_report=requirement_report,
                    image_token_bindings=image_token_bindings,
                )
            status = self._attachment_role_status_labels.get(spec.role)
            source_path = str(getattr(binding, "source_path", "") or "")
            if not source_path and items:
                source_path = str(items[0].file_ref.source_path or "")
            path_edit = self._attachment_role_path_edits.get(spec.role)
            if path_edit is not None:
                path_edit.setText(source_path)
                path_edit.setAccessibleName(source_path)
            preview = self._attachment_role_preview_labels.get(spec.role)
            if preview is not None:
                if not items:
                    preview.setText("未选")
                elif spec.source_kind == "single_file":
                    extension = Path(items[0].relative_path).suffix.lstrip(".").upper()
                    preview.setText(extension[:5] or "文件")
                else:
                    preview.setText(f"{len(items)} 项")
            accepted = " / ".join(spec.accepted_types)
            if status is not None:
                status.setToolTip("")
                status.setAccessibleDescription("")
                row = self._attachment_role_rows.get(spec.role)
                if row is not None:
                    row.setToolTip("")
                legacy_error = self._attachment_legacy_errors.get(spec.role, "")
                if legacy_error:
                    status.setText(f"旧附件绑定未通过迁移预检：{legacy_error}")
                elif items:
                    projection = project_attachment_binding(binding)
                    mode_label = (
                        "同步替换副本"
                        if binding.processing_mode.value == "substitute_copy"
                        else "原样交付"
                    )
                    if (
                        requirement_report is not None
                        and requirement_report.legacy_count
                    ):
                        status.setText(
                            f"{mode_label} · 检测到旧 Token "
                            f"{requirement_report.legacy_count} · 需迁移后同步"
                        )
                    elif preparation_report is not None and not preparation_report.profile_count:
                        status.setText(f"{mode_label} · 请先勾选本次生成数据")
                    elif preparation_report is not None and preparation_report.token_count:
                        strict_count = sum(
                            item.kind.value in {"field", "image"}
                            for item in preparation_report.requirements
                        )
                        pending_count = sum(
                            item.kind.value in {"field", "image"} and not item.is_ready
                            for item in preparation_report.requirements
                        )
                        status.setText(
                            f"{mode_label} · DOCX {requirement_report.docx_count} · "
                            f"Token {strict_count} · 待补 {pending_count}"
                        )
                    else:
                        status.setText(
                            f"{mode_label} · DOCX "
                            f"{projection['processable_docx_count']} · "
                            f"原样 {projection['opaque_file_count']}"
                        )
                    if (
                        requirement_report is not None
                        and requirement_report.unreadable_paths
                    ):
                        status.setText(
                            f"{status.text()} · 无法读取 "
                            f"{len(requirement_report.unreadable_paths)}"
                        )
                    status.setAccessibleDescription(
                        f"{mode_label}；{len(items)} 项；"
                        f"发现 {preparation_report.token_count if preparation_report else 0} "
                        f"个 Token 需求；支持 {accepted}"
                    )
                elif spec.required:
                    status.setText(f"未选择，生成前要补齐；支持 {accepted}")
                else:
                    status.setText(f"未选择，可选；支持 {accepted}")
                status.setVisible(True)
            preparation_summary = self._attachment_preparation_summaries.get(
                spec.role
            )
            if preparation_summary is not None:
                preparation_summary.set_report(preparation_report)
            open_btn = self._attachment_role_open_buttons.get(spec.role)
            if open_btn is not None:
                open_btn.setEnabled(bool(items))
            clear_btn = self._attachment_role_clear_buttons.get(spec.role)
            if clear_btn is not None:
                clear_btn.setEnabled(bool(items) or bool(legacy_error))
            refresh_btn = self._attachment_role_refresh_buttons.get(spec.role)
            if refresh_btn is not None:
                refresh_btn.setEnabled(bool(source_path))
            action_strip = self._attachment_role_action_strips.get(spec.role)
            if action_strip is not None:
                action_strip.sync_visibility()

    def _attachment_image_token_bindings(self) -> dict[str, str]:
        bindings: dict[str, str] = {}
        for spec in (
            *tuple(getattr(self, "_asset_slot_specs", ())),
            *tuple(getattr(self, "_asset_group_specs", ())),
        ):
            token = str(getattr(spec, "target", "") or "").strip()
            role = str(getattr(spec, "role", "") or "").strip()
            if token and role:
                bindings[token] = role
        for rule in dict(getattr(self, "_image_material_rules", {}) or {}).values():
            token = str(getattr(rule, "anchor_token", "") or "").strip()
            role = str(getattr(rule, "source_role", "") or "").strip()
            if token and role:
                bindings[token] = role
        return bindings

    def _set_asset_thumbnail(self, role: str, path: str) -> None:
        label = self._asset_slot_thumbnail_labels.get(role)
        if label is None:
            return
        preview_size = label.size()
        if not preview_size.isValid() or preview_size.isEmpty():
            preview_size = QSize(52, 52)
        pixmap = _load_scaled_pixmap(path, preview_size)
        if pixmap is None:
            label.clear()
            label.setText("未选")
            return
        label.setText("")
        label.setPixmap(pixmap)


__all__ = ["AssetSlotStatusPresenterMixin"]
