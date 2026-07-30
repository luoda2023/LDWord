"""
scene_panel — 方案配置面板（Master-Detail 架构）

与模板面板同构：左侧导航卡片 + 右侧可切换详情面板。
信息分层:
  Top:    方案选择与方案概览
  Groups: 方案入口 / 规则 / 资料包填充
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

from src.config import library as config_library
from src.config.default_delivery_identity import project_default_delivery_identity
from src.config.master_library import OFFICIAL_USER_MASTER_DIR
from src.config.scene import (
    ContentVisibilityRule,
    DeliveryPreset,
    ExamPaperConfig,
    SceneWorkspace,
    coerce_exam_paper_config,
)
from src.config.scene_identity import allocate_scene_id, safe_scene_file_stem
from src.config.feature_configs import OutputConfig
from src.qt_api import (
    QButtonGroup,
    QCheckBox,
    QDesktopServices,
    QFileSystemWatcher,
    QFrame,
    QHBoxLayout,
    QLabel,
    QKeySequence,
    QPushButton,
    QSizePolicy,
    QShortcut,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui import (
    DetailPaneController,
    FlowLayout,
    LibraryActionRow,
    MasterDetailShell,
    NavigationCard,
    ThemedRadioButton,
)
from src.shared.ui.card import Card
from src.shared.ui.dialogs import confirm, input_text
from src.shared.ui.layout_sync import (
    refresh_layout_chain,
    refresh_layout_chain_later,
)
from src.shared.ui.navigation_highlight import NavigationHighlighter
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGrid
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toast import Toast
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.adapters.field_display_names import (
    field_display_context,
    field_display_name,
    navigation_issue_hint,
)
from src.ui.adapters.config_selector_models import (
    plan_combo_label,
    plan_display_label,
    plan_selector_descriptors,
    template_display_label,
)
from src.ui.base_panel import BasePanel
from src.ui.bridge import navigation_intent_value
from src.config.library import (
    default_scene_entry,
    default_scene_descriptor,
    get_scene_entry,
    load_scene_from_library,
    load_template_from_library,
)
from src.config.template import TemplateConfig
from src.ui.panels.scene_product_summary_projection import (
    FAILURE_POLICY_LABELS,
    PRESERVATION_MODE_LABELS,
    build_compliance_summary_items,
    recommended_object_preflight_targets_for_scene,
)
from src.ui.panels.scene_card_definitions import (
    CARD_DEFINITIONS,
    FORMAT_TEMPLATE_CARDS,
    INPUT_MATERIAL_CARDS,
    NAV_SECTION_CARD_GROUPS,
)
from src.ui.panels.scene_navigation_projection import (
    build_scene_navigation_card_snapshots,
    default_delivery_preset,
    _normalise_scene_detail_card_id,
)
from src.ui.panels.scene_state_projection import (
    builtin_scene_id_set as _builtin_scene_id_set,
    is_scene_selector_group as _is_scene_selector_group,
    scene_is_exam as _scene_is_exam,
    scene_should_show_content_card as _scene_should_show_content_card,
)
from src.config.scene_surface_registry import (
    scene_uses_official_document_surface as _scene_uses_official_document_surface,
    scene_uses_plan_preview_surface as _scene_uses_plan_preview_surface,
)
from src.ui.panels.scene_delivery_helpers import (
    _scene_current_template_id,
    _template_label_with_id,
)
from src.ui.panels.scene_content_detail import _ContentDetail
from src.ui.panels.scene_detail_base import _SimpleFormDetail
from src.ui.panels.scene_detail_support import (
    _apply_template_button_contract,
    _populate_combo,
    _set_combo_by_data,
)
from src.ui.panels.scene_exam_detail import (
    ExamPaperDetail,
    ensure_exam_paper_config,
)
from src.ui.panels.scene_output_detail import _OutputDetail
from src.ui.panels.scene_session_coordinator import (
    SCENE_PENDING_CANCEL,
    SCENE_PENDING_DISCARD,
    SCENE_PENDING_SAVE,
    SceneProjectionCallbacks,
    SceneSessionCoordinator,
)
from src.ui.panels.scene_scope_sections import DocumentScopeSection
from src.ui.panels.scene_overview_projection import (
    SceneOverviewRowSpec,
    SceneRunStepSpec,
    build_scene_overview_spec,
)
from src.ui.panels.template_navigation_context import (
    build_template_navigation_context,
)
from src.shared.engine.object_preflight import OBJECT_PREFLIGHT_SCAN_TARGETS
from src.shared.ui.base_dialog import BaseDialog


_SCENE_TEMPLATE_UNSET = object()






ALIGNMENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "左对齐"),
    ("center", "居中"),
    ("right", "右对齐"),
    ("justify", "两端对齐"),
)

FORMULA_OUTPUT_MODE_LABELS: dict[str, str] = {
    "word_native": "Word 原生公式",
    "image_fallback": "图片降级",
    "keep_source": "保留原文",
}

FORMULA_LOW_CONFIDENCE_LABELS: dict[str, str] = {
    "skip_and_mark": "跳过并标记",
    "image_fallback": "图片降级",
    "manual_review": "人工复核",
}


def _exam_student_delivery_preset() -> DeliveryPreset:
    preset = DeliveryPreset(
        preset_id="student",
        label="学生卷",
        target_template_id="",
        artifacts=OutputConfig(final_docx=True),
    )
    preset.content_visibility_rules = [
        ContentVisibilityRule(
            rule_id="hide_answers",
            label="隐藏答案与解析",
            selector_type="marker_block",
            selector="answer",
            action="remove",
        ),
        ContentVisibilityRule(
            rule_id="hide_explanations",
            label="隐藏解析",
            selector_type="marker_block",
            selector="explanation",
            action="remove",
        ),
    ]
    return preset

def _exam_answer_delivery_preset() -> DeliveryPreset:
    return DeliveryPreset(
        preset_id="answer_key",
        label="答案速查",
        target_template_id="",
        artifacts=OutputConfig(final_docx=True),
    )


def _is_plain_default_delivery_preset(preset: DeliveryPreset) -> bool:
    return (
        str(getattr(preset, "preset_id", "") or "").strip() == "final"
        and str(getattr(preset, "label", "") or "").strip() in {"", "Final DOCX"}
        and str(getattr(preset, "target_template_id", "") or "").strip() == ""
        and str(getattr(preset, "output_dir_template", "") or "").strip()
        == "{document_dir}/output"
        and str(getattr(preset, "filename_template", "") or "").strip()
        == "{stem}_{preset_id}"
        and not list(getattr(preset, "content_visibility_rules", []) or [])
        and not bool(getattr(preset, "include_structured_intermediate", False))
        and str(getattr(preset, "report_level", "") or "").strip() in {"", "summary"}
    )


def _sync_exam_answer_delivery(
    scene: SceneWorkspace,
    answer_policy: str,
    *,
    preserve_default: bool = False,
) -> None:
    answer_policy = str(answer_policy or "").strip() or "student_plus_answer"
    if answer_policy not in {"student_plus_answer", "student_only", "answer_only"}:
        answer_policy = "student_plus_answer"
    previous_default_id = str(
        getattr(scene, "default_delivery_preset_id", "") or ""
    ).strip()
    presets = [
        preset
        for preset in list(getattr(scene, "delivery_presets", []) or [])
        if not _is_plain_default_delivery_preset(preset)
    ]
    by_id = {
        str(getattr(preset, "preset_id", "") or "").strip(): preset
        for preset in presets
    }
    if answer_policy != "answer_only" and "student" not in by_id:
        presets.insert(0, _exam_student_delivery_preset())
    if answer_policy == "student_plus_answer":
        presets = [
            preset
            for preset in presets
            if str(getattr(preset, "preset_id", "") or "").strip() != "answer"
        ]
        by_id = {
            str(getattr(preset, "preset_id", "") or "").strip(): preset
            for preset in presets
        }
        if "answer_key" not in by_id:
            presets.append(_exam_answer_delivery_preset())
    elif answer_policy == "answer_only":
        presets = [
            preset
            for preset in presets
            if str(getattr(preset, "preset_id", "") or "").strip()
            not in {"student", "answer"}
        ]
        by_id = {
            str(getattr(preset, "preset_id", "") or "").strip(): preset
            for preset in presets
        }
        if "answer_key" not in by_id:
            presets.insert(0, _exam_answer_delivery_preset())
    else:
        presets = [
            preset
            for preset in presets
            if str(getattr(preset, "preset_id", "") or "").strip()
            not in {"answer", "answer_key"}
        ]
    if not presets:
        presets = [
            _exam_answer_delivery_preset()
            if answer_policy == "answer_only"
            else _exam_student_delivery_preset()
        ]
    scene.delivery_presets = presets
    preset_ids = {
        str(getattr(preset, "preset_id", "") or "").strip()
        for preset in scene.delivery_presets
    }
    if preserve_default and previous_default_id in preset_ids:
        scene.default_delivery_preset_id = previous_default_id
    else:
        scene.default_delivery_preset_id = (
            "answer_key" if answer_policy == "answer_only" else "student"
        )


_EXAM_ANSWER_POLICIES = frozenset(
    {"student_plus_answer", "student_only", "answer_only"}
)


def _project_exam_paper_config(
    scene: SceneWorkspace,
) -> tuple[ExamPaperConfig, str, str]:
    """Project exam controls without repairing the scene during display."""

    raw = getattr(scene, "exam_paper", None)
    projected = coerce_exam_paper_config(raw)
    if raw is None:
        return projected, "missing", ""
    if not isinstance(raw, ExamPaperConfig):
        return projected, "invalid", ""
    raw_policy = str(getattr(raw, "answer_policy", "") or "").strip()
    if raw_policy not in _EXAM_ANSWER_POLICIES:
        return projected, "invalid", raw_policy
    return projected, "ok", raw_policy


PREFLIGHT_TARGET_LABELS: dict[str, str] = {
    "ole_objects": "OLE 对象",
    "embedded_workbooks": "嵌入表格",
    "embedded_packages": "嵌入包",
    "visio_drawings": "Visio",
    "macros": "宏",
    "tracked_changes": "修订",
    "comments": "批注",
    "textboxes": "文本框",
    "content_controls": "内容控件",
    "fields": "域",
}


def _apply_desc_theme(widget: QWidget, t, obj_name: str = "scn_form_desc") -> None:
    for w in widget.findChildren(QLabel, obj_name):
        w.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")






class _SceneOverviewSettingRow(QWidget):
    """Readable scene setting row with a direct jump to its detail card."""

    navigate_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_card_id = "scn_overview"
        self._secondary_target_card_id = ""
        self._icon_name = "circle"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self._icon = QLabel(self)
        self._icon.setFixedSize(18, 18)
        layout.addWidget(self._icon, 0, Qt.AlignTop)

        text_wrap = QWidget(self)
        text_lay = QVBoxLayout(text_wrap)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(2)

        header = QWidget(text_wrap)
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(8)
        self._label = QLabel("", header)
        self._status = QLabel("", header)
        header_lay.addWidget(self._label)
        header_lay.addWidget(self._status)
        header_lay.addStretch(1)
        text_lay.addWidget(header)

        self._summary = QLabel("", text_wrap)
        self._summary.setWordWrap(True)
        text_lay.addWidget(self._summary)
        layout.addWidget(text_wrap, 1)

        self._actions_wrap = QWidget(self)
        actions_lay = QVBoxLayout(self._actions_wrap)
        actions_lay.setContentsMargins(0, 0, 0, 0)
        actions_lay.setSpacing(6)

        self._jump_btn = QPushButton("编辑", self._actions_wrap)
        self._jump_btn.clicked.connect(
            lambda: self.navigate_requested.emit(self._target_card_id)
        )
        actions_lay.addWidget(self._jump_btn)

        self._secondary_jump_btn = QPushButton("", self._actions_wrap)
        self._secondary_jump_btn.clicked.connect(
            lambda: self.navigate_requested.emit(self._secondary_target_card_id)
        )
        self._secondary_jump_btn.setVisible(False)
        actions_lay.addWidget(self._secondary_jump_btn)
        actions_lay.addStretch(1)
        layout.addWidget(self._actions_wrap, 0, Qt.AlignTop)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_spec(self, spec: SceneOverviewRowSpec) -> None:
        self._target_card_id = spec.target_card_id
        self._secondary_target_card_id = spec.secondary_target_card_id
        self._icon_name = spec.icon_name
        self._label.setText(spec.label)
        self._summary.setText(spec.summary)
        self._status.setText(spec.status)
        self._jump_btn.setText(
            spec.action_label
            or (
                "查看"
                if spec.target_card_id == "scn_overview"
                or spec.target_card_id.startswith("tpl_")
                else "编辑"
            )
        )
        self._jump_btn.setVisible(bool(spec.target_card_id))
        self._secondary_jump_btn.setText(spec.secondary_action_label)
        self._secondary_jump_btn.setVisible(
            bool(spec.secondary_target_card_id and spec.secondary_action_label)
        )
        self._actions_wrap.setVisible(
            not self._jump_btn.isHidden() or not self._secondary_jump_btn.isHidden()
        )
        self._apply_theme()

    def summary_text(self) -> str:
        return self._summary.text()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._label.setStyleSheet(
            f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.text_primary};"
        )
        self._summary.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._status.setStyleSheet(
            f"font-size: {t.font_size_sm - 1}px; color: {t.primary}; "
            f"background: {t.info_bg}; border-radius: {t.radius_sm}px; padding: 1px 6px;"
        )
        try:
            from src.shared.ui.icons.catalog import get_icon

            self._icon.setPixmap(
                get_icon(self._icon_name, size=16, color=t.text_hint).pixmap(16, 16)
            )
            self._icon.setText("")
        except Exception:
            self._icon.setText("•")
        _apply_template_button_contract(
            (self._jump_btn, "secondary"),
            (self._secondary_jump_btn, "secondary"),
        )


class _SceneOverviewRunStepRow(QWidget):
    """Compact one-step row for the scene overview run preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon_name = "circle"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)

        self._icon = QLabel(self)
        self._icon.setFixedSize(18, 18)
        layout.addWidget(self._icon, 0, Qt.AlignTop)

        text_wrap = QWidget(self)
        text_lay = QVBoxLayout(text_wrap)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(1)

        self._title = QLabel("", text_wrap)
        self._detail = QLabel("", text_wrap)
        self._detail.setWordWrap(True)
        text_lay.addWidget(self._title)
        text_lay.addWidget(self._detail)
        layout.addWidget(text_wrap, 1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_step(self, step: SceneRunStepSpec) -> None:
        self._icon_name = step.icon_name
        self._title.setText(step.title)
        self._detail.setText(step.detail)
        self._apply_theme()

    def step_text(self) -> str:
        return f"{self._title.text()} {self._detail.text()}".strip()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._title.setStyleSheet(
            f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.text_primary};"
        )
        self._detail.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        try:
            from src.shared.ui.icons.catalog import get_icon

            self._icon.setPixmap(
                get_icon(self._icon_name, size=16, color=t.text_hint).pixmap(16, 16)
            )
            self._icon.setText("")
        except Exception:
            self._icon.setText("•")


# ── 方案概览 ────────────────────────────────────────


class _SceneOverviewDetail(QWidget):
    """Layer 1: Scene selector + template binding + summary."""

    scene_changed = Signal(int)
    scene_edited = Signal()
    navigate_requested = Signal(str)
    execute_requested = Signal()
    new_scene_requested = Signal()
    duplicate_scene_requested = Signal()
    rename_scene_requested = Signal()
    open_scene_folder_requested = Signal()
    delete_scene_requested = Signal()
    selector_open_requested = Signal()

    def __init__(
        self, scene_descriptors: list, *, work_mode_id: str = "custom", parent=None
    ):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._is_syncing = False
        self._work_mode_id = str(work_mode_id or "").strip() or "custom"
        self._scene_descriptors = list(scene_descriptors)
        self._template_preview_action = ""
        self._overview_title_labels: list[QLabel] = []
        self._overview_header_icons: dict[str, QLabel] = {}
        self._overview_separators: list[QFrame] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        task_card = Card(parent=self)
        self._scene_card = task_card
        task_card.add_widget(
            self._make_scene_overview_header("mountain-snow", "当前方案")
        )

        # Scene selector
        self._combo = StyledComboBox(self)
        self._combo.set_full_width_mode(True)
        self._combo_index_by_scene_id: dict[str, int] = {}
        self._populate_scene_combo()
        self._combo.currentIndexChanged.connect(self.scene_changed.emit)
        self._combo.popup_about_to_show.connect(self.selector_open_requested.emit)
        task_card.add_widget(self._combo)

        self._scene_action_row = LibraryActionRow(
            task_card,
            object_name="scn_overview_scene_action_row",
        )
        self._new_scene_btn = self._scene_action_row.add_action(
            "new",
            "新建方案",
            object_name="scn_overview_new_scene_btn",
            icon_name="plus",
            callback=self.new_scene_requested.emit,
        )
        # Saving remains available through Ctrl+S and dirty-transition guards.
        # Keep it out of this first-screen row: built-in ownership is represented
        # by the explicit "创建副本" action, not a second save-as-copy action.
        self._duplicate_scene_btn = self._scene_action_row.add_action(
            "duplicate",
            "创建副本",
            object_name="scn_overview_duplicate_scene_btn",
            icon_name="copy",
            callback=self.duplicate_scene_requested.emit,
        )
        self._rename_scene_btn = self._scene_action_row.add_action(
            "rename",
            "重命名方案",
            object_name="scn_overview_rename_scene_btn",
            icon_name="pencil-line",
            callback=self.rename_scene_requested.emit,
        )
        self._open_scene_folder_btn = self._scene_action_row.add_action(
            "open_folder",
            "打开方案文件夹",
            object_name="scn_overview_open_scene_folder_btn",
            icon_name="folder-open",
            callback=self.open_scene_folder_requested.emit,
        )
        self._delete_scene_btn = self._scene_action_row.add_action(
            "delete",
            "删除方案",
            object_name="scn_overview_delete_scene_btn",
            icon_name="trash-2",
            variant="ghost-danger",
            side="right",
            callback=self.delete_scene_requested.emit,
        )
        task_card.add_widget(self._scene_action_row)

        # Description
        self._desc = QLabel("", self)
        self._desc.setObjectName("scn_desc")
        self._desc.setWordWrap(True)
        self._desc.setVisible(False)
        task_card.add_widget(self._desc)

        self._task_title = QLabel("", self)
        self._task_title.setObjectName("scn_task_title")
        self._task_title.setWordWrap(True)
        self._task_title.setVisible(False)
        task_card.add_widget(self._task_title)

        self._task_meta = QLabel("", self)
        self._task_meta.setObjectName("scn_task_meta")
        self._task_meta.setWordWrap(True)
        self._task_meta.setVisible(False)
        task_card.add_widget(self._task_meta)

        self._task_suitable = QLabel("", self)
        self._task_suitable.setObjectName("scn_task_suitable")
        self._task_suitable.setWordWrap(True)
        self._task_suitable.setVisible(False)
        task_card.add_widget(self._task_suitable)

        self._task_boundary = QLabel("", self)
        self._task_boundary.setObjectName("scn_task_boundary")
        self._task_boundary.setWordWrap(True)
        self._task_boundary.setVisible(False)
        task_card.add_widget(self._task_boundary)

        self._summary = QLabel("", self)
        self._summary.setObjectName("scn_summary")
        self._summary.setWordWrap(True)
        # Counts are visible in the key-setting rows; keep this as legacy state only.
        self._summary.setVisible(False)
        task_card.add_widget(self._summary)

        layout.addWidget(task_card)

        self._run_preview_card = Card(parent=self)
        self._run_preview_card.add_widget(
            self._make_scene_overview_header("play-circle", "执行预览")
        )
        strategy_row = QWidget(self._run_preview_card)
        s_lay = QHBoxLayout(strategy_row)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(8)
        self._strategy_group = QButtonGroup(self)
        self._strategy_group.setExclusive(True)
        self._rebuild_radio = ThemedRadioButton("重建编号", strategy_row)
        self._preserve_radio = ThemedRadioButton("保留原编号", strategy_row)
        self._strategy_group.addButton(self._rebuild_radio, 0)
        self._strategy_group.addButton(self._preserve_radio, 1)
        self._rebuild_radio.setChecked(True)
        self._rebuild_radio.toggled.connect(self._on_strategy_changed)
        s_lay.addWidget(self._rebuild_radio)
        s_lay.addWidget(self._preserve_radio)
        s_lay.addStretch(1)
        self._run_preview_card.add_widget(
            template_form_row("编号策略", strategy_row, parent=self._run_preview_card)
        )
        self._run_step_rows = [
            _SceneOverviewRunStepRow(parent=self._run_preview_card) for _ in range(5)
        ]
        for row in self._run_step_rows:
            self._run_preview_card.add_widget(row)
        self._run_steps_label = QLabel("", self)
        self._run_steps_label.setObjectName("scn_run_steps")
        self._run_steps_label.setWordWrap(True)
        self._run_steps_label.setVisible(False)
        self._run_preview_card.add_widget(self._run_steps_label)

        action_row = QWidget(self._run_preview_card)
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 4, 0, 0)
        action_layout.setSpacing(8)
        action_layout.addStretch(1)
        self._execute_btn = QPushButton("去执行", action_row)
        self._execute_btn.setObjectName("scn_go_execute_btn")
        self._execute_btn.setCursor(Qt.PointingHandCursor)
        self._execute_btn.clicked.connect(self.execute_requested.emit)
        action_layout.addWidget(self._execute_btn)
        self._run_preview_card.add_widget(action_row)

        self._settings_card = Card(parent=self)
        self._settings_card.add_widget(
            self._make_scene_overview_header("sliders-horizontal", "方案规则")
        )
        self._settings_card.add_widget(self._make_scene_overview_separator())
        self._setting_rows: dict[str, QWidget] = {}
        for row_key in (
            "exam_blank_style",
            "exam_runtime_fields",
            "materials",
            "scope",
            "reference_format",
            "delivery",
        ):
            row = _SceneOverviewSettingRow(parent=self._settings_card)
            row.navigate_requested.connect(self.navigate_requested.emit)
            self._setting_rows[row_key] = row
            self._settings_card.add_widget(row)
        layout.addWidget(self._settings_card)
        layout.addWidget(self._run_preview_card)
        layout.addStretch(1)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def take_scene_card(self) -> QWidget:
        """Detach the real plan selector so a specialized preview can host it."""
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.removeWidget(self._scene_card)
        self._scene_card.setParent(None)
        return self._scene_card

    def restore_scene_card(self, card: QWidget | None = None) -> None:
        target = card or self._scene_card
        layout = self.layout()
        if not isinstance(layout, QVBoxLayout):
            return
        target.setParent(self)
        layout.insertWidget(0, target)
        target.setVisible(True)

    def _populate_scene_combo(self, current_scene_id: str = "") -> None:
        self._combo.clear()
        self._combo_index_by_scene_id = {}
        user_descriptors = [
            descriptor
            for descriptor in self._scene_descriptors
            if str(getattr(descriptor, "source_type", "") or "").strip() != "builtin"
        ]
        builtin_descriptors = [
            descriptor
            for descriptor in self._scene_descriptors
            if str(getattr(descriptor, "source_type", "") or "").strip() == "builtin"
        ]

        for descriptor in user_descriptors:
            self._add_scene_descriptor_item(descriptor)
        for descriptor in builtin_descriptors:
            self._add_scene_descriptor_item(descriptor)

        if not self._set_scene_combo_current_id(current_scene_id):
            first_index = self._first_available_scene_combo_index()
            if first_index >= 0:
                self._combo.setCurrentIndex(first_index)

    def _add_scene_descriptor_item(self, descriptor) -> None:
        scene_id = str(getattr(descriptor, "config_id", "") or "").strip()
        if not scene_id:
            return
        source_type = str(getattr(descriptor, "source_type", "") or "").strip()
        item_index = self._combo.add_badged_item(
            plan_combo_label(descriptor, include_source_prefix=False),
            scene_id,
            badge_text="内置" if source_type == "builtin" else "自定",
            badge_kind="builtin" if source_type == "builtin" else "user",
        )
        self._combo_index_by_scene_id[scene_id] = item_index
        if descriptor.load_error:
            self._combo.setItemData(item_index, descriptor.load_error, Qt.ToolTipRole)

    def _set_scene_combo_current_id(self, scene_id: str) -> bool:
        target_id = str(scene_id or "").strip()
        if not target_id:
            return False
        index = self._combo_index_by_scene_id.get(target_id, -1)
        if index < 0:
            return False
        self._combo.setCurrentIndex(index)
        return True

    def _first_available_scene_combo_index(self) -> int:
        descriptors_by_id = {
            str(getattr(descriptor, "config_id", "") or "").strip(): descriptor
            for descriptor in self._scene_descriptors
        }
        for scene_id, index in self._combo_index_by_scene_id.items():
            descriptor = descriptors_by_id.get(scene_id)
            if descriptor is not None and not getattr(descriptor, "load_error", ""):
                return index
        for index in self._combo_index_by_scene_id.values():
            return index
        return -1

    def set_scene_options(
        self,
        scene_descriptors: list,
        *,
        current_scene_id: str = "",
        work_mode_id: str = "",
    ) -> None:
        if work_mode_id:
            self._work_mode_id = str(work_mode_id or "").strip() or "custom"
        self._scene_descriptors = list(scene_descriptors)
        target_id = str(current_scene_id or "").strip()
        self._combo.blockSignals(True)
        try:
            self._populate_scene_combo(target_id)
        finally:
            self._combo.blockSignals(False)

    def set_scene_action_state(
        self,
        *,
        can_rename: bool,
        can_delete: bool,
        rename_tooltip: str = "",
        delete_tooltip: str = "",
        folder_tooltip: str = "",
    ) -> None:
        self._rename_scene_btn.setEnabled(can_rename)
        self._delete_scene_btn.setEnabled(can_delete)
        self._rename_scene_btn.setToolTip(rename_tooltip)
        self._delete_scene_btn.setToolTip(delete_tooltip)
        self._open_scene_folder_btn.setToolTip(folder_tooltip)

    def _make_scene_overview_header(self, icon_name: str, title: str) -> QWidget:
        header = QWidget(self)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(6)

        icon = QLabel(header)
        icon.setFixedSize(18, 18)
        layout.addWidget(icon)

        title_label = QLabel(title, header)
        self._overview_title_labels.append(title_label)
        layout.addWidget(title_label)
        layout.addStretch(1)

        self._overview_header_icons[icon_name] = icon
        return header

    def _make_scene_overview_separator(self) -> QFrame:
        separator = QFrame(self)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        self._overview_separators.append(separator)
        return separator

    def set_scene(
        self,
        scene: SceneWorkspace,
        *,
        template=None,
        template_preview_action: str = "",
    ) -> None:
        self._current_scene = scene
        self._current_template = template
        self._template_preview_action = str(template_preview_action or "").strip()
        self._desc.setText(scene.description or "")
        self._combo.blockSignals(True)
        try:
            if not self._set_scene_combo_current_id(scene.scene_id):
                scene_id = str(scene.scene_id or "custom").strip() or "custom"
                label = str(scene.name or scene_id).strip() or scene_id
                self._combo.addItem(label, scene_id)
                index = self._combo.count() - 1
                self._combo_index_by_scene_id[scene_id] = index
                self._combo.setCurrentIndex(index)
        finally:
            self._combo.blockSignals(False)

        # Strategy controls emit toggled while projecting a newly loaded scene.
        # Treat projection as read-only so it cannot mark the scene dirty or
        # republish its bound template during mode activation.
        self._is_syncing = True
        try:
            self._rebuild_radio.setChecked(scene.strict_mode)
            self._preserve_radio.setChecked(not scene.strict_mode)
        finally:
            self._is_syncing = False

        # Summary
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        if self._current_scene is None:
            return
        scene = self._current_scene
        spec = build_scene_overview_spec(
            scene,
            template=getattr(self, "_current_template", None),
            template_label=self._current_template_label(),
            template_preview_action=self._template_preview_action,
        )
        self._task_title.setText(spec.task.title)
        self._task_meta.setText(
            f"模板：{spec.task.template_label} · 编号：{spec.task.numbering_label}"
        )
        self._task_suitable.setText(spec.task.suitable_for)
        self._task_boundary.setText(spec.task.boundary_note)
        scope_row = next((row for row in spec.key_settings if row.key == "scope"), None)
        scope_summary = scope_row.summary if scope_row is not None else "处理区域已配置"
        self._summary.setText(scope_summary)
        self._run_steps_label.setText(self._format_run_preview_steps(spec.run_steps))
        self._sync_run_preview_steps(spec.run_steps)
        for row in self._setting_rows.values():
            row.setVisible(False)
        for row_spec in spec.key_settings:
            row = self._setting_rows.get(row_spec.key)
            if row is not None:
                row.set_spec(row_spec)
                row.setVisible(True)

    def _current_template_label(self) -> str:
        if self._current_scene is None:
            return ""
        template_id = str(
            self._current_scene.template_id
            or ""
        ).strip()
        label = template_display_label(
            template_id,
            mode_id=self._work_mode_id,
            fallback="",
        )
        if label and label != template_id:
            return label
        current_template = getattr(self, "_current_template", None)
        template_name = str(getattr(current_template, "name", "") or "").strip()
        if template_name:
            return template_name
        return label or str(template_id).strip()

    def _format_run_preview_steps(self, steps: tuple[SceneRunStepSpec, ...]) -> str:
        return "\n".join(
            f"{index}. {step.title}：{step.detail}"
            for index, step in enumerate(steps, start=1)
        )

    def _sync_run_preview_steps(self, steps: tuple[SceneRunStepSpec, ...]) -> None:
        for index, row in enumerate(self._run_step_rows):
            if index < len(steps):
                row.set_step(steps[index])
                row.setVisible(True)
            else:
                row.setVisible(False)

    def set_template_preview_action(self, action: str) -> None:
        self._template_preview_action = str(action or "").strip()
        self._refresh_summary()

    def _on_strategy_changed(self, _checked: bool) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.strict_mode = self._rebuild_radio.isChecked()
        self._refresh_summary()
        self.scene_edited.emit()

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        if self.layout() is not None:
            self.layout().setSpacing(t.template_detail_section_gap)
        title_ss = (
            f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.primary}; background: transparent;"
        )
        for label in self._overview_title_labels:
            label.setStyleSheet(title_ss)
        for separator in self._overview_separators:
            separator.setStyleSheet(f"background: {t.border_light}; max-height: 1px;")
        self._desc.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._task_title.setStyleSheet(
            f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.text_primary};"
        )
        self._task_meta.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.primary};"
        )
        self._task_suitable.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_primary};"
        )
        self._task_boundary.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._summary.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )
        self._run_steps_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_primary}; line-height: 145%;"
        )
        self._scene_action_row.apply_theme()
        _apply_template_button_contract((self._execute_btn, "primary"))
        try:
            from src.shared.ui.icons.catalog import get_icon

            for icon_name, label in self._overview_header_icons.items():
                label.setPixmap(get_icon(icon_name, 18, t.primary).pixmap(18, 18))
            self._execute_btn.setIcon(get_icon("play-circle", 16, t.text_on_primary))
        except Exception:
            pass


# ── 处理范围 ────────────────────────────────────────


class _ScopeDetail(QWidget):
    """Plan-owned logical document processing scope."""

    scope_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._is_syncing = False
        self._navigation_highlighter = NavigationHighlighter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._document_scope_section = DocumentScopeSection(self)
        self._document_scope_section.scope_changed.connect(
            self._on_scope_value_changed
        )
        self._scope_card = self._document_scope_section.card
        layout.addWidget(self._document_scope_section)
        layout.addStretch(1)

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if not target:
            return False

        if target in {
            "scene.document_scope.mode",
            "scene.document_scope.selected_roles",
        }:
            self._highlight_navigation_widget(
                self._document_scope_section.mode_control,
                target,
            )
            return True
        return False

    def _highlight_navigation_widget(self, widget: QWidget, label: str) -> None:
        self._navigation_highlighter.highlight(
            widget,
            label,
            display_label=(
                field_display_context(label).label_with_group()
                or field_display_name(label)
            ),
        )

    def set_scene(self, scene: SceneWorkspace, template=None) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._document_scope_section.set_mode_id(scene.mode_id)
            self._document_scope_section.set_scope(
                scene.document_scope.mode,
                scene.document_scope.selected_roles,
            )
            refresh_layout_chain(self)
            refresh_layout_chain_later(self)
        finally:
            self._is_syncing = False

    def _on_scope_value_changed(self, mode: str, selected_roles) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.document_scope.mode = str(mode or "").strip() or "all"
        self._current_scene.document_scope.selected_roles = list(selected_roles or ())
        self._current_scene.document_scope.__post_init__()
        self.scope_changed.emit()






# ── 方案规则 ────────────────────────────────────────


class _SceneOutputRulesCard(QWidget):
    """Compact generated-result card shown inside scene rules."""

    scene_edited = Signal()

    def __init__(self, output_detail: QWidget, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._output_detail = output_detail
        self._mode_id = ""
        self._expanded = False
        self._is_syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._card = Card(parent=self)
        self._card.set_header("生成结果", icon_name="folder-output")

        self._delivery_row = QWidget(self._card)
        delivery_layout = QHBoxLayout(self._delivery_row)
        delivery_layout.setContentsMargins(0, 0, 0, 0)
        delivery_layout.setSpacing(12)
        self._delivery_label = QLabel("交付内容", self._delivery_row)
        self._delivery_label.setObjectName("scn_output_delivery_label")
        self._delivery_choices = QWidget(self._delivery_row)
        self._delivery_choices.setObjectName("scn_output_delivery_choices")
        self._delivery_choices.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._delivery_flow = FlowLayout(
            self._delivery_choices, h_spacing=18, v_spacing=8
        )
        self._delivery_flow.setContentsMargins(0, 0, 0, 0)
        delivery_layout.addWidget(self._delivery_label, 0, Qt.AlignTop)
        delivery_layout.addWidget(self._delivery_choices, 1)
        self._card.add_widget(self._delivery_row)

        self._general_checks: dict[str, QCheckBox] = {}
        for key, label, tooltip in (
            ("final_docx", "最终 Word", "生成排版后的 Word 文件。"),
            (
                "review_pdf",
                "审阅 PDF",
                "从内部审阅稿生成 PDF；渲染器不可用时保留正式 Word 并提示。",
            ),
            ("compare_docx", "对比 Word", "生成便于核对修改痕迹的对比稿。"),
            ("report", "处理报告", "记录执行提醒和处理结果。"),
            ("material_manifest", "资料清单", "输出本次使用资料的清单。"),
            ("material_package", "资料包", "打包本次交付关联资料。"),
        ):
            checkbox = QCheckBox(label, self._delivery_choices)
            checkbox.setObjectName(f"scn_output_choice_{key}")
            checkbox.setToolTip(tooltip)
            checkbox.setCursor(Qt.PointingHandCursor)
            checkbox.toggled.connect(self._on_general_choice_changed)
            self._general_checks[key] = checkbox
            self._delivery_flow.addWidget(checkbox)

        self._exam_student_check = QCheckBox("学生卷", self._delivery_choices)
        self._exam_student_check.setObjectName("scn_output_choice_exam_student")
        self._exam_student_check.setToolTip("试卷方案默认生成学生卷。")
        self._exam_student_check.setCursor(Qt.PointingHandCursor)
        self._exam_student_check.toggled.connect(self._on_exam_choice_changed)
        self._delivery_flow.addWidget(self._exam_student_check)

        self._exam_answer_check = QCheckBox("答案版", self._delivery_choices)
        self._exam_answer_check.setObjectName("scn_output_choice_exam_answer")
        self._exam_answer_check.setToolTip("勾选后同时生成答案速查。")
        self._exam_answer_check.setCursor(Qt.PointingHandCursor)
        self._exam_answer_check.toggled.connect(self._on_exam_choice_changed)
        self._delivery_flow.addWidget(self._exam_answer_check)

        layout.addWidget(self._card)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_scene(self, scene: SceneWorkspace, *, mode_id: str = "") -> None:
        self._current_scene = scene
        self._mode_id = str(mode_id or "").strip()
        self._sync_choices(scene)
        self._sync_output_detail_visibility()

    def _sync_choices(self, scene: SceneWorkspace) -> None:
        self._is_syncing = True
        try:
            is_exam = _scene_is_exam(scene, mode_id=self._mode_id)
            is_official = _scene_uses_official_document_surface(
                scene,
                mode_id=self._mode_id,
            )
            for key, checkbox in self._general_checks.items():
                checkbox.setVisible(
                    (not is_exam) and (key != "review_pdf" or is_official)
                )
            self._exam_student_check.setVisible(is_exam)
            self._exam_answer_check.setVisible(is_exam)

            if is_exam:
                config, status, raw_policy = _project_exam_paper_config(scene)
                enabled = status == "ok"
                self._set_delivery_projection_status(
                    status,
                    (
                        ""
                        if enabled
                        else (
                            "试卷配置缺失"
                            if status == "missing"
                            else f"答案版本策略无效：{raw_policy or '空'}"
                        )
                    ),
                )
                self._exam_student_check.setEnabled(enabled)
                self._exam_answer_check.setEnabled(enabled)
                self._exam_student_check.setChecked(
                    enabled and config.answer_policy != "answer_only"
                )
                self._exam_answer_check.setChecked(
                    enabled and config.answer_policy != "student_only"
                )
                return

            identity = project_default_delivery_identity(scene)
            enabled = identity.is_ok
            self._set_delivery_projection_status(
                identity.status,
                (
                    ""
                    if enabled
                    else (
                        f"默认交付引用无效：{identity.requested_id}"
                        if identity.status == "invalid"
                        else "未设置默认交付"
                    )
                ),
            )
            for checkbox in self._general_checks.values():
                checkbox.setEnabled(enabled)
            preset = identity.preset
            output = preset.artifacts if preset is not None else DeliveryPreset().artifacts
            self._general_checks["final_docx"].setChecked(bool(output.final_docx))
            self._general_checks["review_pdf"].setChecked(
                bool(getattr(output, "review_pdf", False))
            )
            self._general_checks["compare_docx"].setChecked(bool(output.compare_docx))
            self._general_checks["report"].setChecked(
                bool(output.report_json or output.report_markdown)
            )
            self._general_checks["material_manifest"].setChecked(
                bool(output.material_manifest)
            )
            self._general_checks["material_package"].setChecked(
                bool(output.material_package)
            )
        finally:
            self._is_syncing = False

    def _on_general_choice_changed(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        scene = self._current_scene
        preset = self._selected_delivery_preset(scene)
        if preset is None:
            return
        output = preset.artifacts
        output.final_docx = self._general_checks["final_docx"].isChecked()
        output.review_pdf = self._general_checks["review_pdf"].isChecked()
        output.compare_docx = self._general_checks["compare_docx"].isChecked()
        output.report_json = self._general_checks["report"].isChecked()
        output.report_markdown = self._general_checks["report"].isChecked()
        output.material_manifest = self._general_checks["material_manifest"].isChecked()
        output.material_package = self._general_checks["material_package"].isChecked()
        self.scene_edited.emit()

    def _on_exam_choice_changed(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        scene = self._current_scene
        _projected, status, _raw_policy = _project_exam_paper_config(scene)
        if status != "ok":
            return
        config = ensure_exam_paper_config(scene)
        student_checked = self._exam_student_check.isChecked()
        answer_checked = self._exam_answer_check.isChecked()
        if not student_checked and not answer_checked:
            self._is_syncing = True
            try:
                self._exam_student_check.setChecked(True)
            finally:
                self._is_syncing = False
            student_checked = True
        if student_checked and answer_checked:
            config.answer_policy = "student_plus_answer"
        elif answer_checked:
            config.answer_policy = "answer_only"
        else:
            config.answer_policy = "student_only"
        _sync_exam_answer_delivery(scene, config.answer_policy)
        self.scene_edited.emit()

    def _selected_delivery_preset(self, scene: SceneWorkspace):
        return project_default_delivery_identity(scene).preset

    def _set_delivery_projection_status(self, status: str, message: str) -> None:
        normalized_status = str(status or "invalid").strip() or "invalid"
        normalized_message = str(message or "").strip()
        self._delivery_label.setText(
            "交付内容"
            if normalized_status == "ok"
            else f"交付内容（{normalized_message or '配置不可用'}）"
        )
        self._delivery_label.setToolTip(normalized_message)
        self._delivery_row.setProperty(
            "deliveryProjectionStatus",
            normalized_status,
        )

    def expand(self) -> None:
        self._expanded = True
        self._sync_output_detail_visibility()

    def _sync_output_detail_visibility(self) -> None:
        self._output_detail.setVisible(self._expanded)
        refresh_layout_chain(self)
        refresh_layout_chain_later(self)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        if not hasattr(self, "_delivery_label"):
            return
        t = get_theme()
        self._delivery_label.setStyleSheet(
            f"font-size: {t.font_size_md}px; "
            f"font-weight: {t.font_weight_emphasis}; "
            f"color: {t.text_primary};"
        )
        checkbox_style = build_checkbox_stylesheet(t)
        for checkbox in (
            *self._general_checks.values(),
            self._exam_student_check,
            self._exam_answer_check,
        ):
            checkbox.setStyleSheet(checkbox_style)


class _SceneRulesDetail(QWidget):
    """Combined plan scope and delivery surface."""

    def __init__(
        self,
        scope: _ScopeDetail,
        output: QWidget,
        parent=None,
    ):
        super().__init__(parent)
        self._scope = scope
        self._output = output
        self._output_rules = _SceneOutputRulesCard(self._output, self)
        self._current_scene: SceneWorkspace | None = None
        self._mode_id = ""
        self._output_rules.scene_edited.connect(self._on_output_rules_edited)
        if hasattr(self._output, "scene_edited"):
            self._output.scene_edited.connect(self._refresh_output_rules)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._scope)
        layout.addWidget(self._output_rules)
        layout.addWidget(self._output)
        layout.addStretch(1)

    def set_scene(
        self,
        scene: SceneWorkspace,
        template: TemplateConfig | None = None,
        *,
        mode_id: str = "",
    ) -> None:
        self._current_scene = scene
        self._mode_id = str(mode_id or "").strip()
        uses_master_assembly = _scene_uses_plan_preview_surface(
            scene,
            mode_id=self._mode_id,
        )
        self._scope.set_scene(scene, template)
        self._scope.setVisible(not uses_master_assembly)
        if hasattr(self._output, "set_scene"):
            self._output.set_scene(scene)
        self._output_rules.set_scene(scene, mode_id=self._mode_id)
        refresh_layout_chain(self)
        refresh_layout_chain_later(self)

    def _refresh_output_rules(self) -> None:
        if self._current_scene is None:
            return
        self._output_rules.set_scene(
            self._current_scene,
            mode_id=self._mode_id,
        )

    def _on_output_rules_edited(self) -> None:
        if self._current_scene is not None and hasattr(self._output, "set_scene"):
            self._output.set_scene(self._current_scene)
        if hasattr(self._output, "scene_edited"):
            self._output.scene_edited.emit()
        else:
            self._refresh_output_rules()

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if self._is_output_target(target):
            return self.focus_output_navigation_field(target)
        return bool(
            not self._scope.isHidden()
            and self._scope.focus_navigation_field(target)
        )

    def focus_output_navigation_field(self, field_id: str = "") -> bool:
        target = str(field_id or "").strip()
        self._output_rules.expand()
        if hasattr(self._output, "focus_navigation_field"):
            return bool(
                self._output.focus_navigation_field(target or "default_delivery")
            )
        return True

    def _is_output_target(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if not target:
            return False
        if target in {
            "default_delivery",
            "preset_id",
            "preset_label",
            "label",
            "target_template",
            "target_template_id",
            "template_options",
            "output_dir",
            "output_dir_template",
            "filename",
            "filename_template",
            "visibility_selector_options",
            "visibility_selector",
            "visibility_rules",
            "final_docx",
            "compare_docx",
            "report_json",
            "report_markdown",
            "report_md",
            "material_manifest",
            "material_package",
        }:
            return True
        combo = getattr(self._output, "_default_delivery", None)
        if combo is not None:
            for index in range(combo.count()):
                if target == str(combo.itemData(index) or "").strip():
                    return True
        return bool(target.startswith(("output.", "delivery.", "delivery_presets.")))

    def apply_theme(self) -> None:
        for detail in (
            self._scope,
            self._output_rules,
            self._output,
        ):
            if hasattr(detail, "apply_theme"):
                detail.apply_theme()


# ── 风险检查 ──────────────────────────────────────


class _CleanupDetail(_SimpleFormDetail):
    """Detail pane for cleanup + validation options."""

    def __init__(self, parent=None):
        super().__init__(
            "风险检查", "scan", "编辑 Markdown 修复、对象风险和执行前校验选项。", parent
        )
        self._current_scene: SceneWorkspace | None = None

        self._compliance_summary = SummaryGrid(columns=3, parent=self._card)
        self._card.add_widget(self._compliance_summary)

        self._fix_breaks = ToggleSwitch(self, checked=True)
        self._fix_breaks.toggled_signal.connect(self._on_edited)
        rows = [template_form_row("段落修复", self._fix_breaks, parent=self._card)]

        self._remove_empty = ToggleSwitch(self, checked=True)
        self._remove_empty.toggled_signal.connect(self._on_edited)
        rows.append(
            template_form_row("空行清理", self._remove_empty, parent=self._card)
        )

        self._normalize_spaces = ToggleSwitch(self, checked=True)
        self._normalize_spaces.toggled_signal.connect(self._on_edited)
        rows.append(
            template_form_row("空格规范", self._normalize_spaces, parent=self._card)
        )

        self._validation_enabled = ToggleSwitch(self, checked=True)
        self._validation_enabled.toggled_signal.connect(self._on_edited)
        rows.append(
            template_form_row("执行前校验", self._validation_enabled, parent=self._card)
        )

        self._object_preflight_enabled = ToggleSwitch(self, checked=True)
        self._object_preflight_enabled.toggled_signal.connect(self._on_edited)
        rows.append(
            template_form_row(
                "对象预检", self._object_preflight_enabled, parent=self._card
            )
        )

        self._scan_target_checks: dict[str, QCheckBox] = {}
        self._scan_targets_widget = QWidget(self)
        self._scan_targets_flow = FlowLayout(
            self._scan_targets_widget,
            h_spacing=14,
            v_spacing=4,
        )
        self._scan_targets_flow.setContentsMargins(0, 4, 0, 0)
        for target in OBJECT_PREFLIGHT_SCAN_TARGETS:
            checkbox = QCheckBox(
                PREFLIGHT_TARGET_LABELS.get(target, target), self._scan_targets_widget
            )
            checkbox.setToolTip(target)
            checkbox.toggled.connect(self._on_edited)
            self._scan_target_checks[target] = checkbox
            self._scan_targets_flow.addWidget(checkbox)
        rows.append(
            template_form_row("扫描目标", self._scan_targets_widget, parent=self._card)
        )

        self._preservation_mode = StyledComboBox(self)
        _populate_combo(self._preservation_mode, PRESERVATION_MODE_LABELS)
        self._preservation_mode.currentIndexChanged.connect(self._on_edited)
        rows.append(
            template_form_row("保护模式", self._preservation_mode, parent=self._card)
        )

        self._skip_high_risk = ToggleSwitch(self, checked=True)
        self._skip_high_risk.toggled_signal.connect(self._on_edited)
        rows.append(
            template_form_row("高风险跳过", self._skip_high_risk, parent=self._card)
        )

        self._apply_family_preflight_btn = QPushButton("应用推荐目标", self)
        self._apply_family_preflight_btn.clicked.connect(
            self._apply_family_preflight_targets
        )
        rows.append(
            template_form_row(
                "方案族预检", self._apply_family_preflight_btn, parent=self._card
            )
        )

        self._compliance_failure = StyledComboBox(self)
        _populate_combo(self._compliance_failure, FAILURE_POLICY_LABELS)
        self._compliance_failure.currentIndexChanged.connect(self._on_edited)
        rows.append(
            template_form_row("失败策略", self._compliance_failure, parent=self._card)
        )

        self._report_level = StyledComboBox(self)
        _populate_combo(
            self._report_level,
            {
                "summary": "摘要",
                "detailed": "详细",
                "audit": "审计",
            },
        )
        self._report_level.currentIndexChanged.connect(self._on_edited)
        rows.append(
            template_form_row("报告粒度", self._report_level, parent=self._card)
        )
        self._add_form_stack(rows)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._fix_breaks.setChecked(
                getattr(scene.md_cleanup, "fix_paragraph_breaks", True)
            )
            self._remove_empty.setChecked(
                getattr(scene.md_cleanup, "remove_empty_paragraphs", True)
            )
            self._normalize_spaces.setChecked(
                getattr(scene.whitespace, "normalize_spaces", True)
            )
            self._validation_enabled.setChecked(
                scene.module_switches.get("validation", False)
            )
            preflight = scene.compliance_profile.object_preflight
            self._object_preflight_enabled.setChecked(preflight.enabled)
            self._set_scan_target_checks(preflight.scan_targets)
            _set_combo_by_data(self._preservation_mode, preflight.preservation_mode)
            self._skip_high_risk.setChecked(preflight.skip_high_risk_modules)
            _set_combo_by_data(
                self._compliance_failure, scene.compliance_profile.failure_policy
            )
            _set_combo_by_data(
                self._report_level, scene.compliance_profile.report_level
            )
            self._apply_family_preflight_btn.setEnabled(
                bool(recommended_object_preflight_targets_for_scene(scene))
            )
            self._compliance_summary.set_items(build_compliance_summary_items(scene))
        finally:
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        if hasattr(self._current_scene.md_cleanup, "fix_paragraph_breaks"):
            self._current_scene.md_cleanup.fix_paragraph_breaks = (
                self._fix_breaks.isChecked()
            )
        if hasattr(self._current_scene.md_cleanup, "remove_empty_paragraphs"):
            self._current_scene.md_cleanup.remove_empty_paragraphs = (
                self._remove_empty.isChecked()
            )
        if hasattr(self._current_scene.whitespace, "normalize_spaces"):
            self._current_scene.whitespace.normalize_spaces = (
                self._normalize_spaces.isChecked()
            )
        self._current_scene.module_switches["validation"] = (
            self._validation_enabled.isChecked()
        )
        profile = self._current_scene.compliance_profile
        preflight = profile.object_preflight
        preflight.enabled = self._object_preflight_enabled.isChecked()
        preflight.scan_targets = [
            target
            for target, checkbox in self._scan_target_checks.items()
            if checkbox.isChecked()
        ]
        preflight.preservation_mode = str(
            self._preservation_mode.currentData() or preflight.preservation_mode
        )
        preflight.skip_high_risk_modules = self._skip_high_risk.isChecked()
        profile.failure_policy = str(
            self._compliance_failure.currentData() or profile.failure_policy
        )
        profile.report_level = str(
            self._report_level.currentData() or profile.report_level
        )
        self._compliance_summary.set_items(
            build_compliance_summary_items(self._current_scene)
        )
        self.scene_edited.emit()

    def _apply_family_preflight_targets(self) -> None:
        if self._current_scene is None:
            return
        targets = recommended_object_preflight_targets_for_scene(self._current_scene)
        if not targets:
            return
        self._current_scene.compliance_profile.object_preflight.scan_targets = list(
            targets
        )
        self._is_syncing = True
        try:
            self._set_scan_target_checks(targets)
        finally:
            self._is_syncing = False
        self._compliance_summary.set_items(
            build_compliance_summary_items(self._current_scene)
        )
        self.scene_edited.emit()

    def _set_scan_target_checks(self, targets) -> None:
        selected = {
            str(target or "").strip()
            for target in list(targets or [])
            if str(target or "").strip()
        }
        for target, checkbox in self._scan_target_checks.items():
            checkbox.setChecked(target in selected)

    def _apply_theme(self) -> None:
        super()._apply_theme()
        if not hasattr(self, "_scan_target_checks"):
            return
        if hasattr(self, "_apply_family_preflight_btn"):
            _apply_template_button_contract(
                (self._apply_family_preflight_btn, "secondary")
            )
        checkbox_style = build_checkbox_stylesheet(get_theme())
        for checkbox in self._scan_target_checks.values():
            checkbox.setStyleSheet(checkbox_style)






# ═══════════════════════════════════════════════════════════════════════
#  Main Panel (Master-Detail)
# ═══════════════════════════════════════════════════════════════════════


class ScenePanel(BasePanel):
    """Master-detail scene configuration panel."""

    panel_title = "方案配置"
    panel_icon = "target"

    _DETAIL_ATTR_NAMES = {
        "_exam_paper": "scn_exam_paper",
        "_rules": "scn_rules",
        "_scope": "scn_rules",
        "_output": "scn_rules",
        "_cleanup": "scn_cleanup",
        "_content": "scn_content",
    }

    @property
    def _current_scene(self) -> SceneWorkspace | None:
        return self._scene_session.state.scene

    @_current_scene.setter
    def _current_scene(self, scene: SceneWorkspace | None) -> None:
        self._scene_session.state.scene = scene

    @property
    def _current_scene_path(self) -> str:
        return self._scene_session.state.scene_path

    @_current_scene_path.setter
    def _current_scene_path(self, path: str) -> None:
        self._scene_session.state.scene_path = str(path or "").strip()

    @property
    def _current_scene_source(self) -> str:
        return self._scene_session.state.scene_source

    @_current_scene_source.setter
    def _current_scene_source(self, source: str) -> None:
        self._scene_session.state.scene_source = str(source or "").strip()

    @property
    def _current_scene_source_type(self) -> str:
        return self._scene_session.state.scene_source_type

    @_current_scene_source_type.setter
    def _current_scene_source_type(self, source_type: str) -> None:
        self._scene_session.state.scene_source_type = str(source_type or "").strip()

    @property
    def _current_template(self) -> TemplateConfig | None:
        return self._scene_session.state.template

    @_current_template.setter
    def _current_template(self, template: TemplateConfig | None) -> None:
        self._scene_session.state.template = template

    @property
    def _activating_scene_id(self) -> str:
        return self._scene_session.state.activating_scene_id

    @_activating_scene_id.setter
    def _activating_scene_id(self, scene_id: str) -> None:
        self._scene_session.state.activating_scene_id = str(scene_id or "").strip()

    @property
    def _restoring_scene_activation(self) -> bool:
        return self._scene_session.state.restoring_activation

    @_restoring_scene_activation.setter
    def _restoring_scene_activation(self, restoring: bool) -> None:
        self._scene_session.state.restoring_activation = bool(restoring)

    @property
    def _ignore_own_scene_changed(self) -> bool:
        return self._scene_session.state.ignore_own_scene_changed

    @_ignore_own_scene_changed.setter
    def _ignore_own_scene_changed(self, ignore: bool) -> None:
        self._scene_session.state.ignore_own_scene_changed = bool(ignore)

    def _current_work_mode_id(self) -> str:
        coordinator = self.__dict__.get("_scene_session")
        if coordinator is not None:
            return coordinator.current_work_mode_id()
        getter = getattr(self.bridge, "current_work_mode_id", None)
        return str(getter() or "").strip() if callable(getter) else "custom"

    def _activation_selected_card_id(self) -> str:
        nav_rail = getattr(self, "_nav_rail", None)
        if nav_rail is None:
            return ""
        return str(nav_rail.selected_card_id() or "").strip()

    def _restore_activation_selected_card(self, card_id: str) -> None:
        target = str(card_id or "").strip()
        card = getattr(self, "_nav_cards", {}).get(target)
        if card is not None and not card.isHidden():
            self._nav_rail.select_card(target)

    def _setup_ui(self) -> None:
        self.setObjectName("ScenePanel")
        self._scene_session = SceneSessionCoordinator(
            self.bridge,
            SceneProjectionCallbacks(
                apply_scene=lambda scene, template: self._apply_scene(
                    scene,
                    resolved_template=template,
                ),
                refresh_scene_selector=self._refresh_scene_selector_options,
                selected_card_id=self._activation_selected_card_id,
                restore_selected_card=self._restore_activation_selected_card,
                refresh_navigation_cards=self._refresh_navigation_cards,
            ),
        )
        self._current_scene_path = self.bridge.current_scene_path()
        self._current_scene_source = self.bridge.current_scene_source()
        self._current_scene_source_type = self.bridge.current_scene_source_type()
        self._current_template: TemplateConfig | None = None
        self._activating_scene_id = ""
        self._restoring_scene_activation = False
        self._ignore_own_scene_changed = False
        self._scene_descriptors = list(
            plan_selector_descriptors(self._current_work_mode_id())
        )
        self._scene_library_watcher = QFileSystemWatcher(self)
        self._scene_library_refresh_pending = False
        self._pending_scene_delete_receipt = None
        self._pending_scene_delete_resolution = ""
        self._scene_delete_activation_in_progress = False

        current_scene = self.bridge.current_scene()
        if current_scene is not None:
            self._current_scene = current_scene
        else:
            default_descriptor = default_scene_descriptor(
                mode_id=self._current_work_mode_id()
            )
            if default_descriptor is not None:
                self._current_scene = load_scene_from_library(
                    default_descriptor.config_id,
                    mode_id=self._current_work_mode_id(),
                )
                self._current_scene_path = str(default_descriptor.path)
                self._current_scene_source = "library"
                self._current_scene_source_type = default_descriptor.source_type
            else:
                self._current_scene = SceneWorkspace(
                    scene_id="custom", template_id="default"
                )
                self._current_scene_source = "runtime"
                self._current_scene_source_type = "runtime"

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

        # Build only the first visible detail during panel construction. Other
        # scene editors are created on demand to keep first open responsive.
        self._overview = _SceneOverviewDetail(
            self._scene_descriptors,
            work_mode_id=self._current_work_mode_id(),
        )
        self._detail_factories = {
            "scn_exam_paper": self._create_exam_paper_detail,
            "scn_rules": self._create_rules_detail,
            "scn_cleanup": self._create_cleanup_detail,
            "scn_content": self._create_content_detail,
        }
        self._detail_attr_names = dict(self._DETAIL_ATTR_NAMES)
        self._loaded_detail_ids: set[str] = {"scn_overview"}
        self._wired_detail_signal_ids: set[str] = set()
        self._detail_map: dict[str, QWidget] = {"scn_overview": self._overview}
        self._details = DetailPaneController(
            self._detail_container,
            self._detail_layout,
            self._detail_scroll,
        )
        self._details.register_details(self._detail_map)
        self._return_navigation_intent: dict[str, object] | None = None
        self._return_bar = QWidget(self._detail_container)
        self._return_bar.setObjectName("scn_return_bar")
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

        # Build navigation cards
        self._nav_cards: dict[str, NavigationCard] = {}
        self._nav_section_headers: dict[str, QLabel] = {}

        for card_id in FORMAT_TEMPLATE_CARDS:
            title, icon = CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

        for card_id in INPUT_MATERIAL_CARDS:
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
                source_type=self._current_scene_source_type,
                emit_signal=False,
            )
        if self.bridge.current_template() is None:
            self._sync_bound_template_from_scene()
        initial_card_id = self._default_visible_card_id()
        self._show_detail(initial_card_id)
        self._nav_rail.select_card(initial_card_id)
        self._save_scene_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        self._save_scene_shortcut.activated.connect(self.save_current_scene)
        self._apply_theme()
        self._setup_scene_library_watcher()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        self.bridge.scene_changed.connect(self.on_scene_changed)
        self.bridge.template_changed.connect(self.on_template_changed)
        if hasattr(self.bridge, "work_mode_changed"):
            self.bridge.work_mode_changed.connect(self._on_work_mode_changed)
        self.bridge.scene_dirty_changed.connect(self._on_scene_dirty_state_changed)
        self._nav_rail.card_selected.connect(self._show_detail)
        self._overview.scene_changed.connect(self._on_scene_changed)
        self._overview.scene_edited.connect(self._on_scene_edited)
        self._overview.navigate_requested.connect(self._show_detail_from_overview)
        self._overview.execute_requested.connect(self._navigate_to_quick_execute)
        self._overview.new_scene_requested.connect(self._on_new_scene_requested)
        self._overview.duplicate_scene_requested.connect(
            self._on_duplicate_scene_requested
        )
        self._overview.rename_scene_requested.connect(self._on_rename_scene_requested)
        self._overview.open_scene_folder_requested.connect(
            self._on_open_scene_folder_requested
        )
        self._overview.delete_scene_requested.connect(self._on_delete_scene_requested)
        self._overview.selector_open_requested.connect(
            self._refresh_scene_library_from_disk
        )
        self._scene_library_watcher.directoryChanged.connect(
            self._on_scene_library_path_changed
        )
        self._scene_library_watcher.fileChanged.connect(
            self._on_scene_library_path_changed
        )

    def __getattr__(self, name: str):
        detail_attrs = self.__dict__.get("_detail_attr_names", {})
        card_id = detail_attrs.get(name)
        if card_id:
            self._ensure_detail_loaded(card_id)
            if name in self.__dict__:
                return self.__dict__[name]
        raise AttributeError(f"{type(self).__name__} object has no attribute {name!r}")

    def _create_exam_paper_detail(self) -> QWidget:
        self._exam_paper = ExamPaperDetail(self.bridge)
        self._exam_paper.attach_plan_card(self._overview.take_scene_card())
        return self._exam_paper

    def _create_rules_detail(self) -> QWidget:
        self._scope = _ScopeDetail()
        self._output = _OutputDetail()
        self._rules = _SceneRulesDetail(
            self._scope,
            self._output,
        )
        return self._rules

    def _create_cleanup_detail(self) -> QWidget:
        self._cleanup = _CleanupDetail()
        return self._cleanup

    def _create_content_detail(self) -> QWidget:
        self._content = _ContentDetail(self.bridge)
        return self._content

    def _ensure_detail_loaded(self, card_id: str) -> QWidget | None:
        card_id = _normalise_scene_detail_card_id(card_id)
        if card_id in self._loaded_detail_ids:
            return self._detail_map.get(card_id)

        factory = self._detail_factories.get(card_id)
        if factory is None:
            return self._detail_map.get(card_id)

        detail = factory()
        detail.hide()
        detail.setParent(self._detail_container)
        self._detail_map[card_id] = detail
        self._details.detail_map[card_id] = detail
        self._loaded_detail_ids.add(card_id)
        self._wire_loaded_detail_signals(card_id)
        self._sync_loaded_detail_state(card_id, detail)
        if hasattr(detail, "apply_theme"):
            detail.apply_theme()
        return detail

    def _wire_loaded_detail_signals(self, card_id: str) -> None:
        if card_id in self._wired_detail_signal_ids:
            return
        if card_id == "scn_exam_paper":
            self._exam_paper.scene_edited.connect(self._mark_scene_detail_dirty)
            self._exam_paper.execute_requested.connect(self._navigate_to_quick_execute)
            self._exam_paper.navigate_material_requested.connect(
                lambda: self._show_detail_from_overview("scn_content")
            )
        elif card_id == "scn_rules":
            self._scope.scope_changed.connect(self._on_scope_changed)
            self._output.scene_edited.connect(self._mark_scene_detail_dirty)
            self._output.family_defaults_applied.connect(
                self._on_scene_family_defaults_applied
            )
        elif card_id in {"scn_cleanup", "scn_content"}:
            detail = self._detail_map.get(card_id)
            if hasattr(detail, "scene_edited"):
                detail.scene_edited.connect(self._mark_scene_detail_dirty)
        self._wired_detail_signal_ids.add(card_id)

    def _on_scene_dirty_state_changed(self, *_args) -> None:
        self._refresh_navigation_cards()
        self._sync_scene_file_status()

    def _sync_loaded_detail_state(self, card_id: str, detail: QWidget) -> None:
        scene = getattr(self, "_current_scene", None)
        if scene is None:
            return
        if card_id == "scn_exam_paper" and hasattr(detail, "set_scene"):
            detail.set_scene(scene)
            return
        if card_id == "scn_rules" and hasattr(detail, "set_scene"):
            detail.set_scene(
                scene,
                getattr(self, "_current_template", None),
                mode_id=self._current_work_mode_id(),
            )
            return
        if card_id in {"scn_cleanup", "scn_content"} and hasattr(detail, "set_scene"):
            detail.set_scene(scene)

    def _show_detail(self, card_id: str) -> None:
        card_id = _normalise_scene_detail_card_id(card_id)
        self._ensure_detail_loaded(card_id)
        self._details.show_detail(card_id)

    def _show_detail_from_overview(self, card_id: str) -> None:
        if str(card_id or "").startswith("tpl_"):
            self.bridge.navigate_to_intent.emit(
                {
                    "panel_id": "template",
                    "card_id": card_id,
                    "return_panel_id": "scene",
                    "return_card_id": "scn_overview",
                    "payload": self._template_navigation_context_payload(),
                }
            )
            return
        card_id = _normalise_scene_detail_card_id(card_id)
        if card_id in self._nav_cards:
            if self._nav_cards[card_id].isHidden():
                self._nav_rail.select_card(self._default_visible_card_id())
                return
            self._nav_rail.select_card(card_id)
            return
        self._show_detail(card_id)

    def _template_navigation_context_payload(self) -> dict[str, object]:
        preview_context = self._template_preview_context_for_scene(self._current_scene)
        return {
            "entry_context_title": preview_context.title,
            "entry_context_detail": preview_context.detail,
            "entry_context_action": preview_context.action,
            "template_preview_groups": preview_context.detail_card_ids,
            "template_preview_coverage": preview_context.coverage_labels,
        }

    def _resolve_template_for_scene(self, scene: SceneWorkspace | None):
        template_id = str(
            getattr(scene, "template_id", "")
            or ""
        ).strip()
        if not template_id:
            return None
        if self.bridge.current_template_id() == template_id:
            template = self.bridge.current_template()
            if template is not None:
                return template
        try:
            return load_template_from_library(
                template_id, mode_id=self._current_work_mode_id()
            )
        except Exception:
            return None

    def _template_preview_context_for_scene(
        self,
        scene: SceneWorkspace | None,
    ):
        template_id = str(
            getattr(scene, "template_id", "")
            or ""
        ).strip()
        template_label = (
            _template_label_with_id(template_id, mode_id=self._current_work_mode_id())
            if template_id
            else "当前模板"
        )
        return build_template_navigation_context(
            scene_label=self._scene_display_label(scene),
            template_label=template_label,
        )

    def _scene_display_label(self, scene: SceneWorkspace | None) -> str:
        scene_id = str(getattr(scene, "scene_id", "") or "").strip()
        for descriptor in self._scene_descriptors:
            if descriptor.config_id == scene_id:
                return plan_display_label(descriptor)
        return str(getattr(scene, "name", "") or "").strip() or scene_id or "当前方案"

    def _current_scene_id(self) -> str:
        return self._scene_session.current_scene_id()

    def _builtin_scene_ids(self) -> set[str]:
        builtin_ids = {
            str(getattr(descriptor, "config_id", "") or "").strip()
            for descriptor in self._scene_descriptors
            if str(getattr(descriptor, "source_type", "") or "").strip() == "builtin"
            and str(getattr(descriptor, "config_id", "") or "").strip()
        }
        builtin_ids.update(_builtin_scene_id_set())
        return builtin_ids

    def _current_scene_is_builtin(self) -> bool:
        scene_id = self._current_scene_id()
        if not scene_id:
            return False
        source_type = str(self._current_scene_source_type or "").strip()
        if source_type:
            return source_type == "builtin"
        descriptor = self._descriptor_for_scene_id(scene_id)
        if descriptor is not None:
            return (
                str(getattr(descriptor, "source_type", "") or "").strip() == "builtin"
            )
        return scene_id in self._builtin_scene_ids()

    def _current_scene_path_obj(self) -> Path | None:
        path = str(self._current_scene_path or "").strip()
        if path:
            return Path(path)
        scene_id = self._current_scene_id()
        if scene_id:
            entry = get_scene_entry(scene_id, mode_id=self._current_work_mode_id())
            if entry is not None:
                return entry.path
        return None

    def _current_scene_manage_path(self) -> Path | None:
        path = self._current_scene_path_obj()
        if path is None or not path.exists() or path.is_dir():
            return None
        source_type = str(self._current_scene_source_type or "").strip()
        if not source_type:
            descriptor = self._descriptor_for_scene_id(self._current_scene_id())
            source_type = str(
                getattr(descriptor, "source_type", "") or ""
            ).strip()
        if not source_type:
            source_type = config_library.scene_source_type_for_path(path)
        if source_type != "user":
            return None
        return path if config_library.is_scene_user_library_path(path) else None

    def _current_scene_can_rename(self) -> bool:
        return (
            self._current_scene is not None
            and not self._current_scene_is_builtin()
            and self._current_scene_manage_path() is not None
        )

    def _current_scene_can_delete(self) -> bool:
        return (
            not self._current_scene_is_builtin()
            and self._current_scene_manage_path() is not None
        )

    def _current_scene_folder(self) -> Path:
        if self._current_work_mode_id() == "official":
            return OFFICIAL_USER_MASTER_DIR
        path = self._current_scene_path_obj()
        if path is not None:
            folder = path if path.is_dir() else path.parent
            if folder.exists():
                return folder
        return config_library.scene_user_dir(self._current_work_mode_id())

    def _sync_scene_file_status(self) -> None:
        if not hasattr(self, "_overview"):
            return
        is_builtin = self._current_scene_is_builtin()
        can_rename = self._current_scene_can_rename()
        can_delete = self._current_scene_can_delete()
        source_type = str(self._current_scene_source_type or "").strip()
        unavailable_reason = (
            "内置方案不能修改，请先创建副本"
            if is_builtin
            else (
                "外部方案不能直接修改，请先创建副本"
                if source_type == "external"
                else "当前方案还没有保存为用户方案文件"
            )
        )
        self._overview.set_scene_action_state(
            can_rename=can_rename,
            can_delete=can_delete,
            rename_tooltip="" if can_rename else unavailable_reason,
            delete_tooltip="" if can_delete else unavailable_reason,
            folder_tooltip=str(self._current_scene_folder()),
        )

    def _scene_library_watch_directories(self) -> list[str]:
        return [
            str(path)
            for path in config_library.scene_library_watch_dirs(
                mode_id=self._current_work_mode_id()
            )
        ]

    def _setup_scene_library_watcher(self) -> None:
        watcher = getattr(self, "_scene_library_watcher", None)
        if watcher is None:
            return
        target_dirs = set(self._scene_library_watch_directories())
        current_dirs = set(watcher.directories())
        remove_dirs = list(current_dirs - target_dirs)
        add_dirs = list(target_dirs - current_dirs)
        if remove_dirs:
            watcher.removePaths(remove_dirs)
        if add_dirs:
            watcher.addPaths(add_dirs)

    def _on_scene_library_path_changed(self, _path: str = "") -> None:
        if self._scene_library_refresh_pending:
            return
        self._scene_library_refresh_pending = True
        QTimer.singleShot(50, self._refresh_scene_library_from_disk)

    def _current_scene_file_was_removed(self) -> bool:
        source = str(self._current_scene_source or "").strip()
        if source not in {"library", "file"}:
            return False
        path = self._current_scene_path_obj()
        return path is not None and not path.exists()

    def _refresh_scene_library_from_disk(self) -> None:
        self._scene_library_refresh_pending = False
        try:
            self._setup_scene_library_watcher()
        except Exception as exc:
            Toast.show_error(f"刷新方案目录失败: {exc}")
            return
        authoritative_conflict = (
            self._scene_session.refresh_authoritative_user_conflict()
        )
        if authoritative_conflict:
            if self._scene_session.recovery_required():
                Toast.show_warning(
                    "上一次方案保存仍需恢复；已保留当前现场，"
                    "恢复完成前不会重载、切换或覆盖方案文件"
                )
                return
            if self._current_scene_file_was_removed():
                if self.bridge.is_scene_dirty():
                    Toast.show_warning(
                        "当前方案文件已被外部删除；未保存草稿仍保留，请保存为新的用户方案"
                    )
                    return
                self._switch_to_default_scene_after_missing_file()
                return
            if self.bridge.is_scene_dirty():
                Toast.show_warning(
                    "当前方案文件已被外部修改；未保存草稿仍保留，"
                    "为避免覆盖外部版本，请保存为新的用户方案"
                )
                return
            self._reload_clean_current_user_scene_from_disk()
            return
        if self._current_scene_file_was_removed():
            if self.bridge.is_scene_dirty():
                Toast.show_warning(
                    "当前方案文件已被外部删除；未保存草稿仍保留，请保存为新的用户方案"
                )
                return
            self._switch_to_default_scene_after_missing_file()
            return
        try:
            self._refresh_scene_selector_options()
        except Exception as exc:
            Toast.show_error(f"刷新方案列表失败: {exc}")

    def _reload_clean_current_user_scene_from_disk(self) -> bool:
        scene_id = self._current_scene_id()
        path = self._current_scene_path_obj()
        mode_id = self._current_work_mode_id()
        try:
            if not scene_id or path is None:
                raise ValueError("当前用户方案缺少可重载的身份或路径")
            expected_path = config_library.validate_scene_library_write_path(path)
            entry = get_scene_entry(scene_id, mode_id=mode_id)
            if (
                entry is None
                or not bool(getattr(entry, "is_available", True))
                or str(getattr(entry, "source_type", "") or "").strip() != "user"
            ):
                raise ValueError("当前用户方案不再是可用的权威库条目")
            entry_path = config_library.validate_scene_library_write_path(entry.path)
            if entry_path != expected_path:
                raise ValueError("当前用户方案的库路径发生变化")
            before_load = self._scene_session.capture_user_reload_candidate(
                expected_path
            )
            scene = load_scene_from_library(scene_id, mode_id=mode_id)
            if str(getattr(scene, "scene_id", "") or "").strip() != scene_id:
                raise ValueError("外部方案内容与当前方案身份不一致")
            after_load = self._scene_session.capture_user_reload_candidate(
                expected_path
            )
            if after_load.revision != before_load.revision:
                raise RuntimeError("方案文件在重载期间再次变化")
        except Exception as exc:
            Toast.show_error(f"重新加载外部修改的方案失败: {exc}")
            return False
        activated = self._activate_scene(
            scene,
            scene_id=scene_id,
            path=str(entry_path),
            source="library",
            source_type="user",
            dirty=False,
            expected_user_revision=after_load.revision,
        )
        if not activated:
            return False
        Toast.show_info("当前方案文件已被外部更新，已重新加载")
        return True

    def _switch_to_default_scene_after_missing_file(self) -> bool:
        message = "当前方案文件已不存在，已切换到默认方案"
        try:
            mode_id = self._current_work_mode_id()
            entry = default_scene_entry(mode_id=mode_id)
            if entry is not None:
                scene = load_scene_from_library(
                    entry.config_id,
                    mode_id=mode_id,
                )
                activated = self._activate_scene(
                    scene,
                    scene_id=entry.config_id,
                    path=str(entry.path),
                    source="library",
                    source_type=entry.source_type,
                    dirty=False,
                )
            else:
                scene = SceneWorkspace(
                    scene_id="custom",
                    mode_id=mode_id,
                    template_id="default",
                )
                activated = self._activate_scene(
                    scene,
                    scene_id="custom",
                    path="",
                    source="runtime",
                    source_type="runtime",
                    dirty=False,
                )
        except Exception as exc:
            Toast.show_error(f"当前方案缺失后加载默认方案失败: {exc}")
            return False
        if activated:
            Toast.show_info(message)
            return True
        return False

    def _refresh_scene_selector_options(self) -> None:
        self._scene_descriptors = list(
            plan_selector_descriptors(self._current_work_mode_id())
        )
        self._overview.set_scene_options(
            self._scene_descriptors,
            current_scene_id=self._current_scene_id(),
            work_mode_id=self._current_work_mode_id(),
        )
        self._sync_scene_file_status()

    def _on_work_mode_changed(self, _mode) -> None:
        # MainWindow owns the mode -> default scene/template transaction and
        # publishes both resources before this later-connected slot runs.
        # Reloading here used to replace that scene with a second instance and
        # emit duplicate scene/template events for one mode switch.
        self._setup_scene_library_watcher()
        self._refresh_scene_selector_options()
        exam_paper = getattr(self, "_exam_paper", None)
        if exam_paper is not None:
            exam_paper.refresh_resource_options_for_work_mode(
                self._current_work_mode_id()
            )

    def _activate_scene(
        self,
        scene: SceneWorkspace,
        *,
        scene_id: str,
        path: str = "",
        source: str = "library",
        source_type: str | None = None,
        dirty: bool = False,
        expected_user_revision: str = "",
    ) -> bool:
        if (
            self._pending_scene_delete_receipt is not None
            and not self._scene_delete_activation_in_progress
            and not self._resolve_pending_scene_delete()
        ):
            return False
        result = self._scene_session.activate(
            scene,
            scene_id=scene_id,
            path=path,
            source=source,
            source_type=source_type,
            dirty=dirty,
            expected_user_revision=expected_user_revision,
        )
        if result.success:
            return True
        if result.rollback_error is not None:
            Toast.show_error(
                f"加载方案失败，且恢复旧方案失败: {result.rollback_error}"
            )
        else:
            Toast.show_error(f"加载方案失败，已恢复旧方案: {result.error}")
        return False

    def _scene_copy_base_name(self) -> str:
        if self._current_scene_is_builtin():
            name = self._scene_display_label(self._current_scene)
        else:
            name = str(
                getattr(self._current_scene, "name", "")
                or self._current_scene_id()
                or "自定义方案"
            )
        name = str(name or "").strip() or "自定义方案"
        return re.sub(r"\s*副本(?:\s*\d+)?$", "", name).strip() or name

    def _unique_scene_copy_name(self) -> str:
        base_name = self._scene_copy_base_name()
        existing_names = {
            str(descriptor.name or "").strip()
            for descriptor in plan_selector_descriptors(self._current_work_mode_id())
            if str(descriptor.name or "").strip()
        }

        def available(name: str) -> bool:
            if name.casefold() in {item.casefold() for item in existing_names}:
                return False
            return self._unique_scene_id_for_name(name) == safe_scene_file_stem(name)

        candidate = f"{base_name} 副本"
        if available(candidate):
            return candidate
        for index in range(2, 1000):
            candidate = f"{base_name} 副本 {index}"
            if available(candidate):
                return candidate
        raise ValueError("无法为方案副本分配不冲突的名称")

    def _unique_scene_id_for_name(self, name: str) -> str:
        return allocate_scene_id(
            name=str(name or "").strip(),
            mode_id=self._current_work_mode_id(),
        )

    def _create_scene_copy(self, name: str, *, action_label: str) -> bool:
        if not self.prepare_pending_scene_changes(
            SCENE_PENDING_SAVE,
            fork_name=str(name or "").strip(),
            force_fork=True,
            force_save=True,
        ):
            return False
        if not self.commit_prepared_scene_changes():
            self.cancel_prepared_scene_changes()
            return False
        if not self.finalize_prepared_scene_changes():
            self.rollback_prepared_scene_changes()
            return False
        Toast.show_success(f"已{action_label}: {name}")
        return True

    def _navigate_to_quick_execute(self) -> None:
        return_card_id = (
            self._nav_rail.selected_card_id()
            if hasattr(self, "_nav_rail")
            and self._nav_rail.selected_card_id() in self._detail_map
            else self._default_visible_card_id()
        )
        self.bridge.navigate_to_intent.emit(
            {
                "panel_id": "workbench",
                "card_id": "quick_execute",
                "return_panel_id": "scene",
                "return_card_id": return_card_id,
            }
        )

    def _refresh_navigation_cards(self) -> None:
        scene = getattr(self, "_current_scene", None)
        if scene is None or not hasattr(self, "_nav_cards"):
            return

        snapshots = self._navigation_card_snapshots(scene)
        for card_id, snapshot in snapshots.items():
            card = self._nav_cards.get(card_id)
            if card is None:
                continue
            card.set_subtitle(snapshot.get("subtitle", ""))
            card.set_badge(
                snapshot.get("badge_text", ""),
                snapshot.get("badge_variant", "neutral"),
            )

    def _navigation_card_snapshots(
        self, scene: SceneWorkspace
    ) -> dict[str, dict[str, str]]:
        scene_label = self._scene_display_label(scene)
        template_label = (
            _template_label_with_id(
                _scene_current_template_id(scene),
                mode_id=self._current_work_mode_id(),
            )
            or "未绑定模板"
        )
        dirty = (
            bool(self.bridge.is_scene_dirty())
            if hasattr(self.bridge, "is_scene_dirty")
            else False
        )
        return build_scene_navigation_card_snapshots(
            scene,
            scene_label=scene_label,
            template_label=template_label,
            scene_dirty=dirty,
            current_template=getattr(self, "_current_template", None),
            delivery_preset=default_delivery_preset(scene),
            exam_paper_config=_project_exam_paper_config(scene)[0],
        )

    def handle_navigation_intent(self, intent) -> None:
        self._set_return_navigation_intent(intent)
        card_id = str(navigation_intent_value(intent, "card_id", "") or "").strip()
        if not card_id:
            return
        self._show_detail_from_overview(card_id)
        self._focus_navigation_field(card_id, intent)

    def _focus_navigation_field(self, card_id: str, intent) -> None:
        detail = self._details.current_detail
        if detail is not None and hasattr(detail, "handle_navigation_intent"):
            if bool(detail.handle_navigation_intent(intent)):
                return
        field_id = str(navigation_intent_value(intent, "field_id", "") or "").strip()
        if not field_id:
            payload = navigation_intent_value(intent, "payload", {}) or {}
            if isinstance(payload, dict):
                field_id = str(
                    payload.get("issue_key") or payload.get("repair_target_key") or ""
                ).strip()
        if not field_id:
            return
        if (
            _normalise_scene_detail_card_id(card_id) == "scn_rules"
            and str(card_id or "").strip() == "scn_output"
            and detail is not None
            and hasattr(detail, "focus_output_navigation_field")
        ):
            detail.focus_output_navigation_field(field_id)
            return
        if detail is not None and hasattr(detail, "focus_navigation_field"):
            detail.focus_navigation_field(field_id)

    def _set_return_navigation_intent(self, intent) -> None:
        panel_id = str(
            navigation_intent_value(intent, "return_panel_id", "") or ""
        ).strip()
        card_id = str(
            navigation_intent_value(intent, "return_card_id", "") or ""
        ).strip()
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
        if issue_key:
            self._return_navigation_intent["field_id"] = issue_key
        if active_issue_id:
            self._return_navigation_intent["active_issue_id"] = active_issue_id
        if payload:
            self._return_navigation_intent["payload"] = dict(payload)
            if active_issue_id and not self._return_navigation_intent["payload"].get(
                "active_issue_id"
            ):
                self._return_navigation_intent["payload"]["active_issue_id"] = (
                    active_issue_id
                )
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

    def _navigate_return_target(self) -> None:
        if not self._return_navigation_intent:
            return
        self.bridge.navigate_to_intent.emit(dict(self._return_navigation_intent))
        self._return_bar.setVisible(False)

    def _prompt_scene_save_as_name(self, reason: str = "") -> str | None:
        try:
            default_name = self._unique_scene_copy_name()
        except Exception as exc:
            Toast.show_error(f"无法生成用户方案名称: {exc}")
            return None
        reason_text = str(reason or "保存当前修改").strip()
        name = input_text(
            "保存为我的方案",
            f"内置方案不会被覆盖。请为用户副本命名，以便{reason_text}：",
            placeholder="例如：校级期中试卷方案",
            default=default_name,
            ok_text="保存",
            parent=self,
        )
        if name is None:
            return None
        normalized = str(name or "").strip()
        if not normalized:
            Toast.show_warning("方案名称不能为空")
            return None
        return normalized

    def save_current_scene(self) -> bool:
        """Persist the active draft through the shared ownership transaction."""

        if not self.bridge.is_scene_dirty():
            Toast.show_info("当前方案没有未保存修改")
            return True
        if not self.prepare_pending_scene_changes(
            SCENE_PENDING_SAVE,
            save_reason="保存当前修改",
        ):
            return False
        if not self.commit_prepared_scene_changes():
            self.cancel_prepared_scene_changes()
            return False
        if not self.finalize_prepared_scene_changes():
            self.rollback_prepared_scene_changes()
            return False
        Toast.show_success("方案已保存")
        return True

    def _on_new_scene_requested(self) -> None:
        try:
            default_name = self._unique_scene_copy_name()
        except Exception as exc:
            Toast.show_error(f"无法创建方案: {exc}")
            return
        name = input_text(
            "新建方案",
            "请输入方案名称：",
            placeholder="例如：合同交付自定义方案",
            default=default_name,
            ok_text="创建",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            Toast.show_warning("方案名称不能为空")
            return
        self._create_scene_copy(name, action_label="新建方案")

    def _on_duplicate_scene_requested(self) -> None:
        try:
            copy_name = self._unique_scene_copy_name()
        except Exception as exc:
            Toast.show_error(f"创建副本失败: {exc}")
            return
        self._create_scene_copy(
            copy_name,
            action_label="创建副本",
        )

    def _on_rename_scene_requested(self) -> None:
        if not self._current_scene_can_rename():
            Toast.show_warning(
                "当前方案不能直接重命名，请先创建副本"
                if self._current_scene_is_builtin()
                or str(self._current_scene_source_type or "").strip()
                in {"legacy", "external"}
                else "当前方案还没有保存为用户方案文件"
            )
            return
        current_name = str(
            getattr(self._current_scene, "name", "")
            or self._current_scene_id()
            or ""
        ).strip()
        name = input_text(
            "重命名方案",
            "请输入新的方案名称：",
            placeholder="方案名称",
            default=current_name,
            ok_text="保存",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            Toast.show_warning("方案名称不能为空")
            return
        if self._current_scene is None:
            return
        renamed_scene = copy.deepcopy(self._current_scene)
        renamed_scene.name = name
        if not self.prepare_pending_scene_changes(
            SCENE_PENDING_SAVE,
            force_save=True,
            scene_override=renamed_scene,
        ):
            return
        if not self.commit_prepared_scene_changes():
            self.cancel_prepared_scene_changes()
            return
        if not self.finalize_prepared_scene_changes():
            self.rollback_prepared_scene_changes()
            return
        Toast.show_success(f"已重命名方案: {name}")

    def _on_open_scene_folder_requested(self) -> None:
        folder = self._current_scene_folder()
        folder.mkdir(parents=True, exist_ok=True)
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        if not opened:
            Toast.show_error(f"无法打开方案文件夹: {folder}")

    def _resolve_pending_scene_delete(self) -> bool:
        receipt = self._pending_scene_delete_receipt
        if receipt is None:
            return True
        try:
            if self._pending_scene_delete_resolution == "finalize":
                config_library.finalize_scene_file_mutation(receipt)
            else:
                config_library.rollback_scene_file_mutation(receipt)
        except Exception as exc:
            Toast.show_error(f"Scene delete recovery is still pending: {exc}")
            return False
        self._pending_scene_delete_receipt = None
        self._pending_scene_delete_resolution = ""
        self._scene_session.set_external_recovery_required(False)
        return True

    def _on_delete_scene_requested(self) -> None:
        if not self._resolve_pending_scene_delete():
            return
        if not self._current_scene_can_delete():
            Toast.show_warning(
                "当前方案不能直接删除，请先创建副本"
                if self._current_scene_is_builtin()
                or str(self._current_scene_source_type or "").strip()
                in {"legacy", "external"}
                else "当前方案还没有可删除的用户方案文件"
            )
            return
        if self.bridge.is_scene_dirty():
            pending_action = self._prompt_pending_scene_action("删除当前方案")
            if pending_action == SCENE_PENDING_CANCEL:
                return
            if pending_action == SCENE_PENDING_SAVE and not self.save_current_scene():
                return
        path = self._current_scene_manage_path()
        if path is None:
            Toast.show_warning("当前方案还没有可删除的用户方案文件")
            return
        scene_name = str(
            getattr(self._current_scene, "name", "")
            or self._current_scene_id()
            or path.stem
        ).strip()
        if not confirm(
            "删除方案",
            f"确定删除方案“{scene_name}”吗？\n\n文件：{path.name}",
            confirm_text="删除",
            destructive=True,
            parent=self,
        ):
            return
        deleted_payload: bytes | None = None
        validated_path: Path | None = None
        delete_receipt = None
        try:
            if not config_library.is_scene_user_library_path(path):
                raise ValueError(f"not an owned user plan: {path}")
            validated_path = config_library.validate_scene_library_write_path(path)
            verified = self._scene_session.capture_verified_authoritative_user_file(
                validated_path
            )
            deleted_payload = verified.payload
            if deleted_payload is None:
                raise FileNotFoundError(validated_path)
            delete_receipt = config_library.replace_scene_file_if_revision(
                validated_path,
                expected_revision=verified.revision,
                replacement_payload=None,
                retain_recovery=True,
            )
            if not isinstance(
                delete_receipt,
                config_library.SceneFileMutationReceipt,
            ):
                raise RuntimeError("Scene delete did not retain rollback evidence")
            self._pending_scene_delete_receipt = delete_receipt
            self._pending_scene_delete_resolution = "rollback"
            self._scene_session.set_external_recovery_required(True)
        except Exception as exc:
            recovery_receipt = getattr(exc, "mutation_receipt", None)
            if isinstance(
                recovery_receipt,
                config_library.SceneFileMutationReceipt,
            ):
                self._pending_scene_delete_receipt = recovery_receipt
                self._pending_scene_delete_resolution = "rollback"
                self._scene_session.set_external_recovery_required(True)
            Toast.show_error(f"删除方案失败: {exc}")
            return

        activated = False
        self._scene_delete_activation_in_progress = True
        try:
            entry = default_scene_entry(mode_id=self._current_work_mode_id())
            if entry is not None:
                scene = load_scene_from_library(
                    entry.config_id,
                    mode_id=self._current_work_mode_id(),
                )
                activated = self._activate_scene(
                    scene,
                    scene_id=entry.config_id,
                    path=str(entry.path),
                    source="library",
                    source_type=entry.source_type,
                    dirty=False,
                )
            else:
                scene = SceneWorkspace(
                    scene_id="custom",
                    mode_id=self._current_work_mode_id(),
                    template_id="default",
                )
                activated = self._activate_scene(
                    scene,
                    scene_id="custom",
                    path="",
                    source="runtime",
                    source_type="runtime",
                    dirty=False,
                )
        except Exception as exc:
            Toast.show_error(f"删除方案后加载默认方案失败: {exc}")
        finally:
            self._scene_delete_activation_in_progress = False
        if activated and delete_receipt is not None:
            self._pending_scene_delete_resolution = "finalize"
            if not self._resolve_pending_scene_delete():
                self._refresh_scene_selector_options()
                return
        if not activated:
            if self._resolve_pending_scene_delete():
                self._scene_session.refresh_authoritative_user_conflict()
                self._refresh_scene_selector_options()
            else:
                self._scene_session.refresh_authoritative_user_conflict()
                Toast.show_warning(
                    "删除回滚期间方案文件已被外部重新创建；已保留外部版本，未覆盖"
                )
                try:
                    self._refresh_scene_selector_options()
                except Exception as refresh_exc:
                    Toast.show_error(f"刷新方案列表失败: {refresh_exc}")
            return
        Toast.show_success(f"已删除方案: {scene_name}")

    def _restore_scene_combo_selection(self) -> None:
        detail_combo = getattr(self._overview, "_combo", None)
        if detail_combo is None:
            return
        target_id = self._current_scene_id()
        if not target_id:
            return
        for row in range(detail_combo.count()):
            if str(detail_combo.itemData(row) or "").strip() == target_id:
                blocked = detail_combo.blockSignals(True)
                detail_combo.setCurrentIndex(row)
                detail_combo.blockSignals(blocked)
                return

    def _descriptor_for_scene_id(self, scene_id: str):
        target_id = str(scene_id or "").strip()
        if not target_id:
            return None
        return next(
            (
                descriptor
                for descriptor in self._scene_descriptors
                if str(getattr(descriptor, "config_id", "") or "").strip() == target_id
            ),
            None,
        )

    @staticmethod
    def _accept_pending_scene_dialog(
        dialog: BaseDialog,
        selected: dict[str, str],
        action: str,
    ) -> None:
        selected["action"] = action
        dialog.accept()

    def _prompt_pending_scene_action(self, reason: str) -> str:
        dialog = BaseDialog(title="未保存的方案修改", icon_style="warning", parent=self)
        dialog.add_message(
            f"当前方案有未保存修改。{str(reason or '继续').strip()}前，"
            "请选择保存、放弃修改或取消。"
        )
        selected = {"action": SCENE_PENDING_CANCEL}
        cancel_button = dialog.add_secondary_button("取消")
        cancel_button.clicked.connect(dialog.reject)
        discard_button = dialog.add_secondary_button("放弃修改")
        discard_button.clicked.connect(
            lambda: self._accept_pending_scene_dialog(
                dialog,
                selected,
                SCENE_PENDING_DISCARD,
            )
        )
        save_button = dialog.add_primary_button(
            "保存为我的方案"
            if self._scene_session.requires_fork_save()
            else "保存"
        )
        save_button.clicked.connect(
            lambda: self._accept_pending_scene_dialog(
                dialog,
                selected,
                SCENE_PENDING_SAVE,
            )
        )
        dialog.exec()
        return str(selected["action"])

    def prepare_pending_scene_changes(
        self,
        action: str,
        *,
        save_callable=None,
        mode_id: str = "",
        fork_name: str | None = None,
        force_fork: bool = False,
        force_save: bool = False,
        scene_override: SceneWorkspace | None = None,
        save_reason: str = "",
    ) -> bool:
        if not self._resolve_pending_scene_delete():
            return False
        normalized_action = str(action or "").strip()
        resolved_fork_name = fork_name
        if normalized_action == SCENE_PENDING_SAVE and resolved_fork_name is None:
            try:
                requires_fork = force_fork or self._scene_session.requires_fork_save(
                    mode_id=mode_id,
                )
            except Exception as exc:
                Toast.show_error(f"无法判断方案保存身份: {exc}")
                return False
            if requires_fork:
                resolved_fork_name = self._prompt_scene_save_as_name(save_reason)
                if resolved_fork_name is None:
                    return False
        result = self._scene_session.prepare_pending_changes(
            action,
            save_callable=save_callable,
            mode_id=mode_id,
            fork_name=resolved_fork_name,
            force_fork=force_fork,
            force_save=force_save,
            scene_override=scene_override,
        )
        if not result.success and result.error is not None:
            Toast.show_error(f"无法准备方案保存: {result.error}")
        return result.success

    def commit_prepared_scene_changes(self) -> bool:
        result = self._scene_session.commit_prepared_changes()
        if result.success:
            return True
        if result.rollback_error is not None:
            Toast.show_error(
                f"保存方案失败，且回滚失败: {result.rollback_error}"
            )
        elif result.error is not None:
            Toast.show_error(f"保存方案失败: {result.error}")
        return False

    def rollback_prepared_scene_changes(self) -> bool:
        result = self._scene_session.rollback_prepared_changes()
        if result.success:
            return True
        error = result.rollback_error or result.error
        if error is not None:
            Toast.show_error(f"回滚方案保存失败: {error}")
        return False

    def finalize_prepared_scene_changes(
        self,
        *,
        retain_rollback: bool = False,
    ) -> bool:
        result = self._scene_session.finalize_prepared_changes(
            retain_rollback=retain_rollback,
        )
        if result.success:
            return True
        if result.error is not None:
            Toast.show_error(f"发布已保存方案失败: {result.error}")
        return False

    def release_finalized_edit_transaction(self) -> bool:
        result = self._scene_session.release_finalized_changes()
        if result.success:
            return True
        if result.error is not None:
            Toast.show_error(f"释放方案保存事务失败: {result.error}")
        return False

    def cancel_prepared_scene_changes(self) -> None:
        self._scene_session.cancel_prepared_changes()

    def prepare_close_pending_changes(self) -> bool:
        if not self._resolve_pending_scene_delete():
            return False
        self.cancel_prepared_scene_changes()
        if not self.bridge.is_scene_dirty():
            return True
        action = self._prompt_pending_scene_action("关闭程序")
        if action == SCENE_PENDING_CANCEL:
            return False
        return self.prepare_pending_scene_changes(
            action,
            save_reason="关闭程序前保存修改",
        )

    def commit_close_pending_changes(self) -> bool:
        return self.commit_prepared_scene_changes()

    def rollback_close_pending_changes(self) -> bool:
        return self.rollback_prepared_scene_changes()

    def finalize_close_pending_changes(
        self,
        *,
        retain_rollback: bool = False,
    ) -> bool:
        finalized = (
            self.finalize_prepared_scene_changes(retain_rollback=True)
            if retain_rollback
            else self.finalize_prepared_scene_changes()
        )
        if finalized is False:
            return False
        return self._shutdown_loaded_document_previews()

    def _shutdown_loaded_document_previews(self, timeout_ms: int = 250) -> bool:
        # Read __dict__ directly: close finalization must never materialize the
        # lazily-created exam/template detail merely to shut it down.
        detail = self.__dict__.get("_exam_paper")
        if detail is None:
            return True
        shutdown = getattr(detail, "_shutdown_document_word_preview", None)
        if not callable(shutdown):
            return True
        return bool(shutdown(timeout_ms=timeout_ms))

    def cancel_prepared_close(self) -> None:
        self.cancel_prepared_scene_changes()

    def _on_scene_changed(self, index: int) -> None:
        detail_combo = getattr(self._overview, "_combo", None)
        if detail_combo is None or not (0 <= index < detail_combo.count()):
            return
        selected_id = str(detail_combo.itemData(index) or "").strip()
        if not selected_id or _is_scene_selector_group(selected_id):
            self._restore_scene_combo_selection()
            return

        descriptor = self._descriptor_for_scene_id(selected_id)
        if descriptor is None or descriptor.load_error:
            self._restore_scene_combo_selection()
            return

        if selected_id == self._current_scene_id():
            return
        if self.bridge.is_scene_dirty():
            action = self._prompt_pending_scene_action(
                f"切换到“{str(descriptor.name or descriptor.config_id)}”"
            )
            if action == SCENE_PENDING_CANCEL:
                self._restore_scene_combo_selection()
                return
            if action == SCENE_PENDING_SAVE:
                if not self.prepare_pending_scene_changes(
                    action,
                    save_reason=f"切换到“{str(descriptor.name or descriptor.config_id)}”",
                ):
                    self._restore_scene_combo_selection()
                    return
                if not self.commit_prepared_scene_changes():
                    self.cancel_prepared_scene_changes()
                    self._restore_scene_combo_selection()
                    return
                if not self.finalize_prepared_scene_changes():
                    self.rollback_prepared_scene_changes()
                    self._restore_scene_combo_selection()
                    return

        try:
            scene = load_scene_from_library(
                descriptor.config_id,
                mode_id=self._current_work_mode_id(),
            )
        except Exception as exc:
            Toast.show_error(f"加载方案失败: {exc}")
            self._restore_scene_combo_selection()
            return
        if not self._activate_scene(
            scene,
            scene_id=descriptor.config_id,
            path=str(descriptor.path),
            source="library",
            dirty=False,
        ):
            self._restore_scene_combo_selection()

    def _apply_scene(
        self,
        scene: SceneWorkspace,
        *,
        resolved_template: TemplateConfig | None | object = _SCENE_TEMPLATE_UNSET,
    ) -> None:
        template = (
            self._resolve_template_for_scene(scene)
            if resolved_template is _SCENE_TEMPLATE_UNSET
            else resolved_template
        )
        if template is not None and not isinstance(template, TemplateConfig):
            raise TypeError("resolved scene template must be TemplateConfig or None")
        self._current_template = template
        preview_context = self._template_preview_context_for_scene(
            scene,
        )
        self._overview.set_scene(
            scene,
            template=template,
            template_preview_action=preview_context.action,
        )
        self._sync_loaded_scene_details(scene, template)
        self._update_dynamic_card_visibility()
        self._refresh_navigation_cards()
        self._sync_scene_file_status()

    def _sync_loaded_scene_details(
        self,
        scene: SceneWorkspace,
        template: TemplateConfig | None,
    ) -> None:
        if "scn_exam_paper" in self._loaded_detail_ids:
            self._exam_paper.set_scene(scene)
        if "scn_rules" in self._loaded_detail_ids:
            self._rules.set_scene(
                scene,
                template,
                mode_id=self._current_work_mode_id(),
            )
        if "scn_cleanup" in self._loaded_detail_ids:
            self._cleanup.set_scene(scene)
        if "scn_content" in self._loaded_detail_ids:
            self._content.set_scene(scene)

    def _on_scope_changed(self) -> None:
        self._mark_scene_detail_dirty()

    def _refresh_scene_overview(self) -> None:
        template = self._resolve_template_for_scene(self._current_scene)
        preview_context = self._template_preview_context_for_scene(
            self._current_scene,
        )
        self._overview.set_scene(
            self._current_scene,
            template=template,
            template_preview_action=preview_context.action,
        )

    def _mark_scene_detail_dirty(self) -> None:
        if self._current_scene is None:
            return
        self._refresh_scene_overview()
        self.bridge.set_current_scene(
            self._current_scene,
            config_id=self._current_scene.scene_id,
            path=self._current_scene_path,
            source=self._current_scene_source,
            source_type=self._current_scene_source_type,
            emit_signal=False,
        )
        self.bridge.mark_scene_dirty(recheck=False)
        self._refresh_navigation_cards()

    def _update_dynamic_card_visibility(self) -> None:
        """Show/hide scenario-specific nav cards."""
        scene = self._current_scene
        mode_id = self._current_work_mode_id()
        uses_plan_preview = _scene_uses_plan_preview_surface(
            scene,
            mode_id=mode_id,
        )
        overview_card = self._nav_cards.get("scn_overview")
        if overview_card is not None:
            overview_card.setVisible(not uses_plan_preview)
        exam_card = self._nav_cards.get("scn_exam_paper")
        if exam_card is not None:
            exam_card.setVisible(uses_plan_preview)
        if "scn_exam_paper" in self._loaded_detail_ids:
            if uses_plan_preview:
                if getattr(self._exam_paper, "_attached_plan_card", None) is None:
                    self._exam_paper.attach_plan_card(self._overview.take_scene_card())
            else:
                detached = self._exam_paper.detach_plan_card()
                if detached is not None:
                    self._overview.restore_scene_card(detached)
        content_card = self._nav_cards.get("scn_content")
        if content_card is not None:
            content_card.setVisible(
                _scene_should_show_content_card(scene, mode_id=mode_id)
            )
        selected_id = self._nav_rail.selected_card_id()
        selected_card = self._nav_cards.get(str(selected_id or ""))
        if selected_card is not None and selected_card.isHidden():
            self._nav_rail.select_card(self._default_visible_card_id())
        self._refresh_nav_section_headers()

    def _default_visible_card_id(self) -> str:
        for card_id in ("scn_exam_paper", "scn_overview", "scn_rules", "scn_content"):
            card = self._nav_cards.get(card_id)
            if card is not None and not card.isHidden():
                return card_id
        return "scn_rules"

    def _refresh_nav_section_headers(self) -> None:
        for section_id, card_ids in NAV_SECTION_CARD_GROUPS:
            header = self._nav_section_headers.get(section_id)
            if header is None:
                continue
            has_visible_card = any(
                (card := self._nav_cards.get(card_id)) is not None
                and not card.isHidden()
                for card_id in card_ids
            )
            header.setVisible(has_visible_card)

    def _on_scene_edited(self) -> None:
        self._refresh_scene_overview()
        was_dirty = (
            bool(self.bridge.is_scene_dirty())
            if hasattr(self.bridge, "is_scene_dirty")
            else False
        )
        self.bridge.set_current_scene(
            self._current_scene,
            config_id=self._current_scene.scene_id,
            path=self._current_scene_path,
            source=self._current_scene_source,
            source_type=self._current_scene_source_type,
            emit_signal=False,
        )
        self.bridge.mark_scene_dirty(recheck=False)
        self._sync_bound_template_from_scene()
        if was_dirty:
            self._refresh_navigation_cards()

    def _on_scene_family_defaults_applied(self) -> None:
        self._apply_scene(self._current_scene)
        self._on_scene_edited()

    def _sync_bound_template_from_scene(self) -> None:
        try:
            self._scene_session.publish_bound_template(self._current_scene)
        except Exception:
            return

    def on_scene_changed(self, scene: SceneWorkspace) -> None:
        if scene is None:
            return
        self._scene_session.accept_bridge_scene(scene)
        if (
            getattr(self, "_ignore_own_scene_changed", False)
            or self._restoring_scene_activation
        ):
            return
        self._refresh_scene_selector_options()
        self._apply_scene(scene)
        self._refresh_navigation_cards()

    def on_template_changed(self, template) -> None:
        if self._current_scene is None or self._restoring_scene_activation:
            return
        self._scene_session.accept_bridge_template(template)
        if "scn_rules" in self._loaded_detail_ids:
            self._rules.set_scene(
                self._current_scene,
                template,
                mode_id=self._current_work_mode_id(),
            )
        preview_context = self._template_preview_context_for_scene(
            self._current_scene,
        )
        self._overview.set_template_preview_action(preview_context.action)
        self._refresh_navigation_cards()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._shell.apply_theme(t)

        # Propagate to details
        for detail in self._detail_map.values():
            if hasattr(detail, "apply_theme"):
                detail.apply_theme()
        if hasattr(self, "_return_label"):
            self._return_label.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
            )
            _apply_template_button_contract((self._return_btn, "secondary"))
