"""Business capability matrix audit for high-level scene planning.

N2.181 sits above pack/family fixture counts.  It answers whether the product
has an explicit high-frequency business capability map, whether each capability
is routed to an existing pack/family or manual boundary, and whether success,
degraded, failure/manual, request-cell, fixture, artifact, and control-style
evidence are visible without overclaiming Green/L5 readiness.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_control_runtime_consistency_audit import (
    build_scene_control_runtime_consistency_audit_report,
)
from src.config.scene_count_profile_audit import (
    build_scene_count_profile_audit_report,
)
from src.config.scene_coverage_manifest import (
    SCENE_COVERAGE_PACK_MAP,
    SceneCoveragePack,
    list_scene_coverage_packs,
)
from src.config.scene_delivery_preset_audit import (
    build_scene_delivery_preset_audit_report,
)
from src.config.scene_family_fixture_depth_audit import (
    build_scene_family_fixture_depth_audit_report,
)
from src.config.scene_family_registry import (
    PLANNED_SCENE_FAMILY_MAP,
    PlannedSceneFamily,
    list_planned_scene_families,
)
from src.config.scene_input_source_audit import (
    build_scene_input_source_audit_report,
)
from src.config.scene_material_schema_audit import (
    build_scene_material_schema_audit_report,
)
from src.config.scene_report_artifact_drilldown_audit import (
    build_scene_report_artifact_drilldown_audit_report,
)
from src.config.scene_request_cell_fixture_registry import (
    SceneRequestCellFixtureSpec,
    list_scene_request_cell_fixtures,
)
from src.config.scene_sample_fixture_registry import (
    SCENE_SAMPLE_FIXTURE_MAP,
    SceneSampleFixtureSpec,
)
from src.config.scene_user_journey_fixture_audit import (
    SCENE_USER_JOURNEY_PATH_TYPES,
    SceneUserJourneyPathRow,
    build_scene_user_journey_fixture_audit_report,
)
from src.config.scene_high_frequency_request_samples import (
    HighFrequencyRequestSample,
    list_high_frequency_request_samples,
)
from src.config.scene_source_evidence import (
    scan_scene_source_markers,
    scene_source_marker_issue_message,
)


SCENE_BUSINESS_CAPABILITY_MATRIX_AUDIT_ID = (
    "scene_business_capability_matrix_audit"
)

SCENE_BUSINESS_CAPABILITY_JOURNEY_GROUPS: tuple[str, ...] = (
    "success",
    "degraded",
    "failure",
    "manual_boundary",
    "failure_or_manual_boundary",
    "handoff",
)

HIGH_PRIORITY_CAPABILITY_PRIORITIES: tuple[str, ...] = ("P1", "P1_CANDIDATE")

SCENE_BUSINESS_CAPABILITY_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "n2_181_local_plan",
        "docs/audits/scene_business_capability_matrix_N2_181_2026-06-19.md",
        (
            "N2.181",
            "高层业务能力矩阵",
            "成功/降级/失败/人工门",
            "count_engine_tech_record",
            "exam_generator_tech_stack_record",
        ),
    ),
    (
        "n2_182_high_frequency_depth_plan",
        "docs/audits/高层场景能力矩阵高频完整性深化规划_N2_182_2026-06-19.md",
        (
            "N2.182",
            "高频完整性",
            "request_sample_ids",
            "exam_education_structured_multiversion",
            "控件样式一致性",
        ),
    ),
    (
        "coverage_manifest",
        "src/config/scene_coverage_manifest.py",
        (
            "SceneCoveragePack",
            "SCENE_COMPLETENESS_GATES",
            "plugin_boundary",
        ),
    ),
    (
        "family_registry",
        "src/config/scene_family_registry.py",
        (
            "PLANNED_SCENE_FAMILIES",
            "required_closures",
            "boundaries",
        ),
    ),
    (
        "high_frequency_requests",
        "src/config/scene_high_frequency_request_samples.py",
        (
            "HIGH_FREQUENCY_REQUEST_SAMPLES",
            "expected_plugin_gate_ids",
            "expected_handoff_pack_ids",
        ),
    ),
    (
        "user_journey_fixture",
        "src/config/scene_user_journey_fixture_audit.py",
        (
            "SCENE_USER_JOURNEY_PATH_TYPES",
            "_family_required_path_types",
            "manual_boundary",
        ),
    ),
    (
        "dashboard_wiring",
        "src/config/scene_matrix_dashboard.py",
        (
            SCENE_BUSINESS_CAPABILITY_MATRIX_AUDIT_ID,
            "business_capability_matrix_count",
        ),
    ),
    (
        "drilldown_wiring",
        "src/config/scene_matrix_drilldown_items.py",
        (
            SCENE_BUSINESS_CAPABILITY_MATRIX_AUDIT_ID,
            "business_capability_matrix",
        ),
    ),
    (
        "release_gate_wiring",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            SCENE_BUSINESS_CAPABILITY_MATRIX_AUDIT_ID,
            "scene_business_capability_matrix_count",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SceneBusinessCapabilitySpec:
    capability_id: str
    label: str
    group_id: str
    priority: str
    pack_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    boundary_policy: str
    required_journey_groups: tuple[str, ...]
    adopted_external_record_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SceneBusinessCapabilityIssue:
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
class SceneBusinessCapabilitySourceEvidence:
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
class SceneBusinessCapabilityRow:
    capability_id: str
    label: str
    group_id: str
    priority: str
    pack_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    boundary_policy: str
    boundary_summary: str
    request_cell_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    manual_gate_ids: tuple[str, ...]
    journey_type_ids: tuple[str, ...]
    required_journey_groups: tuple[str, ...]
    missing_journey_groups: tuple[str, ...]
    input_format_ids: tuple[str, ...]
    material_schema_ids: tuple[str, ...]
    count_profile_ids: tuple[str, ...]
    delivery_preset_ids: tuple[str, ...]
    docx_surfaces: tuple[str, ...]
    expected_behaviors: tuple[str, ...]
    report_expectations: tuple[str, ...]
    artifact_channel_ids: tuple[str, ...]
    control_alignment_ids: tuple[str, ...]
    adopted_external_record_ids: tuple[str, ...]
    boundary_note_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]
    warning_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        if self.issue_ids:
            return "blocked"
        if self.warning_ids:
            return "needs_depth"
        return "ready"

    @property
    def is_high_priority(self) -> bool:
        return self.priority in HIGH_PRIORITY_CAPABILITY_PRIORITIES

    @property
    def is_boundary_capability(self) -> bool:
        return self.boundary_policy in {
            "core_with_manual_gate",
            "professional_manual_gate",
            "import_handoff_boundary",
        }

    def to_payload(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "label": self.label,
            "group_id": self.group_id,
            "priority": self.priority,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "boundary_policy": self.boundary_policy,
            "boundary_summary": self.boundary_summary,
            "request_cell_ids": list(self.request_cell_ids),
            "fixture_ids": list(self.fixture_ids),
            "manual_gate_ids": list(self.manual_gate_ids),
            "journey_type_ids": list(self.journey_type_ids),
            "required_journey_groups": list(self.required_journey_groups),
            "missing_journey_groups": list(self.missing_journey_groups),
            "input_format_ids": list(self.input_format_ids),
            "material_schema_ids": list(self.material_schema_ids),
            "count_profile_ids": list(self.count_profile_ids),
            "delivery_preset_ids": list(self.delivery_preset_ids),
            "docx_surfaces": list(self.docx_surfaces),
            "expected_behaviors": list(self.expected_behaviors),
            "report_expectations": list(self.report_expectations),
            "artifact_channel_ids": list(self.artifact_channel_ids),
            "control_alignment_ids": list(self.control_alignment_ids),
            "adopted_external_record_ids": list(
                self.adopted_external_record_ids
            ),
            "boundary_note_ids": list(self.boundary_note_ids),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneBusinessCapabilityMatrixAuditReport:
    rows: tuple[SceneBusinessCapabilityRow, ...]
    issues: tuple[SceneBusinessCapabilityIssue, ...]
    warnings: tuple[SceneBusinessCapabilityIssue, ...]
    source_evidence: tuple[SceneBusinessCapabilitySourceEvidence, ...]
    capability_filter: str = ""
    group_filter: str = ""
    priority_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def capability_count(self) -> int:
        return len(self.rows)

    @property
    def ready_capability_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def high_priority_capability_count(self) -> int:
        return sum(1 for row in self.rows if row.is_high_priority)

    @property
    def high_priority_ready_count(self) -> int:
        return sum(
            1 for row in self.rows if row.is_high_priority and row.status == "ready"
        )

    @property
    def boundary_capability_count(self) -> int:
        return sum(1 for row in self.rows if row.is_boundary_capability)

    @property
    def manual_gate_capability_count(self) -> int:
        return sum(1 for row in self.rows if row.manual_gate_ids)

    @property
    def unique_request_cell_count(self) -> int:
        return len(_unique_values(cell for row in self.rows for cell in row.request_cell_ids))

    @property
    def unique_fixture_count(self) -> int:
        return len(_unique_values(fixture for row in self.rows for fixture in row.fixture_ids))

    @property
    def missing_journey_group_count(self) -> int:
        return sum(len(row.missing_journey_groups) for row in self.rows)

    @property
    def adopted_external_record_count(self) -> int:
        return len(
            _unique_values(
                record_id
                for row in self.rows
                for record_id in row.adopted_external_record_ids
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
        group_counts = Counter(row.group_id for row in self.rows)
        priority_counts = Counter(row.priority for row in self.rows)
        status_counts = Counter(row.status for row in self.rows)
        return {
            "status": self.status,
            "source_id": SCENE_BUSINESS_CAPABILITY_MATRIX_AUDIT_ID,
            "capability_filter": self.capability_filter,
            "group_filter": self.group_filter,
            "priority_filter": self.priority_filter,
            "journey_groups": list(SCENE_BUSINESS_CAPABILITY_JOURNEY_GROUPS),
            "counts": {
                "capability_count": self.capability_count,
                "ready_capability_count": self.ready_capability_count,
                "high_priority_capability_count": (
                    self.high_priority_capability_count
                ),
                "high_priority_ready_count": self.high_priority_ready_count,
                "boundary_capability_count": self.boundary_capability_count,
                "manual_gate_capability_count": self.manual_gate_capability_count,
                "unique_request_cell_count": self.unique_request_cell_count,
                "unique_fixture_count": self.unique_fixture_count,
                "missing_journey_group_count": self.missing_journey_group_count,
                "adopted_external_record_count": (
                    self.adopted_external_record_count
                ),
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "status_counts": [
                {"status": status, "count": int(status_counts.get(status, 0))}
                for status in ("ready", "needs_depth", "blocked")
                if status_counts.get(status, 0)
            ],
            "group_counts": [
                {"group_id": group_id, "count": int(group_counts[group_id])}
                for group_id in sorted(group_counts)
            ],
            "priority_counts": [
                {"priority": priority, "count": int(priority_counts[priority])}
                for priority in sorted(priority_counts)
            ],
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def build_scene_business_capability_matrix_audit_report(
    *,
    capability_id: str = "",
    group_id: str = "",
    priority: str = "",
    project_root: Path | str | None = None,
) -> SceneBusinessCapabilityMatrixAuditReport:
    normalized_capability = str(capability_id or "").strip()
    normalized_group = str(group_id or "").strip()
    normalized_priority = str(priority or "").strip().upper()

    specs = _business_capability_specs()
    if normalized_capability:
        specs = tuple(
            spec for spec in specs if spec.capability_id == normalized_capability
        )
    if normalized_group:
        specs = tuple(spec for spec in specs if spec.group_id == normalized_group)
    if normalized_priority:
        specs = tuple(spec for spec in specs if spec.priority == normalized_priority)

    request_cells = list_scene_request_cell_fixtures()
    request_samples = list_high_frequency_request_samples()
    journey_report = build_scene_user_journey_fixture_audit_report()
    family_depth_report = build_scene_family_fixture_depth_audit_report()
    input_source_report = build_scene_input_source_audit_report()
    count_profile_report = build_scene_count_profile_audit_report()
    material_schema_report = build_scene_material_schema_audit_report()
    delivery_preset_report = build_scene_delivery_preset_audit_report()
    artifact_report = build_scene_report_artifact_drilldown_audit_report()
    control_runtime_report = build_scene_control_runtime_consistency_audit_report()

    rows = tuple(
        _build_row(
            spec,
            request_cells=request_cells,
            request_samples=request_samples,
            journey_rows=journey_report.path_rows,
            family_depth_rows=family_depth_report.rows,
            input_source_rows=input_source_report.family_rows,
            count_profile_rows=count_profile_report.family_rows,
            material_schema_rows=material_schema_report.family_rows,
            delivery_preset_rows=delivery_preset_report.family_rows,
            artifact_rows=artifact_report.rows,
            control_runtime_ready=control_runtime_report.issue_count == 0,
        )
        for spec in specs
    )

    source_evidence = _source_evidence(project_root)
    issues, warnings = audit_scene_business_capability_matrix_report(
        SceneBusinessCapabilityMatrixAuditReport(
            rows=rows,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            capability_filter=normalized_capability,
            group_filter=normalized_group,
            priority_filter=normalized_priority,
        )
    )
    return SceneBusinessCapabilityMatrixAuditReport(
        rows=rows,
        issues=issues,
        warnings=warnings,
        source_evidence=source_evidence,
        capability_filter=normalized_capability,
        group_filter=normalized_group,
        priority_filter=normalized_priority,
    )


def audit_scene_business_capability_matrix_report(
    report: SceneBusinessCapabilityMatrixAuditReport | None = None,
) -> tuple[
    tuple[SceneBusinessCapabilityIssue, ...],
    tuple[SceneBusinessCapabilityIssue, ...],
]:
    current = report or build_scene_business_capability_matrix_audit_report()
    issues: list[SceneBusinessCapabilityIssue] = []
    warnings: list[SceneBusinessCapabilityIssue] = []

    if len({row.capability_id for row in current.rows}) != len(current.rows):
        issues.append(
            _issue(
                "capability_matrix",
                "capability_id",
                "duplicate_capability_id",
                "Business capability ids must be unique.",
            )
        )

    if not (current.capability_filter or current.group_filter or current.priority_filter):
        expected_family_ids = {family.family_id for family in list_planned_scene_families()}
        represented_family_ids = {
            family_id for row in current.rows for family_id in row.family_ids
        }
        for family_id in sorted(expected_family_ids - represented_family_ids):
            issues.append(
                _issue(
                    "family",
                    family_id,
                    "missing_business_capability_family",
                    f"Planned scene family '{family_id}' is not represented in the business capability matrix.",
                )
            )

        expected_pack_only = {"quick_formatting", "import_ai_boundary"}
        represented_pack_ids = {
            pack_id for row in current.rows for pack_id in row.pack_ids
        }
        for pack_id in sorted(expected_pack_only - represented_pack_ids):
            issues.append(
                _issue(
                    "pack",
                    pack_id,
                    "missing_pack_only_business_capability",
                    f"Pack-only capability '{pack_id}' is not represented in the business capability matrix.",
                )
            )

        sample_issues = _sample_mapping_issues(current.rows)
        issues.extend(sample_issues)

    for row in current.rows:
        for issue_id in row.issue_ids:
            issues.append(
                _issue(
                    "capability",
                    row.capability_id,
                    issue_id,
                    f"Capability '{row.capability_id}' has blocking issue {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                _issue(
                    "capability",
                    row.capability_id,
                    warning_id,
                    f"Capability '{row.capability_id}' needs depth for {warning_id}.",
                    severity="warning",
                )
            )

    for evidence in current.source_evidence:
        if evidence.status != "ready":
            issues.append(
                _issue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    scene_source_marker_issue_message(
                        evidence.source_path,
                        evidence.missing_markers,
                    ),
                )
            )
    return tuple(issues), tuple(warnings)


def _business_capability_specs() -> tuple[SceneBusinessCapabilitySpec, ...]:
    family_specs = tuple(
        _family_spec(family) for family in list_planned_scene_families()
    )
    return (
        SceneBusinessCapabilitySpec(
            capability_id="quick_word_formatting",
            label="Quick Word formatting and cleanup",
            group_id="general_word_formatting",
            priority="P0_CORE",
            pack_ids=("quick_formatting",),
            family_ids=(),
            boundary_policy="core_with_boundary_note",
            required_journey_groups=(
                "success",
                "degraded",
                "failure_or_manual_boundary",
            ),
        ),
        *family_specs,
        SceneBusinessCapabilitySpec(
            capability_id="professional_disclosure_boundary",
            label="Professional disclosure and regulated judgment boundary",
            group_id="professional_manual_boundary",
            priority="P0_BOUNDARY",
            pack_ids=("professional_disclosure",),
            family_ids=(),
            boundary_policy="professional_manual_gate",
            required_journey_groups=("manual_boundary",),
        ),
        SceneBusinessCapabilitySpec(
            capability_id="import_ai_assistance_boundary",
            label="Import, OCR, PDF, and AI assistance boundary",
            group_id="import_ai_boundary",
            priority="P0_BOUNDARY",
            pack_ids=("import_ai_boundary",),
            family_ids=(),
            boundary_policy="import_handoff_boundary",
            required_journey_groups=("failure", "manual_boundary", "handoff"),
        ),
    )


def _family_spec(family: PlannedSceneFamily) -> SceneBusinessCapabilitySpec:
    pack_ids = tuple(
        pack.pack_id
        for pack in list_scene_coverage_packs()
        if family.family_id in pack.planned_family_ids
    )
    return SceneBusinessCapabilitySpec(
        capability_id=family.family_id,
        label=family.name,
        group_id=_family_group_id(family.family_id),
        priority=family.priority,
        pack_ids=pack_ids,
        family_ids=(family.family_id,),
        boundary_policy=_family_boundary_policy(family),
        required_journey_groups=_family_required_journey_groups(family),
        adopted_external_record_ids=_family_external_record_ids(family.family_id),
    )


def _build_row(
    spec: SceneBusinessCapabilitySpec,
    *,
    request_cells: Sequence[SceneRequestCellFixtureSpec],
    request_samples: Sequence[HighFrequencyRequestSample],
    journey_rows: Sequence[SceneUserJourneyPathRow],
    family_depth_rows,
    input_source_rows,
    count_profile_rows,
    material_schema_rows,
    delivery_preset_rows,
    artifact_rows,
    control_runtime_ready: bool,
) -> SceneBusinessCapabilityRow:
    families = tuple(
        PLANNED_SCENE_FAMILY_MAP[family_id]
        for family_id in spec.family_ids
        if family_id in PLANNED_SCENE_FAMILY_MAP
    )
    packs = tuple(
        SCENE_COVERAGE_PACK_MAP[pack_id]
        for pack_id in spec.pack_ids
        if pack_id in SCENE_COVERAGE_PACK_MAP
    )
    cells = _matching_request_cells(spec, request_cells)
    samples = _matching_samples(spec, request_samples)
    paths = _matching_journey_paths(spec, journey_rows)
    fixtures = _fixture_specs(_unique_values(fixture_id for cell in cells for fixture_id in cell.fixture_ids))
    journey_type_ids = _ordered_journey_types(row.journey_type for row in paths)
    missing_journey_groups = tuple(
        group
        for group in spec.required_journey_groups
        if not _journey_group_covered(group, journey_type_ids)
    )

    family_depth = tuple(
        row for row in family_depth_rows if row.family_id in spec.family_ids
    )
    input_rows = tuple(row for row in input_source_rows if row.family_id in spec.family_ids)
    count_rows = tuple(row for row in count_profile_rows if row.family_id in spec.family_ids)
    material_rows = tuple(
        row for row in material_schema_rows if row.family_id in spec.family_ids
    )
    delivery_rows = tuple(
        row for row in delivery_preset_rows if row.family_id in spec.family_ids
    )
    artifact_channel_ids = _unique_values(
        row.drilldown_channel_id
        for row in artifact_rows
        if set(row.pack_ids) & set(spec.pack_ids)
        or set(row.family_ids) & set(spec.family_ids)
    )
    boundary_notes = _unique_values(
        (
            *(pack.boundary for pack in packs),
            *(boundary for family in families for boundary in family.boundaries),
            *(sample.boundary_phrase for sample in samples),
            *(sample.notes for sample in samples),
        )
    )
    manual_gate_ids = _unique_values(
        (
            *(cell.manual_gate_ids for cell in cells),
            *(cell.expected_plugin_gate_ids for cell in cells),
            *(fixture.manual_gate_id for fixture in fixtures),
            *(gate_id for row in family_depth for gate_id in row.plugin_gate_ids),
        )
    )
    fixture_ids = _unique_values(
        (
            *(fixture.fixture_id for fixture in fixtures),
            *(
                fixture_id
                for row in family_depth
                for fixture_id in (*row.independent_fixture_ids, *row.manual_boundary_fixture_ids)
            ),
        )
    )
    docx_surfaces = _unique_values(
        (
            *(surface for fixture in fixtures for surface in fixture.docx_surfaces),
            *(surface for row in family_depth for surface in row.docx_surfaces),
        )
    )
    expected_behaviors = _unique_values(
        (
            *(behavior for fixture in fixtures for behavior in fixture.expected_behaviors),
            *(behavior for row in family_depth for behavior in row.expected_behaviors),
        )
    )
    report_expectations = _unique_values(
        (
            *(expectation for fixture in fixtures for expectation in fixture.report_expectations),
            *(expectation for row in family_depth for expectation in row.report_expectations),
        )
    )
    material_schema_ids = _unique_values(
        (
            *(family.material_schema_ids for family in families),
            *(schema_id for row in material_rows for schema_id in row.material_schema_ids),
        )
    )
    delivery_preset_ids = _unique_values(
        (
            *(family.delivery_presets for family in families),
            *(preset_id for row in delivery_rows for preset_id in row.actual_delivery_preset_ids),
        )
    )
    control_alignment_ids = (
        ("scene_control_runtime_consistency_audit",)
        if control_runtime_ready
        else ()
    )

    issue_ids = _row_issue_ids(
        spec,
        packs=packs,
        families=families,
        boundary_notes=boundary_notes,
        manual_gate_ids=manual_gate_ids,
        control_alignment_ids=control_alignment_ids,
    )
    warning_ids = _row_warning_ids(
        spec,
        request_cell_ids=tuple(cell.sample_id for cell in cells),
        fixture_ids=fixture_ids,
        docx_surfaces=docx_surfaces,
        missing_journey_groups=missing_journey_groups,
        artifact_channel_ids=artifact_channel_ids,
        material_schema_ids=material_schema_ids,
        count_profile_ids=_unique_values(
            (
                *(family.count_profiles for family in families),
                *(profile_id for row in count_rows for profile_id in row.count_profile_ids),
            )
        ),
        delivery_preset_ids=delivery_preset_ids,
        input_format_ids=_unique_values(
            (
                *(family.input_formats for family in families),
                *(fmt for row in input_rows for fmt in row.actual_accepted_formats),
            )
        ),
    )

    count_profile_ids = _unique_values(
        (
            *(family.count_profiles for family in families),
            *(profile_id for row in count_rows for profile_id in row.count_profile_ids),
        )
    )
    input_format_ids = _unique_values(
        (
            *(family.input_formats for family in families),
            *(fmt for row in input_rows for fmt in row.actual_accepted_formats),
        )
    )
    return SceneBusinessCapabilityRow(
        capability_id=spec.capability_id,
        label=spec.label,
        group_id=spec.group_id,
        priority=spec.priority,
        pack_ids=spec.pack_ids,
        family_ids=spec.family_ids,
        boundary_policy=spec.boundary_policy,
        boundary_summary="; ".join(boundary_notes),
        request_cell_ids=tuple(cell.sample_id for cell in cells),
        fixture_ids=fixture_ids,
        manual_gate_ids=manual_gate_ids,
        journey_type_ids=journey_type_ids,
        required_journey_groups=spec.required_journey_groups,
        missing_journey_groups=missing_journey_groups,
        input_format_ids=input_format_ids,
        material_schema_ids=material_schema_ids,
        count_profile_ids=count_profile_ids,
        delivery_preset_ids=delivery_preset_ids,
        docx_surfaces=docx_surfaces,
        expected_behaviors=expected_behaviors,
        report_expectations=report_expectations,
        artifact_channel_ids=artifact_channel_ids,
        control_alignment_ids=control_alignment_ids,
        adopted_external_record_ids=spec.adopted_external_record_ids,
        boundary_note_ids=boundary_notes,
        issue_ids=issue_ids,
        warning_ids=warning_ids,
    )


def _row_issue_ids(
    spec: SceneBusinessCapabilitySpec,
    *,
    packs: Sequence[SceneCoveragePack],
    families: Sequence[PlannedSceneFamily],
    boundary_notes: Sequence[str],
    manual_gate_ids: Sequence[str],
    control_alignment_ids: Sequence[str],
) -> tuple[str, ...]:
    issues: list[str] = []
    if len(packs) != len(spec.pack_ids):
        issues.append("unknown_pack")
    if len(families) != len(spec.family_ids):
        issues.append("unknown_family")
    if not boundary_notes:
        issues.append("missing_boundary_statement")
    if spec.boundary_policy in {
        "core_with_manual_gate",
        "professional_manual_gate",
        "import_handoff_boundary",
    } and not manual_gate_ids:
        issues.append("missing_manual_gate_for_boundary_policy")
    if spec.boundary_policy not in {
        "core_auto",
        "core_with_boundary_note",
        "core_with_manual_gate",
        "professional_manual_gate",
        "import_handoff_boundary",
    }:
        issues.append("unknown_boundary_policy")
    if not control_alignment_ids:
        issues.append("missing_scene_control_style_alignment")
    return tuple(issues)


def _row_warning_ids(
    spec: SceneBusinessCapabilitySpec,
    *,
    request_cell_ids: Sequence[str],
    fixture_ids: Sequence[str],
    docx_surfaces: Sequence[str],
    missing_journey_groups: Sequence[str],
    artifact_channel_ids: Sequence[str],
    material_schema_ids: Sequence[str],
    count_profile_ids: Sequence[str],
    delivery_preset_ids: Sequence[str],
    input_format_ids: Sequence[str],
) -> tuple[str, ...]:
    warnings: list[str] = []
    if not request_cell_ids:
        warnings.append("missing_request_cell_evidence")
    if not fixture_ids:
        warnings.append("missing_real_docx_fixture")
    if not docx_surfaces:
        warnings.append("missing_docx_surface_evidence")
    for group in missing_journey_groups:
        warnings.append(f"missing_{group}_journey")
    if not artifact_channel_ids:
        warnings.append("missing_report_artifact_drilldown")
    if spec.family_ids and not input_format_ids:
        warnings.append("missing_input_source_profile")
    if spec.family_ids and not count_profile_ids:
        warnings.append("missing_count_profile")
    if spec.family_ids and _requires_material_schema(spec) and not material_schema_ids:
        warnings.append("missing_material_schema")
    if spec.family_ids and not delivery_preset_ids:
        warnings.append("missing_delivery_preset")
    return tuple(warnings)


def _sample_mapping_issues(
    rows: Sequence[SceneBusinessCapabilityRow],
) -> tuple[SceneBusinessCapabilityIssue, ...]:
    row_family_ids = {family_id for row in rows for family_id in row.family_ids}
    row_pack_ids = {pack_id for row in rows for pack_id in row.pack_ids}
    issues: list[SceneBusinessCapabilityIssue] = []
    for sample in list_high_frequency_request_samples():
        if sample.expected_status == "unmatched":
            continue
        missing_family_ids = tuple(
            family_id
            for family_id in sample.expected_family_ids
            if family_id not in row_family_ids
        )
        missing_pack_ids = tuple(
            pack_id
            for pack_id in sample.expected_pack_ids
            if pack_id not in row_pack_ids
        )
        if missing_family_ids:
            issues.append(
                _issue(
                    "request_sample",
                    sample.sample_id,
                    "request_sample_family_not_mapped",
                    (
                        f"Request sample '{sample.sample_id}' targets families not "
                        f"in the business capability matrix: {', '.join(missing_family_ids)}."
                    ),
                )
            )
        if missing_pack_ids:
            issues.append(
                _issue(
                    "request_sample",
                    sample.sample_id,
                    "request_sample_pack_not_mapped",
                    (
                        f"Request sample '{sample.sample_id}' targets packs not "
                        f"in the business capability matrix: {', '.join(missing_pack_ids)}."
                    ),
                )
            )
    return tuple(issues)


def _matching_request_cells(
    spec: SceneBusinessCapabilitySpec,
    cells: Sequence[SceneRequestCellFixtureSpec],
) -> tuple[SceneRequestCellFixtureSpec, ...]:
    pack_ids = set(spec.pack_ids)
    family_ids = set(spec.family_ids)
    if family_ids:
        return tuple(
            cell
            for cell in cells
            if set(cell.expected_family_ids) & family_ids
        )
    return tuple(
        cell
        for cell in cells
        if set(cell.expected_pack_ids) & pack_ids
    )


def _matching_samples(
    spec: SceneBusinessCapabilitySpec,
    samples: Sequence[HighFrequencyRequestSample],
) -> tuple[HighFrequencyRequestSample, ...]:
    pack_ids = set(spec.pack_ids)
    family_ids = set(spec.family_ids)
    if family_ids:
        return tuple(
            sample
            for sample in samples
            if set(sample.expected_family_ids) & family_ids
        )
    return tuple(
        sample
        for sample in samples
        if set(sample.expected_pack_ids) & pack_ids
    )


def _matching_journey_paths(
    spec: SceneBusinessCapabilitySpec,
    paths: Sequence[SceneUserJourneyPathRow],
) -> tuple[SceneUserJourneyPathRow, ...]:
    pack_ids = set(spec.pack_ids)
    family_ids = set(spec.family_ids)
    return tuple(
        row
        for row in paths
        if set(row.pack_ids) & pack_ids or set(row.family_ids) & family_ids
    )


def _fixture_specs(fixture_ids: Iterable[str]) -> tuple[SceneSampleFixtureSpec, ...]:
    return tuple(
        SCENE_SAMPLE_FIXTURE_MAP[fixture_id]
        for fixture_id in fixture_ids
        if fixture_id in SCENE_SAMPLE_FIXTURE_MAP
    )


def _family_group_id(family_id: str) -> str:
    groups = {
        "thesis_cn": "academic_and_submission",
        "journal_en": "academic_and_submission",
        "exam_teaching": "education_exam",
        "project_application": "application_and_business_reports",
        "contract_delivery": "contract_and_legal_boundary",
        "hr_batch_documents": "batch_and_fixed_form",
        "meeting_policy_documents": "official_archive",
        "product_sales_documents": "application_and_business_reports",
        "long_document_publishing": "technical_and_long_docs",
        "form_batch_documents": "batch_and_fixed_form",
        "qualification_archive_packages": "bidding_and_qualification",
        "finance_quote_documents": "professional_manual_boundary",
        "ip_patent_documents": "professional_manual_boundary",
        "bilingual_translation_documents": "professional_manual_boundary",
        "regulated_disclosure_documents": "professional_manual_boundary",
    }
    return groups.get(family_id, "unclassified")


def _family_boundary_policy(family: PlannedSceneFamily) -> str:
    if family.priority == "P2":
        return "professional_manual_gate"
    if family.family_id == "exam_teaching":
        return "core_with_manual_gate"
    if any("does not" in boundary for boundary in family.boundaries):
        return "core_with_boundary_note"
    return "core_auto"


def _family_required_journey_groups(
    family: PlannedSceneFamily,
) -> tuple[str, ...]:
    if family.priority in HIGH_PRIORITY_CAPABILITY_PRIORITIES:
        return ("success", "degraded", "failure_or_manual_boundary")
    if family.priority == "P2":
        return ("manual_boundary",)
    return ("success",)


def _family_external_record_ids(family_id: str) -> tuple[str, ...]:
    records: list[str] = []
    if family_id in {
        "thesis_cn",
        "journal_en",
        "project_application",
        "long_document_publishing",
    }:
        records.append("count_engine_tech_record")
    if family_id == "exam_teaching":
        records.append("exam_generator_tech_stack_record")
    return tuple(records)


def _requires_material_schema(spec: SceneBusinessCapabilitySpec) -> bool:
    return any(
        PLANNED_SCENE_FAMILY_MAP[family_id].material_schema_ids
        for family_id in spec.family_ids
        if family_id in PLANNED_SCENE_FAMILY_MAP
    )


def _journey_group_covered(group: str, journey_type_ids: Sequence[str]) -> bool:
    if group == "failure_or_manual_boundary":
        return bool({"failure", "manual_boundary"} & set(journey_type_ids))
    return group in journey_type_ids


def _ordered_journey_types(values: Iterable[str]) -> tuple[str, ...]:
    present = set(str(value or "").strip() for value in values if str(value or "").strip())
    return tuple(path_type for path_type in SCENE_USER_JOURNEY_PATH_TYPES if path_type in present)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneBusinessCapabilitySourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
    return tuple(
        SceneBusinessCapabilitySourceEvidence(
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
            SCENE_BUSINESS_CAPABILITY_SOURCE_MARKERS,
        )
    )


def _issue(
    scope_type: str,
    scope_id: str,
    kind: str,
    message: str,
    *,
    severity: str = "error",
) -> SceneBusinessCapabilityIssue:
    return SceneBusinessCapabilityIssue(
        scope_type=scope_type,
        scope_id=scope_id,
        kind=kind,
        message=message,
        severity=severity,
    )


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if isinstance(value, (tuple, list, set)):
            candidates = value
        else:
            candidates = (value,)
        for candidate in candidates:
            normalized = str(candidate or "").strip()
            if normalized and normalized not in result:
                result.append(normalized)
    return tuple(result)


__all__ = [
    "HIGH_PRIORITY_CAPABILITY_PRIORITIES",
    "SCENE_BUSINESS_CAPABILITY_JOURNEY_GROUPS",
    "SCENE_BUSINESS_CAPABILITY_MATRIX_AUDIT_ID",
    "SceneBusinessCapabilityIssue",
    "SceneBusinessCapabilityMatrixAuditReport",
    "SceneBusinessCapabilityRow",
    "audit_scene_business_capability_matrix_report",
    "build_scene_business_capability_matrix_audit_report",
]
