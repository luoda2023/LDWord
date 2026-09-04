from __future__ import annotations

import logging


_LOGGER = logging.getLogger(__name__)


def log_best_effort_shutdown_failure(owner: str, action: str, exc: Exception) -> None:
    _LOGGER.warning(
        "Workbench %s ignored %s failure during best-effort shutdown: %s",
        owner,
        action,
        exc,
        exc_info=exc,
    )


def log_path_fallback_failure(owner: str, action: str, raw_path: str | None, exc: Exception) -> None:
    _LOGGER.warning(
        "Workbench %s used fallback after %s failure for %r: %s",
        owner,
        action,
        raw_path,
        exc,
        exc_info=exc,
    )


def log_best_effort_state_sync_failure(owner: str, action: str, exc: Exception) -> None:
    _LOGGER.warning(
        "Workbench %s ignored %s failure during best-effort state sync: %s",
        owner,
        action,
        exc,
        exc_info=exc,
    )


__all__ = [
    "log_best_effort_shutdown_failure",
    "log_best_effort_state_sync_failure",
    "log_path_fallback_failure",
]
