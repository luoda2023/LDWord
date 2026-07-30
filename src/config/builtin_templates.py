"""Cycle-free registry for canonical built-in template resources.

Built-in template content lives only in the mode-scoped JSON resources under
``config_library/templates/<mode>/builtin``.  This module deliberately does
not import ``src.config.library``: the library may seed another root from these
resources without creating an import cycle or a second content source.
"""

from __future__ import annotations

from pathlib import Path

from src.config.canonical_resource import assert_non_symbolic_resource_path
from src.config.loader import load_template
from src.config.template import TemplateConfig


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CANONICAL_TEMPLATE_ROOT = _PROJECT_ROOT / "config_library" / "templates"

# Ordered product metadata.  A template id can intentionally appear in more
# than one mode (currently ``default`` in custom and exam), while its content
# remains an explicit mode-scoped resource in each slot.
_BUILTIN_TEMPLATE_RESOURCES: tuple[tuple[str, str], ...] = (
    ("custom", "default"),
    ("exam", "default"),
    ("thesis", "thesis_gbt"),
    ("thesis", "thesis_custom"),
    ("bidding", "bid_engineering"),
    ("bidding", "bid_procurement"),
    ("bidding", "bid_custom"),
    ("official", "official_gbt"),
    ("official", "official_custom"),
    ("technical", "tech_standard"),
    ("technical", "tech_custom"),
    ("report", "report_default"),
    ("report", "report_custom"),
)

_PRIMARY_TEMPLATE_MODES: dict[str, str] = {
    "default": "custom",
    "thesis_gbt": "thesis",
    "thesis_custom": "thesis",
    "bid_engineering": "bidding",
    "bid_procurement": "bidding",
    "bid_custom": "bidding",
    "official_gbt": "official",
    "official_custom": "official",
    "tech_standard": "technical",
    "tech_custom": "technical",
    "report_default": "report",
    "report_custom": "report",
}


def builtin_template_resource_path(
    template_id: str,
    *,
    mode_id: str | None = None,
) -> Path:
    """Return the exact canonical JSON path for one built-in identity."""

    normalized_id = str(template_id or "").strip()
    normalized_mode = str(mode_id or "").strip() or _PRIMARY_TEMPLATE_MODES.get(
        normalized_id,
        "",
    )
    if (normalized_mode, normalized_id) not in _BUILTIN_TEMPLATE_RESOURCES:
        qualifier = f"{normalized_mode}/" if normalized_mode else ""
        raise ValueError(f"unknown built-in template id: {qualifier}{normalized_id}")
    return (
        _CANONICAL_TEMPLATE_ROOT
        / normalized_mode
        / "builtin"
        / f"{normalized_id}.json"
    )


def create_builtin_template(
    template_id: str,
    *,
    mode_id: str | None = None,
) -> TemplateConfig:
    """Load a fresh config from the canonical mode-scoped JSON resource."""

    path = builtin_template_resource_path(template_id, mode_id=mode_id)
    assert_non_symbolic_resource_path(
        path,
        _CANONICAL_TEMPLATE_ROOT,
        resource_label="template",
    )
    return load_template(path)


def has_builtin_template(template_id: str, *, mode_id: str | None = None) -> bool:
    normalized_id = str(template_id or "").strip()
    if mode_id is None:
        return normalized_id in _PRIMARY_TEMPLATE_MODES
    return (str(mode_id or "").strip(), normalized_id) in _BUILTIN_TEMPLATE_RESOURCES


def list_builtin_template_ids() -> list[str]:
    return list(_PRIMARY_TEMPLATE_MODES)


def list_builtin_template_resources() -> tuple[tuple[str, str, Path], ...]:
    """Return every authoritative mode/id/path resource slot."""

    return tuple(
        (
            mode_id,
            template_id,
            builtin_template_resource_path(template_id, mode_id=mode_id),
        )
        for mode_id, template_id in _BUILTIN_TEMPLATE_RESOURCES
    )


def canonical_template_root() -> Path:
    """Return the authoritative boundary used for bundled template paths."""

    return _CANONICAL_TEMPLATE_ROOT


__all__ = [
    "builtin_template_resource_path",
    "canonical_template_root",
    "create_builtin_template",
    "has_builtin_template",
    "list_builtin_template_ids",
    "list_builtin_template_resources",
]
