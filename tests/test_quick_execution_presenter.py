import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace
from src.config.scene_presets import create_exam_scene
from src.ui.panels.workbench.quick_execution_result_presenter import (
    build_execution_result_presentation,
)
from src.ui.panels.workbench.quick_execution_presenter import (
    QuickExecutionStatusViewModel,
    build_feature_navigation_snapshot,
    build_navigation_snapshot,
    build_ready_status,
    build_running_status,
)
from src.ui.panels.workbench.quick_execution_source_presenter import (
    build_exam_source_projection,
    build_official_document_readiness_projection,
    resolve_official_document_profile_id,
)
from src.ui.panels.workbench.state import ArtifactItemState, ExecutionResultState


def test_build_feature_navigation_snapshot_returns_catalog_entry():
    snapshot = build_feature_navigation_snapshot("content_fill")

    assert snapshot == {
        "subtitle": "资料源 / 5 个映射字段",
        "badge_text": "资料就绪",
        "badge_variant": "neutral",
    }


def test_build_feature_navigation_snapshot_returns_neutral_fallback_for_unknown_feature():
    snapshot = build_feature_navigation_snapshot("unknown")

    assert snapshot == {
        "subtitle": "",
        "badge_text": "",
        "badge_variant": "neutral",
    }


def test_build_navigation_snapshot_prioritizes_running_and_recent_result_states():
    running = build_navigation_snapshot(
        document_path="C:/docs/thesis.docx",
        strategy_name="论文模板",
        enabled_count=2,
        execution_running=True,
        last_result_status="idle",
    )
    success = build_navigation_snapshot(
        document_path="C:/docs/thesis.docx",
        strategy_name="论文模板",
        enabled_count=0,
        execution_running=False,
        last_result_status="success",
    )
    failed = build_navigation_snapshot(
        document_path="C:/docs/thesis.docx",
        strategy_name="论文模板",
        enabled_count=0,
        execution_running=False,
        last_result_status="failed",
    )
    cancelled = build_navigation_snapshot(
        document_path="C:/docs/thesis.docx",
        strategy_name="论文模板",
        enabled_count=0,
        execution_running=False,
        last_result_status="cancelled",
    )

    assert running["subtitle"] == "thesis.docx · 论文模板"
    assert running["badge_text"] == "执行中"
    assert running["badge_variant"] == "info"

    assert success["badge_text"] == "最近完成"
    assert success["badge_variant"] == "success"

    assert failed["badge_text"] == "最近异常"
    assert failed["badge_variant"] == "warning"

    assert cancelled["badge_text"] == "已取消"
    assert cancelled["badge_variant"] == "neutral"


def test_build_navigation_snapshot_reports_missing_document_or_enabled_feature_count_when_idle():
    missing_doc = build_navigation_snapshot(
        document_path="",
        strategy_name="默认流程",
        enabled_count=0,
        execution_running=False,
        last_result_status="idle",
    )
    ready_with_features = build_navigation_snapshot(
        document_path="C:/docs/report.docx",
        strategy_name="默认流程",
        enabled_count=3,
        execution_running=False,
        last_result_status="idle",
    )

    assert missing_doc == {
        "subtitle": "未选择文档 · 默认流程",
        "badge_text": "待补充",
        "badge_variant": "warning",
    }
    assert ready_with_features == {
        "subtitle": "report.docx · 默认流程",
        "badge_text": "3 项增强",
        "badge_variant": "success",
    }


def test_build_ready_status_returns_hint_or_ready_summary():
    missing_doc = build_ready_status(
        document_path="",
        strategy_name="默认流程",
        strict_mode=True,
    )
    ready = build_ready_status(
        document_path="C:/docs/report.docx",
        strategy_name="汇报演示",
        strict_mode=False,
    )

    assert missing_doc == QuickExecutionStatusViewModel(
        text="请先选择输入文档",
        tone="hint",
    )
    assert ready == QuickExecutionStatusViewModel(
        text="就绪：report.docx · 汇报演示 · 标准模式",
        tone="success",
    )


def test_build_ready_status_reports_material_schema_reasons_before_ready_summary():
    status = build_ready_status(
        document_path="C:/docs/report.docx",
        strategy_name="汇报演示",
        strict_mode=False,
        material_schema_reasons=["资料 Schema 未注册：missing_schema_v1"],
    )

    assert status == QuickExecutionStatusViewModel(
        text="资料 Schema 未注册：missing_schema_v1",
        tone="warning",
    )


def test_build_running_status_uses_document_name_or_generic_fallback():
    assert build_running_status("C:/docs/report.docx") == "正在执行：report.docx"
    assert build_running_status("") == "正在执行：文档"


def test_exam_source_presenter_owns_markdown_parsing_and_counts(tmp_path):
    source = tmp_path / "paper.md"
    source.write_text(
        """# 数学测试

> 科目：数学　满分：5 分

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

    summary, rows = build_exam_source_projection(
        scene=create_exam_scene(),
        document_path=str(source),
    )

    assert summary == "已识别 1 大题 / 1 小题"
    assert rows["source"] == "Markdown 题稿：paper.md"
    assert "1 大题 / 1 小题" in rows["assembly"]
    assert rows["fields"].startswith("答案 1/1")


def test_official_source_presenter_resolves_profile_and_contract_readiness():
    scene = SceneWorkspace(
        scene_id="custom",
        mode_id="custom",
        default_material_profile_id="official:minutes",
    )
    profile_id = resolve_official_document_profile_id(
        explicit_profile_id="letter",
        scene=scene,
    )
    summary, rows = build_official_document_readiness_projection(
        profile_id=profile_id,
        material_context=MaterialExecutionContext(),
        plan_label="公文基础方案",
        template_label="公文模板",
    )

    assert profile_id == "letter"
    assert summary.startswith("公文执行前检查：")
    assert rows["source"] == "公文基础方案"
    assert rows["assembly"] == "函 (letter)"
    assert "公文模板" in rows["delivery"]


def test_result_presenter_owns_artifact_logs_and_batch_retry_projection():
    presentation = build_execution_result_presentation(
        ExecutionResultState(
            status="partial_success",
            summary="1 份成功，1 份失败",
            output_paths={"review": "C:/tmp/review.docx"},
            artifact_items=[
                ArtifactItemState(
                    label="审阅稿",
                    detail="目标文件将被覆盖",
                )
            ],
            batch_isolation={
                "history_run_id": "run-1",
                "attempt_number": 2,
                "retry_eligible_profile_ids": ["row-2", ""],
            },
        )
    )

    assert presentation.status == "partial_success"
    assert presentation.execute_button_text == "重新生成"
    assert presentation.retry_profile_ids == ("row-2",)
    assert presentation.batch_run_id == "run-1"
    assert presentation.batch_attempt_number == 2
    messages = [entry.message for entry in presentation.log_entries]
    assert "输出文件[审阅稿]：C:/tmp/review.docx" in messages
    assert "产物预检[审阅稿]：目标文件将被覆盖" in messages


def test_result_presenter_fails_closed_for_non_plain_terminal_payload():
    presentation = build_execution_result_presentation(
        ExecutionResultState(
            status="success",
            summary="done",
            terminal_payload={"bad": object()},
        )
    )

    assert presentation.status == "failed"
    assert presentation.expand_log is True
    assert presentation.terminal_payload["status"] == "failed"
    assert "Invalid terminal payload" in presentation.error_text
