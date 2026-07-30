"""Package-driven ``成套生成`` Workbench detail surface."""

from __future__ import annotations

import copy
from pathlib import Path

from src.config.entity import EntityArchive
from src.config.material_import_draft import inspect_material_workbook
from src.config.material_batch import MaterialBatchSelection
from src.config.material_package_v6 import (
    MaterialPackageV6,
    load_material_package_any,
    material_package_v6_from_archive,
    synchronize_material_package_from_archive,
)
from src.config.material_scope import MaterialScopeResolver
from src.material_suite.plan import (
    MaterialSuiteRunPlan,
    compile_material_suite_plan,
    discover_material_suite_bundle,
)
from src.qt_api import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.engine.material_timeline import (
    default_timeline_plan,
    evenly_distributed_nodes,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.theme import bind_theme, get_theme

from .quick_execution_result_presenter import build_execution_result_presentation
from .state import ExecutionProgressState, ExecutionResultState


class MaterialSuiteGenerationDetail(QWidget):
    """Configure and preview a material-package-to-artifact-suite run."""

    execute_requested = Signal()
    retry_requested = Signal()
    cancel_requested = Signal()
    summary_changed = Signal()
    material_selection_changed = Signal(object)
    material_workspace_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("materialSuiteGenerationDetail")
        self._selection = MaterialBatchSelection()
        self._template_root = ""
        self._output_root = ""
        self._actions_enabled = True
        self._execution_running = False
        self._cancel_requested = False
        self._last_result_status = "idle"
        self._last_retry_profile_ids: list[str] = []
        self._last_plan: MaterialSuiteRunPlan | None = None
        self._record_selection_explicit = False
        self._syncing_record_list = False
        self._build_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self._refresh_projection()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 16, 28, 28)
        layout.setSpacing(16)

        intro = QLabel("按资料包记录成套生成 Word 文档与对应产品测试表")
        intro.setObjectName("materialSuiteIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        source_card = Card("1. 资料包基准", parent=self)
        source_card.set_header("1. 资料包基准", icon_name="package")
        source_card.set_description(
            "每条资料是一个项目记录；字段函数和全部时间流会在预检时统一解析并冻结。"
        )
        source_row = QHBoxLayout()
        self._package_path = QLineEdit(self)
        self._package_path.setObjectName("materialSuitePackagePath")
        self._package_path.setReadOnly(True)
        self._package_path.setPlaceholderText(
            "使用资料包工作台当前选择，或选择 JSON / Excel 资料包"
        )
        self._package_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._package_btn = QPushButton("选择资料包", self)
        self._package_btn.clicked.connect(self._choose_package)
        self._material_workspace_btn = QPushButton("编辑资料与时间流", self)
        self._material_workspace_btn.clicked.connect(
            self.material_workspace_requested.emit
        )
        self._activate_ready_btn = QPushButton("激活完整草稿", self)
        self._activate_ready_btn.clicked.connect(self._activate_ready_drafts)
        source_row.addWidget(self._package_path, 1)
        source_row.addWidget(self._package_btn)
        source_row.addWidget(self._material_workspace_btn)
        source_row.addWidget(self._activate_ready_btn)
        source_card.add_layout(source_row)
        self._package_summary = QLabel(self)
        self._package_summary.setWordWrap(True)
        source_card.add_widget(self._package_summary)
        self._record_list = QListWidget(self)
        self._record_list.setObjectName("materialSuiteRecordList")
        self._record_list.setMaximumHeight(150)
        self._record_list.itemChanged.connect(self._on_record_item_changed)
        source_card.add_widget(self._record_list)
        layout.addWidget(source_card)

        template_card = Card("2. 成套模板", parent=self)
        template_card.set_header("2. 成套模板", icon_name="layers")
        template_card.set_description(
            "Word文档目录作为通用件；“产品名_测试表”目录按资料中的产品名称成套映射。"
        )
        template_row = QHBoxLayout()
        self._template_path = QLineEdit(self)
        self._template_path.setObjectName("materialSuiteTemplatePath")
        self._template_path.setReadOnly(True)
        self._template_path.setPlaceholderText(
            "选择包含“Word文档”和“*_测试表”的模板目录"
        )
        self._template_btn = QPushButton("选择模板套件", self)
        self._template_btn.clicked.connect(self._choose_template_root)
        template_row.addWidget(self._template_path, 1)
        template_row.addWidget(self._template_btn)
        template_card.add_layout(template_row)
        layout.addWidget(template_card)

        output_card = Card("3. 输出与预检", parent=self)
        output_card.set_header("3. 输出与预检", icon_name="folder-output")
        output_row = QHBoxLayout()
        self._output_path = QLineEdit(self)
        self._output_path.setObjectName("materialSuiteOutputPath")
        self._output_path.setReadOnly(True)
        self._output_path.setPlaceholderText("选择成套输出根目录")
        self._output_btn = QPushButton("选择输出目录", self)
        self._output_btn.clicked.connect(self._choose_output_root)
        output_row.addWidget(self._output_path, 1)
        output_row.addWidget(self._output_btn)
        output_card.add_layout(output_row)
        self._matrix_preview = QTextEdit(self)
        self._matrix_preview.setObjectName("materialSuiteMatrixPreview")
        self._matrix_preview.setReadOnly(True)
        self._matrix_preview.setMaximumHeight(180)
        self._matrix_preview.setPlaceholderText(
            "输入完整后显示“资料记录 × 成套产物”预检矩阵"
        )
        output_card.add_widget(self._matrix_preview)
        layout.addWidget(output_card)

        execution_card = Card("4. 执行", parent=self)
        execution_card.set_header("4. 执行", icon_name="play")
        self._status_label = QLabel("请先补齐资料包、模板套件和输出目录", self)
        self._status_label.setWordWrap(True)
        execution_card.add_widget(self._status_label)
        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setVisible(False)
        execution_card.add_widget(self._progress)
        action_row = QHBoxLayout()
        self._execute_btn = QPushButton("开始成套生成", self)
        self._execute_btn.setObjectName("materialSuiteExecuteButton")
        self._execute_btn.clicked.connect(self.execute_requested.emit)
        self._retry_btn = QPushButton("仅重试失败记录", self)
        self._retry_btn.clicked.connect(self.retry_requested.emit)
        self._retry_btn.setVisible(False)
        self._cancel_btn = QPushButton("取消生成", self)
        self._cancel_btn.clicked.connect(self._request_cancel)
        self._cancel_btn.setVisible(False)
        action_row.addWidget(self._execute_btn)
        action_row.addWidget(self._retry_btn)
        action_row.addWidget(self._cancel_btn)
        action_row.addStretch(1)
        execution_card.add_layout(action_row)
        self._log = QTextEdit(self)
        self._log.setObjectName("materialSuiteExecutionLog")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(130)
        self._log.setVisible(False)
        execution_card.add_widget(self._log)
        layout.addWidget(execution_card)
        layout.addStretch(1)

    def set_material_batch_selection(
        self,
        selection: MaterialBatchSelection | None,
    ) -> None:
        incoming_has_v6 = isinstance(
            getattr(selection, "material_package", None),
            MaterialPackageV6,
        )
        self._selection = (
            selection.clone()
            if isinstance(selection, MaterialBatchSelection)
            else MaterialBatchSelection()
        )
        archive = self._selection.archive
        package = getattr(self._selection, "material_package", None)
        if isinstance(package, MaterialPackageV6) and archive.profiles:
            self._selection.material_package = (
                synchronize_material_package_from_archive(package, archive)
            )
        elif archive.profiles:
            self._selection.material_package = material_package_v6_from_archive(
                archive,
                source_path=self._selection.source_path or archive.source_path,
            )
        self._record_selection_explicit = incoming_has_v6
        source_path = str(self._selection.source_path or archive.source_path or "")
        if source_path and not archive.source_path:
            archive.source_path = source_path
        self._package_path.setText(source_path)
        self._set_default_paths(source_path)
        self._refresh_record_list()
        self._refresh_projection()

    def _set_default_paths(self, source_path: str) -> None:
        if not source_path:
            return
        parent = Path(source_path).parent
        template_candidate = parent / "模板文件"
        if not self._template_root and template_candidate.is_dir():
            self._template_root = str(template_candidate)
            self._template_path.setText(self._template_root)
        if not self._output_root:
            self._output_root = str(parent / "成套生成输出")
            self._output_path.setText(self._output_root)

    def _choose_package(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择资料包",
            self._package_path.text(),
            "资料包 (*.json *.xlsx *.xlsm *.csv);;全部文件 (*)",
        )
        if not path:
            return
        try:
            package = _load_material_package_v6_source(path)
        except Exception as exc:  # noqa: BLE001 - user-selected package boundary
            self._status_label.setText(f"资料包读取失败：{type(exc).__name__}: {exc}")
            return
        archive = package.to_entity_archive()
        archive.source_path = path
        active_ids = [
            item.record_id
            for item in package.records
            if item.lifecycle_state == "active"
        ]
        selection = MaterialBatchSelection(
            package_id=archive.package_id or archive.archive_id,
            archive=archive,
            profile_ids=active_ids,
            source_kind=Path(path).suffix.lower().lstrip("."),
            source_path=path,
            item_metadata={
                item.record_id: {
                    "lifecycle_state": item.lifecycle_state,
                    "group_id": item.group_id,
                    "source_locator": copy.deepcopy(item.source_locator),
                }
                for item in package.records
            },
            material_package=package,
        )
        self.set_material_batch_selection(selection)
        self._record_selection_explicit = True
        self._refresh_record_list()
        self.material_selection_changed.emit(selection.clone())

    def _choose_template_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择成套模板目录",
            self._template_root,
        )
        if path:
            self.set_template_root(path)

    def _choose_output_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择成套输出目录",
            self._output_root,
        )
        if path:
            self.set_output_root(path)

    def set_template_root(self, path: str) -> None:
        self._template_root = str(path or "").strip()
        self._template_path.setText(self._template_root)
        self._refresh_projection()

    def set_output_root(self, path: str) -> None:
        self._output_root = str(path or "").strip()
        self._output_path.setText(self._output_root)
        self._refresh_projection()

    def current_run_plan(
        self,
        *,
        retry_only: bool = False,
    ) -> MaterialSuiteRunPlan:
        profile_ids = (
            tuple(self._last_retry_profile_ids)
            if retry_only
            else tuple(self._selection.profile_ids)
            if self._selection.profile_ids or self._record_selection_explicit
            else None
        )
        bundle = discover_material_suite_bundle(self._template_root)
        plan = compile_material_suite_plan(
            self._selection.archive,
            bundle,
            output_root=self._output_root,
            profile_ids=profile_ids,
            base_selection=self._selection,
        )
        self._last_plan = plan
        return plan

    def execution_blocking_reasons(self) -> list[str]:
        reasons: list[str] = []
        if not self._selection.archive.profiles:
            reasons.append("尚未选择包含记录的资料包")
        if not self._template_root:
            reasons.append("尚未选择成套模板目录")
        if not self._output_root:
            reasons.append("尚未选择输出目录")
        if not reasons:
            plan = self.current_run_plan()
            reasons.extend(plan.issues)
            reasons.extend(
                f"{record.profile_name}：{'；'.join(record.issues)}"
                for record in plan.records
                if record.issues
            )
        return list(dict.fromkeys(reasons))

    def can_start_execution(self) -> bool:
        return not self.execution_blocking_reasons()

    def reset_execution_feedback(self) -> None:
        self._execution_running = False
        self._cancel_requested = False
        self._last_result_status = "idle"
        self._last_retry_profile_ids = []
        self._progress.setVisible(False)
        self._retry_btn.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._log.clear()
        self._log.setVisible(False)
        self._refresh_projection()

    def set_execute_enabled(self, enabled: bool) -> None:
        self._actions_enabled = bool(enabled)
        self._refresh_actions()

    def set_execution_progress(self, state: ExecutionProgressState) -> None:
        self._execution_running = True
        self._last_result_status = "running"
        self._progress.setVisible(True)
        self._progress.setValue(max(0, min(100, int(state.percent or 0))))
        self._cancel_btn.setVisible(True)
        self._cancel_btn.setEnabled(not self._cancel_requested)
        self._retry_btn.setVisible(False)
        self._status_label.setText(
            f"{state.stage_text or '成套生成中'} {int(state.percent or 0)}%"
        )
        self._append_log(f"执行阶段：{state.stage_text}")
        self._refresh_actions()
        self.summary_changed.emit()

    def _request_cancel(self) -> None:
        if not self._execution_running or self._cancel_requested:
            return
        self._cancel_requested = True
        self._cancel_btn.setEnabled(False)
        self._status_label.setText("正在取消；当前记录的暂存结果将被清理…")
        self.cancel_requested.emit()

    def set_execution_result(self, state: ExecutionResultState) -> None:
        self._execution_running = False
        self._cancel_requested = False
        presentation = build_execution_result_presentation(state)
        self._last_result_status = presentation.status
        self._last_retry_profile_ids = list(presentation.retry_profile_ids)
        self._progress.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._retry_btn.setVisible(bool(self._last_retry_profile_ids))
        self._status_label.setText(presentation.summary or presentation.status_text)
        self._log.clear()
        for entry in presentation.log_entries:
            self._append_log(entry.message)
        self._log.setVisible(bool(presentation.log_entries))
        self._refresh_actions()
        self.summary_changed.emit()

    def finish_execution(self) -> None:
        self._execution_running = False
        self._cancel_requested = False
        self._cancel_btn.setVisible(False)
        self._refresh_actions()

    def navigation_snapshot(self) -> dict[str, str]:
        count = _selected_active_count(
            self._selection,
            explicit=self._record_selection_explicit,
        )
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
        return {
            "subtitle": f"{count} 条资料 · Word + 测试表"
            if count
            else "尚未选择资料包",
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def _refresh_projection(self) -> None:
        archive = self._selection.archive
        selected_count = _selected_active_count(
            self._selection,
            explicit=self._record_selection_explicit,
        )
        package = getattr(self._selection, "material_package", None)
        candidate_count = (
            len(package.records)
            if isinstance(package, MaterialPackageV6)
            else len(archive.profiles)
        )
        draft_count = (
            sum(item.lifecycle_state == "draft" for item in package.records)
            if isinstance(package, MaterialPackageV6)
            else 0
        )
        self._package_summary.setText(
            (
                f"{archive.archive_name or archive.archive_id or '当前资料包'}"
                f" · {candidate_count} 个候选槽位"
                f" · {selected_count} 条活动记录"
                + (f" · {draft_count} 条草稿" if draft_count else "")
                + f" · {sum(len(item.timeline_plans) for item in archive.profiles)} 段时间流"
            )
            if archive.profiles
            else "尚未准备资料包"
        )
        blockers: list[str]
        if archive.profiles and self._template_root and self._output_root:
            try:
                plan = self.current_run_plan()
            except Exception as exc:  # noqa: BLE001 - preview must stay responsive
                self._matrix_preview.setPlainText(
                    f"预检失败：{type(exc).__name__}: {exc}"
                )
                blockers = ["成套映射预检失败"]
            else:
                lines = [
                    (
                        f"候选 {plan.inspection.candidate_count} · "
                        f"活动 {plan.inspection.active_count} · "
                        f"草稿 {plan.inspection.draft_count} · "
                        f"本次执行 {plan.inspection.executable_count}"
                    ),
                    "",
                    *[
                        (
                            f"{record.profile_name} [{record.route_key or '通用'}]"
                            f" → {len(record.artifacts)} 个文件"
                            + (
                                f"\n  阻断：{'；'.join(record.issues)}"
                                if record.issues
                                else ""
                            )
                        )
                        for record in plan.records
                    ],
                ]
                if plan.issues:
                    lines.insert(0, "全局阻断：" + "；".join(plan.issues))
                self._matrix_preview.setPlainText("\n".join(lines))
                blockers = [
                    *plan.issues,
                    *[issue for record in plan.records for issue in record.issues],
                ]
        else:
            self._matrix_preview.clear()
            blockers = []
            if not archive.profiles:
                blockers.append("请选择资料包")
            if not self._template_root:
                blockers.append("请选择模板套件")
            if not self._output_root:
                blockers.append("请选择输出目录")
        if not self._execution_running and self._last_result_status == "idle":
            self._status_label.setText(
                "预检通过，可以开始成套生成"
                if not blockers
                else "无法执行：" + "；".join(blockers[:3])
            )
        self._refresh_actions(blockers=blockers)
        self.summary_changed.emit()

    def _refresh_actions(self, *, blockers: list[str] | None = None) -> None:
        if blockers is None and not self._execution_running:
            blockers = self.execution_blocking_reasons()
        count = _selected_active_count(
            self._selection,
            explicit=self._record_selection_explicit,
        )
        self._execute_btn.setText(
            "成套生成中..."
            if self._execution_running
            else f"开始成套生成 {count} 套"
            if count
            else "开始成套生成"
        )
        self._execute_btn.setEnabled(
            self._actions_enabled and not self._execution_running and not blockers
        )
        self._package_btn.setEnabled(
            self._actions_enabled and not self._execution_running
        )
        self._template_btn.setEnabled(
            self._actions_enabled and not self._execution_running
        )
        self._output_btn.setEnabled(
            self._actions_enabled and not self._execution_running
        )
        self._record_list.setEnabled(
            self._actions_enabled and not self._execution_running
        )
        self._material_workspace_btn.setEnabled(
            self._actions_enabled and not self._execution_running
        )
        self._activate_ready_btn.setEnabled(
            self._actions_enabled
            and not self._execution_running
            and self._has_draft_records()
        )
        self._retry_btn.setEnabled(
            self._actions_enabled
            and not self._execution_running
            and bool(self._last_retry_profile_ids)
        )

    def _append_log(self, text: str) -> None:
        if str(text or "").strip():
            self._log.append(str(text))

    def _refresh_record_list(self) -> None:
        if not hasattr(self, "_record_list"):
            return
        package = getattr(self._selection, "material_package", None)
        self._syncing_record_list = True
        try:
            self._record_list.clear()
            if not isinstance(package, MaterialPackageV6):
                self._record_list.setVisible(False)
                return
            self._record_list.setVisible(bool(package.records))
            selected = set(self._selection.profile_ids)
            for record in package.records:
                group = package.get_group(record.group_id) if record.group_id else None
                group_name = group.group_name if group is not None else "未分组"
                state_label = {
                    "active": "活动",
                    "draft": "草稿",
                    "disabled": "停用",
                    "archived": "归档",
                }.get(record.lifecycle_state, record.lifecycle_state)
                item = QListWidgetItem(
                    f"[{state_label}] {group_name} · {record.record_name}"
                )
                item.setData(Qt.UserRole, record.record_id)
                if record.lifecycle_state == "active":
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    checked = (
                        record.record_id in selected
                        if self._record_selection_explicit
                        else True
                    )
                    item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                self._record_list.addItem(item)
        finally:
            self._syncing_record_list = False

    def _on_record_item_changed(self, _item) -> None:
        if self._syncing_record_list:
            return
        package = getattr(self._selection, "material_package", None)
        if not isinstance(package, MaterialPackageV6):
            return
        selected: list[str] = []
        for index in range(self._record_list.count()):
            item = self._record_list.item(index)
            if item is None or item.checkState() != Qt.Checked:
                continue
            record_id = str(item.data(Qt.UserRole) or "").strip()
            record = package.get_record(record_id)
            if record is not None and record.lifecycle_state == "active":
                selected.append(record_id)
        self._record_selection_explicit = True
        self._selection.profile_ids = selected
        self._last_retry_profile_ids = []
        self.material_selection_changed.emit(self._selection.clone())
        self._refresh_projection()

    def _has_draft_records(self) -> bool:
        package = getattr(self._selection, "material_package", None)
        return isinstance(package, MaterialPackageV6) and any(
            item.lifecycle_state == "draft" for item in package.records
        )

    def _activate_ready_drafts(self) -> None:
        package = getattr(self._selection, "material_package", None)
        if not isinstance(package, MaterialPackageV6):
            return
        resolver = MaterialScopeResolver(package)
        activated: list[str] = []
        for record in package.records:
            if record.lifecycle_state != "draft":
                continue
            resolved = resolver.resolve_record(record.record_id)
            values = resolved.values
            has_name = any(
                str(values.get(key, "") or "").strip()
                for key in ("项目名称", "project_name", "entity_name")
            )
            has_code = any(
                str(values.get(key, "") or "").strip()
                for key in ("项目编号", "project_code", "record_id")
            )
            if has_name and has_code and not resolved.blocking_issues:
                record.lifecycle_state = "active"
                activated.append(record.record_id)
        if not activated:
            self._status_label.setText(
                "没有可激活的草稿；草稿需同时具备项目名称和项目编号"
            )
            return
        self._record_selection_explicit = True
        self._selection.profile_ids = list(
            dict.fromkeys((*self._selection.profile_ids, *activated))
        )
        for record_id in activated:
            self._selection.item_metadata.setdefault(record_id, {})[
                "lifecycle_state"
            ] = "active"
        self._refresh_record_list()
        self.material_selection_changed.emit(self._selection.clone())
        self._refresh_projection()
        self._status_label.setText(f"已激活 {len(activated)} 条完整草稿")

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#materialSuiteGenerationDetail {{
                background: {theme.bg_window};
            }}
            QLabel {{
                color: {theme.text_primary};
                background: transparent;
            }}
            QLabel#materialSuiteIntro {{
                font-size: {theme.font_size_xl}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLineEdit, QTextEdit {{
                background: {theme.bg_input};
                color: {theme.text_primary};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_sm}px;
                padding: 7px 9px;
            }}
            QProgressBar {{
                border: 1px solid {theme.border};
                border-radius: {theme.radius_sm}px;
                background: {theme.progress_track};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {theme.progress_fill};
                border-radius: {theme.radius_sm}px;
            }}
            """
            + build_button_stylesheet(theme)
        )
        apply_button_variant(self._execute_btn, "primary")
        apply_button_variant(self._retry_btn, "secondary")
        apply_button_variant(self._cancel_btn, "danger")
        apply_button_variant(self._package_btn, "secondary")
        apply_button_variant(self._material_workspace_btn, "secondary")
        apply_button_variant(self._activate_ready_btn, "secondary")
        apply_button_variant(self._template_btn, "secondary")
        apply_button_variant(self._output_btn, "secondary")


def _load_material_package(path: str) -> EntityArchive:
    """Compatibility projection for callers that still consume EntityArchive."""

    return _load_material_package_v6_source(path).to_entity_archive()


def _load_material_package_v6_source(path: str) -> MaterialPackageV6:
    source = Path(path)
    if source.suffix.lower() == ".json":
        return load_material_package_any(source)
    if source.suffix.lower() in {".xlsx", ".xlsm"}:
        return inspect_material_workbook(source).materialize()
    from src.ui.panels.assets.batch_import import _load_batch_profiles_from_path

    profiles = _load_batch_profiles_from_path(source)
    _normalize_legacy_suite_profiles(profiles)
    return material_package_v6_from_archive(
        EntityArchive(
            archive_id=source.stem,
            archive_name=source.stem,
            profiles=copy.deepcopy(profiles),
            source_path=str(source),
        ),
        source_path=source,
    )


def _selected_active_count(
    selection: MaterialBatchSelection,
    *,
    explicit: bool,
) -> int:
    package = getattr(selection, "material_package", None)
    selected = set(selection.profile_ids)
    if isinstance(package, MaterialPackageV6):
        if explicit:
            return sum(
                item.record_id in selected
                and item.lifecycle_state == "active"
                for item in package.records
            )
        return sum(item.lifecycle_state == "active" for item in package.records)
    return len(selection.profile_ids) or len(selection.archive.profiles)


_LEGACY_TIMELINE_OUTPUTS = (
    "节点_设计策划",
    "节点_编制计划书",
    "节点_设计输入",
    "节点_性能评审",
    "节点_设计输出",
    "节点_系统评审",
    "节点_设计验证",
    "节点_试产可行性",
    "节点_试产总结",
    "节点_设计确认",
    "节点_设计正稿",
)


def _normalize_legacy_suite_profiles(profiles) -> None:
    """Migrate the VBA workbook row contract into explicit package records."""

    used_ids: set[str] = set()
    for index, profile in enumerate(profiles, start=1):
        profile_id = str(profile.profile_id or "").strip()
        if not profile_id or profile_id in used_ids:
            profile_id = f"record-{index:04d}"
        profile.profile_id = profile_id
        used_ids.add(profile_id)
        project_name = str(
            profile.fields.get("项目名称") or profile.fields.get("project_name") or ""
        ).strip()
        if project_name and (
            not str(profile.profile_name or "").strip()
            or str(profile.profile_name).startswith("第 ")
        ):
            profile.profile_name = project_name
        if profile.timeline_plans:
            continue
        start_key = _first_existing_field(
            profile.fields,
            ("项目开始日期", "project_start_date", "start_date"),
        )
        end_key = _first_existing_field(
            profile.fields,
            ("项目结束日期", "project_end_date", "end_date"),
        )
        if not start_key or not end_key:
            continue
        plan = default_timeline_plan()
        plan["start_field"] = start_key
        plan["end_field"] = end_key
        plan["calendar"] = {
            **dict(plan.get("calendar", {})),
            "basis": "calendar_day",
            "weekend_adjust": "forward",
        }
        nodes = evenly_distributed_nodes(len(_LEGACY_TIMELINE_OUTPUTS))
        for node, output_key in zip(nodes, _LEGACY_TIMELINE_OUTPUTS, strict=True):
            node["outputs"] = [{"field": output_key, "format": "yyyy-MM-dd"}]
        plan["nodes"] = nodes
        profile.timeline_plans = {"legacy_iso_timeline": plan}


def _first_existing_field(fields, candidates) -> str:
    for key in candidates:
        if str(fields.get(key, "") or "").strip():
            return key
    return ""


__all__ = ["MaterialSuiteGenerationDetail"]
