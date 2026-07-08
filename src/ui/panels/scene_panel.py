"""
scene_panel — 场景配置面板（Master-Detail 架构）

与模板面板同构：左侧导航卡片 + 右侧可切换详情面板。
信息分层:
  Top:    场景概览
  Groups: 场景策略 / 资料包
"""

from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from html import escape
from pathlib import Path

from src.config import library as config_library
from src.config.scene import (
    ContentVisibilityRule,
    DeliveryPreset,
    ExamPaperConfig,
    FormatScopeConfig,
    SceneWorkspace,
    coerce_exam_paper_config,
)
from src.config.scene_family_application import (
    apply_planned_scene_family_defaults,
    has_planned_scene_family_application,
)
from src.config.feature_configs import (
    WatermarkConfig,
    OutputConfig,
)
from src.config.delivery_preset_display import (
    DELIVERY_PRESET_DISPLAY_LABELS,
    delivery_preset_display_name,
    delivery_preset_option_tooltip,
)
from src.config.style_field_descriptors import (
    scene_style_navigation_target_from_field_id,
)
from src.config.style_variant_semantics import (
    STYLE_VARIANTS,
    is_section_style_overridden,
)
from src.qt_api import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDesktopServices,
    QFileDialog,
    QFileSystemWatcher,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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
    FlowLayout,
    LibraryActionRow,
    MasterDetailShell,
    NavigationCard,
    SegmentedControl,
    ThemedRadioButton,
    apply_button_variant,
    build_button_stylesheet,
    build_text_input_stylesheet,
)
from src.shared.ui.card import Card
from src.shared.ui.dialogs import confirm, input_text
from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later, updates_suspended
from src.shared.ui.navigation_highlight import NavigationHighlighter
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem
from src.shared.ui.template_form_layout import (
    TemplateFormStack,
    template_form_row,
)
from src.shared.ui.text_area import TextArea
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toast import Toast
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.adapters.field_display_names import (
    field_display_context,
    field_display_name,
    navigation_issue_hint,
)
from src.ui.base_panel import BasePanel
from src.ui.bridge import navigation_intent_value
from src.ui.panels.workbench.scene_presets import (
    SCENE_METAS,
)
from src.config.builtin_templates import create_builtin_template
from src.config.library import (
    default_scene_entry,
    default_scene_descriptor,
    get_scene_entry,
    get_template_entry,
    list_scene_descriptors,
    load_scene_from_library,
    load_template_from_library,
    save_scene_to_library,
)
from src.config.template import TemplateConfig
from src.ui.panels.scene_summary_projection import (
    FAILURE_POLICY_LABELS,
    FORMAT_DISPLAY_LABELS,
    LATEX_POLICY_LABELS,
    MARKDOWN_POLICY_LABELS,
    PRESERVATION_MODE_LABELS,
    SCENE_SCOPE_ZONE_DISPLAY_LABELS,
    build_compliance_summary_items,
    build_delivery_summary_items,
    build_input_profile_summary_items,
    build_scene_overview_summary_items,
    build_scene_sample_fixture_detail_text,
    build_scene_scope_summary_items,
    build_scene_style_override_summary_items,
    recommended_object_preflight_targets_for_scene,
    scene_request_cell_count_text,
    scene_request_cell_count_tooltip,
    scene_request_cell_evidence_status_text,
    scene_request_cell_evidence_status_tooltip,
    scene_request_cell_filter_options,
    scene_request_cell_fixture_specs_for_scene,
    scene_request_cell_list_item_projection,
    scene_request_cell_matches_filter,
    scene_sample_fixture_list_item_projection,
    scene_sample_fixture_specs_for_scene,
    scene_sample_fixture_library_status_text,
    scene_sample_fixture_library_status_tooltip,
    scene_application_boundary_display_name,
)
from src.ui.panels.scene_delivery_helpers import (
    _DELIVERY_PRESET_TEMPLATE_MAP,
    _VISIBILITY_ACTION_OPTIONS,
    _VISIBILITY_SELECTOR_RE,
    _append_visibility_rule_text,
    _apply_delivery_preset_template_artifacts,
    _build_delivery_preset_template_rules,
    _build_delivery_validation_items,
    _delivery_preset_template_label,
    _extract_visibility_selector_input,
    _format_visibility_rules,
    _parse_visibility_rules,
    _populate_delivery_preset_template_combo,
    _populate_delivery_variable_combo,
    _populate_visibility_selector_combo,
    _safe_delivery_preset_id,
    _scene_compatible_template_ids,
    _scene_current_template_id,
    _scene_family_delivery_preview_tooltip,
    _template_display_label,
    _template_label_with_id,
    _template_option_tooltip,
)
from src.ui.panels.scene_material_requirement_block import (
    _MaterialRequirementBlock,
    _build_material_schema_validation_items,
    _profile_material_schema_ids,
)
from src.ui.panels.scene_style_override_service import (
    restore_scene_section_style_to_template,
    scene_section_style_override_projection,
    scene_style_variants_for_scene,
    scene_uses_reference_format,
    set_scene_section_style_override,
)
from src.ui.panels.scene_scope_service import apply_scene_scope_zone_states
from src.ui.panels.scene_scope_sections import SceneScopeZoneSection
from src.ui.panels.scene_style_rules_block import SceneStyleRulesBlock
from src.ui.panels.style_object_projection_builders import (
    build_scene_section_style_projection,
)
from src.ui.panels.scene_overview_projection import (
    SceneOverviewRowSpec,
    SceneRiskNoticeSpec,
    SceneRunStepSpec,
    build_scene_overview_spec,
)
from src.ui.panels.template_format import build_template_preview_context
from src.ui.panels.template_reference_detail import ReferenceDetail
from src.shared.engine.object_preflight import OBJECT_PREFLIGHT_SCAN_TARGETS
from src.shared.engine.exam_paper_style import (
    EXAM_AI_PROMPT_OPTIONS,
    builtin_exam_blank_style_options,
    create_exam_blank_master_copy,
    ensure_current_exam_blank_master_docx,
    exam_ai_prompt_text,
    exam_blank_style_label,
    exam_blank_style_options,
    exam_blank_style_preview_lines,
    import_exam_blank_master_docx,
    resolve_exam_blank_style,
    write_exam_blank_style_sample_docx,
)
from src.shared.engine.scene_sample_docx_builder import (
    DEFAULT_SCENE_SAMPLE_FIXTURE_DIR,
    build_scene_sample_docx_library,
)
from src.shared.ui.base_dialog import BaseDialog


def _open_local_path(path: Path) -> bool:
    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))))


def _safe_scene_file_stem(value: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(ch if ch not in forbidden else "_" for ch in str(value or "").strip())
    cleaned = cleaned.strip(" ._")
    return cleaned or "scene"


# ═══════════════════════════════════════════════════════════════════════
#  Card definitions
# ═══════════════════════════════════════════════════════════════════════

CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    # Fixed Layer 1: Identity
    "scn_overview":    ("场景概览",    "mountain-snow"),
    # Scenario-specific assembly pages
    "scn_exam_paper":  ("试卷装配",    "file-text"),
    # Fixed Layer 2: Scenario rules
    "scn_rules":       ("场景规则",    "sliders-horizontal"),
    "scn_cleanup":     ("风险检查",    "scan"),
    "scn_content":     ("资料包与填充", "pen-tool"),
    "scn_output":      ("生成结果",    "folder-output"),
}

CARD_ORDER = (
    "scn_overview",
    "scn_exam_paper",
    "scn_rules",
    "scn_content",
)

FIXED_CARDS = (
    "scn_overview",
    "scn_exam_paper",
    "scn_rules",
)
FORMAT_TEMPLATE_CARDS = (
    "scn_exam_paper",
    "scn_rules",
)
INPUT_MATERIAL_CARDS = ("scn_content",)
NAV_SECTION_CARD_GROUPS = (
    ("format_template", FORMAT_TEMPLATE_CARDS),
    ("input_material", INPUT_MATERIAL_CARDS),
)

_SCENE_RULES_ALIAS_CARDS = frozenset(
    (
        "scn_scope",
        "scn_style_rules",
        "scn_reference",
        "scn_output",
    )
)


def _normalise_scene_detail_card_id(card_id: str) -> str:
    normalized = str(card_id or "").strip()
    return "scn_rules" if normalized in _SCENE_RULES_ALIAS_CARDS else normalized

_SCENE_SELECTOR_GROUP_PREFIX = "__scene_group__:"
_SCENE_SELECTOR_MY_GROUP = f"{_SCENE_SELECTOR_GROUP_PREFIX}mine"
_SCENE_SELECTOR_BUILTIN_GROUP = f"{_SCENE_SELECTOR_GROUP_PREFIX}builtin"

_NAV_SCOPE_MODE_LABELS = {
    "follow_template": "按模板默认",
    "body_only": "只处理正文",
    "full_document": "处理全文",
    "confirm_before_apply": "每次执行前选择",
}

_NAV_OUTPUT_FIELDS = (
    "final_docx",
    "compare_docx",
    "report_json",
    "report_markdown",
    "material_manifest",
    "material_package",
)


def _nav_display_id(value: object, mapping: dict[str, str] | None = None) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if mapping and normalized in mapping:
        return mapping[normalized]
    return normalized.replace("_", " ")


def _is_scene_selector_group(value: object) -> bool:
    return str(value or "").strip().startswith(_SCENE_SELECTOR_GROUP_PREFIX)


def _builtin_scene_id_set() -> set[str]:
    return {str(meta.scene_id or "").strip() for meta in SCENE_METAS}


def _nav_join(parts: Sequence[str]) -> str:
    return " · ".join(part for part in parts if str(part or "").strip())


def _nav_scope_subtitle(mode: str) -> str:
    return _NAV_SCOPE_MODE_LABELS.get(mode, mode or "按模板默认")


def _nav_format_summary(values: Sequence[object]) -> str:
    labels = [_nav_display_id(value, FORMAT_DISPLAY_LABELS) for value in values]
    labels = [label for label in labels if label]
    if not labels:
        return "Word 文档"
    if len(labels) <= 2:
        return "、".join(labels)
    return "、".join(labels[:2]) + f"等 {len(labels)} 种输入"


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

EXAM_BLANK_STYLE_OPTIONS: tuple[tuple[str, str], ...] = builtin_exam_blank_style_options()

EXAM_RUNTIME_FIELD_OPTIONS: tuple[tuple[str, str], ...] = (
    ("title", "标题"),
    ("subject", "科目"),
    ("grade", "年级"),
    ("duration", "考试时间"),
    ("total_score", "满分"),
    ("class_name", "班级"),
    ("teacher", "命题人"),
    ("exam_date", "日期"),
)

EXAM_DEFAULT_RUNTIME_FIELDS = ("title", "subject", "grade", "duration", "total_score")


def _set_combo_by_data(combo: StyledComboBox, target) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == target:
            combo.setCurrentIndex(i)
            return


def _populate_combo(combo: StyledComboBox, items: dict[str, str]) -> None:
    combo.clear()
    for value, label in items.items():
        combo.addItem(label, value)


def _option_label(options: Sequence[tuple[str, str]], value: str, fallback: str = "") -> str:
    target = str(value or "").strip()
    for option_value, label in options:
        if option_value == target:
            return label
    return fallback or target


def _scene_is_exam(scene: SceneWorkspace | None) -> bool:
    if scene is None:
        return False
    parts = (
        getattr(scene, "scene_id", ""),
        getattr(scene, "category", ""),
        getattr(scene, "category_label", ""),
        getattr(scene, "name", ""),
        getattr(scene, "description", ""),
    )
    text = " ".join(str(part or "").lower() for part in parts)
    return any(
        token in text
        for token in (
            "exam",
            "exam paper",
            "test paper",
            "test_paper",
            "question paper",
            "question_paper",
            "试卷",
            "考试",
            "测验",
            "试题",
        )
    )


def _scene_uses_reference_format(scene: SceneWorkspace | None) -> bool:
    return scene_uses_reference_format(scene)


def _generic_style_variants_for_scene(
    scene: SceneWorkspace | None,
    template: TemplateConfig | None = None,
):
    return scene_style_variants_for_scene(scene, template)


def _scene_should_show_content_card(scene: SceneWorkspace | None) -> bool:
    if scene is None or not _scene_is_exam(scene):
        return True
    return _scene_has_material_content_contract(scene)


def _scene_has_material_content_contract(scene: SceneWorkspace | None) -> bool:
    if scene is None:
        return False
    profile = getattr(scene, "input_source_profile", None)
    switches = getattr(scene, "module_switches", {}) or {}
    watermark = getattr(scene, "watermark", None)
    return bool(
        switches.get("content_fill", False)
        or getattr(profile, "require_material_package", False)
        or str(getattr(profile, "material_schema_id", "") or "").strip()
        or any(str(item or "").strip() for item in getattr(profile, "material_schema_ids", ()) or ())
        or any(str(item or "").strip() for item in getattr(profile, "required_material_fields", ()) or ())
        or any(str(item or "").strip() for item in getattr(profile, "required_image_roles", ()) or ())
        or bool(getattr(watermark, "enabled", False))
        or str(getattr(watermark, "text", "") or "").strip()
    )


def _ensure_exam_paper_config(scene: SceneWorkspace) -> ExamPaperConfig:
    config = coerce_exam_paper_config(getattr(scene, "exam_paper", None))
    scene.exam_paper = config
    return config


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
            selector_type="semantic_block",
            selector="answer",
            action="remove",
        ),
        ContentVisibilityRule(
            rule_id="hide_explanations",
            label="隐藏解析",
            selector_type="semantic_block",
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
            if str(getattr(preset, "preset_id", "") or "").strip() not in {"student", "answer"}
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
            if str(getattr(preset, "preset_id", "") or "").strip() not in {"answer", "answer_key"}
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
    selected = next(
        (
            preset
            for preset in scene.delivery_presets
            if str(getattr(preset, "preset_id", "") or "").strip()
            == scene.default_delivery_preset_id
        ),
        scene.delivery_presets[0],
    )
    scene.output = copy.deepcopy(getattr(selected, "artifacts", OutputConfig()))


def _apply_template_line_edit_contract(*line_edits: QLineEdit) -> None:
    stylesheet = build_text_input_stylesheet(get_theme())
    for line_edit in line_edits:
        apply_size_class(line_edit, "md")
        line_edit.setAttribute(Qt.WA_StyledBackground, True)
        line_edit.setStyleSheet(stylesheet)


def _apply_template_button_contract(*buttons: tuple[QPushButton, str]) -> None:
    stylesheet = build_button_stylesheet(get_theme())
    for button, variant in buttons:
        apply_button_variant(button, variant)
        apply_size_class(button, "md")
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(stylesheet)


def _format_request_cell_tooltip(cell) -> str:
    return scene_request_cell_list_item_projection(cell).tooltip


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


_SCENE_DETAIL_SUMMARY_COPY: dict[str, dict[str, str]] = {
    "风险检查": {
        "main_value": "执行前检查",
        "main_detail": "配置 Markdown 修复、对象预检、报告粒度和高风险处理。",
        "risk_value": "高风险先提醒",
        "risk_detail": "宏、嵌入对象、修订等会按策略提醒、跳过或阻断。",
    },
    "资料包与填充": {
        "main_value": "文件和资料包",
        "main_detail": "声明可接受输入、资料 Schema、内容显隐和水印。",
        "risk_value": "资料缺失会影响输出",
        "risk_detail": "缺字段、缺图片或未识别资料规则会进入执行前问题队列。",
    },
    "生成结果": {
        "main_value": "交付版本",
        "main_detail": "配置最终稿、对比稿、报告、资料清单和命名规则。",
        "risk_value": "输出路径需确认",
        "risk_detail": "路径冲突、目录不可写或命名过长会在执行前提示。",
    },
}


def _scene_detail_summary_items(
    title: str,
    description: str,
) -> tuple[SummaryGridItem, ...]:
    copy = _SCENE_DETAIL_SUMMARY_COPY.get(title, {})
    return (
        SummaryGridItem(
            key="main_controls",
            label="主要控件",
            value=copy.get("main_value", "下方编辑"),
            detail=copy.get("main_detail", description),
            variant="info",
        ),
        SummaryGridItem(
            key="risk_note",
            label="风险说明",
            value=copy.get("risk_value", "有风险会提醒"),
            detail=copy.get(
                "risk_detail",
                "阻断、跳过或人工确认会在风险检查和执行报告里说明。",
            ),
            variant="warning",
        ),
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
        self._navigation_highlighter = NavigationHighlighter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._card = Card(parent=self)
        self._card.set_header(title, icon_name=icon_name)

        self._desc_label = QLabel(description)
        self._desc_label.setObjectName("scn_form_desc")
        self._desc_label.setWordWrap(True)
        self._card.add_widget(self._desc_label)

        self._detail_summary = SummaryGrid(columns=2, parent=self._card)
        self._detail_summary.set_items(_scene_detail_summary_items(title, description))
        self._card.add_widget(self._detail_summary)

        layout.addWidget(self._card)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        if self.layout() is not None:
            self.layout().setSpacing(t.template_detail_section_gap)
        self._desc_label.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")

    def _add_form_stack(self, rows: list[QWidget]) -> None:
        self._card.add_widget(TemplateFormStack(rows, parent=self._card))

    def _highlight_navigation_widget(self, widget: QWidget, label: str) -> None:
        self._navigation_highlighter.highlight(
            widget,
            label,
            display_label=(
                field_display_context(label).label_with_group()
                or field_display_name(label)
            ),
        )


class _ExamPaperPreviewDialog(BaseDialog):
    """Small preview dialog for the selected blank exam-paper style."""

    def __init__(self, config: ExamPaperConfig, style_id: str, parent=None):
        super().__init__("试卷样式预览", icon_style="info", parent=parent)
        self.setMinimumWidth(620)
        self.setMaximumWidth(760)
        self._config = copy.deepcopy(config)
        self._style_id = str(style_id or "default_exam")

        mode_row = QWidget(self)
        mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(14)
        self._student_radio = ThemedRadioButton("学生卷", mode_row)
        self._answer_radio = ThemedRadioButton("答案版", mode_row)
        self._student_radio.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._student_radio)
        self._mode_group.addButton(self._answer_radio)
        mode_layout.addWidget(self._student_radio)
        mode_layout.addWidget(self._answer_radio)
        mode_layout.addStretch(1)
        self.content_layout.addWidget(mode_row)

        self._page_label = QLabel(self)
        self._page_label.setObjectName("exam_paper_style_preview_page")
        self._page_label.setWordWrap(True)
        self.content_layout.addWidget(self._page_label)

        self._student_radio.toggled.connect(self._refresh_preview)
        self._answer_radio.toggled.connect(self._refresh_preview)
        self._refresh_preview()

        ok_btn = self.add_primary_button("确定")
        ok_btn.clicked.connect(self.accept)

    def _refresh_preview(self, *_args) -> None:
        answer_version = self._answer_radio.isChecked()
        self._page_label.setText(
            "\n".join(
                exam_blank_style_preview_lines(
                    self._style_id,
                    self._config,
                    answer_version=answer_version,
                )
            )
        )
        self._apply_preview_style()

    def _apply_preview_style(self) -> None:
        t = get_theme()
        self._page_label.setStyleSheet(
            f"font-size: {t.font_size_md}px; color: {t.text_primary};"
            f"background: {t.bg_input}; border: 1px solid {t.border_light};"
            f"border-radius: {t.radius_sm}px; padding: 16px 18px;"
            "line-height: 150%;"
        )


class _ExamPaperDetail(_SimpleFormDetail):
    """Scene-specific assembly rules for exam papers."""

    execute_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(
            "试卷装配",
            "file-text",
            "选择试卷母版，生成样张或导入自己的 Word 母版。",
            parent,
        )
        self._current_scene: SceneWorkspace | None = None
        self._open_sample_path_handler = _open_local_path
        self._runtime_checks: dict[str, QCheckBox] = {}
        self._detail_summary.setVisible(False)

        self._reset_btn = QPushButton("恢复默认", self._card)
        self._reset_btn.clicked.connect(self._reset_defaults)
        self._workbench_btn = QPushButton("去工作台填写", self._card)
        self._workbench_btn.clicked.connect(self.execute_requested.emit)
        self._card.add_header_action(self._reset_btn)
        self._card.add_header_action(self._workbench_btn)
        self._card.setVisible(False)

        self._blank_style = StyledComboBox(self)
        for value, label in exam_blank_style_options():
            self._blank_style.addItem(label, value)
        self._blank_style.set_full_width_mode(True)
        self._blank_style.setToolTip("选择试卷的空白外框样式。")
        self._blank_style.currentIndexChanged.connect(self._on_blank_style_changed)

        self._master_card = Card(parent=self)
        self._master_card.set_header("试卷装配", icon_name="file-text", show_separator=False)

        self._master_card.add_widget(self._blank_style)

        self._style_action_row = LibraryActionRow(
            self._master_card,
            object_name="scn_exam_master_action_row",
        )
        self._default_master_btn = self._style_action_row.add_action(
            "default",
            "默认母版",
            object_name="scn_exam_master_default_btn",
            icon_name="refresh-ccw",
            callback=self._reset_defaults,
        )
        self._copy_style_btn = self._style_action_row.add_action(
            "copy",
            "创建副本",
            object_name="scn_exam_master_copy_btn",
            icon_name="copy",
            callback=self._copy_blank_style,
        )
        self._open_master_folder_btn = self._style_action_row.add_action(
            "open_folder",
            "打开母版文件夹",
            object_name="scn_exam_master_open_folder_btn",
            icon_name="folder-open",
            callback=self._open_blank_master_folder,
        )
        self._open_master_btn = self._style_action_row.add_action(
            "open",
            "打开母版",
            object_name="scn_exam_master_open_btn",
            icon_name="file-text",
            callback=self._open_blank_master,
        )
        self._sample_docx_btn = self._style_action_row.add_action(
            "sample",
            "生成样张",
            object_name="scn_exam_master_sample_btn",
            icon_name="download",
            callback=self._generate_sample_docx,
        )
        self._import_style_btn = self._style_action_row.add_action(
            "import",
            "导入母版",
            object_name="scn_exam_master_import_btn",
            icon_name="plus",
            callback=self._import_blank_master,
        )
        self._default_master_btn.setToolTip("切回内置默认试卷母版。")
        self._copy_style_btn.setToolTip("复制内置母版为当前场景可修改的副本。")
        self._open_master_folder_btn.setToolTip("打开当前母版所在文件夹。")
        self._open_master_btn.setToolTip("打开当前选中的 Word 母版文件。")
        self._sample_docx_btn.setToolTip("用当前母版生成一份示例试卷。")
        self._import_style_btn.setToolTip("选择已有的 .docx 试卷母版并设为当前场景样式。")
        self._master_card.add_widget(self._style_action_row)

        self._preview_card = Card(parent=self)
        self._preview_card.set_header("母版预览", icon_name="eye", show_separator=False)
        self._preview_mode_control = SegmentedControl(parent=self._preview_card)
        self._preview_mode_control.setObjectName("scn_exam_master_preview_mode")
        self._preview_mode_control.add_segment("学生卷", "student")
        self._preview_mode_control.add_segment("答案版", "answer")
        self._preview_mode_control.setFixedWidth(220)
        self._preview_mode_control.setToolTip("学生卷预览母版卷面；答案速查仅预览内容，不修改生成结果设置。")
        self._preview_card.add_header_action(self._preview_mode_control)

        self._preview_canvas = QFrame(self._preview_card)
        self._preview_canvas.setObjectName("scn_exam_master_preview_canvas")
        preview_layout = QVBoxLayout(self._preview_canvas)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(0)

        self._preview_page = QLabel("", self._preview_canvas)
        self._preview_page.setObjectName("scn_exam_master_preview_page")
        self._preview_page.setWordWrap(True)
        self._preview_page.setTextFormat(Qt.RichText)
        self._preview_page.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._preview_page.setMinimumHeight(260)
        self._preview_page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        preview_layout.addWidget(self._preview_page)
        self._preview_card.add_widget(self._preview_canvas)

        self._preview_mode_control.current_changed.connect(self._refresh_master_preview)

        self._prompt_card = Card(parent=self)
        self._prompt_card.set_header("AI 提示词", icon_name="sparkles", show_separator=False)
        self._copy_prompt_btn = QPushButton("复制提示词", self._prompt_card)
        self._copy_prompt_btn.clicked.connect(self._copy_current_exam_prompt)
        self._prompt_card.add_header_action(self._copy_prompt_btn)

        self._prompt_mode_control = SegmentedControl(parent=self._prompt_card)
        self._prompt_mode_control.setObjectName("scn_exam_ai_prompt_mode")
        for prompt_id, label, _text in EXAM_AI_PROMPT_OPTIONS:
            self._prompt_mode_control.add_segment(label, prompt_id)
        self._prompt_mode_control.setFixedWidth(240)
        self._prompt_card.add_widget(self._prompt_mode_control)

        self._prompt_area = TextArea(min_height=260, max_height=420, parent=self._prompt_card)
        self._prompt_area.set_text(exam_ai_prompt_text("markdown"))
        self._prompt_area._text_edit.setReadOnly(True)
        self._prompt_area._text_edit.setObjectName("scn_exam_ai_prompt_text")
        self._prompt_card.add_widget(self._prompt_area)
        self._prompt_mode_control.current_changed.connect(self._refresh_exam_prompt)

        self._runtime_fields_widget = QWidget(self)
        self._runtime_fields_widget.setVisible(False)
        self._runtime_fields_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._runtime_fields_widget.setMinimumHeight(40)
        self._runtime_fields_widget.setMaximumHeight(88)
        runtime_layout = FlowLayout(self._runtime_fields_widget, h_spacing=10, v_spacing=8)
        runtime_layout.setContentsMargins(0, 0, 0, 0)
        for field_id, label in EXAM_RUNTIME_FIELD_OPTIONS:
            checkbox = QCheckBox(label, self._runtime_fields_widget)
            checkbox.setCursor(Qt.PointingHandCursor)
            checkbox.toggled.connect(self._on_runtime_fields_changed)
            self._runtime_checks[field_id] = checkbox
            runtime_layout.addWidget(checkbox)

        self._live_summary = QLabel("", self)
        self._live_summary.setObjectName("scn_exam_paper_live_summary")
        self._live_summary.setWordWrap(True)
        self._live_summary.setVisible(False)

        self._runtime_note = QLabel(
            "场景页只保存长期装配规则；具体标题、科目、考试时间等每次执行时再填写。",
            self,
        )
        self._runtime_note.setWordWrap(True)
        self._runtime_note.setVisible(False)

        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(1, self._master_card)
            layout.insertWidget(2, self._preview_card)
            layout.insertWidget(3, self._prompt_card)
        self._apply_theme()

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        config = _ensure_exam_paper_config(scene)
        self._is_syncing = True
        try:
            self._refresh_blank_style_options(config)
            _set_combo_by_data(self._blank_style, config.blank_style_id)
            selected_fields = set(config.runtime_fields or EXAM_DEFAULT_RUNTIME_FIELDS)
            for field_id, checkbox in self._runtime_checks.items():
                checkbox.setChecked(field_id in selected_fields)
            self._refresh_style_status(config)
            self._refresh_live_summary(config)
        finally:
            self._is_syncing = False

    def focus_navigation_field(self, field_id: str) -> bool:
        widgets = {
            "exam_paper.blank_style_id": self._blank_style,
            "exam_paper.runtime_fields": self._workbench_btn,
        }
        widget = widgets.get(str(field_id or "").strip())
        if widget is None:
            return False
        self._highlight_navigation_widget(widget, field_id)
        return True

    def _refresh_blank_style_options(self, config: ExamPaperConfig) -> None:
        current = str(config.blank_style_id or "default_exam")
        self._blank_style.clear()
        for value, label in exam_blank_style_options(config):
            self._blank_style.addItem(label, value)
        _set_combo_by_data(self._blank_style, current)

    def _refresh_style_status(self, config: ExamPaperConfig | None = None) -> None:
        if self._current_scene is None:
            return
        config = config or _ensure_exam_paper_config(self._current_scene)
        style_id = str(self._blank_style.currentData() or config.blank_style_id or "default_exam")
        resolve_exam_blank_style(config, style_id)
        self._refresh_master_preview(config=config, style_id=style_id)

    def _config(self) -> ExamPaperConfig | None:
        if self._current_scene is None:
            return None
        return _ensure_exam_paper_config(self._current_scene)

    def _on_blank_style_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        config = self._config()
        if config is None:
            return
        config.blank_style_id = str(self._blank_style.currentData() or "default_exam")
        self._refresh_style_status(config)
        self._refresh_live_summary(config)
        self.scene_edited.emit()

    def _open_blank_master(self) -> None:
        config = self._config()
        if config is None:
            return
        style_id = str(self._blank_style.currentData() or config.blank_style_id or "default_exam")
        try:
            master_path = ensure_current_exam_blank_master_docx(config, style_id)
        except Exception as exc:
            Toast.show_error(f"母版打开失败: {exc}")
            return
        if self._open_sample_path_handler(master_path):
            Toast.show_success(f"已打开母版: {master_path.name}")
        else:
            Toast.show_warning(f"母版已生成，但无法自动打开: {master_path}")

    def _open_blank_master_folder(self) -> None:
        config = self._config()
        if config is None:
            return
        style_id = str(self._blank_style.currentData() or config.blank_style_id or "default_exam")
        try:
            master_path = ensure_current_exam_blank_master_docx(config, style_id)
        except Exception as exc:
            Toast.show_error(f"母版文件夹打开失败: {exc}")
            return
        folder_path = master_path.parent
        if self._open_sample_path_handler(folder_path):
            Toast.show_success(f"已打开母版文件夹: {folder_path.name}")
        else:
            Toast.show_warning(f"无法自动打开母版文件夹: {folder_path}")

    def _generate_sample_docx(self) -> None:
        config = self._config()
        if config is None:
            return
        style_id = str(self._blank_style.currentData() or config.blank_style_id or "default_exam")
        output_dir = config_library.SCENE_LIBRARY_DIR.parent / "exam_samples"
        try:
            sample_path = write_exam_blank_style_sample_docx(
                style_id,
                output_dir,
                config=config,
            )
        except Exception as exc:
            Toast.show_error(f"样张生成失败: {exc}")
            return
        if self._open_sample_path_handler(sample_path):
            Toast.show_success(f"已生成样张: {sample_path.name}")
        else:
            Toast.show_warning(f"样张已生成，但无法自动打开: {sample_path}")

    def _copy_blank_style(self) -> None:
        if self._current_scene is None:
            return
        config = _ensure_exam_paper_config(self._current_scene)
        style = create_exam_blank_master_copy(
            config,
            str(self._blank_style.currentData() or config.blank_style_id or "default_exam"),
        )
        config.custom_blank_styles.append(style)
        config.blank_style_id = style.style_id
        self._is_syncing = True
        try:
            self._refresh_blank_style_options(config)
            _set_combo_by_data(self._blank_style, style.style_id)
            self._refresh_style_status(config)
            self._refresh_live_summary(config)
        finally:
            self._is_syncing = False
        copied_path = ensure_current_exam_blank_master_docx(config, style.style_id)
        if self._open_sample_path_handler(copied_path):
            Toast.show_success(f"已创建并打开试卷母版副本: {style.label}")
        else:
            Toast.show_warning(f"已创建试卷母版副本，但无法自动打开: {copied_path}")
        self.scene_edited.emit()

    def _import_blank_master(self) -> None:
        if self._current_scene is None:
            return
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "导入试卷母版",
            str(config_library.SCENE_LIBRARY_DIR.parent),
            "Word 文档 (*.docx)",
        )
        if not file_path:
            return

        config = _ensure_exam_paper_config(self._current_scene)
        try:
            style = import_exam_blank_master_docx(
                config,
                file_path,
                base_style_id=str(
                    self._blank_style.currentData()
                    or config.blank_style_id
                    or "default_exam"
                ),
            )
        except Exception as exc:
            Toast.show_error(f"母版导入失败: {exc}")
            return

        config.custom_blank_styles.append(style)
        config.blank_style_id = style.style_id
        self._is_syncing = True
        try:
            self._refresh_blank_style_options(config)
            _set_combo_by_data(self._blank_style, style.style_id)
            self._refresh_style_status(config)
            self._refresh_live_summary(config)
        finally:
            self._is_syncing = False
        Toast.show_success(f"已导入并选用试卷母版: {style.label}")
        self.scene_edited.emit()

    def _on_runtime_fields_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        config = self._config()
        if config is None:
            return
        selected = [
            field_id
            for field_id, _label in EXAM_RUNTIME_FIELD_OPTIONS
            if self._runtime_checks[field_id].isChecked()
        ]
        if not selected:
            selected = list(EXAM_DEFAULT_RUNTIME_FIELDS)
            self._is_syncing = True
            try:
                for field_id, checkbox in self._runtime_checks.items():
                    checkbox.setChecked(field_id in selected)
            finally:
                self._is_syncing = False
        config.runtime_fields = selected
        self._refresh_live_summary(config)
        self.scene_edited.emit()

    def _refresh_exam_prompt(self, *_args) -> None:
        prompt_id = str(self._prompt_mode_control.current_data() or "markdown")
        self._prompt_area.set_text(exam_ai_prompt_text(prompt_id))
        refresh_layout_chain_later(self)

    def _copy_current_exam_prompt(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._prompt_area.get_text())
        Toast.show_success("已复制提示词")

    def _refresh_master_preview(
        self,
        *_args,
        config: ExamPaperConfig | None = None,
        style_id: str | None = None,
    ) -> None:
        if not hasattr(self, "_preview_page"):
            return
        if self._current_scene is None:
            self._preview_page.setText("")
            return
        config = config or _ensure_exam_paper_config(self._current_scene)
        selected_style_id = str(
            style_id
            or self._blank_style.currentData()
            or config.blank_style_id
            or "default_exam"
        )
        answer_version = self._preview_mode_control.current_data() == "answer"
        lines = exam_blank_style_preview_lines(
            selected_style_id,
            config,
            answer_version=answer_version,
        )
        self._preview_page.setText(self._format_master_preview_html(lines))
        refresh_layout_chain_later(self)

    def _format_master_preview_html(self, lines: list[str]) -> str:
        t = get_theme()
        if not lines:
            return ""

        safe_lines = [escape(str(line or "")) for line in lines]
        style_label = safe_lines[0] if safe_lines else ""
        title = safe_lines[1] if len(safe_lines) > 1 else ""
        metadata = safe_lines[2] if len(safe_lines) > 2 else ""
        footer = safe_lines[-1] if len(safe_lines) > 4 else ""
        body_lines = safe_lines[3:-1] if len(safe_lines) > 4 else safe_lines[3:]

        body_html: list[str] = []
        raw_body_lines = lines[3:-1] if len(lines) > 4 else lines[3:]
        for raw, text in zip(raw_body_lines, body_lines):
            raw_text = str(raw or "").strip()
            if not raw_text:
                continue
            if raw_text == "答案速查":
                body_html.append(
                    f'<div align="center" style="margin-top:6px; '
                    f'margin-bottom:8px; font-weight:700; '
                    f'color:{t.primary};">{text}</div>'
                )
            elif raw_text.startswith("注意事项"):
                body_html.append(
                    f'<div style="margin-top:8px; color:{t.text_secondary}; '
                    f'font-size:{t.font_size_sm}px;">{text}</div>'
                )
            elif re.match(r"^[一二三四五六七八九十]+、", raw_text):
                body_html.append(
                    f'<div style="margin-top:10px; font-weight:700; '
                    f'color:{t.text_primary};">{text}</div>'
                )
            elif re.match(r"^\\d+[.、]", raw_text):
                body_html.append(
                    f'<div style="margin-top:5px; color:{t.text_primary};">{text}</div>'
                )
            elif raw_text.startswith("学生卷"):
                body_html.append(
                    f'<div style="margin-top:12px; color:{t.text_secondary}; '
                    f'font-weight:600;">{text}</div>'
                )
            else:
                body_html.append(
                    f'<div style="margin-top:5px; color:{t.text_primary};">{text}</div>'
                )

        return (
            f'<div style="font-family: Microsoft YaHei, SimSun, sans-serif;">'
            f'<div style="font-size:{t.font_size_sm}px; color:{t.text_secondary}; '
            f'margin-bottom:8px;">{style_label}</div>'
            f'<div align="center" style="font-size:{t.font_size_lg}px; '
            f'font-weight:700; color:{t.text_primary}; margin-bottom:8px;">{title}</div>'
            f'<div style="font-size:{t.font_size_sm}px; color:{t.text_secondary}; '
            f'padding:7px 0; border-top:1px solid {t.divider}; '
            f'border-bottom:1px solid {t.divider};">{metadata}</div>'
            f'<div style="font-size:{t.font_size_md}px; line-height:150%; '
            f'margin-top:12px;">{"".join(body_html)}</div>'
            f'<div align="right" style="font-size:{t.font_size_sm}px; '
            f'color:{t.text_hint}; margin-top:14px; padding-top:8px; '
            f'border-top:1px solid {t.divider};">{footer}</div>'
            "</div>"
        )

    def _reset_defaults(self) -> None:
        if self._current_scene is None:
            return
        current = _ensure_exam_paper_config(self._current_scene)
        config = ExamPaperConfig(
            blank_style_id="default_exam",
            question_structure_mode=current.question_structure_mode,
            answer_policy=current.answer_policy,
            runtime_fields=list(current.runtime_fields or EXAM_DEFAULT_RUNTIME_FIELDS),
        )
        self._current_scene.exam_paper = config
        self.set_scene(self._current_scene)
        self.scene_edited.emit()

    def _refresh_live_summary(self, config: ExamPaperConfig | None = None) -> None:
        if self._current_scene is None:
            self._live_summary.setText("")
            return
        config = config or _ensure_exam_paper_config(self._current_scene)
        blank = exam_blank_style_label(config.blank_style_id, config)
        fields = [
            _option_label(EXAM_RUNTIME_FIELD_OPTIONS, field_id, field_id)
            for field_id in config.runtime_fields
            if str(field_id or "").strip()
        ]
        field_text = "、".join(fields) if fields else "标题、科目、年级、考试时间、满分"
        self._live_summary.setText(
            f"当前会使用“{blank}”；工作台会填写：{field_text}。"
        )
        refresh_layout_chain_later(self)

    def _apply_theme(self) -> None:
        super()._apply_theme()
        t = get_theme()
        if hasattr(self, "_reset_btn"):
            stylesheet = build_button_stylesheet(t)
            for button, variant in (
                (self._reset_btn, "secondary"),
                (self._workbench_btn, "primary"),
            ):
                button.setStyleSheet(stylesheet)
                apply_button_variant(button, variant)
        if hasattr(self, "_live_summary"):
            self._live_summary.setStyleSheet(
                f"font-size: {t.font_size_md}px; color: {t.text_primary};"
                f"background: {t.bg_selected}; border: 1px solid {t.border_light};"
                f"border-radius: {t.radius_sm}px; padding: 8px 10px;"
            )
        if hasattr(self, "_preview_canvas"):
            self._preview_canvas.setStyleSheet(
                f"QFrame#scn_exam_master_preview_canvas {{"
                f"background: {t.bg_window}; border: none;"
                f"border-radius: {t.radius_sm}px;"
                f"}}"
            )
        if hasattr(self, "_copy_prompt_btn"):
            self._copy_prompt_btn.setStyleSheet(build_button_stylesheet(t))
            apply_button_variant(self._copy_prompt_btn, "secondary")
        if hasattr(self, "_preview_page"):
            self._preview_page.setStyleSheet(
                f"font-size: {t.font_size_md}px; color: {t.text_primary};"
                f"background: {t.bg_card}; border: 1px solid {t.border_light};"
                f"border-radius: {t.radius_sm}px; padding: 22px 24px;"
            )
        if hasattr(self, "_runtime_note"):
            self._runtime_note.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
            )
        if hasattr(self, "_runtime_checks"):
            stylesheet = build_checkbox_stylesheet(t)
            for checkbox in self._runtime_checks.values():
                checkbox.setStyleSheet(stylesheet)


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
        self._jump_btn.clicked.connect(lambda: self.navigate_requested.emit(self._target_card_id))
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
                if spec.target_card_id == "scn_overview" or spec.target_card_id.startswith("tpl_")
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
            from src.ui.icons.catalog import get_icon

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
            from src.ui.icons.catalog import get_icon

            self._icon.setPixmap(
                get_icon(self._icon_name, size=16, color=t.text_hint).pixmap(16, 16)
            )
            self._icon.setText("")
        except Exception:
            self._icon.setText("•")


class _SceneOverviewRiskRow(QWidget):
    """One concise boundary/risk notice for the first screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)
        self._label = QLabel("", self)
        self._label.setFixedWidth(78)
        layout.addWidget(self._label, 0, Qt.AlignTop)
        self._detail = QLabel("", self)
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail, 1)
        self._severity = "info"
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_notice(self, notice: SceneRiskNoticeSpec) -> None:
        self._label.setText(notice.label)
        self._detail.setText(notice.detail)
        self._severity = notice.severity
        self._apply_theme()

    def notice_text(self) -> str:
        return f"{self._label.text()} {self._detail.text()}".strip()

    def _apply_theme(self) -> None:
        t = get_theme()
        color_map = {
            "warning": t.warning,
            "neutral": t.text_secondary,
            "info": t.primary,
        }
        self._label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {color_map.get(self._severity, t.primary)};"
        )
        self._detail.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )


# ── 场景概览 ────────────────────────────────────────

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

    def __init__(self, scene_descriptors: list, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._scene_descriptors = list(scene_descriptors)
        self._sample_fixture_output_dir = DEFAULT_SCENE_SAMPLE_FIXTURE_DIR
        self._sample_fixture_library_dir = DEFAULT_SCENE_SAMPLE_FIXTURE_DIR
        self._open_local_path_handler = _open_local_path
        self._sample_fixture_specs = ()
        self._request_cell_specs = ()
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
        task_card.add_widget(self._make_scene_overview_header("mountain-snow", "当前场景"))

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
            "新建场景",
            object_name="scn_overview_new_scene_btn",
            icon_name="plus",
            callback=self.new_scene_requested.emit,
        )
        self._duplicate_scene_btn = self._scene_action_row.add_action(
            "duplicate",
            "创建副本",
            object_name="scn_overview_duplicate_scene_btn",
            icon_name="copy",
            callback=self.duplicate_scene_requested.emit,
        )
        self._rename_scene_btn = self._scene_action_row.add_action(
            "rename",
            "重命名场景",
            object_name="scn_overview_rename_scene_btn",
            icon_name="pencil-line",
            callback=self.rename_scene_requested.emit,
        )
        self._open_scene_folder_btn = self._scene_action_row.add_action(
            "open_folder",
            "打开场景文件夹",
            object_name="scn_overview_open_scene_folder_btn",
            icon_name="folder-open",
            callback=self.open_scene_folder_requested.emit,
        )
        self._delete_scene_btn = self._scene_action_row.add_action(
            "delete",
            "删除场景",
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
            _SceneOverviewRunStepRow(parent=self._run_preview_card)
            for _ in range(5)
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
            self._make_scene_overview_header("sliders-horizontal", "场景策略")
        )
        self._settings_card.add_widget(self._make_scene_overview_separator())
        self._setting_rows: dict[str, QWidget] = {}
        for row_key in (
            "exam_blank_style",
            "exam_runtime_fields",
            "materials",
            "scope",
            "style_source",
            "reference_format",
            "delivery",
        ):
            row = _SceneOverviewSettingRow(parent=self._settings_card)
            row.navigate_requested.connect(self.navigate_requested.emit)
            self._setting_rows[row_key] = row
            self._settings_card.add_widget(row)
        layout.addWidget(self._settings_card)
        layout.addWidget(self._run_preview_card)

        self._advanced_evidence_card = Card(parent=self)
        self._advanced_evidence_card.set_header("诊断资料", icon_name="database")
        self._advanced_evidence_expanded = False
        self._advanced_evidence_toggle_btn = QPushButton("展开", self._advanced_evidence_card)
        self._advanced_evidence_toggle_btn.clicked.connect(self._toggle_advanced_evidence)
        self._advanced_evidence_card.add_header_action(self._advanced_evidence_toggle_btn)
        self._advanced_evidence_hint = QLabel(
            "需要追溯时再看：场景覆盖、样本文档和常见说法。",
            self,
        )
        self._advanced_evidence_hint.setObjectName("scn_advanced_evidence_hint")
        self._advanced_evidence_hint.setWordWrap(True)
        self._advanced_evidence_card.add_widget(self._advanced_evidence_hint)

        self._advanced_evidence_content = QWidget(self._advanced_evidence_card)
        self._advanced_evidence_content_layout = QVBoxLayout(self._advanced_evidence_content)
        self._advanced_evidence_content_layout.setContentsMargins(0, 0, 0, 0)
        self._advanced_evidence_content_layout.setSpacing(8)
        self._advanced_evidence_card.add_widget(self._advanced_evidence_content)

        self._profile_summary = SummaryGrid(columns=1, parent=self._advanced_evidence_content)
        self._advanced_evidence_content_layout.addWidget(self._profile_summary)

        self._risk_card = Card(parent=self._advanced_evidence_content)
        self._risk_card.add_widget(
            self._make_scene_overview_header("shield-alert", "执行边界")
        )
        self._risk_card.add_widget(self._make_scene_overview_separator())
        self._risk_rows = [_SceneOverviewRiskRow(parent=self._risk_card) for _ in range(3)]
        for row in self._risk_rows:
            self._risk_card.add_widget(row)
        self._advanced_evidence_content_layout.addWidget(self._risk_card)

        self._sample_fixture_detail = TextArea(
            min_height=92,
            max_height=180,
            parent=self._advanced_evidence_content,
        )
        self._sample_fixture_detail._text_edit.setObjectName("scn_sample_fixture_detail")
        self._sample_fixture_detail._text_edit.setReadOnly(True)
        self._sample_fixture_detail_row = template_form_row(
            "样本详情",
            self._sample_fixture_detail,
            parent=self._advanced_evidence_content,
        )
        self._sample_fixture_detail_row.setVisible(False)
        self._advanced_evidence_content_layout.addWidget(self._sample_fixture_detail_row)

        self._sample_fixture_actions = QWidget(self._advanced_evidence_content)
        sample_fixture_actions_layout = QHBoxLayout(self._sample_fixture_actions)
        sample_fixture_actions_layout.setContentsMargins(0, 0, 0, 0)
        sample_fixture_actions_layout.setSpacing(8)
        self._generate_sample_fixture_btn = QPushButton("生成样本库", self._sample_fixture_actions)
        self._generate_sample_fixture_btn.clicked.connect(self._generate_sample_fixture_library)
        self._open_sample_fixture_file_btn = QPushButton("打开样本", self._sample_fixture_actions)
        self._open_sample_fixture_file_btn.clicked.connect(self._open_sample_fixture_file)
        self._open_sample_fixture_file_btn.setEnabled(False)
        self._open_sample_fixture_dir_btn = QPushButton("打开目录", self._sample_fixture_actions)
        self._open_sample_fixture_dir_btn.clicked.connect(self._open_sample_fixture_library_dir)
        self._open_sample_fixture_dir_btn.setEnabled(False)
        self._sample_fixture_manifest = QLabel("", self._sample_fixture_actions)
        self._sample_fixture_manifest.setObjectName("scn_sample_fixture_manifest")
        self._sample_fixture_manifest.setWordWrap(True)
        sample_fixture_actions_layout.addWidget(self._generate_sample_fixture_btn)
        sample_fixture_actions_layout.addWidget(self._open_sample_fixture_file_btn)
        sample_fixture_actions_layout.addWidget(self._open_sample_fixture_dir_btn)
        sample_fixture_actions_layout.addWidget(self._sample_fixture_manifest, 1)
        self._sample_fixture_actions_row = template_form_row(
            "样本库",
            self._sample_fixture_actions,
            parent=self._advanced_evidence_content,
        )
        self._sample_fixture_actions_row.setVisible(False)
        self._advanced_evidence_content_layout.addWidget(self._sample_fixture_actions_row)

        self._sample_fixture_list = QListWidget(self._advanced_evidence_content)
        self._sample_fixture_list.setObjectName("scn_sample_fixture_list")
        self._sample_fixture_list.setMinimumHeight(92)
        self._sample_fixture_list.setMaximumHeight(124)
        self._sample_fixture_list.currentItemChanged.connect(
            lambda *_args: self._sync_selected_sample_fixture_state()
        )
        self._sample_fixture_list.itemDoubleClicked.connect(
            lambda *_args: self._open_sample_fixture_file()
        )
        self._sample_fixture_list_row = template_form_row(
            "样本文件",
            self._sample_fixture_list,
            parent=self._advanced_evidence_content,
        )
        self._sample_fixture_list_row.setVisible(False)
        self._advanced_evidence_content_layout.addWidget(self._sample_fixture_list_row)

        self._request_cell_filter_container = QWidget(self._advanced_evidence_content)
        request_cell_filter_layout = QHBoxLayout(self._request_cell_filter_container)
        request_cell_filter_layout.setContentsMargins(0, 0, 0, 0)
        request_cell_filter_layout.setSpacing(8)
        self._request_cell_filter = StyledComboBox(self._request_cell_filter_container)
        for filter_id, label in scene_request_cell_filter_options():
            self._request_cell_filter.addItem(label, filter_id)
        self._request_cell_filter_status = QLabel("", self._request_cell_filter_container)
        self._request_cell_filter_status.setObjectName("scn_request_cell_filter_status")
        self._request_cell_filter_status.setWordWrap(False)
        request_cell_filter_layout.addWidget(self._request_cell_filter, 1)
        request_cell_filter_layout.addWidget(self._request_cell_filter_status, 0)
        self._request_cell_filter_row = template_form_row(
            "说法筛选",
            self._request_cell_filter_container,
            parent=self._advanced_evidence_content,
        )
        self._request_cell_filter_row.setVisible(False)
        self._advanced_evidence_content_layout.addWidget(self._request_cell_filter_row)

        self._request_cell_actions = QWidget(self._advanced_evidence_content)
        request_cell_actions_layout = QHBoxLayout(self._request_cell_actions)
        request_cell_actions_layout.setContentsMargins(0, 0, 0, 0)
        request_cell_actions_layout.setSpacing(8)
        self._open_request_cell_fixture_btn = QPushButton("打开证据", self._request_cell_actions)
        self._open_request_cell_fixture_btn.clicked.connect(
            self._open_request_cell_fixture_file
        )
        self._open_request_cell_fixture_btn.setEnabled(False)
        self._request_cell_evidence_status = QLabel("", self._request_cell_actions)
        self._request_cell_evidence_status.setObjectName("scn_request_cell_evidence_status")
        self._request_cell_evidence_status.setWordWrap(True)
        request_cell_actions_layout.addWidget(self._open_request_cell_fixture_btn)
        request_cell_actions_layout.addWidget(self._request_cell_evidence_status, 1)
        self._request_cell_actions_row = template_form_row(
            "说法依据",
            self._request_cell_actions,
            parent=self._advanced_evidence_content,
        )
        self._request_cell_actions_row.setVisible(False)
        self._advanced_evidence_content_layout.addWidget(self._request_cell_actions_row)

        self._request_cell_list = QListWidget(self._advanced_evidence_content)
        self._request_cell_list.setObjectName("scn_request_cell_list")
        self._request_cell_list.setMinimumHeight(104)
        self._request_cell_list.setMaximumHeight(156)
        self._request_cell_filter.currentIndexChanged.connect(
            lambda *_args: self._refresh_request_cell_list()
        )
        self._request_cell_list.currentItemChanged.connect(
            lambda *_args: self._sync_selected_request_cell_state()
        )
        self._request_cell_list.itemDoubleClicked.connect(
            lambda *_args: self._open_request_cell_fixture_file()
        )
        self._request_cell_list_row = template_form_row(
            "常见说法",
            self._request_cell_list,
            parent=self._advanced_evidence_content,
        )
        self._request_cell_list_row.setVisible(False)
        self._advanced_evidence_content_layout.addWidget(self._request_cell_list_row)

        self._advanced_evidence_card.setVisible(False)
        layout.addStretch(1)

        self._sync_advanced_evidence_visibility()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _populate_scene_combo(self, current_scene_id: str = "") -> None:
        self._combo.clear()
        self._combo_index_by_scene_id = {}
        builtin_ids = _builtin_scene_id_set()
        user_descriptors = [
            descriptor
            for descriptor in self._scene_descriptors
            if str(getattr(descriptor, "config_id", "") or "").strip() not in builtin_ids
        ]
        builtin_descriptors = [
            descriptor
            for descriptor in self._scene_descriptors
            if str(getattr(descriptor, "config_id", "") or "").strip() in builtin_ids
        ]

        if user_descriptors:
            self._add_scene_group_header("我的场景", _SCENE_SELECTOR_MY_GROUP)
            for descriptor in user_descriptors:
                self._add_scene_descriptor_item(descriptor)
        if builtin_descriptors:
            self._add_scene_group_header("内置场景", _SCENE_SELECTOR_BUILTIN_GROUP)
            for descriptor in builtin_descriptors:
                self._add_scene_descriptor_item(descriptor)

        if not self._set_scene_combo_current_id(current_scene_id):
            first_index = self._first_available_scene_combo_index()
            if first_index >= 0:
                self._combo.setCurrentIndex(first_index)

    def _add_scene_group_header(self, label: str, data: str) -> None:
        self._combo.addItem(label, data)
        index = self._combo.count() - 1
        self._combo.setItemData(index, "分组标题，不会作为场景加载", Qt.ToolTipRole)
        model = self._combo.model()
        item_getter = getattr(model, "item", None)
        if callable(item_getter):
            item = item_getter(index)
            if item is not None:
                item.setEnabled(False)

    def _add_scene_descriptor_item(self, descriptor) -> None:
        scene_id = str(getattr(descriptor, "config_id", "") or "").strip()
        if not scene_id:
            return
        self._combo.addItem(descriptor.display_name, scene_id)
        item_index = self._combo.count() - 1
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
    ) -> None:
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
            self._set_scene_combo_current_id(scene.scene_id)
        finally:
            self._combo.blockSignals(False)

        # Strategy
        self._rebuild_radio.setChecked(scene.strict_mode)
        self._preserve_radio.setChecked(not scene.strict_mode)

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
                if row_spec.key == "style_source" and hasattr(row, "apply_projection"):
                    row.apply_projection(spec.style_source)
                else:
                    row.set_spec(row_spec)
                row.setVisible(True)
        for index, row in enumerate(self._risk_rows):
            if index < len(spec.risk_notices):
                row.set_notice(spec.risk_notices[index])
                row.setVisible(True)
            else:
                row.setVisible(False)
        self._profile_summary.set_items(build_scene_overview_summary_items(scene))
        sample_detail = build_scene_sample_fixture_detail_text(scene)
        self._sample_fixture_detail.set_text(sample_detail)
        self._sample_fixture_specs = scene_sample_fixture_specs_for_scene(scene)
        self._refresh_sample_fixture_list()
        self._request_cell_specs = scene_request_cell_fixture_specs_for_scene(scene)
        self._refresh_request_cell_list()
        has_sample_detail = bool(sample_detail.strip())
        has_request_cells = bool(self._request_cell_specs)
        self._sample_fixture_detail_row.setVisible(has_sample_detail)
        self._sample_fixture_actions_row.setVisible(has_sample_detail)
        self._sample_fixture_list_row.setVisible(has_sample_detail and bool(self._sample_fixture_specs))
        self._request_cell_filter_row.setVisible(has_request_cells)
        self._request_cell_actions_row.setVisible(has_request_cells)
        self._request_cell_list_row.setVisible(has_request_cells)
        if has_sample_detail:
            self._refresh_sample_fixture_library_state()
        else:
            self._sync_selected_request_cell_state()

    def _current_template_label(self) -> str:
        if self._current_scene is None:
            return ""
        template_id = str(
            self._current_scene.template_id
            or self._current_scene.default_template_id
            or ""
        ).strip()
        entry = get_template_entry(template_id)
        if entry is not None:
            return entry.name
        current_template = getattr(self, "_current_template", None)
        template_name = str(getattr(current_template, "name", "") or "").strip()
        if template_name:
            return template_name
        return str(
            template_id
        ).strip()

    def _format_run_preview_steps(
        self, steps: tuple[SceneRunStepSpec, ...]
    ) -> str:
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

    def _toggle_advanced_evidence(self) -> None:
        self._advanced_evidence_expanded = not self._advanced_evidence_expanded
        self._sync_advanced_evidence_visibility()

    def show_advanced_evidence(self) -> None:
        if not self._advanced_evidence_expanded:
            self._advanced_evidence_expanded = True
            self._sync_advanced_evidence_visibility()

    def advanced_evidence_widget(self) -> QWidget:
        return self._advanced_evidence_card

    def _sync_advanced_evidence_visibility(self) -> None:
        self._advanced_evidence_content.setVisible(self._advanced_evidence_expanded)
        self._advanced_evidence_hint.setVisible(self._advanced_evidence_expanded)
        self._advanced_evidence_toggle_btn.setText(
            "收起" if self._advanced_evidence_expanded else "展开"
        )
        try:
            from src.ui.icons.catalog import get_icon

            icon_name = "chevron-up" if self._advanced_evidence_expanded else "chevron-down"
            self._advanced_evidence_toggle_btn.setIcon(
                get_icon(icon_name, 16, get_theme().primary)
            )
        except Exception:
            pass
        refresh_layout_chain_later(self)

    def _refresh_sample_fixture_list(self) -> None:
        current_id = self._selected_sample_fixture_id()
        self._sample_fixture_list.blockSignals(True)
        self._sample_fixture_list.clear()
        selected_row = -1
        for row, fixture in enumerate(self._sample_fixture_specs):
            projection = scene_sample_fixture_list_item_projection(fixture, row + 1)
            item = QListWidgetItem(projection.text)
            item.setData(Qt.UserRole, projection.fixture_id)
            item.setToolTip(projection.tooltip)
            self._sample_fixture_list.addItem(item)
            if fixture.fixture_id == current_id:
                selected_row = row
        if self._sample_fixture_list.count():
            self._sample_fixture_list.setCurrentRow(selected_row if selected_row >= 0 else 0)
        self._sample_fixture_list.blockSignals(False)
        self._sync_selected_sample_fixture_state()

    def _refresh_request_cell_list(self) -> None:
        current_id = self._selected_request_cell_id()
        level_filter = str(self._request_cell_filter.currentData() or "all")
        self._request_cell_list.blockSignals(True)
        self._request_cell_list.clear()
        selected_row = -1
        for cell in self._request_cell_specs:
            if not scene_request_cell_matches_filter(cell, level_filter):
                continue
            projection = scene_request_cell_list_item_projection(cell)
            item = QListWidgetItem(projection.text)
            item.setData(Qt.UserRole, cell.sample_id)
            item.setToolTip(projection.tooltip)
            self._request_cell_list.addItem(item)
            if cell.sample_id == current_id:
                selected_row = self._request_cell_list.count() - 1
        if self._request_cell_list.count():
            self._request_cell_list.setCurrentRow(
                selected_row if selected_row >= 0 else 0
            )
        self._request_cell_list.blockSignals(False)
        total_count = len(self._request_cell_specs)
        if hasattr(self, "_request_cell_filter_status"):
            self._request_cell_filter_status.setText(
                scene_request_cell_count_text(
                    self._request_cell_list.count(),
                    total_count,
                )
            )
            self._request_cell_filter_status.setToolTip(
                scene_request_cell_count_tooltip(
                    self._request_cell_list.count(),
                    total_count,
                    level_filter,
                )
            )
        self._sync_selected_request_cell_state()

    def _selected_request_cell_id(self) -> str:
        item = self._request_cell_list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.UserRole) or "").strip()

    def _selected_request_cell(self):
        sample_id = self._selected_request_cell_id()
        if not sample_id:
            return None
        for cell in self._request_cell_specs:
            if str(cell.sample_id or "").strip() == sample_id:
                return cell
        return None

    def _refresh_sample_fixture_library_state(self) -> None:
        manifest_path = Path(self._sample_fixture_output_dir) / "manifest.json"
        self._sample_fixture_library_dir = Path(self._sample_fixture_output_dir)
        if manifest_path.exists():
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("generated")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "generated",
                    manifest_path.resolve(),
                )
            )
            self._open_sample_fixture_dir_btn.setEnabled(True)
        else:
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("not_generated")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "not_generated",
                    manifest_path.resolve(),
                )
            )
            self._open_sample_fixture_dir_btn.setEnabled(False)
        self._sync_selected_sample_fixture_state()
        self._sync_selected_request_cell_state()

    def _generate_sample_fixture_library(self) -> None:
        try:
            library = build_scene_sample_docx_library(Path(self._sample_fixture_output_dir))
        except Exception as exc:
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("generation_failed")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "generation_failed",
                    Path(self._sample_fixture_output_dir).resolve(),
                    detail=str(exc),
                )
            )
            self._open_sample_fixture_dir_btn.setEnabled(False)
            self._open_sample_fixture_file_btn.setEnabled(False)
            return
        self._sample_fixture_library_dir = Path(library.output_dir)
        manifest_path = Path(library.manifest_path)
        self._sample_fixture_manifest.setText(
            scene_sample_fixture_library_status_text(
                "generated",
                len(library.artifacts),
            )
        )
        self._sample_fixture_manifest.setToolTip(
            scene_sample_fixture_library_status_tooltip(
                "generated",
                manifest_path.resolve(),
            )
        )
        self._open_sample_fixture_dir_btn.setEnabled(True)
        self._sync_selected_sample_fixture_state()
        self._sync_selected_request_cell_state()

    def _selected_sample_fixture_id(self) -> str:
        item = self._sample_fixture_list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.UserRole) or "").strip()

    def _selected_sample_fixture_docx_path(self) -> Path | None:
        fixture_id = self._selected_sample_fixture_id()
        if not fixture_id:
            return None
        return Path(self._sample_fixture_output_dir) / f"{fixture_id}.docx"

    def _sync_selected_sample_fixture_state(self) -> None:
        path = self._selected_sample_fixture_docx_path()
        enabled = bool(path and path.exists())
        self._open_sample_fixture_file_btn.setEnabled(enabled)
        if enabled and path is not None:
            self._open_sample_fixture_file_btn.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "generated",
                    path.resolve(),
                )
            )
        elif path is not None:
            self._open_sample_fixture_file_btn.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "sample_missing",
                    path.resolve(),
                )
            )
        else:
            self._open_sample_fixture_file_btn.setToolTip(
                scene_sample_fixture_library_status_tooltip("no_sample_selection")
            )

    def _selected_request_cell_fixture_docx_path(self) -> Path | None:
        cell = self._selected_request_cell()
        if cell is None:
            return None
        fixture_ids = tuple(getattr(cell, "fixture_ids", ()) or ())
        if not fixture_ids:
            return None
        fixture_id = str(fixture_ids[0] or "").strip()
        if not fixture_id:
            return None
        return Path(self._sample_fixture_output_dir) / f"{fixture_id}.docx"

    def _sync_selected_request_cell_state(self) -> None:
        if not hasattr(self, "_open_request_cell_fixture_btn"):
            return
        cell = self._selected_request_cell()
        path = self._selected_request_cell_fixture_docx_path()
        enabled = bool(path and path.exists())
        self._open_request_cell_fixture_btn.setEnabled(enabled)
        if enabled and path is not None:
            self._open_request_cell_fixture_btn.setToolTip(
                scene_request_cell_evidence_status_tooltip("ready", path.resolve())
            )
        elif path is not None:
            self._open_request_cell_fixture_btn.setToolTip(
                scene_request_cell_evidence_status_tooltip(
                    "missing_file",
                    path.resolve(),
                )
            )
        elif cell is not None:
            self._open_request_cell_fixture_btn.setToolTip(
                scene_request_cell_evidence_status_tooltip("no_docx")
            )
        else:
            self._open_request_cell_fixture_btn.setToolTip(
                scene_request_cell_evidence_status_tooltip("no_selection")
            )

    def _open_request_cell_fixture_file(self) -> None:
        cell = self._selected_request_cell()
        path = self._selected_request_cell_fixture_docx_path()
        if cell is None:
            self._request_cell_evidence_status.setText(
                scene_request_cell_evidence_status_text("no_selection")
            )
            self._request_cell_evidence_status.setToolTip(
                scene_request_cell_evidence_status_tooltip("no_selection")
            )
            return
        if path is None:
            self._request_cell_evidence_status.setText(
                scene_request_cell_evidence_status_text("no_docx")
            )
            self._request_cell_evidence_status.setToolTip(
                scene_request_cell_evidence_status_tooltip("no_docx")
            )
            return
        if not path.exists():
            self._request_cell_evidence_status.setText(
                scene_request_cell_evidence_status_text("missing_file")
            )
            self._request_cell_evidence_status.setToolTip(
                scene_request_cell_evidence_status_tooltip(
                    "missing_file",
                    path.resolve(),
                )
            )
            self._open_request_cell_fixture_btn.setEnabled(False)
            return
        if self._open_local_path_handler(path):
            self._request_cell_evidence_status.setText(
                scene_request_cell_evidence_status_text("opened")
            )
            self._request_cell_evidence_status.setToolTip(
                scene_request_cell_evidence_status_tooltip("opened", path.resolve())
            )
        else:
            self._request_cell_evidence_status.setText(
                scene_request_cell_evidence_status_text("open_failed")
            )
            self._request_cell_evidence_status.setToolTip(
                scene_request_cell_evidence_status_tooltip(
                    "open_failed",
                    path.resolve(),
                )
            )

    def _open_sample_fixture_file(self) -> None:
        path = self._selected_sample_fixture_docx_path()
        if path is None:
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("no_sample_selection")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip("no_sample_selection")
            )
            return
        if not path.exists():
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("sample_missing")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "sample_missing",
                    path.resolve(),
                )
            )
            self._open_sample_fixture_file_btn.setEnabled(False)
            return
        if self._open_local_path_handler(path):
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("sample_opened")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "sample_opened",
                    path.resolve(),
                )
            )
        else:
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("sample_open_failed")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "sample_open_failed",
                    path.resolve(),
                )
            )

    def _open_sample_fixture_library_dir(self) -> None:
        output_dir = Path(self._sample_fixture_library_dir)
        if not output_dir.exists():
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("directory_missing")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "directory_missing",
                    output_dir.resolve(),
                )
            )
            self._open_sample_fixture_dir_btn.setEnabled(False)
            return
        if self._open_local_path_handler(output_dir):
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("directory_opened")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "directory_opened",
                    output_dir.resolve(),
                )
            )
        else:
            self._sample_fixture_manifest.setText(
                scene_sample_fixture_library_status_text("directory_open_failed")
            )
            self._sample_fixture_manifest.setToolTip(
                scene_sample_fixture_library_status_tooltip(
                    "directory_open_failed",
                    output_dir.resolve(),
                )
            )

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
        self._desc.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_secondary};")
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
        self._summary.setStyleSheet(f"font-size: {t.font_size_sm}px; color: {t.text_hint};")
        self._run_steps_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_primary}; line-height: 145%;"
        )
        self._advanced_evidence_hint.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )
        self._sample_fixture_manifest.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )
        self._request_cell_evidence_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )
        self._request_cell_filter_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )
        self._scene_action_row.apply_theme()
        _apply_template_button_contract(
            (self._execute_btn, "primary"),
            (self._advanced_evidence_toggle_btn, "secondary"),
            (self._generate_sample_fixture_btn, "secondary"),
            (self._open_sample_fixture_file_btn, "secondary"),
            (self._open_sample_fixture_dir_btn, "secondary"),
            (self._open_request_cell_fixture_btn, "secondary"),
        )
        try:
            from src.ui.icons.catalog import get_icon

            for icon_name, label in self._overview_header_icons.items():
                label.setPixmap(get_icon(icon_name, 18, t.primary).pixmap(18, 18))
            self._execute_btn.setIcon(get_icon("play-circle", 16, t.text_on_primary))
            self._advanced_evidence_toggle_btn.setIcon(
                get_icon(
                    "chevron-up" if self._advanced_evidence_expanded else "chevron-down",
                    16,
                    t.primary,
                )
            )
        except Exception:
            pass
        for list_widget, object_name in (
            (self._sample_fixture_list, "scn_sample_fixture_list"),
            (self._request_cell_list, "scn_request_cell_list"),
        ):
            list_widget.setStyleSheet(
                f"""
                QListWidget#{object_name} {{
                    background: {t.bg_input};
                    color: {t.text_primary};
                    border: 1px solid {t.border};
                    border-radius: {t.input_radius}px;
                    padding: 4px;
                    font-size: {t.font_size_sm}px;
                }}
                QListWidget#{object_name}::item {{
                    min-height: 28px;
                    padding: 4px 8px;
                }}
                QListWidget#{object_name}::item:selected {{
                    background: {t.bg_selected};
                    color: {t.primary};
                }}
                """
            )


# ── 处理范围 ────────────────────────────────────────

class _ScopeDetail(QWidget):
    """Layer 2: Scene application boundary."""

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

        self._scope_zone_section = SceneScopeZoneSection(
            self,
            summary_items=build_scene_scope_summary_items(None),
            zone_labels=SCENE_SCOPE_ZONE_DISPLAY_LABELS,
        )
        self._scope_zone_section.zone_changed.connect(self._on_scope_zone_changed)
        self._scope_zone_section.boundary_mode_changed.connect(
            self._on_boundary_mode_changed
        )
        self._scope_card = self._scope_zone_section.card
        self._detail_summary = self._scope_zone_section.summary
        self._scope_zone_checklist = self._scope_zone_section.checklist
        self._zone_checks = self._scope_zone_section.checks
        layout.addWidget(self._scope_zone_section)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if not target:
            return False

        zone_id = self._scope_zone_for_field(target)
        if zone_id:
            self._highlight_navigation_widget(self._zone_checks[zone_id], target)
            return True
        return False

    def _scope_zone_for_field(self, field_id: str) -> str:
        target = str(field_id or "").strip()
        for prefix in (
            "scene.format_scope.sections.",
            "format_scope.sections.",
            "sections.",
            "scope.",
        ):
            if target.startswith(prefix):
                target = target[len(prefix):].split(".", 1)[0]
                break
        return target if target in self._zone_checks else ""

    def _highlight_navigation_widget(self, widget: QWidget, label: str) -> None:
        self._navigation_highlighter.highlight(
            widget,
            label,
            display_label=(
                field_display_context(label).label_with_group()
                or field_display_name(label)
            ),
        )

    def _refresh_scope_summary(self) -> None:
        if hasattr(self, "_scope_zone_section"):
            self._scope_zone_section.set_summary_items(
                build_scene_scope_summary_items(self._current_scene)
            )

    def set_scene(self, scene: SceneWorkspace, template=None) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            for zone_id in self._zone_checks:
                self._scope_zone_section.set_zone_checked(
                    zone_id,
                    scene.format_scope.sections.get(zone_id, False),
                )
            self._scope_zone_section.set_boundary_mode(
                getattr(scene.application_boundary, "mode", "follow_template")
            )
            self._refresh_scope_summary()
            refresh_layout_chain(self)
            refresh_layout_chain_later(self)
        finally:
            self._is_syncing = False

    def _on_scope_zone_changed(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        apply_scene_scope_zone_states(
            self._current_scene,
            self._scope_zone_section.checked_states(),
        )
        self.scope_changed.emit()

    def _on_boundary_mode_changed(self, mode: str) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._apply_application_boundary_mode(self._current_scene, mode)
        self.scope_changed.emit()

    def _apply_application_boundary_mode(
        self,
        scene: SceneWorkspace,
        mode: str,
    ) -> None:
        normalized = str(mode or "").strip() or "follow_template"
        if normalized not in _NAV_SCOPE_MODE_LABELS:
            normalized = "follow_template"
        scene.application_boundary.mode = normalized
        scene.application_boundary.confirm_before_apply = (
            normalized == "confirm_before_apply"
        )

        legacy_sections = dict(scene.format_scope.sections or FormatScopeConfig().sections)
        if normalized == "body_only":
            scene.format_scope.sections = {
                key: key == "body" for key in legacy_sections
            }
            scene.format_scope.mode = "auto"
        elif normalized == "full_document":
            scene.format_scope.sections = {key: True for key in legacy_sections}
            scene.format_scope.mode = "auto"
        elif normalized == "confirm_before_apply":
            scene.format_scope.mode = "manual_review"
        else:
            scene.format_scope.sections = dict(FormatScopeConfig().sections)
            scene.format_scope.mode = "auto"

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        if hasattr(self, "_scope_zone_section"):
            self._scope_zone_section.apply_theme()


# ── 格式例外 ────────────────────────────────────────

class _StyleRulesDetail(QWidget):
    """Layer 2: Scene-specific section style rules."""

    style_rules_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._current_template = None
        self._is_syncing = False
        self._restore_all_style_snapshot: dict[str, object] = {}
        self._navigation_highlighter = NavigationHighlighter()
        self._unit_labels: list[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._style_rules_block = SceneStyleRulesBlock(
            self,
            summary_items=build_scene_style_override_summary_items(None, None),
            style_variants=STYLE_VARIANTS,
        )
        self._style_rules_block.policy_toggled.connect(self._on_variant_toggled)
        self._style_rules_block.current_variant_changed.connect(
            self._on_editor_variant_changed
        )
        self._style_rules_block.restore_requested.connect(
            self._on_restore_selected_style_to_template
        )
        self._style_rules_block.restore_all_requested.connect(
            self._on_restore_all_styles_to_template
        )
        self._style_rules_block.undo_restore_all_requested.connect(
            self._on_undo_restore_all_styles
        )
        self._style_rules_block.style_changed.connect(self._on_style_editor_edited)

        self._style_override_card = self._style_rules_block.card
        self._style_override_summary = self._style_rules_block.summary
        self._style_override_toggle_list = self._style_rules_block.toggle_list
        self._variant_toggles = self._style_rules_block.toggles
        self._variant_rows = self._style_rules_block.rows

        self._style_owner_toolbar = self._style_rules_block.owner_toolbar
        self._style_owner_status = self._style_rules_block.owner_status
        self._style_comparison_strip = self._style_rules_block.comparison_strip
        self._style_variant_combo = self._style_rules_block.selector
        self._restore_section_style_btn = self._style_rules_block.restore_button
        self._restore_all_section_styles_btn = self._style_rules_block.restore_all_button
        self._undo_restore_all_section_styles_btn = (
            self._style_rules_block.undo_restore_all_button
        )
        self._style_editor_hint = self._style_rules_block.hint_label
        self._section_style_preview = self._style_rules_block.preview
        self._style_surface = self._style_rules_block.style_surface

        self._unit_labels.extend(self._style_rules_block.unit_labels)

        layout.addWidget(self._style_rules_block)
        layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if not target:
            return False

        variant_key, editor_field = self._style_navigation_target(target)
        if variant_key:
            self._set_style_editor_variant(variant_key)
            self._sync_style_editor()
            widget = self._style_rules_block.navigation_widget_for_field(
                editor_field,
                variant_key=variant_key,
                prefer_toggle_when_unchecked=True,
            )
            if widget is not None:
                self._highlight_navigation_widget(widget, target)
                return True

        widget = self._style_rules_block.editor_widget_for_field(target)
        if widget is not None:
            variant = self._selected_style_variant()
            if (
                variant is not None
                and self._current_scene is not None
                and not is_section_style_overridden(self._current_scene, variant.key)
            ):
                target_widget = self._style_rules_block.navigation_widget_for_field(
                    target,
                    variant_key=variant.key,
                    prefer_toggle=True,
                )
                self._highlight_navigation_widget(target_widget or widget, target)
                return True
            self._highlight_navigation_widget(widget, target)
            return True

        return False

    def _style_navigation_target(self, field_id: str) -> tuple[str, str]:
        target = str(field_id or "").strip()
        if not target:
            return "", ""
        variant_key, editor_field = scene_style_navigation_target_from_field_id(target)
        visible_keys = {
            variant.key
            for variant in _generic_style_variants_for_scene(
                self._current_scene,
                self._current_template,
            )
        }
        if (
            variant_key
            and variant_key in visible_keys
            and self._style_rules_block.has_policy_key(variant_key)
        ):
            return variant_key, editor_field
        for prefix in ("scene.section_styles.", "section_styles."):
            if target.startswith(prefix):
                parts = target[len(prefix):].split(".")
                if len(parts) >= 2 and parts[0] == "*":
                    variant = self._wildcard_style_variant()
                    return (
                        variant.key if variant is not None else "",
                        ".".join(parts[1:]),
                    )
        if target.startswith("section_style."):
            variant = self._selected_style_variant()
            return (variant.key if variant is not None else ""), target[len("section_style."):]
        return "", ""

    def _wildcard_style_variant(self):
        scene = self._current_scene
        variants = _generic_style_variants_for_scene(scene, self._current_template)
        if scene is not None:
            for variant in variants:
                if is_section_style_overridden(scene, variant.key):
                    return variant
            for variant in variants:
                return variant
        return self._selected_style_variant()

    def _highlight_navigation_widget(self, widget: QWidget, label: str) -> None:
        self._navigation_highlighter.highlight(
            widget,
            label,
            display_label=(
                field_display_context(label).label_with_group()
                or field_display_name(label)
            ),
        )

    def _refresh_style_override_summary(self) -> None:
        if not hasattr(self, "_style_rules_block"):
            return
        self._sync_style_editor()

    def _restore_all_style_snapshot_labels(self) -> tuple[str, ...]:
        snapshot_keys = set(self._restore_all_style_snapshot)
        if not snapshot_keys:
            return ()
        return tuple(
            variant.label
            for variant in _generic_style_variants_for_scene(
                self._current_scene,
                self._current_template,
            )
            if variant.key in snapshot_keys
        )

    def _restore_all_style_labels(self) -> tuple[str, ...]:
        scene = self._current_scene
        if scene is None:
            return ()
        return tuple(
            variant.label
            for variant in _generic_style_variants_for_scene(
                scene,
                self._current_template,
            )
            if is_section_style_overridden(scene, variant.key)
        )

    def _clear_restore_all_style_snapshot(self) -> None:
        if not self._restore_all_style_snapshot:
            return
        self._restore_all_style_snapshot = {}

    def discard_restore_all_style_snapshot(self) -> None:
        self._clear_restore_all_style_snapshot()
        self._refresh_style_override_summary()

    def _selected_style_override_projection(self):
        scene = self._current_scene
        variant = self._selected_style_variant()
        if scene is None or variant is None:
            return None
        return scene_section_style_override_projection(
            scene,
            getattr(self, "_current_template", None),
            variant.key,
        )

    def set_scene(self, scene: SceneWorkspace, template=None) -> None:
        previous_scene = self._current_scene
        self._current_scene = scene
        if template is not None:
            self._current_template = template
        if scene is not previous_scene:
            self._restore_all_style_snapshot = {}
        self._is_syncing = True
        try:
            visible_variants = _generic_style_variants_for_scene(
                scene,
                self._current_template,
            )
            visible_keys = {variant.key for variant in visible_variants}
            self._style_rules_block.set_style_variants(visible_variants)
            for variant in STYLE_VARIANTS:
                self._set_variant_toggle_checked(
                    variant.key,
                    is_section_style_overridden(scene, variant.key),
                )
                self._style_rules_block.set_policy_row_visible(
                    variant.key,
                    variant.key in visible_keys,
                )
            current_key = self._style_rules_block.current_variant_key()
            if visible_variants and current_key not in visible_keys:
                self._style_rules_block.set_current_variant(visible_variants[0].key)
            elif not visible_variants:
                self._style_rules_block.set_current_policy_key("")
            self._sync_style_editor()
            refresh_layout_chain(self)
            refresh_layout_chain_later(self)
        finally:
            self._is_syncing = False

    def _on_variant_toggled(self, variant_key: str, checked: bool) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        self._clear_restore_all_style_snapshot()
        set_scene_section_style_override(
            self._current_scene,
            self._current_template,
            variant_key,
            checked,
        )
        self._set_variant_toggle_checked(variant_key, checked)
        self._set_style_editor_variant(variant_key)
        self._sync_style_editor()
        self.style_rules_changed.emit()

    def _on_restore_selected_style_to_template(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        variant = self._selected_style_variant()
        if variant is None:
            return
        if not restore_scene_section_style_to_template(self._current_scene, variant.key):
            return
        self._clear_restore_all_style_snapshot()
        self._set_variant_toggle_checked_silently(variant.key, False)
        self._sync_style_editor()
        self.style_rules_changed.emit()

    def _on_restore_all_styles_to_template(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        snapshot = {
            variant.key: copy.deepcopy(self._current_scene.section_styles[variant.key])
            for variant in _generic_style_variants_for_scene(
                self._current_scene,
                self._current_template,
            )
            if is_section_style_overridden(self._current_scene, variant.key)
        }
        restored = tuple(
            key
            for key in snapshot
            if restore_scene_section_style_to_template(self._current_scene, key)
        )
        if not restored:
            return
        self._restore_all_style_snapshot = {
            key: snapshot[key]
            for key in restored
            if key in snapshot
        }
        for variant_key in restored:
            self._set_variant_toggle_checked_silently(variant_key, False)
        self._sync_style_editor()
        self.style_rules_changed.emit()

    def _on_undo_restore_all_styles(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        snapshot = dict(self._restore_all_style_snapshot)
        if not snapshot:
            return
        for variant_key, style in snapshot.items():
            self._current_scene.section_styles[variant_key] = copy.deepcopy(style)
            self._set_variant_toggle_checked_silently(variant_key, True)
        self._restore_all_style_snapshot = {}
        self._sync_style_editor()
        self.style_rules_changed.emit()

    def _set_variant_toggle_checked_silently(self, variant_key: str, checked: bool) -> None:
        previous = self._is_syncing
        self._is_syncing = True
        try:
            self._set_variant_toggle_checked(variant_key, checked)
        finally:
            self._is_syncing = previous

    def _set_variant_toggle_checked(self, variant_key: str, checked: bool) -> None:
        self._style_rules_block.set_policy_checked(variant_key, checked)

    def _on_editor_variant_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        self._sync_style_editor()

    def _set_style_editor_variant(self, variant_key: str) -> None:
        if hasattr(self, "_style_rules_block"):
            self._style_rules_block.set_current_variant(variant_key)

    def _selected_style_variant(self):
        if hasattr(self, "_style_rules_block"):
            variant_key = self._style_rules_block.current_variant_key()
        else:
            variant_key = str(self._style_variant_combo.currentData() or "")
        variants = _generic_style_variants_for_scene(
            self._current_scene,
            self._current_template,
        )
        for variant in variants:
            if variant.key == variant_key:
                return variant
        return variants[0] if variants else None

    def _editable_section_style(self):
        if self._current_scene is None:
            return None
        variant = self._selected_style_variant()
        if variant is None:
            return None
        if not is_section_style_overridden(self._current_scene, variant.key):
            return None
        return self._current_scene.section_styles.get(variant.key)

    def _sync_style_editor(self) -> None:
        if not hasattr(self, "_style_variant_combo"):
            return
        variant = self._selected_style_variant()
        scene = self._current_scene

        previous_syncing = self._is_syncing
        self._is_syncing = True
        try:
            self._style_rules_block.apply_style_object_projection(
                build_scene_section_style_projection(
                    scene,
                    getattr(self, "_current_template", None),
                    variant.key if variant is not None else "",
                    summary_variants=_generic_style_variants_for_scene(
                        scene,
                        getattr(self, "_current_template", None),
                    ),
                    restore_all_labels=self._restore_all_style_labels(),
                    undo_restore_all_labels=self._restore_all_style_snapshot_labels(),
                )
            )
        finally:
            self._is_syncing = previous_syncing

    def _set_style_editor_enabled(self, enabled: bool) -> None:
        self._style_rules_block.set_editor_editable(enabled)

    def _on_style_editor_edited(self, *_args) -> None:
        if self._is_syncing:
            return
        style = self._editable_section_style()
        if style is None:
            return
        self._clear_restore_all_style_snapshot()
        self._style_rules_block.apply_editor_to_style(style)
        self._sync_style_editor()
        self.style_rules_changed.emit()

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        unit_ss = f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        for lbl in self._unit_labels:
            lbl.setStyleSheet(unit_ss)
        if hasattr(self, "_style_rules_block"):
            self._style_rules_block.apply_theme()


class _SceneReferenceDetail(ReferenceDetail):
    """Scene-owned reference-list settings, reusing the existing reference controls."""

    scene_edited = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._proxy_syncing = False
        self._navigation_highlighter = NavigationHighlighter()
        self.template_edited.connect(self._on_reference_proxy_edited)
        self.save_requested.connect(self.scene_edited.emit)
        self.set_save_enabled(False)

    def set_scene(self, scene: SceneWorkspace, template: TemplateConfig | None = None) -> None:
        previous_snapshot = self._snapshot if scene is self._current_scene else None
        self._current_scene = scene
        proxy = self._reference_proxy_from_scene(scene, template)
        self._proxy_syncing = True
        try:
            self.set_template(proxy)
            if previous_snapshot is not None:
                self._snapshot = previous_snapshot
                self._refresh_action_state()
            else:
                self.capture_entry_snapshot()
            self.set_save_enabled(False)
        finally:
            self._proxy_syncing = False

    def _reference_proxy_from_scene(
        self,
        scene: SceneWorkspace,
        template: TemplateConfig | None,
    ) -> TemplateConfig:
        proxy = copy.deepcopy(template) if template is not None else TemplateConfig()
        proxy.reference_style = copy.deepcopy(scene.reference_style)
        proxy.styles = copy.deepcopy(getattr(proxy, "styles", {}) or {})
        proxy.styles.pop("references_body", None)
        section_styles = getattr(scene, "section_styles", {}) or {}
        reference_style = section_styles.get("references_body")
        if reference_style is not None:
            proxy.styles["references_body"] = copy.deepcopy(reference_style)
        return proxy

    def _on_reference_proxy_edited(self, proxy: TemplateConfig | None) -> None:
        if self._proxy_syncing or self._current_scene is None or proxy is None:
            return
        self._current_scene.reference_style = copy.deepcopy(proxy.reference_style)
        reference_style = proxy.styles.get("references_body")
        if reference_style is None:
            self._current_scene.section_styles.pop("references_body", None)
        else:
            self._current_scene.section_styles["references_body"] = copy.deepcopy(reference_style)
        self.scene_edited.emit()

    def focus_navigation_field(self, field_id: str) -> bool:
        widget = self._reference_navigation_widget(field_id)
        if widget is None:
            return False
        label = str(field_id or "").strip()
        self._navigation_highlighter.highlight(
            widget,
            label,
            display_label=(
                field_display_context(label).label_with_group()
                or field_display_name(label)
            ),
        )
        return True

    def _reference_navigation_widget(self, field_id: str):
        target = str(field_id or "").strip()
        if not target:
            return None
        if "references_body" not in target and "reference_style" not in target:
            return None
        field_widgets = (
            ("font_cn", "_font_cn_row"),
            ("font_en", "_font_en_row"),
            ("size_pt", "_size_row"),
            ("alignment", "_alignment_row"),
            ("line_spacing", "_line_spacing_row"),
            ("hanging_indent", "_hanging_indent_row"),
            ("space_after", "_space_after_row"),
        )
        for field_key, attr_name in field_widgets:
            if field_key in target and hasattr(self, attr_name):
                return getattr(self, attr_name)
        return getattr(self, "_style_form", None)


# ── 场景规则 ────────────────────────────────────────

class _SceneOutputRulesCard(QWidget):
    """Compact generated-result card shown inside scene rules."""

    scene_edited = Signal()

    def __init__(self, output_detail: QWidget, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._output_detail = output_detail
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
        self._delivery_flow = FlowLayout(self._delivery_choices, h_spacing=18, v_spacing=8)
        self._delivery_flow.setContentsMargins(0, 0, 0, 0)
        delivery_layout.addWidget(self._delivery_label, 0, Qt.AlignTop)
        delivery_layout.addWidget(self._delivery_choices, 1)
        self._card.add_widget(self._delivery_row)

        self._general_checks: dict[str, QCheckBox] = {}
        for key, label, tooltip in (
            ("final_docx", "最终 Word", "生成排版后的 Word 文件。"),
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
        self._exam_student_check.setToolTip("试卷场景默认生成学生卷。")
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

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._sync_choices(scene)
        self._sync_output_detail_visibility()

    def _sync_choices(self, scene: SceneWorkspace) -> None:
        self._is_syncing = True
        try:
            is_exam = _scene_is_exam(scene)
            for checkbox in self._general_checks.values():
                checkbox.setVisible(not is_exam)
            self._exam_student_check.setVisible(is_exam)
            self._exam_answer_check.setVisible(is_exam)

            if is_exam:
                config = _ensure_exam_paper_config(scene)
                _sync_exam_answer_delivery(
                    scene,
                    config.answer_policy,
                    preserve_default=True,
                )
                self._exam_student_check.setEnabled(True)
                self._exam_student_check.setChecked(config.answer_policy != "answer_only")
                self._exam_answer_check.setChecked(config.answer_policy != "student_only")
                return

            output = scene.output
            self._general_checks["final_docx"].setChecked(bool(output.final_docx))
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
        output = scene.output
        output.final_docx = self._general_checks["final_docx"].isChecked()
        output.compare_docx = self._general_checks["compare_docx"].isChecked()
        output.report_json = self._general_checks["report"].isChecked()
        output.report_markdown = self._general_checks["report"].isChecked()
        output.material_manifest = self._general_checks["material_manifest"].isChecked()
        output.material_package = self._general_checks["material_package"].isChecked()
        preset = self._selected_delivery_preset(scene)
        if preset is not None:
            preset.artifacts = copy.deepcopy(output)
        self.scene_edited.emit()

    def _on_exam_choice_changed(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        scene = self._current_scene
        config = _ensure_exam_paper_config(scene)
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
        selected_id = str(getattr(scene, "default_delivery_preset_id", "") or "").strip()
        for preset in list(getattr(scene, "delivery_presets", []) or []):
            if str(getattr(preset, "preset_id", "") or "").strip() == selected_id:
                return preset
        return None

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
    """Combined scene rule surface: boundary, format exceptions, output, and scene-owned rules."""

    def __init__(
        self,
        scope: _ScopeDetail,
        style_rules: _StyleRulesDetail,
        reference: _SceneReferenceDetail,
        output: QWidget,
        parent=None,
    ):
        super().__init__(parent)
        self._scope = scope
        self._style_rules = style_rules
        self._reference = reference
        self._output = output
        self._output_rules = _SceneOutputRulesCard(self._output, self)
        self._current_scene: SceneWorkspace | None = None
        self._output_rules.scene_edited.connect(self._on_output_rules_edited)
        if hasattr(self._output, "scene_edited"):
            self._output.scene_edited.connect(self._refresh_output_rules)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._scope)
        layout.addWidget(self._style_rules)
        layout.addWidget(self._reference)
        layout.addWidget(self._output_rules)
        layout.addWidget(self._output)
        layout.addStretch(1)

    def set_scene(self, scene: SceneWorkspace, template: TemplateConfig | None = None) -> None:
        self._current_scene = scene
        self._scope.set_scene(scene, template)
        self._style_rules.set_scene(scene, template)
        self._style_rules.setVisible(
            bool(_generic_style_variants_for_scene(scene, template))
        )
        self._reference.set_scene(scene, template)
        self._reference.setVisible(_scene_uses_reference_format(scene))
        if hasattr(self._output, "set_scene"):
            self._output.set_scene(scene)
        self._output_rules.set_scene(scene)
        refresh_layout_chain(self)
        refresh_layout_chain_later(self)

    def _refresh_output_rules(self) -> None:
        if self._current_scene is None:
            return
        self._output_rules.set_scene(self._current_scene)

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
        reference_target = (
            "references_body" in target or "reference_style" in target
        )
        if (
            reference_target
            and not self._reference.isHidden()
            and self._reference.focus_navigation_field(target)
        ):
            return True
        for detail in (self._scope, self._style_rules):
            if not detail.isHidden() and bool(detail.focus_navigation_field(target)):
                return True
        if (
            _scene_uses_reference_format(self._current_scene)
            and self._reference.focus_navigation_field(target)
        ):
            return True
        return False

    def focus_output_navigation_field(self, field_id: str = "") -> bool:
        target = str(field_id or "").strip()
        self._output_rules.expand()
        if hasattr(self._output, "focus_navigation_field"):
            return bool(self._output.focus_navigation_field(target or "default_delivery"))
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
        for detail in (self._scope, self._style_rules, self._reference, self._output_rules, self._output):
            if hasattr(detail, "apply_theme"):
                detail.apply_theme()


# ── 风险检查 ──────────────────────────────────────

class _CleanupDetail(_SimpleFormDetail):
    """Detail pane for cleanup + validation options."""

    def __init__(self, parent=None):
        super().__init__("风险检查", "scan", "编辑 Markdown 修复、对象风险和执行前校验选项。", parent)
        self._current_scene: SceneWorkspace | None = None

        self._compliance_summary = SummaryGrid(columns=3, parent=self._card)
        self._card.add_widget(self._compliance_summary)

        self._fix_breaks = ToggleSwitch(self, checked=True)
        self._fix_breaks.toggled_signal.connect(self._on_edited)
        rows = [template_form_row("段落修复", self._fix_breaks, parent=self._card)]

        self._remove_empty = ToggleSwitch(self, checked=True)
        self._remove_empty.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("空行清理", self._remove_empty, parent=self._card))

        self._normalize_spaces = ToggleSwitch(self, checked=True)
        self._normalize_spaces.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("空格规范", self._normalize_spaces, parent=self._card))

        self._validation_enabled = ToggleSwitch(self, checked=True)
        self._validation_enabled.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("执行前校验", self._validation_enabled, parent=self._card))

        self._object_preflight_enabled = ToggleSwitch(self, checked=True)
        self._object_preflight_enabled.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("对象预检", self._object_preflight_enabled, parent=self._card))

        self._scan_target_checks: dict[str, QCheckBox] = {}
        self._scan_targets_widget = QWidget(self)
        self._scan_targets_flow = FlowLayout(
            self._scan_targets_widget,
            h_spacing=14,
            v_spacing=4,
        )
        self._scan_targets_flow.setContentsMargins(0, 4, 0, 0)
        for target in OBJECT_PREFLIGHT_SCAN_TARGETS:
            checkbox = QCheckBox(PREFLIGHT_TARGET_LABELS.get(target, target), self._scan_targets_widget)
            checkbox.setToolTip(target)
            checkbox.toggled.connect(self._on_edited)
            self._scan_target_checks[target] = checkbox
            self._scan_targets_flow.addWidget(checkbox)
        rows.append(template_form_row("扫描目标", self._scan_targets_widget, parent=self._card))

        self._preservation_mode = StyledComboBox(self)
        _populate_combo(self._preservation_mode, PRESERVATION_MODE_LABELS)
        self._preservation_mode.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("保护模式", self._preservation_mode, parent=self._card))

        self._skip_high_risk = ToggleSwitch(self, checked=True)
        self._skip_high_risk.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("高风险跳过", self._skip_high_risk, parent=self._card))

        self._apply_family_preflight_btn = QPushButton("应用推荐目标", self)
        self._apply_family_preflight_btn.clicked.connect(self._apply_family_preflight_targets)
        rows.append(template_form_row("场景族预检", self._apply_family_preflight_btn, parent=self._card))

        self._compliance_failure = StyledComboBox(self)
        _populate_combo(self._compliance_failure, FAILURE_POLICY_LABELS)
        self._compliance_failure.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("失败策略", self._compliance_failure, parent=self._card))

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
        rows.append(template_form_row("报告粒度", self._report_level, parent=self._card))
        self._add_form_stack(rows)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._fix_breaks.setChecked(getattr(scene.md_cleanup, 'fix_paragraph_breaks', True))
            self._remove_empty.setChecked(getattr(scene.md_cleanup, 'remove_empty_paragraphs', True))
            self._normalize_spaces.setChecked(getattr(scene.whitespace, 'normalize_spaces', True))
            self._validation_enabled.setChecked(scene.module_switches.get("validation", False))
            preflight = scene.compliance_profile.object_preflight
            self._object_preflight_enabled.setChecked(preflight.enabled)
            self._set_scan_target_checks(preflight.scan_targets)
            _set_combo_by_data(self._preservation_mode, preflight.preservation_mode)
            self._skip_high_risk.setChecked(preflight.skip_high_risk_modules)
            _set_combo_by_data(self._compliance_failure, scene.compliance_profile.failure_policy)
            _set_combo_by_data(self._report_level, scene.compliance_profile.report_level)
            self._apply_family_preflight_btn.setEnabled(
                bool(recommended_object_preflight_targets_for_scene(scene))
            )
            self._compliance_summary.set_items(build_compliance_summary_items(scene))
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
        self._current_scene.module_switches["validation"] = self._validation_enabled.isChecked()
        profile = self._current_scene.compliance_profile
        preflight = profile.object_preflight
        preflight.enabled = self._object_preflight_enabled.isChecked()
        preflight.scan_targets = [
            target
            for target, checkbox in self._scan_target_checks.items()
            if checkbox.isChecked()
        ]
        preflight.preservation_mode = str(self._preservation_mode.currentData() or preflight.preservation_mode)
        preflight.skip_high_risk_modules = self._skip_high_risk.isChecked()
        profile.failure_policy = str(self._compliance_failure.currentData() or profile.failure_policy)
        profile.report_level = str(self._report_level.currentData() or profile.report_level)
        self._compliance_summary.set_items(build_compliance_summary_items(self._current_scene))
        self.scene_edited.emit()

    def _apply_family_preflight_targets(self) -> None:
        if self._current_scene is None:
            return
        targets = recommended_object_preflight_targets_for_scene(self._current_scene)
        if not targets:
            return
        self._current_scene.compliance_profile.object_preflight.scan_targets = list(targets)
        self._is_syncing = True
        try:
            self._set_scan_target_checks(targets)
        finally:
            self._is_syncing = False
        self._compliance_summary.set_items(build_compliance_summary_items(self._current_scene))
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
            _apply_template_button_contract((self._apply_family_preflight_btn, "secondary"))
        checkbox_style = build_checkbox_stylesheet(get_theme())
        for checkbox in self._scan_target_checks.values():
            checkbox.setStyleSheet(checkbox_style)


# ── 资料包与填充 ──────────────────────────────────────

class _ContentDetail(_SimpleFormDetail):
    """Detail pane for watermark + content fill."""

    def __init__(self, parent=None):
        super().__init__("资料包与填充", "pen-tool", "编辑资料包输入、字段填充和水印配置。", parent)
        self._current_scene: SceneWorkspace | None = None

        self._input_summary = SummaryGrid(columns=3, parent=self._card)
        self._card.add_widget(self._input_summary)

        self._material_requirement_block = _MaterialRequirementBlock(self)
        self._material_rule_selector = self._material_requirement_block
        self._material_rule_selector.edited.connect(self._on_edited)
        self._schema_validation_summary = self._material_rule_selector.preview_summary
        self._card.add_widget(self._schema_validation_summary)

        self._markdown_policy = StyledComboBox(self)
        _populate_combo(self._markdown_policy, MARKDOWN_POLICY_LABELS)
        self._markdown_policy.currentIndexChanged.connect(self._on_edited)
        rows = [template_form_row("Markdown", self._markdown_policy, parent=self._card)]

        self._latex_policy = StyledComboBox(self)
        _populate_combo(self._latex_policy, LATEX_POLICY_LABELS)
        self._latex_policy.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("LaTeX", self._latex_policy, parent=self._card))

        self._require_material = ToggleSwitch(self, checked=False)
        self._require_material.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("资料包必需", self._require_material, parent=self._card))

        self._schema_registry_tools = self._material_rule_selector.schema_registry_tools
        self._schema_registry_combo = self._material_rule_selector.schema_registry_combo
        self._set_primary_schema_btn = self._material_rule_selector.set_primary_button
        self._append_schema_btn = self._material_rule_selector.append_button
        self._replace_unknown_schema_btn = (
            self._material_rule_selector.replace_unrecognized_button
        )
        self._remove_unknown_schema_btn = (
            self._material_rule_selector.remove_unrecognized_button
        )
        self._material_schema_id = self._material_rule_selector.primary_schema_editor
        self._material_schema_ids = self._material_rule_selector.schema_list_editor
        self._required_material_fields = (
            self._material_rule_selector.required_material_fields_editor
        )
        self._required_image_roles = self._material_rule_selector.required_image_roles_editor
        rows.extend(self._material_rule_selector.form_rows(parent=self._card))

        self._input_failure = StyledComboBox(self)
        _populate_combo(self._input_failure, FAILURE_POLICY_LABELS)
        self._input_failure.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("失败策略", self._input_failure, parent=self._card))

        self._watermark_enabled = ToggleSwitch(self, checked=False)
        self._watermark_enabled.toggled_signal.connect(self._on_edited)
        rows.append(template_form_row("启用水印", self._watermark_enabled, parent=self._card))

        self._watermark_text = QLineEdit(self)
        self._watermark_text.setPlaceholderText("例如 内部传阅")
        self._watermark_text.textChanged.connect(self._on_edited)
        rows.append(template_form_row("水印文本", self._watermark_text, parent=self._card))
        self._add_form_stack(rows)
        self._apply_theme()

    def _apply_theme(self) -> None:
        super()._apply_theme()
        if not hasattr(self, "_material_rule_selector"):
            return
        self._material_rule_selector.apply_theme()
        _apply_template_line_edit_contract(self._watermark_text)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            profile = scene.input_source_profile
            _set_combo_by_data(self._markdown_policy, profile.markdown_policy)
            _set_combo_by_data(self._latex_policy, profile.latex_policy)
            self._require_material.setChecked(profile.require_material_package)
            self._material_rule_selector.set_scene(scene)
            _set_combo_by_data(self._input_failure, profile.failure_policy)
            self._watermark_enabled.setChecked(scene.watermark.enabled)
            self._watermark_text.setText(scene.watermark.text)
            self._sync_watermark_text_state()
            self._input_summary.set_items(build_input_profile_summary_items(scene))
            self._material_rule_selector.refresh_preview(scene)
            self._material_rule_selector.sync_actions()
        finally:
            self._is_syncing = False

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if not target:
            return False
        widget = self._schema_focus_widget(target)
        if widget is None:
            return False
        self._highlight_navigation_widget(widget, target)
        return True

    def _schema_focus_widget(self, field_id: str) -> QWidget | None:
        target = str(field_id or "").strip()
        widget = self._material_rule_selector.navigation_widget_for_field(target)
        if widget is not None:
            return widget
        if "." not in target:
            return self._material_schema_id
        return None

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        profile = self._current_scene.input_source_profile
        profile.markdown_policy = str(self._markdown_policy.currentData() or profile.markdown_policy)
        profile.latex_policy = str(self._latex_policy.currentData() or profile.latex_policy)
        profile.require_material_package = self._require_material.isChecked()
        self._material_rule_selector.apply_to_profile(profile)
        profile.failure_policy = str(self._input_failure.currentData() or profile.failure_policy)
        self._current_scene.watermark.enabled = self._watermark_enabled.isChecked()
        self._current_scene.watermark.text = self._watermark_text.text().strip()
        self._sync_watermark_text_state()
        self._input_summary.set_items(build_input_profile_summary_items(self._current_scene))
        self._material_rule_selector.refresh_preview(self._current_scene)
        self._material_rule_selector.sync_actions()
        self.scene_edited.emit()

    def _sync_watermark_text_state(self) -> None:
        if not hasattr(self, "_watermark_text"):
            return
        enabled = bool(self._watermark_enabled.isChecked())
        self._watermark_text.setEnabled(enabled)
        self._watermark_text.setToolTip(
            "水印启用后可编辑状态文本" if enabled else "启用水印后可编辑状态文本"
        )

    def _selected_registry_schema_id(self) -> str:
        return self._material_rule_selector.selected_schema_id()

    def _schema_ids_from_inputs(self) -> tuple[str, ...]:
        return self._material_rule_selector.schema_ids_from_inputs()

    def _suggest_unknown_schema_replacement(self, missing_ids: tuple[str, ...]) -> str:
        return self._material_rule_selector._suggest_unknown_schema_replacement(missing_ids)

    def _sync_schema_registry_actions(self) -> None:
        self._material_rule_selector.sync_actions()

    def _set_selected_schema_as_primary(self) -> None:
        self._material_rule_selector.set_selected_schema_as_primary()

    def _append_selected_schema(self) -> None:
        self._material_rule_selector.append_selected_schema()

    def _replace_unknown_schemas(self) -> None:
        self._material_rule_selector.replace_unrecognized_schemas()

    def _remove_unknown_schemas(self) -> None:
        self._material_rule_selector.remove_unrecognized_schemas()


# ── 生成结果 ────────────────────────────────────────

class _OutputDetail(_SimpleFormDetail):
    """Detail pane for output toggles."""

    family_defaults_applied = Signal()

    def __init__(self, parent=None):
        super().__init__("生成结果", "folder-output", "设置这个场景会生成哪些文件和交付版本。", parent)
        self._current_scene: SceneWorkspace | None = None
        self._visibility_rule_text_cache: dict[str, str] = {}

        self._delivery_summary = SummaryGrid(columns=2, parent=self._card)
        self._card.add_widget(self._delivery_summary)

        self._delivery_validation_summary = SummaryGrid(columns=3, parent=self._card)
        self._card.add_widget(self._delivery_validation_summary)

        self._default_delivery = StyledComboBox(self)
        self._default_delivery.setObjectName("scn_output_default_delivery")
        self._default_delivery.currentIndexChanged.connect(self._on_edited)
        primary_rows = [template_form_row("默认交付", self._default_delivery, parent=self._card)]
        advanced_rows: list[QWidget] = []

        self._preset_actions = QWidget(self)
        preset_actions_layout = QHBoxLayout(self._preset_actions)
        preset_actions_layout.setContentsMargins(0, 0, 0, 0)
        preset_actions_layout.setSpacing(8)
        self._add_preset_btn = QPushButton("新增版本", self._preset_actions)
        self._copy_preset_btn = QPushButton("复制版本", self._preset_actions)
        self._remove_preset_btn = QPushButton("移除版本", self._preset_actions)
        self._move_up_preset_btn = QPushButton("上移", self._preset_actions)
        self._move_down_preset_btn = QPushButton("下移", self._preset_actions)
        self._add_preset_btn.clicked.connect(self._add_delivery_preset)
        self._copy_preset_btn.clicked.connect(self._copy_delivery_preset)
        self._remove_preset_btn.clicked.connect(self._remove_delivery_preset)
        self._move_up_preset_btn.clicked.connect(lambda: self._move_delivery_preset(-1))
        self._move_down_preset_btn.clicked.connect(lambda: self._move_delivery_preset(1))
        preset_actions_layout.addWidget(self._add_preset_btn)
        preset_actions_layout.addWidget(self._copy_preset_btn)
        preset_actions_layout.addWidget(self._remove_preset_btn)
        preset_actions_layout.addWidget(self._move_up_preset_btn)
        preset_actions_layout.addWidget(self._move_down_preset_btn)
        preset_actions_layout.addStretch(1)
        primary_rows.append(template_form_row("版本管理", self._preset_actions, parent=self._card))

        self._preset_template_tools = QWidget(self)
        preset_template_layout = QHBoxLayout(self._preset_template_tools)
        preset_template_layout.setContentsMargins(0, 0, 0, 0)
        preset_template_layout.setSpacing(8)
        self._delivery_preset_template_combo = StyledComboBox(self._preset_template_tools)
        self._delivery_preset_template_combo.setObjectName("scn_output_business_template")
        _populate_delivery_preset_template_combo(self._delivery_preset_template_combo)
        self._add_preset_template_btn = QPushButton("套用模板", self._preset_template_tools)
        self._add_preset_template_btn.setToolTip("按所选版本模板新增交付版本。")
        self._add_preset_template_btn.clicked.connect(self._add_delivery_preset_from_template)
        self._apply_family_delivery_btn = QPushButton("应用推荐", self._preset_template_tools)
        self._apply_family_delivery_btn.setToolTip("按当前场景类型补齐推荐交付版本。")
        self._apply_family_delivery_btn.clicked.connect(self._apply_scene_family_defaults)
        preset_template_layout.addWidget(self._delivery_preset_template_combo, 1)
        preset_template_layout.addWidget(self._add_preset_template_btn)
        preset_template_layout.addWidget(self._apply_family_delivery_btn)
        primary_rows.append(template_form_row("版本模板", self._preset_template_tools, parent=self._card))

        self._delivery_preset_id = QLineEdit(self)
        self._delivery_preset_id.setObjectName("scn_output_preset_id")
        self._delivery_preset_id.setPlaceholderText("自动生成，可按需修改")
        self._delivery_preset_id.setToolTip("用于文件命名和内部引用；例如 review_copy。")
        self._delivery_preset_id.editingFinished.connect(self._on_preset_id_edited)
        advanced_rows.append(template_form_row("交付编号", self._delivery_preset_id, parent=self._card))

        self._delivery_label = QLineEdit(self)
        self._delivery_label.setObjectName("scn_output_preset_label")
        self._delivery_label.setPlaceholderText("例如 Review copy")
        self._delivery_label.textChanged.connect(self._on_edited)
        primary_rows.append(template_form_row("交付名称", self._delivery_label, parent=self._card))

        self._delivery_target_template = QLineEdit(self)
        self._delivery_target_template.setObjectName("scn_output_target_template")
        self._delivery_target_template.setPlaceholderText("留空则使用当前模板")
        self._delivery_target_template.textChanged.connect(self._on_edited)
        advanced_rows.append(template_form_row("目标模板", self._delivery_target_template, parent=self._card))

        self._delivery_target_template_combo = StyledComboBox(self)
        self._delivery_target_template_combo.setObjectName("scn_output_template_option")
        self._delivery_target_template_combo.currentIndexChanged.connect(
            self._on_target_template_combo_changed
        )
        advanced_rows.append(template_form_row("模板选项", self._delivery_target_template_combo, parent=self._card))

        self._delivery_output_dir = QLineEdit(self)
        self._delivery_output_dir.setObjectName("scn_output_dir_template")
        self._delivery_output_dir.setPlaceholderText("默认放到当前文档旁的 output 文件夹")
        self._delivery_output_dir.setToolTip("支持占位符，例如 {document_dir}/output。")
        self._delivery_output_dir.textChanged.connect(self._on_edited)
        advanced_rows.append(template_form_row("输出目录", self._delivery_output_dir, parent=self._card))

        self._delivery_filename = QLineEdit(self)
        self._delivery_filename.setObjectName("scn_output_filename_template")
        self._delivery_filename.setPlaceholderText("默认使用原文件名加交付编号")
        self._delivery_filename.setToolTip("支持占位符，例如 {stem}_{preset_id}。")
        self._delivery_filename.textChanged.connect(self._on_edited)
        advanced_rows.append(template_form_row("文件命名", self._delivery_filename, parent=self._card))

        self._delivery_variable_tools = QWidget(self)
        variable_tools_layout = QHBoxLayout(self._delivery_variable_tools)
        variable_tools_layout.setContentsMargins(0, 0, 0, 0)
        variable_tools_layout.setSpacing(8)
        self._delivery_variable_combo = StyledComboBox(self._delivery_variable_tools)
        self._delivery_variable_combo.setObjectName("scn_output_variable_combo")
        _populate_delivery_variable_combo(self._delivery_variable_combo)
        self._delivery_variable_combo.setToolTip("选择要插入到目录或文件名中的信息。")
        self._insert_output_variable_btn = QPushButton("放入目录", self._delivery_variable_tools)
        self._insert_filename_variable_btn = QPushButton("放入文件名", self._delivery_variable_tools)
        self._insert_output_variable_btn.clicked.connect(
            lambda: self._insert_delivery_variable(self._delivery_output_dir)
        )
        self._insert_filename_variable_btn.clicked.connect(
            lambda: self._insert_delivery_variable(self._delivery_filename)
        )
        variable_tools_layout.addWidget(self._delivery_variable_combo, 1)
        variable_tools_layout.addWidget(self._insert_output_variable_btn)
        variable_tools_layout.addWidget(self._insert_filename_variable_btn)
        advanced_rows.append(template_form_row("命名信息", self._delivery_variable_tools, parent=self._card))

        self._visibility_rule_tools = QWidget(self)
        visibility_rule_layout = QHBoxLayout(self._visibility_rule_tools)
        visibility_rule_layout.setContentsMargins(0, 0, 0, 0)
        visibility_rule_layout.setSpacing(8)
        self._visibility_selector_combo = StyledComboBox(self._visibility_rule_tools)
        self._visibility_selector_combo.setObjectName("scn_output_visibility_selector_combo")
        _populate_visibility_selector_combo(self._visibility_selector_combo)
        self._visibility_selector_combo.currentIndexChanged.connect(
            self._on_visibility_selector_combo_changed
        )
        self._visibility_selector_input = QLineEdit(self._visibility_rule_tools)
        self._visibility_selector_input.setObjectName("scn_output_visibility_selector")
        self._visibility_selector_input.setPlaceholderText("或输入自定义内容块名")
        self._visibility_selector_input.setToolTip("可粘贴 {{#visibility:answer}}，保存时只记录内容块名 answer。")
        self._visibility_action_combo = StyledComboBox(self._visibility_rule_tools)
        self._visibility_action_combo.setObjectName("scn_output_visibility_action")
        _populate_combo(self._visibility_action_combo, _VISIBILITY_ACTION_OPTIONS)
        self._insert_visibility_rule_btn = QPushButton("添加到规则", self._visibility_rule_tools)
        self._insert_visibility_rule_btn.clicked.connect(self._insert_visibility_rule)
        visibility_rule_layout.addWidget(self._visibility_selector_combo, 1)
        visibility_rule_layout.addWidget(self._visibility_selector_input, 1)
        visibility_rule_layout.addWidget(self._visibility_action_combo)
        visibility_rule_layout.addWidget(self._insert_visibility_rule_btn)
        advanced_rows.append(template_form_row("添加内容块", self._visibility_rule_tools, parent=self._card))

        self._final_docx = ToggleSwitch(self, checked=True)
        self._final_docx.setObjectName("scn_output_final_docx")
        self._final_docx.toggled_signal.connect(self._on_edited)
        primary_rows.append(template_form_row("最终 Word", self._final_docx, parent=self._card))

        self._compare_docx = ToggleSwitch(self, checked=True)
        self._compare_docx.setObjectName("scn_output_compare_docx")
        self._compare_docx.toggled_signal.connect(self._on_edited)
        primary_rows.append(template_form_row("对比 Word", self._compare_docx, parent=self._card))

        self._report_json = ToggleSwitch(self, checked=True)
        self._report_json.setObjectName("scn_output_report_json")
        self._report_json.toggled_signal.connect(self._on_edited)
        advanced_rows.append(template_form_row("报告 JSON", self._report_json, parent=self._card))

        self._report_md = ToggleSwitch(self, checked=True)
        self._report_md.setObjectName("scn_output_report_md")
        self._report_md.toggled_signal.connect(self._on_edited)
        advanced_rows.append(template_form_row("报告 Markdown", self._report_md, parent=self._card))

        self._material_manifest = ToggleSwitch(self, checked=False)
        self._material_manifest.setObjectName("scn_output_material_manifest")
        self._material_manifest.toggled_signal.connect(self._on_edited)
        primary_rows.append(template_form_row("资料清单", self._material_manifest, parent=self._card))

        self._material_package = ToggleSwitch(self, checked=False)
        self._material_package.setObjectName("scn_output_material_package")
        self._material_package.toggled_signal.connect(self._on_edited)
        primary_rows.append(template_form_row("资料包", self._material_package, parent=self._card))

        self._visibility_rules = TextArea(
            placeholder="answer=remove\nanalysis=remove",
            min_height=88,
            max_height=150,
            parent=self._card,
        )
        self._visibility_rules.setObjectName("scn_output_visibility_rules")
        self._visibility_rules._text_edit.setObjectName("scn_output_visibility_rules_text")
        self._visibility_rules.setToolTip("每行一条内容块规则，例如 answer=remove。建议先用上方控件添加。")
        self._visibility_rules.text_changed.connect(self._on_visibility_rules_edited)
        advanced_rows.append(template_form_row("内容块规则", self._visibility_rules, parent=self._card))

        self._add_form_stack(primary_rows)

        self._advanced_output_expanded = False
        self._advanced_output_header = QWidget(self._card)
        advanced_header_layout = QHBoxLayout(self._advanced_output_header)
        advanced_header_layout.setContentsMargins(0, 8, 0, 0)
        advanced_header_layout.setSpacing(8)
        self._advanced_output_title = QLabel("高级命名、规则与报告", self._advanced_output_header)
        self._advanced_output_title.setObjectName("scn_output_advanced_title")
        self._advanced_output_toggle_btn = QPushButton("展开", self._advanced_output_header)
        self._advanced_output_toggle_btn.clicked.connect(self._toggle_advanced_output)
        advanced_header_layout.addWidget(self._advanced_output_title)
        advanced_header_layout.addStretch(1)
        advanced_header_layout.addWidget(self._advanced_output_toggle_btn)
        self._card.add_widget(self._advanced_output_header)

        self._advanced_output_container = QWidget(self._card)
        advanced_output_layout = QVBoxLayout(self._advanced_output_container)
        advanced_output_layout.setContentsMargins(0, 0, 0, 0)
        advanced_output_layout.setSpacing(0)
        advanced_output_layout.addWidget(TemplateFormStack(advanced_rows, parent=self._advanced_output_container))
        self._card.add_widget(self._advanced_output_container)
        self._sync_advanced_output_visibility()
        self._apply_theme()

    def _apply_theme(self) -> None:
        super()._apply_theme()
        if not hasattr(self, "_delivery_preset_id"):
            return
        _apply_template_line_edit_contract(
            self._delivery_preset_id,
            self._delivery_label,
            self._delivery_target_template,
            self._delivery_output_dir,
            self._delivery_filename,
            self._visibility_selector_input,
        )
        _apply_template_button_contract(
            (self._add_preset_btn, "secondary"),
            (self._copy_preset_btn, "secondary"),
            (self._remove_preset_btn, "ghost-danger"),
            (self._move_up_preset_btn, "secondary"),
            (self._move_down_preset_btn, "secondary"),
            (self._add_preset_template_btn, "secondary"),
            (self._apply_family_delivery_btn, "secondary"),
            (self._insert_output_variable_btn, "secondary"),
            (self._insert_filename_variable_btn, "secondary"),
            (self._insert_visibility_rule_btn, "secondary"),
            (self._advanced_output_toggle_btn, "secondary"),
        )
        self._advanced_output_title.setStyleSheet(
            f"font-size: {get_theme().font_size_sm}px; "
            f"font-weight: {get_theme().font_weight_emphasis}; "
            f"color: {get_theme().text_primary};"
        )

    def _toggle_advanced_output(self) -> None:
        self._advanced_output_expanded = not self._advanced_output_expanded
        self._sync_advanced_output_visibility()

    def _sync_advanced_output_visibility(self) -> None:
        if not hasattr(self, "_advanced_output_container"):
            return
        self._advanced_output_container.setVisible(self._advanced_output_expanded)
        self._advanced_output_toggle_btn.setText(
            "收起" if self._advanced_output_expanded else "展开"
        )

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if not target:
            return False
        delivery_ids = {
            str(self._default_delivery.itemData(index) or "").strip()
            for index in range(self._default_delivery.count())
        }
        if target in delivery_ids:
            _set_combo_by_data(self._default_delivery, target)
            self._highlight_navigation_widget(self._default_delivery, target)
            return True

        mapping: dict[str, QWidget] = {
            "default_delivery": self._default_delivery,
            "preset_id": self._delivery_preset_id,
            "preset_label": self._delivery_label,
            "label": self._delivery_label,
            "target_template": self._delivery_target_template,
            "target_template_id": self._delivery_target_template,
            "template_options": self._delivery_target_template_combo,
            "output_dir": self._delivery_output_dir,
            "output_dir_template": self._delivery_output_dir,
            "filename": self._delivery_filename,
            "filename_template": self._delivery_filename,
            "visibility_selector_options": self._visibility_selector_combo,
            "visibility_selector": self._visibility_selector_input,
            "visibility_rules": self._visibility_rules,
            "final_docx": self._final_docx,
            "compare_docx": self._compare_docx,
            "report_json": self._report_json,
            "report_markdown": self._report_md,
            "report_md": self._report_md,
            "material_manifest": self._material_manifest,
            "material_package": self._material_package,
        }
        widget = mapping.get(target)
        if widget is None:
            widget = self._default_delivery
        if widget in {
            self._delivery_preset_id,
            self._delivery_target_template,
            self._delivery_target_template_combo,
            self._delivery_output_dir,
            self._delivery_filename,
            self._visibility_selector_combo,
            self._visibility_selector_input,
            self._visibility_rules,
            self._report_json,
            self._report_md,
        }:
            self._advanced_output_expanded = True
            self._sync_advanced_output_visibility()
        self._highlight_navigation_widget(widget, target)
        return True

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._populate_delivery_combo(scene.default_delivery_preset_id)
            self._sync_delivery_fields()
            self._final_docx.setChecked(scene.output.final_docx)
            self._compare_docx.setChecked(scene.output.compare_docx)
            self._report_json.setChecked(scene.output.report_json)
            self._report_md.setChecked(scene.output.report_markdown)
            self._material_manifest.setChecked(scene.output.material_manifest)
            self._material_package.setChecked(scene.output.material_package)
            self._sync_visibility_rules()
            self._delivery_summary.set_items(build_delivery_summary_items(scene))
            self._sync_delivery_validation_summary()
            self._sync_preset_action_buttons()
        finally:
            if self._default_delivery.signalsBlocked():
                self._default_delivery.blockSignals(False)
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        selected_id = str(self._default_delivery.currentData() or "")
        if selected_id and selected_id != self._current_scene.default_delivery_preset_id:
            self._current_scene.default_delivery_preset_id = selected_id
            preset = self._selected_delivery_preset()
            if preset is not None:
                self._current_scene.output = copy.deepcopy(preset.artifacts)
                self._sync_delivery_fields()
                self._sync_output_toggles()
                self._sync_visibility_rules()
                self._delivery_summary.set_items(build_delivery_summary_items(self._current_scene))
                self._sync_delivery_validation_summary()
                self.scene_edited.emit()
                return

        self._current_scene.output.final_docx = self._final_docx.isChecked()
        self._current_scene.output.compare_docx = self._compare_docx.isChecked()
        self._current_scene.output.report_json = self._report_json.isChecked()
        self._current_scene.output.report_markdown = self._report_md.isChecked()
        self._current_scene.output.material_manifest = self._material_manifest.isChecked()
        self._current_scene.output.material_package = self._material_package.isChecked()
        preset = self._selected_delivery_preset()
        if preset is not None:
            preset_id = str(getattr(preset, "preset_id", "") or "").strip()
            if preset_id:
                self._visibility_rule_text_cache[preset_id] = self._visibility_rules.get_text()
            preset.label = self._delivery_label.text().strip() or str(preset.preset_id or "")
            preset.target_template_id = self._delivery_target_template.text().strip()
            self._populate_target_template_combo(preset.target_template_id)
            preset.output_dir_template = (
                self._delivery_output_dir.text().strip() or "{document_dir}/output"
            )
            preset.filename_template = self._delivery_filename.text().strip() or "{stem}_{preset_id}"
            preset.artifacts = copy.deepcopy(self._current_scene.output)
            preset.content_visibility_rules = _parse_visibility_rules(
                self._visibility_rules.get_text()
            )
            self._refresh_selected_delivery_label(preset)
        self._delivery_summary.set_items(build_delivery_summary_items(self._current_scene))
        self._sync_delivery_validation_summary()
        self._sync_preset_action_buttons()
        self.scene_edited.emit()

    def _on_target_template_combo_changed(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        target_id = str(self._delivery_target_template_combo.currentData() or "").strip()
        self._set_line_text(self._delivery_target_template, target_id)
        self._on_edited()

    def _on_visibility_selector_combo_changed(self, *_args) -> None:
        selector = str(self._visibility_selector_combo.currentData() or "").strip()
        if selector:
            self._visibility_selector_input.setText(selector)

    def _on_visibility_rules_edited(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        preset = self._selected_delivery_preset()
        if preset is not None:
            preset_id = str(getattr(preset, "preset_id", "") or "").strip()
            if preset_id:
                self._visibility_rule_text_cache[preset_id] = self._visibility_rules.get_text()
            preset.content_visibility_rules = _parse_visibility_rules(
                self._visibility_rules.get_text()
            )
        self._delivery_summary.set_items(build_delivery_summary_items(self._current_scene))
        self._sync_delivery_validation_summary()
        self.scene_edited.emit()

    def _on_preset_id_edited(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        preset = self._selected_delivery_preset()
        if preset is None:
            return
        old_id = str(getattr(preset, "preset_id", "") or "").strip()
        requested_id = _safe_delivery_preset_id(self._delivery_preset_id.text())
        new_id = self._unique_delivery_preset_id(requested_id, exclude_preset=preset)
        if new_id != old_id:
            preset.preset_id = new_id
            self._current_scene.default_delivery_preset_id = new_id
            if old_id in self._visibility_rule_text_cache:
                self._visibility_rule_text_cache[new_id] = self._visibility_rule_text_cache.pop(old_id)
        self._is_syncing = True
        try:
            self._set_line_text(self._delivery_preset_id, new_id)
            self._populate_delivery_combo(new_id)
            self._delivery_summary.set_items(build_delivery_summary_items(self._current_scene))
            self._sync_delivery_validation_summary()
            self._sync_preset_action_buttons()
        finally:
            self._is_syncing = False
        self.scene_edited.emit()

    def _selected_delivery_preset(self):
        if self._current_scene is None:
            return None
        selected_id = str(self._current_scene.default_delivery_preset_id or "")
        return next(
            (
                preset
                for preset in self._current_scene.delivery_presets
                if str(preset.preset_id or "") == selected_id
            ),
            None,
        )

    def _populate_delivery_combo(self, selected_id: str = "") -> None:
        if self._current_scene is None:
            return
        self._default_delivery.blockSignals(True)
        try:
            self._default_delivery.clear()
            for preset in self._current_scene.delivery_presets:
                preset_id = str(getattr(preset, "preset_id", "") or "").strip()
                if not preset_id:
                    continue
                self._default_delivery.addItem(
                    delivery_preset_display_name(preset),
                    preset_id,
                )
                self._default_delivery.setItemData(
                    self._default_delivery.count() - 1,
                    delivery_preset_option_tooltip(preset),
                    Qt.ToolTipRole,
                )
            _set_combo_by_data(
                self._default_delivery,
                selected_id or self._current_scene.default_delivery_preset_id,
            )
        finally:
            self._default_delivery.blockSignals(False)

    def _populate_target_template_combo(self, selected_id: str = "") -> None:
        if self._current_scene is None:
            return
        selected = str(selected_id or "").strip()
        self._delivery_target_template_combo.blockSignals(True)
        try:
            self._delivery_target_template_combo.clear()
            current_id = _scene_current_template_id(self._current_scene)
            current_label = _template_display_label(current_id) if current_id else "当前模板"
            self._delivery_target_template_combo.addItem(f"跟随当前模板 - {current_label}", "")
            self._delivery_target_template_combo.setItemData(
                0,
                _template_option_tooltip(current_id),
                Qt.ToolTipRole,
            )
            for template_id in _scene_compatible_template_ids(self._current_scene):
                self._delivery_target_template_combo.addItem(_template_display_label(template_id), template_id)
                self._delivery_target_template_combo.setItemData(
                    self._delivery_target_template_combo.count() - 1,
                    _template_option_tooltip(template_id),
                    Qt.ToolTipRole,
                )
            if selected and self._delivery_target_template_combo.findData(selected) < 0:
                custom_label = _template_display_label(selected)
                self._delivery_target_template_combo.addItem(
                    f"自定义模板 - {custom_label}" if custom_label != selected else "自定义模板",
                    selected,
                )
                self._delivery_target_template_combo.setItemData(
                    self._delivery_target_template_combo.count() - 1,
                    _template_option_tooltip(selected),
                    Qt.ToolTipRole,
                )
            _set_combo_by_data(self._delivery_target_template_combo, selected)
        finally:
            self._delivery_target_template_combo.blockSignals(False)

    def _add_delivery_preset(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        preset_id = self._unique_delivery_preset_id("delivery")
        preset = DeliveryPreset(
            preset_id=preset_id,
            label=f"交付 {len(self._current_scene.delivery_presets) + 1}",
            output_dir_template="{preset_id}",
            filename_template="{stem}_{preset_id}",
            artifacts=copy.deepcopy(self._current_scene.output),
        )
        self._current_scene.delivery_presets.append(preset)
        self._select_delivery_preset(preset_id)

    def _add_delivery_preset_from_template(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        template_id = str(self._delivery_preset_template_combo.currentData() or "").strip()
        spec = _DELIVERY_PRESET_TEMPLATE_MAP.get(template_id)
        if spec is None:
            return
        preset_id = self._unique_delivery_preset_id(str(spec.get("preset_id", "") or "delivery"))
        artifacts = _apply_delivery_preset_template_artifacts(
            copy.deepcopy(self._current_scene.output),
            spec,
        )
        preset = DeliveryPreset(
            preset_id=preset_id,
            label=_delivery_preset_template_label(spec, preset_id),
            target_template_id=str(spec.get("target_template_id", "") or ""),
            output_dir_template=str(spec.get("output_dir_template", "") or "{preset_id}"),
            filename_template=str(spec.get("filename_template", "") or "{stem}_{preset_id}"),
            artifacts=artifacts,
            content_visibility_rules=_build_delivery_preset_template_rules(spec),
            include_structured_intermediate=bool(
                spec.get("include_structured_intermediate", False)
            ),
            report_level=str(spec.get("report_level", "") or "summary"),
        )
        self._current_scene.delivery_presets.append(preset)
        self._select_delivery_preset(preset_id)

    def _apply_scene_family_defaults(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        result = apply_planned_scene_family_defaults(self._current_scene)
        if not result.applied:
            self._sync_preset_action_buttons()
            return
        self._select_delivery_preset(result.default_delivery_preset_id)
        self.family_defaults_applied.emit()

    def _copy_delivery_preset(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        current = self._selected_delivery_preset()
        if current is None:
            return
        preset = copy.deepcopy(current)
        preset_id = str(getattr(current, "preset_id", "") or "delivery").strip()
        preset.preset_id = self._unique_delivery_preset_id(f"{preset_id}_copy")
        preset.label = f"{getattr(current, 'label', '') or preset_id} Copy"
        self._current_scene.delivery_presets.append(preset)
        self._select_delivery_preset(preset.preset_id)

    def _remove_delivery_preset(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        presets = list(self._current_scene.delivery_presets or [])
        if len(presets) <= 1:
            return
        selected_id = str(self._current_scene.default_delivery_preset_id or "").strip()
        selected_index = next(
            (
                index
                for index, preset in enumerate(presets)
                if str(getattr(preset, "preset_id", "") or "").strip() == selected_id
            ),
            0,
        )
        kept = [
            preset
            for preset in presets
            if str(getattr(preset, "preset_id", "") or "").strip() != selected_id
        ]
        if selected_id:
            self._visibility_rule_text_cache.pop(selected_id, None)
        self._current_scene.delivery_presets = kept
        next_index = min(selected_index, len(kept) - 1)
        next_id = str(getattr(kept[next_index], "preset_id", "") or "final").strip()
        self._select_delivery_preset(next_id)

    def _move_delivery_preset(self, offset: int) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        presets = list(self._current_scene.delivery_presets or [])
        selected_index = self._selected_delivery_preset_index()
        if selected_index < 0:
            return
        next_index = selected_index + int(offset)
        if next_index < 0 or next_index >= len(presets):
            self._sync_preset_action_buttons()
            return
        presets[selected_index], presets[next_index] = presets[next_index], presets[selected_index]
        self._current_scene.delivery_presets = presets
        selected_id = str(self._current_scene.default_delivery_preset_id or "").strip()
        self._is_syncing = True
        try:
            self._populate_delivery_combo(selected_id)
            self._delivery_summary.set_items(build_delivery_summary_items(self._current_scene))
            self._sync_delivery_validation_summary()
            self._sync_preset_action_buttons()
        finally:
            self._is_syncing = False
        self.scene_edited.emit()

    def _select_delivery_preset(self, preset_id: str) -> None:
        if self._current_scene is None:
            return
        self._current_scene.default_delivery_preset_id = str(preset_id or "").strip()
        preset = self._selected_delivery_preset()
        if preset is not None:
            self._current_scene.output = copy.deepcopy(preset.artifacts)
        self._is_syncing = True
        try:
            self._populate_delivery_combo(self._current_scene.default_delivery_preset_id)
            self._sync_delivery_fields()
            self._sync_output_toggles()
            self._sync_visibility_rules()
            self._delivery_summary.set_items(build_delivery_summary_items(self._current_scene))
            self._sync_delivery_validation_summary()
            self._sync_preset_action_buttons()
        finally:
            self._is_syncing = False
        self.scene_edited.emit()

    def _selected_delivery_preset_index(self) -> int:
        if self._current_scene is None:
            return -1
        selected_id = str(self._current_scene.default_delivery_preset_id or "").strip()
        return next(
            (
                index
                for index, preset in enumerate(self._current_scene.delivery_presets or [])
                if str(getattr(preset, "preset_id", "") or "").strip() == selected_id
            ),
            -1,
        )

    def _unique_delivery_preset_id(self, base: str, *, exclude_preset=None) -> str:
        existing = {
            str(getattr(preset, "preset_id", "") or "").strip()
            for preset in list(getattr(self._current_scene, "delivery_presets", []) or [])
            if preset is not exclude_preset
        }
        root = _safe_delivery_preset_id(base)
        candidate = root
        index = 2
        while candidate in existing:
            candidate = f"{root}_{index}"
            index += 1
        return candidate

    def _sync_preset_action_buttons(self) -> None:
        has_scene = self._current_scene is not None
        preset_count = (
            len(list(getattr(self._current_scene, "delivery_presets", []) or []))
            if has_scene
            else 0
        )
        self._add_preset_btn.setEnabled(has_scene)
        self._add_preset_template_btn.setEnabled(has_scene)
        can_apply_family_delivery = (
            has_scene and has_planned_scene_family_application(self._current_scene)
        )
        self._apply_family_delivery_btn.setEnabled(can_apply_family_delivery)
        self._apply_family_delivery_btn.setToolTip(
            _scene_family_delivery_preview_tooltip(
                self._current_scene if has_scene else None
            )
        )
        self._copy_preset_btn.setEnabled(has_scene and preset_count >= 1)
        self._remove_preset_btn.setEnabled(has_scene and preset_count > 1)
        self._insert_visibility_rule_btn.setEnabled(has_scene and preset_count >= 1)
        selected_index = self._selected_delivery_preset_index() if has_scene else -1
        self._move_up_preset_btn.setEnabled(selected_index > 0)
        self._move_down_preset_btn.setEnabled(
            selected_index >= 0 and selected_index < preset_count - 1
        )

    def _sync_output_toggles(self) -> None:
        if self._current_scene is None:
            return
        self._is_syncing = True
        try:
            self._final_docx.setChecked(self._current_scene.output.final_docx)
            self._compare_docx.setChecked(self._current_scene.output.compare_docx)
            self._report_json.setChecked(self._current_scene.output.report_json)
            self._report_md.setChecked(self._current_scene.output.report_markdown)
            self._material_manifest.setChecked(self._current_scene.output.material_manifest)
            self._material_package.setChecked(self._current_scene.output.material_package)
        finally:
            self._is_syncing = False

    def _insert_delivery_variable(self, line_edit: QLineEdit) -> None:
        variable = str(self._delivery_variable_combo.currentData() or "").strip()
        if not variable:
            return
        line_edit.insert(f"{{{variable}}}")
        line_edit.setFocus()

    def _insert_visibility_rule(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        selector_source = self._visibility_selector_input.text().strip()
        if not selector_source:
            selector_source = str(self._visibility_selector_combo.currentData() or "").strip()
        selector = _extract_visibility_selector_input(selector_source)
        if not selector or not _VISIBILITY_SELECTOR_RE.match(selector):
            self._visibility_selector_input.setFocus()
            self._visibility_selector_input.selectAll()
            return
        action = str(self._visibility_action_combo.currentData() or "remove")
        current_text = self._visibility_rules.get_text()
        next_text = _append_visibility_rule_text(current_text, selector, action)
        if next_text == current_text:
            self._visibility_selector_input.setFocus()
            self._visibility_selector_input.selectAll()
            return
        self._set_visibility_rules_text(next_text)
        self._visibility_selector_input.clear()
        _set_combo_by_data(self._visibility_selector_combo, "")
        self._on_visibility_rules_edited()

    def _sync_delivery_validation_summary(self) -> None:
        preset = self._selected_delivery_preset()
        self._delivery_validation_summary.set_items(
            _build_delivery_validation_items(
                preset,
                scene=self._current_scene,
                output_template=self._delivery_output_dir.text(),
                filename_template=self._delivery_filename.text(),
                visibility_text=self._visibility_rules.get_text(),
            )
        )

    def _sync_delivery_fields(self) -> None:
        preset = self._selected_delivery_preset()
        if preset is None:
            self._set_line_text(self._delivery_preset_id, "")
            self._set_line_text(self._delivery_label, "")
            self._set_line_text(self._delivery_target_template, "")
            self._populate_target_template_combo("")
            self._set_line_text(self._delivery_output_dir, "")
            self._set_line_text(self._delivery_filename, "")
            return
        self._set_line_text(
            self._delivery_preset_id,
            str(getattr(preset, "preset_id", "") or ""),
        )
        self._set_line_text(
            self._delivery_label,
            delivery_preset_display_name(preset),
        )
        self._set_line_text(
            self._delivery_target_template,
            str(getattr(preset, "target_template_id", "") or ""),
        )
        self._populate_target_template_combo(str(getattr(preset, "target_template_id", "") or ""))
        self._set_line_text(
            self._delivery_output_dir,
            str(getattr(preset, "output_dir_template", "") or "{document_dir}/output"),
        )
        self._set_line_text(
            self._delivery_filename,
            str(getattr(preset, "filename_template", "") or "{stem}_{preset_id}"),
        )

    def _set_line_text(self, line_edit: QLineEdit, text: str) -> None:
        line_edit.blockSignals(True)
        try:
            line_edit.setText(text)
        finally:
            line_edit.blockSignals(False)

    def _refresh_selected_delivery_label(self, preset) -> None:
        current_index = self._default_delivery.currentIndex()
        if current_index < 0:
            return
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        selected_id = str(self._default_delivery.itemData(current_index) or "").strip()
        if preset_id and selected_id != preset_id:
            return
        self._default_delivery.setItemText(
            current_index,
            delivery_preset_display_name(preset),
        )
        self._default_delivery.setItemData(
            current_index,
            delivery_preset_option_tooltip(preset),
            Qt.ToolTipRole,
        )

    def _sync_visibility_rules(self) -> None:
        preset = self._selected_delivery_preset()
        preset_id = str(getattr(preset, "preset_id", "") or "").strip() if preset else ""
        cached_text = self._visibility_rule_text_cache.get(preset_id)
        self._set_visibility_rules_text(
            cached_text
            if cached_text is not None
            else _format_visibility_rules(getattr(preset, "content_visibility_rules", []))
        )

    def _set_visibility_rules_text(self, text: str) -> None:
        self._visibility_rules.blockSignals(True)
        try:
            self._visibility_rules.set_text(text)
        finally:
            self._visibility_rules.blockSignals(False)


# ═══════════════════════════════════════════════════════════════════════
#  Main Panel (Master-Detail)
# ═══════════════════════════════════════════════════════════════════════

class ScenePanel(BasePanel):
    """Master-detail scene configuration panel."""

    panel_title = "场景配置"
    panel_icon = "target"

    _DETAIL_ATTR_NAMES = {
        "_exam_paper": "scn_exam_paper",
        "_rules": "scn_rules",
        "_scope": "scn_rules",
        "_style_rules": "scn_rules",
        "_reference": "scn_rules",
        "_output": "scn_rules",
        "_cleanup": "scn_cleanup",
        "_content": "scn_content",
    }

    def _setup_ui(self) -> None:
        self.setObjectName("ScenePanel")
        self._current_scene_path = self.bridge.current_scene_path()
        self._current_scene_source = self.bridge.current_scene_source()
        self._current_template: TemplateConfig | None = None
        self._scene_descriptors = list_scene_descriptors()
        self._scene_library_watcher = QFileSystemWatcher(self)
        self._scene_library_refresh_pending = False

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

        # Build only the first visible detail during panel construction. Other
        # scene editors are created on demand to keep first open responsive.
        self._overview = _SceneOverviewDetail(self._scene_descriptors)
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

        # Fixed top card
        card_id = "scn_overview"
        title, icon = CARD_DEFINITIONS[card_id]
        card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
        self._nav_cards[card_id] = card
        self._nav_rail.add_card(card_id, card)

        # Section header
        self._nav_section_headers["format_template"] = self._nav_rail.add_section_header(
            "场景策略"
        )

        for card_id in FORMAT_TEMPLATE_CARDS:
            title, icon = CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

        self._nav_section_headers["input_material"] = self._nav_rail.add_section_header("资料包")

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
                emit_signal=False,
            )
        if self.bridge.current_template() is None:
            self._sync_bound_template_from_scene(clear_dirty=True)
        self._show_detail("scn_overview")
        self._nav_rail.select_card("scn_overview")
        self._apply_theme()
        self._setup_scene_library_watcher()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        self.bridge.scene_changed.connect(self.on_scene_changed)
        self.bridge.template_changed.connect(self.on_template_changed)
        self.bridge.scene_dirty_changed.connect(lambda *_args: self._refresh_navigation_cards())
        self.bridge.template_dirty_changed.connect(lambda *_args: self._refresh_navigation_cards())
        self._nav_rail.card_selected.connect(self._show_detail)
        self._overview.scene_changed.connect(self._on_scene_changed)
        self._overview.scene_edited.connect(self._on_scene_edited)
        self._overview.navigate_requested.connect(self._show_detail_from_overview)
        self._overview.execute_requested.connect(self._navigate_to_quick_execute)
        self._overview.new_scene_requested.connect(self._on_new_scene_requested)
        self._overview.duplicate_scene_requested.connect(self._on_duplicate_scene_requested)
        self._overview.rename_scene_requested.connect(self._on_rename_scene_requested)
        self._overview.open_scene_folder_requested.connect(self._on_open_scene_folder_requested)
        self._overview.delete_scene_requested.connect(self._on_delete_scene_requested)
        self._overview.selector_open_requested.connect(self._refresh_scene_library_from_disk)
        self._scene_library_watcher.directoryChanged.connect(self._on_scene_library_path_changed)
        self._scene_library_watcher.fileChanged.connect(self._on_scene_library_path_changed)

    def __getattr__(self, name: str):
        detail_attrs = self.__dict__.get("_detail_attr_names", {})
        card_id = detail_attrs.get(name)
        if card_id:
            self._ensure_detail_loaded(card_id)
            if name in self.__dict__:
                return self.__dict__[name]
        raise AttributeError(f"{type(self).__name__} object has no attribute {name!r}")

    def _create_exam_paper_detail(self) -> QWidget:
        self._exam_paper = _ExamPaperDetail()
        return self._exam_paper

    def _create_rules_detail(self) -> QWidget:
        self._scope = _ScopeDetail()
        self._style_rules = _StyleRulesDetail()
        self._reference = _SceneReferenceDetail()
        self._output = _OutputDetail()
        self._rules = _SceneRulesDetail(
            self._scope,
            self._style_rules,
            self._reference,
            self._output,
        )
        return self._rules

    def _create_cleanup_detail(self) -> QWidget:
        self._cleanup = _CleanupDetail()
        return self._cleanup

    def _create_content_detail(self) -> QWidget:
        self._content = _ContentDetail()
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
        elif card_id == "scn_rules":
            self._scope.scope_changed.connect(self._on_scope_changed)
            self._style_rules.style_rules_changed.connect(self._on_style_rules_changed)
            for detail in (self._reference, self._output):
                detail.scene_edited.connect(self._mark_scene_detail_dirty)
            self._output.family_defaults_applied.connect(self._on_scene_family_defaults_applied)
        elif card_id in {"scn_cleanup", "scn_content"}:
            detail = self._detail_map.get(card_id)
            if hasattr(detail, "scene_edited"):
                detail.scene_edited.connect(self._mark_scene_detail_dirty)
        self._wired_detail_signal_ids.add(card_id)

    def _sync_loaded_detail_state(self, card_id: str, detail: QWidget) -> None:
        scene = getattr(self, "_current_scene", None)
        if scene is None:
            return
        if card_id == "scn_exam_paper" and hasattr(detail, "set_scene"):
            detail.set_scene(scene)
            return
        if card_id == "scn_rules" and hasattr(detail, "set_scene"):
            detail.set_scene(scene, getattr(self, "_current_template", None))
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
                self._nav_rail.select_card("scn_overview")
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
            or getattr(scene, "default_template_id", "")
            or ""
        ).strip()
        if not template_id:
            return None
        if self.bridge.current_template_id() == template_id:
            template = self.bridge.current_template()
            if template is not None:
                return template
        try:
            return load_template_from_library(template_id)
        except Exception:
            return None

    def _template_preview_context_for_scene(
        self,
        scene: SceneWorkspace | None,
        *,
        template=None,
    ):
        preview_template = template or self._resolve_template_for_scene(scene)
        if preview_template is None:
            preview_template = create_builtin_template("default")
        template_id = str(
            getattr(scene, "template_id", "")
            or getattr(scene, "default_template_id", "")
            or ""
        ).strip()
        template_label = _template_label_with_id(template_id) if template_id else "当前模板"
        return build_template_preview_context(
            preview_template,
            scene_label=self._scene_display_label(scene),
            template_label=template_label,
        )

    def _scene_display_label(self, scene: SceneWorkspace | None) -> str:
        scene_id = str(getattr(scene, "scene_id", "") or "").strip()
        for descriptor in self._scene_descriptors:
            if descriptor.config_id == scene_id:
                return descriptor.display_name
        return (
            str(getattr(scene, "name", "") or "").strip()
            or scene_id
            or "当前场景"
        )

    def _current_scene_id(self) -> str:
        return str(
            self.bridge.current_scene_id()
            or getattr(self._current_scene, "scene_id", "")
            or ""
        ).strip()

    def _builtin_scene_ids(self) -> set[str]:
        return _builtin_scene_id_set()

    def _current_scene_is_builtin(self) -> bool:
        scene_id = self._current_scene_id()
        return bool(scene_id and scene_id in self._builtin_scene_ids())

    def _current_scene_path_obj(self) -> Path | None:
        path = str(self._current_scene_path or "").strip()
        if path:
            return Path(path)
        scene_id = self._current_scene_id()
        if scene_id:
            entry = get_scene_entry(scene_id)
            if entry is not None:
                return entry.path
        return None

    def _current_scene_manage_path(self) -> Path | None:
        path = self._current_scene_path_obj()
        if path is None or not path.exists() or path.is_dir():
            return None
        return path

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
        path = self._current_scene_path_obj()
        if path is not None:
            folder = path if path.is_dir() else path.parent
            if folder.exists():
                return folder
        return config_library.SCENE_LIBRARY_DIR

    def _sync_scene_file_status(self) -> None:
        if not hasattr(self, "_overview"):
            return
        is_builtin = self._current_scene_is_builtin()
        can_rename = self._current_scene_can_rename()
        can_delete = self._current_scene_can_delete()
        self._overview.set_scene_action_state(
            can_rename=can_rename,
            can_delete=can_delete,
            rename_tooltip="" if can_rename else (
                "内置场景不能重命名，请先创建副本"
                if is_builtin else "当前场景还没有保存为场景文件"
            ),
            delete_tooltip="" if can_delete else (
                "内置场景不能删除，请先创建副本"
                if is_builtin else "当前场景还没有可删除的文件"
            ),
            folder_tooltip=str(self._current_scene_folder()),
        )

    def _scene_library_watch_directories(self) -> list[str]:
        config_library.SCENE_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        directories = [config_library.SCENE_LIBRARY_DIR]
        try:
            directories.extend(
                path
                for path in config_library.SCENE_LIBRARY_DIR.iterdir()
                if path.is_dir()
            )
        except Exception:
            pass
        return [str(path) for path in directories]

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
        self._setup_scene_library_watcher()
        if self._current_scene_file_was_removed():
            self._switch_to_default_scene_after_missing_file()
            return
        self._refresh_scene_selector_options()

    def _switch_to_default_scene_after_missing_file(self) -> None:
        message = "当前场景文件已不存在，已切换到默认场景"
        entry = default_scene_entry()
        if entry is not None:
            scene = load_scene_from_library(entry.config_id)
            self._activate_scene(
                scene,
                scene_id=entry.config_id,
                path=str(entry.path),
                source="library",
                dirty=False,
            )
        else:
            scene = SceneWorkspace(scene_id="custom", template_id="default")
            self._activate_scene(
                scene,
                scene_id="custom",
                path="",
                source="runtime",
                dirty=False,
            )
        Toast.show_info(message)

    def _refresh_scene_selector_options(self) -> None:
        self._scene_descriptors = list_scene_descriptors()
        self._overview.set_scene_options(
            self._scene_descriptors,
            current_scene_id=self._current_scene_id(),
        )
        self._sync_scene_file_status()

    def _activate_scene(
        self,
        scene: SceneWorkspace,
        *,
        scene_id: str,
        path: str = "",
        source: str = "library",
        dirty: bool = False,
    ) -> None:
        self._current_scene = scene
        self._current_scene_path = str(path or "").strip()
        self._current_scene_source = str(source or "").strip()
        self.bridge.set_current_scene(
            scene,
            config_id=scene_id,
            path=self._current_scene_path,
            source=self._current_scene_source,
            emit_signal=False,
        )
        if not dirty:
            self.bridge.clear_scene_dirty()
        self._refresh_scene_selector_options()
        self._sync_bound_template_from_scene(clear_dirty=not dirty)
        self._apply_scene(scene)

    def _scene_copy_base_name(self) -> str:
        if self._current_scene_is_builtin():
            name = self._scene_display_label(self._current_scene)
        else:
            name = str(
                getattr(self._current_scene, "name", "")
                or self._current_scene_id()
                or "自定义场景"
            )
        name = str(name or "").strip() or "自定义场景"
        return re.sub(r"\s*副本(?:\s*\d+)?$", "", name).strip() or name

    def _unique_scene_copy_name(self) -> str:
        base_name = self._scene_copy_base_name()
        existing_names = {
            str(descriptor.name or "").strip()
            for descriptor in list_scene_descriptors()
            if str(descriptor.name or "").strip()
        }

        def available(name: str) -> bool:
            if name in existing_names:
                return False
            scene_id = self._unique_scene_id_for_name(name)
            return scene_id == _safe_scene_file_stem(name)

        candidate = f"{base_name} 副本"
        if available(candidate):
            return candidate
        for index in range(2, 1000):
            candidate = f"{base_name} 副本 {index}"
            if available(candidate):
                return candidate
        return f"{base_name} 副本 1000"

    def _unique_scene_id_for_name(self, name: str) -> str:
        base_id = _safe_scene_file_stem(name)
        existing_ids = {
            str(descriptor.config_id or "").strip()
            for descriptor in list_scene_descriptors()
            if str(descriptor.config_id or "").strip()
        }
        existing_ids.update(self._builtin_scene_ids())

        def path_exists(scene_id: str) -> bool:
            return any(
                (config_library.SCENE_LIBRARY_DIR / f"{scene_id}{suffix}").exists()
                for suffix in (".json", ".yaml", ".yml")
            )

        if base_id not in existing_ids and not path_exists(base_id):
            return base_id
        for index in range(2, 1000):
            candidate = f"{base_id}_{index}"
            if candidate not in existing_ids and not path_exists(candidate):
                return candidate
        return f"{base_id}_1000"

    def _create_scene_copy(self, name: str, *, action_label: str) -> bool:
        scene = (
            copy.deepcopy(self._current_scene)
            if self._current_scene is not None
            else SceneWorkspace(scene_id="custom", template_id="default")
        )
        scene.name = name
        scene_id = self._unique_scene_id_for_name(name)
        scene.scene_id = scene_id
        try:
            entry = save_scene_to_library(scene, scene_id=scene_id)
            activated_scene = load_scene_from_library(entry.config_id)
        except Exception as exc:
            Toast.show_error(f"{action_label}失败: {exc}")
            return False
        self._activate_scene(
            activated_scene,
            scene_id=entry.config_id,
            path=str(entry.path),
            source="library",
            dirty=False,
        )
        Toast.show_success(f"已{action_label}: {name}")
        return True

    def _navigate_to_quick_execute(self) -> None:
        return_card_id = (
            self._nav_rail.selected_card_id()
            if hasattr(self, "_nav_rail") and self._nav_rail.selected_card_id() in self._detail_map
            else "scn_overview"
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

    def _navigation_card_snapshots(self, scene: SceneWorkspace) -> dict[str, dict[str, str]]:
        snapshots: dict[str, dict[str, str]] = {
            "scn_overview": self._overview_navigation_snapshot(scene),
            "scn_exam_paper": self._exam_paper_navigation_snapshot(scene),
            "scn_rules": self._rules_navigation_snapshot(scene),
            "scn_content": self._content_navigation_snapshot(scene),
        }
        return snapshots

    def _overview_navigation_snapshot(self, scene: SceneWorkspace) -> dict[str, str]:
        scene_label = self._scene_display_label(scene)
        template_label = _template_label_with_id(_scene_current_template_id(scene)) or "未绑定模板"
        dirty = bool(self.bridge.is_scene_dirty()) if hasattr(self.bridge, "is_scene_dirty") else False
        return {
            "subtitle": f"{scene_label} · {template_label}",
            "badge_text": "未保存" if dirty else "场景",
            "badge_variant": "warning" if dirty else "success",
        }

    def _rules_navigation_snapshot(self, scene: SceneWorkspace) -> dict[str, str]:
        boundary_mode = getattr(scene.application_boundary, "mode", "follow_template")
        override_count = self._style_override_count(scene)
        has_style_rules = bool(
            _generic_style_variants_for_scene(
                scene,
                getattr(self, "_current_template", None),
            )
        )
        style_summary = (
            f"{override_count} 个格式例外"
            if override_count
            else ("无格式例外" if has_style_rules else "")
        )
        return {
            "subtitle": _nav_join(
                (
                    _nav_scope_subtitle(boundary_mode),
                    style_summary,
                    self._output_result_nav_summary(scene),
                    "参考文献规则" if _scene_uses_reference_format(scene) else "",
                )
            ),
            "badge_text": scene_application_boundary_display_name(scene),
            "badge_variant": (
                "warning" if boundary_mode == "confirm_before_apply" else "success"
            ),
        }

    def _output_result_nav_summary(self, scene: SceneWorkspace) -> str:
        output_count = sum(
            1 for field_name in _NAV_OUTPUT_FIELDS if bool(getattr(scene.output, field_name, False))
        )
        preset = self._default_delivery_preset(scene)
        preset_label = str(
            getattr(preset, "label", "")
            or DELIVERY_PRESET_DISPLAY_LABELS.get(
                str(getattr(preset, "preset_id", "") or "").strip(),
                "",
            )
            or getattr(preset, "preset_id", "")
            or "默认交付"
        )
        preset_label = _nav_display_id(preset_label, DELIVERY_PRESET_DISPLAY_LABELS)
        return f"{preset_label} {output_count} 项产物" if output_count else "未配置产物"

    def _style_override_count(self, scene: SceneWorkspace) -> int:
        visible_keys = {
            variant.key
            for variant in _generic_style_variants_for_scene(
                scene,
                getattr(self, "_current_template", None),
            )
        }
        return sum(
            1
            for key, value in scene.section_styles.items()
            if key in visible_keys and value is not None
        )

    def _style_rules_navigation_snapshot(self, scene: SceneWorkspace) -> dict[str, str]:
        override_count = self._style_override_count(scene)
        if override_count:
            return {
                "subtitle": f"{override_count} 个格式例外 · 可恢复模板",
                "badge_text": f"{override_count} 项",
                "badge_variant": "info",
            }
        return {
            "subtitle": "跟随模板 · 无格式例外",
            "badge_text": "模板",
            "badge_variant": "neutral",
        }

    def _reference_navigation_snapshot(self, scene: SceneWorkspace) -> dict[str, str]:
        ref = scene.reference_style
        mode = "独立条目样式" if scene.section_styles.get("references_body") is not None else "跟随正文"
        return {
            "subtitle": (
                f"{mode} · 悬挂缩进 {ref.hanging_indent_cm:g}cm · "
                f"段后 {ref.space_after_pt:g}{getattr(ref, 'space_after_unit', 'pt')}"
            ),
            "badge_text": "论文",
            "badge_variant": "info",
        }

    def _exam_paper_navigation_snapshot(self, scene: SceneWorkspace) -> dict[str, str]:
        config = _ensure_exam_paper_config(scene)
        blank = exam_blank_style_label(config.blank_style_id, config)
        return {
            "subtitle": f"{blank} · 试卷母版",
            "badge_text": "试卷",
            "badge_variant": "info",
        }

    def _cleanup_navigation_snapshot(self, scene: SceneWorkspace) -> dict[str, str]:
        profile = scene.compliance_profile
        preflight = profile.object_preflight
        checks = len(profile.enabled_checks or [])
        scan_targets = len(preflight.scan_targets or [])
        enabled = bool(preflight.enabled or checks)
        return {
            "subtitle": _nav_join(
                (
                    f"检查 {checks} 项",
                    f"扫描目标 {scan_targets} 个",
                    FAILURE_POLICY_LABELS.get(profile.failure_policy, profile.failure_policy),
                )
            ),
            "badge_text": "已开启" if enabled else "未开启",
            "badge_variant": "success" if enabled else "neutral",
        }

    def _content_navigation_snapshot(self, scene: SceneWorkspace) -> dict[str, str]:
        profile = scene.input_source_profile
        formats = _nav_format_summary(tuple(profile.accepted_formats or ()))
        material_fields = len(profile.required_material_fields or [])
        schema_count = len(_profile_material_schema_ids(profile))
        configured = bool(
            profile.require_material_package
            or material_fields
            or schema_count
            or profile.material_schema_id
        )
        return {
            "subtitle": _nav_join(
                (
                    formats,
                    f"资料字段 {material_fields} 个",
                    f"资料规则 {schema_count} 项",
                )
            ),
            "badge_text": "已配置" if configured else "未开启",
            "badge_variant": "success" if configured else "neutral",
        }

    def _output_navigation_snapshot(self, scene: SceneWorkspace) -> dict[str, str]:
        output_count = sum(
            1 for field_name in _NAV_OUTPUT_FIELDS if bool(getattr(scene.output, field_name, False))
        )
        preset = self._default_delivery_preset(scene)
        preset_label = str(
            getattr(preset, "label", "")
            or DELIVERY_PRESET_DISPLAY_LABELS.get(
                str(getattr(preset, "preset_id", "") or "").strip(),
                "",
            )
            or getattr(preset, "preset_id", "")
            or "默认交付"
        )
        preset_label = _nav_display_id(preset_label, DELIVERY_PRESET_DISPLAY_LABELS)
        return {
            "subtitle": f"{preset_label} · {output_count} 项产物",
            "badge_text": f"{output_count} 项",
            "badge_variant": "success" if output_count else "warning",
        }

    def _default_delivery_preset(self, scene: SceneWorkspace):
        target_id = str(getattr(scene, "default_delivery_preset_id", "") or "").strip()
        for preset in scene.delivery_presets or []:
            if str(getattr(preset, "preset_id", "") or "").strip() == target_id:
                return preset
        return (scene.delivery_presets or [None])[0]

    def handle_navigation_intent(self, intent) -> None:
        self._set_return_navigation_intent(intent)
        card_id = str(navigation_intent_value(intent, "card_id", "") or "").strip()
        if not card_id:
            return
        self._show_detail_from_overview(card_id)
        self._focus_navigation_field(card_id, intent)

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
        detail = self._details.current_detail
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
        if issue_key:
            self._return_navigation_intent["field_id"] = issue_key
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

    def _navigate_return_target(self) -> None:
        if not self._return_navigation_intent:
            return
        self.bridge.navigate_to_intent.emit(dict(self._return_navigation_intent))
        self._return_bar.setVisible(False)

    def _on_new_scene_requested(self) -> None:
        default_name = self._unique_scene_copy_name()
        name = input_text(
            "新建场景",
            "请输入场景名称：",
            placeholder="例如：合同交付自定义场景",
            default=default_name,
            ok_text="创建",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            Toast.show_warning("场景名称不能为空")
            return
        self._create_scene_copy(name, action_label="新建场景")

    def _on_duplicate_scene_requested(self) -> None:
        name = self._unique_scene_copy_name()
        self._create_scene_copy(name, action_label="创建副本")

    def _on_rename_scene_requested(self) -> None:
        if not self._current_scene_can_rename():
            Toast.show_warning(
                "内置场景不能重命名，请先创建副本"
                if self._current_scene_is_builtin()
                else "当前场景还没有保存为场景文件"
            )
            return
        current_name = str(
            getattr(self._current_scene, "name", "") or self._current_scene_id() or ""
        ).strip()
        name = input_text(
            "重命名场景",
            "请输入新的场景名称：",
            placeholder="场景名称",
            default=current_name,
            ok_text="保存",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            Toast.show_warning("场景名称不能为空")
            return
        if self._current_scene is None:
            return
        scene_id = self._current_scene_id()
        self._current_scene.name = name
        try:
            entry = save_scene_to_library(self._current_scene, scene_id=scene_id)
            activated_scene = load_scene_from_library(entry.config_id)
        except Exception as exc:
            Toast.show_error(f"重命名场景失败: {exc}")
            return
        self._activate_scene(
            activated_scene,
            scene_id=entry.config_id,
            path=str(entry.path),
            source="library",
            dirty=False,
        )
        Toast.show_success(f"已重命名场景: {name}")

    def _on_open_scene_folder_requested(self) -> None:
        folder = self._current_scene_folder()
        folder.mkdir(parents=True, exist_ok=True)
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        if not opened:
            Toast.show_error(f"无法打开场景文件夹: {folder}")

    def _on_delete_scene_requested(self) -> None:
        if not self._current_scene_can_delete():
            Toast.show_warning(
                "内置场景不能删除，请先创建副本"
                if self._current_scene_is_builtin()
                else "当前场景还没有可删除的文件"
            )
            return
        path = self._current_scene_manage_path()
        if path is None:
            Toast.show_warning("当前场景还没有可删除的文件")
            return
        scene_name = str(
            getattr(self._current_scene, "name", "")
            or self._current_scene_id()
            or path.stem
        ).strip()
        if not confirm(
            "删除场景",
            f"确定删除场景“{scene_name}”吗？\n\n文件：{path.name}",
            confirm_text="删除",
            destructive=True,
            parent=self,
        ):
            return
        try:
            path.unlink()
        except Exception as exc:
            Toast.show_error(f"删除场景失败: {exc}")
            return

        entry = default_scene_entry()
        if entry is not None:
            scene = load_scene_from_library(entry.config_id)
            self._activate_scene(
                scene,
                scene_id=entry.config_id,
                path=str(entry.path),
                source="library",
                dirty=False,
            )
        else:
            scene = SceneWorkspace(scene_id="custom", template_id="default")
            self._activate_scene(
                scene,
                scene_id="custom",
                path="",
                source="runtime",
                dirty=False,
            )
        Toast.show_success(f"已删除场景: {scene_name}")

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

        scene = load_scene_from_library(descriptor.config_id)
        self._activate_scene(
            scene,
            scene_id=descriptor.config_id,
            path=str(descriptor.path),
            source="library",
            dirty=False,
        )

    def _apply_scene(self, scene: SceneWorkspace) -> None:
        template = self._resolve_template_for_scene(scene)
        self._current_template = template
        preview_context = self._template_preview_context_for_scene(
            scene,
            template=template,
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
            self._rules.set_scene(scene, template)
        if "scn_cleanup" in self._loaded_detail_ids:
            self._cleanup.set_scene(scene)
        if "scn_content" in self._loaded_detail_ids:
            self._content.set_scene(scene)

    def _on_scope_changed(self) -> None:
        self._mark_scene_detail_dirty()

    def _on_style_rules_changed(self) -> None:
        self._mark_scene_detail_dirty()

    def _refresh_scene_overview(self) -> None:
        template = self._resolve_template_for_scene(self._current_scene)
        preview_context = self._template_preview_context_for_scene(
            self._current_scene,
            template=template,
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
            emit_signal=False,
        )
        self.bridge.mark_scene_dirty(recheck=False)
        self._refresh_navigation_cards()

    def _update_dynamic_card_visibility(self) -> None:
        """Show/hide scenario-specific nav cards."""
        scene = self._current_scene
        exam_card = self._nav_cards.get("scn_exam_paper")
        if exam_card is not None:
            exam_card.setVisible(_scene_is_exam(scene))
        content_card = self._nav_cards.get("scn_content")
        if content_card is not None:
            content_card.setVisible(_scene_should_show_content_card(scene))
        selected_id = self._nav_rail.selected_card_id()
        selected_card = self._nav_cards.get(str(selected_id or ""))
        if selected_card is not None and selected_card.isHidden():
            self._nav_rail.select_card("scn_overview")
        self._refresh_nav_section_headers()

    def _refresh_nav_section_headers(self) -> None:
        for section_id, card_ids in NAV_SECTION_CARD_GROUPS:
            header = self._nav_section_headers.get(section_id)
            if header is None:
                continue
            has_visible_card = any(
                (card := self._nav_cards.get(card_id)) is not None and not card.isHidden()
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
            emit_signal=False,
        )
        self.bridge.mark_scene_dirty(recheck=False)
        self._sync_bound_template_from_scene(clear_dirty=False)
        if was_dirty:
            self._refresh_navigation_cards()

    def _on_scene_family_defaults_applied(self) -> None:
        self._apply_scene(self._current_scene)
        self._on_scene_edited()

    def _sync_bound_template_from_scene(self, *, clear_dirty: bool) -> None:
        template_id = str(getattr(self._current_scene, "template_id", "") or "").strip()
        if not template_id:
            return
        if (
            self.bridge.current_template() is not None
            and self.bridge.current_template_id() == template_id
        ):
            if clear_dirty:
                self.bridge.clear_template_dirty()
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
        if getattr(self, "_ignore_own_scene_changed", False):
            return
        self._refresh_scene_selector_options()
        self._apply_scene(scene)
        self._refresh_navigation_cards()

    def on_template_changed(self, template) -> None:
        if self._current_scene is None:
            return
        self._current_template = template
        if "scn_rules" in self._loaded_detail_ids:
            self._rules.set_scene(self._current_scene, template)
        preview_context = self._template_preview_context_for_scene(
            self._current_scene,
            template=template,
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
