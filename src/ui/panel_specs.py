"""Static, side-effect-free definitions for first-level application panels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelSpec:
    """One sidebar destination and its presentation metadata."""

    id: str
    title: str
    icon: str
    group: str = "main"


PANEL_SPECS: tuple[PanelSpec, ...] = (
    PanelSpec(id="workbench", title="工作台", icon="layout-dashboard"),
    PanelSpec(id="scene", title="方案配置", icon="mountain-snow"),
    PanelSpec(id="template", title="模板管理", icon="scroll-text"),
    PanelSpec(id="assistant", title="AI 文档助手", icon="sparkles"),
    PanelSpec(id="theme", title="主题编辑器", icon="palette", group="bottom"),
    PanelSpec(id="preferences", title="偏好设置", icon="settings", group="bottom"),
)

OPTIONAL_PANEL_SPECS: tuple[PanelSpec, ...] = (
    PanelSpec(id="assets", title="完整资料包工作台", icon="package"),
)


def application_panel_specs(
    *, include_optional: bool = False
) -> tuple[PanelSpec, ...]:
    """Return core product surfaces plus optional specialist workbenches."""

    if include_optional:
        return PANEL_SPECS + OPTIONAL_PANEL_SPECS
    return PANEL_SPECS


MAIN_SPECS = tuple(spec for spec in PANEL_SPECS if spec.group == "main")
BOTTOM_SPECS = tuple(spec for spec in PANEL_SPECS if spec.group == "bottom")

_PANEL_INDEX_BY_ID = {spec.id: index for index, spec in enumerate(PANEL_SPECS)}


def panel_index(panel_id: str, *, fallback: int = 0) -> int:
    """Return a stable navigation index without importing any panel class."""

    return _PANEL_INDEX_BY_ID.get(str(panel_id or "").strip(), fallback)


__all__ = [
    "BOTTOM_SPECS",
    "MAIN_SPECS",
    "OPTIONAL_PANEL_SPECS",
    "PANEL_SPECS",
    "PanelSpec",
    "application_panel_specs",
    "panel_index",
]
