from __future__ import annotations

import copy
import json
import logging
from importlib import import_module

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
from src.config.scene_surface_registry import (
    scene_uses_exam_paper_surface,
    scene_uses_official_document_surface,
)
from src.config.template import TemplateConfig
from src.qt_api import QWidget
from src.shared.ui import DetailPaneController, MasterDetailShell, Toast
from src.shared.ui.theme import bind_theme, get_theme
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

from .document_path_controller import WorkbenchDocumentPathController
from .document_scope_controller import WorkbenchDocumentScopeController
from .execution_controller import WorkbenchExecutionController
from .execution_session_controller import WorkbenchExecutionSessionController
from .feature_detail_panes import (
    CitationDetailPane,
    CleanupDetailPane,
    ContentDataDetailPane,
    FormulaDetailPane,
    TableChartDetailPane,
)
from .navigation_controller import WorkbenchNavigationController
from .quick_execution_detail import QuickExecutionDetail
from .styles import apply_workbench_v2_shell_theme

logger = logging.getLogger(__name__)


class _RecentRunPanelModuleProxy:
    def _open_artifact_file(self, path: str, *, fragment: str = "") -> bool:
        from . import recent_run_panel

        return recent_run_panel._open_artifact_file(path, fragment=fragment)


recent_run_panel_module = _RecentRunPanelModuleProxy()


def _panel_index(panel_id: str) -> int:
    target = str(panel_id or "").strip()
    for index, spec in enumerate(PANEL_SPECS):
        if spec.id == target:
            return index
    return -1


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


class WorkbenchPanel(BasePanel):
    """Master-detail workbench panel."""

    FEATURE_CARD_ORDER = CAPABILITY_FEATURE_CARD_ORDER

    CARD_DEFINITIONS = {
        "quick_execute": ("\u5feb\u901f\u6267\u884c", "zap"),
        "batch_generate": ("批量生成", "layers"),
        "material_suite_generate": ("成套生成", "package"),
    }
    CARD_DEFINITIONS.update(CAPABILITY_FEATURE_CARD_DEFINITIONS)

    @property
    def _execution_worker(self):

        return self._execution_session.active_worker

    @_execution_worker.setter
    def _execution_worker(self, worker) -> None:

        self._execution_session.set_active_worker(worker)

    def shutdown_active_execution(self, timeout_ms: int | None = 1000) -> bool:
        return self._execution_session.shutdown_active_execution(timeout_ms=timeout_ms)

    def _setup_ui(self) -> None:

        self.setObjectName("WorkbenchPanel")

        self._initialize_panel_state()

        self._build_shell_widgets()

        self._build_detail_panes()

        self._build_controllers()

        self._create_navigation_cards()

        self._bootstrap_strategy_context()

        self._refresh_strategy_summary()

        self._sync_dynamic_cards()

        self._refresh_fixed_cards()

        self._nav_rail.select_card("quick_execute")

        self._apply_theme()

        bind_theme(self, self._apply_theme)

    def _initialize_panel_state(self) -> None:

        self._execution_adapter = WorkbenchExecutionAdapter()

        self._strategy_adapter = WorkbenchStrategyAdapter()

        self._current_template: TemplateConfig | None = None

        self._current_scene: SceneWorkspace | None = None

        self._ignore_own_scene_changed = False
        self._skip_next_scene_dirty_recheck = False

        self._execution_session = WorkbenchExecutionSessionController(
            resolve_document_path=self._resolve_document_path_for_execution,
            worker_parent=self,
        )
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

        self._quick_execution_detail = QuickExecutionDetail(self)
        if hasattr(self._quick_execution_detail, "set_work_mode"):
            self._quick_execution_detail.set_work_mode(
                self.bridge.current_work_mode_id()
            )

        # Batch generation is a fixed Workbench destination, but loading its
        # specialist surface must not expand the application entrypoint graph.
        batch_module = import_module("src.ui.panels.workbench.batch_generation_detail")
        self._batch_generation_detail = batch_module.BatchGenerationDetail(self)
        self._batch_generation_detail.set_work_mode(self.bridge.current_work_mode_id())
        suite_detail_module = import_module(
            "src.ui.panels.workbench.material_suite_generation_detail"
        )
        self._suite_generation_detail = (
            suite_detail_module.MaterialSuiteGenerationDetail(self)
        )

        # Feature detail panes mapped to new capability group IDs
        self._table_chart_detail = TableChartDetailPane(self)

        self._formula_detail = FormulaDetailPane(self)

        self._citation_detail = CitationDetailPane(self)

        self._cleanup_detail = CleanupDetailPane(self)

        self._content_fill_detail = ContentDataDetailPane(self)

        self._heading_numbering_detail = self._table_chart_detail

        self._quick_fill_detail = self._content_fill_detail

        detail_map = {
            "quick_execute": self._quick_execution_detail,
            "table_chart": self._table_chart_detail,
            "formula": self._formula_detail,
            "citation": self._citation_detail,
            "cleanup": self._cleanup_detail,
            "content_fill": self._content_fill_detail,
            "heading_numbering": self._heading_numbering_detail,
            "quick_fill": self._quick_fill_detail,
        }
        if self._batch_generation_detail is not None:
            detail_map["batch_generate"] = self._batch_generation_detail
        detail_map["material_suite_generate"] = self._suite_generation_detail

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
            scene=lambda: (
                self._current_scene or self._quick_execution_detail.current_scene()
            ),
            status_detail=self._quick_execution_detail,
        )

        self._navigation = WorkbenchNavigationController(
            self._nav_rail,
            self._quick_execution_detail,
            self._batch_generation_detail,
            self._suite_generation_detail,
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
            refresh_navigation=self._refresh_fixed_cards,
            clear_execution_worker=self._clear_execution_worker,
            has_ready_document=self._document_paths.has_selected_document,
        )
        suite_controller_module = import_module(
            "src.ui.panels.workbench.material_suite_workbench_controller"
        )
        self._suite_generation_flow = (
            suite_controller_module.MaterialSuiteWorkbenchController(
                self._suite_generation_detail,
                self._execution,
                start_worker=self._start_worker_from_build,
                active_worker=lambda: self._execution_worker,
                cancel_execution=self._cancel_execution,
                refresh_navigation=self._refresh_fixed_cards,
                publish_material_selection=(
                    self.bridge.set_current_material_batch_selection
                ),
                open_material_workspace=lambda: self._emit_panel_navigation("assets"),
                worker_parent=self,
            )
        )

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
                self._document_scope.start_scan(selected_document)

        material_context = self.bridge.current_material_context()
        self._content_fill_detail.set_material_context(
            material_context, emit_signal=False
        )
        self._quick_execution_detail.set_material_context(material_context)
        if hasattr(self.bridge, "current_material_preview_snapshot"):
            self._quick_execution_detail.set_material_preview_snapshot(
                self.bridge.current_material_preview_snapshot()
            )
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_source_document(
                self.bridge.current_document_path()
            )
            self._batch_generation_detail.set_scene_context(self._current_scene)
        self._quick_execution_detail.set_official_document_type_id(
            self.bridge.current_official_document_type_id()
        )
        self._document_scope.recheck()
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_material_batch_selection(
                self.bridge.current_material_batch_selection()
            )
        self._suite_generation_flow.apply_material_selection(
            self.bridge.current_material_batch_selection()
        )

    def _connect_signals(self) -> None:

        self.bridge.template_changed.connect(self.on_template_changed)

        self.bridge.scene_changed.connect(self.on_scene_changed)

        if hasattr(self.bridge, "work_mode_changed"):
            self.bridge.work_mode_changed.connect(self._on_work_mode_changed)

        self.bridge.material_context_changed.connect(self._on_material_context_changed)
        if hasattr(self.bridge, "material_preview_snapshot_changed"):
            self.bridge.material_preview_snapshot_changed.connect(
                self._on_material_preview_snapshot_changed
            )
        self.bridge.official_document_type_changed.connect(
            self._on_official_document_type_changed
        )
        self.bridge.material_batch_selection_changed.connect(
            self._on_material_batch_selection_changed
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

        self._quick_execution_detail.summary_changed.connect(
            self._on_quick_summary_changed
        )

        self._quick_execution_detail.binding_changed.connect(
            self._on_quick_binding_changed
        )
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.binding_changed.connect(
                self._on_quick_binding_changed
            )

        self._quick_execution_detail.scene_config_changed.connect(
            self._on_quick_scene_config_changed
        )
        self._quick_execution_detail.official_document_type_changed.connect(
            self._sync_official_document_type_from_quick
        )

        self._quick_execution_detail.execute_requested.connect(self._execute_requested)
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.source_document_selected.connect(
                self._on_batch_detail_document_selected
            )
            self._batch_generation_detail.execute_requested.connect(
                self._start_batch_execution
            )
            self._batch_generation_detail.retry_requested.connect(
                self._start_failed_batch_retry
            )
            self._batch_generation_detail.cancel_requested.connect(
                self._cancel_execution
            )
            self._batch_generation_detail.summary_changed.connect(
                self._refresh_batch_generate_card
            )

        self._quick_execution_detail.cancel_requested.connect(self._cancel_execution)

        self._quick_execution_detail.object_preflight_cancel_requested.connect(
            self._cancel_object_preflight_confirmation
        )

        self._quick_execution_detail.document_selected.connect(
            self._on_quick_detail_document_selected
        )
        self._quick_execution_detail.document_scope_review_requested.connect(
            self._document_scope.review
        )

        self._content_fill_detail.material_context_changed.connect(
            self._sync_material_context_from_detail
        )
        self._quick_execution_detail.material_context_changed.connect(
            self._sync_material_context_from_quick_detail
        )

        self._nav_rail.select_card(self._nav_rail.selected_card_id() or "quick_execute")

    def _current_work_mode_id(self) -> str:
        if hasattr(self.bridge, "current_work_mode_id"):
            return str(self.bridge.current_work_mode_id() or "").strip()
        return "custom"

    def _on_work_mode_changed(self, mode) -> None:
        mode_id = (
            str(getattr(mode, "mode_id", "") or "").strip()
            or self._current_work_mode_id()
        )
        self._document_scope.reset_decisions()
        if hasattr(self._quick_execution_detail, "set_work_mode"):
            self._quick_execution_detail.set_work_mode(mode_id)
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_work_mode(mode_id)
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

    def _refresh_batch_generate_card(self) -> None:
        self._navigation.refresh_batch_generate_card()

    def _refresh_strategy_summary(self) -> None:

        self._sync_strategy_state()

        template_id = self.bridge.current_template_id()
        if not template_id and self._current_scene is not None:
            template_id = self._current_scene.template_id

        self._quick_execution_detail.set_strategy_context(
            template_name=self._strategy_state.template_label,
            template_id=template_id,
            scene_name=self._strategy_state.name
            if self._strategy_state.source_type == "scene"
            else "",
            strict_mode=self._strategy_state.strict_mode
            if self._strategy_state.source_type == "scene"
            else None,
        )
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_strategy_context(
                plan_label=(
                    self._strategy_state.name
                    if self._strategy_state.source_type == "scene"
                    else self._strategy_state.scene_label
                ),
                template_label=self._strategy_state.template_label,
                template_id=template_id,
            )

    def _sync_strategy_state(self) -> None:

        self._strategy_state = self._strategy_adapter.build_summary(
            self._current_template, self._current_scene
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
            self._quick_execution_detail.set_scene_context(current_bridge_scene)
            if self._batch_generation_detail is not None:
                self._batch_generation_detail.set_scene_context(current_bridge_scene)
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

        if feature_id in self._detail_map and feature_id not in self._navigation_cards:
            self._quick_execution_detail.set_feature_enabled(feature_id, True)
            self._sync_dynamic_cards()
        self._navigation.open_feature_card(feature_id)

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

        self._open_feature_card(projection.feature_card_id or "content_fill")

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

        self._open_feature_card(projection.feature_card_id or "content_fill")

    def handle_navigation_intent(self, intent) -> None:
        card_id = str(navigation_intent_value(intent, "card_id", "") or "").strip()
        if card_id:
            self._nav_rail.select_card(card_id)

    def _on_card_selected(self, card_id: str) -> None:

        self._details.show_detail(card_id)

        self._current_detail = self._details.current_detail

    def _on_document_loaded(self, file_path: str) -> None:

        self._clear_object_preflight_confirmation()

        selected_document = self._document_paths.apply_loaded_document(file_path)
        if selected_document is None:
            return

        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_source_document(selected_document)
        self._document_scope.start_scan(selected_document, force=True)
        self._refresh_quick_execute_card()
        self._refresh_batch_generate_card()

    def on_template_changed(self, template: TemplateConfig) -> None:

        self._clear_object_preflight_confirmation()

        self._current_template = template

        self._quick_execution_detail.set_template_context(template)

        self._refresh_strategy_summary()

        self._refresh_fixed_cards()

    def on_scene_changed(self, scene: SceneWorkspace) -> None:

        self._clear_object_preflight_confirmation()

        self._current_scene = scene

        if getattr(self, "_ignore_own_scene_changed", False):
            return

        self._quick_execution_detail.set_scene_context(scene)
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_scene_context(scene)
        self._document_scope.recheck()

        self._refresh_strategy_summary()

        self._refresh_fixed_cards()

    def _on_scene_dirty_changed(self, dirty: bool) -> None:

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

    def _on_material_context_changed(self, context) -> None:

        self._content_fill_detail.set_material_context(context, emit_signal=False)
        if not getattr(self, "_syncing_quick_material_context", False):
            self._quick_execution_detail.set_material_context(context)

    def _on_material_preview_snapshot_changed(self, snapshot) -> None:
        self._quick_execution_detail.set_material_preview_snapshot(snapshot)

    def _on_official_document_type_changed(self, document_type_id: str) -> None:
        self._clear_object_preflight_confirmation()
        self._quick_execution_detail.set_official_document_type_id(document_type_id)
        self._refresh_quick_execute_card()

    def _sync_official_document_type_from_quick(self, document_type_id: str) -> None:
        self._clear_object_preflight_confirmation()
        self.bridge.set_current_official_document_type_id(document_type_id)

    def _on_material_batch_selection_changed(self, selection) -> None:
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_material_batch_selection(selection)
            self._refresh_batch_generate_card()
        self._suite_generation_flow.apply_material_selection(selection)

    def _sync_material_context_from_detail(self, context) -> None:

        self._quick_execution_detail.set_material_context(context)
        self.bridge.set_current_material_context(context)

    def _sync_material_context_from_quick_detail(self, context) -> None:
        self._syncing_quick_material_context = True
        try:
            self._content_fill_detail.set_material_context(context, emit_signal=False)
            self.bridge.set_current_material_context(context)
        finally:
            self._syncing_quick_material_context = False

    def _execute_requested(self) -> None:

        self._start_execution()

    def _cancel_execution(self) -> None:

        self._execution.cancel_execution(self._execution_worker)

    def _cancel_object_preflight_confirmation(self) -> None:
        self._clear_object_preflight_confirmation()
        self._quick_execution_detail.reset_execution_feedback()
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
        source_dependent_gate = scene_uses_exam_paper_surface(
            self._current_scene,
            mode_id=effective_mode_id,
        )
        material_gate = None
        if not source_dependent_gate:
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
        if source_dependent_gate:
            material_gate = (
                self._quick_execution_detail.current_execution_gate_decision()
            )
            if not material_gate.can_run:
                self._quick_execution_detail.recheck_current_context(force=True)
                return
        assert material_gate is not None
        build = self._execution_session.build_worker(
            template=self._current_template,
            scene=self._current_scene,
            session_overrides=self._quick_execution_detail.runtime_template_overrides(),
            # The bridge is the authoritative workbench material state.
            # Quick execution and the legacy content-data editor both publish
            # here; execution must not depend on whichever widget refreshed last.
            material_context=self.bridge.current_material_context(),
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
            output_root=self._quick_execution_detail.custom_output_dir(),
            material_gate_confirmed=material_gate.requires_confirmation,
            expected_input_revision=(self._confirmed_object_preflight_source_revision),
            object_preflight_confirmation_digest=(
                self._confirmed_object_preflight_digest
            ),
            document_structure_evidence=self._document_scope.evidence,
            document_scope_decisions=self._document_scope.decisions,
        )

        self._start_worker_from_build(build)

    def _start_batch_execution(self) -> None:
        if self._batch_generation_detail is None or self._execution_worker is not None:
            return
        set_feedback_target = getattr(self._execution, "set_feedback_target", None)
        if callable(set_feedback_target):
            set_feedback_target("batch")

        selection = self.bridge.current_material_batch_selection()
        self._batch_generation_detail.set_work_mode(self._current_work_mode_id())
        self._batch_generation_detail.set_scene_context(self._current_scene)
        self._batch_generation_detail.set_material_batch_selection(selection)
        self._batch_generation_detail.set_runtime_template_overrides(
            self._quick_execution_detail.runtime_template_overrides()
        )

        if not selection.archive.profiles:
            self._execution.reset_feedback()

            self.apply_execution_result(
                {
                    "status": "failed",
                    "output_path": "",
                    "report_paths": [],
                    "failed_count": 0,
                    "error_text": "No material profiles selected for batch execution",
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
            self._refresh_batch_generate_card()
            return

        source_document_required = not (
            str(selection.source_kind or "").strip() == "official_document_table"
            and scene_uses_official_document_surface(
                self._current_scene,
                mode_id=self._current_work_mode_id(),
            )
        )
        if source_document_required:
            if self._resolve_document_path_for_execution() is None:
                return
            if not self._document_scope.ensure_confirmed():
                return
            if not self._ensure_object_preflight_confirmed():
                return
        else:
            self._clear_object_preflight_confirmation()

        build = self._execution_session.build_batch_worker(
            template=self._current_template,
            scene=self._current_scene,
            archive=selection.archive,
            profile_ids=selection.profile_ids,
            base_output_dir=self._batch_generation_detail.output_dir() or None,
            output_dir_template=selection.output_dir_template,
            session_overrides=self._batch_generation_detail.runtime_template_overrides(),
            base_context=selection.base_context,
            source_kind=selection.source_kind,
            source_path=selection.source_path,
            item_metadata=selection.item_metadata,
            mode_id=self._current_work_mode_id(),
            plan_id=self.bridge.current_scene_id(),
            plan_path=self.bridge.current_scene_path(),
            plan_source_type=self.bridge.current_scene_source_type(),
            template_id=self.bridge.current_template_id(),
            template_path=self.bridge.current_template_path(),
            template_source_type=self.bridge.current_template_source_type(),
            material_gate_confirmed=material_gate.requires_confirmation,
            expected_input_revision=(self._confirmed_object_preflight_source_revision),
            object_preflight_confirmation_digest=(
                self._confirmed_object_preflight_digest
            ),
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

        source_selection = self.bridge.current_material_batch_selection()
        self._batch_generation_detail.set_work_mode(self._current_work_mode_id())
        self._batch_generation_detail.set_scene_context(self._current_scene)
        self._batch_generation_detail.set_material_batch_selection(source_selection)
        self._batch_generation_detail.set_runtime_template_overrides(
            self._quick_execution_detail.runtime_template_overrides()
        )
        failed_profile_ids = self._batch_generation_detail.failed_batch_profile_ids()
        batch_history_module = import_module(
            "src.shared.engine.official_document_batch_history"
        )
        retry_selection = (
            batch_history_module.build_official_document_batch_retry_selection(
                source_selection,
                failed_profile_ids,
                retry_of_run_id=(self._batch_generation_detail.last_batch_run_id()),
                attempt_number=(
                    self._batch_generation_detail.next_batch_attempt_number()
                ),
            )
        )

        if not retry_selection.profile_ids:
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

        issue_module = import_module("src.ui.adapters.workbench_material_issues")
        retry_gate = issue_module.material_batch_readiness_gate_decision(
            self._current_scene,
            retry_selection,
        )
        if not retry_gate.can_run:
            self.apply_execution_result(
                {
                    "status": "failed",
                    "output_path": "",
                    "report_paths": [],
                    "failed_count": len(retry_selection.profile_ids),
                    "error_text": "；".join(retry_gate.blocking_reasons),
                }
            )
            return

        source_document_required = not (
            str(retry_selection.source_kind or "").strip() == "official_document_table"
            and scene_uses_official_document_surface(
                self._current_scene,
                mode_id=self._current_work_mode_id(),
            )
        )
        if source_document_required:
            if self._resolve_document_path_for_execution() is None:
                return
            if not self._document_scope.ensure_confirmed():
                return
            if not self._ensure_object_preflight_confirmed():
                return
        else:
            self._clear_object_preflight_confirmation()

        build = self._execution_session.build_batch_worker(
            template=self._current_template,
            scene=self._current_scene,
            archive=retry_selection.archive,
            profile_ids=retry_selection.profile_ids,
            base_output_dir=self._batch_generation_detail.output_dir() or None,
            output_dir_template=retry_selection.output_dir_template,
            session_overrides=self._batch_generation_detail.runtime_template_overrides(),
            base_context=retry_selection.base_context,
            source_kind=retry_selection.source_kind,
            source_path=retry_selection.source_path,
            item_metadata=retry_selection.item_metadata,
            retry_of_run_id=self._batch_generation_detail.last_batch_run_id(),
            attempt_number=self._batch_generation_detail.next_batch_attempt_number(),
            mode_id=self._current_work_mode_id(),
            plan_id=self.bridge.current_scene_id(),
            plan_path=self.bridge.current_scene_path(),
            plan_source_type=self.bridge.current_scene_source_type(),
            template_id=self.bridge.current_template_id(),
            template_path=self.bridge.current_template_path(),
            template_source_type=self.bridge.current_template_source_type(),
            material_gate_confirmed=retry_gate.requires_confirmation,
            expected_input_revision=(self._confirmed_object_preflight_source_revision),
            object_preflight_confirmation_digest=(
                self._confirmed_object_preflight_digest
            ),
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
        scene = self._current_scene or self._quick_execution_detail.current_scene()
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

        self._quick_execution_detail.reset_execution_feedback()
        self._quick_execution_detail.set_object_preflight_confirmation(
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
        scene = self._current_scene or self._quick_execution_detail.current_scene()
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
