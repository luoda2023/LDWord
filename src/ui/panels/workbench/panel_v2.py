from __future__ import annotations

# ruff: noqa: I001

import copy
import json
import logging
from importlib import import_module
from typing import TYPE_CHECKING

from src.config.library import (
    get_scene_entry,
    get_template_entry,
    load_template_from_library,
)
from src.config.object_preflight_evidence import (
    ObjectPreflightEvidence,
    build_object_preflight_evidence,
    object_preflight_evidence_is_current,
)
from src.config.scene import SceneWorkspace
from src.config.scene_presets import (
    CAPABILITY_FEATURE_CARD_DEFINITIONS,
    CAPABILITY_FEATURE_CARD_ORDER,
)
from src.config.template import TemplateConfig
from src.qt_api import (
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui import DetailPaneController, MasterDetailShell, Toast
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.config_selector_models import scoped_selector_projections
from src.ui.adapters.field_display_names import (
    field_display_context,
    navigation_issue_hint,
)
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from src.ui.adapters.workbench_product_issue_navigation import (
    WorkbenchIssueNavigationProjection,
    workbench_issue_navigation_for_target,
)
from src.ui.adapters.workbench_strategy_adapter import WorkbenchStrategyAdapter
from src.ui.base_panel import BasePanel
from src.ui.bridge import navigation_intent_value
from src.ui.panel_specs import PANEL_SPECS
from src.ui.workspace_preferences import ModeWorkspacePreferences
from src.domain.materials import MaterialRunSelection

from .document_execution_coordinator import (
    DocumentExecutionAdapters,
    DocumentExecutionCoordinator,
)
from .document_execution_state import (
    DocumentExecutionSnapshot,
    DocumentExecutionState,
    DocumentExecutionTopology,
    OutputPolicy,
    SceneBinding,
    SourceRequirement,
    TemplateBinding,
    inspect_document_execution_readiness,
    resolve_document_execution_topology,
)
from .document_path_controller import WorkbenchDocumentPathController
from .execution_binding_card import ExecutionBindingCard
from .execution_controller import WorkbenchExecutionController
from .execution_controller import FileBatchWorkbenchController  # noqa: I001
from .feature_detail_panes import (
    CitationDetailPane,
    TableChartDetailPane,
)
from .navigation_controller import WorkbenchNavigationController
from .output_location_card import OutputLocationCard
from .quick_execution_detail import QuickExecutionDetail
from .material_state import choose_material_package
from .release_policy import (
    MATERIAL_SUITE_DELIVERY_CARD_ID,
    MATERIAL_SUITE_DELIVERY_RELEASED,
    is_workbench_card_released,
)
from .styles import apply_workbench_v2_shell_theme
from .workbench_execution_footer import WorkbenchExecutionFooter
from .workbench_execution_lifecycle_mixin import WorkbenchExecutionLifecycleMixin

if TYPE_CHECKING:
    from .document_scope_controller import WorkbenchDocumentScopeController
    from .execution_session_controller import WorkbenchExecutionSessionController

logger = logging.getLogger(__name__)


class _LazyExecutionSessionController:
    """Defer production-runtime imports until an execution is requested."""

    def __init__(self, *, resolve_document_path, worker_parent=None) -> None:
        self._resolve_document_path = resolve_document_path
        self._worker_parent = worker_parent
        self._delegate = None
        self._pending_worker = None

    def _ensure_delegate(self):
        if self._delegate is None:
            from .execution_session_controller import (
                WorkbenchExecutionSessionController as Controller,
            )

            self._delegate = Controller(
                resolve_document_path=self._resolve_document_path,
                worker_parent=self._worker_parent,
            )
            if self._pending_worker is not None:
                self._delegate.set_active_worker(self._pending_worker)
        return self._delegate

    @property
    def active_worker(self):
        if self._delegate is not None:
            return self._delegate.active_worker
        return self._pending_worker

    def set_active_worker(self, worker) -> None:
        self._pending_worker = worker
        if self._delegate is not None:
            self._delegate.set_active_worker(worker)

    def clear_active_worker(self) -> None:
        self._pending_worker = None
        if self._delegate is not None:
            self._delegate.clear_active_worker()

    def shutdown_active_execution(self, timeout_ms: int | None = 1000) -> bool:
        if self._delegate is None and self._pending_worker is None:
            return True
        return self._ensure_delegate().shutdown_active_execution(timeout_ms=timeout_ms)

    def __getattr__(self, name: str):
        return getattr(self._ensure_delegate(), name)


class _LazyDocumentScopeController:
    """Avoid importing document analysis before a compatible file is selected."""

    def __init__(
        self,
        *,
        parent,
        source_path,
        mode_id,
        scene,
        status_detail,
    ) -> None:
        self._controller_args = {
            "parent": parent,
            "source_path": source_path,
            "mode_id": mode_id,
            "scene": scene,
            "status_detail": status_detail,
        }
        self._source_path = source_path
        self._mode_id = mode_id
        self._status_detail = status_detail
        self._delegate = None

    def _ensure_delegate(self):
        if self._delegate is None:
            from .document_scope_controller import (
                WorkbenchDocumentScopeController as Controller,
            )

            self._delegate = Controller(**self._controller_args)
        return self._delegate

    def _is_applicable(self, source_path: str) -> bool:
        return (
            self._mode_id() not in {"official", "exam"}
            and str(source_path or "").strip().lower().endswith(".docx")
        )

    @property
    def evidence(self):
        return self._delegate.evidence if self._delegate is not None else None

    @property
    def decisions(self):
        return self._delegate.decisions if self._delegate is not None else ()

    def clear(self) -> None:
        if self._delegate is not None:
            self._delegate.clear()
        else:
            self._status_detail.set_document_scope_status("idle")

    def reset_decisions(self) -> None:
        if self._delegate is not None:
            self._delegate.reset_decisions()

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        if self._delegate is None:
            return True
        return self._delegate.shutdown(timeout_ms=timeout_ms)

    def start_scan(self, source_path: str, *, force: bool = False) -> None:
        if not self._is_applicable(source_path):
            self.clear()
            return
        self._ensure_delegate().start_scan(source_path, force=force)

    def recheck(self) -> None:
        source_path = self._source_path() or ""
        if not self._is_applicable(source_path):
            self.clear()
            return
        self._ensure_delegate().recheck()

    def review(self) -> bool:
        source_path = self._source_path() or ""
        if not self._is_applicable(source_path):
            return True
        return self._ensure_delegate().review()

    def ensure_confirmed(self) -> bool:
        source_path = self._source_path() or ""
        if not self._is_applicable(source_path):
            return True
        return self._ensure_delegate().ensure_confirmed()

    def __getattr__(self, name: str):
        return getattr(self._ensure_delegate(), name)


# Preserve the panel's controller contract while changing its construction time.
WorkbenchExecutionSessionController = _LazyExecutionSessionController
WorkbenchDocumentScopeController = _LazyDocumentScopeController


class _DeferredDetailPlaceholder(QWidget):
    """Small in-place host used while a non-primary detail is constructed."""

    retry_requested = Signal()
    material_workspace_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addStretch()
        self._label = QLabel("正在打开…", self)
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)
        self._retry_button = QPushButton("重试", self)
        self._retry_button.setFixedWidth(104)
        self._retry_button.setVisible(False)
        self._retry_button.clicked.connect(self.retry_requested.emit)
        layout.addWidget(self._retry_button, 0, Qt.AlignHCenter)
        layout.addStretch()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_loading(self) -> None:
        self._label.setText("正在打开…")
        self._retry_button.setVisible(False)

    def set_failed(self) -> None:
        self._label.setText("打开失败")
        self._retry_button.setVisible(True)

    def navigation_snapshot(self) -> dict[str, str]:
        return {
            "subtitle": "",
            "badge_text": "待补充",
            "badge_variant": "neutral",
        }

    def set_execute_enabled(self, _enabled: bool) -> None:
        return

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._label.setStyleSheet(
            f"color: {theme.text_hint}; font-size: {theme.font_size_lg}px;"
        )


class _SuiteDetailLoader:
    """Own the deferred suite-detail lifecycle outside WorkbenchPanel."""

    def __init__(self, panel) -> None:
        self._panel = panel
        self.timer = QTimer(panel)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.finish)

    def schedule(self) -> None:
        panel = self._panel
        if not isinstance(
            panel._suite_generation_detail,
            _DeferredDetailPlaceholder,
        ):
            return
        if panel._suite_detail_loading:
            return
        panel._suite_generation_detail.set_loading()
        panel._suite_detail_loading = True
        self.timer.start(16)

    def finish(self) -> None:
        panel = self._panel
        if not panel._suite_detail_loading:
            return
        if not isinstance(
            panel._suite_generation_detail,
            _DeferredDetailPlaceholder,
        ):
            panel._suite_detail_loading = False
            return
        placeholder = panel._suite_generation_detail
        try:
            detail_module = import_module(
                "src.ui.panels.workbench.material_suite_generation_detail"
            )
            detail = detail_module.MaterialSuiteGenerationDetail(panel)
            controller_module = import_module(
                "src.ui.panels.workbench.material_suite_workbench_controller"
            )
            flow = controller_module.MaterialSuiteWorkbenchController(
                detail,
                panel._execution,
                start_worker=panel._start_worker_from_build,
                active_worker=lambda: panel._execution_worker,
                cancel_execution=panel._cancel_execution,
                refresh_navigation=panel._refresh_fixed_cards,
                publish_material_selection=(
                    panel.bridge.set_current_material_run_selection
                ),
                open_material_workspace=lambda: panel._emit_panel_navigation(
                    "assets"
                ),
                current_mode_id=panel._current_work_mode_id,
                current_scene_id=panel.bridge.current_scene_id,
                current_document_type_id=(
                    panel.bridge.current_official_document_type_id
                ),
                worker_parent=panel,
            )
            flow.apply_material_selection(
                panel.bridge.current_material_run_selection(),
                preview=panel.bridge.current_material_preview_snapshot(),
                issues=panel.bridge.current_material_issues(),
            )
            panel._details.replace_detail(
                MATERIAL_SUITE_DELIVERY_CARD_ID,
                detail,
            )
            panel._suite_generation_detail = detail
            panel._suite_generation_flow = flow
            panel._navigation.set_suite_generation_detail(detail)
            panel._execution.set_suite_generation_detail(detail)
            panel._current_detail = panel._details.current_detail
            panel._refresh_fixed_cards()
        except Exception:
            logger.exception("Failed to load material suite detail")
            placeholder.set_failed()
        finally:
            panel._suite_detail_loading = False


class _RecentRunPanelModuleProxy:
    def _open_artifact_file(self, path: str, *, fragment: str = "") -> bool:
        from . import recent_run_panel

        return recent_run_panel._open_artifact_file(path, fragment=fragment)


recent_run_panel_module = _RecentRunPanelModuleProxy()


class DocumentExecutionDetail(QWidget):
    """One document surface that infers its executor from discovered inputs."""

    document_selected = Signal(str)
    mode_changed = Signal(str)
    execute_requested = Signal()
    retry_requested = Signal()
    cancel_requested = Signal()
    object_preflight_cancel_requested = Signal()
    material_repair_requested = Signal(str, str)
    summary_changed = Signal()
    MODES = ("single", "files", "records", "mapping_required")

    def __init__(
        self,
        single_detail: QWidget,
        file_batch_detail: QWidget,
        record_batch_detail: QWidget,
        source_area,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("wb_document_execution_detail")
        self._details = {
            "single": single_detail,
            "files": file_batch_detail,
            "records": record_batch_detail,
        }
        self._record_ids: tuple[str, ...] = ()
        self._material_selection = None
        self._material_preview = None
        self._source_requirement: SourceRequirement = "required"
        self._execution_state = DocumentExecutionState()
        self._active_mode = "single"
        self._syncing_sources = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)

        self._source_area = source_area
        self._source_area.setParent(self)
        layout.addWidget(self._source_area)
        if hasattr(single_detail, "set_document_picker_visible"):
            single_detail.set_document_picker_visible(False)
        record_source_area = getattr(record_batch_detail, "_source_area", None)
        set_record_picker_visible = getattr(
            record_source_area,
            "set_document_picker_visible",
            None,
        )
        if callable(set_record_picker_visible):
            set_record_picker_visible(False)

        self._binding_card = ExecutionBindingCard(single_detail, self)
        layout.addWidget(self._binding_card)

        for detail, names in (
            (single_detail, ("_output_card", "_execution_card")),
            (
                file_batch_detail,
                ("_binding_card", "_output_card", "_execution_card"),
            ),
            (
                record_batch_detail,
                ("_binding_card", "_output_card", "_execution_card"),
            ),
        ):
            for name in names:
                widget = getattr(detail, name, None)
                if widget is not None:
                    widget.setVisible(False)

        self._stack = QStackedWidget(self)
        self._stack.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Maximum,
        )
        for mode in ("single", "files", "records"):
            self._stack.addWidget(self._details[mode])
        self._mapping_issue_detail = QLabel(self)
        self._mapping_issue_detail.setObjectName(
            "wb_document_execution_mapping_issue"
        )
        self._mapping_issue_detail.setWordWrap(True)
        self._mapping_issue_detail.setAlignment(Qt.AlignCenter)
        self._stack.addWidget(self._mapping_issue_detail)
        layout.addWidget(self._stack)

        self._output_card = OutputLocationCard(self)
        layout.addWidget(self._output_card)
        self._output_card.output_changed.connect(
            lambda _path: self._refresh_snapshot()
        )
        self._execution_footer = WorkbenchExecutionFooter(self)
        self._execution_footer.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Maximum,
        )
        layout.addWidget(self._execution_footer)
        self._execution_footer.execute_requested.connect(
            self.execute_requested.emit
        )
        self._execution_footer.retry_requested.connect(
            self.retry_requested.emit
        )
        self._execution_footer.cancel_requested.connect(
            self.cancel_requested.emit
        )
        self._execution_footer.confirmation_cancel_requested.connect(
            self.object_preflight_cancel_requested.emit
        )
        self._execution_footer.repair_requested.connect(
            self.material_repair_requested.emit
        )
        self._execution_footer.summary_changed.connect(
            self.summary_changed.emit
        )
        self._binding_card.binding_changed.connect(
            self._on_binding_snapshot_changed
        )
        layout.addStretch(1)

        file_batch_detail.paths_changed.connect(self._on_paths_changed)
        if hasattr(single_detail, "document_selected"):
            single_detail.document_selected.connect(
                self._on_single_detail_selected
            )
        bind_theme(self, self._apply_execution_mode_theme)
        self._refresh_snapshot()
        self._apply_execution_mode_theme()
        self._apply_topology()

    def active_mode(self) -> str:
        return self._active_mode

    def active_detail(self) -> QWidget:
        if self.active_mode() == "mapping_required":
            return self._mapping_issue_detail
        return self._details[self.active_mode()]

    def selected_paths(self) -> tuple[str, ...]:
        return self._source_area.paths()

    def input_manifest(self):
        return self._source_area.manifest()

    def output_dir(self) -> str:
        return self._output_card.output_dir()

    def output_roots_by_path(self) -> dict[str, str]:
        return self.input_manifest().output_roots(self.output_dir())

    def set_selected_paths(self, paths) -> tuple[str, ...]:
        return self._source_area.set_paths(paths)

    def set_material_selection(
        self,
        selection,
        *,
        preview=None,
        issues=(),
    ) -> None:
        self._material_selection = selection
        self._material_preview = preview
        self._record_ids = tuple(
            str(record_id or "").strip()
            for record_id in getattr(selection, "selected_record_ids", ())
            if str(record_id or "").strip()
        )
        self._details["records"].set_material_selection(
            selection,
            preview=preview,
            issues=tuple(issues),
        )
        self._refresh_snapshot()
        self._apply_topology()

    def set_material_preview(self, preview) -> None:
        self._material_preview = copy.deepcopy(preview)
        self._refresh_snapshot()
        self._apply_topology()

    def set_source_requirement(
        self,
        requirement: SourceRequirement,
    ) -> None:
        self._source_requirement = requirement
        self._refresh_snapshot()
        self._apply_topology()

    def topology(self) -> DocumentExecutionTopology:
        return resolve_document_execution_topology(
            document_paths=self._snapshot.input_manifest.paths(),
            record_ids=(
                self._snapshot.material_selection.selected_record_ids
                if self._snapshot.material_selection is not None
                else ()
            ),
            source_requirement=self._snapshot.source_requirement,
        )

    def snapshot(self) -> DocumentExecutionSnapshot:
        return self._snapshot

    def navigation_snapshot(self) -> dict[str, str]:
        topology = self.topology()
        if topology.blocked:
            return {
                "subtitle": topology.summary,
                "badge_text": "需映射",
                "badge_variant": "warning",
            }
        snapshot = self._execution_footer.navigation_snapshot()
        return {
            "subtitle": topology.summary,
            "badge_text": str(snapshot.get("badge_text") or ""),
            "badge_variant": str(snapshot.get("badge_variant") or "neutral"),
        }

    def _on_single_detail_selected(self, file_path: str) -> None:
        if self._syncing_sources:
            return
        cleaned = str(file_path or "").strip()
        self.set_selected_paths((cleaned,) if cleaned else ())

    def _on_paths_changed(self, paths: object) -> None:
        selected = tuple(paths or ())
        self._syncing_sources = True
        try:
            self._details["single"].set_document_path(
                selected[0] if len(selected) == 1 else ""
            )
            self._details["records"].set_source_document(
                selected[0] if len(selected) == 1 else ""
            )
        finally:
            self._syncing_sources = False
        self._refresh_snapshot()
        self._apply_topology()
        self.document_selected.emit(
            selected[0] if len(selected) == 1 else ""
        )

    def _apply_topology(self) -> None:
        topology = self.topology()
        if topology.kind in {"files", "records"}:
            context_detail = self._details[topology.kind]
            ensure_context_built = getattr(
                context_detail,
                "ensure_context_built",
                None,
            )
            if callable(ensure_context_built):
                ensure_context_built()
            if topology.kind == "records":
                record_source_area = getattr(
                    context_detail,
                    "_source_area",
                    None,
                )
                set_picker_visible = getattr(
                    record_source_area,
                    "set_document_picker_visible",
                    None,
                )
                if callable(set_picker_visible):
                    set_picker_visible(False)
        domain_blockers: tuple[str, ...] = ()
        domain_warnings: tuple[str, ...] = ()
        repair_action = None
        if topology.kind == "single" and topology.document_count:
            decision = self._details["single"].current_execution_gate_decision()
            domain_blockers = tuple(decision.blocking_reasons)
            domain_warnings = tuple(
                (*decision.confirmation_reasons, *decision.warning_reasons)
            )
            repair_action = decision.primary_action
        readiness = inspect_document_execution_readiness(
            topology,
            input_issues=tuple(self._source_area.manifest().issues),
            input_truncated=self._source_area.manifest().truncated,
            domain_blockers=domain_blockers,
            domain_warnings=domain_warnings,
        )
        self._output_card.set_source_paths(self.selected_paths())
        self._output_card.set_topology(topology)
        self._execution_footer.set_context(topology, readiness)
        ready_status = ""
        single_detail = self._details["single"]
        execution_scene = single_detail.execution_scene()
        if (
            str(getattr(execution_scene, "mode_id", "") or "").strip()
            == "official"
            and topology.document_count
        ):
            material_selection = single_detail.execution_material_selection()
            ready_status = (
                "已准备：按公文母版组装"
                if material_selection is not None
                else "已准备：按文种套用内置公文母版"
            )
        self._execution_footer.set_ready_status(ready_status)
        self._execution_footer.set_repair_action(
            label=str(getattr(repair_action, "label", "") or ""),
            target_type=str(
                getattr(repair_action, "target_type", "") or ""
            ),
            target_key=str(getattr(repair_action, "target_key", "") or ""),
            tooltip="打开资料配置",
        )
        next_mode = topology.kind
        if next_mode == "mapping_required":
            self._mapping_issue_detail.setText(
                f"{topology.summary}\n\n{topology.blocking_reason}"
            )
            self._stack.setCurrentWidget(self._mapping_issue_detail)
        else:
            self._stack.setCurrentWidget(self._details[next_mode])

        self._details["single"].set_execute_enabled(
            next_mode == "single" and readiness.can_execute
        )
        self._details["files"].set_execute_enabled(
            next_mode == "files" and readiness.can_execute
        )
        self._details["records"].set_execute_enabled(
            topology.record_count > 0 and readiness.can_execute
        )
        if next_mode != self._active_mode:
            self._active_mode = next_mode
            self.mode_changed.emit(next_mode)
        self._apply_execution_mode_theme()

    def set_execute_enabled(self, enabled: bool) -> None:
        self._execution_footer.set_execute_enabled(enabled)

    def reset_execution_feedback(self) -> None:
        self._execution_footer.reset_execution_feedback()

    def set_execution_progress(self, state) -> None:
        self._execution_state = DocumentExecutionState(
            status="running",
            progress_current=int(getattr(state, "current_step", 0) or 0),
            progress_total=int(getattr(state, "total_steps", 0) or 0),
            stage_text=str(getattr(state, "stage_text", "") or ""),
        )
        self._refresh_snapshot()
        self._execution_footer.set_execution_progress(state)

    def set_execution_result(self, state) -> None:
        self._execution_state = DocumentExecutionState(
            status=str(getattr(state, "status", "") or "failed")
        )
        self._refresh_snapshot()
        self._execution_footer.set_execution_result(state)

    def set_object_preflight_confirmation(
        self,
        state,
        *,
        blocked: bool,
    ) -> None:
        self._execution_footer.set_preflight_confirmation(
            state,
            blocked=blocked,
        )

    def set_confirmation_message(self, message: str) -> None:
        self._execution_footer.set_confirmation_message(message)

    def finish_execution(self) -> None:
        if self._execution_state.status == "running":
            self._execution_state = DocumentExecutionState()
            self._refresh_snapshot()
        self._execution_footer.finish_execution()

    def failed_batch_record_ids(self) -> list[str]:
        return list(self._execution_footer.retry_record_ids())

    def last_batch_run_id(self) -> str:
        return self._execution_footer.last_batch_run_id()

    def next_batch_attempt_number(self) -> int:
        return self._execution_footer.next_batch_attempt_number()

    def _on_binding_snapshot_changed(self, _scene, _template_id: str) -> None:
        self._refresh_snapshot()
        self._apply_topology()

    def _refresh_snapshot(self) -> None:
        scene = self._binding_card.current_scene()
        template_id = self._binding_card.current_template_id()
        self._snapshot = DocumentExecutionSnapshot.capture(
            input_manifest=self._source_area.manifest(),
            material_selection=self._material_selection,
            material_preview=self._material_preview,
            scene_binding=SceneBinding(
                scene_id=str(getattr(scene, "scene_id", "") or ""),
                scene=scene,
            ),
            template_binding=TemplateBinding(template_id=template_id),
            source_requirement=self._source_requirement,
            output_policy=OutputPolicy(
                custom_root=self._output_card.output_dir()
            ),
            execution_state=self._execution_state,
        )

    def _apply_execution_mode_theme(self) -> None:
        theme = get_theme()
        self._mapping_issue_detail.setStyleSheet(
            f"font-size: {theme.font_size_lg}px; "
            f"color: {theme.warning}; background: transparent;"
        )


def _panel_index(panel_id: str) -> int:
    target = str(panel_id or "").strip()
    for index, spec in enumerate(PANEL_SPECS):
        if spec.id == target:
            return index
    return -1


def _hydrate_document_execution_mode(panel, mode: str) -> None:
    mode_id = panel._current_work_mode_id()
    if mode == "files":
        panel._file_batch_execution_detail.set_work_mode(mode_id)
        panel._file_batch_execution_detail.set_scene_context(
            panel._current_scene
        )
        panel._file_batch_execution_detail.set_material_selection(
            panel.bridge.current_material_run_selection(),
            preview=panel.bridge.current_material_preview_snapshot(),
        )
    elif mode == "records" and panel._batch_generation_detail is not None:
        panel._batch_generation_detail.set_work_mode(mode_id)
        panel._batch_generation_detail.set_scene_context(panel._current_scene)
    panel._refresh_quick_execute_card()


def _publish_document_topology_block(panel, reason: str) -> None:
    panel._execution.set_feedback_target("single")
    panel.apply_execution_result(
        {
            "status": "failed",
            "output_path": "",
            "report_paths": [],
            "failed_count": 0,
            "error_text": str(reason or "当前输入关系尚不能执行"),
        }
    )


def _decode_profile_repair_target(payload: str) -> tuple[str, str, str]:
    raw = str(payload or "").strip()
    if not raw:
        return ("", "", "")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return ("", "", raw)
    if not isinstance(data, dict):
        return ("", "", raw)
    return (
        str(data.get("profile_id") or "").strip(),
        str(data.get("profile_name") or "").strip(),
        str(data.get("target_key") or "").strip(),
    )


def _decode_profile_repair_candidate(
    payload: str,
) -> tuple[str, str, dict[str, object]]:
    raw = str(payload or "").strip()
    if not raw:
        return ("", "", {})
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return ("", "", {})
    if not isinstance(data, dict):
        return ("", "", {})
    candidate = data.get("candidate")
    candidate_payload = dict(candidate) if isinstance(candidate, dict) else {}
    target_key = str(data.get("target_key") or "").strip()
    if target_key and not str(candidate_payload.get("repair_target_key") or "").strip():
        candidate_payload["repair_target_key"] = target_key
    return (
        str(data.get("profile_id") or "").strip(),
        str(data.get("profile_name") or "").strip(),
        candidate_payload,
    )


def _decode_transaction_task_summary_target(payload: str) -> tuple[str, str]:
    raw = str(payload or "").strip()
    if not raw:
        return ("", "")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return (raw, "")
    if not isinstance(data, dict):
        return (raw, "")
    report_path = str(data.get("report_path") or "").strip()
    artifact_path = str(data.get("artifact_path") or "").strip()
    fragment = str(data.get("fragment") or "").strip()
    return (report_path or artifact_path, fragment)


class WorkbenchPanel(WorkbenchExecutionLifecycleMixin, BasePanel):
    """Master-detail workbench panel."""

    FEATURE_CARD_ORDER = CAPABILITY_FEATURE_CARD_ORDER

    CARD_DEFINITIONS = {
        "quick_execute": ("文档执行", "zap"),
    }
    if MATERIAL_SUITE_DELIVERY_RELEASED:
        CARD_DEFINITIONS[MATERIAL_SUITE_DELIVERY_CARD_ID] = (
            "成套交付",
            "package",
        )
    CARD_DEFINITIONS.update(CAPABILITY_FEATURE_CARD_DEFINITIONS)

    @scoped_selector_projections
    def _setup_ui(self) -> None:

        self.setObjectName("WorkbenchPanel")

        self._initialize_panel_state()

        self._build_shell_widgets()

        self._build_detail_panes()

        self._build_controllers()

        self._create_navigation_cards()

        self._bootstrap_strategy_context()

        self.restore_workspace_preferences()

        self._refresh_strategy_summary()

        self._sync_dynamic_cards()

        self._refresh_fixed_cards()

        self._nav_rail.select_card("quick_execute")

        self._apply_theme()

        bind_theme(self, self._apply_theme)

    def _initialize_panel_state(self) -> None:

        self._execution_adapter = WorkbenchExecutionAdapter()

        self._strategy_adapter = WorkbenchStrategyAdapter()

        preference_store_getter = getattr(
            self.bridge,
            "workspace_preference_store",
            None,
        )
        self._workspace_preference_store = (
            preference_store_getter()
            if callable(preference_store_getter)
            else None
        )
        self._restoring_workspace_preferences = False

        self._current_template: TemplateConfig | None = None

        self._current_scene: SceneWorkspace | None = None

        self._ignore_own_scene_changed = False
        self._skip_next_scene_dirty_recheck = False
        self._module_switch_projection_stale = False

        self._execution_session = WorkbenchExecutionSessionController(
            resolve_document_path=self._resolve_document_path_for_execution,
            worker_parent=self,
        )
        self._suite_detail_loading = False
        self._suite_detail_loader = _SuiteDetailLoader(self)
        self._suite_load_timer = self._suite_detail_loader.timer
        self._schedule_suite_detail_load = self._suite_detail_loader.schedule
        self._finish_suite_detail_load = self._suite_detail_loader.finish
        self._pending_object_preflight_confirmation_key = ""
        self._pending_object_preflight_evidence: ObjectPreflightEvidence | None = None
        self._confirmed_object_preflight_source_revision = ""
        self._confirmed_object_preflight_digest = ""

        self._strategy_state = self._strategy_adapter.build_summary(None, None)

    def _build_shell_widgets(self) -> None:

        self._shell = MasterDetailShell(
            self,
            panel_name="WorkbenchPanel",
            nav_object_name="wb_v2_navigation",
            detail_object_name="wb_v2_detail",
            detail_content_object_name="wb_v2_detail_content",
        )
        self._layout = self._shell.layout
        self._nav_rail = self._shell.nav_rail
        self._detail_scroll = self._shell.detail_scroll
        self._detail_container = self._shell.detail_container
        self._detail_layout = self._shell.detail_layout

    def _build_detail_panes(self) -> None:

        self._quick_execution_detail = QuickExecutionDetail(
            self,
            include_shared_chrome=False,
        )
        if hasattr(self._quick_execution_detail, "set_work_mode"):
            self._quick_execution_detail.set_work_mode(
                self.bridge.current_work_mode_id()
            )

        # Batch generation is a fixed Workbench destination, but loading its
        # specialist surface must not expand the application entrypoint graph.
        batch_module = import_module("src.ui.panels.workbench.batch_generation_detail")
        self._batch_generation_detail = batch_module.BatchGenerationDetail(
            self,
            defer_context_build=True,
        )
        file_batch_module = import_module(
            "src.ui.panels.workbench.file_batch_execution_detail"
        )
        document_source_area = file_batch_module.FileBatchSourceArea(self)
        self._file_batch_execution_detail = (
            file_batch_module.FileBatchExecutionDetail(
                self,
                source_area=document_source_area,
                include_source_area=False,
                include_shared_chrome=False,
                defer_context_build=True,
            )
        )
        self._suite_generation_detail = None
        if MATERIAL_SUITE_DELIVERY_RELEASED:
            self._suite_generation_detail = _DeferredDetailPlaceholder(self)
            self._suite_generation_detail.retry_requested.connect(
                self._schedule_suite_detail_load
            )
            self._suite_generation_detail.material_workspace_requested.connect(
                lambda: self._emit_panel_navigation("assets")
            )

        # Feature detail panes mapped to new capability group IDs
        self._table_chart_detail = TableChartDetailPane(self)

        self._citation_detail = CitationDetailPane(self)

        self._heading_numbering_detail = self._table_chart_detail

        self._document_execution_detail = DocumentExecutionDetail(
            self._quick_execution_detail,
            self._file_batch_execution_detail,
            self._batch_generation_detail,
            document_source_area,
            self,
        )

        detail_map = {
            "quick_execute": self._document_execution_detail,
            "table_chart": self._table_chart_detail,
            "citation": self._citation_detail,
            "heading_numbering": self._heading_numbering_detail,
        }
        if self._suite_generation_detail is not None:
            detail_map[MATERIAL_SUITE_DELIVERY_CARD_ID] = (
                self._suite_generation_detail
            )

        self._details = DetailPaneController(
            self._detail_container,
            self._detail_layout,
            self._detail_scroll,
        )

        self._details.register_details(detail_map)

        self._detail_map = self._details.detail_map

        self._current_detail: QWidget | None = self._details.current_detail

    def _build_controllers(self) -> None:

        self._document_paths = WorkbenchDocumentPathController(
            self._quick_execution_detail,
            pick_document_path=self._pick_document_path,
        )
        self._document_scope = WorkbenchDocumentScopeController(
            parent=self,
            source_path=lambda: self._document_paths.selected_existing_document() or "",
            mode_id=self._current_work_mode_id,
            scene=lambda: self._quick_execution_detail.execution_scene(
                self._current_scene
                or self._quick_execution_detail.current_scene()
            ),
            status_detail=self._quick_execution_detail,
        )

        self._navigation = WorkbenchNavigationController(
            self._nav_rail,
            self._quick_execution_detail,
            self._batch_generation_detail,
            self._suite_generation_detail,
            document_execution_detail=self._document_execution_detail,
            card_definitions=self.CARD_DEFINITIONS,
            feature_card_order=self.FEATURE_CARD_ORDER,
        )

        self._navigation_cards = self._navigation.navigation_cards

        self._dynamic_cards = self._navigation.dynamic_cards

        self._execution = WorkbenchExecutionController(
            self._execution_adapter,
            self._quick_execution_detail,
            self._batch_generation_detail,
            self._suite_generation_detail,
            file_batch_execution_detail=self._file_batch_execution_detail,
            document_execution_detail=self._document_execution_detail,
            refresh_navigation=self._refresh_fixed_cards,
            clear_execution_worker=self._clear_execution_worker,
            has_ready_document=self._document_paths.has_selected_document,
        )
        self._file_batch_flow = FileBatchWorkbenchController(
            self._file_batch_execution_detail,
            self._execution,
            self._execution_session,
            self._quick_execution_detail,
            active_worker=lambda: self._execution_worker,
            current_template=lambda: (
                self._quick_execution_detail.execution_template(
                    self._current_template
                )
            ),
            current_scene=lambda: self._quick_execution_detail.execution_scene(
                self._current_scene
            ),
            current_mode_id=self._current_work_mode_id,
            current_material_selection=(
                self._quick_execution_detail.execution_material_selection
            ),
            current_document_type_id=(
                self.bridge.current_official_document_type_id
            ),
            execution_binding=lambda: {
                "plan_id": self.bridge.current_scene_id(),
                "plan_path": self.bridge.current_scene_path(),
                "plan_source_type": self.bridge.current_scene_source_type(),
                "template_id": self.bridge.current_template_id(),
                "template_path": self.bridge.current_template_path(),
                "template_source_type": (
                    self.bridge.current_template_source_type()
                ),
            },
            current_output_root=lambda: (
                self._document_execution_detail.output_dir()
                or self._file_batch_execution_detail.output_dir()
            ),
            publish_confirmation=(
                self._document_execution_detail.set_confirmation_message
            ),
            start_worker=self._start_worker_from_build,
            apply_execution_result=self.apply_execution_result,
            refresh_navigation=self._refresh_quick_execute_card,
        )
        self._document_execution = DocumentExecutionCoordinator(
            topology=self._document_execution_detail.topology,
            adapters=DocumentExecutionAdapters(
                single=self._start_execution,
                files=self._file_batch_flow.start,
                records=self._start_batch_execution,
                retry_records=self._start_failed_batch_retry,
                cancel=self._cancel_execution,
            ),
            publish_blocked=lambda reason: _publish_document_topology_block(
                self,
                reason,
            ),
        )
        self._suite_generation_flow = None

    def _create_navigation_cards(self) -> None:

        self._navigation.add_fixed_cards()

    def _bootstrap_strategy_context(self) -> None:

        if self.bridge.current_scene() is not None:
            self._current_scene = self.bridge.current_scene()

        else:
            self._current_scene = self._quick_execution_detail.current_scene()

            scene_entry = get_scene_entry(
                self._current_scene.scene_id,
                mode_id=self._current_work_mode_id(),
            )

            self.bridge.set_current_scene(
                self._current_scene,
                config_id=self._current_scene.scene_id,
                path=str(scene_entry.path) if scene_entry is not None else "",
                source="library" if scene_entry is not None else "builtin",
                source_type=scene_entry.source_type
                if scene_entry is not None
                else "builtin",
                emit_signal=False,
            )

        if self.bridge.current_template() is not None:
            self._current_template = self.bridge.current_template()

        else:
            template_id = self._quick_execution_detail.current_template_id()

            if template_id:
                template_entry = get_template_entry(
                    template_id,
                    mode_id=self._current_work_mode_id(),
                )

                self._current_template = load_template_from_library(
                    template_id,
                    mode_id=self._current_work_mode_id(),
                )

                self.bridge.set_current_template(
                    self._current_template,
                    config_id=template_id,
                    path=str(template_entry.path) if template_entry is not None else "",
                    source="library" if template_entry is not None else "builtin",
                    source_type=(
                        template_entry.source_type
                        if template_entry is not None
                        else "builtin"
                    ),
                    emit_signal=False,
                )

        self._quick_execution_detail.set_scene_context(self._current_scene)

        self._quick_execution_detail.set_template_context(self._current_template)
        current_document_path = str(self.bridge.current_document_path() or "").strip()
        if current_document_path:
            selected_document = self._document_paths.apply_loaded_document(
                current_document_path
            )
            if selected_document:
                self._document_execution_detail.set_selected_paths(
                    (selected_document,)
                )
                self._document_scope.start_scan(selected_document)

        material_selection = self.bridge.current_material_run_selection()
        material_preview = self.bridge.current_material_preview_snapshot()
        material_issues = self.bridge.current_material_issues()
        self._quick_execution_detail.set_material_selection(
            material_selection,
            preview_snapshot=material_preview,
            issues=material_issues,
        )
        self._document_execution_detail.set_material_preview(material_preview)
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_source_document(
                self.bridge.current_document_path()
            )
        self._quick_execution_detail.set_official_document_type_id(
            self.bridge.current_official_document_type_id()
        )
        self._document_scope.recheck()
        self._document_execution_detail.set_material_selection(
            material_selection,
            preview=material_preview,
            issues=material_issues,
        )
        self._refresh_document_source_requirement()
        if self._suite_generation_flow is not None:
            self._suite_generation_flow.apply_material_selection(
                material_selection,
                preview=material_preview,
                issues=material_issues,
            )

    def _connect_signals(self) -> None:

        self.bridge.template_changed.connect(self.on_template_changed)

        self.bridge.scene_changed.connect(self.on_scene_changed)

        if hasattr(self.bridge, "work_mode_changed"):
            self.bridge.work_mode_changed.connect(self._on_work_mode_changed)

        self.bridge.material_run_selection_changed.connect(
            self._on_material_run_selection_changed
        )
        self.bridge.material_preview_snapshot_changed.connect(
            self._on_material_preview_snapshot_changed
        )
        self.bridge.material_issues_changed.connect(
            self._on_material_issues_changed
        )
        self.bridge.official_document_type_changed.connect(
            self._on_official_document_type_changed
        )

        self.bridge.document_loaded.connect(self._on_document_loaded)

        self.bridge.scene_dirty_changed.connect(self._on_scene_dirty_changed)

        self._nav_rail.card_selected.connect(self._on_card_selected)

        self._quick_execution_detail.feature_toggled.connect(self._on_feature_toggled)

        self._quick_execution_detail.feature_config_requested.connect(
            self._open_feature_card
        )

        self._quick_execution_detail.material_repair_requested.connect(
            self._open_material_repair_target
        )
        self._document_execution_detail.material_repair_requested.connect(
            self._open_material_repair_target
        )

        self._quick_execution_detail.summary_changed.connect(
            self._on_quick_summary_changed
        )

        self._document_execution_detail._binding_card.binding_changed.connect(
            self._on_quick_binding_changed
        )

        self._quick_execution_detail.scene_config_changed.connect(
            self._on_quick_scene_config_changed
        )
        self._quick_execution_detail.official_document_type_changed.connect(
            self._sync_official_document_type_from_quick
        )

        self._document_execution_detail.execute_requested.connect(
            self._document_execution.start
        )
        self._document_execution_detail.retry_requested.connect(
            self._document_execution.retry
        )
        self._document_execution_detail.cancel_requested.connect(
            self._document_execution.cancel
        )
        self._document_execution_detail.summary_changed.connect(
            self._refresh_quick_execute_card
        )
        self._document_execution_detail.mode_changed.connect(
            lambda mode: _hydrate_document_execution_mode(self, mode)
        )
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.source_document_selected.connect(
                self._on_batch_detail_document_selected
            )
            self._batch_generation_detail.summary_changed.connect(
                self._refresh_quick_execute_card
            )

        self._quick_execution_detail.object_preflight_cancel_requested.connect(
            self._cancel_object_preflight_confirmation
        )
        self._document_execution_detail.object_preflight_cancel_requested.connect(
            self._cancel_object_preflight_confirmation
        )
        # Compatibility signal: the visible cancel action now lives in the
        # shared footer, while legacy extensions may still emit this signal.
        self._quick_execution_detail.cancel_requested.connect(self._cancel_execution)

        self._document_execution_detail.document_selected.connect(
            self._on_quick_detail_document_selected
        )
        self._quick_execution_detail.material_package_selected.connect(
            self._on_quick_material_package_selected
        )
        self._quick_execution_detail.preference_changed.connect(
            self._persist_workspace_preferences
        )
        self._document_execution_detail._output_card.output_changed.connect(
            lambda _path: self._persist_workspace_preferences()
        )

        self._nav_rail.select_card(self._nav_rail.selected_card_id() or "quick_execute")

    def _current_work_mode_id(self) -> str:
        if hasattr(self.bridge, "current_work_mode_id"):
            return str(self.bridge.current_work_mode_id() or "").strip()
        return "custom"

    def restore_workspace_preferences(self) -> None:
        store = getattr(self, "_workspace_preference_store", None)
        if store is None:
            return
        preference = (
            store.load().for_mode(self._current_work_mode_id())
            or ModeWorkspacePreferences()
        )

        self._restoring_workspace_preferences = True
        try:
            self._quick_execution_detail.restore_preference_state(
                execution_template_id=preference.execution_template_id,
                plan_enabled=preference.plan_enabled,
                template_enabled=preference.template_enabled,
                material_enabled=preference.material_enabled,
                material_package_id=preference.material_package_id,
                official_document_type_id=(
                    preference.official_document_type_id
                ),
            )

            projection = (
                choose_material_package(
                    preference.material_package_id,
                    work_mode_id=self._current_work_mode_id(),
                )
                if preference.material_enabled
                and preference.material_package_id
                else choose_material_package(
                    "",
                    work_mode_id=self._current_work_mode_id(),
                )
            )
            self.bridge.set_current_material_run_selection(
                projection.selection,
                emit_signal=False,
            )
            self.bridge.set_current_material_preview_snapshot(
                projection.preview,
                emit_signal=False,
            )
            self.bridge.set_current_material_issues(
                projection.issues,
                emit_signal=False,
            )
            self._on_material_preview_snapshot_changed(projection.preview)

            output_dir = (
                preference.custom_output_dir
                if preference.output_mode == "custom"
                else ""
            )
            self._document_execution_detail._output_card.set_output_dir(
                output_dir
            )
            self._refresh_strategy_summary()
            self._refresh_fixed_cards()
        finally:
            self._restoring_workspace_preferences = False

    def _persist_workspace_preferences(self) -> None:
        store = getattr(self, "_workspace_preference_store", None)
        if store is None or self._restoring_workspace_preferences:
            return
        selection = self.bridge.current_material_run_selection()
        package_id = (
            selection.package_ref.package_id
            if isinstance(selection, MaterialRunSelection)
            else self._quick_execution_detail.selected_material_package_id()
        )
        material_enabled = bool(
            self._quick_execution_detail.material_package_enabled()
            and package_id
        )
        output_dir = self._document_execution_detail.output_dir()
        try:
            store.update_mode(
                self._current_work_mode_id(),
                execution_template_id=(
                    self._quick_execution_detail.selected_template_id()
                ),
                plan_enabled=self._quick_execution_detail.plan_enabled(),
                template_enabled=(
                    self._quick_execution_detail.template_enabled()
                ),
                material_enabled=material_enabled,
                material_package_id=package_id if material_enabled else "",
                official_document_type_id=(
                    self._quick_execution_detail.official_document_type_id()
                ),
                output_mode="custom" if output_dir else "default",
                custom_output_dir=output_dir,
            )
        except (OSError, TypeError, ValueError) as exc:
            logger.warning(
                "Could not persist Workbench preferences: %s",
                exc,
                exc_info=exc,
            )

    def _on_work_mode_changed(self, _emitted_mode) -> None:
        # Mode activation may be rolled back by an earlier signal listener.
        # Downstream panes must project Bridge's final state, not a stale
        # payload that is still completing its outer Qt dispatch.
        mode_id = self._current_work_mode_id()
        self._document_scope.reset_decisions()
        self._document_execution_detail._binding_card.set_work_mode(mode_id)
        self._quick_execution_detail.set_official_document_type_id(
            self.bridge.current_official_document_type_id()
        )
        self._document_scope.recheck()

    def closeEvent(self, event) -> None:

        if not self.shutdown_active_execution(timeout_ms=1000):
            event.ignore()

            return

        if not self._document_scope.shutdown(timeout_ms=1000):
            event.ignore()
            return

        super().closeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API

        super().showEvent(event)
        if self._module_switch_projection_stale:
            QTimer.singleShot(0, self._flush_module_switch_projection)

    def _defer_module_switch_projection(self) -> None:

        self._module_switch_projection_stale = True
        if self.isVisible():
            QTimer.singleShot(0, self._flush_module_switch_projection)

    def _flush_module_switch_projection(self) -> None:

        if not self._module_switch_projection_stale:
            return
        self._module_switch_projection_stale = False
        self._refresh_strategy_summary()
        self._refresh_fixed_cards()

    def _refresh_fixed_cards(self) -> None:

        self._navigation.refresh_fixed_cards(
            cached_document_path=self._document_paths.cached_document_path,
            strategy_state=self._strategy_state,
            execution_worker=self._execution_worker,
        )

    def _refresh_quick_execute_card(self) -> None:

        self._navigation.refresh_quick_execute_card(
            cached_document_path=self._document_paths.cached_document_path,
            strategy_state=self._strategy_state,
            execution_worker=self._execution_worker,
        )

    def _refresh_strategy_summary(self) -> None:

        self._sync_strategy_state()

        template_id = self.bridge.current_template_id()
        if not template_id and self._current_scene is not None:
            template_id = self._current_scene.template_id

        self._document_execution_detail._binding_card.set_strategy_context(
            template_name=self._strategy_state.template_label,
            template_id=template_id,
            scene_name=self._strategy_state.name
            if self._strategy_state.source_type == "scene"
            else "",
            strict_mode=self._strategy_state.strict_mode
            if self._strategy_state.source_type == "scene"
            else None,
        )

    def _sync_strategy_state(self) -> None:

        self._strategy_state = self._strategy_adapter.build_summary(
            self._quick_execution_detail.execution_template(
                self._current_template
            ),
            self._quick_execution_detail.execution_scene(
                self._current_scene
            ),
        )

    def _on_quick_detail_document_selected(self, file_path: str) -> None:

        self._clear_object_preflight_confirmation()
        if not str(file_path or "").strip():
            self._document_paths.clear_selection()
            self.bridge.set_current_document_path("", emit_signal=False)
            self._document_scope.clear()
            return

        selected = self._document_paths.accept_detail_selection(file_path)

        if not selected:
            return

        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_source_document(selected)
        self.bridge.set_current_document_path(selected)

    def _on_batch_detail_document_selected(self, file_path: str) -> None:
        """Publish a source chosen on the batch page through the shared bridge."""

        self._on_quick_detail_document_selected(file_path)

    def _on_feature_toggled(self, _feature_id: str, _enabled: bool) -> None:

        self._sync_dynamic_cards()

    def _on_quick_summary_changed(self) -> None:

        self._sync_strategy_state()
        self._refresh_document_source_requirement()

        self._refresh_quick_execute_card()

    def _on_quick_binding_changed(
        self, scene: SceneWorkspace, template_id: str
    ) -> None:

        self._clear_object_preflight_confirmation()

        current_bridge_scene = self.bridge.current_scene()
        current_scene_id = str(self.bridge.current_scene_id() or "").strip()
        next_scene_id = str(getattr(scene, "scene_id", "") or "").strip()
        if (
            self.bridge.is_scene_dirty()
            and current_bridge_scene is not None
            and current_scene_id
            and next_scene_id != current_scene_id
        ):
            self._document_execution_detail._binding_card.set_scene_context(
                current_bridge_scene
            )
            Toast.show_warning(
                "\u5f53\u524d\u65b9\u6848\u6709\u672a\u4fdd\u5b58\u4fee\u6539\uff0c\u8bf7\u5148\u4fdd\u5b58\u6216\u6062\u590d\u540e\u518d\u5207\u6362\u3002"
            )
            return

        if (
            self.bridge.is_scene_dirty()
            and current_bridge_scene is not None
            and next_scene_id == current_scene_id
        ):
            scene = copy.deepcopy(current_bridge_scene)

        self._current_scene = scene

        scene_entry = get_scene_entry(
            scene.scene_id, mode_id=self._current_work_mode_id()
        )

        self.bridge.set_current_scene(
            scene,
            config_id=scene.scene_id,
            path=str(scene_entry.path) if scene_entry is not None else "",
            source="library" if scene_entry is not None else "builtin",
            source_type=scene_entry.source_type
            if scene_entry is not None
            else "builtin",
        )

        template_id = str(template_id or "").strip()

        if template_id:
            if (
                self.bridge.current_template() is not None
                and self.bridge.current_template_id() == template_id
                and self.bridge.current_template_mode_id()
                == self._current_work_mode_id()
            ):
                self._current_template = self.bridge.current_template()
                self._quick_execution_detail.set_template_context(
                    self._current_template
                )
                self._refresh_strategy_summary()
                self._refresh_fixed_cards()
                return

            template_entry = get_template_entry(
                template_id, mode_id=self._current_work_mode_id()
            )

            try:
                template = load_template_from_library(
                    template_id,
                    mode_id=self._current_work_mode_id(),
                )

            except Exception as exc:
                logger.warning(
                    "Workbench quick binding ignored template load failure for %s: %s",
                    template_id,
                    exc,
                    exc_info=exc,
                )

                template = None

            if template is not None:
                self.bridge.set_current_template(
                    template,
                    config_id=template_id,
                    path=str(template_entry.path) if template_entry is not None else "",
                    source="library" if template_entry is not None else "builtin",
                    source_type=(
                        template_entry.source_type
                        if template_entry is not None
                        else "builtin"
                    ),
                )

    def _on_quick_scene_config_changed(self, scene: SceneWorkspace) -> None:

        self._clear_object_preflight_confirmation()

        self._current_scene = scene

        scene_entry = get_scene_entry(
            scene.scene_id, mode_id=self._current_work_mode_id()
        )

        self._ignore_own_scene_changed = True
        try:
            self.bridge.set_current_scene(
                scene,
                config_id=scene.scene_id,
                path=str(scene_entry.path) if scene_entry is not None else "",
                source="library" if scene_entry is not None else "builtin",
                source_type=scene_entry.source_type
                if scene_entry is not None
                else "builtin",
            )
        finally:
            self._ignore_own_scene_changed = False

        if not self.bridge.is_scene_dirty():
            self._skip_next_scene_dirty_recheck = True
        self.bridge.mark_scene_dirty()
        self._document_scope.recheck()

    def _sync_dynamic_cards(self) -> None:

        self._navigation.sync_dynamic_cards()

    def _open_feature_card(self, feature_id: str) -> None:
        target = str(feature_id or "").strip()
        if target not in self._navigation_cards:
            logger.warning("Ignoring unavailable Workbench card: %s", target)
            target = "quick_execute"
        self._navigation.open_feature_card(target)

    def _emit_panel_navigation(
        self,
        panel_id: str,
        *,
        card_id: str = "",
        issue_type: str = "",
        issue_key: str = "",
        issue_context: dict[str, str] | None = None,
        return_card_id: str = "quick_execute",
    ) -> None:
        index = _panel_index(panel_id)
        if index >= 0:
            self.bridge.navigate_to_panel.emit(index)
        context = dict(issue_context or {})
        active_issue_id = str(
            context.get("active_issue_id") or context.get("issue_item_id") or ""
        ).strip()
        issue_display_name = str(
            context.get("issue_target_label_with_group")
            or context.get("issue_target_label")
            or ""
        ).strip()
        if not issue_display_name and issue_type == "template_style_field":
            issue_display_name = field_display_context(
                issue_key,
                target_type=issue_type,
            ).label_with_group()
        if not issue_display_name:
            issue_display_name = navigation_issue_hint(
                str(context.get("issue_title") or "").strip(),
                issue_key,
                issue_type=issue_type,
            )
        self.bridge.navigate_to_intent.emit(
            {
                "panel_id": panel_id,
                "card_id": card_id,
                "issue_id": issue_type,
                "field_id": issue_key,
                "active_issue_id": active_issue_id,
                "return_panel_id": "workbench",
                "return_card_id": str(return_card_id or "quick_execute"),
                "payload": {
                    **context,
                    "issue_type": issue_type,
                    "issue_key": issue_key,
                    "issue_display_name": issue_display_name,
                },
            }
        )

    def _navigate_issue_projection(
        self,
        projection: WorkbenchIssueNavigationProjection,
    ) -> bool:
        if projection.panel_id:
            self._emit_panel_navigation(
                projection.panel_id,
                card_id=projection.card_id,
                issue_type=projection.target_type,
                issue_key=projection.target_key,
                return_card_id="quick_execute",
            )
            return True
        if projection.feature_card_id:
            self._open_feature_card(projection.feature_card_id)
            return True
        return False

    def _open_material_repair_target(self, target_type: str, target_key: str) -> None:

        normalized_type = str(target_type or "").strip()

        normalized_key = str(target_key or "").strip()
        projection = workbench_issue_navigation_for_target(
            normalized_type,
            normalized_key,
        )

        if (
            normalized_type in {"asset", "field", "question_figure_item"}
            and normalized_key
        ):
            self.bridge.request_material_repair_target(normalized_type, normalized_key)

            if self._navigate_issue_projection(projection):
                return

        if projection.action_kind == "material_target":
            if self._navigate_issue_projection(projection):
                return

        if projection.action_kind in {"scene_panel", "template_panel", "feature_card"}:
            if self._navigate_issue_projection(projection):
                return

        self._emit_panel_navigation("assets")

    def _open_issue_repair_target(self, target_type: str, target_key: str) -> None:

        normalized_type = str(target_type or "").strip()

        normalized_key = str(target_key or "").strip()
        projection = workbench_issue_navigation_for_target(
            normalized_type,
            normalized_key,
        )

        if projection.action_kind == "material_profile_candidate":
            profile_id, profile_name, candidate = _decode_profile_repair_candidate(
                normalized_key
            )

            self.bridge.request_material_profile_repair_candidate(
                profile_id,
                profile_name,
                candidate,
            )

            if self._navigate_issue_projection(projection):
                return

        if projection.action_kind == "material_profile_target":
            profile_id, profile_name, repair_key = _decode_profile_repair_target(
                normalized_key
            )

            base_type = normalized_type.removeprefix("profile_")

            self.bridge.request_material_profile_repair_target(
                profile_id,
                profile_name,
                base_type,
                repair_key,
            )

            if self._navigate_issue_projection(projection):
                return

        if projection.action_kind == "material_target":
            self._open_material_repair_target(normalized_type, normalized_key)

            return

        if projection.action_kind == "template_panel":
            self._navigate_issue_projection(projection)
            return

        if projection.action_kind == "transaction_artifact":
            path, fragment = _decode_transaction_task_summary_target(normalized_key)

            if path:
                recent_run_panel_module._open_artifact_file(path, fragment=fragment)

            self._navigate_issue_projection(projection)
            return

        if projection.action_kind in {"scene_panel", "feature_card"}:
            self._navigate_issue_projection(projection)
            return

        self._open_feature_card(projection.feature_card_id or "quick_execute")

    def handle_navigation_intent(self, intent) -> None:
        card_id = str(navigation_intent_value(intent, "card_id", "") or "").strip()
        if card_id and is_workbench_card_released(card_id):
            self._nav_rail.select_card(card_id)

    def _on_card_selected(self, card_id: str) -> None:

        if not is_workbench_card_released(card_id):
            return

        self._details.show_detail(card_id)

        self._current_detail = self._details.current_detail
        if card_id == MATERIAL_SUITE_DELIVERY_CARD_ID:
            self._schedule_suite_detail_load()
        elif self._suite_load_timer.isActive():
            self._suite_load_timer.stop()
            self._suite_detail_loading = False

    def _on_document_loaded(self, file_path: str) -> None:

        self._clear_object_preflight_confirmation()

        selected_document = self._document_paths.apply_loaded_document(file_path)
        if selected_document is None:
            return

        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_source_document(selected_document)
        self._document_execution_detail.set_selected_paths(
            (selected_document,) if selected_document else ()
        )
        self._document_scope.start_scan(selected_document, force=True)
        self._refresh_quick_execute_card()

    def on_template_changed(self, template: TemplateConfig) -> None:

        self._clear_object_preflight_confirmation()

        self._current_template = template

        self._document_execution_detail._binding_card.set_template_context(
            template
        )

        self._refresh_strategy_summary()

        self._refresh_fixed_cards()
        self._module_switch_projection_stale = False

    def on_scene_changed(self, scene: SceneWorkspace) -> None:

        self._clear_object_preflight_confirmation()

        self._current_scene = scene

        if self.bridge.scene_change_reason() == "module_switches":
            self._defer_module_switch_projection()
            return

        if getattr(self, "_ignore_own_scene_changed", False):
            return

        self._document_execution_detail._binding_card.set_scene_context(scene)
        active_mode = self._document_execution_detail.active_mode()
        if active_mode == "files":
            self._file_batch_execution_detail.set_scene_context(scene)
        elif active_mode == "records" and self._batch_generation_detail is not None:
            self._batch_generation_detail.set_scene_context(scene)
        self._refresh_document_source_requirement()
        self._document_scope.recheck()

        self._refresh_strategy_summary()

        self._refresh_fixed_cards()
        self._module_switch_projection_stale = False

    def _on_scene_dirty_changed(self, dirty: bool) -> None:

        if self.bridge.scene_change_reason() == "module_switches":
            if hasattr(self.bridge, "consume_scene_dirty_recheck_suppressed"):
                self.bridge.consume_scene_dirty_recheck_suppressed()
            self._defer_module_switch_projection()
            return

        if dirty:
            bridge_skip_recheck = (
                self.bridge.consume_scene_dirty_recheck_suppressed()
                if hasattr(self.bridge, "consume_scene_dirty_recheck_suppressed")
                else False
            )
            if (
                getattr(self, "_skip_next_scene_dirty_recheck", False)
                or bridge_skip_recheck
            ):
                self._skip_next_scene_dirty_recheck = False
            else:
                self._quick_execution_detail.recheck_current_context()
        else:
            self._skip_next_scene_dirty_recheck = False

        self._refresh_fixed_cards()

    def _on_material_preview_snapshot_changed(self, snapshot) -> None:
        self._quick_execution_detail.set_material_preview_snapshot(snapshot)
        self._document_execution_detail.set_material_preview(snapshot)
        self._on_material_run_selection_changed(
            self.bridge.current_material_run_selection()
        )

    def _on_official_document_type_changed(self, document_type_id: str) -> None:
        self._clear_object_preflight_confirmation()
        self._quick_execution_detail.set_official_document_type_id(document_type_id)
        self._refresh_quick_execute_card()

    def _sync_official_document_type_from_quick(self, document_type_id: str) -> None:
        self._clear_object_preflight_confirmation()
        self.bridge.set_current_official_document_type_id(document_type_id)

    def _on_material_run_selection_changed(self, selection) -> None:
        preview = self.bridge.current_material_preview_snapshot()
        issues = self.bridge.current_material_issues()
        material_enabled = None
        if selection is None and not issues:
            material_enabled = False
        self._quick_execution_detail.set_material_selection(
            selection,
            preview_snapshot=preview,
            issues=issues,
            material_enabled=material_enabled,
        )
        self._document_execution_detail.set_material_selection(
            selection,
            preview=preview,
            issues=issues,
        )
        self._refresh_document_source_requirement(selection)
        self._refresh_quick_execute_card()
        if self._suite_generation_flow is not None:
            self._suite_generation_flow.apply_material_selection(
                selection,
                preview=preview,
                issues=issues,
            )

    def _refresh_document_source_requirement(self, selection=None) -> None:
        del selection
        self._document_execution_detail.set_source_requirement("required")

    def _on_material_issues_changed(self, issues) -> None:
        normalized = tuple(issues or ())
        self._quick_execution_detail.set_material_issues(normalized)
        self._on_material_run_selection_changed(
            self.bridge.current_material_run_selection()
        )

    def _on_quick_material_package_selected(self, package_id: str) -> None:
        projection = choose_material_package(
            package_id,
            work_mode_id=self._current_work_mode_id(),
        )
        self.bridge.set_current_material_preview_snapshot(projection.preview)
        self.bridge.set_current_material_issues(projection.issues)
        self.bridge.set_current_material_run_selection(projection.selection)

    def _execute_requested(self) -> None:

        self._start_execution()

    def _cancel_execution(self) -> None:

        self._execution.cancel_execution(self._execution_worker)

    def _cancel_object_preflight_confirmation(self) -> None:
        self._clear_object_preflight_confirmation()
        if self._quick_execution_detail.has_local_execution_surface():
            self._quick_execution_detail.reset_execution_feedback()
        self._document_execution_detail.reset_execution_feedback()
        self._refresh_quick_execute_card()

    def _resolve_document_path_for_execution(self) -> str | None:
        document_path = self._document_paths.resolve_execution_document()
        if document_path and self._batch_generation_detail is not None:
            self._batch_generation_detail.set_source_document(document_path)
        if document_path and document_path != self.bridge.current_document_path():
            self.bridge.set_current_document_path(document_path)
        return document_path

    def _pick_document_path(self) -> str | None:
        cleaned = str(self._quick_execution_detail.pick_document_path() or "").strip()
        return cleaned or None

    def _start_execution(self) -> None:
        if self._execution_worker is not None:
            return
        set_feedback_target = getattr(self._execution, "set_feedback_target", None)
        if callable(set_feedback_target):
            set_feedback_target("single")
        effective_mode_id = self._current_work_mode_id()
        execution_scene = self._quick_execution_detail.execution_scene(
            self._current_scene
        )
        execution_template = self._quick_execution_detail.execution_template(
            self._current_template
        )
        selection = self._quick_execution_detail.execution_material_selection()
        material_gate = (
            self._quick_execution_detail.current_execution_gate_decision()
        )
        if not material_gate.can_run:
            self._quick_execution_detail.recheck_current_context(force=True)
            return
        if self._resolve_document_path_for_execution() is None:
            return
        if not self._document_scope.ensure_confirmed():
            return
        if not self._ensure_object_preflight_confirmed():
            return
        build = self._execution_session.build_document_worker(
            template=execution_template,
            scene=execution_scene,
            selection=selection,
            session_overrides=self._quick_execution_detail.runtime_template_overrides(),
            document_type_id=(
                self.bridge.current_official_document_type_id()
                if effective_mode_id == "official"
                else ""
            ),
            mode_id=effective_mode_id,
            plan_id=self.bridge.current_scene_id(),
            plan_path=self.bridge.current_scene_path(),
            plan_source_type=self.bridge.current_scene_source_type(),
            template_id=self.bridge.current_template_id(),
            template_path=self.bridge.current_template_path(),
            template_source_type=self.bridge.current_template_source_type(),
            output_root=self._document_execution_detail.output_dir(),
            document_structure_evidence=self._document_scope.evidence,
            document_scope_decisions=self._document_scope.decisions,
        )

        self._start_worker_from_build(build)

    def _start_batch_execution(self) -> None:
        if self._batch_generation_detail is None or self._execution_worker is not None:
            return
        topology = self._document_execution_detail.topology()
        if topology.record_count == 0 or topology.kind not in {"single", "records"}:
            self._execution.reset_feedback()
            self.apply_execution_result(
                {
                    "status": "failed",
                    "output_path": "",
                    "report_paths": [],
                    "failed_count": 0,
                    "error_text": (
                        topology.blocking_reason
                        or "当前输入未识别为按资料批量执行"
                    ),
                }
            )
            self._refresh_quick_execute_card()
            return
        self._batch_generation_detail.ensure_context_built()
        set_feedback_target = getattr(self._execution, "set_feedback_target", None)
        if callable(set_feedback_target):
            set_feedback_target("batch")

        selection = self._quick_execution_detail.execution_material_selection()
        execution_scene = self._quick_execution_detail.execution_scene(
            self._current_scene
        )
        execution_template = self._quick_execution_detail.execution_template(
            self._current_template
        )
        self._batch_generation_detail.set_work_mode(self._current_work_mode_id())
        self._batch_generation_detail.set_scene_context(execution_scene)
        self._batch_generation_detail.set_material_selection(
            selection,
            preview=self.bridge.current_material_preview_snapshot(),
            issues=self.bridge.current_material_issues(),
        )
        self._batch_generation_detail.set_runtime_template_overrides(
            self._quick_execution_detail.runtime_template_overrides()
        )

        if selection is None or not selection.selected_record_ids:
            self._execution.reset_feedback()

            self.apply_execution_result(
                {
                    "status": "failed",
                    "output_path": "",
                    "report_paths": [],
                    "failed_count": 0,
                    "error_text": "尚未选择可执行资料记录",
                }
            )

            return

        material_gate = (
            self._batch_generation_detail.current_batch_execution_gate_decision()
        )
        if (
            not material_gate.can_run
            or not self._batch_generation_detail.can_start_execution()
        ):
            self._refresh_quick_execute_card()
            return

        document_path = self._resolve_document_path_for_execution()
        if document_path is None:
            return
        if not self._document_scope.ensure_confirmed():
            return
        if not self._ensure_object_preflight_confirmed():
            return

        build = self._execution_session.build_record_batch_worker(
            document_paths=(document_path,),
            template=execution_template,
            scene=execution_scene,
            selection=selection,
            output_root=(
                self._document_execution_detail.output_dir()
                or self._batch_generation_detail.output_dir()
            ),
            session_overrides=self._batch_generation_detail.runtime_template_overrides(),
            document_type_id=(
                self.bridge.current_official_document_type_id()
                if self._current_work_mode_id() == "official"
                else ""
            ),
            mode_id=self._current_work_mode_id(),
            plan_id=self.bridge.current_scene_id(),
            plan_path=self.bridge.current_scene_path(),
            plan_source_type=self.bridge.current_scene_source_type(),
            template_id=self.bridge.current_template_id(),
            template_path=self.bridge.current_template_path(),
            template_source_type=self.bridge.current_template_source_type(),
            document_structure_evidence=self._document_scope.evidence,
            document_scope_decisions=self._document_scope.decisions,
        )

        self._start_worker_from_build(build)

    def _start_failed_batch_retry(self) -> None:
        if self._batch_generation_detail is None or self._execution_worker is not None:
            return
        set_feedback_target = getattr(self._execution, "set_feedback_target", None)
        if callable(set_feedback_target):
            set_feedback_target("batch")

        source_selection = self._quick_execution_detail.execution_material_selection()
        if source_selection is None:
            return
        execution_scene = self._quick_execution_detail.execution_scene(
            self._current_scene
        )
        execution_template = self._quick_execution_detail.execution_template(
            self._current_template
        )
        self._batch_generation_detail.set_work_mode(self._current_work_mode_id())
        self._batch_generation_detail.set_scene_context(execution_scene)
        self._batch_generation_detail.set_material_selection(
            source_selection,
            preview=self.bridge.current_material_preview_snapshot(),
            issues=self.bridge.current_material_issues(),
        )
        self._batch_generation_detail.set_runtime_template_overrides(
            self._quick_execution_detail.runtime_template_overrides()
        )
        failed_record_ids = self._document_execution_detail.failed_batch_record_ids()
        retry_selection = MaterialRunSelection(
            package_ref=source_selection.package_ref,
            selected_record_ids=tuple(failed_record_ids),
            runtime_field_overrides=source_selection.runtime_field_overrides,
            runtime_resource_overrides=source_selection.runtime_resource_overrides,
            runtime_image_watermark_text=source_selection.runtime_image_watermark_text,
        )

        if not retry_selection.selected_record_ids:
            self.apply_execution_result(
                {
                    "status": "failed",
                    "output_path": "",
                    "report_paths": [],
                    "failed_count": 0,
                    "error_text": "没有可重试的公文批次失败项",
                }
            )

            return

        retry_gate = (
            self._batch_generation_detail.current_batch_execution_gate_decision()
        )
        if not retry_gate.can_run:
            self.apply_execution_result(
                {
                    "status": "failed",
                    "output_path": "",
                    "report_paths": [],
                    "failed_count": len(retry_selection.selected_record_ids),
                    "error_text": "；".join(retry_gate.blocking_reasons),
                }
            )
            return

        document_path = self._resolve_document_path_for_execution()
        if document_path is None:
            return
        if not self._document_scope.ensure_confirmed():
            return
        if not self._ensure_object_preflight_confirmed():
            return

        build = self._execution_session.build_record_batch_worker(
            document_paths=(document_path,),
            template=execution_template,
            scene=execution_scene,
            selection=retry_selection,
            output_root=(
                self._document_execution_detail.output_dir()
                or self._batch_generation_detail.output_dir()
            ),
            session_overrides=self._batch_generation_detail.runtime_template_overrides(),
            document_type_id=(
                self.bridge.current_official_document_type_id()
                if self._current_work_mode_id() == "official"
                else ""
            ),
            mode_id=self._current_work_mode_id(),
            plan_id=self.bridge.current_scene_id(),
            plan_path=self.bridge.current_scene_path(),
            plan_source_type=self.bridge.current_scene_source_type(),
            template_id=self.bridge.current_template_id(),
            template_path=self.bridge.current_template_path(),
            template_source_type=self.bridge.current_template_source_type(),
            document_structure_evidence=self._document_scope.evidence,
            document_scope_decisions=self._document_scope.decisions,
        )

        self._start_worker_from_build(build)

    def _start_worker_from_build(self, build) -> None:

        if build.already_running:
            return

        if getattr(build, "error_text", ""):
            self._execution.reset_feedback()
            self.apply_execution_result(
                {
                    "status": "failed",
                    "output_path": "",
                    "report_paths": [],
                    "failed_count": 0,
                    "error_text": str(build.error_text),
                    "execution_session": (
                        build.session_snapshot.to_dict()
                        if build.session_snapshot is not None
                        else {}
                    ),
                }
            )
            return

        worker = build.worker

        if worker is None:
            if build.cancelled:
                return

            self._execution.reset_feedback()

            self.apply_execution_result(
                {
                    "status": "failed",
                    "output_path": "",
                    "report_paths": [],
                    "failed_count": 0,
                    "error_text": "No execution worker available",
                }
            )

            return

        self._execution_worker = worker
        try:
            self._execution.prepare_worker(worker)
            self._execution_session.start_worker(worker)
        except Exception as exc:
            snapshot = getattr(build, "session_snapshot", None)
            cleanup_issues = self._execution_session.discard_worker(
                worker,
                snapshot=snapshot,
            )
            error_parts = [
                f"execution_worker_start_failed:{type(exc).__name__}:{exc}",
                *cleanup_issues,
            ]
            self._execution.reset_feedback()
            self.apply_execution_result(
                {
                    "status": "failed",
                    "output_path": "",
                    "report_paths": [],
                    "failed_count": 0,
                    "error_text": "; ".join(
                        part for part in error_parts if str(part).strip()
                    ),
                    "execution_session": (
                        snapshot.to_dict() if snapshot is not None else {}
                    ),
                }
            )
            return

        self._clear_object_preflight_confirmation()

    def _clear_execution_worker(self) -> None:

        self._execution_session.clear_active_worker()

    def apply_execution_result(self, result) -> None:

        self._execution.apply_execution_result(result)

    def _ensure_object_preflight_confirmed(self) -> bool:

        doc_path = self._document_paths.selected_existing_document()
        scene = self._quick_execution_detail.execution_scene(
            self._current_scene or self._quick_execution_detail.current_scene()
        )
        pending_evidence = self._pending_object_preflight_evidence
        if pending_evidence is not None and object_preflight_evidence_is_current(
            pending_evidence,
            scene,
            doc_path,
        ):
            evidence = pending_evidence
        else:
            evidence = self._build_object_preflight_preview_evidence()
        preview_payload = evidence.to_payload()
        source_revision = evidence.source_revision
        confirmation_key = evidence.canonical_key
        confirmation_digest = evidence.evidence_digest
        findings_count = int(preview_payload.get("findings_count") or 0)
        module_skips_count = int(preview_payload.get("module_skips_count") or 0)
        if findings_count <= 0 and module_skips_count <= 0:
            self._pending_object_preflight_confirmation_key = ""
            self._pending_object_preflight_evidence = None
            self._confirmed_object_preflight_source_revision = source_revision
            self._confirmed_object_preflight_digest = confirmation_digest
            return True

        result_state = self._execution_adapter.build_result_state(
            terminal_payload={
                "status": "success",
                "output_path": "",
                "report_paths": [],
                "failed_count": 0,
                "error_text": "",
                "object_preflight": preview_payload,
            },
        )
        blocking_count = int(preview_payload.get("blocking_findings_count") or 0)
        blocked = bool(preview_payload.get("blocked"))
        if blocking_count > 0 and blocked:
            self._execution.reset_feedback()
            self._quick_execution_detail.set_object_preflight_confirmation(
                result_state,
                blocked=True,
            )
            self._document_execution_detail.set_object_preflight_confirmation(
                result_state,
                blocked=True,
            )
            self._pending_object_preflight_confirmation_key = ""
            self._pending_object_preflight_evidence = None
            self._confirmed_object_preflight_source_revision = ""
            self._confirmed_object_preflight_digest = ""
            self._refresh_quick_execute_card()
            return False

        if (
            confirmation_key
            and self._pending_object_preflight_confirmation_key == confirmation_key
        ):
            self._pending_object_preflight_confirmation_key = ""
            self._pending_object_preflight_evidence = None
            self._confirmed_object_preflight_source_revision = source_revision
            self._confirmed_object_preflight_digest = confirmation_digest
            return True

        if self._quick_execution_detail.has_local_execution_surface():
            self._quick_execution_detail.reset_execution_feedback()
        self._document_execution_detail.reset_execution_feedback()
        self._quick_execution_detail.set_object_preflight_confirmation(
            result_state,
            blocked=False,
        )
        self._document_execution_detail.set_object_preflight_confirmation(
            result_state,
            blocked=False,
        )
        self._pending_object_preflight_confirmation_key = confirmation_key
        self._pending_object_preflight_evidence = (
            evidence if isinstance(evidence, ObjectPreflightEvidence) else None
        )
        self._confirmed_object_preflight_source_revision = ""
        self._confirmed_object_preflight_digest = ""
        self._refresh_quick_execute_card()
        return False

    def _build_object_preflight_preview_payload(self) -> dict[str, object]:

        return self._build_object_preflight_preview_evidence().to_payload()

    def _build_object_preflight_preview_evidence(self) -> ObjectPreflightEvidence:

        doc_path = self._document_paths.selected_existing_document()
        scene = self._quick_execution_detail.execution_scene(
            self._current_scene or self._quick_execution_detail.current_scene()
        )
        return build_object_preflight_evidence(scene, doc_path)

    def _clear_object_preflight_confirmation(self) -> None:

        self._pending_object_preflight_confirmation_key = ""
        self._pending_object_preflight_evidence = None
        self._confirmed_object_preflight_source_revision = ""
        self._confirmed_object_preflight_digest = ""

    def _apply_theme(self) -> None:

        apply_workbench_v2_shell_theme(
            self,
            self._nav_rail,
            self._detail_scroll,
            self._detail_container,
            theme=get_theme(),
        )
