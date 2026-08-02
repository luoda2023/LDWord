from PySide6.QtCore import QCoreApplication
from shiboken6 import isValid

from src.assistant.storage.models import AssistantSessionSummary
from src.assistant.ui.session_sidebar import AssistantSessionSidebar
from src.qt_api import QApplication, QEvent, QScrollArea, QVBoxLayout, QWidget
from src.shared.ui.compact_row_actions import CompactRowActions
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.detail_geometry import ScrollableDetailGeometrySync
from src.shared.ui.toast import Toast


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_deferred_qt_method_skips_target_deleted_before_next_event_loop():
    app = _app()
    calls: list[str] = []

    class Target(QWidget):
        def record(self, value: str) -> None:
            calls.append(value)

    target = Target()
    defer_qt_method(target, "record", "should-not-run")
    target.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    assert isValid(target) is False
    app.processEvents()
    assert calls == []


def test_deferred_qt_method_coalesces_identical_calls_in_same_event_loop():
    app = _app()
    calls: list[str] = []

    class Target(QWidget):
        def record(self, value: str) -> None:
            calls.append(value)

    target = Target()
    try:
        defer_qt_method(target, "record", "once")
        defer_qt_method(target, "record", "once")
        app.processEvents()
        assert calls == ["once"]
    finally:
        target.close()


def test_session_row_focus_sync_is_safe_when_row_is_removed_before_it_runs(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions(
        (
            AssistantSessionSummary(
                session_id="session-to-remove",
                title="Temporary session",
                updated_at="2026-07-31T00:00:00+00:00",
            ),
        )
    )
    sidebar.show()
    qapp.processEvents()

    row = sidebar.recent_list.session_row("session-to-remove")
    assert row is not None
    row.title_button.setFocus()
    qapp.processEvents()
    row.title_button.clearFocus()
    sidebar.replace_sessions(())
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    assert isValid(row) is False
    qapp.processEvents()
    sidebar.close()


def test_deferred_layout_receivers_can_be_deleted_before_next_event_loop():
    app = _app()
    host = QWidget()
    host_layout = QVBoxLayout(host)
    actions = CompactRowActions(host)
    button = actions.add_action("copy", icon_name="copy", tooltip="复制")
    host_layout.addWidget(actions)

    scroll = QScrollArea(host)
    detail = QWidget(scroll)
    detail_layout = QVBoxLayout(detail)
    scroll.setWidget(detail)
    host_layout.addWidget(scroll)
    geometry_sync = ScrollableDetailGeometrySync(detail, detail_layout, scroll)
    geometry_sync.set_active_widget(detail)

    button.hide()
    geometry_sync.schedule()
    host.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    assert isValid(host) is False
    app.processEvents()


def test_toast_stack_prunes_wrappers_deleted_outside_its_timeout_path():
    first = Toast("first")
    second = Toast("second")
    Toast._toasts = [first]
    first.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    try:
        Toast._toasts.append(second)
        assert second._stack_offset() == 0
        assert Toast._toasts == [second]
    finally:
        Toast._toasts.clear()
        second.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
