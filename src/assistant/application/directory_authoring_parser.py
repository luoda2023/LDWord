"""Directory-driven long-document authoring trigger parsing.

The engine recognises the high-confidence "follow this outline / write by
chapter / produce the whole document" request and extracts the chapter list
either from the request text itself or from attached Markdown/plain-text
outline files.  It never fabricates an outline for ordinary chat.
"""

from __future__ import annotations

import re
from pathlib import Path

_WRITE_PATTERNS = (
    "按这个目录",
    "按这份目录",
    "按目录",
    "按这个大纲",
    "按这份大纲",
    "按大纲",
    "按我给",
    "按我提供",
    "按照这个目录",
    "按照目录",
    "按照大纲",
    "按上面的目录",
    "按上面的章",
    "参照目录",
    "照这个目录",
    "照目录",
    "根据目录",
    "根据这个目录",
    "按这个章节",
    "按章节",
    "分章节",
    "逐章",
    "一章一章",
    "每个章节",
    "每个章",
    "各章节",
    "写成一本书",
    "写一本",
    "整理成一本",
    "整理为一本",
    "汇编成",
    "成书",
)
_STAGE_HINT_TERMS = (
    "施工组织设计",
    "施组",
    "可研",
    "可行性研究",
    "初设",
    "初步设计",
    "概算",
    "预算",
    "招投标",
    "招标文件",
    "投标",
    "标书",
    "合同",
    "结算",
    "决算",
    "竣工",
    "验收",
    "造价",
    "专项方案",
    "安全",
    "质量",
    "监理",
    "施工方案",
    "设计说明书",
    "进度计划",
    "勘察",
    "项目建议书",
    "开工报告",
    "技术交底",
    "竣工资料",
)
_KIND_HINT_TERMS = (
    "施工组织设计",
    "可行性研究",
    "初步设计",
    "招标",
    "投标",
    "合同",
    "结算",
    "决算",
    "竣工",
    "验收",
    "造价",
    "专项",
    "方案",
    "报告",
    "说明书",
    "交底",
)
_CHAPTER_RE = re.compile(
    # 统一中文章节约定：第X(单元|部分|章|篇|部|卷|分)=顶级章节；节为章内小节不在此列。
    r"^\s*(?:第\s*[一二三四五六七八九十百千万0-9１-９]+\s*(?:单元|部分|[章篇部卷分])|"
    r"[一二三四五六七八九十百千万]+[、.．]|[0-9]+[、.．]\s*|[（(]?[一二三四五六七八九十]+[)）]\s*)"
)
_DEEP_PREFIX_RE = re.compile(r"^(?:[0-9]+(?:\.[0-9]+)*[、.．]?\s*|[一二三四五六七八九十]+[、.．]\s*)")
_NUM_RE = re.compile(r"[0-9]+")
_CN_NUM = "一二三四五六七八九十百千万"


def normalize_trigger_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def is_directory_authoring_trigger(query: str) -> bool:
    text = normalize_trigger_text(query)
    if not text:
        return False
    if any(token in text for token in ("格式证据", "克隆", "读格式", "只看", "帮我看看这份", "帮我校对", "帮我修改这份文档")):
        return False
    if "模板" in text and ("另存" in text or "存成" in text or "做成模板" in text or "把这份" in text):
        return False
    return any(token in text for token in _WRITE_PATTERNS)


def extract_doc_hint(query: str) -> tuple[str, str]:
    text = normalize_trigger_text(query)
    stage_hint = ""
    kind_hint = ""
    for token in _STAGE_HINT_TERMS:
        if token in text:
            stage_hint = token
            break
    for token in _KIND_HINT_TERMS:
        if token in text:
            kind_hint = token
            break
    return (stage_hint, kind_hint)


def parse_directory_attachments(
    refs,
) -> tuple[tuple[str, ...], tuple[str, ...], str, str, bool]:
    """Return (titles, notes, outline_text, errors, found_outline).

    Only Markdown/plain-text attachments are candidates; binary DOCX keeps its
    role untouched so normal document tasks still route correctly.
    """
    titles: list[str] = []
    notes: list[str] = []
    outline_texts: list[str] = []
    found = False
    for raw in tuple(refs or ()):
        if not isinstance(raw, dict):
            continue
        path_text = str(
            raw.get("path") or raw.get("file_path") or raw.get("local_path") or ""
        ).strip()
        if not path_text:
            continue
        path = Path(path_text).expanduser()
        suffix = path.suffix.casefold()
        if suffix not in {
            ".md", ".markdown", ".txt", ".docx", ".doc", ".wps",
            ".xlsx", ".xlsm", ".pptx", ".pptm",
        }:
            continue
        if not path.is_file():
            continue
        text = ""
        if suffix in {".md", ".markdown", ".txt"}:
            try:
                text = path.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
        elif suffix in {".xlsx", ".xlsm", ".pptx", ".pptm"}:
            try:
                from src.assistant.application.office_outline_source import (
                    office_text_for_outline,
                )

                text = office_text_for_outline(path)
            except Exception:  # noqa: BLE001 - unreadable office source
                continue
        else:
            try:
                text = _read_word_text(path)
            except Exception:  # noqa: BLE001 - unreadable Word source
                continue
        parsed_titles, parsed_notes = _split_outline(text)
        if parsed_titles:
            titles.extend(parsed_titles)
            notes.extend(parsed_notes)
            outline_texts.append(text)
            found = True
    return (tuple(titles), tuple(notes), "\n\n".join(outline_texts), "", found)


def parse_authoring_payload(
    query: str,
    *,
    attachments=None,
    context_text: str = "",
) -> dict[str, object]:
    """Public entry: resolve a full directory-authoring payload for a request.

    Returns dict with keys:
      titles / notes / outline_text / doc_hint / found_any / root_title
    When found_any is False the caller should not start authoring.
    """
    titles: list[str] = []
    notes: list[str] = []
    outline_text = str(context_text or "")
    attachments = tuple(attachments or ())
    found_any = False
    parsed, notes_from_text, text_from_att, err, found_att = parse_directory_attachments(
        attachments
    )
    if found_att:
        titles.extend(parsed)
        notes.extend(notes_from_text)
        outline_text = text_from_att or outline_text
        found_any = True
    if not found_att:
        inline_titles = _split_inline_titles(query)
        if inline_titles:
            titles.extend(inline_titles)
            found_any = True
    stage_hint, kind_hint = extract_doc_hint(query)
    root_title = ""
    lines = [ln.strip() for ln in outline_text.splitlines() if ln.strip()]
    if lines:
        root_title = lines[0][:80]
    return {
        "titles": tuple(titles),
        "notes": tuple(notes),
        "outline_text": outline_text,
        "doc_hint": f"{stage_hint} {kind_hint}".strip(),
        "found_any": bool(found_any),
        "root_title": root_title,
    }


_TOP_CHAPTER_RE = re.compile(
    r"^(?:第\s*[一二三四五六七八九十百千万0-9１-９]+\s*(?:单元|部分|[章篇部卷分])|"
    r"[一二三四五六七八九十百千万]+[、.．]|[（(]?[一二三四五六七八九十]+[)）])"
)
_SUB_HEADING_RE = re.compile(r"^(?:[0-9]+(?:\.[0-9]+)*\s*[、.．]?|[（(][0-9]+[)）])\s*")
_PLAIN_CHAPTER_RE = re.compile(
    r"^第\s*[一二三四五六七八九十百千万0-9１-９]+\s*(?:单元|部分|[章篇部卷分])"
)


def _is_top_chapter(text: str) -> bool:
    if _PLAIN_CHAPTER_RE.match(text):
        return True
    if re.match(r"^[一二三四五六七八九十百千万]+[、.．]", text):
        return True
    if len(text) <= 32 and re.match(r"^[（(][一二三四五六七八九十百千万]+[)）]", text):
        return True
    return False


def _read_word_text(path: Path) -> str:
    """Best-effort paragraph text extraction for Word attachments."""
    if path.suffix.casefold() in {".doc", ".wps"}:
        from src.services.legacy_word_import import ensure_editable_docx
        path = ensure_editable_docx(path).docx_path
    from docx import Document
    document = Document(str(path))
    chunks = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text and paragraph.text.strip()
    ]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                chunks.append("\t".join(cells))
    return "\n".join(chunks).strip()


def _split_outline(text: str) -> tuple[list[str], list[str]]:
    """Keep only the top-level chapter lines; deeper headings become notes.

    A typical outline lists top chapters either as Markdown H1 or as plain
    “第X章/一、” lines.  Sub-sections such as “1.1 项目概况” or “## 1.1”
    describe what that chapter must contain, so they belong to the chapter's
    notes, not to the generated title list.
    """
    titles: list[str] = []
    notes: list[str] = []
    saw_h1 = False
    h1_first = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        level = 0
        if line.lstrip().startswith("#"):
            for ch in line.lstrip():
                if ch != "#":
                    break
                level += 1
            stripped = line.lstrip()[level:].strip()
            if level == 1:
                saw_h1 = True
                if not titles and not notes:
                    h1_first = True
                if stripped:
                    titles.append(stripped)
                    notes.append("")
                continue
            # Deeper heading belongs to the current chapter's notes.
            if stripped and titles:
                notes[-1] += ("\n" if notes[-1] else "") + stripped
            continue
        if _is_top_chapter(stripped):
            titles.append(stripped)
            notes.append("")
            continue
        if titles and (_SUB_HEADING_RE.match(stripped) or len(stripped) <= 120):
            notes[-1] += ("\n" if notes[-1] else "") + stripped
    # Remove a leading document-title H1 that is not itself a chapter.
    if h1_first and titles:
        del titles[0]
        del notes[0]
    if not any(_is_top_chapter(t) for t in titles):
        return [], []
    return titles, notes


def _split_inline_titles(query: str) -> list[str]:
    found: list[str] = []
    saw_chapter_line = False
    for raw in str(query or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if _CHAPTER_RE.match(line) and len(line) <= 160:
            found.append(line)
            saw_chapter_line = True
    return found if saw_chapter_line else []


__all__ = [
    "extract_doc_hint",
    "is_directory_authoring_trigger",
    "normalize_trigger_text",
    "parse_authoring_payload",
    "parse_directory_attachments",
]
