# -*- coding: utf-8 -*-
"""Regression tests for the shared "keep undo history after export" preference.

The preference is surfaced in two entry points — the export-confirm checkbox in
the AI assistant and the "通用偏好" page of the global settings panel. Both must
read and write through the SAME QSettings-backed helper (single source), so the
two controls can never drift apart. These tests lock that contract down.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.config.app_preferences import (
    export_keep_undo_history,
    save_keep_undo_history,
    set_export_keep_undo_history,
    set_save_keep_undo_history,
)
from src.qt_api import QApplication

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


def test_round_trip_persists():
    _app()
    set_export_keep_undo_history(True)
    assert export_keep_undo_history() is True
    set_export_keep_undo_history(False)
    assert export_keep_undo_history() is False
    set_export_keep_undo_history(True)


def test_default_is_keep():
    _app()
    # Restore to a clean value and confirm the (default-true) read is stable.
    set_export_keep_undo_history(True)
    assert export_keep_undo_history() is True


def test_assistant_delegate_uses_shared_key():
    """The export dialog's load/save helpers must delegate to the shared module,
    proving both UI entries write to one source of truth."""
    import src.assistant.ui.assistant_panel as panel

    set_export_keep_undo_history(False)
    assert panel._load_export_undo_keep() is False
    panel._save_export_undo_keep(True)
    assert export_keep_undo_history() is True
    assert panel._load_export_undo_keep() is True


def test_save_pref_round_trip_and_defaults_keep():
    """The non-export save preference is independent of the export one and
    defaults to keep (True), mirroring export."""
    _app()
    set_save_keep_undo_history(True)
    assert save_keep_undo_history() is True
    set_save_keep_undo_history(False)
    assert save_keep_undo_history() is False
    set_save_keep_undo_history(True)


def test_save_and_export_prefs_are_independent():
    _app()
    set_export_keep_undo_history(False)
    set_save_keep_undo_history(True)
    assert export_keep_undo_history() is False
    assert save_keep_undo_history() is True
    set_export_keep_undo_history(True)


def test_save_delegate_uses_shared_key():
    """The save action's keep/clear helper must delegate to the shared module so
    the save decision and the settings-page toggle share one source of truth."""
    import src.assistant.ui.assistant_panel as panel

    set_save_keep_undo_history(False)
    assert panel._load_save_undo_keep() is False
    panel._save_save_undo_keep(True)
    assert save_keep_undo_history() is True
    assert panel._load_save_undo_keep() is True
