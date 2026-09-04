from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = [
    "HeadingNumberingPanel",
    "WorkbenchPanel",
]

if TYPE_CHECKING:
    from .heading_numbering_panel import HeadingNumberingPanel
    from .workbench import WorkbenchPanel


def __getattr__(name: str):
    if name == "HeadingNumberingPanel":
        from .heading_numbering_panel import HeadingNumberingPanel

        return HeadingNumberingPanel
    if name == "WorkbenchPanel":
        from .workbench import WorkbenchPanel

        return WorkbenchPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
