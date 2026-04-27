"""Body-style detail pane for template management."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.style_semantics import (
    LINE_SPACING_OPTIONS,
    apply_style_special_indent,
    display_font_size_with_name,
    format_spacing_value,
    line_spacing_display_label,
    line_spacing_is_editable,
    line_spacing_unit_label,
    normalize_line_spacing_type,
    spacing_editor_config,
    SPACING_UNIT_OPTIONS,
    resolve_line_spacing_value,
    resolve_style_paragraph_spacing,
    resolve_style_special_indent,
)
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.paragraph_style_inputs import IndentInput, SpecialIndentInput
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.typography_controls import build_emphasis_widget

ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
    ("justify", "两端对齐"),
)

ALIGNMENT_LABELS = {value: label for value, label in ALIGNMENT_OPTIONS}

INDENT_UNIT_LABELS = {
    "chars": "字",
    "pt": "磅",
    "cm": "cm",
}


@dataclass(eq=True)
class _StyleSnapshot:
    """Immutable snapshot of editable body-style values for restore operations."""

    body_style: StyleConfig

    @classmethod
    def from_template(cls, template: TemplateConfig) -> _StyleSnapshot:
        body = template.styles.get("body")
        if body is None:
            normal = template.styles.get("normal")
            body = deepcopy(normal) if normal is not None else StyleConfig()
        return cls(body_style=deepcopy(body))

    def apply_to(self, template: TemplateConfig) -> None:
        template.styles["body"] = deepcopy(self.body_style)


def _set_combo_by_data(combo: StyledComboBox, target) -> None:
    normalized_target = "" if target in (None, "") else str(target)
    for index in range(combo.count()):
        current = combo.itemData(index)
        normalized_current = "" if current in (None, "") else str(current)
        if normalized_current == normalized_target:
            combo.setCurrentIndex(index)
            return


def _size_text(style: StyleConfig) -> str:
    if style.size_display:
        return style.size_display
    if style.size_pt:
        return f"{style.size_pt:g}磅"
    return "未设置字号"


def _emphasis_text(style: StyleConfig) -> str:
    states: list[str] = []
    if style.bold:
        states.append("加粗")
    if style.italic:
        states.append("斜体")
    return " / ".join(states) if states else "常规"


def _indent_value_text(value: float, unit: str) -> str:
    return f"{float(value):g}{INDENT_UNIT_LABELS.get(str(unit), str(unit))}"


def _special_indent_text(style: StyleConfig) -> str:
    special = resolve_style_special_indent(style)
    if special["mode"] == "first_line" and float(special["value"]) > 0:
        return f"首行 {_indent_value_text(float(special['value']), str(special['unit']))}"
    if special["mode"] == "hanging" and float(special["value"]) > 0:
        return f"悬挂 {_indent_value_text(float(special['value']), str(special['unit']))}"
    return "无特殊缩进"


def _line_spacing_text(style: StyleConfig) -> str:
    line_kind = normalize_line_spacing_type(style.line_spacing_type)
    value = resolve_line_spacing_value(line_kind, style.line_spacing_pt)
    label = line_spacing_display_label(line_kind)
    if line_kind == "exact":
        return f"{label} {value:g} 磅"
    if line_kind == "multiple":
        return f"{label} {value:g} 倍"
    return label


class StyleDetail(QWidget):
    """Editable body-style pane backed by ``TemplateConfig.styles['body']``."""

    template_edited = Signal(object)
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._snapshot: _StyleSnapshot | None = None
        self._header_icons: list[tuple[str, QLabel]] = []
        self._header_titles: list[QLabel] = []
        self._desc_labels: list[QLabel] = []
        self._unit_labels: list[QLabel] = []
        self._is_syncing = False
        self._save_enabled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._build_summary_card()
        layout.addWidget(self._summary_card)

        self._build_editor_column(self)
        layout.addWidget(self._editor_column)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def _build_summary_card(self) -> None:
        self._summary_card = Card(parent=self)
        header = QWidget(self._summary_card)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(6)

        icon_label = QLabel(header)
        icon_label.setFixedSize(18, 18)
        self._header_icons.append(("type-outline", icon_label))
        layout.addWidget(icon_label)

        title_label = QLabel("正文排版", header)
        title_label.setObjectName("tpl_card_title")
        self._header_titles.append(title_label)
        layout.addWidget(title_label)
        layout.addStretch(1)

        self._restore_entry_btn = QPushButton("恢复", header)
        self._restore_entry_btn.setCursor(Qt.PointingHandCursor)
        self._restore_entry_btn.setIconSize(QSize(16, 16))
        self._restore_entry_btn.clicked.connect(self._on_restore_entry)
        layout.addWidget(self._restore_entry_btn)

        self._save_btn = QPushButton("保存", header)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        layout.addWidget(self._save_btn)

        self._summary_card.add_widget(header)

        self._summary_grid = SummaryGrid(columns=6, parent=self._summary_card)
        self._summary_card.add_widget(self._summary_grid)

    def _build_editor_column(self, parent: QWidget) -> None:
        self._editor_column = QWidget(parent)
        self._editor_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QVBoxLayout(self._editor_column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._text_card = Card(parent=self._editor_column)
        self._add_card_header(
            self._text_card,
            "whole-word",
            "文字样式",
        )
        self._build_text_card()
        layout.addWidget(self._text_card)

        self._alignment_indent_card = Card(parent=self._editor_column)
        self._add_card_header(
            self._alignment_indent_card,
            "layers",
            "对齐与缩进",
        )
        self._build_alignment_indent_card()
        layout.addWidget(self._alignment_indent_card)

        self._spacing_card = Card(parent=self._editor_column)
        self._add_card_header(
            self._spacing_card,
            "sliders-horizontal",
            "行距与段距",
        )
        self._build_spacing_card()
        layout.addWidget(self._spacing_card)
        layout.addStretch(1)

    def _add_card_header(
        self,
        card: Card,
        icon_name: str,
        title: str,
        description: str | None = None,
    ) -> None:
        header = QWidget(card)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(6)

        icon_label = QLabel(header)
        icon_label.setFixedSize(18, 18)
        self._header_icons.append((icon_name, icon_label))
        layout.addWidget(icon_label)

        title_label = QLabel(title, header)
        title_label.setObjectName("tpl_card_title")
        self._header_titles.append(title_label)
        layout.addWidget(title_label)
        layout.addStretch(1)
        card.add_widget(header)

        if description:
            desc_label = QLabel(description, card)
            desc_label.setWordWrap(True)
            self._desc_labels.append(desc_label)
            card.add_widget(desc_label)

    def _build_form_row(
        self,
        label: str,
        widget: QWidget,
        *,
        parent,
        label_width: int | None = None,
        suffix_widget: QWidget | None = None,
    ) -> QWidget:
        return template_form_row(
            label,
            widget,
            suffix_widget=suffix_widget,
            label_width=label_width,
            parent=parent,
        )

    def _build_text_card(self) -> None:
        self._font_cn = FontCombo(lang="cn", parent=self)
        self._font_cn.font_changed.connect(self._on_form_edited)

        self._font_en = FontCombo(lang="en", parent=self)
        self._font_en.font_changed.connect(self._on_form_edited)

        self._size_combo = SizeCombo(self)
        self._size_combo.size_changed.connect(self._on_form_edited)
        self._size_combo.currentTextChanged.connect(self._on_form_edited)

        self._bold_switch = ToggleSwitch(self, checked=False)
        self._bold_switch.toggled_signal.connect(self._on_form_edited)

        self._italic_switch = ToggleSwitch(self, checked=False)
        self._italic_switch.toggled_signal.connect(self._on_form_edited)

        self._text_form = InspectorForm(parent=self._text_card)
        font_cn_row = self._build_form_row("中文字体", self._font_cn, parent=self._text_form)
        font_en_row = self._build_form_row("英文字体", self._font_en, parent=self._text_form)
        size_row = self._build_form_row("字号", self._size_combo, parent=self._text_form)
        emphasis_row = self._build_form_row(
            "字形",
            self._build_emphasis_widget(),
            parent=self._text_form,
        )
        self._text_form.add_grid(
            [
                [font_cn_row, size_row],
                [font_en_row, emphasis_row],
            ]
        )
        self._text_card.add_widget(self._text_form)

    def _build_alignment_indent_card(self) -> None:
        self._alignment_combo = StyledComboBox(self)
        self._alignment_combo.setSizeAdjustPolicy(self._alignment_combo.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        for value, label in ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(label, value)
        self._alignment_combo.currentIndexChanged.connect(self._on_form_edited)
        self._alignment_combo.setToolTip("正文对齐方式。论文正文通常使用两端对齐。")

        self._special_indent = SpecialIndentInput(self, reference_size_pt=12.0)
        self._special_indent.value_changed.connect(self._on_form_edited)

        self._left_indent = IndentInput(self, reference_size_pt=12.0)
        self._left_indent.value_changed.connect(self._on_form_edited)

        self._right_indent = IndentInput(self, reference_size_pt=12.0)
        self._right_indent.value_changed.connect(self._on_form_edited)

        self._alignment_indent_form = InspectorForm(parent=self._alignment_indent_card)
        alignment_row = self._build_form_row(
            "对齐",
            self._alignment_combo,
            parent=self._alignment_indent_form,
        )
        special_indent_row = self._build_form_row(
            "特殊缩进",
            self._special_indent,
            parent=self._alignment_indent_form,
        )
        left_indent_row = self._build_form_row(
            "左缩进",
            self._left_indent,
            parent=self._alignment_indent_form,
        )
        right_indent_row = self._build_form_row(
            "右缩进",
            self._right_indent,
            parent=self._alignment_indent_form,
        )
        self._alignment_indent_form.add_grid(
            [
                [alignment_row, special_indent_row],
                [left_indent_row, right_indent_row],
            ]
        )
        self._alignment_indent_card.add_widget(self._alignment_indent_form)

    def _build_spacing_card(self) -> None:
        self._line_type_combo = StyledComboBox(self)
        self._line_type_combo.setSizeAdjustPolicy(self._line_type_combo.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        for value, label in LINE_SPACING_OPTIONS:
            self._line_type_combo.addItem(label, value)
        self._line_type_combo.currentIndexChanged.connect(self._on_line_spacing_type_changed)
        self._line_type_combo.setToolTip("支持固定值、单倍、1.5 倍、双倍和多倍行距。")

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
        self._line_value_suffix = QLabel("磅", self)
        self._line_value_suffix.setObjectName("tpl_style_unit")
        self._unit_labels.append(self._line_value_suffix)

        self._space_before = SpacingInput(
            unit="pt",
            min_val=0.0,
            max_val=80.0,
            step=1.0,
            decimals=1,
            units=SPACING_UNIT_OPTIONS,
            show_unit=True,
            unit_inline=True,
            parent=self,
        )
        self._space_before.value_changed.connect(self._on_form_edited)
        self._space_before_suffix = QLabel("", self)
        self._space_before_suffix.setObjectName("tpl_style_unit")
        self._unit_labels.append(self._space_before_suffix)

        self._space_after = SpacingInput(
            unit="pt",
            min_val=0.0,
            max_val=80.0,
            step=1.0,
            decimals=1,
            units=SPACING_UNIT_OPTIONS,
            show_unit=True,
            unit_inline=True,
            parent=self,
        )
        self._space_after.value_changed.connect(self._on_form_edited)
        self._space_after_suffix = QLabel("", self)
        self._space_after_suffix.setObjectName("tpl_style_unit")
        self._unit_labels.append(self._space_after_suffix)

        self._spacing_form = InspectorForm(parent=self._spacing_card)
        line_type_row = self._build_form_row(
            "行距类型",
            self._line_type_combo,
            parent=self._spacing_form,
        )
        line_value_row = self._build_form_row(
            "行距值",
            self._line_value,
            suffix_widget=self._line_value_suffix,
            parent=self._spacing_form,
        )
        space_before_row = self._build_form_row(
            "段前",
            self._space_before,
            suffix_widget=self._space_before_suffix,
            parent=self._spacing_form,
        )
        space_after_row = self._build_form_row(
            "段后",
            self._space_after,
            suffix_widget=self._space_after_suffix,
            parent=self._spacing_form,
        )
        self._spacing_form.add_grid(
            [
                [line_type_row, line_value_row],
                [space_before_row, space_after_row],
            ]
        )
        self._spacing_card.add_widget(self._spacing_form)

    def _build_emphasis_widget(self) -> QWidget:
        return build_emphasis_widget(self, self._bold_switch, self._italic_switch, spacing=10)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_template(self, template: TemplateConfig | None) -> None:
        preserve_snapshot = template is self._current_template and self._snapshot is not None
        self._current_template = template
        if template is None:
            self._snapshot = None
        elif not preserve_snapshot:
            self._snapshot = _StyleSnapshot.from_template(template)
        self._sync_from_template()
        self._refresh_view_state()

    def capture_entry_snapshot(self) -> None:
        if self._current_template is None:
            self._snapshot = None
        else:
            self._snapshot = _StyleSnapshot.from_template(self._current_template)
        self._refresh_action_state()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    def apply_theme(self) -> None:
        self._apply_theme()

    # ------------------------------------------------------------------
    # Internal sync
    # ------------------------------------------------------------------

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

    def _sync_from_template(self) -> None:
        style = self._editable_style()
        if style is None:
            self._refresh_summary()
            self._refresh_action_state()
            return

        self._is_syncing = True
        try:
            self._font_cn.set_font_name(style.font_cn)
            self._font_en.set_font_name(style.font_en)
            self._size_combo.set_pt(style.size_pt)
            self._bold_switch.setChecked(style.bold)
            self._italic_switch.setChecked(style.italic)
            _set_combo_by_data(self._alignment_combo, style.alignment)

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
            _set_combo_by_data(self._line_type_combo, line_kind)
            self._sync_line_spacing_editor(
                line_kind,
                resolve_line_spacing_value(line_kind, style.line_spacing_pt),
            )

            before = resolve_style_paragraph_spacing(style, "before")
            after = resolve_style_paragraph_spacing(style, "after")
            self._sync_spacing_editor(self._space_before, self._space_before_suffix, before)
            self._sync_spacing_editor(self._space_after, self._space_after_suffix, after)
        finally:
            self._is_syncing = False

    def _sync_spacing_editor(self, input_widget: SpacingInput, suffix: QLabel, spacing: dict[str, float | str]) -> None:
        unit = str(spacing["unit"])
        config = spacing_editor_config(unit)
        spin = input_widget.spin_box
        spin.setRange(float(config["min"]), float(config["max"]))
        spin.setSingleStep(float(config["step"]))
        spin.setDecimals(int(config["decimals"]))
        input_widget.setEnabled(bool(config["enabled"]))
        input_widget.set_value(float(spacing["value"]), unit)
        suffix.setText("")

    def _sync_line_spacing_editor(self, line_kind: str, value: float) -> None:
        editable = line_spacing_is_editable(line_kind)
        spin = self._line_value.spin_box
        if line_kind == "exact":
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
        style.space_before_unit = self._space_before.unit()
        style.space_after_pt = self._space_after.value()
        style.space_after_unit = self._space_after.unit()

        self._refresh_view_state()
        self.template_edited.emit(self._current_template)

    def _on_restore_entry(self) -> None:
        if self._current_template is None or self._snapshot is None:
            return
        self._snapshot.apply_to(self._current_template)
        self._sync_from_template()
        self._refresh_view_state()
        self.template_edited.emit(self._current_template)

    # ------------------------------------------------------------------
    # Derived UI state
    # ------------------------------------------------------------------

    def _refresh_view_state(self) -> None:
        self._refresh_summary()
        self._refresh_action_state()

    def _refresh_summary(self) -> None:
        style = self._editable_style()
        if style is None:
            self._summary_grid.set_items(
                [
                    SummaryGridItem(
                        key="empty",
                        label="当前状态",
                        value="未选择模板。",
                        detail="选择模板后，这里会汇总字体、缩进和行距等正文排版信息。",
                        column_span=6,
                    ),
                ]
            )
            return

        self._summary_grid.set_items(
            [
                SummaryGridItem(
                    key="text",
                    label="文字样式",
                    value=f"{style.font_cn or '-'} / {style.font_en or '-'}",
                    detail=f"字号 {_size_text(style)}  字形 {_emphasis_text(style)}",
                    detail_emphasis=True,
                    column_span=2,
                ),
                SummaryGridItem(
                    key="paragraph",
                    label="对齐与缩进",
                    value=f"{ALIGNMENT_LABELS.get(style.alignment, str(style.alignment or '未设置对齐'))}  {_special_indent_text(style)}",
                    detail=(
                        f"左缩进 {_indent_value_text(style.left_indent_chars, style.left_indent_unit)}  "
                        f"右缩进 {_indent_value_text(style.right_indent_chars, style.right_indent_unit)}"
                    ),
                    detail_emphasis=True,
                    column_span=2,
                ),
                SummaryGridItem(
                    key="spacing",
                    label="行距与段距",
                    value=_line_spacing_text(style),
                    detail=(
                        f"段前 {format_spacing_value(style.space_before_pt, getattr(style, 'space_before_unit', 'pt'))}  "
                        f"段后 {format_spacing_value(style.space_after_pt, getattr(style, 'space_after_unit', 'pt'))}"
                    ),
                    detail_emphasis=True,
                    column_span=2,
                ),
            ]
        )

    def _refresh_action_state(self) -> None:
        template = self._current_template
        if template is None:
            self._restore_entry_btn.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._refresh_action_icons()
            return

        current = _StyleSnapshot.from_template(template)
        self._restore_entry_btn.setEnabled(self._snapshot is not None and current != self._snapshot)
        self._save_btn.setEnabled(self._save_enabled)
        self._refresh_action_icons()

    def _refresh_action_icons(self) -> None:
        try:
            from src.ui.icons.catalog import get_icon
        except Exception:
            return

        theme = get_theme()
        restore_color = theme.primary if self._restore_entry_btn.isEnabled() else theme.text_disabled
        save_color = theme.text_on_primary if self._save_btn.isEnabled() else theme.text_disabled
        self._restore_entry_btn.setIcon(get_icon("refresh-ccw", 16, restore_color))
        self._save_btn.setIcon(get_icon("save", 16, save_color))

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(build_button_stylesheet(theme))

        title_ss = (
            f"font-size: {theme.font_size_lg}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.primary}; background: transparent;"
        )
        desc_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
        unit_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"

        for label in self._header_titles:
            label.setStyleSheet(title_ss)
        for label in self._desc_labels:
            label.setStyleSheet(desc_ss)
        for label in self._unit_labels:
            label.setStyleSheet(unit_ss)

        apply_button_variant(self._restore_entry_btn, "ghost-primary")
        apply_button_variant(self._save_btn, "primary")

        try:
            from src.ui.icons.catalog import get_icon

            for icon_name, label in self._header_icons:
                label.setPixmap(get_icon(icon_name, 18, theme.primary).pixmap(18, 18))
        except Exception:
            pass

        self._refresh_view_state()


__all__ = ["StyleDetail"]
