# -*- coding: utf-8 -*-
"""Shared, single-source app preferences backed by QSettings.

These helpers exist so a preference surfaced in more than one place (e.g. the
"keep undo history after export" toggle shown both in the export-confirm dialog
and on the global preferences page) is read and written through the SAME key
and code path — the two entry points can never drift apart.
"""

from __future__ import annotations

_EXPORT_KEEP_UNDO_KEY = "export/keep_undo_history"
_SAVE_KEEP_UNDO_KEY = "save/keep_undo_history"
_MEMORY_LOCATION_KEY = "assistant/system_memory_location"

# Valid values for the system-memory storage location.
MEMORY_LOCATION_INTERNAL = "internal"
MEMORY_LOCATION_PROJECT = "project"


def memory_storage_location(default: str = MEMORY_LOCATION_INTERNAL) -> str:
    """Return where the assistant's durable ``system_memory.json`` should be
    kept.

    ``internal`` (default): alongside the chapter cache under the app-internal
    ``<root>/workbench/<session_id>/`` directory.  ``project``: next to the
    user's current project / source document (``<document folder>/system_memory.json``)
    so it travels with the file; when no real document is bound yet it falls
    back to the internal location.
    """
    raw = _string_pref(_MEMORY_LOCATION_KEY, MEMORY_LOCATION_INTERNAL)
    normalized = str(raw or "").strip().casefold()
    if normalized == MEMORY_LOCATION_PROJECT:
        return MEMORY_LOCATION_PROJECT
    return MEMORY_LOCATION_INTERNAL


def set_memory_storage_location(value: str) -> None:
    """Persist the user's system-memory storage-location preference (shared key)."""
    normalized = str(value or "").strip().casefold()
    if normalized == MEMORY_LOCATION_PROJECT:
        normalized = MEMORY_LOCATION_PROJECT
    else:
        normalized = MEMORY_LOCATION_INTERNAL
    _set_string_pref(_MEMORY_LOCATION_KEY, normalized)


def resolve_memory_project_dir(
    candidate_paths: tuple[str, ...],
    *,
    location: str | None = None,
) -> str | None:
    """Return the folder that should hold ``system_memory.json`` when the user
    keeps memory next to their documents, or ``None`` to use the internal cache.

    ``location`` is the stored storage-location preference (defaults to the
    current value).  When it is ``project``, the first candidate path that is an
    existing supported document file decides the folder: its parent directory.
    The candidates are ordered by relevance (the document being rewritten, the
    workbench source, then the bridge's current document).  Returns ``None`` for
    ``internal`` or when no candidate is a real bound file.
    """
    from pathlib import Path

    if location is None:
        location = memory_storage_location()
    if str(location or "").strip().casefold() != MEMORY_LOCATION_PROJECT:
        return None
    supported = {".docx", ".doc", ".wps", ".md", ".markdown"}
    for raw in candidate_paths or ():
        raw_text = str(raw or "").strip()
        if not raw_text:
            continue
        try:
            path = Path(raw_text).expanduser()
        except OSError:
            continue
        if path.is_file() and path.suffix.casefold() in supported:
            folder = path.resolve().parent
            try:
                return str(folder)
            except OSError:
                continue
    return None


def _string_pref(key: str, default: str) -> str:
    try:
        from src.qt_api import QSettings

        settings = QSettings("LDWord", "LDWord")
        value = settings.value(key, default)
        return str(value) if value is not None else default
    except Exception:  # noqa: BLE001 - never block UI on settings errors
        return default


def _set_string_pref(key: str, value: str) -> None:
    try:
        from src.qt_api import QSettings

        settings = QSettings("LDWord", "LDWord")
        settings.setValue(key, str(value))
        settings.sync()
    except Exception:  # noqa: BLE001 - preference persistence must never crash
        pass


def export_keep_undo_history(default: bool = True) -> bool:
    """Return whether to keep the editor's undo history after a successful
    export (True by default) instead of clearing it for a fresh baseline."""
    return _bool_pref(_EXPORT_KEEP_UNDO_KEY, bool(default))


def set_export_keep_undo_history(keep: bool) -> None:
    """Persist the user's export undo-history preference (shared key)."""
    _set_bool_pref(_EXPORT_KEEP_UNDO_KEY, bool(keep))


def save_keep_undo_history(default: bool = True) -> bool:
    """Return whether to keep the editor's undo history after an explicit
    save-to-file (non-export) action, instead of clearing it for a fresh
    baseline.  True by default (matches the export preference)."""
    return _bool_pref(_SAVE_KEEP_UNDO_KEY, bool(default))


def set_save_keep_undo_history(keep: bool) -> None:
    """Persist the user's save undo-history preference (shared key)."""
    _set_bool_pref(_SAVE_KEEP_UNDO_KEY, bool(keep))


def _bool_pref(key: str, default: bool) -> bool:
    try:
        from src.qt_api import QSettings

        settings = QSettings("LDWord", "LDWord")
        return bool(settings.value(key, bool(default), type=bool))
    except Exception:  # noqa: BLE001 - never block UI on settings errors
        return bool(default)


def _set_bool_pref(key: str, value: bool) -> None:
    try:
        from src.qt_api import QSettings

        settings = QSettings("LDWord", "LDWord")
        settings.setValue(key, bool(value))
        settings.sync()
    except Exception:  # noqa: BLE001 - preference persistence must never crash
        pass
