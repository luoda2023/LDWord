"""
ConfigResolver ? merge template / scene / session into ResolvedConfig.

Merge order:
    session > scene.template_overrides > template
"""

from __future__ import annotations

import copy
from dataclasses import asdict
from typing import Any, Mapping, Sequence

from src.config.dataclass_utils import dict_to_dataclass, merge_dict_layers
from src.config.migration import (
    flatten_dict,
    normalize_module_switches,
    normalize_template_overrides,
    unflatten_dict,
)
from src.config.template import TemplateConfig
from src.config.scene import SceneWorkspace
from src.config.resolved import (
    ResolvedConfig,
    ConfigValue,
    ImageInsertionItem,
    ReplacementRule,
)


def resolve_config(
    template: TemplateConfig,
    scene: SceneWorkspace,
    session_overrides: dict[str, Any] | None = None,
    entity_data: Mapping[str, str] | None = None,
    entity_assets_dir: str | None = None,
    images: Sequence[ImageInsertionItem | Mapping[str, Any]] | None = None,
    replacements: Sequence[ReplacementRule | Mapping[str, Any]] | None = None,
) -> ResolvedConfig:
    """Merge template, scene and session values into a ResolvedConfig."""
    scene_overrides = normalize_template_overrides(scene.template_overrides)
    session_overrides = normalize_template_overrides(session_overrides)

    template_payload = asdict(template)
    template_flat = flatten_dict("", template_payload)

    merged_payload = merge_dict_layers(
        template_payload,
        unflatten_dict(scene_overrides),
        unflatten_dict(session_overrides),
    )
    merged_template = dict_to_dataclass(TemplateConfig, merged_payload)
    merged_flat = flatten_dict("", asdict(merged_template))
    provenance = _build_provenance(
        template_flat=template_flat,
        merged_flat=merged_flat,
        scene_overrides=scene_overrides,
        session_overrides=session_overrides,
    )

    return ResolvedConfig(
        page_setup=merged_template.page_setup,
        styles=merged_template.styles,
        heading_numbering=merged_template.heading_numbering,
        heading_model=merged_template.heading_model,
        toc=merged_template.toc,
        caption=merged_template.caption,
        table=merged_template.table,
        section=merged_template.section,
        header_footer=merged_template.header_footer,
        watermark=merged_template.watermark,
        reference_style=merged_template.reference_style,
        formula_table=merged_template.formula_table,
        formula_style=merged_template.formula_style,
        equation_numbering=merged_template.equation_numbering,
        output=merged_template.output,
        module_switches=normalize_module_switches(scene.module_switches),
        format_scope=copy.deepcopy(scene.format_scope),
        strict_mode=scene.strict_mode,
        md_cleanup=copy.deepcopy(scene.md_cleanup),
        whitespace=copy.deepcopy(scene.whitespace),
        citation_link=copy.deepcopy(scene.citation_link),
        formula_convert=copy.deepcopy(scene.formula_convert),
        chem_typography=copy.deepcopy(scene.chem_typography),
        entity_data=dict(entity_data or {}),
        entity_assets_dir=entity_assets_dir or "",
        images=_normalize_image_items(images),
        replacements=_normalize_replacement_rules(replacements),
        _provenance=provenance,
    )


def _build_provenance(
    *,
    template_flat: dict[str, Any],
    merged_flat: dict[str, Any],
    scene_overrides: dict[str, Any],
    session_overrides: dict[str, Any],
) -> dict[str, ConfigValue]:
    provenance: dict[str, ConfigValue] = {}

    for key, value in merged_flat.items():
        if key in session_overrides:
            source = "session"
        elif key in scene_overrides:
            source = "scene"
        else:
            source = "template"

        provenance[key] = ConfigValue(
            value=value,
            source=source,
            template_default=template_flat.get(key),
        )

    return provenance


def _normalize_image_items(
    items: Sequence[ImageInsertionItem | Mapping[str, Any]] | None,
) -> list[ImageInsertionItem]:
    normalized: list[ImageInsertionItem] = []

    for item in items or []:
        if isinstance(item, ImageInsertionItem):
            normalized.append(copy.deepcopy(item))
            continue

        if not isinstance(item, Mapping):
            continue

        width_raw = item.get("width_cm", 14.0)
        try:
            width_cm = float(width_raw)
        except (TypeError, ValueError):
            width_cm = 14.0

        normalized.append(
            ImageInsertionItem(
                path=str(item.get("path", "") or ""),
                position=item.get("position", "end"),
                width_cm=width_cm,
            )
        )

    return normalized


def _normalize_replacement_rules(
    rules: Sequence[ReplacementRule | Mapping[str, Any]] | None,
) -> list[ReplacementRule]:
    normalized: list[ReplacementRule] = []

    for rule in rules or []:
        if isinstance(rule, ReplacementRule):
            normalized.append(copy.deepcopy(rule))
            continue

        if not isinstance(rule, Mapping):
            continue

        normalized.append(
            ReplacementRule(
                old=str(rule.get("old", "") or ""),
                new=str(rule.get("new", "") or ""),
            )
        )

    return normalized
