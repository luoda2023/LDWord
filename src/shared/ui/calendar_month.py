"""CalendarMonth — 月视图日历控件"""

from __future__ import annotations

import calendar
import warnings
from datetime import date

from src.qt_api import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme


class CalendarMonth(QWidget):
    """月视图日历，支持日期标记和事件圆点。

    用法::

        cal = CalendarMonth()
        cal.date_clicked.connect(lambda d: print(d))
        cal.mark_date(date(2026, 4, 5), color="#FF4D4F")  # 标记日期
    """

    date_clicked = Signal(object)    # 点击日期，参数为 datetime.date

    def __init__(self, *, value: date | None = None, parent=None):
        super().__init__(parent)
        self._today = date.today()
        self._view_year = (value or self._today).year
        self._view_month = (value or self._today).month
        self._selected: date | None = value
        self._marks: dict[date, str] = {}   # date -> color

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # 导航栏
        nav = QHBoxLayout()
        self._prev_btn = QPushButton("‹")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.clicked.connect(self._go_prev)
        nav.addWidget(self._prev_btn)

        self._title_lbl = QLabel()
        self._title_lbl.setAlignment(Qt.AlignCenter)
        nav.addWidget(self._title_lbl, 1)

        self._next_btn = QPushButton("›")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.clicked.connect(self._go_next)
        nav.addWidget(self._next_btn)
        root.addLayout(nav)

        # 星期头（周日起）
        week_row = QHBoxLayout()
        week_row.setSpacing(0)
        for h in ["日", "一", "二", "三", "四", "五", "六"]:
            lbl = QLabel(h)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(40, 24)
            week_row.addWidget(lbl)
        self._week_header_widgets = week_row
        root.addLayout(week_row)

        # 日期格
        self._grid = QGridLayout()
        self._grid.setSpacing(2)
        self._day_cells: list[QWidget] = []
        for i in range(42):
            cell = QWidget()
            cell_l = QVBoxLayout(cell)
            cell_l.setContentsMargins(0, 0, 0, 0)
            cell_l.setSpacing(0)
            cell.setFixedSize(40, 40)
            btn = QPushButton()
            btn.setFixedSize(36, 26)
            btn.setCursor(Qt.PointingHandCursor)
            dot = QLabel()
            dot.setFixedHeight(6)
            dot.setAlignment(Qt.AlignCenter)
            cell_l.addWidget(btn, 0, Qt.AlignCenter)
            cell_l.addWidget(dot, 0, Qt.AlignCenter)
            self._grid.addWidget(cell, i // 7, i % 7)
            cell.btn = btn
            cell.dot = dot
            self._day_cells.append(cell)
        root.addLayout(self._grid)

        self._render()

    # ── 渲染 ─────────────────────────────────────────────────────────────────

    def _render(self) -> None:
        t = get_theme()
        self._title_lbl.setText(
            f"{self._view_year} 年 {self._view_month} 月"
        )

        first_wd = date(self._view_year, self._view_month, 1).weekday()   # 0=Mon
        first_col = (first_wd + 1) % 7                                    # 0=Sun
        month_days = calendar.monthrange(self._view_year, self._view_month)[1]
        days = [0] * first_col + list(range(1, month_days + 1))
        days += [0] * (42 - len(days))

        for idx, cell in enumerate(self._day_cells):
            d = days[idx]
            btn: QPushButton = cell.btn
            dot: QLabel = cell.dot

            if d == 0:
                btn.setText("")
                btn.setEnabled(False)
                btn.setStyleSheet("background:transparent;border:none;")
                dot.setText("")
                continue

            cur = date(self._view_year, self._view_month, d)
            is_today = (cur == self._today)
            is_sel = (cur == self._selected)
            is_weekend = (idx % 7 == 0)
            mark_color = self._marks.get(cur, "")

            bg = t.primary if is_sel else ("transparent")
            fg = t.text_on_primary if is_sel else (
                t.primary if is_today else
                (t.error if is_weekend else t.text_primary)
            )
            border = f"1px solid {t.primary}" if is_today and not is_sel else "none"

            btn.setText(str(d))
            btn.setEnabled(True)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background:{bg}; color:{fg};
                    border:{border}; border-radius:13px;
                    font-size:{t.font_size_sm}px;
                    font-weight:{'600' if is_sel or is_today else '400'};
                }}
                QPushButton:hover {{ background:{t.primary_hover if is_sel else t.bg_hover}; color:{t.text_on_primary if is_sel else t.text_primary}; }}
                """
            )
            dot.setText("●" if mark_color else "")
            dot.setStyleSheet(
                f"color:{mark_color if mark_color else 'transparent'};"
                f"font-size:6px;background:transparent;border:none;"
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                try:
                    btn.clicked.disconnect()
                except (RuntimeError, TypeError):
                    pass
            btn.clicked.connect(lambda _, _d=d: self._on_day_click(_d))

    def _apply_theme(self) -> None:
        t = get_theme()
        nav_s = (
            f"QPushButton{{background:transparent;border:none;"
            f"color:{t.text_primary};font-size:18px;font-weight:bold;border-radius:16px;}}"
            f"QPushButton:hover{{background:{t.bg_hover};}}"
        )
        self._prev_btn.setStyleSheet(nav_s)
        self._next_btn.setStyleSheet(nav_s)
        self._title_lbl.setStyleSheet(
            f"color:{t.text_primary};font-size:{t.font_size_md}px;"
            f"font-weight:600;background:transparent;border:none;"
        )
        self._render()

    # ── 交互 ─────────────────────────────────────────────────────────────────

    def _go_prev(self) -> None:
        if self._view_month == 1:
            self._view_month = 12
            self._view_year -= 1
        else:
            self._view_month -= 1
        self._render()

    def _go_next(self) -> None:
        if self._view_month == 12:
            self._view_month = 1
            self._view_year += 1
        else:
            self._view_month += 1
        self._render()

    def _on_day_click(self, day: int) -> None:
        self._selected = date(self._view_year, self._view_month, day)
        self._render()
        self.date_clicked.emit(self._selected)

    # ── 公共 API ─────────────────────────────────────────────────────────────

    def mark_date(self, d: date, color: str = "") -> None:
        """标记日期，显示小圆点。color 为空则清除标记。"""
        if color:
            self._marks[d] = color
        else:
            self._marks.pop(d, None)
        self._render()

    def set_view(self, year: int, month: int) -> None:
        self._view_year = year
        self._view_month = month
        self._render()

    def get_selected(self) -> date | None:
        return self._selected
