"""
base_panel — 所有面板的基类

定义统一接口，确保所有面板遵循相同的生命周期约定。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.qt_api import QWidget

if TYPE_CHECKING:
    from src.ui.bridge import PanelBridge
    from src.config.scene import SceneWorkspace
    from src.config.template import TemplateConfig


class BasePanel(QWidget):
    """面板基类。

    子类必须实现:
        _setup_ui()         — 构建 UI
        _connect_signals()  — 连接 bridge 信号

    子类可选重写:
        on_scene_changed()    — 方案切换响应
        on_template_changed() — 模板切换响应
    """

    panel_title: str = ""
    panel_icon: str = ""

    def __init__(self, bridge: PanelBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """构建 UI，子类必须实现。"""
        raise NotImplementedError

    def _connect_signals(self) -> None:
        """连接 bridge 信号，子类必须实现。"""
        raise NotImplementedError

    def on_scene_changed(self, scene: SceneWorkspace) -> None:
        """方案切换时的响应，子类按需重写。"""

    def on_template_changed(self, template: TemplateConfig) -> None:
        """模板切换时的响应，子类按需重写。"""
