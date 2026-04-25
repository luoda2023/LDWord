"""Style variant helpers — manage section-specific style overrides.

Core rule: "key exists in styles → independent; key absent → inherits body".

This module provides the single source of truth for which style keys
are section variants and how to query / toggle their override state.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.section_semantics import SECTION_STYLE_KEY_MAP
from src.config.template import StyleConfig, TemplateConfig


@dataclass(frozen=True)
class StyleVariantMeta:
    """Metadata for a section-specific paragraph style variant."""

    key: str              # e.g. "references_body"
    section_type: str     # e.g. "references"
    label: str            # UI display name, e.g. "参考文献"
    description: str      # tooltip / help text


STYLE_VARIANTS: tuple[StyleVariantMeta, ...] = (
    StyleVariantMeta(
        key="references_body",
        section_type="references",
        label="参考文献",
        description="参考文献段落的字体、字号、缩进和行距。",
    ),
    StyleVariantMeta(
        key="acknowledgment_body",
        section_type="acknowledgment",
        label="致谢",
        description="致谢段落的排版样式。",
    ),
    StyleVariantMeta(
        key="abstract_body",
        section_type="abstract_cn",
        label="摘要",
        description="中英文摘要段落的排版样式。",
    ),
    StyleVariantMeta(
        key="appendix_body",
        section_type="appendix",
        label="附录",
        description="附录段落的排版样式。",
    ),
    StyleVariantMeta(
        key="resume_body",
        section_type="resume",
        label="个人简历",
        description="个人简历段落的排版样式。",
    ),
)

VARIANT_KEY_TO_META: dict[str, StyleVariantMeta] = {
    v.key: v for v in STYLE_VARIANTS
}


def get_effective_style(template: TemplateConfig, variant_key: str) -> StyleConfig:
    """Return the effective StyleConfig for *variant_key*.

    If the variant has an independent override, return it.
    Otherwise fall back to ``styles["body"]`` (or a fresh default).
    """
    override = template.styles.get(variant_key)
    if override is not None:
        return override

    body = template.styles.get("body")
    if body is not None:
        return body

    return template.styles.get("normal") or StyleConfig()


def is_variant_overridden(template: TemplateConfig, variant_key: str) -> bool:
    """Return ``True`` when the variant has its own independent style."""
    return variant_key in template.styles


def enable_variant_override(template: TemplateConfig, variant_key: str) -> StyleConfig:
    """Create an independent style for *variant_key* (deep-copied from body).

    Returns the newly created ``StyleConfig`` so the caller can bind UI to it.
    """
    if variant_key in template.styles:
        return template.styles[variant_key]

    body = get_effective_style(template, "body")
    independent = deepcopy(body)
    template.styles[variant_key] = independent
    return independent


def disable_variant_override(template: TemplateConfig, variant_key: str) -> None:
    """Remove the independent style, making the variant inherit from body."""
    template.styles.pop(variant_key, None)


# ---------------------------------------------------------------------------
# Scene-aware variant API (section_styles lives in SceneWorkspace)
# ---------------------------------------------------------------------------

def get_effective_section_style(
    scene, template: TemplateConfig, variant_key: str,
):
    """Return effective StyleConfig: scene override → template body → default."""
    from src.config.scene import SceneWorkspace
    if isinstance(scene, SceneWorkspace) and variant_key in scene.section_styles:
        return scene.section_styles[variant_key]
    return get_effective_style(template, variant_key)


def is_section_style_overridden(scene, variant_key: str) -> bool:
    """Check if the scene has an independent style for this variant."""
    return variant_key in getattr(scene, "section_styles", {})


def enable_section_style_override(scene, template: TemplateConfig, variant_key: str):
    """Create an independent section style in scene (deep-copied from template body)."""
    if variant_key in scene.section_styles:
        return scene.section_styles[variant_key]
    body = get_effective_style(template, "body")
    independent = deepcopy(body)
    scene.section_styles[variant_key] = independent
    return independent


def disable_section_style_override(scene, variant_key: str) -> None:
    """Remove the independent section style, reverting to body."""
    if hasattr(scene, "section_styles"):
        scene.section_styles.pop(variant_key, None)


__all__ = [
    "StyleVariantMeta",
    "STYLE_VARIANTS",
    "VARIANT_KEY_TO_META",
    "get_effective_style",
    "is_variant_overridden",
    "enable_variant_override",
    "disable_variant_override",
    "get_effective_section_style",
    "is_section_style_overridden",
    "enable_section_style_override",
    "disable_section_style_override",
]
