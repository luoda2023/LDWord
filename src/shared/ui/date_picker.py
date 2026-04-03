"""DatePicker — 日期选择控件"""

from __future__ import annotations

import calendar
import warnings
from datetime import date, datetime

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


class DatePicker(QWidget):
    """日期选择控件，含弹出日历面板和年月导航。

    用法::

        picker = DatePicker()
        picker.date_selected.connect(lambda d: print(d.isoformat()))

        # 预设日期
        picker = DatePicker(value=date.today())
    """

    date_selected = Signal(object)   # 选中日期，参数为 datetime.date

    def __init__(self, *, value: date | None = None, parent=None):
        super().__init__(parent)
        self._selected = value or date.today()
        self._view_year = self._selected.year
        self._view_month = self._selected.month

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 触发按钮
        self._trigger_btn = QPushButton()
        self._trigger_btn.setCursor(Qt.PointingHandCursor)
        self._trigger_btn.clicked.connect(self._toggle_popup)
        layout.addWidget(self._trigger_btn)

        # 弹出面板（默认隐藏）
        self._popup = QWidget(self, Qt.Popup)
        self._popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(8, 8, 8, 8)
        popup_layout.setSpacing(4)

        # 月份导航
        nav = QHBoxLayout()
        self._prev_month_btn = QPushButton("‹")
        self._prev_month_btn.setFixedSize(28, 28)
        self._prev_month_btn.clicked.connect(self._go_prev_month)
        nav.addWidget(self._prev_month_btn)

        self._month_label = QLabel()
        self._month_label.setAlignment(Qt.AlignCenter)
        nav.addWidget(self._month_label, 1)

        self._next_month_btn = QPushButton("›")
        self._next_month_btn.setFixedSize(28, 28)
        self._next_month_btn.clicked.connect(self._go_next_month)
        nav.addWidget(self._next_month_btn)
        popup_layout.addLayout(nav)

        # 星期头
        week_header = QHBoxLayout()
        week_header.setSpacing(0)
        for d in ["日", "一", "二", "三", "四", "五", "六"]:
            lbl = QLabel(d)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(32, 24)
            week_header.addWidget(lbl)
        popup_layout.addLayout(week_header)

        # 日期网格
        self._grid = QGridLayout()
        self._grid.setSpacing(2)
        popup_layout.addLayout(self._grid)

        self._day_btns: list[QPushButton] = []
        for _ in range(42):           # 6 行 × 7 列
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.PointingHandCursor)
            self._grid.addWidget(btn, _ // 7, _ % 7)
            self._day_btns.append(btn)

        self._refresh_calendar()
        self._update_trigger_text()

    # ── 渲染 ─────────────────────────────────────────────────────────────────

    def _refresh_calendar(self) -> None:
        """重绘当月日历"""
        t = get_theme()
        today = date.today()
        self._month_label.setText(
            f"{self._view_year} 年 {self._view_month} 月"
        )

        # calendar.monthcalendar 返回 [[周一..周日], ...], 0 表示不属于本月
        # 我们要日历从周日开始，先获取 Mon-first 然后旋转
        weeks_mon = calendar.monthcalendar(self._view_year, self._view_month)
        # 转成 Sun-first
        days: list[int] = []
        first_weekday = date(self._view_year, self._view_month, 1).weekday()  # 0=Mon
        first_col = (first_weekday + 1) % 7          # 0=Sun
        month_days = calendar.monthrange(self._view_year, self._view_month)[1]
        days = [0] * first_col + list(range(1, month_days + 1))
        days += [0] * (42 - len(days))

        for idx, btn in enumerate(self._day_btns):
            d = days[idx]
            if d == 0:
                btn.setText("")
                btn.setEnabled(False)
                btn.setStyleSheet("background:transparent;border:none;")
            else:
                btn.setText(str(d))
                btn.setEnabled(True)
                cur_date = date(self._view_year, self._view_month, d)
                is_selected = (cur_date == self._selected)
                is_today = (cur_date == today)
                is_weekend = (idx % 7 == 0)   # 周日

                bg = t.primary if is_selected else (
                    t.primary_light if is_today else "transparent"
                )
                fg = t.text_on_primary if is_selected else (
                    t.primary if is_today else
                    (t.error if is_weekend else t.text_primary)
                )
                border = f"1px solid {t.primary}" if is_today and not is_selected else "none"
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background: {bg};
                        color: {fg};
                        border: {border};
                        border-radius: 16px;
                        font-size: {t.font_size_sm}px;
                        font-weight: {'600' if is_selected or is_today else '400'};
                    }}
                    QPushButton:hover {{
                        background: {t.bg_hover if not is_selected else t.primary_hover};
                    }}
                    """
                )
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    try:
                        btn.clicked.disconnect()
                    except (RuntimeError, TypeError):
                        pass
                btn.clicked.connect(
                    lambda _, _d=d: self._on_day_clicked(_d)
                )

    def _apply_theme(self) -> None:
        t = get_theme()
        self._trigger_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {t.bg_input};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: {t.input_radius}px;
                padding: 4px 10px;
                font-size: {t.font_size_md}px;
                text-align: left;
            }}
            QPushButton:hover {{ border-color: {t.border_focus}; }}
            """
        )
        self._popup.setStyleSheet(
            f"""
            QWidget {{
                background: {t.bg_card};
                border: 1px solid {t.border};
                border-radius: {t.radius_md}px;
            }}
            """
        )
        nav_style = f"""
            QPushButton {{
                background: transparent; border: none;
                color: {t.text_primary}; font-size: 18px; font-weight: bold;
                border-radius: 14px;
            }}
            QPushButton:hover {{ background: {t.bg_hover}; }}
        """
        self._prev_month_btn.setStyleSheet(nav_style)
        self._next_month_btn.setStyleSheet(nav_style)
        self._month_label.setStyleSheet(
            f"color:{t.text_primary};font-size:{t.font_size_md}px;"
            f"font-weight:600;background:transparent;border:none;"
        )
        self._refresh_calendar()

    def _update_trigger_text(self) -> None:
        self._trigger_btn.setText(
            f"📅  {self._selected.strftime('%Y-%m-%d')}"
        )

    # ── 交互 ─────────────────────────────────────────────────────────────────

    def _toggle_popup(self) -> None:
        if self._popup.isVisible():
            self._popup.hide()
        else:
            pos = self.mapToGlobal(self._trigger_btn.rect().bottomLeft())
            self._popup.move(pos)
            self._popup.show()

    def _go_prev_month(self) -> None:
        if self._view_month == 1:
            self._view_month = 12
            self._view_year -= 1
        else:
            self._view_month -= 1
        self._refresh_calendar()

    def _go_next_month(self) -> None:
        if self._view_month == 12:
            self._view_month = 1
            self._view_year += 1
        else:
            self._view_month += 1
        self._refresh_calendar()

    def _on_day_clicked(self, day: int) -> None:
        self._selected = date(self._view_year, self._view_month, day)
        self._update_trigger_text()
        self._refresh_calendar()
        self._popup.hide()
        self.date_selected.emit(self._selected)

    # ── 公共 API ─────────────────────────────────────────────────────────────

    def get_date(self) -> date:
        return self._selected

    def set_date(self, d: date) -> None:
        self._selected = d
        self._view_year = d.year
        self._view_month = d.month
        self._update_trigger_text()
        self._refresh_calendar()
