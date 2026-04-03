import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.workbench.quick_execution_presenter import (
    QuickExecutionStatusViewModel,
    build_feature_navigation_snapshot,
    build_navigation_snapshot,
    build_ready_status,
    build_running_status,
)


def test_build_feature_navigation_snapshot_returns_catalog_entry():
    snapshot = build_feature_navigation_snapshot("content_fill")

    assert snapshot == {
        "subtitle": "Excel / 5 个映射字段",
        "badge_text": "数据就绪",
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

    assert running["subtitle"] == "thesis.docx · 论文模板"
    assert running["badge_text"] == "执行中"
    assert running["badge_variant"] == "info"

    assert success["badge_text"] == "最近完成"
    assert success["badge_variant"] == "success"

    assert failed["badge_text"] == "最近异常"
    assert failed["badge_variant"] == "warning"


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


def test_build_running_status_uses_document_name_or_generic_fallback():
    assert build_running_status("C:/docs/report.docx") == "正在执行：report.docx"
    assert build_running_status("") == "正在执行：文档"
