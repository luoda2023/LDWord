"""Reusable paragraph style editor shared by template and scene owners."""

from __future__ import annotations

from src.config.style_semantics import (
    LINE_SPACING_OPTIONS,
    SPACING_UNIT_OPTIONS,
    apply_style_special_indent,
    display_font_size_with_name,
    line_spacing_is_editable,
    line_spacing_unit_label,
    normalize_line_spacing_type,
    resolve_line_spacing_value,
    resolve_style_paragraph_spacing,
    resolve_style_special_indent,
    spacing_editor_config,
)
from src.config.template import StyleConfig
from src.config.style_field_descriptors import (
    STYLE_FIELD_ALIASES,
    STYLE_FIELD_WIDGET_ATTRS,
    canonical_paragraph_style_field_id,
    style_field_layout_rows,
    style_field_widget_attr,
)
from src.qt_api import QLabel, QSizePolicy, QVBoxLayout, QWidget, Signal
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.paragraph_style_inputs import IndentInput, SpecialIndentInput
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import (
    TemplateFormStack,
    template_form_pair_row,
    template_form_row,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.typography_controls import build_emphasis_widget


ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
    ("justify", "两端对齐"),
)


_UNSET = object()


def _set_combo_by_data(combo: StyledComboBox, target) -> None:
    normalized_target = "" if target in (None, "") else str(target)
    for index in range(combo.count()):
        current = combo.itemData(index)
        normalized_current = "" if current in (None, "") else str(current)
        if normalized_current == normalized_target:
            combo.setCurrentIndex(index)
            return


class ParagraphStyleEditor(QWidget):
    """Edit a StyleConfig without owning where that style is stored."""

    style_changed = Signal()

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "paragraph_style",
        build_layout: bool = True,
    ) -> None:
        super().__init__(parent)
        self._is_syncing = False
        self._editable = True
        self._unit_labels: list[QLabel] = []

        layout = None
        if build_layout:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._build_controls(object_name_prefix)
        self._rows = ()
        if layout is not None:
            self._build_layout(layout)
        self.set_editable(True)
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def font_cn(self) -> FontCombo:
        return self._font_cn

    @property
    def font_en(self) -> FontCombo:
        return self._font_en

    @property
    def size_combo(self) -> SizeCombo:
        return self._size_combo

    @property
    def bold_switch(self) -> ToggleSwitch:
        return self._bold_switch

    @property
    def italic_switch(self) -> ToggleSwitch:
        return self._italic_switch

    @property
    def emphasis_widget(self) -> QWidget:
        return self._emphasis

    @property
    def alignment_combo(self) -> StyledComboBox:
        return self._alignment_combo

    @property
    def special_indent(self) -> SpecialIndentInput:
        return self._special_indent

    @property
    def left_indent(self) -> IndentInput:
        return self._left_indent

    @property
    def right_indent(self) -> IndentInput:
        return self._right_indent

    @property
    def line_type_combo(self) -> StyledComboBox:
        return self._line_type_combo

    @property
    def line_value(self) -> SpacingInput:
        return self._line_value

    @property
    def line_value_suffix(self) -> QLabel:
        return self._line_value_suffix

    @property
    def space_before(self) -> SpacingInput:
        return self._space_before

    @property
    def space_after(self) -> SpacingInput:
        return self._space_after

    def _build_controls(self, object_name_prefix: str) -> None:
        prefix = str(object_name_prefix or "paragraph_style").strip()

        self._font_cn = FontCombo(lang="cn", parent=self)
        self._font_cn.setObjectName(f"{prefix}_font_cn")
        self._font_cn.font_changed.connect(self._emit_style_changed)

        self._font_en = FontCombo(lang="en", parent=self)
        self._font_en.setObjectName(f"{prefix}_font_en")
        self._font_en.font_changed.connect(self._emit_style_changed)

        self._size_combo = SizeCombo(self)
        self._size_combo.setObjectName(f"{prefix}_size")
        self._size_combo.size_changed.connect(self._on_size_changed)
        self._size_combo.currentTextChanged.connect(self._emit_style_changed)

        self._bold_switch = ToggleSwitch(self, checked=False)
        self._bold_switch.setObjectName(f"{prefix}_bold")
        self._bold_switch.toggled_signal.connect(self._emit_style_changed)

        self._italic_switch = ToggleSwitch(self, checked=False)
        self._italic_switch.setObjectName(f"{prefix}_italic")
        self._italic_switch.toggled_signal.connect(self._emit_style_changed)

        self._emphasis = build_emphasis_widget(
            self,
            self._bold_switch,
            self._italic_switch,
            spacing=10,
        )

        self._alignment_combo = StyledComboBox(self)
        self._alignment_combo.setObjectName(f"{prefix}_alignment")
        self._alignment_combo.setSizeAdjustPolicy(
            self._alignment_combo.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        for value, label in ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(label, value)
        self._alignment_combo.currentIndexChanged.connect(self._emit_style_changed)

        self._special_indent = SpecialIndentInput(self, reference_size_pt=12.0)
        self._special_indent.setObjectName(f"{prefix}_special_indent")
        self._special_indent.value_changed.connect(self._emit_style_changed)

        self._left_indent = IndentInput(self, reference_size_pt=12.0)
        self._left_indent.setObjectName(f"{prefix}_left_indent")
        self._left_indent.value_changed.connect(self._emit_style_changed)

        self._right_indent = IndentInput(self, reference_size_pt=12.0)
        self._right_indent.setObjectName(f"{prefix}_right_indent")
        self._right_indent.value_changed.connect(self._emit_style_changed)

        self._line_type_combo = StyledComboBox(self)
        self._line_type_combo.setObjectName(f"{prefix}_line_spacing_type")
        self._line_type_combo.setSizeAdjustPolicy(
            self._line_type_combo.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        for value, label in LINE_SPACING_OPTIONS:
            self._line_type_combo.addItem(label, value)
        self._line_type_combo.currentIndexChanged.connect(
            self._on_line_spacing_type_changed
        )

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
        self._line_value.setObjectName(f"{prefix}_line_spacing_value")
        self._line_value.value_changed.connect(self._emit_style_changed)
        self._line_value_suffix = QLabel("磅", self)
        self._line_value_suffix.setObjectName(f"{prefix}_line_spacing_unit")
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
        self._space_before.setObjectName(f"{prefix}_space_before")
        self._space_before.value_changed.connect(self._emit_style_changed)

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
        self._space_after.setObjectName(f"{prefix}_space_after")
        self._space_after.value_changed.connect(self._emit_style_changed)

    def _build_layout(self, layout: QVBoxLayout) -> None:
        created_rows: list[QWidget] = []
        pair_rows: list[QWidget] = []
        for group_id in ("text", "alignment_indent", "spacing"):
            for row_items in style_field_layout_rows(group_id):
                rows = [
                    template_form_row(
                        item.label,
                        self._layout_widget_for_item(item.item_id),
                        suffix_widget=(
                            self._line_value_suffix
                            if item.item_id == "line_spacing_pt"
                            else None
                        ),
                        parent=self,
                    )
                    for item in row_items
                ]
                created_rows.extend(rows)
                if len(rows) == 2:
                    pair_rows.append(
                        template_form_pair_row(rows[0], rows[1], parent=self)
                    )
                else:
                    pair_rows.extend(rows)

        self._rows = tuple(created_rows)
        layout.addWidget(
            TemplateFormStack(
                pair_rows,
                parent=self,
            )
        )

    def _layout_widget_for_item(self, item_id: str) -> QWidget:
        widgets = {
            "font_cn": self._font_cn,
            "size_pt": self._size_combo,
            "font_en": self._font_en,
            "emphasis": self._emphasis,
            "alignment": self._alignment_combo,
            "special_indent": self._special_indent,
            "left_indent": self._left_indent,
            "right_indent": self._right_indent,
            "line_spacing_type": self._line_type_combo,
            "line_spacing_pt": self._line_value,
            "space_before": self._space_before,
            "space_after": self._space_after,
        }
        widget = widgets.get(str(item_id or "").strip())
        if widget is None:
            raise KeyError(f"Unknown paragraph style layout item: {item_id}")
        return widget

    def set_style(self, style: StyleConfig | None) -> None:
        self._is_syncing = True
        try:
            if style is None:
                self.set_editable(False)
                return

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

            self._sync_spacing_editor(
                self._space_before,
                resolve_style_paragraph_spacing(style, "before"),
            )
            self._sync_spacing_editor(
                self._space_after,
                resolve_style_paragraph_spacing(style, "after"),
            )
        finally:
            self._is_syncing = False
        self._refresh_enabled_state()

    def apply_to_style(self, style: StyleConfig) -> None:
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

        line_kind = normalize_line_spacing_type(
            self._line_type_combo.currentData() or "exact"
        )
        style.line_spacing_type = line_kind
        style.line_spacing_pt = resolve_line_spacing_value(
            line_kind,
            self._line_value.value(),
        )
        style.space_before_pt = self._space_before.value()
        style.space_before_unit = self._space_before.unit()
        style.space_after_pt = self._space_after.value()
        style.space_after_unit = self._space_after.unit()

    def set_values(
        self,
        *,
        font_cn: object = _UNSET,
        font_en: object = _UNSET,
        size_pt: object = _UNSET,
        bold: object = _UNSET,
        italic: object = _UNSET,
        alignment: object = _UNSET,
        special_indent: object = _UNSET,
        left_indent: object = _UNSET,
        right_indent: object = _UNSET,
        line_spacing_type: object = _UNSET,
        line_spacing_pt: object = _UNSET,
        space_before: object = _UNSET,
        space_after: object = _UNSET,
    ) -> None:
        was_syncing = self._is_syncing
        self._is_syncing = True
        try:
            if font_cn is not _UNSET:
                self._font_cn.set_font_name(str(font_cn or ""))
            if font_en is not _UNSET:
                self._font_en.set_font_name(str(font_en or ""))
            if size_pt is not _UNSET:
                pt = float(size_pt)
                self._size_combo.set_pt(pt)
                self._special_indent.set_reference_size(pt)
                self._left_indent.set_reference_size(pt)
                self._right_indent.set_reference_size(pt)
            if bold is not _UNSET:
                self._bold_switch.setChecked(bool(bold))
            if italic is not _UNSET:
                self._italic_switch.setChecked(bool(italic))
            if alignment is not _UNSET:
                _set_combo_by_data(self._alignment_combo, alignment)
            if special_indent is not _UNSET:
                mode, value, unit = special_indent
                self._special_indent.set_value(str(mode), float(value), str(unit))
            if left_indent is not _UNSET:
                value, unit = left_indent
                self._left_indent.set_value(float(value), str(unit))
            if right_indent is not _UNSET:
                value, unit = right_indent
                self._right_indent.set_value(float(value), str(unit))
            if line_spacing_type is not _UNSET:
                _set_combo_by_data(self._line_type_combo, line_spacing_type)
            if line_spacing_type is not _UNSET or line_spacing_pt is not _UNSET:
                line_kind = normalize_line_spacing_type(
                    self._line_type_combo.currentData() or "exact"
                )
                value = (
                    float(line_spacing_pt)
                    if line_spacing_pt is not _UNSET
                    else resolve_line_spacing_value(line_kind, self._line_value.value())
                )
                self._sync_line_spacing_editor(line_kind, value)
            if space_before is not _UNSET:
                value, unit = space_before
                self._space_before.set_value(float(value), str(unit))
            if space_after is not _UNSET:
                value, unit = space_after
                self._space_after.set_value(float(value), str(unit))
        finally:
            self._is_syncing = was_syncing
        self._refresh_enabled_state()
        if not was_syncing:
            self.style_changed.emit()

    def set_editable(self, enabled: bool) -> None:
        self._editable = bool(enabled)
        self._refresh_enabled_state()

    def widget_for_field(self, field_id: str) -> QWidget | None:
        attr_name = style_field_widget_attr(field_id)
        if not attr_name:
            return None
        return getattr(self, attr_name, None)

    def widget_for_layout_item(self, item_id: str) -> QWidget | None:
        try:
            return self._layout_widget_for_item(item_id)
        except KeyError:
            return None

    def focus_field(self, field_id: str) -> bool:
        widget = self.widget_for_field(field_id)
        if widget is None:
            return False
        widget.setFocus()
        return True

    def _sync_spacing_editor(
        self,
        input_widget: SpacingInput,
        spacing: dict[str, float | str],
    ) -> None:
        unit = str(spacing["unit"])
        config = spacing_editor_config(unit)
        spin = input_widget.spin_box
        spin.setRange(float(config["min"]), float(config["max"]))
        spin.setSingleStep(float(config["step"]))
        spin.setDecimals(int(config["decimals"]))
        input_widget.set_value(float(spacing["value"]), unit)

    def _sync_line_spacing_editor(self, line_kind: str, value: float) -> None:
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
        self._line_value.set_value(value, "pt")

    def _on_size_changed(self, pt: float) -> None:
        if self._is_syncing:
            return
        self._special_indent.set_reference_size(pt)
        self._left_indent.set_reference_size(pt)
        self._right_indent.set_reference_size(pt)
        self._emit_style_changed()

    def _on_line_spacing_type_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        line_kind = normalize_line_spacing_type(
            self._line_type_combo.currentData() or "exact"
        )
        value = resolve_line_spacing_value(line_kind, self._line_value.value())
        self._is_syncing = True
        try:
            self._sync_line_spacing_editor(line_kind, value)
        finally:
            self._is_syncing = False
        self._refresh_enabled_state()
        self._emit_style_changed()

    def _refresh_enabled_state(self) -> None:
        enabled = self._editable
        for widget in (
            self._font_cn,
            self._font_en,
            self._size_combo,
            self._bold_switch,
            self._italic_switch,
            self._emphasis,
            self._alignment_combo,
            self._special_indent,
            self._left_indent,
            self._right_indent,
            self._line_type_combo,
        ):
            widget.setEnabled(enabled)

        self._space_before.setEnabled(enabled and self._space_before.unit() != "auto")
        self._space_after.setEnabled(enabled and self._space_after.unit() != "auto")
        line_kind = normalize_line_spacing_type(
            self._line_type_combo.currentData() or "exact"
        )
        self._line_value.setEnabled(enabled and line_spacing_is_editable(line_kind))

    def _emit_style_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        self._refresh_enabled_state()
        self.style_changed.emit()

    def _apply_theme(self) -> None:
        t = get_theme()
        unit_ss = f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        for label in self._unit_labels:
            label.setStyleSheet(unit_ss)


__all__ = [
    "ALIGNMENT_OPTIONS",
    "ParagraphStyleEditor",
    "STYLE_FIELD_ALIASES",
    "STYLE_FIELD_WIDGET_ATTRS",
    "canonical_paragraph_style_field_id",
]
