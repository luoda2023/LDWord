"""Global single-owner lease for Form document production."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class ExecutionLease:
    execution_id: str
    session_id: str
    acquired_at: str


class ExecutionLeaseManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._current: ExecutionLease | None = None

    @property
    def current(self) -> ExecutionLease | None:
        with self._lock:
            return self._current

    def acquire(self, lease: ExecutionLease) -> bool:
        with self._lock:
            if self._current is not None:
                return False
            self._current = lease
            return True

    def release(self, execution_id: str) -> bool:
        with self._lock:
            if self._current is None or self._current.execution_id != execution_id:
                return False
            self._current = None
            return True


GLOBAL_EXECUTION_LEASE = ExecutionLeaseManager()

__all__ = ["ExecutionLease", "ExecutionLeaseManager", "GLOBAL_EXECUTION_LEASE"]
