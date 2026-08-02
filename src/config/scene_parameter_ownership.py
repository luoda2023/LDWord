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
from src.config.template import TemplateConfig

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
    "display_order": _spec(
        "display_order",
        "scene",
        "scene library selector",
        "config library",
        "Library/UI ordering metadata stored with the scene resource; the execution pipeline does not consume it.",
    ),
    "description": _spec("description", "scene", "ScenePanel overview", "config library", "Scene help text."),
    "category": _spec("category", "scene", "ScenePanel overview", "scene family registry", "Scene family routing."),
    "category_label": _spec("category_label", "scene", "ScenePanel overview", "summary projection", "Human-readable family label."),
    "scene_id": _spec("scene_id", "scene", "ScenePanel overview", "config library", "Stable scene identifier."),
    "mode_id": _spec("mode_id", "scene", "Title bar / config library", "work mode bridge", "Work mode that owns this plan; it scopes plan, template, master, and material lookups."),
    "template_id": _spec("template_id", "scene", "ScenePanel overview", "resolver", "Scene chooses a template baseline."),
    "master_id": _spec("master_id", "scene", "ScenePanel overview", "execution-session resolver", "Stable master identifier; revisions and paths exist only in the execution snapshot."),
    "compatible_template_ids": _spec("compatible_template_ids", "scene", "ScenePanel overview", "resolver", "Allowed template baselines for this scene."),
    # Scope and behavior.
    "document_scope": _spec("document_scope", "scene", "ScenePanel scope", "pipeline scheduler", "Plan-owned logical document regions that may be modified after current-document structure review."),
    "module_switches": _spec("module_switches", "scene", "TemplatePanel runtime toggles / Workbench", "pipeline scheduler", "Generic non-formula module scheduling; thesis formula enablement stays inside thesis_formula_rules and is projected only at runtime."),
    "exam_paper": _spec("exam_paper", "scene", "ScenePanel exam paper", "workbench runner", "Exam-paper assembly rules owned by the scene; per-run field values stay in Workbench."),
    "exam_paper.question_structure_mode": _spec("exam_paper.question_structure_mode", "scene", "ScenePanel exam paper", "workbench runner", "How imported question content is assembled into exam structure."),
    "exam_paper.answer_policy": _spec("exam_paper.answer_policy", "scene", "ScenePanel exam paper", "workbench runner", "Whether the scene produces student-only output or an answer version."),
    "exam_paper.runtime_fields": _spec("exam_paper.runtime_fields", "scene", "ScenePanel exam paper", "workbench runner", "Workbench fields requested per execution; concrete values are not scene data."),
    "md_cleanup": _spec("md_cleanup", "scene", "ScenePanel scene rules input cleanup", "cleanup modules", "Source-aware Markdown cleanup behavior."),
    "whitespace": _spec("whitespace", "scene", "ScenePanel scene rules input cleanup", "cleanup modules", "Whitespace normalization behavior."),
    "citation_link": _spec("citation_link", "scene", "scene preset / Workbench", "citation modules", "Reference linking behavior."),
    "thesis_formula_rules": _spec("thesis_formula_rules", "scene", "论文方案规则", "formula module", "Optional thesis-only aggregate and sole persisted formula-policy owner."),
    "thesis_formula_rules.formula_enabled": _spec("thesis_formula_rules.formula_enabled", "scene", "论文公式处理", "formula module", "Master execution gate for formula conversion and equation formatting; child workflow settings remain retained while disabled."),
    "thesis_formula_rules.formula_convert": _spec("thesis_formula_rules.formula_convert", "scene", "论文方案规则", "formula conversion", "Formula input/conversion strategy."),
    "thesis_formula_rules.formula_convert.enabled": _spec("thesis_formula_rules.formula_convert.enabled", "scene", "论文方案规则", "formula conversion", "Whether formula conversion executes."),
    "thesis_formula_rules.formula_convert.output_mode": _spec("thesis_formula_rules.formula_convert.output_mode", "scene", "论文方案规则", "formula conversion", "Formula conversion output strategy."),
    "thesis_formula_rules.formula_convert.low_confidence_policy": _spec("thesis_formula_rules.formula_convert.low_confidence_policy", "scene", "论文方案规则", "formula conversion", "Low-confidence formula conversion policy."),
    "thesis_formula_rules.formula_convert.office_fallback_enabled": _spec("thesis_formula_rules.formula_convert.office_fallback_enabled", "scene", "论文方案规则", "formula conversion", "Whether Office fallback may be used."),
    "thesis_formula_rules.formula_convert.office_fallback_timeout_sec": _spec("thesis_formula_rules.formula_convert.office_fallback_timeout_sec", "scene", "论文方案规则", "formula conversion", "Office fallback timeout."),
    "thesis_formula_rules.formula_to_table": _spec("thesis_formula_rules.formula_to_table", "scene", "论文方案规则", "formula table module", "Standalone-formula containerization policy."),
    "thesis_formula_rules.formula_to_table.enabled": _spec("thesis_formula_rules.formula_to_table.enabled", "scene", "论文方案规则", "formula table module", "Whether formula paragraphs become equation tables."),
    "thesis_formula_rules.formula_to_table.block_only": _spec("thesis_formula_rules.formula_to_table.block_only", "scene", "论文方案规则", "formula table module", "Whether table conversion is restricted to block formulas."),
    "thesis_formula_rules.chem_typography": _spec("thesis_formula_rules.chem_typography", "scene", "论文方案规则", "chem typography module", "Chemistry typography and script-recovery behavior."),
    "thesis_formula_rules.chem_typography.enabled": _spec("thesis_formula_rules.chem_typography.enabled", "scene", "论文方案规则", "chem typography module", "Whether script recovery executes."),
    "thesis_formula_rules.chem_typography.western_font": _spec("thesis_formula_rules.chem_typography.western_font", "scene", "论文方案规则", "chem typography module", "Western font for chemical tokens."),
    "thesis_formula_rules.chem_typography.scopes": _spec("thesis_formula_rules.chem_typography.scopes", "scene", "论文方案规则", "chem typography module", "Authorized document roles for script recovery."),
    "strict_mode": _spec("strict_mode", "scene", "ScenePanel overview / Workbench", "heading pipeline", "Numbering rebuild policy."),
    # Material and compliance contracts.
    "input_source_profile": _spec("input_source_profile", "material", "ScenePanel content", "material preflight", "Accepted inputs and material schema contract."),
    "input_source_profile.markdown_policy": _spec("input_source_profile.markdown_policy", "scene", "ScenePanel scene rules input cleanup", "cleanup modules", "Markdown handling policy; execution also requires an actual Markdown source."),
    "input_source_profile.material_schema_id": _spec("input_source_profile.material_schema_id", "material", "ScenePanel content", "material preflight", "Primary material schema."),
    "input_source_profile.material_schema_ids": _spec("input_source_profile.material_schema_ids", "material", "ScenePanel content", "material preflight", "Ordered material schema set."),
    "input_source_profile.required_material_fields": _spec("input_source_profile.required_material_fields", "material", "ScenePanel content", "material preflight", "Required material fields."),
    "input_source_profile.required_image_roles": _spec("input_source_profile.required_image_roles", "material", "ScenePanel content", "material preflight", "Required image/signature roles."),
    "input_source_profile.failure_policy": _spec("input_source_profile.failure_policy", "material", "ScenePanel content", "material preflight", "How material gaps affect execution."),
    "compliance_profile": _spec("compliance_profile", "scene", "Execution diagnostics / advanced plan policy", "preflight/report", "Scene-level checking profile."),
    "compliance_profile.count_profile_id": _spec("compliance_profile.count_profile_id", "scene", "Execution diagnostics / advanced plan policy", "count engine", "Scene selects count semantics."),
    "compliance_profile.object_preflight": _spec("compliance_profile.object_preflight", "scene", "Execution diagnostics / advanced plan policy", "object preflight", "Object risk policy."),
    "compliance_profile.object_preflight.scan_targets": _spec("compliance_profile.object_preflight.scan_targets", "scene", "Execution diagnostics / advanced plan policy", "object preflight", "OOXML object surfaces to inspect."),
    "compliance_profile.object_preflight.skip_modules_by_finding": _spec("compliance_profile.object_preflight.skip_modules_by_finding", "scene", "Execution diagnostics / advanced plan policy", "pipeline scheduler", "Risk-triggered module degradation."),
    # Delivery and output.
    "default_delivery_preset_id": _spec("default_delivery_preset_id", "output", "ScenePanel scene rules generated-result", "workbench runner", "Default output version."),
    "delivery_presets": _spec("delivery_presets", "output", "ScenePanel scene rules generated-result", "workbench runner", "Named output versions."),
    "delivery_presets.*.target_template_id": _spec("delivery_presets.*.target_template_id", "output", "ScenePanel scene rules generated-result", "resolver", "Output-version template override."),
    "delivery_presets.*.output_dir_template": _spec("delivery_presets.*.output_dir_template", "output", "ScenePanel scene rules generated-result", "workbench runner", "Output directory naming."),
    "delivery_presets.*.filename_template": _spec("delivery_presets.*.filename_template", "output", "ScenePanel scene rules generated-result", "workbench runner", "Output filename naming."),
    "delivery_presets.*.artifacts": _spec("delivery_presets.*.artifacts", "output", "ScenePanel scene rules generated-result", "workbench runner", "Artifacts for this output version."),
    "delivery_presets.*.artifacts.final_docx": _spec("delivery_presets.*.artifacts.final_docx", "output", "ScenePanel scene rules generated-result", "workbench runner", "Generate final DOCX for this delivery."),
    "delivery_presets.*.artifacts.compare_docx": _spec("delivery_presets.*.artifacts.compare_docx", "output", "ScenePanel scene rules generated-result", "workbench runner", "Generate comparison DOCX for this delivery."),
    "delivery_presets.*.artifacts.compare_text": _spec("delivery_presets.*.artifacts.compare_text", "output", "ScenePanel scene rules generated-result", "workbench runner", "Include text differences for this delivery."),
    "delivery_presets.*.artifacts.compare_formatting": _spec("delivery_presets.*.artifacts.compare_formatting", "output", "ScenePanel scene rules generated-result", "workbench runner", "Include formatting differences for this delivery."),
    "delivery_presets.*.artifacts.report_json": _spec("delivery_presets.*.artifacts.report_json", "output", "ScenePanel scene rules generated-result", "report writer", "Generate a JSON report for this delivery."),
    "delivery_presets.*.artifacts.report_markdown": _spec("delivery_presets.*.artifacts.report_markdown", "output", "ScenePanel scene rules generated-result", "report writer", "Generate a Markdown report for this delivery."),
    "delivery_presets.*.artifacts.material_manifest": _spec("delivery_presets.*.artifacts.material_manifest", "output", "ScenePanel scene rules generated-result", "material manifest writer", "Generate a material manifest for this delivery."),
    "delivery_presets.*.artifacts.material_package": _spec("delivery_presets.*.artifacts.material_package", "output", "ScenePanel scene rules generated-result", "material package writer", "Generate a material package for this delivery."),
    "delivery_presets.*.artifacts.review_pdf": _spec("delivery_presets.*.artifacts.review_pdf", "output", "ScenePanel scene rules generated-result", "workbench runner", "Generate a review PDF for this delivery."),
    "delivery_presets.*.content_visibility_rules": _spec("delivery_presets.*.content_visibility_rules", "output", "ScenePanel scene rules generated-result / Workbench", "content visibility engine", "Version-specific block visibility."),
    "delivery_presets.*.include_structured_intermediate": _spec("delivery_presets.*.include_structured_intermediate", "output", "ScenePanel scene rules generated-result", "workbench runner", "Whether to emit structured intermediate artifacts."),
    "delivery_presets.*.report_level": _spec("delivery_presets.*.report_level", "output", "ScenePanel scene rules generated-result", "report writer", "Per-delivery report detail level."),
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
    "thesis_formula_rules.formula_table": _spec("thesis_formula_rules.formula_table", "scene", "论文方案规则", "formula table module", "Formula-table geometry and typography."),
    "thesis_formula_rules.formula_table.formula_font_name": _spec("thesis_formula_rules.formula_table.formula_font_name", "scene", "论文方案规则", "formula table module", "Formula font."),
    "thesis_formula_rules.formula_table.formula_font_size_pt": _spec("thesis_formula_rules.formula_table.formula_font_size_pt", "scene", "论文方案规则", "formula table module", "Formula size."),
    "thesis_formula_rules.formula_table.formula_line_spacing": _spec("thesis_formula_rules.formula_table.formula_line_spacing", "scene", "论文方案规则", "formula table module", "Formula line spacing."),
    "thesis_formula_rules.formula_table.formula_space_before_pt": _spec("thesis_formula_rules.formula_table.formula_space_before_pt", "scene", "论文方案规则", "formula table module", "Formula spacing before."),
    "thesis_formula_rules.formula_table.formula_space_after_pt": _spec("thesis_formula_rules.formula_table.formula_space_after_pt", "scene", "论文方案规则", "formula table module", "Formula spacing after."),
    "thesis_formula_rules.formula_table.block_alignment": _spec("thesis_formula_rules.formula_table.block_alignment", "scene", "论文方案规则", "formula table module", "Standalone formula block alignment."),
    "thesis_formula_rules.formula_table.table_alignment": _spec("thesis_formula_rules.formula_table.table_alignment", "scene", "论文方案规则", "formula table module", "Equation-table alignment."),
    "thesis_formula_rules.formula_table.formula_cell_alignment": _spec("thesis_formula_rules.formula_table.formula_cell_alignment", "scene", "论文方案规则", "formula table module", "Formula-cell alignment."),
    "thesis_formula_rules.formula_table.number_alignment": _spec("thesis_formula_rules.formula_table.number_alignment", "scene", "论文方案规则", "formula table module", "Equation-number alignment."),
    "thesis_formula_rules.formula_table.number_font_name": _spec("thesis_formula_rules.formula_table.number_font_name", "scene", "论文方案规则", "formula table module", "Equation-number font."),
    "thesis_formula_rules.formula_table.number_font_size_pt": _spec("thesis_formula_rules.formula_table.number_font_size_pt", "scene", "论文方案规则", "formula table module", "Equation-number size."),
    "thesis_formula_rules.formula_table.auto_shrink_number_column": _spec("thesis_formula_rules.formula_table.auto_shrink_number_column", "scene", "论文方案规则", "formula table module", "Whether the number column is compacted."),
    "thesis_formula_rules.formula_style": _spec("thesis_formula_rules.formula_style", "scene", "论文方案规则", "formula module", "Whether the thesis plan normalizes formula style."),
    "thesis_formula_rules.formula_style.enabled": _spec("thesis_formula_rules.formula_style.enabled", "scene", "论文方案规则", "formula module", "Whether formula style normalization executes."),
    "thesis_formula_rules.formula_style.unify_font": _spec("thesis_formula_rules.formula_style.unify_font", "scene", "论文方案规则", "formula module", "Normalize formula font."),
    "thesis_formula_rules.formula_style.unify_size": _spec("thesis_formula_rules.formula_style.unify_size", "scene", "论文方案规则", "formula module", "Normalize formula size."),
    "thesis_formula_rules.formula_style.unify_spacing": _spec("thesis_formula_rules.formula_style.unify_spacing", "scene", "论文方案规则", "formula module", "Normalize formula spacing."),
    "thesis_formula_rules.equation_numbering": _spec("thesis_formula_rules.equation_numbering", "scene", "论文方案规则", "equation numbering module", "Formula numbering policy."),
    "thesis_formula_rules.equation_numbering.enabled": _spec("thesis_formula_rules.equation_numbering.enabled", "scene", "论文方案规则", "equation numbering module", "Whether equation-table formatting and numbering execute."),
    "thesis_formula_rules.equation_numbering.numbering_format": _spec("thesis_formula_rules.equation_numbering.numbering_format", "scene", "论文方案规则", "equation numbering module", "Formula numbering format."),
    "reference_style": _spec("reference_style", "scene", "ScenePanel references", "reference module", "Reference-list rules belong to document-type scenes such as thesis; general templates no longer expose them as a common section."),
    "watermark": _spec("watermark", "scene", "ScenePanel content", "watermark module", "Watermark is a delivery/status policy."),
    "watermark.enabled": _spec("watermark.enabled", "scene", "ScenePanel content", "watermark module", "Whether the scene applies watermark status."),
    "watermark.text": _spec("watermark.text", "scene", "ScenePanel content", "watermark module", "Watermark business/status text."),
    "watermark.color": _spec("watermark.color", "scene", "ScenePanel content", "watermark module", "Watermark appearance for status policy."),
    "watermark.rotation": _spec("watermark.rotation", "scene", "ScenePanel content", "watermark module", "Watermark rotation."),
    "watermark.font_size": _spec("watermark.font_size", "scene", "ScenePanel content", "watermark module", "Watermark font size."),
    "template_overrides": _spec("template_overrides", "template", "resolver", "resolver", "Legacy template override escape hatch.", template_baseline=True, notes="New keys should receive explicit ownership specs."),
}


PARAMETER_CONSUMER_ANCHORS: dict[str, tuple[ParameterConsumerAnchor, ...]] = {
    "execution-session resolver": (
        _anchor(
            "execution-session resolver",
            "src/services/execution_session/__init__.py",
            "build_execution_session_snapshot",
            "ResourceRef",
            rationale="Execution freezes plan, template, and master refs before runtime.",
        ),
    ),
    "batch runner": (
        _anchor(
            "batch runner",
            "src/document_batch/recipe.py",
            "class DocumentBatchPlan",
            "def compile_document_batch_plan",
        ),
        _anchor(
            "batch runner",
            "src/ui/panels/workbench/execution_session_controller.py",
            "class _DocumentBatchRunner",
            "compile_document_batch_plan(",
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
            "src/modules/special/formula_convert.py",
            "class FormulaConvertModule",
            "output_mode",
        ),
        _anchor(
            "formula conversion",
            "src/modules/special/formula_convert.py",
            "latex_fragment_to_omml",
            "low_confidence_policy",
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
            "src/services/production_runtime/material_artifacts.py",
            "def publish_material_artifacts",
            "_material_manifest_payload",
        ),
    ),
    "material package writer": (
        _anchor(
            "material package writer",
            "src/services/production_runtime/material_artifacts.py",
            "def publish_material_artifacts",
            "build_material_delivery_package",
            "DeliveryPackageBuildRequest",
            rationale=(
                "Workbench delegates package publication to the transaction-safe "
                "material delivery service with an explicit build request."
            ),
        ),
    ),
    "material preflight": (
        _anchor(
            "material preflight",
            "src/application/materials/execution.py",
            "def bind_material_run",
            "def finalize_execution_material_snapshot",
        ),
        _anchor(
            "material preflight",
            "src/ui/panels/workbench/material_state.py",
            "def bind_workbench_material",
            "def material_execution_gate",
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
            "src/pipeline/module_selection.py",
            "build_module_selection_plan",
            "ModuleSelectionPlan",
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
    "work mode bridge": (
        _anchor(
            "work mode bridge",
            "src/config/library.py",
            "_set_scene_mode",
            "_normalize_mode_id",
        ),
    ),
    "workbench runner": (
        _anchor(
            "workbench runner",
            "src/services/production_runtime/execution_runtime.py",
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
    "thesis_formula_rules.formula_enabled",
    "thesis_formula_rules.formula_convert.enabled",
    "thesis_formula_rules.formula_convert.output_mode",
    "thesis_formula_rules.formula_convert.low_confidence_policy",
    "thesis_formula_rules.formula_to_table.enabled",
    "thesis_formula_rules.formula_to_table.block_only",
    "master_id",
    "exam_paper.question_structure_mode",
    "exam_paper.answer_policy",
    "exam_paper.runtime_fields",
    "thesis_formula_rules.formula_table.formula_font_name",
    "thesis_formula_rules.formula_table.formula_font_size_pt",
    "thesis_formula_rules.formula_style.enabled",
    "thesis_formula_rules.formula_style.unify_font",
    "thesis_formula_rules.formula_style.unify_size",
    "thesis_formula_rules.formula_style.unify_spacing",
    "thesis_formula_rules.equation_numbering.enabled",
    "thesis_formula_rules.equation_numbering.numbering_format",
    "thesis_formula_rules.chem_typography.enabled",
    "thesis_formula_rules.chem_typography.scopes",
    "watermark.enabled",
    "watermark.text",
    "watermark.color",
    "watermark.rotation",
    "watermark.font_size",
    "delivery_presets.*.target_template_id",
    "delivery_presets.*.output_dir_template",
    "delivery_presets.*.filename_template",
    "delivery_presets.*.artifacts",
    "delivery_presets.*.artifacts.final_docx",
    "delivery_presets.*.artifacts.compare_docx",
    "delivery_presets.*.artifacts.compare_text",
    "delivery_presets.*.artifacts.compare_formatting",
    "delivery_presets.*.artifacts.report_json",
    "delivery_presets.*.artifacts.report_markdown",
    "delivery_presets.*.artifacts.material_manifest",
    "delivery_presets.*.artifacts.material_package",
    "delivery_presets.*.artifacts.review_pdf",
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
    template_type: type = TemplateConfig,
) -> ParameterOwnershipAuditResult:
    if not is_dataclass(scene_type):
        raise TypeError("scene_type must be a dataclass type")
    if not is_dataclass(template_type):
        raise TypeError("template_type must be a dataclass type")

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
            for path, spec in SCENE_PARAMETER_OWNERSHIP_SPECS.items()
            if not _path_exists_on_config(path, scene_type)
            and not (
                spec.template_baseline
                and _path_exists_on_config(path, template_type)
            )
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


def _path_exists_on_config(path: str, config_type: type) -> bool:
    normalized = _normalize_path(path)
    if not normalized:
        return False

    top_level_fields = {field.name for field in fields(config_type)}
    root = normalized.split(".", 1)[0]
    if root not in top_level_fields:
        return False

    current: Any = (
        config_type(mode_id="thesis")
        if config_type is SceneWorkspace and root == "thesis_formula_rules"
        else config_type()
    )
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
    "REQUIRED_SCENE_PARAMETER_PATHS",
    "SCENE_PARAMETER_OWNERSHIP_SPECS",
    "ParameterConsumerAnchor",
    "ParameterConsumerAuditResult",
    "ParameterOwnershipAuditResult",
    "ParameterOwnershipSpec",
    "audit_parameter_execution_consumers",
    "audit_scene_parameter_ownership",
    "classify_scene_parameter",
    "parameter_consumer_anchors",
    "scene_parameter_ownership_specs",
]
