"""User-facing projection of a typed document plan.

The plan remains the machine contract.  This module owns labels and action copy
so the Assistant UI never exposes config IDs or re-infers domain behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.assistant.application.exam_plan_editing import exam_master_display_label
from src.assistant.application.official_plan_editing import (
    OfficialPlanEditValues,
    official_plan_missing_user_fields,
)
from src.assistant.application.request_policy import route_display_label_by_id
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.task_plan import (
    ARTIFACT_KIND_EXAM,
    CAPABILITY_EXECUTABLE,
    SOURCE_ROLE_REFERENCE_MATERIAL,
    SOURCE_ROLE_STANDARD_FORMAT_REFERENCE,
)
from src.assistant.domain.exam_authoring_contract import (
    parse_exam_authoring_requirements,
    resolve_exam_blueprint,
)
from src.config.library import get_scene_entry, get_template_entry
from src.config.master_library import get_master
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    get_official_document_profile,
)
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
_OFFICIAL_DELIVERY_LABELS = {
    "formal": "正式版 Word",
    "internal_review": "内部审阅版 Word",
    "meeting_archive": "会议纪要与归档套件",
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
    output_location = str(plan.output_policy.output_root or "").strip()
    if output_location:
        output_location = str(Path(output_location).expanduser())
    else:
        output_location = "未设置"
    delivery_labels = tuple(
        _DELIVERY_LABELS.get(key, key)
        for key in plan.delivery_contract.required_artifact_keys
    )

    exam_facts: tuple[tuple[str, str], ...] = ()
    grade_label = ""
    exam_title = ""
    if assembler == "exam":
        requirements = parse_exam_authoring_requirements(plan.intent)
        blueprint = resolve_exam_blueprint(
            plan.intent,
            scene_id=str(plan.scene_ref.get("id") or ""),
            scale_profile_id=str(plan.scene_ref.get("scale_profile_id") or ""),
        )
        grade_label = requirements.grade
        if requirements.school_stage and grade_label:
            if requirements.school_stage == "初中" and "预备" in plan.intent:
                grade_label = f"初中预备班（{grade_label}）"
            else:
                grade_label = f"{requirements.school_stage}{grade_label}"
        reference_paths = {
            str(item.get("path") or item.get("artifact_id") or "")
            for item in plan.material_refs
            if str(item.get("path") or item.get("artifact_id") or "")
        }
        reference_paths.update(
            str(item.path or item.artifact_id or "")
            for item in plan.source_artifacts
            if item.role
            in {
                SOURCE_ROLE_REFERENCE_MATERIAL,
                SOURCE_ROLE_STANDARD_FORMAT_REFERENCE,
            }
            and str(item.path or item.artifact_id or "")
        )
        scope_label = " · ".join(
            item
            for item in (
                requirements.textbook_edition,
                requirements.semester,
                requirements.scope_hint,
            )
            if item
        )
        exam_period_label = requirements.exam_period or _exam_period_from_profile(
            blueprint.profile.profile_id
        )
        exam_facts = (
            ("年级", grade_label or "待确认"),
            ("学科", requirements.subject or "待确认"),
            ("考试类型", exam_period_label),
            ("题量", f"{blueprint.question_count} 道"),
            ("考试时长", f"{blueprint.duration_minutes:g} 分钟"),
            ("满分", f"{blueprint.total_score:g} 分"),
            ("交付", "、".join(delivery_labels) or "待确认"),
            (
                "参考资料",
                f"已添加 {len(reference_paths)} 项" if reference_paths else "未添加",
            ),
            ("卷面模板", exam_master_display_label(plan)),
            ("输出位置", output_location),
        )
        if scope_label:
            exam_facts += (("教材范围", scope_label),)
        exam_title = "".join(
            item
            for item in (
                grade_label,
                requirements.subject,
                exam_period_label,
            )
            if item
        )

    official_facts: tuple[tuple[str, str], ...] = ()
    if assembler == "official" and plan.generation_required:
        values = OfficialPlanEditValues.from_plan(plan)
        profile = get_official_document_profile(values.document_type_id)
        try:
            master = get_master(values.master_id, "official")
        except (OSError, RuntimeError, TypeError, ValueError):
            master = None
        master_label = str(
            getattr(master, "label", "")
            or values.master_id
            or "默认公文版式"
        )
        contract = get_official_document_assembly_contract(
            values.document_type_id
        )
        requirements = (
            {
                binding.field_key: binding.resolved_requirement
                for binding in contract.field_bindings
            }
            if contract is not None
            else {}
        )
        facts_buffer = [
            ("文种", profile.label if profile is not None else "待选择"),
            ("发文机关", values.organization or "待填写"),
            ("内容要求", _compact_fact(values.content_requirements)),
        ]
        for field_key, label, value, fallback in (
            ("recipient", "主送机关", values.recipient, "待填写"),
            ("signer", "签发人", values.signer, "待填写"),
            ("document_no", "发文字号", values.document_no, "待编"),
            ("issue_date", "成文日期", values.issue_date, "生成时按当天暂填"),
        ):
            requirement = requirements.get(field_key, "forbidden")
            if requirement == "forbidden":
                continue
            if not value and requirement not in {"required"}:
                continue
            facts_buffer.append((label, value or fallback))
        facts_buffer.extend(
            (
            ("格式模板", template_label),
            ("公文版式", master_label),
            (
                "交付方式",
                _OFFICIAL_DELIVERY_LABELS.get(
                    values.delivery_profile,
                    values.delivery_profile or "正式版 Word",
                ),
            ),
            ("输出位置", output_location),
            )
        )
        official_facts = tuple(facts_buffer)

    facts = (
        exam_facts
        if assembler == "exam"
        else official_facts
        if official_facts
        else (
            (
                "任务",
                route_display_label_by_id(plan.capability_ref.route_id),
            ),
            ("操作", _OPERATION_LABELS.get(plan.operation, plan.operation)),
            ("输入", input_name),
            ("模式", mode_label),
            ("方案", scene_label),
            ("模板", template_label),
            ("输出", output_location),
        )
        + ((("交付", "、".join(delivery_labels)),) if delivery_labels else ())
    )
    material_ref = dict(plan.material_snapshot_ref)
    material_count = (
        int(material_ref.get("field_count") or 0)
        + int(material_ref.get("asset_count") or 0)
        + int(material_ref.get("content_count") or 0)
    )
    if assembler != "exam" and material_count:
        facts += (
            (
                "资料",
                f"{material_count} 项",
            ),
        )
    source_roles = {item.role for item in plan.source_artifacts}
    if assembler != "exam" and SOURCE_ROLE_REFERENCE_MATERIAL in source_roles:
        facts += (("数据范围", "材料正文需确认后发送模型"),)
    elif assembler != "exam" and SOURCE_ROLE_STANDARD_FORMAT_REFERENCE in source_roles:
        facts += (("数据范围", "仅格式结构证据需确认后发送"),)
    elif assembler != "exam" and plan.production_input_artifact is not None:
        facts += (("数据范围", "生产输入仅在本地处理"),)
    notices: list[str] = []
    if plan.unresolved_questions:
        notices.extend(f"待补充：{item}" for item in plan.unresolved_questions)
    visible_warnings = tuple(
        item
        for item in plan.warnings
        if not _is_internal_diagnostic(item)
        and item != "将先生成并校验领域产物，再进入 Form 生产。"
    )
    if visible_warnings:
        notices.extend(f"提示：{item}" for item in visible_warnings)
    actions = _plan_actions(plan)
    if assembler == "exam":
        actions += (
            {
                "id": "edit_exam_plan_requirements",
                "label": "修改要求",
                "variant": "secondary",
            },
        )
    elif assembler == "official" and plan.generation_required:
        missing_official = official_plan_missing_user_fields(plan)
        edit_action = {
            "id": "edit_official_plan_requirements",
            "label": "填写公文信息" if missing_official else "修改公文信息",
            "variant": "primary" if missing_official else "secondary",
        }
        actions = (edit_action,) if missing_official else actions + (edit_action,)

    return DocumentPlanPresentation(
        title=exam_title or title,
        body="",
        actions=actions,
        facts=facts,
        notices=tuple(notices),
    )


def generated_draft_display_name(
    plan: DocumentPlan,
    preview_path: str,
) -> str:
    """Give an internal versioned draft a stable, user-facing file label."""

    title = present_document_plan(plan).title.strip() or "内容"
    suffix = Path(str(preview_path or "")).suffix
    return f"{title}-内容草稿{suffix}"


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
        getattr(entry, "display_name", "") or getattr(entry, "name", "") or fallback
    )


def _is_internal_diagnostic(value: str) -> bool:
    normalized = str(value or "").strip()
    return normalized.startswith("assistant_")


def _exam_period_from_profile(profile_id: str) -> str:
    return {
        "quiz": "随堂测验",
        "term": "期中/期末考试",
        "standard": "单元/阶段测试",
    }.get(str(profile_id or "").strip(), "考试")


def _compact_fact(value: str, *, limit: int = 72) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return "待填写"
    return text if len(text) <= limit else text[: limit - 1] + "…"


__all__ = [
    "DocumentPlanPresentation",
    "generated_draft_display_name",
    "present_document_plan",
]
