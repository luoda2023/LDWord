"""Formula detail pane for template management."""

from __future__ import annotations

from src.config.template import TemplateConfig
from src.qt_api import QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy, Signal
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._is_syncing = False
        self._custom_numbering_value: str | None = None

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
        title = QLabel("公式规范", header)
        title.setObjectName("tpl_card_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self._card.add_widget(header)

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

        self._numbering_combo = StyledComboBox(self)
        for value, label in _NUMBERING_OPTIONS:
            self._numbering_combo.addItem(label, value)
        self._numbering_combo.currentIndexChanged.connect(self._on_form_edited)
        rows.append(template_form_row("编号方式", self._numbering_combo, parent=self._card))

        self._unify_font = ToggleSwitch(self, checked=True)
        self._unify_font.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("统一字体", self._unify_font, parent=self._card))

        self._unify_size = ToggleSwitch(self, checked=True)
        self._unify_size.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("统一字号", self._unify_size, parent=self._card))

        self._unify_spacing = ToggleSwitch(self, checked=True)
        self._unify_spacing.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("统一间距", self._unify_spacing, parent=self._card))
        self._card.add_widget(TemplateFormStack(rows, parent=self._card))

    def _build_hint(self) -> None:
        self._footer_note = QLabel("更细的公式表格参数会在后续迭代继续补充。")
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
        self._current_template = template
        if template is None:
            return
        self._is_syncing = True
        try:
            self._font_combo.set_font_name(template.formula_table.formula_font_name)
            self._size_combo.set_pt(template.formula_table.formula_font_size_pt)
            self._set_combo_by_data(self._alignment_combo, template.formula_table.block_alignment)
            self._set_combo_by_data(
                self._numbering_combo,
                template.equation_numbering.numbering_format,
                allow_custom=True,
            )
            self._unify_font.setChecked(template.formula_style.unify_font)
            self._unify_size.setChecked(template.formula_style.unify_size)
            self._unify_spacing.setChecked(template.formula_style.unify_spacing)
        finally:
            self._is_syncing = False

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
        numbering.numbering_format = str(self._numbering_combo.currentData() or "chapter.seq")
        style.unify_font = self._unify_font.isChecked()
        style.unify_size = self._unify_size.isChecked()
        style.unify_spacing = self._unify_spacing.isChecked()

        self.template_edited.emit(self._current_template)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_lg}px; font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; background: transparent;"
            )
        self._desc.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
        self._footer_note.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")

        try:
            from src.ui.icons.catalog import get_icon

            self._header_icon.setPixmap(get_icon("sigma", 18, theme.primary).pixmap(18, 18))
        except Exception:
            self._header_icon.setText("∑")


__all__ = ["FormulaDetail"]
