"""Thin Workbench coordinator for the independent material-suite flow."""

from __future__ import annotations

from src.material_suite.runner import MaterialSuiteGenerationRunner

from .execution_session_controller import ExecutionBuildResult
from .execution_thread_handle import ThreadedExecutionHandle
from .execution_worker import ExecutionWorker


class MaterialSuiteWorkbenchController:
    """Wire the suite detail to the shared worker lifecycle without panel bloat."""

    def __init__(
        self,
        detail,
        execution_controller,
        *,
        start_worker,
        active_worker,
        cancel_execution,
        refresh_navigation,
        publish_material_selection=None,
        open_material_workspace=None,
        worker_parent=None,
    ) -> None:
        self._detail = detail
        self._execution_controller = execution_controller
        self._start_worker = start_worker
        self._active_worker = active_worker
        self._cancel_execution = cancel_execution
        self._refresh_navigation = refresh_navigation
        self._worker_parent = worker_parent
        detail.execute_requested.connect(self.start)
        detail.retry_requested.connect(self.retry)
        detail.cancel_requested.connect(cancel_execution)
        detail.summary_changed.connect(refresh_navigation)
        if publish_material_selection is not None:
            detail.material_selection_changed.connect(publish_material_selection)
        if open_material_workspace is not None:
            detail.material_workspace_requested.connect(open_material_workspace)

    def apply_material_selection(self, selection) -> None:
        self._detail.set_material_batch_selection(selection)

    def start(self) -> None:
        self._start(retry_only=False)

    def retry(self) -> None:
        self._start(retry_only=True)

    def _start(self, *, retry_only: bool) -> None:
        if self._active_worker() is not None:
            return
        self._execution_controller.set_feedback_target("suite")
        try:
            plan = self._detail.current_run_plan(retry_only=retry_only)
        except Exception as exc:  # noqa: BLE001 - report preflight through UI
            self._start_worker(
                ExecutionBuildResult(
                    worker=None,
                    error_text=f"成套生成预检失败：{type(exc).__name__}: {exc}",
                )
            )
            return
        if not plan.ok:
            issues = [
                *plan.issues,
                *[
                    f"{record.profile_name}：{'；'.join(record.issues)}"
                    for record in plan.records
                    if record.issues
                ],
            ]
            self._start_worker(
                ExecutionBuildResult(
                    worker=None,
                    error_text="成套生成预检未通过：" + "；".join(issues),
                )
            )
            return
        worker = ExecutionWorker(MaterialSuiteGenerationRunner(plan))
        handle = ThreadedExecutionHandle(worker, parent=self._worker_parent)
        self._start_worker(ExecutionBuildResult(worker=handle))


__all__ = ["MaterialSuiteWorkbenchController"]
