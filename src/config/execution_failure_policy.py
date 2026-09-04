"""Canonical persisted execution-failure policy vocabulary."""

from __future__ import annotations


EXECUTION_FAILURE_POLICY_VALUES: tuple[str, ...] = ("warn", "block", "confirm")


def normalize_execution_failure_policy(value: object) -> str:
    """Return a canonical policy or reject corrupted configuration.

    The project is unreleased and persists only the canonical vocabulary, so
    aliases and permissive fallback would create a second interpretation path.
    """

    normalized = str(value or "").strip().lower()
    if normalized not in EXECUTION_FAILURE_POLICY_VALUES:
        display_value = str(value or "").strip() or "<empty>"
        raise ValueError(f"execution_failure_policy_invalid:{display_value}")
    return normalized


def execution_failure_policy_issue(value: object) -> str:
    """Return a stable integrity issue for an invalid persisted policy."""

    try:
        normalize_execution_failure_policy(value)
    except ValueError as exc:
        return str(exc)
    return ""


__all__ = [
    "EXECUTION_FAILURE_POLICY_VALUES",
    "execution_failure_policy_issue",
    "normalize_execution_failure_policy",
]
