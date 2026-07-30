"""Formula detail pane for template management."""

from __future__ import annotations

from copy import deepcopy

from src.config.template import TemplateConfig
from src.qt_api import QLabel, QPushButton, QSize, QVBoxLayout, QWidget, QSizePolicy, Signal
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.template_summary_card import (
    TemplateSummaryCard,
    apply_template_summary_action_button,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.panels.template_summary_projection import build_template_detail_summary_items


_ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
)

_NUMBERING_OPTIONS: tuple[tuple[str, str], ...] = (
    ("chapter.seq", "章.序"),
    ("chapter-seq", "章-序"),
    ("chapter:seq", "章:序"),
    ("chapter/seq", "章/序"),
    ("chapter_seq", "章_序"),
    ("chapterseq", "章序"),
    ("chapter—seq", "章—序"),
    ("chapter–seq", "章–序"),
    ("global", "全局序号"),
)


class FormulaDetail(QWidget):
    """Editable formula pane backed by TemplateConfig formula fields."""

    template_edited = Signal(object)
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._is_syncing = False
        self._save_enabled = False
        self._snapshot = None
        self._custom_numbering_value: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._summary_card = TemplateSummaryCard("公式", "sigma", parent=self)
        self._header_card = self._summary_card
        self._restore_btn = QPushButton("恢复", self._summary_card.header)
        self._restore_btn.setIconSize(QSize(16, 16))
        self._restore_btn.clicked.connect(self._on_restore_entry)
        self._summary_card.add_action(self._restore_btn)
        self._save_btn = QPushButton("保存", self._summary_card.header)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._summary_card.add_action(self._save_btn)
        layout.addWidget(self._summary_card)

        self._card = Card(parent=self)
        self._card.set_header("公式排版参数", icon_name="sigma")
        layout.addWidget(self._card)
        layout.addStretch(1)

        self._build_header()
        self._build_form()
        self._build_hint()

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _build_header(self) -> None:
        self._desc = QLabel("编辑公式字体、字号、编号方式和统一样式选项。")
        self._desc.setObjectName("tpl_formula_desc")
        self._desc.setWordWrap(True)
        self._card.add_widget(self._desc)

    def _build_form(self) -> None:
        rows = []

        self._font_combo = FontCombo(lang="en", parent=self)
        self._font_combo.font_changed.connect(self._on_form_edited)
        rows.append(template_form_row("公式字体", self._font_combo, parent=self._card))

        self._size_combo = SizeCombo(self)
        self._size_combo.size_changed.connect(self._on_form_edited)
        self._size_combo.currentTextChanged.connect(self._on_form_edited)
        rows.append(template_form_row("公式字号", self._size_combo, parent=self._card))

        self._alignment_combo = StyledComboBox(self)
        for value, label in _ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(label, value)
        self._alignment_combo.currentIndexChanged.connect(self._on_form_edited)
        rows.append(template_form_row("块对齐", self._alignment_combo, parent=self._card))

        self._table_alignment_combo = StyledComboBox(self)
        self._formula_cell_alignment_combo = StyledComboBox(self)
        self._number_alignment_combo = StyledComboBox(self)
        for combo in (
            self._table_alignment_combo,
            self._formula_cell_alignment_combo,
            self._number_alignment_combo,
        ):
            for value, label in _ALIGNMENT_OPTIONS:
                combo.addItem(label, value)
            combo.currentIndexChanged.connect(self._on_form_edited)
        rows.append(template_form_row("公式表对齐", self._table_alignment_combo, parent=self._card))
        rows.append(template_form_row("公式单元格", self._formula_cell_alignment_combo, parent=self._card))
        rows.append(template_form_row("编号对齐", self._number_alignment_combo, parent=self._card))

        self._numbering_combo = StyledComboBox(self)
        for value, label in _NUMBERING_OPTIONS:
            self._numbering_combo.addItem(label, value)
        self._numbering_combo.currentIndexChanged.connect(self._on_form_edited)
        rows.append(template_form_row("编号方式", self._numbering_combo, parent=self._card))

        self._number_font_combo = FontCombo(lang="en", parent=self)
        self._number_font_combo.font_changed.connect(self._on_form_edited)
        rows.append(template_form_row("编号字体", self._number_font_combo, parent=self._card))

        self._number_size_combo = SizeCombo(self)
        self._number_size_combo.size_changed.connect(self._on_form_edited)
        self._number_size_combo.currentTextChanged.connect(self._on_form_edited)
        rows.append(template_form_row("编号字号", self._number_size_combo, parent=self._card))

        self._line_spacing = SpacingInput(
            unit="multiple", min_val=0.5, max_val=4.0, step=0.1,
            decimals=2, units=(("multiple", "倍"),), show_unit=True,
            unit_inline=True, parent=self,
        )
        self._line_spacing.value_changed.connect(self._on_form_edited)
        rows.append(template_form_row("公式行距", self._line_spacing, parent=self._card))

        self._space_before = SpacingInput(
            unit="pt", min_val=0.0, max_val=72.0, step=0.5,
            decimals=1, units=(("pt", "磅"), ("cm", "cm")),
            show_unit=True, unit_inline=True, parent=self,
        )
        self._space_before.value_changed.connect(self._on_form_edited)
        rows.append(template_form_row("公式前间距", self._space_before, parent=self._card))

        self._space_after = SpacingInput(
            unit="pt", min_val=0.0, max_val=72.0, step=0.5,
            decimals=1, units=(("pt", "磅"), ("cm", "cm")),
            show_unit=True, unit_inline=True, parent=self,
        )
        self._space_after.value_changed.connect(self._on_form_edited)
        rows.append(template_form_row("公式后间距", self._space_after, parent=self._card))

        self._unify_font = ToggleSwitch(self, checked=True)
        self._unify_font.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("统一字体", self._unify_font, parent=self._card))

        self._unify_size = ToggleSwitch(self, checked=True)
        self._unify_size.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("统一字号", self._unify_size, parent=self._card))

        self._unify_spacing = ToggleSwitch(self, checked=True)
        self._unify_spacing.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("统一间距", self._unify_spacing, parent=self._card))

        self._auto_shrink_number = ToggleSwitch(self, checked=True)
        self._auto_shrink_number.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("自适应编号列", self._auto_shrink_number, parent=self._card))
        self._card.add_widget(TemplateFormStack(rows, parent=self._card))

    def _build_hint(self) -> None:
        self._footer_note = QLabel("预览与执行共享上述公式字体、间距、对齐和编号参数。")
        self._footer_note.setObjectName("tpl_formula_footer")
        self._footer_note.setWordWrap(True)
        self._card.add_widget(self._footer_note)

    def _set_combo_by_data(
        self,
        combo: StyledComboBox,
        target,
        *,
        allow_custom: bool = False,
    ) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == target:
                if (
                    allow_custom
                    and combo is self._numbering_combo
                    and self._custom_numbering_value
                    and self._custom_numbering_value != target
                ):
                    for custom_index in range(self._numbering_combo.count() - 1, -1, -1):
                        if self._numbering_combo.itemData(custom_index) == self._custom_numbering_value:
                            self._numbering_combo.removeItem(custom_index)
                            break
                    self._custom_numbering_value = None
                combo.setCurrentIndex(index)
                return
        if allow_custom and target not in (None, ""):
            self._set_custom_numbering_option(str(target))

    def _set_custom_numbering_option(self, value: str) -> None:
        normalized = str(value or "").strip()
        if not normalized:
            return

        if self._custom_numbering_value and self._custom_numbering_value != normalized:
            for index in range(self._numbering_combo.count() - 1, -1, -1):
                if self._numbering_combo.itemData(index) == self._custom_numbering_value:
                    self._numbering_combo.removeItem(index)
                    break

        for index in range(self._numbering_combo.count()):
            if self._numbering_combo.itemData(index) == normalized:
                self._numbering_combo.setCurrentIndex(index)
                self._custom_numbering_value = normalized
                return

        self._numbering_combo.addItem(f"自定义 ({normalized})", normalized)
        self._numbering_combo.setCurrentIndex(self._numbering_combo.count() - 1)
        self._custom_numbering_value = normalized

    def set_template(self, template: TemplateConfig | None) -> None:
        preserve_snapshot = template is self._current_template and self._snapshot is not None
        self._current_template = template
        if template is None:
            self._snapshot = None
            return
        if not preserve_snapshot:
            self.capture_entry_snapshot()
        self._is_syncing = True
        try:
            self._font_combo.set_font_name(template.formula_table.formula_font_name)
            self._size_combo.set_pt(template.formula_table.formula_font_size_pt)
            self._set_combo_by_data(self._alignment_combo, template.formula_table.block_alignment)
            self._set_combo_by_data(self._table_alignment_combo, template.formula_table.table_alignment)
            self._set_combo_by_data(
                self._formula_cell_alignment_combo,
                template.formula_table.formula_cell_alignment,
            )
            self._set_combo_by_data(
                self._number_alignment_combo,
                template.formula_table.number_alignment,
            )
            self._set_combo_by_data(
                self._numbering_combo,
                template.equation_numbering.numbering_format,
                allow_custom=True,
            )
            self._number_font_combo.set_font_name(template.formula_table.number_font_name)
            self._number_size_combo.set_pt(template.formula_table.number_font_size_pt)
            self._line_spacing.set_value(template.formula_table.formula_line_spacing, "multiple")
            self._space_before.set_value(
                template.formula_table.formula_space_before_pt,
                template.formula_table.formula_space_before_unit,
            )
            self._space_after.set_value(
                template.formula_table.formula_space_after_pt,
                template.formula_table.formula_space_after_unit,
            )
            self._unify_font.set_checked(template.formula_style.unify_font)
            self._unify_size.set_checked(template.formula_style.unify_size)
            self._unify_spacing.set_checked(template.formula_style.unify_spacing)
            self._auto_shrink_number.set_checked(
                template.formula_table.auto_shrink_number_column
            )
        finally:
            self._is_syncing = False
        self._summary_card.set_summary_items(
            build_template_detail_summary_items(template, "tpl_formula")
        )

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        formula = self._current_template.formula_table
        style = self._current_template.formula_style
        numbering = self._current_template.equation_numbering

        formula.formula_font_name = self._font_combo.selected_font()
        pt = self._size_combo.current_pt()
        if pt is not None:
            formula.formula_font_size_pt = pt
            formula.formula_font_size_display = f"{pt:g}"
        formula.block_alignment = str(self._alignment_combo.currentData() or "center")
        formula.table_alignment = str(self._table_alignment_combo.currentData() or "center")
        formula.formula_cell_alignment = str(
            self._formula_cell_alignment_combo.currentData() or "center"
        )
        formula.number_alignment = str(self._number_alignment_combo.currentData() or "right")
        numbering.numbering_format = str(self._numbering_combo.currentData() or "chapter.seq")
        formula.number_font_name = self._number_font_combo.selected_font()
        number_pt = self._number_size_combo.current_pt()
        if number_pt is not None:
            formula.number_font_size_pt = number_pt
            formula.number_font_size_display = f"{number_pt:g}"
        formula.formula_line_spacing = self._line_spacing.value()
        formula.formula_space_before_pt = self._space_before.value()
        formula.formula_space_before_unit = self._space_before.unit()
        formula.formula_space_after_pt = self._space_after.value()
        formula.formula_space_after_unit = self._space_after.unit()
        style.unify_font = self._unify_font.isChecked()
        style.unify_size = self._unify_size.isChecked()
        style.unify_spacing = self._unify_spacing.isChecked()
        formula.auto_shrink_number_column = self._auto_shrink_number.isChecked()

        self._summary_card.set_summary_items(
            build_template_detail_summary_items(self._current_template, "tpl_formula")
        )
        self.template_edited.emit(self._current_template)

    def capture_entry_snapshot(self) -> None:
        if self._current_template is None:
            self._snapshot = None
            return
        self._snapshot = (
            deepcopy(self._current_template.formula_table),
            deepcopy(self._current_template.formula_style),
            deepcopy(self._current_template.equation_numbering),
        )

    def _on_restore_entry(self) -> None:
        if self._current_template is None or self._snapshot is None:
            return
        formula, style, numbering = self._snapshot
        self._current_template.formula_table = deepcopy(formula)
        self._current_template.formula_style = deepcopy(style)
        self._current_template.equation_numbering = deepcopy(numbering)
        self.set_template(self._current_template)
        self.template_edited.emit(self._current_template)

    def apply_theme(self) -> None:
        self._apply_theme()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._save_btn.setEnabled(self._save_enabled)
        self._restore_btn.setEnabled(self._save_enabled)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._desc.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
        self._footer_note.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")
        apply_template_summary_action_button(self._restore_btn, "ghost-primary")
        apply_template_summary_action_button(self._save_btn, "primary")
        self._restore_btn.setEnabled(self._save_enabled)
        self._save_btn.setEnabled(self._save_enabled)


__all__ = ["FormulaDetail"]
