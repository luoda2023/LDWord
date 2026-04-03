"""ContextMenu — 右键菜单控件"""

from __future__ import annotations

from typing import Callable, Optional

from src.qt_api import QAction, QCursor, QMenu, QWidget

from src.shared.ui.theme import bind_theme, get_theme


class ContextMenu(QMenu):
    """右键菜单控件，支持图标和快捷键。

    用法::

        # 基础用法
        menu = ContextMenu()
        menu.add_action("复制", callback=lambda: print("复制"))
        menu.add_action("粘贴", callback=lambda: print("粘贴"))
        menu.add_separator()
        menu.add_action("删除", callback=lambda: print("删除"))

        # 显示菜单
        menu.exec_(QCursor.pos())

        # 带图标和快捷键
        menu.add_action("保存", icon="💾", shortcut="Ctrl+S", callback=save_func)
    """

    def __init__(self, *, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        self.setStyleSheet(
            f"""
            QMenu {{
                background: {t.bg_card};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: {t.radius_md}px;
                padding: 4px;
            }}
            QMenu::item {{
                background: transparent;
                color: {t.text_primary};
                padding: 8px 32px 8px 12px;
                border-radius: {t.radius_sm}px;
                font-size: {t.font_size_md}px;
            }}
            QMenu::item:selected {{
                background: {t.bg_hover};
            }}
            QMenu::item:disabled {{
                color: {t.text_disabled};
            }}
            QMenu::separator {{
                height: 1px;
                background: {t.divider};
                margin: 4px 8px;
            }}
            QMenu::icon {{
                padding-left: 8px;
            }}
            """
        )

    def add_action(
        self,
        text: str,
        *,
        icon: str = "",
        shortcut: str = "",
        enabled: bool = True,
        callback: Optional[Callable] = None,
    ) -> QAction:
        """添加菜单项。

        Args:
            text: 菜单项文本
            icon: 图标（emoji 或文字）
            shortcut: 快捷键
            enabled: 是否启用
            callback: 点击回调函数

        Returns:
            QAction 对象
        """
        if icon:
            action = self.addAction(f"{icon}  {text}")
        else:
            action = self.addAction(text)

        if shortcut:
            action.setShortcut(shortcut)

        action.setEnabled(enabled)

        if callback:
            action.triggered.connect(callback)

        return action

    def add_separator(self) -> None:
        """添加分割线"""
        super().addSeparator()

    @staticmethod
    def show_at_cursor(menu: "ContextMenu") -> None:
        """在鼠标位置显示菜单"""
        menu.exec_(QCursor.pos())
