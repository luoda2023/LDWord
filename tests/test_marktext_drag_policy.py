# -*- coding: utf-8 -*-
"""Qt *event-level* regression tests for the embedded MarkText editor's
drag/drop policy.

These drive the real ``eventFilter`` with genuine Qt drag events (real
``QDragEnterEvent`` / ``QDragMoveEvent`` / ``QDropEvent`` / ``QDragLeaveEvent``
instances, so ``type()``, ``acceptProposedAction()`` and ``ignore()`` are the
framework's own).  PySide6 returns a stub ``QObject`` from a *manually
constructed* drag event's ``mimeData()`` when no native drag is running, so each
subclass overrides ``mimeData()`` to hand the event its prepared ``QMimeData`` —
the same object a real OS drag supplies.

Behaviour under test:
* image drags   -> accepted (cursor allows), green hint shown, no auto-hide.
* non-image     -> rejected (``ignore()``, cursor forbidden), amber hint lists
  the unsupported extensions, and a one-shot timer auto-hides it.
* drop of image(s) -> collected and pushed to the page (images_dropped).
* drop / leave of a rejected drag never leaves the notice lingering.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QPoint, QUrl, Qt
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtTest import QTest
from src.qt_api import QApplication
from src.assistant.ui.marktext_view import EmbeddedMarkTextView, _DROP_REJECT_HINT_MS

_APP = None
_VIEW = None

IMG_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


def _app() -> QApplication:
    global _APP
    existing = QApplication.instance()
    if existing is not None:
        _APP = existing
        return _APP
    if _APP is None:
        _APP = QApplication([])
    return _APP


def _view():
    global _VIEW
    if _VIEW is not None:
        return _VIEW
    try:
        _VIEW = EmbeddedMarkTextView(None)
    except Exception as exc:  # noqa: BLE001 - QWebEngine may be unavailable
        raise RuntimeError(f"QWebEngine unavailable: {exc}") from exc
    _VIEW.show()
    return _VIEW


class _MimeDragEnter(QDragEnterEvent):
    """Real DragEnter whose mimeData returns the prepared QMimeData."""

    def __init__(self, pos, mime):
        super().__init__(pos, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        self._mime = mime

    def mimeData(self):
        return self._mime


class _MimeDragMove(QDragMoveEvent):
    def __init__(self, pos, mime):
        super().__init__(pos, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        self._mime = mime

    def mimeData(self):
        return self._mime


class _MimeDrop(QDropEvent):
    def __init__(self, pos, mime):
        super().__init__(pos, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        self._mime = mime

    def mimeData(self):
        return self._mime


def _url_mime(paths):
    m = QMimeData()
    m.setUrls([QUrl.fromLocalFile(p) for p in paths])
    return m


def _make_files(suffixes):
    created = []
    for suffix in suffixes:
        f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        f.close()
        created.append(f.name)
    return created


def _clean(paths):
    for p in paths:
        try:
            os.unlink(p)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Event-level: image drag branch
# ---------------------------------------------------------------------------


def test_image_drag_enter_is_accepted_and_no_autohide():
    _app()
    view = _view()
    img = os.path.join(tempfile.gettempdir(), "ldword_policy_img.png")
    Path(img).write_bytes(IMG_PNG)
    try:
        ev = _MimeDragEnter(QPoint(5, 5), _url_mime([img]))
        assert ev.type() == QEvent.DragEnter
        view.eventFilter(view._view, ev)
        assert ev.isAccepted() is True, "image drag must be accepted"
        assert view._drop_hint.isVisible() is True
        assert "松开插入图片" in view._drop_hint.text()
        assert view._drop_hint_timer.isActive() is False, "no auto-hide for images"
    finally:
        _clean([img])


def test_image_drag_move_stays_accepted_and_keeps_hint():
    _app()
    view = _view()
    img = os.path.join(tempfile.gettempdir(), "ldword_policy_move.png")
    Path(img).write_bytes(IMG_PNG)
    try:
        enter = _MimeDragEnter(QPoint(2, 2), _url_mime([img]))
        view.eventFilter(view._view, enter)
        move = _MimeDragMove(QPoint(9, 9), _url_mime([img]))
        assert move.type() == QEvent.DragMove
        view.eventFilter(view._view, move)
        assert move.isAccepted() is True
        assert view._drop_hint.isVisible() is True
        assert view._drop_hint_timer.isActive() is False
    finally:
        _clean([img])


def test_image_drop_collects_all_images_and_hides_hint():
    _app()
    view = _view()
    imgs = []
    for i in range(3):
        p = os.path.join(tempfile.gettempdir(), f"ldword_policy_multi{i}.png")
        Path(p).write_bytes(IMG_PNG)
        imgs.append(p)
    dropped = []
    # Observe which image paths the view forwards to the page.
    view.bridge.images_dropped.connect(lambda paths: dropped.extend(paths))
    try:
        drop = _MimeDrop(QPoint(5, 5), _url_mime(imgs))
        assert drop.type() == QEvent.Drop
        view.eventFilter(view._view, drop)
        assert drop.isAccepted() is True
        assert view._drop_hint.isVisible() is False, "hint hidden on drop"
        # url.toLocalFile() normalises separators to '/', so compare on that.
        def norm(p):
            return os.path.normpath(os.path.normcase(str(p))).replace("\\", "/")

        assert sorted(norm(p) for p in dropped) == sorted(norm(p) for p in imgs), (
            "all dropped images are collected"
        )
    finally:
        _clean(imgs)


# ---------------------------------------------------------------------------
# Event-level: non-image drag branch
# ---------------------------------------------------------------------------


def test_non_image_drag_enter_is_rejected_and_autohides():
    _app()
    view = _view()
    txt = _make_files([".txt"])[0]
    try:
        ev = _MimeDragEnter(QPoint(5, 5), _url_mime([txt]))
        view.eventFilter(view._view, ev)
        assert ev.isAccepted() is False, "non-image drag must be rejected"
        assert view._drop_hint.isVisible() is True
        assert view._drop_hint_timer.isActive() is True, "auto-hide timer armed"
        assert "仅支持图片" in view._drop_hint.text()
        QTest.qWait(int(_DROP_REJECT_HINT_MS) + 500)
        assert view._drop_hint.isVisible() is False, "notice auto-hides"
        assert view._drop_hint_timer.isActive() is False
    finally:
        _clean([txt])


def test_non_image_drag_move_rejects_and_rearms_timer():
    _app()
    view = _view()
    txt = _make_files([".pdf"])[0]
    try:
        enter = _MimeDragEnter(QPoint(2, 2), _url_mime([txt]))
        view.eventFilter(view._view, enter)
        # A DragMove for the still-rejected file stays rejected.
        move = _MimeDragMove(QPoint(9, 9), _url_mime([txt]))
        view.eventFilter(view._view, move)
        assert move.isAccepted() is False
        assert view._drop_hint.isVisible() is True
        assert view._drop_hint_timer.isActive() is True
    finally:
        _clean([txt])


def test_rejection_lists_unsupported_extensions_distinct():
    _app()
    view = _view()
    files = _make_files([".pdf", ".pdf", ".txt", ".docx"])
    try:
        ev = _MimeDragEnter(QPoint(5, 5), _url_mime(files))
        view.eventFilter(view._view, ev)
        assert ev.isAccepted() is False
        text = view._drop_hint.text()
        assert ".PDF" in text
        assert ".TXT" in text
        assert ".DOCX" in text
        assert text.count(".PDF") == 1, "duplicate extensions are collapsed"
    finally:
        _clean(files)


def test_non_image_drop_is_ignored_and_hint_hidden():
    _app()
    view = _view()
    files = _make_files([".docx", ".pdf"])
    images_dropped = []
    view.bridge.images_dropped.connect(lambda paths: images_dropped.extend(paths))
    try:
        drop = _MimeDrop(QPoint(5, 5), _url_mime(files))
        view.eventFilter(view._view, drop)
        assert drop.isAccepted() is False, "non-image drop is ignored"
        assert images_dropped == [], "no images were pushed"
        assert view._drop_hint.isVisible() is False, "hint not lingering after drop"
    finally:
        _clean(files)


def test_drag_leave_hides_hint():
    _app()
    view = _view()
    ev = QDragLeaveEvent()
    assert ev.type() == QEvent.DragLeave
    view.eventFilter(view._view, ev)
    assert view._drop_hint.isVisible() is False
