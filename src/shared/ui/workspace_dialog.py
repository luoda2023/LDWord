"""Frameless modal shell for task-oriented editing workbenches."""

from __future__ import annotations

from src.qt_api import QSize
from src.shared.ui.preview_dialog import PreviewShellDialog


class WorkspaceDialog(PreviewShellDialog):
    """Reuse the shared adaptive window chrome without preview semantics.

    Preview and editing workbenches need the same non-native title bar, screen
    fitting, rounded surface, drag behaviour, and theme lifecycle.  This thin
    semantic boundary keeps feature dialogs from copying that window code.
    """

    def __init__(
        self,
        *,
        title: str,
        subtitle: str = "",
        preferred_size: QSize | None = None,
        parent=None,
    ) -> None:
        super().__init__(
            title=title,
            subtitle=subtitle,
            preferred_size=preferred_size,
            parent=parent,
        )
        self.setObjectName("shared_workspace_dialog")
        self.setProperty("workspaceShell", True)
        self.setModal(True)


__all__ = ["WorkspaceDialog"]
