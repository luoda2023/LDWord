"""Workbench issue navigation registry.

This module owns the pure-data mapping from Workbench repair targets to UI
surfaces.  Widgets and panels should execute the navigation, but they should
not each carry a private copy of target-type-to-card rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.scene import SceneWorkspace
from src.config.style_field_descriptors import (
    canonical_paragraph_style_field_id,
    scene_style_navigation_target_from_field_id,
)
from src.ui.adapters.field_display_names import field_display_context
from src.ui.adapters.workbench_execution_adapter import (
    WorkbenchIssueItem,
    workbench_issue_action_target,
)


@dataclass(frozen=True, slots=True)
class WorkbenchIssueNavigationProjection:
    """Pure navigation projection for a Workbench issue repair target."""

    target_type: str = ""
    target_key: str = ""
    action_kind: str = "feature_card"
    panel_id: str = ""
    card_id: str = ""
    feature_card_id: str = ""

    @property
    def has_panel_target(self) -> bool:
        return bool(self.panel_id)

    @property
    def has_feature_target(self) -> bool:
        return bool(self.feature_card_id)


@dataclass(frozen=True, slots=True)
class WorkbenchIssueNavigationAuditResult:
    """Audit result for route-registry and navigation-registry consistency."""

    missing_route_target_types: tuple[str, ...] = ()
    fallback_route_target_types: tuple[str, ...] = ()
    unexpected_navigation_target_types: tuple[str, ...] = ()
    invalid_panel_targets: tuple[tuple[str, str], ...] = ()
    invalid_card_targets: tuple[tuple[str, str, str], ...] = ()
    invalid_feature_card_targets: tuple[tuple[str, str], ...] = ()
    invalid_scene_field_targets: tuple[tuple[str, str, str], ...] = ()
    invalid_template_field_targets: tuple[tuple[str, str, str], ...] = ()

    @property
    def is_clean(self) -> bool:
        return not (
            self.missing_route_target_types
            or self.fallback_route_target_types
            or self.unexpected_navigation_target_types
            or self.invalid_panel_targets
            or self.invalid_card_targets
            or self.invalid_feature_card_targets
            or self.invalid_scene_field_targets
            or self.invalid_template_field_targets
        )


@dataclass(frozen=True, slots=True)
class WorkbenchSceneFieldFocusProjection:
    """Pure focus projection for scene field repair targets."""

    target_type: str = ""
    target_key: str = ""
    normalized_key: str = ""
    focus_kind: str = ""
    display_label: str = ""
    display_label_with_group: str = ""
    layout_item_id: str = ""
    field_ids: tuple[str, ...] = ()
    control_contract_key: str = ""
    valid: bool = False
    reason: str = ""


@dataclass(frozen=True, slots=True)
class WorkbenchTemplateFieldFocusProjection:
    """Pure focus projection for template field repair targets."""

    target_type: str = ""
    target_key: str = ""
    normalized_key: str = ""
    focus_kind: str = ""
    display_label: str = ""
    display_label_with_group: str = ""
    layout_item_id: str = ""
    field_ids: tuple[str, ...] = ()
    control_contract_key: str = ""
    valid: bool = False
    reason: str = ""


PROFILE_CANDIDATE_TARGET_TYPES: tuple[str, ...] = (
    "profile_question_figure_repair_candidate",
    "profile_question_figure_repair_conflict_selection",
)

PROFILE_MATERIAL_TARGET_TYPES: tuple[str, ...] = (
    "profile_asset",
    "profile_field",
    "profile_schema",
    "profile_question_figure_item",
)

MATERIAL_TARGET_TYPES: tuple[str, ...] = (
    "material",
    "asset",
    "field",
    "question_figure_item",
)

TEMPLATE_TARGET_CARD_MAP: dict[str, str] = {
    "template": "tpl_overview",
    "template_field": "tpl_overview",
    "template_style_field": "tpl_style",
    "template_page_field": "tpl_page",
    "template_table_field": "tpl_table",
    "template_output_field": "tpl_overview",
}

SCENE_TARGET_CARD_MAP: dict[str, str] = {
    "scene": "scn_overview",
    "scene_profile": "scn_overview",
    "profile": "scn_overview",
    "count_profile": "scn_overview",
    "scene_scope_field": "scn_rules",
    "scene_style_field": "scn_rules",
    "schema": "scn_content",
    "material_schema": "scn_content",
    "output": "scn_rules",
    "output_target": "scn_rules",
    "delivery": "scn_rules",
    "delivery_preset": "scn_rules",
    "coverage_boundary": "scn_overview",
    "sample_fixture": "scn_overview",
    "parameter_ownership": "scn_overview",
    "control_contract": "scn_cleanup",
    "object": "scn_cleanup",
    "object_preflight": "scn_cleanup",
    "fixed_layout": "scn_cleanup",
    "row_height": "scn_cleanup",
    "content_control": "scn_cleanup",
    "content_controls": "scn_cleanup",
    "textbox": "scn_cleanup",
    "textboxes": "scn_cleanup",
    "parameter_path": "scn_cleanup",
}

WORKBENCH_FEATURE_TARGET_MAP: dict[str, str] = {
    "plugin": "quick_execute",
    "plugin_manual_gate": "quick_execute",
}

WORKBENCH_NAVIGATION_ALLOWED_EXTRA_TARGET_TYPES: tuple[str, ...] = (
    "material_schema",
    "parameter_path",
    "profile_question_figure_repair_candidate",
    "profile_question_figure_repair_conflict_selection",
    "question_figure_batch_apply_transaction_task_summary",
)

WORKBENCH_SCENE_FIELD_FOCUS_AUDIT_SAMPLES: tuple[tuple[str, str], ...] = (
    ("scene_scope_field", "format_scope.sections.references"),
    ("scene_scope_field", "scene.format_scope.sections.references"),
    ("scene_style_field", "scene.section_styles.references_body.font_cn"),
    ("scene_style_field", "scene.section_styles.*.line_spacing_pt"),
    ("schema", "input_source_profile.material_schema_id"),
)

WORKBENCH_TEMPLATE_FIELD_FOCUS_AUDIT_SAMPLES: tuple[tuple[str, str], ...] = (
    ("template_style_field", "template.styles.body.font_name"),
    ("template_style_field", "body.line_spacing_value"),
    ("template_page_field", "template.page_setup.margin.left_cm"),
    ("template_page_field", "template.page_setup.header_distance_cm"),
)

TEMPLATE_PAGE_FIELD_NORMALIZED_KEYS: dict[str, str] = {
    "paper_size": "template.page_setup.paper_size",
    "orientation": "template.page_setup.orientation",
    "section_break_type": "template.section.section_break_type",
    "top_cm": "template.page_setup.margin.top_cm",
    "bottom_cm": "template.page_setup.margin.bottom_cm",
    "left_cm": "template.page_setup.margin.left_cm",
    "right_cm": "template.page_setup.margin.right_cm",
    "gutter_cm": "template.page_setup.gutter_cm",
    "header_distance_cm": "template.page_setup.header_distance_cm",
    "footer_distance_cm": "template.page_setup.footer_distance_cm",
}

TEMPLATE_PAGE_FIELD_FOCUS_KIND: dict[str, str] = {
    "paper_size": "page_paper",
    "orientation": "page_orientation",
    "section_break_type": "page_section",
    "top_cm": "page_margin",
    "bottom_cm": "page_margin",
    "left_cm": "page_margin",
    "right_cm": "page_margin",
    "gutter_cm": "page_margin",
    "header_distance_cm": "page_header_footer",
    "footer_distance_cm": "page_header_footer",
}


def registered_workbench_issue_navigation_target_types() -> tuple[str, ...]:
    """Return all target types explicitly handled by the navigation registry."""

    targets = {
        *PROFILE_CANDIDATE_TARGET_TYPES,
        *PROFILE_MATERIAL_TARGET_TYPES,
        *MATERIAL_TARGET_TYPES,
        *TEMPLATE_TARGET_CARD_MAP,
        *SCENE_TARGET_CARD_MAP,
        *WORKBENCH_FEATURE_TARGET_MAP,
        "question_figure_batch_apply_transaction_task_summary",
    }
    return tuple(sorted(target for target in targets if target))


def _default_navigation_surface_sets() -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    from src.ui.panel_registry import PANEL_SPECS
    from src.ui.panels.scene_panel import CARD_DEFINITIONS as SCENE_CARD_DEFINITIONS
    from src.ui.panels.template_panel import (
        CARD_DEFINITIONS as TEMPLATE_CARD_DEFINITIONS,
    )
    from src.ui.panels.workbench.scene_presets import (
        CAPABILITY_FEATURE_CARD_DEFINITIONS,
    )

    panel_ids = tuple(sorted(str(spec.id) for spec in PANEL_SPECS))
    scene_card_ids = tuple(sorted(SCENE_CARD_DEFINITIONS))
    template_card_ids = tuple(sorted(TEMPLATE_CARD_DEFINITIONS))
    workbench_feature_card_ids = tuple(
        sorted(
            {
                "quick_execute",
                "config_management",
                *CAPABILITY_FEATURE_CARD_DEFINITIONS,
            }
        )
    )
    return (
        panel_ids,
        scene_card_ids,
        template_card_ids,
        workbench_feature_card_ids,
    )


def _scene_scope_zone_ids() -> tuple[str, ...]:
    workspace = SceneWorkspace()
    return tuple(sorted(str(key) for key in workspace.format_scope.sections))


def workbench_scene_field_focus_projection(
    target_type: str,
    target_key: str,
) -> WorkbenchSceneFieldFocusProjection:
    """Normalize and validate a scene field target before UI focus."""

    normalized_type = str(target_type or "").strip()
    normalized_key = str(target_key or "").strip()
    if not normalized_key:
        return WorkbenchSceneFieldFocusProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            reason="empty_target_key",
        )
    if normalized_type == "scene_scope_field":
        return _workbench_scene_scope_focus_projection(
            normalized_type,
            normalized_key,
        )
    if normalized_type == "scene_style_field":
        return _workbench_scene_style_focus_projection(
            normalized_type,
            normalized_key,
        )
    if normalized_type in {"schema", "material_schema"}:
        return _workbench_scene_content_focus_projection(
            normalized_type,
            normalized_key,
        )
    return WorkbenchSceneFieldFocusProjection(
        target_type=normalized_type,
        target_key=normalized_key,
        reason="unsupported_target_type",
    )


def _workbench_scene_scope_focus_projection(
    target_type: str,
    target_key: str,
) -> WorkbenchSceneFieldFocusProjection:
    target = target_key
    for prefix in (
        "scene.format_scope.sections.",
        "format_scope.sections.",
        "sections.",
        "scope.",
    ):
        if target.startswith(prefix):
            target = target[len(prefix) :].split(".", 1)[0]
            break
    valid_zones = set(_scene_scope_zone_ids())
    if target in valid_zones:
        normalized_key = f"format_scope.sections.{target}"
        return WorkbenchSceneFieldFocusProjection(
            target_type=target_type,
            target_key=target_key,
            normalized_key=normalized_key,
            focus_kind="scope_zone",
            **_focus_display_context_kwargs(normalized_key, target_type),
            valid=True,
        )
    return WorkbenchSceneFieldFocusProjection(
        target_type=target_type,
        target_key=target_key,
        focus_kind="scope_zone",
        reason="unknown_scope_zone",
    )


def _workbench_scene_style_focus_projection(
    target_type: str,
    target_key: str,
) -> WorkbenchSceneFieldFocusProjection:
    for prefix in ("scene.section_styles.", "section_styles."):
        if target_key.startswith(prefix):
            tail = target_key[len(prefix) :]
            variant_key, _, editor_field = tail.partition(".")
            if variant_key == "*":
                return _workbench_scene_style_field_projection(
                    target_type,
                    target_key,
                    variant_key,
                    editor_field,
                    focus_kind="style_wildcard",
                )
            parsed_variant, parsed_editor_field = (
                scene_style_navigation_target_from_field_id(target_key)
            )
            if not parsed_variant:
                return WorkbenchSceneFieldFocusProjection(
                    target_type=target_type,
                    target_key=target_key,
                    focus_kind="style_variant",
                    reason="unknown_style_variant",
                )
            if not parsed_editor_field:
                return _workbench_scene_style_toggle_projection(
                    target_type,
                    target_key,
                    parsed_variant,
                )
            return _workbench_scene_style_field_projection(
                target_type,
                target_key,
                parsed_variant,
                parsed_editor_field,
                focus_kind="style_variant",
            )

    parsed_variant, parsed_editor_field = scene_style_navigation_target_from_field_id(
        target_key
    )
    if parsed_variant:
        if not parsed_editor_field:
            return _workbench_scene_style_toggle_projection(
                target_type,
                target_key,
                parsed_variant,
            )
        return _workbench_scene_style_field_projection(
            target_type,
            target_key,
            parsed_variant,
            parsed_editor_field,
            focus_kind="style_variant",
        )

    if target_key.startswith("section_style."):
        editor_field = target_key[len("section_style.") :]
        canonical = canonical_paragraph_style_field_id(editor_field)
        if canonical:
            normalized_key = f"section_style.{canonical}"
            return WorkbenchSceneFieldFocusProjection(
                target_type=target_type,
                target_key=target_key,
                normalized_key=normalized_key,
                focus_kind="style_editor",
                **_focus_display_context_kwargs(normalized_key, target_type),
                valid=True,
            )
        return WorkbenchSceneFieldFocusProjection(
            target_type=target_type,
            target_key=target_key,
            focus_kind="style_editor",
            reason="unknown_style_field",
        )

    canonical = canonical_paragraph_style_field_id(target_key)
    if canonical:
        normalized_key = f"section_style.{canonical}"
        return WorkbenchSceneFieldFocusProjection(
            target_type=target_type,
            target_key=target_key,
            normalized_key=normalized_key,
            focus_kind="style_editor",
            **_focus_display_context_kwargs(normalized_key, target_type),
            valid=True,
        )
    return WorkbenchSceneFieldFocusProjection(
        target_type=target_type,
        target_key=target_key,
        reason="not_scene_style_field",
    )


def _workbench_scene_style_toggle_projection(
    target_type: str,
    target_key: str,
    variant_key: str,
) -> WorkbenchSceneFieldFocusProjection:
    normalized_key = f"scene.section_styles.{variant_key}"
    return WorkbenchSceneFieldFocusProjection(
        target_type=target_type,
        target_key=target_key,
        normalized_key=normalized_key,
        focus_kind="style_variant_toggle",
        **_focus_display_context_kwargs(normalized_key, target_type),
        valid=True,
    )


def _workbench_scene_style_field_projection(
    target_type: str,
    target_key: str,
    variant_key: str,
    editor_field: str,
    *,
    focus_kind: str,
) -> WorkbenchSceneFieldFocusProjection:
    if not editor_field:
        return WorkbenchSceneFieldFocusProjection(
            target_type=target_type,
            target_key=target_key,
            focus_kind=focus_kind,
            reason="missing_style_field",
        )
    canonical = canonical_paragraph_style_field_id(editor_field)
    if not canonical:
        return WorkbenchSceneFieldFocusProjection(
            target_type=target_type,
            target_key=target_key,
            focus_kind=focus_kind,
            reason="unknown_style_field",
        )
    normalized_key = f"scene.section_styles.{variant_key}.{canonical}"
    return WorkbenchSceneFieldFocusProjection(
        target_type=target_type,
        target_key=target_key,
        normalized_key=normalized_key,
        focus_kind=focus_kind,
        **_focus_display_context_kwargs(normalized_key, target_type),
        valid=True,
    )


def _workbench_scene_content_focus_projection(
    target_type: str,
    target_key: str,
) -> WorkbenchSceneFieldFocusProjection:
    target = target_key
    aliases = {
        "schema": "input_source_profile.material_schema_id",
        "schema_id": "input_source_profile.material_schema_id",
        "material_schema": "input_source_profile.material_schema_id",
        "material_schema_id": "input_source_profile.material_schema_id",
        "input_source_profile.material_schema_id": (
            "input_source_profile.material_schema_id"
        ),
        "material_schema_ids": "input_source_profile.material_schema_ids",
        "input_source_profile.material_schema_ids": (
            "input_source_profile.material_schema_ids"
        ),
        "required_material_fields": (
            "input_source_profile.required_material_fields"
        ),
        "input_source_profile.required_material_fields": (
            "input_source_profile.required_material_fields"
        ),
        "required_image_roles": "input_source_profile.required_image_roles",
        "input_source_profile.required_image_roles": (
            "input_source_profile.required_image_roles"
        ),
    }
    normalized = aliases.get(target)
    if normalized:
        return WorkbenchSceneFieldFocusProjection(
            target_type=target_type,
            target_key=target_key,
            normalized_key=normalized,
            focus_kind="material_schema_contract",
            **_focus_display_context_kwargs(normalized, target_type),
            valid=True,
        )
    return WorkbenchSceneFieldFocusProjection(
        target_type=target_type,
        target_key=target_key,
        normalized_key=target,
        focus_kind="material_schema_id",
        **_focus_display_context_kwargs(target, target_type),
        valid=True,
    )


def audit_workbench_scene_field_focus_targets(
    targets: tuple[tuple[str, str], ...] | None = None,
) -> tuple[tuple[str, str, str], ...]:
    """Return scene field targets that cannot reach a known ScenePanel control."""

    checked_targets = WORKBENCH_SCENE_FIELD_FOCUS_AUDIT_SAMPLES
    if targets is not None:
        checked_targets = targets
    invalid: list[tuple[str, str, str]] = []
    for target_type, target_key in tuple(checked_targets or ()):
        projection = workbench_scene_field_focus_projection(target_type, target_key)
        if not projection.valid:
            invalid.append((target_type, target_key, projection.reason))
    return tuple(sorted(invalid))


def workbench_template_field_focus_projection(
    target_type: str,
    target_key: str,
) -> WorkbenchTemplateFieldFocusProjection:
    """Normalize and validate a template field target before UI focus."""

    normalized_type = str(target_type or "").strip()
    normalized_key = str(target_key or "").strip()
    if not normalized_key:
        return WorkbenchTemplateFieldFocusProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            reason="empty_target_key",
        )
    if normalized_type == "template_style_field":
        canonical = canonical_paragraph_style_field_id(normalized_key)
        if canonical:
            normalized_template_key = f"template.styles.body.{canonical}"
            return WorkbenchTemplateFieldFocusProjection(
                target_type=normalized_type,
                target_key=normalized_key,
                normalized_key=normalized_template_key,
                focus_kind="style_editor",
                **_focus_display_context_kwargs(
                    normalized_template_key,
                    normalized_type,
                ),
                valid=True,
            )
        return WorkbenchTemplateFieldFocusProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            focus_kind="style_editor",
            reason="unknown_style_field",
        )
    if normalized_type == "template_page_field":
        page_field = _canonical_template_page_field_id(normalized_key)
        if page_field:
            normalized_page_key = TEMPLATE_PAGE_FIELD_NORMALIZED_KEYS[page_field]
            return WorkbenchTemplateFieldFocusProjection(
                target_type=normalized_type,
                target_key=normalized_key,
                normalized_key=normalized_page_key,
                focus_kind=TEMPLATE_PAGE_FIELD_FOCUS_KIND[page_field],
                **_focus_display_context_kwargs(
                    normalized_page_key,
                    normalized_type,
                ),
                valid=True,
            )
        return WorkbenchTemplateFieldFocusProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            focus_kind="page_setup",
            reason="unknown_page_field",
        )
    return WorkbenchTemplateFieldFocusProjection(
        target_type=normalized_type,
        target_key=normalized_key,
        reason="unsupported_target_type",
    )


def _canonical_template_page_field_id(target_key: str) -> str:
    target = str(target_key or "").strip()
    if target.startswith("template."):
        target = target[len("template.") :]
    aliases = {
        "paper": "paper_size",
        "paper_size": "paper_size",
        "page.paper_size": "paper_size",
        "page_setup.paper_size": "paper_size",
        "orientation": "orientation",
        "page.orientation": "orientation",
        "page_setup.orientation": "orientation",
        "section_break_type": "section_break_type",
        "section.section_break_type": "section_break_type",
        "page_setup.section_break_type": "section_break_type",
        "top_cm": "top_cm",
        "top_margin_cm": "top_cm",
        "margin.top_cm": "top_cm",
        "page.margin.top_cm": "top_cm",
        "page_setup.margin.top_cm": "top_cm",
        "bottom_cm": "bottom_cm",
        "bottom_margin_cm": "bottom_cm",
        "margin.bottom_cm": "bottom_cm",
        "page.margin.bottom_cm": "bottom_cm",
        "page_setup.margin.bottom_cm": "bottom_cm",
        "left_cm": "left_cm",
        "left_margin_cm": "left_cm",
        "margin.left_cm": "left_cm",
        "page.margin.left_cm": "left_cm",
        "page_setup.margin.left_cm": "left_cm",
        "right_cm": "right_cm",
        "right_margin_cm": "right_cm",
        "margin.right_cm": "right_cm",
        "page.margin.right_cm": "right_cm",
        "page_setup.margin.right_cm": "right_cm",
        "gutter_cm": "gutter_cm",
        "page.gutter_cm": "gutter_cm",
        "page_setup.gutter_cm": "gutter_cm",
        "header_distance_cm": "header_distance_cm",
        "page.header_distance_cm": "header_distance_cm",
        "page_setup.header_distance_cm": "header_distance_cm",
        "footer_distance_cm": "footer_distance_cm",
        "page.footer_distance_cm": "footer_distance_cm",
        "page_setup.footer_distance_cm": "footer_distance_cm",
    }
    return aliases.get(target, "")


def _focus_display_context_kwargs(target_key: str, target_type: str) -> dict:
    context = field_display_context(target_key, target_type=target_type)
    return {
        "display_label": context.label,
        "display_label_with_group": context.label_with_group(),
        "layout_item_id": context.layout_item_id,
        "field_ids": context.field_ids,
        "control_contract_key": context.control_contract_key,
    }


def audit_workbench_template_field_focus_targets(
    targets: tuple[tuple[str, str], ...] | None = None,
) -> tuple[tuple[str, str, str], ...]:
    """Return template field targets that cannot reach a known TemplatePanel control."""

    checked_targets = WORKBENCH_TEMPLATE_FIELD_FOCUS_AUDIT_SAMPLES
    if targets is not None:
        checked_targets = targets
    invalid: list[tuple[str, str, str]] = []
    for target_type, target_key in tuple(checked_targets or ()):
        projection = workbench_template_field_focus_projection(
            target_type,
            target_key,
        )
        if not projection.valid:
            invalid.append((target_type, target_key, projection.reason))
    return tuple(sorted(invalid))


def audit_workbench_issue_navigation_routes(
    routes=None,
    *,
    valid_panel_ids: tuple[str, ...] | None = None,
    valid_scene_card_ids: tuple[str, ...] | None = None,
    valid_template_card_ids: tuple[str, ...] | None = None,
    valid_workbench_feature_card_ids: tuple[str, ...] | None = None,
    scene_field_targets: tuple[tuple[str, str], ...] | None = None,
    template_field_targets: tuple[tuple[str, str], ...] | None = None,
) -> WorkbenchIssueNavigationAuditResult:
    """Audit that scene repair route targets have explicit navigation entries."""

    if routes is None:
        from src.config.scene_repair_routing import list_scene_repair_routes

        routes = list_scene_repair_routes()
    if (
        valid_panel_ids is None
        or valid_scene_card_ids is None
        or valid_template_card_ids is None
        or valid_workbench_feature_card_ids is None
    ):
        (
            default_panel_ids,
            default_scene_card_ids,
            default_template_card_ids,
            default_feature_card_ids,
        ) = _default_navigation_surface_sets()
        valid_panel_ids = valid_panel_ids or default_panel_ids
        valid_scene_card_ids = valid_scene_card_ids or default_scene_card_ids
        valid_template_card_ids = (
            valid_template_card_ids or default_template_card_ids
        )
        valid_workbench_feature_card_ids = (
            valid_workbench_feature_card_ids or default_feature_card_ids
        )
    route_targets = tuple(
        sorted(
            {
                str(target or "").strip()
                for route in tuple(routes or ())
                for target in tuple(getattr(route, "repair_target_types", ()) or ())
                if str(target or "").strip()
            }
        )
    )
    registered_targets = set(registered_workbench_issue_navigation_target_types())
    missing = tuple(
        target for target in route_targets if target not in registered_targets
    )
    fallback = tuple(
        target
        for target in route_targets
        if workbench_issue_navigation_for_target(target).feature_card_id
        == "content_fill"
    )
    allowed_extra = set(WORKBENCH_NAVIGATION_ALLOWED_EXTRA_TARGET_TYPES)
    unexpected = tuple(
        sorted(registered_targets - set(route_targets) - allowed_extra)
    )
    valid_panels = set(valid_panel_ids)
    valid_scene_cards = set(valid_scene_card_ids)
    valid_template_cards = set(valid_template_card_ids)
    valid_workbench_features = set(valid_workbench_feature_card_ids)
    invalid_panels: list[tuple[str, str]] = []
    invalid_cards: list[tuple[str, str, str]] = []
    invalid_features: list[tuple[str, str]] = []
    for target in registered_workbench_issue_navigation_target_types():
        projection = workbench_issue_navigation_for_target(target)
        if projection.panel_id:
            if projection.panel_id not in valid_panels:
                invalid_panels.append((target, projection.panel_id))
            if (
                projection.panel_id == "scene"
                and projection.card_id not in valid_scene_cards
            ):
                invalid_cards.append((target, projection.panel_id, projection.card_id))
            if (
                projection.panel_id == "template"
                and projection.card_id not in valid_template_cards
            ):
                invalid_cards.append((target, projection.panel_id, projection.card_id))
        if (
            projection.feature_card_id
            and projection.feature_card_id not in valid_workbench_features
        ):
            invalid_features.append((target, projection.feature_card_id))
    return WorkbenchIssueNavigationAuditResult(
        missing_route_target_types=missing,
        fallback_route_target_types=fallback,
        unexpected_navigation_target_types=unexpected,
        invalid_panel_targets=tuple(sorted(invalid_panels)),
        invalid_card_targets=tuple(sorted(invalid_cards)),
        invalid_feature_card_targets=tuple(sorted(invalid_features)),
        invalid_scene_field_targets=audit_workbench_scene_field_focus_targets(
            scene_field_targets
        ),
        invalid_template_field_targets=audit_workbench_template_field_focus_targets(
            template_field_targets
        ),
    )


def workbench_issue_navigation_for_target(
    target_type: str,
    target_key: str = "",
) -> WorkbenchIssueNavigationProjection:
    """Return the registered Workbench navigation projection for a target."""

    normalized_type = str(target_type or "").strip()
    normalized_key = str(target_key or "").strip()
    if normalized_type in PROFILE_CANDIDATE_TARGET_TYPES:
        return WorkbenchIssueNavigationProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            action_kind="material_profile_candidate",
            panel_id="assets",
        )
    if normalized_type in PROFILE_MATERIAL_TARGET_TYPES:
        return WorkbenchIssueNavigationProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            action_kind="material_profile_target",
            panel_id="assets",
        )
    if normalized_type in MATERIAL_TARGET_TYPES:
        return WorkbenchIssueNavigationProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            action_kind="material_target",
            panel_id="assets",
        )
    if normalized_type in TEMPLATE_TARGET_CARD_MAP:
        return WorkbenchIssueNavigationProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            action_kind="template_panel",
            panel_id="template",
            card_id=TEMPLATE_TARGET_CARD_MAP[normalized_type],
        )
    if normalized_type == "question_figure_batch_apply_transaction_task_summary":
        return WorkbenchIssueNavigationProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            action_kind="transaction_artifact",
            feature_card_id="quick_execute",
        )
    if normalized_type in SCENE_TARGET_CARD_MAP:
        return WorkbenchIssueNavigationProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            action_kind="scene_panel",
            panel_id="scene",
            card_id=SCENE_TARGET_CARD_MAP[normalized_type],
        )
    if normalized_type in WORKBENCH_FEATURE_TARGET_MAP:
        return WorkbenchIssueNavigationProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            action_kind="feature_card",
            feature_card_id=WORKBENCH_FEATURE_TARGET_MAP[normalized_type],
        )
    return WorkbenchIssueNavigationProjection(
        target_type=normalized_type,
        target_key=normalized_key,
        action_kind="feature_card",
        feature_card_id="content_fill",
    )


def workbench_issue_parameter_navigation_target(
    issue: WorkbenchIssueItem | None,
    parameter_path: str,
) -> tuple[str, str]:
    """Return a repair target for a parameter evidence action."""

    value = str(parameter_path or "").strip()
    if not value:
        return "", ""
    if value.startswith("scene.section_styles."):
        return _normalized_scene_field_navigation_target("scene_style_field", value)
    if value.startswith("section_styles."):
        return _normalized_scene_field_navigation_target(
            "scene_style_field",
            f"scene.{value}",
        )
    if value.startswith("scene.format_scope."):
        return _normalized_scene_field_navigation_target(
            "scene_scope_field",
            value,
        )
    if value.startswith("format_scope."):
        return _normalized_scene_field_navigation_target("scene_scope_field", value)
    if issue is not None:
        target_type, target_key = workbench_issue_action_target(issue)
        if target_type:
            return target_type, target_key
    return "parameter_path", value


def _normalized_scene_field_navigation_target(
    target_type: str,
    target_key: str,
) -> tuple[str, str]:
    projection = workbench_scene_field_focus_projection(target_type, target_key)
    if projection.valid and projection.normalized_key:
        return target_type, projection.normalized_key
    return target_type, target_key


__all__ = [
    "WorkbenchIssueNavigationProjection",
    "WorkbenchIssueNavigationAuditResult",
    "WorkbenchSceneFieldFocusProjection",
    "WorkbenchTemplateFieldFocusProjection",
    "audit_workbench_issue_navigation_routes",
    "audit_workbench_scene_field_focus_targets",
    "audit_workbench_template_field_focus_targets",
    "registered_workbench_issue_navigation_target_types",
    "workbench_issue_navigation_for_target",
    "workbench_issue_parameter_navigation_target",
    "workbench_scene_field_focus_projection",
    "workbench_template_field_focus_projection",
]
