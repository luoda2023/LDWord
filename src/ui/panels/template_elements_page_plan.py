"""Page-number plan controls for the template elements detail pane."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from src.config.feature_configs import default_continuous_page_number_phases
from src.config.header_footer_presets import (
    split_page_number_phases,
    toc_roman_body_decimal_phases,
)
from src.config.special_title_rules import special_title_selector_label
from src.config.template import PageNumberPhaseConfig, TemplateConfig
from src.qt_api import (
    QApplication,
    QEvent,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSize,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.engine.page_number_planner import (
    collect_static_page_number_diagnostics,
    expand_page_number_selectors,
    format_page_number_diagnostic_text,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.flow_layout import FlowLayout
from src.shared.ui.flow_section import FlowSection
from src.shared.ui.inline_alert import InlineAlert
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.layout_sync import (
    refresh_layout_chain,
    refresh_layout_chain_later,
    updates_suspended,
)
from src.shared.ui.sizing import apply_size_class, control_size_metrics
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.template_form_layout import (
    TemplateFormGrid,
    compact_form_column_gap,
    template_form_row,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.viewport_mutation import viewport_mutation_for_widget

if TYPE_CHECKING:
    from src.ui.panels.template_elements_detail import ElementsDetail


PAGE_NUMBER_FORMAT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("decimal", "阿拉伯数字"),
    ("upperRoman", "大写罗马"),
    ("lowerRoman", "小写罗马"),
    ("upperLetter", "大写字母"),
    ("lowerLetter", "小写字母"),
    ("ordinal", "序数"),
    ("cardinalText", "英文基数词"),
    ("ordinalText", "英文序数词"),
    ("decimalZero", "补零数字"),
    ("decimalFullWidth", "全角数字"),
)

PAGE_NUMBER_START_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("restart", "重新起号"),
    ("continue", "延续前段"),
)

PAGE_NUMBER_VALIDATION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("strict", "阻止生成"),
    ("warn", "只提醒"),
)

PAGE_NUMBER_DOC_TREE_POLICY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("warn_and_fallback", "提醒并按默认结构处理"),
    ("fallback", "按默认结构处理"),
)

PAGE_NUMBER_RULE_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("continuous", "全文连续编号"),
    ("split_restart", "前置罗马，正文从 1"),
    ("split_continue", "前置罗马，正文续号"),
    ("toc_roman_body_decimal", "仅目录罗马，正文从 1"),
    ("custom", "自定义编号分组"),
)

PAGE_NUMBER_SELECTOR_OPTIONS: tuple[tuple[str, str], ...] = (
    ("all_numbered_content", "全文"),
    ("front_matter", "前置部分"),
    ("body", "其余正文"),
    ("back_matter", "后置部分"),
    ("cover", "封面"),
)

SUPPRESS_HEADER_FOOTER_SELECTOR_OPTIONS: tuple[tuple[str, str], ...] = (
    ("pre_numbering", "封面"),
    ("cover", "封面"),
    ("front_matter", "前置部分"),
    ("toc", "目录"),
    ("body", "其余正文"),
    ("back_matter", "后置部分"),
    ("references", "参考文献"),
    ("appendix", "附录"),
)

_SECTION_TYPE_LABELS: dict[str, str] = {
    "cover": "封面",
    "abstract_cn": "中文摘要",
    "abstract_en": "英文摘要",
    "toc": "目录",
    "body": "其余正文",
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


split_page_number_preset = split_page_number_phases


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
        label_map.get(
            str(selector or "").strip(),
            special_title_selector_label(selector),
        )
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
    return "、".join(labels) if labels else "未设置不显示页面"


def _section_type_label(section_type: str) -> str:
    normalized = str(section_type or "").strip()
    return _SECTION_TYPE_LABELS.get(
        normalized,
        special_title_selector_label(normalized),
    )


def _section_type_labels(section_types: set[str] | frozenset[str]) -> str:
    order = {section_type: index for index, section_type in enumerate(_SECTION_TYPE_PREVIEW_ORDER)}
    sorted_types = sorted(
        (str(section_type or "").strip() for section_type in section_types if str(section_type or "").strip()),
        key=lambda section_type: (order.get(section_type, len(order)), section_type),
    )
    return "、".join(_section_type_label(section_type) for section_type in sorted_types)


def _page_number_format_label(value: str) -> str:
    return dict(PAGE_NUMBER_FORMAT_OPTIONS).get(str(value or "decimal"), "阿拉伯数字")


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
        hint_text: str = "",
        allow_custom_input: bool = True,
        retain_unknown_selectors: bool = False,
    ):
        super().__init__(parent)
        self._is_syncing = False
        self._options = tuple(options)
        self._allow_custom_input = bool(allow_custom_input)
        self._retain_unknown_selectors = bool(retain_unknown_selectors)
        self._retained_selectors: list[str] = []
        self._selector_buttons: dict[str, QPushButton] = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignTop)

        self._chips = QWidget(self)
        self._chips.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._chips_layout = FlowLayout(self._chips, h_spacing=8, v_spacing=8)

        for selector, label in self._options:
            self._add_selector_button(selector, label)

        layout.addWidget(self._chips)

        self._custom_edit = QLineEdit(self)
        self._custom_edit.setPlaceholderText("补充已识别分区名")
        self._custom_edit.setVisible(self._allow_custom_input)
        self._custom_edit.textChanged.connect(self._emit_changed)
        layout.addWidget(self._custom_edit)

        self._hint = QLabel(hint_text, self)
        self._hint.setObjectName("tpl_selector_hint")
        self._hint.setWordWrap(True)
        self._hint.setVisible(bool(str(hint_text or "").strip()))
        layout.addWidget(self._hint)

        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self._sync_chips_height()

    def _add_selector_button(self, selector: str, label: str) -> None:
        button = QPushButton(label, self._chips)
        button.setCheckable(True)
        button.clicked.connect(self._emit_changed)
        self._selector_buttons[selector] = button
        self._chips_layout.addWidget(button)

    def set_options(
        self,
        options: Iterable[tuple[str, str]],
        *,
        preserve_selection: bool = True,
    ) -> None:
        """Replace visible scope chips without emitting a user edit."""

        selected = self.selectors() if preserve_selection else []
        normalized_options: list[tuple[str, str]] = []
        seen: set[str] = set()
        for raw_selector, raw_label in options:
            selector = str(raw_selector or "").strip()
            if not selector or selector in seen:
                continue
            seen.add(selector)
            normalized_options.append((selector, str(raw_label or selector)))

        self._is_syncing = True
        try:
            while self._chips_layout.count():
                item = self._chips_layout.takeAt(0)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()
            self._selector_buttons.clear()
            self._options = tuple(normalized_options)
            for selector, label in self._options:
                self._add_selector_button(selector, label)
        finally:
            self._is_syncing = False
        self.set_selectors(selected)
        self._apply_theme()
        self._sync_chips_height()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        width = max(1, int(width))
        margins = self.layout().contentsMargins()
        spacing = self.layout().spacing()
        chips_height = max(0, self._chips_layout.heightForWidth(width))
        visible_heights = [chips_height]
        if self._custom_edit.isVisible():
            visible_heights.append(
                max(self._custom_edit.sizeHint().height(), self._custom_edit.minimumSizeHint().height())
            )
        if self._hint.isVisible():
            hint_height = self._hint.heightForWidth(width) if self._hint.hasHeightForWidth() else self._hint.sizeHint().height()
            visible_heights.append(max(self._hint.minimumSizeHint().height(), hint_height))
        return (
            margins.top()
            + margins.bottom()
            + sum(visible_heights)
            + spacing * max(0, len(visible_heights) - 1)
        )

    def sizeHint(self) -> QSize:
        width = max(1, self.width() or self._DEFAULT_LAYOUT_WIDTH)
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        width = max(1, self.width() or self._DEFAULT_LAYOUT_WIDTH)
        return QSize(0, self.heightForWidth(width))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_chips_height()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_chips_height()

    def _sync_chips_height(self) -> None:
        width = max(1, self._chips.width() or self.width() or self._DEFAULT_LAYOUT_WIDTH)
        height = max(0, self._chips_layout.heightForWidth(width))
        geometry_changed = False
        if self._chips.minimumHeight() != height:
            self._chips.setMinimumHeight(height)
            geometry_changed = True
        if self._chips.maximumHeight() != height:
            self._chips.setMaximumHeight(height)
            geometry_changed = True
        if geometry_changed:
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
            self._custom_edit.setText(_selector_text(extras) if self._allow_custom_input else "")
            self._retained_selectors = (
                list(extras)
                if self._retain_unknown_selectors
                else []
            )
        finally:
            self._is_syncing = False

    def selectors(self) -> list[str]:
        selected = [
            selector
            for selector, _label in self._options
            if self._selector_buttons[selector].isChecked()
        ]
        if self._allow_custom_input:
            selected.extend(
                selector
                for selector in _parse_selector_text(self._custom_edit.text())
                if selector not in selected
            )
        selected.extend(
            selector
            for selector in self._retained_selectors
            if selector not in selected
        )
        return selected

    def _emit_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        self.changed.emit()

    def _apply_theme(self) -> None:
        theme = get_theme()
        button_metrics = control_size_metrics(
            theme,
            "sm",
            vertical_padding=2,
            border_width=1,
        )
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
            f"min-height: {button_metrics.content_height}px;"
            f"max-height: {button_metrics.content_height}px;"
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
            apply_size_class(button, "sm")
            button.setStyleSheet(button_stylesheet)
        self._sync_chips_height()


class PageNumberPlanSection:
    """Owns the page-number plan card and dynamic rule rows."""

    def __init__(
        self,
        owner: "ElementsDetail",
        *,
        container: Card | None = None,
        embedded: bool = False,
        group_title_builder=None,
    ):
        self._owner = owner
        self._page_phase_rows: list[PageNumberPhaseControls] = []
        self._selector_options = PAGE_NUMBER_SELECTOR_OPTIONS
        self._embedded = bool(embedded)
        self._group_title_builder = group_title_builder
        self._syncing_numbering_mode = False

        host = container or Card(parent=owner._editor_column)
        self.section = host
        self._page_plan_section = self.section
        owner._page_plan_section = self.section
        if container is None:
            owner._add_card_header(self.section, "list-ordered", "页码编号")
            owner._editor_layout.addWidget(self.section)
        elif callable(self._group_title_builder):
            self.section.add_widget(self._group_title_builder("页码编号", parent=self.section))
            self._embedded_note = QLabel("", self.section)
            self._embedded_note.setObjectName("tpl_phase_plan_note")
            self._embedded_note.setWordWrap(True)
            self._embedded_note.setVisible(False)
            self.section.add_widget(self._embedded_note)
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
        for combo in (self._page_validation_mode_combo, self._page_missing_doc_tree_combo):
            combo.hide()
            combo.setFocusPolicy(Qt.NoFocus)

        self._page_plan_note = QLabel("", self._owner)
        self._page_plan_note.setObjectName("tpl_phase_plan_note")
        self._page_plan_note.setWordWrap(True)
        self._page_plan_note.setVisible(False)
        self.section.add_widget(self._page_plan_note)

        self._numbering_mode_combo = StyledComboBox(self._owner)
        for value, label in PAGE_NUMBER_RULE_MODE_OPTIONS:
            self._numbering_mode_combo.addItem(label, value)
        self._numbering_mode_combo.currentIndexChanged.connect(self._on_numbering_mode_changed)
        self._numbering_mode_row = self._form_row("编号方式", self._numbering_mode_combo, parent=self.section)

        self._preset_buttons = QWidget(self._owner)
        self._preset_buttons.hide()
        preset_layout = QHBoxLayout(self._preset_buttons)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(8)

        self._preset_continuous_btn = QPushButton("全文连续编号", self._preset_buttons)
        self._preset_continuous_btn.clicked.connect(
            lambda: self._apply_page_number_preset("continuous")
        )
        preset_layout.addWidget(self._preset_continuous_btn)

        self._preset_split_restart_btn = QPushButton("前置罗马，正文从 1", self._preset_buttons)
        self._preset_split_restart_btn.clicked.connect(
            lambda: self._apply_page_number_preset("split_restart")
        )
        preset_layout.addWidget(self._preset_split_restart_btn)

        self._preset_split_continue_btn = QPushButton("前置罗马，正文续号", self._preset_buttons)
        self._preset_split_continue_btn.clicked.connect(
            lambda: self._apply_page_number_preset("split_continue")
        )
        preset_layout.addWidget(self._preset_split_continue_btn)

        preset_layout.addStretch(1)
        self._preset_row = self._numbering_mode_row
        self.section.add_widget(self._preset_row)

        self._page_advanced_section = FlowSection("编号分组", expanded=True, parent=self.section)

        self._page_plan_alert = InlineAlert("", variant="warning", parent=self._page_advanced_section)
        self._page_plan_alert.hide()
        self._page_advanced_section.add_widget(self._page_plan_alert)

        advanced_actions = QWidget(self._page_advanced_section)
        advanced_actions_layout = QHBoxLayout(advanced_actions)
        advanced_actions_layout.setContentsMargins(0, 0, 0, 0)
        advanced_actions_layout.setSpacing(8)
        advanced_actions_layout.addStretch(1)

        self._add_phase_btn = QPushButton("添加编号分组", advanced_actions)
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

    def _insert_page_phase_row(
        self,
        phase: PageNumberPhaseConfig,
        *,
        index: int | None = None,
    ) -> PageNumberPhaseControls:
        section = FlowSection("未选择范围", expanded=True, parent=self._page_phase_rows_host)

        phase_id_edit = QLineEdit(section)
        phase_id_edit.setPlaceholderText("例如：前置 / 正文 / 附录")
        phase_id_edit.hide()

        selector_editor = PageSelectorEditor(
            section,
            options=self._selector_options,
            hint_text="",
            allow_custom_input=False,
            retain_unknown_selectors=True,
        )
        selector_preview = QLabel("", section)
        selector_preview.setObjectName("tpl_phase_selector_preview")
        selector_preview.setWordWrap(True)
        selector_preview.setVisible(False)
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

        selector_row = self._form_row("包含部分", selector_editor, parent=section)
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

        if index is None:
            self._page_phase_rows_layout.addWidget(section)
            self._page_phase_rows.append(controls)
        else:
            target = max(0, min(int(index), len(self._page_phase_rows)))
            self._page_phase_rows_layout.insertWidget(target, section)
            self._page_phase_rows.insert(target, controls)

        phase_id_edit.setText(str(phase.phase_id or ""))
        selector_editor.set_selectors(list(phase.selectors or []))
        visible_toggle.setChecked(bool(phase.visible))
        self._set_combo_by_data(format_combo, phase.number_format or "decimal")
        self._set_combo_by_data(start_mode_combo, phase.start_mode or "restart")
        start_value_spin.setValue(float(max(1, int(phase.start_value or 1))))
        return controls

    def _settle_incremental_phase_rows(self) -> None:
        """Synchronously settle an insert or move without rebuilding every row."""

        self._refresh_page_phase_row_state()
        self.apply_theme()
        refresh_layout_chain(self._page_phase_rows_host, passes=1)

    def _phase_viewport_mutation(self, anchor: QWidget | None):
        return viewport_mutation_for_widget(
            self._owner,
            anchor=anchor,
            layout_roots=(self._page_phase_rows_host, self.section),
            paint_targets=(self.section, self._owner),
        )

    def _rebuild_page_phase_rows(
        self,
        phases: list[PageNumberPhaseConfig],
        *,
        ensure_one: bool = True,
    ) -> None:
        with updates_suspended(self.section, self._owner._editor_column):
            self._clear_page_phase_rows()
            phase_list = [deepcopy(phase) for phase in phases]
            if ensure_one and not phase_list:
                phase_list = continuous_page_number_preset()
            for phase in phase_list:
                self._insert_page_phase_row(phase)
            self._refresh_page_phase_row_state()
            self.apply_theme()
            refresh_layout_chain(self.section)
        refresh_layout_chain_later(self.section)

    def _refresh_page_phase_row_state(self) -> None:
        row_count = len(self._page_phase_rows)
        matched_by_section = self._matched_sections_by_phase_row()
        for index, row in enumerate(self._page_phase_rows, start=1):
            matched_sections = matched_by_section.get(id(row), set())
            row.section._toggle_button.setText(
                self._phase_section_title(index, row)
            )
            preview_text = self._phase_preview_text(row, matched_sections)
            row.selector_preview.setText(preview_text)
            row.selector_preview.setVisible(bool(preview_text))
            start_mode = str(row.start_mode_combo.currentData() or "restart")
            row.start_value_spin.setEnabled(start_mode == "restart")
            row.remove_btn.setEnabled(row_count > 1)
            row.move_up_btn.setEnabled(index > 1)
            row.move_down_btn.setEnabled(index < row_count)

    def _matched_sections_by_phase_row(self) -> dict[int, set[str]]:
        matched_by_row: dict[int, set[str]] = {}
        for row in self._page_phase_rows:
            matched_by_row[id(row)] = set(expand_page_number_selectors(row.selector_editor.selectors()))
        return matched_by_row

    def _phase_preview_text(
        self,
        row: PageNumberPhaseControls,
        matched_sections: set[str],
    ) -> str:
        selectors = row.selector_editor.selectors()
        lines: list[str] = []
        if not selectors:
            lines.append("请选择这一组包含的部分。")
        elif not matched_sections:
            lines.append("这些范围没有匹配到已知分区。")

        overlap_sections = self._overlapped_sections_for_row(row, matched_sections)
        if overlap_sections:
            lines.append(f"{_section_type_labels(overlap_sections)} 同时出现在多个编号分组中。")
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

    def _phase_section_title(
        self,
        index: int,
        row: PageNumberPhaseControls,
        *,
        hidden_sections: set[str] | frozenset[str] | None = None,
    ) -> str:
        scope_text = _selector_title_brief(row.selector_editor.selectors())
        if scope_text == "未选择范围":
            return "未选择范围"
        if not row.visible_toggle.isChecked():
            return f"{scope_text}：不显示页码"

        format_label = {
            "decimal": "阿拉伯数字",
            "upperRoman": "大写罗马",
            "lowerRoman": "小写罗马",
            "upperLetter": "大写字母",
            "lowerLetter": "小写字母",
            "ordinal": "序数",
            "cardinalText": "英文基数词",
            "ordinalText": "英文序数词",
            "decimalZero": "补零数字",
            "decimalFullWidth": "全角数字",
        }.get(
            str(row.format_combo.currentData() or "decimal"),
            "阿拉伯数字",
        )
        start_mode = str(row.start_mode_combo.currentData() or "restart")
        if start_mode == "continue":
            title = f"{scope_text}：{format_label}，延续前段"
            return title
        start_value = max(1, int(round(row.start_value_spin.value())))
        if start_value == 1:
            title = f"{scope_text}：{format_label}，从 1 起"
            return title
        title = f"{scope_text}：{format_label}，从 {start_value} 起"
        return title

    def _phase_title_with_exclusions(
        self,
        title: str,
        hidden_sections: set[str] | frozenset[str] | None,
    ) -> str:
        if not hidden_sections:
            return title
        return f"{title}（不含{_section_type_labels(hidden_sections)}）"

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

    def _on_numbering_mode_changed(self, *_args) -> None:
        if self._syncing_numbering_mode:
            return
        mode = str(self._numbering_mode_combo.currentData() or "continuous")
        if mode == "custom":
            self._sync_rule_editor_visibility()
            self._owner._on_structure_edited()
            return
        self._apply_page_number_preset(mode)

    def _set_numbering_mode(self, mode: str) -> None:
        self._syncing_numbering_mode = True
        try:
            self._set_combo_by_data(self._numbering_mode_combo, mode)
        finally:
            self._syncing_numbering_mode = False
        self._sync_rule_editor_visibility()

    def _sync_numbering_mode_from_phases(self, phases: list[PageNumberPhaseConfig]) -> None:
        self._set_numbering_mode(self._preset_id_for_phases(phases))

    def _sync_rule_editor_visibility(self) -> None:
        custom = str(self._numbering_mode_combo.currentData() or "continuous") == "custom"
        self._page_advanced_section.setVisible(custom)
        if custom:
            self._page_advanced_section.set_expanded(True)

    def _preset_id_for_phases(self, phases: list[PageNumberPhaseConfig]) -> str:
        candidates = {
            "continuous": continuous_page_number_preset(),
            "split_restart": split_page_number_preset(continue_body=False),
            "split_continue": split_page_number_preset(continue_body=True),
            "toc_roman_body_decimal": toc_roman_body_decimal_phases(),
        }
        for preset_id, preset_phases in candidates.items():
            if self._phases_match(phases, preset_phases):
                return preset_id
        return "custom"

    def _phases_match(
        self,
        phases: list[PageNumberPhaseConfig],
        expected: list[PageNumberPhaseConfig],
    ) -> bool:
        if len(phases) != len(expected):
            return False
        for left, right in zip(phases, expected):
            if list(left.selectors or []) != list(right.selectors or []):
                return False
            if bool(left.visible) != bool(right.visible):
                return False
            if str(left.number_format or "decimal") != str(right.number_format or "decimal"):
                return False
            if str(left.start_mode or "restart") != str(right.start_mode or "restart"):
                return False
            if int(left.start_value or 1) != int(right.start_value or 1):
                return False
        return True

    def _apply_page_number_preset(self, preset_id: str) -> None:
        if self._owner._current_template is None:
            return
        if preset_id == "split_restart":
            phases = split_page_number_preset(continue_body=False)
        elif preset_id == "split_continue":
            phases = split_page_number_preset(continue_body=True)
        elif preset_id == "toc_roman_body_decimal":
            phases = toc_roman_body_decimal_phases()
        else:
            phases = continuous_page_number_preset()

        with self._phase_viewport_mutation(self._numbering_mode_combo):
            self._owner._is_syncing = True
            try:
                self._rebuild_page_phase_rows(phases)
                self._set_numbering_mode(preset_id)
            finally:
                self._owner._is_syncing = False
            self._owner._on_structure_edited()

    def _on_add_phase(self) -> None:
        if self._owner._current_template is None:
            return
        with self._phase_viewport_mutation(self._add_phase_btn):
            self._owner._is_syncing = True
            try:
                self._set_numbering_mode("custom")
                self._page_advanced_section.set_expanded(True)
                self._insert_page_phase_row(self._build_empty_phase())
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
        row_index = self._page_phase_rows.index(row)
        anchor = (
            self._page_phase_rows[row_index + 1].section
            if row_index + 1 < len(self._page_phase_rows)
            else self._page_phase_rows[row_index - 1].section
        )
        with self._phase_viewport_mutation(anchor):
            for index in range(self._page_phase_rows_layout.count()):
                item = self._page_phase_rows_layout.itemAt(index)
                if item is not None and item.widget() is row.section:
                    self._page_phase_rows_layout.takeAt(index)
                    break
            self._page_phase_rows.remove(row)
            row.section.hide()
            row.section.setParent(None)
            row.section.deleteLater()
            self._refresh_page_phase_row_state()
            self.apply_theme()
            self._owner._on_structure_edited()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            QApplication.sendPostedEvents(None, QEvent.LayoutRequest)
            refresh_layout_chain(self._owner._editor_column, passes=2)

    def _duplicate_phase_row(self, row: PageNumberPhaseControls) -> None:
        if self._owner._current_template is None or row not in self._page_phase_rows:
            return
        phases = self.phase_rows_to_configs()
        index = self._page_phase_rows.index(row)
        copied = deepcopy(phases[index])
        copied.phase_id = self._unique_phase_id(copied.phase_id or f"phase_{index + 1}")
        with self._phase_viewport_mutation(row.section):
            self._owner._is_syncing = True
            try:
                with updates_suspended(
                    self._page_phase_rows_host,
                    self.section,
                    self._owner._editor_column,
                ):
                    self._insert_page_phase_row(copied, index=index + 1)
                    self._settle_incremental_phase_rows()
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
        with self._phase_viewport_mutation(row.section):
            self._owner._is_syncing = True
            try:
                with updates_suspended(
                    self._page_phase_rows_host,
                    self.section,
                    self._owner._editor_column,
                ):
                    layout_index = self._page_phase_rows_layout.indexOf(row.section)
                    if layout_index < 0:
                        return
                    self._page_phase_rows_layout.takeAt(layout_index)
                    self._page_phase_rows.pop(index)
                    self._page_phase_rows.insert(target, row)
                    self._page_phase_rows_layout.insertWidget(target, row.section)
                    self._settle_incremental_phase_rows()
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

    def set_selector_options(
        self,
        options: Iterable[tuple[str, str]],
    ) -> None:
        self._selector_options = tuple(options)
        for row in self._page_phase_rows:
            row.selector_editor.set_options(self._selector_options)

    def set_header_footer(self, header_footer) -> None:
        self._set_combo_by_data(
            self._page_validation_mode_combo,
            getattr(header_footer.page_number_plan, "validation_mode", "strict"),
        )
        self._set_combo_by_data(
            self._page_missing_doc_tree_combo,
            getattr(header_footer.page_number_plan, "on_missing_doc_tree", "warn_and_fallback"),
        )
        phases = default_page_number_phases(header_footer)
        self._rebuild_page_phase_rows(phases)
        self._sync_numbering_mode_from_phases(phases)

    def apply_to(self, header_footer) -> None:
        header_footer.page_number_plan.validation_mode = str(
            self._page_validation_mode_combo.currentData() or "strict"
        )
        header_footer.page_number_plan.on_missing_doc_tree = str(
            self._page_missing_doc_tree_combo.currentData() or "warn_and_fallback"
        )
        header_footer.page_number_plan.phases = self.phase_rows_to_configs()

    def set_enabled_visible(self, enabled: bool) -> None:
        with updates_suspended(self.section, self._owner._editor_column):
            self.section.setVisible(True)
            self.section.setEnabled(True)
            self._page_plan_note.setVisible(False)
            self._preset_row.setVisible(True)
            self._preset_row.setEnabled(bool(enabled))
            self._sync_rule_editor_visibility()
            self._page_advanced_section.setEnabled(bool(enabled))
            refresh_layout_chain(self.section)
        refresh_layout_chain_later(self.section)

    def refresh_validation_alert(self, template: TemplateConfig | None) -> None:
        if template is None:
            self._page_plan_alert.hide()
            return

        diagnostics = [
            item
            for item in collect_static_page_number_diagnostics(template.header_footer)
            if not self._is_exclusion_overlap_diagnostic(item)
        ]
        if not diagnostics:
            self._page_plan_alert.hide()
            return

        variant = "error" if any(item.level == "error" for item in diagnostics) else "warning"
        message = self._page_plan_alert_message(diagnostics)
        self._page_plan_alert.set_variant(variant)
        self._page_plan_alert.set_message(message)
        self._page_plan_alert.show()
        self._set_numbering_mode("custom")
        self._page_advanced_section.set_expanded(True)

    def _is_exclusion_overlap_diagnostic(self, diagnostic) -> bool:
        message = str(getattr(diagnostic, "message", "") or "")
        return "包含已排除部分" in message

    def _page_plan_alert_message(self, diagnostics) -> str:
        missing_scope_count = sum(
            1
            for item in diagnostics
            if self._is_missing_scope_diagnostic(item)
        )
        if missing_scope_count < 2:
            return "\n\n".join(self._friendly_page_plan_diagnostic_text(item) for item in diagnostics)

        messages = [
            f"有 {missing_scope_count} 个编号分组尚未选择范围。"
        ]
        messages.extend(
            self._friendly_page_plan_diagnostic_text(item)
            for item in diagnostics
            if not self._is_missing_scope_diagnostic(item)
        )
        return "\n\n".join(messages)

    def _is_missing_scope_diagnostic(self, diagnostic) -> bool:
        message = str(getattr(diagnostic, "message", "") or "")
        return "尚未选择" in message and "范围" in message

    def _friendly_page_plan_diagnostic_text(self, diagnostic) -> str:
        message = str(getattr(diagnostic, "message", "") or "")
        if self._is_missing_scope_diagnostic(diagnostic):
            return "有编号分组尚未选择范围。"
        if "同时属于多个编号分组" in message:
            return "有部分内容同时属于多个编号分组，请调整范围。"
        if "没有匹配到已知分区" in message:
            return "有编号分组没有匹配到已知分区。"
        if "编号分组名称" in message and "重复" in message:
            return "编号分组名称重复，请调整后再生成。"
        return format_page_number_diagnostic_text(diagnostic)

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
    "ensure_default_page_number_phases",
    "page_number_phase_brief",
    "split_page_number_preset",
]
