from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QThread

from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.execution_diagnostics import build_execution_diagnostics
from src.modules.registry import create_all_modules
from src.pipeline.runner import Pipeline
from src.pipeline.scheduler import select_enabled_modules
from src.qt_api import QObject, Signal
from src.report_writer import write_json_report, write_markdown_report

from .diagnostics import log_best_effort_shutdown_failure


class WorkbenchProductionRunner:
    """Wrap pipeline execution for the workbench UI."""

    def __init__(
        self,
        *,
        doc_path: str,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        session_overrides: dict[str, object] | None = None,
    ) -> None:
        self.doc_path = str(doc_path or "")
        self._template = template
        self._scene = scene
        self._session_overrides = dict(session_overrides or {})

    def run(self, progress_cb, cancel_check):
        input_path = Path(self.doc_path)
        output_dir = input_path.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        template = self._template or TemplateConfig()
        scene = self._scene or SceneWorkspace()
        config = resolve_config(
            template,
            scene,
            session_overrides=self._session_overrides,
        )

        modules = create_all_modules()
        enabled, _auto_pruned = select_enabled_modules(modules, config.is_module_enabled)

        started_at = time.perf_counter()
        pipeline = Pipeline(
            modules=enabled,
            config=config,
            output_dir=str(output_dir),
            output_suffix="_formatted",
            progress_callback=progress_cb,
            cancel_check=cancel_check,
        )
        result = pipeline.execute(str(input_path))
        elapsed = time.perf_counter() - started_at
        diagnostics = build_execution_diagnostics(result)

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
                "diagnostics_count": int(diagnostics["count"]),
                "diagnostics_summary": str(diagnostics["summary"] or ""),
            }

        output_path = ""
        output_paths = getattr(result, "output_paths", None)
        if isinstance(output_paths, dict):
            output_path = str(output_paths.get("final") or "")

        report_paths: list[str] = []
        output_cfg = getattr(config, "output", None)
        report_json_enabled = bool(getattr(output_cfg, "report_json", True))
        report_markdown_enabled = bool(getattr(output_cfg, "report_markdown", True))
        final_output_path = Path(output_path) if output_path else None

        if report_json_enabled:
            report_json = output_dir / f"{input_path.stem}_changes.json"
            write_json_report(
                result,
                input_path=input_path,
                output_path=final_output_path,
                report_path=report_json,
                elapsed=elapsed,
                modules_enabled=len(enabled),
                modules_total=len(modules),
            )
            report_paths.append(str(report_json))

        if report_markdown_enabled:
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
            "diagnostics_count": int(diagnostics["count"]),
            "diagnostics_summary": str(diagnostics["summary"] or ""),
        }


class ThreadedExecutionHandle(QObject):
    """Run an ExecutionWorker on a dedicated QThread."""

    progress_changed = Signal(int, int, str)
    execution_started = Signal()
    execution_succeeded = Signal(object)
    execution_partial = Signal(object)
    execution_failed = Signal(object)
    execution_cancelled = Signal()
    execution_finished = Signal()

    def __init__(self, worker, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._thread = QThread(self)

        self._worker.progress_changed.connect(self.progress_changed.emit)
        self._worker.execution_started.connect(self.execution_started.emit)
        self._worker.execution_succeeded.connect(self.execution_succeeded.emit)
        self._worker.execution_partial.connect(self.execution_partial.emit)
        self._worker.execution_failed.connect(self.execution_failed.emit)
        self._worker.execution_cancelled.connect(self.execution_cancelled.emit)
        self._worker.execution_finished.connect(self.execution_finished.emit)

        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.execution_finished.connect(self._thread.quit)

        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self.deleteLater)

    def start(self) -> None:
        self._thread.start()

    def request_cancel(self) -> None:
        self._worker.request_cancel()

    def shutdown(self, timeout_ms: int | None = 1000) -> None:
        try:
            self.request_cancel()
        except Exception as exc:
            log_best_effort_shutdown_failure("execution thread handle", "request_cancel", exc)

        thread = getattr(self, "_thread", None)
        if thread is None:
            return

        is_running = getattr(thread, "isRunning", None)
        try:
            running = bool(is_running()) if callable(is_running) else True
        except Exception as exc:
            log_best_effort_shutdown_failure("execution thread handle", "thread.isRunning", exc)
            running = True

        if not running:
            return

        quit_thread = getattr(thread, "quit", None)
        if callable(quit_thread):
            try:
                quit_thread()
            except Exception as exc:
                log_best_effort_shutdown_failure("execution thread handle", "thread.quit", exc)

        wait_thread = getattr(thread, "wait", None)
        if callable(wait_thread):
            try:
                if timeout_ms is None:
                    wait_thread()
                else:
                    wait_thread(int(timeout_ms))
            except TypeError:
                try:
                    wait_thread()
                except Exception as exc:
                    log_best_effort_shutdown_failure("execution thread handle", "thread.wait", exc)
            except Exception as exc:
                log_best_effort_shutdown_failure("execution thread handle", "thread.wait", exc)


__all__ = ["ThreadedExecutionHandle", "WorkbenchProductionRunner"]
