"""CommandPalette — Ctrl+K 全局命令/搜索面板"""

from __future__ import annotations

from typing import Callable

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.divider import Divider
from src.shared.ui.input_metrics import build_input_editor_stylesheet, configure_input_line_edit
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


class CommandPalette(QWidget):
    """Ctrl+K 全局命令 / 搜索面板，浮层弹出。

    用法::

        palette = CommandPalette(parent=main_window)
        palette.add_command("打开文件",  shortcut="Ctrl+O", callback=open_file)
        palette.add_command("切换主题",  callback=toggle_theme)
        palette.add_command("导出 PDF",  callback=export_pdf)

        # 弹出（通常绑定到 Ctrl+K 快捷键）
        palette.toggle()
    """

    command_executed = Signal(str)   # 执行命令，参数为命令名

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._commands: list[dict] = []       # {name, shortcut, callback, visible}

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self.hide()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        # 半透明遮罩背景
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        # 实际面板
        self._panel = QWidget()
        self._panel.setFixedWidth(560)
        panel_l = QVBoxLayout(self._panel)
        panel_l.setContentsMargins(0, 0, 0, 0)
        panel_l.setSpacing(0)

        # 搜索框
        search_row = QHBoxLayout()
        search_row.setContentsMargins(12, 10, 12, 10)
        self._search_icon = QLabel()
        self._search_icon.setFixedWidth(24)
        self._search_icon.setAlignment(Qt.AlignCenter)
        search_row.addWidget(self._search_icon)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索命令...")
        self._search_edit.textChanged.connect(self._filter)
        self._search_edit.returnPressed.connect(self._execute_first)
        search_row.addWidget(self._search_edit)
        panel_l.addLayout(search_row)

        panel_l.addWidget(Divider())

        # 结果列表
        self._list = QListWidget()
        self._list.setFrameShape(QListWidget.NoFrame)
        self._list.itemActivated.connect(self._on_item_activated)
        panel_l.addWidget(self._list)

        outer.addSpacing(80)
        outer.addWidget(self._panel, 0, Qt.AlignHCenter)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(f"background: {t.overlay};")
        self._panel.setStyleSheet(
            f"""
            QWidget {{
                background: {t.bg_card};
                border: 1px solid {t.border};
                border-radius: {t.radius_lg}px;
            }}
            """
        )
        configure_input_line_edit(
            self._search_edit,
            t,
            stylesheet=build_input_editor_stylesheet(t, font_size=t.font_size_lg),
        )
        self._search_icon.setPixmap(
            get_icon("search", 16, t.icon_secondary).pixmap(16, 16)
        )
        self._search_icon.setStyleSheet(
            "background:transparent;border:none;"
        )
        self._list.setStyleSheet(
            f"""
            QListWidget {{
                background: transparent; border: none;
                color: {t.text_primary}; font-size: {t.font_size_md}px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px 16px;
                border-radius: {t.radius_sm}px;
            }}
            QListWidget::item:selected, QListWidget::item:hover {{
                background: {t.bg_hover};
            }}
            """
        )

    # ── 交互 ─────────────────────────────────────────────────────────────────

    def _filter(self, keyword: str) -> None:
        kw = keyword.strip().lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(kw not in item.text().lower())

    def _execute_first(self) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not item.isHidden():
                self._on_item_activated(item)
                return

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.UserRole)
        for cmd in self._commands:
            if cmd["name"] == name and cmd.get("callback"):
                cmd["callback"]()
                break
        self.command_executed.emit(name)
        self.hide()
        self._search_edit.clear()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.hide()
            self._search_edit.clear()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        # 点击遮罩区域关闭
        if not self._panel.geometry().contains(event.pos()):
            self.hide()
            self._search_edit.clear()

    # ── 公共 API ─────────────────────────────────────────────────────────────

    def add_command(
        self,
        name: str,
        *,
        shortcut: str = "",
        callback: Callable | None = None,
    ) -> None:
        """注册命令"""
        self._commands.append(
            {"name": name, "shortcut": shortcut, "callback": callback}
        )
        display = f"{name}   {shortcut}" if shortcut else name
        item = QListWidgetItem(display)
        item.setData(Qt.UserRole, name)
        self._list.addItem(item)

    def toggle(self) -> None:
        """切换显示/隐藏"""
        if self.isVisible():
            self.hide()
            self._search_edit.clear()
        else:
            if self.parent():
                self.setGeometry(self.parent().rect())
            self.show()
            self.raise_()
            self._search_edit.setFocus()
