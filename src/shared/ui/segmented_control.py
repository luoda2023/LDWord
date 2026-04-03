"""SegmentedControl — 分段选择器控件"""

from __future__ import annotations

from src.qt_api import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme


class SegmentedControl(QWidget):
    """分段选择器，胶囊样式，支持单选。

    用法::

        # 基础用法
        segmented = SegmentedControl()
        segmented.add_segment("选项1")
        segmented.add_segment("选项2")
        segmented.add_segment("选项3")
        segmented.current_changed.connect(lambda idx: print(f"选中 {idx}"))

        # 预设选项
        segmented = SegmentedControl(options=["日", "周", "月", "年"])
    """

    current_changed = Signal(int)  # 当前选项变化信号

    def __init__(self, *, options: list = None, parent=None):
        """初始化分段选择器。

        Args:
            options: 选项列表
            parent: 父控件
        """
        super().__init__(parent)
        self._segments = []
        self._current_index = 0

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

        # 添加预设选项
        if options:
            for option in options:
                self.add_segment(option)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(0)

        # 按钮组
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        self.setStyleSheet(
            f"""
            SegmentedControl {{
                background: {t.bg_hover};
                border-radius: {t.radius_full}px;
            }}
            """
        )

        # 更新所有按钮样式
        for i, btn in enumerate(self._segments):
            self._update_button_style(i)

    def add_segment(self, text: str, data: any = None) -> int:
        """添加分段。

        Args:
            text: 分段文本
            data: 关联数据

        Returns:
            分段索引
        """
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("data", data)

        index = len(self._segments)
        btn.clicked.connect(lambda: self.set_current_index(index))

        self._button_group.addButton(btn, index)
        self._layout.addWidget(btn)
        self._segments.append(btn)

        # 第一个按钮默认选中
        if index == 0:
            btn.setChecked(True)

        self._update_button_style(index)
        return index

    def set_current_index(self, index: int) -> None:
        """设置当前选中的分段"""
        if 0 <= index < len(self._segments) and index != self._current_index:
            old_index = self._current_index
            self._current_index = index

            self._segments[index].setChecked(True)

            # 更新样式
            self._update_button_style(old_index)
            self._update_button_style(index)

            self.current_changed.emit(index)

    def current_index(self) -> int:
        """获取当前选中的分段索引"""
        return self._current_index

    def current_text(self) -> str:
        """获取当前选中的分段文本"""
        if 0 <= self._current_index < len(self._segments):
            return self._segments[self._current_index].text()
        return ""

    def current_data(self) -> any:
        """获取当前选中的分段关联数据"""
        if 0 <= self._current_index < len(self._segments):
            return self._segments[self._current_index].property("data")
        return None

    def _update_button_style(self, index: int) -> None:
        """更新按钮样式"""
        if not (0 <= index < len(self._segments)):
            return

        t = get_theme()
        btn = self._segments[index]
        is_checked = btn.isChecked()

        btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {t.primary if is_checked else 'transparent'};
                color: {t.text_on_primary if is_checked else t.text_secondary};
                border: none;
                border-radius: {t.radius_full}px;
                padding: {t.button_padding_y}px {t.button_padding_x}px;
                font-size: {t.font_size_sm}px;
                font-weight: {500 if is_checked else 400};
                min-height: 28px;
            }}
            QPushButton:hover {{
                background: {t.primary_hover if is_checked else t.bg_selected};
                color: {t.text_on_primary if is_checked else t.text_primary};
            }}
            QPushButton:pressed {{
                background: {t.primary_pressed if is_checked else t.bg_hover};
            }}
            """
        )

    def count(self) -> int:
        """获取分段数量"""
        return len(self._segments)

    def segment_text(self, index: int) -> str:
        """获取指定分段的文本"""
        if 0 <= index < len(self._segments):
            return self._segments[index].text()
        return ""
