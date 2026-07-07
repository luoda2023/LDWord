"""Horizontal MaterialSchema audit for high-frequency scene packs.

N2.166 turns MaterialSchema from a local registry check into a matrix-level
source of truth.  The audit keeps three views together:

* planned families and their schema contracts;
* coverage packs and executable scene schemas that carry those contracts;
* registry rows that may otherwise become orphaned.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config.material_schema_registry import (
    MATERIAL_SCHEMA_MAP,
    MaterialSchema,
    list_material_schemas,
    resolve_material_schema_ids,
)
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_packs_for_family,
    list_scene_coverage_packs,
)
from src.config.scene_family_registry import (
    PLANNED_SCENE_FAMILY_MAP,
    PlannedSceneFamily,
    list_planned_scene_families,
)


SCENE_MATERIAL_SCHEMA_AUDIT_SOURCE_ID = "scene_material_schema_audit"

SCENE_MATERIAL_SCHEMA_SOURCE_MARKERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "material_schema_registry",
        "src/config/material_schema_registry.py",
        ("MATERIAL_SCHEMAS", "MaterialSchema", "build_material_requirements"),
    ),
    (
        "scene_family_registry",
        "src/config/scene_family_registry.py",
        ("PLANNED_SCENE_FAMILIES", "material_schema_ids"),
    ),
    (
        "scene_coverage_manifest",
        "src/config/scene_coverage_manifest.py",
        ("material_schema", "coverage_packs_for_family"),
    ),
    (
        "scene_pack_slot_audit",
        "src/config/scene_pack_slot_audit.py",
        ("_material_schema_slot", "Material schema"),
    ),
    (
        "scene_family_application",
        "src/config/scene_family_application.py",
        ("material_schema_id", "material_schema_ids"),
    ),
    (
        "config_scene_presets",
        "src/config/scene_presets.py",
        ("SCENE_FACTORIES", "material_schema_id"),
    ),
)

MATERIAL_REPORT_EVIDENCE_TOKENS: tuple[str, ...] = (
    "report",
    "manifest",
    "package",
    "inventory",
    "summary",
    "consistency",
    "validation",
    "check",
    "review",
    "declaration",
    "archive",
    "residue",
    "key",
)

NON_SINGLE_BATCH_MODES: tuple[str, ...] = (
    "multi_profile",
    "structured_source",
    "attachment_package",
    "chapter_collection",
)


@dataclass(frozen=True, slots=True)
class SceneMaterialSchemaIssue:
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
class SceneMaterialSchemaSourceEvidence:
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
class SceneMaterialSchemaFamilyRow:
    family_id: str
    name: str
    priority: str
    status: str
    pack_ids: tuple[str, ...]
    material_schema_ids: tuple[str, ...]
    registered_schema_ids: tuple[str, ...]
    missing_schema_ids: tuple[str, ...]
    required_field_keys: tuple[str, ...]
    required_asset_roles: tuple[str, ...]
    asset_role_ids: tuple[str, ...]
    batch_modes: tuple[str, ...]
    boundary_count: int
    delivery_preset_ids: tuple[str, ...]
    capability_domain_ids: tuple[str, ...]
    workflow_archetype_ids: tuple[str, ...]
    report_evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    @property
    def is_material_family(self) -> bool:
        return bool(self.material_schema_ids)

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "material_schema_ids": list(self.material_schema_ids),
            "registered_schema_ids": list(self.registered_schema_ids),
            "missing_schema_ids": list(self.missing_schema_ids),
            "required_field_keys": list(self.required_field_keys),
            "required_asset_roles": list(self.required_asset_roles),
            "asset_role_ids": list(self.asset_role_ids),
            "batch_modes": list(self.batch_modes),
            "boundary_count": self.boundary_count,
            "delivery_preset_ids": list(self.delivery_preset_ids),
            "capability_domain_ids": list(self.capability_domain_ids),
            "workflow_archetype_ids": list(self.workflow_archetype_ids),
            "report_evidence_ids": list(self.report_evidence_ids),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneMaterialSchemaPackRow:
    pack_id: str
    label: str
    status: str
    material_relevant: bool
    planned_family_ids: tuple[str, ...]
    executable_scene_ids: tuple[str, ...]
    material_schema_ids: tuple[str, ...]
    family_schema_ids: tuple[str, ...]
    executable_schema_ids: tuple[str, ...]
    registered_schema_ids: tuple[str, ...]
    missing_schema_ids: tuple[str, ...]
    required_field_count: int
    required_asset_count: int
    batch_modes: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "label": self.label,
            "status": self.status,
            "material_relevant": self.material_relevant,
            "planned_family_ids": list(self.planned_family_ids),
            "executable_scene_ids": list(self.executable_scene_ids),
            "material_schema_ids": list(self.material_schema_ids),
            "family_schema_ids": list(self.family_schema_ids),
            "executable_schema_ids": list(self.executable_schema_ids),
            "registered_schema_ids": list(self.registered_schema_ids),
            "missing_schema_ids": list(self.missing_schema_ids),
            "required_field_count": self.required_field_count,
            "required_asset_count": self.required_asset_count,
            "batch_modes": list(self.batch_modes),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneMaterialSchemaRegistryRow:
    schema_id: str
    label: str
    family: str
    status: str
    field_count: int
    required_field_count: int
    asset_role_count: int
    required_asset_count: int
    batch_mode: str
    boundary_count: int
    referenced_by_family_ids: tuple[str, ...]
    referenced_by_pack_ids: tuple[str, ...]
    referenced_by_scene_ids: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()

    @property
    def is_referenced(self) -> bool:
        return bool(
            self.referenced_by_family_ids
            or self.referenced_by_pack_ids
            or self.referenced_by_scene_ids
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "label": self.label,
            "family": self.family,
            "status": self.status,
            "field_count": self.field_count,
            "required_field_count": self.required_field_count,
            "asset_role_count": self.asset_role_count,
            "required_asset_count": self.required_asset_count,
            "batch_mode": self.batch_mode,
            "boundary_count": self.boundary_count,
            "referenced_by_family_ids": list(self.referenced_by_family_ids),
            "referenced_by_pack_ids": list(self.referenced_by_pack_ids),
            "referenced_by_scene_ids": list(self.referenced_by_scene_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneMaterialSchemaAuditReport:
    family_rows: tuple[SceneMaterialSchemaFamilyRow, ...]
    pack_rows: tuple[SceneMaterialSchemaPackRow, ...]
    schema_rows: tuple[SceneMaterialSchemaRegistryRow, ...]
    issues: tuple[SceneMaterialSchemaIssue, ...]
    warnings: tuple[SceneMaterialSchemaIssue, ...]
    source_evidence: tuple[SceneMaterialSchemaSourceEvidence, ...]
    pack_filter: str = ""
    family_filter: str = ""
    schema_filter: str = ""
    total_family_count: int = 0
    total_pack_count: int = 0
    total_schema_count: int = 0

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def family_count(self) -> int:
        return len(self.family_rows)

    @property
    def material_family_count(self) -> int:
        return sum(1 for row in self.family_rows if row.is_material_family)

    @property
    def ready_material_family_count(self) -> int:
        return sum(
            1
            for row in self.family_rows
            if row.is_material_family and row.status == "ready"
        )

    @property
    def pack_count(self) -> int:
        return len(self.pack_rows)

    @property
    def material_pack_count(self) -> int:
        return sum(1 for row in self.pack_rows if row.material_relevant)

    @property
    def ready_material_pack_count(self) -> int:
        return sum(
            1
            for row in self.pack_rows
            if row.material_relevant and row.status == "ready"
        )

    @property
    def schema_count(self) -> int:
        return len(self.schema_rows)

    @property
    def referenced_schema_count(self) -> int:
        return sum(1 for row in self.schema_rows if row.is_referenced)

    @property
    def registry_only_schema_count(self) -> int:
        return sum(1 for row in self.schema_rows if not row.is_referenced)

    @property
    def required_field_count(self) -> int:
        return len(
            _unique_values(
                key for row in self.family_rows for key in row.required_field_keys
            )
        )

    @property
    def required_asset_count(self) -> int:
        return len(
            _unique_values(
                role for row in self.family_rows for role in row.required_asset_roles
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
        return sum(1 for evidence in self.source_evidence if evidence.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_MATERIAL_SCHEMA_AUDIT_SOURCE_ID,
            "pack_filter": self.pack_filter,
            "family_filter": self.family_filter,
            "schema_filter": self.schema_filter,
            "counts": {
                "family_count": self.family_count,
                "total_family_count": self.total_family_count,
                "material_family_count": self.material_family_count,
                "ready_material_family_count": self.ready_material_family_count,
                "pack_count": self.pack_count,
                "total_pack_count": self.total_pack_count,
                "material_pack_count": self.material_pack_count,
                "ready_material_pack_count": self.ready_material_pack_count,
                "schema_count": self.schema_count,
                "total_schema_count": self.total_schema_count,
                "referenced_schema_count": self.referenced_schema_count,
                "registry_only_schema_count": self.registry_only_schema_count,
                "required_field_count": self.required_field_count,
                "required_asset_count": self.required_asset_count,
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "family_rows": [row.to_payload() for row in self.family_rows],
            "pack_rows": [row.to_payload() for row in self.pack_rows],
            "schema_rows": [row.to_payload() for row in self.schema_rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_material_schema_audit_report(
    *,
    pack_id: str = "",
    family_id: str = "",
    schema_id: str = "",
    project_root: Path | str | None = None,
) -> SceneMaterialSchemaAuditReport:
    normalized_pack = str(pack_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_schema = str(schema_id or "").strip()

    executable_schema_by_scene = _executable_schema_ids_by_scene()
    all_family_rows = tuple(
        _family_row(family) for family in list_planned_scene_families()
    )
    all_pack_rows = tuple(
        _pack_row(pack, executable_schema_by_scene)
        for pack in list_scene_coverage_packs()
    )
    all_schema_rows = tuple(
        _schema_row(
            schema,
            family_rows=all_family_rows,
            pack_rows=all_pack_rows,
            executable_schema_by_scene=executable_schema_by_scene,
        )
        for schema in list_material_schemas()
    )

    family_rows = _filter_family_rows(
        all_family_rows,
        pack_id=normalized_pack,
        family_id=normalized_family,
        schema_id=normalized_schema,
    )
    pack_rows = _filter_pack_rows(
        all_pack_rows,
        pack_id=normalized_pack,
        family_id=normalized_family,
        schema_id=normalized_schema,
    )
    schema_rows = _filter_schema_rows(
        all_schema_rows,
        pack_id=normalized_pack,
        family_id=normalized_family,
        schema_id=normalized_schema,
    )
    source_evidence = _source_evidence(project_root)
    issues, warnings = audit_scene_material_schema_report(
        SceneMaterialSchemaAuditReport(
            family_rows=family_rows,
            pack_rows=pack_rows,
            schema_rows=schema_rows,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            pack_filter=normalized_pack,
            family_filter=normalized_family,
            schema_filter=normalized_schema,
            total_family_count=len(all_family_rows),
            total_pack_count=len(all_pack_rows),
            total_schema_count=len(all_schema_rows),
        )
    )
    return SceneMaterialSchemaAuditReport(
        family_rows=family_rows,
        pack_rows=pack_rows,
        schema_rows=schema_rows,
        issues=issues,
        warnings=warnings,
        source_evidence=source_evidence,
        pack_filter=normalized_pack,
        family_filter=normalized_family,
        schema_filter=normalized_schema,
        total_family_count=len(all_family_rows),
        total_pack_count=len(all_pack_rows),
        total_schema_count=len(all_schema_rows),
    )


def audit_scene_material_schema_report(
    report: SceneMaterialSchemaAuditReport,
) -> tuple[tuple[SceneMaterialSchemaIssue, ...], tuple[SceneMaterialSchemaIssue, ...]]:
    issues: list[SceneMaterialSchemaIssue] = []
    warnings: list[SceneMaterialSchemaIssue] = []

    for row in report.family_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneMaterialSchemaIssue(
                    "family",
                    row.family_id,
                    issue_id,
                    f"MaterialSchema family row has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneMaterialSchemaIssue(
                    "family",
                    row.family_id,
                    warning_id,
                    f"MaterialSchema family row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for row in report.pack_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneMaterialSchemaIssue(
                    "pack",
                    row.pack_id,
                    issue_id,
                    f"MaterialSchema pack row has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneMaterialSchemaIssue(
                    "pack",
                    row.pack_id,
                    warning_id,
                    f"MaterialSchema pack row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for row in report.schema_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneMaterialSchemaIssue(
                    "schema",
                    row.schema_id,
                    issue_id,
                    f"MaterialSchema registry row has unresolved issue: {issue_id}.",
                )
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneMaterialSchemaIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    f"Missing source markers: {', '.join(evidence.missing_markers)}",
                )
            )
    return tuple(issues), tuple(warnings)


def _family_row(family: PlannedSceneFamily) -> SceneMaterialSchemaFamilyRow:
    schemas = _schemas_for_ids(family.material_schema_ids)
    missing_schema_ids = tuple(
        schema_id
        for schema_id in family.material_schema_ids
        if schema_id not in MATERIAL_SCHEMA_MAP
    )
    report_evidence_ids = _report_evidence_ids(family)
    issue_ids: list[str] = []
    if _family_requires_material(family) and not family.material_schema_ids:
        issue_ids.append("family_material_without_schema")
    for schema_id in missing_schema_ids:
        issue_ids.append(f"missing_schema.{schema_id}")
    for schema in schemas:
        if schema.family != family.family_id:
            issue_ids.append(f"schema_family_mismatch.{schema.schema_id}")
        _extend_schema_contract_issues(issue_ids, schema)
    if _family_requires_batch_material(family) and not any(
        schema.batch_mode in NON_SINGLE_BATCH_MODES for schema in schemas
    ):
        issue_ids.append("family_batch_workflow_without_batch_schema")
    if family.material_schema_ids and not report_evidence_ids:
        issue_ids.append("family_material_without_report_evidence")

    status = "not_applicable"
    if family.material_schema_ids:
        status = "blocked" if issue_ids else "ready"
    elif issue_ids:
        status = "blocked"

    return SceneMaterialSchemaFamilyRow(
        family_id=family.family_id,
        name=family.name,
        priority=family.priority,
        status=status,
        pack_ids=tuple(pack.pack_id for pack in coverage_packs_for_family(family.family_id)),
        material_schema_ids=family.material_schema_ids,
        registered_schema_ids=tuple(schema.schema_id for schema in schemas),
        missing_schema_ids=missing_schema_ids,
        required_field_keys=_unique_values(
            key for schema in schemas for key in schema.required_field_keys
        ),
        required_asset_roles=_unique_values(
            role for schema in schemas for role in schema.required_asset_roles
        ),
        asset_role_ids=_unique_values(
            role.role for schema in schemas for role in schema.asset_roles
        ),
        batch_modes=_unique_values(schema.batch_mode for schema in schemas),
        boundary_count=sum(len(schema.boundaries) for schema in schemas),
        delivery_preset_ids=family.delivery_presets,
        capability_domain_ids=family.capability_domains,
        workflow_archetype_ids=family.workflow_archetypes,
        report_evidence_ids=report_evidence_ids,
        issue_ids=tuple(issue_ids),
        warning_ids=(),
    )


def _pack_row(
    pack: SceneCoveragePack,
    executable_schema_by_scene: Mapping[str, tuple[str, ...]],
) -> SceneMaterialSchemaPackRow:
    families = tuple(
        PLANNED_SCENE_FAMILY_MAP[family_id]
        for family_id in pack.planned_family_ids
        if family_id in PLANNED_SCENE_FAMILY_MAP
    )
    family_schema_ids = _unique_values(
        schema_id for family in families for schema_id in family.material_schema_ids
    )
    include_executable_schemas = bool(family_schema_ids) or (
        "material_schema" in pack.capability_axis_ids
    )
    executable_schema_ids = (
        _unique_values(
            schema_id
            for scene_id in pack.executable_scene_ids
            for schema_id in executable_schema_by_scene.get(scene_id, ())
        )
        if include_executable_schemas
        else ()
    )
    material_schema_ids = _unique_values((*family_schema_ids, *executable_schema_ids))
    schemas = _schemas_for_ids(material_schema_ids)
    missing_schema_ids = tuple(
        schema_id for schema_id in material_schema_ids if schema_id not in MATERIAL_SCHEMA_MAP
    )
    material_relevant = bool(material_schema_ids) or (
        "material_schema" in pack.capability_axis_ids
    )
    issue_ids: list[str] = []
    if "material_schema" in pack.capability_axis_ids and not material_schema_ids:
        issue_ids.append("pack_material_axis_without_schema")
    for schema_id in missing_schema_ids:
        issue_ids.append(f"missing_schema.{schema_id}")
    for schema in schemas:
        _extend_schema_contract_issues(issue_ids, schema)
    if "batch_preset" in pack.capability_axis_ids and material_relevant and not any(
        schema.batch_mode in NON_SINGLE_BATCH_MODES for schema in schemas
    ):
        issue_ids.append("pack_batch_axis_without_batch_schema")

    status = "not_applicable"
    if material_relevant:
        status = "blocked" if issue_ids else "ready"

    return SceneMaterialSchemaPackRow(
        pack_id=pack.pack_id,
        label=pack.label,
        status=status,
        material_relevant=material_relevant,
        planned_family_ids=pack.planned_family_ids,
        executable_scene_ids=pack.executable_scene_ids,
        material_schema_ids=material_schema_ids,
        family_schema_ids=family_schema_ids,
        executable_schema_ids=executable_schema_ids,
        registered_schema_ids=tuple(schema.schema_id for schema in schemas),
        missing_schema_ids=missing_schema_ids,
        required_field_count=len(
            _unique_values(key for schema in schemas for key in schema.required_field_keys)
        ),
        required_asset_count=len(
            _unique_values(role for schema in schemas for role in schema.required_asset_roles)
        ),
        batch_modes=_unique_values(schema.batch_mode for schema in schemas),
        issue_ids=tuple(issue_ids),
        warning_ids=(),
    )


def _schema_row(
    schema: MaterialSchema,
    *,
    family_rows: Sequence[SceneMaterialSchemaFamilyRow],
    pack_rows: Sequence[SceneMaterialSchemaPackRow],
    executable_schema_by_scene: Mapping[str, tuple[str, ...]],
) -> SceneMaterialSchemaRegistryRow:
    referenced_by_family_ids = tuple(
        row.family_id for row in family_rows if schema.schema_id in row.material_schema_ids
    )
    referenced_by_pack_ids = tuple(
        row.pack_id for row in pack_rows if schema.schema_id in row.material_schema_ids
    )
    referenced_by_scene_ids = tuple(
        scene_id
        for scene_id, schema_ids in executable_schema_by_scene.items()
        if schema.schema_id in schema_ids
    )
    issue_ids: list[str] = []
    _extend_schema_contract_issues(issue_ids, schema)
    if (
        not referenced_by_family_ids
        and not referenced_by_pack_ids
        and not referenced_by_scene_ids
        and "legacy" not in f"{schema.label} {schema.description}".lower()
    ):
        issue_ids.append("unclaimed_registered_schema")
    status = "blocked" if issue_ids else "ready"
    if status == "ready" and not (
        referenced_by_family_ids or referenced_by_pack_ids or referenced_by_scene_ids
    ):
        status = "registry_only"

    return SceneMaterialSchemaRegistryRow(
        schema_id=schema.schema_id,
        label=schema.label,
        family=schema.family,
        status=status,
        field_count=len(schema.fields),
        required_field_count=len(schema.required_field_keys),
        asset_role_count=len(schema.asset_roles),
        required_asset_count=len(schema.required_asset_roles),
        batch_mode=schema.batch_mode,
        boundary_count=len(schema.boundaries),
        referenced_by_family_ids=referenced_by_family_ids,
        referenced_by_pack_ids=referenced_by_pack_ids,
        referenced_by_scene_ids=referenced_by_scene_ids,
        issue_ids=tuple(issue_ids),
    )


def _filter_family_rows(
    rows: Sequence[SceneMaterialSchemaFamilyRow],
    *,
    pack_id: str,
    family_id: str,
    schema_id: str,
) -> tuple[SceneMaterialSchemaFamilyRow, ...]:
    return tuple(
        row
        for row in rows
        if (not pack_id or pack_id in row.pack_ids)
        and (not family_id or row.family_id == family_id)
        and (not schema_id or schema_id in row.material_schema_ids)
    )


def _filter_pack_rows(
    rows: Sequence[SceneMaterialSchemaPackRow],
    *,
    pack_id: str,
    family_id: str,
    schema_id: str,
) -> tuple[SceneMaterialSchemaPackRow, ...]:
    return tuple(
        row
        for row in rows
        if (not pack_id or row.pack_id == pack_id)
        and (not family_id or family_id in row.planned_family_ids)
        and (not schema_id or schema_id in row.material_schema_ids)
    )


def _filter_schema_rows(
    rows: Sequence[SceneMaterialSchemaRegistryRow],
    *,
    pack_id: str,
    family_id: str,
    schema_id: str,
) -> tuple[SceneMaterialSchemaRegistryRow, ...]:
    return tuple(
        row
        for row in rows
        if (not pack_id or pack_id in row.referenced_by_pack_ids)
        and (not family_id or family_id in row.referenced_by_family_ids)
        and (not schema_id or row.schema_id == schema_id)
    )


def _schemas_for_ids(schema_ids: Sequence[str]) -> tuple[MaterialSchema, ...]:
    return tuple(
        MATERIAL_SCHEMA_MAP[schema_id]
        for schema_id in schema_ids
        if schema_id in MATERIAL_SCHEMA_MAP
    )


def _family_requires_material(family: PlannedSceneFamily) -> bool:
    if family.material_schema_ids:
        return True
    material_tokens = {
        "material_package",
        "structured_input",
        "placeholder_fill",
        "attachment_inventory",
        "field_consistency",
        "terminology_fields",
    }
    return bool(material_tokens & set(family.capability_domains)) or bool(
        material_tokens & set(family.workflow_archetypes)
    )


def _family_requires_batch_material(family: PlannedSceneFamily) -> bool:
    batch_tokens = {
        "batch_generation",
        "failure_isolation",
        "attachment_inventory",
        "chapter_inventory",
        "archive_package",
    }
    return bool(batch_tokens & set(family.capability_domains)) or bool(
        batch_tokens & set(family.workflow_archetypes)
    )


def _report_evidence_ids(family: PlannedSceneFamily) -> tuple[str, ...]:
    candidates = (
        *family.delivery_presets,
        *family.required_closures,
        family.first_closed_slice,
    )
    result: list[str] = []
    for value in candidates:
        text = str(value or "").lower()
        matched = [token for token in MATERIAL_REPORT_EVIDENCE_TOKENS if token in text]
        if matched:
            result.append(str(value))
    return tuple(result)


def _extend_schema_contract_issues(
    issue_ids: list[str],
    schema: MaterialSchema,
) -> None:
    if not schema.fields and not schema.asset_roles:
        issue_ids.append(f"schema_without_fields_or_assets.{schema.schema_id}")
    if not schema.boundaries:
        issue_ids.append(f"schema_without_boundaries.{schema.schema_id}")
    for role in schema.asset_roles:
        if not role.accepted_types:
            issue_ids.append(
                f"asset_role_without_accepted_types.{schema.schema_id}.{role.role}"
            )


def _executable_schema_ids_by_scene() -> dict[str, tuple[str, ...]]:
    from src.config.scene_presets import SCENE_FACTORIES

    result: dict[str, tuple[str, ...]] = {}
    for scene_id, factory in SCENE_FACTORIES.items():
        scene = factory()
        profile = getattr(scene, "input_source_profile", None)
        result[scene_id] = resolve_material_schema_ids(
            str(getattr(profile, "material_schema_id", "") or "").strip(),
            list(getattr(profile, "material_schema_ids", []) or []),
        )
    return result


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneMaterialSchemaSourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    evidence: list[SceneMaterialSchemaSourceEvidence] = []
    for source_id, source_path, markers in SCENE_MATERIAL_SCHEMA_SOURCE_MARKERS:
        path = root / source_path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneMaterialSchemaSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
                status="ready" if path.exists() and not missing else "missing",
            )
        )
    return tuple(evidence)


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "SCENE_MATERIAL_SCHEMA_AUDIT_SOURCE_ID",
    "SceneMaterialSchemaAuditReport",
    "SceneMaterialSchemaFamilyRow",
    "SceneMaterialSchemaIssue",
    "SceneMaterialSchemaPackRow",
    "SceneMaterialSchemaRegistryRow",
    "SceneMaterialSchemaSourceEvidence",
    "audit_scene_material_schema_report",
    "build_scene_material_schema_audit_report",
]
