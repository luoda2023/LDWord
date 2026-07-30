import sys
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.config.material_context import MaterialExecutionContext
from src.config.object_preflight_evidence import build_object_preflight_evidence
from src.config.materials import AssetItem
from src.config.scene import ExamPaperConfig, InputSourceProfile, SceneWorkspace
from src.config.scene_sample_fixture_registry import SceneSampleFixtureAuditIssue
from src.config.template import TemplateConfig
from src.shared.engine.material_timeline import default_timeline_plan
from src.shared.ui.style_management_block import StyleManagementBlock
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.style_receipt_slot_frame import StyleReceiptSlotFrame
from src.ui.adapters.workbench_execution_adapter import (
    WorkbenchExecutionAdapter,
    batch_execution_issue_items,
    execution_diagnostic_issue_items,
    output_target_preflight_issue_items,
    question_figure_repair_queue_issue_items,
    question_figure_transaction_task_issue_items,
)
from src.ui.adapters.workbench_boundary_issues import (
    coverage_boundary_issue_items,
    sample_fixture_issue_items,
)
from src.ui.adapters.workbench_issue_models import WorkbenchIssueItem
from src.ui.adapters.workbench_issue_projection import (
    workbench_issue_action_target,
    workbench_issue_display_text,
    workbench_issue_evidence_actions,
    workbench_issue_evidence_body_text,
    workbench_issue_evidence_lines,
    workbench_issue_source_note_label,
)
from src.ui.adapters.workbench_material_issues import (
    material_asset_comparison_issue_items,
    material_readiness_issue_groups,
    material_readiness_issue_items,
    material_readiness_reasons,
    material_schema_readiness_reasons,
)
from src.ui.panels.workbench.execution_center import ExecutionCenter
from src.services.production_runtime.execution_runtime import (
    WorkbenchProductionRunner,
)
from src.services.execution_session import (
    build_execution_session_snapshot,
    cleanup_execution_session_resources,
)
from src.services.production_runtime.batch_reporting import (
    build_batch_issue_items_for_result,
)
from src.services.production_runtime import material_preflight_reporting
from src.config.scene_presets import create_bidding_scene
from src.ui.panels.workbench.state import (
    ExecutionProgressState,
    ExecutionResultState,
    ReadinessState,
    RecentRunState,
)


def _app():
    return QApplication.instance() or QApplication([])


def _build_exam_execution_session(
    *,
    scene: SceneWorkspace,
    template: TemplateConfig,
    input_path: Path,
    output_root: Path,
    material_context: MaterialExecutionContext | None = None,
):
    context = material_context or MaterialExecutionContext(mode_id="exam")
    evidence = build_object_preflight_evidence(scene, input_path)
    return build_execution_session_snapshot(
        mode_id="exam",
        scene=scene,
        template=template,
        material_context=context,
        input_path=input_path,
        output_root=output_root,
        plan_id="exam",
        template_id="default",
        object_preflight_confirmation_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )


def test_execution_center_routes_style_receipt_through_style_object_projection():
    source = (ROOT / "src/ui/panels/workbench/execution_center.py").read_text(
        encoding="utf-8"
    )

    assert "build_execution_style_projection" in source
    assert "apply_style_object_projection(style_projection)" in source
    assert "effective_style_source_envelope" not in source
    assert "_style_receipt_slot.apply_envelope" not in source


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
        "receipt"
    )
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
    assert item.severity == "warning"
    assert item.blocking is False
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


def test_workbench_issue_evidence_projection_keeps_ui_semantics_in_owner():
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


def test_sample_fixture_issue_items_keep_structured_repair_target():
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


def test_coverage_boundary_issue_items_expose_contract_legal_boundary():
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
        "方案字段：company_name, project_name, legal_person",
        "方案资产：logo, seal",
        "当前资料：未配置",
    )
    assert groups.detail_lines() == [
        "字段：company_name, project_name, legal_person",
        "资产：logo, seal",
        "来源：Schema：Bidding materials (bid_materials_v1)",
        "来源：方案字段：company_name, project_name, legal_person",
        "来源：方案资产：logo, seal",
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


def test_material_readiness_blocks_package_schema_mismatch_before_session_build():
    scene = create_bidding_scene()
    context = MaterialExecutionContext(
        package_id="wrong-package",
        material_schema_ids=("official_document_v1",),
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

    groups = material_readiness_issue_groups(scene, context)
    items = material_readiness_issue_items(scene, context)

    assert groups.incompatible_schema_ids == ("official_document_v1",)
    assert groups.field_keys == ()
    assert groups.asset_roles == ()
    assert material_readiness_reasons(scene, context) == [
        "资料包 Schema 与当前方案不兼容：official_document_v1"
    ]
    assert [item.issue_id for item in items] == [
        "material.schema.incompatible"
    ]
    assert items[0].blocking is True
    assert items[0].repair_target_type == "material_package"


def test_material_readiness_blocks_named_package_without_schema_declaration():
    scene = create_bidding_scene()
    context = MaterialExecutionContext(
        package_id="legacy-package",
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

    groups = material_readiness_issue_groups(scene, context)

    assert groups.incompatible_schema_ids == ("未声明",)
    assert "资料包 Schema：未声明" in groups.source_notes


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
            summary="本次使用模板“默认格式”。",
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
        "receipt"
    )
    assert center._style_receipt_row.isHidden() is False
    assert center._style_receipt_row.summary_text() == (
        "样式来源：本次使用模板“默认格式”。"
    )
    assert center._style_receipt_row.property("style_presentation_kind") == (
        "execution_receipt"
    )
    assert center._style_receipt_row.detail.text() == (
        "本次使用模板“默认格式”。"
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
    assert center._style_receipt_row.isHidden() is True
    assert center._style_receipt_block.isHidden() is True
    assert center._style_receipt_block.property("style_object_kind") == "execution_style"


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
        terminal_payload={
            "status": "success",
            "output_path": "C:/tmp/out.docx",
            "report_paths": ["C:/tmp/report.json", "C:/tmp/report.md"],
            "failed_count": 0,
            "error_text": "",
            "diagnostics_count": 1,
            "diagnostics_summary": "诊断提示（1）\n- [equation_table_format] 1 个公式编号: skipped",
            "style_source": {
                "template_label": "默认格式",
                "summary": "本次使用模板“默认格式”。",
            },
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
        "样式来源：本次使用模板“默认格式”。"
    )
    assert state.style_source_envelope.kind == "execution_receipt"
    assert state.style_source_envelope.receipt_summary(title_fallback="样式来源") == (
        state.style_source_summary
    )
    recent = adapter.build_recent_run_state(state)
    assert recent.style_source_summary == state.style_source_summary
    assert recent.style_source_envelope == state.style_source_envelope


def test_execution_adapter_separates_artifact_failures_from_business_failures():
    state = WorkbenchExecutionAdapter().build_result_state(
        terminal_payload={
            "status": "partial_success",
            "output_path": "out.docx",
            "report_paths": [],
            "failed_count": 0,
            "artifact_failure_count": 1,
            "error_text": "report write failed",
        },
    )

    assert state.failed_count == 0
    assert state.artifact_failure_count == 1
    assert "辅助产物" in state.summary
    assert "0 个模块" not in state.summary


def test_execution_adapter_converts_batch_issue_payloads_to_workbench_issues():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        terminal_payload={
            "status": "partial_success",
            "output_path": "",
            "report_paths": ["C:/tmp/batch_report.json"],
            "failed_count": 1,
            "error_text": "",
            "batch_isolation": {
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
            "batch_issue_items": [
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
        },
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
                "kind": "scene_document_scope_diagnostic",
                "summary": "方案处理范围需要确认",
                "parameter_path": "scene.document_scope.mode",
            },
            {
                "profile_id": "thesis_a",
                "profile_name": "论文 A",
                "kind": "scene_document_scope_roles_diagnostic",
                "summary": "指定区域需要确认",
                "parameter_paths": ["scene.document_scope.selected_roles"],
            },
        ]
    )

    mode_item, roles_item = items
    for item, target in (
        (mode_item, "scene.document_scope.mode"),
        (roles_item, "scene.document_scope.selected_roles"),
    ):
        assert item.category == "batch_issue"
        assert item.repair_target_type == "scene_document_scope_field"
        assert item.repair_target_key == target
        assert f"参数路径：{target}" in item.details
        assert workbench_issue_action_target(item) == (
            "scene_document_scope_field",
            target,
        )


def test_workbench_execution_adapter_uses_only_current_issue_model():
    adapter_source = (ROOT / "src/ui/adapters/workbench_execution_adapter.py").read_text(
        encoding="utf-8"
    )
    model_source = (ROOT / "src/ui/adapters/workbench_issue_models.py").read_text(
        encoding="utf-8"
    )

    assert "from src.ui.adapters.workbench_issue_models import" in adapter_source
    assert "class WorkbenchIssueItem" not in adapter_source
    assert "class MaterialReadinessIssueGroups" in model_source
    assert "class WorkbenchIssueItem" in model_source
    assert "class WorkbenchIssueQueueSummary" not in model_source
    assert "ISSUE_STATUS_VALUES" not in model_source
    assert "ISSUE_TERMINAL_STATUS_VALUES" in model_source


def test_workbench_issue_projection_owns_issue_actions_without_adapter_reexport():
    adapter_source = (ROOT / "src/ui/adapters/workbench_execution_adapter.py").read_text(
        encoding="utf-8"
    )
    projection_source = (
        ROOT / "src/ui/adapters/workbench_issue_projection.py"
    ).read_text(encoding="utf-8")

    assert "from src.ui.adapters.workbench_issue_projection import" not in adapter_source
    assert "COVERAGE_PACK_DISPLAY_LABELS =" not in adapter_source
    assert "BOUNDARY_TEXT_DISPLAY_LABELS =" not in adapter_source
    assert "COVERAGE_PACK_DISPLAY_LABELS =" in projection_source
    assert "BOUNDARY_TEXT_DISPLAY_LABELS =" in projection_source
    for function_name in (
        "workbench_issue_action_target",
        "workbench_issue_action_visual",
        "workbench_issue_evidence_lines",
        "workbench_issue_evidence_actions",
        "workbench_issue_evidence_body_text",
        "workbench_issue_display_text",
        "workbench_issue_source_note_label",
    ):
        assert f"def {function_name}(" not in adapter_source
        assert f"def {function_name}(" in projection_source


def test_boundary_issue_family_has_no_execution_adapter_reexport():
    adapter_source = (ROOT / "src/ui/adapters/workbench_execution_adapter.py").read_text(
        encoding="utf-8"
    )
    boundary_source = (
        ROOT / "src/ui/adapters/workbench_boundary_issues.py"
    ).read_text(encoding="utf-8")

    assert "from src.ui.adapters.workbench_boundary_issues import" not in adapter_source
    for function_name in (
        "coverage_boundary_issue_items",
        "sample_fixture_issue_items",
    ):
        assert f"def {function_name}(" not in adapter_source
        assert f"def {function_name}(" in boundary_source
    for helper_name in (
        "_coverage_packs_for_scene_context",
        "_coverage_boundary_details",
        "_sample_fixture_issue",
        "_sample_fixture_issue_pack_id",
    ):
        assert f"def {helper_name}(" not in adapter_source
        assert f"def {helper_name}(" in boundary_source


def test_material_issue_family_has_no_execution_adapter_reexport():
    adapter_source = (ROOT / "src/ui/adapters/workbench_execution_adapter.py").read_text(
        encoding="utf-8"
    )
    material_source = (
        ROOT / "src/ui/adapters/workbench_material_issues.py"
    ).read_text(encoding="utf-8")

    assert "from src.ui.adapters.workbench_material_issues import" not in adapter_source
    for function_name in (
        "material_schema_readiness_reasons",
        "material_readiness_reasons",
        "material_readiness_issue_items",
        "material_asset_comparison_issue_items",
        "material_readiness_issue_groups",
    ):
        assert f"def {function_name}(" not in adapter_source
        assert f"def {function_name}(" in material_source
    for helper_name in (
        "_missing_scene_material_schema_ids",
        "_scene_material_schema_ids",
        "_material_context_asset_roles",
        "_material_source_notes",
    ):
        assert f"def {helper_name}(" not in adapter_source
        assert f"def {helper_name}(" in material_source


def test_execution_diagnostic_issue_items_infer_scene_field_targets():
    items = execution_diagnostic_issue_items(
        [
            {
                "rule_name": "document_scope",
                "change_type": "preflight_document_scope",
                "reason": "处理范围需要确认",
                "parameter_path": "scene.document_scope.mode",
            },
            {
                "rule_name": "document_scope",
                "change_type": "preflight_document_scope_roles",
                "reason": "指定区域需要确认",
                "parameter_paths": ["scene.document_scope.selected_roles"],
            },
            {
                "rule_name": "plain_warning",
                "change_type": "skip",
                "reason": "没有可定位字段",
            },
        ]
    )

    assert len(items) == 2
    for item, target in zip(
        items,
        ("scene.document_scope.mode", "scene.document_scope.selected_roles"),
    ):
        assert item.category == "scene_document_scope"
        assert item.title == "方案处理范围需要确认"
        assert item.owner == "scene"
        assert item.repair_target_type == "scene_document_scope_field"
        assert item.repair_target_key == target
        assert f"参数路径：{target}" in item.details
        assert workbench_issue_action_target(item) == (
            "scene_document_scope_field",
            target,
        )


def test_result_state_includes_routable_execution_diagnostic_issues():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        terminal_payload={
            "status": "success",
            "output_path": "out.docx",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
            "diagnostics_count": 1,
            "diagnostics_summary": "诊断提示（1）",
            "diagnostics_items": [
                {
                    "rule_name": "document_scope",
                    "reason": "指定区域需要确认",
                    "parameter_path": "scene.document_scope.selected_roles",
                }
            ],
        },
    )

    assert len(state.issue_items) == 1
    item = state.issue_items[0]
    assert item.category == "scene_document_scope"
    assert item.repair_target_type == "scene_document_scope_field"
    assert item.repair_target_key == "scene.document_scope.selected_roles"


def test_runtime_batch_issue_payload_preserves_scene_parameter_paths():
    payloads = build_batch_issue_items_for_result(
        {
            "profile_id": "thesis_a",
            "profile_name": "论文 A",
            "status": "partial_success",
            "material_diagnostics": [
                {
                    "change_type": "scene_document_scope_diagnostic",
                    "reason": "方案处理范围需要确认",
                    "level": "warning",
                    "parameter_path": "scene.document_scope.mode",
                }
            ],
        }
    )

    assert len(payloads) == 1
    assert payloads[0]["parameter_paths"] == [
        "scene.document_scope.mode"
    ]

    item = batch_execution_issue_items(payloads)[0]
    assert item.repair_target_type == "scene_document_scope_field"
    assert item.repair_target_key == "scene.document_scope.mode"


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
        terminal_payload={
            "status": "success",
            "output_path": "C:/tmp/out.docx",
            "report_paths": ["C:/tmp/report.json"],
            "failed_count": 0,
            "error_text": "",
            "material_field_consistency": {
                "schema_id": "contract_parties_v1",
                "family_id": "contract_delivery",
                "status": "warning",
                "field_count": 4,
                "issue_count": 1,
                "items": [],
                "issues": [{"kind": "label_value_conflict"}],
            },
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
        terminal_payload={
            "status": "success",
            "output_path": "C:/tmp/out.docx",
            "report_paths": ["C:/tmp/report.json"],
            "failed_count": 0,
            "error_text": "",
            "object_preflight": {
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


def test_execution_adapter_builds_recent_run_state_from_result():
    adapter = WorkbenchExecutionAdapter()
    result_state = adapter.build_result_state(
        terminal_payload={
            "status": "partial_success",
            "output_path": "C:/tmp/out.docx",
            "report_paths": ["C:/tmp/report.json"],
            "failed_count": 2,
            "error_text": "",
        },
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
        terminal_payload={
            "status": "success",
            "output_path": "C:/tmp/out.docx",
            "output_paths": {"final": "C:/tmp/out.docx", "review": "C:/tmp/review.docx"},
            "compare_paths": {"review": "C:/tmp/review_compare.docx"},
            "report_paths": ["C:/tmp/source_review_changes.md"],
            "intermediate_paths": {"review": "C:/tmp/review_intermediate.json"},
            "material_manifest_paths": {"material": "C:/tmp/material_manifest.json"},
            "material_package_paths": {
                "zip": "C:/tmp/material_package.zip",
                "report": "C:/tmp/archive_report.md",
            },
            "failed_count": 0,
            "error_text": "",
        },
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
        terminal_payload={
            "status": "success",
            "output_path": "C:/tmp/answer.docx",
            "output_paths": {"answer_key": "C:/tmp/answer.docx"},
            "compare_paths": {"answer_key": "C:/tmp/answer_compare.docx"},
            "report_paths": [],
            "intermediate_paths": {"answer_key": "C:/tmp/answer_intermediate.json"},
            "failed_count": 0,
            "error_text": "",
        },
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
        terminal_payload={
            "status": "success",
            "output_path": "C:/tmp/student.docx",
            "output_paths": {
                "student": "C:/tmp/student.docx",
                "answer_key": "C:/tmp/answer.docx",
            },
            "compare_paths": {},
            "report_paths": [],
            "intermediate_paths": {},
            "failed_count": 0,
            "error_text": "",
        },
    )
    recent = adapter.build_recent_run_state(state)

    assert "学生卷: C:/tmp/student.docx" in recent.output_label
    assert "答案速查: C:/tmp/answer.docx" in recent.output_label
    assert [item.label for item in recent.artifact_items[:2]] == ["学生卷", "答案速查"]


def test_workbench_runner_executes_exam_markdown_source_without_docx_pipeline(tmp_path):
    source = tmp_path / "exam_source.md"
    source.write_text(
        """# 七年级数学单元测试

> 科目：数学　年级：七年级　考试时间：45 分钟　满分：10 分

## 一、选择题

1. 1 + 1 = （　　）（5 分）
   A. 1
   B. 2
   C. 3
   D. 4

## 二、填空题

1. 3 + 4 = ______。（5 分）

## 答案速查

一、选择题
1. B

二、填空题
1. 7
""",
        encoding="utf-8",
    )
    scene = SceneWorkspace(
        scene_id="exam",
        mode_id="exam",
        category="exam_paper",
        template_id="default",
        compatible_template_ids=["default"],
        master_id="default_exam",
        input_source_profile=InputSourceProfile(
            accepted_formats=["markdown"],
            structured_formats=["json"],
        ),
        exam_paper=ExamPaperConfig(
            answer_policy="student_plus_answer",
        ),
    )
    progress: list[tuple[int, int, str]] = []
    template = TemplateConfig()
    material_context = MaterialExecutionContext(mode_id="exam")
    execution_session = _build_exam_execution_session(
        scene=scene,
        template=template,
        input_path=source,
        output_root=tmp_path / "runs",
        material_context=material_context,
    )
    runner = WorkbenchProductionRunner(
        doc_path=str(source),
        template=template,
        scene=scene,
        output_dir=Path(execution_session.output_namespace),
        material_context=material_context,
        execution_session=execution_session,
    )

    try:
        payload = runner.run(
            lambda current, total, message: progress.append((current, total, message)),
            lambda: False,
        )
    finally:
        cleanup_execution_session_resources(execution_session)

    assert payload["status"] == "success"
    assert set(payload["output_paths"]) == {"student", "answer_key"}
    assert Path(payload["output_paths"]["student"]).exists()
    assert Path(payload["output_paths"]["answer_key"]).exists()
    assert payload["exam_markdown_import"]["summary"]["question_count"] == 2
    assert payload["exam_markdown_import"]["summary"]["answered_question_count"] == 2
    report_json = next(
        Path(path)
        for path in payload["report_paths"]
        if str(path).endswith(".json")
    )
    report_payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert report_payload["exam_markdown_import"] == payload["exam_markdown_import"]
    report_markdown = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in payload["report_paths"]
        if str(path).endswith(".md")
    )
    assert "## Markdown 题稿导入证据" in report_markdown
    assert "## 试卷题源结构校验" in report_markdown
    assert "## 试卷多版本运行时渲染" in report_markdown
    assert "Failed to open document" not in str(payload)
    assert any(message == "解析 Markdown 题稿" for *_steps, message in progress)


def test_workbench_runner_applies_block_material_policy_to_exam_markdown(tmp_path):
    source = tmp_path / "incomplete_exam_source.md"
    source.write_text(
        """# 数学练习

## 一、选择题

1. 1 + 1 = （　　）
   A. 1
   B. 2
""",
        encoding="utf-8",
    )
    scene = SceneWorkspace(
        scene_id="exam",
        mode_id="exam",
        category="exam_paper",
        template_id="default",
        compatible_template_ids=["default"],
        master_id="default_exam",
        input_source_profile=InputSourceProfile(
            accepted_formats=["markdown"],
            structured_formats=["json"],
            material_schema_id="exam_items_v1",
            failure_policy="block",
        ),
        exam_paper=ExamPaperConfig(
            answer_policy="student_only",
        ),
    )
    runner = WorkbenchProductionRunner(
        doc_path=str(source),
        template=TemplateConfig(),
        scene=scene,
        output_dir=tmp_path / "out",
    )

    payload = runner.run(lambda *_args: None, lambda: False)

    assert payload["status"] == "failed"
    assert payload["output_paths"] == {}
    assert payload["exam_markdown_import"]["summary"]["question_count"] == 1
    assert "Missing required material fields" in payload["error_text"]
    assert {
        diagnostic["change_type"]
        for diagnostic in payload["material_diagnostics"]
    } >= {"preflight_missing_material_fields"}
    report_json = next(
        Path(path)
        for path in payload["report_paths"]
        if str(path).endswith(".json")
    )
    report_payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert report_payload["exam_markdown_import"] == (
        payload["exam_markdown_import"]
    )
    report_markdown = next(
        Path(path).read_text(encoding="utf-8")
        for path in payload["report_paths"]
        if str(path).endswith(".md")
    )
    assert "## Markdown 题稿导入证据" in report_markdown


def test_exam_material_preflight_report_failure_is_isolated_and_atomic(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "incomplete_exam_source.md"
    source.write_text(
        """# 数学练习

## 一、选择题

1. 1 + 1 = （　　）
   A. 1
   B. 2
""",
        encoding="utf-8",
    )
    scene = SceneWorkspace(
        scene_id="exam",
        mode_id="exam",
        category="exam_paper",
        template_id="default",
        compatible_template_ids=["default"],
        master_id="default_exam",
        input_source_profile=InputSourceProfile(
            accepted_formats=["markdown"],
            structured_formats=["json"],
            material_schema_id="exam_items_v1",
            failure_policy="block",
        ),
        exam_paper=ExamPaperConfig(
            answer_policy="student_only",
        ),
    )
    original_atomic_write_text = material_preflight_reporting.atomic_write_text

    def _fail_markdown_stage(path, text, *, encoding="utf-8"):
        if Path(path).suffix.casefold() == ".md":
            raise OSError("simulated markdown report failure")
        return original_atomic_write_text(path, text, encoding=encoding)

    monkeypatch.setattr(
        material_preflight_reporting,
        "atomic_write_text",
        _fail_markdown_stage,
    )
    output_dir = tmp_path / "out"
    payload = WorkbenchProductionRunner(
        doc_path=str(source),
        template=TemplateConfig(),
        scene=scene,
        output_dir=output_dir,
    ).run(lambda *_args: None, lambda: False)

    assert payload["status"] == "failed"
    assert payload["exam_markdown_import"]["summary"]["question_count"] == 1
    assert payload["report_paths"] == []
    assert payload["artifact_failure_count"] >= 1
    failure = next(
        item
        for item in payload["artifact_failures"]
        if item["kind"] == "material_preflight_reports"
    )
    assert failure["error_type"] == "OSError"
    assert "simulated markdown report failure" in failure["error"]
    assert list(output_dir.glob("*_changes.json")) == []
    assert list(output_dir.glob("*_changes.md")) == []


def test_exam_markdown_block_policy_does_not_block_timeline_warning(tmp_path):
    source = tmp_path / "timeline_warning_exam.md"
    source.write_text(
        """# 数学练习

> 科目：数学　年级：七年级　考试时间：45 分钟　满分：5 分

## 一、选择题

1. 1 + 1 = （　　）（5 分）
   A. 1
   B. 2

## 答案速查

一、选择题
1. B
""",
        encoding="utf-8",
    )
    scene = SceneWorkspace(
        scene_id="exam",
        mode_id="exam",
        category="exam_paper",
        template_id="default",
        compatible_template_ids=["default"],
        master_id="default_exam",
        input_source_profile=InputSourceProfile(
            accepted_formats=["markdown"],
            structured_formats=["json"],
            material_schema_id="exam_items_v1",
            failure_policy="block",
        ),
        exam_paper=ExamPaperConfig(
            answer_policy="student_only",
        ),
    )
    plan = default_timeline_plan()
    plan["start_field"] = "timeline_start"
    plan["end_field"] = "timeline_end"
    material_context = MaterialExecutionContext(
        mode_id="exam",
        entity_data={
            "timeline_start": "2025-01-01",
            "timeline_end": "2025-01-01",
        },
        timeline_plans={"primary": plan},
    )
    template = TemplateConfig()
    execution_session = _build_exam_execution_session(
        scene=scene,
        template=template,
        input_path=source,
        output_root=tmp_path / "runs",
        material_context=material_context,
    )
    runner = WorkbenchProductionRunner(
        doc_path=str(source),
        template=template,
        scene=scene,
        output_dir=Path(execution_session.output_namespace),
        material_context=material_context,
        execution_session=execution_session,
    )

    try:
        payload = runner.run(lambda *_args: None, lambda: False)
    finally:
        cleanup_execution_session_resources(execution_session)
    timeline_diagnostics = [
        diagnostic
        for diagnostic in payload["material_diagnostics"]
        if str(diagnostic.get("change_type") or "").startswith("timeline_")
    ]

    assert payload["status"] == "success"
    assert timeline_diagnostics
    assert {diagnostic["level"] for diagnostic in timeline_diagnostics} == {"warning"}


def test_execution_adapter_exposes_scene_sample_manifest_artifact(tmp_path):
    adapter = WorkbenchExecutionAdapter()
    manifest_path = tmp_path / "scene_sample_fixtures" / "manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text('{"artifact_count": 12}', encoding="utf-8")

    state = adapter.build_result_state(
        terminal_payload={
            "status": "success",
            "output_path": "C:/tmp/out.docx",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
            "scene_sample_manifest_paths": {"fixture_manifest": str(manifest_path)},
        },
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
        terminal_payload={
            "status": "success",
            "output_path": "C:/tmp/source.docx",
            "output_paths": {"final": "C:/tmp/source.docx"},
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
            "output_target_preflight": {
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
        terminal_payload={
            "status": "partial_success",
            "output_path": "",
            "report_paths": [
                "C:/tmp/source_batch_report.json",
                "C:/tmp/source_batch_report.md",
            ],
            "failed_count": 0,
            "error_text": "",
            "question_figure_repair_queue": {
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


def test_output_target_preflight_items_preserve_result_repair_targets():
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
        terminal_payload={
            "status": "failed",
            "output_path": "C:/tmp/out.docx",
            "report_paths": ["C:/tmp/report.json"],
            "failed_count": 5,
            "error_text": "处理失败",
        },
    )

    assert state.status == "failed"
    assert state.summary == "执行失败"
    assert state.error_text == "处理失败"


def test_execution_adapter_builds_cancelled_result_summary():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        terminal_payload={
            "status": "cancelled",
            "output_path": "C:/tmp/out.docx",
            "report_paths": ["C:/tmp/report.json"],
            "failed_count": 0,
            "error_text": "",
        },
    )

    assert state.status == "cancelled"
    assert state.summary == "已取消"


def test_execution_adapter_rejects_unknown_result_status():
    adapter = WorkbenchExecutionAdapter()

    with pytest.raises(ValueError):
        adapter.build_result_state(
            terminal_payload={
                "status": "paused",
                "output_path": "C:/tmp/out.docx",
                "report_paths": ["C:/tmp/report.json"],
                "failed_count": 0,
                "error_text": "",
            },
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
