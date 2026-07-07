"""Audit manifest for high-level scene capability coverage.

The manifest turns the V12 planning table into code-level evidence. It does
not expose new executable scenes; it records which high-frequency request
families are covered by existing top-level scenes, planned families, profiles,
presets, schemas, or plugin boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import shlex

from src.config.material_schema_registry import get_material_schema, resolve_material_schema_ids


@dataclass(frozen=True, slots=True)
class CapabilityAxis:
    """One cross-cutting capability axis required for L3 scene closure."""

    axis_id: str
    label: str
    question: str
    typical_landings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SceneCompletenessGate:
    """One required answer before a scene capability can be called complete."""

    gate_id: str
    label: str
    required_question: str
    evidence_surfaces: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowArchetype:
    """One reusable workflow lens used to prevent high-frequency omissions."""

    archetype_id: str
    label: str
    capability_axis_ids: tuple[str, ...]
    acceptance_signal: str


@dataclass(frozen=True, slots=True)
class WordRiskSurface:
    """One Word/OOXML surface that high-level scene packs must account for."""

    surface_id: str
    label: str
    touchpoints: tuple[str, ...]
    required_strategy: str


@dataclass(frozen=True, slots=True)
class SceneClosureTask:
    """One actionable missing closure task for a coverage pack."""

    summary: str
    priority: str
    owner: str
    target_phase: str
    validation_commands: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SceneCoveragePack:
    """One high-frequency scenario pack from the V12 coverage matrix."""

    pack_id: str
    label: str
    natural_requests: tuple[str, ...]
    primary_landings: tuple[str, ...]
    secondary_landings: tuple[str, ...]
    capability_axis_ids: tuple[str, ...]
    workflow_archetype_ids: tuple[str, ...]
    word_risk_surface_ids: tuple[str, ...]
    boundary: str
    executable_scene_ids: tuple[str, ...] = ()
    planned_family_ids: tuple[str, ...] = ()
    plugin_boundary: bool = False
    implemented_closures: tuple[str, ...] = ()
    closure_tasks: tuple[SceneClosureTask, ...] = ()
    missing_closures: tuple[str, ...] = ()
    completeness_gate_ids: tuple[str, ...] = field(
        default_factory=lambda: SCENE_COMPLETENESS_GATE_IDS
    )

    def __post_init__(self) -> None:
        if self.closure_tasks and not self.missing_closures:
            object.__setattr__(
                self,
                "missing_closures",
                tuple(task.summary for task in self.closure_tasks),
            )


@dataclass(frozen=True, slots=True)
class ScenePackCompletenessAuditResult:
    """Static completeness audit for one high-frequency coverage pack."""

    pack_id: str
    missing_gate_ids: tuple[str, ...]
    unknown_workflow_archetype_ids: tuple[str, ...]
    unknown_word_risk_surface_ids: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        return not (
            self.missing_gate_ids
            or self.unknown_workflow_archetype_ids
            or self.unknown_word_risk_surface_ids
        )


@dataclass(frozen=True, slots=True)
class ScenePackMatrixAlignmentAuditResult:
    """Audit whether pack axes, workflows, and Word risks agree."""

    pack_id: str
    missing_axis_workflow_ids: tuple[str, ...]
    missing_workflow_word_risk_ids: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        return not (
            self.missing_axis_workflow_ids or self.missing_workflow_word_risk_ids
        )


@dataclass(frozen=True, slots=True)
class SceneClosureValidationEvidence:
    """Audited evidence for one closure task validation command."""

    pack_id: str
    task_summary: str
    command: str
    target_paths: tuple[str, ...]
    missing_paths: tuple[str, ...]
    trace_tokens: tuple[str, ...]
    trace_hits: tuple[str, ...]
    status: str

    @property
    def is_valid(self) -> bool:
        return self.status == "ok"


def _closure_task(
    summary: str,
    *,
    priority: str,
    owner: str,
    target_phase: str,
    validation_paths: tuple[str, ...],
) -> SceneClosureTask:
    return SceneClosureTask(
        summary=summary,
        priority=priority,
        owner=owner,
        target_phase=target_phase,
        validation_commands=_pytest_commands(validation_paths),
    )


def _pytest_commands(paths: tuple[str, ...]) -> tuple[str, ...]:
    return ("python -m pytest " + " ".join(paths) + " -q",)


CAPABILITY_AXES: tuple[CapabilityAxis, ...] = (
    CapabilityAxis(
        axis_id="input_fact_source",
        label="Input fact source",
        question="Which input is the machine-readable source of truth?",
        typical_landings=("InputSourceProfile", "schema", "structured_json"),
    ),
    CapabilityAxis(
        axis_id="template_baseline",
        label="Template baseline",
        question="Which visual decisions belong to the template baseline?",
        typical_landings=("TemplateConfig", "compatible_template_ids", "template_overrides"),
    ),
    CapabilityAxis(
        axis_id="material_schema",
        label="Material schema",
        question="Which fields, assets, signatures, and attachments are required?",
        typical_landings=("MaterialSchema", "MaterialExecutionContext", "AssetsPanel"),
    ),
    CapabilityAxis(
        axis_id="structure_scope",
        label="Structure and scope",
        question="Which document sections and Word stories are included or excluded?",
        typical_landings=("FormatScopeConfig", "CountProfile", "ObjectPreflight"),
    ),
    CapabilityAxis(
        axis_id="content_visibility",
        label="Content visibility",
        question="How does one source produce role-specific or version-specific output?",
        typical_landings=("ContentVisibilityRule", "DeliveryPreset"),
    ),
    CapabilityAxis(
        axis_id="count_profile",
        label="Count profile",
        question="Which Word-like and rule-specific counting metrics apply?",
        typical_landings=("CountProfile", "ValidationModule", "report"),
    ),
    CapabilityAxis(
        axis_id="object_preflight",
        label="Object preflight",
        question="Which fragile Word objects block, warn, or downgrade execution?",
        typical_landings=("ObjectPreflightPolicy", "ObjectPreflight", "report"),
    ),
    CapabilityAxis(
        axis_id="delivery_preset",
        label="Delivery preset",
        question="Which business versions and artifacts must be produced?",
        typical_landings=("DeliveryPreset", "OutputConfig", "artifact_browser"),
    ),
    CapabilityAxis(
        axis_id="batch_preset",
        label="Batch preset",
        question="How are multi-record inputs isolated and reported?",
        typical_landings=("BatchPreset", "MaterialBatchSelection", "batch_report"),
    ),
    CapabilityAxis(
        axis_id="plugin_boundary",
        label="Plugin boundary",
        question="Which professional, AI, OCR, or import risks stay outside core?",
        typical_landings=("plugin", "manual_confirmation", "boundary_report"),
    ),
)

SCENE_COMPLETENESS_GATES: tuple[SceneCompletenessGate, ...] = (
    SceneCompletenessGate(
        gate_id="natural_request_alias",
        label="Natural request aliases",
        required_question="How would a user naturally ask for this task?",
        evidence_surfaces=("coverage pack", "navigation or planned family", "docs"),
    ),
    SceneCompletenessGate(
        gate_id="ownership_layer",
        label="Ownership layer",
        required_question="Does the capability belong to scene, template, material, output, or plugin?",
        evidence_surfaces=("scene_parameter_ownership", "control_contract", "docs"),
    ),
    SceneCompletenessGate(
        gate_id="fact_source",
        label="Fact source",
        required_question="Which input is the machine-readable source of truth?",
        evidence_surfaces=("input profile", "material schema", "delivery preset"),
    ),
    SceneCompletenessGate(
        gate_id="workflow_slots",
        label="Workflow slots",
        required_question="Which reusable workflows are required before execution is credible?",
        evidence_surfaces=("workflow archetype registry", "scene family registry", "tests"),
    ),
    SceneCompletenessGate(
        gate_id="word_risk_surface",
        label="Word risk surface",
        required_question="Which Word/OOXML surfaces can this capability touch or break?",
        evidence_surfaces=("object preflight", "runtime module", "report"),
    ),
    SceneCompletenessGate(
        gate_id="ui_control_contract",
        label="UI control contract",
        required_question="Are scene controls consistent with template management for shared parameters?",
        evidence_surfaces=("control_contract_registry", "ScenePanel", "TemplatePanel"),
    ),
    SceneCompletenessGate(
        gate_id="executable_chain",
        label="Executable chain",
        required_question="Is there a real path through resolver, scheduler, pipeline, and runner?",
        evidence_surfaces=("resolver", "pipeline", "runtime events"),
    ),
    SceneCompletenessGate(
        gate_id="report_issue_artifact",
        label="Report issue artifact",
        required_question="Can the outcome be explained through report, issue queue, or artifacts?",
        evidence_surfaces=("JSON report", "Markdown report", "Workbench issue queue"),
    ),
    SceneCompletenessGate(
        gate_id="test_evidence",
        label="Test evidence",
        required_question="Is there at least first-slice evidence for registry, UI, runtime, or report?",
        evidence_surfaces=("pytest command", "trace tokens", "closure task"),
    ),
)

SCENE_COMPLETENESS_GATE_IDS: tuple[str, ...] = tuple(
    gate.gate_id for gate in SCENE_COMPLETENESS_GATES
)

WORKFLOW_ARCHETYPES: tuple[WorkflowArchetype, ...] = (
    WorkflowArchetype(
        archetype_id="template_normalization",
        label="Template normalization",
        capability_axis_ids=("template_baseline", "structure_scope", "object_preflight"),
        acceptance_signal="A template baseline, scope, and object-risk decision are visible before execution.",
    ),
    WorkflowArchetype(
        archetype_id="scope_localization",
        label="Scope localization",
        capability_axis_ids=("structure_scope", "count_profile"),
        acceptance_signal="The pack declares which sections, stories, or page ranges can be included.",
    ),
    WorkflowArchetype(
        archetype_id="structured_input",
        label="Structured input",
        capability_axis_ids=("input_fact_source", "material_schema"),
        acceptance_signal="A JSON/XLSX/schema path is the source of truth instead of ad hoc text.",
    ),
    WorkflowArchetype(
        archetype_id="material_fill",
        label="Material fill",
        capability_axis_ids=("material_schema", "object_preflight"),
        acceptance_signal="Missing fields, assets, and roles can be preflighted and reported.",
    ),
    WorkflowArchetype(
        archetype_id="asset_attachment_inventory",
        label="Asset and attachment inventory",
        capability_axis_ids=("material_schema", "delivery_preset"),
        acceptance_signal="Image, seal, PDF, and attachment roles have manifest-level evidence.",
    ),
    WorkflowArchetype(
        archetype_id="content_visibility",
        label="Content visibility",
        capability_axis_ids=("content_visibility", "delivery_preset"),
        acceptance_signal="Multiple output versions are derived from one source with rule evidence.",
    ),
    WorkflowArchetype(
        archetype_id="batch_generation",
        label="Batch generation",
        capability_axis_ids=("batch_preset", "delivery_preset", "material_schema"),
        acceptance_signal="One-record-one-output isolation and batch issue reporting are planned.",
    ),
    WorkflowArchetype(
        archetype_id="count_compliance",
        label="Count compliance",
        capability_axis_ids=("count_profile", "structure_scope"),
        acceptance_signal="A profile-driven multi-metric count definition exists for the pack.",
    ),
    WorkflowArchetype(
        archetype_id="citation_reference",
        label="Citation and reference handling",
        capability_axis_ids=("input_fact_source", "count_profile", "plugin_boundary"),
        acceptance_signal="Reference sources, missing citation checks, and style boundaries are explicit.",
    ),
    WorkflowArchetype(
        archetype_id="formula_symbol",
        label="Formula and symbol handling",
        capability_axis_ids=("input_fact_source", "object_preflight", "plugin_boundary"),
        acceptance_signal="Formula conversion, confidence, and unsupported diagram boundaries are visible.",
    ),
    WorkflowArchetype(
        archetype_id="fixed_layout_table",
        label="Fixed-layout table",
        capability_axis_ids=("structure_scope", "object_preflight", "delivery_preset"),
        acceptance_signal="Table row height, content controls, and fixed-position form risks are separated from body style.",
    ),
    WorkflowArchetype(
        archetype_id="object_safety",
        label="Object safety",
        capability_axis_ids=("object_preflight", "plugin_boundary"),
        acceptance_signal="Fragile objects block, warn, or downgrade execution with report evidence.",
    ),
    WorkflowArchetype(
        archetype_id="review_compare",
        label="Review and compare",
        capability_axis_ids=("object_preflight", "delivery_preset"),
        acceptance_signal="Review copy, compare output, tracked changes, and comments have a policy.",
    ),
    WorkflowArchetype(
        archetype_id="submission_archive",
        label="Submission and archive",
        capability_axis_ids=("delivery_preset", "material_schema"),
        acceptance_signal="Delivery presets define final, review, archive, manifest, or package artifacts.",
    ),
    WorkflowArchetype(
        archetype_id="field_consistency",
        label="Field consistency",
        capability_axis_ids=("input_fact_source", "material_schema", "object_preflight"),
        acceptance_signal="Repeated business fields can be traced, checked, and reported.",
    ),
    WorkflowArchetype(
        archetype_id="placeholder_residue",
        label="Placeholder residue",
        capability_axis_ids=("material_schema", "object_preflight"),
        acceptance_signal="Unfilled placeholders and unmapped controls are detected after fill.",
    ),
    WorkflowArchetype(
        archetype_id="plugin_manual_gate",
        label="Plugin and manual gate",
        capability_axis_ids=("plugin_boundary", "object_preflight"),
        acceptance_signal="Professional, AI, OCR, or conversion risks do not masquerade as core execution.",
    ),
)

WORD_RISK_SURFACES: tuple[WordRiskSurface, ...] = (
    WordRiskSurface(
        surface_id="paragraph_run",
        label="Paragraph and run",
        touchpoints=("w:p", "w:r", "w:rPr", "w:pPr"),
        required_strategy="Preserve inline structure and report destructive rewrites.",
    ),
    WordRiskSurface(
        surface_id="styles",
        label="Styles",
        touchpoints=("styles.xml", "w:style", "w:rFonts", "w:sz"),
        required_strategy="Keep visual baselines template-owned and justify scene overrides.",
    ),
    WordRiskSurface(
        surface_id="numbering",
        label="Numbering",
        touchpoints=("numbering.xml", "w:num", "w:abstractNum", "w:lvl"),
        required_strategy="Declare rebuild, preserve, or repair strategy before touching numbering.",
    ),
    WordRiskSurface(
        surface_id="table_grid",
        label="Table grid",
        touchpoints=("w:tbl", "w:tr", "w:tc", "w:gridCol"),
        required_strategy="Handle merge, width, header repeat, and pagination separately from body text.",
    ),
    WordRiskSurface(
        surface_id="fixed_row_height",
        label="Fixed row height",
        touchpoints=("w:trHeight",),
        required_strategy="Treat row height as a fixed-layout form capability, not a generic template noise field.",
    ),
    WordRiskSurface(
        surface_id="content_controls",
        label="Content controls",
        touchpoints=("w:sdt", "w:tag", "w:alias"),
        required_strategy="Map, fill, protect, or report content controls explicitly.",
    ),
    WordRiskSurface(
        surface_id="textbox_shape",
        label="Textbox and shape",
        touchpoints=("w:txbxContent", "v:shape", "wps:txbx"),
        required_strategy="Preflight textboxes and shapes before treating content as normal paragraphs.",
    ),
    WordRiskSurface(
        surface_id="drawing_media_rels",
        label="Drawing, media, and relationships",
        touchpoints=("w:drawing", "word/media/*", "word/_rels/*.rels"),
        required_strategy="Inventory image and relationship roles before copying or replacing assets.",
    ),
    WordRiskSurface(
        surface_id="fields",
        label="Fields",
        touchpoints=("w:fldSimple", "w:instrText", "TOC", "PAGE", "REF"),
        required_strategy="Declare preserve, update, or skip behavior for fields and cross references.",
    ),
    WordRiskSurface(
        surface_id="headers_footers",
        label="Headers and footers",
        touchpoints=("header*.xml", "footer*.xml", "sectPr"),
        required_strategy="Separate template-owned appearance from scene-owned status and delivery policy.",
    ),
    WordRiskSurface(
        surface_id="comments_revisions",
        label="Comments and revisions",
        touchpoints=("comments.xml", "w:ins", "w:del", "w:commentRangeStart"),
        required_strategy="Preserve, block, or require confirmation before formatting review documents.",
    ),
    WordRiskSurface(
        surface_id="footnotes_endnotes",
        label="Footnotes and endnotes",
        touchpoints=("footnotes.xml", "endnotes.xml"),
        required_strategy="State whether notes are in scope for counting and formatting.",
    ),
    WordRiskSurface(
        surface_id="hidden_text",
        label="Hidden text",
        touchpoints=("w:vanish",),
        required_strategy="Preflight hidden text and explain counting or visibility effects.",
    ),
    WordRiskSurface(
        surface_id="ole_embedded_vba",
        label="OLE, embedded workbooks, and VBA",
        touchpoints=("embeddings/*", "vbaProject.bin", "oleObject"),
        required_strategy="Block, warn, or isolate risky embedded objects before core execution.",
    ),
    WordRiskSurface(
        surface_id="package_relationships",
        label="Package relationships",
        touchpoints=("_rels/.rels", "word/_rels/document.xml.rels", "externalLink"),
        required_strategy="Inventory links, attachments, and external relationships in reports.",
    ),
)

SCENE_COMPLETENESS_GATE_MAP: dict[str, SceneCompletenessGate] = {
    gate.gate_id: gate for gate in SCENE_COMPLETENESS_GATES
}
WORKFLOW_ARCHETYPE_MAP: dict[str, WorkflowArchetype] = {
    archetype.archetype_id: archetype for archetype in WORKFLOW_ARCHETYPES
}
WORD_RISK_SURFACE_MAP: dict[str, WordRiskSurface] = {
    surface.surface_id: surface for surface in WORD_RISK_SURFACES
}


SCENE_COVERAGE_PACKS: tuple[SceneCoveragePack, ...] = (
    SceneCoveragePack(
        pack_id="quick_formatting",
        label="Quick Word formatting",
        natural_requests=("format word", "clean document", "normalize report"),
        primary_landings=("report", "custom", "technical", "official"),
        secondary_landings=("TemplateConfig", "ObjectPreflight", "DeliveryPreset"),
        executable_scene_ids=("report", "custom", "technical", "official"),
        capability_axis_ids=(
            "template_baseline",
            "structure_scope",
            "object_preflight",
            "delivery_preset",
        ),
        workflow_archetype_ids=(
            "template_normalization",
            "scope_localization",
            "object_safety",
            "submission_archive",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "styles",
            "numbering",
            "table_grid",
            "fields",
            "headers_footers",
            "comments_revisions",
            "ole_embedded_vba",
        ),
        boundary="does not judge professional compliance",
        implemented_closures=(
            "P0 workbench scenes can execute template-driven formatting",
            "object preflight and delivery preset summaries are visible in Workbench",
            "pre-execution output target issue queue",
            "filterable Workbench problem center",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="chinese_academic",
        label="Chinese academic documents",
        natural_requests=("thesis", "course paper", "literature review", "proposal"),
        primary_landings=("thesis", "thesis_cn"),
        secondary_landings=("CountProfile", "references", "formula", "caption"),
        executable_scene_ids=("thesis",),
        planned_family_ids=("thesis_cn",),
        capability_axis_ids=(
            "template_baseline",
            "structure_scope",
            "material_schema",
            "count_profile",
            "delivery_preset",
        ),
        workflow_archetype_ids=(
            "structured_input",
            "template_normalization",
            "scope_localization",
            "count_compliance",
            "citation_reference",
            "formula_symbol",
            "submission_archive",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "styles",
            "numbering",
            "table_grid",
            "drawing_media_rels",
            "fields",
            "headers_footers",
            "footnotes_endnotes",
        ),
        boundary="does not absorb English journal submission or exam generation",
        implemented_closures=(
            "thesis top-level scene exists and remains separate from journal/exam packs",
            "count profile and Word story scanning base are available",
            "explicit thesis_cn profile split with planned family and library-backed scene defaults",
            "citation and formula confidence reporting in JSON/Markdown reports",
            "school rule source and section classifier confirmation context is exposed as scene material schema",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="english_journal",
        label="English journal submission",
        natural_requests=("journal manuscript", "cover letter", "revision", "submission package"),
        primary_landings=("journal_en",),
        secondary_landings=("BibTeX/CSL", "journal CountProfile", "DeliveryPreset"),
        planned_family_ids=("journal_en",),
        capability_axis_ids=(
            "input_fact_source",
            "structure_scope",
            "count_profile",
            "object_preflight",
            "delivery_preset",
            "plugin_boundary",
        ),
        workflow_archetype_ids=(
            "structured_input",
            "object_safety",
            "scope_localization",
            "count_compliance",
            "citation_reference",
            "formula_symbol",
            "submission_archive",
            "review_compare",
            "plugin_manual_gate",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "styles",
            "table_grid",
            "drawing_media_rels",
            "fields",
            "comments_revisions",
            "package_relationships",
            "ole_embedded_vba",
        ),
        boundary="does not promise publisher-final layout or unreviewed rule fetching",
        plugin_boundary=True,
        implemented_closures=(
            "planning family registry records journal-specific workflow and boundaries",
            "material schema, count profiles, and OOXML touchpoints are registered",
            "BibTeX/CSL parser and citation checks first slice",
            "submission package runtime and report evidence first slice",
            "reviewed journal rule source governance registry and report evidence first slice",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="exam_education",
        label="Exam and teaching materials",
        natural_requests=("student version", "teacher version", "answer key", "handout"),
        primary_landings=("exam_teaching",),
        secondary_landings=("structured JSON", "ContentVisibilityRule", "DeliveryPreset"),
        executable_scene_ids=("exam",),
        planned_family_ids=("exam_teaching",),
        capability_axis_ids=(
            "input_fact_source",
            "material_schema",
            "content_visibility",
            "count_profile",
            "delivery_preset",
            "plugin_boundary",
        ),
        workflow_archetype_ids=(
            "structured_input",
            "content_visibility",
            "formula_symbol",
            "count_compliance",
            "asset_attachment_inventory",
            "batch_generation",
            "submission_archive",
            "plugin_manual_gate",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "numbering",
            "table_grid",
            "fixed_row_height",
            "drawing_media_rels",
            "fields",
            "package_relationships",
        ),
        boundary="does not guarantee AI content quality or complex diagram generation",
        plugin_boundary=True,
        implemented_closures=(
            "planning family registry records structured source and multi-version intent",
            "material schemas and plugin-boundary Workbench warning are available",
            "question schema validation runtime first slice",
            "student/teacher/answer delivery presets first slice",
            "AI quality and complex diagram plugin/manual gate entry is registered",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="bidding_materials",
        label="Bidding and qualification packages",
        natural_requests=("bid document", "tender copy", "seal assets", "qualification archive"),
        primary_landings=("bidding",),
        secondary_landings=("qualification_archive_packages", "MaterialSchema", "BatchPreset"),
        executable_scene_ids=("bidding",),
        planned_family_ids=("qualification_archive_packages",),
        capability_axis_ids=(
            "material_schema",
            "object_preflight",
            "delivery_preset",
            "batch_preset",
        ),
        workflow_archetype_ids=(
            "template_normalization",
            "material_fill",
            "asset_attachment_inventory",
            "object_safety",
            "submission_archive",
            "batch_generation",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "styles",
            "numbering",
            "table_grid",
            "fixed_row_height",
            "content_controls",
            "drawing_media_rels",
            "fields",
            "headers_footers",
            "package_relationships",
        ),
        boundary="does not judge bidding strategy, legal conclusions, or certificate authenticity",
        implemented_closures=(
            "bidding top-level scene and bid material schema are executable",
            "missing material fields and assets enter the Workbench issue queue",
            "qualification archive directory rules flow through schema, manifest, and package paths",
            "multi-company batch failure isolation is visible in batch payloads, reports, and UI summaries",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="official_policy",
        label="Official and policy documents",
        natural_requests=("notice", "letter", "minutes", "policy collection"),
        primary_landings=("official",),
        secondary_landings=("meeting_policy_documents", "official profile"),
        executable_scene_ids=("official",),
        planned_family_ids=("meeting_policy_documents",),
        capability_axis_ids=(
            "template_baseline",
            "material_schema",
            "structure_scope",
            "object_preflight",
            "delivery_preset",
        ),
        workflow_archetype_ids=(
            "template_normalization",
            "scope_localization",
            "material_fill",
            "object_safety",
            "review_compare",
            "submission_archive",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "styles",
            "numbering",
            "fields",
            "headers_footers",
            "comments_revisions",
            "textbox_shape",
        ),
        boundary="does not create many small administrative top-level scenes",
        implemented_closures=(
            "official top-level scene is executable",
            "meeting/policy planning family is covered without expanding navigation",
            "numbering preservation evidence in JSON/Markdown reports",
            "policy archive profile defaults for formal/internal/archive delivery",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="technical_long_docs",
        label="Technical and long documents",
        natural_requests=("SOP", "interface manual", "acceptance report", "book manuscript"),
        primary_landings=("technical",),
        secondary_landings=("long_document_publishing", "ObjectPreflight", "archive preset"),
        executable_scene_ids=("technical",),
        planned_family_ids=("long_document_publishing",),
        capability_axis_ids=(
            "template_baseline",
            "structure_scope",
            "object_preflight",
            "delivery_preset",
        ),
        workflow_archetype_ids=(
            "template_normalization",
            "scope_localization",
            "object_safety",
            "review_compare",
            "submission_archive",
            "citation_reference",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "styles",
            "numbering",
            "table_grid",
            "drawing_media_rels",
            "fields",
            "headers_footers",
            "comments_revisions",
            "ole_embedded_vba",
            "package_relationships",
        ),
        boundary="does not verify technical truth or replace publisher systems",
        implemented_closures=(
            "technical top-level scene is executable",
            "object preflight risks can enter Workbench issue items",
            "chapter inventory runtime and report evidence first slice",
            "proof/review/final/archive delivery presets",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="application_reports",
        label="Project applications and product reports",
        natural_requests=("application book", "review package", "whitepaper", "pre-sales document"),
        primary_landings=("project_application", "report", "product_sales_documents"),
        secondary_landings=("attachment inventory", "CountProfile", "DeliveryPreset"),
        executable_scene_ids=("report",),
        planned_family_ids=("project_application", "product_sales_documents"),
        capability_axis_ids=(
            "input_fact_source",
            "material_schema",
            "count_profile",
            "object_preflight",
            "delivery_preset",
        ),
        workflow_archetype_ids=(
            "structured_input",
            "material_fill",
            "asset_attachment_inventory",
            "count_compliance",
            "object_safety",
            "submission_archive",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "styles",
            "table_grid",
            "drawing_media_rels",
            "fields",
            "headers_footers",
            "package_relationships",
        ),
        boundary="does not replace submission systems or promise marketing copy quality",
        implemented_closures=(
            "report top-level scene covers lightweight application and product documents",
            "project and product planning families are covered by manifest",
            "project attachment inventory profile with material manifest/package evidence",
            "section word-limit report evidence",
            "product/pre-sales package presets with customer/internal/package delivery defaults",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="contract_delivery",
        label="Contract delivery",
        natural_requests=("review copy", "signing copy", "field consistency", "signature package"),
        primary_landings=("contract_delivery",),
        secondary_landings=("MaterialSchema", "compare_docx", "ObjectPreflight"),
        planned_family_ids=("contract_delivery",),
        capability_axis_ids=(
            "input_fact_source",
            "material_schema",
            "object_preflight",
            "delivery_preset",
        ),
        workflow_archetype_ids=(
            "structured_input",
            "material_fill",
            "field_consistency",
            "object_safety",
            "review_compare",
            "submission_archive",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "fields",
            "content_controls",
            "headers_footers",
            "comments_revisions",
            "hidden_text",
            "package_relationships",
        ),
        boundary="does not provide legal advice or judge clause validity",
        implemented_closures=(
            "contract planning family can apply schema, count profile, and delivery defaults",
            "contract field consistency has report and Workbench summary evidence",
            "legal boundary wording in contract delivery reports",
            "signature placement and signing package manifest",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="batch_forms",
        label="Batch HR and fixed-layout forms",
        natural_requests=("offer batch", "certificate batch", "fixed form", "registration form"),
        primary_landings=("hr_batch_documents", "form_batch_documents"),
        secondary_landings=("BatchPreset", "content controls", "w:trHeight"),
        planned_family_ids=("hr_batch_documents", "form_batch_documents"),
        capability_axis_ids=(
            "input_fact_source",
            "material_schema",
            "structure_scope",
            "delivery_preset",
            "batch_preset",
        ),
        workflow_archetype_ids=(
            "structured_input",
            "material_fill",
            "batch_generation",
            "fixed_layout_table",
            "placeholder_residue",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "table_grid",
            "fixed_row_height",
            "content_controls",
            "textbox_shape",
            "fields",
            "headers_footers",
        ),
        boundary="does not verify personnel or business data truthfulness",
        implemented_closures=(
            "HR and form planning families are covered without top-level navigation",
            "batch/material primitives exist for multi-record workflows",
            "w:trHeight row-height execution policy is fixed-layout scoped",
            "content control and textbox placeholder replacement runtime first slice",
            "content control tag/alias and textbox docPr anchored field mapping first slice",
            "VML shape textbox anchored field mapping first slice",
            "profile aliases and fixed-layout mapping report evidence first slice",
            "per-record batch issue payload and report first slice",
            "Workbench batch issue center UI consumption first slice",
            "batch issue profile-specific repair routing first slice",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="professional_disclosure",
        label="Finance, disclosure, IP, and bilingual review",
        natural_requests=("quote", "budget", "ESG report", "patent draft", "bilingual review"),
        primary_landings=(
            "finance_quote_documents",
            "regulated_disclosure_documents",
            "ip_patent_documents",
            "bilingual_translation_documents",
        ),
        secondary_landings=("professional plugin", "review copy", "archive package"),
        planned_family_ids=(
            "finance_quote_documents",
            "regulated_disclosure_documents",
            "ip_patent_documents",
            "bilingual_translation_documents",
        ),
        capability_axis_ids=(
            "input_fact_source",
            "material_schema",
            "count_profile",
            "object_preflight",
            "delivery_preset",
            "plugin_boundary",
        ),
        workflow_archetype_ids=(
            "structured_input",
            "material_fill",
            "count_compliance",
            "object_safety",
            "review_compare",
            "submission_archive",
            "plugin_manual_gate",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "numbering",
            "table_grid",
            "drawing_media_rels",
            "fields",
            "comments_revisions",
            "hidden_text",
            "ole_embedded_vba",
            "package_relationships",
        ),
        boundary="does not perform audit, legal, patent, finance, or translation-quality judgment",
        plugin_boundary=True,
        implemented_closures=(
            "finance, disclosure, IP, and bilingual planning families are registered",
            "plugin-boundary Workbench warning is available for professional families",
            "professional plugin entry and manual confirmation flow is registered",
            "audit/legal/patent/finance/translation boundary report text is emitted",
            "archive package presets for disclosure-style documents",
        ),
        closure_tasks=(),
    ),
    SceneCoveragePack(
        pack_id="import_ai_boundary",
        label="Import and AI assistance",
        natural_requests=("OCR import", "PDF to Word", "full LaTeX", "AI content", "complex diagrams"),
        primary_landings=("plugin", "input_assistant"),
        secondary_landings=("confidence report", "manual confirmation", "asset import"),
        capability_axis_ids=(
            "input_fact_source",
            "object_preflight",
            "delivery_preset",
            "plugin_boundary",
        ),
        workflow_archetype_ids=(
            "structured_input",
            "asset_attachment_inventory",
            "object_safety",
            "submission_archive",
            "plugin_manual_gate",
        ),
        word_risk_surface_ids=(
            "paragraph_run",
            "table_grid",
            "drawing_media_rels",
            "textbox_shape",
            "fields",
            "package_relationships",
            "ole_embedded_vba",
        ),
        boundary="core does not promise lossless import or content quality",
        plugin_boundary=True,
        implemented_closures=(
            "import and AI risks are represented as a dedicated coverage pack",
            "plugin-boundary issue model can surface the boundary in Workbench",
            "actual plugin entry point is registered in plugin/manual gate registry",
            "confidence report contract for OCR/PDF/LaTeX import is represented",
            "manual confirmation gate before core execution is visible in Workbench/report evidence",
        ),
        closure_tasks=(),
    ),
)


CAPABILITY_AXIS_MAP: dict[str, CapabilityAxis] = {
    axis.axis_id: axis for axis in CAPABILITY_AXES
}

SCENE_COVERAGE_PACK_MAP: dict[str, SceneCoveragePack] = {
    pack.pack_id: pack for pack in SCENE_COVERAGE_PACKS
}

CAPABILITY_AXIS_REQUIRED_WORKFLOW_OPTIONS: dict[str, tuple[tuple[str, ...], ...]] = {
    "input_fact_source": (("structured_input",),),
    "template_baseline": (("template_normalization",),),
    "material_schema": (("structured_input", "material_fill"),),
    "structure_scope": (("scope_localization", "fixed_layout_table"),),
    "content_visibility": (("content_visibility",),),
    "count_profile": (("count_compliance",),),
    "object_preflight": (("object_safety", "plugin_manual_gate"),),
    "delivery_preset": (
        (
            "submission_archive",
            "content_visibility",
            "batch_generation",
            "review_compare",
        ),
    ),
    "batch_preset": (("batch_generation",),),
    "plugin_boundary": (("plugin_manual_gate",),),
}

WORKFLOW_REQUIRED_WORD_RISK_OPTIONS: dict[str, tuple[tuple[str, ...], ...]] = {
    "template_normalization": (("paragraph_run",), ("styles",)),
    "scope_localization": (("paragraph_run", "numbering", "fields"),),
    "structured_input": (("paragraph_run", "fields", "table_grid"),),
    "material_fill": (("paragraph_run",), ("fields", "content_controls", "textbox_shape")),
    "asset_attachment_inventory": (("drawing_media_rels", "package_relationships"),),
    "content_visibility": (("fields", "hidden_text"),),
    "batch_generation": (("table_grid", "package_relationships"),),
    "count_compliance": (("table_grid", "fields", "footnotes_endnotes"),),
    "citation_reference": (("fields", "footnotes_endnotes"),),
    "formula_symbol": (("drawing_media_rels", "fields"),),
    "fixed_layout_table": (
        ("table_grid",),
        ("fixed_row_height",),
        ("content_controls", "textbox_shape"),
    ),
    "object_safety": (
        (
            "ole_embedded_vba",
            "package_relationships",
            "drawing_media_rels",
            "comments_revisions",
        ),
    ),
    "review_compare": (("comments_revisions", "hidden_text"),),
    "submission_archive": (("package_relationships", "headers_footers"),),
    "field_consistency": (("fields", "content_controls"),),
    "placeholder_residue": (("content_controls", "textbox_shape", "fields"),),
    "plugin_manual_gate": (
        ("ole_embedded_vba", "package_relationships", "drawing_media_rels"),
    ),
}


def list_capability_axes() -> tuple[CapabilityAxis, ...]:
    """Return all cross-cutting capability axes."""

    return CAPABILITY_AXES


def list_scene_completeness_gates() -> tuple[SceneCompletenessGate, ...]:
    """Return gates that every complete scene capability must answer."""

    return SCENE_COMPLETENESS_GATES


def list_workflow_archetypes() -> tuple[WorkflowArchetype, ...]:
    """Return reusable workflow archetypes used by coverage packs."""

    return WORKFLOW_ARCHETYPES


def list_word_risk_surfaces() -> tuple[WordRiskSurface, ...]:
    """Return Word/OOXML risk surfaces used by coverage packs."""

    return WORD_RISK_SURFACES


def get_capability_axis(axis_id: str) -> CapabilityAxis:
    """Look up one capability axis by id."""

    normalized = str(axis_id or "").strip()
    try:
        return CAPABILITY_AXIS_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown capability axis: {axis_id}") from exc


def get_scene_completeness_gate(gate_id: str) -> SceneCompletenessGate:
    """Look up one completeness gate by id."""

    normalized = str(gate_id or "").strip()
    try:
        return SCENE_COMPLETENESS_GATE_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown scene completeness gate: {gate_id}") from exc


def get_workflow_archetype(archetype_id: str) -> WorkflowArchetype:
    """Look up one workflow archetype by id."""

    normalized = str(archetype_id or "").strip()
    try:
        return WORKFLOW_ARCHETYPE_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown workflow archetype: {archetype_id}") from exc


def get_word_risk_surface(surface_id: str) -> WordRiskSurface:
    """Look up one Word/OOXML risk surface by id."""

    normalized = str(surface_id or "").strip()
    try:
        return WORD_RISK_SURFACE_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown Word risk surface: {surface_id}") from exc


def list_scene_coverage_packs() -> tuple[SceneCoveragePack, ...]:
    """Return all high-frequency coverage packs."""

    return SCENE_COVERAGE_PACKS


def get_scene_coverage_pack(pack_id: str) -> SceneCoveragePack:
    """Look up one coverage pack by id."""

    normalized = str(pack_id or "").strip()
    try:
        return SCENE_COVERAGE_PACK_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown scene coverage pack: {pack_id}") from exc


def coverage_packs_for_family(family_id: str) -> tuple[SceneCoveragePack, ...]:
    """Return coverage packs that claim a planned scene family."""

    normalized = str(family_id or "").strip()
    return tuple(
        pack for pack in SCENE_COVERAGE_PACKS if normalized in pack.planned_family_ids
    )


def coverage_packs_for_scene(scene_id: str) -> tuple[SceneCoveragePack, ...]:
    """Return coverage packs that claim an executable top-level scene."""

    normalized = str(scene_id or "").strip()
    return tuple(
        pack for pack in SCENE_COVERAGE_PACKS if normalized in pack.executable_scene_ids
    )


def coverage_candidate_keys_for_config(config) -> tuple[str, ...]:
    """Return scene/family/schema keys that may imply coverage packs."""

    if config is None:
        return ()

    candidates: list[str] = []
    scene_id = str(getattr(config, "scene_id", "") or "").strip()
    category = str(getattr(config, "category", "") or "").strip()
    candidates.extend([scene_id, category])

    compliance = getattr(config, "compliance_profile", None)
    rule_family = str(getattr(compliance, "rule_family", "") or "").strip()
    profile_id = str(getattr(compliance, "profile_id", "") or "").strip()
    candidates.extend([rule_family, profile_id])

    if (
        scene_id == "official"
        or category in {"government", "official"}
        or rule_family
        in {
            "official_document",
            "meeting_minutes",
            "policy_collection",
            "meeting_policy_documents",
        }
        or profile_id
        in {
            "official_document",
            "meeting_minutes",
            "policy_collection",
            "meeting_policy_documents_default",
        }
    ):
        candidates.append("meeting_policy_documents")

    input_profile = getattr(config, "input_source_profile", None)
    schema_ids = resolve_material_schema_ids(
        str(getattr(input_profile, "material_schema_id", "") or "").strip(),
        list(getattr(input_profile, "material_schema_ids", []) or []),
    )
    for schema_id in schema_ids:
        try:
            family_id = get_material_schema(schema_id).family
        except KeyError:
            continue
        candidates.append(family_id)
        if family_id == "official":
            candidates.append("meeting_policy_documents")
    return _unique_texts(candidates)


def coverage_packs_for_config(config) -> tuple[SceneCoveragePack, ...]:
    """Resolve coverage packs for a runtime/UI/report config object."""

    packs: list[SceneCoveragePack] = []
    for key in coverage_candidate_keys_for_config(config):
        if key in SCENE_COVERAGE_PACK_MAP:
            packs.append(SCENE_COVERAGE_PACK_MAP[key])
        packs.extend(coverage_packs_for_scene(key))
        packs.extend(coverage_packs_for_family(key))
    return _dedupe_scene_coverage_packs(packs)


def _dedupe_scene_coverage_packs(
    packs: list[SceneCoveragePack],
) -> tuple[SceneCoveragePack, ...]:
    result: list[SceneCoveragePack] = []
    seen: set[str] = set()
    for pack in packs:
        if pack.pack_id in seen:
            continue
        seen.add(pack.pack_id)
        result.append(pack)
    return tuple(result)


def planned_family_ids_in_coverage() -> tuple[str, ...]:
    """Return unique planned family ids referenced by coverage packs."""

    return _unique_texts(
        family_id
        for pack in SCENE_COVERAGE_PACKS
        for family_id in pack.planned_family_ids
    )


def executable_scene_ids_in_coverage() -> tuple[str, ...]:
    """Return unique executable scene ids referenced by coverage packs."""

    return _unique_texts(
        scene_id
        for pack in SCENE_COVERAGE_PACKS
        for scene_id in pack.executable_scene_ids
    )


def build_scene_coverage_summary(pack: SceneCoveragePack) -> str:
    """Build a compact audit summary for docs and tests."""

    axes = "/".join(pack.capability_axis_ids[:4])
    workflows = "/".join(pack.workflow_archetype_ids[:3])
    primary = "/".join(pack.primary_landings[:3])
    families = "/".join(pack.planned_family_ids[:3]) or "-"
    scenes = "/".join(pack.executable_scene_ids[:3]) or "-"
    return (
        f"{pack.pack_id}: primary={primary}; scenes={scenes}; "
        f"families={families}; axes={axes}; workflows={workflows}; "
        f"plugin={pack.plugin_boundary}; "
        f"closures={len(pack.implemented_closures)}/{len(pack.missing_closures)}"
    )


def coverage_packs_with_missing_closures() -> tuple[SceneCoveragePack, ...]:
    """Return coverage packs that still have explicit missing closure work."""

    return tuple(pack for pack in SCENE_COVERAGE_PACKS if pack.missing_closures)


def build_scene_coverage_closure_summary(pack: SceneCoveragePack) -> str:
    """Build a compact closure summary for audit surfaces."""

    next_task = pack.closure_tasks[0] if pack.closure_tasks else None
    if next_task is not None:
        next_missing = (
            f"{next_task.priority}/{next_task.owner}/{next_task.target_phase}: "
            f"{next_task.summary}"
        )
    else:
        next_missing = pack.missing_closures[0] if pack.missing_closures else "-"
    return (
        f"{pack.pack_id}: implemented={len(pack.implemented_closures)}; "
        f"missing={len(pack.missing_closures)}; next={next_missing}"
    )


def audit_scene_pack_completeness() -> tuple[ScenePackCompletenessAuditResult, ...]:
    """Audit every coverage pack against gates, workflows, and Word risks."""

    required_gates = set(SCENE_COMPLETENESS_GATE_IDS)
    known_workflows = set(WORKFLOW_ARCHETYPE_MAP)
    known_word_risks = set(WORD_RISK_SURFACE_MAP)
    return tuple(
        ScenePackCompletenessAuditResult(
            pack_id=pack.pack_id,
            missing_gate_ids=tuple(
                gate_id
                for gate_id in SCENE_COMPLETENESS_GATE_IDS
                if gate_id not in set(pack.completeness_gate_ids)
            ),
            unknown_workflow_archetype_ids=tuple(
                workflow_id
                for workflow_id in pack.workflow_archetype_ids
                if workflow_id not in known_workflows
            ),
            unknown_word_risk_surface_ids=tuple(
                surface_id
                for surface_id in pack.word_risk_surface_ids
                if surface_id not in known_word_risks
            ),
        )
        for pack in SCENE_COVERAGE_PACKS
        if (
            required_gates - set(pack.completeness_gate_ids)
            or set(pack.workflow_archetype_ids) - known_workflows
            or set(pack.word_risk_surface_ids) - known_word_risks
        )
    )


def audit_scene_pack_matrix_alignment() -> tuple[ScenePackMatrixAlignmentAuditResult, ...]:
    """Audit whether high-frequency packs align axes, workflows, and Word risks."""

    results: list[ScenePackMatrixAlignmentAuditResult] = []
    for pack in SCENE_COVERAGE_PACKS:
        workflow_ids = set(pack.workflow_archetype_ids)
        word_risk_ids = set(pack.word_risk_surface_ids)
        missing_axis_workflows = tuple(
            requirement
            for axis_id in pack.capability_axis_ids
            for requirement in _missing_required_options(
                f"{axis_id}:",
                CAPABILITY_AXIS_REQUIRED_WORKFLOW_OPTIONS.get(axis_id, ()),
                workflow_ids,
            )
        )
        missing_workflow_word_risks = tuple(
            requirement
            for workflow_id in pack.workflow_archetype_ids
            for requirement in _missing_required_options(
                f"{workflow_id}:",
                WORKFLOW_REQUIRED_WORD_RISK_OPTIONS.get(workflow_id, ()),
                word_risk_ids,
            )
        )
        if missing_axis_workflows or missing_workflow_word_risks:
            results.append(
                ScenePackMatrixAlignmentAuditResult(
                    pack_id=pack.pack_id,
                    missing_axis_workflow_ids=missing_axis_workflows,
                    missing_workflow_word_risk_ids=missing_workflow_word_risks,
                )
            )
    return tuple(results)


def audit_scene_closure_validation_commands(
    root: str | Path = ".",
) -> tuple[SceneClosureValidationEvidence, ...]:
    """Audit whether closure validation commands point to traceable tests.

    This is intentionally a static audit: it checks that commands reference
    existing test files and that those files contain at least one trace token
    from the pack, family, axis, or task summary. Running pytest remains the
    responsibility of the validation command itself.
    """

    root_path = Path(root)
    evidence: list[SceneClosureValidationEvidence] = []
    for pack in SCENE_COVERAGE_PACKS:
        for task in pack.closure_tasks:
            for command in task.validation_commands:
                target_paths = _validation_command_test_paths(command)
                missing_paths = tuple(
                    path for path in target_paths if not (root_path / path).exists()
                )
                trace_tokens = _closure_trace_tokens(pack, task)
                trace_hits = _closure_trace_hits(
                    root_path,
                    target_paths,
                    trace_tokens,
                )
                evidence.append(
                    SceneClosureValidationEvidence(
                        pack_id=pack.pack_id,
                        task_summary=task.summary,
                        command=command,
                        target_paths=target_paths,
                        missing_paths=missing_paths,
                        trace_tokens=trace_tokens,
                        trace_hits=trace_hits,
                        status=_closure_validation_status(
                            command,
                            target_paths,
                            missing_paths,
                            trace_hits,
                        ),
                    )
                )
    return tuple(evidence)


def _validation_command_test_paths(command: str) -> tuple[str, ...]:
    try:
        parts = shlex.split(str(command or ""), posix=False)
    except ValueError:
        parts = str(command or "").split()
    paths: list[str] = []
    for part in parts:
        normalized = str(part or "").strip().strip("'\"").replace("\\", "/")
        if normalized.startswith("tests/") and normalized not in paths:
            paths.append(normalized)
    return tuple(paths)


def _closure_trace_tokens(
    pack: SceneCoveragePack,
    task: SceneClosureTask,
) -> tuple[str, ...]:
    seed_values = (
        pack.pack_id,
        *pack.executable_scene_ids,
        *pack.planned_family_ids,
        *pack.capability_axis_ids,
        task.summary,
    )
    tokens: list[str] = []
    stop_words = {
        "actual",
        "after",
        "and",
        "before",
        "core",
        "every",
        "flow",
        "for",
        "from",
        "into",
        "the",
        "with",
    }
    for value in seed_values:
        for token in re.split(r"[^A-Za-z0-9_]+", str(value or "").lower()):
            if len(token) < 4 or token in stop_words:
                continue
            if token not in tokens:
                tokens.append(token)
    return tuple(tokens)


def _closure_trace_hits(
    root: Path,
    target_paths: tuple[str, ...],
    trace_tokens: tuple[str, ...],
) -> tuple[str, ...]:
    content_parts: list[str] = []
    for target_path in target_paths:
        path = root / target_path
        if not path.exists():
            continue
        content_parts.append(path.read_text(encoding="utf-8", errors="ignore").lower())
    content = "\n".join(content_parts)
    return tuple(token for token in trace_tokens if token in content)


def _closure_validation_status(
    command: str,
    target_paths: tuple[str, ...],
    missing_paths: tuple[str, ...],
    trace_hits: tuple[str, ...],
) -> str:
    normalized = str(command or "").strip()
    if not normalized.startswith("python -m pytest ") or not normalized.endswith(" -q"):
        return "invalid_command"
    if not target_paths:
        return "missing_targets"
    if missing_paths:
        return "missing_paths"
    if not trace_hits:
        return "weak_trace"
    return "ok"


def _missing_required_options(
    prefix: str,
    requirement_groups: tuple[tuple[str, ...], ...],
    declared_ids: set[str],
) -> tuple[str, ...]:
    return tuple(
        f"{prefix}{'|'.join(options)}"
        for options in requirement_groups
        if options and not (set(options) & declared_ids)
    )


def _unique_texts(values) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "CAPABILITY_AXES",
    "CAPABILITY_AXIS_MAP",
    "SCENE_COMPLETENESS_GATES",
    "SCENE_COMPLETENESS_GATE_IDS",
    "SCENE_COMPLETENESS_GATE_MAP",
    "SCENE_COVERAGE_PACKS",
    "SCENE_COVERAGE_PACK_MAP",
    "WORD_RISK_SURFACES",
    "WORD_RISK_SURFACE_MAP",
    "WORKFLOW_ARCHETYPES",
    "WORKFLOW_ARCHETYPE_MAP",
    "CapabilityAxis",
    "SceneCompletenessGate",
    "SceneClosureValidationEvidence",
    "SceneClosureTask",
    "ScenePackCompletenessAuditResult",
    "ScenePackMatrixAlignmentAuditResult",
    "SceneCoveragePack",
    "WordRiskSurface",
    "WorkflowArchetype",
    "audit_scene_closure_validation_commands",
    "audit_scene_pack_matrix_alignment",
    "audit_scene_pack_completeness",
    "build_scene_coverage_closure_summary",
    "build_scene_coverage_summary",
    "coverage_candidate_keys_for_config",
    "coverage_packs_for_config",
    "coverage_packs_for_family",
    "coverage_packs_for_scene",
    "coverage_packs_with_missing_closures",
    "executable_scene_ids_in_coverage",
    "get_capability_axis",
    "get_scene_completeness_gate",
    "get_scene_coverage_pack",
    "get_word_risk_surface",
    "get_workflow_archetype",
    "list_capability_axes",
    "list_scene_completeness_gates",
    "list_scene_coverage_packs",
    "list_word_risk_surfaces",
    "list_workflow_archetypes",
    "planned_family_ids_in_coverage",
]
