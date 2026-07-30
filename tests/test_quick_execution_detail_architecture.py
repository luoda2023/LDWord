import inspect
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QDesktopServices, QFileDialog
from src.config.material_context import MaterialExecutionContext
from src.config.materials import AssetItem
from src.config.scene import SceneWorkspace
from src.shared.ui.theme import get_theme
from src.shared.ui.themed_radio_button import ThemedRadioButton
from src.ui.panels.workbench.state import (
    ArtifactItemState,
    ExecutionProgressState,
    ExecutionResultState,
)
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from src.ui.adapters.config_selector_models import plan_selector_options
from src.ui.panels.workbench.quick_execution_drop_area import QuickExecutionDropArea
from src.ui.panels.workbench.quick_execution_detail import QuickExecutionDetail
from src.ui.panels.workbench.quick_execution_feedback_mixin import (
    QuickExecutionFeedbackMixin,
)
from src.config.scene_engineering_summary import (
    build_scene_control_contract_summary,
    build_scene_parameter_ownership_summary,
    build_scene_product_readiness_summary,
    build_scene_request_cell_summary_text,
    build_scene_sample_coverage_summary_text,
)
from src.config.scene_presets import (
    LEGACY_FEATURE_GROUP_MAP,
    build_scene_summary,
    create_bidding_scene,
    create_exam_scene,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_quick_execution_detail_uses_presenter_and_authoritative_gate_logic():
    detail_source = inspect.getsource(QuickExecutionDetail)
    module_source = (
        ROOT / "src/ui/panels/workbench/quick_execution_detail.py"
    ).read_text(encoding="utf-8")
    result_presenter_source = (
        ROOT / "src/ui/panels/workbench/quick_execution_result_presenter.py"
    ).read_text(encoding="utf-8")
    feedback_module_source = (
        ROOT
        / "src/ui/panels/workbench/quick_execution_feedback_mixin.py"
    ).read_text(encoding="utf-8")
    feedback_source = inspect.getsource(QuickExecutionFeedbackMixin)
    source_presenter_source = (
        ROOT / "src/ui/panels/workbench/quick_execution_source_presenter.py"
    ).read_text(encoding="utf-8")

    assert "from .quick_execution_presenter import" in module_source
    assert "from .quick_execution_feedback_mixin import" in module_source
    assert "from src.ui.panels.workbench.quick_execution_result_presenter import" in (
        feedback_module_source
    )
    assert "from .quick_execution_source_presenter import" in module_source
    assert "from .quick_execution_drop_area import QuickExecutionDropArea" in module_source
    assert "from src.ui.adapters.workbench_execution_adapter import" not in module_source
    assert "from src.ui.adapters.workbench_artifact_items import" not in module_source
    assert "from src.ui.adapters.workbench_artifact_items import" in result_presenter_source
    assert "parse_exam_markdown_file" not in module_source
    assert "load_exam_markdown_source" in source_presenter_source
    assert "from src.ui.adapters.workbench_execution_gate import" in module_source
    assert "from src.ui.adapters.workbench_material_issues import" in module_source
    assert "build_navigation_snapshot(" in detail_source
    assert "build_feature_navigation_snapshot(" in detail_source
    assert "build_running_status(" in detail_source
    assert "build_exam_source_projection(" in detail_source
    assert "build_official_document_readiness_projection(" in detail_source
    assert "build_execution_result_presentation(" in feedback_source
    assert "def set_execution_result(" not in detail_source
    assert "material_readiness_gate_decision(" in detail_source
    assert "build_ready_status(" not in detail_source


def test_quick_execution_detail_retains_complete_terminal_payload():
    _app()
    detail = QuickExecutionDetail()
    try:
        state = ExecutionResultState(
            status="success",
            summary="done",
            terminal_payload={
                "exam_markdown_import": {"summary": {"question_count": 2}},
                "future_extension": {"kept": True},
            },
        )
        detail.set_execution_result(state)
        state.terminal_payload["future_extension"]["kept"] = False

        assert detail.last_terminal_payload()["exam_markdown_import"] == {
            "summary": {"question_count": 2}
        }
        assert detail.last_terminal_payload()["future_extension"] == {
            "kept": True
        }
    finally:
        detail.close()


def test_quick_execution_detail_fails_closed_on_non_plain_terminal_payload():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_execution_result(
            ExecutionResultState(
                status="success",
                summary="done",
                terminal_payload={
                    "status": "success",
                    "future_extension": {"lock": threading.Lock()},
                },
            )
        )

        payload = detail.last_terminal_payload()
        assert detail._last_result_status == "failed"
        assert payload["status"] == "failed"
        assert "$.future_extension.lock" in payload["error_text"]
        assert "_thread.lock" in payload["error_text"]
    finally:
        detail.close()


def test_quick_execution_detail_fails_closed_on_normalizer_runtime_error():
    _app()

    class _ExplodingMapping(dict):
        def items(self):
            raise RuntimeError("simulated mapping iteration failure")

    detail = QuickExecutionDetail()
    try:
        detail.set_execution_result(
            ExecutionResultState(
                status="success",
                summary="done",
                terminal_payload=_ExplodingMapping(status="success"),
            )
        )

        payload = detail.last_terminal_payload()
        assert detail._last_result_status == "failed"
        assert payload["status"] == "failed"
        assert "RuntimeError" in payload["error_text"]
        assert "simulated mapping iteration failure" in payload["error_text"]
    finally:
        detail.close()


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
            detail._material_preview,
            detail._output_card,
            detail._execution_card,
        ]
        for current, following in zip(widgets, widgets[1:]):
            assert following.y() - (current.y() + current.height()) == expected_gap
    finally:
        detail.close()
        app.processEvents()


def test_quick_execution_detail_only_owns_single_document_execution():
    _app()
    detail = QuickExecutionDetail()
    try:
        assert detail._execute_btn.text() == "选择文档并生成"
        assert not hasattr(detail, "_assistant_btn")
        assert not hasattr(detail, "_batch_execute_btn")
        assert not hasattr(detail, "_batch_retry_btn")
        assert not hasattr(detail, "assistant_requested")
        assert not hasattr(detail, "batch_execute_requested")
        assert detail._exec_status_area.minimumHeight() == detail._execute_btn.minimumHeight()
        assert detail._exec_status_area.maximumHeight() == detail._execute_btn.maximumHeight()
    finally:
        detail.close()


def test_quick_execution_detail_keeps_current_mode_authoritative_for_custom_scene():
    app = _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_work_mode("official")
        detail.set_scene_context(
            SceneWorkspace(
                scene_id="custom",
                category="custom",
                mode_id="custom",
                template_id="default",
            )
        )
        app.processEvents()

        assert detail._work_mode_id == "official"
        assert detail._is_official_document_scene() is True
        assert detail._is_exam_scene() is False
    finally:
        detail.close()
        app.processEvents()


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


def test_quick_execution_detail_invalidates_stale_result_when_input_changes(tmp_path):
    _app()
    detail = QuickExecutionDetail()
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"
    output = tmp_path / "output" / "final.docx"
    output.parent.mkdir()
    output.write_bytes(b"result")
    try:
        detail.set_document_path(str(first))
        detail.set_execution_result(
            ExecutionResultState(
                status="success",
                summary="执行完成",
                output_path=str(output),
            )
        )
        assert detail._last_result_status == "success"
        assert detail._result_receipt.isHidden() is False
        assert detail._exec_log.toPlainText()

        detail.set_document_path(str(second))

        assert detail._last_result_status == "idle"
        assert detail._result_receipt.isHidden() is True
        assert detail._exec_log.toPlainText() == ""
        assert detail._log_toggle_btn.isHidden() is True
        assert detail._execute_btn.text() == "生成文档"

        detail.set_execution_result(
            ExecutionResultState(
                status="success",
                summary="第二次执行完成",
                output_path=str(output),
            )
        )
        detail._on_floating_field_changed("title", "新标题")

        assert detail._last_result_status == "idle"
        assert detail._result_receipt.isHidden() is True
        assert detail._exec_log.toPlainText() == ""
    finally:
        detail.close()


def test_quick_execution_detail_shows_compact_result_receipt(
    monkeypatch,
    tmp_path,
):
    _app()
    detail = QuickExecutionDetail()
    output = tmp_path / "final.docx"
    output.write_bytes(b"result")
    opened: list[str] = []
    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    try:
        detail.set_execution_result(
            ExecutionResultState(
                status="success",
                summary="执行完成",
                output_path=str(output),
            )
        )

        assert detail._result_receipt.isHidden() is False
        assert detail._result_receipt_label.text() == "已生成：final.docx"
        assert detail._result_receipt_label.toolTip() == str(output)
        assert detail._open_result_btn.isEnabled() is True
        assert detail._open_result_folder_btn.isEnabled() is True
        assert detail._log_toggle_btn.text() == "查看全部产物与日志"

        detail._open_result_btn.click()
        detail._open_result_folder_btn.click()

        assert [Path(path) for path in opened] == [output, tmp_path]
    finally:
        detail.close()


def test_quick_execution_detail_shows_exam_source_assembly_card_only_for_exam_scene():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(SceneWorkspace(scene_id="custom", template_id="default"))
        assert detail._exam_source_card.isHidden()

        detail._apply_scene(create_exam_scene())
        assert not detail._exam_source_card.isHidden()
        assert detail._exam_source_summary.text() == "等待题稿"
        assert detail._exam_source_rows["source"][1].text() == "待上传 Markdown 题稿"
        assert detail._exam_source_rows["assembly"][1].text() == "按 Markdown 标题装配"
        assert detail._exam_source_rows["delivery"][1].text() == "学生卷 + 答案版"
        assert detail._exam_source_rows["fields"][1].text() == (
            "标题、科目、年级、考试时间、满分"
        )
        assert detail._exam_source_rows["fields"][0].text() == "状态"
        assert detail._drop_area._accepted_suffixes == (".md", ".markdown")
        assert detail._drop_area._hint_title.text() == (
            "上传 Markdown 题稿（支持格式：.md / .markdown）"
        )
    finally:
        detail.close()


def test_quick_execution_primary_picker_uses_active_scene_file_policy(
    monkeypatch,
    tmp_path,
):
    _app()
    detail = QuickExecutionDetail()
    source = tmp_path / "paper.md"
    source.write_text("# 试卷", encoding="utf-8")
    observed_filters: list[str] = []

    def _pick(*args):
        observed_filters.append(str(args[3]))
        return str(source), args[3]

    try:
        detail._apply_scene(create_exam_scene())
        monkeypatch.setattr(QFileDialog, "getOpenFileName", _pick)

        assert detail.pick_document_path() == str(source)
        assert detail.document_path() == str(source)
        assert len(observed_filters) == 1
        assert observed_filters[0].startswith("Markdown 文件 (*.md *.markdown)")
    finally:
        detail.close()


def test_quick_execution_detail_exam_source_card_avoids_unverified_question_counts():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(create_exam_scene())
        detail.set_document_path("C:/docs/final_exam.docx")

        source_text = detail._exam_source_rows["source"][1].text()
        card_text = "\n".join(
            [detail._exam_source_summary.text()]
            + [
                value.text()
                for _key, value in detail._exam_source_rows.values()
            ]
        )

        assert "当前试卷入口仅支持 Markdown 题稿" in source_text
        assert "大题" not in card_text
        assert "小题" not in card_text
        assert "已识别" not in card_text

        detail.set_document_path("C:/docs/final_exam.json")
        assert detail._exam_source_rows["source"][1].text() == (
            "当前试卷入口仅支持 Markdown 题稿：final_exam.json"
        )
    finally:
        detail.close()


def test_quick_execution_detail_exam_source_card_shows_markdown_counts(tmp_path):
    _app()
    source = tmp_path / "final_exam.md"
    source.write_text(
        """# 七年级数学单元测试

> 科目：数学　年级：七年级　考试时间：45 分钟　满分：10 分

## 一、选择题

1. 1 + 1 = （　　）（5 分）
   A. 1
   B. 2

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
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(create_exam_scene())
        detail.set_document_path(str(source))

        assert detail._exam_source_summary.text() == "已识别 2 大题 / 2 小题"
        assert detail._exam_source_rows["source"][1].text() == (
            "Markdown 题稿：final_exam.md"
        )
        assert "2 大题 / 2 小题" in detail._exam_source_rows["assembly"][1].text()
        assert "分值：声明 10 / 计算 10" in detail._exam_source_rows["assembly"][1].text()
        assert detail._exam_source_rows["fields"][1].text() == (
            "答案 2/2；解析 0/2；可生成"
        )
    finally:
        detail.close()


def test_quick_execution_detail_reports_compact_ready_status_and_navigation_snapshot():
    _app()
    detail = QuickExecutionDetail()
    try:
        assert detail._status_label is detail._exec_status_label
        assert detail._status_label.text() == "请选择或拖入输入文档"
        assert detail.navigation_snapshot() == {
            "subtitle": "未选择文档 · 默认流程",
            "badge_text": "待补充",
            "badge_variant": "warning",
        }

        detail.set_document_path("C:/docs/report.docx")
        detail.set_strategy_context(template_name="汇报演示", strict_mode=False)
        detail.set_feature_enabled("content_fill", True)

        assert detail._active_template_label() == "汇报演示"
        assert detail._status_label.text() == "可生成"
        assert detail._execute_btn.isEnabled() is True
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


def test_quick_execution_default_plan_never_projects_an_empty_template():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_work_mode("custom")

        assert detail._scene_combo.currentText().strip()
        assert detail._template_combo.count() >= 1
        assert detail._template_combo.currentText().strip() == "默认格式"
        assert detail.current_template_id() == "default"
    finally:
        detail.close()


def test_quick_execution_detail_reports_material_schema_as_nonblocking_warning():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_document_path("C:/docs/report.docx")
        detail.current_scene().input_source_profile.material_schema_id = (
            "missing_schema_v1"
        )
        detail.current_scene().input_source_profile.failure_policy = "warn"
        detail._emit_summary_changed()

        decision = detail.current_execution_gate_decision()
        assert decision.state == "warning"
        assert decision.can_run is True
        assert decision.blocking_reasons == ()
        assert decision.warning_reasons == (
            "资料 Schema 未注册：missing_schema_v1",
        )
        assert detail._status_label.text() == "可生成；部分信息将使用默认值"
        assert detail._status_label.toolTip() == (
            "资料 Schema 未注册：missing_schema_v1"
        )
        assert detail._execute_btn.isEnabled() is True
        assert detail._material_repair_btn.text() == "补充信息（可选）"
    finally:
        detail.close()

def test_quick_execution_detail_official_readiness_shows_plan_profile_master_template_and_fields():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_work_mode("official")

        assert detail._exam_source_card.isHidden() is False
        assert detail._exam_source_card._title_label.text() == "公文资料与装配"
        assert detail._exam_source_summary.text() == "公文执行前检查：5 个方案字段未绑定"

        row_labels = {
            key: label.text()
            for key, (label, _value) in detail._exam_source_rows.items()
        }
        row_values = {
            key: value.text()
            for key, (_label, value) in detail._exam_source_rows.items()
        }

        assert row_labels == {
            "source": "处理方案",
            "assembly": "文种",
            "delivery": "版式 / 模板",
            "fields": "资料字段",
        }
        assert row_values["source"] == "公文基础方案"
        assert row_values["assembly"] == "通知 (notice)"
        assert "GB/T 9704 通用红头公文版式" in row_values["delivery"]
        assert "GB/T 9704 公文格式" in row_values["delivery"]
        assert row_values["fields"] == (
            "当前方案需要 5 项 · 已映射 0 项 · 已填写 0 项 · "
            "未绑定 5 项：标题、正文、发文机关、发文字号、成文日期"
        )

        detail.set_material_context(
            MaterialExecutionContext(
                profile_id="official:notice",
                field_scopes={
                    "organization": "fixed",
                    "title": "floating",
                    "body": "floating",
                    "document_no": "floating",
                    "issue_date": "floating",
                },
                entity_data={
                    "document_type": "notice",
                    "title": "关于召开项目推进会的通知",
                    "body": "请各单位按时参会。",
                    "organization": "示例办公室",
                    "document_no": "示办发〔2026〕1号",
                    "issue_date": "2026年7月10日",
                },
            )
        )

        assert detail._exam_source_summary.text() == "公文执行前检查：必填字段已齐"
        assert (
            detail._exam_source_rows["fields"][1].text()
            == "当前方案需要 5 项 · 已映射 5 项 · 已填写 5 项 · "
            "自由字段 4/4 已填写"
        )
        assert detail._floating_fields_card.isHidden() is False
        assert list(detail._floating_field_inputs) == [
            "title",
            "body",
            "document_no",
            "issue_date",
        ]
        assert detail._floating_field_name_labels["title"].text() == "{{@text:标题1}}"
        assert detail._floating_fields_progress.text() == "已完成 4/4"
        assert detail._floating_field_inputs["body"]._editor_kind == "multiline"
        assert detail._floating_field_inputs["issue_date"]._editor_kind == "date"

        changed_contexts = []
        detail.material_context_changed.connect(changed_contexts.append)
        detail._floating_field_inputs["title"].setText("新的通知标题")
        assert detail._floating_field_name_labels["title"].text() == "{{@text:标题1}}"
        assert changed_contexts[-1].entity_data["title"] == "新的通知标题"
    finally:
        detail.close()


def test_quick_execution_free_fields_keep_same_rows_when_context_values_refresh():
    app = _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_work_mode("official")
        detail.set_material_context(
            MaterialExecutionContext(
                profile_id="official:notice",
                field_scopes={"title": "floating", "body": "floating"},
                entity_data={"title": "旧标题", "body": "旧正文"},
            )
        )
        app.processEvents()

        original_rows = dict(detail._floating_field_rows)
        original_inputs = dict(detail._floating_field_inputs)
        original_labels = dict(detail._floating_field_name_labels)

        detail.set_material_context(
            MaterialExecutionContext(
                profile_id="official:notice",
                field_scopes={"title": "floating", "body": "floating"},
                entity_data={"title": "新标题", "body": "新正文"},
            )
        )
        app.processEvents()

        assert list(detail._floating_field_rows) == ["title", "body"]
        assert all(
            detail._floating_field_rows[key] is original_rows[key]
            for key in original_rows
        )
        assert all(
            detail._floating_field_inputs[key] is original_inputs[key]
            for key in original_inputs
        )
        assert all(
            detail._floating_field_name_labels[key] is original_labels[key]
            for key in original_labels
        )
        assert detail._floating_field_inputs["title"].text() == "新标题"
        assert detail._floating_field_inputs["body"].text() == "新正文"
    finally:
        detail.close()


def test_quick_execution_detail_official_document_type_is_independent_from_plan():
    app = _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_work_mode("official")

        official_index = detail._scene_combo.findData("official")
        assert official_index >= 0
        detail._scene_combo.setCurrentIndex(official_index)
        app.processEvents()
        assert detail._scene_combo.currentData() == "official"
        assert [
            detail._document_type_combo.itemData(index)
            for index in range(detail._document_type_combo.count())
        ] == ["notice", "letter", "minutes", "report", "request", "approval"]

        letter_index = detail._document_type_combo.findData("letter")
        assert letter_index >= 0
        detail._document_type_combo.setCurrentIndex(letter_index)
        app.processEvents()

        assert detail.current_scene().scene_id == "official"
        assert detail._exam_source_rows["source"][1].text() == "公文基础方案"
        assert detail._exam_source_rows["assembly"][1].text() == "函 (letter)"

        minutes_index = detail._document_type_combo.findData("minutes")
        assert minutes_index >= 0
        detail._document_type_combo.setCurrentIndex(minutes_index)
        app.processEvents()

        assert detail.current_scene().scene_id == "official"
        assert detail._exam_source_rows["source"][1].text() == "公文基础方案"
        assert detail._exam_source_rows["assembly"][1].text() == "纪要 (minutes)"
        assert "GB/T 9704 纪要格式" in detail._exam_source_rows["delivery"][1].text()

        for profile_id, profile_label in (
            ("report", "报告"),
            ("request", "请示"),
            ("approval", "批复"),
        ):
            index = detail._document_type_combo.findData(profile_id)
            assert index >= 0
            detail._document_type_combo.setCurrentIndex(index)
            app.processEvents()

            assert detail.current_scene().scene_id == "official"
            assert detail._exam_source_rows["source"][1].text() == "公文基础方案"
            assert detail._exam_source_rows["assembly"][1].text() == (
                f"{profile_label} ({profile_id})"
            )
    finally:
        detail.close()


def test_quick_execution_detail_material_profile_does_not_override_task_document_type():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_work_mode("official")
        scene = detail.current_scene()

        assert scene.scene_id == "official"
        assert scene.default_material_profile_id == "official:notice"

        detail.set_material_context(
            MaterialExecutionContext(
                profile_id="official:letter",
                field_scopes={
                    "title": "floating",
                    "body": "floating",
                    "organization": "fixed",
                    "document_no": "floating",
                    "issue_date": "floating",
                },
                entity_data={
                    "document_type": "letter",
                    "title": "Letter title",
                    "body": "Letter body",
                    "organization": "Archive Office",
                    "document_no": "A-2026-1",
                    "issue_date": "2026-07-10",
                    "recipient": "Project unit",
                },
            )
        )

        assert detail.current_scene() is scene
        assert detail.current_scene().scene_id == "official"
        assert detail.current_scene().default_material_profile_id == "official:notice"
        assert detail._exam_source_rows["source"][1].text() == "公文基础方案"
        assert detail._exam_source_rows["assembly"][1].text() == "通知 (notice)"
        assert detail._exam_source_summary.text() == "公文执行前检查：必填字段已齐"
    finally:
        detail.close()


def test_quick_execution_detail_does_not_treat_unscoped_entity_values_as_mapped_fields():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_work_mode("official")
        detail.set_material_context(
            MaterialExecutionContext(
                profile_id="official:notice",
                entity_data={
                    "title": "Unscoped title",
                    "body": "Unscoped body",
                    "organization": "Unscoped office",
                    "document_no": "UNSCOPED-1",
                    "issue_date": "2026-07-14",
                },
            )
        )

        assert detail._exam_source_summary.text() == "公文执行前检查：5 个方案字段未绑定"
        assert "已映射 0 项" in detail._exam_source_rows["fields"][1].text()
    finally:
        detail.close()


def test_quick_execution_detail_official_missing_fields_use_compact_warn_gate():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail.set_work_mode("official")
        detail.set_document_path("C:/docs/notice.docx")

        decision = detail.current_execution_gate_decision()
        assert decision.state == "warning"
        assert decision.can_run is True
        assert decision.blocking_reasons == ()
        assert decision.primary_action is not None
        assert decision.primary_action.target_type == "field"
        assert decision.primary_action.target_key == "title"
        assert decision.warning_reasons == (
            "资料字段缺失：title, body, organization, document_no, issue_date",
        )
        assert detail._exec_status_label.text() == "可生成；部分信息将使用默认值"
        assert detail._execute_btn.isEnabled() is True
        assert detail._material_repair_btn.text() == "补充信息（可选）"
        assert "字段：title, body, organization, document_no, issue_date" in (
            detail._material_repair_btn.toolTip()
        )
    finally:
        detail.close()

def test_quick_execution_detail_plan_combo_uses_current_work_mode_options():
    _app()
    detail = QuickExecutionDetail()
    try:
        for mode_id in ("exam", "official", "bidding", "thesis"):
            detail.set_work_mode(mode_id)
            actual_values = [
                detail._scene_combo.itemData(index)
                for index in range(detail._scene_combo.count())
            ]
            expected_values = [
                option.value for option in plan_selector_options(mode_id)
            ]

            assert actual_values == expected_values
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


def test_quick_execution_detail_compact_gate_covers_ready_warn_block_and_confirm():
    _app()
    detail = QuickExecutionDetail()
    try:
        ready_scene = SceneWorkspace(scene_id="custom", template_id="default")
        detail._apply_scene(ready_scene)
        detail.set_document_path("C:/docs/ready.docx")
        decision = detail.current_execution_gate_decision()
        assert decision.state == "ready"
        assert decision.ready_to_start is True
        assert detail._exec_status_label.text() == "可生成"
        assert detail._execute_btn.isEnabled() is True
        assert detail._material_repair_btn.isHidden() is True

        warn_scene = create_exam_scene()
        warn_scene.input_source_profile.material_schema_id = "exam_items_v1"
        warn_scene.input_source_profile.failure_policy = "warn"
        detail._apply_scene(warn_scene)
        detail.set_document_path("C:/docs/warn.docx")
        decision = detail.current_execution_gate_decision()
        assert decision.state == "warning"
        assert decision.can_run is True
        assert decision.warning_reasons
        assert detail._exec_status_label.text() == "可生成；部分信息将使用默认值"
        assert detail._execute_btn.isEnabled() is True
        assert detail._material_repair_btn.text() == "补充信息（可选）"

        detail._apply_scene(create_bidding_scene())
        detail.set_document_path("C:/docs/block.docx")
        decision = detail.current_execution_gate_decision()
        assert decision.state == "blocked"
        assert decision.can_run is False
        assert decision.blocking_reasons
        assert detail._exec_status_label.text() == "无法生成：缺少必需资料"
        assert detail._execute_btn.isEnabled() is False
        assert detail._material_repair_btn.text() == "去补齐"

        confirm_scene = create_bidding_scene()
        confirm_scene.input_source_profile.failure_policy = "confirm"
        detail._apply_scene(confirm_scene)
        detail.set_document_path("C:/docs/confirm.docx")
        decision = detail.current_execution_gate_decision()
        assert decision.state == "confirmation"
        assert decision.can_run is True
        assert decision.requires_confirmation is True
        assert detail._exec_status_label.text() == "生成前需确认资料缺口"
        assert detail._execute_btn.text() == "确认并生成"
        assert detail._execute_btn.isEnabled() is True
    finally:
        detail.close()


def test_quick_execution_detail_static_audits_do_not_enter_execution_gate():
    module_source = (
        ROOT / "src/ui/panels/workbench/quick_execution_detail.py"
    ).read_text(encoding="utf-8")
    static_audit_builders = (
        "coverage_boundary_issue_items",
        "parameter_ownership_issue_items",
        "sample_fixture_issue_items",
        "control_contract_issue_items",
    )
    assert all(name not in module_source for name in static_audit_builders)

    _app()
    detail = QuickExecutionDetail()
    try:
        scene = SceneWorkspace(
            scene_id="exam_teaching",
            category="exam_teaching",
            template_id="default",
        )
        detail._apply_scene(scene)
        detail.set_document_path("C:/docs/exam.docx")
        decision = detail.current_execution_gate_decision()
        assert decision.state == "ready"
        assert detail._exec_status_label.text() == "可生成"
        assert "插件" not in detail._exec_status_label.text()
        assert "边界" not in detail._exec_status_label.toolTip()
    finally:
        detail.close()


def test_quick_execution_detail_removes_inline_issue_management_controls():
    module_source = (
        ROOT / "src/ui/panels/workbench/quick_execution_detail.py"
    ).read_text(encoding="utf-8")
    removed_members = (
        "_issue_panel",
        "_issue_panel_body",
        "_issue_list",
        "_issue_detail_panel",
        "_issue_filter_combo",
        "_issue_action_group_combo",
        "_issue_resolve_btn",
        "_issue_ignore_btn",
        "issue_repair_requested",
        "current_issue_items",
        "set_issue_queue_filter",
    )

    _app()
    detail = QuickExecutionDetail()
    try:
        assert all(not hasattr(detail, name) for name in removed_members)
        assert all(name not in module_source for name in removed_members)
        assert "已处理" not in module_source
        assert "忽略" not in module_source
    finally:
        detail.close()


def test_quick_execution_detail_preflight_does_not_expand_execution_card_inline():
    app = _app()
    detail = QuickExecutionDetail()
    try:
        detail.resize(1080, 900)
        detail.show()
        app.processEvents()
        before_height = detail._execution_card.sizeHint().height()

        detail._apply_scene(create_bidding_scene())
        detail.set_document_path("C:/docs/bid.docx")
        app.processEvents()
        after_height = detail._execution_card.sizeHint().height()

        assert detail.current_execution_gate_decision().state == "blocked"
        assert after_height <= before_height + get_theme().control_height_sm
        assert detail._exec_log.isHidden() is True
        assert not hasattr(detail, "_issue_panel")
    finally:
        detail.close()


def test_quick_execution_detail_markdown_metadata_satisfies_exam_gate(tmp_path):
    source = tmp_path / "exam.md"
    source.write_text(
        """# 七年级数学单元测试

> 科目：数学　年级：七年级　考试时间：45 分钟　满分：10 分

## 一、选择题

1. 1 + 1 = （　　）（10 分）
   A. 1
   B. 2
""",
        encoding="utf-8",
    )
    _app()
    detail = QuickExecutionDetail()
    try:
        exam_scene = create_exam_scene()
        exam_scene.input_source_profile.material_schema_id = "exam_items_v1"
        exam_scene.input_source_profile.failure_policy = "warn"
        detail._apply_scene(exam_scene)
        detail.set_document_path(str(source))
        decision = detail.current_execution_gate_decision()
        assert decision.state == "ready"
        assert decision.warning_reasons == ()
        assert decision.blocking_reasons == ()
        assert detail._material_readiness_issues.has_issues is False
        assert detail._exec_status_label.text() == "可生成"
        assert detail._execute_btn.isEnabled() is True
        assert detail._material_repair_btn.isHidden() is True
    finally:
        detail.close()


def test_quick_execution_detail_exposes_one_material_cta_only():
    _app()
    detail = QuickExecutionDetail()
    requested: list[tuple[str, str]] = []
    try:
        detail.material_repair_requested.connect(
            lambda target_type, target_key: requested.append(
                (target_type, target_key)
            )
        )
        detail._apply_scene(create_bidding_scene())
        detail.set_document_path("C:/docs/bid.docx")
        assert detail._material_repair_btn.text() == "去补齐"
        assert detail._material_repair_btn.isHidden() is False
        assert not hasattr(detail, "_result_details_btn")
        assert detail._object_preflight_cancel_btn.isHidden() is True
        assert not hasattr(detail, "_issue_action_btn")

        detail._material_repair_btn.click()
        assert requested == [("field", "company_name")]
    finally:
        detail.close()


def test_quick_execution_detail_log_is_collapsed_until_requested_or_failed():
    _app()
    detail = QuickExecutionDetail()
    try:
        assert detail._exec_log.isHidden() is True
        assert detail._log_toggle_btn.isHidden() is True
        detail.set_execution_progress(
            ExecutionProgressState(
                stage_text="解析文档",
                current_step=1,
                total_steps=2,
            )
        )
        detail.set_execution_progress(
            ExecutionProgressState(
                stage_text="解析文档",
                current_step=2,
                total_steps=3,
            )
        )
        assert detail._log_toggle_btn.isHidden() is False
        assert detail._exec_log.isHidden() is True
        assert detail._log_toggle_btn.text() == "查看执行日志"
        assert detail._exec_log.toPlainText().count("执行阶段：解析文档") == 1

        detail._log_toggle_btn.click()
        assert detail._exec_log.isHidden() is False
        assert detail._log_toggle_btn.text() == "收起执行日志"

        detail._log_toggle_btn.click()
        detail.set_execution_result(
            ExecutionResultState(status="success", summary="执行完成")
        )
        assert detail._exec_log.isHidden() is True

        detail.set_execution_result(
            ExecutionResultState(
                status="failed",
                summary="执行失败",
                error_text="模板不可用",
            )
        )
        assert detail._exec_log.isHidden() is False
        assert detail._log_toggle_btn.text() == "收起执行日志"
    finally:
        detail.close()


def test_quick_execution_detail_runtime_cancel_is_one_shot_and_neutral():
    _app()
    detail = QuickExecutionDetail()
    runtime_cancelled: list[bool] = []
    preflight_cancelled: list[bool] = []
    try:
        detail.cancel_requested.connect(lambda: runtime_cancelled.append(True))
        detail.object_preflight_cancel_requested.connect(
            lambda: preflight_cancelled.append(True)
        )

        assert detail._execution_cancel_btn.isHidden() is True
        assert detail._object_preflight_cancel_btn.isHidden() is True

        detail.set_execution_progress(
            ExecutionProgressState(
                stage_text="解析文档",
                current_step=1,
                total_steps=3,
            )
        )

        assert detail._execution_cancel_btn.isHidden() is False
        assert detail._execution_cancel_btn.isEnabled() is True
        assert detail._execution_cancel_btn.text() == "取消生成"
        assert detail._object_preflight_cancel_btn.isHidden() is True

        detail._execution_cancel_btn.click()
        detail._execution_cancel_btn.click()

        assert runtime_cancelled == [True]
        assert preflight_cancelled == []
        assert detail._execution_cancel_btn.isEnabled() is False
        assert detail._execution_cancel_btn.text() == "正在取消..."
        assert detail._exec_status_label.text() == "正在取消，请稍候…"

        # Late progress must not make cancellation appear reversible.
        detail.set_execution_progress(
            ExecutionProgressState(
                stage_text="写入临时产物",
                current_step=2,
                total_steps=3,
            )
        )
        assert detail._execution_cancel_btn.isEnabled() is False
        assert detail._execution_cancel_btn.text() == "正在取消..."
        assert detail._exec_status_label.text() == "正在取消，请稍候…"

        detail.set_execution_result(
            ExecutionResultState(
                status="cancelled",
                summary="已取消",
                error_text="cancelled by user",
            )
        )

        assert detail._exec_status_label.text() == "已取消"
        assert detail._execution_cancel_btn.isHidden() is True
        assert detail._exec_error_count == 0
        assert detail._exec_log.isHidden() is True
        assert detail.navigation_snapshot()["badge_text"] == "已取消"
        assert detail.navigation_snapshot()["badge_variant"] == "neutral"

        detail.set_object_preflight_confirmation(
            ExecutionResultState(
                status="failed",
                summary="对象预检需确认",
                object_preflight={"findings_count": 1},
            ),
            blocked=False,
        )
        assert detail._execution_cancel_btn.isHidden() is True
        assert detail._object_preflight_cancel_btn.isHidden() is False
        detail._object_preflight_cancel_btn.click()
        assert runtime_cancelled == [True]
        assert preflight_cancelled == [True]
    finally:
        detail.close()

def test_quick_execution_detail_updates_compact_gate_from_material_context():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(create_bidding_scene())
        detail.set_document_path("C:/docs/bid.docx")
        before = detail.current_execution_gate_decision()
        assert before.state == "blocked"
        assert detail._status_label.text() == "无法生成：缺少必需资料"
        assert detail._execute_btn.isEnabled() is False

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
        after = detail.current_execution_gate_decision()
        assert after.state == "ready"
        assert detail._status_label.text() == "可生成"
        assert detail._execute_btn.isEnabled() is True
        assert detail._material_repair_btn.isHidden() is True
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


def test_quick_execution_scene_summary_separates_product_and_engineering_details():
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
        assert "参数归属" not in shared_summary
        assert "控件契约" not in shared_summary
        assert "产品成熟度" not in shared_summary
        assert "样本覆盖" not in shared_summary
        assert "常见说法" not in shared_summary

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
        assert request_cell_summary.startswith("常见说法")
        assert (
            "已守门" in request_cell_summary
            or "个缺口" in request_cell_summary
        )
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
        assert not hasattr(detail, "_advanced_card")
        assert not hasattr(detail, "_zone_checks")
        assert not hasattr(detail.current_scene(), "format_scope")
        assert not hasattr(detail, "_strategy_rebuild")

        detail.set_feature_enabled("content_fill", True)

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


def test_quick_execution_detail_warns_when_optional_review_pdf_is_unavailable():
    _app()
    detail = QuickExecutionDetail()
    adapter = WorkbenchExecutionAdapter()
    try:
        state = adapter.build_result_state(
            terminal_payload={
                "status": "success",
                "output_path": "C:/tmp/official.docx",
                "output_paths": {"official_docx": "C:/tmp/official.docx"},
                "report_paths": [],
                "failed_count": 0,
                "error_text": "",
                "official_document_assembly": {
                    "status": "ok",
                    "review_pdf_status": "renderer_unavailable",
                    "review_pdf_path": "",
                    "review_pdf_renderer": "",
                    "review_pdf_issue": "docx_to_pdf_renderer_unavailable",
                },
            },
        )

        warning = next(
            item for item in state.artifact_items if item.group_id == "review_pdf"
        )
        assert warning.label == "审阅 PDF"
        assert warning.path == ""
        assert warning.status == "warning"
        assert "当前环境没有可用" in warning.detail
        assert "正式公文仍已生成" in warning.detail

        detail.set_execution_result(state)
        log_text = detail._exec_log.toPlainText()
        assert "输出文件[正式公文]：C:/tmp/official.docx" in log_text
        assert "产物预检[审阅 PDF]" in log_text
        assert "当前环境没有可用" in log_text
    finally:
        detail.close()


def test_quick_execution_detail_keeps_result_feedback_inline():
    _app()
    detail = QuickExecutionDetail()
    adapter = WorkbenchExecutionAdapter()
    try:
        state = adapter.build_result_state(
            terminal_payload={
                "status": "success",
                "output_path": "C:/tmp/source.docx",
                "output_paths": {"review": "C:/tmp/review.docx"},
                "report_paths": [],
                "failed_count": 0,
                "error_text": "",
                "output_target_preflight": {
                    "items": [
                        {
                            "preset_id": "review",
                            "path": "C:/tmp/review.docx",
                            "issues": [
                                {
                                    "kind": "target_exists",
                                    "message": (
                                        "review 输出文件已存在，将被覆盖: "
                                        "C:/tmp/review.docx"
                                    ),
                                }
                            ],
                        }
                    ]
                },
            },
        )
        detail.set_execution_result(state)

        assert detail._exec_status_label.text() == "✓ 本次生成完成；1 项提醒"
        assert detail._exec_bar.isHidden() is True
        assert detail._execute_btn.text() == "重新生成"
        assert not hasattr(detail, "_result_details_btn")
        assert not hasattr(detail, "result_details_requested")
        assert detail._material_repair_btn.isHidden() is True
        assert not hasattr(detail, "current_issue_items")

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


def test_quick_execution_detail_uses_compact_object_preflight_confirmation():
    _app()
    detail = QuickExecutionDetail()
    cancelled: list[bool] = []
    state = ExecutionResultState(
        status="failed",
        summary="对象预检需确认",
        object_preflight_summary="对象预检：1 项风险 · 跳过 1 个模块",
        object_preflight_details=[
            "风险[warning] comments @ word/comments.xml: Comments are present.",
            "跳过模块 section_format <- comments",
        ],
        object_preflight={
            "enabled": True,
            "preservation_mode": "warn",
            "findings_count": 1,
            "blocking_findings_count": 0,
            "module_skips_count": 1,
        },
    )
    try:
        detail.object_preflight_cancel_requested.connect(
            lambda: cancelled.append(True)
        )
        detail.set_object_preflight_confirmation(state, blocked=False)
        assert detail._exec_status_label.text() == (
            "检测到 1 个对象风险，继续后将跳过 1 个模块"
        )
        assert detail._execute_btn.text() == "确认并继续"
        assert detail._execute_btn.isEnabled() is True
        assert detail._object_preflight_cancel_btn.isHidden() is False
        assert detail._log_toggle_btn.text() == "查看 1 项对象风险"
        assert detail._material_repair_btn.isHidden() is True
        assert not hasattr(detail, "_result_details_btn")
        assert not hasattr(detail, "_issue_panel")
        assert not hasattr(detail, "current_issue_items")

        detail._object_preflight_cancel_btn.click()
        assert cancelled == [True]

        blocked_state = ExecutionResultState(
            status="failed",
            summary="对象预检未通过",
            object_preflight={"findings_count": 1},
        )
        detail.set_object_preflight_confirmation(blocked_state, blocked=True)
        assert detail._exec_status_label.text() == "无法生成：检测到 1 个高风险对象"
        assert detail._execute_btn.text() == "重新检查"
        assert detail._execute_btn.isEnabled() is True
        assert detail._object_preflight_cancel_btn.isHidden() is True
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
