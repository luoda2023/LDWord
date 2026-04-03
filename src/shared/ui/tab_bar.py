"""TabBar — 水平标签页控件"""

from __future__ import annotations

from typing import Callable

from src.qt_api import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme


class TabBar(QWidget):
    """水平标签页控件，支持下划线指示和可关闭标签。

    用法::

        # 基础用法
        tab_bar = TabBar()
        tab_bar.add_tab("首页")
        tab_bar.add_tab("设置")
        tab_bar.tab_changed.connect(lambda idx: print(f"切换到标签 {idx}"))

        # 可关闭标签
        tab_bar = TabBar()
        tab_bar.add_tab("文档1", closable=True)
        tab_bar.tab_closed.connect(lambda idx: print(f"关闭标签 {idx}"))
    """

    tab_changed = Signal(int)  # 标签切换信号，参数为索引
    tab_closed = Signal(int)   # 标签关闭信号，参数为索引

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._tabs = []
        self._current_index = 0

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标签容器
        self._tab_container = QWidget()
        self._tab_layout = QHBoxLayout(self._tab_container)
        self._tab_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_layout.setSpacing(0)
        self._tab_layout.addStretch()

        layout.addWidget(self._tab_container)

        # 下划线指示器
        self._indicator = QWidget()
        self._indicator.setFixedHeight(2)
        layout.addWidget(self._indicator)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        self.setStyleSheet(
            f"""
            TabBar {{
                background: {t.bg_card};
                border-bottom: 1px solid {t.border_light};
            }}
            """
        )

        self._indicator.setStyleSheet(
            f"background: {t.tab_active_border};"
        )

        # 更新所有标签样式
        for i, tab_data in enumerate(self._tabs):
            self._update_tab_style(i)

    def add_tab(
        self,
        text: str,
        *,
        closable: bool = False,
        data: any = None
    ) -> int:
        """添加标签。

        Args:
            text: 标签文本
            closable: 是否可关闭
            data: 关联数据

        Returns:
            标签索引
        """
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        tab_layout.setContentsMargins(16, 8, 16, 8)
        tab_layout.setSpacing(8)

        # 标签按钮
        tab_btn = QPushButton(text)
        tab_btn.setCursor(Qt.PointingHandCursor)
        tab_btn.clicked.connect(
            lambda checked, idx=len(self._tabs): self.set_current_index(idx)
        )
        tab_layout.addWidget(tab_btn)

        # 关闭按钮
        close_btn = None
        if closable:
            close_btn = QPushButton("×")
            close_btn.setFixedSize(16, 16)
            close_btn.setCursor(Qt.PointingHandCursor)
            close_btn.clicked.connect(
                lambda checked, idx=len(self._tabs): self._on_tab_close(idx)
            )
            tab_layout.addWidget(close_btn)

        # 插入到 stretch 之前
        self._tab_layout.insertWidget(len(self._tabs), tab_widget)

        # 保存标签数据
        self._tabs.append({
            "widget": tab_widget,
            "button": tab_btn,
            "close_button": close_btn,
            "text": text,
            "data": data,
        })

        self._update_tab_style(len(self._tabs) - 1)
        return len(self._tabs) - 1

    def remove_tab(self, index: int) -> None:
        """移除标签"""
        if 0 <= index < len(self._tabs):
            tab_data = self._tabs.pop(index)
            tab_data["widget"].deleteLater()

            # 调整当前索引
            if self._current_index >= len(self._tabs) and len(self._tabs) > 0:
                self.set_current_index(len(self._tabs) - 1)
            elif len(self._tabs) == 0:
                self._current_index = -1

    def set_current_index(self, index: int) -> None:
        """设置当前标签"""
        if 0 <= index < len(self._tabs) and index != self._current_index:
            old_index = self._current_index
            self._current_index = index

            # 更新样式
            if 0 <= old_index < len(self._tabs):
                self._update_tab_style(old_index)
            self._update_tab_style(index)

            self.tab_changed.emit(index)

    def current_index(self) -> int:
        """获取当前标签索引"""
        return self._current_index

    def _update_tab_style(self, index: int) -> None:
        """更新标签样式"""
        if not (0 <= index < len(self._tabs)):
            return

        t = get_theme()
        tab_data = self._tabs[index]
        is_active = index == self._current_index

        # 标签按钮样式
        tab_data["button"].setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {t.tab_active_text if is_active else t.tab_inactive_text};
                font-size: {t.font_size_md}px;
                font-weight: {500 if is_active else 400};
                padding: 0;
            }}
            QPushButton:hover {{
                color: {t.tab_active_text};
            }}
            """
        )

        # 关闭按钮样式
        if tab_data["close_button"]:
            tab_data["close_button"].setStyleSheet(
                f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {t.text_hint};
                    font-size: 18px;
                    font-weight: bold;
                    padding: 0;
                }}
                QPushButton:hover {{
                    background: {t.bg_hover};
                    border-radius: 8px;
                    color: {t.text_primary};
                }}
                """
            )

    def _on_tab_close(self, index: int) -> None:
        """处理标签关闭"""
        self.tab_closed.emit(index)
        self.remove_tab(index)

    def count(self) -> int:
        """获取标签数量"""
        return len(self._tabs)

    def tab_text(self, index: int) -> str:
        """获取标签文本"""
        if 0 <= index < len(self._tabs):
            return self._tabs[index]["text"]
        return ""

    def tab_data(self, index: int) -> any:
        """获取标签关联数据"""
        if 0 <= index < len(self._tabs):
            return self._tabs[index]["data"]
        return None
