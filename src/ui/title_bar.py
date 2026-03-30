"""
title_bar — 自定义标题栏

模仿微信风格：~40px高度，左侧标题，右侧窗口控制按钮，可拖拽移动窗口。
颜色全部来自 theme token（bg_sidebar / text_sidebar）。
"""

from __future__ import annotations

from src.qt_api import QFont, QHBoxLayout, QLabel, QMouseEvent, QPoint, QPushButton, QSizePolicy, QWidget, Qt

from src.shared.ui.theme import get_theme, bind_theme
from src.ui.icons.catalog import get_app_logo


class TitleBar(QWidget):
    """自定义标题栏 — 40px 高度，可拖拽。"""

    HEIGHT = 40

    def __init__(self, parent_window, parent=None):
        super().__init__(parent)
        self._window = parent_window
        self._drag_pos: QPoint | None = None

        self.setFixedHeight(self.HEIGHT)
        self.setObjectName("titlebar")
        self.setAttribute(Qt.WA_StyledBackground, True)

        # ── 布局 ──
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(8)

        # App 图标
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(24, 24)
        layout.addWidget(self._icon_label)

        # 标题
        self._title_label = QLabel("Lark Formatter V1.0")
        self._title_label.setObjectName("titlebar_title")

        layout.addWidget(self._title_label)
        layout.addStretch()

        # 窗口控制按钮
        self._btn_min = self._make_btn("minimize", "—", "最小化")
        self._btn_max = self._make_btn("maximize", "☐", "最大化")
        self._btn_close = self._make_btn("close", "✕", "关闭")
        self._btn_close.setObjectName("titlebar_close")

        layout.addWidget(self._btn_min)
        layout.addWidget(self._btn_max)
        layout.addWidget(self._btn_close)

        # 信号
        self._btn_min.clicked.connect(self._window.showMinimized)
        self._btn_max.clicked.connect(self._toggle_maximize)
        self._btn_close.clicked.connect(self._window.close)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _make_btn(self, name: str, text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(46, self.HEIGHT)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
            self._btn_max.setText("☐")
            self._btn_max.setToolTip("最大化")
        else:
            self._window.showMaximized()
            self._btn_max.setText("❐")
            self._btn_max.setToolTip("向下还原")

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
        # App Logo (深蓝+浅蓝双色跟随主题)
        logo = get_app_logo(24)
        self._icon_label.setPixmap(logo.pixmap(24, 24))
        self.setStyleSheet(f"""
            #titlebar {{
                background: {t.bg_sidebar};
                border-bottom: 1px solid {t.border_light};
            }}
            #titlebar_title {{
                color: {t.text_primary};
                font-size: {t.font_size_md}px;
                font-weight: {t.font_weight_bold};
            }}
            QPushButton {{
                background: transparent;
                color: {t.text_secondary};
                border: none;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {t.bg_hover};
            }}
            #titlebar_close:hover {{
                background: {t.window_close_hover_bg};
                color: {t.window_close_hover_text};
            }}
        """)
