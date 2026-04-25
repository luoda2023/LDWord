import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from src.ui.panels.workbench.execution_center import ExecutionCenter
from src.ui.panels.workbench.state import (
    ExecutionProgressState,
    ExecutionResultState,
    ReadinessState,
    RecentRunState,
)


def _app():
    return QApplication.instance() or QApplication([])


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
    assert state.report_paths == []
    assert state.failed_count == 0
    assert state.diagnostics_count == 0
    assert state.diagnostics_summary == ""


def test_recent_run_state_defaults_are_safe():
    state = RecentRunState()

    assert state.status == "idle"
    assert state.title == "最近结果"
    assert state.summary == "暂无最近结果"
    assert state.output_label == ""
    assert state.report_label == ""
    assert state.error_summary == ""
    assert state.diagnostics_count == 0
    assert state.diagnostics_summary == ""


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
    )

    assert isinstance(state, ExecutionResultState)
    assert state.status == "success"
    assert state.summary == "本次执行已完成"
    assert state.output_path.endswith("out.docx")
    assert len(state.report_paths) == 2
    assert state.failed_count == 0
    assert state.diagnostics_count == 1
    assert "诊断提示（1）" in state.diagnostics_summary


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
