"""ObjectPreflight action-closure audit for high-frequency scenes.

N2.172 turns Word/OOXML object risk visibility into an auditable action
contract: each preflight target must have detection, scene-family planning,
report/workbench exposure, repair routing, and sample behavior evidence where
that target is part of the current high-frequency surface area.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.config.scene import ObjectPreflightPolicy, SceneWorkspace
from src.config.scene_coverage_manifest import coverage_packs_for_family
from src.config.scene_family_application import (
    apply_planned_scene_family_defaults,
    planned_family_is_application_boundary_only,
)
from src.config.scene_family_registry import (
    PlannedSceneFamily,
    list_planned_scene_families,
)
from src.config.scene_repair_routing import repair_route_for_target
from src.config.scene_sample_fixture_registry import list_scene_sample_fixtures
from src.config.scene_source_evidence import scan_scene_source_markers
from src.config.scene_word_risk_closure_audit import (
    build_scene_word_risk_closure_audit_report,
)
from src.shared.engine.object_preflight import (
    OBJECT_PREFLIGHT_SCAN_TARGETS,
    object_preflight_targets_for_touchpoints,
)


SCENE_OBJECT_PREFLIGHT_ACTION_AUDIT_SOURCE_ID = (
    "scene_object_preflight_action_audit"
)

SCENE_OBJECT_PREFLIGHT_ACTION_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]], ...
] = (
    (
        "object_preflight_engine",
        "src/shared/engine/object_preflight.py",
        (
            "OBJECT_PREFLIGHT_SCAN_TARGETS",
            "inspect_docx_package",
            "object_preflight_module_skips",
            "OOXML_TOUCHPOINT_TO_PREFLIGHT_TARGETS",
        ),
    ),
    (
        "pipeline_runner",
        "src/pipeline/runner.py",
        (
            "_run_object_preflight",
            "_build_object_preflight_policy_snapshot",
            "object_preflight_module_skips",
        ),
    ),
    (
        "report_writer",
        "src/report_writer.py",
        (
            "_extract_object_preflight",
            "_format_object_preflight_markdown",
            "module_skips",
        ),
    ),
    (
        "workbench_execution_adapter",
        "src/ui/adapters/workbench_execution_adapter.py",
        (
            "object_preflight_issue_items",
            'repair_target_type="object_preflight"',
            "_object_preflight_summary",
        ),
    ),
    (
        "workbench_execution_runtime",
        "src/ui/panels/workbench/execution_runtime.py",
        (
            "_object_preflight_payload",
            "recommended_scan_targets",
            "module_skips",
        ),
    ),
    (
        "repair_routing",
        "src/config/scene_repair_routing.py",
        (
            'route_id="object_preflight"',
            'repair_target_types=("object", "object_preflight")',
            "ObjectPreflightPolicy",
        ),
    ),
    (
        "sample_fixture_registry",
        "src/config/scene_sample_fixture_registry.py",
        ("expected_preflight_findings", "expected_behaviors", "object_preflight"),
    ),
    (
        "word_risk_closure",
        "src/config/scene_word_risk_closure_audit.py",
        ("WORD_RISK_PREFLIGHT_TARGET_MAP", "PREFLIGHT_GLOBAL_EVIDENCE"),
    ),
    (
        "object_preflight_tests",
        "tests/test_object_preflight_semantics.py",
        (
            "test_pipeline_blocks_strict_object_preflight_findings",
            "test_pipeline_skips_configured_high_risk_modules_after_preflight",
            "test_object_preflight_report_includes_policy_and_planning_evidence",
        ),
    ),
)

HIGH_RISK_PREFLIGHT_TARGETS: tuple[str, ...] = (
    "ole_objects",
    "embedded_workbooks",
    "embedded_packages",
    "visio_drawings",
    "macros",
)

ACTION_BEHAVIOR_IDS: tuple[str, ...] = (
    "detect",
    "warn",
    "block_report",
    "skip_report",
    "manual_confirmation",
    "preserve_layout",
    "repair_route",
)


@dataclass(frozen=True, slots=True)
class SceneObjectPreflightActionIssue:
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
class SceneObjectPreflightActionSourceEvidence:
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
class SceneObjectPreflightTargetRow:
    target_id: str
    status: str
    high_risk: bool
    word_risk_surface_ids: tuple[str, ...]
    recommended_family_ids: tuple[str, ...]
    actual_family_ids: tuple[str, ...]
    strict_family_ids: tuple[str, ...]
    pack_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    expected_behaviors: tuple[str, ...]
    block_policy_family_ids: tuple[str, ...]
    skip_module_ids: tuple[str, ...]
    repair_route_id: str
    action_behavior_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "target_id": self.target_id,
            "status": self.status,
            "high_risk": self.high_risk,
            "word_risk_surface_ids": list(self.word_risk_surface_ids),
            "recommended_family_ids": list(self.recommended_family_ids),
            "actual_family_ids": list(self.actual_family_ids),
            "strict_family_ids": list(self.strict_family_ids),
            "pack_ids": list(self.pack_ids),
            "fixture_ids": list(self.fixture_ids),
            "expected_behaviors": list(self.expected_behaviors),
            "block_policy_family_ids": list(self.block_policy_family_ids),
            "skip_module_ids": list(self.skip_module_ids),
            "repair_route_id": self.repair_route_id,
            "action_behavior_ids": list(self.action_behavior_ids),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneObjectPreflightFamilyRow:
    family_id: str
    name: str
    priority: str
    status: str
    pack_ids: tuple[str, ...]
    ooxml_touchpoints: tuple[str, ...]
    recommended_scan_targets: tuple[str, ...]
    actual_scan_targets: tuple[str, ...]
    missing_recommended_targets: tuple[str, ...]
    preservation_mode: str
    block_on: tuple[str, ...]
    skip_module_targets: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    expected_preflight_findings: tuple[str, ...]
    application_applied: bool
    plugin_boundary_only: bool
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "ooxml_touchpoints": list(self.ooxml_touchpoints),
            "recommended_scan_targets": list(self.recommended_scan_targets),
            "actual_scan_targets": list(self.actual_scan_targets),
            "missing_recommended_targets": list(self.missing_recommended_targets),
            "preservation_mode": self.preservation_mode,
            "block_on": list(self.block_on),
            "skip_module_targets": list(self.skip_module_targets),
            "fixture_ids": list(self.fixture_ids),
            "expected_preflight_findings": list(self.expected_preflight_findings),
            "application_applied": self.application_applied,
            "plugin_boundary_only": self.plugin_boundary_only,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneObjectPreflightActionAuditReport:
    target_rows: tuple[SceneObjectPreflightTargetRow, ...]
    family_rows: tuple[SceneObjectPreflightFamilyRow, ...]
    issues: tuple[SceneObjectPreflightActionIssue, ...]
    warnings: tuple[SceneObjectPreflightActionIssue, ...]
    source_evidence: tuple[SceneObjectPreflightActionSourceEvidence, ...]
    target_filter: str = ""
    family_filter: str = ""
    total_target_count: int = 0
    total_family_count: int = 0

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def target_count(self) -> int:
        return len(self.target_rows)

    @property
    def ready_target_count(self) -> int:
        return sum(1 for row in self.target_rows if row.status == "ready")

    @property
    def warning_target_count(self) -> int:
        return sum(1 for row in self.target_rows if row.warning_ids)

    @property
    def high_risk_target_count(self) -> int:
        return sum(1 for row in self.target_rows if row.high_risk)

    @property
    def fixture_backed_target_count(self) -> int:
        return sum(1 for row in self.target_rows if row.fixture_ids)

    @property
    def blockable_target_count(self) -> int:
        return sum(1 for row in self.target_rows if row.block_policy_family_ids)

    @property
    def skippable_target_count(self) -> int:
        return sum(1 for row in self.target_rows if row.skip_module_ids)

    @property
    def manual_confirmation_target_count(self) -> int:
        return sum(
            1 for row in self.target_rows if "manual_confirmation" in row.expected_behaviors
        )

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
    def strict_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.preservation_mode == "strict")

    @property
    def family_with_fixture_count(self) -> int:
        return sum(1 for row in self.family_rows if row.fixture_ids)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "target_filter": self.target_filter,
            "family_filter": self.family_filter,
            "total_target_count": self.total_target_count,
            "total_family_count": self.total_family_count,
            "counts": {
                "target_count": self.target_count,
                "ready_target_count": self.ready_target_count,
                "warning_target_count": self.warning_target_count,
                "high_risk_target_count": self.high_risk_target_count,
                "fixture_backed_target_count": self.fixture_backed_target_count,
                "blockable_target_count": self.blockable_target_count,
                "skippable_target_count": self.skippable_target_count,
                "manual_confirmation_target_count": (
                    self.manual_confirmation_target_count
                ),
                "family_count": self.family_count,
                "ready_family_count": self.ready_family_count,
                "boundary_family_count": self.boundary_family_count,
                "strict_family_count": self.strict_family_count,
                "family_with_fixture_count": self.family_with_fixture_count,
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "target_rows": [row.to_payload() for row in self.target_rows],
            "family_rows": [row.to_payload() for row in self.family_rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


@lru_cache(maxsize=32)
def build_scene_object_preflight_action_audit_report(
    *,
    target_id: str = "",
    family_id: str = "",
    project_root: Path | str | None = None,
) -> SceneObjectPreflightActionAuditReport:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    normalized_target = str(target_id or "").strip()
    normalized_family = str(family_id or "").strip()
    source_evidence = _source_evidence(root)

    all_families = tuple(_family_row(family) for family in list_planned_scene_families())
    all_targets = tuple(_target_row(target, all_families) for target in OBJECT_PREFLIGHT_SCAN_TARGETS)
    issues, warnings = audit_scene_object_preflight_action_report(
        SceneObjectPreflightActionAuditReport(
            target_rows=all_targets,
            family_rows=all_families,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            total_target_count=len(all_targets),
            total_family_count=len(all_families),
        )
    )

    target_rows = tuple(
        row for row in all_targets if not normalized_target or row.target_id == normalized_target
    )
    family_rows = tuple(
        row for row in all_families if not normalized_family or row.family_id == normalized_family
    )
    if normalized_target and not target_rows:
        issues = (
            *issues,
            SceneObjectPreflightActionIssue(
                "target",
                normalized_target,
                "unknown_target",
                f"Unknown ObjectPreflight target: {normalized_target}",
            ),
        )
    if normalized_family and not family_rows:
        issues = (
            *issues,
            SceneObjectPreflightActionIssue(
                "family",
                normalized_family,
                "unknown_family",
                f"Unknown scene family: {normalized_family}",
            ),
        )

    visible_target_ids = {row.target_id for row in target_rows}
    visible_family_ids = {row.family_id for row in family_rows}
    visible_issues = tuple(
        issue
        for issue in issues
        if (
            issue.scope_type == "source_evidence"
            or (issue.scope_type == "target" and issue.scope_id in visible_target_ids)
            or (issue.scope_type == "family" and issue.scope_id in visible_family_ids)
        )
    )
    visible_warnings = tuple(
        warning
        for warning in warnings
        if (
            warning.scope_type == "source_evidence"
            or (warning.scope_type == "target" and warning.scope_id in visible_target_ids)
            or (warning.scope_type == "family" and warning.scope_id in visible_family_ids)
        )
    )

    return SceneObjectPreflightActionAuditReport(
        target_rows=target_rows,
        family_rows=family_rows,
        issues=visible_issues,
        warnings=visible_warnings,
        source_evidence=source_evidence,
        target_filter=normalized_target,
        family_filter=normalized_family,
        total_target_count=len(all_targets),
        total_family_count=len(all_families),
    )


def audit_scene_object_preflight_action_report(
    report: SceneObjectPreflightActionAuditReport,
) -> tuple[
    tuple[SceneObjectPreflightActionIssue, ...],
    tuple[SceneObjectPreflightActionIssue, ...],
]:
    issues: list[SceneObjectPreflightActionIssue] = []
    warnings: list[SceneObjectPreflightActionIssue] = []

    for row in report.target_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneObjectPreflightActionIssue(
                    "target",
                    row.target_id,
                    issue_id,
                    f"ObjectPreflight target has unresolved action gap: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneObjectPreflightActionIssue(
                    "target",
                    row.target_id,
                    warning_id,
                    f"ObjectPreflight target has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for row in report.family_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneObjectPreflightActionIssue(
                    "family",
                    row.family_id,
                    issue_id,
                    f"ObjectPreflight family row has unresolved gap: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneObjectPreflightActionIssue(
                    "family",
                    row.family_id,
                    warning_id,
                    f"ObjectPreflight family row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneObjectPreflightActionIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    "Missing source markers: " + ", ".join(evidence.missing_markers),
                )
            )
    return tuple(issues), tuple(warnings)


def _family_row(family: PlannedSceneFamily) -> SceneObjectPreflightFamilyRow:
    scene = SceneWorkspace(scene_id=family.family_id, category=family.family_id)
    result = apply_planned_scene_family_defaults(scene, family_id=family.family_id)
    plugin_boundary_only = planned_family_is_application_boundary_only(family.family_id)
    policy = scene.compliance_profile.object_preflight
    recommended_targets = object_preflight_targets_for_touchpoints(family.ooxml_touchpoints)
    actual_targets = _ordered_targets(getattr(policy, "scan_targets", []) or [])
    block_on = _ordered_targets(getattr(policy, "block_on", []) or [])
    skip_module_targets = _ordered_targets(
        (getattr(policy, "skip_modules_by_finding", {}) or {}).keys()
    )
    fixtures = tuple(
        fixture
        for fixture in list_scene_sample_fixtures()
        if fixture.family_id == family.family_id
    )
    missing_targets = tuple(
        target for target in recommended_targets if target not in actual_targets
    )
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if not plugin_boundary_only and recommended_targets and not getattr(policy, "enabled", True):
        issue_ids.append("preflight_disabled_for_ooxml_family")
    if missing_targets:
        issue_ids.append("missing_recommended_scan_targets")
    if not plugin_boundary_only and family.ooxml_touchpoints and not recommended_targets:
        warning_ids.append("ooxml_touchpoints_have_no_scan_mapping")
    if not fixtures and not plugin_boundary_only:
        warning_ids.append("missing_family_fixture")

    status = "ready"
    if issue_ids:
        status = "blocked"
    elif plugin_boundary_only:
        status = "boundary"
    elif warning_ids:
        status = "needs_depth"

    return SceneObjectPreflightFamilyRow(
        family_id=family.family_id,
        name=family.name,
        priority=family.priority,
        status=status,
        pack_ids=tuple(pack.pack_id for pack in coverage_packs_for_family(family.family_id)),
        ooxml_touchpoints=family.ooxml_touchpoints,
        recommended_scan_targets=recommended_targets,
        actual_scan_targets=actual_targets,
        missing_recommended_targets=missing_targets,
        preservation_mode=str(getattr(policy, "preservation_mode", "") or ""),
        block_on=block_on,
        skip_module_targets=skip_module_targets,
        fixture_ids=tuple(fixture.fixture_id for fixture in fixtures),
        expected_preflight_findings=_unique_values(
            finding for fixture in fixtures for finding in fixture.expected_preflight_findings
        ),
        application_applied=result.applied,
        plugin_boundary_only=plugin_boundary_only,
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _target_row(
    target_id: str,
    family_rows: Sequence[SceneObjectPreflightFamilyRow],
) -> SceneObjectPreflightTargetRow:
    word_risk_rows = build_scene_word_risk_closure_audit_report().rows
    fixtures = list_scene_sample_fixtures()
    default_policy = ObjectPreflightPolicy()
    repair_route = repair_route_for_target("object_preflight")
    fixture_ids = tuple(
        fixture.fixture_id
        for fixture in fixtures
        if target_id in fixture.expected_preflight_findings
    )
    expected_behaviors = _unique_values(
        behavior
        for fixture in fixtures
        if target_id in fixture.expected_preflight_findings
        for behavior in fixture.expected_behaviors
    )
    recommended_family_ids = tuple(
        row.family_id for row in family_rows if target_id in row.recommended_scan_targets
    )
    actual_family_ids = tuple(
        row.family_id for row in family_rows if target_id in row.actual_scan_targets
    )
    strict_family_ids = tuple(
        row.family_id
        for row in family_rows
        if row.preservation_mode == "strict" and target_id in row.actual_scan_targets
    )
    block_policy_family_ids = tuple(
        row.family_id for row in family_rows if target_id in row.block_on
    )
    word_risk_surface_ids = tuple(
        row.surface_id for row in word_risk_rows if target_id in row.preflight_targets
    )
    pack_ids = _unique_values(
        pack_id
        for row in word_risk_rows
        if target_id in row.preflight_targets
        for pack_id in row.pack_ids
    )
    skip_module_ids = _unique_values(
        module_name
        for row in family_rows
        for module_name in _mapping_values_for_target(row, target_id)
    )
    action_behavior_ids = _target_action_behaviors(
        target_id=target_id,
        expected_behaviors=expected_behaviors,
        block_policy_family_ids=block_policy_family_ids,
        skip_module_ids=skip_module_ids,
        default_policy=default_policy,
        repair_route_id=repair_route.route_id,
    )

    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if target_id not in OBJECT_PREFLIGHT_SCAN_TARGETS:
        issue_ids.append("unsupported_scan_target")
    if not repair_route or repair_route.route_id != "object_preflight":
        issue_ids.append("missing_repair_route")
    if word_risk_surface_ids and not actual_family_ids:
        issue_ids.append("word_risk_target_without_family_policy")
    if word_risk_surface_ids and not pack_ids:
        issue_ids.append("word_risk_target_without_pack")
    if not fixture_ids:
        warning_ids.append("missing_fixture_behavior")
    if target_id in HIGH_RISK_PREFLIGHT_TARGETS and not (
        block_policy_family_ids or skip_module_ids or "manual_confirmation" in expected_behaviors
    ):
        warning_ids.append("high_risk_target_without_block_skip_or_manual")

    status = "ready" if not issue_ids and not warning_ids else "needs_depth"
    if issue_ids:
        status = "blocked"
    return SceneObjectPreflightTargetRow(
        target_id=target_id,
        status=status,
        high_risk=target_id in HIGH_RISK_PREFLIGHT_TARGETS,
        word_risk_surface_ids=word_risk_surface_ids,
        recommended_family_ids=recommended_family_ids,
        actual_family_ids=actual_family_ids,
        strict_family_ids=strict_family_ids,
        pack_ids=pack_ids,
        fixture_ids=fixture_ids,
        expected_behaviors=expected_behaviors,
        block_policy_family_ids=block_policy_family_ids,
        skip_module_ids=skip_module_ids,
        repair_route_id=repair_route.route_id,
        action_behavior_ids=action_behavior_ids,
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _target_action_behaviors(
    *,
    target_id: str,
    expected_behaviors: Sequence[str],
    block_policy_family_ids: Sequence[str],
    skip_module_ids: Sequence[str],
    default_policy: ObjectPreflightPolicy,
    repair_route_id: str,
) -> tuple[str, ...]:
    behaviors = ["detect"]
    if target_id in getattr(default_policy, "scan_targets", []):
        behaviors.append("warn")
    if block_policy_family_ids:
        behaviors.append("block_report")
    if skip_module_ids:
        behaviors.append("skip_report")
    if "manual_confirmation" in expected_behaviors:
        behaviors.append("manual_confirmation")
    if "preserve_layout" in expected_behaviors:
        behaviors.append("preserve_layout")
    if repair_route_id:
        behaviors.append("repair_route")
    return tuple(behavior for behavior in ACTION_BEHAVIOR_IDS if behavior in behaviors)


def _mapping_values_for_target(
    row: SceneObjectPreflightFamilyRow,
    target_id: str,
) -> tuple[str, ...]:
    scene = SceneWorkspace(scene_id=row.family_id, category=row.family_id)
    apply_planned_scene_family_defaults(scene, family_id=row.family_id)
    mapping = getattr(
        scene.compliance_profile.object_preflight,
        "skip_modules_by_finding",
        {},
    )
    if not isinstance(mapping, Mapping):
        return ()
    return tuple(str(value or "").strip() for value in mapping.get(target_id, ()) if str(value or "").strip())


@lru_cache(maxsize=16)
def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneObjectPreflightActionSourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    return tuple(
        SceneObjectPreflightActionSourceEvidence(
            source_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=(
                result.missing_markers
                if result.source_exists
                else ("<missing file>", *result.missing_markers)
            ),
            status=(
                "ready"
                if result.source_exists and not result.missing_markers
                else "missing"
            ),
        )
        for result in scan_scene_source_markers(
            root,
            SCENE_OBJECT_PREFLIGHT_ACTION_SOURCE_MARKERS,
        )
    )


def _ordered_targets(values: Iterable[object]) -> tuple[str, ...]:
    raw = _unique_values(values)
    ordered = [target for target in OBJECT_PREFLIGHT_SCAN_TARGETS if target in raw]
    ordered.extend(target for target in raw if target not in ordered)
    return tuple(ordered)


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_OBJECT_PREFLIGHT_ACTION_AUDIT_SOURCE_ID",
    "SceneObjectPreflightActionAuditReport",
    "SceneObjectPreflightActionIssue",
    "SceneObjectPreflightActionSourceEvidence",
    "SceneObjectPreflightFamilyRow",
    "SceneObjectPreflightTargetRow",
    "audit_scene_object_preflight_action_report",
    "build_scene_object_preflight_action_audit_report",
]
