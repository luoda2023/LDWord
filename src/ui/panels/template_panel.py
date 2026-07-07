"""
template_panel — 模板管理面板（Master-Detail 架构）

与工作台同构：左侧导航卡片 + 右侧可切换详情面板。
信息分层:
  Layer 1: 模板概览 (主操作)
  Layer 2: 导入导出 (管理操作)
  Layer 3: 页面设置 / 排版样式 / 标题编号 (参数细节)
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from src.config.builtin_templates import create_builtin_template, list_builtin_template_ids
from src.config.heading_style_semantics import resolve_heading_style, resolve_non_numbered_heading_style
from src.config.library import (
    TEMPLATE_LIBRARY_DIR,
    default_template_entry,
    get_template_entry,
    is_template_library_path,
    list_template_entries,
    load_template_from_library,
)
from src.config.loader import load_template, save_template
from src.config.style_semantics import (
    CM_TO_PT,
    SPECIAL_INDENT_FIRST_LINE,
    SPECIAL_INDENT_HANGING,
    config_indent_value_to_pt,
    normalize_line_spacing_type,
    resolve_spacing_render_pt,
    resolve_line_spacing_value,
    resolve_style_special_indent,
)
from src.config.table_style_presets import color_palette, color_variant
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import (
    QApplication,
    QBrush,
    QColor,
    QDesktopServices,
    QFileDialog,
    QFileSystemWatcher,
    QFont,
    QFontMetricsF,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPen,
    QRectF,
    QPushButton,
    QSizePolicy,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui import (
    DetailPaneController,
    LibraryActionRow,
    MasterDetailShell,
    NavigationCard,
    StyleManagementBlock,
    Toast,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.dialogs import confirm, input_text
from src.shared.ui.style_preview_surface import StylePreviewSurface
from src.shared.ui.style_preview_utils import (
    preview_alignment_flags,
    resolve_preview_indents_pt,
    resolve_preview_size_pt,
)
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.adapters.field_display_names import navigation_issue_hint
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.base_panel import BasePanel
from src.ui.bridge import navigation_intent_value
from src.ui.panels.template_format import (
    build_template_page_presentation_envelope,
    build_template_preview_context,
    build_template_preview_groups,
)
from src.ui.panels.template_style_preview import TemplateStylePreview, _build_template_preview_paragraphs
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_caption_detail import CaptionDetail
from src.ui.panels.template_elements_detail import ElementsDetail
from src.ui.panels.template_table_detail import TableCaptionDetail
from src.ui.panels.template_page_detail import PageSetupDetail
from src.ui.panels.template_style_detail import StyleDetail


# ═══════════════════════════════════════════════════════════════════════
#  Built-in template registry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class _BuiltinTemplateOption:
    template_id: str
    name: str


# ═══════════════════════════════════════════════════════════════════════
#  Card definitions (Layer 1 → 2 → 3)
# ═══════════════════════════════════════════════════════════════════════

CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    # Layer 1: Primary
    "tpl_overview":  ("模板概览",  "scan-text"),
    # Layer 2: Management
    "tpl_io":        ("导入导出",  "folder-open"),
    # Layer 3: Core parameter details
    "tpl_page":      ("页面设置",  "ruler"),
    "tpl_style":     ("正文排版",  "type-outline"),
    "tpl_heading":   ("标题编号",  "list-ordered"),
    "tpl_table":     ("表格",  "table-2"),
    "tpl_header_footer": ("页眉与页脚", "panel-top"),
    "tpl_toc":       ("目录", "chart-no-axes-gantt"),
    "tpl_caption":   ("题注", "waves-arrow-down"),
}

CARD_ORDER = (
    "tpl_overview",
    "tpl_io",
    "tpl_page",
    "tpl_style",
    "tpl_heading",
    "tpl_table",
    "tpl_header_footer",
    "tpl_toc",
    "tpl_caption",
)
FIXED_CARDS = ("tpl_overview", "tpl_io")
DETAIL_CARDS = (
    "tpl_page",
    "tpl_style",
    "tpl_heading",
    "tpl_table",
    "tpl_header_footer",
    "tpl_toc",
    "tpl_caption",
)

DETAIL_REFORMAT_MODULES: dict[str, tuple[str, ...]] = {
    "tpl_page": ("page_setup", "section_format"),
    "tpl_style": ("paragraph_style",),
    "tpl_heading": ("heading_numbering",),
    "tpl_table": ("table_format",),
    "tpl_header_footer": ("header_footer",),
    "tpl_toc": ("toc",),
    "tpl_caption": ("caption",),
}

DETAIL_REFORMAT_TARGETS: dict[str, str] = {
    "tpl_page": "页面设置",
    "tpl_style": "正文排版",
    "tpl_heading": "标题编号",
    "tpl_table": "表格格式",
    "tpl_header_footer": "页眉与页脚",
    "tpl_toc": "目录",
    "tpl_caption": "题注",
}

FIRST_LOAD_LOADING_CARDS = frozenset({"tpl_page", "tpl_style", "tpl_heading", "tpl_table", "tpl_header_footer", "tpl_toc", "tpl_caption"})
STARTUP_BACKGROUND_PRELOAD_CARDS = ("tpl_heading", "tpl_header_footer", "tpl_toc")
FIRST_LOAD_LOADING_DELAY_MS = 150
DETAIL_LOADING_MIN_VISIBLE_MS = 200
DETAIL_REFRESH_MIN_VISIBLE_MS = 140
DETAIL_LOADING_SKELETONS: dict[str, tuple[tuple[str, int], ...]] = {
    "tpl_page": (("summary_3", 118), ("card_header_a", 24), ("editor_a", 186), ("card_header_b", 24), ("editor_b", 154)),
    "tpl_style": (("summary_3", 118), ("card_header_a", 24), ("editor_a", 148), ("card_header_b", 24), ("editor_b", 148), ("card_header_c", 24), ("editor_c", 148)),
    "tpl_heading": (("summary_3", 118), ("card_header_a", 24), ("editor_a", 168), ("card_header_b", 24), ("editor_b", 168), ("card_header_c", 24), ("editor_c", 168)),
    "tpl_table": (("summary_3", 118), ("card_header_a", 24), ("editor_a", 164), ("card_header_b", 24), ("editor_b", 148), ("card_header_c", 24), ("editor_c", 132)),
    "tpl_header_footer": (("summary_2", 118), ("card_header_a", 24), ("editor_a", 142), ("card_header_b", 24), ("editor_b", 210), ("card_header_c", 24), ("editor_c", 168)),
    "tpl_toc": (("summary_2", 118), ("card_header_a", 24), ("editor_a", 148), ("card_header_b", 24), ("editor_b", 188)),
    "tpl_caption": (("summary_2", 112), ("card_header_a", 24), ("editor_a", 168), ("card_header_b", 24), ("editor_b", 168)),
}


def _safe_template_file_stem(value: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(ch if ch not in forbidden else "_" for ch in str(value or "").strip())
    cleaned = cleaned.strip(" ._")
    return cleaned or "template"


class TemplateOverviewDetail(QWidget):
    """Layer 1 detail: template selector + parameter summary + edit navigation."""

    template_selected = Signal(int)      # combo index
    edit_navigate = Signal(str)          # target card_id
    new_template_requested = Signal()
    duplicate_template_requested = Signal()
    rename_template_requested = Signal()
    open_template_folder_requested = Signal()
    delete_template_requested = Signal()
    selector_open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template = create_builtin_template("default")

        # Cached refs for O(1) theme update
        self._cached_title_labels: list[QLabel] = []
        self._cached_hint_label: QLabel | None = None
        self._cached_preview_desc: QLabel | None = None
        self._cached_sep: QFrame | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # ── Card 1: Template selector ──
        self._selector_card = Card(parent=self)
        self._build_selector()
        layout.addWidget(self._selector_card)

        # ── Card 2: Parameter overview ──
        self._overview_card = Card(parent=self)
        self._build_overview()
        layout.addWidget(self._overview_card)

        # ── Card 3: Style preview ──
        self._build_preview()
        layout.addWidget(self._preview_card)

        layout.addStretch(1)

    def _build_selector(self) -> None:
        # Header
        hdr = self._make_card_header("file-text", "当前模板")
        self._selector_card.add_widget(hdr)

        # ComboBox
        self._combo = StyledComboBox(self)
        self._combo.set_full_width_mode(True)
        self._combo.currentIndexChanged.connect(self.template_selected.emit)
        self._combo.popup_about_to_show.connect(self.selector_open_requested.emit)
        self._selector_card.add_widget(self._combo)

        self._status_chip = QLabel("内置模板", self._selector_card)
        self._status_chip.setObjectName("tpl_overview_status_chip")
        self._status_chip.setAlignment(Qt.AlignCenter)
        self._status_chip.hide()

        self._template_action_row = LibraryActionRow(
            self._selector_card,
            object_name="tpl_overview_template_action_row",
        )
        self._new_template_btn = self._template_action_row.add_action(
            "new",
            "新建模板",
            object_name="tpl_overview_new_template_btn",
            icon_name="plus",
            callback=self.new_template_requested.emit,
        )
        self._duplicate_template_btn = self._template_action_row.add_action(
            "duplicate",
            "创建副本",
            object_name="tpl_overview_duplicate_template_btn",
            icon_name="copy",
            callback=self.duplicate_template_requested.emit,
        )
        self._rename_template_btn = self._template_action_row.add_action(
            "rename",
            "重命名模板",
            object_name="tpl_overview_rename_template_btn",
            icon_name="pencil-line",
            callback=self.rename_template_requested.emit,
        )
        self._open_template_folder_btn = self._template_action_row.add_action(
            "open_folder",
            "打开模板文件夹",
            object_name="tpl_overview_open_template_folder_btn",
            icon_name="folder-open",
            callback=self.open_template_folder_requested.emit,
        )
        self._delete_template_btn = self._template_action_row.add_action(
            "delete",
            "删除模板",
            object_name="tpl_overview_delete_template_btn",
            icon_name="trash-2",
            variant="ghost-danger",
            side="right",
            callback=self.delete_template_requested.emit,
        )

        self._selector_card.add_widget(self._template_action_row)

    def set_template_options(
        self,
        options: list[_BuiltinTemplateOption],
        *,
        current_template_id: str = "",
    ) -> None:
        self._combo.blockSignals(True)
        try:
            self._combo.clear()
            for option in options:
                self._combo.addItem(option.name, option.template_id)
            target_id = str(current_template_id or "").strip()
            matched = False
            for index in range(self._combo.count()):
                if str(self._combo.itemData(index) or "").strip() == target_id:
                    self._combo.setCurrentIndex(index)
                    matched = True
                    break
            if not matched and self._combo.count() > 0:
                self._combo.setCurrentIndex(0)
        finally:
            self._combo.blockSignals(False)

    def _build_overview(self) -> None:
        # Header
        hdr = self._make_card_header("square-sigma", "参数概览")
        self._overview_card.add_widget(hdr)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        self._cached_sep = sep
        self._overview_card.add_widget(sep)

        # Summary rows
        self._rows: dict[str, _SummaryRow] = {}
        for group in build_template_preview_groups(self._current_template):
            row = _SummaryRow(
                group.icon_name,
                group.label,
                group.summary,
                row_key=group.group_id,
                parent=self,
            )
            row.edit_clicked.connect(lambda _, t=group.detail_card_id: self.edit_navigate.emit(t))
            self._rows[group.group_id] = row
            self._overview_card.add_widget(row)

    def _build_preview(self) -> None:
        preview_envelope = build_template_page_presentation_envelope(
            self._current_template
        )
        self._preview_slot = StylePreviewSurface(
            self,
            object_name_prefix="tpl_overview_preview",
            renderer_kind="template_page",
            show_metadata=False,
        )
        self._cached_preview_desc = self._preview_slot.summary_label

        self._preview = TemplateStylePreview(self._preview_slot)
        self._preview.refresh(self._current_template)
        self._preview_slot.set_renderer(self._preview, renderer_kind="template_page")
        self._preview_slot.apply_envelope(preview_envelope)

        self._preview_management_block = StyleManagementBlock(
            self,
            title="样式预览",
            icon_name="eye",
            object_name_prefix="tpl_overview_preview",
            mode="template_overview_preview",
            preview_slot=self._preview_slot,
            compact_header=True,
        )
        self._preview_card = self._preview_management_block

    def _make_card_header(self, icon_name: str, title: str) -> QWidget:
        hdr = QWidget()
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(6)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(18, 18)
        lay.addWidget(icon_lbl)
        title_lbl = QLabel(title)
        self._cached_title_labels.append(title_lbl)
        lay.addWidget(title_lbl)
        lay.addStretch(1)
        # Cache icon ref
        self._header_icons = getattr(self, "_header_icons", {})
        self._header_icons[icon_name] = icon_lbl
        return hdr

    def refresh(self, cfg: TemplateConfig) -> None:
        self._current_template = cfg
        for group in build_template_preview_groups(cfg):
            row = self._rows.get(group.group_id)
            if row:
                row.set_value(group.summary)
        # Refresh preview
        self._preview.refresh(cfg)
        if hasattr(self, "_preview_slot"):
            self._preview_slot.apply_envelope(self._preview.presentation_envelope)

    def set_status_text(self, text: str) -> None:
        self._status_chip.setText(text)

    def set_template_action_state(
        self,
        *,
        can_rename: bool,
        can_delete: bool,
        rename_tooltip: str = "",
        delete_tooltip: str = "",
        folder_tooltip: str = "",
    ) -> None:
        self._rename_template_btn.setEnabled(can_rename)
        self._delete_template_btn.setEnabled(can_delete)
        self._rename_template_btn.setToolTip(rename_tooltip)
        self._delete_template_btn.setToolTip(delete_tooltip)
        self._open_template_folder_btn.setToolTip(folder_tooltip)

    def apply_theme(self) -> None:
        t = get_theme()
        if self.layout() is not None:
            self.layout().setSpacing(t.template_detail_section_gap)
        title_ss = (
            f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.primary}; background: transparent;"
        )
        for lbl in self._cached_title_labels:
            lbl.setStyleSheet(title_ss)
        self._status_chip.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.primary}; "
            f"background: {t.bg_selected}; border: 1px solid {t.border_light}; "
            f"border-radius: {t.radius_sm}px; padding: 3px 8px;"
        )
        self._template_action_row.apply_theme()
        if self._cached_hint_label:
            self._cached_hint_label.setStyleSheet(
                f"font-size: {t.font_size_sm - 1}px; color: {t.text_hint}; padding-top: 4px;"
            )
        if self._cached_preview_desc:
            self._cached_preview_desc.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
            )
        if hasattr(self, "_preview_slot") and self._preview_slot.layout() is not None:
            self._preview_slot.layout().setSpacing(t.card_content_spacing)
        if self._cached_sep:
            self._cached_sep.setStyleSheet(f"background: {t.border_light}; max-height: 1px;")
        try:
            from src.ui.icons.catalog import get_icon
            for name, lbl in getattr(self, "_header_icons", {}).items():
                lbl.setPixmap(get_icon(name, 18, t.primary).pixmap(18, 18))
        except Exception:
            pass
        self._preview.apply_theme()


# ═══════════════════════════════════════════════════════════════════════
#  Summary Row widget (reusable)
# ═══════════════════════════════════════════════════════════════════════

class _SummaryRow(QWidget):
    """Single row: icon + label + value + edit link."""

    edit_clicked = Signal(str)

    def __init__(self, icon_name: str, label: str, value: str, *, row_key: str | None = None, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._label_text = label
        self._row_key = row_key or label

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)

        self._icon_lbl = QLabel(self)
        self._icon_lbl.setFixedSize(16, 16)
        layout.addWidget(self._icon_lbl)

        self._label = QLabel(label, self)
        self._label.setFixedWidth(72)
        layout.addWidget(self._label)

        self._value = QLabel(value, self)
        self._value.setWordWrap(True)
        self._value.setMinimumWidth(0)
        self._value.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self._value, 1)

        self._edit_btn = QPushButton("编辑", self)
        self._edit_btn.setFlat(True)
        self._edit_btn.setCursor(Qt.PointingHandCursor)
        self._edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._row_key))
        layout.addWidget(self._edit_btn)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.text_secondary};"
        )
        self._value.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_primary};")
        self._edit_btn.setStyleSheet(
            f"QPushButton {{ font-size: {t.font_size_sm}px; color: {t.primary}; "
            f"border: none; background: transparent; padding: 2px 6px; }}"
            f"QPushButton:hover {{ text-decoration: underline; }}"
        )
        self._edit_btn.setMinimumHeight(22)
        self._edit_btn.setMaximumHeight(22)
        try:
            from src.ui.icons.catalog import get_icon
            self._icon_lbl.setPixmap(get_icon(self._icon_name, size=14, color=t.text_hint).pixmap(14, 14))
        except Exception:
            self._icon_lbl.setText(self._label_text[:1])


def _set_toggle_checked(toggle: ToggleSwitch, checked: bool) -> None:
    toggle.set_checked(bool(checked), animate=False)


class _ReformatToggleCard(QWidget):
    """Scene-level module switch surfaced inline in a detail header."""

    toggled = Signal(str, bool)

    def __init__(
        self,
        card_id: str,
        *,
        target_label: str,
        module_names: tuple[str, ...],
        parent=None,
    ):
        super().__init__(parent=parent)
        self._card_id = card_id
        self._target_label = target_label
        self._module_names = module_names
        self._syncing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._toggle = ToggleSwitch(self, checked=True)
        self._toggle.set_checked_track_color(get_theme().primary)
        self._toggle.toggled_signal.connect(self._on_toggled)
        layout.addWidget(self._toggle, 0, Qt.AlignVCenter)
        self._status_label = QLabel("", self)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label, 0, Qt.AlignVCenter)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def sync_state(self, *, enabled: bool, available: bool, partial: bool = False) -> None:
        self._syncing = True
        try:
            _set_toggle_checked(self._toggle, enabled)
            self._toggle.setEnabled(available)
            if not available:
                status = "未绑定当前场景"
                status_label = status
            elif partial:
                status = f"重新排版{self._target_label}：当前场景部分开启"
                status_label = "当前场景：部分开启"
            elif enabled:
                status = f"重新排版{self._target_label}：当前场景已开启"
                status_label = "当前场景：已开启"
            else:
                status = f"重新排版{self._target_label}：当前场景已跳过"
                status_label = "当前场景：已跳过"
            self.setToolTip(status)
            self._status_label.setText(status_label)
        finally:
            self._syncing = False

    def _on_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self.toggled.emit(self._card_id, bool(checked))

    def _apply_theme(self) -> None:
        self.setContentsMargins(0, 0, 0, 0)
        self._toggle.set_checked_track_color(get_theme().primary)
        self.setToolTip(self.toolTip())



class ImportExportDetail(QWidget):
    """Layer 2 detail: import / save-as / reset."""

    import_requested = Signal()
    save_as_requested = Signal()
    reset_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)

        # Header
        hdr = QWidget()
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 6)
        h_lay.setSpacing(6)
        self._hdr_icon = QLabel()
        self._hdr_icon.setFixedSize(18, 18)
        h_lay.addWidget(self._hdr_icon)
        title = QLabel("模板文件管理")
        title.setObjectName("tpl_card_title")
        h_lay.addWidget(title)
        h_lay.addStretch(1)
        card.add_widget(hdr)

        self._file_state = QLabel("模板类型：内置模板")
        self._file_state.setObjectName("tpl_io_file_state")
        self._file_state.setWordWrap(True)
        card.add_widget(self._file_state)

        self._path_state = QLabel("保存位置：未保存到文件")
        self._path_state.setObjectName("tpl_io_path_state")
        self._path_state.setWordWrap(True)
        card.add_widget(self._path_state)

        self._save_state = QLabel("保存状态：已保存")
        self._save_state.setObjectName("tpl_io_save_state")
        self._save_state.setWordWrap(True)
        card.add_widget(self._save_state)

        # Buttons
        btn_row = QWidget()
        btn_lay = QHBoxLayout(btn_row)
        btn_lay.setContentsMargins(0, 8, 0, 0)
        btn_lay.setSpacing(8)

        self._import_btn = QPushButton("导入模板")
        self._import_btn.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._import_btn, "primary")
        self._import_btn.clicked.connect(self.import_requested.emit)
        btn_lay.addWidget(self._import_btn, 1)

        self._export_btn = QPushButton("另存为")
        self._export_btn.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._export_btn, "secondary")
        self._export_btn.clicked.connect(self.save_as_requested.emit)
        btn_lay.addWidget(self._export_btn, 1)

        card.add_widget(btn_row)

        # Reset row
        reset_row = QWidget()
        r_lay = QHBoxLayout(reset_row)
        r_lay.setContentsMargins(0, 4, 0, 0)
        r_lay.setSpacing(8)

        self._reset_btn = QPushButton("恢复为内置默认模板")
        self._reset_btn.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._reset_btn, "secondary")
        self._reset_btn.clicked.connect(self.reset_requested.emit)
        r_lay.addWidget(self._reset_btn, 1)
        r_lay.addStretch(1)

        card.add_widget(reset_row)

        # Status
        self._status = QLabel("")
        self._status.setObjectName("tpl_io_status")
        self._status.setWordWrap(True)
        card.add_widget(self._status)

        layout.addWidget(card)
        layout.addStretch(1)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_file_status(self, text: str) -> None:
        self._file_state.setText(text)

    def set_path_status(self, text: str, tooltip: str = "") -> None:
        self._path_state.setText(text)
        self._path_state.setToolTip(tooltip)

    def set_save_status(self, dirty: bool) -> None:
        self._save_state.setText("保存状态：有未保存更改" if dirty else "保存状态：已保存")

    def apply_theme(self) -> None:
        t = get_theme()
        for w in self.findChildren(QLabel, "tpl_card_title"):
            w.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; color: {t.primary}; background: transparent;"
            )
        self._file_state.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_hint};")
        self._path_state.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_hint};")
        self._save_state.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_hint};")
        self._status.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")
        try:
            from src.ui.icons.catalog import get_icon
            self._hdr_icon.setPixmap(get_icon("folder-open", 18, t.primary).pixmap(18, 18))
            self._import_btn.setIcon(get_icon("folder-open", 16, t.text_on_primary))
            self._export_btn.setIcon(get_icon("download", 16, t.primary))
            self._reset_btn.setIcon(get_icon("refresh-ccw", 16, t.primary))
        except Exception:
            pass


class _PlaceholderDetail(QWidget):
    """Placeholder for future parameter editing panes."""

    def __init__(self, title: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon_name = icon_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)

        hdr = QWidget()
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 6)
        h_lay.setSpacing(6)
        self._hdr_icon = QLabel()
        self._hdr_icon.setFixedSize(18, 18)
        h_lay.addWidget(self._hdr_icon)
        t_lbl = QLabel(title)
        t_lbl.setObjectName("tpl_card_title")
        h_lay.addWidget(t_lbl)
        h_lay.addStretch(1)
        card.add_widget(hdr)

        desc = QLabel(f"「{title}」暂未开放。")
        desc.setObjectName("tpl_placeholder_desc")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        card.add_widget(desc)

        layout.addWidget(card)
        layout.addStretch(1)

    def apply_theme(self) -> None:
        t = get_theme()
        for w in self.findChildren(QLabel, "tpl_card_title"):
            w.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; color: {t.primary}; background: transparent;"
            )
        for w in self.findChildren(QLabel, "tpl_placeholder_desc"):
            w.setStyleSheet(
                f"font-size: {t.font_size_md}px; color: {t.text_hint}; padding: 40px 20px;"
            )
        try:
            from src.ui.icons.catalog import get_icon
            self._hdr_icon.setPixmap(get_icon(self._icon_name, 18, t.primary).pixmap(18, 18))
        except Exception:
            pass


class _LoadingDetail(QWidget):
    """In-place first-load skeleton overlay for heavier detail panes."""

    def __init__(self, title: str, icon_name: str, *, blocks: tuple[tuple[str, int], ...], parent=None):
        super().__init__(parent)
        self._title = title
        self._icon_name = icon_name
        self._block_specs = tuple(blocks)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(8)

        self._shell = QWidget(self)
        shell_layout = QVBoxLayout(self._shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(8)

        header = QWidget(self._shell)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        self._hdr_icon = QLabel(header)
        self._hdr_icon.setFixedSize(18, 18)
        header_layout.addWidget(self._hdr_icon)
        title_label = QLabel(title, header)
        title_label.setObjectName("tpl_card_title")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        shell_layout.addWidget(header)

        self._desc = QLabel(f"正在加载“{title}”…", self._shell)
        self._desc.setObjectName("tpl_loading_desc")
        self._desc.setWordWrap(True)
        shell_layout.addWidget(self._desc)

        self._blocks: dict[str, QFrame] = {}
        for name, height in self._block_specs:
            block = QFrame(self._shell)
            block.setObjectName(f"tpl_loading_block_{name}")
            block.setMinimumHeight(height)
            block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            if name.startswith("summary_"):
                inner = QHBoxLayout(block)
                inner.setContentsMargins(16, 14, 16, 14)
                inner.setSpacing(12)
                chip_count = 3 if name.endswith("_3") else 2
                for index in range(chip_count):
                    chip = QFrame(block)
                    chip.setObjectName(f"tpl_loading_chip_{name}_{index}")
                    chip.setMinimumHeight(52)
                    chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    inner.addWidget(chip, 1)
            elif name.startswith("editor_"):
                inner = QVBoxLayout(block)
                inner.setContentsMargins(18, 16, 18, 16)
                inner.setSpacing(10)
                for row_index in range(2):
                    row = QFrame(block)
                    row.setObjectName(f"tpl_loading_row_{name}_{row_index}")
                    row.setMinimumHeight(28)
                    row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    inner.addWidget(row)
            shell_layout.addWidget(block)
            self._blocks[name] = block

        layout.addWidget(self._shell)
        layout.addStretch(1)

    def show_overlay(self) -> None:
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tint = QColor(get_theme().bg_window)
        tint.setAlpha(210)
        painter.fillRect(self.rect(), tint)
        super().paintEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.updateGeometry()

    def apply_theme(self) -> None:
        t = get_theme()
        for w in self.findChildren(QLabel, "tpl_card_title"):
            w.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; color: {t.primary}; background: transparent;"
            )
        self._desc.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")
        shell_style = (
            f"background: transparent; border: none;"
        )
        self._shell.setStyleSheet(shell_style)
        block_style = (
            f"background: {t.bg_card}; border: 1px solid {t.border_light}; border-radius: {t.radius_md}px;"
        )
        header_block_style = (
            f"background: {t.bg_hover}; border: 1px solid {t.border_light}; border-radius: {t.radius_sm}px;"
        )
        for name, block in self._blocks.items():
            if name.startswith("card_header_"):
                block.setStyleSheet(header_block_style)
            else:
                block.setStyleSheet(block_style)
        chip_style = (
            f"background: {t.bg_hover}; border: 1px solid {t.border_light}; border-radius: {t.radius_sm}px;"
        )
        row_style = (
            f"background: {t.bg_hover}; border: 1px solid {t.border_light}; border-radius: {t.radius_sm}px;"
        )
        for chip in self.findChildren(QFrame):
            object_name = chip.objectName()
            if object_name.startswith("tpl_loading_chip_"):
                chip.setStyleSheet(chip_style)
            elif object_name.startswith("tpl_loading_row_"):
                chip.setStyleSheet(row_style)
        try:
            from src.ui.icons.catalog import get_icon
            self._hdr_icon.setPixmap(get_icon(self._icon_name, 18, t.primary).pixmap(18, 18))
        except Exception:
            pass
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.update()


class _RefreshOverlay(QWidget):
    """Lightweight refresh transition overlay for the visible detail pane."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.hide()

    def show_overlay(self) -> None:
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tint = QColor(get_theme().bg_window)
        tint.setAlpha(150)
        painter.fillRect(self.rect(), tint)

    def apply_theme(self) -> None:
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.update()


# ═══════════════════════════════════════════════════════════════════════
#  Main Panel (Master-Detail)
# ═══════════════════════════════════════════════════════════════════════

class TemplatePanel(BasePanel):
    """Master-detail template management panel."""

    panel_title = "模板管理"
    panel_icon = "file-text"

    def _setup_ui(self) -> None:
        self.setObjectName("TemplatePanel")
        self._current_template_id = self.bridge.current_template_id()
        self._current_template_path = self.bridge.current_template_path()
        self._current_template_source = self.bridge.current_template_source()
        self._persisted_template_snapshot = None
        self._bridge_template_echo_depth = 0
        self._template_library_refresh_pending = False
        self._template_library_watcher = QFileSystemWatcher(self)

        current_template = self.bridge.current_template()
        if current_template is not None:
            self._current_template = current_template
            if not self.bridge.is_template_dirty():
                self._remember_persisted_template_state(current_template)
        else:
            scene = self.bridge.current_scene()
            scene_template_id = ""
            if scene is not None:
                scene_template_id = str(
                    getattr(scene, "template_id", "")
                    or getattr(scene, "default_template_id", "")
                    or ""
                ).strip()

            if scene_template_id:
                entry = get_template_entry(scene_template_id)
                self._current_template = load_template_from_library(scene_template_id)
                self._current_template_id = scene_template_id
                self._current_template_path = str(entry.path) if entry is not None else ""
                self._current_template_source = "library" if entry is not None else "builtin"
            else:
                default_entry = default_template_entry()
                if default_entry is not None:
                    self._current_template = load_template_from_library(default_entry.config_id)
                    self._current_template_id = default_entry.config_id
                    self._current_template_path = str(default_entry.path)
                    self._current_template_source = "library"
                else:
                    self._current_template = create_builtin_template("default")
                    self._current_template_id = "default"
                    self._current_template_source = "builtin"
            self._remember_persisted_template_state(self._current_template)

        self._shell = MasterDetailShell(
            self,
            panel_name="TemplatePanel",
            nav_object_name="tpl_navigation",
            detail_object_name="tpl_detail",
            detail_content_object_name="tpl_detail_content",
        )
        self._layout = self._shell.layout
        self._nav_rail = self._shell.nav_rail
        self._detail_scroll = self._shell.detail_scroll
        self._detail_container = self._shell.detail_container
        self._detail_layout = self._shell.detail_layout

        # ── Build detail panes ──
        self._overview_detail = TemplateOverviewDetail()
        self._io_detail = ImportExportDetail()
        self._detail_factories = {
            "tpl_page": PageSetupDetail,
            "tpl_style": StyleDetail,
            "tpl_heading": lambda: HeadingNumberingPanel(self.bridge),
            "tpl_table": TableCaptionDetail,
            "tpl_header_footer": lambda: ElementsDetail(scope="header_footer"),
            "tpl_toc": lambda: ElementsDetail(scope="toc"),
            "tpl_caption": CaptionDetail,
        }
        self._detail_attr_names = {
            "_page_detail": "tpl_page",
            "_style_detail": "tpl_style",
            "_heading_detail": "tpl_heading",
            "_table_detail": "tpl_table",
            "_header_footer_detail": "tpl_header_footer",
            "_toc_detail": "tpl_toc",
            "_caption_detail": "tpl_caption",
        }
        self._loaded_detail_ids: set[str] = {"tpl_overview", "tpl_io"}
        self._retired_detail_placeholders: list[QWidget] = []
        self._reformat_toggle_cards: dict[str, _ReformatToggleCard] = {}
        self._loading_detail: _LoadingDetail | None = None
        self._refresh_overlay: _RefreshOverlay | None = None
        self._loading_timer: QTimer | None = None
        self._loading_min_visible_timer: QTimer | None = None
        self._loading_visible_since: float | None = None
        self._pending_detail_card_id: str | None = None
        self._pending_real_detail_switch_card_id: str | None = None

        self._detail_map: dict[str, QWidget] = {
            "tpl_overview": self._overview_detail,
            "tpl_io": self._io_detail,
        }
        for card_id in DETAIL_CARDS:
            title, icon = CARD_DEFINITIONS[card_id]
            self._detail_map[card_id] = _PlaceholderDetail(title, icon)
        self._details = DetailPaneController(
            self._detail_container,
            self._detail_layout,
            self._detail_scroll,
        )
        self._details.register_details(self._detail_map)
        self._current_detail: QWidget | None = self._details.current_detail
        self._return_navigation_intent: dict[str, object] | None = None

        self._entry_context_bar = QWidget(self._detail_container)
        self._entry_context_bar.setObjectName("tpl_entry_context_bar")
        entry_layout = QVBoxLayout(self._entry_context_bar)
        entry_layout.setContentsMargins(10, 8, 10, 8)
        entry_layout.setSpacing(3)
        self._entry_context_title = QLabel("", self._entry_context_bar)
        self._entry_context_title.setObjectName("tpl_entry_context_title")
        self._entry_context_title.setWordWrap(True)
        self._entry_context_detail = QLabel("", self._entry_context_bar)
        self._entry_context_detail.setObjectName("tpl_entry_context_detail")
        self._entry_context_detail.setWordWrap(True)
        entry_layout.addWidget(self._entry_context_title)
        entry_layout.addWidget(self._entry_context_detail)
        self._entry_context_bar.setVisible(False)
        self._detail_layout.addWidget(self._entry_context_bar)

        self._return_bar = QWidget(self._detail_container)
        self._return_bar.setObjectName("tpl_return_bar")
        return_layout = QHBoxLayout(self._return_bar)
        return_layout.setContentsMargins(0, 0, 0, 8)
        return_layout.setSpacing(8)
        self._return_label = QLabel("从执行问题进入", self._return_bar)
        self._return_btn = QPushButton("返回执行", self._return_bar)
        self._return_btn.clicked.connect(self._navigate_return_target)
        return_layout.addWidget(self._return_label)
        return_layout.addStretch(1)
        return_layout.addWidget(self._return_btn)
        self._return_bar.setVisible(False)
        self._detail_layout.addWidget(self._return_bar)

        # ── Build navigation cards (Layer 1 + 2, then header, then Layer 3) ──
        self._nav_cards: dict[str, NavigationCard] = {}

        # Layer 1 + 2: Fixed cards
        for card_id in FIXED_CARDS:
            title, icon = CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

        # Section header between Layer 2 and Layer 3
        self._nav_rail.add_section_header("参数编辑")

        # Layer 3: Detail cards
        for card_id in DETAIL_CARDS:
            title, icon = CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

        # ── Initial state ──
        self._refresh_template_selector_options()
        self._set_detail_templates(self._current_template)
        self._sync_template_file_status()
        self._overview_detail.refresh(self._current_template)
        self._refresh_subtitles()
        self._sync_reformat_toggles()
        self._set_detail_save_enabled(self.bridge.is_template_dirty())
        if self.bridge.current_template() is None:
            self._publish_current_template(emit_signal=False)
        # Manually show initial detail (signals not yet connected)
        self._show_detail("tpl_overview")
        self._nav_rail.select_card("tpl_overview")
        self._apply_theme()
        self._setup_template_library_watcher()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        # Navigation
        self._nav_rail.card_selected.connect(self._show_detail)

        # Overview interactions
        self._overview_detail.template_selected.connect(self._on_template_selected)
        self._overview_detail.edit_navigate.connect(self._nav_rail.select_card)
        self._overview_detail.new_template_requested.connect(self._on_new_template_requested)
        self._overview_detail.duplicate_template_requested.connect(self._on_duplicate_template_requested)
        self._overview_detail.rename_template_requested.connect(self._on_rename_template_requested)
        self._overview_detail.open_template_folder_requested.connect(self._on_open_template_folder_requested)
        self._overview_detail.delete_template_requested.connect(self._on_delete_template_requested)
        self._overview_detail.selector_open_requested.connect(self._refresh_template_library_from_disk)
        self._template_library_watcher.directoryChanged.connect(self._on_template_library_path_changed)
        self._template_library_watcher.fileChanged.connect(self._on_template_library_path_changed)

        # Import/Export
        self._io_detail.import_requested.connect(self._on_import)
        self._io_detail.save_as_requested.connect(self._save_current_template_as)
        self._io_detail.reset_requested.connect(self._on_reset)

        # Bridge
        self.bridge.scene_changed.connect(self.on_scene_changed)
        self.bridge.template_changed.connect(self.on_template_changed)
        self.bridge.template_dirty_changed.connect(self._on_template_dirty_changed)

    # ──────────────────────────────────────────────────────
    # Detail switching
    # ──────────────────────────────────────────────────────

    def __getattr__(self, name: str):
        detail_attrs = self.__dict__.get("_detail_attr_names", {})
        card_id = detail_attrs.get(name)
        if card_id:
            return self._ensure_detail_loaded(card_id)
        raise AttributeError(f"{type(self).__name__} object has no attribute {name!r}")

    def _show_detail(self, card_id: str) -> None:
        is_first_detail_load = card_id not in self._loaded_detail_ids and card_id in self._detail_factories
        use_loading = is_first_detail_load and card_id in FIRST_LOAD_LOADING_CARDS
        if use_loading:
            self._pending_real_detail_switch_card_id = card_id
            self._schedule_loading_detail(card_id)
            QTimer.singleShot(0, lambda cid=card_id: self._complete_first_load_detail(cid))
            return
        self._show_loaded_detail(card_id)

    def _complete_first_load_detail(self, card_id: str) -> None:
        if self._pending_real_detail_switch_card_id != card_id:
            return
        self._ensure_detail_loaded(card_id)
        self._finish_detail_transition(card_id)

    def _show_loaded_detail(self, card_id: str) -> None:
        self._ensure_detail_loaded(card_id)
        self._finish_detail_transition(card_id)

    def handle_navigation_intent(self, intent) -> None:
        self._set_return_navigation_intent(intent)
        self._set_entry_context(intent)
        card_id = str(navigation_intent_value(intent, "card_id", "") or "").strip()
        if not card_id:
            return
        if card_id in self._detail_map or card_id in self._detail_factories:
            self._nav_rail.select_card(card_id)
            QTimer.singleShot(0, lambda: self._focus_navigation_field(card_id, intent))

    def _focus_navigation_field(self, card_id: str, intent) -> None:
        field_id = str(navigation_intent_value(intent, "field_id", "") or "").strip()
        if not field_id:
            payload = navigation_intent_value(intent, "payload", {}) or {}
            if isinstance(payload, dict):
                field_id = str(
                    payload.get("issue_key")
                    or payload.get("repair_target_key")
                    or ""
                ).strip()
        if not field_id:
            return
        detail = self._detail_map.get(card_id)
        if detail is None or not hasattr(detail, "focus_navigation_field"):
            return
        detail.focus_navigation_field(field_id)

    def _set_return_navigation_intent(self, intent) -> None:
        panel_id = str(navigation_intent_value(intent, "return_panel_id", "") or "").strip()
        card_id = str(navigation_intent_value(intent, "return_card_id", "") or "").strip()
        if not panel_id:
            self._return_navigation_intent = None
            self._return_label.setText("从执行问题进入")
            self._return_bar.setVisible(False)
            return
        payload = navigation_intent_value(intent, "payload", {}) or {}
        if not isinstance(payload, dict):
            payload = {}
        active_issue_id = str(
            navigation_intent_value(intent, "active_issue_id", "")
            or payload.get("active_issue_id")
            or payload.get("issue_item_id")
            or ""
        ).strip()
        issue_key = str(
            navigation_intent_value(intent, "field_id", "")
            or payload.get("issue_key")
            or ""
        ).strip()
        issue_title = str(payload.get("issue_title") or "").strip()
        issue_type = str(
            navigation_intent_value(intent, "issue_id", "")
            or payload.get("issue_type")
            or ""
        ).strip()
        self._return_navigation_intent = {
            "panel_id": panel_id,
            "card_id": card_id,
        }
        if active_issue_id:
            self._return_navigation_intent["active_issue_id"] = active_issue_id
        if payload:
            self._return_navigation_intent["payload"] = dict(payload)
            if active_issue_id and not self._return_navigation_intent["payload"].get("active_issue_id"):
                self._return_navigation_intent["payload"]["active_issue_id"] = active_issue_id
        hint = str(payload.get("issue_display_name") or "").strip()
        if not hint:
            hint = navigation_issue_hint(
                issue_title,
                issue_key,
                issue_type=issue_type,
            )
        self._return_label.setText(
            f"从执行问题进入：{hint}" if hint else "从执行问题进入"
        )
        self._return_bar.setVisible(True)

    def _set_entry_context(self, intent) -> None:
        payload = navigation_intent_value(intent, "payload", {}) or {}
        if not isinstance(payload, dict):
            payload = {}

        title = str(payload.get("entry_context_title") or "").strip()
        detail = str(payload.get("entry_context_detail") or "").strip()
        action = str(payload.get("entry_context_action") or "").strip()

        if not title:
            issue_title = str(payload.get("issue_title") or "").strip()
            if issue_title:
                title = f"来自执行问题：{issue_title}"
                detail = detail or str(payload.get("issue_summary") or "").strip()
                action = action or "调整后返回执行页复检"

        if not title:
            return_panel_id = str(navigation_intent_value(intent, "return_panel_id", "") or "").strip()
            if return_panel_id == "scene":
                preview_context = build_template_preview_context(
                    self._current_template,
                    detail=self._scene_template_context_detail(),
                )
                title = preview_context.title
                detail = detail or preview_context.detail
                action = action or preview_context.action

        if not title:
            self._entry_context_title.setText("")
            self._entry_context_detail.setText("")
            self._entry_context_bar.setVisible(False)
            return

        if action:
            detail = f"{detail}；{action}" if detail else action
        self._entry_context_title.setText(title)
        self._entry_context_detail.setText(detail)
        self._entry_context_bar.setVisible(True)

    def _scene_template_context_detail(self) -> str:
        scene = self.bridge.current_scene()
        scene_label = ""
        if scene is not None:
            scene_label = str(
                getattr(scene, "display_name", "")
                or getattr(scene, "name", "")
                or getattr(scene, "scene_id", "")
                or ""
            ).strip()
        template_label = str(getattr(self._current_template, "name", "") or "").strip()
        parts = []
        if scene_label:
            parts.append(f"场景：{scene_label}")
        if template_label:
            parts.append(f"模板：{template_label}")
        return "；".join(parts)

    def _navigate_return_target(self) -> None:
        if not self._return_navigation_intent:
            return
        self.bridge.navigate_to_intent.emit(dict(self._return_navigation_intent))
        self._return_bar.setVisible(False)
        self._entry_context_bar.setVisible(False)

    def _finish_detail_transition(self, card_id: str) -> None:
        self._pending_real_detail_switch_card_id = None
        loading_visible_since = self._loading_visible_since
        if loading_visible_since is not None:
            elapsed_ms = int((monotonic() - loading_visible_since) * 1000)
            remaining_ms = max(0, DETAIL_LOADING_MIN_VISIBLE_MS - elapsed_ms)
            if remaining_ms > 0:
                if self._loading_min_visible_timer is None:
                    self._loading_min_visible_timer = QTimer(self)
                    self._loading_min_visible_timer.setSingleShot(True)
                    self._loading_min_visible_timer.timeout.connect(self._on_loading_min_visible_timeout)
                self._pending_detail_card_id = card_id
                self._loading_min_visible_timer.start(remaining_ms)
                return
        self._hide_loading_detail()
        self._details.show_detail(card_id)
        self._current_detail = self._details.current_detail
        detail = self._detail_map.get(card_id)
        if (
            detail is not None
            and hasattr(detail, "capture_entry_snapshot")
            and not self.bridge.is_template_dirty()
        ):
            detail.capture_entry_snapshot()

    def _schedule_loading_detail(self, card_id: str) -> None:
        self._pending_detail_card_id = card_id
        if self._loading_timer is None:
            self._loading_timer = QTimer(self)
            self._loading_timer.setSingleShot(True)
            self._loading_timer.timeout.connect(self._on_loading_timer_timeout)
        self._loading_timer.start(FIRST_LOAD_LOADING_DELAY_MS)

    def _on_loading_timer_timeout(self) -> None:
        card_id = self._pending_detail_card_id
        if not card_id or self._pending_real_detail_switch_card_id != card_id:
            return
        self._show_loading_detail(card_id)

    def _on_loading_min_visible_timeout(self) -> None:
        card_id = self._pending_detail_card_id
        if not card_id:
            return
        self._hide_loading_detail()
        self._details.show_detail(card_id)
        self._current_detail = self._details.current_detail
        detail = self._detail_map.get(card_id)
        if (
            detail is not None
            and hasattr(detail, "capture_entry_snapshot")
            and not self.bridge.is_template_dirty()
        ):
            detail.capture_entry_snapshot()

    def _show_loading_detail(self, card_id: str) -> None:
        title, icon = CARD_DEFINITIONS.get(card_id, (card_id, ""))
        if self._loading_timer is not None:
            self._loading_timer.stop()
        self._pending_detail_card_id = card_id
        self._loading_visible_since = monotonic()
        block_specs = DETAIL_LOADING_SKELETONS.get(card_id, (("summary", 118), ("editor_a", 168), ("editor_b", 148)))
        self._loading_detail = _LoadingDetail(title, icon, blocks=block_specs, parent=self._detail_container)
        self._loading_detail.apply_theme()
        self._loading_detail.show_overlay()

    def _hide_loading_detail(self) -> None:
        if self._loading_timer is not None:
            self._loading_timer.stop()
        if self._loading_min_visible_timer is not None:
            self._loading_min_visible_timer.stop()
        self._pending_detail_card_id = None
        self._loading_visible_since = None
        loading = self._loading_detail
        self._loading_detail = None
        if loading is None:
            return
        loading.hide()
        loading.setParent(None)
        self._retired_detail_placeholders.append(loading)

    def _ensure_detail_loaded(self, card_id: str) -> QWidget:
        if card_id in self._loaded_detail_ids:
            return self._detail_map[card_id]

        factory = self._detail_factories.get(card_id)
        if factory is None:
            return self._detail_map[card_id]

        detail = factory()
        old = self._detail_map[card_id]
        self._detail_map[card_id] = detail
        self._details.detail_map[card_id] = detail
        detail.hide()
        detail.setParent(self._detail_container)
        self._attach_reformat_toggle(card_id, detail)
        old.hide()
        old.setParent(None)
        self._retired_detail_placeholders.append(old)

        for attr_name, attr_card_id in self._detail_attr_names.items():
            if attr_card_id == card_id:
                setattr(self, attr_name, detail)
                break

        self._loaded_detail_ids.add(card_id)
        self._wire_parameter_detail_signals(card_id, detail)
        self._sync_detail_state(detail)
        return detail

    def preload_details_for_startup(self, status_callback=None) -> None:
        """Create heavier detail panes while the startup splash is visible."""
        while self.preload_one_detail_for_startup(status_callback):
            pass

    def preload_one_detail_for_startup(self, status_callback=None) -> bool:
        """Create one pending detail pane and return whether work was done."""
        for card_id in STARTUP_BACKGROUND_PRELOAD_CARDS:
            if card_id in self._loaded_detail_ids:
                continue
            if card_id not in self._detail_factories:
                continue
            title, _icon = CARD_DEFINITIONS.get(card_id, (card_id, ""))
            if callable(status_callback):
                status_callback(f"后台预热{title}")
            QApplication.processEvents()
            self._ensure_detail_loaded(card_id)
            return True
        return False

    def _show_refresh_overlay(self) -> None:
        current = self._details.current_detail
        if current is None:
            return
        if self._refresh_overlay is not None:
            self._refresh_overlay.hide()
            self._refresh_overlay.setParent(None)
        self._refresh_overlay = _RefreshOverlay(parent=self._detail_container)
        self._refresh_overlay.apply_theme()
        self._refresh_overlay.show_overlay()

    def _hide_refresh_overlay(self) -> None:
        overlay = self._refresh_overlay
        self._refresh_overlay = None
        if overlay is None:
            return
        overlay.hide()
        overlay.setParent(None)
        self._retired_detail_placeholders.append(overlay)

    def _attach_reformat_toggle(self, card_id: str, detail: QWidget) -> None:
        module_names = DETAIL_REFORMAT_MODULES.get(card_id)
        if not module_names or card_id in self._reformat_toggle_cards:
            return

        summary_card = getattr(detail, "_summary_card", None)
        if summary_card is None and hasattr(detail, "_header_card"):
            summary_card = getattr(detail, "_header_card", None)
        if summary_card is None:
            return

        content_layout = getattr(summary_card, "_content_layout", None)
        header_widget = None
        if content_layout is not None and content_layout.count() > 0:
            first_item = content_layout.itemAt(0)
            header_widget = first_item.widget() if first_item is not None else None
        header_layout = header_widget.layout() if header_widget is not None else None
        if header_layout is None or not hasattr(header_layout, "insertWidget"):
            return

        card = _ReformatToggleCard(
            card_id,
            target_label=DETAIL_REFORMAT_TARGETS.get(card_id, CARD_DEFINITIONS[card_id][0]),
            module_names=module_names,
            parent=header_widget,
        )
        card.toggled.connect(self._on_reformat_toggle_changed)
        add_control = getattr(header_widget, "add_control", None)
        if callable(add_control):
            add_control(card)
        else:
            header_layout.insertWidget(2, card, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self._reformat_toggle_cards[card_id] = card
        self._sync_reformat_toggle(card_id)

    def _sync_reformat_toggles(self) -> None:
        for card_id in DETAIL_CARDS:
            self._sync_reformat_nav_badge(card_id)
        for card_id in tuple(self._reformat_toggle_cards):
            self._sync_reformat_toggle(card_id)

    def _sync_reformat_nav_badge(self, card_id: str) -> None:
        nav_card = self._nav_cards.get(card_id)
        if nav_card is None:
            return

        scene = self.bridge.current_scene()
        module_names = DETAIL_REFORMAT_MODULES.get(card_id, ())
        if scene is None or not module_names:
            nav_card.set_badge("", "neutral")
            return

        switches = getattr(scene, "module_switches", {}) or {}
        states = [bool(switches.get(module_name, False)) for module_name in module_names]
        enabled = any(states)
        partial = any(states) and not all(states)

        if partial:
            nav_card.set_badge("部分", "warning")
        elif not enabled:
            nav_card.set_badge("跳过", "neutral")
        else:
            nav_card.set_badge("执行", "success")

    def _sync_reformat_toggle(self, card_id: str) -> None:
        card = self._reformat_toggle_cards.get(card_id)
        if card is None:
            return

        scene = self.bridge.current_scene()
        module_names = DETAIL_REFORMAT_MODULES.get(card_id, ())
        if scene is None or not module_names:
            card.sync_state(enabled=False, available=False)
            detail = self._detail_map.get(card_id)
            if hasattr(detail, "set_reformat_enabled"):
                detail.set_reformat_enabled(None)
            self._sync_reformat_nav_badge(card_id)
            return

        switches = getattr(scene, "module_switches", {}) or {}
        states = [bool(switches.get(module_name, False)) for module_name in module_names]
        enabled = any(states)
        partial = any(states) and not all(states)
        card.sync_state(enabled=enabled, available=True, partial=partial)
        detail = self._detail_map.get(card_id)
        if hasattr(detail, "set_reformat_enabled"):
            detail.set_reformat_enabled(enabled)
        self._sync_reformat_nav_badge(card_id)

    def _on_reformat_toggle_changed(self, card_id: str, enabled: bool) -> None:
        scene = self.bridge.current_scene()
        module_names = DETAIL_REFORMAT_MODULES.get(card_id, ())
        if scene is None or not module_names:
            self._sync_reformat_toggle(card_id)
            return

        changed_modules: list[str] = []
        for module_name in module_names:
            if scene.module_switches.get(module_name) == bool(enabled):
                continue
            scene.module_switches[module_name] = bool(enabled)
            changed_modules.append(module_name)

        if changed_modules:
            self.bridge.set_current_scene(
                scene,
                config_id=self.bridge.current_scene_id(),
                path=self.bridge.current_scene_path(),
                source=self.bridge.current_scene_source(),
                emit_signal=False,
            )
            for module_name in changed_modules:
                self.bridge.module_toggled.emit(module_name, bool(enabled))
            self.bridge.mark_scene_dirty(recheck=False)

        self._sync_reformat_toggles()

    def _wire_parameter_detail_signals(self, card_id: str, detail: QWidget) -> None:
        if hasattr(detail, "template_edited"):
            detail.template_edited.connect(self._on_template_edited)
        if not hasattr(detail, "save_requested"):
            return
        if card_id == "tpl_page":
            detail.save_requested.connect(self._on_page_save_requested)
        elif card_id == "tpl_style":
            detail.save_requested.connect(self._on_style_save_requested)
        else:
            detail.save_requested.connect(self._save_current_template)

    def _sync_detail_state(self, detail: QWidget) -> None:
        was_dirty = self.bridge.is_template_dirty()
        if hasattr(detail, "set_scene"):
            detail.set_scene(self.bridge.current_scene())
        if hasattr(detail, "set_template"):
            detail.set_template(self._current_template)
        elif hasattr(detail, "on_template_changed"):
            detail.on_template_changed(self._current_template)
        if was_dirty and not self.bridge.is_template_dirty():
            self.bridge.mark_template_dirty()
        if hasattr(detail, "set_save_enabled"):
            detail.set_save_enabled(self.bridge.is_template_dirty())
        if hasattr(detail, "apply_theme"):
            detail.apply_theme()
        elif hasattr(detail, "_apply_theme"):
            detail._apply_theme()

    def _template_source_text(self) -> str:
        source = str(self._current_template_source or "").strip()
        path = str(self._current_template_path or "").strip()
        if source == "library" and path:
            return self._format_source_text("模板文件", path)
        if source == "file" and path:
            return self._format_source_text("本地文件", path)
        if source == "builtin":
            return self._format_source_text("模板类型", "内置模板")
        if path:
            return self._format_source_text("模板文件", path)
        return "未保存到模板文件"

    def _template_overview_status_text(self) -> str:
        source = str(self._current_template_source or "").strip()
        path = str(self._current_template_path or "").strip()
        if source == "file" and path:
            return "本地文件"
        if source == "library" and path:
            return "模板文件"
        if source == "builtin":
            return "内置模板"
        if path:
            return "模板文件"
        return "未保存"

    def _template_path_status_text(self) -> str:
        path = str(self._current_template_path or "").strip()
        if not path:
            return "保存位置：未保存到文件"
        parent = str(Path(path).parent)
        if parent in ("", "."):
            parent = "当前文件夹"
        return f"保存位置：{parent}"

    def _template_path_tooltip(self) -> str:
        path = str(self._current_template_path or "").strip()
        return path if path else "当前模板还没有保存到文件"

    def _current_template_path_obj(self) -> Path | None:
        path = str(self._current_template_path or "").strip()
        if not path:
            return None
        return Path(path)

    def _current_template_is_builtin(self) -> bool:
        template_id = str(self._current_template_id or "").strip()
        return template_id in set(list_builtin_template_ids())

    def _current_template_manage_path(self) -> Path | None:
        path = self._current_template_path_obj()
        if path is None or not path.exists() or path.is_dir():
            return None
        return path

    def _current_template_can_rename(self) -> bool:
        return (
            self._current_template is not None
            and not self._current_template_is_builtin()
            and self._current_template_manage_path() is not None
        )

    def _current_template_can_delete(self) -> bool:
        return (
            not self._current_template_is_builtin()
            and self._current_template_manage_path() is not None
        )

    def _current_template_folder(self) -> Path:
        path = self._current_template_path_obj()
        if path is not None:
            folder = path if path.is_dir() else path.parent
            if folder.exists():
                return folder
        return TEMPLATE_LIBRARY_DIR

    def _current_template_file_was_removed(self) -> bool:
        source = str(self._current_template_source or "").strip()
        if source not in {"library", "file"}:
            return False
        path = self._current_template_path_obj()
        return path is not None and not path.exists()

    def _current_template_should_stay_in_selector(self) -> bool:
        if self._current_template is None:
            return False
        path = self._current_template_path_obj()
        if path is not None:
            return path.exists()
        source = str(self._current_template_source or "").strip()
        return source not in {"library", "file"}

    def _template_library_watch_directories(self) -> list[str]:
        TEMPLATE_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        directories = [TEMPLATE_LIBRARY_DIR]
        try:
            directories.extend(
                path
                for path in TEMPLATE_LIBRARY_DIR.iterdir()
                if path.is_dir()
            )
        except Exception:
            pass
        return [str(path) for path in directories]

    def _setup_template_library_watcher(self) -> None:
        watcher = getattr(self, "_template_library_watcher", None)
        if watcher is None:
            return
        target_dirs = set(self._template_library_watch_directories())
        current_dirs = set(watcher.directories())
        remove_dirs = list(current_dirs - target_dirs)
        add_dirs = list(target_dirs - current_dirs)
        if remove_dirs:
            watcher.removePaths(remove_dirs)
        if add_dirs:
            watcher.addPaths(add_dirs)

    def _on_template_library_path_changed(self, _path: str = "") -> None:
        if self._template_library_refresh_pending:
            return
        self._template_library_refresh_pending = True
        QTimer.singleShot(50, self._refresh_template_library_from_disk)

    def _switch_to_default_template_after_missing_file(self) -> None:
        message = "当前模板文件已不存在，已切换到默认格式"
        entry = default_template_entry()
        if entry is not None:
            template = load_template_from_library(entry.config_id)
            self._activate_template(
                template,
                template_id=entry.config_id,
                path=str(entry.path),
                source="library",
                status=f"ℹ {message}",
                dirty=False,
            )
        else:
            template = create_builtin_template("default")
            self._activate_template(
                template,
                template_id="default",
                path="",
                source="builtin",
                status=f"ℹ {message}",
                dirty=False,
            )
        Toast.show_info(message)

    def _refresh_template_library_from_disk(self) -> None:
        self._template_library_refresh_pending = False
        self._setup_template_library_watcher()
        if self._current_template_file_was_removed():
            self._switch_to_default_template_after_missing_file()
            return
        self._refresh_template_selector_options()
        self._sync_template_file_status()

    @staticmethod
    def _format_source_text(source_label: str, path: str = "") -> str:
        label = str(source_label or "").strip() or "模板文件"
        value = str(path or "").strip()
        if not value:
            return label
        display = Path(value).name if any(sep in value for sep in ("/", "\\")) else value
        return f"{label}：{display}"

    def _sync_template_file_status(self) -> None:
        self._overview_detail.set_status_text(self._template_overview_status_text())
        is_builtin = self._current_template_is_builtin()
        can_rename = self._current_template_can_rename()
        can_delete = self._current_template_can_delete()
        self._overview_detail.set_template_action_state(
            can_rename=can_rename,
            can_delete=can_delete,
            rename_tooltip="" if can_rename else (
                "内置模板不能重命名，请先新建模板"
                if is_builtin else "当前模板还没有保存为模板文件"
            ),
            delete_tooltip="" if can_delete else (
                "内置模板不能删除，请先新建模板"
                if is_builtin else "当前模板还没有可删除的文件"
            ),
            folder_tooltip=str(self._current_template_folder()),
        )
        if hasattr(self, "_io_detail"):
            self._io_detail.set_file_status(self._template_source_text())
            self._io_detail.set_path_status(
                self._template_path_status_text(),
                self._template_path_tooltip(),
            )

    def _template_ids_for_selector(self) -> list[str]:
        template_ids: list[str] = []
        seen: set[str] = set()

        entries = list_template_entries()
        entry_ids = {entry.config_id for entry in entries}
        for template_id in list_builtin_template_ids():
            if template_id in seen:
                continue
            if template_id in entry_ids or not entry_ids:
                seen.add(template_id)
                template_ids.append(template_id)

        for entry in entries:
            template_id = str(entry.config_id or "").strip()
            if not template_id or template_id in seen:
                continue
            seen.add(template_id)
            template_ids.append(template_id)

        current_template_id = str(self._current_template_id or "").strip()
        if (
            current_template_id
            and current_template_id not in template_ids
            and self._current_template_should_stay_in_selector()
        ):
            template_ids.insert(0, current_template_id)
        return [template_id for template_id in template_ids if template_id]

    def _template_option_label(self, template_id: str) -> str:
        target_id = str(template_id or "").strip()
        if not target_id:
            return ""

        if target_id == str(self._current_template_id or "").strip() and self._current_template is not None:
            current_name = str(getattr(self._current_template, "name", "") or "").strip()
            if current_name:
                return current_name

        entry = get_template_entry(target_id)
        if entry is not None:
            return entry.name

        try:
            return str(create_builtin_template(target_id).name or target_id)
        except Exception:
            return target_id

    def _refresh_template_selector_options(self) -> None:
        options = [
            _BuiltinTemplateOption(template_id=template_id, name=self._template_option_label(template_id))
            for template_id in self._template_ids_for_selector()
        ]
        self._overview_detail.set_template_options(options, current_template_id=self._current_template_id)

    def _parameter_details(self) -> list[QWidget]:
        return [
            self._detail_map[card_id]
            for card_id in DETAIL_CARDS
            if card_id in self._loaded_detail_ids
        ]

    def _set_detail_templates(self, template: TemplateConfig) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "set_scene"):
                detail.set_scene(self.bridge.current_scene())
            if hasattr(detail, "set_template"):
                detail.set_template(template)
            elif hasattr(detail, "on_template_changed"):
                detail.on_template_changed(template)
        if template is not None and not self.bridge.is_template_dirty():
            self._remember_persisted_template_state(template)

    def _set_detail_scenes(self, scene) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "set_scene"):
                detail.set_scene(scene)

    def _set_detail_save_enabled(self, enabled: bool) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "set_save_enabled"):
                detail.set_save_enabled(enabled)
        if hasattr(self, "_io_detail"):
            self._io_detail.set_save_status(bool(enabled))

    def _capture_detail_snapshots(self) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "capture_entry_snapshot"):
                detail.capture_entry_snapshot()

    def _remember_persisted_template_state(self, template=None) -> None:
        target = template if template is not None else self._current_template
        self._persisted_template_snapshot = copy.deepcopy(target) if target is not None else None

    def _compute_dirty_against_persisted_snapshot(self) -> bool | None:
        if self._current_template is None:
            return False
        if self._persisted_template_snapshot is None:
            return None
        return self._current_template != self._persisted_template_snapshot

    def _sync_template_dirty_state(self, *, assume_dirty_if_unknown: bool = False) -> bool:
        dirty = self._compute_dirty_against_persisted_snapshot()
        if dirty is None:
            dirty = True if assume_dirty_if_unknown else self.bridge.is_template_dirty()
        if dirty:
            self.bridge.mark_template_dirty()
        else:
            self.bridge.clear_template_dirty()
        return dirty

    def _can_save_in_place(self) -> bool:
        path = str(self._current_template_path or "").strip()
        return bool(path)

    def _publish_current_template(self, *, emit_signal: bool = True) -> None:
        if self._current_template is None:
            return

        if emit_signal:
            self._bridge_template_echo_depth += 1
        try:
            self.bridge.set_current_template(
                self._current_template,
                config_id=self._current_template_id,
                path=self._current_template_path,
                source=self._current_template_source,
                emit_signal=emit_signal,
            )
        finally:
            if emit_signal:
                self._bridge_template_echo_depth -= 1

    def _write_current_template_to_path(
        self,
        path: str | Path,
        *,
        success_message: str,
    ) -> bool:
        if self._current_template is None:
            return False

        try:
            saved = save_template(self._current_template, path)
            self._current_template_id = saved.stem
            self._current_template_path = str(saved)
            self._current_template_source = "library" if is_template_library_path(saved) else "file"
            self._remember_persisted_template_state(self._current_template)
            success_text = success_message.format(name=saved.name)
            self._io_detail.set_status(success_text)
            self._sync_template_file_status()
            self.bridge.clear_template_dirty()
            self._publish_current_template()
            self._capture_detail_snapshots()
            self._set_detail_save_enabled(False)
            Toast.show_success(success_text.replace("✅ ", ""))
            return True
        except Exception as exc:
            message = f"❌ 保存失败: {exc}"
            self._io_detail.set_status(message)
            Toast.show_error(f"保存失败: {exc}")
            return False

    def _load_template_for_selector(
        self,
        template_id: str,
    ) -> tuple[TemplateConfig, str, str]:
        target_id = str(template_id or "").strip()
        if not target_id:
            raise ValueError("模板 id 为空")

        entry = get_template_entry(target_id)
        if entry is not None:
            return load_template(entry.path), str(entry.path), "library"

        current_id = str(self._current_template_id or "").strip()
        if target_id == current_id:
            path = self._current_template_path_obj()
            if path is not None and path.exists() and not path.is_dir():
                source = "library" if is_template_library_path(path) else "file"
                return load_template(path), str(path), source
            if self._current_template is not None:
                source = str(self._current_template_source or "").strip()
                if not source and target_id in set(list_builtin_template_ids()):
                    source = "builtin"
                return self._current_template, str(self._current_template_path or ""), source

        if target_id in set(list_builtin_template_ids()):
            return create_builtin_template(target_id), "", "builtin"

        raise ValueError(f"找不到模板：{target_id}")

    def _unique_template_path_for_name(self, name: str) -> Path:
        TEMPLATE_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        stem = _safe_template_file_stem(name)
        candidate = TEMPLATE_LIBRARY_DIR / f"{stem}.json"
        if not candidate.exists():
            return candidate
        for index in range(2, 1000):
            candidate = TEMPLATE_LIBRARY_DIR / f"{stem}_{index}.json"
            if not candidate.exists():
                return candidate
        return TEMPLATE_LIBRARY_DIR / f"{stem}_{int(monotonic() * 1000)}.json"

    def _template_copy_base_name(self) -> str:
        name = str(
            getattr(self._current_template, "name", "") or "自定义模板"
        ).strip() or "自定义模板"
        return re.sub(r"\s*副本(?:\s*\d+)?$", "", name).strip() or name

    def _unique_template_copy_name(self) -> str:
        base_name = self._template_copy_base_name()
        existing_names = {
            str(entry.name or "").strip()
            for entry in list_template_entries()
            if str(entry.name or "").strip()
        }

        def available(name: str) -> bool:
            if name in existing_names:
                return False
            stem = _safe_template_file_stem(name)
            return not (TEMPLATE_LIBRARY_DIR / f"{stem}.json").exists()

        candidate = f"{base_name} 副本"
        if available(candidate):
            return candidate
        for index in range(2, 1000):
            candidate = f"{base_name} 副本 {index}"
            if available(candidate):
                return candidate
        return f"{base_name} 副本 {int(monotonic() * 1000)}"

    def _create_template_copy(self, name: str, *, action_label: str) -> bool:
        template = (
            copy.deepcopy(self._current_template)
            if self._current_template is not None
            else create_builtin_template("default")
        )
        template.name = name
        target = self._unique_template_path_for_name(name)
        try:
            saved = save_template(template, target)
        except Exception as exc:
            Toast.show_error(f"{action_label}失败: {exc}")
            self._io_detail.set_status(f"❌ {action_label}失败: {exc}")
            return False

        self._activate_template(
            template,
            template_id=saved.stem,
            path=str(saved),
            source="library",
            status=f"✅ 已{action_label}: {saved.name}",
            dirty=False,
        )
        Toast.show_success(f"已{action_label}: {name}")
        return True

    def _activate_template(
        self,
        template: TemplateConfig,
        *,
        template_id: str,
        path: str = "",
        source: str = "",
        status: str = "",
        dirty: bool = False,
    ) -> None:
        self._current_template = template
        self._current_template_id = template_id
        self._current_template_path = path
        self._current_template_source = source
        self._refresh_template_selector_options()
        self._set_detail_templates(self._current_template)
        self._remember_persisted_template_state(self._current_template)
        self._sync_template_file_status()
        self._overview_detail.refresh(self._current_template)
        self._io_detail.set_status(status)
        self._refresh_subtitles()
        if dirty:
            self.bridge.mark_template_dirty()
        else:
            self.bridge.clear_template_dirty()
        self._set_detail_save_enabled(bool(dirty))
        self._publish_current_template()

    def _save_current_template(self) -> bool:
        if self._current_template is None:
            return False
        if self._can_save_in_place():
            return self._write_current_template_to_path(
                self._current_template_path,
                success_message="✅ 已保存: {name}",
            )
        return self._save_current_template_as()

    def _save_current_template_as(self) -> bool:
        if self._current_template is None:
            return False

        default_name = (self._current_template.name or "template") + ".json"
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为模板配置", default_name,
            "JSON (*.json);;YAML (*.yaml *.yml)",
        )
        if not path:
            return False
        return self._write_current_template_to_path(
            path,
            success_message="✅ 已另存为: {name}",
        )

    # ──────────────────────────────────────────────────────
    # Event handlers
    # ──────────────────────────────────────────────────────

    def _on_new_template_requested(self) -> None:
        default_name = (
            getattr(self._current_template, "name", "") or "自定义模板"
        ).strip()
        if default_name and not default_name.endswith("副本"):
            default_name = f"{default_name} 副本"
        name = input_text(
            "新建模板",
            "请输入模板名称：",
            placeholder="例如：论文自定义模板",
            default=default_name or "自定义模板",
            ok_text="创建",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            Toast.show_warning("模板名称不能为空")
            return

        self._create_template_copy(name, action_label="新建模板")

    def _on_duplicate_template_requested(self) -> None:
        name = self._unique_template_copy_name()
        self._create_template_copy(name, action_label="创建副本")

    def _on_rename_template_requested(self) -> None:
        if not self._current_template_can_rename():
            Toast.show_warning(
                "内置模板不能重命名，请先新建模板"
                if self._current_template_is_builtin()
                else "当前模板还没有保存为模板文件"
            )
            return
        current_name = str(
            getattr(self._current_template, "name", "") or self._current_template_id or ""
        ).strip()
        name = input_text(
            "重命名模板",
            "请输入新的模板名称：",
            placeholder="模板名称",
            default=current_name,
            ok_text="保存",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            Toast.show_warning("模板名称不能为空")
            return
        if self._current_template is None:
            return
        self._current_template.name = name
        saved = self._save_current_template()
        self._refresh_template_selector_options()
        self._overview_detail.refresh(self._current_template)
        self._refresh_subtitles()
        if saved:
            Toast.show_success(f"已重命名模板: {name}")

    def _on_open_template_folder_requested(self) -> None:
        folder = self._current_template_folder()
        folder.mkdir(parents=True, exist_ok=True)
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        if not opened:
            Toast.show_error(f"无法打开模板文件夹: {folder}")

    def _on_delete_template_requested(self) -> None:
        if not self._current_template_can_delete():
            Toast.show_warning(
                "内置模板不能删除，请先新建模板"
                if self._current_template_is_builtin()
                else "当前模板还没有可删除的文件"
            )
            return
        path = self._current_template_manage_path()
        if path is None:
            Toast.show_warning("当前模板还没有可删除的文件")
            return
        template_name = str(
            getattr(self._current_template, "name", "")
            or self._current_template_id
            or path.stem
        ).strip()
        if not confirm(
            "删除模板",
            f"确定删除模板“{template_name}”吗？\n\n文件：{path.name}",
            confirm_text="删除",
            destructive=True,
            parent=self,
        ):
            return

        try:
            path.unlink()
        except Exception as exc:
            Toast.show_error(f"删除模板失败: {exc}")
            self._io_detail.set_status(f"❌ 删除模板失败: {exc}")
            return

        entry = default_template_entry()
        if entry is not None:
            template = load_template_from_library(entry.config_id)
            self._activate_template(
                template,
                template_id=entry.config_id,
                path=str(entry.path),
                source="library",
                status=f"✅ 已删除模板: {template_name}",
                dirty=False,
            )
        else:
            template = create_builtin_template("default")
            self._activate_template(
                template,
                template_id="default",
                path="",
                source="builtin",
                status=f"✅ 已删除模板: {template_name}",
                dirty=False,
            )
        Toast.show_success(f"已删除模板: {template_name}")

    def _on_template_selected(self, index: int) -> None:
        template_id = str(self._overview_detail._combo.itemData(index) or "").strip()
        if template_id:
            try:
                template, path, source = self._load_template_for_selector(template_id)
            except Exception as exc:
                message = f"模板加载失败: {exc}"
                self._io_detail.set_status(f"❌ {message}")
                Toast.show_error(message)
                self._refresh_template_selector_options()
                return
            self._activate_template(
                template,
                template_id=template_id,
                path=path,
                source=source,
                status="",
                dirty=False,
            )

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入模板配置", "",
            "配置文件 (*.json *.yaml *.yml);;JSON (*.json);;YAML (*.yaml *.yml)",
        )
        if not path:
            return
        try:
            cfg = load_template(path)
            self._current_template = cfg
            self._current_template_id = Path(path).stem
            self._current_template_path = str(Path(path))
            self._current_template_source = "file"
            name = cfg.name or Path(path).stem
            self._refresh_template_selector_options()
            self._set_detail_templates(self._current_template)
            self._remember_persisted_template_state(self._current_template)
            self._sync_template_file_status()
            self._overview_detail.refresh(cfg)
            self._io_detail.set_status(f"✅ 已导入: {name}")
            self._refresh_subtitles()
            self.bridge.clear_template_dirty()
            self._set_detail_save_enabled(False)
            self._publish_current_template()
        except Exception as e:
            self._io_detail.set_status(f"❌ 导入失败: {e}")

    def _on_page_save_requested(self) -> None:
        self._save_current_template()

    def _on_style_save_requested(self) -> None:
        self._save_current_template()

    def _on_reset(self) -> None:
        idx = self._overview_detail._combo.currentIndex()
        template_id = str(self._overview_detail._combo.itemData(idx) or "").strip()
        if template_id:
            entry = get_template_entry(template_id)
            self._current_template = load_template_from_library(template_id)
            self._current_template_id = template_id
            self._current_template_path = str(entry.path) if entry is not None else ""
            self._current_template_source = "library" if entry is not None else "builtin"
            self._refresh_template_selector_options()
            self._set_detail_templates(self._current_template)
            self._remember_persisted_template_state(self._current_template)
            self._sync_template_file_status()
            self._overview_detail.refresh(self._current_template)
            self._io_detail.set_status("✅ 已恢复为内置默认模板")
            self._refresh_subtitles()
            self.bridge.clear_template_dirty()
            self._set_detail_save_enabled(False)
            self._publish_current_template()

    def _on_template_edited(self, template: TemplateConfig) -> None:
        self._current_template = template
        self._overview_detail.refresh(template)
        self._refresh_subtitles()
        self._publish_current_template()
        self._sync_template_dirty_state(assume_dirty_if_unknown=True)

    def _on_template_dirty_changed(self, dirty: bool) -> None:
        self._overview_detail.refresh(self._current_template)
        self._refresh_subtitles()
        self._set_detail_save_enabled(bool(dirty))

    def on_scene_changed(self, _scene) -> None:
        self._refresh_template_selector_options()
        self._sync_reformat_toggles()
        self._set_detail_scenes(_scene)

    def on_template_changed(self, template: TemplateConfig) -> None:
        if self._bridge_template_echo_depth:
            return
        previous_template = self._current_template
        previous_path = self._current_template_path
        previous_source = self._current_template_source
        self._current_template = template
        self._current_template_id = self.bridge.current_template_id()
        self._current_template_path = self.bridge.current_template_path()
        self._current_template_source = self.bridge.current_template_source()
        if (
            not self.bridge.is_template_dirty()
            and (
                template is not previous_template
                or self._current_template_path != previous_path
                or self._current_template_source != previous_source
            )
        ):
            self._remember_persisted_template_state(template)
        self._refresh_template_selector_options()
        self._sync_template_file_status()
        self._overview_detail.refresh(template)
        self._set_detail_templates(template)
        self._set_detail_save_enabled(self.bridge.is_template_dirty())
        self._refresh_subtitles()

    # ──────────────────────────────────────────────────────
    # Subtitle refresh
    # ──────────────────────────────────────────────────────

    def _refresh_subtitles(self) -> None:
        groups = build_template_preview_groups(self._current_template)
        subtitle_map = {group.detail_card_id: group.summary for group in groups}

        card = self._nav_cards.get("tpl_overview")
        if card:
            card.set_subtitle(self._current_template.name or "默认格式")

        for card_id in DETAIL_CARDS:
            card = self._nav_cards.get(card_id)
            if card:
                card.set_subtitle(subtitle_map.get(card_id, ""))

    # ──────────────────────────────────────────────────────
    # Theme
    # ──────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        t = get_theme()
        self._shell.apply_theme(t)

        if self._loading_detail is not None:
            self._loading_detail.apply_theme()
        if self._refresh_overlay is not None:
            self._refresh_overlay.apply_theme()
        if hasattr(self, "_return_label"):
            self._return_label.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
            )
            apply_button_variant(self._return_btn, "secondary")
        if hasattr(self, "_entry_context_bar"):
            self._entry_context_bar.setStyleSheet(
                f"background: {t.bg_selected}; border: 1px solid {t.border_light}; "
                f"border-radius: {t.radius_sm}px;"
            )
            self._entry_context_title.setStyleSheet(
                f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.text_primary}; background: transparent;"
            )
            self._entry_context_detail.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary}; background: transparent;"
            )

        # Propagate to details
        self._overview_detail.apply_theme()
        self._io_detail.apply_theme()
        current_detail = self._details.current_detail
        show_refresh = current_detail is not None and current_detail not in {self._overview_detail, self._io_detail}
        if show_refresh:
            self._show_refresh_overlay()
        for detail in self._parameter_details():
            if hasattr(detail, "apply_theme"):
                detail.apply_theme()
            elif hasattr(detail, "_apply_theme"):
                detail._apply_theme()
        if show_refresh:
            QTimer.singleShot(DETAIL_REFRESH_MIN_VISIBLE_MS, self._hide_refresh_overlay)
