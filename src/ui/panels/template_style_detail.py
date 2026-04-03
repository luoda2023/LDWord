"""Style detail pane for template management."""

from __future__ import annotations

from copy import deepcopy

from src.config.style_semantics import (
    LINE_SPACING_OPTIONS,
    apply_style_special_indent,
    display_font_size_with_name,
    line_spacing_is_editable,
    line_spacing_unit_label,
    normalize_line_spacing_type,
    resolve_style_special_indent,
    resolve_line_spacing_value,
)
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy, Signal
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.form_row import FormRow
from src.shared.ui.paragraph_style_inputs import IndentInput, SpecialIndentInput
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch


_ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
    ("justify", "两端对齐"),
)


class StyleDetail(QWidget):
    """Editable body-style pane backed by TemplateConfig.styles['body']."""

    template_edited = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._is_syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._card = Card(parent=self)
        layout.addWidget(self._card)
        layout.addStretch(1)

        self._build_header()
        self._build_form()
        self._build_hint()

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _build_header(self) -> None:
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 4)
        header_layout.setSpacing(6)
        self._header_icon = QLabel(header)
        self._header_icon.setFixedSize(18, 18)
        header_layout.addWidget(self._header_icon)
        title = QLabel("排版样式", header)
        title.setObjectName("tpl_card_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self._card.add_widget(header)

        self._desc = QLabel("编辑正文默认字体、字号、对齐、缩进和段落间距。")
        self._desc.setObjectName("tpl_style_desc")
        self._desc.setWordWrap(True)
        self._card.add_widget(self._desc)

    def _build_form(self) -> None:
        self._font_cn = FontCombo(lang="cn", parent=self)
        self._font_cn.font_changed.connect(self._on_form_edited)
        self._card.add_widget(FormRow("中文字体", self._font_cn, parent=self._card))

        self._font_en = FontCombo(lang="en", parent=self)
        self._font_en.font_changed.connect(self._on_form_edited)
        self._card.add_widget(FormRow("英文字体", self._font_en, parent=self._card))

        self._size_combo = SizeCombo(self)
        self._size_combo.size_changed.connect(self._on_form_edited)
        self._size_combo.currentTextChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("字号", self._size_combo, parent=self._card))

        self._bold_switch = ToggleSwitch(self, checked=False)
        self._bold_switch.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("加粗", self._bold_switch, parent=self._card))

        self._italic_switch = ToggleSwitch(self, checked=False)
        self._italic_switch.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("斜体", self._italic_switch, parent=self._card))

        self._alignment_combo = StyledComboBox(self)
        for value, label in _ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(label, value)
        self._alignment_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("对齐", self._alignment_combo, parent=self._card))

        self._special_indent = SpecialIndentInput(self, reference_size_pt=12.0)
        self._special_indent.value_changed.connect(self._on_form_edited)
        self._card.add_widget(
            FormRow("特殊缩进", self._special_indent, parent=self._card)
        )

        self._left_indent = IndentInput(self, reference_size_pt=12.0)
        self._left_indent.value_changed.connect(self._on_form_edited)
        self._card.add_widget(FormRow("左缩进", self._left_indent, parent=self._card))

        self._right_indent = IndentInput(self, reference_size_pt=12.0)
        self._right_indent.value_changed.connect(self._on_form_edited)
        self._card.add_widget(FormRow("右缩进", self._right_indent, parent=self._card))

        self._line_type_combo = StyledComboBox(self)
        for value, label in LINE_SPACING_OPTIONS:
            self._line_type_combo.addItem(label, value)
        self._line_type_combo.currentIndexChanged.connect(self._on_line_spacing_type_changed)
        self._card.add_widget(FormRow("行距类型", self._line_type_combo, parent=self._card))

        self._line_value = SpacingInput(
            unit="pt",
            min_val=0.5,
            max_val=60.0,
            step=0.5,
            decimals=1,
            units=("pt",),
            show_unit=False,
            parent=self,
        )
        self._line_value.value_changed.connect(self._on_form_edited)
        self._line_value_suffix = QLabel("pt", self)
        self._line_value_suffix.setObjectName("tpl_style_unit")
        self._card.add_widget(
            FormRow("行距值", self._line_value, suffix_widget=self._line_value_suffix, parent=self._card)
        )

        self._space_before = SpacingInput(
            unit="pt",
            min_val=0.0,
            max_val=80.0,
            step=1.0,
            decimals=1,
            units=("pt",),
            show_unit=False,
            parent=self,
        )
        self._space_before.value_changed.connect(self._on_form_edited)
        before_suffix = QLabel("pt", self)
        before_suffix.setObjectName("tpl_style_unit")
        self._card.add_widget(
            FormRow("段前", self._space_before, suffix_widget=before_suffix, parent=self._card)
        )

        self._space_after = SpacingInput(
            unit="pt",
            min_val=0.0,
            max_val=80.0,
            step=1.0,
            decimals=1,
            units=("pt",),
            show_unit=False,
            parent=self,
        )
        self._space_after.value_changed.connect(self._on_form_edited)
        after_suffix = QLabel("pt", self)
        after_suffix.setObjectName("tpl_style_unit")
        self._card.add_widget(
            FormRow("段后", self._space_after, suffix_widget=after_suffix, parent=self._card)
        )

    def _build_hint(self) -> None:
        self._footer_note = QLabel("当前版本优先覆盖正文主样式参数，标题细分样式沿用现有编号面板。")
        self._footer_note.setObjectName("tpl_style_footer")
        self._footer_note.setWordWrap(True)
        self._card.add_widget(self._footer_note)

    def _sync_line_spacing_editor(self, line_kind: str, value: float) -> None:
        editable = line_spacing_is_editable(line_kind)
        is_exact = line_kind == "exact"
        spin = self._line_value.spin_box
        if is_exact:
            spin.setRange(1.0, 80.0)
            spin.setSingleStep(1.0)
            spin.setDecimals(1)
        else:
            spin.setRange(0.5, 5.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(1)

        self._line_value_suffix.setText(line_spacing_unit_label(line_kind))
        self._line_value.setEnabled(editable)
        self._line_value.set_value(value, "pt")

    def _editable_style(self) -> StyleConfig | None:
        if self._current_template is None:
            return None
        styles = self._current_template.styles
        body = styles.get("body")
        if body is not None:
            return body
        normal = styles.get("normal")
        if normal is not None:
            styles["body"] = deepcopy(normal)
        else:
            styles["body"] = StyleConfig()
        return styles["body"]

    def _set_combo_by_data(self, combo: StyledComboBox, target) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == target:
                combo.setCurrentIndex(index)
                return

    def set_template(self, template: TemplateConfig | None) -> None:
        self._current_template = template
        style = self._editable_style()
        if style is None:
            return

        self._is_syncing = True
        try:
            self._font_cn.set_font_name(style.font_cn)
            self._font_en.set_font_name(style.font_en)
            self._size_combo.set_pt(style.size_pt)
            self._bold_switch.setChecked(style.bold)
            self._italic_switch.setChecked(style.italic)
            self._set_combo_by_data(self._alignment_combo, style.alignment)

            self._special_indent.set_reference_size(style.size_pt)
            self._left_indent.set_reference_size(style.size_pt)
            self._right_indent.set_reference_size(style.size_pt)

            special = resolve_style_special_indent(style)
            self._special_indent.set_value(
                str(special["mode"]),
                float(special["value"]),
                str(special["unit"]),
            )
            self._left_indent.set_value(style.left_indent_chars, style.left_indent_unit)
            self._right_indent.set_value(style.right_indent_chars, style.right_indent_unit)

            line_kind = normalize_line_spacing_type(style.line_spacing_type)
            self._set_combo_by_data(self._line_type_combo, line_kind)
            self._sync_line_spacing_editor(
                line_kind,
                resolve_line_spacing_value(line_kind, style.line_spacing_pt),
            )

            self._space_before.set_value(style.space_before_pt, "pt")
            self._space_after.set_value(style.space_after_pt, "pt")
        finally:
            self._is_syncing = False

    def _on_line_spacing_type_changed(self, *_args) -> None:
        if self._is_syncing:
            return

        line_kind = normalize_line_spacing_type(self._line_type_combo.currentData() or "exact")
        value = resolve_line_spacing_value(line_kind, self._line_value.value())

        self._is_syncing = True
        try:
            self._sync_line_spacing_editor(line_kind, value)
        finally:
            self._is_syncing = False

        self._on_form_edited()

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing:
            return

        style = self._editable_style()
        if style is None:
            return

        style.font_cn = self._font_cn.selected_font()
        style.font_en = self._font_en.selected_font()

        pt = self._size_combo.current_pt()
        if pt is not None:
            style.size_pt = pt
            style.size_display = display_font_size_with_name(pt)
            self._special_indent.set_reference_size(pt)
            self._left_indent.set_reference_size(pt)
            self._right_indent.set_reference_size(pt)

        style.bold = self._bold_switch.isChecked()
        style.italic = self._italic_switch.isChecked()
        style.alignment = str(self._alignment_combo.currentData() or "justify")

        apply_style_special_indent(
            style,
            self._special_indent.mode(),
            self._special_indent.value(),
            self._special_indent.unit(),
        )
        style.left_indent_chars = self._left_indent.value()
        style.left_indent_unit = self._left_indent.unit()
        style.right_indent_chars = self._right_indent.value()
        style.right_indent_unit = self._right_indent.unit()

        line_kind = normalize_line_spacing_type(self._line_type_combo.currentData() or "exact")
        style.line_spacing_type = line_kind
        style.line_spacing_pt = resolve_line_spacing_value(line_kind, self._line_value.value())
        style.space_before_pt = self._space_before.value()
        style.space_after_pt = self._space_after.value()

        self.template_edited.emit(self._current_template)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_md}px; font-weight: {theme.font_weight_bold}; color: {theme.primary};"
            )
        self._desc.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
        self._footer_note.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")
        for widget in self.findChildren(QLabel, "tpl_style_unit"):
            widget.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")

        try:
            from src.ui.icons.catalog import get_icon

            self._header_icon.setPixmap(get_icon("type-outline", 16, theme.primary).pixmap(16, 16))
        except Exception:
            self._header_icon.setText("字")


__all__ = ["StyleDetail"]
