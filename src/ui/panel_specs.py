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
    PanelSpec(id="assistant", title="共创写作", icon="sparkles", group="ai"),
    PanelSpec(id="workbench", title="排版装配", icon="layout-dashboard"),
    PanelSpec(id="template", title="模板管理", icon="scroll-text"),
    PanelSpec(id="assets", title="资料包", icon="package"),
    PanelSpec(id="scene", title="方案配置", icon="mountain-snow"),
    PanelSpec(id="marktext", title="Markdown 编辑", icon="file-text", group="markdown"),
    PanelSpec(id="engineering_library", title="工程范本库", icon="book-open", group="markdown"),
    PanelSpec(id="theme", title="主题编辑器", icon="palette", group="bottom"),
    PanelSpec(id="preferences", title="偏好设置", icon="settings", group="bottom"),
)

MAIN_SPECS = tuple(spec for spec in PANEL_SPECS if spec.group == "main")
BOTTOM_SPECS = tuple(spec for spec in PANEL_SPECS if spec.group == "bottom")

_PANEL_INDEX_BY_ID = {spec.id: index for index, spec in enumerate(PANEL_SPECS)}


def panel_index(panel_id: str, *, fallback: int = 0) -> int:
    """Return a stable navigation index without importing any panel class."""

    return _PANEL_INDEX_BY_ID.get(str(panel_id or "").strip(), fallback)


__all__ = [
    "BOTTOM_SPECS",
    "MAIN_SPECS",
    "PANEL_SPECS",
    "PanelSpec",
    "panel_index",
]
