from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QThread

from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig

from src.config.resolver import resolve_config
from src.modules.registry import create_all_modules
from src.pipeline.runner import Pipeline
from src.pipeline.scheduler import select_enabled_modules
from src.qt_api import QFileDialog, QHBoxLayout, QObject, QVBoxLayout, Signal, QWidget
from src.report_writer import write_json_report, write_markdown_report
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from src.ui.adapters.workbench_strategy_adapter import WorkbenchStrategyAdapter
from src.ui.base_panel import BasePanel

from .capability_grid import CapabilityGrid
from .command_bar import TaskCommandBar
from .execution_center import ExecutionCenter
from .execution_worker import ExecutionWorker
from .heading_quick_card import HeadingQuickCard
from .quick_fill_card import QuickFillCard
from .recent_run_panel import RecentRunPanel
from .state import CurrentTaskState, ExecutionProgressState, ReadinessState
from .styles import build_workbench_stylesheet
from .strategy_card import StrategyCard


class _WorkbenchProductionRunner:
    """Panel-owned production runner that wraps the pipeline primitives."""

    def __init__(
        self,
        *,
        doc_path: str,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
    ) -> None:
        self.doc_path = str(doc_path or "")
        self._template = template
        self._scene = scene

    def run(self, progress_cb, cancel_check):
        input_path = Path(self.doc_path)
        output_dir = input_path.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        template = self._template or TemplateConfig()
        scene = self._scene or SceneWorkspace()
        config = resolve_config(template, scene)

        modules = create_all_modules()
        enabled, _auto_pruned = select_enabled_modules(modules, config.is_module_enabled)

        t0 = time.perf_counter()
        pipeline = Pipeline(
            modules=enabled,
            config=config,
            output_dir=str(output_dir),
            output_suffix="_formatted",
            progress_callback=progress_cb,
            cancel_check=cancel_check,
        )
        result = pipeline.execute(str(input_path))
        elapsed = time.perf_counter() - t0

        status = getattr(result, "status", "failed") or "failed"
        if status == "cancelled":
            return {"status": "cancelled"}

        failed_items = list(getattr(result, "failed_items", []) or [])
        failed_count = len(failed_items)

        if not getattr(result, "success", False):
            return {
                "status": "failed",
                "output_path": "",
                "report_paths": [],
                "failed_count": failed_count,
                "error_text": str(getattr(result, "error", "") or ""),
            }

        output_path = ""
        output_paths = getattr(result, "output_paths", None)
        if isinstance(output_paths, dict):
            output_path = str(output_paths.get("final") or "")

        report_paths: list[str] = []
        if output_path:
            report_json = output_dir / f"{input_path.stem}_changes.json"
            write_json_report(
                result,
                input_path=input_path,
                output_path=Path(output_path),
                report_path=report_json,
                elapsed=elapsed,
                modules_enabled=len(enabled),
                modules_total=len(modules),
            )
            report_paths.append(str(report_json))

            report_md = output_dir / f"{input_path.stem}_changes.md"
            write_markdown_report(
                result,
                input_path=input_path,
                report_path=report_md,
                elapsed=elapsed,
                modules_enabled=len(enabled),
                modules_total=len(modules),
            )
            report_paths.append(str(report_md))

        return {
            "status": str(status),
            "output_path": output_path,
            "report_paths": report_paths,
            "failed_count": failed_count,
            "error_text": str(getattr(result, "error", "") or ""),
        }


class _ThreadedExecutionHandle(QObject):
    """Execution handle that runs an ExecutionWorker on a QThread.

    Exposes the same signals as ExecutionWorker + start()/request_cancel().
    """

    progress_changed = Signal(int, int, str)
    execution_started = Signal()
    execution_succeeded = Signal(object)
    execution_partial = Signal(object)
    execution_failed = Signal(object)
    execution_cancelled = Signal()
    execution_finished = Signal()

    def __init__(self, worker: ExecutionWorker, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._thread = QThread(self)

        # Forward worker signals to this handle so the panel can keep using
        # the same lifecycle wiring.
        self._worker.progress_changed.connect(self.progress_changed.emit)
        self._worker.execution_started.connect(self.execution_started.emit)
        self._worker.execution_succeeded.connect(self.execution_succeeded.emit)
        self._worker.execution_partial.connect(self.execution_partial.emit)
        self._worker.execution_failed.connect(self.execution_failed.emit)
        self._worker.execution_cancelled.connect(self.execution_cancelled.emit)
        self._worker.execution_finished.connect(self.execution_finished.emit)

        # Thread lifecycle: run when started, quit when finished.
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.execution_finished.connect(self._thread.quit)

        # Cleanup: ensure we don't leak the worker/thread/handle after a run completes.
        # Note: deleteLater() is the safest Qt-side cleanup API for QObjects.
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self.deleteLater)

    def start(self) -> None:
        self._thread.start()

    def request_cancel(self) -> None:
        self._worker.request_cancel()

    def shutdown(self, timeout_ms: int | None = 1000) -> None:
        """Best-effort shutdown for panel teardown while a run may be active.

        Contract:
        - always request cancellation
        - if the thread is (or may be) running: quit and wait up to timeout_ms
        """
        try:
            self.request_cancel()
        except Exception:
            pass

        thread = getattr(self, "_thread", None)
        if thread is None:
            return

        is_running = getattr(thread, "isRunning", None)
        try:
            running = bool(is_running()) if callable(is_running) else True
        except Exception:
            running = True

        if not running:
            return

        quit_thread = getattr(thread, "quit", None)
        if callable(quit_thread):
            try:
                quit_thread()
            except Exception:
                pass

        wait_thread = getattr(thread, "wait", None)
        if callable(wait_thread):
            try:
                if timeout_ms is None:
                    wait_thread()
                else:
                    wait_thread(int(timeout_ms))
            except TypeError:
                # Some test doubles or bindings may not accept the timeout param.
                try:
                    wait_thread()
                except Exception:
                    pass
            except Exception:
                pass


class WorkbenchPanel(BasePanel):
    """Dedicated Workbench panel implementation."""
    heading_advanced_requested = Signal()

    def shutdown_active_execution(self, timeout_ms: int | None = 1000) -> bool:
        """Attempt to stop any active execution owned by this panel.

        Returns:
            True: no active execution, or shutdown succeeded.
            False: shutdown timed out and the execution still appears to be running.
        """
        worker = getattr(self, "_execution_worker", None)
        if worker is None:
            return True

        request_cancel = getattr(worker, "request_cancel", None)
        if callable(request_cancel):
            try:
                request_cancel()
            except Exception:
                # Continue with shutdown attempts even if cancel can't be requested.
                pass

        shutdown = getattr(worker, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown(timeout_ms=timeout_ms)
            except TypeError:
                # Some implementations may not accept a keyword arg.
                try:
                    if timeout_ms is None:
                        shutdown()
                    else:
                        shutdown(int(timeout_ms))
                except Exception:
                    pass
            except Exception:
                # Still try to detect running state below.
                pass

        # Prefer checking a threaded handle's thread state (QThread.isRunning).
        thread = getattr(worker, "_thread", None)
        is_running = getattr(thread, "isRunning", None) if thread is not None else None
        if not callable(is_running):
            is_running = getattr(worker, "isRunning", None)

        if callable(is_running):
            try:
                return not bool(is_running())
            except Exception:
                return False

        # Non-threaded executions can't be observed reliably; treat best-effort cancel as success.
        return True

    def _setup_ui(self) -> None:
        self.setObjectName("WorkbenchPanel")
        self._root_layout = QVBoxLayout(self)

        self._command_bar = TaskCommandBar(self)
        self._root_layout.addWidget(self._command_bar)

        self._middle_container = QWidget(self)
        self._middle_layout = QHBoxLayout(self._middle_container)
        self._left_column = QWidget(self._middle_container)
        self._left_layout = QVBoxLayout(self._left_column)
        self._right_column = QWidget(self._middle_container)
        self._right_layout = QVBoxLayout(self._right_column)

        self._strategy_adapter = WorkbenchStrategyAdapter()
        self._strategy_card = StrategyCard(self._left_column)
        self._strategy_card.setObjectName("wb_strategy_card")
        self._capability_grid = CapabilityGrid(self._left_column)
        self._heading_quick_card = HeadingQuickCard(self.bridge, self._capability_grid)
        self._capability_grid.add_card(self._heading_quick_card, 0, 0)
        self._quick_fill_card = QuickFillCard(self.bridge, self._capability_grid)
        self._capability_grid.add_card(self._quick_fill_card, 0, 1)

        self._left_layout.addWidget(self._strategy_card)
        self._left_layout.addWidget(self._capability_grid)

        self._execution_center = ExecutionCenter(self._right_column)
        self._execution_center.setObjectName("wb_execution_center")
        self._right_layout.addWidget(self._execution_center)

        self._middle_layout.addWidget(self._left_column, 7)
        self._middle_layout.addWidget(self._right_column, 3)
        self._root_layout.addWidget(self._middle_container, 1)

        self._recent_run_panel = RecentRunPanel(self)
        self._recent_run_panel.setObjectName("wb_recent_run")
        self._root_layout.addWidget(self._recent_run_panel)

        self._current_template: TemplateConfig | None = None
        self._current_scene: SceneWorkspace | None = None

        # Execution slice ownership (Task 5): panel owns the adapter + current worker reference.
        self._execution_adapter = WorkbenchExecutionAdapter()
        self._execution_worker = None
        self._last_task_state = CurrentTaskState()
        self._last_readiness_state = ReadinessState()
        self._execution_result_received = False
        self._cached_document_path: str = ""
        self._last_execution_pick_cancelled = False

        # Minimal shipped behavior: default-ready execution state.
        # The user can pick a document on-demand when they click Run.
        self.set_current_task_state(
            CurrentTaskState(
                document_label=CurrentTaskState().document_label,
                strategy_label="默认策略",
                ready=True,
                status_text="Ready",
            )
        )

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_strategy_summary(self, template: TemplateConfig | None, scene: SceneWorkspace | None) -> None:
        self._current_template = template
        self._current_scene = scene
        state = self._strategy_adapter.build_summary(self._current_template, self._current_scene)
        self._strategy_card.set_state(state)

    def _connect_signals(self) -> None:
        self.bridge.template_changed.connect(self.on_template_changed)
        self.bridge.scene_changed.connect(self.on_scene_changed)
        self.bridge.document_loaded.connect(self._on_document_loaded)
        self._heading_quick_card.advanced_requested.connect(self.heading_advanced_requested.emit)
        self._execution_center.execute_requested.connect(self._execute_requested)
        self._execution_center.cancel_requested.connect(self._cancel_execution)
        self._command_bar._run_button.clicked.connect(self._execute_requested)

    def closeEvent(self, event) -> None:
        """Ensure active threaded executions are torn down if the panel is closed/destroyed."""
        if not self.shutdown_active_execution(timeout_ms=1000):
            event.ignore()
            return
        super().closeEvent(event)

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
        self._sync_document_label_from_path(self._cached_document_path)

    def _sync_document_label_from_path(self, file_path: str) -> None:
        """Keep the command bar document label in sync with the chosen path."""
        try:
            name = Path(str(file_path or "")).name
        except Exception:
            name = str(file_path or "").strip()
        if not name:
            return

        current = self._last_task_state
        if current.document_label == name:
            return

        self.set_current_task_state(
            CurrentTaskState(
                document_label=name,
                strategy_label=current.strategy_label,
                ready=current.ready,
                status_text=current.status_text,
            )
        )

    def on_template_changed(self, template: TemplateConfig) -> None:
        self._current_template = template
        self.set_strategy_summary(self._current_template, self._current_scene)

    def on_scene_changed(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self.set_strategy_summary(self._current_template, self._current_scene)

    def set_current_task_state(self, state: CurrentTaskState) -> None:
        self._last_task_state = state
        self._command_bar.set_state(state)
        self._last_readiness_state = ReadinessState(ready=state.ready, label=state.status_text, reasons=[])
        self._execution_center.set_readiness(self._last_readiness_state)
        if self._execution_worker is not None:
            self._command_bar._run_button.setEnabled(False)
            self._execution_center._execute_button.setEnabled(False)

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
        # ExecutionWorker must not have a parent if we want to move it to a QThread.
        worker = ExecutionWorker(runner, parent=None)
        return _ThreadedExecutionHandle(worker, parent=self)

    def _resolve_document_path_for_execution(self) -> str | None:
        cached = str(getattr(self, "_cached_document_path", "") or "")
        if cached:
            try:
                if Path(cached).exists():
                    self._sync_document_label_from_path(cached)
                    return cached
            except Exception:
                pass

        label = str(getattr(self._last_task_state, "document_label", "") or "").strip()
        if label:
            try:
                candidate = Path(label)
                if candidate.is_absolute() and candidate.exists():
                    resolved = str(candidate.resolve())
                    self._cached_document_path = resolved
                    self._sync_document_label_from_path(resolved)
                    return resolved
            except Exception:
                pass

        file_name, _selected = QFileDialog.getOpenFileName(
            self,
            "选择文档",
            "",
            "Word Documents (*.docx);;All Files (*)",
        )
        file_name = str(file_name or "").strip()
        if not file_name:
            return None
        try:
            path = Path(file_name).expanduser()
            if path.exists():
                resolved = str(path.resolve())
            else:
                resolved = str(path)
        except Exception:
            resolved = file_name
        self._cached_document_path = resolved
        self._sync_document_label_from_path(resolved)
        return resolved

    def _start_execution(self) -> None:
        if self._execution_worker is not None:
            return

        worker = self._build_execution_worker()
        if worker is None:
            if getattr(self, "_last_execution_pick_cancelled", False):
                # User dismissed the on-demand file picker: treat as a no-op.
                self._last_execution_pick_cancelled = False
                return
            # Still a real lifecycle path: surface a deterministic failure state.
            self._reset_execution_progress()
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

        # Lock visible execute affordances immediately after accepting a worker,
        # before any worker callbacks arrive.
        self._command_bar._run_button.setEnabled(False)
        self._execution_center.set_progress_state(
            self._execution_adapter.build_progress_state(
                stage_text="Starting",
                current_step=0,
                total_steps=0,
            )
        )

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
        self._execution_center.set_progress_state(
            self._execution_adapter.build_progress_state(
                stage_text="开始执行",
                current_step=0,
                total_steps=0,
            )
        )

    def _on_execution_progress(self, current_step: int, total_steps: int, stage_text: str) -> None:
        self._execution_center.set_progress_state(
            self._execution_adapter.build_progress_state(
                stage_text=stage_text,
                current_step=current_step,
                total_steps=total_steps,
            )
        )

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
        # If the worker finishes without a result callback, ExecutionCenter may still think it is running.
        self._execution_center._execution_running = False
        if not self._execution_result_received:
            self._execution_center._status_label.setText(self._execution_center._friendly_status("idle"))
        self._command_bar.set_state(self._last_task_state)
        self._execution_center.set_readiness(self._last_readiness_state)

    def apply_execution_result(self, result) -> None:
        """Consume either a normalized payload dict or an ExecutionResultState and sync UI panels."""
        from .state import ExecutionResultState

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

        self._execution_center.set_result_state(result_state)
        self._recent_run_panel.set_state(self._execution_adapter.build_recent_run_state(result_state))
        self._execution_result_received = True

        # A result can arrive before execution_finished (cleanup), so keep the execute
        # affordance locked until the worker reports finished.
        if self._execution_worker is not None:
            self._command_bar._run_button.setEnabled(False)
            self._execution_center._execute_button.setEnabled(False)

    def _reset_execution_progress(self) -> None:
        default = ExecutionProgressState()
        self._execution_center._progress_stage_label.setText(default.stage_text)
        self._execution_center._progress_label.setText(f"{default.current_step} / {default.total_steps}")
        self._execution_center._progress_bar.setValue(default.percent)

    def _apply_theme(self) -> None:
        self.setStyleSheet(build_workbench_stylesheet(get_theme()))
