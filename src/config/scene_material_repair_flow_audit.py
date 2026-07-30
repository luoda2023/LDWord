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


N2_177_MATERIAL_REPAIR_FLOW_SPECS: tuple[SceneMaterialRepairFlowSpec, ...] = (
    _spec(
        "schema_requirements_to_assets_panel",
        "Material schemas validate the package-owned AssetsPanel inventory",
        "all_material",
        ("material_schema_projection", "package_owned_field_inventory", "required_asset_controls"),
        ("material_schema_id", "material_schema_ids", "required_material_fields", "required_image_roles"),
        ("field", "asset"),
        (
            "build_material_requirements",
            "project_material_field_inventory",
            "SceneSpecPresenterMixin._asset_slots_from_scene",
            "SceneSpecPresenterMixin._attachment_roles_from_scene",
        ),
        ("AssetsPanel profile card", "AssetsPanel image card", "AssetsPanel attachment roles"),
        (
            "test_material_requirement_evaluation_merges_schema_and_scene_overrides",
            "test_material_requirements_merge_multiple_schema_ids",
        ),
        (
            _evidence(
                "ui.assets.schema_requirements",
                "src/config/material_field_inventory.py",
                "ui",
                "def project_material_field_inventory",
                "Plans, masters,",
                "must never populate it",
            ),
            _evidence(
                "registry.material_requirements",
                "src/config/material_schema_registry.py",
                "registry",
                "def build_material_requirements",
                "required_field_keys",
                "required_asset_roles",
            ),
            _evidence(
                "test.assets.schema_requirements",
                "tests/test_material_schema_registry.py",
                "test",
                "def test_material_requirement_evaluation_merges_schema_and_scene_overrides",
                "def test_material_requirements_merge_multiple_schema_ids",
            ),
        ),
    ),
    _spec(
        "assets_panel_preview_missing_detection",
        "AssetsPanel preview detects missing fields, assets, and next repair target",
        "material_fields_or_assets",
        ("material_preview_validation", "missing_target_priority", "placeholder_feedback"),
        ("package_field_inventory", "missing_asset_roles", "unmatched_placeholders"),
        ("field", "asset", "preview"),
        ("AssetsPanel._current_preview_state", "AssetsPanel._next_missing_target"),
        ("AssetsPanel preview table", "AssetsPanel attention card"),
        (
            "test_material_repair_navigation_presenter_owns_preview_missing_target_methods",
            "test_material_repair_navigation_presenter_owns_asset_focus_methods",
            "test_material_repair_navigation_presenter_owns_question_figure_target_methods",
        ),
        (
            _evidence(
                "ui.assets.preview_state",
                "src/ui/panels/assets/material_repair_navigation_presenter.py",
                "ui",
                "def _focus_missing_content",
                "missing_asset_roles",
                "unmatched_placeholders",
                "def _next_missing_target",
            ),
            _evidence(
                "test.assets.preview_state",
                "tests/test_assets_panel_helper_modules.py",
                "test",
                "def test_material_repair_navigation_presenter_owns_preview_missing_target_methods",
                "def test_material_repair_navigation_presenter_owns_asset_focus_methods",
                "def test_material_repair_navigation_presenter_owns_question_figure_target_methods",
            ),
        ),
    ),
    _spec(
        "workbench_material_readiness_groups",
        "Workbench groups missing schema, field, asset, and source notes",
        "all_material",
        ("material_readiness_grouping", "schema_recommendation", "runtime_preflight"),
        ("schema_ids", "field_keys", "asset_roles", "source_notes"),
        ("field", "asset", "schema"),
        (
            "material_readiness_issue_groups",
            "evaluate_material_requirements",
            "recommend_material_schema_replacement",
        ),
        ("QuickExecutionDetail status label",),
        (
            "test_material_schema_readiness_reasons_reports_unknown_schema",
            "test_material_readiness_reasons_reports_missing_fields_and_assets",
            "test_material_readiness_issue_groups_recommend_schema_replacement",
        ),
        (
            _evidence(
                "runtime.workbench.material_groups",
                "src/ui/adapters/workbench_material_issues.py",
                "runtime",
                "def material_readiness_issue_groups",
                "evaluate_material_requirements(",
                "def _missing_scene_material_schema_ids",
                "recommend_material_schema_replacement(",
            ),
            _evidence(
                "test.workbench.material_groups",
                "tests/test_workbench_execution_center.py",
                "test",
                "def test_material_schema_readiness_reasons_reports_unknown_schema",
                "def test_material_readiness_reasons_reports_missing_fields_and_assets",
                "def test_material_readiness_issue_groups_recommend_schema_replacement",
            ),
        ),
    ),
    _spec(
        "execution_gate_policy_semantics",
        "Material readiness follows the unified execution-gate policy",
        "all_material",
        (
            "unified_execution_gate",
            "policy_aware_material_readiness",
            "shared_gate_decision",
        ),
        ("failure_policy", "can_run", "blocking_reasons", "warning_reasons"),
        ("field", "asset", "schema"),
        ("material_readiness_gate_decision", "decide_execution_gate_for_policy"),
        ("QuickExecutionDetail compact readiness status",),
        (
            "test_execution_gate_warn_policy_allows_run",
            "test_execution_gate_block_policy_prevents_run",
            "test_material_readiness_gate_matches_warn_issue_contract",
            "test_material_readiness_gate_matches_block_issue_contract",
        ),
        (
            _evidence(
                "runtime.workbench.execution_gate",
                "src/ui/adapters/workbench_execution_gate.py",
                "runtime",
                "class ExecutionGateDecision",
                "def decide_execution_gate_for_policy",
                "can_run",
                "blocking_reasons",
                "warning_reasons",
                "primary_action",
            ),
            _evidence(
                "runtime.workbench.material_gate",
                "src/ui/adapters/workbench_material_issues.py",
                "runtime",
                "def material_readiness_gate_decision",
                "failure_policy",
                "decide_execution_gate_for_policy",
            ),
            _evidence(
                "test.workbench.execution_gate",
                "tests/test_workbench_execution_gate.py",
                "test",
                "def test_execution_gate_warn_policy_allows_run",
                "def test_execution_gate_block_policy_prevents_run",
                "def test_material_readiness_gate_matches_warn_issue_contract",
                "def test_material_readiness_gate_matches_block_issue_contract",
            ),
        ),
    ),
    _spec(
        "execution_result_detail_access",
        "Post-run diagnostics remain available through inline status and logs",
        "all_material",
        ("inline_result_feedback", "post_run_diagnostic_access", "collapsed_execution_log"),
        ("result_status", "execution_log", "issue_items", "error_text"),
        ("field", "asset", "schema", "profile_field", "profile_asset", "profile_schema"),
        (
            "QuickExecutionDetail.set_execution_result",
            "WorkbenchExecutionAdapter.build_result_state",
        ),
        (
            "QuickExecutionDetail inline status",
            "QuickExecutionDetail execution log",
        ),
        (
            "test_quick_execution_detail_keeps_result_feedback_inline",
            "test_quick_execution_detail_log_is_collapsed_until_requested_or_failed",
        ),
        (
            _evidence(
                "ui.quick_detail.result_presenter_status",
                "src/ui/panels/workbench/quick_execution_result_presenter.py",
                "ui_presenter",
                "def build_execution_result_presentation",
                "✓ 本次生成完成",
                "status_tone = \"success\"",
            ),
            _evidence(
                "ui.quick_detail.execution_log",
                "src/ui/panels/workbench/quick_execution_feedback_mixin.py",
                "ui",
                "def _append_exec_log",
                "def _set_log_expanded",
                "self._set_log_expanded(True)",
            ),
            _evidence(
                "runtime.execution_result_state",
                "src/ui/panels/workbench/execution_controller.py",
                "runtime",
                "def apply_execution_result",
                "self._feedback_surface().set_execution_result(result_state)",
            ),
            _evidence(
                "test.quick_detail.inline_result",
                "tests/test_quick_execution_detail_architecture.py",
                "test",
                "def test_quick_execution_detail_keeps_result_feedback_inline",
            ),
            _evidence(
                "test.quick_detail.execution_log",
                "tests/test_quick_execution_detail_architecture.py",
                "test",
                "def test_quick_execution_detail_log_is_collapsed_until_requested_or_failed",
            ),
        ),
    ),
    _spec(
        "quick_material_repair_button",
        "QuickExecutionDetail exposes one contextual material repair action",
        "all_material",
        ("compact_primary_action", "material_gap_tooltip", "field_asset_priority"),
        ("detail_lines", "field_keys", "asset_roles", "recommendation_schema_id"),
        ("field", "asset", "content_fill"),
        ("material_readiness_issue_groups", "QuickExecutionDetail._request_material_repair"),
        ("QuickExecutionDetail material primary action",),
        (
            "test_quick_execution_detail_shows_schema_replacement_recommendation_in_repair_tooltip",
            "test_quick_execution_detail_exposes_one_material_cta_only",
        ),
        (
            _evidence(
                "ui.quick_detail.material_repair_button",
                "src/ui/panels/workbench/quick_execution_detail.py",
                "ui",
                "_material_repair_btn = QPushButton(",
                "def _request_material_repair",
                "material_repair_requested.emit",
            ),
            _evidence(
                "test.quick_detail.material_repair_button",
                "tests/test_quick_execution_detail_architecture.py",
                "test",
                "def test_quick_execution_detail_shows_schema_replacement_recommendation_in_repair_tooltip",
                "def test_quick_execution_detail_exposes_one_material_cta_only",
            ),
        ),
    ),
    _spec(
        "panel_bridge_material_routing",
        "Workbench routes the single material repair action through PanelBridge",
        "all_material",
        ("panel_bridge_repair_routing", "schema_scene_content_route", "profile_target_routing"),
        ("material_repair_requested", "material_repair_target_requested", "material_profile_repair_target_requested"),
        ("field", "asset", "schema", "profile_field", "profile_asset", "profile_schema"),
        ("WorkbenchPanel._open_material_repair_target", "PanelBridge.request_material_repair_target"),
        ("Assets panel navigation", "Scene content detail"),
        (
            "test_workbench_panel_routes_quick_asset_repair_to_core_content_fill",
            "test_workbench_panel_routes_quick_field_repair_to_core_content_fill",
            "test_workbench_panel_routes_schema_issue_repair_to_scene_content",
        ),
        (
            _evidence(
                "ui.workbench.panel_material_routing",
                "src/ui/panels/workbench/panel_v2.py",
                "ui",
                "def _open_material_repair_target",
                "request_material_repair_target",
                "request_material_profile_repair_target",
            ),
            _evidence(
                "ui.bridge.material_targets",
                "src/ui/bridge.py",
                "ui",
                "material_repair_target_requested",
                "material_profile_repair_target_requested",
                "def request_material_repair_target",
                "def request_material_profile_repair_target",
            ),
            _evidence(
                "test.workbench.panel_material_routing",
                "tests/test_workbench_execution_session_architecture.py",
                "test",
                "def test_workbench_panel_routes_quick_asset_repair_to_core_content_fill",
                "def test_workbench_panel_routes_quick_field_repair_to_core_content_fill",
                "def test_workbench_panel_routes_schema_issue_repair_to_scene_content",
            ),
        ),
    ),
    _spec(
        "assets_panel_target_focus",
        "AssetsPanel consumes repair targets and focuses field, asset, or profile rows",
        "material_fields_or_assets",
        ("repair_target_focus", "profile_repair_focus", "bridge_target_consumption"),
        ("current_material_repair_target", "current_material_profile_repair_target"),
        ("field", "asset", "profile_field", "profile_asset"),
        (
            "AssetsPanel.focus_material_repair_target",
            "AssetsPanel.focus_material_profile_repair_target",
        ),
        ("AssetsPanel profile card", "AssetsPanel image card"),
        (
            "test_material_repair_navigation_presenter_owns_bridge_target_consumption_methods",
            "test_material_repair_navigation_presenter_owns_focus_card_methods",
            "test_assets_panel_uses_material_repair_navigation_mixin",
        ),
        (
            _evidence(
                "ui.assets.target_focus",
                "src/ui/panels/assets/material_repair_navigation_presenter.py",
                "ui",
                "def focus_material_repair_target",
                "def focus_material_profile_repair_target",
                "consume_material_repair_target",
                "consume_material_profile_repair_target",
                "def _focus_asset_slot",
                "def _focus_attachment_role",
            ),
            _evidence(
                "test.assets.target_focus",
                "tests/test_assets_panel_helper_modules.py",
                "test",
                "def test_material_repair_navigation_presenter_owns_bridge_target_consumption_methods",
                "def test_material_repair_navigation_presenter_owns_focus_card_methods",
                "def test_assets_panel_uses_material_repair_navigation_mixin",
            ),
        ),
    ),
    _spec(
        "schema_replacement_recommendation_flow",
        "Unknown schema ids feed the gate primary action and schema repair route",
        "schema_reference",
        ("schema_alias_recommendation", "policy_aware_schema_gate", "schema_repair_target"),
        ("missing_schema_ids", "recommendation_schema_id", "recommendation_reasons"),
        ("schema", "content_fill"),
        ("recommend_material_schema_replacement", "material_readiness_gate_decision"),
        ("QuickExecutionDetail material primary action", "Scene content schema controls"),
        (
            "test_material_readiness_issue_groups_recommend_schema_replacement",
            "test_material_readiness_gate_matches_block_issue_contract",
            "test_quick_execution_detail_shows_schema_replacement_recommendation_in_repair_tooltip",
        ),
        (
            _evidence(
                "registry.material_schema_recommendation",
                "src/config/material_schema_registry.py",
                "registry",
                "def recommend_material_schema_replacement",
                "aliases",
                "alias_hits",
                "family_hints",
            ),
            _evidence(
                "runtime.workbench.schema_recommendation",
                "src/ui/adapters/workbench_material_issues.py",
                "runtime",
                "material_readiness_gate_decision",
                "recommendation_schema_id",
                "recommendation_reasons",
            ),
            _evidence(
                "test.schema_recommendation",
                "tests/test_workbench_execution_center.py",
                "test",
                "def test_material_readiness_issue_groups_recommend_schema_replacement",
            ),
            _evidence(
                "test.schema_gate",
                "tests/test_workbench_execution_gate.py",
                "test",
                "def test_material_readiness_gate_matches_block_issue_contract",
            ),
            _evidence(
                "test.quick_detail.schema_recommendation",
                "tests/test_quick_execution_detail_architecture.py",
                "test",
                "def test_quick_execution_detail_shows_schema_replacement_recommendation_in_repair_tooltip",
                "signature_assets_v2",
            ),
        ),
    ),
    _spec(
        "batch_profile_material_repair_targets",
        "Batch material failures preserve repair targets in result state and logs",
        "batch_material",
        ("batch_profile_repair", "failed_record_isolation", "profile_scoped_target"),
        ("batch_issue_items", "profile_id", "profile_name", "repair_target_key"),
        ("profile_field", "profile_asset", "profile_schema"),
        ("batch_execution_issue_items", "QuickExecutionDetail.set_execution_result"),
        ("QuickExecutionDetail execution log", "AssetsPanel profile selection"),
        (
            "test_execution_adapter_converts_batch_issue_payloads_to_workbench_issues",
            "test_quick_execution_detail_keeps_result_feedback_inline",
        ),
        (
            _evidence(
                "runtime.workbench.batch_issue_items",
                "src/ui/adapters/workbench_execution_adapter.py",
                "runtime",
                "def batch_execution_issue_items",
                "profile_id",
                "profile_name",
                "repair_target_type",
                "repair_target_key",
            ),
            _evidence(
                "test.workbench.batch_issue_items",
                "tests/test_workbench_execution_center.py",
                "test",
                "def test_execution_adapter_converts_batch_issue_payloads_to_workbench_issues",
                "profile_field",
            ),
            _evidence(
                "ui.quick_detail.batch_issue_items",
                "src/ui/panels/workbench/quick_execution_feedback_mixin.py",
                "ui",
                "def set_execution_result",
                "_last_result_issue_count",
            ),
            _evidence(
                "test.quick_detail.batch_issue_items",
                "tests/test_quick_execution_detail_architecture.py",
                "test",
                "def test_quick_execution_detail_keeps_result_feedback_inline",
            ),
        ),
    ),
    _spec(
        "material_manifest_feedback",
        "Material manifests carry schema, missing data, diagnostics, and delivery feedback",
        "all_material",
        ("material_manifest_feedback", "delivery_feedback", "diagnostics_summary"),
        ("material_manifest_paths", "material_package_paths", "material_diagnostics", "missing"),
        ("field", "asset", "schema"),
        ("WorkbenchProductionRunner._write_material_manifest", "_material_manifest_payload"),
        ("QuickExecutionDetail artifact log", "material package artifact browser"),
        (
            "test_workbench_runner_writes_technical_long_document_delivery_package",
            "test_workbench_runner_writes_product_pre_sales_delivery_package",
        ),
        (
            _evidence(
                "runtime.material_manifest_feedback",
                "src/services/production_runtime/material_artifacts.py",
                "runtime",
                "def _material_manifest_payload",
                "def _manifest_document_payload",
                "\"fields\": schema_state.fields_payload",
                "\"asset_roles\": domain_state.asset_roles_payload",
                "\"missing\": {",
                "\"diagnostics\": material_diagnostics",
                "\"delivery\": _manifest_delivery_payload(",
            ),
            _evidence(
                "test.material_manifest_feedback",
                "tests/test_output_runtime_semantics.py",
                "test",
                "def test_workbench_runner_writes_technical_long_document_delivery_package",
                "def test_workbench_runner_writes_product_pre_sales_delivery_package",
                "material_manifest_paths",
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
