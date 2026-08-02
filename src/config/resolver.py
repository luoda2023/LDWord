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
from src.config.execution_config_integrity import delivery_preset_identity_issue
from src.config.migration import (
    add_template_compat_aliases,
    flatten_dict,
    normalize_module_switches,
    normalize_template_overrides,
    unflatten_dict,
)
from src.config.template import TemplateConfig
from src.config.feature_configs import (
    EquationNumberingConfig,
    FormulaStyleConfig,
    FormulaTableConfig,
    disabled_output_config,
)
from src.config.formula_policy import (
    ChemTypographyOptions,
    FormulaConvertOptions,
    FormulaToTableOptions,
    THESIS_FORMULA_MODULE_NAMES,
    ThesisFormulaRules,
    is_thesis_formula_mode,
)
from src.config.document_scope import coerce_document_scope_policy
from src.config.scene import (
    SceneWorkspace,
    coerce_exam_paper_config,
)
from src.config.resolved import (
    ResolvedConfig,
    ConfigValue,
    ImageInsertionItem,
    ReplacementRule,
)

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
    field_scopes: Mapping[str, str] | None = None,
    field_aliases: Mapping[str, str] | None = None,
    timeline_field_keys: Sequence[str] | None = None,
    exact_material_placeholders: bool = False,
    entity_assets_dir: str | None = None,
    images: Sequence[ImageInsertionItem | Mapping[str, Any]] | None = None,
    replacements: Sequence[ReplacementRule | Mapping[str, Any]] | None = None,
) -> ResolvedConfig:
    """Merge template, scene and session values into a ResolvedConfig."""
    delivery_issue = delivery_preset_identity_issue(scene)
    if delivery_issue:
        raise ValueError(f"execution_config_invalid:{delivery_issue}")

    scene_overrides = _filter_scene_template_overrides(
        normalize_template_overrides(scene.template_overrides)
    )
    scene_overrides = _filter_delivery_artifact_overrides(scene_overrides)
    session_overrides = _filter_delivery_artifact_overrides(
        normalize_template_overrides(session_overrides)
    )
    scene_feature_overrides = _extract_scene_feature_overrides(scene)
    formula_rules = _resolved_formula_rules(scene)

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
    artifact_output = (
        copy.deepcopy(scene.default_delivery_preset().artifacts)
        if scene.delivery_presets
        else disabled_output_config()
    )
    for key, value in flatten_dict("output", asdict(artifact_output)).items():
        provenance[key] = ConfigValue(
            value=copy.deepcopy(value),
            source="scene",
            template_default=None,
        )
    if is_thesis_formula_mode(scene.mode_id):
        for key, value in flatten_dict("", asdict(formula_rules)).items():
            provenance[key] = ConfigValue(
                value=copy.deepcopy(value),
                source="scene",
                template_default=None,
            )
    return ResolvedConfig(
        # From template (core appearance)
        page_setup=merged_template.page_setup,
        styles=merged_template.styles,
        heading_numbering=merged_template.heading_numbering,
        heading_model=merged_template.heading_model,
        section=merged_template.section,
        # Template visual baseline plus explicit overrides. Scene-owned policy fields
        # below may still project into TemplateConfig-shaped runtime slots.
        table=merged_template.table,
        # Delivery artifacts have one state owner: the scene's default preset.
        # ResolvedConfig keeps this copy only as a runtime projection for existing
        # consumers that expect an OutputConfig-shaped value.
        output=artifact_output,
        toc=merged_template.toc,
        caption=merged_template.caption,
        header_footer=merged_template.header_footer,
        watermark=merged_template.watermark,
        reference_style=merged_template.reference_style,
        formula_table=copy.deepcopy(formula_rules.formula_table),
        formula_style=copy.deepcopy(formula_rules.formula_style),
        equation_numbering=copy.deepcopy(formula_rules.equation_numbering),
        # From scene (behavior)
        module_switches=_resolved_module_switches(scene),
        mode_id=str(scene.mode_id or "").strip() or "custom",
        document_scope=coerce_document_scope_policy(scene.document_scope),
        strict_mode=scene.strict_mode,
        md_cleanup=copy.deepcopy(scene.md_cleanup),
        whitespace=copy.deepcopy(scene.whitespace),
        citation_link=copy.deepcopy(scene.citation_link),
        formula_convert=copy.deepcopy(formula_rules.formula_convert),
        formula_to_table=copy.deepcopy(formula_rules.formula_to_table),
        chem_typography=copy.deepcopy(formula_rules.chem_typography),
        input_source_profile=copy.deepcopy(scene.input_source_profile),
        compliance_profile=copy.deepcopy(scene.compliance_profile),
        default_delivery_preset_id=scene.default_delivery_preset_id,
        delivery_presets=copy.deepcopy(scene.delivery_presets),
        exam_paper=coerce_exam_paper_config(getattr(scene, "exam_paper", None)),
        entity_data=dict(entity_data or {}),
        field_scopes=dict(field_scopes or {}),
        field_aliases=dict(field_aliases or {}),
        timeline_field_keys=tuple(
            dict.fromkeys(
                str(item or "").strip()
                for item in tuple(timeline_field_keys or ())
                if str(item or "").strip()
            )
        ),
        exact_material_placeholders=bool(exact_material_placeholders),
        entity_assets_dir=entity_assets_dir or "",
        images=_normalize_image_items(images),
        replacements=_normalize_replacement_rules(replacements),
        _provenance=provenance,
    )


def resolve_template_baseline(template: TemplateConfig) -> ResolvedConfig:
    """Project appearance-only template values without output authorization."""

    baseline = copy.deepcopy(template)
    template_flat = add_template_compat_aliases(
        flatten_dict("", asdict(baseline))
    )
    provenance = {
        key: ConfigValue(
            value=copy.deepcopy(value),
            source="template",
            template_default=copy.deepcopy(value),
        )
        for key, value in template_flat.items()
    }
    return ResolvedConfig(
        page_setup=baseline.page_setup,
        styles=baseline.styles,
        heading_numbering=baseline.heading_numbering,
        heading_model=baseline.heading_model,
        section=baseline.section,
        table=baseline.table,
        output=disabled_output_config(),
        toc=baseline.toc,
        caption=baseline.caption,
        header_footer=baseline.header_footer,
        watermark=baseline.watermark,
        reference_style=baseline.reference_style,
        # Formula policy has no template baseline.  These inert defaults only
        # satisfy the execution-shaped ResolvedConfig used by preview callers.
        formula_table=FormulaTableConfig(),
        formula_style=FormulaStyleConfig(),
        equation_numbering=EquationNumberingConfig(),
        formula_convert=FormulaConvertOptions(),
        formula_to_table=FormulaToTableOptions(),
        chem_typography=ChemTypographyOptions(),
        module_switches={},
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
    "reference_style",
    "watermark",
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
        if diff:
            overrides[field_name] = diff
    return overrides


def _filter_delivery_artifact_overrides(
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Reject loose output overrides; delivery presets are the sole owner."""
    return {
        key: value
        for key, value in overrides.items()
        if key != "output" and not key.startswith("output.")
    }


def _filter_scene_template_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for key, value in overrides.items():
        root = str(key).split(".", 1)[0]
        if root in {
            "formula_convert",
            "formula_to_table",
            "formula_table",
            "formula_style",
            "equation_table_format",
            "equation_numbering",
            "chem_typography",
        }:
            continue
        if key in _SCENE_IGNORED_PAGE_NUMBER_OVERRIDE_KEYS:
            continue
        if any(
            key == prefix.rstrip(".") or key.startswith(prefix)
            for prefix in _SCENE_IGNORED_PAGE_NUMBER_OVERRIDE_PREFIXES
        ):
            continue
        filtered[key] = value
    return filtered


def _resolved_formula_rules(scene: SceneWorkspace) -> ThesisFormulaRules:
    """Return the only formula policy authorized for execution."""

    if not is_thesis_formula_mode(scene.mode_id):
        return ThesisFormulaRules()
    rules = scene.thesis_formula_rules
    return copy.deepcopy(rules) if rules is not None else ThesisFormulaRules()


def _resolved_module_switches(scene: SceneWorkspace) -> dict[str, bool]:
    switches = normalize_module_switches(scene.module_switches)
    rules = scene.thesis_formula_rules
    if not is_thesis_formula_mode(scene.mode_id) or rules is None:
        for module_name in THESIS_FORMULA_MODULE_NAMES:
            switches[module_name] = False
        return switches
    switches["formula_convert"] = bool(
        rules.formula_enabled and rules.formula_convert.enabled
    )
    switches["chem_typography"] = bool(
        rules.chem_typography.enabled
        and any(
            bool(active)
            for active in (rules.chem_typography.scopes or {}).values()
        )
    )
    switches["equation_table_format"] = bool(
        rules.formula_enabled
        and (
            rules.formula_to_table.enabled
            or rules.equation_numbering.enabled
            or rules.formula_style.enabled
        )
    )
    return switches


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
