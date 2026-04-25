from __future__ import annotations

from pathlib import Path

import html as _html

from src.qt_api import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    Qt,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.qt_api import QIcon, QPropertyAnimation, QProgressBar
from src.shared.ui import DashedSeparator
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.feature_toggle_row import FeatureToggleRow
from src.shared.engine.document_structure_preview import (
    StructurePreviewItem,
    analyze_document_structure,
    suppression_selectors_before,
)
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.icons.catalog import get_icon
from src.ui.panels.workbench.state import ExecutionProgressState, ExecutionResultState

from .quick_execution_drop_area import QuickExecutionDropArea
from .quick_execution_presenter import (
    FEATURE_DEFINITIONS,
    QuickExecutionStatusViewModel,
    build_feature_navigation_snapshot,
    build_navigation_snapshot,
    build_ready_status,
    build_running_status,
)
from src.config.library import (
    default_scene_descriptor,
    get_template_entry,
    list_scene_descriptors,
    load_scene_from_library,
)
from src.config.scene import SceneWorkspace
from .scene_presets import (
    LEGACY_FEATURE_GROUP_MAP,
    UI_CAPABILITY_GROUPS,
    UI_GROUP_MAP,
    get_group_enabled,
    set_group_enabled,
)


class QuickExecutionDetail(QWidget):
    """Workbench V2 quick-execution detail pane (redesigned)."""

    feature_toggled = Signal(str, bool)
    feature_config_requested = Signal(str)
    summary_changed = Signal()
    execute_requested = Signal()
    cancel_requested = Signal()
    document_selected = Signal(str)
    binding_changed = Signal(object, str)
    scene_config_changed = Signal(object)

    FEATURE_DEFINITIONS = FEATURE_DEFINITIONS
    FEATURE_ID_ALIASES = LEGACY_FEATURE_GROUP_MAP

    def __init__(self, parent=None):
        super().__init__(parent)
        self._feature_rows: dict[str, FeatureToggleRow] = {}
        self._zone_checks: dict[str, QCheckBox] = {}
        self._execution_running = False
        self._last_result_status = "idle"
        self._known_execution_modules: list[str] = []
        self._structure_items: list[StructurePreviewItem] = []
        self._binding_signal_blocked = False
        self._scene_syncing = False
        self._scene_descriptors = list_scene_descriptors()
        initial_scene = default_scene_descriptor()
        if initial_scene is None and self._scene_descriptors:
            initial_scene = self._scene_descriptors[0]
        if initial_scene is not None:
            self._current_scene = load_scene_from_library(initial_scene.config_id)
        else:
            self._current_scene = SceneWorkspace(scene_id="custom", template_id="default")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.setMinimumWidth(320)
        # Prevent vertical compression — scroll area must scroll, not squish
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # ── 1. Input file ──
        self._drop_area = QuickExecutionDropArea(self)
        self._drop_area.file_selected.connect(self._on_file_selected)
        self._drop_area.file_cleared.connect(self._on_file_cleared)
        self._layout.addWidget(self._drop_area)

        # ── 2. Scene & Template ──
        self._scene_card = Card(parent=self)
        self._build_scene_section()
        self._layout.addWidget(self._scene_card)

        # ── 3. Summary + collapsible advanced ──
        self._advanced_card = Card(parent=self)
        self._build_summary_and_advanced()
        self._layout.addWidget(self._advanced_card)

        # ── 4. Output ──
        self._output_card = Card(parent=self)
        self._build_output_section()
        self._layout.addWidget(self._output_card)

        # ── 5. Execute ──
        self._execution_card = Card(parent=self)
        self._build_execute_area()
        self._layout.addWidget(self._execution_card)

        self._layout.addStretch(1)


        # ── init ──
        self._apply_scene(self._current_scene)
        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self._emit_summary_changed()

    # ═══════════════════════════════════════════════════════════════════════
    #  Section builders
    # ═══════════════════════════════════════════════════════════════════════

    def _build_scene_section(self) -> None:
        """Build the scene + template cascade selectors."""
        # ── Section header: icon + title ──
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 6)
        header_layout.setSpacing(6)
        self._scene_card_icon = QLabel(header)
        self._scene_card_icon.setFixedSize(18, 18)
        header_layout.addWidget(self._scene_card_icon)
        self._scene_card_title = QLabel("场景与模板", header)
        self._scene_card_title.setObjectName("scene_card_title")
        header_layout.addWidget(self._scene_card_title)
        header_layout.addStretch(1)
        self._scene_card.add_widget(header)

        # ── Single row: 场景 [combo] | 模板 [combo] ──
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        # Scene icon + label + combo
        self._scene_icon_label = QLabel(row)
        self._scene_icon_label.setFixedSize(16, 16)
        row_layout.addWidget(self._scene_icon_label)

        self._scene_text_label = QLabel("场景", row)
        self._scene_text_label.setObjectName("scene_tpl_label")
        row_layout.addWidget(self._scene_text_label)

        self._scene_combo = StyledComboBox(self)
        for descriptor in self._scene_descriptors:
            self._scene_combo.addItem(descriptor.display_name, descriptor.config_id)
            item_index = self._scene_combo.count() - 1
            if descriptor.load_error:
                self._scene_combo.setItemData(item_index, descriptor.load_error, Qt.ToolTipRole)
        self._scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        row_layout.addWidget(self._scene_combo, 1)

        # Vertical dashed divider between scene & template
        self._scene_tpl_divider = DashedSeparator(orientation="vertical", parent=row)
        row_layout.addWidget(self._scene_tpl_divider)

        # Template icon + label + combo
        self._tpl_icon_label = QLabel(row)
        self._tpl_icon_label.setFixedSize(16, 16)
        row_layout.addWidget(self._tpl_icon_label)

        self._tpl_text_label = QLabel("模板", row)
        self._tpl_text_label.setObjectName("scene_tpl_label")
        row_layout.addWidget(self._tpl_text_label)

        self._template_combo = StyledComboBox(self)
        self._template_combo.currentIndexChanged.connect(self._on_template_changed)
        row_layout.addWidget(self._template_combo, 1)

        self._scene_card.add_widget(row)

    def _build_summary_and_advanced(self) -> None:
        """Build the summary line + collapsible advanced area."""
        # ── Header row: icon + title + summary + toggle chevron ──
        header = QWidget(self)
        header.setCursor(Qt.PointingHandCursor)
        header.mousePressEvent = lambda _e: self._toggle_advanced()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self._adv_header_icon = QLabel(header)
        self._adv_header_icon.setFixedSize(18, 18)
        header_layout.addWidget(self._adv_header_icon)

        self._adv_header_title = QLabel("高级调整", header)
        self._adv_header_title.setObjectName("adv_card_title")
        header_layout.addWidget(self._adv_header_title)

        self._summary_label = QLabel("", header)
        self._summary_label.setObjectName("wb_v2_scene_summary")
        header_layout.addWidget(self._summary_label, 1)

        self._adv_chevron = QLabel(header)
        self._adv_chevron.setFixedSize(16, 16)
        header_layout.addWidget(self._adv_chevron)

        self._advanced_card.add_widget(header)

        # ── Collapsible container ──
        self._advanced_container = QWidget(self)
        self._advanced_container.setVisible(False)
        adv_layout = QVBoxLayout(self._advanced_container)
        adv_layout.setContentsMargins(0, 4, 0, 0)
        adv_layout.setSpacing(6)

        # Top separator (solid)
        sep = QFrame(self._advanced_container)
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("wb_v2_adv_sep")
        adv_layout.addWidget(sep)

        # ── Strategy (inline: title + radios on one row) ──
        strategy_row = QWidget(self._advanced_container)
        strategy_layout = QHBoxLayout(strategy_row)
        strategy_layout.setContentsMargins(0, 0, 0, 0)
        strategy_layout.setSpacing(8)

        strategy_label = QLabel("结构策略", strategy_row)
        strategy_label.setObjectName("wb_v2_section_title")
        strategy_layout.addWidget(strategy_label)

        self._strategy_rebuild = QRadioButton("重建编号体系（推荐）", strategy_row)
        self._strategy_preserve = QRadioButton("保留原编号，仅修复样式", strategy_row)
        self._strategy_rebuild.setChecked(True)
        self._strategy_rebuild.toggled.connect(self._on_strategy_changed)
        strategy_layout.addWidget(self._strategy_rebuild)
        strategy_layout.addWidget(self._strategy_preserve)
        strategy_layout.addStretch(1)

        adv_layout.addWidget(strategy_row)

        # Dashed separator: strategy / zones
        self._sep_strategy_zones = DashedSeparator(orientation="horizontal", parent=self._advanced_container)
        adv_layout.addWidget(self._sep_strategy_zones)

        # ── Document structure preview / page-number start ──
        structure_row = QWidget(self._advanced_container)
        structure_layout = QHBoxLayout(structure_row)
        structure_layout.setContentsMargins(0, 0, 0, 0)
        structure_layout.setSpacing(8)

        structure_title = QLabel("页码从", structure_row)
        structure_title.setObjectName("wb_v2_section_title")
        structure_layout.addWidget(structure_title)

        self._page_start_combo = StyledComboBox(structure_row)
        self._page_start_combo.addItem("自动判断", -1)
        self._page_start_combo.currentIndexChanged.connect(self._on_page_start_changed)
        structure_layout.addWidget(self._page_start_combo, 1)

        self._structure_refresh_btn = QPushButton("重新识别", structure_row)
        self._structure_refresh_btn.setFlat(True)
        self._structure_refresh_btn.setCursor(Qt.PointingHandCursor)
        self._structure_refresh_btn.clicked.connect(lambda: self._refresh_structure_preview(self.document_path()))
        structure_layout.addWidget(self._structure_refresh_btn)
        adv_layout.addWidget(structure_row)

        self._structure_status_label = QLabel("选择文档后可确认页码起点", self._advanced_container)
        self._structure_status_label.setObjectName("wb_v2_structure_status")
        self._structure_status_label.setWordWrap(True)
        adv_layout.addWidget(self._structure_status_label)

        self._sep_structure_zones = DashedSeparator(orientation="horizontal", parent=self._advanced_container)
        adv_layout.addWidget(self._sep_structure_zones)

        # ── Processing scope (zones) ──
        zones_header = QHBoxLayout()
        zones_header.setContentsMargins(0, 0, 0, 0)
        zones_title = QLabel("处理范围", self._advanced_container)
        zones_title.setObjectName("wb_v2_section_title")
        zones_header.addWidget(zones_title)
        zones_header.addStretch(1)

        self._zones_select_all_btn = QPushButton("全选", self._advanced_container)
        self._zones_select_all_btn.setFlat(True)
        self._zones_select_all_btn.setCursor(Qt.PointingHandCursor)
        self._zones_select_all_btn.clicked.connect(self._zones_select_all)
        zones_header.addWidget(self._zones_select_all_btn)

        self._zones_clear_btn = QPushButton("清空", self._advanced_container)
        self._zones_clear_btn.setFlat(True)
        self._zones_clear_btn.setCursor(Qt.PointingHandCursor)
        self._zones_clear_btn.clicked.connect(self._zones_clear_all)
        zones_header.addWidget(self._zones_clear_btn)

        adv_layout.addLayout(zones_header)

        # Zone checkboxes container (flow layout)
        self._zones_container = QWidget(self._advanced_container)
        self._zones_flow = _FlowLayout(self._zones_container, h_spacing=12, v_spacing=4)
        adv_layout.addWidget(self._zones_container)

        # Dashed separator: zones / features
        self._sep_zones_features = DashedSeparator(orientation="horizontal", parent=self._advanced_container)
        adv_layout.addWidget(self._sep_zones_features)

        # ── Feature toggles (2-column grid with vertical divider) ──
        features_title = QLabel("处理功能", self._advanced_container)
        features_title.setObjectName("wb_v2_section_title")
        adv_layout.addWidget(features_title)

        from src.qt_api import QGridLayout
        features_grid = QWidget(self._advanced_container)
        grid = QGridLayout(features_grid)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)  # divider column — fixed width
        grid.setColumnStretch(2, 1)
        grid.setColumnMinimumWidth(1, 20)  # divider column width

        num_rows = (len(UI_CAPABILITY_GROUPS) + 1) // 2
        for i, ui_group in enumerate(UI_CAPABILITY_GROUPS):
            row = FeatureToggleRow(ui_group.label, parent=features_grid)
            row.toggled.connect(
                lambda enabled, gid=ui_group.group_id: self._on_feature_row_toggled(gid, enabled)
            )
            row.config_clicked.connect(
                lambda gid=ui_group.group_id: self._on_feature_config_requested(gid)
            )
            self._feature_rows[ui_group.group_id] = row
            r, c = i // 2, (i % 2) * 2  # columns 0 and 2 (1 is divider)
            grid.addWidget(row, r, c, Qt.AlignVCenter)

        # Vertical divider between two columns
        self._features_vdiv = DashedSeparator(orientation="vertical", parent=features_grid)
        grid.addWidget(self._features_vdiv, 0, 1, num_rows, 1)

        adv_layout.addWidget(features_grid)

        self._advanced_card.add_widget(self._advanced_container)

    def _build_output_section(self) -> None:
        """Build the output directory section – matches scene card style."""
        # ── Section header: icon + title ──
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 6)
        header_layout.setSpacing(6)
        self._output_card_icon = QLabel(header)
        self._output_card_icon.setFixedSize(18, 18)
        header_layout.addWidget(self._output_card_icon)
        self._output_card_title = QLabel("输出目录", header)
        self._output_card_title.setObjectName("output_card_title")
        header_layout.addWidget(self._output_card_title)
        header_layout.addStretch(1)
        self._output_card.add_widget(header)

        # ── Row: ○ 默认  ○ 自定义  [browse btn] ──
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        # Radio buttons
        self._output_default_radio = QRadioButton("默认", row)
        self._output_custom_radio = QRadioButton("自定义", row)
        self._output_default_radio.setChecked(True)
        self._output_custom_radio.toggled.connect(self._on_output_mode_changed)
        row_layout.addWidget(self._output_default_radio)
        row_layout.addWidget(self._output_custom_radio)

        # Browse button (hidden by default, retains size to prevent layout shake)
        self._output_browse_btn = QPushButton("选择目录", row)
        self._output_browse_btn.setCursor(Qt.PointingHandCursor)
        self._output_browse_btn.clicked.connect(self._on_output_browse)
        self._output_browse_btn.setAcceptDrops(True)
        self._output_browse_btn.installEventFilter(self)
        sp = self._output_browse_btn.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self._output_browse_btn.setSizePolicy(sp)
        self._output_browse_btn.setVisible(False)
        row_layout.addWidget(self._output_browse_btn, 1)

        row_layout.addStretch(1)

        # Store the custom output path
        self._custom_output_dir = ""

        self._output_card.add_widget(row)

    def eventFilter(self, obj, event):
        """Handle drag-drop on the output browse button."""
        from PySide6.QtCore import QEvent
        if obj is getattr(self, "_output_browse_btn", None):
            if event.type() == QEvent.Type.DragEnter:
                if event.mimeData().hasUrls():
                    for url in event.mimeData().urls():
                        if Path(url.toLocalFile()).is_dir():
                            event.acceptProposedAction()
                            return True
            elif event.type() == QEvent.Type.Drop:
                for url in event.mimeData().urls():
                    path = url.toLocalFile()
                    if Path(path).is_dir():
                        self._set_output_dir(path)
                        return True
        return super().eventFilter(obj, event)

    def _on_output_mode_changed(self, is_custom: bool) -> None:
        """Toggle between default and custom output path."""
        self._output_browse_btn.setVisible(is_custom)
        if not is_custom:
            self._custom_output_dir = ""
            self._output_browse_btn.setText("选择目录")
            self._output_browse_btn.setIcon(QIcon())
        self._emit_summary_changed()

    def _on_output_browse(self) -> None:
        """Open folder picker for custom output directory."""
        folder = QFileDialog.getExistingDirectory(
            self, "选择输出目录", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self._set_output_dir(folder)

    def _set_output_dir(self, folder: str) -> None:
        """Apply a chosen output directory (from browse or drag-drop)."""
        self._custom_output_dir = folder
        display = Path(folder).name or folder
        self._output_browse_btn.setText(display)
        self._output_browse_btn.setIcon(get_icon("folder-open", 16, "#64748B"))
        # Auto-switch to custom mode if not already
        if not self._output_custom_radio.isChecked():
            self._output_custom_radio.setChecked(True)
        self._emit_summary_changed()

    def custom_output_dir(self) -> str:
        """Return custom output directory, or empty for default."""
        return self._custom_output_dir

    def _build_execute_area(self) -> None:
        # ── Card header: icon + "执行输出" ──
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._exec_card_icon = QLabel(header)
        self._exec_card_icon.setFixedSize(20, 20)
        header_layout.addWidget(self._exec_card_icon)

        self._exec_card_title = QLabel("执行输出", header)
        self._exec_card_title.setObjectName("wb_v2_card_header")
        header_layout.addWidget(self._exec_card_title)
        header_layout.addStretch(1)
        self._execution_card.add_widget(header)

        # ── Row: [Button LEFT] + [Status panel RIGHT, fixed height] ──
        exec_row = QWidget(self)
        exec_row_layout = QHBoxLayout(exec_row)
        exec_row_layout.setContentsMargins(0, 0, 0, 0)
        exec_row_layout.setSpacing(0)

        # Left: Execute button
        self._execute_btn = QPushButton("开始执行", self)
        self._execute_btn.setObjectName("wb_v2_execute_btn")
        self._execute_btn.setFixedHeight(get_theme().control_height_lg)
        self._execute_btn.setCursor(Qt.PointingHandCursor)
        self._execute_btn.setIcon(get_icon("play", 16, "#FFFFFF"))
        apply_button_variant(self._execute_btn, "primary")
        self._execute_btn.clicked.connect(self.execute_requested.emit)
        exec_row_layout.addWidget(self._execute_btn, 4)

        # Right: Compact status panel (fixed height = button height)
        self._exec_status_area = QWidget(exec_row)
        self._exec_status_area.setObjectName("wb_v2_exec_status_area")
        self._exec_status_area.setFixedHeight(get_theme().control_height_lg)
        status_layout = QVBoxLayout(self._exec_status_area)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(0)

        self._exec_status_label = QLabel("等待开始...", self._exec_status_area)
        self._exec_status_label.setObjectName("wb_v2_exec_status")
        self._exec_status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self._exec_status_label, 1)
        self._status_label = self._exec_status_label

        self._exec_bar = QProgressBar(self._exec_status_area)
        self._exec_bar.setObjectName("wb_v2_exec_bar")
        self._exec_bar.setRange(0, 100)
        self._exec_bar.setValue(0)
        self._exec_bar.setTextVisible(False)
        self._exec_bar.setFixedHeight(4)
        self._exec_bar.setVisible(False)
        status_layout.addWidget(self._exec_bar)

        exec_row_layout.addWidget(self._exec_status_area, 6)
        self._execution_card.add_widget(exec_row)



        # ── Log section: title + light-themed log ──
        self._log_title = QLabel("执行日志", self)
        self._log_title.setObjectName("wb_v2_log_title")
        self._execution_card.add_widget(self._log_title)

        self._exec_log = QTextEdit(self)
        self._exec_log.setReadOnly(True)
        self._exec_log.setMinimumHeight(120)
        self._exec_log.setMaximumHeight(200)
        self._exec_log.setObjectName("wb_v2_log_terminal")
        self._execution_card.add_widget(self._exec_log)
        self._exec_error_count = 0

    # ═══════════════════════════════════════════════════════════════════════
    #  Scene / template cascade logic
    # ═══════════════════════════════════════════════════════════════════════

    def _on_scene_changed(self, index: int) -> None:
        descriptor = self._scene_descriptors[index] if 0 <= index < len(self._scene_descriptors) else None
        if descriptor is not None and descriptor.load_error:
            if self._current_scene is not None:
                restore_index = self._find_scene_index(self._current_scene.scene_id)
                if restore_index >= 0 and restore_index != index:
                    blocked = self._scene_combo.blockSignals(True)
                    self._scene_combo.setCurrentIndex(restore_index)
                    self._scene_combo.blockSignals(blocked)
            self._append_exec_log("error", f"场景“{descriptor.name}”加载失败：{descriptor.load_error}")
            return

        scene_id = str(self._scene_combo.itemData(index) or "").strip()
        if not scene_id and 0 <= index < len(self._scene_descriptors):
            scene_id = self._scene_descriptors[index].config_id
        if scene_id:
            self._current_scene = load_scene_from_library(scene_id)
            self._apply_scene(self._current_scene)
            self._emit_summary_changed()
            self._emit_binding_changed()

    def _apply_scene(self, scene: SceneWorkspace) -> None:
        """Apply a scene: update templates, zones, capabilities, strategy."""
        self._scene_syncing = True
        try:
            scene_index = self._find_scene_index(scene.scene_id)
            if scene_index >= 0:
                was_blocked = self._scene_combo.blockSignals(True)
                self._scene_combo.setCurrentIndex(scene_index)
                self._scene_combo.blockSignals(was_blocked)

            # Update template combo
            was_blocked = self._template_combo.blockSignals(True)
            self._template_combo.clear()
            template_ids = list(scene.compatible_template_ids or [])
            if not template_ids:
                seed = str(scene.template_id or scene.default_template_id or "").strip()
                if seed:
                    template_ids.append(seed)
            for template_id in template_ids:
                entry = get_template_entry(template_id)
                label = entry.name if entry is not None else template_id
                self._template_combo.addItem(label, template_id)
            for index in range(self._template_combo.count()):
                if self._template_combo.itemData(index) == scene.template_id:
                    self._template_combo.setCurrentIndex(index)
                    break
            self._template_combo.blockSignals(was_blocked)

            # Update strategy radio
            self._strategy_rebuild.setChecked(bool(scene.strict_mode))
            self._strategy_preserve.setChecked(not bool(scene.strict_mode))

            # Update zones
            self._rebuild_zones(scene)

            # Update capability toggles
            for group_id, row in self._feature_rows.items():
                group = UI_GROUP_MAP.get(group_id)
                enabled = get_group_enabled(scene, group) if group else False
                was_blocked_row = row.blockSignals(True)
                row.set_checked(enabled)
                row.blockSignals(was_blocked_row)

            # Update summary
            self._update_summary_label()
        finally:
            self._scene_syncing = False

    def _rebuild_zones(self, scene: SceneWorkspace) -> None:
        """Rebuild the zone checkbox grid from SceneWorkspace.format_scope.sections."""
        # Clear old
        for cb in self._zone_checks.values():
            cb.setParent(None)
            cb.deleteLater()
        self._zone_checks.clear()

        # Zone labels
        zone_labels = {
            "body": "正文", "references": "参考文献", "acknowledgment": "致谢",
            "appendix": "附录", "abstract_cn": "中文摘要", "abstract_en": "英文摘要",
            "toc": "目录", "errata": "勘误页", "resume": "个人简历",
        }

        # Build new from format_scope.sections
        for zone_id, enabled in scene.format_scope.sections.items():
            label = zone_labels.get(zone_id, zone_id)
            cb = QCheckBox(label, self._zones_container)
            cb.setChecked(enabled)
            cb.toggled.connect(lambda checked, zid=zone_id: self._on_zone_toggled(zid, checked))
            self._zone_checks[zone_id] = cb
            self._zones_flow.addWidget(cb)

        self._apply_zone_styles()

    def _zones_select_all(self) -> None:
        for cb in self._zone_checks.values():
            cb.setChecked(True)

    def _zones_clear_all(self) -> None:
        for cb in self._zone_checks.values():
            cb.setChecked(False)

    def _on_zone_toggled(self, zone_id: str, checked: bool) -> None:
        self._current_scene.format_scope.sections[zone_id] = bool(checked)
        self._update_summary_label()
        self._emit_summary_changed()
        if not self._scene_syncing:
            self.scene_config_changed.emit(self._current_scene)

    def _update_summary_label(self) -> None:
        scene = self._current_scene
        strategy = "rebuild" if self._strategy_rebuild.isChecked() else "preserve"
        strategy_text = "重建编号" if strategy == "rebuild" else "保留原编号"

        enabled_zones = sum(1 for cb in self._zone_checks.values() if cb.isChecked())
        total_zones = len(self._zone_checks)

        enabled_caps = []
        for group_id, row in self._feature_rows.items():
            if row.is_checked() and group_id in UI_GROUP_MAP:
                enabled_caps.append(UI_GROUP_MAP[group_id].label)
        cap_count = len(enabled_caps)
        cap_text = "·".join(enabled_caps) if enabled_caps else "无"

        summary = f"{strategy_text} · {self._page_start_summary_text()} · {enabled_zones}/{total_zones}个分区 · {cap_count}项功能"
        self._summary_label.setText(summary)

    # ═══════════════════════════════════════════════════════════════════════
    #  Advanced panel toggle
    # ═══════════════════════════════════════════════════════════════════════

    def _toggle_advanced(self) -> None:
        visible = not self._advanced_container.isVisible()
        self._advanced_container.setVisible(visible)
        self._update_chevron()
        # Force immediate layout recalculation to prevent flicker
        self._advanced_card.updateGeometry()
        from src.qt_api import QApplication
        QApplication.processEvents()

    def _update_chevron(self) -> None:
        """Update chevron icon based on expanded/collapsed state."""
        if not hasattr(self, "_adv_chevron"):
            return
        t = get_theme()
        expanded = self._advanced_container.isVisible()
        icon_name = "chevron-down" if expanded else "chevron-right"
        self._adv_chevron.setPixmap(
            get_icon(icon_name, 16, t.text_hint).pixmap(16, 16)
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  Event handlers
    # ═══════════════════════════════════════════════════════════════════════

    def _on_file_selected(self, file_path: str) -> None:
        if file_path:
            self._refresh_structure_preview(file_path)
            self.document_selected.emit(file_path)
        self._emit_summary_changed()

    def _on_file_cleared(self) -> None:
        self._clear_structure_preview()
        self._emit_summary_changed()

    def _on_feature_row_toggled(self, feature_id: str, enabled: bool) -> None:
        group = UI_GROUP_MAP.get(feature_id)
        if group is not None:
            set_group_enabled(self._current_scene, group, bool(enabled))
        self.feature_toggled.emit(feature_id, bool(enabled))
        self._update_summary_label()
        self._emit_summary_changed()
        if not self._scene_syncing:
            self.scene_config_changed.emit(self._current_scene)

    def _on_strategy_changed(self, checked: bool) -> None:
        if self._scene_syncing:
            return
        self._current_scene.strict_mode = self._strategy_rebuild.isChecked()
        self._update_summary_label()
        self._emit_summary_changed()
        self.scene_config_changed.emit(self._current_scene)

    def _on_page_start_changed(self, _index: int) -> None:
        self._update_structure_status()
        self._update_summary_label()
        self._emit_summary_changed()

    def _on_feature_config_requested(self, feature_id: str) -> None:
        self.feature_config_requested.emit(feature_id)

    # ═══════════════════════════════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════════════════════════════

    def document_path(self) -> str:
        return self._drop_area.file_path()

    def set_document_path(self, file_path: str) -> None:
        cleaned = str(file_path or "").strip()
        previous = self._drop_area.file_path()
        if cleaned == previous:
            return
        was_blocked = self._drop_area.blockSignals(True)
        try:
            if cleaned:
                self._drop_area.set_file(cleaned)
            else:
                self._drop_area.clear()
        finally:
            self._drop_area.blockSignals(was_blocked)
        self._refresh_structure_preview(cleaned)
        self._emit_summary_changed()

    def set_strategy_context(
        self,
        *,
        template_name: str | None = None,
        scene_name: str | None = None,
        strict_mode: bool | None = None,
    ) -> None:
        """Legacy-compat setter; maps strict_mode → strategy."""
        self._binding_signal_blocked = True
        self._scene_syncing = True
        try:
            if scene_name:
                for idx, descriptor in enumerate(self._scene_descriptors):
                    if descriptor.name == scene_name:
                        self._scene_combo.setCurrentIndex(idx)
                        break
            if template_name:
                self._ensure_combo_value(template_name)
            if strict_mode is not None:
                self._strategy_rebuild.setChecked(bool(strict_mode))
                self._strategy_preserve.setChecked(not bool(strict_mode))
        finally:
            self._binding_signal_blocked = False
            self._scene_syncing = False
        self._emit_summary_changed()

    def set_execute_enabled(self, enabled: bool) -> None:
        self._execute_btn.setEnabled(bool(enabled))

    def set_feature_enabled(self, feature_id: str, enabled: bool) -> None:
        row = self._feature_rows.get(self._resolve_feature_id(feature_id))
        if row is None:
            raise KeyError(feature_id)
        row.set_checked(bool(enabled))

    def is_feature_enabled(self, feature_id: str) -> bool:
        row = self._feature_rows.get(self._resolve_feature_id(feature_id))
        if row is None:
            return False
        return row.is_checked()

    def _append_exec_log(self, level: str, message: str) -> None:
        """Append a log line to the always-visible light-themed log."""
        safe = _html.escape(str(message))
        t = get_theme()
        colors = {
            "info": t.text_secondary, "warning": "#D97706",
            "error": "#DC2626", "critical": "#DC2626",
            "success": "#16A34A",
        }
        c = colors.get(level.lower(), t.text_primary)
        self._exec_log.append(f'<span style="color: {c};">{safe}</span>')
        if level.lower() in ("error", "critical"):
            self._exec_error_count += 1

    def set_execution_progress(self, state: ExecutionProgressState) -> None:
        self._execution_running = True
        self._last_result_status = "running"
        self._exec_bar.setVisible(True)
        self._execute_btn.setEnabled(False)
        self._execute_btn.setText("执行中...")
        self._execute_btn.setIcon(QIcon())

        stage_text = str(state.stage_text or "执行中")
        current_step = int(state.current_step or 0)
        total_steps = int(state.total_steps or 0)
        pct = int(current_step / max(total_steps, 1) * 100)
        self._exec_bar.setValue(pct)
        self._exec_status_label.setText(f"{stage_text} {pct}%")
        if stage_text not in self._known_execution_modules:
            self._known_execution_modules.append(stage_text)
        self._append_exec_log("info", f"执行阶段：{stage_text}")
        self.summary_changed.emit()

    def set_execution_result(self, state: ExecutionResultState) -> None:
        self._execution_running = False
        self._last_result_status = state.status
        success = state.status in {"success", "partial_success"}
        self._exec_bar.setValue(100 if success else self._exec_bar.value())
        self._exec_status_label.setText("已完成" if success else "执行失败")

        self._append_exec_log("success" if success else "error", state.summary)
        if state.output_path:
            self._append_exec_log("info", f"输出文件：{state.output_path}")
        if state.report_paths:
            self._append_exec_log("info", f"报告文件：{', '.join(state.report_paths)}")
        if state.error_text:
            self._append_exec_log("error", state.error_text)
        self._execute_btn.setText("开始执行")
        self._execute_btn.setIcon(get_icon("play", 16, "#FFFFFF"))
        self._execute_btn.setEnabled(True)
        apply_button_variant(self._execute_btn, "primary")
        self.summary_changed.emit()

    def finish_execution(self) -> None:
        self._execution_running = False
        if self._last_result_status == "running":
            self._last_result_status = "idle"
        self._emit_summary_changed()

    def reset_execution_feedback(self) -> None:
        self._known_execution_modules.clear()
        self._exec_bar.setValue(0)
        self._exec_bar.setVisible(False)
        self._exec_status_label.setText("等待开始...")
        self._exec_log.clear()
        self._exec_error_count = 0
        self._last_result_status = "idle"
        self._execution_running = False
        self._execute_btn.setText("开始执行")
        self._execute_btn.setIcon(get_icon("play", 16, "#FFFFFF"))
        apply_button_variant(self._execute_btn, "primary")
        self._emit_summary_changed()

    def enabled_features(self) -> list[str]:
        return [feature_id for feature_id, row in self._feature_rows.items() if row.is_checked()]

    def current_scene_id(self) -> str:
        return self._current_scene.scene_id

    def current_scene(self) -> SceneWorkspace:
        return self._current_scene

    def current_template_id(self) -> str:
        template_id = str(self._template_combo.currentData() or "").strip()
        if template_id:
            return template_id
        return str(self._current_scene.template_id or "").strip()

    def current_strategy(self) -> str:
        return "rebuild" if self._strategy_rebuild.isChecked() else "preserve"

    def runtime_template_overrides(self) -> dict[str, object]:
        selected_index = self._current_page_start_index()
        if selected_index < 0 or not self._structure_items:
            return {}
        return {
            "header_footer.suppress_header_footer_selectors": suppression_selectors_before(
                self._structure_items,
                selected_index,
            )
        }

    def navigation_snapshot(self) -> dict[str, str]:
        return build_navigation_snapshot(
            document_path=self.document_path(),
            strategy_name=self._active_template_label(),
            enabled_count=len(self.enabled_features()),
            execution_running=self._execution_running,
            last_result_status=self._last_result_status,
        )

    def feature_navigation_snapshot(self, feature_id: str) -> dict[str, str]:
        return build_feature_navigation_snapshot(self._resolve_feature_id(feature_id))

    # ═══════════════════════════════════════════════════════════════════════
    #  Internals
    # ═══════════════════════════════════════════════════════════════════════

    def _ensure_combo_value(self, text: str) -> None:
        target = str(text or "").strip()
        if not target:
            return
        for index in range(self._template_combo.count()):
            if self._template_combo.itemText(index).strip() == target:
                self._template_combo.setCurrentIndex(index)
                return
        self._template_combo.addItem(target, self.current_template_id() or target)
        self._template_combo.setCurrentIndex(self._template_combo.count() - 1)

    def _find_scene_index(self, scene_id: str) -> int:
        target = str(scene_id or "").strip()
        if not target:
            return -1
        for index in range(self._scene_combo.count()):
            if str(self._scene_combo.itemData(index) or "").strip() == target:
                return index
        return -1

    def _on_template_changed(self, _index: int) -> None:
        template_id = str(self._template_combo.currentData() or "").strip()
        if template_id:
            self._current_scene.template_id = template_id
        self._emit_summary_changed()
        if not self._scene_syncing:
            self._emit_binding_changed()

    def _emit_binding_changed(self) -> None:
        if self._binding_signal_blocked:
            return
        self.binding_changed.emit(self._current_scene, self.current_template_id())

    def _refresh_structure_preview(self, file_path: str) -> None:
        cleaned = str(file_path or "").strip()
        if not cleaned:
            self._clear_structure_preview()
            return

        path = Path(cleaned)
        if not path.exists() or path.suffix.lower() != ".docx":
            self._set_structure_items([], status="当前文档暂时无法识别结构")
            return

        try:
            items = analyze_document_structure(path)
        except Exception as exc:
            self._set_structure_items([], status=f"结构识别失败：{exc}")
            return

        status = f"已识别 {len(items)} 个内容块，可按需调整页码起点" if items else "未识别到可选内容块"
        self._set_structure_items(items, status=status)

    def _clear_structure_preview(self) -> None:
        self._set_structure_items([], status="选择文档后可确认页码起点")

    def _set_structure_items(self, items: list[StructurePreviewItem], *, status: str) -> None:
        self._structure_items = list(items)
        was_blocked = self._page_start_combo.blockSignals(True)
        try:
            self._page_start_combo.clear()
            self._page_start_combo.addItem("自动判断", -1)
            for index, item in enumerate(self._structure_items):
                self._page_start_combo.addItem(item.display_text, index)
        finally:
            self._page_start_combo.blockSignals(was_blocked)
        self._structure_status_label.setText(status)
        self._update_summary_label()

    def _update_structure_status(self) -> None:
        selected_index = self._current_page_start_index()
        if selected_index < 0:
            if self._structure_items:
                self._structure_status_label.setText(
                    f"已识别 {len(self._structure_items)} 个内容块，可按需调整页码起点"
                )
            else:
                self._structure_status_label.setText("选择文档后可确认页码起点")
            return

        if 0 <= selected_index < len(self._structure_items):
            item = self._structure_items[selected_index]
            hidden_count = len(suppression_selectors_before(self._structure_items, selected_index))
            self._structure_status_label.setText(
                f"页眉页码将从“{item.display_text}”开始，之前 {hidden_count} 个内容块留空"
            )

    def _page_start_summary_text(self) -> str:
        selected_index = self._current_page_start_index()
        if selected_index < 0:
            return "页码自动"
        if 0 <= selected_index < len(self._structure_items):
            return f"页码从{self._structure_items[selected_index].label}"
        return "页码自动"

    def _current_page_start_index(self) -> int:
        data = self._page_start_combo.currentData()
        try:
            return int(data)
        except (TypeError, ValueError):
            return -1

    def _active_template_label(self) -> str:
        label = self._template_combo.currentText().strip()
        if not label or label == "默认格式":
            return "默认流程"
        return label

    def _resolve_feature_id(self, feature_id: str) -> str:
        return self.FEATURE_ID_ALIASES.get(feature_id, feature_id)

    def _update_status(self, text: str) -> None:
        """Update the exec status label text."""
        self._exec_status_label.setText(str(text or "").strip())

    def _emit_summary_changed(self) -> None:
        if self._execution_running:
            self._update_status(build_running_status(self.document_path()))
            self.summary_changed.emit()
            return
        # Not running — build a ready status but only write it to the log label
        status = build_ready_status(
            document_path=self.document_path(),
            strategy_name=self._active_template_label(),
            strict_mode=self.current_strategy() == "rebuild",
        )
        self._exec_status_label.setText(status.text)
        t = get_theme()
        color = t.success if status.tone == "success" else t.text_hint
        self._exec_status_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {color}; background: transparent;"
        )
        self.summary_changed.emit()

    def _apply_zone_styles(self) -> None:
        t = get_theme()
        from src.shared.ui.selection_control_style import build_checkbox_stylesheet
        cb_qss = build_checkbox_stylesheet(t)
        for cb in self._zone_checks.values():
            cb.setStyleSheet(cb_qss)

    def _apply_theme(self) -> None:
        t = get_theme()
        from src.shared.ui.input_style import build_text_input_stylesheet
        from src.shared.ui.selection_control_style import build_checkbox_stylesheet
        from src.shared.ui.sizing import apply_size_class

        btn_qss = build_button_stylesheet(t)
        self.setStyleSheet(btn_qss)

        # Summary label (inline, small gray)
        if hasattr(self, "_summary_label"):
            self._summary_label.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_hint}; background: transparent;"
            )

        # Advanced header icon + title (primary color, like scene card)
        if hasattr(self, "_adv_header_icon"):
            self._adv_header_icon.setPixmap(
                get_icon("puzzle", 18, t.primary).pixmap(18, 18)
            )
        if hasattr(self, "_adv_header_title"):
            self._adv_header_title.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.primary}; background: transparent;"
            )

        # Advanced toggle chevron
        if hasattr(self, "_adv_chevron"):
            self._update_chevron()

        # Section titles
        for title_label in self.findChildren(QLabel, "wb_v2_section_title"):
            title_label.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; color: {t.text_primary};"
            )

        # Separator
        for sep in self.findChildren(QFrame, "wb_v2_adv_sep"):
            sep.setStyleSheet(f"background: {t.border_light}; max-height: 1px;")

        # Scene/template card title (primary color)
        if hasattr(self, "_scene_card_title"):
            self._scene_card_title.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.primary}; background: transparent;"
            )
        if hasattr(self, "_scene_card_icon"):
            self._scene_card_icon.setPixmap(
                get_icon("boxes", 18, t.primary).pixmap(18, 18)
            )

        # Scene/template row labels
        for lbl in self.findChildren(QLabel, "scene_tpl_label"):
            lbl.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.text_secondary}; background: transparent;"
            )

        # Scene/template row icons (match sidebar)
        if hasattr(self, "_scene_icon_label"):
            self._scene_icon_label.setPixmap(
                get_icon("mountain-snow", 16, t.text_hint).pixmap(16, 16)
            )
        if hasattr(self, "_tpl_icon_label"):
            self._tpl_icon_label.setPixmap(
                get_icon("scroll-text", 16, t.text_hint).pixmap(16, 16)
            )

        # Scene/template vertical dashed divider
        if hasattr(self, "_scene_tpl_divider"):
            self._scene_tpl_divider.set_color(t.text_hint)

        # Dashed separators — use text_hint for clear visibility
        dashed_color = t.text_hint
        for w in (getattr(self, '_sep_strategy_zones', None),
                  getattr(self, '_sep_zones_features', None)):
            if w:
                w.set_color(dashed_color)
        if hasattr(self, "_features_vdiv"):
            self._features_vdiv.set_color(dashed_color)

        # Zone buttons
        if hasattr(self, "_zones_select_all_btn"):
            flat_btn_qss = f"font-size: {t.font_size_sm}px; color: {t.primary}; border: none; padding: 2px 6px;"
            self._zones_select_all_btn.setStyleSheet(flat_btn_qss)
            self._zones_clear_btn.setStyleSheet(flat_btn_qss)

        # Zone checkboxes
        if hasattr(self, "_zone_checks"):
            self._apply_zone_styles()

        # Output card header (same style as scene card)
        if hasattr(self, "_output_card_title"):
            self._output_card_title.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.primary}; background: transparent;"
            )
        if hasattr(self, "_output_card_icon"):
            self._output_card_icon.setPixmap(
                get_icon("square-arrow-out-up-right", 18, t.primary).pixmap(18, 18)
            )

        # Output browse button (styled like scene combo area)
        if hasattr(self, "_output_browse_btn"):
            self._output_browse_btn.setStyleSheet(
                f"QPushButton {{ font-size: {t.font_size_md}px; color: {t.text_secondary}; "
                f"border: 1px solid {t.border}; border-radius: {t.radius_sm}px; "
                f"padding: 6px 12px; background: {t.bg_card}; text-align: left; }}"
                f"QPushButton:hover {{ border-color: {t.primary}; color: {t.primary}; }}"
            )

        # Execute card header
        if hasattr(self, "_exec_card_icon"):
            self._exec_card_icon.setPixmap(
                get_icon("terminal", 18, t.primary).pixmap(18, 18)
            )
        if hasattr(self, "_exec_card_title"):
            self._exec_card_title.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.primary}; background: transparent;"
            )

        # Execute button
        if hasattr(self, "_execute_btn"):
            apply_button_variant(self._execute_btn, "primary")

        # Exec status area (right of button)
        if hasattr(self, "_exec_status_area"):
            self._exec_status_area.setStyleSheet(
                f"""QWidget#wb_v2_exec_status_area {{
                    background: {t.bg_hover};
                    border-radius: {t.radius_sm}px;
                }}"""
            )
        if hasattr(self, "_exec_status_label"):
            self._exec_status_label.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_hint}; background: transparent;"
            )

        # Progress bar
        if hasattr(self, "_exec_bar"):
            self._exec_bar.setStyleSheet(
                f"""QProgressBar#wb_v2_exec_bar {{
                    border: none; background: {t.border_light};
                    border-radius: 2px;
                }}
                QProgressBar#wb_v2_exec_bar::chunk {{
                    background: {t.primary}; border-radius: 2px;
                }}"""
            )

        # Log title
        if hasattr(self, "_log_title"):
            self._log_title.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.text_primary}; background: transparent;"
            )

        # Log area (light theme)
        if hasattr(self, "_exec_log"):
            self._exec_log.setStyleSheet(
                f"""QTextEdit#wb_v2_log_terminal {{
                    background: {t.bg_hover};
                    color: {t.text_secondary};
                    font-size: {t.font_size_sm}px;
                    border-radius: {t.radius_sm}px;
                    padding: 10px;
                    border: 1px solid {t.border_light};
                }}"""
            )

        self._emit_summary_changed()


# ═══════════════════════════════════════════════════════════════════════════
#  Flow layout helper for zone checkboxes
# ═══════════════════════════════════════════════════════════════════════════

class _FlowLayout(QHBoxLayout):
    """Simplified horizontal flow that wraps (using QHBoxLayout as base,
    actual wrapping delegated to the container's word-wrap behavior).
    For a true flow, we just use a grid-like horizontal layout here."""

    def __init__(self, parent=None, h_spacing: int = 8, v_spacing: int = 4):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(h_spacing)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
