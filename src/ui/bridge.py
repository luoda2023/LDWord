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
        self._template_dirty = False

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
