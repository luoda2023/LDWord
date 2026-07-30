import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.workbench.execution_thread_handle import ThreadedExecutionHandle
from src.ui.panels.workbench.execution_session_controller import WorkbenchExecutionSessionController
from src.ui.panels.workbench.execution_worker import ExecutionWorker
from src.qt_api import QApplication


def _app():
    return QApplication.instance() or QApplication([])


def test_unstarted_thread_handle_shutdown_releases_execution_resources():
    _app()

    class _Runner:
        def run(self, _progress_cb, _cancel_check):
            return {"status": "success"}

    worker = ExecutionWorker(_Runner())
    cleanup_calls = []
    worker.cleanup_execution_resources = lambda: cleanup_calls.append(True) or []
    handle = ThreadedExecutionHandle(worker)

    handle.shutdown()

    assert cleanup_calls == [True]


def test_discard_worker_clears_active_handle_and_shuts_it_down():
    class _Worker:
        def __init__(self) -> None:
            self.shutdown_calls = []

        def shutdown(self, timeout_ms=None) -> None:
            self.shutdown_calls.append(timeout_ms)

    controller = WorkbenchExecutionSessionController(resolve_document_path=lambda: None)
    worker = _Worker()
    controller.set_active_worker(worker)

    assert controller.discard_worker(worker, timeout_ms=250) == []
    assert controller.active_worker is None
    assert worker.shutdown_calls == [250]


def test_threaded_execution_handle_shutdown_logs_best_effort_failures(caplog):
    class _FailingThread:
        def __init__(self) -> None:
            self.quit_calls = 0
            self.wait_calls = []

        def isRunning(self) -> bool:
            return True

        def quit(self) -> None:
            self.quit_calls += 1
            raise RuntimeError("quit boom")

        def wait(self, timeout_ms: int) -> None:
            self.wait_calls.append(timeout_ms)
            raise RuntimeError("wait boom")

    class _FailingHandle:
        def __init__(self) -> None:
            self._thread = _FailingThread()
            self.cancel_requests = 0

        def request_cancel(self) -> None:
            self.cancel_requests += 1
            raise RuntimeError("cancel boom")

    handle = _FailingHandle()

    with caplog.at_level(logging.WARNING):
        ThreadedExecutionHandle.shutdown(handle, timeout_ms=250)

    assert handle.cancel_requests == 1
    assert handle._thread.quit_calls == 1
    assert handle._thread.wait_calls == [250]

    messages = [record.getMessage() for record in caplog.records]
    assert any("execution thread handle" in message and "request_cancel" in message for message in messages)
    assert any("execution thread handle" in message and "thread.quit" in message for message in messages)
    assert any("execution thread handle" in message and "thread.wait" in message for message in messages)


def test_execution_session_controller_shutdown_logs_failures_and_returns_false_when_running_state_unknown(
    caplog,
):
    class _FailingThread:
        def isRunning(self) -> bool:
            raise RuntimeError("state boom")

    class _FailingWorker:
        def __init__(self) -> None:
            self._thread = _FailingThread()
            self.cancel_requests = 0
            self.shutdown_calls = []

        def request_cancel(self) -> None:
            self.cancel_requests += 1
            raise RuntimeError("cancel boom")

        def shutdown(self, timeout_ms: int | None = 1000) -> None:
            self.shutdown_calls.append(timeout_ms)
            raise RuntimeError("shutdown boom")

    controller = WorkbenchExecutionSessionController(resolve_document_path=lambda: None)
    worker = _FailingWorker()
    controller.set_active_worker(worker)

    with caplog.at_level(logging.WARNING):
        result = controller.shutdown_active_execution(timeout_ms=125)

    assert result is False
    assert worker.cancel_requests == 1
    assert worker.shutdown_calls == [125]

    messages = [record.getMessage() for record in caplog.records]
    assert any("execution session controller" in message and "request_cancel" in message for message in messages)
    assert any("execution session controller" in message and "worker.shutdown" in message for message in messages)
    assert any("execution session controller" in message and "worker.isRunning" in message for message in messages)


def test_execution_session_controller_shutdown_supports_positional_timeout_without_warning(caplog):
    class _StoppedThread:
        def isRunning(self) -> bool:
            return False

    class _CompatWorker:
        def __init__(self) -> None:
            self._thread = _StoppedThread()
            self.cancel_requests = 0
            self.shutdown_calls = []

        def request_cancel(self) -> None:
            self.cancel_requests += 1

        def shutdown(self, *args) -> None:
            self.shutdown_calls.append(args)

    controller = WorkbenchExecutionSessionController(resolve_document_path=lambda: None)
    worker = _CompatWorker()
    controller.set_active_worker(worker)

    with caplog.at_level(logging.WARNING):
        result = controller.shutdown_active_execution(timeout_ms=500)

    assert result is True
    assert worker.cancel_requests == 1
    assert worker.shutdown_calls == [(500,)]
    assert not caplog.records
