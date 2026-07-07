"""Release-closure ledger audit for the high-level scene matrix.

N2.390 keeps the release-governance work from becoming a pile of separate
green checks.  It records the ordered release stages from guarded boundary
completion through subject continuity, then verifies that every stage is bound
to the same release surfaces users and maintainers rely on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SCENE_RELEASE_CLOSURE_LEDGER_AUDIT_SOURCE_ID = (
    "scene_release_closure_ledger_audit"
)

SCENE_RELEASE_CLOSURE_LEDGER_REQUIRED_EVIDENCE_IDS: tuple[str, ...] = (
    "ordered_stage",
    "upstream_dependency",
    "release_gate_check",
    "dashboard_source",
    "dashboard_card",
    "drilldown_item",
    "summary_projection",
    "export_script",
    "workflow_test",
    "closure_doc",
)

SCENE_RELEASE_CLOSURE_LEDGER_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "release_closure_ledger_registry",
        "src/config/scene_release_closure_ledger_audit.py",
        (
            "SCENE_RELEASE_CLOSURE_LEDGER_REQUIRED_EVIDENCE_IDS",
            "release_closure_ledger",
            "stage_order_count",
            "supplemental_source_markers",
            "supplemental_evidence_ids",
            "requirement_dimension_trace",
            "residual_ratio_receipt_alignment_trace",
            "acceptance_receipt_trace",
        ),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_RELEASE_CLOSURE_LEDGER_AUDIT_SOURCE_ID,
            "release_closure_ledger_ready_count",
            "release_closure_ledger",
        ),
    ),
    (
        "scene_matrix_drilldown",
        "src/config/scene_matrix_drilldown_release_items.py",
        (
            SCENE_RELEASE_CLOSURE_LEDGER_AUDIT_SOURCE_ID,
            "release_closure_ledger",
        ),
    ),
    (
        "summary_projection",
        "src/ui/panels/scene_summary_projection.py",
        (
            "release_closure_ledger_ready_count",
            "Release closure ledger",
        ),
    ),
    (
        "release_gate",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_RELEASE_CLOSURE_LEDGER_AUDIT_SOURCE_ID,
            "scene_release_closure_ledger_ready_count",
        ),
    ),
    (
        "export_script",
        "scripts/export_scene_release_closure_ledger_audit.py",
        (
            "build_scene_release_closure_ledger_audit_report",
            "Stages ready",
            "row.order",
            "row.stage_id",
            "row.evidence_ids",
            "Supplemental",
            "_supplemental_detail",
            "json",
            "markdown",
        ),
    ),
    (
        "workflow",
        ".github/workflows/scene-matrix-release-gate.yml",
        ("tests/test_scene_release_closure_ledger_audit.py",),
    ),
    (
        "release_shell",
        "tests/test_release_shell.py",
        (
            "export_scene_release_closure_ledger_audit.py",
            "test_scene_release_closure_ledger_audit.py",
        ),
    ),
    (
        "n2_390_index",
        "docs/audits/高层场景能力矩阵N2_390发布闭环总账序列索引_2026-06-24.md",
        (
            "N2.390",
            "release_acceptance_certificate",
            "stage_count = 13",
            "upstream_dependency_count = 18",
            "13/13 release ledger",
        ),
    ),
    (
        "n2_394_plan",
        "docs/audits/高层场景能力矩阵N2_394发布验收证书闭环_2026-06-24.md",
        ("N2.394", "release_closure_ledger", "13/13"),
    ),
    (
        "n2_395_requirement_trace_plan",
        "docs/audits/scene_release_acceptance_requirement_trace_N2_395_2026-06-25.md",
        (
            "N2.395",
            "requirement_dimensions=10/10",
            "projection_export_visibility",
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
        "n2_399_projection_trace_plan",
        "docs/audits/scene_release_residual_ratio_projection_trace_N2_399_2026-06-25.md",
        (
            "N2.399",
            "residual_ratio_receipt_alignment_trace",
            "release_residual_ratio_ledger",
        ),
    ),
    (
        "n2_400_acceptance_receipt_plan",
        "docs/audits/scene_release_acceptance_receipt_trace_N2_400_2026-06-25.md",
        (
            "N2.400",
            "acceptance_certificate=14/14",
            "acceptance_evidence=15/15",
        ),
    ),
    (
        "n2_401_acceptance_projection_trace_plan",
        "docs/audits/scene_release_acceptance_projection_trace_N2_401_2026-06-25.md",
        (
            "N2.401",
            "acceptance_receipt_trace",
            "release_acceptance_certificate",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneReleaseClosureLedgerStageSpec:
    stage_id: str
    order: int
    n2_id: str
    source_id: str
    upstream_stage_ids: tuple[str, ...]
    release_gate_check_id: str
    dashboard_card_id: str
    drilldown_id: str
    summary_marker: str
    export_script_path: str
    test_path: str
    closure_doc_path: str
    supplemental_source_markers: tuple[tuple[str, str], ...] = ()
    supplemental_closure_doc_paths: tuple[str, ...] = ()
    supplemental_evidence_ids: tuple[str, ...] = ()


SCENE_RELEASE_CLOSURE_LEDGER_STAGE_SPECS: tuple[
    SceneReleaseClosureLedgerStageSpec, ...
] = (
    SceneReleaseClosureLedgerStageSpec(
        stage_id="boundary_guarded_completion",
        order=1,
        n2_id="N2.380",
        source_id="scene_boundary_guarded_completion_audit",
        upstream_stage_ids=(),
        release_gate_check_id="scene_boundary_guarded_completion_audit",
        dashboard_card_id="boundary_guarded_completion",
        drilldown_id="boundary_guarded_completion",
        summary_marker="boundary guarded",
        export_script_path="scripts/export_scene_boundary_guarded_completion_audit.py",
        test_path="tests/test_scene_boundary_guarded_completion_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_380边界守护完成度闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="residual_warning_governance",
        order=2,
        n2_id="N2.381",
        source_id="scene_residual_warning_governance_audit",
        upstream_stage_ids=("boundary_guarded_completion",),
        release_gate_check_id="scene_residual_warning_governance_audit",
        dashboard_card_id="residual_warning_governance",
        drilldown_id="residual_warning_governance",
        summary_marker="managed warnings",
        export_script_path="scripts/export_scene_residual_warning_governance_audit.py",
        test_path="tests/test_scene_residual_warning_governance_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_381残留Warning治理闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="boundary_readiness_reconciliation",
        order=3,
        n2_id="N2.382",
        source_id="scene_boundary_readiness_reconciliation_audit",
        upstream_stage_ids=(
            "boundary_guarded_completion",
            "residual_warning_governance",
        ),
        release_gate_check_id="scene_boundary_readiness_reconciliation_audit",
        dashboard_card_id="boundary_readiness_reconciliation",
        drilldown_id="boundary_readiness_reconciliation",
        summary_marker="readiness reconciled",
        export_script_path=(
            "scripts/export_scene_boundary_readiness_reconciliation_audit.py"
        ),
        test_path="tests/test_scene_boundary_readiness_reconciliation_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_382边界Readiness读数调和闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="terminal_release_exception",
        order=4,
        n2_id="N2.383",
        source_id="scene_terminal_release_exception_audit",
        upstream_stage_ids=("boundary_readiness_reconciliation",),
        release_gate_check_id="scene_terminal_release_exception_audit",
        dashboard_card_id="terminal_release_exceptions",
        drilldown_id="terminal_release_exception",
        summary_marker="release exceptions",
        export_script_path="scripts/export_scene_terminal_release_exception_audit.py",
        test_path="tests/test_scene_terminal_release_exception_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_383发布例外账本闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="terminal_release_trace_ledger",
        order=5,
        n2_id="N2.384",
        source_id="scene_terminal_release_exception_audit",
        upstream_stage_ids=("terminal_release_exception",),
        release_gate_check_id="scene_terminal_release_exception_audit",
        dashboard_card_id="terminal_release_exceptions",
        drilldown_id="terminal_release_exception",
        summary_marker="release exceptions",
        export_script_path="scripts/export_scene_terminal_release_exception_audit.py",
        test_path="tests/test_scene_terminal_release_exception_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_384发布例外账本行级追踪闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="boundary_subject_release_dossier",
        order=6,
        n2_id="N2.385",
        source_id="scene_boundary_subject_release_dossier_audit",
        upstream_stage_ids=("terminal_release_trace_ledger",),
        release_gate_check_id="scene_boundary_subject_release_dossier_audit",
        dashboard_card_id="boundary_subject_dossiers",
        drilldown_id="boundary_subject_release_dossier",
        summary_marker="boundary dossiers",
        export_script_path=(
            "scripts/export_scene_boundary_subject_release_dossier_audit.py"
        ),
        test_path="tests/test_scene_boundary_subject_release_dossier_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_385边界主体发布证据包闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="non_subject_release_trace_attribution",
        order=7,
        n2_id="N2.386",
        source_id="scene_non_subject_release_trace_attribution_audit",
        upstream_stage_ids=("terminal_release_trace_ledger",),
        release_gate_check_id="scene_non_subject_release_trace_attribution_audit",
        dashboard_card_id="non_subject_release_traces",
        drilldown_id="non_subject_release_trace_attribution",
        summary_marker="non-subject traces",
        export_script_path=(
            "scripts/export_scene_non_subject_release_trace_attribution_audit.py"
        ),
        test_path="tests/test_scene_non_subject_release_trace_attribution_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_386非主体发布Trace归因闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="release_trace_partition_guard",
        order=8,
        n2_id="N2.387",
        source_id="scene_release_trace_partition_guard_audit",
        upstream_stage_ids=(
            "boundary_subject_release_dossier",
            "non_subject_release_trace_attribution",
        ),
        release_gate_check_id="scene_release_trace_partition_guard_audit",
        dashboard_card_id="release_trace_partition",
        drilldown_id="release_trace_partition_guard",
        summary_marker="trace partition",
        export_script_path="scripts/export_scene_release_trace_partition_guard_audit.py",
        test_path="tests/test_scene_release_trace_partition_guard_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_387发布Trace分区守门闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="release_projection_surface_parity",
        order=9,
        n2_id="N2.388",
        source_id="scene_release_projection_surface_parity_audit",
        upstream_stage_ids=("release_trace_partition_guard",),
        release_gate_check_id="scene_release_projection_surface_parity_audit",
        dashboard_card_id="release_projection_surfaces",
        drilldown_id="release_projection_surface_parity",
        summary_marker="release projections",
        export_script_path=(
            "scripts/export_scene_release_projection_surface_parity_audit.py"
        ),
        test_path="tests/test_scene_release_projection_surface_parity_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_388发布投影面一致性闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="boundary_subject_release_continuity",
        order=10,
        n2_id="N2.389",
        source_id="scene_boundary_subject_release_continuity_audit",
        upstream_stage_ids=(
            "boundary_subject_release_dossier",
            "release_projection_surface_parity",
        ),
        release_gate_check_id="scene_boundary_subject_release_continuity_audit",
        dashboard_card_id="boundary_subject_continuity",
        drilldown_id="boundary_subject_release_continuity",
        summary_marker="subject continuity",
        export_script_path=(
            "scripts/export_scene_boundary_subject_release_continuity_audit.py"
        ),
        test_path="tests/test_scene_boundary_subject_release_continuity_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_389边界主体发布链连续性闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="boundary_maturity_release_envelope",
        order=11,
        n2_id="N2.392",
        source_id="scene_boundary_maturity_release_envelope_audit",
        upstream_stage_ids=(
            "boundary_subject_release_continuity",
            "release_projection_surface_parity",
        ),
        release_gate_check_id="scene_boundary_maturity_release_envelope_audit",
        dashboard_card_id="boundary_release_envelopes",
        drilldown_id="boundary_maturity_release_envelope",
        summary_marker="boundary release envelopes",
        export_script_path=(
            "scripts/export_scene_boundary_maturity_release_envelope_audit.py"
        ),
        test_path="tests/test_scene_boundary_maturity_release_envelope_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_392边界成熟度发布保留项证据封套闭环_2026-06-24.md"
        ),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="release_residual_ratio_ledger",
        order=12,
        n2_id="N2.393",
        source_id="scene_release_residual_ratio_ledger_audit",
        upstream_stage_ids=(
            "boundary_readiness_reconciliation",
            "boundary_maturity_release_envelope",
        ),
        release_gate_check_id="scene_release_residual_ratio_ledger_audit",
        dashboard_card_id="release_residual_ratios",
        drilldown_id="release_residual_ratio_ledger",
        summary_marker="release residual ratios",
        export_script_path=(
            "scripts/export_scene_release_residual_ratio_ledger_audit.py"
        ),
        test_path="tests/test_scene_release_residual_ratio_ledger_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_393发布残留比例读数账本闭环_2026-06-24.md"
        ),
        supplemental_source_markers=(
            ("dashboard", "receipt alignments"),
            ("summary_projection", "residual ratio receipts"),
            ("release_gate", "residual_ratio_receipts="),
            ("test", "retained_gap_receipt_alignment_link_count"),
        ),
        supplemental_closure_doc_paths=(
            "docs/audits/scene_release_residual_ratio_receipt_alignment_N2_398_2026-06-25.md",
        ),
        supplemental_evidence_ids=("residual_ratio_receipt_alignment_trace",),
    ),
    SceneReleaseClosureLedgerStageSpec(
        stage_id="release_acceptance_certificate",
        order=13,
        n2_id="N2.394",
        source_id="scene_release_acceptance_certificate_audit",
        upstream_stage_ids=(
            "release_projection_surface_parity",
            "release_residual_ratio_ledger",
        ),
        release_gate_check_id="scene_release_acceptance_certificate_audit",
        dashboard_card_id="release_acceptance_certificate",
        drilldown_id="release_acceptance_certificate",
        summary_marker="release acceptance certificate",
        export_script_path=(
            "scripts/export_scene_release_acceptance_certificate_audit.py"
        ),
        test_path="tests/test_scene_release_acceptance_certificate_audit.py",
        closure_doc_path=(
            "docs/audits/高层场景能力矩阵N2_394发布验收证书闭环_2026-06-24.md"
        ),
        supplemental_source_markers=(
            ("dashboard", "requirement dimensions"),
            ("dashboard", "release_acceptance_certificate_report.source_evidence_count"),
            ("drilldown", "requirement_dimension_trace"),
            ("summary_projection", "requirement dimensions"),
            ("summary_projection", "acceptance evidence"),
            ("release_gate", "requirement_dimensions="),
            ("release_gate", "acceptance_evidence="),
            ("test", "Requirement dimensions ready: 10/10"),
            ("test", "Certificates ready: 14/14"),
            ("test", "acceptance_evidence=15/15"),
        ),
        supplemental_closure_doc_paths=(
            "docs/audits/scene_release_acceptance_requirement_trace_N2_395_2026-06-25.md",
            "docs/audits/scene_release_acceptance_receipt_trace_N2_400_2026-06-25.md",
            "docs/audits/scene_release_acceptance_projection_trace_N2_401_2026-06-25.md",
        ),
        supplemental_evidence_ids=(
            "requirement_dimension_trace",
            "acceptance_receipt_trace",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneReleaseClosureLedgerIssue:
    stage_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "stage_id": self.stage_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseClosureLedgerSourceEvidence:
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
class SceneReleaseClosureLedgerStageRow:
    stage_id: str
    order: int
    n2_id: str
    source_id: str
    upstream_stage_ids: tuple[str, ...]
    release_gate_check_id: str
    dashboard_card_id: str
    drilldown_id: str
    summary_marker: str
    export_script_path: str
    test_path: str
    closure_doc_path: str
    supplemental_source_markers: tuple[tuple[str, str], ...]
    supplemental_closure_doc_paths: tuple[str, ...]
    supplemental_evidence_ids: tuple[str, ...]
    status: str
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status == "ledger_stage_ready"

    def to_payload(self) -> dict[str, object]:
        return {
            "stage_id": self.stage_id,
            "order": self.order,
            "n2_id": self.n2_id,
            "source_id": self.source_id,
            "upstream_stage_ids": list(self.upstream_stage_ids),
            "release_gate_check_id": self.release_gate_check_id,
            "dashboard_card_id": self.dashboard_card_id,
            "drilldown_id": self.drilldown_id,
            "summary_marker": self.summary_marker,
            "export_script_path": self.export_script_path,
            "test_path": self.test_path,
            "closure_doc_path": self.closure_doc_path,
            "supplemental_source_markers": [
                {"source": source, "marker": marker}
                for source, marker in self.supplemental_source_markers
            ],
            "supplemental_closure_doc_paths": list(
                self.supplemental_closure_doc_paths
            ),
            "supplemental_evidence_ids": list(self.supplemental_evidence_ids),
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneReleaseClosureLedgerAuditReport:
    rows: tuple[SceneReleaseClosureLedgerStageRow, ...]
    issues: tuple[SceneReleaseClosureLedgerIssue, ...]
    source_evidence: tuple[SceneReleaseClosureLedgerSourceEvidence, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def stage_count(self) -> int:
        return len(self.rows)

    @property
    def ready_stage_count(self) -> int:
        return sum(1 for row in self.rows if row.is_ready)

    @property
    def stage_order_count(self) -> int:
        return sum(
            1
            for index, row in enumerate(self.rows, start=1)
            if row.order == index and "invalid_stage_order" not in row.issue_ids
        )

    @property
    def upstream_dependency_count(self) -> int:
        return sum(len(row.upstream_stage_ids) for row in self.rows)

    @property
    def upstream_dependency_ready_count(self) -> int:
        return sum(
            len(row.upstream_stage_ids)
            for row in self.rows
            if "missing_upstream_stage" not in row.issue_ids
            and "upstream_stage_order_violation" not in row.issue_ids
        )

    @property
    def release_gate_check_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_release_gate_check" not in row.issue_ids
        )

    @property
    def dashboard_source_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_dashboard_source" not in row.issue_ids
        )

    @property
    def dashboard_card_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_dashboard_card" not in row.issue_ids
        )

    @property
    def drilldown_item_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_drilldown_item" not in row.issue_ids
        )

    @property
    def summary_projection_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_summary_projection" not in row.issue_ids
        )

    @property
    def export_script_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_export_script" not in row.issue_ids
        )

    @property
    def workflow_test_count(self) -> int:
        return sum(
            1 for row in self.rows if "missing_workflow_test" not in row.issue_ids
        )

    @property
    def closure_doc_count(self) -> int:
        return sum(1 for row in self.rows if "missing_closure_doc" not in row.issue_ids)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_RELEASE_CLOSURE_LEDGER_AUDIT_SOURCE_ID,
            "required_evidence_ids": list(
                SCENE_RELEASE_CLOSURE_LEDGER_REQUIRED_EVIDENCE_IDS
            ),
            "counts": {
                "stage_count": self.stage_count,
                "ready_stage_count": self.ready_stage_count,
                "stage_order_count": self.stage_order_count,
                "upstream_dependency_count": self.upstream_dependency_count,
                "upstream_dependency_ready_count": (
                    self.upstream_dependency_ready_count
                ),
                "release_gate_check_count": self.release_gate_check_count,
                "dashboard_source_count": self.dashboard_source_count,
                "dashboard_card_count": self.dashboard_card_count,
                "drilldown_item_count": self.drilldown_item_count,
                "summary_projection_count": self.summary_projection_count,
                "export_script_count": self.export_script_count,
                "workflow_test_count": self.workflow_test_count,
                "closure_doc_count": self.closure_doc_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_release_closure_ledger_audit_report(
    *,
    project_root: Path | str | None = None,
) -> SceneReleaseClosureLedgerAuditReport:
    root = Path(project_root) if project_root is not None else Path.cwd()
    source_texts = _source_texts(root)
    specs_by_id = {
        spec.stage_id: spec for spec in SCENE_RELEASE_CLOSURE_LEDGER_STAGE_SPECS
    }
    rows = tuple(
        _row_for_spec(
            spec,
            root=root,
            source_texts=source_texts,
            specs_by_id=specs_by_id,
        )
        for spec in SCENE_RELEASE_CLOSURE_LEDGER_STAGE_SPECS
    )
    issues: list[SceneReleaseClosureLedgerIssue] = []
    for row in rows:
        issues.extend(
            SceneReleaseClosureLedgerIssue(
                row.stage_id,
                issue_id,
                f"Release closure ledger stage {row.stage_id} failed: {issue_id}.",
            )
            for issue_id in row.issue_ids
        )
    source_evidence = _source_evidence(root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneReleaseClosureLedgerAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
    )


def audit_scene_release_closure_ledger_report(
    report: SceneReleaseClosureLedgerAuditReport | None = None,
) -> tuple[SceneReleaseClosureLedgerIssue, ...]:
    current = report or build_scene_release_closure_ledger_audit_report()
    return current.issues


def _row_for_spec(
    spec: SceneReleaseClosureLedgerStageSpec,
    *,
    root: Path,
    source_texts: dict[str, str],
    specs_by_id: dict[str, SceneReleaseClosureLedgerStageSpec],
) -> SceneReleaseClosureLedgerStageRow:
    issue_ids: list[str] = []
    if spec.order < 1 or spec.order != _expected_order(spec.stage_id):
        issue_ids.append("invalid_stage_order")
    for upstream_stage_id in spec.upstream_stage_ids:
        upstream_spec = specs_by_id.get(upstream_stage_id)
        if upstream_spec is None:
            issue_ids.append("missing_upstream_stage")
        elif upstream_spec.order >= spec.order:
            issue_ids.append("upstream_stage_order_violation")
    if spec.source_id not in source_texts["dashboard"]:
        issue_ids.append("missing_dashboard_source")
    if spec.dashboard_card_id not in source_texts["dashboard"]:
        issue_ids.append("missing_dashboard_card")
    if spec.drilldown_id not in source_texts["drilldown"]:
        issue_ids.append("missing_drilldown_item")
    if spec.summary_marker not in source_texts["summary_projection"]:
        issue_ids.append("missing_summary_projection")
    if spec.release_gate_check_id not in source_texts["release_gate"]:
        issue_ids.append("missing_release_gate_check")
    if not _exists(root, spec.export_script_path):
        issue_ids.append("missing_export_script")
    if not _exists(root, spec.test_path):
        issue_ids.append("missing_test_file")
    if spec.test_path not in source_texts["workflow"]:
        issue_ids.append("missing_workflow_test")
    if not _exists(root, spec.closure_doc_path):
        issue_ids.append("missing_closure_doc")
    supplemental_source_texts = {
        **source_texts,
        "test": _read_text(root / spec.test_path),
    }
    for source_id, marker in spec.supplemental_source_markers:
        if marker not in supplemental_source_texts.get(source_id, ""):
            issue_ids.append(f"missing_supplemental_marker.{source_id}")
    for closure_doc_path in spec.supplemental_closure_doc_paths:
        if not _exists(root, closure_doc_path):
            issue_ids.append("missing_supplemental_closure_doc")
    return SceneReleaseClosureLedgerStageRow(
        stage_id=spec.stage_id,
        order=spec.order,
        n2_id=spec.n2_id,
        source_id=spec.source_id,
        upstream_stage_ids=spec.upstream_stage_ids,
        release_gate_check_id=spec.release_gate_check_id,
        dashboard_card_id=spec.dashboard_card_id,
        drilldown_id=spec.drilldown_id,
        summary_marker=spec.summary_marker,
        export_script_path=spec.export_script_path,
        test_path=spec.test_path,
        closure_doc_path=spec.closure_doc_path,
        supplemental_source_markers=spec.supplemental_source_markers,
        supplemental_closure_doc_paths=spec.supplemental_closure_doc_paths,
        supplemental_evidence_ids=spec.supplemental_evidence_ids,
        status="ledger_stage_ready" if not issue_ids else "ledger_stage_gap",
        evidence_ids=(
            SCENE_RELEASE_CLOSURE_LEDGER_REQUIRED_EVIDENCE_IDS
            + spec.supplemental_evidence_ids
        ),
        issue_ids=tuple(dict.fromkeys(issue_ids)),
    )


def _expected_order(stage_id: str) -> int:
    for index, spec in enumerate(SCENE_RELEASE_CLOSURE_LEDGER_STAGE_SPECS, start=1):
        if spec.stage_id == stage_id:
            return index
    return -1


def _source_texts(root: Path) -> dict[str, str]:
    return {
        "dashboard": _read_text(root / "src/config/scene_matrix_dashboard.py"),
        "drilldown": "\n".join(
            (
                _read_text(root / "src/config/scene_matrix_drilldown.py"),
                _read_text(root / "src/config/scene_matrix_drilldown_items.py"),
                _read_text(
                    root / "src/config/scene_matrix_drilldown_release_items.py"
                ),
            )
        ),
        "summary_projection": _read_text(
            root / "src/ui/panels/scene_summary_projection.py"
        ),
        "release_gate": _read_text(root / "scripts/verify_scene_matrix_release_gate.py"),
        "workflow": _read_text(
            root / ".github/workflows/scene-matrix-release-gate.yml"
        ),
    }


def _source_evidence(
    root: Path,
) -> tuple[SceneReleaseClosureLedgerSourceEvidence, ...]:
    evidence: list[SceneReleaseClosureLedgerSourceEvidence] = []
    for source_id, source_path, markers in SCENE_RELEASE_CLOSURE_LEDGER_SOURCE_MARKERS:
        text = _read_text(root / source_path)
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneReleaseClosureLedgerSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneReleaseClosureLedgerSourceEvidence, ...],
) -> tuple[SceneReleaseClosureLedgerIssue, ...]:
    return tuple(
        SceneReleaseClosureLedgerIssue(
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


def _exists(root: Path, path: str) -> bool:
    return (root / path).exists()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


__all__ = [
    "SCENE_RELEASE_CLOSURE_LEDGER_AUDIT_SOURCE_ID",
    "SCENE_RELEASE_CLOSURE_LEDGER_REQUIRED_EVIDENCE_IDS",
    "SCENE_RELEASE_CLOSURE_LEDGER_STAGE_SPECS",
    "SceneReleaseClosureLedgerAuditReport",
    "SceneReleaseClosureLedgerIssue",
    "SceneReleaseClosureLedgerSourceEvidence",
    "SceneReleaseClosureLedgerStageRow",
    "SceneReleaseClosureLedgerStageSpec",
    "audit_scene_release_closure_ledger_report",
    "build_scene_release_closure_ledger_audit_report",
]
