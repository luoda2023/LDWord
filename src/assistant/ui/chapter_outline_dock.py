# -*- coding: utf-8 -*-
"""Docked outline sidebar for engineering long-document authoring.

While the AI writes a long engineering report chapter by chapter, this panel
sits as a *persistent* left dock inside the conversation centre (next to the
chat), showing the confirmed outline (目录大纲) with, per chapter:

* state      —— pending / running / done / failed (待写/写作中/已完成/中断)
* score      —— AI 自评分数 (0-100)
* grade      —— 评分档位 (优/良/待完善/待补充…)
* chars      —— 该章已写字数

A summary strip on top tracks overall completion (已完成 N/M 章 · 总字数 ·
整体评分).  Clicking a chapter asks the workflow mixin to open that chapter in
the document workbench.

Documents that nest coarse grouping headings (篇/部分/卷/单元) above their
content chapters carry per-chapter ``part_title`` metadata; the dock then
renders a collapsible group header for each 篇 (▍…).  Clicking a header folds or
expands the chapter rows underneath, and a 「润色整篇」button on each group
asks the assistant to polish every chapter under that 篇 in one pass (see the
``polish_part_requested`` signal).

Unlike the floating top-right board (which is transient), this dock is meant
to stay visible and behave like part of the LDWord main layout.
"""
from __future__ import annotations

from src.qt_api import (
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


_STATE_ICON = {
    "pending": "circle",
    "running": "loader",
    "done": "circle-check",
    "failed": "circle-alert",
}
_STATE_TEXT = {
    "pending": "待写",
    "running": "写作中",
    "done": "已完成",
    "failed": "中断",
}


def _grade_color(theme, grade: str | None, score: int | None) -> str:
    if score is None:
        return theme.text_hint
    if score >= 85:
        return theme.success
    if score >= 60:
        return theme.warning
    return theme.error


class _PartHeader(QWidget):
    """One collapsible group row for a 篇/部分/卷/单元 that contains chapters."""

    toggled = Signal()
    polish_requested = Signal()  # user asked to 润色整篇 (all chapters under this part)

    def __init__(self, part_title: str, parent=None) -> None:
        super().__init__(parent)
        self.part_title = str(part_title or "")
        self._collapsed = False
        self._count = 0
        self._busy = False
        self.setObjectName("outline_dock_part")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        root = QHBoxLayout(self)
        root.setContentsMargins(4, 5, 4, 5)
        root.setSpacing(4)
        self._chevron = QLabel(self)
        self._chevron.setFixedSize(14, 14)
        self._chevron.setAlignment(Qt.AlignCenter)
        root.addWidget(self._chevron, 0, Qt.AlignVCenter)
        self._text = QLabel(f"▍{self.part_title}", self)
        self._text.setObjectName("outline_dock_part_text")
        self._text.setWordWrap(True)
        self._text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        apply_text_role(self._text, TextRole.CAPTION)
        root.addWidget(self._text, 1)
        self._count_label = QLabel("", self)
        self._count_label.setObjectName("outline_dock_part_count")
        apply_text_role(self._count_label, TextRole.CAPTION)
        root.addWidget(self._count_label, 0, Qt.AlignVCenter)

        # 「润色整篇」：run the AI over every chapter under this 篇 in one pass.
        self._polish = QToolButton(self)
        self._polish.setObjectName("outline_dock_part_polish")
        self._polish.setToolTip(f"润色整篇《{self.part_title}》下的全部章节")
        self._polish.setAccessibleName(f"润色整篇 {self.part_title}")
        self._polish.setCursor(Qt.PointingHandCursor)
        self._polish.setFixedSize(22, 22)
        self._polish.setFocusPolicy(Qt.NoFocus)
        self._polish.clicked.connect(self._on_polish_clicked)
        root.addWidget(self._polish, 0, Qt.AlignVCenter)

        bind_theme(self, self._apply_theme)
        self._refresh()

    # ---- interaction ----------------------------------------------------
    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        # Only toggle collapse when the click did not land on the polish
        # button (the button handles its own click already).
        if (
            event.button() == Qt.LeftButton
            and self.childAt(event.position().toPoint()) is not self._polish
        ):
            self.toggle()
        super().mouseReleaseEvent(event)

    def toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._refresh()
        self.toggled.emit()

    def _on_polish_clicked(self) -> None:
        if self._busy:
            return
        self.polish_requested.emit()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self._refresh()

    def set_busy(self, busy: bool) -> None:
        """While a polish is running, disable re-entry and show a spinner."""
        self._busy = bool(busy)
        self._polish.setEnabled(not self._busy)
        self._refresh()

    def set_count(self, count: int) -> None:
        self._count = max(0, int(count))
        self._count_label.setText(f"{self._count} 章")
        self._refresh()

    def _refresh(self) -> None:
        theme = get_theme()
        arrow = "chevron-right" if self._collapsed else "chevron-down"
        self._chevron.setPixmap(get_icon(arrow, 12, theme.text_hint).pixmap(12, 12))
        icon_name = "loader" if self._busy else "sparkles"
        self._polish.setIcon(
            get_icon(icon_name, 14, theme.primary if not self._busy else theme.text_hint)
        )
        if self._busy:
            self._polish.setToolTip(f"正在润色整篇《{self.part_title}》，请稍候…")
        else:
            self._polish.setToolTip(f"润色整篇《{self.part_title}》下的全部章节")
        self.setToolTip(
            ("展开" if self._collapsed else "收起") + f"《{self.part_title}》下的章节"
        )
        self._apply_row_style()

    def _apply_row_style(self) -> None:
        theme = get_theme()
        background = theme.bg_selected if self._collapsed else theme.bg_window
        border = theme.border_light
        self.setStyleSheet(
            f"""
            QWidget#outline_dock_part {{
                background: {background};
                border: 1px solid {border};
                border-radius: {theme.radius_sm}px;
            }}
            QLabel#outline_dock_part_text {{
                color: {theme.text_secondary};
                background: transparent;
                border: none;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#outline_dock_part_count {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
            }}
            QToolButton#outline_dock_part_polish {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: {theme.radius_xs}px;
            }}
            QToolButton#outline_dock_part_polish:hover {{
                background: {theme.bg_hover};
                border-color: {theme.border_light};
            }}
            QToolButton#outline_dock_part_polish:disabled {{
                background: transparent;
                border: none;
            }}
            """
        )

    def _apply_theme(self) -> None:
        self._refresh()


class _DockRow(QWidget):
    """One chapter row: 序号 + 标题 + 状态/字数/评分/步骤条."""

    clicked = Signal(int)

    def __init__(self, index: int, title: str, parent=None) -> None:
        super().__init__(parent)
        self.index = int(index)
        self.title = str(title or "")
        self._state = "pending"
        self._active = False
        self._chars = 0
        self._score: int | None = None
        self._grade: str | None = None
        self.setObjectName("outline_dock_row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 8, 6)
        root.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        self._icon = QLabel(self)
        self._icon.setFixedSize(15, 15)
        self._icon.setAlignment(Qt.AlignCenter)
        top.addWidget(self._icon, 0, Qt.AlignVCenter)
        self._num = QLabel(str(self.index), self)
        self._num.setObjectName("outline_dock_num")
        self._num.setFixedWidth(20)
        self._num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        apply_text_role(self._num, TextRole.CAPTION)
        top.addWidget(self._num, 0, Qt.AlignVCenter)
        self._title = QLabel(self.title, self)
        self._title.setObjectName("outline_dock_title")
        self._title.setWordWrap(True)
        self._title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        apply_text_role(self._title, TextRole.BODY)
        top.addWidget(self._title, 1)
        self._meta = QLabel("", self)
        self._meta.setObjectName("outline_dock_meta")
        self._meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        apply_text_role(self._meta, TextRole.CAPTION)
        top.addWidget(self._meta, 0, Qt.AlignVCenter)
        root.addLayout(top)

        # 步骤/完成度细条：当前章写作进度条 + 评分短标
        bottom = QHBoxLayout()
        bottom.setContentsMargins(21, 0, 2, 0)
        bottom.setSpacing(6)
        self._bar_bg = QFrame(self)
        self._bar_bg.setObjectName("outline_dock_bar_bg")
        self._bar_bg.setFixedHeight(4)
        self._bar_fill = QFrame(self._bar_bg)
        self._bar_fill.setObjectName("outline_dock_bar_fill")
        self._bar_fill.setFixedHeight(4)
        self._bar_fill.setGeometry(0, 0, 0, 4)
        bottom.addWidget(self._bar_bg, 1)
        self._grade_label = QLabel("", self)
        self._grade_label.setObjectName("outline_dock_grade")
        apply_text_role(self._grade_label, TextRole.CAPTION)
        bottom.addWidget(self._grade_label, 0, Qt.AlignVCenter)
        root.addLayout(bottom)

        bind_theme(self, self._apply_theme)
        self._refresh()

    # ---- mouse ----------------------------------------------------------
    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)
        super().mouseReleaseEvent(event)

    # ---- state updates ---------------------------------------------------
    def set_state(self, state: str, *, chars: int | None = None) -> None:
        normalized = str(state or "pending").strip()
        if normalized not in _STATE_ICON:
            normalized = "pending"
        self._state = normalized
        if chars is not None:
            self._chars = max(0, int(chars))
        self._refresh()

    def set_stats(self, *, chars: int | None = None,
                  score: int | None = None, grade: str | None = None) -> None:
        if chars is not None:
            self._chars = max(0, int(chars))
        if score is not None:
            self._score = int(score)
        if grade is not None:
            self._grade = str(grade or "").strip() or None
        self._refresh()

    def state(self) -> str:
        return self._state

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self._refresh()

    def chars(self) -> int:
        return self._chars

    def score(self) -> int | None:
        return self._score

    # ---- internals --------------------------------------------------------
    def _refresh(self) -> None:
        theme = get_theme()
        accent = theme.text_hint
        if self._state == "running":
            accent = theme.primary
        elif self._state == "done":
            accent = theme.success
        elif self._state == "failed":
            accent = theme.error
        if self._active:
            accent = theme.primary
        icon_name = _STATE_ICON[self._state]
        self._icon.setPixmap(get_icon(icon_name, 14, accent).pixmap(14, 14))

        if self._state == "running":
            self._meta.setText(f"{self._chars:,} 字")
        elif self._state == "done":
            parts = [f"{self._chars:,} 字"]
            if self._score is not None:
                parts.append(str(self._score))
            self._meta.setText(" · ".join(parts))
        elif self._state == "failed":
            self._meta.setText("中断")
        else:
            self._meta.setText("")

        # completion bar: full when done; proportional when running.
        width = self._bar_bg.width()
        if self._state == "done":
            ratio = 1.0
        elif self._state == "running":
            ratio = 0.6
        else:
            ratio = 0.0
        self._bar_fill.setGeometry(0, 0, int(max(0, width) * ratio), 4)

        grade_color = _grade_color(theme, self._grade, self._score)
        if self._grade:
            self._grade_label.setText(self._grade)
            self._grade_label.setStyleSheet(
                f"color: {grade_color}; background: transparent; border: none;"
            )
        else:
            self._grade_label.setText(_STATE_TEXT[self._state])
            self._grade_label.setStyleSheet(
                f"color: {theme.text_hint}; background: transparent; border: none;"
            )
        self._apply_row_style(accent)

    def _apply_row_style(self, accent: str) -> None:
        theme = get_theme()
        if self._active:
            background = theme.bg_selected
            border = theme.border_focus
        elif self._state == "running":
            background = theme.bg_selected
            border = theme.border_focus
        elif self._state == "done":
            background = theme.bg_card
            border = theme.border_light
        else:
            background = theme.bg_window
            border = theme.border_light
        self.setStyleSheet(
            f"""
            QWidget#outline_dock_row {{
                background: {background};
                border: 1px solid {border};
                border-radius: {theme.radius_sm}px;
            }}
            QLabel#outline_dock_num,
            QLabel#outline_dock_title,
            QLabel#outline_dock_meta {{
                background: transparent;
                border: none;
                color: {theme.text_primary};
            }}
            QLabel#outline_dock_num {{ color: {theme.text_hint}; }}
            QLabel#outline_dock_meta {{ color: {accent}; }}
            QFrame#outline_dock_bar_bg {{
                background: {theme.bg_window};
                border: 1px solid {theme.border_light};
                border-radius: 2px;
            }}
            QFrame#outline_dock_bar_fill {{
                background: {accent};
                border: none;
                border-radius: 2px;
            }}
            """
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()

    def _apply_theme(self) -> None:
        self._refresh()


class ChapterOutlineDock(QFrame):
    """Persistent left dock listing the current outline with live progress."""

    chapter_activated = Signal(int)
    polish_part_requested = Signal(str)  # part_title the user asked to 润色整篇
    closed = Signal()
    collapse_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("chapter_outline_dock")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(264)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._rows: dict[int, _DockRow] = {}
        self._titles: list[str] = []
        # Each chapter's ancestor group title (篇/部分/卷/单元), keyed by index.
        self._part_by_index: dict[int, str] = {}
        # Ordered part names as they first appear (for group-header rebuilds).
        self._part_names: list[str] = []
        # index -> _PartHeader, for collapse state bookkeeping.
        self._part_widgets: dict[str, _PartHeader] = {}
        # Chapter indices that belong to each part.
        self._part_members: dict[str, list[int]] = {}
        self._current_index = 0
        self._total = 0
        self._collapsed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 0, 0)
        header.setSpacing(4)
        self._collapse = QToolButton(self)
        self._collapse.setObjectName("outline_dock_collapse")
        self._collapse.setToolTip("收起 / 展开目录大纲")
        self._collapse.setCursor(Qt.PointingHandCursor)
        self._collapse.setFixedSize(20, 20)
        self._collapse.clicked.connect(self.toggle_collapsed)
        header.addWidget(self._collapse, 0, Qt.AlignVCenter)
        self._heading = QLabel("目录大纲", self)
        self._heading.setObjectName("outline_dock_heading")
        apply_text_role(self._heading, TextRole.NAVIGATION_TITLE_ACTIVE)
        header.addWidget(self._heading)
        header.addStretch(1)
        root.addLayout(header)

        self._summary = QLabel("", self)
        self._summary.setObjectName("outline_dock_summary")
        self._summary.setWordWrap(True)
        apply_text_role(self._summary, TextRole.CAPTION)
        root.addWidget(self._summary)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("outline_dock_scroll")
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self._host = QWidget(self._scroll)
        self._host.setObjectName("outline_dock_host")
        self._list = QVBoxLayout(self._host)
        self._list.setContentsMargins(0, 0, 2, 0)
        self._list.setSpacing(4)
        self._list.addStretch(1)
        self._scroll.setWidget(self._host)
        root.addWidget(self._scroll, 1)

        self._empty_label = QLabel(
            "开始多章节写作后，这里会自动列出\n确认的章节目录与每章进度、评分。",
            self,
        )
        self._empty_label.setObjectName("outline_dock_empty")
        self._empty_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._empty_label.setWordWrap(True)
        apply_text_role(self._empty_label, TextRole.CAPTION)
        root.addWidget(self._empty_label)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ---- public API -------------------------------------------------------
    def set_outline(self, titles: list[str], parts: list[str] | None = None) -> None:
        """Rebuild the outline.

        ``parts`` is an optional list aligned with ``titles`` carrying each
        chapter's ancestor group (篇/部分/卷/单元) title, or ``""`` for a
        top-level chapter.  When any group is present the dock renders a
        collapsible group header between runs of chapters sharing the same
        group.  Passing ``parts=None`` behaves exactly like the flat layout.
        """
        for i in range(self._list.count() - 1, -1, -1):
            item = self._list.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()
        self._titles = [str(t or "").strip() for t in titles if str(t or "").strip()]
        self._part_by_index.clear()
        self._part_names.clear()
        self._part_widgets.clear()
        self._part_members.clear()
        self._total = len(self._titles)

        # Re-align the optional part metadata against the (possibly filtered)
        # titles; skip empty titles entirely as today.
        parts_aligned: list[str] = []
        if parts:
            cursor = 0
            for title in titles:
                if str(title or "").strip():
                    part = str(parts[cursor]) if cursor < len(parts) else ""
                    parts_aligned.append(part)
                cursor += 1

        # Assign each chapter's part (index-keyed), preserving order of first
        # appearance of each group across the filtered titles.
        if parts_aligned:
            for offset, title in enumerate(self._titles):
                index = offset + 1
                part = str(parts_aligned[offset]) if offset < len(parts_aligned) else ""
                self._part_by_index[index] = part
                if part:
                    self._part_members.setdefault(part, []).append(index)

        # Build ordered visual items: a group header when a part starts, then
        # the chapters under that part (or top-level chapters with no header).
        ordered: list[tuple[str, list[int]]] = []  # (part_name or "", [indices])
        current_group = ""
        current_indices: list[int] = []
        for index in range(1, self._total + 1):
            part = self._part_by_index.get(index, "")
            if part != current_group:
                if current_indices:
                    ordered.append((current_group, current_indices))
                current_group = part
                current_indices = []
            current_indices.append(index)
        if current_indices:
            ordered.append((current_group, current_indices))

        # Top-level ("" group) chapters have no header row; others do.
        for part_name, indices in ordered:
            if part_name:
                header = _PartHeader(part_name, self._host)
                header.set_count(len(indices))
                header.toggled.connect(lambda: self._rebuild_visibility())
                header.polish_requested.connect(
                    lambda p=part_name: self.polish_part_requested.emit(p)
                )
                self._part_widgets[part_name] = header
                self._part_names.append(part_name)
                self._list.insertWidget(self._list.count() - 1, header)
            for index in indices:
                title = self._titles[index - 1]
                row = _DockRow(index, title, self._host)
                row.clicked.connect(self.chapter_activated.emit)
                self._rows[index] = row
                self._list.insertWidget(self._list.count() - 1, row)

        self._rebuild_visibility()
        self._sync_empty()
        self._update_summary()

    def clear(self) -> None:
        self.set_outline([])

    def row(self, index: int) -> _DockRow | None:
        return self._rows.get(int(index))

    def part_widget(self, part_title: str) -> _PartHeader | None:
        return self._part_widgets.get(str(part_title or ""))

    def set_state(self, index: int, state: str, *, chars: int | None = None) -> None:
        row = self._rows.get(int(index))
        if row is not None:
            row.set_state(state, chars=chars)
        self._update_summary()

    def set_current(self, index: int) -> None:
        """Highlight *index* as the chapter currently open in the workbench."""
        self._current_index = max(0, int(index or 0))
        for row_index, row in self._rows.items():
            row.set_active(row_index == self._current_index)
        # If the active chapter lives in a collapsed group, expand it so the
        # user can always see which chapter is open.
        if self._current_index:
            part = self._part_by_index.get(self._current_index, "")
            widget = self._part_widgets.get(part)
            if widget is not None and widget.is_collapsed():
                widget.set_collapsed(False)
                self._rebuild_visibility()
        self._update_summary()

    def set_stats(self, index: int, *, chars: int | None = None,
                  score: int | None = None, grade: str | None = None) -> None:
        row = self._rows.get(int(index))
        if row is not None:
            row.set_stats(chars=chars, score=score, grade=grade)
        self._update_summary()

    def set_part_busy(self, part_title: str, busy: bool) -> None:
        widget = self._part_widgets.get(str(part_title or ""))
        if widget is not None:
            widget.set_busy(bool(busy))

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self._heading.setVisible(not self._collapsed)
        self._summary.setVisible(not self._collapsed)
        self._scroll.setVisible(not self._collapsed)
        self._empty_label.setVisible(not self._collapsed)
        self._refresh_icons()
        if self._collapsed:
            self.setFixedWidth(44)
        else:
            self.setFixedWidth(264)
        self.collapse_changed.emit()

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def outline_summary(self) -> dict[str, object]:
        done = sum(1 for row in self._rows.values() if row.state() == "done")
        failed = sum(1 for row in self._rows.values() if row.state() == "failed")
        chars = sum(row.chars() for row in self._rows.values() if row.state() == "done")
        scored = [
            row.score()
            for row in self._rows.values()
            if row.score() is not None
        ]
        return {
            "total": self._total,
            "done": done,
            "failed": failed,
            "remaining": max(0, self._total - done - failed),
            "chars": chars,
            "average_score": round(sum(scored) / len(scored)) if scored else None,
        }

    def is_part_collapsed(self, part_title: str) -> bool:
        widget = self._part_widgets.get(str(part_title or ""))
        return widget is not None and widget.is_collapsed()

    # ---- internals ---------------------------------------------------------
    def _rebuild_visibility(self) -> None:
        """Show/hide chapter rows under each group according to its collapse
        state.  Top-level chapters (no group) are always visible."""
        for part, widget in self._part_widgets.items():
            collapsed = widget.is_collapsed()
            for index in self._part_members.get(part, ()):
                row = self._rows.get(index)
                if row is not None:
                    row.setVisible(not collapsed)

    def _sync_empty(self) -> None:
        self._empty_label.setVisible(not self._rows)

    def _update_summary(self) -> None:
        summary = self.outline_summary()
        if not summary["total"]:
            self._summary.setText("")
            return
        parts = [f"进度 {summary['done']}/{summary['total']} 章"]
        if summary["chars"]:
            parts.append(f"{summary['chars']:,} 字")
        if summary["average_score"] is not None:
            parts.append(f"均分 {summary['average_score']}")
        running = [
            row for row in self._rows.values() if row.state() == "running"
        ]
        if running:
            parts.append(f"→ 正在写第 {running[0].index} 章")
        elif self._current_index:
            parts.append(f"→ 已打开第 {self._current_index} 章")
        self._summary.setText(" · ".join(parts))

    def _refresh_icons(self) -> None:
        theme = get_theme()
        self._collapse.setIcon(
            get_icon(
                "chevron-left" if not self._collapsed else "chevron-right",
                15,
                theme.text_hint,
            )
        )

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QFrame#chapter_outline_dock {{
                background: {theme.bg_window};
                border-right: 1px solid {theme.divider};
            }}
            QLabel#outline_dock_heading {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#outline_dock_summary {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
                padding: 2px 4px 4px 4px;
            }}
            QLabel#outline_dock_empty {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
                padding: 8px 4px;
            }}
            QToolButton#outline_dock_collapse {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: {theme.radius_xs}px;
            }}
            QToolButton#outline_dock_collapse:hover {{
                background: {theme.bg_hover};
                border-color: {theme.border_light};
            }}
            QScrollArea#outline_dock_scroll {{ background: transparent; border: none; }}
            QWidget#outline_dock_host {{ background: transparent; }}
            """
        )
        self._refresh_icons()


__all__ = ["ChapterOutlineDock"]
