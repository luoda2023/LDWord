from __future__ import annotations

import logging

from src.config.library import get_scene_entry, get_template_entry, load_template_from_library
from src.config.scene import SceneWorkspace

from src.config.template import TemplateConfig

from src.qt_api import QFileDialog, QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget, Qt

from src.shared.ui import DynamicNavigationRail

from src.shared.ui.theme import bind_theme, get_theme

from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter

from src.ui.adapters.workbench_strategy_adapter import WorkbenchStrategyAdapter

from src.ui.base_panel import BasePanel

from .config_management_detail import ConfigManagementDetail

from .detail_controller import WorkbenchDetailController

from .document_path_controller import WorkbenchDocumentPathController

from .execution_controller import WorkbenchExecutionController

from .execution_session_controller import WorkbenchExecutionSessionController

from .feature_detail_panes import (

    CitationDetailPane,

    CleanupDetailPane,

    ContentDataDetailPane,

    ExecutionHistoryDetailPane,

    FormulaDetailPane,

    PageElementsDetailPane,

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

        self._execution_session = WorkbenchExecutionSessionController(

            resolve_document_path=self._resolve_document_path_for_execution,

            worker_parent=self,

        )

        self._strategy_card = StrategyCard(self)

        self._strategy_state = self._strategy_adapter.build_summary(None, None)

    def _build_shell_widgets(self) -> None:

        self._layout = QHBoxLayout(self)

        self._layout.setContentsMargins(0, 0, 0, 0)

        self._layout.setSpacing(0)

        self._nav_rail = DynamicNavigationRail(parent=self)

        self._nav_rail.setObjectName("wb_v2_navigation")

        self._nav_rail.setFixedWidth(260)

        self._layout.addWidget(self._nav_rail)

        self._detail_scroll = QScrollArea(self)

        self._detail_scroll.setObjectName("wb_v2_detail")

        self._detail_scroll.setWidgetResizable(True)

        self._detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self._detail_scroll.setFrameShape(QFrame.NoFrame)

        self._detail_container = QWidget(self._detail_scroll)

        self._detail_container.setObjectName("wb_v2_detail_content")

        self._detail_layout = QVBoxLayout(self._detail_container)

        self._detail_layout.setContentsMargins(16, 10, 16, 16)

        self._detail_layout.setSpacing(0)

        self._detail_scroll.setWidget(self._detail_container)

        self._layout.addWidget(self._detail_scroll, 1)

    def _build_detail_panes(self) -> None:

        self._quick_execution_detail = QuickExecutionDetail(self)

        self._config_management_detail = ConfigManagementDetail(self._strategy_card, self.bridge, self)

        # Feature detail panes mapped to new capability group IDs
        self._table_chart_detail = TableChartDetailPane(self)

        self._page_elements_detail = PageElementsDetailPane(self)

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

            "page_elements": self._page_elements_detail,

            "formula": self._formula_detail,

            "citation": self._citation_detail,

            "cleanup": self._cleanup_detail,

            "content_fill": self._content_fill_detail,

            "heading_numbering": self._heading_numbering_detail,

            "quick_fill": self._quick_fill_detail,

        }

        self._details = WorkbenchDetailController(

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

        self._config_management_detail.set_current_scene(self._current_scene)

        if self._current_template is not None:

            self._config_management_detail.set_current_template(self._current_template)

    def _connect_signals(self) -> None:

        self.bridge.template_changed.connect(self.on_template_changed)

        self.bridge.scene_changed.connect(self.on_scene_changed)

        self.bridge.document_loaded.connect(self._on_document_loaded)

        self.bridge.scene_dirty_changed.connect(self._on_scene_dirty_changed)

        self.bridge.template_dirty_changed.connect(self._on_template_dirty_changed)

        self._nav_rail.card_selected.connect(self._on_card_selected)

        self._quick_execution_detail.feature_toggled.connect(self._on_feature_toggled)

        self._quick_execution_detail.feature_config_requested.connect(self._open_feature_card)

        self._quick_execution_detail.summary_changed.connect(self._on_quick_summary_changed)

        self._quick_execution_detail.binding_changed.connect(self._on_quick_binding_changed)

        self._quick_execution_detail.scene_config_changed.connect(self._on_quick_scene_config_changed)

        self._quick_execution_detail.execute_requested.connect(self._execute_requested)

        self._quick_execution_detail.cancel_requested.connect(self._cancel_execution)

        self._quick_execution_detail.document_selected.connect(self._on_quick_detail_document_selected)

        self._config_management_detail.summary_changed.connect(self._refresh_config_management_card)

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

        self._quick_execution_detail.set_strategy_context(

            template_name=self._strategy_state.template_label,

            scene_name=self._strategy_state.name if self._strategy_state.source_type == "scene" else "",

            strict_mode=self._strategy_state.strict_mode if self._strategy_state.source_type == "scene" else None,

        )

    def _sync_strategy_state(self) -> None:

        self._strategy_state = self._strategy_adapter.build_summary(self._current_template, self._current_scene)

        self._strategy_card.set_state(self._strategy_state)

    def _on_quick_detail_document_selected(self, file_path: str) -> None:

        selected = self._document_paths.accept_detail_selection(file_path)

        if not selected:

            return

        self.bridge.document_loaded.emit(selected)

    def _on_feature_toggled(self, _feature_id: str, _enabled: bool) -> None:

        self._sync_dynamic_cards()

    def _on_quick_summary_changed(self) -> None:

        self._sync_strategy_state()

        self._refresh_quick_execute_card()

        self._refresh_config_management_card()

    def _on_quick_binding_changed(self, scene: SceneWorkspace, template_id: str) -> None:

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

        self._current_scene = scene

        scene_entry = get_scene_entry(scene.scene_id)

        self.bridge.set_current_scene(

            scene,

            config_id=scene.scene_id,

            path=str(scene_entry.path) if scene_entry is not None else "",

            source="library" if scene_entry is not None else "builtin",

        )

        self.bridge.mark_scene_dirty()

    def _sync_dynamic_cards(self) -> None:

        self._navigation.sync_dynamic_cards()

    def _open_feature_card(self, feature_id: str) -> None:

        self._navigation.open_feature_card(feature_id)

    def _on_card_selected(self, card_id: str) -> None:

        self._details.show_detail(card_id)

        self._current_detail = self._details.current_detail

    def _on_document_loaded(self, file_path: str) -> None:

        if self._document_paths.apply_loaded_document(file_path) is None:

            return

        self._refresh_quick_execute_card()

    def on_template_changed(self, template: TemplateConfig) -> None:

        self._current_template = template

        self._config_management_detail.set_current_template(template)

        self.bridge.clear_template_dirty()

        self._refresh_strategy_summary()

        self._refresh_fixed_cards()

    def on_scene_changed(self, scene: SceneWorkspace) -> None:

        self._current_scene = scene

        self._config_management_detail.set_current_scene(scene)

        self._refresh_strategy_summary()

        self._refresh_fixed_cards()

    def _on_scene_dirty_changed(self, dirty: bool) -> None:

        self._scene_dirty = bool(dirty)

        self._refresh_fixed_cards()

    def _on_template_dirty_changed(self, dirty: bool) -> None:

        self._template_dirty = bool(dirty)

        self._refresh_fixed_cards()

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

        build = self._execution_session.build_worker(

            template=self._current_template,

            scene=self._current_scene,

            session_overrides=self._quick_execution_detail.runtime_template_overrides(),

        )

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

        self._execution_session.start_worker(worker)

    def _clear_execution_worker(self) -> None:

        self._execution_session.clear_active_worker()

    def apply_execution_result(self, result) -> None:

        self._execution.apply_execution_result(result)

    def _apply_theme(self) -> None:

        apply_workbench_v2_shell_theme(

            self,

            self._nav_rail,

            self._detail_scroll,

            self._detail_container,

            theme=get_theme(),

        )

WorkbenchPanelV2 = WorkbenchPanel
