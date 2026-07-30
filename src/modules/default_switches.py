"""Cycle-free default enablement metadata for pipeline modules.

Configuration normalization needs module defaults before implementation modules
are imported.  Keeping this one small leaf catalog prevents the configuration
layer from importing the implementation registry and creating a config/module
cycle.
"""

from __future__ import annotations

from types import MappingProxyType


DEFAULT_MODULE_SWITCHES = MappingProxyType(
    {
        "page_setup": True,
        "section_format": True,
        "paragraph_style": True,
        "header_footer": True,
        "heading_recognition": True,
        "heading_numbering": True,
        "toc": True,
        "caption": True,
        "table_format": True,
        "figure_table_center": True,
        "entity_fill": False,
        "source_fill": False,
        "placeholder_replace": False,
        "image_insertion": False,
        "watermark": False,
        "chem_typography": False,
        "md_cleanup": False,
        "whitespace_normalize": False,
        "validation": True,
        "citation_link": False,
        "equation_table_format": True,
        "reference_format": True,
    }
)


def default_enabled_for_module(module_name: str) -> bool:
    """Return the registered default; ad-hoc/test modules default to disabled."""

    return bool(DEFAULT_MODULE_SWITCHES.get(str(module_name or "").strip(), False))


def default_module_switches() -> dict[str, bool]:
    """Return an isolated copy of the canonical switch catalog."""

    return dict(DEFAULT_MODULE_SWITCHES)


__all__ = [
    "DEFAULT_MODULE_SWITCHES",
    "default_enabled_for_module",
    "default_module_switches",
]
