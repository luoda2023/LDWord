"""Execution completeness audit for DeliveryPreset output chains.

N2.176 sits after the horizontal DeliveryPreset registry audit.  The registry
answers which presets and artifacts a scene promises; this audit answers
whether the runtime chain can actually produce, aggregate, isolate failures,
and surface those artifacts through reports and UI state.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.plugin_manual_gate import list_plugin_manual_gates
from src.config.scene_delivery_preset_audit import (
    SceneDeliveryPresetAuditReport,
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_source_evidence import scan_scene_source_markers

SCENE_DELIVERY_PRESET_EXECUTION_AUDIT_ID = (
    "scene_delivery_preset_execution_audit"
)

BATCH_FAILURE_FAMILY_IDS: tuple[str, ...] = (
    "hr_batch_documents",
    "form_batch_documents",
    "bidding_materials",
)


@dataclass(frozen=True, slots=True)
class SceneDeliveryPresetExecutionEvidenceSpec:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    evidence_layer: str


@dataclass(frozen=True, slots=True)
class SceneDeliveryPresetExecutionSpec:
    execution_id: str
    label: str
    coverage_selector: str
    required_output_signal_ids: tuple[str, ...]
    payload_keys: tuple[str, ...]
    runtime_surface_ids: tuple[str, ...]
    report_surface_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence: tuple[SceneDeliveryPresetExecutionEvidenceSpec, ...]


@dataclass(frozen=True, slots=True)
class SceneDeliveryPresetExecutionIssue:
    execution_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneDeliveryPresetExecutionEvidence:
    execution_id: str
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
            "execution_id": self.execution_id,
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "evidence_layer": self.evidence_layer,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneDeliveryPresetExecutionRow:
    execution_id: str
    label: str
    coverage_selector: str
    pack_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    required_output_signal_ids: tuple[str, ...]
    payload_keys: tuple[str, ...]
    runtime_surface_ids: tuple[str, ...]
    report_surface_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id,
            "label": self.label,
            "coverage_selector": self.coverage_selector,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "required_output_signal_ids": list(self.required_output_signal_ids),
            "payload_keys": list(self.payload_keys),
            "runtime_surface_ids": list(self.runtime_surface_ids),
            "report_surface_ids": list(self.report_surface_ids),
            "ui_surface_ids": list(self.ui_surface_ids),
            "test_ids": list(self.test_ids),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneDeliveryPresetExecutionAuditReport:
    rows: tuple[SceneDeliveryPresetExecutionRow, ...]
    issues: tuple[SceneDeliveryPresetExecutionIssue, ...]
    source_evidence: tuple[SceneDeliveryPresetExecutionEvidence, ...]
    execution_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def execution_channel_count(self) -> int:
        return len(self.rows)

    @property
    def ready_execution_channel_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def required_output_signal_count(self) -> int:
        return len(
            _unique_values(
                signal
                for row in self.rows
                for signal in row.required_output_signal_ids
            )
        )

    @property
    def payload_key_count(self) -> int:
        return len(
            _unique_values(key for row in self.rows for key in row.payload_keys)
        )

    @property
    def runtime_surface_count(self) -> int:
        return len(
            _unique_values(
                surface for row in self.rows for surface in row.runtime_surface_ids
            )
        )

    @property
    def report_surface_count(self) -> int:
        return len(
            _unique_values(
                surface for row in self.rows for surface in row.report_surface_ids
            )
        )

    @property
    def ui_surface_count(self) -> int:
        return len(
            _unique_values(surface for row in self.rows for surface in row.ui_surface_ids)
        )

    @property
    def test_evidence_count(self) -> int:
        return len(_unique_values(test_id for row in self.rows for test_id in row.test_ids))

    @property
    def covered_pack_count(self) -> int:
        return len(_unique_values(pack_id for row in self.rows for pack_id in row.pack_ids))

    @property
    def covered_family_count(self) -> int:
        return len(
            _unique_values(family_id for row in self.rows for family_id in row.family_ids)
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
            "source_id": SCENE_DELIVERY_PRESET_EXECUTION_AUDIT_ID,
            "execution_filter": self.execution_filter,
            "counts": {
                "execution_channel_count": self.execution_channel_count,
                "ready_execution_channel_count": (
                    self.ready_execution_channel_count
                ),
                "required_output_signal_count": self.required_output_signal_count,
                "payload_key_count": self.payload_key_count,
                "runtime_surface_count": self.runtime_surface_count,
                "report_surface_count": self.report_surface_count,
                "ui_surface_count": self.ui_surface_count,
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
) -> SceneDeliveryPresetExecutionEvidenceSpec:
    return SceneDeliveryPresetExecutionEvidenceSpec(
        evidence_id=evidence_id,
        source_path=source_path,
        evidence_layer=evidence_layer,
        markers=tuple(markers),
    )


def _spec(
    execution_id: str,
    label: str,
    coverage_selector: str,
    required_output_signal_ids: tuple[str, ...],
    payload_keys: tuple[str, ...],
    runtime_surface_ids: tuple[str, ...],
    report_surface_ids: tuple[str, ...],
    ui_surface_ids: tuple[str, ...],
    test_ids: tuple[str, ...],
    evidence: tuple[SceneDeliveryPresetExecutionEvidenceSpec, ...],
) -> SceneDeliveryPresetExecutionSpec:
    return SceneDeliveryPresetExecutionSpec(
        execution_id=execution_id,
        label=label,
        coverage_selector=coverage_selector,
        required_output_signal_ids=required_output_signal_ids,
        payload_keys=payload_keys,
        runtime_surface_ids=runtime_surface_ids,
        report_surface_ids=report_surface_ids,
        ui_surface_ids=ui_surface_ids,
        test_ids=test_ids,
        evidence=evidence,
    )


N2_176_DELIVERY_PRESET_EXECUTION_SPECS: tuple[
    SceneDeliveryPresetExecutionSpec, ...
] = (
    _spec(
        "final_docx_delivery_outputs",
        "Final DOCX delivery outputs",
        "final_docx",
        ("final_docx", "output_paths"),
        ("output_path", "output_paths"),
        ("Pipeline._save_delivery_outputs",),
        ("PipelineResult.output_paths",),
        (),
        ("test_pipeline_publishes_each_delivery_variant_with_visibility_receipts",),
        (
            _evidence(
                "runtime.pipeline.final_docx",
                "src/pipeline/runner.py",
                "runtime",
                "def _save_delivery_outputs",
                'getattr(artifacts, "final_docx", False)',
                "def _publish_output_documents",
                "transaction.publish(candidates)",
            ),
            _evidence(
                "test.pipeline.final_docx",
                "tests/test_delivery_reporting_v1.py",
                "test",
                "def test_pipeline_publishes_each_delivery_variant_with_visibility_receipts",
                'assert set(payload["output_paths"]) == {"student", "teacher"}',
                'assert "Teacher answer" in teacher_text',
            ),
        ),
    ),
    _spec(
        "content_visibility_variant_outputs",
        "Content visibility variant outputs",
        "content_visibility",
        (
            "visibility_pruned_docx",
            "content_visibility_scan",
            "content_visibility_preview",
        ),
        ("output_paths", "content_visibility_scan", "content_visibility_preview"),
        (
            "Pipeline._apply_content_visibility_rules",
            "Pipeline._record_content_visibility_summary",
        ),
        ("delivery_visibility change records",),
        ("QuickExecutionDetail content visibility controls",),
        (
            "test_pipeline_publishes_each_delivery_variant_with_visibility_receipts",
            "test_content_visibility_preview_reports_per_preset_removed_blocks",
            "test_content_visibility_preview_uses_strict_body_plan_for_table_counts",
        ),
        (
            _evidence(
                "runtime.pipeline.visibility",
                "src/pipeline/runner.py",
                "runtime",
                "_apply_content_visibility_rules(preset_doc, preset)",
                "def _record_content_visibility_summary",
                'rule_name="delivery_visibility"',
            ),
            _evidence(
                "reporting.execution_payload.visibility",
                "src/reporting/execution_payload.py",
                "runtime_payload",
                "def content_visibility_scan_payload",
                "def content_visibility_preview_payload",
                'payload["has_issues"]',
            ),
            _evidence(
                "test.visibility",
                "tests/test_delivery_reporting_v1.py",
                "test",
                "def test_pipeline_publishes_each_delivery_variant_with_visibility_receipts",
                'assert "Teacher answer" not in student_text',
                'assert payload["content_visibility_preview"]',
            ),
        ),
    ),
    _spec(
        "target_template_group_execution",
        "Target template dependency capture",
        "target_template",
        ("target_template_docx", "target_group_report", "partial_success"),
        ("status", "output_path", "output_paths", "failed_count", "error_text"),
        (
            "resolve_execution_resource_graph",
            "_delivery_target_template_refs",
        ),
        ("dependent_template_refs",),
        (),
        ("test_delivery_target_templates_are_captured_as_dependent_resources",),
        (
            _evidence(
                "runtime.target_groups",
                "src/services/execution_session/resolution.py",
                "runtime",
                "def _delivery_target_template_refs",
                '"delivery_target_template"',
                "dependent_template_refs=dependent_template_refs",
                "dependent_resource_issues=tuple(dependent_resource_issues)",
            ),
            _evidence(
                "test.target_groups",
                "tests/test_delivery_reporting_v1.py",
                "test",
                "def test_delivery_target_templates_are_captured_as_dependent_resources",
                "session_resolution._delivery_target_template_refs(",
                '("delivery_target_template", "review-template", "ok")',
            ),
        ),
    ),
    _spec(
        "compare_docx_artifacts",
        "Compare DOCX artifacts",
        "compare_docx",
        ("compare_docx", "compare_paths"),
        ("compare_paths",),
        ("_write_compare_docx_artifacts", "write_compare_docx"),
        ("compare artifact path map",),
        ("WorkbenchExecutionAdapter.compare_paths",),
        ("test_compare_docx_artifact_is_atomically_published",),
        (
            _evidence(
                "runtime.compare",
                "src/services/production_runtime/delivery_reporting.py",
                "runtime",
                "def _write_compare_docx_artifacts",
                "write_compare_docx(",
                "compare_paths[preset_id] = str(target)",
            ),
            _evidence(
                "test.compare",
                "tests/test_delivery_reporting_v1.py",
                "test",
                "def test_compare_docx_artifact_is_atomically_published",
                'compare_path = Path(paths["review"])',
                'assert not list(compare_path.parent.glob(".ldword-compare-*"))',
            ),
        ),
    ),
    _spec(
        "delivery_reports",
        "Delivery JSON/Markdown reports",
        "report",
        ("report_json", "report_markdown", "report_paths"),
        ("report_paths",),
        ("write_delivery_reports", "write_json_report", "write_markdown_report"),
        ("delivery_changes_json", "delivery_changes_markdown"),
        ("QuickExecutionDetail.report_paths",),
        ("test_delivery_reports_follow_preset_artifact_toggles",),
        (
            _evidence(
                "runtime.reports",
                "src/services/production_runtime/delivery_reporting.py",
                "runtime",
                "def write_delivery_reports",
                "write_json_report(",
                "write_markdown_report(",
                "paths.append(str(path))",
            ),
            _evidence(
                "test.reports",
                "tests/test_delivery_reporting_v1.py",
                "test",
                "def test_delivery_reports_follow_preset_artifact_toggles",
                'assert {Path(path).suffix for path in paths} == {".json", ".md"}',
                "assert all(Path(path).is_file() for path in paths)",
            ),
        ),
    ),
    _spec(
        "structured_intermediate_outputs",
        "Structured intermediate outputs",
        "structured_intermediate",
        ("structured_intermediate_json", "intermediate_paths"),
        ("intermediate_paths",),
        ("write_structured_intermediates", "_structured_intermediate_payload"),
        ("delivery_structured_intermediate",),
        ("WorkbenchExecutionAdapter.intermediate_paths",),
        ("test_structured_intermediate_contains_delivery_contract",),
        (
            _evidence(
                "runtime.intermediate",
                "src/services/production_runtime/delivery_reporting.py",
                "runtime",
                "def write_structured_intermediates",
                "def _structured_intermediate_payload",
                '"kind": "delivery_structured_intermediate"',
                "paths[preset_id] = str(path)",
            ),
            _evidence(
                "test.intermediate",
                "tests/test_delivery_reporting_v1.py",
                "test",
                "def test_structured_intermediate_contains_delivery_contract",
                'intermediate = json.loads(Path(paths["review"]).read_text',
                'assert intermediate["kind"] == "delivery_structured_intermediate"',
            ),
        ),
    ),
    _spec(
        "material_manifest_package_outputs",
        "Material manifest/package outputs",
        "material_package",
        ("material_manifest_json", "material_package_manifest", "material_package_zip"),
        ("material_manifest_paths", "material_package_paths"),
        ("publish_material_artifacts", "build_material_delivery_package"),
        ("material_delivery_package", "material_attachment_manifest"),
        ("WorkbenchExecutionAdapter.material_package_paths",),
        (
            "test_publish_material_artifacts_writes_manifest_and_transactional_package",
            "test_material_package_redacts_local_paths_from_json_outputs",
        ),
        (
            _evidence(
                "runtime.material_package",
                "src/services/production_runtime/material_artifacts.py",
                "runtime",
                "def publish_material_artifacts",
                "def _material_manifest_payload",
                '"kind": "material_attachment_manifest"',
                "build_material_delivery_package(",
            ),
            _evidence(
                "test.material_package",
                "tests/test_material_artifact_publication.py",
                "test",
                "def test_publish_material_artifacts_writes_manifest_and_transactional_package",
                "def test_material_package_redacts_local_paths_from_json_outputs",
                'assert "manifest/material_manifest.json" in archive.namelist()',
            ),
        ),
    ),
    _spec(
        "failed_run_material_package_outputs",
        "Failed-run material package outputs",
        "material_package",
        (
            "failed_run_material_manifest",
            "failed_run_material_package",
            "failed_count",
        ),
        (
            "status",
            "material_manifest_paths",
            "material_package_paths",
            "failed_count",
            "error_text",
        ),
        ("project_execution_result.failed",),
        ("failed execution material manifest",),
        ("WorkbenchExecutionAdapter.failed_count",),
        ("test_failed_run_still_publishes_reports_and_material_package",),
        (
            _evidence(
                "runtime.failed_package",
                "src/services/production_runtime/delivery_reporting.py",
                "runtime",
                "def finalize_result_artifacts",
                "publish_material_artifacts(",
                "material_manifest_paths=material_outcome.material_manifest_paths",
                "material_package_paths=material_outcome.material_package_paths",
            ),
            _evidence(
                "test.failed_package",
                "tests/test_delivery_reporting_v1.py",
                "test",
                "def test_failed_run_still_publishes_reports_and_material_package",
                'assert payload["status"] == "failed"',
                'assert Path(payload["material_package_paths"]["zip"]).is_file()',
            ),
        ),
    ),
    _spec(
        "batch_failure_isolation_artifacts",
        "Batch atomic-set rollback evidence",
        "batch_failure",
        ("batch_atomic_set", "rolled_back_paths", "items"),
        (
            "status",
            "items",
            "output_paths",
            "rolled_back_paths",
            "error_text",
            "document_batch_receipt",
        ),
        ("DocumentBatchPlan.run", "os.replace", "transaction rollback"),
        ("document_batch_receipt",),
        ("FileBatchExecutionDetail batch result",),
        ("test_document_batch_rolls_back_the_atomic_set_on_publish_failure",),
        (
            _evidence(
                "runtime.batch_isolation",
                "src/document_batch/recipe.py",
                "document_batch",
                "class DocumentBatchPlan",
                "def run(self)",
                "os.replace(stage, final)",
                '"rolled_back_paths": [str(item) for item in committed]',
                "shutil.rmtree(staging, ignore_errors=True)",
            ),
            _evidence(
                "test.batch_isolation",
                "tests/test_document_batch_v1.py",
                "test",
                "def test_document_batch_rolls_back_the_atomic_set_on_publish_failure",
                'assert result["status"] == "failed"',
                'assert len(result["rolled_back_paths"]) == 1',
            ),
        ),
    ),
    _spec(
        "artifact_surface_state_and_logs",
        "Artifact surface state and logs",
        "all_delivery",
        ("artifact_items", "recent_artifact_label", "quick_execution_log"),
        (
            "artifact_items",
            "output_paths",
            "compare_paths",
            "report_paths",
            "intermediate_paths",
            "material_manifest_paths",
            "material_package_paths",
        ),
        ("WorkbenchExecutionAdapter.build_result_state",),
        ("RecentRunState artifact labels",),
        (
            "QuickExecutionDetail.set_execution_result",
            "WorkbenchExecutionController.apply_execution_result",
            "RecentRunPanel.artifact_items",
        ),
        (
            "test_execution_worker_preserves_delivery_artifact_maps",
            "test_recent_run_panel_renders_delivery_artifact_labels",
        ),
        (
            _evidence(
                "runtime.artifact_adapter",
                "src/ui/adapters/workbench_execution_adapter.py",
                "ui",
                "def _execution_result_state_from_terminal",
                "paths = _terminal_result_paths(payload)",
                "def _terminal_result_paths",
                '_terminal_dict_projection(payload, "output_paths")',
                '_terminal_dict_projection(payload, "compare_paths")',
                '_terminal_dict_projection(payload, "material_package_paths")',
            ),
            _evidence(
                "runtime.artifact_quick_result_presenter",
                "src/ui/panels/workbench/quick_execution_result_presenter.py",
                "ui_presenter",
                "def build_execution_result_presentation",
                "def _append_artifact_log_entries",
                "for label, path in workbench_artifact_display_items(",
                '(state.compare_paths, "对比稿", True)',
                '(state.material_package_paths, "资料包", False)',
                "f\"报告文件：{', '.join(state.report_paths)}\"",
            ),
            _evidence(
                "test.artifact_surface",
                "tests/test_execution_worker.py",
                "test",
                "def test_execution_worker_preserves_delivery_artifact_maps",
                '"compare_paths": {"review": Path("out/review_compare.docx")}',
                '"material_package_paths": {"zip": Path("out/material_package.zip")}',
            ),
            _evidence(
                "test.quick_detail_artifact_surface",
                "tests/test_recent_run_panel.py",
                "test",
                "def test_recent_run_panel_renders_delivery_artifact_labels",
                'assert "资料包: zip: material_package.zip" in text',
                'assert "产物清单: 输出[review]: review.docx (预警)" in text',
            ),
        ),
    ),
)


def build_scene_delivery_preset_execution_audit_report(
    *,
    execution_id: str = "",
    project_root: Path | str | None = None,
) -> SceneDeliveryPresetExecutionAuditReport:
    normalized_execution = str(execution_id or "").strip()
    specs = tuple(
        spec
        for spec in N2_176_DELIVERY_PRESET_EXECUTION_SPECS
        if not normalized_execution or spec.execution_id == normalized_execution
    )
    delivery_report = build_scene_delivery_preset_audit_report(
        project_root=project_root
    )
    source_evidence = _source_evidence(specs, project_root)
    evidence_by_execution = _evidence_by_execution(source_evidence)
    rows = tuple(
        _row(spec, delivery_report, evidence_by_execution.get(spec.execution_id, ()))
        for spec in specs
    )
    issues = audit_scene_delivery_preset_execution_report(
        SceneDeliveryPresetExecutionAuditReport(
            rows=rows,
            issues=(),
            source_evidence=source_evidence,
            execution_filter=normalized_execution,
        )
    )
    return SceneDeliveryPresetExecutionAuditReport(
        rows=rows,
        issues=issues,
        source_evidence=source_evidence,
        execution_filter=normalized_execution,
    )


def audit_scene_delivery_preset_execution_report(
    report: SceneDeliveryPresetExecutionAuditReport,
) -> tuple[SceneDeliveryPresetExecutionIssue, ...]:
    issues: list[SceneDeliveryPresetExecutionIssue] = []
    seen_issue_keys: set[tuple[str, str, str]] = set()
    for row in report.rows:
        for issue_id in row.issue_ids:
            _append_issue(
                issues,
                seen_issue_keys,
                row.execution_id,
                issue_id,
                f"DeliveryPreset execution channel has unresolved issue: {issue_id}.",
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            _append_issue(
                issues,
                seen_issue_keys,
                evidence.execution_id,
                f"missing_source_evidence.{evidence.evidence_id}",
                f"Missing source markers: {', '.join(evidence.missing_markers)}",
            )
    return tuple(issues)


def _append_issue(
    issues: list[SceneDeliveryPresetExecutionIssue],
    seen: set[tuple[str, str, str]],
    execution_id: str,
    kind: str,
    message: str,
) -> None:
    key = (execution_id, kind, message)
    if key in seen:
        return
    seen.add(key)
    issues.append(
        SceneDeliveryPresetExecutionIssue(
            execution_id=execution_id,
            kind=kind,
            message=message,
        )
    )


def _row(
    spec: SceneDeliveryPresetExecutionSpec,
    delivery_report: SceneDeliveryPresetAuditReport,
    evidence: tuple[SceneDeliveryPresetExecutionEvidence, ...],
) -> SceneDeliveryPresetExecutionRow:
    pack_ids, family_ids = _coverage_links(spec.coverage_selector, delivery_report)
    issue_ids: list[str] = []
    if not evidence:
        issue_ids.append("missing_evidence_specs")
    for item in evidence:
        if item.status != "ready":
            issue_ids.append(f"missing_source_evidence.{item.evidence_id}")
    if spec.coverage_selector != "ui_surface" and not pack_ids:
        issue_ids.append("missing_pack_coverage")
    if spec.coverage_selector != "ui_surface" and not family_ids:
        issue_ids.append("missing_family_coverage")
    if not spec.required_output_signal_ids:
        issue_ids.append("missing_required_output_signals")
    if not spec.payload_keys:
        issue_ids.append("missing_payload_keys")
    if not spec.runtime_surface_ids:
        issue_ids.append("missing_runtime_surfaces")
    if not spec.test_ids:
        issue_ids.append("missing_test_evidence")
    return SceneDeliveryPresetExecutionRow(
        execution_id=spec.execution_id,
        label=spec.label,
        coverage_selector=spec.coverage_selector,
        pack_ids=pack_ids,
        family_ids=family_ids,
        required_output_signal_ids=spec.required_output_signal_ids,
        payload_keys=spec.payload_keys,
        runtime_surface_ids=spec.runtime_surface_ids,
        report_surface_ids=spec.report_surface_ids,
        ui_surface_ids=spec.ui_surface_ids,
        test_ids=spec.test_ids,
        evidence_ids=tuple(item.evidence_id for item in evidence),
        issue_ids=_unique_values(issue_ids),
    )


def _coverage_links(
    selector: str,
    delivery_report: SceneDeliveryPresetAuditReport,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    blocked_family_ids = {
        family_id
        for gate in list_plugin_manual_gates()
        if gate.blocks_core_execution_until_confirmed
        for family_id in gate.blocking_family_ids
    }
    family_rows = tuple(
        row
        for row in delivery_report.family_rows
        if row.family_id not in blocked_family_ids
        and _family_matches_selector(row, selector)
    )
    family_ids = _unique_values(row.family_id for row in family_rows)
    pack_ids = _unique_values(pack_id for row in family_rows for pack_id in row.pack_ids)
    if selector == "batch_failure":
        pack_ids = _unique_values(
            (
                *pack_ids,
                *(
                    row.pack_id
                    for row in delivery_report.pack_rows
                    if row.pack_id == "batch_forms"
                ),
            )
        )
    return pack_ids, family_ids


def _family_matches_selector(row, selector: str) -> bool:
    if selector == "all_delivery":
        return bool(row.actual_delivery_preset_ids)
    if selector == "final_docx":
        return row.final_docx_preset_count > 0
    if selector == "content_visibility":
        return row.content_visibility_rule_count > 0
    if selector == "target_template":
        return bool(row.target_template_ids)
    if selector == "compare_docx":
        return row.compare_docx_preset_count > 0
    if selector == "report":
        return bool(row.report_levels or row.report_only_preset_count)
    if selector == "structured_intermediate":
        return row.structured_intermediate_preset_count > 0
    if selector == "material_package":
        return row.material_package_preset_count > 0
    if selector == "batch_failure":
        return row.family_id in BATCH_FAILURE_FAMILY_IDS
    return bool(row.actual_delivery_preset_ids)


def _source_evidence(
    specs: Iterable[SceneDeliveryPresetExecutionSpec],
    project_root: Path | str | None,
) -> tuple[SceneDeliveryPresetExecutionEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    evidence_specs = tuple(
        (spec.execution_id, item)
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
        SceneDeliveryPresetExecutionEvidence(
            execution_id=execution_id,
            evidence_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
            evidence_layer=item.evidence_layer,
        )
        for (execution_id, item), result in zip(evidence_specs, marker_results)
    )


def _evidence_by_execution(
    evidence: Iterable[SceneDeliveryPresetExecutionEvidence],
) -> dict[str, tuple[SceneDeliveryPresetExecutionEvidence, ...]]:
    grouped: dict[str, list[SceneDeliveryPresetExecutionEvidence]] = {}
    for item in evidence:
        grouped.setdefault(item.execution_id, []).append(item)
    return {key: tuple(value) for key, value in grouped.items()}


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "N2_176_DELIVERY_PRESET_EXECUTION_SPECS",
    "SCENE_DELIVERY_PRESET_EXECUTION_AUDIT_ID",
    "SceneDeliveryPresetExecutionAuditReport",
    "SceneDeliveryPresetExecutionEvidence",
    "SceneDeliveryPresetExecutionIssue",
    "SceneDeliveryPresetExecutionRow",
    "audit_scene_delivery_preset_execution_report",
    "build_scene_delivery_preset_execution_audit_report",
]
