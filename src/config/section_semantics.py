"""Compatibility exports for shared logical-section semantics."""

from src.shared.engine.section_semantics import (
    SECTION_STYLE_KEY_MAP,
    SECTION_TYPE_ALIASES,
    STYLE_ALIAS_GROUPS,
    canonicalize_section_type,
    style_key_for_section,
)

__all__ = [
    "SECTION_STYLE_KEY_MAP",
    "SECTION_TYPE_ALIASES",
    "STYLE_ALIAS_GROUPS",
    "canonicalize_section_type",
    "style_key_for_section",
]
