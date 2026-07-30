"""User-facing projection of a typed document plan.

The plan remains the machine contract.  This module owns labels and action copy
so the Assistant UI never exposes config IDs or re-infers domain behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.task_plan import (
    ARTIFACT_KIND_EXAM,
    CAPABILITY_EXECUTABLE,
    SOURCE_ROLE_REFERENCE_MATERIAL,
    SOURCE_ROLE_STANDARD_FORMAT_REFERENCE,
)
from src.assistant.application.request_policy import route_display_label_by_id
from src.config.library import get_scene_entry, get_template_entry
from src.config.work_mode import get_work_mode


_ASSEMBLER_TITLES = {
    "exam": "试卷生成计划",
    "official": "公文处理计划",
    "generic": "文档处理计划",
}
_DELIVERY_LABELS = {
    "student": "学生卷",
    "teacher": "教师卷",
    "answer_key": "答案卷",
    "analysis": "解析卷",
    "answer_sheet": "答题卡",
    "final_docx": "最终文档",
}
_OPERATION_LABELS = {
    "author": "起草新文档",
    "transform": "处理现有文档",
    "review": "只读审阅",
    "batch": "批量生产",
    "import": "导入转换",
    "author_master": "创建母版",
}


@dataclass(frozen=True, slots=True)
class DocumentPlanPresentation:
    title: str
    body: str
    actions: tuple[dict[str, str], ...]
    facts: tuple[tuple[str, str], ...] = ()
    notices: tuple[str, ...] = ()


def present_document_plan(plan: DocumentPlan) -> DocumentPlanPresentation:
    """Project one plan into stable, user-facing card content."""

    assembler = str(plan.production_contract.terminal_assembler or "generic")
    title = _ASSEMBLER_TITLES.get(assembler, "文档处理计划")
    input_name = str(plan.production_input_ref.get("name") or "由 AI 生成")
    mode = get_work_mode(plan.work_mode_id)
    mode_label = str(getattr(mode, "label", "") or plan.work_mode_id or "通用版")
    scene_label = _library_entry_name(
        get_scene_entry,
        str(plan.scene_ref.get("id") or ""),
        mode_id=plan.work_mode_id,
        fallback="默认方案",
    )
    template_label = _library_entry_name(
        get_template_entry,
        str(plan.template_ref.get("id") or ""),
        mode_id=plan.work_mode_id,
        fallback="默认模板",
    )
    output_name = (
        Path(plan.output_policy.output_root).name or "Alavette-Form-Outputs"
    )
    delivery_labels = tuple(
        _DELIVERY_LABELS.get(key, key)
        for key in plan.delivery_contract.required_artifact_keys
    )

    facts = (
        (
            "任务",
            route_display_label_by_id(plan.capability_ref.route_id),
        ),
        ("操作", _OPERATION_LABELS.get(plan.operation, plan.operation)),
        ("输入", input_name),
        ("模式", mode_label),
        ("方案", scene_label),
        ("模板", template_label),
        ("输出", output_name),
    ) + ((("交付", "、".join(delivery_labels)),) if delivery_labels else ())
    material_ref = dict(plan.material_snapshot_ref)
    material_count = (
        int(material_ref.get("field_count") or 0)
        + int(material_ref.get("asset_count") or 0)
        + int(material_ref.get("content_count") or 0)
    )
    material_name = str(
        material_ref.get("package_id")
        or material_ref.get("profile_id")
        or ""
    ).strip()
    if material_count or material_name:
        material_value = (
            f"{material_name} · {material_count} 项"
            if material_name and material_count
            else (material_name or f"{material_count} 项")
        )
        facts += (
            (
                "资料",
                material_value,
            ),
        )
    source_roles = {item.role for item in plan.source_artifacts}
    if SOURCE_ROLE_REFERENCE_MATERIAL in source_roles:
        facts += (("数据范围", "材料正文需确认后发送模型"),)
    elif SOURCE_ROLE_STANDARD_FORMAT_REFERENCE in source_roles:
        facts += (("数据范围", "仅格式结构证据需确认后发送"),)
    elif plan.production_input_artifact is not None:
        facts += (("数据范围", "生产输入仅在本地处理"),)
    body_lines = [f"{label}：{value}" for label, value in facts]

    notices: list[str] = []
    if plan.unresolved_questions:
        notices.extend(f"待补充：{item}" for item in plan.unresolved_questions)
    visible_warnings = tuple(
        item for item in plan.warnings if not _is_internal_diagnostic(item)
    )
    if visible_warnings:
        notices.extend(f"提示：{item}" for item in visible_warnings)
    if notices:
        body_lines.extend(("", *(f"• {item}" for item in notices)))

    return DocumentPlanPresentation(
        title=title,
        body="\n".join(body_lines),
        actions=_plan_actions(plan),
        facts=facts,
        notices=tuple(notices),
    )


def _plan_actions(plan: DocumentPlan) -> tuple[dict[str, str], ...]:
    if plan.capability_ref.status != CAPABILITY_EXECUTABLE:
        return ()
    if plan.blocking_issues:
        return ({"id": "open_workbench", "label": "补充所需材料"},)
    if plan.generation_required and not plan.production_input_artifact:
        label = (
            "生成并校验题稿"
            if plan.generation_contract.artifact_kind == ARTIFACT_KIND_EXAM
            else "生成并校验内容"
        )
        return ({"id": "generate_content_draft", "label": label},)
    if plan.unresolved_questions:
        return ({"id": "open_workbench", "label": "补充所需信息"},)
    return ({"id": "preflight", "label": "检查并继续"},)


def _library_entry_name(
    loader: Callable[..., object | None],
    config_id: str,
    *,
    mode_id: str,
    fallback: str,
) -> str:
    try:
        entry = loader(config_id, mode_id=mode_id)
    except (OSError, RuntimeError, TypeError, ValueError):
        return fallback
    return str(
        getattr(entry, "display_name", "")
        or getattr(entry, "name", "")
        or fallback
    )


def _is_internal_diagnostic(value: str) -> bool:
    normalized = str(value or "").strip()
    return normalized.startswith("assistant_")


__all__ = ["DocumentPlanPresentation", "present_document_plan"]
