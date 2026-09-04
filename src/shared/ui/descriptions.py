"""Descriptions — 键值对描述列表控件"""

from __future__ import annotations

from typing import List, Tuple

from src.qt_api import (
    QGridLayout,
    QLabel,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.divider import Divider


class Descriptions(QWidget):
    """键值对描述列表，用于展示详细信息。

    用法::

        # 基础用法
        desc = Descriptions()
        desc.add_item("姓名", "张三")
        desc.add_item("年龄", "25")
        desc.add_item("城市", "北京")

        # 批量设置
        desc = Descriptions(items=[
            ("姓名", "张三"),
            ("年龄", "25"),
            ("城市", "北京"),
        ])
    """

    def __init__(self, *, items: List[Tuple[str, str]] = None, parent=None):
        """初始化描述列表。

        Args:
            items: 键值对列表 [(key, value), ...]
            parent: 父控件
        """
        super().__init__(parent)
        self._items = []

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

        # 添加预设项
        if items:
            for key, value in items:
                self.add_item(key, value)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)
        self._layout.setColumnStretch(1, 1)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        self.setStyleSheet(
            """
            Descriptions {
                background: transparent;
            }
            """
        )

        # 更新所有标签样式
        for key_label, value_label, _ in self._items:
            key_label.setStyleSheet(
                f"""
                QLabel {{
                    color: {t.text_secondary};
                    font-size: {t.font_size_md}px;
                    font-weight: {t.font_weight_medium};
                    background: transparent;
                    border: none;
                }}
                """
            )
            value_label.setStyleSheet(
                f"""
                QLabel {{
                    color: {t.text_primary};
                    font-size: {t.font_size_md}px;
                    background: transparent;
                    border: none;
                }}
                """
            )

    def add_item(self, key: str, value: str) -> None:
        """添加键值对"""
        row = len(self._items)

        # 键标签
        key_label = QLabel(key + ":")
        key_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self._layout.addWidget(key_label, row, 0)

        # 值标签
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        value_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._layout.addWidget(value_label, row, 1)

        # 分割线（最后一项不添加）
        divider = None
        if row > 0:
            divider = Divider()
            self._layout.addWidget(divider, row, 0, 1, 2)

        self._items.append((key_label, value_label, divider))
        self._apply_theme()

    def set_items(self, items: List[Tuple[str, str]]) -> None:
        """批量设置键值对"""
        self.clear()
        for key, value in items:
            self.add_item(key, value)

    def clear(self) -> None:
        """清空所有项"""
        for key_label, value_label, divider in self._items:
            key_label.deleteLater()
            value_label.deleteLater()
            if divider:
                divider.deleteLater()
        self._items.clear()

    def update_value(self, key: str, value: str) -> bool:
        """更新指定键的值"""
        for key_label, value_label, _ in self._items:
            if key_label.text() == key + ":":
                value_label.setText(value)
                return True
        return False

    def get_value(self, key: str) -> str:
        """获取指定键的值"""
        for key_label, value_label, _ in self._items:
            if key_label.text() == key + ":":
                return value_label.text()
        return ""
