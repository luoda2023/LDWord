from __future__ import annotations

from pathlib import Path

import html as _html

from src.qt_api import (
    QButtonGroup,
    QDesktopServices,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSize,
    QSizePolicy,
    Qt,
    QTextEdit,
    QUrl,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.qt_api import QIcon, QPropertyAnimation, QProgressBar
from src.shared.ui import (
    EvidenceActionBar,
    EvidenceLineItem,
    EvidenceLineList,
    IssueDetailSection,
    ThemedRadioButton,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later
from src.shared.ui.style_difference_summary_slot import StyleDifferenceSummarySlot
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.config.builtin_templates import create_builtin_template
from src.ui.adapters.workbench_execution_adapter import (
    ISSUE_TERMINAL_STATUS_VALUES,
    WorkbenchIssueEvidenceLineProjection,
    WorkbenchIssueItem,
    workbench_issue_display_text,
    workbench_issue_evidence_actions,
    workbench_issue_evidence_body_text,
    workbench_issue_evidence_lines,
    control_contract_issue_items,
    coverage_boundary_issue_items,
    material_asset_comparison_issue_items,
    material_readiness_issue_groups,
    material_readiness_issue_items,
    object_preflight_issue_items,
    parameter_ownership_issue_items,
    sample_fixture_issue_items,
    summarize_workbench_issue_queue,
    update_workbench_issue_status,
    workbench_artifact_display_items,
    workbench_issue_action_group,
    workbench_issue_action_target,
    workbench_issue_action_visual,
    workbench_issue_action_visual_for_item,
    workbench_issue_source_note_label,
)
from src.ui.adapters.workbench_issue_navigation import (
    workbench_issue_parameter_navigation_target,
)
from src.ui.adapters.field_display_names import field_display_context, field_display_name
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
from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace
from src.ui.panels.style_object_projection_builders import (
    build_execution_prereview_style_projection,
)
from .scene_presets import (
    LEGACY_FEATURE_GROUP_MAP,
    SCENE_META_MAP,
    UI_CAPABILITY_GROUPS,
    UI_GROUP_MAP,
    get_group_enabled,
    set_group_enabled,
)


def _open_local_path(path: Path) -> bool:
    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))))


class QuickExecutionDetail(QWidget):
    """Workbench V2 quick-execution detail pane (redesigned)."""

    feature_toggled = Signal(str, bool)
    feature_config_requested = Signal(str)
    material_repair_requested = Signal(str, str)
    issue_repair_requested = Signal(str, str)
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
        self._execution_running = False
        self._last_result_status = "idle"
        self._known_execution_modules: list[str] = []
        self._binding_signal_blocked = False
        self._scene_syncing = False
        self._scene_descriptors = list_scene_descriptors()
        self._current_template = None
        initial_scene = default_scene_descriptor()
        if initial_scene is None and self._scene_descriptors:
            initial_scene = self._scene_descriptors[0]
        if initial_scene is not None:
            self._current_scene = load_scene_from_library(initial_scene.config_id)
        else:
            self._current_scene = SceneWorkspace(scene_id="custom", template_id="default")
        self._material_context = MaterialExecutionContext()
        self._material_readiness_issues = material_readiness_issue_groups(
            self._current_scene,
            self._material_context,
        )
        self._workbench_issue_items: list[WorkbenchIssueItem] = []
        self._scene_summary_cache_key = None
        self._scene_summary_cache: dict[str, str] = {}
        self._scene_issue_cache_key = None
        self._scene_issue_cache: tuple[WorkbenchIssueItem, ...] = ()
        self._issue_queue_source = "preflight_config"
        self._issue_queue_filter_category = ""
        self._issue_queue_filter_action_group = ""
        self._active_issue_id = ""
        self._issue_panel_expanded = True
        self._issue_navigation_context: dict[str, str] = {}
        self._open_local_path_handler = _open_local_path

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(get_theme().template_detail_section_gap)
        self.setMinimumWidth(320)
        # Prevent vertical compression — scroll area must scroll, not squish
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # ── 1. Input file ──
        self._drop_area = QuickExecutionDropArea(self)
        self._drop_area.file_selected.connect(self._on_file_selected)
        self._drop_area.file_cleared.connect(self._on_file_cleared)
        self._layout.addWidget(self._drop_area)

        # ── 2. Scene & Template ──
        self._build_scene_section()
        self._layout.addWidget(self._scene_card)

        # ── 3. Output ──
        self._output_card = Card(parent=self)
        self._build_output_section()
        self._layout.addWidget(self._output_card)

        # ── 4. Execute ──
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
        # ── Single row: 场景 [combo] | 模板 [combo] ──
        row = QWidget(self)
        row.setObjectName("wb_execution_prereview_selector_row")
        self._scene_template_selector_row = row
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

        row_layout.addSpacing(10)

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

        self._style_difference_slot = StyleDifferenceSummarySlot(
            self,
            object_name_prefix="wb_style_difference",
        )
        self._style_difference_slot.setProperty(
            "style_difference_review_mode",
            "execution_prereview",
        )
        self._style_difference_slot.setVisible(False)
        self._scene_card_is_full = False
        self._scene_card = Card(parent=self)
        self._scene_card.set_header("场景与模板", icon_name="boxes")
        self._scene_card.add_widget(self._scene_template_selector_row)
        self._scene_card.add_widget(self._style_difference_slot)

    def _build_output_section(self) -> None:
        """Build the output directory section – matches scene card style."""
        self._output_card.set_header("输出目录", icon_name="square-arrow-out-up-right")

        # ── Row: ○ 默认  ○ 自定义  [browse btn] ──
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        # Radio buttons
        self._output_mode_group = QButtonGroup(self)
        self._output_mode_group.setExclusive(True)
        self._output_default_radio = ThemedRadioButton("默认", row)
        self._output_custom_radio = ThemedRadioButton("自定义", row)
        self._output_mode_group.addButton(self._output_default_radio, 0)
        self._output_mode_group.addButton(self._output_custom_radio, 1)
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
        self._output_browse_btn.setIcon(get_icon("folder-open", 16, get_theme().icon_primary))
        # Auto-switch to custom mode if not already
        if not self._output_custom_radio.isChecked():
            self._output_custom_radio.setChecked(True)
        self._emit_summary_changed()

    def custom_output_dir(self) -> str:
        """Return custom output directory, or empty for default."""
        return self._custom_output_dir

    def _build_execute_area(self) -> None:
        self._execution_card.set_header("执行输出", icon_name="terminal")

        # ── Row: [Button LEFT] + [Status panel RIGHT, fixed height] ──
        exec_row = QWidget(self)
        exec_row_layout = QHBoxLayout(exec_row)
        exec_row_layout.setContentsMargins(0, 0, 0, 0)
        exec_row_layout.setSpacing(0)

        # Left: Execute button
        self._execute_btn = QPushButton("生成文档", self)
        self._execute_btn.setObjectName("wb_v2_execute_btn")
        exec_height = get_theme().control_height_lg
        self._execute_btn.setMinimumHeight(exec_height)
        self._execute_btn.setMaximumHeight(exec_height)
        self._execute_btn.setCursor(Qt.PointingHandCursor)
        self._execute_btn.setIcon(get_icon("play", 16, get_theme().text_on_primary))
        apply_button_variant(self._execute_btn, "primary")
        exec_height = max(
            exec_height,
            self._execute_btn.minimumSizeHint().height(),
            self._execute_btn.sizeHint().height(),
        )
        self._execute_btn.setMinimumHeight(exec_height)
        self._execute_btn.setMaximumHeight(exec_height)
        self._execute_btn.clicked.connect(self.execute_requested.emit)
        exec_row_layout.addWidget(self._execute_btn, 4)

        # Right: Compact status panel (fixed height = button height)
        self._exec_status_area = QWidget(exec_row)
        self._exec_status_area.setObjectName("wb_v2_exec_status_area")
        self._exec_status_area.setMinimumHeight(exec_height)
        self._exec_status_area.setMaximumHeight(exec_height)
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
        self._exec_bar.setMinimumHeight(4)
        self._exec_bar.setMaximumHeight(4)
        self._exec_bar.setVisible(False)
        status_layout.addWidget(self._exec_bar)

        exec_row_layout.addWidget(self._exec_status_area, 9)

        self._material_repair_btn = QPushButton("补资料", self)
        self._material_repair_btn.setObjectName("wb_v2_material_repair_btn")
        self._material_repair_btn.setMinimumHeight(exec_height)
        self._material_repair_btn.setMaximumHeight(exec_height)
        self._material_repair_btn.setCursor(Qt.PointingHandCursor)
        self._material_repair_btn.setToolTip("打开资料配置")
        self._material_repair_btn.setIcon(get_icon("pen-tool", 16, get_theme().text_primary))
        apply_button_variant(self._material_repair_btn, "secondary")
        self._material_repair_btn.clicked.connect(self._request_material_repair)
        self._material_repair_btn.setVisible(False)
        exec_row_layout.addWidget(self._material_repair_btn, 2)
        self._execution_card.add_widget(exec_row)

        self._issue_panel = QFrame(self)
        self._issue_panel.setObjectName("wb_v2_issue_panel")
        issue_panel_layout = QVBoxLayout(self._issue_panel)
        issue_panel_layout.setContentsMargins(10, 8, 10, 10)
        issue_panel_layout.setSpacing(8)

        issue_panel_header = QWidget(self._issue_panel)
        issue_panel_header_layout = QHBoxLayout(issue_panel_header)
        issue_panel_header_layout.setContentsMargins(0, 0, 0, 0)
        issue_panel_header_layout.setSpacing(8)
        self._issue_panel_title = QLabel("问题处理", issue_panel_header)
        self._issue_panel_title.setObjectName("wb_v2_issue_panel_title")
        issue_panel_header_layout.addWidget(self._issue_panel_title, 0)
        self._issue_panel_count = QLabel("", issue_panel_header)
        self._issue_panel_count.setObjectName("wb_v2_issue_panel_count")
        issue_panel_header_layout.addWidget(self._issue_panel_count, 1)
        self._issue_panel_toggle_btn = QPushButton("收起", issue_panel_header)
        self._issue_panel_toggle_btn.setObjectName("wb_v2_issue_panel_toggle")
        self._issue_panel_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._issue_panel_toggle_btn.clicked.connect(self._toggle_issue_panel)
        apply_button_variant(self._issue_panel_toggle_btn, "secondary")
        issue_panel_header_layout.addWidget(self._issue_panel_toggle_btn, 0)
        issue_panel_layout.addWidget(issue_panel_header)

        self._issue_panel_body = QWidget(self._issue_panel)
        issue_panel_body_layout = QVBoxLayout(self._issue_panel_body)
        issue_panel_body_layout.setContentsMargins(0, 0, 0, 0)
        issue_panel_body_layout.setSpacing(8)

        self._issue_filter_row = QWidget(self._issue_panel_body)
        self._issue_filter_row.setObjectName("wb_v2_issue_filter_row")
        issue_filter_layout = QHBoxLayout(self._issue_filter_row)
        issue_filter_layout.setContentsMargins(0, 0, 0, 0)
        issue_filter_layout.setSpacing(8)
        self._issue_filter_label = QLabel("问题筛选", self._issue_filter_row)
        self._issue_filter_label.setObjectName("wb_v2_issue_filter_label")
        issue_filter_layout.addWidget(self._issue_filter_label, 0)
        self._issue_filter_combo = StyledComboBox(self._issue_filter_row)
        self._issue_filter_combo.setObjectName("wb_v2_issue_filter_combo")
        self._issue_filter_combo.setToolTip("按类别筛选运行前问题")
        self._issue_filter_combo.currentIndexChanged.connect(self._on_issue_filter_changed)
        issue_filter_layout.addWidget(self._issue_filter_combo, 1)
        self._issue_action_group_combo = StyledComboBox(self._issue_filter_row)
        self._issue_action_group_combo.setObjectName("wb_v2_issue_action_group_combo")
        self._issue_action_group_combo.setToolTip("按处理动作筛选运行前问题")
        self._issue_action_group_combo.currentIndexChanged.connect(
            self._on_issue_action_group_filter_changed
        )
        issue_filter_layout.addWidget(self._issue_action_group_combo, 1)
        self._issue_action_btn = QPushButton("处理", self._issue_filter_row)
        self._issue_action_btn.setObjectName("wb_v2_issue_action_btn")
        self._issue_action_btn.setCursor(Qt.PointingHandCursor)
        self._issue_action_btn.setIcon(
            get_icon("square-arrow-out-up-right", 16, get_theme().text_primary)
        )
        self._issue_action_btn.clicked.connect(self._request_current_issue_action)
        apply_button_variant(self._issue_action_btn, "secondary")
        self._issue_action_btn.setVisible(False)
        issue_filter_layout.addWidget(self._issue_action_btn, 0)
        self._issue_resolve_btn = QPushButton("已处理", self._issue_filter_row)
        self._issue_resolve_btn.setObjectName("wb_v2_issue_resolve_btn")
        self._issue_resolve_btn.setCursor(Qt.PointingHandCursor)
        self._issue_resolve_btn.setIcon(
            get_icon("circle-check", 16, get_theme().text_primary)
        )
        self._issue_resolve_btn.clicked.connect(self._mark_current_issue_resolved)
        apply_button_variant(self._issue_resolve_btn, "secondary")
        self._issue_resolve_btn.setVisible(False)
        issue_filter_layout.addWidget(self._issue_resolve_btn, 0)
        self._issue_ignore_btn = QPushButton("忽略", self._issue_filter_row)
        self._issue_ignore_btn.setObjectName("wb_v2_issue_ignore_btn")
        self._issue_ignore_btn.setCursor(Qt.PointingHandCursor)
        self._issue_ignore_btn.setIcon(
            get_icon("circle-x", 16, get_theme().text_primary)
        )
        self._issue_ignore_btn.clicked.connect(self._mark_current_issue_ignored)
        apply_button_variant(self._issue_ignore_btn, "secondary")
        self._issue_ignore_btn.setVisible(False)
        issue_filter_layout.addWidget(self._issue_ignore_btn, 0)
        self._issue_filter_row.setVisible(False)
        issue_panel_body_layout.addWidget(self._issue_filter_row)

        self._issue_list = QListWidget(self._issue_panel_body)
        self._issue_list.setObjectName("wb_v2_issue_list")
        self._issue_list.setMinimumHeight(74)
        self._issue_list.setMaximumHeight(142)
        self._issue_list.currentItemChanged.connect(
            lambda *_args: self._sync_selected_issue_from_list()
        )
        issue_panel_body_layout.addWidget(self._issue_list)

        self._issue_detail_panel = QFrame(self._issue_panel_body)
        self._issue_detail_panel.setObjectName("wb_v2_issue_detail_panel")
        issue_detail_layout = QVBoxLayout(self._issue_detail_panel)
        issue_detail_layout.setContentsMargins(10, 8, 10, 8)
        issue_detail_layout.setSpacing(6)
        self._issue_detail_title = QLabel("", self._issue_detail_panel)
        self._issue_detail_title.setObjectName("wb_v2_issue_detail_title")
        self._issue_detail_title.setWordWrap(True)
        issue_detail_layout.addWidget(self._issue_detail_title)
        self._issue_detail_meta = QLabel("", self._issue_detail_panel)
        self._issue_detail_meta.setObjectName("wb_v2_issue_detail_meta")
        self._issue_detail_meta.setWordWrap(True)
        issue_detail_layout.addWidget(self._issue_detail_meta)
        self._issue_detail_impact_section = IssueDetailSection(
            "影响",
            tone="warning",
            parent=self._issue_detail_panel,
        )
        self._issue_detail_impact_title = (
            self._issue_detail_impact_section.title_label
        )
        self._issue_detail_impact_title.setObjectName(
            "wb_v2_issue_detail_impact_title"
        )
        self._issue_detail_impact = self._issue_detail_impact_section.body_label
        self._issue_detail_impact.setObjectName("wb_v2_issue_detail_impact")
        issue_detail_layout.addWidget(self._issue_detail_impact_section)

        self._issue_detail_action_section = IssueDetailSection(
            "动作",
            tone="primary",
            parent=self._issue_detail_panel,
        )
        self._issue_detail_action_title = (
            self._issue_detail_action_section.title_label
        )
        self._issue_detail_action_title.setObjectName(
            "wb_v2_issue_detail_action_title"
        )
        self._issue_detail_advice = self._issue_detail_action_section.body_label
        self._issue_detail_advice.setObjectName("wb_v2_issue_detail_advice")
        issue_detail_layout.addWidget(self._issue_detail_action_section)

        self._issue_detail_evidence_section = IssueDetailSection(
            "证据",
            tone="neutral",
            parent=self._issue_detail_panel,
        )
        self._issue_detail_evidence_title = (
            self._issue_detail_evidence_section.title_label
        )
        self._issue_detail_evidence_title.setObjectName(
            "wb_v2_issue_detail_evidence_title"
        )
        self._issue_detail_body = self._issue_detail_evidence_section.body_label
        self._issue_detail_body.setObjectName("wb_v2_issue_detail_body")
        self._issue_detail_body.setVisible(False)
        issue_detail_layout.addWidget(self._issue_detail_evidence_section)
        self._issue_evidence_line_list = EvidenceLineList(parent=self._issue_detail_panel)
        self._issue_evidence_line_list.action_requested.connect(
            self._request_issue_evidence_action
        )
        issue_detail_layout.addWidget(self._issue_evidence_line_list)
        self._issue_evidence_action_bar = EvidenceActionBar(parent=self._issue_detail_panel)
        self._issue_evidence_action_bar.setObjectName("wb_v2_issue_evidence_action_bar")
        self._issue_evidence_action_bar.action_requested.connect(
            self._request_issue_evidence_action
        )
        self._issue_evidence_action_row = self._issue_evidence_action_bar
        self._issue_evidence_parameter_btn = None
        self._issue_evidence_file_btn = None
        issue_detail_layout.addWidget(self._issue_evidence_action_bar)
        issue_detail_actions = QWidget(self._issue_detail_panel)
        issue_detail_actions_layout = QHBoxLayout(issue_detail_actions)
        issue_detail_actions_layout.setContentsMargins(0, 0, 0, 0)
        issue_detail_actions_layout.setSpacing(8)
        issue_detail_actions_layout.addStretch(1)
        self._issue_recheck_btn = QPushButton("复检", issue_detail_actions)
        self._issue_recheck_btn.setObjectName("wb_v2_issue_recheck_btn")
        self._issue_recheck_btn.setCursor(Qt.PointingHandCursor)
        self._issue_recheck_btn.clicked.connect(self._recheck_current_issue)
        apply_button_variant(self._issue_recheck_btn, "secondary")
        issue_detail_actions_layout.addWidget(self._issue_recheck_btn, 0)
        issue_detail_layout.addWidget(issue_detail_actions)
        self._issue_detail_panel.setVisible(False)
        issue_panel_body_layout.addWidget(self._issue_detail_panel)

        self._issue_queue_label = QLabel("", self._issue_panel_body)
        self._issue_queue_label.setObjectName("wb_v2_issue_queue")
        self._issue_queue_label.setWordWrap(True)
        self._issue_queue_label.setVisible(False)
        issue_panel_body_layout.addWidget(self._issue_queue_label)

        issue_panel_layout.addWidget(self._issue_panel_body)
        self._issue_panel.setVisible(False)
        self._execution_card.add_widget(self._issue_panel)


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
            self._ensure_full_scene_card()
            self._emit_summary_changed()
            self._emit_binding_changed()

    def _apply_scene(self, scene: SceneWorkspace) -> None:
        """Apply a scene and refresh the execution surface."""
        self._current_scene = scene
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
                fallback_label = self._template_label_for_scene(scene, template_id)
                entry_label = str(getattr(entry, "name", "") or "").strip() if entry is not None else ""
                label = entry_label if entry_label and entry_label != template_id else fallback_label
                self._template_combo.addItem(label, template_id)
            for index in range(self._template_combo.count()):
                if self._template_combo.itemData(index) == scene.template_id:
                    self._template_combo.setCurrentIndex(index)
                    break
            self._template_combo.blockSignals(was_blocked)

            self._sync_style_prereview_state()
        finally:
            self._scene_syncing = False

    def _scene_static_cache_key(self, *function_markers) -> tuple:
        scene = self._current_scene
        input_profile = getattr(scene, "input_source_profile", None)
        compliance = getattr(scene, "compliance_profile", None)
        preflight = getattr(compliance, "object_preflight", None)
        delivery_presets = tuple(
            (
                str(getattr(preset, "preset_id", "") or ""),
                str(getattr(preset, "target_template_id", "") or ""),
            )
            for preset in list(getattr(scene, "delivery_presets", []) or [])
        )
        return (
            id(scene),
            scene.__class__,
            str(getattr(scene, "scene_id", "") or ""),
            str(getattr(scene, "category", "") or ""),
            str(getattr(input_profile, "material_schema_id", "") or ""),
            tuple(getattr(input_profile, "accepted_formats", ()) or ()),
            str(getattr(compliance, "profile_id", "") or ""),
            bool(getattr(preflight, "enabled", False)),
            str(getattr(preflight, "preservation_mode", "") or ""),
            str(getattr(scene, "default_delivery_preset_id", "") or ""),
            delivery_presets,
            tuple(id(marker) for marker in function_markers),
        )

    def _sync_style_prereview_state(self) -> None:
        if not hasattr(self, "_scene_card"):
            return
        if not getattr(self, "_scene_card_is_full", False):
            if self._scene_has_style_prereview_difference():
                self._ensure_full_scene_card()
            return
        style_projection = build_execution_prereview_style_projection(
            self._current_scene,
            template=getattr(self, "_current_template", None),
            template_label=self._active_template_label(),
        )
        self._scene_card.apply_style_object_projection(style_projection)
        self._style_difference_slot.setVisible(style_projection.difference is not None)
        refresh_layout_chain(self._style_difference_slot)
        refresh_layout_chain_later(self._scene_card)

    def _scene_has_style_prereview_difference(self) -> bool:
        section_styles = getattr(self._current_scene, "section_styles", {}) or {}
        return bool(section_styles)

    def _ensure_full_scene_card(self) -> None:
        if getattr(self, "_scene_card_is_full", False):
            return
        from src.shared.ui import StyleManagementBlock
        from src.ui.panels.style_object_projection_builders import (
            build_execution_prereview_style_projection,
        )

        globals()["build_execution_prereview_style_projection"] = (
            build_execution_prereview_style_projection
        )
        old_card = self._scene_card
        index = self._layout.indexOf(old_card)
        self._scene_template_selector_row.setParent(self)
        self._style_difference_slot.setParent(self)
        full_card = StyleManagementBlock(
            self,
            title="场景与模板",
            icon_name="boxes",
            object_name_prefix="wb_execution_prereview",
            mode="execution_prereview",
            source_slot=self._scene_template_selector_row,
            scope_slot=self._scene_template_selector_row,
            difference_slot=self._style_difference_slot,
            compact_header=True,
        )
        self._scene_card = full_card
        self._scene_card_is_full = True
        if index >= 0:
            self._layout.insertWidget(index, full_card)
            self._layout.removeWidget(old_card)
        old_card.hide()
        old_card.deleteLater()
        self._sync_style_prereview_state()

    # ═══════════════════════════════════════════════════════════════════════
    #  Event handlers
    # ═══════════════════════════════════════════════════════════════════════

    def _on_file_selected(self, file_path: str) -> None:
        if file_path:
            self.document_selected.emit(file_path)
        self._emit_summary_changed()

    def _on_file_cleared(self) -> None:
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
        self._emit_summary_changed()

    def set_scene_context(self, scene: SceneWorkspace) -> None:
        """Apply an externally selected scene to the full quick execution surface."""
        self._apply_scene(scene)

    def set_template_context(self, template) -> None:
        """Apply an externally selected template for style-source comparisons."""
        self._current_template = template
        self._sync_style_prereview_state()

    def set_strategy_context(
        self,
        *,
        template_name: str | None = None,
        template_id: str | None = None,
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
                self._ensure_combo_value(template_name, template_id=template_id)
            elif template_id:
                self._set_current_template_id(template_id)
            if strict_mode is not None:
                self._current_scene.strict_mode = bool(strict_mode)
        finally:
            self._binding_signal_blocked = False
            self._scene_syncing = False
        self._sync_style_prereview_state()
        self._emit_summary_changed()

    def set_execute_enabled(self, enabled: bool) -> None:
        self._execute_btn.setEnabled(bool(enabled))

    def set_object_preflight_confirmation(
        self,
        state: ExecutionResultState,
        *,
        blocked: bool = False,
    ) -> None:
        self._execution_running = False
        self._last_result_status = "failed" if blocked else "idle"
        self._exec_bar.setVisible(False)
        self._set_material_repair_visible(False)
        self._issue_queue_source = "object_preflight"
        self._workbench_issue_items = object_preflight_issue_items(state.object_preflight)
        self._set_issue_queue_visible(bool(self._workbench_issue_items), self._workbench_issue_items)
        self._exec_status_label.setText(
            "对象预检阻断执行" if blocked else "对象预检需确认"
        )
        level = "error" if blocked else "warning"
        if blocked:
            self._append_exec_log("error", "对象预检发现阻断风险，已停止执行。")
        else:
            self._append_exec_log("warning", "对象预检发现风险，再次点击将继续执行。")
        if state.object_preflight_summary:
            self._append_exec_log(level, state.object_preflight_summary)
        for line in list(state.object_preflight_details or []):
            self._append_exec_log(level, f"对象预检明细：{line}")

        if blocked:
            self._execute_btn.setText("重新检查")
            self._execute_btn.setIcon(QIcon())
            self._execute_btn.setEnabled(True)
            return

        self._execute_btn.setText("确认并继续")
        self._execute_btn.setIcon(get_icon("circle-check", 16, get_theme().text_on_primary))
        self._execute_btn.setEnabled(True)

    def set_feature_enabled(self, feature_id: str, enabled: bool) -> None:
        resolved = self._resolve_feature_id(feature_id)
        group = UI_GROUP_MAP.get(resolved)
        if group is None:
            raise KeyError(feature_id)
        set_group_enabled(self._current_scene, group, bool(enabled))
        self.feature_toggled.emit(resolved, bool(enabled))
        self._emit_summary_changed()
        if not self._scene_syncing:
            self.scene_config_changed.emit(self._current_scene)

    def is_feature_enabled(self, feature_id: str) -> bool:
        group = UI_GROUP_MAP.get(self._resolve_feature_id(feature_id))
        if group is None:
            return False
        return get_group_enabled(self._current_scene, group)

    def _append_exec_log(self, level: str, message: str) -> None:
        """Append a log line to the always-visible light-themed log."""
        safe = _html.escape(str(message))
        t = get_theme()
        colors = {
            "info": t.text_secondary,
            "warning": t.warning,
            "error": t.error,
            "critical": t.error_pressed,
            "success": t.success,
        }
        c = colors.get(level.lower(), t.text_primary)
        self._exec_log.append(f'<span style="color: {c};">{safe}</span>')
        if level.lower() in ("error", "critical"):
            self._exec_error_count += 1

    def set_execution_progress(self, state: ExecutionProgressState) -> None:
        self._execution_running = True
        self._last_result_status = "running"
        self._issue_queue_source = "running"
        self._workbench_issue_items = []
        self._exec_bar.setVisible(True)
        self._set_material_repair_visible(False)
        self._set_issue_queue_visible(False)
        self._execute_btn.setEnabled(False)
        self._execute_btn.setText("生成中...")
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
        self._issue_queue_source = "execution_result"
        self._workbench_issue_items = [
            item
            for item in list(getattr(state, "issue_items", []) or [])
            if isinstance(item, WorkbenchIssueItem)
        ]
        success = state.status in {"success", "partial_success"}
        self._exec_bar.setValue(100 if success else self._exec_bar.value())
        self._set_material_repair_visible(False)
        self._set_issue_queue_visible(bool(self._workbench_issue_items), self._workbench_issue_items)
        self._exec_status_label.setText("已完成" if success else "执行失败")

        self._append_exec_log("success" if success else "error", state.summary)
        for label, path in workbench_artifact_display_items(
            state.output_paths,
            delivery_preset_labels=True,
        ):
            self._append_exec_log("info", f"输出文件[{label}]：{path}")
        if state.output_path and not state.output_paths:
            self._append_exec_log("info", f"输出文件：{state.output_path}")
        for label, path in workbench_artifact_display_items(
            state.compare_paths,
            delivery_preset_labels=True,
        ):
            self._append_exec_log("info", f"对比稿[{label}]：{path}")
        for label, path in workbench_artifact_display_items(
            state.intermediate_paths,
            delivery_preset_labels=True,
        ):
            self._append_exec_log("info", f"中间产物[{label}]：{path}")
        for label, path in workbench_artifact_display_items(
            state.material_manifest_paths
        ):
            self._append_exec_log("info", f"资料清单[{label}]：{path}")
        for label, path in workbench_artifact_display_items(
            state.material_package_paths
        ):
            self._append_exec_log("info", f"资料包[{label}]：{path}")
        for item in list(state.artifact_items or []):
            if item.detail:
                self._append_exec_log("warning", f"产物预检[{item.label}]：{item.detail}")
        if state.report_paths:
            self._append_exec_log("info", f"报告文件：{', '.join(state.report_paths)}")
        if state.style_source_summary:
            self._append_exec_log("info", state.style_source_summary)
        if state.object_preflight_summary:
            level = "info"
            payload = getattr(state, "object_preflight", {}) or {}
            if isinstance(payload, dict):
                try:
                    if int(payload.get("findings_count") or 0) > 0 or int(
                        payload.get("module_skips_count") or 0
                    ) > 0:
                        level = "warning"
                except (TypeError, ValueError):
                    pass
            self._append_exec_log(level, state.object_preflight_summary)
            for line in list(state.object_preflight_details or []):
                self._append_exec_log(level, f"对象预检明细：{line}")
        if state.material_field_consistency_summary:
            level = "warning"
            payload = getattr(state, "material_field_consistency", {}) or {}
            if isinstance(payload, dict):
                try:
                    if int(payload.get("issue_count") or 0) <= 0:
                        level = "info"
                except (TypeError, ValueError):
                    pass
            self._append_exec_log(level, state.material_field_consistency_summary)
        if state.batch_isolation_summary:
            level = "warning"
            payload = getattr(state, "batch_isolation", {}) or {}
            if isinstance(payload, dict):
                try:
                    if int(payload.get("failed_count") or 0) <= 0:
                        level = "info"
                except (TypeError, ValueError):
                    pass
            self._append_exec_log(level, state.batch_isolation_summary)
            for line in list(state.batch_isolation_details or []):
                self._append_exec_log(level, f"Batch isolation detail: {line}")
        if state.error_text:
            self._append_exec_log("error", state.error_text)
        self._execute_btn.setText("生成文档")
        self._execute_btn.setIcon(get_icon("play", 16, get_theme().text_on_primary))
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
        self._execute_btn.setText("生成文档")
        self._execute_btn.setIcon(get_icon("play", 16, get_theme().text_on_primary))
        apply_button_variant(self._execute_btn, "primary")
        self._emit_summary_changed()

    def enabled_features(self) -> list[str]:
        enabled: list[str] = []
        for group in UI_CAPABILITY_GROUPS:
            if get_group_enabled(self._current_scene, group):
                enabled.append(group.group_id)
        return enabled

    def current_scene_id(self) -> str:
        return self._current_scene.scene_id

    def current_scene(self) -> SceneWorkspace:
        return self._current_scene

    def current_issue_items(self) -> list[WorkbenchIssueItem]:
        return list(self._workbench_issue_items)

    def current_filtered_issue_items(self) -> list[WorkbenchIssueItem]:
        summary = summarize_workbench_issue_queue(
            self._workbench_issue_items,
            category=self._issue_queue_filter_category,
            action_group=self._issue_queue_filter_action_group,
        )
        return _sort_issue_items_by_action(summary.visible_items)

    def current_issue_action_targets(self) -> list[tuple[str, str]]:
        targets: list[tuple[str, str]] = []
        for item in self.current_filtered_issue_items():
            target_type, target_key = workbench_issue_action_target(item)
            if target_type:
                targets.append((target_type, target_key))
        return targets

    def current_active_issue_id(self) -> str:
        return str(self._active_issue_id or "").strip()

    def current_issue_navigation_context(self) -> dict[str, str]:
        return dict(self._issue_navigation_context)

    def current_issue_evidence_actions(self) -> list[tuple[str, str, str]]:
        selected = self._selected_issue()
        if selected is None:
            return []
        return list(workbench_issue_evidence_actions(selected))

    def set_active_issue(self, issue_id: str) -> None:
        target = str(issue_id or "").strip()
        if not target:
            return
        for item in self._workbench_issue_items:
            if item.issue_id == target:
                self._active_issue_id = target
                self._issue_queue_filter_category = str(item.category or "").strip()
                self._issue_queue_filter_action_group = workbench_issue_action_group(item)
                self._issue_panel_expanded = True
                self._set_issue_queue_visible(
                    bool(self._workbench_issue_items),
                    self._workbench_issue_items,
                )
                return

    def set_issue_queue_filter(self, category: str) -> None:
        self._issue_queue_filter_category = str(category or "").strip()
        self._set_issue_queue_visible(
            bool(self._workbench_issue_items),
            self._workbench_issue_items,
        )

    def set_issue_queue_action_filter(self, action_group: str) -> None:
        self._issue_queue_filter_action_group = str(action_group or "").strip()
        self._set_issue_queue_visible(
            bool(self._workbench_issue_items),
            self._workbench_issue_items,
        )

    def _on_issue_filter_changed(self, _index: int) -> None:
        if not hasattr(self, "_issue_filter_combo"):
            return
        category = str(self._issue_filter_combo.currentData() or "").strip()
        if category == self._issue_queue_filter_category:
            return
        self._issue_queue_filter_category = category
        self._set_issue_queue_visible(
            bool(self._workbench_issue_items),
            self._workbench_issue_items,
        )

    def _request_current_issue_action(self) -> None:
        for item in self._current_action_issue_candidates():
            target_type, target_key = workbench_issue_action_target(item)
            if target_type:
                self._active_issue_id = item.issue_id
                self._issue_navigation_context = _issue_navigation_context(item)
                self.issue_repair_requested.emit(target_type, target_key)
                return

    def _issue_evidence_action_lines(
        self,
        issue: WorkbenchIssueItem | None,
    ) -> list[WorkbenchIssueEvidenceLineProjection]:
        if issue is None:
            return []
        return [
            line
            for line in workbench_issue_evidence_lines(issue)
            if line.action_type and line.action_value
        ]

    def _first_issue_evidence_action(
        self,
        issue: WorkbenchIssueItem | None,
        action_types: set[str],
    ) -> WorkbenchIssueEvidenceLineProjection | None:
        wanted = {str(action_type or "").strip() for action_type in action_types}
        for line in self._issue_evidence_action_lines(issue):
            if line.action_type in wanted:
                return line
        return None

    def _request_issue_evidence_parameter_action(self) -> None:
        selected = self._selected_issue()
        line = self._first_issue_evidence_action(selected, {"navigate_parameter"})
        if line is None:
            self._append_exec_log("warning", "当前问题没有可定位的参数。")
            return
        self._request_issue_evidence_action(line.action_type, line.action_value)

    def _request_issue_evidence_file_action(self) -> None:
        selected = self._selected_issue()
        line = self._first_issue_evidence_action(
            selected,
            {"open_evidence", "open_output", "open_replacement"},
        )
        if line is None:
            self._append_exec_log("warning", "当前问题没有可打开的证据文件。")
            return
        self._request_issue_evidence_action(line.action_type, line.action_value)

    def _request_issue_evidence_action(
        self,
        action_type: str,
        action_value: str,
    ) -> None:
        selected = self._selected_issue()
        action = str(action_type or "").strip()
        value = str(action_value or "").strip()
        if not action or not value:
            return
        if action == "navigate_parameter":
            target_type, target_key = workbench_issue_parameter_navigation_target(
                selected,
                value,
            )
            if not target_type:
                self._append_exec_log("warning", "当前参数没有可定位的设置入口。")
                return
            if selected is not None:
                self._active_issue_id = selected.issue_id
                self._issue_navigation_context = _issue_navigation_context(selected)
            self.issue_repair_requested.emit(target_type, target_key)
            return
        if action in {"open_evidence", "open_output", "open_replacement"}:
            path = _local_path_from_issue_evidence_action_value(value)
            if path is None:
                self._append_exec_log("warning", "当前证据没有可打开的文件路径。")
                return
            if not path.exists():
                self._append_exec_log("warning", f"证据文件不存在：{path}")
                return
            if self._open_local_path_handler(path):
                self._append_exec_log("info", f"已打开证据：{path}")
            else:
                self._append_exec_log("warning", f"无法打开证据：{path}")

    def set_issue_status(self, issue_id: str, status: str) -> None:
        self._workbench_issue_items = update_workbench_issue_status(
            self._workbench_issue_items,
            issue_id,
            status,
        )
        self._set_issue_queue_visible(
            bool(self._workbench_issue_items),
            self._workbench_issue_items,
        )

    def _current_status_issue(self) -> WorkbenchIssueItem | None:
        visible_items = self.current_filtered_issue_items()
        selected = self._selected_issue()
        if selected is not None:
            status = str(getattr(selected, "status", "") or "open").strip() or "open"
            if status not in ISSUE_TERMINAL_STATUS_VALUES:
                return selected
        for item in visible_items:
            status = str(getattr(item, "status", "") or "open").strip() or "open"
            if status not in ISSUE_TERMINAL_STATUS_VALUES:
                return item
        return visible_items[0] if visible_items else None

    def _mark_current_issue_resolved(self) -> None:
        issue = self._current_status_issue()
        if issue is not None:
            self.set_issue_status(issue.issue_id, "resolved")

    def _mark_current_issue_ignored(self) -> None:
        issue = self._current_status_issue()
        if issue is not None:
            self.set_issue_status(issue.issue_id, "ignored")

    def set_material_context(self, context: MaterialExecutionContext | None) -> None:
        self._material_context = (
            context.clone()
            if isinstance(context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        self._emit_summary_changed()

    def current_template_id(self) -> str:
        template_id = str(self._template_combo.currentData() or "").strip()
        if template_id:
            return template_id
        return str(self._current_scene.template_id or "").strip()

    def current_strategy(self) -> str:
        return "rebuild" if bool(getattr(self._current_scene, "strict_mode", False)) else "preserve"

    def runtime_template_overrides(self) -> dict[str, object]:
        return {}

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

    def _ensure_combo_value(self, text: str, *, template_id: str | None = None) -> None:
        target = str(text or "").strip()
        if not target:
            return
        target_id = str(template_id or "").strip()
        if target_id:
            for index in range(self._template_combo.count()):
                if str(self._template_combo.itemData(index) or "").strip() == target_id:
                    self._template_combo.setItemText(index, target)
                    self._template_combo.setCurrentIndex(index)
                    self._set_current_template_id(target_id)
                    return
        for index in range(self._template_combo.count()):
            if self._template_combo.itemText(index).strip() == target and not target_id:
                self._template_combo.setCurrentIndex(index)
                return
        self._template_combo.addItem(target, target_id or self.current_template_id() or target)
        self._template_combo.setCurrentIndex(self._template_combo.count() - 1)
        if target_id:
            self._set_current_template_id(target_id)

    def _set_current_template_id(self, template_id: str) -> None:
        target = str(template_id or "").strip()
        if not target:
            return
        self._current_scene.template_id = target
        if target not in self._current_scene.compatible_template_ids:
            self._current_scene.compatible_template_ids.insert(0, target)
        self._sync_style_prereview_state()

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
            self._set_current_template_id(template_id)
        if not self._scene_syncing:
            self._ensure_full_scene_card()
        self._emit_summary_changed()
        if not self._scene_syncing:
            self._emit_binding_changed()

    def _emit_binding_changed(self) -> None:
        if self._binding_signal_blocked:
            return
        self.binding_changed.emit(self._current_scene, self.current_template_id())

    def _active_template_label(self) -> str:
        label = self._template_combo.currentText().strip()
        template_id = str(self._template_combo.currentData() or "").strip()
        if template_id and (not label or label == template_id):
            entry = get_template_entry(template_id)
            entry_name = str(getattr(entry, "name", "") or "").strip()
            if entry_name:
                label = entry_name
            else:
                try:
                    builtin_template = create_builtin_template(template_id)
                except ValueError:
                    builtin_template = None
                builtin_name = str(getattr(builtin_template, "name", "") or "").strip()
                if builtin_name:
                    label = builtin_name
        if not label or label == "默认格式":
            return "默认流程"
        return label

    def _template_label_for_scene(self, scene: SceneWorkspace, template_id: str) -> str:
        target = str(template_id or "").strip()
        meta = SCENE_META_MAP.get(str(getattr(scene, "scene_id", "") or "").strip())
        if meta is not None:
            for template_meta in tuple(getattr(meta, "compatible_templates", ()) or ()):
                if str(getattr(template_meta, "template_id", "") or "").strip() == target:
                    label = str(getattr(template_meta, "name", "") or "").strip()
                    if label:
                        return label
        return target

    def _resolve_feature_id(self, feature_id: str) -> str:
        return self.FEATURE_ID_ALIASES.get(feature_id, feature_id)

    def _update_status(self, text: str) -> None:
        """Update the exec status label text."""
        self._exec_status_label.setText(str(text or "").strip())

    def _set_material_repair_visible(
        self,
        visible: bool,
        detail_lines: list[str] | None = None,
    ) -> None:
        if hasattr(self, "_material_repair_btn"):
            self._material_repair_btn.setVisible(bool(visible))
            lines = [
                line
                for line in (str(item or "").strip() for item in list(detail_lines or []))
                if line
            ]
            if visible and lines:
                self._material_repair_btn.setToolTip(
                    "资料缺口明细\n" + "\n".join(lines) + "\n点击打开资料配置"
                )
            else:
                self._material_repair_btn.setToolTip("打开资料配置")

    def _set_issue_queue_visible(
        self,
        visible: bool,
        items: list[WorkbenchIssueItem] | None = None,
    ) -> None:
        if not hasattr(self, "_issue_queue_label"):
            return
        queue_items = list(items or [])
        all_summary = summarize_workbench_issue_queue(queue_items)
        available_categories = {category for category, _count in all_summary.category_counts}
        available_action_groups = {
            action_group for action_group, _count in all_summary.action_group_counts
        }
        if self._issue_queue_filter_category and (
            self._issue_queue_filter_category not in available_categories
        ):
            self._issue_queue_filter_category = ""
        if self._issue_queue_filter_action_group and (
            self._issue_queue_filter_action_group not in available_action_groups
        ):
            self._issue_queue_filter_action_group = ""
        queue_summary = summarize_workbench_issue_queue(
            queue_items,
            category=self._issue_queue_filter_category,
            action_group=self._issue_queue_filter_action_group,
        )
        self._sync_issue_filter_control(all_summary, queue_summary)
        visible_items = _sort_issue_items_by_action(queue_summary.visible_items)
        show_panel = bool(visible and queue_summary.has_issues)
        if hasattr(self, "_issue_panel"):
            self._issue_panel.setVisible(show_panel)
        if hasattr(self, "_issue_panel_body"):
            self._issue_panel_body.setVisible(show_panel and self._issue_panel_expanded)
        if hasattr(self, "_issue_panel_toggle_btn"):
            self._issue_panel_toggle_btn.setText(
                "收起" if self._issue_panel_expanded else "展开"
            )
            self._issue_panel_toggle_btn.setVisible(show_panel)
        if hasattr(self, "_issue_panel_count"):
            if show_panel:
                self._issue_panel_count.setText(
                    _issue_panel_count_text(all_summary, queue_summary)
                )
            else:
                self._issue_panel_count.setText("")
        self._issue_queue_label.setVisible(show_panel and self._issue_panel_expanded)
        if not visible or not queue_summary.has_issues:
            self._issue_queue_label.setText("")
            self._issue_queue_label.setToolTip("")
            if hasattr(self, "_issue_filter_row"):
                self._issue_filter_row.setVisible(False)
            if hasattr(self, "_issue_list"):
                self._issue_list.clear()
            self._sync_issue_detail_panel(None)
            return
        self._populate_issue_list(visible_items)
        self._sync_issue_filter_control(all_summary, queue_summary)
        self._sync_issue_detail_panel(self._selected_issue())
        summary = "；".join(
            _issue_item_summary(item)
            for item in visible_items[:3]
            if _issue_item_summary(item)
        )
        if not summary:
            summary = "当前筛选没有问题" if queue_summary.has_filter else "查看明细"
        suffix = "" if len(visible_items) <= 3 else f" 等 {len(visible_items)} 项"
        filter_suffix = ""
        if queue_summary.has_filter:
            filter_parts = []
            if queue_summary.active_category:
                filter_parts.append(_issue_category_label(queue_summary.active_category))
            if queue_summary.active_action_group:
                filter_parts.append(
                    _issue_action_group_label(queue_summary.active_action_group)
                )
            filter_suffix = (
                f"（{' / '.join(part for part in filter_parts if part)} "
                f"{queue_summary.visible_count}/{queue_summary.total_count}）"
            )
        action_summary = _format_issue_action_group_counts(
            queue_summary.visible_action_group_counts
        )
        summary_prefix = f"{action_summary}；" if action_summary else ""
        self._issue_queue_label.setText(
            f"运行前问题 {queue_summary.total_count} 项{filter_suffix}："
            f"{summary_prefix}{summary}{suffix}"
        )
        tooltip_lines: list[str] = [
            "问题处理",
            "行动：" + _format_issue_action_group_counts(
                queue_summary.visible_action_group_counts
            ),
            "分类：" + _format_issue_counts(queue_summary.category_counts),
            "严重度：" + _format_issue_counts(queue_summary.severity_counts),
            "状态：" + _format_issue_counts(queue_summary.status_counts),
            "负责人：" + _format_issue_counts(queue_summary.owner_counts),
            f"阻断：{queue_summary.blocking_count}",
        ]
        if queue_summary.actionable_count:
            tooltip_lines.append(
                "可处理目标：" + _format_issue_target_counts(queue_summary.repair_target_counts)
            )
        active_filter_labels = []
        if queue_summary.active_category:
            active_filter_labels.append(_issue_category_label(queue_summary.active_category))
        if queue_summary.active_action_group:
            active_filter_labels.append(
                _issue_action_group_label(queue_summary.active_action_group)
            )
        if active_filter_labels:
            tooltip_lines.append(
                "当前筛选：" + " / ".join(active_filter_labels)
            )
        for index, item in enumerate(visible_items, start=1):
            tooltip_lines.append(f"{index}. " + _issue_item_summary(item))
            tooltip_lines.extend("   " + line for line in _issue_display_detail_lines(item))
        self._issue_queue_label.setToolTip("\n".join(tooltip_lines))

    def _toggle_issue_panel(self) -> None:
        self._issue_panel_expanded = not self._issue_panel_expanded
        self._set_issue_queue_visible(
            bool(self._workbench_issue_items),
            self._workbench_issue_items,
        )

    def _on_issue_action_group_filter_changed(self, _index: int) -> None:
        if not hasattr(self, "_issue_action_group_combo"):
            return
        action_group = str(self._issue_action_group_combo.currentData() or "").strip()
        if action_group == self._issue_queue_filter_action_group:
            return
        self._issue_queue_filter_action_group = action_group
        self._set_issue_queue_visible(
            bool(self._workbench_issue_items),
            self._workbench_issue_items,
        )

    def recheck_current_context(self, *, force: bool = False) -> None:
        if self._execution_running:
            return
        if not force and self._issue_queue_source not in {
            "",
            "preflight_config",
        }:
            return
        previous_id = self.current_active_issue_id()
        previous_category = str(self._issue_queue_filter_category or "").strip()
        previous_action_group = str(self._issue_queue_filter_action_group or "").strip()
        self._emit_summary_changed()
        if previous_id and any(
            item.issue_id == previous_id for item in self._workbench_issue_items
        ):
            self.set_active_issue(previous_id)
            return
        if previous_category or previous_action_group:
            self._issue_queue_filter_category = previous_category
            self._issue_queue_filter_action_group = previous_action_group
            self._set_issue_queue_visible(
                bool(self._workbench_issue_items),
                self._workbench_issue_items,
            )

    def _populate_issue_list(self, items: list[WorkbenchIssueItem]) -> None:
        if not hasattr(self, "_issue_list"):
            return
        previous_id = self._active_issue_id
        self._issue_list.blockSignals(True)
        self._issue_list.clear()
        target_row = 0
        sorted_items = _sort_issue_items_by_action(items)
        for row, issue in enumerate(sorted_items):
            label = _issue_item_summary(issue)
            if not label:
                label = issue.issue_id
            status = _issue_category_label(str(issue.status or "open"))
            visual = workbench_issue_action_visual_for_item(issue)
            action_group = visual.group
            action_label = visual.label
            item = QListWidgetItem(f"{action_label} · {label}  ·  {status}")
            item.setSizeHint(QSize(0, 38))
            item.setData(Qt.UserRole, issue.issue_id)
            item.setToolTip(
                "\n".join([f"行动：{action_label}", *_issue_tooltip_lines(issue)])
            )
            self._issue_list.addItem(item)
            self._issue_list.setItemWidget(
                item,
                _build_issue_list_row_widget(
                    self._issue_list,
                    issue=issue,
                    label=label,
                    status=status,
                    action_group=action_group,
                    action_label=action_label,
                    badge_tone=visual.badge_tone,
                ),
            )
            if issue.issue_id == previous_id:
                target_row = row
        self._issue_list.setVisible(self._issue_panel_expanded and bool(items))
        if sorted_items:
            self._issue_list.setCurrentRow(target_row)
            selected_issue = sorted_items[target_row]
            self._active_issue_id = str(selected_issue.issue_id or "").strip()
            self._issue_navigation_context = _issue_navigation_context(selected_issue)
        else:
            self._active_issue_id = ""
            self._issue_navigation_context = {}
        self._issue_list.blockSignals(False)

    def _sync_selected_issue_from_list(self) -> None:
        selected = self._selected_issue()
        if selected is not None:
            self._active_issue_id = selected.issue_id
            self._issue_navigation_context = _issue_navigation_context(selected)
        summary = summarize_workbench_issue_queue(self._workbench_issue_items)
        filtered_summary = summarize_workbench_issue_queue(
            self._workbench_issue_items,
            category=self._issue_queue_filter_category,
            action_group=self._issue_queue_filter_action_group,
        )
        self._sync_issue_filter_control(summary, filtered_summary)
        self._sync_issue_detail_panel(selected)

    def _sync_issue_detail_panel(self, issue: WorkbenchIssueItem | None) -> None:
        if not hasattr(self, "_issue_detail_panel"):
            return
        visible = bool(issue is not None and self._issue_panel_expanded)
        self._issue_detail_panel.setVisible(visible)
        if issue is None:
            self._issue_detail_title.setText("")
            self._issue_detail_meta.setText("")
            self._set_issue_detail_section(
                self._issue_detail_impact_section,
                title="",
                body="",
                tone="neutral",
            )
            self._set_issue_detail_section(
                self._issue_detail_action_section,
                title="",
                body="",
                tone="primary",
            )
            self._set_issue_detail_section(
                self._issue_detail_evidence_section,
                title="",
                body="",
                tone="neutral",
            )
            self._sync_issue_evidence_action_controls(None)
            return
        title = _issue_item_summary(issue) or issue.issue_id
        target_type, target_key = workbench_issue_action_target(issue)
        blocking_text = "阻断" if issue.blocking else "提醒"
        action_group = workbench_issue_action_group(issue)
        action_group_text = _issue_action_group_label(action_group)
        self._issue_detail_title.setText(title)
        self._issue_detail_meta.setText(
            " / ".join(
                part
                for part in (
                    action_group_text,
                    _issue_category_label(issue.category),
                    _issue_category_label(issue.severity),
                    _issue_category_label(issue.status),
                    _issue_category_label(issue.owner),
                    blocking_text,
                )
                if part and part != "-"
            )
        )
        evidence_body = workbench_issue_evidence_body_text(issue)
        action_label = _issue_action_label(issue, target_type, target_key)
        self._set_issue_detail_section(
            self._issue_detail_impact_section,
            title="影响",
            body=_issue_detail_impact_text(issue, action_group),
            tone=_issue_detail_impact_tone(issue, action_group),
        )
        self._set_issue_detail_section(
            self._issue_detail_action_section,
            title="动作",
            body=_issue_detail_action_text(issue, action_label, action_group),
            tone="primary",
        )
        self._set_issue_detail_section(
            self._issue_detail_evidence_section,
            title="证据",
            body=evidence_body,
            tone="neutral",
        )
        self._sync_issue_evidence_action_controls(issue)

    def _sync_issue_evidence_action_controls(
        self,
        issue: WorkbenchIssueItem | None,
    ) -> None:
        if not hasattr(self, "_issue_evidence_action_bar"):
            return
        line_items = _issue_evidence_line_items(issue) if issue is not None else []
        self._issue_evidence_line_list.set_items(line_items)
        self._issue_evidence_action_bar.set_actions(line_items)
        self._issue_evidence_parameter_btn = (
            self._issue_evidence_action_bar.button_for_action_type("navigate_parameter")
        )
        self._issue_evidence_file_btn = (
            self._issue_evidence_action_bar.button_for_action_type("open_evidence")
            or self._issue_evidence_action_bar.button_for_action_type("open_output")
            or self._issue_evidence_action_bar.button_for_action_type(
                "open_replacement"
            )
        )
        should_show_actions = bool(
            issue is not None
            and self._issue_panel_expanded
            and self._issue_evidence_action_bar.current_actions()
        )
        self._issue_evidence_line_list.setVisible(
            bool(issue is not None and self._issue_panel_expanded and line_items)
        )
        self._issue_evidence_action_row.setVisible(should_show_actions)

    def _set_issue_detail_section(
        self,
        section: IssueDetailSection,
        *,
        title: str,
        body: str,
        tone: str,
    ) -> None:
        section.set_title(title)
        section.set_body(body)
        section.set_tone(tone)

    def _recheck_current_issue(self) -> None:
        self.recheck_current_context(force=True)

    def _selected_issue(self) -> WorkbenchIssueItem | None:
        selected_id = ""
        if hasattr(self, "_issue_list"):
            current = self._issue_list.currentItem()
            if current is not None:
                selected_id = str(current.data(Qt.UserRole) or "").strip()
        if not selected_id:
            selected_id = str(self._active_issue_id or "").strip()
        visible_items = self.current_filtered_issue_items()
        if selected_id:
            for item in visible_items:
                if item.issue_id == selected_id:
                    return item
        return visible_items[0] if visible_items else None

    def _current_action_issue_candidates(self) -> list[WorkbenchIssueItem]:
        selected = self._selected_issue()
        candidates: list[WorkbenchIssueItem] = []
        if selected is not None:
            candidates.append(selected)
        for item in self.current_filtered_issue_items():
            if selected is not None and item.issue_id == selected.issue_id:
                continue
            candidates.append(item)
        return candidates

    def _sync_issue_filter_control(self, summary, filtered_summary) -> None:
        if not hasattr(self, "_issue_filter_combo") or not hasattr(self, "_issue_filter_row"):
            return
        show_category_filter = summary.has_issues and len(summary.category_counts) > 1
        show_action_group_filter = (
            summary.has_issues and len(summary.action_group_counts) > 1
        )
        show_filter = show_category_filter or show_action_group_filter
        show_action = bool(filtered_summary.actionable_count)
        status_issue = _first_status_mutable_issue(filtered_summary.visible_items)
        show_status_controls = status_issue is not None
        self._issue_filter_row.setVisible(
            self._issue_panel_expanded
            and (show_filter or show_action or show_status_controls)
        )
        if hasattr(self, "_issue_filter_label"):
            self._issue_filter_label.setText("问题筛选" if show_filter else "问题处理")
        self._issue_filter_combo.setVisible(show_category_filter)
        if hasattr(self, "_issue_action_group_combo"):
            self._issue_action_group_combo.setVisible(show_action_group_filter)
        if hasattr(self, "_issue_action_btn"):
            self._issue_action_btn.setVisible(show_action)
            self._issue_action_btn.setEnabled(show_action)
            selected = self._selected_issue()
            target_type, target_key = workbench_issue_action_target(selected) if selected else ("", "")
            if target_type:
                self._issue_action_btn.setToolTip(
                    f"处理当前问题：{_issue_action_label(selected, target_type, target_key)}"
                )
            else:
                self._issue_action_btn.setToolTip("当前筛选没有可处理目标")
        for button_name, tooltip_prefix in (
            ("_issue_resolve_btn", "标记为已处理"),
            ("_issue_ignore_btn", "忽略当前问题"),
        ):
            if hasattr(self, button_name):
                button = getattr(self, button_name)
                button.setVisible(show_status_controls)
                button.setEnabled(show_status_controls)
                if status_issue is not None:
                    button.setToolTip(f"{tooltip_prefix}：{status_issue.title}")
                else:
                    button.setToolTip("当前筛选没有可更新状态的问题")
        if show_category_filter:
            combo = self._issue_filter_combo
            blocked = combo.blockSignals(True)
            combo.clear()
            combo.addItem(f"全部问题 ({summary.total_count})", "")
            for category, count in summary.category_counts:
                combo.addItem(f"{_issue_category_label(category)} ({count})", category)
            target = self._issue_queue_filter_category
            for index in range(combo.count()):
                if str(combo.itemData(index) or "") == target:
                    combo.setCurrentIndex(index)
                    break
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(blocked)
        if show_action_group_filter and hasattr(self, "_issue_action_group_combo"):
            combo = self._issue_action_group_combo
            blocked = combo.blockSignals(True)
            combo.clear()
            combo.addItem(f"全部动作 ({summary.total_count})", "")
            for action_group, count in summary.action_group_counts:
                combo.addItem(
                    f"{_issue_action_group_label(action_group)} ({count})",
                    action_group,
                )
            target = self._issue_queue_filter_action_group
            for index in range(combo.count()):
                if str(combo.itemData(index) or "") == target:
                    combo.setCurrentIndex(index)
                    break
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(blocked)

    def _request_material_repair(self) -> None:
        issues = material_readiness_issue_groups(
            self._current_scene,
            self._material_context,
        )
        if issues.field_keys:
            self.material_repair_requested.emit("field", issues.field_keys[0])
            return
        if issues.asset_roles:
            self.material_repair_requested.emit("asset", issues.asset_roles[0])
            return
        self.feature_config_requested.emit("content_fill")

    def _emit_summary_changed(self) -> None:
        if self._execution_running:
            self._set_material_repair_visible(False)
            self._update_status(build_running_status(self.document_path()))
            self.summary_changed.emit()
            return
        # Not running — build a ready status but only write it to the log label
        material_issues = material_readiness_issue_groups(
            self._current_scene,
            self._material_context,
        )
        self._workbench_issue_items = material_readiness_issue_items(
            self._current_scene,
            self._material_context,
        )
        self._issue_queue_source = "preflight_config"
        self._workbench_issue_items.extend(
            material_asset_comparison_issue_items(self._material_context)
        )
        self._workbench_issue_items.extend(self._cached_static_issue_items())
        self._material_readiness_issues = material_issues
        material_reasons = material_issues.to_reasons()
        status = build_ready_status(
            document_path=self.document_path(),
            strategy_name=self._active_template_label(),
            strict_mode=self.current_strategy() == "rebuild",
            material_schema_reasons=material_reasons,
        )
        self._set_material_repair_visible(
            bool(self.document_path()) and material_issues.has_issues,
            material_issues.detail_lines(),
        )
        self._set_issue_queue_visible(
            bool(self.document_path()) and bool(self._workbench_issue_items),
            self._workbench_issue_items,
        )
        self._exec_status_label.setText(status.text)
        t = get_theme()
        if status.tone == "success":
            color = t.success
        elif status.tone == "warning":
            color = t.warning
        else:
            color = t.text_hint
        self._exec_status_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {color}; background: transparent;"
        )
        self.summary_changed.emit()

    def _cached_static_issue_items(self) -> list[WorkbenchIssueItem]:
        key = self._scene_static_cache_key(
            coverage_boundary_issue_items,
            parameter_ownership_issue_items,
            sample_fixture_issue_items,
            control_contract_issue_items,
        )
        if key != self._scene_issue_cache_key:
            items: list[WorkbenchIssueItem] = []
            items.extend(coverage_boundary_issue_items(self._current_scene))
            items.extend(parameter_ownership_issue_items(self._current_scene))
            items.extend(sample_fixture_issue_items(self._current_scene))
            items.extend(control_contract_issue_items())
            self._scene_issue_cache_key = key
            self._scene_issue_cache = tuple(items)
        return list(self._scene_issue_cache)

    def _apply_theme(self) -> None:
        t = get_theme()
        from src.shared.ui.input_style import build_text_input_stylesheet
        from src.shared.ui.sizing import apply_size_class

        self._layout.setSpacing(t.template_detail_section_gap)

        btn_qss = build_button_stylesheet(t)
        self.setStyleSheet(btn_qss)

        if hasattr(self, "_issue_queue_label"):
            self._issue_queue_label.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.warning}; "
                f"background: transparent; padding-top: 2px;"
            )
        if hasattr(self, "_issue_panel"):
            self._issue_panel.setStyleSheet(
                f"""
                QFrame#wb_v2_issue_panel {{
                    background: {t.bg_hover};
                    border: 1px solid {t.border};
                    border-radius: {t.radius_sm}px;
                }}
                """
            )
        if hasattr(self, "_issue_panel_title"):
            self._issue_panel_title.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.text_primary}; background: transparent;"
            )
        if hasattr(self, "_issue_panel_count"):
            self._issue_panel_count.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_hint}; background: transparent;"
            )
        if hasattr(self, "_issue_panel_toggle_btn"):
            self._issue_panel_toggle_btn.setMinimumHeight(t.control_height_sm)
            self._issue_panel_toggle_btn.setMaximumHeight(t.control_height_sm)
            apply_button_variant(self._issue_panel_toggle_btn, "secondary")
        if hasattr(self, "_issue_filter_label"):
            self._issue_filter_label.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_hint}; background: transparent;"
            )
        if hasattr(self, "_issue_list"):
            self._issue_list.setStyleSheet(
                f"""
                QListWidget#wb_v2_issue_list {{
                    background: {t.bg_input};
                    color: {t.text_primary};
                    border: 1px solid {t.border};
                    border-radius: {t.input_radius}px;
                    padding: 4px;
                    font-size: {t.font_size_sm}px;
                }}
                QListWidget#wb_v2_issue_list::item {{
                    min-height: 30px;
                    padding: 4px 8px;
                }}
                QListWidget#wb_v2_issue_list::item:selected {{
                    background: {t.bg_selected};
                    color: {t.primary};
                }}
                """
            )
        if hasattr(self, "_issue_detail_panel"):
            self._issue_detail_panel.setStyleSheet(
                f"""
                QFrame#wb_v2_issue_detail_panel {{
                    background: {t.bg_card};
                    border: 1px solid {t.border_light};
                    border-radius: {t.radius_sm}px;
                }}
                """
            )
        if hasattr(self, "_issue_detail_title"):
            self._issue_detail_title.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.text_primary}; background: transparent;"
            )
        if hasattr(self, "_issue_detail_meta"):
            self._issue_detail_meta.setStyleSheet(
                f"font-size: {t.font_size_xs}px; color: {t.text_hint}; background: transparent;"
            )
        # Scene/template row labels
        for lbl in self.findChildren(QLabel, "scene_tpl_label"):
            lbl.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.text_secondary}; background: transparent;"
            )
        if hasattr(self, "_style_difference_slot"):
            self._style_difference_slot.apply_theme()

        # Scene/template row icons (match sidebar)
        if hasattr(self, "_scene_icon_label"):
            self._scene_icon_label.setPixmap(
                get_icon("mountain-snow", 16, t.text_hint).pixmap(16, 16)
            )
        if hasattr(self, "_tpl_icon_label"):
            self._tpl_icon_label.setPixmap(
                get_icon("scroll-text", 16, t.text_hint).pixmap(16, 16)
            )

        # Output browse button (styled like scene combo area)
        if hasattr(self, "_output_browse_btn"):
            self._output_browse_btn.setStyleSheet(
                f"QPushButton {{ font-size: {t.font_size_md}px; color: {t.text_secondary}; "
                f"border: 1px solid {t.border}; border-radius: {t.radius_sm}px; "
                f"padding: 6px 12px; background: {t.bg_card}; text-align: left; }}"
                f"QPushButton:hover {{ border-color: {t.primary}; color: {t.primary}; }}"
            )
            if self._custom_output_dir:
                self._output_browse_btn.setIcon(get_icon("folder-open", 16, t.icon_primary))

        # Execute button
        exec_height = t.control_height_lg
        if hasattr(self, "_execute_btn"):
            apply_button_variant(self._execute_btn, "primary")
            exec_height = max(
                exec_height,
                self._execute_btn.minimumSizeHint().height(),
                self._execute_btn.sizeHint().height(),
            )
            self._execute_btn.setMinimumHeight(exec_height)
            self._execute_btn.setMaximumHeight(exec_height)
            if not self._execution_running:
                self._execute_btn.setIcon(get_icon("play", 16, t.text_on_primary))
        if hasattr(self, "_material_repair_btn"):
            self._material_repair_btn.setMinimumHeight(exec_height)
            self._material_repair_btn.setMaximumHeight(exec_height)
            self._material_repair_btn.setIcon(get_icon("pen-tool", 16, t.text_primary))
            apply_button_variant(self._material_repair_btn, "secondary")
        if hasattr(self, "_issue_action_btn"):
            self._issue_action_btn.setMinimumHeight(t.control_height_md)
            self._issue_action_btn.setMaximumHeight(t.control_height_md)
            self._issue_action_btn.setIcon(
                get_icon("square-arrow-out-up-right", 16, t.text_primary)
            )
            apply_button_variant(self._issue_action_btn, "secondary")
        if hasattr(self, "_issue_recheck_btn"):
            self._issue_recheck_btn.setMinimumHeight(t.control_height_md)
            self._issue_recheck_btn.setMaximumHeight(t.control_height_md)
            self._issue_recheck_btn.setIcon(get_icon("refresh-cw", 16, t.text_primary))
            apply_button_variant(self._issue_recheck_btn, "secondary")
        for button_name, icon_name in (
            ("_issue_resolve_btn", "circle-check"),
            ("_issue_ignore_btn", "circle-x"),
        ):
            if hasattr(self, button_name):
                button = getattr(self, button_name)
                button.setMinimumHeight(t.control_height_md)
                button.setMaximumHeight(t.control_height_md)
                button.setIcon(get_icon(icon_name, 16, t.text_primary))
                apply_button_variant(button, "secondary")

        # Exec status area (right of button)
        if hasattr(self, "_exec_status_area"):
            self._exec_status_area.setMinimumHeight(exec_height)
            self._exec_status_area.setMaximumHeight(exec_height)
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

def _first_status_mutable_issue(
    items: tuple[WorkbenchIssueItem, ...] | list[WorkbenchIssueItem],
) -> WorkbenchIssueItem | None:
    for item in list(items or []):
        status = str(getattr(item, "status", "") or "open").strip() or "open"
        if status not in ISSUE_TERMINAL_STATUS_VALUES:
            return item
    return None

def _issue_item_summary(item: WorkbenchIssueItem) -> str:
    title = workbench_issue_display_text(
        str(getattr(item, "title", "") or "").strip(),
        include_raw_field_key=False,
    )
    summary = workbench_issue_display_text(
        str(getattr(item, "summary", "") or "").strip(),
        include_raw_field_key=False,
    )
    if title and summary:
        return f"{title}：{summary}"
    return title or summary


def _sort_issue_items_by_action(
    items: list[WorkbenchIssueItem] | tuple[WorkbenchIssueItem, ...],
) -> list[WorkbenchIssueItem]:
    queue_items = [
        item for item in list(items or []) if isinstance(item, WorkbenchIssueItem)
    ]
    ranked = sorted(
        enumerate(queue_items),
        key=lambda pair: (
            workbench_issue_action_visual_for_item(pair[1]).rank,
            pair[0],
        ),
    )
    return [item for _index, item in ranked]


def _issue_action_group_rank(value: str) -> int:
    return workbench_issue_action_visual(value).rank


def _issue_detail_impact_text(issue: WorkbenchIssueItem, action_group: str) -> str:
    status = str(getattr(issue, "status", "") or "open").strip()
    if status == "resolved":
        return "已处理，保留记录。"
    if status == "ignored":
        return "已忽略，不再作为当前阻断。"
    if action_group == "handle_first":
        if bool(getattr(issue, "blocking", False)):
            return "会阻断本次运行，需要先处理。"
        return "可能导致执行失败或结果不可用，需要先处理。"
    if action_group == "confirm":
        return "不一定阻断运行，但会影响边界判断或修复选择。"
    return "仅供查看，不需要立即处理。"


def _issue_detail_impact_tone(issue: WorkbenchIssueItem, action_group: str) -> str:
    return workbench_issue_action_visual(
        action_group,
        status=str(getattr(issue, "status", "") or "open").strip(),
    ).detail_tone


def _issue_detail_action_text(
    issue: WorkbenchIssueItem,
    action_label: str,
    action_group: str,
) -> str:
    status = str(getattr(issue, "status", "") or "open").strip()
    if status == "resolved":
        return "已处理；需要重新确认时点“复检”。"
    if status == "ignored":
        return "已忽略；需要重新确认时点“复检”。"
    if action_label:
        return f"处理：{action_label}"
    if action_group == "handle_first":
        return "处理：查看证据并补齐缺口"
    if action_group == "confirm":
        return "确认：查看证据后决定是否调整"
    return "查看：保留记录"


def _issue_evidence_line_items(
    issue: WorkbenchIssueItem,
) -> list[EvidenceLineItem]:
    return [
        EvidenceLineItem(
            kind=line.kind,
            label=line.label,
            text=line.text,
            action_type=line.action_type,
            action_value=line.action_value,
            action_label=line.action_label,
            tone=line.tone,
        )
        for line in workbench_issue_evidence_lines(issue)
    ]


def _local_path_from_issue_evidence_action_value(value: str) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    candidate = text.split("#", 1)[0].strip()
    path_part, sep, suffix = candidate.rpartition(":")
    if sep and path_part and suffix.isdigit():
        candidate = path_part
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _build_issue_list_row_widget(
    parent,
    *,
    issue: WorkbenchIssueItem,
    label: str,
    status: str,
    action_group: str,
    action_label: str,
    badge_tone: str,
) -> QWidget:
    t = get_theme()
    row = QWidget(parent)
    row.setObjectName("wb_v2_issue_row")
    row.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    row.setToolTip(
        "\n".join([f"行动：{action_label}", *_issue_tooltip_lines(issue)])
    )
    layout = QHBoxLayout(row)
    layout.setContentsMargins(8, 4, 8, 4)
    layout.setSpacing(8)

    badge = QLabel(action_label, row)
    badge.setObjectName("wb_v2_issue_action_badge")
    badge.setProperty("issue_action_group", str(action_group or "").strip())
    badge.setProperty("issue_action_tone", str(badge_tone or "").strip())
    badge.setAlignment(Qt.AlignCenter)
    badge.setMinimumWidth(58)
    badge.setStyleSheet(_issue_action_badge_stylesheet(badge_tone))
    layout.addWidget(badge, 0)

    summary = QLabel(label, row)
    summary.setObjectName("wb_v2_issue_row_summary")
    summary.setMinimumWidth(0)
    summary.setWordWrap(False)
    summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    summary.setStyleSheet(
        f"font-size: {t.font_size_sm}px; color: {t.text_primary}; "
        "background: transparent;"
    )
    layout.addWidget(summary, 1)

    status_label = QLabel(status, row)
    status_label.setObjectName("wb_v2_issue_row_status")
    status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    status_label.setStyleSheet(
        f"font-size: {t.font_size_xs}px; color: {t.text_hint}; "
        "background: transparent;"
    )
    layout.addWidget(status_label, 0)
    return row


def _issue_action_badge_stylesheet(tone: str) -> str:
    t = get_theme()
    value = str(tone or "").strip()
    if value == "error":
        bg, fg, border = t.error_bg, t.error, t.error
    elif value == "info":
        bg, fg, border = t.info_bg, t.primary, t.primary
    elif value == "success":
        bg, fg, border = t.success_bg, t.success, t.success
    else:
        bg, fg, border = t.bg_hover, t.text_secondary, t.border
    return (
        f"font-size: {t.font_size_xs}px;"
        f"font-weight: {t.font_weight_emphasis};"
        f"color: {fg};"
        f"background: {bg};"
        f"border: 1px solid {border};"
        "border-radius: 6px;"
        "padding: 2px 7px;"
    )


def _issue_tooltip_lines(item: WorkbenchIssueItem) -> list[str]:
    lines = [_issue_item_summary(item) or str(getattr(item, "issue_id", "") or "")]
    lines.extend(_issue_display_detail_lines(item))
    return [line for line in lines if str(line or "").strip()]


def _issue_display_detail_lines(item: WorkbenchIssueItem) -> list[str]:
    lines = [
        workbench_issue_display_text(line)
        for line in list(getattr(item, "details", ()) or ())
    ]
    lines.extend(
        "来源：" + workbench_issue_source_note_label(note)
        for note in list(getattr(item, "source_notes", ()) or ())
    )
    return [line for line in lines if str(line or "").strip()]


def _issue_navigation_context(item: WorkbenchIssueItem) -> dict[str, str]:
    if not isinstance(item, WorkbenchIssueItem):
        return {}
    context = {
        "active_issue_id": str(item.issue_id or "").strip(),
        "issue_item_id": str(item.issue_id or "").strip(),
        "issue_category": str(item.category or "").strip(),
        "issue_title": str(item.title or "").strip(),
        "issue_summary": str(item.summary or "").strip(),
    }
    target_type, target_key = workbench_issue_action_target(item)
    if target_type:
        display_context = field_display_context(target_key, target_type=target_type)
        context.update(
            {
                "issue_target_type": str(target_type or "").strip(),
                "issue_target_key": str(target_key or "").strip(),
                "issue_target_label": display_context.label,
                "issue_target_label_with_group": display_context.label_with_group(),
                "issue_target_layout_item_id": display_context.layout_item_id,
                "issue_target_field_ids": ",".join(display_context.field_ids),
                "issue_target_control_contract_key": (
                    display_context.control_contract_key
                ),
            }
        )
    return context


def _issue_action_label(
    item: WorkbenchIssueItem | None,
    target_type: str,
    target_key: str,
) -> str:
    target_type = str(target_type or "").strip()
    target_key = str(target_key or "").strip()
    owner = str(getattr(item, "owner", "") or "").strip() if item is not None else ""
    category = str(getattr(item, "category", "") or "").strip() if item is not None else ""
    target_label = _issue_target_display_name(target_key)
    if target_type == "field":
        return f"去资料页补齐{target_label}"
    if target_type == "asset":
        return f"去资料页补齐{target_label}"
    if target_type in {"schema", "material_schema"}:
        return "去场景页确认资料 Schema"
    if target_type == "question_figure_item":
        return "去资料页处理对应题图"
    if target_type == "template_style_field":
        return f"去模板页调整{_issue_target_display_name_with_group(target_key)}"
    if target_type == "scene_style_field":
        return f"去场景页调整{_issue_target_display_name_with_group(target_key)}"
    if target_type == "output_target":
        return "去场景页调整生成结果"
    if target_type == "object_preflight":
        return "查看对象预检结果并确认处理方式"
    if target_type in {"coverage_boundary", "sample_fixture", "plugin_boundary"}:
        return "去高级证据核对覆盖和样本"
    if target_type == "plugin_manual_gate":
        return "去高级证据核对人工确认"
    if target_type in {"parameter_ownership", "control_contract"}:
        return "去高级证据核对配置边界"
    if owner == "template":
        return "去模板页调整对应设置"
    if owner == "scene" or category in {"coverage_boundary", "sample_fixture"}:
        return "去场景页调整对应设置"
    if owner == "workbench":
        return "回到工作台处理当前问题"
    if owner in {"pipeline", "report"}:
        return "查看执行报告里的问题说明"
    return "打开对应设置"


def _issue_target_display_name(target_key: str) -> str:
    display_name = field_display_context(target_key).label
    if display_name and display_name != str(target_key or "").strip():
        return display_name
    labels = {
        "company_name": "公司名称",
        "project_name": "项目名称",
        "legal_person": "法定代表人",
        "logo": "企业标志",
        "seal": "公章图片",
        "body.font_name": "正文字体",
        "body.font_cn": "中文字体",
        "body.font_en": "英文字体",
        "body.size_pt": "正文字号",
        "body.special_indent": "首行缩进",
        "body.line_spacing_type": "行距",
        "body.space_before": "段前间距",
        "journal_publisher_rule_review_gate": "期刊规则确认",
        "exam_ai_complex_diagram_gate": "试卷 AI 与复杂图确认",
        "professional_disclosure_review_gate": "专业披露审阅确认",
        "import_ai_conversion_gate": "导入/AI 转换确认",
    }
    return labels.get(str(target_key or "").strip(), "对应项目")


def _issue_target_display_name_with_group(target_key: str) -> str:
    context = field_display_context(target_key)
    label = context.label_with_group()
    if label and label != str(target_key or "").strip():
        return label
    return _issue_target_display_name(target_key)


def _issue_panel_count_text(summary, filtered_summary) -> str:
    total = int(getattr(summary, "total_count", 0) or 0)
    blocking = int(getattr(summary, "blocking_count", 0) or 0)
    visible = int(getattr(filtered_summary, "visible_count", 0) or 0)
    if getattr(filtered_summary, "has_filter", False):
        return f"{visible}/{total} 项，{blocking} 项阻断"
    return f"{total} 项，{blocking} 项阻断"


def _format_issue_counts(values: tuple[tuple[str, int], ...]) -> str:
    if not values:
        return "-"
    return " / ".join(
        f"{_issue_category_label(key)} {count}"
        for key, count in values
    )


def _format_issue_action_group_counts(values: tuple[tuple[str, int], ...]) -> str:
    if not values:
        return "-"
    return " / ".join(
        f"{_issue_action_group_label(key)} {count}"
        for key, count in values
    )


def _format_issue_target_counts(values: tuple[tuple[str, int], ...]) -> str:
    if not values:
        return "-"
    return " / ".join(
        f"{_issue_target_count_label(key)} {count}"
        for key, count in values
    )


def _issue_action_group_label(value: str) -> str:
    raw = str(value or "").strip()
    if raw in {"handle_first", "confirm", "view_only", ""}:
        return workbench_issue_action_visual(raw).label
    return raw or "其他"


def _issue_target_count_label(value: str) -> str:
    raw = str(value or "").strip()
    target_type, _, target_key = raw.partition(":")
    target_label = _issue_target_display_name(target_key)
    labels = {
        "field": f"资料字段：{target_label}",
        "asset": f"资料素材：{target_label}",
        "schema": "资料 Schema",
        "question_figure_item": "题图素材",
        "template_style_field": f"模板样式：{_issue_target_display_name_with_group(target_key)}",
        "scene_style_field": f"场景样式：{_issue_target_display_name_with_group(target_key)}",
        "output_target": "生成结果",
        "object_preflight": "对象预检",
        "coverage_boundary": "覆盖边界",
        "sample_fixture": "样本证据",
        "plugin_boundary": "插件边界",
        "plugin_manual_gate": f"人工确认：{target_label}",
        "parameter_ownership": "参数归属",
        "control_contract": "控件边界",
    }
    return labels.get(target_type, _issue_category_label(raw))


def _issue_category_label(category: str) -> str:
    labels = {
        "material_field": "资料字段",
        "material_asset": "资料资产",
        "material_asset_comparison": "题图对比",
        "material_schema": "资料 Schema",
        "object_preflight": "对象预检",
        "output_target": "输出目标",
        "batch_issue": "批量记录",
        "question_figure_batch_apply_transaction_task": "题图事务任务",
        "plugin_boundary": "插件边界",
        "coverage_boundary": "边界覆盖",
        "sample_fixture": "样本覆盖",
        "parameter_ownership": "参数归属",
        "control_contract": "控件契约",
        "warning": "警告",
        "error": "错误",
        "info": "信息",
        "open": "待处理",
        "in_progress": "处理中",
        "resolved": "已处理",
        "ignored": "已忽略",
        "workbench": "工作台",
        "scene": "场景配置",
        "pipeline": "执行链路",
        "plugin": "插件/专业",
        "report": "报告",
    }
    return labels.get(str(category or "").strip(), str(category or "").strip() or "-")
