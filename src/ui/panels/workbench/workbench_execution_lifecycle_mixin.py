"""Execution-worker lifecycle accessors for the workbench panel."""

from __future__ import annotations


class WorkbenchExecutionLifecycleMixin:
    @property
    def _execution_worker(self):
        return self._execution_session.active_worker

    @_execution_worker.setter
    def _execution_worker(self, worker) -> None:
        self._execution_session.set_active_worker(worker)

    def shutdown_active_execution(self, timeout_ms: int | None = 1000) -> bool:
        return self._execution_session.shutdown_active_execution(timeout_ms=timeout_ms)


__all__ = ["WorkbenchExecutionLifecycleMixin"]
