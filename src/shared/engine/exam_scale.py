"""Stable scale profiles shared by exam authoring and delivery.

Page ranges are delivery targets for the student paper.  They are deliberately
kept separate from the Word master: a master owns visual style, while a scale
profile owns how much assessment content one run is expected to contain.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExamScaleProfile:
    profile_id: str
    scene_id: str
    label: str
    default_duration_minutes: int
    default_total_score: int
    default_question_count: int
    min_student_pages: int
    max_student_pages: int
    min_section_count: int
    min_knowledge_point_count: int
    difficulty_percentages: tuple[int, int, int] = (30, 50, 20)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "scene_id": self.scene_id,
            "label": self.label,
            "default_duration_minutes": self.default_duration_minutes,
            "default_total_score": self.default_total_score,
            "default_question_count": self.default_question_count,
            "student_page_range": [
                self.min_student_pages,
                self.max_student_pages,
            ],
            "min_section_count": self.min_section_count,
            "min_knowledge_point_count": self.min_knowledge_point_count,
            "difficulty_percentages": list(self.difficulty_percentages),
        }


EXAM_SCALE_PROFILES: tuple[ExamScaleProfile, ...] = (
    ExamScaleProfile(
        profile_id="quiz",
        scene_id="exam_quiz",
        label="随堂测验",
        default_duration_minutes=25,
        default_total_score=30,
        default_question_count=8,
        min_student_pages=2,
        max_student_pages=4,
        min_section_count=2,
        min_knowledge_point_count=3,
    ),
    ExamScaleProfile(
        profile_id="standard",
        scene_id="exam",
        label="完整单元/阶段试卷",
        default_duration_minutes=60,
        default_total_score=100,
        default_question_count=18,
        min_student_pages=4,
        max_student_pages=8,
        min_section_count=3,
        min_knowledge_point_count=5,
    ),
    ExamScaleProfile(
        profile_id="term",
        scene_id="exam_term",
        label="期中/期末试卷",
        default_duration_minutes=90,
        default_total_score=100,
        default_question_count=24,
        min_student_pages=6,
        max_student_pages=10,
        min_section_count=4,
        min_knowledge_point_count=7,
    ),
)

_PROFILE_BY_ID = {profile.profile_id: profile for profile in EXAM_SCALE_PROFILES}
_PROFILE_BY_SCENE_ID = {
    profile.scene_id: profile for profile in EXAM_SCALE_PROFILES
}

_QUIZ_HINTS = (
    "随堂",
    "小测",
    "课堂测验",
    "课时测验",
    "课时练习",
    "练习卷",
    "quiz",
)
_TERM_HINTS = (
    "期中",
    "期末",
    "终结性",
    "学业水平考试",
    "毕业考试",
    "term exam",
    "final exam",
)
_STANDARD_HINTS = (
    "单元",
    "阶段",
    "月考",
    "综合测试",
    "模拟考试",
    "测试卷",
)


def exam_scale_profile(profile_id: str) -> ExamScaleProfile:
    return _PROFILE_BY_ID.get(
        str(profile_id or "").strip(),
        _PROFILE_BY_ID["standard"],
    )


def exam_scale_profile_for_scene(scene_id: str) -> ExamScaleProfile:
    return _PROFILE_BY_SCENE_ID.get(
        str(scene_id or "").strip(),
        _PROFILE_BY_ID["standard"],
    )


def resolve_exam_scale_profile(
    intent: str,
    *,
    scene_id: str = "",
    duration_minutes: float | None = None,
    total_score: float | None = None,
    question_count: int | None = None,
) -> ExamScaleProfile:
    """Resolve one scale without letting a selected scene hide explicit intent."""

    text = " ".join(str(intent or "").casefold().split())
    if any(token in text for token in _TERM_HINTS):
        return _PROFILE_BY_ID["term"]
    if any(token in text for token in _QUIZ_HINTS):
        return _PROFILE_BY_ID["quiz"]
    if any(token in text for token in _STANDARD_HINTS):
        return _PROFILE_BY_ID["standard"]

    quiz_signals = sum(
        (
            duration_minutes is not None and duration_minutes <= 30,
            total_score is not None and total_score <= 40,
            question_count is not None and question_count <= 10,
        )
    )
    term_signals = sum(
        (
            duration_minutes is not None and duration_minutes >= 80,
            total_score is not None and total_score >= 100,
            question_count is not None and question_count >= 22,
        )
    )
    if quiz_signals >= 2:
        return _PROFILE_BY_ID["quiz"]
    if term_signals >= 2:
        return _PROFILE_BY_ID["term"]

    selected = _PROFILE_BY_SCENE_ID.get(str(scene_id or "").strip())
    if selected is not None:
        return selected
    if question_count is not None and question_count <= 8:
        return _PROFILE_BY_ID["quiz"]
    if duration_minutes is not None and duration_minutes <= 25:
        return _PROFILE_BY_ID["quiz"]
    if question_count is not None and question_count >= 24:
        return _PROFILE_BY_ID["term"]
    return _PROFILE_BY_ID["standard"]


__all__ = [
    "EXAM_SCALE_PROFILES",
    "ExamScaleProfile",
    "exam_scale_profile",
    "exam_scale_profile_for_scene",
    "resolve_exam_scale_profile",
]
