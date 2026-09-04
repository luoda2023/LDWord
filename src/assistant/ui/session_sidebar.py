"""Design-compatible assistant session sidebar backed by Form sessions.

This module ports the information architecture and interaction contract of
LDWord session sidebar layout without importing external UI models.
The sidebar only emits user intent; :class:`AssistantPanel` remains the single
owner of session persistence and document execution state.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from src.assistant.storage.models import (
    ASSISTANT_SESSION_ICON_NAMES,
    AssistantSessionSummary,
)
from src.qt_api import (
    QAbstractItemView,
    QApplication,
    QDrag,
    QEvent,
    QFrame,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMimeData,
    QModelIndex,
    QPushButton,
    QShortcut,
    QSize,
    QSizePolicy,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, apply_text_role

_SESSION_ID_ROLE = int(Qt.UserRole)
_SESSION_PINNED_ROLE = int(Qt.UserRole) + 1
_SESSION_CORRUPT_ROLE = int(Qt.UserRole) + 2
_SESSION_TITLE_ROLE = int(Qt.UserRole) + 3
_SESSION_MIME_TYPE = "application/x-ldword-assistant-session"

SESSION_ICON_OPTIONS = (
    ("message-circle", "对话"),
    ("file-text", "文档"),
    ("chart-no-axes-gantt", "分析"),
    ("alert-triangle", "风险"),
    ("circle-check", "完成"),
)
@dataclass(frozen=True, slots=True)
class SessionRowPresentation:
    state: str
    marker: str
    status_label: str
    preview: str

    @property
    def accessible_description(self) -> str:
        parts = [part for part in (self.status_label, self.preview) if part]
        return "；".join(parts) or "普通对话"


def session_row_presentation(
    summary: AssistantSessionSummary,
) -> SessionRowPresentation:
    turn = str(summary.turn_status or "").strip()
    job = str(summary.document_job_status or "").strip()
    preview = str(summary.preview or "").strip()
    if summary.has_draft:
        preview = "有未发送草稿"
    elif not preview and summary.turn_count == 0:
        preview = "开始一段新对话"

    if summary.corrupt:
        return SessionRowPresentation(
            "corrupt",
            "⚠",
            "会话文件需要恢复",
            preview,
        )

    running_turns = {
        "started",
        "context_ready",
        "provider_running",
        "local_processing",
    }
    running_jobs = {
        "resolving_context",
        "provider_running",
        "content_generation_running",
        "preflight_running",
        "execution_queued",
        "execution_running",
    }
    if turn in running_turns or job in running_jobs:
        return SessionRowPresentation("running", "●", "任务运行中", preview)

    waiting_turn_labels = {
        "waiting_user_question": "等待回答",
        "waiting_data_permission": "等待数据授权",
        "waiting_tool_permission": "等待工具授权",
    }
    waiting_job_labels = {
        "response_waiting": "等待继续",
        "needs_route_clarification": "等待补充信息",
        "needs_data_disclosure": "等待数据授权",
        "plan_candidate": "计划待确认",
        "content_generation_ready": "等待生成内容",
        "needs_official_field_completion": "等待补充公文字段",
        "content_draft_ready": "内容草稿待确认",
        "needs_execution_approval": "等待执行批准",
        "plan_ready": "计划待处理",
    }
    waiting_label = waiting_turn_labels.get(turn) or waiting_job_labels.get(job)
    if waiting_label:
        return SessionRowPresentation("waiting", "●", waiting_label, preview)

    if turn == "blocked":
        return SessionRowPresentation("blocked", "!", "任务已阻塞", preview)
    if turn == "cancelled" or job == "cancelled":
        return SessionRowPresentation("cancelled", "!", "任务已取消", preview)
    if turn == "failed" or job in {"failed", "preflight_failed"}:
        return SessionRowPresentation("failed", "!", "任务失败", preview)
    if job == "partial_success":
        return SessionRowPresentation("partial", "!", "任务部分完成", preview)
    if summary.unread:
        return SessionRowPresentation("unread", "●", "有新回复", preview)
    if turn in {"success", "completed"} or job in {
        "success",
        "response_ready",
        "response_closed",
    }:
        return SessionRowPresentation("success", "✓", "任务已完成", preview)
    if summary.has_draft:
        return SessionRowPresentation("draft", "✎", "有未发送草稿", preview)
    return SessionRowPresentation("idle", "·", "", preview)


class _RenameLineEdit(QLineEdit):
    cancel_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.cancel_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _SessionTitleButton(QPushButton):
    rename_requested = Signal()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.rename_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _SessionRow(QFrame):
    """One discoverable session row with hover actions and inline rename."""

    selected = Signal(str)
    menu_requested = Signal(str, object)
    pin_requested = Signal(str, bool)
    rename_requested = Signal(str, str)
    delete_confirmation_requested = Signal(str)
    delete_requested = Signal(str)
    icon_requested = Signal(str, object)
    drag_requested = Signal(str)

    HEIGHT = 34

    def __init__(
        self,
        summary: AssistantSessionSummary,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("assistant_session_row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(self.HEIGHT)
        self._summary = summary
        self._display_title = ""
        self._hovered = False
        self._selected = False
        self._keyboard_focus = False
        self._editing_title = False
        self._delete_armed = False
        self._drag_start = None
        self._presentation = session_row_presentation(summary)

        root = QHBoxLayout(self)
        root.setContentsMargins(5, 0, 4, 0)
        root.setSpacing(3)
        self._layout = root

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("assistant_session_status")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedWidth(10)
        self.status_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        root.addWidget(self.status_label)

        self.session_icon = QPushButton("", self)
        self.session_icon.setObjectName("assistant_session_icon")
        self.session_icon.setFixedSize(20, 24)
        self.session_icon.setFocusPolicy(Qt.TabFocus)
        self.session_icon.clicked.connect(
            lambda: self.icon_requested.emit(
                self._summary.session_id,
                self.session_icon.mapToGlobal(
                    self.session_icon.rect().bottomLeft()
                ),
            )
        )
        root.addWidget(self.session_icon)

        self.title_button = _SessionTitleButton("", self)
        self.title_button.setObjectName("assistant_session_title")
        self.title_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.title_button.setFixedHeight(self.HEIGHT)
        self.title_button.clicked.connect(
            lambda: self.selected.emit(self._summary.session_id)
        )
        self.title_button.rename_requested.connect(self.start_rename)
        root.addWidget(self.title_button, 1)

        self.title_edit = _RenameLineEdit(self)
        self.title_edit.setObjectName("assistant_session_title_edit")
        apply_text_role(self.title_edit, TextRole.CAPTION)
        self.title_edit.setFixedHeight(26)
        self.title_edit.setMaxLength(80)
        self.title_edit.setVisible(False)
        self.title_edit.returnPressed.connect(self._commit_rename)
        self.title_edit.editingFinished.connect(self._commit_rename)
        self.title_edit.cancel_requested.connect(self.cancel_rename)
        root.addWidget(self.title_edit, 1)

        self.time_label = QLabel("", self)
        self.time_label.setObjectName("assistant_session_time")
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_label.setFixedWidth(40)
        self.time_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        root.addWidget(self.time_label)

        self.pin_button = self._action_button("pin", "置顶")
        self.pin_button.clicked.connect(
            lambda: self.pin_requested.emit(
                self._summary.session_id,
                not self._summary.pinned,
            )
        )
        root.addWidget(self.pin_button)

        self.rename_button = self._action_button("pencil-line", "重命名")
        self.rename_button.clicked.connect(self.start_rename)
        root.addWidget(self.rename_button)

        self.delete_button = self._action_button("trash-2", "删除")
        self.delete_button.clicked.connect(self.request_delete)
        root.addWidget(self.delete_button)
        self._action_buttons = (
            self.pin_button,
            self.rename_button,
            self.delete_button,
        )
        for control in (
            self.session_icon,
            self.title_button,
            self.title_edit,
            *self._action_buttons,
        ):
            control.installEventFilter(self)
        self.update_summary(summary)

    def _action_button(self, icon_name: str, tooltip: str) -> QPushButton:
        button = QPushButton("", self)
        button.setObjectName("assistant_session_action")
        button.setProperty("iconName", icon_name)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(18, 24)
        button.setFocusPolicy(Qt.TabFocus)
        button.setVisible(False)
        return button

    def update_summary(self, summary: AssistantSessionSummary) -> None:
        self._summary = summary
        self._presentation = session_row_presentation(summary)
        self._display_title = str(summary.title or "新对话")
        activity_at = summary.activity_at or summary.updated_at
        self.status_label.setText(self._presentation.marker)
        status_label = self._presentation.status_label or "对话"
        self.status_label.setToolTip(status_label)
        self.status_label.setAccessibleName(status_label)
        icon_label = "待恢复会话" if summary.corrupt else "更换会话图标"
        self.session_icon.setToolTip(icon_label)
        self.session_icon.setAccessibleName(icon_label)
        self.session_icon.setEnabled(not summary.corrupt)
        self.title_button.setAccessibleName(self._display_title)
        tooltip_lines = [self._display_title]
        if self._presentation.status_label:
            tooltip_lines.append(self._presentation.status_label)
        if self._presentation.preview:
            tooltip_lines.append(self._presentation.preview)
        absolute_activity = _localized_time(activity_at)
        tooltip_lines.append(
            f"最近活动：{absolute_activity or '未知'}"
        )
        self.title_button.setToolTip(
            f"{self._display_title}\n原文件已保留：{summary.recovery_path}\n"
            "点击查看恢复说明。"
            if summary.corrupt
            else "\n".join(tooltip_lines)
        )
        if not self._editing_title:
            self.title_edit.setText(self._display_title)
        pin_label = "取消置顶" if summary.pinned else "置顶"
        self.pin_button.setProperty(
            "iconName",
            "pin-off" if summary.pinned else "pin",
        )
        self.pin_button.setToolTip(pin_label)
        self.pin_button.setAccessibleName(pin_label)
        delete_label = "从列表移除" if summary.corrupt else "删除"
        if self._delete_armed:
            delete_label = (
                "再次点击确认移除"
                if summary.corrupt
                else "再次点击确认删除"
            )
        self.delete_button.setToolTip(delete_label)
        self.delete_button.setAccessibleName(delete_label)
        self.refresh_relative_time()
        self._sync_visibility()
        self._sync_elided_title()
        self._apply_theme()

    def set_selected(self, selected: bool) -> None:
        next_selected = bool(selected)
        if self._selected == next_selected:
            return
        self._selected = next_selected
        self._apply_theme()

    def refresh_relative_time(self) -> None:
        value = self._summary.activity_at or self._summary.updated_at
        self.time_label.setText(_relative_age(value))
        accessible_parts = [
            self._presentation.accessible_description,
            (
                "有新回复"
                if self._summary.unread
                and self._presentation.state != "unread"
                else ""
            ),
            "已置顶" if self._summary.pinned else "",
            (
                f"最近活动{self.time_label.text()}"
                if self.time_label.text()
                else ""
            ),
        ]
        self.title_button.setAccessibleDescription(
            "；".join(part for part in accessible_parts if part)
        )

    def start_rename(self) -> None:
        if self._summary.corrupt:
            return
        self.set_delete_armed(False)
        self._editing_title = True
        self.title_edit.setText(self._display_title)
        self._sync_visibility()
        self.title_edit.setFocus(Qt.ShortcutFocusReason)
        self.title_edit.selectAll()

    def request_delete(self) -> None:
        """Arm deletion in-place, then emit only after a second activation."""
        if self._delete_armed:
            self.set_delete_armed(False)
            self.delete_requested.emit(self._summary.session_id)
            return
        self.delete_confirmation_requested.emit(self._summary.session_id)

    def set_delete_armed(self, armed: bool) -> None:
        next_armed = bool(armed)
        if self._delete_armed == next_armed:
            return
        self._delete_armed = next_armed
        delete_label = "移除" if self._summary.corrupt else "删除"
        if next_armed:
            self.delete_button.setText("确认")
            self.delete_button.setIcon(get_icon(""))
            self.delete_button.setFixedWidth(42)
            self.delete_button.setToolTip(f"再次点击确认{delete_label}")
            self.delete_button.setAccessibleName(f"确认{delete_label}")
        else:
            self.delete_button.setText("")
            self.delete_button.setFixedWidth(18)
            self.delete_button.setToolTip(
                "从列表移除" if self._summary.corrupt else "删除"
            )
            self.delete_button.setAccessibleName(self.delete_button.toolTip())
        self._sync_visibility()
        self._apply_theme()

    def cancel_rename(self) -> None:
        if not self._editing_title:
            return
        self._editing_title = False
        self.title_edit.setText(self._display_title)
        self._sync_visibility()
        self._sync_elided_title()

    def _commit_rename(self) -> None:
        if not self._editing_title:
            return
        normalized = self.title_edit.text().strip()
        self._editing_title = False
        self._sync_visibility()
        self._sync_elided_title()
        if normalized and normalized != self._display_title:
            self.rename_requested.emit(self._summary.session_id, normalized)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._editing_title:
            self.selected.emit(self._summary.session_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def eventFilter(self, watched, event) -> bool:
        controls = (
            self.session_icon,
            self.title_button,
            self.title_edit,
            *self._action_buttons,
        )
        if watched in controls and event.type() == QEvent.FocusIn:
            self._keyboard_focus = True
            self._sync_visibility()
        elif watched in controls and event.type() == QEvent.FocusOut:
            defer_qt_method(self, "_sync_keyboard_focus")
        if (
            watched is self.delete_button
            and self._delete_armed
            and event.type() == QEvent.KeyPress
            and event.key() == Qt.Key_Escape
        ):
            self.set_delete_armed(False)
            return True
        if watched is self.title_button:
            if (
                event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton
            ):
                self._drag_start = event.position().toPoint()
            elif (
                event.type() == QEvent.MouseMove
                and self._drag_start is not None
                and event.buttons() & Qt.LeftButton
                and (
                    event.position().toPoint() - self._drag_start
                ).manhattanLength()
                >= 6
            ):
                self._drag_start = None
                self.drag_requested.emit(self._summary.session_id)
                return True
            elif event.type() == QEvent.MouseButtonRelease:
                self._drag_start = None
        return super().eventFilter(watched, event)

    def _sync_keyboard_focus(self) -> None:
        focused = QApplication.focusWidget()
        self._keyboard_focus = bool(
            focused is not None
            and (focused is self or self.isAncestorOf(focused))
        )
        self._sync_visibility()

    def contextMenuEvent(self, event) -> None:
        self.menu_requested.emit(self._summary.session_id, event.globalPos())
        event.accept()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._sync_visibility()
        self._sync_elided_title()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._sync_visibility()
        self._sync_elided_title()
        super().leaveEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_elided_title()

    def _sync_visibility(self) -> None:
        self.title_button.setVisible(not self._editing_title)
        self.title_edit.setVisible(self._editing_title)
        show_actions = (
            self._hovered or self._keyboard_focus or self._delete_armed
        ) and not self._editing_title
        self.time_label.setVisible(not show_actions and not self._editing_title)
        self.pin_button.setVisible(
            show_actions and not self._summary.corrupt and not self._delete_armed
        )
        self.rename_button.setVisible(
            show_actions and not self._summary.corrupt and not self._delete_armed
        )
        self.delete_button.setVisible(show_actions)
        self._layout.activate()

    def _sync_elided_title(self) -> None:
        self.title_button.setText(
            self.title_button.fontMetrics().elidedText(
                self._display_title,
                Qt.ElideRight,
                max(28, self.title_button.width() - 3),
            )
        )

    def _apply_theme(self) -> None:
        theme = get_theme()
        status_color = {
            "corrupt": theme.error,
            "running": theme.primary,
            "waiting": theme.warning,
            "blocked": theme.warning,
            "failed": theme.error,
            "cancelled": theme.text_hint,
            "partial": theme.warning,
            "unread": theme.primary,
            "success": theme.success,
            "draft": theme.text_secondary,
            "idle": theme.text_hint,
        }.get(self._presentation.state, theme.text_hint)
        background = theme.bg_selected if self._selected else "transparent"
        icon_name = (
            self._summary.icon_name
            if self._summary.icon_name in ASSISTANT_SESSION_ICON_NAMES
            else "message-circle"
        )
        self.session_icon.setIcon(
            get_icon(
                "alert-triangle" if self._summary.corrupt else icon_name,
                15,
                theme.error if self._summary.corrupt else theme.text_secondary,
            )
        )
        self.session_icon.setIconSize(QSize(15, 15))
        self.delete_button.setProperty("deleteArmed", self._delete_armed)
        self.setStyleSheet(
            f"""
            QFrame#assistant_session_row {{
                background: {background};
                border: none;
                border-radius: {theme.radius_sm}px;
            }}
            QFrame#assistant_session_row:hover {{
                background: {theme.bg_hover if not self._selected else theme.bg_selected};
            }}
            QLabel#assistant_session_status {{
                background: transparent;
                color: {status_color};
                border: none;
                font-size: {theme.font_size_xs}px;
            }}
            QLabel#assistant_session_time {{
                background: transparent;
                color: {theme.text_hint};
                border: none;
                font-size: {theme.font_size_xs}px;
            }}
            QPushButton#assistant_session_icon {{
                background: transparent;
                border: none;
                border-radius: {theme.radius_sm}px;
                padding: 0;
            }}
            QPushButton#assistant_session_icon:hover,
            QPushButton#assistant_session_icon:focus {{
                background: {theme.bg_card};
            }}
            QPushButton#assistant_session_title {{
                background: transparent;
                color: {theme.text_primary};
                border: none;
                padding: 0;
                text-align: left;
                font-size: {theme.font_size_sm}px;
            }}
            QPushButton#assistant_session_action {{
                background: transparent;
                color: {theme.text_secondary};
                border: none;
                border-radius: {theme.radius_sm}px;
                padding: 0;
            }}
            QPushButton#assistant_session_action:hover {{
                background: {theme.bg_card};
            }}
            QPushButton#assistant_session_action[deleteArmed="true"] {{
                color: {theme.error};
                background: {theme.error_bg};
                font-size: {theme.font_size_xs}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QPushButton#assistant_session_action[deleteArmed="true"]:hover {{
                background: {theme.error_bg};
            }}
            QLineEdit#assistant_session_title_edit {{
                background: {theme.bg_input};
                color: {theme.text_primary};
                border: 1px solid {theme.primary};
                border-radius: {theme.radius_sm}px;
                padding: 0 4px;
            }}
            """
        )
        for button in self._action_buttons:
            icon_name = str(button.property("iconName") or "pin")
            color = theme.error if icon_name == "trash-2" else theme.text_hint
            button.setIcon(
                get_icon(icon_name, 13, color)
                if button is not self.delete_button or not self._delete_armed
                else get_icon("")
            )


class _SessionList(QListWidget):
    """One Design task section with cross-section pin/unpin drops."""

    session_open_requested = Signal(str)
    session_menu_requested = Signal(str, object)
    session_pin_requested = Signal(str, bool)
    session_rename_requested = Signal(str, str)
    session_delete_confirmation_requested = Signal(str)
    session_delete_requested = Signal(str)
    session_icon_requested = Signal(str, object)
    session_order_requested = Signal(object, bool)
    session_move_requested = Signal(str, bool, int)

    def __init__(self, *, pinned_target: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pinned_target = bool(pinned_target)
        self.setObjectName(
            "assistant_pinned_session_list"
            if pinned_target
            else "assistant_recent_session_list"
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.itemClicked.connect(self._open_item)
        self.customContextMenuRequested.connect(self._request_menu)
        self._rows: dict[str, _SessionRow] = {}

    def _open_item(self, item: QListWidgetItem) -> None:
        session_id = str(item.data(_SESSION_ID_ROLE) or "")
        if session_id:
            self.session_open_requested.emit(session_id)

    def _request_menu(self, position) -> None:
        item = self.itemAt(position)
        if item is None:
            return
        session_id = str(item.data(_SESSION_ID_ROLE) or "")
        if session_id:
            self.session_menu_requested.emit(
                session_id,
                self.viewport().mapToGlobal(position),
            )

    def replace_summaries(
        self,
        summaries: Iterable[AssistantSessionSummary],
    ) -> None:
        ordered = tuple(summaries)
        incoming_ids = {summary.session_id for summary in ordered}
        scroll_value = self.verticalScrollBar().value()

        for session_id in tuple(self._rows):
            if session_id in incoming_ids:
                continue
            row_widget = self._rows.pop(session_id)
            item = self._item_for_session(session_id)
            if item is not None:
                self.removeItemWidget(item)
                self.takeItem(self.row(item))
            row_widget.deleteLater()

        for target_index, summary in enumerate(ordered):
            item = self._item_for_session(summary.session_id)
            row_widget = self._rows.get(summary.session_id)
            if item is None or row_widget is None:
                item = _session_item(summary)
                self.insertItem(target_index, item)
                row_widget = _SessionRow(summary, parent=self.viewport())
                self._wire_row(row_widget)
                self._rows[summary.session_id] = row_widget
                self.setItemWidget(item, row_widget)
            else:
                item.setData(_SESSION_TITLE_ROLE, summary.title)
                item.setData(_SESSION_PINNED_ROLE, summary.pinned)
                item.setData(_SESSION_CORRUPT_ROLE, summary.corrupt)
                row_widget.update_summary(summary)
            current_index = self.row(item)
            if current_index != target_index:
                destination = (
                    target_index + 1
                    if current_index < target_index
                    else target_index
                )
                moved = self.model().moveRow(
                    QModelIndex(),
                    current_index,
                    QModelIndex(),
                    destination,
                )
                if not moved:
                    raise RuntimeError("Unable to reorder assistant session rows")

        self.verticalScrollBar().setValue(scroll_value)

    def session_row(self, session_id: str) -> _SessionRow | None:
        return self._rows.get(str(session_id or ""))

    def refresh_relative_times(self) -> None:
        for row_widget in self._rows.values():
            row_widget.refresh_relative_time()

    def set_selected_session(self, session_id: str) -> None:
        selected = str(session_id or "")
        self.clearSelection()
        matched = False
        for candidate_id, row_widget in self._rows.items():
            is_selected = candidate_id == selected
            row_widget.set_selected(is_selected)
            if is_selected:
                item = self._item_for_session(candidate_id)
                if item is not None:
                    self.setCurrentItem(item)
                    matched = True
        if not matched:
            self.setCurrentItem(None)

    def filter_title(self, query: str) -> None:
        normalized = str(query or "").strip().casefold()
        for index in range(self.count()):
            item = self.item(index)
            session_id = str(item.data(_SESSION_ID_ROLE) or "")
            row_widget = self._rows.get(session_id)
            title = (
                row_widget._display_title
                if row_widget is not None
                else str(item.data(_SESSION_TITLE_ROLE) or "")
            )
            item.setHidden(bool(normalized and normalized not in title.casefold()))

    def visible_item_count(self) -> int:
        return sum(
            1 for index in range(self.count()) if not self.item(index).isHidden()
        )

    def _wire_row(self, row_widget: _SessionRow) -> None:
        row_widget.selected.connect(self._open_session_id)
        row_widget.menu_requested.connect(self.session_menu_requested.emit)
        row_widget.pin_requested.connect(self.session_pin_requested.emit)
        row_widget.rename_requested.connect(self.session_rename_requested.emit)
        row_widget.delete_confirmation_requested.connect(
            self.session_delete_confirmation_requested.emit
        )
        row_widget.delete_requested.connect(self.session_delete_requested.emit)
        row_widget.icon_requested.connect(self.session_icon_requested.emit)
        row_widget.drag_requested.connect(self._start_session_drag)

    def _open_session_id(self, session_id: str) -> None:
        item = self._item_for_session(session_id)
        if item is not None:
            self.setCurrentItem(item)
        self.session_open_requested.emit(session_id)

    def keyPressEvent(self, event) -> None:
        item = self.currentItem()
        if item is not None and event.key() in {
            Qt.Key_Return,
            Qt.Key_Enter,
            Qt.Key_Space,
        }:
            self._open_item(item)
            event.accept()
            return
        if item is not None and event.key() == Qt.Key_F2:
            session_id = str(item.data(_SESSION_ID_ROLE) or "")
            row_widget = self._rows.get(session_id)
            if row_widget is not None:
                row_widget.start_rename()
            event.accept()
            return
        if item is not None and event.key() == Qt.Key_Delete:
            session_id = str(item.data(_SESSION_ID_ROLE) or "")
            row_widget = self._rows.get(session_id)
            if row_widget is not None:
                row_widget.request_delete()
            event.accept()
            return
        if item is not None and (
            event.key() == Qt.Key_Menu
            or (
                event.key() == Qt.Key_F10
                and event.modifiers() & Qt.ShiftModifier
            )
        ):
            session_id = str(item.data(_SESSION_ID_ROLE) or "")
            row_widget = self._rows.get(session_id)
            if session_id and row_widget is not None:
                self.session_menu_requested.emit(
                    session_id,
                    row_widget.mapToGlobal(row_widget.rect().bottomLeft()),
                )
            event.accept()
            return
        super().keyPressEvent(event)

    def _start_session_drag(self, session_id: str) -> None:
        item = self._item_for_session(session_id)
        if item is None or bool(item.data(_SESSION_CORRUPT_ROLE)):
            return
        self.setCurrentItem(item)
        self.startDrag(Qt.MoveAction)

    def startDrag(self, supported_actions) -> None:
        item = self.currentItem()
        session_id = str(item.data(_SESSION_ID_ROLE) or "") if item else ""
        if (
            not session_id
            or item is None
            or bool(item.data(_SESSION_CORRUPT_ROLE))
        ):
            return
        mime = QMimeData()
        mime.setData(
            _SESSION_MIME_TYPE,
            f"{session_id}\n{int(self._pinned_target)}".encode(),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(supported_actions, Qt.MoveAction)

    def _item_for_session(self, session_id: str) -> QListWidgetItem | None:
        for index in range(self.count()):
            item = self.item(index)
            if str(item.data(_SESSION_ID_ROLE) or "") == session_id:
                return item
        return None

    def dropEvent(self, event) -> None:
        source = event.source()
        session_id, source_pinned = self._drag_payload(event.mimeData())
        if isinstance(source, _SessionList):
            item = source.currentItem()
            session_id = (
                str(item.data(_SESSION_ID_ROLE) or "")
                if item is not None
                else session_id
            )
            corrupt = bool(
                item.data(_SESSION_CORRUPT_ROLE)
            ) if item is not None else False
            same_section = source is self
        else:
            corrupt = False
            same_section = (
                source_pinned is not None
                and source_pinned == self._pinned_target
            )
            if same_section:
                source = self
        if not session_id:
            event.ignore()
            return
        item = (
            source._item_for_session(session_id)
            if isinstance(source, _SessionList)
            else None
        )
        if item is not None:
            corrupt = corrupt or bool(item.data(_SESSION_CORRUPT_ROLE))
        if corrupt:
            event.ignore()
            return
        target_index = self._drop_insertion_index(event.position().toPoint())
        if not same_section:
            self.session_move_requested.emit(
                session_id,
                self._pinned_target,
                target_index,
            )
            event.acceptProposedAction()
            return
        source_index = self.row(item)
        if source_index < target_index:
            target_index -= 1
        if target_index != source_index:
            destination = (
                target_index + 1
                if source_index < target_index
                else target_index
            )
            if self.model().moveRow(
                QModelIndex(),
                source_index,
                QModelIndex(),
                destination,
            ):
                self.session_order_requested.emit(
                    tuple(
                        str(self.item(index).data(_SESSION_ID_ROLE) or "")
                        for index in range(self.count())
                        if not bool(
                            self.item(index).data(_SESSION_CORRUPT_ROLE)
                        )
                    ),
                    self._pinned_target,
                )
                event.acceptProposedAction()
                return
        event.ignore()

    def dragEnterEvent(self, event) -> None:
        session_id, _source_pinned = self._drag_payload(event.mimeData())
        if session_id:
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        session_id, _source_pinned = self._drag_payload(event.mimeData())
        if session_id:
            event.acceptProposedAction()
            return
        event.ignore()

    @staticmethod
    def _drag_payload(mime) -> tuple[str, bool | None]:
        if mime is None or not mime.hasFormat(_SESSION_MIME_TYPE):
            return "", None
        try:
            raw = bytes(mime.data(_SESSION_MIME_TYPE)).decode("utf-8")
            session_id, pinned_text = raw.split("\n", 1)
        except (UnicodeError, ValueError):
            return "", None
        return session_id.strip(), pinned_text.strip() == "1"

    def _drop_insertion_index(self, position) -> int:
        target = self.itemAt(position)
        if target is None:
            return self.count()
        index = self.row(target)
        if position.y() > self.visualItemRect(target).center().y():
            index += 1
        return index

    def sizeHint(self) -> QSize:
        return QSize(212, max(36, min(180, self.count() * 36 + 4)))


class _PinnedDropHint(QFrame):
    session_pin_requested = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("assistant_pin_drop_hint")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setFixedHeight(34)
        self.setProperty("dragActive", False)
        self.setAccessibleName("拖到这里置顶")
        self.setToolTip("把最近任务拖到这里即可置顶")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)
        layout.addStretch(1)
        self._icon = QLabel(self)
        self._icon.setObjectName("assistant_pin_drop_icon")
        self._icon.setFixedSize(16, 16)
        self._icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon)
        self._label = QLabel("拖到这里置顶", self)
        self._label.setObjectName("assistant_pin_drop_label")
        layout.addWidget(self._label)
        layout.addStretch(1)

    def apply_theme(self) -> None:
        theme = get_theme()
        color = theme.primary if self.property("dragActive") else theme.icon_secondary
        self._icon.setPixmap(get_icon("pin", 14, color=color).pixmap(14, 14))

    def _set_drag_active(self, active: bool) -> None:
        if bool(self.property("dragActive")) == active:
            return
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.apply_theme()

    def dragEnterEvent(self, event) -> None:
        if isinstance(event.source(), _SessionList):
            self._set_drag_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._set_drag_active(False)
        source = event.source()
        item = source.currentItem() if isinstance(source, _SessionList) else None
        session_id = str(item.data(_SESSION_ID_ROLE) or "") if item else ""
        if session_id:
            self.session_pin_requested.emit(session_id, True)
            event.acceptProposedAction()
        else:
            event.ignore()


class AssistantSessionSidebar(QFrame):
    """LDWord sidebar structure connected to real assistant sessions."""

    session_selected = Signal(str)
    new_session_requested = Signal()
    session_menu_requested = Signal(str, object)
    session_pin_requested = Signal(str, bool)
    session_rename_requested = Signal(str, str)
    session_delete_requested = Signal(str)
    session_icon_requested = Signal(str, object)
    session_order_requested = Signal(object, bool)
    session_move_requested = Signal(str, bool, int)

    WIDTH = 240

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("assistant_session_rail")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(self.WIDTH)
        self._selected_session = ""
        self._filter_query = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 16, 12, 12)
        root.setSpacing(0)

        mode_host = QWidget(self)
        mode_host.setObjectName("assistant_mode_switcher")
        mode_layout = QHBoxLayout(mode_host)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        self._chat_heading = QPushButton("对话", mode_host)
        self._chat_heading.setObjectName("assistant_mode_button")
        self._chat_heading.setCheckable(True)
        self._chat_heading.setChecked(True)
        self._chat_heading.setIcon(get_icon("message-circle", 17))
        self._chat_heading.setIconSize(QSize(17, 17))
        self._chat_heading.setFixedHeight(34)
        self._chat_heading.setFocusPolicy(Qt.NoFocus)
        self._chat_heading.clicked.connect(
            lambda _checked=False: self._chat_heading.setChecked(True)
        )
        mode_layout.addWidget(self._chat_heading)
        mode_layout.addStretch(1)
        self._search_button = QPushButton("", mode_host)
        self._search_button.setObjectName("assistant_session_search_button")
        self._search_button.setIcon(get_icon("search", 15))
        self._search_button.setIconSize(QSize(15, 15))
        self._search_button.setFixedSize(30, 30)
        self._search_button.setToolTip("搜索对话（Ctrl+F）")
        self._search_button.setAccessibleName("搜索对话")
        self._search_button.clicked.connect(self.show_search)
        mode_layout.addWidget(self._search_button)
        root.addWidget(mode_host)

        self._search_host = QWidget(self)
        self._search_host.setObjectName("assistant_session_search_host")
        search_layout = QHBoxLayout(self._search_host)
        search_layout.setContentsMargins(0, 6, 0, 0)
        search_layout.setSpacing(4)
        self._search_edit = _RenameLineEdit(self._search_host)
        self._search_edit.setObjectName("assistant_session_search")
        self._search_edit.setPlaceholderText("搜索对话")
        self._search_edit.setAccessibleName("搜索对话")
        self._search_edit.textChanged.connect(self.filter_sessions)
        self._search_edit.returnPressed.connect(
            self._open_first_filtered_session
        )
        self._search_edit.cancel_requested.connect(self.hide_search)
        search_layout.addWidget(self._search_edit, 1)
        self._search_close = QPushButton("", self._search_host)
        self._search_close.setObjectName("assistant_session_search_close")
        self._search_close.setIcon(get_icon("x", 14))
        self._search_close.setIconSize(QSize(14, 14))
        self._search_close.setFixedSize(30, 30)
        self._search_close.setToolTip("关闭搜索")
        self._search_close.setAccessibleName("关闭对话搜索")
        self._search_close.clicked.connect(self.hide_search)
        search_layout.addWidget(self._search_close)
        self._search_host.hide()
        root.addWidget(self._search_host)
        self._search_shortcut = QShortcut(QKeySequence.Find, self)
        self._search_shortcut.activated.connect(self.show_search)
        root.addSpacing(14)

        self._new_button = QPushButton("新任务", self)
        self._new_button.setObjectName("assistant_new_session")
        self._new_button.setIcon(get_icon("plus", 16))
        self._new_button.setIconSize(QSize(16, 16))
        self._new_button.setFixedHeight(38)
        self._new_button.clicked.connect(self._request_new_session)
        root.addWidget(self._new_button)
        root.addSpacing(14)
        self._top_divider = QFrame(self)
        self._top_divider.setObjectName("assistant_sidebar_divider")
        self._top_divider.setFrameShape(QFrame.HLine)
        self._top_divider.setFixedHeight(1)
        root.addWidget(self._top_divider)
        root.addSpacing(12)

        self._pinned_label = QLabel("置顶", self)
        self._pinned_label.setObjectName("assistant_sidebar_section_label")
        root.addWidget(self._pinned_label)
        root.addSpacing(4)
        self._pin_drop_hint = _PinnedDropHint(self)
        self._pin_drop_hint.session_pin_requested.connect(
            self.session_pin_requested.emit
        )
        root.addWidget(self._pin_drop_hint)
        self._pinned_list = _SessionList(pinned_target=True, parent=self)
        self._wire_session_list(self._pinned_list)
        self._pinned_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        root.addWidget(self._pinned_list)

        root.addSpacing(10)
        self._bottom_divider = QFrame(self)
        self._bottom_divider.setObjectName("assistant_sidebar_divider")
        self._bottom_divider.setFrameShape(QFrame.HLine)
        self._bottom_divider.setFixedHeight(1)
        root.addWidget(self._bottom_divider)
        root.addSpacing(12)

        self._recent_label = QLabel("最近任务", self)
        self._recent_label.setObjectName("assistant_sidebar_section_label")
        root.addWidget(self._recent_label)
        root.addSpacing(4)
        self._recent_list = _SessionList(pinned_target=False, parent=self)
        self._wire_session_list(self._recent_list)
        root.addWidget(self._recent_list, 1)
        self._recent_empty_label = QLabel("还没有最近对话", self)
        self._recent_empty_label.setObjectName("assistant_session_empty")
        self._recent_empty_label.setAlignment(Qt.AlignCenter)
        self._recent_empty_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        self._recent_empty_label.hide()
        root.addWidget(self._recent_empty_label, 1)

        self._relative_time_timer = QTimer(self)
        self._relative_time_timer.setInterval(60_000)
        self._relative_time_timer.timeout.connect(self._refresh_relative_times)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def showEvent(self, event) -> None:
        self._relative_time_timer.start()
        self._refresh_relative_times()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._relative_time_timer.stop()
        super().hideEvent(event)

    @property
    def pinned_list(self) -> QListWidget:
        return self._pinned_list

    @property
    def recent_list(self) -> QListWidget:
        return self._recent_list

    @property
    def new_session_button(self) -> QPushButton:
        return self._new_button

    def _wire_session_list(self, session_list: _SessionList) -> None:
        session_list.session_open_requested.connect(self._select_session)
        session_list.session_menu_requested.connect(self.session_menu_requested.emit)
        session_list.session_pin_requested.connect(self.session_pin_requested.emit)
        session_list.session_rename_requested.connect(
            self.session_rename_requested.emit
        )
        session_list.session_delete_confirmation_requested.connect(
            self.request_delete_confirmation
        )
        session_list.session_delete_requested.connect(
            self.session_delete_requested.emit
        )
        session_list.session_icon_requested.connect(
            self.session_icon_requested.emit
        )
        session_list.session_order_requested.connect(
            self.session_order_requested.emit
        )
        session_list.session_move_requested.connect(
            self.session_move_requested.emit
        )

    def _request_new_session(self) -> None:
        self.new_session_requested.emit()

    def _select_session(self, session_id: str) -> None:
        self.cancel_delete_confirmation()
        self.session_selected.emit(session_id)

    def request_delete_confirmation(self, session_id: str) -> bool:
        """Replace the target row's trash icon with an in-place confirm button."""
        target_id = str(session_id or "")
        target_row = None
        for session_list in (self._pinned_list, self._recent_list):
            for candidate_id, row in session_list._rows.items():
                armed = candidate_id == target_id
                row.set_delete_armed(armed)
                if armed:
                    target_row = row
        if target_row is not None:
            target_row.delete_button.setFocus(Qt.ShortcutFocusReason)
        return target_row is not None

    def cancel_delete_confirmation(self) -> None:
        for session_list in (self._pinned_list, self._recent_list):
            for row in session_list._rows.values():
                row.set_delete_armed(False)

    def select_session(self, session_id: str) -> None:
        self._selected_session = str(session_id or "")
        for session_list in (self._pinned_list, self._recent_list):
            session_list.blockSignals(True)
            try:
                session_list.set_selected_session(self._selected_session)
            finally:
                session_list.blockSignals(False)

    def restore_rename(self, session_id: str, attempted_title: str) -> None:
        for session_list in (self._pinned_list, self._recent_list):
            row = session_list.session_row(session_id)
            if row is None:
                continue
            row.start_rename()
            row.title_edit.setText(str(attempted_title or ""))
            row.title_edit.selectAll()
            return

    def _clear_list_selection(self) -> None:
        self._selected_session = ""
        for session_list in (self._pinned_list, self._recent_list):
            session_list.set_selected_session("")

    def replace_sessions(
        self,
        summaries: Iterable[AssistantSessionSummary],
        *,
        selected_session_id: str = "",
    ) -> None:
        ordered = tuple(summaries)
        self._pinned_list.replace_summaries(
            summary for summary in ordered if summary.pinned
        )
        self._recent_list.replace_summaries(
            summary for summary in ordered if not summary.pinned
        )
        has_pinned = self._pinned_list.count() > 0
        self._pin_drop_hint.setVisible(not has_pinned)
        self._pinned_list.setVisible(has_pinned)
        if has_pinned:
            self._pinned_list.setFixedHeight(self._pinned_list.sizeHint().height())
        self.filter_sessions(self._filter_query)
        self.select_session(selected_session_id)

    def all_items(self) -> tuple[QListWidgetItem, ...]:
        return tuple(
            session_list.item(index)
            for session_list in (self._pinned_list, self._recent_list)
            for index in range(session_list.count())
        )

    def filter_sessions(self, text: str) -> None:
        self._filter_query = str(text or "")
        self._pinned_list.filter_title(self._filter_query)
        self._recent_list.filter_title(self._filter_query)
        self._sync_filtered_sections()

    def show_search(self) -> None:
        self._search_host.show()
        self._search_edit.setFocus(Qt.ShortcutFocusReason)
        self._search_edit.selectAll()

    def hide_search(self) -> None:
        self._search_edit.clear()
        self._search_host.hide()
        self._search_button.setFocus(Qt.ShortcutFocusReason)

    def _open_first_filtered_session(self) -> None:
        for session_list in (self._pinned_list, self._recent_list):
            for index in range(session_list.count()):
                item = session_list.item(index)
                if not item.isHidden():
                    session_list._open_item(item)
                    return

    def _sync_filtered_sections(self) -> None:
        query_active = bool(self._filter_query.strip())
        pinned_visible = self._pinned_list.visible_item_count()
        recent_visible = self._recent_list.visible_item_count()
        has_pinned = self._pinned_list.count() > 0
        self._pinned_label.setVisible(not query_active or pinned_visible > 0)
        self._pin_drop_hint.setVisible(not has_pinned and not query_active)
        self._pinned_list.setVisible(pinned_visible > 0)
        if pinned_visible:
            self._pinned_list.setFixedHeight(
                max(36, min(180, pinned_visible * 36 + 4))
            )
        self._recent_list.setVisible(recent_visible > 0)
        self._recent_empty_label.setText(
            "没有匹配的对话" if query_active else "还没有最近对话"
        )
        self._recent_empty_label.setVisible(
            recent_visible == 0
            and (not query_active or pinned_visible == 0)
        )

    def _refresh_relative_times(self) -> None:
        self._pinned_list.refresh_relative_times()
        self._recent_list.refresh_relative_times()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QFrame#assistant_session_rail {{
                background: {theme.bg_card};
                border: none;
                border-right: 1px solid {theme.divider};
            }}
            QWidget#assistant_mode_switcher {{ background: transparent; }}
            QWidget#assistant_session_search_host {{ background: transparent; }}
            QPushButton#assistant_mode_button {{
                background: transparent;
                color: {theme.text_secondary};
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0;
                padding: 4px 4px;
                font-weight: {theme.font_weight_emphasis};
                text-align: left;
            }}
            QPushButton#assistant_mode_button:checked {{
                color: {theme.text_primary};
                border-bottom-color: {theme.primary};
            }}
            QPushButton#assistant_new_session {{
                color: {theme.text_primary};
                background: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_md}px;
                padding: 0 12px;
                text-align: left;
            }}
            QPushButton#assistant_new_session:hover {{
                background: {theme.bg_hover};
                border-color: {theme.primary};
            }}
            QPushButton#assistant_session_search_button,
            QPushButton#assistant_session_search_close {{
                color: {theme.text_secondary};
                background: transparent;
                border: none;
                border-radius: {theme.radius_sm}px;
                padding: 0;
            }}
            QPushButton#assistant_session_search_button:hover,
            QPushButton#assistant_session_search_close:hover {{
                color: {theme.text_primary};
                background: {theme.bg_hover};
            }}
            QLineEdit#assistant_session_search {{
                color: {theme.text_primary};
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_sm}px;
                padding: 0 8px;
                min-height: 30px;
            }}
            QLineEdit#assistant_session_search:focus {{
                border-color: {theme.border_focus};
            }}
            QFrame#assistant_sidebar_divider {{ background: {theme.divider}; border: none; }}
            QLabel#assistant_sidebar_section_label {{
                color: {theme.text_hint};
                background: transparent;
                padding: 0 4px;
            }}
            QLabel#assistant_session_empty {{
                color: {theme.text_hint};
                background: transparent;
            }}
            QFrame#assistant_pin_drop_hint {{
                background: {theme.bg_hover};
                border: 1px solid transparent;
                border-radius: {theme.radius_md}px;
            }}
            QFrame#assistant_pin_drop_hint:hover {{
                background: {theme.primary_light};
            }}
            QFrame#assistant_pin_drop_hint[dragActive="true"] {{
                background: {theme.primary_light};
                border-color: {theme.primary};
            }}
            QLabel#assistant_pin_drop_icon {{
                background: transparent;
                border: none;
            }}
            QLabel#assistant_pin_drop_label {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
            }}
            QFrame#assistant_pin_drop_hint:hover QLabel#assistant_pin_drop_label,
            QFrame#assistant_pin_drop_hint[dragActive="true"] QLabel#assistant_pin_drop_label {{
                color: {theme.text_secondary};
            }}
            QListWidget#assistant_pinned_session_list,
            QListWidget#assistant_recent_session_list {{
                color: {theme.text_secondary};
                background: transparent;
                border: none;
                outline: none;
                padding: 0;
            }}
            QListWidget#assistant_pinned_session_list::item,
            QListWidget#assistant_recent_session_list::item {{
                border: none;
                padding: 0;
                background: transparent;
            }}
            QListWidget#assistant_pinned_session_list::item:hover,
            QListWidget#assistant_pinned_session_list::item:selected,
            QListWidget#assistant_recent_session_list::item:hover,
            QListWidget#assistant_recent_session_list::item:selected {{
                border: none;
                background: transparent;
            }}
            """
        )
        self._chat_heading.setIcon(get_icon("message-circle", 17))
        self._new_button.setIcon(get_icon("plus", 16))
        self._search_button.setIcon(get_icon("search", 15))
        self._search_close.setIcon(get_icon("x", 14))
        self._pin_drop_hint.apply_theme()
        for session_list in (self._pinned_list, self._recent_list):
            for row_widget in session_list._rows.values():
                row_widget._apply_theme()


def _status_marker(turn_status: str, document_status: str) -> str:
    return session_row_presentation(
        AssistantSessionSummary(
            session_id="status-projection",
            title="",
            updated_at="",
            turn_status=turn_status,
            document_job_status=document_status,
        )
    ).marker


def _status_tooltip(summary: AssistantSessionSummary) -> str:
    return session_row_presentation(summary).status_label or "对话"


def _session_item(summary: AssistantSessionSummary) -> QListWidgetItem:
    # The visible content is rendered by _SessionRow. Keeping text in the
    # underlying item makes Qt's delegate paint the title a second time through
    # the row's transparent background.
    item = QListWidgetItem()
    item.setData(_SESSION_ID_ROLE, summary.session_id)
    item.setData(_SESSION_PINNED_ROLE, summary.pinned)
    item.setData(_SESSION_CORRUPT_ROLE, summary.corrupt)
    item.setData(_SESSION_TITLE_ROLE, summary.title)
    item.setSizeHint(QSize(196, _SessionRow.HEIGHT))
    return item


def _relative_age(value: str, *, now: datetime | None = None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        seconds = max(
            0,
            int(
                (
                    reference.astimezone(timezone.utc)
                    - parsed.astimezone(timezone.utc)
                ).total_seconds()
            ),
        )
    except (TypeError, ValueError, OverflowError):
        return ""
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60}分"
    if seconds < 86400:
        return f"{seconds // 3600}时"
    days = seconds // 86400
    if days < 30:
        return f"{days}天"
    if days < 365:
        return f"{days // 30}月"
    return f"{days // 365}年"


def _localized_time(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OverflowError):
        return ""


__all__ = [
    "SESSION_ICON_OPTIONS",
    "AssistantSessionSidebar",
    "SessionRowPresentation",
    "session_row_presentation",
]
