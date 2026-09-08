# -*- coding: utf-8 -*-
"""篇幅目标（length targeting）——让“我要写一篇1000页的文档”可执行。

用户在需求里给出总篇幅（页数或字数）时，系统把总目标分摊到每一章，
逐章注入“本章目标字数/范围”指令；模型按指令扩写每章体量。分摊是
**软目标**（预算+范围），不是硬截断；实际字数以模型产出为准。

页数换算：1 页 ≈ 700 汉字（A4 五号字常规行距的工程文档经验值，
同时被导出侧的页数估算沿用同一量级）。
"""

from __future__ import annotations

from dataclasses import dataclass

import re

# 1 页 ≈ 700 字（与导出页数估算保持同一量级假设）。
CHARS_PER_PAGE = 700

# 单章体量上限：超过该值的多章任务按比例分摊，单章不超过此数，
# 由章节内部的小节扩写实现（避免给模型一个不可达的单一目标）。
_PER_CHAPTER_CAP = 12000

_PAGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(千页|页|page)")
_COUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(万字|千字|字)")


def parse_length_target(query: str) -> tuple[int, str] | None:
    """从需求文本解析总篇幅目标，返回 ``(总字数, 原文匹配片段)``。

    识别：
    * ``1000页`` / ``30页`` / ``2千页`` / ``1000 page``
    * ``50万字`` / ``20万字`` / ``80万字``

    未提及篇幅时返回 ``None``。
    """
    text = str(query or "")
    for pattern in (_PAGE_RE, _COUNT_RE):
        match = pattern.search(text)
        if not match:
            continue
        # 小数篇幅（如 2.5 千页）保留精度乘算，最后统一取整。
        number = float(match.group(1))
        unit = match.group(2)
        if unit == "千页":
            total = int(number * 1000 * CHARS_PER_PAGE)
        elif unit == "页" or unit == "page":
            total = int(number * CHARS_PER_PAGE)
        elif unit == "万字":
            total = int(number * 10000)
        elif unit == "千字":
            total = int(number * 1000)
        else:  # 字
            total = int(number)
        if total > 0:
            return total, match.group(0)
    return None


@dataclass(frozen=True, slots=True)
class ChapterLengthTarget:
    """一章的篇幅预算：目标字数 + 软范围。"""

    target: int
    minimum: int
    maximum: int


def allocate_chapter_targets(
    total_chars: int,
    chapter_count: int,
) -> list[ChapterLengthTarget]:
    """把总字数按章分摊：长章多分、短章少分，单章不超上限。

    * 总量 ≤ 单章上限 × 章数：均摊（向上取整）；
    * 超出时按上限封顶，超出部分仍要求各章在其上限内尽量充实
      （不硬截断——模型按各自上限写满即可接近总目标）。
    """
    if chapter_count <= 0 or total_chars <= 0:
        return []
    base = total_chars // chapter_count
    remainder = total_chars % chapter_count
    targets: list[ChapterLengthTarget] = []
    for index in range(chapter_count):
        # 前 remainder 章各多 1 字，凑齐总预算。
        target = base + (1 if index < remainder else 0)
        target = min(target, _PER_CHAPTER_CAP)
        minimum = max(600, int(target * 0.8))
        maximum = int(target * 1.25) + 200
        targets.append(ChapterLengthTarget(target, minimum, maximum))
    return targets


def chapter_length_directive(
    target: ChapterLengthTarget | None,
    *,
    chapter_number: int = 0,
    total_chapters: int = 0,
) -> str:
    """渲染逐章篇幅指令（注入章节 system prompt）。"""
    if target is None or target.target <= 0:
        return ""
    scope = ""
    if chapter_number and total_chapters:
        scope = f"（第 {chapter_number}/{total_chapters} 章）"
    return (
        f"\n\n【本章篇幅要求{scope}】\n"
        f"本章正文目标约 {target.target} 个汉字（不少于 {target.minimum} 字，"
        f"不超过 {target.maximum} 字）。"
        "这是把整篇文档的总篇幅目标分摊到本章的硬性要求：必须通过"
        "充实的小节内容、展开的说明、行业惯例所需的表格与数据占位"
        "（如“待补充”）把篇幅写满；不允许用目录、套话或提前收尾来缩短本章。"
        "若单次回复无法容纳，按之前说明继续输出，系统会自动拼接续写。"
    )


def total_length_directive(total_chars: int, matched_text: str) -> str:
    """渲染单次整篇生成（无分章）时的总篇幅指令。"""
    pages = total_chars / CHARS_PER_PAGE
    pretty = f"{pages:.0f}" if pages >= 10 else f"{pages:.1f}"
    return (
        f"\n\n【全篇篇幅要求】\n用户要求成稿约 {pretty} 页"
        f"（约 {total_chars} 个汉字，用户原话：{matched_text}）。"
        "必须通过充实的小节内容、展开的说明、行业惯例所需的表格与数据"
        "占位（如“待补充”）把篇幅写满，不允许用套话或提前收尾来缩短。"
        "若单次回复无法容纳，系统会自动要求续写，请直接续写不要重复。"
    )


__all__ = [
    "CHARS_PER_PAGE",
    "ChapterLengthTarget",
    "allocate_chapter_targets",
    "chapter_length_directive",
    "parse_length_target",
    "total_length_directive",
]
