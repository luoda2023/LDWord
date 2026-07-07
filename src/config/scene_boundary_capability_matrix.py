"""Boundary capability matrix for professional and import/AI scene families."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.material_schema_registry import get_material_schema
from src.config.plugin_manual_gate import list_plugin_manual_gates
from src.config.scene_coverage_manifest import SCENE_COVERAGE_PACK_MAP
from src.config.scene_family_registry import PLANNED_SCENE_FAMILY_MAP
from src.config.scene_high_frequency_request_samples import (
    list_high_frequency_request_samples,
)
from src.config.scene_product_readiness import list_scene_product_readiness_specs
from src.config.scene_sample_fixture_registry import SCENE_SAMPLE_FIXTURE_MAP


SCENE_BOUNDARY_CAPABILITY_MATRIX_ID = "scene_boundary_capability_matrix"

SCENE_BOUNDARY_CAPABILITY_REQUIRED_DECISION_IDS: tuple[str, ...] = (
    "manual_decision_required",
    "external_status_recorded",
    "fallback_report_required",
    "excluded_core_claims_visible",
)

SCENE_BOUNDARY_CAPABILITY_REQUIRED_GUARDRAIL_IDS: tuple[str, ...] = (
    "remain_blue_boundary",
    "no_core_professional_or_conversion_claim",
    "manual_or_plugin_receipt_required",
    "release_allowed_not_green",
)

SCENE_BOUNDARY_CAPABILITY_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "boundary_matrix_registry",
        "src/config/scene_boundary_capability_matrix.py",
        (
            "SCENE_BOUNDARY_CAPABILITY_SPECS",
            "professional_boundary_matrix",
            "confidence_artifact_manifest",
            "risk_domain_ids",
            "decision_requirement_ids",
            "external_receipt_ids",
            "release_guardrail_ids",
        ),
    ),
    (
        "scene_summary_projection",
        "src/ui/panels/scene_summary_projection.py",
        (
            "build_boundary_capability_evidence_summary_items",
            "boundary_capability_evidence",
            "professional_boundary_matrix",
            "external_receipt_ids",
            "release_guardrail_ids",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_BOUNDARY_CAPABILITY_MATRIX_ID,
            "scene_boundary_capability_ready_count",
            "scene_boundary_capability_external_receipt_count",
        ),
    ),
    (
        "n2_378_plan",
        "docs/audits/高层场景能力矩阵N2_378边界能力矩阵证据闭环_2026-06-24.md",
        (
            "N2.378",
            "边界能力矩阵",
            "professional_boundary_matrix",
            "confidence_artifact_manifest",
        ),
    ),
    (
        "n2_396_boundary_governance_trace",
        "docs/audits/scene_boundary_capability_matrix_governance_trace_N2_396_2026-06-25.md",
        (
            "N2.396",
            "boundary_decision_requirements=6/6",
            "external_receipt_targets=6/6",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneBoundaryCapabilitySpec:
    capability_id: str
    label: str
    subject_type: str
    subject_id: str
    pack_id: str
    family_id: str = ""
    boundary_group: str = ""
    plugin_gate_id: str = ""
    high_frequency_sample_ids: tuple[str, ...] = ()
    material_schema_ids: tuple[str, ...] = ()
    fixture_ids: tuple[str, ...] = ()
    report_expectation_ids: tuple[str, ...] = ()
    ui_surface_ids: tuple[str, ...] = ()
    risk_domain_ids: tuple[str, ...] = ()
    decision_requirement_ids: tuple[
        str, ...
    ] = SCENE_BOUNDARY_CAPABILITY_REQUIRED_DECISION_IDS
    external_receipt_ids: tuple[str, ...] = ()
    release_guardrail_ids: tuple[
        str, ...
    ] = SCENE_BOUNDARY_CAPABILITY_REQUIRED_GUARDRAIL_IDS
    core_scope: tuple[str, ...] = ()
    excluded_scope: tuple[str, ...] = ()
    handoff_target_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SceneBoundaryCapabilityIssue:
    scope_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "scope_id": self.scope_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneBoundaryCapabilitySourceEvidence:
    source_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneBoundaryCapabilityRow:
    capability_id: str
    label: str
    subject_type: str
    subject_id: str
    pack_id: str
    family_id: str
    boundary_group: str
    readiness_level: str
    plugin_gate_id: str
    high_frequency_sample_ids: tuple[str, ...]
    material_schema_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    report_expectation_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    risk_domain_ids: tuple[str, ...]
    decision_requirement_ids: tuple[str, ...]
    external_receipt_ids: tuple[str, ...]
    release_guardrail_ids: tuple[str, ...]
    core_scope: tuple[str, ...]
    excluded_scope: tuple[str, ...]
    handoff_target_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "label": self.label,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "pack_id": self.pack_id,
            "family_id": self.family_id,
            "boundary_group": self.boundary_group,
            "readiness_level": self.readiness_level,
            "plugin_gate_id": self.plugin_gate_id,
            "high_frequency_sample_ids": list(self.high_frequency_sample_ids),
            "material_schema_ids": list(self.material_schema_ids),
            "fixture_ids": list(self.fixture_ids),
            "report_expectation_ids": list(self.report_expectation_ids),
            "ui_surface_ids": list(self.ui_surface_ids),
            "risk_domain_ids": list(self.risk_domain_ids),
            "decision_requirement_ids": list(self.decision_requirement_ids),
            "external_receipt_ids": list(self.external_receipt_ids),
            "release_guardrail_ids": list(self.release_guardrail_ids),
            "core_scope": list(self.core_scope),
            "excluded_scope": list(self.excluded_scope),
            "handoff_target_ids": list(self.handoff_target_ids),
            "issue_ids": list(self.issue_ids),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneBoundaryCapabilityAuditReport:
    rows: tuple[SceneBoundaryCapabilityRow, ...]
    issues: tuple[SceneBoundaryCapabilityIssue, ...]
    source_evidence: tuple[SceneBoundaryCapabilitySourceEvidence, ...]
    boundary_group_filter: str = ""
    subject_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def capability_count(self) -> int:
        return len(self.rows)

    @property
    def ready_capability_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def professional_capability_count(self) -> int:
        return sum(1 for row in self.rows if row.boundary_group == "professional")

    @property
    def import_ai_capability_count(self) -> int:
        return sum(1 for row in self.rows if row.boundary_group == "import_ai")

    @property
    def fixture_count(self) -> int:
        return len({fixture_id for row in self.rows for fixture_id in row.fixture_ids})

    @property
    def report_expectation_count(self) -> int:
        return len(
            {
                report_id
                for row in self.rows
                for report_id in row.report_expectation_ids
            }
        )

    @property
    def ui_surface_count(self) -> int:
        return len({surface_id for row in self.rows for surface_id in row.ui_surface_ids})

    @property
    def risk_domain_count(self) -> int:
        return len({domain for row in self.rows for domain in row.risk_domain_ids})

    @property
    def decision_requirement_count(self) -> int:
        return len(
            {
                requirement
                for row in self.rows
                for requirement in row.decision_requirement_ids
            }
        )

    @property
    def external_receipt_count(self) -> int:
        return len({receipt for row in self.rows for receipt in row.external_receipt_ids})

    @property
    def release_guardrail_count(self) -> int:
        return len(
            {
                guardrail
                for row in self.rows
                for guardrail in row.release_guardrail_ids
            }
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_BOUNDARY_CAPABILITY_MATRIX_ID,
            "boundary_group_filter": self.boundary_group_filter,
            "subject_filter": self.subject_filter,
            "counts": {
                "capability_count": self.capability_count,
                "ready_capability_count": self.ready_capability_count,
                "professional_capability_count": self.professional_capability_count,
                "import_ai_capability_count": self.import_ai_capability_count,
                "fixture_count": self.fixture_count,
                "report_expectation_count": self.report_expectation_count,
                "ui_surface_count": self.ui_surface_count,
                "risk_domain_count": self.risk_domain_count,
                "decision_requirement_count": self.decision_requirement_count,
                "external_receipt_count": self.external_receipt_count,
                "release_guardrail_count": self.release_guardrail_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [evidence.to_payload() for evidence in self.source_evidence],
        }


SCENE_BOUNDARY_CAPABILITY_SPECS: tuple[SceneBoundaryCapabilitySpec, ...] = (
    SceneBoundaryCapabilitySpec(
        capability_id="professional_disclosure_boundary_matrix",
        label="Professional disclosure boundary matrix",
        subject_type="pack",
        subject_id="professional_disclosure",
        pack_id="professional_disclosure",
        boundary_group="professional",
        plugin_gate_id="professional_disclosure_review_gate",
        high_frequency_sample_ids=(
            "professional_finance_quote",
            "professional_esg_archive",
            "professional_patent_claims",
            "professional_bilingual_terms",
            "professional_legal_opinion",
            "professional_medical_regulatory",
        ),
        fixture_ids=(
            "professional_disclosure_manual_boundary",
            "professional_disclosure_source_quality_degraded",
            "professional_disclosure_finance_table_mapping_boundary",
            "professional_disclosure_patent_claim_quality_boundary",
            "professional_disclosure_bilingual_termbase_boundary",
            "professional_disclosure_regulated_assurance_boundary",
        ),
        report_expectation_ids=(
            "professional_boundary_matrix",
            "plugin_manual_gate",
            "professional_source_quality_report",
        ),
        ui_surface_ids=("boundary_capability_evidence", "professional_boundary_matrix"),
        risk_domain_ids=(
            "audit_assurance",
            "legal_opinion",
            "financial_assurance",
            "ip_patent_quality",
            "medical_regulatory",
            "translation_quality",
        ),
        external_receipt_ids=(
            "reviewed_plugin_receipt_contract",
            "external_review_result_ingestion",
        ),
        core_scope=(
            "route professional disclosure requests to explicit review gates",
            "show family-level evidence reports before plugin/manual judgment",
        ),
        excluded_scope=(
            "audit, legal, finance, patent, medical, or translation judgment",
            "silent core execution without professional confirmation",
        ),
    ),
    SceneBoundaryCapabilitySpec(
        capability_id="import_ai_boundary_confidence_matrix",
        label="Import, OCR, PDF, LaTeX, and AI confidence boundary",
        subject_type="pack",
        subject_id="import_ai_boundary",
        pack_id="import_ai_boundary",
        boundary_group="import_ai",
        plugin_gate_id="import_ai_conversion_gate",
        high_frequency_sample_ids=(
            "import_pdf_thesis",
            "import_ocr_pdf",
            "import_latex_project",
            "import_ai_diagrams",
        ),
        fixture_ids=(
            "import_ai_boundary_blocking_macro",
            "import_ai_boundary_conversion_confidence_degraded",
            "import_ai_boundary_latex_handoff_confidence",
        ),
        report_expectation_ids=(
            "conversion_confidence_report",
            "confidence_artifact_manifest",
            "ocr_pdf_latex_plugin_boundary",
            "import_handoff",
        ),
        ui_surface_ids=("boundary_capability_evidence", "confidence_artifact_manifest"),
        risk_domain_ids=("ocr_confidence", "pdf_conversion", "full_latex_conversion"),
        external_receipt_ids=(
            "conversion_confidence_receipts",
            "loss_review_artifact_roundtrip",
        ),
        core_scope=(
            "surface conversion confidence and blocking object risks",
            "handoff to target Word scenes only after manual confirmation",
        ),
        excluded_scope=(
            "lossless PDF/OCR/LaTeX conversion guarantee",
            "AI content correctness or complex diagram generation quality",
        ),
        handoff_target_ids=("chinese_academic", "thesis_cn"),
    ),
    SceneBoundaryCapabilitySpec(
        capability_id="finance_quote_boundary_depth",
        label="Finance quote spreadsheet and attachment boundary",
        subject_type="family",
        subject_id="finance_quote_documents",
        pack_id="professional_disclosure",
        family_id="finance_quote_documents",
        boundary_group="professional",
        plugin_gate_id="professional_disclosure_review_gate",
        high_frequency_sample_ids=("professional_finance_quote",),
        material_schema_ids=("finance_quote_fields_v1",),
        fixture_ids=(
            "professional_disclosure_source_quality_degraded",
            "professional_disclosure_finance_table_mapping_boundary",
        ),
        report_expectation_ids=(
            "finance_spreadsheet_mapping_report",
            "finance_plugin_handoff",
            "attachment_inventory",
            "professional_boundary_matrix",
        ),
        ui_surface_ids=("boundary_capability_evidence", "finance_spreadsheet_mapping_report"),
        risk_domain_ids=("financial_assurance",),
        external_receipt_ids=("quote_source_reconciliation_receipt",),
        core_scope=(
            "track quote fields, source workbook id, table mapping, and attachments",
            "prepare finance handoff evidence",
        ),
        excluded_scope=("financial audit judgment", "quotation correctness verification"),
    ),
    SceneBoundaryCapabilitySpec(
        capability_id="ip_patent_boundary_depth",
        label="Patent claim and figure boundary",
        subject_type="family",
        subject_id="ip_patent_documents",
        pack_id="professional_disclosure",
        family_id="ip_patent_documents",
        boundary_group="professional",
        plugin_gate_id="professional_disclosure_review_gate",
        high_frequency_sample_ids=("professional_patent_claims",),
        material_schema_ids=("patent_document_fields_v1",),
        fixture_ids=("professional_disclosure_patent_claim_quality_boundary",),
        report_expectation_ids=(
            "patent_claim_boundary_report",
            "claim_quality_boundary_ui",
            "ip_plugin_handoff",
            "professional_boundary_matrix",
        ),
        ui_surface_ids=("boundary_capability_evidence", "claim_quality_boundary_ui"),
        risk_domain_ids=("ip_patent_quality", "legal_opinion"),
        external_receipt_ids=("claim_quality_review_receipt",),
        core_scope=(
            "inventory patent sections, figures, terms, and review-copy handoff",
            "make claim-quality boundary visible before professional review",
        ),
        excluded_scope=("patentability judgment", "infringement or claim validity review"),
    ),
    SceneBoundaryCapabilitySpec(
        capability_id="bilingual_translation_boundary_depth",
        label="Bilingual termbase and translation-quality boundary",
        subject_type="family",
        subject_id="bilingual_translation_documents",
        pack_id="professional_disclosure",
        family_id="bilingual_translation_documents",
        boundary_group="professional",
        plugin_gate_id="professional_disclosure_review_gate",
        high_frequency_sample_ids=("professional_bilingual_terms",),
        material_schema_ids=("bilingual_terms_v1",),
        fixture_ids=("professional_disclosure_bilingual_termbase_boundary",),
        report_expectation_ids=(
            "bilingual_termbase_report",
            "termbase_ui",
            "translation_quality_plugin_handoff",
            "professional_boundary_matrix",
        ),
        ui_surface_ids=("boundary_capability_evidence", "termbase_ui"),
        risk_domain_ids=("translation_quality",),
        external_receipt_ids=("termbase_review_receipt",),
        core_scope=(
            "track language pair, termbase manifest, unresolved terms, and parallel layout",
            "prepare translation-quality handoff evidence",
        ),
        excluded_scope=("translation quality guarantee", "silent bilingual meaning rewrite"),
    ),
    SceneBoundaryCapabilitySpec(
        capability_id="regulated_disclosure_boundary_depth",
        label="Regulated disclosure rule-source and assurance boundary",
        subject_type="family",
        subject_id="regulated_disclosure_documents",
        pack_id="professional_disclosure",
        family_id="regulated_disclosure_documents",
        boundary_group="professional",
        plugin_gate_id="professional_disclosure_review_gate",
        high_frequency_sample_ids=("professional_esg_archive",),
        material_schema_ids=("regulated_disclosure_materials_v1",),
        fixture_ids=(
            "professional_disclosure_manual_boundary",
            "professional_disclosure_regulated_assurance_boundary",
        ),
        report_expectation_ids=(
            "regulated_rule_source_governance",
            "assurance_boundary_ui",
            "disclosure_archive_manifest",
            "professional_boundary_matrix",
        ),
        ui_surface_ids=("boundary_capability_evidence", "assurance_boundary_ui"),
        risk_domain_ids=("audit_assurance",),
        external_receipt_ids=("assurance_receipt_archive",),
        core_scope=(
            "track disclosure period, rule source, section inventory, tables, and archive package",
            "make audit/assurance boundary visible before professional review",
        ),
        excluded_scope=("audit assurance", "regulated filing completeness decision"),
    ),
)


def list_scene_boundary_capabilities(
    *, boundary_group: str = "", subject_id: str = ""
) -> tuple[SceneBoundaryCapabilitySpec, ...]:
    normalized_group = str(boundary_group or "").strip()
    normalized_subject = str(subject_id or "").strip()
    return tuple(
        spec
        for spec in SCENE_BOUNDARY_CAPABILITY_SPECS
        if (not normalized_group or spec.boundary_group == normalized_group)
        and (not normalized_subject or spec.subject_id == normalized_subject)
    )


def build_scene_boundary_capability_audit_report(
    *,
    boundary_group: str = "",
    subject_id: str = "",
    project_root: Path | str | None = None,
) -> SceneBoundaryCapabilityAuditReport:
    specs = list_scene_boundary_capabilities(
        boundary_group=boundary_group,
        subject_id=subject_id,
    )
    rows: list[SceneBoundaryCapabilityRow] = []
    issues: list[SceneBoundaryCapabilityIssue] = []
    readiness = {
        (spec.subject_type, spec.subject_id): spec
        for spec in list_scene_product_readiness_specs()
    }
    for spec in specs:
        row, row_issues = _build_row(spec, readiness)
        rows.append(row)
        issues.extend(row_issues)
    issues.extend(_coverage_issues(tuple(rows)))
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneBoundaryCapabilityAuditReport(
        rows=tuple(rows),
        issues=tuple(issues),
        source_evidence=source_evidence,
        boundary_group_filter=str(boundary_group or "").strip(),
        subject_filter=str(subject_id or "").strip(),
    )


def audit_scene_boundary_capability_report(
    report: SceneBoundaryCapabilityAuditReport | None = None,
) -> tuple[SceneBoundaryCapabilityIssue, ...]:
    current = report or build_scene_boundary_capability_audit_report()
    return current.issues


def _build_row(
    spec: SceneBoundaryCapabilitySpec,
    readiness: dict[tuple[str, str], object],
) -> tuple[SceneBoundaryCapabilityRow, tuple[SceneBoundaryCapabilityIssue, ...]]:
    readiness_spec = readiness.get((spec.subject_type, spec.subject_id))
    readiness_level = str(
        getattr(readiness_spec, "product_readiness_level", "") or ""
    )
    issues = _row_issues(spec, readiness_level)
    row = SceneBoundaryCapabilityRow(
        capability_id=spec.capability_id,
        label=spec.label,
        subject_type=spec.subject_type,
        subject_id=spec.subject_id,
        pack_id=spec.pack_id,
        family_id=spec.family_id,
        boundary_group=spec.boundary_group,
        readiness_level=readiness_level,
        plugin_gate_id=spec.plugin_gate_id,
        high_frequency_sample_ids=spec.high_frequency_sample_ids,
        material_schema_ids=spec.material_schema_ids,
        fixture_ids=spec.fixture_ids,
        report_expectation_ids=spec.report_expectation_ids,
        ui_surface_ids=spec.ui_surface_ids,
        risk_domain_ids=spec.risk_domain_ids,
        decision_requirement_ids=spec.decision_requirement_ids,
        external_receipt_ids=spec.external_receipt_ids,
        release_guardrail_ids=spec.release_guardrail_ids,
        core_scope=spec.core_scope,
        excluded_scope=spec.excluded_scope,
        handoff_target_ids=spec.handoff_target_ids,
        issue_ids=tuple(issue.kind for issue in issues),
    )
    return row, tuple(issues)


def _row_issues(
    spec: SceneBoundaryCapabilitySpec,
    readiness_level: str,
) -> tuple[SceneBoundaryCapabilityIssue, ...]:
    issues: list[SceneBoundaryCapabilityIssue] = []

    def add(kind: str, message: str) -> None:
        issues.append(SceneBoundaryCapabilityIssue(spec.capability_id, kind, message))

    if spec.pack_id not in SCENE_COVERAGE_PACK_MAP:
        add("unknown_pack", f"Unknown coverage pack: {spec.pack_id}.")
    if spec.family_id and spec.family_id not in PLANNED_SCENE_FAMILY_MAP:
        add("unknown_family", f"Unknown planned family: {spec.family_id}.")
    if readiness_level != "blue_boundary":
        add(
            "boundary_subject_not_blue",
            "Boundary capability subjects must remain Blue/Boundary until the external judgment/integration is real.",
        )
    gate_ids = {gate.gate_id for gate in list_plugin_manual_gates()}
    if spec.plugin_gate_id not in gate_ids:
        add("unknown_plugin_gate", f"Unknown plugin/manual gate: {spec.plugin_gate_id}.")
    sample_map = {sample.sample_id: sample for sample in list_high_frequency_request_samples()}
    for sample_id in spec.high_frequency_sample_ids:
        sample = sample_map.get(sample_id)
        if sample is None:
            add("unknown_request_sample", f"Unknown high-frequency sample: {sample_id}.")
            continue
        if spec.pack_id not in sample.expected_pack_ids:
            add(
                "request_sample_pack_mismatch",
                f"{sample_id} does not target pack {spec.pack_id}.",
            )
        if spec.family_id and spec.family_id not in sample.expected_family_ids:
            add(
                "request_sample_family_mismatch",
                f"{sample_id} does not target family {spec.family_id}.",
            )
        if spec.plugin_gate_id not in sample.expected_plugin_gate_ids:
            add(
                "request_sample_gate_mismatch",
                f"{sample_id} does not expose gate {spec.plugin_gate_id}.",
            )
    for schema_id in spec.material_schema_ids:
        try:
            schema = get_material_schema(schema_id)
        except KeyError:
            add("unknown_material_schema", f"Unknown material schema: {schema_id}.")
            continue
        if spec.family_id and schema.family != spec.family_id:
            add(
                "material_schema_family_mismatch",
                f"{schema_id} belongs to {schema.family}, not {spec.family_id}.",
            )
    fixture_report_ids: set[str] = set()
    for fixture_id in spec.fixture_ids:
        fixture = SCENE_SAMPLE_FIXTURE_MAP.get(fixture_id)
        if fixture is None:
            add("unknown_fixture", f"Unknown scene sample fixture: {fixture_id}.")
            continue
        if fixture.pack_id != spec.pack_id:
            add(
                "fixture_pack_mismatch",
                f"{fixture_id} belongs to {fixture.pack_id}, not {spec.pack_id}.",
            )
        if spec.family_id and fixture.family_id != spec.family_id:
            add(
                "fixture_family_mismatch",
                f"{fixture_id} belongs to {fixture.family_id}, not {spec.family_id}.",
            )
        if fixture.manual_gate_id and fixture.manual_gate_id != spec.plugin_gate_id:
            add(
                "fixture_gate_mismatch",
                f"{fixture_id} exposes {fixture.manual_gate_id}, not {spec.plugin_gate_id}.",
            )
        fixture_report_ids.update(fixture.report_expectations)
    missing_report_ids = tuple(
        report_id
        for report_id in spec.report_expectation_ids
        if report_id not in fixture_report_ids
    )
    if missing_report_ids:
        add(
            "missing_fixture_report_expectation",
            "Fixture evidence does not expose reports: " + ", ".join(missing_report_ids),
        )
    if not spec.ui_surface_ids:
        add("missing_ui_surface", "Boundary capability must declare UI summary surfaces.")
    if not spec.risk_domain_ids:
        add("missing_risk_domain", "Boundary capability must declare risk domains.")
    missing_decision_ids = tuple(
        decision_id
        for decision_id in SCENE_BOUNDARY_CAPABILITY_REQUIRED_DECISION_IDS
        if decision_id not in spec.decision_requirement_ids
    )
    if missing_decision_ids:
        add(
            "missing_decision_requirement",
            "Boundary capability is missing decision requirements: "
            + ", ".join(missing_decision_ids),
        )
    if not spec.external_receipt_ids:
        add(
            "missing_external_receipt_target",
            "Boundary capability must declare external receipt or exit-signal targets.",
        )
    missing_guardrail_ids = tuple(
        guardrail_id
        for guardrail_id in SCENE_BOUNDARY_CAPABILITY_REQUIRED_GUARDRAIL_IDS
        if guardrail_id not in spec.release_guardrail_ids
    )
    if missing_guardrail_ids:
        add(
            "missing_release_guardrail",
            "Boundary capability is missing release guardrails: "
            + ", ".join(missing_guardrail_ids),
        )
    if not spec.core_scope:
        add("missing_core_scope", "Boundary capability must declare core scope.")
    if not spec.excluded_scope:
        add("missing_excluded_scope", "Boundary capability must declare excluded scope.")
    return tuple(issues)


def _coverage_issues(
    rows: tuple[SceneBoundaryCapabilityRow, ...],
) -> tuple[SceneBoundaryCapabilityIssue, ...]:
    issues: list[SceneBoundaryCapabilityIssue] = []
    row_subjects = {(row.subject_type, row.subject_id) for row in rows}
    blue_subjects = {
        (spec.subject_type, spec.subject_id)
        for spec in list_scene_product_readiness_specs()
        if spec.product_readiness_level == "blue_boundary"
    }
    for subject_type, subject_id in sorted(blue_subjects - row_subjects):
        issues.append(
            SceneBoundaryCapabilityIssue(
                f"{subject_type}:{subject_id}",
                "blue_boundary_subject_missing",
                "Blue/Boundary product-readiness subject is missing from the boundary capability matrix.",
            )
        )
    p2_professional_families = {
        family_id
        for family_id, family in PLANNED_SCENE_FAMILY_MAP.items()
        if family.priority == "P2"
    }
    row_family_ids = {row.family_id for row in rows if row.family_id}
    for family_id in sorted(p2_professional_families - row_family_ids):
        issues.append(
            SceneBoundaryCapabilityIssue(
                family_id,
                "p2_family_missing",
                "P2 professional/boundary family is missing from the boundary capability matrix.",
            )
        )
    return tuple(issues)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneBoundaryCapabilitySourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneBoundaryCapabilitySourceEvidence] = []
    for source_id, source_path, markers in SCENE_BOUNDARY_CAPABILITY_SOURCE_MARKERS:
        path = Path(source_path)
        if not path.is_absolute():
            path = root / source_path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneBoundaryCapabilitySourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneBoundaryCapabilitySourceEvidence, ...],
) -> tuple[SceneBoundaryCapabilityIssue, ...]:
    return tuple(
        SceneBoundaryCapabilityIssue(
            evidence.source_id,
            "missing_source_evidence",
            (
                f"{evidence.source_path} missing markers: "
                f"{', '.join(evidence.missing_markers)}"
            ),
        )
        for evidence in source_evidence
        if evidence.missing_markers
    )


def _unique_values(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_BOUNDARY_CAPABILITY_MATRIX_ID",
    "SCENE_BOUNDARY_CAPABILITY_REQUIRED_DECISION_IDS",
    "SCENE_BOUNDARY_CAPABILITY_REQUIRED_GUARDRAIL_IDS",
    "SCENE_BOUNDARY_CAPABILITY_SPECS",
    "SceneBoundaryCapabilityAuditReport",
    "SceneBoundaryCapabilityIssue",
    "SceneBoundaryCapabilityRow",
    "SceneBoundaryCapabilitySpec",
    "audit_scene_boundary_capability_report",
    "build_scene_boundary_capability_audit_report",
    "list_scene_boundary_capabilities",
]
