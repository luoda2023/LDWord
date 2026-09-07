# -*- coding: utf-8 -*-
"""Regression tests: live-streamed markdown tables form **row by row**.

``AssistantMessageBodyRenderer.append_live_text`` renders live text as fast
markdown snapshots (never raw ``|`` symbols).  As soon as the header +
delimiter rows have streamed in, Qt parses them into a real ``QTextTable``,
and every finished data row that follows immediately adds a visible table row
— so the user watches the table being typed instead of it popping in only
after the whole chapter finishes.

Each test feeds the renderer line by line (as a streaming worker would) and
asserts the table exists and grows *while still streaming*, before any
``finalize_live_body`` call.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextTable
from PySide6.QtTest import QTest

from src.assistant.ui.message_body_renderer import AssistantMessageBodyRenderer
from src.qt_api import QApplication

_APP = None
_RENDERER = None

# Streamed chapter whose mid-section is a 3-column table with three data rows.
_STREAM_LINES = [
    "# 设备清单表\n",
    "\n",
    "本章列出主要施工机械设备。\n",
    "\n",
    "| 设备名称 | 数量 | 备注 |\n",
    "| --- | --- | --- |\n",
    "| 塔吊 | 2 | 租用 |\n",
    "| 挖掘机 | 5 | 自有 |\n",
    "| 泵车 | 3 | 租用 |\n",
    "\n",
    "以上为本次设备清单。\n",
]


def _app() -> QApplication:
    global _APP
    existing = QApplication.instance()
    if existing is not None:
        _APP = existing
        return _APP
    _APP = QApplication([])
    return _APP


def _renderer() -> AssistantMessageBodyRenderer:
    global _RENDERER
    if _RENDERER is None:
        _RENDERER = AssistantMessageBodyRenderer()
    return _RENDERER


def _table_rows(renderer) -> int:
    """Rows of the first real QTextTable inside the document (0 if none)."""
    doc = renderer.document()
    found = []

    def walk(frame):
        it = frame.begin()
        while not it.atEnd():
            child = it.currentFrame()
            if child is not None:
                if isinstance(child, QTextTable):
                    found.append(child)
                walk(child)
            it += 1

    walk(doc.rootFrame())
    return found[0].rows() if found else 0


def _reset(renderer) -> None:
    renderer.set_live_text("")
    renderer._live = True  # set_live_text already leaves it live


def test_table_grows_row_by_row_while_streaming():
    app = _app()
    renderer = _renderer()
    _reset(renderer)

    row_trace: list[int] = []
    for line in _STREAM_LINES:
        renderer.append_live_text(line)
        # Let the immediate/debounce snapshot render land (like a real event loop).
        QTest.qWait(110)
        row_trace.append(_table_rows(renderer))

    # Table must already exist mid-stream (never wait for finalise).
    assert any(rows >= 1 for rows in row_trace), (
        f"no table appeared during streaming; row trace={row_trace}"
    )
    # Rows may only grow while more data rows stream in (no shrinking).
    assert row_trace == sorted(row_trace), f"table rows shrank: {row_trace}"
    # After the last data row has streamed (still before finalise), the table
    # must already carry header + all three data rows = 4 rows.
    # Index of "| 泵车 | 3 | 租用 |" line in _STREAM_LINES is 8.
    assert row_trace[8] >= 4, f"expected 4 rows after last data row: {row_trace}"


def test_no_raw_pipe_symbols_during_or_after_streaming():
    app = _app()
    renderer = _renderer()
    _reset(renderer)

    for line in _STREAM_LINES:
        renderer.append_live_text(line)
        QTest.qWait(110)
        # Once a real table exists, raw '|' never leaks into the visible text.
        if _table_rows(renderer) >= 1:
            assert "|" not in renderer.toPlainText(), (
                "raw pipe symbols leaked into the rendered body"
            )


def test_no_raw_pipe_leak_while_header_is_still_streaming():
    """Regression: while a table header line streams in (before the ``|---|``
    delimiter row arrives) Qt must not show the raw ``| a | b |`` text.

    Earlier the throttle could re-typeset between the header row and the
    delimiter row; Qt cannot recognise a header without its delimiter, so the
    half-formed table flashed as raw pipes.  The live snapshot now appends a
    synthetic delimiter at render time, so the header already typesets as a
    real table row (and no raw ``|`` ever appears) even mid-header.
    """
    app = _app()
    renderer = _renderer()
    _reset(renderer)

    full = "".join(_STREAM_LINES)
    for index in range(len(full)):
        renderer.append_live_text(full[index])
        # Character-level cadence: many deltas arrive before any re-typeset
        # debounce fires; sample both before and after the timer runs.
        if index % 4 == 0:
            assert "|" not in renderer.toPlainText(), (
                f"raw pipe leaked at char {index}: {renderer.toPlainText()!r}"
            )
        QTest.qWait(24)
    QTest.qWait(120)
    assert "|" not in renderer.toPlainText()


def test_finalise_preserves_complete_table():
    app = _app()
    renderer = _renderer()
    _reset(renderer)

    for line in _STREAM_LINES:
        renderer.append_live_text(line)
        QTest.qWait(60)
    renderer.finalize_live_body()

    assert _table_rows(renderer) == 4, "final table must be 4 rows (header+3 data)"
    assert "|" not in renderer.toPlainText()
