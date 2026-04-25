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

from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from src.config.heading_normalize import CHAIN_NUMBER_STYLE_BY_CORE, CURRENT_CORE_STYLE_ALIASES
from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.numbering import format_number
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

# ── 占位符 → format_number 格式映射 ────────────
_PLACEHOLDER_FORMAT: dict[str, str] = {
    "nn": "arabic",
    "cn": "cn_lower",
    "CN": "cn_upper",
    "rn": "roman_lower",
    "RN": "roman_upper",
    "cc": "circled",
    "al": "alpha_lower",
    "AL": "alpha_upper",
}

_PLACEHOLDER_RE = re.compile(r"\{(" + "|".join(_PLACEHOLDER_FORMAT.keys()) + r"|chain)\}")

# ── display_core_style 自动展开表 ────────────────
_CORE_STYLE_AUTO_EXPAND: dict[str, str] = {
    "chinese_chapter": "第{cn}章",
    "chinese_section": "第{cn}节",
    "chinese_lower": "{cn}、",
    "chinese_upper": "{CN}、",
    "chinese_paren": "({cn})",
    "arabic": "{nn}",
    "arabic_paren": "{nn})",
    "roman_upper": "{RN}",
    "roman_lower": "{rn}",
    "circled": "{cc}",
    "circled_paren": "{cc}",
    "alpha_upper": "{AL}",
    "alpha_lower": "{al}",
}

# ── chain 解析 ──────────────────────────────────
_CHAIN_PATTERN = re.compile(r"^((?:parent\.)*)?current(?:_only)?$")


def _parse_chain(chain: str) -> list[str]:
    """解析 chain 字符串为 segments 列表。"""
    m = _CHAIN_PATTERN.match(chain)
    if not m:
        return chain.split(".")
    parts = []
    prefix = m.group(1) or ""
    if prefix:
        parts.extend(["parent"] * prefix.count("parent"))
    parts.append("current")
    return parts


def _resolve_chain_counters(
    level: int, counters: list[int], chain_segments: list[str],
) -> list[tuple[int, int, bool]]:
    """根据 chain segments 提取 (counter_value, source_level, is_current) 三元组。"""
    result: list[tuple[int, int, bool]] = []
    current_lvl = level
    for seg in reversed(chain_segments):
        if seg == "current":
            result.append((counters[current_lvl], current_lvl, True))
        elif seg == "parent":
            current_lvl -= 1
            val = counters[current_lvl] if current_lvl >= 1 else 0
            result.append((val, max(current_lvl, 1), False))
        else:
            result.append((0, current_lvl, False))
    result.reverse()
    return result


# ── 核心格式化引擎 ──────────────────────────────

def _format_level_number(
    level: int,
    counters: list[int],
    binding: HeadingLevelBindingConfig,
    level_bindings: dict[str, HeadingLevelBindingConfig] | None = None,
) -> str:
    """根据 binding 配置生成编号文本。

    渲染流程:
    1. 确定 display_template (显式 > display_core_style 自动展开)
    2. 解析 chain → 获取 (counter, source_level) 对列表
    3. 单级 chain: 替换模板中的 {nn}/{cn}/... 占位符
    4. 多级 chain: 每段用其源级别的 reference_core_style 格式化
    5. 拼接 title_separator
    """
    # 1. 确定 display_template
    template = binding.display_template
    if not template:
        template = _CORE_STYLE_AUTO_EXPAND.get(binding.display_core_style, "{nn}")

    # 2. 解析 chain
    chain_segments = _parse_chain(binding.chain)
    pairs = _resolve_chain_counters(level, counters, chain_segments)

    # 3. 单级 chain → 直接替换占位符
    if len(pairs) == 1:
        n = pairs[0][0]
        result = _replace_placeholders(template, n)
        return result + binding.title_separator

    # 4. 多级 chain → current 用 display_core_style, parent 用 reference_core_style
    fallback_fmt = _PLACEHOLDER_FORMAT.get(binding.chain_number_style, "arabic")
    chain_parts: list[str] = []
    for value, src_level, is_current in pairs:
        fmt = fallback_fmt
        if level_bindings:
            src_binding = level_bindings.get(f"heading{src_level}")
            if src_binding:
                # current 段用自己的 display 样式, parent 段用被引用时的 reference 样式
                style_key = src_binding.display_core_style if is_current else src_binding.reference_core_style
                fmt = _resolve_core_style_format(style_key, fallback_fmt)
        chain_parts.append(format_number(value, fmt))
    chain_str = binding.chain_separator.join(chain_parts)

    if "{chain}" in template:
        result = template.replace("{chain}", chain_str)
    elif _PLACEHOLDER_RE.search(template):
        result = _PLACEHOLDER_RE.sub(chain_str, template, count=1)
    else:
        result = chain_str

    return result + binding.title_separator


def _replace_placeholders(template: str, n: int) -> str:
    """替换模板中所有格式占位符为数字 n。"""
    def _replacer(m: re.Match) -> str:
        key = m.group(1)
        if key == "chain":
            return str(n)
        fmt = _PLACEHOLDER_FORMAT.get(key, "arabic")
        return format_number(n, fmt)

    return _PLACEHOLDER_RE.sub(_replacer, template)


def _resolve_core_style_format(style_key: str | None, fallback: str = "arabic") -> str:
    raw = str(style_key or "").strip()
    if not raw:
        return fallback
    normalized = CURRENT_CORE_STYLE_ALIASES.get(raw, raw)
    return CHAIN_NUMBER_STYLE_BY_CORE.get(normalized, fallback)


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
        enabled_by_default=True,
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
            return

        level_bindings = config.heading_numbering.level_bindings
        non_numbered = set(config.heading_model.non_numbered_title_texts or [])
        non_numbered_pfx = list(config.heading_model.non_numbered_prefixes or [])
        max_levels = config.heading_model.max_heading_levels
        counters: list[int] = [0] * 10
        count = 0

        for i, para in enumerate(doc.paragraphs):
            level = heading_map.get(i)
            if level is None:
                continue

            # 超出级数上限 → 只设 outline level, 不编号
            if level > max_levels:
                _set_outline_level(para, level)
                continue

            if _should_skip_numbering(para, non_numbered, non_numbered_pfx):
                _set_outline_level(para, level)
                continue

            binding_key = f"heading{level}"
            binding = level_bindings.get(binding_key)
            if not binding or not binding.enabled:
                _set_outline_level(para, level)
                continue

            counters[level] += 1
            for j in range(level + 1, 10):
                counters[j] = 0

            number_text = _format_level_number(level, counters, binding, level_bindings)
            _strip_existing_number(para)

            if number_text:
                _prepend_number(para, number_text)
                count += 1

            _set_outline_level(para, level)

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
