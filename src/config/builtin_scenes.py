"""Cycle-free registry for canonical built-in plan resources.

Built-in plan behavior lives only in complete, mode-scoped JSON resources
under ``config_library/plans/<mode>/builtin``.  Python exposes identities and
fresh materialization; it does not reconstruct plan content from defaults.
"""

from __future__ import annotations

from pathlib import Path

from src.config.canonical_resource import assert_non_symbolic_resource_path
from src.config.loader import load_scene
from src.config.scene import SceneWorkspace


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CANONICAL_SCENE_ROOT = _PROJECT_ROOT / "config_library" / "plans"

_BUILTIN_SCENE_RESOURCES: tuple[tuple[str, str], ...] = (
    ("custom", "custom"),
    ("engineering", "engineering"),
    ("exam", "exam"),
    ("exam", "exam_quiz"),
    ("exam", "exam_term"),
    ("thesis", "thesis"),
    ("bidding", "bidding"),
    ("official", "official"),
    ("technical", "technical"),
    ("report", "report"),
)
_PRIMARY_SCENE_MODES = {
    scene_id: mode_id for mode_id, scene_id in _BUILTIN_SCENE_RESOURCES
}


def builtin_scene_resource_path(
    scene_id: str,
    *,
    mode_id: str | None = None,
) -> Path:
    """Return the exact canonical JSON path for one built-in plan identity."""

    normalized_id = str(scene_id or "").strip()
    normalized_mode = str(mode_id or "").strip() or _PRIMARY_SCENE_MODES.get(
        normalized_id,
        "",
    )
    if (normalized_mode, normalized_id) not in _BUILTIN_SCENE_RESOURCES:
        qualifier = f"{normalized_mode}/" if normalized_mode else ""
        raise ValueError(f"unknown built-in plan id: {qualifier}{normalized_id}")
    return (
        _CANONICAL_SCENE_ROOT
        / normalized_mode
        / "builtin"
        / f"{normalized_id}.json"
    )


def create_builtin_scene(
    scene_id: str,
    *,
    mode_id: str | None = None,
) -> SceneWorkspace:
    """Load a fresh plan from its complete canonical JSON resource."""

    path = builtin_scene_resource_path(scene_id, mode_id=mode_id)
    assert_non_symbolic_resource_path(
        path,
        _CANONICAL_SCENE_ROOT,
        resource_label="plan",
    )
    return load_scene(path)


def has_builtin_scene(scene_id: str, *, mode_id: str | None = None) -> bool:
    normalized_id = str(scene_id or "").strip()
    if mode_id is None:
        return normalized_id in _PRIMARY_SCENE_MODES
    return (str(mode_id or "").strip(), normalized_id) in _BUILTIN_SCENE_RESOURCES


def list_builtin_scene_resources() -> tuple[tuple[str, str, Path], ...]:
    """Return every authoritative mode/id/path resource slot."""

    return tuple(
        (
            mode_id,
            scene_id,
            builtin_scene_resource_path(scene_id, mode_id=mode_id),
        )
        for mode_id, scene_id in _BUILTIN_SCENE_RESOURCES
    )


def canonical_scene_root() -> Path:
    """Return the authoritative boundary used for bundled plan paths."""

    return _CANONICAL_SCENE_ROOT


__all__ = [
    "builtin_scene_resource_path",
    "canonical_scene_root",
    "create_builtin_scene",
    "has_builtin_scene",
    "list_builtin_scene_resources",
]
