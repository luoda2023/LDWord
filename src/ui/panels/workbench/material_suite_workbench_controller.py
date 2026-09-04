"""Controller for canonical material-suite generation."""

from __future__ import annotations

from collections.abc import Callable

from src.application.materials import MaterialPreviewSnapshot
from src.domain.materials import MaterialIssue, MaterialRunSelection
from src.material_suite.plan import (
    MaterialSuiteRunRequest,
    compile_material_suite_plan,
    discover_material_suite_bundle,
)
from src.material_suite.runner import MaterialSuiteGenerationRunner

from .execution_session_controller import (
    ExecutionBuildResult,
    build_threaded_runner,
)
from .material_state import bind_workbench_material


class _MaterialSuiteRunner:
    def __init__(self, plan) -> None:
        self._runner = MaterialSuiteGenerationRunner(plan)

    def run(self, progress_callback, cancel_check):
        return self._runner.run(progress_callback, cancel_check)


class MaterialSuiteWorkbenchController:
    def __init__(
        self,
        detail,
        execution,
        *,
        start_worker: Callable[[ExecutionBuildResult], None],
        active_worker: Callable[[], object | None],
        cancel_execution: Callable[[], None],
        refresh_navigation: Callable[[], None],
        publish_material_selection: Callable[[MaterialRunSelection | None], None],
        open_material_workspace: Callable[[], None],
        current_mode_id: Callable[[], str] | None = None,
        current_scene_id: Callable[[], str] | None = None,
        current_document_type_id: Callable[[], str] | None = None,
        worker_parent=None,
    ) -> None:
        self._detail = detail
        self._execution = execution
        self._start_worker = start_worker
        self._active_worker = active_worker
        self._refresh_navigation = refresh_navigation
        self._publish_material_selection = publish_material_selection
        self._current_mode_id = current_mode_id or (lambda: "custom")
        self._current_scene_id = current_scene_id or (lambda: "")
        self._current_document_type_id = (
            current_document_type_id or (lambda: "")
        )
        self._worker_parent = worker_parent
        detail.execute_requested.connect(self.start)
        detail.retry_requested.connect(self.start)
        detail.cancel_requested.connect(cancel_execution)
        detail.material_workspace_requested.connect(open_material_workspace)
        detail.summary_changed.connect(refresh_navigation)

    def apply_material_selection(
        self,
        selection: MaterialRunSelection | None,
        *,
        preview: MaterialPreviewSnapshot | None = None,
        issues: tuple[MaterialIssue, ...] = (),
    ) -> None:
        self._detail.set_material_selection(
            selection,
            preview=preview,
            issues=issues,
        )

    def start(self) -> None:
        if self._active_worker() is not None:
            return
        selection = self._detail.material_selection()
        if selection is None:
            return
        blockers = self._detail.execution_blocking_reasons()
        if blockers:
            return
        mode_id = self._current_mode_id()
        snapshot, issues = bind_workbench_material(
            selection,
            work_mode_id=mode_id,
            recipe_id="material_suite",
            scene_id=self._current_scene_id(),
            document_type=(
                self._current_document_type_id()
                if mode_id == "official"
                else ""
            ),
        )
        if snapshot is None:
            self._publish_failure(issues)
            return
        try:
            bundle = discover_material_suite_bundle(
                self._detail.suite_root()
            )
            plan = compile_material_suite_plan(
                snapshot,
                bundle,
                output_root=self._detail.output_dir(),
                request=MaterialSuiteRunRequest(
                    output_root=self._detail.output_dir(),
                    requested_by="workbench",
                ),
            )
            build = build_threaded_runner(
                _MaterialSuiteRunner(plan),
                parent=self._worker_parent,
            )
        except Exception as exc:
            self._publish_failure(
                (
                    MaterialIssue(
                        code="material_suite.plan_failed",
                        message=f"{type(exc).__name__}: {exc}",
                    ),
                )
            )
            return
        self._execution.set_feedback_target("suite")
        self._start_worker(build)

    def _publish_failure(
        self,
        issues: tuple[MaterialIssue, ...],
    ) -> None:
        self._execution.set_feedback_target("suite")
        self._execution.reset_feedback()
        self._execution.apply_execution_result(
            {
                "status": "failed",
                "output_path": "",
                "report_paths": [],
                "failed_count": 0,
                "error_text": "；".join(
                    item.message or item.code for item in issues
                ),
            }
        )
        self._refresh_navigation()


__all__ = ["MaterialSuiteWorkbenchController"]
