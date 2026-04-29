"""Header/footer section for the template elements detail pane."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.config.template import TemplateConfig
from src.qt_api import QHBoxLayout, QLabel, QLineEdit, QWidget, Qt
from src.shared.ui.card import Card
from src.shared.ui.flow_section import FlowSection
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import normalize_template_form_rows, template_form_row
from src.shared.ui.theme import get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.typography_controls import build_emphasis_widget
from src.ui.panels.template_elements_page_plan import (
    PageNumberPlanSection,
    PageSelectorEditor,
    SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS,
    continuous_page_number_preset,
    default_page_number_phases,
    default_suppress_header_footer_selectors,
    ensure_default_page_number_phases,
    page_number_phase_brief,
    split_page_number_preset,
)

if TYPE_CHECKING:
    from src.ui.panels.template_elements_detail import ElementsDetail


HEADER_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("styleref", "跟随章节标题"),
    ("fixed", "固定文字"),
    ("none", "不显示页眉"),
)

FOOTER_CONTENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("page_number", "仅页码"),
    ("fixed", "仅固定文字"),
    ("page_number_with_text", "页码 + 固定文字"),
    ("none", "不显示页脚"),
)

FOOTER_ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
)

HEADER_FOOTER_SCHEME_OPTIONS: tuple[tuple[str, str], ...] = (
    ("thesis", "论文默认：封面不显示，前置罗马，正文阿拉伯"),
    ("continuous", "可编号内容统一页码"),
    ("no_page_number", "不显示页脚"),
    ("custom", "自定义"),
)

class HeaderFooterDetailSection:
    """Owns the header/footer controls inside ElementsDetail."""

    def __init__(self, owner: "ElementsDetail"):
        self._owner = owner

        self.section = Card(parent=owner._editor_column)
        owner._header_section = self.section
        owner._add_card_header(self.section, "panel-top", "页眉与页脚")
        owner._editor_layout.addWidget(self.section)
        self._build_form()

        self._page_plan = PageNumberPlanSection(owner)
        self._page_plan.export_compat_attributes(self)
        self._export_compat_attributes()

    def _export_compat_attributes(self) -> None:
        names = (
            "_scheme_combo",
            "_scheme_row",
            "_scheme_note",
            "_quick_preview_label",
            "_structure_section",
            "_header_mode_combo",
            "_header_mode_row",
            "_header_text_edit",
            "_header_text_row",
            "_styleref_level_combo",
            "_styleref_level_row",
            "_font_cn_combo",
            "_font_cn_row",
            "_font_en_combo",
            "_font_en_row",
            "_size_combo",
            "_size_row",
            "_bold_toggle",
            "_italic_toggle",
            "_emphasis_row",
            "_footer_content_combo",
            "_footer_content_row",
            "_footer_text_edit",
            "_footer_text_row",
            "_footer_alignment_combo",
            "_footer_alignment_row",
            "_header_border_toggle",
            "_header_border_row",
            "_hide_cover_toggle",
            "_hide_cover_row",
            "_suppress_selector_editor",
            "_suppress_selector_row",
            "_page_plan_section",
            "_page_advanced_section",
            "_page_validation_mode_combo",
            "_page_missing_doc_tree_combo",
            "_page_plan_alert",
            "_page_plan_note",
            "_preset_continuous_btn",
            "_preset_split_restart_btn",
            "_preset_split_continue_btn",
            "_add_phase_btn",
            "_page_phase_rows_host",
            "_page_phase_rows_layout",
        )
        for name in names:
            setattr(self._owner, name, getattr(self, name))
        self._owner._page_phase_rows = self._page_phase_rows

    def _build_form(self) -> None:
        self._inspector_form = InspectorForm(parent=self.section)

        self._scheme_combo = StyledComboBox(self._owner)
        for value, label in HEADER_FOOTER_SCHEME_OPTIONS:
            self._scheme_combo.addItem(label, value)
        self._scheme_combo.currentIndexChanged.connect(self._on_scheme_changed)
        self._scheme_row = self._form_row("应用方案", self._scheme_combo, parent=self._inspector_form)
        self._inspector_form.add_widget(self._scheme_row)
        self._scheme_note = self._group_note("选择方案后仍可手动微调。")
        self._inspector_form.add_widget(self._scheme_note)

        self._quick_preview_label = QLabel(self._inspector_form)
        self._quick_preview_label.setObjectName("tpl_header_footer_quick_preview")
        self._quick_preview_label.setWordWrap(True)
        self._inspector_form.add_widget(self._quick_preview_label)

        self._inspector_form.add_widget(self._group_title("页眉"))

        self._header_mode_combo = StyledComboBox(self._owner)
        for value, label in HEADER_MODE_OPTIONS:
            self._header_mode_combo.addItem(label, value)
        self._header_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._header_mode_row = self._form_row("页眉内容", self._header_mode_combo, parent=self._inspector_form)

        self._header_text_edit = QLineEdit(self._owner)
        self._header_text_edit.textChanged.connect(self._owner._on_structure_edited)
        self._header_text_row = self._form_row("页眉文字", self._header_text_edit, parent=self._inspector_form)

        self._styleref_level_combo = StyledComboBox(self._owner)
        for level in range(1, 7):
            self._styleref_level_combo.addItem(f"{level} 级", level)
        self._styleref_level_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._styleref_level_row = self._form_row("标题级别", self._styleref_level_combo, parent=self._inspector_form)
        self._header_mode_pair = self._inspector_form.add_pair(
            self._header_mode_row,
            self._styleref_level_row,
            self._header_text_row,
        )

        self._header_border_toggle = ToggleSwitch(self._owner, checked=True)
        self._header_border_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._header_border_row = self._form_row("页眉横线", self._header_border_toggle, parent=self._inspector_form)
        self._inspector_form.add_widget(self._header_border_row)

        self._inspector_form.add_widget(self._group_title("页脚"))

        self._footer_content_combo = StyledComboBox(self._owner)
        for value, label in FOOTER_CONTENT_OPTIONS:
            self._footer_content_combo.addItem(label, value)
        self._footer_content_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._footer_content_row = self._form_row("页脚内容", self._footer_content_combo, parent=self._inspector_form)

        self._footer_text_edit = QLineEdit(self._owner)
        self._footer_text_edit.textChanged.connect(self._owner._on_structure_edited)
        self._footer_text_row = self._form_row("页脚文字", self._footer_text_edit, parent=self._inspector_form)

        self._footer_alignment_combo = StyledComboBox(self._owner)
        for value, label in FOOTER_ALIGNMENT_OPTIONS:
            self._footer_alignment_combo.addItem(label, value)
        self._footer_alignment_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._footer_alignment_row = self._form_row("页脚对齐", self._footer_alignment_combo, parent=self._inspector_form)

        self._footer_grid = self._inspector_form.add_pair(
            self._footer_content_row,
            self._footer_alignment_row,
        )
        self._inspector_form.add_widget(self._footer_text_row)

        self._inspector_form.add_widget(self._group_title("页眉页脚文字样式"))
        self._inspector_form.add_widget(
            self._group_note("同时应用于实际显示的页眉文字、页脚文字和页码。")
        )

        self._font_cn_combo = FontCombo(lang="cn", parent=self._owner)
        self._font_cn_combo.font_changed.connect(self._owner._on_structure_edited)
        self._font_cn_row = self._form_row("中文字体", self._font_cn_combo, parent=self._inspector_form)

        self._font_en_combo = FontCombo(lang="en", parent=self._owner)
        self._font_en_combo.font_changed.connect(self._owner._on_structure_edited)
        self._font_en_row = self._form_row("英文字体", self._font_en_combo, parent=self._inspector_form)

        self._size_combo = SizeCombo(self._owner)
        self._size_combo.size_changed.connect(self._owner._on_structure_edited)
        self._size_combo.currentTextChanged.connect(self._owner._on_structure_edited)
        self._size_row = self._form_row("字号", self._size_combo, parent=self._inspector_form)

        self._bold_toggle = ToggleSwitch(self._owner, checked=False)
        self._bold_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._italic_toggle = ToggleSwitch(self._owner, checked=False)
        self._italic_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._emphasis_row = self._form_row(
            "字形",
            build_emphasis_widget(self._owner, self._bold_toggle, self._italic_toggle),
            parent=self._inspector_form,
        )
        self._typography_grid = self._inspector_form.add_grid(
            [
                [self._font_cn_row, self._size_row],
                [self._font_en_row, self._emphasis_row],
            ],
        )

        self._structure_section = FlowSection("高级：分区排除", expanded=False, parent=self._inspector_form)
        self._structure_section.add_widget(
            self._group_note("启用后，所选分区的页眉、页脚和页码都不显示；分区来自文档结构识别。")
        )

        self._hide_cover_toggle = ToggleSwitch(self._owner, checked=True)
        self._hide_cover_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._hide_cover_row = self._form_row("启用分区排除", self._hide_cover_toggle, parent=self._structure_section)
        toggle_rows = [self._hide_cover_row]
        normalize_template_form_rows(toggle_rows)
        self._page_toggle_group = QWidget(self._structure_section)
        toggle_layout = QHBoxLayout(self._page_toggle_group)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(16)
        for row in toggle_rows:
            toggle_layout.addWidget(row, 0, Qt.AlignLeft | Qt.AlignVCenter)
        toggle_layout.addStretch(1)
        self._structure_section.add_widget(self._page_toggle_group)

        self._suppress_selector_editor = PageSelectorEditor(
            self._structure_section,
            options=SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS,
            hint_text="选择不显示页眉、页脚和页码的分区。普通论文通常排除封面及声明页。",
        )
        self._suppress_selector_editor.changed.connect(self._owner._on_structure_edited)
        self._suppress_selector_row = self._form_row(
            "不显示分区",
            self._suppress_selector_editor,
            parent=self._structure_section,
        )
        self._structure_section.add_widget(self._suppress_selector_row)
        self._suppress_selector_row.set_label_alignment(Qt.AlignLeft | Qt.AlignTop)
        self._inspector_form.add_widget(self._structure_section)
        self.section.add_widget(self._inspector_form)

    def _form_row(
        self,
        label: str,
        widget: QWidget,
        *,
        suffix_widget: QWidget | None = None,
        parent,
    ) -> QWidget:
        return template_form_row(label, widget, suffix_widget=suffix_widget, parent=parent)

    def _group_title(self, text: str) -> QLabel:
        label = QLabel(text, self._inspector_form)
        label.setObjectName("tpl_form_group_title")
        theme = get_theme()
        label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; font-weight: {theme.font_weight_medium}; color: {theme.text_primary}; margin-top: 8px;"
        )
        return label

    def _group_note(self, text: str) -> QLabel:
        label = QLabel(text, self._inspector_form)
        label.setObjectName("tpl_form_group_note")
        label.setWordWrap(True)
        theme = get_theme()
        label.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")
        return label

    def _set_combo_by_data(self, combo: StyledComboBox, target) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == target:
                combo.setCurrentIndex(index)
                return

    def phase_rows_to_configs(self):
        return self._page_plan.phase_rows_to_configs()

    def _apply_page_number_preset(self, preset_id: str) -> None:
        self._page_plan._apply_page_number_preset(preset_id)

    def _on_add_phase(self) -> None:
        self._page_plan._on_add_phase()

    def clear(self) -> None:
        self._page_plan.clear()

    def _on_scheme_changed(self, *_args) -> None:
        if self._owner._is_syncing:
            return
        scheme = str(self._scheme_combo.currentData() or "custom")
        if scheme == "custom":
            self._owner._on_structure_edited()
            return
        self._apply_scheme(scheme)

    def _apply_scheme(self, scheme: str) -> None:
        previous_syncing = self._owner._is_syncing
        self._owner._is_syncing = True
        try:
            if scheme == "thesis":
                self._set_combo_by_data(self._footer_content_combo, "page_number")
                self._hide_cover_toggle.setChecked(True)
                self._suppress_selector_editor.set_selectors(["pre_numbering"])
                self._page_plan._rebuild_page_phase_rows(split_page_number_preset(continue_body=False))
            elif scheme == "continuous":
                self._set_combo_by_data(self._footer_content_combo, "page_number")
                self._hide_cover_toggle.setChecked(False)
                self._suppress_selector_editor.set_selectors(["pre_numbering"])
                self._page_plan._rebuild_page_phase_rows(continuous_page_number_preset())
            elif scheme == "no_page_number":
                self._set_combo_by_data(self._footer_content_combo, "none")
                self._hide_cover_toggle.setChecked(False)
                self._suppress_selector_editor.set_selectors(["pre_numbering"])
                self._page_plan._rebuild_page_phase_rows(continuous_page_number_preset())
        finally:
            self._owner._is_syncing = previous_syncing
        self.sync_dependent_state()
        self._owner._on_structure_edited()

    def _sync_scheme_combo(self, header_footer) -> None:
        scheme = self._infer_scheme(header_footer)
        self._set_scheme_combo_quietly(scheme)

    def _set_scheme_combo_quietly(self, scheme: str) -> None:
        previous_syncing = self._owner._is_syncing
        self._owner._is_syncing = True
        try:
            self._set_combo_by_data(self._scheme_combo, scheme)
        finally:
            self._owner._is_syncing = previous_syncing

    def _infer_scheme(self, header_footer) -> str:
        footer_mode = str(getattr(getattr(header_footer, "footer", None), "content_mode", "page_number") or "page_number")
        suppress_selectors = default_suppress_header_footer_selectors(header_footer)
        phases = default_page_number_phases(header_footer)
        if footer_mode == "none":
            if not suppress_selectors and len(phases) == 1:
                phase = phases[0]
                if list(phase.selectors or []) == ["all_numbered_content"]:
                    return "no_page_number"
            return "custom"
        if footer_mode != "page_number":
            return "custom"
        if suppress_selectors == ["pre_numbering"] and len(phases) == 2:
            front, body = phases
            if (
                list(front.selectors or []) == ["front_matter"]
                and str(front.number_format or "") == "upperRoman"
                and str(front.start_mode or "") == "restart"
                and list(body.selectors or []) == ["body", "back_matter"]
                and str(body.number_format or "") == "decimal"
                and str(body.start_mode or "") == "restart"
            ):
                return "thesis"
        if not suppress_selectors and len(phases) == 1:
            phase = phases[0]
            if list(phase.selectors or []) == ["all_numbered_content"]:
                return "continuous"
        return "custom"

    def set_header_footer(self, header_footer) -> None:
        self._set_combo_by_data(self._header_mode_combo, header_footer.header_mode)
        self._header_text_edit.setText(header_footer.header_text or "")
        self._set_combo_by_data(self._styleref_level_combo, header_footer.styleref_level)
        self._font_cn_combo.set_font_name(header_footer.font_cn or "")
        self._font_en_combo.set_font_name(header_footer.font_en or "")
        self._size_combo.set_pt(header_footer.size_pt or 12.0)
        self._bold_toggle.setChecked(bool(getattr(header_footer, "bold", False)))
        self._italic_toggle.setChecked(bool(getattr(header_footer, "italic", False)))
        self._set_combo_by_data(self._footer_content_combo, getattr(header_footer.footer, "content_mode", "page_number"))
        self._footer_text_edit.setText(getattr(header_footer, "footer_text", "") or "")
        self._set_combo_by_data(self._footer_alignment_combo, getattr(header_footer, "footer_alignment", "center"))
        self._header_border_toggle.setChecked(header_footer.header_border)
        suppress_selectors = default_suppress_header_footer_selectors(header_footer)
        self._hide_cover_toggle.setChecked(bool(suppress_selectors))
        self._suppress_selector_editor.set_selectors(suppress_selectors or ["pre_numbering"])
        self._page_plan.set_header_footer(header_footer)
        self._sync_scheme_combo(header_footer)

    def apply_to(self, header_footer) -> None:
        header_footer.header_mode = str(self._header_mode_combo.currentData() or "styleref")
        header_footer.header_text = self._header_text_edit.text()
        header_footer.styleref_level = int(self._styleref_level_combo.currentData() or 1)
        header_footer.font_cn = self._font_cn_combo.selected_font() or None
        header_footer.font_en = self._font_en_combo.selected_font() or None
        header_footer.size_pt = self._size_combo.current_pt()
        header_footer.bold = self._bold_toggle.isChecked()
        header_footer.italic = self._italic_toggle.isChecked()
        header_footer.footer.content_mode = str(self._footer_content_combo.currentData() or "page_number")
        header_footer.footer_text = self._footer_text_edit.text()
        header_footer.footer_alignment = str(self._footer_alignment_combo.currentData() or "center")
        header_footer.header_border = self._header_border_toggle.isChecked()
        suppress_enabled = self._hide_cover_toggle.isChecked()
        header_footer.header.hide_on_cover = suppress_enabled
        header_footer.footer.hide_on_cover = suppress_enabled
        suppress_selectors = self._suppress_selector_editor.selectors() if suppress_enabled else []
        if suppress_enabled and not suppress_selectors:
            suppress_selectors = ["pre_numbering"]
        header_footer.suppress_header_footer_selectors = suppress_selectors
        self._page_plan.apply_to(header_footer)

    def sync_dependent_state(self) -> None:
        header_mode = str(self._header_mode_combo.currentData() or "styleref")
        footer_mode = str(self._footer_content_combo.currentData() or "page_number")
        page_number_enabled = footer_mode in {"page_number", "page_number_with_text"}
        footer_text_enabled = footer_mode in {"fixed", "page_number_with_text"}

        self._header_text_row.setVisible(header_mode == "fixed")
        self._styleref_level_row.setVisible(header_mode == "styleref")
        self._header_mode_pair.updateGeometry()
        self._footer_text_row.setVisible(footer_text_enabled)
        self._footer_alignment_row.setEnabled(footer_mode != "none")

        header_outputs = header_mode != "none"
        footer_outputs = footer_mode != "none"
        typography_enabled = header_outputs or footer_outputs
        self._font_cn_row.setEnabled(typography_enabled)
        self._font_en_row.setEnabled(typography_enabled)
        self._size_row.setEnabled(typography_enabled)
        self._emphasis_row.setEnabled(typography_enabled)
        self._header_border_row.setEnabled(header_outputs)
        self._suppress_selector_row.setVisible(self._hide_cover_toggle.isChecked())
        self._suppress_selector_row.setEnabled(self._hide_cover_toggle.isChecked())

        self._page_plan.set_enabled_visible(page_number_enabled)
        self._refresh_section_preview()
        if self._owner._current_template is not None and not self._owner._is_syncing:
            self._sync_scheme_combo(self._owner._current_template.header_footer)

    def _refresh_section_preview(self) -> None:
        header_text = self._preview_header_text()
        footer_text = self._preview_footer_summary_text()
        page_text = self._preview_page_summary_text()
        hidden_text = self._preview_hidden_summary_text()
        parts = [f"页眉：{header_text}", f"页脚：{footer_text}"]
        if page_text:
            parts.append(f"页码：{page_text}")
        if hidden_text:
            parts.append(f"不显示：{hidden_text}")
        self._quick_preview_label.setText("；".join(parts))

    def _preview_header_text(self) -> str:
        mode = str(self._header_mode_combo.currentData() or "styleref")
        if mode == "none":
            return "不显示"
        if mode == "fixed":
            return self._header_text_edit.text().strip() or "固定文字未填写"
        return f"跟随 {int(self._styleref_level_combo.currentData() or 1)} 级标题"

    def _preview_excluded_sections(self) -> set[str]:
        if not self._hide_cover_toggle.isChecked():
            return set()
        selectors = self._suppress_selector_editor.selectors() or ["pre_numbering"]
        expanded: set[str] = set()
        for selector in selectors:
            if selector == "pre_numbering":
                expanded.add("pre_numbering")
            elif selector in {"cover", "statement", "authorization", "front_note"}:
                expanded.add("pre_numbering")
            elif selector in {"abstracts", "front_matter", "toc"}:
                expanded.add("front_matter")
            elif selector in {"body"}:
                expanded.add("body")
            elif selector in {"back_matter", "references", "appendix", "acknowledgment", "resume", "errata"}:
                expanded.add("back_matter")
        return expanded

    def _preview_hidden_summary_text(self) -> str:
        if not self._hide_cover_toggle.isChecked():
            return ""
        selectors = self._suppress_selector_editor.selectors() or ["pre_numbering"]
        labels = dict(SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS)
        return "、".join(labels.get(str(selector), str(selector)) for selector in selectors)

    def _preview_footer_summary_text(self) -> str:
        footer_mode = str(self._footer_content_combo.currentData() or "page_number")
        if footer_mode == "none":
            return "不显示"
        if footer_mode == "fixed":
            return self._footer_text_edit.text().strip() or "固定文字未填写"
        if footer_mode == "page_number_with_text":
            text = self._footer_text_edit.text().strip() or "固定文字未填写"
            return f"页码 + {text}"
        return "页码"

    def _preview_page_summary_text(self) -> str:
        footer_mode = str(self._footer_content_combo.currentData() or "page_number")
        if footer_mode in {"none", "fixed"}:
            return ""
        phases = self.phase_rows_to_configs()
        if not phases:
            return "未设置"
        if len(phases) == 1:
            return self._preview_single_phase_summary(phases[0])
        if len(phases) == 2:
            front, body = phases
            if list(getattr(front, "selectors", []) or []) == ["front_matter"] and list(
                getattr(body, "selectors", []) or []
            ) == ["body", "back_matter"]:
                body_suffix = "续号" if str(getattr(body, "start_mode", "restart") or "restart") == "continue" else ""
                return f"前置{self._preview_number_format_short(front)}，正文{self._preview_number_format_short(body)}{body_suffix}"
        return f"自定义 {len(phases)} 项"

    def _preview_single_phase_summary(self, phase) -> str:
        selectors = list(getattr(phase, "selectors", []) or [])
        scope = "全文" if selectors == ["all_numbered_content"] else "自定义"
        if not bool(getattr(phase, "visible", True)):
            return f"{scope}不显示"
        suffix = "续号" if str(getattr(phase, "start_mode", "restart") or "restart") == "continue" else "从 1 起"
        return f"{scope}{self._preview_number_format_short(phase)}{suffix}"

    def _preview_number_format_short(self, phase) -> str:
        return {
            "decimal": "阿拉伯",
            "upperRoman": "罗马",
            "lowerRoman": "小写罗马",
        }.get(str(getattr(phase, "number_format", "decimal") or "decimal"), "阿拉伯")

    def refresh_validation_alert(self, template: TemplateConfig | None) -> None:
        self._page_plan.refresh_validation_alert(template)

    def apply_theme(self) -> None:
        self._header_text_edit.setStyleSheet(
            build_text_input_stylesheet(get_theme(), selector="QLineEdit")
        )
        self._page_plan.apply_theme()


__all__ = [
    "HeaderFooterDetailSection",
    "default_page_number_phases",
    "default_suppress_header_footer_selectors",
    "ensure_default_page_number_phases",
    "page_number_phase_brief",
]
