"""Project a live Form bridge into detached, assistant-safe state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Protocol


class WorkspaceStatePort(Protocol):
    def current_work_mode_id(self) -> str: ...
    def current_work_mode(self) -> object: ...
    def current_scene_id(self) -> str: ...
    def current_scene_source_type(self) -> str: ...
    def current_template_id(self) -> str: ...
    def current_template_source_type(self) -> str: ...
    def current_document_path(self) -> str: ...
    def current_material_run_selection(self) -> object: ...
    def current_material_preview_snapshot(self) -> object: ...
    def current_official_document_type_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    mode_id: str
    mode_label: str
    scene_id: str
    scene_source_type: str
    template_id: str
    template_source_type: str
    input_path: str
    input_name: str
    input_exists: bool
    material_summary: dict[str, Any]
    document_type_id: str = ""
    material_refs: tuple[dict[str, object], ...] = ()

    def to_dict(self, *, include_local_path: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode_id": self.mode_id,
            "mode_label": self.mode_label,
            "scene_id": self.scene_id,
            "scene_source_type": self.scene_source_type,
            "template_id": self.template_id,
            "template_source_type": self.template_source_type,
            "input_name": self.input_name,
            "input_exists": self.input_exists,
            "material_summary": dict(self.material_summary),
            "document_type_id": self.document_type_id,
        }
        if include_local_path:
            payload["input_path"] = self.input_path
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkspaceSnapshot":
        """Restore a detached plan snapshot without consulting the live bridge."""

        material_summary = value.get("material_summary")
        return cls(
            mode_id=str(value.get("mode_id") or ""),
            mode_label=str(value.get("mode_label") or ""),
            scene_id=str(value.get("scene_id") or ""),
            scene_source_type=str(value.get("scene_source_type") or ""),
            template_id=str(value.get("template_id") or ""),
            template_source_type=str(value.get("template_source_type") or ""),
            input_path=str(value.get("input_path") or ""),
            input_name=str(value.get("input_name") or ""),
            input_exists=bool(value.get("input_exists", False)),
            material_summary=(
                dict(material_summary)
                if isinstance(material_summary, Mapping)
                else {}
            ),
            document_type_id=str(value.get("document_type_id") or ""),
        )


def snapshot_workspace(port: WorkspaceStatePort) -> WorkspaceSnapshot:
    path_text = str(port.current_document_path() or "").strip()
    path = Path(path_text) if path_text else None
    mode = port.current_work_mode()
    selection = port.current_material_run_selection()
    preview = port.current_material_preview_snapshot()
    document_type_getter = getattr(port, "current_official_document_type_id", None)
    document_type_id = (
        str(document_type_getter() or "").strip()
        if callable(document_type_getter)
        else ""
    )
    summary = {
        "package_id": str(getattr(selection, "package_id", "") or ""),
        "revision": str(getattr(selection, "revision", "") or ""),
        "record_ids": list(getattr(selection, "record_ids", ()) or ()),
        "record_count": int(getattr(preview, "record_count", 0) or 0),
        "field_count": int(getattr(preview, "field_count", 0) or 0),
        "resource_count": int(getattr(preview, "resource_count", 0) or 0),
    }
    return WorkspaceSnapshot(
        mode_id=str(port.current_work_mode_id() or ""),
        mode_label=str(getattr(mode, "label", "") or ""),
        scene_id=str(port.current_scene_id() or ""),
        scene_source_type=str(port.current_scene_source_type() or ""),
        template_id=str(port.current_template_id() or ""),
        template_source_type=str(port.current_template_source_type() or ""),
        input_path=path_text,
        input_name=path.name if path is not None else "",
        input_exists=bool(path is not None and path.is_file()),
        material_summary=summary,
        document_type_id=document_type_id,
    )


__all__ = ["WorkspaceSnapshot", "WorkspaceStatePort", "snapshot_workspace"]
