"""Service helpers for scene section-style override workflows."""

from __future__ import annotations

import re
from collections.abc import Sequence

from src.config.builtin_templates import create_builtin_template
from src.config.library import load_template_from_library
from src.config.style_variant_semantics import (
    STYLE_VARIANTS,
    VARIANT_KEY_TO_META,
    StyleVariantMeta,
    build_section_style_override_projection,
    build_section_style_preview_projection,
    disable_section_style_override,
    enable_section_style_override,
    get_effective_section_style,
    is_section_style_overridden,
)
from src.config.template import TemplateConfig
from src.config.style_difference_projection import build_style_difference_projection


def resolve_scene_style_template(scene, template: TemplateConfig | None = None) -> TemplateConfig:
    """Return the template used as the baseline for scene section styles."""

    if template is not None:
        return template
    template_id = str(getattr(scene, "template_id", "") or "default")
    try:
        return load_template_from_library(template_id)
    except Exception:
        return create_builtin_template("default")


def scene_style_variants_for_scene(
    scene,
    template: TemplateConfig | None = None,
    *,
    include_existing_overrides: bool = True,
) -> tuple[StyleVariantMeta, ...]:
    """Return section-style variants the scene can actually manage in this UI.

    Exam scenes use a separate exam-paper assembly model. They should not inherit
    thesis-like generic section candidates unless the active template or an
    existing override already exposes a known section-style key.
    """

    if scene is None:
        return STYLE_VARIANTS

    hidden_keys = _hidden_style_variant_keys_for_scene(scene)
    if _scene_uses_exam_paper_model(scene):
        baseline = resolve_scene_style_template(scene, template)
        visible_keys = {
            key
            for key in getattr(baseline, "styles", {})
            if key in VARIANT_KEY_TO_META
        }
        if include_existing_overrides:
            visible_keys.update(
                key
                for key in getattr(scene, "section_styles", {})
                if key in VARIANT_KEY_TO_META
            )
    else:
        visible_keys = {variant.key for variant in STYLE_VARIANTS}

    visible_keys.difference_update(hidden_keys)
    return tuple(variant for variant in STYLE_VARIANTS if variant.key in visible_keys)


def scene_section_effective_style(scene, template: TemplateConfig | None, variant_key: str):
    if scene is None or not variant_key:
        return None
    baseline = resolve_scene_style_template(scene, template)
    return get_effective_section_style(scene, baseline, variant_key)


def scene_section_style_override_projection(
    scene,
    template: TemplateConfig | None,
    variant_key: str,
):
    if scene is None or not variant_key:
        return None
    baseline = resolve_scene_style_template(scene, template)
    return build_section_style_override_projection(scene, baseline, variant_key)


def scene_section_style_preview_projection(
    scene,
    template: TemplateConfig | None,
    variant_key: str,
):
    if scene is None or not variant_key:
        return None
    baseline = resolve_scene_style_template(scene, template)
    return build_section_style_preview_projection(scene, baseline, variant_key)


def scene_section_style_comparison_projection(
    scene,
    template: TemplateConfig | None,
    variant_key: str,
):
    if scene is None or not variant_key:
        return None
    baseline = resolve_scene_style_template(scene, template)
    return build_style_difference_projection(scene, baseline, variant_key)


def set_scene_section_style_override(
    scene,
    template: TemplateConfig | None,
    variant_key: str,
    enabled: bool,
):
    """Enable or disable a scene section-style override."""

    if scene is None or not variant_key:
        return None
    if enabled:
        baseline = resolve_scene_style_template(scene, template)
        return enable_section_style_override(scene, baseline, variant_key)
    disable_section_style_override(scene, variant_key)
    return None


def restore_scene_section_style_to_template(scene, variant_key: str) -> bool:
    """Remove a scene override so the section follows the template again."""

    if scene is None or not variant_key:
        return False
    if not is_section_style_overridden(scene, variant_key):
        return False
    disable_section_style_override(scene, variant_key)
    return True


def restore_all_scene_section_styles_to_template(
    scene,
    variants: Sequence[StyleVariantMeta] = STYLE_VARIANTS,
) -> tuple[str, ...]:
    """Remove every known scene section-style override."""

    if scene is None:
        return ()
    restored: list[str] = []
    for variant in variants:
        if not is_section_style_overridden(scene, variant.key):
            continue
        disable_section_style_override(scene, variant.key)
        restored.append(variant.key)
    return tuple(restored)


def sync_disabled_section_style_overrides(
    scene,
    variants: Sequence[StyleVariantMeta] = STYLE_VARIANTS,
) -> tuple[str, ...]:
    """Compatibility no-op: old scope gates no longer delete format exceptions."""

    return ()


def _hidden_style_variant_keys_for_scene(scene) -> set[str]:
    if scene_uses_reference_format(scene):
        return {"references_body"}
    return set()


def scene_uses_reference_format(scene) -> bool:
    if scene is None or _scene_uses_exam_paper_model(scene):
        return False
    text = _scene_search_text(scene)
    return _scene_text_has_any(
        text,
        latin_tokens=(
            "academic",
            "thesis",
            "journal",
        ),
        cjk_tokens=(
            "论文",
            "学术",
            "期刊",
            "投稿",
        ),
    )


def _scene_uses_exam_paper_model(scene) -> bool:
    if scene is None:
        return False
    text = _scene_search_text(scene)
    return _scene_text_has_any(
        text,
        latin_tokens=(
            "exam_paper",
            "exam paper",
            "test paper",
            "test_paper",
            "question paper",
            "question_paper",
            "exam",
        ),
        cjk_tokens=(
            "试卷",
            "考试",
            "测验",
            "试题",
        ),
    )


def _scene_search_text(scene) -> str:
    profile = getattr(scene, "compliance_profile", None)
    parts = (
        getattr(scene, "scene_id", ""),
        getattr(scene, "category", ""),
        getattr(scene, "category_label", ""),
        getattr(scene, "name", ""),
        getattr(scene, "description", ""),
        getattr(profile, "profile_id", ""),
        getattr(profile, "rule_family", ""),
        getattr(profile, "count_profile_id", ""),
    )
    return " ".join(str(part or "").lower() for part in parts)


def _scene_text_has_any(
    text: str,
    *,
    latin_tokens: Sequence[str] = (),
    cjk_tokens: Sequence[str] = (),
) -> bool:
    normalized = str(text or "").lower()
    if any(str(token or "") in normalized for token in cjk_tokens if token):
        return True
    for token in latin_tokens:
        cleaned = str(token or "").strip().lower()
        if not cleaned:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(cleaned)}(?![a-z0-9])"
        if re.search(pattern, normalized):
            return True
    return False


__all__ = [
    "resolve_scene_style_template",
    "restore_all_scene_section_styles_to_template",
    "restore_scene_section_style_to_template",
    "scene_section_effective_style",
    "scene_section_style_comparison_projection",
    "scene_section_style_override_projection",
    "scene_section_style_preview_projection",
    "scene_style_variants_for_scene",
    "scene_uses_reference_format",
    "set_scene_section_style_override",
    "sync_disabled_section_style_overrides",
]
