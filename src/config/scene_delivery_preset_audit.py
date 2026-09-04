"""Horizontal DeliveryPreset audit for high-frequency scene packs.

N2.167 keeps output delivery from falling back into loose output toggles.  The
audit distinguishes business delivery versions from artifact switches such as
``compare_docx`` and traces family/pack delivery coverage through executable
scene defaults, pipeline output handling, Workbench artifact payloads, and
report evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config.scene import DeliveryPreset, SceneWorkspace
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_packs_for_family,
    list_scene_coverage_packs,
)
from src.config.scene_family_application import (
    apply_planned_scene_family_defaults,
    planned_family_is_plugin_boundary_only,
)
from src.config.scene_family_registry import (
    PlannedSceneFamily,
    list_planned_scene_families,
)
from src.config.scene_source_evidence import scan_scene_source_markers


SCENE_DELIVERY_PRESET_AUDIT_SOURCE_ID = "scene_delivery_preset_audit"

SCENE_DELIVERY_PRESET_SOURCE_MARKERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "scene_model_delivery_preset",
        "src/config/scene.py",
        ("class DeliveryPreset", "default_delivery_preset_id", "OutputConfig"),
    ),
    (
        "scene_family_registry",
        "src/config/scene_family_registry.py",
        ("delivery_presets", "PLANNED_SCENE_FAMILIES"),
    ),
    (
        "scene_family_application",
        "src/config/scene_family_application.py",
        ("_upsert_delivery_presets", "include_structured_intermediate"),
    ),
    (
        "pipeline_delivery_outputs",
        "src/pipeline/runner.py",
        ("_save_delivery_outputs", "delivery_presets"),
    ),
    (
        "workbench_delivery_runtime",
        "src/services/production_runtime/delivery_reporting.py",
        (
            "should_force_delivery_presets",
            "_write_compare_docx_artifacts",
            "write_structured_intermediates",
            "delivery_preset_payload",
        ),
    ),
    (
        "report_writer_delivery_evidence",
        "src/product_report_writer.py",
        ("default_delivery_preset_id", "include_structured_intermediate"),
    ),
)

DELIVERY_ARTIFACT_PSEUDO_IDS: tuple[str, ...] = (
    "compare_docx",
    "report_json",
    "report_markdown",
    "material_manifest",
    "material_package",
    "structured_intermediate",
)

DELIVERY_REPORT_HINTS: tuple[str, ...] = (
    "report",
    "manifest",
    "package",
    "archive",
    "review",
    "summary",
    "compliance",
    "inventory",
    "residue",
    "consistency",
    "declaration",
    "key",
)


@dataclass(frozen=True, slots=True)
class SceneDeliveryPresetIssue:
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
class SceneDeliveryPresetSourceEvidence:
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
class SceneDeliveryPresetFamilyRow:
    family_id: str
    name: str
    priority: str
    status: str
    pack_ids: tuple[str, ...]
    planned_delivery_preset_ids: tuple[str, ...]
    actual_delivery_preset_ids: tuple[str, ...]
    matched_delivery_preset_ids: tuple[str, ...]
    artifact_pseudo_ids: tuple[str, ...]
    missing_delivery_preset_ids: tuple[str, ...]
    default_delivery_preset_id: str
    application_applied: bool
    plugin_boundary_only: bool
    final_docx_preset_count: int
    compare_docx_preset_count: int
    report_only_preset_count: int
    material_manifest_preset_count: int
    material_package_preset_count: int
    structured_intermediate_preset_count: int
    content_visibility_rule_count: int
    output_dir_template_count: int
    target_template_ids: tuple[str, ...]
    report_levels: tuple[str, ...]
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    @property
    def delivery_preset_count(self) -> int:
        return len(self.actual_delivery_preset_ids)

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"

    def to_payload(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "planned_delivery_preset_ids": list(self.planned_delivery_preset_ids),
            "actual_delivery_preset_ids": list(self.actual_delivery_preset_ids),
            "matched_delivery_preset_ids": list(self.matched_delivery_preset_ids),
            "artifact_pseudo_ids": list(self.artifact_pseudo_ids),
            "missing_delivery_preset_ids": list(self.missing_delivery_preset_ids),
            "default_delivery_preset_id": self.default_delivery_preset_id,
            "application_applied": self.application_applied,
            "plugin_boundary_only": self.plugin_boundary_only,
            "final_docx_preset_count": self.final_docx_preset_count,
            "compare_docx_preset_count": self.compare_docx_preset_count,
            "report_only_preset_count": self.report_only_preset_count,
            "material_manifest_preset_count": self.material_manifest_preset_count,
            "material_package_preset_count": self.material_package_preset_count,
            "structured_intermediate_preset_count": (
                self.structured_intermediate_preset_count
            ),
            "content_visibility_rule_count": self.content_visibility_rule_count,
            "output_dir_template_count": self.output_dir_template_count,
            "target_template_ids": list(self.target_template_ids),
            "report_levels": list(self.report_levels),
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneDeliveryPresetPackRow:
    pack_id: str
    label: str
    status: str
    delivery_relevant: bool
    plugin_boundary: bool
    planned_family_ids: tuple[str, ...]
    executable_scene_ids: tuple[str, ...]
    planned_delivery_preset_ids: tuple[str, ...]
    actual_delivery_preset_ids: tuple[str, ...]
    executable_delivery_preset_ids: tuple[str, ...]
    default_delivery_preset_ids: tuple[str, ...]
    final_docx_preset_count: int
    compare_docx_preset_count: int
    report_only_preset_count: int
    material_package_preset_count: int
    structured_intermediate_preset_count: int
    content_visibility_rule_count: int
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "label": self.label,
            "status": self.status,
            "delivery_relevant": self.delivery_relevant,
            "plugin_boundary": self.plugin_boundary,
            "planned_family_ids": list(self.planned_family_ids),
            "executable_scene_ids": list(self.executable_scene_ids),
            "planned_delivery_preset_ids": list(self.planned_delivery_preset_ids),
            "actual_delivery_preset_ids": list(self.actual_delivery_preset_ids),
            "executable_delivery_preset_ids": list(
                self.executable_delivery_preset_ids
            ),
            "default_delivery_preset_ids": list(self.default_delivery_preset_ids),
            "final_docx_preset_count": self.final_docx_preset_count,
            "compare_docx_preset_count": self.compare_docx_preset_count,
            "report_only_preset_count": self.report_only_preset_count,
            "material_package_preset_count": self.material_package_preset_count,
            "structured_intermediate_preset_count": (
                self.structured_intermediate_preset_count
            ),
            "content_visibility_rule_count": self.content_visibility_rule_count,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneDeliveryPresetAuditReport:
    family_rows: tuple[SceneDeliveryPresetFamilyRow, ...]
    pack_rows: tuple[SceneDeliveryPresetPackRow, ...]
    issues: tuple[SceneDeliveryPresetIssue, ...]
    warnings: tuple[SceneDeliveryPresetIssue, ...]
    source_evidence: tuple[SceneDeliveryPresetSourceEvidence, ...]
    pack_filter: str = ""
    family_filter: str = ""
    preset_filter: str = ""
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
    def accounted_family_count(self) -> int:
        return self.ready_family_count + self.boundary_family_count

    @property
    def pack_count(self) -> int:
        return len(self.pack_rows)

    @property
    def delivery_pack_count(self) -> int:
        return sum(1 for row in self.pack_rows if row.delivery_relevant)

    @property
    def ready_delivery_pack_count(self) -> int:
        return sum(
            1
            for row in self.pack_rows
            if row.delivery_relevant and row.status == "ready"
        )

    @property
    def boundary_delivery_pack_count(self) -> int:
        return sum(
            1
            for row in self.pack_rows
            if row.delivery_relevant and row.status == "boundary"
        )

    @property
    def accounted_delivery_pack_count(self) -> int:
        return self.ready_delivery_pack_count + self.boundary_delivery_pack_count

    @property
    def delivery_preset_count(self) -> int:
        return len(
            _unique_values(
                preset_id
                for row in self.family_rows
                for preset_id in row.actual_delivery_preset_ids
            )
        )

    @property
    def final_docx_preset_count(self) -> int:
        return sum(row.final_docx_preset_count for row in self.family_rows)

    @property
    def compare_docx_preset_count(self) -> int:
        return sum(row.compare_docx_preset_count for row in self.family_rows)

    @property
    def report_only_preset_count(self) -> int:
        return sum(row.report_only_preset_count for row in self.family_rows)

    @property
    def material_package_preset_count(self) -> int:
        return sum(row.material_package_preset_count for row in self.family_rows)

    @property
    def structured_intermediate_preset_count(self) -> int:
        return sum(
            row.structured_intermediate_preset_count for row in self.family_rows
        )

    @property
    def content_visibility_rule_count(self) -> int:
        return sum(row.content_visibility_rule_count for row in self.family_rows)

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
            "source_id": SCENE_DELIVERY_PRESET_AUDIT_SOURCE_ID,
            "pack_filter": self.pack_filter,
            "family_filter": self.family_filter,
            "preset_filter": self.preset_filter,
            "counts": {
                "family_count": self.family_count,
                "total_family_count": self.total_family_count,
                "ready_family_count": self.ready_family_count,
                "boundary_family_count": self.boundary_family_count,
                "accounted_family_count": self.accounted_family_count,
                "pack_count": self.pack_count,
                "total_pack_count": self.total_pack_count,
                "delivery_pack_count": self.delivery_pack_count,
                "ready_delivery_pack_count": self.ready_delivery_pack_count,
                "boundary_delivery_pack_count": self.boundary_delivery_pack_count,
                "accounted_delivery_pack_count": (
                    self.accounted_delivery_pack_count
                ),
                "delivery_preset_count": self.delivery_preset_count,
                "final_docx_preset_count": self.final_docx_preset_count,
                "compare_docx_preset_count": self.compare_docx_preset_count,
                "report_only_preset_count": self.report_only_preset_count,
                "material_package_preset_count": self.material_package_preset_count,
                "structured_intermediate_preset_count": (
                    self.structured_intermediate_preset_count
                ),
                "content_visibility_rule_count": self.content_visibility_rule_count,
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "family_rows": [row.to_payload() for row in self.family_rows],
            "pack_rows": [row.to_payload() for row in self.pack_rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_delivery_preset_audit_report(
    *,
    pack_id: str = "",
    family_id: str = "",
    preset_id: str = "",
    project_root: Path | str | None = None,
) -> SceneDeliveryPresetAuditReport:
    normalized_pack = str(pack_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_preset = str(preset_id or "").strip()

    executable_scenes = _executable_scene_delivery_summary()
    all_family_rows = tuple(_family_row(family) for family in list_planned_scene_families())
    all_pack_rows = tuple(
        _pack_row(pack, family_rows=all_family_rows, executable_scenes=executable_scenes)
        for pack in list_scene_coverage_packs()
    )
    family_rows = _filter_family_rows(
        all_family_rows,
        pack_id=normalized_pack,
        family_id=normalized_family,
        preset_id=normalized_preset,
    )
    pack_rows = _filter_pack_rows(
        all_pack_rows,
        pack_id=normalized_pack,
        family_id=normalized_family,
        preset_id=normalized_preset,
    )
    source_evidence = _source_evidence(project_root)
    issues, warnings = audit_scene_delivery_preset_report(
        SceneDeliveryPresetAuditReport(
            family_rows=family_rows,
            pack_rows=pack_rows,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            pack_filter=normalized_pack,
            family_filter=normalized_family,
            preset_filter=normalized_preset,
            total_family_count=len(all_family_rows),
            total_pack_count=len(all_pack_rows),
        )
    )
    return SceneDeliveryPresetAuditReport(
        family_rows=family_rows,
        pack_rows=pack_rows,
        issues=issues,
        warnings=warnings,
        source_evidence=source_evidence,
        pack_filter=normalized_pack,
        family_filter=normalized_family,
        preset_filter=normalized_preset,
        total_family_count=len(all_family_rows),
        total_pack_count=len(all_pack_rows),
    )


def audit_scene_delivery_preset_report(
    report: SceneDeliveryPresetAuditReport,
) -> tuple[tuple[SceneDeliveryPresetIssue, ...], tuple[SceneDeliveryPresetIssue, ...]]:
    issues: list[SceneDeliveryPresetIssue] = []
    warnings: list[SceneDeliveryPresetIssue] = []
    for row in report.family_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneDeliveryPresetIssue(
                    "family",
                    row.family_id,
                    issue_id,
                    f"DeliveryPreset family row has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneDeliveryPresetIssue(
                    "family",
                    row.family_id,
                    warning_id,
                    f"DeliveryPreset family row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for row in report.pack_rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneDeliveryPresetIssue(
                    "pack",
                    row.pack_id,
                    issue_id,
                    f"DeliveryPreset pack row has unresolved issue: {issue_id}.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneDeliveryPresetIssue(
                    "pack",
                    row.pack_id,
                    warning_id,
                    f"DeliveryPreset pack row has warning: {warning_id}.",
                    severity="warning",
                )
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneDeliveryPresetIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    f"Missing source markers: {', '.join(evidence.missing_markers)}",
                )
            )
    return tuple(issues), tuple(warnings)


def _family_row(family: PlannedSceneFamily) -> SceneDeliveryPresetFamilyRow:
    scene = SceneWorkspace(scene_id=family.family_id, category=family.family_id)
    result = apply_planned_scene_family_defaults(scene, family_id=family.family_id)
    plugin_boundary_only = planned_family_is_plugin_boundary_only(family.family_id)
    presets = (
        ()
        if plugin_boundary_only and not result.applied
        else tuple(getattr(scene, "delivery_presets", []) or ())
    )
    preset_ids = _unique_values(
        str(getattr(preset, "preset_id", "") or "").strip() for preset in presets
    )
    planned_ids = family.delivery_presets
    artifact_pseudo_ids = tuple(
        preset_id for preset_id in planned_ids if preset_id in DELIVERY_ARTIFACT_PSEUDO_IDS
    )
    delivery_planned_ids = tuple(
        preset_id for preset_id in planned_ids if preset_id not in artifact_pseudo_ids
    )
    matched_ids = tuple(preset_id for preset_id in delivery_planned_ids if preset_id in preset_ids)
    missing_ids = tuple(
        preset_id for preset_id in delivery_planned_ids if preset_id not in preset_ids
    )
    issue_ids: list[str] = []
    if not planned_ids:
        issue_ids.append("family_without_planned_delivery_presets")
    if not result.applied and not plugin_boundary_only:
        issue_ids.append("family_without_delivery_application_defaults")
    if not plugin_boundary_only:
        for preset_id in missing_ids:
            issue_ids.append(f"missing_delivery_preset.{preset_id}")
    if result.applied and str(getattr(scene, "default_delivery_preset_id", "") or "") not in preset_ids:
        issue_ids.append("default_delivery_preset_not_in_actual_presets")
    if result.applied:
        _extend_delivery_contract_issues(issue_ids, family, presets)

    status = "boundary" if plugin_boundary_only else "ready"
    if issue_ids:
        status = "blocked"

    return SceneDeliveryPresetFamilyRow(
        family_id=family.family_id,
        name=family.name,
        priority=family.priority,
        status=status,
        pack_ids=tuple(pack.pack_id for pack in coverage_packs_for_family(family.family_id)),
        planned_delivery_preset_ids=planned_ids,
        actual_delivery_preset_ids=preset_ids,
        matched_delivery_preset_ids=matched_ids,
        artifact_pseudo_ids=artifact_pseudo_ids,
        missing_delivery_preset_ids=missing_ids,
        default_delivery_preset_id=str(getattr(scene, "default_delivery_preset_id", "") or ""),
        application_applied=bool(result.applied),
        plugin_boundary_only=plugin_boundary_only,
        final_docx_preset_count=sum(_artifact_flag(preset, "final_docx") for preset in presets),
        compare_docx_preset_count=sum(_artifact_flag(preset, "compare_docx") for preset in presets),
        report_only_preset_count=sum(
            1
            for preset in presets
            if not _artifact_flag(preset, "final_docx")
            and (
                _artifact_flag(preset, "report_json")
                or _artifact_flag(preset, "report_markdown")
                or _artifact_flag(preset, "material_manifest")
            )
        ),
        material_manifest_preset_count=sum(_artifact_flag(preset, "material_manifest") for preset in presets),
        material_package_preset_count=sum(_artifact_flag(preset, "material_package") for preset in presets),
        structured_intermediate_preset_count=sum(
            1 for preset in presets if bool(getattr(preset, "include_structured_intermediate", False))
        ),
        content_visibility_rule_count=sum(
            len(getattr(preset, "content_visibility_rules", []) or []) for preset in presets
        ),
        output_dir_template_count=len(
            _unique_values(getattr(preset, "output_dir_template", "") for preset in presets)
        ),
        target_template_ids=_unique_values(
            getattr(preset, "target_template_id", "") for preset in presets
        ),
        report_levels=_unique_values(getattr(preset, "report_level", "") for preset in presets),
        issue_ids=tuple(issue_ids),
        warning_ids=(),
    )


def _pack_row(
    pack: SceneCoveragePack,
    *,
    family_rows: Sequence[SceneDeliveryPresetFamilyRow],
    executable_scenes: Mapping[str, tuple[tuple[str, ...], str]],
) -> SceneDeliveryPresetPackRow:
    rows = tuple(row for row in family_rows if row.family_id in pack.planned_family_ids)
    family_actual_ids = _unique_values(
        preset_id for row in rows for preset_id in row.actual_delivery_preset_ids
    )
    family_planned_ids = _unique_values(
        preset_id for row in rows for preset_id in row.planned_delivery_preset_ids
    )
    executable_ids = _unique_values(
        preset_id
        for scene_id in pack.executable_scene_ids
        for preset_id in executable_scenes.get(scene_id, ((), ""))[0]
    )
    actual_ids = _unique_values((*family_actual_ids, *executable_ids))
    default_ids = _unique_values(
        [
            *(row.default_delivery_preset_id for row in rows),
            *(
                executable_scenes.get(scene_id, ((), ""))[1]
                for scene_id in pack.executable_scene_ids
            ),
        ]
    )
    delivery_relevant = bool(actual_ids or family_planned_ids) or (
        "delivery_preset" in pack.capability_axis_ids
    )
    issue_ids: list[str] = []
    if delivery_relevant and not actual_ids and not pack.plugin_boundary:
        issue_ids.append("pack_delivery_axis_without_presets")
    if any(row.issue_ids for row in rows):
        issue_ids.append("family_delivery_preset_issues")
    status = "not_applicable"
    if delivery_relevant:
        if pack.plugin_boundary and not actual_ids:
            status = "boundary"
        else:
            status = "blocked" if issue_ids else "ready"

    preset_lookup = _presets_for_pack(pack, family_rows=rows)
    return SceneDeliveryPresetPackRow(
        pack_id=pack.pack_id,
        label=pack.label,
        status=status,
        delivery_relevant=delivery_relevant,
        plugin_boundary=pack.plugin_boundary,
        planned_family_ids=pack.planned_family_ids,
        executable_scene_ids=pack.executable_scene_ids,
        planned_delivery_preset_ids=family_planned_ids,
        actual_delivery_preset_ids=actual_ids,
        executable_delivery_preset_ids=executable_ids,
        default_delivery_preset_ids=default_ids,
        final_docx_preset_count=sum(_artifact_flag(preset, "final_docx") for preset in preset_lookup),
        compare_docx_preset_count=sum(_artifact_flag(preset, "compare_docx") for preset in preset_lookup),
        report_only_preset_count=sum(
            1
            for preset in preset_lookup
            if not _artifact_flag(preset, "final_docx")
            and (
                _artifact_flag(preset, "report_json")
                or _artifact_flag(preset, "report_markdown")
                or _artifact_flag(preset, "material_manifest")
            )
        ),
        material_package_preset_count=sum(
            _artifact_flag(preset, "material_package") for preset in preset_lookup
        ),
        structured_intermediate_preset_count=sum(
            1
            for preset in preset_lookup
            if bool(getattr(preset, "include_structured_intermediate", False))
        ),
        content_visibility_rule_count=sum(
            len(getattr(preset, "content_visibility_rules", []) or [])
            for preset in preset_lookup
        ),
        issue_ids=tuple(issue_ids),
        warning_ids=(),
    )


def _extend_delivery_contract_issues(
    issue_ids: list[str],
    family: PlannedSceneFamily,
    presets: Sequence[DeliveryPreset],
) -> None:
    if not presets:
        issue_ids.append("delivery_application_produced_no_presets")
        return
    for preset in presets:
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            issue_ids.append("delivery_preset_without_id")
        if not str(getattr(preset, "label", "") or "").strip():
            issue_ids.append(f"delivery_preset_without_label.{preset_id or 'unknown'}")
        if not str(getattr(preset, "filename_template", "") or "").strip():
            issue_ids.append(f"delivery_preset_without_filename_template.{preset_id}")
        if not str(getattr(preset, "output_dir_template", "") or "").strip():
            issue_ids.append(f"delivery_preset_without_output_dir_template.{preset_id}")
        if not (
            _artifact_flag(preset, "final_docx")
            or _artifact_flag(preset, "report_json")
            or _artifact_flag(preset, "report_markdown")
            or _artifact_flag(preset, "material_manifest")
            or _artifact_flag(preset, "material_package")
        ):
            issue_ids.append(f"delivery_preset_without_artifacts.{preset_id}")

    workflow_ids = set(family.workflow_archetypes) | set(family.capability_domains)
    if {"multi_version_delivery", "content_visibility"} & workflow_ids and not any(
        getattr(preset, "content_visibility_rules", []) for preset in presets
    ):
        issue_ids.append("multi_version_delivery_without_visibility_rules")
    if "review_compare" in workflow_ids and not any(
        _artifact_flag(preset, "compare_docx") for preset in presets
    ):
        issue_ids.append("review_workflow_without_compare_artifact")
    if {
        "attachment_inventory",
        "archive_package",
        "signing_package",
        "delivery_archive",
    } & workflow_ids and not any(
        _artifact_flag(preset, "material_manifest")
        or _artifact_flag(preset, "material_package")
        for preset in presets
    ):
        issue_ids.append("package_workflow_without_manifest_or_package_artifact")
    if {"failure_isolation", "residue_check"} & workflow_ids and not any(
        not _artifact_flag(preset, "final_docx") for preset in presets
    ):
        issue_ids.append("batch_workflow_without_report_only_preset")
    if not _report_evidence_ids(family):
        issue_ids.append("family_delivery_without_report_evidence")


def _filter_family_rows(
    rows: Sequence[SceneDeliveryPresetFamilyRow],
    *,
    pack_id: str,
    family_id: str,
    preset_id: str,
) -> tuple[SceneDeliveryPresetFamilyRow, ...]:
    return tuple(
        row
        for row in rows
        if (not pack_id or pack_id in row.pack_ids)
        and (not family_id or row.family_id == family_id)
        and (
            not preset_id
            or preset_id in row.planned_delivery_preset_ids
            or preset_id in row.actual_delivery_preset_ids
        )
    )


def _filter_pack_rows(
    rows: Sequence[SceneDeliveryPresetPackRow],
    *,
    pack_id: str,
    family_id: str,
    preset_id: str,
) -> tuple[SceneDeliveryPresetPackRow, ...]:
    return tuple(
        row
        for row in rows
        if (not pack_id or row.pack_id == pack_id)
        and (not family_id or family_id in row.planned_family_ids)
        and (
            not preset_id
            or preset_id in row.planned_delivery_preset_ids
            or preset_id in row.actual_delivery_preset_ids
        )
    )


def _executable_scene_delivery_summary() -> dict[str, tuple[tuple[str, ...], str]]:
    from src.config.scene_presets import SCENE_FACTORIES

    result: dict[str, tuple[tuple[str, ...], str]] = {}
    for scene_id, factory in SCENE_FACTORIES.items():
        scene = factory()
        result[scene_id] = (
            _unique_values(
                str(getattr(preset, "preset_id", "") or "").strip()
                for preset in list(getattr(scene, "delivery_presets", []) or [])
            ),
            str(getattr(scene, "default_delivery_preset_id", "") or "").strip(),
        )
    return result


def _presets_for_pack(
    pack: SceneCoveragePack,
    *,
    family_rows: Sequence[SceneDeliveryPresetFamilyRow],
) -> tuple[DeliveryPreset, ...]:
    presets: list[DeliveryPreset] = []
    for row in family_rows:
        scene = SceneWorkspace(scene_id=row.family_id, category=row.family_id)
        result = apply_planned_scene_family_defaults(scene, family_id=row.family_id)
        if result.applied:
            presets.extend(list(getattr(scene, "delivery_presets", []) or []))
    if pack.executable_scene_ids:
        from src.config.scene_presets import SCENE_FACTORIES

        for scene_id in pack.executable_scene_ids:
            factory = SCENE_FACTORIES.get(scene_id)
            if factory is None:
                continue
            scene = factory()
            presets.extend(list(getattr(scene, "delivery_presets", []) or []))
    return tuple(presets)


def _artifact_flag(preset: DeliveryPreset, name: str) -> bool:
    return bool(getattr(getattr(preset, "artifacts", None), name, False))


def _report_evidence_ids(family: PlannedSceneFamily) -> tuple[str, ...]:
    candidates = (
        *family.delivery_presets,
        *family.required_closures,
        family.first_closed_slice,
    )
    result: list[str] = []
    for value in candidates:
        text = str(value or "").lower()
        if any(token in text for token in DELIVERY_REPORT_HINTS):
            result.append(str(value))
    return tuple(result)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneDeliveryPresetSourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    return tuple(
        SceneDeliveryPresetSourceEvidence(
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
            SCENE_DELIVERY_PRESET_SOURCE_MARKERS,
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
    "SCENE_DELIVERY_PRESET_AUDIT_SOURCE_ID",
    "SceneDeliveryPresetAuditReport",
    "SceneDeliveryPresetFamilyRow",
    "SceneDeliveryPresetIssue",
    "SceneDeliveryPresetPackRow",
    "SceneDeliveryPresetSourceEvidence",
    "audit_scene_delivery_preset_report",
    "build_scene_delivery_preset_audit_report",
]
