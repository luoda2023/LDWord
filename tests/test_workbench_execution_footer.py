from __future__ import annotations

from src.shared.ui.theme import get_theme
from src.ui.panels.workbench.document_execution_state import (
    inspect_document_execution_readiness,
    resolve_document_execution_topology,
)
from src.ui.panels.workbench.execution_session_controller import (
    _composite_file_batch_progress,
    _DocumentBatchRunner,
)
from src.ui.panels.workbench.state import (
    ExecutionProgressState,
    ExecutionResultState,
)
from src.ui.panels.workbench.workbench_execution_footer import (
    WorkbenchExecutionFooter,
)


def _set_ready_document_context(footer: WorkbenchExecutionFooter) -> None:
    topology = resolve_document_execution_topology(
        document_paths=("source.docx",),
    )
    footer.set_context(
        topology,
        inspect_document_execution_readiness(topology),
    )


def _terminal_payload(
    *,
    status: str,
    output_path: str = "",
    error_text: str = "",
) -> dict[str, object]:
    return {
        "status": status,
        "summary": "生成完成" if status == "success" else "执行失败",
        "output_path": output_path,
        "output_paths": {},
        "report_paths": [],
        "failed_count": 0,
        "artifact_failure_count": 0,
        "error_text": error_text,
        "diagnostics_count": 0,
        "diagnostics_summary": "",
    }


def test_blocked_footer_keeps_generation_action_and_points_to_source(qapp):
    footer = WorkbenchExecutionFooter()
    try:
        topology = resolve_document_execution_topology(
            record_ids=("record-1",),
            source_requirement="required",
        )
        footer.set_context(
            topology,
            inspect_document_execution_readiness(topology),
        )

        assert footer._execute_button.text() == "生成文档"
        assert footer._execute_button.isEnabled() is False
        assert footer._status_label.text() == (
            "当前方案需要底稿，请先在上方选择文档"
        )
        assert not hasattr(footer, "_receipt")
        assert not hasattr(footer, "_log_toggle")
        assert not hasattr(footer, "_log")
    finally:
        footer.close()


def test_footer_owns_button_variant_stylesheet(qapp):
    footer = WorkbenchExecutionFooter()
    try:
        _set_ready_document_context(footer)

        stylesheet = footer.styleSheet()
        assert 'QPushButton[variant="primary"]' in stylesheet
        assert 'QPushButton[variant="secondary"]' in stylesheet
        assert footer._execute_button.property("variant") == "primary"
        assert not footer._execute_button.isHidden()
        assert footer._execute_button.isEnabled()
    finally:
        footer.close()


def test_footer_can_explain_the_resolved_official_strategy(qapp):
    footer = WorkbenchExecutionFooter()
    try:
        _set_ready_document_context(footer)
        footer.set_ready_status("已准备：按文种套用内置公文母版")

        assert footer._status_label.text() == "已准备：按文种套用内置公文母版"
        assert footer._execute_button.isEnabled()
    finally:
        footer.close()


def test_footer_uses_indeterminate_progress_until_total_is_known(qapp):
    footer = WorkbenchExecutionFooter()
    try:
        _set_ready_document_context(footer)
        footer.set_execution_progress(
            ExecutionProgressState(
                stage_text="正在准备",
                current_step=0,
                total_steps=0,
                percent=0,
            )
        )

        assert footer._progress.minimum() == 0
        assert footer._progress.maximum() == 0
        assert "0%" not in footer._status_label.text()
        assert footer._status_label.text() == "正在生成文档"
        assert footer._execute_button.isHidden()
        assert not footer._cancel_button.isHidden()

        footer.set_execution_progress(
            ExecutionProgressState(
                stage_text="套用模板",
                current_step=2,
                total_steps=4,
                percent=50,
            )
        )

        assert footer._progress.minimum() == 0
        assert footer._progress.maximum() == 100
        assert footer._progress.value() == 50
        assert footer._status_label.text() == "正在生成文档 · 50%"
        status_style = footer._status_label.styleSheet()
        assert f"font-size: {get_theme().font_size_lg}px" in status_style
        assert "font-weight:" in status_style
    finally:
        footer.close()


def test_success_replaces_progress_in_place_without_adding_result_rows(
    qapp,
    tmp_path,
):
    output = tmp_path / "result.docx"
    output.touch()
    footer = WorkbenchExecutionFooter()
    try:
        _set_ready_document_context(footer)
        idle_height = footer.sizeHint().height()
        footer.set_execution_progress(
            ExecutionProgressState(
                stage_text="输出文件",
                current_step=1,
                total_steps=1,
                percent=100,
            )
        )
        running_height = footer.sizeHint().height()

        payload = _terminal_payload(
            status="success",
            output_path=str(output),
        )
        footer.set_execution_result(
            ExecutionResultState(
                status="success",
                summary="生成完成",
                output_path=str(output),
                terminal_payload=payload,
            )
        )

        assert footer.sizeHint().height() == idle_height == running_height
        assert footer._status_label.text() == "生成完成 · result.docx"
        assert not footer._open_button.isHidden()
        assert footer._open_button.text() == "打开文档"
        assert footer._execute_button.text() == "再次生成"
        assert not footer._execute_button.isHidden()
    finally:
        footer.close()


def test_failure_shows_sanitized_inline_recovery_without_log_surface(qapp):
    footer = WorkbenchExecutionFooter()
    try:
        _set_ready_document_context(footer)
        error_text = "RuntimeError: internal pipeline state exploded"
        footer.set_execution_result(
            ExecutionResultState(
                status="failed",
                summary="执行失败",
                error_text=error_text,
                terminal_payload=_terminal_payload(
                    status="failed",
                    error_text=error_text,
                ),
            )
        )

        assert footer._status_label.text() == (
            "生成失败 · 生成过程中出现错误，请重试"
        )
        assert footer._execute_button.text() == "重试"
        assert not footer._execute_button.isHidden()
        assert not hasattr(footer, "_log")
    finally:
        footer.close()


def test_material_placeholder_failure_names_the_unmatched_role(qapp):
    footer = WorkbenchExecutionFooter()
    try:
        _set_ready_document_context(footer)
        error_text = "material.bind.template_resources_unsupported:photo,gallery"
        footer.set_execution_result(
            ExecutionResultState(
                status="failed",
                summary="执行失败",
                error_text=error_text,
                terminal_payload=_terminal_payload(
                    status="failed",
                    error_text=error_text,
                ),
            )
        )

        assert footer._status_label.text() == (
            "生成失败 · 资料包图片缺少对应文档占位符：photo、gallery"
        )
    finally:
        footer.close()


def test_output_collision_failure_explains_that_the_old_file_is_kept(qapp):
    footer = WorkbenchExecutionFooter()
    try:
        _set_ready_document_context(footer)
        error_text = "material.bind.output_path_exists"
        footer.set_execution_result(
            ExecutionResultState(
                status="failed",
                summary="执行失败",
                error_text=error_text,
                terminal_payload=_terminal_payload(
                    status="failed",
                    error_text=error_text,
                ),
            )
        )

        assert footer._status_label.text() == (
            "生成失败 · 输出目标已存在，旧文件已保留；请重试生成"
        )
    finally:
        footer.close()


def test_file_batch_progress_includes_current_file_internal_progress():
    assert _composite_file_batch_progress(
        index=1,
        file_count=2,
        inner_current=1,
        inner_total=4,
    ) == (250, 2000)
    assert _composite_file_batch_progress(
        index=2,
        file_count=2,
        inner_current=2,
        inner_total=4,
    ) == (1500, 2000)
    assert _composite_file_batch_progress(
        index=2,
        file_count=2,
        inner_current=4,
        inner_total=4,
    ) == (2000, 2000)


def test_document_batch_progress_does_not_present_planning_as_fifty_percent(
    monkeypatch,
):
    class _Plan:
        @staticmethod
        def run():
            return {"status": "success"}

    monkeypatch.setattr(
        "src.ui.panels.workbench.execution_session_controller."
        "compile_document_batch_plan",
        lambda *_args, **_kwargs: _Plan(),
    )
    runner = _DocumentBatchRunner(
        object(),
        source_paths=("source.docx",),
        output_root="output",
    )
    progress: list[tuple[int, int, str]] = []

    result = runner.run(
        lambda current, total, text: progress.append(
            (current, total, text)
        ),
        lambda: False,
    )

    assert result == {"status": "success"}
    assert progress == [
        (0, 0, "正在准备…"),
        (0, 0, "正在生成文档"),
    ]
