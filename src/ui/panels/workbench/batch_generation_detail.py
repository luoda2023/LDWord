from __future__ import annotations

import html as _html
from pathlib import Path

from src.config.library import load_scene_from_library
from src.config.material_batch import (
    MaterialBatchSelection,
    build_material_batch_items,
    check_material_batch_preflight,
)
from src.config.scene import SceneWorkspace
from src.config.scene_surface_registry import scene_uses_official_document_surface
from src.qt_api import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QIcon,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui import ThemedRadioButton
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.path_action_semantics import PathAction, path_action_presentation
from src.shared.ui.sizing import apply_size_class, resolved_control_height
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.config_selector_models import (
    plan_selector_options,
    strip_source_prefix,
    template_selector_options,
)
from src.ui.adapters.workbench_execution_gate import ExecutionGateDecision
from src.ui.adapters.workbench_material_issues import (
    material_batch_readiness_gate_decision,
)
from src.shared.ui.icons.catalog import get_icon

from .batch_generation_source_area import BatchGenerationSourceArea
from .quick_execution_result_presenter import build_execution_result_presentation
from .state import ExecutionProgressState, ExecutionResultState


def _source_badge(source_type: object) -> tuple[str, str]:
    is_builtin = str(source_type or "").strip() == "builtin"
    return ("内置", "builtin") if is_builtin else ("自定", "user")


class BatchGenerationDetail(QWidget):
    """Independent multi-document execution surface aligned with quick execute."""

    source_document_selected = Signal(str)
    binding_changed = Signal(object, str)
    execute_requested = Signal()
    retry_requested = Signal()
    cancel_requested = Signal()
    summary_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("wb_batch_generation_detail")

        self._scene = SceneWorkspace(scene_id="default")
        self._work_mode_id = "custom"
        self._selection = MaterialBatchSelection()
        self._source_document_path = ""
        self._plan_label = "未绑定方案"
        self._template_label = "未绑定模板"
        self._binding_signal_blocked = False
        self._execution_running = False
        self._execution_cancel_requested = False
        self._actions_enabled = True
        self._last_result_status = "idle"
        self._last_retry_profile_ids: list[str] = []
        self._last_batch_run_id = ""
        self._last_batch_attempt_number = 1
        self._log_expanded = False
        self._runtime_template_overrides: dict[str, object] = {}

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(get_theme().template_detail_section_gap)
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._build_source_area()
        self._build_binding_card()
        self._build_output_card()
        self._build_execution_card()
        self._layout.addStretch(1)

        bind_theme(self, self._apply_theme)
        self._apply_theme()
        self._populate_scene_options()
        self._populate_template_options()
        self._refresh_projection()

    def _build_source_area(self) -> None:
        self._source_area = BatchGenerationSourceArea(self)
        self._source_area.source_document_selected.connect(
            self._on_source_document_selected
        )
        self._layout.addWidget(self._source_area)

    def _build_binding_card(self) -> None:
        self._binding_card = Card(parent=self)
        self._binding_card.setObjectName("wb_batch_binding_card")
        self._binding_card.set_header("处理方案与模板", icon_name="boxes")

        row = QWidget(self._binding_card)
        row.setObjectName("wb_batch_binding_selector_row")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self._scene_icon_label = QLabel(row)
        self._scene_icon_label.setFixedSize(16, 16)
        row_layout.addWidget(self._scene_icon_label)

        self._scene_text_label = QLabel("处理方案", row)
        self._scene_text_label.setObjectName("scene_tpl_label")
        row_layout.addWidget(self._scene_text_label)

        self._scene_combo = StyledComboBox(row)
        self._scene_combo.setObjectName("wb_batch_scene_combo")
        self._scene_combo.set_full_width_mode(True)
        self._scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        row_layout.addWidget(self._scene_combo, 1)

        row_layout.addSpacing(10)

        self._template_icon_label = QLabel(row)
        self._template_icon_label.setFixedSize(16, 16)
        row_layout.addWidget(self._template_icon_label)

        self._template_text_label = QLabel("模板", row)
        self._template_text_label.setObjectName("scene_tpl_label")
        row_layout.addWidget(self._template_text_label)

        self._template_combo = StyledComboBox(row)
        self._template_combo.setObjectName("wb_batch_template_combo")
        self._template_combo.set_full_width_mode(True)
        self._template_combo.currentIndexChanged.connect(self._on_template_changed)
        row_layout.addWidget(self._template_combo, 1)

        self._binding_card.add_widget(row)
        self._layout.addWidget(self._binding_card)

    def _build_output_card(self) -> None:
        self._output_card = Card(parent=self)
        self._output_card.setObjectName("wb_batch_output_card")
        self._output_card.set_header(
            "输出目录",
            icon_name="square-arrow-out-up-right",
        )

        row = QWidget(self._output_card)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

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

        self._output_browse_btn = QPushButton("选择目录", row)
        self._output_browse_btn.setObjectName("wb_batch_output_browse")
        self._output_browse_btn.setProperty(
            "pathAction",
            PathAction.CHOOSE_DIRECTORY.value,
        )
        self._output_browse_btn.setCursor(Qt.PointingHandCursor)
        self._output_browse_btn.clicked.connect(self._on_output_browse)
        size_policy = self._output_browse_btn.sizePolicy()
        size_policy.setRetainSizeWhenHidden(True)
        self._output_browse_btn.setSizePolicy(size_policy)
        self._output_browse_btn.setVisible(False)
        row_layout.addWidget(self._output_browse_btn, 1)

        self._output_preview = QLabel("选择批次资料后显示输出预览", row)
        self._output_preview.setObjectName("wb_batch_output_preview")
        self._output_preview.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(self._output_preview, 1)

        self._custom_output_dir = ""
        self._output_card.add_widget(row)
        self._layout.addWidget(self._output_card)

    def _build_execution_card(self) -> None:
        self._execution_card = Card(parent=self)
        self._execution_card.setObjectName("wb_batch_execution_card")
        self._execution_card.set_header("执行输出", icon_name="terminal")

        execution_row = QWidget(self._execution_card)
        execution_layout = QHBoxLayout(execution_row)
        execution_layout.setContentsMargins(0, 0, 0, 0)
        execution_layout.setSpacing(0)

        self._execute_btn = QPushButton("开始批量生成", execution_row)
        self._execute_btn.setObjectName("wb_batch_execute_btn")
        self._execute_btn.setCursor(Qt.PointingHandCursor)
        self._execute_btn.clicked.connect(self.execute_requested.emit)
        apply_size_class(self._execute_btn, "lg")
        execution_layout.addWidget(self._execute_btn, 4)

        self._exec_status_area = QWidget(execution_row)
        self._exec_status_area.setObjectName("wb_batch_exec_status_area")
        height = resolved_control_height(get_theme(), "lg")
        self._exec_status_area.setMinimumHeight(height)
        self._exec_status_area.setMaximumHeight(height)
        status_layout = QVBoxLayout(self._exec_status_area)
        status_layout.setContentsMargins(12, 0, 12, 0)
        status_layout.setSpacing(0)

        self._exec_status_label = QLabel("等待批次资料", self._exec_status_area)
        self._exec_status_label.setObjectName("wb_batch_exec_status")
        self._exec_status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        status_layout.addWidget(self._exec_status_label, 1)

        self._exec_bar = QProgressBar(self._exec_status_area)
        self._exec_bar.setObjectName("wb_batch_exec_bar")
        self._exec_bar.setRange(0, 100)
        self._exec_bar.setValue(0)
        self._exec_bar.setTextVisible(False)
        self._exec_bar.setMinimumHeight(4)
        self._exec_bar.setMaximumHeight(4)
        self._exec_bar.setVisible(False)
        status_layout.addWidget(self._exec_bar)
        execution_layout.addWidget(self._exec_status_area, 9)

        self._retry_btn = QPushButton("重试失败项", execution_row)
        self._retry_btn.setObjectName("wb_batch_retry_btn")
        self._retry_btn.setCursor(Qt.PointingHandCursor)
        self._retry_btn.clicked.connect(self.retry_requested.emit)
        self._retry_btn.setVisible(False)
        apply_size_class(self._retry_btn, "lg")
        execution_layout.addWidget(self._retry_btn, 3)

        self._cancel_btn = QPushButton("取消生成", execution_row)
        self._cancel_btn.setObjectName("wb_batch_cancel_btn")
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._request_cancel)
        self._cancel_btn.setVisible(False)
        apply_size_class(self._cancel_btn, "lg")
        execution_layout.addWidget(self._cancel_btn, 2)

        self._execution_card.add_widget(execution_row)

        self._log_toggle_btn = QPushButton("查看执行日志", self._execution_card)
        self._log_toggle_btn.setObjectName("wb_batch_log_toggle")
        self._log_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._log_toggle_btn.clicked.connect(self._toggle_log_visibility)
        self._log_toggle_btn.setVisible(False)
        self._execution_card.add_widget(self._log_toggle_btn)

        self._exec_log = QTextEdit(self._execution_card)
        self._exec_log.setObjectName("wb_batch_exec_log")
        self._exec_log.setReadOnly(True)
        self._exec_log.setMinimumHeight(120)
        self._exec_log.setMaximumHeight(200)
        self._exec_log.setVisible(False)
        self._execution_card.add_widget(self._exec_log)

        self._layout.addWidget(self._execution_card)

    def _populate_scene_options(self, *, current_scene_id: str = "") -> None:
        target = str(current_scene_id or self._scene.scene_id or "").strip()
        blocked = self._scene_combo.blockSignals(True)
        try:
            self._scene_combo.clear()
            selected_index = -1
            for option in plan_selector_options(
                self._work_mode_id,
                include_source_prefix=False,
            ):
                badge_text, badge_kind = _source_badge(option.source_type)
                index = self._scene_combo.add_badged_item(
                    option.label,
                    option.value,
                    badge_text=badge_text,
                    badge_kind=badge_kind,
                )
                if option.tooltip:
                    self._scene_combo.setItemData(index, option.tooltip, Qt.ToolTipRole)
                if option.disabled:
                    item_getter = getattr(self._scene_combo.model(), "item", None)
                    item = item_getter(index) if callable(item_getter) else None
                    if item is not None:
                        item.setEnabled(False)
                if option.value == target:
                    selected_index = index
            if selected_index >= 0:
                self._scene_combo.setCurrentIndex(selected_index)
        finally:
            self._scene_combo.blockSignals(blocked)

    def _populate_template_options(self, *, current_template_id: str = "") -> None:
        compatible_ids = list(self._scene.compatible_template_ids or [])
        if not compatible_ids and self._scene.template_id:
            compatible_ids = [self._scene.template_id]
        target = (
            str(current_template_id or "").strip()
            or str(self._scene.template_id or "").strip()
        )
        blocked = self._template_combo.blockSignals(True)
        try:
            self._template_combo.clear()
            selected_index = -1
            for option in template_selector_options(
                self._work_mode_id,
                template_ids=compatible_ids or None,
                include_source_prefix=False,
            ):
                badge_text, badge_kind = _source_badge(option.source_type)
                index = self._template_combo.add_badged_item(
                    option.label,
                    option.value,
                    badge_text=badge_text,
                    badge_kind=badge_kind,
                )
                if option.tooltip:
                    self._template_combo.setItemData(
                        index,
                        option.tooltip,
                        Qt.ToolTipRole,
                    )
                if option.disabled:
                    item_getter = getattr(self._template_combo.model(), "item", None)
                    item = item_getter(index) if callable(item_getter) else None
                    if item is not None:
                        item.setEnabled(False)
                if option.value == target:
                    selected_index = index
            if selected_index >= 0:
                self._template_combo.setCurrentIndex(selected_index)
        finally:
            self._template_combo.blockSignals(blocked)

    def _on_scene_changed(self, index: int) -> None:
        if self._binding_signal_blocked or index < 0:
            return
        scene_id = str(self._scene_combo.itemData(index) or "").strip()
        if not scene_id:
            return
        try:
            scene = load_scene_from_library(
                scene_id,
                mode_id=self._work_mode_id,
            )
        except Exception:
            self._populate_scene_options(current_scene_id=self._scene.scene_id)
            return
        self._scene = scene
        self._plan_label = strip_source_prefix(self._scene_combo.currentText())
        self._populate_template_options(current_template_id=scene.template_id)
        self._last_result_status = "idle"
        self._refresh_projection()
        self.binding_changed.emit(scene, self.current_template_id())

    def _on_template_changed(self, index: int) -> None:
        if self._binding_signal_blocked or index < 0:
            return
        template_id = str(self._template_combo.itemData(index) or "").strip()
        if not template_id:
            return
        self._template_label = strip_source_prefix(
            self._template_combo.currentText()
        )
        self._last_result_status = "idle"
        self._refresh_projection()
        self.binding_changed.emit(self._scene, template_id)

    def current_template_id(self) -> str:
        return str(self._template_combo.currentData() or "").strip()

    def source_title_text(self) -> str:
        return self._source_area.title_text()

    def source_hint_text(self) -> str:
        return self._source_area.hint_text()

    def binding_summary(self) -> str:
        return f"处理方案：{self._plan_label} · 模板：{self._template_label}"

    def set_material_batch_selection(
        self,
        selection: MaterialBatchSelection | None,
    ) -> None:
        previous_source = str(self._selection.source_path or "").strip()
        self._selection = (
            selection.clone()
            if isinstance(selection, MaterialBatchSelection)
            else MaterialBatchSelection()
        )
        current_source = str(self._selection.source_path or "").strip()
        if previous_source != current_source:
            self.reset_execution_feedback()
            return
        self._refresh_projection()

    def set_scene_context(self, scene: SceneWorkspace | None) -> None:
        self._scene = (
            scene
            if isinstance(scene, SceneWorkspace)
            else SceneWorkspace(scene_id="default")
        )
        scene_mode = str(getattr(self._scene, "mode_id", "") or "").strip()
        if scene_mode:
            self._work_mode_id = scene_mode
        self._binding_signal_blocked = True
        try:
            self._populate_scene_options(current_scene_id=self._scene.scene_id)
            self._populate_template_options(
                current_template_id=self._scene.template_id
            )
        finally:
            self._binding_signal_blocked = False
        self._refresh_projection()

    def set_work_mode(self, mode_id: str) -> None:
        mode = str(mode_id or "").strip() or "custom"
        if mode == self._work_mode_id and self._scene_combo.count():
            return
        self._work_mode_id = mode
        self._binding_signal_blocked = True
        try:
            self._populate_scene_options(current_scene_id=self._scene.scene_id)
            self._populate_template_options(
                current_template_id=self._scene.template_id
            )
        finally:
            self._binding_signal_blocked = False
        self._refresh_projection()

    def set_strategy_context(
        self,
        *,
        plan_label: str,
        template_label: str,
        template_id: str = "",
    ) -> None:
        self._plan_label = str(plan_label or "").strip() or "未绑定方案"
        self._template_label = str(template_label or "").strip() or "未绑定模板"
        target_id = str(template_id or "").strip()
        if target_id:
            index = self._template_combo.findData(target_id)
            if index >= 0:
                blocked = self._template_combo.blockSignals(True)
                self._template_combo.setCurrentIndex(index)
                self._template_combo.blockSignals(blocked)
        self._refresh_projection()

    def set_runtime_template_overrides(
        self,
        overrides: dict[str, object] | None,
    ) -> None:
        self._runtime_template_overrides = dict(overrides or {})

    def runtime_template_overrides(self) -> dict[str, object]:
        return dict(self._runtime_template_overrides)

    def set_source_document(self, path: str) -> None:
        cleaned = str(path or "").strip()
        if cleaned == self._source_document_path:
            return
        self._source_document_path = cleaned
        self.reset_execution_feedback()

    def _on_source_document_selected(self, path: str) -> None:
        self._source_document_path = str(path or "").strip()
        self._last_result_status = "idle"
        self._refresh_projection()
        self.source_document_selected.emit(self._source_document_path)

    def output_dir(self) -> str:
        return self._custom_output_dir

    def _on_output_mode_changed(self, is_custom: bool) -> None:
        self._output_browse_btn.setVisible(bool(is_custom))
        if not is_custom:
            self._custom_output_dir = ""
            self._output_browse_btn.setText("选择目录")
            self._output_browse_btn.setIcon(QIcon())
        self._last_result_status = "idle"
        self._refresh_projection()

    def _on_output_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self._set_output_dir(folder)

    def _set_output_dir(self, folder: str) -> None:
        self._custom_output_dir = str(folder or "").strip()
        display = Path(self._custom_output_dir).name or self._custom_output_dir
        self._output_browse_btn.setText(display or "选择目录")
        choose_directory = path_action_presentation(PathAction.CHOOSE_DIRECTORY)
        self._output_browse_btn.setIcon(
            get_icon(choose_directory.icon_name, 16, get_theme().icon_primary)
        )
        if not self._output_custom_radio.isChecked():
            self._output_custom_radio.setChecked(True)
        self._last_result_status = "idle"
        self._refresh_projection()

    def current_batch_execution_gate_decision(self) -> ExecutionGateDecision:
        return material_batch_readiness_gate_decision(
            self._scene,
            self._selection,
        )

    def can_start_execution(self) -> bool:
        return not self.execution_blocking_reasons()

    def execution_blocking_reasons(self) -> list[str]:
        selected_ids = self._selected_profile_ids()
        reasons: list[str] = []
        if not selected_ids:
            reasons.append("尚未选择批次资料")

        decision = self.current_batch_execution_gate_decision()
        reasons.extend(
            str(reason)
            for reason in decision.blocking_reasons
            if str(reason)
        )

        if (
            selected_ids
            and self._source_document_required()
            and not self._selected_source_document_exists()
        ):
            reasons.append("请选择本批次共用的 DOCX 源文档")

        if selected_ids:
            try:
                preflight = check_material_batch_preflight(
                    self._selection.archive,
                    profile_ids=selected_ids,
                    base_output_dir=self.output_dir(),
                    output_dir_template=self._selection.output_dir_template,
                )
            except Exception as exc:
                reasons.append(f"批次输出预检失败：{type(exc).__name__}")
            else:
                if preflight.issues:
                    reasons.append("批次输出命名存在冲突或无效设置")

        return list(dict.fromkeys(reasons))

    def failed_batch_profile_ids(self) -> list[str]:
        selected = set(self._selected_profile_ids())
        return [
            profile_id
            for profile_id in self._last_retry_profile_ids
            if profile_id in selected
        ]

    def last_batch_run_id(self) -> str:
        return self._last_batch_run_id

    def next_batch_attempt_number(self) -> int:
        return max(2, self._last_batch_attempt_number + 1)

    def reset_execution_feedback(self) -> None:
        self._execution_running = False
        self._execution_cancel_requested = False
        self._last_result_status = "idle"
        self._last_retry_profile_ids = []
        self._last_batch_run_id = ""
        self._last_batch_attempt_number = 1
        self._exec_bar.setValue(0)
        self._exec_bar.setVisible(False)
        self._retry_btn.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._exec_log.clear()
        self._log_toggle_btn.setVisible(False)
        self._set_log_expanded(False)
        self._refresh_projection()

    def set_execute_enabled(self, enabled: bool) -> None:
        self._actions_enabled = bool(enabled)
        self._refresh_actions()

    def set_execution_progress(self, state: ExecutionProgressState) -> None:
        self._execution_running = True
        self._last_result_status = "running"
        self._exec_bar.setVisible(True)
        self._exec_bar.setValue(max(0, min(100, int(state.percent or 0))))
        self._retry_btn.setVisible(False)
        self._cancel_btn.setVisible(True)
        self._cancel_btn.setEnabled(not self._execution_cancel_requested)
        self._execute_btn.setText("批量生成中...")
        self._execute_btn.setEnabled(False)
        stage = str(state.stage_text or "批量生成中")
        if self._execution_cancel_requested:
            self._set_status("正在取消，请稍候…", "info")
        else:
            self._set_status(f"{stage} {int(state.percent or 0)}%", "info")
        self._append_exec_log("info", f"执行阶段：{stage}")
        self.summary_changed.emit()

    def _request_cancel(self) -> None:
        if not self._execution_running or self._execution_cancel_requested:
            return
        self._execution_cancel_requested = True
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("正在取消...")
        self._set_status("正在取消，请稍候…", "info")
        self._append_exec_log("info", "已请求取消本次批量生成。")
        self.cancel_requested.emit()

    def set_execution_result(self, state: ExecutionResultState) -> None:
        self._execution_running = False
        self._execution_cancel_requested = False
        presentation = build_execution_result_presentation(state)
        self._last_result_status = presentation.status
        self._last_retry_profile_ids = list(presentation.retry_profile_ids)
        self._last_batch_run_id = presentation.batch_run_id
        self._last_batch_attempt_number = presentation.batch_attempt_number
        self._exec_bar.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.setText("取消生成")

        status_text = presentation.status_text
        if presentation.status == "partial_success" and presentation.summary:
            status_text = f"部分完成：{presentation.summary}"
        self._set_status(status_text, presentation.status_tone)
        for entry in presentation.log_entries:
            self._append_exec_log(entry.level, entry.message)
        self._log_toggle_btn.setVisible(bool(presentation.log_entries))
        self._set_log_expanded(
            bool(presentation.expand_log or presentation.retry_profile_ids)
        )
        self._refresh_actions()
        self.summary_changed.emit()

    def finish_execution(self) -> None:
        self._execution_running = False
        self._execution_cancel_requested = False
        self._cancel_btn.setVisible(False)
        if self._last_result_status == "running":
            self._last_result_status = "idle"
            self._refresh_projection()
            return
        self._refresh_actions()

    def navigation_snapshot(self) -> dict[str, str]:
        count = len(self._selected_profile_ids())
        if self._execution_running:
            badge_text, badge_variant = "执行中", "info"
        elif self._last_result_status in {"success", "partial_success"}:
            badge_text, badge_variant = "已完成", "success"
        elif self._last_result_status in {"failed", "cancelled"}:
            badge_text, badge_variant = "需处理", "warning"
        elif self.can_start_execution():
            badge_text, badge_variant = "可执行", "success"
        else:
            badge_text, badge_variant = "待补充", "neutral"
        source = self._selection_source_label()
        subtitle = f"{count} 份资料 · {source}" if count else "尚未准备批次资料"
        return {
            "subtitle": subtitle,
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def _refresh_projection(self) -> None:
        selected_ids = self._selected_profile_ids()
        count = len(selected_ids)
        profile_names = self._selected_profile_names()
        visible_names = profile_names[:3]
        profile_summary = "、".join(visible_names)
        if len(profile_names) > 3:
            profile_summary += f" 等 {len(profile_names)} 份"

        self._source_area.set_batch_state(
            count=count,
            source_label=self._selection_source_label(),
            profile_summary=profile_summary,
            source_document_required=self._source_document_required(),
            source_document_path=self._source_document_path,
        )

        self._refresh_output_preview()
        self._refresh_actions()
        if not self._execution_running and self._last_result_status == "idle":
            self._refresh_readiness_status()
        self.summary_changed.emit()

    def _refresh_output_preview(self) -> None:
        selected_ids = self._selected_profile_ids()
        if not selected_ids:
            self._output_preview.setText("选择批次资料后显示输出预览")
            self._output_preview.setToolTip("")
            return
        try:
            items = build_material_batch_items(
                self._selection.archive,
                profile_ids=selected_ids,
                base_output_dir=self.output_dir(),
                output_dir_template=self._selection.output_dir_template,
                base_context=self._selection.base_context,
            )
        except Exception as exc:
            self._output_preview.setText("输出预览不可用")
            self._output_preview.setToolTip(
                f"无法生成输出预览：{type(exc).__name__}"
            )
            return
        self._output_preview.setText(f"预计生成 {len(items)} 个独立目录")
        self._output_preview.setToolTip(
            "\n".join(str(item.output_dir) for item in items[:5])
        )

    def _refresh_readiness_status(self) -> None:
        blockers = self.execution_blocking_reasons()
        decision = self.current_batch_execution_gate_decision()
        if blockers:
            if blockers == ["尚未选择批次资料"]:
                self._set_status("请先准备批次资料", "hint")
            else:
                self._set_status("无法生成：请补齐批次输入", "error")
        elif decision.requires_confirmation:
            self._set_status("生成前需确认批次资料缺口", "warning")
        elif decision.warning_reasons:
            self._set_status("可生成；部分信息将使用默认值", "warning")
        else:
            self._set_status(
                f"可批量生成 {len(self._selected_profile_ids())} 份",
                "success",
            )
        self._exec_status_label.setToolTip(
            "\n".join(
                [
                    *blockers,
                    *decision.confirmation_reasons,
                    *decision.warning_reasons,
                ]
            )
        )

    def _refresh_actions(self) -> None:
        decision = self.current_batch_execution_gate_decision()
        count = len(self._selected_profile_ids())
        blockers = self.execution_blocking_reasons()
        executable = (
            self._actions_enabled
            and not self._execution_running
            and count > 0
            and not blockers
        )
        if self._execution_running:
            self._execute_btn.setText("批量生成中...")
        elif decision.requires_confirmation and count:
            self._execute_btn.setText(f"确认并生成 {count} 份")
        else:
            self._execute_btn.setText(
                f"批量生成 {count} 份" if count else "开始批量生成"
            )
        self._execute_btn.setEnabled(executable)
        self._execute_btn.setToolTip(
            "\n".join(
                blockers
                or list(decision.confirmation_reasons)
                or list(decision.warning_reasons)
            )
        )

        retry_ids = self.failed_batch_profile_ids()
        self._retry_btn.setVisible(bool(retry_ids) and not self._execution_running)
        self._retry_btn.setText(
            f"重试失败项 {len(retry_ids)} 份"
            if retry_ids
            else "重试失败项"
        )
        self._retry_btn.setEnabled(
            self._actions_enabled
            and not self._execution_running
            and bool(retry_ids)
        )
        self._cancel_btn.setVisible(self._execution_running)

    def _set_status(self, text: str, tone: str = "hint") -> None:
        self._exec_status_label.setText(str(text or "").strip())
        theme = get_theme()
        colors = {
            "success": theme.success,
            "warning": theme.warning,
            "error": theme.error,
            "info": theme.primary,
            "hint": theme.text_hint,
        }
        self._exec_status_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"color: {colors.get(tone, theme.text_hint)}; "
            "background: transparent;"
        )

    def _append_exec_log(self, level: str, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        theme = get_theme()
        colors = {
            "success": theme.success,
            "warning": theme.warning,
            "error": theme.error,
            "critical": theme.error,
            "info": theme.text_secondary,
        }
        color = colors.get(str(level or "").lower(), theme.text_secondary)
        self._exec_log.append(
            f'<span style="color: {color};">{_html.escape(text)}</span>'
        )
        self._log_toggle_btn.setVisible(True)

    def _toggle_log_visibility(self) -> None:
        self._set_log_expanded(not self._log_expanded)

    def _set_log_expanded(self, expanded: bool) -> None:
        self._log_expanded = bool(expanded)
        self._exec_log.setVisible(self._log_expanded)
        self._log_toggle_btn.setText(
            "收起执行日志" if self._log_expanded else "查看执行日志"
        )
        self._log_toggle_btn.setIcon(
            get_icon(
                "chevron-up" if self._log_expanded else "chevron-down",
                16,
                get_theme().text_primary,
            )
        )

    def _selected_profile_ids(self) -> list[str]:
        return [
            text
            for text in (
                str(profile_id or "").strip()
                for profile_id in self._selection.profile_ids
            )
            if text
        ]

    def _selected_profile_names(self) -> list[str]:
        selected = set(self._selected_profile_ids())
        names: list[str] = []
        for profile in self._selection.archive.profiles:
            profile_id = str(profile.profile_id or "").strip()
            if profile_id not in selected:
                continue
            names.append(
                str(
                    profile.profile_name
                    or profile.profile_id
                    or "未命名资料"
                ).strip()
            )
        return names

    def _selection_source_label(self) -> str:
        source_path = str(self._selection.source_path or "").strip()
        if source_path:
            return Path(source_path).name
        archive_name = str(self._selection.archive.archive_name or "").strip()
        if archive_name:
            return archive_name
        package_id = str(self._selection.package_id or "").strip()
        return package_id or "资料包"

    def _source_document_required(self) -> bool:
        return not (
            str(self._selection.source_kind or "").strip()
            == "official_document_table"
            and scene_uses_official_document_surface(
                self._scene,
                mode_id=self._work_mode_id,
            )
        )

    def _selected_source_document_exists(self) -> bool:
        return bool(
            self._source_document_path
            and Path(self._source_document_path).is_file()
            and Path(self._source_document_path).suffix.lower() == ".docx"
        )

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._layout.setSpacing(theme.template_detail_section_gap)
        self.setStyleSheet(build_button_stylesheet(theme))

        for label in (self._scene_text_label, self._template_text_label):
            label.setStyleSheet(
                f"font-size: {theme.font_size_md}px; "
                f"font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.text_secondary}; background: transparent;"
            )
        self._scene_icon_label.setPixmap(
            get_icon("mountain-snow", 16, theme.text_hint).pixmap(16, 16)
        )
        self._template_icon_label.setPixmap(
            get_icon("scroll-text", 16, theme.text_hint).pixmap(16, 16)
        )
        self._output_preview.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint}; "
            "background: transparent;"
        )
        self._output_browse_btn.setStyleSheet(
            f"QPushButton {{ font-size: {theme.font_size_md}px; "
            f"color: {theme.text_secondary}; border: 1px solid {theme.border}; "
            f"border-radius: {theme.radius_sm}px; padding: 6px 12px; "
            f"background: {theme.bg_card}; text-align: left; }}"
            f"QPushButton:hover {{ border-color: {theme.primary}; "
            f"color: {theme.primary}; }}"
        )

        for button in (self._retry_btn, self._cancel_btn):
            apply_size_class(button, "lg")
            apply_button_variant(button, "secondary")
        apply_size_class(self._execute_btn, "lg")
        apply_button_variant(self._execute_btn, "primary")
        self._execute_btn.setIcon(
            get_icon("play", 16, theme.text_on_primary)
        )
        self._retry_btn.setIcon(
            get_icon("refresh-ccw", 16, theme.text_primary)
        )
        self._cancel_btn.setIcon(
            get_icon("circle-x", 16, theme.text_primary)
        )
        apply_size_class(self._log_toggle_btn, "sm")
        apply_button_variant(self._log_toggle_btn, "ghost-primary")

        height = resolved_control_height(theme, "lg")
        self._exec_status_area.setMinimumHeight(height)
        self._exec_status_area.setMaximumHeight(height)
        self._exec_bar.setStyleSheet(
            f"""QProgressBar#wb_batch_exec_bar {{
                border: none; background: {theme.border_light};
                border-radius: 2px;
            }}
            QProgressBar#wb_batch_exec_bar::chunk {{
                background: {theme.primary}; border-radius: 2px;
            }}"""
        )
        self._exec_log.setStyleSheet(
            f"""QTextEdit#wb_batch_exec_log {{
                background: {theme.bg_hover};
                color: {theme.text_secondary};
                font-size: {theme.font_size_sm}px;
                border-radius: {theme.radius_sm}px;
                padding: 10px;
                border: 1px solid {theme.border_light};
            }}"""
        )
        if not self._execution_running and self._last_result_status == "idle":
            self._refresh_readiness_status()


__all__ = ["BatchGenerationDetail"]
