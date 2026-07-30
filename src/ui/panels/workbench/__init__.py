"""Package entry point for Workbench components."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["WorkbenchPanel"]

if TYPE_CHECKING:
    from .panel_v2 import WorkbenchPanel


def __getattr__(name: str):
    if name == "WorkbenchPanel":
        from .panel_v2 import WorkbenchPanel

        return WorkbenchPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
