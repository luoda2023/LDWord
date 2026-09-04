"""Thread-safe cancellation token adapted from Alavette Flow (MIT)."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock


class AssistantCancellationToken:
    def __init__(self) -> None:
        self._event = Event()
        self._callbacks: dict[int, Callable[[], object]] = {}
        self._callback_lock = Lock()
        self._next_callback_id = 0

    def cancel(self) -> None:
        if self._event.is_set():
            return
        self._event.set()
        with self._callback_lock:
            callbacks = tuple(self._callbacks.values())
            self._callbacks.clear()
        for callback in callbacks:
            try:
                callback()
            except Exception:
                continue

    def cancelled(self) -> bool:
        return self._event.is_set()

    def register_cancel_callback(self, callback: Callable[[], object]) -> Callable[[], None]:
        if not callable(callback):
            return lambda: None
        with self._callback_lock:
            if self._event.is_set():
                callback_id = -1
            else:
                self._next_callback_id += 1
                callback_id = self._next_callback_id
                self._callbacks[callback_id] = callback
        if callback_id < 0:
            try:
                callback()
            except Exception:
                pass
            return lambda: None

        def unregister() -> None:
            with self._callback_lock:
                self._callbacks.pop(callback_id, None)

        return unregister


def is_cancelled(token: AssistantCancellationToken | None) -> bool:
    return bool(token is not None and token.cancelled())


__all__ = ["AssistantCancellationToken", "is_cancelled"]
