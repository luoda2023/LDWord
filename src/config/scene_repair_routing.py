"""Repair-route registry for scene/workbench issue queues.

The high-level scene matrix needs one auditable mapping from issue categories
and repair target types back to the product surface that can fix them.  This
keeps Workbench issues from becoming a bag of unrelated strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ALLOWED_REPAIR_ROUTE_LAYERS: tuple[str, ...] = (
    "template",
    "scene",
    "material",
    "output",
    "object_preflight",
    "fixed_layout",
    "plugin",
)


@dataclass(frozen=True, slots=True)
class SceneRepairRouteEvidence:
    source_path: str
    markers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SceneRepairRoute:
    route_id: str
    label: str
    owner_layer: str
    repair_target_types: tuple[str, ...]
    issue_categories: tuple[str, ...]
    primary_surface: str
    action_contract: str
    evidence: tuple[SceneRepairRouteEvidence, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class SceneRepairRouteAuditResult:
    missing_required_routes: tuple[str, ...] = ()
    invalid_owner_layers: tuple[tuple[str, str], ...] = ()
    duplicate_repair_target_types: tuple[tuple[str, str, str], ...] = ()
    missing_evidence_files: tuple[tuple[str, str], ...] = ()
    missing_evidence_markers: tuple[tuple[str, str, str], ...] = ()

    @property
    def is_clean(self) -> bool:
        return not (
            self.missing_required_routes
            or self.invalid_owner_layers
            or self.duplicate_repair_target_types
            or self.missing_evidence_files
            or self.missing_evidence_markers
        )


def _evidence(source_path: str, *markers: str) -> SceneRepairRouteEvidence:
    return SceneRepairRouteEvidence(source_path=source_path, markers=tuple(markers))


SCENE_REPAIR_ROUTES: tuple[SceneRepairRoute, ...] = (
    SceneRepairRoute(
        route_id="template_control_contract",
        label="Template/control contract repair",
        owner_layer="template",
        repair_target_types=("template", "control_contract"),
        issue_categories=("control_contract",),
        primary_surface="TemplatePanel / ScenePanel contract summary",
        action_contract="Open the template/control contract owner surface for shared formatting controls.",
        evidence=(
            _evidence(
                "src/ui/adapters/workbench_execution_adapter.py",
                'category="control_contract"',
                'repair_target_type="control_contract"',
            ),
            _evidence(
                "src/config/control_contract_registry.py",
                "CONTROL_CONTRACTS",
                "template_surface",
            ),
            _evidence(
                "src/ui/adapters/workbench_issue_navigation.py",
                "SCENE_TARGET_CARD_MAP",
                '"control_contract": "scn_cleanup"',
            ),
        ),
        notes="Shared style controls repair through the contract owner, not ad hoc scene-only widgets.",
    ),
    SceneRepairRoute(
        route_id="template_field_repair",
        label="Template field-level repair",
        owner_layer="template",
        repair_target_types=(
            "template_field",
            "template_style_field",
            "template_page_field",
            "template_table_field",
            "template_output_field",
        ),
        issue_categories=("template_field", "template_style", "template_table"),
        primary_surface="TemplatePanel field detail panes",
        action_contract=(
            "Open the template management surface for the exact style, page, "
            "table, or output field that caused a quick-formatting repair item."
        ),
        evidence=(
            _evidence(
                "src/shared/ui/paragraph_style_surface.py",
                "StyleControlSurface",
                "ParagraphStyleEditor(",
                "style_field_layout_rows",
            ),
            _evidence(
                "src/ui/panels/template_table_detail.py",
                "class TableCaptionDetail",
                "_TableSnapshot.from_template",
            ),
            _evidence(
                "src/ui/adapters/workbench_issue_navigation.py",
                "TEMPLATE_TARGET_CARD_MAP",
                '"template_field": "tpl_overview"',
            ),
        ),
        notes=(
            "Quick formatting template problems route to the template field owner "
            "instead of becoming generic scene/profile repair items."
        ),
    ),
    SceneRepairRoute(
        route_id="scene_profile",
        label="Scene/profile repair",
        owner_layer="scene",
        repair_target_types=(
            "scene",
            "scene_profile",
            "profile",
            "count_profile",
            "parameter_ownership",
            "sample_fixture",
        ),
        issue_categories=(
            "parameter_ownership",
            "scene_profile",
            "count_profile",
            "sample_fixture",
        ),
        primary_surface="ScenePanel overview/profile summary",
        action_contract="Open scene/profile governance for ownership, count profile, sample coverage, or scene-level policy gaps.",
        evidence=(
            _evidence(
                "src/ui/adapters/workbench_execution_adapter.py",
                'category="parameter_ownership"',
                'repair_target_type="parameter_ownership"',
            ),
            _evidence(
                "src/ui/adapters/workbench_boundary_issues.py",
                'category="sample_fixture"',
                'repair_target_type="sample_fixture"',
            ),
            _evidence(
                "src/config/scene_parameter_ownership.py",
                "scene_parameter_ownership_specs",
                "count_profile_id",
            ),
            _evidence(
                "src/config/scene_sample_fixture_registry.py",
                "SCENE_SAMPLE_FIXTURES",
                "audit_scene_sample_fixtures",
            ),
            _evidence(
                "count_profiles/builtin.json",
                '"profile_id"',
                '"primary_metrics"',
            ),
        ),
        notes="Rules and count profiles stay scene/profile owned until a narrower material/output route exists.",
    ),
    SceneRepairRoute(
        route_id="scene_field_repair",
        label="Scene field-level repair",
        owner_layer="scene",
        repair_target_types=("scene_scope_field", "scene_style_field"),
        issue_categories=("scene_scope", "scene_style"),
        primary_surface="ScenePanel processing scope and section-style details",
        action_contract=(
            "Open the scene scope or section-style detail and focus the exact "
            "processing-range or style override field that caused the execution issue."
        ),
        evidence=(
            _evidence(
                "src/ui/adapters/workbench_issue_navigation.py",
                "SCENE_TARGET_CARD_MAP",
                "scene_scope_field",
                "scene_style_field",
                '"scn_rules"',
            ),
            _evidence(
                "src/ui/panels/scene_panel.py",
                "def focus_navigation_field(self, field_id: str) -> bool:",
                "format_scope.sections.",
                "scene.section_styles.",
            ),
            _evidence(
                "src/ui/adapters/workbench_execution_adapter.py",
                "_infer_scene_field_repair_target",
                "scene_scope_field",
                "scene_style_field",
            ),
        ),
        notes=(
            "Scene field repairs keep task-level scope and style overrides in "
            "ScenePanel while template defaults stay in TemplatePanel."
        ),
    ),
    SceneRepairRoute(
        route_id="material_package",
        label="Material/schema repair",
        owner_layer="material",
        repair_target_types=(
            "material",
            "field",
            "asset",
            "schema",
            "profile_field",
            "profile_asset",
            "profile_schema",
            "question_figure_item",
            "profile_question_figure_item",
        ),
        issue_categories=("material_field", "material_asset", "material_schema", "batch_issue"),
        primary_surface="AssetsPanel / ScenePanel content material schema editor",
        action_contract="Open material fields, assets, schema selection, or profile-scoped material repair.",
        evidence=(
            _evidence(
                "src/ui/adapters/workbench_material_issues.py",
                'repair_target_type="field"',
                'repair_target_type="asset"',
                'repair_target_type="schema"',
                'question_figure_item',
            ),
            _evidence(
                "src/ui/adapters/workbench_execution_adapter.py",
                "def batch_execution_issue_items",
                'payload.get("repair_target_type")',
                'payload.get("repair_target_key")',
            ),
            _evidence(
                "src/ui/bridge.py",
                "request_material_repair_target",
                "material_profile_repair_target_requested",
            ),
            _evidence(
                "src/ui/panels/assets/material_repair_navigation_presenter.py",
                "consume_material_repair_target",
                "consume_material_profile_repair_target",
                "_focus_question_figure_item",
            ),
        ),
        notes="Material repairs are fact-source repairs: fields, assets, schema ids, question-figure rows, or batch profile items.",
    ),
    SceneRepairRoute(
        route_id="output_delivery",
        label="Output/delivery repair",
        owner_layer="output",
        repair_target_types=("output", "output_target", "delivery", "delivery_preset"),
        issue_categories=("output_target", "delivery"),
        primary_surface="ScenePanel scene rules generated-result card",
        action_contract="Open generated-result rules, then focus delivery preset, artifact, output path, or content visibility controls.",
        evidence=(
            _evidence(
                "src/ui/adapters/workbench_execution_adapter.py",
                'category="output_target"',
                'repair_target_type="output_target"',
            ),
            _evidence(
                "src/ui/panels/scene_panel.py",
                "_default_delivery",
                "_delivery_summary",
                "_visibility_rules",
            ),
            _evidence(
                "src/ui/adapters/workbench_issue_navigation.py",
                "SCENE_TARGET_CARD_MAP",
                '"output_target": "scn_rules"',
            ),
        ),
        notes="Output issues repair delivery presets or artifact targets, not template typography.",
    ),
    SceneRepairRoute(
        route_id="object_preflight",
        label="Object-preflight repair",
        owner_layer="object_preflight",
        repair_target_types=("object", "object_preflight"),
        issue_categories=("object_preflight",),
        primary_surface="Workbench object preflight confirmation / ScenePanel compliance",
        action_contract="Open object risk details for comments, revisions, fields, OLE, VBA, and skipped modules.",
        evidence=(
            _evidence(
                "src/ui/adapters/workbench_execution_adapter.py",
                'category="object_preflight"',
                'repair_target_type="object_preflight"',
            ),
            _evidence(
                "src/shared/engine/object_preflight.py",
                "ObjectPreflightPolicy",
                "scan_targets",
            ),
            _evidence(
                "tests/test_workbench_execution_center.py",
                "test_object_preflight_issue_items_expose_risks_for_workbench_queue",
                "repair_target_type == \"object_preflight\"",
            ),
        ),
        notes="Object-preflight repairs explain or confirm risky Word objects before execution continues.",
    ),
    SceneRepairRoute(
        route_id="fixed_layout",
        label="Fixed-layout repair",
        owner_layer="fixed_layout",
        repair_target_types=(
            "fixed_layout",
            "row_height",
            "content_control",
            "content_controls",
            "textbox",
            "textboxes",
        ),
        issue_categories=("fixed_layout", "placeholder_residue"),
        primary_surface="ScenePanel fixed-layout profile / Object preflight details",
        action_contract="Open fixed-layout row-height, content-control, textbox, or placeholder-residue repair.",
        evidence=(
            _evidence(
                "src/config/fixed_layout.py",
                "FixedLayoutRowHeightPolicy",
                "form_batch_documents.table.row_height_pt",
                "content_controls",
                "textboxes",
            ),
            _evidence(
                "src/shared/engine/fixed_layout_tables.py",
                "apply_fixed_layout_row_height_policy",
                "w:trHeight",
            ),
            _evidence(
                "src/config/control_contract_registry.py",
                "fixed_layout.table_row_height",
            ),
        ),
        notes="Fixed-layout repair is separate from generic table formatting and template body style.",
    ),
    SceneRepairRoute(
        route_id="plugin_manual_gate",
        label="Plugin/manual gate repair",
        owner_layer="plugin",
        repair_target_types=("plugin", "plugin_manual_gate", "coverage_boundary"),
        issue_categories=("plugin_boundary", "import_ai_boundary"),
        primary_surface="Workbench plugin/manual gate issue",
        action_contract="Open manual confirmation or plugin handoff for professional/import risks.",
        evidence=(
            _evidence(
                "src/config/plugin_manual_gate.py",
                "PLUGIN_MANUAL_GATES",
                "plugin_manual_gate_payload",
            ),
            _evidence(
                "src/ui/adapters/workbench_boundary_issues.py",
                "plugin_manual_gate_for_pack",
                '"plugin_manual_gate" if gate is not None else "coverage_boundary"',
            ),
            _evidence(
                "tests/test_workbench_execution_center.py",
                "test_coverage_boundary_issue_items_expose_plugin_boundary_for_planned_family",
                'repair_target_type == "plugin_manual_gate"',
            ),
        ),
        notes="Professional, OCR/PDF/LaTeX, AI, and complex diagram risks require confirmation or plugin handoff.",
    ),
)


REQUIRED_SCENE_REPAIR_ROUTE_IDS: tuple[str, ...] = (
    "template_control_contract",
    "template_field_repair",
    "scene_profile",
    "scene_field_repair",
    "material_package",
    "output_delivery",
    "object_preflight",
    "fixed_layout",
    "plugin_manual_gate",
)

SCENE_REPAIR_ROUTE_MAP: dict[str, SceneRepairRoute] = {
    route.route_id: route for route in SCENE_REPAIR_ROUTES
}
REPAIR_ROUTE_BY_TARGET_TYPE: dict[str, SceneRepairRoute] = {
    target_type: route
    for route in SCENE_REPAIR_ROUTES
    for target_type in route.repair_target_types
}
REPAIR_ROUTE_BY_CATEGORY: dict[str, SceneRepairRoute] = {
    category: route
    for route in SCENE_REPAIR_ROUTES
    for category in route.issue_categories
}


def list_scene_repair_routes() -> tuple[SceneRepairRoute, ...]:
    return SCENE_REPAIR_ROUTES


def get_scene_repair_route(route_id: str) -> SceneRepairRoute:
    normalized = str(route_id or "").strip()
    try:
        return SCENE_REPAIR_ROUTE_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown scene repair route: {route_id}") from exc


def repair_route_for_target(
    repair_target_type: str,
    *,
    issue_category: str = "",
) -> SceneRepairRoute | None:
    normalized_target = str(repair_target_type or "").strip()
    if normalized_target in REPAIR_ROUTE_BY_TARGET_TYPE:
        return REPAIR_ROUTE_BY_TARGET_TYPE[normalized_target]
    normalized_category = str(issue_category or "").strip()
    return REPAIR_ROUTE_BY_CATEGORY.get(normalized_category)


def repair_route_for_issue(issue_item) -> SceneRepairRoute | None:
    return repair_route_for_target(
        str(getattr(issue_item, "repair_target_type", "") or ""),
        issue_category=str(getattr(issue_item, "category", "") or ""),
    )


def build_scene_repair_route_summary(route: SceneRepairRoute) -> str:
    targets = "/".join(route.repair_target_types[:5])
    categories = "/".join(route.issue_categories[:4])
    return (
        f"{route.route_id} [{route.owner_layer}] -> {route.primary_surface}; "
        f"targets={targets}; categories={categories}"
    )


def audit_scene_repair_routing(
    *,
    project_root: Path | None = None,
) -> SceneRepairRouteAuditResult:
    root = project_root or Path(__file__).resolve().parents[2]
    route_ids = set(SCENE_REPAIR_ROUTE_MAP)
    missing_required = tuple(
        route_id
        for route_id in REQUIRED_SCENE_REPAIR_ROUTE_IDS
        if route_id not in route_ids
    )
    invalid_owner_layers = tuple(
        sorted(
            (
                (route.route_id, route.owner_layer)
                for route in SCENE_REPAIR_ROUTES
                if route.owner_layer not in ALLOWED_REPAIR_ROUTE_LAYERS
            ),
            key=lambda item: item[0],
        )
    )
    duplicate_target_types = _duplicate_target_types()
    missing_files: list[tuple[str, str]] = []
    missing_markers: list[tuple[str, str, str]] = []
    for route in SCENE_REPAIR_ROUTES:
        for evidence in route.evidence:
            evidence_path = root / evidence.source_path
            if not evidence_path.exists():
                missing_files.append((route.route_id, evidence.source_path))
                continue
            content = evidence_path.read_text(encoding="utf-8", errors="ignore")
            for marker in evidence.markers:
                if marker not in content:
                    missing_markers.append(
                        (route.route_id, evidence.source_path, marker)
                    )
    return SceneRepairRouteAuditResult(
        missing_required_routes=missing_required,
        invalid_owner_layers=invalid_owner_layers,
        duplicate_repair_target_types=duplicate_target_types,
        missing_evidence_files=tuple(sorted(missing_files)),
        missing_evidence_markers=tuple(sorted(missing_markers)),
    )


def _duplicate_target_types() -> tuple[tuple[str, str, str], ...]:
    seen: dict[str, str] = {}
    duplicates: list[tuple[str, str, str]] = []
    for route in SCENE_REPAIR_ROUTES:
        for target_type in route.repair_target_types:
            normalized = str(target_type or "").strip()
            if not normalized:
                continue
            existing = seen.get(normalized)
            if existing and existing != route.route_id:
                duplicates.append((normalized, existing, route.route_id))
            else:
                seen[normalized] = route.route_id
    return tuple(sorted(duplicates))


__all__ = [
    "ALLOWED_REPAIR_ROUTE_LAYERS",
    "REQUIRED_SCENE_REPAIR_ROUTE_IDS",
    "REPAIR_ROUTE_BY_CATEGORY",
    "REPAIR_ROUTE_BY_TARGET_TYPE",
    "SCENE_REPAIR_ROUTE_MAP",
    "SCENE_REPAIR_ROUTES",
    "SceneRepairRoute",
    "SceneRepairRouteAuditResult",
    "SceneRepairRouteEvidence",
    "audit_scene_repair_routing",
    "build_scene_repair_route_summary",
    "get_scene_repair_route",
    "list_scene_repair_routes",
    "repair_route_for_issue",
    "repair_route_for_target",
]
