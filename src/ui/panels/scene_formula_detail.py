"""Thesis-only formula and chemical-script detail panes.

The panes intentionally mirror template detail semantics: a summary header
owns the execution switch plus restore/save actions, while the cards below
edit the retained parameters.  Turning a feature off never erases its detail
configuration.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from src.config.feature_configs import (
    EquationNumberingConfig,
    FormulaStyleConfig,
    FormulaTableConfig,
)
from src.config.formula_policy import (
    ChemTypographyOptions,
    FormulaConvertOptions,
    FormulaToTableOptions,
)
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.qt_api import (
    QCheckBox,
    QLabel,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.navigation_highlight import NavigationHighlighter
from src.shared.ui.persistence_actions import PersistenceActions
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.summary_grid import SummaryGridItem
from src.shared.ui.template_form_layout import (
    TemplateFormGrid,
    compact_form_column_gap,
    template_form_row,
)
from src.shared.ui.template_summary_card import DetailSummaryCard
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.panels.scene_detail_support import _set_combo_by_data

FORMULA_OUTPUT_MODE_LABELS: dict[str, str] = {
    "word_native": "Word 原生公式",
    "latex": "LaTeX 逻辑（仍输出 Word 原生公式）",
    "keep_source": "保留原文",
}

FORMULA_LOW_CONFIDENCE_LABELS: dict[str, str] = {
    "skip_and_mark": "跳过并标记",
    "manual_review": "人工复核",
}

FORMULA_ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
)

FORMULA_NUMBERING_OPTIONS: tuple[tuple[str, str], ...] = (
    ("chapter.seq", "章.序"),
    ("chapter-seq", "章-序"),
    ("chapter:seq", "章:序"),
    ("chapter/seq", "章/序"),
    ("chapter_seq", "章_序"),
    ("chapterseq", "章序"),
    ("global", "全局序号"),
)

CHEM_TYPOGRAPHY_SCOPE_LABELS: tuple[tuple[str, str], ...] = (
    ("body", "正文"),
    ("headings", "标题"),
    ("abstract_cn", "中文摘要"),
    ("abstract_en", "英文摘要"),
    ("tables", "表格"),
    ("captions", "题注"),
    ("references", "参考文献"),
)


def _display_label(combo: StyledComboBox, fallback: str) -> str:
    text = str(combo.currentText() or "").strip()
    return text or fallback


def _selection_grid(
    controls: list[QCheckBox],
    *,
    parent: QWidget,
    columns: int = 2,
) -> TemplateFormGrid:
    """Lay selection options out on the same responsive grid as detail forms."""

    resolved_columns = max(1, int(columns))
    for control in controls:
        control.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    rows = [
        controls[index : index + resolved_columns]
        for index in range(0, len(controls), resolved_columns)
    ]
    return TemplateFormGrid(
        rows,
        parent=parent,
        column_gap=compact_form_column_gap(),
        column_stretches=tuple(1 for _ in range(resolved_columns)),
        align_trailing_labels=False,
        stack_slack=24,
    )


class _AggregateScopeCheckBox(QCheckBox):
    """Tri-state summary whose user cycle remains select-all / clear-all."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setTristate(True)

    def nextCheckState(self) -> None:
        self.setCheckState(
            Qt.Unchecked if self.checkState() == Qt.Checked else Qt.Checked
        )


@dataclass(eq=True)
class _FormulaSnapshot:
    formula_enabled: bool
    formula_convert: FormulaConvertOptions
    formula_to_table: FormulaToTableOptions
    formula_table: FormulaTableConfig
    formula_style: FormulaStyleConfig
    equation_numbering: EquationNumberingConfig

    @classmethod
    def from_scene(cls, scene: SceneWorkspace) -> _FormulaSnapshot:
        rules = scene.ensure_thesis_formula_rules()
        return cls(
            formula_enabled=bool(rules.formula_enabled),
            formula_convert=copy.deepcopy(rules.formula_convert),
            formula_to_table=copy.deepcopy(rules.formula_to_table),
            formula_table=copy.deepcopy(rules.formula_table),
            formula_style=copy.deepcopy(rules.formula_style),
            equation_numbering=copy.deepcopy(rules.equation_numbering),
        )

    def apply_to(self, scene: SceneWorkspace) -> None:
        rules = scene.ensure_thesis_formula_rules()
        rules.formula_enabled = bool(self.formula_enabled)
        rules.formula_convert = copy.deepcopy(self.formula_convert)
        rules.formula_to_table = copy.deepcopy(self.formula_to_table)
        rules.formula_table = copy.deepcopy(self.formula_table)
        rules.formula_style = copy.deepcopy(self.formula_style)
        rules.equation_numbering = copy.deepcopy(self.equation_numbering)


@dataclass(eq=True)
class _ChemTypographySnapshot:
    chem_typography: ChemTypographyOptions

    @classmethod
    def from_scene(cls, scene: SceneWorkspace) -> _ChemTypographySnapshot:
        return cls(
            chem_typography=copy.deepcopy(
                scene.ensure_thesis_formula_rules().chem_typography
            )
        )

    def apply_to(self, scene: SceneWorkspace) -> None:
        scene.ensure_thesis_formula_rules().chem_typography = copy.deepcopy(
            self.chem_typography
        )


class _SceneFormulaRulesCard(QWidget):
    """Formula conversion, layout and numbering as one thesis detail pane."""

    scene_edited = Signal()
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._current_template: TemplateConfig | None = None
        self._snapshot: _FormulaSnapshot | None = None
        self._is_syncing = False
        self._save_enabled = False
        self._navigation_highlighter = NavigationHighlighter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._summary_card = DetailSummaryCard(
            "公式处理",
            "sigma",
            columns=12,
            parent=self,
        )
        self._feature_enabled = ToggleSwitch(self._summary_card, checked=True)
        self._feature_enabled.setObjectName("scn_formula_feature_enabled")
        self._feature_enabled.setAccessibleName("启用公式处理")
        self._feature_enabled.toggled_signal.connect(self._on_feature_toggled)
        self._summary_card.add_control(self._feature_enabled)
        self._persistence = PersistenceActions(
            object_name_prefix="scn_formula",
            parent=self._summary_card,
        )
        self._persistence.restore_requested.connect(self._on_restore_entry)
        self._persistence.save_requested.connect(self.save_requested.emit)
        self._summary_card.add_action(self._persistence)
        layout.addWidget(self._summary_card)

        self._build_conversion_card()
        layout.addWidget(self._conversion_card)
        self._build_layout_card()
        layout.addStretch(1)

        self.apply_theme()
        bind_theme(self, self.apply_theme)

    def _build_conversion_card(self) -> None:
        self._conversion_card = Card(parent=self)
        self._conversion_card.set_header("公式转换", icon_name="sigma")
        self._card = self._conversion_card

        self._convert_enabled = ToggleSwitch(self, checked=True)
        self._convert_enabled.toggled_signal.connect(self._on_process_edited)
        self._output_mode = StyledComboBox(self)
        for value, label in FORMULA_OUTPUT_MODE_LABELS.items():
            self._output_mode.addItem(label, value)
        self._output_mode.currentIndexChanged.connect(self._on_process_edited)
        self._low_confidence = StyledComboBox(self)
        for value, label in FORMULA_LOW_CONFIDENCE_LABELS.items():
            self._low_confidence.addItem(label, value)
        self._low_confidence.currentIndexChanged.connect(self._on_process_edited)
        self._office_fallback = ToggleSwitch(self, checked=False)
        self._office_fallback.toggled_signal.connect(self._on_process_edited)
        self._office_timeout = StyledSpinBox(self)
        self._office_timeout.setDecimals(0)
        self._office_timeout.setRange(10, 600)
        self._office_timeout.setSingleStep(5)
        self._office_timeout.setSuffix(" 秒")
        self._office_timeout.valueChanged.connect(self._on_process_edited)

        self._conversion_form = InspectorForm(parent=self._conversion_card)
        self._conversion_form.add_field("公式片段转换", self._convert_enabled)
        self._conversion_form.add_grid(
            (
                (
                    template_form_row(
                        "输出方式", self._output_mode, parent=self._conversion_form
                    ),
                    template_form_row(
                        "低置信处理",
                        self._low_confidence,
                        parent=self._conversion_form,
                    ),
                ),
                (
                    template_form_row(
                        "Office 降级",
                        self._office_fallback,
                        parent=self._conversion_form,
                    ),
                    template_form_row(
                        "Office 超时",
                        self._office_timeout,
                        parent=self._conversion_form,
                    ),
                ),
            ),
            column_gap=compact_form_column_gap(),
            align_trailing_labels=True,
            stack_slack=24,
        )
        self._conversion_card.add_widget(self._conversion_form)

    def _build_layout_card(self) -> None:
        self._formula_font = FontCombo(lang="en", parent=self)
        self._formula_font.font_changed.connect(self._on_layout_edited)
        self._formula_size = SizeCombo(self)
        self._formula_size.size_changed.connect(self._on_layout_edited)
        self._formula_size.currentTextChanged.connect(self._on_layout_edited)
        self._number_font = FontCombo(lang="en", parent=self)
        self._number_font.font_changed.connect(self._on_layout_edited)
        self._number_size = SizeCombo(self)
        self._number_size.size_changed.connect(self._on_layout_edited)
        self._number_size.currentTextChanged.connect(self._on_layout_edited)

        self._formula_alignment = StyledComboBox(self)
        self._table_alignment = StyledComboBox(self)
        self._formula_cell_alignment = StyledComboBox(self)
        self._number_alignment = StyledComboBox(self)
        for combo in (
            self._formula_alignment,
            self._table_alignment,
            self._formula_cell_alignment,
            self._number_alignment,
        ):
            for value, label in FORMULA_ALIGNMENT_OPTIONS:
                combo.addItem(label, value)
            combo.currentIndexChanged.connect(self._on_layout_edited)

        self._numbering = StyledComboBox(self)
        for value, label in FORMULA_NUMBERING_OPTIONS:
            self._numbering.addItem(label, value)
        self._numbering.currentIndexChanged.connect(self._on_layout_edited)
        self._formula_line_spacing = StyledSpinBox(self)
        self._formula_line_spacing.setRange(0.5, 5.0)
        self._formula_line_spacing.setSingleStep(0.05)
        self._formula_line_spacing.setDecimals(2)
        self._formula_line_spacing.setSuffix(" 倍")
        self._formula_line_spacing.valueChanged.connect(self._on_layout_edited)
        spacing_units = (
            ("pt", "磅"),
            ("cm", "厘米"),
            ("mm", "毫米"),
            ("in", "英寸"),
        )
        self._formula_space_before = SpacingInput(
            unit="pt", max_val=200, step=0.5, units=spacing_units, parent=self
        )
        self._formula_space_after = SpacingInput(
            unit="pt", max_val=200, step=0.5, units=spacing_units, parent=self
        )
        self._formula_space_before.value_changed.connect(self._on_layout_edited)
        self._formula_space_after.value_changed.connect(self._on_layout_edited)
        self._auto_shrink_number = ToggleSwitch(self, checked=True)
        self._auto_shrink_number.toggled_signal.connect(self._on_layout_edited)

        self._formula_style_checks: dict[str, QCheckBox] = {}
        for key, label in (
            ("unify_font", "统一字体"),
            ("unify_size", "统一字号"),
            ("unify_spacing", "统一间距"),
        ):
            checkbox = QCheckBox("", self)
            checkbox.setAccessibleName(label)
            checkbox.toggled.connect(self._on_layout_edited)
            self._formula_style_checks[key] = checkbox

        self._formula_workflow_checks: dict[str, QCheckBox] = {}
        for key, label in (
            ("formula_to_table", "块公式转表格"),
            ("equation_numbering", "表格格式与编号"),
            ("formula_style", "公式样式统一"),
            ("block_only", "仅处理块公式"),
        ):
            checkbox = QCheckBox(label, self)
            checkbox.toggled.connect(self._on_workflow_edited)
            self._formula_workflow_checks[key] = checkbox

        self._workflow_card = Card(parent=self)
        self._workflow_card.set_header("处理步骤", icon_name="list-checks")
        self._formula_workflow_wrap = _selection_grid(
            list(self._formula_workflow_checks.values()),
            parent=self._workflow_card,
        )
        self._workflow_card.add_widget(self._formula_workflow_wrap)

        self._formula_style_card = Card(parent=self)
        self._formula_style_card.set_header("公式样式", icon_name="type-outline")
        self._formula_style_form = InspectorForm(parent=self._formula_style_card)
        self._formula_style_rows = {
            "formula_font": template_form_row(
                "公式字体", self._formula_font, parent=self._formula_style_form
            ),
            "formula_size": template_form_row(
                "公式字号", self._formula_size, parent=self._formula_style_form
            ),
            "formula_alignment": template_form_row(
                "公式块对齐",
                self._formula_alignment,
                parent=self._formula_style_form,
            ),
            "formula_line_spacing": template_form_row(
                "公式行距",
                self._formula_line_spacing,
                parent=self._formula_style_form,
            ),
            "formula_space_before": template_form_row(
                "公式段前",
                self._formula_space_before,
                parent=self._formula_style_form,
            ),
            "formula_space_after": template_form_row(
                "公式段后",
                self._formula_space_after,
                parent=self._formula_style_form,
            ),
            "unify_font": template_form_row(
                "统一字体",
                self._formula_style_checks["unify_font"],
                parent=self._formula_style_form,
            ),
            "unify_size": template_form_row(
                "统一字号",
                self._formula_style_checks["unify_size"],
                parent=self._formula_style_form,
            ),
            "unify_spacing": template_form_row(
                "统一间距",
                self._formula_style_checks["unify_spacing"],
                parent=self._formula_style_form,
            ),
        }
        self._formula_style_wrap = self._formula_style_form.add_grid(
            (
                (
                    self._formula_style_rows["formula_font"],
                    self._formula_style_rows["formula_size"],
                ),
                (
                    self._formula_style_rows["formula_alignment"],
                    self._formula_style_rows["formula_line_spacing"],
                ),
                (
                    self._formula_style_rows["formula_space_before"],
                    self._formula_style_rows["formula_space_after"],
                ),
                (
                    self._formula_style_rows["unify_font"],
                    self._formula_style_rows["unify_size"],
                ),
                (self._formula_style_rows["unify_spacing"],),
            ),
            column_gap=compact_form_column_gap(),
            align_trailing_labels=True,
            stack_slack=24,
        )
        self._formula_style_card.add_widget(self._formula_style_form)

        self._numbering_card = Card(parent=self)
        self._numbering_card.set_header("编号与表格", icon_name="table-2")
        self._numbering_form = InspectorForm(parent=self._numbering_card)
        self._numbering_rows = {
            "numbering": template_form_row(
                "编号方式", self._numbering, parent=self._numbering_form
            ),
            "number_alignment": template_form_row(
                "编号位置",
                self._number_alignment,
                parent=self._numbering_form,
            ),
            "number_font": template_form_row(
                "编号字体", self._number_font, parent=self._numbering_form
            ),
            "number_size": template_form_row(
                "编号字号", self._number_size, parent=self._numbering_form
            ),
            "table_alignment": template_form_row(
                "公式表对齐",
                self._table_alignment,
                parent=self._numbering_form,
            ),
            "formula_cell_alignment": template_form_row(
                "单元格对齐",
                self._formula_cell_alignment,
                parent=self._numbering_form,
            ),
        }
        self._numbering_form.add_grid(
            (
                (
                    self._numbering_rows["numbering"],
                    self._numbering_rows["number_alignment"],
                ),
                (
                    self._numbering_rows["number_font"],
                    self._numbering_rows["number_size"],
                ),
                (
                    self._numbering_rows["table_alignment"],
                    self._numbering_rows["formula_cell_alignment"],
                ),
            ),
            column_gap=compact_form_column_gap(),
            align_trailing_labels=True,
            stack_slack=24,
        )
        self._auto_shrink_number_row = self._numbering_form.add_field(
            "自动压缩编号列", self._auto_shrink_number
        )
        self._numbering_card.add_widget(self._numbering_form)

        self._layout_card = self._formula_style_card
        for card in (
            self._workflow_card,
            self._formula_style_card,
            self._numbering_card,
        ):
            self.layout().addWidget(card)

    def set_scene(
        self,
        scene: SceneWorkspace,
        template: TemplateConfig | None = None,
        *,
        mode_id: str = "",
    ) -> None:
        effective_mode = str(mode_id or scene.mode_id or "").strip()
        is_thesis = effective_mode == "thesis" and scene.mode_id == "thesis"
        self.setVisible(is_thesis)
        if not is_thesis:
            self._current_scene = scene
            self._current_template = template
            self._snapshot = None
            return
        preserve_snapshot = scene is self._current_scene and self._snapshot is not None
        self._current_scene = scene
        self._current_template = template
        if not preserve_snapshot:
            self._snapshot = _FormulaSnapshot.from_scene(scene)
        self._sync_from_scene()

    def capture_entry_snapshot(self) -> None:
        if self._current_scene is None or self._current_scene.mode_id != "thesis":
            self._snapshot = None
        else:
            self._snapshot = _FormulaSnapshot.from_scene(self._current_scene)
        self._refresh_action_state()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    def _sync_from_scene(self) -> None:
        if self._current_scene is None or self._current_scene.mode_id != "thesis":
            return
        rules = self._current_scene.ensure_thesis_formula_rules()
        conversion = rules.formula_convert
        formula = rules.formula_table
        self._is_syncing = True
        try:
            self._feature_enabled.set_checked(
                bool(rules.formula_enabled), animate=False
            )
            self._convert_enabled.set_checked(bool(conversion.enabled), animate=False)
            self._formula_workflow_checks["formula_to_table"].setChecked(
                bool(rules.formula_to_table.enabled)
            )
            self._formula_workflow_checks["equation_numbering"].setChecked(
                bool(rules.equation_numbering.enabled)
            )
            self._formula_workflow_checks["formula_style"].setChecked(
                bool(rules.formula_style.enabled)
            )
            self._formula_workflow_checks["block_only"].setChecked(
                bool(rules.formula_to_table.block_only)
            )
            _set_combo_by_data(
                self._output_mode, str(conversion.output_mode or "word_native")
            )
            _set_combo_by_data(
                self._low_confidence,
                str(conversion.low_confidence_policy or "skip_and_mark"),
            )
            self._office_fallback.set_checked(
                bool(conversion.office_fallback_enabled), animate=False
            )
            self._office_timeout.setValue(
                int(conversion.office_fallback_timeout_sec or 30)
            )
            self._formula_font.set_font_name(
                str(formula.formula_font_name or "Cambria Math")
            )
            self._formula_size.set_pt(float(formula.formula_font_size_pt or 12.0))
            self._number_font.set_font_name(
                str(formula.number_font_name or "Times New Roman")
            )
            self._number_size.set_pt(float(formula.number_font_size_pt or 10.5))
            _set_combo_by_data(
                self._formula_alignment, str(formula.block_alignment or "center")
            )
            _set_combo_by_data(
                self._number_alignment, str(formula.number_alignment or "right")
            )
            _set_combo_by_data(
                self._table_alignment, str(formula.table_alignment or "center")
            )
            _set_combo_by_data(
                self._formula_cell_alignment,
                str(formula.formula_cell_alignment or "center"),
            )
            self._formula_line_spacing.setValue(
                float(formula.formula_line_spacing or 1.0)
            )
            self._formula_space_before.set_value(
                float(formula.formula_space_before_pt or 0.0),
                str(formula.formula_space_before_unit or "pt"),
            )
            self._formula_space_after.set_value(
                float(formula.formula_space_after_pt or 0.0),
                str(formula.formula_space_after_unit or "pt"),
            )
            self._auto_shrink_number.set_checked(
                bool(formula.auto_shrink_number_column), animate=False
            )
            _set_combo_by_data(
                self._numbering,
                str(rules.equation_numbering.numbering_format or "chapter.seq"),
            )
            for key, checkbox in self._formula_style_checks.items():
                checkbox.setChecked(bool(getattr(rules.formula_style, key)))
        finally:
            self._is_syncing = False
        self._refresh_view_state()

    def _on_feature_toggled(self, checked: bool) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.ensure_thesis_formula_rules().formula_enabled = bool(
            checked
        )
        self._finish_edit()

    def _on_process_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        conversion = self._current_scene.ensure_thesis_formula_rules().formula_convert
        conversion.enabled = self._convert_enabled.isChecked()
        conversion.output_mode = str(self._output_mode.currentData() or "word_native")
        conversion.low_confidence_policy = str(
            self._low_confidence.currentData() or "skip_and_mark"
        )
        conversion.office_fallback_enabled = self._office_fallback.isChecked()
        conversion.office_fallback_timeout_sec = int(self._office_timeout.value())
        self._finish_edit()

    def _on_workflow_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        rules = self._current_scene.ensure_thesis_formula_rules()
        rules.formula_to_table.enabled = self._formula_workflow_checks[
            "formula_to_table"
        ].isChecked()
        rules.formula_to_table.block_only = self._formula_workflow_checks[
            "block_only"
        ].isChecked()
        rules.equation_numbering.enabled = self._formula_workflow_checks[
            "equation_numbering"
        ].isChecked()
        rules.formula_style.enabled = self._formula_workflow_checks[
            "formula_style"
        ].isChecked()
        self._finish_edit()

    def _on_layout_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        rules = self._current_scene.ensure_thesis_formula_rules()
        formula = rules.formula_table
        formula.formula_font_name = self._formula_font.selected_font() or "Cambria Math"
        point_size = self._formula_size.current_pt()
        if point_size is not None:
            formula.formula_font_size_pt = point_size
            formula.formula_font_size_display = f"{point_size:g}"
        formula.number_font_name = (
            self._number_font.selected_font() or "Times New Roman"
        )
        number_size = self._number_size.current_pt()
        if number_size is not None:
            formula.number_font_size_pt = number_size
            formula.number_font_size_display = f"{number_size:g}"
        formula.block_alignment = str(self._formula_alignment.currentData() or "center")
        formula.table_alignment = str(self._table_alignment.currentData() or "center")
        formula.formula_cell_alignment = str(
            self._formula_cell_alignment.currentData() or "center"
        )
        formula.number_alignment = str(self._number_alignment.currentData() or "right")
        formula.formula_line_spacing = float(self._formula_line_spacing.value())
        formula.formula_space_before_pt = float(self._formula_space_before.value())
        formula.formula_space_before_unit = self._formula_space_before.unit()
        formula.formula_space_after_pt = float(self._formula_space_after.value())
        formula.formula_space_after_unit = self._formula_space_after.unit()
        formula.auto_shrink_number_column = self._auto_shrink_number.isChecked()
        rules.equation_numbering.numbering_format = str(
            self._numbering.currentData() or "chapter.seq"
        )
        for key, checkbox in self._formula_style_checks.items():
            setattr(rules.formula_style, key, checkbox.isChecked())
        self._finish_edit()

    def _on_restore_entry(self) -> None:
        if self._current_scene is None or self._snapshot is None:
            return
        self._snapshot.apply_to(self._current_scene)
        self._sync_from_scene()
        self.scene_edited.emit()

    def _finish_edit(self) -> None:
        self._refresh_view_state()
        self.scene_edited.emit()

    def _refresh_view_state(self) -> None:
        self._sync_control_states()
        self._refresh_summary()
        self._refresh_action_state()

    def _sync_control_states(self) -> None:
        feature_enabled = self._feature_enabled.isChecked()
        self._conversion_card.setEnabled(feature_enabled)
        self._workflow_card.setEnabled(feature_enabled)
        convert_enabled = feature_enabled and self._convert_enabled.isChecked()
        for control in (self._output_mode, self._low_confidence, self._office_fallback):
            control.setEnabled(convert_enabled)
        self._office_timeout.setEnabled(
            convert_enabled and self._office_fallback.isChecked()
        )
        to_table_enabled = feature_enabled and self._formula_workflow_checks[
            "formula_to_table"
        ].isChecked()
        numbering_enabled = feature_enabled and self._formula_workflow_checks[
            "equation_numbering"
        ].isChecked()
        style_enabled = feature_enabled and self._formula_workflow_checks[
            "formula_style"
        ].isChecked()
        self._formula_workflow_checks["block_only"].setEnabled(to_table_enabled)

        # Equation-table formatting intentionally reuses formula typography
        # values, while the independent formula-style pass applies them to all
        # native/source formula paragraphs.
        formula_style_controls_enabled = style_enabled or numbering_enabled
        self._formula_style_card.setEnabled(formula_style_controls_enabled)
        for row in self._formula_style_rows.values():
            row.setEnabled(formula_style_controls_enabled)

        table_controls_enabled = to_table_enabled or numbering_enabled
        self._numbering_card.setEnabled(table_controls_enabled)
        self._numbering_rows["table_alignment"].setEnabled(
            table_controls_enabled
        )
        for key in (
            "numbering",
            "number_alignment",
            "number_font",
            "number_size",
            "formula_cell_alignment",
        ):
            self._numbering_rows[key].setEnabled(numbering_enabled)
        self._auto_shrink_number_row.setEnabled(numbering_enabled)

    def _refresh_summary(self) -> None:
        if self._current_scene is None or self._current_scene.mode_id != "thesis":
            self._summary_card.set_summary_items(())
            return
        rules = self._current_scene.ensure_thesis_formula_rules()
        workflow_labels = [
            label
            for enabled, label in (
                (rules.formula_to_table.enabled, "转表格"),
                (rules.equation_numbering.enabled, "编号"),
                (rules.formula_style.enabled, "统一样式"),
            )
            if enabled
        ]
        formula = rules.formula_table
        self._summary_card.set_summary_items(
            (
                SummaryGridItem(
                    "conversion",
                    "公式转换",
                    (
                        FORMULA_OUTPUT_MODE_LABELS.get(
                            str(rules.formula_convert.output_mode),
                            str(rules.formula_convert.output_mode),
                        )
                        if rules.formula_convert.enabled
                        else "不转换"
                    ),
                    FORMULA_LOW_CONFIDENCE_LABELS.get(
                        str(rules.formula_convert.low_confidence_policy),
                        str(rules.formula_convert.low_confidence_policy),
                    ),
                    icon_name="sigma",
                    column_span=4,
                ),
                SummaryGridItem(
                    "workflow",
                    "排版步骤",
                    f"{len(workflow_labels)} 项处理" if workflow_labels else "不处理",
                    "、".join(workflow_labels) or "保留现有排版",
                    icon_name="sliders-horizontal",
                    column_span=4,
                ),
                SummaryGridItem(
                    "style",
                    "公式样式",
                    f"{formula.formula_font_name} / {formula.formula_font_size_pt:g} 磅",
                    f"{_display_label(self._formula_alignment, '居中')} · {_display_label(self._numbering, '章.序')}",
                    icon_name="type-outline",
                    column_span=4,
                ),
            )
        )

    def _refresh_action_state(self) -> None:
        current = self._current_scene
        restore_enabled = False
        if (
            current is not None
            and current.mode_id == "thesis"
            and self._snapshot is not None
        ):
            restore_enabled = _FormulaSnapshot.from_scene(current) != self._snapshot
        self._persistence.set_states(
            restore_enabled=restore_enabled,
            save_enabled=self._save_enabled,
        )

    def focus_navigation_field(self, field_id: str) -> bool:
        if self.isHidden():
            return False
        target = str(field_id or "").strip()
        if target.startswith("thesis_formula_rules."):
            target = target.removeprefix("thesis_formula_rules.")
        controls = {
            "formula_enabled": self._feature_enabled,
            "formula_convert": self._convert_enabled,
            "formula_convert.enabled": self._convert_enabled,
            "formula_convert.output_mode": self._output_mode,
            "output_mode": self._output_mode,
            "formula_convert.low_confidence_policy": self._low_confidence,
            "low_confidence_policy": self._low_confidence,
            "formula_convert.office_fallback_enabled": self._office_fallback,
            "office_fallback_enabled": self._office_fallback,
            "formula_convert.office_fallback_timeout_sec": self._office_timeout,
            "office_fallback_timeout_sec": self._office_timeout,
            "equation_table_format": self._formula_workflow_wrap,
            "formula_to_table": self._formula_workflow_checks["formula_to_table"],
            "formula_to_table.enabled": self._formula_workflow_checks[
                "formula_to_table"
            ],
            "formula_to_table.block_only": self._formula_workflow_checks["block_only"],
            "formula_table": self._formula_font,
            "formula_table.formula_font_name": self._formula_font,
            "formula_table.formula_font_size_pt": self._formula_size,
            "formula_table.number_font_name": self._number_font,
            "formula_table.number_font_size_pt": self._number_size,
            "formula_table.block_alignment": self._formula_alignment,
            "formula_table.table_alignment": self._table_alignment,
            "formula_table.formula_cell_alignment": self._formula_cell_alignment,
            "formula_table.number_alignment": self._number_alignment,
            "formula_table.formula_line_spacing": self._formula_line_spacing,
            "formula_table.formula_space_before_pt": self._formula_space_before,
            "formula_table.formula_space_after_pt": self._formula_space_after,
            "formula_table.auto_shrink_number_column": self._auto_shrink_number,
            "formula_style": self._formula_style_wrap,
            "formula_style.enabled": self._formula_workflow_checks["formula_style"],
            "equation_numbering": self._numbering,
            "equation_numbering.enabled": self._formula_workflow_checks[
                "equation_numbering"
            ],
            "equation_numbering.numbering_format": self._numbering,
        }
        control = controls.get(target)
        if control is None:
            return False
        self._navigation_highlighter.highlight(control, target)
        control.setFocus(Qt.OtherFocusReason)
        return True

    def apply_theme(self) -> None:
        theme = get_theme()
        self.layout().setSpacing(theme.template_detail_section_gap)
        checkbox_style = build_checkbox_stylesheet(theme)
        for checkbox in (
            *self._formula_style_checks.values(),
            *self._formula_workflow_checks.values(),
        ):
            checkbox.setStyleSheet(checkbox_style)
        self._feature_enabled.set_checked_track_color(theme.primary)
        self._persistence.apply_theme()


class _SceneChemTypographyDetail(QWidget):
    """Chemical formula super/subscript recovery as an independent detail."""

    scene_edited = Signal()
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._snapshot: _ChemTypographySnapshot | None = None
        self._is_syncing = False
        self._save_enabled = False
        self._navigation_highlighter = NavigationHighlighter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._summary_card = DetailSummaryCard(
            "上下角标与化学式",
            "whole-word",
            columns=12,
            parent=self,
        )
        self._chem_enabled = ToggleSwitch(self._summary_card, checked=False)
        self._chem_enabled.setObjectName("scn_chem_typography_enabled")
        self._chem_enabled.setAccessibleName("启用上下角标与化学式")
        self._chem_enabled.toggled_signal.connect(self._on_chem_edited)
        self._summary_card.add_control(self._chem_enabled)
        self._persistence = PersistenceActions(
            object_name_prefix="scn_chem_typography",
            parent=self._summary_card,
        )
        self._persistence.restore_requested.connect(self._on_restore_entry)
        self._persistence.save_requested.connect(self.save_requested.emit)
        self._summary_card.add_action(self._persistence)
        layout.addWidget(self._summary_card)

        self._chem_font = FontCombo(lang="en", parent=self)
        self._chem_font.font_changed.connect(self._on_chem_edited)
        self._chem_all_scope = _AggregateScopeCheckBox("全文", self)
        self._chem_all_scope.stateChanged.connect(
            lambda state: self._on_chem_scope_toggled(
                "__all__", Qt.CheckState(state) == Qt.Checked
            )
        )
        self._chem_scope_checks: dict[str, QCheckBox] = {}
        for key, label in CHEM_TYPOGRAPHY_SCOPE_LABELS:
            checkbox = QCheckBox(label, self)
            checkbox.toggled.connect(
                lambda checked, scope_key=key: self._on_chem_scope_toggled(
                    scope_key, checked
                )
            )
            self._chem_scope_checks[key] = checkbox

        self._scope_card = Card(parent=self)
        self._scope_card.set_header("处理范围", icon_name="scan-text")
        self._chem_scope_wrap = QWidget(self._scope_card)
        scope_layout = QVBoxLayout(self._chem_scope_wrap)
        scope_layout.setContentsMargins(0, 0, 0, 0)
        scope_layout.setSpacing(get_theme().spacing_sm)
        scope_layout.addWidget(self._chem_all_scope)
        self._chem_scope_grid = _selection_grid(
            list(self._chem_scope_checks.values()),
            parent=self._chem_scope_wrap,
        )
        scope_layout.addWidget(self._chem_scope_grid)
        self._scope_card.add_widget(self._chem_scope_wrap)
        layout.addWidget(self._scope_card)

        self._chem_style_card = Card(parent=self)
        self._chem_style_card.set_header("字符样式", icon_name="type-outline")
        self._chem_style_form = InspectorForm(parent=self._chem_style_card)
        self._chem_style_form.add_field("西文字体", self._chem_font)
        self._chem_style_card.add_widget(self._chem_style_form)
        self._chem_note = QLabel(
            "用于恢复 H₂O、SO₄²⁻ 等化学式的上下角标；不会改写公式表格中的数学上下标。",
            self._chem_style_card,
        )
        self._chem_note.setWordWrap(True)
        self._chem_style_card.add_widget(self._chem_note)
        layout.addWidget(self._chem_style_card)
        self._chem_card = self._chem_style_card
        layout.addStretch(1)

        self.apply_theme()
        bind_theme(self, self.apply_theme)

    def set_scene(
        self,
        scene: SceneWorkspace,
        template: TemplateConfig | None = None,
        *,
        mode_id: str = "",
    ) -> None:
        del template
        effective_mode = str(mode_id or scene.mode_id or "").strip()
        is_thesis = effective_mode == "thesis" and scene.mode_id == "thesis"
        self.setVisible(is_thesis)
        if not is_thesis:
            self._current_scene = scene
            self._snapshot = None
            return
        preserve_snapshot = scene is self._current_scene and self._snapshot is not None
        self._current_scene = scene
        if not preserve_snapshot:
            self._snapshot = _ChemTypographySnapshot.from_scene(scene)
        self._sync_from_scene()

    def capture_entry_snapshot(self) -> None:
        if self._current_scene is None or self._current_scene.mode_id != "thesis":
            self._snapshot = None
        else:
            self._snapshot = _ChemTypographySnapshot.from_scene(self._current_scene)
        self._refresh_action_state()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    def _sync_from_scene(self) -> None:
        if self._current_scene is None or self._current_scene.mode_id != "thesis":
            return
        chem = self._current_scene.ensure_thesis_formula_rules().chem_typography
        self._is_syncing = True
        try:
            self._chem_enabled.set_checked(bool(chem.enabled), animate=False)
            self._chem_font.set_font_name(str(chem.western_font or "Times New Roman"))
            scopes = dict(chem.scopes or {})
            for key, checkbox in self._chem_scope_checks.items():
                checkbox.setChecked(bool(scopes.get(key, False)))
            self._sync_chem_all_scope_state()
        finally:
            self._is_syncing = False
        self._refresh_view_state()

    def _on_chem_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._write_configuration()
        self._finish_edit()

    def _on_chem_scope_toggled(self, scope_key: str, checked: bool) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._is_syncing = True
        try:
            if scope_key == "__all__":
                for checkbox in self._chem_scope_checks.values():
                    checkbox.setChecked(bool(checked))
            elif scope_key != "__all__":
                self._sync_chem_all_scope_state()
        finally:
            self._is_syncing = False
        self._write_configuration()
        self._finish_edit()

    def _sync_chem_all_scope_state(self) -> None:
        selected = sum(
            1
            for checkbox in self._chem_scope_checks.values()
            if checkbox.isChecked()
        )
        if selected == len(self._chem_scope_checks):
            state = Qt.Checked
        elif selected:
            state = Qt.PartiallyChecked
        else:
            state = Qt.Unchecked
        self._chem_all_scope.setCheckState(state)

    def _write_configuration(self) -> None:
        if self._current_scene is None:
            return
        chem = self._current_scene.ensure_thesis_formula_rules().chem_typography
        chem.enabled = self._chem_enabled.isChecked()
        chem.western_font = self._chem_font.selected_font() or "Times New Roman"
        scopes = dict(chem.scopes or {})
        for key, checkbox in self._chem_scope_checks.items():
            scopes[key] = checkbox.isChecked()
        chem.scopes = scopes

    def _on_restore_entry(self) -> None:
        if self._current_scene is None or self._snapshot is None:
            return
        self._snapshot.apply_to(self._current_scene)
        self._sync_from_scene()
        self.scene_edited.emit()

    def _finish_edit(self) -> None:
        self._refresh_view_state()
        self.scene_edited.emit()

    def _refresh_view_state(self) -> None:
        enabled = self._chem_enabled.isChecked()
        self._scope_card.setEnabled(enabled)
        self._chem_style_card.setEnabled(enabled)
        self._refresh_summary()
        self._refresh_action_state()

    def _refresh_summary(self) -> None:
        if self._current_scene is None or self._current_scene.mode_id != "thesis":
            self._summary_card.set_summary_items(())
            return
        chem = self._current_scene.ensure_thesis_formula_rules().chem_typography
        active_scopes = [
            label
            for key, label in CHEM_TYPOGRAPHY_SCOPE_LABELS
            if bool((chem.scopes or {}).get(key, False))
        ]
        scope_value = (
            "全文"
            if len(active_scopes) == len(CHEM_TYPOGRAPHY_SCOPE_LABELS)
            else (f"{len(active_scopes)} 个范围" if active_scopes else "未选择范围")
        )
        self._summary_card.set_summary_items(
            (
                SummaryGridItem(
                    "scope",
                    "处理范围",
                    scope_value,
                    "、".join(active_scopes) or "开启后请至少选择一个范围",
                    icon_name="scan-text",
                    column_span=4,
                    variant="warning"
                    if chem.enabled and not active_scopes
                    else "neutral",
                ),
                SummaryGridItem(
                    "font",
                    "西文字体",
                    str(chem.western_font or "Times New Roman"),
                    "仅作用于识别到的化学式字符",
                    icon_name="type-outline",
                    column_span=4,
                ),
                SummaryGridItem(
                    "boundary",
                    "处理边界",
                    "化学式上下角标",
                    "不处理公式表格中的数学上下标",
                    icon_name="whole-word",
                    column_span=4,
                ),
            )
        )

    def _refresh_action_state(self) -> None:
        current = self._current_scene
        restore_enabled = False
        if (
            current is not None
            and current.mode_id == "thesis"
            and self._snapshot is not None
        ):
            restore_enabled = (
                _ChemTypographySnapshot.from_scene(current) != self._snapshot
            )
        self._persistence.set_states(
            restore_enabled=restore_enabled,
            save_enabled=self._save_enabled,
        )

    def focus_navigation_field(self, field_id: str) -> bool:
        if self.isHidden():
            return False
        target = str(field_id or "").strip()
        if target.startswith("thesis_formula_rules."):
            target = target.removeprefix("thesis_formula_rules.")
        controls = {
            "chem_typography": self._chem_enabled,
            "chem_typography.enabled": self._chem_enabled,
            "chem_typography.western_font": self._chem_font,
            "chem_typography.scopes": self._chem_scope_wrap,
        }
        control = controls.get(target)
        if control is None:
            return False
        self._navigation_highlighter.highlight(control, target)
        control.setFocus(Qt.OtherFocusReason)
        return True

    def apply_theme(self) -> None:
        theme = get_theme()
        self.layout().setSpacing(theme.template_detail_section_gap)
        checkbox_style = build_checkbox_stylesheet(theme)
        for checkbox in (
            self._chem_all_scope,
            *self._chem_scope_checks.values(),
        ):
            checkbox.setStyleSheet(checkbox_style)
        self._chem_note.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
        )
        self._chem_enabled.set_checked_track_color(theme.primary)
        self._persistence.apply_theme()


__all__ = ["_SceneChemTypographyDetail", "_SceneFormulaRulesCard"]
