# -*- coding: utf-8 -*-
"""Regression tests for 篇/部分 group rendering in the left workbench dock.

When a document nests coarse grouping headings (篇/部分/卷/单元) above its
content chapters, ``DetectedChapter.part_title`` is now persisted into the
chapter cache outline, and ``ChapterOutlineDock`` renders a collapsible group
header for each part with click-to-fold/expand of its chapter rows — mirroring
the rewrite outline card.

Covers:
* cache persistence: ``part_title`` survives ``begin_run`` / ``update_state`` /
  the ``outline.json`` round-trip, and flat ``begin_run`` stays empty;
* dock grouping: ``set_outline(titles, parts=...)`` builds one header per
  distinct part and groups the right chapters under it;
* collapse hides a part's chapter rows; expand restores them; top-level
  chapters (no group) are always visible;
* ``set_current`` on a chapter inside a collapsed group auto-expands that group
  so the active row stays visible;
* flat outlines (``parts=None``) keep the plain flat list with no headers.

Run with ``QT_QPA_PLATFORM=offscreen`` and needs no ``pytest-qt``: a
session-scoped ``QApplication`` fixture is provided here.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from src.assistant.application.chapter_cache import ChapterCacheStore
from src.assistant.ui.chapter_outline_dock import ChapterOutlineDock


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def dock(qapp):
    d = ChapterOutlineDock()
    d.show()
    yield d
    d.hide()
    d.deleteLater()


@pytest.fixture
def store(qapp, tmp_path):
    return ChapterCacheStore(tmp_path)


def _spin(qapp):
    qapp.processEvents()


PART_OUTLINE_TITLES = ["第一章 项目背景", "第二章 建设目标", "第三章 总体设计", "第四章 实施方案"]
PART_OUTLINE_PARTS = ["第一篇 总论", "第一篇 总论", "第二篇 工程设计", ""]


# ---------------------------------------------------------------------------
# Cache persistence
# ---------------------------------------------------------------------------
def test_cache_begin_run_stores_parts(store):
    sid = "sess_parts"
    store.begin_run(sid, PART_OUTLINE_TITLES, parts=PART_OUTLINE_PARTS)
    entries = store.load_outline(sid)
    assert [e.part_title for e in entries] == PART_OUTLINE_PARTS


def test_cache_update_state_preserves_part(store):
    sid = "sess_parts_upd"
    store.begin_run(sid, PART_OUTLINE_TITLES, parts=PART_OUTLINE_PARTS)
    store.update_state(sid, 2, "done", rescan_score=True)
    store.update_state(sid, 1, chars=500)
    by = {e.index: e for e in store.load_outline(sid)}
    assert by[1].part_title == "第一篇 总论"
    assert by[2].state == "done"
    assert by[2].part_title == "第一篇 总论"
    assert by[3].part_title == "第二篇 工程设计"
    assert by[4].part_title == ""


def test_cache_flat_begin_run_has_no_part(store):
    sid = "sess_flat"
    store.begin_run(sid, ["第一章 概述", "第二章 验收"])
    assert all(e.part_title == "" for e in store.load_outline(sid))


# ---------------------------------------------------------------------------
# Dock part-group rendering
# ---------------------------------------------------------------------------
def test_dock_builds_part_groups(qapp, dock):
    dock.set_outline(PART_OUTLINE_TITLES, parts=PART_OUTLINE_PARTS)
    _spin(qapp)
    assert set(dock._rows) == {1, 2, 3, 4}
    assert set(dock._part_widgets) == {"第一篇 总论", "第二篇 工程设计"}
    assert dock._part_members["第一篇 总论"] == [1, 2]
    assert dock._part_members["第二篇 工程设计"] == [3]
    # Everything expanded by default: no row hidden.
    assert all(not dock._rows[i].isHidden() for i in (1, 2, 3, 4))


def test_dock_collapse_hides_only_that_part_rows(qapp, dock):
    dock.set_outline(PART_OUTLINE_TITLES, parts=PART_OUTLINE_PARTS)
    _spin(qapp)
    part1 = dock._part_widgets["第一篇 总论"]
    part1.set_collapsed(True)
    dock._rebuild_visibility()
    _spin(qapp)
    assert dock._rows[1].isHidden() and dock._rows[2].isHidden()
    assert not dock._rows[3].isHidden()  # other part stays expanded
    assert not dock._rows[4].isHidden()  # top-level chapter always visible
    part1.set_collapsed(False)
    dock._rebuild_visibility()
    _spin(qapp)
    assert not dock._rows[1].isHidden() and not dock._rows[2].isHidden()


def test_dock_set_current_auto_expands_collapsed_part(qapp, dock):
    dock.set_outline(PART_OUTLINE_TITLES, parts=PART_OUTLINE_PARTS)
    _spin(qapp)
    part1 = dock._part_widgets["第一篇 总论"]
    part1.set_collapsed(True)
    dock._rebuild_visibility()
    _spin(qapp)
    assert dock._rows[1].isHidden()
    dock.set_current(1)
    _spin(qapp)
    assert not part1.is_collapsed()
    assert not dock._rows[1].isHidden()


def test_dock_header_toggle_signal_folds_rows(qapp, dock):
    dock.set_outline(PART_OUTLINE_TITLES, parts=PART_OUTLINE_PARTS)
    _spin(qapp)
    part2 = dock._part_widgets["第二篇 工程设计"]
    # simulate the header widget toggling (mouse click path)
    part2.set_collapsed(True)
    dock._rebuild_visibility()
    _spin(qapp)
    assert dock._rows[3].isHidden()


def test_dock_flat_outline_has_no_group_headers(qapp, dock):
    dock.set_outline(["第一章 概述", "第二章 验收"])
    _spin(qapp)
    assert not dock._part_widgets
    assert set(dock._rows) == {1, 2}
    assert not dock._rows[1].isHidden() and not dock._rows[2].isHidden()


def test_dock_summary_totals_include_all_chapters(qapp, dock):
    dock.set_outline(PART_OUTLINE_TITLES, parts=PART_OUTLINE_PARTS)
    _spin(qapp)
    assert dock.outline_summary()["total"] == 4
