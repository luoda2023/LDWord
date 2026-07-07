import sys
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.config.control_contract_registry import ControlContractAuditResult
from src.config.material_context import MaterialExecutionContext
from src.config.materials import AssetItem
from src.config.scene import SceneWorkspace
from src.config.scene_sample_fixture_registry import SceneSampleFixtureAuditIssue
from src.config.style_difference_projection import StyleDifferenceSummaryProjection
from src.shared.ui.style_difference_summary_slot import StyleDifferenceSummarySlot
from src.shared.ui.style_management_block import StyleManagementBlock
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.style_receipt_slot_frame import StyleReceiptSlotFrame
from src.ui.adapters.workbench_execution_adapter import (
    WorkbenchExecutionAdapter,
    WorkbenchIssueItem,
    batch_execution_issue_items,
    control_contract_issue_items,
    coverage_boundary_issue_items,
    execution_diagnostic_issue_items,
    material_asset_comparison_issue_items,
    material_readiness_issue_items,
    material_readiness_issue_groups,
    material_readiness_reasons,
    material_schema_readiness_reasons,
    object_preflight_issue_items,
    output_target_preflight_issue_items,
    parameter_ownership_issue_items,
    question_figure_repair_queue_issue_items,
    question_figure_transaction_task_issue_items,
    sample_fixture_issue_items,
    summarize_workbench_issue_queue,
    update_workbench_issue_status,
    workbench_issue_action_group,
    workbench_issue_action_target,
    workbench_issue_action_visual,
    workbench_issue_action_visual_for_item,
    workbench_issue_display_text,
    workbench_issue_evidence_actions,
    workbench_issue_evidence_body_text,
    workbench_issue_evidence_lines,
    workbench_issue_source_note_label,
)
from src.ui.panels.workbench.execution_center import ExecutionCenter
from src.ui.panels.workbench.execution_runtime import _batch_issue_items_for_result
from src.ui.panels.workbench.scene_presets import create_bidding_scene
from src.ui.panels.workbench.state import (
    ExecutionProgressState,
    ExecutionResultState,
    ReadinessState,
    RecentRunState,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_execution_center_routes_style_receipt_through_style_object_projection():
    source = (ROOT / "src/ui/panels/workbench/execution_center.py").read_text(
        encoding="utf-8"
    )

    assert "build_execution_style_projection" in source
    assert "apply_style_object_projection(style_projection)" in source
    assert "effective_style_source_envelope" not in source
    assert "_style_receipt_slot.apply_envelope" not in source
    assert "_style_difference_slot.apply_projection" not in source


def test_execution_progress_state_defaults_are_safe():
    state = ExecutionProgressState()

    assert state.stage_text == "等待执行"
    assert state.current_step == 0
    assert state.total_steps == 0
    assert state.percent == 0


def test_execution_result_state_defaults_are_safe():
    state = ExecutionResultState()

    assert state.status == "idle"
    assert state.summary == "尚未执行"
    assert state.error_text == ""
    assert state.output_path == ""
    assert state.output_paths == {}
    assert state.compare_paths == {}
    assert state.report_paths == []
    assert state.intermediate_paths == {}
    assert state.artifact_items == []
    assert state.failed_count == 0
    assert state.diagnostics_count == 0
    assert state.diagnostics_summary == ""
    assert state.style_source_envelope.is_empty() is True
    assert state.style_difference_summary is None
    assert state.object_preflight == {}
    assert state.object_preflight_summary == ""
    assert state.object_preflight_details == []
    assert state.material_field_consistency == {}
    assert state.material_field_consistency_summary == ""


def test_recent_run_state_defaults_are_safe():
    state = RecentRunState()

    assert state.status == "idle"
    assert state.title == "最近结果"
    assert state.summary == "暂无最近结果"
    assert state.output_label == ""
    assert state.compare_label == ""
    assert state.report_label == ""
    assert state.intermediate_label == ""
    assert state.error_summary == ""
    assert state.diagnostics_count == 0
    assert state.diagnostics_summary == ""
    assert state.style_source_envelope.is_empty() is True
    assert state.style_difference_summary is None
    assert state.object_preflight == {}
    assert state.object_preflight_summary == ""
    assert state.object_preflight_details == []
    assert state.material_field_consistency == {}
    assert state.material_field_consistency_summary == ""


def test_readiness_state_defaults_to_blocked():
    state = ReadinessState()

    assert state.ready is False
    assert state.label == "待执行"
    assert state.reasons == ["未选择文档", "未选择策略"]


def test_execution_center_defaults_to_canonical_readiness_state():
    _app()
    center = ExecutionCenter()
    default_state = ReadinessState()

    assert center._ready_label.text() == default_state.label
    assert center._reason_label.text() == "、".join(default_state.reasons)
    assert isinstance(center._style_receipt_block, StyleManagementBlock)
    assert center._style_receipt_block.isHidden() is True
    assert center._style_receipt_block.property("style_management_mode") == (
        "execution_receipt_review"
    )
    assert center._style_receipt_block.property("style_management_content_plan") == (
        "difference|receipt"
    )
    assert isinstance(center._style_difference_slot, StyleDifferenceSummarySlot)
    assert center._style_difference_slot.isHidden() is True
    assert center._style_receipt_block.difference_slot is center._style_difference_slot
    assert isinstance(center._style_receipt_slot, StyleReceiptSlotFrame)
    assert center._style_receipt_slot.property("style_management_content_plan") == (
        "receipt"
    )
    assert center._style_receipt_slot.receipt_row is center._style_receipt_row
    assert center._style_receipt_block.receipt_slot is center._style_receipt_slot
    assert center._style_receipt_block.property("style_management_has_editor") is False


def test_execution_center_exposes_polish_section_labels():
    _app()
    center = ExecutionCenter()

    assert center._center_title.text() == "执行中心"
    assert center._center_title.objectName() == "wb_execution_title"
    assert center._summary_title.text() == "执行摘要"
    assert center._progress_title.text() == "执行进度"


def test_execution_center_primary_surface_uses_styled_section_hooks():
    _app()
    center = ExecutionCenter()
    center.set_readiness(ReadinessState(ready=True, label="待执行", reasons=[]))
    center.set_progress_state(
        ExecutionProgressState(stage_text="执行中", current_step=1, total_steps=2, percent=50)
    )

    assert center._progress_title.objectName() == "wb_execution_section_title"
    assert center._summary_title.objectName() == "wb_execution_section_title"
    assert center._status_label.objectName() == "wb_execution_status"
    assert center._summary_box.objectName() == "wb_execution_summary"
    assert center._status_label.text() == "执行中"
    assert center._execute_button.isEnabled() is False
    assert center._cancel_button.isEnabled() is True


def test_execution_adapter_build_readiness_blocks_without_document_or_strategy():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_readiness(has_document=False, has_strategy=False)

    assert state.ready is False
    assert state.label == "待执行"
    assert state.reasons == ["未选择文档", "未选择策略"]


def test_execution_adapter_build_readiness_blocks_without_document():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_readiness(has_document=False, has_strategy=True)

    assert state.ready is False
    assert state.label == "待执行"
    assert state.reasons == ["未选择文档"]


def test_execution_adapter_build_readiness_blocks_without_strategy():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_readiness(has_document=True, has_strategy=False)

    assert state.ready is False
    assert state.label == "待执行"
    assert state.reasons == ["未选择策略"]


def test_execution_adapter_build_readiness_ready_with_document_and_strategy():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_readiness(has_document=True, has_strategy=True)

    assert state.ready is True
    assert state.label == "待执行"
    assert state.reasons == []


def test_material_schema_readiness_reasons_reports_unknown_schema():
    scene = SceneWorkspace()
    scene.input_source_profile.material_schema_id = "missing_schema_v1"

    assert material_schema_readiness_reasons(scene) == [
        "资料 Schema 未注册：missing_schema_v1"
    ]


def test_material_readiness_issue_groups_recommend_schema_replacement():
    scene = SceneWorkspace(scene_id="contract_delivery")
    scene.category = "contract_delivery"
    scene.input_source_profile.material_schema_id = "signature_assets_v2"

    groups = material_readiness_issue_groups(scene, MaterialExecutionContext())

    assert groups.schema_ids == ("signature_assets_v2",)
    assert groups.recommendation_schema_id == "signature_assets_v1"
    assert "alias:signature_assets_v2" in groups.recommendation_reasons
    assert "family:contract_delivery" in groups.recommendation_reasons
    assert any(line.startswith("推荐替换：signature_assets_v1") for line in groups.detail_lines())
    assert "来源：推荐 Schema：signature_assets_v1" in groups.detail_lines()


def test_material_readiness_issue_items_expose_schema_recommendation_for_workbench_queue():
    scene = SceneWorkspace(scene_id="contract_delivery")
    scene.category = "contract_delivery"
    scene.input_source_profile.material_schema_id = "signature_assets_v2"

    items = material_readiness_issue_items(scene, MaterialExecutionContext())

    assert len(items) == 1
    item = items[0]
    assert item.issue_id == "material.schema.unregistered"
    assert item.category == "material_schema"
    assert item.severity == "error"
    assert item.blocking is True
    assert item.summary == "signature_assets_v2"
    assert item.repair_target_type == "schema"
    assert item.repair_target_key == "signature_assets_v2"
    assert len(item.details) == 1
    assert item.details[0].startswith("推荐替换：signature_assets_v1")
    assert "alias:signature_assets_v2" in item.details[0]
    assert "family:contract_delivery" in item.details[0]
    assert "推荐 Schema：signature_assets_v1" in item.source_notes
    assert any("推荐替换：signature_assets_v1" in line for line in item.tooltip_lines())


def test_material_readiness_issue_items_group_fields_and_assets_for_workbench_queue():
    scene = create_bidding_scene()

    items = material_readiness_issue_items(scene, MaterialExecutionContext())

    assert [item.issue_id for item in items] == [
        "material.fields.missing",
        "material.assets.missing",
    ]
    field_item, asset_item = items
    assert field_item.category == "material_field"
    assert field_item.repair_target_type == "field"
    assert field_item.repair_target_key == "company_name"
    assert field_item.summary == "company_name, project_name, legal_person"
    assert field_item.blocking is True
    assert asset_item.category == "material_asset"
    assert asset_item.repair_target_type == "asset"
    assert asset_item.repair_target_key == "logo"
    assert asset_item.summary == "logo, seal"
    assert asset_item.blocking is True


def test_material_asset_comparison_issue_items_route_question_figure_targets():
    context = MaterialExecutionContext(
        profile_id="exam_a",
        profile_name="Exam A",
        asset_items=[
            AssetItem(
                item_id="question_figure_2",
                label="Question 2 figure",
                role="question_figure",
                path="C:/exam/question_2.png",
                metadata={
                    "question_index": "2",
                    "comparison_issue_status": "flagged",
                    "comparison_issue_type": "manual_compare",
                    "comparison_issue_reference": "C:/exam/question_1.png",
                    "comparison_issue_display_name": "question_1.png",
                    "comparison_issue_kind": "题图对比",
                    "comparison_issue_marked_at": "2026-06-21T00:00:00+00:00",
                    "comparison_issue_summary": "题2 题图对比: question_1.png",
                    "comparison_issue_region_type": "current_view",
                    "comparison_issue_region_summary": (
                        "current_view(x=0, y=0, w=320, h=240, zoom=100%, image=320x240)"
                    ),
                },
            )
        ],
    )

    items = material_asset_comparison_issue_items(context)

    assert len(items) == 1
    item = items[0]
    assert item.category == "material_asset_comparison"
    assert item.title == "题图对比问题"
    assert item.summary == "题2 题图对比: question_1.png"
    assert item.repair_target_type == "question_figure_item"
    assert any("差异区域：current_view(" in detail for detail in item.details)
    assert item.repair_context == (("profile_id", "exam_a"), ("profile_name", "Exam A"))
    target = json.loads(item.repair_target_key)
    assert target["item_id"] == "question_figure_2"
    assert target["question_index"] == "2"
    assert target["metadata"]["comparison_issue_status"] == "flagged"
    action_type, action_payload = workbench_issue_action_target(item)
    assert action_type == "profile_question_figure_item"
    action_data = json.loads(action_payload)
    assert action_data["profile_id"] == "exam_a"
    assert json.loads(action_data["target_key"])["item_id"] == "question_figure_2"


def test_workbench_issue_queue_summary_filters_by_category():
    scene = create_bidding_scene()
    items = [
        *material_readiness_issue_items(scene, MaterialExecutionContext()),
        *coverage_boundary_issue_items(
            SceneWorkspace(scene_id="exam_teaching", category="exam_teaching")
        ),
    ]

    summary = summarize_workbench_issue_queue(items)

    assert summary.total_count == 3
    assert summary.visible_count == 3
    assert summary.blocking_count == 2
    assert summary.actionable_count == 3
    assert summary.category_counts == (
        ("material_field", 1),
        ("material_asset", 1),
        ("plugin_boundary", 1),
    )
    assert summary.severity_counts == (("warning", 3),)
    assert summary.status_counts == (("open", 3),)
    assert summary.owner_counts == (
        ("workbench", 2),
        ("plugin", 1),
    )
    assert summary.action_group_counts == (
        ("handle_first", 2),
        ("confirm", 1),
    )
    assert summary.visible_action_group_counts == (
        ("handle_first", 2),
        ("confirm", 1),
    )
    assert summary.repair_target_counts == (
        ("field:company_name", 1),
        ("asset:logo", 1),
        ("plugin_manual_gate:exam_ai_complex_diagram_gate", 1),
    )

    filtered = summarize_workbench_issue_queue(items, category="plugin_boundary")

    assert filtered.total_count == 3
    assert filtered.visible_count == 1
    assert filtered.actionable_count == 1
    assert filtered.active_category == "plugin_boundary"
    assert filtered.status_counts == (("open", 3),)
    assert filtered.owner_counts == (
        ("workbench", 2),
        ("plugin", 1),
    )
    assert filtered.action_group_counts == (
        ("handle_first", 2),
        ("confirm", 1),
    )
    assert filtered.visible_action_group_counts == (("confirm", 1),)
    assert filtered.repair_target_counts == (
        ("plugin_manual_gate:exam_ai_complex_diagram_gate", 1),
    )
    assert filtered.visible_items[0].issue_id == "coverage.exam_education.plugin_boundary"

    action_filtered = summarize_workbench_issue_queue(
        items,
        action_group="confirm",
    )

    assert action_filtered.total_count == 3
    assert action_filtered.visible_count == 1
    assert action_filtered.active_action_group == "confirm"
    assert action_filtered.visible_action_group_counts == (("confirm", 1),)
    assert action_filtered.visible_items[0].issue_id == (
        "coverage.exam_education.plugin_boundary"
    )

    combined_empty = summarize_workbench_issue_queue(
        items,
        category="material_field",
        action_group="confirm",
    )

    assert combined_empty.visible_count == 0
    assert combined_empty.active_category == "material_field"
    assert combined_empty.active_action_group == "confirm"
    assert combined_empty.visible_action_group_counts == ()
    assert combined_empty.visible_items == ()


def test_workbench_issue_action_group_keeps_user_action_language_stable():
    open_blocker = material_readiness_issue_items(
        create_bidding_scene(),
        MaterialExecutionContext(),
    )[0]
    confirmable = coverage_boundary_issue_items(
        SceneWorkspace(scene_id="exam_teaching", category="exam_teaching")
    )[0]
    view_only = update_workbench_issue_status(
        [confirmable],
        confirmable.issue_id,
        "resolved",
    )[0]

    assert workbench_issue_action_group(open_blocker) == "handle_first"
    assert workbench_issue_action_group(confirmable) == "confirm"
    assert workbench_issue_action_group(view_only) == "view_only"

    blocker_visual = workbench_issue_action_visual_for_item(open_blocker)
    confirm_visual = workbench_issue_action_visual_for_item(confirmable)
    resolved_visual = workbench_issue_action_visual_for_item(view_only)

    assert (blocker_visual.label, blocker_visual.rank, blocker_visual.badge_tone) == (
        "先处理",
        0,
        "error",
    )
    assert (confirm_visual.label, confirm_visual.rank, confirm_visual.detail_tone) == (
        "建议确认",
        1,
        "info",
    )
    assert (resolved_visual.label, resolved_visual.rank, resolved_visual.detail_tone) == (
        "仅查看",
        2,
        "success",
    )
    assert workbench_issue_action_visual("unknown").label == "仅查看"


def test_workbench_issue_evidence_projection_keeps_ui_semantics_in_adapter():
    item = WorkbenchIssueItem(
        issue_id="ui.control_contract.required.body_special_indent",
        category="control_contract",
        severity="warning",
        title="控件契约缺失",
        summary="body.special_indent",
        details=(
            "缺少必审控件契约：body.special_indent",
            "参数路径：body.special_indent",
            "证据：src/shared/ui/paragraph_style_inputs.py:120#class SpecialIndentInput",
            "输出路径：output/report.docx",
            "替换来源：profiles/default.json",
            "保护模式：strict",
        ),
        source_notes=("control_contract_registry",),
        repair_target_type="control_contract",
        repair_target_key="body.special_indent",
        owner="scene",
    )

    lines = workbench_issue_evidence_lines(item)

    assert [(line.kind, line.label, line.text) for line in lines] == [
        ("note", "说明", "缺少必审控件契约：正文特殊缩进（body.special_indent）"),
        ("parameter_path", "参数", "正文特殊缩进"),
        (
            "evidence_file",
            "证据文件",
            "src/shared/ui/paragraph_style_inputs.py:120#class SpecialIndentInput",
        ),
        ("output_path", "输出", "output/report.docx"),
        ("replacement", "替换来源", "profiles/default.json"),
        ("guard", "保护", "strict"),
        ("source", "来源", "控件边界登记"),
    ]
    assert [
        (line.action_type, line.action_label, line.tone)
        for line in lines
        if line.has_action()
    ] == [
        ("navigate_parameter", "定位参数", "primary"),
        ("open_evidence", "打开证据", "primary"),
        ("open_output", "打开输出", "primary"),
        ("open_replacement", "打开来源", "primary"),
    ]
    assert workbench_issue_evidence_actions(item) == (
        ("parameter_path", "navigate_parameter", "body.special_indent"),
        (
            "evidence_file",
            "open_evidence",
            "src/shared/ui/paragraph_style_inputs.py:120#class SpecialIndentInput",
        ),
        ("output_path", "open_output", "output/report.docx"),
        ("replacement", "open_replacement", "profiles/default.json"),
    )
    assert "来源：控件边界登记" in workbench_issue_evidence_body_text(item)
    assert workbench_issue_source_note_label("control_contract_registry") == (
        "控件边界登记"
    )
    assert workbench_issue_display_text("coverage pack：contract_delivery") == (
        "覆盖资料包：合同交付"
    )
    assert workbench_issue_display_text("控件契约缺失：body.special_indent") == (
        "控件契约缺失：正文特殊缩进（body.special_indent）"
    )
    assert workbench_issue_display_text(
        "控件契约缺失：body.special_indent",
        include_raw_field_key=False,
    ) == "控件契约缺失：正文特殊缩进"

    emphasis_item = WorkbenchIssueItem(
        issue_id="template.body.bold",
        category="template_style",
        severity="warning",
        title="模板样式不一致",
        summary="template.styles.body.bold",
        details=("参数路径：template.styles.body.bold",),
        repair_target_type="template_style_field",
        repair_target_key="template.styles.body.bold",
        owner="template",
    )
    emphasis_lines = workbench_issue_evidence_lines(emphasis_item)
    assert [(line.kind, line.label, line.text) for line in emphasis_lines] == [
        ("parameter_path", "参数", "正文字形"),
    ]
    assert workbench_issue_evidence_actions(emphasis_item) == (
        ("parameter_path", "navigate_parameter", "template.styles.body.bold"),
    )
    assert workbench_issue_display_text(
        "模板样式不一致：template.styles.body.bold",
        include_raw_field_key=False,
    ) == "模板样式不一致：正文字形"


def test_parameter_ownership_issue_items_expose_audit_gaps_for_workbench_queue():
    @dataclass
    class FutureSceneWorkspace(SceneWorkspace):
        experimental_knob: str = ""

    items = parameter_ownership_issue_items(FutureSceneWorkspace(scene_id="future"))

    assert len(items) == 1
    item = items[0]
    assert item.issue_id == "scene.parameter_ownership.audit"
    assert item.category == "parameter_ownership"
    assert item.severity == "warning"
    assert item.title == "参数归属缺口"
    assert item.summary == "1 类缺口"
    assert item.details == ("缺少顶层字段归属：experimental_knob",)
    assert item.repair_target_type == "parameter_ownership"
    assert item.repair_target_key == "registry"
    assert item.owner == "scene"
    assert item.blocking is False

    summary = summarize_workbench_issue_queue(items)
    assert summary.category_counts == (("parameter_ownership", 1),)
    assert summary.owner_counts == (("scene", 1),)
    assert summary.repair_target_counts == (("parameter_ownership:registry", 1),)


def test_sample_fixture_issue_items_expose_audit_gaps_for_workbench_queue():
    scene = SceneWorkspace(scene_id="contract_delivery", category="contract_delivery")
    items = sample_fixture_issue_items(
        scene,
        audit=[
            SceneSampleFixtureAuditIssue(
                fixture_id="contract_delivery_revisions",
                kind="missing_surfaces",
                message="Sample fixture must declare at least one DOCX surface.",
            )
        ],
    )

    assert len(items) == 1
    item = items[0]
    assert item.issue_id == (
        "sample_fixture.contract_delivery_missing_surfaces_contract_delivery_revisions"
    )
    assert item.category == "sample_fixture"
    assert item.severity == "error"
    assert item.title == "样本覆盖缺口"
    assert item.summary == "contract_delivery: missing_surfaces"
    assert item.repair_target_type == "sample_fixture"
    assert item.repair_target_key == "contract_delivery"
    assert item.owner == "scene"
    assert item.blocking is False
    assert "覆盖 pack：contract_delivery" in item.details
    assert "scene_sample_fixture_registry" in item.source_notes
    assert workbench_issue_action_target(item) == (
        "sample_fixture",
        "contract_delivery",
    )

    summary = summarize_workbench_issue_queue(items)
    assert summary.category_counts == (("sample_fixture", 1),)
    assert summary.owner_counts == (("scene", 1),)
    assert summary.repair_target_counts == (
        ("sample_fixture:contract_delivery", 1),
    )


def test_control_contract_issue_items_expose_audit_gaps_for_workbench_queue():
    audit = ControlContractAuditResult(
        missing_required_contracts=("body.special_indent",),
        invalid_owner_layers=(("body.left_indent", "loose"),),
        missing_paired_contracts=(("body.left_indent", "body.right_indent"),),
        missing_evidence_files=(("body.font_cn", "src/missing.py"),),
        missing_evidence_markers=(
            ("body.font_en", "src/ui/panels/template_style_detail.py", "FontCombo"),
        ),
    )

    items = control_contract_issue_items(audit)

    assert [item.issue_id for item in items] == [
        "ui.control_contract.required.body_special_indent",
        "ui.control_contract.owner.body_left_indent",
        "ui.control_contract.pair.body_left_indent.body_right_indent",
        "ui.control_contract.evidence_file.body_font_cn.src_missing_py",
        "ui.control_contract.evidence_marker.body_font_en.fontcombo",
    ]
    by_id = {item.issue_id: item for item in items}
    missing = by_id["ui.control_contract.required.body_special_indent"]
    assert missing.category == "control_contract"
    assert missing.severity == "warning"
    assert missing.title == "控件契约缺失"
    assert missing.summary == "body.special_indent"
    assert missing.repair_target_type == "control_contract"
    assert missing.repair_target_key == "body.special_indent"
    assert missing.owner == "scene"
    assert missing.blocking is False
    assert missing.details[0] == "缺少必审控件契约：body.special_indent"
    assert "契约：特殊缩进 (body.special_indent)" in missing.details
    assert "规范控件：SpecialIndentInput" in missing.details
    assert "归属层：template" in missing.details
    assert any(line.startswith("参数路径：") for line in missing.details)
    evidence_lines = [line for line in missing.details if line.startswith("证据：")]
    assert any(
        line.startswith("证据：src/shared/ui/paragraph_style_inputs.py:")
        and "#class SpecialIndentInput" in line
        and ":0#" not in line
        for line in evidence_lines
    )
    assert "control_contract_registry" in missing.source_notes
    assert by_id["ui.control_contract.owner.body_left_indent"].details[0] == (
        "非法控件归属层：body.left_indent:loose"
    )
    assert by_id[
        "ui.control_contract.pair.body_left_indent.body_right_indent"
    ].details[0] == "配对控件缺失：body.left_indent->body.right_indent"
    assert by_id[
        "ui.control_contract.evidence_file.body_font_cn.src_missing_py"
    ].details[0] == "证据文件缺失：body.font_cn:src/missing.py"
    marker_details = by_id[
        "ui.control_contract.evidence_marker.body_font_en.fontcombo"
    ].details
    assert marker_details[0].startswith("证据 marker 缺失：body.font_en")

    summary = summarize_workbench_issue_queue(items)
    assert summary.category_counts == (("control_contract", 5),)
    assert summary.owner_counts == (("scene", 5),)
    assert summary.repair_target_counts == (
        ("control_contract:body.special_indent", 1),
        ("control_contract:body.left_indent", 2),
        ("control_contract:body.font_cn", 1),
        ("control_contract:body.font_en", 1),
    )


def test_workbench_issue_status_update_returns_new_queue_items():
    scene = create_bidding_scene()
    items = [
        *material_readiness_issue_items(scene, MaterialExecutionContext()),
        *coverage_boundary_issue_items(
            SceneWorkspace(scene_id="exam_teaching", category="exam_teaching")
        ),
    ]

    updated = update_workbench_issue_status(
        items,
        "material.assets.missing",
        "resolved",
    )
    updated = update_workbench_issue_status(
        updated,
        "coverage.exam_education.plugin_boundary",
        "ignored",
    )
    unchanged = update_workbench_issue_status(
        updated,
        "material.fields.missing",
        "done",
    )

    assert [item.status for item in updated] == ["open", "resolved", "ignored"]
    assert [item.status for item in items] == ["open", "open", "open"]
    assert unchanged == updated
    assert summarize_workbench_issue_queue(updated).status_counts == (
        ("open", 1),
        ("resolved", 1),
        ("ignored", 1),
    )


def test_coverage_boundary_issue_items_expose_plugin_boundary_for_planned_family():
    scene = SceneWorkspace(scene_id="exam_teaching")
    scene.category = "exam_teaching"

    items = coverage_boundary_issue_items(scene)

    assert len(items) == 1
    item = items[0]
    assert item.issue_id == "coverage.exam_education.plugin_boundary"
    assert item.category == "plugin_boundary"
    assert item.severity == "warning"
    assert item.blocking is False
    assert item.repair_target_type == "plugin_manual_gate"
    assert item.repair_target_key == "exam_ai_complex_diagram_gate"
    assert "Exam and teaching materials" in item.summary
    assert "does not guarantee AI content quality" in item.summary
    assert any("exam_ai_quality_diagram_plugin" in line for line in item.details)
    assert any("required" in line for line in item.details)
    assert any("ai_content_quality" in line for line in item.details)
    assert any("needs_plugin_handoff" in line for line in item.details)
    assert any("ContentVisibilityRule" in line for line in item.details)
    assert any("geometry_diagram_generation" in line for line in item.details)
    assert not any(
        "AI quality and complex diagram plugin entry" in line and "P2/plugin/L4" in line
        for line in item.details
    )
    assert item.source_notes == ("coverage pack：exam_education",)


def test_coverage_boundary_issue_items_support_direct_import_gate_scene():
    scene = SceneWorkspace(scene_id="import_ai_boundary", category="import_ai_boundary")

    items = coverage_boundary_issue_items(scene)

    assert len(items) == 1
    item = items[0]
    assert item.issue_id == "coverage.import_ai_boundary.plugin_boundary"
    assert item.repair_target_type == "plugin_manual_gate"
    assert item.repair_target_key == "import_ai_conversion_gate"
    assert any("import_ai_assistant_plugin" in line for line in item.details)
    assert any("ocr_confidence" in line for line in item.details)
    assert any("lossless_pdf_to_word" in line for line in item.details)


def test_coverage_boundary_issue_items_expose_contract_legal_boundary_banner():
    scene = SceneWorkspace(scene_id="contract_delivery", category="contract_delivery")

    items = coverage_boundary_issue_items(scene)

    assert len(items) == 1
    item = items[0]
    assert item.issue_id == "coverage.contract_delivery.coverage_boundary"
    assert item.category == "coverage_boundary"
    assert item.severity == "warning"
    assert item.blocking is False
    assert item.owner == "scene"
    assert item.repair_target_type == "coverage_boundary"
    assert item.repair_target_key == "contract_delivery"
    assert "Contract delivery" in item.summary
    assert "does not provide legal advice" in item.summary
    assert any("material_schema" in line for line in item.details)
    assert any("ObjectPreflight" in line for line in item.details)

    summary = summarize_workbench_issue_queue(items)
    assert summary.category_counts == (("coverage_boundary", 1),)
    assert summary.owner_counts == (("scene", 1),)
    assert summary.repair_target_counts == (
        ("coverage_boundary:contract_delivery", 1),
    )


def test_coverage_boundary_issue_items_do_not_warn_for_normal_p0_report_scene():
    scene = SceneWorkspace(scene_id="report")

    assert coverage_boundary_issue_items(scene) == []


def test_material_readiness_reasons_reports_missing_fields_and_assets():
    scene = create_bidding_scene()

    assert material_readiness_reasons(scene, MaterialExecutionContext()) == [
        "资料字段缺失：company_name, project_name, legal_person",
        "资料资产缺失：logo, seal",
    ]


def test_material_readiness_issue_groups_report_structured_missing_materials():
    scene = create_bidding_scene()

    groups = material_readiness_issue_groups(scene, MaterialExecutionContext())

    assert groups.schema_ids == ()
    assert groups.field_keys == ("company_name", "project_name", "legal_person")
    assert groups.asset_roles == ("logo", "seal")
    assert groups.source_notes == (
        "Schema：Bidding materials (bid_materials_v1)",
        "场景字段：company_name, project_name, legal_person",
        "场景资产：logo, seal",
        "当前资料：未配置",
    )
    assert groups.detail_lines() == [
        "字段：company_name, project_name, legal_person",
        "资产：logo, seal",
        "来源：Schema：Bidding materials (bid_materials_v1)",
        "来源：场景字段：company_name, project_name, legal_person",
        "来源：场景资产：logo, seal",
        "来源：当前资料：未配置",
    ]


def test_material_readiness_reasons_clears_when_context_satisfies_requirements():
    scene = create_bidding_scene()
    context = MaterialExecutionContext(
        entity_data={
            "company_name": "测试公司",
            "project_name": "示例项目",
            "legal_person": "张三",
        },
        asset_items=[
            AssetItem(role="logo", path="C:/assets/logo.png"),
            AssetItem(role="seal", path="C:/assets/seal.png"),
        ],
    )

    assert material_readiness_reasons(scene, context) == []


def test_execution_adapter_build_readiness_blocks_unknown_material_schema():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_readiness(
        has_document=True,
        has_strategy=True,
        material_schema_reasons=["资料 Schema 未注册：missing_schema_v1"],
    )

    assert state.ready is False
    assert state.label == "待执行"
    assert state.reasons == ["资料 Schema 未注册：missing_schema_v1"]


def test_execution_center_renders_readiness_and_summary():
    _app()
    center = ExecutionCenter()
    blocked_state = ReadinessState(
        reasons=["未选择文档", "未选择策略"],
        label="待执行",
    )

    center.set_readiness(blocked_state)

    assert center._ready_label.text() == "待执行"
    assert center._reason_label.text() == "未选择文档、未选择策略"

    ready_state = ReadinessState(
        ready=True,
        label="待执行",
        reasons=[],
    )

    center.set_readiness(ready_state)
    center.set_summary("本次启用模块：3")

    assert center._ready_label.text() == "待执行"
    assert center._reason_label.text() == ""
    assert center._summary_box.toPlainText() == "本次启用模块：3"


def test_execution_center_buttons_follow_readiness_and_running_state():
    _app()
    center = ExecutionCenter()

    assert not center._execute_button.isEnabled()
    assert not center._cancel_button.isEnabled()

    ready_state = ReadinessState(ready=True, label="待执行", reasons=[])
    center.set_readiness(ready_state)
    assert center._execute_button.isEnabled()

    progress_state = ExecutionProgressState(
        stage_text="正在生成目录",
        current_step=1,
        total_steps=3,
        percent=33,
    )

    center.set_progress_state(progress_state)

    assert not center._execute_button.isEnabled()
    assert center._cancel_button.isEnabled()
    assert center._status_label.text() == "执行中"


def test_execution_center_final_state_restores_controls_and_show_friendly_text():
    _app()
    center = ExecutionCenter()
    center.set_readiness(ReadinessState(ready=True, label="待执行", reasons=[]))

    center.set_progress_state(
        ExecutionProgressState(stage_text="正在生成目录", current_step=2, total_steps=4, percent=50)
    )

    result_state = ExecutionResultState(
        status="success",
        summary="执行成功",
        error_text="",
        output_path="C:/tmp/output.docx",
        report_paths=["C:/tmp/report"],
        failed_count=0,
    )

    center.set_result_state(result_state)

    assert center._status_label.text() == "已完成"
    assert center._summary_box.toPlainText() == "执行成功"
    assert center._cancel_button.isEnabled() is False
    assert center._execute_button.isEnabled()


def test_execution_center_result_state_renders_partial_success_and_cancelled_text():
    _app()
    center = ExecutionCenter()

    partial = ExecutionResultState(status="partial_success", summary="部分完成", error_text="")
    center.set_result_state(partial)
    assert center._status_label.text() == "部分完成"

    cancelled = ExecutionResultState(status="cancelled", summary="已取消", error_text="")
    center.set_result_state(cancelled)
    assert center._status_label.text() == "已取消"


def test_execution_center_readiness_change_during_run_keeps_buttons_consistent():
    _app()
    center = ExecutionCenter()

    center.set_readiness(ReadinessState(ready=True, label="待执行", reasons=[]))
    center.set_progress_state(
        ExecutionProgressState(stage_text="进行中", current_step=1, total_steps=2, percent=50)
    )

    assert not center._execute_button.isEnabled()
    assert center._cancel_button.isEnabled()

    center.set_readiness(ReadinessState(ready=False, label="待执行", reasons=["策略变更"]))

    assert not center._execute_button.isEnabled()
    assert center._cancel_button.isEnabled()

    center.set_result_state(ExecutionResultState(status="failed", summary="执行失败", error_text=""))

    assert not center._cancel_button.isEnabled()
    assert not center._execute_button.isEnabled()
    assert center._status_label.text() == "执行失败"
def test_execution_center_emits_execute_and_cancel_signals():
    _app()
    center = ExecutionCenter()

    execute_calls: list[bool] = []
    cancel_calls: list[bool] = []

    center.execute_requested.connect(lambda: execute_calls.append(True))
    center.cancel_requested.connect(lambda: cancel_calls.append(True))

    center.set_readiness(ReadinessState(ready=True, label="待执行", reasons=[]))

    center._execute_button.click()
    center.set_progress_state(
        ExecutionProgressState(stage_text="执行中", current_step=1, total_steps=2, percent=50)
    )
    center._cancel_button.click()

    assert execute_calls == [True]
    assert cancel_calls == [True]

def test_execution_center_progress_state_renders_stage_step_counts_and_bar():
    _app()
    center = ExecutionCenter()

    state = ExecutionProgressState(
        stage_text="正在生成目录",
        current_step=2,
        total_steps=5,
        percent=40,
    )

    center.set_progress_state(state)

    assert center._progress_stage_label.text() == "正在生成目录"
    assert center._progress_label.text() == "2 / 5"
    assert center._progress_bar.value() == 40

def test_execution_center_result_state_renders_status_and_summary():
    _app()
    center = ExecutionCenter()

    result = ExecutionResultState(
        status="failed",
        summary="执行失败",
        error_text="错误信息",
        output_path="C:/tmp/output.docx",
        report_paths=["C:/tmp/report"],
        failed_count=1,
    )

    center.set_result_state(result)

    assert center._status_label.text() == "执行失败"
    assert center._summary_box.toPlainText() == "执行失败"


def test_execution_center_result_state_renders_style_source_receipt():
    _app()
    center = ExecutionCenter()

    result = ExecutionResultState(
        status="success",
        summary="本次执行已完成",
        style_source_envelope=StylePresentationEnvelope(
            kind="execution_receipt",
            title="样式来源",
            summary="本次按模板“默认格式”处理",
            detail="参考文献（行距）使用场景独立样式。",
        ),
        style_difference_summary=StyleDifferenceSummaryProjection(
            template_status="模板基线",
            current_status="参考文献 独立样式",
            difference_status="已调整 1 项",
            detail="不同：行距",
            variant="warning",
            section_count=1,
            changed_section_count=1,
        ),
    )

    center.set_result_state(result)

    assert center._summary_box.toPlainText() == "本次执行已完成"
    assert center._style_receipt_block.isHidden() is False
    assert center._style_receipt_block.property("style_object_kind") == "execution_style"
    assert center._style_receipt_block.property("style_object_label") == "样式回执"
    assert center._style_receipt_block.property("style_object_source_label") == "本次使用"
    assert center._style_receipt_block.property("style_object_scope_label") == "执行结果"
    assert center._style_receipt_block.property("style_object_edit_state_label") == "只读"
    assert center._style_receipt_block.property("style_management_content_plan") == (
        "difference|receipt"
    )
    assert center._style_difference_slot.isHidden() is False
    assert center._style_difference_slot.property("style_difference_status") == (
        "已调整 1 项"
    )
    assert center._style_difference_slot.property("style_difference_current_status") == (
        "参考文献 独立样式"
    )
    assert center._style_receipt_row.isHidden() is False
    assert center._style_receipt_row.summary_text() == (
        "样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。"
    )
    assert center._style_receipt_row.property("style_presentation_kind") == (
        "execution_receipt"
    )
    assert center._style_receipt_row.detail.text() == (
        "本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。"
    )


def test_execution_center_hides_receipt_block_without_style_source():
    _app()
    center = ExecutionCenter()

    center.set_result_state(
        ExecutionResultState(
            status="success",
            summary="本次执行已完成",
        )
    )

    assert center._summary_box.toPlainText() == "本次执行已完成"
    assert center._style_difference_slot.isHidden() is True
    assert center._style_receipt_row.isHidden() is True
    assert center._style_receipt_block.isHidden() is True
    assert center._style_receipt_block.property("style_object_kind") == "execution_style"


def test_execution_center_shows_style_difference_without_receipt():
    _app()
    center = ExecutionCenter()

    center.set_result_state(
        ExecutionResultState(
            status="success",
            summary="本次执行已完成",
            style_difference_summary=StyleDifferenceSummaryProjection(
                template_status="模板基线",
                current_status="2 个格式例外",
                difference_status="1 个格式例外已调整",
                detail="不同：参考文献改了行距",
                variant="warning",
                section_count=2,
                changed_section_count=1,
            ),
        )
    )

    assert center._style_receipt_block.isHidden() is False
    assert center._style_receipt_block.property("style_object_kind") == "execution_style"
    assert center._style_receipt_row.isHidden() is True
    assert center._style_difference_slot.isHidden() is False
    assert center._style_difference_slot.property("style_difference_detail") == (
        "不同：参考文献改了行距"
    )


def test_execution_adapter_builds_progress_state_from_step_counts():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_progress_state(
        stage_text="正在生成目录",
        current_step=2,
        total_steps=5,
    )

    assert isinstance(state, ExecutionProgressState)
    assert state.stage_text == "正在生成目录"
    assert state.current_step == 2
    assert state.total_steps == 5
    assert state.percent == 40


def test_execution_adapter_maps_pipeline_stage_text_to_shared_user_flow():
    adapter = WorkbenchExecutionAdapter()

    assert adapter.build_progress_state(
        stage_text="Loading document",
        current_step=1,
        total_steps=5,
    ).stage_text == "读取文件"
    assert adapter.build_progress_state(
        stage_text="Object preflight",
        current_step=2,
        total_steps=5,
    ).stage_text == "检查风险"
    assert adapter.build_progress_state(
        stage_text="Running module: 正文排版",
        current_step=3,
        total_steps=5,
    ).stage_text == "套用模板"
    assert adapter.build_progress_state(
        stage_text="Writing report",
        current_step=4,
        total_steps=5,
    ).stage_text == "生成报告"
    assert adapter.build_progress_state(
        stage_text="Saving output",
        current_step=5,
        total_steps=5,
    ).stage_text == "输出文件"


def test_execution_adapter_builds_success_result_state():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="success",
        output_path="C:/tmp/out.docx",
        report_paths=["C:/tmp/report.json", "C:/tmp/report.md"],
        failed_count=0,
        error_text="",
        diagnostics_count=1,
        diagnostics_summary="诊断提示（1）\n- [equation_table_format] 1 个公式编号: skipped",
        style_source={
            "template_label": "默认格式",
            "summary": "本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。",
            "section_status": "1 个格式例外",
            "sections": [
                {
                    "variant_key": "references_body",
                    "label": "参考文献",
                    "current_status": "独立样式",
                    "difference_status": "已调整 1 项",
                    "detail": "不同：行距",
                    "changed_labels": ["行距"],
                    "overridden": True,
                    "follows_template": False,
                }
            ],
        },
    )

    assert isinstance(state, ExecutionResultState)
    assert state.status == "success"
    assert state.summary == "本次执行已完成"
    assert state.output_path.endswith("out.docx")
    assert len(state.report_paths) == 2
    assert state.failed_count == 0
    assert state.diagnostics_count == 1
    assert "诊断提示（1）" in state.diagnostics_summary
    assert state.style_source["template_label"] == "默认格式"
    assert state.style_source_summary == (
        "样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。"
    )
    assert state.style_source_envelope.kind == "execution_receipt"
    assert state.style_source_envelope.receipt_summary(title_fallback="样式来源") == (
        state.style_source_summary
    )
    assert isinstance(state.style_difference_summary, StyleDifferenceSummaryProjection)
    assert state.style_difference_summary.current_status == "参考文献 独立样式"
    assert state.style_difference_summary.difference_status == "已调整 1 项"
    assert state.style_difference_summary.detail == "不同：行距"

    recent = adapter.build_recent_run_state(state)
    assert recent.style_source_summary == state.style_source_summary
    assert recent.style_source_envelope == state.style_source_envelope
    assert recent.style_difference_summary == state.style_difference_summary


def test_execution_adapter_converts_batch_issue_payloads_to_workbench_issues():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="partial_success",
        output_path="",
        report_paths=["C:/tmp/batch_report.json"],
        failed_count=1,
        error_text="",
        batch_isolation={
            "kind": "batch_failure_isolation",
            "total_count": 2,
            "success_count": 1,
            "warning_count": 0,
            "failed_count": 1,
            "profiles": [
                {"profile_id": "ok", "profile_name": "完整员工", "status": "success"},
                {
                    "profile_id": "missing",
                    "profile_name": "缺编号员工",
                    "status": "failed",
                    "missing_field_keys": ["employee_id"],
                    "missing_asset_roles": [],
                    "summary": "Missing required material fields: employee_id",
                },
            ],
        },
        batch_issue_items=[
            {
                "issue_id": "batch:missing:preflight_missing_material_fields:1",
                "profile_id": "missing",
                "profile_name": "缺编号员工",
                "status": "failed",
                "kind": "preflight_missing_material_fields",
                "severity": "error",
                "summary": "Missing required material fields: employee_id",
                "missing_field_keys": ["employee_id"],
                "repair_target_type": "field",
                "repair_target_key": "employee_id",
            }
        ],
    )

    assert len(state.issue_items) == 1
    item = state.issue_items[0]
    assert item.category == "batch_issue"
    assert item.title == "批量记录问题"
    assert item.summary == "Missing required material fields: employee_id"
    assert item.repair_target_type == "field"
    assert item.repair_target_key == "employee_id"
    assert item.repair_context[0] == ("profile_id", "missing")
    action_type, action_payload = workbench_issue_action_target(item)
    assert action_type == "profile_field"
    action_data = json.loads(action_payload)
    assert action_data["profile_id"] == "missing"
    assert action_data["target_key"] == "employee_id"
    assert state.batch_isolation_summary == (
        "Batch isolation: total=2; success=1; warning=0; failed=1"
    )
    assert any("employee_id" in line for line in state.batch_isolation_details)
    assert item.owner == "workbench"
    assert item.blocking is True
    assert "记录 ID：missing" in item.details
    assert "缺字段：employee_id" in item.details


def test_batch_execution_issue_items_preserve_asset_repair_targets():
    items = batch_execution_issue_items(
        [
            {
                "profile_id": "a",
                "profile_name": "主体 A",
                "kind": "preflight_missing_asset_roles",
                "summary": "Missing asset: seal",
                "missing_asset_roles": ["seal"],
                "repair_target_type": "asset",
                "repair_target_key": "seal",
            }
        ]
    )

    assert len(items) == 1
    assert items[0].category == "batch_issue"
    assert items[0].repair_target_type == "asset"
    assert items[0].repair_target_key == "seal"
    action_type, action_payload = workbench_issue_action_target(items[0])
    assert action_type == "profile_asset"
    assert json.loads(action_payload)["profile_id"] == "a"
    assert "缺素材：seal" in items[0].details


def test_batch_execution_issue_items_preserve_question_figure_item_targets():
    target_key = json.dumps(
        {
            "role": "question_figure",
            "item_id": "question_figure_2",
            "question_index": "2",
            "path": "missing_question_2.png",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    items = batch_execution_issue_items(
        [
            {
                "profile_id": "exam_a",
                "profile_name": "Exam A",
                "kind": "preflight_missing_question_figure_file",
                "summary": "Missing question figure file for question 2",
                "missing_asset_items": [
                    {
                        "role": "question_figure",
                        "item_id": "question_figure_2",
                        "path": "missing_question_2.png",
                    }
                ],
                "repair_target_type": "question_figure_item",
                "repair_target_key": target_key,
            }
        ]
    )

    assert len(items) == 1
    assert items[0].category == "batch_issue"
    assert items[0].repair_target_type == "question_figure_item"
    assert items[0].repair_target_key == target_key
    action_type, action_payload = workbench_issue_action_target(items[0])
    assert action_type == "profile_question_figure_item"
    action_data = json.loads(action_payload)
    assert action_data["profile_id"] == "exam_a"
    assert json.loads(action_data["target_key"])["question_index"] == "2"


def test_batch_execution_issue_items_infer_scene_field_targets_from_parameter_paths():
    items = batch_execution_issue_items(
        [
            {
                "profile_id": "thesis_a",
                "profile_name": "论文 A",
                "kind": "scene_style_diagnostic",
                "summary": "参考文献字体需要场景级检查",
                "parameter_path": "scene.section_styles.references_body.font_cn",
            },
            {
                "profile_id": "thesis_a",
                "profile_name": "论文 A",
                "kind": "scene_scope_diagnostic",
                "summary": "参考文献范围未纳入处理",
                "parameter_paths": ["scene.format_scope.sections.references"],
            },
            {
                "profile_id": "thesis_a",
                "profile_name": "论文 A",
                "kind": "scene_style_wildcard_diagnostic",
                "summary": "场景分区行距需要检查",
                "parameter_path": "scene.section_styles.*.line_spacing_pt",
            },
            {
                "profile_id": "thesis_a",
                "profile_name": "论文 A",
                "kind": "scene_style_alias_diagnostic",
                "summary": "参考文献行距需要场景级检查",
                "parameter_path": "section_styles.references_body.line_spacing_value",
            },
        ]
    )

    style_item, scope_item, wildcard_item, alias_item = items
    assert style_item.category == "batch_issue"
    assert style_item.repair_target_type == "scene_style_field"
    assert style_item.repair_target_key == "scene.section_styles.references_body.font_cn"
    assert "参数路径：scene.section_styles.references_body.font_cn" in style_item.details
    assert workbench_issue_action_target(style_item) == (
        "scene_style_field",
        "scene.section_styles.references_body.font_cn",
    )

    assert scope_item.category == "batch_issue"
    assert scope_item.repair_target_type == "scene_scope_field"
    assert scope_item.repair_target_key == "format_scope.sections.references"
    assert "参数路径：scene.format_scope.sections.references" in scope_item.details
    assert workbench_issue_action_target(scope_item) == (
        "scene_scope_field",
        "format_scope.sections.references",
    )

    assert wildcard_item.repair_target_type == "scene_style_field"
    assert wildcard_item.repair_target_key == "scene.section_styles.*.line_spacing_pt"
    assert "参数路径：scene.section_styles.*.line_spacing_pt" in wildcard_item.details
    assert workbench_issue_action_target(wildcard_item) == (
        "scene_style_field",
        "scene.section_styles.*.line_spacing_pt",
    )

    assert alias_item.repair_target_type == "scene_style_field"
    assert (
        alias_item.repair_target_key
        == "scene.section_styles.references_body.line_spacing_pt"
    )
    assert workbench_issue_action_target(alias_item) == (
        "scene_style_field",
        "scene.section_styles.references_body.line_spacing_pt",
    )


def test_workbench_execution_adapter_reuses_scene_style_path_descriptors():
    source = (ROOT / "src/ui/adapters/workbench_execution_adapter.py").read_text(
        encoding="utf-8"
    )

    assert "scene_style_navigation_target_from_field_id" in source
    assert "canonical_paragraph_style_field_id" in source


def test_execution_diagnostic_issue_items_infer_scene_field_targets():
    items = execution_diagnostic_issue_items(
        [
            {
                "rule_name": "section_style",
                "change_type": "preflight_scene_style",
                "reason": "参考文献字体需要确认",
                "parameter_path": "scene.section_styles.references_body.font_cn",
            },
            {
                "rule_name": "format_scope",
                "change_type": "preflight_scene_scope",
                "reason": "参考文献范围未纳入处理",
                "parameter_paths": ["scene.format_scope.sections.references"],
            },
            {
                "rule_name": "plain_warning",
                "change_type": "skip",
                "reason": "没有可定位字段",
            },
        ]
    )

    assert len(items) == 2
    style_item, scope_item = items
    assert style_item.category == "scene_style"
    assert style_item.title == "场景样式需要确认"
    assert style_item.owner == "scene"
    assert style_item.repair_target_type == "scene_style_field"
    assert style_item.repair_target_key == "scene.section_styles.references_body.font_cn"
    assert "参数路径：scene.section_styles.references_body.font_cn" in style_item.details
    assert workbench_issue_action_target(style_item) == (
        "scene_style_field",
        "scene.section_styles.references_body.font_cn",
    )

    assert scope_item.category == "scene_scope"
    assert scope_item.title == "场景处理范围需要确认"
    assert scope_item.repair_target_type == "scene_scope_field"
    assert scope_item.repair_target_key == "format_scope.sections.references"
    assert "参数路径：scene.format_scope.sections.references" in scope_item.details
    assert workbench_issue_action_target(scope_item) == (
        "scene_scope_field",
        "format_scope.sections.references",
    )


def test_result_state_includes_routable_execution_diagnostic_issues():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="success",
        output_path="out.docx",
        report_paths=[],
        failed_count=0,
        error_text="",
        diagnostics_count=1,
        diagnostics_summary="诊断提示（1）",
        diagnostics_items=[
            {
                "rule_name": "section_style",
                "reason": "行距需要确认",
                "parameter_path": "scene.section_styles.*.line_spacing_pt",
            }
        ],
    )

    assert len(state.issue_items) == 1
    item = state.issue_items[0]
    assert item.category == "scene_style"
    assert item.repair_target_type == "scene_style_field"
    assert item.repair_target_key == "scene.section_styles.*.line_spacing_pt"


def test_runtime_batch_issue_payload_preserves_scene_parameter_paths():
    payloads = _batch_issue_items_for_result(
        {
            "profile_id": "thesis_a",
            "profile_name": "论文 A",
            "status": "partial_success",
            "material_diagnostics": [
                {
                    "change_type": "scene_scope_diagnostic",
                    "reason": "参考文献范围未纳入处理",
                    "level": "warning",
                    "parameter_path": "scene.format_scope.sections.references",
                }
            ],
        }
    )

    assert len(payloads) == 1
    assert payloads[0]["parameter_paths"] == [
        "scene.format_scope.sections.references"
    ]

    item = batch_execution_issue_items(payloads)[0]
    assert item.repair_target_type == "scene_scope_field"
    assert item.repair_target_key == "format_scope.sections.references"


def test_question_figure_repair_queue_issue_items_route_candidates_to_rows():
    target_key = json.dumps(
        {
            "role": "question_figure",
            "item_id": "question_figure_2",
            "question_index": "2",
            "path": "current_question_2.png",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    items = question_figure_repair_queue_issue_items(
        {
            "kind": "question_figure_repair_queue",
            "queue_count": 1,
            "entries": [
                {
                    "queue_id": "repair:question_figure:exam_a:q2:abc",
                    "status": "candidate",
                    "profile_id": "exam_a",
                    "profile_name": "Exam A",
                    "question_index": "2",
                    "comparison_display_name": "question_2_expected.png",
                    "issue_summary": "Question 2 figure mismatch",
                    "region_summary": "current_view(x=0, y=0, w=320, h=240)",
                    "repair_target_type": "question_figure_item",
                    "repair_target_key": target_key,
                    "source_issue_id": "batch:exam_a:manual_compare:1",
                    "requires_user_confirmation": True,
                    "auto_apply_supported": False,
                    "confirmation_apply_supported": True,
                    "confirmation_status": "ready",
                    "replacement_source_path": "C:/tmp/question_2_expected.png",
                    "apply_blockers": [],
                }
            ],
        }
    )

    assert len(items) == 1
    item = items[0]
    assert item.issue_id == "repair:question_figure:exam_a:q2:abc"
    assert item.category == "question_figure_repair_queue"
    assert item.title == "题图修复候选"
    assert item.repair_target_type == "question_figure_item"
    assert item.repair_target_key == target_key
    assert any("candidate" in detail for detail in item.details)
    assert any("current_view(" in detail for detail in item.details)
    assert any("确认替换：可用" in detail for detail in item.details)
    assert any("C:/tmp/question_2_expected.png" in detail for detail in item.details)
    assert any("确认状态：ready" in detail for detail in item.details)
    action_type, action_payload = workbench_issue_action_target(item)
    assert action_type == "profile_question_figure_repair_candidate"
    action_data = json.loads(action_payload)
    assert action_data["profile_id"] == "exam_a"
    assert action_data["profile_name"] == "Exam A"
    assert json.loads(action_data["target_key"])["item_id"] == "question_figure_2"
    assert action_data["candidate"]["repair_target_key"] == target_key
    assert action_data["candidate"]["replacement_source_path"] == (
        "C:/tmp/question_2_expected.png"
    )
    assert action_data["candidate"]["confirmation_status"] == "ready"


def test_question_figure_repair_queue_issue_items_keep_blocked_candidates_as_row_route():
    target_key = json.dumps(
        {
            "role": "question_figure",
            "item_id": "question_figure_5",
            "question_index": "5",
            "path": "current_question_5.png",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    items = question_figure_repair_queue_issue_items(
        {
            "kind": "question_figure_repair_queue",
            "queue_count": 1,
            "entries": [
                {
                    "queue_id": "repair:question_figure:exam_b:q5:def",
                    "status": "candidate",
                    "profile_id": "exam_b",
                    "profile_name": "Exam B",
                    "question_index": "5",
                    "comparison_display_name": "question_5_expected.png",
                    "repair_target_type": "question_figure_item",
                    "repair_target_key": target_key,
                    "requires_user_confirmation": True,
                    "auto_apply_supported": False,
                    "confirmation_apply_supported": False,
                    "confirmation_status": "blocked",
                    "apply_blockers": ["comparison_reference_not_local_file"],
                }
            ],
        }
    )

    assert len(items) == 1
    action_type, action_payload = workbench_issue_action_target(items[0])

    assert action_type == "profile_question_figure_item"
    action_data = json.loads(action_payload)
    assert action_data["profile_id"] == "exam_b"
    assert json.loads(action_data["target_key"])["question_index"] == "5"


def test_question_figure_transaction_task_issue_items_route_active_task_to_report():
    items = question_figure_transaction_task_issue_items(
        {
            "kind": "question_figure_repair_queue",
            "batch_apply_transaction_manifest": {
                "kind": "question_figure_repair_batch_apply_transaction_manifest",
                "status": "tracked",
                "artifact_path": (
                    "C:/tmp/question_figure_batch_apply_transaction_manifest.json"
                ),
                "report_path": (
                    "C:/tmp/question_figure_batch_apply_transaction_manifest.md"
                ),
                "task_summary": {
                    "kind": (
                        "question_figure_repair_batch_apply_transaction_task_summary"
                    ),
                    "status": "active",
                    "next_action": "review_active_transaction",
                    "transaction_count": 2,
                    "active_count": 1,
                    "rolled_back_count": 1,
                    "rollback_available_count": 1,
                    "orphan_rollback_count": 0,
                    "active_transaction_ids": ["tx-active"],
                    "rolled_back_transaction_ids": ["tx-rolled-back"],
                    "rollback_available_transaction_ids": ["tx-active"],
                    "latest_transaction_id": "tx-active",
                    "latest_transaction_status": "applied",
                    "latest_apply_audit_id": "apply-1",
                    "latest_rollback_audit_id": "rollback-1",
                    "report_path": (
                        "C:/tmp/question_figure_batch_apply_transaction_manifest.md"
                    ),
                },
            },
        }
    )

    assert len(items) == 1
    item = items[0]
    assert item.category == "question_figure_batch_apply_transaction_task"
    assert item.severity == "warning"
    assert item.blocking is False
    assert item.owner == "pipeline"
    assert item.repair_target_type == (
        "question_figure_batch_apply_transaction_task_summary"
    )
    assert item.summary == (
        "active; next=review_active_transaction; rollback_available=1"
    )
    assert any("review_active_transaction" in detail for detail in item.details)
    assert any("tx-active" in detail for detail in item.details)
    action_type, action_payload = workbench_issue_action_target(item)
    action_data = json.loads(action_payload)

    assert action_type == "question_figure_batch_apply_transaction_task_summary"
    assert action_data["status"] == "active"
    assert action_data["next_action"] == "review_active_transaction"
    assert action_data["report_path"] == (
        "C:/tmp/question_figure_batch_apply_transaction_manifest.md"
    )
    assert action_data["artifact_path"] == (
        "C:/tmp/question_figure_batch_apply_transaction_manifest.json"
    )
    assert action_data["fragment"] == (
        "question-figure-batch-apply-transaction-task-summary"
    )
    assert action_data["rollback_available_count"] == 1


def test_question_figure_transaction_task_issue_items_only_surface_open_tasks():
    completed_items = question_figure_transaction_task_issue_items(
        {
            "batch_apply_transaction_manifest": {
                "task_summary": {
                    "status": "completed",
                    "next_action": "review_transaction_history",
                    "rollback_available_count": 0,
                }
            }
        }
    )
    blocked_items = question_figure_transaction_task_issue_items(
        {
            "batch_apply_transaction_manifest": {
                "artifact_path": "C:/tmp/manifest.json",
                "task_summary": {
                    "status": "blocked",
                    "next_action": "resolve_manifest_blocker",
                    "rollback_available_count": 0,
                    "blockers": ["audit_history_missing"],
                },
            }
        }
    )

    assert completed_items == []
    assert len(blocked_items) == 1
    assert blocked_items[0].severity == "error"
    assert blocked_items[0].blocking is True
    assert any("audit_history_missing" in detail for detail in blocked_items[0].details)


def test_question_figure_repair_queue_issue_items_keep_conflicts_as_row_route():
    target_key = json.dumps(
        {
            "role": "question_figure",
            "item_id": "question_figure_2",
            "question_index": "2",
            "path": "current_question_2.png",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    items = question_figure_repair_queue_issue_items(
        {
            "kind": "question_figure_repair_queue",
            "status": "conflict",
            "queue_count": 1,
            "conflict_group_count": 1,
            "conflict_count": 2,
            "entries": [
                {
                    "queue_id": "repair:question_figure:exam_a:q2:conflict-a",
                    "status": "candidate",
                    "profile_id": "exam_a",
                    "profile_name": "Exam A",
                    "question_index": "2",
                    "comparison_display_name": "question_2_expected_a.png",
                    "repair_target_type": "question_figure_item",
                    "repair_target_key": target_key,
                    "requires_user_confirmation": True,
                    "auto_apply_supported": False,
                    "confirmation_action": (
                        "resolve_question_figure_replacement_conflict"
                    ),
                    "confirmation_apply_supported": False,
                    "confirmation_status": "conflict",
                    "conflict_group_id": "repair-conflict:1:abc",
                    "conflict_candidate_count": 2,
                    "apply_blockers": ["candidate_conflict_same_repair_target"],
                }
            ],
        }
    )

    assert len(items) == 1
    item = items[0]
    assert any("确认替换：不可用" in detail for detail in item.details)
    assert any("确认状态：conflict" in detail for detail in item.details)
    assert any(
        "candidate_conflict_same_repair_target" in detail
        for detail in item.details
    )
    action_type, action_payload = workbench_issue_action_target(item)

    assert action_type == "profile_question_figure_item"
    action_data = json.loads(action_payload)
    assert action_data["profile_id"] == "exam_a"
    assert json.loads(action_data["target_key"])["question_index"] == "2"


def test_question_figure_repair_queue_issue_items_route_conflict_selection_action():
    target_key = json.dumps(
        {
            "role": "question_figure",
            "item_id": "question_figure_2",
            "question_index": "2",
            "path": "current_question_2.png",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    items = question_figure_repair_queue_issue_items(
        {
            "kind": "question_figure_repair_queue",
            "status": "conflict",
            "queue_count": 2,
            "conflict_group_count": 1,
            "conflict_count": 2,
            "entries": [
                {
                    "queue_id": "repair:question_figure:exam_a:q2:conflict-a",
                    "status": "candidate",
                    "profile_id": "exam_a",
                    "profile_name": "Exam A",
                    "question_index": "2",
                    "comparison_display_name": "question_2_expected_a.png",
                    "repair_target_type": "question_figure_item",
                    "repair_target_key": target_key,
                    "requires_user_confirmation": True,
                    "auto_apply_supported": False,
                    "confirmation_action": (
                        "resolve_question_figure_replacement_conflict"
                    ),
                    "confirmation_apply_supported": False,
                    "confirmation_status": "conflict",
                    "replacement_source_path": "C:/tmp/question_2_expected_a.png",
                    "replacement_source_kind": "local_file",
                    "conflict_group_id": "repair-conflict:1:abc",
                    "conflict_candidate_count": 2,
                    "conflict_candidate_queue_ids": [
                        "repair:question_figure:exam_a:q2:conflict-a",
                        "repair:question_figure:exam_a:q2:conflict-b",
                    ],
                    "conflict_resolution_select_supported": True,
                    "conflict_resolution_action": (
                        "select_question_figure_replacement_conflict_candidate"
                    ),
                    "apply_blockers": ["candidate_conflict_same_repair_target"],
                },
                {
                    "queue_id": "repair:question_figure:exam_a:q2:conflict-b",
                    "status": "candidate",
                    "profile_id": "exam_a",
                    "profile_name": "Exam A",
                    "question_index": "2",
                    "comparison_display_name": "question_2_expected_b.png",
                    "repair_target_type": "question_figure_item",
                    "repair_target_key": target_key,
                    "confirmation_action": (
                        "resolve_question_figure_replacement_conflict"
                    ),
                    "confirmation_apply_supported": False,
                    "confirmation_status": "conflict",
                    "replacement_source_path": "C:/tmp/question_2_expected_b.png",
                    "replacement_source_kind": "local_file",
                    "conflict_group_id": "repair-conflict:1:abc",
                    "conflict_candidate_count": 2,
                    "conflict_candidate_queue_ids": [
                        "repair:question_figure:exam_a:q2:conflict-a",
                        "repair:question_figure:exam_a:q2:conflict-b",
                    ],
                    "conflict_resolution_select_supported": True,
                    "conflict_resolution_action": (
                        "select_question_figure_replacement_conflict_candidate"
                    ),
                    "apply_blockers": ["candidate_conflict_same_repair_target"],
                },
            ],
        }
    )

    item = items[0]
    assert any("可选择此候选" in detail for detail in item.details)
    assert any("同组候选：" in detail for detail in item.details)
    action_type, action_payload = workbench_issue_action_target(item)

    assert action_type == "profile_question_figure_repair_conflict_selection"
    action_data = json.loads(action_payload)
    candidate = action_data["candidate"]
    assert action_data["profile_id"] == "exam_a"
    assert candidate["queue_id"] == "repair:question_figure:exam_a:q2:conflict-a"
    assert candidate["confirmation_status"] == "ready"
    assert candidate["confirmation_apply_supported"] is True
    assert candidate["confirmation_action"] == "confirm_question_figure_replacement"
    assert candidate["conflict_resolution_status"] == "selected"
    assert candidate["conflict_selected_queue_id"] == candidate["queue_id"]
    assert candidate["conflict_resolution_rejected_queue_ids"] == [
        "repair:question_figure:exam_a:q2:conflict-b"
    ]
    assert candidate["apply_blockers"] == []


def test_question_figure_repair_queue_issue_items_route_resolved_conflict_selection():
    target_key = json.dumps(
        {
            "role": "question_figure",
            "item_id": "question_figure_2",
            "question_index": "2",
            "path": "C:/tmp/question_2.png",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    selected_candidate = {
        "queue_id": "repair:question_figure:exam_a:q2:selected",
        "kind": "question_figure_repair_candidate",
        "status": "candidate",
        "profile_id": "exam_a",
        "profile_name": "Exam A",
        "question_index": "2",
        "repair_target_type": "question_figure_item",
        "repair_target_key": target_key,
        "auto_apply_supported": False,
        "requires_user_confirmation": True,
        "confirmation_apply_supported": True,
        "confirmation_status": "ready",
        "confirmation_action": "confirm_question_figure_replacement",
        "replacement_source_path": "C:/tmp/question_2_expected_b.png",
        "conflict_group_id": "repair-conflict:1:abc",
        "conflict_resolution_status": "selected",
        "conflict_resolution_note": "choose clearer reference",
        "apply_blockers": [],
    }
    rejected_candidate = {
        "queue_id": "repair:question_figure:exam_a:q2:rejected",
        "kind": "question_figure_repair_candidate",
        "status": "rejected",
        "profile_id": "exam_a",
        "profile_name": "Exam A",
        "question_index": "2",
        "repair_target_type": "question_figure_item",
        "repair_target_key": target_key,
        "auto_apply_supported": False,
        "requires_user_confirmation": True,
        "confirmation_apply_supported": False,
        "confirmation_status": "rejected",
        "confirmation_action": "review_question_figure_replacement",
        "replacement_source_path": "C:/tmp/question_2_expected_a.png",
        "conflict_group_id": "repair-conflict:1:abc",
        "conflict_resolution_status": "rejected",
        "conflict_resolution_note": "choose clearer reference",
        "apply_blockers": ["candidate_rejected_by_conflict_resolution"],
    }

    items = question_figure_repair_queue_issue_items(
        {
            "kind": "question_figure_repair_queue",
            "status": "queued",
            "queue_count": 2,
            "conflict_group_count": 0,
            "conflict_count": 0,
            "entries": [selected_candidate, rejected_candidate],
        }
    )

    selected_item = next(
        item
        for item in items
        if item.issue_id == "repair:question_figure:exam_a:q2:selected"
    )
    rejected_item = next(
        item
        for item in items
        if item.issue_id == "repair:question_figure:exam_a:q2:rejected"
    )
    assert any("selected" in detail for detail in selected_item.details)
    assert any("rejected" in detail for detail in rejected_item.details)
    assert any("choose clearer reference" in detail for detail in selected_item.details)

    action_type, action_payload = workbench_issue_action_target(selected_item)
    assert action_type == "profile_question_figure_repair_candidate"
    action_data = json.loads(action_payload)
    assert action_data["profile_id"] == "exam_a"
    assert action_data["candidate"]["queue_id"] == selected_candidate["queue_id"]
    assert action_data["candidate"]["confirmation_status"] == "ready"

    rejected_action_type, rejected_action_payload = workbench_issue_action_target(
        rejected_item
    )
    assert rejected_action_type == "profile_question_figure_item"
    rejected_action_data = json.loads(rejected_action_payload)
    assert json.loads(rejected_action_data["target_key"])["question_index"] == "2"


def test_execution_adapter_preserves_material_field_consistency_summary():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="success",
        output_path="C:/tmp/out.docx",
        report_paths=["C:/tmp/report.json"],
        failed_count=0,
        error_text="",
        material_field_consistency={
            "schema_id": "contract_parties_v1",
            "family_id": "contract_delivery",
            "status": "warning",
            "field_count": 4,
            "issue_count": 1,
            "items": [],
            "issues": [{"kind": "label_value_conflict"}],
        },
    )
    recent = adapter.build_recent_run_state(state)

    assert state.material_field_consistency["schema_id"] == "contract_parties_v1"
    assert "字段一致性：contract_parties_v1 · 1 项风险" == (
        state.material_field_consistency_summary
    )
    assert recent.material_field_consistency == state.material_field_consistency
    assert recent.material_field_consistency_summary == state.material_field_consistency_summary


def test_execution_adapter_preserves_object_preflight_summary():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="success",
        output_path="C:/tmp/out.docx",
        report_paths=["C:/tmp/report.json"],
        failed_count=0,
        error_text="",
        object_preflight={
            "enabled": True,
            "preservation_mode": "warn",
            "scan_targets": ["ole_objects", "fields"],
            "findings_count": 2,
            "findings": [
                {
                    "kind": "ole_objects",
                    "severity": "warning",
                    "location": "word/document.xml",
                    "message": "OLE object markup is present.",
                },
                {
                    "kind": "fields",
                    "severity": "warning",
                    "location": "word/header1.xml",
                    "message": "Word field instructions are present.",
                },
            ],
            "module_skips_count": 1,
            "module_skips": [
                {
                    "module_name": "section_format",
                    "finding_kinds": ["ole_objects"],
                    "reason": "High-risk objects require preservation.",
                }
            ],
        },
    )
    recent = adapter.build_recent_run_state(state)

    assert state.object_preflight["findings_count"] == 2
    assert state.object_preflight_summary == "对象预检：2 项风险 · 跳过 1 个模块"
    assert state.object_preflight_details == [
        "风险[warning] ole_objects @ word/document.xml: OLE object markup is present.",
        "风险[warning] fields @ word/header1.xml: Word field instructions are present.",
        "跳过模块 section_format <- ole_objects: High-risk objects require preservation.",
    ]
    assert recent.object_preflight == state.object_preflight
    assert recent.object_preflight_summary == state.object_preflight_summary
    assert recent.object_preflight_details == state.object_preflight_details


def test_object_preflight_issue_items_expose_risks_for_workbench_queue():
    items = object_preflight_issue_items(
        {
            "enabled": True,
            "preservation_mode": "strict",
            "scan_targets": ["comments", "fields"],
            "findings_count": 2,
            "blocking_findings_count": 1,
            "findings": [
                {
                    "kind": "comments",
                    "severity": "warning",
                    "location": "word/comments.xml",
                    "message": "Comments are present.",
                },
                {
                    "kind": "macros",
                    "severity": "error",
                    "location": "word/vbaProject.bin",
                    "message": "Macros are present.",
                },
            ],
            "module_skips_count": 1,
            "module_skips": [
                {
                    "module_name": "section_format",
                    "finding_kinds": ["macros"],
                    "reason": "protected object",
                }
            ],
        }
    )

    assert len(items) == 2
    comments_item, macros_item = items
    assert comments_item.issue_id == "object_preflight.finding.1.comments"
    assert comments_item.category == "object_preflight"
    assert comments_item.severity == "warning"
    assert comments_item.blocking is False
    assert comments_item.repair_target_key == "comments@word/comments.xml"
    assert comments_item.summary == "word/comments.xml: Comments are present."

    assert macros_item.issue_id == "object_preflight.finding.2.macros"
    assert macros_item.category == "object_preflight"
    assert macros_item.severity == "error"
    assert macros_item.blocking is True
    assert macros_item.repair_target_type == "object_preflight"
    assert macros_item.repair_target_key == "macros@word/vbaProject.bin"
    assert macros_item.summary == "word/vbaProject.bin: Macros are present."
    assert "风险[error] macros @ word/vbaProject.bin: Macros are present." in macros_item.details
    assert "跳过模块 section_format <- macros: protected object" in macros_item.details
    assert "保护模式：strict" in macros_item.source_notes
    assert "扫描对象：comments, fields" in macros_item.source_notes


def test_execution_adapter_builds_recent_run_state_from_result():
    adapter = WorkbenchExecutionAdapter()
    result_state = adapter.build_result_state(
        status="partial_success",
        output_path="C:/tmp/out.docx",
        report_paths=["C:/tmp/report.json"],
        failed_count=2,
        error_text="",
    )

    recent = adapter.build_recent_run_state(result_state)

    assert isinstance(recent, RecentRunState)
    assert recent.status == "partial_success"
    assert "2" in recent.summary
    assert recent.output_label.endswith("out.docx")
    assert recent.title == "最近结果"


def test_execution_adapter_preserves_delivery_artifact_paths():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="success",
        output_path="C:/tmp/out.docx",
        output_paths={"final": "C:/tmp/out.docx", "review": "C:/tmp/review.docx"},
        compare_paths={"review": "C:/tmp/review_compare.docx"},
        report_paths=["C:/tmp/source_review_changes.md"],
        intermediate_paths={"review": "C:/tmp/review_intermediate.json"},
        material_manifest_paths={"material": "C:/tmp/material_manifest.json"},
        material_package_paths={
            "zip": "C:/tmp/material_package.zip",
            "report": "C:/tmp/archive_report.md",
        },
        failed_count=0,
        error_text="",
    )
    recent = adapter.build_recent_run_state(state)

    assert state.output_paths["review"].endswith("review.docx")
    assert state.compare_paths["review"].endswith("review_compare.docx")
    assert state.intermediate_paths["review"].endswith("review_intermediate.json")
    assert state.material_manifest_paths["material"].endswith("material_manifest.json")
    assert state.material_package_paths["zip"].endswith("material_package.zip")
    assert [item.kind for item in state.artifact_items] == [
        "output",
        "output",
        "compare",
        "report",
        "intermediate",
        "material_manifest",
        "material_package",
        "material_package_report",
    ]
    assert state.artifact_items[1].group_id == "review"
    assert state.artifact_items[2].group_id == "review"
    assert state.artifact_items[3].group_id == "review"
    assert state.artifact_items[0].label == "最终 Word"
    assert state.artifact_items[1].label == "审阅稿"
    assert state.artifact_items[1].group_label == "审阅稿"
    assert state.artifact_items[3].group_label == "审阅稿"
    assert "审阅稿: C:/tmp/review.docx" in recent.output_label
    assert recent.compare_label == "审阅稿: C:/tmp/review_compare.docx"
    assert recent.intermediate_label == "审阅稿: C:/tmp/review_intermediate.json"
    assert recent.material_manifest_label == "material: C:/tmp/material_manifest.json"
    assert recent.material_package_label == (
        "zip: C:/tmp/material_package.zip, report: C:/tmp/archive_report.md"
    )
    package_report = next(
        item for item in state.artifact_items if item.kind == "material_package_report"
    )
    assert package_report.path == "C:/tmp/archive_report.md"
    assert package_report.fragment == "remote-asset-cache"
    assert package_report.detail == "Remote Asset Cache"
    assert "输出[审阅稿]: C:/tmp/review.docx" in recent.artifact_label
    assert [item.kind for item in recent.artifact_items] == [
        "output",
        "output",
        "compare",
        "report",
        "intermediate",
        "material_manifest",
        "material_package",
        "material_package_report",
    ]


def test_execution_adapter_recent_run_uses_shared_delivery_display_name_for_standard_ids():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="success",
        output_path="C:/tmp/answer.docx",
        output_paths={"answer_key": "C:/tmp/answer.docx"},
        compare_paths={"answer_key": "C:/tmp/answer_compare.docx"},
        report_paths=[],
        intermediate_paths={"answer_key": "C:/tmp/answer_intermediate.json"},
        failed_count=0,
        error_text="",
    )
    recent = adapter.build_recent_run_state(state)

    assert state.output_paths == {"answer_key": "C:/tmp/answer.docx"}
    assert recent.output_label == "答案速查: C:/tmp/answer.docx"
    assert recent.compare_label == "答案速查: C:/tmp/answer_compare.docx"
    assert recent.intermediate_label == "答案速查: C:/tmp/answer_intermediate.json"
    assert recent.artifact_items[0].group_id == "answer_key"
    assert recent.artifact_items[0].label == "答案速查"
    assert recent.artifact_items[0].group_label == "答案速查"


def test_execution_adapter_labels_exam_student_and_answer_key_outputs():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="success",
        output_path="C:/tmp/student.docx",
        output_paths={
            "student": "C:/tmp/student.docx",
            "answer_key": "C:/tmp/answer.docx",
        },
        compare_paths={},
        report_paths=[],
        intermediate_paths={},
        failed_count=0,
        error_text="",
    )
    recent = adapter.build_recent_run_state(state)

    assert "学生卷: C:/tmp/student.docx" in recent.output_label
    assert "答案速查: C:/tmp/answer.docx" in recent.output_label
    assert [item.label for item in recent.artifact_items[:2]] == ["学生卷", "答案速查"]


def test_execution_adapter_exposes_scene_sample_manifest_artifact(tmp_path):
    adapter = WorkbenchExecutionAdapter()
    manifest_path = tmp_path / "scene_sample_fixtures" / "manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text('{"artifact_count": 12}', encoding="utf-8")

    state = adapter.build_result_state(
        status="success",
        output_path="C:/tmp/out.docx",
        report_paths=[],
        failed_count=0,
        error_text="",
        scene_sample_manifest_paths={"fixture_manifest": str(manifest_path)},
    )
    recent = adapter.build_recent_run_state(state)

    assert state.scene_sample_manifest_paths == {
        "fixture_manifest": str(manifest_path)
    }
    sample_items = [
        item for item in state.artifact_items if item.kind == "scene_sample_manifest"
    ]
    assert len(sample_items) == 1
    assert sample_items[0].label == "fixture_manifest"
    assert sample_items[0].group_id == "scene_samples"
    assert sample_items[0].group_label == "样本库"
    assert sample_items[0].path == str(manifest_path)
    assert recent.scene_sample_manifest_label == f"fixture_manifest: {manifest_path}"
    assert "样本清单[fixture_manifest]" in recent.artifact_label


def test_execution_adapter_marks_artifact_items_with_output_preflight_warnings():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="success",
        output_path="C:/tmp/source.docx",
        output_paths={"final": "C:/tmp/source.docx"},
        report_paths=[],
        failed_count=0,
        error_text="",
        output_target_preflight={
            "items": [
                {
                    "preset_id": "final",
                    "path": "C:/tmp/source.docx",
                    "issues": [
                        {
                            "kind": "target_exists",
                            "message": "final 输出文件已存在，将被覆盖: C:/tmp/source.docx",
                        }
                    ],
                }
            ]
        },
    )
    recent = adapter.build_recent_run_state(state)

    assert state.artifact_items[0].kind == "output"
    assert state.artifact_items[0].status == "warning"
    assert "将被覆盖" in state.artifact_items[0].detail
    assert "预警" in recent.artifact_label
    assert recent.artifact_items[0].status == "warning"
    assert len(state.issue_items) == 1
    assert state.issue_items[0].issue_id == "output_target.final.warning"
    assert state.issue_items[0].category == "output_target"
    assert state.issue_items[0].repair_target_key == "final"
    assert "将被覆盖" in state.issue_items[0].summary


def test_execution_adapter_exposes_question_figure_repair_queue_artifact():
    adapter = WorkbenchExecutionAdapter()
    target_key = json.dumps(
        {
            "role": "question_figure",
            "item_id": "question_figure_2",
            "question_index": "2",
            "path": "current_question_2.png",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    state = adapter.build_result_state(
        status="partial_success",
        output_path="",
        report_paths=[
            "C:/tmp/source_batch_report.json",
            "C:/tmp/source_batch_report.md",
        ],
        failed_count=0,
        error_text="",
        question_figure_repair_queue={
            "kind": "question_figure_repair_queue",
            "queue_count": 2,
            "batch_confirmation_plan": {
                "kind": "question_figure_repair_batch_confirmation_plan",
                "status": "partial",
                "eligible_count": 1,
                "blocked_count": 1,
                "conflict_count": 0,
            },
            "batch_confirmation_freeze": {
                "kind": "question_figure_repair_batch_confirmation_freeze",
                "status": "partial_frozen",
                "frozen_candidate_count": 1,
            },
            "batch_apply_dry_run": {
                "kind": "question_figure_repair_batch_apply_dry_run",
                "status": "ready",
                "checked_candidate_count": 1,
            },
            "batch_apply_execution_plan": {
                "kind": "question_figure_repair_batch_apply_execution_plan",
                "status": "planned",
                "planned_candidate_count": 1,
            },
            "batch_apply_execution_result": {
                "kind": "question_figure_repair_batch_apply_execution_result",
                "status": "applied",
                "applied_count": 1,
                "audit_written": True,
            },
            "batch_apply_rollback_result": {
                "kind": "question_figure_repair_batch_apply_rollback_result",
                "status": "rolled_back",
                "restored_count": 1,
                "audit_written": True,
            },
            "batch_apply_transaction_manifest": {
                "kind": "question_figure_repair_batch_apply_transaction_manifest",
                "status": "tracked",
                "transaction_count": 1,
                "active_count": 0,
                "rolled_back_count": 1,
                "orphan_rollback_count": 0,
                "artifact_written": True,
                "artifact_path": (
                    "C:/tmp/question_figure_batch_apply_transaction_manifest.json"
                ),
                "report_written": True,
                "report_path": (
                    "C:/tmp/question_figure_batch_apply_transaction_manifest.md"
                ),
                "task_summary": {
                    "kind": (
                        "question_figure_repair_batch_apply_transaction_task_summary"
                    ),
                    "status": "completed",
                    "next_action": "review_transaction_history",
                    "transaction_count": 1,
                    "active_count": 0,
                    "rolled_back_count": 1,
                    "rollback_available_count": 0,
                    "latest_apply_audit_id": "apply-1",
                    "latest_rollback_audit_id": "rollback-1",
                    "report_path": (
                        "C:/tmp/question_figure_batch_apply_transaction_manifest.md"
                    ),
                },
            },
            "entries": [
                {
                    "queue_id": "repair:question_figure:exam_a:q2:abc",
                    "status": "candidate",
                    "profile_id": "exam_a",
                    "profile_name": "Exam A",
                    "question_index": "2",
                    "repair_target_type": "question_figure_item",
                    "repair_target_key": target_key,
                },
                {
                    "queue_id": "repair:question_figure:exam_b:q5:def",
                    "status": "candidate",
                },
            ],
        },
    )
    recent = adapter.build_recent_run_state(state)

    queue_item = next(
        item for item in state.artifact_items if item.kind == "question_figure_repair_queue"
    )
    assert queue_item.path == "C:/tmp/source_batch_report.md"
    assert queue_item.fragment == "question-figure-repair-queue"
    assert queue_item.status == "warning"
    assert "2" in queue_item.detail
    assert "人工确认" in queue_item.detail
    assert "自动应用关闭" in queue_item.detail
    assert "batch_plan=partial" in queue_item.detail
    assert "eligible=1" in queue_item.detail
    assert "blocked=1" in queue_item.detail
    assert "conflicts=0" in queue_item.detail
    assert "freeze=partial_frozen" in queue_item.detail
    assert "frozen=1" in queue_item.detail
    assert "dry_run=ready" in queue_item.detail
    assert "checked=1" in queue_item.detail
    assert "exec_plan=planned" in queue_item.detail
    assert "planned=1" in queue_item.detail
    assert "exec_result=applied" in queue_item.detail
    assert "applied=1" in queue_item.detail
    assert "audit=written" in queue_item.detail
    assert "rollback=rolled_back" in queue_item.detail
    assert "restored=1" in queue_item.detail
    assert "rollback_audit=written" in queue_item.detail
    assert "transaction=tracked" in queue_item.detail
    assert "tx=1" in queue_item.detail
    assert "rolled_back=1" in queue_item.detail
    assert "tx_task=completed" in queue_item.detail
    assert "rollback_available=0" in queue_item.detail
    assert "tx_artifact=written" in queue_item.detail
    assert "tx_report=written" in queue_item.detail
    transaction_item = next(
        item
        for item in state.artifact_items
        if item.kind == "question_figure_batch_apply_transaction_manifest"
    )
    assert transaction_item.path == (
        "C:/tmp/question_figure_batch_apply_transaction_manifest.json"
    )
    assert transaction_item.fragment == (
        "question-figure-batch-apply-transaction-manifest"
    )
    assert transaction_item.status == "success"
    assert "rolled_back=1" in transaction_item.detail
    transaction_report_item = next(
        item
        for item in state.artifact_items
        if item.kind == "question_figure_batch_apply_transaction_report"
    )
    assert transaction_report_item.path == (
        "C:/tmp/question_figure_batch_apply_transaction_manifest.md"
    )
    assert transaction_report_item.fragment == (
        "question-figure-batch-apply-transaction-report"
    )
    assert transaction_report_item.status == "success"
    assert "rolled_back=1" in transaction_report_item.detail
    transaction_task_item = next(
        item
        for item in state.artifact_items
        if item.kind == "question_figure_batch_apply_transaction_task_summary"
    )
    assert transaction_task_item.path == (
        "C:/tmp/question_figure_batch_apply_transaction_manifest.md"
    )
    assert transaction_task_item.fragment == (
        "question-figure-batch-apply-transaction-task-summary"
    )
    assert transaction_task_item.status == "success"
    assert "active=0" in transaction_task_item.detail
    assert "rollback_available=0" in transaction_task_item.detail
    assert recent.question_figure_repair_queue["queue_count"] == 2
    assert recent.question_figure_repair_queue["batch_confirmation_plan"][
        "eligible_count"
    ] == 1
    assert any(
        item.kind == "question_figure_repair_queue"
        for item in recent.artifact_items
    )
    assert any(
        item.kind == "question_figure_batch_apply_transaction_manifest"
        for item in recent.artifact_items
    )
    assert any(
        item.kind == "question_figure_batch_apply_transaction_report"
        for item in recent.artifact_items
    )
    assert any(
        item.kind == "question_figure_batch_apply_transaction_task_summary"
        for item in recent.artifact_items
    )
    assert "题图修复候选[candidates]" in recent.artifact_label


    queue_issue = next(
        item
        for item in state.issue_items
        if item.category == "question_figure_repair_queue"
    )
    action_type, action_payload = workbench_issue_action_target(queue_issue)
    assert action_type == "profile_question_figure_item"
    assert json.loads(action_payload)["profile_id"] == "exam_a"


def test_output_target_preflight_issue_items_expose_output_risks_for_workbench_queue():
    items = output_target_preflight_issue_items(
        {
            "items": [
                {
                    "preset_id": "review",
                    "path": "C:/tmp/review.docx",
                    "issues": [
                        {
                            "kind": "target_exists",
                            "message": "review 输出文件已存在，将被覆盖: C:/tmp/review.docx",
                        },
                        {
                            "kind": "same_as_source",
                            "message": "review 输出路径与源文件相同",
                        },
                    ],
                },
                {
                    "preset_id": "final",
                    "path": "C:/tmp/final.docx",
                    "issues": [],
                },
            ]
        }
    )

    assert len(items) == 1
    item = items[0]
    assert item.issue_id == "output_target.review.warning"
    assert item.category == "output_target"
    assert item.severity == "warning"
    assert item.blocking is False
    assert item.repair_target_type == "output_target"
    assert item.repair_target_key == "review"
    assert item.summary == (
        "审阅稿：输出文件已存在，将被覆盖: C:/tmp/review.docx；"
        "输出路径与源文件相同"
    )
    assert item.details == (
        "输出文件已存在，将被覆盖: C:/tmp/review.docx",
        "输出路径与源文件相同",
    )
    assert item.source_notes == (
        "交付版本 ID：review",
        "输出路径：C:/tmp/review.docx",
    )


def test_execution_center_includes_diagnostics_in_summary_box():
    _app()
    center = ExecutionCenter()

    result = ExecutionResultState(
        status="success",
        summary="执行成功",
        diagnostics_count=1,
        diagnostics_summary="诊断提示（1）\n- [equation_table_format] 1 个公式编号: skipped",
    )

    center.set_result_state(result)

    assert center._summary_box.toPlainText() == (
        "执行成功\n\n诊断提示（1）\n- [equation_table_format] 1 个公式编号: skipped"
    )


def test_execution_center_includes_material_field_consistency_before_diagnostics():
    _app()
    center = ExecutionCenter()

    result = ExecutionResultState(
        status="success",
        summary="执行成功",
        diagnostics_count=1,
        diagnostics_summary="诊断提示（1）",
        material_field_consistency_summary="字段一致性：contract_parties_v1 · 1 项风险",
    )

    center.set_result_state(result)

    assert center._summary_box.toPlainText() == (
        "执行成功\n\n字段一致性：contract_parties_v1 · 1 项风险\n\n诊断提示（1）"
    )


def test_execution_center_includes_object_preflight_before_field_consistency():
    _app()
    center = ExecutionCenter()

    result = ExecutionResultState(
        status="success",
        summary="执行成功",
        object_preflight_summary="对象预检：2 项风险 · 跳过 1 个模块",
        object_preflight_details=[
            "风险[warning] comments @ word/comments.xml: Comments are present.",
            "跳过模块 section_format <- ole_objects",
        ],
        material_field_consistency_summary="字段一致性：contract_parties_v1 · 1 项风险",
    )

    center.set_result_state(result)

    assert center._summary_box.toPlainText() == (
        "执行成功\n\n对象预检：2 项风险 · 跳过 1 个模块"
        "\n- 风险[warning] comments @ word/comments.xml: Comments are present."
        "\n- 跳过模块 section_format <- ole_objects"
        "\n\n字段一致性：contract_parties_v1 · 1 项风险"
    )


def test_execution_adapter_builds_failed_result_summary():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="failed",
        output_path="C:/tmp/out.docx",
        report_paths=["C:/tmp/report.json"],
        failed_count=5,
        error_text="处理失败",
    )

    assert state.status == "failed"
    assert state.summary == "执行失败"
    assert state.error_text == "处理失败"


def test_execution_adapter_builds_cancelled_result_summary():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="cancelled",
        output_path="C:/tmp/out.docx",
        report_paths=["C:/tmp/report.json"],
        failed_count=0,
        error_text="",
    )

    assert state.status == "cancelled"
    assert state.summary == "已取消"


def test_execution_adapter_rejects_unknown_result_status():
    adapter = WorkbenchExecutionAdapter()

    with pytest.raises(ValueError):
        adapter.build_result_state(
            status="paused",
            output_path="C:/tmp/out.docx",
            report_paths=["C:/tmp/report.json"],
            failed_count=0,
            error_text="",
        )


def test_execution_adapter_builds_progress_state_with_non_positive_total_steps():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_progress_state(
        stage_text="阶段",
        current_step=3,
        total_steps=-4,
    )

    assert state.stage_text == "阶段"
    assert state.current_step == 0
    assert state.total_steps == 0
    assert state.percent == 0


def test_execution_adapter_builds_progress_state_clamps_to_one_hundred_percent():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_progress_state(
        stage_text="阶段",
        current_step=15,
        total_steps=10,
    )

    assert state.stage_text == "阶段"
    assert state.current_step == 10
    assert state.total_steps == 10
    assert state.percent == 100
