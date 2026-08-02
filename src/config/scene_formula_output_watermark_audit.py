"""Formula/output/watermark ownership audit for high-frequency scenes.

N2.168 keeps formula, output, and watermark settings from drifting back into a
miscellaneous template bucket.  The audit proves ownership, UI/control
contracts, execution consumers, plugin/manual boundaries, and family routing for
the three capability domains.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config.control_contract_registry import (
    audit_control_contract_registry,
    get_control_contract,
)
from src.config.plugin_manual_gate import list_plugin_manual_gates
from src.config.scene_family_application import planned_family_is_plugin_boundary_only
from src.config.scene_family_registry import (
    PlannedSceneFamily,
    list_planned_scene_families,
)
from src.config.scene_parameter_ownership import (
    audit_parameter_execution_consumers,
    classify_scene_parameter,
    scene_parameter_ownership_specs,
)
from src.config.scene_coverage_manifest import coverage_packs_for_family
from src.config.scene_source_evidence import scan_scene_source_markers


SCENE_FORMULA_OUTPUT_WATERMARK_AUDIT_SOURCE_ID = (
    "scene_formula_output_watermark_audit"
)

SCENE_FORMULA_OUTPUT_WATERMARK_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "scene_parameter_ownership",
        "src/config/scene_parameter_ownership.py",
        (
            "thesis_formula_rules.formula_convert.output_mode",
            "watermark.enabled",
            "delivery_presets.*.artifacts.final_docx",
        ),
    ),
    (
        "control_contract_registry",
        "src/config/control_contract_registry.py",
        (
            "scene.formula_conversion_strategy",
            "scene.watermark_status",
            "output.delivery_preset",
        ),
    ),
    (
        "scene_model",
        "src/config/formula_policy.py",
        ("class ThesisFormulaRules", "formula_table", "chem_typography"),
    ),
    (
        "resolver_scene_feature_overrides",
        "src/config/resolver.py",
        ("_resolved_formula_rules", "THESIS_FORMULA_MODULE_NAMES", "watermark"),
    ),
    (
        "formula_execution",
        "src/modules/special/equation_table_format.py",
        ("formula_style", "equation_numbering", "EquationTablePlan"),
    ),
    (
        "watermark_execution",
        "src/modules/insert/watermark.py",
        ("class WatermarkModule", "config.watermark", "_inject_text_watermark"),
    ),
    (
        "output_execution",
        "src/services/production_runtime/delivery_reporting.py",
        ("should_force_delivery_presets", "delivery_preset_payload", "output_paths"),
    ),
    (
        "plugin_manual_gate",
        "src/config/plugin_manual_gate.py",
        ("full_latex_conversion", "complex_diagram_generation", "manual_decision"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneFormulaOutputWatermarkIssue:
    scope_type: str
    scope_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneFormulaOutputWatermarkSourceEvidence:
    source_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]
    status: str

    def to_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class FormulaOutputWatermarkCapabilitySpec:
    capability_id: str
    label: str
    expected_owner_layer: str
    parameter_paths: tuple[str, ...]
    template_baseline_paths: tuple[str, ...]
    control_contract_ids: tuple[str, ...]
    execution_consumers: tuple[str, ...]
    family_predicate: Callable[[PlannedSceneFamily], bool]
    plugin_risk_domain_ids: tuple[str, ...] = ()
    boundary_note: str = ""


@dataclass(frozen=True, slots=True)
class SceneFormulaOutputWatermarkCapabilityRow:
    capability_id: str
    label: str
    status: str
    expected_owner_layer: str
    parameter_paths: tuple[str, ...]
    template_baseline_paths: tuple[str, ...]
    control_contract_ids: tuple[str, ...]
    execution_consumers: tuple[str, ...]
    family_ids: tuple[str, ...]
    pack_ids: tuple[str, ...]
    plugin_gate_ids: tuple[str, ...]
    plugin_risk_domain_ids: tuple[str, ...]
    boundary_note: str
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "label": self.label,
            "status": self.status,
            "expected_owner_layer": self.expected_owner_layer,
            "parameter_paths": list(self.parameter_paths),
            "template_baseline_paths": list(self.template_baseline_paths),
            "control_contract_ids": list(self.control_contract_ids),
            "execution_consumers": list(self.execution_consumers),
            "family_ids": list(self.family_ids),
            "pack_ids": list(self.pack_ids),
            "plugin_gate_ids": list(self.plugin_gate_ids),
            "plugin_risk_domain_ids": list(self.plugin_risk_domain_ids),
            "boundary_note": self.boundary_note,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneFormulaOutputWatermarkFamilyRow:
    family_id: str
    name: str
    priority: str
    status: str
    pack_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    formula_relevant: bool
    output_relevant: bool
    watermark_relevant: bool
    plugin_boundary_only: bool
    delivery_preset_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "capability_ids": list(self.capability_ids),
            "formula_relevant": self.formula_relevant,
            "output_relevant": self.output_relevant,
            "watermark_relevant": self.watermark_relevant,
            "plugin_boundary_only": self.plugin_boundary_only,
            "delivery_preset_ids": list(self.delivery_preset_ids),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneFormulaOutputWatermarkAuditReport:
    capability_rows: tuple[SceneFormulaOutputWatermarkCapabilityRow, ...]
    family_rows: tuple[SceneFormulaOutputWatermarkFamilyRow, ...]
    issues: tuple[SceneFormulaOutputWatermarkIssue, ...]
    warnings: tuple[SceneFormulaOutputWatermarkIssue, ...]
    source_evidence: tuple[SceneFormulaOutputWatermarkSourceEvidence, ...]
    capability_filter: str = ""
    family_filter: str = ""
    pack_filter: str = ""
    total_family_count: int = 0

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def capability_count(self) -> int:
        return len(self.capability_rows)

    @property
    def ready_capability_count(self) -> int:
        return sum(1 for row in self.capability_rows if row.status == "ready")

    @property
    def family_count(self) -> int:
        return len(self.family_rows)

    @property
    def ready_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.status == "ready")

    @property
    def boundary_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.status == "boundary")

    @property
    def accounted_family_count(self) -> int:
        return self.ready_family_count + self.boundary_family_count

    @property
    def formula_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.formula_relevant)

    @property
    def output_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.output_relevant)

    @property
    def watermark_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.watermark_relevant)

    @property
    def plugin_gate_count(self) -> int:
        return len(
            _unique_values(
                gate_id
                for row in self.capability_rows
                for gate_id in row.plugin_gate_ids
            )
        )

    @property
    def control_contract_count(self) -> int:
        return len(
            _unique_values(
                contract_id
                for row in self.capability_rows
                for contract_id in row.control_contract_ids
            )
        )

    @property
    def parameter_path_count(self) -> int:
        return len(
            _unique_values(
                path
                for row in self.capability_rows
                for path in row.parameter_paths
            )
        )

    @property
    def template_baseline_path_count(self) -> int:
        return len(
            _unique_values(
                path
                for row in self.capability_rows
                for path in row.template_baseline_paths
            )
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_FORMULA_OUTPUT_WATERMARK_AUDIT_SOURCE_ID,
            "capability_filter": self.capability_filter,
            "family_filter": self.family_filter,
            "pack_filter": self.pack_filter,
            "counts": {
                "capability_count": self.capability_count,
                "ready_capability_count": self.ready_capability_count,
                "family_count": self.family_count,
                "total_family_count": self.total_family_count,
                "ready_family_count": self.ready_family_count,
                "boundary_family_count": self.boundary_family_count,
                "accounted_family_count": self.accounted_family_count,
                "formula_family_count": self.formula_family_count,
                "output_family_count": self.output_family_count,
                "watermark_family_count": self.watermark_family_count,
                "plugin_gate_count": self.plugin_gate_count,
                "control_contract_count": self.control_contract_count,
                "parameter_path_count": self.parameter_path_count,
                "template_baseline_path_count": self.template_baseline_path_count,
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "capability_rows": [row.to_payload() for row in self.capability_rows],
            "family_rows": [row.to_payload() for row in self.family_rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_formula_output_watermark_audit_report(
    *,
    capability_id: str = "",
    family_id: str = "",
    pack_id: str = "",
    project_root: Path | str | None = None,
) -> SceneFormulaOutputWatermarkAuditReport:
    normalized_capability = str(capability_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_pack = str(pack_id or "").strip()

    families = list_planned_scene_families()
    capability_rows = tuple(_capability_row(spec, families) for spec in _CAPABILITY_SPECS)
    family_rows = tuple(_family_row(family) for family in families)

    capability_rows = _filter_capability_rows(
        capability_rows,
        capability_id=normalized_capability,
        family_id=normalized_family,
        pack_id=normalized_pack,
    )
    family_rows = _filter_family_rows(
        family_rows,
        capability_id=normalized_capability,
        family_id=normalized_family,
        pack_id=normalized_pack,
    )
    source_evidence = _source_evidence(project_root)
    issues, warnings = audit_scene_formula_output_watermark_report(
        SceneFormulaOutputWatermarkAuditReport(
            capability_rows=capability_rows,
            family_rows=family_rows,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            capability_filter=normalized_capability,
            family_filter=normalized_family,
            pack_filter=normalized_pack,
            total_family_count=len(families),
        )
    )
    return SceneFormulaOutputWatermarkAuditReport(
        capability_rows=capability_rows,
        family_rows=family_rows,
        issues=issues,
        warnings=warnings,
        source_evidence=source_evidence,
        capability_filter=normalized_capability,
        family_filter=normalized_family,
        pack_filter=normalized_pack,
        total_family_count=len(families),
    )


def audit_scene_formula_output_watermark_report(
    report: SceneFormulaOutputWatermarkAuditReport,
) -> tuple[
    tuple[SceneFormulaOutputWatermarkIssue, ...],
    tuple[SceneFormulaOutputWatermarkIssue, ...],
]:
    issues: list[SceneFormulaOutputWatermarkIssue] = []
    warnings: list[SceneFormulaOutputWatermarkIssue] = []
    for row in report.capability_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneFormulaOutputWatermarkIssue(
                    "capability",
                    row.capability_id,
                    issue_id,
                    f"Formula/output/watermark capability has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneFormulaOutputWatermarkIssue(
                    "capability",
                    row.capability_id,
                    warning_id,
                    f"Formula/output/watermark capability has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for row in report.family_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneFormulaOutputWatermarkIssue(
                    "family",
                    row.family_id,
                    issue_id,
                    f"Formula/output/watermark family row has unresolved issue: {issue_id}.",
                )
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneFormulaOutputWatermarkIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    f"Missing source markers: {', '.join(evidence.missing_markers)}",
                )
            )
    return tuple(issues), tuple(warnings)


def _formula_relevant(family: PlannedSceneFamily) -> bool:
    return family.family_id == "thesis_cn"


def _output_relevant(family: PlannedSceneFamily) -> bool:
    return bool(family.delivery_presets)


def _watermark_relevant(family: PlannedSceneFamily) -> bool:
    return family.family_id == "meeting_policy_documents" or (
        "formal_internal_delivery" in family.workflow_archetypes
    )


_CAPABILITY_SPECS: tuple[FormulaOutputWatermarkCapabilitySpec, ...] = (
    FormulaOutputWatermarkCapabilitySpec(
        capability_id="formula_policy",
        label="Formula conversion and formula style policy",
        expected_owner_layer="scene",
        parameter_paths=(
            "thesis_formula_rules.formula_enabled",
            "thesis_formula_rules.formula_convert.enabled",
            "thesis_formula_rules.formula_convert.output_mode",
            "thesis_formula_rules.formula_convert.low_confidence_policy",
            "thesis_formula_rules.formula_convert.office_fallback_enabled",
            "thesis_formula_rules.formula_to_table.enabled",
            "thesis_formula_rules.formula_to_table.block_only",
            "thesis_formula_rules.formula_table.formula_font_name",
            "thesis_formula_rules.formula_table.formula_font_size_pt",
            "thesis_formula_rules.formula_style.unify_font",
            "thesis_formula_rules.formula_style.enabled",
            "thesis_formula_rules.formula_style.unify_size",
            "thesis_formula_rules.formula_style.unify_spacing",
            "thesis_formula_rules.equation_numbering.numbering_format",
            "thesis_formula_rules.equation_numbering.enabled",
            "thesis_formula_rules.chem_typography.enabled",
            "thesis_formula_rules.chem_typography.scopes",
        ),
        template_baseline_paths=(),
        control_contract_ids=("scene.formula_conversion_strategy",),
        execution_consumers=(
            "formula conversion",
            "formula module",
            "formula table module",
            "equation numbering module",
        ),
        family_predicate=_formula_relevant,
        plugin_risk_domain_ids=(
            "full_latex_conversion",
            "complex_diagram_generation",
            "ai_content_quality",
        ),
        boundary_note=(
            "The thesis plan exclusively owns formula and script-recovery policy; full LaTeX/OCR/AI quality remains plugin/manual gated."
        ),
    ),
    FormulaOutputWatermarkCapabilitySpec(
        capability_id="output_delivery",
        label="Output delivery and artifact versions",
        expected_owner_layer="output",
        parameter_paths=(
            "default_delivery_preset_id",
            "delivery_presets.*.target_template_id",
            "delivery_presets.*.output_dir_template",
            "delivery_presets.*.filename_template",
            "delivery_presets.*.artifacts",
            "delivery_presets.*.content_visibility_rules",
            "delivery_presets.*.include_structured_intermediate",
            "delivery_presets.*.report_level",
            "delivery_presets.*.artifacts.final_docx",
            "delivery_presets.*.artifacts.compare_docx",
            "delivery_presets.*.artifacts.report_json",
            "delivery_presets.*.artifacts.report_markdown",
            "delivery_presets.*.artifacts.material_manifest",
            "delivery_presets.*.artifacts.material_package",
        ),
        template_baseline_paths=(),
        control_contract_ids=(
            "output.delivery_preset",
            "output.content_visibility_rules",
        ),
        execution_consumers=(
            "workbench runner",
            "content visibility engine",
            "report writer",
        ),
        family_predicate=_output_relevant,
        boundary_note=(
            "Business versions are DeliveryPreset rows; compare/report/package flags stay artifact-level."
        ),
    ),
    FormulaOutputWatermarkCapabilitySpec(
        capability_id="watermark_status",
        label="Watermark status and delivery marker",
        expected_owner_layer="scene",
        parameter_paths=(
            "watermark.enabled",
            "watermark.text",
            "watermark.color",
            "watermark.rotation",
            "watermark.font_size",
        ),
        template_baseline_paths=(),
        control_contract_ids=("scene.watermark_status",),
        execution_consumers=("watermark module",),
        family_predicate=_watermark_relevant,
        boundary_note=(
            "Scene owns watermark status text; visual styling still follows shared control language."
        ),
    ),
)


def _capability_row(
    spec: FormulaOutputWatermarkCapabilitySpec,
    families: Sequence[PlannedSceneFamily],
) -> SceneFormulaOutputWatermarkCapabilityRow:
    matched_families = tuple(family for family in families if spec.family_predicate(family))
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    ownership_specs = scene_parameter_ownership_specs()
    consumer_audit = audit_parameter_execution_consumers()
    control_audit = audit_control_contract_registry()

    for path in spec.parameter_paths:
        owner = classify_scene_parameter(path)
        if owner is None:
            issue_ids.append(f"missing_parameter_ownership.{path}")
        elif owner.owner_layer != spec.expected_owner_layer:
            issue_ids.append(
                f"wrong_parameter_owner.{path}.{owner.owner_layer}"
            )
    for path in spec.template_baseline_paths:
        owner = classify_scene_parameter(path)
        if owner is None:
            issue_ids.append(f"missing_template_baseline_ownership.{path}")
        elif owner.owner_layer != "template":
            issue_ids.append(
                f"wrong_template_baseline_owner.{path}.{owner.owner_layer}"
            )
    for consumer in spec.execution_consumers:
        if consumer in consumer_audit.missing_consumers:
            issue_ids.append(f"missing_execution_consumer.{consumer}")
    if not consumer_audit.is_clean:
        issue_ids.append("parameter_consumer_anchor_audit_failed")
    if not control_audit.is_clean:
        issue_ids.append("control_contract_audit_failed")
    for contract_id in spec.control_contract_ids:
        try:
            contract = get_control_contract(contract_id)
        except KeyError:
            issue_ids.append(f"missing_control_contract.{contract_id}")
            continue
        if contract.owner_layer != spec.expected_owner_layer:
            issue_ids.append(
                f"wrong_control_contract_owner.{contract_id}.{contract.owner_layer}"
            )
    if not matched_families:
        warning_ids.append("capability_has_no_family_routes")
    if not all(path in ownership_specs for path in spec.parameter_paths):
        missing = tuple(path for path in spec.parameter_paths if path not in ownership_specs)
        issue_ids.extend(f"missing_explicit_spec.{path}" for path in missing)

    plugin_gate_ids = _plugin_gate_ids_for_risks(spec.plugin_risk_domain_ids)
    if spec.plugin_risk_domain_ids and not plugin_gate_ids:
        issue_ids.append("plugin_boundary_risk_domains_without_gate")

    status = "ready" if not issue_ids else "blocked"
    return SceneFormulaOutputWatermarkCapabilityRow(
        capability_id=spec.capability_id,
        label=spec.label,
        status=status,
        expected_owner_layer=spec.expected_owner_layer,
        parameter_paths=spec.parameter_paths,
        template_baseline_paths=spec.template_baseline_paths,
        control_contract_ids=spec.control_contract_ids,
        execution_consumers=spec.execution_consumers,
        family_ids=tuple(family.family_id for family in matched_families),
        pack_ids=_unique_values(
            pack.pack_id
            for family in matched_families
            for pack in coverage_packs_for_family(family.family_id)
        ),
        plugin_gate_ids=plugin_gate_ids,
        plugin_risk_domain_ids=spec.plugin_risk_domain_ids,
        boundary_note=spec.boundary_note,
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _family_row(family: PlannedSceneFamily) -> SceneFormulaOutputWatermarkFamilyRow:
    capability_ids = tuple(
        spec.capability_id for spec in _CAPABILITY_SPECS if spec.family_predicate(family)
    )
    issue_ids: list[str] = []
    if not capability_ids:
        issue_ids.append("family_without_formula_output_watermark_route")
    status = "ready" if not issue_ids else "blocked"
    if planned_family_is_plugin_boundary_only(family.family_id):
        status = "boundary" if not issue_ids else "blocked"
    return SceneFormulaOutputWatermarkFamilyRow(
        family_id=family.family_id,
        name=family.name,
        priority=family.priority,
        status=status,
        pack_ids=tuple(pack.pack_id for pack in coverage_packs_for_family(family.family_id)),
        capability_ids=capability_ids,
        formula_relevant="formula_policy" in capability_ids,
        output_relevant="output_delivery" in capability_ids,
        watermark_relevant="watermark_status" in capability_ids,
        plugin_boundary_only=planned_family_is_plugin_boundary_only(family.family_id),
        delivery_preset_ids=family.delivery_presets,
        issue_ids=tuple(issue_ids),
        warning_ids=(),
    )


def _filter_capability_rows(
    rows: Sequence[SceneFormulaOutputWatermarkCapabilityRow],
    *,
    capability_id: str,
    family_id: str,
    pack_id: str,
) -> tuple[SceneFormulaOutputWatermarkCapabilityRow, ...]:
    return tuple(
        row
        for row in rows
        if (not capability_id or row.capability_id == capability_id)
        and (not family_id or family_id in row.family_ids)
        and (not pack_id or pack_id in row.pack_ids)
    )


def _filter_family_rows(
    rows: Sequence[SceneFormulaOutputWatermarkFamilyRow],
    *,
    capability_id: str,
    family_id: str,
    pack_id: str,
) -> tuple[SceneFormulaOutputWatermarkFamilyRow, ...]:
    return tuple(
        row
        for row in rows
        if (not capability_id or capability_id in row.capability_ids)
        and (not family_id or row.family_id == family_id)
        and (not pack_id or pack_id in row.pack_ids)
    )


def _plugin_gate_ids_for_risks(risk_domain_ids: Sequence[str]) -> tuple[str, ...]:
    risks = set(risk_domain_ids)
    if not risks:
        return ()
    return _unique_values(
        gate.gate_id
        for gate in list_plugin_manual_gates()
        if risks.intersection(gate.risk_domain_ids)
    )


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneFormulaOutputWatermarkSourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    return tuple(
        SceneFormulaOutputWatermarkSourceEvidence(
            source_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
            status=(
                "ready"
                if result.source_exists and not result.missing_markers
                else "missing"
            ),
        )
        for result in scan_scene_source_markers(
            root,
            SCENE_FORMULA_OUTPUT_WATERMARK_SOURCE_MARKERS,
        )
    )


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_FORMULA_OUTPUT_WATERMARK_AUDIT_SOURCE_ID",
    "SceneFormulaOutputWatermarkAuditReport",
    "SceneFormulaOutputWatermarkCapabilityRow",
    "SceneFormulaOutputWatermarkFamilyRow",
    "SceneFormulaOutputWatermarkIssue",
    "SceneFormulaOutputWatermarkSourceEvidence",
    "audit_scene_formula_output_watermark_report",
    "build_scene_formula_output_watermark_audit_report",
]
