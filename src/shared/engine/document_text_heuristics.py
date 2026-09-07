"""Text heuristics shared by heading/TOC/reference modules."""

from __future__ import annotations

import re

_ROMAN_PAGE_CHARS = "\u2160\u2161\u2162\u2163\u2164\u2165\u2166\u2167\u2168\u2169\u216a\u216b"
_CN_NUM_CHARS = "\u3007\u96f6\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341"

# ---------------------------------------------------------------------------
# 统一的中文章节单位约定（标题识别 / 目录作者解析 / 工作台大纲解析共用）
#
# 顶级章节单位（可作拆分边界 / H1）：章、篇、部(含“部分”)、卷、分、单元
# 章节内小节单位（H2）：节
# 编号字符：中文数字 + 半角/全角阿拉伯数字 + 〇零两
# ---------------------------------------------------------------------------
_CN_ORDINAL_CLASS = "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u3007\u96f6\u4e24"
_CN_ORDINAL_CLASS_FULL = (
    _CN_ORDINAL_CLASS + "0-9" + "\uff11-\uff19" + "\uff10"
)
# 顶级单位（“部分”以“部”起头、“单元”为双字，均需先匹配多字形式）
CN_TOP_LEVEL_UNITS = "\u7ae0\u7bc7\u90e8\u5377\u5206"  # 章 篇 部 卷 分
CN_TOP_LEVEL_UNIT_RE = re.compile(r"(?:\u5355\u5143|\u90e8\u5206|[\u7ae0\u7bc7\u90e8\u5377\u5206])")
CN_SECTION_UNIT_RE = re.compile(r"\u8282")  # 节

_RE_TOC_TAB_PAGE_SUFFIX = re.compile(
    rf"(?:\t\s*(?:\d+|[IVXLCDMivxlcdm]+|[{_ROMAN_PAGE_CHARS}])){{1,3}}\s*$"
)
_RE_TOC_DOT_LEADER_SUFFIX = re.compile(
    rf"[.\uff0e\u3002\u2026\xb7]{{2,}}\s*(?:\d+|[IVXLCDMivxlcdm]+|[{_ROMAN_PAGE_CHARS}])\s*$"
)
_RE_TOC_LOOSE_PAGE_SUFFIX = re.compile(
    rf"(?:\t|[.\uff0e\u3002\u2026\xb7]{{2,}}|\s{{2,}})(?:\d+|[IVXLCDMivxlcdm]+|[{_ROMAN_PAGE_CHARS}])\s*$"
)
_RE_TOC_SINGLE_SPACE_PAGE_SUFFIX = re.compile(
    rf"\s+(?:\d{{1,3}}|[IVXLCDMivxlcdm]+|[{_ROMAN_PAGE_CHARS}])\s*$"
)
_RE_REFERENCE_ENTRY = re.compile(r"^\s*(\[\d{1,4}\]|[\uff08(]\d{1,4}[\uff09)]|\d{1,4}\.)\s+\S")
_RE_REFERENCE_ENTRY_PREFIX = re.compile(
    r"^\s*(?:\[\d{1,4}\]|[\uff08(]\d{1,4}[\uff09)]|\d{1,4}\.)\s*"
)
_RE_REFERENCE_TYPE_MARKER = re.compile(
    r"\[(?:J|M|D|C|R|P|S|N|Z|A|CP|EB/OL|DB/OL|OL)\]",
    re.IGNORECASE,
)
_RE_REFERENCE_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_RE_REFERENCE_VOLUME_ISSUE = re.compile(r"(?:,|\uff0c)\s*\d+\s*\(\s*\d+\s*\)\s*[:\uff1a]")
_RE_REFERENCE_ARTICLE_ID = re.compile(
    r"[:\uff1a]\s*(?:e?\d{4,}|\d+\s*-\s*\d+)\.?\s*$",
    re.IGNORECASE,
)
_RE_REFERENCE_PUB_HINT = re.compile(r"\b(?:doi|vol\.?|no\.?|pp\.?)\b", re.IGNORECASE)
_RE_DATE_PLACEHOLDER_LINE = re.compile(
    rf"^(?:\d{{2,4}}|[{_CN_NUM_CHARS}]{{2,6}})\u5e74(?:\d{{1,2}})?\u6708(?:(?:\d{{1,2}})?\u65e5)?$"
)
_CN_DIGITS_BCP = (
    "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d"
    "\u5341\u767e\u5343\u4e07\u96f6\u3007\u4e24"
    + r"\d"
)
# 统一：第X(单元|部分|章|篇|部|卷|分|节) 都是编号标题前缀（单元/部分 须先于单字匹配）
_RE_NUMBERED_HEADING_PREFIX = re.compile(
    rf"^(?:"
    rf"\u7b2c\s*[{_CN_DIGITS_BCP}]+\s*(?:\u5355\u5143|\u90e8\u5206|[\u7ae0\u8282\u7bc7\u90e8\u5377\u5206])"
    rf"|[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u96f6]+\u3001"
    rf"|\d+(?:\.\d+){{0,5}}"
    rf")"
)


def _norm_no_space(text: str) -> str:
    return re.sub(r"\s+", "", text or "").strip()


def looks_like_toc_entry_line(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    return bool(_RE_TOC_TAB_PAGE_SUFFIX.search(raw) or _RE_TOC_DOT_LEADER_SUFFIX.search(raw))


def looks_like_numbered_toc_entry_with_page_suffix(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    if not _RE_NUMBERED_HEADING_PREFIX.match(raw):
        return False
    return bool(_RE_TOC_LOOSE_PAGE_SUFFIX.search(raw) or _RE_TOC_SINGLE_SPACE_PAGE_SUFFIX.search(raw))


def looks_like_bibliographic_reference_line(text: str) -> bool:
    raw = (text or "").strip()
    if len(raw) < 20:
        return False

    has_prefix = bool(_RE_REFERENCE_ENTRY_PREFIX.match(raw))
    has_type_marker = bool(_RE_REFERENCE_TYPE_MARKER.search(raw))
    has_year = bool(_RE_REFERENCE_YEAR.search(raw))
    has_pub_tail = bool(
        _RE_REFERENCE_VOLUME_ISSUE.search(raw)
        or _RE_REFERENCE_ARTICLE_ID.search(raw)
        or _RE_REFERENCE_PUB_HINT.search(raw)
    )
    punctuation_count = sum(raw.count(ch) for ch in (",", "\uff0c", ".", "\uff0e", ";", "\uff1b", ":", "\uff1a"))
    authorish = punctuation_count >= 3

    if has_type_marker and has_year and (has_pub_tail or authorish or has_prefix):
        return True
    if has_prefix and has_year and has_pub_tail and authorish:
        return True
    return False


def looks_like_reference_entry_line(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    if _RE_REFERENCE_ENTRY.match(raw) and not re.match(r"^\s*\d{1,4}\.\s+", raw):
        return True
    if not _RE_REFERENCE_ENTRY_PREFIX.match(raw):
        return False
    # Plain decimal numbering is also the normal shape of generated report
    # subheadings ("1. Results", "2. Stability").  It becomes reference
    # evidence only when bibliographic markers are present.
    return looks_like_bibliographic_reference_line(raw)


def looks_like_date_placeholder_line(text: str) -> bool:
    norm = _norm_no_space(text)
    if not norm:
        return False
    return bool(_RE_DATE_PLACEHOLDER_LINE.match(norm))
