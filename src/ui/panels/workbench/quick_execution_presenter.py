from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .scene_presets import (
    LEGACY_FEATURE_GROUP_MAP,
    UI_CAPABILITY_GROUPS,
)


# ---------------------------------------------------------------------------
# Legacy-compatible feature definition (now backed by UICapabilityGroup)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class QuickExecutionFeatureDefinition:
    feature_id: str
    label: str
    subtitle: str
    badge_text: str
    badge_variant: str


@dataclass(frozen=True, slots=True)
class QuickExecutionStatusViewModel:
    text: str
    tone: str


# Build feature definitions from real UI capability groups (6 groups)
_FEATURE_SNAPSHOT_OVERRIDES: dict[str, dict[str, str]] = {
    "table_chart": {
        "subtitle": "标题层级 / 目录联动",
        "badge_text": "编号就绪",
        "badge_variant": "neutral",
    },
    "content_fill": {
        "subtitle": "Excel / 5 个映射字段",
        "badge_text": "数据就绪",
        "badge_variant": "neutral",
    },
}

_FEATURE_SNAPSHOT_MAP: dict[str, dict[str, str]] = {
    group.group_id: {
        **{
            "subtitle": group.description,
            "badge_text": "",
            "badge_variant": "neutral",
        },
        **_FEATURE_SNAPSHOT_OVERRIDES.get(group.group_id, {}),
    }
    for group in UI_CAPABILITY_GROUPS
}


def _resolve_feature_id(feature_id: str) -> str:
    return LEGACY_FEATURE_GROUP_MAP.get(feature_id, feature_id)


FEATURE_DEFINITIONS = tuple(
    QuickExecutionFeatureDefinition(
        feature_id=group.group_id,
        label=group.label,
        subtitle=_FEATURE_SNAPSHOT_MAP[group.group_id]["subtitle"],
        badge_text=_FEATURE_SNAPSHOT_MAP[group.group_id]["badge_text"],
        badge_variant=_FEATURE_SNAPSHOT_MAP[group.group_id]["badge_variant"],
    )
    for group in UI_CAPABILITY_GROUPS
)


def build_feature_navigation_snapshot(feature_id: str) -> dict[str, str]:
    snapshot = _FEATURE_SNAPSHOT_MAP.get(_resolve_feature_id(feature_id))
    if snapshot is None:
        return {"subtitle": "", "badge_text": "", "badge_variant": "neutral"}
    return dict(snapshot)


def build_navigation_snapshot(
    *,
    document_path: str,
    strategy_name: str | None = None,
    scene_name: str | None = None,
    enabled_count: int,
    execution_running: bool,
    last_result_status: str,
) -> dict[str, str]:
    file_name = Path(document_path).name if document_path else "未选择文档"
    strategy_label = str(strategy_name or scene_name or "").strip() or "默认流程"
    if execution_running:
        badge_text = "执行中"
        badge_variant = "info"
    elif last_result_status in {"success", "partial_success"}:
        badge_text = "最近完成"
        badge_variant = "success"
    elif last_result_status in {"failed", "cancelled"}:
        badge_text = "最近异常"
        badge_variant = "warning"
    else:
        if not document_path:
            badge_text = "待补充"
            badge_variant = "warning"
        else:
            badge_text = f"{enabled_count} 项增强" if enabled_count else "就绪"
            badge_variant = "success"
    return {
        "subtitle": f"{file_name} · {strategy_label}",
        "badge_text": badge_text,
        "badge_variant": badge_variant,
    }


def build_ready_status(
    *,
    document_path: str,
    strategy_name: str | None = None,
    strict_mode: bool | None = None,
    scene_name: str | None = None,
    strategy: str | None = None,
) -> QuickExecutionStatusViewModel:
    if not document_path:
        return QuickExecutionStatusViewModel(
            text="请先选择输入文档",
            tone="hint",
        )

    if strict_mode is None:
        strict_mode = strategy == "rebuild"

    mode_text = "严格模式" if strict_mode else "标准模式"
    strategy_label = str(strategy_name or scene_name or "").strip() or "默认流程"
    return QuickExecutionStatusViewModel(
        text=f"就绪：{Path(document_path).name} · {strategy_label} · {mode_text}",
        tone="success",
    )


def build_running_status(document_path: str) -> str:
    doc_name = Path(document_path).name if document_path else "文档"
    return f"正在执行：{doc_name}"


__all__ = [
    "FEATURE_DEFINITIONS",
    "QuickExecutionFeatureDefinition",
    "QuickExecutionStatusViewModel",
    "build_feature_navigation_snapshot",
    "build_navigation_snapshot",
    "build_ready_status",
    "build_running_status",
]
