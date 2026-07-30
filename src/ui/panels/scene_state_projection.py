from __future__ import annotations

from src.config.builtin_scenes import list_builtin_scene_resources
from src.config.scene import SceneWorkspace
from src.config.scene_surface_registry import (
    scene_surface_for_scene,
    scene_uses_exam_paper_surface,
)


SCENE_SELECTOR_GROUP_PREFIX = "__scene_group__:"
SCENE_SELECTOR_MY_GROUP = f"{SCENE_SELECTOR_GROUP_PREFIX}mine"
SCENE_SELECTOR_BUILTIN_GROUP = f"{SCENE_SELECTOR_GROUP_PREFIX}builtin"


def is_scene_selector_group(value: object) -> bool:
    return str(value or "").strip().startswith(SCENE_SELECTOR_GROUP_PREFIX)


def builtin_scene_id_set() -> set[str]:
    return {
        scene_id
        for _mode_id, scene_id, _path in list_builtin_scene_resources()
    }


def scene_is_exam(
    scene: SceneWorkspace | None,
    *,
    mode_id: object = "",
) -> bool:
    return scene_uses_exam_paper_surface(scene, mode_id=mode_id)


def scene_should_show_content_card(
    scene: SceneWorkspace | None,
    *,
    mode_id: object = "",
) -> bool:
    surface = scene_surface_for_scene(scene, mode_id=mode_id)
    if scene is None or not surface.hides_content_card_without_material_contract:
        return True
    return scene_has_material_content_contract(scene)


def scene_has_material_content_contract(scene: SceneWorkspace | None) -> bool:
    if scene is None:
        return False
    profile = getattr(scene, "input_source_profile", None)
    switches = getattr(scene, "module_switches", {}) or {}
    watermark = getattr(scene, "watermark", None)
    return bool(
        switches.get("content_fill", False)
        or getattr(profile, "require_material_package", False)
        or str(getattr(profile, "material_schema_id", "") or "").strip()
        or any(
            str(item or "").strip()
            for item in getattr(profile, "material_schema_ids", ()) or ()
        )
        or any(
            str(item or "").strip()
            for item in getattr(profile, "required_material_fields", ()) or ()
        )
        or any(
            str(item or "").strip()
            for item in getattr(profile, "required_image_roles", ()) or ()
        )
        or bool(getattr(watermark, "enabled", False))
        or str(getattr(watermark, "text", "") or "").strip()
    )
