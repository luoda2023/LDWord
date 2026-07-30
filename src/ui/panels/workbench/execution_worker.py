from __future__ import annotations

from collections.abc import Callable, Mapping

from src.services.execution_session import (
    ExecutionSessionSnapshot,
    cleanup_execution_session_resources,
)
from src.qt_api import QObject, Signal
from src.services.execution_result_contract import (
    execution_result_status,
    normalize_dict_payload,
    normalize_execution_result,
)
from src.services.execution_session_result import (
    attach_cleanup_issues,
    attach_execution_session,
)


class ExecutionWorker(QObject):
    """Bridge a cooperative runner into Qt signals for the Workbench UI."""

    progress_changed = Signal(int, int, str)
    execution_started = Signal()
    execution_succeeded = Signal(object)
    execution_partial = Signal(object)
    execution_failed = Signal(object)
    execution_cancelled = Signal(object)
    execution_finished = Signal()

    def __init__(
        self,
        runner,
        parent=None,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ):
        super().__init__(parent)
        self._runner = runner
        self._cancel_requested = False
        self._external_cancel_check = cancel_check

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def cleanup_execution_resources(self) -> list[str]:
        """Release a frozen session even when this worker never gets to run."""

        snapshot = getattr(self._runner, "execution_session_snapshot", None)
        if not isinstance(snapshot, ExecutionSessionSnapshot):
            return []
        return list(cleanup_execution_session_resources(snapshot))

    def _is_cancelled(self) -> bool:
        if self._cancel_requested:
            return True
        return bool(
            self._external_cancel_check is not None
            and self._external_cancel_check()
        )

    def _result_status(self, result) -> str:
        return execution_result_status(result)

    def _normalize_result(self, result, status: str) -> dict[str, object]:
        payload = normalize_execution_result(result, status)
        attach_execution_session(
            payload,
            normalize_dict_payload(
                result.get("execution_session")
                if isinstance(result, Mapping)
                else getattr(result, "execution_session", None)
            ),
            snapshot=getattr(self._runner, "execution_session_snapshot", None),
        )
        return payload

    def _failure_payload(self, error_text: str) -> dict[str, object]:
        return {
            "status": "failed",
            "output_path": "",
            "report_paths": [],
            "failed_count": 0,
            "error_text": error_text,
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }

    def run(self) -> None:
        self.execution_started.emit()
        try:
            result = self._runner.run(self.progress_changed.emit, self._is_cancelled)
            status = self._result_status(result)
            payload = self._normalize_result(result, status)
            _cleanup_session_resources(payload, worker=self)
            status = str(payload["status"])
            if status == "cancelled":
                self.execution_cancelled.emit(payload)
            elif status == "partial_success":
                self.execution_partial.emit(payload)
            elif status == "failed":
                self.execution_failed.emit(payload)
            else:
                self.execution_succeeded.emit(payload)
        except Exception as exc:
            payload = self._failure_payload(str(exc))
            snapshot = getattr(self._runner, "execution_session_snapshot", None)
            if isinstance(snapshot, ExecutionSessionSnapshot):
                attach_execution_session(payload, snapshot=snapshot)
            _cleanup_session_resources(payload, worker=self)
            self.execution_failed.emit(payload)
        finally:
            self._cancel_requested = False
            self.execution_finished.emit()


def _cleanup_session_resources(
    payload: dict[str, object],
    *,
    worker: ExecutionWorker,
) -> None:
    runner = worker._runner
    snapshot = getattr(runner, "execution_session_snapshot", None)
    if not isinstance(snapshot, ExecutionSessionSnapshot):
        return
    issues = worker.cleanup_execution_resources()
    if not issues:
        return
    attach_cleanup_issues(payload, issues, snapshot=snapshot)
