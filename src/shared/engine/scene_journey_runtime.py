"""Project stable scene contracts into one product execution report.

This module is deliberately runtime-only.  It may consume resolved
configuration and declarative registries, but it must not import fixture,
source-marker, dashboard, or release-gate audits.  The full development audit
entry lives in :mod:`src.config.scene_journey_static_audit`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config.material_schema_registry import resolve_material_schema_ids
from src.config.plugin_manual_gate import plugin_manual_gate_for_pack
from src.config.scene_product_coverage_manifest import (
    coverage_candidate_keys_for_config,
    coverage_packs_for_config,
)
from src.config.scene_family_registry import (
    PLANNED_SCENE_FAMILY_MAP,
    get_planned_scene_family,
)


RUNTIME_EVIDENCE_SCOPE = "runtime_contract"
STATIC_AUDIT_NOT_RUN = "not_run"


@dataclass(frozen=True, slots=True)
class SceneJourneyRuntimePath:
    """One configured runtime contract, not a tested fixture journey."""

    path_id: str
    journey_type: str
    label: str
    contract_id: str = ""
    manual_gate_ids: tuple[str, ...] = ()
    expected_behaviors: tuple[str, ...] = ()
    report_expectations: tuple[str, ...] = ()
    boundary_notes: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "path_id": self.path_id,
            "journey_type": self.journey_type,
            "label": self.label,
            "contract_id": self.contract_id,
            "manual_gate_ids": list(self.manual_gate_ids),
            "expected_behaviors": list(self.expected_behaviors),
            "report_expectations": list(self.report_expectations),
            "boundary_notes": list(self.boundary_notes),
        }


@dataclass(frozen=True, slots=True)
class SceneJourneyRuntimeResult:
    """Report payload for contracts that apply to one resolved execution."""

    status: str
    evidence_scope: str = RUNTIME_EVIDENCE_SCOPE
    static_audit_status: str = STATIC_AUDIT_NOT_RUN
    source_scan_performed: bool = False
    pack_ids: tuple[str, ...] = ()
    family_ids: tuple[str, ...] = ()
    capability_ids: tuple[str, ...] = ()
    contract_ids: tuple[str, ...] = ()
    journey_type_ids: tuple[str, ...] = ()
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
    def contract_count(self) -> int:
        return len(self.contract_ids)

    @property
    def is_applicable(self) -> bool:
        return self.status != "not_applicable"

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "evidence_scope": self.evidence_scope,
            "static_audit_status": self.static_audit_status,
            "source_scan_performed": self.source_scan_performed,
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "capability_ids": list(self.capability_ids),
            "contract_ids": list(self.contract_ids),
            "contract_count": self.contract_count,
            "journey_type_ids": list(self.journey_type_ids),
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
    """Build lightweight evidence from the resolved runtime contract only.

    ``status`` describes projection/gating, not product maturity or static
    audit success.  Source-marker and fixture validation is intentionally not
    performed here.
    """

    packs = _runtime_packs_for_config(config)
    pack_ids = _unique_texts(pack.pack_id for pack in packs)
    family_ids = _family_ids_for_config(config, packs)
    if not pack_ids and not family_ids:
        return SceneJourneyRuntimeResult(status="not_applicable")

    gates = tuple(
        gate
        for pack_id in pack_ids
        if (gate := plugin_manual_gate_for_pack(pack_id)) is not None
    )
    manual_gate_ids = _unique_texts(gate.gate_id for gate in gates)
    expected_behaviors = _runtime_expected_behaviors(config, gates=gates)
    report_expectations = _runtime_report_expectations(config, gates=gates)
    artifact_channel_ids = _runtime_artifact_channel_ids(config, gates=gates)
    repair_target_types = _runtime_repair_target_types(config, gates=gates)
    boundary_notes = _runtime_boundary_notes(packs, family_ids)
    contract_specs = _runtime_contract_specs(packs, family_ids)
    contract_ids = tuple(spec[0] for spec in contract_specs)
    paths = tuple(
        SceneJourneyRuntimePath(
            path_id=contract_id,
            contract_id=contract_id,
            journey_type=(
                "manual_boundary" if manual_gate_ids else "configured_execution"
            ),
            label=label,
            manual_gate_ids=manual_gate_ids,
            expected_behaviors=expected_behaviors,
            report_expectations=report_expectations,
            boundary_notes=notes,
        )
        for contract_id, label, notes in contract_specs[
            : max(0, int(max_path_samples))
        ]
    )
    journey_type_ids = _unique_texts(path.journey_type for path in paths)
    status = "manual_gate_required" if manual_gate_ids else "contract_projected"
    return SceneJourneyRuntimeResult(
        status=status,
        pack_ids=pack_ids,
        family_ids=family_ids,
        capability_ids=family_ids or pack_ids,
        contract_ids=contract_ids,
        journey_type_ids=journey_type_ids,
        manual_gate_ids=manual_gate_ids,
        expected_behaviors=expected_behaviors,
        report_expectations=report_expectations,
        artifact_channel_ids=artifact_channel_ids,
        repair_target_types=repair_target_types,
        boundary_notes=boundary_notes,
        paths=paths,
        path_count=len(contract_specs),
        sampled_path_count=len(paths),
    )


def _family_ids_for_config(config, packs) -> tuple[str, ...]:
    candidate_keys = coverage_candidate_keys_for_config(config)
    pack_family_ids = _unique_texts(
        family_id for pack in packs for family_id in pack.planned_family_ids
    )
    exact_family_ids = _unique_texts(
        key
        for key in candidate_keys
        if key in PLANNED_SCENE_FAMILY_MAP and key in pack_family_ids
    )
    # Prefer the exact resolved family.  Falling back to all pack families is
    # necessary for older top-level scenes that do not expose a family id.
    return exact_family_ids or pack_family_ids


def _runtime_packs_for_config(config):
    """Remove broad top-level fallbacks when an exact family is resolved."""

    packs = coverage_packs_for_config(config)
    candidate_keys = coverage_candidate_keys_for_config(config)
    exact_family_ids = {
        key for key in candidate_keys if key in PLANNED_SCENE_FAMILY_MAP
    }
    if not exact_family_ids:
        return packs
    exact_packs = tuple(
        pack
        for pack in packs
        if exact_family_ids.intersection(pack.planned_family_ids)
    )
    return exact_packs or packs


def _runtime_contract_specs(packs, family_ids) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    specs: list[tuple[str, str, tuple[str, ...]]] = []
    if family_ids:
        for family_id in family_ids:
            family = get_planned_scene_family(family_id)
            if family is None:
                continue
            specs.append(
                (
                    f"family:{family.family_id}",
                    family.name,
                    tuple(family.boundaries),
                )
            )
    if not specs:
        specs.extend(
            (f"pack:{pack.pack_id}", pack.label, (pack.boundary,))
            for pack in packs
        )
    return tuple(specs)


def _runtime_expected_behaviors(config, *, gates) -> tuple[str, ...]:
    values: list[str] = ["apply_configured_modules"]
    compliance = getattr(config, "compliance_profile", None)
    object_preflight = getattr(compliance, "object_preflight", None)
    if bool(getattr(object_preflight, "enabled", False)):
        values.append("preflight_fragile_objects")
    if _runtime_material_schema_ids(config):
        values.append("validate_material_contract")
    if gates:
        values.append("require_manual_confirmation")
    return _unique_texts(values)


def _runtime_report_expectations(config, *, gates) -> tuple[str, ...]:
    values: list[str] = ["pipeline_execution_report", "coverage_boundaries"]
    compliance = getattr(config, "compliance_profile", None)
    object_preflight = getattr(compliance, "object_preflight", None)
    if bool(getattr(object_preflight, "enabled", False)):
        values.append("object_preflight")
    if _runtime_material_schema_ids(config):
        values.append("material_field_consistency")
    if str(getattr(compliance, "count_profile_id", "") or "").strip():
        values.append("count_report")
    if _runtime_delivery_preset_ids(config):
        values.append("delivery_artifact_report")
    input_profile = getattr(config, "input_source_profile", None)
    if bool(getattr(input_profile, "require_material_package", False)):
        values.append("material_package")
    if gates:
        values.append("plugin_manual_gate")
    if any(bool(getattr(gate, "confidence_report_required", False)) for gate in gates):
        values.append("conversion_confidence_report")
    return _unique_texts(values)


def _runtime_artifact_channel_ids(config, *, gates) -> tuple[str, ...]:
    values: list[str] = ["execution_report"]
    values.extend(
        f"delivery:{preset_id}" for preset_id in _runtime_delivery_preset_ids(config)
    )
    input_profile = getattr(config, "input_source_profile", None)
    if bool(getattr(input_profile, "require_material_package", False)):
        values.append("material_package")
    if gates:
        values.append("manual_gate_receipt")
    return _unique_texts(values)


def _runtime_repair_target_types(config, *, gates) -> tuple[str, ...]:
    values: list[str] = []
    compliance = getattr(config, "compliance_profile", None)
    object_preflight = getattr(compliance, "object_preflight", None)
    if bool(getattr(object_preflight, "enabled", False)):
        values.append("object_preflight")
    if _runtime_material_schema_ids(config):
        values.append("material_repair")
    if str(getattr(compliance, "count_profile_id", "") or "").strip():
        values.append("count_profile")
    if _runtime_delivery_preset_ids(config):
        values.append("delivery_preset")
    if gates:
        values.append("plugin_manual_gate")
        values.append("boundary_confirmation")
    return _unique_texts(values)


def _runtime_boundary_notes(packs, family_ids) -> tuple[str, ...]:
    return _unique_texts(
        (
            *(pack.boundary for pack in packs),
            *(
                boundary
                for family_id in family_ids
                if (family := get_planned_scene_family(family_id)) is not None
                for boundary in family.boundaries
            ),
        )
    )


def _runtime_material_schema_ids(config) -> tuple[str, ...]:
    input_profile = getattr(config, "input_source_profile", None)
    return resolve_material_schema_ids(
        str(getattr(input_profile, "material_schema_id", "") or ""),
        list(getattr(input_profile, "material_schema_ids", []) or []),
    )


def _runtime_delivery_preset_ids(config) -> tuple[str, ...]:
    return _unique_texts(
        getattr(preset, "preset_id", "")
        for preset in list(getattr(config, "delivery_presets", []) or [])
    )


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
    "RUNTIME_EVIDENCE_SCOPE",
    "STATIC_AUDIT_NOT_RUN",
    "SceneJourneyRuntimePath",
    "SceneJourneyRuntimeResult",
    "build_scene_journey_runtime_evidence",
]
