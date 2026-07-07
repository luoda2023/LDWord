"""Service helpers for scene processing-scope workflows."""

from __future__ import annotations

from collections.abc import Mapping


def apply_scene_scope_zone_states(
    scene,
    zone_states: Mapping[str, bool],
) -> tuple[str, ...]:
    """Write legacy processing-zone states without touching format exceptions."""

    if scene is None:
        return ()
    sections = getattr(getattr(scene, "format_scope", None), "sections", None)
    if sections is None:
        return ()

    for zone_id, enabled in zone_states.items():
        key = str(zone_id or "").strip()
        if key:
            sections[key] = bool(enabled)
    return ()


__all__ = ["apply_scene_scope_zone_states"]
