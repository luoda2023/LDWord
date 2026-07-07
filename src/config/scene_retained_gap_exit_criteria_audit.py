"""Retained-gap exit criteria audit for scene release readiness.

N2.393j keeps retained boundary gaps from becoming permanent vague exceptions.
Each retained gap may stay outside Green/L5 only when it has a ready release
envelope, a guarded handoff path, explicit release conditions, and a named set
of prohibited core claims that the product must not overstate before exit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.scene_boundary_capability_matrix import (
    list_scene_boundary_capabilities,
)
from src.config.scene_boundary_guarded_completion_audit import (
    build_scene_boundary_guarded_completion_audit_report,
)
from src.config.scene_boundary_maturity_release_envelope_audit import (
    build_scene_boundary_maturity_release_envelope_audit_report,
)
from src.config.scene_external_handoff_contract_audit import (
    build_scene_external_handoff_contract_audit_report,
)


SCENE_RETAINED_GAP_EXIT_CRITERIA_AUDIT_SOURCE_ID = (
    "scene_retained_gap_exit_criteria_audit"
)

SCENE_RETAINED_GAP_RELEASE_CONDITION_IDS: tuple[str, ...] = (
    "release_envelope_ready",
    "handoff_contract_ready",
    "guarded_completion_ready",
    "manual_decision_required",
    "fallback_report_required",
    "excluded_core_claims_declared",
)


@dataclass(frozen=True, slots=True)
class SceneRetainedGapExitCriteriaSpec:
    subject_type: str
    subject_id: str
    gap_id: str
    exit_signal_ids: tuple[str, ...]
    prohibited_core_claim_ids: tuple[str, ...]
    release_condition_ids: tuple[str, ...] = (
        SCENE_RETAINED_GAP_RELEASE_CONDITION_IDS
    )
    rationale: str = ""

    @property
    def criteria_id(self) -> str:
        return f"{self.subject_type}:{self.subject_id}:{self.gap_id}"


SCENE_RETAINED_GAP_EXIT_CRITERIA_SPECS: tuple[
    SceneRetainedGapExitCriteriaSpec, ...
] = (
    SceneRetainedGapExitCriteriaSpec(
        subject_type="pack",
        subject_id="professional_disclosure",
        gap_id="real plugin ecosystem",
        exit_signal_ids=(
            "professional_plugin_marketplace_available",
            "reviewed_plugin_receipt_contract",
            "external_review_result_ingestion",
        ),
        prohibited_core_claim_ids=(
            "audit opinion",
            "legal conclusion",
            "financial assurance",
            "patentability judgment",
            "medical regulatory conclusion",
            "translation quality guarantee",
        ),
        rationale=(
            "Professional disclosure can ship as a guarded boundary, but exits "
            "only when real review plugins and receipt ingestion are available."
        ),
    ),
    SceneRetainedGapExitCriteriaSpec(
        subject_type="pack",
        subject_id="import_ai_boundary",
        gap_id="real OCR/PDF/LaTeX plugin integration",
        exit_signal_ids=(
            "ocr_pdf_latex_plugin_installed",
            "conversion_confidence_receipts",
            "loss_review_artifact_roundtrip",
        ),
        prohibited_core_claim_ids=(
            "lossless PDF to Word",
            "full LaTeX project conversion",
            "OCR truthfulness",
        ),
        rationale=(
            "Import and AI conversion remains releasable only as a confidence "
            "handoff until external conversion plugins provide receipts."
        ),
    ),
    SceneRetainedGapExitCriteriaSpec(
        subject_type="family",
        subject_id="finance_quote_documents",
        gap_id="finance plugin handoff",
        exit_signal_ids=(
            "finance_assurance_plugin_available",
            "quote_source_reconciliation_receipt",
        ),
        prohibited_core_claim_ids=(
            "quotation correctness",
            "financial assurance",
        ),
        rationale=(
            "Finance quote generation may map source tables, but assurance exits "
            "only with a finance review plugin and reconciliation receipt."
        ),
    ),
    SceneRetainedGapExitCriteriaSpec(
        subject_type="family",
        subject_id="ip_patent_documents",
        gap_id="IP plugin handoff",
        exit_signal_ids=(
            "ip_review_plugin_available",
            "claim_quality_review_receipt",
        ),
        prohibited_core_claim_ids=(
            "patentability judgment",
            "claim quality judgment",
        ),
        rationale=(
            "Patent document assembly can be in-core, while claim quality exits "
            "only through an IP review plugin receipt."
        ),
    ),
    SceneRetainedGapExitCriteriaSpec(
        subject_type="family",
        subject_id="bilingual_translation_documents",
        gap_id="translation-quality plugin handoff",
        exit_signal_ids=(
            "translation_quality_plugin_available",
            "termbase_review_receipt",
        ),
        prohibited_core_claim_ids=(
            "translation quality guarantee",
            "silent meaning rewrite",
        ),
        rationale=(
            "Bilingual layout and termbase support can ship, but translation "
            "quality exits only with explicit reviewer or plugin receipts."
        ),
    ),
    SceneRetainedGapExitCriteriaSpec(
        subject_type="family",
        subject_id="regulated_disclosure_documents",
        gap_id="external assurance review handoff",
        exit_signal_ids=(
            "external_assurance_provider_configured",
            "assurance_receipt_archive",
        ),
        prohibited_core_claim_ids=(
            "audit assurance opinion",
            "regulated filing completeness conclusion",
        ),
        rationale=(
            "Regulated disclosure packaging can ship, but assurance exits only "
            "when an external provider and archived receipt are configured."
        ),
    ),
)

SCENE_RETAINED_GAP_EXIT_CRITERIA_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]], ...
] = (
    (
        "retained_gap_exit_criteria_registry",
        "src/config/scene_retained_gap_exit_criteria_audit.py",
        (
            "SCENE_RETAINED_GAP_EXIT_CRITERIA_SPECS",
            "exit_signal_ids",
            "prohibited_core_claim_ids",
        ),
    ),
    (
        "boundary_release_envelope",
        "src/config/scene_boundary_maturity_release_envelope_audit.py",
        (
            "release_envelope_ready",
            "boundary_maturity_release_envelope",
        ),
    ),
    (
        "external_handoff_contract",
        "src/config/scene_external_handoff_contract_audit.py",
        (
            "excluded_core_claims",
            "manual_decision_required",
            "fallback_report_required",
        ),
    ),
    (
        "boundary_guarded_completion",
        "src/config/scene_boundary_guarded_completion_audit.py",
        (
            "boundary_guarded_complete",
            "excluded_core_claims_declared",
        ),
    ),
    (
        "boundary_capability_matrix",
        "src/config/scene_boundary_capability_matrix.py",
        (
            "external_receipt_ids",
            "release_guardrail_ids",
            "boundary_decision_requirements=6/6",
        ),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_RETAINED_GAP_EXIT_CRITERIA_AUDIT_SOURCE_ID,
            "retained_gap_exit_criteria_release_allowed_count",
            "retained_gap_external_receipt_alignment_count",
        ),
    ),
    (
        "scene_matrix_drilldown",
        "src/config/scene_matrix_drilldown_release_items.py",
        (
            SCENE_RETAINED_GAP_EXIT_CRITERIA_AUDIT_SOURCE_ID,
            "retained_gap_exit_criteria",
        ),
    ),
    (
        "summary_projection",
        "src/ui/panels/scene_summary_projection.py",
        (
            "retained_gap_exit_criteria_release_allowed_count",
            "retained gap exit criteria",
            "retained_gap_external_receipt_alignment_count",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_RETAINED_GAP_EXIT_CRITERIA_AUDIT_SOURCE_ID,
            "scene_retained_gap_exit_criteria_release_allowed_count",
            "scene_retained_gap_external_receipt_alignment_count",
            "retained_gap_exit_criteria=",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_retained_gap_exit_criteria_audit.py",
        (
            "build_scene_retained_gap_exit_criteria_audit_report",
            "Release allowed",
            "row.criteria_id",
            "row.exit_signal_ids",
            "row.external_receipt_ids",
            "row.boundary_capability_ids",
            "row.prohibited_core_claim_ids",
            "json",
            "markdown",
        ),
    ),
    (
        "workflow",
        ".github/workflows/scene-matrix-release-gate.yml",
        ("tests/test_scene_retained_gap_exit_criteria_audit.py",),
    ),
    (
        "n2_393j_plan",
        "docs/audits/高层场景能力矩阵N2_393j保留Gap退出准入读数归因补充_2026-06-25.md",
        (
            "N2.393j",
            "retained_gap_exit_criteria=6/6 release-allowed",
            "SCENE_RETAINED_GAP_EXIT_CRITERIA_SPECS",
        ),
    ),
    (
        "n2_397_receipt_alignment_plan",
        "docs/audits/scene_retained_gap_receipt_alignment_N2_397_2026-06-25.md",
        (
            "N2.397",
            "retained_gap_receipt_alignment=6/6",
            "external_receipt_targets=8",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneRetainedGapExitCriteriaIssue:
    criteria_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "criteria_id": self.criteria_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneRetainedGapExitCriteriaSourceEvidence:
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
class SceneRetainedGapExitCriteriaRow:
    criteria_id: str
    subject_type: str
    subject_id: str
    gap_id: str
    status: str
    release_envelope_id: str
    external_handoff_contract_id: str
    guarded_completion_status: str
    boundary_capability_ids: tuple[str, ...]
    exit_signal_ids: tuple[str, ...]
    external_receipt_ids: tuple[str, ...]
    release_condition_ids: tuple[str, ...]
    prohibited_core_claim_ids: tuple[str, ...]
    rationale: str
    issue_ids: tuple[str, ...]

    @property
    def is_release_allowed(self) -> bool:
        return self.status == "release_allowed_with_exit_criteria"

    def to_payload(self) -> dict[str, object]:
        return {
            "criteria_id": self.criteria_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "gap_id": self.gap_id,
            "status": self.status,
            "release_envelope_id": self.release_envelope_id,
            "external_handoff_contract_id": self.external_handoff_contract_id,
            "guarded_completion_status": self.guarded_completion_status,
            "boundary_capability_ids": list(self.boundary_capability_ids),
            "exit_signal_ids": list(self.exit_signal_ids),
            "external_receipt_ids": list(self.external_receipt_ids),
            "release_condition_ids": list(self.release_condition_ids),
            "prohibited_core_claim_ids": list(self.prohibited_core_claim_ids),
            "rationale": self.rationale,
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneRetainedGapExitCriteriaAuditReport:
    rows: tuple[SceneRetainedGapExitCriteriaRow, ...]
    issues: tuple[SceneRetainedGapExitCriteriaIssue, ...]
    source_evidence: tuple[SceneRetainedGapExitCriteriaSourceEvidence, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def criteria_count(self) -> int:
        return len(self.rows)

    @property
    def release_allowed_count(self) -> int:
        return sum(1 for row in self.rows if row.is_release_allowed)

    @property
    def envelope_link_count(self) -> int:
        return sum(1 for row in self.rows if row.release_envelope_id)

    @property
    def handoff_link_count(self) -> int:
        return sum(1 for row in self.rows if row.external_handoff_contract_id)

    @property
    def guarded_completion_link_count(self) -> int:
        return sum(1 for row in self.rows if row.guarded_completion_status)

    @property
    def boundary_capability_link_count(self) -> int:
        return sum(1 for row in self.rows if row.boundary_capability_ids)

    @property
    def exit_signal_count(self) -> int:
        return len(
            _unique_values(signal for row in self.rows for signal in row.exit_signal_ids)
        )

    @property
    def external_receipt_target_count(self) -> int:
        return len(
            _unique_values(
                receipt for row in self.rows for receipt in row.external_receipt_ids
            )
        )

    @property
    def external_receipt_alignment_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.external_receipt_ids
            and set(row.external_receipt_ids).issubset(set(row.exit_signal_ids))
        )

    @property
    def prohibited_core_claim_count(self) -> int:
        return len(
            _unique_values(
                claim for row in self.rows for claim in row.prohibited_core_claim_ids
            )
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_RETAINED_GAP_EXIT_CRITERIA_AUDIT_SOURCE_ID,
            "release_condition_ids": list(SCENE_RETAINED_GAP_RELEASE_CONDITION_IDS),
            "counts": {
                "criteria_count": self.criteria_count,
                "release_allowed_count": self.release_allowed_count,
                "envelope_link_count": self.envelope_link_count,
                "handoff_link_count": self.handoff_link_count,
                "guarded_completion_link_count": self.guarded_completion_link_count,
                "boundary_capability_link_count": self.boundary_capability_link_count,
                "exit_signal_count": self.exit_signal_count,
                "external_receipt_target_count": self.external_receipt_target_count,
                "external_receipt_alignment_count": (
                    self.external_receipt_alignment_count
                ),
                "prohibited_core_claim_count": self.prohibited_core_claim_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_retained_gap_exit_criteria_audit_report(
    *,
    project_root: Path | str | None = None,
    boundary_maturity_release_envelope_report=None,
    external_handoff_contract_report=None,
    boundary_guarded_completion_report=None,
) -> SceneRetainedGapExitCriteriaAuditReport:
    root = Path(project_root) if project_root is not None else Path.cwd()
    envelope_report = (
        boundary_maturity_release_envelope_report
        or build_scene_boundary_maturity_release_envelope_audit_report(
            project_root=root
        )
    )
    handoff_report = (
        external_handoff_contract_report
        or build_scene_external_handoff_contract_audit_report(project_root=root)
    )
    guarded_report = (
        boundary_guarded_completion_report
        or build_scene_boundary_guarded_completion_audit_report(project_root=root)
    )
    envelopes = {(row.subject_type, row.subject_id, row.gap_id): row for row in envelope_report.rows}
    handoffs = {(row.subject_type, row.subject_id, row.gap_id): row for row in handoff_report.rows}
    guarded = {(row.subject_type, row.subject_id): row for row in guarded_report.rows}
    boundary_capabilities: dict[tuple[str, str], list[object]] = {}
    for capability in list_scene_boundary_capabilities():
        boundary_capabilities.setdefault(
            (capability.subject_type, capability.subject_id),
            [],
        ).append(capability)
    rows = tuple(
        _row_for_spec(
            spec,
            envelopes=envelopes,
            handoffs=handoffs,
            guarded=guarded,
            boundary_capabilities={
                key: tuple(value) for key, value in boundary_capabilities.items()
            },
        )
        for spec in SCENE_RETAINED_GAP_EXIT_CRITERIA_SPECS
    )
    source_evidence = _source_evidence(root)
    issues = (
        *_row_issues(rows),
        *_source_evidence_issues(source_evidence),
    )
    return SceneRetainedGapExitCriteriaAuditReport(
        rows=rows,
        issues=issues,
        source_evidence=source_evidence,
    )


def audit_scene_retained_gap_exit_criteria_report(
    report: SceneRetainedGapExitCriteriaAuditReport | None = None,
) -> tuple[SceneRetainedGapExitCriteriaIssue, ...]:
    current = report or build_scene_retained_gap_exit_criteria_audit_report()
    return current.issues


def _row_for_spec(
    spec: SceneRetainedGapExitCriteriaSpec,
    *,
    envelopes: dict[tuple[str, str, str], object],
    handoffs: dict[tuple[str, str, str], object],
    guarded: dict[tuple[str, str], object],
    boundary_capabilities: dict[tuple[str, str], tuple[object, ...]],
) -> SceneRetainedGapExitCriteriaRow:
    subject_key = (spec.subject_type, spec.subject_id)
    gap_key = (*subject_key, spec.gap_id)
    envelope = envelopes.get(gap_key)
    handoff = handoffs.get(gap_key)
    guarded_row = guarded.get(subject_key)
    capability_rows = boundary_capabilities.get(subject_key, ())
    boundary_capability_ids = _unique_values(
        getattr(capability, "capability_id", "") for capability in capability_rows
    )
    external_receipt_ids = _unique_values(
        receipt
        for capability in capability_rows
        for receipt in getattr(capability, "external_receipt_ids", ())
    )
    issue_ids: list[str] = []
    if envelope is None:
        issue_ids.append("missing_release_envelope")
    elif not envelope.is_ready:
        issue_ids.append("release_envelope_not_ready")
    if handoff is None:
        issue_ids.append("missing_handoff_contract")
    elif getattr(handoff, "status", "") != "ready":
        issue_ids.append("handoff_contract_not_ready")
    if guarded_row is None:
        issue_ids.append("missing_guarded_completion")
    elif not guarded_row.is_guarded_complete:
        issue_ids.append("guarded_completion_not_ready")
    elif spec.gap_id not in guarded_row.remaining_gap_ids:
        issue_ids.append("guarded_completion_gap_mismatch")
    if not spec.exit_signal_ids:
        issue_ids.append("missing_exit_signal")
    if not boundary_capability_ids:
        issue_ids.append("missing_boundary_capability")
    if not external_receipt_ids:
        issue_ids.append("missing_boundary_external_receipt")
    else:
        missing_receipt_ids = tuple(
            receipt
            for receipt in external_receipt_ids
            if receipt not in spec.exit_signal_ids
        )
        if missing_receipt_ids:
            issue_ids.append("external_receipt_not_exit_signal")
    if not spec.release_condition_ids:
        issue_ids.append("missing_release_condition")
    if not spec.prohibited_core_claim_ids:
        issue_ids.append("missing_prohibited_core_claim")
    if handoff is not None:
        handoff_claims = set(handoff.excluded_core_claims)
        missing_claims = tuple(
            claim
            for claim in spec.prohibited_core_claim_ids
            if claim not in handoff_claims
        )
        if missing_claims:
            issue_ids.append("prohibited_claim_not_declared")
        if "manual_decision_required" not in handoff.failure_policy_ids:
            issue_ids.append("missing_manual_decision_required")
        if "fallback_report_required" not in handoff.failure_policy_ids:
            issue_ids.append("missing_fallback_report_required")
    return SceneRetainedGapExitCriteriaRow(
        criteria_id=spec.criteria_id,
        subject_type=spec.subject_type,
        subject_id=spec.subject_id,
        gap_id=spec.gap_id,
        status=(
            "release_allowed_with_exit_criteria"
            if not issue_ids
            else "exit_criteria_gap"
        ),
        release_envelope_id=envelope.envelope_id if envelope is not None else "",
        external_handoff_contract_id=handoff.contract_id if handoff is not None else "",
        guarded_completion_status=guarded_row.status if guarded_row is not None else "",
        boundary_capability_ids=boundary_capability_ids,
        exit_signal_ids=spec.exit_signal_ids,
        external_receipt_ids=external_receipt_ids,
        release_condition_ids=spec.release_condition_ids,
        prohibited_core_claim_ids=spec.prohibited_core_claim_ids,
        rationale=spec.rationale,
        issue_ids=tuple(_unique_values(issue_ids)),
    )


def _row_issues(
    rows: tuple[SceneRetainedGapExitCriteriaRow, ...],
) -> tuple[SceneRetainedGapExitCriteriaIssue, ...]:
    return tuple(
        SceneRetainedGapExitCriteriaIssue(
            row.criteria_id,
            issue_id,
            f"Retained gap exit criteria {row.criteria_id} failed: {issue_id}.",
        )
        for row in rows
        for issue_id in row.issue_ids
    )


def _source_evidence(
    root: Path,
) -> tuple[SceneRetainedGapExitCriteriaSourceEvidence, ...]:
    evidence: list[SceneRetainedGapExitCriteriaSourceEvidence] = []
    for source_id, source_path, markers in (
        SCENE_RETAINED_GAP_EXIT_CRITERIA_SOURCE_MARKERS
    ):
        text = _source_text(root, source_path)
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneRetainedGapExitCriteriaSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_text(root: Path, source_path: str) -> str:
    path = Path(source_path)
    if not path.is_absolute():
        path = root / source_path
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _source_evidence_issues(
    source_evidence: tuple[SceneRetainedGapExitCriteriaSourceEvidence, ...],
) -> tuple[SceneRetainedGapExitCriteriaIssue, ...]:
    return tuple(
        SceneRetainedGapExitCriteriaIssue(
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


def _unique_values(values) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_RETAINED_GAP_EXIT_CRITERIA_AUDIT_SOURCE_ID",
    "SCENE_RETAINED_GAP_EXIT_CRITERIA_SPECS",
    "SceneRetainedGapExitCriteriaAuditReport",
    "SceneRetainedGapExitCriteriaIssue",
    "SceneRetainedGapExitCriteriaRow",
    "audit_scene_retained_gap_exit_criteria_report",
    "build_scene_retained_gap_exit_criteria_audit_report",
]
