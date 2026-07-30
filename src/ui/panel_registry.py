"""
panel_registry — 面板/导航注册的唯一来源

Sidebar 和 MainWindow 都从 PANEL_SPECS 读取导航配置，
避免双写导致的不同步问题。
"""

from __future__ import annotations

from importlib import import_module

from src.ui.panel_specs import (
    BOTTOM_SPECS as BOTTOM_SPECS,
    MAIN_SPECS as MAIN_SPECS,
    OPTIONAL_PANEL_SPECS as OPTIONAL_PANEL_SPECS,
    PANEL_SPECS as PANEL_SPECS,
    PanelSpec as PanelSpec,
)


def create_panel(
    panel_id: str,
    bridge,
    *,
    include_optional_features: bool | None = None,
):
    """Return a real panel instance when that panel has landed."""
    # Kept only for compatibility with older integration callers. Core product
    # capabilities must not disappear when optional specialist panels are off.
    del include_optional_features
    if panel_id == "workbench":
        from src.ui.panels.workbench import WorkbenchPanel

        return WorkbenchPanel(bridge)
    if panel_id == "scene":
        from src.ui.panels.scene_panel import ScenePanel

        return ScenePanel(bridge)
    if panel_id == "template":
        from src.ui.panels.template_panel import TemplatePanel

        return TemplatePanel(bridge)
    if panel_id == "assets":
        panel_module = import_module("src.ui.panels.assets_panel")
        return panel_module.AssetsPanel(bridge)
    if panel_id == "assistant":
        from src.assistant.ui.assistant_panel import AssistantPanel

        # A global first-level destination with its own Design-compatible
        # conversation sidebar. The right context rail stays out of this shell;
        # context is represented once by Form's bridge and task surfaces.
        return AssistantPanel(bridge, first_level=True)
    if panel_id == "theme":
        from src.ui.panels.theme_panel import ThemePanel

        return ThemePanel(bridge)
    if panel_id == "preferences":
        from src.ui.panels.preferences_panel import PreferencesPanel

        return PreferencesPanel(bridge)
    return None
