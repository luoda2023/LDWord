"""Deterministic request and quality contract for Assistant-authored exams.

The provider may draft prose, but it does not decide whether an exam is
complete.  This module keeps the request interpretation and the generated
Markdown acceptance rules in one non-UI owner.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re

from src.assistant.contracts.task_plan import DeliveryContract
from src.shared.engine.exam_question_schema import ExamMarkdownImportResult
from src.shared.engine.exam_scale import (
    ExamScaleProfile,
    exam_scale_profile,
    resolve_exam_scale_profile,
)


_SUBJECTS = (
    "道德与法治",
    "信息技术",
    "语文",
    "数学",
    "英语",
    "物理",
    "化学",
    "生物",
    "历史",
    "地理",
    "政治",
    "科学",
)
_GRADE_RE = re.compile(r"(?:[一二三四五六七八九1-9]年级|初[一二三123]|高[一二三123])")
_TEXTBOOK_EDITION_RE = re.compile(
    r"(?:统编版|部编版|人教版|沪教版|苏教版|北师大版|鲁教版|冀教版|浙教版)"
)
_SCOPE_RE = re.compile(
    r"(?:考试范围|命题范围|范围)\s*[：:]?\s*([^，。；;\n]+)"
)
_DURATION_RE = re.compile(
    r"(?:考试时间|考试时长|时长|限时)\s*[：:]?\s*(\d+(?:\.\d+)?)\s*分钟"
)
_TOTAL_SCORE_RE = re.compile(
    r"(?:满分|总分)\s*[：:]?\s*(\d+(?:\.\d+)?)\s*分?"
)
_TOTAL_QUESTION_COUNT_RE = re.compile(
    r"(?:共|总共|一共|合计)\s*(\d+)\s*道(?:题|试题)?"
)
_PLACEHOLDER_RE = re.compile(r"\{\{[^{}\r\n]+\}\}")

_QUESTION_TYPE_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("choice", ("选择题", "单选题", "多选题", "选择")),
    ("judgment", ("判断题", "判断")),
    ("fill", ("填空题", "填空")),
    (
        "calculation",
        ("计算题", "解答题", "应用题", "证明题", "计算", "解答", "证明"),
    ),
    ("reading", ("阅读题", "阅读理解", "阅读")),
    ("writing", ("作文题", "写作题", "作文", "写作")),
    ("short_answer", ("简答题", "问答题", "简答", "问答")),
)


@dataclass(frozen=True, slots=True)
class ExamAuthoringRequirements:
    subject: str = ""
    grade: str = ""
    school_stage: str = ""
    exam_period: str = ""
    textbook_edition: str = ""
    semester: str = ""
    scope_hint: str = ""
    duration_minutes: float | None = None
    total_score: float | None = None
    question_count: int | None = None
    question_type_families: tuple[str, ...] = ()
    question_type_counts: tuple[tuple[str, int], ...] = ()
    analysis_required: bool = False

    def prompt_lines(self) -> tuple[str, ...]:
        lines: list[str] = [
            "不得在输出中保留 {{...}} 占位符。",
            "标题、学科、年级、考试时间和满分必须填写为具体值。",
            "每道题必须有分值和答案；选择题必须有至少两个选项。",
        ]
        if self.subject:
            lines.append(f"学科必须为：{self.subject}。")
        if self.grade:
            lines.append(f"年级必须为：{self.grade}。")
        if self.school_stage:
            lines.append(
                f"学段必须按“{self.school_stage}”理解，不得擅自改成其他学段。"
            )
        if self.exam_period:
            lines.append(
                f"考试类型必须为：{self.exam_period}；试卷标题不得替换成其他考试类型。"
            )
        if self.textbook_edition:
            lines.append(f"教材版本必须为：{self.textbook_edition}。")
        if self.semester:
            lines.append(f"册次/学期必须为：{self.semester}。")
        if self.scope_hint:
            lines.append(f"命题范围必须限定为：{self.scope_hint}。")
        if self.duration_minutes is not None:
            lines.append(f"考试时间必须为：{_format_number(self.duration_minutes)} 分钟。")
        if self.total_score is not None:
            lines.append(f"满分必须为：{_format_number(self.total_score)} 分。")
        if self.question_count is not None:
            lines.append(f"全卷题量必须为：{self.question_count} 道。")
        if self.question_type_families:
            labels = "、".join(
                _question_type_label(item) for item in self.question_type_families
            )
            lines.append(f"题型必须覆盖：{labels}。")
        for family, count in self.question_type_counts:
            lines.append(f"{_question_type_label(family)}必须为：{count} 道。")
        if self.analysis_required:
            lines.append("每道题都必须提供可核验的解析。")
        if self.subject == "信息技术":
            lines.append(
                "程序运行与纠错题必须逐行核算，并准确区分语法错误、运行时异常、"
                "语义错误和结果不符合预期；Python 中两个 input() 返回的字符串"
                "可以进行字典序比较，不得误写成类型不匹配报错。"
            )
        return tuple(lines)


@dataclass(frozen=True, slots=True)
class ExamSectionBlueprint:
    section_id: str
    label: str
    question_count: int
    total_score: float

    def question_score_plan(self) -> tuple[float, ...]:
        """Return an exact, human-friendly score for every question."""

        return _balanced_question_score_plan(
            self.total_score,
            self.question_count,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "label": self.label,
            "question_count": self.question_count,
            "total_score": self.total_score,
        }


@dataclass(frozen=True, slots=True)
class ExamBlueprint:
    """One deterministic assessment-scale contract for a generation run."""

    profile: ExamScaleProfile
    duration_minutes: float
    total_score: float
    question_count: int
    question_count_source: str
    min_section_count: int
    min_knowledge_point_count: int
    difficulty_counts: tuple[tuple[str, int], ...]
    section_blueprints: tuple[ExamSectionBlueprint, ...] = ()

    @property
    def scene_id(self) -> str:
        return self.profile.scene_id

    def prompt_lines(self) -> tuple[str, ...]:
        difficulty_text = "、".join(
            f"{_difficulty_label(level)} {count} 道"
            for level, count in self.difficulty_counts
        )
        section_line = ""
        if self.section_blueprints:
            section_line = "大题蓝图必须严格为：" + "；".join(
                f"{item.label} {item.question_count} 道/"
                f"{_format_number(item.total_score)} 分（各题依次 "
                + "、".join(
                    _format_number(score)
                    for score in item.question_score_plan()
                )
                + " 分）"
                for item in self.section_blueprints
            ) + "。"
        lines = [
            f"本次考试规格为“{self.profile.label}”（{self.profile.profile_id}）。",
            f"考试时间必须为：{_format_number(self.duration_minutes)} 分钟。",
            f"满分必须为：{_format_number(self.total_score)} 分。",
            f"全卷题量必须为：{self.question_count} 道，不得用子问虚增或合并题号。",
            (
                "满分为整数且不少于题量时，每道题分值必须使用正整数；"
                "总分不能平均整除时，用相邻整数在题目间分配，禁止用小数均分。"
            ),
            f"至少设置 {self.min_section_count} 个有题目的大题，并按学科逻辑组织题型。",
            (
                "学生卷渲染目标为 "
                f"{self.profile.min_student_pages}-{self.profile.max_student_pages} 页；"
                "通过完整题干、必要材料和合理作答空间达到，禁止插入空白页、"
                "放大字号或堆叠无效说明凑页数。"
            ),
            (
                f"难度结构必须为：{difficulty_text}；"
                f"按全卷题号依次分配为：{_difficulty_number_plan(self.difficulty_counts)}。"
            ),
            (
                "每道题在题干/选项之后单独给出 difficulty: 基础|中等|提高，"
                "并给出 knowledge_points: 知识点1、知识点2；这些是结构元数据，"
                "不要写进题干。"
            ),
            (
                f"全卷至少覆盖 {self.min_knowledge_point_count} 个不同知识点；"
                "不得只换数字、变量名或选项顺序重复出题。"
            ),
            (
                "主观题必须按真实作答量设置 answer_area_kind 和 answer_lines；"
                "选择题不要设置答题区。"
            ),
            (
                "题干内部如需列步骤，使用（1）（2）或项目符号，"
                "不要使用会被识别为新题号的“1.”“2.”。"
            ),
        ]
        if section_line:
            lines.insert(5, section_line)
        return tuple(lines)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile.profile_id,
            "scene_id": self.profile.scene_id,
            "label": self.profile.label,
            "duration_minutes": self.duration_minutes,
            "total_score": self.total_score,
            "question_count": self.question_count,
            "question_count_source": self.question_count_source,
            "student_page_range": [
                self.profile.min_student_pages,
                self.profile.max_student_pages,
            ],
            "min_section_count": self.min_section_count,
            "min_knowledge_point_count": self.min_knowledge_point_count,
            "difficulty_counts": dict(self.difficulty_counts),
            "sections": [
                section.to_dict() for section in self.section_blueprints
            ],
        }


def parse_exam_authoring_requirements(intent: str) -> ExamAuthoringRequirements:
    text = " ".join(str(intent or "").split())
    subject = next((item for item in _SUBJECTS if item in text), "")
    grade_matches = tuple(_GRADE_RE.finditer(text))
    duration_match = _DURATION_RE.search(text)
    total_score_match = _TOTAL_SCORE_RE.search(text)
    total_count_match = _TOTAL_QUESTION_COUNT_RE.search(text)
    textbook_matches = tuple(_TEXTBOOK_EDITION_RE.finditer(text))
    scope_matches = tuple(_SCOPE_RE.finditer(text))

    families = tuple(
        family
        for family, tokens in _QUESTION_TYPE_TOKENS
        if any(token in text for token in tokens)
    )
    type_counts: list[tuple[str, int]] = []
    for family, tokens in _QUESTION_TYPE_TOKENS:
        count = _question_type_count(text, tokens)
        if count is not None:
            type_counts.append((family, count))

    return ExamAuthoringRequirements(
        subject=subject,
        grade=grade_matches[-1].group(0) if grade_matches else "",
        school_stage=_last_school_stage(text),
        exam_period=_last_exam_period(text),
        textbook_edition=(
            textbook_matches[-1].group(0) if textbook_matches else ""
        ),
        semester=_last_semester(text),
        scope_hint=(scope_matches[-1].group(1).strip() if scope_matches else ""),
        duration_minutes=(
            float(duration_match.group(1)) if duration_match else None
        ),
        total_score=(
            float(total_score_match.group(1)) if total_score_match else None
        ),
        question_count=(
            int(total_count_match.group(1)) if total_count_match else None
        ),
        question_type_families=families,
        question_type_counts=tuple(type_counts),
        analysis_required=any(
            token in text
            for token in ("详细解析", "答案解析", "附解析", "含解析", "带解析")
        ),
    )


def exam_request_clarification(intent: str) -> dict[str, object] | None:
    """Return one deterministic clarification for contradictory school stages."""

    requirements = parse_exam_authoring_requirements(intent)
    grade = _normalize_grade(
        f"{requirements.school_stage}{requirements.grade}"
        if requirements.school_stage
        else requirements.grade
    )
    if requirements.school_stage == "初中" and grade in {
        "一年级",
        "二年级",
        "三年级",
        "四年级",
        "五年级",
        "六年级",
    }:
        return {
            "clarification_id": "exam_school_stage",
            "title": "确认年级所属学段",
            "prompt": (
                f"“{requirements.school_stage}{requirements.grade}”在不同地区可能指代不同学段。"
                "请选择本次试卷面向的学生范围，避免题目难度和教材内容错位。"
            ),
            "options": [
                {
                    "id": "primary_grade",
                    "label": f"小学{requirements.grade}",
                    "description": "按小学对应年级的课程难度和教材范围命题。",
                },
                {
                    "id": "middle_preparatory",
                    "label": f"初中预备班（{requirements.grade}）",
                    "description": "按初中预备年级的课程难度和教材范围命题。",
                },
            ],
        }
    return None


def resolve_exam_blueprint(
    intent: str,
    *,
    scene_id: str = "",
    scale_profile_id: str = "",
) -> ExamBlueprint:
    requirements = parse_exam_authoring_requirements(intent)
    counted_families = {family for family, _count in requirements.question_type_counts}
    derived_type_count = (
        sum(count for _family, count in requirements.question_type_counts)
        if requirements.question_type_counts
        and set(requirements.question_type_families) <= counted_families
        else None
    )
    requested_question_count = requirements.question_count or derived_type_count
    authoritative_profile_id = str(scale_profile_id or "").strip()
    if authoritative_profile_id:
        profile = exam_scale_profile(authoritative_profile_id)
        if profile.profile_id != authoritative_profile_id:
            raise ValueError(
                f"exam_scale_profile_unknown:{authoritative_profile_id}"
            )
    else:
        profile = resolve_exam_scale_profile(
            intent,
            scene_id=scene_id,
            duration_minutes=requirements.duration_minutes,
            total_score=requirements.total_score,
            question_count=requested_question_count,
        )
    question_count = requested_question_count or profile.default_question_count
    question_count_source = (
        "user_total"
        if requirements.question_count is not None
        else (
            "user_type_counts"
            if derived_type_count is not None
            else "scale_profile"
        )
    )
    min_section_count = profile.min_section_count
    if derived_type_count is not None:
        min_section_count = min(
            min_section_count,
            max(1, len(requirements.question_type_counts)),
        )
    total_score = (
        requirements.total_score
        if requirements.total_score is not None
        else float(profile.default_total_score)
    )
    return ExamBlueprint(
        profile=profile,
        duration_minutes=(
            requirements.duration_minutes
            if requirements.duration_minutes is not None
            else float(profile.default_duration_minutes)
        ),
        total_score=total_score,
        question_count=question_count,
        question_count_source=question_count_source,
        min_section_count=min(min_section_count, question_count),
        min_knowledge_point_count=min(
            profile.min_knowledge_point_count,
            question_count,
        ),
        difficulty_counts=_difficulty_counts(
            question_count,
            profile.difficulty_percentages,
        ),
        section_blueprints=_default_section_blueprints(
            profile,
            requirements.subject,
            question_count=question_count,
            total_score=total_score,
            # A user-visible plan editor writes the resolved total back into the
            # request.  That does not make the section mix user-owned.  Preserve
            # the safe default blueprint unless explicit per-type counts exist;
            # the helper already rejects totals that do not fit the profile.
            enabled=not requirements.question_type_counts,
        ),
    )


def exam_generation_prompt_addendum(
    intent: str,
    *,
    scene_id: str = "",
    scale_profile_id: str = "",
) -> str:
    requirements = parse_exam_authoring_requirements(intent)
    blueprint = resolve_exam_blueprint(
        intent,
        scene_id=scene_id,
        scale_profile_id=scale_profile_id,
    )
    rules = "\n".join(
        f"- {line}"
        for line in (*requirements.prompt_lines(), *blueprint.prompt_lines())
    )
    return (
        "\n\n【本次运行硬约束】\n"
        "上方 {{...}} 仅是字段说明，不是可以原样输出的内容。"
        "以当前用户消息为本次需求来源，并遵守以下可本地校验的规则：\n"
        f"{rules}"
    )


def _generated_exam_findings(
    markdown: str,
    result: ExamMarkdownImportResult,
    *,
    intent: str = "",
    scene_id: str = "",
    scale_profile_id: str = "",
) -> tuple[str, ...]:
    """Return every stable contract finding for one generated exam draft."""

    blockers: list[str] = []
    if _PLACEHOLDER_RE.search(str(markdown or "")):
        blockers.append("unresolved_template_placeholder")

    payload = dict(result.payload or {})
    required_metadata = {
        "paper_title": payload.get("paper_title"),
        "subject": payload.get("subject"),
        "grade": payload.get("grade"),
        "duration": payload.get("duration"),
        "total_score": payload.get("total_score"),
    }
    for key, value in required_metadata.items():
        if not str(value or "").strip():
            blockers.append(f"missing_{key}")
        elif _PLACEHOLDER_RE.search(str(value)):
            blockers.append(f"unresolved_{key}")

    summary = result.summary
    if summary.question_count < 1:
        blockers.append("question_count_zero")
    if summary.answered_question_count != summary.question_count:
        blockers.append("answer_coverage_incomplete")
    if summary.scored_question_count != summary.question_count:
        blockers.append("score_coverage_incomplete")
    if summary.declared_total_score is None:
        blockers.append("declared_total_score_missing")
    if (
        summary.declared_total_score is not None
        and summary.computed_total_score is not None
        and abs(summary.declared_total_score - summary.computed_total_score) > 0.01
    ):
        blockers.append("total_score_mismatch")

    actual_type_counts: dict[str, int] = {}
    normalized_question_signatures: list[str] = []
    python_string_comparison_error_claim = False
    python_mixed_type_comparison_missing_error_option = False
    python_mixed_type_comparison_answer_incorrect = False
    question_numbering_mode: str | None = None
    global_question_offset = 0
    payload_sections = _mapping_sequence(payload.get("sections"))
    for section in payload_sections:
        questions = _mapping_sequence(section.get("questions"))
        section_title = str(section.get("title") or "")
        family = _question_type_family(
            str(section.get("type") or section.get("question_type") or section_title)
        )
        if family:
            actual_type_counts[family] = actual_type_counts.get(family, 0) + len(
                questions
            )
        for question in questions:
            question_signature = _question_content_signature(question)
            if question_signature:
                normalized_question_signatures.append(question_signature)
            if _claims_python_string_comparison_is_runtime_error(question):
                python_string_comparison_error_claim = True
            if _python_relational_type_mismatch_expected(question):
                if not _question_offers_runtime_error_answer(question):
                    python_mixed_type_comparison_missing_error_option = True
                elif _first_mapping_text(
                    question,
                    ("answer", "answers", "correct_answer", "solution"),
                ) and not _question_answer_explains_runtime_error(question):
                    python_mixed_type_comparison_answer_incorrect = True
        numbers = [
            int(question.get("number"))
            for question in questions
            if str(question.get("number") or "").isdigit()
        ]
        referenced_numbers = tuple(
            int(value)
            for value in re.findall(r"第\s*(\d+)\s*题", section_title)
        )
        if (
            referenced_numbers
            and len(referenced_numbers) == len(numbers)
            and referenced_numbers != tuple(numbers)
        ):
            blockers.append("section_question_number_reference_mismatch")
        if numbers:
            section_sequence = list(range(1, len(numbers) + 1))
            global_sequence = list(
                range(
                    global_question_offset + 1,
                    global_question_offset + len(numbers) + 1,
                )
            )
            if question_numbering_mode == "section":
                number_sequence_valid = numbers == section_sequence
            elif question_numbering_mode == "global":
                number_sequence_valid = numbers == global_sequence
            elif section_sequence == global_sequence:
                number_sequence_valid = numbers == section_sequence
            elif numbers == section_sequence:
                question_numbering_mode = "section"
                number_sequence_valid = True
            elif numbers == global_sequence:
                question_numbering_mode = "global"
                number_sequence_valid = True
            else:
                number_sequence_valid = False
            if not number_sequence_valid:
                blockers.append("question_number_sequence_invalid")
            global_question_offset += len(numbers)
        declared_count = _declared_section_question_count(section_title)
        if declared_count is not None and declared_count != len(questions):
            blockers.append("section_question_count_mismatch")
        question_scores = [
            _first_number(question.get("score"))
            for question in questions
        ]
        if all(score is not None for score in question_scores):
            section_score = sum(
                float(score) for score in question_scores if score is not None
            )
            declared_section_score = _declared_section_score(section_title)
            if (
                declared_section_score is not None
                and abs(declared_section_score - section_score) > 0.01
            ):
                blockers.append("section_score_mismatch")
            declared_each_score = _declared_each_question_score(section_title)
            if declared_each_score is not None and any(
                abs(float(score) - declared_each_score) > 0.01
                for score in question_scores
                if score is not None
            ):
                blockers.append("section_per_question_score_mismatch")
        if family == "choice":
            for question in questions:
                options = question.get("options")
                if not isinstance(options, Sequence) or isinstance(
                    options, (str, bytes, bytearray)
                ) or len(tuple(options)) < 2:
                    blockers.append("choice_options_incomplete")
                    break

    requirements = parse_exam_authoring_requirements(intent)
    blueprint = resolve_exam_blueprint(
        intent,
        scene_id=scene_id,
        scale_profile_id=scale_profile_id,
    )
    actual_title = str(payload.get("paper_title") or "")
    actual_subject = str(payload.get("subject") or "")
    actual_grade = str(payload.get("grade") or "")
    if requirements.subject and _normalize_subject(
        requirements.subject
    ) != _normalize_subject(actual_subject):
        blockers.append("requested_subject_mismatch")
    expected_grade = _normalize_grade(
        f"{requirements.school_stage}{requirements.grade}"
        if requirements.school_stage
        else requirements.grade
    )
    if requirements.grade and expected_grade != _normalize_grade(actual_grade):
        blockers.append("requested_grade_mismatch")
    if requirements.exam_period:
        expected_period = _exam_period_token(requirements.exam_period)
        conflicting_periods = {
            token
            for token in ("期中", "期末", "随堂", "单元", "阶段")
            if token in actual_title and token != expected_period
        }
        if expected_period not in actual_title or conflicting_periods:
            blockers.append("requested_exam_period_mismatch")
    if (
        requirements.school_stage == "初中"
        and _normalize_grade(requirements.grade) == "六年级"
        and not any(token in actual_title for token in ("初中", "预备"))
    ):
        blockers.append("requested_school_stage_mismatch")
    if requirements.duration_minutes is not None:
        actual_duration = _first_number(payload.get("duration"))
        if actual_duration is None or abs(
            actual_duration - requirements.duration_minutes
        ) > 0.01:
            blockers.append("requested_duration_mismatch")
    else:
        actual_duration = _first_number(payload.get("duration"))
        if actual_duration is None or abs(
            actual_duration - blueprint.duration_minutes
        ) > 0.01:
            blockers.append("blueprint_duration_mismatch")
    if requirements.total_score is not None:
        actual_total = summary.declared_total_score
        if actual_total is None or abs(actual_total - requirements.total_score) > 0.01:
            blockers.append("requested_total_score_mismatch")
    else:
        actual_total = summary.declared_total_score
        if actual_total is None or abs(actual_total - blueprint.total_score) > 0.01:
            blockers.append("blueprint_total_score_mismatch")
    if summary.question_count != blueprint.question_count:
        blockers.append(
            "requested_question_count_mismatch"
            if blueprint.question_count_source != "scale_profile"
            else "blueprint_question_count_mismatch"
        )
    # Section shape and difficulty ratios are quality defaults, not fields the
    # user explicitly approved in the plan editor. They remain visible review
    # warnings, but must not discard an otherwise usable paper.
    if len(normalized_question_signatures) != len(
        set(normalized_question_signatures)
    ):
        blockers.append("duplicate_question_stem")
    if python_string_comparison_error_claim:
        blockers.append("python_string_comparison_error_claim")
    if python_mixed_type_comparison_missing_error_option:
        blockers.append("python_mixed_type_comparison_missing_error_option")
    if python_mixed_type_comparison_answer_incorrect:
        blockers.append("python_mixed_type_comparison_answer_incorrect")
    if (
        requirements.analysis_required
        and summary.analysis_count != summary.question_count
    ):
        blockers.append("requested_analysis_coverage_incomplete")
    for family in requirements.question_type_families:
        if actual_type_counts.get(family, 0) < 1:
            blockers.append(f"requested_question_type_missing:{family}")
    for family, expected_count in requirements.question_type_counts:
        if actual_type_counts.get(family, 0) != expected_count:
            blockers.append(f"requested_question_type_count_mismatch:{family}")

    return tuple(dict.fromkeys(blockers))


_REVIEWABLE_EXAM_FINDING_CODES = frozenset(
    {
        "missing_paper_title",
        "missing_subject",
        "missing_grade",
        "missing_duration",
        "missing_total_score",
        "answer_coverage_incomplete",
        "score_coverage_incomplete",
        "declared_total_score_missing",
        "total_score_mismatch",
        "section_question_number_reference_mismatch",
        "question_number_sequence_invalid",
        "section_question_count_mismatch",
        "section_score_mismatch",
        "section_per_question_score_mismatch",
        "choice_options_incomplete",
        "duplicate_question_stem",
        "requested_analysis_coverage_incomplete",
    }
)


def _generated_exam_finding_is_reviewable(code: str) -> bool:
    return str(code or "") in _REVIEWABLE_EXAM_FINDING_CODES


def generated_exam_blockers(
    markdown: str,
    result: ExamMarkdownImportResult,
    *,
    intent: str = "",
    scene_id: str = "",
    scale_profile_id: str = "",
) -> tuple[str, ...]:
    """Return findings that make production unsafe or violate explicit intent."""

    return tuple(
        code
        for code in _generated_exam_findings(
            markdown,
            result,
            intent=intent,
            scene_id=scene_id,
            scale_profile_id=scale_profile_id,
        )
        if not _generated_exam_finding_is_reviewable(code)
    )


def generated_exam_warnings(
    markdown: str,
    result: ExamMarkdownImportResult,
    *,
    intent: str = "",
    scene_id: str = "",
    scale_profile_id: str = "",
) -> tuple[str, ...]:
    """Return non-fatal quality findings for a structurally usable exam.

    These findings are deliberately kept out of ``generated_exam_blockers``:
    they are useful review signals, but do not prove that producing the paper
    would violate the user's request or corrupt the downstream document.
    """

    payload = dict(result.payload or {})
    blueprint = resolve_exam_blueprint(
        intent,
        scene_id=scene_id,
        scale_profile_id=scale_profile_id,
    )
    sections = _mapping_sequence(payload.get("sections"))
    knowledge_points: set[str] = set()
    actual_difficulty_counts = {"basic": 0, "medium": 0, "advanced": 0}
    missing_difficulty_count = 0
    invalid_difficulty_count = 0
    for section in sections:
        for question in _mapping_sequence(section.get("questions")):
            knowledge_points.update(_question_knowledge_points(question))
            raw_difficulty = _first_mapping_text(
                question,
                ("difficulty", "difficulty_level", "难度"),
            )
            if not raw_difficulty:
                missing_difficulty_count += 1
                continue
            difficulty = _normalize_difficulty(raw_difficulty)
            if difficulty:
                actual_difficulty_counts[difficulty] += 1
            else:
                invalid_difficulty_count += 1
    warnings: list[str] = [
        code
        for code in _generated_exam_findings(
            markdown,
            result,
            intent=intent,
            scene_id=scene_id,
            scale_profile_id=scale_profile_id,
        )
        if _generated_exam_finding_is_reviewable(code)
    ]
    if len(knowledge_points) < blueprint.min_knowledge_point_count:
        warnings.append("knowledge_point_coverage_too_low")
    if result.summary.section_count < blueprint.min_section_count:
        warnings.append("blueprint_section_count_too_low")
    if blueprint.section_blueprints:
        nonempty_sections = tuple(
            section
            for section in sections
            if _mapping_sequence(section.get("questions"))
        )
        if len(nonempty_sections) != len(blueprint.section_blueprints):
            warnings.append("blueprint_section_structure_mismatch")
        else:
            for section, expected in zip(
                nonempty_sections,
                blueprint.section_blueprints,
            ):
                questions = _mapping_sequence(section.get("questions"))
                if len(questions) != expected.question_count:
                    warnings.append(
                        "blueprint_section_question_count_mismatch:"
                        + expected.section_id
                    )
                scores = [
                    _first_number(question.get("score"))
                    for question in questions
                ]
                if any(score is None for score in scores) or abs(
                    sum(float(score) for score in scores if score is not None)
                    - expected.total_score
                ) > 0.01:
                    warnings.append(
                        "blueprint_section_score_mismatch:"
                        + expected.section_id
                    )
    if missing_difficulty_count:
        warnings.append("difficulty_metadata_incomplete")
    if invalid_difficulty_count:
        warnings.append("difficulty_metadata_invalid")
    expected_difficulties = dict(blueprint.difficulty_counts)
    if any(
        actual_difficulty_counts[level] != expected_difficulties[level]
        for level in expected_difficulties
    ):
        warnings.append("difficulty_distribution_mismatch")
    return tuple(dict.fromkeys(warnings))


def exam_delivery_contract_for_intent(
    intent: str,
    fallback: DeliveryContract,
) -> DeliveryContract:
    """Resolve an explicitly requested exam bundle without model-owned guessing."""

    text = " ".join(str(intent or "").split())
    student_only = any(
        token in text
        for token in ("只要学生卷", "仅学生卷", "学生卷即可", "不要答案", "无需答案", "不含答案")
    )
    answer_only = any(
        token in text
        for token in ("只要答案卷", "仅答案卷", "只要答案速查", "仅答案速查")
    )
    if student_only and not answer_only:
        return DeliveryContract(
            default_preset_id="student",
            preset_ids=("student",),
            required_artifact_keys=("student",),
        )
    if answer_only and not student_only:
        return DeliveryContract(
            default_preset_id="answer",
            preset_ids=("answer",),
            required_artifact_keys=("answer_key",),
        )

    mentions_student = any(token in text for token in ("学生卷", "学生版"))
    mentions_answer = any(
        token in text for token in ("答案卷", "答案版", "答案速查", "参考答案")
    )
    if mentions_student and not mentions_answer:
        return DeliveryContract(
            default_preset_id="student",
            preset_ids=("student",),
            required_artifact_keys=("student",),
        )
    if mentions_answer and not mentions_student:
        # “生成试卷并附答案” still means a student paper plus its answer key.
        if any(token in text for token in ("附答案", "含答案", "带答案")):
            return fallback
        return DeliveryContract(
            default_preset_id="answer",
            preset_ids=("answer",),
            required_artifact_keys=("answer_key",),
        )
    return fallback


def _question_type_count(text: str, tokens: tuple[str, ...]) -> int | None:
    for token in tokens:
        escaped = re.escape(token)
        before = re.search(rf"(\d+)\s*道\s*{escaped}", text)
        if before:
            return int(before.group(1))
        after = re.search(rf"{escaped}\s*(\d+)\s*道", text)
        if after:
            return int(after.group(1))
    return None


def _question_type_family(value: str) -> str:
    normalized = str(value or "").casefold()
    for family, tokens in _QUESTION_TYPE_TOKENS:
        if any(token.casefold() in normalized for token in tokens):
            return family
    return ""


def _question_type_label(family: str) -> str:
    return {
        "choice": "选择题",
        "judgment": "判断题",
        "fill": "填空题",
        "calculation": "计算/解答题",
        "reading": "阅读题",
        "writing": "作文/写作题",
        "short_answer": "简答题",
    }.get(family, family)


def _difficulty_counts(
    question_count: int,
    percentages: tuple[int, int, int],
) -> tuple[tuple[str, int], ...]:
    levels = ("basic", "medium", "advanced")
    raw_counts = [
        max(0.0, question_count * percentage / 100.0)
        for percentage in percentages
    ]
    counts = [int(value) for value in raw_counts]
    remaining = question_count - sum(counts)
    order = sorted(
        range(len(levels)),
        key=lambda index: (raw_counts[index] - counts[index], -index),
        reverse=True,
    )
    for index in order[:remaining]:
        counts[index] += 1
    return tuple(zip(levels, counts))


def _difficulty_label(level: str) -> str:
    return {
        "basic": "基础",
        "medium": "中等",
        "advanced": "提高",
    }.get(level, level)


def _difficulty_number_plan(
    difficulty_counts: tuple[tuple[str, int], ...],
) -> str:
    start = 1
    parts: list[str] = []
    for level, count in difficulty_counts:
        if count <= 0:
            continue
        end = start + count - 1
        number_text = str(start) if start == end else f"{start}-{end}"
        parts.append(f"题号 {number_text} 为{_difficulty_label(level)}")
        start = end + 1
    return "，".join(parts)


def _default_section_blueprints(
    profile: ExamScaleProfile,
    subject: str,
    *,
    question_count: int,
    total_score: float,
    enabled: bool,
) -> tuple[ExamSectionBlueprint, ...]:
    if not enabled:
        return ()
    subject_text = str(subject or "").casefold()
    information_technology = any(
        token in subject_text
        for token in ("信息技术", "计算机", "python", "编程")
    )
    language = any(
        token in subject_text
        for token in ("语文", "英语", "language", "english")
    )
    if profile.profile_id == "quiz":
        counts = (4, 3, 1)
        ratios = (8, 12, 10)
        labels = (
            "一、基础客观题",
            "二、阅读/分析题",
            "三、综合应用题",
        )
    elif profile.profile_id == "term":
        if information_technology:
            counts = (12, 5, 4, 3)
            labels = (
                "一、单项选择题",
                "二、基础填空与纠错题",
                "三、程序阅读与分析题",
                "四、程序设计题",
            )
        elif language:
            counts = (10, 8, 4, 2)
            labels = (
                "一、基础知识题",
                "二、阅读理解题",
                "三、综合运用题",
                "四、表达与写作题",
            )
        else:
            counts = (10, 6, 5, 3)
            labels = (
                "一、基础客观题",
                "二、理解与应用题",
                "三、综合解答题",
                "四、探究提高题",
            )
        ratios = (24, 20, 24, 32)
    else:
        if information_technology:
            counts = (10, 5, 3)
            labels = (
                "一、单项选择题",
                "二、程序阅读与分析题",
                "三、程序设计题",
            )
        elif language:
            counts = (8, 8, 2)
            labels = (
                "一、基础知识题",
                "二、阅读与综合运用题",
                "三、表达与写作题",
            )
        else:
            counts = (8, 6, 4)
            labels = (
                "一、基础客观题",
                "二、理解与应用题",
                "三、综合解答题",
            )
        ratios = (30, 30, 40)
    if sum(counts) != question_count:
        return ()
    section_scores = _allocate_score_total(
        total_score,
        ratios,
        minimums=counts,
    )
    return tuple(
        ExamSectionBlueprint(
            section_id=f"section_{index}",
            label=label,
            question_count=count,
            total_score=score,
        )
        for index, (label, count, score) in enumerate(
            zip(labels, counts, section_scores),
            start=1,
        )
    )


def _allocate_score_total(
    total_score: float,
    ratios: tuple[int, ...],
    *,
    minimums: tuple[int, ...] = (),
) -> tuple[float, ...]:
    ratio_total = max(1, sum(ratios))
    precision = 1 if float(total_score).is_integer() else 100
    total_units = round(float(total_score) * precision)
    raw_units = [total_units * ratio / ratio_total for ratio in ratios]
    allocated_units = [int(value) for value in raw_units]
    remainder = total_units - sum(allocated_units)
    remainder_order = sorted(
        range(len(ratios)),
        key=lambda index: (raw_units[index] - allocated_units[index], index),
        reverse=True,
    )
    for index in remainder_order[:remainder]:
        allocated_units[index] += 1
    if (
        precision == 1
        and len(minimums) == len(allocated_units)
        and total_units >= sum(minimums)
    ):
        for receiver, minimum in enumerate(minimums):
            deficit = max(0, minimum - allocated_units[receiver])
            while deficit:
                donor = max(
                    (
                        index
                        for index, donor_minimum in enumerate(minimums)
                        if allocated_units[index] > donor_minimum
                    ),
                    key=lambda index: allocated_units[index] - minimums[index],
                    default=None,
                )
                if donor is None:
                    break
                transfer = min(
                    deficit,
                    allocated_units[donor] - minimums[donor],
                )
                allocated_units[donor] -= transfer
                allocated_units[receiver] += transfer
                deficit -= transfer
    return tuple(value / precision for value in allocated_units)


def _balanced_question_score_plan(
    total_score: float,
    question_count: int,
) -> tuple[float, ...]:
    """Split one section total exactly without inventing awkward decimals.

    Whole-number totals use whole-number question scores whenever every question
    can receive at least one point.  A fractional fallback is retained only for
    mathematically incompatible requests such as 5 total points across 10
    questions.
    """

    count = max(1, int(question_count))
    use_whole_points = (
        float(total_score).is_integer() and float(total_score) >= count
    )
    precision = 1 if use_whole_points else 100
    total_units = round(float(total_score) * precision)
    base_units, remainder = divmod(total_units, count)
    return tuple(
        (
            base_units
            + (1 if question_index >= count - remainder else 0)
        )
        / precision
        for question_index in range(count)
    )


def _normalize_difficulty(value: str) -> str:
    normalized = re.sub(r"\s+", "", str(value or "")).casefold()
    if normalized in {"基础", "简单", "容易", "basic", "easy"}:
        return "basic"
    if normalized in {"中等", "适中", "medium", "moderate"}:
        return "medium"
    if normalized in {"提高", "困难", "较难", "难", "advanced", "hard"}:
        return "advanced"
    return ""


def _first_mapping_text(
    value: Mapping[str, object],
    keys: tuple[str, ...],
) -> str:
    for key in keys:
        text = str(value.get(key) or "").strip()
        if text:
            return text
    return ""


def _question_knowledge_points(question: Mapping[str, object]) -> set[str]:
    raw = (
        question.get("knowledge_points")
        or question.get("knowledgePoints")
        or question.get("tags")
        or question.get("知识点")
    )
    if isinstance(raw, Sequence) and not isinstance(
        raw,
        (str, bytes, bytearray),
    ):
        values = [str(item or "") for item in raw]
    else:
        values = re.split(r"[,，、;；|/]+", str(raw or ""))
    return {
        re.sub(r"\s+", "", item).casefold()
        for item in values
        if re.sub(r"\s+", "", item)
    }


def _normalize_question_stem(value: str) -> str:
    return re.sub(r"[\W_]+", "", str(value or ""), flags=re.UNICODE).casefold()


def _question_content_signature(question: Mapping[str, object]) -> str:
    """Identify a truly duplicated item without rejecting shared instructions.

    Language papers legitimately repeat stems such as "choose the correct
    answer" while varying the passage or options.  A duplicate is therefore
    only blocking when the material, stem, and options are all equivalent.
    """

    parts = [
        str(question.get(key) or "")
        for key in (
            "lead_in",
            "leadIn",
            "context",
            "material",
            "stem",
            "question",
        )
    ]
    raw_options = question.get("options")
    if isinstance(raw_options, Sequence) and not isinstance(
        raw_options,
        (str, bytes, bytearray),
    ):
        parts.extend(str(item or "") for item in raw_options)
    return _normalize_question_stem("\n".join(parts))


def _normalize_subject(value: str) -> str:
    normalized = re.sub(r"\s+", "", str(value or "")).casefold()
    normalized = re.sub(r"^(?:小学|初中|高中)", "", normalized)
    normalized = re.sub(r"(?:学科|科目)$", "", normalized)
    return normalized


def _claims_python_string_comparison_is_runtime_error(
    question: Mapping[str, object],
) -> bool:
    text = "\n".join(
        str(question.get(key) or "")
        for key in ("lead_in", "leadIn", "context", "material", "stem", "question")
    )
    input_variables = set(
        re.findall(
            r"(?m)^\s*([A-Za-z_]\w*)\s*=\s*input\s*\(",
            text,
        )
    )
    if len(input_variables) < 2:
        return False
    compared_input_variables = any(
        left in input_variables and right in input_variables
        for left, right in re.findall(
            r"\b([A-Za-z_]\w*)\s*(?:>=|<=|>|<)\s*([A-Za-z_]\w*)\b",
            text,
        )
    )
    if not compared_input_variables:
        return False
    normalized = re.sub(r"\s+", "", text).casefold()
    return (
        "不支持" in normalized
        and "报错" in normalized
    ) or any(
        token in normalized
        for token in (
            "系统会报错",
            "程序会报错",
            "运行时报错",
            "不支持'>'",
            '不支持">"',
            "不支持‘>’",
            "不支持“>”",
            "类型不匹配",
            "typeerror",
        )
    )


def _python_relational_type_mismatch_expected(
    question: Mapping[str, object],
) -> bool:
    text = "\n".join(
        str(question.get(key) or "")
        for key in ("lead_in", "leadIn", "context", "material", "stem", "question")
    )
    input_variables = set(
        re.findall(
            r"(?m)^\s*([A-Za-z_]\w*)\s*=\s*input\s*\(",
            text,
        )
    )
    numeric_variables = set(
        re.findall(
            r"(?m)^\s*([A-Za-z_]\w*)\s*=\s*-?\d+(?:\.\d+)?\s*$",
            text,
        )
    )
    if not input_variables:
        return False
    for left, right in re.findall(
        r"\b([A-Za-z_]\w*|-?\d+(?:\.\d+)?)\s*"
        r"(?:>=|<=|>|<)\s*"
        r"([A-Za-z_]\w*|-?\d+(?:\.\d+)?)\b",
        text,
    ):
        left_is_string = left in input_variables
        right_is_string = right in input_variables
        left_is_number = left in numeric_variables or bool(
            re.fullmatch(r"-?\d+(?:\.\d+)?", left)
        )
        right_is_number = right in numeric_variables or bool(
            re.fullmatch(r"-?\d+(?:\.\d+)?", right)
        )
        if (left_is_string and right_is_number) or (
            right_is_string and left_is_number
        ):
            return True
    return False


def _question_offers_runtime_error_answer(
    question: Mapping[str, object],
) -> bool:
    options = question.get("options")
    if not isinstance(options, Sequence) or isinstance(
        options,
        (str, bytes, bytearray),
    ):
        return True
    return any(_mentions_python_runtime_type_error(str(option or "")) for option in options)


def _question_answer_explains_runtime_error(
    question: Mapping[str, object],
) -> bool:
    answer = _first_mapping_text(
        question,
        ("answer", "answers", "correct_answer", "solution"),
    )
    analysis = _first_mapping_text(
        question,
        ("analysis", "explanation", "解析"),
    )
    options = question.get("options")
    selected_option = ""
    selected_match = re.match(r"^\s*([A-H])(?:\b|[\.、．])", answer, flags=re.I)
    if (
        selected_match
        and isinstance(options, Sequence)
        and not isinstance(options, (str, bytes, bytearray))
    ):
        selected_label = selected_match.group(1).upper()
        selected_option = next(
            (
                str(option or "")
                for option in options
                if re.match(
                    rf"^\s*{re.escape(selected_label)}(?:\b|[\.、．])",
                    str(option or ""),
                    flags=re.I,
                )
            ),
            "",
        )
    answer_evidence = "\n".join(
        item for item in (answer, selected_option) if item
    )
    if not _mentions_python_runtime_type_error(answer_evidence):
        return False
    if analysis:
        normalized_analysis = re.sub(r"\s+", "", analysis).casefold()
        if "ascii" in normalized_analysis or "逻辑值为true" in normalized_analysis:
            return False
        if not _mentions_python_runtime_type_error(analysis):
            return False
    return True


def _mentions_python_runtime_type_error(value: str) -> bool:
    normalized = re.sub(r"\s+", "", str(value or "")).casefold()
    return any(
        token in normalized
        for token in (
            "typeerror",
            "类型错误",
            "类型不兼容",
            "不同类型",
            "运行时异常",
            "程序异常",
            "发生异常",
            "出现异常",
            "程序报错",
            "运行时报错",
            "不能比较",
            "无法比较",
            "不支持比较",
        )
    )


def _mapping_sequence(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _first_number(value: object) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    return float(match.group(0)) if match else None


def _declared_section_question_count(value: str) -> int | None:
    match = re.search(r"共\s*(\d+)\s*小题", str(value or ""))
    return int(match.group(1)) if match else None


def _declared_section_score(value: str) -> float | None:
    matches = re.findall(r"共\s*(\d+(?:\.\d+)?)\s*分", str(value or ""))
    return float(matches[-1]) if matches else None


def _declared_each_question_score(value: str) -> float | None:
    match = re.search(r"每(?:小题|题)\s*(\d+(?:\.\d+)?)\s*分", str(value or ""))
    return float(match.group(1)) if match else None


def _normalize_grade(value: str) -> str:
    normalized = re.sub(r"\s+", "", str(value or ""))
    high_school = "高中" in normalized
    middle_school = "初中" in normalized and "预备" not in normalized
    normalized = re.sub(r"[（）()\[\]]", "", normalized)
    normalized = re.sub(r"^(?:小学|初中预备班|预备班|初中|高中)", "", normalized)
    normalized = normalized.replace("初1", "初一").replace(
        "初2", "初二"
    ).replace("初3", "初三").replace("高1", "高一").replace(
        "高2", "高二"
    ).replace("高3", "高三")
    if high_school:
        normalized = {
            "一年级": "高一",
            "二年级": "高二",
            "三年级": "高三",
        }.get(normalized, normalized)
    elif middle_school:
        normalized = {
            "一年级": "七年级",
            "二年级": "八年级",
            "三年级": "九年级",
        }.get(normalized, normalized)
    return {
        "初一": "七年级",
        "初二": "八年级",
        "初三": "九年级",
    }.get(normalized, normalized)


def _last_school_stage(value: str) -> str:
    matches: list[tuple[int, str]] = []
    for token, stage in (
        ("小学", "小学"),
        ("初中", "初中"),
        ("预备班", "初中"),
        ("预备年级", "初中"),
        ("高中", "高中"),
    ):
        matches.extend((match.start(), stage) for match in re.finditer(token, value))
    matches.extend(
        (match.start(), "初中")
        for match in re.finditer(r"初[一二三123]", value)
    )
    matches.extend(
        (match.start(), "高中")
        for match in re.finditer(r"高[一二三123]", value)
    )
    return max(matches, default=(-1, ""), key=lambda item: item[0])[1]


def _last_exam_period(value: str) -> str:
    matches: list[tuple[int, str]] = []
    for token, label in (
        ("期中", "期中考试"),
        ("期末", "期末考试"),
        ("随堂", "随堂测验"),
        ("单元", "单元测试"),
        ("阶段", "阶段测试"),
    ):
        matches.extend((match.start(), label) for match in re.finditer(token, value))
    return max(matches, default=(-1, ""), key=lambda item: item[0])[1]


def _exam_period_token(value: str) -> str:
    return next(
        (token for token in ("期中", "期末", "随堂", "单元", "阶段") if token in value),
        value,
    )


def _last_semester(value: str) -> str:
    matches: list[tuple[int, str]] = []
    for token, label in (
        ("上册", "上册"),
        ("下册", "下册"),
        ("上学期", "上学期"),
        ("下学期", "下学期"),
    ):
        matches.extend((match.start(), label) for match in re.finditer(token, value))
    return max(matches, default=(-1, ""), key=lambda item: item[0])[1]


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


__all__ = [
    "ExamAuthoringRequirements",
    "ExamBlueprint",
    "ExamSectionBlueprint",
    "exam_delivery_contract_for_intent",
    "exam_generation_prompt_addendum",
    "exam_request_clarification",
    "generated_exam_blockers",
    "generated_exam_warnings",
    "parse_exam_authoring_requirements",
    "resolve_exam_blueprint",
]
