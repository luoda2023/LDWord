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
    add_template_compat_aliases,
    flatten_dict,
    normalize_module_switches,
    normalize_template_overrides,
    unflatten_dict,
)
from src.config.template import TemplateConfig
from src.config.scene import (
    SceneWorkspace,
    coerce_exam_paper_config,
    format_scope_for_application_boundary,
    scene_application_boundary_for_runtime,
)
from src.config.resolved import (
    ResolvedConfig,
    ConfigValue,
    ImageInsertionItem,
    ReplacementRule,
)

_SCENE_HEADER_FOOTER_ALLOWED_HEADER_KEYS = {
    "mode",
    "fixed_text",
    "styleref_level",
    "border",
}
_SCENE_HEADER_FOOTER_ALLOWED_ROOT_KEYS = {
    "typography",
    "header",
}
_SCENE_IGNORED_PAGE_NUMBER_OVERRIDE_KEYS = {
    "header_footer.page_number_enabled",
    "header_footer.hide_cover_header_footer",
    "header_footer.suppress_header_footer_selectors",
    "header_footer.front_matter_page_number_format",
    "header_footer.front_matter_page_number_start",
    "header_footer.body_page_number_format",
    "header_footer.body_page_number_start",
    "header_footer.restart_body_page_number",
}
_SCENE_IGNORED_PAGE_NUMBER_OVERRIDE_PREFIXES = (
    "header_footer.page_number_plan.",
    "header_footer.footer.",
    "header_footer.header.hide_on_cover",
)


def resolve_config(
    template: TemplateConfig,
    scene: SceneWorkspace,
    session_overrides: dict[str, Any] | None = None,
    entity_data: Mapping[str, str] | None = None,
    field_aliases: Mapping[str, str] | None = None,
    entity_assets_dir: str | None = None,
    images: Sequence[ImageInsertionItem | Mapping[str, Any]] | None = None,
    replacements: Sequence[ReplacementRule | Mapping[str, Any]] | None = None,
) -> ResolvedConfig:
    """Merge template, scene and session values into a ResolvedConfig."""
    scene_overrides = _filter_scene_template_overrides(
        normalize_template_overrides(scene.template_overrides)
    )
    session_overrides = normalize_template_overrides(session_overrides)
    scene_feature_overrides = _extract_scene_feature_overrides(scene)

    template_payload = asdict(template)
    template_flat = add_template_compat_aliases(flatten_dict("", template_payload))

    merged_payload = merge_dict_layers(
        template_payload,
        scene_feature_overrides,
        unflatten_dict(scene_overrides),
        unflatten_dict(session_overrides),
    )
    merged_template = dict_to_dataclass(TemplateConfig, merged_payload)
    merged_flat = add_template_compat_aliases(
        flatten_dict("", asdict(merged_template))
    )
    provenance = _build_provenance(
        template_flat=template_flat,
        merged_flat=merged_flat,
        scene_feature_overrides=add_template_compat_aliases(
            flatten_dict("", scene_feature_overrides)
        ),
        scene_overrides=scene_overrides,
        session_overrides=session_overrides,
    )
    application_boundary = scene_application_boundary_for_runtime(scene)

    return ResolvedConfig(
        # From template (core appearance)
        page_setup=merged_template.page_setup,
        styles={**merged_template.styles, **copy.deepcopy(scene.section_styles)},
        heading_numbering=merged_template.heading_numbering,
        heading_model=merged_template.heading_model,
        section=merged_template.section,
        # Template visual baseline plus explicit overrides. Scene-owned policy fields
        # below may still project into TemplateConfig-shaped runtime slots.
        table=merged_template.table,
        output=merged_template.output,
        toc=merged_template.toc,
        caption=merged_template.caption,
        header_footer=merged_template.header_footer,
        watermark=merged_template.watermark,
        reference_style=merged_template.reference_style,
        formula_table=merged_template.formula_table,
        formula_style=merged_template.formula_style,
        equation_numbering=merged_template.equation_numbering,
        # From scene (behavior)
        module_switches=normalize_module_switches(scene.module_switches),
        application_boundary=copy.deepcopy(application_boundary),
        format_scope=format_scope_for_application_boundary(
            application_boundary,
            scene.format_scope,
        ),
        strict_mode=scene.strict_mode,
        md_cleanup=copy.deepcopy(scene.md_cleanup),
        whitespace=copy.deepcopy(scene.whitespace),
        citation_link=copy.deepcopy(scene.citation_link),
        formula_convert=copy.deepcopy(scene.formula_convert),
        chem_typography=copy.deepcopy(scene.chem_typography),
        input_source_profile=copy.deepcopy(scene.input_source_profile),
        compliance_profile=copy.deepcopy(scene.compliance_profile),
        default_delivery_preset_id=scene.default_delivery_preset_id,
        delivery_presets=copy.deepcopy(scene.delivery_presets),
        exam_paper=coerce_exam_paper_config(getattr(scene, "exam_paper", None)),
        entity_data=dict(entity_data or {}),
        field_aliases=dict(field_aliases or {}),
        entity_assets_dir=entity_assets_dir or "",
        images=_normalize_image_items(images),
        replacements=_normalize_replacement_rules(replacements),
        _provenance=provenance,
    )


def _build_provenance(
    *,
    template_flat: dict[str, Any],
    merged_flat: dict[str, Any],
    scene_feature_overrides: dict[str, Any],
    scene_overrides: dict[str, Any],
    session_overrides: dict[str, Any],
) -> dict[str, ConfigValue]:
    provenance: dict[str, ConfigValue] = {}

    for key, value in merged_flat.items():
        if key in session_overrides:
            source = "session"
        elif key in scene_feature_overrides:
            source = "scene"
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


_SCENE_FEATURE_FIELDS = (
    "formula_style",
    "equation_numbering",
    "reference_style",
    "watermark",
    "output",
)


def _extract_scene_feature_overrides(scene: SceneWorkspace) -> dict[str, Any]:
    """Return scene-owned runtime policy values stored in TemplateConfig-shaped slots."""
    overrides: dict[str, Any] = {}
    for field_name in _SCENE_FEATURE_FIELDS:
        current = getattr(scene, field_name, None)
        if current is None:
            continue
        current_payload = asdict(current)
        default_payload = asdict(type(current)())
        diff = {
            key: copy.deepcopy(value)
            for key, value in current_payload.items()
            if value != default_payload.get(key)
        }
        if field_name == "header_footer":
            diff = _filter_scene_header_footer_overrides(diff)
        if diff:
            overrides[field_name] = diff
    return overrides


def _filter_scene_header_footer_overrides(diff: dict[str, Any]) -> dict[str, Any]:
    filtered: dict[str, Any] = {}

    typography = diff.get("typography")
    if isinstance(typography, Mapping) and typography:
        filtered["typography"] = copy.deepcopy(dict(typography))

    header = diff.get("header")
    if isinstance(header, Mapping):
        header_filtered = {
            key: copy.deepcopy(value)
            for key, value in dict(header).items()
            if key in _SCENE_HEADER_FOOTER_ALLOWED_HEADER_KEYS
        }
        if header_filtered:
            filtered["header"] = header_filtered

    return {
        key: value
        for key, value in filtered.items()
        if key in _SCENE_HEADER_FOOTER_ALLOWED_ROOT_KEYS and value
    }


def _filter_scene_template_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for key, value in overrides.items():
        if key in _SCENE_IGNORED_PAGE_NUMBER_OVERRIDE_KEYS:
            continue
        if any(
            key == prefix.rstrip(".") or key.startswith(prefix)
            for prefix in _SCENE_IGNORED_PAGE_NUMBER_OVERRIDE_PREFIXES
        ):
            continue
        filtered[key] = value
    return filtered


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
