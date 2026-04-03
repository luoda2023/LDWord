"""Page setup detail pane for template management."""

from __future__ import annotations

from src.config.template import TemplateConfig
from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    Qt,
    Signal,
)
from src.shared.ui.card import Card
from src.shared.ui.form_row import FormRow
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme


_PAPER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("A4", "A4"),
    ("A3", "A3"),
    ("B5", "B5"),
    ("LETTER", "Letter"),
    ("LEGAL", "Legal"),
    ("16K", "16K"),
)

_PAGE_FIELDS: tuple[tuple[str, str], ...] = (
    ("top_cm", "上边距"),
    ("bottom_cm", "下边距"),
    ("left_cm", "左边距"),
    ("right_cm", "右边距"),
    ("gutter_cm", "装订线"),
    ("header_distance_cm", "页眉距离"),
    ("footer_distance_cm", "页脚距离"),
)


class PageSetupDetail(QWidget):
    """Editable page setup pane backed by TemplateConfig.page_setup."""

    template_edited = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._is_syncing = False
        self._page_inputs: dict[str, SpacingInput] = {}

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

        title = QLabel("页面设置", header)
        title.setObjectName("tpl_card_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self._card.add_widget(header)

        self._desc = QLabel("设置纸张、页边距、装订线以及页眉页脚距离。")
        self._desc.setObjectName("tpl_page_desc")
        self._desc.setWordWrap(True)
        self._card.add_widget(self._desc)

    def _build_form(self) -> None:
        self._paper_combo = StyledComboBox(self)
        for value, label in _PAPER_OPTIONS:
            self._paper_combo.addItem(label, value)
        self._paper_combo.currentIndexChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("纸张", self._paper_combo, parent=self._card))

        for field_name, label in _PAGE_FIELDS:
            spacing = SpacingInput(
                unit="cm",
                min_val=0.0,
                max_val=20.0,
                step=0.1,
                decimals=1,
                units=("cm",),
                show_unit=False,
                parent=self,
            )
            spacing.value_changed.connect(self._on_form_edited)
            self._page_inputs[field_name] = spacing

            suffix = QLabel("cm", self)
            suffix.setObjectName("tpl_page_unit")
            self._card.add_widget(
                FormRow(label, spacing, suffix_widget=suffix, parent=self._card)
            )

        action_row = QWidget(self)
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 8, 0, 0)
        action_layout.setSpacing(12)

        self._reset_btn = QLabel("修改后将立即反映到模板预览与导航摘要。", action_row)
        self._reset_btn.setObjectName("tpl_page_hint_inline")
        action_layout.addWidget(self._reset_btn, 1)
        self._card.add_widget(action_row)

    def _build_hint(self) -> None:
        self._footer_note = QLabel(
            "页面几何参数已接入真实 TemplateConfig，可直接用于导出与执行。"
        )
        self._footer_note.setObjectName("tpl_page_footer")
        self._footer_note.setWordWrap(True)
        self._card.add_widget(self._footer_note)

    def set_template(self, template: TemplateConfig | None) -> None:
        self._current_template = template
        self._sync_from_template()

    def _sync_from_template(self) -> None:
        template = self._current_template
        if template is None:
            return

        self._is_syncing = True
        try:
            paper = (template.page_setup.paper_size or "A4").upper()
            combo_index = next(
                (
                    index
                    for index in range(self._paper_combo.count())
                    if str(self._paper_combo.itemData(index)).upper() == paper
                ),
                -1,
            )
            if combo_index >= 0:
                self._paper_combo.setCurrentIndex(combo_index)

            values = {
                "top_cm": template.page_setup.margin.top_cm,
                "bottom_cm": template.page_setup.margin.bottom_cm,
                "left_cm": template.page_setup.margin.left_cm,
                "right_cm": template.page_setup.margin.right_cm,
                "gutter_cm": template.page_setup.gutter_cm,
                "header_distance_cm": template.page_setup.header_distance_cm,
                "footer_distance_cm": template.page_setup.footer_distance_cm,
            }
            for field_name, value in values.items():
                self._page_inputs[field_name].set_value(float(value), "cm")
        finally:
            self._is_syncing = False

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        page_setup = self._current_template.page_setup
        page_setup.paper_size = str(self._paper_combo.currentData() or "A4").upper()
        page_setup.margin.top_cm = self._page_inputs["top_cm"].value()
        page_setup.margin.bottom_cm = self._page_inputs["bottom_cm"].value()
        page_setup.margin.left_cm = self._page_inputs["left_cm"].value()
        page_setup.margin.right_cm = self._page_inputs["right_cm"].value()
        page_setup.gutter_cm = self._page_inputs["gutter_cm"].value()
        page_setup.header_distance_cm = self._page_inputs["header_distance_cm"].value()
        page_setup.footer_distance_cm = self._page_inputs["footer_distance_cm"].value()

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
        self._reset_btn.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
        )
        for widget in self.findChildren(QLabel, "tpl_page_unit"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
            )

        try:
            from src.ui.icons.catalog import get_icon

            self._header_icon.setPixmap(get_icon("ruler", 16, theme.primary).pixmap(16, 16))
        except Exception:
            self._header_icon.setText("尺")


__all__ = ["PageSetupDetail"]
