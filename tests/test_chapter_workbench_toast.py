# -*- coding: utf-8 -*-
"""Qt regression tests for the left workbench toast + chapter-switch trigger.

Covers the ChapterWorkbench behaviours added for cross-pane consistency:

* The transient status toast is hidden by default, is shown by ``show_toast``
  (arming its single-shot timer) and auto-hides when the timer fires.
* A real chapter switch emits ``chapter_navigated`` (which reloads the body
  and clears the undo stack) and shows the "撤销历史已重置" toast.
* Re-selecting the SAME chapter keeps the undo stack: it does NOT emit a new
  navigation/reload signal and does NOT show a new reset toast — mirroring the
  right-hand MarkText editor.

Runs headless via ``QT_QPA_PLATFORM=offscreen`` and needs no ``pytest-qt``:
a session-scoped ``QApplication`` fixture is provided here.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.assistant.ui.chapter_workbench import ChapterWorkbench


@pytest.fixture(scope="session")
def qapp():
    """A single headless QApplication for the whole test session."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def workbench(qapp):
    """A shown ChapterWorkbench with a recorded chapter_navigated probe."""
    bench = ChapterWorkbench()
    bench.show()  # children need a visible parent for isVisible() to be true
    navigated: list[int] = []
    bench.chapter_navigated.connect(navigated.append)
    bench._navigated_probe = navigated  # convenience probe
    yield bench
    bench.hide()
    bench.deleteLater()


# ---------------------------------------------------------------------------
# Toast show / hide
# ---------------------------------------------------------------------------
def test_toast_hidden_by_default(workbench):
    assert workbench._toast is not None
    assert not workbench._toast.isVisible()
    assert not workbench._toast_timer.isActive()


def test_show_toast_displays_and_arms_timer(workbench):
    workbench.show_toast("示例文案", kind="warning")
    assert workbench._toast.isVisible()
    assert workbench._toast_timer.isActive()


def test_show_toast_neutral_kind_still_displays(workbench):
    workbench.show_toast("普通提示", kind="")
    assert workbench._toast.isVisible()
    assert workbench._toast.text() == "普通提示"


def test_toast_auto_hides_after_timer(workbench):
    workbench._toast_timer.setInterval(30)
    workbench.show_toast("一闪而过", kind="success")
    assert workbench._toast.isVisible()
    assert workbench._toast_timer.isActive()
    QTest.qWait(90)
    assert not workbench._toast.isVisible()
    assert not workbench._toast_timer.isActive()


# ---------------------------------------------------------------------------
# Chapter-switch trigger (real switch vs same-chapter re-select)
# ---------------------------------------------------------------------------
def test_real_switch_emits_and_shows_reset_toast(workbench):
    # First hop (from no chapter) merely lands on chapter 1: nothing to reset
    # yet, so no toast — only a navigation signal.
    workbench.navigate_chapter(1)
    assert workbench._navigated_probe == [1]
    assert not workbench._toast.isVisible()

    # A REAL switch 1 -> 2 reloads a different chapter: emits navigation and
    # shows the "撤销历史已重置" toast (the loaded body clears its undo stack).
    workbench.navigate_chapter(2)
    assert workbench.current_index == 2
    assert workbench._navigated_probe == [1, 2]
    assert workbench._toast.isVisible()
    assert workbench._toast_timer.isActive()


def test_same_chapter_reselect_keeps_undo_stack(workbench):
    # Land on chapter 1 first (real switch emits + toasts).
    workbench.navigate_chapter(1)
    assert workbench._navigated_probe == [1]
    # Simulate the earlier toast having faded away.
    workbench._toast_timer.stop()
    workbench._toast.hide()

    # Re-selecting the same chapter must NOT emit a reload signal and must NOT
    # show a new "history reset" toast => the undo stack is preserved.
    workbench.navigate_chapter(1)
    assert workbench._navigated_probe == [1]  # no second navigation signal
    assert workbench.current_index == 1
    assert not workbench._toast.isVisible()  # no new reset toast
    assert not workbench._toast_timer.isActive()


def test_internal_navigate_same_chapter_also_keeps_stack(workbench):
    workbench._on_navigate(2)
    assert workbench._navigated_probe == [2]
    workbench._toast_timer.stop()
    workbench._toast.hide()

    workbench._on_navigate(2)
    assert workbench._navigated_probe == [2]
    assert workbench.current_index == 2
    assert not workbench._toast.isVisible()
    assert not workbench._toast_timer.isActive()
