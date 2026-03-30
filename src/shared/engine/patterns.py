"""
patterns — 预编译正则常量库

所有正则在模块加载时编译，各模块直接引用，避免运行时重复编译。
"""

from __future__ import annotations

import re

# ── 占位符 ───────────────────────────────────────

PLACEHOLDER_DBL_BRACE = re.compile(r"\{\{(.+?)\}\}")
"""双花括号占位符: {{company_name}}"""

PLACEHOLDER_DOLLAR = re.compile(r"\$\{(.+?)\}")
"""美元花括号占位符: ${company_name}"""

# ── 中英文字符 ───────────────────────────────────

CJK_CHAR = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
"""单个 CJK 字符"""

CJK_RANGE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+")
"""连续 CJK 字符串"""

ASCII_WORD = re.compile(r"[A-Za-z0-9]+")
"""连续 ASCII 字母/数字"""

# ── 标点与符号 ───────────────────────────────────

CN_PUNCTUATION = re.compile(r"[\u3000-\u303f\uff00-\uffef]")
"""中文标点与全角符号"""

EN_PUNCTUATION = re.compile(r"[!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~]")
"""英文标点"""

PAIRED_QUOTES = {
    '"': '"', '"': '"',
    "'": "'", "'": "'",
    "「": "」", "『": "』",
    "（": "）", "(": ")",
    "【": "】", "[": "]",
}

# ── 空白 ─────────────────────────────────────────

MULTIPLE_SPACES = re.compile(r" {2,}")
"""连续多个半角空格"""

FULLWIDTH_SPACE = re.compile(r"\u3000")
"""全角空格"""

ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
"""零宽字符（零宽空格/零宽连接符/软连字符/BOM）"""

TAB_CHAR = re.compile(r"\t")

LEADING_TRAILING_SPACE = re.compile(r"(^\s+|\s+$)")
"""段首段尾空白"""

# ── 编号与标号 ───────────────────────────────────

HEADING_NUMBERING = re.compile(
    r"^(\d+(?:\.\d+)*)[.\s\u3000]"
)
"""阿拉伯数字编号: 1. / 1.1 / 1.1.1 开头"""

CN_HEADING_NUMBERING = re.compile(
    r"^[第]?([一二三四五六七八九十百千万]+)[章节条款项]"
)
"""中文编号: 第一章 / 第二节 / 一、"""

CN_ORDINAL = re.compile(
    r"^[（(]?([一二三四五六七八九十]+)[）)]"
)
"""中文括号编号: （一）/ (二)"""

CIRCLED_NUMBER = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]")
"""带圈数字"""

# ── 公式 ─────────────────────────────────────────

FORMULA_INLINE = re.compile(r"\$(.+?)\$")
"""行内公式: $E=mc^2$"""

FORMULA_BLOCK = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
"""块级公式: $$...$$"""

# ── 参考文献 ─────────────────────────────────────

CITATION_BRACKET = re.compile(r"\[(\d+(?:[,，、-]\d+)*)\]")
"""方括号引用: [1] / [1,2] / [1-3]"""

REFERENCE_LABEL = re.compile(r"^\[(\d+)\]")
"""参考文献标号: [1] 开头"""

# ── 金额日期 ─────────────────────────────────────

AMOUNT_PATTERN = re.compile(
    r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:元|万元|亿元)"
)
"""金额: 1,234.56元 / 100万元"""

DATE_ISO = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}")
"""ISO 日期: 2026-03-24"""

DATE_CN = re.compile(r"\d{4}年\d{1,2}月\d{1,2}日")
"""中文日期: 2026年3月24日"""

# ── 化学式 ───────────────────────────────────────

CHEMICAL_FORMULA = re.compile(
    r"\b([A-Z][a-z]?)(\d+)\b"
)
"""简单化学式: H2O / CO2 / NaOH"""
