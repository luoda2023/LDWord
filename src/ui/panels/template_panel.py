"""
template_panel — 模板管理面板（Master-Detail 架构）

与工作台同构：左侧导航卡片 + 右侧可切换详情面板。
信息分层:
  Layer 1: 模板概览 (主操作)
  Layer 2: 导入导出 (管理操作)
  Layer 3: 页面设置 / 排版样式 / 标题编号 (参数细节)
"""

from __future__ import annotations

from pathlib import Path

from src.config.builtin_templates import create_builtin_template
from src.config.loader import load_template, save_template
from src.config.template import TemplateConfig
from src.qt_api import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui import DynamicNavigationRail, NavigationCard
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.base_panel import BasePanel
from src.ui.panels.template_formula_detail import FormulaDetail
from src.ui.panels.template_format import build_template_preview_groups
from src.ui.panels.template_elements_detail import ElementsDetail
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_other_detail import OtherDetail
from src.ui.panels.template_page_detail import PageSetupDetail
from src.ui.panels.template_reference_detail import ReferenceDetail
from src.ui.panels.template_style_detail import StyleDetail
from src.ui.panels.template_table_detail import TableCaptionDetail
from src.ui.panels.workbench.detail_controller import WorkbenchDetailController


# ═══════════════════════════════════════════════════════════════════════
#  Built-in template registry
# ═══════════════════════════════════════════════════════════════════════

_BUILTIN_TEMPLATES: list["TemplateMeta"] = []
_BUILTIN_LOADED = False


def _ensure_builtins() -> list["TemplateMeta"]:
    """Lazy-load template metadata from scene presets."""
    global _BUILTIN_LOADED
    if _BUILTIN_LOADED:
        return _BUILTIN_TEMPLATES
    _BUILTIN_LOADED = True

    from src.ui.panels.workbench.scene_presets import SCENE_METAS

    seen: set[str] = set()
    for scene in SCENE_METAS:
        for tpl in scene.compatible_templates:
            if tpl.template_id in seen:
                continue
            seen.add(tpl.template_id)
            _BUILTIN_TEMPLATES.append(tpl)
    return _BUILTIN_TEMPLATES


# ═══════════════════════════════════════════════════════════════════════
#  Card definitions (Layer 1 → 2 → 3)
# ═══════════════════════════════════════════════════════════════════════

CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    # Layer 1: Primary
    "tpl_overview":  ("模板概览",  "scan-text"),
    # Layer 2: Management
    "tpl_io":        ("导入导出",  "folder-open"),
    # Layer 3: Parameter details
    "tpl_page":      ("页面设置",  "ruler"),
    "tpl_style":     ("排版样式",  "type-outline"),
    "tpl_heading":   ("标题编号",  "list-ordered"),
    "tpl_table":     ("表格题注",  "table-2"),
    "tpl_elements":  ("页眉目录",  "panel-top"),
    "tpl_formula":   ("公式规范",  "sigma"),
    "tpl_reference": ("参考文献",  "book-open"),
    "tpl_other":     ("其他参数",  "settings"),
}

CARD_ORDER = (
    "tpl_overview",
    "tpl_io",
    "tpl_page",
    "tpl_style",
    "tpl_heading",
    "tpl_table",
    "tpl_elements",
    "tpl_formula",
    "tpl_reference",
    "tpl_other",
)
FIXED_CARDS = ("tpl_overview", "tpl_io")
DETAIL_CARDS = (
    "tpl_page",
    "tpl_style",
    "tpl_heading",
    "tpl_table",
    "tpl_elements",
    "tpl_formula",
    "tpl_reference",
    "tpl_other",
)


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
        self._value.setWordWrap(False)
        self._value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
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
            f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_bold}; "
            f"color: {t.text_secondary};"
        )
        self._value.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_primary};")
        self._edit_btn.setStyleSheet(
            f"QPushButton {{ font-size: {t.font_size_sm}px; color: {t.primary}; "
            f"border: none; background: transparent; padding: 2px 6px; }}"
            f"QPushButton:hover {{ text-decoration: underline; }}"
        )
        self._edit_btn.setFixedHeight(22)
        try:
            from src.ui.icons.catalog import get_icon
            self._icon_lbl.setPixmap(get_icon(self._icon_name, size=14, color=t.text_hint).pixmap(14, 14))
        except Exception:
            self._icon_lbl.setText(self._label_text[:1])


# ═══════════════════════════════════════════════════════════════════════
#  Detail Panes
# ═══════════════════════════════════════════════════════════════════════

class TemplateOverviewDetail(QWidget):
    """Layer 1 detail: template selector + parameter summary + edit navigation."""

    template_selected = Signal(int)      # builtin index
    edit_navigate = Signal(str)          # target card_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_template = create_builtin_template("default")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # ── Card 1: Template selector ──
        self._selector_card = Card(parent=self)
        self._build_selector()
        layout.addWidget(self._selector_card)

        # ── Card 2: Parameter overview ──
        self._overview_card = Card(parent=self)
        self._build_overview()
        layout.addWidget(self._overview_card)

        layout.addStretch(1)

    def _build_selector(self) -> None:
        # Header
        hdr = self._make_card_header("file-text", "当前模板")
        self._selector_card.add_widget(hdr)

        # ComboBox
        self._combo = StyledComboBox(self)
        for meta in _ensure_builtins():
            self._combo.addItem(meta.name)
        self._combo.currentIndexChanged.connect(self.template_selected.emit)
        self._selector_card.add_widget(self._combo)

        # Source hint
        self._source_label = QLabel("来源: 内置模板")
        self._source_label.setObjectName("tpl_source")
        self._selector_card.add_widget(self._source_label)

    def _build_overview(self) -> None:
        # Header
        hdr = self._make_card_header("eye", "参数概览")
        self._overview_card.add_widget(hdr)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("tpl_sep")
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

        # Hint
        hint = QLabel('点击各参数行的"编辑"可跳转至对应设置面板')
        hint.setObjectName("tpl_hint")
        self._overview_card.add_widget(hint)

    def _make_card_header(self, icon_name: str, title: str) -> QWidget:
        hdr = QWidget()
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(6)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(18, 18)
        icon_lbl.setObjectName(f"tpl_hdr_icon_{icon_name}")
        lay.addWidget(icon_lbl)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("tpl_card_title")
        lay.addWidget(title_lbl)
        lay.addStretch(1)
        # Cache for theme
        self._header_icons = getattr(self, "_header_icons", {})
        self._header_icons[icon_name] = icon_lbl
        return hdr

    def refresh(self, cfg: TemplateConfig) -> None:
        self._current_template = cfg
        for group in build_template_preview_groups(cfg):
            row = self._rows.get(group.group_id)
            if row:
                row.set_value(group.summary)

    def set_source_text(self, text: str) -> None:
        self._source_label.setText(text)

    def apply_theme(self) -> None:
        t = get_theme()
        for w in self.findChildren(QLabel, "tpl_card_title"):
            w.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_bold}; color: {t.primary};"
            )
        self._source_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_hint};")
        for w in self.findChildren(QLabel, "tpl_hint"):
            w.setStyleSheet(f"font-size: {t.font_size_sm - 1}px; color: {t.text_hint}; padding-top: 4px;")
        for w in self.findChildren(QFrame, "tpl_sep"):
            w.setStyleSheet(f"background: {t.border_light}; max-height: 1px;")
        try:
            from src.ui.icons.catalog import get_icon
            for name, lbl in getattr(self, "_header_icons", {}).items():
                lbl.setPixmap(get_icon(name, 16, t.primary).pixmap(16, 16))
        except Exception:
            pass


class ImportExportDetail(QWidget):
    """Layer 2 detail: import / export / reset."""

    import_requested = Signal()
    export_requested = Signal()
    reset_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)

        # Header
        hdr = QWidget()
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 4)
        h_lay.setSpacing(6)
        self._hdr_icon = QLabel()
        self._hdr_icon.setFixedSize(18, 18)
        h_lay.addWidget(self._hdr_icon)
        title = QLabel("模板文件管理")
        title.setObjectName("tpl_card_title")
        h_lay.addWidget(title)
        h_lay.addStretch(1)
        card.add_widget(hdr)

        # Description
        desc = QLabel("从文件导入模板配置，或将当前模板导出为 JSON/YAML 文件以便分享和备份。")
        desc.setObjectName("tpl_io_desc")
        desc.setWordWrap(True)
        card.add_widget(desc)

        # Buttons
        btn_row = QWidget()
        btn_lay = QHBoxLayout(btn_row)
        btn_lay.setContentsMargins(0, 8, 0, 0)
        btn_lay.setSpacing(12)

        self._import_btn = QPushButton("📥  导入模板")
        self._import_btn.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._import_btn, "primary")
        self._import_btn.clicked.connect(self.import_requested.emit)
        btn_lay.addWidget(self._import_btn, 1)

        self._export_btn = QPushButton("📤  导出当前")
        self._export_btn.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._export_btn, "secondary")
        self._export_btn.clicked.connect(self.export_requested.emit)
        btn_lay.addWidget(self._export_btn, 1)

        card.add_widget(btn_row)

        # Reset row
        reset_row = QWidget()
        r_lay = QHBoxLayout(reset_row)
        r_lay.setContentsMargins(0, 4, 0, 0)
        r_lay.setSpacing(12)

        self._reset_btn = QPushButton("♻️  恢复为内置默认模板")
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

    def apply_theme(self) -> None:
        t = get_theme()
        for w in self.findChildren(QLabel, "tpl_card_title"):
            w.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_bold}; color: {t.primary};"
            )
        for w in self.findChildren(QLabel, "tpl_io_desc"):
            w.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")
        self._status.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")
        try:
            from src.ui.icons.catalog import get_icon
            self._hdr_icon.setPixmap(get_icon("folder-open", 16, t.primary).pixmap(16, 16))
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
        layout.setSpacing(12)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)

        hdr = QWidget()
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 4)
        h_lay.setSpacing(6)
        self._hdr_icon = QLabel()
        self._hdr_icon.setFixedSize(18, 18)
        h_lay.addWidget(self._hdr_icon)
        t_lbl = QLabel(title)
        t_lbl.setObjectName("tpl_card_title")
        h_lay.addWidget(t_lbl)
        h_lay.addStretch(1)
        card.add_widget(hdr)

        desc = QLabel(f"「{title}」参数编辑面板开发中...\n后续版本将支持在此直接编辑模板参数。")
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
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_bold}; color: {t.primary};"
            )
        for w in self.findChildren(QLabel, "tpl_placeholder_desc"):
            w.setStyleSheet(
                f"font-size: {t.font_size_md}px; color: {t.text_hint}; padding: 40px 20px;"
            )
        try:
            from src.ui.icons.catalog import get_icon
            self._hdr_icon.setPixmap(get_icon(self._icon_name, 16, t.primary).pixmap(16, 16))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
#  Main Panel (Master-Detail)
# ═══════════════════════════════════════════════════════════════════════

class TemplatePanel(BasePanel):
    """Master-detail template management panel."""

    panel_title = "模板管理"
    panel_icon = "file-text"

    def _setup_ui(self) -> None:
        self.setObjectName("TemplatePanel")
        self._current_template = create_builtin_template("default")

        # ── Shell: HBox → NavRail + DetailScroll ──
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Left: navigation rail
        self._nav_rail = DynamicNavigationRail(parent=self)
        self._nav_rail.setObjectName("tpl_navigation")
        self._nav_rail.setFixedWidth(260)
        self._layout.addWidget(self._nav_rail)

        # Right: scrollable detail
        self._detail_scroll = QScrollArea(self)
        self._detail_scroll.setObjectName("tpl_detail")
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._detail_scroll.setFrameShape(QFrame.NoFrame)

        self._detail_container = QWidget(self._detail_scroll)
        self._detail_container.setObjectName("tpl_detail_content")
        self._detail_layout = QVBoxLayout(self._detail_container)
        self._detail_layout.setContentsMargins(20, 12, 20, 20)
        self._detail_layout.setSpacing(0)
        self._detail_scroll.setWidget(self._detail_container)
        self._layout.addWidget(self._detail_scroll, 1)

        # ── Build detail panes ──
        self._overview_detail = TemplateOverviewDetail()
        self._io_detail = ImportExportDetail()
        self._page_detail = PageSetupDetail()
        self._style_detail = StyleDetail()
        self._heading_detail = HeadingNumberingPanel(self.bridge)
        self._table_detail = TableCaptionDetail()
        self._elements_detail = ElementsDetail()
        self._formula_detail = FormulaDetail()
        self._reference_detail = ReferenceDetail()
        self._other_detail = OtherDetail()

        self._detail_map: dict[str, QWidget] = {
            "tpl_overview": self._overview_detail,
            "tpl_io": self._io_detail,
            "tpl_page": self._page_detail,
            "tpl_style": self._style_detail,
            "tpl_heading": self._heading_detail,
            "tpl_table": self._table_detail,
            "tpl_elements": self._elements_detail,
            "tpl_formula": self._formula_detail,
            "tpl_reference": self._reference_detail,
            "tpl_other": self._other_detail,
        }
        self._details = WorkbenchDetailController(
            self._detail_container,
            self._detail_layout,
            self._detail_scroll,
        )
        self._details.register_details(self._detail_map)
        self._current_detail: QWidget | None = self._details.current_detail

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
        self._refresh_subtitles()
        self._page_detail.set_template(self._current_template)
        self._style_detail.set_template(self._current_template)
        self._heading_detail.on_template_changed(self._current_template)
        self._table_detail.set_template(self._current_template)
        self._elements_detail.set_template(self._current_template)
        self._formula_detail.set_template(self._current_template)
        self._reference_detail.set_template(self._current_template)
        self._other_detail.set_template(self._current_template)
        # Manually show initial detail (signals not yet connected)
        self._show_detail("tpl_overview")
        self._nav_rail.select_card("tpl_overview")
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        # Navigation
        self._nav_rail.card_selected.connect(self._show_detail)

        # Overview interactions
        self._overview_detail.template_selected.connect(self._on_template_selected)
        self._overview_detail.edit_navigate.connect(self._nav_rail.select_card)

        # Import/Export
        self._io_detail.import_requested.connect(self._on_import)
        self._io_detail.export_requested.connect(self._on_export)
        self._io_detail.reset_requested.connect(self._on_reset)
        self._page_detail.template_edited.connect(self._on_template_edited)
        self._style_detail.template_edited.connect(self._on_template_edited)
        self._table_detail.template_edited.connect(self._on_template_edited)
        self._elements_detail.template_edited.connect(self._on_template_edited)
        self._formula_detail.template_edited.connect(self._on_template_edited)
        self._reference_detail.template_edited.connect(self._on_template_edited)
        self._other_detail.template_edited.connect(self._on_template_edited)

        # Bridge
        self.bridge.template_changed.connect(self.on_template_changed)
        self.bridge.template_dirty_changed.connect(self._on_template_dirty_changed)

    # ──────────────────────────────────────────────────────
    # Detail switching
    # ──────────────────────────────────────────────────────

    def _show_detail(self, card_id: str) -> None:
        self._details.show_detail(card_id)
        self._current_detail = self._details.current_detail

    # ──────────────────────────────────────────────────────
    # Event handlers
    # ──────────────────────────────────────────────────────

    def _on_template_selected(self, index: int) -> None:
        builtins = _ensure_builtins()
        if 0 <= index < len(builtins):
            meta = builtins[index]
            self._current_template = meta.create_template()
            self._overview_detail.set_source_text(f"来源: 内置模板 · {meta.name}")
            self._overview_detail.refresh(self._current_template)
            self._io_detail.set_status("")
            self._refresh_subtitles()
            self.bridge.template_changed.emit(self._current_template)

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
            name = cfg.name or Path(path).stem
            self._overview_detail.set_source_text(f"来源: 导入文件 · {Path(path).name}")
            self._overview_detail.refresh(cfg)
            self._io_detail.set_status(f"✅ 已导入: {name}")
            self._refresh_subtitles()
            self.bridge.template_changed.emit(cfg)
        except Exception as e:
            self._io_detail.set_status(f"❌ 导入失败: {e}")

    def _on_export(self) -> None:
        default_name = (self._current_template.name or "template") + ".json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出模板配置", default_name,
            "JSON (*.json);;YAML (*.yaml *.yml)",
        )
        if not path:
            return
        try:
            saved = save_template(self._current_template, path)
            self._io_detail.set_status(f"✅ 已导出: {saved.name}")
        except Exception as e:
            self._io_detail.set_status(f"❌ 导出失败: {e}")

    def _on_reset(self) -> None:
        builtins = _ensure_builtins()
        idx = self._overview_detail._combo.currentIndex()
        if 0 <= idx < len(builtins):
            meta = builtins[idx]
            self._current_template = meta.create_template()
            self._overview_detail.set_source_text(f"来源: 内置模板 · {meta.name}")
            self._overview_detail.refresh(self._current_template)
            self._io_detail.set_status("✅ 已恢复为内置默认模板")
            self._refresh_subtitles()
            self.bridge.template_changed.emit(self._current_template)

    def _on_template_edited(self, template: TemplateConfig) -> None:
        self._current_template = template
        self._overview_detail.refresh(template)
        self._refresh_subtitles()
        self.bridge.template_changed.emit(template)
        self.bridge.mark_template_dirty()

    def _on_template_dirty_changed(self, _dirty: bool) -> None:
        self._overview_detail.refresh(self._current_template)
        self._refresh_subtitles()

    def on_template_changed(self, template: TemplateConfig) -> None:
        self._current_template = template
        self._overview_detail.refresh(template)
        self._page_detail.set_template(template)
        self._style_detail.set_template(template)
        self._table_detail.set_template(template)
        self._elements_detail.set_template(template)
        self._formula_detail.set_template(template)
        self._reference_detail.set_template(template)
        self._other_detail.set_template(template)
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
        radius = t.shell_radius

        self.setStyleSheet(
            f"#TemplatePanel {{ background: {t.bg_window}; border-bottom-right-radius: {radius}px; }}"
        )
        self._nav_rail.setStyleSheet(
            f"#tpl_navigation {{ background: {t.bg_nav_rail}; }}"
        )
        self._detail_scroll.setStyleSheet(
            f"#tpl_detail {{ border: none; background: {t.bg_window}; "
            f"border-bottom-right-radius: {radius}px; }}"
        )
        self._detail_container.setStyleSheet(
            f"#tpl_detail_content {{ background: {t.bg_window}; "
            f"border-bottom-right-radius: {radius}px; }}"
        )
        viewport = self._detail_scroll.viewport()
        if viewport:
            viewport.setObjectName("tpl_detail_viewport")
            viewport.setStyleSheet(
                f"#tpl_detail_viewport {{ background: {t.bg_window}; "
                f"border-bottom-right-radius: {radius}px; }}"
            )

        # Propagate to details
        self._overview_detail.apply_theme()
        self._io_detail.apply_theme()
        self._page_detail.apply_theme()
        self._style_detail.apply_theme()
        if hasattr(self._heading_detail, "apply_theme"):
            self._heading_detail.apply_theme()
        elif hasattr(self._heading_detail, "_apply_theme"):
            self._heading_detail._apply_theme()
        self._table_detail.apply_theme()
        self._elements_detail.apply_theme()
        self._formula_detail.apply_theme()
        self._reference_detail.apply_theme()
        self._other_detail.apply_theme()
