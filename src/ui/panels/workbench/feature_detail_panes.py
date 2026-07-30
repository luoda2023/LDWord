from __future__ import annotations

from src.config.material_context import MaterialExecutionContext
from src.qt_api import QLabel, QLineEdit, QVBoxLayout, QWidget, Signal

from src.shared.ui.card import Card
from src.shared.ui.file_drop_zone import FileDropZone
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.path_drop import PathAcceptancePolicy
from src.shared.ui.search_input import SearchInput
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.text_area import TextArea
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


class FormulaDetailPane(_FeatureDetailPaneBase):
    """公式处理能力组详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "公式处理",
            "设置公式转换、低置信度处理和化学式修正；公式外观基线来自模板。",
            parent=parent,
        )

        formula_card = self._build_card("公式处理")
        self._formula_style_combo = StyledComboBox(formula_card)
        self._formula_style_combo.addItems(["学位论文公式", "期刊简洁样式", "技术文档样式"])
        self._formula_style_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())

        self._formula_align_combo = StyledComboBox(formula_card)
        self._formula_align_combo.addItems(["整体居中", "编号右对齐", "文本流内显示"])
        self._formula_align_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())
        self._add_form_rows(
            formula_card,
            [
                template_form_row("处理方案", self._formula_style_combo, parent=formula_card),
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


class CleanupDetailPane(_FeatureDetailPaneBase):
    """风险检查能力域详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "风险检查",
            "用于统一清洗 Markdown 残留、空白噪声和结构异常，适合作为最终执行前的合规闸门。",
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
    """资料包填充能力域详情页。"""

    material_context_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(
            "资料包填充",
            "资料字段与文档中的 {{字段}} 严格同名时写入，并在执行前提供确定性预览。",
            parent=parent,
        )
        self._material_context = MaterialExecutionContext()

        template_card = self._build_card("方案与占位规则")
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
            policy=PathAcceptancePolicy(
                suffixes=(".xlsx", ".csv", ".json"),
                dialog_label="数据文件",
            ),
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

        entity_card = self._build_card("当前资料")
        self._profile_name_edit = QLineEdit(entity_card)
        self._profile_name_edit.setPlaceholderText("未选择资料")
        self._profile_name_edit.textChanged.connect(lambda *_: self._on_material_context_edited())

        self._assets_picker = FolderPicker(placeholder="未选择图片目录", parent=entity_card)
        self._assets_picker.folder_changed.connect(lambda *_: self._on_material_context_edited())

        self._entity_fields_edit = TextArea(
            placeholder="company_name=测试公司\nlegal_person=张三",
            min_height=88,
            max_height=140,
            parent=entity_card,
        )
        self._entity_fields_edit.text_changed.connect(self._on_material_context_edited)
        self._add_form_rows(
            entity_card,
            [
                template_form_row("当前资料", self._profile_name_edit, parent=entity_card),
                template_form_row("图片目录", self._assets_picker, parent=entity_card),
                template_form_row("字段资料", self._entity_fields_edit, parent=entity_card),
            ],
        )
        self._layout.addWidget(entity_card)

        behavior_card = self._build_card("预览与匹配规则")
        self._confidence_slider = ThemedSlider(parent=behavior_card)
        self._confidence_slider.setRange(50, 100)
        self._confidence_slider.setValue(78)
        self._confidence_slider.valueChanged.connect(self._update_confidence_label)
        self._confidence_value = QLabel("78%", behavior_card)

        self._preview_toggle = ToggleSwitch(behavior_card, checked=True)
        self._preview_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        self._confidence_row = template_form_row(
            "映射信心度",
            self._confidence_slider,
            suffix_widget=self._confidence_value,
            parent=behavior_card,
        )
        self._add_form_rows(
            behavior_card,
            [
                self._confidence_row,
                template_form_row("自动预览", self._preview_toggle, parent=behavior_card),
            ],
        )
        self._layout.addWidget(behavior_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_confidence_label(self, value: int) -> None:
        self._confidence_value.setText(f"{value}%")
        self._refresh_summary()

    def material_context(self) -> MaterialExecutionContext:
        context = self._material_context.clone()
        context.profile_name = self._profile_name_edit.text().strip()
        context.entity_data = _parse_entity_fields_text(
            self._entity_fields_edit.get_text()
        )
        context.entity_assets_dir = self._assets_picker.path().strip()
        return context

    def set_material_context(
        self,
        context: MaterialExecutionContext | None,
        *,
        emit_signal: bool = True,
    ) -> None:
        context = context.clone() if isinstance(context, MaterialExecutionContext) else MaterialExecutionContext()
        self._material_context = context.clone()
        self._confidence_row.setVisible(not context.exact_material_placeholders)

        self._profile_name_edit.blockSignals(True)
        self._entity_fields_edit.blockSignals(True)
        self._assets_picker.blockSignals(True)
        try:
            self._profile_name_edit.setText(context.profile_name)
            self._entity_fields_edit.set_text(_format_entity_fields_text(context.entity_data))
            self._assets_picker.set_path(context.entity_assets_dir)
        finally:
            self._assets_picker.blockSignals(False)
            self._entity_fields_edit.blockSignals(False)
            self._profile_name_edit.blockSignals(False)

        self._refresh_summary()
        if emit_signal:
            self.material_context_changed.emit(self.material_context())

    def _on_material_context_edited(self) -> None:
        self._refresh_summary()
        self.material_context_changed.emit(self.material_context())

    def _refresh_summary(self) -> None:
        template_name = self._template_combo.currentText() or "未选择模板"
        source_name = self._source_picker.file_path() or "未挂载数据源"
        source_label = source_name.split("\\")[-1] if source_name else "未挂载数据源"
        placeholder_text = "保留未匹配占位符" if self._placeholder_toggle.isChecked() else "直接落地替换"
        preview_text = "开启自动预览" if self._preview_toggle.isChecked() else "仅保存结果"
        material = self.material_context()
        entity_text = material.profile_name or "未选择资料"
        field_text = f"资料已填 {len(material.entity_data)} 项" if material.entity_data else "资料未填写"
        assets_text = "图片目录已选择" if material.entity_assets_dir else "图片目录未选择"
        matching_text = (
            "精确 {{@text:字段}} 匹配"
            if material.exact_material_placeholders
            else f"信心度 {self._confidence_slider.value()}%"
        )
        self.set_summary(
            f"当前流程：{template_name} · 数据源 {source_label} · 当前资料 {entity_text} · {field_text} · {assets_text} · {matching_text} · {placeholder_text} · {preview_text}"
        )

    def _apply_theme(self) -> None:
        super()._apply_theme()
        theme = get_theme()
        self._source_hint.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")
        apply_size_class(self._profile_name_edit, "md")
        self._profile_name_edit.setStyleSheet(build_text_input_stylesheet(theme))


def _parse_entity_fields_text(text: str) -> dict[str, str]:
    entity_data: dict[str, str] = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        key = key.strip()
        if key:
            entity_data[key] = value.strip()
    return entity_data


def _format_entity_fields_text(entity_data: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in entity_data.items())


__all__ = [
    "CitationDetailPane",
    "CleanupDetailPane",
    "ContentDataDetailPane",
    "FormulaDetailPane",
    "TableChartDetailPane",
]
