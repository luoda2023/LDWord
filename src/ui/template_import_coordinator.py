"""Application-level monitoring and serialized background template imports."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import threading
from typing import Any, Callable

from src.config.template_authoring_workspace import (
    TemplateAuthoringWorkspace,
    TemplateImportBatch,
    ensure_template_authoring_workspace,
    process_template_import_inbox,
    template_authoring_workspace_descriptor,
)
from src.config.work_mode import default_work_mode
from src.qt_api import QFileSystemWatcher, QObject, QTimer, Signal


class CoordinatorPhase(str, Enum):
    STOPPED = "stopped"
    PREPARING = "preparing"
    WATCHING = "watching"
    IMPORTING = "importing"
    STOPPING = "stopping"


@dataclass(frozen=True, slots=True)
class _CoordinatorTask:
    phase: CoordinatorPhase
    mode_id: str
    future: Future


class _DaemonSerialExecutor:
    """Run one task at a time with bounded, process-safe shutdown.

    A running Python callable cannot be forcibly cancelled.  The template
    import jobs also call filesystem and third-party code which does not expose
    a cancellation token.  A regular ``ThreadPoolExecutor`` therefore risks
    holding interpreter shutdown forever.  This small executor preserves the
    ``Future`` contract while using one daemon worker and an explicitly bounded
    join.
    """

    def __init__(self, *, thread_name: str) -> None:
        self._thread_name = thread_name
        self._thread: threading.Thread | None = None
        self._future: Future | None = None
        self._closed = False

    def submit(self, callback: Callable[..., Any], /, *args: Any) -> Future:
        if self._closed:
            raise RuntimeError("cannot schedule work after shutdown")
        if self._future is not None and not self._future.done():
            raise RuntimeError("serial executor already has an active task")

        future: Future = Future()

        def _run() -> None:
            if not future.set_running_or_notify_cancel():
                return
            try:
                result = callback(*args)
            except BaseException as exc:  # mirror concurrent.futures semantics
                future.set_exception(exc)
            else:
                future.set_result(result)

        thread = threading.Thread(
            target=_run,
            name=self._thread_name,
            daemon=True,
        )
        self._future = future
        self._thread = thread
        thread.start()
        return future

    @property
    def is_alive(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    @property
    def worker_thread(self) -> threading.Thread | None:
        return self._thread

    def shutdown(self, *, cancel_futures: bool, timeout_ms: int) -> bool:
        self._closed = True
        if cancel_futures and self._future is not None:
            self._future.cancel()
        return self.wait(timeout_ms=timeout_ms)

    def wait(self, *, timeout_ms: int) -> bool:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return True
        if thread is threading.current_thread():
            return False
        thread.join(max(0, int(timeout_ms)) / 1000.0)
        return not thread.is_alive()


class TemplateImportCoordinator(QObject):
    """Watch the current mode inbox and serialize imports off the GUI thread."""

    batch_processed = Signal(str, object)  # mode_id, TemplateImportBatch
    monitoring_error = Signal(str, str)  # mode_id, message
    phase_changed = Signal(object)  # CoordinatorPhase
    idle = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = False
        self._phase = CoordinatorPhase.STOPPED
        self._active_mode_id = ""
        self._requested_mode_id = ""
        self._pending_mode_ids: set[str] = set()
        self._inbox_mode_by_path: dict[str, str] = {}
        self._executor: _DaemonSerialExecutor | None = None
        self._retired_executor: _DaemonSerialExecutor | None = None
        self._task: _CoordinatorTask | None = None

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_directory_changed)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self.process_pending_now)

        self._future_poll_timer = QTimer(self)
        self._future_poll_timer.setInterval(30)
        self._future_poll_timer.timeout.connect(self._poll_future)

        self._reconcile_timer = QTimer(self)
        self._reconcile_timer.setInterval(30000)
        self._reconcile_timer.timeout.connect(self._reconcile)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def phase(self) -> CoordinatorPhase:
        return self._phase

    @property
    def is_idle(self) -> bool:
        return (
            self._running
            and self._phase == CoordinatorPhase.WATCHING
            and self._task is None
            and not self._requested_mode_id
            and not self._pending_mode_ids
        )

    @property
    def active_mode_id(self) -> str:
        return self._active_mode_id

    def watched_inbox_paths(self) -> tuple[Path, ...]:
        return tuple(
            Path(path)
            for path in sorted(self._inbox_mode_by_path, key=str.casefold)
        )

    def start(self, mode_id: str | None = None) -> None:
        """Start monitoring and materialize only the requested mode board."""

        requested = str(mode_id or default_work_mode().mode_id).strip()
        if self._running:
            self.activate_mode(requested)
            return
        self._reap_retired_executor()
        if self._retired_executor is not None:
            self.monitoring_error.emit(
                requested,
                "上一轮模板导入任务仍在退出，暂不重复启动后台导入。",
            )
            return
        self._running = True
        self._set_phase(CoordinatorPhase.WATCHING)
        self._executor = _DaemonSerialExecutor(
            thread_name="template-import",
        )
        self._watcher.blockSignals(False)
        self._reconcile_timer.start()
        self.activate_mode(requested)

    def stop(self, timeout_ms: int = 100) -> bool:
        """Stop monitoring and wait only up to ``timeout_ms`` for its worker.

        ``False`` means a running daemon worker did not cooperate within the
        bound.  Its result is detached from the stopped coordinator and callers
        may use :meth:`wait_for_stopped` for diagnostic or test cleanup.
        """

        if not self._running and self._executor is None:
            self._set_phase(CoordinatorPhase.STOPPED)
            return self.wait_for_stopped(timeout_ms=timeout_ms)
        self._set_phase(CoordinatorPhase.STOPPING)
        self._running = False
        self._active_mode_id = ""
        self._requested_mode_id = ""
        self._debounce_timer.stop()
        self._future_poll_timer.stop()
        self._reconcile_timer.stop()
        self._pending_mode_ids.clear()
        self._clear_watches()
        self._watcher.blockSignals(True)

        task = self._task
        if task is not None:
            task.future.cancel()

        executor = self._executor
        self._executor = None
        stopped = True
        if executor is not None:
            stopped = executor.shutdown(
                cancel_futures=True,
                timeout_ms=timeout_ms,
            )
            if not stopped:
                self._retired_executor = executor
        self._task = None
        self._set_phase(CoordinatorPhase.STOPPED)
        return stopped

    @property
    def has_live_worker(self) -> bool:
        return bool(
            (self._executor is not None and self._executor.is_alive)
            or (
                self._retired_executor is not None
                and self._retired_executor.is_alive
            )
        )

    @property
    def worker_thread(self) -> threading.Thread | None:
        for executor in (self._executor, self._retired_executor):
            if executor is not None and executor.worker_thread is not None:
                return executor.worker_thread
        return None

    def wait_for_stopped(self, timeout_ms: int = 1000) -> bool:
        executor = self._retired_executor
        if executor is None:
            return not self.has_live_worker
        stopped = executor.wait(timeout_ms=timeout_ms)
        if stopped:
            self._retired_executor = None
        return stopped

    def _reap_retired_executor(self) -> None:
        executor = self._retired_executor
        if executor is not None and not executor.is_alive:
            self._retired_executor = None

    def activate_mode(self, mode_id: str) -> bool:
        """Switch monitoring to one mode without materializing its peers."""

        normalized = str(mode_id or "").strip()
        if not self._running or not normalized:
            return False
        try:
            template_authoring_workspace_descriptor(normalized)
        except ValueError as exc:
            self.monitoring_error.emit(normalized, f"无法准备模板工作台：{exc}")
            return False

        if normalized == self._active_mode_id:
            task = self._task
            if (
                self._requested_mode_id == normalized
                or (task is not None and task.mode_id == normalized)
                or normalized in self._inbox_mode_by_path.values()
            ):
                return True

        self._active_mode_id = normalized
        self._requested_mode_id = normalized
        self._pending_mode_ids.intersection_update({normalized})
        self._clear_watches()
        self._begin_requested_prepare()
        return True

    def queue_mode(self, mode_id: str, *, debounce_ms: int = 0) -> bool:
        """Queue the currently monitored mode for serialized processing."""

        normalized = str(mode_id or "").strip()
        watched_modes = set(self._inbox_mode_by_path.values())
        if (
            not self._running
            or normalized != self._active_mode_id
            or normalized not in watched_modes
        ):
            return False
        self._pending_mode_ids.add(normalized)
        if debounce_ms > 0:
            self._debounce_timer.start(int(debounce_ms))
        else:
            self.process_pending_now()
        return True

    def process_pending_now(self) -> None:
        """Dispatch at most one import to the serial worker."""

        if not self._running or self._task is not None:
            return
        mode_id = self._active_mode_id
        self._pending_mode_ids.intersection_update({mode_id})
        if not mode_id or mode_id not in self._pending_mode_ids:
            self.idle.emit()
            return
        executor = self._executor
        if executor is None:
            return
        self._pending_mode_ids.remove(mode_id)
        self._start_task(
            CoordinatorPhase.IMPORTING,
            mode_id,
            executor.submit(process_template_import_inbox, mode_id),
        )

    def _begin_requested_prepare(self) -> None:
        if (
            not self._running
            or not self._requested_mode_id
            or self._task is not None
        ):
            return
        executor = self._executor
        if executor is None:
            return
        mode_id = self._requested_mode_id
        self._requested_mode_id = ""
        self._start_task(
            CoordinatorPhase.PREPARING,
            mode_id,
            executor.submit(ensure_template_authoring_workspace, mode_id),
        )

    def _start_task(
        self,
        phase: CoordinatorPhase,
        mode_id: str,
        future: Future,
    ) -> None:
        if self._task is not None:
            raise RuntimeError("template import coordinator already has an active task")
        if phase not in {CoordinatorPhase.PREPARING, CoordinatorPhase.IMPORTING}:
            raise ValueError(f"invalid task phase: {phase}")
        self._task = _CoordinatorTask(phase=phase, mode_id=mode_id, future=future)
        self._set_phase(phase)
        self._future_poll_timer.start()

    def _set_phase(self, phase: CoordinatorPhase) -> None:
        if phase == self._phase:
            return
        self._phase = phase
        self.phase_changed.emit(phase)

    def _clear_watches(self) -> None:
        watched_paths = self._watcher.directories()
        if watched_paths:
            self._watcher.removePaths(watched_paths)
        self._inbox_mode_by_path.clear()

    def _sync_workspace(
        self,
        workspace: TemplateAuthoringWorkspace,
        *,
        queue_existing: bool,
    ) -> None:
        self._clear_watches()
        if workspace.mode_id != self._active_mode_id:
            return
        raw_path = str(workspace.inbox_path)
        failed_paths = self._watcher.addPaths([raw_path])
        if failed_paths:
            self.monitoring_error.emit(
                workspace.mode_id,
                f"无法监控模板待导入目录：{raw_path}",
            )
            return
        self._inbox_mode_by_path[_path_key(workspace.inbox_path)] = workspace.mode_id
        if queue_existing and _workspace_has_pending_json(workspace):
            self._pending_mode_ids.add(workspace.mode_id)

    def _on_directory_changed(self, path: str) -> None:
        if not self._running:
            return
        mode_id = self._inbox_mode_by_path.get(_path_key(Path(path)), "")
        if not mode_id:
            self._reconcile_timer.start()
            return
        self.queue_mode(mode_id, debounce_ms=450)

    def _poll_future(self) -> None:
        task = self._task
        if task is None or not task.future.done():
            return
        self._task = None
        self._set_phase(CoordinatorPhase.WATCHING)
        retry_delay_ms = 0

        if task.phase == CoordinatorPhase.PREPARING:
            try:
                workspace = task.future.result()
                if not isinstance(workspace, TemplateAuthoringWorkspace):
                    raise TypeError("workspace preparation returned an invalid result")
            except Exception as exc:
                self.monitoring_error.emit(
                    task.mode_id,
                    f"准备模板工作台失败：{exc}",
                )
            else:
                self._sync_workspace(workspace, queue_existing=True)
        elif task.phase == CoordinatorPhase.IMPORTING:
            retry_delay_ms = 150
            try:
                batch = task.future.result()
                if not isinstance(batch, TemplateImportBatch):
                    raise TypeError("template import returned an invalid result")
            except Exception as exc:
                self.monitoring_error.emit(
                    task.mode_id,
                    f"处理模板待导入目录发生内部错误：{exc}",
                )
            else:
                if batch.has_activity:
                    self.batch_processed.emit(task.mode_id, batch)
                if batch.pending_count and task.mode_id == self._active_mode_id:
                    self._pending_mode_ids.add(task.mode_id)
                    retry_delay_ms = 900

        self._continue_serial_work(retry_delay_ms=retry_delay_ms)

    def _continue_serial_work(self, *, retry_delay_ms: int = 0) -> None:
        if not self._running:
            return
        if self._requested_mode_id:
            self._begin_requested_prepare()
            return
        if self._pending_mode_ids:
            self._debounce_timer.start(max(0, int(retry_delay_ms)))
            return
        self._future_poll_timer.stop()
        self._set_phase(CoordinatorPhase.WATCHING)
        self.idle.emit()

    def _reconcile(self) -> None:
        if not self._running or not self._active_mode_id:
            return
        workspace = template_authoring_workspace_descriptor(self._active_mode_id)
        inbox_key = _path_key(workspace.inbox_path)
        if (
            workspace.inbox_path.is_dir()
            and self._inbox_mode_by_path.get(inbox_key) == self._active_mode_id
        ):
            if _workspace_has_pending_json(workspace):
                self.queue_mode(self._active_mode_id, debounce_ms=150)
            return
        self._requested_mode_id = self._active_mode_id
        self._begin_requested_prepare()


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve()).casefold()
    except OSError:
        return str(path.absolute()).casefold()


def _workspace_has_pending_json(workspace: TemplateAuthoringWorkspace) -> bool:
    return _directory_has_json(workspace.processing_dir) or _directory_has_json(
        workspace.inbox_path
    )


def _directory_has_json(directory: Path) -> bool:
    try:
        return any(
            path.is_file() and path.suffix.casefold() == ".json"
            for path in directory.iterdir()
        )
    except OSError:
        return False


__all__ = ["CoordinatorPhase", "TemplateImportCoordinator"]
