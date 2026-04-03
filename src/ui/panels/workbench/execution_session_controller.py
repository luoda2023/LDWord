from __future__ import annotations

from dataclasses import dataclass

from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig

from .execution_runtime import ThreadedExecutionHandle, WorkbenchProductionRunner
from .execution_worker import ExecutionWorker


@dataclass(frozen=True)
class ExecutionBuildResult:
    worker: object | None
    cancelled: bool = False
    already_running: bool = False


class WorkbenchExecutionSessionController:
    """Own active worker lifecycle for the workbench panel."""

    def __init__(self, *, resolve_document_path, worker_parent=None) -> None:
        self._resolve_document_path = resolve_document_path
        self._worker_parent = worker_parent
        self._active_worker = None

    @property
    def active_worker(self):
        return self._active_worker

    def set_active_worker(self, worker) -> None:
        self._active_worker = worker

    def clear_active_worker(self) -> None:
        self._active_worker = None

    def build_worker(
        self,
        *,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
    ) -> ExecutionBuildResult:
        if self._active_worker is not None:
            return ExecutionBuildResult(
                worker=self._active_worker,
                already_running=True,
            )

        doc_path = self._resolve_document_path()
        if doc_path is None:
            return ExecutionBuildResult(worker=None, cancelled=True)

        runner = WorkbenchProductionRunner(
            doc_path=doc_path,
            template=template or TemplateConfig(),
            scene=scene or SceneWorkspace(),
        )
        worker = ExecutionWorker(runner, parent=None)
        return ExecutionBuildResult(
            worker=ThreadedExecutionHandle(worker, parent=self._worker_parent),
        )

    @staticmethod
    def start_worker(worker) -> None:
        start = getattr(worker, "start", None)
        if callable(start):
            start()
            return

        run = getattr(worker, "run", None)
        if callable(run):
            run()

    def shutdown_active_execution(self, timeout_ms: int | None = 1000) -> bool:
        worker = self._active_worker
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


__all__ = ["ExecutionBuildResult", "WorkbenchExecutionSessionController"]
