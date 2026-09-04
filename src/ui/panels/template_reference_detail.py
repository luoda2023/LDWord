"""Reference detail pane — paragraph style + reference rules.

The paragraph style section supports two modes:
  * "跟随正文" — inherits from ``styles["body"]``
  * "独立设置" — has its own ``styles["references_body"]``

The reference rules section (hanging indent, list cleanup) always shows.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.style_semantics import (
    LINE_SPACING_OPTIONS,
    display_font_size_with_name,
    spacing_editor_config,
    SPACING_UNIT_OPTIONS,
    line_spacing_is_editable,
    line_spacing_unit_label,
    normalize_line_spacing_type,
    resolve_style_paragraph_spacing,
    resolve_line_spacing_value,
)
from src.config.style_variant_semantics import (
    disable_variant_override,
    enable_variant_override,
    get_effective_style,
    is_variant_overridden,
)
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import (
    QLabel,
    QPushButton,
    QSize,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.button_style import build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.layout_sync import (
    refresh_layout_chain,
    refresh_layout_chain_later,
    reserve_visible_height,
    updates_suspended,
)
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

_VARIANT_KEY = "references_body"

ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
    ("justify", "两端对齐"),
)

@dataclass(eq=True)
class _ReferenceSnapshot:
    reference_style: object
    section_style: object
    section_style_enabled: bool

    @classmethod
    def from_template(cls, template: TemplateConfig) -> "_ReferenceSnapshot":
        return cls(
            reference_style=deepcopy(template.reference_style),
            section_style=deepcopy(template.styles.get(_VARIANT_KEY)),
            section_style_enabled=bool(is_variant_overridden(template, _VARIANT_KEY)),
        )

    def apply_to(self, template: TemplateConfig) -> None:
        template.reference_style = deepcopy(self.reference_style)
        if self.section_style_enabled:
            template.styles[_VARIANT_KEY] = deepcopy(self.section_style)
        else:
            template.styles.pop(_VARIANT_KEY, None)


class ReferenceDetail(QWidget):
    """Reference-style pane: paragraph style override + reference rules."""

    template_edited = Signal(object)
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._snapshot: _ReferenceSnapshot | None = None
        self._is_syncing = False
        self._save_enabled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # ── Summary card ──
        self._summary_card = TemplateSummaryCard("参考文献", "book-open", parent=self)
        self._header_card = self._summary_card
        layout.addWidget(self._summary_card)

        # ── Style source ──
        self._source_card = Card("样式来源", parent=self)
        self._source_card.set_header("样式来源", icon_name="book-open")
        self._mode_card = self._source_card
        layout.addWidget(self._source_card)

        # ── Entry style (visible only in independent mode) ──
        self._style_card = Card("条目样式", parent=self)
        self._style_card.set_header("条目样式", icon_name="type-outline")
        self._style_container = self._style_card
        self._text_section = self._style_card
        self._spacing_section = self._style_card
        layout.addWidget(self._style_card)

        # ── Entry rules (always visible) ──
        self._rules_card = Card("条目规则", parent=self)
        self._rules_card.set_header("条目规则", icon_name="book-open")
        self._rules_section = self._rules_card
        layout.addWidget(self._rules_card)

        layout.addStretch(1)

        self._build_header()
        self._build_mode_switch()
        self._build_style_form()
        self._build_rules()

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ──────────────────────────────────────────────────────
    # Build UI
    # ──────────────────────────────────────────────────────

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

    def _build_mode_switch(self) -> None:
        self._source_form = InspectorForm(parent=self._source_card)

        self._mode_combo = StyledComboBox(self)
        self._mode_combo.addItem("跟随正文", "follow")
        self._mode_combo.addItem("独立设置", "independent")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._mode_row = self._form_row("样式来源", self._mode_combo, parent=self._source_form)

        self._source_summary = QLabel("", self)
        self._source_summary.setObjectName("tpl_reference_source_summary")
        self._source_summary.setWordWrap(True)
        self._source_summary_row = self._form_row("当前样式", self._source_summary, parent=self._source_form)

        self._source_grid = self._source_form.add_grid(
            [
                [self._mode_row],
                [self._source_summary_row],
            ]
        )
        self._source_card.add_widget(self._source_form)

    def _build_style_form(self) -> None:
        self._style_form = InspectorForm(parent=self._style_card)

        self._font_cn = FontCombo(lang="cn", parent=self)
        self._font_cn.font_changed.connect(self._on_form_edited)
        self._font_cn_row = self._form_row("中文字体", self._font_cn, parent=self._style_form)

        self._font_en = FontCombo(lang="en", parent=self)
        self._font_en.font_changed.connect(self._on_form_edited)
        self._font_en_row = self._form_row("英文字体", self._font_en, parent=self._style_form)

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
            self._build_emphasis_widget(),
            parent=self._style_form,
        )

        self._alignment_combo = StyledComboBox(self)
        for value, label in ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(label, value)
        self._alignment_combo.currentIndexChanged.connect(self._on_form_edited)
        self._alignment_row = self._form_row("对齐", self._alignment_combo, parent=self._style_form)

        self._line_type_combo = StyledComboBox(self)
        for value, label in LINE_SPACING_OPTIONS:
            self._line_type_combo.addItem(label, value)
        self._line_type_combo.currentIndexChanged.connect(self._on_line_spacing_type_changed)
        self._line_type_row = self._form_row("行距类型", self._line_type_combo, parent=self._style_form)

        self._line_value = SpacingInput(
            unit="pt", min_val=0.5, max_val=60.0, step=0.5,
            decimals=1, units=("pt",), show_unit=False, parent=self,
        )
        self._line_value.value_changed.connect(self._on_form_edited)
        self._line_value_suffix = QLabel("磅", self)
        self._line_value_suffix.setObjectName("tpl_style_unit")
        self._line_value_row = self._form_row(
            "行距值",
            self._line_value,
            suffix_widget=self._line_value_suffix,
            parent=self._style_form,
        )

        self._space_before = SpacingInput(
            unit="pt", min_val=0.0, max_val=80.0, step=1.0,
            decimals=1, units=SPACING_UNIT_OPTIONS, show_unit=True, unit_inline=True, parent=self,
        )
        self._space_before.value_changed.connect(self._on_form_edited)
        before_suffix = QLabel("", self)
        before_suffix.setObjectName("tpl_style_unit")
        self._space_before_row = self._form_row(
            "段前",
            self._space_before,
            suffix_widget=before_suffix,
            parent=self._style_form,
        )

        self._space_after = SpacingInput(
            unit="pt", min_val=0.0, max_val=80.0, step=1.0,
            decimals=1, units=SPACING_UNIT_OPTIONS, show_unit=True, unit_inline=True, parent=self,
        )
        self._space_after.value_changed.connect(self._on_form_edited)
        after_suffix = QLabel("", self)
        after_suffix.setObjectName("tpl_style_unit")
        self._space_after_row = self._form_row(
            "段后",
            self._space_after,
            suffix_widget=after_suffix,
            parent=self._style_form,
        )

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

    def _build_rules(self) -> None:
        self._rules_form = InspectorForm(parent=self._rules_card)

        self._hanging_indent = SpacingInput(
            unit="cm", min_val=0.0, max_val=5.0, step=0.1,
            decimals=2, units=("cm",), show_unit=False, parent=self,
        )
        self._hanging_indent.value_changed.connect(self._on_rules_edited)
        indent_suffix = QLabel("cm", self)
        indent_suffix.setObjectName("tpl_style_unit")
        self._hanging_indent_row = self._form_row(
            "悬挂缩进",
            self._hanging_indent,
            suffix_widget=indent_suffix,
            parent=self._rules_form,
        )

        self._rules_space_after = SpacingInput(
            unit="pt", min_val=0.0, max_val=40.0, step=1.0,
            decimals=1, units=SPACING_UNIT_OPTIONS, show_unit=True, unit_inline=True, parent=self,
        )
        self._rules_space_after.value_changed.connect(self._on_rules_edited)
        after_suffix = QLabel("", self)
        after_suffix.setObjectName("tpl_style_unit")
        self._rules_space_after_row = self._form_row(
            "条目段后",
            self._rules_space_after,
            suffix_widget=after_suffix,
            parent=self._rules_form,
        )

        self._rules_grid = self._rules_form.add_grid(
            [
                [self._hanging_indent_row, self._rules_space_after_row],
            ]
        )
        self._rules_card.add_widget(self._rules_form)

    # ──────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────

    def _build_emphasis_widget(self) -> QWidget:
        return build_emphasis_widget(
            self,
            self._bold_switch,
            self._italic_switch,
            variant="inline",
            fill=False,
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

    def _set_combo_by_data(self, combo: StyledComboBox, target) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == target:
                combo.setCurrentIndex(index)
                return

    def _is_independent(self) -> bool:
        if self._current_template is None:
            return False
        return is_variant_overridden(self._current_template, _VARIANT_KEY)

    def _editable_style(self) -> StyleConfig | None:
        if self._current_template is None:
            return None
        if not is_variant_overridden(self._current_template, _VARIANT_KEY):
            return enable_variant_override(self._current_template, _VARIANT_KEY)
        return self._current_template.styles.get(_VARIANT_KEY)

    def _style_for_display(self) -> StyleConfig | None:
        if self._current_template is None:
            return None
        return deepcopy(get_effective_style(self._current_template, _VARIANT_KEY))

    # ──────────────────────────────────────────────────────
    # Mode switching
    # ──────────────────────────────────────────────────────

    def _update_mode_visibility(self) -> None:
        independent = self._is_independent()
        with updates_suspended(self._style_container, self):
            self._style_container.setVisible(independent)
            if independent:
                reserve_visible_height(self._style_container)
            self._update_source_summary()
            refresh_layout_chain(self)
        refresh_layout_chain_later(self)

    def _update_source_summary(self) -> None:
        if self._current_template is None:
            self._source_summary.setText("")
            return
        style = self._style_for_display()
        if style is None:
            self._source_summary.setText("")
            return
        mode = "独立设置" if self._is_independent() else "跟随正文"
        size_text = style.size_display or (f"{style.size_pt:g} 磅" if style.size_pt else "默认字号")
        alignment = {
            "left": "左对齐",
            "center": "居中",
            "right": "右对齐",
            "justify": "两端对齐",
        }.get(str(style.alignment or ""), "未设置对齐")
        self._source_summary.setText(
            f"{mode}: {style.font_cn or '-'} / {style.font_en or '-'} / {size_text} / {alignment}"
        )

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
            build_template_detail_summary_items(self._current_template, "tpl_reference")
        )

    def _on_mode_changed(self, index: int) -> None:
        if self._is_syncing or self._current_template is None:
            return

        if index == 1:  # independent
            style = enable_variant_override(self._current_template, _VARIANT_KEY)
            self._sync_style_form(style)
        else:  # follow body
            disable_variant_override(self._current_template, _VARIANT_KEY)

        self._update_mode_visibility()
        self._refresh_summary()
        self._refresh_action_state()
        self.template_edited.emit(self._current_template)

    # ──────────────────────────────────────────────────────
    # Sync UI ↔ Data
    # ──────────────────────────────────────────────────────

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

    def _sync_style_form(self, style: StyleConfig) -> None:
        """Populate all style form controls from the given StyleConfig."""
        self._is_syncing = True
        try:
            self._font_cn.set_font_name(style.font_cn)
            self._font_en.set_font_name(style.font_en)
            self._size_combo.set_pt(style.size_pt)
            self._bold_switch.setChecked(style.bold)
            self._italic_switch.setChecked(style.italic)
            self._set_combo_by_data(self._alignment_combo, style.alignment)

            line_kind = normalize_line_spacing_type(style.line_spacing_type)
            self._set_combo_by_data(self._line_type_combo, line_kind)
            self._sync_line_spacing_editor(
                line_kind,
                resolve_line_spacing_value(line_kind, style.line_spacing_pt),
            )

            self._sync_spacing_editor(self._space_before, resolve_style_paragraph_spacing(style, "before"))
            self._sync_spacing_editor(self._space_after, resolve_style_paragraph_spacing(style, "after"))
        finally:
            self._is_syncing = False

    def _sync_spacing_editor(self, input_widget: SpacingInput, spacing: dict[str, float | str]) -> None:
        unit = str(spacing["unit"])
        config = spacing_editor_config(unit)
        spin = input_widget.spin_box
        spin.setRange(float(config["min"]), float(config["max"]))
        spin.setSingleStep(float(config["step"]))
        spin.setDecimals(int(config["decimals"]))
        input_widget.setEnabled(bool(config["enabled"]))
        input_widget.set_value(float(spacing["value"]), unit)

    def set_template(self, template: TemplateConfig | None) -> None:
        preserve_snapshot = template is self._current_template and self._snapshot is not None
        self._current_template = template
        if template is None:
            self._snapshot = None
            self._refresh_summary()
            self._refresh_action_state()
            return
        if not preserve_snapshot:
            self._snapshot = _ReferenceSnapshot.from_template(template)

        self._is_syncing = True
        try:
            independent = self._is_independent()
            self._mode_combo.setCurrentIndex(1 if independent else 0)
            self._update_mode_visibility()

            if independent:
                style = self._style_for_display()
                if style is not None:
                    self._sync_style_form(style)

            # Rules
            ref = template.reference_style
            self._hanging_indent.set_value(ref.hanging_indent_cm, "cm")
            self._sync_spacing_editor(
                self._rules_space_after,
                {"value": float(getattr(ref, "space_after_pt", 0.0)), "unit": str(getattr(ref, "space_after_unit", "pt"))},
            )
        finally:
            self._is_syncing = False
        self._refresh_summary()
        self._refresh_action_state()

    def capture_entry_snapshot(self) -> None:
        if self._current_template is None:
            self._snapshot = None
        else:
            self._snapshot = _ReferenceSnapshot.from_template(self._current_template)
        self._refresh_action_state()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    # ──────────────────────────────────────────────────────
    # Edit handlers
    # ──────────────────────────────────────────────────────

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

        style.bold = self._bold_switch.isChecked()
        style.italic = self._italic_switch.isChecked()
        style.alignment = str(self._alignment_combo.currentData() or "justify")

        line_kind = normalize_line_spacing_type(self._line_type_combo.currentData() or "exact")
        style.line_spacing_type = line_kind
        style.line_spacing_pt = resolve_line_spacing_value(line_kind, self._line_value.value())
        style.space_before_pt = self._space_before.value()
        style.space_before_unit = self._space_before.unit()
        style.space_after_pt = self._space_after.value()
        style.space_after_unit = self._space_after.unit()

        self._update_source_summary()
        self._refresh_summary()
        self._refresh_action_state()
        self.template_edited.emit(self._current_template)

    def _on_rules_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        ref = self._current_template.reference_style
        ref.hanging_indent_cm = self._hanging_indent.value()
        ref.space_after_pt = self._rules_space_after.value()
        ref.space_after_unit = self._rules_space_after.unit()

        self._refresh_summary()
        self._refresh_action_state()
        self.template_edited.emit(self._current_template)

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
            self._refresh_action_icons()
            return
        current = _ReferenceSnapshot.from_template(self._current_template)
        self._restore_entry_btn.setEnabled(self._snapshot is not None and current != self._snapshot)
        self._save_btn.setEnabled(self._save_enabled)
        self._refresh_action_icons()

    def _refresh_action_icons(self) -> None:
        try:
            from src.shared.ui.icons.catalog import get_icon
        except Exception:
            return

        theme = get_theme()
        restore_color = theme.primary if self._restore_entry_btn.isEnabled() else theme.text_disabled
        save_color = theme.text_on_primary if self._save_btn.isEnabled() else theme.text_disabled
        self._restore_entry_btn.setIcon(get_icon("refresh-ccw", 16, restore_color))
        self._save_btn.setIcon(get_icon("save", 16, save_color))

    # ──────────────────────────────────────────────────────
    # Theme
    # ──────────────────────────────────────────────────────

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(build_button_stylesheet(theme))
        gap = theme.template_detail_section_gap
        self.layout().setSpacing(gap)

        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_lg}px; "
                f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; background: transparent;"
            )
        for widget in self.findChildren(QLabel, "tpl_reference_source_summary"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
            )
        for widget in self.findChildren(QLabel, "tpl_style_help"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
            )
        for widget in self.findChildren(QLabel, "tpl_style_unit"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
            )
        apply_template_summary_action_button(self._restore_entry_btn, "ghost-primary")
        apply_template_summary_action_button(self._save_btn, "primary")

        try:
            from src.shared.ui.icons.catalog import get_icon
            self._summary_card.header.icon_label.setPixmap(
                get_icon("book-open", 28, theme.primary).pixmap(28, 28)
            )
        except Exception:
            self._summary_card.header.icon_label.setText("书")
        self._refresh_action_state()

__all__ = ["ReferenceDetail"]
