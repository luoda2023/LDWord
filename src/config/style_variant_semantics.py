"""Template-owned paragraph style variants."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.template import StyleConfig, TemplateConfig


@dataclass(frozen=True)
class StyleVariantMeta:
    key: str
    section_type: str
    label: str
    description: str


STYLE_VARIANTS: tuple[StyleVariantMeta, ...] = (
    StyleVariantMeta(
        "references_body",
        "references",
        "参考文献",
        "参考文献段落的字体、字号、缩进和行距。",
    ),
    StyleVariantMeta(
        "acknowledgment_body",
        "acknowledgment",
        "致谢",
        "致谢段落的排版样式。",
    ),
    StyleVariantMeta(
        "abstract_body",
        "abstract_cn",
        "摘要",
        "中英文摘要段落的排版样式。",
    ),
    StyleVariantMeta(
        "appendix_body",
        "appendix",
        "附录",
        "附录段落的排版样式。",
    ),
    StyleVariantMeta(
        "resume_body",
        "resume",
        "个人简历",
        "个人简历段落的排版样式。",
    ),
)

VARIANT_KEY_TO_META: dict[str, StyleVariantMeta] = {
    variant.key: variant for variant in STYLE_VARIANTS
}


def get_effective_style(
    template: TemplateConfig,
    variant_key: str,
) -> StyleConfig:
    override = template.styles.get(variant_key)
    if override is not None:
        return override
    return (
        template.styles.get("body")
        or template.styles.get("normal")
        or StyleConfig()
    )


def is_variant_overridden(
    template: TemplateConfig,
    variant_key: str,
) -> bool:
    return variant_key in template.styles


def enable_variant_override(
    template: TemplateConfig,
    variant_key: str,
) -> StyleConfig:
    if variant_key in template.styles:
        return template.styles[variant_key]
    style = deepcopy(get_effective_style(template, variant_key))
    template.styles[variant_key] = style
    return style


def disable_variant_override(
    template: TemplateConfig,
    variant_key: str,
) -> None:
    template.styles.pop(variant_key, None)


__all__ = [
    "StyleVariantMeta",
    "STYLE_VARIANTS",
    "VARIANT_KEY_TO_META",
    "get_effective_style",
    "is_variant_overridden",
    "enable_variant_override",
    "disable_variant_override",
]
