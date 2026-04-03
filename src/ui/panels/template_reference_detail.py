"""Reference style detail pane for template management."""

from __future__ import annotations

from src.config.template import TemplateConfig
from src.qt_api import QHBoxLayout, QLabel, QVBoxLayout, QWidget, QSizePolicy, Signal
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.form_row import FormRow
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.theme import bind_theme, get_theme


class ReferenceDetail(QWidget):
    """Editable reference-style pane backed by TemplateConfig.reference_style."""

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
        title = QLabel("参考文献", header)
        title.setObjectName("tpl_card_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self._card.add_widget(header)

        self._desc = QLabel("编辑参考文献字体、字号、悬挂缩进和段后间距。")
        self._desc.setObjectName("tpl_reference_desc")
        self._desc.setWordWrap(True)
        self._card.add_widget(self._desc)

    def _build_form(self) -> None:
        self._font_cn = FontCombo(lang="cn", parent=self)
        self._font_cn.font_changed.connect(self._on_form_edited)
        self._card.add_widget(FormRow("中文字体", self._font_cn, parent=self._card))

        self._font_en = FontCombo(lang="en", parent=self)
        self._font_en.font_changed.connect(self._on_form_edited)
        self._card.add_widget(FormRow("英文字体", self._font_en, parent=self._card))

        self._size_combo = SizeCombo(self)
        self._size_combo.size_changed.connect(self._on_form_edited)
        self._size_combo.currentTextChanged.connect(self._on_form_edited)
        self._card.add_widget(FormRow("字号", self._size_combo, parent=self._card))

        self._hanging_indent = SpacingInput(
            unit="cm",
            min_val=0.0,
            max_val=5.0,
            step=0.1,
            decimals=2,
            units=("cm",),
            show_unit=False,
            parent=self,
        )
        self._hanging_indent.value_changed.connect(self._on_form_edited)
        indent_suffix = QLabel("cm", self)
        indent_suffix.setObjectName("tpl_reference_unit")
        self._card.add_widget(
            FormRow("悬挂缩进", self._hanging_indent, suffix_widget=indent_suffix, parent=self._card)
        )

        self._space_after = SpacingInput(
            unit="pt",
            min_val=0.0,
            max_val=40.0,
            step=1.0,
            decimals=1,
            units=("pt",),
            show_unit=False,
            parent=self,
        )
        self._space_after.value_changed.connect(self._on_form_edited)
        after_suffix = QLabel("pt", self)
        after_suffix.setObjectName("tpl_reference_unit")
        self._card.add_widget(
            FormRow("段后", self._space_after, suffix_widget=after_suffix, parent=self._card)
        )

    def _build_hint(self) -> None:
        self._footer_note = QLabel("当前版本优先覆盖参考文献段落样式的核心参数。")
        self._footer_note.setObjectName("tpl_reference_footer")
        self._footer_note.setWordWrap(True)
        self._card.add_widget(self._footer_note)

    def set_template(self, template: TemplateConfig | None) -> None:
        self._current_template = template
        if template is None:
            return
        self._is_syncing = True
        try:
            ref = template.reference_style
            if ref.font_cn:
                self._font_cn.set_font_name(ref.font_cn)
            if ref.font_en:
                self._font_en.set_font_name(ref.font_en)
            if ref.size_pt:
                self._size_combo.set_pt(ref.size_pt)
            self._hanging_indent.set_value(ref.hanging_indent_cm, "cm")
            self._space_after.set_value(ref.space_after_pt, "pt")
        finally:
            self._is_syncing = False

    def _on_form_edited(self, *_args) -> None:
        if self._is_syncing or self._current_template is None:
            return

        ref = self._current_template.reference_style
        ref.font_cn = self._font_cn.selected_font()
        ref.font_en = self._font_en.selected_font()
        pt = self._size_combo.current_pt()
        ref.size_pt = pt
        ref.hanging_indent_cm = self._hanging_indent.value()
        ref.space_after_pt = self._space_after.value()

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
        for widget in self.findChildren(QLabel, "tpl_reference_unit"):
            widget.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")

        try:
            from src.ui.icons.catalog import get_icon

            self._header_icon.setPixmap(get_icon("book-open", 16, theme.primary).pixmap(16, 16))
        except Exception:
            self._header_icon.setText("书")


__all__ = ["ReferenceDetail"]
