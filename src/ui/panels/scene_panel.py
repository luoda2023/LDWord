"""
scene_panel — 场景配置面板（Master-Detail 架构）

与模板面板同构：左侧导航卡片 + 右侧可切换详情面板。
信息分层:
  Fixed:  场景概览 / 处理范围 / 功能开关 / 输出设置
  Dynamic: 6 个功能参数卡片 (1:1 映射 UI_CAPABILITY_GROUPS)
"""

from __future__ import annotations

from dataclasses import asdict

from src.config.scene import SceneWorkspace
from src.config.table_style_presets import TABLE_STYLE_OPTIONS
from src.config.feature_configs import (
    HeaderFooterConfig,
    TocConfig,
    CaptionConfig,
    FormulaTableConfig,
    ReferenceStyleConfig,
    WatermarkConfig,
    TableConfig,
    OutputConfig,
)
from src.config.style_variant_semantics import (
    STYLE_VARIANTS,
    is_section_style_overridden,
    enable_section_style_override,
    disable_section_style_override,
)
from src.qt_api import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui import FlowLayout, MasterDetailShell, NavigationCard
from src.shared.ui.card import Card
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.table_style_gallery import ColorTableGallery
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.feature_toggle_row import FeatureToggleRow
from src.ui.base_panel import BasePanel
from src.ui.panels.workbench.detail_controller import WorkbenchDetailController
from src.ui.panels.workbench.scene_presets import (
    UI_CAPABILITY_GROUPS,
    UI_GROUP_MAP,
    get_group_enabled,
    set_group_enabled,
)
from src.config.builtin_templates import create_builtin_template
from src.config.library import (
    default_scene_descriptor,
    get_template_entry,
    list_scene_descriptors,
    load_scene_from_library,
    load_template_from_library,
)


# ═══════════════════════════════════════════════════════════════════════
#  Card definitions
# ═══════════════════════════════════════════════════════════════════════

CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    # Fixed Layer 1: Identity
    "scn_overview":    ("场景概览",    "target"),
    # Fixed Layer 2: Scope
    "scn_scope":       ("处理范围",    "map-pin"),
    # Fixed Layer 3: Capability switches
    "scn_features":    ("功能开关",    "toggle-right"),
    # Dynamic Layer: Feature params (1:1 with UI_CAPABILITY_GROUPS)
    "scn_table_chart": ("表格与图表",  "table-2"),
    "scn_page_elem":   ("页面元素",    "panel-top"),
    "scn_formula":     ("公式规范",    "sigma"),
    "scn_citation":    ("参考文献",    "book-open"),
    "scn_cleanup":     ("校验与清理",  "scan"),
    "scn_content":     ("内容与数据",  "pen-tool"),
    # Fixed bottom
    "scn_output":      ("输出设置",    "hard-drive"),
}

CARD_ORDER = (
    "scn_overview",
    "scn_scope",
    "scn_features",
    "scn_table_chart",
    "scn_page_elem",
    "scn_formula",
    "scn_citation",
    "scn_cleanup",
    "scn_content",
    "scn_output",
)

FIXED_CARDS = ("scn_overview", "scn_scope", "scn_features", "scn_output")
DYNAMIC_CARDS = (
    "scn_table_chart", "scn_page_elem", "scn_formula",
    "scn_citation", "scn_cleanup", "scn_content",
)

# Map capability group_id → nav card id (1:1)
_GROUP_TO_CARD: dict[str, str] = {
    "table_chart":   "scn_table_chart",
    "page_elements": "scn_page_elem",
    "formula":       "scn_formula",
    "citation":      "scn_citation",
    "cleanup":       "scn_cleanup",
    "content_fill":  "scn_content",
}


def _set_combo_by_data(combo: StyledComboBox, target) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == target:
            combo.setCurrentIndex(i)
            return


def _apply_desc_theme(widget: QWidget, t, obj_name: str = "scn_form_desc") -> None:
    for w in widget.findChildren(QLabel, obj_name):
        w.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")


_PAGE_NUMBER_FORMAT_LABELS: dict[str, str] = {
    "decimal": "阿拉伯数字",
    "upperRoman": "大写罗马",
    "lowerRoman": "小写罗马",
}

_PAGE_NUMBER_SELECTOR_LABELS: dict[str, str] = {
    "cover": "封面",
    "front_matter": "前置部分",
    "abstracts": "摘要",
    "toc": "目录",
    "body": "正文",
    "back_matter": "后置部分",
    "references": "参考文献",
    "errata": "勘误",
    "appendix": "附录",
    "acknowledgment": "致谢",
    "resume": "简历",
    "all_numbered_content": "全部编号内容",
}


def _format_page_number_scope(selectors: list[str], phase_id: str) -> str:
    labels = [
        _PAGE_NUMBER_SELECTOR_LABELS.get(str(selector or ""), str(selector or ""))
        for selector in selectors
        if str(selector or "").strip()
    ]
    return " / ".join(labels) if labels else (phase_id or "未命名阶段")


def _summarize_page_number_strategy(header_footer: HeaderFooterConfig | None) -> str:
    if header_footer is None:
        return "暂时无法读取当前模板的页码策略。"

    if not header_footer.page_number_enabled:
        return "模板页脚当前不显示页码。"

    phases = list(getattr(header_footer.page_number_plan, "phases", []) or [])
    if not phases:
        return "模板已启用页码，但还没有定义编号阶段。"

    parts: list[str] = []
    for phase in phases[:3]:
        scope = _format_page_number_scope(
            list(getattr(phase, "selectors", []) or []),
            str(getattr(phase, "phase_id", "") or ""),
        )
        if not bool(getattr(phase, "visible", True)):
            rule = "隐藏页码"
        else:
            fmt = _PAGE_NUMBER_FORMAT_LABELS.get(
                str(getattr(phase, "number_format", "") or ""),
                str(getattr(phase, "number_format", "") or "decimal"),
            )
            start_mode = str(getattr(phase, "start_mode", "") or "continue")
            if start_mode == "restart":
                start_value = max(1, int(getattr(phase, "start_value", 1) or 1))
                rule = f"{fmt}，从 {start_value} 重新起号"
            else:
                rule = f"{fmt}，延续前段"
        parts.append(f"{scope}: {rule}")

    extra_phases = len(phases) - 3
    if extra_phases > 0:
        parts.append(f"另有 {extra_phases} 个阶段未展开")

    return "；".join(parts)


def _scene_has_legacy_page_number_override(scene: SceneWorkspace) -> bool:
    default_header_footer = HeaderFooterConfig()
    return (
        scene.header_footer.page_number_enabled != default_header_footer.page_number_enabled
        or asdict(scene.header_footer.page_number_plan)
        != asdict(default_header_footer.page_number_plan)
    )


# ═══════════════════════════════════════════════════════════════════════
#  Detail panes
# ═══════════════════════════════════════════════════════════════════════

class _SimpleFormDetail(QWidget):
    """Generic form-based detail pane for feature-specific config cards."""

    scene_edited = Signal()

    def __init__(self, title: str, icon_name: str, description: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon_name = icon_name
        self._is_syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._card = Card(parent=self)
        self._card.set_header(title, icon_name=icon_name)

        self._desc_label = QLabel(description)
        self._desc_label.setObjectName("scn_form_desc")
        self._desc_label.setWordWrap(True)
        self._card.add_widget(self._desc_label)

        layout.addWidget(self._card)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._desc_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")

    def _add_form_stack(self, rows: list[QWidget]) -> None:
        self._card.add_widget(TemplateFormStack(rows, parent=self._card))


# ── 场景概览 ────────────────────────────────────────

class _SceneOverviewDetail(QWidget):
    """Layer 1: Scene selector + template binding + summary."""

    scene_changed = Signal(int)
    scene_edited = Signal()

    def __init__(self, scene_descriptors: list, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._scene_descriptors = list(scene_descriptors)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)
        card.set_header("当前场景", icon_name="target")

        # Scene selector
        self._combo = StyledComboBox(self)
        for descriptor in self._scene_descriptors:
            self._combo.addItem(descriptor.display_name, descriptor.config_id)
            item_index = self._combo.count() - 1
            if descriptor.load_error:
                self._combo.setItemData(item_index, descriptor.load_error, Qt.ToolTipRole)
        self._combo.currentIndexChanged.connect(self.scene_changed.emit)
        card.add_widget(template_form_row("场景预设", self._combo, parent=card))

        # Template binding
        self._tpl_combo = StyledComboBox(self)
        self._tpl_combo.currentIndexChanged.connect(self._on_tpl_changed)
        card.add_widget(template_form_row("关联模板", self._tpl_combo, parent=card))

        # Strategy
        strategy_row = QWidget(self)
        s_lay = QHBoxLayout(strategy_row)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(8)
        self._rebuild_radio = QRadioButton("重建编号", strategy_row)
        self._preserve_radio = QRadioButton("保留原编号", strategy_row)
        self._rebuild_radio.setChecked(True)
        self._rebuild_radio.toggled.connect(self._on_strategy_changed)
        s_lay.addWidget(self._rebuild_radio)
        s_lay.addWidget(self._preserve_radio)
        s_lay.addStretch(1)
        card.add_widget(template_form_row("编号策略", strategy_row, parent=card))

        # Description
        self._desc = QLabel("", self)
        self._desc.setObjectName("scn_desc")
        self._desc.setWordWrap(True)
        card.add_widget(self._desc)

        # Summary
        self._summary = QLabel("", self)
        self._summary.setObjectName("scn_summary")
        self._summary.setWordWrap(True)
        card.add_widget(self._summary)

        layout.addWidget(card)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._desc.setText(scene.description or "")
        for idx, descriptor in enumerate(self._scene_descriptors):
            if descriptor.config_id == scene.scene_id:
                self._combo.blockSignals(True)
                self._combo.setCurrentIndex(idx)
                self._combo.blockSignals(False)
                break

        # Populate template combo
        self._tpl_combo.blockSignals(True)
        self._tpl_combo.clear()
        template_ids = list(scene.compatible_template_ids or [])
        if not template_ids:
            seed = str(scene.template_id or scene.default_template_id or "").strip()
            if seed:
                template_ids.append(seed)
        for template_id in template_ids:
            entry = get_template_entry(template_id)
            label = entry.name if entry is not None else template_id
            self._tpl_combo.addItem(label, template_id)
        for i in range(self._tpl_combo.count()):
            if self._tpl_combo.itemData(i) == scene.template_id:
                self._tpl_combo.setCurrentIndex(i)
                break
        self._tpl_combo.blockSignals(False)

        # Strategy
        self._rebuild_radio.setChecked(scene.strict_mode)
        self._preserve_radio.setChecked(not scene.strict_mode)

        # Summary
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        if self._current_scene is None:
            return
        scene = self._current_scene
        enabled = sum(1 for v in scene.format_scope.sections.values() if v)
        total = len(scene.format_scope.sections)
        cap_count = sum(
            1 for g in UI_CAPABILITY_GROUPS if get_group_enabled(scene, g)
        )
        strategy = "重建编号" if scene.strict_mode else "保留原编号"
        self._summary.setText(
            f"策略: {strategy} · {enabled}/{total}个分区 · {cap_count}项功能"
        )

    def _on_tpl_changed(self, _idx: int) -> None:
        if self._current_scene is None:
            return
        tpl_id = self._tpl_combo.currentData()
        if tpl_id:
            self._current_scene.template_id = str(tpl_id)
            self.scene_edited.emit()

    def _on_strategy_changed(self, _checked: bool) -> None:
        if self._current_scene is None:
            return
        self._current_scene.strict_mode = self._rebuild_radio.isChecked()
        self._refresh_summary()
        self.scene_edited.emit()

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._desc.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")
        self._summary.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_hint};")


# ── 处理范围 ────────────────────────────────────────

class _ScopeDetail(QWidget):
    """Layer 2: Processing scope — section checkboxes + section style overrides."""

    scope_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._current_template = None
        self._is_syncing = False

        self._desc_labels: list[QLabel] = []
        self._form_labels: list[QLabel] = []
        self._variant_labels: list[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)
        card.set_header("处理范围", icon_name="map-pin")

        desc = QLabel("选择本场景要处理的文档区域。有独立样式需求的分区可开启自定义。")
        desc.setWordWrap(True)
        self._desc_labels.append(desc)
        card.add_widget(desc)

        # Section checkboxes
        self._zone_checks: dict[str, QCheckBox] = {}
        zone_labels = {
            "body": "正文", "references": "参考文献", "acknowledgment": "致谢",
            "appendix": "附录", "abstract_cn": "中文摘要", "abstract_en": "英文摘要",
            "toc": "目录", "errata": "勘误页", "resume": "个人简历",
        }
        zones_widget = QWidget(self)
        self._zones_flow = FlowLayout(zones_widget, h_spacing=16, v_spacing=4)
        self._zones_flow.setContentsMargins(0, 6, 0, 0)

        for zone_id, label in zone_labels.items():
            cb = QCheckBox(label, zones_widget)
            cb.toggled.connect(self._on_edited)
            self._zone_checks[zone_id] = cb
            self._zones_flow.addWidget(cb)

        card.add_widget(zones_widget)

        # Section style overrides — one row per STYLE_VARIANT
        style_header = QLabel("分区样式")
        self._form_labels.append(style_header)
        card.add_widget(style_header)

        style_desc = QLabel("开启的分区可设置独立样式（默认跟随正文）。")
        style_desc.setWordWrap(True)
        self._desc_labels.append(style_desc)
        card.add_widget(style_desc)

        self._variant_toggles: dict[str, ToggleSwitch] = {}
        self._variant_rows: dict[str, QWidget] = {}
        for variant in STYLE_VARIANTS:
            row = QWidget(self)
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(0, 2, 0, 2)
            r_lay.setSpacing(8)
            lbl = QLabel(variant.label, row)
            self._variant_labels.append(lbl)
            r_lay.addWidget(lbl, 1)
            toggle = ToggleSwitch(row, checked=False)
            toggle.setToolTip(f"为「{variant.label}」启用独立样式")
            toggle.toggled_signal.connect(
                lambda checked, vk=variant.key: self._on_variant_toggled(vk, checked)
            )
            r_lay.addWidget(toggle)
            self._variant_toggles[variant.key] = toggle
            self._variant_rows[variant.key] = row
            card.add_widget(row)

        layout.addWidget(card)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_scene(self, scene: SceneWorkspace, template=None) -> None:
        self._current_scene = scene
        if template is not None:
            self._current_template = template
        self._is_syncing = True
        try:
            for zone_id, cb in self._zone_checks.items():
                cb.setChecked(scene.format_scope.sections.get(zone_id, False))
            # Update variant toggles
            for variant in STYLE_VARIANTS:
                toggle = self._variant_toggles.get(variant.key)
                if toggle:
                    toggle.setChecked(is_section_style_overridden(scene, variant.key))
                # Visibility: only show if the section is enabled
                row = self._variant_rows.get(variant.key)
                if row:
                    section_on = scene.format_scope.sections.get(variant.section_type, False)
                    row.setVisible(section_on)
        finally:
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        for zone_id, cb in self._zone_checks.items():
            self._current_scene.format_scope.sections[zone_id] = cb.isChecked()
        # Update variant row visibility
        for variant in STYLE_VARIANTS:
            row = self._variant_rows.get(variant.key)
            if row:
                on = self._current_scene.format_scope.sections.get(variant.section_type, False)
                row.setVisible(on)
                # If section turned off, also disable its override
                if not on:
                    toggle = self._variant_toggles.get(variant.key)
                    if toggle and toggle.isChecked():
                        toggle.setChecked(False)
                        disable_section_style_override(self._current_scene, variant.key)
        self.scope_changed.emit()

    def _on_variant_toggled(self, variant_key: str, checked: bool) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        if checked:
            tpl = self._current_template
            if tpl is None:
                try:
                    tpl = load_template_from_library(self._current_scene.template_id or "default")
                except Exception:
                    tpl = create_builtin_template("default")
            enable_section_style_override(self._current_scene, tpl, variant_key)
        else:
            disable_section_style_override(self._current_scene, variant_key)
        self.scope_changed.emit()

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        desc_ss = f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        for lbl in self._desc_labels:
            lbl.setStyleSheet(desc_ss)
        form_ss = (
            f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.text_secondary};"
        )
        for lbl in self._form_labels:
            lbl.setStyleSheet(form_ss)
        var_ss = f"font-size: {t.font_size_sm}px; color: {t.text_primary};"
        for lbl in self._variant_labels:
            lbl.setStyleSheet(var_ss)


# ── 功能开关 ────────────────────────────────────────

class _FeaturesDetail(QWidget):
    """Layer 3: Feature group toggles — triggers dynamic card visibility."""

    feature_toggled = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._is_syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)
        card.set_header("功能开关", icon_name="toggle-right")

        self._desc_label = QLabel("开启功能后，对应的配置卡片会出现在左侧导航中。")
        self._desc_label.setWordWrap(True)
        card.add_widget(self._desc_label)

        self._feature_rows: dict[str, FeatureToggleRow] = {}
        for group in UI_CAPABILITY_GROUPS:
            row = FeatureToggleRow(group.label, parent=card)
            row.toggled.connect(
                lambda enabled, gid=group.group_id: self._on_toggle(gid, enabled)
            )
            self._feature_rows[group.group_id] = row
            card.add_widget(row)

        layout.addWidget(card)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            for group_id, row in self._feature_rows.items():
                group = UI_GROUP_MAP.get(group_id)
                enabled = get_group_enabled(scene, group) if group else False
                row.set_checked(enabled)
        finally:
            self._is_syncing = False

    def _on_toggle(self, group_id: str, enabled: bool) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        group = UI_GROUP_MAP.get(group_id)
        if group:
            set_group_enabled(self._current_scene, group, enabled)
        self.feature_toggled.emit(group_id, enabled)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._desc_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")


# ── 表格与图表 ──────────────────────────────────────

class _TableChartDetail(_SimpleFormDetail):
    """Detail pane for table + caption config."""

    def __init__(self, parent=None):
        super().__init__("表格与图表", "table-2", "编辑表格边框、布局和题注编号。", parent)
        self._current_scene: SceneWorkspace | None = None

        _BORDER_MODES = tuple((option.key, option.label) for option in TABLE_STYLE_OPTIONS)
        rows = []

        self._border = StyledComboBox(self)
        for val, lbl in _BORDER_MODES:
            self._border.addItem(lbl, val)
        self._border.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("边框样式", self._border, parent=self._card))

        self._color_gallery = ColorTableGallery(self._card)
        self._color_gallery.selection_changed.connect(self._on_edited)
        rows.append(self._color_gallery)

        _LAYOUT_MODES = (("smart", "智能布局"), ("compact", "紧凑布局"), ("full", "撑满布局"), ("keep", "保留原样"))
        self._layout_mode = StyledComboBox(self)
        for val, lbl in _LAYOUT_MODES:
            self._layout_mode.addItem(lbl, val)
        self._layout_mode.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("布局模式", self._layout_mode, parent=self._card))

        self._repeat_header = ToggleSwitch(self, checked=False)
        self._repeat_header.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("跨页重复表头", self._repeat_header, parent=self._card))

        _NUMBERING = (("chapter", "按章编号"), ("global", "全局编号"))
        self._caption_mode = StyledComboBox(self)
        for val, lbl in _NUMBERING:
            self._caption_mode.addItem(lbl, val)
        self._caption_mode.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("题注编号", self._caption_mode, parent=self._card))

        self._fig_prefix = StyledComboBox(self)
        for p in ("图", "Fig.", "Figure"):
            self._fig_prefix.addItem(p)
        self._fig_prefix.setEditable(True)
        self._fig_prefix.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("图前缀", self._fig_prefix, parent=self._card))

        self._tbl_prefix = StyledComboBox(self)
        for p in ("表", "Tab.", "Table"):
            self._tbl_prefix.addItem(p)
        self._tbl_prefix.setEditable(True)
        self._tbl_prefix.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("表前缀", self._tbl_prefix, parent=self._card))
        self._add_form_stack(rows)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            _set_combo_by_data(self._border, scene.table.border_mode)
            self._color_gallery.set_selection(
                getattr(scene.table, "color_table_accent", "blue"),
                getattr(scene.table, "color_table_variant", "header_grid"),
            )
            _set_combo_by_data(self._layout_mode, scene.table.layout_mode)
            self._repeat_header.setChecked(scene.table.repeat_header)
            _set_combo_by_data(self._caption_mode, scene.caption.numbering_mode)
            self._fig_prefix.setCurrentText(scene.caption.figure_prefix)
            self._tbl_prefix.setCurrentText(scene.caption.table_prefix)
        finally:
            self._is_syncing = False
        self._sync_color_gallery_state()

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.table.border_mode = str(self._border.currentData() or "three_line")
        self._current_scene.table.color_table_accent = self._color_gallery.selected_palette()
        self._current_scene.table.color_table_variant = self._color_gallery.selected_variant()
        self._current_scene.table.layout_mode = str(self._layout_mode.currentData() or "smart")
        self._current_scene.table.repeat_header = self._repeat_header.isChecked()
        self._current_scene.caption.numbering_mode = str(self._caption_mode.currentData() or "chapter")
        self._current_scene.caption.figure_prefix = self._fig_prefix.currentText()
        self._current_scene.caption.table_prefix = self._tbl_prefix.currentText()
        self._sync_color_gallery_state()
        self.scene_edited.emit()

    def _sync_color_gallery_state(self) -> None:
        self._color_gallery.setVisible(str(self._border.currentData() or "") == "color_table")


# ── 页面元素 ────────────────────────────────────────

class _PageElementsDetail(_SimpleFormDetail):
    """Detail pane for scene-owned page elements and template-owned page numbers."""

    def __init__(self, parent=None):
        super().__init__("页面元素", "panel-top", "编辑页眉模式和目录，并查看模板页码策略。", parent)
        self._current_scene: SceneWorkspace | None = None
        self._current_template = None

        _HEADER_MODES = (("styleref", "STYLEREF 跟随"), ("fixed", "固定页眉"), ("none", "无页眉"))
        self._header_mode = StyledComboBox(self)
        for val, lbl in _HEADER_MODES:
            self._header_mode.addItem(lbl, val)
        self._header_mode.currentIndexChanged.connect(self._on_edited)
        self._add_form_stack([
            template_form_row("页眉模式", self._header_mode, parent=self._card),
        ])

        self._page_number_owner = QLabel("模板控制", self)
        self._page_number_owner.setObjectName("scn_page_number_owner")
        self._add_form_stack([
            template_form_row("页码来源", self._page_number_owner, parent=self._card),
        ])

        self._page_number_summary = QLabel("", self)
        self._page_number_summary.setObjectName("scn_page_number_summary")
        self._page_number_summary.setWordWrap(True)
        self._card.add_widget(self._page_number_summary)

        self._page_number_hint = QLabel("页码策略由模板统一定义，请到模板面板的“页面元素”中调整。", self)
        self._page_number_hint.setObjectName("scn_page_number_hint")
        self._page_number_hint.setWordWrap(True)
        self._card.add_widget(self._page_number_hint)

        self._page_number_compat_note = QLabel("", self)
        self._page_number_compat_note.setObjectName("scn_page_number_compat_note")
        self._page_number_compat_note.setWordWrap(True)
        self._page_number_compat_note.hide()
        self._card.add_widget(self._page_number_compat_note)

        self._header_border = ToggleSwitch(self, checked=True)
        self._header_border.toggled_signal.connect(self._on_edited)
        rows = [template_form_row("页眉横线", self._header_border, parent=self._card)]

        self._toc_enabled = ToggleSwitch(self, checked=True)
        self._toc_enabled.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("启用目录", self._toc_enabled, parent=self._card))

        self._toc_depth = StyledComboBox(self)
        for lvl in range(1, 7):
            self._toc_depth.addItem(f"{lvl} 级", lvl)
        self._toc_depth.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("目录深度", self._toc_depth, parent=self._card))
        self._add_form_stack(rows)

    def set_scene(self, scene: SceneWorkspace, template=None) -> None:
        self._current_scene = scene
        self._current_template = template
        self._is_syncing = True
        try:
            _set_combo_by_data(self._header_mode, scene.header_footer.header_mode)
            self._header_border.setChecked(scene.header_footer.header_border)
            self._toc_enabled.setChecked(scene.toc.enabled)
            _set_combo_by_data(self._toc_depth, scene.toc.max_level)
            self._refresh_page_number_summary()
        finally:
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        hf = self._current_scene.header_footer
        hf.header_mode = str(self._header_mode.currentData() or "styleref")
        hf.header_border = self._header_border.isChecked()
        self._current_scene.toc.enabled = self._toc_enabled.isChecked()
        self._current_scene.toc.max_level = int(self._toc_depth.currentData() or 3)
        self.scene_edited.emit()

    def _refresh_page_number_summary(self) -> None:
        if self._current_scene is None:
            return

        template_name = str(getattr(self._current_template, "name", "") or "").strip()
        template_id = str(getattr(self._current_scene, "template_id", "") or "").strip()
        if self._current_template is None:
            if template_id:
                self._page_number_owner.setText(f"模板控制（{template_id} 未加载）")
            else:
                self._page_number_owner.setText("未绑定模板")
        elif template_name:
            self._page_number_owner.setText(f"模板控制（{template_name}）")
        else:
            self._page_number_owner.setText("模板控制")

        self._page_number_summary.setText(
            _summarize_page_number_strategy(
                getattr(self._current_template, "header_footer", None)
            )
        )

        has_legacy_override = _scene_has_legacy_page_number_override(self._current_scene)
        self._page_number_compat_note.setVisible(has_legacy_override)
        if has_legacy_override:
            self._page_number_compat_note.setText(
                "检测到当前场景仍携带旧版页码覆盖，运行时可能继续覆盖模板设置；后续应迁移到模板侧统一维护。"
            )
        else:
            self._page_number_compat_note.clear()

    def apply_theme(self) -> None:
        super().apply_theme()
        t = get_theme()
        self._page_number_owner.setStyleSheet(
            f"font-size: {t.font_size_md}px; color: {t.text_primary};"
        )
        self._page_number_summary.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._page_number_hint.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )
        self._page_number_compat_note.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.warning};"
        )


# ── 公式规范 ────────────────────────────────────────

class _FormulaDetail(_SimpleFormDetail):
    """Detail pane for formula config."""

    def __init__(self, parent=None):
        super().__init__("公式规范", "sigma", "编辑公式字体、字号和编号格式。", parent)
        self._current_scene: SceneWorkspace | None = None

        self._font_combo = StyledComboBox(self)
        for f in ("Times New Roman", "Cambria Math", "Latin Modern Math"):
            self._font_combo.addItem(f)
        self._font_combo.currentIndexChanged.connect(self._on_edited)
        rows = [template_form_row("公式字体", self._font_combo, parent=self._card)]

        self._unify_font = ToggleSwitch(self, checked=True)
        self._unify_font.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("统一字体", self._unify_font, parent=self._card))

        self._unify_size = ToggleSwitch(self, checked=True)
        self._unify_size.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("统一字号", self._unify_size, parent=self._card))

        self._unify_spacing = ToggleSwitch(self, checked=True)
        self._unify_spacing.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("统一间距", self._unify_spacing, parent=self._card))
        self._add_form_stack(rows)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            idx = self._font_combo.findText(scene.formula_table.formula_font_name)
            if idx >= 0:
                self._font_combo.setCurrentIndex(idx)
            self._unify_font.setChecked(scene.formula_style.unify_font)
            self._unify_size.setChecked(scene.formula_style.unify_size)
            self._unify_spacing.setChecked(scene.formula_style.unify_spacing)
        finally:
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.formula_table.formula_font_name = self._font_combo.currentText()
        self._current_scene.formula_style.unify_font = self._unify_font.isChecked()
        self._current_scene.formula_style.unify_size = self._unify_size.isChecked()
        self._current_scene.formula_style.unify_spacing = self._unify_spacing.isChecked()
        self.scene_edited.emit()


# ── 参考文献 ────────────────────────────────────────

class _CitationDetail(_SimpleFormDetail):
    """Detail pane for reference/citation config."""

    def __init__(self, parent=None):
        super().__init__("参考文献", "book-open", "编辑参考文献排版样式。", parent)
        self._current_scene: SceneWorkspace | None = None

        self._auto_number = ToggleSwitch(self, checked=True)
        self._auto_number.toggled_signal.connect(self._on_edited)
        rows = [template_form_row("自动编号", self._auto_number, parent=self._card)]

        self._superscript = ToggleSwitch(self, checked=False)
        self._superscript.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("上标页码", self._superscript, parent=self._card))
        self._add_form_stack(rows)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._auto_number.setChecked(scene.citation_link.auto_number_reference_entries)
            self._superscript.setChecked(scene.citation_link.superscript_outer_page_numbers)
        finally:
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.citation_link.auto_number_reference_entries = self._auto_number.isChecked()
        self._current_scene.citation_link.superscript_outer_page_numbers = self._superscript.isChecked()
        self.scene_edited.emit()


# ── 校验与清理 ──────────────────────────────────────

class _CleanupDetail(_SimpleFormDetail):
    """Detail pane for MD cleanup + whitespace options."""

    def __init__(self, parent=None):
        super().__init__("校验与清理", "scan", "编辑 Markdown 修复和空白规范选项。", parent)
        self._current_scene: SceneWorkspace | None = None

        self._fix_breaks = ToggleSwitch(self, checked=True)
        self._fix_breaks.toggled_signal.connect(self._on_edited)
        rows = [template_form_row("段落修复", self._fix_breaks, parent=self._card)]

        self._remove_empty = ToggleSwitch(self, checked=True)
        self._remove_empty.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("空行清理", self._remove_empty, parent=self._card))

        self._normalize_spaces = ToggleSwitch(self, checked=True)
        self._normalize_spaces.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("空格规范", self._normalize_spaces, parent=self._card))
        self._add_form_stack(rows)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._fix_breaks.setChecked(getattr(scene.md_cleanup, 'fix_paragraph_breaks', True))
            self._remove_empty.setChecked(getattr(scene.md_cleanup, 'remove_empty_paragraphs', True))
            self._normalize_spaces.setChecked(getattr(scene.whitespace, 'normalize_spaces', True))
        finally:
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        if hasattr(self._current_scene.md_cleanup, 'fix_paragraph_breaks'):
            self._current_scene.md_cleanup.fix_paragraph_breaks = self._fix_breaks.isChecked()
        if hasattr(self._current_scene.md_cleanup, 'remove_empty_paragraphs'):
            self._current_scene.md_cleanup.remove_empty_paragraphs = self._remove_empty.isChecked()
        if hasattr(self._current_scene.whitespace, 'normalize_spaces'):
            self._current_scene.whitespace.normalize_spaces = self._normalize_spaces.isChecked()
        self.scene_edited.emit()


# ── 内容与数据 ──────────────────────────────────────

class _ContentDetail(_SimpleFormDetail):
    """Detail pane for watermark + content fill."""

    def __init__(self, parent=None):
        super().__init__("内容与数据", "pen-tool", "编辑水印配置。", parent)
        self._current_scene: SceneWorkspace | None = None

        self._watermark_enabled = ToggleSwitch(self, checked=False)
        self._watermark_enabled.toggled_signal.connect(self._on_edited)
        self._card.add_widget(template_form_row("启用水印", self._watermark_enabled, parent=self._card))

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._watermark_enabled.setChecked(scene.watermark.enabled)
        finally:
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.watermark.enabled = self._watermark_enabled.isChecked()
        self.scene_edited.emit()


# ── 输出设置 ────────────────────────────────────────

class _OutputDetail(_SimpleFormDetail):
    """Detail pane for output toggles."""

    def __init__(self, parent=None):
        super().__init__("输出设置", "hard-drive", "选择需要生成的输出文件。", parent)
        self._current_scene: SceneWorkspace | None = None

        self._final_docx = ToggleSwitch(self, checked=True)
        self._final_docx.toggled_signal.connect(self._on_edited)
        rows = [template_form_row("最终 DOCX", self._final_docx, parent=self._card)]

        self._compare_docx = ToggleSwitch(self, checked=True)
        self._compare_docx.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("对比 DOCX", self._compare_docx, parent=self._card))

        self._report_json = ToggleSwitch(self, checked=True)
        self._report_json.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("报告 JSON", self._report_json, parent=self._card))

        self._report_md = ToggleSwitch(self, checked=True)
        self._report_md.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("报告 Markdown", self._report_md, parent=self._card))
        self._add_form_stack(rows)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._final_docx.setChecked(scene.output.final_docx)
            self._compare_docx.setChecked(scene.output.compare_docx)
            self._report_json.setChecked(scene.output.report_json)
            self._report_md.setChecked(scene.output.report_markdown)
        finally:
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.output.final_docx = self._final_docx.isChecked()
        self._current_scene.output.compare_docx = self._compare_docx.isChecked()
        self._current_scene.output.report_json = self._report_json.isChecked()
        self._current_scene.output.report_markdown = self._report_md.isChecked()
        self.scene_edited.emit()


# ═══════════════════════════════════════════════════════════════════════
#  Main Panel (Master-Detail)
# ═══════════════════════════════════════════════════════════════════════

class ScenePanel(BasePanel):
    """Master-detail scene configuration panel."""

    panel_title = "场景配置"
    panel_icon = "target"

    def _setup_ui(self) -> None:
        self.setObjectName("ScenePanel")
        self._current_scene_path = self.bridge.current_scene_path()
        self._current_scene_source = self.bridge.current_scene_source()
        self._scene_descriptors = list_scene_descriptors()

        current_scene = self.bridge.current_scene()
        if current_scene is not None:
            self._current_scene = current_scene
        else:
            default_descriptor = default_scene_descriptor()
            if default_descriptor is not None:
                self._current_scene = load_scene_from_library(default_descriptor.config_id)
                self._current_scene_path = str(default_descriptor.path)
                self._current_scene_source = "library"
            else:
                self._current_scene = SceneWorkspace(scene_id="custom", template_id="default")
                self._current_scene_source = "runtime"

        self._shell = MasterDetailShell(
            self,
            panel_name="ScenePanel",
            nav_object_name="scn_navigation",
            detail_object_name="scn_detail",
            detail_content_object_name="scn_detail_content",
        )
        self._layout = self._shell.layout
        self._nav_rail = self._shell.nav_rail
        self._detail_scroll = self._shell.detail_scroll
        self._detail_container = self._shell.detail_container
        self._detail_layout = self._shell.detail_layout

        # Build detail panes
        self._overview = _SceneOverviewDetail(self._scene_descriptors)
        self._scope = _ScopeDetail()
        self._features = _FeaturesDetail()
        self._table_chart = _TableChartDetail()
        self._page_elem = _PageElementsDetail()
        self._formula = _FormulaDetail()
        self._citation = _CitationDetail()
        self._cleanup = _CleanupDetail()
        self._content = _ContentDetail()
        self._output = _OutputDetail()

        self._detail_map: dict[str, QWidget] = {
            "scn_overview":    self._overview,
            "scn_scope":       self._scope,
            "scn_features":    self._features,
            "scn_table_chart": self._table_chart,
            "scn_page_elem":   self._page_elem,
            "scn_formula":     self._formula,
            "scn_citation":    self._citation,
            "scn_cleanup":     self._cleanup,
            "scn_content":     self._content,
            "scn_output":      self._output,
        }
        self._details = WorkbenchDetailController(
            self._detail_container,
            self._detail_layout,
            self._detail_scroll,
        )
        self._details.register_details(self._detail_map)

        # Build navigation cards
        self._nav_cards: dict[str, NavigationCard] = {}

        # Fixed top cards
        for card_id in ("scn_overview", "scn_scope", "scn_features"):
            title, icon = CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

        # Section header
        self._nav_rail.add_section_header("功能参数")

        # Dynamic cards
        for card_id in DYNAMIC_CARDS:
            title, icon = CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

        # Section header for output
        self._nav_rail.add_section_header("输出")

        # Fixed bottom card
        card_id = "scn_output"
        title, icon = CARD_DEFINITIONS[card_id]
        card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
        self._nav_cards[card_id] = card
        self._nav_rail.add_card(card_id, card)

        # Initial state
        self._apply_scene(self._current_scene)
        if self.bridge.current_scene() is None:
            self.bridge.set_current_scene(
                self._current_scene,
                config_id=self._current_scene.scene_id,
                path=self._current_scene_path,
                source=self._current_scene_source,
                emit_signal=False,
            )
        if self.bridge.current_template() is None:
            self._sync_bound_template_from_scene(clear_dirty=True)
        self._show_detail("scn_overview")
        self._nav_rail.select_card("scn_overview")
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        self.bridge.scene_changed.connect(self.on_scene_changed)
        self.bridge.template_changed.connect(self.on_template_changed)
        self._nav_rail.card_selected.connect(self._show_detail)
        self._overview.scene_changed.connect(self._on_scene_changed)
        self._overview.scene_edited.connect(self._on_scene_edited)
        self._scope.scope_changed.connect(self._on_scene_edited)
        self._features.feature_toggled.connect(self._on_feature_toggled)
        for detail in (
            self._table_chart, self._page_elem, self._formula,
            self._citation, self._cleanup, self._content, self._output,
        ):
            detail.scene_edited.connect(self._on_scene_edited)

    def _show_detail(self, card_id: str) -> None:
        self._details.show_detail(card_id)

    def _on_scene_changed(self, index: int) -> None:
        if 0 <= index < len(self._scene_descriptors):
            descriptor = self._scene_descriptors[index]
            if descriptor.load_error:
                if self._current_scene is not None:
                    restore_index = next(
                        (
                            idx
                            for idx, item in enumerate(self._scene_descriptors)
                            if item.config_id == self._current_scene.scene_id
                        ),
                        -1,
                    )
                    if restore_index >= 0 and restore_index != index:
                        detail_combo = getattr(self._overview, "_combo", None)
                        if detail_combo is not None:
                            blocked = detail_combo.blockSignals(True)
                            detail_combo.setCurrentIndex(restore_index)
                            detail_combo.blockSignals(blocked)
                return
            self._current_scene = load_scene_from_library(descriptor.config_id)
            self._current_scene_path = str(descriptor.path)
            self._current_scene_source = "library"
            self.bridge.clear_scene_dirty()
            self.bridge.set_current_scene(
                self._current_scene,
                config_id=descriptor.config_id,
                path=self._current_scene_path,
                source=self._current_scene_source,
            )
            self._sync_bound_template_from_scene(clear_dirty=True)

    def _apply_scene(self, scene: SceneWorkspace) -> None:
        self._overview.set_scene(scene)
        template = None
        template_id = str(scene.template_id or "").strip()
        if template_id:
            if self.bridge.current_template_id() == template_id:
                template = self.bridge.current_template()
            if template is None:
                try:
                    template = load_template_from_library(template_id)
                except Exception:
                    template = None
        self._scope.set_scene(scene, template)
        self._features.set_scene(scene)
        self._table_chart.set_scene(scene)
        self._page_elem.set_scene(scene, template)
        self._formula.set_scene(scene)
        self._citation.set_scene(scene)
        self._cleanup.set_scene(scene)
        self._content.set_scene(scene)
        self._output.set_scene(scene)
        self._update_dynamic_card_visibility()

    def _on_feature_toggled(self, group_id: str, enabled: bool) -> None:
        self._update_dynamic_card_visibility()
        self._on_scene_edited()

    def _update_dynamic_card_visibility(self) -> None:
        """Show/hide dynamic nav cards based on which features are enabled."""
        scene = self._current_scene
        for group_id, card_id in _GROUP_TO_CARD.items():
            group = UI_GROUP_MAP.get(group_id)
            enabled = get_group_enabled(scene, group) if group else False
            nav_card = self._nav_cards.get(card_id)
            if nav_card:
                nav_card.setVisible(enabled)

    def _on_scene_edited(self) -> None:
        self._overview.set_scene(self._current_scene)
        self.bridge.set_current_scene(
            self._current_scene,
            config_id=self._current_scene.scene_id,
            path=self._current_scene_path,
            source=self._current_scene_source,
        )
        self.bridge.mark_scene_dirty()
        self._sync_bound_template_from_scene(clear_dirty=False)

    def _sync_bound_template_from_scene(self, *, clear_dirty: bool) -> None:
        template_id = str(getattr(self._current_scene, "template_id", "") or "").strip()
        if not template_id:
            return
        entry = get_template_entry(template_id)
        try:
            template = load_template_from_library(template_id)
        except Exception:
            return
        self.bridge.set_current_template(
            template,
            config_id=template_id,
            path=str(entry.path) if entry is not None else "",
            source="library" if entry is not None else "builtin",
        )
        if clear_dirty:
            self.bridge.clear_template_dirty()

    def on_scene_changed(self, scene: SceneWorkspace) -> None:
        if scene is None:
            return
        self._current_scene = scene
        self._current_scene_path = self.bridge.current_scene_path()
        self._current_scene_source = self.bridge.current_scene_source()
        self._apply_scene(scene)

    def on_template_changed(self, template) -> None:
        if self._current_scene is None:
            return
        self._scope.set_scene(self._current_scene, template)
        self._page_elem.set_scene(self._current_scene, template)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._shell.apply_theme(t)

        # Propagate to details
        for detail in self._detail_map.values():
            if hasattr(detail, "apply_theme"):
                detail.apply_theme()
