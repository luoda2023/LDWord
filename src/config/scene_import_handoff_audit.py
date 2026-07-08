"""Import/AI handoff audit for scene-matrix boundary workflows.

N2.163 keeps import/conversion work behind ``import_ai_boundary`` until a
confidence report and manual decision explicitly hand the request to a target
scene pack.  The audit verifies the route, request sample, request-cell,
plugin/manual gate, target family, report fields, and fallback policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.plugin_manual_gate import get_plugin_manual_gate
from src.config.scene_source_evidence import (
    scan_scene_source_markers,
    scene_source_marker_issue_message,
)
from src.config.scene_coverage_manifest import (
    SCENE_COVERAGE_PACK_MAP,
    coverage_packs_for_family,
)
from src.config.scene_family_registry import PLANNED_SCENE_FAMILY_MAP
from src.config.scene_high_frequency_request_samples import (
    HighFrequencyRequestSample,
    list_high_frequency_request_samples,
)
from src.config.scene_natural_request_router import (
    NaturalRequestRoute,
    NATURAL_REQUEST_ROUTE_MAP,
    route_natural_scene_request,
)
from src.config.scene_request_cell_fixture_registry import (
    SceneRequestCellFixtureSpec,
    list_scene_request_cell_fixtures,
)


N2_163_REQUIRED_HANDOFF_IDS: tuple[str, ...] = (
    "pdf_thesis_import_to_chinese_academic",
)

N2_163_REQUIRED_REPORT_FIELDS: tuple[str, ...] = (
    "source_type",
    "confidence_level",
    "low_confidence_regions",
    "manual_decision",
    "handoff_pack_id",
    "handoff_family_id",
    "handoff_status",
    "fallback_strategy",
)

N2_163_REQUIRED_DECISION_STATE = "needs_plugin_handoff"

N2_163_SOURCE_EVIDENCE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "v29_plan",
        "docs/audits/高层场景能力矩阵V29高频任务全集与边界准入深化规划_2026-06-19.md",
        ("N2.163", "handoff", "人工状态"),
    ),
    (
        "natural_router_handoff",
        "src/config/scene_natural_request_router.py",
        ("import_pdf_thesis_boundary", "handoff_pack_id", "handoff_family_id"),
    ),
    (
        "request_sample_handoff",
        "src/config/scene_high_frequency_request_samples.py",
        ("import_pdf_thesis", "expected_handoff_pack_ids", "expected_handoff_family_ids"),
    ),
    (
        "plugin_gate_report_fields",
        "src/config/plugin_manual_gate.py",
        ("handoff_pack_id", "handoff_status", "fallback_strategy"),
    ),
    (
        "report_writer_handoff_fields",
        "src/report_writer.py",
        ("Report fields:", "report_fields"),
    ),
)


@dataclass(frozen=True, slots=True)
class ImportHandoffSpec:
    handoff_id: str
    sample_id: str
    request_text: str
    route_id: str
    source_pack_id: str
    target_pack_id: str
    target_family_id: str
    plugin_gate_id: str
    required_decision_state: str
    fallback_strategy: str
    required_report_fields: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "handoff_id": self.handoff_id,
            "sample_id": self.sample_id,
            "request_text": self.request_text,
            "route_id": self.route_id,
            "source_pack_id": self.source_pack_id,
            "target_pack_id": self.target_pack_id,
            "target_family_id": self.target_family_id,
            "plugin_gate_id": self.plugin_gate_id,
            "required_decision_state": self.required_decision_state,
            "fallback_strategy": self.fallback_strategy,
            "required_report_fields": list(self.required_report_fields),
        }


@dataclass(frozen=True, slots=True)
class SceneImportHandoffIssue:
    handoff_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "handoff_id": self.handoff_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneImportHandoffSourceEvidence:
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
class SceneImportHandoffRow:
    handoff_id: str
    sample_id: str
    request_text: str
    route_id: str
    source_pack_id: str
    target_pack_id: str
    target_family_id: str
    plugin_gate_id: str
    route_status: str
    selected_route_id: str
    selected_pack_id: str
    route_handoff_pack_id: str
    route_handoff_family_id: str
    sample_handoff_pack_ids: tuple[str, ...]
    sample_handoff_family_ids: tuple[str, ...]
    request_cell_coverage_level: str
    request_cell_fixture_ids: tuple[str, ...]
    gate_manual_confirmation_required: bool
    gate_confidence_report_required: bool
    gate_blocks_core_execution: bool
    gate_decision_states: tuple[str, ...]
    required_decision_state: str
    gate_report_fields: tuple[str, ...]
    required_report_fields: tuple[str, ...]
    fallback_strategy: str
    target_family_pack_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "handoff_id": self.handoff_id,
            "sample_id": self.sample_id,
            "request_text": self.request_text,
            "status": self.status,
            "route_id": self.route_id,
            "source_pack_id": self.source_pack_id,
            "target_pack_id": self.target_pack_id,
            "target_family_id": self.target_family_id,
            "plugin_gate_id": self.plugin_gate_id,
            "route_status": self.route_status,
            "selected_route_id": self.selected_route_id,
            "selected_pack_id": self.selected_pack_id,
            "route_handoff_pack_id": self.route_handoff_pack_id,
            "route_handoff_family_id": self.route_handoff_family_id,
            "sample_handoff_pack_ids": list(self.sample_handoff_pack_ids),
            "sample_handoff_family_ids": list(self.sample_handoff_family_ids),
            "request_cell_coverage_level": self.request_cell_coverage_level,
            "request_cell_fixture_ids": list(self.request_cell_fixture_ids),
            "gate_manual_confirmation_required": (
                self.gate_manual_confirmation_required
            ),
            "gate_confidence_report_required": self.gate_confidence_report_required,
            "gate_blocks_core_execution": self.gate_blocks_core_execution,
            "gate_decision_states": list(self.gate_decision_states),
            "required_decision_state": self.required_decision_state,
            "gate_report_fields": list(self.gate_report_fields),
            "required_report_fields": list(self.required_report_fields),
            "fallback_strategy": self.fallback_strategy,
            "target_family_pack_ids": list(self.target_family_pack_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneImportHandoffAuditReport:
    rows: tuple[SceneImportHandoffRow, ...]
    issues: tuple[SceneImportHandoffIssue, ...]
    source_evidence: tuple[SceneImportHandoffSourceEvidence, ...]
    handoff_filter: str = ""
    target_pack_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def handoff_count(self) -> int:
        return len(self.rows)

    @property
    def ready_handoff_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def target_pack_count(self) -> int:
        return len({row.target_pack_id for row in self.rows if row.target_pack_id})

    @property
    def fallback_strategy_count(self) -> int:
        return len({row.fallback_strategy for row in self.rows if row.fallback_strategy})

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.missing_markers)

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "handoff_filter": self.handoff_filter,
            "target_pack_filter": self.target_pack_filter,
            "counts": {
                "handoff_count": self.handoff_count,
                "ready_handoff_count": self.ready_handoff_count,
                "target_pack_count": self.target_pack_count,
                "fallback_strategy_count": self.fallback_strategy_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "required_handoff_ids": list(N2_163_REQUIRED_HANDOFF_IDS),
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


IMPORT_HANDOFF_SPECS: tuple[ImportHandoffSpec, ...] = (
    ImportHandoffSpec(
        handoff_id="pdf_thesis_import_to_chinese_academic",
        sample_id="import_pdf_thesis",
        request_text="PDF论文排版",
        route_id="import_pdf_thesis_boundary",
        source_pack_id="import_ai_boundary",
        target_pack_id="chinese_academic",
        target_family_id="thesis_cn",
        plugin_gate_id="import_ai_conversion_gate",
        required_decision_state=N2_163_REQUIRED_DECISION_STATE,
        fallback_strategy="stay_in_import_ai_boundary_until_manual_confirmation",
        required_report_fields=N2_163_REQUIRED_REPORT_FIELDS,
    ),
)


def list_import_handoff_specs() -> tuple[ImportHandoffSpec, ...]:
    return IMPORT_HANDOFF_SPECS


def build_scene_import_handoff_audit_report(
    handoff_id: str = "",
    target_pack_id: str = "",
    project_root: Path | str | None = None,
) -> SceneImportHandoffAuditReport:
    normalized_handoff = str(handoff_id or "").strip()
    normalized_target_pack = str(target_pack_id or "").strip()
    specs = tuple(
        spec
        for spec in IMPORT_HANDOFF_SPECS
        if (not normalized_handoff or spec.handoff_id == normalized_handoff)
        and (not normalized_target_pack or spec.target_pack_id == normalized_target_pack)
    )
    samples = {sample.sample_id: sample for sample in list_high_frequency_request_samples()}
    cells = {cell.sample_id: cell for cell in list_scene_request_cell_fixtures()}
    rows: list[SceneImportHandoffRow] = []
    issues: list[SceneImportHandoffIssue] = []
    for spec in specs:
        sample = samples.get(spec.sample_id)
        route = NATURAL_REQUEST_ROUTE_MAP.get(spec.route_id)
        cell = cells.get(spec.sample_id)
        row, row_issues = _build_row(spec, sample, route, cell)
        rows.append(row)
        issues.extend(row_issues)

    if not normalized_handoff and not normalized_target_pack:
        issues.extend(_registry_issues(tuple(rows)))
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneImportHandoffAuditReport(
        rows=tuple(rows),
        issues=tuple(issues),
        source_evidence=source_evidence,
        handoff_filter=normalized_handoff,
        target_pack_filter=normalized_target_pack,
    )


def audit_scene_import_handoff_report(
    report: SceneImportHandoffAuditReport | None = None,
) -> tuple[SceneImportHandoffIssue, ...]:
    current = report or build_scene_import_handoff_audit_report()
    return current.issues


def _build_row(
    spec: ImportHandoffSpec,
    sample: HighFrequencyRequestSample | None,
    route: NaturalRequestRoute | None,
    cell: SceneRequestCellFixtureSpec | None,
) -> tuple[SceneImportHandoffRow, tuple[SceneImportHandoffIssue, ...]]:
    issue_ids: list[str] = []
    issues: list[SceneImportHandoffIssue] = []
    routed = (
        route_natural_scene_request(sample.request_text)
        if sample is not None
        else None
    )
    gate = get_plugin_manual_gate(spec.source_pack_id)
    target_family_pack_ids = tuple(
        pack.pack_id for pack in coverage_packs_for_family(spec.target_family_id)
    )

    def add_issue(kind: str, message: str) -> None:
        issue_ids.append(kind)
        issues.append(SceneImportHandoffIssue(spec.handoff_id, kind, message))

    if route is None:
        add_issue("missing_route", f"Missing route {spec.route_id}.")
    else:
        if route.pack_id != spec.source_pack_id:
            add_issue("route_source_pack_mismatch", f"Route pack is {route.pack_id}.")
        if route.handoff_pack_id != spec.target_pack_id:
            add_issue(
                "route_handoff_pack_mismatch",
                f"Route handoff pack is {route.handoff_pack_id}.",
            )
        if route.handoff_family_id != spec.target_family_id:
            add_issue(
                "route_handoff_family_mismatch",
                f"Route handoff family is {route.handoff_family_id}.",
            )
        if route.plugin_gate_id != spec.plugin_gate_id:
            add_issue(
                "route_plugin_gate_mismatch",
                f"Route plugin gate is {route.plugin_gate_id}.",
            )

    if sample is None:
        add_issue("missing_sample", f"Missing sample {spec.sample_id}.")
    else:
        if sample.expected_status != "matched":
            add_issue("sample_not_matched", f"Sample status is {sample.expected_status}.")
        if spec.route_id not in sample.expected_route_ids:
            add_issue("sample_missing_route", f"Sample lacks route {spec.route_id}.")
        if spec.source_pack_id not in sample.expected_pack_ids:
            add_issue(
                "sample_missing_source_pack",
                f"Sample lacks source pack {spec.source_pack_id}.",
            )
        if spec.target_pack_id not in sample.expected_handoff_pack_ids:
            add_issue(
                "sample_missing_handoff_pack",
                f"Sample lacks handoff pack {spec.target_pack_id}.",
            )
        if spec.target_family_id not in sample.expected_handoff_family_ids:
            add_issue(
                "sample_missing_handoff_family",
                f"Sample lacks handoff family {spec.target_family_id}.",
            )

    if routed is None:
        add_issue("missing_route_result", "Cannot route missing sample.")
    else:
        if routed.status != "matched":
            add_issue("route_result_not_matched", f"Router returned {routed.status}.")
        if routed.selected_route_id != spec.route_id:
            add_issue(
                "route_result_id_mismatch",
                f"Router selected {routed.selected_route_id}.",
            )
        if routed.selected_pack_id != spec.source_pack_id:
            add_issue(
                "route_result_pack_mismatch",
                f"Router selected pack {routed.selected_pack_id}.",
            )

    if cell is None:
        add_issue("missing_request_cell", f"Missing request-cell {spec.sample_id}.")
    else:
        if cell.coverage_level != "manual_boundary_fixture":
            add_issue(
                "request_cell_not_manual_boundary",
                f"Coverage is {cell.coverage_level}.",
            )
        if spec.plugin_gate_id not in cell.expected_plugin_gate_ids:
            add_issue(
                "request_cell_missing_plugin_gate",
                f"Request-cell lacks gate {spec.plugin_gate_id}.",
            )
        if not cell.fixture_ids:
            add_issue("request_cell_missing_fixture", "Request-cell has no fixture.")

    if not gate.manual_confirmation_required:
        add_issue("gate_missing_manual_confirmation", "Gate must require manual confirmation.")
    if not gate.confidence_report_required:
        add_issue("gate_missing_confidence_report", "Gate must require confidence report.")
    if not gate.blocks_core_execution_until_confirmed:
        add_issue("gate_does_not_block_core", "Gate must block core execution until confirmed.")
    if spec.required_decision_state not in gate.confirmation_decision_states:
        add_issue(
            "gate_missing_handoff_decision",
            f"Gate lacks decision state {spec.required_decision_state}.",
        )
    for field in spec.required_report_fields:
        if field not in gate.report_fields:
            add_issue("gate_missing_report_field", f"Gate lacks report field {field}.")

    if spec.target_pack_id not in SCENE_COVERAGE_PACK_MAP:
        add_issue("unknown_target_pack", f"Unknown target pack {spec.target_pack_id}.")
    if spec.target_family_id not in PLANNED_SCENE_FAMILY_MAP:
        add_issue("unknown_target_family", f"Unknown target family {spec.target_family_id}.")
    elif spec.target_pack_id not in target_family_pack_ids:
        add_issue(
            "target_family_not_covered_by_pack",
            f"{spec.target_family_id} is not covered by {spec.target_pack_id}.",
        )
    if not spec.fallback_strategy:
        add_issue("missing_fallback_strategy", "Fallback strategy is required.")

    row = SceneImportHandoffRow(
        handoff_id=spec.handoff_id,
        sample_id=spec.sample_id,
        request_text=spec.request_text,
        route_id=spec.route_id,
        source_pack_id=spec.source_pack_id,
        target_pack_id=spec.target_pack_id,
        target_family_id=spec.target_family_id,
        plugin_gate_id=spec.plugin_gate_id,
        route_status=routed.status if routed is not None else "",
        selected_route_id=routed.selected_route_id if routed is not None else "",
        selected_pack_id=routed.selected_pack_id if routed is not None else "",
        route_handoff_pack_id=route.handoff_pack_id if route is not None else "",
        route_handoff_family_id=route.handoff_family_id if route is not None else "",
        sample_handoff_pack_ids=(
            sample.expected_handoff_pack_ids if sample is not None else ()
        ),
        sample_handoff_family_ids=(
            sample.expected_handoff_family_ids if sample is not None else ()
        ),
        request_cell_coverage_level=cell.coverage_level if cell is not None else "",
        request_cell_fixture_ids=cell.fixture_ids if cell is not None else (),
        gate_manual_confirmation_required=gate.manual_confirmation_required,
        gate_confidence_report_required=gate.confidence_report_required,
        gate_blocks_core_execution=gate.blocks_core_execution_until_confirmed,
        gate_decision_states=gate.confirmation_decision_states,
        required_decision_state=spec.required_decision_state,
        gate_report_fields=gate.report_fields,
        required_report_fields=spec.required_report_fields,
        fallback_strategy=spec.fallback_strategy,
        target_family_pack_ids=target_family_pack_ids,
        issue_ids=tuple(issue_ids),
    )
    return row, tuple(issues)


def _registry_issues(
    rows: tuple[SceneImportHandoffRow, ...],
) -> tuple[SceneImportHandoffIssue, ...]:
    row_ids = {row.handoff_id for row in rows}
    return tuple(
        SceneImportHandoffIssue(
            handoff_id,
            "missing_required_handoff",
            f"Required import handoff {handoff_id} is missing.",
        )
        for handoff_id in N2_163_REQUIRED_HANDOFF_IDS
        if handoff_id not in row_ids
    )


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneImportHandoffSourceEvidence, ...]:
    return tuple(
        SceneImportHandoffSourceEvidence(
            evidence_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
        )
        for result in scan_scene_source_markers(
            project_root,
            N2_163_SOURCE_EVIDENCE,
        )
    )


def _source_evidence_issues(
    source_evidence: tuple[SceneImportHandoffSourceEvidence, ...],
) -> tuple[SceneImportHandoffIssue, ...]:
    return tuple(
        SceneImportHandoffIssue(
            evidence.evidence_id,
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
    "IMPORT_HANDOFF_SPECS",
    "N2_163_REQUIRED_HANDOFF_IDS",
    "N2_163_REQUIRED_REPORT_FIELDS",
    "SceneImportHandoffAuditReport",
    "SceneImportHandoffIssue",
    "audit_scene_import_handoff_report",
    "build_scene_import_handoff_audit_report",
    "list_import_handoff_specs",
]
