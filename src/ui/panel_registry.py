"""
panel_registry — 面板/导航注册的唯一来源

Sidebar 和 MainWindow 都从 PANEL_SPECS 读取导航配置，
避免双写导致的不同步问题。
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from src.ui.panel_specs import (
    BOTTOM_SPECS as BOTTOM_SPECS,
    MAIN_SPECS as MAIN_SPECS,
    PANEL_SPECS as PANEL_SPECS,
    PanelSpec as PanelSpec,
)


@dataclass(frozen=True)
class PanelFactorySpec:
    """Lazy import target for one first-level destination."""

    module_name: str
    class_name: str
    keyword_args: tuple[tuple[str, object], ...] = ()


PANEL_FACTORIES: dict[str, PanelFactorySpec] = {
    "workbench": PanelFactorySpec(
        "src.ui.panels.workbench",
        "WorkbenchPanel",
    ),
    "scene": PanelFactorySpec(
        "src.ui.panels.scene_panel",
        "ScenePanel",
    ),
    "template": PanelFactorySpec(
        "src.ui.panels.template_panel",
        "TemplatePanel",
    ),
    "assets": PanelFactorySpec(
        "src.ui.panels.assets_panel",
        "AssetsPanel",
    ),
    "assistant": PanelFactorySpec(
        "src.assistant.ui.assistant_panel",
        "AssistantPanel",
        (("first_level", True),),
    ),
    "marktext": PanelFactorySpec(
        "src.ui.panels.marktext_panel",
        "MarkTextPanel",
    ),
    "engineering_library": PanelFactorySpec(
        "src.ui.panels.engineering_library_panel",
        "EngineeringLibraryPanel",
    ),
    "theme": PanelFactorySpec(
        "src.ui.panels.theme_panel",
        "ThemePanel",
    ),
    "preferences": PanelFactorySpec(
        "src.ui.panels.preferences_panel",
        "PreferencesPanel",
    ),
}


def create_panel(
    panel_id: str,
    bridge,
):
    """Construct a registered panel without importing other destinations."""

    normalized = str(panel_id or "").strip()
    try:
        factory = PANEL_FACTORIES[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown panel id: {normalized or panel_id!r}") from exc
    panel_module = import_module(factory.module_name)
    panel_type = getattr(panel_module, factory.class_name)
    return panel_type(bridge, **dict(factory.keyword_args))
