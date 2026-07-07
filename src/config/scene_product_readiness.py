"""Product readiness registry for the high-level scene matrix.

Coverage-pack closure is a static planning signal.  Product readiness is a
separate promise about what users can rely on in UI, execution, reports,
artifacts, samples, and tests.  This side registry keeps the two signals from
being silently conflated.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.scene_coverage_manifest import SCENE_COVERAGE_PACK_MAP
from src.config.scene_family_registry import PLANNED_SCENE_FAMILY_MAP


SCENE_READINESS_SUBJECT_TYPES: tuple[str, ...] = ("pack", "family")
STATIC_CLOSURE_LEVELS: tuple[str, ...] = ("declared", "audited", "closed")
PRODUCT_READINESS_LEVELS: tuple[str, ...] = (
    "gray_l1",
    "blue_boundary",
    "yellow_l3",
    "orange_l4",
    "green_l5",
)


@dataclass(frozen=True, slots=True)
class SceneProductReadinessSpec:
    subject_type: str
    subject_id: str
    static_closure_level: str
    product_readiness_level: str
    evidence_surfaces: tuple[str, ...]
    remaining_product_gaps: tuple[str, ...]
    rationale: str

    @property
    def is_green(self) -> bool:
        return self.product_readiness_level == "green_l5"

    @property
    def is_boundary(self) -> bool:
        return self.product_readiness_level == "blue_boundary"


@dataclass(frozen=True, slots=True)
class SceneProductReadinessAuditResult:
    subject_type: str
    subject_id: str
    issue: str
    expected: str = ""
    actual: str = ""

    @property
    def is_clean(self) -> bool:
        return not self.issue


def _pack(
    subject_id: str,
    product_readiness_level: str,
    evidence_surfaces: tuple[str, ...],
    remaining_product_gaps: tuple[str, ...],
    rationale: str,
    *,
    static_closure_level: str = "closed",
) -> SceneProductReadinessSpec:
    return SceneProductReadinessSpec(
        subject_type="pack",
        subject_id=subject_id,
        static_closure_level=static_closure_level,
        product_readiness_level=product_readiness_level,
        evidence_surfaces=evidence_surfaces,
        remaining_product_gaps=remaining_product_gaps,
        rationale=rationale,
    )


def _family(
    subject_id: str,
    product_readiness_level: str,
    evidence_surfaces: tuple[str, ...],
    remaining_product_gaps: tuple[str, ...],
    rationale: str,
    *,
    static_closure_level: str = "audited",
) -> SceneProductReadinessSpec:
    return SceneProductReadinessSpec(
        subject_type="family",
        subject_id=subject_id,
        static_closure_level=static_closure_level,
        product_readiness_level=product_readiness_level,
        evidence_surfaces=evidence_surfaces,
        remaining_product_gaps=remaining_product_gaps,
        rationale=rationale,
    )


SCENE_PRODUCT_READINESS_SPECS: tuple[SceneProductReadinessSpec, ...] = (
    _pack(
        "quick_formatting",
        "green_l5",
        (
            "router",
            "template controls",
            "issue queue",
            "report",
            "sample fixture",
            "field-level template repair routing",
            "real business template fixture",
        ),
        (),
        (
            "General formatting has router, template controls, issue queue, "
            "report, field-level template repair routing, and real business "
            "template fixture evidence."
        ),
    ),
    _pack(
        "chinese_academic",
        "green_l5",
        (
            "count profile",
            "rule source registry",
            "citation/formula report",
            "sample fixture",
            "school rule source governance UI",
            "section classifier confirmation",
            "academic rule evidence UI",
        ),
        (),
        (
            "Chinese academic support has count/profile/report evidence plus "
            "school-rule source selection and section-classifier confirmation "
            "surfaces, while strict school-specific compliance remains bounded "
            "by reviewed rule data."
        ),
    ),
    _pack(
        "english_journal",
        "green_l5",
        (
            "journal family",
            "BibTeX/CSL planning",
            "submission package report",
            "sample fixture",
            "reviewed journal profile updates",
            "submission artifact manifest",
            "journal submission evidence UI",
            "publisher manual gate",
        ),
        (),
        (
            "English journal submission now connects reviewed generic profile "
            "updates, BibTeX/CSL diagnostics, submission package artifacts, "
            "sample fixtures, UI evidence, and publisher manual gates while "
            "keeping publisher-final layout and unreviewed target-journal rules "
            "outside core."
        ),
    ),
    _pack(
        "exam_education",
        "green_l5",
        (
            "question schema",
            "delivery presets",
            "runtime Word versions",
            "Markdown preview report",
            "fixed-layout answer-sheet runtime",
            "question asset runtime",
            "question asset replacement UI bridge",
            "question asset per-question runtime mapping",
            "question asset structured asset-items import bridge",
            "question asset frontstage mapping summary",
            "question asset frontstage detail table",
            "question asset frontstage row preview",
            "question asset frontstage row replacement",
            "question asset missing-file row repair",
            "question asset issue queue row routing",
            "question asset remote id/source bridge",
            "question asset remote cache path bridge",
            "question asset remote cache miss repair bridge",
            "question asset remote no-cache repair bridge",
            "question asset remote url download cache bridge",
            "question asset remote asset-url metadata download bridge",
            "question asset remote asset-id resolver bridge",
            "question asset remote authenticated download bridge",
            "question asset remote authorization UI bridge",
            "question asset remote permission failure diagnostics bridge",
            "question asset remote cache refresh bridge",
            "question asset remote cache expiry refresh bridge",
            "question asset remote conditional revalidation bridge",
            "question asset remote cache index manifest bridge",
            "question asset remote cache-hit index bridge",
            "question asset remote cache index summary bridge",
            "question asset remote cache hit-rate summary bridge",
            "question asset remote cache hit-rate trend history bridge",
            "question asset remote cache hit-rate trend history UI bridge",
            "question asset remote cache hit-rate archive trend panel UI bridge",
            "question asset remote shared cache index bridge",
            "question asset remote shared cache directory summary bridge",
            "question asset remote shared cache directory browser UI bridge",
            "question asset remote shared cache index drilldown UI bridge",
            "question asset remote shared cache directory open UI bridge",
            "question asset remote cache invalidation bridge",
            "question asset remote cache batch invalidation bridge",
            "question asset remote filtered batch cache invalidation bridge",
            "question asset remote cross-directory cache cleanup bridge",
            "question asset remote cache cleanup dry-run bridge",
            "question asset remote cache cleanup history bridge",
            "question asset remote cache cleanup history UI bridge",
            "question asset remote cache cleanup confirmation UI bridge",
            "question asset remote cache cleanup confirmed execution bridge",
            "question asset remote cache cleanup task list UI bridge",
            "question asset remote cache cleanup archive task center UI bridge",
            "question asset remote download retry bridge",
            "question asset remote cache package bridge",
            "question asset remote cache package report bridge",
            "question asset remote cache package report drilldown bridge",
            "question asset remote content metadata bridge",
            "question asset remote thumbnail preview UI bridge",
            "question asset remote thumbnail-url preview UI bridge",
            "question asset remote full-preview URL UI bridge",
            "question asset remote full-preview viewer UI bridge",
            "question asset remote full-preview zoom UI bridge",
            "question asset remote full-preview compare UI bridge",
            "question asset remote full-preview multi-compare UI bridge",
            "question asset remote full-preview manual annotation UI bridge",
            "question asset manual comparison issue queue bridge",
            "question asset batch comparison matrix report bridge",
            "question asset comparison region annotation bridge",
            "question asset comparison repair queue candidate bridge",
            "question asset comparison repair queue artifact bridge",
            "question asset comparison repair queue issue action bridge",
            "question asset comparison repair queue confirmation plan bridge",
            "question asset comparison repair queue batch confirmation preflight bridge",
            "question asset comparison repair queue batch confirmation freeze bridge",
            "question asset comparison repair queue batch apply dry-run guard bridge",
            "question asset comparison repair queue batch apply execution plan bridge",
            "question asset comparison repair queue batch apply Word media write bridge",
            "question asset comparison repair queue batch apply execution audit bridge",
            "question asset comparison repair queue batch apply audit rollback bridge",
            "question asset comparison repair queue batch apply transaction manifest bridge",
            "question asset comparison repair queue batch apply transaction manifest artifact bridge",
            "question asset comparison repair queue batch apply transaction manifest report bridge",
            "question asset comparison repair queue batch apply transaction task summary bridge",
            "question asset comparison repair queue batch apply transaction task issue-action bridge",
            "question asset comparison repair queue batch apply transaction task report-drilldown action bridge",
            "question asset comparison repair queue batch apply transaction task report-drilldown audit bridge",
            "question asset comparison repair queue frontstage apply bridge",
            "question asset comparison repair queue replacement audit bridge",
            "question asset comparison repair queue rollback bridge",
            "question asset comparison repair queue conflict guard bridge",
            "question asset comparison repair queue conflict resolution bridge",
            "question asset comparison repair queue conflict selection action bridge",
            "question asset figure group ordering bridge",
            "question asset flat figure group import bridge",
            "question asset filename mismatch preflight bridge",
            "question asset per-question asset library index UI bridge",
            "question asset per-question asset library metadata editing UI bridge",
            "question asset per-question asset library metadata issue UI bridge",
            "question asset per-question asset library version history UI bridge",
            "question asset per-question asset library version rollback UI bridge",
            "question asset per-question asset library local version consistency UI bridge",
            "question asset altText editing UI bridge",
            "question asset altText runtime/report",
            "plugin gate",
            "sample fixture",
        ),
        (),
        (
            "Exam education keeps local question-asset runtime, cache, preview, "
            "comparison, repair audit, per-question library metadata/history, "
            "local version consistency, and altText evidence after enterprise "
            "remote governance removal."
        ),
    ),
    _pack(
        "bidding_materials",
        "green_l5",
        (
            "material schema",
            "attachment package",
            "batch isolation",
            "sample fixture",
            "multi-party consortium schema",
            "seal-position residual checks",
        ),
        (),
        "Bidding packages have consortium/expiry/seal-residue evidence while certificate authenticity and bid strategy remain out of scope.",
    ),
    _pack(
        "official_policy",
        "green_l5",
        (
            "official family",
            "watermark status",
            "policy archive preset",
            "sample fixture",
            "official metadata schema",
            "formal/internal/archive report depth",
        ),
        (),
        (
            "Official documents have metadata schema, formal/internal/archive "
            "report evidence, and archive fixture coverage while administrative "
            "decision substance stays out of scope."
        ),
    ),
    _pack(
        "technical_long_docs",
        "green_l5",
        (
            "chapter inventory",
            "object preflight",
            "delivery presets",
            "sample fixture",
            "index/appendix handling",
            "multi-file merge boundary",
        ),
        (),
        (
            "Technical long docs have chapter, index/appendix, cross-reference, "
            "and multi-file boundary evidence while publisher-system merge "
            "correctness stays out of scope."
        ),
    ),
    _pack(
        "application_reports",
        "green_l5",
        (
            "project limits",
            "product/sales router",
            "journey runtime report",
            "artifact drilldown bridge",
            "attachment inventory",
            "request-cell fixture",
            "sample fixture",
            "project rule-source governance",
            "submission-system boundary UI",
            "product asset consistency UI",
            "quote/body disambiguation fixtures",
            "application/report evidence UI",
        ),
        (),
        (
            "Applications and product documents now connect project rule-source "
            "governance, submission-system boundary reporting, product asset "
            "consistency, quote/body disambiguation, fixtures, runtime reports, "
            "and artifact drilldown while keeping external system state and "
            "marketing claim truthfulness outside core."
        ),
    ),
    _pack(
        "contract_delivery",
        "green_l5",
        (
            "field consistency",
            "review/signing presets",
            "signature material",
            "sample fixture",
            "field evidence UI",
            "pre-execution legal-boundary banner",
        ),
        (),
        (
            "Contract delivery exposes field evidence and a pre-execution "
            "legal-boundary banner while keeping legal advice outside core."
        ),
    ),
    _pack(
        "batch_forms",
        "green_l5",
        (
            "batch runtime",
            "fixed row height",
            "placeholder residue",
            "sample fixture",
            "fixed-layout profile browser",
            "profile-specific preview",
            "exam answer-sheet reuse path",
            "fixed-layout batch evidence UI",
        ),
        (),
        (
            "Batch and fixed-layout forms now expose profile browsing, "
            "profile-specific previews, answer-sheet reuse evidence, row-height "
            "control contracts, fixture/report evidence, and per-record failure "
            "isolation while keeping data truthfulness outside core."
        ),
    ),
    _pack(
        "professional_disclosure",
        "blue_boundary",
        (
            "plugin gate",
            "boundary report",
            "journey runtime report",
            "professional families",
            "sample fixture",
            "boundary capability matrix",
            "professional family report depth",
        ),
        ("real plugin ecosystem",),
        (
            "Professional disclosure is boundary-complete for in-core routing, "
            "family report evidence, and UI summary, while real professional "
            "plugin ecosystems remain outside core."
        ),
    ),
    _pack(
        "import_ai_boundary",
        "blue_boundary",
        (
            "plugin gate",
            "manual confirmation",
            "journey runtime report",
            "handoff routing",
            "sample fixture",
            "boundary capability matrix",
            "confidence artifact manifest",
        ),
        ("real OCR/PDF/LaTeX plugin integration",),
        (
            "Import and AI assistance now expose confidence artifact and handoff "
            "evidence, but real OCR/PDF/LaTeX conversion integrations remain "
            "manual/plugin guarded."
        ),
    ),
    _family(
        "thesis_cn",
        "green_l5",
        (
            "scene defaults",
            "count profile",
            "rule source registry",
            "thesis school rule context schema",
            "school rule source governance UI",
            "section classifier confirmation",
        ),
        (),
        (
            "Thesis family now exposes rule-source context and section "
            "confirmation evidence beside count/profile defaults; it still "
            "does not claim every school rule is authoritative without reviewed "
            "profile data."
        ),
    ),
    _family(
        "journal_en",
        "green_l5",
        (
            "router",
            "material schema",
            "submission presets",
            "reviewed journal source updates",
            "submission artifact manifest",
            "journal submission evidence UI",
            "publisher manual gate",
        ),
        (),
        (
            "Journal family now has reviewed generic rule-source evidence, "
            "submission package artifacts, citation-source diagnostics, "
            "degraded/manual fixtures, and UI evidence while target-publisher "
            "strict layout remains a manual/plugin boundary."
        ),
    ),
    _family(
        "exam_teaching",
        "green_l5",
        (
            "question schema",
            "content visibility",
            "runtime Word versions",
            "Markdown preview report",
            "fixed-layout answer-sheet runtime",
            "question asset runtime",
            "question asset replacement UI bridge",
            "question asset per-question runtime mapping",
            "question asset structured asset-items import bridge",
            "question asset frontstage mapping summary",
            "question asset frontstage detail table",
            "question asset frontstage row preview",
            "question asset frontstage row replacement",
            "question asset missing-file row repair",
            "question asset issue queue row routing",
            "question asset remote id/source bridge",
            "question asset remote cache path bridge",
            "question asset remote cache miss repair bridge",
            "question asset remote no-cache repair bridge",
            "question asset remote url download cache bridge",
            "question asset remote asset-url metadata download bridge",
            "question asset remote asset-id resolver bridge",
            "question asset remote authenticated download bridge",
            "question asset remote authorization UI bridge",
            "question asset remote permission failure diagnostics bridge",
            "question asset remote cache refresh bridge",
            "question asset remote cache expiry refresh bridge",
            "question asset remote conditional revalidation bridge",
            "question asset remote cache index manifest bridge",
            "question asset remote cache-hit index bridge",
            "question asset remote cache index summary bridge",
            "question asset remote cache hit-rate summary bridge",
            "question asset remote cache hit-rate trend history bridge",
            "question asset remote cache hit-rate trend history UI bridge",
            "question asset remote cache hit-rate archive trend panel UI bridge",
            "question asset remote shared cache index bridge",
            "question asset remote shared cache directory summary bridge",
            "question asset remote shared cache directory browser UI bridge",
            "question asset remote shared cache index drilldown UI bridge",
            "question asset remote shared cache directory open UI bridge",
            "question asset remote cache invalidation bridge",
            "question asset remote cache batch invalidation bridge",
            "question asset remote filtered batch cache invalidation bridge",
            "question asset remote cross-directory cache cleanup bridge",
            "question asset remote cache cleanup dry-run bridge",
            "question asset remote cache cleanup history bridge",
            "question asset remote cache cleanup history UI bridge",
            "question asset remote cache cleanup confirmation UI bridge",
            "question asset remote cache cleanup confirmed execution bridge",
            "question asset remote cache cleanup task list UI bridge",
            "question asset remote cache cleanup archive task center UI bridge",
            "question asset remote download retry bridge",
            "question asset remote cache package bridge",
            "question asset remote cache package report bridge",
            "question asset remote cache package report drilldown bridge",
            "question asset remote content metadata bridge",
            "question asset remote thumbnail preview UI bridge",
            "question asset remote thumbnail-url preview UI bridge",
            "question asset remote full-preview URL UI bridge",
            "question asset remote full-preview viewer UI bridge",
            "question asset remote full-preview zoom UI bridge",
            "question asset remote full-preview compare UI bridge",
            "question asset remote full-preview multi-compare UI bridge",
            "question asset remote full-preview manual annotation UI bridge",
            "question asset manual comparison issue queue bridge",
            "question asset batch comparison matrix report bridge",
            "question asset comparison region annotation bridge",
            "question asset comparison repair queue candidate bridge",
            "question asset comparison repair queue artifact bridge",
            "question asset comparison repair queue issue action bridge",
            "question asset comparison repair queue confirmation plan bridge",
            "question asset comparison repair queue batch confirmation preflight bridge",
            "question asset comparison repair queue batch confirmation freeze bridge",
            "question asset comparison repair queue batch apply dry-run guard bridge",
            "question asset comparison repair queue batch apply execution plan bridge",
            "question asset comparison repair queue batch apply Word media write bridge",
            "question asset comparison repair queue batch apply execution audit bridge",
            "question asset comparison repair queue batch apply audit rollback bridge",
            "question asset comparison repair queue batch apply transaction manifest bridge",
            "question asset comparison repair queue batch apply transaction manifest artifact bridge",
            "question asset comparison repair queue batch apply transaction manifest report bridge",
            "question asset comparison repair queue batch apply transaction task summary bridge",
            "question asset comparison repair queue batch apply transaction task issue-action bridge",
            "question asset comparison repair queue batch apply transaction task report-drilldown action bridge",
            "question asset comparison repair queue batch apply transaction task report-drilldown audit bridge",
            "question asset comparison repair queue frontstage apply bridge",
            "question asset comparison repair queue replacement audit bridge",
            "question asset comparison repair queue rollback bridge",
            "question asset comparison repair queue conflict guard bridge",
            "question asset comparison repair queue conflict resolution bridge",
            "question asset comparison repair queue conflict selection action bridge",
            "question asset figure group ordering bridge",
            "question asset flat figure group import bridge",
            "question asset filename mismatch preflight bridge",
            "question asset per-question asset library index UI bridge",
            "question asset per-question asset library metadata editing UI bridge",
            "question asset per-question asset library metadata issue UI bridge",
            "question asset per-question asset library version history UI bridge",
            "question asset per-question asset library version rollback UI bridge",
            "question asset per-question asset library local version consistency UI bridge",
            "question asset altText editing UI bridge",
            "question asset altText runtime/report",
            "plugin gate",
        ),
        (),
        (
            "Exam teaching keeps local question-asset runtime, cache, preview, "
            "comparison, repair audit, per-question library metadata/history, "
            "local version consistency, and altText evidence after enterprise "
            "remote governance removal."
        ),
    ),
    _family(
        "project_application",
        "green_l5",
        (
            "application limits",
            "attachment schema",
            "delivery preset",
            "journey runtime report",
            "artifact drilldown bridge",
            "external rule source governance",
            "submission system boundary UI",
            "application/report evidence UI",
        ),
        (),
        (
            "Project applications have local rule-source governance, attachment "
            "inventory, submission-system boundary reporting, journey/runtime "
            "reports, and artifact evidence while external platform status "
            "requires manual confirmation."
        ),
    ),
    _family(
        "contract_delivery",
        "green_l5",
        (
            "contract schema",
            "field consistency",
            "signing preset",
            "field evidence UI",
        ),
        (),
        (
            "Contract delivery family has schema, field consistency, signing "
            "preset, and frontstage field evidence without legal advice claims."
        ),
    ),
    _family(
        "hr_batch_documents",
        "green_l5",
        (
            "batch runtime",
            "personnel schema",
            "failure isolation",
            "profile-specific fixed-layout previews",
            "profile preview material manifest",
            "fixed-layout batch evidence UI",
        ),
        (),
        (
            "HR batch documents have personnel schema, profile-specific preview "
            "evidence, batch failure isolation, and report/UI evidence without "
            "claiming personnel qualification truthfulness."
        ),
    ),
    _family(
        "meeting_policy_documents",
        "green_l5",
        (
            "official defaults",
            "watermark status",
            "archive preset",
            "official metadata schema",
            "formal/internal/archive report depth",
        ),
        (),
        (
            "Meeting and policy documents keep the official sub-profile shape "
            "with metadata, delivery-status, and archive-manifest evidence; "
            "they do not become a separate top-level scene."
        ),
    ),
    _family(
        "product_sales_documents",
        "green_l5",
        (
            "router",
            "product asset schema",
            "customer/internal presets",
            "journey runtime report",
            "artifact drilldown bridge",
            "quote/body disambiguation fixtures",
            "asset consistency UI",
            "asset consistency report",
            "application/report evidence UI",
        ),
        (),
        (
            "Product/sales documents have asset schema, customer/internal "
            "delivery presets, quote/body disambiguation fixtures, asset "
            "consistency reporting, and UI evidence without claiming marketing "
            "or technical truthfulness."
        ),
    ),
    _family(
        "long_document_publishing",
        "green_l5",
        (
            "chapter inventory",
            "delivery presets",
            "object safety",
            "index/appendix handling",
            "multi-file import boundary",
        ),
        (),
        (
            "Long-document publishing has index/appendix inventory and "
            "multi-file import boundary evidence without claiming to replace "
            "publisher layout or merge systems."
        ),
    ),
    _family(
        "form_batch_documents",
        "green_l5",
        (
            "fixed row height",
            "content controls",
            "placeholder residue",
            "batch reports",
            "profile browser",
            "answer-sheet reuse path",
            "fixed-layout profile evidence UI",
            "fixed row-height policy material field",
        ),
        (),
        (
            "Fixed-layout form batch documents now connect OOXML/runtime row-height "
            "evidence, profile browsing, answer-sheet reuse, placeholder-residue "
            "reports, fixtures, and UI evidence without returning row height to "
            "generic table templates."
        ),
    ),
    _family(
        "qualification_archive_packages",
        "green_l5",
        (
            "qualification schema",
            "attachment package",
            "missing-items report",
            "expiry metadata governance",
            "multi-party archive depth",
        ),
        (),
        "Qualification archives have expiry and consortium archive evidence, but remain material packages rather than certificate authenticity checks.",
    ),
    _family(
        "finance_quote_documents",
        "blue_boundary",
        (
            "finance schema",
            "spreadsheet table mapping manifest",
            "finance boundary capability matrix",
            "plugin gate",
            "boundary report",
        ),
        ("finance plugin handoff",),
        (
            "Finance quote documents can track quote fields, workbooks, table "
            "mapping, and attachments, but finance assurance remains plugin/manual."
        ),
    ),
    _family(
        "ip_patent_documents",
        "blue_boundary",
        (
            "patent schema",
            "claim-quality boundary UI",
            "IP boundary capability matrix",
            "plugin gate",
            "review preset",
        ),
        ("IP plugin handoff",),
        (
            "Patent/IP support can inventory sections, figures, and claim "
            "placeholders, but claim quality and patentability remain external."
        ),
    ),
    _family(
        "bilingual_translation_documents",
        "blue_boundary",
        (
            "bilingual schema",
            "termbase UI",
            "bilingual boundary capability matrix",
            "plugin gate",
            "review preset",
        ),
        ("translation-quality plugin handoff",),
        (
            "Bilingual review can track termbase, layout, and unresolved terms, "
            "but translation quality remains plugin/manual review."
        ),
    ),
    _family(
        "regulated_disclosure_documents",
        "blue_boundary",
        (
            "disclosure schema",
            "regulated rule source governance",
            "assurance boundary UI",
            "regulated disclosure boundary capability matrix",
            "archive preset",
            "plugin gate",
        ),
        ("external assurance review handoff",),
        (
            "Disclosure support can track rule sources, sections, tables, and "
            "archive packages, but audit/assurance review remains external."
        ),
    ),
)


SCENE_PRODUCT_READINESS_MAP: dict[tuple[str, str], SceneProductReadinessSpec] = {
    (spec.subject_type, spec.subject_id): spec for spec in SCENE_PRODUCT_READINESS_SPECS
}


def list_scene_product_readiness_specs(
    subject_type: str | None = None,
) -> tuple[SceneProductReadinessSpec, ...]:
    if subject_type is None:
        return SCENE_PRODUCT_READINESS_SPECS
    normalized = str(subject_type or "").strip()
    return tuple(
        spec for spec in SCENE_PRODUCT_READINESS_SPECS if spec.subject_type == normalized
    )


def product_readiness_for(
    subject_id: str,
    *,
    subject_type: str = "pack",
) -> SceneProductReadinessSpec:
    key = (str(subject_type or "").strip(), str(subject_id or "").strip())
    try:
        return SCENE_PRODUCT_READINESS_MAP[key]
    except KeyError as exc:
        raise KeyError(f"Unknown scene product readiness subject: {key}") from exc


def audit_scene_product_readiness() -> tuple[SceneProductReadinessAuditResult, ...]:
    issues: list[SceneProductReadinessAuditResult] = []
    pack_spec_ids = {
        spec.subject_id
        for spec in SCENE_PRODUCT_READINESS_SPECS
        if spec.subject_type == "pack"
    }
    family_spec_ids = {
        spec.subject_id
        for spec in SCENE_PRODUCT_READINESS_SPECS
        if spec.subject_type == "family"
    }
    _append_missing(
        issues,
        "pack",
        "missing_pack_readiness",
        set(SCENE_COVERAGE_PACK_MAP),
        pack_spec_ids,
    )
    _append_missing(
        issues,
        "family",
        "missing_family_readiness",
        set(PLANNED_SCENE_FAMILY_MAP),
        family_spec_ids,
    )
    _append_missing(
        issues,
        "pack",
        "unknown_pack_readiness",
        pack_spec_ids,
        set(SCENE_COVERAGE_PACK_MAP),
    )
    _append_missing(
        issues,
        "family",
        "unknown_family_readiness",
        family_spec_ids,
        set(PLANNED_SCENE_FAMILY_MAP),
    )
    for spec in SCENE_PRODUCT_READINESS_SPECS:
        if spec.subject_type not in SCENE_READINESS_SUBJECT_TYPES:
            issues.append(
                _issue(
                    spec,
                    "invalid_subject_type",
                    ",".join(SCENE_READINESS_SUBJECT_TYPES),
                    spec.subject_type,
                )
            )
        if spec.static_closure_level not in STATIC_CLOSURE_LEVELS:
            issues.append(
                _issue(
                    spec,
                    "invalid_static_closure_level",
                    ",".join(STATIC_CLOSURE_LEVELS),
                    spec.static_closure_level,
                )
            )
        if spec.product_readiness_level not in PRODUCT_READINESS_LEVELS:
            issues.append(
                _issue(
                    spec,
                    "invalid_product_readiness_level",
                    ",".join(PRODUCT_READINESS_LEVELS),
                    spec.product_readiness_level,
                )
            )
        if not spec.evidence_surfaces:
            issues.append(_issue(spec, "missing_evidence_surfaces"))
        if spec.is_green and spec.remaining_product_gaps:
            issues.append(
                _issue(
                    spec,
                    "green_l5_with_remaining_gaps",
                    "no remaining gaps",
                    "; ".join(spec.remaining_product_gaps),
                )
            )
        if spec.is_boundary and "plugin gate" not in {
            surface.casefold() for surface in spec.evidence_surfaces
        }:
            issues.append(_issue(spec, "boundary_without_plugin_gate_evidence"))
    return tuple(issues)


def readiness_summary(spec: SceneProductReadinessSpec) -> str:
    gaps = len(spec.remaining_product_gaps)
    return (
        f"{spec.subject_type}:{spec.subject_id} "
        f"static={spec.static_closure_level}; "
        f"readiness={spec.product_readiness_level}; "
        f"evidence={len(spec.evidence_surfaces)}; gaps={gaps}"
    )


def static_closed_but_not_green_specs() -> tuple[SceneProductReadinessSpec, ...]:
    return tuple(
        spec
        for spec in SCENE_PRODUCT_READINESS_SPECS
        if spec.static_closure_level == "closed" and not spec.is_green
    )


def _append_missing(
    issues: list[SceneProductReadinessAuditResult],
    subject_type: str,
    issue: str,
    expected_ids: set[str],
    actual_ids: set[str],
) -> None:
    missing = tuple(sorted(expected_ids - actual_ids))
    if not missing:
        return
    issues.append(
        SceneProductReadinessAuditResult(
            subject_type=subject_type,
            subject_id=",".join(missing),
            issue=issue,
            expected=",".join(sorted(expected_ids)),
            actual=",".join(sorted(actual_ids)),
        )
    )


def _issue(
    spec: SceneProductReadinessSpec,
    issue: str,
    expected: str = "",
    actual: str = "",
) -> SceneProductReadinessAuditResult:
    return SceneProductReadinessAuditResult(
        subject_type=spec.subject_type,
        subject_id=spec.subject_id,
        issue=issue,
        expected=expected,
        actual=actual,
    )


__all__ = [
    "PRODUCT_READINESS_LEVELS",
    "SCENE_PRODUCT_READINESS_MAP",
    "SCENE_PRODUCT_READINESS_SPECS",
    "SCENE_READINESS_SUBJECT_TYPES",
    "STATIC_CLOSURE_LEVELS",
    "SceneProductReadinessAuditResult",
    "SceneProductReadinessSpec",
    "audit_scene_product_readiness",
    "list_scene_product_readiness_specs",
    "product_readiness_for",
    "readiness_summary",
    "static_closed_but_not_green_specs",
]
