"""Scene-side read-only projection of the canonical material contract."""

from __future__ import annotations

from src.application.materials import (
    default_material_contract_id,
    get_material_contract,
)
from src.qt_api import QLabel, QPushButton, QVBoxLayout
from src.ui.panel_specs import panel_index
from src.ui.panels.scene_detail_base import _SimpleFormDetail


class _ContentDetail(_SimpleFormDetail):
    """Show requirements here; editing remains exclusively in AssetsPanel."""

    def __init__(self, bridge=None, parent=None):
        super().__init__(
            "资料契约",
            "package",
            "方案只声明需要什么资料；资料值、记录和资源统一在资料包页面管理。",
            parent,
        )
        self._bridge = bridge
        self._scene = None
        self._contract_summary = QLabel(self._card)
        self._contract_summary.setWordWrap(True)
        self._card.add_widget(self._contract_summary)
        self._preview_summary = QLabel(self._card)
        self._preview_summary.setWordWrap(True)
        self._card.add_widget(self._preview_summary)
        self._open_materials = QPushButton("打开资料包", self._card)
        self._open_materials.clicked.connect(self._navigate_to_materials)
        self._card.add_widget(self._open_materials)
        if bridge is not None:
            bridge.material_preview_snapshot_changed.connect(
                lambda _value: self._refresh()
            )
            bridge.material_run_selection_changed.connect(
                lambda _value: self._refresh()
            )
            bridge.work_mode_changed.connect(lambda _value: self._refresh())
        self._refresh()

    def set_scene(self, scene) -> None:
        self._scene = scene
        self._refresh()

    def _refresh(self) -> None:
        mode_id = (
            self._bridge.current_work_mode_id()
            if self._bridge is not None
            else str(getattr(self._scene, "mode_id", "") or "custom")
        )
        try:
            contract = get_material_contract(
                default_material_contract_id(mode_id),
                work_mode_id=mode_id,
            )
            required_fields = [item.label for item in contract.fields if item.required]
            required_roles = [
                item.label for item in contract.resource_roles if item.required
            ]
            requirements = [*required_fields, *required_roles]
            self._contract_summary.setText(
                f"契约：{contract.label}（{contract.contract_id}）\n"
                + (
                    "必填：" + "、".join(requirements)
                    if requirements
                    else "当前契约没有强制资料项。"
                )
            )
        except Exception as exc:
            self._contract_summary.setText(f"资料契约不可用：{exc}")
        preview = (
            self._bridge.current_material_preview_snapshot()
            if self._bridge is not None
            else None
        )
        selection = (
            self._bridge.current_material_run_selection()
            if self._bridge is not None
            else None
        )
        if preview is None or selection is None:
            self._preview_summary.setText("本次运行尚未选择资料包。")
        else:
            self._preview_summary.setText(
                f"当前：{preview.package_name} · "
                f"{len(selection.selected_record_ids)} 条记录 · "
                f"必填完成 {preview.filled_required_field_count}/"
                f"{preview.required_field_count}"
            )

    def _navigate_to_materials(self) -> None:
        if self._bridge is not None:
            self._bridge.navigate_to_panel.emit(panel_index("assets"))


__all__ = ["_ContentDetail"]
