"""Owner-facing control consistency audit for the high-level scene matrix.

N2.157C turns the shared control-contract registry into a scene-matrix gate:
each contract must expose its canonical control, units, pairing, disabled-state
rules, and evidence on the surface owned by its declared layer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.config.control_contract_registry import (
    ControlContract,
    audit_control_contract_registry,
    list_control_contracts,
    resolve_control_contract_evidence_locations,
)


N2_157C_CONTROL_CONTRACT_IDS: tuple[str, ...] = (
    "body.left_indent",
    "body.right_indent",
    "body.special_indent",
    "body.line_spacing",
    "body.space_before",
    "body.space_after",
    "fixed_layout.table_row_height",
    "scene.formula_conversion_strategy",
    "scene.watermark_status",
    "material.schema_selection",
    "output.delivery_preset",
    "output.content_visibility_rules",
    "plugin.manual_gate",
)

N2_157C_PAIR_REQUIREMENTS: tuple[tuple[str, str, str], ...] = (
    ("body.left_indent", "body.right_indent", "same_row"),
    ("body.space_before", "body.space_after", "same_row"),
)

N2_157C_DISABLED_RULE_MARKERS: dict[str, tuple[str, ...]] = {
    "body.special_indent": ("mode=none", "value 0"),
    "body.line_spacing": ("single/one_half/double", "exact/multiple"),
    "body.space_before": ("auto",),
    "body.space_after": ("auto",),
    "fixed_layout.table_row_height": ("fixed-layout",),
    "scene.formula_conversion_strategy": ("full LaTeX", "plugin/manual"),
    "material.schema_selection": ("unknown schema",),
    "plugin.manual_gate": ("manual confirmation",),
}

N2_157C_GLOBAL_SURFACE_EVIDENCE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "scene_summary_projection",
        "src/ui/panels/scene_summary_projection.py",
        ("build_control_contract_summary_items", "control_contract_scope"),
    ),
    (
        "workbench_scene_summary",
        "src/config/scene_engineering_summary.py",
        ("build_scene_control_contract_summary", "list_control_contracts"),
    ),
    (
        "workbench_execution_gate",
        "src/ui/adapters/workbench_execution_gate.py",
        (
            "class ExecutionGateDecision",
            "def decide_execution_gate",
            "primary_action",
        ),
    ),
    (
        "report_writer",
        "src/report_writer.py",
        ("_format_control_contracts_markdown", "_extract_control_contracts"),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneControlConsistencyIssue:
    contract_id: str
    kind: str
    message: str

    def to_payload(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "kind": self.kind,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class SceneControlSurfaceEvidence:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneControlConsistencyRow:
    contract_id: str
    canonical_label: str
    owner_layer: str
    canonical_control: str
    parameter_paths: tuple[str, ...]
    unit_set: tuple[str, ...]
    paired_contract_ids: tuple[str, ...]
    disabled_state_rule: str
    template_surface: str
    scene_surface: str
    workbench_surface: str
    evidence_location_count: int
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "canonical_label": self.canonical_label,
            "owner_layer": self.owner_layer,
            "canonical_control": self.canonical_control,
            "parameter_paths": list(self.parameter_paths),
            "unit_set": list(self.unit_set),
            "paired_contract_ids": list(self.paired_contract_ids),
            "disabled_state_rule": self.disabled_state_rule,
            "template_surface": self.template_surface,
            "scene_surface": self.scene_surface,
            "workbench_surface": self.workbench_surface,
            "evidence_location_count": self.evidence_location_count,
            "issue_ids": list(self.issue_ids),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneControlConsistencyAuditReport:
    rows: tuple[SceneControlConsistencyRow, ...]
    issues: tuple[SceneControlConsistencyIssue, ...]
    surface_evidence: tuple[SceneControlSurfaceEvidence, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def contract_count(self) -> int:
        return len(self.rows)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def owner_layer_counts(self) -> tuple[tuple[str, int], ...]:
        counts = Counter(row.owner_layer for row in self.rows)
        return tuple(sorted(counts.items()))

    @property
    def missing_surface_evidence_count(self) -> int:
        return sum(1 for item in self.surface_evidence if item.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "contract_count": self.contract_count,
            "issue_count": self.issue_count,
            "owner_layer_counts": [
                {"owner_layer": layer, "count": count}
                for layer, count in self.owner_layer_counts
            ],
            "missing_surface_evidence_count": self.missing_surface_evidence_count,
            "required_contract_ids": list(N2_157C_CONTROL_CONTRACT_IDS),
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "surface_evidence": [
                evidence.to_payload() for evidence in self.surface_evidence
            ],
        }


def build_scene_control_consistency_audit_report(
    *,
    contract_id: str = "",
    project_root: Path | None = None,
) -> SceneControlConsistencyAuditReport:
    root = project_root or Path(__file__).resolve().parents[2]
    registry_audit = audit_control_contract_registry(project_root=root)
    issues: list[SceneControlConsistencyIssue] = []
    rows: list[SceneControlConsistencyRow] = []
    requested_id = str(contract_id or "").strip()
    required_ids = (
        (requested_id,)
        if requested_id
        else N2_157C_CONTROL_CONTRACT_IDS
    )
    contracts = {contract.contract_id: contract for contract in list_control_contracts()}

    _append_registry_audit_issues(issues, registry_audit)

    for required_id in required_ids:
        contract = contracts.get(required_id)
        if contract is None:
            issues.append(
                SceneControlConsistencyIssue(
                    contract_id=required_id,
                    kind="missing_contract",
                    message="Required scene control contract is not registered.",
                )
            )
            continue
        row, row_issues = _build_row(contract, project_root=root)
        rows.append(row)
        issues.extend(row_issues)

    issues.extend(_pair_requirement_issues(rows))
    surface_evidence = _build_surface_evidence(root)
    for evidence in surface_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneControlConsistencyIssue(
                    contract_id="*",
                    kind=f"missing_surface_evidence.{evidence.evidence_id}",
                    message=(
                        f"{evidence.source_path} is missing markers: "
                        + ", ".join(evidence.missing_markers)
                    ),
                )
            )

    return SceneControlConsistencyAuditReport(
        rows=tuple(rows),
        issues=tuple(issues),
        surface_evidence=surface_evidence,
    )


def audit_scene_control_consistency_report(
    report: SceneControlConsistencyAuditReport | None = None,
) -> tuple[SceneControlConsistencyIssue, ...]:
    report = report or build_scene_control_consistency_audit_report()
    return report.issues


def _build_row(
    contract: ControlContract,
    *,
    project_root: Path,
) -> tuple[SceneControlConsistencyRow, tuple[SceneControlConsistencyIssue, ...]]:
    issues: list[SceneControlConsistencyIssue] = []
    issue_ids: list[str] = []

    if not contract.canonical_control.strip():
        _append_issue(
            issues,
            issue_ids,
            contract.contract_id,
            "missing_canonical_control",
            "Scene control contract must name a canonical control.",
        )
    if not contract.parameter_paths:
        _append_issue(
            issues,
            issue_ids,
            contract.contract_id,
            "missing_parameter_paths",
            "Scene control contract must list parameter paths.",
        )
    if contract.owner_layer == "template" and not contract.template_surface.strip():
        _append_issue(
            issues,
            issue_ids,
            contract.contract_id,
            "missing_template_surface",
            "A template-owned control requires a template-facing surface description.",
        )
    elif contract.owner_layer != "template" and not contract.scene_surface.strip():
        _append_issue(
            issues,
            issue_ids,
            contract.contract_id,
            "missing_scene_surface",
            "N2.157C requires a scene-facing surface description.",
        )

    expected_markers = N2_157C_DISABLED_RULE_MARKERS.get(contract.contract_id, ())
    for marker in expected_markers:
        if marker not in contract.disabled_state_rule:
            _append_issue(
                issues,
                issue_ids,
                contract.contract_id,
                f"missing_disabled_rule_marker.{marker}",
                f"Disabled-state rule must mention {marker!r}.",
            )

    evidence_locations = resolve_control_contract_evidence_locations(
        contract.contract_id,
        project_root=project_root,
    )
    resolved_count = sum(1 for location in evidence_locations if location.line_number)
    if not resolved_count:
        _append_issue(
            issues,
            issue_ids,
            contract.contract_id,
            "missing_resolved_evidence",
            "No source evidence markers resolve to a line number.",
        )

    return (
        SceneControlConsistencyRow(
            contract_id=contract.contract_id,
            canonical_label=contract.canonical_label,
            owner_layer=contract.owner_layer,
            canonical_control=contract.canonical_control,
            parameter_paths=contract.parameter_paths,
            unit_set=contract.unit_set,
            paired_contract_ids=contract.paired_contract_ids,
            disabled_state_rule=contract.disabled_state_rule,
            template_surface=contract.template_surface,
            scene_surface=contract.scene_surface,
            workbench_surface=contract.workbench_surface,
            evidence_location_count=resolved_count,
            issue_ids=tuple(issue_ids),
        ),
        tuple(issues),
    )


def _pair_requirement_issues(
    rows: list[SceneControlConsistencyRow],
) -> tuple[SceneControlConsistencyIssue, ...]:
    issues: list[SceneControlConsistencyIssue] = []
    by_id = {row.contract_id: row for row in rows}
    for left_id, right_id, layout in N2_157C_PAIR_REQUIREMENTS:
        left = by_id.get(left_id)
        right = by_id.get(right_id)
        if left is None or right is None:
            continue
        if right_id not in left.paired_contract_ids:
            issues.append(
                SceneControlConsistencyIssue(
                    contract_id=left_id,
                    kind=f"missing_pair.{right_id}",
                    message=f"{left_id} must be paired with {right_id} for {layout}.",
                )
            )
        if left_id not in right.paired_contract_ids:
            issues.append(
                SceneControlConsistencyIssue(
                    contract_id=right_id,
                    kind=f"missing_pair.{left_id}",
                    message=f"{right_id} must be paired with {left_id} for {layout}.",
                )
            )
    return tuple(issues)


def _build_surface_evidence(root: Path) -> tuple[SceneControlSurfaceEvidence, ...]:
    evidence_items: list[SceneControlSurfaceEvidence] = []
    for evidence_id, source_path, markers in N2_157C_GLOBAL_SURFACE_EVIDENCE:
        path = root / source_path
        content = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing_markers = tuple(marker for marker in markers if marker not in content)
        evidence_items.append(
            SceneControlSurfaceEvidence(
                evidence_id=evidence_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing_markers,
            )
        )
    return tuple(evidence_items)


def _append_registry_audit_issues(issues: list[SceneControlConsistencyIssue], audit) -> None:
    for contract_id in audit.missing_required_contracts:
        issues.append(
            SceneControlConsistencyIssue(
                contract_id=contract_id,
                kind="registry_missing_required",
                message="Required control contract is missing from registry audit.",
            )
        )
    for contract_id, owner_layer in audit.invalid_owner_layers:
        issues.append(
            SceneControlConsistencyIssue(
                contract_id=contract_id,
                kind="registry_invalid_owner_layer",
                message=f"Invalid owner layer: {owner_layer}",
            )
        )
    for contract_id, paired_id in audit.missing_paired_contracts:
        issues.append(
            SceneControlConsistencyIssue(
                contract_id=contract_id,
                kind="registry_missing_pair",
                message=f"Missing paired contract: {paired_id}",
            )
        )
    for contract_id, source_path in audit.missing_evidence_files:
        issues.append(
            SceneControlConsistencyIssue(
                contract_id=contract_id,
                kind="registry_missing_evidence_file",
                message=f"Missing evidence file: {source_path}",
            )
        )
    for contract_id, source_path, marker in audit.missing_evidence_markers:
        issues.append(
            SceneControlConsistencyIssue(
                contract_id=contract_id,
                kind="registry_missing_evidence_marker",
                message=f"Missing evidence marker {marker!r} in {source_path}",
            )
        )


def _append_issue(
    issues: list[SceneControlConsistencyIssue],
    issue_ids: list[str],
    contract_id: str,
    kind: str,
    message: str,
) -> None:
    issue_ids.append(kind)
    issues.append(
        SceneControlConsistencyIssue(
            contract_id=contract_id,
            kind=kind,
            message=message,
        )
    )


__all__ = [
    "N2_157C_CONTROL_CONTRACT_IDS",
    "SceneControlConsistencyAuditReport",
    "SceneControlConsistencyIssue",
    "SceneControlConsistencyRow",
    "SceneControlSurfaceEvidence",
    "audit_scene_control_consistency_report",
    "build_scene_control_consistency_audit_report",
]
