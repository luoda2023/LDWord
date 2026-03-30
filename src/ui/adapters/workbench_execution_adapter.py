from __future__ import annotations

from src.ui.panels.workbench.state import (
    ExecutionProgressState,
    ExecutionResultState,
    ReadinessState,
    RecentRunState,
)


class WorkbenchExecutionAdapter:
    def build_readiness(self, *, has_document: bool, has_strategy: bool) -> ReadinessState:
        reasons: list[str] = []
        if not has_document:
            reasons.append("未选择文档")
        if not has_strategy:
            reasons.append("未选择策略")
        return ReadinessState(
            ready=not reasons,
            label="Ready" if not reasons else "待执行",
            reasons=reasons,
        )

    def build_progress_state(
        self,
        *,
        stage_text: str,
        current_step: int,
        total_steps: int,
    ) -> ExecutionProgressState:
        sanitized_total_steps = max(total_steps, 0)
        if sanitized_total_steps <= 0:
            sanitized_current_step = 0
        else:
            sanitized_current_step = min(max(current_step, 0), sanitized_total_steps)
        percent = 0
        if sanitized_total_steps > 0:
            percent = int(sanitized_current_step / sanitized_total_steps * 100)
        return ExecutionProgressState(
            stage_text=stage_text,
            current_step=sanitized_current_step,
            total_steps=sanitized_total_steps,
            percent=percent,
        )

    def build_result_state(
        self,
        *,
        status: str,
        output_path: str,
        report_paths: list[str],
        failed_count: int,
        error_text: str,
    ) -> ExecutionResultState:
        summary_map = {
            "success": "本次执行已完成",
            "partial_success": f"执行完成，但有 {failed_count} 个模块未成功",
            "failed": "执行失败",
            "cancelled": "已取消",
        }
        if status not in summary_map:
            raise ValueError(f"Unknown execution status: {status!r}")

        return ExecutionResultState(
            status=status,
            summary=summary_map[status],
            error_text=error_text,
            output_path=output_path,
            report_paths=list(report_paths),
            failed_count=failed_count,
        )

    def build_recent_run_state(
        self,
        result_state: ExecutionResultState,
    ) -> RecentRunState:
        report_label = ", ".join(result_state.report_paths)
        return RecentRunState(
            status=result_state.status,
            title="最近结果",
            summary=result_state.summary,
            output_label=result_state.output_path,
            report_label=report_label,
            error_summary=result_state.error_text,
        )
