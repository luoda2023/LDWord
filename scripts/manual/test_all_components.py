"""全量控件预览面板。

运行方式：
    cd <repository-root>
    python scripts/manual/test_all_components.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

try:
    from ._bootstrap import ensure_project_root
except ImportError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from src.qt_api import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSize,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.ui import (
    CalendarMonth,
    ChatBubble,
    CommandPalette,
    ContextMenu,
    DataTable,
    DatePicker,
    Descriptions,
    Divider,
    Drawer,
    EmptyState,
    Form,
    InlineAlert,
    MarkdownPreview,
    MessageInput,
    Pagination,
    Result,
    SegmentedControl,
    Spin,
    SplitPane,
    SurfaceCard,
    TabBar,
    TagChip,
    TextArea,
    Toast,
    Typography,
    TypingIndicator,
)
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.stepper_widget import StepperWidget
from src.shared.ui.theme import DARK, LIGHT, bind_theme, get_theme, set_theme


PAGE_ROLE = Qt.UserRole + 1
PHASE_ROLE = Qt.UserRole + 2
COMPONENT_ROLE = Qt.UserRole + 3

PHASE_COMPONENTS = [
    {
        "title": "Phase A",
        "subtitle": "基础展示",
        "summary": "排版、分割、标签与加载状态的基础控件。",
        "components": ["Typography", "Divider", "TagChip", "Spin"],
    },
    {
        "title": "Phase B",
        "subtitle": "交互核心",
        "summary": "标签页、空态、通知和文本输入等高频交互控件。",
        "components": [
            "TabBar",
            "EmptyState",
            "Toast",
            "TextArea",
            "InlineAlert",
            "SegmentedControl",
        ],
    },
    {
        "title": "Phase C",
        "subtitle": "数据与容器",
        "summary": "表格、描述、拆分容器、对话组件与流程容器控件。",
        "components": [
            "DataTable",
            "Descriptions",
            "SplitPane",
            "Pagination",
            "ContextMenu",
            "ChatBubble",
            "MessageInput",
            "TypingIndicator",
            "StepperWidget",
            "SurfaceCard",
            "RoundedSurfaceFrame",
        ],
    },
    {
        "title": "Phase D",
        "subtitle": "高级体验",
        "summary": "日期、命令面板、抽屉、结果页、Markdown 与表单控件。",
        "components": [
            "DatePicker",
            "CalendarMonth",
            "CommandPalette",
            "Drawer",
            "Result",
            "MarkdownPreview",
            "Form",
        ],
    },
]

COMPONENT_DESCRIPTIONS = {
    "Typography": "验证标题层级、正文与辅助文案在主题切换下的可读性。",
    "Divider": "验证列表、区块和说明文案之间的分割节奏。",
    "TagChip": "展示标签状态、可关闭标签和颜色语义。",
    "Spin": "展示加载指示器在不同尺寸和文案下的表现。",
    "TabBar": "验证标签切换、关闭标签和信息反馈。",
    "EmptyState": "展示空内容页面的图标、说明与主操作按钮。",
    "Toast": "统一验证信息、成功、警告与错误通知。",
    "TextArea": "验证多行输入、字数统计和最大长度。",
    "InlineAlert": "展示内联提示在四种状态下的反馈样式。",
    "SegmentedControl": "验证短切换选项与当前值反馈。",
    "DataTable": "展示多列数据、滚动与行选中回调。",
    "Descriptions": "展示键值说明列表的排版与信息密度。",
    "SplitPane": "验证左右内容拆分与拖拽尺寸调整。",
    "Pagination": "展示分页状态切换和页码反馈。",
    "ContextMenu": "演示右键菜单、图标与快捷键文案。",
    "ChatBubble": "展示用户 / 助手消息气泡的对话排版。",
    "MessageInput": "验证消息输入框、快捷键与发送回调。",
    "TypingIndicator": "展示输入中动画和动态状态。",
    "StepperWidget": "展示任务流程步骤、状态更新与视觉连线。",
    "SurfaceCard": "展示新的表面卡片容器和内容布局能力。",
    "RoundedSurfaceFrame": "展示自绘圆角表面的容器能力和主题响应。",
    "DatePicker": "展示日期选择器与选择结果反馈。",
    "CalendarMonth": "展示整月视图、事件标记和日期点击。",
    "CommandPalette": "展示 Ctrl+K 命令面板与实时执行能力。",
    "Drawer": "展示左右侧抽屉、遮罩和任意内容容器。",
    "Result": "展示成功结果页和多操作按钮布局。",
    "MarkdownPreview": "验证标题、引用、列表、代码和链接渲染。",
    "Form": "验证必填、校验、顶部告警和提交 / 取消流程。",
}

TOTAL_COMPONENTS = sum(len(phase["components"]) for phase in PHASE_COMPONENTS)


def _build_label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    return label


def _build_row(*items) -> QWidget:
    row_widget = QWidget()
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(10)
    for item in items:
        if item == "stretch":
            row_layout.addStretch()
        else:
            row_layout.addWidget(item)
    return row_widget


def _build_column(*widgets, spacing: int = 10) -> QWidget:
    column_widget = QWidget()
    column_layout = QVBoxLayout(column_widget)
    column_layout.setContentsMargins(0, 0, 0, 0)
    column_layout.setSpacing(spacing)
    for widget in widgets:
        column_layout.addWidget(widget)
    return column_widget


def _build_preview_card(title: str, description: str, content: QWidget) -> QFrame:
    card = QFrame()
    card.setObjectName("previewCard")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(14)
    layout.addWidget(_build_label(title, "previewCardTitle"))
    layout.addWidget(_build_label(description, "previewCardDescription"))
    layout.addWidget(Divider())
    layout.addWidget(content)

    return card


class AllComponentsPreviewPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._theme_group = QButtonGroup(self)
        self._nav_list = QListWidget()
        self._preview_stack = QStackedWidget()
        self._title_label = _build_label("全部新控件预览", "panelTitle")
        self._meta_label = _build_label("", "panelMeta")
        self._floating_tools: list[QWidget] = []

        self._build_shell()
        self._populate_navigation()
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def _build_shell(self) -> None:
        self.setObjectName("previewRoot")
        self.setWindowTitle("Alavette 共享 UI 新控件预览面板")
        self.resize(1380, 920)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(self._build_header_card())

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self._build_navigation_card(), 0)
        body.addWidget(self._build_content_card(), 1)
        root.addLayout(body)

    def _build_header_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("headerCard")

        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        intro = QVBoxLayout()
        intro.setContentsMargins(0, 0, 0, 0)
        intro.setSpacing(6)
        intro.addWidget(self._title_label)
        intro.addWidget(
            _build_label(
                f"左侧按 Phase 分组浏览，右侧查看对应控件示例，当前共 {TOTAL_COMPONENTS} 个新控件。",
                "panelDescription",
            )
        )
        layout.addLayout(intro, 1)

        theme_box = QVBoxLayout()
        theme_box.setContentsMargins(0, 0, 0, 0)
        theme_box.setSpacing(8)
        theme_box.addWidget(_build_label("主题切换", "themeCaption"))
        theme_row = QHBoxLayout()
        theme_row.setContentsMargins(0, 0, 0, 0)
        theme_row.setSpacing(8)
        theme_row.addWidget(self._build_theme_button("浅色主题", LIGHT))
        theme_row.addWidget(self._build_theme_button("深色主题", DARK))
        theme_box.addLayout(theme_row)
        layout.addLayout(theme_box)

        return card

    def _build_theme_button(self, text: str, theme) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        button.setObjectName(f"themeButton_{text}")
        button.clicked.connect(lambda checked, value=theme: self._switch_theme(value))
        self._theme_group.addButton(button)
        return button

    def _build_navigation_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("navCard")
        card.setFixedWidth(280)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(_build_label("Phase 导航", "navTitle"))
        layout.addWidget(_build_label("点击控件名称即可切换到对应预览页。", "navDescription"))

        self._nav_list.setObjectName("phaseNav")
        self._nav_list.setSpacing(4)
        self._nav_list.setFrameShape(QFrame.NoFrame)
        self._nav_list.currentItemChanged.connect(self._on_nav_changed)
        layout.addWidget(self._nav_list, 1)

        return card

    def _build_content_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("contentCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self._meta_label)
        layout.addWidget(Divider())
        layout.addWidget(self._preview_stack, 1)

        return card

    def _populate_navigation(self) -> None:
        first_item = None

        for phase in PHASE_COMPONENTS:
            header_item = QListWidgetItem()
            header_item.setFlags(Qt.NoItemFlags)
            header_item.setSizeHint(QSize(240, 34))
            self._nav_list.addItem(header_item)

            header_label = _build_label(
                f"{phase['title']} · {phase['subtitle']}",
                "phaseHeader",
            )
            self._nav_list.setItemWidget(header_item, header_label)

            for component in phase["components"]:
                page = self._build_component_page(phase, component)
                page_index = self._preview_stack.addWidget(page)

                item = QListWidgetItem(f"  {component}")
                item.setSizeHint(QSize(240, 40))
                item.setData(PAGE_ROLE, page_index)
                item.setData(PHASE_ROLE, phase["title"])
                item.setData(COMPONENT_ROLE, component)
                self._nav_list.addItem(item)

                if first_item is None:
                    first_item = item

        if first_item is not None:
            self._nav_list.setCurrentItem(first_item)

    def _build_component_page(self, phase: dict, component_name: str) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 20, 20, 20)
        hero_layout.setSpacing(8)
        hero_layout.addWidget(_build_label(f"{phase['title']} · {phase['subtitle']}", "heroEyebrow"))
        hero_layout.addWidget(_build_label(component_name, "heroTitle"))
        hero_layout.addWidget(_build_label(COMPONENT_DESCRIPTIONS[component_name], "heroDescription"))
        layout.addWidget(hero)

        layout.addWidget(
            _build_preview_card(
                "交互预览",
                "下面是当前控件的实时可交互示例，用来快速查看视觉和行为状态。",
                self._build_preview_content(component_name),
            )
        )
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("previewScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _build_preview_content(self, component_name: str) -> QWidget:
        builders = {
            "Typography": self._build_typography_preview,
            "Divider": self._build_divider_preview,
            "TagChip": self._build_tag_chip_preview,
            "Spin": self._build_spin_preview,
            "TabBar": self._build_tab_bar_preview,
            "EmptyState": self._build_empty_state_preview,
            "Toast": self._build_toast_preview,
            "TextArea": self._build_text_area_preview,
            "InlineAlert": self._build_inline_alert_preview,
            "SegmentedControl": self._build_segmented_control_preview,
            "DataTable": self._build_data_table_preview,
            "Descriptions": self._build_descriptions_preview,
            "SplitPane": self._build_split_pane_preview,
            "Pagination": self._build_pagination_preview,
            "ContextMenu": self._build_context_menu_preview,
            "ChatBubble": self._build_chat_bubble_preview,
            "MessageInput": self._build_message_input_preview,
            "TypingIndicator": self._build_typing_indicator_preview,
            "StepperWidget": self._build_stepper_preview,
            "SurfaceCard": self._build_surface_card_preview,
            "RoundedSurfaceFrame": self._build_rounded_surface_preview,
            "DatePicker": self._build_date_picker_preview,
            "CalendarMonth": self._build_calendar_month_preview,
            "CommandPalette": self._build_command_palette_preview,
            "Drawer": self._build_drawer_preview,
            "Result": self._build_result_preview,
            "MarkdownPreview": self._build_markdown_preview,
            "Form": self._build_form_preview,
        }
        return builders[component_name]()

    def _on_nav_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return

        page_index = current.data(PAGE_ROLE)
        if page_index is None:
            return

        component_name = current.data(COMPONENT_ROLE)
        phase_title = current.data(PHASE_ROLE)
        self._preview_stack.setCurrentIndex(page_index)
        self._meta_label.setText(f"{phase_title} · {component_name} · {COMPONENT_DESCRIPTIONS[component_name]}")

    def _switch_theme(self, theme) -> None:
        set_theme(theme)

    def _apply_theme(self) -> None:
        theme = get_theme()
        is_dark = theme == DARK

        for button in self._theme_group.buttons():
            if "浅色" in button.text():
                button.setChecked(not is_dark)
            if "深色" in button.text():
                button.setChecked(is_dark)

        self.setStyleSheet(
            f"""
            QWidget#previewRoot {{
                background: {theme.bg_window};
                color: {theme.text_primary};
            }}
            QFrame#headerCard,
            QFrame#navCard,
            QFrame#contentCard,
            QFrame#heroCard,
            QFrame#previewCard {{
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_lg}px;
            }}
            QLabel#panelTitle {{
                color: {theme.text_primary};
                font-size: {theme.font_size_xxl + 6}px;
                font-weight: {theme.font_weight_bold};
                background: transparent;
                border: none;
            }}
            QLabel#panelDescription,
            QLabel#navDescription,
            QLabel#previewCardDescription,
            QLabel#heroDescription,
            QLabel#panelMeta {{
                color: {theme.text_secondary};
                font-size: {theme.font_size_md}px;
                background: transparent;
                border: none;
            }}
            QLabel#themeCaption,
            QLabel#heroEyebrow,
            QLabel#phaseHeader {{
                color: {theme.text_hint};
                font-size: {theme.font_size_sm}px;
                font-weight: {theme.font_weight_bold};
                background: transparent;
                border: none;
            }}
            QLabel#navTitle,
            QLabel#heroTitle,
            QLabel#previewCardTitle {{
                color: {theme.text_primary};
                font-size: {theme.font_size_xl}px;
                font-weight: {theme.font_weight_bold};
                background: transparent;
                border: none;
            }}
            QLabel#panelMeta {{
                font-size: {theme.font_size_lg}px;
            }}
            QPushButton[objectName^=\"themeButton_\"] {{
                background: {theme.bg_card};
                color: {theme.text_primary};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_sm}px;
                padding: 8px 14px;
                min-width: 92px;
            }}
            QPushButton[objectName^=\"themeButton_\"]:hover {{
                background: {theme.bg_hover};
            }}
            QPushButton[objectName^=\"themeButton_\"]:checked {{
                background: {theme.primary_light};
                color: {theme.primary};
                border: 1px solid {theme.border_focus};
                font-weight: {theme.font_weight_bold};
            }}
            QListWidget#phaseNav {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget#phaseNav::item {{
                margin: 0 0 2px 0;
                padding: 10px 12px;
                border-radius: {theme.radius_sm}px;
                color: {theme.text_secondary};
            }}
            QListWidget#phaseNav::item:hover {{
                background: {theme.bg_hover};
            }}
            QListWidget#phaseNav::item:selected {{
                background: {theme.primary_light};
                color: {theme.text_primary};
                border: 1px solid {theme.border_focus};
            }}
            QScrollArea#previewScroll {{
                background: transparent;
                border: none;
            }}
            """
        )

    def _build_typography_preview(self) -> QWidget:
        return _build_column(
            Typography("H1 标题示例", variant="h1"),
            Typography("H2 区块标题示例", variant="h2"),
            Typography("H3 小节标题示例", variant="h3"),
            Typography("正文内容示例，用于验证排版层级、字重和主题切换后的可读性。", variant="body"),
            Typography("Caption 辅助说明文字", variant="caption"),
        )

    def _build_divider_preview(self) -> QWidget:
        return _build_column(
            Typography("文档设置", variant="body"),
            Divider(),
            Typography("主题配置", variant="body"),
            Divider(),
            Typography("导出结果", variant="body"),
        )

    def _build_tag_chip_preview(self) -> QWidget:
        status_label = _build_label("点击可关闭标签会触发关闭回调。", "panelDescription")
        closable = TagChip("可关闭标签", variant="primary", closable=True)
        closable.closed.connect(lambda: Toast.show_info("TagChip 已关闭"))
        return _build_column(
            _build_row(
                TagChip("默认", variant="default"),
                TagChip("主要", variant="primary"),
                TagChip("成功", variant="success"),
                TagChip("警告", variant="warning"),
                TagChip("错误", variant="error"),
                TagChip("信息", variant="info"),
                "stretch",
            ),
            _build_row(closable, status_label, "stretch"),
        )

    def _build_spin_preview(self) -> QWidget:
        return _build_row(
            Spin(tip="加载中..."),
            Spin(size=44),
            Spin(size=52, tip="同步中"),
            "stretch",
        )

    def _build_tab_bar_preview(self) -> QWidget:
        tab_bar = TabBar()
        for text in ["首页", "模板", "执行中心", "关于"]:
            tab_bar.add_tab(text, closable=(text == "关于"))
        tab_bar.tab_changed.connect(lambda index: Toast.show_info(f"切换到标签 {index + 1}"))
        return _build_column(tab_bar, _build_label("点击不同标签会弹出 Toast 提示。", "panelDescription"))

    def _build_empty_state_preview(self) -> QWidget:
        state = EmptyState(
            icon="📦",
            title="暂无预设模板",
            description="你可以先拖入一个配置文件，或者点击按钮创建第一套模板。",
            action_text="创建模板",
        )
        state.action_clicked.connect(lambda: Toast.show_success("已触发空态主操作"))
        return state

    def _build_toast_preview(self) -> QWidget:
        return _build_row(
            self._make_demo_button("Info", lambda: Toast.show_info("这是一条信息通知")),
            self._make_demo_button("Success", lambda: Toast.show_success("操作已成功完成")),
            self._make_demo_button("Warning", lambda: Toast.show_warning("请检查当前输入")),
            self._make_demo_button("Error", lambda: Toast.show_error("导出失败，请重试")),
            "stretch",
        )

    def _build_text_area_preview(self) -> QWidget:
        area = TextArea(placeholder="输入多行描述，查看字数统计和长度限制。", show_count=True, max_length=200)
        area.set_text("第一行：用于展示 TextArea。\n第二行：支持多行内容和主题切换。")
        return area

    def _build_inline_alert_preview(self) -> QWidget:
        return _build_column(
            InlineAlert("这里是信息提示，可用于说明当前状态。", variant="info", closable=True),
            InlineAlert("保存成功，配置已写入磁盘。", variant="success", closable=True),
            InlineAlert("注意：当前模板仍有 2 处待确认项。", variant="warning", closable=True),
            InlineAlert("提交失败，请检查输入后重试。", variant="error", closable=True),
        )

    def _build_segmented_control_preview(self) -> QWidget:
        label = _build_label("当前选择：日", "panelDescription")
        control = SegmentedControl(options=["日", "周", "月", "年"])
        control.current_changed.connect(lambda _index: label.setText(f"当前选择：{control.current_text()}"))
        return _build_column(control, label)

    def _build_data_table_preview(self) -> QWidget:
        table = DataTable()
        table.set_columns(["姓名", "部门", "状态", "更新时间"])
        for index in range(1, 13):
            table.add_row(
                [
                    f"成员 {index:02d}",
                    f"小组 {index % 4 + 1}",
                    "在线" if index % 3 else "离线",
                    f"2026-04-{index:02d}",
                ]
            )
        table.setFixedHeight(260)
        table.row_selected.connect(lambda row: Toast.show_info(f"选中第 {row + 1} 行"))
        return table

    def _build_descriptions_preview(self) -> QWidget:
        return Descriptions(
            items=[
                ("项目名称", "Lark-Formatter V1.0"),
                ("当前阶段", "UI 组件整理"),
                ("主题数量", "2 套主主题"),
                ("新增控件", str(TOTAL_COMPONENTS)),
            ]
        )

    def _build_split_pane_preview(self) -> QWidget:
        split = SplitPane()
        split.setFixedHeight(220)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.addWidget(Typography("左侧内容区", variant="h3"))
        left_layout.addWidget(_build_label("这里可以放导航、筛选项或文件树。", "panelDescription"))
        left_layout.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.addWidget(Typography("右侧详情区", variant="h3"))
        right_layout.addWidget(
            Descriptions(
                items=[
                    ("场景", "模板预览"),
                    ("模式", "可拖拽调整"),
                    ("状态", "已接入主题"),
                ]
            )
        )
        right_layout.addStretch()

        split.add_widget(left)
        split.add_widget(right)
        split.set_sizes([250, 500])
        return split

    def _build_pagination_preview(self) -> QWidget:
        label = _build_label("当前页：1", "panelDescription")
        pagination = Pagination(total=240, page_size=10)
        pagination.page_changed.connect(lambda page: label.setText(f"当前页：{page}"))
        return _build_column(pagination, label)

    def _build_context_menu_preview(self) -> QWidget:
        button = self._make_demo_button("右键点击打开菜单", lambda: None)
        button.setContextMenuPolicy(Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(lambda _pos: self._show_context_menu())
        return _build_column(
            _build_label("在按钮上点击右键，即可预览 ContextMenu 的分组和快捷键信息。", "panelDescription"),
            _build_row(button, "stretch"),
        )

    def _show_context_menu(self) -> None:
        menu = ContextMenu()
        menu.add_action("复制", icon="📋", shortcut="Ctrl+C", callback=lambda: Toast.show_info("已复制"))
        menu.add_action("粘贴", icon="📌", shortcut="Ctrl+V", callback=lambda: Toast.show_success("已粘贴"))
        menu.add_separator()
        menu.add_action("删除", icon="🗑", callback=lambda: Toast.show_error("已删除"))
        ContextMenu.show_at_cursor(menu)

    def _build_chat_bubble_preview(self) -> QWidget:
        return _build_column(
            ChatBubble("你好，我已经准备好接收这份文档。", role="assistant", avatar="🤖", timestamp="14:30"),
            ChatBubble("请帮我检查一下目录和日期格式。", role="user", avatar="👤", timestamp="14:31"),
            ChatBubble("没问题，我先从标题层级开始。", role="assistant", avatar="🤖", timestamp="14:31"),
        )

    def _build_message_input_preview(self) -> QWidget:
        status = _build_label("试试输入一条消息，然后发送。", "panelDescription")
        message_input = MessageInput(placeholder="输入消息，Ctrl+Enter 发送...")
        message_input.message_sent.connect(lambda message: status.setText(f"最近一次发送：{message}"))
        return _build_column(status, message_input)

    def _build_typing_indicator_preview(self) -> QWidget:
        indicator = TypingIndicator()
        indicator.start()
        return _build_column(
            _build_label("TypingIndicator 会持续显示三点动画。", "panelDescription"),
            _build_row(indicator, "stretch"),
        )

    def _build_stepper_preview(self) -> QWidget:
        stepper = StepperWidget()
        stepper.add_module("scan", "扫描文档结构")
        stepper.add_module("normalize", "统一样式")
        stepper.add_module("export", "导出结果")
        stepper.update_status("scan", "completed", 100)
        stepper.update_status("normalize", "running", 65)
        stepper.update_status("export", "queued", 0)
        return _build_column(
            _build_label("StepperWidget 用于展示任务流和当前执行节点。", "panelDescription"),
            stepper,
        )

    def _build_surface_card_preview(self) -> QWidget:
        card = SurfaceCard("SurfaceCard")
        card.add_widget(_build_label("这是一个基于自绘表面的新卡片容器。", "panelDescription"))
        card.add_widget(TagChip("Card", variant="info"))
        card.add_widget(self._make_demo_button("卡片内操作", lambda: Toast.show_success("SurfaceCard 按钮已点击")))
        return card

    def _build_rounded_surface_preview(self) -> QWidget:
        shell = RoundedSurfaceFrame()
        content = QWidget(shell)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(10)
        content_layout.addWidget(Typography("RoundedSurfaceFrame", variant="h3"))
        content_layout.addWidget(_build_label("它是新的圆角表面基元，适合窗口壳和大面积容器。", "panelDescription"))
        content_layout.addWidget(self._make_demo_button("刷新表面", lambda: Toast.show_info("RoundedSurfaceFrame 正在使用当前主题配色")))

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.addWidget(content)

        def _apply_surface() -> None:
            theme = get_theme()
            shell.configure_surface(
                background=theme.bg_card,
                radius=theme.radius_lg,
                border_color=theme.border_focus,
                border_width=1.0,
            )

        _apply_surface()
        bind_theme(shell, _apply_surface)
        return shell

    def _build_date_picker_preview(self) -> QWidget:
        label = _build_label("当前未选择日期。", "panelDescription")
        picker = DatePicker()
        picker.date_selected.connect(lambda value: label.setText(f"已选择：{value}"))
        return _build_column(_build_row(Typography("选择日期", variant="body"), picker, "stretch"), label)

    def _build_calendar_month_preview(self) -> QWidget:
        calendar = CalendarMonth()
        calendar.mark_date(date.today(), color="#1677FF")
        calendar.mark_date(date.today() + timedelta(days=3), color="#52C41A")
        calendar.setFixedHeight(320)
        calendar.date_clicked.connect(lambda value: Toast.show_info(f"点击日期：{value}"))
        return calendar

    def _build_command_palette_preview(self) -> QWidget:
        status = _build_label("点击按钮或使用 Ctrl+K 触发命令面板。", "panelDescription")
        palette = CommandPalette(parent=self)
        palette.add_command("切换到浅色主题", shortcut="Ctrl+L", callback=lambda: set_theme(LIGHT))
        palette.add_command("切换到深色主题", shortcut="Ctrl+D", callback=lambda: set_theme(DARK))
        palette.add_command("显示成功通知", callback=lambda: Toast.show_success("命令已执行"))
        palette.command_executed.connect(lambda name: status.setText(f"最近执行：{name}"))
        self._floating_tools.append(palette)
        return _build_column(
            status,
            _build_row(
                self._make_demo_button("打开 CommandPalette", palette.toggle),
                "stretch",
            ),
        )

    def _build_drawer_preview(self) -> QWidget:
        status = _build_label("点击按钮后将从右侧打开抽屉。", "panelDescription")
        drawer = Drawer(title="预览抽屉", width=360, parent=self)
        drawer_body = QWidget()
        drawer_layout = QVBoxLayout(drawer_body)
        drawer_layout.setContentsMargins(18, 18, 18, 18)
        drawer_layout.setSpacing(12)
        drawer_layout.addWidget(Typography("抽屉内容", variant="h3"))
        drawer_layout.addWidget(InlineAlert("这里可以放任意控件组合。", variant="info"))
        drawer_layout.addWidget(self._make_demo_button("抽屉内操作", lambda: Toast.show_success("抽屉内动作已触发")))
        drawer_layout.addStretch()
        drawer.set_body(drawer_body)
        drawer.closed.connect(lambda: status.setText("抽屉已关闭。"))
        self._floating_tools.append(drawer)
        return _build_column(status, _build_row(self._make_demo_button("打开 Drawer", drawer.open), "stretch"))

    def _build_result_preview(self) -> QWidget:
        result = Result(
            status="success",
            title="排版任务已完成",
            description="本次任务共修复 42 处格式问题，输出文件已经准备好。",
        )
        result.add_action("查看结果", primary=True, callback=lambda: Toast.show_success("正在打开结果文件"))
        result.add_action("返回首页", callback=lambda: Toast.show_info("返回首页"))
        return result

    def _build_markdown_preview(self) -> QWidget:
        preview = MarkdownPreview()
        preview.set_markdown(
            "# Markdown 预览\n\n"
            "支持 **粗体**、*斜体*、`行内代码`。\n\n"
            "> 这是一个引用块\n\n"
            "- 无序列表 A\n"
            "- 无序列表 B\n\n"
            "---\n\n"
            "[访问示例站点](https://example.com)"
        )
        preview.setFixedHeight(280)
        return preview

    def _build_form_preview(self) -> QWidget:
        status = _build_label("留空提交可以看到必填与自定义校验效果。", "panelDescription")
        form = Form()

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("请输入姓名")
        form.add_field("name", name_edit, label="姓名", required=True)

        age_edit = QLineEdit()
        age_edit.setPlaceholderText("请输入年龄（数字）")
        form.add_field(
            "age",
            age_edit,
            label="年龄",
            validator=lambda value: "请输入有效数字" if value and not value.isdigit() else None,
        )
        form.add_divider()
        form.add_submit_button("提交表单", cancel_text="取消")
        form.submitted.connect(lambda payload: status.setText(f"提交成功：{payload}"))
        form.cancelled.connect(lambda: status.setText("已取消提交。"))
        return _build_column(status, form)

    def _make_demo_button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        return button


def main() -> None:
    app = QApplication(sys.argv)
    set_theme(LIGHT)
    window = AllComponentsPreviewPanel()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
