"""
panel_registry — 面板/导航注册的唯一来源

Sidebar 和 MainWindow 都从 PANEL_SPECS 读取导航配置，
避免双写导致的不同步问题。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelSpec:
    """面板规格定义。"""
    id: str
    title: str
    icon: str           # Lucide icon name in SIDEBAR_ICONS
    group: str = "main"  # "main" | "bottom"
    transitional: bool = False  # 过渡性入口，终态会替换


PANEL_SPECS: tuple[PanelSpec, ...] = (
    PanelSpec(id="workbench",   title="工作台",   icon="layout-dashboard"),
    PanelSpec(id="scene",       title="场景配置", icon="target"),
    PanelSpec(id="template",    title="模板管理", icon="file-text"),
    PanelSpec(id="pipeline",    title="流水线",   icon="git-branch", transitional=True),
    PanelSpec(id="assets",      title="素材管理", icon="package"),
    PanelSpec(id="theme",       title="主题",     icon="palette",  group="bottom"),
    PanelSpec(id="preferences", title="偏好设置", icon="settings",  group="bottom"),
)

MAIN_SPECS = tuple(s for s in PANEL_SPECS if s.group == "main")
BOTTOM_SPECS = tuple(s for s in PANEL_SPECS if s.group == "bottom")


def create_panel(panel_id: str, bridge):
    """Return a real panel instance when that panel has landed."""
    if panel_id == "workbench":
        from src.ui.panels.workbench.panel_v2 import WorkbenchPanelV2

        return WorkbenchPanelV2(bridge)
    return None
