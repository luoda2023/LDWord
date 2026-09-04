"""Qt thread adapter for a workbench execution worker."""

from __future__ import annotations

from PySide6.QtCore import QThread

from src.qt_api import QObject, Signal

from .diagnostics import log_best_effort_shutdown_failure


class ThreadedExecutionHandle(QObject):
    """Run an ExecutionWorker on a dedicated QThread."""

    progress_changed = Signal(int, int, str)
    execution_started = Signal()
    execution_succeeded = Signal(object)
    execution_partial = Signal(object)
    execution_failed = Signal(object)
    execution_cancelled = Signal(object)
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
            log_best_effort_shutdown_failure(
                "execution thread handle",
                "request_cancel",
                exc,
            )

        thread = getattr(self, "_thread", None)
        if thread is None:
            self._release_execution_resources()
            return

        is_running = getattr(thread, "isRunning", None)
        try:
            running = bool(is_running()) if callable(is_running) else True
        except Exception as exc:
            log_best_effort_shutdown_failure(
                "execution thread handle",
                "thread.isRunning",
                exc,
            )
            running = True

        if not running:
            self._release_execution_resources()
            return

        quit_thread = getattr(thread, "quit", None)
        if callable(quit_thread):
            try:
                quit_thread()
            except Exception as exc:
                log_best_effort_shutdown_failure(
                    "execution thread handle",
                    "thread.quit",
                    exc,
                )

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
                    log_best_effort_shutdown_failure(
                        "execution thread handle",
                        "thread.wait",
                        exc,
                    )
            except Exception as exc:
                log_best_effort_shutdown_failure(
                    "execution thread handle",
                    "thread.wait",
                    exc,
                )

        try:
            running = bool(is_running()) if callable(is_running) else True
        except Exception:
            running = True
        if not running:
            self._release_execution_resources()

    def _release_execution_resources(self) -> None:
        worker = getattr(self, "_worker", None)
        cleanup = getattr(worker, "cleanup_execution_resources", None)
        if not callable(cleanup):
            return
        try:
            issues = list(cleanup() or [])
        except Exception as exc:
            log_best_effort_shutdown_failure(
                "execution thread handle",
                "cleanup_execution_resources",
                exc,
            )
            return
        for issue in issues:
            log_best_effort_shutdown_failure(
                "execution thread handle",
                "cleanup_execution_resources",
                RuntimeError(str(issue)),
            )


__all__ = ["ThreadedExecutionHandle"]
