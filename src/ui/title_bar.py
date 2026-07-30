"""
title_bar — 自定义标题栏

模仿微信风格：~40px高度，左侧标题，右侧窗口控制按钮，可拖拽移动窗口。
颜色全部来自 theme token（bg_sidebar / text_sidebar）。
"""

from __future__ import annotations

import ctypes
import sys

from src.app_meta import APP_DISPLAY_NAME_FULL
from src.qt_api import QHBoxLayout, QLabel, QMouseEvent, QPoint, QPushButton, QSize, QSizePolicy, QWidget, Qt

from src.config.work_mode import WorkModeSpec, list_work_modes
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import get_theme, bind_theme
from src.shared.ui.tooltip import set_global_tooltip
from src.shared.ui.typography_policy import brand_font
from src.shared.ui.icons.catalog import get_app_logo, get_icon


class TitleBar(QWidget):
    """自定义标题栏 — 40px 高度，可拖拽。"""

    HEIGHT = 40
    ICON_SIZE = 14

    def __init__(
        self,
        parent_window,
        parent=None,
        bridge=None,
        work_mode_change_handler=None,
    ):
        super().__init__(parent)
        self._window = parent_window
        self._bridge = bridge
        self._work_mode_change_handler = work_mode_change_handler
        self._drag_pos: QPoint | None = None
        self._pinned = False
        self._syncing_work_mode = False

        self.setFixedHeight(self.HEIGHT)
        self.setObjectName("titlebar")
        self.setAttribute(Qt.WA_StyledBackground, True)

        # ── 布局 ──
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(0)

        # App 图标
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(24, 24)
        layout.addWidget(self._icon_label)

        layout.addSpacing(8)

        # 标题
        self._title_label = QLabel(APP_DISPLAY_NAME_FULL)
        self._title_label.setObjectName("titlebar_title")

        layout.addWidget(self._title_label)
        layout.addSpacing(16)

        self._work_mode_combo = StyledComboBox(self)
        self._work_mode_combo.setObjectName("titlebar_work_mode_combo")
        self._work_mode_combo.set_titlebar_mode(True)
        self._work_mode_combo.setFixedSize(128, 28)
        self._work_mode_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._work_mode_combo.setToolTip("选择当前工作模式。")
        for mode in list_work_modes():
            self._work_mode_combo.addItem(mode.label, mode.mode_id)
        self._work_mode_combo.currentIndexChanged.connect(self._on_work_mode_changed)
        layout.addWidget(self._work_mode_combo)

        layout.addStretch()

        # 窗口控制按钮
        self._btn_pin = self._make_btn("titlebar_pin", "置顶")
        self._btn_min = self._make_btn("titlebar_min", "最小化")
        self._btn_max = self._make_btn("titlebar_max", "最大化")
        self._btn_close = self._make_btn("titlebar_close", "关闭")

        layout.addWidget(self._btn_pin)
        layout.addWidget(self._btn_min)
        layout.addWidget(self._btn_max)
        layout.addWidget(self._btn_close)

        # 信号
        self._btn_pin.clicked.connect(self._toggle_pin)
        self._btn_min.clicked.connect(self._window.showMinimized)
        self._btn_max.clicked.connect(self._toggle_maximize)
        self._btn_close.clicked.connect(self._window.close)

        if self._bridge is not None:
            self._bridge.work_mode_changed.connect(self.set_work_mode)
            self.set_work_mode(self._bridge.current_work_mode())

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _make_btn(self, object_name: str, tooltip: str) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName(object_name)
        set_global_tooltip(btn, tooltip, placement="bottom", role="chrome")
        btn.setFixedSize(46, self.HEIGHT)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        return btn

    def set_work_mode(self, mode: WorkModeSpec | str) -> None:
        mode_id = str(getattr(mode, "mode_id", mode) or "").strip()
        index = self._work_mode_combo.findData(mode_id)
        if index < 0:
            index = self._work_mode_combo.findData("custom")
        self._syncing_work_mode = True
        try:
            self._work_mode_combo.setCurrentIndex(max(index, 0))
        finally:
            self._syncing_work_mode = False

    def _on_work_mode_changed(self, *_args) -> None:
        if self._syncing_work_mode or self._bridge is None:
            return
        mode_id = str(self._work_mode_combo.currentData() or "").strip()
        if callable(self._work_mode_change_handler):
            self._work_mode_change_handler(mode_id)
            # A rejected or failed request leaves the bridge unchanged.  Keep
            # the selector projected from that authoritative state.
            self.set_work_mode(self._bridge.current_work_mode())
            return
        self._bridge.set_current_work_mode(mode_id)

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self._update_icons()

    def _toggle_pin(self) -> None:
        self._pinned = not self._pinned
        if sys.platform == "win32":
            try:
                hwnd = int(self._window.winId())
                HWND_TOPMOST = ctypes.c_void_p(-1)
                HWND_NOTOPMOST = ctypes.c_void_p(-2)
                SWP_FLAGS = 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE
                target = HWND_TOPMOST if self._pinned else HWND_NOTOPMOST
                ctypes.windll.user32.SetWindowPos(
                    ctypes.c_void_p(hwnd), target, 0, 0, 0, 0, SWP_FLAGS
                )
            except Exception:
                # Fallback: setWindowFlags (causes brief flash)
                geo = self._window.geometry()
                flags = self._window.windowFlags()
                if self._pinned:
                    self._window.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
                else:
                    self._window.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
                self._window.setGeometry(geo)
                self._window.show()
        else:
            geo = self._window.geometry()
            flags = self._window.windowFlags()
            if self._pinned:
                self._window.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
            else:
                self._window.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
            self._window.setGeometry(geo)
            self._window.show()

        set_global_tooltip(self._btn_pin, "取消置顶" if self._pinned else "置顶", placement="bottom", role="chrome")
        self._update_icons()

    # ── 拖拽移动窗口 ──
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and not self._window.isMaximized():
            self._drag_pos = event.globalPos() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self._window.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._toggle_maximize()

    # ── 主题 ──
    def _apply_theme(self) -> None:
        t = get_theme()
        logo = get_app_logo(24)
        self._icon_label.setPixmap(logo.pixmap(24, 24))
        self._update_icons()

        self._title_label.setFont(
            brand_font(pixel_size=t.font_size_md, weight=t.font_weight_bold)
        )

        self.setStyleSheet(f"""
            #titlebar {{
                background: {t.bg_sidebar};
                border-top-left-radius: {t.shell_radius}px;
                border-top-right-radius: {t.shell_radius}px;
            }}
            #titlebar_title {{
                color: {t.text_primary};
            }}
            QPushButton {{
                background: transparent;
                border: none;
            }}
            QPushButton:hover {{
                background: {t.bg_hover};
            }}
            #titlebar_close:hover {{
                background: {t.window_close_hover_bg};
            }}
        """)

    def _update_icons(self) -> None:
        t = get_theme()
        s = self.ICON_SIZE
        color = t.text_secondary

        # Pin
        pin_color = t.primary if self._pinned else color
        self._btn_pin.setIcon(get_icon("pin", size=s, color=pin_color))

        # Minimize
        self._btn_min.setIcon(get_icon("minus", size=s, color=color))

        # Maximize / Restore
        if self._window.isMaximized():
            self._btn_max.setIcon(get_icon("copy", size=s, color=color))
            set_global_tooltip(self._btn_max, "向下还原", placement="bottom", role="chrome")
        else:
            self._btn_max.setIcon(get_icon("square", size=s, color=color))
            set_global_tooltip(self._btn_max, "最大化", placement="bottom", role="chrome")

        # Close
        self._btn_close.setIcon(get_icon("x", size=s, color=color))
