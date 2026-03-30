"""
bridge — 面板间通信总线

所有跨面板事件通过此类转发，面板之间绝不直接引用。
"""

from __future__ import annotations

from src.qt_api import QObject, Signal


class PanelBridge(QObject):
    """面板间通信总线。

    用法::

        bridge = PanelBridge()

        # 面板 A 发出
        bridge.module_toggled.emit("page_setup", True)

        # 面板 B 接收
        bridge.module_toggled.connect(self._on_module_toggled)
    """

    # ── 场景/模板事件 ──
    scene_changed = Signal(object)             # SceneWorkspace
    template_changed = Signal(object)           # TemplateConfig

    # ── 模块配置事件 ──
    module_toggled = Signal(str, bool)           # (module_name, enabled)
    config_value_changed = Signal(str, str, object)  # (module, key, value)

    # ── 文档事件 ──
    document_loaded = Signal(str)                # file_path
    format_requested = Signal()
    format_completed = Signal(dict)              # report_data

    # ── 导航事件 ──
    navigate_to_panel = Signal(int)              # panel_index
