"""Report and artifact drilldown productization audit for the scene matrix.

N2.180 sits after DeliveryPreset execution.  The delivery audits answer
whether outputs can be produced; this audit answers whether generated outputs,
reports, intermediates, material packages, sample manifests, and output-target
warnings are normalized into a browsable user-facing artifact chain.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    list_scene_coverage_packs,
)
from src.config.scene_source_evidence import scan_scene_source_markers


SCENE_REPORT_ARTIFACT_DRILLDOWN_AUDIT_ID = (
    "scene_report_artifact_drilldown_audit"
)


@dataclass(frozen=True, slots=True)
class SceneReportArtifactDrilldownEvidenceSpec:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    evidence_layer: str


@dataclass(frozen=True, slots=True)
class SceneReportArtifactDrilldownSpec:
    drilldown_channel_id: str
    label: str
    coverage_selector: str
    artifact_kind_ids: tuple[str, ...]
    runtime_surface_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    report_surface_ids: tuple[str, ...]
    repair_target_types: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence: tuple[SceneReportArtifactDrilldownEvidenceSpec, ...]


@dataclass(frozen=True, slots=True)
class SceneReportArtifactDrilldownIssue:
    drilldown_channel_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "drilldown_channel_id": self.drilldown_channel_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneReportArtifactDrilldownEvidence:
    drilldown_channel_id: str
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]
    evidence_layer: str

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "drilldown_channel_id": self.drilldown_channel_id,
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "evidence_layer": self.evidence_layer,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneReportArtifactDrilldownRow:
    drilldown_channel_id: str
    label: str
    coverage_selector: str
    pack_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    artifact_kind_ids: tuple[str, ...]
    runtime_surface_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    report_surface_ids: tuple[str, ...]
    repair_target_types: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "drilldown_channel_id": self.drilldown_channel_id,
            "label": self.label,
            "coverage_selector": self.coverage_selector,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "artifact_kind_ids": list(self.artifact_kind_ids),
            "runtime_surface_ids": list(self.runtime_surface_ids),
            "ui_surface_ids": list(self.ui_surface_ids),
            "report_surface_ids": list(self.report_surface_ids),
            "repair_target_types": list(self.repair_target_types),
            "test_ids": list(self.test_ids),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneReportArtifactDrilldownAuditReport:
    rows: tuple[SceneReportArtifactDrilldownRow, ...]
    issues: tuple[SceneReportArtifactDrilldownIssue, ...]
    source_evidence: tuple[SceneReportArtifactDrilldownEvidence, ...]
    drilldown_channel_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def drilldown_channel_count(self) -> int:
        return len(self.rows)

    @property
    def ready_drilldown_channel_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def artifact_kind_count(self) -> int:
        return len(
            _unique_values(
                artifact_kind
                for row in self.rows
                for artifact_kind in row.artifact_kind_ids
            )
        )

    @property
    def runtime_surface_count(self) -> int:
        return len(
            _unique_values(
                surface for row in self.rows for surface in row.runtime_surface_ids
            )
        )

    @property
    def ui_surface_count(self) -> int:
        return len(
            _unique_values(surface for row in self.rows for surface in row.ui_surface_ids)
        )

    @property
    def report_surface_count(self) -> int:
        return len(
            _unique_values(
                surface for row in self.rows for surface in row.report_surface_ids
            )
        )

    @property
    def repair_target_type_count(self) -> int:
        return len(
            _unique_values(
                target for row in self.rows for target in row.repair_target_types
            )
        )

    @property
    def test_evidence_count(self) -> int:
        return len(_unique_values(test for row in self.rows for test in row.test_ids))

    @property
    def covered_pack_count(self) -> int:
        return len(_unique_values(pack for row in self.rows for pack in row.pack_ids))

    @property
    def covered_family_count(self) -> int:
        return len(
            _unique_values(family for row in self.rows for family in row.family_ids)
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def source_evidence_count(self) -> int:
        return len(self.source_evidence)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_REPORT_ARTIFACT_DRILLDOWN_AUDIT_ID,
            "drilldown_channel_filter": self.drilldown_channel_filter,
            "counts": {
                "drilldown_channel_count": self.drilldown_channel_count,
                "ready_drilldown_channel_count": (
                    self.ready_drilldown_channel_count
                ),
                "artifact_kind_count": self.artifact_kind_count,
                "runtime_surface_count": self.runtime_surface_count,
                "ui_surface_count": self.ui_surface_count,
                "report_surface_count": self.report_surface_count,
                "repair_target_type_count": self.repair_target_type_count,
                "test_evidence_count": self.test_evidence_count,
                "covered_pack_count": self.covered_pack_count,
                "covered_family_count": self.covered_family_count,
                "issue_count": self.issue_count,
                "source_evidence_count": self.source_evidence_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def _evidence(
    evidence_id: str,
    source_path: str,
    evidence_layer: str,
    *markers: str,
) -> SceneReportArtifactDrilldownEvidenceSpec:
    return SceneReportArtifactDrilldownEvidenceSpec(
        evidence_id=evidence_id,
        source_path=source_path,
        evidence_layer=evidence_layer,
        markers=tuple(markers),
    )


def _spec(
    drilldown_channel_id: str,
    label: str,
    coverage_selector: str,
    artifact_kind_ids: tuple[str, ...],
    runtime_surface_ids: tuple[str, ...],
    ui_surface_ids: tuple[str, ...],
    report_surface_ids: tuple[str, ...],
    repair_target_types: tuple[str, ...],
    test_ids: tuple[str, ...],
    evidence: tuple[SceneReportArtifactDrilldownEvidenceSpec, ...],
) -> SceneReportArtifactDrilldownSpec:
    return SceneReportArtifactDrilldownSpec(
        drilldown_channel_id=drilldown_channel_id,
        label=label,
        coverage_selector=coverage_selector,
        artifact_kind_ids=artifact_kind_ids,
        runtime_surface_ids=runtime_surface_ids,
        ui_surface_ids=ui_surface_ids,
        report_surface_ids=report_surface_ids,
        repair_target_types=repair_target_types,
        test_ids=test_ids,
        evidence=evidence,
    )


N2_180_REPORT_ARTIFACT_DRILLDOWN_SPECS: tuple[
    SceneReportArtifactDrilldownSpec, ...
] = (
    _spec(
        "artifact_state_model",
        "Artifact state model",
        "delivery_artifact",
        (
            "output",
            "compare",
            "report",
            "intermediate",
            "material_manifest",
            "material_package",
            "material_package_report",
            "scene_sample_manifest",
        ),
        ("ArtifactItemState", "ExecutionResultState", "RecentRunState"),
        ("RecentRunPanel.artifact_items", "QuickExecutionDetail.artifact_log"),
        ("artifact_label", "report_paths"),
        (),
        ("test_execution_adapter_preserves_delivery_artifact_paths",),
        (
            _evidence(
                "state.artifact_item",
                "src/ui/panels/workbench/state.py",
                "runtime",
                "class ArtifactItemState",
                "artifact_items",
                "scene_sample_manifest_paths",
            ),
            _evidence(
                "adapter.artifact_items",
                "src/ui/adapters/workbench_execution_adapter.py",
                "runtime",
                "artifact_items=_build_artifact_items",
                "artifact_label=_artifact_browser_label",
                "material_package_paths",
            ),
            _evidence(
                "adapter.artifact_builder",
                "src/ui/adapters/workbench_artifact_items.py",
                "runtime",
                "def _build_artifact_items",
                "def _artifact_browser_label",
                "material_package_report",
                "ArtifactItemState",
            ),
            _evidence(
                "adapter.material_package_artifacts",
                "src/ui/adapters/workbench_artifact_items.py",
                "runtime",
                "material_package_report",
                "Remote Asset Cache",
            ),
            _evidence(
                "test.artifact_state",
                "tests/test_workbench_execution_center.py",
                "test",
                "def test_execution_adapter_preserves_delivery_artifact_paths",
                "assert [item.kind for item in state.artifact_items] ==",
            ),
        ),
    ),
    _spec(
        "runtime_delivery_artifact_maps",
        "Runtime delivery artifact maps",
        "delivery_artifact",
        ("output", "compare", "report", "intermediate", "material_manifest", "material_package"),
        (
            "WorkbenchProductionRunner",
            "_write_compare_docx_artifacts",
            "write_structured_intermediates",
            "write_material_manifest",
            "write_material_package_artifacts",
        ),
        ("QuickExecutionDetail.report_paths",),
        ("output_paths", "compare_paths", "intermediate_paths", "material_manifest_paths", "material_package_paths"),
        (),
        (
            "test_workbench_runner_uses_delivery_preset_artifacts_for_outputs_and_reports",
            "test_workbench_runner_writes_technical_long_document_delivery_package",
            "test_workbench_runner_writes_material_package_for_failed_delivery_run",
        ),
        (
            _evidence(
                "runtime.delivery_artifacts",
                "src/services/production_runtime/delivery_reporting.py",
                "runtime",
                "_write_compare_docx_artifacts",
                "write_structured_intermediates",
                "write_material_manifest",
                "write_material_package_artifacts",
            ),
            _evidence(
                "runtime.payload_artifacts",
                "src/services/execution_result_contract.py",
                "runtime",
                'result_value(result, "report_paths")',
                '"material_manifest_paths",',
                '"material_package_paths",',
            ),
            _evidence(
                "test.delivery_artifacts",
                "tests/test_output_runtime_semantics.py",
                "test",
                "def test_workbench_runner_uses_delivery_preset_artifacts_for_outputs_and_reports",
                'assert sorted(Path(path).name for path in payload["report_paths"])',
            ),
        ),
    ),
    _spec(
        "artifact_grouping_and_report_inference",
        "Artifact grouping and report inference",
        "delivery_artifact",
        ("output", "compare", "report", "intermediate"),
        ("_infer_report_group", "_extend_report_items", "_known_artifact_groups"),
        ("RecentRunPanel group headers",),
        ("group_id", "group_label"),
        (),
        ("test_execution_adapter_preserves_delivery_artifact_paths",),
        (
            _evidence(
                "runtime.grouping",
                "src/ui/adapters/workbench_artifact_items.py",
                "runtime",
                "def _infer_report_group",
                "def _extend_report_items",
                "known_groups",
            ),
            _evidence(
                "test.grouping",
                "tests/test_workbench_execution_center.py",
                "test",
                'assert state.artifact_items[3].group_id == "review"',
                "source_review_changes.md",
            ),
        ),
    ),
    _spec(
        "recent_run_artifact_browser",
        "Recent run artifact browser",
        "delivery_artifact",
        (
            "output",
            "compare",
            "report",
            "intermediate",
            "material_manifest",
            "material_package",
            "material_package_report",
        ),
        ("RecentRunState.artifact_items",),
        (
            "RecentRunPanel._set_artifact_items",
            "RecentRunPanel._build_artifact_row",
            "QDesktopServices.openUrl",
        ),
        ("artifact_label",),
        (),
        (
            "test_recent_run_panel_renders_delivery_artifact_labels",
            "test_recent_run_panel_expands_scene_sample_manifest_artifacts_and_request_cells",
            "test_recent_run_panel_labels_material_package_report_anchor",
        ),
        (
            _evidence(
                "ui.recent_run_browser",
                "src/ui/panels/workbench/recent_run_panel.py",
                "ui",
                "def _set_artifact_items",
                "def _build_artifact_row",
                "QDesktopServices.openUrl",
                "material_package_report",
            ),
            _evidence(
                "test.recent_run_browser",
                "tests/test_recent_run_panel.py",
                "test",
                "def test_recent_run_panel_renders_delivery_artifact_labels",
                "def test_recent_run_panel_expands_scene_sample_manifest_artifacts_and_request_cells",
                "def test_recent_run_panel_labels_material_package_report_anchor",
            ),
        ),
    ),
    _spec(
        "question_figure_transaction_task_report_drilldown",
        "Question-figure transaction task report drilldown",
        "delivery_artifact",
        (
            "question_figure_batch_apply_transaction_report",
            "question_figure_batch_apply_transaction_task_summary",
        ),
        (
            "question_figure_transaction_task_issue_items",
            "_extend_question_figure_repair_queue_item",
        ),
        (
            "WorkbenchPanel._open_issue_repair_target",
            "RecentRunPanel._open_artifact_file",
        ),
        (
            "report_path",
            "artifact_path",
            "question-figure-batch-apply-transaction-task-summary",
        ),
        ("question_figure_batch_apply_transaction_task_summary",),
        (
            "test_question_figure_transaction_task_issue_items_route_active_task_to_report",
            "test_workbench_panel_routes_issue_repair_targets_to_existing_surfaces",
            "test_recent_run_panel_labels_question_figure_transaction_task_anchors",
        ),
        (
            _evidence(
                "runtime.question_figure_transaction_task_issue",
                "src/ui/adapters/workbench_execution_adapter.py",
                "runtime",
                "def question_figure_transaction_task_issue_items",
                "question_figure_batch_apply_transaction_task_summary",
                "question-figure-batch-apply-transaction-task-summary",
            ),
            _evidence(
                "ui.question_figure_transaction_task_action",
                "src/ui/adapters/workbench_product_issue_navigation.py",
                "ui",
                'if normalized_type == "question_figure_batch_apply_transaction_task_summary":',
                'action_kind="transaction_artifact"',
                'feature_card_id="quick_execute"',
            ),
            _evidence(
                "ui.question_figure_transaction_task_artifact",
                "src/ui/panels/workbench/recent_run_panel.py",
                "ui",
                "def _open_artifact_file",
                "question_figure_batch_apply_transaction_report",
                "question_figure_batch_apply_transaction_task_summary",
            ),
            _evidence(
                "test.question_figure_transaction_task_drilldown",
                "tests/test_workbench_detail_architecture.py",
                "test",
                "def test_workbench_panel_routes_issue_repair_targets_to_existing_surfaces",
                "opened_artifacts[-1]",
                "question-figure-batch-apply-transaction-task-summary",
            ),
            _evidence(
                "test.question_figure_transaction_task_anchor_labels",
                "tests/test_recent_run_panel.py",
                "test",
                "def test_recent_run_panel_labels_question_figure_transaction_task_anchors",
                "question_figure_batch_apply_transaction_task_summary",
            ),
        ),
    ),
    _spec(
        "quick_execution_artifact_log",
        "Quick execution artifact log",
        "delivery_artifact",
        ("output", "compare", "report", "intermediate", "material_manifest", "material_package"),
        ("ExecutionResultState",),
        ("QuickExecutionDetail execution log",),
        ("report_paths", "artifact_items"),
        (),
        ("test_quick_execution_detail_logs_delivery_artifacts",),
        (
            _evidence(
                "ui.quick_result_presenter_log",
                "src/ui/panels/workbench/quick_execution_result_presenter.py",
                "ui_presenter",
                "def _append_artifact_log_entries",
                "workbench_artifact_display_items(",
                "state.output_paths",
                "(state.material_package_paths, \"资料包\", False)",
                "delivery_preset_labels=True",
                "state.report_paths",
            ),
            _evidence(
                "test.quick_detail_log",
                "tests/test_quick_execution_detail_architecture.py",
                "test",
                "def test_quick_execution_detail_logs_delivery_artifacts",
                "material_package.zip",
            ),
        ),
    ),
    _spec(
        "report_writer_artifact_evidence",
        "Report writer artifact evidence",
        "delivery_artifact",
        ("report", "material_manifest", "material_package", "intermediate"),
        ("_extract_journal_submission_package", "_extract_scene_sample_fixture_manifest"),
        ("Markdown report", "JSON report"),
        ("journal_submission_package", "scene_sample_fixtures", "control_contracts"),
        (),
        (
            "test_report_writer_emits_scene_sample_fixture_manifest_evidence",
            "test_workbench_runner_writes_material_package_for_failed_delivery_run",
        ),
        (
            _evidence(
                "report.delivery_package",
                "src/product_report_writer.py",
                "report",
                "def _extract_journal_submission_package",
                "material_artifact_enabled_count",
                "artifact_parts.append",
            ),
            _evidence(
                "report.sample_manifest",
                "src/report_writer.py",
                "report",
                "def _extract_scene_sample_fixture_manifest",
                "def _format_scene_sample_fixture_manifest_markdown",
                "artifact_count",
            ),
            _evidence(
                "test.report_manifest",
                "tests/test_scene_sample_fixture_regression.py",
                "test",
                "def test_report_writer_emits_scene_sample_fixture_manifest_evidence",
                "artifact_count",
            ),
        ),
    ),
    _spec(
        "sample_manifest_child_drilldown",
        "Sample manifest child drilldown",
        "sample_fixture_artifact",
        ("scene_sample_manifest", "scene_sample_docx", "request_cell_report"),
        (
            "_expand_scene_sample_manifest_items",
            "_scene_sample_fixture_artifact_items",
            "_scene_request_cell_artifact_items",
        ),
        ("RecentRunPanel sample manifest drilldown",),
        ("fixture_manifest", "request_cell_report_path"),
        ("sample_fixture",),
        (
            "test_execution_adapter_exposes_scene_sample_manifest_artifact",
            "test_recent_run_panel_expands_scene_sample_manifest_artifacts_and_request_cells",
        ),
        (
            _evidence(
                "ui.sample_manifest_children",
                "src/ui/panels/workbench/recent_run_panel.py",
                "ui",
                "def _expand_scene_sample_manifest_items",
                "def _scene_sample_fixture_artifact_items",
                "def _scene_request_cell_artifact_items",
            ),
            _evidence(
                "test.sample_manifest_children",
                "tests/test_recent_run_panel.py",
                "test",
                "def test_recent_run_panel_expands_scene_sample_manifest_artifacts_and_request_cells",
                'kinds.count("scene_sample_manifest")',
            ),
        ),
    ),
    _spec(
        "output_target_warning_repair",
        "Output-target warning repair route",
        "delivery_artifact",
        ("planned_output", "output"),
        ("output_target_preflight_issue_items", "_planned_output_preflight_items"),
        ("Execution history result detail", "ScenePanel scene rules generated-result card"),
        ("output_target_preflight", "output_target.warning"),
        ("output_target",),
        (
            "test_output_target_preflight_items_preserve_result_repair_targets",
            "test_workbench_panel_routes_issue_repair_targets_to_existing_surfaces",
        ),
        (
            _evidence(
                "runtime.output_target_issue",
                "src/ui/adapters/workbench_execution_adapter.py",
                "runtime",
                "def output_target_preflight_issue_items",
                'repair_target_type="output_target"',
                "_planned_output_preflight_items",
            ),
            _evidence(
                "runtime.output_target_preflight_parser",
                "src/ui/adapters/workbench_artifact_items.py",
                "runtime",
                "def _planned_output_preflight_items",
                "def _split_issue_detail_text",
                "def _output_preflight_issue_detail",
            ),
            _evidence(
                "ui.output_target_route",
                "src/ui/adapters/workbench_product_issue_navigation.py",
                "ui",
                '"output_target": "scn_rules"',
                'action_kind="scene_panel"',
                "card_id=SCENE_TARGET_CARD_MAP[normalized_type]",
            ),
            _evidence(
                "test.output_target_issue",
                "tests/test_workbench_execution_center.py",
                "test",
                "def test_output_target_preflight_items_preserve_result_repair_targets",
                'repair_target_type == "output_target"',
            ),
        ),
    ),
    _spec(
        "matrix_browse_report_artifact_drilldown",
        "Scene matrix can browse report and artifact drilldown readiness",
        "delivery_artifact",
        ("output", "compare", "report", "intermediate", "material_manifest", "material_package", "scene_sample_manifest"),
        (
            "scene_report_artifact_drilldown_audit",
            "SceneMatrixDashboard.report_artifact_drilldown",
            "SceneMatrixDrilldown.report_artifact_drilldown",
        ),
        ("Dashboard card", "Drilldown item", "Summary projection"),
        ("release_gate.counts",),
        ("output_target", "sample_fixture"),
        (
            "test_scene_report_artifact_drilldown_audit_locks_n2_180_channels",
            "test_release_gate_includes_scene_report_artifact_drilldown_audit",
        ),
        (
            _evidence(
                "dashboard.report_artifact_drilldown",
                "src/config/scene_matrix_dashboard.py",
                "ui",
                "report_artifact_drilldown",
                "scene_report_artifact_drilldown_audit",
            ),
            _evidence(
                "drilldown.report_artifact_drilldown",
                "src/config/scene_matrix_drilldown_items.py",
                "ui",
                "report_artifact_drilldown",
                "scene_report_artifact_drilldown_audit",
            ),
            _evidence(
                "summary.report_artifact_drilldown",
                "scripts/verify_scene_matrix_release_gate.py",
                "release_gate_summary",
                "report_artifact_drilldown_ready_channel_count",
                "report/artifact drilldown",
            ),
            _evidence(
                "test.matrix_report_artifact_drilldown",
                "tests/test_scene_report_artifact_drilldown_audit.py",
                "test",
                "def test_scene_report_artifact_drilldown_audit_locks_n2_180_channels",
                "def test_release_gate_includes_scene_report_artifact_drilldown_audit",
            ),
        ),
    ),
)


def build_scene_report_artifact_drilldown_audit_report(
    *,
    drilldown_channel_id: str = "",
    project_root: Path | str | None = None,
) -> SceneReportArtifactDrilldownAuditReport:
    normalized_channel = str(drilldown_channel_id or "").strip()
    specs = tuple(
        spec
        for spec in N2_180_REPORT_ARTIFACT_DRILLDOWN_SPECS
        if not normalized_channel or spec.drilldown_channel_id == normalized_channel
    )
    packs = list_scene_coverage_packs()
    source_evidence = _source_evidence(specs, project_root)
    evidence_by_channel = _evidence_by_channel(source_evidence)
    rows = tuple(
        _row(spec, packs, evidence_by_channel.get(spec.drilldown_channel_id, ()))
        for spec in specs
    )
    issues = audit_scene_report_artifact_drilldown_report(
        SceneReportArtifactDrilldownAuditReport(
            rows=rows,
            issues=(),
            source_evidence=source_evidence,
            drilldown_channel_filter=normalized_channel,
        )
    )
    return SceneReportArtifactDrilldownAuditReport(
        rows=rows,
        issues=issues,
        source_evidence=source_evidence,
        drilldown_channel_filter=normalized_channel,
    )


def audit_scene_report_artifact_drilldown_report(
    report: SceneReportArtifactDrilldownAuditReport,
) -> tuple[SceneReportArtifactDrilldownIssue, ...]:
    issues: list[SceneReportArtifactDrilldownIssue] = []
    seen: set[tuple[str, str, str]] = set()
    for row in report.rows:
        for issue_id in row.issue_ids:
            _append_issue(
                issues,
                seen,
                row.drilldown_channel_id,
                issue_id,
                f"Report/artifact drilldown channel has unresolved issue: {issue_id}.",
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            _append_issue(
                issues,
                seen,
                evidence.drilldown_channel_id,
                f"missing_source_evidence.{evidence.evidence_id}",
                f"Missing source markers: {', '.join(evidence.missing_markers)}",
            )
    return tuple(issues)


def _append_issue(
    issues: list[SceneReportArtifactDrilldownIssue],
    seen: set[tuple[str, str, str]],
    drilldown_channel_id: str,
    kind: str,
    message: str,
) -> None:
    key = (drilldown_channel_id, kind, message)
    if key in seen:
        return
    seen.add(key)
    issues.append(
        SceneReportArtifactDrilldownIssue(
            drilldown_channel_id=drilldown_channel_id,
            kind=kind,
            message=message,
        )
    )


def _row(
    spec: SceneReportArtifactDrilldownSpec,
    packs: tuple[SceneCoveragePack, ...],
    evidence: tuple[SceneReportArtifactDrilldownEvidence, ...],
) -> SceneReportArtifactDrilldownRow:
    pack_ids, family_ids = _coverage_links(spec.coverage_selector, packs)
    issue_ids: list[str] = []
    if not evidence:
        issue_ids.append("missing_evidence_specs")
    for item in evidence:
        if item.status != "ready":
            issue_ids.append(f"missing_source_evidence.{item.evidence_id}")
    if not pack_ids:
        issue_ids.append("missing_pack_coverage")
    if not family_ids:
        issue_ids.append("missing_family_coverage")
    if not spec.artifact_kind_ids:
        issue_ids.append("missing_artifact_kinds")
    if not spec.runtime_surface_ids:
        issue_ids.append("missing_runtime_surfaces")
    if not spec.ui_surface_ids:
        issue_ids.append("missing_ui_surfaces")
    if not spec.report_surface_ids:
        issue_ids.append("missing_report_surfaces")
    if not spec.test_ids:
        issue_ids.append("missing_test_evidence")
    return SceneReportArtifactDrilldownRow(
        drilldown_channel_id=spec.drilldown_channel_id,
        label=spec.label,
        coverage_selector=spec.coverage_selector,
        pack_ids=pack_ids,
        family_ids=family_ids,
        artifact_kind_ids=spec.artifact_kind_ids,
        runtime_surface_ids=spec.runtime_surface_ids,
        ui_surface_ids=spec.ui_surface_ids,
        report_surface_ids=spec.report_surface_ids,
        repair_target_types=spec.repair_target_types,
        test_ids=spec.test_ids,
        evidence_ids=tuple(item.evidence_id for item in evidence),
        issue_ids=_unique_values(issue_ids),
    )


def _coverage_links(
    selector: str,
    packs: tuple[SceneCoveragePack, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if selector == "sample_fixture_artifact":
        selected = tuple(pack for pack in packs if pack.pack_id != "quick_formatting")
    elif selector == "material_artifact":
        selected = tuple(
            pack for pack in packs if "material_schema" in pack.capability_axis_ids
        )
    else:
        selected = tuple(
            pack for pack in packs if "delivery_preset" in pack.capability_axis_ids
        )
    return (
        _unique_values(pack.pack_id for pack in selected),
        _unique_values(
            family_id for pack in selected for family_id in pack.planned_family_ids
        ),
    )


def _source_evidence(
    specs: Sequence[SceneReportArtifactDrilldownSpec],
    project_root: Path | str | None,
) -> tuple[SceneReportArtifactDrilldownEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
    evidence_specs = tuple(
        (spec.drilldown_channel_id, item)
        for spec in specs
        for item in spec.evidence
    )
    marker_results = scan_scene_source_markers(
        root,
        tuple(
            (item.evidence_id, item.source_path, item.markers)
            for _, item in evidence_specs
        ),
    )
    return tuple(
        SceneReportArtifactDrilldownEvidence(
            drilldown_channel_id=drilldown_channel_id,
            evidence_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
            evidence_layer=item.evidence_layer,
        )
        for (drilldown_channel_id, item), result in zip(
            evidence_specs,
            marker_results,
        )
    )


def _evidence_by_channel(
    source_evidence: Sequence[SceneReportArtifactDrilldownEvidence],
) -> dict[str, tuple[SceneReportArtifactDrilldownEvidence, ...]]:
    grouped: dict[str, list[SceneReportArtifactDrilldownEvidence]] = {}
    for item in source_evidence:
        grouped.setdefault(item.drilldown_channel_id, []).append(item)
    return {key: tuple(value) for key, value in grouped.items()}


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


__all__ = [
    "N2_180_REPORT_ARTIFACT_DRILLDOWN_SPECS",
    "SCENE_REPORT_ARTIFACT_DRILLDOWN_AUDIT_ID",
    "SceneReportArtifactDrilldownAuditReport",
    "SceneReportArtifactDrilldownEvidence",
    "SceneReportArtifactDrilldownIssue",
    "SceneReportArtifactDrilldownRow",
    "audit_scene_report_artifact_drilldown_report",
    "build_scene_report_artifact_drilldown_audit_report",
]
