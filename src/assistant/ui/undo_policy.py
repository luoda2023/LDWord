# -*- coding: utf-8 -*-
"""Single-source undo-history strategy for baseline events.

Every place that resets or snapshots the editor's undo/redo stack — exporting to
DOCX, saving markdown to a file, switching chapters, or closing the window —
used to inline its own ``if keep: preserve else: clear`` logic and its own toast
keys.  That behaviour drifted across the right MarkText editor, the left
workbench and the shell.  This module is the one place that decides, per event,
whether to *keep* (snapshot / still undo back past the event) or *clear* (fresh
baseline), and which toast to surface.

Events that are genuinely user-configurable (export, save) resolve their
keep/clear from the shared QSettings-backed preferences in
:mod:`src.config.app_preferences`.  Events that are structural (chapter switch
loads a new document whose undo stack must not bleed from the previous one) and
the terminal close event keep their fixed defaults here, so the whole strategy
is described in one table instead of scattered ``if`` blocks.
"""

from __future__ import annotations

from enum import Enum

from src.config.app_preferences import (
    export_keep_undo_history,
    save_keep_undo_history,
)

# ---------------------------------------------------------------------------
# Event kinds
# ---------------------------------------------------------------------------


class UndoEvent(str, Enum):
    """A point in the product flow where the undo/redo baseline may change."""

    EXPORT = "export"          # A DOCX was exported successfully.
    SAVE_MARKDOWN = "save"     # The document was saved to a .md file.
    CHAPTER_SWITCH = "chapter_switch"  # The active chapter changed.
    CLOSE = "close"            # The editor window is being closed.


# Actions the strategy can take on the editor's undo/redo stack.
KEEP = "keep"    # Snapshot: still undo back past the event.
CLEAR = "clear"  # Reset to a fresh baseline (cannot undo past the event).


class UndoResolution:
    """The resolved action + toast keys for one baseline event."""

    __slots__ = ("action", "keep_toast", "clear_toast")

    def __init__(self, action: str, *, keep_toast: str, clear_toast: str) -> None:
        self.action = action
        self.keep_toast = keep_toast
        self.clear_toast = clear_toast

    @property
    def keep(self) -> bool:
        return self.action == KEEP

    def toast_for(self) -> str:
        """Return the toast key that matches the resolved action."""
        return self.keep_toast if self.keep else self.clear_toast


# Event -> what the strategy does and the toast to show for each branch.
# ``resolver`` returns True to KEEP (snapshot) or False to CLEAR.
_EVENTS: dict[UndoEvent, dict] = {
    UndoEvent.EXPORT: {
        "resolver": export_keep_undo_history,
        "keep_toast": "exported_kept",
        "clear_toast": "exported_cleared",
    },
    UndoEvent.SAVE_MARKDOWN: {
        "resolver": save_keep_undo_history,
        "keep_toast": "saved_kept",
        "clear_toast": "saved_cleared",
    },
    UndoEvent.CHAPTER_SWITCH: {
        # Loading a chapter replaces the whole document in the editor; the
        # previous chapter's undo stack must not bleed into this one, so a real
        # chapter switch always starts a fresh baseline.
        "resolver": lambda: False,
        "keep_toast": "chapter_reset",
        "clear_toast": "chapter_reset",
    },
    UndoEvent.CLOSE: {
        # Closing discards the widget anyway; snapshot (keep) so we never make
        # a destructive clear, and no "history reset" toast is needed on exit.
        "resolver": lambda: True,
        "keep_toast": "",
        "clear_toast": "",
    },
}


def resolve(event: UndoEvent) -> UndoResolution:
    """Resolve *event* to the configured action + toast keys."""
    spec = _EVENTS[UndoEvent(event)]
    keep = bool(spec["resolver"]())
    action = KEEP if keep else CLEAR
    return UndoResolution(
        action,
        keep_toast=spec["keep_toast"],
        clear_toast=spec["clear_toast"],
    )


def apply_to_view(view, event: UndoEvent) -> UndoResolution:
    """Resolve *event* and apply it to the MarkText ``view``.

    ``view`` must expose ``apply_undo_baseline(keep, toast)`` which snapshots
    (keep) or clears (clear) its undo/redo stack and shows ``toast``.  Returns
    the resolution so callers can branch on what actually happened.
    """
    resolution = resolve(UndoEvent(event))
    if view is None:
        return resolution
    # The low-level view already guards on page readiness and whether the JS
    # functions exist, so calling for a not-yet-ready editor is a safe no-op.
    view.apply_undo_baseline(resolution.keep, resolution.toast_for())
    return resolution


__all__ = [
    "UndoEvent",
    "UndoResolution",
    "KEEP",
    "CLEAR",
    "resolve",
    "apply_to_view",
]
