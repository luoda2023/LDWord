"""Header/footer section for the template elements detail pane."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from src.config.template import TemplateConfig
from src.config.special_title_rules import (
    special_title_selector_label,
    special_title_selector_options,
)
from src.config.header_footer_presets import (
    USER_PRESET_DIR,
    configs_equal as header_footer_configs_equal,
    detect_matching_preset as detect_matching_header_footer_preset,
    get_preset_catalog as get_header_footer_preset_catalog,
    get_preset_config as get_header_footer_preset_config,
)
from src.qt_api import QDesktopServices, QLabel, QLineEdit, QUrl, QWidget, Qt
from src.shared.ui.card import Card
from src.shared.ui.dashed_separator import DashedSeparator
from src.shared.ui.form_action_row import FormActionButtonRow
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.layout_sync import (
    refresh_layout_chain,
    refresh_layout_chain_later,
)
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.toast import Toast
from src.shared.ui.typography_controls import build_emphasis_widget
from src.ui.panels.template_elements_page_plan import (
    PAGE_NUMBER_SELECTOR_OPTIONS,
    PageNumberPlanSection,
    PageSelectorEditor,
    default_page_number_phases,
    ensure_default_page_number_phases,
    page_number_phase_brief,
)

if TYPE_CHECKING:
    from src.ui.panels.template_elements_detail import ElementsDetail


HEADER_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("styleref", "跟随章节标题"),
    ("fixed", "固定文字"),
    ("none", "不显示"),
)

FOOTER_CONTENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("none", "不显示页脚文字"),
    ("fixed", "显示固定文字"),
)

PAGE_NUMBER_POSITION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "页脚左侧"),
    ("center", "页脚居中"),
    ("right", "页脚右侧"),
)

HEADER_POSITION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "页眉左侧"),
    ("center", "页眉居中"),
    ("right", "页眉右侧"),
)

PAGE_NUMBER_DISPLAY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("plain", "1（纯数字）"),
    ("page", "第 1 页"),
    ("total", "第 1 页 / 共 10 页"),
    ("custom", "自定义"),
)

PAGE_NUMBER_TEMPLATE_BY_DISPLAY = {
    "plain": "{page}",
    "page": "第 {page} 页",
    "total": "第 {page} 页 / 共 {pages} 页",
}

FIRST_HEADER_CONTENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("inherit", "沿用普通页"),
    ("none", "不显示"),
    ("styleref", "跟随章节标题"),
    ("fixed", "固定文字"),
    ("template", "手写模板"),
)

EVEN_HEADER_CONTENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("inherit", "沿用奇数页"),
    ("none", "不显示"),
    ("styleref", "跟随章节标题"),
    ("fixed", "固定文字"),
    ("template", "手写模板"),
)

FIRST_FOOTER_CONTENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("inherit", "沿用普通页文字"),
    ("none", "不显示页脚文字"),
    ("fixed", "固定文字"),
    ("template", "文字模板"),
)

EVEN_FOOTER_CONTENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("inherit", "沿用奇数页文字"),
    ("none", "不显示页脚文字"),
    ("fixed", "固定文字"),
    ("template", "文字模板"),
)

PAGE_NUMBER_VARIANT_VISIBILITY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("inherit", "跟随编号阶段"),
    ("show", "强制显示"),
    ("hide", "隐藏"),
)

PAGE_NUMBER_VARIANT_ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("inherit", "跟随默认位置"),
    *PAGE_NUMBER_POSITION_OPTIONS,
)

PAGE_NUMBER_VARIANT_DISPLAY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("inherit", "跟随默认样式"),
    *PAGE_NUMBER_DISPLAY_OPTIONS,
)

SECTION_LINK_OPTIONS: tuple[tuple[str, str], ...] = (
    ("never", "各节分别应用模板"),
    ("preserve", "沿用原文的节间关系"),
)

CUSTOM_SECTION_EXCLUSION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("cover", "封面"),
    ("body", "其余正文"),
)

SECTION_EXCLUSION_LABELS = {
    "pre_numbering": "封面",
    "cover": "封面",
    "abstracts": "摘要",
    "front_matter": "前置部分",
    "toc": "目录",
    "body": "其余正文",
    "back_matter": "后置部分",
    "references": "参考文献",
    "appendix": "附录",
    "acknowledgment": "致谢",
    "errata": "勘误",
    "resume": "简历",
}


class HeaderFooterDetailSection:
    """Owns the header/footer controls inside ElementsDetail."""

    def __init__(self, owner: "ElementsDetail"):
        self._owner = owner
        self._active_scheme_key: str | None = None

        self._scheme_card = Card(parent=owner._editor_column)
        owner._add_card_header(self._scheme_card, "list", "页眉页脚预设")
        owner._editor_layout.addWidget(self._scheme_card)
        self._build_scheme_form()

        self._build_page_variants_form()

        self._normal_page_card = Card(parent=owner._editor_column)
        owner._add_card_header(self._normal_page_card, "panel-top", "页眉")
        owner._editor_layout.addWidget(self._normal_page_card)
        self._build_normal_page_form()

        self._footer_card = Card(parent=owner._editor_column)
        owner._add_card_header(self._footer_card, "panel-bottom", "页脚文字")
        owner._editor_layout.addWidget(self._footer_card)
        self._build_footer_form()
        self._build_footer_variant_form()
        self._build_footer_typography_form()

        self._page_number_card = Card(parent=owner._editor_column)
        owner._add_card_header(self._page_number_card, "list-ordered", "页码")
        owner._editor_layout.addWidget(self._page_number_card)
        self._build_page_number_form()
        self._build_page_number_variant_form()
        self._page_plan = PageNumberPlanSection(owner, container=self._page_number_card, embedded=True)

        self._build_section_exclusion_form()
        self._build_section_link_form()

        self._page_plan.export_compat_attributes(self)
        self.section = self._normal_page_card
        self._export_compat_attributes()

    def _export_compat_attributes(self) -> None:
        names = (
            "_scheme_combo",
            "_scheme_row",
            "_scheme_note",
            "_scheme_actions",
            "_scheme_actions_row",
            "_scheme_open_folder_btn",
            "_normal_page_card",
            "_footer_card",
            "_page_number_card",
            "_structure_card",
            "_structure_form",
            "_structure_section",
            "_normal_header_title_label",
            "_header_mode_combo",
            "_header_mode_row",
            "_header_alignment_combo",
            "_header_alignment_row",
            "_header_text_edit",
            "_header_text_row",
            "_styleref_level_combo",
            "_styleref_level_row",
            "_header_typography_title_label",
            "_font_cn_combo",
            "_font_cn_row",
            "_font_en_combo",
            "_font_en_row",
            "_size_combo",
            "_size_row",
            "_bold_toggle",
            "_italic_toggle",
            "_emphasis_row",
            "_header_typography_separator",
            "_header_typography_grid",
            "_footer_font_cn_combo",
            "_footer_font_cn_row",
            "_footer_font_en_combo",
            "_footer_font_en_row",
            "_footer_size_combo",
            "_footer_size_row",
            "_footer_bold_toggle",
            "_footer_italic_toggle",
            "_footer_emphasis_row",
            "_footer_typography_separator",
            "_footer_typography_grid",
            "_footer_form",
            "_footer_grid",
            "_normal_footer_title_label",
            "_bottom_text_mode_combo",
            "_bottom_text_mode_row",
            "_footer_content_combo",
            "_footer_content_row",
            "_footer_text_edit",
            "_footer_text_row",
            "_footer_alignment_combo",
            "_footer_alignment_row",
            "_footer_typography_title_label",
            "_page_number_enabled_toggle",
            "_page_number_enabled_row",
            "_page_number_alignment_combo",
            "_page_number_alignment_row",
            "_page_number_display_combo",
            "_page_number_display_row",
            "_header_border_toggle",
            "_header_border_row",
            "_suppress_selector_editor",
            "_suppress_selector_row",
            "_header_scope_editor",
            "_header_scope_row",
            "_footer_scope_editor",
            "_footer_scope_row",
            "_page_variants_card",
            "_page_variants_form",
            "_page_variant_switch_grid",
            "_section_link_card",
            "_section_link_form",
            "_section_link_mode_combo",
            "_section_link_mode_row",
            "_header_enabled_toggle",
            "_header_enabled_row",
            "_footer_enabled_toggle",
            "_footer_enabled_row",
            "_different_first_page_toggle",
            "_different_first_page_row",
            "_different_odd_even_toggle",
            "_different_odd_even_row",
            "_page_number_template_edit",
            "_page_number_template_row",
            "_first_page_number_visibility_combo",
            "_first_page_number_visibility_row",
            "_first_page_number_alignment_combo",
            "_first_page_number_alignment_row",
            "_first_page_number_display_combo",
            "_first_page_number_display_row",
            "_first_page_number_template_edit",
            "_first_page_number_template_row",
            "_even_page_number_visibility_combo",
            "_even_page_number_visibility_row",
            "_even_page_number_alignment_combo",
            "_even_page_number_alignment_row",
            "_even_page_number_display_combo",
            "_even_page_number_display_row",
            "_even_page_number_template_edit",
            "_even_page_number_template_row",
            "_first_header_title_label",
            "_first_header_mode_combo",
            "_first_header_mode_row",
            "_first_header_alignment_combo",
            "_first_header_alignment_row",
            "_first_header_level_combo",
            "_first_header_level_row",
            "_first_header_text_edit",
            "_first_header_text_row",
            "_first_footer_mode_combo",
            "_first_footer_mode_row",
            "_first_footer_alignment_combo",
            "_first_footer_alignment_row",
            "_first_footer_text_edit",
            "_first_footer_text_row",
            "_first_footer_title_label",
            "_first_header_variant_grid",
            "_first_footer_variant_grid",
            "_first_variant_grid",
            "_even_header_separator",
            "_even_footer_separator",
            "_even_header_title_label",
            "_even_header_mode_combo",
            "_even_header_mode_row",
            "_even_header_alignment_combo",
            "_even_header_alignment_row",
            "_even_header_level_combo",
            "_even_header_level_row",
            "_even_header_text_edit",
            "_even_header_text_row",
            "_even_footer_mode_combo",
            "_even_footer_mode_row",
            "_even_footer_alignment_combo",
            "_even_footer_alignment_row",
            "_even_footer_text_edit",
            "_even_footer_text_row",
            "_even_footer_title_label",
            "_even_header_variant_grid",
            "_even_footer_variant_grid",
            "_even_variant_grid",
            "_header_variant_separator",
            "_footer_variant_separator",
            "_page_plan_section",
            "_page_advanced_section",
            "_page_validation_mode_combo",
            "_page_missing_doc_tree_combo",
            "_page_plan_alert",
            "_page_plan_note",
            "_numbering_mode_combo",
            "_numbering_mode_row",
            "_preset_row",
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

    def _build_scheme_form(self) -> None:
        form = InspectorForm(parent=self._scheme_card)

        self._scheme_combo = StyledComboBox(self._owner)
        self._populate_scheme_combo()
        self._scheme_combo.currentIndexChanged.connect(self._on_scheme_changed)
        self._scheme_row = self._form_row("页眉页脚预设", self._scheme_combo, parent=form)
        form.add_widget(self._scheme_row)

        self._scheme_actions = FormActionButtonRow(self._owner)
        self._scheme_open_folder_btn = self._scheme_actions.add_button(
            "打开方案文件夹", "secondary"
        )
        self._scheme_open_folder_btn.clicked.connect(
            self._on_scheme_open_folder_requested
        )
        self._scheme_actions_row = self._form_row("方案操作", self._scheme_actions, parent=form)
        form.add_widget(self._scheme_actions_row)

        self._scheme_note = self._group_note("", form)
        self._scheme_note.setVisible(False)

        self._scheme_card.add_widget(form)
        self._quick_preview_label = self._group_note("", form)
        form.add_widget(self._quick_preview_label)
        self._quick_preview_label.setVisible(True)

    def _populate_scheme_combo(self) -> None:
        current_key = self._scheme_combo.currentData() if hasattr(self, "_scheme_combo") else None
        self._scheme_combo.blockSignals(True)
        try:
            self._scheme_combo.set_display_text_override(None)
            self._scheme_combo.clear()
            for key, entry in get_header_footer_preset_catalog().items():
                label = str(entry.get("label", key))
                is_user = entry.get("source") == "user"
                self._scheme_combo.add_badged_item(
                    label,
                    key,
                    badge_text="自定" if is_user else "内置",
                    badge_kind="user" if is_user else "builtin",
                )
            if current_key:
                self._scheme_combo.setCurrentIndex(self._find_scheme_index(str(current_key)))
            else:
                self._scheme_combo.setCurrentIndex(-1)
        finally:
            self._scheme_combo.blockSignals(False)

    def _find_scheme_index(self, key: str | None) -> int:
        if not key:
            return -1
        for index in range(self._scheme_combo.count()):
            if self._scheme_combo.itemData(index) == key:
                return index
        return -1

    def _scheme_entry_label(self, key: str | None) -> str:
        if not key:
            return ""
        entry = get_header_footer_preset_catalog().get(key)
        return str(entry.get("label", key) if entry else key)

    def _scheme_entry_source_label(self, key: str | None) -> str:
        if not key:
            return ""
        entry = get_header_footer_preset_catalog().get(key)
        if not entry:
            return ""
        return "用户" if entry.get("source") == "user" else "内置"

    def _build_normal_page_form(self) -> None:
        self._normal_header_title_label = self._section_title("普通页页眉", self._normal_page_card)
        self._normal_page_card.add_widget(self._normal_header_title_label)

        form = InspectorForm(parent=self._normal_page_card)

        self._header_mode_combo = StyledComboBox(self._owner)
        for value, label in HEADER_MODE_OPTIONS:
            self._header_mode_combo.addItem(label, value)
        self._header_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._header_mode_row = self._form_row("页眉内容", self._header_mode_combo, parent=form)

        self._header_alignment_combo = self._options_combo(HEADER_POSITION_OPTIONS)
        self._header_alignment_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._header_alignment_row = self._form_row("页眉位置", self._header_alignment_combo, parent=form)

        self._header_text_edit = QLineEdit(self._owner)
        self._header_text_edit.textChanged.connect(self._owner._on_structure_edited)
        self._header_text_row = self._form_row("顶部文字", self._header_text_edit, parent=form)

        self._styleref_level_combo = self._level_combo()
        self._styleref_level_row = self._form_row("标题级别", self._styleref_level_combo, parent=form)
        self._header_border_toggle = ToggleSwitch(self._owner, checked=True)
        self._header_border_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._header_border_row = self._form_row("顶部横线", self._header_border_toggle, parent=form)

        self._normal_page_grid = form.add_grid(
            [
                [self._header_mode_row, self._header_alignment_row],
                [self._styleref_level_row, self._header_text_row],
                [self._header_border_row],
            ],
        )
        self._normal_page_card.add_widget(form)
        self._build_header_variant_form()
        self._build_header_typography_form()

    def _build_header_variant_form(self) -> None:
        self._header_variant_separator = DashedSeparator(parent=self._normal_page_card)
        self._normal_page_card.add_widget(self._header_variant_separator)

        form = InspectorForm(parent=self._normal_page_card)

        self._even_header_title_label = self._section_title("偶数页页眉", form)
        form.add_widget(self._even_header_title_label)

        self._even_header_mode_combo = self._options_combo(EVEN_HEADER_CONTENT_OPTIONS)
        self._even_header_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._even_header_mode_row = self._form_row(
            "页眉内容",
            self._even_header_mode_combo,
            parent=form,
        )
        self._even_header_alignment_combo = self._options_combo(HEADER_POSITION_OPTIONS)
        self._even_header_alignment_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._even_header_alignment_row = self._form_row(
            "页眉位置",
            self._even_header_alignment_combo,
            parent=form,
        )
        self._even_header_level_combo = self._level_combo()
        self._even_header_level_row = self._form_row("标题级别", self._even_header_level_combo, parent=form)
        self._even_header_text_edit = QLineEdit(self._owner)
        self._even_header_text_edit.setPlaceholderText("固定文字或模板")
        self._even_header_text_edit.textChanged.connect(self._owner._on_structure_edited)
        self._even_header_text_row = self._form_row(
            "页眉文字",
            self._even_header_text_edit,
            parent=form,
        )

        self._even_header_variant_grid = form.add_grid(
            [
                [self._even_header_mode_row, self._even_header_alignment_row],
                [self._even_header_level_row, self._even_header_text_row],
            ],
        )

        self._even_header_separator = DashedSeparator(parent=form)
        form.add_widget(self._even_header_separator)
        self._first_header_title_label = self._section_title("首页页眉", form)
        form.add_widget(self._first_header_title_label)

        self._first_header_mode_combo = self._options_combo(FIRST_HEADER_CONTENT_OPTIONS)
        self._first_header_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._first_header_mode_row = self._form_row(
            "页眉内容",
            self._first_header_mode_combo,
            parent=form,
        )
        self._first_header_alignment_combo = self._options_combo(HEADER_POSITION_OPTIONS)
        self._first_header_alignment_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._first_header_alignment_row = self._form_row(
            "页眉位置",
            self._first_header_alignment_combo,
            parent=form,
        )
        self._first_header_level_combo = self._level_combo()
        self._first_header_level_row = self._form_row("标题级别", self._first_header_level_combo, parent=form)
        self._first_header_text_edit = QLineEdit(self._owner)
        self._first_header_text_edit.setPlaceholderText("固定文字或模板")
        self._first_header_text_edit.textChanged.connect(self._owner._on_structure_edited)
        self._first_header_text_row = self._form_row(
            "页眉文字",
            self._first_header_text_edit,
            parent=form,
        )

        self._first_header_variant_grid = form.add_grid(
            [
                [self._first_header_mode_row, self._first_header_alignment_row],
                [self._first_header_level_row, self._first_header_text_row],
            ],
        )
        self._first_variant_grid = self._first_header_variant_grid
        self._even_variant_grid = self._even_header_variant_grid
        self._normal_page_card.add_widget(form)

    def _build_footer_form(self) -> None:
        self._normal_footer_title_label = self._section_title("普通页页脚文字", self._footer_card)
        self._footer_card.add_widget(self._normal_footer_title_label)

        self._footer_form = InspectorForm(parent=self._footer_card)

        self._bottom_text_mode_combo = StyledComboBox(self._owner)
        for value, label in FOOTER_CONTENT_OPTIONS:
            self._bottom_text_mode_combo.addItem(label, value)
        self._bottom_text_mode_combo.currentIndexChanged.connect(self._on_footer_content_mode_changed)
        self._bottom_text_mode_row = self._form_row("文字内容", self._bottom_text_mode_combo, parent=self._footer_form)
        self._footer_content_combo = self._bottom_text_mode_combo
        self._footer_content_row = self._bottom_text_mode_row

        self._footer_alignment_combo = StyledComboBox(self._owner)
        for value, label in PAGE_NUMBER_POSITION_OPTIONS:
            self._footer_alignment_combo.addItem(label, value)
        self._footer_alignment_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._footer_alignment_row = self._form_row("文字位置", self._footer_alignment_combo, parent=self._footer_form)

        self._footer_text_edit = QLineEdit(self._owner)
        self._footer_text_edit.textChanged.connect(self._owner._on_structure_edited)
        self._footer_text_row = self._form_row("页脚文字", self._footer_text_edit, parent=self._footer_form)

        self._footer_grid = self._footer_form.add_grid(
            [
                [self._bottom_text_mode_row, self._footer_alignment_row],
                [self._footer_text_row],
            ],
        )
        self._footer_card.add_widget(self._footer_form)

    def _build_page_number_form(self) -> None:
        form = InspectorForm(parent=self._page_number_card)

        self._page_number_enabled_toggle = ToggleSwitch(self._owner, checked=True)
        self._page_number_enabled_toggle.toggled_signal.connect(self._on_page_number_enabled_toggled)
        self._page_number_enabled_row = self._form_row("显示页码", self._page_number_enabled_toggle, parent=form)

        self._page_number_alignment_combo = self._options_combo(
            PAGE_NUMBER_POSITION_OPTIONS
        )
        self._page_number_alignment_combo.currentIndexChanged.connect(
            self._owner._on_structure_edited
        )
        self._page_number_alignment_row = self._form_row(
            "页码位置",
            self._page_number_alignment_combo,
            parent=form,
        )

        self._page_number_display_combo = StyledComboBox(self._owner)
        for value, label in PAGE_NUMBER_DISPLAY_OPTIONS:
            self._page_number_display_combo.addItem(label, value)
        self._page_number_display_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._page_number_display_row = self._form_row("页码样式", self._page_number_display_combo, parent=form)

        self._page_number_template_edit = QLineEdit(self._owner)
        self._page_number_template_edit.setPlaceholderText("如：第 {page} 页 / 共 {pages} 页")
        self._page_number_template_edit.textChanged.connect(self._owner._on_structure_edited)
        self._page_number_template_row = self._form_row(
            "自定义样式",
            self._page_number_template_edit,
            parent=form,
        )

        self._page_number_grid = form.add_grid(
            [
                [self._page_number_enabled_row, self._page_number_alignment_row],
                [self._page_number_display_row, self._page_number_template_row],
            ],
        )
        self._page_number_card.add_widget(form)

    def _build_page_number_variant_form(self) -> None:
        self._page_number_variant_separator = DashedSeparator(parent=self._page_number_card)
        self._page_number_card.add_widget(self._page_number_variant_separator)
        form = InspectorForm(parent=self._page_number_card)

        self._even_page_number_title_label = self._section_title("偶数页页码", form)
        form.add_widget(self._even_page_number_title_label)
        self._even_page_number_visibility_combo = self._options_combo(
            PAGE_NUMBER_VARIANT_VISIBILITY_OPTIONS
        )
        self._even_page_number_visibility_combo.currentIndexChanged.connect(
            self._owner._on_structure_edited
        )
        self._even_page_number_visibility_row = self._form_row(
            "显示策略",
            self._even_page_number_visibility_combo,
            parent=form,
        )
        self._even_page_number_alignment_combo = self._options_combo(
            PAGE_NUMBER_VARIANT_ALIGNMENT_OPTIONS
        )
        self._even_page_number_alignment_combo.currentIndexChanged.connect(
            self._owner._on_structure_edited
        )
        self._even_page_number_alignment_row = self._form_row(
            "页码位置",
            self._even_page_number_alignment_combo,
            parent=form,
        )
        self._even_page_number_display_combo = self._options_combo(
            PAGE_NUMBER_VARIANT_DISPLAY_OPTIONS
        )
        self._even_page_number_display_combo.currentIndexChanged.connect(
            self._owner._on_structure_edited
        )
        self._even_page_number_display_row = self._form_row(
            "页码样式",
            self._even_page_number_display_combo,
            parent=form,
        )
        self._even_page_number_template_edit = QLineEdit(self._owner)
        self._even_page_number_template_edit.setPlaceholderText("如：第 {page} 页")
        self._even_page_number_template_edit.textChanged.connect(
            self._owner._on_structure_edited
        )
        self._even_page_number_template_row = self._form_row(
            "自定义样式",
            self._even_page_number_template_edit,
            parent=form,
        )
        self._even_page_number_variant_grid = form.add_grid(
            [
                [
                    self._even_page_number_visibility_row,
                    self._even_page_number_alignment_row,
                ],
                [
                    self._even_page_number_display_row,
                    self._even_page_number_template_row,
                ],
            ]
        )

        self._page_number_even_first_separator = DashedSeparator(parent=form)
        form.add_widget(self._page_number_even_first_separator)
        self._first_page_number_title_label = self._section_title("首页页码", form)
        form.add_widget(self._first_page_number_title_label)
        self._first_page_number_visibility_combo = self._options_combo(
            PAGE_NUMBER_VARIANT_VISIBILITY_OPTIONS
        )
        self._first_page_number_visibility_combo.currentIndexChanged.connect(
            self._owner._on_structure_edited
        )
        self._first_page_number_visibility_row = self._form_row(
            "显示策略",
            self._first_page_number_visibility_combo,
            parent=form,
        )
        self._first_page_number_alignment_combo = self._options_combo(
            PAGE_NUMBER_VARIANT_ALIGNMENT_OPTIONS
        )
        self._first_page_number_alignment_combo.currentIndexChanged.connect(
            self._owner._on_structure_edited
        )
        self._first_page_number_alignment_row = self._form_row(
            "页码位置",
            self._first_page_number_alignment_combo,
            parent=form,
        )
        self._first_page_number_display_combo = self._options_combo(
            PAGE_NUMBER_VARIANT_DISPLAY_OPTIONS
        )
        self._first_page_number_display_combo.currentIndexChanged.connect(
            self._owner._on_structure_edited
        )
        self._first_page_number_display_row = self._form_row(
            "页码样式",
            self._first_page_number_display_combo,
            parent=form,
        )
        self._first_page_number_template_edit = QLineEdit(self._owner)
        self._first_page_number_template_edit.setPlaceholderText("如：第 {page} 页")
        self._first_page_number_template_edit.textChanged.connect(
            self._owner._on_structure_edited
        )
        self._first_page_number_template_row = self._form_row(
            "自定义样式",
            self._first_page_number_template_edit,
            parent=form,
        )
        self._first_page_number_variant_grid = form.add_grid(
            [
                [
                    self._first_page_number_visibility_row,
                    self._first_page_number_alignment_row,
                ],
                [
                    self._first_page_number_display_row,
                    self._first_page_number_template_row,
                ],
            ]
        )
        self._page_number_card.add_widget(form)

    def _build_footer_variant_form(self) -> None:
        self._footer_variant_separator = DashedSeparator(parent=self._footer_card)
        self._footer_card.add_widget(self._footer_variant_separator)

        form = InspectorForm(parent=self._footer_card)

        self._even_footer_title_label = self._section_title("偶数页页脚文字", form)
        form.add_widget(self._even_footer_title_label)

        self._even_footer_mode_combo = self._options_combo(EVEN_FOOTER_CONTENT_OPTIONS)
        self._even_footer_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._even_footer_mode_row = self._form_row(
            "文字内容",
            self._even_footer_mode_combo,
            parent=form,
        )
        self._even_footer_alignment_combo = self._options_combo(PAGE_NUMBER_POSITION_OPTIONS)
        self._even_footer_alignment_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._even_footer_alignment_row = self._form_row(
            "文字位置",
            self._even_footer_alignment_combo,
            parent=form,
        )
        self._even_footer_text_edit = QLineEdit(self._owner)
        self._even_footer_text_edit.setPlaceholderText("固定文字或模板")
        self._even_footer_text_edit.textChanged.connect(self._owner._on_structure_edited)
        self._even_footer_text_row = self._form_row(
            "页脚文字",
            self._even_footer_text_edit,
            parent=form,
        )

        self._even_footer_variant_grid = form.add_grid(
            [
                [self._even_footer_mode_row, self._even_footer_alignment_row],
                [self._even_footer_text_row],
            ],
        )

        self._even_footer_separator = DashedSeparator(parent=form)
        form.add_widget(self._even_footer_separator)
        self._first_footer_title_label = self._section_title("首页页脚文字", form)
        form.add_widget(self._first_footer_title_label)

        self._first_footer_mode_combo = self._options_combo(FIRST_FOOTER_CONTENT_OPTIONS)
        self._first_footer_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._first_footer_mode_row = self._form_row(
            "文字内容",
            self._first_footer_mode_combo,
            parent=form,
        )
        self._first_footer_alignment_combo = self._options_combo(PAGE_NUMBER_POSITION_OPTIONS)
        self._first_footer_alignment_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._first_footer_alignment_row = self._form_row(
            "文字位置",
            self._first_footer_alignment_combo,
            parent=form,
        )
        self._first_footer_text_edit = QLineEdit(self._owner)
        self._first_footer_text_edit.setPlaceholderText("固定文字或模板")
        self._first_footer_text_edit.textChanged.connect(self._owner._on_structure_edited)
        self._first_footer_text_row = self._form_row(
            "页脚文字",
            self._first_footer_text_edit,
            parent=form,
        )

        self._first_footer_variant_grid = form.add_grid(
            [
                [self._first_footer_mode_row, self._first_footer_alignment_row],
                [self._first_footer_text_row],
            ],
        )
        self._first_variant_rows = (
            self._first_header_mode_row,
            self._first_header_alignment_row,
            self._first_header_level_row,
            self._first_header_text_row,
            self._first_footer_mode_row,
            self._first_footer_alignment_row,
            self._first_footer_text_row,
        )
        self._even_variant_rows = (
            self._even_header_mode_row,
            self._even_header_alignment_row,
            self._even_header_level_row,
            self._even_header_text_row,
            self._even_footer_mode_row,
            self._even_footer_alignment_row,
            self._even_footer_text_row,
        )
        self._footer_card.add_widget(form)

    def _build_header_typography_form(self) -> None:
        self._header_typography_separator = DashedSeparator(parent=self._normal_page_card)
        self._normal_page_card.add_widget(self._header_typography_separator)
        self._header_typography_title_label = self._section_title("页眉样式", self._normal_page_card)
        self._normal_page_card.add_widget(self._header_typography_title_label)

        form = InspectorForm(parent=self._normal_page_card)
        controls = self._build_typography_controls(form)
        self._font_cn_combo = controls["font_cn"]
        self._font_cn_row = controls["font_cn_row"]
        self._font_en_combo = controls["font_en"]
        self._font_en_row = controls["font_en_row"]
        self._size_combo = controls["size"]
        self._size_row = controls["size_row"]
        self._bold_toggle = controls["bold"]
        self._italic_toggle = controls["italic"]
        self._emphasis_row = controls["emphasis_row"]
        self._header_typography_grid = controls["grid"]
        self._typography_grid = self._header_typography_grid
        self._normal_page_card.add_widget(form)

    def _build_footer_typography_form(self) -> None:
        self._footer_typography_separator = DashedSeparator(parent=self._footer_card)
        self._footer_card.add_widget(self._footer_typography_separator)
        self._footer_typography_title_label = self._section_title("页脚样式", self._footer_card)
        self._footer_card.add_widget(self._footer_typography_title_label)

        form = InspectorForm(parent=self._footer_card)
        controls = self._build_typography_controls(form)
        self._footer_font_cn_combo = controls["font_cn"]
        self._footer_font_cn_row = controls["font_cn_row"]
        self._footer_font_en_combo = controls["font_en"]
        self._footer_font_en_row = controls["font_en_row"]
        self._footer_size_combo = controls["size"]
        self._footer_size_row = controls["size_row"]
        self._footer_bold_toggle = controls["bold"]
        self._footer_italic_toggle = controls["italic"]
        self._footer_emphasis_row = controls["emphasis_row"]
        self._footer_typography_grid = controls["grid"]
        self._footer_card.add_widget(form)

    def _build_typography_controls(self, form: InspectorForm) -> dict[str, QWidget]:
        font_cn = FontCombo(lang="cn", parent=self._owner)
        font_cn.font_changed.connect(self._owner._on_structure_edited)
        font_cn_row = self._form_row("中文字体", font_cn, parent=form)

        font_en = FontCombo(lang="en", parent=self._owner)
        font_en.font_changed.connect(self._owner._on_structure_edited)
        font_en_row = self._form_row("英文字体", font_en, parent=form)

        size = SizeCombo(self._owner)
        size.size_changed.connect(self._owner._on_structure_edited)
        size.currentTextChanged.connect(self._owner._on_structure_edited)
        size_row = self._form_row("字号", size, parent=form)

        bold = ToggleSwitch(self._owner, checked=False)
        bold.toggled.connect(self._owner._on_structure_edited)
        italic = ToggleSwitch(self._owner, checked=False)
        italic.toggled.connect(self._owner._on_structure_edited)
        emphasis_row = self._form_row(
            "字形",
            build_emphasis_widget(self._owner, bold, italic),
            parent=form,
        )
        grid = form.add_grid(
            [
                [font_cn_row, size_row],
                [font_en_row, emphasis_row],
            ],
        )
        return {
            "font_cn": font_cn,
            "font_cn_row": font_cn_row,
            "font_en": font_en,
            "font_en_row": font_en_row,
            "size": size,
            "size_row": size_row,
            "bold": bold,
            "italic": italic,
            "emphasis_row": emphasis_row,
            "grid": grid,
        }

    def _build_section_exclusion_form(self) -> None:
        # Scope controls belong to the output channel they affect.  Compatibility
        # aliases remain available to older tests/adapters, but no standalone
        # "不显示页面" card is created.
        self._header_scope_separator = DashedSeparator(parent=self._normal_page_card)
        self._normal_page_card.add_widget(self._header_scope_separator)
        self._header_scope_form = InspectorForm(parent=self._normal_page_card)
        self._header_scope_editor = PageSelectorEditor(
            self._header_scope_form,
            options=CUSTOM_SECTION_EXCLUSION_OPTIONS,
            hint_text="",
            allow_custom_input=False,
        )
        self._header_scope_editor.changed.connect(self._owner._on_structure_edited)
        self._header_scope_row = self._form_row(
            "隐藏页眉范围",
            self._header_scope_editor,
            parent=self._header_scope_form,
        )
        self._header_scope_form.add_widget(self._header_scope_row)
        self._header_scope_row.set_label_alignment(Qt.AlignLeft | Qt.AlignTop)
        self._normal_page_card.add_widget(self._header_scope_form)

        self._footer_scope_separator = DashedSeparator(parent=self._footer_card)
        self._footer_card.add_widget(self._footer_scope_separator)
        self._footer_scope_form = InspectorForm(parent=self._footer_card)
        self._footer_scope_editor = PageSelectorEditor(
            self._footer_scope_form,
            options=CUSTOM_SECTION_EXCLUSION_OPTIONS,
            hint_text="",
            allow_custom_input=False,
        )
        self._footer_scope_editor.changed.connect(self._owner._on_structure_edited)
        self._footer_scope_row = self._form_row(
            "隐藏页脚文字范围",
            self._footer_scope_editor,
            parent=self._footer_scope_form,
        )
        self._footer_scope_form.add_widget(self._footer_scope_row)
        self._footer_scope_row.set_label_alignment(Qt.AlignLeft | Qt.AlignTop)
        self._footer_card.add_widget(self._footer_scope_form)

        self._structure_card = self._normal_page_card
        self._structure_form = self._header_scope_form
        self._structure_section = self._normal_page_card
        self._suppress_selector_editor = self._header_scope_editor
        self._suppress_selector_row = self._header_scope_row

    def _build_page_variants_form(self) -> None:
        self._page_variants_card = Card(parent=self._owner._editor_column)
        self._owner._add_card_header(self._page_variants_card, "copy", "首页与奇偶页")
        self._page_variants_form = InspectorForm(parent=self._page_variants_card)

        self._header_enabled_toggle = ToggleSwitch(self._owner, checked=True)
        self._header_enabled_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._header_enabled_row = self._form_row(
            "开启页眉",
            self._header_enabled_toggle,
            parent=self._page_variants_form,
        )

        self._footer_enabled_toggle = ToggleSwitch(self._owner, checked=True)
        self._footer_enabled_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._footer_enabled_row = self._form_row(
            "开启页脚文字",
            self._footer_enabled_toggle,
            parent=self._page_variants_form,
        )

        self._different_first_page_toggle = ToggleSwitch(self._owner, checked=False)
        self._different_first_page_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._different_first_page_row = self._form_row(
            "每个分节的首页不同",
            self._different_first_page_toggle,
            parent=self._page_variants_form,
        )

        self._different_odd_even_toggle = ToggleSwitch(self._owner, checked=False)
        self._different_odd_even_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._different_odd_even_row = self._form_row(
            "奇偶页不同",
            self._different_odd_even_toggle,
            parent=self._page_variants_form,
        )

        self._page_variant_switch_grid = self._page_variants_form.add_grid(
            [
                [self._header_enabled_row, self._footer_enabled_row],
                [self._different_first_page_row, self._different_odd_even_row],
            ],
        )

        self._page_variants_card.add_widget(self._page_variants_form)
        self._owner._editor_layout.addWidget(self._page_variants_card)

    def _build_section_link_form(self) -> None:
        self._section_link_card = Card(parent=self._owner._editor_column)
        self._owner._add_card_header(
            self._section_link_card,
            "workflow",
            "跨分节处理",
        )
        self._section_link_form = InspectorForm(parent=self._section_link_card)
        self._section_link_mode_combo = self._options_combo(SECTION_LINK_OPTIONS)
        self._section_link_mode_combo.currentIndexChanged.connect(
            self._owner._on_structure_edited
        )
        self._section_link_mode_row = self._form_row(
            "不同分节如何处理",
            self._section_link_mode_combo,
            parent=self._section_link_form,
        )
        self._section_link_form.add_widget(self._section_link_mode_row)
        self._section_link_card.add_widget(self._section_link_form)
        self._owner._editor_layout.addWidget(self._section_link_card)

    def _options_combo(self, options: tuple[tuple[str, str], ...]) -> StyledComboBox:
        combo = StyledComboBox(self._owner)
        for value, label in options:
            combo.addItem(label, value)
        return combo

    def _level_combo(self) -> StyledComboBox:
        combo = StyledComboBox(self._owner)
        for level in range(1, 7):
            combo.addItem(f"{level} 级", level)
        combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        return combo

    def _section_title(self, text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName("tpl_form_section_title")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._apply_section_title_theme(label)
        bind_theme(label, lambda: self._apply_section_title_theme(label))
        return label

    def _apply_section_title_theme(self, label: QLabel) -> None:
        theme = get_theme()
        label.setStyleSheet(
            f"font-size: {theme.font_size_lg}px; font-weight: bold; color: {theme.text_primary};"
        )

    def _form_row(
        self,
        label: str,
        widget: QWidget,
        *,
        suffix_widget: QWidget | None = None,
        parent,
    ) -> QWidget:
        return template_form_row(label, widget, suffix_widget=suffix_widget, parent=parent)

    def _refresh_layout_chain(self, start: QWidget | None = None) -> None:
        refresh_layout_chain(start or self._owner._editor_column)

    def _refresh_dependent_layout(self) -> None:
        try:
            for widget in (
                self._normal_page_card,
                self._footer_card,
                self._page_number_card,
                self._structure_card,
                self._page_variants_card,
                self._owner._editor_column,
            ):
                self._refresh_layout_chain(widget)
        except RuntimeError:
            pass

    def _group_note(self, text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
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

    def _set_bottom_text_and_page_number_from_mode(self, mode: str) -> None:
        mode = str(mode or "page_number")
        text_mode = "fixed" if mode in {"fixed", "page_number_with_text"} else "none"
        self._set_combo_by_data(self._bottom_text_mode_combo, text_mode)

    def _combined_footer_content_mode(self) -> str:
        mode = str(self._bottom_text_mode_combo.currentData() or "none")
        if mode in {"none", "fixed"}:
            return mode
        return "none"

    def _footer_mode_has_page_number(self) -> bool:
        return self._page_number_enabled_toggle.isChecked()

    def _footer_mode_has_fixed_text(self) -> bool:
        return self._combined_footer_content_mode() == "fixed"

    def _sync_page_number_toggle_from_footer_mode(self) -> None:
        return

    def _on_footer_content_mode_changed(self, *_args) -> None:
        self._owner._on_structure_edited()

    def _on_page_number_enabled_toggled(self, checked: bool) -> None:
        self._owner._on_structure_edited()

    def _set_page_number_display_from_template(self, template: str) -> None:
        template = str(template or "{page}").strip() or "{page}"
        for key, candidate in PAGE_NUMBER_TEMPLATE_BY_DISPLAY.items():
            if template == candidate:
                self._set_combo_by_data(self._page_number_display_combo, key)
                self._page_number_template_edit.setText(template)
                return
        self._set_combo_by_data(self._page_number_display_combo, "custom")
        self._page_number_template_edit.setText(template)

    def _selected_page_number_template(self) -> str:
        display = str(self._page_number_display_combo.currentData() or "plain")
        if display != "custom":
            return PAGE_NUMBER_TEMPLATE_BY_DISPLAY.get(display, "{page}")
        return self._page_number_template_edit.text().strip() or "{page}"

    def _page_number_display_is_custom(self) -> bool:
        return str(self._page_number_display_combo.currentData() or "plain") == "custom"

    def _set_page_number_variant_controls(
        self,
        variant,
        visibility_combo: StyledComboBox,
        alignment_combo: StyledComboBox,
        display_combo: StyledComboBox,
        template_edit: QLineEdit,
    ) -> None:
        self._set_combo_by_data(
            visibility_combo,
            str(getattr(variant, "visibility", "inherit") or "inherit"),
        )
        self._set_combo_by_data(
            alignment_combo,
            str(getattr(variant, "alignment", "inherit") or "inherit"),
        )
        template = str(getattr(variant, "template", "") or "").strip()
        if not template:
            self._set_combo_by_data(display_combo, "inherit")
            template_edit.setText("")
            return
        for key, candidate in PAGE_NUMBER_TEMPLATE_BY_DISPLAY.items():
            if template == candidate:
                self._set_combo_by_data(display_combo, key)
                template_edit.setText(template)
                return
        self._set_combo_by_data(display_combo, "custom")
        template_edit.setText(template)

    def _selected_page_number_variant_template(
        self,
        display_combo: StyledComboBox,
        template_edit: QLineEdit,
    ) -> str:
        display = str(display_combo.currentData() or "inherit")
        if display == "inherit":
            return ""
        if display != "custom":
            return PAGE_NUMBER_TEMPLATE_BY_DISPLAY.get(display, "{page}")
        return template_edit.text().strip() or "{page}"

    def _apply_page_number_variant_controls(
        self,
        variant,
        visibility_combo: StyledComboBox,
        alignment_combo: StyledComboBox,
        display_combo: StyledComboBox,
        template_edit: QLineEdit,
    ) -> None:
        if variant is None:
            return
        variant.visibility = str(visibility_combo.currentData() or "inherit")
        variant.alignment = str(alignment_combo.currentData() or "inherit")
        variant.template = self._selected_page_number_variant_template(
            display_combo,
            template_edit,
        )

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
        scheme = str(self._scheme_combo.currentData() or "")
        if not scheme:
            return
        self._apply_scheme(scheme)

    def _apply_scheme(self, scheme: str) -> None:
        preset = get_header_footer_preset_config(scheme)
        if preset is None:
            return
        previous_syncing = self._owner._is_syncing
        self._owner._is_syncing = True
        try:
            self._active_scheme_key = scheme
            self._set_header_footer_controls(preset, sync_scheme=False)
        finally:
            self._owner._is_syncing = previous_syncing
        self._owner._on_structure_edited()

    def _sync_scheme_combo(self, header_footer) -> None:
        preferred_key = self._active_scheme_key
        matched_key = (
            preferred_key
            if preferred_key and self._scheme_matches_current(preferred_key, header_footer)
            else detect_matching_header_footer_preset(header_footer)
        )
        if matched_key:
            self._active_scheme_key = matched_key
            self._set_scheme_combo_quietly(matched_key, display_override=None)
            self._refresh_scheme_action_state(header_footer)
            return

        active_key = self._active_scheme_key
        if active_key and active_key not in get_header_footer_preset_catalog():
            active_key = None
            self._active_scheme_key = None
        if active_key:
            label = self._scheme_entry_label(active_key)
            source = self._scheme_entry_source_label(active_key)
            display = f"{label}（{source}，已修改）"
        else:
            display = "当前配置（自定义）"
        self._set_scheme_combo_quietly(None, display_override=display)
        self._refresh_scheme_action_state(header_footer)

    def _set_scheme_combo_quietly(self, scheme: str | None, *, display_override: str | None = None) -> None:
        previous_syncing = self._owner._is_syncing
        self._owner._is_syncing = True
        try:
            self._scheme_combo.blockSignals(True)
            try:
                index = self._find_scheme_index(scheme)
                self._scheme_combo.setCurrentIndex(index)
                self._scheme_combo.set_display_text_override(display_override)
                self._scheme_combo.setToolTip(display_override or (self._scheme_combo.itemText(index) if index >= 0 else ""))
            finally:
                self._scheme_combo.blockSignals(False)
        finally:
            self._owner._is_syncing = previous_syncing

    def _current_header_footer_config(self):
        if self._owner._current_template is None:
            return None
        header_footer = deepcopy(self._owner._current_template.header_footer)
        self.apply_to(header_footer)
        return header_footer

    def _scheme_matches_current(self, scheme: str | None, header_footer=None) -> bool:
        if not scheme:
            return False
        preset = get_header_footer_preset_config(scheme)
        if preset is None:
            return False
        current = header_footer or self._current_header_footer_config()
        return header_footer_configs_equal(current, preset)

    def _refresh_scheme_action_state(self, header_footer=None) -> None:
        if hasattr(self, "_scheme_open_folder_btn"):
            self._scheme_open_folder_btn.setEnabled(True)

    def _on_scheme_open_folder_requested(self) -> None:
        USER_PRESET_DIR.mkdir(parents=True, exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(USER_PRESET_DIR))):
            Toast.show_error(f"无法打开页眉页脚方案文件夹: {USER_PRESET_DIR}")

    def _set_variant_control_values(
        self,
        header_combo: StyledComboBox,
        header_alignment_combo: StyledComboBox,
        header_level_combo: StyledComboBox,
        header_text: QLineEdit,
        footer_combo: StyledComboBox,
        footer_alignment_combo: StyledComboBox,
        footer_text: QLineEdit,
        *,
        header_mode: str,
        footer_mode: str,
        header_alignment: str = "center",
        header_level: int = 1,
        footer_alignment: str = "center",
        header_value: str = "",
        footer_value: str = "",
    ) -> None:
        self._set_combo_by_data(header_combo, header_mode)
        self._set_combo_by_data(header_alignment_combo, header_alignment)
        self._set_combo_by_data(header_level_combo, max(1, int(header_level or 1)))
        header_text.setText(header_value)
        self._set_combo_by_data(footer_combo, footer_mode)
        self._set_combo_by_data(footer_alignment_combo, footer_alignment)
        footer_text.setText(footer_value)

    def _set_variant_controls(
        self,
        variant,
        header_combo: StyledComboBox,
        header_alignment_combo: StyledComboBox,
        header_level_combo: StyledComboBox,
        header_text: QLineEdit,
        footer_combo: StyledComboBox,
        footer_alignment_combo: StyledComboBox,
        footer_text: QLineEdit,
        *,
        default_header_mode: str,
        default_footer_mode: str,
    ) -> None:
        header_content = getattr(variant, "header", None)
        footer_content = getattr(variant, "footer", None)
        self._set_variant_control_values(
            header_combo,
            header_alignment_combo,
            header_level_combo,
            header_text,
            footer_combo,
            footer_alignment_combo,
            footer_text,
            header_mode=str(getattr(header_content, "mode", default_header_mode) or default_header_mode),
            footer_mode=str(getattr(footer_content, "mode", default_footer_mode) or default_footer_mode),
            header_alignment=str(getattr(header_content, "alignment", "center") or "center"),
            header_level=max(1, int(getattr(header_content, "styleref_level", 1) or 1)),
            footer_alignment=str(getattr(footer_content, "alignment", "center") or "center"),
            header_value=self._content_edit_value(header_content),
            footer_value=self._content_edit_value(footer_content),
        )

    def _content_edit_value(self, content) -> str:
        mode = str(getattr(content, "mode", "inherit") or "inherit")
        if mode == "template":
            return str(getattr(content, "template", "") or "")
        return str(getattr(content, "fixed_text", "") or "")

    def _apply_variant_controls(
        self,
        variant,
        header_combo: StyledComboBox,
        header_alignment_combo: StyledComboBox,
        header_level_combo: StyledComboBox,
        header_text: QLineEdit,
        footer_combo: StyledComboBox,
        footer_alignment_combo: StyledComboBox,
        footer_text: QLineEdit,
    ) -> None:
        if variant is None:
            return
        self._apply_content_control(
            getattr(variant, "header", None),
            str(header_combo.currentData() or "inherit"),
            header_text.text(),
            default_alignment=str(header_alignment_combo.currentData() or "center"),
            styleref_level=int(header_level_combo.currentData() or 1),
        )
        self._apply_content_control(
            getattr(variant, "footer", None),
            str(footer_combo.currentData() or "inherit"),
            footer_text.text(),
            default_alignment=str(footer_alignment_combo.currentData() or "center"),
        )

    def _apply_content_control(
        self,
        content,
        mode: str,
        value: str,
        *,
        default_alignment: str,
        styleref_level: int | None = None,
    ) -> None:
        if content is None:
            return
        content.mode = mode
        content.alignment = default_alignment
        content.styleref_level = int(styleref_level if styleref_level is not None else self._styleref_level_combo.currentData() or 1)
        value = str(value or "").strip()
        if mode == "template":
            content.template = value
            content.fixed_text = ""
        elif mode in {"fixed", "page_number_with_text"}:
            content.fixed_text = value
            content.template = ""
        else:
            content.fixed_text = ""
            content.template = ""

    def _set_header_footer_controls(self, header_footer, *, sync_scheme: bool) -> None:
        self._header_enabled_toggle.setChecked(bool(getattr(header_footer, "header_enabled", True)))
        self._footer_enabled_toggle.setChecked(bool(getattr(header_footer, "footer_enabled", True)))
        self._set_combo_by_data(self._header_mode_combo, header_footer.header_mode)
        self._set_combo_by_data(self._header_alignment_combo, getattr(header_footer, "header_alignment", "center"))
        self._header_text_edit.setText(header_footer.header_text or "")
        self._set_combo_by_data(self._styleref_level_combo, header_footer.styleref_level)
        header_typography = getattr(getattr(header_footer, "header", None), "typography", None)
        footer_typography = getattr(getattr(header_footer, "footer", None), "typography", None)
        self._font_cn_combo.set_font_name(str(getattr(header_typography, "font_cn", "") or ""))
        self._font_en_combo.set_font_name(str(getattr(header_typography, "font_en", "") or ""))
        self._size_combo.set_pt(getattr(header_typography, "size_pt", None) or 12.0)
        self._bold_toggle.setChecked(bool(getattr(header_typography, "bold", False)))
        self._italic_toggle.setChecked(bool(getattr(header_typography, "italic", False)))
        self._footer_font_cn_combo.set_font_name(str(getattr(footer_typography, "font_cn", "") or ""))
        self._footer_font_en_combo.set_font_name(str(getattr(footer_typography, "font_en", "") or ""))
        self._footer_size_combo.set_pt(getattr(footer_typography, "size_pt", None) or 12.0)
        self._footer_bold_toggle.setChecked(bool(getattr(footer_typography, "bold", False)))
        self._footer_italic_toggle.setChecked(bool(getattr(footer_typography, "italic", False)))
        self._set_bottom_text_and_page_number_from_mode(getattr(header_footer.footer, "content_mode", "page_number"))
        self._page_number_enabled_toggle.setChecked(
            bool(getattr(header_footer, "page_number_enabled", True))
        )
        self._footer_text_edit.setText(getattr(header_footer, "footer_text", "") or "")
        self._set_combo_by_data(self._footer_alignment_combo, getattr(header_footer, "footer_alignment", "center"))
        self._set_combo_by_data(
            self._page_number_alignment_combo,
            getattr(header_footer, "page_number_alignment", "center"),
        )
        self._header_border_toggle.setChecked(header_footer.header_border)
        self._header_scope_editor.set_selectors(
            list(getattr(header_footer.header, "hidden_selectors", []) or [])
        )
        self._footer_scope_editor.set_selectors(
            list(getattr(header_footer.footer, "hidden_selectors", []) or [])
        )
        behavior = getattr(header_footer, "behavior", None)
        self._different_first_page_toggle.setChecked(bool(getattr(behavior, "different_first_page", False)))
        self._different_odd_even_toggle.setChecked(bool(getattr(behavior, "different_odd_even_pages", False)))
        self._set_combo_by_data(
            self._section_link_mode_combo,
            getattr(behavior, "link_to_previous", "never"),
        )
        self._set_page_number_display_from_template(getattr(header_footer, "page_number_template", "{page}") or "{page}")
        page_number_plan = getattr(header_footer, "page_number_plan", None)
        self._set_page_number_variant_controls(
            getattr(page_number_plan, "first", None),
            self._first_page_number_visibility_combo,
            self._first_page_number_alignment_combo,
            self._first_page_number_display_combo,
            self._first_page_number_template_edit,
        )
        self._set_page_number_variant_controls(
            getattr(page_number_plan, "even", None),
            self._even_page_number_visibility_combo,
            self._even_page_number_alignment_combo,
            self._even_page_number_display_combo,
            self._even_page_number_template_edit,
        )
        variants = getattr(header_footer, "variants", None)
        self._set_variant_controls(
            getattr(variants, "first", None),
            self._first_header_mode_combo,
            self._first_header_alignment_combo,
            self._first_header_level_combo,
            self._first_header_text_edit,
            self._first_footer_mode_combo,
            self._first_footer_alignment_combo,
            self._first_footer_text_edit,
            default_header_mode="none",
            default_footer_mode="none",
        )
        self._set_variant_controls(
            getattr(variants, "even", None),
            self._even_header_mode_combo,
            self._even_header_alignment_combo,
            self._even_header_level_combo,
            self._even_header_text_edit,
            self._even_footer_mode_combo,
            self._even_footer_alignment_combo,
            self._even_footer_text_edit,
            default_header_mode="inherit",
            default_footer_mode="inherit",
        )
        self._page_plan.set_header_footer(header_footer)
        if sync_scheme:
            self._sync_scheme_combo(header_footer)

    def set_header_footer(self, header_footer, heading_model=None) -> None:
        dynamic_options = special_title_selector_options(heading_model)
        self._header_scope_editor.set_options(
            (*CUSTOM_SECTION_EXCLUSION_OPTIONS, *dynamic_options),
            preserve_selection=False,
        )
        self._footer_scope_editor.set_options(
            (*CUSTOM_SECTION_EXCLUSION_OPTIONS, *dynamic_options),
            preserve_selection=False,
        )
        self._page_plan.set_selector_options(
            (*PAGE_NUMBER_SELECTOR_OPTIONS, *dynamic_options)
        )
        self._set_header_footer_controls(header_footer, sync_scheme=True)

    def apply_to(self, header_footer) -> None:
        header_footer.header_enabled = self._header_enabled_toggle.isChecked()
        header_footer.footer_enabled = self._footer_enabled_toggle.isChecked()
        header_footer.header_mode = str(self._header_mode_combo.currentData() or "styleref")
        header_footer.header_alignment = str(self._header_alignment_combo.currentData() or "center")
        header_footer.header_text = self._header_text_edit.text()
        header_footer.styleref_level = int(self._styleref_level_combo.currentData() or 1)
        header_footer.header.typography.font_cn = self._font_cn_combo.selected_font() or None
        header_footer.header.typography.font_en = self._font_en_combo.selected_font() or None
        header_footer.header.typography.size_pt = self._size_combo.current_pt()
        header_footer.header.typography.bold = self._bold_toggle.isChecked()
        header_footer.header.typography.italic = self._italic_toggle.isChecked()
        header_footer.footer.typography.font_cn = self._footer_font_cn_combo.selected_font() or None
        header_footer.footer.typography.font_en = self._footer_font_en_combo.selected_font() or None
        header_footer.footer.typography.size_pt = self._footer_size_combo.current_pt()
        header_footer.footer.typography.bold = self._footer_bold_toggle.isChecked()
        header_footer.footer.typography.italic = self._footer_italic_toggle.isChecked()
        header_footer.footer.content_mode = self._combined_footer_content_mode()
        header_footer.footer_text = (
            self._footer_text_edit.text()
            if self._footer_mode_has_fixed_text()
            else ""
        )
        header_footer.footer_alignment = str(self._footer_alignment_combo.currentData() or "center")
        header_footer.header_border = self._header_border_toggle.isChecked()
        header_footer.header.hidden_selectors = self._header_scope_editor.selectors()
        header_footer.footer.hidden_selectors = self._footer_scope_editor.selectors()
        behavior = getattr(header_footer, "behavior", None)
        if behavior is not None:
            behavior.different_first_page = self._different_first_page_toggle.isChecked()
            behavior.different_odd_even_pages = self._different_odd_even_toggle.isChecked()
            behavior.link_to_previous = str(
                self._section_link_mode_combo.currentData() or "never"
            )
            behavior.preserve_existing_content = False
        header_footer.page_number_template = self._selected_page_number_template()
        header_footer.page_number_enabled = self._page_number_enabled_toggle.isChecked()
        header_footer.page_number_alignment = str(
            self._page_number_alignment_combo.currentData() or "center"
        )
        page_number_plan = getattr(header_footer, "page_number_plan", None)
        self._apply_page_number_variant_controls(
            getattr(page_number_plan, "first", None),
            self._first_page_number_visibility_combo,
            self._first_page_number_alignment_combo,
            self._first_page_number_display_combo,
            self._first_page_number_template_edit,
        )
        self._apply_page_number_variant_controls(
            getattr(page_number_plan, "even", None),
            self._even_page_number_visibility_combo,
            self._even_page_number_alignment_combo,
            self._even_page_number_display_combo,
            self._even_page_number_template_edit,
        )
        variants = getattr(header_footer, "variants", None)
        if variants is not None:
            self._apply_variant_controls(
                getattr(variants, "first", None),
                self._first_header_mode_combo,
                self._first_header_alignment_combo,
                self._first_header_level_combo,
                self._first_header_text_edit,
                self._first_footer_mode_combo,
                self._first_footer_alignment_combo,
                self._first_footer_text_edit,
            )
            self._apply_variant_controls(
                getattr(variants, "even", None),
                self._even_header_mode_combo,
                self._even_header_alignment_combo,
                self._even_header_level_combo,
                self._even_header_text_edit,
                self._even_footer_mode_combo,
                self._even_footer_alignment_combo,
                self._even_footer_text_edit,
            )
        self._page_plan.apply_to(header_footer)

    def sync_dependent_state(self) -> None:
        header_enabled = self._header_enabled_toggle.isChecked()
        footer_enabled = self._footer_enabled_toggle.isChecked()
        header_mode = str(self._header_mode_combo.currentData() or "styleref")
        footer_mode = self._combined_footer_content_mode()
        page_number_enabled = self._page_number_enabled_toggle.isChecked()
        page_number_active = page_number_enabled
        footer_text_enabled = self._footer_mode_has_fixed_text()

        self._header_text_row.setVisible(header_mode == "fixed")
        self._styleref_level_row.setVisible(header_mode == "styleref")
        self._header_alignment_row.setVisible(header_mode != "none")
        for row in (
            self._header_mode_row,
            self._header_alignment_row,
            self._header_text_row,
            self._styleref_level_row,
        ):
            row.setEnabled(header_enabled)
        self._normal_page_grid.updateGeometry()
        self._footer_text_row.setVisible(footer_text_enabled)
        for row in (self._bottom_text_mode_row, self._footer_text_row):
            row.setEnabled(footer_enabled)
        self._footer_grid.updateGeometry()
        self._footer_alignment_row.setEnabled(footer_enabled and footer_mode != "none")
        self._page_number_enabled_row.setEnabled(True)
        self._page_number_alignment_row.setEnabled(page_number_active)
        self._page_number_display_row.setEnabled(page_number_active)
        self._page_number_template_row.setVisible(page_number_enabled and self._page_number_display_is_custom())
        self._page_number_template_row.setEnabled(page_number_active and self._page_number_display_is_custom())

        header_outputs = header_enabled and header_mode != "none"
        footer_outputs = footer_enabled and footer_mode != "none"
        self._header_scope_row.setVisible(True)
        self._header_scope_row.setEnabled(header_outputs)
        self._footer_scope_row.setVisible(True)
        self._footer_scope_row.setEnabled(footer_outputs)

        first_enabled = self._different_first_page_toggle.isChecked()
        even_enabled = self._different_odd_even_toggle.isChecked()
        self._sync_page_number_variant_rows(
            enabled=first_enabled,
            page_number_enabled=page_number_enabled,
            title=self._first_page_number_title_label,
            grid=self._first_page_number_variant_grid,
            visibility_row=self._first_page_number_visibility_row,
            visibility_combo=self._first_page_number_visibility_combo,
            alignment_row=self._first_page_number_alignment_row,
            display_row=self._first_page_number_display_row,
            display_combo=self._first_page_number_display_combo,
            template_row=self._first_page_number_template_row,
        )
        self._sync_page_number_variant_rows(
            enabled=even_enabled,
            page_number_enabled=page_number_enabled,
            title=self._even_page_number_title_label,
            grid=self._even_page_number_variant_grid,
            visibility_row=self._even_page_number_visibility_row,
            visibility_combo=self._even_page_number_visibility_combo,
            alignment_row=self._even_page_number_alignment_row,
            display_row=self._even_page_number_display_row,
            display_combo=self._even_page_number_display_combo,
            template_row=self._even_page_number_template_row,
        )
        self._page_number_variant_separator.setVisible(first_enabled or even_enabled)
        self._page_number_even_first_separator.setVisible(first_enabled and even_enabled)
        first_header_mode = str(self._first_header_mode_combo.currentData() or "none")
        first_footer_mode = str(self._first_footer_mode_combo.currentData() or "none")
        even_header_mode = str(self._even_header_mode_combo.currentData() or "inherit")
        even_footer_mode = str(self._even_footer_mode_combo.currentData() or "inherit")
        self._sync_header_section_titles(first_enabled=first_enabled, even_enabled=even_enabled)
        self._sync_footer_section_titles(first_enabled=first_enabled, even_enabled=even_enabled)

        self._sync_variant_rows(
            enabled=first_enabled,
            grid=self._first_header_variant_grid,
            rows=(
                self._first_header_mode_row,
                self._first_header_alignment_row,
                self._first_header_level_row,
                self._first_header_text_row,
            ),
            mode=first_header_mode,
            text_row=self._first_header_text_row,
            alignment_row=self._first_header_alignment_row,
            level_row=self._first_header_level_row,
        )
        self._sync_variant_rows(
            enabled=first_enabled,
            grid=self._first_footer_variant_grid,
            rows=(self._first_footer_mode_row, self._first_footer_alignment_row, self._first_footer_text_row),
            mode=first_footer_mode,
            text_row=self._first_footer_text_row,
            alignment_row=self._first_footer_alignment_row,
        )
        self._sync_variant_rows(
            enabled=even_enabled,
            grid=self._even_header_variant_grid,
            rows=(
                self._even_header_mode_row,
                self._even_header_alignment_row,
                self._even_header_level_row,
                self._even_header_text_row,
            ),
            mode=even_header_mode,
            text_row=self._even_header_text_row,
            alignment_row=self._even_header_alignment_row,
            level_row=self._even_header_level_row,
        )
        self._sync_variant_rows(
            enabled=even_enabled,
            grid=self._even_footer_variant_grid,
            rows=(self._even_footer_mode_row, self._even_footer_alignment_row, self._even_footer_text_row),
            mode=even_footer_mode,
            text_row=self._even_footer_text_row,
            alignment_row=self._even_footer_alignment_row,
        )
        self._header_variant_separator.setVisible(first_enabled or even_enabled)
        self._even_header_separator.setVisible(first_enabled and even_enabled)
        self._footer_variant_separator.setVisible(first_enabled or even_enabled)
        self._even_footer_separator.setVisible(first_enabled and even_enabled)
        for row in (
            self._first_header_mode_row,
            self._first_header_alignment_row,
            self._first_header_level_row,
            self._first_header_text_row,
            self._even_header_mode_row,
            self._even_header_alignment_row,
            self._even_header_level_row,
            self._even_header_text_row,
        ):
            row.setEnabled(header_enabled)
        for row in (
            self._first_footer_mode_row,
            self._first_footer_alignment_row,
            self._first_footer_text_row,
            self._even_footer_mode_row,
            self._even_footer_alignment_row,
            self._even_footer_text_row,
        ):
            row.setEnabled(footer_enabled)

        header_outputs = header_outputs or (
            header_enabled and first_enabled and self._variant_outputs(first_header_mode, header_outputs)
        ) or (
            header_enabled and even_enabled and self._variant_outputs(even_header_mode, header_outputs)
        )
        footer_outputs = footer_outputs or (
            footer_enabled and first_enabled and self._variant_outputs(first_footer_mode, footer_outputs)
        ) or (
            footer_enabled and even_enabled and self._variant_outputs(even_footer_mode, footer_outputs)
        )
        for row in (self._font_cn_row, self._font_en_row, self._size_row, self._emphasis_row):
            row.setEnabled(header_outputs)
        for row in (
            self._footer_font_cn_row,
            self._footer_font_en_row,
            self._footer_size_row,
            self._footer_emphasis_row,
        ):
            row.setEnabled(footer_outputs)
        self._header_border_row.setEnabled(header_outputs)
        self._page_plan.set_enabled_visible(page_number_active)
        self._refresh_quick_preview()
        self._refresh_dependent_layout()
        refresh_layout_chain_later(self._owner._editor_column)
        if self._owner._current_template is not None and not self._owner._is_syncing:
            self._sync_scheme_combo(self._owner._current_template.header_footer)

    def _sync_header_section_titles(self, *, first_enabled: bool, even_enabled: bool) -> None:
        if even_enabled:
            title = "奇数页页眉（首页以外）" if first_enabled else "奇数页页眉"
        else:
            title = "普通页页眉（首页以外）" if first_enabled else "普通页页眉"
        self._normal_header_title_label.setText(title)
        self._first_header_title_label.setVisible(first_enabled)
        self._even_header_title_label.setVisible(even_enabled)

    def _sync_footer_section_titles(self, *, first_enabled: bool, even_enabled: bool) -> None:
        if even_enabled:
            title = "奇数页页脚文字（首页以外）" if first_enabled else "奇数页页脚文字"
        else:
            title = "普通页页脚文字（首页以外）" if first_enabled else "普通页页脚文字"
        self._normal_footer_title_label.setText(title)
        self._first_footer_title_label.setVisible(first_enabled)
        self._even_footer_title_label.setVisible(even_enabled)

    def _sync_variant_rows(
        self,
        *,
        enabled: bool,
        grid: QWidget,
        rows: tuple[QWidget, ...],
        mode: str,
        text_row: QWidget,
        alignment_row: QWidget | None = None,
        level_row: QWidget | None = None,
    ) -> None:
        grid.setVisible(enabled)
        for row in rows:
            row.setVisible(enabled)
        text_row.setVisible(enabled and self._variant_mode_needs_text(mode))
        if alignment_row is not None:
            alignment_row.setVisible(enabled and mode not in {"inherit", "none", "preserve"})
        if level_row is not None:
            level_row.setVisible(enabled and mode == "styleref")

    def _sync_page_number_variant_rows(
        self,
        *,
        enabled: bool,
        page_number_enabled: bool,
        title: QLabel,
        grid: QWidget,
        visibility_row: QWidget,
        visibility_combo: StyledComboBox,
        alignment_row: QWidget,
        display_row: QWidget,
        display_combo: StyledComboBox,
        template_row: QWidget,
    ) -> None:
        visibility = str(visibility_combo.currentData() or "inherit")
        active = enabled and page_number_enabled and visibility != "hide"
        custom = str(display_combo.currentData() or "inherit") == "custom"
        title.setVisible(enabled)
        grid.setVisible(enabled)
        visibility_row.setVisible(enabled)
        alignment_row.setVisible(enabled)
        display_row.setVisible(enabled)
        template_row.setVisible(enabled and active and custom)
        visibility_row.setEnabled(enabled and page_number_enabled)
        alignment_row.setEnabled(active)
        display_row.setEnabled(active)
        template_row.setEnabled(active and custom)

    def _variant_mode_needs_text(self, mode: str) -> bool:
        return mode in {"fixed", "page_number_with_text", "template"}

    def _variant_outputs(self, mode: str, inherited_outputs: bool) -> bool:
        normalized = str(mode or "inherit")
        if normalized == "inherit":
            return inherited_outputs
        return normalized != "none"

    def _refresh_quick_preview(self) -> None:
        header_mode = str(self._header_mode_combo.currentData() or "styleref")
        if header_mode == "none":
            header_text = "不显示"
        elif header_mode == "fixed":
            header_text = f"固定文字 {self._header_text_edit.text() or '未填写'}"
        else:
            header_text = f"跟随 {int(self._styleref_level_combo.currentData() or 1)} 级标题"

        footer_mode = self._combined_footer_content_mode()
        bottom_text = "固定文字" if footer_mode in {"fixed", "page_number_with_text"} else "不显示"

        header_hidden = [
            SECTION_EXCLUSION_LABELS.get(
                selector,
                special_title_selector_label(selector),
            )
            for selector in self._header_scope_editor.selectors()
        ]
        footer_hidden = [
            SECTION_EXCLUSION_LABELS.get(
                selector,
                special_title_selector_label(selector),
            )
            for selector in self._footer_scope_editor.selectors()
        ]
        if header_text != "不显示" and header_hidden:
            header_text += f"（{'、'.join(header_hidden)}隐藏）"
        if bottom_text != "不显示" and footer_hidden:
            bottom_text += f"（{'、'.join(footer_hidden)}隐藏）"

        lines = [f"页眉：{header_text} · 页脚文字：{bottom_text}"]
        page_summary = self._preview_page_summary_text()
        if page_summary:
            lines.append(f"页码：{page_summary}")
        if self._different_first_page_toggle.isChecked():
            lines.append(
                "首页页码："
                + self._page_number_variant_preview_text(
                    self._first_page_number_visibility_combo,
                    self._first_page_number_alignment_combo,
                    self._first_page_number_display_combo,
                )
            )
        if self._different_odd_even_toggle.isChecked():
            lines.append(
                "偶数页页码："
                + self._page_number_variant_preview_text(
                    self._even_page_number_visibility_combo,
                    self._even_page_number_alignment_combo,
                    self._even_page_number_display_combo,
                )
            )
        word_parts: list[str] = []
        if self._different_first_page_toggle.isChecked():
            word_parts.append("每个分节的首页不同")
        if self._different_odd_even_toggle.isChecked():
            word_parts.append("奇偶页不同")
        selected_template = self._selected_page_number_template()
        if selected_template != "{page}":
            word_parts.append("自定义页码格式" if self._page_number_display_is_custom() else "页码格式")
        if word_parts:
            lines.append(f"Word：{'、'.join(word_parts)}")
        self._quick_preview_label.setText("\n".join(lines))

    def _page_number_variant_preview_text(
        self,
        visibility_combo: StyledComboBox,
        alignment_combo: StyledComboBox,
        display_combo: StyledComboBox,
    ) -> str:
        visibility = str(visibility_combo.currentData() or "inherit")
        if visibility == "hide":
            return "隐藏"
        parts = ["强制显示" if visibility == "show" else "跟随编号阶段"]
        alignment = str(alignment_combo.currentData() or "inherit")
        if alignment != "inherit":
            parts.append(dict(PAGE_NUMBER_POSITION_OPTIONS).get(alignment, "页脚居中"))
        display = str(display_combo.currentData() or "inherit")
        if display != "inherit":
            parts.append(dict(PAGE_NUMBER_DISPLAY_OPTIONS).get(display, "自定义"))
        return " / ".join(parts)

    def _preview_page_summary_text(self) -> str:
        if not self._footer_mode_has_page_number():
            return ""
        phases = self.phase_rows_to_configs()
        if not phases:
            return "未设置"
        return "；".join(self._preview_single_phase_summary(phase) for phase in phases)

    def _preview_single_phase_summary(self, phase) -> str:
        selectors = list(getattr(phase, "selectors", []) or [])
        scope = self._preview_phase_scope_short(selectors)
        if not bool(getattr(phase, "visible", True)):
            return f"{scope}不显示（仍参与本阶段计数）"
        if str(getattr(phase, "start_mode", "restart") or "restart") == "continue":
            suffix = "续号"
        else:
            suffix = f"从 {max(1, int(getattr(phase, 'start_value', 1) or 1))} 起"
        return f"{scope}{self._preview_number_format_short(phase)}{suffix}"

    def _preview_phase_scope_short(self, selectors: list[str]) -> str:
        normalized = [
            str(selector or "").strip()
            for selector in selectors
            if str(selector or "").strip()
        ]
        selector_set = set(normalized)
        compact = (
            ({"abstract_cn", "abstract_en"}, "摘要"),
            ({"abstract_cn", "abstract_en", "toc"}, "前置部分"),
            (
                {
                    "body",
                    "references",
                    "errata",
                    "appendix",
                    "acknowledgment",
                    "resume",
                },
                "正文及后置",
            ),
            (
                {
                    "abstract_cn",
                    "abstract_en",
                    "toc",
                    "body",
                    "references",
                    "errata",
                    "appendix",
                    "acknowledgment",
                    "resume",
                },
                "前置、正文及后置",
            ),
        )
        for members, label in compact:
            if selector_set == members and len(normalized) == len(members):
                return label
        if normalized == ["all_numbered_content"]:
            return "全文"
        labels = [
            SECTION_EXCLUSION_LABELS.get(
                selector,
                special_title_selector_label(selector),
            )
            for selector in normalized
        ]
        if len(labels) <= 2:
            return "、".join(labels) or "未设置范围"
        return f"{labels[0]}等 {len(labels)} 项"

    def _preview_number_format_short(self, phase) -> str:
        return {
            "decimal": "阿拉伯",
            "upperRoman": "罗马",
            "lowerRoman": "小写罗马",
            "upperLetter": "大写字母",
            "lowerLetter": "小写字母",
            "ordinal": "序数",
            "cardinalText": "英文基数词",
            "ordinalText": "英文序数词",
            "decimalZero": "补零数字",
            "decimalFullWidth": "全角数字",
        }.get(str(getattr(phase, "number_format", "decimal") or "decimal"), "阿拉伯")

    def refresh_validation_alert(self, template: TemplateConfig | None) -> None:
        self._page_plan.refresh_validation_alert(template)

    def apply_theme(self) -> None:
        theme = get_theme()
        ss = build_text_input_stylesheet(theme, selector="QLineEdit")
        self._header_text_edit.setStyleSheet(ss)
        self._footer_text_edit.setStyleSheet(ss)
        self._page_number_template_edit.setStyleSheet(ss)
        self._first_header_text_edit.setStyleSheet(ss)
        self._first_footer_text_edit.setStyleSheet(ss)
        self._even_header_text_edit.setStyleSheet(ss)
        self._even_footer_text_edit.setStyleSheet(ss)
        self._scheme_actions.apply_theme()
        self._refresh_scheme_action_state()
        self._page_plan.apply_theme()


__all__ = [
    "HeaderFooterDetailSection",
    "default_page_number_phases",
    "ensure_default_page_number_phases",
    "page_number_phase_brief",
]
