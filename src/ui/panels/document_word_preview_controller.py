"""Single serial background controller for every plan Word preview."""

from __future__ import annotations

from collections.abc import Callable
import inspect
import threading

from src.qt_api import QObject, QTimer, Signal
from src.shared.engine.document_word_preview import (
    DocumentWordPreviewRequest,
    DocumentWordPreviewResult,
    render_document_word_preview,
)


PreviewRenderer = Callable[..., DocumentWordPreviewResult]


class DocumentWordPreviewController(QObject):
    result_ready = Signal(object)
    render_failed = Signal(object)
    busy_changed = Signal(bool)
    _thread_finished = Signal(int, object)

    def __init__(
        self,
        parent=None,
        *,
        renderer: PreviewRenderer = render_document_word_preview,
        debounce_ms: int = 700,
    ) -> None:
        super().__init__(parent)
        self._renderer = renderer
        self._renderer_accepts_cancel_event = _accepts_cancel_event(renderer)
        self._generation = 0
        self._pending: tuple[int, DocumentWordPreviewRequest, bool] | None = None
        self._active = False
        self._closed = False
        self._worker_thread: threading.Thread | None = None
        self._cancel_event: threading.Event | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(0, int(debounce_ms)))
        self._timer.timeout.connect(self._start_pending)
        self._thread_finished.connect(self._on_thread_finished)

    def request_preview(
        self,
        request: DocumentWordPreviewRequest,
        *,
        force: bool = False,
    ) -> int:
        if self._closed:
            return self._generation
        self._generation += 1
        token = self._generation
        self._pending = (token, request, bool(force))
        if self._cancel_event is not None:
            self._cancel_event.set()
        self._timer.start()
        return token

    def refresh_now(self) -> None:
        if self._closed:
            return
        self._timer.stop()
        self._start_pending()

    def shutdown(self, timeout_ms: int = 250) -> bool:
        """Cancel queued work and join the active renderer for a bounded time."""

        self._closed = True
        self._pending = None
        self._timer.stop()
        if self._cancel_event is not None:
            self._cancel_event.set()
        stopped = self.wait_for_stopped(timeout_ms=timeout_ms)
        if stopped:
            self._active = False
        return stopped

    @property
    def has_live_worker(self) -> bool:
        thread = self._worker_thread
        return bool(thread is not None and thread.is_alive())

    @property
    def worker_thread(self) -> threading.Thread | None:
        return self._worker_thread

    def wait_for_stopped(self, timeout_ms: int = 1000) -> bool:
        thread = self._worker_thread
        if thread is None or not thread.is_alive():
            self._worker_thread = None
            return True
        if thread is threading.current_thread():
            return False
        thread.join(max(0, int(timeout_ms)) / 1000.0)
        stopped = not thread.is_alive()
        if stopped and self._worker_thread is thread:
            self._worker_thread = None
        return stopped

    def _start_pending(self) -> None:
        if self._closed or self._active or self._pending is None:
            return
        token, request, force = self._pending
        self._pending = None
        self._active = True
        cancel_event = threading.Event()
        self._cancel_event = cancel_event
        self.busy_changed.emit(True)
        thread = threading.Thread(
            target=self._run_render,
            args=(token, request, force, cancel_event),
            name="document-word-preview",
            daemon=True,
        )
        self._worker_thread = thread
        thread.start()

    def _run_render(
        self,
        token: int,
        request: DocumentWordPreviewRequest,
        force: bool,
        cancel_event: threading.Event,
    ) -> None:
        try:
            if cancel_event.is_set():
                result = _cancelled_result(request)
            elif self._renderer_accepts_cancel_event:
                result = self._renderer(
                    request,
                    force=force,
                    cancel_event=cancel_event,
                )
            else:
                result = self._renderer(request, force=force)
        except Exception as exc:
            result = DocumentWordPreviewResult(
                status="render_failed",
                provider_id=request.provider_id,
                variant_id=request.variant_id,
                issues=(str(exc),),
            )
        try:
            self._thread_finished.emit(token, result)
        except RuntimeError:
            return

    def _on_thread_finished(
        self,
        token: int,
        result: DocumentWordPreviewResult,
    ) -> None:
        self._active = False
        self._worker_thread = None
        self._cancel_event = None
        if self._closed:
            return
        if token == self._generation:
            if result.ready:
                self.result_ready.emit(result)
            else:
                self.render_failed.emit(result)
        if self._pending is not None:
            self._start_pending()
        else:
            self.busy_changed.emit(False)


def _accepts_cancel_event(renderer: PreviewRenderer) -> bool:
    try:
        parameters = inspect.signature(renderer).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.name == "cancel_event"
        or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


def _cancelled_result(
    request: DocumentWordPreviewRequest,
) -> DocumentWordPreviewResult:
    return DocumentWordPreviewResult(
        status="cancelled",
        provider_id=request.provider_id,
        variant_id=request.variant_id,
    )


__all__ = ["DocumentWordPreviewController"]
