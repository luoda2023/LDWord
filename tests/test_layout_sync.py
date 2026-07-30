from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from shiboken6 import isValid

from src.qt_api import QApplication, QEvent, QWidget
from src.shared.ui import layout_sync


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_updates_suspended_nested_scope_does_not_resume_outer_scope_early():
    _app()
    widget = QWidget()
    try:
        assert widget.updatesEnabled() is True

        with layout_sync.updates_suspended(widget):
            assert widget.updatesEnabled() is False
            with layout_sync.updates_suspended(widget):
                assert widget.updatesEnabled() is False
            assert widget.updatesEnabled() is False

        assert widget.updatesEnabled() is True
    finally:
        widget.close()


def test_updates_suspended_preserves_preexisting_disabled_state():
    _app()
    widget = QWidget()
    widget.setUpdatesEnabled(False)
    try:
        with layout_sync.updates_suspended(widget, widget, None):
            assert widget.updatesEnabled() is False

        assert widget.updatesEnabled() is False
    finally:
        widget.setUpdatesEnabled(True)
        widget.close()


def test_refresh_layout_chain_later_runs_for_a_live_widget(monkeypatch):
    app = _app()
    widget = QWidget()
    calls: list[tuple[QWidget, int]] = []
    try:
        monkeypatch.setattr(
            layout_sync,
            "refresh_layout_chain",
            lambda target, *, passes: calls.append((target, passes)),
        )

        layout_sync.refresh_layout_chain_later(widget, passes=7)
        app.processEvents()

        assert calls == [(widget, 7)]
    finally:
        widget.close()


def test_refresh_layout_chain_later_skips_deleted_widget(monkeypatch):
    app = _app()
    widget = QWidget()
    calls: list[tuple[QWidget, int]] = []
    monkeypatch.setattr(
        layout_sync,
        "refresh_layout_chain",
        lambda target, *, passes: calls.append((target, passes)),
    )

    layout_sync.refresh_layout_chain_later(widget)
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    assert isValid(widget) is False
    app.processEvents()
    assert calls == []


def test_refresh_layout_chain_later_coalesces_same_root_and_pending_ancestor(
    monkeypatch,
):
    app = _app()
    parent = QWidget()
    child = QWidget(parent)
    calls: list[tuple[QWidget, int]] = []
    monkeypatch.setattr(
        layout_sync,
        "refresh_layout_chain",
        lambda target, *, passes: calls.append((target, passes)),
    )
    try:
        layout_sync.refresh_layout_chain_later(child, passes=2)
        layout_sync.refresh_layout_chain_later(child, passes=7)
        layout_sync.refresh_layout_chain_later(parent, passes=9)
        assert calls == []

        app.processEvents()

        assert calls == [(child, 9)]
    finally:
        parent.close()


def test_refresh_layout_chain_later_keeps_sibling_roots_in_one_flush(monkeypatch):
    app = _app()
    parent = QWidget()
    first = QWidget(parent)
    second = QWidget(parent)
    calls: list[tuple[QWidget, int]] = []
    monkeypatch.setattr(
        layout_sync,
        "refresh_layout_chain",
        lambda target, *, passes: calls.append((target, passes)),
    )
    try:
        layout_sync.refresh_layout_chain_later(first, passes=2)
        layout_sync.refresh_layout_chain_later(second, passes=3)
        app.processEvents()

        assert set(calls) == {(first, 2), (second, 3)}
    finally:
        parent.close()
