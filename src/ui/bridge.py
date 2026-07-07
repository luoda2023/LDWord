"""
bridge - panel-to-panel event bus.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config.material_batch import MaterialBatchSelection
from src.config.material_context import MaterialExecutionContext
from src.qt_api import QObject, Signal


@dataclass(frozen=True)
class NavigationIntent:
    """Cross-panel navigation target with optional in-panel context."""

    panel_id: str = ""
    panel_index: int = -1
    card_id: str = ""
    field_id: str = ""
    issue_id: str = ""
    return_panel_id: str = ""
    return_card_id: str = ""
    payload: dict[str, object] = field(default_factory=dict)


def navigation_intent_value(intent, key: str, default=None):
    """Read a field from a NavigationIntent-like object or dict."""
    if isinstance(intent, dict):
        return intent.get(key, default)
    return getattr(intent, key, default)


class PanelBridge(QObject):
    """Shared event bus for cross-panel communication."""

    # Scene / template events
    scene_changed = Signal(object)                  # SceneWorkspace
    template_changed = Signal(object)               # TemplateConfig
    scene_dirty_changed = Signal(bool)
    template_dirty_changed = Signal(bool)
    material_context_changed = Signal(object)       # MaterialExecutionContext
    material_batch_selection_changed = Signal(object)  # MaterialBatchSelection
    material_repair_target_requested = Signal(str, str)  # (target_type, target_key)
    material_profile_repair_target_requested = Signal(str, str, str, str)  # (profile_id, profile_name, target_type, target_key)
    material_profile_repair_candidate_requested = Signal(str, str, object)  # (profile_id, profile_name, candidate)

    # Module configuration events
    module_toggled = Signal(str, bool)              # (module_name, enabled)
    config_value_changed = Signal(str, str, object) # (module, key, value)

    # Document events
    document_loaded = Signal(str)                   # file_path
    format_requested = Signal()
    format_completed = Signal(dict)                 # report_data

    # Navigation events
    navigate_to_panel = Signal(int)                 # panel_index
    navigate_to_intent = Signal(object)             # NavigationIntent | dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene = None
        self._current_scene_id = ""
        self._current_scene_path = ""
        self._current_scene_source = ""
        self._current_template = None
        self._current_template_id = ""
        self._current_template_path = ""
        self._current_template_source = ""
        self._current_document_path = ""
        self._scene_dirty = False
        self._template_dirty = False
        self._suppress_next_scene_dirty_recheck = False
        self._material_context = MaterialExecutionContext()
        self._material_batch_selection = MaterialBatchSelection()
        self._material_repair_target: tuple[str, str] = ("", "")
        self._material_profile_repair_target: tuple[str, str, str, str] = ("", "", "", "")
        self._material_profile_repair_candidate: tuple[str, str, dict[str, object]] = ("", "", {})

    def current_scene(self):
        return self._current_scene

    def current_scene_id(self) -> str:
        return self._current_scene_id

    def current_scene_path(self) -> str:
        return self._current_scene_path

    def current_scene_source(self) -> str:
        return self._current_scene_source

    def set_current_scene(
        self,
        scene,
        *,
        config_id: str = "",
        path: str = "",
        source: str = "",
        emit_signal: bool = True,
    ) -> None:
        self._current_scene = scene
        self._current_scene_id = str(config_id or "").strip()
        self._current_scene_path = str(path or "").strip()
        self._current_scene_source = str(source or "").strip()
        if emit_signal:
            self.scene_changed.emit(scene)

    def is_scene_dirty(self) -> bool:
        return self._scene_dirty

    def set_scene_dirty(self, dirty: bool) -> None:
        dirty = bool(dirty)
        if self._scene_dirty == dirty:
            return
        self._scene_dirty = dirty
        if not dirty:
            self._suppress_next_scene_dirty_recheck = False
        self.scene_dirty_changed.emit(dirty)

    def mark_scene_dirty(self, *, recheck: bool = True) -> None:
        if not recheck and not self._scene_dirty:
            self._suppress_next_scene_dirty_recheck = True
        self.set_scene_dirty(True)

    def clear_scene_dirty(self) -> None:
        self.set_scene_dirty(False)

    def consume_scene_dirty_recheck_suppressed(self) -> bool:
        suppressed = bool(self._suppress_next_scene_dirty_recheck)
        self._suppress_next_scene_dirty_recheck = False
        return suppressed

    def current_template(self):
        return self._current_template

    def current_template_id(self) -> str:
        return self._current_template_id

    def current_template_path(self) -> str:
        return self._current_template_path

    def current_template_source(self) -> str:
        return self._current_template_source

    def current_document_path(self) -> str:
        return self._current_document_path

    def set_current_document_path(self, path: str, *, emit_signal: bool = True) -> None:
        self._current_document_path = str(path or "").strip()
        if emit_signal:
            self.document_loaded.emit(self._current_document_path)

    def set_current_template(
        self,
        template,
        *,
        config_id: str = "",
        path: str = "",
        source: str = "",
        emit_signal: bool = True,
    ) -> None:
        self._current_template = template
        self._current_template_id = str(config_id or "").strip()
        self._current_template_path = str(path or "").strip()
        self._current_template_source = str(source or "").strip()
        if emit_signal:
            self.template_changed.emit(template)

    def is_template_dirty(self) -> bool:
        return self._template_dirty

    def set_template_dirty(self, dirty: bool) -> None:
        dirty = bool(dirty)
        if self._template_dirty == dirty:
            return
        self._template_dirty = dirty
        self.template_dirty_changed.emit(dirty)

    def mark_template_dirty(self) -> None:
        self.set_template_dirty(True)

    def clear_template_dirty(self) -> None:
        self.set_template_dirty(False)

    def current_material_context(self) -> MaterialExecutionContext:
        return self._material_context.clone()

    def set_current_material_context(
        self,
        context: MaterialExecutionContext | None,
        *,
        emit_signal: bool = True,
    ) -> None:
        self._material_context = (
            context.clone()
            if isinstance(context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        if emit_signal:
            self.material_context_changed.emit(self._material_context.clone())

    def current_material_batch_selection(self) -> MaterialBatchSelection:
        return self._material_batch_selection.clone()

    def set_current_material_batch_selection(
        self,
        selection: MaterialBatchSelection | None,
        *,
        emit_signal: bool = True,
    ) -> None:
        self._material_batch_selection = (
            selection.clone()
            if isinstance(selection, MaterialBatchSelection)
            else MaterialBatchSelection()
        )
        if emit_signal:
            self.material_batch_selection_changed.emit(self._material_batch_selection.clone())

    def current_material_repair_target(self) -> tuple[str, str]:
        return self._material_repair_target

    def consume_material_repair_target(self) -> tuple[str, str]:
        target = self._material_repair_target
        self._material_repair_target = ("", "")
        return target

    def current_material_profile_repair_target(self) -> tuple[str, str, str, str]:
        return self._material_profile_repair_target

    def consume_material_profile_repair_target(self) -> tuple[str, str, str, str]:
        target = self._material_profile_repair_target
        self._material_profile_repair_target = ("", "", "", "")
        return target

    def current_material_profile_repair_candidate(self) -> tuple[str, str, dict[str, object]]:
        return (
            self._material_profile_repair_candidate[0],
            self._material_profile_repair_candidate[1],
            dict(self._material_profile_repair_candidate[2]),
        )

    def consume_material_profile_repair_candidate(self) -> tuple[str, str, dict[str, object]]:
        profile_id, profile_name, candidate = self._material_profile_repair_candidate
        self._material_profile_repair_candidate = ("", "", {})
        return (profile_id, profile_name, dict(candidate))

    def request_material_repair_target(
        self,
        target_type: str,
        target_key: str,
        *,
        emit_signal: bool = True,
    ) -> None:
        normalized_type = str(target_type or "").strip()
        normalized_key = str(target_key or "").strip()
        self._material_repair_target = (normalized_type, normalized_key)
        if emit_signal:
            self.material_repair_target_requested.emit(normalized_type, normalized_key)

    def request_material_profile_repair_target(
        self,
        profile_id: str,
        profile_name: str,
        target_type: str,
        target_key: str,
        *,
        emit_signal: bool = True,
    ) -> None:
        normalized_profile_id = str(profile_id or "").strip()
        normalized_profile_name = str(profile_name or "").strip()
        normalized_type = str(target_type or "").strip()
        normalized_key = str(target_key or "").strip()
        self._material_profile_repair_target = (
            normalized_profile_id,
            normalized_profile_name,
            normalized_type,
            normalized_key,
        )
        if emit_signal:
            self.material_profile_repair_target_requested.emit(
                normalized_profile_id,
                normalized_profile_name,
                normalized_type,
                normalized_key,
            )

    def request_material_profile_repair_candidate(
        self,
        profile_id: str,
        profile_name: str,
        candidate: dict[str, object],
        *,
        emit_signal: bool = True,
    ) -> None:
        normalized_profile_id = str(profile_id or "").strip()
        normalized_profile_name = str(profile_name or "").strip()
        normalized_candidate = dict(candidate) if isinstance(candidate, dict) else {}
        self._material_profile_repair_candidate = (
            normalized_profile_id,
            normalized_profile_name,
            normalized_candidate,
        )
        if emit_signal:
            self.material_profile_repair_candidate_requested.emit(
                normalized_profile_id,
                normalized_profile_name,
                dict(normalized_candidate),
            )
