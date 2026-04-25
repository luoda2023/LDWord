"""
bridge - panel-to-panel event bus.
"""

from __future__ import annotations

from src.qt_api import QObject, Signal


class PanelBridge(QObject):
    """Shared event bus for cross-panel communication."""

    # Scene / template events
    scene_changed = Signal(object)                  # SceneWorkspace
    template_changed = Signal(object)               # TemplateConfig
    scene_dirty_changed = Signal(bool)
    template_dirty_changed = Signal(bool)

    # Module configuration events
    module_toggled = Signal(str, bool)              # (module_name, enabled)
    config_value_changed = Signal(str, str, object) # (module, key, value)

    # Document events
    document_loaded = Signal(str)                   # file_path
    format_requested = Signal()
    format_completed = Signal(dict)                 # report_data

    # Navigation events
    navigate_to_panel = Signal(int)                 # panel_index

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
        self._scene_dirty = False
        self._template_dirty = False

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
        self.scene_dirty_changed.emit(dirty)

    def mark_scene_dirty(self) -> None:
        self.set_scene_dirty(True)

    def clear_scene_dirty(self) -> None:
        self.set_scene_dirty(False)

    def current_template(self):
        return self._current_template

    def current_template_id(self) -> str:
        return self._current_template_id

    def current_template_path(self) -> str:
        return self._current_template_path

    def current_template_source(self) -> str:
        return self._current_template_source

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
