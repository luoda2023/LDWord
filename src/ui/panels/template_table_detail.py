"""Table and caption detail pane for template management."""

from __future__ import annotations

from src.config.template import TemplateConfig
from src.qt_api import QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy, Signal
from src.shared.ui.card import Card
from src.shared.ui.form_row import FormRow
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch


_BORDER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("three_line", "三线表"),
    ("full_grid", "全框线"),
    ("keep", "保留原样"),
)

_LAYOUT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("smart", "智能布局"),
    ("compact", "紧凑布局"),
    ("full", "撑满布局"),
)

_LINE_SPACING_OPTIONS: tuple[tuple[str, str], ...] = (
    ("single", "单倍"),
    ("one_half", "1.5 倍"),
    ("double", "双倍"),
)

_NUMBERING_OPTIONS: tuple[tuple[str, str], ...] = (
    ("chapter.seq", "章.序"),
    ("global", "全局序号"),
)


class TableCaptionDetail(QWidget):
    """Editable table/caption pane backed by TemplateConfig.table/caption."""

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

        title = QLabel("表格题注", header)
        title.setObjectName("tpl_card_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self._card.add_widget(header)

        self._desc = QLabel("编辑表格布局、边框、题注编号和表头重复策略。")
        self._desc.setObjectName("tpl_table_desc")
        self._desc.setWordWrap(True)
        self._card.add_widget(self._desc)

    def _build_form(self) -> None:
        self._border_combo = StyledComboBox(self)
        for value, label in _BORDER_OPTIONS:
            self._border_combo.addItem(label, value)
        self._border_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("边框", self._border_combo, parent=self._card))

        self._layout_combo = StyledComboBox(self)
        for value, label in _LAYOUT_OPTIONS:
            self._layout_combo.addItem(label, value)
        self._layout_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("布局", self._layout_combo, parent=self._card))

        self._smart_levels_combo = StyledComboBox(self)
        for level in range(1, 7):
            self._smart_levels_combo.addItem(f"{level} 级", level)
        self._smart_levels_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("智能层级", self._smart_levels_combo, parent=self._card))

        self._line_spacing_combo = StyledComboBox(self)
        for value, label in _LINE_SPACING_OPTIONS:
            self._line_spacing_combo.addItem(label, value)
        self._line_spacing_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("表格行距", self._line_spacing_combo, parent=self._card))

        self._repeat_header_toggle = ToggleSwitch(self, checked=False)
        self._repeat_header_toggle.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("重复表头", self._repeat_header_toggle, parent=self._card))

        self._numbering_combo = StyledComboBox(self)
        for value, label in _NUMBERING_OPTIONS:
            self._numbering_combo.addItem(label, value)
        self._numbering_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("题注编号", self._numbering_combo, parent=self._card))

    def _build_hint(self) -> None:
        self._footer_note = QLabel("当前版本聚焦表格/题注的核心结构参数。")
        self._footer_note.setObjectName("tpl_table_footer")
        self._footer_note.setWordWrap(True)
        self._card.add_widget(self._footer_note)

    def _set_combo_by_data(self, combo: StyledComboBox, target) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == target:
                combo.setCurrentIndex(index)
                return

    def set_template(self, template: TemplateConfig | None) -> None:
        self._current_template = template
        if template is None:
            return
        self._is_syncing = True
        try:
            table = template.table
            caption = template.caption
            self._set_combo_by_data(self._border_combo, table.border_mode)
            self._set_combo_by_data(self._layout_combo, table.layout_mode)
            self._set_combo_by_data(self._smart_levels_combo, table.smart_levels)
            self._set_combo_by_data(self._line_spacing_combo, table.line_spacing_mode)
            self._repeat_header_toggle.setChecked(table.repeat_header)
            self._set_combo_by_data(self._numbering_combo, caption.numbering_format)
        finally:
            self._is_syncing = False

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        table = self._current_template.table
        caption = self._current_template.caption
        table.border_mode = str(self._border_combo.currentData() or "three_line")
        table.layout_mode = str(self._layout_combo.currentData() or "smart")
        table.smart_levels = int(self._smart_levels_combo.currentData() or 4)
        table.line_spacing_mode = str(self._line_spacing_combo.currentData() or "single")
        table.repeat_header = self._repeat_header_toggle.isChecked()
        caption.numbering_format = str(self._numbering_combo.currentData() or "chapter.seq")

        self.template_edited.emit(self._current_template)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_md}px; "
                f"font-weight: {theme.font_weight_bold}; color: {theme.primary};"
            )
        self._desc.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
        )
        self._footer_note.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
        )

        try:
            from src.ui.icons.catalog import get_icon

            self._header_icon.setPixmap(get_icon("table-2", 16, theme.primary).pixmap(16, 16))
        except Exception:
            self._header_icon.setText("表")


__all__ = ["TableCaptionDetail"]
