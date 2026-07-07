"""Table detail pane for template management."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.feature_configs import TABLE_SMART_LEVEL_OPTIONS, normalize_table_smart_levels
from src.config.table_style_presets import (
    TABLE_STYLE_OPTIONS,
    color_palette,
    color_variant,
    table_style_label,
)
from src.config.template import TemplateConfig
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
from src.shared.ui.button_style import build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.layout_sync import (
    refresh_layout_chain,
    reserve_visible_height,
    set_visible_if_changed,
    updates_suspended,
)
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGridItem
from src.shared.ui.table_style_gallery import ColorTableGallery
from src.shared.ui.template_form_layout import (
    TemplateFormGrid,
    TemplateFormStack,
    template_form_row,
)
from src.shared.ui.template_summary_card import (
    TemplateSummaryCard,
    apply_template_summary_action_button,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.typography_controls import build_emphasis_widget
from src.ui.panels.template_summary_projection import build_template_detail_summary_items


TABLE_STYLE_OPTIONS_UI: tuple[tuple[str, str], ...] = tuple(
    (option.key, option.label) for option in TABLE_STYLE_OPTIONS
)
BORDER_OPTIONS = TABLE_STYLE_OPTIONS_UI

LAYOUT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("smart", "智能布局"),
    ("compact", "紧凑布局"),
    ("full", "撑满布局"),
    ("keep", "保留原样"),
)

LINE_SPACING_OPTIONS: tuple[tuple[str, str], ...] = (
    ("single", "单倍"),
    ("one_half", "1.5 倍"),
    ("double", "双倍"),
)

ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("", "不调整"),
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
)

TABLE_ALIGNMENT_OPTIONS = ALIGNMENT_OPTIONS


@dataclass(eq=True)
class _TableSnapshot:
    table_config: object

    @classmethod
    def from_template(cls, template: TemplateConfig) -> "_TableSnapshot":
        return cls(table_config=deepcopy(template.table))

    def apply_to(self, template: TemplateConfig) -> None:
        template.table = deepcopy(self.table_config)


class TableCaptionDetail(QWidget):
    """Editable table pane backed by TemplateConfig.table."""

    template_edited = Signal(object)
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._snapshot: _TableSnapshot | None = None
        self._header_icons: list[tuple[str, QLabel]] = []
        self._header_titles: list[QLabel] = []
        self._unit_labels: list[QLabel] = []
        self._is_syncing = False
        self._save_enabled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._build_summary_card()
        layout.addWidget(self._summary_card)

        self._build_editor_column(self)
        layout.addWidget(self._editor_column)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _build_summary_card(self) -> None:
        self._summary_card = TemplateSummaryCard("表格", "table-2", parent=self)
        header = self._summary_card.header

        self._restore_entry_btn = QPushButton("恢复", header)
        self._restore_entry_btn.setCursor(Qt.PointingHandCursor)
        self._restore_entry_btn.setIconSize(QSize(16, 16))
        self._restore_entry_btn.clicked.connect(self._on_restore_entry)
        self._summary_card.add_action(self._restore_entry_btn)

        self._save_btn = QPushButton("保存", header)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._summary_card.add_action(self._save_btn)

        self._summary_grid = self._summary_card.summary_grid

    def _build_editor_column(self, parent: QWidget) -> None:
        self._editor_column = QWidget(parent)
        self._editor_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QVBoxLayout(self._editor_column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)

        self._border_layout_card = Card(parent=self._editor_column)
        self._add_card_header(
            self._border_layout_card,
            "grid-2x2",
            "边框样式与布局",
        )
        self._build_border_layout_form()
        layout.addWidget(self._border_layout_card)

        self._typography_card = Card(parent=self._editor_column)
        self._add_card_header(
            self._typography_card,
            "type",
            "字体与对齐",
        )
        self._build_typography_form()
        layout.addWidget(self._typography_card)

        self._behavior_card = Card(parent=self._editor_column)
        self._add_card_header(
            self._behavior_card,
            "repeat",
            "输出行为",
        )
        self._build_behavior_form()
        layout.addWidget(self._behavior_card)

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
            desc = QLabel(description, card)
            desc.setWordWrap(True)
            card.add_widget(desc)

    def _build_border_layout_form(self) -> None:
        rows = []

        self._border_combo = StyledComboBox(self)
        for value, label in TABLE_STYLE_OPTIONS_UI:
            self._border_combo.addItem(label, value)
        self._border_combo.currentIndexChanged.connect(self._on_form_edited)
        self._border_row = self._form_row(
            "边框样式",
            self._border_combo,
            parent=self._border_layout_card,
        )

        self._layout_combo = StyledComboBox(self)
        for value, label in LAYOUT_OPTIONS:
            self._layout_combo.addItem(label, value)
        self._layout_combo.currentIndexChanged.connect(self._on_form_edited)
        layout_row = self._form_row(
            "布局",
            self._layout_combo,
            parent=self._border_layout_card,
        )
        rows.append(self._pair_row(self._border_row, layout_row))

        self._smart_levels_combo = StyledComboBox(self)
        for level in TABLE_SMART_LEVEL_OPTIONS:
            self._smart_levels_combo.addItem(f"{level} 级", level)
        self._smart_levels_combo.currentIndexChanged.connect(self._on_form_edited)
        self._smart_levels_row = self._form_row(
            "智能层级",
            self._smart_levels_combo,
            parent=self._border_layout_card,
        )
        rows.append(self._smart_levels_row)

        self._color_gallery = ColorTableGallery(self._border_layout_card)
        self._color_gallery.selection_changed.connect(self._on_color_table_selected)
        rows.append(self._color_gallery)

        self._border_width_input = SpacingInput(unit="pt", min_val=0.1, max_val=6.0, step=0.1, decimals=1, units=("pt",), show_unit=False, parent=self)
        self._border_width_input.value_changed.connect(self._on_form_edited)
        border_width_suffix = QLabel("磅", self)
        self._unit_labels.append(border_width_suffix)
        self._border_width_row = self._form_row(
            "线宽",
            self._border_width_input,
            suffix_widget=border_width_suffix,
            parent=self._border_layout_card,
        )
        rows.append(self._border_width_row)

        self._header_width_input = SpacingInput(unit="pt", min_val=0.1, max_val=6.0, step=0.1, decimals=1, units=("pt",), show_unit=False, parent=self)
        self._header_width_input.value_changed.connect(self._on_form_edited)
        header_width_suffix = QLabel("磅", self)
        self._unit_labels.append(header_width_suffix)
        self._header_width_row = self._form_row(
            "外线宽",
            self._header_width_input,
            suffix_widget=header_width_suffix,
            parent=self._border_layout_card,
        )

        self._bottom_width_input = SpacingInput(unit="pt", min_val=0.1, max_val=6.0, step=0.1, decimals=1, units=("pt",), show_unit=False, parent=self)
        self._bottom_width_input.value_changed.connect(self._on_form_edited)
        bottom_width_suffix = QLabel("磅", self)
        self._unit_labels.append(bottom_width_suffix)
        self._bottom_width_row = self._form_row(
            "表头下线",
            self._bottom_width_input,
            suffix_widget=bottom_width_suffix,
            parent=self._border_layout_card,
        )
        self._three_line_width_pair = self._pair_row(self._header_width_row, self._bottom_width_row)
        rows.append(self._three_line_width_pair)

        self._line_spacing_combo = StyledComboBox(self)
        for value, label in LINE_SPACING_OPTIONS:
            self._line_spacing_combo.addItem(label, value)
        self._line_spacing_combo.currentIndexChanged.connect(self._on_form_edited)
        self._line_spacing_row = self._form_row(
            "表格行距",
            self._line_spacing_combo,
            parent=self._border_layout_card,
        )
        rows.append(self._line_spacing_row)
        self._border_layout_card.add_widget(TemplateFormStack(rows, parent=self._border_layout_card))

    def _build_typography_form(self) -> None:
        self._typography_form = InspectorForm(parent=self._typography_card)

        self._font_cn_combo = FontCombo(lang="cn", parent=self)
        self._font_cn_combo.font_changed.connect(self._on_form_edited)
        font_cn_row = self._form_row("中文字体", self._font_cn_combo, parent=self._typography_form)

        self._font_en_combo = FontCombo(lang="en", parent=self)
        self._font_en_combo.font_changed.connect(self._on_form_edited)
        font_en_row = self._form_row("英文字体", self._font_en_combo, parent=self._typography_form)

        self._size_combo = SizeCombo(self)
        self._size_combo.size_changed.connect(self._on_form_edited)
        self._size_combo.currentTextChanged.connect(self._on_form_edited)
        size_row = self._form_row("字号", self._size_combo, parent=self._typography_form)

        self._bold_toggle = ToggleSwitch(self, checked=False)
        self._bold_toggle.toggled_signal.connect(self._on_form_edited)
        self._italic_toggle = ToggleSwitch(self, checked=False)
        self._italic_toggle.toggled_signal.connect(self._on_form_edited)
        emphasis_row = self._form_row(
            "字形",
            build_emphasis_widget(self, self._bold_toggle, self._italic_toggle),
            parent=self._typography_form,
        )

        self._alignment_combo = StyledComboBox(self)
        for value, label in ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(label, value)
        self._alignment_combo.currentIndexChanged.connect(self._on_form_edited)
        alignment_row = self._form_row("对齐", self._alignment_combo, parent=self._typography_form)
        self._typography_form.add_grid(
            [
                [font_cn_row, size_row],
                [font_en_row, emphasis_row],
                [alignment_row],
            ]
        )
        self._typography_card.add_widget(self._typography_form)

    def _build_behavior_form(self) -> None:
        self._first_row_bold_toggle = ToggleSwitch(self, checked=False)
        self._first_row_bold_toggle.toggled_signal.connect(self._on_form_edited)
        first_row_bold_row = self._form_row("首行加粗", self._first_row_bold_toggle, parent=self._behavior_card)

        self._repeat_header_toggle = ToggleSwitch(self, checked=False)
        self._repeat_header_toggle.toggled_signal.connect(self._on_form_edited)
        repeat_header_row = self._form_row("跨页重复表头", self._repeat_header_toggle, parent=self._behavior_card)

        self._table_alignment_combo = StyledComboBox(self)
        for value, label in TABLE_ALIGNMENT_OPTIONS:
            self._table_alignment_combo.addItem(label, value)
        self._table_alignment_combo.currentIndexChanged.connect(self._on_form_edited)
        self._table_alignment_row = self._form_row("表格对齐", self._table_alignment_combo, parent=self._behavior_card)
        self._behavior_card.add_widget(self._pair_row(first_row_bold_row, repeat_header_row, self._table_alignment_row))

    def _form_row(
        self,
        label: str,
        widget: QWidget,
        *,
        suffix_widget: QWidget | None = None,
        label_width: int | None = None,
        parent,
    ) -> QWidget:
        return template_form_row(
            label,
            widget,
            suffix_widget=suffix_widget,
            label_width=label_width,
            parent=parent,
        )

    def _pair_row(self, *rows: QWidget) -> TemplateFormGrid:
        return TemplateFormGrid([rows], parent=self)

    def _set_explicit_visible_if_changed(self, widget: QWidget, visible: bool) -> bool:
        return set_visible_if_changed(widget, visible)

    def _reserve_visible_height(self, widget: QWidget, height: int | None = None) -> None:
        reserve_visible_height(widget, height)

    def _refresh_layout_chain(self, start: QWidget | None = None) -> None:
        refresh_layout_chain(start or self)

    def _sync_layout_dependent_state(self) -> None:
        with updates_suspended(self._border_layout_card, self._editor_column, self):
            is_smart = str(self._layout_combo.currentData() or "smart") == "smart"
            self._set_explicit_visible_if_changed(self._smart_levels_row, is_smart)
            border_mode = str(self._border_combo.currentData() or "three_line")
            is_color_table = border_mode == "color_table"
            self._set_explicit_visible_if_changed(self._color_gallery, is_color_table)
            self._sync_width_controls_state(border_mode)
            self._refresh_layout_chain(self._border_layout_card)

    def _sync_width_controls_state(self, border_mode: str) -> None:
        color_variant_key = self._color_gallery.selected_variant() if border_mode == "color_table" else ""
        is_color_rule = color_variant(color_variant_key).header_rule_only
        uses_general_width = border_mode == "full_grid" or (border_mode == "color_table" and not is_color_rule)
        uses_three_line_widths = border_mode == "three_line" or (border_mode == "color_table" and is_color_rule)

        self._set_explicit_visible_if_changed(self._border_width_row, uses_general_width)
        if uses_three_line_widths:
            self._set_explicit_visible_if_changed(self._header_width_row, True)
            self._set_explicit_visible_if_changed(self._bottom_width_row, True)
            self._reserve_visible_height(
                self._three_line_width_pair,
                max(self._header_width_row.minimumHeight(), self._bottom_width_row.minimumHeight()),
            )
            self._set_explicit_visible_if_changed(self._three_line_width_pair, True)
        else:
            self._set_explicit_visible_if_changed(self._three_line_width_pair, False)
            self._set_explicit_visible_if_changed(self._header_width_row, False)
            self._set_explicit_visible_if_changed(self._bottom_width_row, False)

        if border_mode == "color_table":
            variant = color_variant(color_variant_key)
            if variant.show_vertical and variant.show_horizontal:
                self._border_width_row.set_label("网格线宽")
            elif variant.show_horizontal:
                self._border_width_row.set_label("横线线宽")
            else:
                self._border_width_row.set_label("线宽")
        elif border_mode == "full_grid":
            self._border_width_row.set_label("网格线宽")
        else:
            self._border_width_row.set_label("线宽")

    def _set_combo_by_data(self, combo: StyledComboBox, target) -> None:
        normalized_target = "" if target is None else target
        for index in range(combo.count()):
            if combo.itemData(index) == normalized_target:
                combo.setCurrentIndex(index)
                return

    def set_template(self, template: TemplateConfig | None) -> None:
        preserve_snapshot = template is self._current_template and self._snapshot is not None
        self._current_template = template
        if template is None:
            self._snapshot = None
            return
        if not preserve_snapshot:
            self._snapshot = _TableSnapshot.from_template(template)
        self._is_syncing = True
        try:
            table = template.table
            table.smart_levels = normalize_table_smart_levels(table.smart_levels)
            self._set_combo_by_data(self._border_combo, table.border_mode)
            self._set_combo_by_data(self._layout_combo, table.layout_mode)
            self._set_combo_by_data(self._table_alignment_combo, getattr(table, "table_alignment", "center"))
            self._set_combo_by_data(self._smart_levels_combo, table.smart_levels)
            self._set_combo_by_data(self._line_spacing_combo, table.line_spacing_mode)
            self._color_gallery.set_selection(
                getattr(table, "color_table_accent", "blue"),
                getattr(table, "color_table_variant", "header_grid"),
            )
            self._border_width_input.set_value(table.border_width_pt, "pt")
            self._header_width_input.set_value(table.three_line_header_width_pt, "pt")
            self._bottom_width_input.set_value(table.three_line_bottom_width_pt, "pt")
            self._font_cn_combo.set_font_name(table.font_cn or "")
            self._font_en_combo.set_font_name(table.font_en or "")
            self._size_combo.set_pt(table.size_pt or 12.0)
            self._bold_toggle.setChecked(bool(getattr(table, "bold", False)))
            self._italic_toggle.setChecked(bool(getattr(table, "italic", False)))
            self._set_combo_by_data(self._alignment_combo, table.cell_alignment)
            self._first_row_bold_toggle.setChecked(bool(getattr(table, "first_row_bold", False)))
            self._repeat_header_toggle.setChecked(table.repeat_header)
        finally:
            self._is_syncing = False
        self._sync_layout_dependent_state()
        self._refresh_summary()
        self._refresh_action_state()

    def capture_entry_snapshot(self) -> None:
        if self._current_template is None:
            self._snapshot = None
        else:
            self._snapshot = _TableSnapshot.from_template(self._current_template)
        self._refresh_action_state()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    def _refresh_summary(self) -> None:
        template = self._current_template
        if template is None:
            self._summary_card.set_summary_items([
                SummaryGridItem(
                    key="empty",
                    label="当前状态",
                    value="未选择模板。",
                    column_span=12,
                    icon_name="info",
                )
            ])
            return
        self._summary_card.set_summary_items(build_template_detail_summary_items(template, "tpl_table"))

    def _behavior_summary_text(self, table) -> str:
        first_row_text = "首行加粗" if bool(getattr(table, "first_row_bold", False)) else "不首行加粗"
        repeat_header_text = "跨页重复表头" if table.repeat_header else "不跨页重复表头"
        table_alignment_label = dict(TABLE_ALIGNMENT_OPTIONS).get(
            getattr(table, "table_alignment", "center") or "",
            "不调整",
        )
        return f"{first_row_text} / {repeat_header_text} / 表格{table_alignment_label}"

    def _emphasis_summary_text(self, table) -> str:
        parts: list[str] = []
        if bool(getattr(table, "bold", False)):
            parts.append("加粗")
        if bool(getattr(table, "italic", False)):
            parts.append("斜体")
        return "、".join(parts) if parts else "常规"

    def _width_summary_text(self, table) -> tuple[str, str]:
        border_mode = str(getattr(table, "border_mode", "") or "three_line")
        if border_mode == "three_line":
            return (
                f"外线 {table.three_line_header_width_pt:g} 磅 / 表头下线 {table.three_line_bottom_width_pt:g} 磅",
                "三线表线宽",
            )
        if border_mode == "full_grid":
            return (
                f"网格线宽 {table.border_width_pt:g} 磅",
                "表头下线不单独调整",
            )
        if border_mode == "color_table":
            variant = color_variant(getattr(table, "color_table_variant", "header_grid"))
            if variant.header_rule_only:
                return (
                    f"外线 {table.three_line_header_width_pt:g} 磅 / 表头下线 {table.three_line_bottom_width_pt:g} 磅",
                    "彩色三线表",
                )
            line_label = "网格线宽" if variant.show_vertical and variant.show_horizontal else "横线线宽"
            return (
                f"{line_label} {table.border_width_pt:g} 磅",
                "颜色表格按所选子样式应用线条",
            )
        if border_mode == "none":
            return "无边框", "线宽参数不生效"
        return "边框保留原样", "线宽参数不生效"

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        table = self._current_template.table
        table.border_mode = str(self._border_combo.currentData() or "three_line")
        table.layout_mode = str(self._layout_combo.currentData() or "smart")
        table.table_alignment = str(self._table_alignment_combo.currentData() or "") or None
        table.smart_levels = normalize_table_smart_levels(self._smart_levels_combo.currentData())
        table.line_spacing_mode = str(self._line_spacing_combo.currentData() or "single")
        table.color_table_accent = self._color_gallery.selected_palette()
        table.color_table_variant = self._color_gallery.selected_variant()
        table.border_width_pt = self._border_width_input.value()
        table.three_line_header_width_pt = self._header_width_input.value()
        table.three_line_bottom_width_pt = self._bottom_width_input.value()
        table.font_cn = self._font_cn_combo.selected_font() or None
        table.font_en = self._font_en_combo.selected_font() or None
        table.size_pt = self._size_combo.current_pt()
        table.bold = self._bold_toggle.isChecked()
        table.italic = self._italic_toggle.isChecked()
        table.cell_alignment = str(self._alignment_combo.currentData() or "") or None
        table.first_row_bold = self._first_row_bold_toggle.isChecked()
        table.repeat_header = self._repeat_header_toggle.isChecked()

        self._sync_layout_dependent_state()
        self._refresh_summary()
        self._refresh_action_state()
        self.template_edited.emit(self._current_template)

    def _on_color_table_selected(self, *_args) -> None:
        if self._is_syncing:
            return
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
        current = _TableSnapshot.from_template(self._current_template)
        self._restore_entry_btn.setEnabled(self._snapshot is not None and current != self._snapshot)
        self._save_btn.setEnabled(self._save_enabled)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(build_button_stylesheet(theme))
        gap = theme.template_detail_section_gap
        self.layout().setSpacing(gap)
        self._editor_column.layout().setSpacing(gap)
        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_lg}px; "
                f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; background: transparent;"
            )
        for label in self._unit_labels:
            label.setStyleSheet(f"font-size: {theme.font_size_md}px; color: {theme.text_secondary};")

        apply_template_summary_action_button(self._restore_entry_btn, "ghost-primary")
        apply_template_summary_action_button(self._save_btn, "primary")

        try:
            from src.ui.icons.catalog import get_icon

            for icon_name, widget in self._header_icons:
                widget.setPixmap(get_icon(icon_name, 18, theme.primary).pixmap(18, 18))
            self._restore_entry_btn.setIcon(
                get_icon("refresh-ccw", 16, theme.primary if self._restore_entry_btn.isEnabled() else theme.text_disabled)
            )
            self._save_btn.setIcon(
                get_icon("save", 16, theme.text_on_primary if self._save_btn.isEnabled() else theme.text_disabled)
            )
        except Exception:
            pass


__all__ = ["TableCaptionDetail"]
