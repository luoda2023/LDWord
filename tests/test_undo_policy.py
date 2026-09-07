# -*- coding: utf-8 -*-
"""Regression tests for the central undo-history strategy (undo_policy).

Every baseline event — DOCX export, save-to-.md, chapter switch, close —
must resolve to the same keep/clear action and toast through one module, so the
behaviour can never scatter across individual call sites again.  These tests
lock the policy table and the single low-level apply entry point.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.qt_api import QApplication
from src.config.app_preferences import (
    export_keep_undo_history,
    save_keep_undo_history,
    set_export_keep_undo_history,
    set_save_keep_undo_history,
)
from src.assistant.ui.undo_policy import (
    CLEAR,
    KEEP,
    UndoEvent,
    apply_to_view,
    resolve,
)

_APP = None


def _app() -> QApplication:
    global _APP
    existing = QApplication.instance()
    if existing is not None:
        _APP = existing
        return _APP
    if _APP is None:
        _APP = QApplication([])
    return _APP


class _FakeView:
    """Records the keep/toast handed to the low-level apply entry."""

    def __init__(self):
        self.calls = []

    def apply_undo_baseline(self, keep, toast):
        self.calls.append((bool(keep), str(toast)))


def test_export_follows_export_pref():
    _app()
    set_export_keep_undo_history(True)
    r = resolve(UndoEvent.EXPORT)
    assert r.action == KEEP and r.keep
    assert r.toast_for() == "exported_kept"

    set_export_keep_undo_history(False)
    r = resolve(UndoEvent.EXPORT)
    assert r.action == CLEAR and not r.keep
    assert r.toast_for() == "exported_cleared"
    set_export_keep_undo_history(True)


def test_save_follows_save_pref():
    _app()
    set_save_keep_undo_history(True)
    r = resolve(UndoEvent.SAVE_MARKDOWN)
    assert r.action == KEEP and r.toast_for() == "saved_kept"

    set_save_keep_undo_history(False)
    r = resolve(UndoEvent.SAVE_MARKDOWN)
    assert r.action == CLEAR and r.toast_for() == "saved_cleared"
    set_save_keep_undo_history(True)


def test_chapter_switch_always_clears_and_no_bleed():
    # Structural rule: switching chapter loads a new document, so the previous
    # chapter's undo stack must never bleed in — regardless of export/save prefs.
    _app()
    set_export_keep_undo_history(True)
    set_save_keep_undo_history(True)
    r = resolve(UndoEvent.CHAPTER_SWITCH)
    assert r.action == CLEAR
    assert r.toast_for() == "chapter_reset"


def test_close_is_non_destructive_keep():
    _app()
    r = resolve(UndoEvent.CLOSE)
    assert r.action == KEEP
    assert r.toast_for() == ""  # no "history reset" toast on exit


def test_apply_to_view_delegates_to_low_level_entry():
    view = _FakeView()
    set_export_keep_undo_history(True)
    apply_to_view(view, UndoEvent.EXPORT)
    assert view.calls == [(True, "exported_kept")]

    set_save_keep_undo_history(False)
    apply_to_view(view, UndoEvent.SAVE_MARKDOWN)
    assert view.calls == [(True, "exported_kept"), (False, "saved_cleared")]

    # None view is a safe no-op.
    apply_to_view(None, UndoEvent.EXPORT)
    assert len(view.calls) == 2


def test_all_events_resolve_through_one_module():
    _app()
    for event in UndoEvent:
        r = resolve(event)
        assert r.action in (KEEP, CLEAR)
        assert r.keep == (r.action == KEEP)
        # Every event has a keep/clear toast key (close uses '' for both).
        assert r.keep_toast in {"", "exported_kept", "saved_kept", "chapter_reset"}
        assert r.clear_toast in {
            "",
            "exported_cleared",
            "saved_cleared",
            "chapter_reset",
        }
