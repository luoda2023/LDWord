import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.workbench.panel import WorkbenchPanel, _ThreadedExecutionHandle


def test_legacy_threaded_execution_handle_shutdown_logs_best_effort_failures(caplog):
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
        _ThreadedExecutionHandle.shutdown(handle, timeout_ms=250)

    assert handle.cancel_requests == 1
    assert handle._thread.quit_calls == 1
    assert handle._thread.wait_calls == [250]
    messages = [record.getMessage() for record in caplog.records]
    assert any("legacy execution thread handle" in message and "request_cancel" in message for message in messages)
    assert any("legacy execution thread handle" in message and "thread.quit" in message for message in messages)
    assert any("legacy execution thread handle" in message and "thread.wait" in message for message in messages)


def test_legacy_workbench_panel_shutdown_logs_failures_and_returns_false_when_running_state_unknown(
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

    panel = type("_LegacyPanelStub", (), {"_execution_worker": _FailingWorker()})()

    with caplog.at_level(logging.WARNING):
        result = WorkbenchPanel.shutdown_active_execution(panel, timeout_ms=125)

    assert result is False
    assert panel._execution_worker.cancel_requests == 1
    assert panel._execution_worker.shutdown_calls == [125]
    messages = [record.getMessage() for record in caplog.records]
    assert any("legacy workbench panel" in message and "request_cancel" in message for message in messages)
    assert any("legacy workbench panel" in message and "worker.shutdown" in message for message in messages)
    assert any("legacy workbench panel" in message and "worker.isRunning" in message for message in messages)


def test_legacy_workbench_panel_on_document_loaded_logs_expanduser_failure(monkeypatch, caplog):
    import src.ui.panels.workbench.panel as panel_module

    class _PanelStub:
        def __init__(self) -> None:
            self._cached_document_path = ""
            self.synced = []

        def _sync_document_label_from_path(self, file_path: str) -> None:
            self.synced.append(file_path)

    def _raise_expanduser(self):
        raise RuntimeError("expanduser boom")

    monkeypatch.setattr(panel_module.Path, "expanduser", _raise_expanduser)
    panel = _PanelStub()

    with caplog.at_level(logging.WARNING):
        WorkbenchPanel._on_document_loaded(panel, "broken.docx")

    assert panel._cached_document_path == ""
    assert panel.synced == []
    assert any("document load expanduser" in record.getMessage() for record in caplog.records)


def test_legacy_workbench_panel_resolve_execution_document_logs_cached_path_failure_and_falls_back_to_picker(
    monkeypatch,
    caplog,
    tmp_path,
):
    import src.ui.panels.workbench.panel as panel_module

    original_exists = panel_module.Path.exists
    failing_cached = str(tmp_path / "cached.docx")
    picked_path = tmp_path / "picked.docx"
    picked_path.write_bytes(b"")
    picked_resolved = str(picked_path.resolve())

    class _TaskState:
        document_label = ""

    class _PanelStub:
        def __init__(self) -> None:
            self._cached_document_path = failing_cached
            self._last_task_state = _TaskState()
            self.synced = []

        def _sync_document_label_from_path(self, file_path: str) -> None:
            self.synced.append(file_path)

    def _exists_with_failure(self):
        if str(self) == failing_cached:
            raise OSError("cached exists boom")
        return original_exists(self)

    monkeypatch.setattr(panel_module.Path, "exists", _exists_with_failure)
    monkeypatch.setattr(
        panel_module.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(picked_path), "")),
    )

    panel = _PanelStub()
    with caplog.at_level(logging.WARNING):
        resolved = WorkbenchPanel._resolve_document_path_for_execution(panel)

    assert resolved == picked_resolved
    assert panel._cached_document_path == picked_resolved
    assert panel.synced == [picked_resolved]
    assert any("cached document exists check" in record.getMessage() for record in caplog.records)
