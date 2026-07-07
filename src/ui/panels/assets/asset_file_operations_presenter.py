"""Presenter mixin for local asset file path operations."""

from __future__ import annotations

from src.qt_api import QDesktopServices, QEvent, QFileDialog, QUrl
from src.ui.panels.assets import AttachmentRoleSpec
from src.ui.panels.assets.fields import _asset_role_label
from src.ui.panels.assets.image_helpers import _first_image_path_from_mime
from src.ui.panels.assets.roles import _attachment_file_filter


class AssetFileOperationsPresenterMixin:
    """Select, drag, clear, reveal, and open local material paths."""

    def _path_for_asset_slot(self, role: str, asset_items=None) -> str:
        manual = self._asset_paths.get(role, "")
        if manual:
            return manual
        items = asset_items if asset_items is not None else self._current_asset_items()
        for item in items:
            if item.role == role and item.path:
                return item.path
        return ""

    def _select_asset_file(self, role: str) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "閫夋嫨鍥剧墖",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff);;All Files (*)",
        )
        if not file_path:
            return
        self._asset_paths[role] = file_path
        self._refresh_summary()
        self._sync_material_batch_selection()

    def _select_attachment_file(self, role: str) -> None:
        spec = self._attachment_role_spec(role)
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            f"閫夋嫨{spec.label if spec is not None else '闄勪欢'}",
            "",
            _attachment_file_filter(spec.accepted_types if spec is not None else ("image", "pdf")),
        )
        if not file_path:
            return
        self._asset_paths[role] = file_path
        self._refresh_summary()
        self._sync_material_batch_selection()

    def _attachment_role_spec(self, role: str) -> AttachmentRoleSpec | None:
        normalized = str(role or "").strip().lower().replace(" ", "_")
        for spec in self._attachment_role_specs:
            if spec.role == normalized:
                return spec
        return None

    def _handle_asset_drag_event(self, role: str, event) -> bool:
        path = _first_image_path_from_mime(event.mimeData()) if hasattr(event, "mimeData") else ""
        if event.type() == QEvent.DragEnter:
            if path:
                event.acceptProposedAction()
                return True
            return False
        if event.type() == QEvent.Drop:
            if not path:
                return False
            self._apply_asset_slot_path(role, path)
            event.acceptProposedAction()
            return True
        return False

    def _apply_asset_slot_path(self, role: str, path: str) -> None:
        self._asset_paths[role] = str(path)
        self._refresh_summary()
        self._sync_material_batch_selection()
        self._set_image_preview(str(path), role=role)

    def _clear_asset_file(self, role: str) -> None:
        self._asset_paths.pop(role, None)
        self._refresh_summary()
        self._sync_material_batch_selection()

    def _clear_attachment_file(self, role: str) -> None:
        self._asset_paths.pop(role, None)
        self._refresh_summary()
        self._sync_material_batch_selection()

    def _show_asset_slot_path(self, role: str) -> None:
        path = self._path_for_asset_slot(role)
        self._set_image_preview(path, role=role)

    def _open_asset_slot_path(self, role: str) -> None:
        path = self._path_for_asset_slot(role)
        if not path:
            status = self._asset_slot_status_labels.get(role)
            if status is not None:
                status.setText(f"请先选择{_asset_role_label(role, self._asset_slot_specs)}。")
            return
        self._open_file_path(path)

    def _open_attachment_path(self, role: str) -> None:
        path = self._asset_paths.get(role, "")
        if not path:
            status = self._attachment_role_status_labels.get(role)
            spec = self._attachment_role_spec(role)
            if status is not None:
                status.setText(f"请先选择{spec.label if spec is not None else role}。")
            return
        self._open_file_path(path)

    def _open_file_path(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


__all__ = ["AssetFileOperationsPresenterMixin"]
