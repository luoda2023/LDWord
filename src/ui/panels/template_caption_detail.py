"""Caption detail pane for template management."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.style_semantics import (
    LINE_SPACING_OPTIONS,
    SPACING_UNIT_OPTIONS,
    line_spacing_is_editable,
    line_spacing_unit_label,
    normalize_line_spacing_type,
    resolve_line_spacing_value,
    resolve_style_paragraph_spacing,
    spacing_editor_config,
)
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QHBoxLayout, QLabel, QLineEdit, QPushButton, QSize, QVBoxLayout, QWidget, QSizePolicy, Signal
from src.shared.ui.button_style import build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.sizing import resolved_control_height
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGridItem
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.template_summary_card import (
    TemplateSummaryCard,
    apply_template_summary_action_button,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.typography_controls import build_emphasis_widget
from src.ui.panels.template_summary_projection import build_template_detail_summary_items


NUMBERING_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("chapter", "按章节编号"),
    ("global", "全文连续"),
)

NUMBERING_FORMAT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("chapter.seq", "1.1（章节.序号）"),
    ("chapter-seq", "1-1（章节-序号）"),
    ("chapter:seq", "1:1（章节:序号）"),
    ("seq", "1（纯序号）"),
)

AUTO_INSERT_OPTIONS: tuple[tuple[bool, str], ...] = (
    (True, "自动补齐"),
    (False, "不自动补齐"),
)

NUMBERING_TYPE_OPTIONS: tuple[tuple[bool, str], ...] = (
    (False, "固定文本编号"),
    (True, "Word 可更新编号"),
)

CAPTION_SEPARATOR_OPTIONS: tuple[tuple[str, str, str | None], ...] = (
    ("fullwidth_space", "全角空格（□）", "\u3000"),
    ("halfwidth_space", "半角空格（·）", " "),
    ("none", "无间隔", ""),
    ("tab", "制表符（→）", "\t"),
    ("custom", "自定义", None),
)

ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
)


def _caption_text_input_stylesheet(theme) -> str:
    content_height = max(24, resolved_control_height(theme, "md") - 2)
    return f"""
{build_text_input_stylesheet(theme, selector="QLineEdit")}
QLineEdit {{
    min-height: {content_height}px;
    max-height: {content_height}px;
    padding-top: 0px;
    padding-bottom: 0px;
}}
""".strip()


class _VisibleWhitespaceLineEdit(QLineEdit):
    _TO_SYMBOL = {
        "\u3000": "□",
        " ": "·",
        "\t": "→",
    }
    _FROM_SYMBOL = {symbol: raw for raw, symbol in _TO_SYMBOL.items()}

    def setRawText(self, raw: str) -> None:
        super().setText("".join(self._TO_SYMBOL.get(ch, ch) for ch in str(raw or "")))

    def text(self) -> str:
        return "".join(self._FROM_SYMBOL.get(ch, ch) for ch in super().text())


class _CaptionSeparatorInput(QWidget):
    textChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._preset_values = {
            key: value for key, _label, value in CAPTION_SEPARATOR_OPTIONS if value is not None
        }
        self._value_to_key = {
            value: key for key, _label, value in CAPTION_SEPARATOR_OPTIONS if value is not None
        }
        self._custom_raw_text = ""
        self._current_key = "custom"
        self._is_syncing = False
        self._control_height = resolved_control_height(get_theme(), "md")

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(self._control_height)
        self.setMaximumHeight(self._control_height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._mode_combo = StyledComboBox(self)
        self._mode_combo.set_full_width_mode(True)
        self._mode_combo.setToolTip("选择编号和标题之间的间隔字符。")
        for key, label, _value in CAPTION_SEPARATOR_OPTIONS:
            self._mode_combo.addItem(label, key)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self._mode_combo, 1)

        self._custom_edit = _VisibleWhitespaceLineEdit(self)
        self._custom_edit.setToolTip("输入时：全角空格=□，半角空格=·，Tab=→。")
        self._custom_edit.setVisible(False)
        self._custom_edit.textChanged.connect(self._on_custom_text_changed)
        layout.addWidget(self._custom_edit, 1)

        self.setRawText("\u3000")

    def setText(self, raw: str) -> None:
        self._set_raw_text(raw, emit=True)

    def setRawText(self, raw: str) -> None:
        self._set_raw_text(raw, emit=False)

    def text(self) -> str:
        if self._current_key == "custom":
            return self._custom_edit.text()
        return str(self._preset_values.get(self._current_key, "") or "")

    def apply_theme(self, theme) -> None:
        self._control_height = resolved_control_height(theme, "md")
        self.setMinimumHeight(self._control_height)
        self.setMaximumHeight(self._control_height)
        self._custom_edit.setMinimumHeight(self._control_height)
        self._custom_edit.setMaximumHeight(self._control_height)
        self._custom_edit.setStyleSheet(_caption_text_input_stylesheet(theme))

    def _set_raw_text(self, raw: str, *, emit: bool) -> None:
        raw_text = str(raw or "")
        previous = self.text()
        key = self._value_to_key.get(raw_text, "custom")
        if key == "custom":
            self._custom_raw_text = raw_text
        self._is_syncing = True
        try:
            index = self._mode_combo.findData(key)
            self._mode_combo.setCurrentIndex(max(index, 0))
            self._current_key = key
            self._sync_custom_edit(raw_text)
        finally:
            self._is_syncing = False
        if emit and self.text() != previous:
            self.textChanged.emit(self.text())

    def _sync_custom_edit(self, raw_text: str | None = None) -> None:
        is_custom = self._current_key == "custom"
        if raw_text is None:
            raw_text = self._custom_raw_text if is_custom else self.text()
        blocked = self._custom_edit.blockSignals(True)
        self._custom_edit.setRawText(raw_text)
        self._custom_edit.blockSignals(blocked)
        self._custom_edit.setVisible(is_custom)

    def _on_mode_changed(self) -> None:
        if self._is_syncing:
            return
        previous = self.text()
        key = str(self._mode_combo.currentData() or "custom")
        if self._current_key == "custom":
            self._custom_raw_text = self._custom_edit.text()
        if key == "custom" and not self._custom_raw_text:
            self._custom_raw_text = previous
        self._current_key = key
        self._sync_custom_edit()
        if self.text() != previous:
            self.textChanged.emit(self.text())

    def _on_custom_text_changed(self) -> None:
        if self._is_syncing or self._current_key != "custom":
            return
        self._custom_raw_text = self._custom_edit.text()
        self.textChanged.emit(self.text())


@dataclass(eq=True)
class _CaptionSnapshot:
    caption_config: object
    caption_style: object

    @classmethod
    def from_template(cls, template: TemplateConfig) -> "_CaptionSnapshot":
        return cls(
            caption_config=deepcopy(template.caption),
            caption_style=deepcopy(template.styles.get("caption")),
        )

    def apply_to(self, template: TemplateConfig) -> None:
        template.caption = deepcopy(self.caption_config)
        if self.caption_style is None:
            template.styles.pop("caption", None)
        else:
            template.styles["caption"] = deepcopy(self.caption_style)


class CaptionDetail(QWidget):
    """Editable caption pane backed by TemplateConfig.caption and styles['caption'].""" 

    template_edited = Signal(object)
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._snapshot: _CaptionSnapshot | None = None
        self._is_syncing = False
        self._save_enabled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._summary_card = TemplateSummaryCard("题注", "waves-arrow-down", parent=self)
        layout.addWidget(self._summary_card)

        self._text_card = Card("题注文本", parent=self)
        self._text_card.set_header("题注文本", icon_name="waves-arrow-down")
        self._editor_card = self._text_card
        self._card = self._text_card
        layout.addWidget(self._text_card)

        self._rules_card = Card("编号与生成", parent=self)
        self._rules_card.set_header("编号与生成", icon_name="list-ordered")
        layout.addWidget(self._rules_card)

        self._style_card = Card("题注样式", parent=self)
        self._style_card.set_header("题注样式", icon_name="type-outline")
        layout.addWidget(self._style_card)
        layout.addStretch(1)

        self._build_header()
        self._build_form()

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _build_header(self) -> None:
        header = self._summary_card.header

        self._restore_entry_btn = QPushButton("恢复", header)
        self._restore_entry_btn.setIconSize(QSize(16, 16))
        self._restore_entry_btn.clicked.connect(self._on_restore_entry)
        self._summary_card.add_action(self._restore_entry_btn)

        self._save_btn = QPushButton("保存", header)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._summary_card.add_action(self._save_btn)

        self._summary_grid = self._summary_card.summary_grid

    def _build_form(self) -> None:
        self._build_text_form()
        self._build_rules_form()
        self._build_style_form()

    def _build_text_form(self) -> None:
        self._text_form = InspectorForm(parent=self._text_card)
        self._figure_prefix_edit = QLineEdit(self)
        self._figure_prefix_edit.textChanged.connect(self._on_form_edited)
        self._figure_prefix_row = self._form_row("图题注前缀", self._figure_prefix_edit, parent=self._text_form)

        self._table_prefix_edit = QLineEdit(self)
        self._table_prefix_edit.textChanged.connect(self._on_form_edited)
        self._table_prefix_row = self._form_row("表题注前缀", self._table_prefix_edit, parent=self._text_form)

        self._separator_edit = _CaptionSeparatorInput(self)
        self._separator_edit.textChanged.connect(self._on_form_edited)
        self._separator_row = self._form_row("编号后间隔", self._separator_edit, parent=self._text_form)

        self._placeholder_edit = QLineEdit(self)
        self._placeholder_edit.textChanged.connect(self._on_form_edited)
        self._placeholder_row = self._form_row("缺失题注标题", self._placeholder_edit, parent=self._text_form)

        self._figure_preview_label = QLabel("", self)
        self._figure_preview_label.setObjectName("tpl_caption_preview")
        self._figure_preview_label.setWordWrap(True)
        self._figure_preview_row = self._form_row("图题注示例", self._figure_preview_label, parent=self._text_form)

        self._table_preview_label = QLabel("", self)
        self._table_preview_label.setObjectName("tpl_caption_preview")
        self._table_preview_label.setWordWrap(True)
        self._table_preview_row = self._form_row("表题注示例", self._table_preview_label, parent=self._text_form)

        self._text_grid = self._text_form.add_grid(
            [
                [self._figure_prefix_row, self._table_prefix_row],
                [self._separator_row, self._placeholder_row],
                [self._figure_preview_row],
                [self._table_preview_row],
            ]
        )
        self._text_card.add_widget(self._text_form)

    def _build_rules_form(self) -> None:
        self._rules_form = InspectorForm(parent=self._rules_card)
        self._numbering_mode_combo = StyledComboBox(self)
        for value, label in NUMBERING_MODE_OPTIONS:
            self._numbering_mode_combo.addItem(label, value)
        self._numbering_mode_combo.currentIndexChanged.connect(self._on_form_edited)
        self._numbering_mode_row = self._form_row("编号范围", self._numbering_mode_combo, parent=self._rules_form)

        self._numbering_format_combo = StyledComboBox(self)
        for value, label in NUMBERING_FORMAT_OPTIONS:
            self._numbering_format_combo.addItem(label, value)
        self._numbering_format_combo.currentIndexChanged.connect(self._on_form_edited)
        self._numbering_format_row = self._form_row("显示格式", self._numbering_format_combo, parent=self._rules_form)

        self._auto_insert_combo = StyledComboBox(self)
        for value, label in AUTO_INSERT_OPTIONS:
            self._auto_insert_combo.addItem(label, value)
        self._auto_insert_combo.currentIndexChanged.connect(self._on_form_edited)
        self._auto_insert_row = self._form_row("缺失题注", self._auto_insert_combo, parent=self._rules_form)

        self._numbering_type_combo = StyledComboBox(self)
        for value, label in NUMBERING_TYPE_OPTIONS:
            self._numbering_type_combo.addItem(label, value)
        self._numbering_type_combo.currentIndexChanged.connect(self._on_form_edited)
        self._numbering_type_row = self._form_row("编号类型", self._numbering_type_combo, parent=self._rules_form)

        self._rules_grid = self._rules_form.add_grid(
            [
                [self._numbering_mode_row, self._numbering_format_row],
                [self._auto_insert_row, self._numbering_type_row],
            ]
        )
        self._rules_card.add_widget(self._rules_form)

    def _build_style_form(self) -> None:
        self._style_form = InspectorForm(parent=self._style_card)
        self._font_cn_combo = FontCombo(lang="cn", parent=self)
        self._font_cn_combo.font_changed.connect(self._on_form_edited)
        self._font_cn_row = self._form_row("中文字体", self._font_cn_combo, parent=self._style_form)

        self._font_en_combo = FontCombo(lang="en", parent=self)
        self._font_en_combo.font_changed.connect(self._on_form_edited)
        self._font_en_row = self._form_row("英文字体", self._font_en_combo, parent=self._style_form)

        self._size_combo = SizeCombo(self)
        self._size_combo.size_changed.connect(self._on_form_edited)
        self._size_combo.currentTextChanged.connect(self._on_form_edited)
        self._size_row = self._form_row("字号", self._size_combo, parent=self._style_form)

        self._bold_switch = ToggleSwitch(self, checked=False)
        self._bold_switch.toggled_signal.connect(self._on_form_edited)
        self._italic_switch = ToggleSwitch(self, checked=False)
        self._italic_switch.toggled_signal.connect(self._on_form_edited)
        self._emphasis_row = self._form_row(
            "字形",
            build_emphasis_widget(self, self._bold_switch, self._italic_switch),
            parent=self._style_form,
        )

        self._alignment_combo = StyledComboBox(self)
        for value, label in ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(label, value)
        self._alignment_combo.currentIndexChanged.connect(self._on_form_edited)
        self._alignment_row = self._form_row("题注对齐", self._alignment_combo, parent=self._style_form)

        self._line_type_combo = StyledComboBox(self)
        for value, label in LINE_SPACING_OPTIONS:
            self._line_type_combo.addItem(label, value)
        self._line_type_combo.currentIndexChanged.connect(self._on_line_spacing_type_changed)
        self._line_type_row = self._form_row("行距类型", self._line_type_combo, parent=self._style_form)

        self._line_value_input = SpacingInput(
            unit="pt",
            min_val=0.5,
            max_val=60.0,
            step=0.5,
            decimals=1,
            units=("pt",),
            show_unit=False,
            parent=self,
        )
        self._line_value_input.value_changed.connect(self._on_form_edited)
        self._line_value_suffix = QLabel("磅", self)
        self._line_value_suffix.setObjectName("tpl_style_unit")
        self._line_value_row = self._form_row(
            "行距值",
            self._line_value_input,
            suffix_widget=self._line_value_suffix,
            parent=self._style_form,
        )

        self._space_before_input = SpacingInput(unit="pt", min_val=0.0, max_val=40.0, step=1.0, decimals=1, units=SPACING_UNIT_OPTIONS, show_unit=True, unit_inline=True, parent=self)
        self._space_before_input.value_changed.connect(self._on_form_edited)
        self._space_before_row = self._form_row("段前", self._space_before_input, suffix_widget=QLabel("", self), parent=self._style_form)

        self._space_after_input = SpacingInput(unit="pt", min_val=0.0, max_val=40.0, step=1.0, decimals=1, units=SPACING_UNIT_OPTIONS, show_unit=True, unit_inline=True, parent=self)
        self._space_after_input.value_changed.connect(self._on_form_edited)
        self._space_after_row = self._form_row("段后", self._space_after_input, suffix_widget=QLabel("", self), parent=self._style_form)

        self._style_grid = self._style_form.add_grid(
            [
                [self._font_cn_row, self._size_row],
                [self._font_en_row, self._emphasis_row],
                [self._alignment_row, self._line_type_row],
                [self._line_value_row],
                [self._space_before_row, self._space_after_row],
            ]
        )
        self._style_card.add_widget(self._style_form)

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

    def set_template(self, template: TemplateConfig | None) -> None:
        preserve_snapshot = template is self._current_template and self._snapshot is not None
        self._current_template = template
        if template is None:
            self._snapshot = None
            self._refresh_caption_preview()
            self._refresh_summary()
            self._refresh_action_state()
            return
        if not preserve_snapshot:
            self._snapshot = _CaptionSnapshot.from_template(template)
        self._is_syncing = True
        try:
            caption = template.caption
            style = template.styles.get("caption") or template.styles.get("body") or template.styles.get("normal") or StyleConfig()
            self._figure_prefix_edit.setText(caption.figure_prefix)
            self._table_prefix_edit.setText(caption.table_prefix)
            self._separator_edit.setRawText(caption.separator)
            self._placeholder_edit.setText(caption.placeholder)
            self._set_combo_by_data(self._numbering_mode_combo, caption.numbering_mode)
            self._set_combo_by_data(self._numbering_format_combo, caption.numbering_format)
            self._set_combo_by_data(self._auto_insert_combo, bool(caption.auto_insert))
            self._set_combo_by_data(self._numbering_type_combo, bool(caption.format_inserted))
            self._font_cn_combo.set_font_name(style.font_cn or "")
            self._font_en_combo.set_font_name(style.font_en or "")
            self._size_combo.set_pt(style.size_pt or 12.0)
            self._bold_switch.setChecked(bool(style.bold))
            self._italic_switch.setChecked(bool(style.italic))
            self._set_combo_by_data(self._alignment_combo, style.alignment)
            line_kind = normalize_line_spacing_type(style.line_spacing_type)
            self._set_combo_by_data(self._line_type_combo, line_kind)
            self._sync_line_spacing_editor(
                line_kind,
                resolve_line_spacing_value(line_kind, style.line_spacing_pt),
            )
            self._sync_spacing_input(self._space_before_input, resolve_style_paragraph_spacing(style, "before"))
            self._sync_spacing_input(self._space_after_input, resolve_style_paragraph_spacing(style, "after"))
        finally:
            self._is_syncing = False
        self._refresh_caption_preview()
        self._refresh_summary()
        self._refresh_action_state()

    def _refresh_summary(self) -> None:
        if self._current_template is None:
            self._summary_card.set_summary_items(
                [
                    SummaryGridItem(
                        key="empty",
                        label="当前状态",
                        value="未选择模板。",
                        column_span=12,
                        icon_name="info",
                    )
                ]
            )
            return
        self._summary_card.set_summary_items(
            build_template_detail_summary_items(self._current_template, "tpl_caption")
        )

    def _sync_spacing_input(self, widget: SpacingInput, spacing: dict[str, float | str]) -> None:
        unit = str(spacing["unit"])
        config = spacing_editor_config(unit)
        spin = widget.spin_box
        spin.setRange(float(config["min"]), float(config["max"]))
        spin.setSingleStep(float(config["step"]))
        spin.setDecimals(int(config["decimals"]))
        widget.setEnabled(bool(config["enabled"]))
        widget.set_value(float(spacing["value"]), unit)

    def _sync_line_spacing_editor(self, line_kind: str, value: float) -> None:
        editable = line_spacing_is_editable(line_kind)
        spin = self._line_value_input.spin_box
        if line_kind == "multiple":
            spin.setRange(0.5, 10.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(2)
        else:
            spin.setRange(0.5, 60.0)
            spin.setSingleStep(0.5)
            spin.setDecimals(1)
        self._line_value_suffix.setText(line_spacing_unit_label(line_kind))
        self._line_value_input.setEnabled(editable)
        self._line_value_input.set_value(value, "pt")

    def _caption_number_sample(self) -> str:
        mode = str(self._numbering_mode_combo.currentData() or "chapter")
        fmt = str(self._numbering_format_combo.currentData() or "chapter.seq")
        if mode == "global" or fmt == "seq":
            return "1"
        if fmt == "chapter-seq":
            return "1-1"
        if fmt == "chapter:seq":
            return "1:1"
        return "1.1"

    def _caption_preview_text(self, prefix: str) -> str:
        number = self._caption_number_sample()
        separator = self._separator_edit.text()
        title = self._placeholder_edit.text().strip() or "[待补充]"
        resolved_prefix = prefix.strip()
        return f"{resolved_prefix}{number}{separator}{title}".strip()

    def _refresh_caption_preview(self) -> None:
        if not hasattr(self, "_figure_preview_label"):
            return
        if self._current_template is None:
            self._figure_preview_label.setText("")
            self._table_preview_label.setText("")
            return
        self._figure_preview_label.setText(self._caption_preview_text(self._figure_prefix_edit.text() or "图"))
        self._table_preview_label.setText(self._caption_preview_text(self._table_prefix_edit.text() or "表"))

    def capture_entry_snapshot(self) -> None:
        if self._current_template is None:
            self._snapshot = None
        else:
            self._snapshot = _CaptionSnapshot.from_template(self._current_template)
        self._refresh_action_state()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        caption = self._current_template.caption
        caption.figure_prefix = self._figure_prefix_edit.text()
        caption.table_prefix = self._table_prefix_edit.text()
        caption.separator = self._separator_edit.text()
        caption.placeholder = self._placeholder_edit.text()
        caption.numbering_mode = str(self._numbering_mode_combo.currentData() or "chapter")
        caption.numbering_format = str(self._numbering_format_combo.currentData() or "chapter.seq")
        caption.auto_insert = bool(self._auto_insert_combo.currentData())
        caption.format_inserted = bool(self._numbering_type_combo.currentData())

        if "caption" not in self._current_template.styles:
            self._current_template.styles["caption"] = deepcopy(
                self._current_template.styles.get("body") or self._current_template.styles.get("normal") or StyleConfig()
            )
        style = self._current_template.styles["caption"]
        style.font_cn = self._font_cn_combo.selected_font()
        style.font_en = self._font_en_combo.selected_font()
        pt = self._size_combo.current_pt()
        if pt is not None:
            style.size_pt = pt
            style.size_display = f"{pt:g}"
        style.bold = self._bold_switch.isChecked()
        style.italic = self._italic_switch.isChecked()
        style.alignment = str(self._alignment_combo.currentData() or "center")
        line_kind = normalize_line_spacing_type(self._line_type_combo.currentData() or "exact")
        style.line_spacing_type = line_kind
        style.line_spacing_pt = resolve_line_spacing_value(line_kind, self._line_value_input.value())
        style.space_before_pt = self._space_before_input.value()
        style.space_before_unit = self._space_before_input.unit()
        style.space_after_pt = self._space_after_input.value()
        style.space_after_unit = self._space_after_input.unit()

        self._refresh_caption_preview()
        self._refresh_summary()
        self._refresh_action_state()
        self.template_edited.emit(self._current_template)

    def _on_line_spacing_type_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        line_kind = normalize_line_spacing_type(self._line_type_combo.currentData() or "exact")
        value = resolve_line_spacing_value(line_kind, self._line_value_input.value())
        self._is_syncing = True
        try:
            self._sync_line_spacing_editor(line_kind, value)
        finally:
            self._is_syncing = False
        self._on_form_edited()

    def _on_restore_entry(self) -> None:
        if self._current_template is None or self._snapshot is None:
            return
        self._snapshot.apply_to(self._current_template)
        self.set_template(self._current_template)
        self.template_edited.emit(self._current_template)

    def _refresh_action_state(self) -> None:
        if self._current_template is None:
            self._restore_entry_btn.setEnabled(False)
            self._save_btn.setEnabled(False)
            return
        current = _CaptionSnapshot.from_template(self._current_template)
        self._restore_entry_btn.setEnabled(self._snapshot is not None and current != self._snapshot)
        self._save_btn.setEnabled(self._save_enabled)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(build_button_stylesheet(theme))
        self.layout().setSpacing(theme.template_detail_section_gap)
        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_lg}px; "
                f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; background: transparent;"
            )
        for widget in self.findChildren(QLabel, "tpl_caption_preview"):
            widget.setStyleSheet(f"font-size: {theme.font_size_md}px; color: {theme.text_primary};")

        line_edit_style = _caption_text_input_stylesheet(theme)
        control_height = resolved_control_height(theme, "md")
        for widget in (self._figure_prefix_edit, self._table_prefix_edit, self._placeholder_edit):
            widget.setMinimumHeight(control_height)
            widget.setMaximumHeight(control_height)
            widget.setStyleSheet(line_edit_style)
        self._separator_edit.apply_theme(theme)

        apply_template_summary_action_button(self._restore_entry_btn, "ghost-primary")
        apply_template_summary_action_button(self._save_btn, "primary")

        try:
            from src.ui.icons.catalog import get_icon

            self._summary_card.header.icon_label.setPixmap(
                get_icon("waves-arrow-down", 28, theme.primary).pixmap(28, 28)
            )
            self._restore_entry_btn.setIcon(get_icon("refresh-ccw", 16, theme.primary if self._restore_entry_btn.isEnabled() else theme.text_disabled))
            self._save_btn.setIcon(get_icon("save", 16, theme.text_on_primary if self._save_btn.isEnabled() else theme.text_disabled))
        except Exception:
            self._summary_card.header.icon_label.setText("题")


__all__ = ["CaptionDetail"]
