"""Floating material-field editing behavior for quick execution."""

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



class QuickExecutionFloatingFieldsMixin:
    """Project and edit execution-scoped material fields."""

    def _floating_field_display_name(self, field_key: str, _value: object = "") -> str:
        spec = self._floating_field_specs.get(field_key)
        label = spec.label if spec is not None else field_key
        namespace = (
            MaterialTokenNamespace.TIME
            if spec is not None and spec.timeline
            else MaterialTokenNamespace.TEXT
        )
        token = (
            "图片水印"
            if field_key == RUNTIME_IMAGE_WATERMARK_KEY
            else material_token(namespace, field_key)
        )
        return f"{token} · {label}" if label and label != token else token

    def _floating_field_editor_kind(self, field_key: str) -> str:
        spec = self._floating_field_specs.get(field_key)
        if spec is not None:
            return spec.editor_kind
        if re.fullmatch(
            r"时间段(?:\d+(?:开始|结束)日期|(?:开始|结束)日期\d+)",
            str(field_key or ""),
        ):
            return "date"
        kinds = {spec.field_key: spec.editor_kind for spec in OFFICIAL_MATERIAL_FIELD_SPECS}
        return kinds.get(field_key, "single_line")

    def _floating_field_placeholder(self, field_key: str) -> str:
        kind = self._floating_field_editor_kind(field_key)
        spec = self._floating_field_specs.get(field_key)
        label = (
            spec.label
            if spec is not None
            else official_material_field_label(field_key)
        )
        if not re.fullmatch(
            r"时间段\d+(?:开始|结束)日期",
            str(field_key or ""),
        ) and not label[-1:].isdigit():
            label += "1"
        if kind == "date":
            return "例如：2026-07-31"
        if kind == "multi_value":
            return f"填写{label}，使用顿号分隔"
        return f"填写{label}"

    def _refresh_floating_fields_card(self) -> None:
        if not hasattr(self, "_floating_fields_card"):
            return
        preview = self._material_preview_snapshot
        specs = tuple(preview.runtime_fields) if preview is not None else ()
        self._floating_field_specs = {item.key: item for item in specs}
        selection = self._material_selection
        overrides = (
            dict(selection.runtime_field_overrides)
            if selection is not None
            else {}
        )
        self._floating_field_render_values = {
            item.key: (
                selection.runtime_image_watermark_text
                if selection is not None and item.image_watermark
                else overrides.get(item.key, item.value)
            )
            for item in specs
        }
        self._floating_generated_keys = set()
        controller = getattr(self, "_floating_fields_controller", None)
        if controller is not None:
            controller.reconcile(
                [
                    (item.key, index + 1 == len(specs))
                    for index, item in enumerate(specs)
                ]
            )
        completed = sum(
            bool(value.strip())
            for value in self._floating_field_render_values.values()
        )
        self._set_floating_fields_progress(completed, len(specs))
        self._floating_fields_card.setVisible(bool(specs))

    def _create_floating_field_row(self, item: tuple[str, bool]) -> QWidget:
        key, _is_last = item
        row = QWidget(self._floating_fields_container)
        row.setObjectName("wb_floating_field_row")
        row.setProperty("fieldKey", key)
        row.setAttribute(Qt.WA_StyledBackground)
        row.setMinimumHeight(56)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(12)

        value = self._floating_field_render_values.get(key, "")
        label = QLabel(self._floating_field_display_name(key, value), row)
        label.setObjectName("wb_floating_field_name")
        label.setProperty("fieldKey", key)
        label.setMinimumWidth(240)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout.addWidget(label, 0)

        edit = OfficialFieldValueEdit(
            editor_kind=self._floating_field_editor_kind(key),
            read_only=key in self._floating_generated_keys,
            parent=row,
        )
        edit.setObjectName("wb_floating_field_input")
        edit.setText(value)
        edit.textChanged.connect(
            lambda text, field_key=key: self._on_floating_field_changed(
                field_key,
                text,
            )
        )
        layout.addWidget(edit, 1)
        self._floating_field_rows[key] = row
        self._floating_field_name_labels[key] = label
        self._floating_field_inputs[key] = edit
        row.setVisible(True)
        return row

    def _update_floating_field_row(
        self,
        row: QWidget,
        item: tuple[str, bool],
        _index: int,
    ) -> None:
        key, is_last = item
        value = self._floating_field_render_values.get(key, "")
        label = self._floating_field_name_labels[key]
        edit = self._floating_field_inputs[key]
        label.setText(self._floating_field_display_name(key, value))
        self._style_floating_field_name(label, value)
        if not edit.hasFocus() and edit.text() != value:
            blocked = edit.blockSignals(True)
            edit.setText(value)
            edit.blockSignals(blocked)
        generated = key in self._floating_generated_keys
        edit.setReadOnly(generated)
        edit.setPlaceholderText(self._floating_field_placeholder(key))
        edit.setToolTip(
            "由字段函数或时间计划自动生成；请在资料区修改"
            if generated
            else ""
        )
        theme = get_theme()
        divider = "transparent" if is_last else theme.divider
        row.setStyleSheet(
            f"""
            QWidget#wb_floating_field_row {{
                border: none;
                border-bottom: 1px solid {divider};
                background: transparent;
            }}
            QWidget#wb_floating_field_row:hover {{ background: {theme.bg_hover}; }}
            """
        )
        row.setVisible(True)

    def _dispose_floating_field_row(self, row: QWidget) -> None:
        key = str(row.property("fieldKey") or "")
        self._floating_field_rows.pop(key, None)
        self._floating_field_name_labels.pop(key, None)
        self._floating_field_inputs.pop(key, None)
        row.hide()
        row.setParent(None)
        row.deleteLater()

    def _on_floating_field_changed(self, key: str, value: str) -> None:
        selection = self._material_selection
        if selection is None or key not in self._floating_field_specs:
            return
        normalized = str(value or "")
        overrides = dict(selection.runtime_field_overrides)
        if key == RUNTIME_IMAGE_WATERMARK_KEY:
            selection = replace(
                selection,
                runtime_image_watermark_text=normalized,
            )
        else:
            if normalized:
                overrides[key] = normalized
            else:
                overrides.pop(key, None)
            selection = replace(
                selection,
                runtime_field_overrides=overrides,
            )
        self._material_selection = selection
        self._floating_field_render_values[key] = normalized
        label = self._floating_field_name_labels.get(key)
        if label is not None:
            self._style_floating_field_name(label, normalized)
        self._set_floating_fields_progress(
            sum(
                bool(item.strip())
                for item in self._floating_field_render_values.values()
            ),
            len(self._floating_field_specs),
        )
        self._invalidate_execution_feedback()
        self._emit_summary_changed()

    def _style_floating_field_name(self, label: QLabel, value: object) -> None:
        theme = get_theme()
        completed = bool(str(value or "").strip())
        label.setStyleSheet(
            f"font-size: {theme.font_size_md}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.primary if completed else theme.text_primary}; "
            "background: transparent;"
        )
        label.setToolTip(
            "资料变量，由系统映射到母版占位符"
            if completed
            else "本字段仅用于当前生成任务"
        )

    def _set_floating_fields_progress(self, completed: int, total: int) -> None:
        if total <= 0:
            self._floating_fields_progress.setText("")
            return
        self._floating_fields_progress.setText(
            f"已完成 {total}/{total}" if completed >= total else f"{completed}/{total} 已填写"
        )
        theme = get_theme()
        self._floating_fields_progress.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.success if completed >= total else theme.text_secondary}; "
            "background: transparent;"
        )
