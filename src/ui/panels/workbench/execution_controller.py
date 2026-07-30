from __future__ import annotations

from typing import Callable

from .state import ExecutionResultState


class WorkbenchExecutionController:
    """Coordinate worker lifecycle feedback for the quick-execute surface."""

    def __init__(
        self,
        execution_adapter,
        quick_execution_detail,
        batch_generation_detail=None,
        suite_generation_detail=None,
        *,
        refresh_navigation: Callable[[], None] | None = None,
        refresh_quick_execute_card: Callable[[], None] | None = None,
        clear_execution_worker: Callable[[], None],
        has_ready_document: Callable[[], bool],
    ) -> None:
        self._execution_adapter = execution_adapter
        self._quick_execution_detail = quick_execution_detail
        self._batch_generation_detail = batch_generation_detail
        self._suite_generation_detail = suite_generation_detail
        self._refresh_navigation = (
            refresh_navigation
            or refresh_quick_execute_card
            or (lambda: None)
        )
        self._clear_execution_worker = clear_execution_worker
        self._has_ready_document = has_ready_document
        self._execution_result_received = False
        self._feedback_target = "single"

    def set_feedback_target(self, target: str) -> None:
        if target not in {"single", "batch", "suite"}:
            raise ValueError(f"Unsupported execution feedback target: {target}")
        self._feedback_target = target

    def _feedback_surface(self):
        if self._feedback_target == "suite" and self._suite_generation_detail is not None:
            return self._suite_generation_detail
        if self._feedback_target == "batch" and self._batch_generation_detail is not None:
            return self._batch_generation_detail
        return self._quick_execution_detail

    def reset_feedback(self) -> None:
        self._feedback_surface().reset_execution_feedback()
        self._refresh_navigation()

    def cancel_execution(self, worker) -> None:
        if worker is None:
            return
        request_cancel = getattr(worker, "request_cancel", None)
        if callable(request_cancel):
            request_cancel()

    def prepare_worker(self, worker) -> None:
        self._execution_result_received = False
        self._wire_worker(worker)
        target = self._feedback_surface()
        target.reset_execution_feedback()
        self._quick_execution_detail.set_execute_enabled(False)
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_execute_enabled(False)
        if self._suite_generation_detail is not None:
            self._suite_generation_detail.set_execute_enabled(False)
        target.set_execution_progress(
            self._execution_adapter.build_progress_state(
                stage_text="Starting",
                current_step=0,
                total_steps=0,
            )
        )
        self._refresh_navigation()

    def apply_execution_result(self, result) -> None:
        if isinstance(result, ExecutionResultState):
            result_state = result
        else:
            result_state = self._execution_adapter.build_result_state(
                terminal_payload=result,
            )

        self._feedback_surface().set_execution_result(result_state)
        self._execution_result_received = True
        self._refresh_navigation()

    def _wire_worker(self, worker) -> None:
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
            stage_text="开始执行",
            current_step=0,
            total_steps=0,
        )
        self._feedback_surface().set_execution_progress(progress_state)
        self._refresh_navigation()

    def _on_execution_progress(self, current_step: int, total_steps: int, stage_text: str) -> None:
        progress_state = self._execution_adapter.build_progress_state(
            stage_text=stage_text,
            current_step=current_step,
            total_steps=total_steps,
        )
        self._feedback_surface().set_execution_progress(progress_state)
        self._refresh_navigation()

    def _on_execution_succeeded(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_partial(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_failed(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_cancelled(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_finished(self) -> None:
        self._clear_execution_worker()
        if not self._execution_result_received:
            self._feedback_surface().finish_execution()
        self._quick_execution_detail.set_execute_enabled(self._has_ready_document())
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_execute_enabled(True)
        if self._suite_generation_detail is not None:
            self._suite_generation_detail.set_execute_enabled(True)
        self._refresh_navigation()
