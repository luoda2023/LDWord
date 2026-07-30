"""Runtime consistency audit for scene-facing control contracts.

N2.175 sits one layer below the static control-contract registry.  The
registry says which labels, units, owners, and disabled-state rules are
canonical; this audit verifies that scene/runtime surfaces are still wired to
the same shared controls, grouping rules, write-back paths, and boundary
consumers as template management.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.config.control_contract_registry import get_control_contract


SCENE_CONTROL_RUNTIME_AUDIT_ID = "scene_control_runtime_consistency_audit"


@dataclass(frozen=True, slots=True)
class SceneControlRuntimeEvidenceSpec:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    evidence_layer: str


@dataclass(frozen=True, slots=True)
class SceneControlRuntimeSpec:
    runtime_id: str
    label: str
    contract_ids: tuple[str, ...]
    scope: str
    required_semantics: tuple[str, ...]
    scene_surface_ids: tuple[str, ...]
    template_surface_ids: tuple[str, ...]
    shared_component_ids: tuple[str, ...]
    runtime_consumer_ids: tuple[str, ...]
    evidence: tuple[SceneControlRuntimeEvidenceSpec, ...]


@dataclass(frozen=True, slots=True)
class SceneControlRuntimeIssue:
    runtime_id: str
    contract_id: str
    kind: str
    message: str

    def to_payload(self) -> dict[str, object]:
        return {
            "runtime_id": self.runtime_id,
            "contract_id": self.contract_id,
            "kind": self.kind,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class SceneControlRuntimeEvidence:
    runtime_id: str
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
            "runtime_id": self.runtime_id,
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "evidence_layer": self.evidence_layer,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneControlRuntimeRow:
    runtime_id: str
    label: str
    contract_ids: tuple[str, ...]
    owner_layer_ids: tuple[str, ...]
    scope: str
    required_semantics: tuple[str, ...]
    scene_surface_ids: tuple[str, ...]
    template_surface_ids: tuple[str, ...]
    shared_component_ids: tuple[str, ...]
    runtime_consumer_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "runtime_id": self.runtime_id,
            "label": self.label,
            "contract_ids": list(self.contract_ids),
            "owner_layer_ids": list(self.owner_layer_ids),
            "scope": self.scope,
            "required_semantics": list(self.required_semantics),
            "scene_surface_ids": list(self.scene_surface_ids),
            "template_surface_ids": list(self.template_surface_ids),
            "shared_component_ids": list(self.shared_component_ids),
            "runtime_consumer_ids": list(self.runtime_consumer_ids),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneControlRuntimeConsistencyReport:
    rows: tuple[SceneControlRuntimeRow, ...]
    issues: tuple[SceneControlRuntimeIssue, ...]
    source_evidence: tuple[SceneControlRuntimeEvidence, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def runtime_control_count(self) -> int:
        return len(self.rows)

    @property
    def ready_runtime_control_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def control_contract_link_count(self) -> int:
        return len({contract_id for row in self.rows for contract_id in row.contract_ids})

    @property
    def scene_surface_count(self) -> int:
        return len({item for row in self.rows for item in row.scene_surface_ids})

    @property
    def template_surface_count(self) -> int:
        return len({item for row in self.rows for item in row.template_surface_ids})

    @property
    def shared_component_count(self) -> int:
        return len({item for row in self.rows for item in row.shared_component_ids})

    @property
    def runtime_consumer_count(self) -> int:
        return len({item for row in self.rows for item in row.runtime_consumer_ids})

    @property
    def source_evidence_count(self) -> int:
        return len(self.source_evidence)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    @property
    def owner_layer_counts(self) -> tuple[tuple[str, int], ...]:
        counts = Counter(layer for row in self.rows for layer in row.owner_layer_ids)
        return tuple(sorted(counts.items()))

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "runtime_control_count": self.runtime_control_count,
            "ready_runtime_control_count": self.ready_runtime_control_count,
            "issue_count": self.issue_count,
            "control_contract_link_count": self.control_contract_link_count,
            "scene_surface_count": self.scene_surface_count,
            "template_surface_count": self.template_surface_count,
            "shared_component_count": self.shared_component_count,
            "runtime_consumer_count": self.runtime_consumer_count,
            "source_evidence_count": self.source_evidence_count,
            "missing_source_evidence_count": self.missing_source_evidence_count,
            "counts": {
                "runtime_control_count": self.runtime_control_count,
                "ready_runtime_control_count": self.ready_runtime_control_count,
                "issue_count": self.issue_count,
                "control_contract_link_count": self.control_contract_link_count,
                "scene_surface_count": self.scene_surface_count,
                "template_surface_count": self.template_surface_count,
                "shared_component_count": self.shared_component_count,
                "runtime_consumer_count": self.runtime_consumer_count,
                "source_evidence_count": self.source_evidence_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "owner_layer_counts": [
                {"owner_layer": layer, "count": count}
                for layer, count in self.owner_layer_counts
            ],
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def _evidence(
    evidence_id: str,
    source_path: str,
    evidence_layer: str,
    *markers: str,
) -> SceneControlRuntimeEvidenceSpec:
    return SceneControlRuntimeEvidenceSpec(
        evidence_id=evidence_id,
        source_path=source_path,
        evidence_layer=evidence_layer,
        markers=tuple(markers),
    )


def _spec(
    runtime_id: str,
    label: str,
    contract_ids: tuple[str, ...],
    scope: str,
    required_semantics: tuple[str, ...],
    scene_surface_ids: tuple[str, ...],
    template_surface_ids: tuple[str, ...],
    shared_component_ids: tuple[str, ...],
    runtime_consumer_ids: tuple[str, ...],
    evidence: tuple[SceneControlRuntimeEvidenceSpec, ...],
) -> SceneControlRuntimeSpec:
    return SceneControlRuntimeSpec(
        runtime_id=runtime_id,
        label=label,
        contract_ids=contract_ids,
        scope=scope,
        required_semantics=required_semantics,
        scene_surface_ids=scene_surface_ids,
        template_surface_ids=template_surface_ids,
        shared_component_ids=shared_component_ids,
        runtime_consumer_ids=runtime_consumer_ids,
        evidence=evidence,
    )


N2_175_SCENE_CONTROL_RUNTIME_SPECS: tuple[SceneControlRuntimeSpec, ...] = (
    _spec(
        "fixed_layout_row_height_profile",
        "固定版位行高 profile",
        ("fixed_layout.table_row_height",),
        "fixed_layout_profile",
        (
            "not a generic TableConfig control",
            "only fixed-layout family/profile owns row_height_pt",
            "runtime writes or preserves Word w:trHeight",
            "N2.178 remains productization follow-up",
        ),
        ("FixedLayoutRowHeightPolicy.form_batch_documents",),
        ("not_generic_template_table_control",),
        ("FixedLayoutRowHeightPolicy", "OOXML helper"),
        (
            "form_batch_documents.table.row_height_pt",
            "apply_fixed_layout_row_height_policy",
            "word.w:trHeight",
        ),
        (
            _evidence(
                "row_height.fixed_layout_policy",
                "src/config/fixed_layout.py",
                "scene_profile",
                "FixedLayoutRowHeightPolicy",
                "form_batch_documents.table.row_height_pt",
                "w:trHeight",
                "without",
                "TableConfig.row_height_pt",
            ),
            _evidence(
                "row_height.ooxml_runtime",
                "src/shared/engine/fixed_layout_tables.py",
                "runtime_semantics",
                "apply_fixed_layout_row_height_policy",
                "set_fixed_layout_row_height",
                "w:trHeight",
                "preserve_existing",
            ),
            _evidence(
                "row_height.generic_table_test",
                "tests/test_table_format_semantics.py",
                "test",
                "test_table_config_no_longer_exposes_legacy_row_height_setting",
                "row_height_pt",
            ),
        ),
    ),
    _spec(
        "formula_policy_scene_controls",
        "公式策略方案策略",
        ("scene.formula_conversion_strategy",),
        "scene_policy",
        (
            "scene owns conversion/confidence/fallback policy",
            "template owns visual typography baseline",
            "full LaTeX/OCR/professional conversion remains plugin/manual gated",
        ),
        (
            "SceneWorkspace.formula_convert",
            "SceneWorkspace.formula_style",
            "Workbench formula confidence boundary",
        ),
        ("formula visual typography baseline",),
        ("StyledComboBox", "ToggleSwitch", "template_form_row"),
        (
            "scene.formula_convert.output_mode",
            "scene.formula_convert.low_confidence_policy",
            "scene.formula_convert.office_fallback_enabled",
            "plugin.manual_gate.full_latex_project_conversion",
        ),
        (
            _evidence(
                "formula.scene_policy",
                "src/config/scene.py",
                "scene_policy",
                "class FormulaConvertOptions",
                "output_mode",
                "low_confidence_policy",
                "office_fallback_enabled",
            ),
            _evidence(
                "formula.ownership",
                "src/config/scene_parameter_ownership.py",
                "ownership",
                "formula_convert.output_mode",
                "formula_style.unify_font",
            ),
            _evidence(
                "formula.plugin_gate",
                "src/config/plugin_manual_gate.py",
                "boundary",
                "full_latex_project_conversion",
                "confidence_report_required=True",
            ),
        ),
    ),
    _spec(
        "watermark_status_scene_controls",
        "水印状态方案控件",
        ("scene.watermark_status",),
        "scene_policy",
        (
            "scene owns business/status text",
            "disabled state keeps text but disables editor",
            "visual baseline remains template/control-contract language",
        ),
        ("ScenePanel._watermark_enabled", "ScenePanel._watermark_text"),
        ("watermark visual baseline",),
        ("ToggleSwitch", "QLineEdit", "template_form_row"),
        ("scene.watermark.enabled", "scene.watermark.text"),
        (
            _evidence(
                "watermark.scene_panel",
                "src/ui/panels/scene_content_detail.py",
                "scene_ui",
                "_watermark_enabled",
                "_watermark_text",
                '"水印文本"',
                "_sync_watermark_text_state",
                "self._watermark_text.setEnabled(enabled)",
            ),
            _evidence(
                "watermark.ownership",
                "src/config/scene_parameter_ownership.py",
                "ownership",
                "watermark.enabled",
                "watermark.text",
            ),
            _evidence(
                "watermark.family_defaults",
                "src/config/scene_family_application.py",
                "scene_defaults",
                "scene.watermark.enabled = True",
                'scene.watermark.text = "内部传阅"',
            ),
        ),
    ),
    _spec(
        "material_schema_selection_controls",
        "资料 Schema 选择控件",
        ("material.schema_selection",),
        "material_fact_source",
        (
            "material schema is a fact-source contract",
            "unknown schema enables replace/remove actions",
            "registered schema enables set/append actions",
        ),
        (
            "ScenePanel._schema_registry_combo",
            "ScenePanel._material_schema_id",
            "ScenePanel._material_schema_ids",
            "ScenePanel._replace_unknown_schema_btn",
        ),
        ("template line-edit contract",),
        ("StyledComboBox", "QLineEdit", "TextArea", "QPushButton"),
        (
            "scene.input_source_profile.material_schema_id",
            "scene.input_source_profile.material_schema_ids",
            "missing_material_schema_ids",
        ),
        (
            _evidence(
                "schema.scene_panel",
                "src/ui/panels/scene_content_detail.py",
                "scene_ui",
                "_schema_registry_combo",
                "_material_schema_id",
                "_set_primary_schema_btn",
                "_append_schema_btn",
                "_replace_unknown_schema_btn",
                "_sync_schema_registry_actions",
            ),
            _evidence(
                "schema.material_requirement_block",
                "src/ui/panels/scene_material_requirement_block.py",
                "scene_ui_block",
                "class _MaterialRequirementBlock",
                "def sync_actions",
                "def _build_material_schema_validation_items",
            ),
            _evidence(
                "schema.registry",
                "src/config/material_schema_registry.py",
                "registry",
                "class MaterialSchema",
                "resolve_material_schema_ids",
                "missing_material_schema_ids",
            ),
            _evidence(
                "schema.workbench_repair",
                "src/ui/adapters/workbench_material_issues.py",
                "runtime_repair",
                "missing_material_schema_ids",
                "repair_target_type=\"schema\"",
            ),
        ),
    ),
    _spec(
        "delivery_preset_controls",
        "输出版本 DeliveryPreset 控件",
        ("output.delivery_preset",),
        "output_policy",
        (
            "business versions are structured DeliveryPreset objects",
            "family default button is enabled only with planned-family defaults",
            "Workbench consumes delivery preset payloads",
        ),
        (
            "ScenePanel._default_delivery",
            "ScenePanel._apply_family_delivery_btn",
            "ScenePanel._delivery_summary",
        ),
        ("output artifact baseline",),
        ("StyledComboBox", "QPushButton", "SummaryGrid"),
        (
            "scene.default_delivery_preset_id",
            "scene.delivery_presets",
            "delivery_reporting.delivery_preset_payload",
        ),
        (
            _evidence(
                "delivery.scene_panel",
                "src/ui/panels/scene_output_detail.py",
                "scene_ui",
                "_default_delivery = StyledComboBox",
                "_apply_family_delivery_btn",
                "_delivery_summary",
                "build_delivery_summary_items",
                "self._apply_family_delivery_btn.setEnabled(",
            ),
            _evidence(
                "delivery.delivery_helpers",
                "src/ui/panels/scene_delivery_helpers.py",
                "scene_ui_helper",
                "_DELIVERY_PRESET_TEMPLATE_MAP",
                "def _populate_delivery_preset_template_combo",
                "def _scene_family_delivery_preview_tooltip",
            ),
            _evidence(
                "delivery.scene_model",
                "src/config/scene.py",
                "model",
                "class DeliveryPreset",
                "default_delivery_preset_id",
                "delivery_presets",
            ),
            _evidence(
                "delivery.workbench_runtime",
                "src/services/production_runtime/delivery_reporting.py",
                "runtime_semantics",
                "should_force_delivery_presets",
                "write_delivery_reports",
                "delivery_preset_payload",
            ),
        ),
    ),
    _spec(
        "content_visibility_rule_controls",
        "内容显隐规则控件",
        ("output.content_visibility_rules",),
        "output_policy",
        (
            "rules belong to the selected delivery preset",
            "selector/action are structured instead of ad hoc text promises",
            "runtime visibility engine consumes the same rule shape",
        ),
        (
            "ScenePanel._visibility_selector_input",
            "ScenePanel._visibility_action_combo",
            "ScenePanel._insert_visibility_rule_btn",
        ),
        ("delivery preset editor",),
        ("QLineEdit", "StyledComboBox", "QPushButton", "TextArea"),
        (
            "ContentVisibilityRule.selector",
            "ContentVisibilityRule.action",
            "content_visibility_rules",
        ),
        (
            _evidence(
                "visibility.scene_panel",
                "src/ui/panels/scene_output_detail.py",
                "scene_ui",
                "_visibility_selector_input",
                "_visibility_action_combo",
                "_insert_visibility_rule_btn",
                "_insert_visibility_rule",
            ),
            _evidence(
                "visibility.delivery_helpers",
                "src/ui/panels/scene_delivery_helpers.py",
                "scene_ui_helper",
                "def _parse_visibility_rules",
                "def _append_visibility_rule_text",
                "_VISIBILITY_ACTION_OPTIONS",
            ),
            _evidence(
                "visibility.scene_model",
                "src/config/scene.py",
                "model",
                "class ContentVisibilityRule",
                "content_visibility_rules",
            ),
            _evidence(
                "visibility.runtime",
                "src/shared/engine/content_visibility.py",
                "runtime_semantics",
                "content_visibility_rules",
                "selector",
                "action",
            ),
        ),
    ),
    _spec(
        "plugin_manual_gate_runtime_controls",
        "插件人工门运行时控件",
        ("plugin.manual_gate",),
        "plugin_boundary",
        (
            "high-risk work uses shared execution-gate/manual-confirmation semantics",
            "plugin boundary must not masquerade as core scene control",
            "reports preserve plugin_manual_gate payload",
        ),
        ("ExecutionGateDecision.primary_action=plugin_manual_gate",),
        ("coverage pack plugin boundary projection",),
        ("Workbench execution gate", "manual confirmation handoff"),
        (
            "plugin_manual_gate.*",
            "coverage_pack.plugin_boundary",
            "report.plugin_manual_gate",
        ),
        (
            _evidence(
                "plugin_gate.registry",
                "src/config/plugin_manual_gate.py",
                "boundary",
                "class PluginManualGate",
                "PLUGIN_MANUAL_GATES",
                "plugin_manual_gate_payload",
            ),
            _evidence(
                "plugin_gate.workbench",
                "src/ui/adapters/workbench_execution_gate.py",
                "runtime_repair",
                "class ExecutionGateDecision",
                "requires_confirmation",
                "primary_action",
            ),
            _evidence(
                "plugin_gate.report",
                "src/reporting/material_sections.py",
                "report",
                "_clean_plugin_manual_gate",
                "plugin_manual_gate",
            ),
        ),
    ),
)


def build_scene_control_runtime_consistency_audit_report(
    *,
    runtime_id: str = "",
    project_root: Path | None = None,
) -> SceneControlRuntimeConsistencyReport:
    root = project_root or Path(__file__).resolve().parents[2]
    requested_id = str(runtime_id or "").strip()
    specs = tuple(
        spec
        for spec in N2_175_SCENE_CONTROL_RUNTIME_SPECS
        if not requested_id or spec.runtime_id == requested_id
    )
    rows: list[SceneControlRuntimeRow] = []
    issues: list[SceneControlRuntimeIssue] = []
    evidence_items: list[SceneControlRuntimeEvidence] = []

    if requested_id and not specs:
        issues.append(
            SceneControlRuntimeIssue(
                runtime_id=requested_id,
                contract_id="*",
                kind="unknown_runtime_control",
                message=f"Unknown scene control runtime id: {requested_id}.",
            )
        )

    for spec in specs:
        row, row_issues, row_evidence = _build_row(spec, project_root=root)
        rows.append(row)
        issues.extend(row_issues)
        evidence_items.extend(row_evidence)

    return SceneControlRuntimeConsistencyReport(
        rows=tuple(rows),
        issues=tuple(issues),
        source_evidence=tuple(evidence_items),
    )


def audit_scene_control_runtime_consistency_report(
    report: SceneControlRuntimeConsistencyReport | None = None,
) -> tuple[SceneControlRuntimeIssue, ...]:
    report = report or build_scene_control_runtime_consistency_audit_report()
    return report.issues


def _build_row(
    spec: SceneControlRuntimeSpec,
    *,
    project_root: Path,
) -> tuple[
    SceneControlRuntimeRow,
    tuple[SceneControlRuntimeIssue, ...],
    tuple[SceneControlRuntimeEvidence, ...],
]:
    issues: list[SceneControlRuntimeIssue] = []
    issue_ids: list[str] = []
    owner_layers: list[str] = []

    for contract_id in spec.contract_ids:
        try:
            contract = get_control_contract(contract_id)
        except KeyError:
            _append_issue(
                issues,
                issue_ids,
                spec.runtime_id,
                contract_id,
                "missing_control_contract",
                "Runtime control references an unregistered control contract.",
            )
            continue
        owner_layers.append(contract.owner_layer)

    row_evidence: list[SceneControlRuntimeEvidence] = []
    for evidence_spec in spec.evidence:
        evidence = _resolve_evidence(spec.runtime_id, evidence_spec, project_root)
        row_evidence.append(evidence)
        if evidence.status != "ready":
            _append_issue(
                issues,
                issue_ids,
                spec.runtime_id,
                "*",
                f"missing_source_evidence.{evidence.evidence_id}",
                (
                    f"{evidence.source_path} is missing markers: "
                    + ", ".join(evidence.missing_markers)
                ),
            )

    if not spec.scene_surface_ids:
        _append_issue(
            issues,
            issue_ids,
            spec.runtime_id,
            "*",
            "missing_scene_surface",
            "Runtime control must expose a scene-facing surface.",
        )
    if not spec.required_semantics:
        _append_issue(
            issues,
            issue_ids,
            spec.runtime_id,
            "*",
            "missing_required_semantics",
            "Runtime control must state the semantics being guarded.",
        )

    return (
        SceneControlRuntimeRow(
            runtime_id=spec.runtime_id,
            label=spec.label,
            contract_ids=spec.contract_ids,
            owner_layer_ids=tuple(sorted(set(owner_layers))),
            scope=spec.scope,
            required_semantics=spec.required_semantics,
            scene_surface_ids=spec.scene_surface_ids,
            template_surface_ids=spec.template_surface_ids,
            shared_component_ids=spec.shared_component_ids,
            runtime_consumer_ids=spec.runtime_consumer_ids,
            evidence_ids=tuple(evidence.evidence_id for evidence in row_evidence),
            issue_ids=tuple(_unique_values(issue_ids)),
        ),
        tuple(issues),
        tuple(row_evidence),
    )


def _resolve_evidence(
    runtime_id: str,
    spec: SceneControlRuntimeEvidenceSpec,
    project_root: Path,
) -> SceneControlRuntimeEvidence:
    path = project_root / spec.source_path
    content = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    missing = tuple(marker for marker in spec.markers if marker not in content)
    if not path.exists() and "__source_file__" not in missing:
        missing = ("__source_file__", *missing)
    return SceneControlRuntimeEvidence(
        runtime_id=runtime_id,
        evidence_id=spec.evidence_id,
        source_path=spec.source_path,
        markers=spec.markers,
        missing_markers=missing,
        evidence_layer=spec.evidence_layer,
    )


def _append_issue(
    issues: list[SceneControlRuntimeIssue],
    issue_ids: list[str],
    runtime_id: str,
    contract_id: str,
    kind: str,
    message: str,
) -> None:
    issue_ids.append(kind)
    issues.append(
        SceneControlRuntimeIssue(
            runtime_id=runtime_id,
            contract_id=contract_id,
            kind=kind,
            message=message,
        )
    )


def _unique_values(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


__all__ = [
    "N2_175_SCENE_CONTROL_RUNTIME_SPECS",
    "SCENE_CONTROL_RUNTIME_AUDIT_ID",
    "SceneControlRuntimeConsistencyReport",
    "SceneControlRuntimeEvidence",
    "SceneControlRuntimeIssue",
    "SceneControlRuntimeRow",
    "audit_scene_control_runtime_consistency_report",
    "build_scene_control_runtime_consistency_audit_report",
]
