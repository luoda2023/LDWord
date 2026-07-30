"""Customer-runtime Workbench issue navigation registry."""

from __future__ import annotations

from dataclasses import dataclass


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
}

SCENE_TARGET_CARD_MAP: dict[str, str] = {
    "scene": "scn_overview",
    "scene_profile": "scn_overview",
    "profile": "scn_overview",
    "count_profile": "scn_overview",
    "scene_document_scope_field": "scn_rules",
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
            feature_card_id="content_fill",
        )
    if normalized_type in PROFILE_MATERIAL_TARGET_TYPES:
        return WorkbenchIssueNavigationProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            action_kind="material_profile_target",
            feature_card_id="content_fill",
        )
    if normalized_type in MATERIAL_TARGET_TYPES:
        return WorkbenchIssueNavigationProjection(
            target_type=normalized_type,
            target_key=normalized_key,
            action_kind="material_target",
            feature_card_id="content_fill",
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


__all__ = [
    "MATERIAL_TARGET_TYPES",
    "PROFILE_CANDIDATE_TARGET_TYPES",
    "PROFILE_MATERIAL_TARGET_TYPES",
    "SCENE_TARGET_CARD_MAP",
    "TEMPLATE_TARGET_CARD_MAP",
    "WORKBENCH_FEATURE_TARGET_MAP",
    "WORKBENCH_NAVIGATION_ALLOWED_EXTRA_TARGET_TYPES",
    "WorkbenchIssueNavigationProjection",
    "workbench_issue_navigation_for_target",
]
