"""Shared user-facing execution flow labels for Scene and Workbench."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionFlowStepSpec:
    key: str
    title: str
    icon_name: str
    stage_aliases: tuple[str, ...] = ()


STANDARD_EXECUTION_FLOW_STEPS: tuple[ExecutionFlowStepSpec, ...] = (
    ExecutionFlowStepSpec(
        key="read",
        title="读取文件",
        icon_name="file-input",
        stage_aliases=("Loading document",),
    ),
    ExecutionFlowStepSpec(
        key="preflight",
        title="检查风险",
        icon_name="shield-alert",
        stage_aliases=("Object preflight", "对象预检"),
    ),
    ExecutionFlowStepSpec(
        key="format",
        title="套用模板",
        icon_name="layout-template",
        stage_aliases=("Running module",),
    ),
    ExecutionFlowStepSpec(
        key="report",
        title="生成报告",
        icon_name="file-text",
        stage_aliases=("Writing report", "报告生成"),
    ),
    ExecutionFlowStepSpec(
        key="deliver",
        title="输出文件",
        icon_name="file-output",
        stage_aliases=("Saving output", "Completed"),
    ),
)


def standard_execution_flow_steps() -> tuple[ExecutionFlowStepSpec, ...]:
    return STANDARD_EXECUTION_FLOW_STEPS


def normalize_workbench_stage_text(stage_text: str) -> str:
    raw = str(stage_text or "").strip()
    if not raw:
        return raw
    if raw == "Starting":
        return "准备执行"
    for step in STANDARD_EXECUTION_FLOW_STEPS:
        for alias in step.stage_aliases:
            if raw == alias or raw.startswith(f"{alias}:"):
                return step.title
    return raw


__all__ = [
    "ExecutionFlowStepSpec",
    "STANDARD_EXECUTION_FLOW_STEPS",
    "normalize_workbench_stage_text",
    "standard_execution_flow_steps",
]
