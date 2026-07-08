from __future__ import annotations

from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.ui.panels.workbench.scene_presets import SCENE_METAS
from src.ui.panels.scene_style_override_service import (
    scene_style_variants_for_scene,
    scene_uses_reference_format as _scene_uses_reference_format,
)


SCENE_SELECTOR_GROUP_PREFIX = "__scene_group__:"
SCENE_SELECTOR_MY_GROUP = f"{SCENE_SELECTOR_GROUP_PREFIX}mine"
SCENE_SELECTOR_BUILTIN_GROUP = f"{SCENE_SELECTOR_GROUP_PREFIX}builtin"


def safe_scene_file_stem(value: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(ch if ch not in forbidden else "_" for ch in str(value or "").strip())
    cleaned = cleaned.strip(" ._")
    return cleaned or "scene"


def is_scene_selector_group(value: object) -> bool:
    return str(value or "").strip().startswith(SCENE_SELECTOR_GROUP_PREFIX)


def builtin_scene_id_set() -> set[str]:
    return {str(meta.scene_id or "").strip() for meta in SCENE_METAS}


def scene_is_exam(scene: SceneWorkspace | None) -> bool:
    if scene is None:
        return False
    parts = (
        getattr(scene, "scene_id", ""),
        getattr(scene, "category", ""),
        getattr(scene, "category_label", ""),
        getattr(scene, "name", ""),
        getattr(scene, "description", ""),
    )
    text = " ".join(str(part or "").lower() for part in parts)
    return any(
        token in text
        for token in (
            "exam",
            "exam paper",
            "test paper",
            "test_paper",
            "question paper",
            "question_paper",
            "试卷",
            "考试",
            "测验",
            "试题",
        )
    )


def scene_uses_reference_format(scene: SceneWorkspace | None) -> bool:
    return _scene_uses_reference_format(scene)


def generic_style_variants_for_scene(
    scene: SceneWorkspace | None,
    template: TemplateConfig | None = None,
):
    return scene_style_variants_for_scene(scene, template)


def scene_should_show_content_card(scene: SceneWorkspace | None) -> bool:
    if scene is None or not scene_is_exam(scene):
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
