"""
sidebar — 侧边图标导航栏

固定宽 48px，Lucide liner SVG 图标，主题色驱动。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.qt_api import QButtonGroup, QPushButton, QSize, QVBoxLayout, QWidget, Signal, Qt

from src.shared.ui.theme import get_theme, bind_theme
from src.shared.ui.tooltip import set_global_tooltip
from src.ui.icons.catalog import get_icon, SIDEBAR_ICONS
from src.ui.panel_registry import MAIN_SPECS, BOTTOM_SPECS

if TYPE_CHECKING:
    from src.ui.bridge import PanelBridge


class _NavButton(QPushButton):
    """侧边栏图标按钮 — Lucide SVG + 主题色。"""

    ICON_SIZE = 20

    def __init__(self, nav_id: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.nav_id = nav_id
        self._active = False
        set_global_tooltip(self, tooltip, placement="right", role="nav", delay_ms=80)
        self.setCheckable(True)
        self.setFixedSize(40, 40)
        self.setCursor(Qt.PointingHandCursor)

    def apply_theme(self) -> None:
        active = self._active
        t = get_theme()
        icon_color = t.icon_accent if active else t.text_sidebar
        lucide_name = SIDEBAR_ICONS.get(self.nav_id, "settings")
        self.setIcon(get_icon(lucide_name, self.ICON_SIZE, icon_color))
        self.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))

        bg = t.bg_sidebar_active if active else "transparent"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: {t.radius_sm}px;
            }}
            QPushButton:hover {{
                background: {t.bg_sidebar_active};
            }}
        """)

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self.apply_theme()


class Sidebar(QWidget):
    """侧边 Lucide 图标导航栏。

    Signals:
        panel_selected(int): 面板索引变化
    """

    panel_selected = Signal(int)

    WIDTH = 48

    def __init__(self, bridge: PanelBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._active_index: int = 0
        self.setFixedWidth(self.WIDTH)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)

        self._buttons: list[_NavButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for i, spec in enumerate(MAIN_SPECS):
            btn = _NavButton(spec.id, spec.title)
            self._group.addButton(btn, i)
            self._buttons.append(btn)
            layout.addWidget(btn, 0, Qt.AlignHCenter)

        layout.addStretch()

        for i, spec in enumerate(BOTTOM_SPECS):
            idx = len(MAIN_SPECS) + i
            btn = _NavButton(spec.id, spec.title)
            self._group.addButton(btn, idx)
            self._buttons.append(btn)
            layout.addWidget(btn, 0, Qt.AlignHCenter)

        self._group.idClicked.connect(self._on_clicked)

        if self._buttons:
            self._buttons[0].setChecked(True)
            self._buttons[0].set_active(True)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _on_clicked(self, idx: int) -> None:
        old = self._active_index
        self._active_index = idx
        # 只更新变化的两按钮，不全量重建
        if old != idx:
            if 0 <= old < len(self._buttons):
                self._buttons[old].set_active(False)
            if 0 <= idx < len(self._buttons):
                self._buttons[idx].set_active(True)
        self.panel_selected.emit(idx)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(f"""
            #sidebar {{
                background: {t.bg_sidebar};
                border-bottom-left-radius: {t.shell_radius}px;
            }}
        """)
        for btn in self._buttons:
            btn.apply_theme()

    def select(self, index: int) -> None:
        """外部切换选中项。"""
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            self._on_clicked(index)
