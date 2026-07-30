"""Minimal product-runtime scene coverage manifest.\n\nEngineering audits remain in src.config.scene_coverage_manifest; this module keeps only the immutable data and selectors required by the shipping UI, pipeline, and reports.\n"""


from __future__ import annotations


from dataclasses import dataclass, field


from src.config.material_schema_registry import get_material_schema, resolve_material_schema_ids


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


SCENE_COMPLETENESS_GATE_IDS: tuple[str, ...] = (
    "natural_request_alias",
    "ownership_layer",
    "fact_source",
    "workflow_slots",
    "word_risk_surface",
    "ui_control_contract",
    "executable_chain",
    "report_issue_artifact",
    "test_evidence",
)


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
            "pre-execution risks use the unified execution gate",
            "compact execution feedback links to accessible result details",
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
        executable_scene_ids=("exam", "exam_quiz", "exam_term"),
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
            "material schemas and the compact policy-aware execution gate are available",
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
            "missing material fields and assets use a policy-aware gate and one repair action",
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
            "object preflight risks use compact confirmation and pipeline protection",
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
            "per-record batch diagnostics payload and report first slice",
            "execution-result detail consumes batch diagnostics first slice",
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


SCENE_COVERAGE_PACK_MAP: dict[str, SceneCoveragePack] = {
    pack.pack_id: pack for pack in SCENE_COVERAGE_PACKS
}


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


def _unique_texts(values) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_COMPLETENESS_GATE_IDS",
    "SCENE_COVERAGE_PACKS",
    "SCENE_COVERAGE_PACK_MAP",
    "SceneClosureTask",
    "SceneCoveragePack",
    "coverage_candidate_keys_for_config",
    "coverage_packs_for_config",
    "coverage_packs_for_family",
    "coverage_packs_for_scene",
    "get_scene_coverage_pack",
    "list_scene_coverage_packs",
]
