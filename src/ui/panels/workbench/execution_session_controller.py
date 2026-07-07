from __future__ import annotations

from dataclasses import dataclass

from src.config.entity import EntityArchive
from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig

from .diagnostics import log_best_effort_shutdown_failure


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
        session_overrides: dict[str, object] | None = None,
        material_context: MaterialExecutionContext | None = None,
    ) -> ExecutionBuildResult:
        if self._active_worker is not None:
            return ExecutionBuildResult(
                worker=self._active_worker,
                already_running=True,
            )

        doc_path = self._resolve_document_path()
        if doc_path is None:
            return ExecutionBuildResult(worker=None, cancelled=True)

        from .execution_runtime import ThreadedExecutionHandle, WorkbenchProductionRunner
        from .execution_worker import ExecutionWorker

        runner = WorkbenchProductionRunner(
            doc_path=doc_path,
            template=template or TemplateConfig(),
            scene=scene or SceneWorkspace(),
            session_overrides=session_overrides,
            material_context=material_context,
        )
        worker = ExecutionWorker(runner, parent=None)
        return ExecutionBuildResult(
            worker=ThreadedExecutionHandle(worker, parent=self._worker_parent),
        )

    def build_batch_worker(
        self,
        *,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        archive: EntityArchive,
        profile_ids: list[str] | None = None,
        base_output_dir: str | None = None,
        output_dir_template: str = "{entity_name}",
        session_overrides: dict[str, object] | None = None,
        base_context: MaterialExecutionContext | None = None,
    ) -> ExecutionBuildResult:
        if self._active_worker is not None:
            return ExecutionBuildResult(
                worker=self._active_worker,
                already_running=True,
            )

        doc_path = self._resolve_document_path()
        if doc_path is None:
            return ExecutionBuildResult(worker=None, cancelled=True)

        from .execution_runtime import ThreadedExecutionHandle, WorkbenchBatchProductionRunner
        from .execution_worker import ExecutionWorker

        runner = WorkbenchBatchProductionRunner(
            doc_path=doc_path,
            template=template or TemplateConfig(),
            scene=scene or SceneWorkspace(),
            archive=archive,
            profile_ids=profile_ids,
            base_output_dir=base_output_dir,
            output_dir_template=output_dir_template,
            session_overrides=session_overrides,
            base_context=base_context,
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
            except Exception as exc:
                log_best_effort_shutdown_failure("execution session controller", "request_cancel", exc)

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
                except Exception as exc:
                    log_best_effort_shutdown_failure(
                        "execution session controller",
                        "worker.shutdown",
                        exc,
                    )
            except Exception as exc:
                log_best_effort_shutdown_failure("execution session controller", "worker.shutdown", exc)

        thread = getattr(worker, "_thread", None)
        is_running = getattr(thread, "isRunning", None) if thread is not None else None
        if not callable(is_running):
            is_running = getattr(worker, "isRunning", None)

        if callable(is_running):
            try:
                return not bool(is_running())
            except Exception as exc:
                log_best_effort_shutdown_failure("execution session controller", "worker.isRunning", exc)
                return False
        return True


__all__ = ["ExecutionBuildResult", "WorkbenchExecutionSessionController"]
