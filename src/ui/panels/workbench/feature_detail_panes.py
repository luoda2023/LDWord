from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget

from src.shared.ui.card import Card
from src.shared.ui.execution_progress_widget import ExecutionProgressWidget
from src.shared.ui.module_status_list import ModuleStatusList
from src.shared.ui.search_input import SearchInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.themed_slider import ThemedSlider
from src.shared.ui.toggle_switch import ToggleSwitch


class _FeatureDetailPaneBase(QWidget):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        self._title = QLabel(title, self)
        self._subtitle = QLabel(subtitle, self)
        self._subtitle.setWordWrap(True)
        self._summary = QLabel(self)
        self._summary.setWordWrap(True)
        self._section_titles: list[QLabel] = []

        self._layout.addWidget(self._title)
        self._layout.addWidget(self._subtitle)
        self._layout.addWidget(self._summary)

    def finish_setup(self) -> None:
        self._layout.addStretch(1)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_summary(self, text: str) -> None:
        self._summary.setText(text)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._title.setStyleSheet(
            f"font-size: {theme.font_size_xl}px; font-weight: {theme.font_weight_emphasis}; color: {theme.text_primary};"
        )
        self._subtitle.setStyleSheet(
            f"font-size: {theme.font_size_md}px; color: {theme.text_secondary};"
        )
        self._summary.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
        )
        for title in self._section_titles:
            title.setStyleSheet(
                f"font-size: {theme.font_size_lg}px; "
                f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; "
                f"background: transparent;"
            )

    def _build_card(self, title: str) -> Card:
        card = Card(parent=self)
        title_label = QLabel(title, card)
        title_label.setObjectName("wb_feature_section_title")
        self._section_titles.append(title_label)
        card.add_widget(title_label)
        return card

    def _add_form_rows(self, card: Card, rows: list[QWidget]) -> None:
        card.add_widget(TemplateFormStack(rows, parent=card))


class TableChartDetailPane(_FeatureDetailPaneBase):
    """图表处理能力组详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "图表处理",
            "选择运行时是否处理表格、题注和图表位置；边框、题注样式等外观基线来自模板。",
            parent=parent,
        )

        caption_card = self._build_card("题注与编号")
        self._caption_style_combo = StyledComboBox(caption_card)
        self._caption_style_combo.addItems(["国标题注", "章节内编号", "简洁编号"])
        self._caption_style_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())

        self._caption_gap_slider = ThemedSlider(parent=caption_card)
        self._caption_gap_slider.setRange(4, 20)
        self._caption_gap_slider.setValue(10)
        self._caption_gap_slider.valueChanged.connect(self._update_gap_label)
        self._caption_gap_value = QLabel("10 磅", caption_card)
        self._add_form_rows(
            caption_card,
            [
                template_form_row("题注处理", self._caption_style_combo, parent=caption_card),
                template_form_row(
                    "题注间距",
                    self._caption_gap_slider,
                    suffix_widget=self._caption_gap_value,
                    parent=caption_card,
                ),
            ],
        )
        self._layout.addWidget(caption_card)

        layout_card = self._build_card("版式规则")
        self._center_toggle = ToggleSwitch(layout_card, checked=True)
        self._center_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())

        self._continued_toggle = ToggleSwitch(layout_card, checked=True)
        self._continued_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        self._add_form_rows(
            layout_card,
            [
                template_form_row("图表居中", self._center_toggle, parent=layout_card),
                template_form_row("续表延续题注", self._continued_toggle, parent=layout_card),
            ],
        )
        self._layout.addWidget(layout_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_gap_label(self, value: int) -> None:
        self._caption_gap_value.setText(f"{value} 磅")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        center_text = "图表居中" if self._center_toggle.isChecked() else "仅保持原始位置"
        continued_text = "续表自动补题注" if self._continued_toggle.isChecked() else "续表人工确认"
        self.set_summary(
            f"当前策略：{self._caption_style_combo.currentText()} · 题注间距 {self._caption_gap_slider.value()} 磅 · {center_text} · {continued_text}"
        )


class CitationDetailPane(_FeatureDetailPaneBase):
    """引用处理能力组详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "引用处理",
            "处理正文引用和参考条目的编号/链接；参考文献列表排版来自模板。",
            parent=parent,
        )

        citation_card = self._build_card("引文规范")
        self._citation_style_combo = StyledComboBox(citation_card)
        self._citation_style_combo.addItems(["GB/T 7714 顺序编码", "作者年制", "自定义期刊样式"])
        self._citation_style_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())

        self._superscript_toggle = ToggleSwitch(citation_card, checked=True)
        self._superscript_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        self._add_form_rows(
            citation_card,
            [
                template_form_row("引用规则", self._citation_style_combo, parent=citation_card),
                template_form_row("正文上标联动", self._superscript_toggle, parent=citation_card),
            ],
        )
        self._layout.addWidget(citation_card)

        numbering_card = self._build_card("编号与去重")
        self._renumber_toggle = ToggleSwitch(numbering_card, checked=True)
        self._renumber_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())

        self._dedupe_slider = ThemedSlider(parent=numbering_card)
        self._dedupe_slider.setRange(0, 100)
        self._dedupe_slider.setValue(65)
        self._dedupe_slider.valueChanged.connect(self._update_dedupe_label)
        self._dedupe_value = QLabel("65%", numbering_card)
        self._add_form_rows(
            numbering_card,
            [
                template_form_row("自动重排编号", self._renumber_toggle, parent=numbering_card),
                template_form_row(
                    "去重阈值",
                    self._dedupe_slider,
                    suffix_widget=self._dedupe_value,
                    parent=numbering_card,
                ),
            ],
        )
        self._layout.addWidget(numbering_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_dedupe_label(self, value: int) -> None:
        self._dedupe_value.setText(f"{value}%")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        superscript_text = "正文上标同步" if self._superscript_toggle.isChecked() else "正文内联显示"
        renumber_text = "自动重排" if self._renumber_toggle.isChecked() else "保留原编号"
        self.set_summary(
            f"当前策略：{self._citation_style_combo.currentText()} · {superscript_text} · {renumber_text} · 去重阈值 {self._dedupe_slider.value()}%"
        )


class ExecutionHistoryDetailPane(_FeatureDetailPaneBase):
    """执行历史详情页，供执行控制器写入实时状态。"""

    def __init__(self, parent=None):
        super().__init__(
            "执行历史",
            "查看最近一次运行的进度、模块状态与查看模式，后续可继续接入真实日志流。",
            parent=parent,
        )

        self._search = SearchInput("搜索历史记录", self)
        self._search.search_changed.connect(lambda *_: self._refresh_summary())
        self._layout.addWidget(self._search)

        latest_card = self._build_card("最新运行概览")
        self._progress_widget = ExecutionProgressWidget(latest_card)
        self._progress_widget.set_progress(3, 5, "模块执行")
        self._progress_widget.update_module_status("模块执行", "running", 42)
        self._progress_widget.update_module_status("报告生成", "queued", 0)
        self._progress_widget.append_log("info", "最近一次运行已进入模块执行阶段。")
        latest_card.add_widget(self._progress_widget)

        self._module_list = ModuleStatusList(latest_card)
        self._module_list.add_module("heading", "标题编号")
        self._module_list.add_module("fill", "内容填充")
        self._module_list.add_module("export", "输出封装")
        self._module_list.update_status("heading", "completed", 100)
        self._module_list.update_status("fill", "running", 42)
        self._module_list.update_status("export", "queued", 0)
        latest_card.add_widget(self._module_list)
        self._layout.addWidget(latest_card)

        filter_card = self._build_card("查看模式")
        self._view_mode_combo = StyledComboBox(filter_card)
        self._view_mode_combo.addItems(["完整日志", "仅看警告", "错误与摘要"])
        self._view_mode_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())
        self._add_form_rows(
            filter_card,
            [template_form_row("日志视图", self._view_mode_combo, parent=filter_card)],
        )
        self._layout.addWidget(filter_card)

        self._refresh_summary()
        self.finish_setup()

    def _refresh_summary(self) -> None:
        filter_text = self._search.text.strip()
        filter_hint = f"，关键字：{filter_text}" if filter_text else ""
        self.set_summary(
            f"当前查看：{self._view_mode_combo.currentText()} · 最新一次运行仍在进行{filter_hint}"
        )


__all__ = [
    "CitationDetailPane",
    "ExecutionHistoryDetailPane",
    "TableChartDetailPane",
]
