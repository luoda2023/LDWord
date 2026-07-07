from __future__ import annotations

import json
import logging
from dataclasses import asdict

from src.config.library import get_scene_entry, get_template_entry, load_template_from_library
from src.config.scene import SceneWorkspace

from src.config.template import TemplateConfig

from src.qt_api import QFileDialog, QWidget

from src.shared.ui import DetailPaneController, MasterDetailShell

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.engine.object_preflight import (
    inspect_docx_package,
    object_preflight_module_skips,
)

from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from src.ui.adapters.workbench_issue_navigation import (
    WorkbenchIssueNavigationProjection,
    workbench_issue_navigation_for_target,
)
from src.ui.adapters.field_display_names import (
    field_display_context,
    navigation_issue_hint,
)

from src.ui.adapters.workbench_strategy_adapter import WorkbenchStrategyAdapter

from src.ui.base_panel import BasePanel
from src.ui.bridge import navigation_intent_value
from src.ui.panel_registry import PANEL_SPECS

from .config_management_detail import ConfigManagementDetail


from .document_path_controller import WorkbenchDocumentPathController

from .execution_controller import WorkbenchExecutionController

from .execution_session_controller import WorkbenchExecutionSessionController

from .feature_detail_panes import (

    CitationDetailPane,

    CleanupDetailPane,

    ContentDataDetailPane,

    ExecutionHistoryDetailPane,

    FormulaDetailPane,

    TableChartDetailPane,

)

from .navigation_controller import WorkbenchNavigationController

from .quick_execution_detail import QuickExecutionDetail

from .scene_presets import (
    CAPABILITY_FEATURE_CARD_DEFINITIONS,
    CAPABILITY_FEATURE_CARD_ORDER,
)

from .strategy_card import StrategyCard

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


def _decode_profile_repair_candidate(payload: str) -> tuple[str, str, dict[str, object]]:
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

        "config_management": ("\u914d\u7f6e\u7ba1\u7406", "save"),

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

        self._scene_dirty = self.bridge.is_scene_dirty()

        self._template_dirty = self.bridge.is_template_dirty()
        self._ignore_own_scene_changed = False
        self._skip_next_scene_dirty_recheck = False

        self._execution_session = WorkbenchExecutionSessionController(

            resolve_document_path=self._resolve_document_path_for_execution,

            worker_parent=self,

        )
        self._pending_object_preflight_confirmation_key = ""

        self._strategy_card = StrategyCard(self)

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

        self._config_management_detail = ConfigManagementDetail(self._strategy_card, self.bridge, self)

        # Feature detail panes mapped to new capability group IDs
        self._table_chart_detail = TableChartDetailPane(self)

        self._formula_detail = FormulaDetailPane(self)

        self._citation_detail = CitationDetailPane(self)

        self._cleanup_detail = CleanupDetailPane(self)

        self._content_fill_detail = ContentDataDetailPane(self)

        self._heading_numbering_detail = self._table_chart_detail

        self._quick_fill_detail = self._content_fill_detail

        self._execution_history_detail = ExecutionHistoryDetailPane(self)

        detail_map = {

            "quick_execute": self._quick_execution_detail,

            "config_management": self._config_management_detail,

            "table_chart": self._table_chart_detail,

            "formula": self._formula_detail,

            "citation": self._citation_detail,

            "cleanup": self._cleanup_detail,

            "content_fill": self._content_fill_detail,

            "heading_numbering": self._heading_numbering_detail,

            "quick_fill": self._quick_fill_detail,

        }

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

        self._navigation = WorkbenchNavigationController(

            self._nav_rail,

            self._quick_execution_detail,

            self._config_management_detail,

            card_definitions=self.CARD_DEFINITIONS,

            feature_card_order=self.FEATURE_CARD_ORDER,

        )

        self._navigation_cards = self._navigation.navigation_cards

        self._dynamic_cards = self._navigation.dynamic_cards

        self._execution = WorkbenchExecutionController(

            self._execution_adapter,

            self._quick_execution_detail,

            self._execution_history_detail,

            refresh_quick_execute_card=self._refresh_quick_execute_card,

            clear_execution_worker=self._clear_execution_worker,

            has_ready_document=self._document_paths.has_selected_document,

        )

    def _create_navigation_cards(self) -> None:

        self._navigation.add_fixed_cards()

    def _bootstrap_strategy_context(self) -> None:

        if self.bridge.current_scene() is not None:

            self._current_scene = self.bridge.current_scene()

        else:

            self._current_scene = self._quick_execution_detail.current_scene()

            scene_entry = get_scene_entry(self._current_scene.scene_id)

            self.bridge.set_current_scene(

                self._current_scene,

                config_id=self._current_scene.scene_id,

                path=str(scene_entry.path) if scene_entry is not None else "",

                source="library" if scene_entry is not None else "builtin",

                emit_signal=False,

            )

        if self.bridge.current_template() is not None:

            self._current_template = self.bridge.current_template()

        else:

            template_id = self._quick_execution_detail.current_template_id()

            if template_id:

                template_entry = get_template_entry(template_id)

                self._current_template = load_template_from_library(template_id)

                self.bridge.set_current_template(

                    self._current_template,

                    config_id=template_id,

                    path=str(template_entry.path) if template_entry is not None else "",

                    source="library" if template_entry is not None else "builtin",

                    emit_signal=False,

                )

        self._quick_execution_detail.set_scene_context(self._current_scene)

        self._config_management_detail.set_current_scene(self._current_scene)

        self._quick_execution_detail.set_template_context(self._current_template)

        if self._current_template is not None:

            self._config_management_detail.set_current_template(self._current_template)

        material_context = self.bridge.current_material_context()
        self._content_fill_detail.set_material_context(material_context, emit_signal=False)
        self._quick_execution_detail.set_material_context(material_context)

    def _connect_signals(self) -> None:

        self.bridge.template_changed.connect(self.on_template_changed)

        self.bridge.scene_changed.connect(self.on_scene_changed)

        self.bridge.material_context_changed.connect(self._on_material_context_changed)

        self.bridge.document_loaded.connect(self._on_document_loaded)

        self.bridge.scene_dirty_changed.connect(self._on_scene_dirty_changed)

        self.bridge.template_dirty_changed.connect(self._on_template_dirty_changed)

        self._nav_rail.card_selected.connect(self._on_card_selected)

        self._quick_execution_detail.feature_toggled.connect(self._on_feature_toggled)

        self._quick_execution_detail.feature_config_requested.connect(self._open_feature_card)

        self._quick_execution_detail.material_repair_requested.connect(self._open_material_repair_target)

        self._quick_execution_detail.issue_repair_requested.connect(self._open_issue_repair_target)

        self._quick_execution_detail.summary_changed.connect(self._on_quick_summary_changed)

        self._quick_execution_detail.binding_changed.connect(self._on_quick_binding_changed)

        self._quick_execution_detail.scene_config_changed.connect(self._on_quick_scene_config_changed)

        self._quick_execution_detail.execute_requested.connect(self._execute_requested)

        self._quick_execution_detail.cancel_requested.connect(self._cancel_execution)

        self._quick_execution_detail.document_selected.connect(self._on_quick_detail_document_selected)

        self._config_management_detail.summary_changed.connect(self._refresh_config_management_card)

        self._content_fill_detail.material_context_changed.connect(self._sync_material_context_from_detail)

        self._nav_rail.select_card(self._nav_rail.selected_card_id() or "quick_execute")

    def closeEvent(self, event) -> None:

        if not self.shutdown_active_execution(timeout_ms=1000):

            event.ignore()

            return

        super().closeEvent(event)

    def _refresh_fixed_cards(self) -> None:

        self._navigation.refresh_fixed_cards(

            cached_document_path=self._document_paths.cached_document_path,

            strategy_state=self._strategy_state,

            execution_worker=self._execution_worker,

            scene_dirty=self._scene_dirty,

            template_dirty=self._template_dirty,

        )

    def _refresh_quick_execute_card(self) -> None:

        self._navigation.refresh_quick_execute_card(

            cached_document_path=self._document_paths.cached_document_path,

            strategy_state=self._strategy_state,

            execution_worker=self._execution_worker,

        )

    def _refresh_config_management_card(self) -> None:

        self._navigation.refresh_config_management_card(

            strategy_state=self._strategy_state,

            scene_dirty=self._scene_dirty,

            template_dirty=self._template_dirty,

        )

    def _refresh_strategy_summary(self) -> None:

        self._sync_strategy_state()

        template_id = self.bridge.current_template_id()
        if not template_id and self._current_scene is not None:
            template_id = self._current_scene.template_id

        self._quick_execution_detail.set_strategy_context(

            template_name=self._strategy_state.template_label,

            template_id=template_id,

            scene_name=self._strategy_state.name if self._strategy_state.source_type == "scene" else "",

            strict_mode=self._strategy_state.strict_mode if self._strategy_state.source_type == "scene" else None,

        )

    def _sync_strategy_state(self) -> None:

        self._strategy_state = self._strategy_adapter.build_summary(self._current_template, self._current_scene)

        self._strategy_card.set_state(self._strategy_state)

    def _on_quick_detail_document_selected(self, file_path: str) -> None:

        self._clear_object_preflight_confirmation()

        selected = self._document_paths.accept_detail_selection(file_path)

        if not selected:

            return

        self.bridge.set_current_document_path(selected)

    def _on_feature_toggled(self, _feature_id: str, _enabled: bool) -> None:

        self._sync_dynamic_cards()

    def _on_quick_summary_changed(self) -> None:

        self._sync_strategy_state()

        self._refresh_quick_execute_card()

        self._refresh_config_management_card()

    def _on_quick_binding_changed(self, scene: SceneWorkspace, template_id: str) -> None:

        self._clear_object_preflight_confirmation()

        self._current_scene = scene

        scene_entry = get_scene_entry(scene.scene_id)

        self.bridge.clear_scene_dirty()

        self.bridge.set_current_scene(

            scene,

            config_id=scene.scene_id,

            path=str(scene_entry.path) if scene_entry is not None else "",

            source="library" if scene_entry is not None else "builtin",

        )

        template_id = str(template_id or "").strip()

        if template_id:

            template_entry = get_template_entry(template_id)

            try:

                template = load_template_from_library(template_id)

            except Exception as exc:

                logger.warning(
                    "Workbench quick binding ignored template load failure for %s: %s",
                    template_id,
                    exc,
                    exc_info=exc,
                )

                template = None

            if template is not None:

                self.bridge.clear_template_dirty()

                self.bridge.set_current_template(

                    template,

                    config_id=template_id,

                    path=str(template_entry.path) if template_entry is not None else "",

                    source="library" if template_entry is not None else "builtin",

                )

    def _on_quick_scene_config_changed(self, scene: SceneWorkspace) -> None:

        self._clear_object_preflight_confirmation()

        self._current_scene = scene

        scene_entry = get_scene_entry(scene.scene_id)

        self._ignore_own_scene_changed = True
        try:
            self.bridge.set_current_scene(

                scene,

                config_id=scene.scene_id,

                path=str(scene_entry.path) if scene_entry is not None else "",

                source="library" if scene_entry is not None else "builtin",

            )
        finally:
            self._ignore_own_scene_changed = False

        if not self.bridge.is_scene_dirty():
            self._skip_next_scene_dirty_recheck = True
        self.bridge.mark_scene_dirty()

    def _sync_dynamic_cards(self) -> None:

        self._navigation.sync_dynamic_cards()

    def _open_feature_card(self, feature_id: str) -> None:

        self._navigation.open_feature_card(feature_id)

    def _emit_panel_navigation(
        self,
        panel_id: str,
        *,
        card_id: str = "",
        issue_type: str = "",
        issue_key: str = "",
        issue_context: dict[str, str] | None = None,
    ) -> None:
        index = _panel_index(panel_id)
        if index >= 0:
            self.bridge.navigate_to_panel.emit(index)
        context = dict(issue_context or {})
        active_issue_id = str(
            context.get("active_issue_id")
            or context.get("issue_item_id")
            or ""
        ).strip()
        issue_display_name = str(
            context.get("issue_target_label_with_group")
            or context.get("issue_target_label")
            or ""
        ).strip()
        if not issue_display_name and issue_type in {
            "template_style_field",
            "scene_style_field",
        }:
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
                "return_card_id": "quick_execute",
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
                issue_context=self._quick_execution_detail.current_issue_navigation_context(),
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

        if normalized_type in {"asset", "field", "question_figure_item"} and normalized_key:

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

            profile_id, profile_name, candidate = _decode_profile_repair_candidate(normalized_key)

            self.bridge.request_material_profile_repair_candidate(
                profile_id,
                profile_name,
                candidate,
            )

            if self._navigate_issue_projection(projection):
                return

        if projection.action_kind == "material_profile_target":

            profile_id, profile_name, repair_key = _decode_profile_repair_target(normalized_key)

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
        active_issue_id = str(
            navigation_intent_value(intent, "active_issue_id", "") or ""
        ).strip()
        payload = navigation_intent_value(intent, "payload", {}) or {}
        if not active_issue_id and isinstance(payload, dict):
            active_issue_id = str(
                payload.get("active_issue_id")
                or payload.get("issue_item_id")
                or ""
            ).strip()
        if card_id == "quick_execute" and active_issue_id:
            self._quick_execution_detail.set_active_issue(active_issue_id)

    def _on_card_selected(self, card_id: str) -> None:

        self._details.show_detail(card_id)

        self._current_detail = self._details.current_detail

    def _on_document_loaded(self, file_path: str) -> None:

        self._clear_object_preflight_confirmation()

        if self._document_paths.apply_loaded_document(file_path) is None:

            return

        self._refresh_quick_execute_card()

    def on_template_changed(self, template: TemplateConfig) -> None:

        self._clear_object_preflight_confirmation()

        self._current_template = template

        self._quick_execution_detail.set_template_context(template)

        self._config_management_detail.set_current_template(template)

        self.bridge.clear_template_dirty()

        self._refresh_strategy_summary()

        self._refresh_fixed_cards()

    def on_scene_changed(self, scene: SceneWorkspace) -> None:

        self._clear_object_preflight_confirmation()

        self._current_scene = scene

        self._config_management_detail.set_current_scene(scene)

        if getattr(self, "_ignore_own_scene_changed", False):
            return

        self._quick_execution_detail.set_scene_context(scene)

        self._refresh_strategy_summary()

        self._refresh_fixed_cards()

    def _on_scene_dirty_changed(self, dirty: bool) -> None:

        self._scene_dirty = bool(dirty)

        if dirty:
            bridge_skip_recheck = (
                self.bridge.consume_scene_dirty_recheck_suppressed()
                if hasattr(self.bridge, "consume_scene_dirty_recheck_suppressed")
                else False
            )
            if getattr(self, "_skip_next_scene_dirty_recheck", False) or bridge_skip_recheck:
                self._skip_next_scene_dirty_recheck = False
            else:
                self._quick_execution_detail.recheck_current_context()
        else:
            self._skip_next_scene_dirty_recheck = False

        self._refresh_fixed_cards()

    def _on_template_dirty_changed(self, dirty: bool) -> None:

        self._template_dirty = bool(dirty)

        if dirty:
            self._quick_execution_detail.recheck_current_context()

        self._refresh_fixed_cards()

    def _on_material_context_changed(self, context) -> None:

        self._content_fill_detail.set_material_context(context, emit_signal=False)
        self._quick_execution_detail.set_material_context(context)

    def _sync_material_context_from_detail(self, context) -> None:

        self._quick_execution_detail.set_material_context(context)
        self.bridge.set_current_material_context(context)

    def _execute_requested(self) -> None:

        self._start_execution()

    def _cancel_execution(self) -> None:

        self._execution.cancel_execution(self._execution_worker)

    def _resolve_document_path_for_execution(self) -> str | None:

        return self._document_paths.resolve_execution_document()

    def _pick_document_path(self) -> str | None:

        file_name, _selected = QFileDialog.getOpenFileName(

            self,

            "\u9009\u62e9\u6587\u6863",

            "",

            "Word Documents (*.docx);;All Files (*)",

        )

        cleaned = str(file_name or "").strip()

        return cleaned or None

    def _start_execution(self) -> None:

        if not self._ensure_object_preflight_confirmed():
            return

        build = self._execution_session.build_worker(

            template=self._current_template,

            scene=self._current_scene,

            session_overrides=self._quick_execution_detail.runtime_template_overrides(),

            material_context=self._content_fill_detail.material_context(),

        )

        self._start_worker_from_build(build)

    def _start_batch_execution(self) -> None:

        selection = self.bridge.current_material_batch_selection()

        if not selection.archive.profiles:

            self._quick_execution_detail.reset_execution_feedback()

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

        if not self._ensure_object_preflight_confirmed():
            return

        build = self._execution_session.build_batch_worker(

            template=self._current_template,

            scene=self._current_scene,

            archive=selection.archive,

            profile_ids=selection.profile_ids,

            base_output_dir=self._quick_execution_detail.custom_output_dir() or None,

            output_dir_template=selection.output_dir_template,

            session_overrides=self._quick_execution_detail.runtime_template_overrides(),

            base_context=selection.base_context,

        )

        self._start_worker_from_build(build)

    def _start_worker_from_build(self, build) -> None:

        if build.already_running:

            return

        worker = build.worker

        if worker is None:

            if build.cancelled:

                return

            self._quick_execution_detail.reset_execution_feedback()

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

        self._execution.prepare_worker(worker)

        self._clear_object_preflight_confirmation()

        self._execution_session.start_worker(worker)

    def _clear_execution_worker(self) -> None:

        self._execution_session.clear_active_worker()

    def apply_execution_result(self, result) -> None:

        self._execution.apply_execution_result(result)

    def _ensure_object_preflight_confirmed(self) -> bool:

        preview_payload = self._build_object_preflight_preview_payload()
        findings_count = int(preview_payload.get("findings_count") or 0)
        module_skips_count = int(preview_payload.get("module_skips_count") or 0)
        if findings_count <= 0 and module_skips_count <= 0:
            self._clear_object_preflight_confirmation()
            return True

        result_state = self._execution_adapter.build_result_state(
            status="success",
            output_path="",
            report_paths=[],
            failed_count=0,
            error_text="",
            object_preflight=preview_payload,
        )
        confirmation_key = self._object_preflight_confirmation_key(preview_payload)
        blocking_count = int(preview_payload.get("blocking_findings_count") or 0)
        blocked = bool(preview_payload.get("blocked"))
        if blocking_count > 0 and blocked:
            self._quick_execution_detail.reset_execution_feedback()
            self._quick_execution_detail.set_object_preflight_confirmation(
                result_state,
                blocked=True,
            )
            self._pending_object_preflight_confirmation_key = ""
            self._refresh_quick_execute_card()
            return False

        if self._pending_object_preflight_confirmation_key == confirmation_key:
            self._pending_object_preflight_confirmation_key = ""
            return True

        self._quick_execution_detail.reset_execution_feedback()
        self._quick_execution_detail.set_object_preflight_confirmation(
            result_state,
            blocked=False,
        )
        self._pending_object_preflight_confirmation_key = confirmation_key
        self._refresh_quick_execute_card()
        return False

    def _build_object_preflight_preview_payload(self) -> dict[str, object]:

        doc_path = self._document_paths.selected_existing_document()
        scene = self._current_scene or self._quick_execution_detail.current_scene()
        compliance = getattr(scene, "compliance_profile", None)
        policy = getattr(compliance, "object_preflight", None)
        if not doc_path or policy is None or not bool(getattr(policy, "enabled", True)):
            return {}

        result = inspect_docx_package(doc_path, policy)
        module_skips = object_preflight_module_skips(result.findings, policy)
        failure_policy = str(getattr(compliance, "failure_policy", "") or "").strip()
        blocked = bool(result.blocking_findings) and (
            bool(getattr(scene, "strict_mode", True)) or failure_policy == "block"
        )
        return {
            "enabled": True,
            "source_path": str(doc_path or ""),
            "preservation_mode": str(getattr(policy, "preservation_mode", "") or ""),
            "scan_targets": _string_list(getattr(policy, "scan_targets", []) or []),
            "block_on": _string_list(getattr(policy, "block_on", []) or []),
            "skip_high_risk_modules": bool(
                getattr(policy, "skip_high_risk_modules", True)
            ),
            "skip_modules_by_finding": {
                str(kind): _string_list(modules)
                for kind, modules in dict(
                    getattr(policy, "skip_modules_by_finding", {}) or {}
                ).items()
            },
            "findings_count": len(result.findings),
            "findings": [asdict(finding) for finding in result.findings],
            "blocking_findings_count": len(result.blocking_findings),
            "blocked": blocked,
            "module_skips_count": len(module_skips),
            "module_skips": list(module_skips.values()),
        }

    def _object_preflight_confirmation_key(self, payload: dict[str, object]) -> str:

        doc_path = str(payload.get("source_path") or "").strip()
        if not doc_path:
            doc_path = self._quick_execution_detail.document_path() or ""
        if not doc_path:
            doc_path = self._document_paths.cached_document_path
        scene_id = str(getattr(self._current_scene, "scene_id", "") or "")
        return json.dumps(
            {
                "doc_path": doc_path,
                "scene_id": scene_id,
                "object_preflight": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def _clear_object_preflight_confirmation(self) -> None:

        self._pending_object_preflight_confirmation_key = ""

    def _apply_theme(self) -> None:

        apply_workbench_v2_shell_theme(

            self,

            self._nav_rail,

            self._detail_scroll,

            self._detail_container,

            theme=get_theme(),

        )


def _string_list(values) -> list[str]:

    return [
        str(item or "").strip()
        for item in list(values or [])
        if str(item or "").strip()
    ]


WorkbenchPanelV2 = WorkbenchPanel
