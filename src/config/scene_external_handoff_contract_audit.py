"""External handoff contract audit for boundary scene capabilities.

N2.379 keeps the last Blue/Boundary gaps honest.  The core formatter still
does not implement external finance/IP/translation/assurance/OCR plugins, but
each remaining gap must have a productized handoff contract: payload, status
states, fixture/report evidence, failure policy, and release/dashboard
visibility.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from src.config.plugin_manual_gate import PLUGIN_MANUAL_GATE_MAP
from src.config.scene_boundary_capability_matrix import (
    list_scene_boundary_capabilities,
)
from src.config.scene_product_readiness import (
    SCENE_PRODUCT_READINESS_MAP,
)
from src.config.scene_sample_fixture_registry import SCENE_SAMPLE_FIXTURE_MAP


SCENE_EXTERNAL_HANDOFF_CONTRACT_AUDIT_SOURCE_ID = (
    "scene_external_handoff_contract_audit"
)

SCENE_EXTERNAL_HANDOFF_STATUS_IDS: tuple[str, ...] = (
    "not_configured",
    "handoff_ready",
    "sent_to_external",
    "external_accepted",
    "external_rejected",
    "returned_with_report",
    "failed",
    "archived",
)

SCENE_EXTERNAL_HANDOFF_REQUIRED_FAILURE_POLICY_IDS: tuple[str, ...] = (
    "block_core_execution_until_confirmed",
    "manual_decision_required",
    "external_status_recorded",
    "fallback_report_required",
)

SCENE_EXTERNAL_HANDOFF_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "handoff_contract_registry",
        "src/config/scene_external_handoff_contract_audit.py",
        (
            "SCENE_EXTERNAL_HANDOFF_CONTRACT_SPECS",
            "external_receipt_id",
            "fallback_report_required",
        ),
    ),
    (
        "plugin_manual_gate",
        "src/config/plugin_manual_gate.py",
        (
            "needs_plugin_handoff",
            "handoff_status",
            "fallback_strategy",
        ),
    ),
    (
        "scene_product_readiness",
        "src/config/scene_product_readiness.py",
        (
            "real plugin ecosystem",
            "finance plugin handoff",
            "external assurance review handoff",
        ),
    ),
    (
        "scene_boundary_capability_matrix",
        "src/config/scene_boundary_capability_matrix.py",
        (
            "handoff_target_ids",
            "finance_plugin_handoff",
            "ocr_pdf_latex_plugin_boundary",
        ),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_EXTERNAL_HANDOFF_CONTRACT_AUDIT_SOURCE_ID,
            "external_handoff_contract_count",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_EXTERNAL_HANDOFF_CONTRACT_AUDIT_SOURCE_ID,
            "scene_external_handoff_contract_ready_count",
        ),
    ),
    (
        "n2_379_plan",
        "docs/audits/高层场景能力矩阵N2_379外部Handoff合同闭环_2026-06-24.md",
        (
            "N2.379",
            "外部 handoff 合同",
            "external_receipt_id",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneExternalHandoffContractSpec:
    contract_id: str
    label: str
    subject_type: str
    subject_id: str
    gap_id: str
    gate_id: str
    target_plugin_id: str
    risk_domain_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    required_report_ids: tuple[str, ...]
    payload_field_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    excluded_core_claims: tuple[str, ...]
    status_ids: tuple[str, ...] = SCENE_EXTERNAL_HANDOFF_STATUS_IDS
    failure_policy_ids: tuple[
        str, ...
    ] = SCENE_EXTERNAL_HANDOFF_REQUIRED_FAILURE_POLICY_IDS


@dataclass(frozen=True, slots=True)
class SceneExternalHandoffContractIssue:
    contract_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneExternalHandoffSourceEvidence:
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
class SceneExternalHandoffContractRow:
    contract_id: str
    label: str
    subject_type: str
    subject_id: str
    gap_id: str
    gate_id: str
    target_plugin_id: str
    readiness_level: str
    risk_domain_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    required_report_ids: tuple[str, ...]
    payload_field_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    status_ids: tuple[str, ...]
    failure_policy_ids: tuple[str, ...]
    excluded_core_claims: tuple[str, ...]
    boundary_capability_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "label": self.label,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "gap_id": self.gap_id,
            "gate_id": self.gate_id,
            "target_plugin_id": self.target_plugin_id,
            "readiness_level": self.readiness_level,
            "risk_domain_ids": list(self.risk_domain_ids),
            "fixture_ids": list(self.fixture_ids),
            "required_report_ids": list(self.required_report_ids),
            "payload_field_ids": list(self.payload_field_ids),
            "ui_surface_ids": list(self.ui_surface_ids),
            "status_ids": list(self.status_ids),
            "failure_policy_ids": list(self.failure_policy_ids),
            "excluded_core_claims": list(self.excluded_core_claims),
            "boundary_capability_ids": list(self.boundary_capability_ids),
            "issue_ids": list(self.issue_ids),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneExternalHandoffContractAuditReport:
    rows: tuple[SceneExternalHandoffContractRow, ...]
    issues: tuple[SceneExternalHandoffContractIssue, ...]
    source_evidence: tuple[SceneExternalHandoffSourceEvidence, ...]
    subject_filter: str = ""
    gate_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def contract_count(self) -> int:
        return len(self.rows)

    @property
    def ready_contract_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def pack_contract_count(self) -> int:
        return sum(1 for row in self.rows if row.subject_type == "pack")

    @property
    def family_contract_count(self) -> int:
        return sum(1 for row in self.rows if row.subject_type == "family")

    @property
    def plugin_gate_count(self) -> int:
        return len(_unique_values(row.gate_id for row in self.rows))

    @property
    def target_plugin_count(self) -> int:
        return len(_unique_values(row.target_plugin_id for row in self.rows))

    @property
    def risk_domain_count(self) -> int:
        return len(_unique_values(domain for row in self.rows for domain in row.risk_domain_ids))

    @property
    def report_count(self) -> int:
        return len(_unique_values(report for row in self.rows for report in row.required_report_ids))

    @property
    def ui_surface_count(self) -> int:
        return len(_unique_values(surface for row in self.rows for surface in row.ui_surface_ids))

    @property
    def fixture_count(self) -> int:
        return len(_unique_values(fixture for row in self.rows for fixture in row.fixture_ids))

    @property
    def status_state_count(self) -> int:
        return len(_unique_values(status for row in self.rows for status in row.status_ids))

    @property
    def failure_policy_count(self) -> int:
        return len(_unique_values(policy for row in self.rows for policy in row.failure_policy_ids))

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_EXTERNAL_HANDOFF_CONTRACT_AUDIT_SOURCE_ID,
            "subject_filter": self.subject_filter,
            "gate_filter": self.gate_filter,
            "required_status_ids": list(SCENE_EXTERNAL_HANDOFF_STATUS_IDS),
            "required_failure_policy_ids": list(
                SCENE_EXTERNAL_HANDOFF_REQUIRED_FAILURE_POLICY_IDS
            ),
            "counts": {
                "contract_count": self.contract_count,
                "ready_contract_count": self.ready_contract_count,
                "pack_contract_count": self.pack_contract_count,
                "family_contract_count": self.family_contract_count,
                "plugin_gate_count": self.plugin_gate_count,
                "target_plugin_count": self.target_plugin_count,
                "risk_domain_count": self.risk_domain_count,
                "report_count": self.report_count,
                "ui_surface_count": self.ui_surface_count,
                "fixture_count": self.fixture_count,
                "status_state_count": self.status_state_count,
                "failure_policy_count": self.failure_policy_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [evidence.to_payload() for evidence in self.source_evidence],
        }


SCENE_EXTERNAL_HANDOFF_CONTRACT_SPECS: tuple[
    SceneExternalHandoffContractSpec,
    ...
] = (
    SceneExternalHandoffContractSpec(
        contract_id="professional_disclosure_plugin_ecosystem_handoff",
        label="Professional disclosure plugin ecosystem handoff",
        subject_type="pack",
        subject_id="professional_disclosure",
        gap_id="real plugin ecosystem",
        gate_id="professional_disclosure_review_gate",
        target_plugin_id="professional_disclosure_review_plugin",
        risk_domain_ids=(
            "audit_assurance",
            "legal_opinion",
            "financial_assurance",
            "ip_patent_quality",
            "medical_regulatory",
            "translation_quality",
        ),
        fixture_ids=(
            "professional_disclosure_manual_boundary",
            "professional_disclosure_source_quality_degraded",
            "professional_disclosure_finance_table_mapping_boundary",
            "professional_disclosure_patent_claim_quality_boundary",
            "professional_disclosure_bilingual_termbase_boundary",
            "professional_disclosure_regulated_assurance_boundary",
        ),
        required_report_ids=(
            "plugin_manual_gate",
            "professional_boundary_matrix",
            "professional_source_quality_report",
        ),
        payload_field_ids=(
            "boundary_text",
            "review_owner",
            "manual_decision",
            "handoff_status",
            "external_receipt_id",
            "fallback_strategy",
        ),
        ui_surface_ids=(
            "professional_boundary_matrix",
            "professional_review_owner_assignment",
            "plugin_handoff_status",
        ),
        excluded_core_claims=(
            "audit opinion",
            "legal conclusion",
            "financial assurance",
            "patentability judgment",
            "medical regulatory conclusion",
            "translation quality guarantee",
        ),
    ),
    SceneExternalHandoffContractSpec(
        contract_id="import_ocr_pdf_latex_plugin_handoff",
        label="OCR/PDF/LaTeX plugin integration handoff",
        subject_type="pack",
        subject_id="import_ai_boundary",
        gap_id="real OCR/PDF/LaTeX plugin integration",
        gate_id="import_ai_conversion_gate",
        target_plugin_id="import_ai_assistant_plugin",
        risk_domain_ids=("ocr_confidence", "pdf_conversion", "full_latex_conversion"),
        fixture_ids=(
            "import_ai_boundary_conversion_confidence_degraded",
            "import_ai_boundary_latex_handoff_confidence",
        ),
        required_report_ids=(
            "conversion_confidence_report",
            "confidence_artifact_manifest",
            "ocr_pdf_latex_plugin_boundary",
            "import_handoff",
        ),
        payload_field_ids=(
            "source_type",
            "confidence_level",
            "low_confidence_regions",
            "manual_decision",
            "handoff_status",
            "external_receipt_id",
            "fallback_strategy",
        ),
        ui_surface_ids=(
            "conversion_confidence_ui",
            "low_confidence_region_review",
            "import_handoff_status",
        ),
        excluded_core_claims=(
            "lossless PDF to Word",
            "full LaTeX project conversion",
            "OCR truthfulness",
        ),
    ),
    SceneExternalHandoffContractSpec(
        contract_id="finance_quote_plugin_handoff",
        label="Finance quote assurance plugin handoff",
        subject_type="family",
        subject_id="finance_quote_documents",
        gap_id="finance plugin handoff",
        gate_id="professional_disclosure_review_gate",
        target_plugin_id="finance_assurance_review_plugin",
        risk_domain_ids=("financial_assurance",),
        fixture_ids=(
            "professional_disclosure_source_quality_degraded",
            "professional_disclosure_finance_table_mapping_boundary",
        ),
        required_report_ids=(
            "finance_spreadsheet_mapping_report",
            "finance_plugin_handoff",
            "attachment_inventory",
        ),
        payload_field_ids=(
            "quote_source_workbook_id",
            "spreadsheet_table_mapping_manifest",
            "attachment_inventory_manifest",
            "manual_decision",
            "handoff_status",
            "external_receipt_id",
        ),
        ui_surface_ids=("finance_table_mapping_review", "finance_plugin_handoff_status"),
        excluded_core_claims=("quotation correctness", "financial assurance"),
    ),
    SceneExternalHandoffContractSpec(
        contract_id="ip_patent_plugin_handoff",
        label="IP/patent claim-quality plugin handoff",
        subject_type="family",
        subject_id="ip_patent_documents",
        gap_id="IP plugin handoff",
        gate_id="professional_disclosure_review_gate",
        target_plugin_id="ip_patent_review_plugin",
        risk_domain_ids=("ip_patent_quality", "legal_opinion"),
        fixture_ids=("professional_disclosure_patent_claim_quality_boundary",),
        required_report_ids=(
            "patent_claim_boundary_report",
            "claim_quality_boundary_ui",
            "ip_plugin_handoff",
        ),
        payload_field_ids=(
            "claim_outline_manifest",
            "figure_number_inventory",
            "review_owner",
            "manual_decision",
            "handoff_status",
            "external_receipt_id",
        ),
        ui_surface_ids=("claim_quality_boundary_ui", "ip_plugin_handoff_status"),
        excluded_core_claims=("patentability judgment", "claim quality judgment"),
    ),
    SceneExternalHandoffContractSpec(
        contract_id="translation_quality_plugin_handoff",
        label="Translation-quality plugin handoff",
        subject_type="family",
        subject_id="bilingual_translation_documents",
        gap_id="translation-quality plugin handoff",
        gate_id="professional_disclosure_review_gate",
        target_plugin_id="translation_quality_review_plugin",
        risk_domain_ids=("translation_quality",),
        fixture_ids=("professional_disclosure_bilingual_termbase_boundary",),
        required_report_ids=(
            "bilingual_termbase_report",
            "termbase_ui",
            "translation_quality_plugin_handoff",
        ),
        payload_field_ids=(
            "termbase_manifest",
            "parallel_alignment_manifest",
            "unresolved_term_report_id",
            "manual_decision",
            "handoff_status",
            "external_receipt_id",
        ),
        ui_surface_ids=("termbase_ui", "translation_quality_plugin_handoff_status"),
        excluded_core_claims=("translation quality guarantee", "silent meaning rewrite"),
    ),
    SceneExternalHandoffContractSpec(
        contract_id="regulated_assurance_review_handoff",
        label="Regulated disclosure assurance review handoff",
        subject_type="family",
        subject_id="regulated_disclosure_documents",
        gap_id="external assurance review handoff",
        gate_id="professional_disclosure_review_gate",
        target_plugin_id="external_assurance_review_plugin",
        risk_domain_ids=("audit_assurance",),
        fixture_ids=(
            "professional_disclosure_manual_boundary",
            "professional_disclosure_regulated_assurance_boundary",
        ),
        required_report_ids=(
            "regulated_rule_source_governance",
            "assurance_boundary_ui",
            "disclosure_archive_manifest",
        ),
        payload_field_ids=(
            "regulated_rule_source_id",
            "section_inventory_manifest",
            "table_attachment_inventory_manifest",
            "review_owner",
            "manual_decision",
            "handoff_status",
            "external_receipt_id",
        ),
        ui_surface_ids=("assurance_boundary_ui", "external_assurance_handoff_status"),
        excluded_core_claims=(
            "audit assurance opinion",
            "regulated filing completeness conclusion",
        ),
    ),
)


def list_scene_external_handoff_contracts() -> tuple[
    SceneExternalHandoffContractSpec,
    ...
]:
    return SCENE_EXTERNAL_HANDOFF_CONTRACT_SPECS


def build_scene_external_handoff_contract_audit_report(
    *,
    subject_id: str = "",
    gate_id: str = "",
    project_root: Path | str | None = None,
) -> SceneExternalHandoffContractAuditReport:
    normalized_subject = str(subject_id or "").strip()
    normalized_gate = str(gate_id or "").strip()
    specs = tuple(
        spec
        for spec in SCENE_EXTERNAL_HANDOFF_CONTRACT_SPECS
        if (not normalized_subject or spec.subject_id == normalized_subject)
        and (not normalized_gate or spec.gate_id == normalized_gate)
    )
    rows: list[SceneExternalHandoffContractRow] = []
    issues: list[SceneExternalHandoffContractIssue] = []
    for spec in specs:
        row = _row_for_spec(spec)
        row_issues = _row_issues(row)
        issues.extend(row_issues)
        rows.append(replace(row, issue_ids=tuple(issue.kind for issue in row_issues)))
    if normalized_subject and not rows:
        issues.append(
            SceneExternalHandoffContractIssue(
                normalized_subject,
                "unknown_subject_filter",
                f"Unknown external handoff subject: {normalized_subject}",
            )
        )
    if normalized_gate and not rows:
        issues.append(
            SceneExternalHandoffContractIssue(
                normalized_gate,
                "unknown_gate_filter",
                f"Unknown external handoff gate: {normalized_gate}",
            )
        )
    if not normalized_subject and not normalized_gate:
        issues.extend(_global_issues(tuple(rows)))
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneExternalHandoffContractAuditReport(
        rows=tuple(rows),
        issues=tuple(issues),
        source_evidence=source_evidence,
        subject_filter=normalized_subject,
        gate_filter=normalized_gate,
    )


def audit_scene_external_handoff_contract_report(
    report: SceneExternalHandoffContractAuditReport | None = None,
) -> tuple[SceneExternalHandoffContractIssue, ...]:
    current = report or build_scene_external_handoff_contract_audit_report()
    return current.issues


def _row_for_spec(
    spec: SceneExternalHandoffContractSpec,
) -> SceneExternalHandoffContractRow:
    readiness = SCENE_PRODUCT_READINESS_MAP.get((spec.subject_type, spec.subject_id))
    capability_ids = tuple(
        capability.capability_id
        for capability in list_scene_boundary_capabilities()
        if capability.subject_type == spec.subject_type
        and capability.subject_id == spec.subject_id
    )
    return SceneExternalHandoffContractRow(
        contract_id=spec.contract_id,
        label=spec.label,
        subject_type=spec.subject_type,
        subject_id=spec.subject_id,
        gap_id=spec.gap_id,
        gate_id=spec.gate_id,
        target_plugin_id=spec.target_plugin_id,
        readiness_level=(
            readiness.product_readiness_level if readiness is not None else ""
        ),
        risk_domain_ids=spec.risk_domain_ids,
        fixture_ids=spec.fixture_ids,
        required_report_ids=spec.required_report_ids,
        payload_field_ids=spec.payload_field_ids,
        ui_surface_ids=spec.ui_surface_ids,
        status_ids=spec.status_ids,
        failure_policy_ids=spec.failure_policy_ids,
        excluded_core_claims=spec.excluded_core_claims,
        boundary_capability_ids=capability_ids,
        issue_ids=(),
    )


def _row_issues(
    row: SceneExternalHandoffContractRow,
) -> tuple[SceneExternalHandoffContractIssue, ...]:
    issues: list[SceneExternalHandoffContractIssue] = []

    def append(kind: str, message: str) -> None:
        issues.append(SceneExternalHandoffContractIssue(row.contract_id, kind, message))

    readiness = SCENE_PRODUCT_READINESS_MAP.get((row.subject_type, row.subject_id))
    if readiness is None:
        append("missing_product_readiness", "Subject has no product-readiness row.")
    else:
        if row.readiness_level != "blue_boundary":
            append(
                "subject_not_blue_boundary",
                "External handoff contracts must stay on Blue/Boundary subjects.",
            )
        if row.gap_id not in readiness.remaining_product_gaps:
            append(
                "gap_not_registered",
                f"Gap is not registered on product readiness: {row.gap_id}.",
            )
    gate = PLUGIN_MANUAL_GATE_MAP.get(_gate_pack_id(row.gate_id))
    if gate is None or gate.gate_id != row.gate_id:
        append("missing_plugin_gate", f"Unknown plugin/manual gate: {row.gate_id}.")
    else:
        gate_domains = set(gate.risk_domain_ids)
        missing_domains = tuple(
            domain for domain in row.risk_domain_ids if domain not in gate_domains
        )
        if missing_domains:
            append(
                "risk_domain_not_on_gate",
                "Risk domains missing from gate: " + ", ".join(missing_domains),
            )
        if "needs_plugin_handoff" not in gate.confirmation_decision_states:
            append(
                "missing_plugin_handoff_decision",
                "Gate must expose the needs_plugin_handoff decision state.",
            )
    fixture_reports: list[str] = []
    for fixture_id in row.fixture_ids:
        fixture = SCENE_SAMPLE_FIXTURE_MAP.get(fixture_id)
        if fixture is None:
            append("missing_fixture", f"Unknown handoff fixture: {fixture_id}.")
            continue
        if fixture.manual_gate_id != row.gate_id:
            append(
                "fixture_gate_mismatch",
                f"Fixture {fixture_id} is not attached to {row.gate_id}.",
            )
        fixture_reports.extend(fixture.report_expectations)
    missing_reports = tuple(
        report_id
        for report_id in row.required_report_ids
        if report_id not in fixture_reports
    )
    if missing_reports:
        append(
            "missing_fixture_report_evidence",
            "Fixture reports missing: " + ", ".join(missing_reports),
        )
    for field_id in ("manual_decision", "handoff_status", "external_receipt_id"):
        if field_id not in row.payload_field_ids:
            append(
                f"missing_payload_field.{field_id}",
                f"Handoff payload must include {field_id}.",
            )
    for status_id in SCENE_EXTERNAL_HANDOFF_STATUS_IDS:
        if status_id not in row.status_ids:
            append(
                f"missing_status.{status_id}",
                f"Handoff status state is missing: {status_id}.",
            )
    for policy_id in SCENE_EXTERNAL_HANDOFF_REQUIRED_FAILURE_POLICY_IDS:
        if policy_id not in row.failure_policy_ids:
            append(
                f"missing_failure_policy.{policy_id}",
                f"Handoff failure policy is missing: {policy_id}.",
            )
    if not row.boundary_capability_ids:
        append(
            "missing_boundary_capability",
            "External handoff contract must link to a boundary capability row.",
        )
    if not row.excluded_core_claims:
        append(
            "missing_excluded_core_claims",
            "External handoff contract must declare claims core will not make.",
        )
    return tuple(issues)


def _global_issues(
    rows: tuple[SceneExternalHandoffContractRow, ...],
) -> tuple[SceneExternalHandoffContractIssue, ...]:
    issues: list[SceneExternalHandoffContractIssue] = []
    subjects = {(row.subject_type, row.subject_id) for row in rows}
    for key, readiness in SCENE_PRODUCT_READINESS_MAP.items():
        if readiness.product_readiness_level != "blue_boundary":
            continue
        if key not in subjects:
            issues.append(
                SceneExternalHandoffContractIssue(
                    ":".join(key),
                    "missing_boundary_subject_contract",
                    "Every Blue/Boundary readiness subject needs an external handoff contract.",
                )
            )
    return tuple(issues)


def _gate_pack_id(gate_id: str) -> str:
    for pack_id, gate in PLUGIN_MANUAL_GATE_MAP.items():
        if gate.gate_id == gate_id:
            return pack_id
    return ""


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneExternalHandoffSourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneExternalHandoffSourceEvidence] = []
    for source_id, source_path, markers in SCENE_EXTERNAL_HANDOFF_SOURCE_MARKERS:
        path = Path(source_path)
        if not path.is_absolute():
            path = root / source_path
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneExternalHandoffSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneExternalHandoffSourceEvidence, ...],
) -> tuple[SceneExternalHandoffContractIssue, ...]:
    return tuple(
        SceneExternalHandoffContractIssue(
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


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_EXTERNAL_HANDOFF_CONTRACT_AUDIT_SOURCE_ID",
    "SCENE_EXTERNAL_HANDOFF_CONTRACT_SPECS",
    "SCENE_EXTERNAL_HANDOFF_REQUIRED_FAILURE_POLICY_IDS",
    "SCENE_EXTERNAL_HANDOFF_STATUS_IDS",
    "SceneExternalHandoffContractAuditReport",
    "SceneExternalHandoffContractIssue",
    "SceneExternalHandoffContractRow",
    "SceneExternalHandoffContractSpec",
    "SceneExternalHandoffSourceEvidence",
    "audit_scene_external_handoff_contract_report",
    "build_scene_external_handoff_contract_audit_report",
    "list_scene_external_handoff_contracts",
]
