"""Preflight all target-group output identities before execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.pipeline.runner import pipeline_output_paths_share_identity


@dataclass(frozen=True, slots=True)
class PreparedDeliveryTargetGroup:
    target_template_id: str
    config: object | None
    planned_output_paths: dict[str, str]
    terminal_owner: str
    error: str
    planned_artifact_paths: dict[str, str] = field(default_factory=dict)


def build_delivery_group_output_preflight(
    groups: list[PreparedDeliveryTargetGroup],
) -> dict[str, object]:
    """Reject colliding final and auxiliary identities before group execution."""

    items: list[dict[str, object]] = []
    targets: list[tuple[int, str, str, int, str]] = []
    for group_index, group in enumerate(groups):
        if group.error or group.config is None:
            message = (
                f"Delivery target {group.target_template_id or 'current'} "
                f"failed preflight: {group.error or 'configuration unresolved'}"
            )
            items.append(
                {
                    "preset_id": "group_preflight",
                    "label": group.target_template_id or "current",
                    "path": "",
                    "issues": [
                        {
                            "kind": "group_preflight_failed",
                            "severity": "error",
                            "message": message,
                        }
                    ],
                }
            )
        for preset_id, path in group.planned_output_paths.items():
            items.append(
                {
                    "preset_id": preset_id,
                    "label": f"{group.target_template_id or 'current'} / {preset_id}",
                    "path": path,
                    "issues": [],
                }
            )
            targets.append(
                (group_index, preset_id, path, len(items) - 1, "final_docx")
            )
        for artifact_id, path in group.planned_artifact_paths.items():
            artifact_kind = str(artifact_id).rsplit(":", 1)[-1]
            items.append(
                {
                    "preset_id": artifact_id,
                    "label": (
                        f"{group.target_template_id or 'current'} / {artifact_id}"
                    ),
                    "path": path,
                    "artifact_kind": artifact_kind,
                    "issues": [],
                }
            )
            targets.append(
                (group_index, artifact_id, path, len(items) - 1, artifact_kind)
            )

    executable_groups = [
        group for group in groups if group.config is not None and not group.error
    ]
    terminal_groups = [group for group in executable_groups if group.terminal_owner]
    if terminal_groups and len(executable_groups) > 1:
        owners = ", ".join(
            f"{group.target_template_id or 'current'}={group.terminal_owner}"
            for group in terminal_groups
        )
        message = (
            "跨模板组包含 assembler-owned 终端输出，当前无法在执行前完整规划其全局 "
            f"final 身份，已 fail-close: {owners}"
        )
        items.append(
            {
                "preset_id": "terminal_assembly",
                "label": "Terminal assembly groups",
                "path": "",
                "issues": [
                    {
                        "kind": "unplannable_terminal_group",
                        "severity": "error",
                        "message": message,
                    }
                ],
            }
        )

    for left_position, (
        left_group,
        left_target_id,
        left_path,
        left_item_index,
        left_kind,
    ) in enumerate(targets):
        for right_position in range(left_position + 1, len(targets)):
            (
                right_group,
                right_target_id,
                right_path,
                right_item_index,
                right_kind,
            ) = targets[right_position]
            left_label = (
                f"{groups[left_group].target_template_id or 'current'}"
                f"/{left_target_id}"
            )
            right_label = (
                f"{groups[right_group].target_template_id or 'current'}"
                f"/{right_target_id}"
            )
            if pipeline_output_paths_share_identity(left_path, right_path):
                if left_kind == right_kind == "final_docx":
                    target_label = "同一 final 文件"
                elif left_kind != "final_docx" and right_kind != "final_docx":
                    target_label = "同一辅助产物文件"
                else:
                    target_label = "同一 final 与辅助产物文件"
                message = (
                    f"交付模板组 {left_label} 与 {right_label} 指向{target_label}: "
                    f"{left_path} <-> {right_path}"
                )
                _append_issue(
                    items,
                    left_item_index,
                    right_item_index,
                    kind=(
                        "duplicate_target"
                        if left_kind == right_kind == "final_docx"
                        else "duplicate_artifact_target"
                    ),
                    message=message,
                )
            if (
                left_kind == right_kind == "final_docx"
                and left_target_id == right_target_id
            ):
                message = (
                    f"交付模板组 {left_label} 与 {right_label} 复用同一输出标识 "
                    f"{left_target_id!r}，聚合结果会发生覆盖"
                )
                _append_issue(
                    items,
                    left_item_index,
                    right_item_index,
                    kind="duplicate_output_id",
                    message=message,
                )
            if (
                left_kind != "final_docx"
                and right_kind != "final_docx"
                and left_target_id == right_target_id
            ):
                message = (
                    f"交付模板组 {left_label} 与 {right_label} 复用同一辅助产物标识 "
                    f"{left_target_id!r}，聚合结果会发生覆盖"
                )
                _append_issue(
                    items,
                    left_item_index,
                    right_item_index,
                    kind="duplicate_artifact_id",
                    message=message,
                )

    issue_count = sum(len(list(item.get("issues") or [])) for item in items)
    return {
        "has_issues": bool(issue_count),
        "has_errors": bool(issue_count),
        "issue_count": issue_count,
        "error_count": issue_count,
        "items": items,
    }


def _append_issue(
    items: list[dict[str, object]],
    left_index: int,
    right_index: int,
    *,
    kind: str,
    message: str,
) -> None:
    issue = {"kind": kind, "severity": "error", "message": message}
    for index in (left_index, right_index):
        issues = items[index].get("issues")
        if isinstance(issues, list):
            issues.append(dict(issue))


__all__ = [
    "PreparedDeliveryTargetGroup",
    "build_delivery_group_output_preflight",
]
