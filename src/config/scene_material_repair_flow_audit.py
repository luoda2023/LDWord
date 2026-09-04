"""MaterialSchema input and repair-flow audit for high-frequency scenes.

N2.177 sits after the horizontal MaterialSchema registry audit.  The registry
answers whether a scene family declares fields, assets, and schema ids; this
audit answers whether missing or conflicting material data can be diagnosed,
reported, routed to a repair surface, focused in the UI, and checked by tests.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_material_schema_audit import (
    SceneMaterialSchemaAuditReport,
    build_scene_material_schema_audit_report,
)
from src.config.scene_source_evidence import scan_scene_source_markers

SCENE_MATERIAL_REPAIR_FLOW_AUDIT_ID = "scene_material_repair_flow_audit"

BATCH_MATERIAL_FAMILY_IDS: tuple[str, ...] = (
    "hr_batch_documents",
    "form_batch_documents",
    "bidding_materials",
)


@dataclass(frozen=True, slots=True)
class SceneMaterialRepairFlowEvidenceSpec:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    evidence_layer: str


@dataclass(frozen=True, slots=True)
class SceneMaterialRepairFlowSpec:
    flow_id: str
    label: str
    coverage_selector: str
    capability_ids: tuple[str, ...]
    material_signal_ids: tuple[str, ...]
    repair_target_types: tuple[str, ...]
    runtime_surface_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence: tuple[SceneMaterialRepairFlowEvidenceSpec, ...]


@dataclass(frozen=True, slots=True)
class SceneMaterialRepairFlowIssue:
    flow_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "flow_id": self.flow_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneMaterialRepairFlowEvidence:
    flow_id: str
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
            "flow_id": self.flow_id,
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "evidence_layer": self.evidence_layer,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneMaterialRepairFlowRow:
    flow_id: str
    label: str
    coverage_selector: str
    pack_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    material_signal_ids: tuple[str, ...]
    repair_target_types: tuple[str, ...]
    runtime_surface_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "flow_id": self.flow_id,
            "label": self.label,
            "coverage_selector": self.coverage_selector,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "capability_ids": list(self.capability_ids),
            "material_signal_ids": list(self.material_signal_ids),
            "repair_target_types": list(self.repair_target_types),
            "runtime_surface_ids": list(self.runtime_surface_ids),
            "ui_surface_ids": list(self.ui_surface_ids),
            "test_ids": list(self.test_ids),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneMaterialRepairFlowAuditReport:
    rows: tuple[SceneMaterialRepairFlowRow, ...]
    issues: tuple[SceneMaterialRepairFlowIssue, ...]
    source_evidence: tuple[SceneMaterialRepairFlowEvidence, ...]
    flow_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def flow_count(self) -> int:
        return len(self.rows)

    @property
    def ready_flow_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def capability_count(self) -> int:
        return len(_unique_values(value for row in self.rows for value in row.capability_ids))

    @property
    def material_signal_count(self) -> int:
        return len(
            _unique_values(value for row in self.rows for value in row.material_signal_ids)
        )

    @property
    def repair_target_type_count(self) -> int:
        return len(
            _unique_values(value for row in self.rows for value in row.repair_target_types)
        )

    @property
    def runtime_surface_count(self) -> int:
        return len(
            _unique_values(value for row in self.rows for value in row.runtime_surface_ids)
        )

    @property
    def ui_surface_count(self) -> int:
        return len(_unique_values(value for row in self.rows for value in row.ui_surface_ids))

    @property
    def test_evidence_count(self) -> int:
        return len(_unique_values(value for row in self.rows for value in row.test_ids))

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
            "source_id": SCENE_MATERIAL_REPAIR_FLOW_AUDIT_ID,
            "flow_filter": self.flow_filter,
            "counts": {
                "flow_count": self.flow_count,
                "ready_flow_count": self.ready_flow_count,
                "capability_count": self.capability_count,
                "material_signal_count": self.material_signal_count,
                "repair_target_type_count": self.repair_target_type_count,
                "runtime_surface_count": self.runtime_surface_count,
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
) -> SceneMaterialRepairFlowEvidenceSpec:
    return SceneMaterialRepairFlowEvidenceSpec(
        evidence_id=evidence_id,
        source_path=source_path,
        evidence_layer=evidence_layer,
        markers=tuple(markers),
    )


def _spec(
    flow_id: str,
    label: str,
    coverage_selector: str,
    capability_ids: tuple[str, ...],
    material_signal_ids: tuple[str, ...],
    repair_target_types: tuple[str, ...],
    runtime_surface_ids: tuple[str, ...],
    ui_surface_ids: tuple[str, ...],
    test_ids: tuple[str, ...],
    evidence: tuple[SceneMaterialRepairFlowEvidenceSpec, ...],
) -> SceneMaterialRepairFlowSpec:
    return SceneMaterialRepairFlowSpec(
        flow_id=flow_id,
        label=label,
        coverage_selector=coverage_selector,
        capability_ids=capability_ids,
        material_signal_ids=material_signal_ids,
        repair_target_types=repair_target_types,
        runtime_surface_ids=runtime_surface_ids,
        ui_surface_ids=ui_surface_ids,
        test_ids=test_ids,
        evidence=evidence,
    )



# Material Package V1 replaced the former profile/schema-editor repair model.
# Keep the public flow ids stable for dashboard/drilldown links while auditing
# only the canonical package, frozen selection, publication, and artifact path.
N2_177_MATERIAL_REPAIR_FLOW_SPECS: tuple[SceneMaterialRepairFlowSpec, ...] = (
    _spec(
        "schema_requirements_to_assets_panel",
        "Schema contracts drive the canonical AssetsPanel package editor",
        "all_material",
        (
            "schema_contract_adapter",
            "package_owned_contract",
            "canonical_assets_editor",
        ),
        (
            "material_contract_id",
            "contract_fields",
            "resource_roles",
            "contract_extensions",
        ),
        ("schema", "field", "asset"),
        ("get_package_material_contract", "material_contract_from_schema"),
        ("AssetsPanel contract-driven fields", "AssetsPanel resource domains"),
        (
            "test_package_owned_dynamic_contract_survives_save_and_resolution",
            "test_image_policy_is_package_owned_and_survives_v1_save",
            "test_preview_is_a_projection_of_package_and_contract",
        ),
        (
            _evidence(
                "runtime.v1.contract_adapter",
                "src/application/materials/contracts.py",
                "runtime",
                "def get_package_material_contract",
                "def material_contract_from_schema",
                "PACKAGE_CONTRACT_EXTENSIONS_KEY",
            ),
            _evidence(
                "ui.v1.assets_contract_editor",
                "src/ui/panels/assets_panel.py",
                "ui",
                "get_package_material_contract",
                "def _refresh_fields",
                "def _refresh_resources",
            ),
            _evidence(
                "test.v1.contract_adapter",
                "tests/test_material_application_v1.py",
                "test",
                "def test_package_owned_dynamic_contract_survives_save_and_resolution",
                "def test_image_policy_is_package_owned_and_survives_v1_save",
                "def test_preview_is_a_projection_of_package_and_contract",
            ),
        ),
    ),
    _spec(
        "assets_panel_preview_missing_detection",
        "Package preview and check surfaces expose typed material gaps",
        "material_fields_or_assets",
        (
            "package_preview_projection",
            "typed_issue_projection",
            "editor_check_surface",
        ),
        (
            "package_revision",
            "required_field_count",
            "resource_count",
            "issue_codes",
        ),
        ("record", "field", "asset"),
        ("project_material_preview", "MaterialResolver.resolve_record"),
        ("AssetsPanel overview preview", "AssetsPanel check table"),
        (
            "test_assets_panel_preserves_scope_after_a_field_edit",
            "test_assets_panel_exposes_v1_material_domains",
            "test_classic_image_page_binds_resource_through_v1_service",
        ),
        (
            _evidence(
                "runtime.v1.preview_projection",
                "src/application/materials/preview.py",
                "runtime",
                "class MaterialPreviewSnapshot",
                "def project_material_preview",
                "issue_codes",
            ),
            _evidence(
                "ui.v1.assets_preview_check",
                "src/ui/panels/assets_panel.py",
                "ui",
                "assets_overview_preview_table",
                "def _refresh_overview",
                "def _refresh_check",
            ),
            _evidence(
                "test.v1.assets_preview_check",
                "tests/test_assets_panel_v1_editor.py",
                "test",
                "def test_assets_panel_preserves_scope_after_a_field_edit",
                "def test_assets_panel_exposes_v1_material_domains",
                "def test_classic_image_page_binds_resource_through_v1_service",
            ),
        ),
    ),
    _spec(
        "workbench_material_readiness_groups",
        "Workbench selects one exact package revision and active record set",
        "all_material",
        (
            "package_selection_projection",
            "exact_revision_loading",
            "active_record_selection",
        ),
        (
            "selected_package_id",
            "selected_record_ids",
            "preview_snapshot",
            "material_issues",
        ),
        ("material_package", "selection", "revision"),
        ("choose_material_package", "MaterialSelectionProjection"),
        ("QuickExecutionDetail package selector", "Quick material preview"),
        (
            "test_quick_execution_floating_inputs_update_the_run_selection",
            "test_all_workbench_run_paths_consume_quick_runtime_selection",
        ),
        (
            _evidence(
                "runtime.v1.workbench_selection",
                "src/ui/panels/workbench/material_state.py",
                "runtime",
                "class MaterialSelectionProjection",
                "def choose_material_package",
                "selected_record_ids",
            ),
            _evidence(
                "ui.v1.workbench_selector",
                "src/ui/panels/workbench/quick_execution_detail.py",
                "ui",
                "material_package_selected",
                "def set_material_selection",
                "execution_material_selection",
            ),
            _evidence(
                "test.v1.workbench_selection",
                "tests/test_workbench_v1_material_runtime.py",
                "test",
                "def test_quick_execution_floating_inputs_update_the_run_selection",
                "def test_all_workbench_run_paths_consume_quick_runtime_selection",
            ),
        ),
    ),
    _spec(
        "execution_gate_policy_semantics",
        "Typed material issues feed one fail-closed Workbench gate",
        "all_material",
        (
            "typed_issue_gate",
            "blocking_error_semantics",
            "repair_primary_action",
        ),
        ("can_run", "blocking_reasons", "warning_reasons"),
        ("material_package", "selection", "record"),
        ("material_execution_gate", "decide_execution_gate"),
        ("QuickExecutionDetail compact readiness status", "Workbench execute action"),
        (
            "test_material_execution_gate_blocks_errors_and_routes_to_package",
            "test_material_execution_gate_keeps_warnings_runnable",
        ),
        (
            _evidence(
                "runtime.v1.material_gate",
                "src/ui/panels/workbench/material_state.py",
                "runtime",
                "def material_execution_gate",
                "ExecutionGateAction",
                '"material_package"',
            ),
            _evidence(
                "runtime.v1.shared_gate",
                "src/ui/adapters/workbench_execution_gate.py",
                "runtime",
                "def decide_execution_gate",
                "blocking_reasons",
                "warning_reasons",
            ),
            _evidence(
                "test.v1.material_gate",
                "tests/test_workbench_v1_material_runtime.py",
                "test",
                "def test_material_execution_gate_blocks_errors_and_routes_to_package",
                "def test_material_execution_gate_keeps_warnings_runnable",
            ),
        ),
    ),
    _spec(
        "execution_result_detail_access",
        "Material receipts remain visible in inline results and artifact drilldown",
        "all_material",
        (
            "inline_result_feedback",
            "artifact_drilldown",
            "material_receipt_visibility",
        ),
        ("result_status", "report_paths", "material_receipt_paths"),
        ("artifact", "material_package", "revision"),
        ("build_execution_result_presentation", "workbench_artifact_display_items"),
        ("QuickExecutionDetail inline status", "RecentRunPanel artifact rows"),
        (
            "test_execution_worker_preserves_material_receipts_errors_and_artifact_failures",
            "test_recent_run_panel_labels_material_package_report_anchor",
        ),
        (
            _evidence(
                "ui.v1.inline_result",
                "src/ui/panels/workbench/quick_execution_result_presenter.py",
                "ui",
                "def build_execution_result_presentation",
                "material_manifest_paths",
                "material_package_paths",
            ),
            _evidence(
                "runtime.v1.artifact_projection",
                "src/ui/adapters/workbench_artifact_items.py",
                "runtime",
                "def workbench_artifact_display_items",
                "def _extend_material_package_items",
            ),
            _evidence(
                "test.v1.material_result_access",
                "tests/test_execution_worker.py",
                "test",
                "def test_execution_worker_preserves_material_receipts_errors_and_artifact_failures",
                "material_manifest_paths",
                "material_package_paths",
            ),
        ),
    ),
    _spec(
        "quick_material_repair_button",
        "Quick execution exposes one repair handoff to the package editor",
        "all_material",
        (
            "compact_primary_action",
            "package_editor_handoff",
            "one_material_cta",
        ),
        ("material_repair_requested", "primary_action", "repair_target_type"),
        ("material_package", "field", "asset"),
        ("QuickExecutionDetail._request_material_repair", "ExecutionGateAction"),
        ("QuickExecutionDetail material primary action",),
        ("test_quick_material_repair_action_targets_package_editor",),
        (
            _evidence(
                "ui.v1.quick_repair_action",
                "src/ui/panels/workbench/quick_execution_detail.py",
                "ui",
                "_material_repair_btn = QPushButton(",
                "def _request_material_repair",
                "material_repair_requested.emit",
            ),
            _evidence(
                "runtime.v1.quick_repair_decision",
                "src/ui/panels/workbench/material_state.py",
                "runtime",
                "ExecutionGateAction",
                '"material_package"',
            ),
            _evidence(
                "test.v1.quick_repair_action",
                "tests/test_workbench_v1_material_runtime.py",
                "test",
                "def test_quick_material_repair_action_targets_package_editor",
                'assert emitted == [("material_package", "")]',
            ),
        ),
    ),
    _spec(
        "panel_bridge_material_routing",
        "Workbench routes material repairs directly to the canonical AssetsPanel",
        "all_material",
        (
            "direct_assets_navigation",
            "typed_navigation_intent",
            "lazy_panel_activation",
        ),
        ("navigate_to_intent", "issue_type", "issue_key"),
        ("material_package", "field", "asset"),
        ("WorkbenchPanel._open_material_repair_target", "workbench_issue_navigation_for_target"),
        ("Assets panel navigation",),
        (
            "test_workbench_issue_navigation_registry_maps_targets_to_surfaces",
            "test_material_repairs_route_to_canonical_assets_panel",
        ),
        (
            _evidence(
                "ui.v1.material_navigation_registry",
                "src/ui/adapters/workbench_product_issue_navigation.py",
                "ui",
                '"material_package"',
                'panel_id="assets"',
                "def workbench_issue_navigation_for_target",
            ),
            _evidence(
                "runtime.v1.material_navigation",
                "src/ui/panels/workbench/panel_v2.py",
                "runtime",
                "def _open_material_repair_target",
                "workbench_issue_navigation_for_target",
                "_navigate_issue_projection",
            ),
            _evidence(
                "test.v1.material_navigation",
                "tests/test_workbench_issue_navigation.py",
                "test",
                "def test_workbench_issue_navigation_registry_maps_targets_to_surfaces",
                "def test_material_repairs_route_to_canonical_assets_panel",
            ),
        ),
    ),
    _spec(
        "assets_panel_target_focus",
        "AssetsPanel protects package drafts with reversible edit transactions",
        "material_fields_or_assets",
        (
            "package_edit_transaction",
            "dirty_draft_preservation",
            "rollback_safe_close",
        ),
        ("draft_revision", "pending_changes", "rollback_receipt"),
        ("material_package", "record", "field"),
        ("AssetsPanel.prepare_pending_material_changes", "AssetsPanel.rollback_prepared_material_changes"),
        ("AssetsPanel package editor",),
        (
            "test_material_service_can_remove_derivation_and_timeline",
            "test_assets_panel_cancelled_package_switch_keeps_dirty_draft",
        ),
        (
            _evidence(
                "ui.v1.assets_transaction",
                "src/ui/panels/assets_panel.py",
                "ui",
                "def prepare_pending_material_changes",
                "def rollback_prepared_material_changes",
                "def finalize_prepared_material_changes",
            ),
            _evidence(
                "runtime.v1.assets_publication",
                "src/config/material_package_library.py",
                "runtime",
                "class MaterialPackagePublicationReceipt",
                "def save_material_package_entry",
            ),
            _evidence(
                "test.v1.assets_transaction",
                "tests/test_assets_panel_v1_editor.py",
                "test",
                "def test_material_service_can_remove_derivation_and_timeline",
                "def test_assets_panel_cancelled_package_switch_keeps_dirty_draft",
            ),
        ),
    ),
    _spec(
        "schema_replacement_recommendation_flow",
        "Contract, mode, and revision mismatches fail closed before execution",
        "schema_reference",
        (
            "contract_identity_guard",
            "mode_compatibility_guard",
            "revision_cas_guard",
        ),
        ("contract_mismatch", "mode_mismatch", "revision_mismatch"),
        ("schema", "material_package", "revision"),
        ("bind_material_run", "material_package_revision"),
        ("AssetsPanel contract identity",),
        (
            "test_binder_freezes_one_identity_and_rejects_document_type_conflict",
            "test_repository_uses_revision_cas_and_no_shadowing",
        ),
        (
            _evidence(
                "runtime.v1.binding_guards",
                "src/application/materials/execution.py",
                "runtime",
                "def bind_material_run",
                "material.bind.mode_mismatch",
                "material.bind.revision_mismatch",
            ),
            _evidence(
                "runtime.v1.package_revision",
                "src/infrastructure/materials/codec.py",
                "runtime",
                "def material_package_revision",
                "canonical_material_package_bytes",
            ),
            _evidence(
                "test.v1.binding_guards",
                "tests/test_material_application_v1.py",
                "test",
                "def test_binder_freezes_one_identity_and_rejects_document_type_conflict",
                "material.bind.document_type_mismatch",
            ),
        ),
    ),
    _spec(
        "batch_profile_material_repair_targets",
        "Batch execution consumes one frozen snapshot and publishes atomically",
        "batch_material",
        (
            "batch_snapshot_freeze",
            "per_record_output_binding",
            "atomic_batch_publication",
        ),
        ("execution_material_snapshot", "batch_record_ids", "batch_output_paths"),
        ("selection", "record", "artifact"),
        ("compile_document_batch_plan", "ExecutionMaterialSnapshot"),
        ("Workbench batch generation detail",),
        (
            "test_document_batch_uses_frozen_snapshot_and_publishes_as_one_set",
            "test_document_batch_rolls_back_the_atomic_set_on_publish_failure",
        ),
        (
            _evidence(
                "runtime.v1.batch_recipe",
                "src/document_batch/recipe.py",
                "runtime",
                "class DocumentBatchRecipe",
                "def compile_document_batch_plan",
                "os.replace(",
            ),
            _evidence(
                "runtime.v1.frozen_snapshot",
                "src/application/materials/execution.py",
                "runtime",
                "class ExecutionMaterialSnapshot",
                "output_paths",
                "preflight_receipt",
            ),
            _evidence(
                "test.v1.batch_recipe",
                "tests/test_document_batch_v1.py",
                "test",
                "def test_document_batch_uses_frozen_snapshot_and_publishes_as_one_set",
                "def test_document_batch_rolls_back_the_atomic_set_on_publish_failure",
            ),
        ),
    ),
    _spec(
        "material_manifest_feedback",
        "Material manifests and packages publish transactionally with public paths",
        "all_material",
        (
            "transactional_material_artifacts",
            "public_path_redaction",
            "failed_run_evidence",
        ),
        ("material_manifest_paths", "material_package_paths", "publication_receipt"),
        ("artifact", "material_package", "revision"),
        ("publish_material_artifacts",),
        ("RecentRunPanel material artifacts",),
        (
            "test_publish_material_artifacts_writes_manifest_and_transactional_package",
            "test_material_package_redacts_local_paths_from_json_outputs",
            "test_failed_run_still_publishes_reports_and_material_package",
            "test_delivery_reports_follow_preset_artifact_toggles",
        ),
        (
            _evidence(
                "runtime.v1.material_artifacts",
                "src/services/production_runtime/material_artifacts.py",
                "runtime",
                "def publish_material_artifacts",
                "material_manifest_paths",
                "material_package_paths",
            ),
            _evidence(
                "test.v1.material_artifacts",
                "tests/test_material_artifact_publication.py",
                "test",
                "def test_publish_material_artifacts_writes_manifest_and_transactional_package",
                "def test_material_package_redacts_local_paths_from_json_outputs",
            ),
            _evidence(
                "test.v1.failed_material_evidence",
                "tests/test_delivery_reporting_v1.py",
                "test",
                "def test_failed_run_still_publishes_reports_and_material_package",
                "material_package_paths",
            ),
        ),
    ),
)


def build_scene_material_repair_flow_audit_report(
    *,
    flow_id: str = "",
    project_root: Path | str | None = None,
) -> SceneMaterialRepairFlowAuditReport:
    normalized_flow = str(flow_id or "").strip()
    specs = tuple(
        spec
        for spec in N2_177_MATERIAL_REPAIR_FLOW_SPECS
        if not normalized_flow or spec.flow_id == normalized_flow
    )
    material_report = build_scene_material_schema_audit_report(project_root=project_root)
    source_evidence = _source_evidence(specs, project_root)
    evidence_by_flow = _evidence_by_flow(source_evidence)
    rows = tuple(
        _row(spec, material_report, evidence_by_flow.get(spec.flow_id, ()))
        for spec in specs
    )
    issues = audit_scene_material_repair_flow_report(
        SceneMaterialRepairFlowAuditReport(
            rows=rows,
            issues=(),
            source_evidence=source_evidence,
            flow_filter=normalized_flow,
        )
    )
    return SceneMaterialRepairFlowAuditReport(
        rows=rows,
        issues=issues,
        source_evidence=source_evidence,
        flow_filter=normalized_flow,
    )


def audit_scene_material_repair_flow_report(
    report: SceneMaterialRepairFlowAuditReport,
) -> tuple[SceneMaterialRepairFlowIssue, ...]:
    issues: list[SceneMaterialRepairFlowIssue] = []
    seen_issue_keys: set[tuple[str, str, str]] = set()
    for row in report.rows:
        for issue_id in row.issue_ids:
            _append_issue(
                issues,
                seen_issue_keys,
                row.flow_id,
                issue_id,
                f"Material repair flow has unresolved issue: {issue_id}.",
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            _append_issue(
                issues,
                seen_issue_keys,
                evidence.flow_id,
                f"missing_source_evidence.{evidence.evidence_id}",
                f"Missing source markers: {', '.join(evidence.missing_markers)}",
            )
    return tuple(issues)


def _append_issue(
    issues: list[SceneMaterialRepairFlowIssue],
    seen: set[tuple[str, str, str]],
    flow_id: str,
    kind: str,
    message: str,
) -> None:
    key = (flow_id, kind, message)
    if key in seen:
        return
    seen.add(key)
    issues.append(
        SceneMaterialRepairFlowIssue(
            flow_id=flow_id,
            kind=kind,
            message=message,
        )
    )


def _row(
    spec: SceneMaterialRepairFlowSpec,
    material_report: SceneMaterialSchemaAuditReport,
    evidence: tuple[SceneMaterialRepairFlowEvidence, ...],
) -> SceneMaterialRepairFlowRow:
    pack_ids, family_ids = _coverage_links(spec.coverage_selector, material_report)
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
    if not spec.capability_ids:
        issue_ids.append("missing_capability_ids")
    if not spec.material_signal_ids:
        issue_ids.append("missing_material_signals")
    if not spec.repair_target_types:
        issue_ids.append("missing_repair_target_types")
    if not spec.runtime_surface_ids:
        issue_ids.append("missing_runtime_surfaces")
    if not spec.ui_surface_ids:
        issue_ids.append("missing_ui_surfaces")
    if not spec.test_ids:
        issue_ids.append("missing_test_evidence")
    return SceneMaterialRepairFlowRow(
        flow_id=spec.flow_id,
        label=spec.label,
        coverage_selector=spec.coverage_selector,
        pack_ids=pack_ids,
        family_ids=family_ids,
        capability_ids=spec.capability_ids,
        material_signal_ids=spec.material_signal_ids,
        repair_target_types=spec.repair_target_types,
        runtime_surface_ids=spec.runtime_surface_ids,
        ui_surface_ids=spec.ui_surface_ids,
        test_ids=spec.test_ids,
        evidence_ids=tuple(item.evidence_id for item in evidence),
        issue_ids=_unique_values(issue_ids),
    )


def _coverage_links(
    selector: str,
    material_report: SceneMaterialSchemaAuditReport,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    rows = tuple(row for row in material_report.family_rows if _family_matches_selector(row, selector))
    return (
        _unique_values(pack_id for row in rows for pack_id in row.pack_ids),
        _unique_values(row.family_id for row in rows),
    )


def _family_matches_selector(row, selector: str) -> bool:
    if selector == "material_fields":
        return bool(row.required_field_keys)
    if selector == "material_assets":
        return bool(row.required_asset_roles)
    if selector == "material_fields_or_assets":
        return bool(row.required_field_keys or row.required_asset_roles)
    if selector == "schema_reference":
        return bool(row.material_schema_ids)
    if selector == "batch_material":
        return row.family_id in BATCH_MATERIAL_FAMILY_IDS or bool(row.batch_modes)
    return bool(row.is_material_family)


def _source_evidence(
    specs: Iterable[SceneMaterialRepairFlowSpec],
    project_root: Path | str | None,
) -> tuple[SceneMaterialRepairFlowEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    evidence_specs = tuple(
        (spec.flow_id, item)
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
        SceneMaterialRepairFlowEvidence(
            flow_id=flow_id,
            evidence_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
            evidence_layer=item.evidence_layer,
        )
        for (flow_id, item), result in zip(evidence_specs, marker_results)
    )


def _evidence_by_flow(
    evidence: Iterable[SceneMaterialRepairFlowEvidence],
) -> dict[str, tuple[SceneMaterialRepairFlowEvidence, ...]]:
    grouped: dict[str, list[SceneMaterialRepairFlowEvidence]] = {}
    for item in evidence:
        grouped.setdefault(item.flow_id, []).append(item)
    return {key: tuple(value) for key, value in grouped.items()}


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "N2_177_MATERIAL_REPAIR_FLOW_SPECS",
    "SCENE_MATERIAL_REPAIR_FLOW_AUDIT_ID",
    "SceneMaterialRepairFlowAuditReport",
    "SceneMaterialRepairFlowEvidence",
    "SceneMaterialRepairFlowIssue",
    "SceneMaterialRepairFlowRow",
    "audit_scene_material_repair_flow_report",
    "build_scene_material_repair_flow_audit_report",
]
