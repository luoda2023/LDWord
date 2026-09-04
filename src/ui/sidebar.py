"""
sidebar — 侧边导航栏（图标 / 图标+文字 双态）

- 收起态：固定 48px，仅图标，Lucide 线性图标，主题色驱动。
- 展开态：固定 176px，图标+文字。
- 顶部切换按钮：收起时显示 chevrons-right（点击展开），展开时显示 chevrons-left。
- 展开状态写入 app_data_root/ui-state.json，重启后保持。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from src.app_paths import app_data_root
from src.config.atomic_io import atomic_write_text
from src.qt_api import QButtonGroup, QPushButton, QSize, QVBoxLayout, QWidget, Signal, Qt

from src.shared.ui.theme import get_theme, bind_theme
from src.shared.ui.tooltip import disable_global_tooltip, set_global_tooltip
from src.shared.ui.typography_policy import (
    LATIN_UI_FONT_FAMILIES,
    UI_FONT_FAMILIES,
    build_font,
)
from src.shared.ui.icons.catalog import get_icon
from src.ui.panel_specs import PANEL_SPECS, PanelSpec

if TYPE_CHECKING:
    from src.ui.bridge import PanelBridge

logger = logging.getLogger(__name__)

_UI_STATE_FILE = "ui-state.json"
_UI_STATE_KEY = "sidebar_expanded"


def _read_ui_state() -> dict:
    try:
        path = app_data_root() / _UI_STATE_FILE
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except (OSError, ValueError, TypeError):
        pass
    return {}


def _write_ui_state(mutator) -> None:
    """Load ui-state, apply mutator(dict) -> dict, persist atomically."""
    try:
        state = _read_ui_state()
        result = mutator(state)
        atomic_write_text(
            app_data_root() / _UI_STATE_FILE,
            json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as exc:  # noqa: BLE001 - best-effort preference persistence
        logger.warning("Failed to persist sidebar ui-state: %s", exc)


class _NavButton(QPushButton):
    """侧边栏导航按钮 — 图标 +（展开时）文字，主题色驱动。"""

    ICON_SIZE = 20
    HEIGHT = 40
    COLLAPSED_WIDTH = 40

    def __init__(
        self,
        nav_id: str,
        tooltip: str,
        icon_name: str,
        *,
        parent=None,
    ):
        super().__init__(parent)
        self.nav_id = nav_id
        self._icon_name = icon_name
        self._active = False
        self._expanded = False
        set_global_tooltip(self, tooltip, placement="right", role="nav", delay_ms=80)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._font = build_font(
            tuple(UI_FONT_FAMILIES or LATIN_UI_FONT_FAMILIES),
            pixel_size=13,
            weight=400,
        )
        self.setFont(self._font)

    def _content_geometry(self, expanded: bool) -> None:
        """收起：正方形纯图标；展开：横向铺满、图标+文字左对齐。"""
        self._expanded = bool(expanded)
        if expanded:
            self.setFixedHeight(self.HEIGHT)
            self.setMinimumWidth(0)
            self.setMaximumWidth(1 << 20)
        else:
            self.setFixedSize(self.COLLAPSED_WIDTH, self.HEIGHT)

    def apply_theme(self) -> None:
        active = self._active
        expanded = self._expanded
        t = get_theme()
        icon_color = t.icon_accent if active else t.text_sidebar
        text_color = t.text_sidebar_active if active else t.text_sidebar
        self.setIcon(get_icon(self._icon_name, self.ICON_SIZE, icon_color))
        self.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        self.setProperty("expanded", expanded)
        bg = t.bg_sidebar_active if active else "transparent"
        radius = t.radius_sm if expanded else t.radius_sm
        align = "left" if expanded else "center"
        padding = "0 0 0 10px" if expanded else "0"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: {radius}px;
                color: {text_color};
                text-align: {align};
                padding: {padding};
            }}
            QPushButton:hover {{
                background: {t.bg_sidebar_active};
            }}
        """
        )

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self.setChecked(active)
        self.apply_theme()


class Sidebar(QWidget):
    """侧边导航栏，图标 / 图标+文字 双态。

    Signals:
        panel_selected(int): 面板索引变化
        expansion_changed(bool): 展开态变化
    """

    panel_selected = Signal(int)
    expansion_changed = Signal(bool)

    WIDTH = 48                # 收起态宽度（仅图标）
    EXPANDED_WIDTH = 176      # 展开态宽度（图标+文字）

    def __init__(
        self,
        bridge: PanelBridge,
        parent=None,
        *,
        panel_specs: tuple[PanelSpec, ...] = PANEL_SPECS,
    ):
        super().__init__(parent)
        self.bridge = bridge
        self._panel_specs = tuple(panel_specs)
        self._active_index: int = 0
        self._expanded = bool(_read_ui_state().get(_UI_STATE_KEY, False))
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._apply_width()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)

        # ── 顶部：展开 / 收起切换按钮 ──
        self._toggle_btn = _NavButton("__toggle__", "展开侧边栏", "chevrons-right")
        self._toggle_btn.setCheckable(False)
        self._toggle_btn.clicked.connect(self.toggle_expanded)
        layout.addWidget(self._toggle_btn, 0, Qt.AlignHCenter)

        self._buttons: list[_NavButton | None] = [None] * len(self._panel_specs)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for i, spec in enumerate(self._panel_specs):
            if spec.group != "main":
                continue
            btn = _NavButton(spec.id, spec.title, spec.icon)
            self._group.addButton(btn, i)
            self._buttons[i] = btn
            layout.addWidget(btn, 0, Qt.AlignHCenter)

        layout.addStretch()

        for idx, spec in enumerate(self._panel_specs):
            if spec.group != "bottom":
                continue
            btn = _NavButton(spec.id, spec.title, spec.icon)
            self._group.addButton(btn, idx)
            self._buttons[idx] = btn
            layout.addWidget(btn, 0, Qt.AlignHCenter)

        self._group.idClicked.connect(self._on_clicked)

        first_button = next((button for button in self._buttons if button), None)
        if first_button is not None:
            first_button.setChecked(True)
            first_button.set_active(True)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

        # 初始几何按已恢复的展开态应用
        self._apply_expanded_geometry(initial=True)
        # 展开态恢复后再应用一次主题：构造期的 apply_theme 早于几何设定，
        # 若省略这一步，按钮样式仍停留在“收起”态（无左对齐/无 padding），
        # 用户首次点击其它面板触发 set_active 时才被纠正，造成文字“移位”。
        self._apply_theme()

    # ── 展开/收起 ──
    @property
    def expanded(self) -> bool:
        return self._expanded

    def is_expanded(self) -> bool:
        return self._expanded

    def _apply_width(self) -> None:
        self.setFixedWidth(self.EXPANDED_WIDTH if self._expanded else self.WIDTH)

    def toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool, *, persist: bool = True) -> None:
        if self._expanded == bool(expanded):
            return
        self._expanded = bool(expanded)
        self._apply_expanded_geometry()
        self._apply_theme()
        if persist:
            _write_ui_state(
                lambda state: {**state, _UI_STATE_KEY: self._expanded}
            )
        self.expansion_changed.emit(self._expanded)

    def _apply_expanded_geometry(self, *, initial: bool = False) -> None:
        expanded = self._expanded
        self._apply_width()
        # 顶部切换按钮：图标随状态变化，宽态下补文字，避免按钮在栏内显空洞
        self._toggle_btn._content_geometry(expanded)
        tip = "收起侧边栏" if expanded else "展开侧边栏"
        self._toggle_btn.setText(tip if expanded else "")
        self._toggle_btn.setIcon(
            get_icon(
                "chevrons-left" if expanded else "chevrons-right",
                self._toggle_btn.ICON_SIZE,
                get_theme().text_sidebar,
            )
        )
        if expanded:
            # 文字已可见，无需再弹悬停提示
            disable_global_tooltip(self._toggle_btn)
        else:
            set_global_tooltip(
                self._toggle_btn,
                tip,
                placement="right",
                role="nav",
                delay_ms=80,
            )
        # 导航按钮文字显隐由样式驱动：展开显示文字、收起隐藏
        for btn in self._buttons:
            if btn is None:
                continue
            if expanded:
                btn.setText(btn.toolTip())
            else:
                btn.setText("")
            btn._content_geometry(expanded)

        # 布局对齐：收起时按钮自身 40x40 居中；展开时按钮横向铺满左对齐
        layout = self.layout()
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if isinstance(w, _NavButton):
                if expanded:
                    # 铺满整行：清掉水平对齐，允许拉伸
                    layout.setAlignment(w, Qt.AlignVCenter)
                else:
                    layout.setAlignment(w, Qt.AlignHCenter | Qt.AlignVCenter)

    def _on_clicked(self, idx: int) -> None:
        old = self._active_index
        self._active_index = idx
        if old != idx:
            if 0 <= old < len(self._buttons) and self._buttons[old] is not None:
                self._buttons[old].set_active(False)
            if 0 <= idx < len(self._buttons) and self._buttons[idx] is not None:
                self._buttons[idx].set_active(True)
        self.panel_selected.emit(idx)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(
            f"""
            #sidebar {{
                background: {t.bg_sidebar};
                border-bottom-left-radius: {t.shell_radius}px;
            }}
        """
        )
        for btn in self._buttons:
            if btn is not None:
                btn.apply_theme()
        self._toggle_btn.apply_theme()

    def select(self, index: int) -> None:
        """外部切换选中项。"""
        if 0 <= index < len(self._buttons) and self._buttons[index] is not None:
            self._buttons[index].setChecked(True)
            self._on_clicked(index)


__all__ = ["Sidebar"]
