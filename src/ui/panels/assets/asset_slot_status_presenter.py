"""Presenter mixin for asset and attachment slot status projection."""

from __future__ import annotations

from pathlib import Path

from src.qt_api import QSize
from src.services.material_assets import repeated_question_figure_status
from src.ui.panels.assets.image_helpers import _image_quality_text, _load_scaled_pixmap


class AssetSlotStatusPresenterMixin:
    """Refresh local asset/attachment slot labels, buttons, and thumbnails."""

    def _refresh_asset_slot_statuses(self, asset_items) -> None:
        for spec in self._asset_slot_specs:
            role = spec.role
            target = spec.target
            path = self._path_for_asset_slot(role, asset_items)
            status = self._asset_slot_status_labels.get(role)
            if status is not None:
                repeated_summary = repeated_question_figure_status(role, asset_items)
                if repeated_summary:
                    status.setText(repeated_summary)
                elif path:
                    alt_text = self._current_asset_metadata().get(role, {}).get("alt_text", "")
                    alt_suffix = " · 图片说明已填写" if alt_text else ""
                    status.setText(f"已选择：{Path(path).name} · {_image_quality_text(path, role=role)}{alt_suffix}")
                elif spec.required:
                    status.setText(f"未选择，生成前要补齐；用于：{target}")
                else:
                    status.setText(f"未选择，将用于：{target}")
            view_btn = self._asset_slot_view_buttons.get(role)
            if view_btn is not None:
                view_btn.setEnabled(bool(path))
            open_btn = self._asset_slot_open_buttons.get(role)
            if open_btn is not None:
                open_btn.setEnabled(bool(path))
            clear_btn = self._asset_slot_clear_buttons.get(role)
            if clear_btn is not None:
                clear_btn.setEnabled(bool(self._asset_paths.get(role)))
            self._set_asset_thumbnail(role, path)

    def _refresh_attachment_role_statuses(self) -> None:
        for spec in self._attachment_role_specs:
            path = self._asset_paths.get(spec.role, "")
            status = self._attachment_role_status_labels.get(spec.role)
            accepted = " / ".join(spec.accepted_types)
            if status is not None:
                if path:
                    status.setText(f"已选择：{Path(path).name} · 支持 {accepted}")
                elif spec.required:
                    status.setText(f"未选择，生成前要补齐；支持 {accepted}")
                else:
                    status.setText(f"未选择，可选；支持 {accepted}")
            open_btn = self._attachment_role_open_buttons.get(spec.role)
            if open_btn is not None:
                open_btn.setEnabled(bool(path))
            clear_btn = self._attachment_role_clear_buttons.get(spec.role)
            if clear_btn is not None:
                clear_btn.setEnabled(bool(path))

    def _set_asset_thumbnail(self, role: str, path: str) -> None:
        label = self._asset_slot_thumbnail_labels.get(role)
        if label is None:
            return
        pixmap = _load_scaled_pixmap(path, QSize(56, 56))
        if pixmap is None:
            label.clear()
            label.setText("未选")
            return
        label.setText("")
        label.setPixmap(pixmap)


__all__ = ["AssetSlotStatusPresenterMixin"]
