"""Miscellaneous template detail pane for template-owned watermark settings."""

from __future__ import annotations

from copy import deepcopy

from src.config.template import TemplateConfig
from src.qt_api import (
    QColor,
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSize,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    Signal,
)
from src.shared.ui.card import Card
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.template_summary_card import (
    TemplateSummaryCard,
    apply_template_summary_action_button,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.panels.template_summary_projection import build_template_detail_summary_items


class OtherDetail(QWidget):
    """Editable miscellaneous pane backed only by the watermark field."""

    template_edited = Signal(object)
    save_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template: TemplateConfig | None = None
        self._is_syncing = False
        self._save_enabled = False
        self._snapshot = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._summary_card = TemplateSummaryCard("文字水印", "settings", parent=self)
        self._header_card = self._summary_card
        self._restore_btn = QPushButton("恢复", self._summary_card.header)
        self._restore_btn.setIconSize(QSize(16, 16))
        self._restore_btn.clicked.connect(self._on_restore_entry)
        self._summary_card.add_action(self._restore_btn)
        self._save_btn = QPushButton("保存", self._summary_card.header)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self.save_requested.emit)
        self._summary_card.add_action(self._save_btn)
        layout.addWidget(self._summary_card)

        self._watermark_card = Card(parent=self)
        self._watermark_card.set_header("文字水印", icon_name="whole-word")
        layout.addWidget(self._watermark_card)

        layout.addStretch(1)

        self._build_header()
        self._build_watermark_form()

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _build_header(self) -> None:
        self._desc = QLabel("设置模板提供的文字水印外观；输出产物由方案的交付预设统一管理。")
        self._desc.setObjectName("tpl_other_desc")
        self._desc.setWordWrap(True)
        self._watermark_card.add_widget(self._desc)

    def _build_watermark_form(self) -> None:
        rows = []
        self._watermark_enabled = ToggleSwitch(self, checked=False)
        self._watermark_enabled.toggled_signal.connect(self._on_form_edited)
        rows.append(template_form_row("启用文字水印", self._watermark_enabled, parent=self._watermark_card))

        self._watermark_text = QLineEdit(self)
        self._watermark_text.setPlaceholderText("例如：内部传阅")
        self._watermark_text.textChanged.connect(self._on_form_edited)
        rows.append(template_form_row("水印文字", self._watermark_text, parent=self._watermark_card))

        color_control = QWidget(self)
        color_layout = QHBoxLayout(color_control)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(get_theme().spacing_sm)
        self._watermark_color = QLineEdit(self)
        self._watermark_color.setPlaceholderText("#C0C0C0")
        self._watermark_color.editingFinished.connect(self._on_form_edited)
        color_layout.addWidget(self._watermark_color, 1)
        self._choose_color_btn = QPushButton("选择颜色", self)
        self._choose_color_btn.clicked.connect(self._choose_watermark_color)
        color_layout.addWidget(self._choose_color_btn)
        rows.append(template_form_row("水印颜色", color_control, parent=self._watermark_card))

        self._watermark_rotation = StyledSpinBox(self)
        self._watermark_rotation.setRange(-180, 180)
        self._watermark_rotation.setDecimals(0)
        self._watermark_rotation.setSuffix("°")
        self._watermark_rotation.valueChanged.connect(self._on_form_edited)
        rows.append(template_form_row("旋转角度", self._watermark_rotation, parent=self._watermark_card))

        self._watermark_font_size = StyledSpinBox(self)
        self._watermark_font_size.setRange(8, 200)
        self._watermark_font_size.setDecimals(0)
        self._watermark_font_size.setSuffix("磅")
        self._watermark_font_size.valueChanged.connect(self._on_form_edited)
        rows.append(template_form_row("水印字号", self._watermark_font_size, parent=self._watermark_card))
        self._watermark_card.add_widget(TemplateFormStack(rows, parent=self._watermark_card))

    def set_template(self, template: TemplateConfig | None) -> None:
        preserve_snapshot = template is self._current_template and self._snapshot is not None
        self._current_template = template
        if template is None:
            self._snapshot = None
            return
        if not preserve_snapshot:
            self.capture_entry_snapshot()
        self._is_syncing = True
        try:
            watermark = template.watermark
            self._watermark_enabled.set_checked(watermark.enabled)
            self._watermark_text.setText(watermark.text)
            self._watermark_color.setText(watermark.color)
            self._watermark_rotation.setValue(watermark.rotation)
            self._watermark_font_size.setValue(watermark.font_size)
        finally:
            self._is_syncing = False
        self._sync_watermark_controls()
        self._summary_card.set_summary_items(
            build_template_detail_summary_items(template, "tpl_other")
        )

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return


        watermark = self._current_template.watermark
        watermark.enabled = self._watermark_enabled.isChecked()
        watermark.text = self._watermark_text.text()
        color = QColor(self._watermark_color.text().strip())
        if color.isValid():
            watermark.color = color.name().upper()
            self._watermark_color.setToolTip("")
        else:
            self._watermark_color.setToolTip("颜色格式无效，已保留上一个有效值")
        watermark.rotation = int(round(self._watermark_rotation.value()))
        watermark.font_size = int(round(self._watermark_font_size.value()))

        self._sync_watermark_controls()
        self._summary_card.set_summary_items(
            build_template_detail_summary_items(self._current_template, "tpl_other")
        )
        self.template_edited.emit(self._current_template)

    def capture_entry_snapshot(self) -> None:
        if self._current_template is None:
            self._snapshot = None
            return
        self._snapshot = deepcopy(self._current_template.watermark)

    def _on_restore_entry(self) -> None:
        if self._current_template is None or self._snapshot is None:
            return
        self._current_template.watermark = deepcopy(self._snapshot)
        self.set_template(self._current_template)
        self.template_edited.emit(self._current_template)

    def _choose_watermark_color(self) -> None:
        initial = QColor(self._watermark_color.text().strip() or "#C0C0C0")
        color = QColorDialog.getColor(initial, self, "选择水印颜色")
        if color.isValid():
            self._watermark_color.setText(color.name().upper())
            self._on_form_edited()

    def _sync_watermark_controls(self) -> None:
        enabled = self._watermark_enabled.isChecked()
        for widget in (
            self._watermark_text,
            self._watermark_color,
            self._choose_color_btn,
            self._watermark_rotation,
            self._watermark_font_size,
        ):
            widget.setEnabled(enabled)

    def apply_theme(self) -> None:
        self._apply_theme()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._save_btn.setEnabled(self._save_enabled)
        self._restore_btn.setEnabled(self._save_enabled)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._desc.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
        input_style = build_text_input_stylesheet(theme)
        self._watermark_text.setStyleSheet(input_style)
        self._watermark_color.setStyleSheet(input_style)
        apply_template_summary_action_button(self._restore_btn, "ghost-primary")
        apply_template_summary_action_button(self._save_btn, "primary")
        self._restore_btn.setEnabled(self._save_enabled)
        self._save_btn.setEnabled(self._save_enabled)


__all__ = ["OtherDetail"]
