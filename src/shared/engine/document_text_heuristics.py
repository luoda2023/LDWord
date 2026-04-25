"""Text heuristics shared by heading/TOC/reference modules."""

from __future__ import annotations

import re

_ROMAN_PAGE_CHARS = "\u2160\u2161\u2162\u2163\u2164\u2165\u2166\u2167\u2168\u2169\u216a\u216b"
_CN_NUM_CHARS = "\u3007\u96f6\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341"

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
_RE_NUMBERED_HEADING_PREFIX = re.compile(
    r"^(?:"
    r"\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u96f6\d]+[\u7ae0\u8282\u7bc7]"
    r"|[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u96f6]+\u3001"
    r"|\d+(?:\.\d+){0,5}"
    r")"
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
    if _RE_REFERENCE_ENTRY.match(raw):
        return True
    if not _RE_REFERENCE_ENTRY_PREFIX.match(raw):
        return False
    return looks_like_bibliographic_reference_line(raw)


def looks_like_date_placeholder_line(text: str) -> bool:
    norm = _norm_no_space(text)
    if not norm:
        return False
    return bool(_RE_DATE_PLACEHOLDER_LINE.match(norm))
