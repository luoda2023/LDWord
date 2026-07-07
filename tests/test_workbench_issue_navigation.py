import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.adapters.workbench_execution_adapter import WorkbenchIssueItem
from src.ui.adapters.workbench_issue_navigation import (
    audit_workbench_issue_navigation_routes,
    audit_workbench_scene_field_focus_targets,
    audit_workbench_template_field_focus_targets,
    registered_workbench_issue_navigation_target_types,
    workbench_issue_navigation_for_target,
    workbench_issue_parameter_navigation_target,
    workbench_scene_field_focus_projection,
    workbench_template_field_focus_projection,
)


def test_workbench_issue_navigation_registry_maps_targets_to_surfaces():
    cases = {
        "profile_field": ("material_profile_target", "assets", "", ""),
        "material": ("material_target", "assets", "", ""),
        "field": ("material_target", "assets", "", ""),
        "schema": ("scene_panel", "scene", "scn_content", ""),
        "template": ("template_panel", "template", "tpl_overview", ""),
        "template_style_field": ("template_panel", "template", "tpl_style", ""),
        "template_page_field": ("template_panel", "template", "tpl_page", ""),
        "scene": ("scene_panel", "scene", "scn_overview", ""),
        "scene_profile": ("scene_panel", "scene", "scn_overview", ""),
        "count_profile": ("scene_panel", "scene", "scn_overview", ""),
        "scene_style_field": ("scene_panel", "scene", "scn_rules", ""),
        "scene_scope_field": ("scene_panel", "scene", "scn_rules", ""),
        "delivery_preset": ("scene_panel", "scene", "scn_rules", ""),
        "output_target": ("scene_panel", "scene", "scn_rules", ""),
        "coverage_boundary": ("scene_panel", "scene", "scn_overview", ""),
        "sample_fixture": ("scene_panel", "scene", "scn_overview", ""),
        "parameter_ownership": ("scene_panel", "scene", "scn_overview", ""),
        "control_contract": ("scene_panel", "scene", "scn_cleanup", ""),
        "row_height": ("scene_panel", "scene", "scn_cleanup", ""),
        "parameter_path": ("scene_panel", "scene", "scn_cleanup", ""),
        "plugin_manual_gate": ("feature_card", "", "", "quick_execute"),
        "question_figure_batch_apply_transaction_task_summary": (
            "transaction_artifact",
            "",
            "",
            "quick_execute",
        ),
    }

    for target_type, expected in cases.items():
        projection = workbench_issue_navigation_for_target(target_type, "payload")
        assert (
            projection.action_kind,
            projection.panel_id,
            projection.card_id,
            projection.feature_card_id,
        ) == expected
        assert projection.target_type == target_type
        assert projection.target_key == "payload"


def test_workbench_issue_navigation_registry_falls_back_to_content_fill():
    projection = workbench_issue_navigation_for_target("unknown_target", "x")

    assert projection.action_kind == "feature_card"
    assert projection.panel_id == ""
    assert projection.feature_card_id == "content_fill"


def test_workbench_issue_navigation_audit_covers_scene_repair_routes():
    audit = audit_workbench_issue_navigation_routes()

    assert audit.is_clean
    assert audit.invalid_panel_targets == ()
    assert audit.invalid_card_targets == ()
    assert audit.invalid_feature_card_targets == ()
    assert audit.invalid_scene_field_targets == ()
    assert audit.invalid_template_field_targets == ()
    assert "template" in registered_workbench_issue_navigation_target_types()
    assert "delivery_preset" in registered_workbench_issue_navigation_target_types()
    assert "parameter_path" in registered_workbench_issue_navigation_target_types()


def test_workbench_issue_navigation_audit_reports_missing_route_targets():
    @dataclass(frozen=True, slots=True)
    class Route:
        repair_target_types: tuple[str, ...]

    audit = audit_workbench_issue_navigation_routes(
        (
            Route(("field", "not_registered_yet")),
        )
    )

    assert audit.missing_route_target_types == ("not_registered_yet",)
    assert audit.fallback_route_target_types == ("not_registered_yet",)


def test_workbench_issue_navigation_audit_reports_missing_surfaces():
    audit = audit_workbench_issue_navigation_routes(
        (),
        valid_panel_ids=("assets", "scene"),
        valid_scene_card_ids=("scn_rules",),
        valid_template_card_ids=("tpl_overview",),
        valid_workbench_feature_card_ids=("content_fill",),
        scene_field_targets=(
            ("scene_scope_field", "format_scope.sections.not_a_zone"),
        ),
        template_field_targets=(
            ("template_page_field", "template.page_setup.margin.not_a_field"),
        ),
    )

    assert ("template", "template") in audit.invalid_panel_targets
    assert ("control_contract", "scene", "scn_cleanup") in audit.invalid_card_targets
    assert ("plugin", "quick_execute") in audit.invalid_feature_card_targets
    assert audit.invalid_scene_field_targets == (
        (
            "scene_scope_field",
            "format_scope.sections.not_a_zone",
            "unknown_scope_zone",
        ),
    )
    assert audit.invalid_template_field_targets == (
        (
            "template_page_field",
            "template.page_setup.margin.not_a_field",
            "unknown_page_field",
        ),
    )


def test_workbench_scene_field_focus_projection_normalizes_reusable_controls():
    scope_projection = workbench_scene_field_focus_projection(
        "scene_scope_field",
        "scene.format_scope.sections.references",
    )
    assert scope_projection.valid
    assert scope_projection.focus_kind == "scope_zone"
    assert scope_projection.normalized_key == "format_scope.sections.references"

    style_projection = workbench_scene_field_focus_projection(
        "scene_style_field",
        "scene.section_styles.references_body.font_cn",
    )
    assert style_projection.valid
    assert style_projection.focus_kind == "style_variant"
    assert (
        style_projection.normalized_key
        == "scene.section_styles.references_body.font_cn"
    )
    assert style_projection.display_label == "参考文献正文中文字体"
    assert style_projection.display_label_with_group == (
        "文字样式：参考文献正文中文字体"
    )
    assert style_projection.layout_item_id == "font_cn"
    assert style_projection.field_ids == ("font_cn",)
    assert style_projection.control_contract_key == "body.font_cn"

    style_toggle_projection = workbench_scene_field_focus_projection(
        "scene_style_field",
        "references_body",
    )
    assert style_toggle_projection.valid
    assert style_toggle_projection.focus_kind == "style_variant_toggle"
    assert style_toggle_projection.normalized_key == "scene.section_styles.references_body"
    assert style_toggle_projection.display_label == "参考文献正文"

    prefixed_toggle_projection = workbench_scene_field_focus_projection(
        "scene_style_field",
        "scene.section_styles.references_body",
    )
    assert prefixed_toggle_projection.valid
    assert prefixed_toggle_projection.focus_kind == "style_variant_toggle"
    assert (
        prefixed_toggle_projection.normalized_key
        == "scene.section_styles.references_body"
    )

    alias_style_projection = workbench_scene_field_focus_projection(
        "scene_style_field",
        "section_styles.references_body.line_spacing_value",
    )
    assert alias_style_projection.valid
    assert alias_style_projection.focus_kind == "style_variant"
    assert (
        alias_style_projection.normalized_key
        == "scene.section_styles.references_body.line_spacing_pt"
    )

    wildcard_projection = workbench_scene_field_focus_projection(
        "scene_style_field",
        "scene.section_styles.*.line_spacing_value",
    )
    assert wildcard_projection.valid
    assert wildcard_projection.focus_kind == "style_wildcard"
    assert (
        wildcard_projection.normalized_key
        == "scene.section_styles.*.line_spacing_pt"
    )
    assert wildcard_projection.display_label == "所有处理分区行距"
    assert wildcard_projection.display_label_with_group == (
        "行距与段距：所有处理分区行距"
    )
    assert wildcard_projection.layout_item_id == "line_spacing_pt"
    assert wildcard_projection.control_contract_key == "body.line_spacing"

    editor_projection = workbench_scene_field_focus_projection(
        "scene_style_field",
        "section_style.left_indent_chars",
    )
    assert editor_projection.valid
    assert editor_projection.focus_kind == "style_editor"
    assert editor_projection.normalized_key == "section_style.left_indent"
    assert editor_projection.display_label_with_group == "对齐与缩进：左缩进"
    assert editor_projection.layout_item_id == "left_indent"
    assert editor_projection.control_contract_key == "body.left_indent"

    schema_projection = workbench_scene_field_focus_projection(
        "schema",
        "input_source_profile.material_schema_id",
    )
    assert schema_projection.valid
    assert schema_projection.focus_kind == "material_schema_contract"
    assert (
        schema_projection.normalized_key
        == "input_source_profile.material_schema_id"
    )

    schema_id_projection = workbench_scene_field_focus_projection(
        "schema",
        "signature_assets_v2",
    )
    assert schema_id_projection.valid
    assert schema_id_projection.focus_kind == "material_schema_id"
    assert schema_id_projection.normalized_key == "signature_assets_v2"


def test_workbench_scene_field_focus_audit_reports_unknown_controls():
    invalid = audit_workbench_scene_field_focus_targets(
        (
            ("scene_scope_field", "format_scope.sections.not_a_zone"),
            (
                "scene_style_field",
                "scene.section_styles.not_a_variant.font_cn",
            ),
            (
                "scene_style_field",
                "scene.section_styles.references_body.not_a_field",
            ),
        )
    )

    assert invalid == (
        (
            "scene_scope_field",
            "format_scope.sections.not_a_zone",
            "unknown_scope_zone",
        ),
        (
            "scene_style_field",
            "scene.section_styles.not_a_variant.font_cn",
            "unknown_style_variant",
        ),
        (
            "scene_style_field",
            "scene.section_styles.references_body.not_a_field",
            "unknown_style_field",
        ),
    )


def test_workbench_scene_style_focus_reuses_shared_path_descriptors():
    source = (ROOT / "src/ui/adapters/workbench_issue_navigation.py").read_text(
        encoding="utf-8"
    )

    assert "scene_style_navigation_target_from_field_id" in source
    assert "src.config.style_variant_semantics" not in source
    assert "_scene_style_variant_ids" not in source


def test_workbench_template_field_focus_projection_normalizes_reusable_controls():
    style_projection = workbench_template_field_focus_projection(
        "template_style_field",
        "template.styles.body.font_name",
    )
    assert style_projection.valid
    assert style_projection.focus_kind == "style_editor"
    assert style_projection.normalized_key == "template.styles.body.font_cn"
    assert style_projection.display_label == "正文中文字体"
    assert style_projection.display_label_with_group == "文字样式：正文中文字体"
    assert style_projection.layout_item_id == "font_cn"
    assert style_projection.control_contract_key == "body.font_cn"

    style_alias_projection = workbench_template_field_focus_projection(
        "template_style_field",
        "body.line_spacing_value",
    )
    assert style_alias_projection.valid
    assert (
        style_alias_projection.normalized_key
        == "template.styles.body.line_spacing_pt"
    )
    assert style_alias_projection.display_label_with_group == (
        "行距与段距：正文行距"
    )
    assert style_alias_projection.layout_item_id == "line_spacing_pt"
    assert style_alias_projection.control_contract_key == "body.line_spacing"

    page_projection = workbench_template_field_focus_projection(
        "template_page_field",
        "template.page_setup.margin.left_cm",
    )
    assert page_projection.valid
    assert page_projection.focus_kind == "page_margin"
    assert page_projection.normalized_key == "template.page_setup.margin.left_cm"

    header_projection = workbench_template_field_focus_projection(
        "template_page_field",
        "template.page_setup.header_distance_cm",
    )
    assert header_projection.valid
    assert header_projection.focus_kind == "page_header_footer"


def test_workbench_template_field_focus_audit_reports_unknown_controls():
    invalid = audit_workbench_template_field_focus_targets(
        (
            ("template_style_field", "template.styles.body.not_a_field"),
            (
                "template_page_field",
                "template.page_setup.margin.not_a_field",
            ),
            ("template_field", "template.name"),
        )
    )

    assert invalid == (
        (
            "template_field",
            "template.name",
            "unsupported_target_type",
        ),
        (
            "template_page_field",
            "template.page_setup.margin.not_a_field",
            "unknown_page_field",
        ),
        (
            "template_style_field",
            "template.styles.body.not_a_field",
            "unknown_style_field",
        ),
    )


def test_workbench_issue_parameter_navigation_target_routes_scene_paths_and_fallback():
    fallback_issue = WorkbenchIssueItem(
        issue_id="ui.control_contract.required.body_special_indent",
        category="control_contract",
        severity="warning",
        title="控件契约缺失",
        summary="body.special_indent",
        repair_target_type="control_contract",
        repair_target_key="body.special_indent",
    )

    assert workbench_issue_parameter_navigation_target(
        fallback_issue,
        "scene.section_styles.references_body.font_cn",
    ) == (
        "scene_style_field",
        "scene.section_styles.references_body.font_cn",
    )
    assert workbench_issue_parameter_navigation_target(
        fallback_issue,
        "section_styles.references_body.font_cn",
    ) == (
        "scene_style_field",
        "scene.section_styles.references_body.font_cn",
    )
    assert workbench_issue_parameter_navigation_target(
        fallback_issue,
        "scene.section_styles.*.line_spacing_value",
    ) == (
        "scene_style_field",
        "scene.section_styles.*.line_spacing_pt",
    )
    assert workbench_issue_parameter_navigation_target(
        fallback_issue,
        "scene.format_scope.sections.references",
    ) == (
        "scene_scope_field",
        "format_scope.sections.references",
    )
    assert workbench_issue_parameter_navigation_target(
        fallback_issue,
        "body.special_indent",
    ) == (
        "control_contract",
        "body.special_indent",
    )
    assert workbench_issue_parameter_navigation_target(
        None,
        "body.special_indent",
    ) == (
        "parameter_path",
        "body.special_indent",
    )
