"""Horizontal InputSourceProfile audit for high-frequency scenes.

N2.171 keeps input and rendering semantics from collapsing into a single
"upload document" selector.  The audit traces planned family input contracts,
executable scene defaults, structured/material sources, delivery rendering
targets, and plugin/manual input boundaries.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config.material_schema_registry import MATERIAL_SCHEMA_MAP, resolve_material_schema_ids
from src.config.plugin_manual_gate import list_plugin_manual_gates
from src.config.scene import DeliveryPreset, SceneWorkspace
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_packs_for_family,
    list_scene_coverage_packs,
)
from src.config.scene_family_application import (
    apply_planned_scene_family_defaults,
    planned_family_is_application_boundary_only,
)
from src.config.scene_family_registry import (
    PLANNED_SCENE_FAMILY_MAP,
    PlannedSceneFamily,
    list_planned_scene_families,
)
from src.config.scene_source_evidence import scan_scene_source_markers


SCENE_INPUT_SOURCE_AUDIT_SOURCE_ID = "scene_input_source_audit"

SCENE_INPUT_SOURCE_SOURCE_MARKERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "scene_model_input_source_profile",
        "src/config/scene.py",
        ("class InputSourceProfile", "accepted_formats", "high_risk_imports"),
    ),
    (
        "scene_family_registry",
        "src/config/scene_family_registry.py",
        ("PLANNED_SCENE_FAMILIES", "input_formats", "material_schema_ids"),
    ),
    (
        "scene_family_application",
        "src/config/scene_family_application.py",
        ("input_source_profile", "structured_formats", "material_schema_id"),
    ),
    (
        "config_scene_presets",
        "src/config/scene_presets.py",
        ("_input_profile", "accepted_formats", "structured_formats"),
    ),
    (
        "workbench_input_preflight",
        "src/ui/panels/workbench/material_artifacts.py",
        ("accepted_formats", "structured_formats", "material_schema_id"),
    ),
    (
        "material_schema_registry",
        "src/config/material_schema_registry.py",
        ("MATERIAL_SCHEMAS", "resolve_material_schema_ids", "MaterialSchema"),
    ),
    (
        "delivery_rendering_targets",
        "src/config/scene_delivery_preset_audit.py",
        ("target_template_ids", "structured_intermediate_preset_count"),
    ),
    (
        "import_handoff_boundary",
        "src/config/scene_import_handoff_audit.py",
        ("source_type", "confidence_level", "handoff_pack_id"),
    ),
    (
        "plugin_manual_gate",
        "src/config/plugin_manual_gate.py",
        ("unsupported_core_inputs", "manual_confirmation_required"),
    ),
)

STRUCTURED_SOURCE_FORMATS: tuple[str, ...] = (
    "json",
    "xlsx",
    "bibtex",
    "csl_json",
)

BOUNDARY_INPUT_SOURCE_IDS: tuple[str, ...] = (
    "full_latex_project",
    "pdf_ocr_import",
    "ai_content_generation",
    "complex_diagram_generation",
)

RENDER_SOURCE_HINTS: tuple[str, ...] = (
    "template",
    "final_docx",
    "structured_intermediate",
    "material_package",
    "material_manifest",
    "compare_docx",
)


@dataclass(frozen=True, slots=True)
class SceneInputSourceIssue:
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
class SceneInputSourceSourceEvidence:
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
class SceneInputSourceFamilyRow:
    family_id: str
    name: str
    priority: str
    status: str
    pack_ids: tuple[str, ...]
    planned_input_formats: tuple[str, ...]
    actual_accepted_formats: tuple[str, ...]
    matched_input_formats: tuple[str, ...]
    missing_input_formats: tuple[str, ...]
    structured_formats: tuple[str, ...]
    material_schema_ids: tuple[str, ...]
    actual_material_schema_ids: tuple[str, ...]
    missing_material_schema_ids: tuple[str, ...]
    require_material_package: bool
    markdown_policy: str
    latex_policy: str
    high_risk_imports: tuple[str, ...]
    failure_policy: str
    delivery_preset_ids: tuple[str, ...]
    render_source_ids: tuple[str, ...]
    target_template_ids: tuple[str, ...]
    structured_intermediate_preset_count: int
    application_applied: bool
    plugin_boundary_only: bool
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"

    @property
    def is_boundary(self) -> bool:
        return self.status == "boundary"

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "planned_input_formats": list(self.planned_input_formats),
            "actual_accepted_formats": list(self.actual_accepted_formats),
            "matched_input_formats": list(self.matched_input_formats),
            "missing_input_formats": list(self.missing_input_formats),
            "structured_formats": list(self.structured_formats),
            "material_schema_ids": list(self.material_schema_ids),
            "actual_material_schema_ids": list(self.actual_material_schema_ids),
            "missing_material_schema_ids": list(self.missing_material_schema_ids),
            "require_material_package": self.require_material_package,
            "markdown_policy": self.markdown_policy,
            "latex_policy": self.latex_policy,
            "high_risk_imports": list(self.high_risk_imports),
            "failure_policy": self.failure_policy,
            "delivery_preset_ids": list(self.delivery_preset_ids),
            "render_source_ids": list(self.render_source_ids),
            "target_template_ids": list(self.target_template_ids),
            "structured_intermediate_preset_count": (
                self.structured_intermediate_preset_count
            ),
            "application_applied": self.application_applied,
            "plugin_boundary_only": self.plugin_boundary_only,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneInputSourcePackRow:
    pack_id: str
    label: str
    status: str
    input_relevant: bool
    plugin_boundary: bool
    planned_family_ids: tuple[str, ...]
    executable_scene_ids: tuple[str, ...]
    input_formats: tuple[str, ...]
    structured_formats: tuple[str, ...]
    material_schema_ids: tuple[str, ...]
    render_source_ids: tuple[str, ...]
    target_template_ids: tuple[str, ...]
    boundary_input_source_ids: tuple[str, ...]
    family_statuses: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "label": self.label,
            "status": self.status,
            "input_relevant": self.input_relevant,
            "plugin_boundary": self.plugin_boundary,
            "planned_family_ids": list(self.planned_family_ids),
            "executable_scene_ids": list(self.executable_scene_ids),
            "input_formats": list(self.input_formats),
            "structured_formats": list(self.structured_formats),
            "material_schema_ids": list(self.material_schema_ids),
            "render_source_ids": list(self.render_source_ids),
            "target_template_ids": list(self.target_template_ids),
            "boundary_input_source_ids": list(self.boundary_input_source_ids),
            "family_statuses": list(self.family_statuses),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneInputSourceFormatRow:
    source_id: str
    label: str
    status: str
    source_kind: str
    family_ids: tuple[str, ...]
    pack_ids: tuple[str, ...]
    accepted_by_executable_scene_ids: tuple[str, ...]
    boundary_gate_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "label": self.label,
            "status": self.status,
            "source_kind": self.source_kind,
            "family_ids": list(self.family_ids),
            "pack_ids": list(self.pack_ids),
            "accepted_by_executable_scene_ids": list(
                self.accepted_by_executable_scene_ids
            ),
            "boundary_gate_ids": list(self.boundary_gate_ids),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneInputSourceAuditReport:
    family_rows: tuple[SceneInputSourceFamilyRow, ...]
    pack_rows: tuple[SceneInputSourcePackRow, ...]
    format_rows: tuple[SceneInputSourceFormatRow, ...]
    issues: tuple[SceneInputSourceIssue, ...]
    warnings: tuple[SceneInputSourceIssue, ...]
    source_evidence: tuple[SceneInputSourceSourceEvidence, ...]
    pack_filter: str = ""
    family_filter: str = ""
    source_filter: str = ""
    total_family_count: int = 0
    total_pack_count: int = 0

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

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
    def pack_count(self) -> int:
        return len(self.pack_rows)

    @property
    def input_pack_count(self) -> int:
        return sum(1 for row in self.pack_rows if row.input_relevant)

    @property
    def ready_input_pack_count(self) -> int:
        return sum(
            1
            for row in self.pack_rows
            if row.input_relevant and row.status in {"ready", "boundary_ready"}
        )

    @property
    def accepted_format_count(self) -> int:
        return len(
            _unique_values(
                fmt
                for row in self.family_rows
                for fmt in row.actual_accepted_formats
            )
        )

    @property
    def structured_format_count(self) -> int:
        return len(
            _unique_values(
                fmt for row in self.family_rows for fmt in row.structured_formats
            )
        )

    @property
    def material_required_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.require_material_package)

    @property
    def markdown_enabled_family_count(self) -> int:
        return sum(
            1
            for row in self.family_rows
            if row.markdown_policy and row.markdown_policy != "disabled"
        )

    @property
    def latex_fragment_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.latex_policy == "formula_fragments_only")

    @property
    def render_source_count(self) -> int:
        return len(
            _unique_values(
                source
                for row in self.family_rows
                for source in row.render_source_ids
            )
        )

    @property
    def target_template_count(self) -> int:
        return len(
            _unique_values(
                template_id
                for row in self.family_rows
                for template_id in row.target_template_ids
            )
        )

    @property
    def boundary_input_source_count(self) -> int:
        return sum(1 for row in self.format_rows if row.source_kind == "boundary")

    @property
    def format_count(self) -> int:
        return len(self.format_rows)

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
            "source_id": SCENE_INPUT_SOURCE_AUDIT_SOURCE_ID,
            "pack_filter": self.pack_filter,
            "family_filter": self.family_filter,
            "source_filter": self.source_filter,
            "counts": {
                "family_count": self.family_count,
                "total_family_count": self.total_family_count,
                "ready_family_count": self.ready_family_count,
                "boundary_family_count": self.boundary_family_count,
                "pack_count": self.pack_count,
                "total_pack_count": self.total_pack_count,
                "input_pack_count": self.input_pack_count,
                "ready_input_pack_count": self.ready_input_pack_count,
                "accepted_format_count": self.accepted_format_count,
                "structured_format_count": self.structured_format_count,
                "material_required_family_count": (
                    self.material_required_family_count
                ),
                "markdown_enabled_family_count": (
                    self.markdown_enabled_family_count
                ),
                "latex_fragment_family_count": self.latex_fragment_family_count,
                "render_source_count": self.render_source_count,
                "target_template_count": self.target_template_count,
                "boundary_input_source_count": self.boundary_input_source_count,
                "format_count": self.format_count,
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "family_rows": [row.to_payload() for row in self.family_rows],
            "pack_rows": [row.to_payload() for row in self.pack_rows],
            "format_rows": [row.to_payload() for row in self.format_rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_input_source_audit_report(
    *,
    pack_id: str = "",
    family_id: str = "",
    source_id: str = "",
    project_root: Path | str | None = None,
) -> SceneInputSourceAuditReport:
    normalized_pack = str(pack_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_source = str(source_id or "").strip()

    executable_inputs = _executable_input_source_summary()
    all_family_rows = tuple(_family_row(family) for family in list_planned_scene_families())
    all_pack_rows = tuple(
        _pack_row(
            pack,
            family_rows=all_family_rows,
            executable_inputs=executable_inputs,
        )
        for pack in list_scene_coverage_packs()
    )
    all_format_rows = tuple(
        _format_row(
            source,
            family_rows=all_family_rows,
            pack_rows=all_pack_rows,
            executable_inputs=executable_inputs,
        )
        for source in _all_input_source_ids(all_family_rows, all_pack_rows, executable_inputs)
    )

    family_rows = _filter_family_rows(
        all_family_rows,
        pack_id=normalized_pack,
        family_id=normalized_family,
        source_id=normalized_source,
    )
    pack_rows = _filter_pack_rows(
        all_pack_rows,
        pack_id=normalized_pack,
        family_id=normalized_family,
        source_id=normalized_source,
    )
    format_rows = _filter_format_rows(
        all_format_rows,
        pack_id=normalized_pack,
        family_id=normalized_family,
        source_id=normalized_source,
    )
    source_evidence = _source_evidence(project_root)
    issues, warnings = audit_scene_input_source_report(
        SceneInputSourceAuditReport(
            family_rows=family_rows,
            pack_rows=pack_rows,
            format_rows=format_rows,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            pack_filter=normalized_pack,
            family_filter=normalized_family,
            source_filter=normalized_source,
            total_family_count=len(all_family_rows),
            total_pack_count=len(all_pack_rows),
        )
    )
    return SceneInputSourceAuditReport(
        family_rows=family_rows,
        pack_rows=pack_rows,
        format_rows=format_rows,
        issues=issues,
        warnings=warnings,
        source_evidence=source_evidence,
        pack_filter=normalized_pack,
        family_filter=normalized_family,
        source_filter=normalized_source,
        total_family_count=len(all_family_rows),
        total_pack_count=len(all_pack_rows),
    )


def audit_scene_input_source_report(
    report: SceneInputSourceAuditReport,
) -> tuple[tuple[SceneInputSourceIssue, ...], tuple[SceneInputSourceIssue, ...]]:
    issues: list[SceneInputSourceIssue] = []
    warnings: list[SceneInputSourceIssue] = []

    for row in report.family_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneInputSourceIssue(
                    "family",
                    row.family_id,
                    issue_id,
                    f"InputSourceProfile family row has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneInputSourceIssue(
                    "family",
                    row.family_id,
                    warning_id,
                    f"InputSourceProfile family row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for row in report.pack_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneInputSourceIssue(
                    "pack",
                    row.pack_id,
                    issue_id,
                    f"InputSourceProfile pack row has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneInputSourceIssue(
                    "pack",
                    row.pack_id,
                    warning_id,
                    f"InputSourceProfile pack row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for row in report.format_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneInputSourceIssue(
                    "source",
                    row.source_id,
                    issue_id,
                    f"Input source row has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneInputSourceIssue(
                    "source",
                    row.source_id,
                    warning_id,
                    f"Input source row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneInputSourceIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    f"Missing source markers: {', '.join(evidence.missing_markers)}",
                )
            )
    return tuple(issues), tuple(warnings)


def _family_row(family: PlannedSceneFamily) -> SceneInputSourceFamilyRow:
    scene = SceneWorkspace(scene_id=family.family_id, category=family.family_id)
    result = apply_planned_scene_family_defaults(scene, family_id=family.family_id)
    profile = getattr(scene, "input_source_profile", None)
    plugin_boundary_only = planned_family_is_application_boundary_only(family.family_id)
    actual_formats = () if plugin_boundary_only and not result.applied else _unique_values(
        getattr(profile, "accepted_formats", []) or []
    )
    structured_formats = () if plugin_boundary_only and not result.applied else _unique_values(
        getattr(profile, "structured_formats", []) or []
    )
    material_schema_ids = resolve_material_schema_ids(
        str(getattr(profile, "material_schema_id", "") or ""),
        list(getattr(profile, "material_schema_ids", []) or []),
    )
    actual_material_schema_ids = (
        ()
        if plugin_boundary_only and not result.applied
        else material_schema_ids
    )
    missing_input_formats = tuple(
        fmt for fmt in family.input_formats if fmt not in actual_formats
    )
    missing_material_schema_ids = tuple(
        schema_id
        for schema_id in family.material_schema_ids
        if schema_id not in actual_material_schema_ids
    )
    presets = (
        ()
        if plugin_boundary_only and not result.applied
        else tuple(getattr(scene, "delivery_presets", []) or ())
    )
    render_source_ids = _render_source_ids(presets)
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if not result.applied and not plugin_boundary_only:
        issue_ids.append("family_without_input_source_application_defaults")
    if not plugin_boundary_only:
        for fmt in missing_input_formats:
            issue_ids.append(f"missing_input_format.{fmt}")
        for schema_id in missing_material_schema_ids:
            issue_ids.append(f"missing_material_schema.{schema_id}")
        _extend_input_contract_issues(
            issue_ids,
            family,
            accepted_formats=actual_formats,
            structured_formats=structured_formats,
            markdown_policy=str(getattr(profile, "markdown_policy", "") or ""),
            latex_policy=str(getattr(profile, "latex_policy", "") or ""),
            material_schema_ids=actual_material_schema_ids,
        )
    else:
        warning_ids.append("plugin_manual_boundary_input_contract")

    status = "boundary" if plugin_boundary_only else "ready"
    if issue_ids:
        status = "blocked"

    return SceneInputSourceFamilyRow(
        family_id=family.family_id,
        name=family.name,
        priority=family.priority,
        status=status,
        pack_ids=tuple(pack.pack_id for pack in coverage_packs_for_family(family.family_id)),
        planned_input_formats=family.input_formats,
        actual_accepted_formats=actual_formats,
        matched_input_formats=tuple(fmt for fmt in family.input_formats if fmt in actual_formats),
        missing_input_formats=missing_input_formats,
        structured_formats=structured_formats,
        material_schema_ids=family.material_schema_ids,
        actual_material_schema_ids=actual_material_schema_ids,
        missing_material_schema_ids=missing_material_schema_ids,
        require_material_package=bool(getattr(profile, "require_material_package", False))
        if not (plugin_boundary_only and not result.applied)
        else False,
        markdown_policy=str(getattr(profile, "markdown_policy", "") or ""),
        latex_policy=str(getattr(profile, "latex_policy", "") or ""),
        high_risk_imports=()
        if plugin_boundary_only and not result.applied
        else _unique_values(getattr(profile, "high_risk_imports", []) or []),
        failure_policy=str(getattr(profile, "failure_policy", "") or ""),
        delivery_preset_ids=_unique_values(getattr(preset, "preset_id", "") for preset in presets),
        render_source_ids=render_source_ids,
        target_template_ids=_unique_values(
            getattr(preset, "target_template_id", "") for preset in presets
        ),
        structured_intermediate_preset_count=sum(
            1 for preset in presets if bool(getattr(preset, "include_structured_intermediate", False))
        ),
        application_applied=bool(result.applied),
        plugin_boundary_only=plugin_boundary_only,
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _pack_row(
    pack: SceneCoveragePack,
    *,
    family_rows: Sequence[SceneInputSourceFamilyRow],
    executable_inputs: Mapping[str, dict[str, tuple[str, ...]]],
) -> SceneInputSourcePackRow:
    rows = tuple(row for row in family_rows if row.family_id in pack.planned_family_ids)
    executable_formats = _unique_values(
        fmt
        for scene_id in pack.executable_scene_ids
        for fmt in executable_inputs.get(scene_id, {}).get("accepted_formats", ())
    )
    executable_structured = _unique_values(
        fmt
        for scene_id in pack.executable_scene_ids
        for fmt in executable_inputs.get(scene_id, {}).get("structured_formats", ())
    )
    executable_schemas = _unique_values(
        schema_id
        for scene_id in pack.executable_scene_ids
        for schema_id in executable_inputs.get(scene_id, {}).get("material_schema_ids", ())
    )
    executable_render_sources = _unique_values(
        source
        for scene_id in pack.executable_scene_ids
        for source in executable_inputs.get(scene_id, {}).get("render_source_ids", ())
    )
    executable_target_templates = _unique_values(
        template_id
        for scene_id in pack.executable_scene_ids
        for template_id in executable_inputs.get(scene_id, {}).get("target_template_ids", ())
    )
    input_formats = _unique_values(
        *[
            (*row.planned_input_formats, *row.actual_accepted_formats)
            for row in rows
        ],
        executable_formats,
    )
    structured_formats = _unique_values(
        *[row.structured_formats for row in rows],
        executable_structured,
    )
    material_schema_ids = _unique_values(
        *[row.actual_material_schema_ids for row in rows],
        executable_schemas,
    )
    render_source_ids = _unique_values(
        *[row.render_source_ids for row in rows],
        executable_render_sources,
    )
    target_template_ids = _unique_values(
        *[row.target_template_ids for row in rows],
        executable_target_templates,
    )
    boundary_input_source_ids = _pack_boundary_input_source_ids(pack)
    input_relevant = bool(
        input_formats
        or structured_formats
        or material_schema_ids
        or "input_fact_source" in pack.capability_axis_ids
    )
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if "input_fact_source" in pack.capability_axis_ids and not input_formats:
        if pack.plugin_boundary:
            warning_ids.append("pack_input_axis_boundary_only")
        else:
            issue_ids.append("pack_input_axis_without_input_formats")
    if pack.plugin_boundary and boundary_input_source_ids:
        warning_ids.append("pack_requires_plugin_or_manual_input_boundary")
    for row in rows:
        for issue_id in row.issue_ids:
            issue_ids.append(f"family.{row.family_id}.{issue_id}")
    if input_relevant and not render_source_ids and not pack.plugin_boundary:
        issue_ids.append("pack_input_without_render_source")

    status = "not_applicable"
    if input_relevant:
        status = "blocked" if issue_ids else "ready"
        if pack.plugin_boundary and not issue_ids:
            status = "boundary_ready"

    return SceneInputSourcePackRow(
        pack_id=pack.pack_id,
        label=pack.label,
        status=status,
        input_relevant=input_relevant,
        plugin_boundary=pack.plugin_boundary,
        planned_family_ids=pack.planned_family_ids,
        executable_scene_ids=pack.executable_scene_ids,
        input_formats=input_formats,
        structured_formats=structured_formats,
        material_schema_ids=material_schema_ids,
        render_source_ids=render_source_ids,
        target_template_ids=target_template_ids,
        boundary_input_source_ids=boundary_input_source_ids,
        family_statuses=_unique_values(row.status for row in rows),
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _format_row(
    source_id: str,
    *,
    family_rows: Sequence[SceneInputSourceFamilyRow],
    pack_rows: Sequence[SceneInputSourcePackRow],
    executable_inputs: Mapping[str, dict[str, tuple[str, ...]]],
) -> SceneInputSourceFormatRow:
    family_ids = tuple(
        row.family_id
        for row in family_rows
        if source_id in row.planned_input_formats
        or source_id in row.actual_accepted_formats
        or source_id in row.structured_formats
        or source_id in row.high_risk_imports
    )
    pack_ids = tuple(
        row.pack_id
        for row in pack_rows
        if source_id in row.input_formats
        or source_id in row.structured_formats
        or source_id in row.boundary_input_source_ids
    )
    accepted_by_executable_scene_ids = tuple(
        scene_id
        for scene_id, data in executable_inputs.items()
        if source_id in data.get("accepted_formats", ())
        or source_id in data.get("structured_formats", ())
    )
    boundary_gate_ids = _boundary_gate_ids_for_source(source_id)
    source_kind = "boundary" if source_id in BOUNDARY_INPUT_SOURCE_IDS else "core"
    if source_id in STRUCTURED_SOURCE_FORMATS:
        source_kind = "structured"
    if source_id == "markdown":
        source_kind = "preview"
    if source_id == "docx":
        source_kind = "word_document"
    issue_ids: list[str] = []
    warning_ids: list[str] = []
    if source_kind == "boundary" and not boundary_gate_ids:
        warning_ids.append("boundary_source_without_explicit_gate")
    if source_kind != "boundary" and not (family_ids or accepted_by_executable_scene_ids):
        issue_ids.append("unclaimed_input_source")
    status = "ready" if not issue_ids else "blocked"
    if source_kind == "boundary":
        status = "boundary" if not issue_ids else "blocked"
    return SceneInputSourceFormatRow(
        source_id=source_id,
        label=_source_label(source_id),
        status=status,
        source_kind=source_kind,
        family_ids=family_ids,
        pack_ids=pack_ids,
        accepted_by_executable_scene_ids=accepted_by_executable_scene_ids,
        boundary_gate_ids=boundary_gate_ids,
        issue_ids=tuple(issue_ids),
        warning_ids=tuple(warning_ids),
    )


def _extend_input_contract_issues(
    issue_ids: list[str],
    family: PlannedSceneFamily,
    *,
    accepted_formats: Sequence[str],
    structured_formats: Sequence[str],
    markdown_policy: str,
    latex_policy: str,
    material_schema_ids: Sequence[str],
) -> None:
    for fmt in family.input_formats:
        if fmt in STRUCTURED_SOURCE_FORMATS and fmt not in structured_formats:
            issue_ids.append(f"structured_format_not_declared.{fmt}")
    if "markdown" in family.input_formats and markdown_policy == "disabled":
        issue_ids.append("markdown_input_with_disabled_policy")
    if "markdown" not in family.input_formats and markdown_policy != "disabled":
        # This is a warning candidate, but not a blocker: many families allow
        # Markdown as an authoring preview even when docx remains the input.
        pass
    if "latex" in accepted_formats and latex_policy == "disabled":
        issue_ids.append("latex_input_with_disabled_policy")
    for schema_id in material_schema_ids:
        if schema_id not in MATERIAL_SCHEMA_MAP:
            issue_ids.append(f"unknown_material_schema.{schema_id}")


def _render_source_ids(presets: Sequence[DeliveryPreset]) -> tuple[str, ...]:
    values: list[str] = []
    for preset in presets:
        target_template_id = str(getattr(preset, "target_template_id", "") or "").strip()
        if target_template_id:
            values.append(f"template:{target_template_id}")
        artifacts = getattr(preset, "artifacts", None)
        if bool(getattr(artifacts, "final_docx", False)):
            values.append("final_docx")
        if bool(getattr(artifacts, "compare_docx", False)):
            values.append("compare_docx")
        if bool(getattr(artifacts, "material_manifest", False)):
            values.append("material_manifest")
        if bool(getattr(artifacts, "material_package", False)):
            values.append("material_package")
        if bool(getattr(preset, "include_structured_intermediate", False)):
            values.append("structured_intermediate")
    return _unique_values(values)


def _pack_boundary_input_source_ids(pack: SceneCoveragePack) -> tuple[str, ...]:
    if pack.pack_id == "import_ai_boundary":
        return (
            "pdf_ocr_import",
            "full_latex_project",
            "ai_content_generation",
            "complex_diagram_generation",
        )
    if pack.pack_id == "exam_education":
        return ("ai_content_generation", "complex_diagram_generation")
    if pack.pack_id == "professional_disclosure":
        return ("ai_content_generation",)
    return ()


def _boundary_gate_ids_for_source(source_id: str) -> tuple[str, ...]:
    matches: list[str] = []
    for gate in list_plugin_manual_gates():
        text = " ".join(
            (
                gate.gate_id,
                gate.label,
                *gate.risk_domain_ids,
                *gate.unsupported_core_inputs,
                *gate.report_fields,
            )
        ).lower()
        if source_id.replace("_", " ") in text or source_id in text:
            matches.append(gate.gate_id)
    if source_id == "pdf_ocr_import":
        matches.append("import_ai_conversion_gate")
    if source_id == "full_latex_project":
        matches.append("import_ai_conversion_gate")
    if source_id == "ai_content_generation":
        matches.extend(("exam_ai_complex_diagram_gate", "import_ai_conversion_gate"))
    if source_id == "complex_diagram_generation":
        matches.extend(("exam_ai_complex_diagram_gate", "import_ai_conversion_gate"))
    return _unique_values(matches)


def _executable_input_source_summary() -> dict[str, dict[str, tuple[str, ...]]]:
    from src.config.scene_presets import SCENE_FACTORIES

    result: dict[str, dict[str, tuple[str, ...]]] = {}
    for scene_id, factory in SCENE_FACTORIES.items():
        scene = factory()
        profile = getattr(scene, "input_source_profile", None)
        presets = tuple(getattr(scene, "delivery_presets", []) or ())
        result[scene_id] = {
            "accepted_formats": _unique_values(
                getattr(profile, "accepted_formats", []) or []
            ),
            "structured_formats": _unique_values(
                getattr(profile, "structured_formats", []) or []
            ),
            "material_schema_ids": resolve_material_schema_ids(
                str(getattr(profile, "material_schema_id", "") or "").strip(),
                list(getattr(profile, "material_schema_ids", []) or []),
            ),
            "render_source_ids": _render_source_ids(presets),
            "target_template_ids": _unique_values(
                getattr(preset, "target_template_id", "") for preset in presets
            ),
        }
    return result


def _all_input_source_ids(
    family_rows: Sequence[SceneInputSourceFamilyRow],
    pack_rows: Sequence[SceneInputSourcePackRow],
    executable_inputs: Mapping[str, dict[str, tuple[str, ...]]],
) -> tuple[str, ...]:
    return _unique_values(
        ("docx", "markdown", "json", "xlsx", "bibtex", "csl_json"),
        *(row.planned_input_formats for row in family_rows),
        *(row.actual_accepted_formats for row in family_rows),
        *(row.structured_formats for row in family_rows),
        *(row.boundary_input_source_ids for row in pack_rows),
        *(
            data.get("accepted_formats", ())
            for data in executable_inputs.values()
        ),
        *(
            data.get("structured_formats", ())
            for data in executable_inputs.values()
        ),
        BOUNDARY_INPUT_SOURCE_IDS,
    )


def _filter_family_rows(
    rows: Sequence[SceneInputSourceFamilyRow],
    *,
    pack_id: str,
    family_id: str,
    source_id: str,
) -> tuple[SceneInputSourceFamilyRow, ...]:
    return tuple(
        row
        for row in rows
        if (not pack_id or pack_id in row.pack_ids)
        and (not family_id or row.family_id == family_id)
        and (
            not source_id
            or source_id in row.planned_input_formats
            or source_id in row.actual_accepted_formats
            or source_id in row.structured_formats
            or source_id in row.high_risk_imports
        )
    )


def _filter_pack_rows(
    rows: Sequence[SceneInputSourcePackRow],
    *,
    pack_id: str,
    family_id: str,
    source_id: str,
) -> tuple[SceneInputSourcePackRow, ...]:
    return tuple(
        row
        for row in rows
        if (not pack_id or row.pack_id == pack_id)
        and (not family_id or family_id in row.planned_family_ids)
        and (
            not source_id
            or source_id in row.input_formats
            or source_id in row.structured_formats
            or source_id in row.boundary_input_source_ids
        )
    )


def _filter_format_rows(
    rows: Sequence[SceneInputSourceFormatRow],
    *,
    pack_id: str,
    family_id: str,
    source_id: str,
) -> tuple[SceneInputSourceFormatRow, ...]:
    return tuple(
        row
        for row in rows
        if (not pack_id or pack_id in row.pack_ids)
        and (not family_id or family_id in row.family_ids)
        and (not source_id or row.source_id == source_id)
    )


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneInputSourceSourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    return tuple(
        SceneInputSourceSourceEvidence(
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
            SCENE_INPUT_SOURCE_SOURCE_MARKERS,
        )
    )


def _source_label(source_id: str) -> str:
    labels = {
        "docx": "Word DOCX",
        "markdown": "Markdown preview/source",
        "json": "Structured JSON",
        "xlsx": "Spreadsheet records",
        "bibtex": "BibTeX references",
        "csl_json": "CSL JSON references",
        "full_latex_project": "Full LaTeX project boundary",
        "pdf_ocr_import": "PDF/OCR import boundary",
        "ai_content_generation": "AI content generation boundary",
        "complex_diagram_generation": "Complex diagram generation boundary",
    }
    return labels.get(source_id, source_id)


def _unique_values(*values: object) -> tuple[str, ...]:
    result: list[str] = []

    def add(value: object) -> None:
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            for item in value:
                add(item)
            return
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)

    for value in values:
        add(value)
    return tuple(result)


__all__ = [
    "SCENE_INPUT_SOURCE_AUDIT_SOURCE_ID",
    "SceneInputSourceAuditReport",
    "SceneInputSourceFamilyRow",
    "SceneInputSourceFormatRow",
    "SceneInputSourceIssue",
    "SceneInputSourcePackRow",
    "SceneInputSourceSourceEvidence",
    "audit_scene_input_source_report",
    "build_scene_input_source_audit_report",
]
