"""DataTable — 数据表格控件"""

from __future__ import annotations

from typing import List, Any

from src.qt_api import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme


def fit_table_height_to_contents(
    table: QTableWidget,
    *,
    empty_row_height: int = 38,
) -> int:
    """Size a non-scrolling table to its header and visible rows."""

    header = table.horizontalHeader()
    header_height = max(header.height(), header.sizeHint().height())
    body_height = sum(table.rowHeight(row) for row in range(table.rowCount()))
    height = (
        header_height
        + (body_height or max(0, int(empty_row_height)))
        + table.frameWidth() * 2
    )
    table.setMinimumHeight(height)
    table.setMaximumHeight(height)
    table.updateGeometry()
    return height


class DataTable(QTableWidget):
    """数据表格控件，支持列排序、行选中、固定列。

    用法::

        # 基础用法
        table = DataTable()
        table.set_columns(["姓名", "年龄", "城市"])
        table.add_row(["张三", "25", "北京"])
        table.add_row(["李四", "30", "上海"])

        # 监听选中
        table.row_selected.connect(lambda row: print(f"选中行 {row}"))
    """

    row_selected = Signal(int)  # 行选中信号
    row_double_clicked = Signal(int)  # 行双击信号

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._data = []

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

        # 连接信号
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        # 表格设置
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)

        # 表头设置
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setHighlightSections(False)

        # 启用排序
        self.setSortingEnabled(True)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        self.setStyleSheet(
            f"""
            QTableWidget {{
                background: {t.bg_card};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: {t.radius_sm}px;
                gridline-color: {t.border_light};
                selection-background-color: {t.bg_selected};
                selection-color: {t.text_primary};
                alternate-background-color: {t.bg_window};
            }}
            QTableWidget::item {{
                padding: 8px;
                border: none;
            }}
            QTableWidget::item:hover {{
                background: {t.bg_hover};
            }}
            QHeaderView::section {{
                background: {t.bg_window};
                color: {t.text_primary};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.border};
                font-weight: {t.font_weight_emphasis};
            }}
            QHeaderView::section:hover {{
                background: {t.bg_hover};
            }}
            QScrollBar:vertical {{
                background: {t.scrollbar_track};
                width: 10px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {t.scrollbar_thumb};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t.scrollbar_thumb_hover};
            }}
            QScrollBar:horizontal {{
                background: {t.scrollbar_track};
                height: 10px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background: {t.scrollbar_thumb};
                border-radius: 5px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {t.scrollbar_thumb_hover};
            }}
            """
        )

    def set_columns(self, columns: List[str]) -> None:
        """设置列标题"""
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)

    def add_row(self, row_data: List[Any]) -> int:
        """添加行数据"""
        row_index = self.rowCount()
        self.insertRow(row_index)

        for col, value in enumerate(row_data):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 禁止编辑
            self.setItem(row_index, col, item)

        self._data.append(row_data)
        return row_index

    def set_data(self, data: List[List[Any]]) -> None:
        """设置所有数据"""
        self.clear_data()
        for row_data in data:
            self.add_row(row_data)

    def clear_data(self) -> None:
        """清空数据"""
        self.setRowCount(0)
        self._data.clear()

    def get_selected_row(self) -> int:
        """获取选中的行索引"""
        selected = self.selectedIndexes()
        if selected:
            return selected[0].row()
        return -1

    def get_row_data(self, row: int) -> List[Any]:
        """获取指定行的数据"""
        if 0 <= row < len(self._data):
            return self._data[row]
        return []

    def _on_selection_changed(self) -> None:
        """处理选中变化"""
        row = self.get_selected_row()
        if row >= 0:
            self.row_selected.emit(row)

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        """处理双击"""
        if item:
            self.row_double_clicked.emit(item.row())
