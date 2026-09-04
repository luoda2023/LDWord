"""Typed user-editable projection for revising one exam plan."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.domain.exam_authoring_contract import (
    parse_exam_authoring_requirements,
    resolve_exam_blueprint,
)
from src.config.library import (
    get_template_entry,
    load_scene_from_library,
)
from src.config.master_library import MasterSpec, get_master


@dataclass(frozen=True, slots=True)
class ExamMasterBinding:
    """Validated exam master and its compatible internal format config."""

    master: MasterSpec
    template_id: str


@dataclass(frozen=True, slots=True)
class ExamPlanEditValues:
    school_stage: str
    grade: str
    subject: str
    exam_period: str
    question_count: int
    duration_minutes: int
    total_score: int
    textbook_edition: str = ""
    semester: str = ""
    scope_hint: str = ""
    include_student: bool = True
    include_answer: bool = True
    analysis_required: bool = False
    output_root: str = ""
    master_id: str = ""

    @classmethod
    def from_plan(cls, plan: DocumentPlan) -> ExamPlanEditValues:
        requirements = parse_exam_authoring_requirements(plan.intent)
        blueprint = resolve_exam_blueprint(
            plan.intent,
            scene_id=str(plan.scene_ref.get("id") or ""),
            scale_profile_id=str(plan.scene_ref.get("scale_profile_id") or ""),
        )
        required = set(plan.delivery_contract.required_artifact_keys)
        school_stage = requirements.school_stage
        if school_stage == "初中" and "预备" in plan.intent:
            school_stage = "初中预备班"
        return cls(
            school_stage=school_stage,
            grade=requirements.grade,
            subject=requirements.subject,
            exam_period=(
                requirements.exam_period
                or _profile_exam_period(blueprint.profile.profile_id)
            ),
            question_count=blueprint.question_count,
            duration_minutes=max(1, round(blueprint.duration_minutes)),
            total_score=max(1, round(blueprint.total_score)),
            textbook_edition=requirements.textbook_edition,
            semester=requirements.semester,
            scope_hint=requirements.scope_hint,
            include_student="student" in required,
            include_answer="answer_key" in required,
            analysis_required=requirements.analysis_required,
            output_root=str(plan.output_policy.output_root or ""),
            master_id=exam_master_id_from_plan(plan),
        )


def exam_master_id_from_plan(plan: DocumentPlan) -> str:
    """Return the explicit plan master, falling back to its library scene."""

    explicit = str(plan.scene_ref.get("master_id") or "").strip()
    if explicit:
        return explicit
    scene_id = str(plan.scene_ref.get("id") or "").strip()
    if not scene_id:
        return ""
    try:
        scene = load_scene_from_library(scene_id, mode_id=plan.work_mode_id)
    except (OSError, RuntimeError, TypeError, ValueError):
        return ""
    return str(getattr(scene, "master_id", "") or "").strip()


def exam_master_display_label(plan: DocumentPlan) -> str:
    """Resolve the user-facing label for the master selected by one plan."""

    scene_id = str(plan.scene_ref.get("id") or "").strip()
    master_id = exam_master_id_from_plan(plan)
    if not scene_id or not master_id:
        return "默认卷面"
    try:
        scene = load_scene_from_library(scene_id, mode_id=plan.work_mode_id)
        master = get_master(
            master_id,
            "exam",
            exam_config=getattr(scene, "exam_paper", None),
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        master = None
    if master is None:
        return str(plan.scene_ref.get("master_label") or "卷面不可用")
    return str(master.label or master.master_id or "默认卷面")


def resolve_exam_master_binding(
    plan: DocumentPlan,
    requested_master_id: str = "",
) -> ExamMasterBinding:
    """Validate a master selection and bind a compatible TemplateConfig."""

    if plan.production_contract.terminal_assembler != "exam":
        raise ValueError("exam_master_plan_invalid")
    scene_id = str(plan.scene_ref.get("id") or "").strip()
    try:
        scene = load_scene_from_library(scene_id, mode_id=plan.work_mode_id)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("exam_master_unavailable") from exc

    master_id = (
        str(requested_master_id or "").strip()
        or str(plan.scene_ref.get("master_id") or "").strip()
        or str(getattr(scene, "master_id", "") or "").strip()
    )
    try:
        master = get_master(
            master_id,
            "exam",
            exam_config=getattr(scene, "exam_paper", None),
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("exam_master_unavailable") from exc
    if master is None or not Path(master.docx_path).is_file():
        raise ValueError("exam_master_unavailable")

    scene_template_ids = tuple(
        dict.fromkeys(
            item
            for item in (
                str(getattr(scene, "template_id", "") or "").strip(),
                *(
                    str(value or "").strip()
                    for value in tuple(
                        getattr(scene, "compatible_template_ids", ()) or ()
                    )
                ),
            )
            if item
        )
    )
    master_template_ids = tuple(
        dict.fromkeys(
            item
            for item in (
                str(master.template_config_id or "").strip(),
                *(
                    str(value or "").strip()
                    for value in master.compatible_template_config_ids
                ),
            )
            if item
        )
    )
    preferred = (
        str(master.template_config_id or "").strip(),
        str(plan.template_ref.get("id") or "").strip(),
        *master_template_ids,
    )
    for template_id in dict.fromkeys(item for item in preferred if item):
        if (
            template_id not in scene_template_ids
            or template_id not in master_template_ids
        ):
            continue
        try:
            entry = get_template_entry(template_id, mode_id=plan.work_mode_id)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("exam_master_template_incompatible") from exc
        if entry is not None and bool(getattr(entry, "is_available", True)):
            return ExamMasterBinding(master=master, template_id=template_id)
    raise ValueError("exam_master_template_incompatible")


def compose_exam_plan_intent(values: ExamPlanEditValues) -> str:
    """Build one explicit Chinese request that the deterministic builder owns."""

    validate_exam_plan_edit_values(values)
    grade = _stage_grade_label(values.school_stage, values.grade)
    exam_period = _paper_label(str(values.exam_period or "考试").strip())
    parts = [
        f"生成一份{grade}{values.subject}{exam_period}",
        f"共 {int(values.question_count)} 道题",
        f"考试时间 {int(values.duration_minutes)} 分钟",
        f"满分 {int(values.total_score)} 分",
    ]
    if values.textbook_edition:
        parts.append(str(values.textbook_edition).strip())
    if values.semester:
        parts.append(str(values.semester).strip())
    if values.scope_hint:
        parts.append(f"考试范围：{str(values.scope_hint).strip()}")
    if values.analysis_required:
        parts.append("每道题含详细解析")
    if values.include_student and values.include_answer:
        parts.append("生成学生卷和答案卷")
    elif values.include_student:
        parts.append("只要学生卷")
    else:
        parts.append("只要答案卷")
    return "，".join(parts)


def normalized_output_root(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return str(fallback or "")
    return str(Path(text).expanduser().resolve(strict=False))


def validate_exam_plan_edit_values(values: ExamPlanEditValues) -> None:
    if not isinstance(values, ExamPlanEditValues):
        raise TypeError("exam_plan_edit_values_invalid")
    if not str(values.grade or "").strip():
        raise ValueError("exam_plan_grade_required")
    if not str(values.subject or "").strip():
        raise ValueError("exam_plan_subject_required")
    if int(values.question_count) < 1:
        raise ValueError("exam_plan_question_count_invalid")
    if int(values.duration_minutes) < 1:
        raise ValueError("exam_plan_duration_invalid")
    if int(values.total_score) < 1:
        raise ValueError("exam_plan_total_score_invalid")
    if not values.include_student and not values.include_answer:
        raise ValueError("exam_plan_delivery_required")


def _stage_grade_label(stage: str, grade: str) -> str:
    stage_text = str(stage or "").strip()
    grade_text = re.sub(r"\s+", "", str(grade or ""))
    grade_text = re.sub(
        r"^(?:小学|初中预备班|预备班|初中|高中)",
        "",
        grade_text,
    )
    if stage_text == "高中" and grade_text in {"高一", "高二", "高三"}:
        return grade_text
    if stage_text == "初中" and grade_text in {"初一", "初二", "初三"}:
        return grade_text
    return f"{stage_text}{grade_text}"


def _profile_exam_period(profile_id: str) -> str:
    return {
        "quiz": "随堂测验",
        "term": "期中/期末考试",
        "standard": "单元/阶段测试",
    }.get(str(profile_id or "").strip(), "考试")


def _paper_label(exam_period: str) -> str:
    normalized = str(exam_period or "考试").strip()
    return normalized if normalized.endswith("试卷") else f"{normalized}试卷"


__all__ = [
    "ExamMasterBinding",
    "ExamPlanEditValues",
    "compose_exam_plan_intent",
    "exam_master_display_label",
    "exam_master_id_from_plan",
    "normalized_output_root",
    "resolve_exam_master_binding",
    "validate_exam_plan_edit_values",
]
