"""Caption detail pane for template management."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.style_semantics import SPACING_UNIT_OPTIONS, resolve_style_paragraph_spacing, spacing_editor_config
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QHBoxLayout, QLabel, QLineEdit, QPushButton, QSize, QVBoxLayout, QWidget, QSizePolicy, Signal
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch


NUMBERING_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("chapter", "章节编号"),
    ("global", "全局编号"),
)

NUMBERING_FORMAT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("chapter.seq", "章.序号"),
    ("chapter-seq", "章-序号"),
    ("chapter:seq", "章:序号"),
    ("seq", "纯序号"),
)

ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
)


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
        layout.setSpacing(4)
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
        header_layout.setContentsMargins(0, 0, 0, 6)
        header_layout.setSpacing(6)

        self._header_icon = QLabel(header)
        self._header_icon.setFixedSize(18, 18)
        header_layout.addWidget(self._header_icon)

        title = QLabel("题注", header)
        title.setObjectName("tpl_card_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self._restore_entry_btn = QPushButton("恢复", header)
        self._restore_entry_btn.setIconSize(QSize(16, 16))
        self._restore_entry_btn.clicked.connect(self._on_restore_entry)
        header_layout.addWidget(self._restore_entry_btn)

        self._save_btn = QPushButton("保存", header)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        header_layout.addWidget(self._save_btn)

        self._card.add_widget(header)

        self._desc = QLabel("编辑图表题注前缀、编号方式，以及共享题注样式。")
        self._desc.setObjectName("tpl_caption_desc")
        self._desc.setWordWrap(True)
        self._card.add_widget(self._desc)

    def _build_form(self) -> None:
        rows = []

        self._figure_prefix_edit = QLineEdit(self)
        self._figure_prefix_edit.textChanged.connect(self._on_form_edited)
        rows.append(template_form_row("图前缀", self._figure_prefix_edit, parent=self._card))

        self._table_prefix_edit = QLineEdit(self)
        self._table_prefix_edit.textChanged.connect(self._on_form_edited)
        rows.append(template_form_row("表前缀", self._table_prefix_edit, parent=self._card))

        self._separator_edit = QLineEdit(self)
        self._separator_edit.textChanged.connect(self._on_form_edited)
        rows.append(template_form_row("分隔符", self._separator_edit, parent=self._card))

        self._placeholder_edit = QLineEdit(self)
        self._placeholder_edit.textChanged.connect(self._on_form_edited)
        rows.append(template_form_row("占位文本", self._placeholder_edit, parent=self._card))

        self._numbering_mode_combo = StyledComboBox(self)
        for value, label in NUMBERING_MODE_OPTIONS:
            self._numbering_mode_combo.addItem(label, value)
        self._numbering_mode_combo.currentIndexChanged.connect(self._on_form_edited)
        rows.append(template_form_row("编号模式", self._numbering_mode_combo, parent=self._card))

        self._numbering_format_combo = StyledComboBox(self)
        for value, label in NUMBERING_FORMAT_OPTIONS:
            self._numbering_format_combo.addItem(label, value)
        self._numbering_format_combo.currentIndexChanged.connect(self._on_form_edited)
        rows.append(template_form_row("编号格式", self._numbering_format_combo, parent=self._card))

        self._auto_insert_toggle = ToggleSwitch(self, checked=True)
        self._auto_insert_toggle.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("自动补题注", self._auto_insert_toggle, parent=self._card))

        self._format_inserted_toggle = ToggleSwitch(self, checked=False)
        self._format_inserted_toggle.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("域代码编号", self._format_inserted_toggle, parent=self._card))

        self._font_cn_combo = FontCombo(lang="cn", parent=self)
        self._font_cn_combo.font_changed.connect(self._on_form_edited)
        rows.append(template_form_row("中文字体", self._font_cn_combo, parent=self._card))

        self._font_en_combo = FontCombo(lang="en", parent=self)
        self._font_en_combo.font_changed.connect(self._on_form_edited)
        rows.append(template_form_row("英文字体", self._font_en_combo, parent=self._card))

        self._size_combo = SizeCombo(self)
        self._size_combo.size_changed.connect(self._on_form_edited)
        self._size_combo.currentTextChanged.connect(self._on_form_edited)
        rows.append(template_form_row("字号", self._size_combo, parent=self._card))

        self._alignment_combo = StyledComboBox(self)
        for value, label in ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(label, value)
        self._alignment_combo.currentIndexChanged.connect(self._on_form_edited)
        rows.append(template_form_row("题注对齐", self._alignment_combo, parent=self._card))

        self._space_before_input = SpacingInput(unit="pt", min_val=0.0, max_val=40.0, step=1.0, decimals=1, units=SPACING_UNIT_OPTIONS, show_unit=True, unit_inline=True, parent=self)
        self._space_before_input.value_changed.connect(self._on_form_edited)
        rows.append(template_form_row("段前", self._space_before_input, suffix_widget=QLabel("", self), parent=self._card))

        self._space_after_input = SpacingInput(unit="pt", min_val=0.0, max_val=40.0, step=1.0, decimals=1, units=SPACING_UNIT_OPTIONS, show_unit=True, unit_inline=True, parent=self)
        self._space_after_input.value_changed.connect(self._on_form_edited)
        rows.append(template_form_row("段后", self._space_after_input, suffix_widget=QLabel("", self), parent=self._card))
        self._card.add_widget(TemplateFormStack(rows, parent=self._card))

    def _build_hint(self) -> None:
        self._footer_note = QLabel("当前编辑的是共享 caption 样式；图/表独立题注样式后续再细化。")
        self._footer_note.setObjectName("tpl_caption_footer")
        self._footer_note.setWordWrap(True)
        self._card.add_widget(self._footer_note)

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
            return
        if not preserve_snapshot:
            self._snapshot = _CaptionSnapshot.from_template(template)
        self._is_syncing = True
        try:
            caption = template.caption
            style = template.styles.get("caption") or template.styles.get("body") or template.styles.get("normal") or StyleConfig()
            self._figure_prefix_edit.setText(caption.figure_prefix)
            self._table_prefix_edit.setText(caption.table_prefix)
            self._separator_edit.setText(caption.separator)
            self._placeholder_edit.setText(caption.placeholder)
            self._set_combo_by_data(self._numbering_mode_combo, caption.numbering_mode)
            self._set_combo_by_data(self._numbering_format_combo, caption.numbering_format)
            self._auto_insert_toggle.setChecked(caption.auto_insert)
            self._format_inserted_toggle.setChecked(caption.format_inserted)
            self._font_cn_combo.set_font_name(style.font_cn or "")
            self._font_en_combo.set_font_name(style.font_en or "")
            self._size_combo.set_pt(style.size_pt or 12.0)
            self._set_combo_by_data(self._alignment_combo, style.alignment)
            self._sync_spacing_input(self._space_before_input, resolve_style_paragraph_spacing(style, "before"))
            self._sync_spacing_input(self._space_after_input, resolve_style_paragraph_spacing(style, "after"))
        finally:
            self._is_syncing = False
        self._refresh_action_state()

    def _sync_spacing_input(self, widget: SpacingInput, spacing: dict[str, float | str]) -> None:
        unit = str(spacing["unit"])
        config = spacing_editor_config(unit)
        spin = widget.spin_box
        spin.setRange(float(config["min"]), float(config["max"]))
        spin.setSingleStep(float(config["step"]))
        spin.setDecimals(int(config["decimals"]))
        widget.setEnabled(bool(config["enabled"]))
        widget.set_value(float(spacing["value"]), unit)

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
        caption.auto_insert = self._auto_insert_toggle.isChecked()
        caption.format_inserted = self._format_inserted_toggle.isChecked()

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
        style.alignment = str(self._alignment_combo.currentData() or "center")
        style.space_before_pt = self._space_before_input.value()
        style.space_before_unit = self._space_before_input.unit()
        style.space_after_pt = self._space_after_input.value()
        style.space_after_unit = self._space_after_input.unit()

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
            return
        current = _CaptionSnapshot.from_template(self._current_template)
        self._restore_entry_btn.setEnabled(self._snapshot is not None and current != self._snapshot)
        self._save_btn.setEnabled(self._save_enabled)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(build_button_stylesheet(theme))
        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_lg}px; "
                f"font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; background: transparent;"
            )
        self._desc.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
        self._footer_note.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")

        line_edit_style = build_text_input_stylesheet(theme, selector="QLineEdit")
        for widget in (self._figure_prefix_edit, self._table_prefix_edit, self._separator_edit, self._placeholder_edit):
            widget.setStyleSheet(line_edit_style)

        apply_button_variant(self._restore_entry_btn, "ghost-primary")
        apply_button_variant(self._save_btn, "primary")

        try:
            from src.ui.icons.catalog import get_icon

            self._header_icon.setPixmap(get_icon("image-plus", 18, theme.primary).pixmap(18, 18))
            self._restore_entry_btn.setIcon(get_icon("refresh-ccw", 16, theme.primary if self._restore_entry_btn.isEnabled() else theme.text_disabled))
            self._save_btn.setIcon(get_icon("save", 16, theme.text_on_primary if self._save_btn.isEnabled() else theme.text_disabled))
        except Exception:
            self._header_icon.setText("题")


__all__ = ["CaptionDetail"]
