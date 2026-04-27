"""TOC section for the template elements detail pane."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from src.config.style_semantics import (
    LINE_SPACING_OPTIONS,
    SPACING_UNIT_OPTIONS,
    display_font_size_with_name,
    line_spacing_is_editable,
    line_spacing_unit_label,
    normalize_line_spacing_type,
    resolve_line_spacing_value,
    resolve_style_paragraph_spacing,
    spacing_editor_config,
)
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QLabel, QLineEdit, QWidget
from src.shared.engine.toc_style_ops import resolve_toc_style_config
from src.shared.ui.card import Card
from src.shared.ui.flow_section import FlowSection
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import TemplateFormGrid, template_form_row
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.typography_controls import build_emphasis_widget

if TYPE_CHECKING:
    from src.ui.panels.template_elements_detail import ElementsDetail


TOC_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("word_native", "Word 自动目录"),
    ("plain", "普通目录"),
)

TOC_INSERT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("auto", "自动"),
    ("after_cover", "封面后"),
    ("0", "文档起始"),
)

TOC_ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
    ("justify", "两端对齐"),
)

TOC_STYLE_META: tuple[tuple[str, str, bool], ...] = (
    ("toc", "目录共享样式", True),
    ("toc_title", "目录标题样式", False),
    ("toc_chapter", "章级目录样式", False),
    ("toc_level1", "一级目录样式", False),
    ("toc_level2", "二级目录样式", False),
)

TOC_STYLE_KEYS = tuple(role for role, _, _ in TOC_STYLE_META)


def _set_combo_by_data(combo: StyledComboBox, target) -> None:
    for index in range(combo.count()):
        if combo.itemData(index) == target:
            combo.setCurrentIndex(index)
            return


class TocDetailSection:
    """Owns TOC structure and TOC style controls inside ElementsDetail."""

    def __init__(self, owner: "ElementsDetail"):
        self._owner = owner
        self._toc_style_controls: dict[str, dict[str, object]] = {}

        self.structure_section = Card(parent=owner._editor_column)
        self._toc_section = self.structure_section
        owner._toc_section = self.structure_section
        owner._add_card_header(self.structure_section, "scroll-text", "目录结构")
        owner._editor_layout.addWidget(self.structure_section)
        self._build_toc_form()

        self.styles_section = Card(parent=owner._editor_column)
        self._toc_styles_section = self.styles_section
        owner._toc_styles_section = self.styles_section
        owner._add_card_header(self.styles_section, "type-outline", "目录样式")
        owner._editor_layout.addWidget(self.styles_section)
        self._build_toc_style_form()

        self._export_compat_attributes()

    def _export_compat_attributes(self) -> None:
        names = (
            "_toc_enabled_toggle",
            "_toc_enabled_row",
            "_toc_mode_combo",
            "_toc_mode_row",
            "_toc_depth_combo",
            "_toc_depth_row",
            "_toc_insert_combo",
            "_toc_insert_row",
            "_toc_styles_section",
            "_toc_style_controls",
        )
        for name in names:
            setattr(self._owner, name, getattr(self, name))

    def _build_toc_form(self) -> None:
        self._toc_enabled_toggle = ToggleSwitch(self._owner, checked=True)
        self._toc_enabled_toggle.toggled_signal.connect(self._owner._on_structure_edited)
        self._toc_enabled_row = self._form_row("启用目录", self._toc_enabled_toggle, parent=self.structure_section)
        self.structure_section.add_widget(self._toc_enabled_row)

        self._toc_mode_combo = StyledComboBox(self._owner)
        for value, label in TOC_MODE_OPTIONS:
            self._toc_mode_combo.addItem(label, value)
        self._toc_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._toc_mode_row = self._form_row("目录模式", self._toc_mode_combo, parent=self.structure_section)
        self.structure_section.add_widget(self._toc_mode_row)

        self._toc_depth_combo = StyledComboBox(self._owner)
        for level in range(1, 7):
            self._toc_depth_combo.addItem(f"{level} 级", level)
        self._toc_depth_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._toc_depth_row = self._form_row("目录深度", self._toc_depth_combo, parent=self.structure_section)
        self.structure_section.add_widget(self._toc_depth_row)

        self._toc_insert_combo = StyledComboBox(self._owner)
        for value, label in TOC_INSERT_OPTIONS:
            self._toc_insert_combo.addItem(label, value)
        self._toc_insert_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._toc_insert_row = self._form_row("插入位置", self._toc_insert_combo, parent=self.structure_section)
        self.structure_section.add_widget(self._toc_insert_row)

    def _build_toc_style_form(self) -> None:
        for role_key, title, expanded in TOC_STYLE_META:
            self.styles_section.add_widget(
                self._build_single_toc_style_section(role_key, title, expanded=expanded)
            )

    def _build_single_toc_style_section(self, role_key: str, title: str, *, expanded: bool) -> FlowSection:
        section = FlowSection(title, expanded=expanded, parent=self.styles_section)

        font_cn = FontCombo(lang="cn", parent=self._owner)
        font_cn.font_changed.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))

        font_en = FontCombo(lang="en", parent=self._owner)
        font_en.font_changed.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))

        size_combo = SizeCombo(self._owner)
        size_combo.size_changed.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))
        size_combo.currentTextChanged.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))

        bold_toggle = ToggleSwitch(self._owner, checked=False)
        bold_toggle.toggled_signal.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))
        italic_toggle = ToggleSwitch(self._owner, checked=False)
        italic_toggle.toggled_signal.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))

        alignment_combo = StyledComboBox(self._owner)
        for value, label in TOC_ALIGNMENT_OPTIONS:
            alignment_combo.addItem(label, value)
        alignment_combo.currentIndexChanged.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))

        line_type_combo = StyledComboBox(self._owner)
        for value, label in LINE_SPACING_OPTIONS:
            line_type_combo.addItem(label, value)
        line_type_combo.currentIndexChanged.connect(
            lambda *_args, role=role_key: self._on_toc_line_spacing_type_changed(role)
        )

        line_value = SpacingInput(
            unit="pt",
            min_val=0.5,
            max_val=60.0,
            step=0.5,
            decimals=1,
            units=("pt",),
            show_unit=False,
            parent=self._owner,
        )
        line_value.value_changed.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))
        line_suffix = QLabel("pt", self._owner)
        line_suffix.setObjectName("tpl_style_unit")

        space_before = SpacingInput(
            unit="pt",
            min_val=0.0,
            max_val=80.0,
            step=1.0,
            decimals=1,
            units=SPACING_UNIT_OPTIONS,
            show_unit=True,
            unit_inline=True,
            parent=self._owner,
        )
        space_before.value_changed.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))

        space_after = SpacingInput(
            unit="pt",
            min_val=0.0,
            max_val=80.0,
            step=1.0,
            decimals=1,
            units=SPACING_UNIT_OPTIONS,
            show_unit=True,
            unit_inline=True,
            parent=self._owner,
        )
        space_after.value_changed.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))

        left_indent = SpacingInput(
            unit="chars",
            min_val=0.0,
            max_val=10.0,
            step=0.5,
            decimals=1,
            units=("chars",),
            show_unit=False,
            parent=self._owner,
        )
        left_indent.value_changed.connect(lambda *_args, role=role_key: self._on_toc_style_edited(role))
        indent_suffix = QLabel("字", self._owner)
        indent_suffix.setObjectName("tpl_style_unit")

        emphasis_widget = build_emphasis_widget(self._owner, bold_toggle, italic_toggle)

        section.add_widget(
            TemplateFormGrid(
                [
                    (
                        self._form_row("中文字体", font_cn, parent=section),
                        self._form_row("英文字体", font_en, parent=section),
                    ),
                    (
                        self._form_row("字号", size_combo, parent=section),
                        self._form_row("字形", emphasis_widget, parent=section),
                    ),
                    (
                        self._form_row("对齐", alignment_combo, parent=section),
                        self._form_row("左缩进", left_indent, suffix_widget=indent_suffix, parent=section),
                    ),
                    (
                        self._form_row("行距类型", line_type_combo, parent=section),
                        self._form_row("行距值", line_value, suffix_widget=line_suffix, parent=section),
                    ),
                    (
                        self._form_row("段前", space_before, parent=section),
                        self._form_row("段后", space_after, parent=section),
                    ),
                ],
                parent=self._owner,
            )
        )

        self._toc_style_controls[role_key] = {
            "section": section,
            "font_cn": font_cn,
            "font_en": font_en,
            "size": size_combo,
            "bold": bold_toggle,
            "italic": italic_toggle,
            "alignment": alignment_combo,
            "line_type": line_type_combo,
            "line_value": line_value,
            "line_suffix": line_suffix,
            "space_before": space_before,
            "space_after": space_after,
            "left_indent": left_indent,
        }
        return section

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
        return TemplateFormGrid([widgets], parent=self._owner)

    def effective_style(self, role_key: str) -> StyleConfig:
        template = self._owner._current_template
        if template is None:
            return StyleConfig()
        return deepcopy(
            resolve_toc_style_config(template.styles, role_key)
            or template.styles.get("body")
            or template.styles.get("normal")
            or StyleConfig()
        )

    def _ensure_style(self, role_key: str) -> StyleConfig:
        template = self._owner._current_template
        if template is None:
            return StyleConfig()
        style = template.styles.get(role_key)
        if style is None:
            style = self.effective_style(role_key)
            template.styles[role_key] = style
        return style

    def _sync_line_spacing_editor(self, role_key: str, line_kind: str, value: float) -> None:
        controls = self._toc_style_controls[role_key]
        line_value = controls["line_value"]
        spin = line_value.spin_box
        if line_kind == "exact":
            spin.setRange(1.0, 80.0)
            spin.setSingleStep(1.0)
            spin.setDecimals(1)
        else:
            spin.setRange(0.5, 5.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(1)
        line_value.setEnabled(line_spacing_is_editable(line_kind))
        line_value.set_value(value, "pt")
        controls["line_suffix"].setText(line_spacing_unit_label(line_kind))

    def _sync_style_form(self, role_key: str, style: StyleConfig) -> None:
        controls = self._toc_style_controls[role_key]
        controls["font_cn"].set_font_name(style.font_cn or "")
        controls["font_en"].set_font_name(style.font_en or "")
        controls["size"].set_pt(style.size_pt or 12.0)
        controls["bold"].setChecked(bool(style.bold))
        controls["italic"].setChecked(bool(style.italic))
        _set_combo_by_data(controls["alignment"], style.alignment or "left")

        line_kind = normalize_line_spacing_type(style.line_spacing_type)
        _set_combo_by_data(controls["line_type"], line_kind)
        self._sync_line_spacing_editor(
            role_key,
            line_kind,
            resolve_line_spacing_value(line_kind, style.line_spacing_pt),
        )

        self._sync_spacing_editor(controls["space_before"], resolve_style_paragraph_spacing(style, "before"))
        self._sync_spacing_editor(controls["space_after"], resolve_style_paragraph_spacing(style, "after"))
        controls["left_indent"].set_value(style.left_indent_chars, "chars")

    def _sync_spacing_editor(self, input_widget: SpacingInput, spacing: dict[str, float | str]) -> None:
        unit = str(spacing["unit"])
        config = spacing_editor_config(unit)
        spin = input_widget.spin_box
        spin.setRange(float(config["min"]), float(config["max"]))
        spin.setSingleStep(float(config["step"]))
        spin.setDecimals(int(config["decimals"]))
        input_widget.setEnabled(bool(config["enabled"]))
        input_widget.set_value(float(spacing["value"]), unit)

    def _on_toc_line_spacing_type_changed(self, role_key: str) -> None:
        owner = self._owner
        if owner._is_syncing:
            return
        controls = self._toc_style_controls[role_key]
        line_kind = normalize_line_spacing_type(controls["line_type"].currentData() or "multiple")
        value = resolve_line_spacing_value(line_kind, controls["line_value"].value())

        owner._is_syncing = True
        try:
            self._sync_line_spacing_editor(role_key, line_kind, value)
        finally:
            owner._is_syncing = False

        self._on_toc_style_edited(role_key)

    def _on_toc_style_edited(self, role_key: str) -> None:
        owner = self._owner
        if owner._is_syncing or owner._current_template is None:
            return

        controls = self._toc_style_controls[role_key]
        style = self._ensure_style(role_key)

        style.font_cn = controls["font_cn"].selected_font()
        style.font_en = controls["font_en"].selected_font()

        pt = controls["size"].current_pt()
        if pt is not None:
            style.size_pt = pt
            style.size_display = display_font_size_with_name(pt)

        style.bold = controls["bold"].isChecked()
        style.italic = controls["italic"].isChecked()
        style.alignment = str(controls["alignment"].currentData() or "left")

        line_kind = normalize_line_spacing_type(controls["line_type"].currentData() or "multiple")
        style.line_spacing_type = line_kind
        style.line_spacing_pt = resolve_line_spacing_value(line_kind, controls["line_value"].value())

        style.space_before_pt = controls["space_before"].value()
        style.space_before_unit = controls["space_before"].unit()
        style.space_after_pt = controls["space_after"].value()
        style.space_after_unit = controls["space_after"].unit()
        style.left_indent_chars = controls["left_indent"].value()
        style.left_indent_unit = "chars"
        style.right_indent_chars = 0.0
        style.right_indent_unit = "chars"
        style.first_line_indent_chars = 0.0
        style.first_line_indent_unit = "chars"
        style.hanging_indent_chars = 0.0
        style.hanging_indent_unit = "chars"
        style.special_indent_mode = "none"
        style.special_indent_value = 0.0
        style.special_indent_unit = "chars"

        owner._refresh_summary()
        owner._refresh_action_state()
        owner.template_edited.emit(owner._current_template)

    def clear(self) -> None:
        self.sync_dependent_state()

    def set_template(self, template: TemplateConfig) -> None:
        toc = template.toc
        self._toc_enabled_toggle.setChecked(toc.enabled)
        _set_combo_by_data(self._toc_mode_combo, toc.mode)
        _set_combo_by_data(self._toc_depth_combo, toc.max_level)
        _set_combo_by_data(self._toc_insert_combo, toc.insert_position)

        for role_key in TOC_STYLE_KEYS:
            self._sync_style_form(role_key, self.effective_style(role_key))

    def apply_to(self, toc) -> None:
        toc.enabled = self._toc_enabled_toggle.isChecked()
        toc.mode = str(self._toc_mode_combo.currentData() or "word_native")
        toc.max_level = int(self._toc_depth_combo.currentData() or 3)
        toc.insert_position = str(self._toc_insert_combo.currentData() or "auto")

    def sync_dependent_state(self) -> None:
        toc_enabled = self._toc_enabled_toggle.isChecked()
        self._toc_mode_row.setEnabled(toc_enabled)
        self._toc_depth_row.setEnabled(toc_enabled)
        self._toc_insert_row.setEnabled(toc_enabled)
        self.styles_section.setVisible(toc_enabled)
        self.styles_section.setEnabled(toc_enabled)


__all__ = [
    "TOC_INSERT_OPTIONS",
    "TOC_MODE_OPTIONS",
    "TOC_STYLE_KEYS",
    "TocDetailSection",
]
