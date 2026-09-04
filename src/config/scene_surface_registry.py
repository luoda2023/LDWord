"""Fixed surface rules for scene-specific runtime and panel options.

This module intentionally keeps these rules out of persisted scene JSON. The
selected scene/function maps to a fixed surface in code. Runtime and UI both
consume the same config-owned classification without a lower-layer UI import.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.execution_feature_state import execution_plan_is_enabled
from src.config.work_mode import resolve_work_mode_id


@dataclass(frozen=True, slots=True)
class SceneSurfaceSpec:
    surface_id: str
    uses_exam_paper_model: bool = False
    uses_official_document_model: bool = False
    hides_content_card_without_material_contract: bool = False


GENERAL_SCENE_SURFACE = SceneSurfaceSpec(surface_id="general")

EXAM_PAPER_SCENE_SURFACE = SceneSurfaceSpec(
    surface_id="exam_paper",
    uses_exam_paper_model=True,
    hides_content_card_without_material_contract=True,
)

OFFICIAL_DOCUMENT_SCENE_SURFACE = SceneSurfaceSpec(
    surface_id="official_document",
    uses_official_document_model=True,
)


_SCENE_SURFACE_BY_MODE_ID: dict[str, SceneSurfaceSpec] = {
    "exam": EXAM_PAPER_SCENE_SURFACE,
    "official": OFFICIAL_DOCUMENT_SCENE_SURFACE,
}


def scene_surface_for_scene(
    scene: object | None,
    *,
    mode_id: object = "",
) -> SceneSurfaceSpec:
    if not execution_plan_is_enabled(scene):
        return GENERAL_SCENE_SURFACE
    has_declared_mode = bool(
        _clean_scene_key(mode_id)
        or _clean_scene_key(getattr(scene, "mode_id", ""))
    )
    if has_declared_mode:
        canonical_mode = resolve_work_mode_id(
            scene,
            requested_mode_id=mode_id,
        )
        return _SCENE_SURFACE_BY_MODE_ID.get(
            canonical_mode,
            GENERAL_SCENE_SURFACE,
        )

    if scene is None:
        return GENERAL_SCENE_SURFACE

    canonical_mode = resolve_work_mode_id(scene)
    return _SCENE_SURFACE_BY_MODE_ID.get(canonical_mode, GENERAL_SCENE_SURFACE)


def scene_uses_exam_paper_surface(
    scene: object | None,
    *,
    mode_id: object = "",
) -> bool:
    return scene_surface_for_scene(
        scene,
        mode_id=mode_id,
    ).uses_exam_paper_model


def scene_uses_official_document_surface(
    scene: object | None,
    *,
    mode_id: object = "",
) -> bool:
    return scene_surface_for_scene(
        scene,
        mode_id=mode_id,
    ).uses_official_document_model


def scene_uses_plan_preview_surface(
    scene: object | None,
    *,
    mode_id: object = "",
) -> bool:
    surface = scene_surface_for_scene(scene, mode_id=mode_id)
    return surface.uses_exam_paper_model or surface.uses_official_document_model


def _clean_scene_key(value: object) -> str:
    return str(value or "").strip().lower()


__all__ = [
    "EXAM_PAPER_SCENE_SURFACE",
    "GENERAL_SCENE_SURFACE",
    "OFFICIAL_DOCUMENT_SCENE_SURFACE",
    "SceneSurfaceSpec",
    "scene_surface_for_scene",
    "scene_uses_exam_paper_surface",
    "scene_uses_official_document_surface",
    "scene_uses_plan_preview_surface",
]
