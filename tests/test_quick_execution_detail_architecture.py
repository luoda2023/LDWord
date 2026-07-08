import inspect
import sys
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QLabel, Qt
from src.config.material_context import MaterialExecutionContext
from src.config.materials import AssetItem
from src.config.scene import SceneWorkspace
from src.config.template import StyleConfig
from src.shared.ui.evidence_widgets import EvidenceActionBar, EvidenceLineList
from src.shared.ui.issue_detail_section import IssueDetailSection
from src.shared.ui.style_difference_summary_slot import StyleDifferenceSummarySlot
from src.shared.ui.style_management_block import StyleManagementBlock
from src.shared.ui.theme import get_theme
from src.shared.ui.themed_radio_button import ThemedRadioButton
from src.ui.panels.workbench.state import ArtifactItemState, ExecutionResultState
from src.ui.adapters.workbench_execution_adapter import (
    WorkbenchExecutionAdapter,
    WorkbenchIssueItem,
    coverage_boundary_issue_items,
    material_readiness_issue_items,
)
import src.ui.panels.workbench.quick_execution_detail as quick_execution_detail_module
from src.ui.panels.workbench.quick_execution_drop_area import QuickExecutionDropArea
from src.ui.panels.workbench.quick_execution_detail import QuickExecutionDetail
from src.ui.panels.workbench.scene_presets import (
    LEGACY_FEATURE_GROUP_MAP,
    build_scene_control_contract_summary,
    build_scene_parameter_ownership_summary,
    build_scene_product_readiness_summary,
    build_scene_request_cell_summary_text,
    build_scene_sample_coverage_summary_text,
    build_scene_summary,
    create_bidding_scene,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_quick_execution_detail_uses_presenter_module_for_snapshot_and_status_logic():
    detail_source = inspect.getsource(QuickExecutionDetail)
    module_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")

    assert "from .quick_execution_presenter import" in module_source
    assert "from .quick_execution_drop_area import QuickExecutionDropArea" in module_source
    assert "build_navigation_snapshot(" in detail_source
    assert "build_feature_navigation_snapshot(" in detail_source
    assert "build_ready_status(" in detail_source
    assert "build_running_status(" in detail_source


def test_quick_execution_detail_uses_dedicated_drop_area_widget():
    _app()
    detail = QuickExecutionDetail()
    try:
        assert isinstance(detail._drop_area, QuickExecutionDropArea)
        assert detail.document_path() == ""
    finally:
        detail.close()


def test_quick_execution_detail_card_spacing_uses_template_detail_gap():
    app = _app()
    detail = QuickExecutionDetail()
    try:
        detail.resize(960, 900)
        detail.show()
        app.processEvents()
        app.processEvents()

        expected_gap = get_theme().template_detail_section_gap
        assert detail.layout().spacing() == expected_gap

        widgets = [
            detail._drop_area,
            detail._scene_card,
            detail._output_card,
            detail._execution_card,
        ]
        for current, following in zip(widgets, widgets[1:]):
            assert following.y() - (current.y() + current.height()) == expected_gap
    finally:
        detail.close()
        app.processEvents()


def test_quick_execution_detail_keeps_batch_generation_out_of_execute_area():
    _app()
    source = (
        ROOT / "src/ui/panels/workbench/quick_execution_detail.py"
    ).read_text(encoding="utf-8")
    detail = QuickExecutionDetail()
    try:
        assert "wb_v2_batch_execute_btn" not in source
        assert "batch_execute_requested" not in source
        assert not hasattr(detail, "_batch_execute_btn")
        assert detail._exec_status_area.minimumHeight() == detail._execute_btn.minimumHeight()
        assert detail._exec_status_area.maximumHeight() == detail._execute_btn.maximumHeight()
    finally:
        detail.close()


def test_quick_execution_detail_uses_shared_radio_controls():
    _app()
    source = (
        ROOT / "src/ui/panels/workbench/quick_execution_detail.py"
    ).read_text(encoding="utf-8")
    detail = QuickExecutionDetail()
    try:
        assert "QRadioButton" not in source
        assert "ThemedRadioButton" in source
        assert "高级调整" not in source
        assert "结构策略" not in source
        assert not hasattr(detail, "_strategy_rebuild")
        assert not hasattr(detail, "_strategy_preserve")

        assert isinstance(detail._output_default_radio, ThemedRadioButton)
        assert isinstance(detail._output_custom_radio, ThemedRadioButton)
        assert detail._output_mode_group.exclusive() is True
        assert detail._output_default_radio.isChecked() is True

        detail._set_output_dir("C:/tmp/out")
        assert detail._output_custom_radio.isChecked() is True
        assert detail._output_default_radio.isChecked() is False
        assert detail.custom_output_dir() == "C:/tmp/out"

        detail._output_default_radio.setChecked(True)
        assert detail._output_default_radio.isChecked() is True
        assert detail._output_custom_radio.isChecked() is False
        assert detail.custom_output_dir() == ""
    finally:
        detail.close()


def test_quick_execution_detail_uses_selector_row_without_style_source_row():
    source = (
        ROOT / "src/ui/panels/workbench/quick_execution_detail.py"
    ).read_text(encoding="utf-8")
    _app()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.section_styles["references_body"] = StyleConfig()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)

        selector = detail._scene_template_selector_row
        slot = detail._style_difference_slot

        assert not hasattr(detail, "_style_source_row")
        assert not hasattr(detail, "_style_prereview_source_slot")
        assert not hasattr(detail, "_style_prereview_preview_slot")
        assert not hasattr(detail, "_style_prereview_preview")
        assert selector.objectName() == "wb_execution_prereview_selector_row"
        assert isinstance(slot, StyleDifferenceSummarySlot)
        assert isinstance(detail._scene_card, StyleManagementBlock)
        assert detail._scene_card.source_slot is selector
        assert detail._scene_card.scope_slot is selector
        assert detail._scene_card.rule_control is None
        assert detail._scene_card.difference_slot is slot
        assert detail._scene_card.preview_slot is None
        assert detail._scene_card.property("style_management_mode") == "execution_prereview"
        assert detail._scene_card.property("style_management_content_plan") == (
            "source|scope|difference"
        )
        assert detail._scene_card.property("style_management_slot_plan") == (
            "source|scope|difference"
        )
        assert detail._scene_card.property("style_management_has_source_slot") is True
        assert detail._scene_card.property("style_management_has_scope_slot") is True
        assert detail._scene_card.property("style_management_has_rules") is False
        assert detail._scene_card.property("style_management_has_policy") is False
        assert detail._scene_card.property("style_management_has_policy_slot") is False
        assert detail._scene_card.property("style_management_rule_control_protocol") == "none"
        assert detail._scene_card.property("style_management_rule_control_ready") is False
        assert detail._scene_card.property(
            "style_management_policy_control_protocol"
        ) == "none"
        assert detail._scene_card.property(
            "style_management_policy_control_ready"
        ) is False
        assert detail._scene_card.property("style_management_has_difference_slot") is True
        assert detail._scene_card.property("style_management_has_preview_slot") is False
        assert detail._scene_card.property("style_management_preview_slot_protocol") == (
            "none"
        )
        assert detail._scene_card.property("style_management_preview_slot_ready") is False
        assert detail._scene_card.effective_preview_slot is None
        assert detail._scene_card.property("style_management_effective_preview_protocol") == (
            "none"
        )
        assert detail._scene_card.property("style_management_effective_preview_ready") is False
        assert detail._scene_card.property("style_object_kind") == (
            "execution_prereview_style"
        )
        assert detail._scene_card.property("style_object_label") == "执行前复核"
        assert detail._scene_card.property("style_object_source_label") == "有格式例外"
        assert detail._scene_card.property("style_object_scope_label") == (
            "1 个格式例外：参考文献"
        )
        assert detail._scene_card.property("style_object_edit_state_label") == "只读"
        assert not hasattr(detail, "_style_prereview_policy_deck")
        assert slot.objectName() == "wb_style_difference_difference_slot"
        assert slot.property("style_difference_review_mode") == "execution_prereview"
        assert slot.isHidden() is False
        assert slot.property("style_difference_current_status") == "参考文献 独立样式"
        assert slot.property("style_difference_status") == "待比较"
        assert slot.property("style_difference_detail") == "需要模板基线后比较字段差异。"

        assert "build_execution_prereview_style_projection" in source
        assert "apply_style_object_projection(style_projection)" in source
        assert "build_style_source_projection" not in source
        assert "build_style_difference_summary_projection" not in source
        assert "_style_source_row" not in source
        assert "_style_prereview_source_slot" not in source
        assert "_on_style_source_navigation_requested" not in source
        assert "_style_difference_slot.apply_projection" not in source
        assert "StyleSourceSlot(" not in source
        assert "source_slot=self._scene_template_selector_row" in source
        assert "scope_slot=self._scene_template_selector_row" in source
        assert "StylePolicyControlDeck(" not in source
        assert "policy_selected.connect" not in source
        assert "_on_style_policy_selected" not in source
        assert "rule_control=self._style_prereview_policy_deck" not in source
        assert "StylePreviewSurface(" not in source
        assert "preview_slot=self._style_prereview_preview_slot" not in source
        assert "_style_prereview_preview" not in source
    finally:
        detail.close()


def test_quick_execution_detail_hides_style_difference_without_independent_sections():
    _app()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)

        assert isinstance(detail._style_difference_slot, StyleDifferenceSummarySlot)
        assert detail._style_difference_slot.isHidden() is True
        assert (
            detail._style_difference_slot.property("style_difference_has_projection")
            is False
        )
    finally:
        detail.close()


def test_quick_execution_detail_style_prereview_uses_summary_without_policy_or_preview():
    _app()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.section_styles["references_body"] = StyleConfig(font_cn="黑体")
    scene.section_styles["acknowledgment_body"] = StyleConfig(font_cn="楷体")
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)

        assert not hasattr(detail, "_style_source_row")
        assert not hasattr(detail, "_style_prereview_source_slot")
        assert not hasattr(detail, "_style_prereview_policy_deck")
        assert not hasattr(detail, "_style_prereview_preview_slot")
        assert not hasattr(detail, "_style_prereview_preview")
        assert detail._scene_card.property("style_management_has_policy") is False
        assert detail._scene_card.property("style_management_has_preview_slot") is False
        assert detail._scene_card.property("style_management_slot_plan") == (
            "source|scope|difference"
        )
        assert detail._scene_card.preview_slot is None
        assert detail._scene_card.effective_preview_slot is None
        assert detail._style_difference_slot.isHidden() is False
    finally:
        detail.close()


def test_quick_execution_detail_reports_presenter_derived_status_and_snapshot():
    _app()
    detail = QuickExecutionDetail()
    try:
        assert detail._status_label.text() == "请先选择输入文档"
        assert detail.navigation_snapshot() == {
            "subtitle": "未选择文档 · 默认流程",
            "badge_text": "待补充",
            "badge_variant": "warning",
        }

        detail.set_document_path("C:/docs/report.docx")
        detail.set_strategy_context(template_name="汇报演示", strict_mode=False)
        detail.set_feature_enabled("content_fill", True)

        assert detail._active_template_label() == "汇报演示"
        assert detail._status_label.text() == "就绪：report.docx · 汇报演示 · 标准模式"
        assert detail.navigation_snapshot() == {
            "subtitle": "report.docx · 汇报演示",
            "badge_text": "1 项增强",
            "badge_variant": "success",
        }
        assert detail.feature_navigation_snapshot("content_fill") == {
            "subtitle": "资料源 / 5 个映射字段",
            "badge_text": "资料就绪",
            "badge_variant": "neutral",
        }
    finally:
        detail.close()


def test_quick_execution_detail_reports_material_schema_readiness_warning():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_document_path("C:/docs/report.docx")
        detail.current_scene().input_source_profile.material_schema_id = "missing_schema_v1"
        detail._emit_summary_changed()

        assert detail._status_label.text() == "资料 Schema 未注册：missing_schema_v1"
    finally:
        detail.close()


def test_quick_execution_detail_shows_schema_replacement_recommendation_in_repair_tooltip():
    _app()
    scene = SceneWorkspace(scene_id="contract_delivery", template_id="default")
    scene.category = "contract_delivery"
    scene.input_source_profile.material_schema_id = "signature_assets_v2"
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/contract.docx")

        tooltip = detail._material_repair_btn.toolTip()

        assert not detail._material_repair_btn.isHidden()
        assert "signature_assets_v1" in tooltip
        assert "alias:signature_assets_v2" in tooltip
        assert "family:contract_delivery" in tooltip
    finally:
        detail.close()


def test_quick_execution_detail_exposes_material_readiness_issue_queue():
    _app()
    scene = create_bidding_scene()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/bid.docx")

        items = detail.current_issue_items()

        assert [item.issue_id for item in items] == [
            "material.fields.missing",
            "material.assets.missing",
        ]
        assert items[0].repair_target_type == "field"
        assert items[0].repair_target_key == "company_name"
        assert items[1].repair_target_type == "asset"
        assert items[1].repair_target_key == "logo"
        assert not detail._issue_queue_label.isHidden()
        assert not detail._issue_panel.isHidden()
        assert detail._issue_panel_title.text() == "问题处理"
        assert detail._issue_panel_count.text() == "2 项，2 项阻断"
        assert detail._issue_list.count() == 2
        assert detail._issue_list.currentItem().data(Qt.UserRole) == (
            "material.fields.missing"
        )
        assert detail._issue_queue_label.text().startswith("运行前问题 2 项：")
        assert "先处理 2" in detail._issue_queue_label.text()
        assert "资料字段缺失：company_name, project_name, legal_person" in (
            detail._issue_queue_label.text()
        )
        assert "问题处理" in detail._issue_queue_label.toolTip()
        assert "行动：先处理 2" in detail._issue_queue_label.toolTip()

        detail._issue_panel_toggle_btn.click()

        assert detail._issue_panel.isHidden() is False
        assert detail._issue_panel_body.isHidden() is True
        assert detail._issue_panel_toggle_btn.text() == "展开"

        detail._issue_panel_toggle_btn.click()

        assert detail._issue_panel_body.isHidden() is False
        assert detail._issue_panel_toggle_btn.text() == "收起"

        detail.set_material_context(
            MaterialExecutionContext(
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
        )

        assert detail.current_issue_items() == []
        assert detail._issue_queue_label.isHidden()
        assert detail._issue_panel.isHidden()
    finally:
        detail.close()


def test_quick_execution_detail_issue_panel_shows_detail_and_rechecks_current_issue():
    app = _app()
    scene = create_bidding_scene()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/bid.docx")

        assert not detail._issue_detail_panel.isHidden()
        assert detail._issue_detail_title.text().startswith("资料字段缺失")
        assert detail._issue_detail_impact_title.text() == "影响"
        assert detail._issue_detail_action_title.text() == "动作"
        assert detail._issue_detail_evidence_title.text() == "证据"
        assert isinstance(detail._issue_detail_impact_section, IssueDetailSection)
        assert detail._issue_detail_impact_section.tone() == "error"
        assert detail._issue_detail_action_section.tone() == "primary"
        assert detail._issue_detail_evidence_section.tone() == "neutral"
        assert detail._issue_detail_impact.text() == "会阻断本次运行，需要先处理。"
        assert detail._issue_detail_advice.text().startswith("处理：")
        assert "去资料页补齐公司名称" in detail._issue_detail_advice.text()
        assert "建议：" not in detail._issue_detail_advice.text()
        assert "field:company_name" not in detail._issue_detail_advice.text()
        assert "来源：" in detail._issue_detail_body.text()

        detail._issue_list.setCurrentRow(1)
        app.processEvents()

        assert detail.current_active_issue_id() == "material.assets.missing"
        assert detail._issue_detail_title.text().startswith("资料资产缺失")
        assert detail._issue_detail_action_title.text() == "动作"
        assert detail._issue_detail_evidence_title.text() == "证据"
        assert "去资料页补齐企业标志" in detail._issue_action_btn.toolTip()
        assert "asset:logo" not in detail._issue_action_btn.toolTip()

        detail._material_context = MaterialExecutionContext(
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

        detail._issue_recheck_btn.click()

        assert detail.current_issue_items() == []
        assert detail._issue_panel.isHidden()
    finally:
        detail.close()


def test_quick_execution_detail_exposes_question_figure_comparison_issue_queue(monkeypatch):
    _app()
    detail = QuickExecutionDetail()
    try:
        monkeypatch.setattr(
            quick_execution_detail_module,
            "coverage_boundary_issue_items",
            lambda _scene: [],
        )
        monkeypatch.setattr(
            quick_execution_detail_module,
            "parameter_ownership_issue_items",
            lambda _scene: [],
        )
        monkeypatch.setattr(
            quick_execution_detail_module,
            "sample_fixture_issue_items",
            lambda _scene: [],
        )
        monkeypatch.setattr(
            quick_execution_detail_module,
            "control_contract_issue_items",
            lambda: [],
        )
        detail._apply_scene(SceneWorkspace(scene_id="exam_education"))
        detail.set_document_path("C:/docs/exam.docx")
        detail.set_material_context(
            MaterialExecutionContext(
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
                            "comparison_issue_summary": "题2 题图对比: question_1.png",
                        },
                    )
                ],
            )
        )

        items = detail.current_issue_items()

        assert len(items) == 1
        assert items[0].category == "material_asset_comparison"
        assert items[0].repair_target_type == "question_figure_item"
        assert detail.current_issue_action_targets()[0][0] == "profile_question_figure_item"
        assert not detail._issue_queue_label.isHidden()
        assert detail._issue_queue_label.text().startswith("运行前问题 1 项：")
        assert "题图对比问题：题2 题图对比: question_1.png" in (
            detail._issue_queue_label.text()
        )
        assert "分类：题图对比 1" in detail._issue_queue_label.toolTip()
        assert "人工标注" not in detail._issue_queue_label.text()

        detail.set_issue_queue_filter("material_asset_comparison")

        assert detail.current_filtered_issue_items()[0].issue_id == items[0].issue_id
        assert "当前筛选：题图对比" in detail._issue_queue_label.toolTip()
    finally:
        detail.close()


def test_quick_execution_detail_exposes_parameter_ownership_issue_queue():
    @dataclass
    class FutureSceneWorkspace(SceneWorkspace):
        experimental_knob: str = ""

    _app()
    scene = FutureSceneWorkspace(scene_id="future")
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/future.docx")

        items = detail.current_issue_items()

        assert [item.issue_id for item in items] == [
            "scene.parameter_ownership.audit",
        ]
        assert items[0].category == "parameter_ownership"
        assert items[0].repair_target_type == "parameter_ownership"
        assert items[0].repair_target_key == "registry"
        assert items[0].owner == "scene"
        assert detail.current_issue_action_targets() == [
            ("parameter_ownership", "registry")
        ]
        assert not detail._issue_queue_label.isHidden()
        assert detail._issue_queue_label.text().startswith("运行前问题 1 项：")
        assert "参数归属缺口：1 类缺口" in detail._issue_queue_label.text()
        assert "分类：参数归属 1" in detail._issue_queue_label.toolTip()
        assert "负责人：场景配置 1" in detail._issue_queue_label.toolTip()
        assert "缺少顶层字段归属：experimental_knob" in (
            detail._issue_queue_label.toolTip()
        )

        detail.set_issue_queue_filter("parameter_ownership")

        assert detail.current_filtered_issue_items()[0].issue_id == (
            "scene.parameter_ownership.audit"
        )
        assert "当前筛选：参数归属" in detail._issue_queue_label.toolTip()
    finally:
        detail.close()


def test_quick_execution_detail_exposes_control_contract_issue_queue(monkeypatch):
    _app()
    detail = QuickExecutionDetail()
    try:
        requested_targets = []
        opened_paths = []
        detail.issue_repair_requested.connect(
            lambda target_type, target_key: requested_targets.append(
                (target_type, target_key)
            )
        )
        detail._open_local_path_handler = (
            lambda path: opened_paths.append(Path(path)) or True
        )
        monkeypatch.setattr(
            quick_execution_detail_module,
            "control_contract_issue_items",
            lambda: [
                WorkbenchIssueItem(
                    issue_id="ui.control_contract.required.body_special_indent",
                    category="control_contract",
                    severity="warning",
                    title="控件契约缺失",
                    summary="body.special_indent",
                    details=(
                        "缺少必审控件契约：body.special_indent",
                        "规范控件：SpecialIndentInput",
                        "参数路径：body.special_indent",
                        "证据：src/shared/ui/paragraph_style_inputs.py:120#class SpecialIndentInput",
                    ),
                    source_notes=("control_contract_registry",),
                    repair_target_type="control_contract",
                    repair_target_key="body.special_indent",
                    owner="scene",
                )
            ],
        )
        detail._apply_scene(SceneWorkspace(scene_id="report"))
        detail.set_document_path("C:/docs/report.docx")

        items = detail.current_issue_items()

        assert [item.issue_id for item in items] == [
            "ui.control_contract.required.body_special_indent"
        ]
        assert items[0].category == "control_contract"
        assert items[0].repair_target_type == "control_contract"
        assert items[0].repair_target_key == "body.special_indent"
        assert items[0].owner == "scene"
        assert detail.current_issue_action_targets() == [
            ("control_contract", "body.special_indent")
        ]
        assert not detail._issue_queue_label.isHidden()
        assert detail._issue_queue_label.text().startswith("运行前问题 1 项：")
        assert "控件契约缺失：正文特殊缩进" in detail._issue_queue_label.text()
        assert "body.special_indent" not in detail._issue_queue_label.text()
        assert "分类：控件契约 1" in detail._issue_queue_label.toolTip()
        assert "负责人：场景配置 1" in detail._issue_queue_label.toolTip()
        assert "缺少必审控件契约：正文特殊缩进（body.special_indent）" in (
            detail._issue_queue_label.toolTip()
        )
        assert "规范控件：SpecialIndentInput" in detail._issue_queue_label.toolTip()
        assert "paragraph_style_inputs.py:120#class SpecialIndentInput" in (
            detail._issue_queue_label.toolTip()
        )
        assert "来源：控件边界登记" in detail._issue_queue_label.toolTip()
        assert "control_contract_registry" not in detail._issue_queue_label.toolTip()
        assert detail._issue_detail_action_title.text() == "动作"
        assert detail._issue_detail_evidence_title.text() == "证据"
        assert "说明：缺少必审控件契约：正文特殊缩进（body.special_indent）" in (
            detail._issue_detail_body.text()
        )
        assert "参数：正文特殊缩进" in detail._issue_detail_body.text()
        assert "证据文件：src/shared/ui/paragraph_style_inputs.py:120#class SpecialIndentInput" in (
            detail._issue_detail_body.text()
        )
        assert "来源：控件边界登记" in detail._issue_detail_body.text()
        assert "control_contract_registry" not in detail._issue_detail_body.text()
        assert detail.current_issue_evidence_actions() == [
            ("parameter_path", "navigate_parameter", "body.special_indent"),
            (
                "evidence_file",
                "open_evidence",
                "src/shared/ui/paragraph_style_inputs.py:120#class SpecialIndentInput",
            ),
        ]
        assert isinstance(detail._issue_evidence_line_list, EvidenceLineList)
        assert isinstance(detail._issue_evidence_action_bar, EvidenceActionBar)
        assert detail._issue_detail_body.isHidden()
        assert not detail._issue_evidence_line_list.isHidden()
        assert detail._issue_evidence_line_list.line_count() == 5
        assert detail._issue_evidence_line_list.text_at(2) == (
            "参数：正文特殊缩进"
        )
        assert detail._issue_evidence_action_bar.current_actions() == [
            ("parameter_path", "navigate_parameter", "body.special_indent"),
            (
                "evidence_file",
                "open_evidence",
                "src/shared/ui/paragraph_style_inputs.py:120#class SpecialIndentInput",
            ),
        ]
        assert not detail._issue_evidence_action_row.isHidden()
        assert detail._issue_evidence_parameter_btn.text() == "定位参数"
        assert detail._issue_evidence_parameter_btn.isEnabled()
        assert "body.special_indent" in detail._issue_evidence_parameter_btn.toolTip()
        assert detail._issue_evidence_file_btn.text() == "打开证据"
        assert detail._issue_evidence_file_btn.isEnabled()
        assert "paragraph_style_inputs.py" in detail._issue_evidence_file_btn.toolTip()

        detail._issue_evidence_parameter_btn.click()
        assert requested_targets[-1] == ("control_contract", "body.special_indent")

        detail._issue_evidence_file_btn.click()
        assert opened_paths
        assert opened_paths[-1].name == "paragraph_style_inputs.py"
        assert opened_paths[-1].is_absolute()
        assert "已打开证据" in detail._exec_log.toPlainText()

        detail.set_issue_queue_filter("control_contract")

        assert detail.current_filtered_issue_items()[0].issue_id == (
            "ui.control_contract.required.body_special_indent"
        )
        assert "当前筛选：控件契约" in detail._issue_queue_label.toolTip()
    finally:
        detail.close()


def test_quick_execution_detail_evidence_parameter_action_routes_scene_style():
    _app()
    detail = QuickExecutionDetail()
    try:
        requested_targets = []
        detail.issue_repair_requested.connect(
            lambda target_type, target_key: requested_targets.append(
                (target_type, target_key)
            )
        )
        item = WorkbenchIssueItem(
            issue_id="scene.style.references_body.font_cn",
            category="scene_style",
            severity="warning",
            title="样式参数不一致",
            summary="参考文献正文中文字体",
            details=("参数路径：scene.section_styles.references_body.font_cn",),
            owner="scene",
        )
        detail._workbench_issue_items = [item]
        detail._issue_panel_expanded = True
        detail._set_issue_queue_visible(True, [item])

        assert not detail._issue_evidence_action_row.isHidden()
        assert detail.current_issue_evidence_actions() == [
            (
                "parameter_path",
                "navigate_parameter",
                "scene.section_styles.references_body.font_cn",
            )
        ]
        assert detail._issue_evidence_line_list.text_at(0) == (
            "参数：参考文献正文中文字体"
        )

        detail._issue_evidence_parameter_btn.click()

        assert requested_targets[-1] == (
            "scene_style_field",
            "scene.section_styles.references_body.font_cn",
        )
    finally:
        detail.close()


def test_quick_execution_detail_action_copy_includes_style_layout_group():
    _app()
    detail = QuickExecutionDetail()
    try:
        item = WorkbenchIssueItem(
            issue_id="template.style.body.bold",
            category="template_style",
            severity="warning",
            title="模板样式不一致",
            summary="template.styles.body.bold",
            details=("参数路径：template.styles.body.bold",),
            repair_target_type="template_style_field",
            repair_target_key="template.styles.body.bold",
            owner="template",
        )
        detail._workbench_issue_items = [item]
        detail._issue_panel_expanded = True
        detail._set_issue_queue_visible(True, [item])

        assert "处理：去模板页调整文字样式：正文字形" in (
            detail._issue_detail_advice.text()
        )
        assert "处理当前问题：去模板页调整文字样式：正文字形" in (
            detail._issue_action_btn.toolTip()
        )
        assert "可处理目标：模板样式：文字样式：正文字形 1" in (
            detail._issue_queue_label.toolTip()
        )
        assert detail.current_issue_evidence_actions() == [
            ("parameter_path", "navigate_parameter", "template.styles.body.bold")
        ]
        navigation_context = detail.current_issue_navigation_context()
        assert navigation_context["issue_target_type"] == "template_style_field"
        assert navigation_context["issue_target_key"] == "template.styles.body.bold"
        assert navigation_context["issue_target_label"] == "正文字形"
        assert navigation_context["issue_target_label_with_group"] == (
            "文字样式：正文字形"
        )
        assert navigation_context["issue_target_layout_item_id"] == "emphasis"
        assert navigation_context["issue_target_field_ids"] == "bold,italic"
        assert navigation_context["issue_target_control_contract_key"] == ""
    finally:
        detail.close()


def test_quick_execution_detail_exposes_contract_boundary_and_sample_fixture_issue_queue(
    monkeypatch,
):
    _app()
    detail = QuickExecutionDetail()
    try:
        monkeypatch.setattr(
            quick_execution_detail_module,
            "sample_fixture_issue_items",
            lambda _scene: [
                WorkbenchIssueItem(
                    issue_id="sample_fixture.contract_delivery_missing_surfaces_contract_delivery_revisions",
                    category="sample_fixture",
                    severity="error",
                    title="样本覆盖缺口",
                    summary="contract_delivery: missing_surfaces",
                    details=(
                        "覆盖 pack：contract_delivery",
                        "缺口类型：missing_surfaces",
                        "Sample fixture must declare at least one DOCX surface.",
                    ),
                    source_notes=("scene_sample_fixture_registry",),
                    repair_target_type="sample_fixture",
                    repair_target_key="contract_delivery",
                    owner="scene",
                )
            ],
        )
        detail._apply_scene(
            SceneWorkspace(scene_id="contract_delivery", category="contract_delivery")
        )
        detail.set_document_path("C:/docs/contract.docx")

        items = detail.current_issue_items()

        assert [item.issue_id for item in items] == [
            "coverage.contract_delivery.coverage_boundary",
            "sample_fixture.contract_delivery_missing_surfaces_contract_delivery_revisions"
        ]
        assert items[0].category == "coverage_boundary"
        assert items[0].repair_target_type == "coverage_boundary"
        assert items[0].repair_target_key == "contract_delivery"
        assert items[1].category == "sample_fixture"
        assert items[1].repair_target_type == "sample_fixture"
        assert items[1].repair_target_key == "contract_delivery"
        assert detail.current_issue_action_targets() == [
            ("sample_fixture", "contract_delivery"),
            ("coverage_boundary", "contract_delivery"),
        ]
        assert not detail._issue_queue_label.isHidden()
        assert detail._issue_queue_label.text().startswith("运行前问题 2 项：")
        assert "法律/交付边界：合同交付" in (
            detail._issue_queue_label.text()
        )
        assert "样本覆盖缺口：合同交付：样本缺少 Word 对象" in (
            detail._issue_queue_label.text()
        )
        assert "分类：边界覆盖 1 / 样本覆盖 1" in detail._issue_queue_label.toolTip()
        assert "负责人：场景配置 2" in detail._issue_queue_label.toolTip()
        assert "不提供法律意见" in detail._issue_queue_label.toolTip()
        assert "覆盖资料包：合同交付" in detail._issue_queue_label.toolTip()
        assert "来源：样本覆盖登记" in detail._issue_queue_label.toolTip()
        assert "覆盖 pack：contract_delivery" not in detail._issue_queue_label.toolTip()
        assert "scene_sample_fixture_registry" not in detail._issue_queue_label.toolTip()
        assert "missing_surfaces" not in detail._issue_queue_label.text()

        detail.set_issue_queue_filter("sample_fixture")

        assert detail.current_filtered_issue_items()[0].repair_target_type == (
            "sample_fixture"
        )
        assert "当前筛选：样本覆盖" in detail._issue_queue_label.toolTip()
    finally:
        detail.close()


def test_quick_execution_detail_filters_issue_queue_by_category():
    _app()
    scene = create_bidding_scene()
    detail = QuickExecutionDetail()
    requested: list[tuple[str, str]] = []
    try:
        detail.issue_repair_requested.connect(
            lambda target_type, target_key: requested.append((target_type, target_key))
        )
        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/bid.docx")

        assert len(detail.current_issue_items()) == 2
        assert not detail._issue_filter_row.isHidden()
        assert not detail._issue_action_btn.isHidden()
        assert detail._issue_filter_combo.count() == 3
        assert detail._issue_filter_combo.itemText(0) == "全部问题 (2)"
        assert detail._issue_filter_combo.itemData(1) == "material_field"
        assert detail._issue_filter_combo.itemData(2) == "material_asset"
        assert detail.current_issue_action_targets() == [
            ("field", "company_name"),
            ("asset", "logo"),
        ]
        assert "去资料页补齐公司名称" in detail._issue_action_btn.toolTip()
        assert "field:company_name" not in detail._issue_action_btn.toolTip()

        detail.set_issue_queue_filter("material_asset")

        assert len(detail.current_issue_items()) == 2
        filtered_items = detail.current_filtered_issue_items()
        assert [item.category for item in filtered_items] == ["material_asset"]
        assert detail.current_issue_action_targets() == [("asset", "logo")]
        assert "去资料页补齐企业标志" in detail._issue_action_btn.toolTip()
        assert "asset:logo" not in detail._issue_action_btn.toolTip()
        assert detail._issue_queue_label.text().startswith(
            "运行前问题 2 项（资料资产 1/2）："
        )
        assert "先处理 1" in detail._issue_queue_label.text()
        assert "资料资产缺失：logo, seal" in detail._issue_queue_label.text()
        assert "资料字段缺失：company_name" not in detail._issue_queue_label.text()
        assert "行动：先处理 1" in detail._issue_queue_label.toolTip()
        assert "分类：资料字段 1 / 资料资产 1" in detail._issue_queue_label.toolTip()
        assert "状态：待处理 2" in detail._issue_queue_label.toolTip()
        assert "负责人：工作台 2" in detail._issue_queue_label.toolTip()
        assert "资料素材：企业标志" in detail._issue_queue_label.toolTip()
        assert "asset:logo" not in detail._issue_queue_label.toolTip()
        assert "当前筛选：资料资产" in detail._issue_queue_label.toolTip()
        assert "1. 资料资产缺失：logo, seal" in detail._issue_queue_label.toolTip()

        detail._issue_action_btn.click()

        assert requested == [("asset", "logo")]

        detail._issue_filter_combo.setCurrentIndex(1)

        assert [item.category for item in detail.current_filtered_issue_items()] == [
            "material_field",
        ]
        assert detail.current_issue_action_targets() == [("field", "company_name")]
        assert "资料字段 1/2" in detail._issue_queue_label.text()

        detail._issue_filter_combo.setCurrentIndex(0)

        assert [item.category for item in detail.current_filtered_issue_items()] == [
            "material_field",
            "material_asset",
        ]
        assert detail._issue_queue_label.text().startswith("运行前问题 2 项：")
    finally:
        detail.close()


def test_quick_execution_detail_filters_issue_queue_by_action_group():
    _app()
    scene = create_bidding_scene()
    detail = QuickExecutionDetail()
    requested: list[tuple[str, str]] = []
    try:
        detail.issue_repair_requested.connect(
            lambda target_type, target_key: requested.append((target_type, target_key))
        )
        items = [
            *coverage_boundary_issue_items(
                SceneWorkspace(scene_id="exam_teaching", category="exam_teaching")
            ),
            *material_readiness_issue_items(scene, MaterialExecutionContext()),
        ]
        detail._workbench_issue_items = list(items)
        detail._set_issue_queue_visible(True, detail._workbench_issue_items)

        assert detail._issue_list.count() == 3
        assert detail._issue_list.item(0).text().startswith("先处理 ·")
        assert detail._issue_list.item(0).data(Qt.UserRole) == "material.fields.missing"
        first_widget = detail._issue_list.itemWidget(detail._issue_list.item(0))
        first_badge = first_widget.findChild(QLabel, "wb_v2_issue_action_badge")
        assert first_badge.text() == "先处理"
        assert first_badge.property("issue_action_group") == "handle_first"
        assert first_badge.property("issue_action_tone") == "error"
        assert not detail._issue_action_group_combo.isHidden()
        assert detail._issue_action_group_combo.itemText(0) == "全部动作 (3)"
        assert detail._issue_action_group_combo.itemData(1) == "handle_first"
        assert detail._issue_action_group_combo.itemData(2) == "confirm"

        detail.set_issue_queue_action_filter("confirm")

        filtered_items = detail.current_filtered_issue_items()
        assert [item.issue_id for item in filtered_items] == [
            "coverage.exam_education.plugin_boundary"
        ]
        assert detail._issue_list.count() == 1
        assert detail._issue_list.item(0).text().startswith("建议确认 ·")
        confirm_widget = detail._issue_list.itemWidget(detail._issue_list.item(0))
        confirm_badge = confirm_widget.findChild(QLabel, "wb_v2_issue_action_badge")
        assert confirm_badge.text() == "建议确认"
        assert confirm_badge.property("issue_action_group") == "confirm"
        assert confirm_badge.property("issue_action_tone") == "info"
        assert "运行前问题 3 项（建议确认 1/3）：" in (
            detail._issue_queue_label.text()
        )
        assert "当前筛选：建议确认" in detail._issue_queue_label.toolTip()
        assert "行动：建议确认" in detail._issue_list.item(0).toolTip()
        assert detail._issue_detail_impact.text() == (
            "不一定阻断运行，但会影响边界判断或修复选择。"
        )
        assert detail._issue_detail_impact_section.tone() == "info"
        assert detail._issue_detail_action_title.text() == "动作"
        assert detail._issue_detail_advice.text() == "处理：去高级证据核对人工确认"

        detail._request_current_issue_action()

        assert requested == [
            ("plugin_manual_gate", "exam_ai_complex_diagram_gate")
        ]

        detail.set_issue_queue_filter("material_field")

        assert detail.current_filtered_issue_items() == []
        assert detail._issue_list.count() == 0
        assert "运行前问题 3 项（资料字段 / 建议确认 0/3）：" in (
            detail._issue_queue_label.text()
        )
        assert "当前筛选没有问题" in detail._issue_queue_label.text()
        assert "当前筛选：资料字段 / 建议确认" in (
            detail._issue_queue_label.toolTip()
        )

        detail.set_issue_queue_action_filter("")

        assert [item.category for item in detail.current_filtered_issue_items()] == [
            "material_field"
        ]
        assert detail._issue_list.item(0).text().startswith("先处理 ·")
        assert "资料字段 1/3" in detail._issue_queue_label.text()
    finally:
        detail.close()


def test_quick_execution_detail_consumes_batch_issue_items_from_result_state():
    _app()
    detail = QuickExecutionDetail()
    adapter = WorkbenchExecutionAdapter()
    requested: list[tuple[str, str]] = []
    try:
        detail.issue_repair_requested.connect(
            lambda target_type, target_key: requested.append((target_type, target_key))
        )
        state = adapter.build_result_state(
            status="partial_success",
            output_path="",
            report_paths=["C:/tmp/source_batch_report.json"],
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

        detail.set_execution_result(state)

        items = detail.current_issue_items()
        assert len(items) == 1
        assert items[0].category == "batch_issue"
        assert items[0].repair_target_key == "employee_id"
        action_targets = detail.current_issue_action_targets()
        assert action_targets[0][0] == "profile_field"
        action_payload = json.loads(action_targets[0][1])
        assert action_payload["profile_id"] == "missing"
        assert action_payload["target_key"] == "employee_id"
        assert "Batch isolation: total=2; success=1; warning=0; failed=1" in (
            detail._exec_log.toPlainText()
        )
        assert not detail._issue_queue_label.isHidden()
        assert detail._issue_queue_label.text().startswith("运行前问题 1 项：")
        assert "批量记录问题：Missing required material fields: employee_id" in (
            detail._issue_queue_label.text()
        )
        assert "分类：批量记录 1" in detail._issue_queue_label.toolTip()
        assert "记录名称：缺编号员工" in detail._issue_queue_label.toolTip()

        detail.set_issue_queue_filter("batch_issue")

        assert detail.current_filtered_issue_items()[0].issue_id == (
            "batch:missing:preflight_missing_material_fields:1"
        )
        assert "当前筛选：批量记录" in detail._issue_queue_label.toolTip()

        detail._request_current_issue_action()

        assert requested[0][0] == "profile_field"
        assert json.loads(requested[0][1])["profile_id"] == "missing"
    finally:
        detail.close()


def test_quick_execution_detail_emits_question_figure_repair_candidate_action():
    _app()
    detail = QuickExecutionDetail()
    adapter = WorkbenchExecutionAdapter()
    requested: list[tuple[str, str]] = []
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
    try:
        detail.issue_repair_requested.connect(
            lambda target_type, target_key: requested.append((target_type, target_key))
        )
        state = adapter.build_result_state(
            status="partial_success",
            output_path="",
            report_paths=["C:/tmp/source_batch_report.md"],
            failed_count=0,
            error_text="",
            question_figure_repair_queue={
                "kind": "question_figure_repair_queue",
                "queue_count": 1,
                "entries": [
                    {
                        "queue_id": "repair:question_figure:exam_a:q2:abc",
                        "status": "candidate",
                        "profile_id": "exam_a",
                        "profile_name": "Exam A",
                        "question_index": "2",
                        "repair_target_type": "question_figure_item",
                        "repair_target_key": target_key,
                        "confirmation_apply_supported": True,
                        "confirmation_status": "ready",
                        "replacement_source_path": "C:/tmp/question_2_expected.png",
                    }
                ],
            },
        )

        detail.set_execution_result(state)
        detail.set_issue_queue_filter("question_figure_repair_queue")

        action_targets = detail.current_issue_action_targets()
        assert action_targets[0][0] == "profile_question_figure_repair_candidate"

        detail._issue_action_btn.click()

        assert requested
        action_type, action_payload = requested[0]
        action_data = json.loads(action_payload)
        assert action_type == "profile_question_figure_repair_candidate"
        assert action_data["profile_id"] == "exam_a"
        assert action_data["candidate"]["confirmation_status"] == "ready"
        assert action_data["candidate"]["repair_target_key"] == target_key
    finally:
        detail.close()


def test_quick_execution_detail_emits_transaction_task_summary_action():
    _app()
    detail = QuickExecutionDetail()
    adapter = WorkbenchExecutionAdapter()
    requested: list[tuple[str, str]] = []
    try:
        detail.issue_repair_requested.connect(
            lambda target_type, target_key: requested.append((target_type, target_key))
        )
        state = adapter.build_result_state(
            status="partial_success",
            output_path="",
            report_paths=["C:/tmp/source_batch_report.md"],
            failed_count=0,
            error_text="",
            question_figure_repair_queue={
                "kind": "question_figure_repair_queue",
                "queue_count": 1,
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
                        "transaction_count": 1,
                        "active_count": 1,
                        "rolled_back_count": 0,
                        "rollback_available_count": 1,
                        "active_transaction_ids": ["tx-active"],
                        "rollback_available_transaction_ids": ["tx-active"],
                        "latest_transaction_id": "tx-active",
                        "latest_apply_audit_id": "apply-1",
                    },
                },
                "entries": [],
            },
        )

        detail.set_execution_result(state)
        detail.set_issue_queue_filter("question_figure_batch_apply_transaction_task")

        action_targets = detail.current_issue_action_targets()
        assert len(action_targets) == 1
        assert action_targets[0][0] == (
            "question_figure_batch_apply_transaction_task_summary"
        )
        action_data = json.loads(action_targets[0][1])
        assert action_data["status"] == "active"
        assert action_data["fragment"] == (
            "question-figure-batch-apply-transaction-task-summary"
        )

        detail._issue_action_btn.click()

        assert requested
        action_type, action_payload = requested[0]
        emitted_data = json.loads(action_payload)
        assert action_type == "question_figure_batch_apply_transaction_task_summary"
        assert emitted_data["next_action"] == "review_active_transaction"
        assert emitted_data["rollback_available_count"] == 1
    finally:
        detail.close()


def test_quick_execution_detail_emits_question_figure_conflict_selection_action():
    _app()
    detail = QuickExecutionDetail()
    adapter = WorkbenchExecutionAdapter()
    requested: list[tuple[str, str]] = []
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
    try:
        detail.issue_repair_requested.connect(
            lambda target_type, target_key: requested.append((target_type, target_key))
        )
        state = adapter.build_result_state(
            status="partial_success",
            output_path="",
            report_paths=["C:/tmp/source_batch_report.md"],
            failed_count=0,
            error_text="",
            question_figure_repair_queue={
                "kind": "question_figure_repair_queue",
                "queue_count": 2,
                "entries": [
                    {
                        "queue_id": "repair:question_figure:exam_a:q2:conflict-a",
                        "status": "candidate",
                        "profile_id": "exam_a",
                        "profile_name": "Exam A",
                        "question_index": "2",
                        "repair_target_type": "question_figure_item",
                        "repair_target_key": target_key,
                        "confirmation_action": (
                            "resolve_question_figure_replacement_conflict"
                        ),
                        "confirmation_apply_supported": False,
                        "confirmation_status": "conflict",
                        "replacement_source_path": "C:/tmp/question_2_expected_a.png",
                        "replacement_source_kind": "local_file",
                        "conflict_group_id": "repair-conflict:1:abc",
                        "conflict_candidate_queue_ids": [
                            "repair:question_figure:exam_a:q2:conflict-a",
                            "repair:question_figure:exam_a:q2:conflict-b",
                        ],
                        "conflict_resolution_select_supported": True,
                        "conflict_resolution_action": (
                            "select_question_figure_replacement_conflict_candidate"
                        ),
                        "apply_blockers": ["candidate_conflict_same_repair_target"],
                    }
                ],
            },
        )

        detail.set_execution_result(state)
        detail.set_issue_queue_filter("question_figure_repair_queue")

        action_targets = detail.current_issue_action_targets()
        assert action_targets[0][0] == (
            "profile_question_figure_repair_conflict_selection"
        )

        detail._issue_action_btn.click()

        assert requested
        action_type, action_payload = requested[0]
        action_data = json.loads(action_payload)
        assert action_type == "profile_question_figure_repair_conflict_selection"
        assert action_data["profile_id"] == "exam_a"
        assert action_data["candidate"]["confirmation_status"] == "ready"
        assert action_data["candidate"]["conflict_resolution_status"] == "selected"
        assert action_data["candidate"]["repair_target_key"] == target_key
    finally:
        detail.close()


def test_quick_execution_detail_marks_filtered_issue_status():
    _app()
    scene = create_bidding_scene()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/bid.docx")

        detail.set_issue_queue_filter("material_asset")

        assert not detail._issue_resolve_btn.isHidden()
        assert not detail._issue_ignore_btn.isHidden()
        assert "资料资产缺失" in detail._issue_resolve_btn.toolTip()

        detail._issue_resolve_btn.click()

        items = {item.issue_id: item for item in detail.current_issue_items()}
        assert items["material.assets.missing"].status == "resolved"
        assert items["material.fields.missing"].status == "open"
        assert "状态：待处理 1 / 已处理 1" in detail._issue_queue_label.toolTip()
        assert detail._issue_resolve_btn.isHidden()
        assert detail._issue_ignore_btn.isHidden()

        detail.set_issue_queue_filter("material_field")

        assert not detail._issue_ignore_btn.isHidden()
        assert "资料字段缺失" in detail._issue_ignore_btn.toolTip()

        detail._issue_ignore_btn.click()

        items = {item.issue_id: item for item in detail.current_issue_items()}
        assert items["material.fields.missing"].status == "ignored"
        assert items["material.assets.missing"].status == "resolved"
        assert "状态：已忽略 1 / 已处理 1" in detail._issue_queue_label.toolTip()
        assert detail._issue_resolve_btn.isHidden()
        assert detail._issue_ignore_btn.isHidden()
    finally:
        detail.close()


def test_quick_execution_detail_exposes_coverage_boundary_issue_queue():
    _app()
    scene = SceneWorkspace(scene_id="exam_teaching", template_id="default")
    scene.category = "exam_teaching"
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/exam.docx")

        items = detail.current_issue_items()

        assert [item.issue_id for item in items] == [
            "coverage.exam_education.plugin_boundary"
        ]
        assert items[0].category == "plugin_boundary"
        assert items[0].blocking is False
        assert not detail._issue_queue_label.isHidden()
        assert detail._issue_queue_label.text().startswith("运行前问题 1 项：")
        assert "建议确认 1" in detail._issue_queue_label.text()
        assert "插件/专业边界：试卷/教学资料" in (
            detail._issue_queue_label.text()
        )
        assert "行动：建议确认 1" in detail._issue_queue_label.toolTip()
        assert "不保证 AI 内容质量或复杂图生成" in (
            detail._issue_queue_label.toolTip()
        )
        assert "试卷 AI/复杂图插件" in (
            detail._issue_queue_label.toolTip()
        )
        assert "复杂图生成" in detail._issue_queue_label.toolTip()
        assert "内容显隐规则" in detail._issue_queue_label.toolTip()
        assert "does not guarantee AI content quality" not in (
            detail._issue_queue_label.toolTip()
        )
        assert "geometry_diagram_generation" not in detail._issue_queue_label.toolTip()
        assert "plugin_manual_gate:" not in detail._issue_queue_label.toolTip()
    finally:
        detail.close()


def test_quick_execution_detail_updates_material_readiness_from_context():
    _app()
    scene = create_bidding_scene()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/bid.docx")

        assert detail._status_label.text() == (
            "资料字段缺失：company_name, project_name, legal_person；"
            "资料资产缺失：logo, seal"
        )

        detail.set_material_context(
            MaterialExecutionContext(
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
        )

        assert detail._status_label.text() == "就绪：bid.docx · 工程类投标文件 · 严格模式"
    finally:
        detail.close()


def test_quick_execution_detail_routes_field_material_repair_action_to_field_target():
    _app()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    scene.input_source_profile.required_material_fields = ["company_name"]
    detail = QuickExecutionDetail()
    opened: list[str] = []
    targeted: list[tuple[str, str]] = []
    try:
        detail.feature_config_requested.connect(lambda feature_id: opened.append(feature_id))
        detail.material_repair_requested.connect(
            lambda target_type, target_key: targeted.append((target_type, target_key))
        )

        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/report.docx")

        assert not detail._material_repair_btn.isHidden()
        detail._material_repair_btn.click()

        assert opened == []
        assert targeted == [("field", "company_name")]
    finally:
        detail.close()


def test_quick_execution_detail_routes_asset_material_repair_action_to_asset_target():
    _app()
    scene = create_bidding_scene()
    detail = QuickExecutionDetail()
    opened: list[str] = []
    targeted: list[tuple[str, str]] = []
    try:
        detail.feature_config_requested.connect(lambda feature_id: opened.append(feature_id))
        detail.material_repair_requested.connect(
            lambda target_type, target_key: targeted.append((target_type, target_key))
        )

        assert detail._material_repair_btn.isHidden()

        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/bid.docx")

        assert not detail._material_repair_btn.isHidden()
        tooltip = detail._material_repair_btn.toolTip()
        assert "资料缺口明细" in tooltip
        assert "字段：company_name, project_name, legal_person" in tooltip
        assert "资产：logo, seal" in tooltip
        assert "来源：Schema：Bidding materials (bid_materials_v1)" in tooltip
        assert "来源：当前资料：未配置" in tooltip
        detail.set_material_context(
            MaterialExecutionContext(
                entity_data={
                    "company_name": "测试公司",
                    "project_name": "示例项目",
                    "legal_person": "张三",
                }
            )
        )
        detail._material_repair_btn.click()

        assert opened == []
        assert targeted == [("asset", "logo")]

        detail.set_material_context(
            MaterialExecutionContext(
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
        )

        assert detail._material_repair_btn.isHidden()
        assert detail._material_repair_btn.toolTip() == "打开资料配置"
    finally:
        detail.close()


def test_quick_execution_scene_summary_includes_profile_contracts():
    _app()
    scene = create_bidding_scene()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(scene)
        assert not hasattr(detail, "_summary_label")

        shared_summary = build_scene_summary(scene)
        assert "输入 docx/xlsx" in shared_summary
        assert "合规 bid_package" in shared_summary
        assert "交付 original+2" in shared_summary
        assert "严格保护" in shared_summary
        assert "参数归属已守门" in shared_summary
        assert "template/scene/material/output" in shared_summary
        assert "控件契约已守门" in shared_summary
        assert "template/scene" in shared_summary
        assert "产品成熟度Green/L5" in shared_summary
        assert "非Green0" in shared_summary
        assert "样本覆盖已守门" in shared_summary
        assert "常见说法已守门" in shared_summary

        ownership_summary = build_scene_parameter_ownership_summary(scene)
        assert ownership_summary.startswith("参数归属已守门")
        assert "template/scene/material/output" in ownership_summary

        contract_summary = build_scene_control_contract_summary()
        assert contract_summary.startswith("控件契约已守门")
        assert "template/scene" in contract_summary

        sample_summary = build_scene_sample_coverage_summary_text(scene)
        assert sample_summary.startswith("样本覆盖已守门")
        assert "4样本/9类OOXML" in sample_summary

        request_cell_summary = build_scene_request_cell_summary_text(scene)
        assert request_cell_summary.startswith("常见说法已守门")
        assert "5请求/5证据/0借用" in request_cell_summary
        assert "0proxy" not in request_cell_summary
        assert "1容易误解" in request_cell_summary

        readiness_summary = build_scene_product_readiness_summary(scene)
        assert readiness_summary.startswith("产品成熟度Green/L5")
        assert "static闭合1" in readiness_summary
        assert "非Green0" in readiness_summary
    finally:
        detail.close()


def test_quick_execution_output_does_not_embed_request_cell_browser():
    source = (
        ROOT / "src/ui/panels/workbench/quick_execution_detail.py"
    ).read_text(encoding="utf-8")
    _app()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(create_bidding_scene())

        assert not hasattr(detail, "_request_cell_panel")
        assert not hasattr(detail, "_request_cell_filter")
        assert not hasattr(detail, "_request_cell_list")
        assert not hasattr(detail, "_request_cell_count_label")
        assert not hasattr(detail, "_open_request_cell_fixture_btn")
        assert not hasattr(detail, "current_request_cell_items")
        assert not hasattr(detail, "_refresh_request_cell_list")
        assert not hasattr(detail, "_open_request_cell_fixture_file")
        assert not hasattr(detail, "_summary_label")
        assert "_request_cell_panel" not in source
        assert "wb_v2_request_cell_panel" not in source
        assert "wb_v2_request_cell_list" not in source
        assert "打开依据" not in source
        assert "scene_request_cell_filter_options" not in source
        assert "scene_request_cell_list_item_projection" not in source
        assert "build_scene_request_cell_summary_text" not in source
    finally:
        detail.close()


def test_quick_execution_scene_summary_reports_parameter_ownership_gaps():
    @dataclass
    class FutureSceneWorkspace(SceneWorkspace):
        experimental_knob: str = ""

    scene = FutureSceneWorkspace(scene_id="future")

    ownership_summary = build_scene_parameter_ownership_summary(scene)

    assert ownership_summary.startswith("参数归属1个缺口")
    assert "template/scene/material/output" in ownership_summary


def test_quick_execution_detail_does_not_expose_advanced_scene_controls():
    _app()
    detail = QuickExecutionDetail()
    try:
        original_scope = dict(detail.current_scene().format_scope.sections)

        assert not hasattr(detail, "_advanced_card")
        assert not hasattr(detail, "_zone_checks")
        assert not hasattr(detail, "_strategy_rebuild")

        detail.set_feature_enabled("content_fill", True)

        assert detail.current_scene().format_scope.sections == original_scope
        assert detail.current_scene().is_module_enabled("entity_fill") is True
    finally:
        detail.close()


def test_quick_execution_detail_logs_delivery_artifacts():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_execution_result(
            ExecutionResultState(
                status="success",
                summary="本次执行已完成",
                output_path="C:/tmp/final.docx",
                output_paths={"final": "C:/tmp/final.docx", "review": "C:/tmp/review.docx"},
                compare_paths={"review": "C:/tmp/review_compare.docx"},
                report_paths=["C:/tmp/report.json"],
                intermediate_paths={"review": "C:/tmp/review_intermediate.json"},
                material_manifest_paths={"material": "C:/tmp/material_manifest.json"},
                material_package_paths={"zip": "C:/tmp/material_package.zip"},
                artifact_items=[
                    ArtifactItemState(
                        kind="output",
                        label="审阅稿",
                        path="C:/tmp/review.docx",
                        status="warning",
                        detail="输出文件已存在，将被覆盖",
                    )
                ],
            )
        )

        log_text = detail._exec_log.toPlainText()
        assert "输出文件[最终 Word]：C:/tmp/final.docx" in log_text
        assert "输出文件[审阅稿]：C:/tmp/review.docx" in log_text
        assert "对比稿[审阅稿]：C:/tmp/review_compare.docx" in log_text
        assert "中间产物[审阅稿]：C:/tmp/review_intermediate.json" in log_text
        assert "资料清单[material]：C:/tmp/material_manifest.json" in log_text
        assert "资料包[zip]：C:/tmp/material_package.zip" in log_text
        assert "产物预检[审阅稿]：输出文件已存在，将被覆盖" in log_text
        assert "报告文件：C:/tmp/report.json" in log_text
    finally:
        detail.close()


def test_quick_execution_detail_exposes_output_target_issue_queue_on_result():
    _app()
    detail = QuickExecutionDetail()
    adapter = WorkbenchExecutionAdapter()
    try:
        state = adapter.build_result_state(
            status="success",
            output_path="C:/tmp/source.docx",
            output_paths={"review": "C:/tmp/review.docx"},
            report_paths=[],
            failed_count=0,
            error_text="",
            output_target_preflight={
                "items": [
                    {
                        "preset_id": "review",
                        "path": "C:/tmp/review.docx",
                        "issues": [
                            {
                                "kind": "target_exists",
                                "message": "review 输出文件已存在，将被覆盖: C:/tmp/review.docx",
                            }
                        ],
                    }
                ]
            },
        )

        detail.set_execution_result(state)

        items = detail.current_issue_items()
        assert len(items) == 1
        assert items[0].issue_id == "output_target.review.warning"
        assert items[0].category == "output_target"
        assert items[0].summary.startswith("审阅稿：输出文件已存在")
        assert items[0].repair_target_key == "review"
        assert not detail._issue_queue_label.isHidden()
        assert detail._issue_queue_label.text().startswith("运行前问题 1 项：")
        assert "输出目标预检：审阅稿：输出文件已存在" in (
            detail._issue_queue_label.text()
        )
        assert "输出文件已存在，将被覆盖" in detail._issue_queue_label.toolTip()
        assert "来源：交付版本 ID：review" in detail._issue_queue_label.toolTip()
        assert "review 输出文件已存在" not in detail._issue_queue_label.text()
        assert "review 输出文件已存在" not in detail._issue_queue_label.toolTip()
    finally:
        detail.close()


def test_quick_execution_detail_logs_object_preflight_details():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_execution_result(
            ExecutionResultState(
                status="success",
                summary="本次执行已完成",
                object_preflight_summary="对象预检：2 项风险 · 跳过 1 个模块",
                object_preflight_details=[
                    "风险[warning] comments @ word/comments.xml: Comments are present.",
                    "跳过模块 section_format <- ole_objects",
                ],
                object_preflight={
                    "findings_count": 2,
                    "module_skips_count": 1,
                },
            )
        )

        log_text = detail._exec_log.toPlainText()
        assert "对象预检：2 项风险 · 跳过 1 个模块" in log_text
        assert (
            "对象预检明细：风险[warning] comments @ word/comments.xml: Comments are present."
            in log_text
        )
        assert "对象预检明细：跳过模块 section_format <- ole_objects" in log_text
    finally:
        detail.close()


def test_quick_execution_detail_exposes_object_preflight_issue_queue_on_confirmation():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_object_preflight_confirmation(
            ExecutionResultState(
                status="failed",
                summary="对象预检需确认",
                object_preflight_summary="对象预检：1 项风险 · 跳过 1 个模块",
                object_preflight_details=[
                    "风险[error] macros @ word/vbaProject.bin: Macros are present.",
                    "跳过模块 section_format <- macros",
                ],
                object_preflight={
                    "enabled": True,
                    "preservation_mode": "strict",
                    "scan_targets": ["macros"],
                    "findings_count": 1,
                    "blocking_findings_count": 1,
                    "findings": [
                        {
                            "kind": "macros",
                            "severity": "error",
                            "location": "word/vbaProject.bin",
                            "message": "Macros are present.",
                        }
                    ],
                    "module_skips_count": 1,
                    "module_skips": [
                        {
                            "module_name": "section_format",
                            "finding_kinds": ["macros"],
                        }
                    ],
                },
            ),
            blocked=True,
        )

        items = detail.current_issue_items()

        assert len(items) == 1
        assert items[0].issue_id == "object_preflight.finding.1.macros"
        assert items[0].severity == "error"
        assert items[0].blocking is True
        assert items[0].repair_target_type == "object_preflight"
        assert items[0].repair_target_key == "macros@word/vbaProject.bin"
        assert detail.current_issue_action_targets() == [
            ("object_preflight", "macros@word/vbaProject.bin")
        ]
        assert not detail._issue_queue_label.isHidden()
        assert detail._issue_queue_label.text().startswith("运行前问题 1 项：")
        assert "对象风险：macros：word/vbaProject.bin: Macros are present." in (
            detail._issue_queue_label.text()
        )
        assert "查看对象预检结果并确认处理方式" in (
            detail._issue_action_btn.toolTip()
        )
        assert "object_preflight:macros@word/vbaProject.bin" not in (
            detail._issue_action_btn.toolTip()
        )
        assert "风险[error] macros @ word/vbaProject.bin" in (
            detail._issue_queue_label.toolTip()
        )
    finally:
        detail.close()


def test_quick_execution_detail_runtime_template_overrides_stay_empty_without_advanced_controls():
    _app()
    detail = QuickExecutionDetail()
    try:
        assert not hasattr(detail, "_page_start_combo")
        assert detail.runtime_template_overrides() == {}
    finally:
        detail.close()


def test_quick_execution_detail_does_not_expose_visibility_rule_editing():
    _app()
    source = "C:/docs/source.docx"
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    changed = []
    detail = QuickExecutionDetail()
    try:
        detail.scene_config_changed.connect(lambda updated: changed.append(updated))
        detail._apply_scene(scene)
        detail.set_document_path(source)

        assert not hasattr(detail, "_visibility_selector_combo")
        assert not hasattr(detail, "_visibility_preset_combo")
        assert not hasattr(detail, "_visibility_add_rule_btn")
        assert changed == []
    finally:
        detail.close()


def test_quick_execution_detail_uses_shared_legacy_feature_group_map():
    module_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")

    assert LEGACY_FEATURE_GROUP_MAP == {
        "heading_numbering": "table_chart",
        "quick_fill": "content_fill",
    }
    assert "LEGACY_FEATURE_GROUP_MAP" in module_source
    assert "FEATURE_ID_ALIASES = {" not in module_source


def test_quick_execution_detail_derives_enabled_features_from_scene_switches():
    module_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_feature_enabled("content_fill", True)

        assert "FeatureToggleRow" not in module_source
        assert "FlowLayout" not in module_source
        assert "QGridLayout" not in module_source
        assert "content_fill" in detail.enabled_features()
    finally:
        detail.close()


def test_shared_dashed_separator_is_exported_for_reuse():
    separator_path = ROOT / "src/shared/ui/dashed_separator.py"
    assert separator_path.exists()

    separator_source = separator_path.read_text(encoding="utf-8")
    export_source = (ROOT / "src/shared/ui/__init__.py").read_text(encoding="utf-8")

    assert "class DashedSeparator" in separator_source
    assert '"DashedSeparator": (".dashed_separator", "DashedSeparator")' in export_source


def test_quick_execution_detail_does_not_use_advanced_separators():
    module_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")

    assert "DashedSeparator," not in module_source
    assert "class _DashedLine" not in module_source
    assert "class _DashedVLine" not in module_source
    assert "DashedSeparator(orientation=\"vertical\"" not in module_source
    assert "DashedSeparator(orientation=\"horizontal\"" not in module_source
    assert "_sep_structure_zones" not in module_source
    assert "dashed_color = t.divider" not in module_source
