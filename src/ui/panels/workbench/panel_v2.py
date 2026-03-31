from __future__ import annotations

from pathlib import Path

from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.qt_api import QFileDialog, QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget, Qt
from src.shared.ui import DynamicNavigationRail, NavigationCard
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from src.ui.adapters.workbench_strategy_adapter import WorkbenchStrategyAdapter
from src.ui.base_panel import BasePanel

from .config_management_detail import ConfigManagementDetail
from .execution_worker import ExecutionWorker
from .feature_detail_panes import (
    ExecutionHistoryDetailPane,
    HeadingNumberingDetailPane,
    ModuleControlDetailPane,
    OutputSettingsDetailPane,
    QuickFillDetailPane,
)
from .panel import _ThreadedExecutionHandle, _WorkbenchProductionRunner
from .quick_execution_detail import QuickExecutionDetail
from .state import ExecutionResultState
from .strategy_card import StrategyCard


class WorkbenchPanelV2(BasePanel):
    """Workbench V2 with a master-detail layout."""

    FIXED_CARD_ORDER = ("quick_execute", "config_management")
    FEATURE_CARD_ORDER = (
        "heading_numbering",
        "quick_fill",
        "module_control",
        "output_settings",
        "execution_history",
    )
    FEATURE_CARD_TITLES = {
        "heading_numbering": "\u6807\u9898\u7f16\u53f7",
        "quick_fill": "\u5185\u5bb9\u586b\u5145",
        "module_control": "\u6a21\u5757\u63a7\u5236",
        "output_settings": "\u8f93\u51fa\u8bbe\u7f6e",
        "execution_history": "\u6267\u884c\u5386\u53f2",
    }

    def shutdown_active_execution(self, timeout_ms: int | None = 1000) -> bool:
        worker = getattr(self, "_execution_worker", None)
        if worker is None:
            return True

        request_cancel = getattr(worker, "request_cancel", None)
        if callable(request_cancel):
            try:
                request_cancel()
            except Exception:
                pass

        shutdown = getattr(worker, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown(timeout_ms=timeout_ms)
            except TypeError:
                try:
                    if timeout_ms is None:
                        shutdown()
                    else:
                        shutdown(int(timeout_ms))
                except Exception:
                    pass
            except Exception:
                pass

        thread = getattr(worker, "_thread", None)
        is_running = getattr(thread, "isRunning", None) if thread is not None else None
        if not callable(is_running):
            is_running = getattr(worker, "isRunning", None)

        if callable(is_running):
            try:
                return not bool(is_running())
            except Exception:
                return False
        return True

    def _setup_ui(self) -> None:
        self.setObjectName("WorkbenchPanelV2")
        self._navigation_cards: dict[str, NavigationCard] = {}
        self._dynamic_cards: set[str] = set()
        self._execution_adapter = WorkbenchExecutionAdapter()
        self._strategy_adapter = WorkbenchStrategyAdapter()
        self._current_template: TemplateConfig | None = None
        self._current_scene: SceneWorkspace | None = None
        self._cached_document_path = ""
        self._execution_worker = None
        self._execution_result_received = False
        self._last_execution_pick_cancelled = False
        self._history_runtime_modules: list[str] = []
        self._strategy_card = StrategyCard(self)
        self._strategy_state = self._strategy_adapter.build_summary(None, None)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(16)

        self._nav_rail = DynamicNavigationRail(parent=self)
        self._nav_rail.setObjectName("wb_v2_navigation")
        self._nav_rail.setFixedWidth(220)
        self._layout.addWidget(self._nav_rail)

        self._detail_scroll = QScrollArea(self)
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._detail_scroll.setFrameShape(QFrame.NoFrame)

        self._detail_container = QWidget(self._detail_scroll)
        self._detail_layout = QVBoxLayout(self._detail_container)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_layout.setSpacing(0)
        self._detail_scroll.setWidget(self._detail_container)
        self._layout.addWidget(self._detail_scroll, 1)

        self._quick_execution_detail = QuickExecutionDetail(self)
        self._config_management_detail = ConfigManagementDetail(self._strategy_card, self)
        self._heading_numbering_detail = HeadingNumberingDetailPane(self)
        self._quick_fill_detail = QuickFillDetailPane(self)
        self._module_control_detail = ModuleControlDetailPane(self)
        self._output_settings_detail = OutputSettingsDetailPane(self)
        self._execution_history_detail = ExecutionHistoryDetailPane(self)
        self._current_detail: QWidget | None = None
        self._detail_map = {
            "quick_execute": self._quick_execution_detail,
            "config_management": self._config_management_detail,
            "heading_numbering": self._heading_numbering_detail,
            "quick_fill": self._quick_fill_detail,
            "module_control": self._module_control_detail,
            "output_settings": self._output_settings_detail,
            "execution_history": self._execution_history_detail,
        }

        self._create_navigation_cards()
        self._refresh_strategy_summary()
        self._refresh_fixed_cards()
        self._sync_dynamic_cards()
        self._nav_rail.select_card("quick_execute")

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _create_navigation_cards(self) -> None:
        self._add_navigation_card("quick_execute", "\u5feb\u901f\u6267\u884c")
        self._add_navigation_card("config_management", "\u914d\u7f6e\u7ba1\u7406")

    def _add_navigation_card(self, card_id: str, title: str) -> NavigationCard:
        card = NavigationCard(card_id, title, parent=self._nav_rail)
        self._navigation_cards[card_id] = card
        self._nav_rail.add_card(card_id, card)
        return card

    def _connect_signals(self) -> None:
        self.bridge.template_changed.connect(self.on_template_changed)
        self.bridge.scene_changed.connect(self.on_scene_changed)
        self.bridge.document_loaded.connect(self._on_document_loaded)
        self._nav_rail.card_selected.connect(self._on_card_selected)
        self._quick_execution_detail.feature_toggled.connect(self._on_feature_toggled)
        self._quick_execution_detail.feature_config_requested.connect(self._open_feature_card)
        self._quick_execution_detail.summary_changed.connect(self._refresh_quick_execute_card)
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

    def _update_navigation_card(self, card_id: str, snapshot: dict[str, str]) -> None:
        card = self._navigation_cards.get(card_id)
        if card is None:
            return
        card.set_subtitle(snapshot.get("subtitle", ""))
        card.set_badge(snapshot.get("badge_text", ""), snapshot.get("badge_variant", "neutral"))

    def _refresh_fixed_cards(self) -> None:
        self._refresh_quick_execute_card()
        self._refresh_config_management_card()

    def _build_quick_execute_snapshot(self) -> dict[str, str]:
        fallback = self._quick_execution_detail.navigation_snapshot()
        document_label = Path(self._cached_document_path).name if self._cached_document_path else "\u672a\u9009\u62e9\u6587\u6863"
        strategy_name = self._strategy_state.name if self._strategy_state.source_type == "scene" else self._strategy_state.template_label
        strategy_name = str(strategy_name or "").strip() or self._quick_execution_detail.navigation_snapshot().get("subtitle", "")
        enabled_count = len(self._quick_execution_detail.enabled_features())
        if self._execution_worker is not None:
            badge_text = "\u6267\u884c\u4e2d"
            badge_variant = "info"
        else:
            badge_text = fallback.get("badge_text", "")
            badge_variant = fallback.get("badge_variant", "neutral")
        return {
            "subtitle": f"{document_label} · {strategy_name or '\u9ed8\u8ba4\u6d41\u7a0b'}",
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def _build_config_management_snapshot(self) -> dict[str, str]:
        fallback = self._config_management_detail.navigation_snapshot()
        if self._strategy_state.source_type == "scene":
            subtitle = f"{self._strategy_state.name} · {self._strategy_state.enabled_module_count} \u4e2a\u6a21\u5757"
            badge_text = "\u573a\u666f"
            badge_variant = "success"
        elif self._strategy_state.source_type == "template":
            subtitle = self._strategy_state.template_label
            badge_text = "\u6a21\u677f"
            badge_variant = "neutral"
        else:
            return fallback
        return {
            "subtitle": subtitle,
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def _refresh_quick_execute_card(self) -> None:
        self._update_navigation_card("quick_execute", self._build_quick_execute_snapshot())
        self._sync_dynamic_cards()

    def _refresh_config_management_card(self) -> None:
        self._update_navigation_card("config_management", self._build_config_management_snapshot())

    def _refresh_strategy_summary(self) -> None:
        self._strategy_state = self._strategy_adapter.build_summary(self._current_template, self._current_scene)
        self._strategy_card.set_state(self._strategy_state)
        self._quick_execution_detail.set_strategy_context(
            template_name=self._strategy_state.template_label,
            scene_name=self._strategy_state.name if self._strategy_state.source_type == "scene" else "",
            strict_mode=self._strategy_state.strict_mode if self._strategy_state.source_type == "scene" else None,
        )

    def _on_quick_detail_document_selected(self, file_path: str) -> None:
        cleaned = str(file_path or "").strip()
        if not cleaned:
            return
        self._cached_document_path = cleaned
        self.bridge.document_loaded.emit(cleaned)
        self._refresh_quick_execute_card()

    def _on_feature_toggled(self, _feature_id: str, _enabled: bool) -> None:
        self._sync_dynamic_cards()

    def _sync_dynamic_cards(self) -> None:
        selected_card_id = self._nav_rail.selected_card_id()

        for feature_id in list(self._dynamic_cards):
            self._nav_rail.remove_card(feature_id)
            self._navigation_cards.pop(feature_id, None)
        self._dynamic_cards.clear()

        for feature_id in self.FEATURE_CARD_ORDER:
            if feature_id not in self._quick_execution_detail.enabled_features():
                continue
            card = self._add_navigation_card(feature_id, self.FEATURE_CARD_TITLES[feature_id])
            snapshot = self._quick_execution_detail.feature_navigation_snapshot(feature_id)
            card.set_subtitle(snapshot.get("subtitle", ""))
            card.set_badge(snapshot.get("badge_text", ""), snapshot.get("badge_variant", "neutral"))
            self._dynamic_cards.add(feature_id)

        if selected_card_id in self._navigation_cards:
            self._nav_rail.select_card(selected_card_id)

    def _open_feature_card(self, feature_id: str) -> None:
        if feature_id in self._navigation_cards:
            self._nav_rail.select_card(feature_id)

    def _on_card_selected(self, card_id: str) -> None:
        detail = self._detail_map.get(card_id)
        if detail is None or detail is self._current_detail:
            return

        if self._current_detail is not None:
            self._detail_layout.removeWidget(self._current_detail)
            self._current_detail.hide()

        detail.setParent(self._detail_container)
        self._detail_layout.addWidget(detail)
        detail.show()
        self._current_detail = detail
        self._detail_scroll.verticalScrollBar().setValue(0)

    def _on_document_loaded(self, file_path: str) -> None:
        try:
            resolved = Path(str(file_path or "")).expanduser()
        except Exception:
            return
        if not resolved.exists():
            return
        try:
            self._cached_document_path = str(resolved.resolve())
        except Exception:
            self._cached_document_path = str(resolved)
        self._quick_execution_detail.set_document_path(self._cached_document_path)
        self._refresh_quick_execute_card()

    def on_template_changed(self, template: TemplateConfig) -> None:
        self._current_template = template
        self._refresh_strategy_summary()
        self._refresh_fixed_cards()

    def on_scene_changed(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._refresh_strategy_summary()
        self._refresh_fixed_cards()

    def _execute_requested(self) -> None:
        self._start_execution()

    def _cancel_execution(self) -> None:
        worker = getattr(self, "_execution_worker", None)
        if worker is None:
            return
        request_cancel = getattr(worker, "request_cancel", None)
        if callable(request_cancel):
            request_cancel()

    def _build_execution_worker(self):
        self._last_execution_pick_cancelled = False
        doc_path = self._resolve_document_path_for_execution()
        if doc_path is None:
            self._last_execution_pick_cancelled = True
            return None
        if not doc_path:
            return None

        template = self._current_template or TemplateConfig()
        scene = self._current_scene or SceneWorkspace()
        runner = _WorkbenchProductionRunner(
            doc_path=doc_path,
            template=template,
            scene=scene,
        )
        worker = ExecutionWorker(runner, parent=None)
        return _ThreadedExecutionHandle(worker, parent=self)

    def _resolve_document_path_for_execution(self) -> str | None:
        detail_path = str(self._quick_execution_detail.document_path() or "").strip()
        if detail_path:
            try:
                candidate = Path(detail_path).expanduser()
                if candidate.exists():
                    resolved = str(candidate.resolve())
                    self._cached_document_path = resolved
                    self._quick_execution_detail.set_document_path(resolved)
                    return resolved
            except Exception:
                pass

        cached = str(self._cached_document_path or "").strip()
        if cached:
            try:
                if Path(cached).exists():
                    self._quick_execution_detail.set_document_path(cached)
                    return cached
            except Exception:
                pass

        file_name, _selected = QFileDialog.getOpenFileName(
            self,
            "\u9009\u62e9\u6587\u6863",
            "",
            "Word Documents (*.docx);;All Files (*)",
        )
        file_name = str(file_name or "").strip()
        if not file_name:
            return None
        try:
            path = Path(file_name).expanduser()
            resolved = str(path.resolve()) if path.exists() else str(path)
        except Exception:
            resolved = file_name
        self._cached_document_path = resolved
        self._quick_execution_detail.set_document_path(resolved)
        return resolved

    def _start_execution(self) -> None:
        if self._execution_worker is not None:
            return

        worker = self._build_execution_worker()
        if worker is None:
            if getattr(self, "_last_execution_pick_cancelled", False):
                self._last_execution_pick_cancelled = False
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
        self._execution_result_received = False
        self._wire_execution_worker(worker)
        self._quick_execution_detail.reset_execution_feedback()
        self._reset_execution_history_feedback()
        self._quick_execution_detail.set_execute_enabled(False)
        self._quick_execution_detail.set_execution_progress(
            self._execution_adapter.build_progress_state(
                stage_text="Starting",
                current_step=0,
                total_steps=0,
            )
        )
        self._refresh_quick_execute_card()

        start = getattr(worker, "start", None)
        if callable(start):
            start()
            return

        run = getattr(worker, "run", None)
        if callable(run):
            run()

    def _wire_execution_worker(self, worker) -> None:
        def _connect(signal, handler) -> None:
            connect = getattr(signal, "connect", None)
            if callable(connect):
                connect(handler)

        _connect(getattr(worker, "execution_started", None), self._on_execution_started)
        _connect(getattr(worker, "progress_changed", None), self._on_execution_progress)
        _connect(getattr(worker, "execution_succeeded", None), self._on_execution_succeeded)
        _connect(getattr(worker, "execution_partial", None), self._on_execution_partial)
        _connect(getattr(worker, "execution_failed", None), self._on_execution_failed)
        _connect(getattr(worker, "execution_cancelled", None), self._on_execution_cancelled)
        _connect(getattr(worker, "execution_finished", None), self._on_execution_finished)

    def _on_execution_started(self) -> None:
        progress_state = self._execution_adapter.build_progress_state(
            stage_text="\u5f00\u59cb\u6267\u884c",
            current_step=0,
            total_steps=0,
        )
        self._quick_execution_detail.set_execution_progress(progress_state)
        self._sync_execution_history_progress(progress_state)
        self._refresh_quick_execute_card()

    def _on_execution_progress(self, current_step: int, total_steps: int, stage_text: str) -> None:
        progress_state = self._execution_adapter.build_progress_state(
            stage_text=stage_text,
            current_step=current_step,
            total_steps=total_steps,
        )
        self._quick_execution_detail.set_execution_progress(progress_state)
        self._sync_execution_history_progress(progress_state)
        self._refresh_quick_execute_card()

    def _on_execution_succeeded(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_partial(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_failed(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_cancelled(self) -> None:
        self.apply_execution_result(
            self._execution_adapter.build_result_state(
                status="cancelled",
                output_path="",
                report_paths=[],
                failed_count=0,
                error_text="",
            )
        )

    def _on_execution_finished(self) -> None:
        self._execution_worker = None
        if not self._execution_result_received:
            self._quick_execution_detail.finish_execution()
        self._quick_execution_detail.set_execute_enabled(bool(self._cached_document_path))
        self._refresh_quick_execute_card()

    def apply_execution_result(self, result) -> None:
        if isinstance(result, ExecutionResultState):
            result_state = result
        else:
            payload = dict(result or {})
            result_state = self._execution_adapter.build_result_state(
                status=str(payload.get("status") or "failed"),
                output_path=str(payload.get("output_path") or ""),
                report_paths=list(payload.get("report_paths") or []),
                failed_count=int(payload.get("failed_count") or 0),
                error_text=str(payload.get("error_text") or ""),
            )

        self._quick_execution_detail.set_execution_result(result_state)
        self._sync_execution_history_result(result_state)
        self._execution_result_received = True
        self._refresh_quick_execute_card()

    def _reset_execution_history_feedback(self) -> None:
        self._history_runtime_modules = []
        progress_widget = getattr(self._execution_history_detail, "_progress_widget", None)
        module_list = getattr(self._execution_history_detail, "_module_list", None)
        if progress_widget is not None:
            progress_widget.reset()
        if module_list is not None:
            clear = getattr(module_list, "clear", None)
            if callable(clear):
                clear()
        if hasattr(self._execution_history_detail, "set_summary"):
            self._execution_history_detail.set_summary("\u5f53\u524d\u67e5\u770b\uff1a\u5b8c\u6574\u65e5\u5fd7 · \u6700\u65b0\u8fd0\u884c\u5c1a\u672a\u5f00\u59cb")

    def _sync_execution_history_progress(self, progress_state) -> None:
        stage_text = str(progress_state.stage_text or "\u6267\u884c\u4e2d")
        progress_widget = getattr(self._execution_history_detail, "_progress_widget", None)
        module_list = getattr(self._execution_history_detail, "_module_list", None)
        if progress_widget is None or module_list is None:
            return

        progress_widget.set_progress(progress_state.current_step, progress_state.total_steps, stage_text)
        if stage_text not in self._history_runtime_modules:
            self._history_runtime_modules.append(stage_text)
            add_module = getattr(module_list, "add_module", None)
            if callable(add_module):
                add_module(stage_text, stage_text)
            if len(self._history_runtime_modules) > 1:
                previous = self._history_runtime_modules[-2]
                update_status = getattr(module_list, "update_status", None)
                if callable(update_status):
                    update_status(previous, "completed", 100)
                progress_widget.update_module_status(previous, "completed", 100)
        update_status = getattr(module_list, "update_status", None)
        if callable(update_status):
            update_status(stage_text, "running", progress_state.percent)
        progress_widget.update_module_status(stage_text, "running", progress_state.percent)
        progress_widget.append_log("info", f"\u9636\u6bb5\u66f4\u65b0\uff1a{stage_text}")
        if hasattr(self._execution_history_detail, "set_summary"):
            self._execution_history_detail.set_summary(
                f"\u5f53\u524d\u67e5\u770b\uff1a\u5b8c\u6574\u65e5\u5fd7 · \u6700\u65b0\u8fd0\u884c\uff1a{stage_text}"
            )

    def _sync_execution_history_result(self, result_state: ExecutionResultState) -> None:
        progress_widget = getattr(self._execution_history_detail, "_progress_widget", None)
        module_list = getattr(self._execution_history_detail, "_module_list", None)
        if progress_widget is None or module_list is None:
            return

        success = result_state.status in {"success", "partial_success"}
        if self._history_runtime_modules:
            final_stage = self._history_runtime_modules[-1]
            final_status = "completed" if success else ("failed" if result_state.status == "failed" else "cancelled")
            final_progress = 100 if success else 0
            update_status = getattr(module_list, "update_status", None)
            if callable(update_status):
                update_status(final_stage, final_status, final_progress)
            progress_widget.update_module_status(final_stage, final_status, final_progress)
        progress_widget.set_completed(success, {"success_count": 1 if success else 0})
        progress_widget.append_log("info", result_state.summary)
        if result_state.output_path:
            progress_widget.append_log("info", f"\u8f93\u51fa\uff1a{result_state.output_path}")
        if result_state.error_text:
            progress_widget.append_log("error", result_state.error_text)
        if hasattr(self._execution_history_detail, "set_summary"):
            self._execution_history_detail.set_summary(
                f"\u5f53\u524d\u67e5\u770b\uff1a\u5b8c\u6574\u65e5\u5fd7 · {result_state.summary}"
            )

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(f"background: {t.bg_window};")
        self._detail_scroll.setStyleSheet(
            f"""
            QScrollArea {{
                border: none;
                background: {t.bg_window};
            }}
            QWidget {{
                background: transparent;
            }}
            """
        )
