"""High-level scene pack slot audit.

N2.133 checks whether every high-frequency coverage pack has explicit evidence
for the slots needed to avoid feature drift: request aliases, profile/family,
material schema, count profile, delivery, Word risks, UI controls, rule source,
report/artifact evidence, repair routing, and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.control_contract_registry import audit_control_contract_registry
from src.config.plugin_manual_gate import plugin_manual_gate_for_pack
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    get_scene_coverage_pack,
    list_scene_coverage_packs,
)
from src.config.scene_family_registry import (
    PLANNED_SCENE_FAMILY_MAP,
    PlannedSceneFamily,
)
from src.config.scene_natural_request_router import (
    audit_natural_request_router,
    routes_for_coverage_pack,
)
from src.config.scene_repair_routing import (
    SCENE_REPAIR_ROUTE_MAP,
    audit_scene_repair_routing,
)
from src.config.scene_rule_source_governance import (
    REQUIRED_RULE_SOURCE_PACK_IDS,
    scene_rule_sources_for_pack,
)

SLOT_STATUS_OK = "ok"
SLOT_STATUS_BOUNDARY = "boundary"
SLOT_STATUS_NOT_APPLICABLE = "not_applicable"
SLOT_STATUS_GAP = "gap"
SATISFIED_SLOT_STATUSES: tuple[str, ...] = (
    SLOT_STATUS_OK,
    SLOT_STATUS_BOUNDARY,
    SLOT_STATUS_NOT_APPLICABLE,
)


@dataclass(frozen=True, slots=True)
class ScenePackSlotDefinition:
    slot_id: str
    label: str
    question: str


@dataclass(frozen=True, slots=True)
class ScenePackSlotEvidence:
    pack_id: str
    slot_id: str
    status: str
    evidence_items: tuple[str, ...] = ()
    detail: str = ""
    source_refs: tuple[str, ...] = ()

    @property
    def is_satisfied(self) -> bool:
        return self.status in SATISFIED_SLOT_STATUSES


@dataclass(frozen=True, slots=True)
class ScenePackSlotAuditResult:
    pack_id: str
    slots: tuple[ScenePackSlotEvidence, ...]

    @property
    def missing_slot_ids(self) -> tuple[str, ...]:
        return tuple(
            slot.slot_id for slot in self.slots if slot.status == SLOT_STATUS_GAP
        )

    @property
    def boundary_slot_ids(self) -> tuple[str, ...]:
        return tuple(
            slot.slot_id for slot in self.slots if slot.status == SLOT_STATUS_BOUNDARY
        )

    @property
    def not_applicable_slot_ids(self) -> tuple[str, ...]:
        return tuple(
            slot.slot_id
            for slot in self.slots
            if slot.status == SLOT_STATUS_NOT_APPLICABLE
        )

    @property
    def is_clean(self) -> bool:
        return not self.missing_slot_ids

    def slot(self, slot_id: str) -> ScenePackSlotEvidence:
        normalized = str(slot_id or "").strip()
        for item in self.slots:
            if item.slot_id == normalized:
                return item
        raise KeyError(f"Unknown slot '{slot_id}' for pack '{self.pack_id}'")


SCENE_PACK_SLOT_DEFINITIONS: tuple[ScenePackSlotDefinition, ...] = (
    ScenePackSlotDefinition(
        "request_alias",
        "Request alias",
        "How does a user naturally ask for this pack, and does the router know it?",
    ),
    ScenePackSlotDefinition(
        "profile_family",
        "Profile and family",
        "Which executable scene, planned family, profile, or boundary owns the pack?",
    ),
    ScenePackSlotDefinition(
        "material_schema",
        "Material schema",
        "Which structured fields, assets, and attachment schemas can drive it?",
    ),
    ScenePackSlotDefinition(
        "count_profile",
        "Count profile",
        "Which CountProfile or inventory profile applies?",
    ),
    ScenePackSlotDefinition(
        "delivery_preset",
        "Delivery preset",
        "Which business output versions or artifacts are expected?",
    ),
    ScenePackSlotDefinition(
        "word_risk_surface",
        "Word risk surface",
        "Which Word/OOXML surfaces can be touched or blocked?",
    ),
    ScenePackSlotDefinition(
        "ui_control_contract",
        "UI control contract",
        "Are shared controls governed by the template/scene control contract?",
    ),
    ScenePackSlotDefinition(
        "rule_source",
        "Rule source",
        "Is there a source, version, review, manual, or plugin rule boundary?",
    ),
    ScenePackSlotDefinition(
        "report_issue_artifact",
        "Report, issue, and artifact",
        "Where will results, skipped work, boundaries, or artifacts be explained?",
    ),
    ScenePackSlotDefinition(
        "repair_route",
        "Repair route",
        "Which owner surface can repair the pack's likely issues?",
    ),
    ScenePackSlotDefinition(
        "test_evidence",
        "Test evidence",
        "Which tests anchor this pack and its first-slice evidence?",
    ),
)

SCENE_PACK_SLOT_IDS: tuple[str, ...] = tuple(
    definition.slot_id for definition in SCENE_PACK_SLOT_DEFINITIONS
)


PACK_TEST_EVIDENCE: dict[str, tuple[tuple[str, str], ...]] = {
    "quick_formatting": (
        ("tests/test_scene_coverage_manifest.py", "quick_formatting"),
        ("tests/test_scene_natural_request_router.py", "quick_formatting_general"),
    ),
    "chinese_academic": (
        ("tests/test_scene_family_application.py", "thesis_cn"),
        ("tests/test_scene_rule_source_governance.py", "school_thesis_rule_defaults"),
    ),
    "english_journal": (
        ("tests/test_scene_rule_source_governance.py", "journal_en_default_rules"),
        ("tests/test_scene_family_application.py", "journal_en"),
    ),
    "exam_education": (
        (
            "tests/test_execution_diagnostics_reporting.py",
            "manual_confirmation_required",
        ),
        ("tests/test_scene_family_application.py", "exam_teaching"),
    ),
    "bidding_materials": (
        ("tests/test_scene_coverage_manifest.py", "bidding_materials"),
        (
            "tests/test_scene_rule_source_governance.py",
            "procurement_bidding_rule_defaults",
        ),
    ),
    "official_policy": (
        ("tests/test_scene_natural_request_router.py", "official_policy_documents"),
        ("tests/test_scene_family_application.py", "meeting_policy_documents"),
    ),
    "technical_long_docs": (
        ("tests/test_execution_diagnostics_reporting.py", "technical_long_docs"),
        ("tests/test_scene_family_application.py", "long_document_publishing"),
    ),
    "application_reports": (
        (
            "tests/test_scene_rule_source_governance.py",
            "project_application_rule_defaults",
        ),
        ("tests/test_material_schema_registry.py", "project_application"),
    ),
    "contract_delivery": (
        ("tests/test_material_field_consistency.py", "contract_delivery"),
        ("tests/test_scene_family_application.py", "contract_delivery"),
    ),
    "batch_forms": (
        (
            "tests/test_scene_family_application.py",
            "form_batch_documents",
        ),
        (
            "tests/test_table_format_semantics.py",
            "form_batch_documents.table.row_height_pt",
        ),
    ),
    "professional_disclosure": (
        (
            "tests/test_scene_rule_source_governance.py",
            "professional_disclosure_boundary_rules",
        ),
        (
            "tests/test_scene_boundary_capability_matrix.py",
            "regulated_disclosure_documents",
        ),
    ),
    "import_ai_boundary": (
        ("tests/test_scene_natural_request_router.py", "import_ai_boundary"),
        ("tests/test_scene_boundary_capability_matrix.py", "import_ai_boundary"),
    ),
}


def audit_scene_pack_slots(
    root: str | Path = ".",
) -> tuple[ScenePackSlotAuditResult, ...]:
    root_path = Path(root)
    context = _GlobalSlotContext(root_path)
    return tuple(
        _audit_pack_slots(pack, root_path, context)
        for pack in list_scene_coverage_packs()
    )


def audit_scene_pack_slot_gaps(
    root: str | Path = ".",
) -> tuple[ScenePackSlotEvidence, ...]:
    return tuple(
        slot
        for result in audit_scene_pack_slots(root)
        for slot in result.slots
        if slot.status == SLOT_STATUS_GAP
    )


def scene_pack_slot_result(
    pack_id: str,
    root: str | Path = ".",
) -> ScenePackSlotAuditResult:
    pack = get_scene_coverage_pack(pack_id)
    root_path = Path(root)
    return _audit_pack_slots(pack, root_path, _GlobalSlotContext(root_path))


def scene_pack_slot_payload(
    pack_id: str,
    root: str | Path = ".",
) -> dict[str, object]:
    result = scene_pack_slot_result(pack_id, root)
    return {
        "pack_id": result.pack_id,
        "slot_count": len(result.slots),
        "gap_count": len(result.missing_slot_ids),
        "boundary_slot_ids": list(result.boundary_slot_ids),
        "not_applicable_slot_ids": list(result.not_applicable_slot_ids),
        "slots": [
            {
                "slot_id": slot.slot_id,
                "status": slot.status,
                "evidence_items": list(slot.evidence_items),
                "detail": slot.detail,
                "source_refs": list(slot.source_refs),
            }
            for slot in result.slots
        ],
    }


def build_scene_pack_slot_summary(result: ScenePackSlotAuditResult) -> str:
    status = "clean" if result.is_clean else "gaps=" + ",".join(result.missing_slot_ids)
    boundary = ",".join(result.boundary_slot_ids) or "-"
    not_applicable = ",".join(result.not_applicable_slot_ids) or "-"
    return (
        f"{result.pack_id}: slots={len(result.slots)}; {status}; "
        f"boundary={boundary}; n/a={not_applicable}"
    )


class _GlobalSlotContext:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path
        self.router_issues = audit_natural_request_router()
        self.control_audit = audit_control_contract_registry(project_root=root_path)
        self.repair_audit = audit_scene_repair_routing(project_root=root_path)


def _audit_pack_slots(
    pack: SceneCoveragePack,
    root_path: Path,
    context: _GlobalSlotContext,
) -> ScenePackSlotAuditResult:
    families = _families_for_pack(pack)
    slots = (
        _request_alias_slot(pack, context),
        _profile_family_slot(pack, families),
        _material_schema_slot(pack, families),
        _count_profile_slot(pack, families),
        _delivery_preset_slot(pack, families),
        _word_risk_surface_slot(pack),
        _ui_control_contract_slot(pack, context),
        _rule_source_slot(pack),
        _report_issue_artifact_slot(pack),
        _repair_route_slot(pack, families, context),
        _test_evidence_slot(pack, root_path),
    )
    return ScenePackSlotAuditResult(pack_id=pack.pack_id, slots=slots)


def _request_alias_slot(
    pack: SceneCoveragePack,
    context: _GlobalSlotContext,
) -> ScenePackSlotEvidence:
    routes = routes_for_coverage_pack(pack.pack_id)
    pack_issues = tuple(
        key for key in context.router_issues if key.startswith(f"pack:{pack.pack_id}:")
    )
    if pack.natural_requests and routes and not pack_issues:
        return _slot(
            pack,
            "request_alias",
            SLOT_STATUS_OK,
            evidence_items=(
                f"natural_requests={len(pack.natural_requests)}",
                f"router_routes={len(routes)}",
            ),
            detail="Coverage pack natural requests are represented by natural-request routes.",
            source_refs=("src/config/scene_natural_request_router.py",),
        )
    return _slot(
        pack,
        "request_alias",
        SLOT_STATUS_GAP,
        evidence_items=pack_issues,
        detail="Pack needs natural request aliases and router coverage.",
        source_refs=("src/config/scene_natural_request_router.py",),
    )


def _profile_family_slot(
    pack: SceneCoveragePack,
    families: tuple[PlannedSceneFamily, ...],
) -> ScenePackSlotEvidence:
    if families:
        return _slot(
            pack,
            "profile_family",
            SLOT_STATUS_OK,
            evidence_items=tuple(family.family_id for family in families),
            detail="Planned family ownership is explicit.",
            source_refs=("src/config/scene_family_registry.py",),
        )
    if pack.executable_scene_ids:
        return _slot(
            pack,
            "profile_family",
            SLOT_STATUS_OK,
            evidence_items=pack.executable_scene_ids,
            detail="Executable top-level scenes own this pack without a separate planned family.",
            source_refs=("src/config/scene_presets.py",),
        )
    if pack.plugin_boundary:
        return _slot(
            pack,
            "profile_family",
            SLOT_STATUS_BOUNDARY,
            evidence_items=("plugin_boundary",),
            detail="This pack is intentionally a plugin/manual boundary rather than a core family.",
            source_refs=("src/config/plugin_manual_gate.py",),
        )
    return _slot(
        pack,
        "profile_family",
        SLOT_STATUS_GAP,
        detail="No owner family, scene, or boundary.",
    )


def _material_schema_slot(
    pack: SceneCoveragePack,
    families: tuple[PlannedSceneFamily, ...],
) -> ScenePackSlotEvidence:
    schema_ids = _unique(
        schema_id for family in families for schema_id in family.material_schema_ids
    )
    if schema_ids:
        return _slot(
            pack,
            "material_schema",
            SLOT_STATUS_OK,
            evidence_items=schema_ids,
            detail="MaterialSchema ids are declared by planned families.",
            source_refs=("src/config/material_schema_registry.py",),
        )
    if pack.plugin_boundary and "material_schema" in pack.capability_axis_ids:
        return _slot(
            pack,
            "material_schema",
            SLOT_STATUS_BOUNDARY,
            evidence_items=("plugin/manual source",),
            detail="Structured inputs are expected to arrive through plugin/manual handoff.",
            source_refs=("src/config/plugin_manual_gate.py",),
        )
    if "material_schema" not in pack.capability_axis_ids:
        return _slot(
            pack,
            "material_schema",
            SLOT_STATUS_NOT_APPLICABLE,
            detail="This pack does not assert material-schema ownership.",
        )
    return _slot(
        pack,
        "material_schema",
        SLOT_STATUS_GAP,
        detail="Material schema axis has no schema evidence.",
    )


def _count_profile_slot(
    pack: SceneCoveragePack,
    families: tuple[PlannedSceneFamily, ...],
) -> ScenePackSlotEvidence:
    profile_ids = _unique(
        profile_id for family in families for profile_id in family.count_profiles
    )
    if profile_ids:
        return _slot(
            pack,
            "count_profile",
            SLOT_STATUS_OK,
            evidence_items=profile_ids,
            detail="CountProfile or inventory profile ids are declared.",
            source_refs=("count_profiles/builtin.json",),
        )
    if pack.plugin_boundary and "count_profile" in pack.capability_axis_ids:
        return _slot(
            pack,
            "count_profile",
            SLOT_STATUS_BOUNDARY,
            evidence_items=("plugin/manual count boundary",),
            detail="Core does not claim a local count profile for this boundary pack.",
            source_refs=("src/config/plugin_manual_gate.py",),
        )
    if "count_profile" not in pack.capability_axis_ids:
        return _slot(
            pack,
            "count_profile",
            SLOT_STATUS_NOT_APPLICABLE,
            detail="This pack does not assert count-profile governance.",
        )
    return _slot(
        pack,
        "count_profile",
        SLOT_STATUS_GAP,
        detail="Count profile axis has no profile evidence.",
    )


def _delivery_preset_slot(
    pack: SceneCoveragePack,
    families: tuple[PlannedSceneFamily, ...],
) -> ScenePackSlotEvidence:
    preset_ids = _unique(
        preset_id for family in families for preset_id in family.delivery_presets
    )
    if preset_ids:
        return _slot(
            pack,
            "delivery_preset",
            SLOT_STATUS_OK,
            evidence_items=preset_ids,
            detail="DeliveryPreset ids are declared by planned families.",
            source_refs=("src/config/scene_family_application.py",),
        )
    if pack.executable_scene_ids and "delivery_preset" in pack.capability_axis_ids:
        return _slot(
            pack,
            "delivery_preset",
            SLOT_STATUS_OK,
            evidence_items=pack.executable_scene_ids,
            detail="Executable scenes carry delivery presets in Workbench scene presets.",
            source_refs=("src/config/scene_presets.py",),
        )
    if pack.plugin_boundary:
        return _slot(
            pack,
            "delivery_preset",
            SLOT_STATUS_BOUNDARY,
            evidence_items=("manual/plugin artifact handoff",),
            detail="Delivery is represented as confirmation, confidence, or boundary artifacts.",
            source_refs=("src/config/plugin_manual_gate.py",),
        )
    return _slot(
        pack,
        "delivery_preset",
        SLOT_STATUS_GAP,
        detail="No delivery preset or artifact boundary evidence.",
    )


def _word_risk_surface_slot(pack: SceneCoveragePack) -> ScenePackSlotEvidence:
    if pack.word_risk_surface_ids:
        return _slot(
            pack,
            "word_risk_surface",
            SLOT_STATUS_OK,
            evidence_items=pack.word_risk_surface_ids,
            detail="Word/OOXML risk surfaces are declared by the coverage pack.",
            source_refs=("src/config/scene_coverage_manifest.py",),
        )
    return _slot(
        pack,
        "word_risk_surface",
        SLOT_STATUS_GAP,
        detail="No Word/OOXML risk surface evidence.",
    )


def _ui_control_contract_slot(
    pack: SceneCoveragePack,
    context: _GlobalSlotContext,
) -> ScenePackSlotEvidence:
    if context.control_audit.is_clean:
        return _slot(
            pack,
            "ui_control_contract",
            SLOT_STATUS_OK,
            evidence_items=("control_contract_registry",),
            detail="Global template/scene/material/output/plugin control contract audit is clean.",
            source_refs=("src/config/control_contract_registry.py",),
        )
    return _slot(
        pack,
        "ui_control_contract",
        SLOT_STATUS_GAP,
        detail="Control contract registry has unresolved audit issues.",
        source_refs=("src/config/control_contract_registry.py",),
    )


def _rule_source_slot(pack: SceneCoveragePack) -> ScenePackSlotEvidence:
    sources = scene_rule_sources_for_pack(pack.pack_id)
    if sources:
        return _slot(
            pack,
            "rule_source",
            SLOT_STATUS_OK,
            evidence_items=tuple(source.source_id for source in sources),
            detail="Rule source governance is explicit for this pack.",
            source_refs=("src/config/scene_rule_source_governance.py",),
        )
    gate = plugin_manual_gate_for_pack(pack.pack_id)
    if gate is not None:
        return _slot(
            pack,
            "rule_source",
            SLOT_STATUS_BOUNDARY,
            evidence_items=(gate.gate_id,),
            detail="Rules are represented by a plugin/manual gate rather than trusted local defaults.",
            source_refs=("src/config/plugin_manual_gate.py",),
        )
    if pack.pack_id not in REQUIRED_RULE_SOURCE_PACK_IDS:
        return _slot(
            pack,
            "rule_source",
            SLOT_STATUS_NOT_APPLICABLE,
            detail="No high-risk external rule source is asserted for this pack in N2.132.",
        )
    return _slot(
        pack,
        "rule_source",
        SLOT_STATUS_GAP,
        detail="Required rule source governance is missing.",
    )


def _report_issue_artifact_slot(pack: SceneCoveragePack) -> ScenePackSlotEvidence:
    if pack.implemented_closures:
        return _slot(
            pack,
            "report_issue_artifact",
            SLOT_STATUS_OK,
            evidence_items=pack.implemented_closures[:4],
            detail="Pack has implemented closures that identify report, issue, or artifact evidence.",
            source_refs=(
                "src/config/scene_coverage_manifest.py",
                "src/report_writer.py",
            ),
        )
    return _slot(
        pack,
        "report_issue_artifact",
        SLOT_STATUS_GAP,
        detail="No report/issue/artifact evidence.",
    )


def _repair_route_slot(
    pack: SceneCoveragePack,
    families: tuple[PlannedSceneFamily, ...],
    context: _GlobalSlotContext,
) -> ScenePackSlotEvidence:
    expected_route_ids = _expected_repair_route_ids(pack, families)
    missing = tuple(
        route_id
        for route_id in expected_route_ids
        if route_id not in SCENE_REPAIR_ROUTE_MAP
    )
    if context.repair_audit.is_clean and not missing and expected_route_ids:
        return _slot(
            pack,
            "repair_route",
            SLOT_STATUS_OK,
            evidence_items=expected_route_ids,
            detail="Likely issue types map back to registered repair routes.",
            source_refs=("src/config/scene_repair_routing.py",),
        )
    return _slot(
        pack,
        "repair_route",
        SLOT_STATUS_GAP,
        evidence_items=missing,
        detail="Repair routing is missing for at least one expected owner layer.",
        source_refs=("src/config/scene_repair_routing.py",),
    )


def _test_evidence_slot(
    pack: SceneCoveragePack,
    root_path: Path,
) -> ScenePackSlotEvidence:
    evidence_specs = PACK_TEST_EVIDENCE.get(pack.pack_id, ())
    missing: list[str] = []
    for path_text, marker in evidence_specs:
        path = root_path / path_text
        if not path.exists():
            missing.append(f"{path_text}:missing_file")
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if marker not in content:
            missing.append(f"{path_text}:missing_marker:{marker}")
    if evidence_specs and not missing:
        return _slot(
            pack,
            "test_evidence",
            SLOT_STATUS_OK,
            evidence_items=tuple(f"{path}:{marker}" for path, marker in evidence_specs),
            detail="Pack has static test anchors for first-slice evidence.",
            source_refs=tuple(path for path, _marker in evidence_specs),
        )
    return _slot(
        pack,
        "test_evidence",
        SLOT_STATUS_GAP,
        evidence_items=tuple(missing),
        detail="Pack needs at least one test anchor with a trace marker.",
    )


def _expected_repair_route_ids(
    pack: SceneCoveragePack,
    families: tuple[PlannedSceneFamily, ...],
) -> tuple[str, ...]:
    ids: list[str] = ["scene_profile"]
    family_schema_count = sum(len(family.material_schema_ids) for family in families)
    if "template_baseline" in pack.capability_axis_ids:
        ids.append("template_control_contract")
    if "material_schema" in pack.capability_axis_ids or family_schema_count:
        ids.append("material_package")
    if "delivery_preset" in pack.capability_axis_ids or any(
        family.delivery_presets for family in families
    ):
        ids.append("output_delivery")
    if "object_preflight" in pack.capability_axis_ids:
        ids.append("object_preflight")
    if (
        "fixed_row_height" in pack.word_risk_surface_ids
        or "content_controls" in pack.word_risk_surface_ids
        or "fixed_layout_table" in pack.workflow_archetype_ids
    ):
        ids.append("fixed_layout")
    if pack.plugin_boundary:
        ids.append("plugin_manual_gate")
    return _unique(ids)


def _families_for_pack(pack: SceneCoveragePack) -> tuple[PlannedSceneFamily, ...]:
    families: list[PlannedSceneFamily] = []
    for family_id in pack.planned_family_ids:
        family = PLANNED_SCENE_FAMILY_MAP.get(family_id)
        if family is not None:
            families.append(family)
    return tuple(families)


def _slot(
    pack: SceneCoveragePack,
    slot_id: str,
    status: str,
    *,
    evidence_items: tuple[str, ...] = (),
    detail: str = "",
    source_refs: tuple[str, ...] = (),
) -> ScenePackSlotEvidence:
    return ScenePackSlotEvidence(
        pack_id=pack.pack_id,
        slot_id=slot_id,
        status=status,
        evidence_items=tuple(str(item) for item in evidence_items if str(item or "")),
        detail=detail,
        source_refs=source_refs,
    )


def _unique(values) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "PACK_TEST_EVIDENCE",
    "SATISFIED_SLOT_STATUSES",
    "SCENE_PACK_SLOT_DEFINITIONS",
    "SCENE_PACK_SLOT_IDS",
    "SLOT_STATUS_BOUNDARY",
    "SLOT_STATUS_GAP",
    "SLOT_STATUS_NOT_APPLICABLE",
    "SLOT_STATUS_OK",
    "ScenePackSlotAuditResult",
    "ScenePackSlotDefinition",
    "ScenePackSlotEvidence",
    "audit_scene_pack_slot_gaps",
    "audit_scene_pack_slots",
    "build_scene_pack_slot_summary",
    "scene_pack_slot_payload",
    "scene_pack_slot_result",
]
