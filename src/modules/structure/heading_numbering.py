"""
heading_numbering — 标题编号模块（模板化全通量引擎）

模板占位符:
  {nn} 阿拉伯  {cn} 中文小写  {CN} 中文大写  {rn} 罗马小写  {RN} 罗马大写
  {cc} 带圈    {al} 字母小写  {AL} 字母大写  {chain} 多级自动连接

使用方式:
  display_template: "第{cn}章"  → 第一章
  display_template: "第{nn}章"  → 第1章
  display_template: "({cn})"   → (一)
  多级: chain: "parent.current" + chain_separator: "." → 3.1
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.document_scope_runtime import document_scope_allows_paragraph
from src.shared.engine.heading_numbering_format import format_heading_level_number
from src.shared.engine.ooxml_ops import qn, find_or_create

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from src.config.resolved import ResolvedConfig
    from src.config.template import HeadingLevelBindingConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


# ── 编号正则 (清除旧编号) ────────────────────────
_EXISTING_NUMBER_RE = re.compile(
    r"^(?:"
    r"\d+(?:\.\d+)*\.?\s*"
    r"|第[一二三四五六七八九十百]+[章节条款篇]\s*"
    r"|第\d+[章节条款篇]\s*"
    r"|第\s*\d+\s*[章节条款篇]\s*"
    r"|[（(][一二三四五六七八九十]+[）)]\s*"
    r"|[一二三四五六七八九十百]+[、.]\s*"
    r"|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]\s*"
    r"|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]\s*"
    r"|[a-zA-Z][.)]\s*"
    r")"
)

# ── 模块主体 ────────────────────────────────────

class HeadingNumberingModule(BaseModule):
    """标题编号模块（模板化全通量引擎）。"""

    meta = ModuleMeta(
        name="heading_numbering",
        description="标题编号",
        category="structure",
        requires_config=("heading_numbering", "heading_model"),
        depends_on=("heading_recognition",),
        consumes=("heading_map",),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        heading_map = context.heading_map
        if not heading_map:
            tracker.record(
                rule_name=self.meta.name,
                target="heading numbering",
                section="global",
                change_type="no_effect",
                before="requested",
                after="no recognized headings",
            )
            return

        level_bindings = config.heading_numbering.level_bindings
        non_numbered = set(config.heading_model.non_numbered_title_texts or [])
        non_numbered_pfx = list(config.heading_model.non_numbered_prefixes or [])
        max_levels = config.heading_model.max_heading_levels
        enabled_levels = {
            level
            for level in range(1, max_levels + 1)
            if (binding := level_bindings.get(f"heading{level}")) is not None
            and binding.enabled
        }
        if not enabled_levels:
            tracker.record(
                rule_name=self.meta.name,
                target="heading numbering",
                section="global",
                change_type="no_effect",
                before="requested",
                after="no enabled heading levels in the committed template",
            )
            return
        counters: list[int] = [0] * 10
        counter_started: list[bool] = [False] * 10
        count = 0

        for i, para in enumerate(doc.paragraphs):
            level = heading_map.get(i)
            if level is None:
                continue
            if not document_scope_allows_paragraph(context, i):
                continue

            binding_key = f"heading{level}"
            binding = level_bindings.get(binding_key)

            # 超出级数上限 → 只设 outline level, 不编号
            if level > max_levels:
                _set_toc_outline_level(para, level, binding)
                continue

            if _should_skip_numbering(para, non_numbered, non_numbered_pfx):
                _set_toc_outline_level(para, level, binding)
                continue

            if not binding or not binding.enabled:
                _set_toc_outline_level(para, level, binding)
                continue

            if not counter_started[level]:
                start_at = getattr(binding, "start_at", 1)
                counters[level] = 1 if start_at is None else int(start_at)
                counter_started[level] = True
            else:
                counters[level] += 1

            number_text = format_heading_level_number(
                level,
                counters,
                binding,
                level_bindings,
            )
            _strip_existing_number(para)

            if number_text:
                _prepend_number(para, number_text)
                count += 1

            _set_toc_outline_level(para, level, binding)
            _reset_deeper_counters(level, counters, counter_started, level_bindings)

        if not count:
            recognized_levels = sorted(set(heading_map.values()))
            tracker.record(
                rule_name=self.meta.name,
                target="heading numbering",
                section="global",
                change_type="no_effect",
                before=f"recognized levels: {recognized_levels}",
                after="recognized headings were excluded or their levels were disabled",
            )

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 个标题",
                section="global",
                change_type="format",
                before="(mixed/无编号)",
                after="已添加编号",
            )


# ── 辅助函数 ────────────────────────────────────

def _should_skip_numbering(
    para: Paragraph,
    non_numbered: set[str],
    non_numbered_prefixes: list[str],
) -> bool:
    """判断标题是否应跳过编号。

    三层检查:
    1. Word 样式名含 'unnumbered'
    2. 精确匹配 non_numbered_title_texts
    3. 前缀匹配 non_numbered_prefixes
    """
    # 第1层: 样式名
    style_name = para.style.name if para.style else ""
    if "unnumbered" in style_name.lower():
        return True
    # 清除旧编号后的纯文本
    text = (para.text or "").strip()
    match = _EXISTING_NUMBER_RE.match(text)
    clean_text = text[match.end():].strip() if match else text
    # 第2层: 精确匹配
    if clean_text in non_numbered:
        return True
    # 第3层: 前缀匹配
    for prefix in non_numbered_prefixes:
        if clean_text.startswith(prefix):
            return True
    return False


def _strip_existing_number(para: Paragraph) -> None:
    """清除段落开头的旧编号，支持编号跨多个 run 的情况。

    例: run0="第" + run1="一章 " + run2="绪论"
    → 清除后: run0="" + run1="" + run2="绪论" (空 run 会被保留以维持格式)
    """
    if not para.runs:
        return

    # 拼接前几个 run 的文本以匹配完整编号
    combined = ""
    run_boundaries: list[tuple[int, int]] = []  # (run_idx, char_count)
    for idx, run in enumerate(para.runs):
        run_text = run.text or ""
        run_boundaries.append((idx, len(run_text)))
        combined += run_text
        # 只需拼到足够长度即可（编号不会超过 30 字符）
        if len(combined) >= 30:
            break

    match = _EXISTING_NUMBER_RE.match(combined)
    if not match:
        return

    chars_to_strip = match.end()

    # 逐 run 消耗字符
    for idx, char_count in run_boundaries:
        run = para.runs[idx]
        if chars_to_strip <= 0:
            break
        if chars_to_strip >= char_count:
            # 整个 run 都在编号范围内 → 清空
            run.text = ""
            chars_to_strip -= char_count
        else:
            # 部分在编号范围内 → 截取
            run.text = (run.text or "")[chars_to_strip:]
            chars_to_strip = 0


def _prepend_number(para: Paragraph, number_text: str) -> None:
    if para.runs:
        para.runs[0].text = number_text + (para.runs[0].text or "")
    else:
        para.add_run(number_text)


def _set_outline_level(para: Paragraph, level: int) -> None:
    pPr = find_or_create(para._element, "w:pPr")
    outline_lvl = find_or_create(pPr, "w:outlineLvl")
    outline_lvl.set(qn("w:val"), str(level - 1))


def _set_toc_excluded_outline_level(para: Paragraph) -> None:
    pPr = find_or_create(para._element, "w:pPr")
    outline_lvl = find_or_create(pPr, "w:outlineLvl")
    outline_lvl.set(qn("w:val"), "9")


def _set_toc_outline_level(para: Paragraph, level: int, binding) -> None:
    if binding is not None and not bool(getattr(binding, "include_in_toc", True)):
        _set_toc_excluded_outline_level(para)
        return
    _set_outline_level(para, level)


def _normalize_restart_on(value) -> str:
    return str(value or "parent").strip().lower().replace("_", "-")


def _restart_target_level(value: str) -> int | None:
    match = re.fullmatch(r"(?:heading|level)?\s*(\d+)", value.replace("-", ""))
    if not match:
        return None
    level = int(match.group(1))
    return level if 1 <= level <= 8 else None


def _should_reset_counter_on_level(child_level: int, trigger_level: int, binding) -> bool:
    if child_level <= trigger_level:
        return False
    mode = _normalize_restart_on(getattr(binding, "restart_on", None))
    if mode in {"document", "never", "continuous", "none"}:
        return False
    target_level = _restart_target_level(mode)
    if target_level is not None:
        return trigger_level == target_level
    return True


def _reset_deeper_counters(
    trigger_level: int,
    counters: list[int],
    counter_started: list[bool],
    level_bindings: dict[str, HeadingLevelBindingConfig],
) -> None:
    for child_level in range(trigger_level + 1, min(len(counters), len(counter_started))):
        binding = level_bindings.get(f"heading{child_level}")
        if _should_reset_counter_on_level(child_level, trigger_level, binding):
            counters[child_level] = 0
            counter_started[child_level] = False
