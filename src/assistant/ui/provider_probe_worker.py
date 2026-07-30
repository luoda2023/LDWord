"""Background worker for the user-initiated provider connection test."""

from __future__ import annotations

from threading import Thread

from src.assistant.application.provider_probe import probe_provider
from src.qt_api import QObject, Signal


class ProviderProbeWorker(QObject):
    finished = Signal(object)

    def __init__(self, gateway, *, model_id: str, parent=None) -> None:
        super().__init__(parent)
        self.gateway = gateway
        self.model_id = model_id
        self._thread: Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Provider probe is already running")
        self._thread = Thread(target=self._run, name="assistant-provider-probe", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self.gateway.cancel()

    def shutdown(self, timeout_ms: int = 3000) -> bool:
        self.cancel()
        if self._thread is None:
            return True
        self._thread.join(max(0, timeout_ms) / 1000)
        return not self._thread.is_alive()

    def _run(self) -> None:
        try:
            result = probe_provider(self.gateway, model_id=self.model_id)
        except Exception as exc:
            from src.assistant.application.provider_probe import ProviderProbeResult

            result = ProviderProbeResult(False, str(exc) or type(exc).__name__)
        self.finished.emit(result)


__all__ = ["ProviderProbeWorker"]
