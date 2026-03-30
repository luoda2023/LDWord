from __future__ import annotations

from collections.abc import Mapping

from src.qt_api import QObject, Signal


class ExecutionWorker(QObject):
    """Bridge a cooperative runner into Qt signals for the Workbench UI."""

    progress_changed = Signal(int, int, str)
    execution_started = Signal()
    execution_succeeded = Signal(object)
    execution_partial = Signal(object)
    execution_failed = Signal(object)
    execution_cancelled = Signal()
    execution_finished = Signal()

    def __init__(self, runner, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def _is_cancelled(self) -> bool:
        return self._cancel_requested

    def _result_status(self, result) -> str:
        if isinstance(result, Mapping):
            status = result.get("status")
        else:
            status = getattr(result, "status", None)

        if status in {"success", "partial_success", "failed", "cancelled"}:
            return status
        raise ValueError(f"Unknown execution status: {status!r}")

    def _normalize_result(self, result, status: str) -> dict[str, object]:
        if isinstance(result, Mapping):
            output_path = str(result.get("output_path") or "")
            output_paths = result.get("output_paths")
            raw_report_paths = list(result.get("report_paths") or [])
            failed_items = list(result.get("failed_items") or [])
            failed_count = int(result.get("failed_count") or len(failed_items))
            error_text = str(result.get("error_text") or result.get("error") or "")
        else:
            output_path = str(getattr(result, "output_path", "") or "")
            output_paths = getattr(result, "output_paths", None)
            raw_report_paths = list(getattr(result, "report_paths", []) or [])
            failed_items = list(getattr(result, "failed_items", []) or [])
            failed_count = int(getattr(result, "failed_count", 0) or len(failed_items))
            error_text = str(
                getattr(result, "error_text", "") or getattr(result, "error", "") or ""
            )

        if not output_path and isinstance(output_paths, Mapping):
            output_path = str(output_paths.get("final") or "")

        report_paths = [str(path) for path in raw_report_paths]

        return {
            "status": status,
            "output_path": output_path,
            "report_paths": report_paths,
            "failed_count": failed_count,
            "error_text": error_text,
        }

    def _failure_payload(self, error_text: str) -> dict[str, object]:
        return {
            "status": "failed",
            "output_path": "",
            "report_paths": [],
            "failed_count": 0,
            "error_text": error_text,
        }

    def run(self) -> None:
        self.execution_started.emit()
        try:
            result = self._runner.run(self.progress_changed.emit, self._is_cancelled)
            status = self._result_status(result)
            payload = self._normalize_result(result, status)
            if status == "cancelled":
                self.execution_cancelled.emit()
            elif status == "partial_success":
                self.execution_partial.emit(payload)
            elif status == "failed":
                self.execution_failed.emit(payload)
            else:
                self.execution_succeeded.emit(payload)
        except Exception as exc:
            self.execution_failed.emit(self._failure_payload(str(exc)))
        finally:
            self._cancel_requested = False
            self.execution_finished.emit()
