from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .document_execution_state import DocumentExecutionTopology


@dataclass(frozen=True, slots=True)
class DocumentExecutionAdapters:
    single: Callable[[], None]
    files: Callable[[], None]
    records: Callable[[], None]
    retry_records: Callable[[], None]
    cancel: Callable[[], None]


class DocumentExecutionCoordinator:
    """Select the execution adapter from inferred topology.

    It does not own the production runners. Its boundary is dispatch,
    cancellation, retry capability and blocked-topology reporting.
    """

    def __init__(
        self,
        *,
        topology: Callable[[], DocumentExecutionTopology],
        adapters: DocumentExecutionAdapters,
        publish_blocked: Callable[[str], None] | None = None,
    ) -> None:
        self._topology = topology
        self._adapters = adapters
        self._publish_blocked = publish_blocked or (lambda _reason: None)

    def start(self) -> None:
        topology = self._topology()
        if topology.kind == "single":
            # One selected material record is a single-output product shape,
            # while the record adapter remains the safe runtime path for
            # profile selection, generated documents and per-record isolation.
            if topology.record_count == 1:
                self._adapters.records()
            else:
                self._adapters.single()
            return
        if topology.kind == "files":
            self._adapters.files()
            return
        if topology.kind == "records":
            self._adapters.records()
            return
        self._publish_blocked(
            topology.blocking_reason or "当前输入关系尚不能执行"
        )

    def retry(self) -> None:
        if self._topology().kind == "records":
            self._adapters.retry_records()

    def cancel(self) -> None:
        self._adapters.cancel()


__all__ = [
    "DocumentExecutionAdapters",
    "DocumentExecutionCoordinator",
]
