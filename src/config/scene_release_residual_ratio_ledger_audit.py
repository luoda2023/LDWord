"""Release residual-ratio ledger audit for the scene matrix.

N2.393 makes the non-full ratios printed by the terminal release gate
publishable.  The lower-level readiness reconciliation and boundary envelopes
already explain the source rows; this ledger binds the final summary counters
to that evidence so a green release gate does not still look like hidden
unfinished work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.scene_source_evidence import (
    scan_scene_source_markers,
    scene_source_marker_issue_message,
)
from src.config.scene_boundary_guarded_completion_audit import (
    build_scene_boundary_guarded_completion_audit_report,
)
from src.config.scene_boundary_maturity_release_envelope_audit import (
    build_scene_boundary_maturity_release_envelope_audit_report,
)
from src.config.scene_boundary_readiness_reconciliation_audit import (
    build_scene_boundary_readiness_reconciliation_audit_report,
)
from src.config.scene_count_profile_audit import build_scene_count_profile_audit_report
from src.config.scene_delivery_preset_audit import (
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_product_maturity_upgrade_audit import (
    build_scene_product_maturity_upgrade_audit_report,
)
from src.config.scene_retained_gap_exit_criteria_audit import (
    build_scene_retained_gap_exit_criteria_audit_report,
)
from src.config.scene_terminal_release_exception_audit import (
    build_scene_terminal_release_exception_audit_report,
)


SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_AUDIT_SOURCE_ID = (
    "scene_release_residual_ratio_ledger_audit"
)

COUNT_DELIVERY_BOUNDARY_RATIO_IDS = ("count_profiles", "delivery_families")
COUNT_DELIVERY_SHARED_BOUNDARY_IDS = (
    "family:ip_patent_documents:IP plugin handoff",
    "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration",
)

SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "actual_release_summary_ratio",
    "readiness_reconciliation_trace",
    "terminal_release_exception",
    "release_envelope_trace",
    "retained_gap_exit_criteria_trace",
    "retained_gap_receipt_alignment_trace",
    "count_delivery_receipt_alignment_trace",
    "maturity_l5_receipt_alignment_trace",
    "boundary_scope_guard_trace",
    "dashboard_projection",
    "release_gate_projection",
    "closure_doc",
)


@dataclass(frozen=True, slots=True)
class SceneReleaseResidualRatioLedgerSpec:
    ratio_id: str
    source_id: str
    numerator_attr: str
    denominator_attr: str
    expected_numerator: int
    expected_denominator: int
    residual_mode: str
    reason: str
    readiness_reconciliation_row_ids: tuple[str, ...]
    terminal_exception_ids: tuple[str, ...]
    release_envelope_ids: tuple[str, ...] = ()
    retained_gap_exit_criteria_ids: tuple[str, ...] = ()


SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_SPECS: tuple[
    SceneReleaseResidualRatioLedgerSpec, ...
] = (
    SceneReleaseResidualRatioLedgerSpec(
        ratio_id="count_profiles",
        source_id="scene_count_profile_audit",
        numerator_attr="ready_family_count",
        denominator_attr="family_count",
        expected_numerator=14,
        expected_denominator=15,
        residual_mode="boundary_or_not_applicable_count_surface",
        reason=(
            "CountProfile remains 14/15 because ip_patent_documents is a "
            "professional-review boundary; quick formatting and import-AI also "
            "stay explicit not-applicable count surfaces."
        ),
        readiness_reconciliation_row_ids=(
            "scene_count_profile_audit:family_readiness_delta:family:ip_patent_documents",
            "scene_count_profile_audit:pack_not_applicable_delta:pack:quick_formatting",
            "scene_count_profile_audit:pack_not_applicable_delta:pack:import_ai_boundary",
        ),
        terminal_exception_ids=("boundary_readiness_reconciliation",),
        release_envelope_ids=(
            "family:ip_patent_documents:IP plugin handoff",
            "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration",
        ),
        retained_gap_exit_criteria_ids=(
            "family:ip_patent_documents:IP plugin handoff",
            "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration",
        ),
    ),
    SceneReleaseResidualRatioLedgerSpec(
        ratio_id="delivery_families",
        source_id="scene_delivery_preset_audit",
        numerator_attr="ready_family_count",
        denominator_attr="family_count",
        expected_numerator=14,
        expected_denominator=15,
        residual_mode="boundary_delivery_surface",
        reason=(
            "DeliveryPreset remains 14/15 because patent delivery is a "
            "professional handoff boundary, while import-AI delivery is a "
            "handoff/report boundary rather than a final-DOCX promise."
        ),
        readiness_reconciliation_row_ids=(
            "scene_delivery_preset_audit:family_readiness_delta:family:ip_patent_documents",
            "scene_delivery_preset_audit:pack_readiness_delta:pack:import_ai_boundary",
        ),
        terminal_exception_ids=("boundary_readiness_reconciliation",),
        release_envelope_ids=(
            "family:ip_patent_documents:IP plugin handoff",
            "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration",
        ),
        retained_gap_exit_criteria_ids=(
            "family:ip_patent_documents:IP plugin handoff",
            "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration",
        ),
    ),
    SceneReleaseResidualRatioLedgerSpec(
        ratio_id="maturity_l5_blocked",
        source_id="scene_product_maturity_upgrade_audit",
        numerator_attr="l5_blocked_subject_count",
        denominator_attr="subject_count",
        expected_numerator=6,
        expected_denominator=27,
        residual_mode="boundary_maturity_retained",
        reason=(
            "Six Blue/Boundary subjects remain intentionally outside Green/L5, "
            "and each retained blocker has a N2.392 release envelope."
        ),
        readiness_reconciliation_row_ids=(
            "scene_product_maturity_upgrade_audit:maturity_l5_blocked:pack:professional_disclosure",
            "scene_product_maturity_upgrade_audit:maturity_l5_blocked:pack:import_ai_boundary",
            "scene_product_maturity_upgrade_audit:maturity_l5_blocked:family:finance_quote_documents",
            "scene_product_maturity_upgrade_audit:maturity_l5_blocked:family:ip_patent_documents",
            "scene_product_maturity_upgrade_audit:maturity_l5_blocked:family:bilingual_translation_documents",
            "scene_product_maturity_upgrade_audit:maturity_l5_blocked:family:regulated_disclosure_documents",
        ),
        terminal_exception_ids=("boundary_guarded_maturity",),
        release_envelope_ids=(
            "pack:professional_disclosure:real plugin ecosystem",
            "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration",
            "family:finance_quote_documents:finance plugin handoff",
            "family:ip_patent_documents:IP plugin handoff",
            "family:bilingual_translation_documents:translation-quality plugin handoff",
            "family:regulated_disclosure_documents:external assurance review handoff",
        ),
        retained_gap_exit_criteria_ids=(
            "pack:professional_disclosure:real plugin ecosystem",
            "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration",
            "family:finance_quote_documents:finance plugin handoff",
            "family:ip_patent_documents:IP plugin handoff",
            "family:bilingual_translation_documents:translation-quality plugin handoff",
            "family:regulated_disclosure_documents:external assurance review handoff",
        ),
    ),
)

SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "release_residual_ratio_ledger_registry",
        "src/config/scene_release_residual_ratio_ledger_audit.py",
        (
            "SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_SPECS",
            "actual_release_summary_ratio",
            "maturity_l5_blocked",
            "count_delivery_receipt_alignment_ids",
            "maturity_l5_receipt_alignment_ids",
            "retained_gap_exit_criteria_ids",
            "retained_gap_receipt_alignment_ids",
        ),
    ),
    (
        "boundary_readiness_reconciliation",
        "src/config/scene_boundary_readiness_reconciliation_audit.py",
        ("SCENE_BOUNDARY_READINESS_RECONCILIATION_SPECS", "reconciled"),
    ),
    (
        "boundary_maturity_release_envelope",
        "src/config/scene_boundary_maturity_release_envelope_audit.py",
        ("release_envelope_ready", "SCENE_BOUNDARY_MATURITY_RELEASE_ENVELOPE"),
    ),
    (
        "boundary_guarded_completion",
        "src/config/scene_boundary_guarded_completion_audit.py",
        (
            "boundary_guarded_complete",
            "boundary_capability_ids",
            "excluded_core_claims",
        ),
    ),
    (
        "retained_gap_exit_criteria",
        "src/config/scene_retained_gap_exit_criteria_audit.py",
        (
            "SCENE_RETAINED_GAP_EXIT_CRITERIA_SPECS",
            "release_allowed_with_exit_criteria",
            "external_receipt_ids",
            "external_receipt_alignment_count",
        ),
    ),
    (
        "terminal_release_exception",
        "src/config/scene_terminal_release_exception_audit.py",
        ("boundary_guarded_maturity", "boundary_readiness_reconciliation"),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_AUDIT_SOURCE_ID,
            "release_residual_ratio_ledger_published_count",
            "count_profile_accounted_family_count",
            "delivery_preset_accounted_family_count",
            "count/delivery boundary links aligned",
            "count/delivery receipts aligned",
            "L5 blockers aligned",
            "L5 receipts aligned",
            "boundary scopes guarded",
            "release_residual_ratio_ledger_count_delivery_receipt_alignment_count",
            "release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count",
            "release_residual_ratio_ledger_receipt_alignment_link_count",
        ),
    ),
    (
        "scene_matrix_drilldown",
        "src/config/scene_matrix_drilldown_release_items.py",
        (
            SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_AUDIT_SOURCE_ID,
            "release_residual_ratio_ledger",
            "boundary_scope_guarded",
            "excluded_core_claims_declared",
        ),
    ),
    (
        "summary_projection",
        "src/ui/panels/scene_summary_projection.py",
        (
            "release_residual_ratio_ledger_published_count",
            "release residual ratios",
            "CountProfile accounted",
            "delivery accounted",
            "count/delivery boundary links aligned",
            "count/delivery receipts aligned",
            "L5 blockers aligned",
            "L5 receipts aligned",
            "boundary scopes guarded",
            "residual ratio receipts",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_AUDIT_SOURCE_ID,
            "scene_release_residual_ratio_ledger_published_count",
            "count_profile_accounted=",
            "count_delivery_alignment=",
            "count_delivery_receipts=",
            "delivery_family_accounted=",
            "maturity_l5_enveloped=",
            "maturity_l5_alignment=",
            "maturity_l5_receipts=",
            "boundary_scope_alignment=",
            "residual_ratio_exit_criteria=",
            "residual_ratio_receipts=",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_release_residual_ratio_ledger_audit.py",
        (
            "run_registered_scene_audit_export",
            SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_AUDIT_SOURCE_ID,
            "Residual ratios published",
            "row.ratio_id",
            "row.observed_ratio",
            "row.residual_mode",
            "Boundary scope alignments",
            "Receipt alignments",
            "Count/delivery receipt alignments",
            "Maturity L5 receipt alignments",
            "row.retained_gap_receipt_alignment_ids",
            "markdown",
        ),
    ),
    (
        "n2_393a_accounted_plan",
        "docs/audits/高层场景能力矩阵N2_393a非满格读数归因补充_2026-06-24.md",
        (
            "N2.393a",
            "count_profile_accounted=15/15",
            "delivery_family_accounted=15/15",
            "fow_family_accounted=15/15",
        ),
    ),
    (
        "n2_393b_maturity_blocker_envelope_plan",
        "docs/audits/高层场景能力矩阵N2_393b成熟度阻断读数归因补充_2026-06-25.md",
        (
            "N2.393b",
            "maturity_l5_blocked=6/27",
            "maturity_l5_enveloped=6/6",
            "maturity_l5_alignment=6/6",
            "release_envelope_ids",
            "criteria id 集合",
        ),
    ),
    (
        "workflow",
        ".github/workflows/scene-matrix-release-gate.yml",
        ("tests/test_scene_release_residual_ratio_ledger_audit.py",),
    ),
    (
        "n2_393k_exit_criteria_links_plan",
        "docs/audits/高层场景能力矩阵N2_393k残留比例退出准入链接补充_2026-06-25.md",
        (
            "N2.393k",
            "residual_ratio_exit_criteria=10/10",
            "count_delivery_alignment=4/4",
            "retained_gap_exit_criteria_trace",
        ),
    ),
    (
        "n2_398_receipt_alignment_plan",
        "docs/audits/scene_release_residual_ratio_receipt_alignment_N2_398_2026-06-25.md",
        (
            "N2.398",
            "residual_ratio_receipt_alignment=10/10",
            "retained_gap_receipts=6/6",
        ),
    ),
    (
        "n2_405_count_delivery_receipt_plan",
        "docs/audits/scene_count_delivery_receipt_alignment_trace_N2_405_2026-06-25.md",
        (
            "N2.405",
            "count_delivery_receipts=4/4",
            "count/delivery receipts aligned",
        ),
    ),
    (
        "n2_406_maturity_l5_receipt_plan",
        "docs/audits/scene_maturity_l5_receipt_alignment_trace_N2_406_2026-06-25.md",
        (
            "N2.406",
            "maturity_l5_receipts=6/6",
            "L5 receipts aligned",
        ),
    ),
    (
        "n2_393_plan",
        "docs/audits/高层场景能力矩阵N2_393发布残留比例读数账本闭环_2026-06-24.md",
        ("N2.393", "release_residual_ratio_ledger", "3/3"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneReleaseResidualRatioLedgerIssue:
    ratio_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "ratio_id": self.ratio_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseResidualRatioLedgerSourceEvidence:
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
class SceneReleaseResidualRatioLedgerRow:
    ratio_id: str
    source_id: str
    observed_numerator: int
    observed_denominator: int
    expected_numerator: int
    expected_denominator: int
    residual_mode: str
    status: str
    reason: str
    readiness_reconciliation_row_ids: tuple[str, ...]
    terminal_exception_ids: tuple[str, ...]
    release_envelope_ids: tuple[str, ...]
    retained_gap_exit_criteria_ids: tuple[str, ...]
    retained_gap_receipt_alignment_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def is_published(self) -> bool:
        return self.status == "published_residual_ratio"

    @property
    def observed_ratio(self) -> str:
        return f"{self.observed_numerator}/{self.observed_denominator}"

    @property
    def expected_ratio(self) -> str:
        return f"{self.expected_numerator}/{self.expected_denominator}"

    def to_payload(self) -> dict[str, object]:
        return {
            "ratio_id": self.ratio_id,
            "source_id": self.source_id,
            "observed_numerator": self.observed_numerator,
            "observed_denominator": self.observed_denominator,
            "observed_ratio": self.observed_ratio,
            "expected_numerator": self.expected_numerator,
            "expected_denominator": self.expected_denominator,
            "expected_ratio": self.expected_ratio,
            "residual_mode": self.residual_mode,
            "status": self.status,
            "reason": self.reason,
            "readiness_reconciliation_row_ids": list(
                self.readiness_reconciliation_row_ids
            ),
            "terminal_exception_ids": list(self.terminal_exception_ids),
            "release_envelope_ids": list(self.release_envelope_ids),
            "retained_gap_exit_criteria_ids": list(
                self.retained_gap_exit_criteria_ids
            ),
            "retained_gap_receipt_alignment_ids": list(
                self.retained_gap_receipt_alignment_ids
            ),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseResidualRatioLedgerAuditReport:
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...]
    issues: tuple[SceneReleaseResidualRatioLedgerIssue, ...]
    source_evidence: tuple[SceneReleaseResidualRatioLedgerSourceEvidence, ...]
    count_delivery_boundary_alignment_ids: tuple[str, ...] = ()
    count_delivery_receipt_alignment_ids: tuple[str, ...] = ()
    maturity_l5_blocker_alignment_ids: tuple[str, ...] = ()
    maturity_l5_blocker_receipt_alignment_ids: tuple[str, ...] = ()
    boundary_scope_alignment_ids: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def ratio_count(self) -> int:
        return len(self.rows)

    @property
    def published_ratio_count(self) -> int:
        return sum(1 for row in self.rows if row.is_published)

    @property
    def non_full_ratio_count(self) -> int:
        return sum(1 for row in self.rows if row.observed_numerator != row.observed_denominator)

    @property
    def readiness_reconciliation_link_count(self) -> int:
        return sum(
            len(row.readiness_reconciliation_row_ids)
            for row in self.rows
            if "missing_readiness_reconciliation" not in row.issue_ids
        )

    @property
    def terminal_exception_link_count(self) -> int:
        return sum(
            len(row.terminal_exception_ids)
            for row in self.rows
            if "missing_terminal_release_exception" not in row.issue_ids
        )

    @property
    def release_envelope_link_count(self) -> int:
        return sum(
            len(row.release_envelope_ids)
            for row in self.rows
            if "missing_release_envelope" not in row.issue_ids
        )

    @property
    def retained_gap_exit_criteria_link_count(self) -> int:
        return sum(
            len(row.retained_gap_exit_criteria_ids)
            for row in self.rows
            if "missing_retained_gap_exit_criteria" not in row.issue_ids
        )

    @property
    def retained_gap_receipt_alignment_link_count(self) -> int:
        return sum(
            len(row.retained_gap_receipt_alignment_ids)
            for row in self.rows
            if "missing_retained_gap_receipt_alignment" not in row.issue_ids
        )

    @property
    def count_delivery_boundary_alignment_count(self) -> int:
        return len(self.count_delivery_boundary_alignment_ids)

    @property
    def count_delivery_boundary_link_count(self) -> int:
        return sum(
            len(row.release_envelope_ids)
            for row in self.rows
            if row.ratio_id in COUNT_DELIVERY_BOUNDARY_RATIO_IDS
        )

    @property
    def count_delivery_receipt_alignment_count(self) -> int:
        return len(self.count_delivery_receipt_alignment_ids)

    @property
    def count_delivery_receipt_alignment_link_count(self) -> int:
        return self.count_delivery_boundary_link_count

    @property
    def maturity_l5_blocker_alignment_count(self) -> int:
        return len(self.maturity_l5_blocker_alignment_ids)

    @property
    def maturity_l5_blocker_release_envelope_count(self) -> int:
        row = _maturity_l5_blocker_row(self.rows)
        if row is None:
            return 0
        return len(row.release_envelope_ids)

    @property
    def maturity_l5_blocker_receipt_alignment_count(self) -> int:
        return len(self.maturity_l5_blocker_receipt_alignment_ids)

    @property
    def maturity_l5_blocker_receipt_alignment_link_count(self) -> int:
        return self.maturity_l5_blocker_release_envelope_count

    @property
    def boundary_scope_alignment_count(self) -> int:
        return len(self.boundary_scope_alignment_ids)

    @property
    def boundary_scope_link_count(self) -> int:
        return len(_unique_release_envelope_ids(self.rows))

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_AUDIT_SOURCE_ID,
            "required_evidence_ids": list(
                SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "ratio_count": self.ratio_count,
                "published_ratio_count": self.published_ratio_count,
                "non_full_ratio_count": self.non_full_ratio_count,
                "readiness_reconciliation_link_count": (
                    self.readiness_reconciliation_link_count
                ),
                "terminal_exception_link_count": self.terminal_exception_link_count,
                "release_envelope_link_count": self.release_envelope_link_count,
                "retained_gap_exit_criteria_link_count": (
                    self.retained_gap_exit_criteria_link_count
                ),
                "retained_gap_receipt_alignment_link_count": (
                    self.retained_gap_receipt_alignment_link_count
                ),
                "count_delivery_boundary_alignment_count": (
                    self.count_delivery_boundary_alignment_count
                ),
                "count_delivery_boundary_link_count": (
                    self.count_delivery_boundary_link_count
                ),
                "count_delivery_receipt_alignment_count": (
                    self.count_delivery_receipt_alignment_count
                ),
                "count_delivery_receipt_alignment_link_count": (
                    self.count_delivery_receipt_alignment_link_count
                ),
                "maturity_l5_blocker_alignment_count": (
                    self.maturity_l5_blocker_alignment_count
                ),
                "maturity_l5_blocker_release_envelope_count": (
                    self.maturity_l5_blocker_release_envelope_count
                ),
                "maturity_l5_blocker_receipt_alignment_count": (
                    self.maturity_l5_blocker_receipt_alignment_count
                ),
                "maturity_l5_blocker_receipt_alignment_link_count": (
                    self.maturity_l5_blocker_receipt_alignment_link_count
                ),
                "boundary_scope_alignment_count": (
                    self.boundary_scope_alignment_count
                ),
                "boundary_scope_link_count": self.boundary_scope_link_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_release_residual_ratio_ledger_audit_report(
    *,
    project_root: Path | str | None = None,
) -> SceneReleaseResidualRatioLedgerAuditReport:
    reports = {
        "scene_count_profile_audit": build_scene_count_profile_audit_report(
            project_root=project_root
        ),
        "scene_delivery_preset_audit": build_scene_delivery_preset_audit_report(
            project_root=project_root
        ),
        "scene_product_maturity_upgrade_audit": (
            build_scene_product_maturity_upgrade_audit_report(
                project_root=project_root
            )
        ),
    }
    readiness_report = build_scene_boundary_readiness_reconciliation_audit_report(
        project_root=project_root
    )
    terminal_report = build_scene_terminal_release_exception_audit_report(
        project_root=project_root
    )
    envelope_report = build_scene_boundary_maturity_release_envelope_audit_report(
        project_root=project_root
    )
    guarded_report = build_scene_boundary_guarded_completion_audit_report(
        project_root=project_root
    )
    exit_criteria_report = build_scene_retained_gap_exit_criteria_audit_report(
        project_root=project_root,
        boundary_maturity_release_envelope_report=envelope_report,
    )
    readiness_by_id = {row.row_id: row for row in readiness_report.rows}
    terminal_by_id = {row.exception_id: row for row in terminal_report.rows}
    envelope_by_id = {row.envelope_id: row for row in envelope_report.rows}
    exit_criteria_by_id = {
        row.criteria_id: row for row in exit_criteria_report.rows
    }

    rows = tuple(
        _row_for_spec(
            spec,
            source_report=reports[spec.source_id],
            readiness_by_id=readiness_by_id,
            terminal_by_id=terminal_by_id,
            envelope_by_id=envelope_by_id,
            exit_criteria_by_id=exit_criteria_by_id,
        )
        for spec in SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_SPECS
    )
    issues: list[SceneReleaseResidualRatioLedgerIssue] = []
    for row in rows:
        issues.extend(
            SceneReleaseResidualRatioLedgerIssue(
                row.ratio_id,
                issue_id,
                f"Release residual ratio {row.ratio_id} failed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    count_delivery_boundary_alignment_ids = (
        _count_delivery_boundary_alignment_ids(rows=rows)
    )
    issues.extend(_count_delivery_boundary_alignment_issues(rows=rows))
    count_delivery_receipt_alignment_ids = (
        _count_delivery_receipt_alignment_ids(rows=rows)
    )
    issues.extend(_count_delivery_receipt_alignment_issues(rows=rows))
    maturity_l5_blocker_alignment_ids = _maturity_l5_blocker_alignment_ids(
        rows=rows,
        envelope_by_id=envelope_by_id,
        exit_criteria_by_id=exit_criteria_by_id,
    )
    issues.extend(
        _maturity_l5_blocker_alignment_issues(
            rows=rows,
            envelope_by_id=envelope_by_id,
            exit_criteria_by_id=exit_criteria_by_id,
        )
    )
    maturity_l5_blocker_receipt_alignment_ids = (
        _maturity_l5_blocker_receipt_alignment_ids(rows=rows)
    )
    issues.extend(_maturity_l5_blocker_receipt_alignment_issues(rows=rows))
    boundary_scope_alignment_ids = _boundary_scope_alignment_ids(
        rows=rows,
        guarded_report_rows=guarded_report.rows,
    )
    issues.extend(
        _boundary_scope_alignment_issues(
            rows=rows,
            guarded_report_rows=guarded_report.rows,
        )
    )
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneReleaseResidualRatioLedgerAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
        count_delivery_boundary_alignment_ids=count_delivery_boundary_alignment_ids,
        count_delivery_receipt_alignment_ids=count_delivery_receipt_alignment_ids,
        maturity_l5_blocker_alignment_ids=maturity_l5_blocker_alignment_ids,
        maturity_l5_blocker_receipt_alignment_ids=(
            maturity_l5_blocker_receipt_alignment_ids
        ),
        boundary_scope_alignment_ids=boundary_scope_alignment_ids,
    )


def audit_scene_release_residual_ratio_ledger_report(
    report: SceneReleaseResidualRatioLedgerAuditReport | None = None,
) -> tuple[SceneReleaseResidualRatioLedgerIssue, ...]:
    current = report or build_scene_release_residual_ratio_ledger_audit_report()
    return current.issues


def _count_delivery_boundary_rows(
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
) -> dict[str, SceneReleaseResidualRatioLedgerRow]:
    return {
        row.ratio_id: row
        for row in rows
        if row.ratio_id in COUNT_DELIVERY_BOUNDARY_RATIO_IDS
    }


def _count_delivery_boundary_alignment_ids(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
) -> tuple[str, ...]:
    row_by_id = _count_delivery_boundary_rows(rows)
    shared_ids = set(COUNT_DELIVERY_SHARED_BOUNDARY_IDS)
    aligned_ids: list[str] = []
    for ratio_id in COUNT_DELIVERY_BOUNDARY_RATIO_IDS:
        row = row_by_id.get(ratio_id)
        if row is None:
            continue
        for boundary_id in sorted(
            set(row.release_envelope_ids)
            & set(row.retained_gap_exit_criteria_ids)
            & shared_ids
        ):
            aligned_ids.append(f"{ratio_id}:{boundary_id}")
    return tuple(aligned_ids)


def _count_delivery_boundary_alignment_issues(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
) -> tuple[SceneReleaseResidualRatioLedgerIssue, ...]:
    row_by_id = _count_delivery_boundary_rows(rows)
    missing_ratio_ids = tuple(
        ratio_id
        for ratio_id in COUNT_DELIVERY_BOUNDARY_RATIO_IDS
        if ratio_id not in row_by_id
    )
    if missing_ratio_ids:
        return tuple(
            SceneReleaseResidualRatioLedgerIssue(
                ratio_id,
                "missing_count_delivery_boundary_row",
                f"Release residual ratio ledger is missing {ratio_id}.",
            )
            for ratio_id in missing_ratio_ids
        )
    shared_ids = set(COUNT_DELIVERY_SHARED_BOUNDARY_IDS)
    mismatched_ratio_ids = tuple(
        ratio_id
        for ratio_id, row in row_by_id.items()
        if set(row.release_envelope_ids) != shared_ids
        or set(row.retained_gap_exit_criteria_ids) != shared_ids
    )
    if not mismatched_ratio_ids:
        return ()
    return (
        SceneReleaseResidualRatioLedgerIssue(
            "count_delivery_boundary_alignment",
            "count_delivery_boundary_alignment_mismatch",
            (
                "count_profiles and delivery_families must share the same "
                "release envelope and retained-gap exit criteria ID set."
            ),
        ),
    )


def _count_delivery_receipt_alignment_ids(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
) -> tuple[str, ...]:
    row_by_id = _count_delivery_boundary_rows(rows)
    shared_ids = set(COUNT_DELIVERY_SHARED_BOUNDARY_IDS)
    aligned_ids: list[str] = []
    for ratio_id in COUNT_DELIVERY_BOUNDARY_RATIO_IDS:
        row = row_by_id.get(ratio_id)
        if row is None:
            continue
        for boundary_id in sorted(
            set(row.release_envelope_ids)
            & set(row.retained_gap_exit_criteria_ids)
            & set(row.retained_gap_receipt_alignment_ids)
            & shared_ids
        ):
            aligned_ids.append(f"{ratio_id}:{boundary_id}")
    return tuple(aligned_ids)


def _count_delivery_receipt_alignment_issues(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
) -> tuple[SceneReleaseResidualRatioLedgerIssue, ...]:
    row_by_id = _count_delivery_boundary_rows(rows)
    shared_ids = set(COUNT_DELIVERY_SHARED_BOUNDARY_IDS)
    mismatched_ratio_ids = tuple(
        ratio_id
        for ratio_id, row in row_by_id.items()
        if set(row.retained_gap_receipt_alignment_ids) != shared_ids
    )
    if not mismatched_ratio_ids:
        return ()
    return (
        SceneReleaseResidualRatioLedgerIssue(
            "count_delivery_receipt_alignment",
            "count_delivery_receipt_alignment_mismatch",
            (
                "count_profiles and delivery_families must retain external "
                "receipt alignment for the same shared boundary ID set."
            ),
        ),
    )


def _maturity_l5_blocker_row(
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
) -> SceneReleaseResidualRatioLedgerRow | None:
    return next((row for row in rows if row.ratio_id == "maturity_l5_blocked"), None)


def _maturity_l5_blocker_alignment_ids(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
    envelope_by_id: dict[str, object],
    exit_criteria_by_id: dict[str, object],
) -> tuple[str, ...]:
    row = _maturity_l5_blocker_row(rows)
    if row is None:
        return ()
    aligned_ids = (
        set(row.release_envelope_ids)
        & set(row.retained_gap_exit_criteria_ids)
        & set(envelope_by_id)
        & set(exit_criteria_by_id)
    )
    return tuple(sorted(aligned_ids))


def _maturity_l5_blocker_alignment_issues(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
    envelope_by_id: dict[str, object],
    exit_criteria_by_id: dict[str, object],
) -> tuple[SceneReleaseResidualRatioLedgerIssue, ...]:
    row = _maturity_l5_blocker_row(rows)
    if row is None:
        return (
            SceneReleaseResidualRatioLedgerIssue(
                "maturity_l5_blocked",
                "missing_maturity_l5_blocker_row",
                "Release residual ratio ledger is missing maturity_l5_blocked.",
            ),
        )
    envelope_ids = set(envelope_by_id)
    exit_criteria_ids = set(exit_criteria_by_id)
    row_envelope_ids = set(row.release_envelope_ids)
    row_exit_criteria_ids = set(row.retained_gap_exit_criteria_ids)
    if (
        row_envelope_ids == envelope_ids
        and row_exit_criteria_ids == envelope_ids
        and exit_criteria_ids == envelope_ids
    ):
        return ()
    return (
        SceneReleaseResidualRatioLedgerIssue(
            "maturity_l5_blocked",
            "maturity_l5_blocker_alignment_mismatch",
            (
                "maturity_l5_blocked release envelopes, retained-gap exit "
                "criteria, and current envelope/criteria reports must share "
                "the same ID set."
            ),
        ),
    )


def _maturity_l5_blocker_receipt_alignment_ids(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
) -> tuple[str, ...]:
    row = _maturity_l5_blocker_row(rows)
    if row is None:
        return ()
    aligned_ids = (
        set(row.release_envelope_ids)
        & set(row.retained_gap_exit_criteria_ids)
        & set(row.retained_gap_receipt_alignment_ids)
    )
    return tuple(sorted(aligned_ids))


def _maturity_l5_blocker_receipt_alignment_issues(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
) -> tuple[SceneReleaseResidualRatioLedgerIssue, ...]:
    row = _maturity_l5_blocker_row(rows)
    if row is None:
        return ()
    envelope_ids = set(row.release_envelope_ids)
    if set(row.retained_gap_receipt_alignment_ids) == envelope_ids:
        return ()
    return (
        SceneReleaseResidualRatioLedgerIssue(
            "maturity_l5_blocked",
            "maturity_l5_receipt_alignment_mismatch",
            (
                "maturity_l5_blocked release envelopes must retain external "
                "receipt alignment for the same ID set."
            ),
        ),
    )


def _unique_release_envelope_ids(
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                envelope_id
                for row in rows
                for envelope_id in row.release_envelope_ids
            }
        )
    )


def _boundary_scope_rows_by_envelope_id(
    guarded_report_rows: tuple[object, ...],
) -> dict[str, object]:
    rows_by_envelope_id: dict[str, object] = {}
    for row in guarded_report_rows:
        subject_type = str(getattr(row, "subject_type", "") or "")
        subject_id = str(getattr(row, "subject_id", "") or "")
        for gap_id in getattr(row, "remaining_gap_ids", ()) or ():
            rows_by_envelope_id[f"{subject_type}:{subject_id}:{gap_id}"] = row
    return rows_by_envelope_id


def _boundary_scope_alignment_ids(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
    guarded_report_rows: tuple[object, ...],
) -> tuple[str, ...]:
    guarded_by_envelope_id = _boundary_scope_rows_by_envelope_id(
        guarded_report_rows
    )
    aligned_ids: list[str] = []
    for envelope_id in _unique_release_envelope_ids(rows):
        guarded_row = guarded_by_envelope_id.get(envelope_id)
        if guarded_row is None:
            continue
        if (
            getattr(guarded_row, "is_guarded_complete", False)
            and getattr(guarded_row, "boundary_capability_ids", ())
            and getattr(guarded_row, "excluded_core_claims", ())
        ):
            aligned_ids.append(envelope_id)
    return tuple(aligned_ids)


def _boundary_scope_alignment_issues(
    *,
    rows: tuple[SceneReleaseResidualRatioLedgerRow, ...],
    guarded_report_rows: tuple[object, ...],
) -> tuple[SceneReleaseResidualRatioLedgerIssue, ...]:
    release_envelope_ids = set(_unique_release_envelope_ids(rows))
    aligned_ids = set(
        _boundary_scope_alignment_ids(
            rows=rows,
            guarded_report_rows=guarded_report_rows,
        )
    )
    if release_envelope_ids == aligned_ids:
        return ()
    return (
        SceneReleaseResidualRatioLedgerIssue(
            "boundary_scope_alignment",
            "boundary_scope_alignment_mismatch",
            (
                "Every residual release envelope must map to a guarded "
                "boundary completion row with local capability IDs and "
                "excluded core claims."
            ),
        ),
    )


def _row_for_spec(
    spec: SceneReleaseResidualRatioLedgerSpec,
    *,
    source_report: object,
    readiness_by_id: dict[str, object],
    terminal_by_id: dict[str, object],
    envelope_by_id: dict[str, object],
    exit_criteria_by_id: dict[str, object],
) -> SceneReleaseResidualRatioLedgerRow:
    numerator = int(getattr(source_report, spec.numerator_attr))
    denominator = int(getattr(source_report, spec.denominator_attr))
    issue_ids: list[str] = []

    if numerator != spec.expected_numerator or denominator != spec.expected_denominator:
        issue_ids.append("unexpected_release_summary_ratio")
    if numerator == denominator:
        issue_ids.append("ratio_is_no_longer_residual")

    missing_readiness = tuple(
        row_id
        for row_id in spec.readiness_reconciliation_row_ids
        if row_id not in readiness_by_id
    )
    unreconciled = tuple(
        row_id
        for row_id in spec.readiness_reconciliation_row_ids
        if row_id in readiness_by_id
        and not getattr(readiness_by_id[row_id], "is_reconciled", False)
    )
    if missing_readiness or unreconciled:
        issue_ids.append("missing_readiness_reconciliation")

    missing_terminal = tuple(
        exception_id
        for exception_id in spec.terminal_exception_ids
        if exception_id not in terminal_by_id
    )
    ungoverned_terminal = tuple(
        exception_id
        for exception_id in spec.terminal_exception_ids
        if exception_id in terminal_by_id
        and not getattr(terminal_by_id[exception_id], "is_governed", False)
    )
    if missing_terminal or ungoverned_terminal:
        issue_ids.append("missing_terminal_release_exception")

    missing_envelopes = tuple(
        envelope_id
        for envelope_id in spec.release_envelope_ids
        if envelope_id not in envelope_by_id
    )
    unready_envelopes = tuple(
        envelope_id
        for envelope_id in spec.release_envelope_ids
        if envelope_id in envelope_by_id
        and not getattr(envelope_by_id[envelope_id], "is_ready", False)
    )
    if missing_envelopes or unready_envelopes:
        issue_ids.append("missing_release_envelope")

    missing_exit_criteria = tuple(
        criteria_id
        for criteria_id in spec.retained_gap_exit_criteria_ids
        if criteria_id not in exit_criteria_by_id
    )
    unready_exit_criteria = tuple(
        criteria_id
        for criteria_id in spec.retained_gap_exit_criteria_ids
        if criteria_id in exit_criteria_by_id
        and not getattr(
            exit_criteria_by_id[criteria_id],
            "is_release_allowed",
            False,
        )
    )
    if missing_exit_criteria or unready_exit_criteria:
        issue_ids.append("missing_retained_gap_exit_criteria")

    retained_gap_receipt_alignment_ids = tuple(
        criteria_id
        for criteria_id in spec.retained_gap_exit_criteria_ids
        if criteria_id in exit_criteria_by_id
        and _retained_gap_receipts_are_aligned(exit_criteria_by_id[criteria_id])
    )
    if len(retained_gap_receipt_alignment_ids) != len(
        spec.retained_gap_exit_criteria_ids
    ):
        issue_ids.append("missing_retained_gap_receipt_alignment")

    return SceneReleaseResidualRatioLedgerRow(
        ratio_id=spec.ratio_id,
        source_id=spec.source_id,
        observed_numerator=numerator,
        observed_denominator=denominator,
        expected_numerator=spec.expected_numerator,
        expected_denominator=spec.expected_denominator,
        residual_mode=spec.residual_mode,
        status="published_residual_ratio" if not issue_ids else "residual_ratio_gap",
        reason=spec.reason,
        readiness_reconciliation_row_ids=spec.readiness_reconciliation_row_ids,
        terminal_exception_ids=spec.terminal_exception_ids,
        release_envelope_ids=spec.release_envelope_ids,
        retained_gap_exit_criteria_ids=spec.retained_gap_exit_criteria_ids,
        retained_gap_receipt_alignment_ids=retained_gap_receipt_alignment_ids,
        evidence_ids=SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_REQUIRED_EVIDENCE_IDS,
        issue_ids=tuple(dict.fromkeys(issue_ids)),
    )


def _retained_gap_receipts_are_aligned(criteria_row: object) -> bool:
    receipt_ids = set(getattr(criteria_row, "external_receipt_ids", ()) or ())
    exit_signal_ids = set(getattr(criteria_row, "exit_signal_ids", ()) or ())
    return bool(receipt_ids) and receipt_ids.issubset(exit_signal_ids)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneReleaseResidualRatioLedgerSourceEvidence, ...]:
    return tuple(
        SceneReleaseResidualRatioLedgerSourceEvidence(
            source_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
        )
        for result in scan_scene_source_markers(
            project_root,
            SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_SOURCE_MARKERS,
        )
    )


def _source_evidence_issues(
    source_evidence: tuple[SceneReleaseResidualRatioLedgerSourceEvidence, ...],
) -> tuple[SceneReleaseResidualRatioLedgerIssue, ...]:
    return tuple(
        SceneReleaseResidualRatioLedgerIssue(
            evidence.source_id,
            "missing_source_evidence",
            scene_source_marker_issue_message(
                evidence.source_path,
                evidence.missing_markers,
            ),
        )
        for evidence in source_evidence
        if evidence.missing_markers
    )


__all__ = [
    "SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_AUDIT_SOURCE_ID",
    "SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_REQUIRED_EVIDENCE_IDS",
    "SCENE_RELEASE_RESIDUAL_RATIO_LEDGER_SPECS",
    "SceneReleaseResidualRatioLedgerAuditReport",
    "SceneReleaseResidualRatioLedgerIssue",
    "SceneReleaseResidualRatioLedgerRow",
    "SceneReleaseResidualRatioLedgerSourceEvidence",
    "SceneReleaseResidualRatioLedgerSpec",
    "audit_scene_release_residual_ratio_ledger_report",
    "build_scene_release_residual_ratio_ledger_audit_report",
]
