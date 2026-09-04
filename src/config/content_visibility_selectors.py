from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContentVisibilitySelectorOption:
    selector: str
    label: str
    description: str = ""


COMMON_CONTENT_VISIBILITY_SELECTOR_OPTIONS: tuple[ContentVisibilitySelectorOption, ...] = (
    ContentVisibilitySelectorOption("answer", "答案", "学生版、客户版常见：不输出答案区"),
    ContentVisibilitySelectorOption("analysis", "解析", "学生版常见：不输出解析区"),
    ContentVisibilitySelectorOption("solution", "解题过程", "只保留题目时可移除解题过程"),
    ContentVisibilitySelectorOption("question_only", "题目区", "答案版常见：不输出仅题目区"),
    ContentVisibilitySelectorOption("teacher_note", "教师备注", "学生版、答案版常见：不输出教师备注"),
    ContentVisibilitySelectorOption("knowledge_points", "知识点", "学生版、答案版常见：不输出知识点提示"),
    ContentVisibilitySelectorOption("student_blank", "学生留白区", "解析版常见：不输出学生作答留白"),
    ContentVisibilitySelectorOption("question_body", "题干正文", "答题卡常见：不输出完整题干正文"),
    ContentVisibilitySelectorOption("internal", "内部内容", "客户版常见：不输出内部内容"),
    ContentVisibilitySelectorOption("internal_note", "内部备注", "客户版常见：不输出内部备注"),
    ContentVisibilitySelectorOption("review_note", "审阅备注", "正式稿常见：不输出审阅备注"),
)

_CONTENT_VISIBILITY_SELECTOR_LABELS = {
    option.selector: option.label for option in COMMON_CONTENT_VISIBILITY_SELECTOR_OPTIONS
}


def content_visibility_selector_label(selector: object) -> str:
    normalized = str(selector or "").strip()
    if not normalized:
        return ""
    return _CONTENT_VISIBILITY_SELECTOR_LABELS.get(
        normalized,
        normalized.replace("_", " "),
    )


__all__ = [
    "COMMON_CONTENT_VISIBILITY_SELECTOR_OPTIONS",
    "ContentVisibilitySelectorOption",
    "content_visibility_selector_label",
]
