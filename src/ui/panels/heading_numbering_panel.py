"""
heading_numbering_panel — 标题编号配置面板 (Unified Level Selection + Per-Level Override)

Uses the same Card/FlowSection/template form row/ToggleSwitch design language
as PageSetupDetail and StyleDetail.

Layout:
  1. Summary Card — preset overview + save/restore
  2. Scheme Card — preset selector + max levels
  3. Level Editor — sidebar navigation + two always-visible detail cards
     a. Numbering Rules card (source + action + editors)
     b. Heading Format card (source + action + editors)
  4. Non-numbered Section
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.heading_presets import get_preset_labels
from src.config.style_semantics import (
    CM_TO_PT,
    LINE_SPACING_OPTIONS,
    SPECIAL_INDENT_FIRST_LINE,
    SPECIAL_INDENT_HANGING,
    config_indent_value_to_pt,
    display_font_size_with_name,
    resolve_spacing_render_pt,
    line_spacing_display_label,
    line_spacing_is_editable,
    line_spacing_unit_label,
    normalize_line_spacing_type,
    spacing_editor_config,
    SPACING_UNIT_OPTIONS,
    resolve_style_paragraph_spacing,
    resolve_style_special_indent,
    resolve_line_spacing_value,
)
from src.config.heading_style_semantics import NON_NUMBERED_HEADING_CUSTOM
from src.config.template import StyleConfig
from src.qt_api import (
    QBrush,
    QCheckBox,
    QColor,
    QComboBox,
    QFont,
    QFontMetricsF,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPainter,
    QPen,
    QRectF,
    QPushButton,
    QSize,
    QSizePolicy,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui import (
    Badge,
    DashedSeparator,
    FlowSection,
    SummaryGrid,
    SummaryGridItem,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.style_preview_utils import (
    preview_alignment_flags,
    resolve_preview_indents_pt,
    resolve_preview_size_pt,
)
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.template_form_layout import template_form_pair_row, template_form_row
from src.shared.ui.theme import get_theme, bind_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.base_panel import BasePanel
from src.ui.heading_numbering_logic import (
    STYLE_OPTIONS,
    build_detail_state,
    build_editor_enable_state,
    build_expert_toggle_text,
    build_non_numbered_toggle_text,
    compose_display_template,
    format_csv_items,
    parse_csv_items,
    should_show_chain_separator,
)


ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
    ("justify", "两端对齐"),
)

NON_NUMBERED_STYLE_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("inherit_heading1", "沿用一级标题"),
    ("custom", "独立设置"),
)

SEPARATOR_OPTIONS: tuple[tuple[str, str, str | None], ...] = (
    ("fullwidth_space", "全角空格 (□)", "\u3000"),
    ("halfwidth_space", "半角空格 (·)", " "),
    ("tab", "制表符 (➡)", "\t"),
    ("underscore", "下划线 (_)", "_"),
    ("custom", "自定义", None),
)

SEPARATOR_COMPACT_LABELS: dict[str, str] = {
    "fullwidth_space": "□",
    "halfwidth_space": "·",
    "tab": "➡",
    "underscore": "_",
    "custom": "自定义",
}

SEPARATOR_VALUE_TO_KEY: dict[str, str] = {
    value: key
    for key, _label, value in SEPARATOR_OPTIONS
    if value is not None
}


# ── Inline Heading Preview ─────────────────────────────────

@dataclass(slots=True)
class _InlineHeadingPreviewLine:
    text: str
    rect: QRectF
    alignment: int


def _preview_line_height_px(style: StyleConfig, font_height: float, pt_to_px: float) -> float:
    kind = normalize_line_spacing_type(style.line_spacing_type)
    if kind == "exact":
        return max(font_height + 1.0, resolve_line_spacing_value(kind, style.line_spacing_pt) * pt_to_px)
    return max(font_height + 1.0, font_height * resolve_line_spacing_value(kind, style.line_spacing_pt))


def _wrap_preview_lines(metrics: QFontMetricsF, text: str, first_width: float, regular_width: float) -> list[str]:
    remaining = str(text or "").strip()
    if not remaining:
        return [""]
    lines: list[str] = []
    current_width = max(20.0, first_width)
    while remaining:
        candidate = ""
        split_index = 0
        for index, _ in enumerate(remaining, start=1):
            probe = remaining[:index]
            if metrics.horizontalAdvance(probe) <= current_width:
                candidate = probe
                split_index = index
                continue
            break
        if not candidate:
            candidate = remaining[:1]
            split_index = 1
        lines.append(candidate)
        remaining = remaining[split_index:]
        current_width = max(20.0, regular_width)
    return lines


class _InlineHeadingPreview(QFrame):
    _SIDE_PADDING = 10.0
    _TOP_PADDING = 6.0
    _BOTTOM_PADDING = 6.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hn_inline_preview")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self._style = StyleConfig()
        self._text = ""
        self._enabled = True
        self._cached_lines: list[_InlineHeadingPreviewLine] = []
        self._cached_font = QFont()
        self._cached_font_pixel_size = 0

        bind_theme(self, self._refresh_visuals)

    def set_preview(self, style: StyleConfig, text: str, *, enabled: bool = True) -> None:
        self._style = deepcopy(style)
        self._text = str(text or "")
        self._enabled = bool(enabled)
        self._rebuild_cache()
        self.updateGeometry()
        self.update()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._layout_for_width(width)[0]

    def sizeHint(self) -> QSize:
        width = 240
        return QSize(width, self.heightForWidth(width))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild_cache()

    def _refresh_visuals(self) -> None:
        self._rebuild_cache()
        self.update()

    def _layout_for_width(self, width: int) -> tuple[int, list[_InlineHeadingPreviewLine], QFont, int]:
        available_width = max(140.0, float(width) - self._SIDE_PADDING * 2.0)
        px_per_pt = max(1.0, float(self.logicalDpiY()) / 72.0)

        style = self._style or StyleConfig()
        font = QFont()
        families = [name for name in [style.font_en, style.font_cn] if name]
        if not families:
            families = [self.font().family()]
        try:
            font.setFamilies(families)
        except AttributeError:
            font.setFamily(families[-1])

        size_pt = resolve_preview_size_pt(style)
        font_pixel_size = max(10, int(round(size_pt * px_per_pt)))
        font.setPixelSize(font_pixel_size)
        font.setBold(bool(style.bold))
        font.setItalic(bool(style.italic))

        metrics = QFontMetricsF(font)
        line_height = _preview_line_height_px(style, float(metrics.height()), px_per_pt)
        indents_pt = resolve_preview_indents_pt(style, size_pt=size_pt)
        left_indent_px = indents_pt["left_pt"] * px_per_pt
        right_indent_px = indents_pt["right_pt"] * px_per_pt
        first_indent_px = indents_pt["first_pt"] * px_per_pt
        hanging_indent_px = indents_pt["hanging_pt"] * px_per_pt

        content_left = self._SIDE_PADDING + left_indent_px
        content_right = self._SIDE_PADDING + available_width - right_indent_px
        first_width = max(60.0, content_right - (content_left + first_indent_px))
        regular_width = max(60.0, content_right - (content_left + hanging_indent_px))
        wrapped_lines = _wrap_preview_lines(metrics, self._text, first_width, regular_width)

        lines: list[_InlineHeadingPreviewLine] = []
        y = self._TOP_PADDING + resolve_spacing_render_pt(
            style.space_before_pt,
            getattr(style, "space_before_unit", "pt"),
            line_height_pt=line_height / max(px_per_pt, 0.0001),
        ) * px_per_pt
        alignment = preview_alignment_flags(style.alignment)
        for index, line_text in enumerate(wrapped_lines):
            draw_x = content_left + (first_indent_px if index == 0 else hanging_indent_px)
            draw_width = first_width if index == 0 else regular_width
            lines.append(
                _InlineHeadingPreviewLine(
                    text=line_text,
                    rect=QRectF(draw_x, y, draw_width, line_height),
                    alignment=alignment,
                )
            )
            y += line_height

        total_height = y + resolve_spacing_render_pt(
            style.space_after_pt,
            getattr(style, "space_after_unit", "pt"),
            line_height_pt=line_height / max(px_per_pt, 0.0001),
        ) * px_per_pt + self._BOTTOM_PADDING
        return max(36, int(round(total_height))), lines, font, font_pixel_size

    def _rebuild_cache(self) -> None:
        height, lines, font, font_pixel_size = self._layout_for_width(self.width() or self.sizeHint().width())
        self._cached_lines = lines
        self._cached_font = font
        self._cached_font_pixel_size = font_pixel_size
        self.setMinimumHeight(height)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        theme = get_theme()

        painter.setFont(self._cached_font)
        text_color = QColor(theme.text_primary if self._enabled else theme.text_disabled)
        painter.setPen(QPen(text_color))
        for line in self._cached_lines:
            painter.drawText(line.rect, line.alignment, line.text)

        painter.end()


class _WhitespaceVisibleLineEdit(QLineEdit):
    """Show whitespace as visible symbols while preserving the raw value."""

    _TO_SYMBOL = {
        "\u3000": "\u25A1",  # □
        " ": "\u00B7",       # ·
        "\t": "\u27A1",      # ➡
    }
    _FROM_SYMBOL = {symbol: raw for raw, symbol in _TO_SYMBOL.items()}

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setRawText(text)

    def setRawText(self, raw: str) -> None:
        display = "".join(self._TO_SYMBOL.get(ch, ch) for ch in str(raw or ""))
        super().setText(display)

    def text(self) -> str:
        display = super().text()
        return "".join(self._FROM_SYMBOL.get(ch, ch) for ch in display)


class _WhitespacePresetWidget(QWidget):
    """Preset/custom whitespace editor aligned with the V0.2 separator model."""

    textChanged = Signal(str)

    def __init__(
        self,
        *,
        text: str = "",
        control_height: int = 32,
        compact_mode_width: int = 72,
        parent=None,
    ):
        super().__init__(parent)
        self._preset_values = {key: value for key, _label, value in SEPARATOR_OPTIONS if value is not None}
        self._preset_labels = {key: label for key, label, _value in SEPARATOR_OPTIONS}
        self._compact_labels = dict(SEPARATOR_COMPACT_LABELS)
        self._value_to_key = dict(SEPARATOR_VALUE_TO_KEY)
        self._custom_raw_text = ""
        self._current_mode_key = "custom"
        self._control_height = max(24, int(control_height or 34))
        self._compact_mode_width = max(60, int(compact_mode_width or 72))
        self._custom_layout_spacing = 6
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(self._control_height)

        self._mode_combo = StyledComboBox(self)
        self._mode_combo.setEditable(True)
        self._mode_combo.setInsertPolicy(QComboBox.NoInsert)
        self._mode_combo.setToolTip("选择常用分隔符，或切换到自定义。")
        self._mode_combo.setMinimumWidth(0)
        self._mode_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        apply_size_class(self._mode_combo, "md")
        combo_line_edit = self._mode_combo.lineEdit()
        if combo_line_edit is not None:
            combo_line_edit.setReadOnly(True)
            combo_line_edit.setAlignment(Qt.AlignCenter)
            combo_line_edit.setTextMargins(0, 0, 0, 0)
        for key, label, _value in SEPARATOR_OPTIONS:
            self._mode_combo.addItem(label, key)
            self._mode_combo.setItemData(self._mode_combo.count() - 1, label, Qt.ToolTipRole)

        self._edit = _WhitespaceVisibleLineEdit(parent=self)
        apply_size_class(self._edit, "md")
        self._edit.setToolTip("输入时：全角空格=□，半角空格=·，Tab=➡。")
        self._edit.setVisible(False)
        self._edit.setMinimumWidth(0)
        self._edit.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._mode_combo.activated.connect(lambda *_args: QTimer.singleShot(0, self._on_mode_activated))
        self._edit.textChanged.connect(lambda _text: self._on_edit_text_changed())
        self.setRawText(text)

    def setRawText(self, raw: str) -> None:
        raw_text = str(raw or "")
        mode_key = self._value_to_key.get(raw_text, "custom")
        if mode_key == "custom":
            self._custom_raw_text = raw_text
        self._set_mode(mode_key, emit=False)

    def text(self) -> str:
        if self._current_mode_key == "custom":
            return self._edit.text()
        return str(self._preset_values.get(self._current_mode_key, "") or "")

    def _set_mode(self, mode_key: str, *, emit: bool) -> None:
        target_mode = str(mode_key or "custom")
        index = self._mode_combo.findData(target_mode)
        blocked_combo = self._mode_combo.blockSignals(True)
        self._mode_combo.setCurrentIndex(max(index, 0))
        self._mode_combo.blockSignals(blocked_combo)

        raw_text = self._custom_raw_text if target_mode == "custom" else str(self._preset_values.get(target_mode, "") or "")
        blocked_edit = self._edit.blockSignals(True)
        self._edit.setRawText(raw_text)
        is_custom = target_mode == "custom"
        self._edit.setEnabled(is_custom)
        self._edit.setVisible(is_custom)
        self._edit.blockSignals(blocked_edit)
        self._current_mode_key = target_mode
        self._sync_mode_combo_display()
        self._sync_mode_combo_alignment()
        self._relayout_children()
        self.updateGeometry()
        if emit:
            self.textChanged.emit(self.text())

    def _on_mode_changed(self) -> None:
        if self._current_mode_key == "custom":
            self._custom_raw_text = self._edit.text()
        self._set_mode(str(self._mode_combo.currentData() or "custom"), emit=True)

    def _on_edit_text_changed(self) -> None:
        if self._current_mode_key == "custom":
            self._custom_raw_text = self._edit.text()
        self.textChanged.emit(self.text())

    def _on_mode_activated(self) -> None:
        self._set_mode(str(self._mode_combo.currentData() or "custom"), emit=True)

    def _sync_mode_combo_display(self) -> None:
        line_edit = self._mode_combo.lineEdit()
        if line_edit is None:
            return
        mode_key = str(self._mode_combo.currentData() or "custom")
        display_text = self._compact_labels.get(mode_key, self._preset_labels.get(mode_key, mode_key))
        blocked = line_edit.blockSignals(True)
        line_edit.setText(display_text)
        line_edit.blockSignals(blocked)

    def _sync_mode_combo_alignment(self) -> None:
        line_edit = self._mode_combo.lineEdit()
        if line_edit is None:
            return
        line_edit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter if self._current_mode_key == "custom" else Qt.AlignCenter)

    def _minimum_mode_combo_width(self) -> int:
        metrics = self._mode_combo.fontMetrics()
        labels = [str(self._compact_labels.get(key, self._preset_labels.get(key, key)) or "") for key in self._preset_labels]
        widest = max((metrics.horizontalAdvance(label) for label in labels), default=0)
        return max(self._compact_mode_width, widest + 34)

    def _relayout_children(self) -> None:
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        control_height = min(self._control_height, rect.height())
        y = rect.y() + max(0, (rect.height() - control_height) // 2)
        if self._current_mode_key != "custom":
            self._mode_combo.setGeometry(rect.x(), y, rect.width(), control_height)
            self._edit.setGeometry(rect.x(), y, 0, control_height)
            return

        spacing = self._custom_layout_spacing
        combo_width = min(self._minimum_mode_combo_width(), rect.width())
        if combo_width >= rect.width():
            spacing = 0
        edit_width = max(0, rect.width() - combo_width - spacing)
        self._mode_combo.setGeometry(rect.x(), y, combo_width, control_height)
        self._edit.setGeometry(rect.x() + combo_width + spacing, y, edit_width, control_height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_children()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._relayout_children()

    def sizeHint(self) -> QSize:
        width = self._minimum_mode_combo_width()
        if self._current_mode_key == "custom":
            width += self._custom_layout_spacing + 56
        return QSize(width, self._control_height)

    def minimumSizeHint(self) -> QSize:
        return QSize(self._minimum_mode_combo_width(), self._control_height)


# ── Main Panel ─────────────────────────────────────────────

class HeadingNumberingPanel(BasePanel):
    """标题编号配置面板 — 统一选级 + 局部覆盖模型。"""

    panel_title = "标题编号"
    panel_icon = "hash"
    template_edited = Signal(object)
    save_requested = Signal()

    # ━━ Setup ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _setup_ui(self) -> None:
        self._initialize_panel_state()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._build_summary_card()
        root.addWidget(self._summary_card)

        self._build_scheme_section()
        root.addWidget(self._scheme_section)

        self._build_level_editor()
        root.addWidget(self._level_editor_card)

        self._build_non_numbered_section()
        root.addWidget(self._nn_section)

        root.addStretch(1)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _initialize_panel_state(self) -> None:
        self.setObjectName("HeadingNumberingPanel")
        self._adapter = HeadingNumberingAdapter(parent=self)
        self._selected_adv_level = 1
        self._is_syncing_ui = False
        self._save_enabled = False
        self._style_editor_expanded = False
        self._expert_editor_expanded = False
        self._header_icons: list[tuple[str, QLabel]] = []
        self._header_titles: list[QLabel] = []
        self._desc_labels: list[QLabel] = []
        self._unit_labels: list[QLabel] = []

    # ━━ 1. Summary Card ━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_summary_card(self) -> None:
        self._summary_card = Card(parent=self)

        header = QWidget(self._summary_card)
        h = QHBoxLayout(header)
        h.setContentsMargins(0, 0, 0, 6)
        h.setSpacing(6)

        icon_label = QLabel(header)
        icon_label.setFixedSize(18, 18)
        self._header_icons.append(("hash", icon_label))
        h.addWidget(icon_label)

        title = QLabel("标题编号", header)
        title.setObjectName("tpl_card_title")
        self._header_titles.append(title)
        h.addWidget(title)
        h.addStretch(1)

        self._restore_btn = QPushButton("恢复", header)
        self._restore_btn.setCursor(Qt.PointingHandCursor)
        self._restore_btn.setIconSize(QSize(16, 16))
        self._restore_btn.clicked.connect(self._on_restore)
        h.addWidget(self._restore_btn)

        self._save_btn = QPushButton("保存", header)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.clicked.connect(self._on_save_requested)
        h.addWidget(self._save_btn)

        self._summary_card.add_widget(header)

        self._summary_grid = SummaryGrid(columns=6, parent=self._summary_card)
        self._summary_card.add_widget(self._summary_grid)

    # ━━ 2. Scheme Section ━━━━━━━━━━━━━━━━━━━━━━━

    def _build_scheme_section(self) -> None:
        self._scheme_section = Card(parent=self)
        self._add_card_header(self._scheme_section, "settings", "编号方案")

        # Preset combo
        self._preset_cb = StyledComboBox(self)
        self._preset_cb.setSizeAdjustPolicy(self._preset_cb.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        for key, label in get_preset_labels():
            self._preset_cb.addItem(label, key)
        self._preset_cb.setPlaceholderText("当前配置（自定义）")
        self._preset_cb.setCurrentIndex(-1)
        self._scheme_section.add_widget(
            self._form_row("编号库", self._preset_cb, parent=self._scheme_section)
        )

        # Max levels
        self._levels_input = SpacingInput(
            unit="",
            min_val=1,
            max_val=8,
            step=1,
            decimals=0,
            units=(),
            show_unit=False,
            parent=self,
        )
        levels_suffix = QLabel("级", self)
        self._unit_labels.append(levels_suffix)
        self._scheme_section.add_widget(
            self._form_row("最大级数", self._levels_input, parent=self._scheme_section, suffix=levels_suffix)
        )
        # Backward-compatible alias used by older tests/callers.
        self._levels_slider = self._levels_input.spin_box

    # ━━ 3. Level Editor ━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_level_editor(self) -> None:
        self._level_editor_card = Card(parent=self)
        self._add_card_header(self._level_editor_card, "list-ordered", "按级编辑")

        content = QWidget(self._level_editor_card)
        layout = QHBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_detail_panel_inspector(), 1)

        self._level_editor_card.add_widget(content)

    def _build_sidebar(self) -> QFrame:
        t = get_theme()
        left_frame = QFrame()
        left_frame.setObjectName("hn_list_frame")
        left_frame.setFixedWidth(t.heading_panel_sidebar_width)
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        list_header = QLabel("选择级别")
        list_header.setObjectName("hn_list_header")
        list_header.setFixedHeight(t.control_height_md)
        list_header.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(list_header)

        self._adv_list = QListWidget()
        self._adv_list.setObjectName("hn_level_list")
        self._adv_list.currentRowChanged.connect(self._on_level_selected)
        left_layout.addWidget(self._adv_list)
        return left_frame

    def _build_detail_panel(self) -> QWidget:
        detail = QWidget()
        layout = QVBoxLayout(detail)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._detail_title = QLabel("级别配置")
        self._detail_title.setObjectName("tpl_card_title")
        self._header_titles.append(self._detail_title)
        layout.addWidget(self._detail_title)

        # ── §1 编号规则 (flat section) ──
        layout.addWidget(self._section_header("编号规则"))
        self._build_numbering_section(layout)

        layout.addSpacing(4)

        # ── §2 标题格式 (flat section) ──
        layout.addWidget(self._section_header("标题格式"))
        self._build_format_section(layout)

        # ── Bottom preview ──
        self._inline_preview = _InlineHeadingPreview(detail)
        layout.addSpacing(4)
        layout.addWidget(self._inline_preview)

        layout.addStretch(1)
        return detail

    def _build_detail_panel_inspector(self) -> QWidget:
        detail = QWidget()
        layout = QVBoxLayout(detail)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self._detail_title = QLabel("级别配置")
        self._detail_title.setObjectName("hn_detail_title")
        layout.addWidget(self._detail_title)

        self._detail_hint = QLabel("先看结果，再展开需要调整的部分。")
        self._detail_hint.setObjectName("hn_detail_hint")
        self._detail_hint.setWordWrap(True)
        layout.addWidget(self._detail_hint)

        self._build_result_strip(layout)
        self._build_numbering_block(layout)
        self._build_output_block(layout)
        self._build_style_inspector(layout)
        self._build_expert_inspector(layout)

        layout.addStretch(1)
        return detail

    def _build_result_strip(self, parent_layout: QVBoxLayout) -> None:
        card = QFrame(self)
        card.setObjectName("hn_result_strip")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self._result_heading_label = QLabel("正文预览", card)
        self._result_heading_label.setObjectName("hn_result_heading")
        self._result_meta_label = QLabel("下面展示的是该级标题在正文里的实际呈现。", card)
        self._result_meta_label.setObjectName("hn_result_meta")
        layout.addWidget(self._result_heading_label)
        layout.addWidget(self._result_meta_label)

        preview_shell = QFrame(card)
        preview_shell.setObjectName("hn_result_preview_shell")
        preview_layout = QVBoxLayout(preview_shell)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_layout.setSpacing(0)

        self._inline_preview = _InlineHeadingPreview(preview_shell)
        preview_layout.addWidget(self._inline_preview)
        layout.addWidget(preview_shell)
        parent_layout.addWidget(card)

    def _build_numbering_block(self, parent_layout: QVBoxLayout) -> None:
        body_layout, _ = self._build_inspector_block(
            parent_layout,
            "编号组成",
            "决定当前级的编号外观，以及是否需要带上上级编号。",
        )
        self._build_numbering_section(body_layout)

    def _build_output_block(self, parent_layout: QVBoxLayout) -> None:
        body_layout, _ = self._build_inspector_block(
            parent_layout,
            "输出与衔接",
            "决定目录、交叉引用以及标题正文之间如何衔接。",
        )
        self._build_output_section(body_layout)

    def _build_style_inspector(self, parent_layout: QVBoxLayout) -> None:
        block = QFrame(self)
        block.setObjectName("hn_inspector_block")
        self._style_block = block
        layout = QVBoxLayout(block)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QWidget(block)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title = QLabel("标题样式", header)
        title.setObjectName("hn_block_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self._style_toggle_btn = QPushButton("展开样式细节", header)
        self._style_toggle_btn.setObjectName("hn_inline_action")
        self._style_toggle_btn.setCursor(Qt.PointingHandCursor)
        apply_size_class(self._style_toggle_btn, "sm")
        self._style_toggle_btn.clicked.connect(self._toggle_style_editor)
        header_layout.addWidget(self._style_toggle_btn)
        layout.addWidget(header)

        self._style_summary_shell = QFrame(block)
        self._style_summary_shell.setObjectName("hn_summary_shell")
        summary_layout = QVBoxLayout(self._style_summary_shell)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(6)

        badges = QWidget(self._style_summary_shell)
        badges_layout = QHBoxLayout(badges)
        badges_layout.setContentsMargins(0, 0, 0, 0)
        badges_layout.setSpacing(6)
        self._style_mode_badge = Badge("", parent=badges)
        self._style_source_badge = Badge("", parent=badges)
        badges_layout.addWidget(self._style_mode_badge, 0, Qt.AlignLeft | Qt.AlignVCenter)
        badges_layout.addWidget(self._style_source_badge, 0, Qt.AlignLeft | Qt.AlignVCenter)
        badges_layout.addStretch(1)
        summary_layout.addWidget(badges)

        self._style_summary_primary = QLabel("", self._style_summary_shell)
        self._style_summary_primary.setObjectName("hn_summary_primary")
        self._style_summary_secondary = QLabel("", self._style_summary_shell)
        self._style_summary_secondary.setObjectName("hn_summary_secondary")
        self._style_summary_secondary.setWordWrap(True)
        summary_layout.addWidget(self._style_summary_primary)
        summary_layout.addWidget(self._style_summary_secondary)
        layout.addWidget(self._style_summary_shell)

        self._style_editor_divider = QFrame(block)
        self._style_editor_divider.setObjectName("hn_editor_divider")
        self._style_editor_divider.setVisible(False)
        layout.addWidget(self._style_editor_divider)

        self._style_editor_container = QWidget(block)
        self._style_editor_container.setVisible(False)
        editor_layout = QVBoxLayout(self._style_editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(10)
        self._build_format_section(editor_layout)
        layout.addWidget(self._style_editor_container)

        parent_layout.addWidget(block)

    def _build_expert_inspector(self, parent_layout: QVBoxLayout) -> None:
        block = QFrame(self)
        block.setObjectName("hn_inspector_block")
        self._expert_block = block
        layout = QVBoxLayout(block)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QWidget(block)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title = QLabel("模板表达式", header)
        title.setObjectName("hn_block_title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self._expert_toggle_btn = QPushButton(build_expert_toggle_text(False), header)
        self._expert_toggle_btn.setObjectName("hn_inline_action")
        self._expert_toggle_btn.setCursor(Qt.PointingHandCursor)
        apply_size_class(self._expert_toggle_btn, "sm")
        self._expert_toggle_btn.clicked.connect(self._toggle_expert_editor)
        header_layout.addWidget(self._expert_toggle_btn)
        layout.addWidget(header)

        self._expert_summary_shell = QFrame(block)
        self._expert_summary_shell.setObjectName("hn_summary_shell")
        summary_layout = QVBoxLayout(self._expert_summary_shell)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(6)

        badges = QWidget(self._expert_summary_shell)
        badges_layout = QHBoxLayout(badges)
        badges_layout.setContentsMargins(0, 0, 0, 0)
        badges_layout.setSpacing(6)
        self._expert_mode_badge = Badge("", parent=badges)
        badges_layout.addWidget(self._expert_mode_badge, 0, Qt.AlignLeft | Qt.AlignVCenter)
        badges_layout.addStretch(1)
        summary_layout.addWidget(badges)

        self._expert_summary_primary = QLabel("", self._expert_summary_shell)
        self._expert_summary_primary.setObjectName("hn_summary_primary")
        self._expert_summary_label = QLabel("", self._expert_summary_shell)
        self._expert_summary_label.setObjectName("hn_summary_secondary")
        self._expert_summary_label.setWordWrap(True)
        summary_layout.addWidget(self._expert_summary_primary)
        summary_layout.addWidget(self._expert_summary_label)
        layout.addWidget(self._expert_summary_shell)

        self._expert_editor_divider = QFrame(block)
        self._expert_editor_divider.setObjectName("hn_editor_divider")
        self._expert_editor_divider.setVisible(False)
        layout.addWidget(self._expert_editor_divider)

        self._expert_editor_container = QWidget(block)
        self._expert_editor_container.setVisible(False)
        editor_layout = QVBoxLayout(self._expert_editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(10)
        self._build_expert_section(editor_layout)
        layout.addWidget(self._expert_editor_container)

        parent_layout.addWidget(block)

    def _build_inspector_block(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        description: str | None = None,
    ) -> tuple[QVBoxLayout, QFrame]:
        block = QFrame(self)
        block.setObjectName("hn_inspector_block")
        layout = QVBoxLayout(block)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title_label = QLabel(title, block)
        title_label.setObjectName("hn_block_title")
        layout.addWidget(title_label)

        if description:
            desc = QLabel(description, block)
            desc.setObjectName("hn_block_desc")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        body = QWidget(block)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)
        layout.addWidget(body)
        parent_layout.addWidget(block)
        return body_layout, block

    def _toggle_style_editor(self) -> None:
        self._style_editor_expanded = not self._style_editor_expanded
        self._refresh_style_summary()

    def _toggle_expert_editor(self) -> None:
        self._expert_editor_expanded = not self._expert_editor_expanded
        self._refresh_expert_summary()

    def _refresh_inspector_toggles(self) -> None:
        if hasattr(self, "_style_editor_container"):
            self._style_editor_container.setVisible(self._style_editor_expanded)
        if hasattr(self, "_style_editor_divider"):
            self._style_editor_divider.setVisible(self._style_editor_expanded)
        if hasattr(self, "_expert_editor_container"):
            self._expert_editor_container.setVisible(self._expert_editor_expanded)
        if hasattr(self, "_expert_editor_divider"):
            self._expert_editor_divider.setVisible(self._expert_editor_expanded)
        if hasattr(self, "_style_toggle_btn"):
            self._style_toggle_btn.setText("收起样式细节" if self._style_editor_expanded else "展开样式细节")
        if hasattr(self, "_expert_toggle_btn"):
            self._expert_toggle_btn.setText(build_expert_toggle_text(self._expert_editor_expanded))
        if hasattr(self, "_style_block"):
            _set_state_property(self._style_block, "expanded", self._style_editor_expanded)
        if hasattr(self, "_expert_block"):
            _set_state_property(self._expert_block, "expanded", self._expert_editor_expanded)

    def _refresh_result_strip(self) -> None:
        if not self._adapter.has_template or not hasattr(self, "_result_heading_label"):
            return
        level = self._selected_adv_level
        binding = self._adapter.get_binding(level)
        binding_from_preset = self._adapter.is_level_binding_from_preset(level)
        has_style_override = self._adapter.has_heading_style_override(level)
        self._result_heading_label.setText("正文预览")
        if not binding.enabled:
            meta_text = "本级已关闭编号，下面只展示标题文字本身。"
        else:
            source_text = "编号沿用预设" if binding_from_preset else "编号已在本级调整"
            style_text = "样式已独立" if has_style_override else "样式沿用继承链"
            meta_text = f"{source_text}，{style_text}。"
        self._result_meta_label.setText(meta_text)

    def _refresh_output_hint(self) -> None:
        if not self._adapter.has_template or not hasattr(self, "_ref_style_hint_label"):
            return
        level = self._selected_adv_level
        binding = self._adapter.get_binding(level)
        if not binding.enabled:
            self._ref_style_hint_label.setText("当前级未启用编号，交叉引用样式暂不会参与下级组合。")
            return

        ref_preview = self._adapter.preview_reference_number(level)
        usage = self._adapter.preview_reference_usage(level)
        if usage is None:
            text = (
                f"被下级引用时，本级编号会写成 {ref_preview}；"
                "当前预设里还没有下级在组合中引用本级编号。"
            )
        else:
            child_level, child_preview = usage
            child_preview = child_preview.replace("\t", "   ")
            text = (
                f"被下级引用时，本级编号会写成 {ref_preview}；"
                f"按当前链路，级别 {child_level} 组合后会显示为 {child_preview}。"
            )
        self._ref_style_hint_label.setText(text)

    def _refresh_style_summary(self) -> None:
        if not self._adapter.has_template or not hasattr(self, "_style_summary_primary"):
            return
        level = self._selected_adv_level
        style_source = self._adapter.get_heading_style_source(level)
        has_style_override = self._adapter.has_heading_style_override(level)
        override_text = (
            "当前级已经单独覆写标题样式。"
            if has_style_override
            else "当前级还没有单独覆写标题样式。"
        )
        self._style_summary_primary.setText(self._adapter.heading_style_summary(level))
        self._style_summary_secondary.setText(
            f"{override_text}{self._adapter.heading_style_source_text(level)}"
        )
        if hasattr(self, "_style_mode_badge"):
            self._style_mode_badge.set_text("样式独立" if has_style_override else "沿用继承")
            self._style_mode_badge.set_variant("info" if has_style_override else "neutral")

            source_badge_text = "来源未定"
            source_badge_variant = "neutral"
            if style_source == f"heading{level}":
                source_badge_text = "本级样式"
                source_badge_variant = "info"
            elif style_source == "heading":
                source_badge_text = "通用标题"
            elif style_source == "body":
                source_badge_text = "正文回退"
            elif style_source == "normal":
                source_badge_text = "普通回退"
            self._style_source_badge.set_text(source_badge_text)
            self._style_source_badge.set_variant(source_badge_variant)
        self._refresh_inspector_toggles()

    def _refresh_expert_summary(self) -> None:
        if not self._adapter.has_template or not hasattr(self, "_expert_summary_label"):
            return
        level = self._selected_adv_level
        binding = self._adapter.get_binding(level)
        raw_template = binding.display_template or "{nn}"
        using_raw = self._use_raw_cb.isChecked()
        edit_mode = "当前正在直接编辑 display_template。" if using_raw else "默认建议优先使用上面的结构化控件。"
        self._expert_summary_primary.setText(f"当前表达式：{raw_template}")
        self._expert_summary_label.setText(
            f"{edit_mode}只有复杂规则无法通过结构化控件表达时，再切换到这里。"
        )
        if hasattr(self, "_expert_mode_badge"):
            self._expert_mode_badge.set_text("表达式模式" if using_raw else "结构化优先")
            self._expert_mode_badge.set_variant("warning" if using_raw else "neutral")
        self._refresh_inspector_toggles()

    def _section_header(self, title: str) -> QWidget:
        """WPS-style flat bold section header with a dashed separator."""
        container = QWidget()
        vl = QVBoxLayout(container)
        vl.setContentsMargins(0, 6, 0, 2)
        vl.setSpacing(4)
        vl.addWidget(DashedSeparator(parent=container))
        lbl = QLabel(title, container)
        lbl.setObjectName("hn_section_title")
        self._header_titles.append(lbl)
        vl.addWidget(lbl)
        return container

    # ── Numbering rules (flat) ─────────────────────────

    def _build_numbering_section(self, parent_layout: QVBoxLayout) -> None:
        # Row 1: Enabled toggle + Number style
        self._level_enabled_switch = ToggleSwitch(self, checked=True)
        self._level_enabled_switch.toggled_signal.connect(self._on_level_enabled_changed)
        enabled_row = self._compact_form_row("启用编号", self._level_enabled_switch, parent=self)

        self._core_style_cb = StyledComboBox(self)
        self._core_style_cb.setSizeAdjustPolicy(self._core_style_cb.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        for key, desc in STYLE_OPTIONS:
            self._core_style_cb.addItem(desc, key)
        self._core_style_cb.currentIndexChanged.connect(self._on_editor_changed)
        core_style_row = self._compact_form_row("编号样式", self._core_style_cb, parent=self)
        parent_layout.addWidget(
            template_form_pair_row(
                enabled_row,
                core_style_row,
                parent=self,
                column_stretches=(0, 1),
                normalize_labels=True,
            )
        )

        # Row 2: Prefix / Suffix
        self._prefix_edit = QLineEdit(self)
        self._prefix_edit.setPlaceholderText("如: 第")
        apply_size_class(self._prefix_edit, "md")
        self._prefix_edit.textEdited.connect(self._on_editor_changed)

        self._suffix_edit = QLineEdit(self)
        self._suffix_edit.setPlaceholderText("如: 章")
        apply_size_class(self._suffix_edit, "md")
        self._suffix_edit.textEdited.connect(self._on_editor_changed)

        prefix_row = self._compact_form_row("前缀", self._prefix_edit, parent=self)
        suffix_row = self._compact_form_row("后缀", self._suffix_edit, parent=self)
        parent_layout.addWidget(
            template_form_pair_row(
                prefix_row,
                suffix_row,
                parent=self,
                column_stretches=(1, 1),
                normalize_labels=True,
            )
        )

        # Row 3: Chain + separator
        self._chain_cb = StyledComboBox(self)
        self._chain_cb.setSizeAdjustPolicy(self._chain_cb.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self._chain_cb.currentIndexChanged.connect(self._on_chain_selected)

        self._chain_sep_edit = QLineEdit(self)
        self._chain_sep_edit.setFixedWidth(50)
        self._chain_sep_edit.setAlignment(Qt.AlignCenter)
        apply_size_class(self._chain_sep_edit, "md")
        self._chain_sep_edit.textEdited.connect(self._on_chain_sep_edited)
        self._chain_sep_lbl_row = self._compact_form_row("级间分隔符", self._chain_sep_edit, parent=self)
        chain_row = self._compact_form_row("带上上级编号", self._chain_cb, parent=self)
        parent_layout.addWidget(
            template_form_pair_row(
                chain_row,
                self._chain_sep_lbl_row,
                parent=self,
                column_stretches=(1, 0),
            )
        )

    def _build_output_section(self, parent_layout: QVBoxLayout) -> None:
        # Row 1: TOC toggle + Start at
        self._toc_switch = ToggleSwitch(self, checked=True)
        self._toc_switch.toggled_signal.connect(self._on_detail_toc_changed)
        toc_row = self._compact_form_row("计入目录", self._toc_switch, parent=self)

        self._start_at_input = SpacingInput(
            unit="", min_val=0, max_val=99, step=1, decimals=0,
            units=(), show_unit=False, parent=self,
        )
        self._start_at_input.value_changed.connect(self._on_start_at_changed)
        start_at_row = self._compact_form_row("起始编号", self._start_at_input, parent=self)
        parent_layout.addWidget(
            template_form_pair_row(
                toc_row,
                start_at_row,
                parent=self,
                column_stretches=(0, 1),
            )
        )

        # Row 2: Reference style + title separator
        self._ref_style_cb = StyledComboBox(self)
        self._ref_style_cb.setSizeAdjustPolicy(self._ref_style_cb.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        for key, desc in STYLE_OPTIONS:
            self._ref_style_cb.addItem(desc, key)
        self._ref_style_cb.currentIndexChanged.connect(self._on_ref_style_edited)
        ref_style_row = self._compact_form_row("交叉引用样式", self._ref_style_cb, parent=self)

        self._title_sep_edit = _WhitespacePresetWidget(parent=self)
        self._title_sep_edit.setToolTip("标题编号和正文之间的分隔符。0.2 设计支持空格、全角空格、Tab 与自定义。")
        self._title_sep_edit.setMinimumWidth(132)
        self._title_sep_edit.setMaximumWidth(176)
        self._title_sep_edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._title_sep_edit.textChanged.connect(self._on_title_sep_edited)
        title_sep_row = self._compact_form_row("标题分隔符", self._title_sep_edit, parent=self)
        title_sep_row.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        parent_layout.addWidget(
            template_form_pair_row(
                ref_style_row,
                title_sep_row,
                parent=self,
                column_stretches=(1, 0),
                normalize_labels=True,
            )
        )
        self._ref_style_hint_label = QLabel("", self)
        self._ref_style_hint_label.setObjectName("hn_summary_secondary")
        self._ref_style_hint_label.setWordWrap(True)
        parent_layout.addWidget(self._ref_style_hint_label)

    def _build_expert_section(self, parent_layout: QVBoxLayout) -> None:
        raw_row = QWidget()
        raw_layout = QHBoxLayout(raw_row)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        raw_layout.setSpacing(8)

        self._use_raw_cb = QCheckBox("改用模板表达式", self)
        self._use_raw_cb.toggled.connect(self._on_use_raw_toggled)
        raw_layout.addWidget(self._use_raw_cb)

        self._raw_template_edit = QLineEdit(self)
        self._raw_template_edit.setPlaceholderText("例如: {parent.nn}-{cn}")
        self._raw_template_edit.setEnabled(False)
        self._raw_template_edit.setMinimumWidth(180)
        apply_size_class(self._raw_template_edit, "md")
        self._raw_template_edit.textEdited.connect(self._on_raw_template_edited)
        raw_layout.addWidget(self._raw_template_edit, 1)
        parent_layout.addWidget(raw_row)

    # ── Heading format (flat) ─────────────────────────

    def _build_format_section(self, parent_layout: QVBoxLayout) -> None:
        # Font row: CN + EN
        self._hd_font_cn = FontCombo(lang="cn", parent=self)
        self._hd_font_cn.font_changed.connect(self._on_heading_format_edited)
        self._hd_font_en = FontCombo(lang="en", parent=self)
        self._hd_font_en.font_changed.connect(self._on_heading_format_edited)
        font_cn_row = self._compact_form_row("中文字体", self._hd_font_cn, parent=self)
        font_en_row = self._compact_form_row("英文字体", self._hd_font_en, parent=self)
        parent_layout.addWidget(
            template_form_pair_row(
                font_cn_row,
                font_en_row,
                parent=self,
                column_stretches=(1, 1),
                normalize_labels=True,
            )
        )

        # Size + emphasis row
        self._hd_size_combo = SizeCombo(self)
        self._hd_size_combo.size_changed.connect(self._on_heading_format_edited)
        self._hd_size_combo.currentTextChanged.connect(self._on_heading_format_edited)

        self._hd_bold = ToggleSwitch(self, checked=False)
        self._hd_bold.toggled_signal.connect(self._on_heading_format_edited)
        self._hd_italic = ToggleSwitch(self, checked=False)
        self._hd_italic.toggled_signal.connect(self._on_heading_format_edited)

        emphasis_w = QWidget(self)
        em_layout = QHBoxLayout(emphasis_w)
        em_layout.setContentsMargins(0, 0, 0, 0)
        em_layout.setSpacing(8)
        bold_lbl = QLabel("加粗")
        self._desc_labels.append(bold_lbl)
        italic_lbl = QLabel("斜体")
        self._desc_labels.append(italic_lbl)
        em_layout.addWidget(bold_lbl)
        em_layout.addWidget(self._hd_bold)
        em_layout.addSpacing(8)
        em_layout.addWidget(italic_lbl)
        em_layout.addWidget(self._hd_italic)
        em_layout.addStretch(1)

        size_row = self._compact_form_row("字号", self._hd_size_combo, parent=self)
        emphasis_row = self._compact_form_row("强调", emphasis_w, parent=self)
        parent_layout.addWidget(
            template_form_pair_row(
                size_row,
                emphasis_row,
                parent=self,
                column_stretches=(1, 1),
                normalize_labels=True,
            )
        )

        # Alignment
        self._hd_alignment = StyledComboBox(self)
        self._hd_alignment.setSizeAdjustPolicy(self._hd_alignment.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        for value, label in ALIGNMENT_OPTIONS:
            self._hd_alignment.addItem(label, value)
        self._hd_alignment.currentIndexChanged.connect(self._on_heading_format_edited)
        parent_layout.addWidget(
            self._compact_form_row("对齐方式", self._hd_alignment, parent=self)
        )

        # Spacing: line type + line value
        self._hd_line_type = StyledComboBox(self)
        self._hd_line_type.setSizeAdjustPolicy(self._hd_line_type.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        for value, label in LINE_SPACING_OPTIONS:
            self._hd_line_type.addItem(label, value)
        self._hd_line_type.currentIndexChanged.connect(self._on_heading_line_type_changed)

        self._hd_line_value = SpacingInput(
            unit="pt", min_val=0.5, max_val=60.0, step=0.5, decimals=1,
            units=("pt",), show_unit=False, parent=self,
        )
        self._hd_line_value.value_changed.connect(self._on_heading_spacing_edited)
        hd_lv_suffix = QLabel("磅", self)
        self._unit_labels.append(hd_lv_suffix)

        self._hd_space_before = SpacingInput(
            unit="pt", min_val=0.0, max_val=80.0, step=1.0, decimals=1,
            units=SPACING_UNIT_OPTIONS, show_unit=True, unit_inline=True, parent=self,
        )
        self._hd_space_before.value_changed.connect(self._on_heading_spacing_edited)
        hd_sb_suffix = QLabel("", self)
        self._unit_labels.append(hd_sb_suffix)

        self._hd_space_after = SpacingInput(
            unit="pt", min_val=0.0, max_val=80.0, step=1.0, decimals=1,
            units=SPACING_UNIT_OPTIONS, show_unit=True, unit_inline=True, parent=self,
        )
        self._hd_space_after.value_changed.connect(self._on_heading_spacing_edited)
        hd_sa_suffix = QLabel("", self)
        self._unit_labels.append(hd_sa_suffix)

        line_type_row = self._compact_form_row("行距类型", self._hd_line_type, parent=self)
        line_value_row = self._compact_form_row(
            "行距值",
            self._hd_line_value,
            parent=self,
            suffix=hd_lv_suffix,
        )
        parent_layout.addWidget(
            template_form_pair_row(
                line_type_row,
                line_value_row,
                parent=self,
                column_stretches=(1, 1),
                normalize_labels=True,
            )
        )

        space_before_row = self._compact_form_row(
            "段前",
            self._hd_space_before,
            parent=self,
            suffix=hd_sb_suffix,
        )
        space_after_row = self._compact_form_row(
            "段后",
            self._hd_space_after,
            parent=self,
            suffix=hd_sa_suffix,
        )
        parent_layout.addWidget(
            template_form_pair_row(
                space_before_row,
                space_after_row,
                parent=self,
                column_stretches=(1, 1),
                normalize_labels=True,
            )
        )

    # ━━ 4. Non-numbered Section ━━━━━━━━━━━━━━━━━

    def _build_non_numbered_section(self) -> None:
        self._nn_section = FlowSection(build_non_numbered_toggle_text(False), expanded=False, parent=self)
        self._nn_section.expanded_changed.connect(self._sync_non_numbered_section_title)

        desc = QLabel("忽略以下列表中匹配的标题，不为其添加编号。")
        desc.setWordWrap(True)
        self._desc_labels.append(desc)
        self._nn_section.add_widget(desc)

        self._nn_texts_edit = QLineEdit(self)
        apply_size_class(self._nn_texts_edit, "md")
        self._nn_texts_edit.setPlaceholderText("如: 参考文献, 致谢, 摘要")
        self._nn_section.add_widget(
            self._form_row("跳过完整文本", self._nn_texts_edit, parent=self._nn_section)
        )

        self._nn_prefix_edit = QLineEdit(self)
        apply_size_class(self._nn_prefix_edit, "md")
        self._nn_prefix_edit.setPlaceholderText("如: 附录, 附件, Appendix")
        self._nn_section.add_widget(
            self._form_row("跳过前缀文本", self._nn_prefix_edit, parent=self._nn_section)
        )

        self._nn_style_mode_combo = StyledComboBox(self)
        for value, label in NON_NUMBERED_STYLE_MODE_OPTIONS:
            self._nn_style_mode_combo.addItem(label, value)
        self._nn_style_mode_combo.currentIndexChanged.connect(self._on_nn_style_mode_changed)
        self._nn_section.add_widget(
            self._form_row("样式来源", self._nn_style_mode_combo, parent=self._nn_section)
        )

        self._nn_style_summary = QLabel("", self)
        self._nn_style_summary.setWordWrap(True)
        self._nn_style_summary.setObjectName("hn_summary_secondary")
        self._nn_section.add_widget(self._nn_style_summary)

        self._nn_style_editor = QWidget(self)
        nn_style_layout = QVBoxLayout(self._nn_style_editor)
        nn_style_layout.setContentsMargins(0, 0, 0, 0)
        nn_style_layout.setSpacing(8)

        self._nn_font_cn = FontCombo(lang="cn", parent=self)
        self._nn_font_cn.font_changed.connect(self._on_nn_style_edited)
        self._nn_font_en = FontCombo(lang="en", parent=self)
        self._nn_font_en.font_changed.connect(self._on_nn_style_edited)
        nn_style_layout.addWidget(
            template_form_pair_row(
                self._compact_form_row("中文字体", self._nn_font_cn, parent=self),
                self._compact_form_row("英文字体", self._nn_font_en, parent=self),
                parent=self,
                column_stretches=(0, 1),
            )
        )

        self._nn_size_combo = SizeCombo(self)
        self._nn_size_combo.size_changed.connect(self._on_nn_style_edited)
        self._nn_size_combo.currentTextChanged.connect(self._on_nn_style_edited)
        self._nn_bold = ToggleSwitch(self, checked=False)
        self._nn_bold.toggled_signal.connect(self._on_nn_style_edited)
        self._nn_italic = ToggleSwitch(self, checked=False)
        self._nn_italic.toggled_signal.connect(self._on_nn_style_edited)
        nn_emphasis = QWidget(self)
        nn_emphasis_layout = QHBoxLayout(nn_emphasis)
        nn_emphasis_layout.setContentsMargins(0, 0, 0, 0)
        nn_emphasis_layout.setSpacing(8)
        nn_emphasis_layout.addWidget(QLabel("加粗", self))
        nn_emphasis_layout.addWidget(self._nn_bold)
        nn_emphasis_layout.addWidget(QLabel("斜体", self))
        nn_emphasis_layout.addWidget(self._nn_italic)
        nn_emphasis_layout.addStretch(1)
        nn_style_layout.addWidget(
            template_form_pair_row(
                self._compact_form_row("字号", self._nn_size_combo, parent=self),
                self._compact_form_row("字形", nn_emphasis, parent=self),
                parent=self,
                column_stretches=(0, 1),
            )
        )

        self._nn_alignment = StyledComboBox(self)
        for value, label in ALIGNMENT_OPTIONS:
            self._nn_alignment.addItem(label, value)
        self._nn_alignment.currentIndexChanged.connect(self._on_nn_style_edited)
        nn_style_layout.addWidget(
            self._compact_form_row("对齐方式", self._nn_alignment, parent=self)
        )

        self._nn_section.add_widget(self._nn_style_editor)

    def _sync_non_numbered_section_title(self, expanded: bool) -> None:
        if hasattr(self._nn_section, "_toggle_button"):
            self._nn_section._toggle_button.setText(build_non_numbered_toggle_text(expanded))

    # ━━ Helpers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _add_card_header(
        self, card: Card, icon_name: str, title: str, description: str | None = None,
    ) -> None:
        header = QWidget(card)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(6)

        icon_label = QLabel(header)
        icon_label.setFixedSize(18, 18)
        self._header_icons.append((icon_name, icon_label))
        layout.addWidget(icon_label)

        title_label = QLabel(title, header)
        title_label.setObjectName("tpl_card_title")
        self._header_titles.append(title_label)
        layout.addWidget(title_label)
        layout.addStretch(1)
        card.add_widget(header)

        if description:
            desc = QLabel(description, card)
            desc.setWordWrap(True)
            self._desc_labels.append(desc)
            card.add_widget(desc)

    def _form_row(
        self, label: str, widget: QWidget, *, parent,
        suffix: QWidget | None = None, label_width: int | None = None,
    ) -> QWidget:
        return template_form_row(
            label, widget, suffix_widget=suffix,
            label_width=label_width, parent=parent,
        )

    def _compact_form_row(
        self, label: str, widget: QWidget, *, parent,
        suffix: QWidget | None = None, label_width: int | None = None,
    ) -> QWidget:
        row = self._form_row(
            label,
            widget,
            parent=parent,
            suffix=suffix,
            label_width=label_width,
        )
        if label_width is None:
            row.set_label_width(row.preferred_label_width())
        return row

    # ━━ Sidebar List ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _rebuild_level_list(self) -> None:
        t = get_theme()
        self._adv_list.blockSignals(True)
        self._adv_list.clear()
        if not self._adapter.has_template:
            self._adv_list.blockSignals(False)
            return

        levels = self._adapter.max_levels
        for level in range(1, levels + 1):
            binding = self._adapter.get_binding(level)
            preview = self._adapter.preview_number(level)
            style_summary = self._sidebar_meta_text(level, binding)
            item = QListWidgetItem()
            item.setSizeHint(QSize(t.heading_panel_sidebar_width, t.control_height_md + 18))
            item.setData(Qt.UserRole, level)
            self._adv_list.addItem(item)
            self._adv_list.setItemWidget(item, self._build_level_row(level, binding, preview, style_summary))

        cur_row = max(0, min(self._selected_adv_level - 1, levels - 1))
        self._adv_list.setCurrentRow(cur_row)
        self._adv_list.blockSignals(False)
        self._sync_detail_pane()

    def _sidebar_meta_text(self, level: int, binding) -> str:
        parts = [
            "编号启用" if binding.enabled else "未启用",
            "TOC" if binding.include_in_toc else "无 TOC",
            "样式独立" if self._adapter.has_heading_style_override(level) else "样式继承",
        ]
        return " · ".join(parts)

    def _build_level_row(self, level: int, binding, preview_text: str, style_summary: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(3)

        top_row = QWidget(widget)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        lv_lbl = QLabel(f"级别 {level}")
        lv_lbl.setObjectName("hn_list_lv")
        top_layout.addWidget(lv_lbl)

        txt_lbl = QLabel(preview_text if (preview_text and binding.enabled) else "未启用")
        txt_lbl.setObjectName("hn_list_txt")
        txt_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        if binding and not binding.enabled:
            _set_disabled_visual(txt_lbl, True)
        top_layout.addWidget(txt_lbl)
        layout.addWidget(top_row)

        meta_lbl = QLabel(style_summary)
        meta_lbl.setObjectName("hn_preview_meta")
        meta_lbl.setWordWrap(True)
        if binding and not binding.enabled:
            _set_disabled_visual(meta_lbl, True)
        layout.addWidget(meta_lbl)

        return widget

    # ━━ Detail Pane Sync ━━━━━━━━━━━━━━━━━━━━━━━━

    def _on_level_selected(self, idx: int) -> None:
        self._sync_detail_pane()

    def _sync_detail_pane(self) -> None:
        if not self._adapter.has_template:
            return
        item = self._adv_list.currentItem()
        if not item:
            return
        level = item.data(Qt.UserRole)
        self._selected_adv_level = level
        binding = self._adapter.get_binding(level)
        if not binding:
            return

        self._is_syncing_ui = True

        self._detail_title.setText(f"级别 {level}")

        # ── Numbering rules — always populate editors ──
        state = build_detail_state(level, binding)
        self._level_enabled_switch.setChecked(binding.enabled)
        self._prefix_edit.setText(state.prefix)
        self._suffix_edit.setText(state.suffix)
        _select(self._core_style_cb, state.core_style)
        self._toc_switch.setChecked(state.include_in_toc)
        self._start_at_input.set_value(state.start_at, "")

        self._chain_cb.blockSignals(True)
        self._chain_cb.clear()
        for label, value in state.chain_options:
            self._chain_cb.addItem(label, value)
        _select(self._chain_cb, state.chain_value)
        self._chain_cb.blockSignals(False)
        self._chain_sep_edit.setText(state.chain_separator)

        _select(self._ref_style_cb, state.reference_core_style)
        self._title_sep_edit.setRawText(state.title_separator)
        self._raw_template_edit.setText(state.raw_template)

        self._use_raw_cb.blockSignals(True)
        self._use_raw_cb.setChecked(False)
        self._use_raw_cb.blockSignals(False)

        self._sync_chain_sep_visibility()
        self._sync_numbering_lock_state()

        # ── Heading format — always populate from resolved style ──
        self._sync_heading_style_editor(level)

        # Update inspector summaries + inline preview
        self._refresh_result_strip()
        self._refresh_output_hint()
        self._refresh_style_summary()
        self._refresh_expert_summary()
        self._refresh_inline_preview()

        self._is_syncing_ui = False

    def _sync_chain_sep_visibility(self) -> None:
        val = self._chain_cb.currentData()
        visible = should_show_chain_separator(val)
        self._chain_sep_lbl_row.setVisible(visible)

    def _sync_numbering_lock_state(self) -> None:
        """Enable/disable numbering editors based on raw template mode."""
        state = build_editor_enable_state(
            is_binding_overridden=True,  # We're in override mode if editors are visible
            use_raw_template=self._use_raw_cb.isChecked(),
        )
        self._prefix_edit.setEnabled(state.prefix)
        self._core_style_cb.setEnabled(state.core_style)
        self._suffix_edit.setEnabled(state.suffix)
        self._chain_cb.setEnabled(state.chain)
        self._chain_sep_edit.setEnabled(state.chain_separator)
        self._ref_style_cb.setEnabled(state.reference_core_style)
        self._title_sep_edit.setEnabled(state.title_separator)
        self._start_at_input.setEnabled(state.start_at)
        self._use_raw_cb.setEnabled(state.use_raw_toggle)
        self._raw_template_edit.setEnabled(state.raw_template)

    def _sync_heading_style_editor(self, level: int) -> None:
        """Sync the heading format section with the selected level's style."""
        style = self._adapter.get_heading_style(level)
        self._hd_font_cn.set_font_name(style.font_cn or "")
        self._hd_font_en.set_font_name(style.font_en or "")
        if style.size_pt:
            self._hd_size_combo.set_pt(style.size_pt)
        else:
            self._hd_size_combo.setCurrentIndex(-1)
            self._hd_size_combo.setEditText(str(style.size_display or ""))
        self._hd_bold.setChecked(bool(style.bold))
        self._hd_italic.setChecked(bool(style.italic))
        _select(self._hd_alignment, style.alignment or "justify")

        ls_type = normalize_line_spacing_type(style.line_spacing_type)
        _select(self._hd_line_type, ls_type)
        ls_value = resolve_line_spacing_value(ls_type, style.line_spacing_pt)
        ls_unit = line_spacing_unit_label(ls_type)
        self._hd_line_value.set_value(ls_value, ls_unit or "pt")
        self._hd_line_value.setEnabled(line_spacing_is_editable(ls_type))

        self._sync_heading_spacing_editor(self._hd_space_before, resolve_style_paragraph_spacing(style, "before"))
        self._sync_heading_spacing_editor(self._hd_space_after, resolve_style_paragraph_spacing(style, "after"))

    def _sync_heading_spacing_editor(self, input_widget: SpacingInput, spacing: dict[str, float | str]) -> None:
        unit = str(spacing["unit"])
        config = spacing_editor_config(unit)
        spin = input_widget.spin_box
        spin.setRange(float(config["min"]), float(config["max"]))
        spin.setSingleStep(float(config["step"]))
        spin.setDecimals(int(config["decimals"]))
        input_widget.setEnabled(bool(config["enabled"]))
        input_widget.set_value(float(spacing["value"]), unit)

    def _refresh_inline_preview(self) -> None:
        if not self._adapter.has_template:
            return
        level = self._selected_adv_level
        style = self._adapter.get_heading_style(level)
        title = self._adapter.preview_heading_text(level, f"示例标题 {level}").replace("\t", "   ")
        enabled = self._adapter.get_binding(level).enabled
        self._inline_preview.set_preview(style, title, enabled=enabled)

    # ━━ Logic: Data writes ━━━━━━━━━━━━━━━━━━━━━━

    def _on_levels_changed(self, *_args) -> None:
        if self._is_syncing_ui:
            return
        value = int(self._levels_input.value())
        if self._adapter.has_template:
            self._adapter.set_max_levels(value)
            self._mark_dirty()
            self._rebuild_level_list()
            self._refresh_summary()

    def _on_preset_changed(self, index: int) -> None:
        key = self._preset_cb.itemData(index)
        if not key or not self._adapter.has_template:
            return
        self._adapter.apply_preset(key)
        self._mark_dirty()
        self._rebuild_level_list()
        self._refresh_summary()

    def _sync_preset_display(self) -> None:
        """Update the preset combo box to reflect current state."""
        custom_text = "当前配置（自定义）"
        key = self._adapter.detect_active_preset()
        self._preset_cb.blockSignals(True)
        try:
            self._preset_cb.setPlaceholderText(custom_text)
            for i in range(self._preset_cb.count()):
                if self._preset_cb.itemData(i) == key:
                    self._preset_cb.setCurrentIndex(i)
                    self._preset_cb.setToolTip(self._preset_cb.itemText(i))
                    return
            self._preset_cb.setCurrentIndex(-1)
            self._preset_cb.setToolTip(custom_text)
        finally:
            self._preset_cb.blockSignals(False)

    def _on_level_enabled_changed(self, checked: bool) -> None:
        if self._is_syncing_ui:
            return
        if self._adapter.has_template:
            self._adapter.set_binding_field(self._selected_adv_level, "enabled", checked)
            self._mark_dirty()
            self._rebuild_level_list()

    def _on_detail_toc_changed(self, checked: bool) -> None:
        if self._is_syncing_ui:
            return
        self._adapter.set_binding_field(self._selected_adv_level, "include_in_toc", checked)
        self._mark_dirty()
        self._rebuild_level_list()

    def _on_start_at_changed(self, *_args) -> None:
        if self._is_syncing_ui:
            return
        value = int(self._start_at_input.value())
        self._adapter.set_binding_field(self._selected_adv_level, "start_at", max(0, value))
        self._mark_dirty()
        self._rebuild_level_list()

    def _on_editor_changed(self, *_args) -> None:
        if self._is_syncing_ui:
            return
        prefix = self._prefix_edit.text()
        suffix = self._suffix_edit.text()
        core_key = self._core_style_cb.currentData()
        tmpl = compose_display_template(prefix, core_key, suffix)
        self._adapter.set_binding_field(self._selected_adv_level, "display_template", tmpl)
        self._adapter.set_binding_field(self._selected_adv_level, "display_core_style", core_key)
        self._raw_template_edit.setText(tmpl)
        self._mark_dirty()
        self._rebuild_level_list()

    def _on_raw_template_edited(self, text: str) -> None:
        if self._is_syncing_ui:
            return
        self._adapter.set_binding_field(self._selected_adv_level, "display_template", text)
        self._mark_dirty()
        self._rebuild_level_list()

    def _on_chain_selected(self, *_args) -> None:
        if self._is_syncing_ui:
            return
        val = self._chain_cb.currentData()
        self._adapter.set_binding_field(self._selected_adv_level, "chain", val)
        self._sync_chain_sep_visibility()
        self._mark_dirty()
        self._rebuild_level_list()

    def _on_chain_sep_edited(self, text: str) -> None:
        if self._is_syncing_ui:
            return
        self._adapter.set_binding_field(self._selected_adv_level, "chain_separator", text)
        self._mark_dirty()
        self._rebuild_level_list()

    def _on_ref_style_edited(self, *_args) -> None:
        if self._is_syncing_ui:
            return
        self._adapter.set_binding_field(
            self._selected_adv_level, "reference_core_style", self._ref_style_cb.currentData()
        )
        self._mark_dirty()
        self._rebuild_level_list()

    def _on_title_sep_edited(self, text: str) -> None:
        if self._is_syncing_ui:
            return
        self._adapter.set_binding_field(self._selected_adv_level, "title_separator", text)
        if text == "\t":
            self._adapter.set_binding_field(self._selected_adv_level, "ooxml_separator_mode", "suff")
            self._adapter.set_binding_field(self._selected_adv_level, "ooxml_suff", "tab")
        elif text == "":
            self._adapter.set_binding_field(self._selected_adv_level, "ooxml_separator_mode", "none")
            self._adapter.set_binding_field(self._selected_adv_level, "ooxml_suff", "nothing")
        else:
            self._adapter.set_binding_field(self._selected_adv_level, "ooxml_separator_mode", "inline")
            self._adapter.set_binding_field(self._selected_adv_level, "ooxml_suff", "nothing")
        self._mark_dirty()
        self._refresh_inline_preview()

    def _on_use_raw_toggled(self, checked: bool) -> None:
        if self._is_syncing_ui:
            return
        self._sync_numbering_lock_state()
        if checked:
            self._on_raw_template_edited(self._raw_template_edit.text())
        else:
            self._on_editor_changed()

    def _on_nn_texts_changed(self, text: str) -> None:
        if self._adapter.has_template:
            self._adapter.set_non_numbered_texts(parse_csv_items(text))
            self._mark_dirty()

    def _on_nn_prefix_changed(self, text: str) -> None:
        if self._adapter.has_template:
            self._adapter.set_non_numbered_prefixes(parse_csv_items(text))
            self._mark_dirty()

    # ── Heading format writes ────────────────────

    def _on_nn_style_mode_changed(self, *_args) -> None:
        if self._is_syncing_ui or not self._adapter.has_template:
            return
        mode = str(self._nn_style_mode_combo.currentData() or "inherit_heading1")
        self._adapter.set_non_numbered_heading_style_mode(mode)
        self._mark_dirty()
        self._sync_non_numbered_style_ui()
        self._nn_style_editor.setVisible(mode == NON_NUMBERED_HEADING_CUSTOM)
        self._refresh_inline_preview()

    def _sync_non_numbered_style_ui(self) -> None:
        if not self._adapter.has_template or not hasattr(self, "_nn_style_mode_combo"):
            return
        was_syncing = self._is_syncing_ui
        self._is_syncing_ui = True
        mode = self._adapter.get_non_numbered_heading_style_mode()
        try:
            blocked = self._nn_style_mode_combo.blockSignals(True)
            try:
                _select(self._nn_style_mode_combo, mode)
            finally:
                self._nn_style_mode_combo.blockSignals(blocked)
            style = self._adapter.get_non_numbered_heading_style()
            self._nn_font_cn.set_font_name(style.font_cn or "")
            self._nn_font_en.set_font_name(style.font_en or "")
            if style.size_pt:
                self._nn_size_combo.set_pt(style.size_pt)
            else:
                self._nn_size_combo.setCurrentIndex(-1)
                self._nn_size_combo.setEditText(str(style.size_display or ""))
            self._nn_bold.setChecked(bool(style.bold))
            self._nn_italic.setChecked(bool(style.italic))
            _select(self._nn_alignment, style.alignment or "justify")
            self._nn_style_editor.setVisible(mode == NON_NUMBERED_HEADING_CUSTOM)
            source = self._adapter.get_non_numbered_heading_style_source() or "heading1"
            source_text = "沿用一级标题" if mode != NON_NUMBERED_HEADING_CUSTOM else f"独立设置（来源 {source}）"
            self._nn_style_summary.setText(
                f"{source_text}：{self._adapter.non_numbered_heading_style_summary()}"
            )
        finally:
            self._is_syncing_ui = was_syncing

    def _on_nn_style_edited(self, *_args) -> None:
        if self._is_syncing_ui or not self._adapter.has_template:
            return
        from src.config.style_semantics import parse_font_size_input

        size_raw = self._nn_size_combo.currentText()
        try:
            size_pt = parse_font_size_input(size_raw)
        except (TypeError, ValueError):
            size_pt = 12

        for field, value in [
            ("font_cn", self._nn_font_cn.selected_font()),
            ("font_en", self._nn_font_en.selected_font()),
            ("size_pt", size_pt),
            ("size_display", size_raw if not str(size_raw).replace(".", "").isdigit() else ""),
            ("bold", self._nn_bold.isChecked()),
            ("italic", self._nn_italic.isChecked()),
            ("alignment", self._nn_alignment.currentData() or "justify"),
        ]:
            self._adapter.set_non_numbered_heading_style_field(field, value)
        self._mark_dirty()
        self._sync_non_numbered_style_ui()
        self._refresh_inline_preview()

    def _on_heading_format_edited(self, *_args) -> None:
        if self._is_syncing_ui:
            return
        level = self._selected_adv_level
        a = self._adapter

        font_cn = self._hd_font_cn.selected_font()
        font_en = self._hd_font_en.selected_font()
        size_raw = self._hd_size_combo.currentText()
        bold = self._hd_bold.isChecked()
        italic = self._hd_italic.isChecked()
        alignment = self._hd_alignment.currentData() or "justify"

        from src.config.style_semantics import parse_font_size_input
        try:
            size_pt = parse_font_size_input(size_raw)
        except (TypeError, ValueError):
            size_pt = 12

        for field, value in [
            ("font_cn", font_cn), ("font_en", font_en),
            ("size_pt", size_pt), ("size_display", size_raw if not str(size_raw).replace(".", "").isdigit() else ""),
            ("bold", bold), ("italic", italic), ("alignment", alignment),
        ]:
            a.set_heading_style_field(level, field, value)

        self._mark_dirty()
        self._refresh_heading_style_feedback()

    def _on_heading_line_type_changed(self, *_args) -> None:
        if self._is_syncing_ui:
            return
        ls_type = self._hd_line_type.currentData() or "exact"
        editable = line_spacing_is_editable(ls_type)
        self._hd_line_value.setEnabled(editable)
        if not editable:
            default_val = resolve_line_spacing_value(ls_type, 0)
            self._hd_line_value.set_value(default_val, line_spacing_unit_label(ls_type) or "pt")
        self._on_heading_spacing_edited()

    def _on_heading_spacing_edited(self, *_args) -> None:
        if self._is_syncing_ui:
            return
        level = self._selected_adv_level
        a = self._adapter
        ls_type = self._hd_line_type.currentData() or "exact"
        ls_value = self._hd_line_value.value()
        a.set_heading_style_field(level, "line_spacing_type", ls_type)
        a.set_heading_style_field(level, "line_spacing_pt", ls_value)
        a.set_heading_style_field(level, "space_before_pt", self._hd_space_before.value())
        a.set_heading_style_field(level, "space_before_unit", self._hd_space_before.unit())
        a.set_heading_style_field(level, "space_after_pt", self._hd_space_after.value())
        a.set_heading_style_field(level, "space_after_unit", self._hd_space_after.unit())
        self._mark_dirty()
        self._refresh_heading_style_feedback()

    def _refresh_heading_style_feedback(self) -> None:
        """Keep local heading-format feedback in sync after style edits."""
        if not self._adapter.has_template:
            return
        self._refresh_inline_preview()
        self._refresh_style_summary()
        self._refresh_result_strip()
        self._rebuild_level_list()

    # ━━ Dirty / Refresh ━━━━━━━━━━━━━━━━━━━━━━━━━

    def _mark_dirty(self) -> None:
        if not self._adapter.has_template:
            return
        self._sync_preset_display()
        self.bridge.mark_template_dirty()
        self._refresh_result_strip()
        self._refresh_style_summary()
        self._refresh_expert_summary()
        self._refresh_action_state()
        self._emit_template_edited()

    def _emit_template_edited(self) -> None:
        if self._adapter.has_template:
            self.template_edited.emit(self._adapter.template)

    def _refresh_summary(self) -> None:
        if not self._adapter.has_template:
            self._summary_grid.set_items([
                SummaryGridItem(key="empty", label="当前状态", value="未选择模板。", column_span=6),
            ])
            return
        items_data = self._adapter.summary_items()
        grid_items = [
            SummaryGridItem(
                key=f"hn_{i}",
                label=d["label"],
                value=d["value"],
                column_span=d.get("span", 1),
            )
            for i, d in enumerate(items_data)
        ]
        self._summary_grid.set_items(grid_items)

    def _refresh_action_state(self) -> None:
        has_changes = self._adapter.has_unsaved_changes if self._adapter.has_template else False
        self._restore_btn.setEnabled(has_changes)
        self._save_btn.setEnabled(self._save_enabled)
        self._refresh_action_icons()

    def _refresh_action_icons(self) -> None:
        try:
            from src.ui.icons.catalog import get_icon
        except Exception:
            return
        t = get_theme()
        restore_color = t.primary if self._restore_btn.isEnabled() else t.text_disabled
        save_color = t.text_on_primary if self._save_btn.isEnabled() else t.text_disabled
        self._restore_btn.setIcon(get_icon("refresh-ccw", 16, restore_color))
        self._save_btn.setIcon(get_icon("save", 16, save_color))

    def _on_restore(self) -> None:
        if self._adapter.restore_snapshot():
            self._sync_from_template()
            self._emit_template_edited()

    def _on_save_requested(self) -> None:
        self.save_requested.emit()

    # ━━ Lifecycle ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _connect_signals(self) -> None:
        self._levels_input.value_changed.connect(self._on_levels_changed)
        self._preset_cb.currentIndexChanged.connect(self._on_preset_changed)
        self._nn_texts_edit.textChanged.connect(self._on_nn_texts_changed)
        self._nn_prefix_edit.textChanged.connect(self._on_nn_prefix_changed)

    def on_template_changed(self, template) -> None:
        self._adapter.set_template(template)
        self._adapter.capture_snapshot()
        self.bridge.clear_template_dirty()
        self._sync_from_template()

    def _sync_from_template(self) -> None:
        self._is_syncing_ui = True
        self._levels_input.set_value(max(1, min(self._adapter.max_levels, 8)), "")
        self._sync_preset_display()
        self._rebuild_level_list()
        self._sync_non_numbered_ui()
        self._sync_non_numbered_style_ui()
        self._refresh_summary()
        self._refresh_action_state()
        self._is_syncing_ui = False

    def _sync_non_numbered_ui(self) -> None:
        if not self._adapter.has_template:
            return
        self._nn_texts_edit.blockSignals(True)
        self._nn_texts_edit.setText(format_csv_items(self._adapter.get_non_numbered_texts()))
        self._nn_texts_edit.blockSignals(False)
        self._nn_prefix_edit.blockSignals(True)
        self._nn_prefix_edit.setText(format_csv_items(self._adapter.get_non_numbered_prefixes()))
        self._nn_prefix_edit.blockSignals(False)

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_enabled = bool(enabled)
        self._refresh_action_state()

    def capture_entry_snapshot(self) -> None:
        self._adapter.capture_snapshot()
        self._refresh_action_state()

    # ━━ Theme ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(self._build_stylesheet(t))

        title_ss = (
            f"font-size: {t.font_size_lg}px; "
            f"font-weight: {t.font_weight_emphasis}; "
            f"color: {t.primary}; background: transparent;"
        )
        desc_ss = f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        unit_ss = f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"

        for label in self._header_titles:
            label.setStyleSheet(title_ss)
        for label in self._desc_labels:
            label.setStyleSheet(desc_ss)
        for label in self._unit_labels:
            label.setStyleSheet(unit_ss)

        apply_button_variant(self._restore_btn, "ghost-primary")
        apply_button_variant(self._save_btn, "primary")
        if hasattr(self, "_style_toggle_btn"):
            apply_button_variant(self._style_toggle_btn, "ghost-primary")
        if hasattr(self, "_expert_toggle_btn"):
            apply_button_variant(self._expert_toggle_btn, "ghost-primary")

        try:
            from src.ui.icons.catalog import get_icon
            for icon_name, label in self._header_icons:
                label.setPixmap(get_icon(icon_name, 18, t.primary).pixmap(18, 18))
        except Exception:
            pass

        self._sync_combo_heights(t)
        QTimer.singleShot(0, lambda: self._sync_combo_heights(get_theme()))
        self._refresh_inspector_toggles()
        self._refresh_action_state()

    @staticmethod
    def _build_stylesheet(t) -> str:
        from src.shared.ui.input_style import build_text_input_stylesheet
        from src.shared.ui.selection_control_style import build_checkbox_stylesheet
        return f"""
            #HeadingNumberingPanel {{ background: transparent; }}

            #hn_detail_title {{
                font-size: {t.font_size_lg + 1}px;
                color: {t.text_primary};
                font-weight: {t.font_weight_emphasis};
            }}
            #hn_detail_hint {{
                font-size: {t.font_size_sm}px;
                color: {t.text_secondary};
            }}
            #hn_list_lv {{
                font-size: {t.font_size_sm}px; color: {t.text_secondary};
            }}
            #hn_list_txt {{
                font-size: {t.font_size_md}px; color: {t.text_primary};
                font-weight: {t.font_weight_emphasis};
            }}
            #hn_preview_meta {{
                font-size: {t.font_size_sm}px; color: {t.text_secondary};
            }}
            #hn_list_txt[muted="true"],
            #hn_preview_meta[muted="true"] {{ color: {t.text_disabled}; }}

            #hn_result_strip {{
                background: rgba(22, 119, 255, 0.03);
                border: 1px solid {t.border_light};
                border-radius: {t.radius_md}px;
            }}
            #hn_inspector_block {{
                background: {t.bg_card};
                border: 1px solid {t.border_light};
                border-radius: {t.radius_md}px;
            }}
            #hn_inspector_block[expanded="true"] {{
                border-color: {t.primary_hover};
            }}
            #hn_result_preview_shell {{
                background: {t.bg_card};
                border: 1px solid {t.border_light};
                border-radius: {t.radius_xs}px;
            }}
            #hn_inline_preview {{
                background: transparent;
                border: none;
            }}
            #hn_result_heading {{
                font-size: {t.font_size_md}px;
                color: {t.text_primary};
                font-weight: {t.font_weight_emphasis};
            }}
            #hn_result_meta,
            #hn_block_desc,
            #hn_summary_secondary {{
                font-size: {t.font_size_sm}px;
                color: {t.text_secondary};
            }}
            #hn_block_title,
            #hn_summary_primary {{
                font-size: {t.font_size_md}px;
                color: {t.text_primary};
                font-weight: {t.font_weight_emphasis};
            }}
            #hn_summary_shell {{
                background: {t.bg_window};
                border: 1px solid {t.border_light};
                border-radius: {t.radius_sm}px;
            }}
            #hn_editor_divider {{
                min-height: 1px;
                max-height: 1px;
                background: {t.divider};
                border: none;
            }}
            #hn_inline_action {{
                padding-left: 8px;
                padding-right: 8px;
            }}

            #hn_section_title {{
                font-size: {t.font_size_md}px; color: {t.text_primary};
                font-weight: {t.font_weight_emphasis};
            }}

            #hn_list_frame {{
                background: {t.bg_card}; border: 1px solid {t.border_light};
                border-radius: {t.radius_md}px;
            }}
            #hn_list_header {{
                font-size: {t.font_size_md}px; color: {t.text_secondary};
                background: {t.bg_window};
                border-bottom: 1px solid {t.border_light};
            }}
            QListWidget#hn_level_list {{
                background: transparent; border: none; outline: none;
            }}
            QListWidget#hn_level_list::item {{
                border-bottom: 1px solid {t.border_light};
            }}
            QListWidget#hn_level_list::item:hover {{
                background: {t.bg_hover};
            }}
            QListWidget#hn_level_list::item:selected {{
                background: {t.primary_light};
                border-left: 3px solid {t.primary};
            }}

            {build_text_input_stylesheet(
                t, "#HeadingNumberingPanel QLineEdit",
                background=t.bg_card, focus_border_color=t.primary, padding_y=0,
            )}
            {build_checkbox_stylesheet(t, selector="#HeadingNumberingPanel QCheckBox")}
        """ + build_button_stylesheet(t)

    def _sync_combo_heights(self, theme) -> None:
        reference_height = theme.control_height_md + 2
        if reference_height <= 0:
            return
        override_marker = "/* heading-panel-height-override */"
        for combo in self.findChildren(StyledComboBox):
            base_style = combo.styleSheet()
            if override_marker in base_style:
                base_style = base_style.split(override_marker, 1)[0].rstrip()
            combo.setStyleSheet(
                (
                    f"{base_style}\n{override_marker}\n"
                    f"#{combo.objectName()} {{\n"
                    f"    min-height: {reference_height}px;\n"
                    f"    max-height: {reference_height}px;\n"
                    f"    padding-top: 0px;\n"
                    f"    padding-bottom: 0px;\n"
                    f"}}\n"
                    f"#{combo.objectName()}[sizeClass=\"md\"] {{\n"
                    f"    min-height: {reference_height}px;\n"
                    f"    max-height: {reference_height}px;\n"
                    f"    padding-top: 0px;\n"
                    f"    padding-bottom: 0px;\n"
                    f"}}\n"
                ).strip()
            )
            combo.updateGeometry()


# ── Utility ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _set_disabled_visual(widget, muted: bool) -> None:
    widget.setProperty("muted", muted)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def _set_state_property(widget, name: str, value) -> None:
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.blockSignals(True)
            w.setParent(None)


def _select(combo: StyledComboBox, value) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return
