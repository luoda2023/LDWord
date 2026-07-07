"""Runtime bridge from scene journey fixtures to execution reports.

The scene matrix already knows which high-frequency journeys are success,
degraded, failure, manual-boundary, or handoff paths.  This module projects
that planning evidence onto one runtime config so reports can explain which
journey expectations, repair targets, and artifact channels apply to the run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config.scene_business_capability_matrix_audit import (
    build_scene_business_capability_matrix_audit_report,
)
from src.config.scene_coverage_manifest import (
    coverage_candidate_keys_for_config,
    coverage_packs_for_config,
)
from src.config.scene_family_registry import PLANNED_SCENE_FAMILY_MAP
from src.config.scene_user_journey_fixture_audit import (
    build_scene_user_journey_fixture_audit_report,
)


@dataclass(frozen=True, slots=True)
class SceneJourneyRuntimePath:
    path_id: str
    journey_type: str
    label: str
    request_cell_ids: tuple[str, ...] = ()
    fixture_ids: tuple[str, ...] = ()
    manual_gate_ids: tuple[str, ...] = ()
    expected_behaviors: tuple[str, ...] = ()
    report_expectations: tuple[str, ...] = ()
    boundary_notes: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "path_id": self.path_id,
            "journey_type": self.journey_type,
            "label": self.label,
            "request_cell_ids": list(self.request_cell_ids),
            "fixture_ids": list(self.fixture_ids),
            "manual_gate_ids": list(self.manual_gate_ids),
            "expected_behaviors": list(self.expected_behaviors),
            "report_expectations": list(self.report_expectations),
            "boundary_notes": list(self.boundary_notes),
        }


@dataclass(frozen=True, slots=True)
class SceneJourneyRuntimeResult:
    status: str
    pack_ids: tuple[str, ...] = ()
    family_ids: tuple[str, ...] = ()
    capability_ids: tuple[str, ...] = ()
    journey_type_ids: tuple[str, ...] = ()
    request_cell_ids: tuple[str, ...] = ()
    fixture_ids: tuple[str, ...] = ()
    manual_gate_ids: tuple[str, ...] = ()
    expected_behaviors: tuple[str, ...] = ()
    report_expectations: tuple[str, ...] = ()
    artifact_channel_ids: tuple[str, ...] = ()
    repair_target_types: tuple[str, ...] = ()
    boundary_notes: tuple[str, ...] = ()
    paths: tuple[SceneJourneyRuntimePath, ...] = field(default_factory=tuple)
    path_count: int = 0
    sampled_path_count: int = 0

    @property
    def manual_gate_count(self) -> int:
        return len(self.manual_gate_ids)

    @property
    def is_applicable(self) -> bool:
        return self.status != "not_applicable"

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "capability_ids": list(self.capability_ids),
            "journey_type_ids": list(self.journey_type_ids),
            "request_cell_ids": list(self.request_cell_ids),
            "fixture_ids": list(self.fixture_ids),
            "manual_gate_ids": list(self.manual_gate_ids),
            "manual_gate_count": self.manual_gate_count,
            "expected_behaviors": list(self.expected_behaviors),
            "report_expectations": list(self.report_expectations),
            "artifact_channel_ids": list(self.artifact_channel_ids),
            "repair_target_types": list(self.repair_target_types),
            "boundary_notes": list(self.boundary_notes),
            "path_count": int(self.path_count),
            "sampled_path_count": int(self.sampled_path_count),
            "paths": [path.to_payload() for path in self.paths],
        }


def build_scene_journey_runtime_evidence(
    config,
    *,
    max_path_samples: int = 24,
) -> SceneJourneyRuntimeResult:
    """Build report-ready journey evidence for one runtime config."""

    packs = coverage_packs_for_config(config)
    pack_ids = _unique_texts(pack.pack_id for pack in packs)
    family_ids = _family_ids_for_config(config, packs)
    if not pack_ids and not family_ids:
        return SceneJourneyRuntimeResult(status="not_applicable")

    journey_report = build_scene_user_journey_fixture_audit_report()
    capability_report = build_scene_business_capability_matrix_audit_report()
    path_rows = tuple(
        row
        for row in journey_report.path_rows
        if _intersects(row.pack_ids, pack_ids) or _intersects(row.family_ids, family_ids)
    )
    capability_rows = tuple(
        row
        for row in capability_report.rows
        if _intersects(row.pack_ids, pack_ids) or _intersects(row.family_ids, family_ids)
    )
    if not path_rows and not capability_rows:
        return SceneJourneyRuntimeResult(
            status="not_applicable",
            pack_ids=pack_ids,
            family_ids=family_ids,
        )

    manual_gate_ids = _unique_texts(
        gate_id
        for row in (*path_rows, *capability_rows)
        for gate_id in getattr(row, "manual_gate_ids", ())
    )
    report_expectations = _unique_texts(
        expectation
        for row in (*path_rows, *capability_rows)
        for expectation in getattr(row, "report_expectations", ())
    )
    expected_behaviors = _unique_texts(
        behavior
        for row in (*path_rows, *capability_rows)
        for behavior in getattr(row, "expected_behaviors", ())
    )
    artifact_channel_ids = _unique_texts(
        channel
        for row in capability_rows
        for channel in getattr(row, "artifact_channel_ids", ())
    )
    status = "manual_gate_required" if manual_gate_ids else "ok"
    sampled = tuple(
        _runtime_path(row) for row in path_rows[: max(0, int(max_path_samples))]
    )
    return SceneJourneyRuntimeResult(
        status=status,
        pack_ids=pack_ids,
        family_ids=family_ids,
        capability_ids=_unique_texts(row.capability_id for row in capability_rows),
        journey_type_ids=_ordered_journey_types(row.journey_type for row in path_rows),
        request_cell_ids=_unique_texts(
            cell_id for row in path_rows for cell_id in row.request_cell_ids
        ),
        fixture_ids=_unique_texts(
            fixture_id for row in path_rows for fixture_id in row.fixture_ids
        ),
        manual_gate_ids=manual_gate_ids,
        expected_behaviors=expected_behaviors,
        report_expectations=report_expectations,
        artifact_channel_ids=artifact_channel_ids,
        repair_target_types=_repair_target_types(
            manual_gate_ids=manual_gate_ids,
            report_expectations=report_expectations,
            expected_behaviors=expected_behaviors,
            journey_type_ids=(row.journey_type for row in path_rows),
        ),
        boundary_notes=_unique_texts(
            note
            for row in (*path_rows, *capability_rows)
            for note in (
                getattr(row, "boundary_notes", ())
                or getattr(row, "boundary_note_ids", ())
            )
        ),
        paths=sampled,
        path_count=len(path_rows),
        sampled_path_count=len(sampled),
    )


def _family_ids_for_config(config, packs) -> tuple[str, ...]:
    candidate_keys = coverage_candidate_keys_for_config(config)
    return _unique_texts(
        (
            *(family_id for pack in packs for family_id in pack.planned_family_ids),
            *(key for key in candidate_keys if key in PLANNED_SCENE_FAMILY_MAP),
        )
    )


def _runtime_path(row) -> SceneJourneyRuntimePath:
    return SceneJourneyRuntimePath(
        path_id=str(getattr(row, "path_id", "") or ""),
        journey_type=str(getattr(row, "journey_type", "") or ""),
        label=str(getattr(row, "label", "") or ""),
        request_cell_ids=tuple(getattr(row, "request_cell_ids", ()) or ()),
        fixture_ids=tuple(getattr(row, "fixture_ids", ()) or ()),
        manual_gate_ids=tuple(getattr(row, "manual_gate_ids", ()) or ()),
        expected_behaviors=tuple(getattr(row, "expected_behaviors", ()) or ()),
        report_expectations=tuple(getattr(row, "report_expectations", ()) or ()),
        boundary_notes=tuple(getattr(row, "boundary_notes", ()) or ()),
    )


def _repair_target_types(
    *,
    manual_gate_ids: tuple[str, ...],
    report_expectations: tuple[str, ...],
    expected_behaviors: tuple[str, ...],
    journey_type_ids,
) -> tuple[str, ...]:
    targets: list[str] = []
    lowered_reports = {item.casefold() for item in report_expectations}
    lowered_behaviors = {item.casefold() for item in expected_behaviors}
    lowered_journeys = {str(item or "").casefold() for item in journey_type_ids}

    if manual_gate_ids or "manual_boundary" in lowered_journeys:
        targets.append("plugin_manual_gate")
    if any("object_preflight" in item for item in lowered_reports):
        targets.append("object_preflight")
    if lowered_reports & {
        "material_package",
        "attachment_inventory",
        "missing_items_report",
        "asset_report",
        "product_asset_inventory",
        "budget_attachment_report",
        "signature_asset_report",
        "missing_required_fields_report",
    }:
        targets.append("material_repair")
    if "count_report" in lowered_reports:
        targets.append("count_profile")
    if lowered_reports & {"rule_source_governance", "journal_rule_source_governance"}:
        targets.append("rule_source")
    if lowered_reports & {
        "customer_internal_version_report",
        "official_delivery_status_report",
        "policy_archive",
        "batch_report",
    }:
        targets.append("delivery_preset")
    if lowered_reports & {"conversion_confidence_report", "import_handoff"}:
        targets.append("import_handoff")
    if lowered_reports & {"fixed_layout_row_height", "placeholder_residue_report"}:
        targets.append("fixed_layout_profile")
    if (
        lowered_reports
        & {"coverage_boundaries", "plugin_manual_gate", "professional_source_quality_report"}
    ) or lowered_behaviors & {"block_report", "skip_report"}:
        targets.append("boundary_confirmation")
    return _unique_texts(targets)


def _ordered_journey_types(values) -> tuple[str, ...]:
    order = {
        "success": 0,
        "degraded": 1,
        "failure": 2,
        "manual_boundary": 3,
        "ambiguous_decision": 4,
        "handoff": 5,
        "negative_control": 6,
    }
    return tuple(
        sorted(_unique_texts(values), key=lambda value: order.get(value, 100))
    )


def _intersects(left, right) -> bool:
    return bool(set(left or ()) & set(right or ()))


def _unique_texts(values) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


__all__ = [
    "SceneJourneyRuntimePath",
    "SceneJourneyRuntimeResult",
    "build_scene_journey_runtime_evidence",
]
