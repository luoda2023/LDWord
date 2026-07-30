"""Design-compatible assistant session sidebar backed by Form sessions.

This module ports the information architecture and interaction contract of
Alavette Design's ``SessionSidebar`` without importing its Flow-owned models.
The sidebar only emits user intent; :class:`AssistantPanel` remains the single
owner of session persistence and document execution state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from src.assistant.storage.models import AssistantSessionSummary
from src.qt_api import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


_SESSION_ID_ROLE = int(Qt.UserRole)
_SESSION_PINNED_ROLE = int(Qt.UserRole) + 1


class _SessionList(QListWidget):
    """One Design task section with cross-section pin/unpin drops."""

    session_open_requested = Signal(str)
    session_menu_requested = Signal(str, object)
    session_pin_requested = Signal(str, bool)

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

    def dropEvent(self, event) -> None:  # noqa: N802
        source = event.source()
        if isinstance(source, _SessionList) and source is not self:
            item = source.currentItem()
            session_id = str(item.data(_SESSION_ID_ROLE) or "") if item else ""
            if session_id:
                self.session_pin_requested.emit(session_id, self._pinned_target)
                event.acceptProposedAction()
                return
        event.ignore()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(212, max(36, min(180, self.count() * 36 + 4)))


class _PinnedDropHint(QLabel):
    session_pin_requested = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("拖拽任务以置顶", parent)
        self.setObjectName("assistant_pin_drop_hint")
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setFixedHeight(36)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if isinstance(event.source(), _SessionList):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        source = event.source()
        item = source.currentItem() if isinstance(source, _SessionList) else None
        session_id = str(item.data(_SESSION_ID_ROLE) or "") if item else ""
        if session_id:
            self.session_pin_requested.emit(session_id, True)
            event.acceptProposedAction()
        else:
            event.ignore()


class AssistantSessionSidebar(QFrame):
    """Alavette Design sidebar structure connected to real Form sessions."""

    session_selected = Signal(str)
    new_session_requested = Signal()
    session_menu_requested = Signal(str, object)
    session_pin_requested = Signal(str, bool)

    WIDTH = 240

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("assistant_session_rail")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(self.WIDTH)
        self._selected_session = ""

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
        root.addWidget(mode_host)
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

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    @property
    def pinned_list(self) -> QListWidget:
        return self._pinned_list

    @property
    def recent_list(self) -> QListWidget:
        return self._recent_list

    def _wire_session_list(self, session_list: _SessionList) -> None:
        session_list.session_open_requested.connect(self._select_session)
        session_list.session_menu_requested.connect(self.session_menu_requested.emit)
        session_list.session_pin_requested.connect(self.session_pin_requested.emit)

    def _request_new_session(self) -> None:
        self._clear_list_selection()
        self.new_session_requested.emit()

    def _select_session(self, session_id: str) -> None:
        self.select_session(session_id)
        self.session_selected.emit(session_id)

    def select_session(self, session_id: str) -> None:
        self._selected_session = str(session_id or "")
        for session_list in (self._pinned_list, self._recent_list):
            session_list.blockSignals(True)
            try:
                session_list.clearSelection()
                for index in range(session_list.count()):
                    item = session_list.item(index)
                    if str(item.data(_SESSION_ID_ROLE) or "") == self._selected_session:
                        session_list.setCurrentItem(item)
                        break
            finally:
                session_list.blockSignals(False)

    def _clear_list_selection(self) -> None:
        self._selected_session = ""
        for session_list in (self._pinned_list, self._recent_list):
            session_list.clearSelection()
            session_list.setCurrentItem(None)

    def replace_sessions(
        self,
        summaries: Iterable[AssistantSessionSummary],
        *,
        selected_session_id: str = "",
    ) -> None:
        self._pinned_list.clear()
        self._recent_list.clear()
        for summary in summaries:
            target = self._pinned_list if summary.pinned else self._recent_list
            target.addItem(self._session_item(summary))
        has_pinned = self._pinned_list.count() > 0
        self._pin_drop_hint.setVisible(not has_pinned)
        self._pinned_list.setVisible(has_pinned)
        if has_pinned:
            self._pinned_list.setFixedHeight(self._pinned_list.sizeHint().height())
        self.select_session(selected_session_id)

    def all_items(self) -> tuple[QListWidgetItem, ...]:
        return tuple(
            session_list.item(index)
            for session_list in (self._pinned_list, self._recent_list)
            for index in range(session_list.count())
        )

    def filter_sessions(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        for item in self.all_items():
            item.setHidden(bool(query and query not in item.text().casefold()))

    @staticmethod
    def _session_item(summary: AssistantSessionSummary) -> QListWidgetItem:
        marker = (
            "⚠"
            if summary.corrupt
            else _status_marker(
                summary.turn_status,
                summary.document_job_status,
            )
        )
        age = _relative_age(summary.updated_at)
        suffix = f"  {age}" if age else ""
        item = QListWidgetItem(f"{marker}  {summary.title}{suffix}")
        item.setData(_SESSION_ID_ROLE, summary.session_id)
        item.setData(_SESSION_PINNED_ROLE, summary.pinned)
        item.setIcon(
            get_icon(
                "alert-triangle" if summary.corrupt else "message-circle",
                15,
            )
        )
        item.setToolTip(
            (
                f"{summary.title}\n原文件已保留：{summary.recovery_path}\n"
                "点击查看恢复说明。"
                if summary.corrupt
                else f"{summary.title}\n更新时间：{summary.updated_at or '未知'}"
            )
        )
        item.setSizeHint(QSize(196, 34))
        return item

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
            QFrame#assistant_sidebar_divider {{ background: {theme.divider}; border: none; }}
            QLabel#assistant_sidebar_section_label {{
                color: {theme.text_hint};
                background: transparent;
                padding: 0 4px;
            }}
            QLabel#assistant_pin_drop_hint {{
                color: {theme.text_hint};
                background: transparent;
                border: 1px dashed {theme.border};
                border-radius: {theme.radius_sm}px;
            }}
            QLabel#assistant_pin_drop_hint:hover {{
                color: {theme.text_secondary};
                background: {theme.bg_hover};
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
                border-radius: {theme.radius_sm}px;
                padding: 0 5px;
            }}
            QListWidget#assistant_pinned_session_list::item:hover,
            QListWidget#assistant_recent_session_list::item:hover {{
                background: {theme.bg_hover};
                color: {theme.text_primary};
            }}
            QListWidget#assistant_pinned_session_list::item:selected,
            QListWidget#assistant_recent_session_list::item:selected {{
                background: {theme.bg_selected};
                color: {theme.text_primary};
            }}
            """
        )
        self._chat_heading.setIcon(get_icon("message-circle", 17))
        self._new_button.setIcon(get_icon("plus", 16))


def _status_marker(turn_status: str, document_status: str) -> str:
    running = {"provider_running", "content_generation_running", "preflight_running", "execution_running"}
    if str(turn_status or "") in running or str(document_status or "") in running:
        return "●"
    if str(document_status or "") in {"success", "completed"}:
        return "✓"
    if str(turn_status or "") in {"failed", "cancelled"}:
        return "!"
    return "·"


def _relative_age(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        seconds = max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return ""
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60}分"
    if seconds < 86400:
        return f"{seconds // 3600}时"
    return f"{seconds // 86400}天"


__all__ = ["AssistantSessionSidebar"]
