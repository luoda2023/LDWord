"""Shared semantic distinctions for document mutation requests."""

from __future__ import annotations

import re

_FORMAT_MUTATION_HINTS = (
    "排版",
    "排一下版",
    "重新排版",
    "格式化",
    "统一格式",
    "套模板",
    "替换模板",
    "应用模板",
    "页边距",
    "字体",
    "字号",
    "行距",
    "段距",
    "目录",
    "页码",
    "页眉",
    "页脚",
    "卷面",
    "美化",
)

_EXPLICIT_SEMANTIC_REVISION_HINTS = (
    "润色",
    "改写",
    "重写",
    "修订正文",
    "修改正文",
    "调整内容",
    "优化语言",
    "优化表达",
    "改专业",
    "更专业",
    "补充内容",
    "补全内容",
    "扩写",
    "缩写",
    "修改第",
    "调整第",
    "删除第",
    "替换第",
    "增加第",
    "新增第",
    "加题",
    "减题",
    "题量",
    "题型",
    "分值",
)

_GENERIC_REVISION_HINTS = (
    "修改",
    "改一下",
    "改改",
    "改成",
    "调整",
    "完善",
    "优化",
    "修正",
    "更改",
    "改动",
    "补充",
    "补全",
    "删除",
    "删掉",
    "去掉",
    "替换",
    "增加",
    "新增",
    "减少",
    "扩充",
    "压缩",
)

_SEMANTIC_NEGATION_RE = re.compile(
    r"(?:不要|不用|无需|不需要|别|不想|不打算)"
    r"(?:再|继续|帮我|给我|替我|进行)?"
    r"(?:润色|改写|重写|修改|调整|优化|完善|修正|更改|删除|增加|补充)?$"
)


def is_format_mutation_request(query: str) -> bool:
    normalized = _normalized(query)
    return any(token in normalized for token in _FORMAT_MUTATION_HINTS)


def is_semantic_revision_request(query: str) -> bool:
    """Return true only when document content, rather than layout, must change."""

    normalized = _normalized(query)
    if not normalized:
        return False
    for token in _EXPLICIT_SEMANTIC_REVISION_HINTS:
        if _contains_positive_token(normalized, token):
            return True
    if is_format_mutation_request(normalized):
        return False
    return any(
        _contains_positive_token(normalized, token) for token in _GENERIC_REVISION_HINTS
    )


def _contains_positive_token(query: str, token: str) -> bool:
    start = query.find(token)
    while start >= 0:
        prefix = query[max(0, start - 12) : start]
        if not _SEMANTIC_NEGATION_RE.search(prefix):
            return True
        start = query.find(token, start + 1)
    return False


def _normalized(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


__all__ = [
    "is_format_mutation_request",
    "is_semantic_revision_request",
]
