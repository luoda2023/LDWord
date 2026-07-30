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
        return tuple(lines)


def parse_exam_authoring_requirements(intent: str) -> ExamAuthoringRequirements:
    text = " ".join(str(intent or "").split())
    subject = next((item for item in _SUBJECTS if item in text), "")
    grade_match = _GRADE_RE.search(text)
    duration_match = _DURATION_RE.search(text)
    total_score_match = _TOTAL_SCORE_RE.search(text)
    total_count_match = _TOTAL_QUESTION_COUNT_RE.search(text)

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
        grade=grade_match.group(0) if grade_match else "",
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


def exam_generation_prompt_addendum(intent: str) -> str:
    requirements = parse_exam_authoring_requirements(intent)
    rules = "\n".join(f"- {line}" for line in requirements.prompt_lines())
    return (
        "\n\n【本次运行硬约束】\n"
        "上方 {{...}} 仅是字段说明，不是可以原样输出的内容。"
        "以当前用户消息为本次需求来源，并遵守以下可本地校验的规则：\n"
        f"{rules}"
    )


def generated_exam_blockers(
    markdown: str,
    result: ExamMarkdownImportResult,
    *,
    intent: str = "",
) -> tuple[str, ...]:
    """Return stable blocker codes for one Assistant-generated exam draft."""

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
    for section in _mapping_sequence(payload.get("sections")):
        questions = _mapping_sequence(section.get("questions"))
        section_title = str(section.get("title") or "")
        family = _question_type_family(
            str(section.get("type") or section.get("question_type") or section_title)
        )
        if family:
            actual_type_counts[family] = actual_type_counts.get(family, 0) + len(
                questions
            )
        numbers = [
            int(question.get("number"))
            for question in questions
            if str(question.get("number") or "").isdigit()
        ]
        if numbers and numbers != list(range(1, len(questions) + 1)):
            blockers.append("question_number_sequence_invalid")
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
    actual_subject = str(payload.get("subject") or "")
    actual_grade = str(payload.get("grade") or "")
    if requirements.subject and requirements.subject not in actual_subject:
        blockers.append("requested_subject_mismatch")
    if requirements.grade and _normalize_grade(requirements.grade) != _normalize_grade(
        actual_grade
    ):
        blockers.append("requested_grade_mismatch")
    if requirements.duration_minutes is not None:
        actual_duration = _first_number(payload.get("duration"))
        if actual_duration is None or abs(
            actual_duration - requirements.duration_minutes
        ) > 0.01:
            blockers.append("requested_duration_mismatch")
    if requirements.total_score is not None:
        actual_total = summary.declared_total_score
        if actual_total is None or abs(actual_total - requirements.total_score) > 0.01:
            blockers.append("requested_total_score_mismatch")
    if (
        requirements.question_count is not None
        and summary.question_count != requirements.question_count
    ):
        blockers.append("requested_question_count_mismatch")
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
    normalized = re.sub(r"\s+", "", str(value or "")).replace("初1", "初一").replace(
        "初2", "初二"
    ).replace("初3", "初三").replace("高1", "高一").replace(
        "高2", "高二"
    ).replace("高3", "高三")
    return {
        "初一": "七年级",
        "初二": "八年级",
        "初三": "九年级",
    }.get(normalized, normalized)


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


__all__ = [
    "ExamAuthoringRequirements",
    "exam_delivery_contract_for_intent",
    "exam_generation_prompt_addendum",
    "generated_exam_blockers",
    "parse_exam_authoring_requirements",
]
