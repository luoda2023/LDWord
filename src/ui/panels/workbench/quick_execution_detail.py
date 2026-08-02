from __future__ import annotations

import copy
import re
from dataclasses import replace
from pathlib import Path

from src.application.materials import (
    RUNTIME_IMAGE_WATERMARK_KEY,
    MaterialPreviewSnapshot,
    MaterialRuntimeFieldPreview,
)
from src.config.execution_feature_state import (
    DISABLED_SELECTOR_LABEL,
    DISABLED_SELECTOR_SOURCE_TYPE,
    DISABLED_SELECTOR_VALUE,
    project_execution_scene,
    project_execution_template,
)
from src.config.library import (
    default_scene_descriptor,
    get_template_entry,
    list_template_entries,
    load_scene_from_library,
)
from src.config.official_document_profiles import (
    get_official_document_profile,
    list_common_official_document_profiles,
)
from src.config.official_material_form import (
    OFFICIAL_MATERIAL_FIELD_SPECS,
    official_material_field_label,
)
from src.config.scene import SceneWorkspace
from src.config.scene_presets import (
    LEGACY_FEATURE_GROUP_MAP,
    UI_CAPABILITY_GROUPS,
    UI_GROUP_MAP,
    get_group_enabled,
    set_group_enabled,
)
from src.config.scene_surface_registry import (
    scene_uses_exam_paper_surface,
    scene_uses_official_document_surface,
)
from src.config.work_mode import get_work_mode, resolve_work_mode_id
from src.qt_api import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QIcon,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    Qt,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.services.execution_result_contract import normalize_terminal_payload
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    material_token,
)
from src.shared.ui import ThemedRadioButton
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.keyed_widget_list import KeyedWidgetListController
from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later
from src.shared.ui.official_field_value_edit import OfficialFieldValueEdit
from src.shared.ui.path_action_semantics import PathAction, path_action_presentation
from src.shared.ui.sizing import apply_size_class, resolved_control_height
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.config_selector_models import (
    material_package_selector_options,
    plan_combo_label,
    plan_selector_descriptors,
    strip_source_prefix,
    template_selector_options,
)
from src.ui.adapters.workbench_execution_gate import ExecutionGateDecision
from src.domain.materials import MaterialIssue, MaterialRunSelection
from src.ui.panels.workbench.state import ExecutionResultState

from .quick_execution_drop_area import QuickExecutionDropArea
from .quick_execution_feedback_mixin import QuickExecutionFeedbackMixin
from .quick_execution_floating_fields_mixin import QuickExecutionFloatingFieldsMixin
from .quick_execution_presenter import (
    FEATURE_DEFINITIONS,
    build_feature_navigation_snapshot,
    build_navigation_snapshot,
    build_running_status,
)
from .quick_execution_source_presenter import (
    build_exam_source_projection,
    build_official_document_readiness_projection,
    resolve_official_document_profile_id,
)
from .quick_material_preview import QuickMaterialPreview
from .quick_material_preview_presenter import (
    build_quick_material_preview_projection,
)
from .material_state import material_execution_gate, material_issue_lines


def _strip_library_combo_prefix(label: str) -> str:
    return strip_source_prefix(label)


def _plan_combo_label(descriptor) -> str:
    return plan_combo_label(descriptor, include_source_prefix=False)


def _source_badge(source_type: object) -> tuple[str, str]:
    normalized = str(source_type or "").strip()
    if normalized == DISABLED_SELECTOR_SOURCE_TYPE:
        return ("关闭", "off")
    is_builtin = normalized == "builtin"
    return ("内置", "builtin") if is_builtin else ("自定", "user")


def _refresh_material_package_selector(detail) -> None:
    preview = getattr(detail, "_material_preview", None)
    if preview is None:
        return
    selection = getattr(detail, "_material_selection", None)
    snapshot = getattr(detail, "_material_preview_snapshot", None)
    identity = (
        selection.package_ref.package_id
        if isinstance(selection, MaterialRunSelection)
        else (
            snapshot.package_id
            if isinstance(snapshot, MaterialPreviewSnapshot)
            else ""
        )
    )
    detail._material_package_identity = identity
    selected_identity = (
        identity
        if getattr(detail, "_material_package_enabled", False)
        else DISABLED_SELECTOR_VALUE
    )
    preview.set_package_options(
        material_package_selector_options(
            detail._work_mode_id,
            include_source_prefix=False,
        ),
        selected_identity=selected_identity,
    )


def _apply_material_package_selection(detail, identity: str) -> None:
    selected_identity = str(identity or "").strip()
    material_enabled = selected_identity != DISABLED_SELECTOR_VALUE
    package_identity = (
        selected_identity
        if selected_identity != DISABLED_SELECTOR_VALUE
        else ""
    )
    detail._material_package_identity = package_identity
    detail._material_package_enabled = material_enabled
    detail.material_package_selected.emit(package_identity)


class QuickExecutionDetail(
    QuickExecutionFloatingFieldsMixin,
    QuickExecutionFeedbackMixin,
    QWidget,
):
    """Workbench V2 quick-execution detail pane (redesigned)."""

    feature_toggled = Signal(str, bool)
    feature_config_requested = Signal(str)
    material_repair_requested = Signal(str, str)
    object_preflight_cancel_requested = Signal()
    summary_changed = Signal()
    execute_requested = Signal()
    cancel_requested = Signal()
    document_selected = Signal(str)
    binding_changed = Signal(object, str)
    scene_config_changed = Signal(object)
    official_document_type_changed = Signal(str)
    material_package_selected = Signal(str)

    FEATURE_DEFINITIONS = FEATURE_DEFINITIONS
    FEATURE_ID_ALIASES = LEGACY_FEATURE_GROUP_MAP

    def __init__(self, parent=None, *, include_shared_chrome: bool = True):
        super().__init__(parent)
        self._include_shared_chrome = bool(include_shared_chrome)
        self._execution_running = False
        self._execution_cancel_requested = False
        self._last_result_status = "idle"
        self._last_terminal_payload: dict[str, object] = {}
        self._known_execution_modules: list[str] = []
        self._binding_signal_blocked = False
        self._scene_syncing = False
        self._work_mode_id = "custom"
        self._work_mode_binding_received = False
        self._scene_descriptors = list(plan_selector_descriptors(self._work_mode_id))
        self._official_document_type_id = "notice"
        self._current_template = None
        self._plan_enabled = True
        self._template_enabled = True
        self._material_package_enabled = True
        initial_scene = default_scene_descriptor(mode_id=self._work_mode_id)
        if initial_scene is None and self._scene_descriptors:
            initial_scene = self._scene_descriptors[0]
        if initial_scene is not None:
            self._current_scene = load_scene_from_library(
                initial_scene.config_id,
                mode_id=self._work_mode_id,
            )
        else:
            self._current_scene = SceneWorkspace(
                scene_id="custom",
                template_id="default",
                compatible_template_ids=["default"],
            )
        self._selected_template_id = str(
            getattr(self._current_scene, "template_id", "") or ""
        ).strip()
        self._material_selection: MaterialRunSelection | None = None
        self._material_package_identity = ""
        self._material_preview_snapshot: MaterialPreviewSnapshot | None = None
        self._material_issues: tuple[MaterialIssue, ...] = ()
        self._last_result_issue_count = 0
        self._log_expanded = False
        self._log_collapsed_label = "查看执行日志"
        self._result_primary_path = ""
        self._custom_output_dir = ""

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

        # ── 2. Plan & Template ──
        self._build_scene_section()
        self._layout.addWidget(self._scene_card)

        # ── 3. Execution-time material preview card ──
        self._material_preview = QuickMaterialPreview(self)
        self._material_preview.expanded_changed.connect(
            lambda _expanded: refresh_layout_chain_later(self)
        )
        self._material_preview.package_selected.connect(
            lambda identity: _apply_material_package_selection(self, identity)
        )
        _refresh_material_package_selector(self)
        self._layout.addWidget(self._material_preview)

        # ── 4. Floating material fields ──
        self._floating_fields_card = Card(parent=self)
        self._build_floating_fields_section()
        self._layout.addWidget(self._floating_fields_card)

        # ── 5. Exam source assembly ──
        self._exam_source_card = Card(parent=self)
        self._build_exam_source_section()
        self._layout.addWidget(self._exam_source_card)

        if self._include_shared_chrome:
            # Standalone compatibility surface. Inside Workbench the shared
            # output policy and footer are created by DocumentExecutionDetail.
            self._output_card = Card(parent=self)
            self._build_output_section()
            self._layout.addWidget(self._output_card)

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

    def set_work_mode(self, mode_id: str) -> None:
        mode = str(mode_id or "").strip() or "custom"
        self._work_mode_binding_received = True
        if mode == self._work_mode_id and self._scene_descriptors:
            return
        self._invalidate_execution_feedback()
        self._work_mode_id = mode
        self._material_package_identity = ""
        _refresh_material_package_selector(self)
        self._scene_descriptors = list(plan_selector_descriptors(self._work_mode_id))
        if not hasattr(self, "_scene_combo"):
            return

        current_scene_id = str(getattr(self._current_scene, "scene_id", "") or "").strip()
        self._populate_scene_combo_options(current_scene_id=current_scene_id)
        self._sync_official_document_type_selector_visibility()
        descriptor = self._descriptor_for_scene_id(current_scene_id)
        if descriptor is None:
            descriptor = default_scene_descriptor(mode_id=self._work_mode_id)
        if descriptor is None and self._scene_descriptors:
            descriptor = self._scene_descriptors[0]
        if descriptor is None:
            return
        try:
            scene = load_scene_from_library(
                descriptor.config_id,
                mode_id=self._work_mode_id,
            )
        except Exception as exc:
            self._append_exec_log(
                "error",
                f"Failed to load plan {descriptor.config_id}: {exc}",
            )
            mode = get_work_mode(self._work_mode_id)
            self._populate_template_combo_options(
                current_template_id=str(
                    getattr(mode, "default_template_id", "") or ""
                ).strip()
            )
            self._emit_summary_changed()
            return
        self._binding_signal_blocked = True
        try:
            self._apply_scene(scene)
        finally:
            self._binding_signal_blocked = False
        self._emit_summary_changed()

    def _descriptor_for_scene_id(self, scene_id: str):
        target = str(scene_id or "").strip()
        if not target:
            return None
        return next(
            (
                descriptor
                for descriptor in self._scene_descriptors
                if str(descriptor.config_id or "").strip() == target
            ),
            None,
        )

    def _populate_scene_combo_options(self, *, current_scene_id: str = "") -> None:
        if not hasattr(self, "_scene_combo"):
            return
        blocked = self._scene_combo.blockSignals(True)
        try:
            self._scene_combo.clear()
            selected_index = -1
            for descriptor in self._scene_descriptors:
                badge_text, badge_kind = _source_badge(descriptor.source_type)
                item_index = self._scene_combo.add_badged_item(
                    _plan_combo_label(descriptor),
                    descriptor.config_id,
                    badge_text=badge_text,
                    badge_kind=badge_kind,
                )
                tooltip = descriptor.load_error or str(getattr(descriptor, "path", "") or "")
                if tooltip:
                    self._scene_combo.setItemData(item_index, tooltip, Qt.ToolTipRole)
                if descriptor.config_id == current_scene_id:
                    selected_index = item_index
            badge_text, badge_kind = _source_badge(
                DISABLED_SELECTOR_SOURCE_TYPE
            )
            disabled_index = self._scene_combo.add_badged_item(
                DISABLED_SELECTOR_LABEL,
                DISABLED_SELECTOR_VALUE,
                badge_text=badge_text,
                badge_kind=badge_kind,
            )
            self._scene_combo.setItemData(
                disabled_index,
                "关闭处理方案及其全部执行模块",
                Qt.ToolTipRole,
            )
            if not self._plan_enabled:
                selected_index = disabled_index
            if selected_index >= 0:
                self._scene_combo.setCurrentIndex(selected_index)
        finally:
            self._scene_combo.blockSignals(blocked)

    def _populate_template_combo_options(
        self,
        *,
        template_ids: list[str] | None = None,
        fallback_labels: dict[str, str] | None = None,
        current_template_id: str = "",
    ) -> None:
        """Project exact-mode template entries, including unavailable ones."""

        if not hasattr(self, "_template_combo"):
            return
        blocked = self._template_combo.blockSignals(True)
        try:
            self._template_combo.clear()
            selected_index = -1
            for option in template_selector_options(
                self._work_mode_id,
                template_ids=template_ids,
                fallback_labels=fallback_labels,
                include_source_prefix=False,
            ):
                badge_text, badge_kind = _source_badge(option.source_type)
                item_index = self._template_combo.add_badged_item(
                    option.label,
                    option.value,
                    badge_text=badge_text,
                    badge_kind=badge_kind,
                )
                if option.tooltip:
                    self._template_combo.setItemData(
                        item_index,
                        option.tooltip,
                        Qt.ToolTipRole,
                    )
                if option.disabled:
                    item_getter = getattr(self._template_combo.model(), "item", None)
                    item = item_getter(item_index) if callable(item_getter) else None
                    if item is not None:
                        item.setEnabled(False)
                if option.value == str(current_template_id or "").strip():
                    selected_index = item_index
            badge_text, badge_kind = _source_badge(
                DISABLED_SELECTOR_SOURCE_TYPE
            )
            disabled_index = self._template_combo.add_badged_item(
                DISABLED_SELECTOR_LABEL,
                DISABLED_SELECTOR_VALUE,
                badge_text=badge_text,
                badge_kind=badge_kind,
            )
            self._template_combo.setItemData(
                disabled_index,
                "关闭模板排版，保留方案中的非排版处理",
                Qt.ToolTipRole,
            )
            target = str(current_template_id or "").strip()
            if target:
                self._selected_template_id = target
            if not self._template_enabled:
                selected_index = disabled_index
            if selected_index >= 0:
                self._template_combo.setCurrentIndex(selected_index)
        finally:
            self._template_combo.blockSignals(blocked)

    def _align_work_mode_for_scene(self, scene: SceneWorkspace) -> None:
        mode_id = self._work_mode_id_for_scene(scene)
        if not mode_id or mode_id == self._work_mode_id:
            return
        self._work_mode_id = mode_id
        self._scene_descriptors = list(plan_selector_descriptors(self._work_mode_id))
        self._populate_scene_combo_options(
            current_scene_id=str(getattr(scene, "scene_id", "") or "").strip()
        )

    def _work_mode_id_for_scene(self, scene: SceneWorkspace) -> str:
        return resolve_work_mode_id(
            scene,
            requested_mode_id=(
                self._work_mode_id if self._work_mode_binding_received else ""
            ),
        )

    def _build_scene_section(self) -> None:
        """Build the plan + template cascade selectors."""
        # ── Single row: 处理方案 [combo] | 模板 [combo] ──
        row = QWidget(self)
        row.setObjectName("wb_strategy_selector_row")
        self._scene_template_selector_row = row
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        # Plan icon + label + combo
        self._scene_icon_label = QLabel(row)
        self._scene_icon_label.setFixedSize(16, 16)
        row_layout.addWidget(self._scene_icon_label)

        self._scene_text_label = QLabel("处理方案", row)
        self._scene_text_label.setObjectName("scene_tpl_label")
        row_layout.addWidget(self._scene_text_label)

        self._scene_combo = StyledComboBox(self)
        for descriptor in self._scene_descriptors:
            badge_text, badge_kind = _source_badge(descriptor.source_type)
            item_index = self._scene_combo.add_badged_item(
                _plan_combo_label(descriptor),
                descriptor.config_id,
                badge_text=badge_text,
                badge_kind=badge_kind,
            )
            tooltip = descriptor.load_error or str(getattr(descriptor, "path", "") or "")
            if tooltip:
                self._scene_combo.setItemData(item_index, tooltip, Qt.ToolTipRole)
        badge_text, badge_kind = _source_badge(DISABLED_SELECTOR_SOURCE_TYPE)
        disabled_index = self._scene_combo.add_badged_item(
            DISABLED_SELECTOR_LABEL,
            DISABLED_SELECTOR_VALUE,
            badge_text=badge_text,
            badge_kind=badge_kind,
        )
        self._scene_combo.setItemData(
            disabled_index,
            "关闭处理方案及其全部执行模块",
            Qt.ToolTipRole,
        )
        self._scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        row_layout.addWidget(self._scene_combo, 1)

        row_layout.addSpacing(10)

        self._document_type_label = QLabel("文种", row)
        self._document_type_label.setObjectName("scene_tpl_label")
        row_layout.addWidget(self._document_type_label)

        self._document_type_combo = StyledComboBox(self)
        self._document_type_combo.setObjectName("wb_official_document_type_combo")
        for profile in list_common_official_document_profiles():
            self._document_type_combo.addItem(profile.label, profile.profile_id)
        self._document_type_combo.currentIndexChanged.connect(
            self._on_official_document_type_changed
        )
        row_layout.addWidget(self._document_type_combo, 1)

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

        self._scene_card = Card(parent=self)
        self._scene_card.set_header("处理方案与模板", icon_name="boxes")
        self._scene_card.add_widget(self._scene_template_selector_row)
        self._sync_official_document_type_selector_visibility()

    def _sync_official_document_type_selector_visibility(self) -> None:
        is_official = self._work_mode_id == "official"
        for widget in (
            getattr(self, "_document_type_label", None),
            getattr(self, "_document_type_combo", None),
        ):
            if widget is not None:
                widget.setVisible(is_official)

    def _build_exam_source_section(self) -> None:
        self._exam_source_card.set_header("题源与装配", icon_name="file-text")

        self._exam_source_summary = QLabel("", self._exam_source_card)
        self._exam_source_summary.setObjectName("wb_exam_source_summary")
        self._exam_source_summary.setWordWrap(True)
        self._exam_source_card.add_widget(self._exam_source_summary)

        self._exam_source_rows: dict[str, tuple[QLabel, QLabel]] = {}
        for row_key, label in (
            ("source", "题源"),
            ("assembly", "装配"),
            ("delivery", "输出"),
            ("fields", "填写"),
        ):
            row = QWidget(self._exam_source_card)
            row.setObjectName("wb_exam_source_row")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            key_label = QLabel(label, row)
            key_label.setObjectName("wb_exam_source_key")
            key_label.setMinimumWidth(42)
            layout.addWidget(key_label, 0)

            value_label = QLabel("", row)
            value_label.setObjectName("wb_exam_source_value")
            value_label.setWordWrap(True)
            value_label.setMinimumWidth(0)
            value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            layout.addWidget(value_label, 1)

            self._exam_source_rows[row_key] = (key_label, value_label)
            self._exam_source_card.add_widget(row)

        self._refresh_exam_source_card()

    def _build_floating_fields_section(self) -> None:
        self._floating_fields_card.set_header("自由字段填写", icon_name="type")
        self._floating_fields_progress = QLabel("", self._floating_fields_card)
        self._floating_fields_progress.setObjectName("wb_floating_fields_progress")
        self._floating_fields_card.add_header_action(self._floating_fields_progress)
        self._floating_fields_container = QWidget(self._floating_fields_card)
        self._floating_fields_layout = QVBoxLayout(self._floating_fields_container)
        self._floating_fields_layout.setContentsMargins(0, 0, 0, 0)
        self._floating_fields_layout.setSpacing(0)
        self._floating_field_inputs: dict[str, OfficialFieldValueEdit] = {}
        self._floating_field_name_labels: dict[str, QLabel] = {}
        self._floating_field_rows: dict[str, QWidget] = {}
        self._floating_field_render_values: dict[str, str] = {}
        self._floating_field_specs: dict[str, MaterialRuntimeFieldPreview] = {}
        self._floating_generated_keys: set[str] = set()
        self._floating_fields_controller = KeyedWidgetListController[
            tuple[str, bool], str
        ](
            layout=self._floating_fields_layout,
            create_widget=self._create_floating_field_row,
            update_widget=self._update_floating_field_row,
            dispose_widget=self._dispose_floating_field_row,
            key=lambda item: item[0],
        )
        self._floating_fields_card.add_widget(self._floating_fields_container)
        self._refresh_floating_fields_card()

    def _build_output_section(self) -> None:
        """Build the output directory section — matches scene card style."""
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
        self._output_browse_btn.setProperty(
            "pathAction",
            PathAction.CHOOSE_DIRECTORY.value,
        )
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
        self._invalidate_execution_feedback()
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
        self._invalidate_execution_feedback()
        self._custom_output_dir = folder
        display = Path(folder).name or folder
        self._output_browse_btn.setText(display)
        choose_directory = path_action_presentation(PathAction.CHOOSE_DIRECTORY)
        self._output_browse_btn.setIcon(
            get_icon(choose_directory.icon_name, 16, get_theme().icon_primary)
        )
        self._output_browse_btn.setProperty(
            "pathAction",
            PathAction.CHOOSE_DIRECTORY.value,
        )
        # Auto-switch to custom mode if not already
        if not self._output_custom_radio.isChecked():
            self._output_custom_radio.setChecked(True)
        self._emit_summary_changed()

    def custom_output_dir(self) -> str:
        """Return custom output directory, or empty for default."""
        return self._custom_output_dir

    def _build_execute_area(self) -> None:
        self._execution_card.set_header("执行输出", icon_name="terminal")
        exec_row = QWidget(self)
        exec_row_layout = QHBoxLayout(exec_row)
        exec_row_layout.setContentsMargins(0, 0, 0, 0)
        exec_row_layout.setSpacing(0)
        self._build_primary_execution_actions(exec_row_layout)
        self._build_execution_status_area(
            exec_row,
            exec_row_layout,
            resolved_control_height(get_theme(), "lg"),
        )
        self._build_secondary_execution_actions(exec_row_layout)
        self._execution_card.add_widget(exec_row)
        self._build_result_receipt()
        self._build_execution_log_area()

    def _build_primary_execution_actions(self, layout: QHBoxLayout) -> None:
        self._execute_btn = QPushButton("生成文档", self)
        self._execute_btn.setObjectName("wb_v2_execute_btn")
        apply_size_class(self._execute_btn, "lg")
        self._execute_btn.setCursor(Qt.PointingHandCursor)
        self._execute_btn.setIcon(get_icon("play", 16, get_theme().text_on_primary))
        apply_button_variant(self._execute_btn, "primary")
        self._execute_btn.clicked.connect(self.execute_requested.emit)
        layout.addWidget(self._execute_btn, 4)

    def _build_execution_status_area(
        self,
        parent: QWidget,
        layout: QHBoxLayout,
        height: int,
    ) -> None:
        self._exec_status_area = QWidget(parent)
        self._exec_status_area.setObjectName("wb_v2_exec_status_area")
        self._exec_status_area.setMinimumHeight(height)
        self._exec_status_area.setMaximumHeight(height)
        status_layout = QVBoxLayout(self._exec_status_area)
        status_layout.setContentsMargins(12, 0, 12, 0)
        status_layout.setSpacing(0)

        self._exec_status_label = QLabel("等待开始...", self._exec_status_area)
        self._exec_status_label.setObjectName("wb_v2_exec_status")
        self._exec_status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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
        layout.addWidget(self._exec_status_area, 9)

    def _build_secondary_execution_actions(self, layout: QHBoxLayout) -> None:
        self._material_repair_btn = QPushButton("补资料", self)
        self._material_repair_btn.setObjectName("wb_v2_material_repair_btn")
        apply_size_class(self._material_repair_btn, "lg")
        self._material_repair_btn.setCursor(Qt.PointingHandCursor)
        self._material_repair_btn.setToolTip("打开资料配置")
        self._material_repair_btn.setIcon(get_icon("pen-tool", 16, get_theme().text_primary))
        apply_button_variant(self._material_repair_btn, "secondary")
        self._material_repair_btn.clicked.connect(self._request_material_repair)
        self._material_repair_btn.setVisible(False)
        layout.addWidget(self._material_repair_btn, 2)

        self._execution_cancel_btn = QPushButton("取消生成", self)
        self._execution_cancel_btn.setObjectName("wb_v2_execution_cancel_btn")
        apply_size_class(self._execution_cancel_btn, "lg")
        self._execution_cancel_btn.setCursor(Qt.PointingHandCursor)
        self._execution_cancel_btn.setIcon(
            get_icon("circle-x", 16, get_theme().text_primary)
        )
        apply_button_variant(self._execution_cancel_btn, "secondary")
        self._execution_cancel_btn.clicked.connect(self._request_execution_cancel)
        self._execution_cancel_btn.setVisible(False)
        layout.addWidget(self._execution_cancel_btn, 2)

        self._object_preflight_cancel_btn = QPushButton("取消", self)
        self._object_preflight_cancel_btn.setObjectName(
            "wb_v2_object_preflight_cancel_btn"
        )
        apply_size_class(self._object_preflight_cancel_btn, "lg")
        self._object_preflight_cancel_btn.setCursor(Qt.PointingHandCursor)
        self._object_preflight_cancel_btn.setIcon(
            get_icon("circle-x", 16, get_theme().text_primary)
        )
        apply_button_variant(self._object_preflight_cancel_btn, "secondary")
        self._object_preflight_cancel_btn.clicked.connect(
            self.object_preflight_cancel_requested.emit
        )
        self._object_preflight_cancel_btn.setVisible(False)
        layout.addWidget(self._object_preflight_cancel_btn, 1)

    def _build_execution_log_area(self) -> None:
        self._log_toggle_btn = QPushButton("查看执行日志", self)
        self._log_toggle_btn.setObjectName("wb_v2_log_toggle_btn")
        self._log_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._log_toggle_btn.setIcon(get_icon("chevron-down", 16, get_theme().text_primary))
        self._log_toggle_btn.clicked.connect(self._toggle_log_visibility)
        apply_button_variant(self._log_toggle_btn, "ghost-primary")
        apply_size_class(self._log_toggle_btn, "sm")
        self._log_toggle_btn.setVisible(False)
        self._execution_card.add_widget(self._log_toggle_btn)

        self._exec_log = QTextEdit(self)
        self._exec_log.setReadOnly(True)
        self._exec_log.setMinimumHeight(120)
        self._exec_log.setMaximumHeight(200)
        self._exec_log.setObjectName("wb_v2_log_terminal")
        self._exec_log.setVisible(False)
        self._execution_card.add_widget(self._exec_log)
        self._exec_error_count = 0

    def _build_result_receipt(self) -> None:
        self._result_receipt = QWidget(self._execution_card)
        self._result_receipt.setObjectName("wb_v2_result_receipt")
        layout = QHBoxLayout(self._result_receipt)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(8)

        self._result_receipt_icon = QLabel(self._result_receipt)
        self._result_receipt_icon.setFixedSize(18, 18)
        self._result_receipt_icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._result_receipt_icon)

        self._result_receipt_label = QLabel("", self._result_receipt)
        self._result_receipt_label.setObjectName("wb_v2_result_receipt_label")
        self._result_receipt_label.setMinimumWidth(0)
        self._result_receipt_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )
        layout.addWidget(self._result_receipt_label, 1)

        self._open_result_btn = QPushButton("打开文档", self._result_receipt)
        self._open_result_btn.setObjectName("wb_v2_open_result")
        self._open_result_btn.setCursor(Qt.PointingHandCursor)
        self._open_result_btn.clicked.connect(self._open_primary_result)
        layout.addWidget(self._open_result_btn)

        self._open_result_folder_btn = QPushButton("打开目录", self._result_receipt)
        self._open_result_folder_btn.setObjectName("wb_v2_open_result_folder")
        self._open_result_folder_btn.setCursor(Qt.PointingHandCursor)
        self._open_result_folder_btn.clicked.connect(
            self._open_primary_result_folder
        )
        layout.addWidget(self._open_result_folder_btn)

        self._result_receipt.setVisible(False)
        self._execution_card.add_widget(self._result_receipt)

    # ═══════════════════════════════════════════════════════════════════════
    #  Plan / template cascade logic
    # ═══════════════════════════════════════════════════════════════════════

    def _on_scene_changed(self, index: int) -> None:
        scene_id = str(self._scene_combo.itemData(index) or "").strip()
        if scene_id == DISABLED_SELECTOR_VALUE:
            if self._plan_enabled:
                self._invalidate_execution_feedback()
            self._plan_enabled = False
            self._configure_drop_area_for_scene(self.execution_scene())
            self._refresh_floating_fields_card()
            self._refresh_exam_source_card()
            self._emit_summary_changed()
            return

        descriptor = self._descriptor_for_scene_id(scene_id)
        if descriptor is None and 0 <= index < len(self._scene_descriptors):
            descriptor = self._scene_descriptors[index]
        if descriptor is not None and descriptor.load_error:
            if self._current_scene is not None:
                restore_index = self._find_scene_index(self._current_scene.scene_id)
                if restore_index >= 0 and restore_index != index:
                    blocked = self._scene_combo.blockSignals(True)
                    self._scene_combo.setCurrentIndex(restore_index)
                    self._scene_combo.blockSignals(blocked)
            self._append_exec_log("error", f"方案“{descriptor.name}”加载失败：{descriptor.load_error}")
            return

        if not scene_id and 0 <= index < len(self._scene_descriptors):
            scene_id = self._scene_descriptors[index].config_id
        if scene_id:
            self._invalidate_execution_feedback()
            self._plan_enabled = True
            self._current_scene = load_scene_from_library(
                scene_id,
                mode_id=self._work_mode_id,
            )
            self._apply_scene(self._current_scene)
            self._emit_summary_changed()
            self._emit_binding_changed()

    def _on_official_document_type_changed(self, _index: int) -> None:
        profile_id = str(self._document_type_combo.currentData() or "").strip()
        if not profile_id or get_official_document_profile(profile_id) is None:
            return
        if profile_id != self._official_document_type_id:
            self._invalidate_execution_feedback()
        self._official_document_type_id = profile_id
        self._refresh_exam_source_card()
        self._emit_summary_changed()
        self.official_document_type_changed.emit(profile_id)

    def _apply_scene(self, scene: SceneWorkspace) -> None:
        """Apply a scene and refresh the execution surface."""
        scene = copy.deepcopy(scene)
        self._align_work_mode_for_scene(scene)
        self._sync_official_document_type_selector_visibility()
        self._current_scene = scene
        self._selected_template_id = str(scene.template_id or "").strip()
        self._configure_drop_area_for_scene(self.execution_scene(scene))
        self._scene_syncing = True
        try:
            scene_index = (
                self._find_scene_index(DISABLED_SELECTOR_VALUE)
                if not self._plan_enabled
                else self._find_scene_index(scene.scene_id)
            )
            if scene_index >= 0:
                was_blocked = self._scene_combo.blockSignals(True)
                self._scene_combo.setCurrentIndex(scene_index)
                self._scene_combo.blockSignals(was_blocked)

            template_ids = list(scene.compatible_template_ids or [])
            if not template_ids:
                seed = str(scene.template_id or "").strip()
                if seed:
                    template_ids.append(seed)
            fallback_labels = {
                template_id: self._template_label_for_scene(scene, template_id)
                for template_id in template_ids
            }
            self._populate_template_combo_options(
                template_ids=template_ids,
                fallback_labels=fallback_labels,
                current_template_id=self._selected_template_id,
            )

            self._refresh_floating_fields_card()
            self._refresh_exam_source_card()
        finally:
            self._scene_syncing = False

    def _configure_drop_area_for_scene(self, scene: SceneWorkspace) -> None:
        if not hasattr(self, "_drop_area"):
            return
        if scene_uses_exam_paper_surface(scene, mode_id=self._work_mode_id):
            self._drop_area.configure_file_acceptance(
                suffixes=(".md", ".markdown"),
                idle_title="上传 Markdown 题稿",
                idle_suffix="支持格式：.md / .markdown",
                dialog_title="选择 Markdown 题稿",
                dialog_label="Markdown 文件",
                icon_text="M",
            )
            return
        self._drop_area.configure_file_acceptance(
            suffixes=(".docx",),
            idle_title="拖拽文件至此处",
            idle_suffix="支持格式：.docx",
            dialog_title="选择文档",
            dialog_label="Word 文档",
            icon_text="W",
        )

    def _refresh_exam_source_card(self) -> None:
        if not hasattr(self, "_exam_source_card"):
            return
        if self._is_official_document_scene():
            self._exam_source_card.set_header("公文资料与装配", icon_name="file-text")
            self._set_source_card_row_labels(
                {
                    "source": "处理方案",
                    "assembly": "文种",
                    "delivery": "版式 / 模板",
                    "fields": "资料字段",
                }
            )
            self._exam_source_card.setVisible(True)
            summary, rows = self._official_document_readiness_projection()
        elif self._is_exam_scene():
            self._exam_source_card.set_header("题源与装配", icon_name="file-text")
            self._set_source_card_row_labels(
                {
                    "source": "题源",
                    "assembly": "装配",
                    "delivery": "输出",
                    "fields": "状态",
                }
            )
            self._exam_source_card.setVisible(True)
            summary, rows = self._exam_source_projection()
        else:
            self._exam_source_card.setVisible(False)
            return

        self._exam_source_summary.setText(summary)
        for row_key, (_key_label, value_label) in self._exam_source_rows.items():
            value_label.setText(rows.get(row_key, ""))
        refresh_layout_chain_later(self._exam_source_card)

    def _set_source_card_row_labels(self, labels: dict[str, str]) -> None:
        for row_key, (key_label, _value_label) in getattr(
            self,
            "_exam_source_rows",
            {},
        ).items():
            key_label.setText(labels.get(row_key, row_key))

    def _is_exam_scene(self) -> bool:
        return scene_uses_exam_paper_surface(
            self.execution_scene(),
            mode_id=self._work_mode_id,
        )

    def _is_official_document_scene(self) -> bool:
        return scene_uses_official_document_surface(
            self.execution_scene(),
            mode_id=self._work_mode_id,
        )

    def _exam_source_projection(self) -> tuple[str, dict[str, str]]:
        return build_exam_source_projection(
            scene=self.execution_scene(),
            document_path=(
                self.document_path() if hasattr(self, "_drop_area") else ""
            ),
        )

    def _official_document_readiness_projection(self) -> tuple[str, dict[str, str]]:
        return build_official_document_readiness_projection(
            profile_id=self._official_profile_id(),
            preview_snapshot=self._material_preview_snapshot,
            plan_label=self._active_plan_label(),
            template_label=self._active_template_combo_label(),
        )

    def _official_profile_id(self) -> str:
        return resolve_official_document_profile_id(
            explicit_profile_id=getattr(self, "_official_document_type_id", ""),
            scene=getattr(self, "_current_scene", None),
        )

    def _active_plan_label(self) -> str:
        if not self._plan_enabled:
            return DISABLED_SELECTOR_LABEL
        if hasattr(self, "_scene_combo"):
            label = _strip_library_combo_prefix(self._scene_combo.currentText())
            if label:
                return label
        return (
            str(getattr(self._current_scene, "name", "") or "").strip()
            or str(getattr(self._current_scene, "scene_id", "") or "").strip()
            or "当前方案"
        )

    def _active_template_combo_label(self) -> str:
        if not self._template_enabled:
            return DISABLED_SELECTOR_LABEL
        if hasattr(self, "_template_combo"):
            label = _strip_library_combo_prefix(self._template_combo.currentText())
            if label:
                return label
        template_id = str(getattr(self._current_scene, "template_id", "") or "").strip()
        return template_id or "当前模板"

    # ═══════════════════════════════════════════════════════════════════════
    #  Event handlers
    # ═══════════════════════════════════════════════════════════════════════

    def _on_file_selected(self, file_path: str) -> None:
        self._invalidate_execution_feedback()
        if file_path:
            self.document_selected.emit(file_path)
        self._refresh_exam_source_card()
        self._emit_summary_changed()

    def _on_file_cleared(self) -> None:
        self._invalidate_execution_feedback()
        self.document_selected.emit("")
        self._refresh_exam_source_card()
        self._emit_summary_changed()

    def _on_feature_config_requested(self, feature_id: str) -> None:
        self.feature_config_requested.emit(feature_id)

    # ═══════════════════════════════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════════════════════════════

    def document_path(self) -> str:
        return self._drop_area.file_path()

    def set_document_picker_visible(self, visible: bool) -> None:
        self._drop_area.setVisible(bool(visible))

    def set_document_scope_status(self, state: str, *, count: int = 0) -> None:
        """Retain the scan-controller API without rendering a status row."""

    def pick_document_path(self) -> str:
        """Choose an input using the same format policy shown by the drop area."""
        return self._drop_area.pick_file()

    def set_document_path(self, file_path: str) -> None:
        cleaned = str(file_path or "").strip()
        previous = self._drop_area.file_path()
        if cleaned == previous:
            return
        self._invalidate_execution_feedback()
        was_blocked = self._drop_area.blockSignals(True)
        try:
            if cleaned:
                self._drop_area.set_file(cleaned)
            else:
                self._drop_area.clear()
        finally:
            self._drop_area.blockSignals(was_blocked)
        self._refresh_exam_source_card()
        self._emit_summary_changed()

    def set_scene_context(self, scene: SceneWorkspace) -> None:
        """Apply an externally selected scene to the full quick execution surface."""
        if scene != self._current_scene:
            self._invalidate_execution_feedback()
        self._apply_scene(scene)
        self._emit_summary_changed()

    def official_document_type_id(self) -> str:
        return self._official_profile_id()

    def set_official_document_type_id(
        self,
        document_type_id: str,
        *,
        emit_signal: bool = False,
    ) -> bool:
        normalized = str(document_type_id or "").strip()
        if get_official_document_profile(normalized) is None:
            return False
        changed = normalized != self._official_document_type_id
        if changed:
            self._invalidate_execution_feedback()
        self._official_document_type_id = normalized
        if hasattr(self, "_document_type_combo"):
            index = self._document_type_combo.findData(normalized)
            if index >= 0:
                blocked = self._document_type_combo.blockSignals(True)
                self._document_type_combo.setCurrentIndex(index)
                self._document_type_combo.blockSignals(blocked)
        self._refresh_exam_source_card()
        self._emit_summary_changed()
        if emit_signal and changed:
            self.official_document_type_changed.emit(normalized)
        return changed

    def set_template_context(self, template) -> None:
        """Apply the externally selected formatting template."""
        if template != self._current_template:
            self._invalidate_execution_feedback()
        self._current_template = template
        self._emit_summary_changed()

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
                        if self._plan_enabled:
                            self._scene_combo.setCurrentIndex(idx)
                        break
            projected_disabled_label = (
                str(template_name or "").strip()
                == DISABLED_SELECTOR_LABEL
                and (
                    not self._plan_enabled
                    or not self._template_enabled
                )
            )
            if template_name and not projected_disabled_label:
                self._ensure_combo_value(template_name, template_id=template_id)
            elif template_id:
                self._set_current_template_id(template_id)
            if strict_mode is not None:
                self._current_scene.strict_mode = bool(strict_mode)
        finally:
            self._binding_signal_blocked = False
            self._scene_syncing = False
        self._emit_summary_changed()

    def set_execute_enabled(self, enabled: bool) -> None:
        if hasattr(self, "_execute_btn"):
            self._execute_btn.setEnabled(bool(enabled))

    def has_local_execution_surface(self) -> bool:
        return self._include_shared_chrome

    def set_object_preflight_confirmation(
        self,
        state: ExecutionResultState,
        *,
        blocked: bool = False,
    ) -> None:
        self._execution_running = False
        self._last_result_status = "failed" if blocked else "idle"
        if not self._include_shared_chrome:
            self.summary_changed.emit()
            return
        self._reset_execution_cancel_button()
        self._clear_result_receipt()
        self._exec_bar.setVisible(False)
        self._set_material_repair_visible(False)
        self._object_preflight_cancel_btn.setVisible(not blocked)
        payload = dict(state.object_preflight or {})
        findings_count = int(payload.get("findings_count") or 0)
        module_skips_count = int(payload.get("module_skips_count") or 0)
        if blocked:
            status_text = (
                f"无法生成：检测到 {findings_count} 个高风险对象"
                if findings_count
                else "无法生成：对象预检未通过"
            )
        else:
            status_text = (
                f"检测到 {findings_count} 个对象风险"
                if findings_count
                else "对象预检需确认"
            )
            if module_skips_count:
                status_text += f"，继续后将跳过 {module_skips_count} 个模块"
        self._set_status(status_text, "error" if blocked else "warning")
        level = "error" if blocked else "warning"
        if blocked:
            self._append_exec_log("error", "对象预检发现阻断风险，已停止执行。")
        else:
            self._append_exec_log("warning", "对象预检发现风险，再次点击将继续执行。")
        if state.object_preflight_summary:
            self._append_exec_log(level, state.object_preflight_summary)
        for line in list(state.object_preflight_details or []):
            self._append_exec_log(level, f"对象预检明细：{line}")
        if findings_count:
            self._log_collapsed_label = f"查看 {findings_count} 项对象风险"
            self._set_log_expanded(self._log_expanded)

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
        if get_group_enabled(self._current_scene, group) != bool(enabled):
            self._invalidate_execution_feedback()
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

    def enabled_features(self) -> list[str]:
        scene = self.execution_scene()
        enabled: list[str] = []
        for group in UI_CAPABILITY_GROUPS:
            if get_group_enabled(scene, group):
                enabled.append(group.group_id)
        return enabled

    def current_scene_id(self) -> str:
        if not self._plan_enabled:
            return DISABLED_SELECTOR_VALUE
        return self._current_scene.scene_id

    def current_scene(self) -> SceneWorkspace:
        return self._current_scene

    def execution_scene(
        self,
        scene: SceneWorkspace | None = None,
    ) -> SceneWorkspace:
        """Return a runtime projection honoring all three enablement switches."""

        return project_execution_scene(
            scene if isinstance(scene, SceneWorkspace) else self._current_scene,
            plan_enabled=self._plan_enabled,
            template_enabled=self._template_enabled,
            material_enabled=self._material_package_enabled,
        )

    def execution_template(self, template=None):
        """Return the selected template or a neutral runtime template."""

        selected = template if template is not None else self._current_template
        return project_execution_template(
            selected,
            enabled=self._plan_enabled and self._template_enabled,
        )

    def execution_material_selection(self) -> MaterialRunSelection | None:
        """Return the exact committed selection used by the next run."""

        if not self._plan_enabled or not self._material_package_enabled:
            return None
        return self._material_selection

    def plan_enabled(self) -> bool:
        return self._plan_enabled

    def template_enabled(self) -> bool:
        return self._template_enabled

    def material_package_enabled(self) -> bool:
        return self._material_package_enabled

    def set_material_selection(
        self,
        selection: MaterialRunSelection | None,
        *,
        preview_snapshot: MaterialPreviewSnapshot | None = None,
        issues: tuple[MaterialIssue, ...] = (),
        material_enabled: bool | None = None,
    ) -> None:
        next_selection = (
            selection
            if isinstance(selection, MaterialRunSelection)
            else None
        )
        next_enabled = (
            self._material_package_enabled
            if material_enabled is None
            else bool(material_enabled)
        )
        if material_enabled is None and next_selection is not None:
            next_enabled = True
        if (
            next_selection != self._material_selection
            or next_enabled != self._material_package_enabled
        ):
            self._invalidate_execution_feedback()
        self._material_selection = next_selection
        self._material_package_enabled = next_enabled
        if preview_snapshot is not None:
            self._material_preview_snapshot = preview_snapshot
        self._material_issues = tuple(issues)
        _refresh_material_package_selector(self)
        self._refresh_floating_fields_card()
        self._refresh_exam_source_card()
        self._emit_summary_changed()

    def set_material_preview_snapshot(
        self,
        snapshot: MaterialPreviewSnapshot | None,
    ) -> None:
        next_snapshot = (
            snapshot
            if isinstance(snapshot, MaterialPreviewSnapshot)
            else None
        )
        if next_snapshot == self._material_preview_snapshot:
            return
        self._material_preview_snapshot = next_snapshot
        _refresh_material_package_selector(self)
        self._refresh_floating_fields_card()
        self._emit_summary_changed()

    def set_material_issues(
        self,
        issues: tuple[MaterialIssue, ...] | list[MaterialIssue],
    ) -> None:
        next_issues = tuple(issues)
        if next_issues == self._material_issues:
            return
        self._material_issues = next_issues
        self._emit_summary_changed()

    def last_terminal_payload(self) -> dict[str, object]:
        return normalize_terminal_payload(self._last_terminal_payload)

    def current_template_id(self) -> str:
        if not self._template_enabled:
            return ""
        return self._binding_template_id()

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
        if target_id and self._template_id_is_from_other_work_mode(target_id):
            return
        if target_id and target_id not in set(
            self._current_scene.compatible_template_ids or []
        ):
            return
        if target_id:
            for index in range(self._template_combo.count()):
                if str(self._template_combo.itemData(index) or "").strip() == target_id:
                    self._template_combo.setItemText(index, target)
                    self._set_current_template_id(target_id)
                    if self._template_enabled:
                        self._template_combo.setCurrentIndex(index)
                    return
        for index in range(self._template_combo.count()):
            if self._template_combo.itemText(index).strip() == target and not target_id:
                self._template_combo.setCurrentIndex(index)
                return
        disabled_index = self._find_template_index(DISABLED_SELECTOR_VALUE)
        insert_index = (
            disabled_index
            if disabled_index >= 0
            else self._template_combo.count()
        )
        self._template_combo.insertItem(
            insert_index,
            target,
            target_id or self._binding_template_id() or target,
        )
        if self._template_enabled:
            self._template_combo.setCurrentIndex(insert_index)
        if target_id:
            self._set_current_template_id(target_id)

    def _set_current_template_id(self, template_id: str) -> None:
        target = str(template_id or "").strip()
        if not target:
            return
        if self._template_id_is_from_other_work_mode(target):
            return
        if target not in set(self._current_scene.compatible_template_ids or []):
            return
        self._selected_template_id = target

    def _binding_template_id(self) -> str:
        selected = str(getattr(self, "_selected_template_id", "") or "").strip()
        if selected:
            return selected
        return str(self._current_scene.template_id or "").strip()

    def _template_id_is_from_other_work_mode(self, template_id: str) -> bool:
        target = str(template_id or "").strip()
        if not target:
            return False
        if get_template_entry(target, mode_id=self._work_mode_id) is not None:
            return False
        return any(
            str(entry.config_id or "").strip() == target
            for entry in list_template_entries()
        )

    def _find_scene_index(self, scene_id: str) -> int:
        target = str(scene_id or "").strip()
        if not target:
            return -1
        for index in range(self._scene_combo.count()):
            if str(self._scene_combo.itemData(index) or "").strip() == target:
                return index
        return -1

    def _find_template_index(self, template_id: str) -> int:
        target = str(template_id or "").strip()
        if not target:
            return -1
        for index in range(self._template_combo.count()):
            if str(self._template_combo.itemData(index) or "").strip() == target:
                return index
        return -1

    def _on_template_changed(self, _index: int) -> None:
        if not self._scene_syncing:
            self._invalidate_execution_feedback()
        template_id = str(self._template_combo.currentData() or "").strip()
        if template_id == DISABLED_SELECTOR_VALUE:
            self._template_enabled = False
            self._emit_summary_changed()
            return
        if template_id:
            self._template_enabled = True
            self._set_current_template_id(template_id)
        self._emit_summary_changed()
        if not self._scene_syncing:
            self._emit_binding_changed()

    def _emit_binding_changed(self) -> None:
        if self._binding_signal_blocked:
            return
        self.binding_changed.emit(self._current_scene, self._binding_template_id())

    def _active_template_label(self) -> str:
        if not self._plan_enabled or not self._template_enabled:
            return DISABLED_SELECTOR_LABEL
        label = _strip_library_combo_prefix(self._template_combo.currentText())
        template_id = str(self._template_combo.currentData() or "").strip()
        if template_id and (not label or label == template_id):
            entry = get_template_entry(template_id, mode_id=self._work_mode_id)
            entry_name = str(getattr(entry, "name", "") or "").strip()
            if entry_name:
                label = entry_name
        if not label or label == "默认格式":
            return "默认流程"
        return label

    def _template_label_for_scene(self, scene: SceneWorkspace, template_id: str) -> str:
        target = str(template_id or "").strip()
        mode_id = str(getattr(scene, "mode_id", "") or self._work_mode_id).strip()
        entry = get_template_entry(target, mode_id=mode_id)
        label = str(getattr(entry, "name", "") or "").strip()
        if label:
            return label
        return target

    def _resolve_feature_id(self, feature_id: str) -> str:
        return self.FEATURE_ID_ALIASES.get(feature_id, feature_id)

    def recheck_current_context(self, *, force: bool = False) -> None:
        if self._execution_running:
            return
        self._emit_summary_changed()

    def current_execution_gate_decision(self) -> ExecutionGateDecision:
        return material_execution_gate(
            self.execution_material_selection(),
            self._material_issues,
        )

    def _request_material_repair(self) -> None:
        decision = self.current_execution_gate_decision()
        action = decision.primary_action
        if action is not None and action.available:
            self.material_repair_requested.emit(action.target_type, action.target_key)
            return
        self.feature_config_requested.emit("content_fill")

    def _emit_summary_changed(self) -> None:
        if self._execution_running:
            if not self._include_shared_chrome:
                self.summary_changed.emit()
                return
            self._set_material_repair_visible(False)
            self._set_status(
                "正在取消，请稍候…"
                if self._execution_cancel_requested
                else build_running_status(self.document_path()),
                "info",
            )
            self.summary_changed.emit()
            return

        document_path = str(self.document_path() or "").strip()
        execution_scene = self.execution_scene()
        selection = self.execution_material_selection()
        decision = material_execution_gate(selection, self._material_issues)
        self._material_preview.set_projection(
            build_quick_material_preview_projection(
                execution_scene,
                selection,
                preview_snapshot=self._material_preview_snapshot,
                gate_decision=decision,
                issues=self._material_issues,
            )
        )
        if not self._include_shared_chrome:
            self.summary_changed.emit()
            return
        self._execution_cancel_btn.setVisible(False)
        show_repair = bool(
            document_path
            and self._material_issues
            and decision.primary_action is not None
        )
        self._set_material_repair_visible(
            show_repair,
            list(material_issue_lines(self._material_issues)),
        )
        self._object_preflight_cancel_btn.setVisible(False)

        if not document_path:
            self._execute_btn.setText("选择文档并生成")
            self._execute_btn.setEnabled(True)
            self._set_status("请选择或拖入输入文档", "hint")
        elif not decision.can_run:
            self._execute_btn.setText("生成文档")
            self._execute_btn.setEnabled(False)
            self._set_status("无法生成：缺少必需资料", "error")
        elif decision.requires_confirmation:
            self._execute_btn.setText("确认并生成")
            self._execute_btn.setEnabled(True)
            self._set_status("生成前需确认资料缺口", "warning")
        elif decision.warning_reasons:
            self._execute_btn.setText("生成文档")
            self._execute_btn.setEnabled(True)
            self._set_status("可生成；部分信息将使用默认值", "warning")
        else:
            self._execute_btn.setText("生成文档")
            self._execute_btn.setEnabled(True)
            self._set_status("可生成", "success")

        if show_repair:
            self._material_repair_btn.setText(
                "去补齐"
                if not decision.can_run
                else "补充信息（可选）"
            )
        self._exec_status_label.setToolTip(
            "\n".join(
                [
                    *decision.blocking_reasons,
                    *decision.confirmation_reasons,
                    *decision.warning_reasons,
                ]
            )
        )
        self.summary_changed.emit()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setSpacing(t.template_detail_section_gap)
        self.setStyleSheet(build_button_stylesheet(t))
        self._apply_source_and_selector_theme(t)
        self._apply_output_theme(t)
        self._apply_execution_action_theme(t)
        self._apply_execution_feedback_theme(t)
        self._emit_summary_changed()

    def _apply_source_and_selector_theme(self, t) -> None:
        for lbl in self.findChildren(QLabel, "scene_tpl_label"):
            lbl.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.text_secondary}; background: transparent;"
            )
        if hasattr(self, "_exam_source_summary"):
            self._exam_source_summary.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_hint}; "
                f"background: transparent;"
            )
        for lbl in self.findChildren(QLabel, "wb_exam_source_key"):
            lbl.setStyleSheet(
                f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.text_secondary}; background: transparent;"
            )
        for lbl in self.findChildren(QLabel, "wb_exam_source_value"):
            lbl.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_primary}; "
                f"background: transparent;"
            )
        if hasattr(self, "_floating_fields_progress"):
            self._set_floating_fields_progress(0, 0)
        if hasattr(self, "_scene_icon_label"):
            self._scene_icon_label.setPixmap(
                get_icon("mountain-snow", 16, t.text_hint).pixmap(16, 16)
            )
        if hasattr(self, "_tpl_icon_label"):
            self._tpl_icon_label.setPixmap(
                get_icon("scroll-text", 16, t.text_hint).pixmap(16, 16)
            )

    def _apply_output_theme(self, t) -> None:
        if hasattr(self, "_output_browse_btn"):
            self._output_browse_btn.setStyleSheet(
                f"QPushButton {{ font-size: {t.font_size_md}px; color: {t.text_secondary}; "
                f"border: 1px solid {t.border}; border-radius: {t.radius_sm}px; "
                f"padding: 6px 12px; background: {t.bg_card}; text-align: left; }}"
                f"QPushButton:hover {{ border-color: {t.primary}; color: {t.primary}; }}"
            )
            if self._custom_output_dir:
                choose_directory = path_action_presentation(
                    PathAction.CHOOSE_DIRECTORY
                )
                self._output_browse_btn.setIcon(
                    get_icon(choose_directory.icon_name, 16, t.icon_primary)
                )
