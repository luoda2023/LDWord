"""Plugin/manual boundary confirmation audit for the scene matrix.

N2.160 makes high-risk plugin/manual boundaries explicit and testable.  The
core formatter can expose formatting, material, delivery, and reporting
workflows, but OCR/PDF/LaTeX/AI quality and professional judgments must stay
behind a confirmation gate with route, request-cell, fixture, report, and UI
evidence.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from src.config.plugin_manual_gate import (
    PluginManualGate,
    list_plugin_manual_gates,
)
from src.config.scene_coverage_manifest import (
    get_scene_coverage_pack,
    list_scene_coverage_packs,
)
from src.config.scene_high_frequency_request_samples import (
    list_high_frequency_request_samples,
)
from src.config.scene_natural_request_router import list_natural_request_routes
from src.config.scene_request_cell_fixture_registry import (
    list_scene_request_cell_fixtures,
)
from src.config.scene_sample_fixture_registry import list_scene_sample_fixtures


N2_160_REQUIRED_RISK_DOMAIN_IDS: tuple[str, ...] = (
    "publisher_final_layout",
    "unreviewed_journal_rules",
    "citation_source_integrity",
    "ocr_confidence",
    "pdf_conversion",
    "full_latex_conversion",
    "ai_content_quality",
    "complex_diagram_generation",
    "legal_opinion",
    "financial_assurance",
    "ip_patent_quality",
    "medical_regulatory",
    "translation_quality",
    "audit_assurance",
)

N2_160_REQUIRED_DECISION_STATES: tuple[str, ...] = (
    "accepted",
    "rejected",
    "needs_plugin_handoff",
)

N2_160_REQUIRED_GATE_PACK_IDS: tuple[str, ...] = (
    "english_journal",
    "exam_education",
    "professional_disclosure",
    "import_ai_boundary",
)

N2_160_CONFIDENCE_RISK_DOMAIN_IDS: tuple[str, ...] = (
    "ocr_confidence",
    "pdf_conversion",
    "full_latex_conversion",
    "ai_content_quality",
    "complex_diagram_generation",
)

N2_160_PROFESSIONAL_RISK_DOMAIN_IDS: tuple[str, ...] = (
    "legal_opinion",
    "financial_assurance",
    "ip_patent_quality",
    "medical_regulatory",
    "translation_quality",
    "audit_assurance",
)

N2_160_ROUTE_RISK_DOMAIN_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "english_journal_submission": (
        "publisher_final_layout",
        "unreviewed_journal_rules",
        "citation_source_integrity",
    ),
    "exam_teaching_versions": (
        "ai_content_quality",
        "complex_diagram_generation",
    ),
    "finance_quote_documents": ("financial_assurance",),
    "regulated_disclosure_documents": ("audit_assurance",),
    "ip_patent_manual_boundary": ("ip_patent_quality", "legal_opinion"),
    "legal_document_manual_boundary": ("legal_opinion",),
    "medical_regulatory_manual_boundary": ("medical_regulatory",),
    "bilingual_review_documents": ("translation_quality",),
    "import_pdf_thesis_boundary": ("pdf_conversion",),
    "import_ai_conversion_boundary": (
        "ocr_confidence",
        "pdf_conversion",
        "full_latex_conversion",
        "ai_content_quality",
        "complex_diagram_generation",
    ),
}

N2_160_SAMPLE_RISK_DOMAIN_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "english_journal_response_letter": (
        "publisher_final_layout",
        "unreviewed_journal_rules",
        "citation_source_integrity",
    ),
    "exam_multi_version": (
        "ai_content_quality",
        "complex_diagram_generation",
    ),
    "professional_finance_quote": ("financial_assurance",),
    "professional_esg_archive": ("audit_assurance",),
    "professional_patent_claims": ("ip_patent_quality", "legal_opinion"),
    "professional_bilingual_terms": ("translation_quality",),
    "professional_legal_opinion": ("legal_opinion",),
    "ambiguous_contract_legal_review": ("legal_opinion",),
    "professional_medical_regulatory": ("medical_regulatory",),
    "import_pdf_thesis": ("pdf_conversion",),
    "import_ocr_pdf": ("ocr_confidence", "pdf_conversion"),
    "import_latex_project": ("full_latex_conversion",),
    "import_ai_diagrams": (
        "ai_content_quality",
        "complex_diagram_generation",
    ),
}

N2_160_SOURCE_EVIDENCE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "pipeline_boundary_payload",
        "src/pipeline/runner.py",
        ("build_coverage_boundary_report_items", "plugin_manual_gate_payload"),
    ),
    (
        "report_writer_boundary",
        "src/reporting/material_sections.py",
        ("_format_coverage_boundaries_markdown", "Risk domains:", "Decision states:"),
    ),
    (
        "workbench_boundary_issue",
        "src/ui/adapters/workbench_boundary_issues.py",
        ("coverage_boundary_issue_items", "风险域：", "确认状态："),
    ),
    (
        "dashboard_boundary_filter",
        "src/config/scene_matrix_dashboard.py",
        ("boundary_signal_ids", "boundary_readiness", "plugin_manual_workflow"),
    ),
    (
        "request_cell_manual_gate",
        "src/config/scene_request_cell_fixture_registry.py",
        ("missing_manual_gate_fixture", "manual_boundary_fixture"),
    ),
)


@dataclass(frozen=True, slots=True)
class ScenePluginBoundaryConfirmationIssue:
    gate_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class ScenePluginBoundarySourceEvidence:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class ScenePluginBoundaryConfirmationRow:
    gate_id: str
    pack_id: str
    label: str
    plugin_entry_id: str
    risk_domain_ids: tuple[str, ...]
    manual_confirmation_required: bool
    confidence_report_required: bool
    boundary_report_required: bool
    blocks_core_execution_until_confirmed: bool
    professional_review_required: bool
    confirmation_decision_states: tuple[str, ...]
    accepted_inputs: tuple[str, ...]
    unsupported_core_inputs: tuple[str, ...]
    confirmation_scope: tuple[str, ...]
    report_fields: tuple[str, ...]
    route_ids: tuple[str, ...]
    request_sample_ids: tuple[str, ...]
    request_cell_sample_ids: tuple[str, ...]
    manual_fixture_ids: tuple[str, ...]
    route_required_risk_domain_ids: tuple[str, ...]
    sample_required_risk_domain_ids: tuple[str, ...]
    coverage_pack_plugin_boundary: bool
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "pack_id": self.pack_id,
            "label": self.label,
            "status": self.status,
            "plugin_entry_id": self.plugin_entry_id,
            "risk_domain_ids": list(self.risk_domain_ids),
            "manual_confirmation_required": self.manual_confirmation_required,
            "confidence_report_required": self.confidence_report_required,
            "boundary_report_required": self.boundary_report_required,
            "blocks_core_execution_until_confirmed": (
                self.blocks_core_execution_until_confirmed
            ),
            "professional_review_required": self.professional_review_required,
            "confirmation_decision_states": list(
                self.confirmation_decision_states
            ),
            "accepted_inputs": list(self.accepted_inputs),
            "unsupported_core_inputs": list(self.unsupported_core_inputs),
            "confirmation_scope": list(self.confirmation_scope),
            "report_fields": list(self.report_fields),
            "route_ids": list(self.route_ids),
            "request_sample_ids": list(self.request_sample_ids),
            "request_cell_sample_ids": list(self.request_cell_sample_ids),
            "manual_fixture_ids": list(self.manual_fixture_ids),
            "route_required_risk_domain_ids": list(
                self.route_required_risk_domain_ids
            ),
            "sample_required_risk_domain_ids": list(
                self.sample_required_risk_domain_ids
            ),
            "coverage_pack_plugin_boundary": self.coverage_pack_plugin_boundary,
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class ScenePluginBoundaryConfirmationAuditReport:
    rows: tuple[ScenePluginBoundaryConfirmationRow, ...]
    issues: tuple[ScenePluginBoundaryConfirmationIssue, ...]
    source_evidence: tuple[ScenePluginBoundarySourceEvidence, ...]
    gate_filter: str = ""
    risk_domain_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def gate_count(self) -> int:
        return len(self.rows)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def risk_domain_count(self) -> int:
        return len(_unique_values(domain for row in self.rows for domain in row.risk_domain_ids))

    @property
    def route_count(self) -> int:
        return len(_unique_values(route_id for row in self.rows for route_id in row.route_ids))

    @property
    def request_sample_count(self) -> int:
        return len(
            _unique_values(
                sample_id for row in self.rows for sample_id in row.request_sample_ids
            )
        )

    @property
    def manual_fixture_count(self) -> int:
        return len(
            _unique_values(
                fixture_id for row in self.rows for fixture_id in row.manual_fixture_ids
            )
        )

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "gate_filter": self.gate_filter,
            "risk_domain_filter": self.risk_domain_filter,
            "gate_count": self.gate_count,
            "issue_count": self.issue_count,
            "risk_domain_count": self.risk_domain_count,
            "route_count": self.route_count,
            "request_sample_count": self.request_sample_count,
            "manual_fixture_count": self.manual_fixture_count,
            "missing_source_evidence_count": self.missing_source_evidence_count,
            "required_risk_domain_ids": list(N2_160_REQUIRED_RISK_DOMAIN_IDS),
            "required_decision_states": list(N2_160_REQUIRED_DECISION_STATES),
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_plugin_boundary_confirmation_audit_report(
    *,
    gate_id: str = "",
    risk_domain_id: str = "",
    project_root: Path | None = None,
) -> ScenePluginBoundaryConfirmationAuditReport:
    root = project_root or Path(__file__).resolve().parents[2]
    normalized_gate = str(gate_id or "").strip()
    normalized_domain = str(risk_domain_id or "").strip()
    gates = tuple(
        gate
        for gate in list_plugin_manual_gates()
        if (not normalized_gate or gate.gate_id == normalized_gate)
        and (not normalized_domain or normalized_domain in gate.risk_domain_ids)
    )
    rows_with_issues: list[ScenePluginBoundaryConfirmationRow] = []
    issues: list[ScenePluginBoundaryConfirmationIssue] = []
    for row in tuple(_build_row(gate) for gate in gates):
        row_issues = _row_issues(row)
        issues.extend(row_issues)
        rows_with_issues.append(
            replace(
                row,
                issue_ids=tuple(issue.kind for issue in row_issues),
            )
        )
    rows = tuple(rows_with_issues)

    if normalized_gate and not rows:
        issues.append(
            ScenePluginBoundaryConfirmationIssue(
                gate_id=normalized_gate,
                kind="unknown_gate_filter",
                message=f"Unknown plugin/manual gate: {normalized_gate}",
            )
        )
    if normalized_domain and not rows:
        issues.append(
            ScenePluginBoundaryConfirmationIssue(
                gate_id="*",
                kind="unknown_risk_domain_filter",
                message=f"Unknown or unassigned risk domain: {normalized_domain}",
            )
        )

    if not normalized_gate and not normalized_domain:
        issues.extend(_global_issues(rows))

    source_evidence = _build_source_evidence(root)
    for evidence in source_evidence:
        if evidence.status != "ready":
            issues.append(
                ScenePluginBoundaryConfirmationIssue(
                    gate_id="*",
                    kind=f"missing_source_evidence.{evidence.evidence_id}",
                    message=(
                        f"{evidence.source_path} is missing markers: "
                        + ", ".join(evidence.missing_markers)
                    ),
                )
            )

    return ScenePluginBoundaryConfirmationAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
        gate_filter=normalized_gate,
        risk_domain_filter=normalized_domain,
    )


def audit_scene_plugin_boundary_confirmation_report(
    report: ScenePluginBoundaryConfirmationAuditReport | None = None,
) -> tuple[ScenePluginBoundaryConfirmationIssue, ...]:
    current = report or build_scene_plugin_boundary_confirmation_audit_report()
    return current.issues


def _build_row(gate: PluginManualGate) -> ScenePluginBoundaryConfirmationRow:
    routes = tuple(
        route
        for route in list_natural_request_routes()
        if route.plugin_gate_id == gate.gate_id
    )
    samples = tuple(
        sample
        for sample in list_high_frequency_request_samples()
        if gate.gate_id in sample.expected_plugin_gate_ids
    )
    cells = tuple(
        cell
        for cell in list_scene_request_cell_fixtures()
        if gate.gate_id in cell.expected_plugin_gate_ids
    )
    fixtures = tuple(
        fixture
        for fixture in list_scene_sample_fixtures()
        if fixture.manual_gate_id == gate.gate_id
    )
    try:
        pack = get_scene_coverage_pack(gate.pack_id)
        plugin_boundary = bool(pack.plugin_boundary)
    except KeyError:
        plugin_boundary = False

    return ScenePluginBoundaryConfirmationRow(
        gate_id=gate.gate_id,
        pack_id=gate.pack_id,
        label=gate.label,
        plugin_entry_id=gate.plugin_entry_id,
        risk_domain_ids=gate.risk_domain_ids,
        manual_confirmation_required=gate.manual_confirmation_required,
        confidence_report_required=gate.confidence_report_required,
        boundary_report_required=gate.boundary_report_required,
        blocks_core_execution_until_confirmed=(
            gate.blocks_core_execution_until_confirmed
        ),
        professional_review_required=gate.professional_review_required,
        confirmation_decision_states=gate.confirmation_decision_states,
        accepted_inputs=gate.accepted_inputs,
        unsupported_core_inputs=gate.unsupported_core_inputs,
        confirmation_scope=gate.confirmation_scope,
        report_fields=gate.report_fields,
        route_ids=tuple(route.route_id for route in routes),
        request_sample_ids=tuple(sample.sample_id for sample in samples),
        request_cell_sample_ids=tuple(cell.sample_id for cell in cells),
        manual_fixture_ids=tuple(fixture.fixture_id for fixture in fixtures),
        route_required_risk_domain_ids=_unique_values(
            domain
            for route in routes
            for domain in N2_160_ROUTE_RISK_DOMAIN_REQUIREMENTS.get(
                route.route_id,
                (),
            )
        ),
        sample_required_risk_domain_ids=_unique_values(
            domain
            for sample in samples
            for domain in N2_160_SAMPLE_RISK_DOMAIN_REQUIREMENTS.get(
                sample.sample_id,
                (),
            )
        ),
        coverage_pack_plugin_boundary=plugin_boundary,
        issue_ids=(),
    )


def _row_issues(
    row: ScenePluginBoundaryConfirmationRow,
) -> tuple[ScenePluginBoundaryConfirmationIssue, ...]:
    issues: list[ScenePluginBoundaryConfirmationIssue] = []

    def append(kind: str, message: str, severity: str = "error") -> None:
        issues.append(
            ScenePluginBoundaryConfirmationIssue(
                gate_id=row.gate_id,
                kind=kind,
                message=message,
                severity=severity,
            )
        )

    if not row.coverage_pack_plugin_boundary:
        append(
            "pack_not_plugin_boundary",
            "Plugin/manual gate must belong to a plugin-boundary coverage pack.",
        )
    if not row.manual_confirmation_required:
        append("manual_confirmation_not_required", "Manual confirmation must be required.")
    if not row.boundary_report_required:
        append("boundary_report_not_required", "Boundary report must be required.")
    if not row.blocks_core_execution_until_confirmed:
        append(
            "core_execution_not_blocked",
            "Core execution must stay blocked until the gate is confirmed.",
        )
    if not row.risk_domain_ids:
        append("missing_risk_domains", "Gate must declare at least one risk domain.")
    unknown_domains = tuple(
        domain
        for domain in row.risk_domain_ids
        if domain not in N2_160_REQUIRED_RISK_DOMAIN_IDS
    )
    if unknown_domains:
        append(
            "unknown_risk_domains",
            "Unknown risk domains: " + ", ".join(unknown_domains),
        )
    missing_decisions = tuple(
        state
        for state in N2_160_REQUIRED_DECISION_STATES
        if state not in row.confirmation_decision_states
    )
    if missing_decisions:
        append(
            "missing_decision_states",
            "Missing confirmation decision states: " + ", ".join(missing_decisions),
        )
    if not row.accepted_inputs:
        append("missing_accepted_inputs", "Gate must declare accepted input types.")
    if not row.unsupported_core_inputs:
        append(
            "missing_unsupported_core_inputs",
            "Gate must declare unsupported core inputs.",
        )
    if not row.confirmation_scope:
        append("missing_confirmation_scope", "Gate must describe confirmation scope.")
    if not row.report_fields:
        append("missing_report_fields", "Gate must declare report fields.")
    if "manual_decision" not in row.report_fields:
        append(
            "missing_manual_decision_report_field",
            "Report fields must include manual_decision.",
        )
    if not row.route_ids:
        append("missing_route_evidence", "Gate has no natural request route evidence.")
    if not row.request_sample_ids:
        append(
            "missing_request_sample_evidence",
            "Gate has no high-frequency request sample evidence.",
        )
    if not row.request_cell_sample_ids:
        append(
            "missing_request_cell_evidence",
            "Gate has no request-cell fixture evidence.",
        )
    if not row.manual_fixture_ids:
        append(
            "missing_manual_fixture_evidence",
            "Gate has no DOCX/manual-boundary fixture evidence.",
        )

    domain_set = set(row.risk_domain_ids)
    missing_route_domains = tuple(
        domain
        for domain in row.route_required_risk_domain_ids
        if domain not in domain_set
    )
    if missing_route_domains:
        append(
            "missing_route_risk_domains",
            "Gate is missing route-required risk domains: "
            + ", ".join(missing_route_domains),
        )
    missing_sample_domains = tuple(
        domain
        for domain in row.sample_required_risk_domain_ids
        if domain not in domain_set
    )
    if missing_sample_domains:
        append(
            "missing_sample_risk_domains",
            "Gate is missing sample-required risk domains: "
            + ", ".join(missing_sample_domains),
        )

    if domain_set & set(N2_160_CONFIDENCE_RISK_DOMAIN_IDS):
        if not row.confidence_report_required:
            append(
                "confidence_report_required",
                "AI/import/OCR/diagram risk domains require a confidence report.",
            )
    if domain_set & set(N2_160_PROFESSIONAL_RISK_DOMAIN_IDS):
        if not row.professional_review_required:
            append(
                "professional_review_required",
                "Professional risk domains require professional review metadata.",
            )
    return tuple(issues)


def _global_issues(
    rows: tuple[ScenePluginBoundaryConfirmationRow, ...],
) -> tuple[ScenePluginBoundaryConfirmationIssue, ...]:
    issues: list[ScenePluginBoundaryConfirmationIssue] = []
    row_pack_ids = {row.pack_id for row in rows}
    pack_map = {pack.pack_id: pack for pack in list_scene_coverage_packs()}
    for pack_id in N2_160_REQUIRED_GATE_PACK_IDS:
        pack = pack_map.get(pack_id)
        if pack is None:
            issues.append(
                ScenePluginBoundaryConfirmationIssue(
                    gate_id="*",
                    kind=f"missing_required_gate_pack.{pack_id}",
                    message=f"Required gate pack is not registered: {pack_id}",
                )
            )
            continue
        if not pack.plugin_boundary:
            issues.append(
                ScenePluginBoundaryConfirmationIssue(
                    gate_id="*",
                    kind=f"gate_pack_not_plugin_boundary.{pack_id}",
                    message=f"Required gate pack is not a plugin boundary: {pack_id}",
                )
            )
        if pack.pack_id not in row_pack_ids:
            issues.append(
                ScenePluginBoundaryConfirmationIssue(
                    gate_id="*",
                    kind=f"missing_gate_for_pack.{pack_id}",
                    message=f"Required plugin/manual pack has no gate: {pack_id}",
                )
            )
    covered_domains = {
        domain for row in rows for domain in row.risk_domain_ids
    }
    for domain in N2_160_REQUIRED_RISK_DOMAIN_IDS:
        if domain not in covered_domains:
            issues.append(
                ScenePluginBoundaryConfirmationIssue(
                    gate_id="*",
                    kind=f"missing_required_risk_domain.{domain}",
                    message=f"Required risk domain is not covered: {domain}",
                )
            )
    return tuple(issues)


def _build_source_evidence(
    root: Path,
) -> tuple[ScenePluginBoundarySourceEvidence, ...]:
    evidence_items: list[ScenePluginBoundarySourceEvidence] = []
    for evidence_id, source_path, markers in N2_160_SOURCE_EVIDENCE:
        path = root / source_path
        content = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing_markers = tuple(marker for marker in markers if marker not in content)
        evidence_items.append(
            ScenePluginBoundarySourceEvidence(
                evidence_id=evidence_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing_markers,
            )
        )
    return tuple(evidence_items)


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "N2_160_REQUIRED_DECISION_STATES",
    "N2_160_REQUIRED_RISK_DOMAIN_IDS",
    "ScenePluginBoundaryConfirmationAuditReport",
    "ScenePluginBoundaryConfirmationIssue",
    "ScenePluginBoundaryConfirmationRow",
    "ScenePluginBoundarySourceEvidence",
    "audit_scene_plugin_boundary_confirmation_report",
    "build_scene_plugin_boundary_confirmation_audit_report",
]
