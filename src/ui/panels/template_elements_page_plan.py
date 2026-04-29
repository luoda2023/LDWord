"""Page-number plan controls for the template elements detail pane."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.config.feature_configs import default_continuous_page_number_phases
from src.config.template import PageNumberPhaseConfig, TemplateConfig
from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.engine.page_number_planner import (
    collect_static_page_number_diagnostics,
    expand_page_number_selectors,
    format_page_number_diagnostic_text,
    resolve_suppressed_header_footer_section_types,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.flow_layout import FlowLayout
from src.shared.ui.flow_section import FlowSection
from src.shared.ui.inline_alert import InlineAlert
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.template_form_layout import TemplateFormGrid, compact_form_column_gap, template_form_row
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch

if TYPE_CHECKING:
    from src.ui.panels.template_elements_detail import ElementsDetail


PAGE_NUMBER_FORMAT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("decimal", "阿拉伯数字"),
    ("upperRoman", "大写罗马"),
    ("lowerRoman", "小写罗马"),
)

PAGE_NUMBER_START_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("restart", "重新起号"),
    ("continue", "延续前段"),
)

PAGE_NUMBER_VALIDATION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("strict", "冲突时停止"),
    ("warn", "只提醒"),
)

PAGE_NUMBER_DOC_TREE_POLICY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("warn_and_fallback", "提醒并使用默认页码结果"),
    ("fallback", "直接使用默认页码结果"),
)

PAGE_NUMBER_SELECTOR_OPTIONS: tuple[tuple[str, str], ...] = (
    ("all_numbered_content", "全文"),
    ("front_matter", "前置部分"),
    ("body", "正文部分"),
    ("back_matter", "后置部分"),
    ("toc", "目录"),
    ("references", "参考文献"),
    ("appendix", "附录"),
    ("acknowledgment", "致谢"),
    ("resume", "简历"),
    ("errata", "勘误"),
    ("abstracts", "摘要"),
    ("cover", "封面"),
)

SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS: tuple[tuple[str, str], ...] = (
    ("pre_numbering", "封面及声明页"),
    ("cover", "仅封面"),
    ("statement", "声明页"),
    ("authorization", "授权书"),
    ("front_note", "说明页"),
    ("front_matter", "前置部分"),
    ("toc", "目录"),
    ("body", "正文部分"),
    ("back_matter", "后置部分"),
    ("references", "参考文献"),
    ("appendix", "附录"),
)

_SECTION_TYPE_LABELS: dict[str, str] = {
    "cover": "封面",
    "statement": "声明页",
    "authorization": "授权书",
    "front_note": "说明页",
    "abstract_cn": "中文摘要",
    "abstract_en": "英文摘要",
    "toc": "目录",
    "body": "正文部分",
    "references": "参考文献",
    "errata": "勘误",
    "appendix": "附录",
    "acknowledgment": "致谢",
    "resume": "简历",
}

_SECTION_TYPE_PREVIEW_ORDER: tuple[str, ...] = tuple(_SECTION_TYPE_LABELS)


@dataclass
class PageNumberPhaseControls:
    section: FlowSection
    phase_id_edit: QLineEdit
    selector_editor: "PageSelectorEditor"
    selector_preview: QLabel
    visible_toggle: ToggleSwitch
    format_combo: StyledComboBox
    start_mode_combo: StyledComboBox
    start_value_spin: StyledSpinBox
    remove_btn: QPushButton
    duplicate_btn: QPushButton
    move_up_btn: QPushButton
    move_down_btn: QPushButton


def continuous_page_number_preset() -> list[PageNumberPhaseConfig]:
    return default_continuous_page_number_phases()


def split_page_number_preset(*, continue_body: bool) -> list[PageNumberPhaseConfig]:
    return [
        PageNumberPhaseConfig(
            phase_id="front",
            selectors=["front_matter"],
            visible=True,
            number_format="upperRoman",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="body",
            selectors=["body", "back_matter"],
            visible=True,
            number_format="decimal",
            start_mode="continue" if continue_body else "restart",
            start_value=1,
        ),
    ]


def default_page_number_phases(header_footer) -> list[PageNumberPhaseConfig]:
    phases = list(deepcopy(getattr(header_footer.page_number_plan, "phases", []) or []))
    if phases:
        return phases
    return continuous_page_number_preset()


def ensure_default_page_number_phases(header_footer) -> None:
    plan = getattr(header_footer, "page_number_plan", None)
    if plan is None:
        return
    if list(getattr(plan, "phases", []) or []):
        return
    plan.phases = continuous_page_number_preset()


def page_number_phase_brief(phase: PageNumberPhaseConfig) -> str:
    format_label = dict(PAGE_NUMBER_FORMAT_OPTIONS).get(
        str(phase.number_format or "decimal"),
        "阿拉伯数字",
    )
    start_text = (
        "接续前一段"
        if str(phase.start_mode or "") == "continue"
        else f"从 {max(1, int(phase.start_value or 1))} 开始"
    )
    visible_text = "显示" if bool(phase.visible) else "隐藏"
    scope_text = _selector_brief(list(phase.selectors or []))
    return f"{scope_text}: {format_label} / {start_text} / {visible_text}"


def _selector_text(selectors: list[str]) -> str:
    return ", ".join(str(selector or "").strip() for selector in selectors if str(selector or "").strip())


def _selector_brief(selectors: list[str]) -> str:
    label_map = dict(PAGE_NUMBER_SELECTOR_OPTIONS)
    labels = [
        label_map.get(str(selector or "").strip(), str(selector or "").strip())
        for selector in selectors
        if str(selector or "").strip()
    ]
    return "、".join(labels) if labels else "未选择范围"


def _selector_title_brief(selectors: list[str]) -> str:
    labels = _selector_brief(selectors).split("、")
    if not labels or labels == ["未选择范围"]:
        return "未选择范围"
    if labels == ["全文"]:
        return "全文"
    if labels == ["正文部分", "后置部分"]:
        return "正文及后置"
    if len(labels) <= 2:
        return "、".join(labels)
    return f"{labels[0]}等 {len(labels)} 项"


def _suppress_selector_brief(selectors: list[str]) -> str:
    label_map = dict(SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS)
    labels = [
        label_map.get(str(selector or "").strip(), str(selector or "").strip())
        for selector in selectors
        if str(selector or "").strip()
    ]
    return "、".join(labels) if labels else "未设置不显示分区"


def _section_type_label(section_type: str) -> str:
    return _SECTION_TYPE_LABELS.get(str(section_type or "").strip(), str(section_type or "").strip())


def _section_type_labels(section_types: set[str] | frozenset[str]) -> str:
    order = {section_type: index for index, section_type in enumerate(_SECTION_TYPE_PREVIEW_ORDER)}
    sorted_types = sorted(
        (str(section_type or "").strip() for section_type in section_types if str(section_type or "").strip()),
        key=lambda section_type: (order.get(section_type, len(order)), section_type),
    )
    return "、".join(_section_type_label(section_type) for section_type in sorted_types)


def _page_number_format_label(value: str) -> str:
    return dict(PAGE_NUMBER_FORMAT_OPTIONS).get(str(value or "decimal"), "阿拉伯数字")


def default_suppress_header_footer_selectors(header_footer) -> list[str]:
    selectors = [
        str(selector or "").strip()
        for selector in (getattr(header_footer, "suppress_header_footer_selectors", None) or [])
        if str(selector or "").strip()
    ]
    if selectors:
        return selectors
    if bool(getattr(header_footer, "hide_cover_header_footer", False)):
        return ["pre_numbering"]
    return []


def _parse_selector_text(text: str) -> list[str]:
    return [
        item.strip()
        for item in str(text or "").replace("，", ",").split(",")
        if item.strip()
    ]


class PageSelectorEditor(QWidget):
    changed = Signal()
    _DEFAULT_LAYOUT_WIDTH = 760

    def __init__(
        self,
        parent=None,
        *,
        options: tuple[tuple[str, str], ...] = PAGE_NUMBER_SELECTOR_OPTIONS,
        hint_text: str = "常用范围可直接点选，其他分区名称写在下方输入框。",
    ):
        super().__init__(parent)
        self._is_syncing = False
        self._options = tuple(options)
        self._selector_buttons: dict[str, QPushButton] = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._chips = QWidget(self)
        self._chips.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._chips_layout = FlowLayout(self._chips, h_spacing=8, v_spacing=8)

        for selector, label in self._options:
            button = QPushButton(label, self._chips)
            button.setCheckable(True)
            button.clicked.connect(self._emit_changed)
            self._selector_buttons[selector] = button
            self._chips_layout.addWidget(button)

        layout.addWidget(self._chips)

        self._custom_edit = QLineEdit(self)
        self._custom_edit.setPlaceholderText("输入其他分区名称，多个值用逗号分隔")
        self._custom_edit.textChanged.connect(self._emit_changed)
        layout.addWidget(self._custom_edit)

        self._hint = QLabel(hint_text, self)
        self._hint.setObjectName("tpl_selector_hint")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self._sync_chips_height()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        width = max(1, int(width))
        margins = self.layout().contentsMargins()
        spacing = self.layout().spacing()
        chips_height = max(0, self._chips_layout.heightForWidth(width))
        edit_height = max(self._custom_edit.sizeHint().height(), self._custom_edit.minimumSizeHint().height())
        hint_height = self._hint.heightForWidth(width) if self._hint.hasHeightForWidth() else self._hint.sizeHint().height()
        hint_height = max(self._hint.minimumSizeHint().height(), hint_height)
        return (
            margins.top()
            + margins.bottom()
            + chips_height
            + edit_height
            + hint_height
            + spacing * 2
        )

    def sizeHint(self) -> QSize:
        width = max(self.width(), self._DEFAULT_LAYOUT_WIDTH, self._chips_layout.minimumSize().width())
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        width = max(1, self._chips_layout.minimumSize().width())
        return QSize(width, self.heightForWidth(self._DEFAULT_LAYOUT_WIDTH))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_chips_height()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_chips_height()

    def _sync_chips_height(self) -> None:
        width = max(1, self._chips.width() or self.width() or self._DEFAULT_LAYOUT_WIDTH)
        height = max(0, self._chips_layout.heightForWidth(width))
        if self._chips.minimumHeight() != height:
            self._chips.setMinimumHeight(height)
        if self._chips.maximumHeight() != height:
            self._chips.setMaximumHeight(height)
        self._chips.updateGeometry()
        self.updateGeometry()

    def set_selectors(self, selectors: list[str]) -> None:
        self._is_syncing = True
        try:
            normalized = [str(selector or "").strip() for selector in selectors if str(selector or "").strip()]
            known = set()
            extras: list[str] = []
            for selector in normalized:
                if selector in self._selector_buttons:
                    known.add(selector)
                else:
                    extras.append(selector)
            for selector, button in self._selector_buttons.items():
                button.setChecked(selector in known)
            self._custom_edit.setText(_selector_text(extras))
        finally:
            self._is_syncing = False

    def selectors(self) -> list[str]:
        selected = [
            selector
            for selector, _label in self._options
            if self._selector_buttons[selector].isChecked()
        ]
        selected.extend(
            selector
            for selector in _parse_selector_text(self._custom_edit.text())
            if selector not in selected
        )
        return selected

    def _emit_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        self.changed.emit()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._custom_edit.setStyleSheet(build_text_input_stylesheet(theme, selector="QLineEdit"))
        self._hint.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
        )
        button_stylesheet = (
            f"QPushButton {{"
            f"background: {theme.bg_card};"
            f"color: {theme.text_secondary};"
            f"border: 1px solid {theme.border};"
            f"border-radius: {theme.radius_sm}px;"
            f"min-height: {theme.control_height_sm}px;"
            f"padding: 2px {theme.button_padding_x}px;"
            f"font-size: {theme.font_size_sm}px;"
            f"}}"
            f"QPushButton:hover {{"
            f"background: {theme.bg_hover};"
            f"color: {theme.text_primary};"
            f"}}"
            f"QPushButton:checked {{"
            f"background: {theme.primary_light};"
            f"color: {theme.primary};"
            f"border-color: {theme.primary};"
            f"font-weight: {theme.font_weight_emphasis};"
            f"}}"
            f"QPushButton:checked:hover {{"
            f"background: {theme.primary_light};"
            f"color: {theme.primary_pressed};"
            f"}}"
        )
        for button in self._selector_buttons.values():
            button.setStyleSheet(button_stylesheet)
        self._sync_chips_height()


class PageNumberPlanSection:
    """Owns the page-number plan card and dynamic rule rows."""

    def __init__(self, owner: "ElementsDetail"):
        self._owner = owner
        self._page_phase_rows: list[PageNumberPhaseControls] = []

        self.section = Card(parent=owner._editor_column)
        self._page_plan_section = self.section
        owner._page_plan_section = self.section
        owner._add_card_header(self.section, "list-ordered", "页码结果")
        owner._editor_layout.addWidget(self.section)
        self._build_form()

    @property
    def page_phase_rows(self) -> list[PageNumberPhaseControls]:
        return self._page_phase_rows

    def export_compat_attributes(self, target) -> None:
        names = (
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
            setattr(target, name, getattr(self, name))
        target._page_phase_rows = self._page_phase_rows

    def _build_form(self) -> None:
        self._page_validation_mode_combo = StyledComboBox(self._owner)
        for value, label in PAGE_NUMBER_VALIDATION_OPTIONS:
            self._page_validation_mode_combo.addItem(label, value)
        self._page_validation_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)

        self._page_missing_doc_tree_combo = StyledComboBox(self._owner)
        for value, label in PAGE_NUMBER_DOC_TREE_POLICY_OPTIONS:
            self._page_missing_doc_tree_combo.addItem(label, value)
        self._page_missing_doc_tree_combo.currentIndexChanged.connect(self._owner._on_structure_edited)

        self._page_plan_note = QLabel(
            "常用方案会直接生成页码结果；只有附录、致谢等需要独立页码时，才需要展开高级编辑器。",
            self._owner,
        )
        self._page_plan_note.setObjectName("tpl_phase_plan_note")
        self._page_plan_note.setWordWrap(True)
        self.section.add_widget(self._page_plan_note)

        preset_row = QWidget(self._owner)
        preset_layout = QHBoxLayout(preset_row)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(8)

        self._preset_continuous_btn = QPushButton("可编号内容从 1 连续", preset_row)
        self._preset_continuous_btn.clicked.connect(
            lambda: self._apply_page_number_preset("continuous")
        )
        preset_layout.addWidget(self._preset_continuous_btn)

        self._preset_split_restart_btn = QPushButton("前置罗马，正文从 1", preset_row)
        self._preset_split_restart_btn.clicked.connect(
            lambda: self._apply_page_number_preset("split_restart")
        )
        preset_layout.addWidget(self._preset_split_restart_btn)

        self._preset_split_continue_btn = QPushButton("前置罗马，正文续号", preset_row)
        self._preset_split_continue_btn.clicked.connect(
            lambda: self._apply_page_number_preset("split_continue")
        )
        preset_layout.addWidget(self._preset_split_continue_btn)

        preset_layout.addStretch(1)
        self.section.add_widget(preset_row)

        self._page_advanced_section = FlowSection("高级：页码结果编辑器", expanded=False, parent=self.section)
        self._page_advanced_section.add_widget(
            self._pair_row(
                self._form_row("冲突处理", self._page_validation_mode_combo, parent=self._page_advanced_section),
                self._form_row("无结构识别时", self._page_missing_doc_tree_combo, parent=self._page_advanced_section),
            )
        )

        self._page_plan_alert = InlineAlert("", variant="warning", parent=self._page_advanced_section)
        self._page_plan_alert.hide()
        self._page_advanced_section.add_widget(self._page_plan_alert)

        advanced_note = QLabel(
            "分区来自文档结构识别。每条结果描述：哪些分区显示页码、使用什么格式、从哪里起号。",
            self._page_advanced_section,
        )
        advanced_note.setObjectName("tpl_phase_plan_note")
        advanced_note.setWordWrap(True)
        self._page_advanced_section.add_widget(advanced_note)

        advanced_actions = QWidget(self._page_advanced_section)
        advanced_actions_layout = QHBoxLayout(advanced_actions)
        advanced_actions_layout.setContentsMargins(0, 0, 0, 0)
        advanced_actions_layout.setSpacing(8)
        advanced_actions_layout.addStretch(1)

        self._add_phase_btn = QPushButton("新增页码结果", advanced_actions)
        self._add_phase_btn.clicked.connect(self._on_add_phase)
        advanced_actions_layout.addWidget(self._add_phase_btn)
        self._page_advanced_section.add_widget(advanced_actions)

        self._page_phase_rows_host = QWidget(self._owner)
        self._page_phase_rows_layout = QVBoxLayout(self._page_phase_rows_host)
        self._page_phase_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._page_phase_rows_layout.setSpacing(10)
        self._page_advanced_section.add_widget(self._page_phase_rows_host)
        self.section.add_widget(self._page_advanced_section)

    def _form_row(
        self,
        label: str,
        widget: QWidget,
        *,
        suffix_widget: QWidget | None = None,
        parent,
    ) -> QWidget:
        return template_form_row(label, widget, suffix_widget=suffix_widget, parent=parent)

    def _pair_row(self, *widgets: QWidget) -> TemplateFormGrid:
        return TemplateFormGrid([widgets], parent=self._owner, column_gap=compact_form_column_gap())

    def _build_page_number_spin(self) -> StyledSpinBox:
        spin = StyledSpinBox(self._owner)
        spin.setRange(1, 99)
        spin.setSingleStep(1)
        spin.setDecimals(0)
        return spin

    def _clear_page_phase_rows(self) -> None:
        while self._page_phase_rows_layout.count():
            item = self._page_phase_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._page_phase_rows.clear()

    def _build_empty_phase(self) -> PageNumberPhaseConfig:
        return PageNumberPhaseConfig(
            phase_id=f"phase_{len(self._page_phase_rows) + 1}",
            selectors=[],
            visible=True,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        )

    def _append_page_phase_row(self, phase: PageNumberPhaseConfig) -> None:
        section = FlowSection("未选择分区", expanded=False, parent=self._page_phase_rows_host)

        phase_id_edit = QLineEdit(section)
        phase_id_edit.setPlaceholderText("例如：前置 / 正文 / 附录")
        phase_id_edit.hide()

        selector_editor = PageSelectorEditor(section)
        selector_preview = QLabel("结果：尚未选择编号分区", section)
        selector_preview.setObjectName("tpl_phase_selector_preview")
        selector_preview.setWordWrap(True)
        visible_toggle = ToggleSwitch(section, checked=True)

        format_combo = StyledComboBox(section)
        for value, label in PAGE_NUMBER_FORMAT_OPTIONS:
            format_combo.addItem(label, value)

        start_mode_combo = StyledComboBox(section)
        for value, label in PAGE_NUMBER_START_MODE_OPTIONS:
            start_mode_combo.addItem(label, value)

        start_value_spin = self._build_page_number_spin()
        duplicate_btn = QPushButton("复制", section)
        move_up_btn = QPushButton("上移", section)
        move_down_btn = QPushButton("下移", section)
        remove_btn = QPushButton("移除", section)

        selector_row = self._form_row("编号分区", selector_editor, parent=section)
        selector_row.set_label_alignment(Qt.AlignLeft | Qt.AlignTop)
        section.add_widget(selector_row)
        section.add_widget(selector_preview)
        section.add_widget(
            self._pair_row(
                self._form_row("显示页码", visible_toggle, parent=section),
                self._form_row("页码格式", format_combo, parent=section),
                self._form_row("起号方式", start_mode_combo, parent=section),
            )
        )
        section.add_widget(
            self._pair_row(
                self._form_row("起始值", start_value_spin, parent=section),
            )
        )

        remove_row = QWidget(section)
        remove_layout = QHBoxLayout(remove_row)
        remove_layout.setContentsMargins(0, 0, 0, 0)
        remove_layout.setSpacing(8)
        remove_layout.addStretch(1)
        remove_layout.addWidget(move_up_btn)
        remove_layout.addWidget(move_down_btn)
        remove_layout.addWidget(duplicate_btn)
        remove_layout.addWidget(remove_btn)
        section.add_widget(remove_row)

        controls = PageNumberPhaseControls(
            section=section,
            phase_id_edit=phase_id_edit,
            selector_editor=selector_editor,
            selector_preview=selector_preview,
            visible_toggle=visible_toggle,
            format_combo=format_combo,
            start_mode_combo=start_mode_combo,
            start_value_spin=start_value_spin,
            remove_btn=remove_btn,
            duplicate_btn=duplicate_btn,
            move_up_btn=move_up_btn,
            move_down_btn=move_down_btn,
        )

        phase_id_edit.textChanged.connect(self._on_phase_row_meta_changed)
        selector_editor.changed.connect(self._on_phase_row_meta_changed)
        visible_toggle.toggled_signal.connect(self._on_phase_row_meta_changed)
        format_combo.currentIndexChanged.connect(self._on_phase_row_meta_changed)
        start_mode_combo.currentIndexChanged.connect(
            lambda *_args, row=controls: self._on_phase_start_mode_changed(row)
        )
        start_value_spin.valueChanged.connect(self._on_phase_row_meta_changed)
        remove_btn.clicked.connect(lambda *_args, row=controls: self._remove_phase_row(row))
        duplicate_btn.clicked.connect(lambda *_args, row=controls: self._duplicate_phase_row(row))
        move_up_btn.clicked.connect(lambda *_args, row=controls: self._move_phase_row(row, -1))
        move_down_btn.clicked.connect(lambda *_args, row=controls: self._move_phase_row(row, 1))

        self._page_phase_rows_layout.addWidget(section)
        self._page_phase_rows.append(controls)

        phase_id_edit.setText(str(phase.phase_id or ""))
        selector_editor.set_selectors(list(phase.selectors or []))
        visible_toggle.setChecked(bool(phase.visible))
        self._set_combo_by_data(format_combo, phase.number_format or "decimal")
        self._set_combo_by_data(start_mode_combo, phase.start_mode or "restart")
        start_value_spin.setValue(float(max(1, int(phase.start_value or 1))))

    def _rebuild_page_phase_rows(
        self,
        phases: list[PageNumberPhaseConfig],
        *,
        ensure_one: bool = True,
    ) -> None:
        self._clear_page_phase_rows()
        phase_list = [deepcopy(phase) for phase in phases]
        if ensure_one and not phase_list:
            phase_list = continuous_page_number_preset()
        for phase in phase_list:
            self._append_page_phase_row(phase)
        self._refresh_page_phase_row_state()
        self.apply_theme()

    def _refresh_page_phase_row_state(self) -> None:
        row_count = len(self._page_phase_rows)
        suppressed = self._suppressed_section_types()
        matched_by_section = self._matched_sections_by_phase_row()
        for index, row in enumerate(self._page_phase_rows, start=1):
            row.section._toggle_button.setText(self._phase_section_title(index, row))
            row.selector_preview.setText(
                self._phase_preview_text(row, suppressed, matched_by_section.get(id(row), set()))
            )
            start_mode = str(row.start_mode_combo.currentData() or "restart")
            row.start_value_spin.setEnabled(start_mode == "restart")
            row.remove_btn.setEnabled(row_count > 1)
            row.move_up_btn.setEnabled(index > 1)
            row.move_down_btn.setEnabled(index < row_count)

    def _suppressed_section_types(self) -> frozenset[str]:
        template = getattr(self._owner, "_current_template", None)
        if template is None:
            return frozenset()
        return resolve_suppressed_header_footer_section_types(template.header_footer)

    def _matched_sections_by_phase_row(self) -> dict[int, set[str]]:
        matched_by_row: dict[int, set[str]] = {}
        for row in self._page_phase_rows:
            matched_by_row[id(row)] = set(expand_page_number_selectors(row.selector_editor.selectors()))
        return matched_by_row

    def _selector_preview_text(self, selectors: list[str]) -> str:
        if not selectors:
            return "分区：尚未选择编号分区"
        label_map = dict(PAGE_NUMBER_SELECTOR_OPTIONS) | dict(SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS)
        labels = [label_map.get(str(selector), str(selector)) for selector in selectors]
        return "分区：" + "、".join(labels)

    def _phase_preview_text(
        self,
        row: PageNumberPhaseControls,
        suppressed: frozenset[str],
        matched_sections: set[str],
    ) -> str:
        selectors = row.selector_editor.selectors()
        lines = [self._selector_preview_text(selectors)]
        if matched_sections:
            lines.append(f"实际命中：{_section_type_labels(matched_sections)}")
        elif selectors:
            lines.append("实际命中：未命中已知分区")
        else:
            lines.append("实际命中：待选择分区")

        if not row.visible_toggle.isChecked():
            lines.append("结果：这些分区不显示页码")
        else:
            start_mode = str(row.start_mode_combo.currentData() or "restart")
            format_label = _page_number_format_label(str(row.format_combo.currentData() or "decimal"))
            if start_mode == "continue":
                lines.append(f"结果：{format_label}，延续前段")
            else:
                start_value = max(1, int(round(row.start_value_spin.value())))
                lines.append(f"结果：{format_label}，从 {start_value} 起号")

        hidden_sections = matched_sections & set(suppressed)
        if hidden_sections:
            lines.append(f"提醒：{_section_type_labels(hidden_sections)} 已在不显示分区内，不会输出页码")

        overlap_sections = self._overlapped_sections_for_row(row, matched_sections)
        if overlap_sections:
            lines.append(f"冲突：{_section_type_labels(overlap_sections)} 同时命中其他页码结果")
        return "\n".join(lines)

    def _overlapped_sections_for_row(
        self,
        row: PageNumberPhaseControls,
        matched_sections: set[str],
    ) -> set[str]:
        if not matched_sections:
            return set()
        overlapped: set[str] = set()
        for other in self._page_phase_rows:
            if other is row:
                continue
            overlapped.update(matched_sections & set(expand_page_number_selectors(other.selector_editor.selectors())))
        return overlapped

    def _phase_section_title(self, index: int, row: PageNumberPhaseControls) -> str:
        scope_text = _selector_title_brief(row.selector_editor.selectors())
        if scope_text == "未选择范围":
            return "未选择编号分区"
        if not row.visible_toggle.isChecked():
            return f"{scope_text}：不显示页码"

        format_label = {
            "decimal": "阿拉伯",
            "upperRoman": "罗马",
            "lowerRoman": "小写罗马",
        }.get(
            str(row.format_combo.currentData() or "decimal"),
            "阿拉伯",
        )
        start_mode = str(row.start_mode_combo.currentData() or "restart")
        if start_mode == "continue":
            return f"{scope_text}：{format_label}，延续前段"
        start_value = max(1, int(round(row.start_value_spin.value())))
        if start_value == 1:
            return f"{scope_text}：{format_label}，从 1 起"
        return f"{scope_text}：{format_label}，从 {start_value} 起"

    def phase_rows_to_configs(self) -> list[PageNumberPhaseConfig]:
        phases: list[PageNumberPhaseConfig] = []
        for index, row in enumerate(self._page_phase_rows, start=1):
            phases.append(
                PageNumberPhaseConfig(
                    phase_id=row.phase_id_edit.text().strip() or f"phase_{index}",
                    selectors=row.selector_editor.selectors(),
                    visible=row.visible_toggle.isChecked(),
                    number_format=str(row.format_combo.currentData() or "decimal"),
                    start_mode=str(row.start_mode_combo.currentData() or "restart"),
                    start_value=max(1, int(round(row.start_value_spin.value()))),
                )
            )
        return phases

    def _apply_page_number_preset(self, preset_id: str) -> None:
        if self._owner._current_template is None:
            return
        if preset_id == "split_restart":
            phases = split_page_number_preset(continue_body=False)
        elif preset_id == "split_continue":
            phases = split_page_number_preset(continue_body=True)
        else:
            phases = continuous_page_number_preset()

        self._owner._is_syncing = True
        try:
            self._rebuild_page_phase_rows(phases)
        finally:
            self._owner._is_syncing = False
        self._owner._on_structure_edited()

    def _on_add_phase(self) -> None:
        if self._owner._current_template is None:
            return
        self._owner._is_syncing = True
        try:
            self._page_advanced_section.set_expanded(True)
            self._append_page_phase_row(self._build_empty_phase())
            self._page_phase_rows[-1].section.set_expanded(True)
            self._refresh_page_phase_row_state()
        finally:
            self._owner._is_syncing = False
        self.apply_theme()
        self._owner._on_structure_edited()

    def _remove_phase_row(self, row: PageNumberPhaseControls) -> None:
        if self._owner._current_template is None or len(self._page_phase_rows) <= 1:
            return
        if row not in self._page_phase_rows:
            return
        for index in range(self._page_phase_rows_layout.count()):
            item = self._page_phase_rows_layout.itemAt(index)
            if item is not None and item.widget() is row.section:
                self._page_phase_rows_layout.takeAt(index)
                break
        self._page_phase_rows.remove(row)
        row.section.setParent(None)
        row.section.deleteLater()
        self._refresh_page_phase_row_state()
        self.apply_theme()
        self._owner._on_structure_edited()

    def _duplicate_phase_row(self, row: PageNumberPhaseControls) -> None:
        if self._owner._current_template is None or row not in self._page_phase_rows:
            return
        phases = self.phase_rows_to_configs()
        index = self._page_phase_rows.index(row)
        copied = deepcopy(phases[index])
        copied.phase_id = self._unique_phase_id(copied.phase_id or f"phase_{index + 1}")
        phases.insert(index + 1, copied)
        self._owner._is_syncing = True
        try:
            self._rebuild_page_phase_rows(phases)
            self._page_phase_rows[index + 1].section.set_expanded(True)
        finally:
            self._owner._is_syncing = False
        self._owner._on_structure_edited()

    def _move_phase_row(self, row: PageNumberPhaseControls, direction: int) -> None:
        if self._owner._current_template is None or row not in self._page_phase_rows:
            return
        index = self._page_phase_rows.index(row)
        target = index + int(direction)
        if target < 0 or target >= len(self._page_phase_rows):
            return
        phases = self.phase_rows_to_configs()
        phases[index], phases[target] = phases[target], phases[index]
        self._owner._is_syncing = True
        try:
            self._rebuild_page_phase_rows(phases)
            self._page_phase_rows[target].section.set_expanded(True)
        finally:
            self._owner._is_syncing = False
        self._owner._on_structure_edited()

    def _unique_phase_id(self, base: str) -> str:
        existing = {phase.phase_id for phase in self.phase_rows_to_configs()}
        stem = str(base or "phase").strip() or "phase"
        candidate = f"{stem}_copy"
        suffix = 2
        while candidate in existing:
            candidate = f"{stem}_copy_{suffix}"
            suffix += 1
        return candidate

    def _on_phase_row_meta_changed(self, *_args) -> None:
        if self._owner._is_syncing:
            return
        self._refresh_page_phase_row_state()
        self._owner._on_structure_edited()

    def _on_phase_start_mode_changed(self, row: PageNumberPhaseControls) -> None:
        if self._owner._is_syncing:
            return
        row.start_value_spin.setEnabled(str(row.start_mode_combo.currentData() or "restart") == "restart")
        self._refresh_page_phase_row_state()
        self._owner._on_structure_edited()

    def _set_combo_by_data(self, combo: StyledComboBox, target) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == target:
                combo.setCurrentIndex(index)
                return

    def clear(self) -> None:
        self._rebuild_page_phase_rows([], ensure_one=False)
        self._page_plan_alert.hide()

    def set_header_footer(self, header_footer) -> None:
        self._set_combo_by_data(
            self._page_validation_mode_combo,
            getattr(header_footer.page_number_plan, "validation_mode", "strict"),
        )
        self._set_combo_by_data(
            self._page_missing_doc_tree_combo,
            getattr(header_footer.page_number_plan, "on_missing_doc_tree", "warn_and_fallback"),
        )
        self._rebuild_page_phase_rows(default_page_number_phases(header_footer))

    def apply_to(self, header_footer) -> None:
        header_footer.page_number_plan.validation_mode = str(
            self._page_validation_mode_combo.currentData() or "strict"
        )
        header_footer.page_number_plan.on_missing_doc_tree = str(
            self._page_missing_doc_tree_combo.currentData() or "warn_and_fallback"
        )
        header_footer.page_number_plan.phases = self.phase_rows_to_configs()

    def set_enabled_visible(self, enabled: bool) -> None:
        self.section.setVisible(enabled)
        self.section.setEnabled(enabled)

    def refresh_validation_alert(self, template: TemplateConfig | None) -> None:
        if template is None:
            self._page_plan_alert.hide()
            return

        diagnostics = collect_static_page_number_diagnostics(template.header_footer)
        if not diagnostics:
            self._page_plan_alert.hide()
            return

        variant = "error" if any(item.level == "error" for item in diagnostics) else "warning"
        message = self._page_plan_alert_message(diagnostics)
        self._page_plan_alert.set_variant(variant)
        self._page_plan_alert.set_message(message)
        self._page_plan_alert.show()
        self._page_advanced_section.set_expanded(True)

    def _page_plan_alert_message(self, diagnostics) -> str:
        missing_scope_text = "尚未选择编号分区"
        missing_scope_count = sum(
            1 for item in diagnostics if missing_scope_text in str(getattr(item, "message", ""))
        )
        if missing_scope_count < 2:
            return "\n\n".join(format_page_number_diagnostic_text(item) for item in diagnostics)

        messages = [
            f"有 {missing_scope_count} 条页码结果未选择编号分区。展开对应项选择分区，或删除空项。"
        ]
        messages.extend(
            format_page_number_diagnostic_text(item)
            for item in diagnostics
            if missing_scope_text not in str(getattr(item, "message", ""))
        )
        return "\n\n".join(messages)

    def apply_theme(self) -> None:
        apply_button_variant(self._preset_continuous_btn, "secondary")
        apply_button_variant(self._preset_split_restart_btn, "secondary")
        apply_button_variant(self._preset_split_continue_btn, "secondary")
        apply_button_variant(self._add_phase_btn, "ghost-primary")
        for row in self._page_phase_rows:
            apply_button_variant(row.move_up_btn, "secondary")
            apply_button_variant(row.move_down_btn, "secondary")
            apply_button_variant(row.duplicate_btn, "secondary")
            apply_button_variant(row.remove_btn, "ghost-danger")


__all__ = [
    "PageNumberPlanSection",
    "PageNumberPhaseControls",
    "PageSelectorEditor",
    "SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS",
    "continuous_page_number_preset",
    "default_page_number_phases",
    "default_suppress_header_footer_selectors",
    "ensure_default_page_number_phases",
    "page_number_phase_brief",
    "split_page_number_preset",
]
