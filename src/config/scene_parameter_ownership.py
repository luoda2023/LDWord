"""Scene parameter ownership registry.

The high-level scene matrix treats parameter ownership as an executable
contract: every scene-facing parameter must have a clear home before it can be
surfaced in UI or consumed by runtime code.  This registry is intentionally
small and explicit.  It does not change scene behavior; it gives tests and
future tooling a stable place to ask, "who owns this parameter?"
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any

from src.config.scene import SceneWorkspace


ALLOWED_PARAMETER_OWNER_LAYERS: tuple[str, ...] = (
    "template",
    "scene",
    "material",
    "output",
    "plugin",
)


@dataclass(frozen=True)
class ParameterOwnershipSpec:
    path: str
    owner_layer: str
    ui_surface: str
    execution_consumer: str
    rationale: str
    template_baseline: bool = False
    notes: str = ""


@dataclass(frozen=True)
class ParameterOwnershipAuditResult:
    missing_top_level_paths: tuple[str, ...] = ()
    missing_required_paths: tuple[str, ...] = ()
    unknown_spec_paths: tuple[str, ...] = ()
    invalid_owner_layers: tuple[tuple[str, str], ...] = ()

    @property
    def is_clean(self) -> bool:
        return not (
            self.missing_top_level_paths
            or self.missing_required_paths
            or self.unknown_spec_paths
            or self.invalid_owner_layers
        )


@dataclass(frozen=True)
class ParameterConsumerAnchor:
    consumer: str
    source_path: str
    markers: tuple[str, ...]
    rationale: str = ""


@dataclass(frozen=True)
class ParameterConsumerAuditResult:
    missing_consumers: tuple[str, ...] = ()
    unused_anchor_consumers: tuple[str, ...] = ()
    missing_anchor_files: tuple[tuple[str, str], ...] = ()
    missing_anchor_markers: tuple[tuple[str, str, str], ...] = ()

    @property
    def is_clean(self) -> bool:
        return not (
            self.missing_consumers
            or self.unused_anchor_consumers
            or self.missing_anchor_files
            or self.missing_anchor_markers
        )


def _spec(
    path: str,
    owner_layer: str,
    ui_surface: str,
    execution_consumer: str,
    rationale: str,
    *,
    template_baseline: bool = False,
    notes: str = "",
) -> ParameterOwnershipSpec:
    return ParameterOwnershipSpec(
        path=path,
        owner_layer=owner_layer,
        ui_surface=ui_surface,
        execution_consumer=execution_consumer,
        rationale=rationale,
        template_baseline=template_baseline,
        notes=notes,
    )


def _anchor(
    consumer: str,
    source_path: str,
    *markers: str,
    rationale: str = "",
) -> ParameterConsumerAnchor:
    return ParameterConsumerAnchor(
        consumer=consumer,
        source_path=source_path,
        markers=tuple(markers),
        rationale=rationale,
    )


SCENE_PARAMETER_OWNERSHIP_SPECS: dict[str, ParameterOwnershipSpec] = {
    # Scene identity and binding.
    "name": _spec("name", "scene", "ScenePanel overview", "config library", "Scene display identity."),
    "description": _spec("description", "scene", "ScenePanel overview", "config library", "Scene help text."),
    "category": _spec("category", "scene", "ScenePanel overview", "scene family registry", "Scene family routing."),
    "category_label": _spec("category_label", "scene", "ScenePanel overview", "summary projection", "Human-readable family label."),
    "scene_id": _spec("scene_id", "scene", "ScenePanel overview", "config library", "Stable scene identifier."),
    "template_id": _spec("template_id", "scene", "ScenePanel overview", "resolver", "Scene chooses a template baseline."),
    "default_template_id": _spec("default_template_id", "scene", "ScenePanel overview", "resolver", "Fallback template baseline."),
    "compatible_template_ids": _spec("compatible_template_ids", "scene", "ScenePanel overview", "resolver", "Allowed template baselines for this scene."),
    # Scope and behavior.
    "application_boundary": _spec("application_boundary", "scene", "ScenePanel scope", "pipeline scheduler", "High-level scene task boundary; it filters template/runtime structure without defining sections."),
    "format_scope": _spec("format_scope", "scene", "ScenePanel scope", "pipeline scheduler", "Legacy compatibility gate for old scene section filters."),
    "available_sections": _spec("available_sections", "scene", "ScenePanel scope", "ScenePanel scope", "Legacy compatibility list for old scene section filters."),
    "module_switches": _spec("module_switches", "scene", "TemplatePanel runtime toggles / Workbench", "pipeline scheduler", "Which modules run for this scene; ScenePanel does not expose duplicate generic switches."),
    "exam_paper": _spec("exam_paper", "scene", "ScenePanel exam paper", "workbench runner", "Exam-paper assembly rules owned by the scene; per-run field values stay in Workbench."),
    "exam_paper.blank_style_id": _spec("exam_paper.blank_style_id", "scene", "ScenePanel exam paper", "workbench runner", "Blank exam-paper shell selected by the scene."),
    "exam_paper.question_structure_mode": _spec("exam_paper.question_structure_mode", "scene", "ScenePanel exam paper", "workbench runner", "How imported question content is assembled into exam structure."),
    "exam_paper.answer_policy": _spec("exam_paper.answer_policy", "scene", "ScenePanel exam paper", "workbench runner", "Whether the scene produces student-only output or an answer version."),
    "exam_paper.runtime_fields": _spec("exam_paper.runtime_fields", "scene", "ScenePanel exam paper", "workbench runner", "Workbench fields requested per execution; concrete values are not scene data."),
    "md_cleanup": _spec("md_cleanup", "scene", "ScenePanel cleanup", "cleanup modules", "Markdown cleanup behavior."),
    "whitespace": _spec("whitespace", "scene", "ScenePanel cleanup", "cleanup modules", "Whitespace normalization behavior."),
    "citation_link": _spec("citation_link", "scene", "scene preset / Workbench", "citation modules", "Reference linking behavior."),
    "formula_convert": _spec("formula_convert", "scene", "scene preset / Workbench", "formula conversion", "Formula input/conversion strategy."),
    "formula_convert.output_mode": _spec("formula_convert.output_mode", "scene", "scene preset / Workbench", "formula conversion", "Formula conversion output strategy."),
    "formula_convert.low_confidence_policy": _spec("formula_convert.low_confidence_policy", "scene", "scene preset / Workbench", "formula conversion", "Low-confidence formula conversion policy."),
    "formula_convert.office_fallback_enabled": _spec("formula_convert.office_fallback_enabled", "scene", "scene preset / Workbench", "formula conversion", "Whether Office fallback may be used."),
    "chem_typography": _spec("chem_typography", "scene", "scene preset / Workbench", "chem typography module", "Chemistry typography behavior."),
    "strict_mode": _spec("strict_mode", "scene", "ScenePanel overview / Workbench", "heading pipeline", "Numbering rebuild policy."),
    # Material and compliance contracts.
    "input_source_profile": _spec("input_source_profile", "material", "ScenePanel content", "material preflight", "Accepted inputs and material schema contract."),
    "input_source_profile.material_schema_id": _spec("input_source_profile.material_schema_id", "material", "ScenePanel content", "material preflight", "Primary material schema."),
    "input_source_profile.material_schema_ids": _spec("input_source_profile.material_schema_ids", "material", "ScenePanel content", "material preflight", "Ordered material schema set."),
    "input_source_profile.required_material_fields": _spec("input_source_profile.required_material_fields", "material", "ScenePanel content", "material preflight", "Required material fields."),
    "input_source_profile.required_image_roles": _spec("input_source_profile.required_image_roles", "material", "ScenePanel content", "material preflight", "Required image/signature roles."),
    "input_source_profile.failure_policy": _spec("input_source_profile.failure_policy", "material", "ScenePanel content", "material preflight", "How material gaps affect execution."),
    "compliance_profile": _spec("compliance_profile", "scene", "ScenePanel cleanup", "preflight/report", "Scene-level checking profile."),
    "compliance_profile.count_profile_id": _spec("compliance_profile.count_profile_id", "scene", "ScenePanel cleanup", "count engine", "Scene selects count semantics."),
    "compliance_profile.object_preflight": _spec("compliance_profile.object_preflight", "scene", "ScenePanel cleanup", "object preflight", "Object risk policy."),
    "compliance_profile.object_preflight.scan_targets": _spec("compliance_profile.object_preflight.scan_targets", "scene", "ScenePanel cleanup", "object preflight", "OOXML object surfaces to inspect."),
    "compliance_profile.object_preflight.skip_modules_by_finding": _spec("compliance_profile.object_preflight.skip_modules_by_finding", "scene", "ScenePanel cleanup", "pipeline scheduler", "Risk-triggered module degradation."),
    # Delivery and output.
    "default_delivery_preset_id": _spec("default_delivery_preset_id", "output", "ScenePanel scene rules generated-result", "workbench runner", "Default output version."),
    "delivery_presets": _spec("delivery_presets", "output", "ScenePanel scene rules generated-result", "workbench runner", "Named output versions."),
    "delivery_presets.*.target_template_id": _spec("delivery_presets.*.target_template_id", "output", "ScenePanel scene rules generated-result", "resolver", "Output-version template override."),
    "delivery_presets.*.output_dir_template": _spec("delivery_presets.*.output_dir_template", "output", "ScenePanel scene rules generated-result", "workbench runner", "Output directory naming."),
    "delivery_presets.*.filename_template": _spec("delivery_presets.*.filename_template", "output", "ScenePanel scene rules generated-result", "workbench runner", "Output filename naming."),
    "delivery_presets.*.artifacts": _spec("delivery_presets.*.artifacts", "output", "ScenePanel scene rules generated-result", "workbench runner", "Artifacts for this output version."),
    "delivery_presets.*.content_visibility_rules": _spec("delivery_presets.*.content_visibility_rules", "output", "ScenePanel scene rules generated-result / Workbench", "content visibility engine", "Version-specific block visibility."),
    "delivery_presets.*.include_structured_intermediate": _spec("delivery_presets.*.include_structured_intermediate", "output", "ScenePanel scene rules generated-result", "workbench runner", "Whether to emit structured intermediate artifacts."),
    "delivery_presets.*.report_level": _spec("delivery_presets.*.report_level", "output", "ScenePanel scene rules generated-result", "report writer", "Per-delivery report detail level."),
    "output": _spec("output", "output", "ScenePanel scene rules generated-result / Workbench", "workbench runner", "Current output artifact switches."),
    "output.final_docx": _spec("output.final_docx", "output", "ScenePanel scene rules generated-result", "workbench runner", "Generate final DOCX."),
    "output.compare_docx": _spec("output.compare_docx", "output", "workbench runner", "workbench runner", "Generate comparison DOCX."),
    "output.report_json": _spec("output.report_json", "output", "ScenePanel scene rules generated-result", "report writer", "Generate JSON report."),
    "output.report_markdown": _spec("output.report_markdown", "output", "ScenePanel scene rules generated-result", "report writer", "Generate Markdown report."),
    "output.material_manifest": _spec("output.material_manifest", "output", "ScenePanel scene rules generated-result", "material manifest writer", "Generate material manifest."),
    "output.material_package": _spec("output.material_package", "output", "ScenePanel scene rules generated-result", "material package writer", "Generate material package."),
    "batch_preset": _spec("batch_preset", "output", "AssetsPanel batch", "batch runner", "Multi-record output strategy."),
    # Template baseline and scene-visible overrides.
    "table": _spec("table", "template", "TemplatePanel table", "table module", "Table style baseline; runtime processing is toggled from template/workbench surfaces, not a duplicate ScenePanel capability page.", template_baseline=True),
    "table.layout_mode": _spec("table.layout_mode", "template", "TemplatePanel table", "table module", "Table layout style.", template_baseline=True),
    "table.border_mode": _spec("table.border_mode", "template", "TemplatePanel table", "table module", "Table border style.", template_baseline=True),
    "table.repeat_header": _spec("table.repeat_header", "template", "TemplatePanel table", "table module", "Repeat header row behavior.", template_baseline=True),
    "header_footer": _spec("header_footer", "template", "TemplatePanel elements", "header/footer modules", "Header/footer/page-number baseline.", template_baseline=True, notes="ScenePanel only summarizes scene/template relation; generic runtime toggles stay on template/workbench surfaces."),
    "header_footer.page_number_plan": _spec("header_footer.page_number_plan", "template", "TemplatePanel elements", "page number planner", "Page-number phases are template-owned.", template_baseline=True),
    "toc": _spec("toc", "template", "TemplatePanel TOC", "toc module", "TOC baseline; ScenePanel does not expose a duplicate generic toggle.", template_baseline=True),
    "caption": _spec("caption", "template", "TemplatePanel captions", "caption module", "Caption baseline; ScenePanel does not expose a duplicate generic toggle.", template_baseline=True),
    "formula_table": _spec("formula_table", "template", "TemplatePanel formula", "formula table module", "Formula visual baseline.", template_baseline=True),
    "formula_table.formula_font_name": _spec("formula_table.formula_font_name", "template", "TemplatePanel formula", "formula table module", "Formula font baseline.", template_baseline=True),
    "formula_style": _spec("formula_style", "scene", "scene preset / Workbench", "formula module", "Whether scene normalizes formula style."),
    "formula_style.unify_font": _spec("formula_style.unify_font", "scene", "scene preset / Workbench", "formula module", "Scene decides whether to normalize formula font."),
    "formula_style.unify_size": _spec("formula_style.unify_size", "scene", "scene preset / Workbench", "formula module", "Scene decides whether to normalize formula size."),
    "formula_style.unify_spacing": _spec("formula_style.unify_spacing", "scene", "scene preset / Workbench", "formula module", "Scene decides whether to normalize formula spacing."),
    "equation_numbering": _spec("equation_numbering", "scene", "scene preset / Workbench", "equation numbering module", "Formula numbering policy by scene."),
    "equation_numbering.numbering_format": _spec("equation_numbering.numbering_format", "scene", "scene preset / Workbench", "equation numbering module", "Formula numbering format."),
    "reference_style": _spec("reference_style", "scene", "ScenePanel references", "reference module", "Reference-list rules belong to document-type scenes such as thesis; general templates no longer expose them as a common section."),
    "watermark": _spec("watermark", "scene", "ScenePanel content", "watermark module", "Watermark is a delivery/status policy."),
    "watermark.enabled": _spec("watermark.enabled", "scene", "ScenePanel content", "watermark module", "Whether the scene applies watermark status."),
    "watermark.text": _spec("watermark.text", "scene", "ScenePanel content", "watermark module", "Watermark business/status text."),
    "watermark.color": _spec("watermark.color", "scene", "ScenePanel content", "watermark module", "Watermark appearance for status policy."),
    "watermark.rotation": _spec("watermark.rotation", "scene", "ScenePanel content", "watermark module", "Watermark rotation."),
    "watermark.font_size": _spec("watermark.font_size", "scene", "ScenePanel content", "watermark module", "Watermark font size."),
    "section_styles": _spec("section_styles", "scene", "ScenePanel scope", "resolver", "Scene-owned format exceptions applied over the template baseline."),
    "template_overrides": _spec("template_overrides", "template", "resolver", "resolver", "Legacy template override escape hatch.", template_baseline=True, notes="New keys should receive explicit ownership specs."),
}


PARAMETER_CONSUMER_ANCHORS: dict[str, tuple[ParameterConsumerAnchor, ...]] = {
    "ScenePanel scope": (
        _anchor(
            "ScenePanel scope",
            "src/ui/panels/scene_panel.py",
            "format_scope.sections",
            "scene.format_scope.sections",
        ),
    ),
    "batch runner": (
        _anchor(
            "batch runner",
            "src/config/material_batch.py",
            "MaterialBatchSelection",
            "build_material_batch_items",
        ),
        _anchor(
            "batch runner",
            "src/ui/panels/workbench/execution_runtime.py",
            "WorkbenchBatchProductionRunner",
            "batch_report_paths",
        ),
    ),
    "caption module": (
        _anchor(
            "caption module",
            "src/modules/table/caption.py",
            "class CaptionModule",
            "config.caption",
        ),
    ),
    "chem typography module": (
        _anchor(
            "chem typography module",
            "src/modules/special/chem_typography.py",
            "class ChemTypographyModule",
            "config.chem_typography",
        ),
    ),
    "citation modules": (
        _anchor(
            "citation modules",
            "src/modules/special/citation_link.py",
            "class CitationLinkModule",
            "citation_link",
        ),
    ),
    "cleanup modules": (
        _anchor(
            "cleanup modules",
            "src/modules/validate/md_cleanup.py",
            "class MdCleanupModule",
            "md_cleanup",
        ),
        _anchor(
            "cleanup modules",
            "src/modules/validate/whitespace_normalize.py",
            "class WhitespaceNormalizeModule",
            "whitespace",
        ),
    ),
    "config library": (
        _anchor(
            "config library",
            "src/config/library.py",
            "load_scene_from_library",
            "_load_scene_entry",
        ),
    ),
    "content visibility engine": (
        _anchor(
            "content visibility engine",
            "src/shared/engine/content_visibility.py",
            "scan_content_visibility_markers",
            "content_visibility_rules",
        ),
        _anchor(
            "content visibility engine",
            "src/pipeline/runner.py",
            "_run_content_visibility_preflight",
            "_apply_content_visibility_rules",
        ),
    ),
    "count engine": (
        _anchor(
            "count engine",
            "src/modules/validate/validation.py",
            "count_profile_id",
            "count_document",
        ),
    ),
    "equation numbering module": (
        _anchor(
            "equation numbering module",
            "src/modules/special/equation_table_format.py",
            "equation_numbering",
            "numbering_cfg",
        ),
    ),
    "formula conversion": (
        _anchor(
            "formula conversion",
            "src/config/resolver.py",
            "formula_convert=copy.deepcopy",
            "ResolvedConfig",
        ),
        _anchor(
            "formula conversion",
            "src/config/resolved.py",
            "formula_convert: FormulaConvertOptions",
            "ResolvedConfig",
        ),
    ),
    "formula module": (
        _anchor(
            "formula module",
            "src/modules/special/equation_table_format.py",
            "formula_style",
            "style_cfg",
        ),
    ),
    "formula table module": (
        _anchor(
            "formula table module",
            "src/modules/special/equation_table_format.py",
            "formula_table",
            "formula_cfg",
        ),
    ),
    "header/footer modules": (
        _anchor(
            "header/footer modules",
            "src/modules/basic/header_footer.py",
            "class HeaderFooterModule",
            "header_footer",
        ),
    ),
    "heading pipeline": (
        _anchor(
            "heading pipeline",
            "src/modules/structure/heading_numbering.py",
            "class HeadingNumberingModule",
            "HeadingNumberingModule",
        ),
    ),
    "material manifest writer": (
        _anchor(
            "material manifest writer",
            "src/ui/panels/workbench/material_artifacts.py",
            "_write_material_manifest",
            "_material_manifest_payload",
        ),
    ),
    "material package writer": (
        _anchor(
            "material package writer",
            "src/ui/panels/workbench/material_artifacts.py",
            "_write_material_package_artifacts",
            "_material_package_status",
        ),
    ),
    "material preflight": (
        _anchor(
            "material preflight",
            "src/config/material_schema_registry.py",
            "evaluate_material_requirements",
            "missing_material_schema_ids",
        ),
        _anchor(
            "material preflight",
            "src/ui/adapters/workbench_material_issues.py",
            "material_schema_readiness_reasons",
            "MaterialReadinessIssueGroups",
        ),
    ),
    "object preflight": (
        _anchor(
            "object preflight",
            "src/shared/engine/object_preflight.py",
            "inspect_docx_package",
            "object_preflight_module_skips",
        ),
        _anchor(
            "object preflight",
            "src/pipeline/runner.py",
            "_run_object_preflight",
            "object_preflight_policy",
        ),
    ),
    "page number planner": (
        _anchor(
            "page number planner",
            "src/shared/engine/page_number_planner.py",
            "PageNumberExecutionPlan",
            "page_number_plan",
        ),
    ),
    "pipeline scheduler": (
        _anchor(
            "pipeline scheduler",
            "src/pipeline/scheduler.py",
            "select_enabled_modules",
            "requires_config",
        ),
    ),
    "preflight/report": (
        _anchor(
            "preflight/report",
            "src/report_writer.py",
            "_extract_object_preflight",
            "_format_object_preflight_markdown",
        ),
    ),
    "reference module": (
        _anchor(
            "reference module",
            "src/modules/special/reference_format.py",
            "class ReferenceFormatModule",
            "reference_style",
        ),
    ),
    "report writer": (
        _anchor(
            "report writer",
            "src/report_writer.py",
            "write_json_report",
            "write_markdown_report",
        ),
    ),
    "resolver": (
        _anchor(
            "resolver",
            "src/config/resolver.py",
            "resolve_config",
            "_build_provenance",
        ),
    ),
    "scene family registry": (
        _anchor(
            "scene family registry",
            "src/config/scene_family_registry.py",
            "get_planned_scene_family",
            "PLANNED_SCENE_FAMILIES",
        ),
    ),
    "summary projection": (
        _anchor(
            "summary projection",
            "src/ui/panels/scene_summary_projection.py",
            "build_scene_overview_summary_items",
            "SummaryGridItem",
        ),
    ),
    "table module": (
        _anchor(
            "table module",
            "src/modules/table/table_format.py",
            "class TableFormatModule",
            "config.table",
        ),
    ),
    "toc module": (
        _anchor(
            "toc module",
            "src/modules/structure/toc.py",
            "class TocModule",
            "config.toc",
        ),
    ),
    "watermark module": (
        _anchor(
            "watermark module",
            "src/modules/insert/watermark.py",
            "class WatermarkModule",
            "config.watermark",
        ),
    ),
    "workbench runner": (
        _anchor(
            "workbench runner",
            "src/ui/panels/workbench/execution_runtime.py",
            "WorkbenchProductionRunner",
            "output_paths",
        ),
        _anchor(
            "workbench runner",
            "src/ui/adapters/workbench_execution_adapter.py",
            "build_result_state",
            "artifact_items",
        ),
    ),
}


REQUIRED_SCENE_PARAMETER_PATHS: tuple[str, ...] = (
    "input_source_profile.material_schema_id",
    "input_source_profile.material_schema_ids",
    "input_source_profile.required_material_fields",
    "input_source_profile.required_image_roles",
    "compliance_profile.count_profile_id",
    "compliance_profile.object_preflight.scan_targets",
    "compliance_profile.object_preflight.skip_modules_by_finding",
    "formula_convert.output_mode",
    "formula_convert.low_confidence_policy",
    "exam_paper.blank_style_id",
    "exam_paper.question_structure_mode",
    "exam_paper.answer_policy",
    "exam_paper.runtime_fields",
    "formula_style.unify_font",
    "formula_style.unify_size",
    "formula_style.unify_spacing",
    "equation_numbering.numbering_format",
    "watermark.enabled",
    "watermark.text",
    "watermark.color",
    "watermark.rotation",
    "watermark.font_size",
    "output.final_docx",
    "output.compare_docx",
    "output.report_json",
    "output.report_markdown",
    "output.material_manifest",
    "output.material_package",
    "delivery_presets.*.target_template_id",
    "delivery_presets.*.output_dir_template",
    "delivery_presets.*.filename_template",
    "delivery_presets.*.artifacts",
    "delivery_presets.*.content_visibility_rules",
    "delivery_presets.*.include_structured_intermediate",
    "delivery_presets.*.report_level",
    "header_footer.page_number_plan",
    "table.layout_mode",
    "table.border_mode",
    "table.repeat_header",
)


def scene_parameter_ownership_specs() -> dict[str, ParameterOwnershipSpec]:
    return dict(SCENE_PARAMETER_OWNERSHIP_SPECS)


def parameter_consumer_anchors() -> dict[str, tuple[ParameterConsumerAnchor, ...]]:
    return {consumer: tuple(anchors) for consumer, anchors in PARAMETER_CONSUMER_ANCHORS.items()}


def classify_scene_parameter(path: str) -> ParameterOwnershipSpec | None:
    normalized = _normalize_path(path)
    if not normalized:
        return None
    exact = SCENE_PARAMETER_OWNERSHIP_SPECS.get(normalized)
    if exact is not None:
        return exact

    parts = normalized.split(".")
    for index, segment in enumerate(parts):
        if _looks_like_collection_index(segment):
            wildcard = ".".join([*parts[:index], "*", *parts[index + 1 :]])
            spec = SCENE_PARAMETER_OWNERSHIP_SPECS.get(wildcard)
            if spec is not None:
                return spec

    return None


def audit_scene_parameter_ownership(
    scene_type: type = SceneWorkspace,
) -> ParameterOwnershipAuditResult:
    if not is_dataclass(scene_type):
        raise TypeError("scene_type must be a dataclass type")

    top_level_fields = {field.name for field in fields(scene_type)}
    spec_paths = set(SCENE_PARAMETER_OWNERSHIP_SPECS)
    top_level_spec_paths = {
        path for path in spec_paths if "." not in path
    }
    missing_top_level = tuple(sorted(top_level_fields - top_level_spec_paths))
    missing_required = tuple(
        path for path in REQUIRED_SCENE_PARAMETER_PATHS if path not in spec_paths
    )
    invalid_owner_layers = tuple(
        sorted(
            (
                (path, spec.owner_layer)
                for path, spec in SCENE_PARAMETER_OWNERSHIP_SPECS.items()
                if spec.owner_layer not in ALLOWED_PARAMETER_OWNER_LAYERS
            ),
            key=lambda item: item[0],
        )
    )
    unknown_spec_paths = tuple(
        sorted(
            path
            for path in spec_paths
            if not _path_exists_on_scene(path, scene_type)
        )
    )

    return ParameterOwnershipAuditResult(
        missing_top_level_paths=missing_top_level,
        missing_required_paths=missing_required,
        unknown_spec_paths=unknown_spec_paths,
        invalid_owner_layers=invalid_owner_layers,
    )


def audit_parameter_execution_consumers(
    *,
    project_root: Path | None = None,
) -> ParameterConsumerAuditResult:
    root = project_root or Path(__file__).resolve().parents[2]
    declared_consumers = {
        _clean_consumer(spec.execution_consumer)
        for spec in SCENE_PARAMETER_OWNERSHIP_SPECS.values()
        if _clean_consumer(spec.execution_consumer)
    }
    anchor_consumers = set(PARAMETER_CONSUMER_ANCHORS)

    missing_consumers = tuple(sorted(declared_consumers - anchor_consumers))
    unused_anchor_consumers = tuple(sorted(anchor_consumers - declared_consumers))
    missing_anchor_files: list[tuple[str, str]] = []
    missing_anchor_markers: list[tuple[str, str, str]] = []

    for consumer, anchors in sorted(PARAMETER_CONSUMER_ANCHORS.items()):
        for anchor in anchors:
            anchor_path = root / anchor.source_path
            if not anchor_path.exists():
                missing_anchor_files.append((consumer, anchor.source_path))
                continue
            try:
                content = anchor_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = anchor_path.read_text(encoding="utf-8", errors="ignore")
            for marker in anchor.markers:
                if marker not in content:
                    missing_anchor_markers.append((consumer, anchor.source_path, marker))

    return ParameterConsumerAuditResult(
        missing_consumers=missing_consumers,
        unused_anchor_consumers=unused_anchor_consumers,
        missing_anchor_files=tuple(sorted(missing_anchor_files)),
        missing_anchor_markers=tuple(sorted(missing_anchor_markers)),
    )


def _clean_consumer(value: str) -> str:
    return str(value or "").strip()


def _normalize_path(path: str) -> str:
    return ".".join(
        part.strip()
        for part in str(path or "").strip().split(".")
        if part.strip()
    )


def _looks_like_collection_index(segment: str) -> bool:
    try:
        index = int(segment)
    except ValueError:
        return False
    return index >= 0


def _path_exists_on_scene(path: str, scene_type: type) -> bool:
    normalized = _normalize_path(path)
    if not normalized:
        return False

    top_level_fields = {field.name for field in fields(scene_type)}
    root = normalized.split(".", 1)[0]
    if root not in top_level_fields:
        return False

    scene = scene_type()
    current: Any = scene
    for segment in normalized.split("."):
        if segment == "*":
            if not isinstance(current, (list, tuple)):
                return False
            if not current:
                return True
            current = current[0]
            continue
        if isinstance(current, (list, tuple)):
            if _looks_like_collection_index(segment):
                index = int(segment)
                if index < 0 or index >= len(current):
                    return False
                current = current[index]
                continue
            return False
        if not hasattr(current, segment):
            return False
        current = getattr(current, segment)
    return True


__all__ = [
    "ALLOWED_PARAMETER_OWNER_LAYERS",
    "PARAMETER_CONSUMER_ANCHORS",
    "ParameterOwnershipAuditResult",
    "ParameterConsumerAnchor",
    "ParameterConsumerAuditResult",
    "ParameterOwnershipSpec",
    "REQUIRED_SCENE_PARAMETER_PATHS",
    "SCENE_PARAMETER_OWNERSHIP_SPECS",
    "audit_parameter_execution_consumers",
    "audit_scene_parameter_ownership",
    "classify_scene_parameter",
    "parameter_consumer_anchors",
    "scene_parameter_ownership_specs",
]
