"""Miscellaneous template detail pane for watermark/output settings."""

from __future__ import annotations

from src.config.template import TemplateConfig
from src.qt_api import QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy, Signal
from src.shared.ui.card import Card
from src.shared.ui.form_row import FormRow
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch


class OtherDetail(QWidget):
    """Editable miscellaneous pane backed by watermark/output fields."""

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
        title = QLabel("其他参数", header)
        title.setObjectName("tpl_card_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self._card.add_widget(header)

        self._desc = QLabel("编辑水印开关以及导出输出项。")
        self._desc.setObjectName("tpl_other_desc")
        self._desc.setWordWrap(True)
        self._card.add_widget(self._desc)

    def _build_form(self) -> None:
        self._watermark_toggle = ToggleSwitch(self, checked=False)
        self._watermark_toggle.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("启用水印", self._watermark_toggle, parent=self._card))

        self._final_docx_toggle = ToggleSwitch(self, checked=True)
        self._final_docx_toggle.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("最终稿 DOCX", self._final_docx_toggle, parent=self._card))

        self._compare_docx_toggle = ToggleSwitch(self, checked=True)
        self._compare_docx_toggle.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("对比稿 DOCX", self._compare_docx_toggle, parent=self._card))

        self._report_json_toggle = ToggleSwitch(self, checked=True)
        self._report_json_toggle.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("JSON 报告", self._report_json_toggle, parent=self._card))

        self._report_markdown_toggle = ToggleSwitch(self, checked=True)
        self._report_markdown_toggle.toggled_signal.connect(self._on_form_edited)
        self._card.add_widget(FormRow("Markdown 报告", self._report_markdown_toggle, parent=self._card))

    def _build_hint(self) -> None:
        self._footer_note = QLabel("颜色、旋转角度与更多输出项会在后续继续补充。")
        self._footer_note.setObjectName("tpl_other_footer")
        self._footer_note.setWordWrap(True)
        self._card.add_widget(self._footer_note)

    def set_template(self, template: TemplateConfig | None) -> None:
        self._current_template = template
        if template is None:
            return
        self._is_syncing = True
        try:
            self._watermark_toggle.setChecked(template.watermark.enabled)
            self._final_docx_toggle.setChecked(template.output.final_docx)
            self._compare_docx_toggle.setChecked(template.output.compare_docx)
            self._report_json_toggle.setChecked(template.output.report_json)
            self._report_markdown_toggle.setChecked(template.output.report_markdown)
        finally:
            self._is_syncing = False

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        self._current_template.watermark.enabled = self._watermark_toggle.isChecked()
        output = self._current_template.output
        output.final_docx = self._final_docx_toggle.isChecked()
        output.compare_docx = self._compare_docx_toggle.isChecked()
        output.report_json = self._report_json_toggle.isChecked()
        output.report_markdown = self._report_markdown_toggle.isChecked()

        self.template_edited.emit(self._current_template)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        for widget in self.findChildren(QLabel, "tpl_card_title"):
            widget.setStyleSheet(
                f"font-size: {theme.font_size_md}px; font-weight: {theme.font_weight_bold}; color: {theme.primary};"
            )
        self._desc.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
        self._footer_note.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")

        try:
            from src.ui.icons.catalog import get_icon

            self._header_icon.setPixmap(get_icon("settings", 16, theme.primary).pixmap(16, 16))
        except Exception:
            self._header_icon.setText("设")


__all__ = ["OtherDetail"]
