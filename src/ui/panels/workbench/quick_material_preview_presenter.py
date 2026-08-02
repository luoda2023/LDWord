"""Pure V1 material-package projection for the quick execution card."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.materials import MaterialPreviewSnapshot
from src.domain.materials import MaterialIssue, MaterialRunSelection
from src.ui.adapters.workbench_execution_gate import ExecutionGateDecision


@dataclass(frozen=True, slots=True)
class QuickMaterialPreviewItem:
    key: str
    label: str
    value: str
    missing: bool = False
    kind: str = "text"
    token: str = ""

    @property
    def compact_text(self) -> str:
        subject = self.label or self.key
        return f"{subject}  {self.value}" if self.value else subject


@dataclass(frozen=True, slots=True)
class QuickMaterialPreviewProjection:
    visible: bool = True
    package_label: str = "未选择资料包"
    package_source_text: str = ""
    package_source_tone: str = "neutral"
    profile_label: str = ""
    summary_text: str = "本次不使用资料包"
    status_text: str = "未选择"
    status_tone: str = "neutral"
    items: tuple[QuickMaterialPreviewItem, ...] = ()
    hidden_item_count: int = 0
    counters: tuple[str, ...] = ()

    @property
    def can_expand(self) -> bool:
        return bool(self.items or self.hidden_item_count)

    @property
    def compact_items(self) -> tuple[QuickMaterialPreviewItem, ...]:
        return self.items[:3]

    @property
    def counter_text(self) -> str:
        return " · ".join(self.counters)


def build_quick_material_preview_projection(
    _scene,
    selection: MaterialRunSelection | None,
    *,
    preview_snapshot: MaterialPreviewSnapshot | None = None,
    gate_decision: ExecutionGateDecision | None = None,
    issues: tuple[MaterialIssue, ...] = (),
) -> QuickMaterialPreviewProjection:
    """Render only canonical selection and committed preview evidence."""

    preview = (
        preview_snapshot
        if isinstance(preview_snapshot, MaterialPreviewSnapshot)
        else None
    )
    if selection is None:
        return QuickMaterialPreviewProjection(
            package_label=preview.package_name if preview is not None else "未选择资料包",
            summary_text="本次不使用资料包",
        )

    package_name = (
        preview.package_name
        if preview is not None and preview.package_name
        else selection.package_ref.package_id
    )
    record_count = len(selection.selected_record_ids)
    current_record = (
        preview.current_record_name
        if preview is not None
        else ""
    )
    counters: list[str] = [f"记录 {record_count}"]
    if preview is not None and preview.field_count:
        counters.append(f"字段 {preview.field_count}")
    if preview is not None and preview.resource_count:
        counters.append(f"资源 {preview.resource_count}")

    errors = tuple(
        item for item in issues if item.severity == "error"
    )
    warnings = tuple(
        item for item in issues if item.severity == "warning"
    )
    if gate_decision is not None and not gate_decision.can_run:
        status_text, status_tone = "待修复", "error"
    elif errors:
        status_text, status_tone = "待修复", "error"
    elif not record_count:
        status_text, status_tone = "未选记录", "warning"
    elif warnings:
        status_text, status_tone = "需确认", "warning"
    else:
        status_text, status_tone = "已绑定", "success"

    summary_parts = []
    if current_record:
        summary_parts.append(current_record)
    summary_parts.extend(counters)
    return QuickMaterialPreviewProjection(
        package_label=package_name,
        package_source_text=(
            "内置"
            if preview is not None and preview.source_type == "builtin"
            else ("自定" if preview is not None else "")
        ),
        package_source_tone=(
            "neutral"
            if preview is None or preview.source_type == "builtin"
            else "info"
        ),
        profile_label=current_record,
        summary_text=" · ".join(summary_parts) or "已选择资料包",
        status_text=status_text,
        status_tone=status_tone,
        counters=tuple(counters),
    )


__all__ = [
    "QuickMaterialPreviewItem",
    "QuickMaterialPreviewProjection",
    "build_quick_material_preview_projection",
]
