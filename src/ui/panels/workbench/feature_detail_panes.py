from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget

from src.shared.ui.card import Card
from src.shared.ui.execution_progress_widget import ExecutionProgressWidget
from src.shared.ui.file_drop_zone import FileDropZone
from src.shared.ui.module_status_list import ModuleStatusList
from src.shared.ui.search_input import SearchInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.themed_slider import ThemedSlider
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.theme import bind_theme, get_theme


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
    """表格与图表能力组详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "表格与图表",
            "集中管理图表题注、对齐方式和续表规则，后续可以直接接入 table_format / caption 等模块。",
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
                template_form_row("题注样式", self._caption_style_combo, parent=caption_card),
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


class PageElementsDetailPane(_FeatureDetailPaneBase):
    """页面元素能力组详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "页面元素",
            "管理页眉页脚、页码和目录联动，后续适合接入 header_footer 与 toc 等模块。",
            parent=parent,
        )

        header_card = self._build_card("页眉页脚策略")
        self._header_footer_combo = StyledComboBox(header_card)
        self._header_footer_combo.addItems(["首页不同", "全篇统一", "分节继承"])
        self._header_footer_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())

        self._page_number_toggle = ToggleSwitch(header_card, checked=True)
        self._page_number_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        self._add_form_rows(
            header_card,
            [
                template_form_row("页眉页脚", self._header_footer_combo, parent=header_card),
                template_form_row("页码联动", self._page_number_toggle, parent=header_card),
            ],
        )
        self._layout.addWidget(header_card)

        toc_card = self._build_card("目录与附加项")
        self._toc_toggle = ToggleSwitch(toc_card, checked=True)
        self._toc_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())

        self._toc_depth_slider = ThemedSlider(parent=toc_card)
        self._toc_depth_slider.setRange(1, 6)
        self._toc_depth_slider.setValue(3)
        self._toc_depth_slider.valueChanged.connect(self._update_depth_label)
        self._toc_depth_value = QLabel("3 级", toc_card)
        self._add_form_rows(
            toc_card,
            [
                template_form_row("自动刷新目录", self._toc_toggle, parent=toc_card),
                template_form_row(
                    "目录深度",
                    self._toc_depth_slider,
                    suffix_widget=self._toc_depth_value,
                    parent=toc_card,
                ),
            ],
        )
        self._layout.addWidget(toc_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_depth_label(self, value: int) -> None:
        self._toc_depth_value.setText(f"{value} 级")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        page_number_text = "页码开启" if self._page_number_toggle.isChecked() else "页码关闭"
        toc_text = "自动刷新目录" if self._toc_toggle.isChecked() else "目录手动维护"
        self.set_summary(
            f"当前策略：{self._header_footer_combo.currentText()} · {page_number_text} · {toc_text} · 目录 {self._toc_depth_slider.value()} 级"
        )


class FormulaDetailPane(_FeatureDetailPaneBase):
    """公式规范能力组详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "公式规范",
            "统一公式样式、化学式排版和展示对齐方式，后续可直接承接 equation_table_format 与 chem_typography。",
            parent=parent,
        )

        formula_card = self._build_card("公式样式")
        self._formula_style_combo = StyledComboBox(formula_card)
        self._formula_style_combo.addItems(["学位论文公式", "期刊简洁样式", "技术文档样式"])
        self._formula_style_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())

        self._formula_align_combo = StyledComboBox(formula_card)
        self._formula_align_combo.addItems(["整体居中", "编号右对齐", "文本流内显示"])
        self._formula_align_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())
        self._add_form_rows(
            formula_card,
            [
                template_form_row("公式样式", self._formula_style_combo, parent=formula_card),
                template_form_row("显示方式", self._formula_align_combo, parent=formula_card),
            ],
        )
        self._layout.addWidget(formula_card)

        chemistry_card = self._build_card("化学式与间距")
        self._chem_toggle = ToggleSwitch(chemistry_card, checked=True)
        self._chem_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())

        self._formula_gap_slider = ThemedSlider(parent=chemistry_card)
        self._formula_gap_slider.setRange(4, 18)
        self._formula_gap_slider.setValue(8)
        self._formula_gap_slider.valueChanged.connect(self._update_gap_label)
        self._formula_gap_value = QLabel("8 磅", chemistry_card)
        self._add_form_rows(
            chemistry_card,
            [
                template_form_row("启用化学式修正", self._chem_toggle, parent=chemistry_card),
                template_form_row(
                    "上下留白",
                    self._formula_gap_slider,
                    suffix_widget=self._formula_gap_value,
                    parent=chemistry_card,
                ),
            ],
        )
        self._layout.addWidget(chemistry_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_gap_label(self, value: int) -> None:
        self._formula_gap_value.setText(f"{value} 磅")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        chem_text = "化学式修正开启" if self._chem_toggle.isChecked() else "仅保留公式基础格式"
        self.set_summary(
            f"当前策略：{self._formula_style_combo.currentText()} · {self._formula_align_combo.currentText()} · {chem_text} · 留白 {self._formula_gap_slider.value()} 磅"
        )


class CitationDetailPane(_FeatureDetailPaneBase):
    """参考文献能力组详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "参考文献",
            "管理引文样式、上标联动和重排规则，后续可以直接接入 reference_format。",
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
                template_form_row("引文样式", self._citation_style_combo, parent=citation_card),
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


class CleanupDetailPane(_FeatureDetailPaneBase):
    """校验与清理能力组详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "校验与清理",
            "用于统一清洗 Markdown 残留、空白噪声和结构异常，适合作为最终执行前的质量闸门。",
            parent=parent,
        )

        rule_card = self._build_card("清理规则")
        self._rule_search = SearchInput("搜索清理规则", self)
        self._rule_search.search_changed.connect(lambda *_: self._refresh_summary())
        rule_card.add_widget(self._rule_search)

        self._markdown_toggle = ToggleSwitch(rule_card, checked=True)
        self._markdown_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())

        self._whitespace_toggle = ToggleSwitch(rule_card, checked=True)
        self._whitespace_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        self._add_form_rows(
            rule_card,
            [
                template_form_row("Markdown / LaTeX 残留清理", self._markdown_toggle, parent=rule_card),
                template_form_row("空白与换行规范化", self._whitespace_toggle, parent=rule_card),
            ],
        )
        self._layout.addWidget(rule_card)

        audit_card = self._build_card("质量闸门")
        self._audit_toggle = ToggleSwitch(audit_card, checked=True)
        self._audit_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())

        self._strictness_slider = ThemedSlider(parent=audit_card)
        self._strictness_slider.setRange(1, 5)
        self._strictness_slider.setValue(3)
        self._strictness_slider.valueChanged.connect(self._update_strictness_label)
        self._strictness_value = QLabel("3 级", audit_card)
        self._add_form_rows(
            audit_card,
            [
                template_form_row("执行前结构校验", self._audit_toggle, parent=audit_card),
                template_form_row(
                    "校验强度",
                    self._strictness_slider,
                    suffix_widget=self._strictness_value,
                    parent=audit_card,
                ),
            ],
        )
        self._layout.addWidget(audit_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_strictness_label(self, value: int) -> None:
        self._strictness_value.setText(f"{value} 级")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        search_text = self._rule_search.text.strip()
        search_hint = f" · 规则过滤：{search_text}" if search_text else ""
        markdown_text = "残留清理开启" if self._markdown_toggle.isChecked() else "保留原始标记"
        whitespace_text = "空白规范化" if self._whitespace_toggle.isChecked() else "保留原始空白"
        audit_text = "执行前强校验" if self._audit_toggle.isChecked() else "仅记录异常"
        self.set_summary(
            f"当前策略：{markdown_text} · {whitespace_text} · {audit_text} · 强度 {self._strictness_slider.value()} 级{search_hint}"
        )


class ContentDataDetailPane(_FeatureDetailPaneBase):
    """内容与数据能力组详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "内容与数据",
            "从结构化数据源选择模板，再决定映射强度与预览策略，后续可以分拆为更细的填充和插入能力。",
            parent=parent,
        )

        template_card = self._build_card("场景与占位规则")
        self._template_combo = StyledComboBox(template_card)
        self._template_combo.addItems(
            [
                "默认填充流程",
                "技术方案说明",
                "汇报演示稿",
                "合同交付件",
            ]
        )
        self._template_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())

        self._placeholder_toggle = ToggleSwitch(template_card, checked=True)
        self._placeholder_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        self._add_form_rows(
            template_card,
            [
                template_form_row("填充模板", self._template_combo, parent=template_card),
                template_form_row("保留未匹配占位符", self._placeholder_toggle, parent=template_card),
            ],
        )
        self._layout.addWidget(template_card)

        source_card = self._build_card("数据源")
        self._source_picker = FileDropZone(
            dialog_title="选择填充数据源",
            file_filter="Data Files (*.xlsx *.csv *.json);;All Files (*)",
            parent=source_card,
        )
        self._source_picker.file_selected.connect(lambda *_: self._refresh_summary())
        source_card.add_widget(self._source_picker)
        self._source_hint = QLabel(
            "支持 Excel / CSV / JSON，后续可继续接真实映射表。",
            source_card,
        )
        self._source_hint.setWordWrap(True)
        source_card.add_widget(self._source_hint)
        self._layout.addWidget(source_card)

        behavior_card = self._build_card("预览与映射强度")
        self._confidence_slider = ThemedSlider(parent=behavior_card)
        self._confidence_slider.setRange(50, 100)
        self._confidence_slider.setValue(78)
        self._confidence_slider.valueChanged.connect(self._update_confidence_label)
        self._confidence_value = QLabel("78%", behavior_card)

        self._preview_toggle = ToggleSwitch(behavior_card, checked=True)
        self._preview_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        self._add_form_rows(
            behavior_card,
            [
                template_form_row(
                    "映射信心度",
                    self._confidence_slider,
                    suffix_widget=self._confidence_value,
                    parent=behavior_card,
                ),
                template_form_row("自动预览", self._preview_toggle, parent=behavior_card),
            ],
        )
        self._layout.addWidget(behavior_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_confidence_label(self, value: int) -> None:
        self._confidence_value.setText(f"{value}%")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        template_name = self._template_combo.currentText() or "未选择模板"
        source_name = self._source_picker.file_path() or "未挂载数据源"
        source_label = source_name.split("\\")[-1] if source_name else "未挂载数据源"
        placeholder_text = "保留未匹配占位符" if self._placeholder_toggle.isChecked() else "直接落地替换"
        preview_text = "开启自动预览" if self._preview_toggle.isChecked() else "仅保存结果"
        self.set_summary(
            f"当前流程：{template_name} · 数据源 {source_label} · 信心度 {self._confidence_slider.value()}% · {placeholder_text} · {preview_text}"
        )

    def _apply_theme(self) -> None:
        super()._apply_theme()
        theme = get_theme()
        self._source_hint.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")


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


QuickFillDetailPane = ContentDataDetailPane


__all__ = [
    "CitationDetailPane",
    "CleanupDetailPane",
    "ContentDataDetailPane",
    "ExecutionHistoryDetailPane",
    "FormulaDetailPane",
    "PageElementsDetailPane",
    "QuickFillDetailPane",
    "TableChartDetailPane",
]
