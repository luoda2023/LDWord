import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.control_contract_registry import ControlContractAuditResult
from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace
from src.config.scene_sample_fixture_registry import SceneSampleFixtureAuditIssue
from src.config.scene_repair_routing import (
    REQUIRED_SCENE_REPAIR_ROUTE_IDS,
    audit_scene_repair_routing,
    build_scene_repair_route_summary,
    get_scene_repair_route,
    list_scene_repair_routes,
    repair_route_for_issue,
    repair_route_for_target,
)
from src.ui.adapters.workbench_execution_adapter import (
    WorkbenchIssueItem,
    control_contract_issue_items,
    coverage_boundary_issue_items,
    material_readiness_issue_items,
    object_preflight_issue_items,
    output_target_preflight_issue_items,
    parameter_ownership_issue_items,
    sample_fixture_issue_items,
)
from src.ui.panels.workbench.scene_presets import create_bidding_scene


def test_scene_repair_routing_registry_covers_n2_131_required_targets():
    routes = {route.route_id: route for route in list_scene_repair_routes()}
    audit = audit_scene_repair_routing(project_root=ROOT)

    assert audit.is_clean
    assert set(REQUIRED_SCENE_REPAIR_ROUTE_IDS) <= set(routes)
    assert repair_route_for_target("control_contract").route_id == (
        "template_control_contract"
    )
    assert repair_route_for_target("template_style_field").route_id == (
        "template_field_repair"
    )
    assert repair_route_for_target("parameter_ownership").route_id == "scene_profile"
    assert repair_route_for_target("scene_scope_field").route_id == "scene_field_repair"
    assert repair_route_for_target("scene_style_field").route_id == "scene_field_repair"
    assert repair_route_for_target("field").route_id == "material_package"
    assert repair_route_for_target("asset").route_id == "material_package"
    assert repair_route_for_target("schema").route_id == "material_package"
    assert repair_route_for_target("output_target").route_id == "output_delivery"
    assert repair_route_for_target("object_preflight").route_id == "object_preflight"
    assert repair_route_for_target("row_height").route_id == "fixed_layout"
    assert repair_route_for_target("sample_fixture").route_id == "scene_profile"
    assert repair_route_for_target("plugin_manual_gate").route_id == (
        "plugin_manual_gate"
    )


def test_scene_repair_route_summary_exposes_surface_and_owner_layer():
    summary = build_scene_repair_route_summary(
        get_scene_repair_route("fixed_layout")
    )

    assert "fixed_layout [fixed_layout]" in summary
    assert "row_height" in summary
    assert "content_control" in summary
    assert "ScenePanel fixed-layout profile" in summary


def test_scene_repair_routing_classifies_existing_workbench_issue_items():
    material_items = material_readiness_issue_items(
        create_bidding_scene(),
        MaterialExecutionContext(),
    )
    output_items = output_target_preflight_issue_items(
        {
            "items": [
                {
                    "preset_id": "review",
                    "path": "missing/review.docx",
                    "issues": [{"message": "目录不存在"}],
                }
            ]
        }
    )
    object_items = object_preflight_issue_items(
        {
            "enabled": True,
            "findings_count": 1,
            "findings": [
                {
                    "kind": "comments",
                    "severity": "warning",
                    "location": "word/comments.xml",
                    "message": "含批注",
                }
            ],
        }
    )
    plugin_items = coverage_boundary_issue_items(
        SceneWorkspace(scene_id="exam_teaching", category="exam_teaching")
    )
    control_items = control_contract_issue_items(
        ControlContractAuditResult(missing_required_contracts=("body.special_indent",))
    )

    @dataclass
    class FutureSceneWorkspace(SceneWorkspace):
        experimental_knob: str = ""

    scene_items = parameter_ownership_issue_items(FutureSceneWorkspace(scene_id="future"))
    sample_items = sample_fixture_issue_items(
        SceneWorkspace(scene_id="contract_delivery", category="contract_delivery"),
        audit=[
            SceneSampleFixtureAuditIssue(
                fixture_id="contract_delivery_revisions",
                kind="missing_surfaces",
                message="Sample fixture must declare at least one DOCX surface.",
            )
        ],
    )
    fixed_layout_item = WorkbenchIssueItem(
        issue_id="fixed_layout.row_height",
        category="fixed_layout",
        severity="warning",
        title="固定版位行高",
        summary="row_height",
        repair_target_type="row_height",
        repair_target_key="form_batch_documents.table.row_height_pt",
    )
    template_field_item = WorkbenchIssueItem(
        issue_id="template.body.left_indent",
        category="template_field",
        severity="warning",
        title="妯℃澘瀛楁淇",
        summary="body.left_indent",
        repair_target_type="template_style_field",
        repair_target_key="template.styles.body.left_indent_chars",
    )
    scene_style_item = WorkbenchIssueItem(
        issue_id="scene.references.font",
        category="scene_style",
        severity="warning",
        title="场景样式覆盖",
        summary="references_body.font_cn",
        repair_target_type="scene_style_field",
        repair_target_key="scene.section_styles.references_body.font_cn",
    )

    classified = {
        "template_field": repair_route_for_issue(template_field_item).route_id,
        "scene_style": repair_route_for_issue(scene_style_item).route_id,
        "material_field": repair_route_for_issue(material_items[0]).route_id,
        "material_asset": repair_route_for_issue(material_items[1]).route_id,
        "output_target": repair_route_for_issue(output_items[0]).route_id,
        "object_preflight": repair_route_for_issue(object_items[0]).route_id,
        "plugin_boundary": repair_route_for_issue(plugin_items[0]).route_id,
        "control_contract": repair_route_for_issue(control_items[0]).route_id,
        "parameter_ownership": repair_route_for_issue(scene_items[0]).route_id,
        "sample_fixture": repair_route_for_issue(sample_items[0]).route_id,
        "fixed_layout": repair_route_for_issue(fixed_layout_item).route_id,
    }

    assert classified == {
        "template_field": "template_field_repair",
        "scene_style": "scene_field_repair",
        "material_field": "material_package",
        "material_asset": "material_package",
        "output_target": "output_delivery",
        "object_preflight": "object_preflight",
        "plugin_boundary": "plugin_manual_gate",
        "control_contract": "template_control_contract",
        "parameter_ownership": "scene_profile",
        "sample_fixture": "scene_profile",
        "fixed_layout": "fixed_layout",
    }


def test_scene_repair_routing_can_fallback_from_issue_category():
    item = WorkbenchIssueItem(
        issue_id="delivery.missing",
        category="output_target",
        severity="warning",
        title="输出缺失",
        summary="review",
        repair_target_type="",
        repair_target_key="review",
    )

    assert repair_route_for_issue(item).route_id == "output_delivery"
