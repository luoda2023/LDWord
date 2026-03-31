"""Package entry point for Workbench components."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["WorkbenchPanel", "WorkbenchPanelV2", "LegacyWorkbenchPanel"]

if TYPE_CHECKING:
    from .panel import WorkbenchPanel as LegacyWorkbenchPanel
    from .panel_v2 import WorkbenchPanelV2


def __getattr__(name: str):
    if name == "WorkbenchPanel":
        from .panel_v2 import WorkbenchPanelV2

        return WorkbenchPanelV2
    if name == "WorkbenchPanelV2":
        from .panel_v2 import WorkbenchPanelV2

        return WorkbenchPanelV2
    if name == "LegacyWorkbenchPanel":
        from .panel import WorkbenchPanel as LegacyWorkbenchPanel

        return LegacyWorkbenchPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
