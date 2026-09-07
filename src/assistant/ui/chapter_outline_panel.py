# -*- coding: utf-8 -*-
"""Chapter authoring progress board — the top-right writing overview.

While the engineering long-document authoring runs chapter by chapter, this
board floats at the top-right of the conversation and shows the confirmed
outline with live state per chapter:

* pending   (⏳ 待写)
* running   (✍️ 写作中)
* done      (✓ 已完成 + characters written)
* failed    (⚠ 生成中断/出错)

The board only *displays* progress. Live per-chapter text is streamed into the
conversation itself so the user watches the model write; the workflow mixin
owns that wiring and calls these display methods on the UI thread.
"""
from __future__ import annotations

from src.qt_api import (
    QEvent,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, apply_text_role


_CHAPTER_STATE_ICON = {
    "pending": "circle",
    "running": "loader",
    "done": "circle-check",
    "failed": "circle-alert",
}


class _ChapterRow(QWidget):
    """One row in the outline: state icon, title, chars badge."""

    def __init__(self, index: int, title: str, parent=None) -> None:
        super().__init__(parent)
        self.index = int(index)
        self.title = str(title or "")
        self._state = "pending"
        self._chars = 0
        self.setObjectName("chapter_outline_row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(8)

        self._icon = QLabel(self)
        self._icon.setFixedSize(16, 16)
        self._icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon, 0, Qt.AlignVCenter)

        self._num = QLabel(str(self.index), self)
        self._num.setObjectName("chapter_outline_num")
        self._num.setFixedWidth(22)
        self._num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        apply_text_role(self._num, TextRole.CAPTION)
        layout.addWidget(self._num, 0, Qt.AlignVCenter)

        self._title = QLabel(self.title, self)
        self._title.setObjectName("chapter_outline_title")
        self._title.setWordWrap(True)
        self._title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        apply_text_role(self._title, TextRole.BODY)
        layout.addWidget(self._title, 1)

        self._chars_label = QLabel("", self)
        self._chars_label.setObjectName("chapter_outline_chars")
        self._chars_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        apply_text_role(self._chars_label, TextRole.CAPTION)
        layout.addWidget(self._chars_label, 0, Qt.AlignVCenter)

        bind_theme(self, self._apply_theme)
        self._refresh()

    def set_state(self, state: str, *, chars: int | None = None) -> None:
        normalized = str(state or "pending").strip()
        if normalized not in _CHAPTER_STATE_ICON:
            normalized = "pending"
        changed = normalized != self._state
        self._state = normalized
        if chars is not None:
            self._chars = max(0, int(chars))
            changed = True
        if changed:
            self._refresh()

    def set_chars(self, chars: int) -> None:
        """Update only the live character badge (kept light per stream token)."""
        if self._state != "running":
            return
        previous = self._chars
        self._chars = max(0, int(chars))
        if self._chars == previous:
            return
        theme = get_theme()
        self._chars_label.setText(f"写作中 · {self._chars:,} 字")
        self._chars_label.setStyleSheet(
            f"color: {theme.primary}; background: transparent; border: none;"
        )

    def state(self) -> str:
        return self._state

    def chars(self) -> int:
        return self._chars

    def _refresh(self) -> None:
        theme = get_theme()
        color = theme.text_hint
        if self._state == "running":
            color = theme.primary
        elif self._state == "done":
            color = theme.success
        elif self._state == "failed":
            color = theme.error
        icon_name = _CHAPTER_STATE_ICON[self._state]
        self._icon.setPixmap(get_icon(icon_name, 15, color).pixmap(15, 15))
        if self._state == "running":
            self._chars_label.setText("写作中…")
        elif self._state == "done":
            self._chars_label.setText(f"{self._chars:,} 字")
        elif self._state == "failed":
            self._chars_label.setText("中断")
        else:
            self._chars_label.setText("待写")
        self._apply_row_style(color)

    def _apply_row_style(self, accent: str) -> None:
        theme = get_theme()
        if self._state == "running":
            background = theme.bg_selected
            border = theme.border_focus
        else:
            background = theme.bg_window
            border = theme.border_light
        self.setStyleSheet(
            f"""
            QWidget#chapter_outline_row {{
                background: {background};
                border: 1px solid {border};
                border-radius: {theme.radius_sm}px;
            }}
            QLabel#chapter_outline_num,
            QLabel#chapter_outline_title,
            QLabel#chapter_outline_chars {{
                background: transparent;
                border: none;
                color: {theme.text_primary};
            }}
            QLabel#chapter_outline_num {{
                color: {theme.text_hint};
            }}
            QLabel#chapter_outline_chars {{
                color: {accent};
            }}
            """
        )

    def _apply_theme(self) -> None:
        self._refresh()


class ChapterOutlinePanel(QFrame):
    """Top-right floating board for the chapter-authoring run.

    Lives as a borderless child of the assistant message viewport so it never
    reflows the chat; it overlays the top-right corner of the conversation
    area and can be collapsed with the chevron button.
    """

    # Emitted when the user manually hides the board; the workflow mixin
    # auto-reopens it on the next multi-chapter authoring run.
    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("chapter_outline_panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(310)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self._rows: dict[int, _ChapterRow] = {}
        self._titles: list[str] = []
        self._current_index = 0
        self._total = 0
        self._collapsed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 2, 0)
        header.setSpacing(6)
        self._collapse = QToolButton(self)
        self._collapse.setObjectName("chapter_outline_collapse")
        self._collapse.setToolTip("收起 / 展开章节总览")
        self._collapse.setCursor(Qt.PointingHandCursor)
        self._collapse.setFixedSize(22, 22)
        self._collapse.clicked.connect(self.toggle_collapsed)
        header.addWidget(self._collapse, 0, Qt.AlignVCenter)
        self._heading = QLabel("章节写作总览", self)
        self._heading.setObjectName("chapter_outline_heading")
        apply_text_role(self._heading, TextRole.NAVIGATION_TITLE_ACTIVE)
        header.addWidget(self._heading)
        header.addStretch(1)
        self._close_button = QToolButton(self)
        self._close_button.setObjectName("chapter_outline_close")
        self._close_button.setToolTip("隐藏本章节总览")
        self._close_button.setCursor(Qt.PointingHandCursor)
        self._close_button.setFixedSize(22, 22)
        self._close_button.clicked.connect(self.close_board)
        header.addWidget(self._close_button, 0, Qt.AlignVCenter)
        root.addLayout(header)

        self._summary = QLabel("", self)
        self._summary.setObjectName("chapter_outline_summary")
        self._summary.setWordWrap(True)
        apply_text_role(self._summary, TextRole.CAPTION)
        root.addWidget(self._summary)

        self._list_scroll = QScrollArea(self)
        self._list_scroll.setObjectName("chapter_outline_scroll")
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._list_scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)

        self._list_host = QWidget(self._list_scroll)
        self._list_host.setObjectName("chapter_outline_host")
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 2, 0)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch(1)
        self._list_scroll.setWidget(self._list_host)
        root.addWidget(self._list_scroll, 1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self.hide()

    # ---- viewport-child geometry ---------------------------------------
    def _reposition_in_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        available = max(0, parent.height() - 16)
        height = 46 if self._collapsed else min(max(available, 220), 520)
        self.setFixedHeight(height)
        self.adjustSize()
        self.move(max(12, parent.width() - self.width() - 12), 12)

    def event(self, event) -> bool:  # noqa: N802
        if event.type() == QEvent.ParentChange and self.parentWidget() is not None:
            self._reposition_in_parent()
        return super().event(event)

    # ---- public API ----------------------------------------------------
    def show_board(self) -> None:
        self.show()
        self.raise_()
        self._reposition_in_parent()

    def close_board(self) -> None:
        self.hide()
        self.closed.emit()

    def set_outline(self, titles: list[str], *, append: bool = False) -> None:
        """(Re)build rows from an outline. ``append`` keeps existing rows."""
        normalized = [str(t or "").strip() for t in titles if str(t or "").strip()]
        if not normalized:
            return
        if append and self._rows:
            existing_count = len(self._rows)
            for i, title in enumerate(normalized, start=existing_count + 1):
                self._add_row(i, title)
        else:
            for i in range(self._list_layout.count() - 1, -1, -1):
                item = self._list_layout.takeAt(i)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self._rows.clear()
            for i, title in enumerate(normalized, start=1):
                self._add_row(i, title)
        self._titles = normalized
        self._total = len(normalized)
        self._update_summary()

    def begin(self, *, index: int, total: int, title: str) -> None:
        self._current_index = int(index)
        self._total = int(total) or self._total
        if index not in self._rows:
            self._add_row(index, str(title or f"第 {index} 章"))
        row = self._rows[index]
        row.set_state("running", chars=0)
        # Earlier rows that are neither done nor failed become done placeholders
        # when generation moves on, but only after they reported done. Keep any
        # stale pending rows as done so the board reads sequentially.
        for idx, existing in self._rows.items():
            if idx < index and existing.state() not in {"done", "failed"}:
                existing.set_state("done")
        self._update_summary()

    def delta(self, *, index: int, chars: int) -> None:
        if index not in self._rows:
            return
        row = self._rows[index]
        if row.state() != "running":
            row.set_state("running", chars=0)
        row.set_chars(max(0, int(chars)))
        self._update_summary()

    def done(self, *, index: int, chars: int) -> None:
        if index not in self._rows:
            self._add_row(index, f"第 {index} 章")
        row = self._rows[index]
        row.set_state("done", chars=max(0, int(chars)))
        if self._current_index == index:
            self._current_index = 0
        self._update_summary()

    def fail(self, *, index: int | None = None) -> None:
        target = int(index) if index else self._current_index
        if target and target in self._rows:
            self._rows[target].set_state("failed")
        elif self._rows:
            for row in self._rows.values():
                if row.state() == "running":
                    row.set_state("failed")
        self._update_summary()

    def running_index(self) -> int:
        return self._current_index

    def outline_summary(self) -> dict[str, object]:
        done = sum(1 for row in self._rows.values() if row.state() == "done")
        chars = sum(row.chars() for row in self._rows.values() if row.state() == "done")
        return {
            "total": self._total,
            "done": done,
            "remaining": max(0, self._total - done),
            "chars": chars,
        }

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self._list_scroll.setVisible(not self._collapsed)
        self._summary.setVisible(not self._collapsed)
        self._refresh_icons()
        self._reposition_in_parent()

    # ---- internals -----------------------------------------------------
    def _add_row(self, index: int, title: str) -> None:
        if index in self._rows:
            return
        row = _ChapterRow(index, title, self._list_host)
        self._rows[index] = row
        # insert before the trailing stretch
        self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _update_summary(self) -> None:
        done = sum(1 for row in self._rows.values() if row.state() == "done")
        total = self._total or max(self._rows.keys(), default=0)
        if not total:
            self._summary.setText("")
            return
        chars = sum(
            int(row.chars())
            for row in self._rows.values()
            if row.state() == "done"
        )
        if self._current_index:
            remaining = max(0, total - done - 1)
            self._summary.setText(
                f"写作中 第 {self._current_index}/{total} 章 · "
                f"已完成 {chars:,} 字 · 剩 {remaining} 章"
            )
        else:
            self._summary.setText(f"已完成 {done}/{total} 章 · 共 {chars:,} 字")

    def _refresh_icons(self) -> None:
        theme = get_theme()
        self._collapse.setIcon(
            get_icon(
                "chevron-down" if not self._collapsed else "chevron-right",
                15,
                theme.text_hint,
            )
        )
        self._close_button.setIcon(get_icon("x", 14, theme.text_hint))

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QFrame#chapter_outline_panel {{
                background: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_md}px;
            }}
            QLabel#chapter_outline_heading {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#chapter_outline_summary {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
            }}
            QToolButton#chapter_outline_collapse,
            QToolButton#chapter_outline_close {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: {theme.radius_xs}px;
            }}
            QToolButton#chapter_outline_collapse:hover,
            QToolButton#chapter_outline_close:hover {{
                background: {theme.bg_hover};
                border-color: {theme.border_light};
            }}
            QScrollArea#chapter_outline_scroll {{
                background: transparent;
                border: none;
            }}
            QWidget#chapter_outline_host {{
                background: transparent;
                border: none;
            }}
            QScrollArea#chapter_outline_scroll QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollArea#chapter_outline_scroll QScrollBar::handle:vertical {{
                background: {theme.border};
                border-radius: 3px;
                min-height: 28px;
            }}
            QScrollArea#chapter_outline_scroll QScrollBar::add-line:vertical,
            QScrollArea#chapter_outline_scroll QScrollBar::sub-line:vertical,
            QScrollArea#chapter_outline_scroll QScrollBar::add-page:vertical,
            QScrollArea#chapter_outline_scroll QScrollBar::sub-page:vertical {{
                background: transparent;
                border: none;
                height: 0;
            }}
            """
        )
        self._refresh_icons()


__all__ = ["ChapterOutlinePanel"]
