"""Shared heading-style resolution semantics for UI previews and runtime."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, MutableMapping

from src.config.template import StyleConfig, TemplateConfig

NON_NUMBERED_HEADING_STYLE_KEY = "non_numbered_heading"
NON_NUMBERED_HEADING_INHERIT_HEADING1 = "inherit_heading1"
NON_NUMBERED_HEADING_CUSTOM = "custom"


def _styles_view(template_or_styles: Any) -> Mapping[str, StyleConfig]:
    if isinstance(template_or_styles, Mapping):
        return template_or_styles
    styles = getattr(template_or_styles, "styles", None)
    if isinstance(styles, Mapping):
        return styles
    return template_or_styles


def _mutable_styles_view(
    template_or_styles: Any,
) -> MutableMapping[str, StyleConfig]:
    if isinstance(template_or_styles, MutableMapping):
        return template_or_styles
    styles = getattr(template_or_styles, "styles", None)
    if isinstance(styles, MutableMapping):
        return styles
    return template_or_styles


def resolve_heading_style(
    template_or_styles: TemplateConfig | Mapping[str, StyleConfig] | object,
    level: int,
    *,
    include_body_fallback: bool = True,
) -> StyleConfig | None:
    """Return the effective heading style for ``level``.

    Resolution order:
    ``headingN`` -> ``heading`` -> ``body`` (optional) -> ``normal``.
    """

    styles = _styles_view(template_or_styles)
    candidates = [f"heading{int(level)}", "heading"]
    if include_body_fallback:
        candidates.append("body")
    candidates.append("normal")

    for key in candidates:
        style = styles.get(key)
        if style is not None:
            return deepcopy(style)
    return None


def resolve_heading_style_source(
    template_or_styles: TemplateConfig | Mapping[str, StyleConfig] | object,
    level: int,
    *,
    include_body_fallback: bool = True,
) -> str | None:
    styles = _styles_view(template_or_styles)
    candidates = [f"heading{int(level)}", "heading"]
    if include_body_fallback:
        candidates.append("body")
    candidates.append("normal")

    for key in candidates:
        if styles.get(key) is not None:
            return key
    return None


def ensure_heading_style_override(
    template_or_styles: TemplateConfig | MutableMapping[str, StyleConfig] | object,
    level: int,
) -> StyleConfig:
    """Materialize an editable ``headingN`` style seeded from the fallback chain."""

    styles = _mutable_styles_view(template_or_styles)
    key = f"heading{int(level)}"
    if key in styles:
        return styles[key]

    seed = resolve_heading_style(styles, level, include_body_fallback=True)
    styles[key] = deepcopy(seed) if seed is not None else StyleConfig()
    return styles[key]


def remove_heading_style_override(
    template_or_styles: TemplateConfig | MutableMapping[str, StyleConfig] | object,
    level: int,
) -> bool:
    """Remove the ``headingN`` style so the level falls back to the inheritance chain."""
    styles = _mutable_styles_view(template_or_styles)
    key = f"heading{int(level)}"
    if key in styles:
        del styles[key]
        return True
    return False


def normalize_non_numbered_heading_style_mode(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"custom", "independent", "override", "独立", "独立设置"}:
        return NON_NUMBERED_HEADING_CUSTOM
    return NON_NUMBERED_HEADING_INHERIT_HEADING1


def resolve_non_numbered_heading_style(
    template: TemplateConfig | object,
    *,
    include_body_fallback: bool = True,
) -> StyleConfig | None:
    """Return the effective style for headings that are skipped from numbering."""

    mode = normalize_non_numbered_heading_style_mode(
        getattr(template.heading_model, "non_numbered_heading_style_mode", None)
    )
    if mode == NON_NUMBERED_HEADING_CUSTOM:
        style = _styles_view(template).get(NON_NUMBERED_HEADING_STYLE_KEY)
        if style is not None:
            return deepcopy(style)
    return resolve_heading_style(template, 1, include_body_fallback=include_body_fallback)


def resolve_non_numbered_heading_style_source(template: TemplateConfig | object) -> str | None:
    mode = normalize_non_numbered_heading_style_mode(
        getattr(template.heading_model, "non_numbered_heading_style_mode", None)
    )
    if mode == NON_NUMBERED_HEADING_CUSTOM and _styles_view(template).get(NON_NUMBERED_HEADING_STYLE_KEY) is not None:
        return NON_NUMBERED_HEADING_STYLE_KEY
    return resolve_heading_style_source(template, 1, include_body_fallback=True)


def ensure_non_numbered_heading_style_override(template: TemplateConfig) -> StyleConfig:
    styles = _mutable_styles_view(template)
    if NON_NUMBERED_HEADING_STYLE_KEY in styles:
        return styles[NON_NUMBERED_HEADING_STYLE_KEY]
    seed = resolve_heading_style(template, 1, include_body_fallback=True)
    styles[NON_NUMBERED_HEADING_STYLE_KEY] = deepcopy(seed) if seed is not None else StyleConfig()
    return styles[NON_NUMBERED_HEADING_STYLE_KEY]


def remove_non_numbered_heading_style_override(template: TemplateConfig) -> bool:
    styles = _mutable_styles_view(template)
    if NON_NUMBERED_HEADING_STYLE_KEY in styles:
        del styles[NON_NUMBERED_HEADING_STYLE_KEY]
        return True
    return False


__all__ = [
    "NON_NUMBERED_HEADING_CUSTOM",
    "NON_NUMBERED_HEADING_INHERIT_HEADING1",
    "NON_NUMBERED_HEADING_STYLE_KEY",
    "ensure_heading_style_override",
    "ensure_non_numbered_heading_style_override",
    "normalize_non_numbered_heading_style_mode",
    "remove_heading_style_override",
    "remove_non_numbered_heading_style_override",
    "resolve_heading_style",
    "resolve_heading_style_source",
    "resolve_non_numbered_heading_style",
    "resolve_non_numbered_heading_style_source",
]
