# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.engine.scene_sample_docx_builder import build_scene_sample_docx_library
from src.shared.ui.style_management_block import StyleManagementBlock
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.style_receipt_slot_frame import StyleReceiptSlotFrame
from src.ui.panels.workbench import recent_run_panel
from src.ui.panels.workbench.recent_run_panel import RecentRunPanel
from src.ui.panels.workbench.state import ArtifactItemState, RecentRunState


def _app():
    return QApplication.instance() or QApplication([])


def test_recent_run_panel_routes_style_receipt_through_style_object_projection():
    source = (ROOT / "src/ui/panels/workbench/recent_run_panel.py").read_text(
        encoding="utf-8"
    )

    assert "build_execution_style_projection" in source
    assert "apply_style_object_projection(style_projection)" in source
    assert "effective_style_source_envelope" not in source
    assert "_style_receipt_slot.apply_envelope" not in source


def test_recent_run_panel_default_summary_text():
    _app()
    panel = RecentRunPanel()
    try:
        assert panel.objectName() == "wb_recent_run"
        assert panel._title_label.text() == "最近结果"
        assert panel._summary.text() == "暂无最近结果"
        assert panel._artifact_list.isVisible() is False
        assert isinstance(panel._style_review_block, StyleManagementBlock)
        assert panel._style_review_block.isHidden() is True
        assert panel._style_review_block.property("style_management_mode") == (
            "execution_receipt_review"
        )
        assert panel._style_review_block.property("style_management_content_plan") == (
            "receipt"
        )
        assert isinstance(panel._style_receipt_slot, StyleReceiptSlotFrame)
        assert panel._style_receipt_slot.isHidden() is True
        assert panel._style_review_block.receipt_slot is panel._style_receipt_slot
        assert panel._style_receipt_slot.property("style_management_mode") == (
            "execution_receipt_review"
        )
        assert panel._style_receipt_slot.property("style_management_content_plan") == (
            "receipt"
        )
        assert panel._style_receipt_slot.property("style_receipt_slot_surface") == (
            "embedded"
        )
        assert panel._style_receipt_slot.receipt_row is panel._style_receipt_row
    finally:
        panel.close()


def test_recent_run_panel_updates_summary_text():
    _app()
    panel = RecentRunPanel()
    try:
        panel.set_summary("已完成运行")
        assert panel._summary.text() == "已完成运行"
    finally:
        panel.close()


def test_recent_run_panel_wraps_long_summary():
    _app()
    panel = RecentRunPanel()
    try:
        long_text = "这是一段非常非常长的总结文本，应该在面板中正确换行显示而不会破坏布局。"
        panel.set_summary(long_text)
        assert panel._summary.text() == long_text
        assert panel._summary.wordWrap()
    finally:
        panel.close()


def test_recent_run_panel_accepts_recent_run_state_and_renders_summary():
    _app()
    panel = RecentRunPanel()
    try:
        panel.set_summary("旧的摘要")

        state = RecentRunState(
            status="success",
            title="最近结果",
            summary="本次执行已完成",
            output_label="out.docx",
            report_label="report.json",
            error_summary="",
        )
        panel.set_state(state)

        assert panel._summary.text() == "本次执行已完成"
    finally:
        panel.close()


def test_recent_run_panel_includes_material_field_consistency_summary():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="success",
            summary="本次执行已完成",
            material_field_consistency_summary="字段一致性：contract_parties_v1 · 1 项风险",
        )

        panel.set_state(state)

        assert panel._summary.text() == (
            "本次执行已完成\n字段一致性：contract_parties_v1 · 1 项风险"
        )
    finally:
        panel.close()


def test_recent_run_panel_includes_style_source_summary():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="success",
            summary="本次执行已完成",
            style_source_summary="样式来源：本次使用模板“默认格式”。",
        )

        panel.set_state(state)

        assert panel._summary.text() == "本次执行已完成"
        assert panel._style_review_block.isHidden() is False
        assert panel._style_receipt_slot.isHidden() is False
        assert panel._style_receipt_slot.has_receipt() is True
        assert panel._style_receipt_row.isHidden() is False
        assert panel._style_receipt_row.summary_text() == (
            "样式来源：本次使用模板“默认格式”。"
        )
        assert panel._style_receipt_row.detail.text() == (
            "本次使用模板“默认格式”。"
        )
    finally:
        panel.close()


def test_recent_run_panel_accepts_style_source_envelope():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="success",
            summary="本次执行已完成",
            style_source_envelope=StylePresentationEnvelope(
                kind="execution_receipt",
                title="样式来源",
                summary="本次使用模板“默认格式”。",
            ),
        )

        panel.set_state(state)

        assert panel._style_receipt_row.summary_text() == (
            "样式来源：本次使用模板“默认格式”。"
        )
        assert panel._style_review_block.isHidden() is False
        assert panel._style_review_block.property("style_object_kind") == "execution_style"
        assert panel._style_review_block.property("style_object_label") == "样式回执"
        assert panel._style_review_block.property("style_object_source_label") == "本次使用"
        assert panel._style_review_block.property("style_object_scope_label") == "执行结果"
        assert panel._style_review_block.property("style_object_edit_state_label") == "只读"
        assert panel._style_receipt_row.property("style_presentation_kind") == (
            "execution_receipt"
        )
    finally:
        panel.close()


def test_recent_run_panel_hides_receipt_slot_without_style_source():
    _app()
    panel = RecentRunPanel()
    try:
        panel.set_state(
            RecentRunState(
                status="success",
                summary="本次执行已完成",
            )
        )

        assert panel._summary.text() == "本次执行已完成"
        assert panel._style_receipt_row.isHidden() is True
        assert panel._style_receipt_slot.isHidden() is True
        assert panel._style_review_block.isHidden() is True
        assert panel._style_review_block.property("style_object_kind") == "execution_style"
    finally:
        panel.close()


def test_recent_run_panel_includes_object_preflight_summary():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="success",
            summary="本次执行已完成",
            object_preflight_summary="对象预检：2 项风险 · 跳过 1 个模块",
            object_preflight_details=[
                "风险[warning] comments @ word/comments.xml: Comments are present.",
                "跳过模块 section_format <- ole_objects",
            ],
        )

        panel.set_state(state)

        assert panel._summary.text() == (
            "本次执行已完成\n对象预检：2 项风险 · 跳过 1 个模块"
            "\n- 风险[warning] comments @ word/comments.xml: Comments are present."
            "\n- 跳过模块 section_format <- ole_objects"
        )
    finally:
        panel.close()


def test_recent_run_panel_renders_quiet_status_and_meta_lines():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="partial_success",
            title="最近结果",
            summary="执行完成，但有 2 个模块未成功",
            output_label="out.docx",
            report_label="report.json",
            error_summary="",
        )

        panel.set_state(state)

        assert panel._status_label.objectName() == "wb_recent_run_status"
        assert panel._status_label.text() == "部分完成"
        assert panel._meta_label.objectName() == "wb_recent_run_meta"
        assert panel._meta_label.text() == "输出: out.docx | 报告: report.json"
    finally:
        panel.close()


def test_recent_run_panel_renders_delivery_artifact_labels():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="success",
            title="最近结果",
            summary="本次执行已完成",
            output_label="final: out.docx",
            compare_label="review: review_compare.docx",
            report_label="report.json",
            intermediate_label="review: review_intermediate.json",
            material_manifest_label="material: material_manifest.json",
            material_package_label="zip: material_package.zip",
            artifact_label="输出[review]: review.docx (预警)",
            error_summary="",
        )

        panel.set_state(state)

        text = panel._meta_label.text()
        assert "输出: final: out.docx" in text
        assert "对比: review: review_compare.docx" in text
        assert "报告: report.json" in text
        assert "中间产物: review: review_intermediate.json" in text
        assert "资料清单: material: material_manifest.json" in text
        assert "资料包: zip: material_package.zip" in text
        assert "产物清单: 输出[review]: review.docx (预警)" in text
    finally:
        panel.close()


def test_recent_run_panel_renders_clickable_artifact_rows(tmp_path):
    _app()
    output_path = tmp_path / "review.docx"
    output_path.write_text("placeholder", encoding="utf-8")
    planned_path = tmp_path / "missing" / "planned.docx"
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="success",
            summary="本次执行已完成",
            artifact_items=[
                ArtifactItemState(
                    kind="output",
                    label="review",
                    group_id="review",
                    group_label="review",
                    path=str(output_path),
                    status="available",
                ),
                ArtifactItemState(
                    kind="compare",
                    label="review",
                    group_id="review",
                    group_label="review",
                    path=str(output_path),
                    status="available",
                ),
                ArtifactItemState(
                    kind="planned_output",
                    label="student",
                    group_id="student",
                    group_label="student",
                    path=str(planned_path),
                    status="warning",
                    detail="student 输出文件已存在，将被覆盖",
                ),
            ],
        )

        panel.set_state(state)

        assert panel._artifact_header.isHidden() is False
        assert panel._artifact_list.isHidden() is False
        assert len(panel._artifact_rows) == 3
        assert [header.text() for header in panel._artifact_group_headers] == [
            "交付 review",
            "交付 student",
        ]
        first, second, third = panel._artifact_rows
        assert first._kind_label.text() == "输出"
        assert first._status_label.text() == "就绪"
        assert "review.docx" in first._path_label.text()
        assert first._open_btn.isEnabled() is True
        assert first._folder_btn.isEnabled() is True
        assert second._kind_label.text() == "对比"
        assert third._kind_label.text() == "计划"
        assert third._status_label.text() == "预警"
        assert third._open_btn.isEnabled() is False
        assert third._folder_btn.isEnabled() is True
        assert "将被覆盖" in third._path_label.toolTip()
    finally:
        panel.close()


def test_recent_run_panel_renders_scene_sample_manifest_artifact(tmp_path):
    _app()
    manifest_path = tmp_path / "scene_sample_fixtures" / "manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text('{"artifact_count": 12}', encoding="utf-8")
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="success",
            summary="本次执行已完成",
            scene_sample_manifest_label=f"fixture_manifest: {manifest_path}",
            artifact_items=[
                ArtifactItemState(
                    kind="scene_sample_manifest",
                    label="fixture_manifest",
                    group_id="scene_samples",
                    group_label="样本库",
                    path=str(manifest_path),
                    status="available",
                    detail="12 个样本",
                )
            ],
        )

        panel.set_state(state)

        assert "样本库: fixture_manifest" in panel._meta_label.text()
        assert [header.text() for header in panel._artifact_group_headers] == ["样本库"]
        row = panel._artifact_rows[0]
        assert row._kind_label.text() == "样本"
        assert row._status_label.text() == "就绪"
        assert "manifest.json" in row._path_label.text()
        assert row._open_btn.isEnabled() is True
        assert row._folder_btn.isEnabled() is True
        assert row._path_label.toolTip() == "12 个样本"
    finally:
        panel.close()


def test_recent_run_panel_expands_scene_sample_manifest_artifacts_and_request_cells(tmp_path):
    _app()
    library = build_scene_sample_docx_library(tmp_path / "scene_sample_fixtures")
    manifest_path = Path(library.manifest_path)
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="success",
            summary="本次执行已完成",
            scene_sample_manifest_label=f"fixture_manifest: {manifest_path}",
            artifact_items=[
                ArtifactItemState(
                    kind="scene_sample_manifest",
                    label="fixture_manifest",
                    group_id="scene_samples",
                    group_label="样本库",
                    path=str(manifest_path),
                    status="available",
                    detail=f"{len(library.artifacts)} 个样本",
                )
            ],
        )

        panel.set_state(state)

        assert [header.text() for header in panel._artifact_group_headers] == ["样本库"]
        assert len(panel._artifact_rows) == (
            1 + len(library.artifacts) + len(library.request_cells)
        )
        kinds = [row._artifact_item.kind for row in panel._artifact_rows]
        assert kinds.count("scene_sample_manifest") == 1
        assert kinds.count("scene_sample_fixture") == len(library.artifacts)
        assert kinds.count("scene_request_cell") == len(library.request_cells)

        fixture_row = next(
            row
            for row in panel._artifact_rows
            if row._artifact_item.kind == "scene_sample_fixture"
            and row._artifact_item.label == "contract_delivery_revisions"
        )
        assert fixture_row._kind_label.text() == "DOCX"
        assert fixture_row._status_label.text() == "就绪"
        assert fixture_row._open_btn.isEnabled() is True
        assert "tracked_changes" in fixture_row._path_label.toolTip()

        request_row = next(
            row
            for row in panel._artifact_rows
            if row._artifact_item.kind == "scene_request_cell"
            and row._artifact_item.label == "contract_signing_consistency"
        )
        assert request_row._kind_label.text() == "请求"
        assert request_row._status_label.text() == "就绪"
        assert request_row._open_btn.isEnabled() is True
        assert "request_cell_report.md" in request_row._path_label.text()
        assert "#request-cell-contract-signing-consistency" in (
            request_row._path_label.text()
        )
        assert request_row._artifact_item.fragment == (
            "request-cell-contract-signing-consistency"
        )
        assert "fixture=contract_delivery_revisions" in request_row._path_label.toolTip()
        assert "contract_delivery_revisions.docx" in request_row._path_label.toolTip()
        assert "anchor=request-cell-contract-signing-consistency" in (
            request_row._path_label.toolTip()
        )

        negative_row = next(
            row
            for row in panel._artifact_rows
            if row._artifact_item.kind == "scene_request_cell"
            and row._artifact_item.label == "unknown_stays_unmatched"
        )
        assert negative_row._status_label.text() == "就绪"
        assert negative_row._open_btn.isEnabled() is True
        assert negative_row._folder_btn.isEnabled() is True
        assert "request_cell_report.md" in negative_row._path_label.text()
        assert negative_row._artifact_item.fragment == (
            "request-cell-unknown-stays-unmatched"
        )
        assert "anchor=request-cell-unknown-stays-unmatched" in (
            negative_row._path_label.toolTip()
        )
    finally:
        panel.close()


def test_recent_run_panel_opens_artifact_with_url_fragment(tmp_path, monkeypatch):
    report_path = tmp_path / "request_cell_report.md"
    report_path.write_text("# report", encoding="utf-8")
    opened_urls = []

    monkeypatch.setattr(
        recent_run_panel.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url) or True,
    )

    assert recent_run_panel._open_artifact_file(
        str(report_path),
        fragment="request-cell-contract-signing-consistency",
    )
    assert opened_urls
    assert Path(opened_urls[0].toLocalFile()) == report_path
    assert opened_urls[0].fragment() == "request-cell-contract-signing-consistency"


def test_recent_run_panel_labels_material_package_report_anchor():
    item = ArtifactItemState(
        kind="material_package_report",
        label="report",
        path="C:/tmp/archive_report.md",
        fragment="remote-asset-cache",
    )

    assert recent_run_panel._artifact_kind_label("material_package_report") == "资料包报告"
    assert recent_run_panel._artifact_path_text(item).endswith(
        "archive_report.md#remote-asset-cache"
    )


def test_recent_run_panel_labels_question_figure_repair_queue_anchor():
    item = ArtifactItemState(
        kind="question_figure_repair_queue",
        label="candidates",
        path="C:/tmp/source_batch_report.md",
        fragment="question-figure-repair-queue",
    )

    assert recent_run_panel._artifact_kind_label("question_figure_repair_queue") == (
        "题图修复候选"
    )
    assert recent_run_panel._artifact_path_text(item).endswith(
        "source_batch_report.md#question-figure-repair-queue"
    )


def test_recent_run_panel_labels_question_figure_transaction_task_anchors():
    report_item = ArtifactItemState(
        kind="question_figure_batch_apply_transaction_report",
        label="transaction_report",
        path="C:/tmp/question_figure_batch_apply_transaction_manifest.md",
        fragment="question-figure-batch-apply-transaction-report",
    )
    task_item = ArtifactItemState(
        kind="question_figure_batch_apply_transaction_task_summary",
        label="transaction_tasks",
        path="C:/tmp/question_figure_batch_apply_transaction_manifest.md",
        fragment="question-figure-batch-apply-transaction-task-summary",
    )

    assert recent_run_panel._artifact_kind_label(
        "question_figure_batch_apply_transaction_report"
    ) == "题图事务报告"
    assert recent_run_panel._artifact_kind_label(
        "question_figure_batch_apply_transaction_task_summary"
    ) == "题图事务任务"
    assert recent_run_panel._artifact_path_text(report_item).endswith(
        "question_figure_batch_apply_transaction_manifest.md#"
        "question-figure-batch-apply-transaction-report"
    )
    assert recent_run_panel._artifact_path_text(task_item).endswith(
        "question_figure_batch_apply_transaction_manifest.md#"
        "question-figure-batch-apply-transaction-task-summary"
    )


def test_recent_run_panel_appends_diagnostics_to_summary():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="success",
            title="最近结果",
            summary="本次执行已完成",
            diagnostics_count=1,
            diagnostics_summary="诊断提示（1）\n- [equation_table_format] 1 个公式编号: skipped",
        )

        panel.set_state(state)

        assert panel._summary.text() == (
            "本次执行已完成\n诊断提示（1）\n- [equation_table_format] 1 个公式编号: skipped"
        )
    finally:
        panel.close()


def test_recent_run_panel_wraps_meta_line_for_long_paths():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="failed",
            title="最近结果",
            summary="执行失败",
            output_label="C:/very/long/path/output/document.docx",
            report_label="C:/very/long/path/report/details.json",
            error_summary="",
        )

        panel.set_state(state)

        assert panel._meta_label.wordWrap() is True
        assert "输出:" in panel._meta_label.text()
        assert "报告:" in panel._meta_label.text()
    finally:
        panel.close()
