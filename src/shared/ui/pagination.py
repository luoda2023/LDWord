"""Pagination — 页码导航控件"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QPushButton,
    QLabel,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme


class Pagination(QWidget):
    """页码导航控件。

    用法::

        # 基础用法
        pagination = Pagination(total=100, page_size=10)
        pagination.page_changed.connect(lambda page: print(f"切换到第 {page} 页"))

        # 自定义页大小
        pagination = Pagination(total=200, page_size=20)
    """

    page_changed = Signal(int)  # 页码变化信号

    def __init__(
        self,
        *,
        total: int = 0,
        page_size: int = 10,
        current: int = 1,
        parent=None,
    ):
        """初始化分页控件。

        Args:
            total: 总条目数
            page_size: 每页条目数
            current: 当前页码（从 1 开始）
            parent: 父控件
        """
        super().__init__(parent)
        self._total = total
        self._page_size = page_size
        self._current = current

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self._update_buttons()

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        # 上一页按钮
        self._prev_btn = QPushButton("‹")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.clicked.connect(self._go_prev)
        layout.addWidget(self._prev_btn)

        # 页码按钮容器
        self._page_buttons_layout = QHBoxLayout()
        self._page_buttons_layout.setSpacing(4)
        layout.addLayout(self._page_buttons_layout)

        # 下一页按钮
        self._next_btn = QPushButton("›")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.clicked.connect(self._go_next)
        layout.addWidget(self._next_btn)

        # 信息标签
        self._info_label = QLabel()
        layout.addWidget(self._info_label)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        # 导航按钮样式
        nav_btn_style = f"""
            QPushButton {{
                background: {t.bg_card};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: {t.radius_sm}px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {t.bg_hover};
                border-color: {t.border_focus};
            }}
            QPushButton:pressed {{
                background: {t.bg_selected};
            }}
            QPushButton:disabled {{
                background: {t.bg_hover};
                color: {t.text_disabled};
                border-color: {t.border_light};
            }}
        """
        self._prev_btn.setStyleSheet(nav_btn_style)
        self._next_btn.setStyleSheet(nav_btn_style)

        # 信息标签样式
        self._info_label.setStyleSheet(
            f"""
            QLabel {{
                color: {t.text_secondary};
                font-size: {t.font_size_sm}px;
                background: transparent;
                border: none;
            }}
            """
        )

    def _update_buttons(self) -> None:
        """更新页码按钮"""
        # 清空现有按钮
        while self._page_buttons_layout.count():
            item = self._page_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total_pages = self.get_total_pages()
        if total_pages == 0:
            return

        t = get_theme()

        # 计算显示的页码范围
        max_buttons = 7
        if total_pages <= max_buttons:
            pages = list(range(1, total_pages + 1))
        else:
            # 显示首页、当前页附近、尾页
            if self._current <= 4:
                pages = list(range(1, 6)) + [-1, total_pages]
            elif self._current >= total_pages - 3:
                pages = [1, -1] + list(range(total_pages - 4, total_pages + 1))
            else:
                pages = [1, -1, self._current - 1, self._current, self._current + 1, -1, total_pages]

        # 创建页码按钮
        for page in pages:
            if page == -1:
                # 省略号
                label = QLabel("...")
                label.setAlignment(Qt.AlignCenter)
                label.setFixedSize(32, 32)
                label.setStyleSheet(
                    f"""
                    QLabel {{
                        color: {t.text_hint};
                        font-size: {t.font_size_md}px;
                        background: transparent;
                        border: none;
                    }}
                    """
                )
                self._page_buttons_layout.addWidget(label)
            else:
                btn = QPushButton(str(page))
                btn.setFixedSize(32, 32)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda checked, p=page: self.set_current(p))

                is_current = page == self._current
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background: {t.primary if is_current else t.bg_card};
                        color: {t.text_on_primary if is_current else t.text_primary};
                        border: 1px solid {t.primary if is_current else t.border};
                        border-radius: {t.radius_sm}px;
                        font-size: {t.font_size_sm}px;
                        font-weight: {500 if is_current else 400};
                    }}
                    QPushButton:hover {{
                        background: {t.primary_hover if is_current else t.bg_hover};
                        border-color: {t.primary_hover if is_current else t.border_focus};
                    }}
                    """
                )
                self._page_buttons_layout.addWidget(btn)

        # 更新导航按钮状态
        self._prev_btn.setEnabled(self._current > 1)
        self._next_btn.setEnabled(self._current < total_pages)

        # 更新信息标签
        start = (self._current - 1) * self._page_size + 1
        end = min(self._current * self._page_size, self._total)
        self._info_label.setText(f"{start}-{end} / {self._total}")

    def _go_prev(self) -> None:
        """上一页"""
        if self._current > 1:
            self.set_current(self._current - 1)

    def _go_next(self) -> None:
        """下一页"""
        if self._current < self.get_total_pages():
            self.set_current(self._current + 1)

    def set_current(self, page: int) -> None:
        """设置当前页"""
        total_pages = self.get_total_pages()
        if 1 <= page <= total_pages and page != self._current:
            self._current = page
            self._update_buttons()
            self.page_changed.emit(page)

    def get_current(self) -> int:
        """获取当前页"""
        return self._current

    def set_total(self, total: int) -> None:
        """设置总条目数"""
        self._total = total
        self._current = 1
        self._update_buttons()

    def get_total_pages(self) -> int:
        """获取总页数"""
        if self._page_size == 0:
            return 0
        return (self._total + self._page_size - 1) // self._page_size
