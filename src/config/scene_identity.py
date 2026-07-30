"""Canonical allocation rules for user-owned Scene identities."""

from __future__ import annotations

from src.config.scene_id_rules import (
    MAX_SCENE_ID_LENGTH,
    require_canonical_scene_id,
    safe_scene_file_stem,
)


class SceneIdentityAllocationError(RuntimeError):
    """No collision-free Scene identity is available within the search bound."""


def allocate_scene_id(
    *,
    name: str,
    mode_id: str,
    max_attempts: int = 1000,
) -> str:
    """Allocate a case-insensitive collision-free ID within one work mode.

    Both built-in and user JSON entries reserve their identities.  Entries in
    other work modes deliberately do not: Scene identity is mode-scoped.
    """

    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")

    # Library access belongs only to allocation; pure ID rules live in
    # ``scene_id_rules`` so persistence code never needs to import this module.
    from src.config.library import list_scene_entries

    occupied = {
        str(entry.config_id or "").casefold()
        for entry in list_scene_entries(mode_id=mode_id)
        if str(entry.config_id or "").strip()
    }
    base_id = safe_scene_file_stem(name)
    for index in range(1, max_attempts + 1):
        candidate = _indexed_scene_id(base_id, index)
        if candidate.casefold() not in occupied:
            return candidate
    raise SceneIdentityAllocationError(
        "scene_id_allocation_exhausted:"
        f" mode={mode_id}; base={base_id}; attempts={max_attempts}"
    )


def _indexed_scene_id(base_id: str, index: int) -> str:
    if index == 1:
        return base_id
    suffix = f"_{index}"
    prefix = base_id[: MAX_SCENE_ID_LENGTH - len(suffix)].rstrip(" ._")
    return f"{prefix or 'plan'}{suffix}"


__all__ = [
    "SceneIdentityAllocationError",
    "allocate_scene_id",
    "require_canonical_scene_id",
    "safe_scene_file_stem",
]
