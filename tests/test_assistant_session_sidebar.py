from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF
from PySide6.QtGui import QContextMenuEvent, QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest

from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.storage.models import AssistantSessionSummary
from src.assistant.storage.session_store import AssistantSessionStore
from src.assistant.ui.session_sidebar import (
    AssistantSessionSidebar,
    _localized_time,
    _relative_age,
    session_row_presentation,
)
from src.qt_api import Qt


def _summary(
    session_id: str = "session-1",
    *,
    title: str = "在吗",
    pinned: bool = False,
    activity_at: str = "2026-07-30T02:16:00+00:00",
    turn_status: str = "",
    document_job_status: str = "",
    corrupt: bool = False,
    has_draft: bool = False,
    unread: bool = False,
    preview: str = "",
    icon_name: str = "message-circle",
) -> AssistantSessionSummary:
    return AssistantSessionSummary(
        session_id=session_id,
        title=title,
        updated_at=activity_at,
        activity_at=activity_at,
        pinned=pinned,
        turn_status=turn_status,
        document_job_status=document_job_status,
        corrupt=corrupt,
        has_draft=has_draft,
        unread=unread,
        preview=preview,
        icon_name=icon_name,
    )


def test_session_row_exposes_time_and_hover_management_actions(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.resize(sidebar.WIDTH, 520)
    sidebar.replace_sessions((_summary(),), selected_session_id="session-1")
    sidebar.show()
    qapp.processEvents()

    item = sidebar.recent_list.item(0)
    row = sidebar.recent_list.itemWidget(item)
    assert row is not None
    assert item.text() == ""
    assert row.title_button.text() == "在吗"
    assert row.time_label.text()
    assert row.time_label.isVisible()
    assert not row.pin_button.isVisible()
    assert not row.rename_button.isVisible()
    assert not row.delete_button.isVisible()

    QTest.mouseMove(row, QPoint(2, 2))
    qapp.processEvents()

    assert not row.time_label.isVisible()
    assert row.pin_button.isVisible()
    assert row.rename_button.isVisible()
    assert row.delete_button.isVisible()
    assert row.rename_button.toolTip() == "重命名"
    assert row.delete_button.toolTip() == "删除"
    sidebar.close()


def test_inline_rename_and_visible_actions_emit_session_intent(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions((_summary(),), selected_session_id="session-1")
    sidebar.show()
    qapp.processEvents()
    row = sidebar.recent_list.itemWidget(sidebar.recent_list.item(0))
    assert row is not None

    renamed: list[tuple[str, str]] = []
    deleted: list[str] = []
    pinned: list[tuple[str, bool]] = []
    sidebar.session_rename_requested.connect(
        lambda session_id, title: renamed.append((session_id, title))
    )
    sidebar.session_delete_requested.connect(deleted.append)
    sidebar.session_pin_requested.connect(
        lambda session_id, value: pinned.append((session_id, value))
    )

    QTest.mouseMove(row, QPoint(2, 2))
    qapp.processEvents()
    row.rename_button.click()
    assert row.title_edit.isVisible()
    assert not row.title_button.isVisible()

    row.title_edit.setText("新的对话标题")
    QTest.keyClick(row.title_edit, Qt.Key_Return)
    qapp.processEvents()
    assert renamed == [("session-1", "新的对话标题")]
    assert row.title_button.isVisible()

    row.delete_button.click()
    assert deleted == []
    assert row.delete_button.text() == "确认"
    assert row.delete_button.toolTip() == "再次点击确认删除"
    row.delete_button.click()
    row.pin_button.click()
    assert deleted == ["session-1"]
    assert pinned == [("session-1", True)]
    sidebar.close()


def test_relative_age_covers_minute_hour_day_month_and_year():
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)

    assert _relative_age((now - timedelta(seconds=30)).isoformat(), now=now) == "刚刚"
    assert _relative_age((now - timedelta(minutes=44)).isoformat(), now=now) == "44分"
    assert _relative_age((now - timedelta(hours=8)).isoformat(), now=now) == "8时"
    assert _relative_age((now - timedelta(days=12)).isoformat(), now=now) == "12天"
    assert _relative_age((now - timedelta(days=60)).isoformat(), now=now) == "2月"
    assert _relative_age((now - timedelta(days=730)).isoformat(), now=now) == "2年"


def test_metadata_edits_do_not_reset_last_activity_time(tmp_path):
    coordinator = AssistantSessionCoordinator(AssistantSessionStore(tmp_path))
    session = coordinator.create_session(title="原名称")
    original_activity = session.activity_at

    renamed = coordinator.rename(session, "新名称")
    assert renamed.activity_at == original_activity

    pinned = coordinator.set_pinned(renamed, True)
    assert pinned.activity_at == original_activity
    assert pinned.summary().activity_at == original_activity

    drafted = coordinator.stage_draft(pinned, "新的草稿")
    assert drafted.activity_at >= original_activity
    assert drafted.activity_at == drafted.updated_at


def test_session_rows_are_reused_and_filter_only_matches_title(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions(
        (
            _summary("session-1", title="项目方案"),
            _summary("session-2", title="会议纪要"),
        ),
        selected_session_id="session-1",
    )
    sidebar.show()
    qapp.processEvents()
    first_row = sidebar.recent_list.session_row("session-1")
    sidebar.replace_sessions(
        (
            _summary("session-1", title="项目方案修订"),
            _summary("session-2", title="会议纪要"),
        ),
        selected_session_id="session-1",
    )

    assert sidebar.recent_list.session_row("session-1") is first_row
    sidebar.filter_sessions("项目")
    first_item = sidebar.recent_list.item(0)
    second_item = sidebar.recent_list.item(1)
    assert not first_item.isHidden()
    assert second_item.isHidden()
    sidebar.close()


def test_relative_order_change_preserves_row_and_inline_edit(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions(
        (
            _summary("session-1", title="先创建"),
            _summary("session-2", title="后创建"),
        ),
        selected_session_id="session-1",
    )
    sidebar.show()
    qapp.processEvents()
    first_row = sidebar.recent_list.session_row("session-1")
    assert first_row is not None
    first_row.start_rename()
    first_row.title_edit.setText("尚未提交的新名称")

    sidebar.replace_sessions(
        (
            _summary("session-2", title="后创建"),
            _summary("session-1", title="先创建"),
        ),
        selected_session_id="session-2",
    )
    sidebar.select_session("session-1")
    qapp.processEvents()

    assert [
        sidebar.recent_list.item(index).data(Qt.UserRole)
        for index in range(sidebar.recent_list.count())
    ] == ["session-2", "session-1"]
    assert sidebar.recent_list.session_row("session-1") is first_row
    assert sidebar.recent_list.session_row("session-2") is not None
    assert first_row.title_edit.isVisible()
    assert first_row.title_edit.text() == "尚未提交的新名称"
    sidebar.close()


@pytest.mark.parametrize(
    ("summary", "expected_state", "expected_label"),
    [
        (_summary(corrupt=True), "corrupt", "需要恢复"),
        (_summary(turn_status="provider_running"), "running", "运行中"),
        (_summary(turn_status="waiting_user_question"), "waiting", "等待回答"),
        (_summary(turn_status="blocked"), "blocked", "阻塞"),
        (_summary(document_job_status="cancelled"), "cancelled", "取消"),
        (_summary(document_job_status="preflight_failed"), "failed", "失败"),
        (_summary(document_job_status="partial_success"), "partial", "部分完成"),
        (_summary(unread=True), "unread", "新回复"),
        (_summary(turn_status="completed"), "success", "完成"),
        (_summary(has_draft=True), "draft", "草稿"),
        (_summary(), "idle", ""),
    ],
)
def test_session_row_presentation_covers_complete_state_matrix(
    summary,
    expected_state,
    expected_label,
):
    presentation = session_row_presentation(summary)
    assert presentation.state == expected_state
    assert expected_label in presentation.status_label


def test_session_list_keyboard_contract_is_reachable_without_hover(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions((_summary(),), selected_session_id="session-1")
    sidebar.show()
    qapp.processEvents()
    session_list = sidebar.recent_list
    row = session_list.session_row("session-1")
    assert row is not None
    opened: list[str] = []
    deleted: list[str] = []
    pinned: list[tuple[str, bool]] = []
    menus: list[tuple[str, object]] = []
    sidebar.session_selected.connect(opened.append)
    sidebar.session_delete_requested.connect(deleted.append)
    sidebar.session_pin_requested.connect(
        lambda session_id, value: pinned.append((session_id, value))
    )
    sidebar.session_menu_requested.connect(
        lambda session_id, point: menus.append((session_id, point))
    )

    session_list.setFocus()
    QTest.keyClick(session_list, Qt.Key_Return)
    QTest.keyClick(session_list, Qt.Key_F2)
    assert opened == ["session-1"]
    assert row.title_edit.isVisible()
    QTest.keyClick(row.title_edit, Qt.Key_Escape)
    assert not row.title_edit.isVisible()

    session_list.setFocus()
    QTest.keyClick(session_list, Qt.Key_Delete)
    assert deleted == []
    assert row.delete_button.text() == "确认"
    QTest.keyClick(row.delete_button, Qt.Key_Space)
    QTest.keyClick(session_list, Qt.Key_F10, Qt.ShiftModifier)
    assert deleted == ["session-1"]
    assert menus and menus[0][0] == "session-1"
    assert row.pin_button.focusPolicy() == Qt.TabFocus
    assert row.rename_button.focusPolicy() == Qt.TabFocus
    assert row.delete_button.focusPolicy() == Qt.TabFocus
    assert row.session_icon.focusPolicy() == Qt.TabFocus
    row.title_button.setFocus()
    qapp.processEvents()
    assert row.pin_button.isVisible()
    QTest.keyClick(row.title_button, Qt.Key_Tab)
    qapp.processEvents()
    assert row.pin_button.hasFocus()
    QTest.keyClick(row.pin_button, Qt.Key_Space)
    assert pinned == [("session-1", True)]
    sidebar.close()


def test_search_shortcut_filters_and_escape_restores_empty_state(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions(
        (
            _summary("session-1", title="项目方案"),
            _summary("session-2", title="会议纪要"),
        )
    )
    sidebar.show()
    sidebar.setFocus()
    qapp.processEvents()

    QTest.keyClick(sidebar, Qt.Key_F, Qt.ControlModifier)
    qapp.processEvents()
    assert sidebar._search_host.isVisible()
    assert sidebar._search_edit.hasFocus()

    sidebar._search_edit.setText("不存在")
    qapp.processEvents()
    assert sidebar.recent_list.visible_item_count() == 0
    assert sidebar._recent_empty_label.isVisible()
    assert sidebar._recent_empty_label.text() == "没有匹配的对话"

    QTest.keyClick(sidebar._search_edit, Qt.Key_Escape)
    qapp.processEvents()
    assert sidebar._search_host.isHidden()
    assert sidebar._search_edit.text() == ""
    assert sidebar.recent_list.visible_item_count() == 2
    sidebar.close()


def test_corrupt_row_only_exposes_safe_removal_action(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions((_summary(corrupt=True),))
    sidebar.show()
    qapp.processEvents()
    row = sidebar.recent_list.session_row("session-1")
    assert row is not None

    QTest.mouseMove(row, QPoint(2, 2))
    qapp.processEvents()
    assert not row.pin_button.isVisible()
    assert not row.rename_button.isVisible()
    assert row.delete_button.isVisible()
    assert row.delete_button.toolTip() == "从列表移除"
    assert not row.session_icon.isEnabled()
    row.start_rename()
    assert not row.title_edit.isVisible()
    sidebar.close()


def test_delete_confirmation_is_inline_exclusive_and_cancellable(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions(
        (
            _summary("session-1", title="一"),
            _summary("session-2", title="二"),
        ),
        selected_session_id="session-1",
    )
    sidebar.show()
    qapp.processEvents()
    first = sidebar.recent_list.session_row("session-1")
    second = sidebar.recent_list.session_row("session-2")
    assert first is not None
    assert second is not None

    first.request_delete()
    assert first.delete_button.text() == "确认"
    assert first.delete_button.isVisible()
    assert not first.pin_button.isVisible()
    assert not first.rename_button.isVisible()

    second.request_delete()
    assert first.delete_button.text() == ""
    assert second.delete_button.text() == "确认"

    sidebar.cancel_delete_confirmation()
    assert second.delete_button.text() == ""
    sidebar.close()


def test_keyboard_current_item_does_not_draw_a_business_state_outline(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions(
        (
            _summary("pinned-1", pinned=True),
            _summary("recent-1"),
        ),
        selected_session_id="",
    )
    sidebar.show()
    qapp.processEvents()

    sidebar.pinned_list.setCurrentItem(sidebar.pinned_list.item(0))
    sidebar.recent_list.setCurrentItem(sidebar.recent_list.item(0))
    pinned_row = sidebar.pinned_list.session_row("pinned-1")
    recent_row = sidebar.recent_list.session_row("recent-1")
    assert pinned_row is not None
    assert recent_row is not None
    assert "border: none;" in pinned_row.styleSheet()
    assert "border: none;" in recent_row.styleSheet()
    assert "1px solid" not in pinned_row.styleSheet().split(
        "QFrame#assistant_session_row:hover", 1
    )[0]
    assert "1px solid" not in recent_row.styleSheet().split(
        "QFrame#assistant_session_row:hover", 1
    )[0]
    sidebar.close()


def test_confirmed_row_deletion_bypasses_question_dialog(monkeypatch):
    from src.assistant.ui.assistant_panel import AssistantPanel

    deleted: list[str] = []

    class _Coordinator:
        @staticmethod
        def list_sessions():
            return ()

        @staticmethod
        def load_session(session_id: str):
            return SimpleNamespace(
                session_id=session_id,
                title="待删除对话",
                turn_status="completed",
                document_job={},
            )

    panel = SimpleNamespace(
        _coordinator=_Coordinator(),
        _delete_session=lambda session_id: deleted.append(session_id),
    )
    monkeypatch.setattr(
        "src.assistant.ui.assistant_panel.decision",
        lambda *_args, **_kwargs: pytest.fail("不应再弹出删除确认框"),
    )

    AssistantPanel._confirm_delete_session(panel, "session-1")

    assert deleted == ["session-1"]


def test_relative_time_timer_only_runs_while_sidebar_is_visible(qapp):
    sidebar = AssistantSessionSidebar()
    assert not sidebar._relative_time_timer.isActive()
    sidebar.show()
    qapp.processEvents()
    assert sidebar._relative_time_timer.isActive()
    sidebar.hide()
    qapp.processEvents()
    assert not sidebar._relative_time_timer.isActive()
    sidebar.close()


def test_localized_time_converts_iso_value_to_readable_local_text():
    rendered = _localized_time("2026-07-30T02:16:00+00:00")
    assert rendered
    assert "T" not in rendered
    assert "+00:00" not in rendered


def test_real_qt_drop_event_reorders_within_section(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions(
        (
            _summary("session-1", title="一"),
            _summary("session-2", title="二"),
            _summary("session-3", title="三"),
        )
    )
    sidebar.show()
    qapp.processEvents()
    session_list = sidebar.recent_list
    session_list.setCurrentItem(session_list.item(0))
    emitted: list[tuple[tuple[str, ...], bool]] = []
    sidebar.session_order_requested.connect(
        lambda values, pinned: emitted.append((tuple(values), pinned))
    )
    mime = QMimeData()
    mime.setData(
        "application/x-alavette-assistant-session",
        b"session-1\n0",
    )
    target_rect = session_list.visualItemRect(session_list.item(1))
    position = QPointF(target_rect.center().x(), target_rect.bottom())
    enter = QDragEnterEvent(
        position.toPoint(),
        Qt.MoveAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    qapp.sendEvent(session_list.viewport(), enter)
    drop = QDropEvent(
        position,
        Qt.MoveAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    qapp.sendEvent(session_list.viewport(), drop)
    qapp.processEvents()

    assert enter.isAccepted()
    assert drop.isAccepted()
    assert emitted == [(("session-2", "session-1", "session-3"), False)]
    assert [
        session_list.item(index).data(Qt.UserRole)
        for index in range(session_list.count())
    ] == ["session-2", "session-1", "session-3"]
    sidebar.close()


def test_real_qt_drop_event_reports_cross_section_insertion(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions(
        (
            _summary("pinned-1", pinned=True),
            _summary("recent-1"),
        )
    )
    sidebar.show()
    qapp.processEvents()
    target = sidebar.pinned_list
    moved: list[tuple[str, bool, int]] = []
    sidebar.session_move_requested.connect(
        lambda session_id, pinned, index: moved.append(
            (session_id, pinned, index)
        )
    )
    mime = QMimeData()
    mime.setData(
        "application/x-alavette-assistant-session",
        b"recent-1\n0",
    )
    position = QPointF(4, 2)
    enter = QDragEnterEvent(
        position.toPoint(),
        Qt.MoveAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    qapp.sendEvent(target.viewport(), enter)
    drop = QDropEvent(
        position,
        Qt.MoveAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    qapp.sendEvent(target.viewport(), drop)
    qapp.processEvents()

    assert drop.isAccepted()
    assert moved == [("recent-1", True, 0)]
    sidebar.close()


def test_session_icon_button_emits_session_and_global_position(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions((_summary(icon_name="file-text"),))
    sidebar.show()
    qapp.processEvents()
    requested: list[tuple[str, object]] = []
    sidebar.session_icon_requested.connect(
        lambda session_id, point: requested.append((session_id, point))
    )
    row = sidebar.recent_list.session_row("session-1")
    assert row is not None
    row.session_icon.click()
    assert requested and requested[0][0] == "session-1"
    sidebar.close()


def test_real_context_menu_event_reaches_session_menu_intent(qapp):
    sidebar = AssistantSessionSidebar()
    sidebar.replace_sessions((_summary(),))
    sidebar.show()
    qapp.processEvents()
    row = sidebar.recent_list.session_row("session-1")
    requested: list[tuple[str, object]] = []
    sidebar.session_menu_requested.connect(
        lambda session_id, point: requested.append((session_id, point))
    )
    local = QPoint(12, 12)
    event = QContextMenuEvent(
        QContextMenuEvent.Mouse,
        local,
        row.mapToGlobal(local),
    )

    qapp.sendEvent(row, event)

    assert event.isAccepted()
    assert requested and requested[0][0] == "session-1"
    sidebar.close()
