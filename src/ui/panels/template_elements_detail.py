"""Header/footer and TOC detail pane for template management."""

from __future__ import annotations

from src.config.template import TemplateConfig
from src.qt_api import QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy, Signal
from src.shared.ui.card import Card
from src.shared.ui.form_row import FormRow
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch


_HEADER_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("styleref", "STYLEREF 跟随"),
    ("fixed", "固定页眉"),
    ("none", "无页眉"),
)


class ElementsDetail(QWidget):
    """Editable header/footer + TOC pane backed by TemplateConfig."""

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

        title = QLabel("页眉目录", header)
        title.setObjectName("tpl_card_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self._card.add_widget(header)

        self._desc = QLabel("编辑页眉模式、页码、页眉横线和目录深度。")
        self._desc.setObjectName("tpl_elements_desc")
        self._desc.setWordWrap(True)
        self._card.add_widget(self._desc)

    def _build_form(self) -> None:
        self._header_mode_combo = StyledComboBox(self)
        for value, label in _HEADER_MODE_OPTIONS:
            self._header_mode_combo.addItem(label, value)
        self._header_mode_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("页眉模式", self._header_mode_combo, parent=self._card))

        self._styleref_level_combo = StyledComboBox(self)
        for level in range(1, 7):
            self._styleref_level_combo.addItem(f"{level} 级", level)
        self._styleref_level_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("跟随级别", self._styleref_level_combo, parent=self._card))

        self._page_number_toggle = ToggleSwitch(self, checked=True)
        self._page_number_toggle.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("页码", self._page_number_toggle, parent=self._card))

        self._header_border_toggle = ToggleSwitch(self, checked=True)
        self._header_border_toggle.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("页眉横线", self._header_border_toggle, parent=self._card))

        self._toc_enabled_toggle = ToggleSwitch(self, checked=True)
        self._toc_enabled_toggle.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("启用目录", self._toc_enabled_toggle, parent=self._card))

        self._toc_depth_combo = StyledComboBox(self)
        for level in range(1, 7):
            self._toc_depth_combo.addItem(f"{level} 级", level)
        self._toc_depth_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("目录深度", self._toc_depth_combo, parent=self._card))

    def _build_hint(self) -> None:
        self._footer_note = QLabel("固定页眉文本和目录插入位置将在后续迭代补充。")
        self._footer_note.setObjectName("tpl_elements_footer")
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
            header_footer = template.header_footer
            toc = template.toc
            self._set_combo_by_data(self._header_mode_combo, header_footer.header_mode)
            self._set_combo_by_data(self._styleref_level_combo, header_footer.styleref_level)
            self._page_number_toggle.setChecked(header_footer.page_number_enabled)
            self._header_border_toggle.setChecked(header_footer.header_border)
            self._toc_enabled_toggle.setChecked(toc.enabled)
            self._set_combo_by_data(self._toc_depth_combo, toc.max_level)
        finally:
            self._is_syncing = False

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        header_footer = self._current_template.header_footer
        toc = self._current_template.toc
        header_footer.header_mode = str(self._header_mode_combo.currentData() or "styleref")
        header_footer.styleref_level = int(self._styleref_level_combo.currentData() or 1)
        header_footer.page_number_enabled = self._page_number_toggle.isChecked()
        header_footer.header_border = self._header_border_toggle.isChecked()
        toc.enabled = self._toc_enabled_toggle.isChecked()
        toc.max_level = int(self._toc_depth_combo.currentData() or 3)

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

            self._header_icon.setPixmap(get_icon("panel-top", 16, theme.primary).pixmap(16, 16))
        except Exception:
            self._header_icon.setText("页")


__all__ = ["ElementsDetail"]
