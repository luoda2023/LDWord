# -*- coding: utf-8 -*-
"""Regression tests for the configurable system-memory storage location.

The durable memory (``system_memory.json``) may be kept in the app-internal
cache (next to the chapter cache, default) or next to the user's current
project / source document.  The choice is a shared, persisted preference read
and written through ``src.config.app_preferences`` so the settings-page control
and the assistant's actual resolution can never drift apart.  These tests lock
that contract down.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from src.config.app_preferences import (
    MEMORY_LOCATION_INTERNAL,
    MEMORY_LOCATION_PROJECT,
    memory_storage_location,
    resolve_memory_project_dir,
    set_memory_storage_location,
)
from src.assistant.application.system_memory import SystemMemoryStore
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


def test_default_location_is_internal():
    _app()
    # Restore to a clean value and confirm the (default-internal) read is stable.
    set_memory_storage_location(MEMORY_LOCATION_INTERNAL)
    assert memory_storage_location() == MEMORY_LOCATION_INTERNAL


def test_location_round_trip():
    _app()
    set_memory_storage_location(MEMORY_LOCATION_PROJECT)
    assert memory_storage_location() == MEMORY_LOCATION_PROJECT
    set_memory_storage_location(MEMORY_LOCATION_INTERNAL)
    assert memory_storage_location() == MEMORY_LOCATION_INTERNAL
    # Unknown values collapse to internal.
    set_memory_storage_location("bogus")
    assert memory_storage_location() == MEMORY_LOCATION_INTERNAL
    set_memory_storage_location(MEMORY_LOCATION_INTERNAL)


def test_resolve_respects_location_preference(tmp_path: Path):
    _app()
    doc = tmp_path / "project" / "report.docx"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_bytes(b"PK")

    set_memory_storage_location(MEMORY_LOCATION_INTERNAL)
    assert resolve_memory_project_dir((str(doc),)) is None

    set_memory_storage_location(MEMORY_LOCATION_PROJECT)
    assert resolve_memory_project_dir((str(doc),)) == str(doc.parent)
    set_memory_storage_location(MEMORY_LOCATION_INTERNAL)


def test_resolve_requires_an_existing_supported_file(tmp_path: Path):
    _app()
    set_memory_storage_location(MEMORY_LOCATION_PROJECT)
    try:
        missing = tmp_path / "does_not_exist.docx"
        assert resolve_memory_project_dir((str(missing),)) is None

        unsupported = tmp_path / "notes.pdf"
        unsupported.write_bytes(b"%PDF")
        assert resolve_memory_project_dir((str(unsupported),)) is None
    finally:
        set_memory_storage_location(MEMORY_LOCATION_INTERNAL)


def test_resolve_takes_first_valid_candidate_in_order(tmp_path: Path):
    _app()
    set_memory_storage_location(MEMORY_LOCATION_PROJECT)
    try:
        first = tmp_path / "a" / "rewrite.docx"
        second = tmp_path / "b" / "workbench.md"
        first.parent.mkdir(parents=True, exist_ok=True)
        second.parent.mkdir(parents=True, exist_ok=True)
        first.write_bytes(b"PK")
        second.write_bytes(b"# t")
        assert resolve_memory_project_dir(
            (str(first), str(second))
        ) == str(first.parent)
    finally:
        set_memory_storage_location(MEMORY_LOCATION_INTERNAL)


def test_store_places_file_at_base_dir_or_internal(tmp_path: Path):
    doc_dir = tmp_path / "bound_project"
    doc_dir.mkdir()

    # Project mode: one durable file directly in the document folder.
    project_store = SystemMemoryStore(base_dir=doc_dir)
    project_store.update_chapter(
        "sess_1",
        index=1,
        title="第一章 概述",
        summary="给出了项目背景。",
    )
    project_path = doc_dir / "system_memory.json"
    assert project_path.is_file()
    assert SystemMemoryStore(base_dir=doc_dir).load("sess_2").chapter_by_index(1) is not None

    # Internal mode (default): under <root>/workbench/<session>.
    internal_store = SystemMemoryStore(root=tmp_path)
    internal_store.set_outline("sess_9", ("第一章 概述",))
    internal_path = tmp_path / "workbench" / "sess_9" / "system_memory.json"
    assert internal_path.is_file()


def test_migrate_to_dir_copies_internal_memory(tmp_path: Path):
    internal = SystemMemoryStore(root=tmp_path)
    internal.set_outline("sess_z", ("第一章 概述",))
    internal.update_chapter("sess_z", index=1, title="第一章 概述", summary="已覆盖背景。")

    doc_dir = tmp_path / "bound_project"
    doc_dir.mkdir()
    assert internal.migrate_to_dir("sess_z", doc_dir) is True
    target = doc_dir / "system_memory.json"
    assert target.is_file()
    assert SystemMemoryStore(base_dir=doc_dir).load("sess_z").chapter_by_index(1).summary == "已覆盖背景。"
    # Re-running on an already doc-bound store is a no-op.
    assert SystemMemoryStore(base_dir=doc_dir).migrate_to_dir("sess_z", doc_dir) is False
