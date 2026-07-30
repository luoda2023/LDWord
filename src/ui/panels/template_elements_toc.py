"""TOC section for the template elements detail pane."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import (
    QColor,
    QFont,
    QFontMetricsF,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSize,
    QSizePolicy,
    QPainter,
    QPen,
    QRectF,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.engine.toc_style_ops import resolve_toc_style_config
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later, updates_suspended
from src.shared.ui.paragraph_style_inputs import IndentInput, SpecialIndentInput
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.style_preview_utils import (
    preview_alignment_flags,
    resolve_preview_indents_pt,
    resolve_preview_size_pt,
)
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import TemplateFormGrid, compact_form_column_gap, template_form_row
from src.shared.ui.theme import get_theme, theme_rgba
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

TOC_STYLE_KEYS: tuple[str, ...] = (
    "toc_title",
    "toc_level1",
    "toc_level2",
    "toc_level3",
    "toc_level4",
    "toc_level5",
    "toc_level6",
)


@dataclass(frozen=True)
class _TocRoleSpec:
    key: str
    label: str
    word_style: str


def _set_combo_by_data(combo: StyledComboBox, target) -> None:
    for index in range(combo.count()):
        if combo.itemData(index) == target:
            combo.setCurrentIndex(index)
            return


def _size_text(style: StyleConfig) -> str:
    if style.size_display:
        return style.size_display
    if style.size_pt:
        return f"{style.size_pt:g} 磅"
    return "默认字号"


def _toc_role_level(role_key: str) -> int:
    raw = str(role_key or "").replace("toc_level", "", 1)
    try:
        return max(1, min(int(raw), 6))
    except (TypeError, ValueError):
        return 1


class _TocStylePreview(QFrame):
    """Draw a compact, live preview for the currently selected TOC role."""

    _SIDE_PADDING = 12.0
    _TOP_PADDING = 8.0
    _BOTTOM_PADDING = 8.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toc_inline_preview")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._style = StyleConfig()
        self._role_key = "toc_title"

    def set_preview(self, role_key: str, style: StyleConfig) -> None:
        self._role_key = str(role_key or "toc_title")
        self._style = deepcopy(style)
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(320, self._preview_height())

    def minimumSizeHint(self) -> QSize:
        return QSize(180, self._preview_height())

    def _sample_text(self) -> tuple[str, str]:
        if self._role_key == "toc_title":
            return "目录", ""
        level = _toc_role_level(self._role_key)
        samples = {
            1: "第一章  示例标题",
            2: "1.1 示例标题",
            3: "1.1.1 示例标题",
            4: "1.1.1.1 示例标题",
            5: "1.1.1.1.1 示例标题",
            6: "1.1.1.1.1.1 示例标题",
        }
        return samples[level], str(level + 1)

    def _font_and_metrics(self) -> tuple[QFont, QFontMetricsF, float]:
        style = self._style or StyleConfig()
        px_per_pt = max(1.0, float(self.logicalDpiY()) / 72.0)
        font = QFont()
        families = [name for name in [style.font_en, style.font_cn] if name]
        if families:
            try:
                font.setFamilies(families)
            except AttributeError:
                font.setFamily(families[-1])
        else:
            font.setFamily(self.font().family())
        size_pt = resolve_preview_size_pt(style)
        font.setPixelSize(max(10, int(round(size_pt * px_per_pt))))
        font.setBold(bool(style.bold))
        font.setItalic(bool(style.italic))
        return font, QFontMetricsF(font), px_per_pt

    def _line_height_px(self, metrics: QFontMetricsF, px_per_pt: float) -> float:
        style = self._style or StyleConfig()
        kind = normalize_line_spacing_type(style.line_spacing_type)
        value = resolve_line_spacing_value(kind, style.line_spacing_pt)
        if kind == "exact":
            return max(float(metrics.height()) + 1.0, value * px_per_pt)
        return max(float(metrics.height()) + 1.0, float(metrics.height()) * value)

    def _preview_height(self) -> int:
        font, metrics, px_per_pt = self._font_and_metrics()
        _ = font
        line_height = self._line_height_px(metrics, px_per_pt)
        return max(48, int(round(line_height + self._TOP_PADDING + self._BOTTOM_PADDING)))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        theme = get_theme()
        style = self._style or StyleConfig()
        font, metrics, px_per_pt = self._font_and_metrics()
        painter.setFont(font)
        painter.setPen(QPen(QColor(theme.text_primary)))

        line_height = self._line_height_px(metrics, px_per_pt)
        size_pt = resolve_preview_size_pt(style)
        indents = resolve_preview_indents_pt(style, size_pt=size_pt)

        left = self._SIDE_PADDING + indents["left_pt"] * px_per_pt
        right = max(left + 20.0, self.width() - self._SIDE_PADDING - indents["right_pt"] * px_per_pt)
        first_left = left + indents["first_pt"] * px_per_pt
        y = max(self._TOP_PADDING, (self.height() - line_height) / 2.0)
        draw_rect = QRectF(first_left, y, max(20.0, right - first_left), line_height)

        text, page = self._sample_text()
        if not page:
            painter.drawText(draw_rect, preview_alignment_flags(style.alignment), text)
            painter.end()
            return

        alignment = str(style.alignment or "left").strip().lower()
        if alignment in {"center", "right"}:
            painter.drawText(draw_rect, preview_alignment_flags(alignment), f"{text}  {page}")
            painter.end()
            return

        text_width = metrics.horizontalAdvance(text)
        page_width = metrics.horizontalAdvance(page)
        page_x = max(first_left + text_width + 12.0, right - page_width)
        dots_left = first_left + text_width + 8.0
        dots_width = max(0.0, page_x - dots_left - 8.0)
        dot_width = max(1.0, metrics.horizontalAdvance("."))
        dots = "." * max(2, int(dots_width / dot_width))

        painter.drawText(QRectF(first_left, y, max(20.0, text_width + 4.0), line_height), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.setPen(QPen(QColor(theme.text_secondary)))
        painter.drawText(QRectF(dots_left, y, dots_width, line_height), Qt.AlignLeft | Qt.AlignVCenter, dots)
        painter.setPen(QPen(QColor(theme.text_primary)))
        painter.drawText(QRectF(page_x, y, page_width + 2.0, line_height), Qt.AlignLeft | Qt.AlignVCenter, page)
        painter.end()


class TocDetailSection:
    """Owns TOC structure and TOC-specific style controls inside ElementsDetail."""

    def __init__(self, owner: "ElementsDetail"):
        self._owner = owner
        self._current_template: TemplateConfig | None = None
        self._selected_role_key = "toc_title"
        self._is_style_syncing = False
        self._toc_style_controls: dict[str, object] = {}
        self._toc_role_items: dict[str, QListWidgetItem] = {}
        self._toc_role_widgets: dict[str, QWidget] = {}

        self.structure_section = Card(parent=owner._editor_column)
        self._toc_section = self.structure_section
        owner._toc_section = self.structure_section
        owner._add_card_header(self.structure_section, "chart-no-axes-gantt", "目录结构")
        owner._editor_layout.addWidget(self.structure_section)
        self._build_toc_form()

        self.styles_section = Card(parent=owner._editor_column)
        self._toc_style_editor_card = self.styles_section
        owner._add_card_header(self.styles_section, "type-outline", "目录样式")
        owner._editor_layout.addWidget(self.styles_section)
        self._build_style_editor()
        self._toc_styles_section = self.styles_section
        owner._toc_styles_section = self.styles_section

        self._export_compat_attributes()

    def _export_compat_attributes(self) -> None:
        names = (
            "_toc_mode_combo",
            "_toc_mode_row",
            "_toc_depth_combo",
            "_toc_depth_row",
            "_toc_insert_combo",
            "_toc_insert_row",
            "_toc_styles_section",
            "_toc_style_editor_card",
            "_toc_style_role_list",
            "_toc_style_controls",
        )
        for name in names:
            setattr(self._owner, name, getattr(self, name))

    def _build_toc_form(self) -> None:
        form = InspectorForm(parent=self.structure_section)

        self._toc_mode_combo = StyledComboBox(self._owner)
        for value, label in TOC_MODE_OPTIONS:
            self._toc_mode_combo.addItem(label, value)
        self._toc_mode_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._toc_mode_row = self._form_row("目录模式", self._toc_mode_combo, parent=form)

        self._toc_depth_combo = StyledComboBox(self._owner)
        for level in range(1, 7):
            self._toc_depth_combo.addItem(f"{level} 级", level)
        self._toc_depth_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._toc_depth_row = self._form_row("目录深度", self._toc_depth_combo, parent=form)

        self._toc_insert_combo = StyledComboBox(self._owner)
        for value, label in TOC_INSERT_OPTIONS:
            self._toc_insert_combo.addItem(label, value)
        self._toc_insert_combo.currentIndexChanged.connect(self._owner._on_structure_edited)
        self._toc_insert_row = self._form_row("插入位置", self._toc_insert_combo, parent=form)

        self._toc_structure_grid = TemplateFormGrid(
            [
                [self._toc_mode_row, self._toc_depth_row],
                [self._toc_insert_row],
            ],
            parent=form,
            align_trailing_labels=False,
        )
        form.add_widget(self._toc_structure_grid)
        self.structure_section.add_widget(form)

    def _build_style_editor(self) -> None:
        self._toc_style_list_frame = QFrame(self.styles_section)
        self._toc_style_list_frame.setObjectName("toc_style_list_frame")
        self._toc_style_list_frame.setMinimumWidth(230)
        self._toc_style_list_frame.setMaximumWidth(280)
        list_layout = QVBoxLayout(self._toc_style_list_frame)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        list_header = QLabel("选择级别", self._toc_style_list_frame)
        list_header.setObjectName("toc_style_list_header")
        list_header.setAlignment(Qt.AlignCenter)
        list_header.setMinimumHeight(48)
        list_layout.addWidget(list_header)

        self._toc_style_role_list = QListWidget(self._toc_style_list_frame)
        self._toc_style_role_list.setObjectName("toc_style_role_list")
        self._toc_style_role_list.setFrameShape(QFrame.NoFrame)
        self._toc_style_role_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._toc_style_role_list.currentItemChanged.connect(self._on_style_role_changed)
        list_layout.addWidget(self._toc_style_role_list, 1)

        inspector = QWidget(self.styles_section)
        inspector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.setSpacing(get_theme().template_detail_section_gap)

        self._toc_style_title = QLabel("目录标题", inspector)
        self._toc_style_title.setObjectName("toc_style_title")
        inspector_layout.addWidget(self._toc_style_title)

        self._build_result_strip(inspector_layout)

        self._toc_style_block = QFrame(inspector)
        self._toc_style_block.setObjectName("toc_inspector_block")
        block_layout = QVBoxLayout(self._toc_style_block)
        block_layout.setContentsMargins(16, 14, 16, 14)
        block_layout.setSpacing(10)

        block_title = QLabel("目录格式", self._toc_style_block)
        block_title.setObjectName("toc_block_title")
        block_layout.addWidget(block_title)

        self._toc_style_form = InspectorForm(parent=self._toc_style_block)
        self._build_style_form_controls()
        block_layout.addWidget(self._toc_style_form)
        inspector_layout.addWidget(self._toc_style_block)
        inspector_layout.addStretch(1)

        self._toc_style_content = QWidget(self.styles_section)
        content_layout = QHBoxLayout(self._toc_style_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(get_theme().template_detail_section_gap)
        content_layout.addWidget(self._toc_style_list_frame)
        content_layout.addWidget(inspector, 1)
        self.styles_section.add_widget(self._toc_style_content)

    def _build_result_strip(self, parent_layout: QVBoxLayout) -> None:
        self._toc_result_strip = QFrame(self.styles_section)
        self._toc_result_strip.setObjectName("toc_result_strip")
        layout = QVBoxLayout(self._toc_result_strip)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self._toc_result_heading = QLabel("样式预览", self._toc_result_strip)
        self._toc_result_heading.setObjectName("toc_result_heading")
        layout.addWidget(self._toc_result_heading)

        preview_shell = QFrame(self._toc_result_strip)
        preview_shell.setObjectName("toc_result_preview_shell")
        preview_layout = QVBoxLayout(preview_shell)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_layout.setSpacing(0)

        self._toc_inline_preview = _TocStylePreview(preview_shell)
        preview_layout.addWidget(self._toc_inline_preview)
        layout.addWidget(preview_shell)
        parent_layout.addWidget(self._toc_result_strip)

    def _build_style_form_controls(self) -> None:
        self._toc_font_cn = FontCombo(lang="cn", parent=self._owner)
        self._toc_font_cn.font_changed.connect(self._on_toc_style_edited)
        self._toc_font_en = FontCombo(lang="en", parent=self._owner)
        self._toc_font_en.font_changed.connect(self._on_toc_style_edited)

        self._toc_size_combo = SizeCombo(self._owner)
        self._toc_size_combo.size_changed.connect(self._on_toc_style_edited)
        self._toc_size_combo.currentTextChanged.connect(self._on_toc_style_edited)

        self._toc_bold_toggle = ToggleSwitch(self._owner, checked=False)
        self._toc_bold_toggle.toggled_signal.connect(self._on_toc_style_edited)
        self._toc_italic_toggle = ToggleSwitch(self._owner, checked=False)
        self._toc_italic_toggle.toggled_signal.connect(self._on_toc_style_edited)

        self._toc_alignment_combo = StyledComboBox(self._owner)
        for value, label in TOC_ALIGNMENT_OPTIONS:
            self._toc_alignment_combo.addItem(label, value)
        self._toc_alignment_combo.currentIndexChanged.connect(self._on_toc_style_edited)

        self._toc_special_indent = SpecialIndentInput(self._owner, reference_size_pt=12.0)
        self._toc_special_indent.value_changed.connect(self._on_toc_style_edited)
        self._toc_left_indent = IndentInput(self._owner, reference_size_pt=12.0)
        self._toc_left_indent.value_changed.connect(self._on_toc_style_edited)
        self._toc_right_indent = IndentInput(self._owner, reference_size_pt=12.0)
        self._toc_right_indent.value_changed.connect(self._on_toc_style_edited)

        self._toc_line_type_combo = StyledComboBox(self._owner)
        for value, label in LINE_SPACING_OPTIONS:
            self._toc_line_type_combo.addItem(label, value)
        self._toc_line_type_combo.currentIndexChanged.connect(self._on_toc_line_spacing_type_changed)

        self._toc_line_value = SpacingInput(
            unit="pt",
            min_val=0.5,
            max_val=60.0,
            step=0.5,
            decimals=1,
            units=("pt",),
            show_unit=False,
            parent=self._owner,
        )
        self._toc_line_value.value_changed.connect(self._on_toc_style_edited)
        self._toc_line_suffix = QLabel("磅", self._owner)
        self._toc_line_suffix.setObjectName("tpl_style_unit")

        self._toc_space_before = SpacingInput(
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
        self._toc_space_before.value_changed.connect(self._on_toc_style_edited)
        self._toc_space_after = SpacingInput(
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
        self._toc_space_after.value_changed.connect(self._on_toc_style_edited)

        font_cn_row = self._form_row("中文字体", self._toc_font_cn, parent=self._toc_style_form)
        font_en_row = self._form_row("英文字体", self._toc_font_en, parent=self._toc_style_form)
        size_row = self._form_row("字号", self._toc_size_combo, parent=self._toc_style_form)
        emphasis_row = self._form_row(
            "字形",
            build_emphasis_widget(
                self._owner,
                self._toc_bold_toggle,
                self._toc_italic_toggle,
                spacing=10,
            ),
            parent=self._toc_style_form,
        )
        alignment_row = self._form_row("对齐", self._toc_alignment_combo, parent=self._toc_style_form)
        special_indent_row = self._form_row("特殊缩进", self._toc_special_indent, parent=self._toc_style_form)
        left_indent_row = self._form_row("左缩进", self._toc_left_indent, parent=self._toc_style_form)
        right_indent_row = self._form_row("右缩进", self._toc_right_indent, parent=self._toc_style_form)
        line_type_row = self._form_row("行距类型", self._toc_line_type_combo, parent=self._toc_style_form)
        line_value_row = self._form_row(
            "行距值",
            self._toc_line_value,
            suffix_widget=self._toc_line_suffix,
            parent=self._toc_style_form,
        )
        space_before_row = self._form_row("段前", self._toc_space_before, parent=self._toc_style_form)
        space_after_row = self._form_row("段后", self._toc_space_after, parent=self._toc_style_form)

        self._toc_font_cn_row = font_cn_row
        self._toc_font_en_row = font_en_row
        self._toc_size_row = size_row
        self._toc_emphasis_row = emphasis_row
        self._toc_alignment_row = alignment_row
        self._toc_special_indent_row = special_indent_row
        self._toc_left_indent_row = left_indent_row
        self._toc_right_indent_row = right_indent_row
        self._toc_line_type_row = line_type_row
        self._toc_line_value_row = line_value_row
        self._toc_space_before_row = space_before_row
        self._toc_space_after_row = space_after_row

        self._toc_style_grid = self._toc_style_form.add_grid(
            [
                [font_cn_row, size_row],
                [font_en_row, emphasis_row],
                [alignment_row, special_indent_row],
                [left_indent_row, right_indent_row],
                [line_type_row, line_value_row],
                [space_before_row, space_after_row],
            ],
            column_gap=compact_form_column_gap(),
            align_trailing_labels=True,
            stack_slack=32,
        )
        self._toc_style_controls = {
            "font_cn": self._toc_font_cn,
            "font_en": self._toc_font_en,
            "size": self._toc_size_combo,
            "bold": self._toc_bold_toggle,
            "italic": self._toc_italic_toggle,
            "alignment": self._toc_alignment_combo,
            "special_indent": self._toc_special_indent,
            "left_indent": self._toc_left_indent,
            "right_indent": self._toc_right_indent,
            "line_type": self._toc_line_type_combo,
            "line_value": self._toc_line_value,
            "space_before": self._toc_space_before,
            "space_after": self._toc_space_after,
        }

    def _form_row(
        self,
        label: str,
        widget: QWidget,
        *,
        suffix_widget: QWidget | None = None,
        parent,
    ) -> QWidget:
        return template_form_row(label, widget, suffix_widget=suffix_widget, parent=parent)

    def _role_specs(self) -> list[_TocRoleSpec]:
        specs = [_TocRoleSpec("toc_title", "目录标题", "TOC Heading")]
        for level in range(1, self._current_toc_depth() + 1):
            specs.append(_TocRoleSpec(f"toc_level{level}", f"{level} 级目录", f"TOC {level}"))
        return specs

    def _rebuild_role_list(self) -> None:
        specs = self._role_specs()
        valid_keys = {spec.key for spec in specs}
        if self._selected_role_key not in valid_keys:
            self._selected_role_key = specs[0].key

        role_list = self._toc_style_role_list
        role_list.blockSignals(True)
        try:
            for row in range(role_list.count() - 1, -1, -1):
                item = role_list.item(row)
                key = str(item.data(Qt.UserRole) or "")
                if key in valid_keys:
                    self._toc_role_items[key] = item
                    widget = role_list.itemWidget(item)
                    if widget is not None:
                        self._toc_role_widgets[key] = widget
                    continue
                widget = role_list.itemWidget(item)
                role_list.removeItemWidget(item)
                role_list.takeItem(row)
                self._toc_role_items.pop(key, None)
                self._toc_role_widgets.pop(key, None)
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()

            for index, spec in enumerate(specs):
                item = self._toc_role_items.get(spec.key)
                widget = self._toc_role_widgets.get(spec.key)
                if item is None or role_list.row(item) < 0:
                    item = QListWidgetItem()
                    role_list.insertItem(index, item)
                    widget = self._build_role_row(spec)
                    role_list.setItemWidget(item, widget)
                    self._toc_role_items[spec.key] = item
                    self._toc_role_widgets[spec.key] = widget
                else:
                    current_row = role_list.row(item)
                    if current_row != index:
                        role_list.removeItemWidget(item)
                        role_list.takeItem(current_row)
                        role_list.insertItem(index, item)
                        if widget is not None:
                            role_list.setItemWidget(item, widget)
                item.setData(Qt.UserRole, spec.key)
                item.setSizeHint(QSize(230, 62))
                if widget is not None:
                    self._sync_role_row(widget, spec)

            selected_item = self._toc_role_items[self._selected_role_key]
            role_list.setCurrentItem(selected_item)
        finally:
            role_list.blockSignals(False)
        self._sync_selected_style()

    def _style_brief(self, role_key: str) -> str:
        style = self._effective_style(role_key)
        alignment = dict(TOC_ALIGNMENT_OPTIONS).get(style.alignment, style.alignment or "左对齐")
        return f"{style.font_cn or '-'} / {_size_text(style)} / {alignment}"

    def _build_role_row(self, spec: _TocRoleSpec) -> QWidget:
        widget = QWidget(self._toc_style_role_list)
        widget.setProperty("roleKey", spec.key)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(3)

        top_row = QWidget(widget)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        title = QLabel(spec.label, top_row)
        title.setObjectName("toc_list_txt")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_layout.addWidget(title)

        word_style = QLabel(spec.word_style, top_row)
        word_style.setObjectName("toc_list_lv")
        top_layout.addWidget(word_style)
        layout.addWidget(top_row)

        meta = QLabel(self._style_brief(spec.key), widget)
        meta.setObjectName("toc_preview_meta")
        meta.setWordWrap(True)
        layout.addWidget(meta)
        return widget

    def _sync_role_row(self, widget: QWidget, spec: _TocRoleSpec) -> None:
        widget.setProperty("roleKey", spec.key)
        title = widget.findChild(QLabel, "toc_list_txt")
        if title is not None:
            title.setText(spec.label)
        word_style = widget.findChild(QLabel, "toc_list_lv")
        if word_style is not None:
            word_style.setText(spec.word_style)
        meta = widget.findChild(QLabel, "toc_preview_meta")
        if meta is not None:
            meta.setText(self._style_brief(spec.key))

    def _effective_style(self, role_key: str) -> StyleConfig:
        template = self._current_template
        if template is None:
            return StyleConfig()
        style = resolve_toc_style_config(template.styles, role_key)
        return deepcopy(style) if style is not None else StyleConfig()

    def _editable_style(self, role_key: str) -> StyleConfig | None:
        template = self._current_template
        if template is None:
            return None
        style = template.styles.get(role_key)
        if style is None:
            style = self._effective_style(role_key)
            template.styles[role_key] = style
        return style

    def _sync_selected_style(self) -> None:
        style = self._effective_style(self._selected_role_key)
        title = next(
            (spec.label for spec in self._role_specs() if spec.key == self._selected_role_key),
            "目录样式",
        )
        self._toc_style_title.setText(title)
        self._sync_style_form(style)
        self._refresh_style_preview(style)

    def _refresh_style_preview(self, style: StyleConfig | None = None) -> None:
        if not hasattr(self, "_toc_inline_preview"):
            return
        preview_style = style if style is not None else self._effective_style(self._selected_role_key)
        self._toc_inline_preview.set_preview(self._selected_role_key, preview_style)

    def _sync_style_form(self, style: StyleConfig) -> None:
        self._is_style_syncing = True
        try:
            self._toc_font_cn.set_font_name(style.font_cn or "")
            self._toc_font_en.set_font_name(style.font_en or "")
            self._toc_size_combo.set_pt(style.size_pt or 12.0)
            self._toc_bold_toggle.setChecked(bool(style.bold))
            self._toc_italic_toggle.setChecked(bool(style.italic))
            _set_combo_by_data(self._toc_alignment_combo, style.alignment or "left")

            size_pt = float(style.size_pt or 12.0)
            self._toc_special_indent.set_reference_size(size_pt)
            self._toc_left_indent.set_reference_size(size_pt)
            self._toc_right_indent.set_reference_size(size_pt)
            special = resolve_style_special_indent(style)
            self._toc_special_indent.set_value(
                str(special["mode"]),
                float(special["value"]),
                str(special["unit"]),
            )
            self._toc_left_indent.set_value(style.left_indent_chars, style.left_indent_unit)
            self._toc_right_indent.set_value(style.right_indent_chars, style.right_indent_unit)

            line_kind = normalize_line_spacing_type(style.line_spacing_type)
            _set_combo_by_data(self._toc_line_type_combo, line_kind)
            self._sync_line_spacing_editor(
                line_kind,
                resolve_line_spacing_value(line_kind, style.line_spacing_pt),
            )
            self._sync_spacing_editor(self._toc_space_before, resolve_style_paragraph_spacing(style, "before"))
            self._sync_spacing_editor(self._toc_space_after, resolve_style_paragraph_spacing(style, "after"))
        finally:
            self._is_style_syncing = False

    def _sync_line_spacing_editor(self, line_kind: str, value: float) -> None:
        spin = self._toc_line_value.spin_box
        if line_kind == "exact":
            spin.setRange(1.0, 80.0)
            spin.setSingleStep(1.0)
            spin.setDecimals(1)
        else:
            spin.setRange(0.5, 5.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(1)
        self._toc_line_value.setEnabled(line_spacing_is_editable(line_kind))
        self._toc_line_value.set_value(value, "pt")
        self._toc_line_suffix.setText(line_spacing_unit_label(line_kind))

    def _sync_spacing_editor(self, input_widget: SpacingInput, spacing: dict[str, float | str]) -> None:
        unit = str(spacing["unit"])
        config = spacing_editor_config(unit)
        spin = input_widget.spin_box
        spin.setRange(float(config["min"]), float(config["max"]))
        spin.setSingleStep(float(config["step"]))
        spin.setDecimals(int(config["decimals"]))
        input_widget.setEnabled(bool(config["enabled"]))
        input_widget.set_value(float(spacing["value"]), unit)

    def _on_style_role_changed(self, current: QListWidgetItem | None, _previous=None) -> None:
        if current is None:
            return
        role_key = str(current.data(Qt.UserRole) or "toc_title")
        if role_key == self._selected_role_key:
            return
        self._selected_role_key = role_key
        self._sync_selected_style()

    def _on_toc_line_spacing_type_changed(self, *_args) -> None:
        if self._is_style_syncing:
            return
        line_kind = normalize_line_spacing_type(self._toc_line_type_combo.currentData() or "multiple")
        value = resolve_line_spacing_value(line_kind, self._toc_line_value.value())
        self._is_style_syncing = True
        try:
            self._sync_line_spacing_editor(line_kind, value)
        finally:
            self._is_style_syncing = False
        self._on_toc_style_edited()

    def _on_toc_style_edited(self, *_args) -> None:
        owner = self._owner
        if self._is_style_syncing or owner._is_syncing or self._current_template is None:
            return

        style = self._editable_style(self._selected_role_key)
        if style is None:
            return

        style.font_cn = self._toc_font_cn.selected_font()
        style.font_en = self._toc_font_en.selected_font()

        pt = self._toc_size_combo.current_pt()
        if pt is not None:
            style.size_pt = pt
            style.size_display = display_font_size_with_name(pt)
            self._toc_special_indent.set_reference_size(pt)
            self._toc_left_indent.set_reference_size(pt)
            self._toc_right_indent.set_reference_size(pt)

        style.bold = self._toc_bold_toggle.isChecked()
        style.italic = self._toc_italic_toggle.isChecked()
        style.alignment = str(self._toc_alignment_combo.currentData() or "left")

        apply_style_special_indent(
            style,
            self._toc_special_indent.mode(),
            self._toc_special_indent.value(),
            self._toc_special_indent.unit(),
        )
        style.left_indent_chars = self._toc_left_indent.value()
        style.left_indent_unit = self._toc_left_indent.unit()
        style.right_indent_chars = self._toc_right_indent.value()
        style.right_indent_unit = self._toc_right_indent.unit()

        line_kind = normalize_line_spacing_type(self._toc_line_type_combo.currentData() or "multiple")
        style.line_spacing_type = line_kind
        style.line_spacing_pt = resolve_line_spacing_value(line_kind, self._toc_line_value.value())
        style.space_before_pt = self._toc_space_before.value()
        style.space_before_unit = self._toc_space_before.unit()
        style.space_after_pt = self._toc_space_after.value()
        style.space_after_unit = self._toc_space_after.unit()

        self._rebuild_role_list()
        owner._refresh_summary()
        owner._refresh_action_state()
        owner.template_edited.emit(self._current_template)

    def clear(self) -> None:
        self._current_template = None
        self.sync_dependent_state()

    def set_template(self, template: TemplateConfig) -> None:
        self._current_template = template
        toc = template.toc
        _set_combo_by_data(self._toc_mode_combo, toc.mode)
        _set_combo_by_data(self._toc_depth_combo, toc.max_level)
        _set_combo_by_data(self._toc_insert_combo, toc.insert_position)
        self._rebuild_role_list()

    def apply_to(self, toc) -> None:
        toc.mode = str(self._toc_mode_combo.currentData() or "word_native")
        toc.max_level = int(self._toc_depth_combo.currentData() or 3)
        toc.insert_position = str(self._toc_insert_combo.currentData() or "auto")

    def sync_dependent_state(self) -> None:
        with updates_suspended(self._owner._editor_column):
            self._rebuild_role_list()
            refresh_layout_chain(self._owner._editor_column)
        refresh_layout_chain_later(self._owner._editor_column)

    def apply_theme(self) -> None:
        theme = get_theme()
        self.styles_section.setStyleSheet(
            f"""
            QLabel#toc_style_title {{
                font-size: {theme.font_size_lg + 1}px;
                color: {theme.text_primary};
                font-weight: {theme.font_weight_emphasis};
                background: transparent;
            }}
            #toc_result_strip {{
                background: {theme_rgba(theme.primary, 0.03)};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            #toc_result_preview_shell {{
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_xs}px;
            }}
            #toc_inline_preview {{
                background: transparent;
                border: none;
            }}
            #toc_result_heading,
            #toc_block_title {{
                font-size: {theme.font_size_md}px;
                color: {theme.text_primary};
                font-weight: {theme.font_weight_emphasis};
                background: transparent;
            }}
            #toc_inspector_block {{
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            QFrame#toc_style_list_frame {{
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            QLabel#toc_style_list_header {{
                font-size: {theme.font_size_md}px;
                color: {theme.text_secondary};
                background: {theme.bg_window};
                border-bottom: 1px solid {theme.border_light};
            }}
            #toc_list_lv {{
                font-size: {theme.font_size_sm}px;
                color: {theme.text_secondary};
                background: transparent;
            }}
            #toc_list_txt {{
                font-size: {theme.font_size_md}px;
                color: {theme.text_primary};
                font-weight: {theme.font_weight_emphasis};
                background: transparent;
            }}
            #toc_preview_meta {{
                font-size: {theme.font_size_sm}px;
                color: {theme.text_secondary};
                background: transparent;
            }}
            QListWidget#toc_style_role_list {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget#toc_style_role_list::item {{
                border-bottom: 1px solid {theme.border_light};
                padding: 8px 12px;
            }}
            QListWidget#toc_style_role_list::item:hover {{
                background: {theme.bg_hover};
            }}
            QListWidget#toc_style_role_list::item:selected {{
                background: {theme.primary_light};
                border-left: 3px solid {theme.primary};
            }}
            """
        )
    def _current_toc_depth(self) -> int:
        return max(1, min(int(self._toc_depth_combo.currentData() or 3), 6))


__all__ = [
    "TOC_INSERT_OPTIONS",
    "TOC_MODE_OPTIONS",
    "TOC_STYLE_KEYS",
    "TocDetailSection",
]
