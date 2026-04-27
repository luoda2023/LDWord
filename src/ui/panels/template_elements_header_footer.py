"""Header/footer section for the template elements detail pane."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.config.template import TemplateConfig
from src.qt_api import QLineEdit, QWidget, Qt
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.panels.template_elements_page_plan import (
    PageNumberPlanSection,
    PageSelectorEditor,
    SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS,
    default_page_number_phases,
    default_suppress_header_footer_selectors,
    ensure_default_page_number_phases,
    page_number_phase_brief,
)

if TYPE_CHECKING:
    from src.ui.panels.template_elements_detail import ElementsDetail


HEADER_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("styleref", "跟随章节标题"),
    ("fixed", "固定文字"),
    ("none", "不显示页眉"),
)

class HeaderFooterDetailSection:
    """Owns the header/footer controls inside ElementsDetail."""

    def __init__(self, owner: "ElementsDetail"):
        self._owner = owner

        self.section = Card(parent=owner._editor_column)
        owner._header_section = self.section
        owner._add_card_header(self.section, "panel-top", "页眉与页脚设置")
        owner._editor_layout.addWidget(self.section)
        self._build_form()

        self._page_plan = PageNumberPlanSection(owner)
        self._page_plan.export_compat_attributes(self)
        self._export_compat_attributes()

    def _export_compat_attributes(self) -> None:
        names = (
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
            "_page_number_toggle",
            "_page_number_row",
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

        self._header_mode_combo = StyledComboBox(self._owner)
        for value, label in HEADER_MODE_OPTIONS:
            self._header_mode_combo.addItem(label, value)
        self._header_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._header_mode_row = self._form_row("页眉内容", self._header_mode_combo, parent=self._inspector_form)

        self._header_text_edit = QLineEdit(self._owner)
        self._header_text_edit.textChanged.connect(self._owner._on_structure_edited)
        self._header_text_row = self._form_row("固定文字", self._header_text_edit, parent=self._inspector_form)

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
        self._typography_grid = self._inspector_form.add_grid(
            [
                [self._font_cn_row, self._size_row],
                [self._font_en_row, None],
            ],
        )

        self._page_number_toggle = ToggleSwitch(self._owner, checked=True)
        self._page_number_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._page_number_row = self._form_row("页码", self._page_number_toggle, parent=self._inspector_form)

        self._header_border_toggle = ToggleSwitch(self._owner, checked=True)
        self._header_border_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._header_border_row = self._form_row("页眉线", self._header_border_toggle, parent=self._inspector_form)

        self._hide_cover_toggle = ToggleSwitch(self._owner, checked=True)
        self._hide_cover_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._hide_cover_row = self._form_row("起始前留空", self._hide_cover_toggle, parent=self._inspector_form)
        self._page_toggle_pair = self._inspector_form.add_pair(
            self._page_number_row,
            self._header_border_row,
            self._hide_cover_row,
            column_stretches=(0, 0, 0),
        )

        self._suppress_selector_editor = PageSelectorEditor(
            self.section,
            options=SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS,
            hint_text="默认覆盖正文页码开始前的封面、声明、授权书和说明页。",
        )
        self._suppress_selector_editor.changed.connect(self._owner._on_structure_edited)
        self._suppress_selector_row = self._form_row(
            "留空范围",
            self._suppress_selector_editor,
            parent=self._inspector_form,
        )
        self._inspector_form.add_widget(self._suppress_selector_row)
        self._suppress_selector_row.set_label_alignment(Qt.AlignLeft | Qt.AlignTop)
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

    def set_header_footer(self, header_footer) -> None:
        self._set_combo_by_data(self._header_mode_combo, header_footer.header_mode)
        self._header_text_edit.setText(header_footer.header_text or "")
        self._set_combo_by_data(self._styleref_level_combo, header_footer.styleref_level)
        self._font_cn_combo.set_font_name(header_footer.font_cn or "")
        self._font_en_combo.set_font_name(header_footer.font_en or "")
        self._size_combo.set_pt(header_footer.size_pt or 12.0)
        self._page_number_toggle.setChecked(header_footer.page_number_enabled)
        self._header_border_toggle.setChecked(header_footer.header_border)
        suppress_selectors = default_suppress_header_footer_selectors(header_footer)
        self._hide_cover_toggle.setChecked(bool(suppress_selectors))
        self._suppress_selector_editor.set_selectors(suppress_selectors or ["pre_numbering"])
        self._page_plan.set_header_footer(header_footer)

    def apply_to(self, header_footer) -> None:
        header_footer.header_mode = str(self._header_mode_combo.currentData() or "styleref")
        header_footer.header_text = self._header_text_edit.text()
        header_footer.styleref_level = int(self._styleref_level_combo.currentData() or 1)
        header_footer.font_cn = self._font_cn_combo.selected_font() or None
        header_footer.font_en = self._font_en_combo.selected_font() or None
        header_footer.size_pt = self._size_combo.current_pt()
        header_footer.page_number_enabled = self._page_number_toggle.isChecked()
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
        page_number_enabled = self._page_number_toggle.isChecked()

        self._header_text_row.setVisible(header_mode == "fixed")
        self._styleref_level_row.setVisible(header_mode == "styleref")
        self._header_mode_pair.updateGeometry()

        header_outputs = header_mode != "none"
        typography_enabled = header_outputs or page_number_enabled
        self._font_cn_row.setEnabled(typography_enabled)
        self._font_en_row.setEnabled(typography_enabled)
        self._size_row.setEnabled(typography_enabled)
        self._header_border_row.setEnabled(header_outputs)
        self._suppress_selector_row.setVisible(self._hide_cover_toggle.isChecked())
        self._suppress_selector_row.setEnabled(self._hide_cover_toggle.isChecked())

        self._page_plan.set_enabled_visible(page_number_enabled)

    def refresh_validation_alert(self, template: TemplateConfig | None) -> None:
        self._page_plan.refresh_validation_alert(template)

    def apply_theme(self) -> None:
        self._page_plan.apply_theme()


__all__ = [
    "HeaderFooterDetailSection",
    "default_page_number_phases",
    "default_suppress_header_footer_selectors",
    "ensure_default_page_number_phases",
    "page_number_phase_brief",
]
